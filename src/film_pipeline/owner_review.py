"""Owner review as a first-class immutable boundary (Package-015).

Three strictly separated authorities:

    REVIEW RECOMMENDATION   any reviewer (worker/backend/human) — advisory
                            documents with zero authority
    OWNER DECISION          the Owner; the ONLY source of a valid
                            OwnerReviewDecision
    PROVIDER MUTATION AUTHORITY  owned exclusively by fresh Tech Lead work
                            packages / execution scopes

The frozen chain is:

    review finding -> OwnerReviewDecision
                   -> future Tech Lead RepairDecision / fresh work package
                   -> provider mutation authority

An Owner decision NEVER triggers Generate by itself and never grants,
restores, or expands provider mutation authority. Worker or model output
can NEVER create an OwnerReviewDecision (schema + importer guards).
A decision bound to different artifact hashes fails closed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256

REQUEST_SCHEMA_VERSION = "owner-review-request-v1"
DECISION_SCHEMA_VERSION = "owner-review-decision-v1"
LEDGER_SCHEMA_VERSION = "owner-decision-ledger-v1"
TEMPLATE_SCHEMA_VERSION = "owner-decision-template-v1"
OWNER_DECISION_STATES = ("ACCEPT", "REJECT", "NEEDS_REPAIR", "DEFER")
# Markers that betray non-Owner (worker/model/harness) origin inside a
# decision payload. A decision carrying any of them is refused.
WORKER_ORIGIN_MARKERS = ("WORKER_REVIEW", "worker-semantic-reviewer",
                         "reviewer_identity", "packet_digest",
                         "harness_identity", "API_MODEL")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OwnerReviewRequest(ContractModel):
    """What the Owner is asked to review, with exact bindings.

    scope=SHOT binds one canonical shot (take + asset + range); scope=
    MASTER binds the canonical master itself (e.g. a master-level advisory
    item). All identity fields are exact; nothing is inferred.
    """
    schema_version: Literal["owner-review-request-v1"] = REQUEST_SCHEMA_VERSION
    review_request_id: str = Field(
        pattern=r"^OWNER-REV-[A-Z0-9][A-Z0-9-]{2,39}$")
    project: str = Field(min_length=1)
    scope: Literal["SHOT", "MASTER"]
    canonical_shot_id: str = ""
    sequence_id: str = ""
    scene_id: str = ""
    narrative_function: str = ""
    master_sha256: str = ""
    shot_spec_identity: dict = {}
    selected_take: str = ""
    asset_id: str = ""
    asset_sha256: str = ""
    provider_media_identity: str = ""
    reference_lineage: dict = {}
    editorial_range: dict = {}
    technical_qc: dict = {}
    advisory_semantic_review: dict = {}
    contact_sheet: dict = {}
    reel_locator: dict = {}
    reason_review_required: str = Field(min_length=1)
    created_at: str

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "SHOT":
            missing = [f for f in ("canonical_shot_id", "selected_take",
                                   "asset_sha256") if not getattr(self, f)]
            if missing or not self.shot_spec_identity:
                raise ValueError(
                    f"SHOT request missing identity fields: {missing}")
        else:
            if len(self.master_sha256) != 64:
                raise ValueError("MASTER request must bind the exact "
                                 "canonical master sha256")
        return self

    def bindings(self) -> dict[str, str]:
        """The exact artifact bindings a decision must carry verbatim."""
        pairs = {
            "asset_sha256": self.asset_sha256,
            "selected_take": self.selected_take,
            "editorial_range_id": (self.editorial_range or {}).get(
                "editorial_range_id", ""),
            "shot_spec_sha256": (self.shot_spec_identity or {}).get(
                "shot_spec_sha256", ""),
            "master_sha256": self.master_sha256,
        }
        return {k: v for k, v in pairs.items() if v}

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class OwnerReviewDecision(ContractModel):
    """An immutable Owner decision on exactly the reviewed artifacts.

    decision_source is OWNER by construction — worker/model output can
    never satisfy this schema through any legitimate surface.
    """
    schema_version: Literal["owner-review-decision-v1"] = \
        DECISION_SCHEMA_VERSION
    decision_id: str = Field(pattern=r"^OWNER-DEC-[a-f0-9]{16}$")
    review_request_id: str = Field(min_length=1)
    reviewed_bindings: dict[str, str]
    decision: str
    note: str = ""
    decided_at: str
    decision_source: Literal["OWNER"]
    owner_identity: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decision(self):
        if self.decision not in OWNER_DECISION_STATES:
            raise ValueError(f"invalid owner decision state {self.decision}")
        return self

    def payload_digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


def refuse_worker_origin(payload: dict) -> None:
    """Fail closed if a decision payload embeds worker/model provenance.

    Worker and model outputs are REVIEW RECOMMENDATIONS. If any of their
    provenance markers appear inside a would-be Owner decision, the
    payload was forged from machine output and is refused.
    """
    blob = canonical_json(payload)
    for marker in WORKER_ORIGIN_MARKERS:
        if marker in blob:
            raise ValueError(
                f"decision payload carries non-Owner origin marker "
                f"({marker}); worker/model output can never create an "
                f"OwnerReviewDecision")


def make_owner_decision(*, request: OwnerReviewRequest, decision: str,
                        owner_identity: str = "OWNER", note: str = "",
                        decided_at: str | None = None,
                        decision_id: str | None = None
                        ) -> OwnerReviewDecision:
    """The only legitimate way to mint a decision: Owner-chosen state on
    the request's exact bindings (hashes carried automatically — the Owner
    never re-types them)."""
    if owner_identity != "OWNER" and "worker" in owner_identity.lower():
        raise ValueError("non-Owner identity cannot mint a decision")
    payload = {"decision": decision, "owner_identity": owner_identity,
               "note": note}
    refuse_worker_origin(payload)
    basis = {"review_request_id": request.review_request_id,
             "bindings": request.bindings(), "decision": decision,
             "note": note, "owner_identity": owner_identity}
    minted = decision_id or ("OWNER-DEC-" +
                             sha256(canonical_json(basis))[:16])
    return OwnerReviewDecision(
        decision_id=minted, review_request_id=request.review_request_id,
        reviewed_bindings=request.bindings(), decision=decision, note=note,
        decided_at=decided_at or utc_now(), decision_source="OWNER",
        owner_identity=owner_identity)


class SupersessionRecord(ContractModel):
    """The ONLY way a second decision on one request can exist.

    Conflicting decisions without this explicit contract are refused; the
    superseded decision is never deleted — history stays immutable.
    """
    schema_version: Literal["owner-supersession-v1"] = "owner-supersession-v1"
    review_request_id: str
    superseded_decision_id: str
    superseding_decision_id: str
    reason: str = Field(min_length=1)
    decided_at: str
    decision_source: Literal["OWNER"]


class OwnerDecisionLedger:
    """Durable, tamper-checking ledger of Owner decisions.

    One ACTIVE decision per review request. A second decision requires an
    explicit SupersessionRecord. DEFER leaves the review unresolved.
    The ledger grants ZERO provider mutation authority — recording a
    decision never triggers generation and never mutates media.
    """

    def __init__(self, path: Path, requests: list[OwnerReviewRequest]):
        self.path = Path(path)
        self._requests = {r.review_request_id: r for r in requests}
        self._decisions: dict[str, list[OwnerReviewDecision]] = {}
        self._supersessions: list[SupersessionRecord] = []
        self._events: list[dict] = []
        if self.path.exists():
            self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        state = json.loads(self.path.read_text(encoding="utf-8"))
        if state.get("schema_version") != LEDGER_SCHEMA_VERSION:
            raise ValueError("owner decision ledger version mismatch")
        for raw in state.get("decisions", []):
            raw = dict(raw)
            recorded_digest = raw.pop("payload_sha256")
            decision = OwnerReviewDecision.model_validate(raw)
            self._verify_integrity(decision, recorded_digest)
            self._decisions.setdefault(decision.review_request_id,
                                       []).append(decision)
        self._supersessions = [SupersessionRecord.model_validate(s) for s in
                               state.get("supersessions", [])]
        self._events = state.get("events", [])

    def _verify_integrity(self, decision: OwnerReviewDecision,
                          recorded_digest: str) -> None:
        if decision.payload_digest() != recorded_digest:
            raise ValueError(
                f"decision {decision.decision_id} was modified after "
                f"recording (digest mismatch)")

    def save(self) -> None:
        state = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "decisions": [
                {**d.model_dump(mode="json"),
                 "payload_sha256": d.payload_digest()}
                for ds in self._decisions.values() for d in ds],
            "supersessions": [s.model_dump(mode="json")
                              for s in self._supersessions],
            "events": self._events,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=1, sort_keys=True),
                             encoding="utf-8")

    # -- recording ------------------------------------------------------
    def record(self, decision: OwnerReviewDecision) -> dict:
        request = self._requests.get(decision.review_request_id)
        if request is None:
            raise ValueError(
                f"unknown review request {decision.review_request_id}")
        refuse_worker_origin(decision.model_dump(mode="json"))
        if decision.reviewed_bindings != request.bindings():
            drifted = {k for k in set(decision.reviewed_bindings) |
                       set(request.bindings())
                       if decision.reviewed_bindings.get(k) !=
                       request.bindings().get(k)}
            raise ValueError(
                f"decision binds different artifacts than the review "
                f"request (stale binding: {sorted(drifted)}); refused")
        existing = self._decisions.get(decision.review_request_id, [])
        active = [d for d in existing
                  if not self._is_superseded(d.decision_id)]
        if any(d.decision_id == decision.decision_id for d in existing):
            raise ValueError(
                f"duplicate decision {decision.decision_id} refused "
                f"(decisions are immutable)")
        if active:
            raise ValueError(
                f"request already has active decision "
                f"{active[-1].decision_id}; a second decision requires "
                f"the explicit supersession contract")
        self._decisions.setdefault(decision.review_request_id,
                                   []).append(decision)
        self._events.append({
            "kind": "OWNER_DECISION_RECORDED",
            "decision_id": decision.decision_id,
            "review_request_id": decision.review_request_id,
            "decision": decision.decision,
            "at": decision.decided_at,
            "provider_mutation": "NONE (decision is a document; mutation "
                                 "requires a fresh Tech Lead work package)"})
        return {"recorded": decision.decision_id,
                "request": decision.review_request_id,
                "decision": decision.decision,
                "provider_mutation_authority": "NONE"}

    def supersede(self, *, superseded_decision_id: str,
                  new_decision: OwnerReviewDecision, reason: str
                  ) -> SupersessionRecord:
        old = self._find(superseded_decision_id)
        if old is None:
            raise ValueError("superseded decision not found")
        if old.review_request_id != new_decision.review_request_id:
            raise ValueError("supersession must target the same request")
        if self._is_superseded(superseded_decision_id):
            raise ValueError("decision already superseded")
        record = SupersessionRecord(
            review_request_id=new_decision.review_request_id,
            superseded_decision_id=superseded_decision_id,
            superseding_decision_id=new_decision.decision_id,
            reason=reason, decided_at=utc_now(), decision_source="OWNER")
        self._supersessions.append(record)
        try:
            self.record(new_decision)
        except Exception:
            self._supersessions.pop()  # no dangling supersession
            raise
        self._events.append({
            "kind": "OWNER_DECISION_SUPERSEDED",
            "superseded": superseded_decision_id,
            "superseding": new_decision.decision_id,
            "at": record.decided_at,
            "provider_mutation": "NONE"})
        return record

    # -- state ----------------------------------------------------------
    def _find(self, decision_id: str) -> OwnerReviewDecision | None:
        for ds in self._decisions.values():
            for d in ds:
                if d.decision_id == decision_id:
                    return d
        return None

    def _is_superseded(self, decision_id: str) -> bool:
        return any(s.superseded_decision_id == decision_id
                   for s in self._supersessions)

    def active_decision(self, review_request_id: str
                        ) -> OwnerReviewDecision | None:
        active = [d for d in self._decisions.get(review_request_id, [])
                  if not self._is_superseded(d.decision_id)]
        return active[-1] if active else None

    def resolved_state(self) -> dict[str, str]:
        out = {}
        for rid in self._requests:
            d = self.active_decision(rid)
            out[rid] = d.decision if d else "UNRESOLVED"
        return out

    def provider_mutation_authority(self) -> str:
        """Structural constant: decisions never carry mutation authority."""
        return "NONE"

    def release_blockers(self) -> list[str]:
        """Requests still blocking OWNER_TAKE_REVIEW_COMPLETE."""
        return sorted(rid for rid, state in self.resolved_state().items()
                      if state != "ACCEPT")


def build_decision_template(requests: list[OwnerReviewRequest], path: Path,
                            review_set_sha256: str) -> dict:
    """Human-fillable, machine-importable decision template.

    The immutable reviewed bindings are baked in; the Owner only chooses
    decision + optional note. decision: null until the Owner decides.
    """
    template = {
        "schema_version": TEMPLATE_SCHEMA_VERSION,
        "review_set_sha256": review_set_sha256,
        "decision_states": list(OWNER_DECISION_STATES),
        "instructions": "fill decision (one of decision_states) and an "
                        "optional note per item; do not edit any other "
                        "field — import fails closed on any drift",
        "items": [{
            "review_request_id": r.review_request_id,
            "shot_id": r.canonical_shot_id or "MASTER",
            "scope": r.scope,
            "reviewed_bindings": r.bindings(),
            "decision": None,
            "note": "",
        } for r in requests],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return template


def import_decision_set(decision_path: Path, requests:
                        list[OwnerReviewRequest], ledger: OwnerDecisionLedger,
                        current_review_set_sha256: str) -> dict:
    """Strict Owner decision import — fails closed on every drift.

    Refuses: malformed JSON, unknown/missing requests, edited bindings
    (stale asset/take), invalid states, duplicates, decisions forged from
    worker output, and a template built against a different review set.
    """
    try:
        payload = json.loads(Path(decision_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed decision file: {exc}") from exc
    if payload.get("schema_version") != TEMPLATE_SCHEMA_VERSION:
        raise ValueError("decision file is not an owner decision template")
    if payload.get("review_set_sha256") != current_review_set_sha256:
        raise ValueError(
            "decision file was built against a different review packet "
            "(review set hash mismatch); refused")
    by_id = {r.review_request_id: r for r in requests}
    seen: set[str] = set()
    imported = []
    for item in payload.get("items", []):
        rid = item.get("review_request_id")
        if rid not in by_id:
            raise ValueError(f"unknown review request {rid!r}")
        if rid in seen:
            raise ValueError(f"duplicate decision item for {rid}")
        seen.add(rid)
        request = by_id[rid]
        if item.get("reviewed_bindings") != request.bindings():
            raise ValueError(
                f"decision bindings drifted from the frozen review packet "
                f"for {rid} (stale asset/take/range); refused")
        refuse_worker_origin(item)
        state = item.get("decision")
        if state is None:
            continue  # untouched item — allowed; request stays unresolved
        if state not in OWNER_DECISION_STATES:
            raise ValueError(f"invalid decision state {state!r} for {rid}")
        decision = make_owner_decision(
            request=request, decision=state,
            owner_identity="OWNER", note=str(item.get("note", "")))
        ledger.record(decision)
        imported.append(decision)
    missing = sorted(set(by_id) - seen)
    if missing:
        raise ValueError(f"decision file is missing review requests: "
                         f"{missing}")
    ledger.save()  # imported decisions become durable immediately
    return {"imported": [d.decision_id for d in imported],
            "resolved_state": ledger.resolved_state(),
            "provider_mutation_authority":
                ledger.provider_mutation_authority()}
