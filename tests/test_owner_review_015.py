"""Owner review boundary (Package-015 Phase 1-2).

Covers the OwnerReviewRequest/Decision contract plus the twelve frozen
authority-boundary scenarios: worker/model can never decide, stale
bindings fail closed, decisions are immutable without explicit
supersession, decisions never carry provider mutation authority, DEFER
stays unresolved, and decision truth survives a restart.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from film_pipeline.owner_review import (
    OWNER_DECISION_STATES, OwnerDecisionLedger, OwnerReviewDecision,
    OwnerReviewRequest, build_decision_template, import_decision_set,
    make_owner_decision, refuse_worker_origin)


def make_request(rid: str = "OWNER-REV-015-001", asset: str = "a" * 64,
                 take: str = "take_" + "b" * 64) -> OwnerReviewRequest:
    return OwnerReviewRequest(
        review_request_id=rid, project="swordsman_film", scope="SHOT",
        canonical_shot_id="SEQ7_F2", sequence_id="SEQ007_DAYLIGHT_ROAD",
        scene_id="SCENE_F_STORM_GATE",
        shot_spec_identity={"shot_id": "SEQ7_F2", "spec_version": 3,
                            "shot_spec_sha256": "c" * 64},
        selected_take=take, asset_id="asset_" + "d" * 64,
        asset_sha256=asset,
        provider_media_identity="20cfe9c0-e2db-4ab8-b8f3-a7fe04cc136c",
        reference_lineage={"kind": "reproof_reference"},
        editorial_range={"editorial_range_id": "er_" + "e" * 64,
                         "source_in_s": 0.0, "source_out_s": 5.6},
        technical_qc={"gate": "SHOT_PROVEN", "full_decode": True},
        reason_review_required="subjective take quality is an Owner "
                               "judgment",
        created_at="2026-10-04T00:00:00+00:00")


def test_01_contract_request_bindings_and_digest():
    request = make_request()
    bindings = request.bindings()
    assert bindings["asset_sha256"] == "a" * 64
    assert bindings["selected_take"].startswith("take_")
    assert bindings["editorial_range_id"].startswith("er_")
    assert bindings["shot_spec_sha256"] == "c" * 64
    assert request.digest() == request.digest()
    with pytest.raises(Exception):
        # a SHOT request without an exact asset hash is not a request
        make_request(asset="")


def test_02_decision_against_different_asset_hash_fails_closed():
    request = make_request()
    forged = OwnerReviewDecision(
        decision_id="OWNER-DEC-" + "0" * 16,
        review_request_id=request.review_request_id,
        reviewed_bindings={**request.bindings(),
                           "asset_sha256": "9" * 64},
        decision="ACCEPT", decided_at="2026-10-04T00:00:01+00:00",
        decision_source="OWNER", owner_identity="OWNER")
    ledger = OwnerDecisionLedger(Path("state_owner_test_02.json"), [request])
    with pytest.raises(ValueError, match="stale binding"):
        ledger.record(forged)


def test_03_worker_cannot_create_owner_decision():
    request = make_request()
    with pytest.raises(ValueError, match="non-Owner"):
        make_owner_decision(request=request, decision="ACCEPT",
                            owner_identity="worker-semantic-reviewer")
    forged_payload = {"decision": "ACCEPT",
                      "provenance": {"backend_type": "WORKER_REVIEW",
                                     "reviewer_identity": "glmanalyst"}}
    with pytest.raises(ValueError, match="non-Owner origin"):
        refuse_worker_origin(forged_payload)


def test_04_semantic_backend_cannot_create_owner_decision():
    request = make_request()
    model_payload = {"decision": "REJECT", "note": "auto",
                     "source": {"backend_type": "API_MODEL",
                                "backend_id": "some-api-model"}}
    with pytest.raises(ValueError, match="non-Owner origin"):
        refuse_worker_origin(model_payload)
    ledger = OwnerDecisionLedger(Path("state_owner_test_04.json"), [request])
    smuggled = OwnerReviewDecision(
        decision_id="OWNER-DEC-" + "1" * 16,
        review_request_id=request.review_request_id,
        reviewed_bindings=request.bindings(), decision="REJECT",
        note="worker-semantic-reviewer says reject",
        decided_at="2026-10-04T00:00:02+00:00", decision_source="OWNER",
        owner_identity="OWNER")
    with pytest.raises(ValueError, match="non-Owner origin"):
        ledger.record(smuggled)


def test_05_stale_take_decision_refused():
    request = make_request()
    stale = OwnerReviewDecision(
        decision_id="OWNER-DEC-" + "2" * 16,
        review_request_id=request.review_request_id,
        reviewed_bindings={**request.bindings(),
                           "selected_take": "take_" + "f" * 64},
        decision="ACCEPT", decided_at="2026-10-04T00:00:03+00:00",
        decision_source="OWNER", owner_identity="OWNER")
    ledger = OwnerDecisionLedger(Path("state_owner_test_05.json"), [request])
    with pytest.raises(ValueError, match="stale binding"):
        ledger.record(stale)


def test_06_wrong_request_refused():
    request = make_request()
    other = make_request(rid="OWNER-REV-015-002")
    decision = make_owner_decision(request=other, decision="ACCEPT")
    ledger = OwnerDecisionLedger(Path("state_owner_test_06.json"), [request])
    with pytest.raises(ValueError, match="unknown review request"):
        ledger.record(decision)


def test_07_duplicate_immutable_decision_refused():
    request = make_request()
    ledger = OwnerDecisionLedger(Path("state_owner_test_07.json"), [request])
    decision = make_owner_decision(request=request, decision="ACCEPT")
    ledger.record(decision)
    with pytest.raises(ValueError, match="duplicate"):
        ledger.record(decision.model_copy())


def test_08_conflicting_second_decision_requires_supersession():
    request = make_request()
    ledger = OwnerDecisionLedger(Path("state_owner_test_08.json"), [request])
    first = make_owner_decision(request=request, decision="ACCEPT")
    ledger.record(first)
    second = make_owner_decision(
        request=request, decision="REJECT",
        decided_at="2026-10-04T00:00:05+00:00")
    with pytest.raises(ValueError, match="supersession"):
        ledger.record(second)
    record = ledger.supersede(superseded_decision_id=first.decision_id,
                              new_decision=second, reason="Owner changed "
                              "their mind after rewatch")
    assert record.decision_source == "OWNER"
    assert ledger.active_decision(request.review_request_id).decision == \
        "REJECT"
    # history is immutable: the first decision still exists
    assert ledger._find(first.decision_id).decision == "ACCEPT"


def test_09_accept_creates_no_provider_mutation(tmp_path: Path):
    request = make_request()
    ledger = OwnerDecisionLedger(tmp_path / "ledger.json", [request])
    ledger.record(make_owner_decision(request=request, decision="ACCEPT"))
    ledger.save()
    assert ledger.provider_mutation_authority() == "NONE"
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["ledger.json"]  # no generate/mutation artifacts
    assert "NONE" in ledger._events[-1]["provider_mutation"]


def test_10_reject_creates_no_provider_mutation(tmp_path: Path):
    request = make_request()
    ledger = OwnerDecisionLedger(tmp_path / "ledger.json", [request])
    ledger.record(make_owner_decision(request=request, decision="REJECT"))
    ledger.save()
    assert ledger.provider_mutation_authority() == "NONE"
    assert (tmp_path / "generate_ledger.json").exists() is False
    assert ledger.resolved_state()[request.review_request_id] == "REJECT"


def test_11_needs_repair_creates_no_provider_mutation(tmp_path: Path):
    request = make_request()
    ledger = OwnerDecisionLedger(tmp_path / "ledger.json", [request])
    summary = ledger.record(make_owner_decision(
        request=request, decision="NEEDS_REPAIR",
        note="eye-line breaks at the cut"))
    assert summary["provider_mutation_authority"] == "NONE"
    assert ledger.provider_mutation_authority() == "NONE"
    # NEEDS_REPAIR is a document for a future Tech Lead work package —
    # it must not mark the take accepted nor release anything.
    assert ledger.release_blockers() == [request.review_request_id]


def test_12_defer_preserves_unresolved_review(tmp_path: Path):
    request = make_request()
    ledger = OwnerDecisionLedger(tmp_path / "ledger.json", [request])
    ledger.record(make_owner_decision(request=request, decision="DEFER"))
    assert ledger.resolved_state()[request.review_request_id] == "DEFER"
    assert ledger.release_blockers() == [request.review_request_id]


def test_13_restart_preserves_decision_truth(tmp_path: Path):
    request = make_request()
    path = tmp_path / "ledger.json"
    ledger = OwnerDecisionLedger(path, [request])
    decision = make_owner_decision(request=request, decision="ACCEPT",
                                   note="approved")
    ledger.record(decision)
    ledger.save()
    reloaded = OwnerDecisionLedger(path, [request])
    assert reloaded.resolved_state() == ledger.resolved_state()
    assert reloaded.active_decision(
        request.review_request_id).payload_digest() == \
        decision.payload_digest()
    # tampering with recorded bytes is detected on reload
    state = json.loads(path.read_text(encoding="utf-8"))
    state["decisions"][0]["decision"] = "REJECT"
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ValueError, match="modified after recording"):
        OwnerDecisionLedger(path, [request])


def test_14_template_import_roundtrip_and_drift_refusal(tmp_path: Path):
    requests = [make_request(rid=f"OWNER-REV-015-{n:03d}")
                for n in (1, 2)]
    set_sha = "7" * 64
    template = build_decision_template(requests,
                                       tmp_path / "template.json", set_sha)
    assert template["items"][0]["decision"] is None
    # untouched template imports nothing but must not drift
    ledger = OwnerDecisionLedger(tmp_path / "ledger.json", requests)
    out = import_decision_set(tmp_path / "template.json", requests, ledger,
                              set_sha)
    assert out["imported"] == []
    assert set(out["resolved_state"].values()) == {"UNRESOLVED"}

    def write(payload):
        (tmp_path / "filled.json").write_text(json.dumps(payload),
                                              encoding="utf-8")

    filled = {**template, "items": [
        {**template["items"][0], "decision": "ACCEPT"},
        {**template["items"][1], "decision": "DEFER"}]}
    write(filled)
    out = import_decision_set(tmp_path / "filled.json", requests, ledger,
                              set_sha)
    assert len(out["imported"]) == 2
    assert out["resolved_state"][requests[0].review_request_id] == "ACCEPT"

    # wrong review-set hash (modified review packet) refused
    write({**filled, "review_set_sha256": "8" * 64})
    with pytest.raises(ValueError, match="review packet"):
        import_decision_set(tmp_path / "filled.json", requests,
                            OwnerDecisionLedger(tmp_path / "l2.json",
                                                requests), set_sha)
    # stale asset binding refused
    drifted = json.loads(json.dumps(template))
    drifted["items"][0]["reviewed_bindings"]["asset_sha256"] = "9" * 64
    drifted["items"][0]["decision"] = "ACCEPT"
    write(drifted)
    with pytest.raises(ValueError, match="stale asset"):
        import_decision_set(tmp_path / "filled.json", requests,
                            OwnerDecisionLedger(tmp_path / "l3.json",
                                                requests), set_sha)
    # invalid state refused
    bad = json.loads(json.dumps(template))
    bad["items"][0]["decision"] = "MAYBE"
    write(bad)
    with pytest.raises(ValueError, match="invalid decision state"):
        import_decision_set(tmp_path / "filled.json", requests,
                            OwnerDecisionLedger(tmp_path / "l4.json",
                                                requests), set_sha)
    # unknown request refused
    unknown = json.loads(json.dumps(template))
    unknown["items"].append({**template["items"][0],
                             "review_request_id": "OWNER-REV-015-999",
                             "decision": "ACCEPT"})
    write(unknown)
    with pytest.raises(ValueError, match="unknown review request"):
        import_decision_set(tmp_path / "filled.json", requests,
                            OwnerDecisionLedger(tmp_path / "l5.json",
                                                requests), set_sha)
    # missing request refused
    missing = json.loads(json.dumps(template))
    missing["items"] = missing["items"][:1]
    missing["items"][0]["decision"] = "ACCEPT"
    write(missing)
    with pytest.raises(ValueError, match="missing review requests"):
        import_decision_set(tmp_path / "filled.json", requests,
                            OwnerDecisionLedger(tmp_path / "l6.json",
                                                requests), set_sha)
    # malformed JSON refused
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        import_decision_set(tmp_path / "broken.json", requests,
                            OwnerDecisionLedger(tmp_path / "l7.json",
                                                requests), set_sha)


def test_15_master_scope_request_contract():
    request = OwnerReviewRequest(
        review_request_id="OWNER-REV-015-005", project="swordsman_film",
        scope="MASTER", master_sha256="976876a1" + "0" * 56,
        narrative_function="whole-film temporal quality",
        reason_review_required="worker 3-frame sample cannot decide "
                               "temporal defects",
        created_at="2026-10-04T00:00:00+00:00")
    assert request.bindings() == {"master_sha256": "976876a1" + "0" * 56}
    with pytest.raises(Exception):
        OwnerReviewRequest(
            review_request_id="OWNER-REV-015-006", project="x",
            scope="MASTER", reason_review_required="no master sha",
            created_at="2026-10-04T00:00:00+00:00")


def test_16_decision_states_are_frozen():
    assert OWNER_DECISION_STATES == ("ACCEPT", "REJECT", "NEEDS_REPAIR",
                                     "DEFER")


def test_17_duplicate_item_in_decision_file_refused(tmp_path: Path):
    requests = [make_request(rid="OWNER-REV-015-001")]
    template = build_decision_template(requests,
                                       tmp_path / "template.json",
                                       "7" * 64)
    dup = json.loads(json.dumps(template))
    dup["items"].append({**template["items"][0], "decision": "ACCEPT"})
    (tmp_path / "dup.json").write_text(json.dumps(dup), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate decision item"):
        import_decision_set(tmp_path / "dup.json", requests,
                           OwnerDecisionLedger(tmp_path / "l.json",
                                               requests), "7" * 64)
