"""V2-004 P6-P8: record the open S1-S13 observations (worker advisory,
evidence-based) and run the governance minting."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_004_f2_blocking"
tech = json.loads((PKG / "technical_qc_v2_004.json").read_text(
    encoding="utf-8"))
MANIFEST_ID = ("edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590"
               "654b059c7969d3")


def S(v, ev):
    return {"verdict": v, "evidence": ev}


def dims(causality, blocking, shot_design, perf):
    return [
     {"dimension": "NARRATIVE_LOGIC", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["the story beat (blocked -> passes) is unchanged by "
                   "the spatial repair alone"]},
     {"dimension": "ACTION_CAUSALITY", "verdict": causality,
      "severity": "NONE" if causality == "IMPROVED" else "MEDIUM",
      "evidence": ["advisory; the authoritative hard checks are the "
                   "spatial S-QC verdicts"]},
     {"dimension": "SHOT_DESIGN", "verdict": shot_design,
      "severity": "NONE",
      "evidence": ["staging: standing stones (A) / rectangular doorway "
                   "(B); WS full-shot per the frozen camera plan"]},
     {"dimension": "IDENTITY", "verdict": "UNCHANGED", "severity": "NONE",
      "evidence": ["white robes, white ribbon + topknot, facial features "
                   "consistent vs the canonical baseline"]},
     {"dimension": "BODY_PROPORTION", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["silhouette consistent; no short/compact drift"]},
     {"dimension": "PERFORMANCE", "verdict": perf,
      "severity": "NONE" if perf == "IMPROVED" else "LOW",
      "evidence": ["advisory: B biomechanics read more natural than A; "
                   "both subordinated to the failed traversal"]},
     {"dimension": "BLOCKING", "verdict": blocking,
      "severity": "NONE" if blocking == "IMPROVED" else "MEDIUM",
      "evidence": ["advisory; hard verdicts in S3/S5/S6/S8/S10/S12"]},
     {"dimension": "CAMERA", "verdict": "UNCHANGED", "severity": "NONE",
      "evidence": ["camera mechanics locked, no orbit, no axis reversal, "
                   "geography not collapsed (advisory)"]},
     {"dimension": "TEMPORAL_MOTION", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["crossing-window strips at 0.4s resolution; advisory; "
                   "QD-005 stands"]},
     {"dimension": "EDITORIAL_FIT", "verdict": "UNCHANGED",
      "severity": "NONE",
      "evidence": ["8s renders, 5.6s window trim-compatible; slot "
                   "unchanged"]},
    ]


COMMON_LIMITS = [
 "worker advisory observations; the Owner visual read is authoritative "
 "(V2-002 lesson)",
 "dense 0.4s strips + full-video watch; no qualified automated spatial "
 "QC backend exists"]

obs = {"version": "v2-004-open-observations-v1",
 "measurement_note": "crossing times measured from the deterministic "
                     "0.4s crossing strips (frames 2.8-6.0s)",
 "candidates": {}}

obs["candidates"]["F2C-V2-004-A"] = {
 "technical": {"full_decode":
               tech["candidates"]["F2C-V2-004-A"]["full_decode"],
               "ffprobe": tech["candidates"]["F2C-V2-004-A"]["ffprobe"]},
 "spatial_qc": {
  "S1_START_SIDE_VISIBLE": S("PASS", [
      "he stands at the gate mouth between the stones at t=0"]),
  "S2_FORWARD_COMMIT_VISIBLE": S("PASS", [
      "initial steps commit forward toward camera (~1-3s)"]),
  "S3_PATH_DIRECT": S("FAIL", [
      "path: toward camera -> 180-degree turn at ~4.0s -> back to the "
      "stones; not a direct traversal"]),
  "S4_NO_ROCK_CONTACT": S("PASS", [
      "no hand/body contact with any stone at any time"]),
  "S5_NO_ROCK_CIRCLING": S("PASS", ["no circling around the stones"]),
  "S6_NO_REVERSAL": S("FAIL", [
      "direction reversal at ~4.0s (frontal walk becomes a "
      "back-to-camera walk toward the stones)"]),
  "S7_GATE_THRESHOLD_VISIBLE": S("FAIL", [
      "no distinct threshold boundary is legible; the gap never "
      "functions as a crossed boundary"]),
  "S8_FULL_BODY_CROSSES_THRESHOLD": S("FAIL", [
      "no threshold crossing occurs; he starts in the gap and ends "
      "before the stones"]),
  "S9_CROSSING_BY_4_8_SECONDS": S("FAIL", [
      "no crossing exists to time"]),
  "S10_FAR_SIDE_REACHED": S("FAIL", [
      "no far-side arrival; final state is static facing the stones"]),
  "S11_FAR_SIDE_READABLE_BY_5_6": S("FAIL", [
      "at 5.4-5.6s he is static with his back to the camera before the "
      "stones"]),
  "S12_END_SIDE_DISTINCT_FROM_START": S("FAIL", [
      "start (in the gap) and end (before the stones) are not distinct "
      "opposite sides"]),
  "S13_ROCK_NOT_DESTINATION": S("FAIL", [
      "he ends static, facing the stones — the rocks read as the "
      "focus/destination; the V2-002 loitering failure repeats"])},
 "camera_qc": {"near_side_visible": True, "far_side_visible": True,
   "threshold_visible": False, "trajectory_visible": True,
   "crossing_not_hidden": True, "no_orbit": True,
   "no_axis_reversal": True, "no_geography_collapse": True,
   "rock_not_visual_center": False,
   "note": "camera mechanics locked and clean; the frame is "
           "compromised by the subject never traversing"},
 "measured": {"full_body_crossing_s": None, "far_side_readable_s": None},
 "findings": dims("UNCHANGED", "REGRESSED", "UNCHANGED", "UNCHANGED"),
 "target_dimensions": ["ACTION_CAUSALITY", "BLOCKING", "SHOT_DESIGN",
                       "CAMERA"],
 "identity_receipt": {"identity_continuity": "UNCHANGED",
                      "verified_by": "worker-grid-advisory-v1"},
 "editorial_receipt": {"editorial_compatible": True,
   "edit_manifest_id": MANIFEST_ID, "affected_clip_order": 24,
   "trim_compatible": True, "verified_by": "v2-004-editorial-preview-v1",
   "note": "preview only; canonical EditManifest NOT modified"},
 "limitations": COMMON_LIMITS}

obs["candidates"]["F2C-V2-004-B"] = {
 "technical": {"full_decode":
               tech["candidates"]["F2C-V2-004-B"]["full_decode"],
               "ffprobe": tech["candidates"]["F2C-V2-004-B"]["ffprobe"]},
 "spatial_qc": {
  "S1_START_SIDE_VISIBLE": S("PASS", [
      "he starts at the right pier of the arch; the threshold is "
      "clearly established"]),
  "S2_FORWARD_COMMIT_VISIBLE": S("PASS", [
      "immediate forward commit leftward at ~1.0s, robes streaming"]),
  "S3_PATH_DIRECT": S("FAIL", [
      "overshoots left past the arch (~2.8-3.6s), returns, then "
      "crosses; not the frozen direct path"]),
  "S4_NO_ROCK_CONTACT": S("PASS", [
      "no contact with the arch or rocks at any time"]),
  "S5_NO_ROCK_CIRCLING": S("PASS", ["no circling of the arch"]),
  "S6_NO_REVERSAL": S("FAIL", [
      "mid-shot direction reversal at ~3.6-4.4s (the leftward lunge "
      "reverses into a return to the doorway)"]),
  "S7_GATE_THRESHOLD_VISIBLE": S("PASS", [
      "the rectangular doorway is an unmistakable threshold for the "
      "whole shot"]),
  "S8_FULL_BODY_CROSSES_THRESHOLD": S("PASS", [
      "full body passes through the doorway plane ~5.6-6.0s and "
      "emerges toward camera"]),
  "S9_CROSSING_BY_4_8_SECONDS": S("FAIL", [
      "measured full-body crossing ~5.6-6.0s > the 4.8s deadline"]),
  "S10_FAR_SIDE_REACHED": S("FAIL", [
      "the BEFORE->BEYOND direction semantics are not unambiguously "
      "rendered; the crossing reads toward the camera"]),
  "S11_FAR_SIDE_READABLE_BY_5_6": S("FAIL", [
      "at 5.4-5.6s he is still inside the doorway plane; the settled "
      "far-side state is not yet readable"]),
  "S12_END_SIDE_DISTINCT_FROM_START": S("FAIL", [
      "start (beside the right pier) and end (in front of the opening) "
      "do not read as opposite sides"]),
  "S13_ROCK_NOT_DESTINATION": S("PASS", [
      "the arch reads purely as a passage; he ends moving onward past "
      "it, never treating it as a destination"])},
 "camera_qc": {"near_side_visible": True, "far_side_visible": True,
   "threshold_visible": True, "trajectory_visible": True,
   "crossing_not_hidden": True, "no_orbit": True,
   "no_axis_reversal": True, "no_geography_collapse": True,
   "rock_not_visual_center": True,
   "note": "camera QC PASS overall (independent of the action-quality "
           "judgment): locked, threshold legible, both sides visible"},
 "measured": {"full_body_crossing_s": 5.8, "far_side_readable_s": None},
 "findings": dims("UNCHANGED", "UNCHANGED", "UNCHANGED", "IMPROVED"),
 "target_dimensions": ["ACTION_CAUSALITY", "BLOCKING", "SHOT_DESIGN",
                       "CAMERA"],
 "identity_receipt": {"identity_continuity": "UNCHANGED",
                      "verified_by": "worker-grid-advisory-v1"},
 "editorial_receipt": {"editorial_compatible": True,
   "edit_manifest_id": MANIFEST_ID, "affected_clip_order": 24,
   "trim_compatible": True, "verified_by": "v2-004-editorial-preview-v1",
   "note": "preview only; canonical EditManifest NOT modified"},
 "limitations": COMMON_LIMITS}

(PKG / "observations_v2_004.json").write_text(
    json.dumps(obs, indent=1, ensure_ascii=False), encoding="utf-8")
print("observations recorded")
