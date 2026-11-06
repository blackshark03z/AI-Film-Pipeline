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
    ani = actions.add_parser("animatic", help="timed storyboard animatic (mp4 + srt + timing report), 0 credits")
    ani.add_argument("--film", required=True, type=Path)
    ani.add_argument("--out", type=Path, help="output directory (default: <film>/media)")
    ani.add_argument("--stills", type=Path, help="directory of approved start stills <gid>.png")
    ani.add_argument("--storyboard", type=Path, help="directory of plan storyboard frames <gid>.png")
    ani.add_argument("--audio", type=Path, help="directory of temp dialogue tracks <gid>.wav (silence if absent)")
    pln = actions.add_parser("planning", help="budget, schedule, risk register and rights ledger")
    pln.add_argument("--film", required=True, type=Path)
    tk = actions.add_parser("takes", help="take log: --register a rendered clip, or list the log")
    tk.add_argument("--film", required=True, type=Path)
    tk.add_argument("--register", metavar="GENERATION_ID")
    tk.add_argument("--clip", type=Path)
    tk.add_argument("--prompt", type=Path, help="the exact prompt text that was sent")
    tk.add_argument("--start-frame", type=Path)
    tk.add_argument("--route", default="start_frame+Khung hinh")
    tk.add_argument("--model", default="")
    tk.add_argument("--credits", type=float)
    rv = actions.add_parser("review", help="write dailies templates for new takes, or --ingest a filled review")
    rv.add_argument("--film", required=True, type=Path)
    rv.add_argument("--ingest", type=Path, help="filled review sheet (or bare TakeQc) JSON")
    rv.add_argument("--clips", type=Path, help="directory holding the take mp4s (enables autoqc warnings)")
    gn = actions.add_parser("generate", help="send payload + intent receipt for one generation (--dry-run: nothing is sent)")
    gn.add_argument("--film", required=True, type=Path)
    gn.add_argument("--gid", required=True, metavar="GENERATION_ID")
    gn.add_argument("--dry-run", action="store_true")
    gn.add_argument("--plan-out", type=Path, help="where the plan is (re)written (default <film>/media/plan)")
    gn.add_argument("--stills", type=Path, help="directory of approved start stills start_<gid>.png")
    gn.add_argument("--start-token", help="tok:<tail> of the start still uploaded to Flow (live only)")
    gn.add_argument("--backlog", type=Path, help="file holding the OWNER_GO_LIVE line (default: the loop backlog)")
    rt = actions.add_parser("retake", help="retake/pickup policy over the take log; --pickup GID starts a new shot version")
    rt.add_argument("--film", required=True, type=Path)
    rt.add_argument("--pickup", metavar="GENERATION_ID")
    rt.add_argument("--reason")
    rt.add_argument("--edits", type=Path, help="JSON object of ShotDecl fields to change in the new version")
    qcp = actions.add_parser("qc", help="validate a take QC record (JSON object or list) and print each verdict")
    qcp.add_argument("--record", required=True, type=Path)
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
        if args.action == "qc":
            from pydantic import ValidationError

            from film_pipeline.production.qc_model import TakeQc, verdict_report
            raw = json.loads(args.record.read_text(encoding="utf-8"))
            try:
                takes = [TakeQc.model_validate(item) for item in (raw if isinstance(raw, list) else [raw])]
            except ValidationError as exc:
                _emit({"ok": False, "error": [e["msg"] for e in exc.errors()]})
                return 2
            reports = [verdict_report(t) for t in takes]
            _emit({"ok": all(r["status"] == "ACCEPTED" for r in reports), "takes": reports})
            return 0 if all(r["status"] != "REJECTED" for r in reports) else 1
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
        if args.action == "animatic":
            from film_pipeline.production.animatic import build_animatic
            report = build_animatic(pkg, args.out, stills_dir=args.stills, storyboard_dir=args.storyboard,
                                    audio_dir=args.audio)
            _emit({k: report[k] for k in ("video", "subtitles", "planned_duration_s", "actual_duration_s", "ok",
                                          "findings")})
            return 0 if report["ok"] else 1
        if args.action == "takes":
            from film_pipeline.production import takes as tk_mod
            if args.register:
                missing = [f for f, v in (("--clip", args.clip), ("--prompt", args.prompt), ("--model", args.model),
                                          ("--credits", args.credits)) if v in (None, "")]
                if missing:
                    _emit({"error": f"--register needs {', '.join(missing)}"})
                    return 2
                known = {g.generation_id for g in pkg.typed["shots"].generations} if "shots" in pkg.typed else None
                try:
                    entry, created = tk_mod.register_take(
                        pkg.root, pkg.header.film_id, args.register, args.clip,
                        prompt_text=args.prompt.read_text(encoding="utf-8"), route=args.route, model=args.model,
                        credits=args.credits, start_frame=args.start_frame, known_generations=known,
                        shot_version=next((g.version for g in pkg.typed["shots"].generations
                                           if g.generation_id == args.register), 1) if "shots" in pkg.typed else 1)
                except (ValueError, OSError) as exc:
                    _emit({"error": str(exc)})
                    return 2
                _emit({"created": created, "take": entry.model_dump(mode="json")})
                return 0
            log = tk_mod.load_log(pkg.root, pkg.header.film_id)
            _emit({"film_id": log.film_id, "takes": [t.model_dump(mode="json") for t in log.takes]})
            return 0
        if args.action == "generate":
            from film_pipeline.production.generate import generate
            try:
                done = generate(pkg, args.gid, dry_run=args.dry_run, plan_out=args.plan_out, stills_dir=args.stills,
                                start_token=args.start_token, backlog=args.backlog)
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 2
            _emit(done)
            if args.dry_run:
                return 0
            return 0 if done["sent"] and done.get("manifest_result") == "PASSED" else 1
        if args.action == "retake":
            from film_pipeline.production import retake as rt_mod
            from film_pipeline.production import takes as tk_mod
            if "shots" not in pkg.typed:
                _emit({"error": "retake needs a valid 04_shots.json"})
                return 2
            if args.pickup:
                if not (args.reason and args.edits):
                    _emit({"error": "--pickup needs --reason and --edits"})
                    return 2
                try:
                    _emit(rt_mod.apply_pickup(pkg.root, pkg.header.film_id, args.pickup, args.reason,
                                              json.loads(args.edits.read_text(encoding="utf-8"))))
                except ValueError as exc:
                    _emit({"error": str(exc)})
                    return 2
                return 0
            report = rt_mod.retake_report(tk_mod.load_log(pkg.root, pkg.header.film_id), pkg.typed["shots"])
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "review":
            from film_pipeline.production import takes as tk_mod
            if args.ingest:
                from pydantic import ValidationError
                try:
                    _emit(tk_mod.ingest_review(pkg.root, pkg.header.film_id,
                                               json.loads(args.ingest.read_text(encoding="utf-8"))))
                except ValidationError as exc:
                    _emit({"error": [e["msg"] for e in exc.errors()]})
                    return 2
                except (ValueError, KeyError) as exc:
                    _emit({"error": str(exc.args[0] if exc.args else exc)})
                    return 2
                return 0
            written = tk_mod.write_dailies(pkg, pkg.root, clips_dir=args.clips)
            _emit({"written": written, "pending": [t.take_id for t in tk_mod.load_log(pkg.root, pkg.header.film_id).takes
                                                   if t.status in ("GENERATED", "INCOMPLETE")]})
            return 0
        if args.action == "planning":
            from film_pipeline.production.planning import planning_report
            if "shots" not in pkg.typed:
                _emit({"error": "planning needs a valid 04_shots.json"})
                return 2
            report = planning_report(pkg)
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
            blocked_by_planning = False
            if pkg.header.profile == "drama" and "preprod" in pkg.typed and "shots" in pkg.typed:
                from film_pipeline.production.planning import planning_report
                plan = planning_report(pkg)
                report["planning"] = {"budget": {k: plan["budget"][k] for k in (
                    "generations", "expected_credits", "high_credits", "cap_credits", "owner_estimate")},
                    "risk_summary": plan["risk_summary"], "legal": plan["legal"]["status"],
                    "owner_decisions": plan["legal"]["owner_decisions"], "issues": plan["issues"]}
                blocked_by_planning = not plan["ok"]
            report["blocked"] = report["blocked"] or bool(pkg.issues) or blocked_by_planning
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
