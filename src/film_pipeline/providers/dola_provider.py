"""Seedance-via-Dola cookie transport — observed web contract, AI-Film boundary.

The wire contract was observed from the Owner's own Story Auto implementation
(`story_auto/providers/dola_cookie`), live-qualified there on 2026-09-23
(browser-UI canary 4: conversation receipt -> task 38417972940811793 ->
succeeded 5s MP4). No reverse-engineered third-party client is used.

Transport family: browser-cookie HTTP (www.dola.com web endpoints).
- Submit: POST /chat/completion (SSE). The SSE_ACK event carries the durable
  conversation_id receipt; the caller persists it BEFORE the stream is
  consumed further. One submission; no retries; no account rotation.
- Poll: POST /im/chain/single. The result is owned only when the input echo
  (client_request_id as local_message_id) and the reply linkage are observed
  in the same conversation; multiple video URLs fail closed.
- Download: GET on an allowlisted CDN host only, validated by ffprobe before
  the candidate file is promoted.

Signed video URLs are transport only: they are never persisted. The cookie is
held in memory only and is never logged, hashed, or written by this module.
No Dola semantics enter Film Core: Film sees only the submit/poll/download
surface and its failure classes.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

PROVIDER_ID = "seedance_dola"
REQUESTED_MODEL = "seedance_v2.0"  # observed in the upstream seed only; provider acceptance is observed post-hoc
SUPPORTED_DURATIONS = (5, 10)
SUPPORTED_ASPECTS = ("16:9", "9:16", "1:1")
ORIGIN = "https://www.dola.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024
DOWNLOAD_HOST_SUFFIXES = (".byteimg.com", ".volces.com", ".ibytedtos.com", ".bytecdn.cn")
CREDIT_FAILURE = re.compile(
    r"unable to (generate|create)|failed to (generate|create)|insufficient|"
    r"余额不足|餘額不足|额度不足|額度不足|额度耗尽|額度耗盡|"
    r"无法生成|無法生成|不能生成|無法完成|无法完成",
    re.IGNORECASE,
)
CLIENT_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,160}")
CONVERSATION_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,200}")


class DolaTransportError(RuntimeError):
    """A safe failure class; never carries provider or credential text."""

    def __init__(self, failure_class: str, dispatch_state: str = "NOT_DISPATCHED") -> None:
        self.failure_class = failure_class
        self.dispatch_state = dispatch_state
        super().__init__(failure_class)


class _Response(Protocol):
    status: int
    headers: Any
    url: str

    def read(self, amount: int = -1) -> bytes: ...

    def read1(self, amount: int = -1) -> bytes: ...

    def __enter__(self) -> "_Response": ...

    def __exit__(self, *args: Any) -> None: ...


OpenRequest = Callable[[Request, float], _Response]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DolaTransportError("DOWNLOAD_REDIRECT_REJECTED", "DISPATCH_CONFIRMED")


def _open(request: Request, timeout: float) -> _Response:
    return build_opener(_NoRedirect()).open(request, timeout=timeout)  # type: ignore[return-value]


def _cookie_value(cookie: str, name: str) -> str:
    found = re.search(r"(?:^|;)\s*" + re.escape(name) + r"=([^;]+)", cookie)
    return found.group(1) if found else ""


def _safe_host(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host.endswith(s) for s in DOWNLOAD_HOST_SUFFIXES)


def _bounded_read(response: _Response, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    data = response.read(limit + 1)
    if len(data) > limit:
        raise DolaTransportError("PROVIDER_RESPONSE_TOO_LARGE", "DISPATCH_CONFIRMED")
    return data


def _as_json(data: bytes, failure: str, dispatch_state: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DolaTransportError(failure, dispatch_state) from error
    if not isinstance(value, dict):
        raise DolaTransportError(failure, dispatch_state)
    return value


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _creation_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages = ((payload.get("downlink_body") or {}).get("pull_singe_chain_downlink_body") or {}).get("messages")
    if not isinstance(messages, list):
        return []
    blocks: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        if not isinstance(content, list):
            continue
        for block in content:
            if (isinstance(block, dict) and block.get("block_type") == 2074
                    and isinstance(block.get("content"), dict)):
                blocks.append(block["content"].get("creation_block") or {})
    return blocks


def _video_creations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The observed creation -> type 2 -> video.download_url chain, deduplicated."""
    results: list[dict[str, Any]] = []
    for block in _creation_blocks(payload):
        creations = block.get("creations")
        if not isinstance(creations, list):
            continue
        for creation in creations:
            if not isinstance(creation, dict) or creation.get("type") != 2:
                continue
            url = ((creation.get("video") or {}).get("download_url"))
            if isinstance(url, str) and url.startswith("https://"):
                results.append({"creation_id": creation.get("creation_id"), "video_url": url})
    seen: set[str] = set()
    unique = []
    for item in results:
        if item["video_url"] in seen:
            continue
        seen.add(item["video_url"])
        unique.append(item)
    return unique


def probe_session(cookie: str, *, opener: OpenRequest = _open, timeout: float = 60.0) -> bool:
    """Read-only session liveness probe: an authenticated conversation read.

    401/403 -> dead session (CREDENTIAL_OR_ACCESS_DENIED); anything else is
    treated as alive for preflight purposes. No generation is possible through
    this call.
    """
    client = DolaCookieTransport(cookie, opener=opener, timeout=timeout)
    try:
        client.poll("0" * 32)
    except DolaTransportError as error:
        if error.failure_class == "CREDENTIAL_OR_ACCESS_DENIED":
            return False
        if error.failure_class in {"PROVIDER_RESPONSE_INVALID", "PROVIDER_JOB_ID_INVALID"}:
            return True
        raise
    return True


class DolaCookieTransport:
    """One explicit cookie session; no rotation, no retries, no browser."""

    provider = PROVIDER_ID
    requested_model = REQUESTED_MODEL
    supported_durations = SUPPORTED_DURATIONS
    supported_aspects = SUPPORTED_ASPECTS

    def __init__(self, cookie: str, *, opener: OpenRequest = _open, timeout: float = 120.0):
        if (not isinstance(cookie, str) or "\r" in cookie or "\n" in cookie
                or not _cookie_value(cookie, "sessionid")):
            raise DolaTransportError("CREDENTIAL_MISSING")
        self._cookie = cookie
        self._opener = opener
        self._timeout = timeout
        self._ms_token = _cookie_value(cookie, "msToken")
        self._fp = _cookie_value(cookie, "s_v_web_id")
        self.call_counts = {"submit": 0, "poll": 0, "download": 0}

    def _params(self) -> str:
        values: dict[str, str] = {
            "aid": "495671", "channel": "g", "device_platform": "web", "language": "zh-Hant",
            "region": "JP", "sys_region": "JP", "samantha_web": "1", "use-olympus-account": "1",
            "version_code": "20800", "web_platform": "browser", "web_tab_id": str(uuid4()),
        }
        if self._ms_token:
            values["msToken"] = self._ms_token
        if self._fp:
            values["fp"] = self._fp
        return urlencode(values)

    def _headers(self, *, conversation_id: str = "", sse: bool = False) -> dict[str, str]:
        return {
            "Accept": "text/event-stream" if sse else "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Cookie": self._cookie,
            "Origin": ORIGIN,
            "Referer": ORIGIN + ("/chat/" + conversation_id if conversation_id else "/chat/"),
            "User-Agent": "AIFilmPipeline seedance_dola qualification transport",
            "agw-js-conv": "str, str" if sse else "str",
        }

    def _video_body(self, prompt: str, aspect_ratio: str, duration: int,
                    client_request_id: str) -> dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 10_000:
            raise DolaTransportError("CAPABILITY_OR_REQUEST_INVALID")
        if aspect_ratio not in SUPPORTED_ASPECTS or duration not in SUPPORTED_DURATIONS:
            raise DolaTransportError("CAPABILITY_OR_REQUEST_INVALID")
        if not CLIENT_REQUEST_ID_RE.fullmatch(client_request_id or ""):
            raise DolaTransportError("CLIENT_REQUEST_ID_INVALID")
        now_ms = int(time.time() * 1000)
        now_sec = now_ms // 1000
        return {
            "client_meta": {"local_conversation_id": f"local_{now_ms}", "conversation_id": "",
                            "bot_id": "7339470689562525703", "last_section_id": "",
                            "last_message_index": None},
            "messages": [{"local_message_id": client_request_id,
                "content_block": [{"block_type": 10000,
                    "content": {"text_block": {
                        "text": f"生成影片：{prompt.strip()}，{aspect_ratio}",
                        "icon_url": "", "icon_url_dark": "", "summary": ""},
                        "pc_event_block": ""},
                    "block_id": str(uuid4()), "parent_id": "", "meta_info": [],
                    "append_fields": []}], "message_status": 0}],
            "option": {"create_time_ms": now_ms, "need_deep_think": 0,
                       "need_create_conversation": True,
                       "conversation_init_option": {"need_ack_conversation": True},
                       "unique_key": client_request_id,
                       "recovery_option": {"is_recovery": False, "req_create_time_sec": now_sec,
                                           "append_sse_event_scene": 0},
                       "sse_recv_event_options": {"support_chunk_delta": True},
                       "message_from": 0, "is_audio": False},
            "chat_ability": {"ability_type": 17,
                "ability_param": json.dumps({"ratio": aspect_ratio, "model": REQUESTED_MODEL,
                                             "duration": duration}, separators=(",", ":"))},
            "user_context": [],
            "ext": {"fp": self._fp, "use_deep_think": "0", "sub_conv_firstmet_type": "1",
                    "conversation_init_option": '{"need_ack_conversation":true}',
                    "commerce_credit_config_enable": "0"},
        }

    def submit(self, prompt: str, aspect_ratio: str, duration: int, on_receipt,
               *, client_request_id: str) -> str:
        """Submit exactly once; persist the receipt via callback before the
        SSE stream is consumed further. The receipt is the durable identity.
        The serialized request facts (hashes, response status) are stashed on
        the transport for the caller's evidence journal; the cookie never
        enters any of them."""
        payload = self._video_body(prompt, aspect_ratio, duration, client_request_id)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        import hashlib
        url = ORIGIN + "/chat/completion?" + self._params()
        request = Request(url, data=body, method="POST", headers=self._headers(sse=True))
        self.call_counts["submit"] += 1
        try:
            response = self._opener(request, self._timeout)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise DolaTransportError("CREDENTIAL_OR_ACCESS_DENIED") from error
            raise DolaTransportError("AMBIGUOUS", "AMBIGUOUS") from error
        except (TimeoutError, URLError, OSError) as error:
            raise DolaTransportError("AMBIGUOUS", "AMBIGUOUS") from error
        self.last_request_hash = hashlib.sha256((url + "\n").encode() + body).hexdigest()
        self.last_body_sha256 = hashlib.sha256(body).hexdigest()
        self.last_response_status = int(getattr(response, "status", 200))
        try:
            with response:
                status = int(getattr(response, "status", 200))
                if status in {401, 403}:
                    raise DolaTransportError("CREDENTIAL_OR_ACCESS_DENIED")
                if status >= 400:
                    raise DolaTransportError("AMBIGUOUS", "AMBIGUOUS")
                return self._receipt_from_sse(response, on_receipt)
        except DolaTransportError:
            raise
        except (TimeoutError, URLError, OSError) as error:
            raise DolaTransportError("AMBIGUOUS", "AMBIGUOUS") from error

    def _receipt_from_sse(self, response: _Response, on_receipt) -> str:
        buffered = b""
        seen = 0
        while True:
            read_available = getattr(response, "read1", None)
            chunk = read_available(4096) if callable(read_available) else response.read(4096)
            if not chunk:
                break
            seen += len(chunk)
            if seen > MAX_RESPONSE_BYTES:
                raise DolaTransportError("PROVIDER_RESPONSE_TOO_LARGE", "AMBIGUOUS")
            buffered = (buffered + chunk).replace(b"\r\n", b"\n")
            while b"\n\n" in buffered:
                raw, buffered = buffered.split(b"\n\n", 1)
                event_name = b""
                for line in raw.splitlines():
                    if line.startswith(b"event:"):
                        event_name = line[6:].strip()
                data = b"\n".join(line[5:].strip() for line in raw.splitlines()
                                  if line.startswith(b"data:"))
                if event_name != b"SSE_ACK" or not data:
                    continue
                try:
                    event = json.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                receipt = (event.get("ack_client_meta") or {}).get("conversation_id")
                if (isinstance(receipt, str) and receipt
                        and CONVERSATION_ID_RE.fullmatch(receipt)):
                    on_receipt(receipt)
                    return receipt
        raise DolaTransportError("RECEIPT_MISSING", "AMBIGUOUS")

    def poll(self, conversation_id: str, *, client_request_id: str | None = None) -> dict[str, Any]:
        if not CONVERSATION_ID_RE.fullmatch(conversation_id or ""):
            raise DolaTransportError("PROVIDER_JOB_ID_INVALID", "DISPATCH_CONFIRMED")
        body = json.dumps({"cmd": 3100, "conversation_id": conversation_id,
                           "anchor_index": 0, "direction": 1, "limit": 20}).encode("utf-8")
        request = Request(ORIGIN + "/im/chain/single?" + self._params(), data=body,
                          method="POST",
                          headers=self._headers(conversation_id=conversation_id))
        self.call_counts["poll"] += 1
        try:
            with self._opener(request, self._timeout) as response:
                status = int(getattr(response, "status", 200))
                if status in {401, 403}:
                    raise DolaTransportError("CREDENTIAL_OR_ACCESS_DENIED", "DISPATCH_CONFIRMED")
                if status >= 400:
                    raise DolaTransportError("PROVIDER_TRANSIENT", "DISPATCH_CONFIRMED")
                payload = _as_json(_bounded_read(response), "PROVIDER_RESPONSE_INVALID",
                                   "DISPATCH_CONFIRMED")
        except DolaTransportError:
            raise
        except HTTPError as error:
            code = "CREDENTIAL_OR_ACCESS_DENIED" if error.code in {401, 403} else "PROVIDER_TRANSIENT"
            raise DolaTransportError(code, "DISPATCH_CONFIRMED") from error
        except (TimeoutError, URLError, OSError) as error:
            raise DolaTransportError("PROVIDER_TRANSIENT", "DISPATCH_CONFIRMED") from error
        creations = _video_creations(payload)
        if len(creations) > 1:
            raise DolaTransportError("PROVIDER_RESULT_AMBIGUOUS", "DISPATCH_CONFIRMED")
        if len(creations) == 1:
            if client_request_id is not None:
                # The private contract's echo must be observed, not assumed.
                messages = ((payload.get("downlink_body") or {})
                            .get("pull_singe_chain_downlink_body") or {}).get("messages", [])
                nodes = list(_walk(messages))
                matched = [n for n in nodes if n.get("local_message_id") == client_request_id]
                if not matched:
                    raise DolaTransportError("DOLA_RESULT_IDENTITY_UNVERIFIED", "DISPATCH_CONFIRMED")
                if any(n.get("conversation_id") not in {None, "", conversation_id} for n in nodes):
                    raise DolaTransportError("DOLA_RESULT_IDENTITY_MISMATCH", "DISPATCH_CONFIRMED")
                input_ids = {n.get("message_id") for n in matched
                             if isinstance(n.get("message_id"), str)}
                linked = False
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    single = {"downlink_body": {"pull_singe_chain_downlink_body": {"messages": [message]}}}
                    if not _video_creations(single):
                        continue
                    linked = (message.get("local_message_id") == client_request_id
                              or bool(input_ids.intersection(
                                  {message.get("reply_to_message_id"),
                                   message.get("parent_message_id")})))
                    if not linked:
                        raise DolaTransportError("DOLA_RESULT_IDENTITY_UNVERIFIED", "DISPATCH_CONFIRMED")
                if not linked:
                    raise DolaTransportError("DOLA_RESULT_IDENTITY_UNVERIFIED", "DISPATCH_CONFIRMED")
            creation = creations[0]
            creation_id = creation.get("creation_id")
            if not isinstance(creation_id, str) or not creation_id:
                raise DolaTransportError("DOLA_RESULT_IDENTITY_UNVERIFIED", "DISPATCH_CONFIRMED")
            return {"status": "COMPLETED", "video_url": creation["video_url"],
                    "creation_id": creation_id}
        text = " ".join(str(node.get("text", "")) for node in _walk(payload))
        return {"status": "FAILED" if CREDIT_FAILURE.search(text) else "PENDING",
                "advisory_text_found": bool(CREDIT_FAILURE.search(text))}

    def download(self, video_url: str, destination: Path) -> dict[str, Any]:
        """Exact acquisition: allowlisted host, ffprobe-validated, atomic."""
        if not _safe_host(video_url):
            raise DolaTransportError("DOWNLOAD_HOST_REJECTED", "DISPATCH_CONFIRMED")
        if destination.exists():
            raise DolaTransportError("ASSET_DESTINATION_EXISTS", "DISPATCH_CONFIRMED")
        candidate = destination.with_suffix(destination.suffix + ".candidate")
        if candidate.exists():
            raise DolaTransportError("ASSET_DESTINATION_EXISTS", "DISPATCH_CONFIRMED")
        request = Request(video_url, headers={"Accept": "video/mp4",
                                              "User-Agent": "AIFilmPipeline seedance_dola qualification transport"})
        self.call_counts["download"] += 1
        candidate_started = False
        try:
            with self._opener(request, self._timeout) as response:
                if not _safe_host(str(getattr(response, "url", video_url))):
                    raise DolaTransportError("DOWNLOAD_HOST_REJECTED", "DISPATCH_CONFIRMED")
                if int(getattr(response, "status", 200)) >= 400:
                    raise DolaTransportError("ASSET_ACQUISITION_FAILED", "DISPATCH_CONFIRMED")
                content_type = str(getattr(response, "headers", {}).get("Content-Type", "")).lower()
                if "video" not in content_type and "octet-stream" not in content_type:
                    raise DolaTransportError("ASSET_ACQUISITION_FAILED", "DISPATCH_CONFIRMED")
                destination.parent.mkdir(parents=True, exist_ok=True)
                total = 0
                candidate_started = True
                with candidate.open("wb") as handle:
                    while True:
                        part = response.read(64 * 1024)
                        if not part:
                            break
                        total += len(part)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise DolaTransportError("ASSET_ACQUISITION_FAILED", "DISPATCH_CONFIRMED")
                        handle.write(part)
            from ..live_runtime import inspect_video
            metadata = inspect_video(candidate)
            candidate.replace(destination)
            candidate_started = False
            return metadata
        except DolaTransportError:
            raise
        except (HTTPError, TimeoutError, URLError, OSError, ValueError, RuntimeError) as error:
            raise DolaTransportError("ASSET_ACQUISITION_FAILED", "DISPATCH_CONFIRMED") from error
        finally:
            if candidate_started:
                candidate.unlink(missing_ok=True)
