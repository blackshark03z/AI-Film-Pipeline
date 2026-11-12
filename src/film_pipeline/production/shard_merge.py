"""Bring a shard branch's take results into the current checkout (`film.py takes --merge-from <git-ref>`).

Shards run on separate worktrees/branches (one Flow profile each) and append to ``takes/index.json`` and
``takes/send_log.jsonl``; a plain git merge of those two append-only files always conflicts. This unions them:

* ``takes/index.json``: union by ``take_id``; the same ``take_id`` with different content is a hard error (nothing written).
* ``takes/send_log.jsonl``: union by exact line, ordered by ``at`` (the current checkout's lines first on a tie).
* everything else is left to a normal ``git merge``; ``04_shots.json`` is only *reported* (same / ours_changed /
  theirs_changed / CONFLICT against the merge base), never resolved here.

"Our" side is the working-tree file; if it still holds git conflict markers (a ``git merge`` in progress) or does not
parse, the committed ``HEAD`` version is used instead.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from film_pipeline.production.runtime import atomic_json, atomic_text
from film_pipeline.production.takes import TakeLog

INDEX, SEND_LOG, SHOTS = "takes/index.json", "takes/send_log.jsonl", "04_shots.json"
_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


class ShardMergeError(ValueError):
    pass


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if check and done.returncode != 0:
        raise ShardMergeError(f"git {' '.join(args[:2])} failed: {done.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return done


def _show(root: Path, ref: str, prefix: str, name: str) -> str | None:
    done = _git(root, "show", f"{ref}:{prefix}{name}", check=False)
    return done.stdout.decode("utf-8") if done.returncode == 0 else None


def _blob(root: Path, ref: str, prefix: str, name: str) -> str | None:
    done = _git(root, "rev-parse", "--verify", "-q", f"{ref}:{prefix}{name}", check=False)
    return done.stdout.decode().strip() if done.returncode == 0 else None


def _has_markers(text: str) -> bool:
    return any(raw.startswith(_MARKERS) for raw in text.splitlines())


def _when(raw: str) -> datetime:
    try:
        at = datetime.fromisoformat(json.loads(raw)["at"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ShardMergeError(f"send_log line without a valid 'at': {raw[:80]}") from exc
    return at if at.tzinfo else at.astimezone()


def _parse_index(text: str, label: str) -> TakeLog:
    try:
        return TakeLog.model_validate_json(text)
    except ValueError as exc:
        raise ShardMergeError(f"{label} takes/index.json is not a valid take log: {str(exc)[:160]}") from exc


def _lines(text: str) -> list[str]:
    return [raw.strip() for raw in text.splitlines() if raw.strip()]


def merge_shard_takes(film_root: Path, ref: str) -> dict[str, Any]:
    root = Path(film_root).resolve()
    _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    prefix = _git(root, "rev-parse", "--show-prefix").stdout.decode().strip()
    # ---- their side (committed in the shard branch) -------------------------------------------------------------------
    theirs_index_text = _show(root, ref, prefix, INDEX)
    theirs_log_text = _show(root, ref, prefix, SEND_LOG) or ""
    # ---- our side: the working tree unless a merge left markers in it --------------------------------------------------
    source = "worktree"
    index_path, log_path = root / INDEX, root / SEND_LOG
    ours_index_text = index_path.read_text(encoding="utf-8") if index_path.is_file() else None
    ours_log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    try:
        if ours_index_text is not None:
            if _has_markers(ours_index_text):
                raise ValueError("markers")
            TakeLog.model_validate_json(ours_index_text)
    except ValueError:
        ours_index_text, source = _show(root, "HEAD", prefix, INDEX), "HEAD"
    if _has_markers(ours_log_text):
        ours_log_text, source = _show(root, "HEAD", prefix, SEND_LOG) or "", "HEAD"
    # ---- index: union by take_id --------------------------------------------------------------------------------------
    ours = _parse_index(ours_index_text, "our") if ours_index_text else None
    theirs = _parse_index(theirs_index_text, "shard") if theirs_index_text else None
    if ours and theirs and ours.film_id != theirs.film_id:
        raise ShardMergeError(f"film mismatch: ours {ours.film_id!r}, shard {theirs.film_id!r}")
    merged = list(ours.takes) if ours else []
    by_id = {t.take_id: t for t in merged}
    added, clashes = [], []
    for take in (theirs.takes if theirs else []):
        have = by_id.get(take.take_id)
        if have is None:
            merged.append(take)
            by_id[take.take_id] = take
            added.append(take.take_id)
        elif have.model_dump(mode="json") != take.model_dump(mode="json"):
            clashes.append(take.take_id)
    if clashes:
        raise ShardMergeError("take_id present on both sides with different content: " + ", ".join(sorted(clashes)))
    # ---- send log: union by exact line, ordered by `at` ---------------------------------------------------------------
    ours_lines = _lines(ours_log_text)
    seen = set(ours_lines)
    new_lines = []
    for raw in _lines(theirs_log_text):
        if raw not in seen:
            seen.add(raw)
            new_lines.append(raw)
    ordered = sorted(ours_lines + new_lines, key=_when)   # validates every line; stable: ours first on a tie
    # ---- write (only when something changed) --------------------------------------------------------------------------
    if added:
        film_id = (ours or theirs).film_id
        atomic_json(index_path, TakeLog(film_id=film_id, takes=merged).model_dump(mode="json"))
    if new_lines or (ordered != ours_lines):
        atomic_text(log_path, "".join(raw + "\n" for raw in ordered))
    # ---- 04_shots.json: report only -----------------------------------------------------------------------------------
    base = _git(root, "merge-base", "HEAD", ref, check=False).stdout.decode().strip()
    base_blob = _blob(root, base, prefix, SHOTS) if base else None
    mine, theirs_blob = _blob(root, "HEAD", prefix, SHOTS), _blob(root, ref, prefix, SHOTS)
    if mine == theirs_blob:
        shots = "same"
    elif theirs_blob == base_blob:
        shots = "ours_changed"
    elif mine == base_blob:
        shots = "theirs_changed"
    else:
        shots = "CONFLICT"
    return {"ref": ref, "ours_source": source, "takes_added": added, "send_log_lines_added": len(new_lines),
            "takes_total": len(merged), "shots": shots, "conflicts": [SHOTS] if shots == "CONFLICT" else [],
            "next": "git merge the shard branch for the remaining files; 04_shots.json: "
                    + {"same": "identical", "ours_changed": "only this branch changed it",
                       "theirs_changed": "git merge will take the shard's change",
                       "CONFLICT": "both sides changed it - resolve by hand"}[shots]}
