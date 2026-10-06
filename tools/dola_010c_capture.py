"""AI-FILM-QUALITY-V2-010C — Layer 2 CDP network capture harness.

Attaches a raw CDP Network-domain session to the browser page and records the
FULL protocol surface (requests incl. post data, extra-info headers/cookies,
responses, SSE frames, WebSocket frames, bodies) into a JSONL raw file that
stays OUTSIDE tracked evidence and is DPAPI-encrypted when a capture closes.

`sanitize_capture` later produces the tracked structural evidence version:
cookie/token/set-cookie values stripped, signed-URL queries stripped, response
bodies reduced to structure + safe scalar values.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from dola_010c_session import RAW_DIR, dpapi_protect

MAX_BODY_BYTES = 2 * 1024 * 1024
BODY_MIME = ("application/json", "text/event-stream", "text/plain",
             "application/x-www-form-urlencoded", "text/html")

SECRET_KEY_RE = re.compile(
    r"cookie|token|session|passwd|password|secret|authorization|msToken|csrf",
    re.I)
SIGNED_URL_QUERY_RE = re.compile(
    r"(?:\\{1,2}u0026|[?&])(X-Amz-Signature|signature|sig|token|Expires|"
    r"X-Goog-Signature|x-expires|x-signature|"
    r"msToken|a_bogus|fp|access_key)=[^&\"\\]*", re.I)


def _utcnow() -> float:
    return datetime.now(timezone.utc).timestamp()


class NetworkCapture:
    """Raw CDP capture → JSONL. Secrets stay in the raw layer only."""

    def __init__(self, context, page, run_id: str) -> None:
        self._context = context
        self._page = page
        self.run_id = run_id
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.raw_path = RAW_DIR / f"raw_{run_id}.jsonl"
        self._handle = self.raw_path.open("a", encoding="utf-8")
        self._cdp = None
        self._pending_bodies: dict[str, dict] = {}
        self.event_counts: dict[str, int] = {}
        self.active = False
        self.started_at: str | None = None
        # live-view for drivers: recent entries + sync subscribers (no awaits)
        self.recent: list[dict] = []
        self.subscribers = []

    # -- plumbing -----------------------------------------------------------

    def _record(self, kind: str, payload: dict) -> None:
        entry = {"kind": kind, "utc": datetime.now(timezone.utc).isoformat(),
                 **payload}
        self._handle.write(json.dumps(entry, ensure_ascii=False,
                                      separators=(",", ":")) + "\n")
        self._handle.flush()
        self.event_counts[kind] = self.event_counts.get(kind, 0) + 1
        self.recent.append(entry)
        if len(self.recent) > 4000:
            del self.recent[:2000]
        for subscriber in tuple(self.subscribers):
            try:
                subscriber(entry)
            except Exception:
                pass

    async def start(self) -> dict:
        self._cdp = await self._context.new_cdp_session(self._page)
        await self._cdp.send("Network.enable", {
            "maxResourceBufferSize": MAX_BODY_BYTES,
            "maxTotalBufferSize": MAX_BODY_BYTES * 4})
        for domain_event, handler in (
            ("Network.requestWillBeSent", self._on_request),
            ("Network.requestWillBeSentExtraInfo", self._on_request_extra),
            ("Network.responseReceived", self._on_response),
            ("Network.responseReceivedExtraInfo", self._on_response_extra),
            ("Network.EventSourceMessageReceived", self._on_sse),
            ("Network.webSocketCreated", self._on_ws_created),
            ("Network.webSocketFrameSent", self._on_ws_frame),
            ("Network.webSocketFrameReceived", self._on_ws_frame),
            ("Network.webSocketClosed", self._on_ws_closed),
            ("Network.loadingFinished", self._on_loading_finished),
            ("Network.loadingFailed", self._on_loading_failed),
        ):
            self._cdp.on(domain_event, handler)
        self.active = True
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._record("CAPTURE_STARTED", {"run_id": self.run_id})
        return {"capture": "ACTIVE", "raw_path": str(self.raw_path)}

    async def stop(self, *, encrypt: bool = True) -> dict:
        if not self.active:
            return {"capture": "INACTIVE"}
        self._record("CAPTURE_STOPPED", {})
        self.active = False
        self._handle.close()
        summary = {"events": self.event_counts,
                   "raw_path": str(self.raw_path)}
        if encrypt:
            blob = self.raw_path.read_bytes()
            encrypted = self.raw_path.with_suffix(".jsonl.dpapi")
            encrypted.write_text(dpapi_protect(blob), encoding="ascii")
            self.raw_path.unlink(missing_ok=True)
            summary["raw_encrypted"] = True
            summary["raw_encrypted_sha256_12"] = hashlib.sha256(
                blob).hexdigest()[:12]
        return summary

    # -- request body / response body fetchers -------------------------------

    async def get_post_data(self, request_id: str) -> str | None:
        try:
            result = await self._cdp.send("Network.getRequestPostData",
                                          {"requestId": request_id})
            return result.get("postData")
        except Exception:
            return None

    async def get_response_body(self, request_id: str) -> dict | None:
        try:
            result = await self._cdp.send("Network.getResponseBody",
                                          {"requestId": request_id})
            return result
        except Exception:
            return None

    # -- CDP handlers ---------------------------------------------------------

    def _on_request(self, event: dict) -> None:
        request = event.get("request") or {}
        self._record("REQ", {
            "request_id": event.get("requestId"),
            "url": request.get("url"), "method": request.get("method"),
            "headers": request.get("headers"),
            "has_post_data": request.get("hasPostData", False),
            "type": event.get("type"), "initiator": (event.get("initiator") or {}).get("type"),
            "document_url": event.get("documentURL"),
            "wall_time": event.get("wallTime"),
            "redirect_response": bool(event.get("redirectResponse"))})

    def _on_request_extra(self, event: dict) -> None:
        cookies = [(c.get("name"), len(c.get("value") or ""))
                   for c in (event.get("associatedCookies") or [])]
        self._record("REQ_EXTRA", {"request_id": event.get("requestId"),
                                   "cookie_names": cookies,
                                   "headers": event.get("headers")})

    def _on_response(self, event: dict) -> None:
        response = event.get("response") or {}
        mime = response.get("mimeType") or ""
        record = {"request_id": event.get("requestId"),
                  "url": response.get("url"), "status": response.get("status"),
                  "mime": mime, "headers": response.get("headers"),
                  "remote_ip": response.get("remoteIPAddress"),
                  "protocol": response.get("protocol"),
                  "from_disk_cache": response.get("fromDiskCache", False)}
        self._record("RESP", record)
        if any(part in mime for part in BODY_MIME) and mime:
            self._pending_bodies[event.get("requestId")] = {
                "url": response.get("url"), "mime": mime}

    def _on_response_extra(self, event: dict) -> None:
        self._record("RESP_EXTRA", {"request_id": event.get("requestId"),
                                    "headers": event.get("headers")})

    def _on_sse(self, event: dict) -> None:
        self._record("SSE_FRAME", {
            "request_id": event.get("requestId"),
            "event_name": event.get("eventName"),
            "event_id": event.get("eventId"),
            "data": event.get("data"),
            "timestamp": event.get("timestamp")})

    def _on_ws_created(self, event: dict) -> None:
        self._record("WS_CREATED", {"request_id": event.get("requestId"),
                                    "url": event.get("url")})

    def _on_ws_frame(self, event: dict) -> None:
        payload = event.get("response") or event
        self._record("WS_FRAME", {
            "request_id": event.get("requestId"),
            "opcode": payload.get("opcode"),
            "data": (payload.get("payloadData") or "")[:4096],
            "masked": payload.get("payloadData", "")[:0] == ""})

    def _on_ws_closed(self, event: dict) -> None:
        self._record("WS_CLOSED", {"request_id": event.get("requestId")})

    def _on_loading_finished(self, event: dict) -> None:
        request_id = event.get("requestId")
        self._record("LOAD_FINISHED", {
            "request_id": request_id,
            "encoded_length": event.get("encodedDataLength")})
        pending = self._pending_bodies.pop(request_id, None)
        if pending:
            asyncio.ensure_future(self._store_body(request_id, pending))

    def _on_loading_failed(self, event: dict) -> None:
        self._pending_bodies.pop(event.get("requestId"), None)
        self._record("LOAD_FAILED", {
            "request_id": event.get("requestId"),
            "error": event.get("errorText"),
            "canceled": event.get("canceled", False)})

    async def _store_body(self, request_id: str, pending: dict) -> None:
        result = await self.get_response_body(request_id)
        if not result:
            self._record("BODY", {"request_id": request_id, **pending,
                                  "body_available": False})
            return
        body = result.get("body") or ""
        if result.get("base64Encoded"):
            self._record("BODY", {"request_id": request_id, **pending,
                                  "body_available": True, "base64": True,
                                  "body_len": len(body)})
            return
        self._record("BODY", {"request_id": request_id, **pending,
                              "body_available": True,
                              "body": body[:MAX_BODY_BYTES]})


# ------------------------------------------------------------- sanitizer ---

def _sanitize_value(key: str, value):
    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(key, v) for v in value]
    if isinstance(value, str):
        if SECRET_KEY_RE.search(key or ""):
            return "REDACTED"
        return SIGNED_URL_QUERY_RE.sub(r"\1=REDACTED", value)
    return value


def _truncate(value, depth: int = 0, max_children: int = 24):
    if isinstance(value, dict):
        if depth > 9:
            return {"__depth_truncated__": True}
        return {k: _truncate(v, depth + 1, max_children)
                for k, v in list(value.items())[:max_children]}
    if isinstance(value, list):
        return [_truncate(v, depth + 1, max_children)
                for v in value[:max_children]] + \
            ([{"__list_truncated__": len(value)}] if len(value) > max_children else [])
    if isinstance(value, str) and len(value) > 300:
        return value[:300] + f"...({len(value)} chars)"
    return value


def sanitize_capture(raw_path: Path, out_path: Path, *,
                     keep_bodies: bool = True) -> dict:
    """Produce the tracked structural evidence version of a raw capture."""
    entries_out = []
    body_count = 0
    with raw_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            kind = entry.get("kind")
            if kind in ("REQ", "RESP", "REQ_EXTRA", "RESP_EXTRA"):
                cleaned = {k: _sanitize_value(k, v) for k, v in entry.items()}
                if kind == "REQ_EXTRA":
                    cleaned.pop("headers", None)  # raw cookie/header values
                entries_out.append(_truncate(cleaned))
            elif kind == "SSE_FRAME":
                data = entry.get("data") or ""
                parsed = None
                try:
                    parsed = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    parsed = None
                cleaned = {"kind": kind, "utc": entry.get("utc"),
                           "request_id": entry.get("request_id"),
                           "event_name": entry.get("event_name"),
                           "structure": _truncate(parsed) if parsed is not None
                           else data[:300]}
                entries_out.append(cleaned)
            elif kind == "BODY" and keep_bodies:
                body = entry.get("body")
                parsed = None
                if isinstance(body, str):
                    try:
                        parsed = json.loads(body)
                    except (json.JSONDecodeError, ValueError):
                        parsed = None
                cleaned = {"kind": "BODY_STRUCTURE", "utc": entry.get("utc"),
                           "request_id": entry.get("request_id"),
                           "url": SIGNED_URL_QUERY_RE.sub(
                               r"\1=REDACTED", entry.get("url") or ""),
                           "mime": entry.get("mime"),
                           "body_available": entry.get("body_available")}
                if parsed is not None:
                    cleaned["structure"] = _truncate(_sanitize_value("", parsed))
                    body_count += 1
                elif isinstance(body, str):
                    cleaned["text_head"] = body[:300]
                    body_count += 1
                entries_out.append(cleaned)
            elif kind in ("LOAD_FINISHED", "LOAD_FAILED", "WS_CREATED",
                          "WS_CLOSED", "CAPTURE_STARTED", "CAPTURE_STOPPED"):
                cleaned = dict(entry)
                if kind == "WS_CREATED":
                    cleaned["url"] = SIGNED_URL_QUERY_RE.sub(
                        r"\1=REDACTED", cleaned.get("url") or "")
                entries_out.append(cleaned)
            # WS_FRAME bodies may contain secrets; structure-only:
            elif kind == "WS_FRAME":
                data = entry.get("data") or ""
                try:
                    parsed = json.loads(data)
                    structure = _truncate(_sanitize_value("", parsed))
                except (json.JSONDecodeError, ValueError):
                    structure = data[:200]
                entries_out.append({"kind": kind, "utc": entry.get("utc"),
                                    "request_id": entry.get("request_id"),
                                    "structure": structure})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries_out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return {"sanitized_path": str(out_path), "entries": len(entries_out),
            "bodies_structured": body_count}
