"""FLOW-PERFORMANCE-MOTION-CANARY-017 (Phase 8): freeze the live
experiment BEFORE Generate #1.

Writes the four candidate fixtures (creative reduction applied to fit
the qualified 500-char/75-word wire envelope — same narrative intent as
the canonical baselines), compiles every candidate prompt through the
performance compiler, records the exact frozen bodies + fingerprints,
the route, references, settings, the advisory complexity classes, and
the hard budget. Nothing here mutates any provider or canonical state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.core import References, ShotSpec, sha256, validate_contract
from film_pipeline.compiler import compile_prompt
from film_pipeline.performance import (BodyProportionAuthority,
                                       PerformanceSpec,
                                       classify_action_complexity)
from film_pipeline.performance_compiler import compile_performance_r2v_prompt
from run_scene_scale_003 import flow_capabilities

D17 = ROOT / "projects/flow_performance_motion_canary_017"
FIXTURES = ROOT / "fixtures/requal017"

F2C_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2C_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"
BASE_REF = "asset_2ab16c9f6aff842e3c3c15b2f1b0619217f3925a0ab2ae255b9fcd86d60a0ae2"
BASE_REF_SHA = "ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4ddf0bc3a0ca4e8"


def base_body() -> BodyProportionAuthority:
    payload = json.loads((ROOT / "fixtures/character_bible/"
                          "swordsman_white_robes_body_v1.json")
                         .read_text(encoding="utf-8"))
    return BodyProportionAuthority(**{k: v for k, v in payload.items()
                                      if k not in ("extends",
                                                   "look_state_id")})


def body_variant(avoid: bool) -> BodyProportionAuthority:
    return base_body().model_copy(
        update={"avoid_short_compact_silhouette": avoid})


F2C_BASE = {
    "schema_version": "1.0.0", "spec_version": 1,
    "scene_id": "SCENE_F_STORM_GATE", "duration_target_s": 8,
    "shot_type": "action",
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
                   "critical_invariants": ["rock gate walls consistent "
                                           "with SEQ7_F1 last frame",
                                           "wardrobe unchanged",
                                           "wind direction constant "
                                           "against him"]},
}

G3C_BASE = {
    "schema_version": "1.0.0", "spec_version": 1,
    "scene_id": "SCENE_G_HIGH_PLATEAU", "duration_target_s": 8,
    "shot_type": "performance",
    "characters": [{"character_id": "swordsman_white_robes",
                    "identity_version": "swordsman_white_robes_v1",
                    "look_state_id": "white_robes_cloud_summit_dawn_v1",
                    "behavior_state": "one long exhale"}],
    "camera": {"framing": "CU", "height": "eye_level",
               "lens_intent": "portrait", "movement": {"type": "locked"}},
    "environment": {"time_of_day": "late day", "weather": "clearing",
                    "atmosphere": "high plateau, low light"},
    "blocking": {"start": "face still from effort",
                 "action_beats": ["the exhale"],
                 "end": "face at rest", "prop_interactions": []},
    "performance": {"observable_beats": [], "forbidden": []},
    "lighting": {},
    "continuity": {"screen_direction": "faces frame-left",
                   "eyeline": "down the road ahead", "start_state": {},
                   "end_state": {},
                   "critical_invariants": ["no face identity drift",
                                           "same hair and headband",
                                           "late-day light consistent"]},
}

CANDIDATES = [
    {
        "candidate_id": "F2C-P017-A",
        "shot_id": "SEQ7_F2C_P017_A",
        "purpose": "BODY_PROPORTION_ONLY",
        "dramatic_purpose": "inside the gate the wind funnels hard",
        "body_avoid": True,
        "spec": {"primary_action": "drives a step through a hard gust"},
        "editorial_target_duration": 5.6,
        "reference": "F2C_BINDING",
    },
    {
        "candidate_id": "F2C-P017-B",
        "shot_id": "SEQ7_F2C_P017_B",
        "purpose": "PERFORMANCE_MOTION_ONLY",
        "dramatic_purpose": "inside the gate the wind funnels hard",
        "body_avoid": False,
        "spec": {"primary_action": "drives a step through a hard gust",
                 "action_intent": "the body answers the gust",
                 "weight_transfer": "weight rolls over the planted foot",
                 "foot_plant": "front foot plants first",
                 "hip_torso_rotation": "hips and shoulders counter-rotate",
                 "arm_countermotion": "arms counter-swing",
                 "secondary_motion": "robes and hair trail the motion",
                 "motion_energy": "moderate",
                 "beats": [
                     {"label": "anticipation",
                      "description": "shoulder coils against the gust"},
                     {"label": "drive",
                      "description": "the step drives through"},
                     {"label": "plant",
                      "description": "front foot plants"},
                     {"label": "settle",
                      "description": "body settles over the foot"}]},
        "editorial_target_duration": 5.6,
        "reference": "F2C_BINDING",
    },
    {
        "candidate_id": "F2C-P017-C",
        "shot_id": "SEQ7_F2C_P017_C",
        "purpose": "COMBINED (main candidate)",
        "dramatic_purpose": "inside the gate the wind funnels hard",
        "body_avoid": True,
        "spec": {"primary_action": "drives a step through a hard gust",
                 "action_intent": "the body answers the gust",
                 "weight_transfer": "weight rolls over the planted foot",
                 "foot_plant": "front foot plants first",
                 "hip_torso_rotation": "hips and shoulders counter-rotate",
                 "secondary_motion": "robes trail the motion",
                 "motion_energy": "moderate",
                 "beats": [
                     {"label": "load",
                      "description": "shoulder coils against the gust"},
                     {"label": "drive",
                      "description": "the step drives through"},
                     {"label": "plant",
                      "description": "front foot plants"},
                     {"label": "settle",
                      "description": "body settles over the foot"}]},
        "editorial_target_duration": 5.6,
        "reference": "F2C_BINDING",
    },
    {
        "candidate_id": "G3C-P017-D",
        "shot_id": "SEQ7_G3C_P017_D",
        "purpose": "GENERALIZATION_CHECK (combined on the sword/body "
                   "performance case)",
        "dramatic_purpose": "the exhale after the arc; the day lets go",
        "body_avoid": True,
        "spec": {"primary_action": "one long exhale and settling",
                 "action_intent": "the effort leaves the body",
                 "anticipation": "breath draws in first",
                 "recovery": "shoulders and chest visibly settle",
                 "motion_energy": "low",
                 "beats": [
                     {"label": "inhale", "description": "breath draws in"},
                     {"label": "exhale", "description": "long exhale out"},
                     {"label": "settle",
                      "description": "shoulders drop, face eases"}]},
        "editorial_target_duration": 3.2,
        "reference": "BASE_REFERENCE",
    },
]


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    D17.mkdir(parents=True, exist_ok=True)
    caps = flow_capabilities()
    frozen = []
    for cand in CANDIDATES:
        payload = json.loads(json.dumps(
            F2C_BASE if cand["reference"] == "F2C_BINDING" else G3C_BASE))
        payload["shot_id"] = cand["shot_id"]
        payload["dramatic_purpose"] = cand["dramatic_purpose"]
        payload["performance_spec"] = {
            "schema_version": "performance-spec-v1",
            **cand["spec"]}
        validate_contract("shot_spec", payload)
        fixture_path = FIXTURES / f"{cand['shot_id']}.json"
        fixture_path.write_text(json.dumps(payload, indent=1),
                                encoding="utf-8")
        shot = ShotSpec.model_validate(payload).model_copy(update={
            "references": References(other_asset_ids=[
                F2C_REF if cand["reference"] == "F2C_BINDING"
                else BASE_REF])})
        ref_sha = F2C_REF_SHA if cand["reference"] == "F2C_BINDING" \
            else BASE_REF_SHA
        plan = compile_prompt(shot, caps, reference_hashes={
            shot.references.other_asset_ids[0]: ref_sha})
        prompt = compile_performance_r2v_prompt(
            plan, "job_" + "0" * 64, model="veo_3_1_r2v_lite",
            performance_spec=shot.performance_spec,
            body_authority=body_variant(cand["body_avoid"]))
        body_text = prompt.text.rsplit(" [FILM-", 1)[0]
        if len(body_text) > 500 or len(prompt.text.split()) > 76:
            raise SystemExit(f"{cand['candidate_id']} over the wire "
                             f"envelope: {len(body_text)} chars / "
                             f"{len(prompt.text.split())} words")
        complexity = classify_action_complexity(
            shot.performance_spec, camera_locked=True)
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
            "body_avoid_short_compact": cand["body_avoid"],
            "advisory_complexity": complexity,
            "editorial_target_duration": cand["editorial_target_duration"],
            "reference_kind": ("last_frame (SEQ7_F1)" if
                               cand["reference"] == "F2C_BINDING"
                               else "same_reference (base reference)")})
    experiment = {
        "version": "motion-canary-experiment-017-v1",
        "frozen_before_generate_1": True,
        "route": {
            "provider_id": "flow_veo", "model_label": "veo_3_1_r2v_lite",
            "project_id": "93a579b4-834e-435b-8304-5f6682937935",
            "account_id": "clean-pro-qualified",
            "transport": "headful native UI, OneGenerateGuard",
            "route_qualification": "the exact currently qualified "
                                   "production Flow route (Packages "
                                   "003/007/008/009); unchanged"},
        "generation_settings": {
            "duration_s": 8, "aspect": "16:9 (1280x720)",
            "references_per_shot": 1,
            "reference_media": "already-bound provider media only; "
                               "0 uploads authorized"},
        "compiler": {
            "canonical": "deterministic-v1",
            "wire": "flow-r2v-performance-compact-v1",
            "limits": {"max_chars": 500, "max_words": 75}},
        "budget": {"max_new_generates": 4, "retries": 0,
                   "uploads": 0,
                   "ambiguity": "OWNER_AMBIGUITY_GATE on any external-"
                                "effect ambiguity; no workaround scopes"},
        "candidates": frozen,
        "baseline_binding": {
            "F2C": {"media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
                    "attestation_id": "refbind_f4277ac1a7a5651c837021241"
                                      "7c06593f08a003aee1676517622292f37"
                                      "cb4fdf",
                    "reference_image_sha256": F2C_REF_SHA},
            "G3C": {"media_id": "7b725f7b-4da5-4455-a6f2-135c4ba22397",
                    "reference_image_sha256": BASE_REF_SHA}},
    }
    (D17 / "experiment_freeze_017.json").write_text(
        json.dumps(experiment, indent=1), encoding="utf-8")
    for cand in frozen:
        print(json.dumps({"candidate": cand["candidate_id"],
                          "chars": cand["creative_body_chars"],
                          "words": cand["creative_body_words"],
                          "risk": cand["advisory_complexity"]
                          ["motion_risk_class"]}))


if __name__ == "__main__":
    main()
