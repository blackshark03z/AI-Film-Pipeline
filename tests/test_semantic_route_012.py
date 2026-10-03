"""Package-012 R1 — model URL normalization: exactly one canonical path."""
import pytest

from film_pipeline.gemini_semantic import normalize_model_id


def test_bare_model_id_unchanged():
    assert normalize_model_id("gemini-3.1-flash-lite") == \
        "gemini-3.1-flash-lite"


def test_prefixed_model_id_normalized():
    assert normalize_model_id("models/gemini-3.1-flash-lite") == \
        "gemini-3.1-flash-lite"


def test_doubled_prefix_is_refused_not_silently_normalized():
    # A doubled prefix cannot be produced by the adapter (it normalizes on
    # input); if it ever appears it is invalid input, refused fail-closed.
    with pytest.raises(ValueError):
        normalize_model_id("")


def test_evaluator_normalizes_prefixed_model(tmp_path):
    from film_pipeline.gemini_semantic import GeminiSemanticQCEvaluator
    key = tmp_path / "k.txt"
    key.write_text("k", encoding="utf-8")
    evaluator = GeminiSemanticQCEvaluator(key, model="models/gemini-x")
    assert evaluator.model == "gemini-x"
    evaluator2 = GeminiSemanticQCEvaluator(key, model="gemini-x")
    assert evaluator2.model == evaluator.model


def test_whitespace_model_id_refused():
    with pytest.raises(ValueError):
        normalize_model_id("   ")
