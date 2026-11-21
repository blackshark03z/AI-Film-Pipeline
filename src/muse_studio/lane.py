#!/usr/bin/env python3
"""
Muse production lanes: persistent per-lane account leases (one Antigravity chat = one lane).

  python -m muse_studio.lane open   --lane L --project <abs dir> -n N [--accounts a,b] [--ttl-hours 8] [--simulate]
  python -m muse_studio.lane status [--lane L]
  python -m muse_studio.lane renew  --lane L [--ttl-hours H]
  python -m muse_studio.lane close  --lane L
  python -m muse_studio.lane gc

Every subcommand prints ONE JSON object on stdout. Exit 0 on success; `open` exits 2 when no account is granted;
exit 3 on a lane/project binding conflict (`LANE_ID_IN_USE`, `PROJECT_IN_USE`): a lane is bound to its project at
first open, a project belongs to one live lane, and `renew`/`close --project P` refuse a lane bound elsewhere.
Registry: `muse_studio/data/lane_leases.json` (env `MUSE_LEASES_FILE` overrides; `--simulate` without the env
uses a temp registry and grants `sim_acc_XX` ids, never touching the real one).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .core.account_manager import AccountManager
    from .core.autoprod_orchestrator import BusyAccountDetector
    from .core.config import ACCOUNTS_FILE, PROFILES_DIR
    from .core.lane_leases import (
        DEFAULT_TTL_HOURS,
        LeaseConflictError,
        LeaseRegistry,
        _iso,
        default_leases_path,
        is_lease_live,
        lane_file_path,
        public_lease_view,
        read_lane_file,
        real_leases_path,
        utcnow,
        write_lane_file,
    )
except ImportError:
    from core.account_manager import AccountManager
    from core.autoprod_orchestrator import BusyAccountDetector
    from core.config import ACCOUNTS_FILE, PROFILES_DIR
    from core.lane_leases import (
        DEFAULT_TTL_HOURS,
        LeaseConflictError,
        LeaseRegistry,
        _iso,
        default_leases_path,
        is_lease_live,
        lane_file_path,
        public_lease_view,
        read_lane_file,
        real_leases_path,
        utcnow,
        write_lane_file,
    )


SIM_ID_POOL = 99


class LaneError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 1, **extra: Any):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.extra = extra


def _emit(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _csv(raw: Optional[str]) -> List[str]:
    out: List[str] = []
    for x in (raw or "").split(","):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


def _registry(args: argparse.Namespace) -> LeaseRegistry:
    simulate = bool(getattr(args, "simulate", False))
    path: Optional[Path] = None
    explicit = getattr(args, "leases_file", None)
    if explicit:
        path = Path(explicit)
    else:
        project = getattr(args, "project", None)
        if project:
            lj = read_lane_file(Path(project))
            if lj and lj.get("leases_file") and (not getattr(args, "lane", None) or lj.get("lane_id") == args.lane):
                path = Path(lj["leases_file"])
    if path is None:
        path = default_leases_path(simulate=simulate)
    # --simulate may read the production registry (status) but never mutate it, whatever pointed there.
    if simulate and args.subcommand != "status" and path.resolve() == real_leases_path().resolve():
        raise LaneError(
            "SIMULATE_REAL_REGISTRY",
            f"--simulate refuses to modify the production registry {path}; set MUSE_LEASES_FILE to a scratch file",
        )
    return LeaseRegistry(path)


def _account_manager(args: argparse.Namespace) -> AccountManager:
    storage = Path(args.accounts_file) if getattr(args, "accounts_file", None) else ACCOUNTS_FILE
    profiles = Path(args.profiles_dir) if getattr(args, "profiles_dir", None) else PROFILES_DIR
    return AccountManager(storage_file=storage, profiles_dir=profiles)


def cmd_open(args: argparse.Namespace) -> Dict[str, Any]:
    lane_id = args.lane.strip()
    if not lane_id:
        raise LaneError("BAD_LANE_ID", "--lane must not be empty")
    project = Path(args.project)
    if not project.is_absolute():
        raise LaneError("PROJECT_NOT_ABSOLUTE", f"--project must be an absolute path: {args.project}")
    project = project.resolve()
    n = int(args.n)
    if n < 1:
        raise LaneError("BAD_N", "-n must be >= 1")
    ttl = float(args.ttl_hours)
    registry = _registry(args)
    only = _csv(args.accounts)

    existing = read_lane_file(project)
    if existing and existing.get("status") == "open" and existing.get("lane_id") not in (None, lane_id):
        # The registry claim (checked atomically in acquire) is authoritative; this also covers a lane.json whose
        # lane lives in a different registry file.
        other = existing.get("lane_id")
        other_reg = LeaseRegistry(Path(existing["leases_file"])) if existing.get("leases_file") else registry
        if other_reg.lane_accounts(other):
            raise LaneError(
                "PROJECT_IN_USE",
                f"{project} is held by open lane {other}; close it first",
                exit_code=3,
                holder_lane=other,
            )

    skipped: Dict[str, str] = {}
    if args.simulate:
        candidates = only or [f"sim_acc_{i:02d}" for i in range(1, SIM_ID_POOL + 1)]
    else:
        mgr = _account_manager(args)
        avail, sel_skipped = BusyAccountDetector.select_uncontended_ready_accounts(
            mgr, lane_id=lane_id, leases=registry.live_leases()
        )
        known = {a["id"]: a for a in mgr.list_accounts()}
        if only:
            candidates = [a for a in avail if a in only]
            for aid in only:
                if aid not in known:
                    skipped[aid] = "UNKNOWN_ACCOUNT"
        else:
            candidates = list(avail)
        for aid, reason in sel_skipped.items():
            if not only or aid in only:
                skipped[aid] = reason
        for aid, acc in known.items():
            if aid in avail or aid in skipped or (only and aid not in only):
                continue
            skipped[aid] = f"NOT_READY_{(acc.get('status') or 'UNKNOWN').upper()}"

    held, new_ids, reg_skipped = registry.acquire(lane_id, str(project), candidates, n, ttl_hours=ttl)
    skipped.update(reg_skipped)
    for aid in held:
        skipped.pop(aid, None)
    if not args.simulate:
        for aid in candidates:
            if aid not in held and aid not in skipped:
                skipped[aid] = "NOT_NEEDED_N_REACHED"

    now_iso = _iso(utcnow())
    prev_open = existing if existing and existing.get("lane_id") == lane_id and existing.get("status") == "open" else None
    lane_doc_needed = bool(held) or bool(existing and existing.get("lane_id") == lane_id)
    lane_doc = {
        "lane_id": lane_id,
        "project_dir": str(project),
        "accounts": held,
        "opened_at": (prev_open or {}).get("opened_at") or now_iso,
        "renewed_at": now_iso,
        "ttl_hours": ttl,
        "status": "open" if held else "blocked",
        "simulate": bool(args.simulate),
        "leases_file": str(registry.path),
    }
    if lane_doc_needed:
        # Written only after the registry claimed the project for this lane (or to mark this lane's own file).
        write_lane_file(project, lane_doc)

    live = registry.live_leases()
    expires = sorted({live[a]["expires_at"] for a in held if a in live})
    out = {
        "lane_id": lane_id,
        "project_dir": str(project),
        "accounts": held,
        "granted": len(held),
        "requested": n,
        "held_exceeds_requested": len(held) > n,
        "newly_granted": new_ids,
        "skipped": dict(sorted(skipped.items())),
        "expires_at": expires[0] if expires else None,
        "lane_file": str(lane_file_path(project)),
        "leases_file": str(registry.path),
        "simulate": bool(args.simulate),
    }
    if not held:
        raise LaneError("NO_ACCOUNTS_GRANTED", "0 accounts granted", exit_code=2, **out)
    return out


def cmd_status(args: argparse.Namespace) -> Dict[str, Any]:
    registry = _registry(args)
    now = utcnow()
    live = registry.live_leases(now)
    mgr = _account_manager(args)
    accounts: List[Dict[str, Any]] = []
    seen = set()
    for acc in mgr.list_accounts():
        aid = acc["id"]
        seen.add(aid)
        rec = live.get(aid)
        if args.lane and (not rec or rec.get("lane_id") != args.lane):
            continue
        usage = acc.get("usage_info") or {}
        accounts.append({
            "id": aid,
            "name": acc.get("name"),
            "email": acc.get("email"),
            "status": acc.get("status"),
            "quota_pct": AccountManager.get_effective_quota_pct(acc) if usage else None,
            "weekly_remaining_pct": usage.get("weekly_remaining_pct"),
            "lease": public_lease_view(rec, now),
            "profile_locked": BusyAccountDetector.is_profile_locked(mgr.profiles_dir / aid),
        })
    # Leased ids that are not in accounts.json (simulated lanes, deleted accounts).
    for aid, rec in sorted(live.items()):
        if aid in seen or (args.lane and rec.get("lane_id") != args.lane):
            continue
        accounts.append({
            "id": aid,
            "status": "NOT_IN_ACCOUNTS_FILE",
            "quota_pct": None,
            "lease": public_lease_view(rec, now),
            "profile_locked": False,
        })

    lanes: Dict[str, Dict[str, Any]] = {}
    for aid, rec in live.items():
        lid = rec.get("lane_id")
        if args.lane and lid != args.lane:
            continue
        ln = lanes.setdefault(lid, {"project_dir": rec.get("project_dir"), "accounts": [], "expires_at": None})
        ln["accounts"].append(aid)
        exp = rec.get("expires_at")
        if exp and (ln["expires_at"] is None or exp < ln["expires_at"]):
            ln["expires_at"] = exp
    for ln in lanes.values():
        ln["accounts"].sort()

    return {
        "leases_file": str(registry.path),
        "lane_filter": args.lane,
        "lanes": lanes,
        "accounts": accounts,
        "checked_at": _iso(now),
    }


def cmd_renew(args: argparse.Namespace) -> Dict[str, Any]:
    registry = _registry(args)
    project = str(Path(args.project).resolve()) if args.project else None
    held, expired = registry.renew(args.lane, args.ttl_hours, project_dir=project)
    live = registry.live_leases()
    expires = sorted({live[a]["expires_at"] for a in held if a in live})
    out = {
        "lane_id": args.lane,
        "accounts": held,
        "renewed": len(held),
        "expired_dropped": expired,
        "expires_at": expires[0] if expires else None,
        "leases_file": str(registry.path),
    }
    if not held:
        raise LaneError("LANE_HAS_NO_LIVE_LEASES", f"lane {args.lane} holds no live lease", exit_code=2, **out)
    return out


def cmd_close(args: argparse.Namespace) -> Dict[str, Any]:
    registry = _registry(args)
    projects = {
        rec.get("project_dir")
        for rec in registry.snapshot().values()
        if rec.get("lane_id") == args.lane and rec.get("project_dir")
    }
    project = str(Path(args.project).resolve()) if args.project else None
    released = registry.release(args.lane, project_dir=project)  # refuses (exit 3) a lane bound to another project
    if project:
        projects.add(project)
    closed_files: List[str] = []
    for proj in sorted(projects):
        lj = read_lane_file(Path(proj))
        if lj and lj.get("lane_id") == args.lane and lj.get("status") != "closed":
            lj["status"] = "closed"
            lj["closed_at"] = _iso(utcnow())
            closed_files.append(str(write_lane_file(Path(proj), lj)))
    return {
        "lane_id": args.lane,
        "released": released,
        "lane_files_closed": closed_files,
        "leases_file": str(registry.path),
    }


def cmd_gc(args: argparse.Namespace) -> Dict[str, Any]:
    registry = _registry(args)
    dropped = registry.gc()
    return {"dropped": dropped, "dropped_count": len(dropped), "leases_file": str(registry.path)}


def _add_registry_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--simulate", action="store_true", help="Use the simulate registry (env or temp file)")
    p.add_argument("--leases-file", default=None, help="Explicit lease registry path (tests/tools)")


def _add_accounts_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--accounts-file", default=None, help="Custom accounts.json")
    p.add_argument("--profiles-dir", default=None, help="Custom profiles dir")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Muse production lanes: per-lane account leases")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_open = sub.add_parser("open", help="Claim up to N READY accounts for a lane and write <project>/lane.json")
    p_open.add_argument("--lane", required=True)
    p_open.add_argument("--project", required=True, help="Absolute project directory")
    p_open.add_argument("-n", "--n", type=int, required=True, dest="n")
    p_open.add_argument("--accounts", default="", help="Restrict to these account ids (comma separated)")
    p_open.add_argument("--ttl-hours", type=float, default=DEFAULT_TTL_HOURS)
    _add_registry_args(p_open)
    _add_accounts_args(p_open)

    p_status = sub.add_parser("status", help="Every account with its lease (no secrets)")
    p_status.add_argument("--lane", default=None)
    p_status.add_argument("--project", default=None)
    _add_registry_args(p_status)
    _add_accounts_args(p_status)

    p_renew = sub.add_parser("renew", help="Extend all leases of a lane")
    p_renew.add_argument("--lane", required=True)
    p_renew.add_argument("--ttl-hours", type=float, default=None)
    p_renew.add_argument("--project", default=None)
    _add_registry_args(p_renew)

    p_close = sub.add_parser("close", help="Release all leases of a lane and mark lane.json closed")
    p_close.add_argument("--lane", required=True)
    p_close.add_argument("--project", default=None)
    _add_registry_args(p_close)

    p_gc = sub.add_parser("gc", help="Drop expired leases")
    _add_registry_args(p_gc)
    return parser


COMMANDS = {"open": cmd_open, "status": cmd_status, "renew": cmd_renew, "close": cmd_close, "gc": cmd_gc}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _emit(COMMANDS[args.subcommand](args))
        return 0
    except LaneError as le:
        _emit({"error": le.code, "message": str(le), **le.extra})
        return le.exit_code
    except LeaseConflictError as ce:
        _emit({"error": ce.code, "message": str(ce), **ce.extra})
        return 3
    except Exception as exc:  # noqa: BLE001 - CLI contract: always one JSON object
        _emit({"error": type(exc).__name__, "message": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
