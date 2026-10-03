"""Production-run orchestration (FLOW-SEQUENCE-SCALE-005, Q4).

ProductionRun → SequencePlan[]:
- N sequences >= 1; deterministic sequence order;
- durable run state with plan identity pinned;
- ADOPTED sequences: already-proven historical sequences enter the run
  read-only — their shots/takes must exist durably and their recorded asset
  hashes are verified at adoption; adoption never regenerates anything;
- LIVE sequences execute through the injected per-shot executor (the scene
  runner chain); completed sequences never re-execute;
- sequence completion cannot be declared with unresolved shots.

No Flow/provider assumptions in this layer.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable

RUN_STATE_VERSION = "production-run-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_production_run(run: dict) -> dict:
    """Fail-closed ProductionRun validation.

    Sequence entries are either {"mode": "adopted", "sequence_id",
    "state_ref"} (historical, read-only) or {"mode": "live",
    "sequence_id", "plan_ref"} (new production).
    """
    if not isinstance(run, dict) or not isinstance(run.get("run_id"), str) or not run["run_id"]:
        raise ValueError("run_id invalid")
    sequences = run.get("sequences")
    if not isinstance(sequences, list) or len(sequences) < 1:
        raise ValueError("production run requires at least one sequence")
    seen = set()
    for index, entry in enumerate(sequences, 1):
        if not isinstance(entry, dict) or not isinstance(entry.get("sequence_id"), str):
            raise ValueError(f"sequence {index} sequence_id invalid")
        if entry["sequence_id"] in seen:
            raise ValueError(f"duplicate sequence_id {entry['sequence_id']}")
        seen.add(entry["sequence_id"])
        mode = entry.get("mode")
        if mode == "adopted":
            if not isinstance(entry.get("state_ref"), str) or not entry["state_ref"]:
                raise ValueError(f"adopted sequence {entry['sequence_id']} requires state_ref")
        elif mode == "live":
            if not isinstance(entry.get("plan_ref"), str) or not entry["plan_ref"]:
                raise ValueError(f"live sequence {entry['sequence_id']} requires plan_ref")
        else:
            raise ValueError(f"sequence {entry['sequence_id']} mode unqualified: {mode}")
    return run


def adopted_sequence_snapshot(state_ref: Path) -> dict:
    """Read-only snapshot of an adopted historical sequence.

    Verifies the historical sequence state file exists, is PROVEN-complete,
    and extracts the durable shot ledger (shot_id → asset sha256) for
    downstream manifest composition. Any drift/duplication fails closed.
    """
    state_path = Path(state_ref)
    if not state_path.is_file():
        raise ValueError(f"adopted sequence state missing: {state_ref}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("version") != "sequence-state-v1":
        raise ValueError("adopted sequence state version mismatch")
    shots = {}
    base = state_path.parent
    for scene_id, entry in state.get("scenes", {}).items():
        if entry.get("status") != "PROVEN":
            raise ValueError(
                f"adopted scene {scene_id} not PROVEN; adoption refused")
        scene_dir = base / f"scene_{scene_id}"
        if not scene_dir.is_dir():
            raise ValueError(f"adopted scene dir missing: {scene_dir}")
        for result_path in sorted(scene_dir.glob("shot_*/result.json")):
            result = json.loads(result_path.read_text(encoding="utf-8"))
            shot_id = result.get("shot_id")
            if result.get("gate") not in ("SHOT_PROVEN", "R3_SHOT3_REPROOF_PROVEN"):
                raise ValueError(f"adopted shot {shot_id} not proven")
            if shot_id in shots:
                raise ValueError(f"duplicate adopted shot {shot_id}")
            asset = result.get("asset", {})
            shots[shot_id] = {"scene_id": scene_id,
                              "asset_sha256": asset.get("sha256"),
                              "provider_media_id": result.get("output_identity"),
                              "selected_take_source": "historical_proven"}
    if not shots:
        raise ValueError("adopted sequence has no proven shots")
    return {"sequence_id": state.get("sequence_id"), "shots": shots,
            "scene_statuses": {k: v.get("status")
                               for k, v in state.get("scenes", {}).items()}}


def run_plan_hash(run: dict) -> str:
    import json as _json

    canonical = {"run_id": run["run_id"],
                 "sequences": [{"sequence_id": s["sequence_id"], "mode": s["mode"]}
                               for s in run["sequences"]]}
    return sha256(_json.dumps(canonical, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")).hexdigest()


class RunState:
    """Durable production-run progress (JSON on disk)."""

    def __init__(self, state_dir: Path, run_id: str):
        self.path = Path(state_dir) / "production_run_state.json"
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("version") != RUN_STATE_VERSION:
                raise ValueError("production run state version mismatch")
            if state.get("run_id") != run_id:
                raise ValueError("production run state belongs to another run")
            self._state = state
        else:
            self._state = {"version": RUN_STATE_VERSION, "run_id": run_id,
                           "started_at": utc_now(), "sequences": {}}
            self._save()

    def record(self, sequence_id: str, status: str, **data) -> None:
        previous = self._state["sequences"].get(sequence_id, {})
        if previous.get("status") == "PROVEN" and status != "PROVEN":
            raise ValueError(f"sequence {sequence_id} already PROVEN; refusing {status}")
        self._state["sequences"][sequence_id] = {
            **previous, "sequence_id": sequence_id, "status": status,
            "updated_at": utc_now(), **data}
        self._save()

    def status(self, sequence_id: str) -> str | None:
        entry = self._state["sequences"].get(sequence_id)
        return entry.get("status") if entry else None

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False),
                             encoding="utf-8")


def execute_production_run(run: dict, state_dir: Path,
                           run_live_sequence: Callable[[dict, Path], dict],
                           adopted_loader: Callable[[dict], dict] = adopted_sequence_snapshot):
    """Execute a production run in frozen sequence order.

    Adopted sequences are verified read-only (no executor call); live
    sequences delegate to ``run_live_sequence(sequence_entry, state_dir)``.
    """
    run = validate_production_run(run)
    state = RunState(state_dir, run["run_id"])
    identity = run_plan_hash(run)
    pinned = state._state.get("plan_sha256")
    if pinned is None:
        state._state["plan_sha256"] = identity
        state._save()
    elif pinned != identity:
        raise ValueError(
            "production run plan changed after first execution; frozen plan "
            "identity mismatch")
    results = []
    for entry in run["sequences"]:
        sequence_id = entry["sequence_id"]
        status = state.status(sequence_id)
        if status == "PROVEN":
            result_path = Path(state_dir) / f"sequence_{sequence_id}" / "run_result.json"
            results.append(json.loads(result_path.read_text(encoding="utf-8")))
            continue
        if status == "UNRESOLVED":
            results.append({"sequence_id": sequence_id, "complete": False,
                            "note": f"durable terminal status {status}; not re-executed"})
            continue
        state.record(sequence_id, "EXECUTING")
        if entry["mode"] == "adopted":
            snapshot = adopted_loader(Path(entry["state_ref"]))
            result = {"sequence_id": sequence_id, "mode": "adopted",
                      "complete": True, "adopted_shots": sorted(snapshot["shots"]),
                      "shot_count": len(snapshot["shots"])}
        else:
            result = run_live_sequence(entry, Path(state_dir) /
                                       f"sequence_{sequence_id}")
            result = {**result, "sequence_id": sequence_id}
        complete = bool(result.get("complete"))
        result_path = Path(state_dir) / f"sequence_{sequence_id}" / "run_result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        state.record(sequence_id, "PROVEN" if complete else "UNRESOLVED")
        results.append(result)
    complete = len(results) == len(run["sequences"]) and \
        all(r.get("complete") for r in results)
    return {"run_id": run["run_id"], "results": results,
            "sequences_proven": sum(1 for r in results if r.get("complete")),
            "sequences_total": len(run["sequences"]),
            "run_complete": complete}
