"""Picture lock and invalidation (categories 105-106 locked picture, 158 change control; Gate 5).

A picture lock freezes the cut: ``<film>/lock/picture.lock.json`` records who locked it, the hash of the EDL and, per
event, a fingerprint of the event (its EDL entry, its tags, the take's bytes and whether the take is still accepted).
Every lock is also kept as ``lock/history/<edl_sha256>.json`` and never rewritten, so an older lock can still be
compared with the cut as it is now.

Downstream work (subtitles, mix, colour, titles, master QC, packaging ...) lives as items of `06_post.json` and
`07_delivery.json`: a top-level key whose value is an object. An item says which cut it was built from with
``"locked_against": "<edl_sha256>"`` and, if it only covers part of the film, ``"events": ["<event_id>", ...]``.
``dirty_items`` compares the cut each item was built from with the cut now:

* the events at or after the first difference are affected (a change moves everything after it on the clock); a change
  to the title/end frame affects every event;
* an item with no ``events`` covers the whole film and is dirty on any change; an item with ``events`` is dirty when one
  of them is affected;
* an item with no stamp, or a stamp that matches no recorded lock, is dirty because nothing proves what it was built on.

Locking needs a valid EDL, every take accepted by a human with unchanged bytes, and no BLOCK at any cut; a relock
after a change records what it supersedes. Gate 5 passes only for a fresh lock.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from film_pipeline.production.edit import cut_continuity, edit_problems

LOCK_DIR = "lock"
LOCK_FILE = "picture.lock.json"
ITEM_STAGES = ("post", "delivery")


def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def lock_dir(root: Path) -> Path:
    return Path(root) / LOCK_DIR


def snapshot(pkg: Any) -> dict[str, Any]:
    """The cut as it is now: EDL hash, a hash of the frame (title/end cards and their lengths) and one fingerprint per
    event, in order."""
    from film_pipeline.production.takes import load_log
    section = pkg.typed.get("edit")
    if section is None:
        raise ValueError("there is no valid 05_edit.json to lock")
    log = {t.take_id: t for t in load_log(Path(pkg.root), pkg.header.film_id).takes}
    tags: dict[str, list[Any]] = {}
    for tag in section.tags:
        tags.setdefault(tag.event_id, []).append(tag.model_dump(mode="json"))
    events = []
    for event in section.events:
        entry = log.get(event.take_id) if event.kind == "TAKE" else None
        source = {"sha256": entry.output_sha256, "accepted": entry.status == "ACCEPTED"} if entry else (
            {"missing": True} if event.kind == "TAKE" else {})
        events.append({"event_id": event.event_id,
                       "sha256": _hash({"event": event.model_dump(mode="json"), "tags": tags.get(event.event_id, []),
                                        "source": source})})
    frame = {k: section.model_dump(mode="json")[k] for k in ("title", "end", "title_s", "end_s")}
    return {"edl_sha256": _hash(section.model_dump(mode="json")), "frame_sha256": _hash(frame), "events": events,
            "sources": {e.take_id: log[e.take_id].output_sha256 for e in section.events
                        if e.kind == "TAKE" and e.take_id in log}}


def affected_events(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Event ids (old and new) whose place on the clock or content differs between two snapshots, in order."""
    if old["frame_sha256"] != new["frame_sha256"]:
        return [e["event_id"] for e in new["events"]] + [e["event_id"] for e in old["events"]
                                                         if e["event_id"] not in {x["event_id"] for x in new["events"]}]
    a, b = old["events"], new["events"]
    first = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), None)
    if first is None:
        if len(a) == len(b):
            return []
        first = min(len(a), len(b))
    out: list[str] = []
    for e in b[first:] + a[first:]:
        if e["event_id"] not in out:
            out.append(e["event_id"])
    return out


def load_lock(root: Path) -> dict[str, Any] | None:
    path = lock_dir(root) / LOCK_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_recorded(root: Path, edl_sha256: str) -> dict[str, Any] | None:
    path = lock_dir(root) / "history" / f"{edl_sha256}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def lock_picture(pkg: Any, locked_by: str, reason: str = "", clips_dir: Path | None = None) -> dict[str, Any]:
    """Freeze the cut. Raises ValueError listing what stops it: an invalid EDL, a take nobody accepted, changed bytes,
    a BLOCK finding at a cut."""
    if not locked_by.strip():
        raise ValueError("a picture lock names the person who locked it (locked_by)")
    section = pkg.typed.get("edit")
    if section is None:
        raise ValueError("there is no valid 05_edit.json to lock")
    if not section.events:
        raise ValueError("an empty cut cannot be locked")
    problems, durations = edit_problems(pkg, section, clips_dir=clips_dir, require_accepted=True)
    blocks = [f"{p['code']} {p['event_id']}: {p['detail']}" for p in problems if p["severity"] == "BLOCK"]
    blocks += [f"{i['code']} {'/'.join(i['between'])}: {i['detail']}"
               for i in cut_continuity(pkg, section, durations)["issues"] if i["severity"] == "BLOCK"]
    if blocks:
        raise ValueError("cannot lock: " + "; ".join(blocks))
    root = Path(pkg.root)
    snap = snapshot(pkg)
    previous = load_lock(root)
    record = {"film_id": pkg.header.film_id, "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "locked_by": locked_by.strip(), "reason": reason, **snap,
              "supersedes": previous["edl_sha256"] if previous and previous["edl_sha256"] != snap["edl_sha256"] else "",
              "changed_events": affected_events(previous, snap) if previous else []}
    history = lock_dir(root) / "history"
    history.mkdir(parents=True, exist_ok=True)
    (history / f"{snap['edl_sha256']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    (lock_dir(root) / LOCK_FILE).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def lock_status(pkg: Any) -> dict[str, Any]:
    root = Path(pkg.root)
    lock = load_lock(root)
    if lock is None:
        return {"locked": False, "fresh": False, "changed_events": [], "reason": "no picture lock"}
    try:
        now = snapshot(pkg)
    except ValueError as exc:
        return {"locked": True, "fresh": False, "lock_edl_sha256": lock["edl_sha256"], "changed_events": [],
                "reason": str(exc)}
    changed = affected_events(lock, now)
    fresh = lock["edl_sha256"] == now["edl_sha256"] and not changed and lock["sources"] == now["sources"]
    return {"locked": True, "fresh": fresh, "locked_by": lock["locked_by"], "locked_at": lock["locked_at"],
            "lock_edl_sha256": lock["edl_sha256"], "current_edl_sha256": now["edl_sha256"], "changed_events": changed,
            "reason": "" if fresh else "the cut changed after the lock"}


def items(pkg: Any) -> list[tuple[str, str, dict[str, Any]]]:
    out = []
    for stage in ITEM_STAGES:
        for name, value in (pkg.stages.get(stage) or {}).items():
            if isinstance(value, dict):
                out.append((stage, name, value))
    return out


def dirty_items(pkg: Any) -> dict[str, Any]:
    """Which post/delivery items no longer match the cut. ``dirty`` and ``clean`` list {stage, item, reason}."""
    root = Path(pkg.root)
    try:
        now = snapshot(pkg)
    except ValueError as exc:
        return {"dirty": [{"stage": s, "item": n, "reason": str(exc)} for s, n, _ in items(pkg)], "clean": []}
    dirty, clean = [], []
    for stage, name, item in items(pkg):
        ref = {"stage": stage, "item": name}
        stamp = item.get("locked_against") or ""
        if not stamp:
            dirty.append({**ref, "reason": "UNSTAMPED: no locked_against, nothing proves which cut it was built from"})
            continue
        built_on = load_recorded(root, stamp)
        if built_on is None:
            dirty.append({**ref, "reason": f"UNKNOWN_LOCK: {stamp[:12]} matches no recorded picture lock"})
            continue
        affected = affected_events(built_on, now)
        covers = item.get("events")
        hit = affected if not covers else [e for e in affected if e in set(covers)]
        if hit:
            dirty.append({**ref, "reason": f"CUT_CHANGED: {', '.join(hit[:6])}{' ...' if len(hit) > 6 else ''}",
                          "events": hit})
        else:
            clean.append({**ref, "reason": "built on an equivalent cut" if affected else "built on this cut"})
    return {"dirty": dirty, "clean": clean}


def picture_lock_issues(pkg: Any) -> list[str]:
    """Gate 5 (drama): a fresh picture lock."""
    status = lock_status(pkg)
    if not status["locked"]:
        return ["picture is not locked (film.py lock --lock --by NAME)"]
    if not status["fresh"]:
        changed = status.get("changed_events") or []
        detail = status.get("reason") or "the cut changed after the lock"
        return [f"{detail}{(': ' + ', '.join(changed[:6])) if changed else ''}; relock after review"]
    return []
