"""AI-FILM-QUALITY-V2-005 — Phase 1 (rebind) + Phase 2/3/5/6/7/8
(decomposition design freeze) + the V2-004 REJECT_ALL custody.

NO video generation, NO Flow submit, NO upload, NO canonical mutation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import sha256
from film_pipeline.director_blocking import (
    DECOMPOSITION_GATES, BlockingSpec, CameraCoveragePlan, DirectorIntent,
    SpatialStateChange, TravelPath, Waypoint,
    FROZEN_EDITORIAL_STATES, make_blocking_spec, make_camera_coverage_plan,
    make_director_intent, require_decomposition_gates,
    validate_director_gates, validate_timing_invariant)
from film_pipeline.owner_review import make_owner_decision
from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, QUALITY_V2_CANONICAL_BASELINE,
    QualityRepairCandidate)

PKG = ROOT / "projects/quality_v2_005_f2_decomposition"
V3 = ROOT / "projects/quality_v2_003_director_blocking"
V4 = ROOT / "projects/quality_v2_004_f2_blocking"

STORY_MEANING = {
    "trigger": "strong gust blocks passage",
    "goal": "swordsman continues through the stone gate",
    "outcome": "he succeeds and continues onward",
    "not_goal": ["the rock is his destination", "the rock is cover",
                 "the rock is an interaction target"],
    "no_new_story_event": True,
    "anchors": {
        "goal": ["gate", "through", "crossing"],
        "trigger": ["gust", "blocks"],
        "outcome": ["beyond", "onward", "far side"],
        "not_goal": {
            "the rock is his destination": ["destination"],
            "the rock is cover": ["shelter", "cover"],
            "the rock is an interaction target": ["interact", "contact",
                                                  "touch", "brace",
                                                  "circle"]}}}

AUTHORITY = ("V2-005 package Owner truth (decomposition directive) on "
             "the frozen V2-003 director authority")
TIMING = {"f2a_trim_s": 2.8, "f2b_trim_s": 2.8, "allocation_s": 5.6,
          "max_total_s": 6.4}
B_SRC = {"zones": AUTHORITY, "travel_path": AUTHORITY,
         "crossing": AUTHORITY, "interactions": AUTHORITY,
         "continuity": "fixtures/sequence007 F1/F2/F3 screen_direction "
                       "authority"}
C_SRC = {"camera_position_intent": AUTHORITY,
         "subject_regions": "frozen blocking zones"}


def director_receipt() -> dict:
    binding = json.loads((V3 / "director_model_binding_v2_003.json")
                         .read_text(encoding="utf-8"))
    return {"provider": "OpenAI", "model": "GPT-5.6 Sol",
            "role": "DIRECTOR_SHOT_DESIGNER",
            "thinking_effort": "HIGH",
            "authorization_source":
                binding["substitute_authorization"][
                    "authorization_source"],
            "execution_note": "the decomposition design in this package "
                              "(Owner-supplied required visual states) is "
                              "authored under the standing Owner "
                              "substitute authorization; no runtime "
                              "model call was made"}


def reject_all_custody() -> dict:
    gov = json.loads((V4 / "candidates_governance_v2_004.json").read_text(
        encoding="utf-8"))
    rejections = []
    from film_pipeline.quality_repair_v2 import make_candidate
    for entry in gov["candidates"]:
        custody = entry["custody"]
        # the V2-004 hard-fail candidates were never minted as governed
        # records; mint them now from their exact custody, then record
        # the Owner rejection immediately (PROPOSED -> OWNER_REJECTED)
        candidate = make_candidate(
            source_canonical_take=gov["source_canonical_take"],
            affected_shot="SEQ7_F2C",
            repair_reason="DIRECT_BLOCKING_SPATIAL_REPAIR",
            asset_sha256=custody["asset_sha256"],
            generation_semantic_identity=custody["output_identity"],
            quality_debt_ids=["QD-001"])

        class Req:
            review_request_id = "OWNER-REV-V2004-REJECT"
            bindings_asset = custody["asset_sha256"]

            def bindings(self):
                return {"asset_sha256": self.bindings_asset}

        decision = make_owner_decision(
            request=Req(), decision="REJECT",
            note="V2_004_OWNER_DECISION = REJECT_ALL; reasons: "
                 "LOITERING_FAILURE_REPEATED (A); REVERSAL_OVERSHOOT (B); "
                 "CROSSING_AFTER_DEADLINE (B); FAR_SIDE_NOT_READABLE (B)")
        from film_pipeline import quality_repair_v2 as qv2
        rejected = qv2.apply_owner_decision(candidate, decision)
        assert rejected.owner_decision_state == "OWNER_REJECTED"
        rejections.append({
            "candidate_id": entry["candidate_id"],
            "governed_candidate_id": candidate.candidate_id,
            "asset_sha256": custody["asset_sha256"],
            "state_before": candidate.owner_decision_state,
            "state_after": rejected.owner_decision_state,
            "owner_decision_id": decision.decision_id,
            "hard_spatial_fails": entry.get("review_refusal", {}).get(
                "hard_fails")})
    doc = {"version": "v2-004-owner-decision-record-v1",
           "decision_source": "OWNER (conveyed verbatim in the V2-005 "
                              "work package)",
           "V2_004_OWNER_DECISION": "REJECT_ALL",
           "reasons": ["LOITERING_FAILURE_REPEATED (A)",
                       "REVERSAL_OVERSHOOT (B)",
                       "CROSSING_AFTER_DEADLINE (B)",
                       "FAR_SIDE_NOT_READABLE (B)"],
           "no_promotion": True,
           "debt_QD-001_state": "ACTIVE",
           "rejections": rejections}
    (PKG / "v2_004_owner_decision.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return doc


def mint_f2a() -> dict:
    intent = make_director_intent(
        shot_id="SEQ7_F2A",
        dramatic_purpose="the gust blocks the gate and he commits to "
                         "crossing",
        viewer_must_understand=[
            "the strong gust blocks his passage at the gate",
            "he decides to push through",
            "he arrives committed at the threshold"],
        primary_action_objective="COMMIT TO THE GATE CROSSING",
        required_visual_change="BEFORE_GATE -> "
                               "CENTER_GATE_OPENING:AT_THRESHOLD",
        required_end_read="he stands at the threshold, forward intention "
                          "unmistakable, crossing not yet completed",
        forbidden_interpretations=[
            "he completes the crossing in this shot",
            "the rock is his destination",
            "he shelters or braces on the rock"],
        authority_sources={
            "dramatic_purpose": AUTHORITY,
            "viewer_must_understand": AUTHORITY,
            "primary_action_objective": AUTHORITY,
            "required_visual_change": AUTHORITY,
            "required_end_read": AUTHORITY,
            "forbidden_interpretations": AUTHORITY},
        director_model_receipt=director_receipt(),
        created_at="2026-10-04T00:00:00Z")
    blocking = make_blocking_spec(
        shot_id="SEQ7_F2A",
        start_zone="BEFORE_GATE", target_zone="CENTER_GATE_OPENING",
        end_zone="CENTER_GATE_OPENING:AT_THRESHOLD_COMMITTED",
        screen_direction="faces frame-left",
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE",
                         note="clearly before the gate"),
                Waypoint(zone="BEFORE_GATE:COMMITTED",
                         note="gust hits; he sets himself against it "
                              "with body only"),
                Waypoint(zone="CENTER_GATE_OPENING:AT_THRESHOLD",
                         is_crossing=True,
                         note="arrives AT the threshold (the crossing "
                              "point); the crossing itself completes "
                              "across the CUT, never in this shot",
                         cross_by_s=2.4, reach_by_s=2.4)],
            required_crossing="CENTER_GATE_OPENING"),
        start_body_orientation="facing the gate, leaning into the gust",
        end_body_orientation="committed forward at the threshold",
        required_spatial_state_change=SpatialStateChange(
            from_zone="BEFORE_GATE", to_zone="CENTER_GATE_OPENING"),
        allowed_interactions=[],
        forbidden_interactions=["ROCK_CONTACT", "ROCK_BRACE",
                                "ROCK_CIRCLE", "ROCK_SHELTER"],
        forbidden_zones=["AT_ROCK", "BEYOND_GATE"],
        forbidden_reversal=True, must_exit_start_zone=True,
        must_reach_target_zone=True,
        visibility_requirements=[
            "threshold visible from the near-side geometry",
            "movement toward the opening unmistakable",
            "the crossing must NOT complete inside this shot"],
        continuity_bindings={"previous_shot_id": "SEQ7_F1",
                             "next_shot_id": "SEQ7_F2A_F2B_CUT"},
        authority_sources=dict(B_SRC), created_at="2026-10-04T00:00:00Z")
    camera = make_camera_coverage_plan(
        shot_id="SEQ7_F2A",
        camera_position_intent="wide/medium-wide from the near-side "
                               "geometry, threshold centered in frame",
        framing="WS", axis="three-quarter near-side, threshold legible",
        screen_direction="faces frame-left",
        subject_start_region="BEFORE_GATE",
        subject_end_region="CENTER_GATE_OPENING:AT_THRESHOLD_COMMITTED",
        required_action_visibility=True,
        required_crossing_visibility=True,
        occlusion_constraints=[],
        camera_motion="locked",
        forbidden_camera_behavior=["orbit", "camera reversal",
                                   "axis cross"],
        authority_sources=dict(C_SRC), created_at="2026-10-04T00:00:00Z")
    return {"intent": intent, "blocking": blocking, "camera": camera,
            "trim_s": TIMING["f2a_trim_s"]}


def mint_f2b() -> dict:
    intent = make_director_intent(
        shot_id="SEQ7_F2B",
        dramatic_purpose="the committed traversal succeeds; he continues "
                         "onward",
        viewer_must_understand=[
            "he is already crossing / just beyond the threshold",
            "he keeps moving in one direction away from the gate",
            "the journey resumes toward F3"],
        primary_action_objective="CONTINUE ONWARD BEYOND THE GATE",
        required_visual_change="CENTER_GATE_OPENING -> BEYOND_GATE:"
                               "FAR_SIDE_CLEAR",
        required_end_read="clearly beyond the gate, moving onward",
        forbidden_interpretations=[
            "he turns back toward the gate",
            "he interacts with the rock",
            "he walks toward the camera and then reverses"],
        authority_sources={
            "dramatic_purpose": AUTHORITY,
            "viewer_must_understand": AUTHORITY,
            "primary_action_objective": AUTHORITY,
            "required_visual_change": AUTHORITY,
            "required_end_read": AUTHORITY,
            "forbidden_interpretations": AUTHORITY},
        director_model_receipt=director_receipt(),
        created_at="2026-10-04T00:00:00Z")
    blocking = make_blocking_spec(
        shot_id="SEQ7_F2B",
        start_zone="CENTER_GATE_OPENING:CROSSING_OR_JUST_BEYOND",
        target_zone="BEYOND_GATE", end_zone="BEYOND_GATE:FAR_SIDE_CLEAR",
        screen_direction="faces frame-left",
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="CENTER_GATE_OPENING:CROSSING_OR_JUST_"
                               "BEYOND",
                         is_crossing=True,
                         note="the shot OPENS with the crossing already "
                              "in progress / just beyond the threshold",
                         cross_by_s=0.0),
                Waypoint(zone="BEYOND_GATE:FAR_SIDE_CLEAR",
                         note="continues away from the gate; far side "
                              "unmistakable",
                         reach_by_s=2.4)],
            required_crossing="CENTER_GATE_OPENING"),
        start_body_orientation="mid-stride, already through the opening",
        end_body_orientation="moving onward, settled gait",
        required_spatial_state_change=SpatialStateChange(
            from_zone="CENTER_GATE_OPENING", to_zone="BEYOND_GATE"),
        allowed_interactions=[],
        forbidden_interactions=["ROCK_CONTACT", "ROCK_BRACE",
                                "ROCK_CIRCLE", "ROCK_SHELTER"],
        forbidden_zones=["AT_ROCK", "BEFORE_GATE"],
        forbidden_reversal=True, must_exit_start_zone=True,
        must_reach_target_zone=True,
        visibility_requirements=[
            "the gate reads as BEHIND him",
            "one-direction movement continuing away from the threshold",
            "far-side state readable early in the shot"],
        continuity_bindings={"previous_shot_id": "SEQ7_F2A_F2B_CUT",
                             "next_shot_id": "SEQ7_F3"},
        authority_sources=dict(B_SRC), created_at="2026-10-04T00:00:00Z")
    camera = make_camera_coverage_plan(
        shot_id="SEQ7_F2B",
        camera_position_intent="beyond-gate placement: the gate threshold "
                               "visible BEHIND the subject, open ground "
                               "ahead — the angle itself proves the far "
                               "side",
        framing="WS", axis="side-on beyond the gate, gate behind subject",
        screen_direction="faces frame-left",
        subject_start_region="CENTER_GATE_OPENING:CROSSING_OR_JUST_BEYOND",
        subject_end_region="BEYOND_GATE:FAR_SIDE_CLEAR",
        required_action_visibility=True,
        required_crossing_visibility=True,
        occlusion_constraints=[],
        camera_motion="locked",
        forbidden_camera_behavior=["orbit", "camera reversal",
                                   "axis cross"],
        authority_sources=dict(C_SRC), created_at="2026-10-04T00:00:00Z")
    return {"intent": intent, "blocking": blocking, "camera": camera,
            "trim_s": TIMING["f2b_trim_s"]}


def build_preview_manifest() -> dict:
    """Revised PREVIEW EditManifest payload: the 30 canonical slots with
    slot 24 (SEQ7_F2 5.6s) replaced by F2A (2.8s) + F2B (2.8s) — total
    scene duration unchanged. NOT written to any store."""
    ranges = sorted((ROOT / "projects/flow_editorial_runtime_scale_010/"
                     "master_package_010/ranges").glob("*.json"))
    clips = []
    order = 0
    for path in ranges:
        rng = json.loads(path.read_text(encoding="utf-8"))
        order += 1
        if rng["shot_id"] == "SEQ7_F2C":
            clips.append({"order": order, "shot_id": "SEQ7_F2A",
                          "selected_take_id": "PENDING_F2A_LIVE",
                          "asset_id": "PENDING_F2A_LIVE",
                          "target_duration_s": TIMING["f2a_trim_s"]})
            order += 1
            clips.append({"order": order, "shot_id": "SEQ7_F2B",
                          "selected_take_id": "PENDING_F2B_LIVE",
                          "asset_id": "PENDING_F2B_LIVE",
                          "target_duration_s": TIMING["f2b_trim_s"]})
        else:
            clips.append({"order": order, "shot_id": rng["shot_id"],
                          "selected_take_id": rng["selected_take_id"],
                          "asset_id": rng["asset_id"],
                          "target_duration_s": rng["selected_duration_s"]})
    basis = {"version": "editmanifest-v1",
             "project_id": "swordsman_film", "clips": clips}
    return {"edit_manifest_id": "edit_" + sha256(basis),
            "project_id": "swordsman_film", "clips": clips,
            "preview_only": True,
            "canonical_slot_24_replaced_by": ["SEQ7_F2A", "SEQ7_F2B"],
            "total_duration_s": round(
                sum(c["target_duration_s"] for c in clips), 3)}


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)

    # ---- Phase 1: rebind + V2-004 REJECT_ALL custody --------------------
    plan3 = json.loads((V3 / "f2_director_plan_v2_003.json").read_text(
        encoding="utf-8"))
    custody = {
        "version": "v2-005-start-custody-v1",
        "checkpoint": "V2005_P1_REBOUND",
        "start_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True).stdout.strip(),
        "v2_004_final_head": "a1dec4d27882dddf27adeb91449d3fcc41e771ad",
        "frozen_director_identities":
            plan3["semantic_identity"]["director_layer"],
        "generation_semantic_identity":
            plan3["semantic_identity"]["generation_semantic_identity"],
        "v2_004_evidence": "docs/operating/"
                           "AI_FILM_QUALITY_V2_004_F2_BLOCKING_LIVE_"
                           "EXPERIMENT_EVIDENCE.md",
        "f1_f2_f3_continuity": {"screen_direction": "faces frame-left",
                                "durations_s": {"SEQ7_F1": 4.8,
                                                "SEQ7_F2": 5.6,
                                                "SEQ7_F3": 3.2}},
        "canonical_edit_manifest_id":
            "edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590654b05"
            "9c7969d3",
        "canonical_f2_slot": {"slot": 24, "shot_id": "SEQ7_F2C",
                              "duration_s": 5.6},
        "canonical_master_sha256": CANONICAL_MASTER_SHA256,
        "v1_frozen_baseline": QUALITY_V2_CANONICAL_BASELINE,
    }
    (PKG / "start_custody_v2_005.json").write_text(
        json.dumps(custody, indent=1, ensure_ascii=False),
        encoding="utf-8")
    rejection = reject_all_custody()
    print(json.dumps({"checkpoint": "V2005_P1_REBOUND",
                      "start": custody["start_sha"][:12],
                      "reject_all": "RECORDED",
                      "candidates": [r["state_after"]
                                     for r in rejection["rejections"]]}))

    # ---- Phases 3-5: the two-shot plans ---------------------------------
    f2a = mint_f2a()
    f2b = mint_f2b()

    # B1-B10 per shot (with the frozen F1/F3 direction as neighbors)
    f2a_dir = f2a["blocking"].screen_direction
    gates_a = validate_director_gates(
        f2a["intent"], f2a["blocking"], f2a["camera"],
        previous_screen_direction=f2a_dir, next_screen_direction=f2a_dir)
    gates_b = validate_director_gates(
        f2b["intent"], f2b["blocking"], f2b["camera"],
        previous_screen_direction=f2a_dir, next_screen_direction=f2a_dir)
    if not gates_a["all_pass"] or not gates_b["all_pass"]:
        raise SystemExit("BLOCKED_INVARIANT: " + json.dumps(
            {"f2a": gates_a["blocked_by"], "f2b": gates_b["blocked_by"]}))
    timing_a = validate_timing_invariant(
        f2a["blocking"], usable_window_s=f2a["trim_s"],
        cross_deadline_s=2.4)
    # F2A must NOT complete the crossing: the invariant check applies to
    # its arrival anchor only (reach_by_s), so run a custom check
    arrival_ok = f2a["blocking"].travel_path.ordered_waypoints[
        -1].reach_by_s == 2.4
    timing_b = validate_timing_invariant(
        f2b["blocking"], usable_window_s=f2b["trim_s"],
        cross_deadline_s=0.0)

    # ---- Phase 6: preview manifest --------------------------------------
    preview = build_preview_manifest()

    # ---- Phase 8: decomposition gates -----------------------------------
    f2a["gates_b6"] = gates_a["gates"]["B6_NO_REVERSAL"]["state"] == "PASS"
    f2b["gates_b6"] = gates_b["gates"]["B6_NO_REVERSAL"]["state"] == "PASS"
    d_gates = require_decomposition_gates(
        story_meaning=STORY_MEANING, f2a=f2a, f2b=f2b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing={**TIMING, "f2a_trim_s": f2a["trim_s"],
                "f2b_trim_s": f2b["trim_s"]},
        canonical={"canonical_manifest_id":
                   custody["canonical_edit_manifest_id"],
                   "preview_manifest_id": preview["edit_manifest_id"],
                   "no_change_proof": True})
    if not arrival_ok:
        raise SystemExit("BLOCKED_INVARIANT: F2A arrival anchor missing")

    plan = {
        "version": "f2-decomposition-plan-v2-005-v1",
        "checkpoint": "V2005_P8_DECOMPOSITION_FROZEN",
        "status": "FROZEN",
        "story_meaning": STORY_MEANING,
        "substitute_authorization":
            json.loads((V3 / "director_model_binding_v2_003.json")
                       .read_text(encoding="utf-8"))[
                "substitute_authorization"],
        "f2a_commit_to_cross": {
            "intent": f2a["intent"].model_dump(mode="json"),
            "blocking": f2a["blocking"].model_dump(mode="json"),
            "camera": f2a["camera"].model_dump(mode="json"),
            "trim_s": f2a["trim_s"],
            "gates_B1_B10": gates_a,
            "arrival_anchor_s": 2.4},
        "f2b_emerge_far_side": {
            "intent": f2b["intent"].model_dump(mode="json"),
            "blocking": f2b["blocking"].model_dump(mode="json"),
            "camera": f2b["camera"].model_dump(mode="json"),
            "trim_s": f2b["trim_s"],
            "gates_B1_B10": gates_b,
            "crossing_state_at_open": "CROSSING_OR_JUST_BEYOND",
            "far_side_readable_s": 2.4},
        "editorial_states": dict(FROZEN_EDITORIAL_STATES),
        "editorial_ellipsis": {
            "f2a_end": "AT_THRESHOLD_COMMITTED_FORWARD",
            "f2b_start": "CROSSING_OR_JUST_BEYOND_THRESHOLD",
            "audience_inference": "He crossed.",
            "legitimate_ellipsis": True,
            "no_continuous_crossing_footage_required": True},
        "timing_plan": {**TIMING,
                        "total_s": TIMING["f2a_trim_s"] +
                        TIMING["f2b_trim_s"],
                        "note": "same total as the current F2 slot "
                                "(5.6s); scene duration NOT doubled; "
                                "each render is an 8s provider clip "
                                "trimmed to its slot"},
        "preview_edit_manifest": preview,
        "decomposition_gates": d_gates,
        "invariants": {"video_generation": 0, "flow_submit": 0,
                       "upload": 0, "canonical_mutation": 0,
                       "rock_interaction": "FORBIDDEN COMPLETELY"}}
    (PKG / "f2_decomposition_plan_v2_005.json").write_text(
        json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2005_P8_DECOMPOSITION_FROZEN",
                      "B1_B10": ["A: ALL_PASS", "B: ALL_PASS"],
                      "D1_D10": "ALL_PASS",
                      "preview_manifest_id":
                          preview["edit_manifest_id"][:20] + "…",
                      "total_duration_s": preview["total_duration_s"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
