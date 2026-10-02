"""Offline proof for the seedance_dola cookie transport.

Every network behavior here is a frozen synthetic double. No live provider
access, no credentials, no cookies. The observed wire shapes come from the
Owner's live-qualified Story Auto evidence (2026-09-23); the transport is
proved fail-closed on identity, ambiguity, host and hygiene invariants.
"""
import json
import subprocess
from pathlib import Path
from urllib.request import Request

import pytest

from film_pipeline.providers.dola_provider import (
    DolaCookieTransport,
    DolaTransportError,
    probe_session,
)

COOKIE = "sessionid=test-session-value; msTokEND" .replace("msTokEND", "msToken=test-ms; s_v_web_id=test-fp")


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200, url: str = "https://www.dola.com/x",
                 content_type: str = "application/json"):
        self._payload = payload
        self.status = status
        self.url = url
        self.headers = {"Content-Type": content_type}

    def read(self, amount: int = -1):
        data, self._payload = self._payload, b""
        return data

    def read1(self, amount: int = -1):
        return self.read(amount)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def sse_body(ack_conversation: str | None) -> bytes:
    if ack_conversation is None:
        return b"event: ping\ndata: {}\n\n"
    event = {"ack_client_meta": {"conversation_id": ack_conversation}}
    return ("event: SSE_ACK\ndata: " + json.dumps(event) + "\n\n").encode()


def make_opener(responses):
    """Sequential fake opener; each call records the request for inspection."""
    calls = []

    def opener(request: Request, timeout: float):
        calls.append(request)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    return opener, calls


def receipt_sink(store: list):
    return lambda conversation_id: store.append(conversation_id)


def test_submit_persists_receipt_before_return_and_binds_client_request_id():
    events: list[str] = []
    opener, calls = make_opener([FakeResponse(sse_body("conv-123"), content_type="text/event-stream")])
    transport = DolaCookieTransport(COOKIE, opener=opener)
    result = transport.submit("a calm river", "16:9", 5, receipt_sink(events),
                              client_request_id="job_" + "a" * 64)
    assert result == "conv-123" and events == ["conv-123"]
    body = json.loads(calls[0].data.decode())
    assert body["messages"][0]["local_message_id"] == "job_" + "a" * 64
    assert body["option"]["unique_key"] == "job_" + "a" * 64
    params = calls[0].full_url.split("?")[1]
    assert "msToken=test-ms" in params and "fp=test-fp" in params
    assert transport.call_counts["submit"] == 1


def test_submit_failures_are_classified_and_never_leak_secrets():
    opener, _ = make_opener([FakeResponse(b"denied", status=401)])
    transport = DolaCookieTransport(COOKIE, opener=opener)
    with pytest.raises(DolaTransportError) as exc401:
        transport.submit("p", "16:9", 5, receipt_sink([]), client_request_id="job_x")
    assert exc401.value.failure_class == "CREDENTIAL_OR_ACCESS_DENIED"
    assert exc401.value.dispatch_state == "NOT_DISPATCHED"

    opener2, _ = make_opener([FakeResponse(b"boom", status=500)])
    transport2 = DolaCookieTransport(COOKIE, opener=opener2)
    with pytest.raises(DolaTransportError) as exc500:
        transport2.submit("p", "16:9", 5, receipt_sink([]), client_request_id="job_x")
    assert exc500.value.failure_class == "AMBIGUOUS" and exc500.value.dispatch_state == "AMBIGUOUS"

    opener3, _ = make_opener([FakeResponse(b"event: ping\ndata: {}\n\n", content_type="text/event-stream")])
    transport3 = DolaCookieTransport(COOKIE, opener=opener3)
    with pytest.raises(DolaTransportError) as exc_missing:
        transport3.submit("p", "16:9", 5, receipt_sink([]), client_request_id="job_x")
    assert exc_missing.value.failure_class == "RECEIPT_MISSING"
    assert "test-session-value" not in str(exc_missing.value)


def test_submit_rejects_unqualified_capability_or_identity_before_network():
    opener, calls = make_opener([])
    transport = DolaCookieTransport(COOKIE, opener=opener)
    with pytest.raises(DolaTransportError):
        transport.submit("p", "21:9", 5, receipt_sink([]), client_request_id="job_x")
    with pytest.raises(DolaTransportError):
        transport.submit("p", "16:9", 8, receipt_sink([]), client_request_id="job_x")
    with pytest.raises(DolaTransportError):
        transport.submit("p", "16:9", 5, receipt_sink([]), client_request_id="bad id!")
    assert calls == []  # nothing was sent


def completed_payload(creation_id: str = "create-1", *, local_message_id: str | None = None,
                      reply_to: str | None = None):
    url = "https://v.byteimg.com/x.mp4?sig=1"
    reply = _creation_message(creation(creation_id, url), local_message_id="reply-1",
                              message_id="msg-2", reply_to_message_id="msg-1",
                              parent_message_id="msg-1")
    if local_message_id is None:
        return _chain_payload(reply)
    inner = _creation_message(creation(creation_id, url), local_message_id=local_message_id,
                              message_id="msg-1")
    return _chain_payload(inner, reply)


def test_poll_owned_result_requires_observed_identity_echo():
    opener, _ = make_opener([FakeResponse(completed_payload(local_message_id="job_" + "b" * 64))])
    transport = DolaCookieTransport(COOKIE, opener=opener)
    result = transport.poll("conv-123", client_request_id="job_" + "b" * 64)
    assert result["status"] == "COMPLETED"
    assert result["creation_id"] == "create-1"
    assert result["video_url"].startswith("https://v.byteimg.com/")

    opener2, _ = make_opener([FakeResponse(completed_payload(local_message_id="someone-else"))])
    transport2 = DolaCookieTransport(COOKIE, opener=opener2)
    with pytest.raises(DolaTransportError) as unverified:
        transport2.poll("conv-123", client_request_id="job_" + "b" * 64)
    assert unverified.value.failure_class == "DOLA_RESULT_IDENTITY_UNVERIFIED"

    # Reply linkage alone is sufficient when the echo message id matches the input.
    opener3, _ = make_opener([FakeResponse(completed_payload(local_message_id="job_" + "b" * 64))])
    transport3 = DolaCookieTransport(COOKIE, opener=opener3)
    assert transport3.poll("conv-123", client_request_id="job_" + "b" * 64)["status"] == "COMPLETED"


def _chain_payload(*messages) -> bytes:
    return json.dumps({"downlink_body": {"pull_singe_chain_downlink_body": {"messages": list(messages)}}}).encode()


def _creation_message(*creations, **message_fields):
    blocks = json.dumps([{"block_type": 2074, "content": {
        "creation_block": {"creations": creations}}}])
    return {"local_message_id": message_fields.get("local_message_id"),
            "message_id": message_fields.get("message_id"),
            "reply_to_message_id": message_fields.get("reply_to_message_id"),
            "parent_message_id": message_fields.get("parent_message_id"),
            "conversation_id": message_fields.get("conversation_id", "conv-123"),
            "content": blocks}


def creation(creation_id: str, url: str) -> dict:
    return {"type": 2, "creation_id": creation_id, "video": {"download_url": url}}


def test_poll_ambiguity_pending_and_failure_states_fail_closed():
    double_creation = _chain_payload(_creation_message(
        creation("c1", "https://v.byteimg.com/1.mp4"),
        creation("c2", "https://v.byteimg.com/2.mp4"),
        local_message_id="job_c", message_id="m1"))
    opener, _ = make_opener([FakeResponse(double_creation)])
    transport = DolaCookieTransport(COOKIE, opener=opener)
    with pytest.raises(DolaTransportError) as ambiguous:
        transport.poll("conv-123", client_request_id="job_c")
    assert ambiguous.value.failure_class == "PROVIDER_RESULT_AMBIGUOUS"

    opener2, _ = make_opener([FakeResponse(_chain_payload(
        {"text": "insufficient credits 余额不足"}))])
    transport2 = DolaCookieTransport(COOKIE, opener=opener2)
    assert transport2.poll("conv-123")["status"] == "FAILED"

    opener3, _ = make_opener([FakeResponse(_chain_payload(
        {"text": "generating..."}))])
    transport3 = DolaCookieTransport(COOKIE, opener=opener3)
    assert transport3.poll("conv-123")["status"] == "PENDING"

    opener4, _ = make_opener([FakeResponse(b"login required", status=401)])
    transport4 = DolaCookieTransport(COOKIE, opener=opener4)
    with pytest.raises(DolaTransportError) as dead:
        transport4.poll("conv-123")
    assert dead.value.dispatch_state == "DISPATCH_CONFIRMED"  # never re-dispatch after receipt


def mp4_fixture(path: Path, seconds: float = 5.0) -> None:
    completed = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=320x240:d={seconds}", "-an",
         "-pix_fmt", "yuv420p", str(path)], capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError("ffmpeg fixture failed")


def test_download_validates_host_and_media_then_promotes_atomically(tmp_path):
    fixture = tmp_path / "fixture.mp4"
    mp4_fixture(fixture)
    opener, _ = make_opener([FakeResponse(fixture.read_bytes(),
                                          url="https://v.byteimg.com/x.mp4?sig=1",
                                          content_type="video/mp4")])
    transport = DolaCookieTransport(COOKIE, opener=opener)
    destination = tmp_path / "assets" / "out.mp4"
    metadata = transport.download("https://v.byteimg.com/x.mp4?sig=1", destination)
    assert destination.exists() and not destination.with_suffix(".mp4.candidate").exists()
    assert abs(metadata["duration_s"] - 5.0) < 0.5

    opener2, _ = make_opener([FakeResponse(b"whatever", url="https://evil.example/x.mp4",
                                           content_type="video/mp4")])
    transport2 = DolaCookieTransport(COOKIE, opener=opener2)
    with pytest.raises(DolaTransportError) as host:
        transport2.download("https://evil.example/x.mp4", tmp_path / "bad.mp4")
    assert host.value.failure_class == "DOWNLOAD_HOST_REJECTED"
    assert not (tmp_path / "bad.mp4").exists()

    transport3 = DolaCookieTransport(COOKIE, opener=make_opener([])[0])
    with pytest.raises(DolaTransportError):
        transport3.download("https://v.byteimg.com/x.mp4", destination)  # existing destination


def test_probe_session_liveness_is_read_only():
    opener, _ = make_opener([FakeResponse(b"unauthorized", status=401)])
    assert probe_session(COOKIE, opener=opener) is False
    opener2, _ = make_opener([FakeResponse(json.dumps({"downlink_body": {}}).encode())])
    assert probe_session(COOKIE, opener=opener2) is True


def test_transport_hygiene_cookie_never_leaks():
    transport = DolaCookieTransport(COOKIE, opener=make_opener([])[0])
    assert "test-session-value" not in repr(transport)
    assert "test-session-value" not in str(DolaTransportError("ANY"))
    with pytest.raises(DolaTransportError):
        DolaCookieTransport("msToken=orphan")
    with pytest.raises(DolaTransportError):
        DolaCookieTransport("sessionid=bad\nnewline")
