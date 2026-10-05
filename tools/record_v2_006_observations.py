"""V2-006 P10-P13: record the open A1-A10 / B1-B10 / pair observations
(worker advisory, evidence-based) and run the governance minting
(refusals — the pair cannot be QUALITY_REVIEW_READY)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_006_f2_decomposed_live"
tech = json.loads((PKG / "technical_qc_v2_006.json").read_text(
    encoding="utf-8"))
MANIFEST_ID = ("edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590"
               "654b059c7969d3")


def S(v, ev):
    return {"verdict": v, "evidence": ev}


COMMON_LIMITS = [
 "worker advisory observations; the Owner visual read is authoritative",
 "0.4s strips + full-video watch; no qualified automated spatial QC "
 "backend exists"]

obs = {"version": "v2-006-open-observations-v1",
 "measurement_note": "times measured from the videos and 0.4s strips",
 "candidates": {}}

obs["candidates"]["F2A-V2-006"] = {
 "technical": tech["shots"]["F2A"],
 "spatial_qc": {
  "A1_START_BEFORE_GATE_VISIBLE": S("PASS", [
    "he starts on the open near-side grass; clearly not beyond anything"]),
  "A2_GUST_READABLE": S("PASS", [
    "robes, hair ribbon and hem stream violently throughout"]),
  "A3_FORWARD_COMMIT_READABLE": S("PASS", [
    "he turns and commits toward the gate (~1-3s)"]),
  "A4_DIRECT_PATH_TO_THRESHOLD": S("PASS", [
    "locomotion is a direct approach once committed; an added sword "
    "draw/guard interrupts the action but not the path"]),
  "A5_REACHES_THRESHOLD": S("FAIL", [
    "measured threshold arrival ~6.5s of the 8s render — far outside "
    "the frozen 2.8s usable window (anchor was 2.4s)"]),
  "A6_DOES_NOT_CROSS_FULLY": S("PASS", [
    "he never passes through; he stops AT the gate structure"]),
  "A7_NO_ROCK_INTERACTION": S("PASS", [
    "no rock contact; NOTE: he touches the gate structure at ~7.0s — "
    "an unplanned interaction with a METAL gate"]),
  "A8_NO_REVERSAL": S("PASS", [
    "travel never reverses; NOTE: the render opens back-to-camera "
    "instead of the planned facing-the-gate orientation"]),
  "A9_THRESHOLD_VISIBLE": S("PASS", [
    "the gate becomes clearly visible as he commits"]),
  "A10_END_STATE_AT_THRESHOLD_READABLE": S("FAIL", [
    "within the 2.8s window he is mid-turn with sword drawn — the "
    "at-threshold end state is not readable inside the trim"]),
  "WORLD_CONTINUITY": S("FAIL", [
    "a METAL ornate gate materializes between the rock pillars "
    "(~6.0s) — materially incompatible with the stone-gate world"]),
  "ADDED_ACTION": S("FAIL", [
    "an unplanned sword draw + guard stance (~2.0-5.0s) not in the "
    "frozen beats"])},
 "camera_qc": {"near_side_visible": True, "far_side_visible": False,
   "threshold_visible": True, "trajectory_visible": True,
   "crossing_not_hidden": True, "no_orbit": True,
   "no_axis_reversal": True, "no_geography_collapse": True,
   "rock_not_visual_center": True,
   "note": "camera mechanics clean; the failures are action/timing "
           "layer"},
 "measured": {"threshold_arrival_s": 6.5, "window_s": 2.8},
 "findings": [
  {"dimension": "NARRATIVE_LOGIC", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["story beat preserved; execution failed"]},
  {"dimension": "ACTION_CAUSALITY", "verdict": "UNCHANGED", "severity": "MEDIUM",
   "evidence": ["the commit reads, but the added sword action and "
                "late arrival break the shot's own causal chain"]},
  {"dimension": "SHOT_DESIGN", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["staging near-side as planned"]},
  {"dimension": "IDENTITY", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["face/hair/robes consistent vs canonical"]},
  {"dimension": "BODY_PROPORTION", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["silhouette consistent"]},
  {"dimension": "PERFORMANCE", "verdict": "UNCHANGED", "severity": "LOW",
   "evidence": ["added sword draw/guard not in the frozen beats"]},
  {"dimension": "BLOCKING", "verdict": "REGRESSED", "severity": "MEDIUM",
   "evidence": ["threshold arrival ~6.5s outside the frozen window; "
                "A5/A10 FAIL"]},
  {"dimension": "CAMERA", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["locked, clean"]},
  {"dimension": "TEMPORAL_MOTION", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["motion natural; QD-005 stands"]},
  {"dimension": "EDITORIAL_FIT", "verdict": "REGRESSED", "severity": "MEDIUM",
   "evidence": ["no 2.8s window contains the required end state"]}],
 "target_dimensions": ["ACTION_CAUSALITY", "BLOCKING", "SHOT_DESIGN",
                       "CAMERA"],
 "identity_receipt": {"identity_continuity": "UNCHANGED",
                      "verified_by": "worker-grid-advisory-v1"},
 "editorial_receipt": {"editorial_compatible": False,
   "edit_manifest_id": MANIFEST_ID, "affected_clip_order": 24,
   "trim_compatible": False, "verified_by": "v2-006-editorial-preview-v1",
   "note": "no usable 2.8s window carries the required end state"},
 "limitations": COMMON_LIMITS}

obs["candidates"]["F2B-V2-006"] = {
 "technical": tech["shots"]["F2B"],
 "spatial_qc": {
  "B1_START_ALREADY_CROSSING_OR_BEYOND": S("FAIL", [
    "he opens well in front of a fortress, hero-walking toward camera; "
    "no just-crossed-the-threshold state is readable"]),
  "B2_GATE_BEHIND_SUBJECT": S("PASS", [
    "a massive gate structure is literally behind him (composition "
    "PASS; world identity of that structure FAILS — see world check)"]),
  "B3_MOVEMENT_AWAY_FROM_GATE": S("PASS", [
    "he strides away from the structure behind him"]),
  "B4_ONE_DIRECTION_ONLY": S("PASS", ["single direction throughout"]),
  "B5_FAR_SIDE_REACHED": S("FAIL", [
    "the far side of THE stone gate is unverifiable — the world is a "
    "castle fortress above clouds, not the SEQ7 storm-gate grassland"]),
  "B6_FAR_SIDE_READABLE_BY_2_4S": S("FAIL", [
    "the far-side-of-the-gate state is never readable (wrong world)"]),
  "B7_NO_BEFORE_GATE_RETURN": S("PASS", ["no return movement"]),
  "B8_NO_ROCK_INTERACTION": S("PASS", ["no interaction"]),
  "B9_NO_REVERSAL": S("PASS", ["no reversal"]),
  "B10_END_STATE_DISTINCT_AND_CLEAR": S("FAIL", [
    "the end state is visually distinct but geographically wrong — "
    "not the required FAR_SIDE_CLEAR of the stone gate"]),
  "WORLD_CONTINUITY": S("FAIL", [
    "MATERIAL world drift: castle fortress + lightning + cloud sea "
    "with warm golden light replaces the storm grassland; the "
    "identity-only reference's warm cloud aesthetic leaked into the "
    "render and the thin world semantics let the model invent "
    "geography"]),
  "ADDED_ACTION": S("FAIL", [
    "sword drawn at his side throughout — not in the frozen beats"])},
 "camera_qc": {"near_side_visible": False, "far_side_visible": True,
   "threshold_visible": True, "trajectory_visible": True,
   "crossing_not_hidden": True, "no_orbit": True,
   "no_axis_reversal": True, "no_geography_collapse": False,
   "rock_not_visual_center": False,
   "note": "composition clean; geography collapse is a WORLD failure, "
           "not a camera-mechanics failure"},
 "measured": {"far_side_readable_s": None, "window_s": 2.8},
 "findings": [
  {"dimension": "NARRATIVE_LOGIC", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["onward-momentum reads"]},
  {"dimension": "ACTION_CAUSALITY", "verdict": "UNCHANGED", "severity": "MEDIUM",
   "evidence": ["the crossing consequence cannot read in a world the "
                "audience does not recognize"]},
  {"dimension": "SHOT_DESIGN", "verdict": "REGRESSED", "severity": "HIGH",
   "evidence": ["fortress/cloud world replaces the storm-gate world"]},
  {"dimension": "IDENTITY", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["face/hair/robes consistent — the identity-only "
                "reference DID preserve identity"]},
  {"dimension": "BODY_PROPORTION", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["silhouette consistent"]},
  {"dimension": "PERFORMANCE", "verdict": "UNCHANGED", "severity": "LOW",
   "evidence": ["unscheduled drawn sword"]},
  {"dimension": "BLOCKING", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["movement direction as planned"]},
  {"dimension": "CAMERA", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["locked, clean"]},
  {"dimension": "TEMPORAL_MOTION", "verdict": "UNCHANGED", "severity": "NONE",
   "evidence": ["motion natural; QD-005 stands"]},
  {"dimension": "EDITORIAL_FIT", "verdict": "REGRESSED", "severity": "HIGH",
   "evidence": ["the shot cannot cut into the storm-gate sequence"]}],
 "target_dimensions": ["ACTION_CAUSALITY", "BLOCKING", "SHOT_DESIGN",
                       "CAMERA"],
 "identity_receipt": {"identity_continuity": "UNCHANGED",
                      "verified_by": "worker-grid-advisory-v1"},
 "editorial_receipt": {"editorial_compatible": False,
   "edit_manifest_id": MANIFEST_ID, "affected_clip_order": 24,
   "trim_compatible": False, "verified_by": "v2-006-editorial-preview-v1",
   "note": "world-incompatible; cannot cut into the sequence"},
 "limitations": COMMON_LIMITS}

(PKG / "observations_v2_006.json").write_text(
    json.dumps(obs, indent=1, ensure_ascii=False), encoding="utf-8")

# ---- govern: both refused; the pair cannot be review-ready -----------
from film_pipeline.quality_repair_v2 import make_candidate, \
    record_technical_validation
rebind = json.loads((PKG / "custody_v2_006.json").read_text(
    encoding="utf-8"))
take = rebind["bindings"]["canonical_f2_selected_take"]
gov = {"version": "quality-v2-006-candidates-governance-v1",
       "checkpoint": "V2006_P15_GOVERNANCE",
       "source_canonical_take": take,
       "atomic_pair": {
           "contract": "F2A + F2B is ONE editorial solution",
           "pair_state": "REFUSED",
           "reason": "both shots fail their hard spatial QC; per the "
                     "frozen rule the pair cannot be QUALITY_REVIEW_"
                     "READY",
           "allowed_owner_decisions": ["SELECT_F2A_F2B_PAIR",
                                       "REJECT_ALL", "KEEP_CANONICAL",
                                       "NEEDS_REPAIR", "DEFER"]},
       "no_owner_decision_minted": True,
       "no_promotion_executed": True,
       "candidates": []}
for cid in ("F2A-V2-006", "F2B-V2-006"):
    o = obs["candidates"][cid]
    hard_fails = sorted(k for k, v in o["spatial_qc"].items()
                        if k.startswith(("A", "B"))
                        and v["verdict"] != "PASS")
    scene = ("scene_SCENE_F_STORM_GATE" if cid.startswith("F2A-")
             else "scene_SCENE_F_FAR_SIDE")
    shot_id = ("SEQ7_F2A_V2_006" if cid.startswith("F2A-")
               else "SEQ7_F2B_V2_006")
    result = json.loads(
        (PKG / f"{scene}/shot_{shot_id}/result.json").read_text(
            encoding="utf-8"))
    candidate = make_candidate(
        source_canonical_take=take, affected_shot="SEQ7_F2C",
        repair_reason="F2_DECOMPOSED_PAIR_HALF",
        asset_sha256=result["asset"]["sha256"],
        generation_semantic_identity=result["output_identity"],
        quality_debt_ids=["QD-001"])
    candidate = record_technical_validation(candidate, {
        "decision": "pass",
        "qc_report_id": "qcr_v2006_" + cid.lower(),
        "asset_sha256": result["asset"]["sha256"],
        "full_decode": o["technical"]["full_decode"],
        "ffprobe": o["technical"]["ffprobe"]})
    gov["candidates"].append({
        "candidate_id": cid,
        "governed": candidate.model_dump(mode="json"),
        "state": candidate.owner_decision_state,
        "review_refusal": {"reason": "hard-required spatial checks "
                                     "failed",
                           "hard_fails": hard_fails},
        "custody": {"asset_sha256": result["asset"]["sha256"],
                    "provider_job_id": result["provider_job_id"],
                    "output_identity": result["output_identity"],
                    "video": result["asset"]["uri_or_path"]},
        "spatial_qc": o["spatial_qc"], "camera_qc": o["camera_qc"]})
(PKG / "candidates_governance_v2_006.json").write_text(
    json.dumps(gov, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"checkpoint": "V2006_P15_GOVERNANCE",
                  "pair_state": gov["atomic_pair"]["pair_state"],
                  "refusals": {c["candidate_id"]:
                               c["review_refusal"]["hard_fails"]
                               for c in gov["candidates"]}}))
