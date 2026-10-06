"""AI-FILM-QUALITY-V2-010E — adapter delta: atomic journal wiring.

Extends the 010D delta (010C base untouched). The journal is appended
SYNCHRONOUSLY inside the CDP handlers:

    NETWORK_RELEASE_OBSERVED — the instant requestWillBeSent fires for the
                               /chat/completion POST carrying the prompt
    SSE_RECEIPT_CAPTURED     — the instant the captured stream body parses
                               an SSE_ACK beyond the pre-dispatch index
                               boundary (the /chat/completion stream closes
                               within seconds — proven in 010C — so the
                               parse happens immediately after the ACK,
                               independent of generation progress)
"""
from __future__ import annotations

import asyncio
import json

from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010c_contract import parse_sse_ack
from dola_010e_dispatch_journal import (DispatchJournal,
                                        NETWORK_RELEASE_OBSERVED,
                                        SSE_RECEIPT_CAPTURED,
                                        receipt_is_fresh)


class DolaBrowserAdapter010E(DolaBrowserAdapter010D):
    """010E delta: dispatch/receipt durability."""

    def attach_journal(self, journal: DispatchJournal, *,
                       expected_needle: str, index_boundary: int,
                       known_creation_ids: set[str],
                       on_receipt_captured=None) -> None:
        self._journal = journal
        self._needle = expected_needle
        self._index_boundary = index_boundary
        self._known_creations = set(known_creation_ids)
        self._on_receipt_captured = on_receipt_captured
        self._release_seen_for: set[str] = set()
        self._receipt_parsed: dict | None = None
        self.capture.subscribers.append(self._journal_subscriber)

    def _journal_subscriber(self, entry: dict) -> None:
        kind = entry.get("kind")
        if kind == "REQ" and entry.get("method") == "POST" and \
                "/chat/completion" in (entry.get("url") or ""):
            request_id = entry.get("request_id")
            if request_id in self._release_seen_for:
                return
            # exact-release verification is body-based; the URL+method+UTC
            # event is persisted NOW (synchronously), then refined
            self._release_seen_for.add(request_id)
            self._journal.append(NETWORK_RELEASE_OBSERVED, {
                "request_id": request_id,
                "request_utc": entry.get("utc"),
                "url_path": "/chat/completion",
                "verification": "body-needle refinement follows; this "
                                "record persists independently of SSE "
                                "parsing"})
            self.event("journal_release_observed", request_id=request_id)
        elif kind == "BODY" and self._receipt_parsed is None and \
                "completion" in (entry.get("url") or ""):
            body = entry.get("body")
            if not isinstance(body, str) or "SSE_ACK" not in body:
                return
            receipt = parse_sse_ack(body)
            if not receipt or not receipt_is_fresh(
                    receipt, self._index_boundary):
                return
            self._receipt_parsed = receipt
            import hashlib
            structural_hash = hashlib.sha256(json.dumps(
                receipt, sort_keys=True).encode("utf-8")).hexdigest()[:16]
            self._journal.append(SSE_RECEIPT_CAPTURED, {
                "conversation_id": receipt.get("conversation_id"),
                "question_id": receipt.get("question_id"),
                "local_message_id": receipt.get("local_message_id"),
                "message_index": receipt.get("message_index"),
                "section_id": receipt.get("section_id"),
                "index_boundary": self._index_boundary,
                "receipt_structural_hash": structural_hash})
            self.event("journal_receipt_captured",
                       question_id=receipt.get("question_id"),
                       message_index=receipt.get("message_index"))
            if self._on_receipt_captured:
                try:
                    self._on_receipt_captured(receipt)
                except Exception:
                    pass

    async def wait_journal_state(self, state: str, timeout_s: int) -> bool:
        from dola_010e_dispatch_journal import STATE_ORDER
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            current = self._journal.state
            if STATE_ORDER[current] >= STATE_ORDER[state] or \
                    (state == "RELEASE_OBSERVED" and
                     self._journal.has(NETWORK_RELEASE_OBSERVED)):
                return True
            await self.page.wait_for_timeout(500)
        return False

    async def verify_release_body(self, request_id: str) -> dict:
        """Refine the observed release: fetch the post body and confirm the
        needle + duration class; record the refined facts."""
        post_data = await self.capture.get_post_data(request_id)
        refined = {"request_id": request_id, "needle_present": False,
                   "duration": None}
        if post_data:
            refined["needle_present"] = self._needle[:20] in post_data
            try:
                body = json.loads(post_data)
                ability = body.get("chat_ability") or {}
                raw = ability.get("ability_param")
                if isinstance(raw, str):
                    raw = json.loads(raw)
                refined["duration"] = (raw or {}).get("duration")
            except (json.JSONDecodeError, ValueError):
                pass
        self._journal.append("NETWORK_RELEASE_OBSERVED", {
            "refinement_for": request_id, **refined})
        return refined
