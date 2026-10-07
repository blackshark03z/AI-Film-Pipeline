"""V2-019 Phase D — generation-time observability normalizer.

Converts provider payloads (poll responses, SSE frames) into normalized
provider events so Film Core never depends on the wire schema. The deep
JSON-string walker is the durable fix for the V2-011W shallow-scan failure:
every string field that looks like JSON is recursively peeled, so surfaces
hidden inside video_model-style JSON strings are always seen.

URLs are normalized through redact_url(): host + parameter NAMES survive,
values never persist (signed-URL redaction rule).
"""
from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlparse

from pydantic import Field

from ...core import ContractModel

_EVENT_KINDS = (
    "GenerationReleased",
    "GenerationReceipt",
    "CreationObserved",
    "VariantObserved",
    "DraftIdentityObserved",
    "FinalizationObserved",
    "CreditStatementObserved",
)


class ProviderEvent(ContractModel):
    kind: str
    observed_at_utc: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class GenerationReleased(ProviderEvent):
    kind: str = "GenerationReleased"


class GenerationReceipt(ProviderEvent):
    kind: str = "GenerationReceipt"


class CreationObserved(ProviderEvent):
    kind: str = "CreationObserved"


class VariantObserved(ProviderEvent):
    kind: str = "VariantObserved"


class DraftIdentityObserved(ProviderEvent):
    kind: str = "DraftIdentityObserved"


class FinalizationObserved(ProviderEvent):
    kind: str = "FinalizationObserved"


class CreditStatementObserved(ProviderEvent):
    kind: str = "CreditStatementObserved"


def redact_url(url: Any) -> dict[str, Any] | str:
    """Host + query parameter NAMES only; never a signed value."""
    if not isinstance(url, str) or not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return "<unparsable>"
    if not parsed.scheme:
        return url[:24]
    names = [name for name, _value in parse_qsl(parsed.query,
                                                keep_blank_values=True)]
    return {"scheme": parsed.scheme, "host": parsed.hostname,
            "path_len": len(parsed.path),
            "query_param_names": sorted(names), "redacted": True}


def deep_json_strings(node: Any, max_depth: int = 8,
                      max_nodes: int = 20000) -> Iterator[Any]:
    """Visit every container reachable from node, recursively json.loads-ing
    string values that look like JSON (the V2-011W rule: surfaces hidden
    inside JSON-string fields must never be skipped). Yields each dict/list
    visited. Bounded to avoid pathological inputs."""
    stack: list[tuple[Any, int]] = [(node, 0)]
    seen = 0
    while stack:
        current, depth = stack.pop()
        seen += 1
        if seen > max_nodes or depth > max_depth:
            return
        if isinstance(current, str):
            s = current.strip()
            if s[:1] in "{[":
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                stack.append((obj, depth + 1))
        elif isinstance(current, dict):
            yield current
            for value in current.values():
                stack.append((value, depth + 1))
        elif isinstance(current, list):
            yield current
            for value in current:
                stack.append((value, depth + 1))


def decode_media_url(value: Any) -> str:
    """Provider encodes rendition URLs as base64; decoding is reading, not
    construction. Plain https URLs pass through; anything else fails to ''."""
    if not isinstance(value, str) or not value:
        return ""
    if value.startswith("https://") or value.startswith("http://"):
        return value
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return ""
    return decoded if decoded.startswith(("https://", "http://")) else ""


def _text_of(blocks: Any) -> str:
    text = ""
    if not isinstance(blocks, list):
        return text
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("block_type") == 10000:
            content = block.get("content") or {}
            text_block = content.get("text_block") or {}
            text += str(text_block.get("text") or "")
    return text


def _iter_creation_objects(payload: dict) -> list[dict]:
    """Creation dicts found by walking every peeled object."""
    rows: list[dict] = []
    seen: set[int] = set()
    for obj in [payload, *deep_json_strings(payload)]:
        if not isinstance(obj, dict):
            continue
        candidates = []
        content = obj.get("content")
        if isinstance(content, list):
            for block in content:
                inner = block.get("content") if isinstance(block, dict) \
                    else None
                if isinstance(inner, dict):
                    candidates.append(
                        inner.get("creation_block") or {})
        if isinstance(obj.get("creation_block"), dict):
            candidates.append(obj["creation_block"])
        if obj.get("block_type") == 2074 and \
                isinstance(obj.get("content"), dict):
            candidates.append(
                (obj["content"].get("creation_block") or {}))
        for block in candidates:
            if not isinstance(block, dict):
                continue
            for creation in block.get("creations") or []:
                if isinstance(creation, dict) and id(creation) not in seen:
                    seen.add(id(creation))
                    rows.append(creation)
    return rows


def normalize_poll_payload(payload: dict, *,
                           observed_at_utc: str | None = None) -> list[ProviderEvent]:
    """Normalized events from a /im/chain/single (or recent_conv) payload.

    Produces CreationObserved (+ VariantObserved per rendition) and
    CreditStatementObserved where provider text states a remaining count.
    DraftIdentityObserved / FinalizationObserved are emitted ONLY for real
    provider draft identity / finalization ops — never inferred.
    """
    events: list[ProviderEvent] = []
    for creation in _iter_creation_objects(payload):
        creation_id = str(creation.get("id") or "")
        video = creation.get("video") if isinstance(creation.get("video"),
                                                    dict) else {}
        status = video.get("status")
        base = {"creation_id": creation_id,
                "conversation_id": creation.get("conversation_id"),
                "video_status": status,
                "type": creation.get("type")}
        events.append(CreationObserved(observed_at_utc=observed_at_utc,
                                       data=base))
        # the deep surface: video.video_model is a JSON STRING
        video_model_raw = video.get("video_model")
        video_model = None
        if isinstance(video_model_raw, str):
            try:
                video_model = json.loads(video_model_raw)
            except Exception:
                video_model = None
        elif isinstance(video_model_raw, dict):
            video_model = video_model_raw
        if not isinstance(video_model, dict):
            for obj in deep_json_strings(video):
                if isinstance(obj, dict) and "video_list" in obj:
                    video_model = obj
                    break
        if isinstance(video_model, dict):
            video_list = video_model.get("video_list")
            if isinstance(video_list, dict):
                for name, rendition in video_list.items():
                    if not isinstance(rendition, dict):
                        continue
                    main = decode_media_url(rendition.get("main_url"))
                    lr = ""
                    if main:
                        try:
                            query = dict(parse_qsl(urlparse(main).query))
                            lr = query.get("lr", "")
                        except Exception:
                            lr = ""
                    events.append(VariantObserved(
                        observed_at_utc=observed_at_utc,
                        data={
                            "creation_id": creation_id,
                            "list_key": name,
                            "definition": rendition.get("definition"),
                            "quality": rendition.get("quality"),
                            "bitrate": rendition.get("bitrate"),
                            "width": rendition.get("vwidth"),
                            "height": rendition.get("vheight"),
                            "variant_lr": lr or None,
                            "main_url": redact_url(main),
                            "download_url": redact_url(
                                video.get("download_url")),
                        }))
    # credit statements from bot text (dedup by statement head)
    seen_statements: set[str] = set()
    for obj in deep_json_strings(payload):
        if not isinstance(obj, dict):
            continue
        content = obj.get("content")
        blocks = None
        if isinstance(content, str):
            try:
                blocks = json.loads(content)
            except Exception:
                blocks = None
        elif isinstance(content, list):
            blocks = content
        if blocks is None:
            continue
        text = _text_of(blocks)
        if not text:
            continue
        import re

        match = re.search(r"残り\s*(\d+)\s*(?:枚|個)?", text)
        if match and text[:80] not in seen_statements:
            seen_statements.add(text[:80])
            events.append(CreditStatementObserved(
                observed_at_utc=observed_at_utc,
                data={"remaining": int(match.group(1)),
                         "source_text_head": text[:80]}))
    return events


def classify_dispatch_state(method: str, failure_class: str) -> str:
    """AMBIGUOUS_POST_DISPATCH discipline for the SSE submit: a POST
    timeout/5xx after the request left the process is AMBIGUOUS."""
    if method != "POST":
        return "NOT_DISPATCHED"
    if failure_class in ("PROVIDER_TRANSIENT", "TIMEOUT", "CONNECTION_RESET"):
        return "AMBIGUOUS"
    return "NOT_DISPATCHED"
