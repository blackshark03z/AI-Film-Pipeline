"""AI-FILM-QUALITY-V2-004 — Phase 2 (candidate freeze) + Phase 3
(compiler conformance).

Both candidates share the FROZEN DirectorIntent / BlockingSpec /
CameraCoveragePlan / ActionIntent / screen direction / zones / travel
path / route / reference — byte-equivalent. ONLY the performance layer
differs (A pure traversal; A+bio biomechanics refinement). Candidate
semantic identities freeze BEFORE Generate #1. The compiled provider
semantics are mechanically checked for the required spatial content;
if the frozen authorities cannot be expressed inside the qualified
envelope => BLOCKED_INVARIANT (no silent shortening).
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
from film_pipeline.director_blocking import (
    assert_compiler_respected_authority)
from film_pipeline.performance import BodyProportionAuthority
from film_pipeline.performance_compiler import compile_causal_r2v_prompt
from run_scene_scale_003 import flow_capabilities

PKG = ROOT / "projects/quality_v2_004_f2_blocking"
V3 = ROOT / "projects/quality_v2_003_director_blocking"
FIXTURES = ROOT / "fixtures/requal004"

F2C_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2C_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"
F2C_BINDING = {
    "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
    "asset_id": F2C_REF,
    "attestation_id": "refbind_f4277ac1a7a5651c8370212417c06593f08a003aee"
                      "1676517622292f37cb4fdf",
    "mechanism": "last_frame", "from_shot": "SEQ7_F1",
    "source_frame_sha256": F2C_REF_SHA}

FORBIDDEN_ROCK = ["ROCK_CONTACT", "ROCK_BRACE", "ROCK_CIRCLE",
                  "ROCK_SHELTER"]
FORBIDDEN_WIRE = ["cover or stop at rock", "aimless touch", "reversal"]

# the FROZEN ActionIntent (identical for both candidates; same as the
# V2-003/V2-002 authoritative intent)
F2_INTENT_V2 = {
    "schema_version": "action-intent-v1",
    "trigger": "a gust hits the gate",
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

CANDIDATES = [
    {"candidate_id": "F2C-V2-004-A", "shot_id": "SEQ7_F2C_V2_004_A",
     "purpose": "PURE TRAVERSAL — the frozen spatial plan executed with "
                "minimum performance complexity",
     "performance_spec": {
         "schema_version": "performance-spec-v1",
         "primary_action": "advances straight through the gate",
         "action_intent": "commits forward against the gust",
         "motion_energy": "moderate",
         "beats": [
             {"label": "commit", "approx_start_s": 0.0,
              "description": "gust hits, body commits forward"},
             {"label": "cross", "approx_start_s": 3.0,
              "description": "deliberate direct traversal through the "
                             "gate"},
             {"label": "arrive", "approx_start_s": 5.2,
              "description": "clear recovery on the far side"}]},
     "editorial_target_duration": 5.6},
    {"candidate_id": "F2C-V2-004-B", "shot_id": "SEQ7_F2C_V2_004_B",
     "purpose": "SAME BLOCKING + BIOMECHANICS — spatial semantics "
                "byte-equivalent to A; only the performance layer is "
                "refined",
     "performance_spec": {
         "schema_version": "performance-spec-v1",
         "primary_action": "advances straight through the gate",
         "action_intent": "commits forward against the gust",
         "weight_transfer": "weight shifts",
         "foot_plant": "planted steps",
         "hip_torso_rotation": "torso leans in",
         "secondary_motion": "cloth and hair stream",
         "motion_energy": "moderate",
         "beats": [
             {"label": "commit", "approx_start_s": 0.0,
              "description": "gust hits, body commits forward"},
             {"label": "cross", "approx_start_s": 3.0,
              "description": "planted steps drive straight through the "
                             "gate"},
             {"label": "arrive", "approx_start_s": 5.2,
              "description": "natural recovery on the far side"}]},
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
    rebind = json.loads((PKG / "rebind_v2_004.json").read_text(
        encoding="utf-8"))
    admission = json.loads((PKG / "experiment_admission_v2_004.json")
                           .read_text(encoding="utf-8"))
    FIXTURES.mkdir(parents=True, exist_ok=True)
    caps = flow_capabilities()
    frozen = []
    for cand in CANDIDATES:
        payload = json.loads(
            (ROOT / "fixtures/requal002/SEQ7_F2C_V2_002_A.json")
            .read_text(encoding="utf-8"))
        payload["shot_id"] = cand["shot_id"]
        payload["characters"][0]["behavior_state"] = None
        payload["dramatic_purpose"] = "cross the gate"
        # camera fields carry the FROZEN CameraCoveragePlan semantics
        payload["camera"] = {
            "framing": "WS", "height": "eye_level",
            "lens_intent": "normal", "movement": {"type": "locked"}}
        payload["environment"] = {"weather": "storm",
                                  "atmosphere": "rock gate"}
        payload["blocking"] = {
            "start": "near side",
            "action_beats": [],
            "end": "beyond gate, far side clear",
            "prop_interactions": []}
        payload["performance"] = {
            "observable_beats": [],
            "forbidden": FORBIDDEN_WIRE}
        payload["continuity"] = {
            "screen_direction": "faces frame-left",
            "eyeline": "down the road ahead",
            "start_state": {}, "end_state": {},
            "critical_invariants": [
                "rock gate walls consistent with SEQ7_F1 last frame",
                "wardrobe unchanged",
                "wind direction constant against him",
                "keeps moving through the gate, no reversal"]}
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
            raise SystemExit(
                f"BLOCKED_INVARIANT: {cand['candidate_id']} cannot fit "
                f"the qualified envelope ({len(body_text)} chars / "
                f"{len(prompt.text.split())} words); spatial semantics "
                f"must NOT be silently shortened")
        # Phase 3: mechanical conformance of the provider-facing text
        low = body_text.lower()
        required_tokens = ["near side", "far side", "gate", "through"]
        missing = [t for t in required_tokens if t not in low]
        if missing:
            raise SystemExit(
                f"BLOCKED_INVARIANT: compiled semantics lack {missing}")
        assert_compiler_respected_authority(body_text, _frozen_blocking())
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
            "candidate_semantic_identity": sha256({
                "frozen_director_identity":
                    rebind["frozen_identities"][
                        "generation_semantic_identity"],
                "action_intent_digest": shot.action_intent.digest(),
                "performance_spec_digest": shot.performance_spec.digest(),
                "fixture_sha256": sha256(shot),
                "creative_body": body_text}),
            "editorial_target_duration": cand["editorial_target_duration"],
            "reference_kind": "last_frame (SEQ7_F1)",
            "reference_media_id": F2C_BINDING["media_id"]})
    a, b = frozen
    shared = {k: a[k] for k in ("action_intent_digest",)}
    if a["action_intent_digest"] != b["action_intent_digest"]:
        raise SystemExit("BLOCKED_INVARIANT: ActionIntent drifted between "
                         "candidates")
    experiment = {
        "version": "quality-v2-004-experiment-freeze-v1",
        "checkpoint": "V2004_P2_EXPERIMENT_FROZEN",
        "frozen_before_generate_1": True,
        "frozen_director_authority": {
            "director_intent_id": rebind["frozen_identities"][
                "director_intent_id"],
            "blocking_spec_id": rebind["frozen_identities"][
                "blocking_spec_id"],
            "camera_plan_id": rebind["frozen_identities"][
                "camera_plan_id"],
            "generation_semantic_identity":
                rebind["frozen_identities"][
                    "generation_semantic_identity"],
            "not_redesigned": True},
        "byte_equivalence": {
            "shared_by_both_candidates": [
                "DirectorIntent", "BlockingSpec", "CameraCoveragePlan",
                "ActionIntent", "screen direction", "start zone",
                "threshold", "end zone", "travel path", "provider route",
                "reference authority"],
            "only_delta": "performance layer"},
        "route": {
            "provider_id": "flow_veo", "model_label": "veo_3_1_r2v_lite",
            "project_id": "93a579b4-834e-435b-8304-5f6682937935",
            "account_id": "clean-pro-qualified",
            "route_qualification": "UNCHANGED qualified route"},
        "generation_settings": {
            "duration_s": 8, "aspect": "16:9 (1280x720)",
            "references_per_shot": 1,
            "reference_media": "already-bound provider media only; "
                               "0 uploads"},
        "compiler": {"canonical": "deterministic-v1",
                     "wire": "flow-r2v-causal-compact-v1",
                     "limits": {"max_chars": 500, "max_words": 75}},
        "budget": {"max_new_generates": 2, "retries": 0, "uploads": 0,
                   "per_candidate": "ONE submit each",
                   "ambiguity": "OWNER_AMBIGUITY_GATE; do not submit the "
                                "second candidate after ambiguity"},
        "canonical_promotion": {"in_this_package": 0},
        "baseline_binding": {"F2C": {"media_id": F2C_BINDING["media_id"],
                                     "attestation_id":
                                         F2C_BINDING["attestation_id"],
                                     "reference_image_sha256":
                                         F2C_REF_SHA}},
        "admission_receipt_id": admission["receipt"]["receipt_id"],
        "forbidden_everywhere": FORBIDDEN_ROCK,
        "candidates": frozen}
    (PKG / "experiment_freeze_v2_004.json").write_text(
        json.dumps(experiment, indent=1, ensure_ascii=False),
        encoding="utf-8")
    for cand in frozen:
        print(json.dumps({"checkpoint": "V2004_P2_EXPERIMENT_FROZEN",
                          "candidate": cand["candidate_id"],
                          "identity":
                              cand["candidate_semantic_identity"][:16],
                          "chars": cand["creative_body_chars"],
                          "words": cand["creative_body_words"]}))


def _frozen_blocking():
    from film_pipeline.director_blocking import BlockingSpec
    plan = json.loads((V3 / "f2_director_plan_v2_003.json").read_text(
        encoding="utf-8"))
    return BlockingSpec.model_validate(plan["blocking_spec"])


if __name__ == "__main__":
    main()
