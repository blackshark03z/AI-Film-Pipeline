"""AI-FILM-QUALITY-V2-004 — Phases 5-8: technical QC, the PRIMARY
spatial/blocking QC (S1-S13), independent camera QC, and the governed
candidate minting through the frozen V2-001 state machine.

Subcommand `evidence`: deterministic frame evidence for the S-QC
(per-0.4s strips across the crossing window, start/end frames,
threshold annotations). No judgment recorded here.

Subcommand `govern`: after the worker records open observations into
observations_v2_004.json (S1-S13 + camera QC + dimension findings),
mint the governed QualityRepairCandidates. A candidate reaches
QUALITY_REVIEW_READY only if the hard-required S-set passes.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PKG = ROOT / "projects/quality_v2_004_f2_blocking"
SCENE = PKG / "scene_SCENE_F_STORM_GATE"
BASELINE_VIDEO = ROOT / ("projects/flow_upload_contract_requal_009/"
                         "reproof/scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/"
                         "videos/c1a69047933565230870ad22.mp4")

S_HARD_REQUIRED = ["S3_PATH_DIRECT", "S4_NO_ROCK_CONTACT",
                   "S5_NO_ROCK_CIRCLING", "S6_NO_REVERSAL",
                   "S8_FULL_BODY_CROSSES_THRESHOLD",
                   "S9_CROSSING_BY_4_8_SECONDS", "S10_FAR_SIDE_REACHED",
                   "S11_FAR_SIDE_READABLE_BY_5_6",
                   "S12_END_SIDE_DISTINCT_FROM_START",
                   "S13_ROCK_NOT_DESTINATION"]
S_ALL = ["S1_START_SIDE_VISIBLE", "S2_FORWARD_COMMIT_VISIBLE",
         "S3_PATH_DIRECT", "S4_NO_ROCK_CONTACT", "S5_NO_ROCK_CIRCLING",
         "S6_NO_REVERSAL", "S7_GATE_THRESHOLD_VISIBLE",
         "S8_FULL_BODY_CROSSES_THRESHOLD", "S9_CROSSING_BY_4_8_SECONDS",
         "S10_FAR_SIDE_REACHED", "S11_FAR_SIDE_READABLE_BY_5_6",
         "S12_END_SIDE_DISTINCT_FROM_START", "S13_ROCK_NOT_DESTINATION"]


def candidates() -> dict:
    freeze = json.loads((PKG / "experiment_freeze_v2_004.json").read_text(
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


def contact_strip(video: Path, times: list[float], out: Path,
                  tile: int) -> None:
    select = "+".join(f"eq(n\\,{int(t * 24)})" for t in times)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
         f"select='{select}',scale=426:-1,tile={tile}x"
         f"{max(len(times) // tile, 1)}", "-frames:v", "1",
         "-update", "1", str(out)], check=True)


def evidence() -> int:
    ev = PKG / "qc_evidence"
    ev.mkdir(parents=True, exist_ok=True)
    cands = candidates()
    report = {"version": "v2-004-technical-evidence-v1",
              "checkpoint": "V2004_P5_TECH_QC", "candidates": {}}
    for cid, info in cands.items():
        video = info["video"]
        probe = ffprobe(video)
        decode = full_decode(video)
        # crossing-window strip: every 0.4 s from 2.8 s to 6.0 s (the
        # S9/S11 timing evidence), labeled order preserved
        times = [round(2.8 + 0.4 * i, 1) for i in range(9)]
        strip = ev / f"crossing_strip_{cid}.png"
        contact_strip(video, times, strip, 3)
        # early window strip (S1/S2/S7): 0.2-2.6 s
        early_times = [round(0.2 + 0.4 * i, 1) for i in range(7)]
        early = ev / f"early_strip_{cid}.png"
        contact_strip(video, early_times, early, 4)
        start_frame = ev / f"start_{cid}.png"
        end_frame = ev / f"end_{cid}.png"
        for out, t in ((start_frame, 0.2), (end_frame, 5.4)):
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}",
                 "-i", str(video), "-frames:v", "1", "-update", "1",
                 str(out)], check=True)
        report["candidates"][cid] = {
            "asset_sha256": info["asset_sha256"],
            "ffprobe": probe, "full_decode": decode,
            "cfr_fps": probe["fps"],
            "crossing_strip_times_s": times,
            "early_strip_times_s": early_times,
            "artifacts": {"crossing_strip": strip.name,
                          "early_strip": early.name,
                          "start_frame": start_frame.name,
                          "end_frame": end_frame.name}}
    (PKG / "technical_qc_v2_004.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2004_P5_TECH_QC",
                      "candidates": {c: {
                          "decode": report["candidates"][c]["full_decode"],
                          "duration": report["candidates"][c]["ffprobe"][
                              "duration_s"]}
                          for c in report["candidates"]}}))
    return 0


def govern() -> int:
    from film_pipeline.quality_repair_v2 import (
        QualityRepairCandidate, attach_quality_review, build_review_receipt,
        make_candidate, record_technical_validation)
    obs = json.loads((PKG / "observations_v2_004.json").read_text(
        encoding="utf-8"))
    rebind = json.loads((PKG / "rebind_v2_004.json").read_text(
        encoding="utf-8"))
    cands = candidates()
    governed = []
    for cid in sorted(cands):
        info = cands[cid]
        o = obs["candidates"][cid]
        hard_fails = [k for k in S_HARD_REQUIRED
                      if o["spatial_qc"][k]["verdict"] != "PASS"]
        candidate = make_candidate(
            source_canonical_take=rebind["canonical_f2_predecessor"][
                "selected_take_id"],
            affected_shot="SEQ7_F2C",
            repair_reason="DIRECT_BLOCKING_SPATIAL_REPAIR",
            asset_sha256=info["asset_sha256"],
            generation_semantic_identity=info["output_identity"],
            quality_debt_ids=["QD-001"])
        candidate = record_technical_validation(candidate, {
            "decision": "pass",
            "qc_report_id": "qcr_v2004_" + cid.lower(),
            "asset_sha256": info["asset_sha256"],
            "full_decode": o["technical"]["full_decode"],
            "ffprobe": o["technical"]["ffprobe"]})
        if hard_fails:
            governed.append({
                "candidate_id": cid,
                "state": "PROPOSED",
                "review_refusal": {
                    "reason": "hard-required spatial checks failed",
                    "hard_fails": hard_fails},
                "open_observations": o,
                "custody": {
                    "asset_sha256": info["asset_sha256"],
                    "provider_job_id": info["provider_job_id"],
                    "output_identity": info["output_identity"]}})
            continue
        review = build_review_receipt(
            candidate=candidate,
            baseline_asset_sha256=file_sha(BASELINE_VIDEO),
            target_dimensions=o["target_dimensions"],
            findings=o["findings"],
            review_source="ADVISORY_WORKER",
            target_defect_debt_ids=["QD-001"],
            limitations=o["limitations"])
        candidate = attach_quality_review(
            candidate, review,
            identity_receipt=o["identity_receipt"],
            editorial_compatibility_receipt=o["editorial_receipt"])
        governed.append({
            "candidate_id": cid,
            "governed": candidate.model_dump(mode="json"),
            "review": review.model_dump(mode="json"),
            "spatial_qc": o["spatial_qc"],
            "camera_qc": o["camera_qc"],
            "custody": {
                "asset_sha256": info["asset_sha256"],
                "asset_id": info["asset_id"],
                "provider_job_id": info["provider_job_id"],
                "output_identity": info["output_identity"],
                "video": str(info["video"].relative_to(ROOT))}})
    out = {"version": "quality-v2-004-candidates-governance-v1",
           "checkpoint": "V2004_P8_QUALITY_RECEIPT",
           "source_canonical_take": rebind["canonical_f2_predecessor"][
               "selected_take_id"],
           "no_owner_decision_minted": True,
           "no_promotion_executed": True,
           "candidates": governed}
    (PKG / "candidates_governance_v2_004.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2004_P8_QUALITY_RECEIPT",
                      "states": {g["candidate_id"]: g.get(
                          "governed", {}).get("owner_decision_state",
                                              g["state"])
                          for g in governed}}))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "evidence":
        raise SystemExit(evidence())
    if cmd == "govern":
        raise SystemExit(govern())
    raise SystemExit("usage: run_v2_004_qc_pipeline.py evidence|govern")
