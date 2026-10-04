"""FLOW-ACTION-INTENT-CAUSALITY-018 (Phase 10): freeze the causal canary
matrix BEFORE Generate #1 — three candidates, exact prompts, hashes,
route, references, budget. Nothing here mutates provider state.
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

D17 = ROOT / "projects/flow_performance_motion_canary_017"
D18 = ROOT / "projects/flow_action_intent_causality_018"
FIXTURES = ROOT / "fixtures/requal018"

F2C_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2C_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"
BASE_REF = "asset_2ab16c9f6aff842e3c3c15b2f1b0619217f3925a0ab2ae255b9fcd86d60a0ae2"
BASE_REF_SHA = "ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4ddf0bc3a0ca4e8"

F2_INTENT = {
    "schema_version": "action-intent-v1",
    "trigger": "a hard gust funnels hard",
    "perception": "the funneled wind hits him",
    "character_goal": "the road onward",
    "motivation": "the storm is the obstacle",
    "obstacle_or_pressure": "wind constant against him",
    "chosen_action": "he drives a step through the funnel",
    "intended_outcome": "he breaks through the worst gust",
    "resulting_state": "the effort shows and is held",
    "next_decision": "the cost is held at the wall (F3)",
    "visual_legibility_requirements": ["the gate contact pushes onward"]}
G3_INTENT = {
    "schema_version": "action-intent-v1",
    "trigger": "the arc completed",
    "perception": "the effort leaving the body",
    "character_goal": "release the effort",
    "motivation": "resolution before the road",
    "obstacle_or_pressure": "",
    "chosen_action": "one long exhale; shoulders settle",
    "intended_outcome": "face at rest, eyes forward",
    "resulting_state": "the faintest ease",
    "next_decision": "the walk resumes (G4)",
    "visual_legibility_requirements": []}

CANDIDATES = [
    {"candidate_id": "F2C-P018-A", "shot_id": "SEQ7_F2C_P018_A",
     "purpose": "CAUSAL_INTENT_ONLY (017-C motion control + the "
                "authoritative trigger/goal/action/outcome chain)",
     "base_fixture": D17 / ".." / ".." /
     "fixtures/requal017/SEQ7_F2C_P017_C.json",
     "behavior_state": "shoulder lowered into the wind",
     "extra_beats": [], "reference": "F2C_BINDING",
     "drop_first_beat": True, "drop_beat_labels": False,
     "drop_hip_rotation": True, "short_ends": True,
     "drop_settle_beat": True, "trim_foot_plant": True,
     "editorial_target_duration": 5.6},
    {"candidate_id": "F2C-P018-B", "shot_id": "SEQ7_F2C_P018_B",
     "purpose": "CAUSAL_INTENT + VISUAL_LEGIBILITY (adds the minimum "
                "in-frame reaction cue: one glance into the funneling "
                "gust before the drive — nothing beyond authority)",
     "base_fixture": D17 / ".." / ".." /
     "fixtures/requal017/SEQ7_F2C_P017_C.json",
     "behavior_state": "glances into the gust, shoulder lowered",
     "extra_beats": [], "reference": "F2C_BINDING",
     "drop_first_beat": True, "drop_beat_labels": True,
     "drop_hip_rotation": True, "short_ends": True,
     "trim_foot_plant": True,
     "editorial_target_duration": 5.6},
    {"candidate_id": "G3C-P018-C", "shot_id": "SEQ7_G3C_P018_C",
     "purpose": "REACTION_CAUSALITY (ties the exhale visibly to the "
                "completed arc's effort; no generic breathing)",
     "base_fixture": D17 / ".." / ".." /
     "fixtures/requal017/SEQ7_G3C_P017_D.json",
     "behavior_state": "one long exhale", "extra_beats": [],
     "reference": "BASE_REFERENCE", "drop_first_beat": False,
     "drop_beat_labels": False, "drop_hip_rotation": True,
     "short_ends": False, "drop_setting": True,
     "drop_all_setting": True,
     "editorial_target_duration": 3.2},
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
    FIXTURES.mkdir(parents=True, exist_ok=True)
    caps = flow_capabilities()
    frozen = []
    for cand in CANDIDATES:
        payload = json.loads(Path(cand["base_fixture"]).read_text(
            encoding="utf-8"))
        payload["shot_id"] = cand["shot_id"]
        payload["characters"][0]["behavior_state"] = cand["behavior_state"]
        if cand.get("drop_first_beat"):
            payload["blocking"]["action_beats"] = \
                payload["blocking"]["action_beats"][1:]
        if cand.get("drop_setting"):
            payload["environment"].pop("time_of_day", None)
        if cand.get("drop_all_setting"):
            payload["environment"] = {}
        if cand.get("drop_settle_beat") and payload.get(
                "performance_spec", {}).get("beats"):
            payload["performance_spec"]["beats"] = [
                b for b in payload["performance_spec"]["beats"]
                if b.get("label") != "settle"]
        if cand.get("short_ends"):
            payload["blocking"]["end"] = "worst gust"
        if cand.get("short_ends"):
            payload["dramatic_purpose"] = "the wind funnels hard"
        if "performance_spec" in payload:
            spec_dict = payload["performance_spec"]
            if cand.get("drop_beat_labels"):
                spec_dict.pop("beats", None)
            if cand.get("drop_hip_rotation"):
                spec_dict.pop("hip_torso_rotation", None)
            if cand.get("trim_foot_plant"):
                spec_dict["foot_plant"] = "front foot plants"
            payload["performance_spec"] = spec_dict
        payload["action_intent"] = dict(
            G3_INTENT if cand["reference"] == "BASE_REFERENCE"
            else F2_INTENT)
        validate_contract("shot_spec", payload)
        fixture_path = FIXTURES / f"{cand['shot_id']}.json"
        fixture_path.write_text(json.dumps(payload, indent=1),
                                encoding="utf-8")
        spec = ShotSpec.model_validate(payload)
        ref = F2C_REF if cand["reference"] == "F2C_BINDING" else BASE_REF
        ref_sha = F2C_REF_SHA if cand["reference"] == "F2C_BINDING" \
            else BASE_REF_SHA
        shot = spec.model_copy(update={
            "references": References(other_asset_ids=[ref])})
        plan = compile_prompt(shot, caps, reference_hashes={ref: ref_sha})
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
            "reference_kind": ("last_frame (SEQ7_F1)" if cand["reference"]
                               == "F2C_BINDING" else
                               "same_reference (base reference)")})
    experiment = {
        "version": "causal-canary-experiment-018-v1",
        "frozen_before_generate_1": True,
        "intent_authority": "action_authority_trace_018.json gate_A1 = "
                            "RESOLVED for F2 and G3",
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
        "budget": {"max_new_generates": 3, "retries": 0, "uploads": 0,
                   "ambiguity": "any provider ambiguity -> "
                                "OWNER_AMBIGUITY_GATE; no retry; no "
                                "redispatch; no alternate scope"},
        "baseline_binding": {
            "F2C": {"media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
                    "attestation_id": "refbind_f4277ac1a7a5651c837021241"
                                      "7c06593f08a003aee1676517622292f37"
                                      "cb4fdf",
                    "reference_image_sha256": F2C_REF_SHA},
            "G3C": {"media_id": "7b725f7b-4da5-4455-a6f2-135c4ba22397",
                    "reference_image_sha256": BASE_REF_SHA}},
        "candidates": frozen}
    (D18 / "experiment_freeze_018.json").write_text(
        json.dumps(experiment, indent=1), encoding="utf-8")
    for cand in frozen:
        print(json.dumps({"candidate": cand["candidate_id"],
                          "chars": cand["creative_body_chars"],
                          "words": cand["creative_body_words"]}))


if __name__ == "__main__":
    main()
