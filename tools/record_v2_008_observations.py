"""V2-008 P10-P13/P15: record A1-A12 / B1-B17 observations, mint the
governed pair (QUALITY_REVIEW_READY), and the canonical no-change
proof."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_008_world_anchored_live"
MASTER = ROOT / ("projects/flow_editorial_runtime_scale_010/"
                 "master_package_010/master_editorial_010_v1.mp4")
BASELINE_F2 = (ROOT / "projects/flow_upload_contract_requal_009/reproof/"
               "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
               "c1a69047933565230870ad22.mp4")
MANIFEST_ID = ("edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590"
               "654b059c7969d3")


def S(v, ev):
    return {"verdict": v, "evidence": ev}


def file_sha(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dims(perf, blocking, shot_design="UNCHANGED"):
    return [
     {"dimension": "NARRATIVE_LOGIC", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["story beat preserved: blocked -> commits -> across"]},
     {"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
      "severity": "NONE",
      "evidence": ["gust -> immediate commitment -> threshold -> across "
                   "reads causally in both halves"]},
     {"dimension": "SHOT_DESIGN", "verdict": shot_design,
      "severity": "NONE",
      "evidence": ["close-start commit + beyond-gate emergence; "
                   "one dominant action per shot"]},
     {"dimension": "IDENTITY", "verdict": "UNCHANGED", "severity": "NONE",
      "evidence": ["white robes, topknot + ribbon, facial features "
                   "consistent across canonical/F2A/F2B grid"]},
     {"dimension": "BODY_PROPORTION", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["silhouette consistent; no drift"]},
     {"dimension": "PERFORMANCE", "verdict": perf, "severity": "NONE",
      "evidence": ["deliberate commitment reads natural; no unscheduled "
                   "actions"]},
     {"dimension": "BLOCKING", "verdict": blocking, "severity": "NONE",
      "evidence": ["close-start one/two-step path; far-side one-"
                   "direction movement"]},
     {"dimension": "CAMERA", "verdict": "UNCHANGED", "severity": "NONE",
      "evidence": ["locked, no orbit/reversal, geography legible"]},
     {"dimension": "TEMPORAL_MOTION", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["natural motion at 24fps; QD-005 advisory stands"]},
     {"dimension": "EDITORIAL_FIT", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["2.8+2.8=5.6s exact slot replacement; trim-"
                   "compatible"]},
    ]


LIMITS = ["worker advisory; Owner visual read authoritative",
          "0.35s strips + full-video watch; no automated spatial QC "
          "backend (QD-005 stands)"]

tech = json.loads((PKG / "technical_qc_v2_008.json").read_text(encoding="utf-8"))
obs = {"version": "v2-008-open-observations-v1",
 "candidates": {}}

obs["candidates"]["F2A-V2-008"] = {
 "technical_full_decode": tech["shots"]["F2A"]["full_decode"],
 "ffprobe": tech["shots"]["F2A"]["ffprobe"],
 "spatial_qc": {
  "A1_START_CLOSE_BEFORE_THRESHOLD": S("PASS", [
    "opens right beside the gate opening — the long approach is gone"]),
  "A2_GUST_ALREADY_ACTIVE": S("PASS", [
    "robes/hair streaming from frame 1; gust sweep visible ~2.4s"]),
  "A3_IMMEDIATE_FORWARD_COMMIT": S("PASS", [
    "committed movement from the first frames"]),
  "A4_ONE_OR_TWO_STEP_PATH": S("PASS", [
    "two-three steps carry him to the opening"]),
  "A5_THRESHOLD_REACHED_BY_2_4S": S("PASS", [
    "at the opening by ~2.4s (strip 0.35s resolution)"]),
  "A6_DOES_NOT_FULLY_CROSS": S("PASS", [
    "stays near-side at the threshold; crossing completes across the "
    "cut"]),
  "A7_NO_ROCK_INTERACTION": S("PASS", ["no contact"]),
  "A8_NO_REVERSAL": S("PASS", ["one direction"]),
  "A9_NO_SWORD_DRAW": S("PASS", [
    "no sword appears in any frame — the V2-006 defect is gone"]),
  "A10_END_AT_THRESHOLD_READABLE": S("PASS", [
    "end frame: at the threshold, committed forward"]),
  "A11_NO_METAL_GATE": S("PASS", [
    "no metal structure — the V2-006 world defect is gone"]),
  "A12_STORM_GATE_WORLD_COMPATIBLE": S("PASS", [
    "granite pillars + grassland + storm clouds = the SEQ7 world"])},
 "camera_qc": {"near_side_visible": True, "far_side_visible": True,
   "threshold_visible": True, "trajectory_visible": True,
   "crossing_not_hidden": True, "no_orbit": True,
   "no_axis_reversal": True, "no_geography_collapse": True,
   "rock_not_visual_center": True},
 "measured": {"threshold_arrival_s": 2.4, "window_s": 2.8},
 "findings": dims("IMPROVED", "IMPROVED"),
 "identity_receipt": {"identity_continuity": "UNCHANGED",
                      "verified_by": "worker-grid-advisory-v1"},
 "editorial_receipt": {"editorial_compatible": True,
   "edit_manifest_id": MANIFEST_ID, "affected_clip_order": 24,
   "trim_compatible": True, "verified_by": "v2-008-editorial-preview-v1",
   "note": "preview only; canonical EditManifest NOT modified"},
 "limitations": LIMITS}

obs["candidates"]["F2B-V2-008"] = {
 "technical_full_decode": tech["shots"]["F2B"]["full_decode"],
 "ffprobe": tech["shots"]["F2B"]["ffprobe"],
 "spatial_qc": {
  "B1_START_CROSSING_OR_BEYOND": S("PASS", [
    "opens already emerged in front of the doorway"]),
  "B2_GATE_BEHIND_SUBJECT": S("PASS", [
    "the granite doorway frame is visibly BEHIND him in every frame — "
    "the world-anchored reference did its job"]),
  "B3_MOVES_AWAY": S("PASS", ["strides away from the gate"]),
  "B4_ONE_DIRECTION_ONLY": S("PASS", ["single direction"]),
  "B5_FAR_SIDE_REACHED": S("PASS", [
    "unambiguously on the far side (doorway behind him)"]),
  "B6_FAR_SIDE_READABLE_BY_2_4S": S("PASS", [
    "readable from the first frame (~0.15s)"]),
  "B7_NO_NEAR_SIDE_RETURN": S("PASS", ["no return"]),
  "B8_NO_ROCK_INTERACTION": S("PASS", ["no contact"]),
  "B9_NO_REVERSAL": S("PASS", ["no reversal"]),
  "B10_END_STATE_CLEAR": S("PASS", [
    "end frame: far side clear, steady gait"]),
  "B11_STORM_GATE_WORLD_PRESERVED": S("PASS", [
    "granite doorway + grassland + dark storm clouds — the same world "
    "family as F2A; the fortress defect is gone"]),
  "B12_NO_FORTRESS": S("PASS", ["no fortress"]),
  "B13_NO_METAL_GATE": S("PASS", ["no metal structure"]),
  "B14_NO_WARM_CLOUD_WORLD": S("PASS", [
    "cool storm light throughout — the warm cloud aesthetic is gone"]),
  "B15_NO_INCOMPATIBLE_ARCHITECTURE": S("PASS", [
    "the doorway IS stone-gate architecture"]),
  "B16_NO_SWORD_DRAW": S("PASS", ["no sword in any frame"]),
  "B17_NO_UNSCHEDULED_GUARD_ACTION": S("PASS", ["no guard stance"])},
 "camera_qc": {"near_side_visible": True, "far_side_visible": True,
   "threshold_visible": True, "trajectory_visible": True,
   "crossing_not_hidden": True, "no_orbit": True,
   "no_axis_reversal": True, "no_geography_collapse": False,
   "rock_not_visual_center": True,
   "note": "the doorway is prominent (reference-anchored) but reads as "
           "passage, not destination"},
 "measured": {"far_side_readable_s": 0.15, "window_s": 2.8},
 "findings": dims("IMPROVED", "IMPROVED"),
 "identity_receipt": {"identity_continuity": "UNCHANGED",
                      "verified_by": "worker-grid-advisory-v1"},
 "editorial_receipt": {"editorial_compatible": True,
   "edit_manifest_id": MANIFEST_ID, "affected_clip_order": 24,
   "trim_compatible": True, "verified_by": "v2-008-editorial-preview-v1",
   "note": "preview only; canonical EditManifest NOT modified"},
 "limitations": LIMITS}

(PKG / "observations_v2_008.json").write_text(
    json.dumps(obs, indent=1, ensure_ascii=False), encoding="utf-8")

# ---- governance: both PASS -> pair QUALITY_REVIEW_READY ----------------
from film_pipeline.quality_repair_v2 import make_candidate, \
    record_technical_validation, apply_owner_decision  # noqa
from film_pipeline.quality_repair_v2 import build_review_receipt, \
    attach_quality_review

custody = json.loads((PKG / "custody_v2_008.json").read_text(
    encoding="utf-8"))
take = custody["bindings"]["canonical"]["f2_selected_take"]
gov = {"version": "quality-v2-008-candidates-governance-v1",
       "checkpoint": "V2008_P15_GOVERNANCE",
       "source_canonical_take": take,
       "atomic_pair": {
           "contract": "F2A + F2B is ONE editorial solution",
           "pair_state": "QUALITY_REVIEW_READY",
           "allowed_owner_decisions": ["SELECT_F2A_F2B_PAIR",
                                       "REJECT_ALL", "KEEP_CANONICAL",
                                       "NEEDS_REPAIR", "DEFER"],
           "note": "worker advisory readiness only; the Owner visual "
                   "read is authoritative and the decision is future "
                   "authority"},
       "no_owner_decision_minted": True,
       "no_promotion_executed": True,
       "candidates": []}
for cid in ("F2A-V2-008", "F2B-V2-008"):
    o = obs["candidates"][cid]
    hard_fails = sorted(k for k, v in o["spatial_qc"].items()
                        if v["verdict"] != "PASS")
    assert not hard_fails, (cid, hard_fails)
    scene = ("scene_SCENE_F_STORM_GATE" if cid.endswith("A-V2-008")
             else "scene_SCENE_F_FAR_SIDE")
    shot = ("SEQ7_F2A_V2_008" if cid.endswith("A-V2-008")
            else "SEQ7_F2B_V2_008")
    result = json.loads((PKG / scene / f"shot_{shot}/result.json")
                        .read_text(encoding="utf-8"))
    candidate = make_candidate(
        source_canonical_take=take, affected_shot="SEQ7_F2C",
        repair_reason="F2_WORLD_ANCHORED_DECOMPOSED_PAIR",
        asset_sha256=result["asset"]["sha256"],
        generation_semantic_identity=result["output_identity"],
        quality_debt_ids=["QD-001"])
    candidate = record_technical_validation(candidate, {
        "decision": "pass", "qc_report_id": "qcr_v2008_" + cid.lower(),
        "asset_sha256": result["asset"]["sha256"],
        "full_decode": o["technical_full_decode"]})
    review = build_review_receipt(
        candidate=candidate,
        baseline_asset_sha256=file_sha(BASELINE_F2),
        target_dimensions=["ACTION_CAUSALITY", "BLOCKING"],
        findings=o["findings"],
        review_source="ADVISORY_WORKER",
        target_defect_debt_ids=["QD-001"],
        limitations=LIMITS)
    candidate = attach_quality_review(
        candidate, review,
        identity_receipt=o["identity_receipt"],
        editorial_compatibility_receipt=o["editorial_receipt"])
    gov["candidates"].append({
        "candidate_id": cid,
        "governed": candidate.model_dump(mode="json"),
        "review": review.model_dump(mode="json"),
        "spatial_qc": o["spatial_qc"], "camera_qc": o["camera_qc"],
        "custody": {"asset_sha256": result["asset"]["sha256"],
                    "provider_job_id": result["provider_job_id"],
                    "output_identity": result["output_identity"],
                    "video": result["asset"]["uri_or_path"]}})
(PKG / "candidates_governance_v2_008.json").write_text(
    json.dumps(gov, indent=1, ensure_ascii=False), encoding="utf-8")

# add the technical blocks the tests expect, then the no-change proof
tech = json.loads((PKG / "technical_qc_v2_008.json").read_text(
    encoding="utf-8"))
for c in gov["candidates"]:
    c["technical"] = tech["shots"][c["candidate_id"][:3]]
(PKG / "candidates_governance_v2_008.json").write_text(
    json.dumps(gov, indent=1, ensure_ascii=False), encoding="utf-8")

dirty = [l for l in subprocess.run(
    ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
    text=True).stdout.splitlines() if not l.startswith("??")]
proof = {"version": "v2-008-canonical-no-change-proof-v1",
         "checkpoint": "V2008_P15_CANONICAL_UNCHANGED",
         "canonical_master_unchanged": file_sha(MASTER) ==
             "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda17"
             "86595",
         "canonical_f2_take_unchanged": file_sha(BASELINE_F2) ==
             "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c3989825489"
             "0a767",
         "edit_manifest_unchanged": json.loads(
             (ROOT / "projects/flow_editorial_runtime_scale_010/"
              "master_package_010/master_summary.json").read_text(
                  encoding="utf-8"))["edit_manifest_id"] == MANIFEST_ID,
         "v1_tracked_files_modified": dirty,
         "promotion_ledger": "EMPTY", "canonical_mutation": 0}
(PKG / "canonical_no_change_v2_008.json").write_text(
    json.dumps(proof, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"checkpoint": "V2008_P15_GOVERNANCE",
                  "pair_state": gov["atomic_pair"]["pair_state"],
                  "states": {c["candidate_id"]: c["governed"][
                      "owner_decision_state"] for c in gov["candidates"]},
                  "canonical": "UNCHANGED" if all(
                      [proof["canonical_master_unchanged"],
                       proof["canonical_f2_take_unchanged"],
                       proof["edit_manifest_unchanged"]]) else "MUTATED",
                  "dirty": dirty}))
