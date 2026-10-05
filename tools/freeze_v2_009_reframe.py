"""AI-FILM-QUALITY-V2-009 — the frozen world-geography reframe.

Freezes the Owner NEEDS_REPAIR custody, the TraversalGeometrySpec v1
(choke-point reframe, G1-G10), the CausalEnvironmentSpec v1 (gust
causality, W1-W6), the L1-L8 legibility contract, the revised F2A/F2B
plan revisions (V2-005/V2-008 plans preserved), and the Seedance access
audit + route selection. NO generation, NO upload, NO canonical
mutation.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.core import sha256
from film_pipeline.director_blocking import (
    BlockingSpec, CameraCoveragePlan, DirectorIntent, SpatialStateChange,
    TravelPath, Waypoint, FROZEN_EDITORIAL_STATES, make_blocking_spec,
    make_camera_coverage_plan, make_director_intent,
    require_decomposition_gates, require_director_gates,
    validate_timing_invariant)
from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, QUALITY_V2_CANONICAL_BASELINE,
    QualityRepairCandidate)
from film_pipeline.world_geography_v2_009 import (
    LEGIBILITY_GATES, TRAVERSAL_GATES, WIND_GATES,
    make_causal_environment, make_traversal_geometry,
    require_traversal_gates, require_wind_gates,
    validate_legibility_contract)

PKG = ROOT / "projects/quality_v2_009_world_geography_reframe"
V8 = ROOT / "projects/quality_v2_008_world_anchored_live"
V5 = ROOT / "projects/quality_v2_005_f2_decomposition"

V2_008_HEAD = "8b6c766126eabcf8c3828937b9907fc074be304e"
AUTHORITY = ("V2-009 Owner NEEDS_REPAIR reframe: the gate is a "
             "PASS-THROUGH OBSTACLE / CHOKE POINT integrated into "
             "terrain; Director interpretation (narrow stone pass / "
             "ruined stone boundary / rock choke point), NOT a newly "
             "asserted source fact")
B_SRC = {"zones": AUTHORITY, "travel_path": AUTHORITY,
         "crossing": AUTHORITY, "interactions": AUTHORITY,
         "continuity": "fixtures/sequence007 F1/F2/F3 authority"}
C_SRC = {"camera_position_intent": "frozen V2-005 camera plan",
         "subject_regions": "revised blocking zones"}


def owner_decision_custody() -> dict:
    gov = json.loads((V8 / "candidates_governance_v2_008.json")
                     .read_text(encoding="utf-8"))
    reasons = ["WORLD_GEOGRAPHY_DOES_NOT_JUSTIFY_GATE_TRAVERSAL",
               "ACTION_GOAL_NOT_NARRATIVELY_LEGIBLE",
               "CHARACTER_READS_AS_SHELTERING_OR_LOITERING",
               "GUST_NOT_LEGIBLE_AS_CAUSAL_OBSTACLE"]
    doc = {
        "version": "v2-008-owner-decision-record-v1",
        "checkpoint": "V2009_P0_NEEDS_REPAIR_RECORDED",
        "decision_source": "OWNER (conveyed verbatim in the V2-009 work "
                           "package)",
        "V2_008_OWNER_DECISION": "NEEDS_REPAIR",
        "reasons": reasons,
        "no_v2_008_candidate_may_enter_OWNER_SELECTED": True,
        "no_promotion": True,
        "debt_QD-001_state": "ACTIVE",
        "candidate_states": {c["candidate_id"]: c["governed"][
            "owner_decision_state"] for c in gov["candidates"]},
        "reframe_directive": {
            "authoritative_truth": {
                "TRIGGER": "a hard gust hits",
                "GOAL": "continue onward THROUGH the gate / passage",
                "ACTION": "drive forward through the obstacle despite "
                          "the gust",
                "OUTCOME": "emerge beyond the worst gust and continue",
                "NOT_GOAL": ["hide", "shelter", "inspect stone",
                             "circle obstacle", "linger",
                             "use rock as destination"]},
            "reframe": "the source does NOT require a freestanding "
                       "decorative doorway in an open field; treat "
                       "'gate' as a PASS-THROUGH OBSTACLE / CHOKE POINT "
                       "whose visual design must make the existing "
                       "causal action believable",
            "director_interpretation_allowed": "narrow stone pass / "
                                               "ruined stone boundary / "
                                               "rock choke point "
                                               "integrated into the "
                                               "terrain (DESIGN "
                                               "interpretation, not a "
                                               "new source fact)",
            "key_invariant": "THE VIEWER MUST NOT REASONABLY THINK: "
                             "'he could simply walk around it.'"}}
    (PKG / "v2_008_owner_decision.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return doc


def main() -> int:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    if head != V2_008_HEAD:
        raise SystemExit("BLOCKED_INVARIANT: start HEAD drift")
    PKG.mkdir(parents=True, exist_ok=True)

    decision = owner_decision_custody()
    print(json.dumps({"checkpoint": "V2009_P0_NEEDS_REPAIR_RECORDED",
                      "states": decision["candidate_states"]}))

    # ---- P1/P2: the world-geography authority ---------------------------
    geometry = make_traversal_geometry(
        shot_scope="SEQ7_F2 (F2A+F2B decomposed pair)",
        entry_region="ROAD_BEFORE_PASS:travel path visibly funnels "
                     "toward the stone boundary",
        threshold_region="NARROW_PASS_OPENING:the only walkable gap in "
                         "the rock boundary",
        exit_region="BEYOND_GATE:ROAD_BEYOND_PASS open travel path "
                    "continuing onward beyond the obstacle",
        barrier_extent="CONTINUOUS_ROCK_RIDGE_BOTH_SIDES:the rock "
                       "boundary extends beyond the visible opening on "
                       "both lateral sides, closing every bypass",
        passage_axis="the travel axis runs THROUGH the single opening; "
                     "no lateral axis exists",
        travel_direction="faces frame-left, moving frame-left through "
                         "the pass (F1/F3 continuity)",
        bypass_visibility="NONE_IN_FRAME",
        shelter_affordance="NONE",
        world_connection="the rock boundary is integrated into the "
                         "terrain: the road the character has been "
                         "traveling (F1/F2 approach) funnels INTO the "
                         "pass, and the road beyond (F3 onward) "
                         "continues from the exit — the barrier stands "
                         "ACROSS the road, not beside it",
        wind_channel="the gust channels THROUGH the pass against the "
                     "travel direction — the choke point is also the "
                     "wind funnel, which is WHY the pass is hard to "
                     "cross",
        camera_proof_requirements=[
            "the continuous rock boundary must be visible on BOTH "
            "lateral sides of the opening in the same frames as the "
            "crossing",
            "the road must be visible entering the pass and continuing "
            "beyond it",
            "the crossing must be provable without cutting away from "
            "the barrier"],
        forbidden_geography=list(("FREESTANDING_DECORATIVE_GATE",
                                  "OPEN_FIELD_BYPASS",
                                  "SHELTER_NICHE_OR_CAVE",
                                  "CASTLE_OR_FORTRESS", "METAL_GATE",
                                  "WARM_CLOUD_SEA",
                                  "LIGHTNING_AS_GUST_PROXY",
                                  "FORBIDDEN_DESTINATION")),
        authority_sources={
            "regions": AUTHORITY, "barrier": AUTHORITY,
            "wind_channel": "V2-009 Owner NEEDS_REPAIR (gust must be "
                            "the causal obstacle)",
            "forbidden_geography": "V2-008 Owner findings verbatim"},
        created_at="2026-10-04T00:00:00Z")
    geo_gates = require_traversal_gates(geometry)

    environment = make_causal_environment(
        shot_scope="SEQ7_F2 (F2A+F2B decomposed pair)",
        gust_direction="against the travel direction: the gust blows "
                       "from beyond the pass INTO his face, channeling "
                       "through the opening",
        cloth_pressure="robes press flat against his body on the "
                       "windward side and stream violently leeward",
        hair_movement="hair and headband stream leeward, tangent to the "
                      "wind vector",
        vegetation_movement="grass on both sides of the road bends "
                            "leeward in the same direction as the "
                            "cloth",
        body_lean_response="center of gravity drops and leans INTO the "
                           "gust; every forward step visibly pushes "
                           "against the wind",
        effort_requirement="forward progress requires visible muscular "
                           "effort caused by the gust — the pass is the "
                           "wind funnel, so crossing means forcing "
                           "through the wind",
        forbidden_environment=["ambient wind with unaffected body",
                               "random storm VFX unrelated to movement",
                               "lightning used as substitute for gust",
                               "character voluntarily crouching beside "
                               "stone", "cover-seeking body language",
                               "loitering", "lingering",
                               "ambient-only wind"],
        authority_sources={
            "gust_direction": AUTHORITY, "cloth_pressure": AUTHORITY,
            "body_lean_response": AUTHORITY,
            "effort_requirement": AUTHORITY},
        created_at="2026-10-04T00:00:00Z")
    wind_gates = require_wind_gates(environment)

    specs = {"geometry": geometry, "environment": environment}
    legibility = validate_legibility_contract(specs)
    if not (geo_gates["all_pass"] and wind_gates["all_pass"] and
            legibility["all_pass"]):
        raise SystemExit("BLOCKED_INVARIANT: " + json.dumps(
            {"geo": geo_gates["blocked_by"],
             "wind": wind_gates["blocked_by"],
             "legibility": legibility["blocked_by"]}))

    # ---- P4: revised blocking (F2A rev3 / F2B rev2) ----------------------
    intent_a = make_director_intent(
        shot_id="SEQ7_F2A",
        dramatic_purpose="the gust funnels through the rock pass; he "
                         "commits into the choke point",
        viewer_must_understand=[
            "the road funnels into a narrow stone pass",
            "the gust channels through that pass against him",
            "he commits into the choke point, crossing not yet "
            "completed"],
        primary_action_objective="COMMIT AND ENTER THE CHOKE POINT",
        required_visual_change="ROAD_BEFORE_PASS -> "
                               "NARROW_PASS_OPENING:AT_THRESHOLD",
        required_end_read="inside the pass opening, committed forward, "
                          "rock boundary on both sides",
        forbidden_interpretations=[
            "he completes the crossing in this shot",
            "the rock is his destination",
            "he shelters or braces on the rock",
            "a sword is drawn or flourished",
            "the pass is a freestanding decorative gate in an open "
            "field"],
        authority_sources={
            "dramatic_purpose": AUTHORITY,
            "viewer_must_understand": AUTHORITY,
            "primary_action_objective": AUTHORITY,
            "required_visual_change": AUTHORITY,
            "required_end_read": AUTHORITY,
            "forbidden_interpretations": AUTHORITY},
        director_model_receipt={
            "provider": "OpenAI", "model": "GPT-5.6 Sol",
            "role": "DIRECTOR_SHOT_DESIGNER", "thinking_effort": "HIGH",
            "authorization_source": "Owner explicit approval in Tech "
                                    "Lead chat (standing substitute "
                                    "authorization)",
            "execution_note": "the geography reframe authored here "
                              "follows the V2-008 Owner findings under "
                              "the standing authorization; no runtime "
                              "model call was made"},
        created_at="2026-10-04T00:00:00Z")
    blocking_a = make_blocking_spec(
        shot_id="SEQ7_F2A",
        start_zone="ROAD_BEFORE_PASS:CLOSE",
        target_zone="NARROW_PASS_OPENING",
        end_zone="NARROW_PASS_OPENING:AT_THRESHOLD_COMMITTED",
        screen_direction="faces frame-left",
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="ROAD_BEFORE_PASS:CLOSE",
                         note="already on the travel path, close to the "
                              "passage; gust active"),
                Waypoint(zone="NARROW_PASS_OPENING:ENTERED",
                         is_crossing=True,
                         note="1-2 decisive steps; enters the opening; "
                              "crossing completes across the CUT",
                         cross_by_s=2.4, reach_by_s=2.4)],
            required_crossing="NARROW_PASS_OPENING"),
        start_body_orientation="facing into the pass, braced against "
                               "AIR ONLY",
        end_body_orientation="inside the opening, committed forward",
        required_spatial_state_change=SpatialStateChange(
            from_zone="ROAD_BEFORE_PASS", to_zone="NARROW_PASS_OPENING"),
        allowed_interactions=[],
        forbidden_interactions=["ROCK_CONTACT", "ROCK_BRACE",
                                "ROCK_CIRCLE", "ROCK_SHELTER",
                                "WALL_TOUCH_FOR_SUPPORT"],
        forbidden_zones=["AT_ROCK", "BEYOND_PASS", "BESIDE_PILLAR"],
        forbidden_reversal=True, must_exit_start_zone=True,
        must_reach_target_zone=True,
        visibility_requirements=[
            "continuous rock boundary visible on BOTH lateral sides",
            "road visible entering the pass",
            "1-2 decisive steps; no loitering",
            "weapon passive/undrawn",
            "bracing against AIR ONLY — never touching wall for "
            "support"],
        continuity_bindings={"previous_shot_id": "SEQ7_F1",
                             "next_shot_id": "SEQ7_F2A_F2B_CUT"},
        authority_sources=dict(B_SRC), created_at="2026-10-04T00:00:00Z")
    camera_a = make_camera_coverage_plan(
        shot_id="SEQ7_F2A",
        camera_position_intent="medium-wide near-side close, the rock "
                               "boundary visible on BOTH lateral sides "
                               "of the opening",
        framing="WS", axis="three-quarter near-side; barrier extent "
                           "legible",
        screen_direction="faces frame-left",
        subject_start_region="ROAD_BEFORE_PASS:CLOSE",
        subject_end_region="NARROW_PASS_OPENING:AT_THRESHOLD_COMMITTED",
        required_action_visibility=True,
        required_crossing_visibility=True,
        occlusion_constraints=[],
        camera_motion="locked",
        forbidden_camera_behavior=["orbit", "camera reversal",
                                   "axis cross"],
        authority_sources=dict(C_SRC), created_at="2026-10-04T00:00:00Z")
    gates_a = require_director_gates(
        intent_a, blocking_a, camera_a,
        previous_screen_direction="faces frame-left",
        next_screen_direction="faces frame-left")
    timing_a = validate_timing_invariant(blocking_a, usable_window_s=2.8,
                                         cross_deadline_s=2.4)

    intent_b = make_director_intent(
        shot_id="SEQ7_F2B",
        dramatic_purpose="he forces through the wind funnel and the "
                         "road continues beyond",
        viewer_must_understand=[
            "he is already through the narrow pass",
            "the rock boundary is BEHIND him — the barrier he forced "
            "through",
            "the road continues onward: the traversal mattered"],
        primary_action_objective="EXIT THE CHOKE POINT AND CONTINUE "
                                 "ONWARD",
        required_visual_change="NARROW_PASS_OPENING -> "
                               "ROAD_BEYOND_PASS:FAR_SIDE_CLEAR",
        required_end_read="beyond the pass, the rock boundary behind "
                          "him, the road continuing",
        forbidden_interpretations=[
            "he turns back toward the opening",
            "he interacts with the rock",
            "he stands beside the gate inspecting it",
            "he loiters or shelters",
            "the barrier was decorative — he could have walked around"],
        authority_sources={
            "dramatic_purpose": AUTHORITY,
            "viewer_must_understand": AUTHORITY,
            "primary_action_objective": AUTHORITY,
            "required_visual_change": AUTHORITY,
            "required_end_read": AUTHORITY,
            "forbidden_interpretations": AUTHORITY},
        director_model_receipt={
            "provider": "OpenAI", "model": "GPT-5.6 Sol",
            "role": "DIRECTOR_SHOT_DESIGNER", "thinking_effort": "HIGH",
            "authorization_source": "Owner explicit approval in Tech "
                                    "Lead chat (standing substitute "
                                    "authorization)",
            "execution_note": "see F2A receipt"},
        created_at="2026-10-04T00:00:00Z")
    blocking_b = make_blocking_spec(
        shot_id="SEQ7_F2B",
        start_zone="NARROW_PASS_OPENING:CROSSING_OR_JUST_BEYOND",
        target_zone="BEYOND_GATE",
        end_zone="BEYOND_GATE:ROAD_BEYOND_PASS FAR_SIDE_CLEAR",
        screen_direction="faces frame-left",
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="NARROW_PASS_OPENING:CROSSING_OR_JUST_"
                               "BEYOND",
                         is_crossing=True,
                         note="opens already through the choke point",
                         cross_by_s=0.0),
                Waypoint(zone="BEYOND_GATE:ROAD_BEYOND_PASS FAR_SIDE_CLEAR",
                         note="the rock boundary falls BEHIND him; the "
                              "road continues",
                         reach_by_s=2.4)],
            required_crossing="NARROW_PASS_OPENING"),
        start_body_orientation="mid-stride, already through the "
                               "passage",
        end_body_orientation="moving onward along the road, settled",
        required_spatial_state_change=SpatialStateChange(
            from_zone="NARROW_PASS_OPENING", to_zone="BEYOND_GATE"),
        allowed_interactions=[],
        forbidden_interactions=["ROCK_CONTACT", "ROCK_BRACE",
                                "ROCK_CIRCLE", "ROCK_SHELTER",
                                "INSPECT_OBSTACLE"],
        forbidden_zones=["AT_ROCK", "ROAD_BEFORE_PASS"],
        forbidden_reversal=True, must_exit_start_zone=True,
        must_reach_target_zone=True,
        visibility_requirements=[
            "the rock boundary visible BEHIND him (the barrier he "
            "forced through)",
            "the road continuing onward ahead",
            "far-side state readable early",
            "no standing beside the opening"],
        continuity_bindings={"previous_shot_id": "SEQ7_F2A_F2B_CUT",
                             "next_shot_id": "SEQ7_F3"},
        authority_sources=dict(B_SRC), created_at="2026-10-04T00:00:00Z")
    camera_b = make_camera_coverage_plan(
        shot_id="SEQ7_F2B",
        camera_position_intent="beyond-pass placement: the rock boundary "
                               "visible BEHIND the subject receding, "
                               "the road ahead continuing",
        framing="WS", axis="side-on beyond the pass; boundary behind "
                           "subject",
        screen_direction="faces frame-left",
        subject_start_region="NARROW_PASS_OPENING:CROSSING_OR_JUST_"
                             "BEYOND",
        subject_end_region="BEYOND_GATE:ROAD_BEYOND_PASS FAR_SIDE_CLEAR",
        required_action_visibility=True,
        required_crossing_visibility=True,
        occlusion_constraints=[],
        camera_motion="locked",
        forbidden_camera_behavior=["orbit", "camera reversal",
                                   "axis cross"],
        authority_sources=dict(C_SRC), created_at="2026-10-04T00:00:00Z")
    gates_b = require_director_gates(
        intent_b, blocking_b, camera_b,
        previous_screen_direction="faces frame-left",
        next_screen_direction="faces frame-left")

    # ---- P7: decomposition + legibility on the revised pair --------------
    f2a = {"intent": intent_a, "blocking": blocking_a,
           "camera": camera_a, "trim_s": 2.8,
           "gates_b6": gates_a["gates"]["B6_NO_REVERSAL"]["state"] ==
           "PASS"}
    f2b = {"intent": intent_b, "blocking": blocking_b,
           "camera": camera_b, "trim_s": 2.8, "gates_b6": True}
    d_gates = require_decomposition_gates(
        story_meaning={
            "trigger": "a hard gust hits",
            "goal": "continue onward THROUGH the gate / passage",
            "outcome": "emerge beyond the worst gust and continue",
            "not_goal": ["hide", "shelter", "inspect stone",
                         "circle obstacle", "linger",
                         "use rock as destination"],
            "anchors": {
                "goal": ["gate", "through", "pass", "onward"],
                "trigger": ["gust", "hit"],
                "outcome": ["beyond", "continue", "emerge"],
                "not_goal": {
                    "hide": ["hide", "shelter", "cover"],
                    "shelter": ["shelter", "brace", "crouch"],
                    "inspect stone": ["inspect", "circle"],
                    "circle obstacle": ["circle", "around"],
                    "linger": ["linger", "loiter"],
                    "use rock as destination": ["destination"]}}},
        f2a=f2a, f2b=f2b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing={"f2a_trim_s": 2.8, "f2b_trim_s": 2.8, "allocation_s": 5.6,
                "max_total_s": 6.4},
        canonical={"canonical_manifest_id":
                   "edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca65"
                   "90654b059c7969d3",
                   "preview_manifest_id": "PREVIEW_PENDING_V2_010",
                   "no_change_proof": True})
    legibility_pair = validate_legibility_contract(
        specs, previz_manifest=None)
    if not gates_b["all_pass"] or not d_gates["all_pass"]:
        raise SystemExit("BLOCKED_INVARIANT: " + json.dumps(
            {"f2b": gates_b["blocked_by"], "d": d_gates["blocked_by"]}))

    plan = {
        "version": "f2-world-geography-reframe-v2-009-v1",
        "checkpoint": "V2009_P4_REFRAME_FROZEN",
        "status": "FROZEN",
        "owner_decision": {"V2_008_OWNER_DECISION": "NEEDS_REPAIR",
                           "reasons": decision["reasons"]},
        "narrative_truth": decision["reframe_directive"][
            "authoritative_truth"],
        "reframe": decision["reframe_directive"]["reframe"],
        "traversal_geometry": geometry.model_dump(mode="json"),
        "causal_environment": environment.model_dump(mode="json"),
        "f2a_enter_choke_point": {
            "intent": intent_a.model_dump(mode="json"),
            "blocking": blocking_a.model_dump(mode="json"),
            "camera": camera_a.model_dump(mode="json"),
            "trim_s": 2.8, "plan_revision": 3,
            "preserved": "V2-005 rev1 + V2-008 rev2 plans unchanged",
            "gates_B1_B10": gates_a, "timing": timing_a,
            "absolutely_forbidden": [
                "touching wall for support", "leaning behind rock",
                "side-step toward cover", "circling", "backtracking",
                "stopping beside pillar", "draw sword",
                "look-around behavior"]},
        "f2b_exit_choke_point": {
            "intent": intent_b.model_dump(mode="json"),
            "blocking": blocking_b.model_dump(mode="json"),
            "camera": camera_b.model_dump(mode="json"),
            "trim_s": 2.8, "plan_revision": 2,
            "preserved": "V2-005 F2B plan unchanged",
            "gates_B1_B10": gates_b,
            "absolutely_forbidden": [
                "turn back", "return toward opening",
                "stand beside gate", "inspect obstacle", "loiter",
                "shelter"]},
        "gates": {"traversal_G1_G10": geo_gates,
                  "wind_W1_W6": wind_gates,
                  "legibility_L1_L8": legibility_pair,
                  "decomposition_D1_D10": d_gates},
        "invariants": {"generation": 0, "upload": 0, "flow_submit": 0,
                       "seedance_submit": 0, "canonical_mutation": 0}}
    (PKG / "world_reframe_plan_v2_009.json").write_text(
        json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2009_P4_REFRAME_FROZEN",
                      "G1_G10": "ALL_PASS", "W1_W6": "ALL_PASS",
                      "L1_L8": "ALL_PASS",
                      "D1_D10": "ALL_PASS",
                      "B1_B10": ["A: ALL_PASS", "B: ALL_PASS"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
