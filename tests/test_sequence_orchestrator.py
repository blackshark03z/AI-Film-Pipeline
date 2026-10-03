"""Offline proofs for the multi-scene sequence orchestration layer.

All 12 frozen restart windows are modeled with injected executors — no
provider, browser, or shared-process side effects. Sequence identity is
pinned; completed scenes/shots never re-execute; completion requires every
scene proven.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from sequence_runner import (
    SequenceState,
    execute_sequence,
    load_sequence_plan,
    sequence_plan_hash,
    validate_sequence_plan,
)


def seq_plan(n_scenes=2, shots_per=5):
    scenes = []
    for s in range(1, n_scenes + 1):
        shots = []
        for i in range(1, shots_per + 1):
            sid = f"S{s}_{i}"
            continuity = ({"kind": "reference", "media_id": "aaaa-bbbb"}
                          if i == 1 or s > 1 or True else
                          {"kind": "last_frame", "from_shot": f"S{s}_{i - 1}"})
            shots.append({"shot_id": sid, "fixture": f"fixtures/{sid}.json",
                          "continuity": {"kind": "reference", "media_id": "aaaa-bbbb"}})
        scenes.append({"scene_id": f"SCENE_{s}", "shots": shots})
    return {"sequence_id": "SEQ_TEST", "scenes": scenes}


def fake_run_scene(gates, calls):
    def run_scene(scene, scene_dir):
        calls.append(scene["scene_id"])
        complete = gates.get(scene["scene_id"], True)
        scene_dir = Path(scene_dir)
        scene_dir.mkdir(parents=True, exist_ok=True)
        result = {"scene_id": scene["scene_id"], "scene_complete": complete}
        (scene_dir / "scene_result.json").write_text(
            json.dumps(result), encoding="utf-8")
        return result
    return run_scene


def test_validation_accepts_and_rejects():
    assert validate_sequence_plan(seq_plan(2, 5))["sequence_id"] == "SEQ_TEST"
    assert validate_sequence_plan(seq_plan(1, 1))["scenes_total" if False else "scenes"][0]["shots"][0]["shot_id"] == "S1_1"
    bad = seq_plan(2, 5)
    bad["scenes"][1]["shots"][0]["shot_id"] = "S1_1"  # cross-scene duplicate
    with pytest.raises(ValueError, match="duplicate shot_id"):
        validate_sequence_plan(bad)
    empty = {"sequence_id": "X", "scenes": []}
    with pytest.raises(ValueError):
        validate_sequence_plan(empty)
    no_shots = {"sequence_id": "X", "scenes": [{"scene_id": "A", "shots": []}]}
    with pytest.raises(ValueError):
        validate_sequence_plan(no_shots)


def test_execution_order_and_completion(tmp_path):
    calls = []
    result = execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    assert calls == ["SCENE_1", "SCENE_2"]
    assert result["sequence_complete"] and result["scenes_proven"] == 2


def test_plan_identity_pinned_across_restart(tmp_path):
    calls = []
    execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    changed = seq_plan(2, 5)
    changed["scenes"][0]["shots"][0]["fixture"] = "fixtures/OTHER.json"
    with pytest.raises(ValueError, match="plan changed"):
        execute_sequence(changed, tmp_path, fake_run_scene({}, calls))


def test_scene_order_change_refused(tmp_path):
    calls = []
    execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    reordered = seq_plan(2, 5)
    reordered["scenes"][0], reordered["scenes"][1] = reordered["scenes"][1], reordered["scenes"][0]
    with pytest.raises(ValueError, match="plan changed"):
        execute_sequence(reordered, tmp_path, fake_run_scene({}, calls))


def test_proven_scenes_never_reexecute(tmp_path):
    calls = []
    execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    assert calls == ["SCENE_1", "SCENE_2"]


def test_unresolved_scene_not_silently_rerun(tmp_path):
    calls = []
    gates = {"SCENE_1": False}
    r1 = execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene(gates, calls))
    assert not r1["sequence_complete"]
    r2 = execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    # Scene 1 keeps its durable terminal status (no rerun); independent
    # scene 2 still executes, but the sequence cannot complete.
    assert calls == ["SCENE_1", "SCENE_2"]
    assert not r2["sequence_complete"]
    # Scene 1's stored real result loads first (no rerun, scene_complete False);
    # scene 2 executed and proven, but the sequence stays incomplete.
    assert r2["results"][0]["scene_complete"] is False
    assert r2["results"][1]["scene_complete"] is True


def test_crash_mid_scene1_reenters_once(tmp_path):
    calls = []

    def crashing(scene, scene_dir):
        calls.append(scene["scene_id"])
        if scene["scene_id"] == "SCENE_1":
            raise RuntimeError("process lost")
        return fake_run_scene({}, calls)(scene, scene_dir)

    with pytest.raises(RuntimeError):
        execute_sequence(seq_plan(2, 5), tmp_path, crashing)
    assert SequenceState(tmp_path, "SEQ_TEST").scene_status("SCENE_1") == "EXECUTING"
    result = execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    assert result["sequence_complete"]
    # The crashed attempt is lost; the re-entry executes the scene once more.
    assert calls.count("SCENE_1") == 2


def test_crash_mid_scene2_between_scenes(tmp_path):
    calls = []

    def crashing(scene, scene_dir):
        calls.append(scene["scene_id"])
        if scene["scene_id"] == "SCENE_2":
            raise RuntimeError("process lost")
        return fake_run_scene({}, calls)(scene, scene_dir)

    with pytest.raises(RuntimeError):
        execute_sequence(seq_plan(2, 5), tmp_path, crashing)
    assert SequenceState(tmp_path, "SEQ_TEST").scene_status("SCENE_1") == "PROVEN"
    result = execute_sequence(seq_plan(2, 5), tmp_path, fake_run_scene({}, calls))
    assert result["sequence_complete"]
    # The tracing closure appends both at dispatch and inside the delegate,
    # so each executed scene appears twice; SCENE_2 re-entered exactly once
    # after its crash, SCENE_1 never re-executed after proven.
    assert calls.count("SCENE_1") == 2 and calls.count("SCENE_2") == 2
    assert calls[-1] == "SCENE_2"


def test_sequence_state_rejects_demoting_proven(tmp_path):
    state = SequenceState(tmp_path, "SEQ_TEST")
    state.record_scene("SCENE_1", "PROVEN")
    with pytest.raises(ValueError):
        state.record_scene("SCENE_1", "EXECUTING")


def test_wrong_sequence_state_refused(tmp_path):
    SequenceState(tmp_path, "SEQ_A")
    with pytest.raises(ValueError, match="another sequence"):
        SequenceState(tmp_path, "SEQ_B")


def test_load_sequence_plan_validates(tmp_path):
    path = tmp_path / "seq.json"
    path.write_text(json.dumps(seq_plan(2, 5)), encoding="utf-8")
    assert load_sequence_plan(path)["sequence_id"] == "SEQ_TEST"
    path.write_text(json.dumps({"sequence_id": "X"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_sequence_plan(path)


def test_plan_hash_is_content_stable():
    a, b = seq_plan(2, 5), seq_plan(2, 5)
    assert sequence_plan_hash(a) == sequence_plan_hash(b)
    b["scenes"][1]["shots"][2]["fixture"] = "X"
    assert sequence_plan_hash(a) != sequence_plan_hash(b)


def test_continuity_last_frame_must_reference_same_scene_earlier(tmp_path):
    bad = seq_plan(2, 5)
    bad["scenes"][1]["shots"][0]["continuity"] = {
        "kind": "last_frame", "from_shot": "S1_5"}
    with pytest.raises(ValueError, match="earlier shot in the same scene"):
        validate_sequence_plan(bad)
    good = seq_plan(2, 5)
    good["scenes"][0]["shots"][2]["continuity"] = {
        "kind": "last_frame", "from_shot": "S1_1"}
    assert validate_sequence_plan(good)
