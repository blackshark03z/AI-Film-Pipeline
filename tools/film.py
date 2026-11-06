"""Generic film CLI over a Production Package (`films/<film_id>/`): new, validate, status."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.production.gates import evaluate_gates, summary  # noqa: E402
from film_pipeline.production.plan import plan_package  # noqa: E402
from film_pipeline.production.package import (  # noqa: E402
    SCRIPT_FILE, STAGE_FILES, FilmHeader, PackageError, load_package, save_header,
)


def _emit(payload: dict) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def scaffold(film_id: str, profile: str, root: Path, title: str | None) -> Path:
    target = root / film_id
    if target.exists() and any(target.iterdir()):
        raise PackageError(f"{target} is not empty; refusing to overwrite")
    header = FilmHeader(film_id=film_id, title=title or film_id, profile=profile)
    save_header(target, header)
    for name in STAGE_FILES.values():
        (target / name).write_text("{}\n", encoding="utf-8", newline="\n")
    if profile == "drama":
        (target / SCRIPT_FILE).write_text("", encoding="utf-8", newline="\n")
    (target / "media").mkdir(exist_ok=True)
    return target


def _narration(args, rest: list[str], parser) -> int:
    from film_pipeline.production.narration import build_package, status_report
    if args.verb in ("prepare", "resume", "finish"):  # thin wrappers: same arguments as tools/film_e2e.py
        sys.path.insert(0, str(ROOT / "tools"))
        import film_e2e
        forwarded = [args.verb, *rest]
        for flag, value in (("--db", args.db), ("--project-id", args.project_id), ("--project", args.project),
                            ("--out", args.out)):
            if value is not None:
                forwarded += [flag, str(value)]
        sys.argv = ["film_e2e.py", *forwarded]
        film_e2e.main()
        return 0
    if rest:
        parser.error(f"unrecognized arguments: {' '.join(rest)}")
    if args.verb == "import":
        if not args.project or not args.out:
            parser.error("narration import needs --project and --out")
        _emit(build_package(args.project, args.out, film_id=args.film_id, title=args.title,
                            language=args.language, refresh=args.refresh))
        return 0
    if not args.film:
        parser.error("narration status needs --film")
    pkg = load_package(args.film)
    if pkg.header.profile != "narration":
        raise PackageError(f"{args.film} is a {pkg.header.profile} package, not narration")
    report = status_report(pkg, args.db, args.project_id)
    _emit(report)
    return 1 if report["package"]["blocked"] or report.get("error") else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    new = actions.add_parser("new", help="scaffold an empty package")
    new.add_argument("film_id")
    new.add_argument("--profile", required=True, choices=["drama", "narration"])
    new.add_argument("--title")
    new.add_argument("--root", type=Path, default=ROOT / "films", help="directory holding film packages")
    for name, text in (("validate", "evaluate gates; exit 1 if any gate BLOCKs"),
                       ("status", "stages present, gates, counts")):
        sub = actions.add_parser(name, help=text)
        sub.add_argument("--film", required=True, type=Path)
    plan = actions.add_parser("plan", help="write prompts, start-frame still prompts, storyboard and gate3.json")
    plan.add_argument("--film", required=True, type=Path)
    plan.add_argument("--out", required=True, type=Path)
    plan.add_argument("--takes", type=Path, help="directory of reviewed <gid>.mp4 takes (marks end states verified)")
    plan.add_argument("--no-storyboard", action="store_true")
    plan.add_argument("--approve-storyboard", metavar="REVIEWER",
                      help="mark every rendered storyboard frame APPROVED by this reviewer (explicit; default PENDING)")
    imp = actions.add_parser("impact", help="what to redo when a versioned design changes")
    imp.add_argument("--film", required=True, type=Path)
    imp.add_argument("--design", required=True)
    cont = actions.add_parser("continuity", help="continuity bible: action/spatial/object/temporal/visual/emotional")
    cont.add_argument("--film", required=True, type=Path)
    cam = actions.add_parser("camera", help="camera & lighting plan: sizes, axis side, size runs, light consistency")
    cam.add_argument("--film", required=True, type=Path)
    narr = actions.add_parser("narration", help="narration profile over an E2E project (import, status, or delegate)")
    narr.add_argument("verb", choices=["import", "status", "prepare", "resume", "finish"])
    narr.add_argument("--project", type=Path, help="E2E project directory (import)")
    narr.add_argument("--out", type=Path, help="package directory to write (import)")
    narr.add_argument("--film-id")
    narr.add_argument("--title")
    narr.add_argument("--language", default="en")
    narr.add_argument("--refresh", action="store_true", help="rewrite story + shots of an existing package")
    narr.add_argument("--film", type=Path, help="narration package (status)")
    narr.add_argument("--db", type=Path)
    narr.add_argument("--project-id", help="exact Flow project ID")
    args, rest = parser.parse_known_args(argv)
    if args.action != "narration" and rest:
        parser.error(f"unrecognized arguments: {' '.join(rest)}")

    try:
        if args.action == "narration":
            return _narration(args, rest, parser)
        if args.action == "new":
            target = scaffold(args.film_id, args.profile, args.root, args.title)
            _emit({"created": str(target), "profile": args.profile})
            return 0
        pkg = load_package(args.film)
        if args.action == "impact":
            from film_pipeline.production.impact import affected_by
            try:
                _emit(affected_by(pkg, args.design).model_dump(mode="json"))
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 2
            return 0
        if args.action == "continuity":
            from film_pipeline.production.continuity import continuity_report
            pre, shots = pkg.typed.get("preprod"), pkg.typed.get("shots")
            if pre is None or shots is None:
                _emit({"error": "continuity needs a valid 03_preprod.json and 04_shots.json"})
                return 2
            report = continuity_report(pre, shots)
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "camera":
            from film_pipeline.production.camera import camera_report
            pre, shots = pkg.typed.get("preprod"), pkg.typed.get("shots")
            if pre is None or shots is None:
                _emit({"error": "camera needs a valid 03_preprod.json and 04_shots.json"})
                return 2
            report = camera_report(pre, shots)
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "plan":
            result = plan_package(pkg, args.out, takes_dir=args.takes, storyboard=not args.no_storyboard,
                                  approve_storyboard=args.approve_storyboard)
            record = result.record
            _emit({"out": str(args.out), "ok": result.ok, "problems": result.problems,
                   "generations": {g: {"verdict": v["verdict"], "words": v["words"]}
                                   for g, v in record["generations"].items()}})
            return 0 if result.ok else 1
        results = evaluate_gates(pkg)
        report = summary(results)
        if args.action == "validate":
            report["package_issues"] = pkg.issues
            report["blocked"] = report["blocked"] or bool(pkg.issues)
            _emit(report)
            return 1 if report["blocked"] else 0
        _emit({
            "film_id": pkg.header.film_id,
            "profile": pkg.header.profile,
            "stages_present": sorted(pkg.stages),
            "stages_missing": pkg.missing_stages,
            "stages_empty": sorted(k for k, v in pkg.stages.items() if not v),
            "script_scenes": len(pkg.script.scenes) if pkg.script else None,
            "package_issues": pkg.issues,
            "gates": {r.gate: r.status for r in results},
        })
        return 0
    except PackageError as exc:
        _emit({"error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
