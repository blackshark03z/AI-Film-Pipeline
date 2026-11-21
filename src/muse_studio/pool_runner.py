#!/usr/bin/env python3
"""
Muse Studio Parallel Pool Runner (`N tài khoản × 6 video shots` / `N × 4 keyframes`).
Công cụ thực thi chuyên biệt cho Gemini Agent (kỹ năng `muse-filmmaker`):
  python -m muse_studio.pool_runner capacity  [--max-accounts N]
  python -m muse_studio.pool_runner keyframes <project_dir> [--max-accounts N]
  python -m muse_studio.pool_runner videos    <project_dir> [--max-accounts N] [--max-rounds 3] [--auto-repair]
Lanes: `--lane <id>` (or an open `<project_dir>/lane.json`) restricts the run to that lane's leased accounts;
without a lane every account leased by a live lane is skipped (see `python -m muse_studio.lane`).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Set

try:
    from .core import send_halt
    from .core.account_manager import AccountManager
    from .core.autoprod_orchestrator import SessionConflictError
    from .core.config import ACCOUNTS_FILE, PROFILES_DIR
    from .core.lane_leases import LaneContext, LeaseRegistry, default_leases_path, read_lane_file, real_leases_path
    from .core.parallel_pool_engine import ParallelPoolEngine
except ImportError:
    from core import send_halt
    from core.account_manager import AccountManager
    from core.autoprod_orchestrator import SessionConflictError
    from core.config import ACCOUNTS_FILE, PROFILES_DIR
    from core.lane_leases import LaneContext, LeaseRegistry, default_leases_path, read_lane_file, real_leases_path
    from core.parallel_pool_engine import ParallelPoolEngine


def _add_common_pool_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--max-accounts",
        "-n",
        type=int,
        default=None,
        help="Số tài khoản tối đa được cấp N (mặc định dùng toàn bộ tài khoản READY đang rảnh -> công suất N x 6 shots)",
    )
    p.add_argument("--accounts", default="", help="Chỉ định danh sách account_id cụ thể (phẩy cách)")
    p.add_argument("--exclude-accounts", default="", help="Danh sách account_id cần chừa lại cho session khác")
    p.add_argument("--simulate", action="store_true", help="Chạy mô phỏng kiểm thử offline")
    p.add_argument("--accounts-file", default=None, help="File accounts.json tùy chỉnh")
    p.add_argument("--profiles-dir", default=None, help="Thư mục profiles tùy chỉnh")
    p.add_argument(
        "--lane",
        default=None,
        help="Lane id: chỉ dùng tài khoản lane này đang giữ lease (mặc định lấy từ <project_dir>/lane.json nếu đang open)",
    )


def _parse_csv_set(raw: str) -> Set[str]:
    return {x.strip() for x in (raw or "").split(",") if x.strip()}


def _resolve_lane(args: argparse.Namespace) -> Optional[LaneContext]:
    """`--lane` wins; otherwise an open `<project_dir>/lane.json` selects the lane automatically."""
    simulate = bool(getattr(args, "simulate", False))
    lane_id = (getattr(args, "lane", None) or "").strip() or None
    leases_file: Optional[str] = None
    project_dir = getattr(args, "project_dir", None)
    lj = read_lane_file(Path(project_dir)) if project_dir else None
    if lj and lj.get("status") == "open":
        if lane_id is None:
            lane_id = lj.get("lane_id") or None
        if lane_id and lj.get("lane_id") == lane_id:
            leases_file = lj.get("leases_file") or None
    if not lane_id:
        return None
    path = Path(leases_file) if leases_file else default_leases_path(simulate=simulate)
    # A --simulate run never writes the production registry.
    read_only = simulate and path.resolve() == real_leases_path().resolve()
    return LaneContext(lane_id, LeaseRegistry(path), read_only=read_only)


def _build_engine(args: argparse.Namespace) -> ParallelPoolEngine:
    storage_f = Path(args.accounts_file) if getattr(args, "accounts_file", None) else ACCOUNTS_FILE
    profiles_d = Path(args.profiles_dir) if getattr(args, "profiles_dir", None) else PROFILES_DIR
    mgr = AccountManager(storage_file=storage_f, profiles_dir=profiles_d)
    return ParallelPoolEngine(
        account_manager=mgr,
        sync_ui=not getattr(args, "no_ui_sync", False),
        lane=_resolve_lane(args),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Muse Parallel Pool Runner: Điều phối cực đại (N tài khoản x 6 video shots)"
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_cap = sub.add_parser("capacity", help="Kiểm tra công suất thực tế (N x 6) & tự lọc tài khoản bận")
    p_cap.add_argument("--verify-unchecked", action="store_true", help="Tự đăng nhập kiểm tra các tài khoản UNCHECKED đang rảnh")
    _add_common_pool_args(p_cap)

    p_kf = sub.add_parser("keyframes", help="Sinh song song Keyframes 00.png trên N tài khoản (N x 4 ảnh/đợt)")
    p_kf.add_argument("project_dir")
    p_kf.add_argument("--include-setups", action="store_true", help="Sinh thêm Master Location Plates vào assets/setups")
    p_kf.add_argument("--include-turnarounds", action="store_true", help="Sinh ảnh nhân vật góc 3/4 và toàn thân còn thiếu")
    p_kf.add_argument("--session-tag", default="pool_keyframes")
    p_kf.add_argument("--clear-halt", action="store_true",
                      help="Remove the machine-wide Muse halt (muse_halt.json, left by a CAPTCHA / verification page) "
                           "after clearing it on Muse; "
                           "unconfirmed keyframe sends stay withheld")
    p_kf.add_argument(
        "--release-unconfirmed", action="store_true",
        help="Release every unconfirmed keyframe send (unconfirmed_keyframes.json) so those images may be resent; "
             "use only after checking on Muse that the earlier generation is finished or dead",
    )
    p_kf.add_argument(
        "--release-unconfirmed-kf", action="append", default=[], metavar="KF_ID",
        help="Release the unconfirmed sends of one keyframe id (repeatable); same check on Muse first",
    )
    p_kf.add_argument("--no-ui-sync", action="store_true")
    _add_common_pool_args(p_kf)

    p_vid = sub.add_parser("videos", help="Sản xuất video hàng đợi động trên N tài khoản (N x 6 shots song song)")
    p_vid.add_argument("project_dir")
    p_vid.add_argument("--max-rounds", type=int, default=3)
    p_vid.add_argument("--auto-repair", action="store_true", default=True, help="Tự chữa prompt các lỗi kỹ thuật QC giữa các vòng")
    p_vid.add_argument("--no-auto-repair", dest="auto_repair", action="store_false", help="Tắt tự chữa tự động để Gemini tự sửa tay")
    p_vid.add_argument(
        "--takes", type=int, default=1,
        help="Independent takes per shot sent in parallel each round (a shot's manifest `takes` field overrides it)",
    )
    p_vid.add_argument(
        "--release-unconfirmed", action="store_true",
        help="Release every unconfirmed submission (batch sent, no result) so those shots may be resent; use only "
             "after checking on Muse that the earlier generation is finished or dead",
    )
    p_vid.add_argument(
        "--release-unconfirmed-shot", action="append", default=[], metavar="SHOT_ID",
        help="Release the unconfirmed submissions of one shot (repeatable); same check on Muse first",
    )
    p_vid.add_argument(
        "--unconfirmed-ttl-min", type=float, default=None,
        help="Minutes after which an unconfirmed submission is flagged EXPIRED_NEEDS_RECONCILE (it still blocks a "
             "resend until released; default env MUSE_UNCONFIRMED_TTL_MIN or 120)",
    )
    p_vid.add_argument("--session-tag", default="pool_videos")
    p_vid.add_argument("--clear-halt", action="store_true",
                       help="Remove the machine-wide Muse halt (muse_halt.json, left by a CAPTCHA / verification "
                            "page) after clearing it on Muse")
    p_vid.add_argument("--no-ui-sync", action="store_true")
    _add_common_pool_args(p_vid)

    return parser


HALTED_EXIT_CODE = 4


def _halt_publication(res) -> None:
    """Before exit 4: finish a pending locked publication (backoff, bounded window) and report its outcome
    (PUBLISHED / PENDING / HALT_PENDING_UNWRITTEN; ALREADY_HALTED when another run or process published it)."""
    if res.get("status") == "HALTED":
        res["halt_publication"] = send_halt.finish_publication() or "ALREADY_HALTED"


INTEGRITY_EXIT_CODE = 5


def _integrity_exit(res) -> int:
    clips = sorted({c for e in res.get("integrity_unpersisted") or [] for c in e.get("clips", [])})
    print(f"[!] INTEGRITY_UNPERSISTED: clip(s) {clips} failed their receipt SHA-256 and could be neither listed in "
          f"integrity_failed.json nor quarantined; the run stopped and the batch is UNCONFIRMED. Fix the batch dir "
          f"(permissions / disk), then reconcile by hand.", file=sys.stderr)
    return INTEGRITY_EXIT_CODE


def _halted_exit(res) -> int:
    print(send_halt.halted_line(res.get("halted")), file=sys.stderr)
    return HALTED_EXIT_CODE


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    engine = _build_engine(args)
    if getattr(engine, "lane", None) is not None:
        send_halt.set_lane_id(engine.lane.lane_id)
    only = _parse_csv_set(args.accounts)
    excl = _parse_csv_set(args.exclude_accounts)

    try:
        if args.subcommand == "capacity":
            res = engine.inspect_capacity(
                max_accounts=args.max_accounts,
                only_accounts=only,
                exclude_accounts=excl,
                auto_verify_unchecked=args.verify_unchecked,
                simulate=args.simulate,
            )
            if engine.lane is not None:
                res["lane"] = engine.lane.report()
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0 if res["granted_accounts"] > 0 else 2

        if args.subcommand == "keyframes":
            res = engine.run_keyframes(
                project_dir=Path(args.project_dir),
                max_accounts=args.max_accounts,
                only_accounts=only,
                exclude_accounts=excl,
                simulate=args.simulate,
                include_setups=bool(getattr(args, "include_setups", False)),
                include_turnarounds=args.include_turnarounds,
                session_tag=args.session_tag,
                clear_halt=args.clear_halt,
                release_unconfirmed=(True if args.release_unconfirmed else list(args.release_unconfirmed_kf)),
            )
            _halt_publication(res)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            if res["status"] == "HALTED":
                return _halted_exit(res)
            if res["status"] == "COMPLETED":
                return 0
            return 2 if res["status"] == "BLOCKED_NO_ACCOUNTS" else 1

        if args.subcommand == "videos":
            res = engine.run_videos(
                project_dir=Path(args.project_dir),
                max_accounts=args.max_accounts,
                only_accounts=only,
                exclude_accounts=excl,
                max_rounds=args.max_rounds,
                auto_repair=args.auto_repair,
                simulate=args.simulate,
                session_tag=args.session_tag,
                takes=args.takes,
                release_unconfirmed=(True if args.release_unconfirmed
                                     else list(args.release_unconfirmed_shot)),
                unconfirmed_ttl_min=args.unconfirmed_ttl_min,
                clear_halt=args.clear_halt,
            )
            _halt_publication(res)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            if res["status"] == "HALTED":
                return _halted_exit(res)
            if res["status"] == "INTEGRITY_UNPERSISTED":
                return _integrity_exit(res)
            if res["status"] == "COMPLETED":
                return 0
            return 2 if res["status"] == "BLOCKED_NO_ACCOUNTS" else 1

    except SessionConflictError as ce:
        print(f"[-] SESSION_CONFLICT: {ce}")
        return 3

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
