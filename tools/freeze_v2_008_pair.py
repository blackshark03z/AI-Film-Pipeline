"""AI-FILM-QUALITY-V2-008 — Phases 3-7: the revised F2A plan revision
(CLOSE_BEFORE_THRESHOLD, V2-005 plan preserved), F2B reference swap to
the newly qualified far-side world frame, fixtures, semantic
identities, compiler conformance, admission receipt. No generation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.core import (ActionIntent, References, ShotSpec,
                                sha256, validate_contract)
from film_pipeline.compiler import compile_prompt
from film_pipeline.director_blocking import (
    BlockingSpec, CameraCoveragePlan, DirectorIntent, SpatialStateChange,
    TravelPath, Waypoint, FROZEN_EDITORIAL_STATES,
    director_semantic_identity, make_blocking_spec,
    make_camera_coverage_plan, make_director_intent,
    require_decomposition_gates, require_director_gates,
    validate_timing_invariant)
from film_pipeline.performance import BodyProportionAuthority
from film_pipeline.performance_compiler import compile_causal_r2v_prompt
from film_pipeline.quality_repair_v2 import (
    ADMISSION_REQUIRED_FROM, QUALITY_V2_CANONICAL_BASELINE, admission_gate,
    load_frozen_debt_ids, make_experiment_admission_receipt)
from run_scene_scale_003 import flow_capabilities

PKG = ROOT / "projects/quality_v2_008_world_anchored_live"
V5 = ROOT / "projects/quality_v2_005_f2_decomposition"
FIXTURES = ROOT / "fixtures/requal008"

F2A_BINDING = {
    "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
    "asset_id": ("asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72"
                 "eda0fa31ec44edc3"),
    "attestation_id": ("refbind_f4277ac1a7a5651c8370212417c06593f08a003a"
                       "ee1676517622292f37cb4fdf"),
    "mechanism": "last_frame", "from_shot": "SEQ7_F1",
    "source_frame_sha256": ("fecf669e9b81436c80cd6502036d10b401f3964534e"
                            "8d3fe9dea0800355f8313"),
    "reference_type": "FULL_FRAME_ENVIRONMENTAL (near-side)",
    "usage": "near-side F2A only"}

STORY_MEANING = json.loads(
    (V5 / "f2_decomposition_plan_v2_005.json").read_text(
        encoding="utf-8"))["story_meaning"]
B_SRC = {"zones": "V2-008 Owner-authorized pacing delta on the frozen "
                  "V2-005 authority",
         "travel_path": "V2-008 Owner-authorized pacing delta",
         "crossing": "V2-005 frozen crossing authority",
         "interactions": "V2-005 frozen interactions authority",
         "continuity": "fixtures/sequence007 F1/F2/F3 authority"}
C_SRC = {"camera_position_intent": "frozen V2-005 F2A camera plan",
         "subject_regions": "revised blocking zones"}


def body_variant(avoid: bool) -> BodyProportionAuthority:
    payload = json.loads((ROOT / "fixtures/character_bible/"
                          "swordsman_white_robes_body_v1.json")
                         .read_text(encoding="utf-8"))
    base = BodyProportionAuthority(**{k: v for k, v in payload.items()
                                      if k not in ("extends",
                                                   "look_state_id")})
    return base.model_copy(
        update={"avoid_short_compact_silhouette": avoid})


def revise_f2a() -> dict:
    """NEW plan revision: CLOSE_BEFORE_THRESHOLD. The V2-005 F2A plan
    stays preserved (this returns a REVISION, plan_revision=2)."""
    intent = make_director_intent(
        shot_id="SEQ7_F2A",
        dramatic_purpose="the gust already rages; he commits at the "
                         "threshold",
        viewer_must_understand=[
            "the gust is already active at the gate",
            "he commits immediately, one or two deliberate steps",
            "he reaches the threshold, crossing not yet completed"],
        primary_action_objective="IMMEDIATE COMMITMENT AT THE THRESHOLD",
        required_visual_change="CLOSE_BEFORE_THRESHOLD -> "
                               "CENTER_GATE_OPENING:AT_THRESHOLD",
        required_end_read="at the threshold, committed forward, crossing "
                          "not completed",
        forbidden_interpretations=[
            "he completes the crossing in this shot",
            "the rock is his destination",
            "he shelters or braces on the rock",
            "a sword is drawn or flourished",
            "a long approach from afar"],
        authority_sources={
            "dramatic_purpose": "V2-008 Owner-authorized pacing delta",
            "viewer_must_understand": "V2-008 Owner-authorized pacing "
                                      "delta",
            "primary_action_objective": "V2-008 Owner-authorized pacing "
                                        "delta",
            "required_visual_change": "V2-008 Owner-authorized pacing "
                                      "delta",
            "required_end_read": "V2-008 Owner-authorized pacing delta",
            "forbidden_interpretations": "V2-008 Owner-authorized pacing "
                                         "delta"},
        director_model_receipt={
            "provider": "OpenAI", "model": "GPT-5.6 Sol",
            "role": "DIRECTOR_SHOT_DESIGNER", "thinking_effort": "HIGH",
            "authorization_source": "Owner explicit approval in Tech "
                                    "Lead chat after V2-007",
            "execution_note": "the pacing delta authored here follows "
                              "the V2-007 diagnosis under the standing "
                              "Owner substitute authorization; no "
                              "runtime model call was made"},
        created_at="2026-10-04T00:00:00Z")
    blocking = make_blocking_spec(
        shot_id="SEQ7_F2A",
        start_zone="BEFORE_GATE:CLOSE_BEFORE_THRESHOLD",
        target_zone="CENTER_GATE_OPENING",
        end_zone="CENTER_GATE_OPENING:AT_THRESHOLD_COMMITTED",
        screen_direction="faces frame-left",
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE:CLOSE_BEFORE_THRESHOLD",
                         note="opens already close; the gust is active"),
                Waypoint(zone="CENTER_GATE_OPENING:AT_THRESHOLD",
                         is_crossing=True,
                         note="one/two deliberate steps; arrives AT the "
                              "threshold; crossing completes across the "
                              "CUT",
                         cross_by_s=2.4, reach_by_s=2.4)],
            required_crossing="CENTER_GATE_OPENING"),
        start_body_orientation="facing the gate, body set against the "
                               "gust",
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
            "threshold visible from the close near-side geometry",
            "one/two-step commitment unmistakable",
            "weapon passive/undrawn",
            "the crossing completes only across the cut"],
        continuity_bindings={"previous_shot_id": "SEQ7_F1",
                             "next_shot_id": "SEQ7_F2A_F2B_CUT"},
        authority_sources=dict(B_SRC), created_at="2026-10-04T00:00:00Z")
    camera = make_camera_coverage_plan(
        shot_id="SEQ7_F2A",
        camera_position_intent="wide/medium-wide close near-side, "
                               "threshold centered in frame",
        framing="WS", axis="three-quarter near-side, threshold legible",
        screen_direction="faces frame-left",
        subject_start_region="BEFORE_GATE:CLOSE_BEFORE_THRESHOLD",
        subject_end_region="CENTER_GATE_OPENING:AT_THRESHOLD_COMMITTED",
        required_action_visibility=True,
        required_crossing_visibility=True,
        occlusion_constraints=[],
        camera_motion="locked",
        forbidden_camera_behavior=["orbit", "camera reversal",
                                   "axis cross"],
        authority_sources=dict(C_SRC), created_at="2026-10-04T00:00:00Z")
    return {"intent": intent, "blocking": blocking, "camera": camera,
            "trim_s": 2.8}


def main() -> int:
    custody = json.loads((PKG / "custody_v2_008.json").read_text(
        encoding="utf-8"))
    qualification = json.loads((PKG /
                                "reference_qualification_v2_008.json")
                               .read_text(encoding="utf-8"))
    binding_f2b = {
        "media_id": qualification["binding"]["media_id"],
        "asset_id": qualification["binding"]["asset_id"],
        "attestation_id": qualification["binding"]["attestation_id"],
        "mechanism": "far_side_world_frame",
        "source_frame_sha256": qualification["binding"]["frame_sha256"],
        "reference_type": "FULL_FRAME_WORLD_AND_IDENTITY (FAR_SIDE)",
        "usage": "far-side F2B only"}

    # ---- P3: revised F2A plan + gates -----------------------------------
    f2a = revise_f2a()
    gates_a = require_director_gates(
        f2a["intent"], f2a["blocking"], f2a["camera"],
        previous_screen_direction="faces frame-left",
        next_screen_direction="faces frame-left")
    timing_a = validate_timing_invariant(f2a["blocking"],
                                         usable_window_s=2.8,
                                         cross_deadline_s=2.4)
    if timing_a["state"] != "PASS":
        raise SystemExit("BLOCKED_INVARIANT: F2A timing " + json.dumps(
            timing_a))

    # ---- D1-D10 on the revised pair --------------------------------------
    plan5 = json.loads((V5 / "f2_decomposition_plan_v2_005.json")
                       .read_text(encoding="utf-8"))
    f2b = {"intent": _intent_from(plan5["f2b_emerge_far_side"]["intent"]),
           "blocking": BlockingSpec.model_validate(
               plan5["f2b_emerge_far_side"]["blocking"]),
           "camera": CameraCoveragePlan.model_validate(
               plan5["f2b_emerge_far_side"]["camera"]),
           "trim_s": 2.8,
           "gates_b6": True}
    f2a["gates_b6"] = gates_a["gates"]["B6_NO_REVERSAL"]["state"] == "PASS"
    d_gates = require_decomposition_gates(
        story_meaning=STORY_MEANING, f2a=f2a, f2b=f2b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing={"f2a_trim_s": 2.8, "f2b_trim_s": 2.8, "allocation_s": 5.6,
                "max_total_s": 6.4},
        canonical={"canonical_manifest_id": custody["bindings"][
            "canonical"]["edit_manifest_id"],
            "preview_manifest_id": "PREVIEW_UNCHANGED_FROM_V2_005",
            "no_change_proof": True})

    # ---- P4/P5: fixtures + identities ------------------------------------
    FIXTURES.mkdir(parents=True, exist_ok=True)
    caps = flow_capabilities()
    frozen = []
    specs = [
        {"candidate_id": "F2A-V2-008", "shot_id": "SEQ7_F2A_V2_008",
         "base_fixture": "fixtures/requal006/SEQ7_F2A_V2_006.json",
         "binding": F2A_BINDING,
         "dramatic_purpose": "the gust rages; he commits at the "
                             "threshold",
         "blocking_start": "close before the gate opening",
         "blocking_end": "at the gate opening",
         "critical_invariants": [
             "rock gate walls consistent with SEQ7_F1 last frame",
             "wardrobe unchanged",
             "wind direction constant against him",
             "he opens already close to the threshold",
             "weapon passive and undrawn",
             "the crossing completes only across the cut"],
         "performance_spec": {
             "schema_version": "performance-spec-v1",
             "primary_action": "commits immediately and steps to the "
                               "gate opening",
             "action_intent": "the body answers at once",
             "weight_transfer": "weight drops forward",
             "motion_energy": "moderate",
             "beats": [
                 {"label": "set", "approx_start_s": 0.0,
                  "description": "gust active, body commits at once"},
                 {"label": "steps", "approx_start_s": 1.0,
                  "description": "one or two deliberate steps"},
                 {"label": "threshold", "approx_start_s": 2.0,
                  "description": "arrives at the opening"}]},
         "required": ["close", "gust", "commit", "opening", "gate"],
         "forbidden_tokens": ["sword", "draw", "guard"]},
        {"candidate_id": "F2B-V2-008", "shot_id": "SEQ7_F2B_V2_008",
         "base_fixture": "fixtures/requal006/SEQ7_F2B_V2_006.json",
         "binding": binding_f2b,
         "dramatic_purpose": "beyond the gate, the gate behind him, "
                             "onward",
         "blocking_start": "just beyond the gate opening",
         "blocking_end": "beyond gate, far side clear",
         "critical_invariants": [
             "wardrobe unchanged",
             "wind direction constant",
             "the gate is behind him",
             "he keeps moving away from the gate",
             "no return toward the gate",
             "the storm-gate world is preserved"],
         "performance_spec": {
             "schema_version": "performance-spec-v1",
             "primary_action": "continues onward away from the gate",
             "action_intent": "the committed crossing carries him "
                              "onward",
             "weight_transfer": "weight rolls forward",
             "motion_energy": "moderate",
             "beats": [
                 {"label": "emerge", "approx_start_s": 0.0,
                  "description": "already crossing / just past the "
                                 "opening"},
                 {"label": "stride", "approx_start_s": 0.9,
                  "description": "continues onward, away from the gate"},
                 {"label": "settle", "approx_start_s": 1.9,
                  "description": "far side clear, steady gait"}]},
         "required": ["beyond", "onward", "far side", "gate", "behind"],
         "forbidden_tokens": ["fortress", "metal", "lightning"]}]
    for cand in specs:
        payload = json.loads((ROOT / cand["base_fixture"]).read_text(
            encoding="utf-8"))
        payload["shot_id"] = cand["shot_id"]
        payload["characters"][0]["behavior_state"] = None
        payload["dramatic_purpose"] = cand["dramatic_purpose"]
        payload["blocking"]["start"] = cand["blocking_start"]
        payload["blocking"]["end"] = cand["blocking_end"]
        payload["continuity"]["critical_invariants"] = \
            cand["critical_invariants"]
        payload["performance_spec"] = cand["performance_spec"]
        payload["action_intent"] = dict(cand["performance_spec"]) if \
            False else payload["action_intent"]
        validate_contract("shot_spec", payload)
        fixture_path = FIXTURES / f"{cand['shot_id']}.json"
        fixture_path.write_text(json.dumps(payload, indent=1),
                                encoding="utf-8")
        spec_obj = ShotSpec.model_validate(payload)
        binding = cand["binding"]
        shot = spec_obj.model_copy(update={
            "references": References(other_asset_ids=[binding[
                "asset_id"]])})
        plan = compile_prompt(shot, caps, reference_hashes={
            binding["asset_id"]: binding["source_frame_sha256"]})
        prompt = compile_causal_r2v_prompt(
            plan, "job_" + "0" * 64, model="veo_3_1_r2v_lite",
            performance_spec=spec_obj.performance_spec,
            body_authority=body_variant(True),
            action_intent=spec_obj.action_intent)
        body_text = prompt.text.rsplit(" [FILM-", 1)[0]
        if len(body_text) > 500 or len(prompt.text.split()) > 76:
            raise SystemExit(f"BLOCKED_INVARIANT: {cand['candidate_id']} "
                             f"over envelope")
        low = body_text.lower()
        missing = [t for t in cand["required"] if t not in low]
        if missing:
            raise SystemExit(f"BLOCKED_INVARIANT: {cand['candidate_id']} "
                             f"lacks {missing}")
        leaked = []
        for token in cand["forbidden_tokens"]:
            occurrences = [i for i in range(len(low))
                           if low.startswith(token, i)]
            standalone = [i for i in occurrences
                          if (i == 0 or not low[i - 1].isalnum()) and
                          (i + len(token) == len(low) or
                           not low[i + len(token)].isalnum())]
            if standalone:
                leaked.append(token)
        if leaked:
            raise SystemExit(f"BLOCKED_INVARIANT: {cand['candidate_id']} "
                             f"expresses forbidden {leaked}")
        frozen.append({
            "candidate_id": cand["candidate_id"],
            "shot_id": cand["shot_id"],
            "fixture": fixture_path.relative_to(ROOT).as_posix(),
            "fixture_sha256": sha256(spec_obj),
            "creative_body": body_text,
            "creative_body_chars": len(body_text),
            "creative_body_words": len(prompt.text.split()),
            "action_intent_digest": spec_obj.action_intent.digest(),
            "performance_spec_digest":
                spec_obj.performance_spec.digest(),
            "reference_binding": binding,
            "editorial_target_duration": 2.8})
    # semantic identities (director layers: revised F2A vs frozen F2B)
    ident_a = director_semantic_identity(
        frozen[0]["fixture_sha256"], f2a["intent"], f2a["blocking"],
        f2a["camera"])
    ident_b = director_semantic_identity(
        frozen[1]["fixture_sha256"], f2b["intent"], f2b["blocking"],
        f2b["camera"])
    old_a = director_semantic_identity(
        frozen[0]["fixture_sha256"],
        _intent_from(plan5["f2a_commit_to_cross"]["intent"]),
        BlockingSpec.model_validate(
            plan5["f2a_commit_to_cross"]["blocking"]),
        CameraCoveragePlan.model_validate(
            plan5["f2a_commit_to_cross"]["camera"]))
    frozen[0]["generation_semantic_identity"] = sha256({
        "director_layer": ident_a["director_layer"],
        "action_intent_digest": frozen[0]["action_intent_digest"],
        "performance_spec_digest": frozen[0]["performance_spec_digest"],
        "reference_binding": frozen[0]["reference_binding"],
        "creative_body": frozen[0]["creative_body"]})
    frozen[1]["generation_semantic_identity"] = sha256({
        "director_layer": ident_b["director_layer"],
        "action_intent_digest": frozen[1]["action_intent_digest"],
        "performance_spec_digest": frozen[1]["performance_spec_digest"],
        "reference_binding": frozen[1]["reference_binding"],
        "creative_body": frozen[1]["creative_body"]})
    old_b = plan5  # frozen V2-005 F2B identity (unchanged historical)
    if frozen[0]["generation_semantic_identity"] == \
            frozen[1]["generation_semantic_identity"]:
        raise SystemExit("BLOCKED_INVARIANT: identity collision")

    experiment = {
        "version": "quality-v2-008-experiment-freeze-v1",
        "checkpoint": "V2008_PAIR_FROZEN",
        "frozen_before_generate_1": True,
        "plan_revisions": {
            "F2A": {"revision": 2,
                    "delta": "CLOSE_BEFORE_THRESHOLD (Owner-authorized "
                             "pacing delta)",
                    "preserved_previous": "V2-005 F2A plan unchanged "
                                          "(plan_revision=1)",
                    "new_director_layer": ident_a["director_layer"],
                    "old_director_layer": old_a["director_layer"]},
            "F2B": {"revision": 1, "plan": "frozen V2-005 (unchanged)",
                    "reference_swapped_to": binding_f2b,
                    "old_reference_was": "identity-only 7b725f7b "
                                         "(V2-006) — identity preserved "
                                         "but world drifted",
                    "director_layer": ident_b["director_layer"]}},
        "reference_qualification": qualification,
        "route": {"provider_id": "flow_veo",
                  "model_label": "veo_3_1_r2v_lite",
                  "project_id": "93a579b4-834e-435b-8304-5f6682937935",
                  "account_id": "clean-pro-qualified"},
        "budget": {"max_new_generates": 2,
                   "allocation": {"F2A": 1, "F2B": 1},
                   "retries": 0,
                   "uploads_consumed": 1,
                   "f2b_requires": "F2A completed with clean attribution"},
        "canonical_promotion": {"in_this_package": 0},
        "gates": {"f2a_B1_B10": gates_a, "decomposition_D1_D10": d_gates,
                  "f2a_timing": timing_a},
        "candidates": frozen}
    (PKG / "experiment_freeze_v2_008.json").write_text(
        json.dumps(experiment, indent=1, ensure_ascii=False),
        encoding="utf-8")
    for cand in frozen:
        print(json.dumps({"checkpoint": "V2008_PAIR_FROZEN",
                          "candidate": cand["candidate_id"],
                          "identity":
                              cand["generation_semantic_identity"][:16],
                          "chars": cand["creative_body_chars"],
                          "words": cand["creative_body_words"]}))

    receipt = make_experiment_admission_receipt(
        experiment_id="V2-008",
        target_quality_debt_ids=["QD-001"],
        canonical_baseline_sha256=QUALITY_V2_CANONICAL_BASELINE,
        hypothesis="A close-start F2A removes provider action-delay from "
                   "the 2.8 s editorial window, while a qualified "
                   "far-side full-frame reference anchors F2B to the "
                   "correct storm-gate world and geography.",
        variables_changed=["F2A pacing/start position",
                           "F2B world reference"],
        variables_held_constant=[
            "story meaning", "character identity authority",
            "screen direction", "two-shot editorial design",
            "total 5.6 s duration", "provider route", "model route",
            "F1/F3 continuity"],
        max_generate_budget=2,
        provider_route="the exact currently qualified Flow/Veo route "
                       "(flow_veo / veo_3_1_r2v_lite / project "
                       "93a579b4-834e-435b-8304-5f6682937935 / "
                       "clean-pro-qualified)",
        acceptance_criteria=[
            "F2A A1-A12 ALL PASS; F2B B1-B17 ALL PASS",
            "pair P1-P10 only when both pass; WORLD_MATCH across the "
            "cut is decisive",
            "IDENTITY must not REGRESS",
            "canonical promotion 0; Owner decision required"],
        owner_review_surface="OWNER_REVIEW/V2_008 (BASELINE_F2, "
                             "F2A_REVISED, F2B_WORLD_ANCHORED, "
                             "NEW_F2_PAIR, COMPARE_REEL) + atomic-pair "
                             "template",
        rollback_plan="not applicable to canonical state: no canonical "
                      "mutation; the pair remains evidence-only unless "
                      "the Owner selects it for a future promotion "
                      "package")
    known = load_frozen_debt_ids(ROOT)
    gate = admission_gate(receipt, known_debt_ids=known)
    if gate["status"] != "ADMITTED":
        raise SystemExit("BLOCKED_INVARIANT")
    (PKG / "experiment_admission_v2_008.json").write_text(
        json.dumps({"version": "experiment-admission-v2-008-v1",
                    "checkpoint": "V2008_P7_ADMISSION_PROVEN",
                    "admission_required_from": ADMISSION_REQUIRED_FROM,
                    "receipt": receipt, "gate_result": gate,
                    "uploads_note": "1 upload already consumed by the "
                                    "reference qualification (before "
                                    "any Generate)",
                    "known_debt_ids": known}, indent=1),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2008_P7_ADMISSION_PROVEN",
                      "receipt_id": receipt["receipt_id"]}))
    return 0


def _intent_from(raw: dict) -> DirectorIntent:
    return DirectorIntent.model_validate(raw)


if __name__ == "__main__":
    raise SystemExit(main())
