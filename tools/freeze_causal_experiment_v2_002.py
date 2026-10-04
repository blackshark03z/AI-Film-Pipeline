"""AI-FILM-QUALITY-V2-002 — Phase 3 (redesign) + Phase 4 (freeze).

P3: redesign ONLY the F2 candidate semantics on the existing rails
(ShotSpec + ActionIntent + PerformanceSpec + flow-r2v-causal-compact-v1)
— no parallel models, no new story events.

P4: freeze the TWO-candidate experiment BEFORE Generate #1: fixtures,
ActionIntent, PerformanceSpec, prompt previews, digests, route,
references, budget (MAX 2), critical negatives. Nothing here mutates
provider state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.core import (ActionIntent, References, ShotSpec,
                                sha256, validate_contract)
from film_pipeline.compiler import compile_prompt
from film_pipeline.performance import BodyProportionAuthority
from film_pipeline.performance_compiler import compile_causal_r2v_prompt
from run_scene_scale_003 import flow_capabilities

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"
FIXTURES = ROOT / "fixtures/requal002"
INTENT = json.loads((PKG / "owner_approved_f2_intent_v2_002.json")
                    .read_text(encoding="utf-8"))

F2C_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2C_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"
F2C_BINDING = {
    "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
    "asset_id": F2C_REF,
    "attestation_id": "refbind_f4277ac1a7a5651c8370212417c06593f08a003aee"
                      "1676517622292f37cb4fdf",
    "mechanism": "last_frame", "from_shot": "SEQ7_F1",
    "source_frame_sha256": F2C_REF_SHA}

V2_001_FINAL_REVISION = "5793dc55bb1ae5d5ff2cb22e02e0ead760f53f46"

# The Owner-approved intent mapped onto action-intent-v1 (no new story
# events; every field traces to the frozen intent text).
F2_INTENT_V2 = {
    "schema_version": "action-intent-v1",
    "trigger": "a hard gust hits the gate",
    "perception": "he reads the gust's force",
    "character_goal": "through the gate",
    "motivation": "the journey continues past the gate",
    "obstacle_or_pressure": "the gust drives against him",
    "chosen_action": "he lowers and advances through the gust",
    "intended_outcome": "he emerges past the gate",
    "resulting_state": "he pauses briefly to recover",
    "next_decision": "the journey resumes (F3)",
    "visual_legibility_requirements": [
        "forward passage through the gate stays visible",
        "the rock is support, never destination"],
    "stakes": "the path is blocked until he passes",
    "urgency": "steady, deliberate",
    "knowledge_state": "he knows the wind, he chooses passage"}

CRITICAL_NEGATIVES = [
    "cover at rock", "end at rock", "aimless touch",
    "no early end"]
CRITICAL_NEGATIVES_FULL = [
    "do NOT turn the action into taking cover behind the rock",
    "do NOT make brace-at-rock the terminal state",
    "do NOT run toward the rock without clear purpose",
    "do NOT touch the rock as an isolated meaningless gesture",
    "do NOT end before the through-state is visually clear"]

COMMON_PRESERVE = [
    "rock gate walls consistent with SEQ7_F1 last frame",
    "wardrobe unchanged",
    "wind direction constant against him",
    "he keeps moving toward and through the gate"]

CANDIDATES = [
    {"candidate_id": "F2C-V2-002-A", "shot_id": "SEQ7_F2C_V2_002_A",
     "purpose": "CAUSAL_CLEAN — maximize visual clarity of gust -> "
                "resistance -> deliberate forward movement -> through-"
                "state; blocking simple; stone contact omitted entirely; "
                "no sword action, no unrelated gesture",
     "behavior_state": "pushes through",
     "dramatic_purpose": "pass the gate against the gust",
     "blocking_start": "gate mouth",
     "blocking_end": "past the gate",
     "performance_spec": {
         "schema_version": "performance-spec-v1",
         "primary_action": "advances through the gate against the gust",
         "action_intent": "the body answers the gust by passing it",
         "weight_transfer": "weight low, forward",
         "motion_energy": "moderate",
         "beats": [
             {"label": "lower", "approx_start_s": 0.0,
              "description": "he reads the gust and lowers"},
             {"label": "advance", "approx_start_s": 2.0,
              "description": "deliberate steps through the gust"},
             {"label": "emerge", "approx_start_s": 5.5,
              "description": "he clears the gate, settles"}]},
     "editorial_target_duration": 5.6},
    {"candidate_id": "F2C-V2-002-B", "shot_id": "SEQ7_F2C_V2_002_B",
     "purpose": "CAUSAL + PERFORMANCE REFINEMENT — same story meaning as "
                "A plus bounded physical realism: visible weight shift "
                "into the wind, planted steps, torso inclination, "
                "controlled progression, recovery after crossing; a "
                "brief stone brace only as visible balance support; no "
                "new story meaning, no action showcase",
     "behavior_state": None,
     "dramatic_purpose": "pass the gate against the gust",
     "blocking_start": "gate mouth",
     "blocking_end": "past the gate",
     "performance_spec": {
         "schema_version": "performance-spec-v1",
         "primary_action": "advances through the gate against the gust",
         "action_intent": "the body answers the gust by passing it",
         "weight_transfer": "weight forward",
         "contact_event": "hand braces stone",
         "motion_energy": "moderate",
         "beats": [
             {"label": "lower", "approx_start_s": 0.0,
              "description": "he reads the gust and sinks lower"},
             {"label": "advance", "approx_start_s": 1.6,
              "description": "planted steps drive through the gust"},
             {"label": "brace", "approx_start_s": 3.2,
              "description": "one hand steadies on the stone, moving"},
             {"label": "emerge", "approx_start_s": 5.0,
              "description": "he clears the gate, settles forward"}]},
     "editorial_target_duration": 5.6},
]


def body_variant(avoid: bool) -> BodyProportionAuthority:
    payload = json.loads((ROOT / "fixtures/character_bible/"
                          "swordsman_white_robes_body_v1.json")
                         .read_text(encoding="utf-8"))
    base = BodyProportionAuthority(**{k: v for k, v in payload.items()
                                      if k not in ("extends",
                                                   "look_state_id")})
    return base.model_copy(
        update={"avoid_short_compact_silhouette": avoid})


def main() -> None:
    admission = json.loads((PKG / "experiment_admission_v2_002.json")
                           .read_text(encoding="utf-8"))

    # ---- P3: redesign record ------------------------------------------
    redesign = {
        "version": "f2-redesign-v2-002-v1",
        "checkpoint": "V2002_P3_REDESIGN_FROZEN",
        "reuses_existing_models_only": ["NarrativeBeat/ShotSpec",
                                        "ActionIntent (action-intent-v1)",
                                        "PerformanceSpec (performance-spec"
                                        "-v1)", "flow-r2v-causal-compact-v1",
                                        "BodyProportionAuthority v1"],
        "no_parallel_models": True,
        "dominant_objective": "PASS THROUGH THE GATE AGAINST THE GUST",
        "visible_chain": [
            "gust exists", "character understands resistance",
            "goal is forward passage", "body works against gust",
            "temporary brace/support if needed",
            "character exits beyond the gate"],
        "intent_mapping": F2_INTENT_V2,
        "critical_negatives_compiled_into_constraints": CRITICAL_NEGATIVES,
        "critical_negatives_full_owner_wording": CRITICAL_NEGATIVES_FULL,
        "envelope_limitation_note": "the 8-second render envelope with a "
                                    "5.6s editorial trim must carry the "
                                    "whole chain in ONE shot; if it cannot "
                                    "communicate cleanly the limitation "
                                    "is recorded — the shot is NOT split "
                                    "in this package (no canonical "
                                    "editorial structure change)",
        "intent_fingerprint": INTENT["intent_fingerprint"],
        "intent_authority": "owner_approved_f2_intent_v2_002.json"}
    (PKG / "f2_redesign_v2_002.json").write_text(
        json.dumps(redesign, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P3_REDESIGN_FROZEN"}))

    # ---- P4: candidate fixtures + freeze -------------------------------
    FIXTURES.mkdir(parents=True, exist_ok=True)
    caps = flow_capabilities()
    frozen = []
    for cand in CANDIDATES:
        payload = json.loads(
            (ROOT / "fixtures/requal018/SEQ7_F2C_P018_A.json")
            .read_text(encoding="utf-8"))
        payload["shot_id"] = cand["shot_id"]
        if cand["behavior_state"] is not None:
            payload["characters"][0]["behavior_state"] = cand["behavior_state"]
        else:
            payload["characters"][0]["behavior_state"] = None
        payload["dramatic_purpose"] = cand["dramatic_purpose"]
        payload["environment"] = {"weather": "storm",
                                  "atmosphere": "narrow rock gate"}
        payload["blocking"]["start"] = cand["blocking_start"]
        payload["blocking"]["end"] = cand["blocking_end"]
        payload["blocking"]["action_beats"] = []
        payload["performance"] = {
            "observable_beats": [],
            "forbidden": CRITICAL_NEGATIVES}
        payload["continuity"]["critical_invariants"] = COMMON_PRESERVE
        payload["performance_spec"] = cand["performance_spec"]
        payload["action_intent"] = dict(F2_INTENT_V2)
        validate_contract("shot_spec", payload)
        fixture_path = FIXTURES / f"{cand['shot_id']}.json"
        fixture_path.write_text(json.dumps(payload, indent=1),
                                encoding="utf-8")
        spec = ShotSpec.model_validate(payload)
        shot = spec.model_copy(update={
            "references": References(other_asset_ids=[F2C_REF])})
        plan = compile_prompt(shot, caps,
                              reference_hashes={F2C_REF: F2C_REF_SHA})
        prompt = compile_causal_r2v_prompt(
            plan, "job_" + "0" * 64, model="veo_3_1_r2v_lite",
            performance_spec=shot.performance_spec,
            body_authority=body_variant(True),
            action_intent=shot.action_intent)
        body_text = prompt.text.rsplit(" [FILM-", 1)[0]
        if len(body_text) > 500 or len(prompt.text.split()) > 76:
            raise SystemExit(f"{cand['candidate_id']} over the envelope: "
                             f"{len(body_text)} chars / "
                             f"{len(prompt.text.split())} words")
        frozen.append({
            "candidate_id": cand["candidate_id"],
            "shot_id": cand["shot_id"],
            "purpose": cand["purpose"],
            "fixture": fixture_path.relative_to(ROOT).as_posix(),
            "fixture_sha256": sha256(shot),
            "prompt_compiler_version": prompt.version,
            "creative_body": body_text,
            "creative_body_chars": len(body_text),
            "creative_body_words": len(prompt.text.split()),
            "action_intent_digest": shot.action_intent.digest(),
            "performance_spec_digest": shot.performance_spec.digest(),
            "editorial_target_duration": cand["editorial_target_duration"],
            "reference_kind": "last_frame (SEQ7_F1)",
            "reference_media_id": F2C_BINDING["media_id"]})

    experiment = {
        "version": "quality-v2-002-experiment-freeze-v1",
        "checkpoint": "V2002_P4_EXPERIMENT_FROZEN",
        "frozen_before_generate_1": True,
        "authority_binding": {
            "v1_baseline": "14ba281d12c15a5678a3fe1b3f0242f577512e5f",
            "v2_001_final_revision": V2_001_FINAL_REVISION,
            "canonical_master_sha256":
                "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda"
                "1786595",
            "canonical_f2_predecessor": INTENT["canonical_predecessor"],
            "owner_intent_fingerprint": INTENT["intent_fingerprint"],
            "admission_receipt_id": admission["receipt"]["receipt_id"],
            "quality_debt": "QD-001"},
        "intent_authority": "owner_approved_f2_intent_v2_002.json "
                            "(Owner-approved, used EXACTLY; no new story "
                            "events)",
        "route": {
            "provider_id": "flow_veo", "model_label": "veo_3_1_r2v_lite",
            "project_id": "93a579b4-834e-435b-8304-5f6682937935",
            "account_id": "clean-pro-qualified",
            "route_qualification": "the exact currently qualified route "
                                   "(unchanged since Packages 003-009)"},
        "generation_settings": {
            "duration_s": 8, "aspect": "16:9 (1280x720)",
            "references_per_shot": 1,
            "reference_media": "already-bound provider media only; "
                               "0 uploads"},
        "compiler": {"canonical": "deterministic-v1",
                     "wire": "flow-r2v-causal-compact-v1",
                     "limits": {"max_chars": 500, "max_words": 75}},
        "budget": {"max_new_generates": 2, "retries": 0, "uploads": 0,
                   "ambiguity": "any provider ambiguity -> "
                                "OWNER_AMBIGUITY_GATE; no retry; no "
                                "redispatch; no alternate scope",
                   "per_candidate": "each candidate gets AT MOST one "
                                    "submission"},
        "canonical_promotion": {"in_this_package": 0,
                                "if_owner_selects": "STOP at "
                                "OWNER_SELECTED; V2-003 qualifies the "
                                "PromotionEnvironment"},
        "baseline_binding": {
            "F2C": {"media_id": F2C_BINDING["media_id"],
                    "attestation_id": F2C_BINDING["attestation_id"],
                    "reference_image_sha256": F2C_REF_SHA}},
        "critical_negatives": CRITICAL_NEGATIVES,
        "candidates": frozen}
    (PKG / "experiment_freeze_v2_002.json").write_text(
        json.dumps(experiment, indent=1, ensure_ascii=False),
        encoding="utf-8")
    for cand in frozen:
        print(json.dumps({"checkpoint": "V2002_P4_EXPERIMENT_FROZEN",
                          "candidate": cand["candidate_id"],
                          "chars": cand["creative_body_chars"],
                          "words": cand["creative_body_words"]}))


if __name__ == "__main__":
    main()
