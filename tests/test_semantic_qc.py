"""Offline schema/contract tests for the semantic QC interface (P3).

The live environment has no qualified VLM key, so live semantic QC stays
SEMANTIC_QC_UNQUALIFIED; these tests prove the replaceable interface is
deterministic, structurally strict, advisory-only, and independently
testable — the contract a future qualified evaluator must satisfy.
"""
import pytest

from film_pipeline.semantic_qc import (
    SEMANTIC_QC_STATUS,
    FrozenFixtureEvaluator,
    SemanticQCRequest,
    SemanticQCObservation,
    validate_semantic_batch,
)

FRAMES = [{"path": "f1.jpg", "sha256": "a" * 64, "label": "first"},
          {"path": "f2.jpg", "sha256": "b" * 64, "label": "last"}]
REQ = {"character_identity": "same white-robed swordsman",
       "environment_world": "summit above cloud-sea at dawn"}
PROVENANCE = {"shot_id": "SHOT_X", "fixture_label": "positive",
              "asset_sha256": "c" * 64}


def make_request(dimensions=None, provenance=None):
    return SemanticQCRequest(
        request_id="semreq_test", dimensions=dimensions or list(REQ),
        frames=FRAMES, requirements=REQ,
        provenance=provenance if provenance is not None else dict(PROVENANCE))


def test_request_validation_is_strict():
    make_request()  # valid
    with pytest.raises(ValueError, match="dimensions unqualified"):
        make_request(dimensions=["vibes"])
    with pytest.raises(ValueError, match="missing frozen requirement"):
        make_request(dimensions=["character_identity", "wardrobe_props"])
    unhashed = [dict(FRAMES[0])]
    unhashed[0]["sha256"] = "nothex"
    with pytest.raises(ValueError):
        SemanticQCRequest(request_id="x", dimensions=["character_identity"],
                          frames=unhashed, requirements=REQ, provenance={})


def test_frozen_fixture_evaluator_positive_negative_ambiguous():
    fixtures = {
        ("character_identity", "positive"): ("PASS", 0.9, ["same robes and sword"]),
        ("character_identity", "negative"): ("FAIL", 0.85, ["different wardrobe"]),
        ("environment_world", "ambiguous"): ("INCONCLUSIVE", 0.3, ["fog obscures"]),
    }
    evaluator = FrozenFixtureEvaluator(fixtures)
    for label, expected in (("positive", "PASS"), ("negative", "FAIL"),
                            ("ambiguous", "INCONCLUSIVE")):
        request = make_request(provenance={**PROVENANCE, "fixture_label": label})
        observations = evaluator.evaluate(request)
        validate_semantic_batch(request, observations)
        assert observations[0].verdict == expected


def test_unfixtures_entries_are_inconclusive():
    evaluator = FrozenFixtureEvaluator({})
    request = make_request()
    observations = evaluator.evaluate(request)
    assert all(o.verdict == "INCONCLUSIVE" for o in observations)
    validate_semantic_batch(request, observations)


def test_evaluator_determinism():
    fixtures = {("character_identity", "positive"): ("PASS", 0.9, ["same"])}
    evaluator = FrozenFixtureEvaluator(fixtures)
    request = make_request(dimensions=["character_identity"])
    first = evaluator.evaluate(request)
    second = evaluator.evaluate(request)
    assert [o.model_dump(mode="json") for o in first] == \
        [o.model_dump(mode="json") for o in second]


def test_batch_contract_mismatches_fail():
    evaluator = FrozenFixtureEvaluator({})
    request = make_request(dimensions=["character_identity"])
    observations = evaluator.evaluate(request)
    with pytest.raises(ValueError, match="cardinality"):
        validate_semantic_batch(request, [])
    other = observations[0].model_copy(update={"dimension": "environment_world"})
    with pytest.raises(ValueError, match="dimensions mismatch"):
        validate_semantic_batch(request, [other])
    wrong_id = observations[0].model_copy(update={"request_id": "other"})
    with pytest.raises(ValueError, match="request_id"):
        validate_semantic_batch(request, [wrong_id])


def test_semantic_qc_status_is_unqualified():
    """Honest freeze: no qualified VLM key exists in this environment."""
    assert SEMANTIC_QC_STATUS == "SEMANTIC_QC_UNQUALIFIED"


def test_observation_never_carries_authority_fields():
    observation = SemanticQCObservation(
        request_id="x", dimension="character_identity", verdict="FAIL",
        confidence=0.5, observations=["note"], evidence_refs=[],
        evaluator_type="t", evaluator_version="t-v1",
        prompt_fingerprint="d" * 64)
    payload = observation.model_dump(mode="json")
    forbidden = {"provider_job_id", "output_id", "mutation_authority",
                 "asset_id", "selected"}
    assert not forbidden & set(payload)
