"""
Persistent per-lane account leases.

A *lane* is one production chat (one Antigravity conversation). It holds N Muse accounts through leases stored in
`data/lane_leases.json` (override: env `MUSE_LEASES_FILE`). A lease is live while `now < expires_at`; process
liveness is deliberately ignored because a lane spans many short-lived processes.

Every read-modify-write runs under an OS file lock on a sidecar `<registry>.lock` file plus an atomic replace, so
concurrent processes never lose a write or double-grant an account.

This module depends only on `config` so that `autoprod_orchestrator` and `parallel_pool_engine` can import it.
"""

import json
import os
import socket
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple

try:
    from .config import DATA_DIR
except ImportError:
    from core.config import DATA_DIR


LEASES_ENV = "MUSE_LEASES_FILE"
HEARTBEAT_ENV = "MUSE_LANE_HEARTBEAT_S"
DEFAULT_TTL_HOURS = 8.0
DEFAULT_HEARTBEAT_S = 300.0
LANE_FILE_NAME = "lane.json"
SIM_LEASES_FILE_NAME = "muse_sim_lane_leases.json"
LOCK_TIMEOUT_S = 30.0


class LeaseRegistryError(RuntimeError):
    """The registry exists but cannot be read/parsed: fail closed (no grant, no dispatch), never overwrite it."""


class LeaseConflictError(RuntimeError):
    """A lane/project binding conflict: `code` is `LANE_ID_IN_USE` or `PROJECT_IN_USE`."""

    def __init__(self, code: str, message: str, **extra: Any):
        super().__init__(message)
        self.code = code
        self.extra = extra


def norm_project(project_dir: Any) -> str:
    """Comparable key for a project dir (absolute, case-folded on Windows)."""
    return os.path.normcase(os.path.abspath(str(project_dir)))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _parse_iso(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def real_leases_path() -> Path:
    """The production registry, next to `accounts.json` (ignores the env override)."""
    return DATA_DIR / "lane_leases.json"


def default_leases_path(simulate: bool = False) -> Path:
    """`MUSE_LEASES_FILE` if set; otherwise the real registry, or a temp registry in simulate mode."""
    env = os.environ.get(LEASES_ENV, "").strip()
    if env:
        return Path(env)
    if simulate:
        return Path(tempfile.gettempdir()) / SIM_LEASES_FILE_NAME
    return real_leases_path()


def heartbeat_interval_s() -> float:
    try:
        return max(1.0, float(os.environ.get(HEARTBEAT_ENV, DEFAULT_HEARTBEAT_S)))
    except ValueError:
        return DEFAULT_HEARTBEAT_S


def is_lease_live(rec: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> bool:
    if not rec:
        return False
    exp = _parse_iso(rec.get("expires_at"))
    return exp is not None and (now or utcnow()) < exp


@contextmanager
def _os_file_lock(lock_path: Path, timeout_s: float = LOCK_TIMEOUT_S) -> Iterator[None]:
    """Exclusive inter-process lock on byte 0 of a sidecar file (msvcrt on Windows, fcntl elsewhere)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + timeout_s
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            while True:
                os.lseek(fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Timed out waiting for lease lock {lock_path}")
                    time.sleep(0.02)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Timed out waiting for lease lock {lock_path}")
                    time.sleep(0.02)
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


def _replace_with_retry(src: Path, dst: Path) -> None:
    # Windows refuses os.replace while a reader outside the lock has the target open; retry briefly.
    for attempt in range(50):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.02)


class LeaseRegistry:
    """File-backed `{account_id: lease}` map shared by every lane and every process."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else default_leases_path()
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    # ---- low level -------------------------------------------------------------------------------------------
    def _load_unlocked(self) -> Dict[str, Any]:
        # Only a missing (or empty) file means "no leases". Any other read/parse/schema problem raises, so a broken
        # registry can neither let a run use leased accounts nor be overwritten by the next acquire.
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raw = ""
        except OSError as exc:
            raise LeaseRegistryError(f"Cannot read lease registry {self.path}: {exc}") from exc
        if not raw.strip():
            return {"version": 1, "leases": {}, "projects": {}}
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise LeaseRegistryError(f"Corrupt lease registry {self.path}: {exc}") from exc
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("leases", {}), dict)
            or not isinstance(data.get("projects", {}), dict)
        ):
            raise LeaseRegistryError(f"Unexpected lease registry schema in {self.path}")
        data.setdefault("leases", {})
        data.setdefault("projects", {})
        data.setdefault("version", 1)
        return data

    def _save_unlocked(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = _iso(utcnow())
        tmp = self.path.with_name(f".{self.path.name}.tmp.{os.getpid()}.{time.monotonic_ns()}")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        _replace_with_retry(tmp, self.path)

    @contextmanager
    def _transaction(self) -> Iterator[Dict[str, Any]]:
        with _os_file_lock(self.lock_path):
            data = self._load_unlocked()
            before = json.dumps([data["leases"], data["projects"]], sort_keys=True)
            yield data  # an exception raised by the caller aborts the transaction: nothing is written
            if json.dumps([data["leases"], data["projects"]], sort_keys=True) != before:
                self._save_unlocked(data)

    @staticmethod
    def _prune(data: Dict[str, Any], now: datetime) -> List[Dict[str, Any]]:
        """Drop expired leases and project claims whose lane no longer holds a live lease."""
        leases, projects = data["leases"], data["projects"]
        dropped = []
        for aid in [a for a, r in leases.items() if not is_lease_live(r, now)]:
            rec = leases.pop(aid)
            dropped.append({"id": aid, "lane_id": rec.get("lane_id"), "expires_at": rec.get("expires_at")})
        live_lanes = {r.get("lane_id") for r in leases.values()}
        for key in [k for k, c in projects.items() if c.get("lane_id") not in live_lanes]:
            del projects[key]
        return dropped

    @staticmethod
    def _bound_project(data: Dict[str, Any], lane_id: str) -> Optional[str]:
        """The project a lane is bound to (its first open), from the claim map or its live leases."""
        for claim in data["projects"].values():
            if claim.get("lane_id") == lane_id:
                return claim.get("project_dir")
        for rec in data["leases"].values():
            if rec.get("lane_id") == lane_id and rec.get("project_dir"):
                return rec.get("project_dir")
        return None

    @classmethod
    def _check_lane_project(cls, data: Dict[str, Any], lane_id: str, project_dir: Optional[str]) -> None:
        if not project_dir:
            return
        bound = cls._bound_project(data, lane_id)
        if bound and norm_project(bound) != norm_project(project_dir):
            raise LeaseConflictError(
                "LANE_ID_IN_USE",
                f"lane {lane_id} is bound to project {bound}, not {project_dir}",
                lane_id=lane_id,
                bound_project=bound,
            )

    def _pruned_copy(self) -> Optional[Dict[str, Any]]:
        if not self.path.exists():
            return None
        with _os_file_lock(self.lock_path):
            data = self._load_unlocked()
        self._prune(data, utcnow())
        return data

    def lane_project(self, lane_id: str) -> Optional[str]:
        data = self._pruned_copy()
        return self._bound_project(data, lane_id) if data else None

    def project_holder(self, project_dir: Any) -> Optional[str]:
        data = self._pruned_copy()
        claim = (data or {}).get("projects", {}).get(norm_project(project_dir))
        return claim.get("lane_id") if claim else None

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """All lease records (live and expired), read under the lock."""
        if not self.path.exists():
            return {}
        with _os_file_lock(self.lock_path):
            return dict(self._load_unlocked()["leases"])

    # ---- queries ---------------------------------------------------------------------------------------------
    def live_leases(self, now: Optional[datetime] = None) -> Dict[str, Dict[str, Any]]:
        now = now or utcnow()
        return {aid: rec for aid, rec in self.snapshot().items() if is_lease_live(rec, now)}

    def lane_accounts(self, lane_id: str, now: Optional[datetime] = None) -> List[str]:
        return sorted(aid for aid, rec in self.live_leases(now).items() if rec.get("lane_id") == lane_id)

    def holder_of(self, account_id: str, now: Optional[datetime] = None) -> Optional[str]:
        rec = self.live_leases(now).get(account_id)
        return rec.get("lane_id") if rec else None

    # ---- mutations -------------------------------------------------------------------------------------------
    def acquire(
        self,
        lane_id: str,
        project_dir: str,
        candidates: Iterable[str],
        n: int,
        ttl_hours: float = DEFAULT_TTL_HOURS,
    ) -> Tuple[List[str], List[str], Dict[str, str]]:
        """
        Keep/extend every live lease of `lane_id`, then top up to `n` from `candidates` (in order). Never releases:
        a smaller `n` on re-open keeps every held lease. Returns `(held_ids, newly_granted_ids, skipped_reasons)`.

        A lane is bound to its project at first open and a project to one lane, both checked and claimed inside the
        same locked transaction: `LeaseConflictError("LANE_ID_IN_USE")` when the lane is live on another project,
        `LeaseConflictError("PROJECT_IN_USE")` when another live lane holds the project.
        """
        if not lane_id:
            raise ValueError("lane_id is required")
        now = utcnow()
        exp = _iso(now + timedelta(hours=float(ttl_hours)))
        host = socket.gethostname()
        skipped: Dict[str, str] = {}
        new_ids: List[str] = []
        with self._transaction() as data:
            leases, projects = data["leases"], data["projects"]
            self._prune(data, now)
            self._check_lane_project(data, lane_id, project_dir)
            claim = projects.get(norm_project(project_dir))
            holder = (claim or {}).get("lane_id") or next(
                (
                    r.get("lane_id")
                    for r in leases.values()
                    if r.get("project_dir") and norm_project(r["project_dir"]) == norm_project(project_dir)
                ),
                None,
            )  # leases written before the claim map existed still bind their project
            if holder and holder != lane_id:
                raise LeaseConflictError(
                    "PROJECT_IN_USE",
                    f"project {project_dir} is held by live lane {holder}",
                    holder_lane=holder,
                )
            held = [aid for aid, rec in leases.items() if rec.get("lane_id") == lane_id]
            for aid in held:
                rec = leases[aid]
                rec.update(
                    project_dir=project_dir,
                    heartbeat_at=_iso(now),
                    expires_at=exp,
                    ttl_hours=float(ttl_hours),
                    host=host,
                    pid=os.getpid(),
                )
            need = int(n) - len(held)
            for aid in candidates:
                if aid in held or aid in new_ids:
                    continue
                other = leases.get(aid)
                if other is not None:
                    skipped[aid] = f"LEASED_BY_{other.get('lane_id')}"
                    continue
                if need <= 0:
                    continue
                leases[aid] = {
                    "lane_id": lane_id,
                    "project_dir": project_dir,
                    "acquired_at": _iso(now),
                    "heartbeat_at": _iso(now),
                    "expires_at": exp,
                    "ttl_hours": float(ttl_hours),
                    "host": host,
                    "pid": os.getpid(),
                }
                new_ids.append(aid)
                need -= 1
            if held or new_ids:
                projects[norm_project(project_dir)] = {
                    "lane_id": lane_id,
                    "project_dir": project_dir,
                    "claimed_at": (claim or {}).get("claimed_at") or _iso(now),
                }
        return sorted(held + new_ids), new_ids, skipped

    def renew(
        self, lane_id: str, ttl_hours: Optional[float] = None, project_dir: Optional[str] = None
    ) -> Tuple[List[str], List[str]]:
        """
        Extend every live lease of the lane. Expired ones are dropped, not revived. Returns `(held, expired)`.
        `project_dir` (optional) must match the lane's bound project, else `LeaseConflictError("LANE_ID_IN_USE")`.
        """
        now = utcnow()
        held: List[str] = []
        expired: List[str] = []
        with self._transaction() as data:
            leases = data["leases"]
            self._check_lane_project(data, lane_id, project_dir)
            for aid in list(leases):
                rec = leases[aid]
                if rec.get("lane_id") != lane_id:
                    continue
                if not is_lease_live(rec, now):
                    expired.append(aid)
                    del leases[aid]
                    continue
                ttl = float(ttl_hours if ttl_hours is not None else rec.get("ttl_hours") or DEFAULT_TTL_HOURS)
                rec["heartbeat_at"] = _iso(now)
                rec["expires_at"] = _iso(now + timedelta(hours=ttl))
                rec["ttl_hours"] = ttl
                rec["pid"] = os.getpid()
                held.append(aid)
            self._prune(data, now)
        return sorted(held), sorted(expired)

    def release(self, lane_id: str, project_dir: Optional[str] = None) -> List[str]:
        """Release every lease and project claim of the lane (`project_dir`, if given, must match its binding)."""
        released: List[str] = []
        with self._transaction() as data:
            leases, projects = data["leases"], data["projects"]
            self._check_lane_project(data, lane_id, project_dir)
            for aid in [a for a, r in leases.items() if r.get("lane_id") == lane_id]:
                del leases[aid]
                released.append(aid)
            for key in [k for k, c in projects.items() if c.get("lane_id") == lane_id]:
                del projects[key]
        return sorted(released)

    def gc(self) -> List[Dict[str, Any]]:
        with self._transaction() as data:
            return self._prune(data, utcnow())


def public_lease_view(rec: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Read-only lease summary for UIs/status (no host/pid)."""
    if not rec or not is_lease_live(rec, now):
        return None
    now = now or utcnow()
    hb = _parse_iso(rec.get("heartbeat_at"))
    return {
        "lane_id": rec.get("lane_id"),
        "project_dir": rec.get("project_dir"),
        "expires_at": rec.get("expires_at"),
        "heartbeat_age_s": int((now - hb).total_seconds()) if hb else None,
    }


# ---- lane.json (per project) ---------------------------------------------------------------------------------
def lane_file_path(project_dir: Path) -> Path:
    return Path(project_dir) / LANE_FILE_NAME


def read_lane_file(project_dir: Path) -> Optional[Dict[str, Any]]:
    p = lane_file_path(project_dir)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_lane_file(project_dir: Path, payload: Dict[str, Any]) -> Path:
    p = lane_file_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _replace_with_retry(tmp, p)
    return p


class LaneContext:
    """
    A running lane inside one pool process: knows which accounts the lane may touch and keeps its leases alive.

    `read_only=True` never writes the registry (used by `--simulate` runs pointed at the real registry).
    """

    def __init__(
        self,
        lane_id: str,
        registry: LeaseRegistry,
        ttl_hours: Optional[float] = None,
        read_only: bool = False,
    ):
        self.lane_id = lane_id
        self.registry = registry
        self.ttl_hours = ttl_hours
        self.read_only = read_only
        self.started_with: Set[str] = set(registry.lane_accounts(lane_id))
        self.lost: Set[str] = set()
        self.renewals = 0

    def held_ids(self) -> Set[str]:
        held = set(self.registry.lane_accounts(self.lane_id))
        self.lost.update(self.started_with - held)
        return held

    def owns(self, account_id: str) -> bool:
        ok = self.registry.holder_of(account_id) == self.lane_id
        if not ok and account_id in self.started_with:
            self.lost.add(account_id)
        return ok

    def renew(self) -> Set[str]:
        if self.read_only:
            return self.held_ids()
        held, expired = self.registry.renew(self.lane_id, self.ttl_hours)
        self.renewals += 1
        self.lost.update(expired)
        self.lost.update(self.started_with - set(held))
        return set(held)

    def report(self) -> Dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "leases_file": str(self.registry.path),
            "accounts": sorted(self.started_with),
            "lost_leases": sorted(self.lost),
            "renewals": self.renewals,
            "read_only": self.read_only,
        }
