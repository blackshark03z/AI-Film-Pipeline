"""REST video adapters: an OpenAI-style ``/v1/videos`` gateway (Vilao) and the official MiniMax API.

Both follow submit -> poll -> download, with the job id as the take's binding (``provider_job_id``). Only stdlib
``urllib`` is used; tests inject a fake ``Transport`` or point ``base_url`` at a local mock server. Base URL, API model id,
auth env var, request field names and the error map come from the capability registry; nothing provider-specific is
decided in the shared code. The API key is read from the environment at call time and never stored or reported.

Field mappings the docs do not settle are listed under ``unverified`` in the registry (Vilao: how frames and references
map onto the body; MiniMax: the ``content[]`` image key) and stay so until the phase B live probe.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, NamedTuple, Protocol

from pydantic import Field

from ..core import ContractModel
from .base import ProviderHealth
from .capability import ModelCapability, NormalizedResult
from .request import GenerationRequest


class HttpResponse(NamedTuple):
    status: int
    body: bytes
    headers: dict[str, str]


class TransportError(Exception):
    """No HTTP response. ``refused`` = the connection was refused, so the request surely never arrived."""

    def __init__(self, message: str, *, refused: bool = False) -> None:
        super().__init__(message)
        self.refused = refused


class Transport(Protocol):
    def request(self, method: str, url: str, headers: Mapping[str, str], body: bytes | None = None,
                timeout: float = 60.0) -> HttpResponse: ...


class UrllibTransport:
    """stdlib transport: a non-2xx status is a response, not an exception."""

    def request(self, method: str, url: str, headers: Mapping[str, str], body: bytes | None = None,
                timeout: float = 60.0) -> HttpResponse:
        req = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https/http URLs from the registry
                return HttpResponse(resp.status, resp.read(), dict(resp.headers.items()))
        except urllib.error.HTTPError as exc:
            return HttpResponse(exc.code, exc.read() or b"", dict(exc.headers.items()) if exc.headers else {})
        except urllib.error.URLError as exc:
            refused = isinstance(exc.reason, ConnectionRefusedError)
            raise TransportError(f"{type(exc.reason).__name__}", refused=refused) from None
        except (TimeoutError, OSError) as exc:
            raise TransportError(type(exc).__name__) from None


class ProviderJobError(Exception):
    """A request the provider answered with a failure (or that never got an answer)."""

    def __init__(self, raw: str, result: NormalizedResult, detail: str = "") -> None:
        super().__init__(f"{raw}: {result} {detail}".strip())
        self.raw, self.result, self.detail = raw, result, detail


class ProviderNotReady(Exception):
    pass


class JobStatus(ContractModel):
    state: Literal["pending", "done"]
    raw: str = ""
    result: NormalizedResult | None = None
    content_url: str = ""


class AdapterOutcome(ContractModel):
    raw_result: str
    result: NormalizedResult
    provider_job_id: str = ""
    output: str = ""
    sha256: str = ""
    detail: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


def _data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(Path(path).read_bytes()).decode('ascii')}"


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, ValueError):
        return None


def _error_code(body: Any) -> str:
    """The provider's error code from a JSON body: ``error.code``/``error.type``, MiniMax ``base_resp.status_code``,
    or a top-level ``code``. "" when there is none (or the code is the success code 0)."""
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    if isinstance(err, dict):
        for key in ("code", "type"):
            if err.get(key) not in (None, "", 0):
                return str(err[key])
    base = body.get("base_resp")
    if isinstance(base, dict) and base.get("status_code") not in (None, 0, "0"):
        return str(base["status_code"])
    if body.get("code") not in (None, "", 0, "0"):
        return str(body["code"])
    return ""


class HttpVideoAdapter:
    """Shared submit/poll/download loop; subclasses build the body and read the provider's statuses."""

    def __init__(self, cap: ModelCapability, *, transport: Transport | None = None,
                 env: Mapping[str, str] | None = None, base_url: str | None = None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 poll_interval_s: float = 10.0, timeout_s: float = 900.0, request_timeout_s: float = 60.0) -> None:
        self.cap = cap
        self.transport = transport or UrllibTransport()
        self.env = env if env is not None else os.environ
        self.base_url = (base_url or cap.base_url).rstrip("/")
        self.sleep, self.clock = sleep, clock
        self.poll_interval_s, self.timeout_s, self.request_timeout_s = poll_interval_s, timeout_s, request_timeout_s
        self._content_urls: dict[str, str] = {}

    # ---- plumbing ----------------------------------------------------------------------------------------------
    def _key(self) -> str:
        """The key from ``<auth_env>``, else from the file named by ``<auth_env>_FILE`` (first non-empty line).
        Never printed, logged or stored; error texts only name the variables."""
        if not self.cap.auth_env:
            raise ProviderNotReady("the registry entry names no auth env var")
        key = (self.env.get(self.cap.auth_env) or "").strip()
        if not key:
            file_var = f"{self.cap.auth_env}_FILE"
            path = (self.env.get(file_var) or "").strip()
            if path:
                try:
                    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
                except OSError:
                    raise ProviderNotReady(f"{file_var} names a file that cannot be read") from None
                key = next((line.strip() for line in lines if line.strip()), "")
        if not key:
            raise ProviderNotReady(f"neither {self.cap.auth_env} nor {self.cap.auth_env}_FILE gives a key")
        return key

    def _headers(self, url: str, *, json_body: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/json, */*"}
        if json_body:
            headers["Content-Type"] = "application/json"
        # the key goes only to the provider's own host (a download URL on a CDN gets no Authorization header)
        if urllib.parse.urlsplit(url).netloc == urllib.parse.urlsplit(self.base_url).netloc:
            headers["Authorization"] = f"Bearer {self._key()}"
        return headers

    def _call(self, method: str, url: str, payload: dict[str, Any] | None = None) -> HttpResponse:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = self._headers(url, json_body=payload is not None)
        try:
            return self.transport.request(method, url, headers, body, timeout=self.request_timeout_s)
        except TransportError as exc:
            raw = "transport_refused" if exc.refused else "transport_error"
            raise ProviderJobError(raw, self.cap.normalize(raw), self._scrub(str(exc))) from None

    def _scrub(self, text: str) -> str:
        """Remove the key from any text that may end up in a receipt or a log."""
        try:
            key = self._key()
        except ProviderNotReady:
            return text
        return text.replace(key, "***") if key else text

    def classify(self, status: int, body: Any) -> tuple[str, NormalizedResult]:
        """(raw, normalized) of a failed response: a known error code wins over the HTTP status."""
        code = _error_code(body)
        if code and (code in self.cap.error_map.exact or any(code.startswith(p) for p in self.cap.error_map.prefix)):
            return code, self.cap.normalize(code)
        raw = f"http_{status}" + (f" {code}" if code else "")
        return raw, self.cap.normalize(f"http_{status}")

    # ---- subclass hooks ------------------------------------------------------------------------------------
    def submit_url(self) -> str:
        raise NotImplementedError

    def build_body(self, request: GenerationRequest) -> dict[str, Any]:
        raise NotImplementedError

    def job_id_of(self, body: Any) -> str:
        raise NotImplementedError

    def status_url(self, job_id: str) -> str:
        raise NotImplementedError

    def read_status(self, job_id: str, body: Any) -> JobStatus:
        raise NotImplementedError

    def content_url(self, job_id: str) -> str:
        raise NotImplementedError

    # ---- sync API (generate.py) ----------------------------------------------------------------------------
    def health(self) -> ProviderHealth:
        pid = self.cap.provider
        if not (self.base_url and self.cap.api_model):
            return ProviderHealth(provider_id=pid, state="MISCONFIGURED", diagnostic_code="REGISTRY_INCOMPLETE")
        try:
            self._key()
        except ProviderNotReady:
            return ProviderHealth(provider_id=pid, state="AUTH_REQUIRED", diagnostic_code="KEY_ENV_MISSING",
                                  evidence=[self.cap.auth_env])
        return ProviderHealth(provider_id=pid, state="READY", diagnostic_code="KEY_PRESENT_NOT_PROBED")

    def submit_sync(self, request: GenerationRequest) -> str:
        resp = self._call("POST", self.submit_url(), self.build_body(request))
        body = _json(resp.body)
        if not 200 <= resp.status < 300 or _error_code(body):
            raw, result = self.classify(resp.status, body)
            raise ProviderJobError(raw, result)
        job_id = self.job_id_of(body)
        if not job_id:
            # 2xx without a job id: the provider may have queued it, we cannot tell
            raise ProviderJobError("no_job_id", "AMBIGUOUS")
        return job_id

    def poll_sync(self, job_id: str) -> JobStatus:
        resp = self._call("GET", self.status_url(job_id))
        body = _json(resp.body)
        if not 200 <= resp.status < 300:
            if resp.status >= 500 or resp.status == 429:
                return JobStatus(state="pending", raw=f"http_{resp.status}")  # transient: keep polling
            raw, result = self.classify(resp.status, body)
            return JobStatus(state="done", raw=raw, result="AMBIGUOUS" if result == "NOT_SUBMITTED" else result)
        status = self.read_status(job_id, body)
        if status.content_url:
            self._content_urls[job_id] = status.content_url
        return status

    def fetch_sync(self, job_id: str, out: Path) -> tuple[Path, str]:
        import hashlib
        out = Path(out)
        if out.exists():
            raise FileExistsError(f"{out} exists; a take is evidence and is never overwritten")
        resp = self._call("GET", self.content_url(job_id))
        if not 200 <= resp.status < 300 or not resp.body:
            raise ProviderJobError(f"download_http_{resp.status}", "AMBIGUOUS")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.body)
        return out, hashlib.sha256(resp.body).hexdigest()

    def run(self, request: GenerationRequest, on_submitted: Callable[[str], None] | None = None) -> AdapterOutcome:
        """Submit, poll until done (or ``timeout_s``: AMBIGUOUS, the job id stays bound), download a PASSED clip."""
        if request.output_path.exists():  # checked before paying: the download could never be written
            return AdapterOutcome(raw_result="output_exists", result="NOT_SUBMITTED",
                                  detail=f"{request.output} exists; a take is evidence and is never overwritten")
        try:
            job_id = self.submit_sync(request)
        except ProviderJobError as exc:
            return AdapterOutcome(raw_result=exc.raw, result=exc.result, detail=exc.detail)
        if on_submitted is not None:
            on_submitted(job_id)
        started = self.clock()
        while True:
            try:
                status = self.poll_sync(job_id)
            except ProviderJobError as exc:  # network trouble while polling: the job exists, keep trying
                status = JobStatus(state="pending", raw=exc.raw)
            if status.state == "done":
                break
            if self.clock() - started >= self.timeout_s:
                return AdapterOutcome(raw_result="timeout", result="AMBIGUOUS", provider_job_id=job_id,
                                      detail=f"still {status.raw or 'pending'} after {self.timeout_s:g} s")
            self.sleep(self.poll_interval_s)
        assert status.result is not None
        if status.result != "PASSED":
            return AdapterOutcome(raw_result=status.raw, result=status.result, provider_job_id=job_id)
        try:
            path, sha = self.fetch_sync(job_id, request.output_path)
        except ProviderJobError as exc:
            return AdapterOutcome(raw_result=exc.raw, result="AMBIGUOUS", provider_job_id=job_id, detail=exc.detail)
        return AdapterOutcome(raw_result=status.raw, result="PASSED", provider_job_id=job_id, output=str(path),
                              sha256=sha)

    # ---- VideoProvider -------------------------------------------------------------------------------------
    def capabilities(self):
        return self.cap.provider_capabilities()

    async def preflight(self) -> ProviderHealth:
        return self.health()

    async def submit(self, request: GenerationRequest) -> str:
        return self.submit_sync(request)

    async def poll(self, provider_job_id: str) -> JobStatus:
        return self.poll_sync(provider_job_id)

    async def fetch_outputs(self, provider_job_id: str, out: Path | None = None) -> list[str]:
        if out is None:
            raise ValueError("fetch_outputs needs the output path of the take")
        return [str(self.fetch_sync(provider_job_id, out)[0])]

    async def cancel(self, provider_job_id: str) -> bool:
        return False  # neither API documents a cancel call we rely on


class OpenAIVideosAdapter(HttpVideoAdapter):
    """OpenAI Videos shape: ``POST {base}/v1/videos``, ``GET {base}/v1/videos/{id}?model=``,
    ``GET {base}/v1/videos/{id}/content?model=`` (Vilao seller endpoint, e.g. base ``https://api.vilao.ai/p/omh3``)."""

    PENDING = ("queued", "in_progress", "processing", "pending", "running")

    def _model_query(self) -> str:
        return urllib.parse.urlencode({"model": self.cap.api_model})

    def submit_url(self) -> str:
        return f"{self.base_url}/v1/videos"

    def status_url(self, job_id: str) -> str:
        return f"{self.base_url}/v1/videos/{urllib.parse.quote(job_id, safe='')}?{self._model_query()}"

    def content_url(self, job_id: str) -> str:
        return f"{self.base_url}/v1/videos/{urllib.parse.quote(job_id, safe='')}/content?{self._model_query()}"

    def build_body(self, request: GenerationRequest) -> dict[str, Any]:
        f = self.cap.request_fields  # UNVERIFIED mapping (registry)
        body: dict[str, Any] = {"model": self.cap.api_model, "prompt": request.prompt,
                                f.get("seconds", "seconds"): str(request.duration_s)}
        native = self.cap.tiers.get(request.tier, "")
        size = self.cap.size_by_aspect.get(native, {}).get(request.aspect)
        if size:
            body[f.get("size", "size")] = size
        if request.first_frame is not None:
            body[f.get("first_frame", "input_reference")] = _data_url(request.first_frame.path)
        if request.last_frame is not None:
            body[f.get("last_frame", "last_frame")] = _data_url(request.last_frame.path)
        if request.references:
            body[f.get("reference_image", "reference_images")] = [_data_url(r.path) for r in request.references]
        return body

    def job_id_of(self, body: Any) -> str:
        return str(body.get("id") or "") if isinstance(body, dict) else ""

    def read_status(self, job_id: str, body: Any) -> JobStatus:
        state = str((body or {}).get("status") or "").lower() if isinstance(body, dict) else ""
        if state in self.PENDING or not state:
            return JobStatus(state="pending", raw=state or "no_status")
        code = _error_code(body)
        if state == "failed" and code and code in self.cap.error_map.exact:
            return JobStatus(state="done", raw=code, result=self.cap.normalize(code))
        raw = f"status_{state}"
        return JobStatus(state="done", raw=raw + (f" {code}" if code else ""), result=self.cap.normalize(raw))


class MiniMaxAdapter(HttpVideoAdapter):
    """Official MiniMax API: ``POST {base}/v2/video_generation`` -> ``task_id``;
    ``GET {base}/v2/query/video_generation/{task_id}`` -> ``queued``/``running``/``succeeded``/``failed``
    (+ ``content.url``). ``content[]`` roles: ``first_frame``, ``last_frame``, ``reference_image``. Code 1026 =
    moderation; failed tasks are not charged (registry ``charged_on``)."""

    PENDING = ("queued", "running", "processing", "pending")

    def submit_url(self) -> str:
        return f"{self.base_url}/v2/video_generation"

    def status_url(self, job_id: str) -> str:
        return f"{self.base_url}/v2/query/video_generation/{urllib.parse.quote(job_id, safe='')}"

    def content_url(self, job_id: str) -> str:
        url = self._content_urls.get(job_id)
        if not url:
            raise ProviderJobError("no_content_url", "AMBIGUOUS")
        return url

    def build_body(self, request: GenerationRequest) -> dict[str, Any]:
        f = self.cap.request_fields
        key = f.get("content_image_key", "image_url")  # UNVERIFIED (registry)
        content: list[dict[str, str]] = []
        if request.first_frame is not None:
            content.append({"role": "first_frame", key: _data_url(request.first_frame.path)})
        if request.last_frame is not None:
            content.append({"role": "last_frame", key: _data_url(request.last_frame.path)})
        content += [{"role": "reference_image", key: _data_url(r.path)} for r in request.references]
        body: dict[str, Any] = {"model": self.cap.api_model, "prompt": request.prompt,
                                f.get("duration", "duration"): int(request.duration_s),
                                f.get("resolution", "resolution"): self.cap.tiers.get(request.tier, ""),
                                f.get("ratio", "ratio"): request.aspect}
        if content:
            body["content"] = content
        return body

    def job_id_of(self, body: Any) -> str:
        return str(body.get("task_id") or "") if isinstance(body, dict) else ""

    def read_status(self, job_id: str, body: Any) -> JobStatus:
        if not isinstance(body, dict):
            return JobStatus(state="pending", raw="no_status")
        state = str(body.get("status") or "").lower()
        if state in self.PENDING or not state:
            return JobStatus(state="pending", raw=state or "no_status")
        code = _error_code(body)
        if code and code in self.cap.error_map.exact:
            return JobStatus(state="done", raw=code, result=self.cap.normalize(code))
        content = body.get("content") if isinstance(body.get("content"), dict) else {}
        raw = f"status_{state}"
        return JobStatus(state="done", raw=raw + (f" {code}" if code else ""), result=self.cap.normalize(raw),
                         content_url=str(content.get("url") or ""))


def make_adapter(cap: ModelCapability, **kw: Any):
    """The adapter class the registry entry names. Flow's is built by generate.py (it needs the runner)."""
    if cap.adapter == "openai_videos":
        return OpenAIVideosAdapter(cap, **kw)
    if cap.adapter == "minimax":
        return MiniMaxAdapter(cap, **kw)
    if cap.adapter == "flow_ui":
        from .flow_ui_adapter import FlowUiAdapter
        return FlowUiAdapter(cap, **kw)
    raise ValueError(f"no adapter {cap.adapter!r}")
