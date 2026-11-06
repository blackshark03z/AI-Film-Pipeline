"""Prepare, inspect, continue and finish one operator-managed local film."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.e2e import finish, prepare, resume, status, verify_package  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    new = actions.add_parser("prepare", help="copy and hash source media; draft editable shot windows")
    new.add_argument("--audio", required=True, type=Path)
    new.add_argument("--srt", required=True, type=Path)
    new.add_argument("--start", required=True, type=float, help="source-audio start time in seconds")
    new.add_argument("--end", required=True, type=float, help="source-audio end time in seconds")
    new.add_argument("--out", required=True, type=Path)
    new.add_argument("--image-profile", help="GPM profile email that produced the ChatGPT reference images")
    new.add_argument("--image-tab", type=int, help="1-based browser tab holding the ChatGPT image chat")
    new.add_argument("--flow-account-alias", help="local label for the Flow account, set once at prepare; "
                     "use a new one when the project moves to a different Flow account so uploads/media "
                     "from another account are never reused")
    inspect = actions.add_parser("status", help="show review and selected-take gaps")
    targets = inspect.add_mutually_exclusive_group(required=True)
    targets.add_argument("--project", type=Path)
    targets.add_argument('--package', type=Path, help='verify a relocated delivery directory without the runtime')
    inspect.add_argument("--db", type=Path)
    inspect.add_argument("--project-id", help="exact Flow project ID")
    run = actions.add_parser("resume", help="lock the reviewed plan and reconcile runtime evidence")
    run.add_argument("--project", required=True, type=Path)
    run.add_argument("--db", type=Path, help="defaults to <project>/runtime.sqlite")
    run.add_argument("--project-id", required=True, help="exact Flow project ID")
    run.add_argument("--references", type=Path, help="JSON receipts for exact per-shot ChatGPT reference images")
    run.add_argument("--review", type=Path, help="Owner review manifest exported by status and filled after playback")
    run.add_argument("--flow-profile", type=Path, help="existing Flow browser profile directory; enables explicit shots")
    run.add_argument("--shot", action="append", help="one shot ID to dispatch; repeat, requires --flow-profile")
    run.add_argument('--repair', type=Path, help='changed intent JSON bound to an exact Owner-rejected shot')
    deliver = actions.add_parser("finish", help="render human-selected, QC-approved Flow takes")
    deliver.add_argument("--project", required=True, type=Path)
    deliver.add_argument("--db", type=Path, help="defaults to <project>/runtime.sqlite")
    deliver.add_argument("--project-id", required=True, help="exact Flow project ID")
    deliver.add_argument('--trim', action='append', default=[], metavar='SHOT_ID=SECONDS',
                         help='source start offset; repeat to preserve the useful action within each shot')
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.audio, args.srt, args.start, args.end, args.out,
                         image_profile=args.image_profile, image_tab_index=args.image_tab,
                         flow_account_alias=args.flow_account_alias)
    elif args.action == "status":
        if args.package:
            if args.db or args.project_id:
                parser.error('--package does not use a database or Flow project ID')
            result = verify_package(args.package)
        else:
            result = status(args.project, args.db, args.project_id)
    elif args.action == "resume":
        db = args.db or args.project / "runtime.sqlite"
        result = resume(args.project, db, args.project_id, args.references, args.review,
                        args.flow_profile, args.shot, args.repair)
    else:
        offsets = {}
        for value in args.trim:
            try:
                shot_id, seconds = value.split('=', 1)
                if shot_id in offsets:
                    parser.error('duplicate --trim shot ID')
                offsets[shot_id] = float(seconds)
            except ValueError:
                parser.error('--trim must be SHOT_ID=SECONDS')
        result = finish(args.project, args.db or args.project / "runtime.sqlite", args.project_id, offsets)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('result') == 'FAIL':
        raise SystemExit(1)


if __name__ == "__main__":
    main()
