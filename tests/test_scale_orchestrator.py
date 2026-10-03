"""Scale-orchestrator proofs (FLOW-PRODUCTION-SCALE-007, Q1 / L1).

30 synthetic slots (6 historical adopted + 3 live scenes × 8 live shots)
through the REAL chain: scale_run → production_run → sequence_runner →
scene_runner. Proves: restart at slot 1 / N/2 / final slot with zero
regeneration; out-of-order scene/shot refusal; historical mutation refusal;
whole-run plan-hash drift; duplicate ShotSpec id; duplicate ProviderJob
binding; missing/stale/wrong results; cross-project media identity. All
offline — injected executors, no provider or browser involvement.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import scene_runner
import sequence_runner
from scale_run import (
    ScaleRunState,
    execute_scale_run,
    scale_plan_hash,
    validate_scale_plan,
    verify_scene_order_integrity,
)

HIST_SHOTS = [f"H{i:02d}" for i in range(1, 7)]  # 6 adopted slots
LIVE_SCENES = ["SC_1", "SC_2", "SC_3"]
LIVE_SHOTS = [f"L{scene}_{i}" for scene in LIVE_SCENES
              for i in range(1, 9)]  # 24 live slots
REF_MEDIA = "media_ref_1"


def make_historical(tmp_path, sequence_id="SEQ_SCALE_HIST"):
    state_dir = tmp_path / "hist"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {"version": "sequence-state-v1", "sequence_id": sequence_id,
             "started_at": "t", "scenes": {}}
    for scene, shot_ids in (("HIST_SC_A", HIST_SHOTS[:3]),
                            ("HIST_SC_B", HIST_SHOTS[3:])):
        state["scenes"][scene] = {"scene_id": scene, "status": "PROVEN"}
        scene_dir = state_dir / f"scene_{scene}"
        scene_dir.mkdir(exist_ok=True)
        for sid in shot_ids:
            shot_dir = scene_dir / f"shot_{sid}"
            shot_dir.mkdir(exist_ok=True)
            (shot_dir / "result.json").write_text(json.dumps(
                {"shot_id": sid, "gate": "SHOT_PROVEN",
                 "output_identity": "media_" + sid,
                 "asset": {"sha256": "hash_" + sid}}), encoding="utf-8")
    (state_dir / "sequence_state.json").write_text(
        json.dumps(state), encoding="utf-8")
    return state_dir / "sequence_state.json"


def scale_plan(hist_ref, live_sequence_id="SEQ_SCALE_LIVE"):
    scenes = [{"scene_id": scene, "shots": [
        {"shot_id": f"L{scene}_{i}",
         "fixture": f"fixtures/L{scene}_{i}.json",
         "continuity": {"kind": "reference", "media_id": REF_MEDIA}}
        for i in range(1, 9)]} for scene in LIVE_SCENES]
    return {"run_id": "RUN_SCALE_TEST", "project_id": "proj_scale",
            "sequences": [
                {"sequence_id": "SEQ_SCALE_HIST", "mode": "adopted",
                 "state_ref": str(hist_ref)},
                {"sequence_id": live_sequence_id, "mode": "live",
                 "plan_ref": "plan_ref_marker",
                 "media_scope": [REF_MEDIA], "scenes": scenes}]}


def make_live_driver(plan, counter, fail_at=None):
    """Full real chain driver: sequence layer over scene layer over a
    synthetic per-shot runtime that writes durable results (and can crash
    right after one, simulating a mid-run process exit)."""
    live = next(s for s in plan["sequences"] if s["mode"] == "live")

    def run_shot(shot, state_dir, scene_state):
        shot_id = shot["shot_id"]
        counter.append(shot_id)
        result = {"shot_id": shot_id, "gate": "SHOT_PROVEN",
                  "provider_job_id": "job_" + shot_id,
                  "asset": {"sha256": "hash_" + shot_id,
                            "provider_job_id": "job_" + shot_id}}
        shot_dir = Path(state_dir) / f"shot_{shot_id}"
        shot_dir.mkdir(parents=True, exist_ok=True)
        (shot_dir / "result.json").write_text(json.dumps(result),
                                              encoding="utf-8")
        if fail_at == shot_id:
            raise RuntimeError("simulated crash after durable result")
        return result

    def run_scene(scene, scene_state_dir):
        return scene_runner.execute_scene(scene, scene_state_dir, run_shot)

    def run_live_sequence(entry, state_dir):
        return sequence_runner.execute_sequence(
            {"sequence_id": entry["sequence_id"], "scenes": live["scenes"]},
            state_dir, run_scene)

    return run_live_sequence


def _real_adopted_loader():
    from production_run import adopted_sequence_snapshot
    return adopted_sequence_snapshot


def _flat_runner():
    from production_run import execute_production_run
    return execute_production_run


def scale_state(tmp_path):
    return json.loads((tmp_path / "run" / "scale_run_state.json")
                      .read_text(encoding="utf-8"))


def test_validate_accepts_30_slot_plan(tmp_path):
    ref = make_historical(tmp_path)
    plan = validate_scale_plan(scale_plan(ref))
    assert plan["slot_count"] == 24  # live slots; adopted slots join at run
    assert len(scale_plan_hash(plan)) == 64


def test_validation_refuses_duplicate_shot_id_across_run(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    plan["sequences"][1]["scenes"][1]["shots"][0]["shot_id"] = \
        plan["sequences"][1]["scenes"][0]["shots"][0]["shot_id"]
    with pytest.raises(ValueError, match="duplicate shot_id"):
        validate_scale_plan(plan)


def test_validation_refuses_duplicate_scene_id_in_sequence(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    plan["sequences"][1]["scenes"][1]["scene_id"] = \
        plan["sequences"][1]["scenes"][0]["scene_id"]
    with pytest.raises(ValueError, match="duplicate scene_id"):
        validate_scale_plan(plan)


def test_cross_project_media_identity_refused(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    plan["sequences"][1]["scenes"][0]["shots"][0]["continuity"] = {
        "kind": "reference", "media_id": "media_from_OTHER_project"}
    with pytest.raises(ValueError, match="outside sequence.*media scope"):
        validate_scale_plan(plan)


def test_full_30_slot_scale_run(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    counter = []
    result = execute_scale_run(plan, tmp_path / "run",
                               make_live_driver(plan, counter),
                               _real_adopted_loader(), _flat_runner())
    assert result["run_complete"] is True
    assert result["slot_count"] == 30
    # Exactly 24 live executor invocations; adopted slots never execute.
    assert sorted(counter) == sorted(LIVE_SHOTS)
    bindings = scale_state(tmp_path)["provider_job_bindings"]
    assert len(bindings) == 24
    assert bindings["job_LSC_1_1"] == "SEQ_SCALE_LIVE/LSC_1_1"
    assert scale_state(tmp_path)["sequences"]["SEQ_SCALE_LIVE"][
        "status"] == "PROVEN"


@pytest.mark.parametrize("fail_index", [0, 11, 23],
                         ids=["slot-1", "slot-N/2", "final-slot"])
def test_restart_never_regenerates_completed_slots(tmp_path, fail_index):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    counter = []
    with pytest.raises(RuntimeError, match="simulated crash"):
        execute_scale_run(plan, tmp_path / "run",
                          make_live_driver(plan, counter,
                                           fail_at=LIVE_SHOTS[fail_index]),
                          _real_adopted_loader(), _flat_runner())
    assert len(counter) == fail_index + 1  # crashed after the durable result
    result = execute_scale_run(plan, tmp_path / "run",
                               make_live_driver(plan, counter),
                               _real_adopted_loader(), _flat_runner())
    assert result["run_complete"] is True
    # No slot executed twice across the restart boundary.
    assert len(counter) == 24
    assert len(counter) == len(set(counter))


def test_out_of_order_scene_result_refused(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    counter = []
    with pytest.raises(RuntimeError, match="simulated crash"):
        execute_scale_run(plan, tmp_path / "run",
                          make_live_driver(plan, counter,
                                           fail_at=LIVE_SHOTS[8]),
                          _real_adopted_loader(), _flat_runner())
    seq_dir = tmp_path / "run" / "sequence_SEQ_SCALE_LIVE"
    # Fabricate a scene result for SC_3 while SC_2 has none: out-of-order.
    fake = {"scene_id": "SC_3", "scene_complete": True,
            "results": [{"shot_id": s, "gate": "SHOT_PROVEN"}
                        for s in LIVE_SHOTS[16:]]}
    (seq_dir / "scene_SC_3").mkdir(parents=True, exist_ok=True)
    (seq_dir / "scene_SC_3" / "scene_result.json").write_text(
        json.dumps(fake), encoding="utf-8")
    with pytest.raises(ValueError, match="out-of-order sequence state"):
        execute_scale_run(plan, tmp_path / "run",
                          make_live_driver(plan, counter),
                          _real_adopted_loader(), _flat_runner())
    # Refusal happened before any execution: no slot ran on the tampered run.
    assert len(counter) == 9


def test_missing_earlier_scene_result_refused_on_resume(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    counter = []
    with pytest.raises(RuntimeError, match="simulated crash"):
        execute_scale_run(plan, tmp_path / "run",
                          make_live_driver(plan, counter,
                                           fail_at=LIVE_SHOTS[8]),
                          _real_adopted_loader(), _flat_runner())
    seq_dir = tmp_path / "run" / "sequence_SEQ_SCALE_LIVE"
    (seq_dir / "scene_SC_1" / "scene_result.json").unlink()
    # SC_1 holds a durable PROVEN status whose result file is now gone:
    # fail closed BEFORE executing anything else.
    with pytest.raises(ValueError, match="stale/missing result"):
        execute_scale_run(plan, tmp_path / "run",
                          make_live_driver(plan, counter),
                          _real_adopted_loader(), _flat_runner())
    assert len(counter) == 9  # no slot executed under tampered state


def test_out_of_order_shot_result_refused(tmp_path):
    scene = {"scene_id": "SC_X", "shots": [
        {"shot_id": f"S{i}", "fixture": "f", "continuity": {"kind": "x"}}
        for i in (1, 2, 3)]}
    scene_dir = tmp_path / "scene_dir"
    (scene_dir / "shot_S3").mkdir(parents=True)
    (scene_dir / "shot_S3" / "result.json").write_text(json.dumps(
        {"shot_id": "S3", "gate": "SHOT_PROVEN"}), encoding="utf-8")
    with pytest.raises(ValueError, match="out-of-order scene state"):
        verify_scene_order_integrity(scene_dir, scene)


def test_historical_sequence_mutation_refused(tmp_path):
    ref = make_historical(tmp_path)
    state = json.loads(ref.read_text(encoding="utf-8"))
    state["scenes"]["HIST_SC_B"]["status"] = "UNRESOLVED"
    ref.write_text(json.dumps(state), encoding="utf-8")
    plan = scale_plan(ref)
    executed = []
    with pytest.raises(ValueError, match="not PROVEN"):
        execute_scale_run(plan, tmp_path / "run",
                          lambda e, d: executed.append(e["sequence_id"]),
                          _real_adopted_loader(), _flat_runner())
    # The unproven historical sequence refuses adoption; nothing executes.
    assert executed == []


def test_adopted_sequence_never_calls_live_executor(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    executed = []
    real_driver = make_live_driver(plan, [])

    def live(entry, state_dir):
        executed.append(entry["sequence_id"])
        return real_driver(entry, state_dir)

    result = execute_scale_run(plan, tmp_path / "run", live,
                               _real_adopted_loader(), _flat_runner())
    assert executed == ["SEQ_SCALE_LIVE"]
    assert result["run_complete"] is True


def test_whole_run_plan_hash_drift_refused(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    execute_scale_run(plan, tmp_path / "run", make_live_driver(plan, []),
                      _real_adopted_loader(), _flat_runner())
    drifted = scale_plan(ref)
    drifted["sequences"][1]["scenes"][0]["shots"][0]["fixture"] = \
        "fixtures/CHANGED.json"
    with pytest.raises(ValueError, match="plan identity mismatch"):
        execute_scale_run(drifted, tmp_path / "run",
                          make_live_driver(drifted, []),
                          _real_adopted_loader(), _flat_runner())


def test_wrong_scene_result_refused_on_resume(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    counter = []
    with pytest.raises(RuntimeError, match="simulated crash"):
        execute_scale_run(plan, tmp_path / "run",
                          make_live_driver(plan, counter,
                                           fail_at=LIVE_SHOTS[8]),
                          _real_adopted_loader(), _flat_runner())
    seq_dir = tmp_path / "run" / "sequence_SEQ_SCALE_LIVE"
    result_path = seq_dir / "scene_SC_1" / "scene_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["scene_id"] = "SC_2"  # wrong identity inside a frozen slot
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="wrong-scene result"):
        execute_scale_run(plan, tmp_path / "run",
                          make_live_driver(plan, counter),
                          _real_adopted_loader(), _flat_runner())


def test_wrong_shot_result_refused(tmp_path):
    scene = {"scene_id": "SC_X", "shots": [
        {"shot_id": f"S{i}", "fixture": "f", "continuity": {"kind": "x"}}
        for i in (1, 2)]}
    scene_dir = tmp_path / "scene_dir"
    for sid in ("S1", "S2"):
        (scene_dir / f"shot_{sid}").mkdir(parents=True)
    (scene_dir / "shot_S1" / "result.json").write_text(json.dumps(
        {"shot_id": "S1", "gate": "SHOT_PROVEN"}), encoding="utf-8")
    (scene_dir / "shot_S2" / "result.json").write_text(json.dumps(
        {"shot_id": "S1", "gate": "SHOT_PROVEN"}), encoding="utf-8")
    with pytest.raises(ValueError, match="wrong-slot result"):
        verify_scene_order_integrity(scene_dir, scene)


def test_duplicate_provider_job_binding_refused(tmp_path):
    state = ScaleRunState(tmp_path, "RUN_X")
    state.bind_provider_job("job_DUP", "SEQ_A/L1")
    with pytest.raises(ValueError, match="duplicate ProviderJob binding"):
        state.bind_provider_job("job_DUP", "SEQ_A/L2")


def test_duplicate_provider_job_in_results_refused(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    real_driver = make_live_driver(plan, [])

    def run_live_sequence(entry, state_dir):
        result = real_driver(entry, state_dir)
        # Simulate two slots bound to one ProviderJob (at-most-once breach).
        tampered = Path(state_dir) / "scene_SC_1" / "shot_LSC_1_1" / \
            "result.json"
        payload = json.loads(tampered.read_text(encoding="utf-8"))
        payload["provider_job_id"] = "job_LSC_1_2"
        tampered.write_text(json.dumps(payload), encoding="utf-8")
        return result

    with pytest.raises(ValueError, match="duplicate ProviderJob binding"):
        execute_scale_run(plan, tmp_path / "run", run_live_sequence,
                          _real_adopted_loader(), _flat_runner())
    # The refusal persists on every later attempt (durable results re-bind).
    with pytest.raises(ValueError, match="duplicate ProviderJob binding"):
        execute_scale_run(plan, tmp_path / "run", real_driver,
                          _real_adopted_loader(), _flat_runner())


def test_scale_state_rejects_demoting_proven(tmp_path):
    state = ScaleRunState(tmp_path, "RUN_X")
    state.record_sequence("SEQ_1", "PROVEN")
    with pytest.raises(ValueError, match="already PROVEN"):
        state.record_sequence("SEQ_1", "EXECUTING")


def test_scale_state_belongs_to_run(tmp_path):
    ScaleRunState(tmp_path, "RUN_A")
    with pytest.raises(ValueError, match="another run"):
        ScaleRunState(tmp_path, "RUN_B")


def test_editorial_target_duration_validated(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    plan["sequences"][1]["scenes"][0]["shots"][0][
        "editorial_target_duration"] = -1.0
    with pytest.raises(ValueError, match="editorial_target_duration invalid"):
        validate_scale_plan(plan)
    ok = scale_plan(ref)
    ok["sequences"][1]["scenes"][0]["shots"][0][
        "editorial_target_duration"] = 3.2
    validate_scale_plan(ok)


def test_editorial_target_drift_refused(tmp_path):
    ref = make_historical(tmp_path)
    plan = scale_plan(ref)
    plan["sequences"][1]["scenes"][0]["shots"][0][
        "editorial_target_duration"] = 4.8
    execute_scale_run(plan, tmp_path / "run", make_live_driver(plan, []),
                      _real_adopted_loader(), _flat_runner())
    drifted = scale_plan(ref)
    drifted["sequences"][1]["scenes"][0]["shots"][0][
        "editorial_target_duration"] = 6.4  # post-hoc retiming refused
    with pytest.raises(ValueError, match="plan identity mismatch"):
        execute_scale_run(drifted, tmp_path / "run",
                          make_live_driver(drifted, []),
                          _real_adopted_loader(), _flat_runner())


def test_adopted_loader_dispatch_run_layout(tmp_path):
    from run_production_scale_007 import adopted_loader_dispatch
    run_dir = tmp_path / "oldrun"
    seq_dir = run_dir / "sequence_OLD"
    (seq_dir / "scene_SC_X" / "shot_X1").mkdir(parents=True)
    (seq_dir / "scene_SC_X" / "shot_X1" / "result.json").write_text(
        json.dumps({"shot_id": "X1", "gate": "SHOT_PROVEN",
                    "output_identity": "m1",
                    "asset": {"sha256": "h1"}}), encoding="utf-8")
    (seq_dir / "run_result.json").write_text(json.dumps(
        {"sequence_id": "OLD", "complete": True}), encoding="utf-8")
    (run_dir / "production_run_state.json").write_text(json.dumps(
        {"sequences": {"OLD": {"status": "PROVEN"}}}), encoding="utf-8")
    snap = adopted_loader_dispatch(seq_dir)
    assert snap["sequence_id"] == "OLD" and len(snap["shots"]) == 1
    # Unproven parent run state refuses adoption.
    (run_dir / "production_run_state.json").write_text(json.dumps(
        {"sequences": {"OLD": {"status": "UNRESOLVED"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="not PROVEN"):
        adopted_loader_dispatch(seq_dir)


def test_loudly_archived_slot_allows_contiguous_results(tmp_path):
    scene = {"scene_id": "SC_X", "shots": [
        {"shot_id": f"S{i}", "fixture": "f", "continuity": {"kind": "x"}}
        for i in (1, 2, 3)]}
    scene_dir = tmp_path / "scene_dir"
    for sid in ("S1", "S2", "S3"):
        (scene_dir / f"shot_{sid}").mkdir(parents=True)
    (scene_dir / "shot_S1" / "result.json").write_text(json.dumps(
        {"shot_id": "S1", "gate": "SHOT_PROVEN"}), encoding="utf-8")
    # S2's prior result was loudly archived: re-entry state, not a gap.
    (scene_dir / "shot_S2" / "result_attempt1.json").write_text(json.dumps(
        {"shot_id": "S2", "gate": "OWNER_GATE"}), encoding="utf-8")
    (scene_dir / "shot_S2" / "reentry_note.json").write_text(json.dumps(
        {"archived_result": "result_attempt1.json"}), encoding="utf-8")
    (scene_dir / "shot_S3" / "result.json").write_text(json.dumps(
        {"shot_id": "S3", "gate": "SHOT_PROVEN"}), encoding="utf-8")
    verify_scene_order_integrity(scene_dir, scene)  # no refusal
    # Without the loud archive the same gap is refused.
    (scene_dir / "shot_S2" / "reentry_note.json").unlink()
    with pytest.raises(ValueError, match="out-of-order scene state"):
        verify_scene_order_integrity(scene_dir, scene)
