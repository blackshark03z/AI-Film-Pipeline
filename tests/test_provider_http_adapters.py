"""HTTP provider adapters (Vilao OpenAI-videos shape, MiniMax): fake transport + one local mock server each."""
from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from film_pipeline.providers.capability import get_capability
from film_pipeline.providers.http_adapters import (
    HttpResponse, MiniMaxAdapter, OpenAIVideosAdapter, ProviderNotReady, TransportError)
from film_pipeline.providers.request import FrameRef, GenerationRequest, ReferenceRef

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
VIDEO = b"\x00\x00\x00\x18ftypmp42" + b"video-bytes" * 10
SHA = "a" * 64


def jr(status, payload) -> HttpResponse:
    return HttpResponse(status, json.dumps(payload).encode(), {})


class FakeTransport:
    """Records calls; ``script(method, url, call_no)`` returns an HttpResponse or an exception to raise."""

    def __init__(self, script):
        self.script, self.calls = script, []

    def request(self, method, url, headers, body=None, timeout=60.0):
        self.calls.append({"method": method, "url": url, "headers": dict(headers),
                           "body": json.loads(body) if body else None})
        out = self.script(method, url, len(self.calls))
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture
def make_request(tmp_path):
    first, last, ref = (tmp_path / n for n in ("first.png", "last.png", "ref.png"))
    for p in (first, last, ref):
        p.write_bytes(PNG)

    def build(*, frames=True, last_frame=False, refs=False, output=None):
        return GenerationRequest(
            film_id="f", generation_id="g", take_id="t", prompt="a calm sea", prompt_sha256=SHA, duration_s=8,
            aspect="16:9", tier="TEST", first_frame=FrameRef(path=str(first)) if frames else None,
            last_frame=FrameRef(path=str(last)) if last_frame else None,
            references=[ReferenceRef(role="character", path=str(ref))] if refs else [],
            audio_mode="SILENT", output=output or str(tmp_path / "t.mp4"))
    return build


class Mock:
    """Local mock server: ``routes(method, path, hit_no) -> (status, content_type, bytes)``; records every request."""

    def __init__(self, routes):
        self.seen, self.counts = [], {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self, method):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                key = (method, self.path)
                outer.counts[key] = outer.counts.get(key, 0) + 1
                outer.seen.append({"method": method, "path": self.path, "auth": self.headers.get("Authorization"),
                                   "body": json.loads(body) if body else None})
                status, ctype, data = routes(method, self.path, outer.counts[key])
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._serve("GET")

            def do_POST(self):
                self._serve("POST")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def root(self):
        return f"http://127.0.0.1:{self.port}"


@pytest.fixture
def start_mock(request):
    servers = []

    def stop():
        for s in servers:
            s.server.shutdown()
            s.server.server_close()

    request.addfinalizer(stop)

    def start(routes):
        servers.append(Mock(routes))
        return servers[-1]
    return start


def js(payload):
    return 200, "application/json", json.dumps(payload).encode()


def vilao(transport=None, base_url="https://api.vilao.ai/p/omh3", env=None, **kw):
    kw.setdefault("sleep", lambda s: None)
    return OpenAIVideosAdapter(get_capability("vilao", "h3-480p"), transport=transport, base_url=base_url,
                               env={"VILAO_API_KEY": "test-key"} if env is None else env, **kw)


def minimax(transport=None, base_url="https://api.minimax.io", env=None, **kw):
    kw.setdefault("sleep", lambda s: None)
    return MiniMaxAdapter(get_capability("minimax", "h3-lite"), transport=transport, base_url=base_url,
                          env={"MINIMAX_API_KEY": "mm-key"} if env is None else env, **kw)


def vilao_ok_script(method, url, n):
    if method == "POST":
        return jr(200, {"id": "vid_1"})
    return HttpResponse(200, VIDEO, {}) if "/content" in url else jr(200, {"status": "completed"})


# ---- Vilao ---------------------------------------------------------------------------------------------------------
def test_vilao_happy_path_against_mock_server(start_mock, make_request, tmp_path):
    def routes(method, path, n):
        if method == "POST" and path == "/p/omh3/v1/videos":
            return js({"id": "vid_1", "status": "queued"})
        if path == "/p/omh3/v1/videos/vid_1?model=h3-480p":
            return js({"status": "queued"} if n == 1 else {"status": "completed"})
        if path == "/p/omh3/v1/videos/vid_1/content?model=h3-480p":
            return 200, "video/mp4", VIDEO
        return 404, "application/json", b"{}"

    mock = start_mock(routes)
    submitted = []
    out = vilao(base_url=f"{mock.root}/p/omh3").run(make_request(last_frame=True), on_submitted=submitted.append)
    assert (out.result, out.provider_job_id) == ("PASSED", "vid_1")
    assert submitted == ["vid_1"]
    assert (tmp_path / "t.mp4").read_bytes() == VIDEO
    assert out.sha256 == hashlib.sha256(VIDEO).hexdigest()
    assert len(mock.seen) == 4 and all(s["auth"] == "Bearer test-key" for s in mock.seen)
    body = mock.seen[0]["body"]
    assert body["model"] == "h3-480p" and body["prompt"] == "a calm sea"
    assert body["seconds"] == "8" and body["size"] == "854x480"
    assert body["input_reference"].startswith("data:image/png;base64,")
    assert body["last_frame"].startswith("data:image/png;base64,")


def test_vilao_http_402_is_not_submitted(make_request):
    t = FakeTransport(lambda m, u, n: jr(402, {"error": {"message": "balance"}}))
    out = vilao(t).run(make_request())
    assert (out.result, out.raw_result, out.provider_job_id) == ("NOT_SUBMITTED", "http_402", "")
    assert get_capability("vilao", "h3-480p").charged("NOT_SUBMITTED") is False


@pytest.mark.parametrize("error, expected",
                         [({"code": "moderation_blocked"}, "REJECTED_POLICY"), (None, "PROVIDER_FAILED")])
def test_vilao_failed_job(make_request, error, expected):
    failed = {"status": "failed", **({"error": error} if error else {})}
    t = FakeTransport(lambda m, u, n: jr(200, {"id": "vid_1"}) if m == "POST" else jr(200, failed))
    out = vilao(t).run(make_request())
    assert (out.result, out.provider_job_id) == (expected, "vid_1")


def test_vilao_poll_timeout_is_ambiguous_and_keeps_job_id(make_request):
    ticks = iter(range(0, 10_000, 100))
    t = FakeTransport(lambda m, u, n: jr(200, {"id": "vid_1"}) if m == "POST" else jr(200, {"status": "in_progress"}))
    out = vilao(t, clock=lambda: next(ticks), timeout_s=250).run(make_request())
    assert (out.result, out.raw_result, out.provider_job_id) == ("AMBIGUOUS", "timeout", "vid_1")


@pytest.mark.parametrize("refused, expected", [(True, "NOT_SUBMITTED"), (False, "AMBIGUOUS")])
def test_vilao_transport_error_on_create(make_request, refused, expected):
    t = FakeTransport(lambda m, u, n: TransportError("boom", refused=refused))
    out = vilao(t).run(make_request())
    assert out.result == expected and out.provider_job_id == ""


def test_vilao_5xx_during_poll_is_transient(make_request):
    def script(m, u, n):
        if m == "POST":
            return jr(200, {"id": "vid_1"})
        if "/content" in u:
            return HttpResponse(200, VIDEO, {})
        return HttpResponse(503, b"", {}) if n <= 3 else jr(200, {"status": "completed"})

    t = FakeTransport(script)
    assert vilao(t).run(make_request()).result == "PASSED"
    assert sum(1 for c in t.calls if c["method"] == "GET" and "/content" not in c["url"]) == 3


def test_vilao_missing_key(make_request):
    assert vilao(env={}).health().state == "AUTH_REQUIRED"
    assert vilao().health().state == "READY"
    t = FakeTransport(lambda m, u, n: jr(200, {"id": "x"}))
    with pytest.raises(ProviderNotReady):
        vilao(t, env={}).run(make_request())
    assert t.calls == []


def test_vilao_never_overwrites_existing_output(make_request, tmp_path):
    out_path = tmp_path / "t.mp4"
    out_path.write_bytes(b"precious")
    transport = FakeTransport(vilao_ok_script)
    adapter = vilao(transport)
    with pytest.raises(FileExistsError):
        adapter.fetch_sync("vid_1", out_path)
    transport.calls.clear()
    outcome = adapter.run(make_request(output=str(out_path)))
    # refused before submitting: nothing is paid for a clip that could never be written
    assert outcome.result == "NOT_SUBMITTED" and outcome.raw_result == "output_exists" and transport.calls == []
    assert out_path.read_bytes() == b"precious"


def test_vilao_key_never_in_outcome(make_request):
    ok = vilao(FakeTransport(vilao_ok_script)).run(make_request())
    bad = vilao(FakeTransport(lambda m, u, n: TransportError("timed out"))).run(make_request())
    assert ok.result == "PASSED"
    for outcome in (ok, bad):
        assert "test-key" not in outcome.model_dump_json()


# ---- MiniMax -------------------------------------------------------------------------------------------------------
def test_minimax_happy_path_against_mock_server(start_mock, make_request, tmp_path):
    holder = {}

    def routes(method, path, n):
        if method == "POST" and path == "/v2/video_generation":
            return js({"task_id": "t1", "base_resp": {"status_code": 0, "status_msg": "success"}})
        if path == "/v2/query/video_generation/t1":
            if n == 1:
                return js({"status": "queued"})
            if n == 2:
                return js({"status": "running"})
            return js({"status": "succeeded", "content": {"url": f"{holder['root']}/files/t1.mp4"}})
        if path == "/files/t1.mp4":
            return 200, "video/mp4", VIDEO
        return 404, "application/json", b"{}"

    mock = start_mock(routes)
    holder["root"] = mock.root
    out = minimax(base_url=mock.root).run(make_request(last_frame=True))
    assert out.result == "PASSED" and out.provider_job_id == "t1"
    assert (tmp_path / "t.mp4").read_bytes() == VIDEO
    assert out.sha256 == hashlib.sha256(VIDEO).hexdigest()
    assert mock.seen[0]["auth"] == "Bearer mm-key"
    body = mock.seen[0]["body"]
    assert body["model"] == "MiniMax-H3-Lite" and body["duration"] == 8 and isinstance(body["duration"], int)
    assert body["resolution"] == "480P" and body["ratio"] == "16:9"
    assert [(c["role"], c["image_url"][:22]) for c in body["content"]] == [
        ("first_frame", "data:image/png;base64,"), ("last_frame", "data:image/png;base64,")]


def test_minimax_references_only(make_request):
    t = FakeTransport(lambda m, u, n: jr(200, {"task_id": "t1"}))
    minimax(t).submit_sync(make_request(frames=False, refs=True))
    content = t.calls[0]["body"]["content"]
    assert [c["role"] for c in content] == ["reference_image"]
    assert content[0]["image_url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("status", [422, 200])
def test_minimax_moderation_at_create(make_request, status):
    t = FakeTransport(lambda m, u, n: jr(status, {"base_resp": {"status_code": 1026, "status_msg": "sensitive"}}))
    out = minimax(t).run(make_request())
    assert (out.result, out.raw_result, out.provider_job_id) == ("REJECTED_POLICY", "1026", "")
    assert get_capability("minimax", "h3-lite").charged("REJECTED_POLICY") is False


@pytest.mark.parametrize("failed, expected",
                         [({"base_resp": {"status_code": 1026}}, "REJECTED_POLICY"), ({}, "PROVIDER_FAILED")])
def test_minimax_failed_task(make_request, failed, expected):
    t = FakeTransport(lambda m, u, n: jr(200, {"task_id": "t1"}) if m == "POST"
                      else jr(200, {"status": "failed", **failed}))
    out = minimax(t).run(make_request())
    assert (out.result, out.provider_job_id) == (expected, "t1")
    assert get_capability("minimax", "h3-lite").charged("PROVIDER_FAILED") is False


def test_minimax_download_on_other_host_gets_no_auth(make_request):
    cdn = "https://cdn.example.com/x.mp4"

    def script(m, u, n):
        if m == "POST":
            return jr(200, {"task_id": "t1"})
        if u == cdn:
            return HttpResponse(200, VIDEO, {})
        return jr(200, {"status": "succeeded", "content": {"url": cdn}})

    t = FakeTransport(script)
    assert minimax(t).run(make_request()).result == "PASSED"
    download = [c for c in t.calls if c["url"] == cdn]
    assert len(download) == 1 and "Authorization" not in download[0]["headers"]
    api = [c for c in t.calls if c["url"] != cdn]
    assert api and all(c["headers"]["Authorization"] == "Bearer mm-key" for c in api)


def test_minimax_succeeded_without_content_url_is_ambiguous(make_request):
    t = FakeTransport(lambda m, u, n: jr(200, {"task_id": "t1"}) if m == "POST" else jr(200, {"status": "succeeded"}))
    out = minimax(t).run(make_request())
    assert (out.result, out.raw_result, out.provider_job_id) == ("AMBIGUOUS", "no_content_url", "t1")
