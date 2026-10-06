"""V2-014 — Elyum provider adapter tests (deterministic, local, no network).

Covers the package-required behaviors before any live canary mutation.
The MCP session is replaced by a MockToolSession; no credential is loaded.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from film_pipeline.providers.elyum_provider import (
    ElyumSeedanceClient,
    ElyumTransportError,
    McpToolSession,
    build_client_ref,
    download_asset,
)


class MockToolSession:
    """Scripted tool responses with request capture."""

    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, arguments: dict | None = None) -> object:
        self.calls.append((name, arguments or {}))
        handler = self.responses.get(name)
        if callable(handler):
            return handler(arguments or {})
        if handler is None:
            raise ElyumTransportError("MCP_ERROR_TEST")
        return handler


KEY = "test-key-not-a-real-secret"


def make_client(responses: dict) -> ElyumSeedanceClient:
    return ElyumSeedanceClient(key=KEY, session=MockToolSession(responses))


# 1. auth injection without secret persistence ------------------------------
def test_auth_injection_and_secret_persistence():
    client = make_client({})
    assert client.key == KEY
    assert client.session is not None
    # the key value never appears in any string rendering of the objects
    assert KEY not in repr(client) and KEY not in str(client)
    assert KEY not in repr(client.session) and KEY not in str(client.session)
    readiness = client.readiness()
    assert readiness["status"] == "READY" and readiness["browser_required"] is False
    # credential loader tolerates a missing key file and empty env
    import film_pipeline.providers.elyum_provider as mod
    saved = mod.OWNER_KEY_FILE
    try:
        mod.OWNER_KEY_FILE = Path("Z:/definitely/missing/key.txt")
        assert mod.load_credential() == ""
    finally:
        mod.OWNER_KEY_FILE = saved


# 2. request translation ------------------------------------------------------
def test_request_translation_t2v():
    seen = {}

    def make(args):
        seen.update(args)
        return {"jobId": "job-1"}

    client = make_client({"elyum_make_video": make})
    job, result = client.make_video(
        client_ref="ref-1", model="seedance-2-fast-i2v",
        prompt="wide cinematic shot of an empty mountain pass",
        duration=5, mode="t2v", aspect_ratio="16:9", resolution="480p")
    assert job == "job-1"
    assert seen["clientRef"] == "ref-1" and seen["mode"] == "t2v"
    assert seen["duration"] == 5 and seen["resolution"] == "480p"
    assert seen["aspectRatio"] == "16:9" and "kind" not in seen
    assert "imageUrl" not in seen and "imageUrls" not in seen


def test_request_translation_i2v_requires_reference():
    client = make_client({})
    with pytest.raises(ElyumTransportError) as e:
        client.make_video(client_ref="r", model="m", prompt="p", mode="i2v")
    assert e.value.failure_class == "REFERENCE_REQUIRED"


# 3. clientRef stability --------------------------------------------------------
def test_client_ref_stability():
    identity = {"shot": "CANARY", "model": "m", "duration": 5}
    a = build_client_ref("attempt-A", identity)
    b = build_client_ref("attempt-A", identity)
    c = build_client_ref("attempt-B", identity)
    assert a == b and a != c
    assert a.startswith("aifilm-v2014-") and len(a) <= 120


# 4. job identity (nested extraction) -----------------------------------------
def test_job_identity_nested_extraction():
    def make(args):
        return {"data": {"job": {"JobId": "job-nested-9"},
                         "genId": "gen-77"}}

    client = make_client({"elyum_make_video": make})
    job, result = client.make_video(client_ref="r", model="m", prompt="p",
                                    mode="t2v")
    assert job == "job-nested-9"
    assert client.gen_id(result) == "gen-77"


def test_missing_job_id_fails_closed_for_reconcile():
    client = make_client({"elyum_make_video": {"ok": True}})
    with pytest.raises(ElyumTransportError) as e:
        client.make_video(client_ref="r", model="m", prompt="p", mode="t2v")
    assert e.value.failure_class == "PROVIDER_JOB_ID_MISSING"
    assert e.value.dispatch_state == "RECONCILE_BY_CLIENT_REF"


# 5. poll transitions -----------------------------------------------------------
def test_poll_transitions():
    states = {"elyum_job_status": [{"status": "running"}, {"status": "completed",
                                                    "genId": "g1"}]}
    client = make_client(dict.fromkeys([], None) or {})
    client.session.responses = {}
    client.session.responses["elyum_job_status"] = lambda args: states[
        "elyum_job_status"].pop(0)
    s1 = client.job_status("job-1")
    s2 = client.job_status("job-1")
    assert client.execution_state(s1) == "running"
    assert client.execution_state(s2) == "completed"
    assert client.gen_id(s2) == "g1"


# 6. output extraction -----------------------------------------------------------
def test_output_extraction_previews_and_downloads():
    # pre-keep observation: the locked preview arrives as a generic `url`
    pre_keep = {"previews": [{"thumb": "https://media.elyum.ai/p.mp4"}],
                "url": "https://media.elyum.ai/preview.mp4"}
    assert ElyumSeedanceClient.preview_urls(pre_keep) == [
        "https://media.elyum.ai/p.mp4", "https://media.elyum.ai/preview.mp4"]
    # post-keep: downloadable originals, duplicates absorbed (8)
    post_keep = {"files": [{"url": "https://media.elyum.ai/final.mp4"},
                           {"url": "https://media.elyum.ai/final.mp4"}],
                 "unlockCredits": 20}
    assert ElyumSeedanceClient.downloadable_urls(post_keep) == ["https://media.elyum.ai/final.mp4"]
    assert ElyumSeedanceClient.unlock_credits(post_keep) == 20


# 7. download binding -----------------------------------------------------------
def test_download_binding(tmp_path, monkeypatch):
    payload = b"\x00\x01fake mp4 bytes"

    class FakeResponseWithBody:
        def __init__(self, body):
            self._body = body

        def read(self, amount=-1):
            out = self._body
            self._body = b""
            return out

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import film_pipeline.providers.elyum_provider as mod
    calls = {}

    def fake_urlopen(request, timeout):
        calls["url"] = request.full_url
        return FakeResponseWithBody(payload)

    monkeypatch.setattr(mod, "urlopen", fake_urlopen)
    dest = tmp_path / "canary.mp4"
    info = download_asset("https://media.elyum.ai/final.mp4", dest)
    assert info["sha256"] == hashlib_sha(payload)
    assert Path(info["path"]).read_bytes() == payload
    assert calls["url"].startswith("https://media.elyum.ai/")
    # unsafe scheme refused
    with pytest.raises(ElyumTransportError) as e:
        download_asset("http://media.elyum.ai/final.mp4", tmp_path / "x.mp4")
    assert e.value.failure_class == "DOWNLOAD_URL_UNSAFE"


def hashlib_sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


# 9. timeout -> PROVIDER_TRANSIENT ---------------------------------------------
def test_timeout_maps_to_transient(monkeypatch):
    import film_pipeline.providers.elyum_provider as mod

    class Boom:
        def __enter__(self):
            raise TimeoutError("timed out")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mod, "urlopen", lambda request, timeout: Boom())
    session = McpToolSession("https://elyum.ai/mcp", KEY)
    with pytest.raises(ElyumTransportError) as e:
        session.call_tool("elyum_account", {})
    assert e.value.failure_class == "PROVIDER_TRANSIENT"


# 10. explicit provider failure classes ----------------------------------------
def test_provider_failure_classes(monkeypatch):
    import film_pipeline.providers.elyum_provider as mod

    class HttpFail:
        def __init__(self, code):
            self.code = code

        def __enter__(self):
            raise mod.HTTPError("https://elyum.ai/mcp", self.code, "x", {}, None)

        def __exit__(self, *a):
            return False

    expectations = {401: "CREDENTIAL_OR_ACCESS_DENIED", 403: "CREDENTIAL_OR_ACCESS_DENIED",
                    429: "RATE_LIMITED", 422: "CAPABILITY_OR_REQUEST_INVALID",
                    500: "PROVIDER_TRANSIENT", 418: "PROVIDER_REQUEST_FAILED"}
    for code, expected in expectations.items():
        monkeypatch.setattr(mod, "urlopen", lambda request, timeout, c=code: HttpFail(c))
        session = McpToolSession("https://elyum.ai/mcp", KEY)
        with pytest.raises(ElyumTransportError) as e:
            session.call_tool("elyum_account", {})
        assert e.value.failure_class == expected


# 11. malformed response ---------------------------------------------------------
def test_malformed_response(monkeypatch):
    import film_pipeline.providers.elyum_provider as mod

    with pytest.raises(ElyumTransportError) as e:
        mod._decode_rpc(b"not json", "application/json")
    assert e.value.failure_class == "MCP_RESPONSE_INVALID"
    # missing result
    session = McpToolSession("https://elyum.ai/mcp", KEY)
    monkeypatch.setattr(session, "_post",
                        lambda message: {"jsonrpc": "2.0", "id": 1})
    with pytest.raises(ElyumTransportError) as e:
        session.call_tool("elyum_account", {})
    assert e.value.failure_class == "MCP_RESULT_INVALID"


# 12. missing jobId covered in test_missing_job_id_fails_closed_for_reconcile ----
# 13. recovery after process restart (reconcile by clientRef) -------------------
def test_recovery_after_restart_reconciles_by_client_ref():
    # a fresh process rebuilds the SAME clientRef from the same attempt identity
    identity = {"shot": "CANARY", "model": "seedance-2-fast-i2v",
                "duration": 5, "resolution": "480p", "mode": "t2v"}
    ref_before = build_client_ref("attempt-xyz", identity)
    # ...process restarts...
    ref_after = build_client_ref("attempt-xyz", identity)
    assert ref_before == ref_after
    # transient dispatch failure demands reconcile-by-clientRef, never resubmit
    client = make_client({})

    def transient(args):
        raise ElyumTransportError("PROVIDER_TRANSIENT")

    client.session.responses["elyum_make_video"] = transient
    with pytest.raises(ElyumTransportError) as e:
        client.make_video(client_ref=ref_before, model="seedance-2-fast-i2v",
                          prompt="p", duration=5, mode="t2v")
    assert e.value.failure_class == "IDEMPOTENT_REPLAY_REQUIRED"
    assert e.value.dispatch_state == "RECONCILE_BY_CLIENT_REF"


# 14. secret redaction in failure paths ------------------------------------------
def test_secret_redaction(monkeypatch):
    import film_pipeline.providers.elyum_provider as mod

    class HttpFail:
        def __enter__(self):
            raise mod.HTTPError("https://elyum.ai/mcp", 401, "denied", {}, None)

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mod, "urlopen", lambda request, timeout: HttpFail())
    session = McpToolSession("https://elyum.ai/mcp", KEY)
    with pytest.raises(ElyumTransportError) as e:
        session.call_tool("elyum_account", {})
    # the rendered failure never carries the credential or auth headers
    rendered = f"{e.value.failure_class} {e.value.detail} {str(e.value)}"
    assert KEY not in rendered
    assert "Authorization" not in rendered and "Bearer" not in rendered


# capability-quote path (read-only estimate) ------------------------------------
def test_estimate_readonly_translation():
    seen = {}

    def estimate(args):
        seen.update(args)
        return {"credits": 5}

    client = make_client({"elyum_estimate": estimate})
    credits = client.estimate_video(model="seedance-2-fast-i2v", duration=5,
                                    mode="t2v", resolution="480p")
    assert credits == 5
    assert seen == {"kind": "video", "mode": "t2v",
                    "model": "seedance-2-fast-i2v", "duration": 5,
                    "resolution": "480p"}


def test_estimate_rejects_out_of_schema():
    client = make_client({})
    with pytest.raises(ElyumTransportError) as e:
        client.estimate_video(model="m", duration=5, mode="t2v",
                              resolution="4k")
    assert e.value.failure_class == "RESOLUTION_UNSUPPORTED"
    with pytest.raises(ElyumTransportError) as e:
        client.estimate_video(model="m", duration=45, mode="t2v")
    assert e.value.failure_class == "DURATION_UNSUPPORTED"
