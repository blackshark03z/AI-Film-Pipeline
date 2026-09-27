import json
from pathlib import Path

import pytest

from film_pipeline.compiler import BLOCK_ORDER, compile_prompt
from film_pipeline.core import (
    ProviderCapabilities, ShotSpec, canonical_json, load_shot, sha256, validate_contract,
)
from film_pipeline.execution import DryRunProvider, route
from film_pipeline.store import SQLiteStore


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = sorted((ROOT / "fixtures").glob("*.json"))


def profile(name):
    payload = json.loads((ROOT / "tests" / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
    validate_contract("provider_capabilities", payload)
    return ProviderCapabilities.model_validate(payload)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_canonical_fixtures_schema_model_and_semantic_round_trip(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    validate_contract("shot_spec", raw)
    shot = load_shot(path)
    serialized = json.loads(canonical_json(shot.payload()))
    validate_contract("shot_spec", serialized)
    assert serialized == raw
    assert ShotSpec.model_validate(serialized).payload() == shot.payload()


def test_canonical_hash_ignores_key_order_and_json_whitespace():
    raw = json.loads(FIXTURES[0].read_text(encoding="utf-8"))
    reverse = json.loads(json.dumps(raw, indent=3, sort_keys=True))
    reverse = {key: reverse[key] for key in reversed(reverse)}
    assert sha256(ShotSpec.model_validate(raw)) == sha256(ShotSpec.model_validate(reverse))
    assert canonical_json(ShotSpec.model_validate(raw)) == canonical_json(ShotSpec.model_validate(reverse))


def test_canonical_hash_normalizes_explicit_schema_defaults():
    raw = json.loads((ROOT / "fixtures" / "dialogue_closeup.json").read_text(encoding="utf-8"))
    omitted = json.loads(json.dumps(raw))
    omitted["blocking"].pop("prop_interactions")
    omitted["references"].pop("other_asset_ids")
    full = ShotSpec.model_validate(raw)
    sparse = ShotSpec.model_validate(omitted)
    assert sha256(full) == sha256(sparse)
    assert compile_prompt(full, profile("provider_full")) == compile_prompt(sparse, profile("provider_full"))


def test_runtime_profile_notes_do_not_enter_compiler_identity():
    shot = load_shot(ROOT / "fixtures" / "dialogue_closeup.json")
    base = profile("provider_full")
    annotated = base.model_copy(update={"notes": ["runtime-only marker"]})
    assert compile_prompt(shot, base) == compile_prompt(shot, annotated)


def test_frozen_motion_rule_requires_purpose_even_when_schema_is_permissive():
    raw = json.loads((ROOT / "fixtures" / "dialogue_closeup.json").read_text(encoding="utf-8"))
    raw["camera"]["movement"]["purpose"] = None
    # The authorized representation alignment now rejects this in JSON Schema too.
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        validate_contract("shot_spec", raw)
    with pytest.raises(ValueError, match="movement requires a purpose"):
        ShotSpec.model_validate(raw)


def test_compiler_deterministic_blocks_and_capability_degradation():
    shot = load_shot(ROOT / "fixtures" / "dialogue_closeup.json")
    full, limited = profile("provider_full"), profile("provider_limited")
    full_plan = compile_prompt(shot, full)
    repeated = compile_prompt(shot, full)
    limited_plan = compile_prompt(shot, limited)
    assert full_plan == repeated
    assert sha256(full_plan) == sha256(repeated)
    assert list(full_plan.canonical_blocks) == list(BLOCK_ORDER)
    assert full_plan.canonical_blocks == limited_plan.canonical_blocks
    assert full_plan.unsupported_controls == []
    assert {"duration_control", "image_input", "multi_reference", "native_audio", "negative_prompt"} <= set(limited_plan.unsupported_controls)
    assert len(limited_plan.degraded_controls) == len(limited_plan.unsupported_controls)
    assert len(limited_plan.warnings) == len(limited_plan.unsupported_controls)
    assert set(limited_plan.mapped_controls["text_fallbacks"]) == set(limited_plan.unsupported_controls)
    assert "phone stays on table" in limited_plan.provider_prompt
    assert '"duration_target_s":5.5' in limited_plan.provider_prompt
    assert "CHAR_LINH_REF_V1" in limited_plan.provider_prompt


def test_routing_dry_run_and_sqlite_fresh_readback(tmp_path):
    shot = load_shot(FIXTURES[1])
    profiles = [profile("provider_limited"), profile("provider_full")]
    plans = [compile_prompt(shot, candidate) for candidate in profiles]
    decision = route(shot, plans, profiles, {candidate.provider_id: True for candidate in profiles})
    assert decision.provider_id == "provider_full"
    assert decision.fallback_provider_ids == ["provider_limited"]
    assert decision.required_capabilities
    assert decision.reasons
    plan = next(candidate for candidate in plans if candidate.provider_id == decision.provider_id)
    adapter = DryRunProvider()
    request = adapter.build_request(plan, decision)
    attempt = adapter.create_attempt(shot, plan, decision, request, started_at="2026-09-27T00:00:00+00:00")
    later_attempt = adapter.create_attempt(shot, plan, decision, request, started_at="2026-09-27T00:00:01+00:00")
    assert later_attempt.generation_attempt_id != attempt.generation_attempt_id
    assert attempt.shot_spec_hash == sha256(shot)
    assert attempt.prompt_plan_hash == sha256(plan)
    assert attempt.routing_decision_id == decision.routing_decision_id
    assert attempt.provider_id == request.provider_id
    database = tmp_path / "film.sqlite"
    store = SQLiteStore(database)
    store.initialize()
    store.save_path(shot, plan, decision, attempt)
    store.save_path(shot, plan, decision, later_attempt)
    reopened = SQLiteStore(database)
    persisted = reopened.read_path(attempt.generation_attempt_id)
    assert persisted == (shot, plan, decision, attempt)
    assert database.exists()


def test_no_available_provider_fails_closed():
    shot = load_shot(FIXTURES[0])
    limited = profile("provider_limited")
    with pytest.raises(ValueError, match="no available"):
        route(shot, [compile_prompt(shot, limited)], [limited], {limited.provider_id: False})
