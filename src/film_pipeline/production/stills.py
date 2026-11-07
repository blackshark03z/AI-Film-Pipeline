"""Start-still stage of a drama Production Package (P10-02).

A generation that opens a chain starts from an image: the "start still". Making that image is an operator step done outside
this module (ChatGPT in the GPM browser, a free tool); nothing here calls a provider. What the package owns is the record:

* ``03_preprod.json`` ``stills[<generation_id>]`` holds the registered image (path under ``media/stills/``, sha256), the sha256
  of the still prompt it answers (the text ``film.py plan`` writes to ``stills/start_<gid>.txt``), where it came from, the
  credits it cost and the reviewer who approved it.
* An approval is only worth something while it describes what is on disk: if the still prompt is re-planned to different text,
  or the image file changes, the approval is stale and the still counts as not approved.
* ``generate`` and ``animatic`` take approved stills from this record by default.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from film_pipeline.production.sections import StillRecord
from film_pipeline.production.takes import sha256_file, sha256_text

STILLS_DIR = ("media", "stills")
PREPROD_FILE = "03_preprod.json"
_FORMATS = ((b"\x89PNG\r\n\x1a\n", ".png"), (b"\xff\xd8\xff", ".jpg"))

StillState = Literal["MISSING", "UNAPPROVED", "APPROVED", "STALE_PROMPT", "STALE_FILE"]


def prompt_hash(text: str) -> str:
    return sha256_text(text.strip())


def still_prompts(pkg: Any) -> dict[str, str]:
    """generation_id -> the still prompt the current plan would write."""
    from film_pipeline.production.plan import _Plan
    plan = _Plan(pkg, None, None)
    return {decl.generation_id: plan.still_prompt(decl, plan.unit_for(decl)) for decl in plan.shots.generations}


def chain_heads(pkg: Any) -> list[str]:
    """Generations that start from a still (the others start from the previous take's end frame)."""
    return [g.generation_id for g in pkg.typed["shots"].generations if not g.previous_generation_id]


def stills_dir(root: Path) -> Path:
    return Path(root).joinpath(*STILLS_DIR)


def _records(pkg: Any) -> dict[str, StillRecord]:
    pre = pkg.typed.get("preprod")
    return dict(pre.stills) if pre is not None else {}


def state_of(pkg: Any, gid: str, prompt: str | None = None) -> tuple[StillState, str]:
    """(state, reason). APPROVED only while the prompt and the file on disk still match the approval."""
    record = _records(pkg).get(gid)
    if record is None:
        return "MISSING", "no still registered"
    path = Path(pkg.root) / record.file
    if not path.is_file():
        return "STALE_FILE", f"{record.file} is not on disk"
    if sha256_file(path) != record.sha256:
        return "STALE_FILE", f"{record.file} changed after it was registered"
    if prompt is None:
        prompt = still_prompts(pkg).get(gid, "")
    if prompt_hash(prompt) != record.prompt_sha256:
        return "STALE_PROMPT", "the still prompt changed after this image was made: make and register a new still"
    if not record.approved_by.strip():
        return "UNAPPROVED", "registered, waiting for a reviewer"
    return "APPROVED", f"approved by {record.approved_by}"


def list_stills(pkg: Any) -> list[dict[str, Any]]:
    prompts = still_prompts(pkg)
    heads = set(chain_heads(pkg))
    rows = []
    for gid, text in prompts.items():
        state, reason = state_of(pkg, gid, text)
        rows.append({"generation_id": gid, "needs_still": gid in heads, "state": state, "reason": reason,
                     "prompt_file": f"stills/start_{gid}.txt", "prompt_sha256": prompt_hash(text),
                     "file": (_records(pkg).get(gid).file if gid in _records(pkg) else "")})
    return rows


def approved_still_path(pkg: Any, gid: str, prompt: str | None = None) -> Path | None:
    state, _ = state_of(pkg, gid, prompt)
    return Path(pkg.root) / _records(pkg)[gid].file if state == "APPROVED" else None


def approved_stills(pkg: Any) -> dict[str, Path]:
    if not _records(pkg):
        return {}
    prompts = still_prompts(pkg)
    return {gid: path for gid in _records(pkg) if gid in prompts
            and (path := approved_still_path(pkg, gid, prompts[gid])) is not None}


# --------------------------------------------------------------------------- writes

def _write_record(root: Path, gid: str, record: StillRecord) -> None:
    path = Path(root) / PREPROD_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.setdefault("stills", {})[gid] = record.model_dump(mode="json")
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extension(image: Path) -> str:
    head = image.read_bytes()[:16]
    for magic, ext in _FORMATS:
        if head.startswith(magic):
            return ext
    raise ValueError(f"{image.name}: not a PNG or JPEG image")


def register_still(pkg: Any, gid: str, image: Path, *, source: str = "", credits: float = 0.0,
                   now: str | None = None) -> dict[str, Any]:
    """Copy `image` under media/stills/ and record it for `gid`. A new registration is never approved."""
    prompts = still_prompts(pkg)
    if gid not in prompts:
        raise ValueError(f"unknown generation {gid!r}")
    image = Path(image)
    if not image.is_file():
        raise ValueError(f"image not found: {image}")
    if credits < 0:
        raise ValueError("credits cannot be negative")
    ext = _extension(image)
    root = Path(pkg.root)
    target = stills_dir(root) / f"start_{gid}{ext}"
    sha = sha256_file(image)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = _records(pkg).get(gid)
    if target.is_file() and sha256_file(target) != sha:  # the replaced image is evidence: keep it
        history = target.parent / "history"
        history.mkdir(exist_ok=True)
        shutil.move(str(target), str(history / f"start_{gid}.{sha256_file(target)[:12]}{ext}"))
    if not target.is_file():
        shutil.copyfile(image, target)
    record = StillRecord(file=target.relative_to(root).as_posix(), sha256=sha, prompt_sha256=prompt_hash(prompts[gid]),
                         source=source.strip(), credits=credits, registered_at=now or _now())
    if previous is not None and previous.sha256 == sha and previous.prompt_sha256 == record.prompt_sha256:
        record = record.model_copy(update={"approved_by": previous.approved_by, "approved_at": previous.approved_at})
    _write_record(root, gid, record)
    return {"generation_id": gid, "file": record.file, "sha256": sha, "prompt_sha256": record.prompt_sha256,
            "approved": bool(record.approved_by)}


def approve_still(pkg: Any, gid: str, by: str, *, now: str | None = None) -> dict[str, Any]:
    """Mark the registered still approved by a named reviewer; refuses a missing or stale still."""
    if not by.strip():
        raise ValueError("an approval needs the reviewer's name")
    state, reason = state_of(pkg, gid)
    if state == "MISSING":
        raise ValueError(f"{gid}: {reason}; register one first")
    if state in ("STALE_PROMPT", "STALE_FILE"):
        raise ValueError(f"{gid}: cannot approve, {reason}")
    record = _records(pkg)[gid].model_copy(update={"approved_by": by.strip(), "approved_at": now or _now()})
    _write_record(Path(pkg.root), gid, record)
    return {"generation_id": gid, "approved_by": record.approved_by, "file": record.file}
