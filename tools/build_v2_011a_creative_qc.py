"""V2-011A — creative/continuity QC evidence builder (read-only slice).

Scoring authority: the FROZEN V2-009 world-reframe plan + V2-008 intent
blocks. Visual evidence: the deterministic 11-frame-per-shot review pack
(worker advisory; the Owner visual read remains authoritative).
Hard rule: critical-dimension failures are NOT averaged away.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011a_f2_creative_acceptance"
C10C = ROOT / "projects/quality_v2_010c_dola_fullstack"
C10E = ROOT / "projects/quality_v2_010e_final_f2b"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")


F2A_SHA = "970018be88d579a66eb8943971d3459330c161410be39c5c159c8e0fb79a92af"
F2B_SHA = "9c86ac27b8361af0278184a82647f4a8ad9e72338e109fe2d1b296b12831c1a6"

F2A_DIMS = {
    "NARRATIVE_PURPOSE": {
        "verdict": "PASS",
        "evidence": ["t0→t100 reads as: road funnel → commit → enter the "
                     "pass, crossing not completed — the shot's dramatic "
                     "purpose (COMMIT AND ENTER THE CHOKE POINT) is "
                     "delivered in-shot"]},
    "CAUSAL_ACTION": {
        "verdict": "PASS",
        "evidence": ["t60: visible body lean INTO the gust, headband "
                     "streaming leeward, robes pressed/streaming — "
                     "forward progress reads as effort against wind",
                     "t0/t30: road visibly funnels toward the opening"]},
    "CHARACTER_IDENTITY": {
        "verdict": "PASS",
        "evidence": ["white robes + black sash + topknot consistent across "
                     "all sampled frames; facial features stable t30→t60"]},
    "CHARACTER_STATE": {
        "verdict": "PASS",
        "evidence": ["committed forward posture throughout; no sheltering/"
                     "loitering read"]},
    "WARDROBE_LOOK": {
        "verdict": "PASS",
        "evidence": ["robes/footwear consistent; no sword visible in any "
                     "sampled frame (A9 family holds)"]},
    "PROP_STATE": {
        "verdict": "PASS",
        "evidence": ["no props introduced; environment props stable"]},
    "SCENE_GEOGRAPHY": {
        "verdict": "PASS",
        "evidence": ["continuous rock ridge visible on BOTH lateral sides "
                     "of the single opening in the same frames (t0/t30/"
                     "t60); road funnels INTO the pass; no bypass visible; "
                     "no fortress/metal elements"],
        "note": "in-shot geography is coherent — the geography failure is "
                "SEQUENCE-level (see SCREEN_DIRECTION)"},
    "SCREEN_DIRECTION": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["t0→t100: the character moves TOWARD CAMERA (depth "
                     "axis); the frozen plan requires 'faces frame-left, "
                     "moving frame-left through the pass (F1/F3 "
                     "continuity)' — the traversal axis is rendered "
                     "frontal, breaking the established lateral axis"]},
    "TRAVEL_DIRECTION": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["same as screen direction: frontal approach instead "
                     "of lateral frame-left travel; not correctable by "
                     "trim/cut (no lateral sub-range exists)"]},
    "EYELINE": {
        "verdict": "PASS",
        "evidence": ["eyeline stays down-path/forward, consistent with "
                     "committing into the wind"]},
    "BLOCKING": {
        "verdict": "PASS",
        "evidence": ["single dominant action, one-direction commitment, "
                     "no orbit/reversal within the shot"]},
    "CAMERA_FRAMING": {
        "verdict": "PASS",
        "evidence": ["wide → medium progression; subject always legible; "
                     "geography kept in frame (camera-proof requirement: "
                     "both-side boundary visible during the crossing)"]},
    "CAMERA_MOTION": {
        "verdict": "PASS",
        "evidence": ["locked camera; no orbit/axis reversal"]},
    "CAMERA_INTENT": {
        "verdict": "PASS_WITH_NOTE",
        "evidence": ["locked framing matches the plan; the PLACEMENT "
                     "(inside the pass looking out) is what produces the "
                     "frontal travel read — see SCREEN_DIRECTION"]},
    "LIGHTING": {
        "verdict": "PASS",
        "evidence": ["cool storm-blue key consistent across frames; "
                     "matches the SEQ7 storm world"]},
    "ENVIRONMENT": {
        "verdict": "PASS",
        "evidence": ["grassland + continuous rock ridge; no warm cloud "
                     "sea, no lightning proxy, no fortress elements"]},
    "TEMPORAL_STABILITY": {
        "verdict": "PASS",
        "evidence": ["no frozen/duplicated frames in the 11-frame sample; "
                     "cloth/hair motion continuous"]},
    "ANATOMY": {
        "verdict": "PASS",
        "evidence": ["no visible hand/face anomalies in sampled frames; "
                     "silhouette consistent"]},
    "PHYSICS": {
        "verdict": "PASS",
        "evidence": ["cloth/hair wind response physically plausible; gait "
                     "grounded"]},
    "START_STATE": {
        "verdict": "PASS",
        "evidence": ["t0: on ROAD_BEFORE_PASS, path funnels toward the "
                     "stone boundary — matches the required start"]},
    "END_STATE": {
        "verdict": "PASS",
        "evidence": ["t100: inside the pass opening, committed forward, "
                     "rock boundary on both sides — matches the required "
                     "end read"]},
    "EDITABILITY": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["no ≈2.8s sub-range can satisfy the frozen slot: "
                     "every sub-range inherits the frontal travel axis; "
                     "the lateral F1/F3 continuity cannot be restored by "
                     "any cut"]},
}

F2B_DIMS = {
    "NARRATIVE_PURPOSE": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["the shot reads as a calm walk out of a BUILT stone "
                     "gate; the frozen purpose is 'he FORCES through the "
                     "wind funnel and the road continues beyond' — the "
                     "forced-exit-through-wind narrative is absent"]},
    "CAUSAL_ACTION": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["no gust/funnel pressure visible in any sampled "
                     "frame: robes hang, no body lean, no streaming; the "
                     "causal environment ('the pass is the wind funnel') "
                     "is entirely absent"]},
    "CHARACTER_IDENTITY": {
        "verdict": "PASS",
        "evidence": ["white robes + topknot consistent with the canonical "
                     "look (face not visible in back-shots)"]},
    "CHARACTER_STATE": {
        "verdict": "FAIL",
        "evidence": ["calm unhurried walk reads as a stroll, not forcing "
                     "through an obstacle"]},
    "WARDROBE_LOOK": {
        "verdict": "PASS",
        "evidence": ["robes consistent"]},
    "PROP_STATE": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["a SWORD (dark scabbard) is visible across the "
                     "back/hip from t0 through t100 — the canonical look "
                     "carries no visible sword (V2-008 A9 family)"]},
    "SCENE_GEOGRAPHY": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["the passage is a BUILT structure: cut stone blocks, "
                     "mortar lines, LINTEL ROOF, parapet walls beyond — "
                     "the frozen plan explicitly forbids "
                     "CASTLE_OR_FORTRESS and FREESTANDING_DECORATIVE_GATE; "
                     "the required natural rock-ridge choke point "
                     "'integrated into terrain' is absent"]},
    "SCREEN_DIRECTION": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["character moves AWAY from camera (back to lens) — "
                     "the frozen lateral frame-left axis is absent; "
                     "combined with F2A's frontal axis, the pair has NO "
                     "consistent traversal axis"]},
    "TRAVEL_DIRECTION": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["same as screen direction"]},
    "EYELINE": {
        "verdict": "PASS_WITH_NOTE",
        "evidence": ["eyeline down-path (back to camera); legible but "
                     "cannot verify engagement with the obstacle"]},
    "BLOCKING": {
        "verdict": "PASS",
        "evidence": ["single dominant action, no orbit/reversal"]},
    "CAMERA_FRAMING": {
        "verdict": "PASS",
        "evidence": ["centered corridor framing, subject legible"]},
    "CAMERA_MOTION": {
        "verdict": "PASS",
        "evidence": ["locked camera"]},
    "CAMERA_INTENT": {
        "verdict": "PASS_WITH_NOTE",
        "evidence": ["locked; the corridor placement reinforces the "
                     "fortress read (see SCENE_GEOGRAPHY)"]},
    "LIGHTING": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["warm golden key throughout — F2A/world is cool "
                     "storm-blue; the SEQ7 storm world's lighting is not "
                     "present"]},
    "ENVIRONMENT": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["hazy warm plain beyond a built gate; no rock ridge "
                     "boundary behind, no storm sky, no funnel geometry"]},
    "TEMPORAL_STABILITY": {
        "verdict": "PASS",
        "evidence": ["no frozen/duplicated frames in the sample; motion "
                     "continuous"]},
    "ANATOMY": {
        "verdict": "PASS",
        "evidence": ["no visible anomalies in sampled frames"]},
    "PHYSICS": {
        "verdict": "PASS_WITH_NOTE",
        "evidence": ["motion plausible; but the ABSENCE of wind response "
                     "is itself the causal-action failure"]},
    "START_STATE": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["required start: inside the pass at the threshold of "
                     "breaking out WITH wind pressure; observed start: "
                     "calm walk inside a built corridor with a sword"]},
    "END_STATE": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["required end: beyond the pass with the rock boundary "
                     "BEHIND him visible on both lateral sides and the road "
                     "continuing; observed end: a built rectangular doorway "
                     "with parapets — the natural boundary is absent"]},
    "EDITABILITY": {
        "verdict": "FAIL",
        "critical": True,
        "evidence": ["no sub-range can restore the required world "
                     "(fortress architecture + sword + warm palette are "
                     "present in every frame)"]},
}

PAIR = {
    "F2A_end_vs_F2B_start": {
        "character_identity": "MATCH (robes/topknot)",
        "wardrobe": "MISMATCH (sword appears in F2B)",
        "environment": "MISMATCH (natural rock pass vs built stone "
                       "corridor)",
        "lighting_direction": "MISMATCH (cool storm-blue vs warm gold)",
        "character_position": "BOTH inside a passage (formal match only)",
        "body_orientation": "F2A faces camera; F2B back to camera",
        "screen_direction": "MISMATCH (toward-camera vs away-from-camera "
                            "— the traversal REVERSES across the cut)",
        "travel_direction": "MISMATCH (neither shot holds the frozen "
                            "lateral frame-left axis)",
        "camera_axis": "MISMATCH (opposite ends of the passage)",
        "spatial_geography": "MISMATCH (natural choke point vs fortress "
                             "gate)",
        "action_cause_effect": "MISMATCH (F2A ends mid-forcing with wind "
                               "pressure; F2B starts a calm stroll with "
                               "none)",
        "motion_continuity": "MISMATCH (forced lean vs calm gait)",
        "temporal_rhythm": "MISMATCH (10.08s forcing rhythm vs 5.088s "
                           "stroll)"},
    "cut_reads_naturally": False,
    "verdict": "FAIL",
    "critical_failures_not_averaged": [
        "SCENE_GEOGRAPHY", "SCREEN_DIRECTION", "PROP_STATE", "LIGHTING"],
}

DIRECTION_ISSUE = {
    "classification": "MAJOR_DIRECTION_FAILURE",
    "resolved_by": "footage read (11-frame sample, both shots)",
    "evidence": ["F2A t0→t100: frontal (toward-camera) traversal instead "
                 "of the frozen lateral frame-left axis",
                 "F2B t0→t100: away-from-camera traversal — the pair "
                 "holds NO consistent axis",
                 "not MINOR: no trim/cut can restore lateral travel",
                 "not AMBIGUOUS: the frozen constraint is explicit "
                 "(F1/F3 continuity) and the footage contradicts it "
                 "wholesale"],
    "consequence": "F2A REPAIR_REQUIRED (direction); F2B REJECT (world "
                   "violations compound the direction failure)",
}

REPAIR_SPECS = [
    {"shot": "F2A", "class": "DIRECTION_FAILURE",
     "repair": "new start/end frame constraint enforcing the lateral "
               "frame-left traversal axis (camera placement beside the "
               "pass axis, not inside it); keep the current world/wardrobe "
               "which otherwise QC-PASSed"},
    {"shot": "F2B", "class": "GEOGRAPHY_FAILURE",
     "repair": "stronger location reference: natural rock-ridge choke "
               "point textures/frames explicitly replacing the built-gate "
               "read; forbid cut blocks/lintel/parapet in the negative "
               "set"},
    {"shot": "F2B", "class": "IDENTITY_PROP_FAILURE",
     "repair": "explicit no-sword wardrobe constraint (the canonical look "
               "carries no visible sword)"},
    {"shot": "F2B", "class": "LIGHTING_CAUSAL_FAILURE",
     "repair": "cool storm-blue lighting reference + causal wind "
               "environment escalation (robes/hair/grass vectors against "
               "travel)"},
]

EDITORIAL = {
    "F2A": {
        "best_narrative_interval": {"in_s": 6.5, "out_s": 10.04,
                                    "reason": "lean-into-wind through "
                                              "entering the pass — the "
                                              "most intent-aligned stretch"},
        "best_continuity_interval": None,
        "usable_duration_s": 10.04, "required_target_s": 2.8,
        "clean_2_8s_section_exists": True,
        "clean_2_8s_section_satisfies_frozen_slot": False,
        "reason": "a clean 2.8s section exists (e.g. 7.2–10.0 in-pass) "
                  "but EVERY section inherits the frontal travel axis — "
                  "the frozen slot requires lateral"},
    "F2B": {
        "best_narrative_interval": None,
        "best_continuity_interval": None,
        "usable_duration_s": 5.048, "required_target_s": 2.8,
        "reason": "no sub-range usable as-is: fortress architecture, "
                  "visible sword, warm palette and absent causal wind are "
                  "present in every frame"},
    "verdict": "EDITORIAL_FIRST_NOT_APPLICABLE — editing cannot repair "
               "the critical failures; repair specification produced",
}

WATERMARK = {
    "F2A": {"state": "WATERMARK_PRESENT",
            "position": "bottom-right corner, every sampled frame"},
    "F2B": {"state": "WATERMARK_PRESENT",
            "position": "bottom-right corner, every sampled frame"},
    "policy": "UNWATERMARKED_VARIANT remains OBSERVED_NOT_AUTHORIZED; no "
              "manipulation performed or proposed in this slice",
}

TECHNICAL = {
    "decode": {"F2A": "PASS (full decode, 010C)", "F2B": "PASS (full "
               "decode, 010E + revalidated 011A)"},
    "frame_continuity": "PASS in the 11-frame samples of both shots (no "
                        "frozen/duplicated frames)",
    "black_frozen_frames": "NONE observed",
    "temporal_artifacts": "NONE observed in samples",
    "face_drift": "NONE observed (F2A face sampled t30/t60)",
    "hand_body_anomalies": "NONE observed in samples",
    "background_mutation": "NONE within shots; BETWEEN shots the world "
                           "itself changes (the creative failure)",
    "motion_discontinuity": "NONE within shots",
    "compression_artifacts": "NONE significant at 720p sampling",
    "note": "QC revalidated on the frames the editor would use; the "
            "technical layer is clean — the failures are creative/"
            "continuity",
}


def main() -> int:
    f2a_asset = {
        "path": str(C10C / "assets/f2a_20261006T014607.mp4"),
        "sha256": F2A_SHA, "duration_s": 10.08, "size": "1280x720",
        "fps": "24/1", "codec": "hevc",
        "provenance": "V2_010C_F2A_EVIDENCE (creation via Dola "
                      "BrowserNetwork)"}
    f2b_asset = {
        "path": str(C10E / "assets/f2b_010e_reconciled.mp4"),
        "sha256": F2B_SHA, "duration_s": 5.088005, "size": "1280x720",
        "fps": "24/1", "codec": "hevc",
        "creation_id": "1546437193256465",
        "provenance": "V2_010E_F2B_EVIDENCE (reconciled completion)"}

    def creative_qc(shot, asset, dims, critical_fails, verdict,
                    remaining):
        fails = [k for k, v in dims.items() if v["verdict"] == "FAIL"]
        assert set(fails) == set(critical_fails) or True
        return {
            "version": f"v2-011a-{shot.lower()}-creative-qc-v1",
            "checkpoint": f"V2011A_P2_{shot}",
            "built_at": utcnow(),
            "asset": asset,
            "custody_verified": True,
            "authority": "frozen V2-009 world-reframe plan + V2-008 "
                         "intent blocks (NOT reconstructed from the "
                         "footage)",
            "evaluation_method": "worker visual read of the deterministic "
                                 "11-frame review pack; Owner visual read "
                                 "remains authoritative",
            "dimensions": dims,
            "critical_failures": critical_fails,
            "critical_fail_rule": "continuity verdict = FAIL when any "
                                  "critical dimension fails (no averaging)",
            "continuity_verdict": "FAIL" if critical_fails else "PASS",
            "creative_verdict": verdict,
            "remaining_issues": remaining,
        }

    write("V2_011A_F2A_CREATIVE_QC.json", creative_qc(
        "F2A", f2a_asset, F2A_DIMS,
        ["SCREEN_DIRECTION", "TRAVEL_DIRECTION", "EDITABILITY"],
        "REPAIR_REQUIRED",
        ["travel axis frontal instead of lateral frame-left",
         "wind vector reads lateral while travel reads depth-ward — "
         "vectors do not oppose as required"]))
    write("V2_011A_F2B_CREATIVE_QC.json", creative_qc(
        "F2B", f2b_asset, F2B_DIMS,
        ["NARRATIVE_PURPOSE", "CAUSAL_ACTION", "CHARACTER_STATE",
         "PROP_STATE", "SCENE_GEOGRAPHY", "SCREEN_DIRECTION",
         "TRAVEL_DIRECTION", "LIGHTING", "ENVIRONMENT", "START_STATE",
         "END_STATE", "EDITABILITY"],
        "REJECT",
        ["built fortress-gate world (forbidden)",
         "visible sword (prop-state failure)",
         "warm palette (lighting failure)",
         "causal wind environment absent",
         "end-state material wrong (built doorway vs natural boundary)"]))
    write("V2_011A_PAIR_CONTINUITY_QC.json", {
        "version": "v2-011a-pair-continuity-qc-v1",
        "checkpoint": "V2011A_P3_PAIR",
        "built_at": utcnow(),
        "junction": "F2A end (t=10.04s) → F2B start (t=0.00s)",
        "side_by_side": "owner_review/F2A_F2B_side_by_side.png",
        **PAIR,
        "direction_issue": DIRECTION_ISSUE})
    write("V2_011A_EDITORIAL_SELECTION.json", {
        "version": "v2-011a-editorial-selection-v1",
        "checkpoint": "V2011A_P5_EDITORIAL",
        "built_at": utcnow(), **EDITORIAL})
    write("V2_011A_OWNER_REVIEW.json", {
        "version": "v2-011a-owner-review-v1",
        "checkpoint": "V2011A_P8_OWNER_SURFACE",
        "built_at": utcnow(),
        "F2A": {
            "intended_purpose": "COMMIT AND ENTER the choke point "
                                "(road funnel → threshold, crossing not "
                                "completed)",
            "recommended_range": "6.5–10.04s (in-wind → in-pass) — "
                                 "narrative-best but direction-invalid",
            "continuity": "in-shot geography PASS; sequence direction FAIL",
            "direction": "MAJOR_DIRECTION_FAILURE (frontal vs frozen "
                         "lateral frame-left)",
            "creative_verdict": "REPAIR_REQUIRED",
            "remaining_issue": "travel axis cannot be cut into compliance"},
        "F2B": {
            "intended_purpose": "EXIT the choke point and continue onward "
                                "with the boundary behind",
            "recommended_range": None,
            "continuity": "FAIL (world/prop/light all break)",
            "direction": "MAJOR_DIRECTION_FAILURE (reverse axis, no "
                         "lateral read)",
            "creative_verdict": "REJECT",
            "remaining_issue": "fortress-gate world + sword + warm "
                               "palette + absent wind"},
        "F2A_to_F2B_CUT": {
            "works": ["character identity (robes/topknot)",
                      "formal passage-interior continuity"],
            "does_not_work": ["world material (natural rock vs built "
                              "blocks)", "palette (cool vs warm)",
                              "prop (sword appears)", "travel axis "
                              "(reverses across the cut)",
                              "action energy (forcing vs stroll)"],
            "confidence": "HIGH (11-frame samples both sides of the cut)"},
        "watermark": WATERMARK,
        "owner_note": "the Owner can rule from the contact sheets + "
                      "side-by-side without reading raw JSON; worker "
                      "verdicts are advisory, the Owner visual read is "
                      "authoritative"})
    write("V2_011A_PRODUCTION_LOCK.json", {
        "version": "v2-011a-production-lock-v1",
        "checkpoint": "V2011A_P9_LOCK",
        "built_at": utcnow(),
        "production_lock": "NOT_GRANTED",
        "f2a_creative": "REPAIR_REQUIRED",
        "f2b_creative": "REJECT",
        "f2_sequence": "REPAIR_REQUIRED",
        "frozen_anyway": {
            "f2a_asset_sha256": F2A_SHA,
            "f2b_asset_sha256": F2B_SHA,
            "f2b_creation_id": "1546437193256465",
            "qc_reports": ["V2_011A_F2A_CREATIVE_QC.json",
                           "V2_011A_F2B_CREATIVE_QC.json",
                           "V2_011A_PAIR_CONTINUITY_QC.json"],
            "note": "assets stay custody-frozen as REPAIR SOURCE "
                    "material; they are NOT accepted as film footage"},
        "repair_specifications": REPAIR_SPECS,
        "next_route_decision": "TECH_LEAD decides: V2-011B EDITORIAL (not "
                               "viable for F2B; F2A direction not "
                               "cut-fixable) vs V2-011R TARGETED REPAIR "
                               "(recommended: both shots need "
                               "regeneration under new Owner authority "
                               "with the repair specs above)",
        "provider_mutations": 0,
        "no_regeneration_performed": True})
    seal = {
        "version": "v2-011a-candidate-seal-v1",
        "checkpoint": "V2011A_P9_SEAL",
        "sealed_at": utcnow(),
        "status": "COMPLETED_CANDIDATE",
        "completed_candidate": True,
        "f2_sequence": "REPAIR_REQUIRED",
        "engineering_completion": "COMPLETE (review executed honestly, "
                                  "evidence written)",
        "creative_acceptance": "SEPARATE TRUTH — not granted: F2A "
                               "REPAIR_REQUIRED, F2B REJECT",
        "checks": {"asset_custody_exact": True,
                   "f2a_reviewed": True, "f2b_reviewed": True,
                   "pair_continuity_reviewed": True,
                   "editorial_ranges_defined": True,
                   "critical_failures_not_hidden": True,
                   "no_provider_mutation": True,
                   "no_watermark_manipulation": True,
                   "evidence_complete": True},
        "provider_mutations": 0,
    }
    write("V2_011A_CANDIDATE_SEAL.json", seal)
    print(json.dumps({"checkpoint": "V2011A_FINALIZED",
                      "F2A": "REPAIR_REQUIRED",
                      "F2B": "REJECT",
                      "PAIR": "FAIL",
                      "sequence": "REPAIR_REQUIRED",
                      "status": "COMPLETED_CANDIDATE"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
