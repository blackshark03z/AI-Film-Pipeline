"""V2-020 — orchestrator offline tests (no network, no browser)."""
from __future__ import annotations

import json

import pytest

from film_pipeline.providers.dola_production import (
    FIXTURE,
    DolaAccountPoolRouter,
    DolaAccountState,
    DolaProductionOrchestrator,
    DolaCapabilityRegistry,
    OrchestratorInterrupt,
    merge_registry,
)


@pytest.fixture(scope="module")
def registry():
    pkg = "projects/quality_v2_019_dola_productionization"
    skill = json.loads((pkg + "/V2_019_PHASEA_SKILL_PACK_1.json")
                       .encode() and open(pkg +
                       "/V2_019_PHASEA_SKILL_PACK_1.json",
                       encoding="utf-8").read())
    bar = json.loads(open(pkg + "/V2_019_PHASEA_ACTION_BAR_CONF_FULL.json",
                          encoding="utf-8").read())
    return merge_registry(skill, bar)


def _orch(tmp_path, registry, **kw):
    return DolaProductionOrchestrator(
        tmp_path / "run.state.json", FIXTURE, registry=registry, **kw)


def _pool(*aliases_credit):
    pool = DolaAccountPoolRouter()
    for alias, credit in aliases_credit:
        pool.register(DolaAccountState(
            account_alias=alias, profile_binding=f"p/{alias}",
            session_state="SESSION_VALID" if credit is None else "READY",
            known_credit_state=credit))
    return pool


def _good_technical(duration=5.1):
    return {"decode_ok": True, "duration_s": duration, "height": 720,
            "fps": 24.0, "black_frame_ratio": 0.0, "freeze_frame_ratio": 0.0,
            "mean_luma": 90.0, "mean_saturation": 0.2, "motion_mad": 3.5}


def test_fixture_frozen_grammar():
    assert [s.role for s in FIXTURE.shots] == \
        ["ARRIVAL", "TRAVERSAL", "SETTLE"]
    assert all(s.duration_class == 5 for s in FIXTURE.shots)
    assert all(s.screen_direction == "left-to-right" for s in FIXTURE.shots)
    needles = [s.needle for s in FIXTURE.shots]
    assert len(set(needles)) == 3
    assert all(n in s.prompt for s, n in zip(FIXTURE.shots, needles))
    assert "weapons" in FIXTURE.forbidden and "architecture" in \
        FIXTURE.forbidden


def test_plan_uses_free_default_model_and_rejects_25(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t1")
    plan = orch.plan_shot("QA_SHOT_A")
    assert plan.model_id == "seedance_v2.0" and plan.eligible
    assert plan.duration_class == 5
    ok, reason = registry.supports_request(model_id="seedance_v2.5")
    assert not ok and reason == "SUBSCRIPTION_GATED"


def test_durable_state_and_idempotent_stages(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t2")
    orch.plan_shot("QA_SHOT_A")
    orch2 = _orch(tmp_path, registry)
    orch2.load_or_init("run_t2")
    plan2 = orch2.plan_shot("QA_SHOT_A")  # idempotent re-plan
    assert plan2.model_id == "seedance_v2.0"
    assert (tmp_path / "run.state.transitions.jsonl").exists()


def test_release_binding_and_restart_recovery(tmp_path, registry):
    orch = _orch(tmp_path, registry, crash_point="after_receipt")
    orch.load_or_init("run_t3")
    orch.plan_shot("QA_SHOT_A")
    with pytest.raises(OrchestratorInterrupt):
        orch.record_release("QA_SHOT_A", account_alias="ACCOUNT_D",
                            attempt_id="att_A", conversation_id="conv1",
                            request_fingerprint="fp1")
    # restart: state recovered, mutation counted, binding immutable
    orch2 = _orch(tmp_path, registry)
    orch2.load_or_init("run_t3")
    assert orch2.mutations_used == 1
    record = orch2.shot("QA_SHOT_A")
    assert record.status == "RELEASED"
    assert orch2.pool.binding("att_A").account_alias == "ACCOUNT_D"
    with pytest.raises(ValueError):
        orch2.pool.bind_release(attempt_id="att_A",
                                account_alias="ACCOUNT_B")


def test_qc_frozen_thresholds(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t4")
    assert orch.qc_verdict("QA_SHOT_A", technical=_good_technical()) == \
        "ACCEPT"
    bad = _good_technical(duration=2.0)
    assert orch.qc_verdict("QA_SHOT_B", technical=bad) == "REPAIR_REQUIRED"
    frozen = _good_technical()
    frozen["freeze_frame_ratio"] = 0.9
    assert orch.qc_verdict("QA_SHOT_C", technical=frozen) == "REJECT"


def test_repair_budget_one_slot_only(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t5")
    for sid in ("QA_SHOT_A", "QA_SHOT_B", "QA_SHOT_C"):
        orch.qc_verdict(sid, technical=_good_technical())
    orch.shot("QA_SHOT_B").qc_verdict = "REPAIR_REQUIRED"
    orch.shot("QA_SHOT_B").status = "QC_REPAIR_REQUIRED"
    assert orch.repair_eligible() == "QA_SHOT_B"
    assert orch.request_repair("QA_SHOT_B") is True
    assert orch.repair_eligible() is None
    assert orch.request_repair("QA_SHOT_B") is False


def test_repair_not_granted_with_multiple_failures(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t6")
    for sid in ("QA_SHOT_A", "QA_SHOT_B", "QA_SHOT_C"):
        orch.qc_verdict(sid, technical=_good_technical())
        orch.shot(sid).qc_verdict = "REPAIR_REQUIRED"
        orch.shot(sid).status = "QC_REPAIR_REQUIRED"
    assert orch.repair_eligible() is None


def test_mutation_budget_cap(tmp_path, registry):
    orch = _orch(tmp_path, registry, mutation_budget=4)
    orch.load_or_init("run_t7")
    orch.plan_shot("QA_SHOT_A")
    orch.record_release("QA_SHOT_A", account_alias="ACCOUNT_D",
                        attempt_id="a1", conversation_id="c1",
                        request_fingerprint="f1")
    assert orch.mutations_used == 1
    # repair blocked at budget
    orch.mutations_used = orch.mutation_budget
    orch.shot("QA_SHOT_A").qc_verdict = "REPAIR_REQUIRED"
    orch.shot("QA_SHOT_A").status = "QC_REPAIR_REQUIRED"
    assert orch.repair_eligible() is None


def test_editorial_ranges_deterministic_with_trim(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t8")
    for sid in ("QA_SHOT_A", "QA_SHOT_B", "QA_SHOT_C"):
        orch.qc_verdict(sid, technical=_good_technical())
    ed = orch.editorial_ranges(trims={"QA_SHOT_C": 6})
    assert ed["ranges"]["QA_SHOT_A"] == [0, 122]  # 5.1s * 24 -> 122
    assert ed["ranges"]["QA_SHOT_C"] == [0, 116]
    assert "regeneration never" in ed["trim_policy"]


def test_manifest_chain_completeness(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t9")
    orch.plan_shot("QA_SHOT_A")
    orch.record_release("QA_SHOT_A", account_alias="ACCOUNT_D",
                        attempt_id="att", conversation_id="384",
                        request_fingerprint="fp")
    orch.record_creation("QA_SHOT_A", ["1542"])
    orch.record_asset("QA_SHOT_A", path="a.mp4", clean_sha256="ab" * 32,
                      watermarked_sha256=None,
                      variant_authority="PROVIDER_ISSUED_UNWATERMARKED")
    orch.qc_verdict("QA_SHOT_A", technical=_good_technical())
    orch.editorial_ranges()
    orch.record_editorial_proof(path="seq.mp4", sha256="cd" * 32,
                                frame_count=360, junctions={"A-B": "PASS"})
    orch.record_finishing(loudness_lufs=-14.0, true_peak_dbtp=-1.2,
                          av_sync="OK", path="fm.mov", sha256="ef" * 32)
    orch.record_master(path="dm.mp4", sha256="12" * 32,
                       watermark_status="ABSENT")
    doc = orch.manifest(run_dir=str(tmp_path))
    entry = doc["chain"][0]
    for key in ("shot_id", "prompt_sha256", "attempt_id", "account_alias",
                "conversation_id", "creation_ids", "clean_sha256",
                "variant_authority", "qc_verdict", "editorial_range"):
        assert key in entry and entry[key] not in (None, [], "")
    assert doc["distribution_master"]["distribution_master_sha256"] == \
        "12" * 32
    blob = json.dumps(doc)
    for marker in ("sessionid", "msToken", "a_bogus", "Bearer"):
        assert marker not in blob


def test_status_transitions_recorded(tmp_path, registry):
    orch = _orch(tmp_path, registry)
    orch.load_or_init("run_t10")
    orch.set_status("WAITING_PROVIDER", "x")
    orch.set_status("QC", "y")
    orch.set_status("COMPLETED", "done")
    assert orch.state.status == "COMPLETED"
    lines = (tmp_path / "run.state.transitions.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert json.loads(lines[-1])["status"] == "COMPLETED"
