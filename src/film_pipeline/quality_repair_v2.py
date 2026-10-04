"""Quality-repair selection governance for the V2 hardening track
(Package QUALITY-V2-001, frozen on V1 remote revision 14ba281d12c15a5678a3f
e1b3f0242f577512e5f).

V1 truth is CLOSED and immutable: this module never rewrites a canonical
SelectedTake, EditManifest or master by itself, never generates video,
and never promotes a Package-017/018 candidate automatically. It freezes
the policy machinery that any FUTURE V2 quality-hardening experiment must
pass through before canonical film state may change:

  candidate (PROPOSED) -> technical validation -> quality review
    -> explicit Owner selection of the EXACT asset sha256
    -> deterministic promotion transaction (append-only, atomic)
    -> verified rebuild, with the predecessor retained for rollback.

Authority boundaries (frozen): workers/models produce evidence only;
automated QC can reject technical invalidity only; the Owner (and only
the Owner) selects, rejects or defers an exact candidate; providers are
never authority. No aggregate quality score exists anywhere in this
contract: one improvement can never silently compensate another
regression, and identity never regresses for meaning.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256, validate_contract
from .owner_review import OwnerReviewDecision, refuse_worker_origin, utc_now

GOVERNANCE_VERSION = "quality-repair-governance-v2-001"

QUALITY_V2_GOAL = ("improve film creative quality without weakening "
                   "V1 technical/provenance guarantees")
QUALITY_V2_CANONICAL_BASELINE = "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
# Frozen canonical master identity at the V1 close (canonical_no_change_019.json).
CANONICAL_MASTER_SHA256 = \
    "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"
V1_COMPLETION_RECEIPT = "AI_FILM_PIPELINE_V1_COMPLETION_019"
DEBT_REGISTRY_019 = ("projects/flow_v1_completion_quality_debt_freeze_019/"
                     "quality_debt_registry_019.json")
OWNER_DECISION_019 = ("projects/flow_v1_completion_quality_debt_freeze_019/"
                      "owner_quality_decision_019.json")

QUALITY_DIMENSIONS = (
    "NARRATIVE_LOGIC", "ACTION_CAUSALITY", "SHOT_DESIGN", "IDENTITY",
    "BODY_PROPORTION", "PERFORMANCE", "BLOCKING", "CAMERA",
    "TEMPORAL_MOTION", "EDITORIAL_FIT")

CANDIDATE_SCHEMA_VERSION = "quality-repair-candidate-v1"
CANDIDATE_STATES = ("PROPOSED", "TECHNICALLY_VALID", "QUALITY_REVIEW_READY",
                    "OWNER_SELECTED", "OWNER_REJECTED", "DEFERRED",
                    "SUPERSEDED")
OWNER_DECISION_STATES = ("OWNER_SELECTED", "OWNER_REJECTED", "DEFERRED")

REVIEW_SCHEMA_VERSION = "quality-review-receipt-v1"
REVIEW_VERDICTS = ("IMPROVED", "UNCHANGED", "REGRESSED", "INCONCLUSIVE",
                   "NOT_APPLICABLE")
SEVERITY_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
HARD_BLOCK_SEVERITIES = ("HIGH", "CRITICAL")

TRANSACTION_SCHEMA_VERSION = "quality-promotion-transaction-v1"

ADMISSION_SCHEMA_VERSION = "experiment-admission-receipt-v1"
ADMISSION_REQUIRED_FROM = "V2-002"

# Frozen custody rule inherited from the V1 track: an ambiguous
# external effect is never interpreted by the worker — it stops.
EXTERNAL_AMBIGUITY_RULE = "OWNER_AMBIGUITY_GATE"

# The ten frozen acceptance conditions. ALL TEN must pass; there is no
# weighting, no "best score wins", and no partial credit.
ACCEPTANCE_CONDITIONS = (
    ("C1_EXACT_CANDIDATE_IDENTITY",
     "exact candidate identity is proven (derived candidate_id, exact "
     "asset sha256, generation semantic identity)"),
    ("C2_TECHNICAL_QC_PASSES",
     "technical QC passes for the candidate asset"),
    ("C3_IDENTITY_WORLD_NO_REGRESSION",
     "identity/world continuity does not materially regress"),
    ("C4_TARGET_IMPROVEMENT_EVIDENCED",
     "the target quality defect shows evidence-supported improvement"),
    ("C5_NO_HIGHER_SEVERITY_NEW_DEFECT",
     "no higher-severity new defect is introduced; any regression must "
     "be explicitly Owner-acknowledged (identity regression is "
     "unconditionally blocking)"),
    ("C6_EDITORIAL_FIT_PROVEN",
     "editorial fit is proven (manifest binding + trim compatibility)"),
    ("C7_OWNER_SELECTS_EXACT_SHA",
     "Owner explicitly SELECTS the exact asset sha256 through an "
     "immutable Owner decision"),
    ("C8_APPEND_ONLY_RECORDING",
     "the replacement is recorded append-only"),
    ("C9_REBUILD_VERIFIED",
     "the rebuilt affected edit/master passes deterministic verification"),
    ("C10_ROLLBACK_TARGET_RETAINED",
     "the rollback target is retained (predecessor take/manifest/master "
     "bindings and predecessor asset bytes)"),
)
ACCEPTANCE_CONDITION_IDS = tuple(c[0] for c in ACCEPTANCE_CONDITIONS)

# Frozen decision rights. PROVIDER holds the empty permission set:
# provider/model output is never authority.
ROLE_PERMISSIONS = {
    "TECH_LEAD": frozenset({"DEFINE_EXPERIMENT", "FREEZE_ACCEPTANCE",
                            "VALIDATE_PROOF"}),
    "WORKER": frozenset({"EXECUTE_EXPERIMENT", "PRODUCE_EVIDENCE",
                         "PROPOSE_CANDIDATE"}),
    "AUTOMATED_QC": frozenset({"VALIDATE_TECHNICAL_CONFORMANCE",
                                "REJECT_TECHNICAL_INVALIDITY"}),
    "OWNER": frozenset({"SELECT_CANDIDATE", "REJECT_CANDIDATE",
                        "DEFER_CANDIDATE", "ACCEPT_KNOWN_QUALITY_DEBT"}),
    "PROVIDER": frozenset(),
}
# Canonical promotion is a PROCEDURE (the transaction below), never a
# role grant: no role may "promote" by action alone.
NON_GRANTABLE_ACTIONS = frozenset({"PROMOTE_CANDIDATE"})

_CANDIDATE_IDENTITY_BASIS_FIELDS = ("source_canonical_take", "affected_shot",
                                    "asset_sha256",
                                    "generation_semantic_identity")


def authorize(role: str, action: str) -> None:
    """Fail closed unless the role holds the action. Promotion is never
    grantable: it is the transaction procedure, not a permission."""
    if action in NON_GRANTABLE_ACTIONS:
        raise ValueError(
            f"{action} is not a grantable role action; canonical promotion "
            f"runs only through the quality promotion transaction")
    if role not in ROLE_PERMISSIONS:
        raise ValueError(f"unknown role {role!r}")
    if action not in ROLE_PERMISSIONS[role]:
        raise ValueError(
            f"role {role} is not authorized for {action} "
            f"(frozen decision rights)")


class QualityRepairCandidate(ContractModel):
    """An evidence-only candidate to replace one canonical SelectedTake.

    The candidate_id is derived from the immutable identity fields only,
    so state transitions never change a candidate's identity. A candidate
    NEVER becomes canonical by existing: canonicality changes only
    through an executed promotion transaction.
    """
    schema_version: Literal["quality-repair-candidate-v1"] = \
        CANDIDATE_SCHEMA_VERSION
    candidate_id: str = Field(pattern=r"^QRC-[a-f0-9]{16}$")
    source_canonical_take: str = Field(min_length=1)
    affected_shot: str = Field(min_length=1)
    repair_reason: str = Field(min_length=1)
    quality_debt_ids: list[str] = Field(default_factory=list)
    generation_semantic_identity: str = Field(min_length=1)
    asset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    technical_qc_receipt: dict = {}
    identity_receipt: dict = {}
    quality_review_receipt: dict = {}
    editorial_compatibility_receipt: dict = {}
    owner_decision_state: str = "PROPOSED"
    owner_decision_id: str = ""
    superseded_by: str = ""
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidate(self):
        if self.owner_decision_state not in CANDIDATE_STATES:
            raise ValueError(
                f"invalid candidate state {self.owner_decision_state}")
        if self.owner_decision_state in OWNER_DECISION_STATES and \
                not self.owner_decision_id:
            raise ValueError(
                f"state {self.owner_decision_state} requires a recorded "
                f"immutable Owner decision (owner_decision_id)")
        if self.owner_decision_state == "SUPERSEDED" and \
                not self.superseded_by:
            raise ValueError("SUPERSEDED requires superseded_by")
        validate_contract("quality_repair_candidate",
                          self.model_dump(mode="json"))
        basis = {f: getattr(self, f) for f in _CANDIDATE_IDENTITY_BASIS_FIELDS}
        expected = "QRC-" + sha256(basis)[:16]
        if self.candidate_id != expected:
            raise ValueError(
                f"candidate identity mismatch: expected {expected}")
        return self

    def payload_digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


def make_candidate(*, source_canonical_take: str, affected_shot: str,
                   repair_reason: str, asset_sha256: str,
                   generation_semantic_identity: str,
                   quality_debt_ids: list[str] | None = None,
                   created_at: str | None = None) -> QualityRepairCandidate:
    """Mint a PROPOSED candidate; the id derives from exact identity."""
    data = dict(source_canonical_take=source_canonical_take,
                affected_shot=affected_shot, repair_reason=repair_reason,
                asset_sha256=asset_sha256,
                generation_semantic_identity=generation_semantic_identity,
                quality_debt_ids=list(quality_debt_ids or []))
    candidate_id = "QRC-" + sha256(
        {f: data[f] for f in _CANDIDATE_IDENTITY_BASIS_FIELDS})[:16]
    return QualityRepairCandidate(candidate_id=candidate_id,
                                  created_at=created_at or utc_now(),
                                  **data)


def _transition(candidate: QualityRepairCandidate, to_state: str,
                **updates) -> QualityRepairCandidate:
    allowed = {
        "PROPOSED": {"TECHNICALLY_VALID"},
        "TECHNICALLY_VALID": {"QUALITY_REVIEW_READY"},
        "QUALITY_REVIEW_READY": set(OWNER_DECISION_STATES),
        "OWNER_SELECTED": {"SUPERSEDED"},
        "OWNER_REJECTED": set(),
        "DEFERRED": {"QUALITY_REVIEW_READY"},
        "SUPERSEDED": set(),
    }
    if to_state not in allowed[candidate.owner_decision_state]:
        raise ValueError(
            f"invalid candidate transition "
            f"{candidate.owner_decision_state} -> {to_state}")
    data = candidate.model_dump(mode="json")
    data["owner_decision_state"] = to_state
    data.update(updates)
    return QualityRepairCandidate.model_validate(data)


def validate_technical_receipt(receipt: dict,
                               candidate: QualityRepairCandidate) -> dict:
    """The technical QC receipt must be a passing report bound to the
    exact candidate asset."""
    required = {"decision", "qc_report_id", "asset_sha256"}
    missing = sorted(required - set(receipt))
    if missing:
        raise ValueError(f"technical receipt missing {missing}")
    if receipt["decision"] != "pass":
        raise ValueError("technical QC did not pass for the candidate")
    if receipt["asset_sha256"] != candidate.asset_sha256:
        raise ValueError("technical receipt binds a different asset sha256")
    return receipt


def record_technical_validation(candidate: QualityRepairCandidate,
                                technical_receipt: dict,
                                *, actor: str = "AUTOMATED_QC"
                                ) -> QualityRepairCandidate:
    """PROPOSED -> TECHNICALLY_VALID. Automated QC may also refuse
    technical invalidity; a refused candidate simply never advances."""
    authorize(actor, "VALIDATE_TECHNICAL_CONFORMANCE")
    validate_technical_receipt(technical_receipt, candidate)
    return _transition(candidate, "TECHNICALLY_VALID",
                       technical_qc_receipt=dict(technical_receipt))


def record_technical_refusal(candidate: QualityRepairCandidate,
                             refusal: dict, *, actor: str = "AUTOMATED_QC"
                             ) -> dict:
    """Automated QC rejects technical invalidity. The candidate stays
    PROPOSED with a refusal receipt; it can never advance."""
    authorize(actor, "REJECT_TECHNICAL_INVALIDITY")
    return {"candidate_id": candidate.candidate_id,
            "refusal": dict(refusal), "state_after": "PROPOSED",
            "advance_blocked": True}


class DimensionFinding(ContractModel):
    dimension: str
    verdict: str
    severity: str = "NONE"
    evidence: list[str] = Field(min_length=1)
    affected_time_range_s: tuple[float, float] | None = None
    note: str = ""

    @model_validator(mode="after")
    def validate_finding(self):
        if self.dimension not in QUALITY_DIMENSIONS:
            raise ValueError(f"unknown quality dimension {self.dimension}")
        if self.verdict not in REVIEW_VERDICTS:
            raise ValueError(f"invalid review verdict {self.verdict}")
        if self.severity not in SEVERITY_ORDER:
            raise ValueError(f"invalid severity {self.severity}")
        return self


class QualityReviewReceipt(ContractModel):
    """Structured per-dimension quality review of one candidate against
    one baseline asset. There is NO aggregate score: `no_aggregate_score`
    is structurally true, and trade-offs must stay visible to the Owner.
    """
    schema_version: Literal["quality-review-receipt-v1"] = \
        REVIEW_SCHEMA_VERSION
    review_id: str = Field(pattern=r"^qrr_[a-f0-9]{64}$")
    candidate_id: str = Field(min_length=1)
    baseline_asset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    target_defect_debt_ids: list[str] = Field(default_factory=list)
    target_dimensions: list[str] = Field(min_length=1)
    findings: list[DimensionFinding] = Field(min_length=10, max_length=10)
    review_source: str
    limitations: list[str] = Field(default_factory=list)
    no_aggregate_score: Literal[True] = True

    @model_validator(mode="after")
    def validate_receipt(self):
        if self.review_source not in ("OWNER", "ADVISORY_WORKER",
                                      "ADVISORY_AUTOMATED_QC"):
            raise ValueError(f"invalid review source {self.review_source}")
        seen: dict[str, DimensionFinding] = {}
        for finding in self.findings:
            if finding.dimension in seen:
                raise ValueError(
                    f"duplicate finding for {finding.dimension}")
            seen[finding.dimension] = finding
        missing = [d for d in QUALITY_DIMENSIONS if d not in seen]
        if missing:
            raise ValueError(f"review receipt missing dimensions: {missing}")
        for dim in self.target_dimensions:
            if dim not in QUALITY_DIMENSIONS:
                raise ValueError(f"unknown target dimension {dim}")
            if seen[dim].verdict != "IMPROVED":
                raise ValueError(
                    f"target dimension {dim} must be IMPROVED with "
                    f"evidence in its own review receipt")
        validate_contract("quality_review_receipt",
                          self.model_dump(mode="json"))
        basis = self.model_dump(mode="json", exclude={"review_id"})
        if self.review_id != "qrr_" + sha256(basis):
            raise ValueError("review receipt identity mismatch")
        return self

    # -- explicit trade-off surface (never an aggregate) -----------------
    def finding(self, dimension: str) -> DimensionFinding:
        for f in self.findings:
            if f.dimension == dimension:
                return f
        raise KeyError(dimension)

    def regressed(self) -> list[DimensionFinding]:
        return [f for f in self.findings if f.verdict == "REGRESSED"]

    def improved(self) -> list[DimensionFinding]:
        return [f for f in self.findings if f.verdict == "IMPROVED"]

    def tradeoff_summary(self) -> dict:
        """The exact view the Owner must see: every verdict, per
        dimension, with severity and evidence. No score is computed."""
        return {
            dim: {"verdict": f.verdict, "severity": f.severity,
                  "evidence": list(f.evidence)}
            for dim, f in ((d, self.finding(d)) for d in QUALITY_DIMENSIONS)}

    def hard_blocks(self) -> list[str]:
        """Regressions that NO Owner decision may accept. Identity never
        regresses for meaning (frozen track rule)."""
        blocks = []
        for f in self.regressed():
            if f.dimension == "IDENTITY":
                blocks.append(
                    f"IDENTITY_REGRESSED_UNACCEPTABLE: identity never "
                    f"regresses for meaning")
            elif f.severity in HARD_BLOCK_SEVERITIES:
                blocks.append(
                    f"{f.dimension}_REGRESSED_{f.severity}: higher-severity "
                    f"new defect")
        return blocks

    def soft_regressions(self) -> list[str]:
        return sorted(f.dimension for f in self.regressed()
                      if f.dimension != "IDENTITY"
                      and f.severity not in HARD_BLOCK_SEVERITIES)


def build_review_receipt(*, candidate: QualityRepairCandidate,
                         baseline_asset_sha256: str,
                         target_dimensions: list[str],
                         findings: list[dict],
                         review_source: str,
                         target_defect_debt_ids: list[str] | None = None,
                         limitations: list[str] | None = None) \
        -> QualityReviewReceipt:
    """Build a complete receipt: dimensions not explicitly reviewed are
    recorded as NOT_APPLICABLE (never silently omitted)."""
    supplied = {f["dimension"]: f for f in findings}
    complete: list[dict] = []
    for dim in QUALITY_DIMENSIONS:
        if dim in supplied:
            complete.append(dict(supplied[dim]))
        else:
            complete.append({"dimension": dim, "verdict": "NOT_APPLICABLE",
                             "severity": "NONE",
                             "evidence": ["not exercised by this repair"]})
    payload = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "candidate_id": candidate.candidate_id,
        "baseline_asset_sha256": baseline_asset_sha256,
        "target_defect_debt_ids": list(target_defect_debt_ids or []),
        "target_dimensions": list(target_dimensions),
        "findings": [DimensionFinding.model_validate(f).model_dump(mode="json")
                     for f in complete],
        "review_source": review_source,
        "limitations": list(limitations or []),
        "no_aggregate_score": True,
    }
    review_id = "qrr_" + sha256(payload)
    return QualityReviewReceipt(review_id=review_id, **payload)


def attach_quality_review(candidate: QualityRepairCandidate,
                          review: QualityReviewReceipt, *,
                          identity_receipt: dict | None = None,
                          editorial_compatibility_receipt: dict | None = None) \
        -> QualityRepairCandidate:
    """TECHNICALLY_VALID -> QUALITY_REVIEW_READY with the review bound."""
    if candidate.owner_decision_state != "TECHNICALLY_VALID":
        raise ValueError(
            "quality review requires a TECHNICALLY_VALID candidate")
    if review.candidate_id != candidate.candidate_id:
        raise ValueError("review receipt belongs to another candidate")
    if review.baseline_asset_sha256 == candidate.asset_sha256:
        raise ValueError(
            "review baseline must be the canonical asset, not the "
            "candidate asset")
    updates: dict[str, Any] = {
        "quality_review_receipt": review.model_dump(mode="json")}
    if identity_receipt is not None:
        updates["identity_receipt"] = dict(identity_receipt)
    if editorial_compatibility_receipt is not None:
        updates["editorial_compatibility_receipt"] = \
            dict(editorial_compatibility_receipt)
    return _transition(candidate, "QUALITY_REVIEW_READY", **updates)


def candidate_review(candidate: QualityRepairCandidate) \
        -> QualityReviewReceipt | None:
    raw = candidate.quality_review_receipt
    return QualityReviewReceipt.model_validate(raw) if raw else None


def apply_owner_decision(candidate: QualityRepairCandidate,
                         decision: OwnerReviewDecision) \
        -> QualityRepairCandidate:
    """The ONLY path to OWNER_SELECTED / OWNER_REJECTED / DEFERRED.

    Requires an immutable OwnerReviewDecision (decision_source is
    schema-locked to OWNER) that binds the EXACT candidate asset sha256.
    A candidate with any (soft) regression can only be selected when the
    Owner's note explicitly acknowledges that trade-off.
    """
    if candidate.owner_decision_state != "QUALITY_REVIEW_READY":
        raise ValueError(
            "Owner decision requires a QUALITY_REVIEW_READY candidate")
    if decision.owner_identity != "OWNER":
        raise ValueError(
            "only the Owner identity may decide a candidate; impersonation "
            "refused")
    refuse_worker_origin(decision.model_dump(mode="json"))
    binding = decision.reviewed_bindings.get("asset_sha256", "")
    if binding != candidate.asset_sha256:
        raise ValueError(
            "Owner decision must select the EXACT candidate asset sha256; "
            f"decision binds {binding!r}")
    mapping = {"ACCEPT": "OWNER_SELECTED", "REJECT": "OWNER_REJECTED",
               "DEFER": "DEFERRED"}
    if decision.decision not in mapping:
        raise ValueError(
            f"owner decision {decision.decision} cannot close a candidate "
            f"review; route it through a fresh Tech Lead package")
    to_state = mapping[decision.decision]
    updates: dict[str, Any] = {"owner_decision_id": decision.decision_id}
    if to_state == "OWNER_SELECTED":
        review = candidate_review(candidate)
        if review is None:
            raise ValueError("selection requires the attached review")
        hard = review.hard_blocks()
        if hard:
            raise ValueError(
                "candidate cannot be selected: " + "; ".join(hard))
        soft = review.soft_regressions()
        if soft:
            ack = "TRADEOFF_ACCEPTED=" + ",".join(soft)
            if ack not in decision.note:
                raise ValueError(
                    f"Owner selection must explicitly acknowledge the "
                    f"trade-offs; note must contain {ack!r}")
    return _transition(candidate, to_state, **updates)


def mark_superseded(candidate: QualityRepairCandidate,
                    by_candidate_id: str) -> QualityRepairCandidate:
    if candidate.owner_decision_state != "OWNER_SELECTED":
        raise ValueError("only an OWNER_SELECTED candidate can be superseded")
    if by_candidate_id == candidate.candidate_id:
        raise ValueError("a candidate cannot supersede itself")
    return _transition(candidate, "SUPERSEDED", superseded_by=by_candidate_id)


def validate_identity_receipt(receipt: dict,
                              review: QualityReviewReceipt) -> dict:
    """Identity/world continuity must be PROVEN unchanged or improved:
    REGRESSED is unconditionally blocking and INCONCLUSIVE means the
    no-regression guarantee is unproven (fail closed)."""
    required = {"identity_continuity", "verified_by"}
    missing = sorted(required - set(receipt))
    if missing:
        raise ValueError(f"identity receipt missing {missing}")
    if receipt["identity_continuity"] not in ("UNCHANGED", "IMPROVED"):
        raise ValueError(
            "identity/world continuity not proven: "
            f"{receipt['identity_continuity']} (REGRESSED is "
            f"unconditionally blocking, INCONCLUSIVE is unproven)")
    if review.finding("IDENTITY").verdict == "REGRESSED":
        raise ValueError("identity/world continuity materially regressed")
    return receipt


def validate_editorial_receipt(receipt: dict) -> dict:
    required = {"editorial_compatible", "edit_manifest_id",
                "affected_clip_order", "trim_compatible", "verified_by"}
    missing = sorted(required - set(receipt))
    if missing:
        raise ValueError(f"editorial receipt missing {missing}")
    if receipt["editorial_compatible"] is not True or \
            receipt["trim_compatible"] is not True:
        raise ValueError("editorial fit is not proven for the candidate")
    return receipt


def evaluate_acceptance(candidate: QualityRepairCandidate, *,
                        owner_decision: OwnerReviewDecision | None = None,
                        promotion_ledger: "HashChainLedger | None" = None,
                        environment: "PromotionEnvironment | None" = None,
                        transaction: "PromotionTransaction | None" = None,
                        rebuild_receipt: dict | None = None) -> dict:
    """Deterministic 10-condition checklist. Conditions whose evidence
    only exists at transaction time are PENDING until then; a promotion
    requires all ten PASS — no weighting, no compensation."""
    results: dict[str, dict] = {}

    def fail(cid: str, detail: str):
        results[cid] = {"condition": dict(ACCEPTANCE_CONDITIONS)[cid],
                        "state": "FAIL", "detail": detail}

    def pending(cid: str, detail: str):
        results[cid] = {"condition": dict(ACCEPTANCE_CONDITIONS)[cid],
                        "state": "PENDING", "detail": detail}

    def nil(cid: str, detail: str = "proven"):
        results[cid] = {"condition": dict(ACCEPTANCE_CONDITIONS)[cid],
                        "state": "PASS", "detail": detail}

    # C1 — identity is re-derived structurally by the model validator.
    nil("C1_EXACT_CANDIDATE_IDENTITY",
        f"candidate_id {candidate.candidate_id} derived from exact identity "
        f"basis; asset {candidate.asset_sha256[:12]}…")
    # C2 — technical QC.
    try:
        validate_technical_receipt(candidate.technical_qc_receipt, candidate)
        nil("C2_TECHNICAL_QC_PASSES",
            candidate.technical_qc_receipt.get("qc_report_id", ""))
    except ValueError as exc:
        fail("C2_TECHNICAL_QC_PASSES", str(exc))
    # C3/C4/C5 — the review receipt.
    review = candidate_review(candidate)
    if review is None:
        fail("C3_IDENTITY_WORLD_NO_REGRESSION", "no review receipt attached")
        fail("C4_TARGET_IMPROVEMENT_EVIDENCED", "no review receipt attached")
        fail("C5_NO_HIGHER_SEVERITY_NEW_DEFECT", "no review receipt attached")
    else:
        try:
            identity = candidate.identity_receipt
            if not identity:
                raise ValueError("identity receipt not attached")
            validate_identity_receipt(identity, review)
            nil("C3_IDENTITY_WORLD_NO_REGRESSION",
                f"identity_continuity={identity['identity_continuity']}")
        except ValueError as exc:
            fail("C3_IDENTITY_WORLD_NO_REGRESSION", str(exc))
        targets_ok = all(
            review.finding(d).verdict == "IMPROVED" and
            review.finding(d).evidence
            for d in review.target_dimensions)
        (nil if targets_ok else fail)(
            "C4_TARGET_IMPROVEMENT_EVIDENCED",
            f"target dimensions {review.target_dimensions} IMPROVED with "
            f"evidence" if targets_ok else
            "a target dimension lacks an evidence-supported improvement")
        hard = review.hard_blocks()
        soft = review.soft_regressions()
        if hard:
            fail("C5_NO_HIGHER_SEVERITY_NEW_DEFECT", "; ".join(hard))
        elif soft and not (owner_decision and
                           "TRADEOFF_ACCEPTED=" + ",".join(soft)
                           in owner_decision.note):
            fail("C5_NO_HIGHER_SEVERITY_NEW_DEFECT",
                 f"soft regressions {soft} require an explicit Owner "
                 f"trade-off acknowledgment")
        else:
            nil("C5_NO_HIGHER_SEVERITY_NEW_DEFECT",
                "no unacknowledged regression")
    # C6 — editorial fit.
    try:
        validate_editorial_receipt(candidate.editorial_compatibility_receipt)
        nil("C6_EDITORIAL_FIT_PROVEN",
            f"manifest {candidate.editorial_compatibility_receipt.get('edit_manifest_id', '')}")
    except ValueError as exc:
        fail("C6_EDITORIAL_FIT_PROVEN", str(exc))
    # C7 — explicit Owner selection of the exact sha.
    if candidate.owner_decision_state == "OWNER_SELECTED" and \
            candidate.owner_decision_id:
        if owner_decision is not None:
            if owner_decision.decision != "ACCEPT" or \
                    owner_decision.reviewed_bindings.get("asset_sha256") != \
                    candidate.asset_sha256:
                fail("C7_OWNER_SELECTS_EXACT_SHA",
                     "owner decision does not select this exact asset sha")
            else:
                nil("C7_OWNER_SELECTS_EXACT_SHA",
                    f"decision {owner_decision.decision_id} selects "
                    f"{candidate.asset_sha256[:12]}…")
        else:
            pending("C7_OWNER_SELECTS_EXACT_SHA",
                    "owner decision receipt required at execution time")
    else:
        fail("C7_OWNER_SELECTS_EXACT_SHA",
             f"candidate state is {candidate.owner_decision_state}, not "
             f"OWNER_SELECTED")
    # C8 — append-only recording.
    if promotion_ledger is None:
        pending("C8_APPEND_ONLY_RECORDING",
                "promotion ledger required at execution time")
    elif promotion_ledger.append_only:
        nil("C8_APPEND_ONLY_RECORDING",
            "hash-chained append-only promotion ledger")
    else:
        fail("C8_APPEND_ONLY_RECORDING", "ledger is not append-only")
    # C9/C10 — transaction-time conditions.
    if transaction is None or environment is None:
        pending("C9_REBUILD_VERIFIED", "evaluated during the transaction")
        pending("C10_ROLLBACK_TARGET_RETAINED",
                "evaluated during the transaction")
    else:
        if rebuild_receipt is None:
            fail("C9_REBUILD_VERIFIED", "no rebuild receipt")
        else:
            nil("C9_REBUILD_VERIFIED",
                f"rebuilt master {rebuild_receipt.get('master_sha256', '')[:12]}…")
        if environment.asset_retained(transaction.predecessor.asset_sha256):
            nil("C10_ROLLBACK_TARGET_RETAINED",
                "predecessor take/manifest/master bindings recorded and "
                "predecessor bytes retained")
        else:
            fail("C10_ROLLBACK_TARGET_RETAINED",
                 "predecessor asset bytes missing; no rollback target")
    blocked = sorted(cid for cid, r in results.items() if r["state"] == "FAIL")
    return {"conditions": results, "all_pass": not blocked,
            "blocked_by": blocked}


# ---------------------------------------------------------------------------
# Promotion transaction (atomic at authority level) + rollback
# ---------------------------------------------------------------------------

class PredecessorBinding(ContractModel):
    selected_take_id: str = Field(min_length=1)
    shot_id: str = Field(min_length=1)
    asset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    edit_manifest_id: str = Field(min_length=1)
    master_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PromotionTransaction(ContractModel):
    schema_version: Literal["quality-promotion-transaction-v1"] = \
        TRANSACTION_SCHEMA_VERSION
    transaction_id: str = Field(pattern=r"^QPT-[a-f0-9]{16}$")
    candidate_id: str = Field(pattern=r"^QRC-[a-f0-9]{16}$")
    candidate_asset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    affected_shot_id: str = Field(min_length=1)
    affected_clip_order: int = Field(ge=1)
    predecessor: PredecessorBinding
    successor_manifest_id: str = Field(min_length=1)
    promotion_scope: dict = {}
    state: Literal["PROPOSED", "COMMITTED", "FAILED", "ROLLED_BACK"] = \
        "PROPOSED"
    promotion_receipt: dict = {}
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_transaction(self):
        validate_contract("quality_promotion_transaction",
                          self.model_dump(mode="json"))
        basis = {"candidate_id": self.candidate_id,
                 "candidate_asset_sha256": self.candidate_asset_sha256,
                 "affected_shot_id": self.affected_shot_id,
                 "affected_clip_order": self.affected_clip_order,
                 "predecessor": self.predecessor.model_dump(mode="json")}
        expected = "QPT-" + sha256(basis)[:16]
        if self.transaction_id != expected:
            raise ValueError(
                f"transaction identity mismatch: expected {expected}")
        return self

    def with_state(self, state: str, receipt: dict | None = None) \
            -> "PromotionTransaction":
        data = self.model_dump(mode="json")
        data["state"] = state
        if receipt is not None:
            data["promotion_receipt"] = receipt
        return PromotionTransaction.model_validate(data)


def build_successor_manifest(predecessor_manifest: dict,
                             transaction: PromotionTransaction,
                             *, candidate_take_id: str,
                             candidate_asset_id: str) -> dict:
    """Deterministic successor manifest: ONLY the affected clip changes;
    every other clip is byte-identical (rebuild only the affected
    editorial scope where possible)."""
    clips = [dict(c) for c in predecessor_manifest["clips"]]
    order = transaction.affected_clip_order
    targets = [c for c in clips if c["order"] == order]
    if len(targets) != 1:
        raise ValueError(f"affected clip order {order} not in predecessor "
                         f"manifest")
    if targets[0]["shot_id"] != transaction.affected_shot_id:
        raise ValueError("affected clip belongs to a different shot")
    targets[0]["selected_take_id"] = candidate_take_id
    targets[0]["asset_id"] = candidate_asset_id
    basis = {"version": "editmanifest-v1",
             "project_id": predecessor_manifest["project_id"],
             "clips": clips}
    return {"edit_manifest_id": "edit_" + sha256(basis),
            "project_id": predecessor_manifest["project_id"],
            "clips": clips}


class PromotionEnvironment:
    """Structural surface the transaction operates on. Implementations
    expose the current canonical manifest id (current_manifest_id) and
    resolve canonical takes by id (selected_take). A real canonical
    adapter wraps QCStore/EditorialStore in a later package; this
    package ships the synthetic reference implementation used for the
    proof (zero live canonical mutation)."""
    current_manifest_id: str

    def canonical_master_sha256(self) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def manifest(self, manifest_id: str) -> dict:  # pragma: no cover
        raise NotImplementedError

    def selected_take(self, selected_take_id: str) -> dict:  # pragma: no cover
        raise NotImplementedError

    def asset_retained(self, asset_sha256: str) -> bool:  # pragma: no cover
        raise NotImplementedError

    def preview_rebuild(self, manifest_payload: dict) -> dict:  # pragma: no cover
        raise NotImplementedError

    def commit(self, **_kw) -> None:  # pragma: no cover
        raise NotImplementedError

    def canonical_state_digest(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def rollback_to_predecessor(self, predecessor: PredecessorBinding) -> None:
        raise NotImplementedError


class SyntheticFilmEnvironment(PromotionEnvironment):
    """In-memory reference environment for the synthetic fixture proof.

    Deterministic rebuild: the master digest is a pure function of the
    successor manifest id and the sorted set of resolved clip asset
    digests. Commit is all-or-nothing; rollback restores the exact
    predecessor without any regeneration (the predecessor asset bytes
    are retained, never re-created).
    """

    def __init__(self, *, master_version: str, manifest: dict,
                 takes: dict[str, dict], asset_digests: dict[str, str]):
        self.master_version = master_version
        self._initial_master_sha = self._master_digest(manifest)
        self.manifests = {manifest["edit_manifest_id"]: json.loads(
            canonical_json(manifest))}
        self.takes = dict(takes)
        self.asset_digests = dict(asset_digests)
        self.current_manifest_id = manifest["edit_manifest_id"]
        self.commits: list[dict] = []
        self.rollbacks: list[dict] = []

    def _master_digest(self, manifest_payload: dict) -> str:
        asset_ids = sorted(c["asset_id"] for c in manifest_payload["clips"])
        return sha256({"version": self.master_version,
                       "manifest_id": manifest_payload["edit_manifest_id"],
                       "asset_ids": asset_ids})

    def canonical_master_sha256(self) -> str:
        return self._master_digest(self.manifests[self.current_manifest_id])

    def manifest(self, manifest_id: str) -> dict:
        if manifest_id not in self.manifests:
            raise ValueError(f"unknown manifest {manifest_id}")
        return json.loads(canonical_json(self.manifests[manifest_id]))

    def selected_take(self, selected_take_id: str) -> dict:
        if selected_take_id not in self.takes:
            raise ValueError(f"unknown selected take {selected_take_id}")
        return dict(self.takes[selected_take_id])

    def asset_retained(self, asset_sha256: str) -> bool:
        return asset_sha256 in set(self.asset_digests.values())

    def preview_rebuild(self, manifest_payload: dict) -> dict:
        master_sha = self._master_digest(manifest_payload)
        return {"master_sha256": master_sha,
                "edit_manifest_id": manifest_payload["edit_manifest_id"],
                "rebuild_scope": "AFFECTED_CLIP",
                "deterministic": True}

    def commit(self, *, new_take: dict, manifest_payload: dict,
               rebuild_receipt: dict, predecessor_master_sha256: str) -> None:
        if self.canonical_master_sha256() != predecessor_master_sha256:
            raise ValueError("canonical master moved; refusing stale commit")
        # staged: nothing below may partially apply; any exception before
        # the final assignment leaves canonical state untouched.
        staged_manifests = dict(self.manifests)
        staged_takes = dict(self.takes)
        staged_manifests[manifest_payload["edit_manifest_id"]] = \
            json.loads(canonical_json(manifest_payload))
        staged_takes[new_take["selected_take_id"]] = dict(new_take)
        if rebuild_receipt["master_sha256"] != \
                self._master_digest(manifest_payload):
            raise ValueError("rebuild receipt does not match the successor")
        self.manifests = staged_manifests
        self.takes = staged_takes
        self.current_manifest_id = manifest_payload["edit_manifest_id"]
        self.commits.append({"manifest_id":
                             manifest_payload["edit_manifest_id"]})

    def canonical_state_digest(self) -> str:
        return sha256({"master": self.canonical_master_sha256(),
                       "manifest_id": self.current_manifest_id,
                       "takes": sorted(self.takes)})

    def rollback_to_predecessor(self, predecessor: PredecessorBinding) -> None:
        if predecessor.edit_manifest_id not in self.manifests:
            raise ValueError("predecessor manifest missing; rollback "
                             "refused")
        self.current_manifest_id = predecessor.edit_manifest_id
        self.rollbacks.append({"restored_master":
                               self.canonical_master_sha256()})


class FaultInjectionEnvironment(SyntheticFilmEnvironment):
    """Simulates a rebuild failure and a partial write torn down by the
    atomic-commit guard (no mixed canonical state may ever be observed)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.fail_commit = False
        self.partial_write_then_fail = False

    def commit(self, **kw) -> None:
        if self.fail_commit:
            raise RuntimeError("simulated rebuild/commit failure")
        if self.partial_write_then_fail:
            try:
                self.takes[kw["new_take"]["selected_take_id"]] = \
                    dict(kw["new_take"])
                raise RuntimeError(
                    "simulated partial write; atomic guard restores prior "
                    "state")
            finally:
                self.takes.pop(kw["new_take"]["selected_take_id"], None)
        super().commit(**kw)


class HashChainLedger:
    """Append-only, hash-chained event ledger (tamper-checking). Events
    are never rewritten or removed; each event commits to the previous
    event's digest. `append_only` is a structural constant consumed by
    acceptance condition C8."""

    def __init__(self, path: Path | None = None, kind: str = "events"):
        self.path = Path(path) if path else None
        self.kind = kind
        self.append_only = True
        self.events: list[dict] = []
        if self.path and self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("kind") != kind:
                raise ValueError("ledger kind mismatch")
            self.events = state.get("events", [])
            self.verify()

    def append(self, kind: str, payload: dict) -> dict:
        prev = self.events[-1]["event_sha256"] if self.events else ""
        event = {"seq": len(self.events) + 1, "kind": kind,
                 "prev_event_sha256": prev, **payload}
        event["event_sha256"] = sha256(
            {k: v for k, v in event.items() if k != "event_sha256"})
        self.events.append(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(
                {"kind": self.kind, "events": self.events}, indent=1,
                sort_keys=True), encoding="utf-8")
        return event

    def verify(self) -> None:
        prev = ""
        for event in self.events:
            recorded = event.get("event_sha256", "")
            recomputed = sha256(
                {k: v for k, v in event.items() if k != "event_sha256"})
            if event.get("prev_event_sha256", "") != prev or \
                    recorded != recomputed:
                raise ValueError(
                    f"{self.kind} ledger integrity failure at seq "
                    f"{event.get('seq')}")
            prev = recorded

    def last_of_kind(self, kind: str) -> dict | None:
        for event in reversed(self.events):
            if event["kind"] == kind:
                return event
        return None


def propose_promotion_transaction(*, candidate: QualityRepairCandidate,
                                  environment: PromotionEnvironment,
                                  affected_clip_order: int,
                                  master_version: str = "master-v1") \
        -> PromotionTransaction:
    """Open a PROPOSED transaction against the CURRENT canonical state.
    The predecessor is read from the CURRENT EditManifest (the canonical
    intent), not from take history. Refuses if the candidate does not
    bind the present predecessor (wrong/stale canonical predecessor,
    stale EditManifest)."""
    predecessor_manifest = environment.manifest(
        environment.current_manifest_id)
    clips_for_shot = [c for c in predecessor_manifest["clips"]
                      if c["shot_id"] == candidate.affected_shot]
    if len(clips_for_shot) != 1:
        raise ValueError(
            f"expected exactly one canonical clip for "
            f"{candidate.affected_shot}")
    current_take = environment.selected_take(
        clips_for_shot[0]["selected_take_id"])
    if current_take["selected_take_id"] != candidate.source_canonical_take:
        raise ValueError(
            "candidate does not bind the current canonical predecessor")
    predecessor = PredecessorBinding(
        selected_take_id=current_take["selected_take_id"],
        shot_id=candidate.affected_shot,
        asset_sha256=current_take["asset_sha256"],
        edit_manifest_id=predecessor_manifest["edit_manifest_id"],
        master_sha256=environment.canonical_master_sha256())
    # The transaction id is a pure function of candidate + predecessor +
    # clip order, so a scaffold can mint it before the successor manifest
    # id is computed (the id basis excludes the successor id).
    scaffold = _scaffold_transaction(candidate, predecessor,
                                     affected_clip_order)
    successor = build_successor_manifest(
        predecessor_manifest, scaffold,
        candidate_take_id=_candidate_take_id(candidate),
        candidate_asset_id=_candidate_asset_id(candidate))
    return PromotionTransaction(
        transaction_id=scaffold.transaction_id,
        candidate_id=candidate.candidate_id,
        candidate_asset_sha256=candidate.asset_sha256,
        affected_shot_id=candidate.affected_shot,
        affected_clip_order=affected_clip_order,
        predecessor=predecessor,
        successor_manifest_id=successor["edit_manifest_id"],
        promotion_scope={"strategy": "AFFECTED_CLIP_ONLY",
                         "affected_clip_order": affected_clip_order},
        created_at=scaffold.created_at)


def _scaffold_transaction(candidate: QualityRepairCandidate,
                          predecessor: PredecessorBinding,
                          affected_clip_order: int) \
        -> PromotionTransaction:
    basis = {"candidate_id": candidate.candidate_id,
             "candidate_asset_sha256": candidate.asset_sha256,
             "affected_shot_id": candidate.affected_shot,
             "affected_clip_order": affected_clip_order,
             "predecessor": predecessor.model_dump(mode="json")}
    return PromotionTransaction(
        transaction_id="QPT-" + sha256(basis)[:16],
        candidate_id=candidate.candidate_id,
        candidate_asset_sha256=candidate.asset_sha256,
        affected_shot_id=candidate.affected_shot,
        affected_clip_order=affected_clip_order, predecessor=predecessor,
        successor_manifest_id="pending", created_at=utc_now())


def _candidate_take_id(candidate: QualityRepairCandidate) -> str:
    return "take_" + sha256({"candidate": candidate.candidate_id,
                             "asset": candidate.asset_sha256})


def _candidate_asset_id(candidate: QualityRepairCandidate) -> str:
    return "asset_" + sha256({"asset": candidate.asset_sha256})[:16]


def _ledger_contains(ledger: HashChainLedger, kind: str,
                     match) -> bool:
    return any(event["kind"] == kind and match(event)
               for event in ledger.events)


def execute_promotion(transaction: PromotionTransaction, *,
                      candidate: QualityRepairCandidate,
                      environment: PromotionEnvironment,
                      promotion_ledger: HashChainLedger,
                      owner_decision: OwnerReviewDecision) -> dict:
    """Deterministic promotion. Either the canonical authority moves to
    the candidate as ONE atomic step with a receipt, or it stays exactly
    on the old take. Any failure leaves zero mixed canonical state."""
    if transaction.state != "PROPOSED":
        raise ValueError(
            f"transaction {transaction.transaction_id} is "
            f"{transaction.state}; only PROPOSED may execute")
    if _ledger_contains(promotion_ledger, "PROMOTION_COMMITTED",
                        lambda e: e.get("receipt", {}).get(
                            "transaction_id") == transaction.transaction_id):
        raise ValueError(
            f"transaction {transaction.transaction_id} already committed "
            f"(append-only ledger)")
    if _ledger_contains(promotion_ledger, "PROMOTION_FAILED",
                        lambda e: e.get("transaction_id") ==
                        transaction.transaction_id):
        raise ValueError(
            f"blind retry refused: transaction {transaction.transaction_id} "
            f"already failed once; a fresh proposal and fresh authority "
            f"are required")
    if not environment.asset_retained(candidate.asset_sha256):
        raise ValueError(
            "candidate asset bytes are not retained in the environment; "
            "identity cannot be proven at promotion time")
    digest_before = environment.canonical_state_digest()
    predecessor_manifest = environment.manifest(
        transaction.predecessor.edit_manifest_id)
    if environment.canonical_master_sha256() != \
            transaction.predecessor.master_sha256:
        raise ValueError(
            "wrong canonical predecessor: environment master does not "
            "match the transaction binding")
    if environment.current_manifest_id != \
            transaction.predecessor.edit_manifest_id:
        raise ValueError("stale EditManifest: canonical manifest moved")
    successor = build_successor_manifest(
        predecessor_manifest, transaction,
        candidate_take_id=_candidate_take_id(candidate),
        candidate_asset_id=_candidate_asset_id(candidate))
    if successor["edit_manifest_id"] != transaction.successor_manifest_id:
        raise ValueError("successor manifest identity mismatch")
    editorial = candidate.editorial_compatibility_receipt
    if editorial.get("edit_manifest_id") and \
            editorial["edit_manifest_id"] != \
            transaction.predecessor.edit_manifest_id:
        raise ValueError(
            "editorial receipt binds a different EditManifest than the "
            "canonical predecessor")
    rebuild = environment.preview_rebuild(successor)
    rebuild_again = environment.preview_rebuild(successor)
    if rebuild != rebuild_again:
        raise ValueError("rebuild is not deterministic; refusing")
    checks = evaluate_acceptance(
        candidate, owner_decision=owner_decision,
        promotion_ledger=promotion_ledger, environment=environment,
        transaction=transaction, rebuild_receipt=rebuild)
    if not checks["all_pass"]:
        promotion_ledger.append("PROMOTION_REFUSED", {
            "transaction_id": transaction.transaction_id,
            "blocked_by": checks["blocked_by"]})
        raise ValueError(
            f"promotion refused; failed conditions: {checks['blocked_by']}")
    new_take = {"selected_take_id": _candidate_take_id(candidate),
                "shot_id": transaction.affected_shot_id,
                "asset_sha256": candidate.asset_sha256,
                "candidate_id": candidate.candidate_id,
                "owner_decision_id": owner_decision.decision_id}
    receipt = {
        "version": "quality-promotion-receipt-v1",
        "transaction_id": transaction.transaction_id,
        "candidate_id": candidate.candidate_id,
        "selected_exact_asset_sha256": candidate.asset_sha256,
        "superseded_selected_take_id":
            transaction.predecessor.selected_take_id,
        "superseded_asset_sha256": transaction.predecessor.asset_sha256,
        "predecessor_edit_manifest_id":
            transaction.predecessor.edit_manifest_id,
        "successor_edit_manifest_id": successor["edit_manifest_id"],
        "master_before_sha256": transaction.predecessor.master_sha256,
        "master_after_sha256": rebuild["master_sha256"],
        "rollback_target": transaction.predecessor.model_dump(mode="json"),
        "append_only": True,
        "owner_decision_id": owner_decision.decision_id,
    }
    try:
        environment.commit(new_take=new_take, manifest_payload=successor,
                           rebuild_receipt=rebuild,
                           predecessor_master_sha256=
                           transaction.predecessor.master_sha256)
    except Exception as exc:
        promotion_ledger.append("PROMOTION_FAILED", {
            "transaction_id": transaction.transaction_id,
            "error": type(exc).__name__ + ": " + str(exc)})
        if environment.canonical_master_sha256() != \
                transaction.predecessor.master_sha256 or \
                environment.canonical_state_digest() != digest_before:
            raise RuntimeError(
                "MIXED CANONICAL STATE DETECTED after failed promotion") \
                from exc
        raise
    promotion_ledger.append("PROMOTION_COMMITTED", {"receipt": receipt})
    return receipt


def rollback_promotion(transaction: PromotionTransaction, *,
                       environment: PromotionEnvironment,
                       promotion_ledger: HashChainLedger) -> dict:
    """Deterministic rollback to the exact predecessor authority. No
    regeneration: the predecessor bindings and bytes are already
    retained. A mismatch is surfaced, never silently absorbed."""
    if transaction.state != "COMMITTED" or not transaction.promotion_receipt:
        raise ValueError(
            f"rollback requires a COMMITTED transaction with its receipt "
            f"(state is {transaction.state})")
    if _ledger_contains(promotion_ledger, "ROLLBACK_RECORDED",
                        lambda e: e.get("receipt", {}).get(
                            "transaction_id") == transaction.transaction_id):
        raise ValueError(
            f"transaction {transaction.transaction_id} already rolled back")
    receipt = transaction.promotion_receipt
    if environment.canonical_master_sha256() != \
            receipt["master_after_sha256"]:
        raise ValueError(
            "rollback mismatch: environment is not on the promotion's "
            "successor state")
    environment.rollback_to_predecessor(transaction.predecessor)
    restored_master = environment.canonical_master_sha256()
    if restored_master != transaction.predecessor.master_sha256:
        raise RuntimeError(
            "rollback mismatch: restored master does not equal the "
            "recorded predecessor")
    rollback_receipt = {
        "version": "quality-rollback-receipt-v1",
        "transaction_id": transaction.transaction_id,
        "restored_selected_take_id":
            transaction.predecessor.selected_take_id,
        "restored_edit_manifest_id":
            transaction.predecessor.edit_manifest_id,
        "restored_master_sha256": restored_master,
        "replaced_asset_sha256": receipt["selected_exact_asset_sha256"],
        "regeneration_required": False,
    }
    promotion_ledger.append("ROLLBACK_RECORDED",
                            {"receipt": rollback_receipt})
    return rollback_receipt


# ---------------------------------------------------------------------------
# Quality-debt closure lifecycle
# ---------------------------------------------------------------------------

DEBT_LIFECYCLE_STATES = ("ACTIVE", "IMPROVEMENT_CANDIDATE",
                         "OWNER_ACCEPTED_RESOLUTION", "CLOSED", "DEFERRED",
                         "ACCEPTED_DEBT")
DEBT_TRANSITIONS = {
    ("ACTIVE", "IMPROVEMENT_CANDIDATE"),
    ("IMPROVEMENT_CANDIDATE", "ACTIVE"),
    ("IMPROVEMENT_CANDIDATE", "OWNER_ACCEPTED_RESOLUTION"),
    ("OWNER_ACCEPTED_RESOLUTION", "CLOSED"),
    ("ACTIVE", "DEFERRED"),
    ("DEFERRED", "ACTIVE"),
    ("ACTIVE", "ACCEPTED_DEBT"),
}


class DebtClosureLedger(HashChainLedger):
    """Append-only lifecycle ledger for QualityDebtItems. It NEVER
    rewrites the frozen V1 registry (quality_debt_registry_019.json); a
    candidate alone can never close debt."""

    def __init__(self, path: Path | None = None):
        super().__init__(path, kind="quality-debt-closure-ledger")
        self._state: dict[str, str] = {}
        self._replay()

    def _replay(self) -> None:
        self._state = {}
        for event in self.events:
            debt_id = event["debt_id"]
            if event["kind"] == "LIFECYCLE_TRANSITION":
                self._state[debt_id] = event["to_state"]

    def state(self, debt_id: str) -> str:
        return self._state.get(debt_id, "ACTIVE")

    def states(self) -> dict[str, str]:
        return dict(self._state)

    def transition(self, debt_id: str, to_state: str, **payload) -> dict:
        current = self.state(debt_id)
        if (current, to_state) not in DEBT_TRANSITIONS:
            raise ValueError(
                f"invalid debt lifecycle transition {current} -> {to_state}")
        event = self.append("LIFECYCLE_TRANSITION",
                            {"debt_id": debt_id, "from_state": current,
                             "to_state": to_state, **payload})
        self._state[debt_id] = to_state
        return event

    def record_improvement_candidate(self, debt_id: str,
                                     candidate: QualityRepairCandidate) -> dict:
        """ACTIVE -> IMPROVEMENT_CANDIDATE: only a candidate that targets
        this debt AND has reached the review-ready bar may move it."""
        if candidate.quality_debt_ids and debt_id not in \
                candidate.quality_debt_ids:
            raise ValueError(
                f"candidate {candidate.candidate_id} does not target "
                f"{debt_id}")
        if candidate.owner_decision_state not in \
                ("QUALITY_REVIEW_READY", "OWNER_SELECTED"):
            raise ValueError(
                "only a QUALITY_REVIEW_READY (or selected) candidate may "
                "mark a debt IMPROVEMENT_CANDIDATE")
        return self.transition(debt_id, "IMPROVEMENT_CANDIDATE",
                               candidate_id=candidate.candidate_id)

    def record_owner_accepted_resolution(self, debt_id: str, *,
                                         candidate: QualityRepairCandidate,
                                         promotion_receipt: dict) -> dict:
        """IMPROVEMENT_CANDIDATE -> OWNER_ACCEPTED_RESOLUTION. Requires
        the candidate OWNER_SELECTED and a COMMITTED promotion receipt —
        a candidate alone NEVER closes debt."""
        if self.state(debt_id) != "IMPROVEMENT_CANDIDATE":
            raise ValueError(
                f"{debt_id} is {self.state(debt_id)}; owner-accepted "
                f"resolution requires IMPROVEMENT_CANDIDATE")
        if candidate.owner_decision_state != "OWNER_SELECTED":
            raise ValueError(
                "candidate alone does not close debt: Owner selection "
                "required")
        if promotion_receipt.get("candidate_id") != candidate.candidate_id \
                or not promotion_receipt.get("transaction_id"):
            raise ValueError(
                "promotion receipt does not bind the selected candidate")
        return self.transition(
            debt_id, "OWNER_ACCEPTED_RESOLUTION",
            candidate_id=candidate.candidate_id,
            transaction_id=promotion_receipt["transaction_id"])

    def record_closed(self, debt_id: str, *, verification: dict) -> dict:
        """OWNER_ACCEPTED_RESOLUTION -> CLOSED only with a deterministic
        verification receipt of the rebuilt result."""
        if self.state(debt_id) != "OWNER_ACCEPTED_RESOLUTION":
            raise ValueError(
                f"{debt_id} is {self.state(debt_id)}; closing requires "
                f"OWNER_ACCEPTED_RESOLUTION")
        if not verification.get("verified") or not verification.get(
                "transaction_id"):
            raise ValueError(
                "closing requires a deterministic verification receipt")
        return self.transition(debt_id, "CLOSED",
                               transaction_id=verification["transaction_id"])


# ---------------------------------------------------------------------------
# Experiment admission gate (mandatory for V2-002 onward)
# ---------------------------------------------------------------------------

def make_experiment_admission_receipt(*, experiment_id: str,
                                      target_quality_debt_ids: list[str],
                                      canonical_baseline_sha256: str,
                                      hypothesis: str,
                                      variables_changed: list[str],
                                      variables_held_constant: list[str],
                                      max_generate_budget: int,
                                      provider_route: str,
                                      acceptance_criteria: list[str],
                                      owner_review_surface: str,
                                      rollback_plan: str,
                                      created_at: str | None = None) \
        -> dict:
    payload = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "target_quality_debt_ids": list(target_quality_debt_ids),
        "canonical_baseline_sha256": canonical_baseline_sha256,
        "hypothesis": hypothesis,
        "variables_changed": list(variables_changed),
        "variables_held_constant": list(variables_held_constant),
        "max_generate_budget": int(max_generate_budget),
        "provider_route": provider_route,
        "acceptance_criteria": list(acceptance_criteria),
        "owner_review_surface": owner_review_surface,
        "rollback_plan": rollback_plan,
        "created_at": created_at or utc_now(),
    }
    payload["receipt_id"] = "EXA-" + sha256(payload)[:16]
    return {"schema_version": ADMISSION_SCHEMA_VERSION, **payload}


def admission_gate(receipt: dict | None, *,
                   known_debt_ids: list[str]) -> dict:
    """Section-9 gate. A missing or invalid admission receipt is a
    BLOCKED_INVARIANT: no V2 live generation package may proceed."""
    if receipt is None:
        raise ValueError(
            "BLOCKED_INVARIANT: ExperimentAdmissionReceipt missing; no V2 "
            f"experiment from {ADMISSION_REQUIRED_FROM} onward may run "
            f"without one")
    ExperimentAdmissionReceipt.model_validate(receipt)
    unknown = sorted(set(receipt["target_quality_debt_ids"]) -
                     set(known_debt_ids))
    if unknown:
        raise ValueError(
            f"BLOCKED_INVARIANT: target quality debt {unknown} not in the "
            f"frozen registry")
    if receipt["canonical_baseline_sha256"] != QUALITY_V2_CANONICAL_BASELINE:
        raise ValueError(
            "BLOCKED_INVARIANT: experiment baseline is not the frozen "
            "QUALITY_V2_CANONICAL_BASELINE")
    if receipt["max_generate_budget"] < 0:
        raise ValueError(
            "BLOCKED_INVARIANT: generation budget must be a finite bound")
    return {"status": "ADMITTED", "receipt_id": receipt["receipt_id"],
            "experiment_id": receipt["experiment_id"]}


class ExperimentAdmissionReceipt(ContractModel):
    schema_version: Literal["experiment-admission-receipt-v1"] = \
        ADMISSION_SCHEMA_VERSION
    receipt_id: str = Field(pattern=r"^EXA-[a-f0-9]{16}$")
    experiment_id: str = Field(min_length=1)
    target_quality_debt_ids: list[str] = Field(min_length=1)
    canonical_baseline_sha256: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    variables_changed: list[str] = Field(min_length=1)
    variables_held_constant: list[str] = Field(min_length=1)
    max_generate_budget: int = Field(ge=0, le=50)
    provider_route: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    owner_review_surface: str = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_receipt(self):
        validate_contract("experiment_admission_receipt",
                          self.model_dump(mode="json"))
        basis = {k: v for k, v in self.model_dump(mode="json").items()
                 if k != "receipt_id"}
        expected = "EXA-" + sha256(basis)[:16]
        if self.receipt_id != expected:
            raise ValueError(f"receipt identity mismatch: expected {expected}")
        return self


def require_experiment_admission(receipt: dict | None, *,
                                 known_debt_ids: list[str],
                                 experiment_id: str = "") -> dict:
    result = admission_gate(receipt, known_debt_ids=known_debt_ids)
    if experiment_id and result["experiment_id"] != experiment_id:
        raise ValueError(
            f"BLOCKED_INVARIANT: admission receipt is for "
            f"{result['experiment_id']}, not {experiment_id}")
    return result


def load_frozen_debt_ids(root: Path) -> list[str]:
    """Debt ids from the frozen V1 registry (never mutated)."""
    registry = json.loads((root / DEBT_REGISTRY_019).read_text(
        encoding="utf-8"))
    return sorted(i["debt_id"] for i in registry["items"])


# ---------------------------------------------------------------------------
# Frozen adversarial / recovery case matrix (>=80 cases; proven in
# tests/test_quality_v2_recovery_matrix_001.py, emitted as evidence by
# tools/build_quality_v2_recovery_matrix_001.py)
# ---------------------------------------------------------------------------

RECOVERY_CASES: list[dict] = [
    # -- acceptance policy ------------------------------------------------
    {"case_id": "RC-001", "category": "ACCEPTANCE_POLICY",
     "scenario": "candidate asset sha256 differs from the technical receipt binding",
     "expected": "REFUSED", "enforced_by": "C1/C2 evaluate_acceptance"},
    {"case_id": "RC-002", "category": "ACCEPTANCE_POLICY",
     "scenario": "technical QC decision is fail",
     "expected": "REFUSED", "enforced_by": "C2 evaluate_acceptance"},
    {"case_id": "RC-003", "category": "ACCEPTANCE_POLICY",
     "scenario": "technical QC receipt missing entirely",
     "expected": "REFUSED", "enforced_by": "C2 evaluate_acceptance"},
    {"case_id": "RC-004", "category": "ACCEPTANCE_POLICY",
     "scenario": "candidate technically valid but identity regresses",
     "expected": "REFUSED", "enforced_by": "C3 evaluate_acceptance"},
    {"case_id": "RC-005", "category": "ACCEPTANCE_POLICY",
     "scenario": "identity continuity INCONCLUSIVE (regression unproven)",
     "expected": "REFUSED", "enforced_by": "C3 evaluate_acceptance"},
    {"case_id": "RC-006", "category": "ACCEPTANCE_POLICY",
     "scenario": "target defect UNCHANGED (no improvement)",
     "expected": "REFUSED", "enforced_by": "C4 evaluate_acceptance"},
    {"case_id": "RC-007", "category": "ACCEPTANCE_POLICY",
     "scenario": "target improvement INCONCLUSIVE",
     "expected": "REFUSED", "enforced_by": "C4 evaluate_acceptance"},
    {"case_id": "RC-008", "category": "ACCEPTANCE_POLICY",
     "scenario": "target dimension claimed but verdict contradicts it",
     "expected": "REFUSED", "enforced_by": "QualityReviewReceipt validator"},
    {"case_id": "RC-009", "category": "ACCEPTANCE_POLICY",
     "scenario": "non-identity dimension REGRESSED at HIGH severity",
     "expected": "REFUSED", "enforced_by": "C5 hard block"},
    {"case_id": "RC-010", "category": "ACCEPTANCE_POLICY",
     "scenario": "soft regression selected without Owner trade-off note",
     "expected": "REFUSED", "enforced_by": "apply_owner_decision"},
    {"case_id": "RC-011", "category": "ACCEPTANCE_POLICY",
     "scenario": "editorial compatibility explicitly false",
     "expected": "REFUSED", "enforced_by": "C6 evaluate_acceptance"},
    {"case_id": "RC-012", "category": "ACCEPTANCE_POLICY",
     "scenario": "editorial receipt binds a different EditManifest",
     "expected": "REFUSED", "enforced_by": "C6/transaction manifest check"},
    # -- review contract: no aggregate compensation ------------------------
    {"case_id": "RC-013", "category": "REVIEW_CONTRACT",
     "scenario": "motion IMPROVED but identity REGRESSED must not become PASS",
     "expected": "REFUSED", "enforced_by": "hard_blocks/no aggregate"},
    {"case_id": "RC-014", "category": "REVIEW_CONTRACT",
     "scenario": "logic IMPROVED but camera coverage REGRESSED must not pass",
     "expected": "REFUSED", "enforced_by": "C5 evaluate_acceptance"},
    {"case_id": "RC-015", "category": "REVIEW_CONTRACT",
     "scenario": "aggregate score hides regression (score computed anyway)",
     "expected": "REFUSED", "enforced_by": "no_aggregate_score structural"},
    {"case_id": "RC-016", "category": "REVIEW_CONTRACT",
     "scenario": "review receipt omits a quality dimension",
     "expected": "REFUSED", "enforced_by": "receipt validator"},
    {"case_id": "RC-017", "category": "REVIEW_CONTRACT",
     "scenario": "review receipt carries an unknown dimension",
     "expected": "REFUSED", "enforced_by": "DimensionFinding validator"},
    {"case_id": "RC-018", "category": "REVIEW_CONTRACT",
     "scenario": "duplicate findings for one dimension",
     "expected": "REFUSED", "enforced_by": "receipt validator"},
    {"case_id": "RC-019", "category": "REVIEW_CONTRACT",
     "scenario": "receipt evidence edited after minting",
     "expected": "REFUSED", "enforced_by": "review_id derivation"},
    {"case_id": "RC-020", "category": "REVIEW_CONTRACT",
     "scenario": "target dimension marked NOT_APPLICABLE",
     "expected": "REFUSED", "enforced_by": "receipt validator"},
    {"case_id": "RC-021", "category": "REVIEW_CONTRACT",
     "scenario": "no_aggregate_score flipped to false",
     "expected": "REFUSED", "enforced_by": "schema const"},
    {"case_id": "RC-022", "category": "REVIEW_CONTRACT",
     "scenario": "advisory review alone claims Owner-selected state",
     "expected": "REFUSED", "enforced_by": "apply_owner_decision"},
    # -- decision rights ---------------------------------------------------
    {"case_id": "RC-023", "category": "DECISION_RIGHTS",
     "scenario": "worker mints OWNER_SELECTED",
     "expected": "REFUSED", "enforced_by": "apply_owner_decision"},
    {"case_id": "RC-024", "category": "DECISION_RIGHTS",
     "scenario": "worker identity inside an owner decision payload",
     "expected": "REFUSED", "enforced_by": "refuse_worker_origin"},
    {"case_id": "RC-025", "category": "DECISION_RIGHTS",
     "scenario": "automated QC selects the creative winner",
     "expected": "REFUSED", "enforced_by": "ROLE_PERMISSIONS"},
    {"case_id": "RC-026", "category": "DECISION_RIGHTS",
     "scenario": "provider model claims any authority action",
     "expected": "REFUSED", "enforced_by": "PROVIDER empty permissions"},
    {"case_id": "RC-027", "category": "DECISION_RIGHTS",
     "scenario": "tech lead impersonates Owner preference",
     "expected": "REFUSED", "enforced_by": "apply_owner_decision identity"},
    {"case_id": "RC-028", "category": "DECISION_RIGHTS",
     "scenario": "worker defines the experiment",
     "expected": "REFUSED", "enforced_by": "ROLE_PERMISSIONS"},
    {"case_id": "RC-029", "category": "DECISION_RIGHTS",
     "scenario": "any role promotes by action grant",
     "expected": "REFUSED", "enforced_by": "NON_GRANTABLE_ACTIONS"},
    {"case_id": "RC-030", "category": "DECISION_RIGHTS",
     "scenario": "worker rejects a candidate (Owner action)",
     "expected": "REFUSED", "enforced_by": "ROLE_PERMISSIONS"},
    {"case_id": "RC-031", "category": "DECISION_RIGHTS",
     "scenario": "automated QC rejects a technically invalid candidate (allowed)",
     "expected": "PROVEN", "enforced_by": "record_technical_refusal"},
    {"case_id": "RC-032", "category": "DECISION_RIGHTS",
     "scenario": "Owner defers an exact candidate (allowed)",
     "expected": "PROVEN", "enforced_by": "apply_owner_decision"},
    {"case_id": "RC-033", "category": "DECISION_RIGHTS",
     "scenario": "advisory payload used as the Owner decision object",
     "expected": "REFUSED", "enforced_by": "apply_owner_decision typing"},
    {"case_id": "RC-034", "category": "DECISION_RIGHTS",
     "scenario": "provider output forges an owner decision",
     "expected": "REFUSED", "enforced_by": "refuse_worker_origin markers"},
    # -- candidate state machine -------------------------------------------
    {"case_id": "RC-035", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "PROPOSED -> OWNER_SELECTED skip",
     "expected": "REFUSED", "enforced_by": "_transition"},
    {"case_id": "RC-036", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "PROPOSED -> QUALITY_REVIEW_READY skip",
     "expected": "REFUSED", "enforced_by": "attach_quality_review"},
    {"case_id": "RC-037", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "duplicate candidate identity (same basis, second mint)",
     "expected": "REFUSED", "enforced_by": "deterministic candidate_id"},
    {"case_id": "RC-038", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "candidate without a 64-hex asset sha256",
     "expected": "REFUSED", "enforced_by": "schema pattern"},
    {"case_id": "RC-039", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "OWNER_SELECTED state without a decision id",
     "expected": "REFUSED", "enforced_by": "model validator"},
    {"case_id": "RC-040", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "SUPERSEDED without superseded_by",
     "expected": "REFUSED", "enforced_by": "model validator"},
    {"case_id": "RC-041", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "TECHNICALLY_VALID -> OWNER_SELECTED (review skipped)",
     "expected": "REFUSED", "enforced_by": "_transition"},
    {"case_id": "RC-042", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "further transition out of terminal SUPERSEDED",
     "expected": "REFUSED", "enforced_by": "_transition"},
    {"case_id": "RC-043", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "candidate becomes canonical without the transaction",
     "expected": "REFUSED", "enforced_by": "execute_promotion C7/C9"},
    {"case_id": "RC-044", "category": "CANDIDATE_STATE_MACHINE",
     "scenario": "review attached to a different candidate",
     "expected": "REFUSED", "enforced_by": "attach_quality_review"},
    # -- promotion transaction ---------------------------------------------
    {"case_id": "RC-045", "category": "PROMOTION_TRANSACTION",
     "scenario": "wrong canonical predecessor (environment master moved)",
     "expected": "REFUSED", "enforced_by": "execute_promotion binding"},
    {"case_id": "RC-046", "category": "PROMOTION_TRANSACTION",
     "scenario": "stale EditManifest at execution time",
     "expected": "REFUSED", "enforced_by": "execute_promotion manifest"},
    {"case_id": "RC-047", "category": "PROMOTION_TRANSACTION",
     "scenario": "execute with a candidate that was never Owner-selected",
     "expected": "REFUSED", "enforced_by": "C7 evaluate_acceptance"},
    {"case_id": "RC-048", "category": "PROMOTION_TRANSACTION",
     "scenario": "execute with failing technical QC",
     "expected": "REFUSED", "enforced_by": "C2 evaluate_acceptance"},
    {"case_id": "RC-049", "category": "PROMOTION_TRANSACTION",
     "scenario": "non-deterministic rebuild preview",
     "expected": "REFUSED", "enforced_by": "execute_promotion determinism"},
    {"case_id": "RC-050", "category": "PROMOTION_TRANSACTION",
     "scenario": "master rebuild failure at commit",
     "expected": "FAILED_CLOSED", "enforced_by": "execute_promotion"},
    {"case_id": "RC-051", "category": "PROMOTION_TRANSACTION",
     "scenario": "partial promotion (torn write) leaves mixed state",
     "expected": "FAILED_CLOSED", "enforced_by": "atomic commit guard"},
    {"case_id": "RC-052", "category": "PROMOTION_TRANSACTION",
     "scenario": "double execution of a COMMITTED transaction",
     "expected": "REFUSED", "enforced_by": "state guard"},
    {"case_id": "RC-053", "category": "PROMOTION_TRANSACTION",
     "scenario": "re-execution of a FAILED transaction",
     "expected": "REFUSED", "enforced_by": "state guard"},
    {"case_id": "RC-054", "category": "PROMOTION_TRANSACTION",
     "scenario": "transaction binds a missing predecessor asset field",
     "expected": "REFUSED", "enforced_by": "PredecessorBinding schema"},
    {"case_id": "RC-055", "category": "PROMOTION_TRANSACTION",
     "scenario": "affected clip order outside the manifest",
     "expected": "REFUSED", "enforced_by": "build_successor_manifest"},
    {"case_id": "RC-056", "category": "PROMOTION_TRANSACTION",
     "scenario": "successor manifest id tampered",
     "expected": "REFUSED", "enforced_by": "identity check"},
    # -- rollback -----------------------------------------------------------
    {"case_id": "RC-057", "category": "ROLLBACK",
     "scenario": "rollback of a PROPOSED transaction",
     "expected": "REFUSED", "enforced_by": "rollback_promotion"},
    {"case_id": "RC-058", "category": "ROLLBACK",
     "scenario": "rollback of a FAILED transaction",
     "expected": "REFUSED", "enforced_by": "rollback_promotion"},
    {"case_id": "RC-059", "category": "ROLLBACK",
     "scenario": "rollback when the environment is not on the successor",
     "expected": "REFUSED", "enforced_by": "rollback mismatch check"},
    {"case_id": "RC-060", "category": "ROLLBACK",
     "scenario": "rollback restores the exact predecessor (positive)",
     "expected": "PROVEN", "enforced_by": "rollback_promotion"},
    {"case_id": "RC-061", "category": "ROLLBACK",
     "scenario": "rollback without regeneration",
     "expected": "PROVEN", "enforced_by": "retained bytes + receipt"},
    {"case_id": "RC-062", "category": "ROLLBACK",
     "scenario": "double rollback",
     "expected": "REFUSED", "enforced_by": "state guard"},
    {"case_id": "RC-063", "category": "ROLLBACK",
     "scenario": "predecessor asset bytes missing at promotion time",
     "expected": "REFUSED", "enforced_by": "C10 evaluate_acceptance"},
    {"case_id": "RC-064", "category": "ROLLBACK",
     "scenario": "promotion ledger chain tampered after recording",
     "expected": "REFUSED", "enforced_by": "HashChainLedger.verify"},
    # -- quality debt lifecycle ----------------------------------------------
    {"case_id": "RC-065", "category": "DEBT_LIFECYCLE",
     "scenario": "a PROPOSED candidate alone closes debt",
     "expected": "REFUSED", "enforced_by": "record_improvement_candidate"},
    {"case_id": "RC-066", "category": "DEBT_LIFECYCLE",
     "scenario": "review-ready candidate closes debt without promotion",
     "expected": "REFUSED", "enforced_by": "record_owner_accepted_resolution"},
    {"case_id": "RC-067", "category": "DEBT_LIFECYCLE",
     "scenario": "IMPROVEMENT_CANDIDATE -> CLOSED skips Owner acceptance",
     "expected": "REFUSED", "enforced_by": "DEBT_TRANSITIONS"},
    {"case_id": "RC-068", "category": "DEBT_LIFECYCLE",
     "scenario": "owner-accepted resolution without a COMMITTED receipt",
     "expected": "REFUSED", "enforced_by": "record_owner_accepted_resolution"},
    {"case_id": "RC-069", "category": "DEBT_LIFECYCLE",
     "scenario": "CLOSED without deterministic verification",
     "expected": "REFUSED", "enforced_by": "record_closed"},
    {"case_id": "RC-070", "category": "DEBT_LIFECYCLE",
     "scenario": "candidate not targeting the debt moves it",
     "expected": "REFUSED", "enforced_by": "record_improvement_candidate"},
    {"case_id": "RC-071", "category": "DEBT_LIFECYCLE",
     "scenario": "full valid closure chain (positive)",
     "expected": "PROVEN", "enforced_by": "DebtClosureLedger"},
    {"case_id": "RC-072", "category": "DEBT_LIFECYCLE",
     "scenario": "V1 registry file rewritten by the lifecycle ledger",
     "expected": "UNCHANGED", "enforced_by": "separate ledger file"},
    # -- experiment admission -------------------------------------------------
    {"case_id": "RC-073", "category": "EXPERIMENT_ADMISSION",
     "scenario": "admission receipt missing",
     "expected": "REFUSED", "enforced_by": "admission_gate"},
    {"case_id": "RC-074", "category": "EXPERIMENT_ADMISSION",
     "scenario": "wrong experiment baseline",
     "expected": "REFUSED", "enforced_by": "admission_gate"},
    {"case_id": "RC-075", "category": "EXPERIMENT_ADMISSION",
     "scenario": "target debt id not in the frozen registry",
     "expected": "REFUSED", "enforced_by": "admission_gate"},
    {"case_id": "RC-076", "category": "EXPERIMENT_ADMISSION",
     "scenario": "empty hypothesis",
     "expected": "REFUSED", "enforced_by": "schema minLength"},
    {"case_id": "RC-077", "category": "EXPERIMENT_ADMISSION",
     "scenario": "unbounded generation budget",
     "expected": "REFUSED", "enforced_by": "schema/le+gate"},
    {"case_id": "RC-078", "category": "EXPERIMENT_ADMISSION",
     "scenario": "no variables held constant",
     "expected": "REFUSED", "enforced_by": "schema minItems"},
    {"case_id": "RC-079", "category": "EXPERIMENT_ADMISSION",
     "scenario": "no acceptance criteria",
     "expected": "REFUSED", "enforced_by": "schema minItems"},
    {"case_id": "RC-080", "category": "EXPERIMENT_ADMISSION",
     "scenario": "valid receipt admits the experiment (positive)",
     "expected": "PROVEN", "enforced_by": "admission_gate"},
    # -- V1 baseline immutability ----------------------------------------------
    {"case_id": "RC-081", "category": "V1_BASELINE_IMMUTABILITY",
     "scenario": "canonical master identity drifts from the 019 receipt",
     "expected": "UNCHANGED", "enforced_by": "CANONICAL_MASTER_SHA256 binding"},
    {"case_id": "RC-082", "category": "V1_BASELINE_IMMUTABILITY",
     "scenario": "debt registry 019 mutated by governance use",
     "expected": "UNCHANGED", "enforced_by": "load_frozen_debt_ids read-only"},
    {"case_id": "RC-083", "category": "V1_BASELINE_IMMUTABILITY",
     "scenario": "owner decision 019 mutated by governance use",
     "expected": "UNCHANGED", "enforced_by": "read-only binding"},
    {"case_id": "RC-084", "category": "V1_BASELINE_IMMUTABILITY",
     "scenario": "governance module exposes a generation capability",
     "expected": "UNCHANGED", "enforced_by": "structural surface scan"},
    {"case_id": "RC-085", "category": "V1_BASELINE_IMMUTABILITY",
     "scenario": "governance use promotes anything by itself",
     "expected": "UNCHANGED", "enforced_by": "zero-promotion invariant"},
    {"case_id": "RC-086", "category": "V1_BASELINE_IMMUTABILITY",
     "scenario": "frozen SOT goal/baseline strings drift",
     "expected": "UNCHANGED", "enforced_by": "SOT doc binding test"},
    {"case_id": "RC-087", "category": "REVIEW_CONTRACT",
     "scenario": "motion IMPROVED but NARRATIVE_LOGIC REGRESSED must not "
                 "pass (one improvement never compensates another "
                 "regression)",
     "expected": "REFUSED", "enforced_by": "C5 evaluate_acceptance"},
    {"case_id": "RC-088", "category": "CUSTODY",
     "scenario": "ambiguous provider output (null-ack / unproven semantic "
                 "identity) proposed as a candidate",
     "expected": "REFUSED",
     "enforced_by": "empty semantic identity refused + "
                    "EXTERNAL_AMBIGUITY_RULE"},
    {"case_id": "RC-089", "category": "CUSTODY",
     "scenario": "blind retry after a failed promotion without fresh "
                 "authority",
     "expected": "REFUSED",
     "enforced_by": "execute_promotion ledger re-execution guard (fresh "
                    "proposal + fresh authority required)"},
]


def list_recovery_cases() -> list[dict]:
    return [dict(case) for case in RECOVERY_CASES]
