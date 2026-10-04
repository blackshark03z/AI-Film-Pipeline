"""QUALITY-V2-001 promotion transaction + rollback proofs on the
synthetic fixture (zero live canonical mutation)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import film_pipeline.quality_repair_v2 as m

from test_quality_v2_repair_policy_001 import (  # noqa: F401
    SHA_A, SHA_B, SHA_C, FakeRequest, fresh_env, owner_decision,
    ready_candidate)


def fault_env(**overrides):
    """Fresh synthetic environment with fault-injection switches."""
    base = fresh_env()
    env = m.FaultInjectionEnvironment(
        master_version=base.master_version,
        manifest=base.manifest(base.current_manifest_id),
        takes=dict(base.takes), asset_digests=dict(base.asset_digests))
    for key, value in overrides.items():
        setattr(env, key, value)
    return env


def select_candidate(**kw):
    return m.apply_owner_decision(ready_candidate(**kw),
                                  owner_decision(kw.get("asset", SHA_B)))


def run_promotion(env=None, candidate=None, ledger=None, **kw):
    env = env or fresh_env()
    candidate = candidate or select_candidate(**kw)
    ledger = ledger or m.HashChainLedger()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    receipt = m.execute_promotion(txn, candidate=candidate,
                                  environment=env,
                                  promotion_ledger=ledger,
                                  owner_decision=owner_decision(
                                      candidate.asset_sha256))
    return env, candidate, ledger, txn, receipt


# --- canonical promotion --------------------------------------------------

def test_01_promotion_moves_authority_atomically_with_receipt():
    env, candidate, ledger, txn, receipt = run_promotion()
    assert env.current_manifest_id == txn.successor_manifest_id
    assert env.canonical_master_sha256() == receipt["master_after_sha256"]
    assert receipt["master_before_sha256"] != receipt["master_after_sha256"]
    assert receipt["selected_exact_asset_sha256"] == candidate.asset_sha256
    assert receipt["superseded_selected_take_id"] == "take_A"
    assert receipt["rollback_target"]["selected_take_id"] == "take_A"
    kinds = [e["kind"] for e in ledger.events]
    assert kinds == ["PROMOTION_COMMITTED"]
    committed = ledger.last_of_kind("PROMOTION_COMMITTED")
    assert committed["receipt"] == receipt


def test_02_promotion_is_deterministic_across_replays():
    _, _, _, _, r1 = run_promotion()
    _, _, _, _, r2 = run_promotion()
    assert r1["master_after_sha256"] == r2["master_after_sha256"]
    assert r1["successor_edit_manifest_id"] == r2["successor_edit_manifest_id"]


def test_03_only_affected_scope_rebuilds():
    env = fresh_env()
    candidate = select_candidate()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    pred = env.manifest("edit_pred")
    assert txn.promotion_scope["strategy"] == "AFFECTED_CLIP_ONLY"
    succ_manifest = env.manifest(txn.successor_manifest_id) \
        if txn.successor_manifest_id in env.manifests else \
        m.build_successor_manifest(
            pred, txn,
            candidate_take_id=m._candidate_take_id(candidate),
            candidate_asset_id=m._candidate_asset_id(candidate))
    assert succ_manifest["clips"][1] == pred["clips"][1]
    assert succ_manifest["clips"][0]["selected_take_id"] != "take_A"


# --- rollback ---------------------------------------------------------------

def test_04_rollback_restores_exact_predecessor_without_regeneration():
    env, candidate, ledger, txn, receipt = run_promotion()
    moved_master = env.canonical_master_sha256()
    txn_c = txn.with_state("COMMITTED", receipt)
    rb = m.rollback_promotion(txn_c, environment=env,
                              promotion_ledger=ledger)
    assert rb["restored_master_sha256"] == receipt["master_before_sha256"]
    assert rb["restored_edit_manifest_id"] == "edit_pred"
    assert rb["restored_selected_take_id"] == "take_A"
    assert rb["regeneration_required"] is False
    assert env.current_manifest_id == "edit_pred"
    assert env.canonical_master_sha256() != moved_master
    assert ledger.last_of_kind("ROLLBACK_RECORDED")["receipt"] == rb


def test_05_rollback_refuses_proposed_failed_or_missing_receipt():
    env, candidate, ledger, txn, receipt = run_promotion()
    with pytest.raises(ValueError, match="COMMITTED"):
        m.rollback_promotion(txn, environment=env, promotion_ledger=ledger)
    no_receipt = txn.with_state("COMMITTED")
    with pytest.raises(ValueError, match="COMMITTED"):
        m.rollback_promotion(no_receipt, environment=env,
                             promotion_ledger=ledger)
    failed = txn.with_state("FAILED", {})
    with pytest.raises(ValueError, match="COMMITTED"):
        m.rollback_promotion(failed, environment=env, promotion_ledger=ledger)


def test_06_rollback_mismatch_is_surfaced_not_absorbed():
    env, candidate, ledger, txn, receipt = run_promotion()
    txn_c = txn.with_state("COMMITTED", receipt)
    # the environment silently drifts off the successor state
    env.current_manifest_id = "edit_pred"
    with pytest.raises(ValueError, match="rollback mismatch"):
        m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)


def test_07_double_rollback_refused():
    env, candidate, ledger, txn, receipt = run_promotion()
    txn_c = txn.with_state("COMMITTED", receipt)
    m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)
    with pytest.raises(ValueError, match="already rolled back"):
        m.rollback_promotion(txn_c, environment=env, promotion_ledger=ledger)


# --- failure paths: canonical authority stays on the old take ---------------

def test_08_rebuild_failure_leaves_canonical_authority_unchanged():
    env = fault_env(fail_commit=True)
    digest_before = env.canonical_state_digest()
    candidate = select_candidate()
    ledger = m.HashChainLedger()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    with pytest.raises(RuntimeError, match="simulated rebuild/commit"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(candidate.asset_sha256))
    assert env.canonical_state_digest() == digest_before
    assert env.current_manifest_id == "edit_pred"
    assert ledger.last_of_kind("PROMOTION_FAILED")["transaction_id"] == \
        txn.transaction_id


def test_09_partial_write_torn_down_no_mixed_canonical_state():
    env = fault_env(partial_write_then_fail=True)
    digest_before = env.canonical_state_digest()
    candidate = select_candidate()
    ledger = m.HashChainLedger()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    with pytest.raises(RuntimeError, match="partial write"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(candidate.asset_sha256))
    assert env.canonical_state_digest() == digest_before
    assert env.takes.get(m._candidate_take_id(candidate)) is None


def test_10_wrong_canonical_predecessor_refused():
    env = fresh_env()
    candidate = select_candidate()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    # a DIFFERENT lineage (different master version) whose master does
    # not match the transaction's predecessor binding
    drifted = m.SyntheticFilmEnvironment(
        master_version="master-v2",
        manifest={"edit_manifest_id": "edit_pred", "project_id": "p",
                  "clips": [{"order": 1, "shot_id": "S1",
                             "selected_take_id": "take_A",
                             "asset_id": "assetA"},
                            {"order": 2, "shot_id": "S2",
                             "selected_take_id": "take_B",
                             "asset_id": "assetB"}]},
        takes=dict(env.takes), asset_digests=dict(env.asset_digests))
    assert drifted.canonical_master_sha256() != \
        txn.predecessor.master_sha256
    with pytest.raises(ValueError, match="wrong canonical predecessor"):
        m.execute_promotion(txn, candidate=candidate, environment=drifted,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


def test_11_stale_edit_manifest_refused():
    env = fresh_env()
    candidate = select_candidate()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    # canonical manifest moved after the transaction was proposed
    env.manifests["edit_moved"] = env.manifest("edit_pred")
    env.manifests["edit_moved"]["clips"][0]["notes"] = "drift"
    env.current_manifest_id = "edit_moved"
    with pytest.raises(ValueError, match="stale EditManifest"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


def test_12_unselected_or_failing_candidate_never_promotes():
    env = fresh_env()
    candidate = ready_candidate()  # QUALITY_REVIEW_READY, no Owner decision
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    ledger = m.HashChainLedger()
    with pytest.raises(ValueError, match="C7_OWNER_SELECTS_EXACT_SHA"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))
    assert env.current_manifest_id == "edit_pred"
    assert ledger.last_of_kind("PROMOTION_REFUSED")["blocked_by"] == \
        ["C7_OWNER_SELECTS_EXACT_SHA"]


def test_13_nondeterministic_rebuild_refused():
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
    candidate = select_candidate()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    with pytest.raises(ValueError, match="not deterministic"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


def test_14_predecessor_bytes_missing_blocks_promotion_c10():
    env = fresh_env()
    env.asset_digests.pop("assetA")  # predecessor bytes gone
    candidate = select_candidate()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    with pytest.raises(ValueError, match="C10_ROLLBACK_TARGET_RETAINED"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


def test_15_candidate_asset_bytes_missing_blocks_promotion():
    env = fresh_env()
    candidate = m.apply_owner_decision(ready_candidate(asset=SHA_C),
                                       owner_decision(SHA_C))
    env.asset_digests["assetC"] = "d" * 64  # candidate bytes unretained
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    with pytest.raises(ValueError, match="candidate asset bytes"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_C))


def test_16_tampered_successor_or_state_refused():
    env2 = fresh_env()
    cand2 = select_candidate()
    txn2 = m.propose_promotion_transaction(candidate=cand2,
                                           environment=env2,
                                           affected_clip_order=1)
    # tampered transaction identity is refused by the model validator
    with pytest.raises(ValidationError, match="identity mismatch"):
        m.PromotionTransaction.model_validate(
            {**txn2.model_dump(mode="json"),
             "transaction_id": "QPT-" + "0" * 16})
    # double execution refused by state
    committed = txn2.with_state("COMMITTED", {"x": 1})
    with pytest.raises(ValueError, match="only PROPOSED may execute"):
        m.execute_promotion(committed, candidate=cand2, environment=env2,
                            promotion_ledger=m.HashChainLedger(),
                            owner_decision=owner_decision(SHA_B))


def test_17_double_execution_refused_via_ledger():
    env = fresh_env()
    candidate = select_candidate()
    ledger = m.HashChainLedger()
    first = m.propose_promotion_transaction(candidate=candidate,
                                            environment=env,
                                            affected_clip_order=1)
    replay = m.propose_promotion_transaction(candidate=candidate,
                                             environment=env,
                                             affected_clip_order=1)
    assert first.transaction_id == replay.transaction_id  # deterministic
    receipt = m.execute_promotion(first, candidate=candidate,
                                  environment=env, promotion_ledger=ledger,
                                  owner_decision=owner_decision(SHA_B))
    with pytest.raises(ValueError, match="already committed"):
        m.execute_promotion(replay, candidate=candidate, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))


def test_18_blind_retry_after_failure_refused():
    env = fault_env(fail_commit=True)
    candidate = select_candidate()
    ledger = m.HashChainLedger()
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    with pytest.raises(RuntimeError):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))
    env.fail_commit = False
    with pytest.raises(ValueError, match="blind retry refused"):
        m.execute_promotion(txn, candidate=candidate, environment=env,
                            promotion_ledger=ledger,
                            owner_decision=owner_decision(SHA_B))


def test_19_ledger_is_append_only_and_tamper_checking(tmp_path):
    path = tmp_path / "promotion_ledger.json"
    env = fresh_env()
    candidate = select_candidate()
    ledger = m.HashChainLedger(path)
    txn = m.propose_promotion_transaction(candidate=candidate,
                                          environment=env,
                                          affected_clip_order=1)
    m.execute_promotion(txn, candidate=candidate, environment=env,
                        promotion_ledger=ledger,
                        owner_decision=owner_decision(SHA_B))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved["events"]) == 1
    ledger.events[0]["receipt"]["selected_exact_asset_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.verify()
    # a reload from disk detects the same tamper
    ledger2 = m.HashChainLedger(path)
    ledger2.events[0]["receipt"]["selected_exact_asset_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="integrity failure"):
        ledger2.verify()


def test_20_supersession_of_old_candidate_after_promotion():
    env, candidate, ledger, txn, receipt = run_promotion()
    # the previously-canonical candidate (a different promoted asset)
    old = m.apply_owner_decision(ready_candidate(asset=SHA_C),
                                 owner_decision(SHA_C))
    superseded = m.mark_superseded(old, by_candidate_id=candidate.candidate_id)
    assert superseded.owner_decision_state == "SUPERSEDED"
    assert superseded.superseded_by == candidate.candidate_id
    with pytest.raises(ValueError, match="cannot supersede itself"):
        m.mark_superseded(old, by_candidate_id=old.candidate_id)
