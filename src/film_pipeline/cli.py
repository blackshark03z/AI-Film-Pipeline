"""Generic film CLI over a Production Package (`films/<film_id>/`): new, validate, status."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if (ROOT / "src").is_dir() and str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
DEFAULT_FILMS_DIR = (ROOT / "films") if (ROOT / "films").is_dir() else (Path.cwd() / "films")

from film_pipeline.production.gates import evaluate_gates, summary  # noqa: E402
from film_pipeline.production.plan import plan_package  # noqa: E402
from film_pipeline.production.package import (  # noqa: E402
    SCRIPT_FILE, STAGE_FILES, FilmHeader, PackageError, load_package, save_header,
)


GENERATORS_FILE_HELP = ("JSON list of {role: video+audio|image|voice|music, name, model, settings}: what each generator made "
                        "(instead of --generators)")


def _emit(payload: dict) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _generators(args):
    """The generator input of titles / versions / deliver: the --generators text, or the records of --generators-file."""
    if args.generators_file is None:
        return args.generators
    if args.generators:
        raise ValueError("use --generators or --generators-file, not both")
    from film_pipeline.production.generators import load_generators_file
    return load_generators_file(args.generators_file)


def scaffold(film_id: str, profile: str, root: Path, title: str | None, *, portrait_9x16: bool = False) -> Path:
    target = root / film_id
    if target.exists() and any(target.iterdir()):
        raise PackageError(f"{target} is not empty; refusing to overwrite")
    header = FilmHeader(film_id=film_id, title=title or film_id, profile=profile, portrait_9x16=portrait_9x16,
                        qc_evidence_version=2, defaults_version=2)
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


def _motion(args, pkg) -> int:
    """`motion`: exit 0 PASS, 1 FLAG (findings for the reviewer), 2 error."""
    from film_pipeline.drama import trajectory as tj
    shots = pkg.typed.get("shots")
    decl = next((g for g in shots.generations if g.generation_id == args.gid), None) if shots is not None else None
    if decl is None:
        _emit({"error": f"unknown generation {args.gid!r}"})
        return 2
    if decl.tracked is None:
        _emit({"error": f"{args.gid} has no `tracked` motion in 04_shots.json"})
        return 2
    if not args.clip.is_file():
        _emit({"error": f"clip not found: {args.clip}"})
        return 2
    acts = [p for p in decl.choreography.phases if p.kind == "ACTION"]
    phase = next((p for p in acts if p.motion), acts[0] if acts else None)
    if phase is None:
        _emit({"error": f"{args.gid} has no ACTION phase"})
        return 2
    window = (phase.start_s, phase.end_s)
    t = decl.tracked
    try:
        curve = tj.motion_curve(args.clip, t.roi, t.axis)
    except ValueError as exc:
        _emit({"error": str(exc)})
        return 2
    verdict = tj.judge_motion(curve, direction=t.direction, action=window)
    if args.plot:
        tj.plot_curve(curve, window, args.plot)
    _emit({"gid": args.gid, "clip": str(args.clip), "verdict": "FLAG" if verdict["findings"] else "PASS",
           "note": "a measurement for the reviewer, not an acceptance of the take", "tracked": t.model_dump(),
           "action_window": list(window), "findings": verdict["findings"], "peak_t": verdict["peak_t"],
           "peak": verdict["peak"], "final": verdict["final"], "curve": verdict["curve"],
           **({"plot": str(args.plot)} if args.plot else {})})
    return 1 if verdict["findings"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    new = actions.add_parser("new", help="scaffold an empty package")
    new.add_argument("film_id")
    new.add_argument("--profile", required=True, choices=["drama", "narration"])
    new.add_argument("--title")
    new.add_argument("--root", type=Path, default=DEFAULT_FILMS_DIR, help="directory holding film packages")
    new.add_argument("--portrait-9x16", action="store_true", help="enable 9:16 portrait delivery in film.json (default: 16:9 only)")
    for name, text in (("validate", "evaluate gates; exit 1 if any gate BLOCKs"),
                       ("status", "stages present, gates, counts")):
        sub = actions.add_parser(name, help=text)
        sub.add_argument("--film", required=name != "status", type=Path)
        if name == "validate":
            sub.add_argument("--sync-gates", action="store_true",
                             help="sync evaluated gate statuses into film.json['gates'] when safe")
        if name == "status":
            sub.add_argument("--all", nargs="?", const=DEFAULT_FILMS_DIR, type=Path, metavar="FILMS_DIR",
                             help="one row per package under FILMS_DIR (default: films/): gates, credits, usable seconds, retake rate, next action")
            sub.add_argument("--package", type=Path, help="restore check of a delivery/ archive, wherever it was copied to: every hash, the package, the disclosure, missing dependencies")
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
    gen_r = actions.add_parser("generability", help="rate each shot GREEN/AMBER/RED for the video model, with findings and drafts")
    gen_r.add_argument("--film", required=True, type=Path)
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
    tk.add_argument("--merge-from", metavar="GIT_REF", help="union a shard branch's takes/index.json and takes/send_log.jsonl "
                    "into this checkout (same take_id with different content = error); reports a 04_shots.json conflict")
    mo = actions.add_parser("motion", help="trajectory QC: measure a tracked prop's travel in a take (a measurement for the reviewer, not an acceptance)")
    mo.add_argument("--film", required=True, type=Path)
    mo.add_argument("--gid", required=True, metavar="GENERATION_ID")
    mo.add_argument("--clip", required=True, type=Path)
    mo.add_argument("--plot", type=Path, help="write the displacement curve as a PNG")
    rv = actions.add_parser("review", help="write dailies templates for new takes, or --ingest a filled review")
    rv.add_argument("--film", required=True, type=Path)
    rv.add_argument("--ingest", type=Path, help="filled review sheet (or bare TakeQc) JSON")
    rv.add_argument("--supplement", metavar="TAKE_ID",
                    help="write the relation-questions sheet for an already-reviewed take (interaction contract on)")
    rv.add_argument("--clips", type=Path, help="directory holding the take mp4s (enables autoqc warnings)")
    gn = actions.add_parser("generate", help="send payload + intent receipt for one generation (--dry-run: nothing is sent)")
    gn.add_argument("--film", required=True, type=Path)
    gn.add_argument("--gid", required=True, metavar="GENERATION_ID")
    gn.add_argument("--dry-run", action="store_true")
    gn.add_argument("--plan-out", type=Path, help="where the plan is (re)written (default <film>/media/plan)")
    gn.add_argument("--stills", type=Path, help="directory of approved start stills start_<gid>.png")
    gn.add_argument("--start-token", help="tok:<tail> of the start still uploaded to Flow (live only)")
    gn.add_argument("--end-token", help="tok:<tail> of the end still uploaded to Flow (live only; shots with end_frame)")
    gn.add_argument("--backlog", type=Path, help="file holding the OWNER_GO_LIVE line (default: the loop backlog)")
    gn.add_argument("--no-auto-resend", action="store_true",
                    help="do not resend once after a provider failure (P18-03; default: resend once)")
    gn.add_argument("--critic", action="store_true",
                    help="run blocking PreSendCritic check on this generation before submitting")
    gn.add_argument("--no-critic", action="store_true",
                    help="skip advisory PreSendCritic warnings on generate")
    mg = actions.add_parser("muse", help="browser-assisted Muse shot handoff; no automatic generation")
    mg.add_argument("verb", choices=["prepare", "dispatch", "ingest"])
    mg.add_argument("--film", required=True, type=Path)
    mg.add_argument("--gid")
    mg.add_argument("--condition-camera", action="store_true", help="render the declared camera plan as Muse prompt text")
    mg.add_argument("--request", type=Path, help="immutable request directory returned by prepare")
    mg.add_argument("--backlog", type=Path, help="OWNER_GO_LIVE file required by dispatch")
    mg.add_argument("--clip", type=Path, help="actual downloaded video for ingest")
    mg.add_argument("--response", type=Path, help="observed Muse response JSON for ingest")
    rc = actions.add_parser("reconcile", help="resolve one existing Flow send without submitting another job")
    rc.add_argument("--film", required=True, type=Path)
    rc.add_argument("--take-id", required=True)
    fi = actions.add_parser("finish", help="run/resume local finishing from a locked EDL; never accepts for the Owner")
    fi.add_argument("--film", required=True, type=Path)
    fi.add_argument("--dry-run", action="store_true")
    fi_p = fi.add_mutually_exclusive_group()
    fi_p.add_argument("--portrait", dest="portrait_override", action="store_true", help="include 9:16 portrait rendering & delivery")
    fi_p.add_argument("--no-portrait", dest="portrait_override", action="store_false", help="ship 16:9 master only (skip 9:16)")
    fi_p.set_defaults(portrait_override=None)
    fi.add_argument("--jobs", type=int, default=None, help="parallel chunk render workers")
    fi.add_argument("--hwaccel", action="store_true", default=None, help="use GPU h264_nvenc when available")
    st = actions.add_parser("stills", help="start stills: list their state, --register an image made elsewhere, --approve it")
    st.add_argument("--film", required=True, type=Path)
    st.add_argument("--register", metavar="GENERATION_ID|end:GENERATION_ID")
    st.add_argument("--image", type=Path, help="the PNG/JPEG to register for --register")
    st.add_argument("--source", default="", help='where the image came from, e.g. "ChatGPT GPM tab 2"')
    st.add_argument("--credits", type=float, default=0.0)
    st.add_argument("--approve", metavar="GENERATION_ID|end:GENERATION_ID")
    st.add_argument("--by", help="reviewer name for --approve or --bind-matching")
    st.add_argument("--bind-matching", action="store_true", help="copy approved stills onto unapproved shots with identical prompt_sha256")
    st.add_argument("--dry-run", action="store_true", help="preview --bind-matching without modifying 03_preprod.json")
    st.add_argument("--tighten", metavar="GENERATION_ID", help="crop the current start still away from the off-frame listener and register it (unapproved)")
    st.add_argument("--side", choices=("left", "right"), help="frame side of the off-frame listener for --tighten (default: from the shot)")
    st.add_argument("--scale", type=float, default=0.85, help="--tighten box size, 0.80-0.95 (default 0.85)")
    st.add_argument("--y", type=float, default=None, help="--tighten box top as a fraction of the height (default: centred)")
    rt = actions.add_parser("retake", help="retake/pickup policy over the take log; --pickup GID starts a new shot version")
    rt.add_argument("--film", required=True, type=Path)
    rt.add_argument("--pickup", metavar="GENERATION_ID")
    rt.add_argument("--reason")
    rt.add_argument("--edits", type=Path, help="JSON object of ShotDecl fields to change in the new version")
    ct = actions.add_parser("cut", help="check the EDL (05_edit.json) against the take log; --render writes the assembly (hard cuts, dissolves, J/L cuts)")
    ct.add_argument("--film", required=True, type=Path)
    ct.add_argument("--render", action="store_true", help="render with ffmpeg (default: check and print the timeline)")
    ct.add_argument("--out", type=Path, help="output mp4 (default <film>/media/cut/rough_cut.mp4)")
    ct.add_argument("--clips", type=Path, help="directory holding the take mp4s (default <film>/media/takes)")
    ct.add_argument("--accepted-only", action="store_true", help="a take nobody accepted blocks instead of warning")
    ct.add_argument("--color", action="store_true", help="apply the colour match and look of color/color.json (film.py grade)")
    ct.add_argument("--jobs", type=int, default=None, help="parallel chunk render workers")
    ct.add_argument("--hwaccel", action="store_true", default=None, help="use GPU h264_nvenc when available")
    gr = actions.add_parser("grade", help="colour matching: per-scene reference, per-shot gains, before/after deviation; --render writes the matched cut")
    gr.add_argument("--film", required=True, type=Path)
    gr.add_argument("--clips", type=Path, help="directory holding the take mp4s (default <film>/media/takes)")
    gr.add_argument("--render", action="store_true", help="also render the cut with the corrections and the look")
    gr.add_argument("--out", type=Path, help="matched cut (default <film>/media/cut/graded_cut.mp4)")
    gr.add_argument("--jobs", type=int, default=None, help="parallel chunk render workers")
    gr.add_argument("--hwaccel", action="store_true", default=None, help="use GPU h264_nvenc when available")
    tt = actions.add_parser("titles", help="credits card, dialogue cues, EN/VI sidecar SRTs, reframe check; --render writes the cut with them")
    tt.add_argument("--film", required=True, type=Path)
    tt.add_argument("--clips", type=Path, help="directory holding the take mp4s (default <film>/media/takes)")
    tt.add_argument("--langs", default="en,vi", help="sidecar languages (default en,vi)")
    tt.add_argument("--generators", default="", help="generator line of the AI credit, e.g. 'Google Flow Omni 1.1 Flash'")
    tt.add_argument("--generators-file", type=Path, help=GENERATORS_FILE_HELP)
    tt.add_argument("--render", action="store_true", help="also render the cut with credits, burned-in cues and reframes")
    tt.add_argument("--out", type=Path, help="titled cut (default <film>/media/cut/titled_cut.mp4)")
    tt.add_argument("--color", action="store_true", help="also apply the colour match of color/color.json")
    tt.add_argument("--clean-copy", action="store_true",
                    help="with --render: also render <out>.clean.mp4 with no burned cues (versions re-lays the cues for 9:16)")
    tt.add_argument("--jobs", type=int, default=None, help="parallel chunk render workers")
    tt.add_argument("--hwaccel", action="store_true", default=None, help="use GPU h264_nvenc when available")
    mq = actions.add_parser("mastercheck", help="technical QC of a rendered master (black/freeze/duplicate frames, format, loudness, clipping, sync, colour, faststart) -> qc/master_qc.json")
    mq.add_argument("--film", required=True, type=Path)
    dc = actions.add_parser("dialoguecheck", help="advisory STT check that the actors said the scripted lines (Vosk + offline faster-whisper, en only) -> qc/dialogue_stt.json")
    dc.add_argument("--film", required=True, type=Path)
    dc.add_argument("--engine", choices=["auto", "vosk", "faster-whisper"], default=None,
                    help="STT engine mode (default: auto = Vosk fast pass + offline faster-whisper verification)")
    mq.add_argument("--video", type=Path, help="the master (default <film>/media/cut/mixed.mp4)")
    mq.add_argument("--cut-report", type=Path, help="the .cut.json holding the planned clock (default: next to the video, else media/cut/rough_cut.cut.json)")
    vs = actions.add_parser("versions", help="thumbnail candidates, metadata draft with AI disclosure, and opt-in 9:16 version -> versions/ (nothing is published)")
    vs.add_argument("--film", required=True, type=Path)
    vs.add_argument("--video", type=Path, help="the 16:9 master (default <film>/media/cut/mixed.mp4)")
    vs.add_argument("--cut-report", type=Path, help="the .cut.json holding the planned clock (default: next to the video, else media/cut/rough_cut.cut.json)")
    vs.add_argument("--portrait-source", type=Path, help="clean cut (no burned-in cues) with the master's clock and sound, cropped instead of the master")
    vs.add_argument("--generators", default="", help="generator line of the AI disclosure, e.g. 'Google Flow Omni 1.1 Flash'")
    vs.add_argument("--generators-file", type=Path, help=GENERATORS_FILE_HELP)
    vs_p = vs.add_mutually_exclusive_group()
    vs_p.add_argument("--portrait", dest="portrait_override", action="store_true", help="render 9:16 portrait version")
    vs_p.add_argument("--no-portrait", dest="portrait_override", action="store_false", help="skip 9:16 portrait version (16:9 only)")
    vs_p.set_defaults(portrait_override=None)
    vs.add_argument("--jobs", type=int, default=None, help="parallel chunk render workers")
    vs.add_argument("--hwaccel", action="store_true", default=None, help="use GPU h264_nvenc when available")
    lg = actions.add_parser("ledger", help="learnings ledger of a film (ledger.json): observation until a second film shows it again")
    lg.add_argument("--film", required=True, type=Path)
    lg.add_argument("--add", metavar="TEXT", help="record a learning (needs --ref)")
    lg.add_argument("--area", default="", help="stage or category the learning is about")
    lg.add_argument("--ref", help="where the evidence can be checked: a file, commit or take id")
    lg.add_argument("--replicate", metavar="LEARNING_ID", help="add evidence from another film (needs --from-film and --ref)")
    lg.add_argument("--from-film", help="film_id of the film that shows the learning again")
    la = actions.add_parser("ledger-adjust", help="audited money adjustments & scene balance checkpoints (takes/adjustments.json)")
    la.add_argument("--film", required=True, type=Path)
    la.add_argument("--add-adjustment", action="store_true", help="record a delta adjustment (needs --delta, --reason, --evidence, --by)")
    la.add_argument("--delta", type=float)
    la.add_argument("--unit", default="credits")
    la.add_argument("--reason", default="")
    la.add_argument("--evidence", default="")
    la.add_argument("--by", default="")
    la.add_argument("--checkpoint-scene", metavar="SCENE_ID", help="record Flow balance checkpoint at scene start/end")
    la.add_argument("--boundary", choices=["start", "end"], default="end")
    la.add_argument("--account", default="")
    la.add_argument("--observed-balance", type=float)
    la.add_argument("--note", default="")
    dv = actions.add_parser("deliver", help="delivery archive: marked masters (AI disclosure, optional C2PA), sidecars, thumbnails, metadata, QC, rights, package JSON, MANIFEST with hashes -> delivery/")
    dv.add_argument("--film", required=True, type=Path)
    dv.add_argument("--video", type=Path, help="the 16:9 master (default <film>/media/cut/mixed.mp4)")
    dv.add_argument("--cut-report", type=Path, help="the .cut.json of the master (default: next to the video, else media/cut/rough_cut.cut.json)")
    dv.add_argument("--generators", default="", help="generator line of the disclosure, e.g. 'Google Flow Omni 1.1 Flash' (';' between several)")
    dv.add_argument("--generators-file", type=Path, help=GENERATORS_FILE_HELP)
    dv.add_argument("--c2pa-cert", type=Path, help="PEM certificate chain for C2PA signing (with --c2pa-key)")
    dv.add_argument("--c2pa-key", type=Path, help="PEM private key for C2PA signing")
    dv.add_argument("--accept", metavar="NAME", help="record the Owner's acceptance of the current delivery (gates 1-5 must pass); builds nothing")
    dv_p = dv.add_mutually_exclusive_group()
    dv_p.add_argument("--portrait", dest="portrait_override", action="store_true", help="require & ship 9:16 version")
    dv_p.add_argument("--no-portrait", dest="portrait_override", action="store_false", help="ship 16:9 master only")
    dv_p.set_defaults(portrait_override=None)
    lk = actions.add_parser("lock", help="picture lock: status and dirty post/delivery items; --lock freezes the cut")
    lk.add_argument("--film", required=True, type=Path)
    lk.add_argument("--lock", action="store_true", help="freeze the cut (every take accepted, no BLOCK at a cut)")
    lk.add_argument("--by", help="who locks the picture (required with --lock)")
    lk.add_argument("--reason", default="")
    lk.add_argument("--clips", type=Path, help="directory holding the take mp4s (default <film>/media/takes)")
    mx = actions.add_parser("mix", help="audio stems (dialogue, ambience, sfx, music), ducked mix, -14 LUFS / -1 dBTP master of a rendered cut")
    mx.add_argument("--film", required=True, type=Path)
    mx.add_argument("--cut", type=Path, help="rendered cut mp4 with its .cut.json (default <film>/media/cut/rough_cut.mp4)")
    mx.add_argument("--out", type=Path, help="mixed mp4 (default <film>/media/cut/mixed.mp4)")
    mx.add_argument("--stems", type=Path, help="stem directory (default <film>/audio/stems)")
    mx.add_argument("--engine", type=Path, help="delegate the final mix/master to the AutoEdit v2 post engine in this "
                    "directory (default: env AFP_POST_ENGINE_DIR; unset = AFP's own mix)")
    sn = actions.add_parser("sounds", help="rights check of the sound assets the mix uses + music cue sheet; --record registers an asset")
    sn.add_argument("--film", required=True, type=Path)
    sn.add_argument("--record", metavar="ASSET", help="path under the film, e.g. audio/music/theme.wav (hash is taken from the file)")
    sn.add_argument("--kind", choices=["music", "sfx"])
    sn.add_argument("--license", dest="license_id")
    sn.add_argument("--source-url", default="")
    sn.add_argument("--status", default="pending", choices=["cleared", "pending", "restricted", "unknown"])
    sn.add_argument("--attribution", default="")
    sn.add_argument("--note", default="")
    sn.add_argument("--usage", action="append", default=[], metavar="START:END", help="usage range in seconds, END may be empty")
    fl = actions.add_parser("foley", help="synthesize offline-cleared foley/sfx WAVs from assets/sfx_catalog.json and register sound_rights")
    fl.add_argument("--film", required=True, type=Path)
    fl.add_argument("--ids", default="", help="comma-separated catalog ids to synthesize (default: match 04_shots.sfx)")
    fl.add_argument("--all", action="store_true", help="synthesize every entry in assets/sfx_catalog.json")
    fl.add_argument("--list", action="store_true", help="list available catalog ids without writing files")
    tr = actions.add_parser("triage", help="advisory pre-dailies scanner (edge intrusion, corner mark, R44F stability, speech trim hint)")
    tr.add_argument("--film", required=True, type=Path)
    tr.add_argument("--take-id", required=True)
    tr.add_argument("--clips", type=Path, help="directory holding take clips (default <film>/media/takes)")
    ap = actions.add_parser("agentic-plan", help="compute DAG waves, pre-send critic report, incremental scene conform status, and CP1-CP3 checkpoints")
    ap.add_argument("--film", required=True, type=Path)
    ap.add_argument("--plan-dir", type=Path, help="plan output directory holding compiled prompts (default <film>/media/plan)")
    ap.add_argument("--json-out", type=Path, help="optional path OUTSIDE <film> to write JSON report")
    ap.add_argument("--lookahead", type=int, default=0, help="optimistic lookahead hops over clean GENERATED takes into speculative_frontier")
    sa = actions.add_parser("setup-anchors", help="suggest or apply independent start-still anchors to shorten deep sequential DAG chains")
    sa.add_argument("--film", required=True, type=Path)
    sa.add_argument("--max-depth", type=int, default=4, help="maximum sequential chain depth before breaking cleanly (default 4)")
    sa.add_argument("--apply", action="store_true", help="write independent_still=true into 04_shots.json")
    rui = actions.add_parser("review-ui", help="generate a local HTML batch dailies reviewer page without changing stage files")
    rui.add_argument("--film", required=True, type=Path)
    rui.add_argument("--out", type=Path, help="output directory (default <film>/media/review_ui)")
    rui.add_argument("--scene", default=None, help="optional scene_id filter")
    rui.add_argument("--triage", action="store_true", help="run advisory dailies triage across clips on disk")
    rui.add_argument("--clips", type=Path, help="directory holding take clips (default <film>/media/takes)")
    dc = actions.add_parser("doctor", help="read-only runtime environment, FFmpeg filter, font, packaged resource and Flow check")
    dc.add_argument("--film", type=Path, help="optional film directory to check free disk space on")
    dc.add_argument("--probe-flow", action="store_true", help="also probe active CDP endpoint for a Flow tab")
    dc.add_argument("--operation", choices=["render", "send"], default="render", help="disk reserve profile to check")
    ls = actions.add_parser("lease", help="inspect or manage SQLite multi-account leases (<film>/takes/lease_pool.sqlite3 or --db)")
    ls.add_argument("verb", choices=["status", "register", "quarantine", "release"])
    ls.add_argument("--film", type=Path)
    ls.add_argument("--db", type=Path)
    ls.add_argument("--account")
    ls.add_argument("--credits", type=float)
    ls.add_argument("--reason", default="")
    ls.add_argument("--gid")
    ls.add_argument("--lease-token")
    ls.add_argument("--spent", type=float)
    ls.add_argument("--shot-version", type=int, default=1)
    ls.add_argument("--release-leases", action="store_true")
    ht = actions.add_parser("halt", help="machine-wide production halt (any Flow account warning stops ALL sending): "
                                          "status | set --reason | clear --by human:ID|agent:ID --reason")
    ht.add_argument("verb", choices=["status", "set", "clear"])
    ht.add_argument("--reason", default="")
    ht.add_argument("--by", default="", help="who clears the halt: human:<id> or agent:<id>")
    sc = actions.add_parser("scene-conform", help="inspect or incrementally conform completed scenes cleanly")
    sc.add_argument("--film", required=True, type=Path)
    sc.add_argument("--render", action="store_true", help="render READY_TO_CONFORM scenes to media/scenes/<scene>.mkv")
    sc.add_argument("--scenes", nargs="*", help="optional subset of scene IDs")
    sc.add_argument("--jobs", type=int, default=None, help="parallel chunk render workers")
    sc.add_argument("--hwaccel", action="store_true", default=None, help="use GPU h264_nvenc when available")
    qcp = actions.add_parser("qc", help="validate a take QC record (JSON object or list) and print each verdict")
    qcp.add_argument("--record", required=True, type=Path)
    rh = actions.add_parser("rehearse", help="offline dress rehearsal: run the whole chain on a COPY of the package with a mock "
                                             "video runner (no provider, no credits); the result is stamped REHEARSAL and never releasable")
    rh.add_argument("--film", required=True, type=Path, help="the package to copy (it is not modified)")
    rh.add_argument("--out", required=True, type=Path, help="new empty directory for the rehearsal copy (media stays inside it)")
    rh.add_argument("--keep-going", action="store_true", help="continue after a failed step instead of stopping")
    rp = actions.add_parser("reviewpack", help="write one self-contained HTML page the Owner can decide from (gates, storyboard, "
                                               "budget, risks, rights, takes awaiting review); changes nothing in the package")
    rp.add_argument("--film", required=True, type=Path)
    rp.add_argument("--out", type=Path, help="page to write (default <film>/media/review/index.html)")
    ed = actions.add_parser("edit", help="--init drafts 05_edit.json from the shot list and the latest ACCEPTED takes plus a title card with the AI line (a draft for a human to edit)")
    ed.add_argument("--film", required=True, type=Path)
    ed.add_argument("--init", action="store_true", required=True, help="write the draft (refused when 05_edit.json already has events)")
    gs = actions.add_parser("generators", help="--init drafts generators.json (video tool from the take log, image tool from the registered stills) for review")
    gs.add_argument("--film", required=True, type=Path)
    gs.add_argument("--init", action="store_true", required=True, help="write the draft (refused when generators.json already has entries)")
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

    from film_pipeline.production.runtime import writer, WriterBusy
    readonly = {"status", "validate", "qc", "impact", "camera", "continuity", "triage", "agentic-plan", "doctor", "review-ui"}
    is_readonly = (
        (args.action in readonly and not (args.action == "validate" and getattr(args, "sync_gates", False)))
        or (args.action == "foley" and getattr(args, "list", False))
        or (args.action == "lease" and getattr(args, "verb", None) == "status")
        or (args.action == "scene-conform" and not getattr(args, "render", False))
        or (args.action == "setup-anchors" and not getattr(args, "apply", False))
        or (args.action == "stills" and getattr(args, "bind_matching", False) and getattr(args, "dry_run", False))
    )
    try:
        if getattr(args, "film", None) and args.action != "generate" and not is_readonly:
            with writer(args.film, flow=args.action == "reconcile"):
                return _run(args, rest, parser)
        return _run(args, rest, parser)
    except WriterBusy as exc:
        _emit({"ok": False, "code": "FILM_BUSY", "error": str(exc)})
        return 1


def _run(args, rest, parser) -> int:
    try:
        if args.action == "narration":
            return _narration(args, rest, parser)
        if args.action == "rehearse":
            from film_pipeline.production import rehearsal as rh_mod
            report = rh_mod.rehearse(args.film, args.out, stop_on_fail=not args.keep_going)
            _emit(report)
            return 0 if report["all_steps_ok"] and report["reached_delivery"] else 1
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
        if args.action == "status" and args.package:
            from film_pipeline.production import deliver as dl_mod
            report = dl_mod.verify_archive(args.package)
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "status" and args.all:
            from film_pipeline.production import report as rp_mod
            _emit({"films": rp_mod.all_films(args.all)})
            return 0
        if args.action == "status" and not args.film:
            _emit({"error": "status needs --film DIR, --all FILMS_DIR or --package DIR"})
            return 2
        if args.action == "ledger":
            from film_pipeline.production import report as rp_mod
            root = args.film
            film_id = load_package(root).header.film_id
            try:
                if args.add:
                    if not args.ref:
                        raise ValueError("--add needs --ref (where the evidence can be checked)")
                    rp_mod.add_learning(root, film_id, args.add, args.ref, area=args.area)
                elif args.replicate:
                    if not (args.from_film and args.ref):
                        raise ValueError("--replicate needs --from-film (the film that shows it again) and --ref")
                    rp_mod.add_evidence(root, args.replicate, args.from_film, args.ref)
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 1
            _emit(rp_mod.ledger_view(root, film_id))
            return 0
        if args.action == "new":
            target = scaffold(args.film_id, args.profile, args.root, args.title, portrait_9x16=args.portrait_9x16)
            _emit({"created": str(target), "profile": args.profile, "portrait_9x16": args.portrait_9x16})
            return 0
        if args.action == "doctor":
            from PIL import ImageFont
            from film_pipeline.drama.post import DEFAULT_FONTS, FPS, H, W
            from film_pipeline.film_package_export import validate as export_validate
            from film_pipeline.production import ffjoin, foley as foley_mod, post_engine, preflight
            from film_pipeline.providers import flow_ui_adapter

            env = preflight.check(args.film or Path.cwd(), probe_flow=args.probe_flow, operation=args.operation)
            required_filters = {"xfade": False, "ebur128": False, "loudnorm": False}
            try:
                filt_out = subprocess.run(
                    ["ffmpeg", "-v", "error", "-filters"],
                    capture_output=True, text=True, check=True, timeout=15,
                ).stdout
                for name in list(required_filters):
                    required_filters[name] = (f" {name} " in filt_out) or (f"\n {name} " in filt_out) or (name in filt_out)
            except (OSError, subprocess.SubprocessError):
                pass
            font_info = {}
            for font_path in DEFAULT_FONTS:
                fp = Path(font_path)
                loaded = fp.is_file()
                if loaded:
                    try:
                        ImageFont.truetype(str(fp), 24)
                    except OSError:
                        loaded = False
                font_info[font_path] = {"present": fp.is_file(), "loadable": loaded}
            resources_info = {}
            resources_ok = True
            try:
                cat = foley_mod.load_catalog()
                resources_info["sfx_catalog"] = {"ok": True, "entries": len(cat.get("entries", []))}
            except Exception as exc:  # noqa: BLE001
                resources_info["sfx_catalog"] = {"ok": False, "error": str(exc)[:160]}
                resources_ok = False
            try:
                schema = export_validate._load_schema()
                resources_info["film_package_schema"] = {"ok": bool(schema), "title": schema.get("title", "")}
            except Exception as exc:  # noqa: BLE001
                resources_info["film_package_schema"] = {"ok": False, "error": str(exc)[:160]}
                resources_ok = False
            flow_send_ok = flow_ui_adapter.FLOW_SEND.is_file()
            resources_info["flow_ui"] = {"ok": flow_send_ok, "path": str(flow_ui_adapter.FLOW_SEND)}
            if not flow_send_ok:
                resources_ok = False
            engine = post_engine.resolve_engine_dir()
            filters_ok = all(required_filters.values())
            all_ok = bool(env["ok"]) and filters_ok and resources_ok
            _emit({
                "ok": all_ok,
                "readonly": True,
                "preflight": env,
                "ffmpeg_filters": required_filters,
                "fonts": font_info,
                "resources": resources_info,
                "post_engine": str(engine) if engine else None,
                "render_profile": {"width": W, "height": H, "fps": FPS},
                "nvenc_available": ffjoin.nvenc_available(),
                "default_render_workers": ffjoin.render_workers(),
            })
            return 0 if all_ok else 1
        if args.action == "halt":
            from film_pipeline.production import halt as halt_mod

            if args.verb == "status":
                current = halt_mod.read_halt()
                _emit({"ok": True, "halted": current is not None, "halt": current, "halt_file": str(halt_mod.halt_path())})
                return 0
            try:
                if args.verb == "set":
                    if not args.reason.strip():
                        _emit({"ok": False, "error": "halt set needs --reason"})
                        return 1
                    _emit({"ok": True, "halted": True, "halt": halt_mod.set_halt(args.reason, source="cli")})
                    return 0
                _emit({"ok": True, "halted": False, "cleared": halt_mod.clear_halt(args.by, args.reason)})
                return 0
            except (ValueError, RuntimeError) as exc:
                _emit({"ok": False, "error": str(exc)})
                return 1
        if args.action == "lease":
            from film_pipeline.agentic.lease_pool import AccountLeasePool

            db_path = args.db or (Path(args.film) / "takes" / "lease_pool.sqlite3" if args.film else None)
            if db_path is None:
                _emit({"error": "lease needs --film or --db"})
                return 2
            film_id = Path(args.film).name if args.film else "default"
            if args.film and (Path(args.film) / "film.json").is_file():
                try:
                    film_id = json.loads((Path(args.film) / "film.json").read_text(encoding="utf-8")).get("film_id") or film_id
                except (OSError, ValueError):
                    pass
            pool = AccountLeasePool(db_path)
            if args.verb == "status":
                _emit({"readonly": True, "db": str(db_path), **pool.snapshot()})
                return 0
            if args.verb == "register":
                if not args.account or args.credits is None:
                    _emit({"error": "lease register needs --account and --credits"})
                    return 2
                pool.register_account(args.account, args.credits)
                _emit({"ok": True, "db": str(db_path), **pool.snapshot()})
                return 0
            if args.verb == "quarantine":
                if not args.account:
                    _emit({"error": "lease quarantine needs --account"})
                    return 2
                out = pool.quarantine_account(
                    args.account,
                    args.reason or "operator_quarantine",
                    release_active_leases=args.release_leases,
                )
                _emit({"ok": True, "quarantine": out, **pool.snapshot()})
                return 0
            if args.verb == "release":
                if not args.gid:
                    _emit({"error": "lease release needs --gid"})
                    return 2
                try:
                    out = pool.release(
                        args.gid,
                        film_id=film_id if args.film else "",
                        shot_version=args.shot_version,
                        lease_token=args.lease_token,
                        credits_spent=0.0 if args.spent is None else args.spent,
                    )
                except KeyError:
                    out = pool.release(
                        args.gid,
                        film_id="",
                        shot_version=args.shot_version,
                        lease_token=args.lease_token,
                        credits_spent=0.0 if args.spent is None else args.spent,
                    )
                except ValueError as exc:
                    _emit({"ok": False, "error": str(exc)})
                    return 1
                _emit({"ok": out is not None, "lease": out, **pool.snapshot()})
                return 0 if out is not None else 1
        pkg = load_package(args.film)
        if args.action == "finish":
            from film_pipeline.production.finish import finish
            report = finish(pkg, command=main, dry_run=args.dry_run, include_portrait=args.portrait_override,
                            jobs=args.jobs, hwaccel=args.hwaccel)
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "reconcile":
            from film_pipeline.production.recovery import reconcile
            try:
                report = reconcile(pkg, args.take_id)
            except (ValueError, OSError) as exc:
                _emit({"resolved": False, "error": str(exc)})
                return 1
            _emit(report)
            return 0 if report["resolved"] else 1
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
        if args.action == "generability":
            from film_pipeline.drama.generability import rate_shot
            shots = pkg.typed.get("shots")
            if shots is None:
                _emit({"error": "generability needs a valid 04_shots.json"})
                return 2
            _emit({d.generation_id: {**{k: v for k, v in rate_shot(d).model_dump().items() if k != "generation_id"},
                                     "accepted_take_reuse": d.accepted_take_reuse,
                                     "exception": bool(d.generability_exception)}
                   for d in shots.generations})
            return 0
        if args.action == "animatic":
            from film_pipeline.production.animatic import build_animatic
            report = build_animatic(pkg, args.out, stills_dir=args.stills, storyboard_dir=args.storyboard,
                                    audio_dir=args.audio)
            _emit({k: report[k] for k in ("video", "subtitles", "planned_duration_s", "actual_duration_s", "ok",
                                          "findings")})
            return 0 if report["ok"] else 1
        if args.action == "motion":
            return _motion(args, pkg)
        if args.action == "takes":
            from film_pipeline.production import takes as tk_mod
            if args.merge_from:
                from film_pipeline.production.shard_merge import ShardMergeError, merge_shard_takes
                try:
                    report = merge_shard_takes(pkg.root, args.merge_from)
                except ShardMergeError as exc:
                    _emit({"error": str(exc)})
                    return 2
                _emit(report)
                return 1 if report["conflicts"] else 0
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
                        prompt_text=args.prompt.read_text(encoding="utf-8").strip(), route=args.route, model=args.model,
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
        if args.action == "muse":
            from film_pipeline.production import muse_gateway as mg_mod
            try:
                if args.verb == "prepare":
                    if not args.gid:
                        raise ValueError("muse prepare needs --gid")
                    folder = mg_mod.prepare(pkg, args.gid, condition_camera=args.condition_camera)
                    _emit({"request": str(folder), "handoff": str(folder / "handoff.zip"), "sent": False})
                else:
                    if args.request is None:
                        raise ValueError("muse dispatch/ingest needs --request")
                    if args.verb == "dispatch":
                        _emit(mg_mod.dispatch(pkg, args.request, backlog=args.backlog))
                    else:
                        if args.clip is None or args.response is None:
                            raise ValueError("muse ingest needs --clip and --response")
                        _emit(mg_mod.ingest(pkg, args.request, args.clip,
                                          json.loads(args.response.read_text(encoding="utf-8"))))
                return 0
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                _emit({"error": str(exc)})
                return 2
        if args.action == "generate":
            from film_pipeline.production.generate import generate
            critic_report = None
            critic_warnings: list[dict] = []
            if getattr(args, "critic", False):
                from film_pipeline.agentic.pre_send_critic import PreSendCritic

                plan_dir_for_critic = args.plan_out or (Path(pkg.root) / "media" / "plan")
                critic_report = PreSendCritic().inspect(
                    pkg, plan_dir=plan_dir_for_critic, include_accepted=True, generation_id=args.gid
                )
                if not critic_report["ok"] and not args.dry_run:
                    _emit({
                        "sent": False,
                        "dry_run": False,
                        "generation_id": args.gid,
                        "blocked": [f["detail"] for f in critic_report["findings"] if f.get("severity") == "BLOCK"],
                        "critic": critic_report,
                    })
                    return 1
            elif not getattr(args, "no_critic", False) and "preprod" in pkg.typed and "shots" in pkg.typed:
                from film_pipeline.agentic.pre_send_critic import PreSendCritic

                plan_dir_for_critic = args.plan_out or (Path(pkg.root) / "media" / "plan")
                adv = PreSendCritic().inspect(
                    pkg, plan_dir=plan_dir_for_critic, include_accepted=True, generation_id=args.gid
                )
                critic_warnings = [f for f in adv["findings"] if f.get("severity") == "WARN"]
            try:
                done = generate(pkg, args.gid, dry_run=args.dry_run, plan_out=args.plan_out, stills_dir=args.stills,
                                start_token=args.start_token, backlog=args.backlog, end_token=args.end_token,
                                auto_resend=0 if args.no_auto_resend else 1)
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 2
            if critic_report is not None:
                done["critic"] = critic_report
            elif critic_warnings:
                done["critic_warnings"] = critic_warnings
            _emit(done)
            if args.dry_run:
                return 0
            last = done
            while last.get("auto_resend"):   # P18-03: the outcome is the last send's
                last = last["auto_resend"]
            return 0 if last["sent"] and last.get("manifest_result") == "PASSED" else 1
        if args.action == "stills":
            from film_pipeline.production import stills as st_mod
            if "preprod" not in pkg.typed or "shots" not in pkg.typed:
                _emit({"error": "stills needs a valid 03_preprod.json and 04_shots.json"})
                return 2
            try:
                if args.register:
                    if args.image is None:
                        _emit({"error": "--register needs --image"})
                        return 2
                    out = st_mod.register_still(pkg, args.register, args.image, source=args.source,
                                                credits=args.credits)
                    rel = st_mod.relation_questions_for(pkg, args.register)
                    if rel:  # informational: the Owner answers in chat; approval logic is unchanged
                        out = {**out, "relation_questions": rel}
                    look = st_mod.still_checks_for(pkg, args.register)
                    if look:  # informational too: eyeline + corner marks (film08 pilot)
                        out = {**out, "still_checks": look}
                    _emit({"registered": out})
                    return 0
                if args.tighten:
                    out = st_mod.tighten_still(pkg, args.tighten, side=args.side, scale=args.scale, y=args.y)
                    box = out["box"]
                    print(f"tightened {out['file']} box x={box['x']} y={box['y']} w={box['w']} h={box['h']} "
                          f"(listener {out['side']})")
                    return 0
                if args.bind_matching:
                    out = st_mod.bind_matching_stills(pkg, by=args.by or "", dry_run=args.dry_run)
                    _emit(out)
                    return 0
                if args.approve:
                    _emit({"approved": st_mod.approve_still(pkg, args.approve, args.by or "")})
                    return 0
            except (ValueError, OSError) as exc:
                _emit({"error": str(exc)})
                return 1
            rows = st_mod.list_stills(pkg)
            missing = [r["generation_id"] for r in rows if r["needs_still"] and r["state"] != "APPROVED"]
            _emit({"stills": rows, "waiting": missing})
            return 0 if not missing else 1
        if args.action in ("edit", "generators"):
            from film_pipeline.production import draft as dr_mod
            try:
                if args.action == "edit":
                    draft = dr_mod.edit_draft(pkg)
                    missing = draft.pop("missing")
                    path = dr_mod.write_json(Path(pkg.root) / "05_edit.json", draft)
                    _emit({"written": str(path), "events": len(draft["events"]), "missing_takes": missing,
                           "note": "a draft: check the order, the cuts and the title card before film.py cut"})
                else:
                    records = dr_mod.generators_draft(pkg)
                    path = dr_mod.write_json(Path(pkg.root) / "generators.json", records)
                    _emit({"written": str(path), "generators": records,
                           "note": "a draft: check the provider names, models and settings before film.py deliver"})
            except (ValueError, OSError) as exc:
                _emit({"error": str(exc)})
                return 1
            return 0
        if args.action == "reviewpack":
            from film_pipeline.production import reviewpack as rv_mod
            _emit(rv_mod.build(pkg, args.out))
            return 0
        if args.action == "lock":
            from film_pipeline.production import lock as lk_mod
            if args.lock:
                try:
                    _emit({"locked": lk_mod.lock_picture(pkg, args.by or "", args.reason, args.clips)})
                except ValueError as exc:
                    _emit({"error": str(exc)})
                    return 1
                return 0
            status = lk_mod.lock_status(pkg)
            dirty = lk_mod.dirty_items(pkg) if status["locked"] else {"dirty": [], "clean": []}
            _emit({"status": status, **dirty})
            return 0 if status["fresh"] and not dirty["dirty"] else 1
        if args.action == "grade":
            from film_pipeline.production import color as col_mod
            from film_pipeline.production import edit as ed_mod
            from film_pipeline.production.mix import stamp_post_item
            try:
                report = col_mod.match(pkg, clips_dir=args.clips, jobs=args.jobs)
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 1
            col_mod.write_report(pkg, report)
            stamp_post_item(pkg, "color", {"report": "color/color.json", "ok": report["ok"], "summary": report["summary"]})
            if args.render and report["ok"]:
                section = pkg.typed.get("edit")
                if section is None:
                    _emit({"error": "grade --render needs a valid 05_edit.json"})
                    return 2
                try:
                    rendered = ed_mod.render_cut(pkg, section, args.out or pkg.root / "media" / "cut" / "graded_cut.mp4",
                                                 clips_dir=args.clips, corrections=col_mod.corrections_of(report),
                                                 look=report["plan"]["look"] or None,
                                                 jobs=args.jobs, hwaccel=args.hwaccel)
                except ValueError as exc:
                    _emit({"error": str(exc)})
                    return 1
                report["render"] = {k: rendered[k] for k in ("output", "output_sha256", "total_s", "path")}
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "mastercheck":
            from film_pipeline.production import master_qc as mq_mod
            from film_pipeline.production.mix import stamp_post_item
            video = args.video or pkg.root / "media" / "cut" / "mixed.mp4"
            if not video.is_file():
                _emit({"error": f"{video} not found (render and mix the cut first)"})
                return 2
            report_path = args.cut_report
            if report_path is None:
                report_path = next((p for p in (video.with_suffix(".cut.json"), pkg.root / "media" / "cut" / "rough_cut.cut.json")
                                    if p.is_file()), None)
            record = mq_mod.check_master(video, pkg=pkg, cut_report=report_path)
            path = mq_mod.write_record(pkg, record)
            stamp_post_item(pkg, "master_qc", {"report": "qc/master_qc.json", "sha256": record.sha256, "ok": record.ok})
            _emit({"ok": record.ok, "record": str(path), "metrics": record.metrics,
                   "checks": {c.group: c.result for c in record.checks},
                   "findings": [f.model_dump(mode="json") for f in record.findings]})
            return 0 if record.ok else 1
        if args.action == "dialoguecheck":
            from film_pipeline.production import dialogue_stt as ds_mod
            from film_pipeline.production.mix import stamp_post_item
            report = ds_mod.check(pkg, engine_mode=args.engine) if args.engine else ds_mod.check(pkg)
            stamp_post_item(pkg, "dialogue_stt", {"report": "qc/dialogue_stt.json", "ok": report["ok"], "summary": report["summary"]})
            _emit(report)
            return 0
        if args.action == "deliver":
            from film_pipeline.production import deliver as dl_mod
            if args.accept is not None:
                try:
                    _emit(dl_mod.accept_delivery(pkg, args.accept))
                except ValueError as exc:
                    _emit({"error": str(exc)})
                    return 1
                return 0
            video = args.video or pkg.root / "media" / "cut" / "mixed.mp4"
            if not video.is_file():
                _emit({"error": f"{video} not found (render and mix the cut first)"})
                return 2
            report_path = args.cut_report or next((p for p in (video.with_suffix(".cut.json"), pkg.root / "media" / "cut" / "rough_cut.cut.json")
                                                   if p.is_file()), None)
            if report_path is None:
                _emit({"error": "deliver needs the .cut.json of the master (--cut-report)"})
                return 2
            if bool(args.c2pa_cert) != bool(args.c2pa_key):
                _emit({"error": "--c2pa-cert and --c2pa-key go together"})
                return 2
            try:
                report = dl_mod.deliver(pkg, video, report_path, generators=_generators(args),
                                        c2pa=(args.c2pa_cert, args.c2pa_key) if args.c2pa_cert else None,
                                        require_portrait=args.portrait_override)
            except (ValueError, KeyError) as exc:
                _emit({"error": str(exc)})
                return 1
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "versions":
            from film_pipeline.production import versions as vs_mod
            from film_pipeline.production.mix import stamp_post_item
            video = args.video or pkg.root / "media" / "cut" / "mixed.mp4"
            if not video.is_file():
                _emit({"error": f"{video} not found (render and mix the cut first)"})
                return 2
            report_path = args.cut_report or next((p for p in (video.with_suffix(".cut.json"), pkg.root / "media" / "cut" / "rough_cut.cut.json")
                                                   if p.is_file()), None)
            if report_path is None:
                _emit({"error": "versions needs the .cut.json of the master (--cut-report)"})
                return 2
            try:
                report = vs_mod.build(pkg, video, report_path, portrait_source=args.portrait_source, generators=_generators(args),
                                      include_portrait=args.portrait_override, jobs=args.jobs, hwaccel=args.hwaccel)
            except (ValueError, KeyError) as exc:
                _emit({"error": str(exc)})
                return 1
            stamp_post_item(pkg, "versions", {"report": "versions/versions.json", "ok": report["ok"], "summary": report["summary"]})
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "titles":
            from film_pipeline.production import edit as ed_mod
            from film_pipeline.production import titles as ti_mod
            from film_pipeline.production.mix import stamp_post_item
            try:
                prepared = ti_mod.prepare(pkg, clips_dir=args.clips, generators=_generators(args),
                                          langs=tuple(x for x in args.langs.split(",") if x), jobs=args.jobs)
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 1
            report = ti_mod.write_outputs(pkg, prepared)
            if args.render and report["ok"]:
                extra = {}
                if args.color:
                    from film_pipeline.production import color as col_mod
                    found = col_mod.load_report(pkg.root)
                    if found is None:
                        _emit({"error": "--color needs color/color.json (run film.py grade first)"})
                        return 1
                    extra = {"corrections": col_mod.corrections_of(found), "look": found["plan"]["look"] or None}
                try:
                    rendered = ed_mod.render_cut(pkg, pkg.typed["edit"], args.out or pkg.root / "media" / "cut" / "titled_cut.mp4",
                                                 clips_dir=args.clips, cues=prepared["cues"], reframes=prepared["reframes"],
                                                 end_lines=prepared["credits"][pkg.header.language],
                                                 jobs=args.jobs, hwaccel=args.hwaccel, **extra)
                except (ValueError, KeyError) as exc:
                    _emit({"error": str(exc)})
                    return 1
                report["render"] = {k: rendered[k] for k in ("output", "output_sha256", "total_s", "path")}
                if args.clean_copy:
                    out_path = Path(rendered["output"])
                    clean_out = out_path.with_name(out_path.stem + ".clean.mp4")
                    try:
                        clean = ed_mod.render_cut(pkg, pkg.typed["edit"], clean_out, clips_dir=args.clips, cues=[],
                                                  reframes=prepared["reframes"],
                                                  end_lines=prepared["credits"][pkg.header.language],
                                                  jobs=args.jobs, hwaccel=args.hwaccel, **extra)
                    except (ValueError, KeyError) as exc:
                        _emit({"error": f"clean copy: {exc}"})
                        return 1
                    try:
                        rel = Path(clean["output"]).resolve().relative_to(Path(pkg.root).resolve()).as_posix()
                    except ValueError:
                        rel = str(Path(clean["output"]).resolve())
                    report["clean_render"] = {"output": rel, "sha256": clean["output_sha256"]}
                    titles_json = ti_mod.titles_dir(pkg.root) / "titles.json"
                    stored = json.loads(titles_json.read_text(encoding="utf-8"))
                    stored["clean_render"] = report["clean_render"]
                    titles_json.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            stamp_post_item(pkg, "titles", {"report": "titles/titles.json", "ok": report["ok"], "summary": report["summary"]})
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "sounds":
            from film_pipeline.production import sound_rights as sr_mod
            if args.record:
                try:
                    ranges = []
                    for spec in args.usage:
                        a, _, b = spec.partition(":")
                        ranges.append(sr_mod.UsageRange(start_s=float(a or 0), end_s=float(b) if b else None))
                    if not (args.kind and args.license_id):
                        raise ValueError("--record needs --kind and --license")
                    rec = sr_mod.record_asset(pkg, args.record, args.kind, args.license_id, source_url=args.source_url,
                                              status=args.status, attribution=args.attribution, note=args.note, usage=ranges)
                except ValueError as exc:
                    _emit({"error": str(exc)})
                    return 1
                _emit({"recorded": rec.model_dump(mode="json")})
                return 0
            checked = sr_mod.check_assets(pkg)
            try:
                sheet = sr_mod.cue_sheet(pkg)
            except ValueError as exc:
                sheet = {"error": str(exc)}
            _emit({"ok": not checked["issues"], **checked, "attributions": sr_mod.attributions(pkg), "cue_sheet": sheet})
            return 1 if checked["issues"] else 0
        if args.action == "foley":
            from film_pipeline.production import foley as fl_mod
            if args.list:
                cat = fl_mod.load_catalog()
                _emit({"license": cat.get("license"), "entries": [{"id": e["id"], "category": e.get("category"), "duration_s": e.get("duration_s"), "description": e.get("description")} for e in cat["entries"]]})
                return 0
            ids = [x.strip() for x in args.ids.split(",") if x.strip()] if args.ids else None
            try:
                _emit(fl_mod.materialize_film_foley(pkg, ids, all_catalog=args.all))
            except (ValueError, FileNotFoundError) as exc:
                _emit({"error": str(exc)})
                return 1
            return 0
        if args.action == "triage":
            from film_pipeline.production import dailies_triage as dt_mod
            try:
                _emit(dt_mod.triage_take(pkg, args.take_id, clips_dir=args.clips))
            except (ValueError, KeyError, FileNotFoundError) as exc:
                _emit({"error": str(exc)})
                return 2
            return 0
        if args.action == "agentic-plan":
            from film_pipeline.agentic import (
                CapabilityRouter,
                CausalRepairRouter,
                PreSendCritic,
                SceneIncrementalConformer,
                WaveDAGScheduler,
            )
            from film_pipeline.agentic.scheduler import hash_files_parallel
            from film_pipeline.production.takes import load_log

            root_dir = Path(pkg.root)
            log = load_log(root_dir, pkg.header.film_id)
            candidate_paths: list[Path] = [
                root_dir / "media" / "takes" / Path(t.output_file).name
                for t in log.takes
                if t.output_file and t.output_sha256
            ]
            scenes_dir = root_dir / "media" / "scenes"
            if scenes_dir.is_dir():
                candidate_paths.extend(scenes_dir.glob("*.mkv"))
            verified_hashes = hash_files_parallel([p for p in candidate_paths if p.is_file()])
            waves = WaveDAGScheduler(pkg, optimistic_lookahead=args.lookahead, verified_hashes=verified_hashes).plan_waves()
            critic = PreSendCritic().inspect(pkg, plan_dir=args.plan_dir) if "preprod" in pkg.typed and "shots" in pkg.typed else None
            repairs = CausalRepairRouter().diagnose_take_log(pkg)
            conform = (
                SceneIncrementalConformer().scene_status(pkg, verified_hashes=verified_hashes)
                if "shots" in pkg.typed
                else None
            )
            checkpoints = CapabilityRouter().checkpoint_plan(pkg, wave_info=waves)
            report = {
                "film_id": pkg.header.film_id,
                "readonly": True,
                "waves": waves,
                "critic": critic,
                "repairs": repairs,
                "incremental_conform": conform,
                **checkpoints,
            }
            if args.json_out is not None:
                out_p = Path(args.json_out).resolve()
                film_root = Path(pkg.root).resolve()
                if out_p == film_root or film_root in out_p.parents:
                    _emit({"error": "agentic-plan --json-out must point outside the film package directory"})
                    return 2
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _emit(report)
            return 0
        if args.action == "setup-anchors":
            from film_pipeline.agentic import suggest_setup_anchors

            try:
                report = suggest_setup_anchors(pkg, max_chain_depth=args.max_depth, apply=args.apply)
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 2
            _emit(report)
            return 0
        if args.action == "review-ui":
            from film_pipeline.production.review_ui import build_review_ui

            try:
                report = build_review_ui(pkg, out_dir=args.out, scene_id=args.scene,
                                         run_triage=args.triage, clips_dir=args.clips)
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 2
            _emit(report)
            return 0
        if args.action == "scene-conform":
            from film_pipeline.agentic.incremental_conform import SceneIncrementalConformer

            report = SceneIncrementalConformer().conform_ready_scenes(
                pkg, render=args.render, scenes=args.scenes, jobs=args.jobs, hwaccel=args.hwaccel
            )
            _emit(report)
            return 0
        if args.action == "mix":
            from film_pipeline.production import mix as mix_mod
            from film_pipeline.production import post_engine
            section = pkg.typed.get("edit")
            if section is None:
                _emit({"error": "mix needs a valid 05_edit.json"})
                return 2
            cut_path = args.cut or pkg.root / "media" / "cut" / "rough_cut.mp4"
            try:
                report = mix_mod.mix_cut(pkg, section, cut_path, args.out or pkg.root / "media" / "cut" / "mixed.mp4",
                                         stems_dir=args.stems,
                                         engine_dir=post_engine.resolve_engine_dir(args.engine))
            except ValueError as exc:
                _emit({"error": str(exc)})
                return 1
            mix_mod.stamp_post_item(pkg, "mix", {"output_sha256": report["output_sha256"], "cut_sha256": report["cut_sha256"],
                                                 "report": "audio/mix.json", "ok": report["ok"]})
            _emit(report)
            return 0 if report["ok"] else 1
        if args.action == "cut":
            from film_pipeline.production import edit as ed_mod
            section = pkg.typed.get("edit")
            if section is None:
                _emit({"error": "cut needs a valid 05_edit.json"})
                return 2
            if args.render:
                out = args.out or pkg.root / "media" / "cut" / "rough_cut.mp4"
                try:
                    extra = {}
                    if args.color:
                        from film_pipeline.production import color as col_mod
                        found = col_mod.load_report(pkg.root)
                        if found is None:
                            raise ValueError("--color needs color/color.json (run film.py grade first)")
                        extra = {"corrections": col_mod.corrections_of(found), "look": found["plan"]["look"] or None}
                    _emit(ed_mod.render_cut(pkg, section, out, clips_dir=args.clips, require_accepted=args.accepted_only,
                                            jobs=args.jobs, hwaccel=args.hwaccel, **extra))
                except ValueError as exc:
                    _emit({"error": str(exc)})
                    return 1
                return 0
            problems, durations = ed_mod.edit_problems(pkg, section, clips_dir=args.clips,
                                                       require_accepted=args.accepted_only)
            blocked = [p for p in problems if p["severity"] == "BLOCK"]
            plan = None if blocked else ed_mod.timeline(section, durations)
            cont = ed_mod.cut_continuity(pkg, section, durations)
            blocked += [i for i in cont["issues"] if i["severity"] == "BLOCK"]
            _emit({"ok": not blocked, "problems": problems, "timeline": plan,
                   "rhythm": ed_mod.rhythm_report(pkg, section, durations), "continuity": cont})
            return 1 if blocked else 0
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
                    payload = json.loads(args.ingest.read_text(encoding="utf-8"))
                    if isinstance(payload, list):
                        if not payload:
                            raise ValueError("batch review list is empty")
                        ingested = [
                            tk_mod.ingest_review(pkg.root, pkg.header.film_id, item, pkg=pkg)
                            for item in payload
                        ]
                        _emit({"batch": True, "count": len(ingested), "ingested": ingested})
                    else:
                        _emit(tk_mod.ingest_review(pkg.root, pkg.header.film_id, payload, pkg=pkg))
                except ValidationError as exc:
                    _emit({"error": [e["msg"] for e in exc.errors()]})
                    return 2
                except (ValueError, KeyError) as exc:
                    _emit({"error": str(exc.args[0] if exc.args else exc)})
                    return 2
                return 0
            if args.supplement:
                try:
                    entry = tk_mod.load_log(pkg.root, pkg.header.film_id).get(args.supplement)
                    _emit({"written": str(tk_mod.supplemental_template(pkg, entry))})
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
        if args.action == "ledger-adjust":
            from film_pipeline.production import money as mn_mod
            from film_pipeline.production import takes as tk_mod
            root = Path(pkg.root)
            if args.add_adjustment:
                missing = [f for f, v in (("--delta", args.delta), ("--reason", args.reason),
                                          ("--evidence", args.evidence), ("--by", args.by)) if v in (None, "")]
                if missing:
                    _emit({"error": f"--add-adjustment needs {', '.join(missing)}"})
                    return 2
                mn_mod.record_adjustment(root, args.delta, args.reason, args.evidence, args.by, unit=args.unit)
            if args.checkpoint_scene:
                if args.observed_balance is None or not args.account:
                    _emit({"error": "--checkpoint-scene needs --account and --observed-balance"})
                    return 2
                log = tk_mod.load_log(root, pkg.header.film_id)
                adj_log = mn_mod.load_adjustments(root)
                spent = mn_mod.money_ledger(log, {}, adj_log.adjustments).get("credits", {}).get("spent", 0.0)
                mn_mod.record_checkpoint(root, args.checkpoint_scene, args.boundary, args.account,
                                         args.observed_balance, spent, note=args.note)
            log = tk_mod.load_log(root, pkg.header.film_id)
            adj_log = mn_mod.load_adjustments(root)
            _emit({"film_id": pkg.header.film_id, "money": mn_mod.money_ledger(log, {}, adj_log.adjustments),
                   "adjustments": [a.model_dump(mode="json") for a in adj_log.adjustments],
                   "checkpoints": [c.model_dump(mode="json") for c in adj_log.checkpoints]})
            return 0
        results = evaluate_gates(pkg)
        report = summary(results)
        if args.action == "validate":
            from film_pipeline.production.gates import sync_header_gates
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
            if args.sync_gates:
                report["synced_gates"] = sync_header_gates(pkg, results)
            _emit(report)
            return 1 if report["blocked"] else 0
        from film_pipeline.production.report import status_report
        full = status_report(pkg)
        _emit({
            "next_action": full["next_action"],
            "runbook": full["runbook"],
            "report": full,
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
