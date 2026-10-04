"""QUALITY-V2-001 policy tests: SOT bindings, candidate model, review
contract, acceptance policy, decision rights, admission gate, debt
lifecycle, ranking/matrix evidence consistency."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import film_pipeline.quality_repair_v2 as qv2
from film_pipeline import quality_repair_v2 as m
from film_pipeline.owner_review import OwnerReviewDecision, \
    make_owner_decision, refuse_worker_origin

ROOT = Path(__file__).resolve().parents[1]
D19 = ROOT / "projects/flow_v1_completion_quality_debt_freeze_019"
P2 = ROOT / "projects/quality_v2_repair_selection_policy_001"

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


class FakeRequest:
    review_request_id = "OWNER-REV-V2TEST"

    def __init__(self, asset_sha):
        self.asset_sha = asset_sha

    def bindings(self):
        return {"asset_sha256": self.asset_sha}


def owner_decision(asset_sha=SHA_B, decision="ACCEPT", note="",
                   owner_identity="OWNER"):
    return make_owner_decision(request=FakeRequest(asset_sha),
                               decision=decision, note=note,
                               owner_identity=owner_identity)


def ready_candidate(*, baseline=SHA_A, asset=SHA_B, debt_ids=("QD-001",),
                    extra_findings=(), source_take="take_A",
                    shot="S1"):
    cand = m.make_candidate(source_canonical_take=source_take,
                            affected_shot=shot,
                            repair_reason="causal logic redesign",
                            asset_sha256=asset,
                            generation_semantic_identity="out-v2test-1",
                            quality_debt_ids=list(debt_ids))
    cand = m.record_technical_validation(cand, {
        "decision": "pass", "qc_report_id": "qcr_v2test",
        "asset_sha256": asset})
    review = m.build_review_receipt(
        candidate=cand, baseline_asset_sha256=baseline,
        target_dimensions=["ACTION_CAUSALITY"],
        findings=[{"dimension": "ACTION_CAUSALITY",
                   "verdict": "IMPROVED", "severity": "NONE",
                   "evidence": ["trigger/goal/outcome readable blind"]},
                  *extra_findings],
        review_source="ADVISORY_WORKER")
    return m.attach_quality_review(
        cand, review,
        identity_receipt={"identity_continuity": "UNCHANGED",
                          "verified_by": "identity-compare-v1"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "edit_pred",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "editorial-v1"})


def fresh_env():
    manifest = {"edit_manifest_id": "edit_pred", "project_id": "p",
                "clips": [
                    {"order": 1, "shot_id": "S1",
                     "selected_take_id": "take_A", "asset_id": "assetA"},
                    {"order": 2, "shot_id": "S2",
                     "selected_take_id": "take_B", "asset_id": "assetB"}]}
    return m.SyntheticFilmEnvironment(
        master_version="master-v1", manifest=manifest,
        takes={"take_A": {"selected_take_id": "take_A", "shot_id": "S1",
                          "asset_sha256": SHA_A},
               "take_B": {"selected_take_id": "take_B", "shot_id": "S2",
                          "asset_sha256": SHA_B}},
        asset_digests={"assetA": SHA_A, "assetB": SHA_B,
                       "assetC": SHA_C})


# --- frozen SOT bindings ------------------------------------------------

def test_01_sot_doc_exists_and_binds_goal_baseline_dimensions():
    doc = (ROOT / "docs/quality-v2/QUALITY_V2_SOT.md").read_text(
        encoding="utf-8")
    assert m.QUALITY_V2_GOAL in doc
    assert m.QUALITY_V2_CANONICAL_BASELINE in doc
    for dim in m.QUALITY_DIMENSIONS:
        assert dim in doc
    assert "never" in doc and "single quality score" in doc


def test_02_frozen_constants_and_019_master_binding():
    assert m.QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
    proof = json.loads((D19 / "canonical_no_change_019.json").read_text(
        encoding="utf-8"))
    assert m.CANONICAL_MASTER_SHA256 == proof["master_sha256"]
    assert proof["result"] == "UNCHANGED"
    assert m.V1_COMPLETION_RECEIPT == "AI_FILM_PIPELINE_V1_COMPLETION_019"


def test_03_ten_dimensions_frozen_no_collapse():
    assert m.QUALITY_DIMENSIONS == (
        "NARRATIVE_LOGIC", "ACTION_CAUSALITY", "SHOT_DESIGN", "IDENTITY",
        "BODY_PROPORTION", "PERFORMANCE", "BLOCKING", "CAMERA",
        "TEMPORAL_MOTION", "EDITORIAL_FIT")
    # no aggregate-score machinery anywhere in the public surface
    public = [n for n, v in vars(m).items()
              if callable(v) and not n.startswith("_")]
    assert not any("score" in n.lower() or "aggregate" in n.lower()
                   for n in public)


def test_04_frozen_debt_registry_readable_and_unouched():
    before = (D19 / "quality_debt_registry_019.json").read_bytes()
    ids = m.load_frozen_debt_ids(ROOT)
    assert ids == ["QD-001", "QD-002", "QD-003", "QD-004", "QD-005"]
    after = (D19 / "quality_debt_registry_019.json").read_bytes()
    assert before == after


# --- candidate model ------------------------------------------------------

def test_05_candidate_identity_deterministic_and_state_default():
    c1 = m.make_candidate(source_canonical_take="take_A",
                          affected_shot="S1", repair_reason="r",
                          asset_sha256=SHA_B,
                          generation_semantic_identity="out-1")
    c2 = m.make_candidate(source_canonical_take="take_A",
                          affected_shot="S1", repair_reason="r",
                          asset_sha256=SHA_B,
                          generation_semantic_identity="out-1")
    assert c1.candidate_id == c2.candidate_id
    assert c1.owner_decision_state == "PROPOSED"
    # identical identity cannot yield a second distinct candidate id
    assert c1.candidate_id != m.make_candidate(
        source_canonical_take="take_A", affected_shot="S1", repair_reason="r",
        asset_sha256=SHA_C, generation_semantic_identity="out-1").candidate_id


def test_06_invalid_candidate_states_refused():
    with pytest.raises(ValidationError, match="OWNER_SELECTED requires"):
        m.QualityRepairCandidate(
            **{**ready_candidate().model_dump(mode="json"),
               "owner_decision_state": "OWNER_SELECTED",
               "owner_decision_id": ""})
    with pytest.raises(ValidationError, match="SUPERSEDED requires"):
        m.QualityRepairCandidate(
            **{**ready_candidate().model_dump(mode="json"),
               "owner_decision_state": "SUPERSEDED"})


def test_07_state_machine_skip_transitions_refused():
    cand = m.make_candidate(source_canonical_take="take_A",
                            affected_shot="S1", repair_reason="r",
                            asset_sha256=SHA_B,
                            generation_semantic_identity="out-1")
    with pytest.raises(ValueError, match="invalid candidate transition"):
        m._transition(cand, "OWNER_SELECTED")
    with pytest.raises(ValueError, match="invalid candidate transition"):
        m._transition(cand, "QUALITY_REVIEW_READY")
    with pytest.raises(ValueError, match="invalid candidate transition"):
        m._transition(ready_candidate(), "SUPERSEDED")
    rejected = m.apply_owner_decision(ready_candidate(),
                                      owner_decision(decision="REJECT"))
    with pytest.raises(ValueError, match="invalid candidate transition"):
        m._transition(rejected, "PROPOSED")


def test_08_technical_validation_and_refusal():
    cand = m.make_candidate(source_canonical_take="take_A",
                            affected_shot="S1", repair_reason="r",
                            asset_sha256=SHA_B,
                            generation_semantic_identity="out-1")
    with pytest.raises(ValueError, match="did not pass"):
        m.record_technical_validation(cand, {
            "decision": "fail", "qc_report_id": "q", "asset_sha256": SHA_B})
    with pytest.raises(ValueError, match="different asset sha256"):
        m.record_technical_validation(cand, {
            "decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_C})
    refusal = m.record_technical_refusal(cand, {"reason": "decode failed"})
    assert refusal["advance_blocked"] is True
    assert refusal["state_after"] == "PROPOSED"


def test_09_attach_review_guards():
    cand = m.make_candidate(source_canonical_take="take_A",
                            affected_shot="S1", repair_reason="r",
                            asset_sha256=SHA_B,
                            generation_semantic_identity="out-1")
    review = m.build_review_receipt(
        candidate=cand, baseline_asset_sha256=SHA_A,
        target_dimensions=["ACTION_CAUSALITY"],
        findings=[{"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
                   "severity": "NONE", "evidence": ["legible"]}],
        review_source="ADVISORY_WORKER")
    with pytest.raises(ValueError, match="TECHNICALLY_VALID"):
        m.attach_quality_review(cand, review)
    tech = m.record_technical_validation(cand, {
        "decision": "pass", "qc_report_id": "q", "asset_sha256": SHA_B})
    other = m.make_candidate(source_canonical_take="take_X",
                             affected_shot="SX", repair_reason="r",
                             asset_sha256=SHA_C,
                             generation_semantic_identity="out-2")
    other_review = m.build_review_receipt(
        candidate=other, baseline_asset_sha256=SHA_A,
        target_dimensions=["ACTION_CAUSALITY"],
        findings=[{"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
                   "severity": "NONE", "evidence": ["legible"]}],
        review_source="ADVISORY_WORKER")
    with pytest.raises(ValueError, match="another candidate"):
        m.attach_quality_review(tech, other_review)
    with pytest.raises(ValueError, match="canonical asset"):
        m.attach_quality_review(tech, m.build_review_receipt(
            candidate=tech, baseline_asset_sha256=SHA_B,
            target_dimensions=["ACTION_CAUSALITY"],
            findings=[{"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
                       "severity": "NONE", "evidence": ["legible"]}],
            review_source="ADVISORY_WORKER"))


def test_10_review_receipt_validation_rules():
    cand = m.make_candidate(source_canonical_take="take_A",
                            affected_shot="S1", repair_reason="r",
                            asset_sha256=SHA_B,
                            generation_semantic_identity="out-1")
    with pytest.raises(ValidationError, match="must be IMPROVED"):
        m.build_review_receipt(
            candidate=cand, baseline_asset_sha256=SHA_A,
            target_dimensions=["TEMPORAL_MOTION"],
            findings=[], review_source="ADVISORY_WORKER")
    full = m.build_review_receipt(
        candidate=cand, baseline_asset_sha256=SHA_A,
        target_dimensions=["ACTION_CAUSALITY"],
        findings=[
            {"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
             "severity": "NONE", "evidence": ["legible"]},
            {"dimension": "IDENTITY", "verdict": "REGRESSED",
             "severity": "HIGH", "evidence": ["face drifted"]}],
        review_source="ADVISORY_WORKER")
    assert len(full.findings) == 10
    with pytest.raises(ValidationError, match="duplicate finding"):
        data = full.model_dump(mode="json")
        data["findings"][1] = dict(data["findings"][0])
        m.QualityReviewReceipt.model_validate(data)
    with pytest.raises(ValidationError):
        data = full.model_dump(mode="json")
        data["findings"][0]["dimension"] = "NOT_A_DIMENSION"
        m.QualityReviewReceipt.model_validate(data)


def test_11_review_tamper_detection_and_tradeoffs():
    cand = m.make_candidate(source_canonical_take="take_A",
                            affected_shot="S1", repair_reason="r",
                            asset_sha256=SHA_B,
                            generation_semantic_identity="out-1")
    review = m.build_review_receipt(
        candidate=cand, baseline_asset_sha256=SHA_A,
        target_dimensions=["ACTION_CAUSALITY"],
        findings=[
            {"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
             "severity": "NONE", "evidence": ["legible"]},
            {"dimension": "PERFORMANCE", "verdict": "REGRESSED",
             "severity": "LOW", "evidence": ["stiffer than baseline"]}],
        review_source="ADVISORY_WORKER")
    tampered = review.model_dump(mode="json")
    tampered["findings"][0]["evidence"] = ["rewritten after minting"]
    with pytest.raises(ValidationError, match="identity mismatch"):
        m.QualityReviewReceipt.model_validate(tampered)
    summary = review.tradeoff_summary()
    assert summary["ACTION_CAUSALITY"]["verdict"] == "IMPROVED"
    assert summary["PERFORMANCE"]["verdict"] == "REGRESSED"
    assert review.soft_regressions() == ["PERFORMANCE"]
    assert review.hard_blocks() == []


def test_12_hard_blocks_identity_and_high_severity():
    cand = m.make_candidate(source_canonical_take="take_A",
                            affected_shot="S1", repair_reason="r",
                            asset_sha256=SHA_B,
                            generation_semantic_identity="out-1")
    identity_reg = m.build_review_receipt(
        candidate=cand, baseline_asset_sha256=SHA_A,
        target_dimensions=["ACTION_CAUSALITY"],
        findings=[
            {"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
             "severity": "NONE", "evidence": ["legible"]},
            {"dimension": "IDENTITY", "verdict": "REGRESSED",
             "severity": "MEDIUM", "evidence": ["face drifted"]}],
        review_source="ADVISORY_WORKER")
    blocks = identity_reg.hard_blocks()
    assert any("IDENTITY_REGRESSED_UNACCEPTABLE" in b for b in blocks)
    camera_high = m.build_review_receipt(
        candidate=cand, baseline_asset_sha256=SHA_A,
        target_dimensions=["ACTION_CAUSALITY"],
        findings=[
            {"dimension": "ACTION_CAUSALITY", "verdict": "IMPROVED",
             "severity": "NONE", "evidence": ["legible"]},
            {"dimension": "CAMERA", "verdict": "REGRESSED",
             "severity": "HIGH", "evidence": ["coverage broken"]}],
        review_source="ADVISORY_WORKER")
    assert any("CAMERA_REGRESSED_HIGH" in b for b in camera_high.hard_blocks())


# --- owner decision application ------------------------------------------

def test_13_owner_decision_binds_exact_sha_and_states():
    cand = ready_candidate()
    good = owner_decision(SHA_B)
    selected = m.apply_owner_decision(cand, good)
    assert selected.owner_decision_state == "OWNER_SELECTED"
    assert selected.owner_decision_id == good.decision_id
    with pytest.raises(ValueError, match="EXACT candidate asset sha256"):
        m.apply_owner_decision(cand, owner_decision(SHA_C))
    with pytest.raises(ValueError, match="requires a QUALITY_REVIEW_READY"):
        m.apply_owner_decision(selected, owner_decision(SHA_B))
    rejected = m.apply_owner_decision(ready_candidate(),
                                      owner_decision(decision="REJECT"))
    assert rejected.owner_decision_state == "OWNER_REJECTED"
    deferred = m.apply_owner_decision(ready_candidate(),
                                      owner_decision(decision="DEFER"))
    assert deferred.owner_decision_state == "DEFERRED"


def test_14_owner_decision_guards_identity_and_origin():
    cand = ready_candidate()
    with pytest.raises(ValueError, match="only the Owner identity"):
        m.apply_owner_decision(cand, owner_decision(owner_identity="LEAD"))
    with pytest.raises(ValueError, match="non-Owner identity"):
        owner_decision(owner_identity="worker-agent-7")
    forged = {"decision": "ACCEPT", "owner_identity": "OWNER",
              "WORKER_REVIEW": "p018-b"}
    with pytest.raises(ValueError, match="non-Owner origin marker"):
        refuse_worker_origin(forged)


def test_15_soft_regression_requires_explicit_tradeoff_note():
    cand = ready_candidate(extra_findings=[
        {"dimension": "PERFORMANCE", "verdict": "REGRESSED",
         "severity": "LOW", "evidence": ["slightly stiffer"]}])
    ack = "TRADEOFF_ACCEPTED=PERFORMANCE"
    with pytest.raises(ValueError, match="trade-off"):
        m.apply_owner_decision(cand, owner_decision(note="looks fine"))
    selected = m.apply_owner_decision(
        cand, owner_decision(note=f"accepting the stiffness cost; {ack}"))
    assert selected.owner_decision_state == "OWNER_SELECTED"


def test_16_identity_receipt_rules():
    cand = ready_candidate()
    review = m.candidate_review(cand)
    with pytest.raises(ValueError, match="unconditionally blocking"):
        m.validate_identity_receipt(
            {"identity_continuity": "REGRESSED", "verified_by": "x"}, review)
    with pytest.raises(ValueError, match="unproven"):
        m.validate_identity_receipt(
            {"identity_continuity": "INCONCLUSIVE", "verified_by": "x"},
            review)
    with pytest.raises(ValueError, match="missing"):
        m.validate_identity_receipt({"verified_by": "x"}, review)
    ok = m.validate_identity_receipt(
        {"identity_continuity": "UNCHANGED", "verified_by": "v"}, review)
    assert ok["identity_continuity"] == "UNCHANGED"


# --- acceptance policy -----------------------------------------------------

def test_17_full_receipts_pass_all_ten_conditions():
    cand = m.apply_owner_decision(ready_candidate(), owner_decision(SHA_B))
    env = fresh_env()
    txn = m.propose_promotion_transaction(candidate=cand, environment=env,
                                          affected_clip_order=1)
    rebuild = env.preview_rebuild(env.manifest("edit_pred"))
    checks = m.evaluate_acceptance(
        cand, owner_decision=owner_decision(SHA_B),
        promotion_ledger=m.HashChainLedger(), environment=env,
        transaction=txn, rebuild_receipt=rebuild)
    assert checks["all_pass"], checks
    assert set(checks["conditions"]) == set(m.ACCEPTANCE_CONDITION_IDS)
    assert len(m.ACCEPTANCE_CONDITION_IDS) == 10


def test_18_acceptance_conditions_fail_independently():
    selected = m.apply_owner_decision(ready_candidate(),
                                      owner_decision(SHA_B))
    dump = selected.model_dump(mode="json")
    # C2: technical fail (candidate otherwise fully selected)
    bad_tech = m.QualityRepairCandidate.model_validate(
        {**dump, "technical_qc_receipt": {"decision": "fail",
                                          "qc_report_id": "q",
                                          "asset_sha256": SHA_B}})
    out = m.evaluate_acceptance(bad_tech, owner_decision=owner_decision(SHA_B))
    assert out["blocked_by"] == ["C2_TECHNICAL_QC_PASSES"]
    # C3: identity receipt missing/unproven
    no_identity = m.QualityRepairCandidate.model_validate(
        {**dump, "identity_receipt": {}})
    out = m.evaluate_acceptance(no_identity,
                                owner_decision=owner_decision(SHA_B))
    assert out["blocked_by"] == ["C3_IDENTITY_WORLD_NO_REGRESSION"]
    # C6: editorial incompatible
    bad_edit = m.QualityRepairCandidate.model_validate(
        {**dump, "editorial_compatibility_receipt": {
            "editorial_compatible": False, "edit_manifest_id": "e",
            "affected_clip_order": 1, "trim_compatible": True,
            "verified_by": "v"}})
    out = m.evaluate_acceptance(bad_edit, owner_decision=owner_decision(SHA_B))
    assert out["blocked_by"] == ["C6_EDITORIAL_FIT_PROVEN"]
    # C7: never owner-selected
    unselected = ready_candidate()
    out = m.evaluate_acceptance(unselected)
    assert out["blocked_by"] == ["C7_OWNER_SELECTS_EXACT_SHA"]
    # C9/C10 pending without transaction context
    out = m.evaluate_acceptance(selected, owner_decision=owner_decision(SHA_B))
    assert out["conditions"]["C9_REBUILD_VERIFIED"]["state"] == "PENDING"
    assert out["conditions"]["C10_ROLLBACK_TARGET_RETAINED"]["state"] == \
        "PENDING"


def test_19_c5_blocks_uncompensated_and_hard_regressions():
    soft = ready_candidate(extra_findings=[
        {"dimension": "CAMERA", "verdict": "REGRESSED", "severity": "LOW",
         "evidence": ["minor reframing"]}])
    out = m.evaluate_acceptance(soft, owner_decision=owner_decision(SHA_B))
    assert "C5_NO_HIGHER_SEVERITY_NEW_DEFECT" in out["blocked_by"]
    hard = ready_candidate(extra_findings=[
        {"dimension": "IDENTITY", "verdict": "REGRESSED", "severity": "LOW",
         "evidence": ["face drifted"]}])
    out = m.evaluate_acceptance(hard, owner_decision=owner_decision(SHA_B))
    assert "C3_IDENTITY_WORLD_NO_REGRESSION" in out["blocked_by"]
    assert "C5_NO_HIGHER_SEVERITY_NEW_DEFECT" in out["blocked_by"]


# --- decision rights --------------------------------------------------------

def test_20_role_permissions_matrix():
    m.authorize("TECH_LEAD", "DEFINE_EXPERIMENT")
    m.authorize("TECH_LEAD", "FREEZE_ACCEPTANCE")
    m.authorize("TECH_LEAD", "VALIDATE_PROOF")
    m.authorize("WORKER", "EXECUTE_EXPERIMENT")
    m.authorize("WORKER", "PRODUCE_EVIDENCE")
    m.authorize("AUTOMATED_QC", "REJECT_TECHNICAL_INVALIDITY")
    m.authorize("OWNER", "SELECT_CANDIDATE")
    m.authorize("OWNER", "ACCEPT_KNOWN_QUALITY_DEBT")
    for role, action in (("WORKER", "DEFINE_EXPERIMENT"),
                         ("WORKER", "SELECT_CANDIDATE"),
                         ("AUTOMATED_QC", "SELECT_CANDIDATE"),
                         ("TECH_LEAD", "SELECT_CANDIDATE"),
                         ("PROVIDER", "EXECUTE_EXPERIMENT"),
                         ("OWNER", "DEFINE_EXPERIMENT")):
        with pytest.raises(ValueError, match="not authorized"):
            m.authorize(role, action)
    for role in ("TECH_LEAD", "WORKER", "AUTOMATED_QC", "OWNER", "PROVIDER"):
        with pytest.raises(ValueError, match="not a grantable role action"):
            m.authorize(role, "PROMOTE_CANDIDATE")


def test_21_advisory_output_can_never_be_an_owner_decision():
    with pytest.raises(ValidationError):
        OwnerReviewDecision(
            decision_id="OWNER-DEC-0123456789abcdef",
            review_request_id="OWNER-REV-V2TEST",
            reviewed_bindings={"asset_sha256": SHA_B},
            decision="ACCEPT", decided_at="2026-10-04T00:00:00Z",
            decision_source="ADVISORY_WORKER", owner_identity="OWNER")


# --- promotion transaction model -------------------------------------------

def test_22_transaction_identity_and_state_transitions():
    env = fresh_env()
    cand = ready_candidate()
    txn = m.propose_promotion_transaction(candidate=cand, environment=env,
                                          affected_clip_order=1)
    assert txn.transaction_id.startswith("QPT-")
    assert txn.successor_manifest_id.startswith("edit_")
    with pytest.raises(ValidationError, match="identity mismatch"):
        m.PromotionTransaction.model_validate(
            {**txn.model_dump(mode="json"), "transaction_id": "QPT-" + "0" * 16})
    moved = txn.with_state("COMMITTED", {"master_after_sha256": SHA_C})
    assert moved.state == "COMMITTED"
    assert moved.promotion_receipt == {"master_after_sha256": SHA_C}


def test_23_successor_manifest_changes_only_affected_clip():
    env = fresh_env()
    cand = ready_candidate()
    txn = m.propose_promotion_transaction(candidate=cand, environment=env,
                                          affected_clip_order=1)
    pred = env.manifest("edit_pred")
    from film_pipeline.quality_repair_v2 import _candidate_take_id, \
        _candidate_asset_id
    computed = m.build_successor_manifest(
        pred, txn, candidate_take_id=_candidate_take_id(cand),
        candidate_asset_id=_candidate_asset_id(cand))
    assert computed["edit_manifest_id"] == txn.successor_manifest_id
    assert computed["clips"][1] == pred["clips"][1]  # untouched clip
    assert computed["clips"][0]["selected_take_id"] != "take_A"
    # affected clip order missing from the predecessor manifest
    clipped = {**pred, "clips": [pred["clips"][1]]}
    with pytest.raises(ValueError, match="not in predecessor"):
        m.build_successor_manifest(clipped, txn, candidate_take_id="t",
                                   candidate_asset_id="a")
    # affected clip belongs to a different shot than the transaction binds
    drifted = {**pred, "clips": [{**pred["clips"][0], "shot_id": "SX"},
                                 pred["clips"][1]]}
    with pytest.raises(ValueError, match="different shot"):
        m.build_successor_manifest(drifted, txn, candidate_take_id="t",
                                   candidate_asset_id="a")


# --- experiment admission gate ----------------------------------------------

def admission_kwargs(**kw):
    base = dict(experiment_id="V2-002",
                target_quality_debt_ids=["QD-001"],
                canonical_baseline_sha256=m.QUALITY_V2_CANONICAL_BASELINE,
                hypothesis="redesigned intent renders legible causality",
                variables_changed=["dramatic_purpose", "beats"],
                variables_held_constant=["provider_route", "character_refs",
                                         "editorial_range"],
                max_generate_budget=2,
                provider_route="qualified-flow-r2v-causal-compact-v1",
                acceptance_criteria=[
                    "blind Owner read of trigger/goal/outcome matches "
                    "authoritative intent"],
                owner_review_surface="blind packet + compare reel",
                rollback_plan="exact predecessor SelectedTake retained")
    base.update(kw)
    return base


def valid_admission(**kw):
    return m.make_experiment_admission_receipt(**admission_kwargs(**kw))


def test_24_admission_gate_paths():
    known = m.load_frozen_debt_ids(ROOT)
    out = m.admission_gate(valid_admission(), known_debt_ids=known)
    assert out["status"] == "ADMITTED"
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.admission_gate(None, known_debt_ids=known)
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.admission_gate(valid_admission(canonical_baseline_sha256="0" * 40),
                         known_debt_ids=known)
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.admission_gate(valid_admission(target_quality_debt_ids=["QD-999"]),
                         known_debt_ids=known)
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.require_experiment_admission(None, known_debt_ids=known,
                                       experiment_id="V2-002")
    # unbounded / negative budgets survive construction (plain dict) but
    # are refused by the gate's model validation
    with pytest.raises(ValidationError):
        m.admission_gate(
            m.make_experiment_admission_receipt(
                **admission_kwargs(max_generate_budget=-1)),
            known_debt_ids=known)
    with pytest.raises(ValidationError):
        m.admission_gate(
            m.make_experiment_admission_receipt(
                **admission_kwargs(max_generate_budget=10_000)),
            known_debt_ids=known)
    # empty hypothesis survives construction but is refused by the gate
    with pytest.raises(ValidationError):
        m.admission_gate(
            m.make_experiment_admission_receipt(
                **admission_kwargs(hypothesis="")), known_debt_ids=known)
    # tampered receipt id is refused on revalidation
    receipt = valid_admission()
    with pytest.raises(ValidationError, match="identity mismatch"):
        m.ExperimentAdmissionReceipt.model_validate(
            {**receipt, "receipt_id": "EXA-" + "0" * 16})
    assert m.ADMISSION_REQUIRED_FROM == "V2-002"


# --- quality debt lifecycle ---------------------------------------------------

def test_25_debt_lifecycle_happy_and_refusals():
    ledger = m.DebtClosureLedger()
    cand = ready_candidate()
    assert ledger.state("QD-001") == "ACTIVE"
    ledger.record_improvement_candidate("QD-001", cand)
    assert ledger.state("QD-001") == "IMPROVEMENT_CANDIDATE"
    with pytest.raises(ValueError, match="candidate alone"):
        ledger.record_owner_accepted_resolution(
            "QD-001", candidate=cand,
            promotion_receipt={"candidate_id": cand.candidate_id,
                               "transaction_id": "QPT-x"})
    with pytest.raises(ValueError, match="invalid debt lifecycle"):
        ledger.transition("QD-001", "CLOSED")
    receipt = {"candidate_id": cand.candidate_id,
               "transaction_id": "QPT-deadbeefdeadbeef"}
    selected = m.apply_owner_decision(cand, owner_decision(SHA_B))
    ledger.record_owner_accepted_resolution("QD-001", candidate=selected,
                                            promotion_receipt=receipt)
    assert ledger.state("QD-001") == "OWNER_ACCEPTED_RESOLUTION"
    with pytest.raises(ValueError, match="verification receipt"):
        ledger.record_closed("QD-001", verification={"verified": False})
    ledger.record_closed("QD-001", verification={
        "verified": True, "transaction_id": receipt["transaction_id"]})
    assert ledger.state("QD-001") == "CLOSED"


def test_26_debt_lifecycle_target_mismatch_and_defer_paths():
    ledger = m.DebtClosureLedger()
    stray = m.make_candidate(source_canonical_take="take_X",
                             affected_shot="SX", repair_reason="r",
                             asset_sha256=SHA_C,
                             generation_semantic_identity="out-x",
                             quality_debt_ids=["QD-002"])
    with pytest.raises(ValueError, match="does not target"):
        ledger.record_improvement_candidate("QD-001", stray)
    proposed = m.make_candidate(source_canonical_take="take_X",
                                affected_shot="SX", repair_reason="r",
                                asset_sha256=SHA_C,
                                generation_semantic_identity="out-x",
                                quality_debt_ids=["QD-001"])
    with pytest.raises(ValueError, match="QUALITY_REVIEW_READY"):
        ledger.record_improvement_candidate("QD-001", proposed)
    ledger.transition("QD-003", "DEFERRED", note="owner defers")
    assert ledger.state("QD-003") == "DEFERRED"
    ledger.transition("QD-003", "ACTIVE")
    ledger.transition("QD-004", "ACCEPTED_DEBT")
    assert ledger.state("QD-004") == "ACCEPTED_DEBT"
    with pytest.raises(ValueError, match="invalid debt lifecycle"):
        ledger.transition("QD-004", "CLOSED")


# --- evidence artifacts --------------------------------------------------------

def test_27_experiment_ranking_computed_and_not_authorized():
    doc = json.loads((P2 / "quality_v2_experiment_priority_001.json")
                     .read_text(encoding="utf-8"))
    ranking = doc["ranking"]
    assert [r["rank"] for r in ranking] == list(range(1, len(ranking) + 1))
    totals = [r["weighted_total"] for r in ranking]
    assert totals == sorted(totals, reverse=True)
    weights = doc["ranking_method"]["weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    for row in ranking:
        expected = round(sum(
            w * (row["criteria"][c]["raw_score"] if c not in
                 doc["ranking_method"]["inverted_criteria"] else
                 6 - row["criteria"][c]["raw_score"])
            for c, w in weights.items()), 4)
        assert row["weighted_total"] == expected
        for crit in row["criteria"].values():
            assert crit["rationale"]
            for rel in crit["cited_artifacts"]:
                assert (ROOT / rel).exists(), rel
    assert doc["recommendation"]["first_experiment"] == \
        "QH-1_action_causality_redesign"
    assert doc["recommendation"]["authorization_state"] == "NOT_AUTHORIZED"
    assert doc["invariants"]["no_generation_in_this_package"] is True
    assert doc["canonical_baseline"] == m.QUALITY_V2_CANONICAL_BASELINE


def test_28_recovery_matrix_evidence_consistent():
    doc = json.loads((P2 / "recovery_matrix_v2_001.json").read_text(
        encoding="utf-8"))
    cases = m.list_recovery_cases()
    assert doc["count"] == len(cases) >= 80
    assert [c["case_id"] for c in doc["cases"]] == \
        [c["case_id"] for c in cases]
    assert "OWNER_AMBIGUITY_GATE" in doc["external_ambiguity_rule"]
    assert set(doc["required_topic_coverage"].values()) <= \
        {c["case_id"] for c in cases}


def test_29_external_ambiguity_and_governance_surface():
    assert m.EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"
    public = [n for n, v in vars(m).items()
              if callable(v) and not n.startswith("_")]
    assert not any("generate" in n.lower() for n in public)
    assert m.list_recovery_cases.__module__ == m.__name__


def test_30_ranking_tool_and_matrix_tool_deterministic():
    import subprocess
    import sys
    for tool, rel in ((sys.executable, "tools/build_quality_v2_recovery_matrix_001.py"),):
        out = subprocess.run(
            [tool, str(ROOT / rel)], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
