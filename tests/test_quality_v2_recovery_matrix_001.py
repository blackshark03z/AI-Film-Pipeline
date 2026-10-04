"""QUALITY-V2-001 recovery matrix: 89 adversarial/recovery cases, each
PROVEN against its live guard. Case table (single source of truth):
film_pipeline.quality_repair_v2.RECOVERY_CASES; emitted as evidence by
tools/build_quality_v2_recovery_matrix_001.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import film_pipeline.quality_repair_v2 as m
from film_pipeline.owner_review import OwnerReviewDecision, \
    make_owner_decision, refuse_worker_origin

from test_quality_v2_repair_policy_001 import (  # noqa: F401
    SHA_A, SHA_B, SHA_C, ROOT, FakeRequest, admission_kwargs,
    fresh_env, owner_decision, ready_candidate)
from test_quality_v2_promotion_rollback_001 import fault_env

EXECUTORS: dict[str, object] = {}


def case(case_id):
    def wrap(fn):
        EXECUTORS[case_id] = fn
        return fn
    return wrap


def rejected_build(**kw):
    return m.apply_owner_decision(ready_candidate(**kw),
                                  owner_decision(kw.get("asset", SHA_B)))


def selected(**kw):
    return rejected_build(**kw)


def propose_for(candidate, env=None):
    env = env or fresh_env()
    return m.propose_promotion_transaction(candidate=candidate,
                                           environment=env,
                                           affected_clip_order=1)


def execute_for(txn, candidate, env=None, ledger=None, sha=SHA_B):
    return m.execute_promotion(txn, candidate=candidate,
                               environment=env or fresh_env(),
                               promotion_ledger=ledger or m.HashChainLedger(),
                               owner_decision=owner_decision(sha))


def committed_run():
    env = fresh_env()
    candidate = selected()
    ledger = m.HashChainLedger()
    txn = propose_for(candidate, env)
    receipt = m.execute_promotion(txn, candidate=candidate, environment=env,
                                  promotion_ledger=ledger,
                                  owner_decision=owner_decision(SHA_B))
    return env, candidate, ledger, txn.with_state("COMMITTED", receipt), receipt


def review_with(candidate, *findings, target=("ACTION_CAUSALITY",)):
    return m.build_review_receipt(
        candidate=candidate, baseline_asset_sha256=SHA_A,
        target_dimensions=list(target),
        findings=[{"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
                   "severity": "NONE", "evidence": ["legible"]}, *findings],
        review_source="ADVISORY_WORKER")



def base_candidate(asset=SHA_B):
    return m.make_candidate(source_canonical_take="take_A",
                            affected_shot="S1", repair_reason="r",
                            asset_sha256=asset,
                            generation_semantic_identity="g")


def regressed(dim, severity):
    return {"dimension": dim, "verdict": "REGRESSED", "severity": severity,
            "evidence": [f"{dim.lower()} drifted"]}


# =======================================================================
# ACCEPTANCE_POLICY
# =======================================================================

@case("RC-001")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValueError, match="different asset sha256"):
        m.record_technical_validation(cand, {"decision": "pass",
                                             "qc_report_id": "q",
                                             "asset_sha256": SHA_C})


@case("RC-002")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValueError, match="did not pass"):
        m.record_technical_validation(cand, {"decision": "fail",
                                             "qc_report_id": "q",
                                             "asset_sha256": SHA_B})


@case("RC-003")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValueError, match="missing"):
        m.validate_technical_receipt({}, cand)


@case("RC-004")
def _():
    base = base_candidate()
    cand = m.attach_quality_review(
        m.record_technical_validation(
            base,
            {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B}),
        review_with(base, regressed("IDENTITY", "MEDIUM")),
        identity_receipt={"identity_continuity": "REGRESSED",
                          "verified_by": "v"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "edit_pred",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "v"})
    out = m.evaluate_acceptance(cand, owner_decision=owner_decision(SHA_B))
    assert "C3_IDENTITY_WORLD_NO_REGRESSION" in out["blocked_by"]
    with pytest.raises(ValueError, match="unconditionally blocking"):
        m.validate_identity_receipt(
            {"identity_continuity": "REGRESSED", "verified_by": "v"},
            m.candidate_review(cand))


@case("RC-005")
def _():
    review = review_with(base_candidate())
    with pytest.raises(ValueError, match="unproven"):
        m.validate_identity_receipt(
            {"identity_continuity": "INCONCLUSIVE", "verified_by": "v"},
            review)


@case("RC-006")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValidationError, match="must be IMPROVED"):
        m.build_review_receipt(
            candidate=cand, baseline_asset_sha256=SHA_A,
            target_dimensions=["TEMPORAL_MOTION"],
            findings=[{"dimension": "TEMPORAL_MOTION",
                       "verdict": "UNCHANGED", "severity": "NONE",
                       "evidence": ["same"]}],
            review_source="ADVISORY_WORKER")


@case("RC-007")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValidationError, match="must be IMPROVED"):
        m.build_review_receipt(
            candidate=cand, baseline_asset_sha256=SHA_A,
            target_dimensions=["TEMPORAL_MOTION"],
            findings=[{"dimension": "TEMPORAL_MOTION",
                       "verdict": "INCONCLUSIVE", "severity": "NONE",
                       "evidence": ["unclear"]}],
            review_source="ADVISORY_WORKER")


@case("RC-008")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValidationError, match="must be IMPROVED"):
        m.build_review_receipt(
            candidate=cand, baseline_asset_sha256=SHA_A,
            target_dimensions=["ACTION_CAUSALITY"],
            findings=[{"dimension": "CAMERA", "verdict": "IMPROVED",
                       "severity": "NONE", "evidence": ["framing better"]}],
            review_source="ADVISORY_WORKER")


@case("RC-009")
def _():
    base = base_candidate()
    cand = m.attach_quality_review(
        m.record_technical_validation(
            base,
            {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B}),
        review_with(base, regressed("CAMERA", "HIGH")),
        identity_receipt={"identity_continuity": "UNCHANGED",
                          "verified_by": "v"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "edit_pred",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "v"})
    with pytest.raises(ValueError, match="CAMERA_REGRESSED_HIGH"):
        m.apply_owner_decision(cand, owner_decision(
            note="TRADEOFF_ACCEPTED=CAMERA"))


@case("RC-010")
def _():
    base = base_candidate()
    cand = m.attach_quality_review(
        m.record_technical_validation(
            base,
            {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B}),
        review_with(base, regressed("PERFORMANCE", "LOW")),
        identity_receipt={"identity_continuity": "UNCHANGED",
                          "verified_by": "v"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "edit_pred",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "v"})
    with pytest.raises(ValueError, match="trade-off"):
        m.apply_owner_decision(cand, owner_decision(note="no ack"))


@case("RC-011")
def _():
    with pytest.raises(ValueError, match="editorial fit"):
        m.validate_editorial_receipt(
            {"editorial_compatible": False, "edit_manifest_id": "e",
             "affected_clip_order": 1, "trim_compatible": True,
             "verified_by": "v"})


@case("RC-012")
def _():
    env = fresh_env()
    cand = m.QualityRepairCandidate.model_validate(
        {**selected().model_dump(mode="json"),
         "editorial_compatibility_receipt": {
             "editorial_compatible": True, "edit_manifest_id": "edit_OTHER",
             "affected_clip_order": 1, "trim_compatible": True,
             "verified_by": "v"}})
    txn = propose_for(cand, env)
    with pytest.raises(ValueError, match="different EditManifest"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


# =======================================================================
# REVIEW_CONTRACT
# =======================================================================

@case("RC-013")
def _():
    base = base_candidate()
    cand = m.attach_quality_review(
        m.record_technical_validation(
            base,
            {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B}),
        review_with(base, regressed("IDENTITY", "LOW"),
                    {"dimension": "TEMPORAL_MOTION", "verdict": "IMPROVED",
                     "severity": "NONE", "evidence": ["smoother"]}),
        identity_receipt={"identity_continuity": "UNCHANGED",
                          "verified_by": "v"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "edit_pred",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "v"})
    review = m.candidate_review(cand)
    assert review.finding("TEMPORAL_MOTION").verdict == "IMPROVED"
    assert review.finding("IDENTITY").verdict == "REGRESSED"
    assert review.hard_blocks()  # motion improvement never compensates
    out = m.evaluate_acceptance(cand, owner_decision=owner_decision(SHA_B))
    assert not out["all_pass"]
    with pytest.raises(ValueError, match="IDENTITY_REGRESSED"):
        m.apply_owner_decision(cand, owner_decision(
            note="TRADEOFF_ACCEPTED=IDENTITY"))


@case("RC-014")
def _():
    base = base_candidate()
    cand = m.attach_quality_review(
        m.record_technical_validation(
            base,
            {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B}),
        m.build_review_receipt(
            candidate=base, baseline_asset_sha256=SHA_A,
            target_dimensions=["NARRATIVE_LOGIC"],
            findings=[{"dimension": "NARRATIVE_LOGIC", "verdict": "IMPROVED",
                       "severity": "NONE", "evidence": ["logic legible"]},
                      regressed("CAMERA", "LOW")],
            review_source="ADVISORY_WORKER"),
        identity_receipt={"identity_continuity": "UNCHANGED",
                          "verified_by": "v"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "edit_pred",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "v"})
    out = m.evaluate_acceptance(cand, owner_decision=owner_decision(SHA_B))
    assert "C5_NO_HIGHER_SEVERITY_NEW_DEFECT" in out["blocked_by"]


@case("RC-087")
def _():
    base = base_candidate()
    cand = m.attach_quality_review(
        m.record_technical_validation(
            base,
            {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B}),
        m.build_review_receipt(
            candidate=base, baseline_asset_sha256=SHA_A,
            target_dimensions=["PERFORMANCE"],
            findings=[{"dimension": "PERFORMANCE", "verdict": "IMPROVED",
                       "severity": "NONE", "evidence": ["less stiff"]},
                      regressed("NARRATIVE_LOGIC", "LOW")],
            review_source="ADVISORY_WORKER"),
        identity_receipt={"identity_continuity": "UNCHANGED",
                          "verified_by": "v"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "edit_pred",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "v"})
    out = m.evaluate_acceptance(cand, owner_decision=owner_decision(SHA_B))
    assert "C5_NO_HIGHER_SEVERITY_NEW_DEFECT" in out["blocked_by"]


@case("RC-015")
def _():
    cand = selected()
    review = m.candidate_review(cand)
    summary = review.tradeoff_summary()
    assert isinstance(summary, dict) and len(summary) == 10
    assert all("verdict" in v and "severity" in v for v in summary.values())
    assert review.no_aggregate_score is True
    public = [n for n, v in vars(m).items()
              if callable(v) and not n.startswith("_")]
    assert not any("score" in n.lower() or "aggregate" in n.lower()
                   for n in public)


@case("RC-016")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    full = review_with(cand).model_dump(mode="json")
    full["findings"] = full["findings"][:9]  # one dimension dropped
    with pytest.raises(ValidationError):
        m.QualityReviewReceipt.model_validate(full)


@case("RC-017")
def _():
    with pytest.raises(ValidationError, match="unknown quality dimension"):
        m.DimensionFinding(dimension="WIBBLE", verdict="IMPROVED",
                           evidence=["e"])


@case("RC-018")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    data = review_with(cand).model_dump(mode="json")
    data["findings"][1] = dict(data["findings"][0])
    with pytest.raises(ValidationError, match="duplicate finding"):
        m.QualityReviewReceipt.model_validate(data)


@case("RC-019")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    data = review_with(cand).model_dump(mode="json")
    data["findings"][0]["evidence"] = ["rewritten after minting"]
    with pytest.raises(ValidationError, match="identity mismatch"):
        m.QualityReviewReceipt.model_validate(data)


@case("RC-020")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValidationError, match="must be IMPROVED"):
        m.build_review_receipt(
            candidate=cand, baseline_asset_sha256=SHA_A,
            target_dimensions=["ACTION_CAUSALITY"], findings=[],
            review_source="ADVISORY_WORKER")


@case("RC-021")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    data = review_with(cand).model_dump(mode="json")
    data["no_aggregate_score"] = False
    with pytest.raises(ValidationError):
        m.QualityReviewReceipt.model_validate(data)


@case("RC-022")
def _():
    with pytest.raises(ValidationError):
        OwnerReviewDecision(
            decision_id="OWNER-DEC-0123456789abcdef",
            review_request_id="OWNER-REV-V2TEST",
            reviewed_bindings={"asset_sha256": SHA_B}, decision="ACCEPT",
            decided_at="2026-10-04T00:00:00Z",
            decision_source="ADVISORY_WORKER", owner_identity="OWNER")


# =======================================================================
# DECISION_RIGHTS
# =======================================================================

@case("RC-023")
def _():
    with pytest.raises(ValidationError, match="OWNER_SELECTED requires"):
        m.QualityRepairCandidate.model_validate(
            {**ready_candidate().model_dump(mode="json"),
             "owner_decision_state": "OWNER_SELECTED",
             "owner_decision_id": ""})
    with pytest.raises(ValueError, match="non-Owner identity"):
        m.apply_owner_decision(ready_candidate(),
                               owner_decision(owner_identity="WORKER-LEAD"))


@case("RC-024")
def _():
    with pytest.raises(ValueError, match="non-Owner identity"):
        owner_decision(owner_identity="worker-agent-7")


@case("RC-025")
def _():
    with pytest.raises(ValueError, match="not authorized"):
        m.authorize("AUTOMATED_QC", "SELECT_CANDIDATE")


@case("RC-026")
def _():
    with pytest.raises(ValueError, match="not authorized"):
        m.authorize("PROVIDER", "EXECUTE_EXPERIMENT")
    assert m.ROLE_PERMISSIONS["PROVIDER"] == frozenset()


@case("RC-027")
def _():
    with pytest.raises(ValueError, match="only the Owner identity"):
        m.apply_owner_decision(ready_candidate(),
                               owner_decision(owner_identity="TECH_LEAD"))


@case("RC-028")
def _():
    with pytest.raises(ValueError, match="not authorized"):
        m.authorize("WORKER", "DEFINE_EXPERIMENT")


@case("RC-029")
def _():
    for role in ("TECH_LEAD", "WORKER", "AUTOMATED_QC", "OWNER", "PROVIDER"):
        with pytest.raises(ValueError, match="not a grantable"):
            m.authorize(role, "PROMOTE_CANDIDATE")


@case("RC-030")
def _():
    with pytest.raises(ValueError, match="not authorized"):
        m.authorize("WORKER", "REJECT_CANDIDATE")


@case("RC-031")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    refusal = m.record_technical_refusal(cand, {"reason": "decode failed"})
    assert refusal["advance_blocked"] is True
    assert refusal["state_after"] == "PROPOSED"


@case("RC-032")
def _():
    deferred = m.apply_owner_decision(ready_candidate(),
                                      owner_decision(decision="DEFER"))
    assert deferred.owner_decision_state == "DEFERRED"


@case("RC-033")
def _():
    with pytest.raises(ValidationError):
        OwnerReviewDecision(
            decision_id="OWNER-DEC-0123456789abcdef",
            review_request_id="OWNER-REV-V2TEST",
            reviewed_bindings={"asset_sha256": SHA_B}, decision="ACCEPT",
            decided_at="2026-10-04T00:00:00Z", decision_source="ADVISORY",
            owner_identity="OWNER")


@case("RC-034")
def _():
    with pytest.raises(ValueError, match="non-Owner origin marker"):
        refuse_worker_origin({"decision": "ACCEPT", "owner_identity": "OWNER",
                              "API_MODEL": "gemini"})


# =======================================================================
# CANDIDATE_STATE_MACHINE
# =======================================================================

@case("RC-035")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    with pytest.raises(ValueError, match="invalid candidate transition"):
        m._transition(cand, "OWNER_SELECTED")


@case("RC-036")
def _():
    cand = m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                            repair_reason="r", asset_sha256=SHA_B,
                            generation_semantic_identity="g")
    review = review_with(cand)
    with pytest.raises(ValueError, match="TECHNICALLY_VALID"):
        m.attach_quality_review(cand, review)


@case("RC-037")
def _():
    first = m.make_candidate(source_canonical_take="take_A",
                             affected_shot="S1", repair_reason="r",
                             asset_sha256=SHA_B,
                             generation_semantic_identity="g")
    second = m.make_candidate(source_canonical_take="take_A",
                              affected_shot="S1", repair_reason="r",
                              asset_sha256=SHA_B,
                              generation_semantic_identity="g")
    assert first.candidate_id == second.candidate_id


@case("RC-038")
def _():
    with pytest.raises(ValidationError):
        m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                         repair_reason="r", asset_sha256="not-a-sha",
                         generation_semantic_identity="g")


@case("RC-039")
def _():
    with pytest.raises(ValidationError, match="OWNER_SELECTED requires"):
        m.QualityRepairCandidate.model_validate(
            {**ready_candidate().model_dump(mode="json"),
             "owner_decision_state": "OWNER_SELECTED",
             "owner_decision_id": ""})


@case("RC-040")
def _():
    with pytest.raises(ValidationError, match="SUPERSEDED requires"):
        m.QualityRepairCandidate.model_validate(
            {**ready_candidate().model_dump(mode="json"),
             "owner_decision_state": "SUPERSEDED"})


@case("RC-041")
def _():
    tech = m.record_technical_validation(
        m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                         repair_reason="r", asset_sha256=SHA_B,
                         generation_semantic_identity="g"),
        {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B})
    with pytest.raises(ValueError, match="invalid candidate transition"):
        m._transition(tech, "OWNER_SELECTED")


@case("RC-042")
def _():
    old = m.apply_owner_decision(ready_candidate(asset=SHA_C),
                                 owner_decision(SHA_C))
    sup = m.mark_superseded(old, by_candidate_id=selected().candidate_id)
    with pytest.raises(ValueError, match="invalid candidate transition"):
        m._transition(sup, "PROPOSED")


@case("RC-043")
def _():
    env = fresh_env()
    cand = ready_candidate()  # never Owner-selected
    txn = propose_for(cand, env)
    with pytest.raises(ValueError, match="C7_OWNER_SELECTS_EXACT_SHA"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))
    assert env.current_manifest_id == "edit_pred"


@case("RC-044")
def _():
    cand = m.record_technical_validation(
        m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                         repair_reason="r", asset_sha256=SHA_B,
                         generation_semantic_identity="g"),
        {"decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B})
    other = m.make_candidate(source_canonical_take="take_X",
                             affected_shot="SX", repair_reason="r",
                             asset_sha256=SHA_C,
                             generation_semantic_identity="g2")
    other_review = review_with(other)
    with pytest.raises(ValueError, match="another candidate"):
        m.attach_quality_review(cand, other_review)


# =======================================================================
# PROMOTION_TRANSACTION
# =======================================================================

@case("RC-045")
def _():
    env = fresh_env()
    cand = selected()
    txn = propose_for(cand, env)
    drifted = m.SyntheticFilmEnvironment(
        master_version="master-v2",
        manifest=env.manifest("edit_pred"), takes=dict(env.takes),
        asset_digests=dict(env.asset_digests))
    with pytest.raises(ValueError, match="wrong canonical predecessor"):
        m.execute_promotion(txn, candidate=cand, environment=drifted,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


@case("RC-046")
def _():
    env = fresh_env()
    cand = selected()
    txn = propose_for(cand, env)
    env.manifests["edit_moved"] = env.manifest("edit_pred")
    env.current_manifest_id = "edit_moved"
    with pytest.raises(ValueError, match="stale EditManifest"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


@case("RC-047")
def _():
    env = fresh_env()
    cand = ready_candidate()
    txn = propose_for(cand, env)
    with pytest.raises(ValueError, match="C7_OWNER_SELECTS_EXACT_SHA"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


@case("RC-048")
def _():
    env = fresh_env()
    cand = m.QualityRepairCandidate.model_validate(
        {**selected().model_dump(mode="json"),
         "technical_qc_receipt": {"decision": "fail", "qc_report_id": "q",
                                  "asset_sha256": SHA_B}})
    txn = propose_for(cand, env)
    with pytest.raises(ValueError, match="C2_TECHNICAL_QC_PASSES"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


@case("RC-049")
def _():
    class FlakyEnv(m.SyntheticFilmEnvironment):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.calls = 0

        def preview_rebuild(self, manifest_payload):
            self.calls += 1
            receipt = super().preview_rebuild(manifest_payload)
            if self.calls > 1:
                receipt = dict(receipt)
                receipt["master_sha256"] = "f" * 64
            return receipt

    base = fresh_env()
    env = FlakyEnv(master_version=base.master_version,
                   manifest=base.manifest(base.current_manifest_id),
                   takes=dict(base.takes),
                   asset_digests=dict(base.asset_digests))
    cand = selected()
    txn = propose_for(cand, env)
    with pytest.raises(ValueError, match="not deterministic"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


@case("RC-050")
def _():
    env = fault_env(fail_commit=True)
    digest = env.canonical_state_digest()
    cand = selected()
    txn = propose_for(cand, env)
    with pytest.raises(RuntimeError, match="simulated rebuild/commit"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))
    assert env.canonical_state_digest() == digest
    assert env.current_manifest_id == "edit_pred"


@case("RC-051")
def _():
    env = fault_env(partial_write_then_fail=True)
    digest = env.canonical_state_digest()
    cand = selected()
    txn = propose_for(cand, env)
    with pytest.raises(RuntimeError, match="partial write"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))
    assert env.canonical_state_digest() == digest


@case("RC-052")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    replay = m.PromotionTransaction.model_validate(
        txn_c.model_dump(mode="json"))
    with pytest.raises(ValueError, match="only PROPOSED may execute"):
        m.execute_promotion(replay, candidate=cand, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))


@case("RC-053")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    failed = txn_c.with_state("FAILED", {})
    with pytest.raises(ValueError, match="only PROPOSED may execute"):
        m.execute_promotion(failed, candidate=cand, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))


@case("RC-054")
def _():
    with pytest.raises(ValidationError):
        m.PredecessorBinding(selected_take_id="take_A", shot_id="S1",
                             asset_sha256=SHA_A)


@case("RC-055")
def _():
    env = fresh_env()
    cand = selected()
    txn = propose_for(cand, env)
    pred = env.manifest("edit_pred")
    clipped = {**pred, "clips": [pred["clips"][1]]}
    with pytest.raises(ValueError, match="not in predecessor"):
        m.build_successor_manifest(clipped, txn, candidate_take_id="t",
                                   candidate_asset_id="a")


@case("RC-056")
def _():
    env = fresh_env()
    cand = selected()
    txn = propose_for(cand, env)
    tampered = m.PromotionTransaction.model_validate(
        {**txn.model_dump(mode="json"), "successor_manifest_id": "edit_wrong"})
    with pytest.raises(ValueError, match="successor manifest identity"):
        m.execute_promotion(tampered, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


# =======================================================================
# ROLLBACK
# =======================================================================

@case("RC-057")
def _():
    env = fresh_env()
    cand = selected()
    txn = propose_for(cand, env)
    with pytest.raises(ValueError, match="COMMITTED"):
        m.rollback_promotion(txn, environment=env,
                             promotion_ledger=m.HashChainLedger())


@case("RC-058")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    failed = txn_c.with_state("FAILED", {})
    with pytest.raises(ValueError, match="COMMITTED"):
        m.rollback_promotion(failed, environment=env, promotion_ledger=ledger)


@case("RC-059")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    env.current_manifest_id = "edit_pred"  # silent drift off successor
    with pytest.raises(ValueError, match="rollback mismatch"):
        m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)


@case("RC-060")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    rb = m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)
    assert rb["restored_master_sha256"] == receipt["master_before_sha256"]
    assert env.current_manifest_id == "edit_pred"
    assert env.canonical_master_sha256() == receipt["master_before_sha256"]


@case("RC-061")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    rb = m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)
    assert rb["regeneration_required"] is False
    assert receipt["master_before_sha256"] and \
        env.asset_retained(receipt["master_before_sha256"]) or \
        env.asset_retained(txn_c.predecessor.asset_sha256)
    assert not hasattr(env, "generate")  # no regeneration capability


@case("RC-062")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)
    with pytest.raises(ValueError, match="already rolled back"):
        m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)


@case("RC-063")
def _():
    env = fresh_env()
    env.asset_digests.pop("assetA")
    cand = selected()
    txn = propose_for(cand, env)
    with pytest.raises(ValueError, match="C10_ROLLBACK_TARGET_RETAINED"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


@case("RC-064")
def _():
    env, cand, ledger, txn_c, receipt = committed_run()
    ledger.events[0]["receipt"]["selected_exact_asset_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.verify()


# =======================================================================
# DEBT_LIFECYCLE
# =======================================================================

@case("RC-065")
def _():
    ledger = m.DebtClosureLedger()
    proposed = m.make_candidate(source_canonical_take="take_A",
                                affected_shot="S1", repair_reason="r",
                                asset_sha256=SHA_B,
                                generation_semantic_identity="g",
                                quality_debt_ids=["QD-001"])
    with pytest.raises(ValueError, match="QUALITY_REVIEW_READY"):
        ledger.record_improvement_candidate("QD-001", proposed)
    assert ledger.state("QD-001") == "ACTIVE"


@case("RC-066")
def _():
    ledger = m.DebtClosureLedger()
    cand = ready_candidate()
    ledger.record_improvement_candidate("QD-001", cand)
    assert ledger.state("QD-001") == "IMPROVEMENT_CANDIDATE"
    with pytest.raises(ValueError, match="candidate alone"):
        ledger.record_owner_accepted_resolution(
            "QD-001", candidate=cand,
            promotion_receipt={"candidate_id": cand.candidate_id,
                               "transaction_id": "QPT-x"})


@case("RC-067")
def _():
    ledger = m.DebtClosureLedger()
    ledger.record_improvement_candidate("QD-001", ready_candidate())
    with pytest.raises(ValueError, match="invalid debt lifecycle"):
        ledger.transition("QD-001", "CLOSED")


@case("RC-068")
def _():
    ledger = m.DebtClosureLedger()
    cand = selected()
    ledger.record_improvement_candidate("QD-001", cand)
    with pytest.raises(ValueError, match="promotion receipt"):
        ledger.record_owner_accepted_resolution(
            "QD-001", candidate=cand, promotion_receipt={})


@case("RC-069")
def _():
    ledger = m.DebtClosureLedger()
    cand = selected()
    ledger.record_improvement_candidate("QD-001", cand)
    ledger.record_owner_accepted_resolution(
        "QD-001", candidate=cand,
        promotion_receipt={"candidate_id": cand.candidate_id,
                           "transaction_id": "QPT-abcd1234abcd1234"})
    with pytest.raises(ValueError, match="verification receipt"):
        ledger.record_closed("QD-001", verification={"verified": False})


@case("RC-070")
def _():
    ledger = m.DebtClosureLedger()
    stray = ready_candidate(debt_ids=["QD-002"])
    with pytest.raises(ValueError, match="does not target"):
        ledger.record_improvement_candidate("QD-001", stray)


@case("RC-071")
def _():
    ledger = m.DebtClosureLedger()
    cand = ready_candidate()
    ledger.record_improvement_candidate("QD-001", cand)
    sel = m.apply_owner_decision(cand, owner_decision(SHA_B))
    receipt = {"candidate_id": sel.candidate_id,
               "transaction_id": "QPT-abcd1234abcd1234"}
    ledger.record_owner_accepted_resolution("QD-001", candidate=sel,
                                            promotion_receipt=receipt)
    ledger.record_closed("QD-001", verification={
        "verified": True, "transaction_id": receipt["transaction_id"]})
    assert ledger.state("QD-001") == "CLOSED"
    assert ledger.state("QD-002") == "ACTIVE"  # untouched debt stays


@case("RC-072")
def _():
    registry = ROOT / ("projects/flow_v1_completion_quality_debt_freeze_019/"
                       "quality_debt_registry_019.json")
    before = registry.read_bytes()
    ledger = m.DebtClosureLedger()
    ledger.record_improvement_candidate("QD-001", ready_candidate())
    ledger.transition("QD-002", "DEFERRED")
    assert registry.read_bytes() == before


# =======================================================================
# EXPERIMENT_ADMISSION
# =======================================================================

@case("RC-073")
def _():
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.admission_gate(None, known_debt_ids=["QD-001"])


@case("RC-074")
def _():
    receipt = m.make_experiment_admission_receipt(
        **admission_kwargs(canonical_baseline_sha256="e" * 40))
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.admission_gate(receipt, known_debt_ids=["QD-001"])


@case("RC-075")
def _():
    receipt = m.make_experiment_admission_receipt(
        **admission_kwargs(target_quality_debt_ids=["QD-777"]))
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.admission_gate(receipt, known_debt_ids=["QD-001"])


@case("RC-076")
def _():
    receipt = m.make_experiment_admission_receipt(
        **admission_kwargs(hypothesis=""))
    with pytest.raises(ValidationError):
        m.admission_gate(receipt, known_debt_ids=["QD-001"])


@case("RC-077")
def _():
    receipt = m.make_experiment_admission_receipt(
        **admission_kwargs(max_generate_budget=-1))
    with pytest.raises(ValidationError):
        m.admission_gate(receipt, known_debt_ids=["QD-001"])


@case("RC-078")
def _():
    receipt = m.make_experiment_admission_receipt(
        **admission_kwargs(variables_held_constant=[]))
    with pytest.raises(ValidationError):
        m.admission_gate(receipt, known_debt_ids=["QD-001"])


@case("RC-079")
def _():
    receipt = m.make_experiment_admission_receipt(
        **admission_kwargs(acceptance_criteria=[]))
    with pytest.raises(ValidationError):
        m.admission_gate(receipt, known_debt_ids=["QD-001"])


@case("RC-080")
def _():
    receipt = m.make_experiment_admission_receipt(**admission_kwargs())
    out = m.admission_gate(receipt, known_debt_ids=["QD-001", "QD-002"])
    assert out["status"] == "ADMITTED"


# =======================================================================
# V1_BASELINE_IMMUTABILITY
# =======================================================================

@case("RC-081")
def _():
    proof = json.loads(
        (ROOT / "projects/flow_v1_completion_quality_debt_freeze_019/"
         "canonical_no_change_019.json").read_text(encoding="utf-8"))
    assert m.CANONICAL_MASTER_SHA256 == proof["master_sha256"]
    assert proof["result"] == "UNCHANGED"
    assert m.QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"


@case("RC-082")
def _():
    registry = ROOT / ("projects/flow_v1_completion_quality_debt_freeze_019/"
                       "quality_debt_registry_019.json")
    before = registry.read_bytes()
    assert m.load_frozen_debt_ids(ROOT) == ["QD-001", "QD-002", "QD-003",
                                            "QD-004", "QD-005"]
    assert registry.read_bytes() == before


@case("RC-083")
def _():
    decision_file = ROOT / (
        "projects/flow_v1_completion_quality_debt_freeze_019/"
        "owner_quality_decision_019.json")
    before = decision_file.read_bytes()
    cand = ready_candidate()
    m.apply_owner_decision(cand, owner_decision(SHA_B))
    m.evaluate_acceptance(cand, owner_decision=owner_decision(SHA_B))
    assert decision_file.read_bytes() == before


@case("RC-084")
def _():
    public = [n for n, v in vars(m).items()
              if callable(v) and not n.startswith("_")]
    assert not any("generate" in n.lower() for n in public)
    assert not hasattr(m, "Generate") and not hasattr(m, "generate_video")


@case("RC-085")
def _():
    ledger = m.HashChainLedger()
    cand = ready_candidate()
    cand = m.apply_owner_decision(cand, owner_decision(SHA_B))
    assert cand.owner_decision_state == "OWNER_SELECTED"
    assert ledger.events == []  # governance alone promotes nothing
    env = fresh_env()
    assert env.current_manifest_id == "edit_pred"


@case("RC-086")
def _():
    doc = (ROOT / "docs/quality-v2/QUALITY_V2_SOT.md").read_text(
        encoding="utf-8")
    assert m.QUALITY_V2_GOAL in doc
    assert m.QUALITY_V2_CANONICAL_BASELINE in doc
    for dim in m.QUALITY_DIMENSIONS:
        assert dim in doc


@case("RC-088")
def _():
    with pytest.raises(ValidationError):
        m.make_candidate(source_canonical_take="take_A", affected_shot="S1",
                         repair_reason="r", asset_sha256=SHA_B,
                         generation_semantic_identity="")
    assert m.EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"


@case("RC-089")
def _():
    env = fault_env(fail_commit=True)
    cand = selected()
    ledger = m.HashChainLedger()
    txn = propose_for(cand, env)
    with pytest.raises(RuntimeError):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))
    env.fail_commit = False
    with pytest.raises(ValueError, match="blind retry refused"):
        m.execute_promotion(txn, candidate=cand, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))


# =======================================================================
# parametrized proof over the frozen case table
# =======================================================================

CASES = m.list_recovery_cases()


@pytest.mark.parametrize("item", CASES, ids=lambda c: c["case_id"])
def test_recovery_case_executes_live_guard(item):
    info = m.list_recovery_cases()
    entry = next(c for c in info if c["case_id"] == item["case_id"])
    executor = EXECUTORS.get(entry["case_id"])
    assert executor is not None, \
        f"no live executor for {entry['case_id']} ({entry['scenario']})"
    executor()


def test_every_case_has_executor_and_matrix_matches():
    assert len(EXECUTORS) == len(CASES) >= 80
    doc = json.loads(
        (ROOT / "projects/quality_v2_repair_selection_policy_001/"
         "recovery_matrix_v2_001.json").read_text(encoding="utf-8"))
    assert [c["case_id"] for c in doc["cases"]] == \
        [c["case_id"] for c in CASES]
    for entry in CASES:
        assert entry["expected"] in {"REFUSED", "FAILED_CLOSED", "PROVEN",
                                     "UNCHANGED"}
