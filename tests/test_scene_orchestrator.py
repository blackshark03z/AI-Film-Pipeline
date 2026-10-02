"""Offline proofs for the generic N-shot scene orchestration layer.

Every restart window is driven with injected executors — no provider, browser
or filesystem side effects beyond the durable scene state. The scene layer
must accept N >= 1, execute in deterministic plan order, never re-execute a
terminal shot, and never declare scene completion with an unproven shot.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

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
    execute_scene(plan(2), tmp_path, fake_run_shot({}, calls))
    assert calls == ["SHOT_1", "SHOT_2"]
    # Crash marker: shot 3 EXECUTING without a durable result file.
    state = SceneState(tmp_path)
    state.record("SHOT_3", "EXECUTING")
    result = execute_scene(plan(3), tmp_path, fake_run_shot({}, calls))
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
