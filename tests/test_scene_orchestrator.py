"""Offline proofs for the generic N-shot scene orchestration layer.

Every restart window is driven with injected executors — no provider, browser
or filesystem side effects beyond the durable scene state. The scene layer
must accept N >= 1, execute in deterministic plan order, never re-execute a
terminal shot, and never declare scene completion with an unproven shot.
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from film_pipeline.live_runtime import LiveRuntimeExecutor
from film_pipeline.store import SQLiteStore
from scene_runner import SceneState, execute_scene, load_plan, validate_scene_plan


def plan(n=3, continuity="reference"):
    return {"scene_id": "SCENE_TEST", "shots": [
        {"shot_id": f"SHOT_{i}", "fixture": f"fixtures/shot_{i}.json",
         "continuity": ({"kind": "reference", "media_id": "aaaa-bbbb"}
                        if i == 1 or continuity == "reference" else
                        {"kind": "last_frame", "from_shot": f"SHOT_{i - 1}"})}
        for i in range(1, n + 1)]}


def fake_run_shot(gates, calls):
    def run_shot(shot, state_dir, state):
        calls.append(shot["shot_id"])
        return {"shot_id": shot["shot_id"], "gate": gates.get(shot["shot_id"], "SHOT_PROVEN")}
    return run_shot


def test_plan_validation_accepts_n_greater_or_equal_one():
    assert validate_scene_plan(plan(1))["scene_id"] == "SCENE_TEST"
    assert validate_scene_plan(plan(9))["shots"][8]["shot_id"] == "SHOT_9"


@pytest.mark.parametrize("broken", [
    {}, {"scene_id": "S"}, {"scene_id": "S", "shots": []},
    {"scene_id": "S", "shots": [{"shot_id": "A", "fixture": "f"}]},
    {"scene_id": "S", "shots": [{"shot_id": "A", "fixture": "f",
                                 "continuity": {"kind": "warp"}}]},
    {"scene_id": "S", "shots": [{"shot_id": "A", "fixture": "f",
                                 "continuity": {"kind": "last_frame", "from_shot": "B"}},
                                {"shot_id": "B", "fixture": "f",
                                 "continuity": {"kind": "reference", "media_id": "m"}}]},
    {"scene_id": "S", "shots": [{"shot_id": "A", "fixture": "f",
                                 "continuity": {"kind": "reference", "media_id": "m"}},
                                {"shot_id": "A", "fixture": "f",
                                 "continuity": {"kind": "reference", "media_id": "m"}}]},
])
def test_plan_validation_fails_closed(broken):
    with pytest.raises(ValueError):
        validate_scene_plan(broken)


def test_execution_is_ordered_and_proven(tmp_path):
    calls = []
    result = execute_scene(plan(3), tmp_path, fake_run_shot({}, calls))
    assert calls == ["SHOT_1", "SHOT_2", "SHOT_3"]
    assert result["scene_complete"] and result["proven"] == 3


def test_completed_shots_never_reexecuted_after_restart(tmp_path):
    calls = []
    execute_scene(plan(3), tmp_path, fake_run_shot({}, calls))
    result = execute_scene(plan(3), tmp_path, fake_run_shot({}, calls))
    assert calls == ["SHOT_1", "SHOT_2", "SHOT_3"]  # no re-execution
    assert result["scene_complete"]


def test_shot_unresolved_is_never_silently_reexecuted(tmp_path):
    calls = []
    gates = {"SHOT_2": "OWNER_AMBIGUITY_GATE"}
    result = execute_scene(plan(3), tmp_path, fake_run_shot(gates, calls))
    assert result["proven"] == 2 and not result["scene_complete"]
    result2 = execute_scene(plan(3), tmp_path, fake_run_shot({}, calls))
    # The unresolved shot keeps its durable terminal status: no silent retry.
    assert calls.count("SHOT_2") == 1
    assert result2["scene_complete"] is False


def test_scene_completion_requires_every_shot_proven(tmp_path):
    gates = {"SHOT_3": "MEDIA_RESOLUTION_WINDOW_EXPIRED"}
    result = execute_scene(plan(3), tmp_path, fake_run_shot(gates, []))
    assert not result["scene_complete"]


def test_restart_mid_scene_resumes_from_durable_truth(tmp_path):
    calls = []
    full = plan(3)

    def crashing_run_shot(shot, state_dir, state):
        if shot["shot_id"] == "SHOT_3":
            # Model process loss: EXECUTING was durably recorded, no result.
            raise RuntimeError("process lost mid-shot")
        return fake_run_shot({}, calls)(shot, state_dir, state)

    with pytest.raises(RuntimeError):
        execute_scene(full, tmp_path, crashing_run_shot)
    assert calls == ["SHOT_1", "SHOT_2"]
    assert SceneState(tmp_path).status("SHOT_3") == "EXECUTING"
    result = execute_scene(full, tmp_path, fake_run_shot({}, calls))
    # The EXECUTING shot is re-entered exactly once (its own resume logic);
    # proven shots are not re-executed.
    assert calls == ["SHOT_1", "SHOT_2", "SHOT_3"]
    assert result["scene_complete"]


def test_scene_state_rejects_demoting_terminal_status(tmp_path):
    state = SceneState(tmp_path)
    state.record("SHOT_1", "PROVEN")
    with pytest.raises(ValueError):
        state.record("SHOT_1", "EXECUTING")


def test_load_plan_reads_and_validates(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan(2)), encoding="utf-8")
    assert len(load_plan(path)["shots"]) == 2
    path.write_text(json.dumps({"scene_id": "X"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_plan(path)


def test_plan_change_after_execution_is_refused(tmp_path):
    calls = []
    execute_scene(plan(2), tmp_path, fake_run_shot({}, calls))
    changed = plan(2)
    changed["shots"][1]["fixture"] = "fixtures/OTHER.json"
    with pytest.raises(ValueError, match="plan changed"):
        execute_scene(changed, tmp_path, fake_run_shot({}, calls))


def test_shot_order_change_after_execution_is_refused(tmp_path):
    calls = []
    execute_scene(plan(3), tmp_path, fake_run_shot({}, calls))
    reordered = plan(3)
    reordered["shots"][1], reordered["shots"][2] =         reordered["shots"][2], reordered["shots"][1]
    with pytest.raises(ValueError, match="plan changed"):
        execute_scene(reordered, tmp_path, fake_run_shot({}, calls))


def test_rough_cut_receipt_detects_tampered_bytes(tmp_path):
    from film_pipeline.editorial_runner import real_rough_cut
    from test_live_runtime import FakeTransport, make_executor
    import asyncio

    # Minimal proven chain: one shot acquired, QC-passed take persisted.
    class EightSecondTransport(FakeTransport):
        async def fetch(self, job, output_id, destination):
            import subprocess as _sp

            completed = _sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                                 "color=c=black:s=16x16:d=8", "-an",
                                 str(destination)], capture_output=True,
                                text=True, check=False)
            if completed.returncode:
                raise RuntimeError("ffmpeg fixture failed")
            return destination

    executor, store, attempt, job = make_executor(tmp_path, FakeTransport())
    asyncio.run(executor.submit_once(job.provider_job_id))
    executor2 = LiveRuntimeExecutor(store, EightSecondTransport())
    asyncio.run(executor2.reconcile(job.provider_job_id))
    store.bind_output(job.provider_job_id, "remote-output-1")
    destination = tmp_path / "videos"
    assets = asyncio.run(executor2.download_assets(job.provider_job_id, destination))
    from film_pipeline.live_runtime import Asset as AssetModel
    from film_pipeline.qc import (QCStore, derive_disposition, derive_report,
                                  evidence, human_decision, technical_evidence)
    from film_pipeline.core import load_shot
    spec = load_shot(Path(__file__).resolve().parents[1] / "fixtures/flow_canary.json")
    asset = assets[0]
    rows, _meta = technical_evidence(spec, asset)
    human = human_decision(asset=asset, reviewer_id="test", action="APPROVE",
                           visual_pass=True, continuity_pass=True,
                           editorial_pass=True)
    rows = list(rows) + [evidence(asset=asset, evaluator_type="human",
        evaluator_version="t-v1", gate=g, criterion="c", observation="o",
        verdict="pass") for g in ("visual", "continuity", "editorial")]
    record = derive_report(asset, rows, human)
    disposition = derive_disposition(spec.shot_id, asset, record, human)
    qc_store = QCStore(SQLiteStore(store.path))
    qc_store.initialize()
    _record, persisted_take = qc_store.save(asset, rows, human)
    out = real_rough_cut(store.path, project_id="rough_test",
                         selected_take_ids=[persisted_take.selected_take_id],
                         output_dir=tmp_path / "cut")
    rough_path = Path(out["output_path"])
    before = rough_path.read_bytes()
    rough_path.write_bytes(before[:-1] + bytes([before[-1] ^ 0xFF]))
    import hashlib
    assert hashlib.sha256(rough_path.read_bytes()).hexdigest() != out["output_sha256"]
