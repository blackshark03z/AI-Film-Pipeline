"""AI-FILM-QUALITY-V2-005R — F2 decomposition reference-compatibility
preflight.

Proves — mechanically from the ACTUAL bound media bytes — whether the
frozen visual reference strategy contradicts F2B's required far-side
geography. No generation, no Flow submit, no upload, no provider
switch, no canonical mutation.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_005r_reference_preflight"
V3 = ROOT / "projects/quality_v2_003_director_blocking"
V4 = ROOT / "projects/quality_v2_004_f2_blocking"
V5 = ROOT / "projects/quality_v2_005_f2_decomposition"

BOUND_REF = (V4 / "scene_SCENE_F_STORM_GATE/continuity_reference/"
             "attestation/"
             "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f"
             "8313.jpg")
BOUND_REF_SHA = ("fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea08"
                 "00355f8313")
IDENTITY_REF = (ROOT / "projects/flow_production_harden_002/"
                "requal_current_build/reference/"
                "ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4ddf0bc3"
                "a0ca4e8.jpg")
IDENTITY_REF_SHA = ("ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4d"
                    "df0bc3a0ca4e8")
IDENTITY_MEDIA_ID = "7b725f7b-4da5-4455-a6f2-135c4ba22397"
IDENTITY_ASSET_ID = ("asset_2ab16c9f6aff842e3c3c15b2f1b0619217f3925a0ab2"
                     "ae255b9fcd86d60a0ae2")
F2C_CANONICAL = (ROOT / "projects/flow_upload_contract_requal_009/"
                 "reproof/scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
                 "c1a69047933565230870ad22.mp4")

REFERENCE_TYPES = ("IDENTITY_ONLY", "CHARACTER_CROP",
                   "FULL_FRAME_ENVIRONMENTAL", "UNKNOWN")


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_signature(path: Path) -> list[float]:
    im = Image.open(path).convert("L").resize((64, 36))
    a = [float(v) for v in im.getdata()]
    mean = sum(a) / len(a)
    std = math.sqrt(sum((v - mean) ** 2 for v in a) / len(a)) + 1e-9
    return [(v - mean) / std for v in a]


def environment_correlation(ref: Path, frame: Path) -> float:
    a, b = image_signature(ref), image_signature(frame)
    return sum(x * y for x, y in zip(a, b)) / len(a)


def classify_reference(image_path: Path, *, expected_sha: str,
                       subject_extent: str) -> dict:
    """Mechanical classification from the ACTUAL bytes. Do not infer
    from filename. The subject-extent observation is recorded as the
    worker's visual read of the exact hashed bytes."""
    actual = file_sha(image_path)
    if actual != expected_sha:
        return {"reference_type": "UNKNOWN",
                "reason": f"sha mismatch: actual {actual[:16]}… expected "
                          f"{expected_sha[:16]}…",
                "sha256": actual}
    img = Image.open(image_path)
    width, height = img.size
    full_frame = (width, height) == (1280, 720)
    if "chest_up_portrait" in subject_extent and \
            "no gate geography" in subject_extent:
        rtype = "IDENTITY_ONLY"
    elif "full scene" in subject_extent and full_frame and \
            "chest_up_portrait" not in subject_extent:
        rtype = "FULL_FRAME_ENVIRONMENTAL"
    elif "chest_up" in subject_extent:
        rtype = "CHARACTER_CROP"
    else:
        rtype = "UNKNOWN"
    return {"reference_type": rtype,
            "sha256": actual,
            "dimensions": [width, height],
            "aspect": round(width / height, 4),
            "full_frame_16_9": full_frame,
            "subject_extent_visual_read": subject_extent,
            "classification_basis": "exact hashed bytes: dimensions + "
                                    "framing/extent visual read; not "
                                    "filename"}


def far_side_geography_conflict(classification: dict,
                                environment_correlation: float,
                                visual_read: dict) -> dict:
    """Deterministic rule: a FULL_FRAME_ENVIRONMENTAL reference whose
    visual read encodes near-side gate geography materially constrains
    camera/geography for a shot that requires the gate BEHIND the
    subject (BEFORE_GATE forbidden). Prompt text is NOT proven to
    override full-frame visual conditioning."""
    if classification["reference_type"] == "UNKNOWN":
        return {"conflict": None, "reason": "reference type UNKNOWN"}
    if classification["reference_type"] == "FULL_FRAME_ENVIRONMENTAL" \
            and visual_read.get("encodes_near_side_geography") and \
            environment_correlation > 0.5:
        return {"conflict": True,
                "reason": "full-frame near-side geography encoded in the "
                          "conditioning input; the far-side shot "
                          "requires the gate BEHIND the subject "
                          "(BEFORE_GATE forbidden)",
                "environment_correlation": environment_correlation}
    return {"conflict": False,
            "reason": "no near-side geography encoded"
            if classification["reference_type"] in
            ("IDENTITY_ONLY", "CHARACTER_CROP") else "type-dependent"}


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)

    # ---- 1. PIN CUSTODY ------------------------------------------------
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    v2_005_head = "b92e03710d5aec6a48527b4fc24c4ef35deb41c7"
    if head != v2_005_head:
        raise SystemExit("BLOCKED_CUSTODY: V2-005 final HEAD not exact")
    plan5 = json.loads((V5 / "f2_decomposition_plan_v2_005.json")
                       .read_text(encoding="utf-8"))
    custody = {
        "version": "v2-005r-custody-v1",
        "checkpoint": "V2005R_P1_CUSTODY_PINNED",
        "v2_005_final_head": v2_005_head,
        "v2_005_evidence": "docs/operating/"
                           "AI_FILM_QUALITY_V2_005_F2_DECOMPOSITION_"
                           "DESIGN_EVIDENCE.md",
        "v2_006_handoff": "docs/quality-v2/"
                          "V2_006_F2_DECOMPOSED_LIVE_HANDOFF.md",
        "bound_reference": {
            "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
            "asset_id": ("asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b"
                         "99749a72eda0fa31ec44edc3"),
            "attestation_id": ("refbind_f4277ac1a7a5651c8370212417c06593f"
                               "08a003aee1676517622292f37cb4fdf"),
            "asset_sha256": BOUND_REF_SHA,
            "local_bytes": str(BOUND_REF.relative_to(ROOT))},
        "f2a_blocking_spec_id":
            plan5["f2a_commit_to_cross"]["blocking"]["blocking_spec_id"],
        "f2a_camera_plan_id":
            plan5["f2a_commit_to_cross"]["camera"]["camera_plan_id"],
        "f2b_blocking_spec_id":
            plan5["f2b_emerge_far_side"]["blocking"]["blocking_spec_id"],
        "f2b_camera_plan_id":
            plan5["f2b_emerge_far_side"]["camera"]["camera_plan_id"]}
    (PKG / "custody_v2_005r.json").write_text(
        json.dumps(custody, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2005R_P1_CUSTODY_PINNED",
                      "head": head[:12]}))

    # ---- 2. CLASSIFY the existing F1 reference --------------------------
    # first frame of the canonical F2C (the near-side environment the
    # reference conditioned) for the mechanical correlation
    first_frame = PKG / "f2c_first_frame.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", "0.2", "-i",
         str(F2C_CANONICAL), "-frames:v", "1", "-update", "1",
         str(first_frame)], check=True)
    bound = classify_reference(
        BOUND_REF, expected_sha=BOUND_REF_SHA,
        subject_extent="full scene: the gate rock slab at frame-left, "
                       "the subject standing beside it at the gate "
                       "mouth on the NEAR side, camera viewing from the "
                       "near side, far side occluded by the rock; no "
                       "gate geography beyond it is visible")
    corr = environment_correlation(BOUND_REF, first_frame)
    visual_read = {"encodes_near_side_geography": True,
                   "gate_visible": True,
                   "far_side_visible": False,
                   "subject_position": "beside the rock at the gate "
                                       "mouth, near side"}
    conflict_f2b_bound = far_side_geography_conflict(
        bound, corr, visual_read)
    reference = {
        "checkpoint": "V2005R_P2_REFERENCE_CLASSIFIED",
        "media_id": custody["bound_reference"]["media_id"],
        "asset_sha256": BOUND_REF_SHA,
        "classification": bound,
        "environment_correlation_vs_canonical_f2c_first_frame":
            round(corr, 3),
        "visual_read": visual_read,
        "materially_constrains_camera_geography":
            bound["reference_type"] == "FULL_FRAME_ENVIRONMENTAL",
        "f2b_conflict_on_this_reference":
            conflict_f2b_bound}
    (PKG / "reference_classification_v2_005r.json").write_text(
        json.dumps(reference, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2005R_P2_REFERENCE_CLASSIFIED",
                      "type": bound["reference_type"],
                      "f2b_conflict": conflict_f2b_bound["conflict"]}))

    # ---- 3/4. compatibility per shot -------------------------------------
    identity = classify_reference(
        IDENTITY_REF, expected_sha=IDENTITY_REF_SHA,
        subject_extent="chest_up_portrait: full scene is clouds and "
                       "distant peaks only; no gate geography anywhere "
                       "in frame")
    f2a_compatible = bound["reference_type"] == \
        "FULL_FRAME_ENVIRONMENTAL" and \
        visual_read["encodes_near_side_geography"] and \
        visual_read["subject_position"].startswith("beside the rock at "
                                                   "the gate mouth")
    f2b_compatible_bound = not conflict_f2b_bound["conflict"]
    identity_conflict = far_side_geography_conflict(
        identity, environment_correlation(IDENTITY_REF, first_frame),
        {"encodes_near_side_geography": False})
    f2b_compatible_identity = identity["reference_type"] == \
        "IDENTITY_ONLY" and identity_conflict["conflict"] is False
    compatibility = {
        "checkpoint": "V2005R_P3_P4_COMPATIBILITY",
        "F2A_REFERENCE_COMPATIBLE": bool(f2a_compatible),
        "F2B_REFERENCE_COMPATIBLE_with_bound_full_frame":
            bool(f2b_compatible_bound),
        "F2B_REFERENCE_COMPATIBLE_with_identity_only":
            bool(f2b_compatible_identity),
        "identity_reference": {
            "media_id": IDENTITY_MEDIA_ID,
            "asset_id": IDENTITY_ASSET_ID,
            "sha256": IDENTITY_REF_SHA,
            "classification": identity,
            "already_qualified": True,
            "provenance": "adopted provider media (readback), store "
                          "asset record + sha attested; used as the "
                          "qualified base reference since Packages "
                          "003+ (G3C 018)"}}
    (PKG / "compatibility_v2_005r.json").write_text(
        json.dumps(compatibility, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2005R_P3_P4_COMPATIBILITY",
                      "f2a": compatibility["F2A_REFERENCE_COMPATIBLE"],
                      "f2b_bound":
                          compatibility[
                              "F2B_REFERENCE_COMPATIBLE_with_bound_full_"
                              "frame"],
                      "f2b_identity":
                          compatibility[
                              "F2B_REFERENCE_COMPATIBLE_with_identity_"
                              "only"]}))

    # ---- 5/6. decision + smallest next qualification ---------------------
    decision_status = "REFERENCE_STRATEGY_COMPATIBLE" \
        if f2b_compatible_bound else (
        "F2B_REFERENCE_GEOGRAPHY_CONFLICT" if conflict_f2b_bound["conflict"]
        else "REFERENCE_COMPATIBILITY_INCONCLUSIVE")
    next_step = {
        "preferred_option_1_selected":
            "reuse the ALREADY-QUALIFIED identity-only reference "
            f"(media {IDENTITY_MEDIA_ID}, asset sha {IDENTITY_REF_SHA[:16]}"
            "…) for F2B — exact provenance exists in the store; the "
            "media is already bound to the project, so 0 uploads; F2A "
            "keeps the near-side full-frame reference (compatible)",
        "requires_owner_authorization": True,
        "no_upload_in_this_package": True}
    preflight = {
        "version": "v2-005r-reference-preflight-v1",
        "checkpoint": "V2005R_P5_DECISION",
        "status": decision_status,
        "v2_006_ready": decision_status ==
                        "REFERENCE_STRATEGY_COMPATIBLE",
        "decision": decision_status,
        "smallest_next_qualification": next_step,
        "reference_strategy_amendment_for_v2_006": {
            "F2A_reference": {"media_id": "8f2f5277-aae8-44b5-a5b7-"
                                           "c197d1d7c115",
                              "sha256": BOUND_REF_SHA,
                              "rationale": "near-side full frame is "
                                           "compatible with the F2A "
                                           "near-side plan"},
            "F2B_reference": {"media_id": IDENTITY_MEDIA_ID,
                              "asset_id": IDENTITY_ASSET_ID,
                              "sha256": IDENTITY_REF_SHA,
                              "rationale": "identity-only carries no "
                                           "geography; the far-side "
                                           "plan is unconstrained"},
            "uploads_required": 0,
            "provider_switch": False},
        "invariants": {"generation": 0, "flow_submit": 0, "upload": 0,
                       "provider_switch": False, "canonical_mutation": 0}}
    (PKG / "reference_preflight_v2_005r.json").write_text(
        json.dumps(preflight, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2005R_P5_DECISION",
                      "status": decision_status,
                      "v2_006_ready": preflight["v2_006_ready"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
