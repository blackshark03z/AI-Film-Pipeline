"""AI-FILM-QUALITY-V2-002 — Phases 7-11 evidence + governance minting.

Subcommand `evidence`: build deterministic visual evidence (dense motion
packets, identity side-by-side sheet, entry/exit continuity sheets) for
the two acquired candidates. No judgment is recorded here.

Subcommand `govern`: after the worker records open observations into
observations_v2_002.json, mint the governed QualityRepairCandidates
(real asset shas) through the frozen state machine: PROPOSED ->
TECHNICALLY_VALID (technical receipt) -> QUALITY_REVIEW_READY (10-
dimension review receipt + identity + editorial receipts). NO Owner
decision is minted here and NO promotion runs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"
SCENE = PKG / "scene_SCENE_F_STORM_GATE"
BASELINE_VIDEO = ROOT / ("projects/flow_upload_contract_requal_009/"
                         "reproof/scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/"
                         "videos/c1a69047933565230870ad22.mp4")
F1_VIDEO = ROOT / ("projects/flow_production_scale_007/"
                   "sequence_SEQ007_DAYLIGHT_ROAD/scene_SCENE_F_STORM_GATE/"
                   "shot_SEQ7_F1/videos")
F3_VIDEO = ROOT / ("projects/flow_production_scale_007/"
                   "sequence_SEQ007_DAYLIGHT_ROAD/scene_SCENE_F_STORM_GATE/"
                   "shot_SEQ7_F3/videos")


def candidates() -> dict:
    freeze = json.loads((PKG / "experiment_freeze_v2_002.json").read_text(
        encoding="utf-8"))
    out = {}
    for cand in freeze["candidates"]:
        result = json.loads(
            (SCENE / f"shot_{cand['shot_id']}/result.json").read_text(
                encoding="utf-8"))
        out[cand["candidate_id"]] = {
            "shot_id": cand["shot_id"],
            "video": Path(result["asset"]["uri_or_path"]),
            "asset_sha256": result["asset"]["sha256"],
            "asset_id": result["asset"]["asset_id"],
            "provider_job_id": result["provider_job_id"],
            "output_identity": result["output_identity"],
            "result": result}
    return out


def file_sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,avg_frame_rate",
         "-of", "json", str(path)], capture_output=True, text=True,
        check=True)
    data = json.loads(out.stdout)
    stream = next(s for s in data["streams"] if "width" in s)
    return {"duration_s": float(data["format"]["duration"]),
            "width": stream["width"], "height": stream["height"],
            "fps": stream["avg_frame_rate"]}


def full_decode(path: Path) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
         "-map", "0:v:0", "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


def contact_strip(video: Path, times: list[float], out: Path) -> None:
    """One row of labeled frames at the given times."""
    import re
    n = len(times)
    select = "+".join(f"eq(n\\,{int(t * 24)})" for t in times)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
         f"select='{select}',scale=320:-1,tile={n}x1", "-frames:v", "1",
         "-update", "1", str(out)], check=True)


def evidence() -> int:
    ev = PKG / "qc_evidence"
    ev.mkdir(parents=True, exist_ok=True)
    cands = candidates()
    report = {"version": "v2-002-technical-evidence-v1",
              "checkpoint": "V2002_P7_TECH_QC", "candidates": {}}
    for cid, info in cands.items():
        video = info["video"]
        probe = ffprobe(video)
        decode = full_decode(video)
        strip = ev / f"strip_{cid}.png"
        contact_strip(video, [0.2, 1.4, 2.8, 4.2, 5.4], strip)
        # dense motion packet (8 fps, first 5.6 s editorial window)
        packet_dir = ev / f"packet_{cid}"
        from film_pipeline.motion_qc import build_motion_packet
        packet = build_motion_packet(
            packet_id=f"MOT-V2-002-{cid}",
            subject_label=cid, video_path=video, out_base=packet_dir,
            trim_start_s=0.0, trim_end_s=5.6, fps=8,
            created_at=info["result"].get("acquired_at", ""))
        report["candidates"][cid] = {
            "asset_sha256": info["asset_sha256"],
            "ffprobe": probe, "full_decode": decode,
            "duration_target_window_s": [0.0, 5.6],
            "trim_compatible": probe["duration_s"] >= 5.6,
            "frame_strip": strip.name,
            "motion_packet": str(packet_dir.relative_to(ROOT))}
    # identity side-by-side: baseline vs A vs B at matched times
    cands_list = sorted(cands)
    times = [0.2, 2.8, 5.0]
    inputs, filters = [], []
    labels = ["BASELINE"] + cands_list
    rows = []
    for idx, (label, video) in enumerate(
            [(labels[0], BASELINE_VIDEO)] +
            [(c, cands[c]["video"]) for c in cands_list]):
        for t_idx, t in enumerate(times):
            inputs += ["-ss", f"{t:.3f}", "-i", str(video)]
            filters.append(
                f"[{idx * len(times) + t_idx}:v]scale=426:240,setsar=1"
                f",drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                f"text='{label} t={t}s':fontcolor=white:fontsize=22:"
                f"box=1:boxcolor=black@0.55:boxborderw=8"
                f"[v{idx * len(times) + t_idx}]")
            rows.append(f"[v{idx * len(times) + t_idx}]")
    grid = "".join(f"[v{i}]" for i in range(len(rows)))
    layout = (f"{grid}xstack=inputs={len(rows)}:layout=0_0|426_0|852_0|"
              f"0_240|426_240|852_240|0_480|426_480|852_480[out]")
    sheet = ev / "identity_side_by_side_v2_002.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters) + ";" + layout,
         "-map", "[out]", "-update", "1", str(sheet)], check=True)
    report["identity_sheet"] = sheet.name
    # entry/exit continuity: F1 last frame vs candidate t=0.2; candidate
    # t=5.4 vs F3 first frame
    f1_last = ev / "f1_last_frame.png"
    f3_first = ev / "f3_first_frame.png"
    f1_video = sorted(F1_VIDEO.glob("*.mp4"))[0]
    f3_video = sorted(F3_VIDEO.glob("*.mp4"))[0]
    f1_dur = ffprobe(f1_video)["duration_s"]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss",
                    f"{f1_dur - 0.2:.3f}", "-i", str(f1_video),
                    "-frames:v", "1", "-update", "1", str(f1_last)],
                   check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "0.2", "-i",
                    str(f3_video), "-frames:v", "1", "-update", "1",
                    str(f3_first)], check=True)
    report["continuity_frames"] = {"f1_last": f1_last.name,
                                   "f3_first": f3_first.name}
    (PKG / "technical_qc_v2_002.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P7_TECH_QC",
                      "candidates": {c: {
                          "decode": report["candidates"][c]["full_decode"],
                          "trim": report["candidates"][c]["trim_compatible"]}
                          for c in report["candidates"]}}))
    return 0


def govern() -> int:
    from film_pipeline.quality_repair_v2 import (
        QualityRepairCandidate, attach_quality_review, build_review_receipt,
        make_candidate, record_technical_validation)
    obs = json.loads((PKG / "observations_v2_002.json").read_text(
        encoding="utf-8"))
    registry = json.loads((PKG / "planned_renders_v2_002.json").read_text(
        encoding="utf-8"))
    cands = candidates()
    governed = []
    mapping = []
    for cid in sorted(cands):
        info = cands[cid]
        o = obs["candidates"][cid]
        candidate = make_candidate(
            source_canonical_take=registry["source_canonical_take"],
            affected_shot="SEQ7_F2C",
            repair_reason=registry["repair_reason"],
            asset_sha256=info["asset_sha256"],
            generation_semantic_identity=info["output_identity"],
            quality_debt_ids=["QD-001"])
        candidate = record_technical_validation(candidate, {
            "decision": "pass",
            "qc_report_id": "qcr_v2002_" + cid.lower(),
            "asset_sha256": info["asset_sha256"],
            "full_decode": o["technical"]["full_decode"],
            "ffprobe": o["technical"]["ffprobe"]})
        review = build_review_receipt(
            candidate=candidate,
            baseline_asset_sha256=BASELINE_VIDEO and file_sha(BASELINE_VIDEO),
            target_dimensions=["ACTION_CAUSALITY"],
            findings=o["findings"],
            review_source="ADVISORY_WORKER",
            target_defect_debt_ids=["QD-001"],
            limitations=o["limitations"])
        candidate = attach_quality_review(
            candidate, review,
            identity_receipt=o["identity_receipt"],
            editorial_compatibility_receipt=o["editorial_receipt"])
        governed.append({"candidate_id": cid,
                         "governed": candidate.model_dump(mode="json"),
                         "review": review.model_dump(mode="json"),
                         "custody": {
                             "asset_sha256": info["asset_sha256"],
                             "asset_id": info["asset_id"],
                             "provider_job_id": info["provider_job_id"],
                             "output_identity": info["output_identity"],
                             "video": str(info["video"].relative_to(ROOT))},
                         "open_observations": o})
        mapping.append({"planned_render_id": next(
            r["planned_render_id"] for r in registry["planned_renders"]
            if r["candidate_id"] == cid),
            "governed_candidate_id": candidate.candidate_id,
            "asset_sha256": info["asset_sha256"],
            "state": candidate.owner_decision_state})
    out = {"version": "quality-v2-002-candidates-governance-v1",
           "checkpoint": "V2002_P10_QUALITY_RECEIPT",
           "source_canonical_take": registry["source_canonical_take"],
           "no_owner_decision_minted": True,
           "no_promotion_executed": True,
           "planned_render_mapping": mapping,
           "candidates": governed}
    (PKG / "candidates_governance_v2_002.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P10_QUALITY_RECEIPT",
                      "states": {m["governed_candidate_id"]: m["state"]
                                 for m in mapping}}))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "evidence":
        raise SystemExit(evidence())
    if cmd == "govern":
        raise SystemExit(govern())
    raise SystemExit("usage: run_v2_002_qc_pipeline.py evidence|govern")
