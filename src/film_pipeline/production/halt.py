"""Machine-wide production halt (Owner rule).

When ANY Flow account shows an account warning ("unusual activity", captcha/verify),
ALL sending stops on this machine. There is no automatic clear: only an explicit
``clear_halt`` with an accountable ``by`` id removes the halt.

The halt file is machine-wide on purpose: several worktrees/films share the same
Flow accounts. Location: ``$AFP_HALT_FILE`` else
``($AFP_STATE_DIR or ~/.afp)/production_halt.json``; history is appended to
``production_halt_history.jsonl`` next to it.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

HALT_FILENAME = "production_halt.json"
HISTORY_FILENAME = "production_halt_history.jsonl"
UNREADABLE_REASON = "unreadable halt file"
_BY_RE = re.compile(r"^(human|agent):[A-Za-z0-9_.\-]+$")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def state_dir() -> Path:
    """The machine-wide production state directory: ``$AFP_STATE_DIR`` else ``~/.afp`` (halt, account lease pool)."""
    return Path(os.environ.get("AFP_STATE_DIR") or (Path.home() / ".afp"))


def halt_path() -> Path:
    override = os.environ.get("AFP_HALT_FILE")
    if override:
        return Path(override)
    return state_dir() / HALT_FILENAME


def history_path() -> Path:
    return halt_path().parent / HISTORY_FILENAME


def _append_history(entry: dict[str, Any]) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_halt() -> dict[str, Any] | None:
    """Return the active halt record, or None. Unreadable file => halted (fail closed)."""
    path = halt_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("halt file is not a JSON object")
        return data
    except (OSError, ValueError):
        return {
            "halted": True,
            "reason": UNREADABLE_REASON,
            "source": "halt",
            "set_at": "",
            "events": [],
            "path": str(path),
        }


def is_halted() -> bool:
    return read_halt() is not None


def halt_reason() -> str:
    halt = read_halt()
    return str((halt or {}).get("reason") or "") if halt else ""


def set_halt(
    reason: str,
    *,
    source: str,
    account: str = "",
    film_id: str = "",
    take_id: str = "",
    evidence: str = "",
) -> dict[str, Any]:
    """Set the halt; if already halted keep the first halt and append this event."""
    event = {
        "at": _now(),
        "reason": str(reason or "").strip() or "account warning",
        "source": source,
        "account": account,
        "film_id": film_id,
        "take_id": take_id,
        "evidence": evidence,
    }
    current = read_halt()
    if current is not None and current.get("reason") != UNREADABLE_REASON:
        record = dict(current)
        events = list(record.get("events") or [])
        events.append(event)
        record["events"] = events
    else:
        record = {
            "halted": True,
            "reason": event["reason"],
            "source": source,
            "account": account,
            "film_id": film_id,
            "take_id": take_id,
            "evidence": evidence,
            "set_at": event["at"],
            "events": [event],
        }
    _atomic_write(halt_path(), record)
    _append_history({"action": "set", "at": event["at"], "event": event})
    return record


def clear_halt(by: str, reason: str) -> dict[str, Any]:
    """Explicitly clear the halt. ``by`` must be ``human:<id>`` or ``agent:<id>``."""
    if not isinstance(by, str) or not _BY_RE.match(by):
        raise ValueError("clear_halt: 'by' must match ^(human|agent):[A-Za-z0-9_.-]+$")
    if not isinstance(reason, str) or len(reason.strip()) < 3:
        raise ValueError("clear_halt: reason must be at least 3 characters")
    path = halt_path()
    current = read_halt()
    if current is None:
        raise RuntimeError("clear_halt: production is not halted")
    entry = {
        "action": "clear",
        "at": _now(),
        "by": by,
        "reason": reason.strip(),
        "cleared_halt": current,
    }
    _append_history(entry)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return entry
