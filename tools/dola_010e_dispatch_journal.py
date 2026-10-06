"""AI-FILM-QUALITY-V2-010E — atomic dispatch/receipt durability.

DispatchJournal: append-only, hash-chained, fsync-per-event JSONL journal
covering the dispatch state machine:

    RESERVED → DISPATCH_ARMED → RELEASE_OBSERVED → RECEIPT_CAPTURED
      → PROVIDER_JOB_BOUND → TERMINAL

Critical rule: a crash after UI release must never leave the system unable
to tell whether dispatch occurred. NETWORK_RELEASE_OBSERVED is appended
SYNCHRONOUSLY inside the CDP request handler (before any SSE parsing);
SSE_RECEIPT_CAPTURED is appended the moment the ACK structure is parsed —
never waiting for creation, download, shutdown, or evidence assembly.

This is a dispatch-level durability primitive BESIDE MutationAuthority (the
authority stays the single budget governor; the journal never re-opens or
grants mutations). Recovery never issues a new provider mutation.
"""
from __future__ import annotations

import hashlib
import re
import json
import os
from datetime import datetime, timezone
from pathlib import Path

RESERVED = "RESERVED"
DISPATCH_ARMED = "DISPATCH_ARMED"
RELEASE_OBSERVED = "RELEASE_OBSERVED"
RECEIPT_CAPTURED = "RECEIPT_CAPTURED"
PROVIDER_JOB_BOUND = "PROVIDER_JOB_BOUND"
TERMINAL = "TERMINAL"

EVENT_KINDS = (
    "MUTATION_RESERVED", "DISPATCH_ARMED", "NETWORK_RELEASE_OBSERVED",
    "SSE_RECEIPT_CAPTURED", "CREATION_BOUND", "ASSET_DOWNLOADED",
    "TERMINAL_SUCCESS", "TERMINAL_PROVIDER_FAILURE", "AMBIGUITY_LATCHED",
)
MUTATION_RESERVED = "MUTATION_RESERVED"
DISPATCH_ARMED_EV = "DISPATCH_ARMED"
NETWORK_RELEASE_OBSERVED = "NETWORK_RELEASE_OBSERVED"
SSE_RECEIPT_CAPTURED = "SSE_RECEIPT_CAPTURED"
CREATION_BOUND = "CREATION_BOUND"
ASSET_DOWNLOADED = "ASSET_DOWNLOADED"
TERMINAL_SUCCESS = "TERMINAL_SUCCESS"
TERMINAL_PROVIDER_FAILURE = "TERMINAL_PROVIDER_FAILURE"
AMBIGUITY_LATCHED = "AMBIGUITY_LATCHED"
KIND_TO_STATE = {
    "MUTATION_RESERVED": RESERVED,
    "DISPATCH_ARMED": DISPATCH_ARMED,
    "NETWORK_RELEASE_OBSERVED": RELEASE_OBSERVED,
    "SSE_RECEIPT_CAPTURED": RECEIPT_CAPTURED,
    "CREATION_BOUND": PROVIDER_JOB_BOUND,
    "ASSET_DOWNLOADED": PROVIDER_JOB_BOUND,  # download happens post-binding
    "TERMINAL_SUCCESS": TERMINAL,
    "TERMINAL_PROVIDER_FAILURE": TERMINAL,
    "AMBIGUITY_LATCHED": TERMINAL,
}
STATE_ORDER = {RESERVED: 0, DISPATCH_ARMED: 1, RELEASE_OBSERVED: 2,
               RECEIPT_CAPTURED: 3, PROVIDER_JOB_BOUND: 4, TERMINAL: 5}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(_sanitize_payload(payload), sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")
                          ).hexdigest()[:16]


_SECRET_KEY_RE = re.compile(
    r"cookie|token|session|passwd|password|secret|authorization|msToken|"
    r"csrf|a_bogus", re.I)


def _sanitize_payload(node):
    """Defense-in-depth: the journal is durable evidence — any secret-named
    key is REDACTED before it can touch disk."""
    if isinstance(node, dict):
        return {k: ("REDACTED" if _SECRET_KEY_RE.search(str(k))
                    else _sanitize_payload(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [_sanitize_payload(v) for v in node]
    if isinstance(node, str):
        return _SIGNED_URL_RE.sub(r"\1=REDACTED", node)
    return node


_SIGNED_URL_RE = re.compile(
    r"([?&])(msToken|a_bogus|fp|access_key|x-signature|x-expires)=[^&\"]*",
    re.I)


class JournalCorruption(RuntimeError):
    pass


class DispatchJournal:
    """Append-only dispatch journal (one file per generation attempt)."""

    def __init__(self, path: Path, generation_attempt_id: str) -> None:
        self.path = Path(path)
        self.generation_attempt_id = generation_attempt_id
        self.events: list[dict] = []
        self._load()

    # -- loading -------------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        previous_hash = ""
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    break  # torn tail write: ignore everything after it
                if event.get("previous_event_hash") != previous_hash:
                    break  # chain break: keep the verified prefix only
                previous_hash = event.get("event_hash", "")
                self.events.append(event)

    # -- appending (sync, fsync, crash-safe) ----------------------------------

    def append(self, kind: str, payload: dict | None = None) -> dict:
        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown journal kind {kind}")
        # duplicate/idempotent guard: the same kind may not repeat once the
        # state has reached or passed its own state
        kind_state = KIND_TO_STATE[kind]
        if STATE_ORDER[self.state] > STATE_ORDER[kind_state] or \
                (self.state == kind_state and kind != "TERMINAL_SUCCESS" and
                 any(e["kind"] == kind for e in self.events)):
            last_same = next((e for e in reversed(self.events)
                              if e["kind"] == kind), None)
            if last_same:
                return dict(last_same, duplicate_ignored=True)
        payload = payload or {}
        ordinal = (self.events[-1]["ordinal"] + 1) if self.events else 1
        event = {
            "event_id": "", "generation_attempt_id":
                self.generation_attempt_id,
            "kind": kind, "ordinal": ordinal, "timestamp": utcnow(),
            "payload": _sanitize_payload(payload),
            "payload_hash": _payload_hash(payload),
            "previous_event_hash": self.events[-1]["event_hash"]
            if self.events else "",
        }
        event["event_id"] = hashlib.sha256(
            f"{self.generation_attempt_id}|{kind}|{ordinal}|"
            f"{event['timestamp']}".encode()).hexdigest()[:16]
        event["event_hash"] = hashlib.sha256(json.dumps(
            {k: v for k, v in event.items() if k != "event_hash"},
            sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.events.append(event)
        return event

    # -- state / recovery ------------------------------------------------------

    @property
    def state(self) -> str:
        current = RESERVED
        for event in self.events:
            candidate = KIND_TO_STATE[event["kind"]]
            if STATE_ORDER[candidate] > STATE_ORDER[current]:
                current = candidate
        return current

    def has(self, kind: str) -> bool:
        return any(e["kind"] == kind for e in self.events)

    def last_of(self, kind: str) -> dict | None:
        return next((e for e in reversed(self.events)
                     if e["kind"] == kind), None)

    def recover(self, *, conversation_has_new_message: bool | None = None,
                known_creation_ids: set[str] | None = None) -> dict:
        """Crash-recovery plan for the current journal state.

        Boundaries: A before release, B after release/before ACK,
        C after ACK/before creation, D after creation/before download,
        E after download/before finalization. Recovery NEVER dispatches.
        """
        state = self.state
        if state == TERMINAL:
            return {"boundary": None, "state": state,
                    "action": "NONE_TERMINAL"}
        if state == PROVIDER_JOB_BOUND:
            if self.has("ASSET_DOWNLOADED"):
                return {"boundary": "E", "state": state,
                        "action": "VERIFY_LOCAL_SHA256_AND_FINALIZE"}
            return {"boundary": "D", "state": state,
                    "action": "RESUME_DOWNLOAD_BY_CREATION_IDENTITY"}
        if state == RECEIPT_CAPTURED:
            return {"boundary": "C", "state": state,
                    "action": "RESUME_POLL_BY_RECEIPT_IDENTITY"}
        if state == RELEASE_OBSERVED:
            return {"boundary": "B", "state": state,
                    "action": "AMBIGUITY_LATCH_THEN_READONLY_RECONCILE"}
        # RESERVED or DISPATCH_ARMED
        if conversation_has_new_message:
            # the Enter may have fired between journal writes: the
            # conversation is authority — treat as an unobserved release
            return {"boundary": "B", "state": state,
                    "action": "AMBIGUITY_LATCH_THEN_READONLY_RECONCILE",
                    "note": "unobserved release suspected (conversation has "
                            "a message beyond the armed boundary)"}
        return {"boundary": "A", "state": state,
                "action": "SAFE_UNSPENT_VERIFY_READONLY_BEFORE_ANY_RETRY"}


# ------------------------------------------------------------- pure checks --

def receipt_is_fresh(receipt: dict, index_boundary: int) -> bool:
    """The ACK's message_index must be strictly beyond the pre-dispatch
    boundary (stale/echo receipts are rejected)."""
    index = receipt.get("message_index")
    return isinstance(index, int) and index > index_boundary


def creation_linkage_ok(creation: dict, receipt: dict,
                        known_creation_ids: set[str]) -> bool:
    """A creation may only bind when it is new (not in the pre-dispatch
    baseline) AND its message identity links to the receipt's question
    (reply_to/local_message_id linkage or a fresh message id beyond the
    receipt). Gallery/history order is never consulted."""
    if creation.get("creation_id") in known_creation_ids:
        return False
    reply_to = creation.get("reply_to")
    if reply_to and receipt.get("question_id") and \
            str(reply_to) == str(receipt["question_id"]):
        return True
    message_index = creation.get("message_index")
    if isinstance(message_index, int) and receipt.get("message_index") \
            is not None and message_index >= receipt["message_index"]:
        return True
    return bool(creation.get("local_message_id")
                and creation.get("local_message_id")
                == receipt.get("local_message_id"))
