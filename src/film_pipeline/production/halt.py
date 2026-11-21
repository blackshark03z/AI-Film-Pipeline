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

``stop_signals`` is the one reader of every stop signal: the AFP halt, the Muse halt, the lock-free pending stops a
sender latches when it cannot publish (``halt_pending/*.json``, ``halt_pending_unwritten/<incident>.flag``) and the
machine-wide send-stop event (``Local\\FilmStudio-SendStop``, Windows). ``clear_halt(include_pending=True)`` publishes
the pending stops into the halt history before it removes them and clears.
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


# ---- the allocator ownership claim (lane contract §11, architecture §6) ---------------------------------------------
OWNER_FILENAME = "allocator_owner.json"
OWNERS = ("afp-broker", "muse-standalone")


def owner_path() -> Path:
    """``<state dir>/allocator_owner.json``: which allocator owns this machine's accounts."""
    return state_dir() / OWNER_FILENAME


def read_owner() -> dict[str, Any]:
    """The allocator claim: ``owner`` (one of ``OWNERS``), ``claim_epoch`` (int >= 0), ``claimed_at``, ``claimed_by``
    and ``problem`` ('' when valid; ``absent`` when there is no file; else why it cannot be trusted). Read it under
    the halt-file lock when a decision depends on it."""
    path = owner_path()
    empty = {"owner": "", "claim_epoch": None, "claimed_at": "", "claimed_by": ""}
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {**empty, "problem": "absent"}
    except OSError as exc:
        return {**empty, "problem": f"unreadable ({type(exc).__name__})"}
    try:
        body = json.loads(raw)
    except ValueError:
        return {**empty, "problem": "not valid JSON"}
    if not isinstance(body, dict):
        return {**empty, "problem": "not a JSON object"}
    owner, epoch = body.get("owner"), body.get("claim_epoch")
    if owner not in OWNERS:
        return {**empty, "problem": f"unknown owner {owner!r}"}
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        return {**empty, "problem": f"invalid claim_epoch {epoch!r}"}
    return {"owner": owner, "claim_epoch": epoch, "claimed_at": str(body.get("claimed_at") or ""),
            "claimed_by": str(body.get("claimed_by") or ""), "problem": ""}


def write_owner_locked(owner: str, claim_epoch: int, claimed_by: str) -> dict[str, Any]:
    """Replace the claim atomically. Only ``Broker.allocator_transfer`` calls it, inside its broker transaction and
    holding the halt-file lock."""
    record = {"owner": owner, "claim_epoch": int(claim_epoch), "claimed_at": _now(), "claimed_by": claimed_by}
    _atomic_write(owner_path(), record)
    return record


halt_file_lock = _halt_file_lock   # the public name (broker_api.halt_file_lock)


# ---- pending stops (lane contract §11): lock-free latches a sender writes when it cannot publish its halt ------------
PENDING_DIRNAME = "halt_pending"
UNWRITTEN_DIRNAME = "halt_pending_unwritten"
LEGACY_UNWRITTEN_FLAG = "halt_pending_unwritten.flag"


def pending_dir() -> Path:
    """``<state dir>/halt_pending/``: one ``<lane_id>-<incarnation_id>.json`` per sender that could not take the
    halt-file lock to publish its halt (create-exclusive, lock-free)."""
    return state_dir() / PENDING_DIRNAME


def unwritten_dir() -> Path:
    """``<state dir>/halt_pending_unwritten/``: one ``<incident_id>.flag`` per sender that could not even write its
    pending marker."""
    return state_dir() / UNWRITTEN_DIRNAME


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


def unwritten_flags() -> tuple[str, list[Path]]:
    """``(problem, flag files)``: every entry of ``halt_pending_unwritten/`` (any name), plus the pre-item-16 single
    ``halt_pending_unwritten.flag`` when it is still there."""
    problem, flags = _dir_entries(unwritten_dir(), "*")
    legacy = state_dir() / LEGACY_UNWRITTEN_FLAG
    try:
        if legacy.exists():
            flags.append(legacy)
    except OSError as exc:
        problem = problem or f"{legacy} cannot be read ({type(exc).__name__})"
    return problem, flags


# ---- the machine-wide send-stop event (lane contract §11, lane review v6 #1) -----------------------------------------
SEND_STOP_EVENT = "Local\\FilmStudio-SendStop"
SEND_STOP_ENV = "AFP_SEND_STOP_EVENT"   # tests only: a private event name, so a test never stops this machine's lanes
_SYNCHRONIZE, _EVENT_MODIFY_STATE = 0x00100000, 0x0002
_ERROR_FILE_NOT_FOUND, _WAIT_OBJECT_0, _WAIT_TIMEOUT = 2, 0x0, 0x102


def send_stop_event_name() -> str:
    """The named kernel event every pre-Enter gate reads: ``Local\\FilmStudio-SendStop`` (per Windows logon session)."""
    return (os.environ.get(SEND_STOP_ENV) or "").strip() or SEND_STOP_EVENT


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    k32.OpenEventW.restype = wintypes.HANDLE
    k32.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    k32.CreateEventW.restype = wintypes.HANDLE
    k32.SetEvent.argtypes = (wintypes.HANDLE,)
    k32.SetEvent.restype = wintypes.BOOL
    k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    k32.CloseHandle.restype = wintypes.BOOL
    return ctypes, k32


def send_stop_state() -> str:
    """``""`` (absent: no such event, or it exists unsignalled; always on non-Windows), ``"SET"`` (exists and
    signalled: refuse) or ``"unknown (...)"`` (any other query error: refuse). Opens the event for SYNCHRONIZE only and
    never changes it."""
    if os.name != "nt":
        return ""
    try:
        ctypes, k32 = _kernel32()
    except (OSError, AttributeError) as exc:
        return f"unknown ({type(exc).__name__})"
    handle = k32.OpenEventW(_SYNCHRONIZE, False, send_stop_event_name())
    if not handle:
        err = ctypes.get_last_error()
        return "" if err == _ERROR_FILE_NOT_FOUND else f"unknown (OpenEventW error {err})"
    try:
        waited = k32.WaitForSingleObject(handle, 0)
        if waited == _WAIT_OBJECT_0:
            return "SET"
        if waited == _WAIT_TIMEOUT:
            return ""
        return f"unknown (WaitForSingleObject {waited:#x}, error {ctypes.get_last_error()})"
    finally:
        k32.CloseHandle(handle)


def raise_send_stop() -> int:
    """A sender's first step on any block: create (or open) the send-stop event, manual-reset, and set it. Returns the
    handle, which the caller keeps open until a durable stop (the halt, a pending marker or an unwritten flag) exists:
    the event dies with its last handle. Needs no disk. Non-Windows: 0 (no event)."""
    if os.name != "nt":
        return 0
    ctypes, k32 = _kernel32()
    handle = k32.CreateEventW(None, True, True, send_stop_event_name())
    if not handle:
        raise OSError(f"CreateEventW failed (error {ctypes.get_last_error()})")
    if not k32.SetEvent(handle):
        err = ctypes.get_last_error()
        k32.CloseHandle(handle)
        raise OSError(f"SetEvent failed (error {err})")
    return int(handle)


def close_send_stop(handle: int) -> None:
    """Close a handle ``raise_send_stop`` returned (the event ends with its last handle)."""
    if os.name == "nt" and handle:
        _kernel32()[1].CloseHandle(handle)


# ---- every stop signal, read in one place under the halt-file lock -----------------------------------------------------
def stop_signals() -> tuple[str, str]:
    """``(code, reason)`` of the first stop signal present (``("", "")``: none). Every pre-Enter gate reads them all
    under the halt-file lock and refuses on any; an unreadable one refuses too (fail closed):

    1. the AFP halt and 2. the Muse halt (``$MUSE_HALT_FILE``) -> ``PRODUCTION_HALT``;
    3. a ``halt_pending/*.json`` marker and 4. a ``halt_pending_unwritten/`` flag -> ``HALT_PENDING``;
    5. the send-stop event set -> ``SEND_STOP``."""
    afp = read_halt()
    if afp is not None:
        return "PRODUCTION_HALT", f"production halted: {afp.get('reason', '')}"
    muse = read_muse_halt()
    if muse is not None:
        return "PRODUCTION_HALT", f"production halted by the Muse halt file {muse.get('path', '')}: " \
                                  f"{muse.get('reason', '')}"
    for what, (problem, entries) in (("pending halt marker", pending_markers()),
                                     ("pending halt incident (marker unwritten)", unwritten_flags())):
        if problem:
            return "HALT_PENDING", f"a {what} directory {problem}: refused until it is readable"
        if entries:
            return "HALT_PENDING", (f"{len(entries)} {what}(s) not yet published ({', '.join(p.name for p in entries)}"
                                    f"): afp-film halt clear --include-pending after review")
    state = send_stop_state()
    if state:
        return "SEND_STOP", f"the send-stop event {send_stop_event_name()} is {state}: a sender hit a block"
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

    Under the broker transaction, then the halt-file lock. Refused (RuntimeError) while a ``halt_pending/`` marker or a
    ``halt_pending_unwritten/`` flag exists, or either dir cannot be listed, unless ``include_pending``: then each
    marker and flag read here is first PUBLISHED into the halt and its history (``set_halt`` from it, the first halt
    kept), exactly those files are removed, and only then is the halt cleared. A marker or flag written after this
    read stays (and keeps every gate refusing). Nothing is ever removed unpublished."""
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
    """Publish then remove the pending markers and unwritten flags present now (halt-file lock held). Returns the ids
    published (``halt_pending/<id>`` and ``halt_pending_unwritten/<id>``)."""
    m_problem, markers = pending_markers()
    f_problem, flags = unwritten_flags()
    if m_problem or f_problem:
        raise RuntimeError(f"clear_halt: {m_problem or f_problem}; nothing cleared")
    if not (markers or flags):
        return []
    if not include_pending:
        raise RuntimeError(f"clear_halt: {len(markers)} pending halt marker(s) and {len(flags)} unwritten-marker "
                           f"flag(s) exist; review them and use --include-pending (they are published, then removed)")
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
    for path in flags:
        fid = _marker_id(path)
        _set_halt_locked(f"pending halt incident {fid} (its marker could not be written)", source=f"halt_pending_"
                         f"unwritten:{fid}", account="", film_id="", take_id="",
                         evidence=f"HALT_PENDING_UNWRITTEN published_by={by}")
        published.append((path, f"{UNWRITTEN_DIRNAME}/{fid}" if path.parent == unwritten_dir() else fid))
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
