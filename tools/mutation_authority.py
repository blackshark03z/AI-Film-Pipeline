"""Durable, mutation-latching Owner ambiguity authority (execution scope).

Frozen invariant (FLOW-SCENE-SCALE-003-R1):

    Once an OWNER_AMBIGUITY_GATE is raised during an execution scope,
    MUTATION_AUTHORITY = PERMANENTLY_LATCHED_OFF for the remainder of that
    execution/package.

Two independent dimensions:

    external_effect_knowledge: UNKNOWN → RESOLVED_NO_EFFECT
                               UNKNOWN → RESOLVED_EFFECT_IDENTIFIED
    mutation_authority:        OPEN → LATCHED_CLOSED   (terminal, one-way)

Read-only reconciliation may resolve KNOWLEDGE but can never re-open the
latch. Only a NEW Owner-authorized execution scope (package/run) may create
fresh mutation authority. The state is durable on disk (JSON, event history)
so the latch survives process/scene-runner/runtime restarts; process memory
is never the authority source.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate

AUTHORITY_OPEN = "OPEN"
AUTHORITY_LATCHED_CLOSED = "LATCHED_CLOSED"
KNOWLEDGE_UNKNOWN = "UNKNOWN"
KNOWLEDGE_RESOLVED_NO_EFFECT = "RESOLVED_NO_EFFECT"
KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED = "RESOLVED_EFFECT_IDENTIFIED"
STATE_VERSION = "mutation-authority-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MutationAuthority:
    """Durable per-scope mutation authority with one-way latching."""

    def __init__(self, scope_dir: Path, scope_id: str):
        self.scope_dir = Path(scope_dir)
        self.scope_id = scope_id
        self.path = self.scope_dir / "mutation_authority.json"
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("version") != STATE_VERSION:
                raise ValueError("mutation authority state version mismatch")
            if state.get("scope_id") != scope_id:
                raise ValueError("mutation authority scope mismatch")
            self._state = state
        else:
            self._state = {"version": STATE_VERSION, "scope_id": scope_id,
                           "created_at": utc_now(),
                           "mutation_authority": AUTHORITY_OPEN,
                           "external_effect_knowledge": KNOWLEDGE_UNKNOWN,
                           "events": []}
            self._save()

    @property
    def authority(self) -> str:
        return self._state["mutation_authority"]

    @property
    def knowledge(self) -> str:
        return self._state["external_effect_knowledge"]

    def _save(self) -> None:
        self.scope_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False),
            encoding="utf-8")

    def _event(self, kind: str, **data) -> None:
        self._state["events"].append({"kind": kind, "at": utc_now(), **data})
        self._save()

    def check_mutation_allowed(self, budget_kind: str) -> None:
        """Gate entry point for EVERY provider mutation path. Fail-closed."""
        if self.authority == AUTHORITY_LATCHED_CLOSED:
            raise OwnerAmbiguityGate(
                f"MUTATION_LATCHED_CLOSED: an OWNER_AMBIGUITY_GATE previously "
                f"latched this execution scope ({self.scope_id}); "
                f"{budget_kind} refused. Read-only reconciliation remains "
                f"allowed; fresh mutation requires a new Owner-authorized "
                f"execution scope.")

    def consume(self, budget_kind: str) -> None:
        """Record one authorized budget consumption (post-release)."""
        self.check_mutation_allowed(budget_kind)
        self._event("BUDGET_CONSUMED", budget_kind=budget_kind)

    def latch(self, kind: str, detail: str) -> dict:
        """Permanently latch mutation authority. Idempotent; one-way."""
        if self.authority == AUTHORITY_LATCHED_CLOSED:
            return {**self._state, "already_latched": True}
        self._state["mutation_authority"] = AUTHORITY_LATCHED_CLOSED
        self._event("OWNER_AMBIGUITY_GATE_LATCHED", gate_kind=kind,
                    detail=detail[:300])
        return {**self._state, "latched": True}

    def record_knowledge(self, state: str, detail: str = "") -> None:
        """Resolve external-effect knowledge. NEVER re-opens the latch."""
        if state not in (KNOWLEDGE_RESOLVED_NO_EFFECT,
                         KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
                         KNOWLEDGE_UNKNOWN):
            raise ValueError(f"unknown knowledge state {state}")
        previous = self._state["external_effect_knowledge"]
        self._state["external_effect_knowledge"] = state
        self._event("EXTERNAL_EFFECT_KNOWLEDGE", from_state=previous,
                    to_state=state, detail=detail[:300])

    def retroactive_latch(self, kind: str, detail: str) -> dict:
        """Custody record for a scope whose ambiguity predated the latch
        mechanism. History is annotated, never erased."""
        result = self.latch(kind, detail)
        self._event("RETROACTIVE_CUSTODY_LATCH",
                    detail="latch mechanism introduced after the historical "
                           "breach; recorded for custody, not a rewrite")
        return result
