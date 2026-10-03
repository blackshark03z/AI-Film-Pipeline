"""Package-011 S1 — semantic error observability offline proofs.

Every external failure keeps the SEMANTIC_API_UNAVAILABLE umbrella for
backward-compatible fail-closed handling while carrying an evidence-based
internal class + sanitized provider classification. Secrets are redacted.
"""
import urllib.error

import pytest

from film_pipeline.gemini_semantic import GeminiSemanticQCEvaluator
from film_pipeline.semantic_errors import (
    SEMANTIC_AUTH_FAILURE,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_PERMISSION_DENIED,
    SEMANTIC_RATE_OR_QUOTA_LIMIT,
    SEMANTIC_RESPONSE_MALFORMED,
    SEMANTIC_SERVICE_UNAVAILABLE,
    SEMANTIC_UNKNOWN_EXTERNAL_ERROR,
    classify_http_failure,
    classify_transport_exception,
    sanitize_detail,
)


def http_error(status: int, body: bytes, headers=None):
    exc = urllib.error.HTTPError("https://x", status, "e", headers or {},
                                 io_bytes(body))
    return exc


class io_bytes:
    def __init__(self, data):
        self._data = data

    def read(self, n=-1):
        return self._data


def make_evaluator(tmp_path, monkeypatch, payload=b"{}", status=200,
                   headers=None):
    key_file = tmp_path / "key.txt"
    key_file.write_text("test-key", encoding="utf-8")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return payload

    def urlopen(request, timeout):
        if status != 200:
            raise http_error(status, payload, headers)
        import json as _json
        r = FakeResponse()
        r.read = lambda: payload
        return r
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return GeminiSemanticQCEvaluator(key_file, model="gemini-test")


def test_quota_body_classified_rate_or_quota():
    err = classify_http_failure(
        429, b'{"error": {"status": "RESOURCE_EXHAUSTED", "message": '
             b'"quota exceeded for model"}}')
    assert err.internal_class == SEMANTIC_RATE_OR_QUOTA_LIMIT
    assert err.provider_class == "RESOURCE_EXHAUSTED"
    assert err.http_status == 429


def test_429_without_quota_metadata_still_rate_class():
    # 429 is rate-class regardless of metadata; the RAW provider status is
    # preserved separately (no forced reclassification of evidence).
    err = classify_http_failure(429, b'{"error": {"status": "UNAVAILABLE"}}')
    assert err.internal_class == SEMANTIC_RATE_OR_QUOTA_LIMIT
    assert err.provider_class == "UNAVAILABLE"


def test_401_is_auth_failure():
    err = classify_http_failure(401, b'{"error": {"status": "UNAUTHENTICATED"}}')
    assert err.internal_class == SEMANTIC_AUTH_FAILURE


def test_403_is_permission_denied():
    err = classify_http_failure(403, b'{"error": {"status": "PERMISSION_DENIED"}}')
    assert err.internal_class == SEMANTIC_PERMISSION_DENIED


def test_404_model_missing_is_model_unavailable():
    err = classify_http_failure(
        404, b'{"error": {"status": "NOT_FOUND", "message": '
             b'"models/gemini-x not found"}}')
    assert err.internal_class == SEMANTIC_MODEL_UNAVAILABLE


def test_408_and_504_are_service_unavailable():
    for status in (408, 504):
        err = classify_http_failure(status, b'{"error": {"status": "DEADLINE_EXCEEDED"}}')
        assert err.internal_class == SEMANTIC_SERVICE_UNAVAILABLE


def test_5xx_is_service_unavailable():
    err = classify_http_failure(500, b'{"error": {"status": "INTERNAL"}}')
    assert err.internal_class == SEMANTIC_SERVICE_UNAVAILABLE


def test_malformed_success_is_fail_closed(evaluator=None):
    from film_pipeline.gemini_semantic import GeminiSemanticQCEvaluator
    # the parser keeps its umbrella fail-closed class:
    import film_pipeline.gemini_semantic as g
    request = type("R", (), {"request_id": "r", "dimensions": [],
                             "frames": [], "requirements": {}})()
    evaluator = GeminiSemanticQCEvaluator.__new__(GeminiSemanticQCEvaluator)
    evaluator.model = "m"
    with pytest.raises(RuntimeError, match="SEMANTIC_RESPONSE_MALFORMED"):
        evaluator._parse({"candidates": [{"content": {"parts": [
            {"text": "not json"}]}}]}, request, "fp")


def test_sdk_exception_without_http_status():
    err = classify_transport_exception(urllib.error.URLError("timed out"))
    assert err.internal_class == SEMANTIC_SERVICE_UNAVAILABLE
    assert err.http_status is None
    generic = classify_transport_exception(urllib.error.URLError("no route"))
    assert generic.internal_class == SEMANTIC_UNKNOWN_EXTERNAL_ERROR


def test_retry_after_is_captured():
    err = classify_http_failure(429, b'{"error": {"status": "RESOURCE_EXHAUSTED"}}',
                                retry_after="30")
    assert err.retry_after == "30"
    assert "retry_after=30" in str(err)


def test_secret_redaction_in_details():
    dirty = ("Authorization: Bearer sk-abc123 key=AIzaSyA-1234567890-abcdef "
             "token=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    clean = sanitize_detail(dirty)
    assert "sk-abc123" not in clean
    assert "AIzaSyA-1234567890" not in clean
    assert "AAAAAAAAAAAAAAAA" not in clean
    assert "<redacted" in clean


def test_evaluator_surfaces_precise_class_with_umbrella(tmp_path, monkeypatch):
    evaluator = make_evaluator(
        tmp_path, monkeypatch,
        payload=b'{"error": {"status": "RESOURCE_EXHAUSTED"}}', status=429,
        headers={"Retry-After": "17"})
    request = type("R", (), {"request_id": "r", "dimensions": [],
                             "frames": [], "requirements": {}})()
    from film_pipeline.gemini_semantic import prompt_fingerprint
    with pytest.raises(RuntimeError, match="SEMANTIC_API_UNAVAILABLE") as info:
        evaluator.evaluate(request)
    assert "SEMANTIC_RATE_OR_QUOTA_LIMIT" in str(info.value)
    assert "retry_after=17" in str(info.value)
    assert "test-key" not in str(info.value)
