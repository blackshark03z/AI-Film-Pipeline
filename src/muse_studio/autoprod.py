#!/usr/bin/env python3
"""
Muse Studio Zero-Talk Autoprod CLI
Đưa 1 file kịch bản (.txt, .md, .fountain, .srt) -> tự đọc hiểu, phân rã, thiết kế Story Bible,
dàn dựng DOP, sinh Keyframes, chạy Pool đa tài khoản (tự né tài khoản đang bận ở session khác),
tự sửa prompt khi trượt 5-Gate QC, và xuất Master 1080p (-16 LUFS) + SRT rời.

Chạy độc lập:
  python -m muse_studio.autoprod path/to/script.txt [--preset drama_35mm] [--project-dir ...]

Real sends: without --simulate autoprod stops after stage 2 (status REFUSED_USE_POOL_RUNNER, exit 2); keyframes and
videos are sent only by `python -m muse_studio.pool_runner keyframes|videos <project_dir>`.
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Optional

try:
    from .core.account_manager import AccountManager
    from .core.autoprod_orchestrator import AutoprodOrchestrator, SessionConflictError
    from .core.config import ACCOUNTS_FILE, PROFILES_DIR
    from .core.script_ingestor import DIRECTOR_PRESETS
except ImportError:
    from core.account_manager import AccountManager
    from core.autoprod_orchestrator import AutoprodOrchestrator, SessionConflictError
    from core.config import ACCOUNTS_FILE, PROFILES_DIR
    from core.script_ingestor import DIRECTOR_PRESETS


def build_autoprod_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Muse Zero-Talk Autoprod: Kịch bản thô -> Final Master 1080p tự động"
    )
    p.add_argument("input", help="Đường dẫn file kịch bản / truyện / .srt đầu vào")
    p.add_argument("--project-dir", default=None, help="Thư mục dự án đích (tự tạo thư mục cô lập nếu bỏ trống)")
    p.add_argument(
        "--preset",
        default="drama_35mm",
        choices=sorted(DIRECTOR_PRESETS.keys()),
        help="Preset đạo diễn mặc định (không cần mô tả dài dòng)",
    )
    p.add_argument(
        "--audio-mode",
        default=None,
        choices=["native_drama", "hybrid_narrated"],
        help="Ghi đè chế độ âm lời của preset nếu cần",
    )
    p.add_argument("--max-rounds", type=int, default=3, help="Số vòng retry tối đa kèm tự sửa prompt")
    p.add_argument("--simulate", action="store_true", help="Chạy mô phỏng offline kiểm thử toàn chuỗi")
    p.add_argument("--no-llm", action="store_true", help="Dùng bộ phân tích kịch bản tất định nội bộ (không gọi API LLM)")
    p.add_argument("--cinematic-cutaways", action="store_true", help="Chèn cảnh phản ứng im lặng và đặc tả đạo cụ")
    p.add_argument("--stop-after-casting", action="store_true", help="Tạm dừng sau khi sinh Keyframes để duyệt mặt diễn viên")
    p.add_argument("--exclude-accounts", default="", help="Danh sách account_id phẩy cách cần chừa lại cho session khác")
    p.add_argument("--bgm", default=None, help="File nhạc nền tùy chọn")
    p.add_argument("--room-tone", default=None, help="File room tone tùy chọn")
    p.add_argument("--session-tag", default="autoprod", help="Nhãn định danh phiên chạy cho .autoprod.lock")
    p.add_argument("--no-ui-sync", action="store_true", help="Không đồng bộ trạng thái sang data/projects của Web UI")
    p.add_argument("--accounts-file", default=None, help="Đường dẫn accounts.json tùy chỉnh (cô lập hoàn toàn)")
    p.add_argument("--profiles-dir", default=None, help="Đường dẫn thư mục profiles tùy chỉnh (cô lập hoàn toàn)")
    return p


def _default_project_dir_for(input_path: Path) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", input_path.stem).strip("_").upper() or "FILM"
    return input_path.resolve().parent / f"{slug}_AUTOPROD"


def run_from_namespace(args: argparse.Namespace) -> int:
    in_path = Path(args.input)
    proj_dir = Path(args.project_dir) if args.project_dir else _default_project_dir_for(in_path)
    excl = {x.strip() for x in (args.exclude_accounts or "").split(",") if x.strip()}

    storage_f = Path(args.accounts_file) if getattr(args, "accounts_file", None) else ACCOUNTS_FILE
    profiles_d = Path(args.profiles_dir) if getattr(args, "profiles_dir", None) else PROFILES_DIR
    mgr = AccountManager(storage_file=storage_f, profiles_dir=profiles_d)

    orch = AutoprodOrchestrator(
        account_manager=mgr,
        sync_ui=not getattr(args, "no_ui_sync", False),
    )
    try:
        res = orch.run(
            input_path=in_path,
            project_dir=proj_dir,
            preset=args.preset,
            audio_mode=args.audio_mode,
            max_rounds=args.max_rounds,
            simulate=args.simulate,
            use_llm=not args.no_llm,
            stop_after_casting=args.stop_after_casting,
            exclude_accounts=excl,
            bgm_path=Path(args.bgm) if args.bgm else None,
            room_tone_path=Path(args.room_tone) if args.room_tone else None,
            session_tag=args.session_tag,
            cinematic_cutaways=bool(getattr(args, "cinematic_cutaways", False)),
        )
    except SessionConflictError as ce:
        print(f"[-] SESSION_CONFLICT: {ce}")
        return 3

    print(json.dumps(res, indent=2, ensure_ascii=False))
    status = res.get("status")
    if status in ("COMPLETED", "PAUSED_FOR_CASTING_REVIEW"):
        return 0
    if status in ("BLOCKED_NO_ACCOUNTS", "REFUSED_USE_POOL_RUNNER"):
        return 2
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_autoprod_parser()
    args = parser.parse_args(argv)
    return run_from_namespace(args)


if __name__ == "__main__":
    raise SystemExit(main())
