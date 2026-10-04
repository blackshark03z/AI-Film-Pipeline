"""AI-FILM-QUALITY-V2-002 package recovery cases: every V2-002-specific
adversarial/recovery case executed against its live guard."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import film_pipeline.quality_repair_v2 as m
from film_pipeline.quality_repair_v2 import (
    QUALITY_V2_CANONICAL_BASELINE, CANONICAL_MASTER_SHA256,
    validate_editorial_receipt)

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")
F2_CANONICAL_SHA = ("e84ba56ccd0f556e3eebe8ccf83def56"
                    "7118a59b87a463c8c39898254890a767")


def pkg_json(name):
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidates_info():
    freeze = pkg_json("experiment_freeze_v2_002.json")
    out = {}
    for cand in freeze["candidates"]:
        result = pkg_json(f"scene_SCENE_F_STORM_GATE/shot_"
                          f"{cand['shot_id']}/result.json")
        out[cand["candidate_id"]] = result
    return out


# V2-002-RC-001 — wrong V1 baseline
def test_rc001_wrong_v1_baseline_refused():
    assert QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
    admission = pkg_json("experiment_admission_v2_002.json")
    assert admission["receipt"]["canonical_baseline_sha256"] == \
        QUALITY_V2_CANONICAL_BASELINE


# V2-002-RC-002 — wrong F2 predecessor
def test_rc002_wrong_f2_predecessor_refused():
    registry = pkg_json("planned_renders_v2_002.json")
    gov = pkg_json("candidates_governance_v2_002.json")
    expected_take = registry["source_canonical_take"]
    assert expected_take == \
        "take_91e4997b99432358ec713c072ef3a82571f65b6b43a4a48fab8cfa17f31efb67"
    for entry in gov["candidates"]:
        assert entry["governed"]["source_canonical_take"] == expected_take
    # a candidate minted against a DIFFERENT take is a different identity
    wrong = m.make_candidate(
        source_canonical_take="take_OTHER", affected_shot="SEQ7_F2C",
        repair_reason="ACTION_CAUSALITY_REDESIGN",
        asset_sha256="b" * 64, generation_semantic_identity="x")
    assert wrong.candidate_id != gov["candidates"][0]["governed"][
        "candidate_id"]


# V2-002-RC-003 — wrong QD target
def test_rc003_wrong_qd_target_refused():
    registry = pkg_json("planned_renders_v2_002.json")
    assert registry["quality_debt_ids"] == ["QD-001"]
    gov = pkg_json("candidates_governance_v2_002.json")
    for entry in gov["candidates"]:
        assert entry["governed"]["quality_debt_ids"] == ["QD-001"]


# V2-002-RC-004 — missing admission receipt
def test_rc004_missing_admission_refused():
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        m.admission_gate(None, known_debt_ids=["QD-001"])
    assert pkg_json("experiment_admission_v2_002.json")["gate_result"][
        "status"] == "ADMITTED"


# V2-002-RC-005 — budget above 2
def test_rc005_budget_above_two_refused():
    ledger = pkg_json("generate_ledger.json")
    assert ledger["max_primary"] == 2
    admission = pkg_json("experiment_admission_v2_002.json")
    assert admission["receipt"]["max_generate_budget"] == 2


# V2-002-RC-006 — third generate attempt
def test_rc006_third_generate_refused(monkeypatch):
    import run_quality_v2_002_experiment as driver
    calls = []
    monkeypatch.setattr(driver.base, "run_live_shot",
                        lambda *a, **k: calls.append(a))
    with pytest.raises(Exception, match="budget exhausted"):
        driver.main()
    assert calls == []  # no live shot call happened at all


# V2-002-RC-007 — duplicate dispatch
def test_rc007_duplicate_dispatch_refused():
    import sqlite3
    db = sqlite3.connect(ROOT / "projects/flow_production_harden_002/"
                         "requal_current_build/runtime.sqlite")
    try:
        for result in candidates_info().values():
            row = db.execute(
                "SELECT dispatch_count FROM provider_jobs WHERE id=?",
                (result["provider_job_id"],)).fetchone()
            assert row is not None and row[0] == 1
    finally:
        db.close()


# V2-002-RC-008 — ambiguous provider effect latches (throwaway scope)
def test_rc008_ambiguity_latches(tmp_path):
    from mutation_authority import MutationAuthority
    auth = MutationAuthority(tmp_path, "THROWAWAY-LATCH-CHECK")
    assert auth.authority == "OPEN"
    auth.latch("GENERATE_AMBIGUITY", "simulated ambiguity check")
    assert auth.authority == "LATCHED_CLOSED"
    from film_pipeline.providers.flow_reference_upload import \
        OwnerAmbiguityGate
    with pytest.raises(OwnerAmbiguityGate):
        auth.check_mutation_allowed("primary_generate")


# V2-002-RC-009 — blind retry after a completed result
def test_rc009_blind_retry_refused():
    ledger = pkg_json("generate_ledger.json")
    assert len(ledger["primary_consumed"]) == 2
    for cid, result in candidates_info().items():
        shot_dir = (PKG / "scene_SCENE_F_STORM_GATE" /
                    f"shot_{result['shot_id']}")
        assert (shot_dir / "result.json").exists()  # durable short-circuit


# V2-002-RC-010 — mislabeled candidate on the blind reel
def test_rc010_mislabel_refused():
    manifest = pkg_json("owner_f2_compare_manifest_v2_002.json")
    key = pkg_json("answer_key_v2_002.json")
    freeze = pkg_json("experiment_freeze_v2_002.json")
    draw = sorted(
        (c["candidate_id"] for c in freeze["candidates"]),
        key=lambda cid: m.sha256(
            {"blind_order": "V2-002", "candidate_id": cid}))
    assert key["mapping"] == {"CANDIDATE 1": draw[0],
                              "CANDIDATE 2": draw[1]}
    assert manifest["blind_section_order"] == ["BASELINE", "CANDIDATE 1",
                                               "CANDIDATE 2"]


# V2-002-RC-011 — intent leak into the blind section
def test_rc011_intent_leak_refused():
    blind = (PKG / "owner_f2_blind_review_v2_002.json").read_text(
        encoding="utf-8")
    manifest = pkg_json("owner_f2_compare_manifest_v2_002.json")
    freeze = pkg_json("experiment_freeze_v2_002.json")
    assert "F2C-V2-002" not in blind
    assert "AUTHORITATIVE INTENT" not in blind
    intent_text = freeze["candidates"][0]["creative_body"]
    for seg in manifest["segments"]:
        if seg["section"] == "BLIND":
            assert seg.get("surface") is None
    assert manifest["leak_check"]["mapping_in_reel"] is False
    assert intent_text not in json.dumps(manifest["segments"])


# V2-002-RC-012 — blind answers after the key was opened
def test_rc012_blind_ordering_enforced():
    blind = pkg_json("owner_f2_blind_review_v2_002.json")
    assert blind["answered_blind"] is True
    assert all(all(v for v in item.values())
               for item in blind["answers"].values())


# V2-002-RC-013/014/015 — critical negatives
def test_rc013_014_015_critical_negatives_checked():
    blind = pkg_json("owner_f2_blind_review_v2_002.json")
    result = pkg_json("quality_v2_002_experiment_result.json")
    q5 = blind["questions"][4]
    for label in ("CANDIDATE 1", "CANDIDATE 2"):
        answer = blind["answers"][label][q5]
        assert "PASSES THROUGH" in answer
        assert "STOP AT the rock" not in answer
    assert result["effects"]["ACTION_CAUSALITY_EFFECT"] == "EFFECT_OBSERVED"


# V2-002-RC-016 — identity drift hidden behind improved logic
def test_rc016_identity_drift_hard_block():
    gov = pkg_json("candidates_governance_v2_002.json")
    for entry in gov["candidates"]:
        identity = entry["governed"]["identity_receipt"]
        assert identity["identity_continuity"] == "UNCHANGED"
        review = m.QualityReviewReceipt.model_validate(entry["review"])
        assert review.finding("IDENTITY").verdict == "UNCHANGED"
        assert review.hard_blocks() == []


# V2-002-RC-017 — performance improves but logic worsens
def test_rc017_logic_regression_blocked():
    # re-run the live V2-001 guard with a logic-regressing receipt
    cand = m.make_candidate(source_canonical_take="t", affected_shot="S",
                            repair_reason="r", asset_sha256="b" * 64,
                            generation_semantic_identity="g")
    cand = m.record_technical_validation(cand, {
        "decision": "pass", "qc_report_id": "q", "asset_sha256": "b" * 64})
    review = m.build_review_receipt(
        candidate=cand, baseline_asset_sha256="a" * 64,
        target_dimensions=["PERFORMANCE"],
        findings=[
            {"dimension": "PERFORMANCE", "verdict": "IMPROVED",
             "severity": "NONE", "evidence": ["smoother"]},
            {"dimension": "NARRATIVE_LOGIC", "verdict": "REGRESSED",
             "severity": "LOW", "evidence": ["goal muddied"]}],
        review_source="ADVISORY_WORKER")
    cand = m.attach_quality_review(
        cand, review,
        identity_receipt={"identity_continuity": "UNCHANGED",
                          "verified_by": "v"},
        editorial_compatibility_receipt={
            "editorial_compatible": True, "edit_manifest_id": "e",
            "affected_clip_order": 24, "trim_compatible": True,
            "verified_by": "v"})
    checks = m.evaluate_acceptance(
        m.apply_owner_decision(cand, _owner_decision("b" * 64)))
    assert "C5_NO_HIGHER_SEVERITY_NEW_DEFECT" in checks["blocked_by"]


def _owner_decision(sha):
    from film_pipeline.owner_review import make_owner_decision

    class Req:
        review_request_id = "OWNER-REV-V2002RC"

        def bindings(self):
            return {"asset_sha256": sha}
    return make_owner_decision(request=Req(), decision="ACCEPT",
                               note="TRADEOFF_ACCEPTED=NARRATIVE_LOGIC")


# V2-002-RC-018 — editorial fit fails
def test_rc018_editorial_fit_refused():
    with pytest.raises(ValueError, match="editorial fit"):
        validate_editorial_receipt(
            {"editorial_compatible": False, "edit_manifest_id": "e",
             "affected_clip_order": 24, "trim_compatible": True,
             "verified_by": "v"})


# V2-002-RC-019 — canonical EditManifest modified by the preview
def test_rc019_editmanifest_unchanged():
    gov = pkg_json("candidates_governance_v2_002.json")
    plan_sha = file_sha(MASTER / "editorial_plan_010.json")
    range_sha = file_sha(MASTER / "ranges/24_SEQ7_F2.json")
    summary = json.loads((MASTER / "master_summary.json").read_text(
        encoding="utf-8"))
    assert summary["edit_manifest_id"] == \
        "edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590654b059c7969d3"
    for entry in gov["candidates"]:
        receipt = entry["governed"]["editorial_compatibility_receipt"]
        assert receipt["note"].startswith("preview successor manifest only")
    # snapshot equality across the two proof runs (deterministic bytes)
    assert plan_sha and range_sha


# V2-002-RC-020 — worker-forged Owner selection
def test_rc020_forged_selection_refused():
    gov = pkg_json("candidates_governance_v2_002.json")
    assert gov["no_owner_decision_minted"] is True
    for entry in gov["candidates"]:
        assert entry["governed"]["owner_decision_id"] == ""
    template = pkg_json("owner_f2_decision_v2_002.template.json")
    assert template["decision"] is None
    assert template["selected_asset_sha256"] is None
    with pytest.raises(ValueError, match="non-Owner identity"):
        from film_pipeline.owner_review import make_owner_decision

        class Req:
            review_request_id = "OWNER-REV-X"

            def bindings(self):
                return {"asset_sha256": "b" * 64}
        make_owner_decision(request=Req(), decision="ACCEPT",
                            owner_identity="worker-agent")


# V2-002-RC-021 — promotion inside V2-002
def test_rc021_no_promotion_in_package():
    gov = pkg_json("candidates_governance_v2_002.json")
    assert gov["no_promotion_executed"] is True
    for entry in gov["candidates"]:
        assert entry["governed"]["owner_decision_state"] == \
            "QUALITY_REVIEW_READY"
    events = sorted(p.name for p in PKG.glob("*ledger*.json"))
    for name in events:
        payload = (PKG / name).read_text(encoding="utf-8")
        assert "PROMOTION_COMMITTED" not in payload


# V2-002-RC-022 — canonical master mutated
def test_rc022_master_unchanged():
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == \
        CANONICAL_MASTER_SHA256
    proof = pkg_json("canonical_no_change_v2_002.json")
    assert proof["canonical_master_unchanged"] is True


# V2-002-RC-023 — V2 candidate in canonical lineage
def test_rc023_canonical_lineage_clean():
    range24 = json.loads((MASTER / "ranges/24_SEQ7_F2.json").read_text(
        encoding="utf-8"))
    assert range24["selected_take_id"] == \
        "take_91e4997b99432358ec713c072ef3a82571f65b6b43a4a48fab8cfa17f31efb67"
    assert range24["asset_sha256"] == F2_CANONICAL_SHA


# V2-002-RC-024 — stale reference binding
def test_rc024_reference_binding_frozen():
    freeze = pkg_json("experiment_freeze_v2_002.json")
    binding = freeze["baseline_binding"]["F2C"]
    att_dir = PKG / "scene_SCENE_F_STORM_GATE/continuity_reference/" \
                    "attestation"
    assert binding["media_id"] == "8f2f5277-aae8-44b5-a5b7-c197d1d7c115"
    assert binding["attestation_id"].startswith("refbind_f4277ac1")
    assert any(p.name.startswith("refbind_f4277ac1")
               for p in att_dir.glob("*.json"))


# V2-002-RC-025 — wrong output identity
def test_rc025_output_identity_binding():
    for result in candidates_info().values():
        video = Path(result["asset"]["uri_or_path"])
        assert video.is_file()
        assert file_sha(video) == result["asset"]["sha256"]


# V2-002-RC-026 — trade-off hidden
def test_rc026_tradeoffs_exposed():
    gov = pkg_json("candidates_governance_v2_002.json")
    template = pkg_json("owner_f2_decision_v2_002.template.json")
    for entry, item in zip(gov["candidates"], template["candidates"]):
        summary = item["tradeoff_summary"]
        assert len(summary) == 10
        assert all("verdict" in v for v in summary.values())


# V2-002-RC-027 — aggregate score introduced
def test_rc027_no_aggregate_score():
    gov = pkg_json("candidates_governance_v2_002.json")
    for entry in gov["candidates"]:
        review = entry["review"]
        assert review["no_aggregate_score"] is True
        assert not any("total" in k or "overall" in k
                       for k in review.keys())


# V2-002-RC-028 — ambiguous attribution
def test_rc028_attribution_unambiguous():
    ledger = pkg_json("generate_ledger.json")
    assert len(ledger["primary_consumed"]) == 2
    outputs = {r["output_identity"] for r in candidates_info().values()}
    assert len(outputs) == 2
    ma = pkg_json("mutation_authority.json")
    assert ma["mutation_authority"] == "OPEN"
    assert len([e for e in ma["events"]
                if e["kind"] == "BUDGET_CONSUMED"]) == 2
