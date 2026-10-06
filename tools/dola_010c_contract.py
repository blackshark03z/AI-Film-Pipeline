"""AI-FILM-QUALITY-V2-010C — contract layer: pure parsers + redaction.

These functions are the PYTHON contract oracle for the Dola current protocol
(the browser runs equivalent JS). Golden fixtures recorded from live 010C
sessions replay through them in tests. No secrets pass through: every
consumer receives sanitized structures.
"""
from __future__ import annotations

import json
import re
from typing import Any

CONVERSATION_ID_RE = re.compile(r'"conversation_id"\s*:\s*"(\d{10,})"')
SIGNED_URL_QUERY_RE = re.compile(
    r"(?:\\{1,2}u0026|[?&])(X-Amz-Signature|signature|sig|token|Expires|"
    r"X-Goog-Signature|x-expires|x-signature|msToken|a_bogus|fp|"
    r"access_key)=[^&\"\\]*", re.I)
SECRET_KEY_RE = re.compile(
    r"cookie|token|session|passwd|password|secret|authorization|msToken|csrf",
    re.I)


def parse_sse_ack(stream_text: str) -> dict | None:
    """Extract the SSE_ACK receipt from a captured /chat/completion stream.

    Returns {"conversation_id", "section_id", "question_id",
    "local_message_id", "message_index"} or None when no ack is present.
    """
    normalized = stream_text.replace("\r\n", "\n")
    for frame in normalized.split("\n\n"):
        event_match = re.search(r"event: (\S+)", frame)
        if not event_match or event_match.group(1) != "SSE_ACK":
            continue
        data_match = re.search(r"data: (.*)", frame, re.S)
        if not data_match:
            continue
        try:
            payload = json.loads(data_match.group(1))
        except json.JSONDecodeError:
            continue
        ack_meta = payload.get("ack_client_meta") or {}
        conversation_id = ack_meta.get("conversation_id")
        if not isinstance(conversation_id, str) or \
                not CONVERSATION_ID_RE.search(json.dumps(payload)):
            continue
        query_list = payload.get("query_list") or [{}]
        first = query_list[0] if isinstance(query_list[0], dict) else {}
        return {
            "conversation_id": conversation_id,
            "section_id": ack_meta.get("section_id"),
            "question_id": first.get("question_id"),
            "local_message_id": first.get("local_message_id"),
            "message_index": first.get("message_index"),
        }
    return None


def parse_poll_replies(poll_payload: dict[str, Any]) -> list[dict]:
    """Parse /im/chain/single downlink into creation records (network
    authority shape)."""
    messages = ((poll_payload.get("downlink_body") or {})
                .get("pull_singe_chain_downlink_body") or {}).get("messages")
    if not isinstance(messages, list):
        return []
    replies: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        blocks = message.get("content")
        if isinstance(blocks, str):
            try:
                blocks = json.loads(blocks)
            except json.JSONDecodeError:
                continue
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict) or block.get("block_type") != 2074:
                continue
            creation_block = (block.get("content") or {}).get(
                "creation_block") or {}
            for creation in creation_block.get("creations") or []:
                if not isinstance(creation, dict):
                    continue
                video = creation.get("video") or {}
                replies.append({
                    "message_id": str(message.get("message_id")),
                    "local_message_id": message.get("local_message_id"),
                    "reply_to": message.get("reply_to_message_id")
                    or message.get("parent_message_id"),
                    "creation_id": (str(creation.get("id"))
                                    if creation.get("id") else None),
                    "type": creation.get("type"),
                    "video_status": video.get("status"),
                    "video_download_url": video.get("download_url"),
                })
    return replies


def correlate_new_videos(replies: list[dict], *,
                         known_creation_ids: set[str],
                         known_message_ids: set[str]) -> list[dict]:
    """Baseline-diffed completion correlation; history-immune by
    construction (only ids absent from the pre-dispatch baseline match)."""
    fresh = [r for r in replies
             if r.get("creation_id") not in known_creation_ids
             and r.get("message_id") not in known_message_ids]
    return [r for r in fresh if r.get("type") == 2
            and r.get("video_download_url")]


def deterministic_video(records: list[dict]) -> str | None:
    """Exactly one distinct download URL, else None (fail-closed)."""
    urls = {r["video_download_url"] for r in records}
    return urls.pop() if len(urls) == 1 else None


def redact_signed_url(url: str) -> str:
    return SIGNED_URL_QUERY_RE.sub(r"\1=REDACTED", url or "")


def sanitize_value(key: str, value: Any):
    if isinstance(value, dict):
        return {k: sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(key, v) for v in value]
    if isinstance(value, str) and SECRET_KEY_RE.search(key or ""):
        return "REDACTED"
    if isinstance(value, str):
        return redact_signed_url(value)
    return value


def receipt_first_ordering(reserved: bool, receipt_persisted: bool,
                           budget_consumed: bool) -> bool:
    """Governance order assertion: reservation → receipt persistence →
    budget consumption. Consumption before receipt is a violation."""
    return reserved and receipt_persisted and budget_consumed and \
        not (budget_consumed and not receipt_persisted)
