"""Drafts of the two files a person had to write by hand before ``cut`` and ``deliver`` (P11-07; rehearsal manual steps M1-M3).

* ``edit_draft`` - ``05_edit.json``: one TAKE event per generation in shot-list order, using the latest ACCEPTED take of the
  current shot version, plus a title card (film title and the AI line; ``deliver`` blocks ``AI_LABEL_MISSING`` without it).
  A generation with no accepted take gets no event and is listed in ``missing``: the draft never invents footage.
* ``generators_draft`` - ``generators.json``: the video tool from the route/model of the take log and the image tool from the
  sources of the registered start stills, each with its role.

Both are drafts for a human to review and edit. They never overwrite a file somebody already filled in.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

AI_LINE = {"vi": "Tạo bằng AI"}  # any other language: English
AI_LINE_DEFAULT = "Generated with AI"
_TAKE_NO = re.compile(r"_t(\d+)$")


def _filled(path: Path, key: str | None) -> bool:
    """True when the file holds something a person wrote (`{}`, an empty list or no file is blank)."""
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True  # unreadable is not blank: never overwrite what cannot be read
    if key is not None:
        return bool(isinstance(data, dict) and data.get(key))
    return bool(data)


def _latest_accepted(log: Any, decl: Any) -> Any | None:
    takes = [t for t in log.for_generation(decl.generation_id) if t.status == "ACCEPTED" and t.shot_version == decl.version]
    return max(takes, key=lambda t: int(_TAKE_NO.search(t.take_id).group(1)) if _TAKE_NO.search(t.take_id) else 0, default=None)


def edit_draft(pkg: Any) -> dict[str, Any]:
    """The EDL draft and the generations it could not fill. Raises ValueError when there is nothing to draft or a real EDL exists."""
    from film_pipeline.production.takes import load_log
    root = Path(pkg.root)
    if _filled(root / "05_edit.json", "events"):
        raise ValueError("05_edit.json already has events: edit it by hand (a draft never overwrites an EDL)")
    shots = pkg.typed.get("shots")
    if shots is None:
        raise ValueError("edit --init needs a valid 04_shots.json")
    log = load_log(root, pkg.header.film_id)
    events, missing = [], []
    for decl in shots.generations:
        take = _latest_accepted(log, decl)
        if take is None:
            missing.append(decl.generation_id)
        else:
            events.append({"event_id": decl.generation_id, "kind": "TAKE", "take_id": take.take_id})
    if not events:
        raise ValueError("no ACCEPTED take of the current shot version: review the takes first (film.py review)")
    ai = AI_LINE.get(pkg.header.language, AI_LINE_DEFAULT)
    title = [{"text": pkg.header.title.upper(), "size": 96}, {"text": ai, "size": 28}]
    return {"events": events, "title": title, "missing": missing}


def generators_draft(pkg: Any) -> list[dict[str, str]]:
    """Records for generators.json from what the package says was used; raises when nothing says so."""
    from film_pipeline.production import stills as stills_mod
    from film_pipeline.production.takes import load_log
    root = Path(pkg.root)
    if _filled(root / "generators.json", None):
        raise ValueError("generators.json already has entries: edit it by hand (a draft never overwrites it)")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for take in load_log(root, pkg.header.film_id).takes:
        key = (take.route, take.model)
        if key in seen or not take.model:
            continue
        seen.add(key)
        records.append({"role": "video+audio", "name": "Google Flow" if "khung" in take.route.lower() or "flow" in take.route.lower()
                        else take.route, "model": take.model, "settings": take.route})
    sources: set[str] = set()
    if "preprod" in pkg.typed and "shots" in pkg.typed:
        sources = {r.source for r in stills_mod._records(pkg).values() if r.source}
    for source in sorted(sources):
        records.append({"role": "image", "name": source, "model": source, "settings": ""})
    if not records:
        raise ValueError("no take and no registered still names a tool: register takes or stills first, or write generators.json by hand")
    return records


def write_json(path: Path, data: Any) -> Path:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Path(path)
