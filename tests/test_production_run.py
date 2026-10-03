"""Offline proofs for the production-run orchestrator (Q4).

Adopted historical sequences are verified read-only (PROVEN-complete, exact
asset hashes, no duplication); live sequences delegate to an injected
executor. Plan identity pinned; completed sequences never re-execute;
completion requires every sequence proven.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from production_run import (
    RunState,
    adopted_sequence_snapshot,
    execute_production_run,
    validate_production_run,
)


def run_plan():
    return {"run_id": "RUN_TEST",
            "sequences": [
                {"sequence_id": "SEQ_A_HIST", "mode": "adopted",
                 "state_ref": "state_ref_marker"},
                {"sequence_id": "SEQ_B_NEW", "mode": "live",
                 "plan_ref": "fixtures/seq_b.json"}]}


def make_historical(tmp_path):
    state_dir = tmp_path / "hist"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {"version": "sequence-state-v1", "sequence_id": "SEQ_A_HIST",
             "started_at": "t", "scenes": {}}
    shots = {}
    for scene, shot_ids in (("SC_A", ["H1", "H2"]), ("SC_B", ["H3"])):
        state["scenes"][scene] = {"scene_id": scene, "status": "PROVEN"}
        scene_dir = state_dir / f"scene_{scene}"
        scene_dir.mkdir(exist_ok=True)
        for sid in shot_ids:
            shot_dir = scene_dir / f"shot_{sid}"
            shot_dir.mkdir(exist_ok=True)
            result = {"shot_id": sid, "gate": "SHOT_PROVEN",
                      "output_identity": "media_" + sid,
                      "asset": {"sha256": "hash_" + sid}}
            (shot_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
            shots[sid] = True
    (state_dir / "sequence_state.json").write_text(
        json.dumps(state), encoding="utf-8")
    return state_dir / "sequence_state.json"


def test_validation_accepts_and_rejects():
    assert validate_production_run(run_plan())["run_id"] == "RUN_TEST"
    dup = run_plan()
    dup["sequences"][1]["sequence_id"] = "SEQ_A_HIST"
    with pytest.raises(ValueError, match="duplicate sequence_id"):
        validate_production_run(dup)
    bad_mode = run_plan()
    bad_mode["sequences"][0]["mode"] = "teleport"
    with pytest.raises(ValueError, match="mode unqualified"):
        validate_production_run(bad_mode)
    no_ref = run_plan()
    no_ref["sequences"][0].pop("state_ref")
    with pytest.raises(ValueError, match="requires state_ref"):
        validate_production_run(no_ref)


def test_adopted_snapshot_verifies_proven_lineage(tmp_path):
    ref = make_historical(tmp_path)
    snapshot = adopted_sequence_snapshot(ref)
    assert len(snapshot["shots"]) == 3
    assert snapshot["shots"]["H1"]["asset_sha256"] == "hash_H1"
    assert all(v == "PROVEN" for v in snapshot["scene_statuses"].values())


def test_adopted_snapshot_fails_on_unproven_or_missing(tmp_path):
    ref = make_historical(tmp_path)
    state = json.loads(ref.read_text(encoding="utf-8"))
    state["scenes"]["SC_B"]["status"] = "UNRESOLVED"
    ref.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ValueError, match="not PROVEN"):
        adopted_sequence_snapshot(ref)
    with pytest.raises(ValueError, match="missing"):
        adopted_sequence_snapshot(tmp_path / "nope.json")


def test_execution_adopts_and_runs_live(tmp_path):
    ref = make_historical(tmp_path)
    plan = run_plan()
    plan["sequences"][0]["state_ref"] = str(ref)
    calls = []

    def live(sequence, state_dir):
        calls.append(sequence["sequence_id"])
        return {"complete": True, "shots_proven": 8}

    result = execute_production_run(plan, tmp_path, live)
    assert calls == ["SEQ_B_NEW"]  # adopted sequence never calls the executor
    assert result["run_complete"] and result["sequences_proven"] == 2
    snapshot = json.loads((tmp_path / "sequence_SEQ_A_HIST" / "run_result.json")
                          .read_text(encoding="utf-8"))
    assert snapshot["mode"] == "adopted" and snapshot["shot_count"] == 3


def test_proven_sequences_never_reexecute(tmp_path):
    ref = make_historical(tmp_path)
    plan = run_plan()
    plan["sequences"][0]["state_ref"] = str(ref)
    calls = []

    def live(sequence, state_dir):
        calls.append(sequence["sequence_id"])
        return {"complete": True}

    execute_production_run(plan, tmp_path, live)
    execute_production_run(plan, tmp_path, live)
    assert calls == ["SEQ_B_NEW"]


def test_run_plan_identity_pinned(tmp_path):
    ref = make_historical(tmp_path)
    plan = run_plan()
    plan["sequences"][0]["state_ref"] = str(ref)
    execute_production_run(plan, tmp_path, lambda s, d: {"complete": True})
    reordered = run_plan()
    reordered["sequences"][0], reordered["sequences"][1] = \
        reordered["sequences"][1], reordered["sequences"][0]
    with pytest.raises(ValueError, match="plan changed"):
        execute_production_run(reordered, tmp_path, lambda s, d: {"complete": True})


def test_incomplete_live_sequence_blocks_run(tmp_path):
    ref = make_historical(tmp_path)
    plan = run_plan()
    plan["sequences"][0]["state_ref"] = str(ref)
    plan["sequences"][0], plan["sequences"][1] = plan["sequences"][1], plan["sequences"][0]
    result = execute_production_run(
        plan, tmp_path, lambda s, d: {"complete": False})
    assert not result["run_complete"]
    # The incomplete live sequence keeps its durable UNRESOLVED status; the
    # adopted sequence still verifies and runs (it blocks only itself).
    assert result["results"][0]["complete"] is False
    assert result["results"][1]["complete"] is True
    assert result["sequences_proven"] == 1
    # A further run must not re-execute the terminal-unresolved sequence:
    # its stored result loads, the executor is never called.
    calls = []

    def tracing(sequence, state_dir):
        calls.append(sequence["sequence_id"])
        return {"complete": False}

    r3 = execute_production_run(plan, tmp_path, tracing)
    assert calls == []
    assert not r3["run_complete"]


def test_run_state_rejects_demoting_proven(tmp_path):
    state = RunState(tmp_path, "RUN_X")
    state.record("SEQ_1", "PROVEN")
    with pytest.raises(ValueError):
        state.record("SEQ_1", "EXECUTING")


def test_adopted_duplicate_shot_refused(tmp_path):
    state_dir = tmp_path / "hist"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {"version": "sequence-state-v1", "sequence_id": "D",
             "started_at": "t", "scenes": {"SC": {"scene_id": "SC",
                                                  "status": "PROVEN"}}}
    scene_dir = state_dir / "scene_SC"
    for parent in ("shot_D1", "shot_D1_copy"):
        (scene_dir / parent).mkdir(parents=True, exist_ok=True)
        (scene_dir / parent / "result.json").write_text(
            json.dumps({"shot_id": "D1", "gate": "SHOT_PROVEN",
                        "asset": {"sha256": "x"}}), encoding="utf-8")
    (state_dir / "sequence_state.json").write_text(
        json.dumps(state), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate adopted shot"):
        adopted_sequence_snapshot(state_dir / "sequence_state.json")
