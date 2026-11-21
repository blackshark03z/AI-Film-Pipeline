"""Machine-wide production halt (Owner rule).

When ANY Flow account shows an account warning ("unusual activity", captcha/verify),
ALL sending stops on this machine. There is no automatic clear: only an explicit
``clear_halt`` with an accountable ``by`` id removes the halt.

The halt file is machine-wide on purpose: several worktrees/films share the same
Flow accounts. Location: ``$AFP_HALT_FILE`` else
``($AFP_STATE_DIR or ~/.afp)/production_halt.json``; history is appended to
``production_halt_history.jsonl`` next to it.

Setting or clearing the halt takes the broker lock (STUDIO_ARCHITECTURE §6): a ``BEGIN IMMEDIATE`` on the broker
database in the state dir (``lease_pool.sqlite3``, when it exists), so no admission and no pre-Enter check (both
read the halt inside that same lock) can interleave with it. The broker passes ``lock=False`` when it sets the halt
inside its own transaction.

Every read-modify-write of the halt file (set and clear, whichever broker database the caller locked) also takes the
halt file's own lock (``production_halt.json.lock``, held only for that file update). It is the innermost lock:
taken after a broker lock, never held while taking one, so set and clear through different brokers (``--db``)
serialize and a clear never erases a warning written after it read the file.

The same halt-file lock is the one serialization boundary of every halt signal (lane contract §11): the broker's
admission and pre-Enter check take it inside their transaction, read the AFP halt, the Muse halt file
(``$MUSE_HALT_FILE``) and the allocator claim (``allocator_owner.json``) under it, and hold it until their COMMIT.
Muse publishes its halt holding only this lock (never a broker transaction), so a check either commits before the
publication or sees the halt. Lock order everywhere: broker transaction -> halt-file lock.

``stop_signals`` is the one reader of every stop signal: the AFP halt, the Muse halt and the lock-free pending markers
a sender writes when it cannot publish its halt (``halt_pending/*.json``). ``clear_halt(include_pending=True)``
publishes the pending markers into the halt history before it removes them and clears.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
from contextlib import contextmanager
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


BROKER_DB_FILENAME = "lease_pool.sqlite3"


@contextmanager
def broker_lock(enabled: bool = True, db: Path | str | None = None):
    """The broker's leaf lock (held for one atomic file write): ``db``, the broker database the caller admits
    against, default the machine broker (``agentic.broker.default_db_path()``)."""
    db = Path(db) if db else state_dir() / BROKER_DB_FILENAME
    if not enabled or not db.is_file():
        yield
        return
    conn = sqlite3.connect(db, timeout=30.0, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        finally:
            if conn.in_transaction:
                conn.execute("COMMIT")
    finally:
        conn.close()


HALT_LOCK_TIMEOUT_S = 60.0


def halt_lock_path() -> Path:
    """``<halt file>.lock``: the halt-file lock (exclusive lock on byte 0: ``msvcrt.locking(LK_NBLCK, 1)`` on Windows,
    ``fcntl.flock(LOCK_EX)`` elsewhere). It guards the AFP halt, the Muse halt file and the allocator claim."""
    path = halt_path()
    return path.with_name(path.name + ".lock")


@contextmanager
def _halt_file_lock(timeout_s: float = HALT_LOCK_TIMEOUT_S):
    """Exclusive OS lock on ``<halt file>.lock`` (the innermost lock: taken inside a broker transaction, never held
    while taking one). Admission and the pre-Enter check hold it from their halt/owner read to their COMMIT; a halt
    set or clear holds it for its file update; Muse holds it, alone, to publish its halt."""
    lock = halt_lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        if lock.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"halt file lock {lock} busy for {timeout_s:g}s") from exc
                time.sleep(0.02)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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


# ---- the Muse halt (lane contract §11): one halt signal, one serialization boundary ----------------------------------
MUSE_HALT_ENV = "MUSE_HALT_FILE"


def muse_halt_path() -> Path | None:
    """The Muse halt file the broker honours: ``$MUSE_HALT_FILE`` (unset: Muse has no halt on this machine)."""
    raw = (os.environ.get(MUSE_HALT_ENV) or "").strip()
    return Path(raw) if raw else None


def read_muse_halt() -> dict[str, Any] | None:
    """The Muse halt record, or None (not configured, or no file). A file that exists is a halt whatever it holds;
    unreadable => halted (fail closed, as Muse's own ``send_halt.load_halt``). Muse writes it under the halt-file lock
    (``halt_lock_path``), so the broker reads it inside its admission and pre-Enter transactions."""
    path = muse_halt_path()
    if path is None:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return {"reason": "unreadable Muse halt file", "path": str(path)}
    try:
        data = json.loads(raw)
    except ValueError:
        return {"reason": "unreadable Muse halt file", "path": str(path)}
    return {**data, "path": str(path)} if isinstance(data, dict) else {"reason": "BLOCKED", "path": str(path)}


# ---- the allocator ownership claim (lane contract §11, architecture §6; P1 scope freeze) -----------------------------
OWNER_FILENAME = "allocator_owner.json"
OWNER = "afp-broker"   # P1: the only allocator; the Muse standalone transfer protocol is M3 backlog


def owner_path() -> Path:
    """``<state dir>/allocator_owner.json``: which allocator owns this machine's accounts."""
    return state_dir() / OWNER_FILENAME


def read_owner() -> dict[str, Any]:
    """The allocator claim: ``owner``, ``claimed_at``, ``claimed_by`` and ``problem`` ('' when the file is valid;
    ``absent`` when there is no file; else why it cannot be trusted). ``owner`` is whatever a valid file names (the
    broker allocates only when it is ``afp-broker``). Read it under the halt-file lock when a decision depends on it."""
    path = owner_path()
    empty = {"owner": "", "claimed_at": "", "claimed_by": "", "db": ""}
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {**empty, "problem": "absent"}
    except (OSError, UnicodeDecodeError) as exc:
        return {**empty, "problem": f"unreadable ({type(exc).__name__})"}
    try:
        body = json.loads(raw)
    except ValueError:
        return {**empty, "problem": "not valid JSON"}
    if not isinstance(body, dict):
        return {**empty, "problem": "not a JSON object"}
    owner = body.get("owner")
    if not isinstance(owner, str) or not owner.strip():
        return {**empty, "problem": f"names no owner ({owner!r})"}
    return {"owner": owner, "claimed_at": str(body.get("claimed_at") or ""),
            "claimed_by": str(body.get("claimed_by") or ""), "db": str(body.get("db") or ""), "problem": ""}


def write_owner_locked(claimed_by: str, db: str = "") -> dict[str, Any]:
    """Write the ``afp-broker`` claim atomically, recording the broker database (``db``) that made it. Only ``Broker.allocator_claim`` calls it, inside its broker
    transaction and holding the halt-file lock."""
    record = {"owner": OWNER, "claimed_at": _now(), "claimed_by": claimed_by, "db": db}
    _atomic_write(owner_path(), record)
    return record


def remove_owner_locked() -> None:
    """Remove the claim. Only ``Broker.allocator_release`` calls it, inside its broker transaction and holding the
    halt-file lock."""
    owner_path().unlink()


halt_file_lock = _halt_file_lock   # the public name (broker_api.halt_file_lock)


# ---- pending stops (lane contract §11): lock-free latches a sender writes when it cannot publish its halt ------------
PENDING_DIRNAME = "halt_pending"


def pending_dir() -> Path:
    """``<state dir>/halt_pending/``: one ``<lane_id>-<incarnation_id>.json`` per sender that could not take the
    halt-file lock to publish its halt (create-exclusive, lock-free)."""
    return state_dir() / PENDING_DIRNAME


def _dir_entries(path: Path, pattern: str) -> tuple[str, list[Path]]:
    """``(problem, entries)`` of ``path`` matching ``pattern``: a missing dir has none; a dir that cannot be listed (or
    a non-directory in its place) is a problem (fail closed)."""
    try:
        entries = sorted(p for p in path.iterdir() if p.match(pattern))
    except FileNotFoundError:
        return "", []
    except OSError as exc:   # NotADirectoryError, PermissionError, ...
        return f"{path} cannot be listed ({type(exc).__name__})", []
    return "", entries


def pending_markers() -> tuple[str, list[Path]]:
    """``(problem, marker files)``: every ``*.json`` in ``halt_pending/``."""
    return _dir_entries(pending_dir(), "*.json")


# ---- every stop signal, read in one place under the halt-file lock -----------------------------------------------------
def stop_signals() -> tuple[str, str]:
    """``(code, reason)`` of the first stop signal present (``("", "")``: none). Every pre-Enter gate reads them all
    under the halt-file lock and refuses on any; an unreadable one refuses too (fail closed):

    1. the AFP halt and 2. the Muse halt (``$MUSE_HALT_FILE``) -> ``PRODUCTION_HALT``;
    3. a ``halt_pending/*.json`` marker (or that dir unreadable) -> ``HALT_PENDING``."""
    afp = read_halt()
    if afp is not None:
        return "PRODUCTION_HALT", f"production halted: {afp.get('reason', '')}"
    muse = read_muse_halt()
    if muse is not None:
        return "PRODUCTION_HALT", f"production halted by the Muse halt file {muse.get('path', '')}: " \
                                  f"{muse.get('reason', '')}"
    problem, entries = pending_markers()
    if problem:
        return "HALT_PENDING", f"the pending halt marker directory {problem}: refused until it is readable"
    if entries:
        return "HALT_PENDING", (f"{len(entries)} pending halt marker(s) not yet published "
                                f"({', '.join(p.name for p in entries)}): afp-film halt clear --include-pending "
                                f"after review")
    return "", ""


def _marker_id(path: Path) -> str:
    return path.name[:-len(path.suffix)] if path.suffix else path.name


def set_halt(
    reason: str,
    *,
    source: str,
    account: str = "",
    film_id: str = "",
    take_id: str = "",
    evidence: str = "",
    lock: bool = True,
    db: Path | str | None = None,
) -> dict[str, Any]:
    """Set the halt; if already halted keep the first halt and append this event. ``lock`` takes the broker lock of
    ``db`` (default: the machine broker; False only inside a broker transaction that already holds it)."""
    with broker_lock(lock, db):
        return _set_halt(reason, source=source, account=account, film_id=film_id, take_id=take_id, evidence=evidence)


def _set_halt(reason: str, *, source: str, account: str, film_id: str, take_id: str, evidence: str) -> dict[str, Any]:
    with _halt_file_lock():
        return _set_halt_locked(reason, source=source, account=account, film_id=film_id, take_id=take_id,
                                evidence=evidence)


def _set_halt_locked(reason: str, *, source: str, account: str, film_id: str, take_id: str,
                     evidence: str) -> dict[str, Any]:
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


def clear_halt(by: str, reason: str, *, include_pending: bool = False) -> dict[str, Any]:
    """Explicitly clear the halt. ``by`` must be ``human:<id>`` or ``agent:<id>``.

    Under the broker transaction, then the halt-file lock. Refused (RuntimeError) while a ``halt_pending/`` marker
    exists, or the dir cannot be listed, unless ``include_pending``: then each marker read here is first PUBLISHED into
    the halt and its history (``set_halt`` from it, the first halt kept), exactly those files are removed, and only
    then is the halt cleared. A marker written after this read stays (and keeps every gate refusing). Nothing is ever
    removed unpublished."""
    if not isinstance(by, str) or not _BY_RE.match(by):
        raise ValueError("clear_halt: 'by' must match ^(human|agent):[A-Za-z0-9_.-]+$")
    if not isinstance(reason, str) or len(reason.strip()) < 3:
        raise ValueError("clear_halt: reason must be at least 3 characters")
    with broker_lock():
        return _clear_halt(by, reason, include_pending=include_pending)


def _clear_halt(by: str, reason: str, *, include_pending: bool = False) -> dict[str, Any]:
    with _halt_file_lock():
        published = _publish_pending_locked(by, include_pending)
        entry = _clear_halt_locked(by, reason)
        if published:
            entry["published_pending"] = published
        return entry


def _publish_pending_locked(by: str, include_pending: bool) -> list[str]:
    """Publish then remove the pending markers present now (halt-file lock held). Returns the ids published
    (``halt_pending/<id>``)."""
    problem, markers = pending_markers()
    if problem:
        raise RuntimeError(f"clear_halt: {problem}; nothing cleared")
    if not markers:
        return []
    if not include_pending:
        raise RuntimeError(f"clear_halt: {len(markers)} pending halt marker(s) exist; review them and use "
                           f"--include-pending (they are published, then removed)")
    published: list[tuple[Path, str]] = []
    for path in markers:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            body = body if isinstance(body, dict) else {}
            readable = True
        except (OSError, ValueError):
            body, readable = {}, False
        mid = _marker_id(path)
        why = str(body.get("reason") or "") if readable else "unreadable pending marker"
        _set_halt_locked(f"pending halt {mid}: {why}".strip()[:300], source=f"halt_pending:{mid}",
                         account=str(body.get("account_id") or "")[:120], film_id="", take_id="",
                         evidence=f"HALT_PENDING provider={str(body.get('provider') or '')[:40]} "
                                  f"ts={str(body.get('ts') or '')[:40]} published_by={by}")
        published.append((path, f"{PENDING_DIRNAME}/{mid}"))
    for path, _ in published:   # every one is in the halt history now; remove exactly these
        path.unlink(missing_ok=True)
    return [pid for _, pid in published]


def _clear_halt_locked(by: str, reason: str) -> dict[str, Any]:
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
