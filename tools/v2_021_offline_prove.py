"""V2-021 — offline full-lifecycle proof (scripted transport doubles).

Proves the compiled chain end-to-end WITHOUT provider claims:
  frozen compilation -> synthetic double assets (ffmpeg-generated, one per
  compiled shot) -> technical QC -> ContinuityEngine (scripted evidence
  records labeled DOUBLE-SCENE) -> repair planner (demonstrated on one
  scripted failure) -> editorial intelligence -> assembly -> finishing ->
  distribution master -> provenance manifest -> learning loop.

NO provider mutation. Assets are clearly labeled synthetic doubles.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.narrative import (
    ContinuityEngine, EditorialIntelligence, LearningLoop, RepairPlanner)

PKG = ROOT / "projects/quality_v2_021_narrative_compiler"
RUN = PKG / "offline_prove"
COMP = json.loads((PKG / "V2_021_FIXTURE_COMPILATION.json")
                  .read_text(encoding="utf-8"))


def make_double(path: Path, function: str, seed: int) -> None:
    """Synthetic 5.05s 1280x720@24 clip with visible motion + the muted
    cold palette family; content varies per shot function."""
    hues = {"ESTABLISH": 0.58, "DISCOVER": 0.55, "PRESSURE": 0.52,
            "REVEAL": 0.60, "AFTERMATH": 0.57, "RESOLVE": 0.53}
    hue = hues.get(function, 0.56)
    vf = (f"testsrc2=size=1280x720:rate=24:duration=5.05,"
          f"hue=h={int(hue * 360)}:s=0.35,"
          f"noise=alls={6 + seed}:allf=t,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", vf, "-c:v", "libx264", "-crf", "20",
                    str(path)], capture_output=True)


def frames_of(path: Path, directory: Path) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                    "-fps_mode", "passthrough", "-start_number", "0",
                    str(directory / "f_%04d.png")], capture_output=True)
    return len(list(directory.glob("f_*.png")))


def technical(path: Path, n_frames: int) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,r_frame_rate,codec_name",
         "-of", "json", str(path)], capture_output=True, text=True)
    meta = json.loads(probe.stdout or "{}")
    stream = next((s for s in meta.get("streams", [])
                   if s.get("codec_type") == "video"), {})
    num, _, den = (stream.get("r_frame_rate") or "0/1").partition("/")
    return {"decode_ok": True, "duration_s": float(
        meta.get("format", {}).get("duration") or 0),
        "width": stream.get("width"), "height": stream.get("height"),
        "fps": float(num) / float(den or 1), "nb_frames": n_frames,
        "double_asset": True}


def main() -> int:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "assets").mkdir(exist_ok=True)
    nodes = COMP["shot_graph"]["nodes"]
    engine = ContinuityEngine()
    learning = LearningLoop()
    qc_reports = {}
    assets = []
    for seed, node in enumerate(nodes):
        sid = node["shot_id"]
        path = RUN / "assets" / f"{sid}.mp4"
        make_double(path, node["function"], seed)
        frames_dir = RUN / "frames" / sid
        n = frames_of(path, frames_dir)
        tech = technical(path, n)
        # scripted DOUBLE-SCENE evidence: every dimension passes because
        # the double was BUILT to satisfy the frozen contracts; the
        # review record explicitly says synthetic
        evidence = {"shot_local": {
            dim: {"verdict": "PASS",
                  "evidence": f"double-scene constructed to contract; "
                              f"advisory review of {n} keyframes"}
            for dim in engine.DIMENSIONS}}
        report = engine.evaluate_shot(shot_id=sid, technical=tech,
                                      evidence=evidence)
        qc_reports[sid] = json.loads(report.model_dump_json())
        learning.record(
            "double-scene QC pipeline executes full continuity contract",
            domain="continuity_engine", evidence=[sid])
        assets.append({"shot_id": sid, "path": str(path),
                       "frames": n, "sha256": hashlib.sha256(
                           path.read_bytes()).hexdigest()})

    # repair-planner demonstration on a SCRIPTED failure (no mutation)
    scripted_fail = dict(qc_reports[nodes[3]["shot_id"]])
    scripted_fail["verdict"] = "REPAIR_REQUIRED"
    scripted_fail["failure_class"] = "PROMPT_REPAIRABLE"
    scripted_fail["shot_local"] = [
        dict(d) for d in qc_reports[nodes[2]["shot_id"]]["shot_local"]]
    for d in scripted_fail["shot_local"]:
        if d["dimension"] == "SCREEN_DIRECTION":
            d["verdict"] = "FAIL"
            d["evidence"] = "SCRIPTED demo: direction flipped"
    truth = {"subject": "courier", "world": "pass",
             "screen_direction": "left-to-right", "camera": "locked"}
    repair_plan = RepairPlanner().plan(
        type("R", (), {"shot_id": scripted_fail["shot_id"],
                       "failure_class": "PROMPT_REPAIRABLE",
                       "shot_local": [type("D", (), d)()
                                      for d in
                                      scripted_fail["shot_local"]],
                       "cut_compatibility": []})(), truth)

    # editorial trim-first demonstration
    trim = EditorialIntelligence().propose_trim(
        qc_report=type("R", (), {"verdict": "REPAIR_REQUIRED",
                                 "cut_compatibility": [type(
                                     "D", (), {"verdict": "FAIL"})()],
                                 "shot_local": [type(
                                     "D", (), {"dimension": "MOTION",
                                               "verdict": "PASS"})()]})(),
        junction_metrics={"tail_trim_frames": 4})

    # assembly (concat filter, segment-interleaved audio-safe order)
    ranges = {a["shot_id"]: [0, a["frames"]] for a in assets}
    inputs, filters, vlabels = [], [], []
    for i, a in enumerate(assets):
        start, end = ranges[a["shot_id"]]
        inputs += ["-i", a["path"]]
        filters.append(
            f"[{i}:v]trim=start_frame={start}:end_frame={end},"
            f"setpts=PTS-STARTPTS[v{i}]")
        vlabels.append(f"[v{i}]")
    filters.append("".join(vlabels) +
                   f"concat=n={len(assets)}:v=1:a=0[out]")
    proof = RUN / "OFFLINE_SEQUENCE_PROOF.mp4"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
         ";".join(filters), "-map", "[out]",
         "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
         str(proof)], capture_output=True, text=True)
    if proc.returncode != 0:
        print("ASSEMBLY FAILED:", proc.stderr[-400:])
        return 1
    count = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-count_frames", "-show_entries", "stream=nb_read_frames",
         "-of", "csv=p=0", str(proof)], capture_output=True, text=True)
    total_frames = int(count.stdout.strip() or 0)

    # silent finishing (doubles carry no audio) + master
    fm = RUN / "OFFLINE_FINISH_MASTER.mov"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(proof),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-shortest", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "128k", str(fm)], capture_output=True)
    dm = RUN / "OFFLINE_DISTRIBUTION_MASTER.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(fm),
                    "-c:v", "copy", "-af",
                    "loudnorm=I=-14:TP=-1.2:LRA=11", "-c:a", "aac",
                    "-b:a", "192k", "-movflags", "+faststart",
                    str(dm)], capture_output=True)

    manifest = {
        "version": "v2-021-offline-prove-manifest-v1",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "claim": "MACHINERY PROOF ONLY — assets are synthetic doubles; "
                 "no provider generation is claimed",
        "chain": {
            "input": COMP["input"],
            "story_graph_nodes": len(COMP["story_graph"]["nodes"]),
            "beats": len(COMP["narrative"]["beats"]),
            "shot_graph": [n["shot_id"] + ":" + n["function"]
                           for n in nodes],
            "prompt_plan_shas": {sid: plan["sha256"][:16] for sid, plan
                                 in COMP["prompt_plans"].items()},
            "attempt": "SCRIPTED_DOUBLE (no dispatch)",
            "assets": assets,
            "qc_verdicts": {sid: r["verdict"] for sid, r in
                            qc_reports.items()},
            "editorial_ranges": ranges,
            "sequence_proof": {"path": str(proof),
                               "sha256": hashlib.sha256(
                                   proof.read_bytes()).hexdigest(),
                               "frames": total_frames},
            "distribution_master": {
                "path": str(dm),
                "sha256": hashlib.sha256(dm.read_bytes()).hexdigest(),
                "note": "silent-track master over double assets"},
        },
        "repair_demo": repair_plan,
        "trim_demo": trim,
        "learnings": learning.to_manifest(),
        "mutations_used": 0,
    }
    dst = RUN / "V2_021_OFFLINE_PROVE.json"
    dst.write_text(json.dumps(manifest, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"saved": str(dst), "shots": len(assets),
                      "proof_frames": total_frames,
                      "qc": {sid: r["verdict"] for sid, r in
                             qc_reports.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
