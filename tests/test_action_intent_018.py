"""Action-intent causal layer tests (Package-018 Phases 2-7)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from film_pipeline.action_intent import (
    OBSERVABILITY_CLASSES, build_shot_causality_graph,
    check_causal_legibility, classify_causal_complexity,
    classify_observability)
from film_pipeline.compiler import compile_prompt
from film_pipeline.core import (ActionIntent, References, ShotSpec,
                                validate_contract)
from film_pipeline.performance import (BodyProportionAuthority,
                                       PerformanceBeat, PerformanceSpec)
from film_pipeline.performance_compiler import (compile_causal_r2v_prompt,
                                                compile_performance_r2v_prompt)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_scene_scale_003 import flow_capabilities  # noqa: E402

F2C_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2C_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"


def f2_intent() -> ActionIntent:
    return ActionIntent(
        trigger="a hard gust funnels hard",
        character_goal="the road onward",
        chosen_action="he drives a step through the funnel",
        intended_outcome="he breaks through the worst gust",
        resulting_state="the effort shows and is held",
        next_decision="the cost is held at the rock wall (F3)",
        visual_legibility_requirements=[
            "the gate contact pushes the drive onward"])


def g3_intent() -> ActionIntent:
    return ActionIntent(
        trigger="the draw's arc completed (G2)",
        perception="the effort leaving the body",
        character_goal="release the effort",
        chosen_action="one long exhale; shoulders settle",
        intended_outcome="face at rest, eyes forward",
        next_decision="the walk resumes (G4)")


def test_01_action_intent_contract_minimal_and_versioned():
    intent = ActionIntent()
    assert intent.schema_version == "action-intent-v1"
    assert intent.digest() == intent.digest()
    full = f2_intent()
    assert full.digest() != ActionIntent().digest()


def test_02_action_intent_optional_field_identity_stable():
    payload = json.loads((ROOT / "fixtures/requal009/SEQ7_F2C.json")
                         .read_text(encoding="utf-8"))
    validate_contract("shot_spec", payload)
    legacy = ShotSpec.model_validate(payload)
    assert legacy.action_intent is None
    payload["action_intent"] = {"schema_version": "action-intent-v1",
                                "trigger": "a hard gust hits"}
    validate_contract("shot_spec", payload)
    parsed = ShotSpec.model_validate(payload)
    assert parsed.action_intent.trigger == "a hard gust hits"
    # legacy digest stability: no intent -> identical hash to before
    from film_pipeline.core import canonical_json, sha256
    assert "action_intent" not in canonical_json(legacy)


def test_03_legibility_checks_fail_closed_on_empty_intent():
    out = check_causal_legibility(ActionIntent(), contact_present=False)
    assert out["legibility"] == "NOT_LEGIBLE"
    assert "TRIGGER_VISIBLE_OR_CONTEXTUALLY_ESTABLISHED" in out["failed"]
    assert "GOAL_INFERABLE" in out["failed"]
    assert "NEXT_STATE_CHANGED" in out["failed"]


def test_04_legibility_passes_on_recovered_f2_intent():
    out = check_causal_legibility(f2_intent(), contact_present=True)
    assert out["legibility"] in ("LEGIBLE", "PARTIALLY_LEGIBLE")
    assert out["failed"] == []
    assert out["checks"]["ACTION_SERVES_GOAL"].startswith("PASS")


def test_05_observability_classification():
    classes = set()
    out = classify_observability(
        f2_intent(), trigger_visible_in_frame=True)
    classes.add(out["observability"])  # no declared reaction requirements
    out = classify_observability(
        ActionIntent(trigger="the draw's arc completed (G2)",
                     visual_legibility_requirements=["release reads"]),
        trigger_visible_in_frame=False, framing="CU")
    classes.add(out["observability"])
    assert classes == {"REQUIRES_REACTION_CUE",
                       "REQUIRES_PREVIOUS_SHOT_CONTEXT"}
    assert all(c in OBSERVABILITY_CLASSES for c in classes)
    assert "never rewritten" in out["rule"]


def test_06_causal_complexity_recommendations():
    heavy = ActionIntent(
        trigger="gust hits", perception="wind Funnel",
        character_goal="through the gate", motivation="the road onward",
        resulting_state="through the worst gust",
        next_decision="cost held at the wall",
        visual_legibility_requirements=["gust visible"])
    out = classify_causal_complexity(heavy, locomotion=True,
                                     interaction=True)
    assert out["count"] >= 5
    assert out["recommendations"] != ["NONE"]
    assert "SPLIT_NARRATIVE_BEAT" in out["recommendations"] or \
        "INSERT_REACTION_SHOT" in out["recommendations"]
    light = classify_causal_complexity(g3_intent())
    assert light["recommendations"] == ["NONE"]


def test_07_causality_graph_state_invariant():
    edges = [{
        "previous_shot": "SEQ7_F1", "target_shot": "SEQ7_F2",
        "following_shot": "SEQ7_F3",
        "incoming_world_state": "close to the rock gate, leaning (F1 end)",
        "character_knowledge_state": "feels the storm funnel through the gate",
        "character_goal": "through the gate, road onward",
        "action": "drives a step through the funnel",
        "outcome": "through the worst gust",
        "outgoing_world_state": "pressed near the rock wall (F3 start)",
        "outcome_alters_state": True}]
    graph = build_shot_causality_graph(edges)
    assert graph["edges"][0]["state_change_invariant"] == "PASS"
    with pytest.raises(ValueError, match="meaningless action chain"):
        build_shot_causality_graph([{
            "previous_shot": "A", "target_shot": "B",
            "following_shot": "C", "incoming_world_state": "x",
            "character_knowledge_state": "", "character_goal": "",
            "action": "touches rock", "outcome": "",
            "outgoing_world_state": "x"}])


MINI_F2 = {
    "schema_version": "1.0.0", "spec_version": 1,
    "shot_id": "SEQ7_F2_P018_TEST", "scene_id": "SCENE_F_STORM_GATE",
    "dramatic_purpose": "the storm funnels through the rock gate",
    "duration_target_s": 8, "shot_type": "action",
    "characters": [{"character_id": "swordsman_white_robes",
                    "identity_version": "swordsman_white_robes_v1",
                    "look_state_id": "white_robes_cloud_summit_dawn_v1",
                    "behavior_state": "shoulder lowered into the wind"}],
    "camera": {"framing": "MS", "height": "eye_level",
               "lens_intent": "normal", "movement": {"type": "locked"}},
    "environment": {"time_of_day": "midday", "weather": "storm front",
                    "atmosphere": "narrow rock gate"},
    "blocking": {"start": "gate mouth",
                 "action_beats": ["a hard gust hits"],
                 "end": "through the worst gust",
                 "prop_interactions": []},
    "performance": {"observable_beats": [], "forbidden": []},
    "lighting": {},
    "continuity": {"screen_direction": "faces frame-left",
                   "eyeline": "down the road ahead", "start_state": {},
                   "end_state": {},
                   "critical_invariants": ["wardrobe unchanged"]},
}


def test_08_causal_compiler_renders_chain_in_order():
    payload = json.loads(json.dumps(MINI_F2))
    payload["performance_spec"] = json.loads(PerformanceSpec(
        primary_action="drives a step through a hard gust",
        weight_transfer="weight rolls over the planted foot",
        foot_plant="front foot plants").model_dump_json())
    payload["action_intent"] = json.loads(f2_intent().model_dump_json())
    validate_contract("shot_spec", payload)
    shot = ShotSpec.model_validate(payload).model_copy(update={
        "references": References(other_asset_ids=[F2C_REF])})
    plan = compile_prompt(shot, flow_capabilities(), reference_hashes={
        F2C_REF: F2C_REF_SHA})
    body = BodyProportionAuthority(
        character_id="swordsman_white_robes",
        identity_version="swordsman_white_robes_v1",
        authority_basis="x", avoid_short_compact_silhouette=True)
    prompt = compile_causal_r2v_prompt(
        plan, "job_" + "4" * 64, model="veo_3_1_r2v_lite",
        performance_spec=shot.performance_spec, body_authority=body,
        action_intent=shot.action_intent)
    text = prompt.text
    assert prompt.version == "flow-r2v-causal-compact-v1"
    assert text.index("Trigger:") < text.index("Goal:") < \
        text.index("Action:") < text.index("Movement:") < \
        text.index("Outcome:")
    assert "a hard gust funnels hard" in text
    body_text = text.rsplit(" [FILM-", 1)[0]
    assert len(body_text) <= 500 and len(text.split()) <= 76
    assert text.count("[FILM-") == 1


def test_09_causal_compiler_overlength_fails_closed():
    payload = json.loads(json.dumps(MINI_F2))
    payload["action_intent"] = json.loads(ActionIntent(
        trigger="a hard gust funnels hard through the narrow rock gate "
                "and the whole ridge leans into the storm",
        character_goal="get through the gate and keep moving down the "
                       "long road beyond it today",
        chosen_action="he drives a decisive step through the funnel",
        intended_outcome="he breaks through the worst gust of the day",
        resulting_state="the effort shows and is held in the jaw",
        next_decision="the cost is held at the rock wall in the next "
                      "shot of the sequence").model_dump_json())
    validate_contract("shot_spec", payload)
    shot = ShotSpec.model_validate(payload).model_copy(update={
        "references": References(other_asset_ids=[F2C_REF])})
    plan = compile_prompt(shot, flow_capabilities(), reference_hashes={
        F2C_REF: F2C_REF_SHA})
    with pytest.raises(Exception, match="PROMPT_LIMIT"):
        compile_causal_r2v_prompt(
            plan, "job_" + "5" * 64, model="veo_3_1_r2v_lite",
            performance_spec=PerformanceSpec(primary_action="x"),
            body_authority=BodyProportionAuthority(
                character_id="c", identity_version="v",
                authority_basis="x"),
            action_intent=shot.action_intent)


def test_10_performance_compiler_unchanged_without_intent():
    payload = json.loads(json.dumps(MINI_F2))
    payload["performance_spec"] = json.loads(PerformanceSpec(
        primary_action="drives a step").model_dump_json())
    validate_contract("shot_spec", payload)
    shot = ShotSpec.model_validate(payload).model_copy(update={
        "references": References(other_asset_ids=[F2C_REF])})
    plan = compile_prompt(shot, flow_capabilities(), reference_hashes={
        F2C_REF: F2C_REF_SHA})
    prompt = compile_performance_r2v_prompt(
        plan, "job_" + "6" * 64, model="veo_3_1_r2v_lite",
        performance_spec=shot.performance_spec,
        body_authority=BodyProportionAuthority(
            character_id="c", identity_version="v", authority_basis="x"))
    assert "Trigger:" not in prompt.text
    assert prompt.version == "flow-r2v-performance-compact-v1"
