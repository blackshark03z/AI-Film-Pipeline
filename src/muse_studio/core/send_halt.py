"""Machine-wide Muse stop-all (lane contract v8 §6, §11; R15).

A CAPTCHA / verification / unusual-activity page seen by ANY Muse entry point stops ALL Muse sending on this machine:

1. Enter is disabled in memory first (`disable_enter`), so this process never submits again.
2. The halt is published under the halt-file lock: `halt_path()` (= `MUSE_HALT_FILE`, default
   `muse_studio/data/muse_halt.json`) is written tmp + fsync + replace while holding a 1-byte OS lock on
   `halt_path() + ".lock"` (60 s default timeout).
3. If the lock cannot be taken, the halt is NOT written without it: a lock-free create-exclusive marker
   `<AFP_STATE_DIR>/halt_pending/<lane_id>-<incarnation_id>.json` latches the stop instead, and the publication is
   retried (`finish_publication`) before the process exits 4.

Every pre-Enter gate (`send_stop`) refuses while any stop signal is present: the in-memory stop, `MUSE_HALT_FILE`,
any `halt_pending/` entry, or `AFP_HALT_FILE` when that is configured. The files are read under the halt-file lock;
anything unreadable (or a lock timeout) also refuses. The per-project `muse_halt.json` is a report copy (it also
refuses for that project). Only an explicit `--clear-halt` removes the Muse halt; it never removes `halt_pending/`
markers (that is the Owner's AFP `halt clear --include-pending`).
"""

import json
import os
import secrets
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

HALT_FILE = "muse_halt.json"
CLEAR_HALT_HINT = "clear the CAPTCHA / verification by hand on Muse, then rerun with --clear-halt"
HALTED_EXIT_CODE = 4
SIM_ACCOUNT_PREFIX = "sim_acc_"
DEFAULT_LOCK_TIMEOUT_S = 60.0
DEFAULT_PENDING_WINDOW_S = 900.0
# One per process: names this process's pending marker (contract §11 incarnation).
INCARNATION_ID = secrets.token_hex(6)

# In-memory stop of this process (set before any file I/O) and the state of its own publication.
_MEMORY_HALT: Optional[Dict[str, Any]] = None
_PUBLICATION: Optional[str] = None  # None | PUBLISHED | PENDING | HALT_PENDING_UNWRITTEN
_PENDING_INFO: Optional[Dict[str, Any]] = None
_LANE_ID: str = "standalone"


class HaltLockTimeout(Exception):
    """The halt-file lock could not be taken in time."""


class ProductionHaltPathInTest(RuntimeError):
    """A test reached the real machine-wide halt / AFP state (it would stop or unpause live lanes)."""


def _under_test() -> bool:
    return "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _is_same_or_inside(path: Path, root: Path) -> bool:
    try:
        p, r = path.resolve(), root.resolve()
    except OSError:
        return True  # cannot tell: treat as production (fail closed)
    return p == r or r in p.parents


def _real_halt_file() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / HALT_FILE


def _guard_not_production(path: Path, source: str) -> Path:
    """The ONE pytest guard for every path this module reads, writes or clears (signal or clear path, whichever
    variable supplies it): under pytest a path that is the real Muse halt (or its lock) or lies inside the real
    `~/.afp` is refused. Outside pytest it is a no-op."""
    if _under_test():
        real = _real_halt_file()
        real_lock = Path(str(real) + ".lock")
        if (_is_same_or_inside(path, real) or _is_same_or_inside(path, real_lock)
                or _is_same_or_inside(path, Path.home() / ".afp")):
            raise ProductionHaltPathInTest(f"{source} points at the real Muse halt or ~/.afp under pytest")
    return path


def _project_halt_path(project_dir: Any) -> Path:
    """The project's own halt copy, through the same guard as every other path (a `project_dir` that is the real
    `muse_studio/data` or `~/.afp` would otherwise read, write or unlink the production halt under pytest)."""
    return _guard_not_production(Path(project_dir) / HALT_FILE, "project_dir")


def halt_path() -> Path:
    env = os.environ.get("MUSE_HALT_FILE")
    if env:
        return _guard_not_production(Path(env), "MUSE_HALT_FILE")
    if _under_test():
        # Hard guard: a test without MUSE_HALT_FILE must never read, write or clear the production halt.
        raise ProductionHaltPathInTest("MUSE_HALT_FILE is not set under pytest: the real Muse halt is off-limits")
    return _real_halt_file()


def afp_halt_file() -> Optional[Path]:
    """`AFP_HALT_FILE` (read-only signal), guarded like every other path."""
    env = os.environ.get("AFP_HALT_FILE")
    return _guard_not_production(Path(env), "AFP_HALT_FILE") if env else None


def halt_lock_path() -> Path:
    return Path(str(halt_path()) + ".lock")


def afp_state_dir() -> Path:
    env = os.environ.get("AFP_STATE_DIR")
    if env:
        return _guard_not_production(Path(env), "AFP_STATE_DIR")
    if _under_test():
        raise ProductionHaltPathInTest("AFP_STATE_DIR is not set under pytest: the real halt_pending/ is off-limits")
    return Path.home() / ".afp"


def pending_dir() -> Path:
    return afp_state_dir() / "halt_pending"


def set_lane_id(lane_id: Optional[str]) -> None:
    global _LANE_ID
    _LANE_ID = str(lane_id or "standalone")


def _lock_timeout_s() -> float:
    try:
        return float(os.environ.get("MUSE_HALT_LOCK_TIMEOUT_S") or DEFAULT_LOCK_TIMEOUT_S)
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT_S


@contextmanager
def halt_file_lock(timeout_s: Optional[float] = None) -> Iterator[None]:
    """1-byte OS lock on `halt_path() + ".lock"` (same primitive as SessionLock). Raises HaltLockTimeout."""
    path = halt_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + (_lock_timeout_s() if timeout_s is None else float(timeout_s))
    locked = False
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise HaltLockTimeout(str(path))
                time.sleep(0.05)
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(3)}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, indent=2, ensure_ascii=False))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_signal(path: Path) -> Optional[Dict[str, Any]]:
    """None when absent; the record when present; an UNREADABLE stop when it cannot be read (refuse)."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"reason": "BLOCKED", "detail": f"invalid {path.name}"}
    except (OSError, ValueError):
        return {"reason": "UNREADABLE", "detail": f"unreadable stop signal {path}"}


def _read_machine_signals() -> Optional[Dict[str, Any]]:
    """Caller holds the halt-file lock."""
    rec = _read_signal(halt_path())
    if rec is not None:
        return {**rec, "signal": "MUSE_HALT_FILE"}
    pdir = pending_dir()
    try:
        # ANY entry stops sending (contract v8): markers are written create-exclusive (no tmp names), so a directory,
        # a symlink or any other non-file entry is an unreadable marker and refuses too.
        entries = sorted(pdir.iterdir()) if pdir.exists() else []
    except OSError:
        return {"reason": "UNREADABLE", "signal": "halt_pending", "detail": f"unreadable {pdir}"}
    if entries:
        if not entries[0].is_file():
            return {"reason": "UNREADABLE", "signal": "halt_pending", "marker": entries[0].name,
                    "detail": f"halt_pending entry {entries[0].name} is not a readable marker file"}
        rec = _read_signal(entries[0]) or {}
        return {**rec, "reason": rec.get("reason") or "BLOCKED", "signal": "halt_pending", "marker": entries[0].name}
    afp = afp_halt_file()
    if afp is not None:
        rec = _read_signal(afp)
        if rec is not None:
            return {**rec, "signal": "AFP_HALT"}
    return None


def disable_enter(info: Dict[str, Any]) -> None:
    """Step 1 of any block: this process never presses Enter again (no I/O, cannot fail)."""
    global _MEMORY_HALT
    if _MEMORY_HALT is None:
        _MEMORY_HALT = dict(info)


def send_stop() -> Optional[Dict[str, Any]]:
    """The stop every pre-Enter gate honours (None = may send). In-memory first, then the machine-wide signals read
    under the halt-file lock; a lock timeout or an unreadable signal refuses."""
    global _MEMORY_HALT
    if _MEMORY_HALT is not None:
        if _PUBLICATION != "PUBLISHED":
            return {**_MEMORY_HALT, "signal": "MEMORY"}
        # Our own published halt: it holds as long as the file does (an Owner --clear-halt lifts it).
    try:
        with halt_file_lock():
            sig = _read_machine_signals()
    except HaltLockTimeout:
        return {"reason": "HALT_LOCK_TIMEOUT", "signal": "LOCK", "detail": str(halt_lock_path())}
    except OSError as exc:
        return {"reason": "UNREADABLE", "signal": "LOCK", "detail": str(exc)[:200]}
    if sig is None and _MEMORY_HALT is not None:
        _reset_memory()  # published, then cleared by the Owner
    return sig


def _reset_memory() -> None:
    global _MEMORY_HALT, _PUBLICATION, _PENDING_INFO
    _MEMORY_HALT, _PUBLICATION, _PENDING_INFO = None, None, None


def _write_pending_marker(info: Dict[str, Any]) -> bool:
    """Lock-free, create-exclusive + fsync (the lock is exactly what could not be taken). No secrets."""
    pdir = pending_dir()
    path = pdir / f"{_LANE_ID}-{INCARNATION_ID}.json"
    if path.exists():
        return True
    payload = {"provider": "muse", "account_id": info.get("account_id"), "reason": info.get("reason", "BLOCKED"),
               "batch_id": info.get("batch_id"), "ts": info.get("at")}
    try:
        pdir.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            os.write(fd, json.dumps(payload).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return True
    except FileExistsError:
        return True
    except OSError:
        return False


def _publish_locked(info: Dict[str, Any], timeout_s: Optional[float] = None) -> None:
    with halt_file_lock(timeout_s):
        path = halt_path()
        if _read_signal(path) is None:  # the first incident stays the record
            _write_atomic(path, {**info, "clear_with": CLEAR_HALT_HINT})


def publish_halt(info: Dict[str, Any], project_dir: Optional[Path] = None) -> str:
    """Synchronous, at the moment of detection and before any awaited cleanup. Returns the publication status."""
    global _PUBLICATION, _PENDING_INFO
    ppath = _project_halt_path(project_dir) if project_dir is not None else None  # guard before any write
    disable_enter(info)
    if _PUBLICATION != "PUBLISHED":
        try:
            _publish_locked(info)
            _PUBLICATION, _PENDING_INFO = "PUBLISHED", None
        except (HaltLockTimeout, OSError):
            _PENDING_INFO = dict(info)
            _PUBLICATION = "PENDING" if _write_pending_marker(info) else "HALT_PENDING_UNWRITTEN"
    if ppath is not None:
        try:
            if not ppath.exists():
                _write_atomic(ppath, {**info, "clear_with": CLEAR_HALT_HINT})
        except OSError:
            pass  # report copy only
    return _PUBLICATION or "PUBLISHED"


def publication_status() -> Optional[str]:
    return _PUBLICATION


def finish_publication(window_s: Optional[float] = None) -> Optional[str]:
    """Before exiting 4: retry a pending locked publication (and an unwritten marker) with backoff, up to the window
    (15 min default, env `MUSE_HALT_PENDING_WINDOW_S`). None when this process published nothing."""
    global _PUBLICATION, _PENDING_INFO
    if _PUBLICATION in (None, "PUBLISHED"):
        return _PUBLICATION
    if window_s is None:
        try:
            window_s = float(os.environ.get("MUSE_HALT_PENDING_WINDOW_S") or DEFAULT_PENDING_WINDOW_S)
        except ValueError:
            window_s = DEFAULT_PENDING_WINDOW_S
    deadline = time.monotonic() + max(0.0, window_s)
    delay = 1.0
    while True:
        info = _PENDING_INFO or _MEMORY_HALT or {"reason": "BLOCKED"}
        if _PUBLICATION == "HALT_PENDING_UNWRITTEN" and _write_pending_marker(info):
            _PUBLICATION = "PENDING"
        try:
            _publish_locked(info, timeout_s=min(_lock_timeout_s(), max(0.0, deadline - time.monotonic())))
            _PUBLICATION, _PENDING_INFO = "PUBLISHED", None
            return _PUBLICATION
        except (HaltLockTimeout, OSError):
            pass
        if time.monotonic() >= deadline:
            return _PUBLICATION
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        delay = min(delay * 2, 30.0)


def load_halt(project_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Start-of-run check: the machine-wide stop, else the project's own halt copy."""
    sig = send_stop()
    if sig is not None:
        return sig
    if project_dir is None:
        return None
    rec = _read_signal(_project_halt_path(project_dir))
    return {**rec, "signal": "PROJECT_HALT_FILE"} if rec is not None else None


def clear_halt(project_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Explicit `--clear-halt` only: remove the machine-wide Muse halt (under the lock) and this project's copy.
    `halt_pending/` markers are never removed here. Returns what was cleared."""
    cleared: Optional[Dict[str, Any]] = None
    ppath = _project_halt_path(project_dir) if project_dir is not None else None  # guard before any unlink
    with halt_file_lock():
        path = halt_path()
        rec = _read_signal(path)
        if rec is not None:
            cleared = rec
            path.unlink()
    if ppath is not None:
        rec = _read_signal(ppath)
        if rec is not None:
            cleared = cleared or rec
            ppath.unlink()
    if _PUBLICATION in (None, "PUBLISHED"):
        _reset_memory()
    return cleared


def halt_info(exc: BaseException, account_id: Optional[str], batch_id: Optional[str]) -> Dict[str, Any]:
    return {
        "reason": "BLOCKED",
        "account_id": account_id,
        "batch_id": batch_id,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "detail": str(exc)[:200],
    }


def record_block(project_dir: Optional[Path], info: Dict[str, Any], account_manager: Any, simulate: bool) -> None:
    """Publish the halt (never in a dry run) and take the blocked account out with a "BLOCKED:" reason."""
    if simulate:
        return
    publish_halt(info, project_dir)
    aid = info.get("account_id")
    if aid and account_manager is not None and not str(aid).startswith(SIM_ACCOUNT_PREFIX):
        try:
            account_manager.update_account(
                aid, status="ERROR",
                error_message=f"BLOCKED: CAPTCHA / verification page on Muse (batch {info.get('batch_id')}); "
                              "clear by hand",
            )
        except Exception:
            pass


def halted_line(info: Optional[Dict[str, Any]]) -> str:
    """One stderr line for a halted run. A CAPTCHA block says so; any other halt (OWNER_PAUSE, a pending marker, an
    unreadable signal, the AFP halt, ...) prints the halt record's own reason / detail, never a made-up CAPTCHA."""
    h = info or {}
    reason = str(h.get("reason") or "BLOCKED")
    if reason == "BLOCKED":
        return (f"[!] HALTED: Muse showed a CAPTCHA / verification page (account {h.get('account_id')}, batch "
                f"{h.get('batch_id')}); all Muse sending on this machine stopped. Clear it by hand on Muse, then "
                f"rerun with --clear-halt.")
    where = f" [{h.get('signal')}]" if h.get("signal") else ""
    detail = str(h.get("detail") or "").strip()
    return (f"[!] HALTED: {reason}{where}" + (f": {detail[:300]}" if detail else "")
            + "; all Muse sending on this machine is stopped. Only the Owner lifts it (--clear-halt for the Muse halt "
              "file; halt_pending markers via AFP).")
