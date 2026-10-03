"""Generic multi-scene sequence orchestration (FLOW-MULTISCENE-SEMANTIC-REPAIR-004).

The smallest sequence layer above the proven scene layer:

SequencePlan → ScenePlan[] → ShotSpec[]
→ per-scene execution (reuses scene_runner.execute_scene)
→ durable sequence state
→ sequence completion only when every scene is proven.

Constraints (frozen package):
- N scenes >= 1, M shots per scene >= 1; no hardcoded counts;
- deterministic scene order and shot order;
- shot_ids unique across the WHOLE sequence;
- durable sequence state, restart-safe; plan identity pinned at first run;
- completed scenes/shots never re-execute; unresolved terminal shots never
  silently re-execute;
- sequence completion cannot be declared with any unproven scene;
- no provider, Film Core, or AutoEdit knowledge in this module.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SEQUENCE_STATE_VERSION = "sequence-state-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_sequence_plan(plan: dict) -> dict:
    """Fail-closed SequencePlan validation. Scene order is execution order."""
    if not isinstance(plan, dict):
        raise ValueError("sequence plan must be an object")
    if not isinstance(plan.get("sequence_id"), str) or not plan["sequence_id"]:
        raise ValueError("sequence_id invalid")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 1:
        raise ValueError("sequence plan requires at least one scene (N >= 1)")
    seen_scenes, seen_shots = set(), set()
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not isinstance(scene.get("scene_id"), str) \
                or not scene["scene_id"]:
            raise ValueError(f"scene {index} scene_id invalid")
        if scene["scene_id"] in seen_scenes:
            raise ValueError(f"duplicate scene_id {scene['scene_id']}")
        seen_scenes.add(scene["scene_id"])
        shots = scene.get("shots")
        if not isinstance(shots, list) or len(shots) < 1:
            raise ValueError(f"scene {scene['scene_id']} requires >= 1 shot")
        for shot_index, shot in enumerate(shots, 1):
            if not isinstance(shot, dict) or not isinstance(shot.get("shot_id"), str) \
                    or not shot["shot_id"]:
                raise ValueError(
                    f"scene {scene['scene_id']} shot {shot_index} shot_id invalid")
            if shot["shot_id"] in seen_shots:
                raise ValueError(f"duplicate shot_id {shot['shot_id']} across scenes")
            seen_shots.add(shot["shot_id"])
            if not isinstance(shot.get("fixture"), str) or not shot["fixture"]:
                raise ValueError(f"shot {shot['shot_id']} fixture invalid")
            continuity = shot.get("continuity")
            if not isinstance(continuity, dict) or "kind" not in continuity:
                raise ValueError(f"shot {shot['shot_id']} continuity invalid")
            kind = continuity["kind"]
            if kind == "reference":
                if not isinstance(continuity.get("media_id"), str) or not continuity["media_id"]:
                    raise ValueError(f"shot {shot['shot_id']} reference continuity requires media_id")
            elif kind == "last_frame":
                earlier = [s["shot_id"] for s in shots[:shot_index - 1]]
                if continuity.get("from_shot") not in earlier:
                    raise ValueError(
                        f"shot {shot['shot_id']} last_frame requires an earlier shot "
                        f"in the same scene")
            else:
                raise ValueError(f"shot {shot['shot_id']} continuity kind unqualified")
    return plan


def sequence_plan_hash(plan: dict) -> str:
    from hashlib import sha256 as _sha256

    import json as _json

    canonical = {"sequence_id": plan["sequence_id"],
                 "scenes": [{"scene_id": s["scene_id"],
                             "shots": [{"shot_id": sh["shot_id"],
                                        "fixture": sh["fixture"],
                                        "continuity": sh["continuity"]}
                                       for sh in s["shots"]]}
                            for s in plan["scenes"]]}
    return _sha256(_json.dumps(canonical, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")).hexdigest()


class SequenceState:
    """Durable, restart-safe sequence progress (JSON on disk)."""

    def __init__(self, state_dir: Path, sequence_id: str):
        self.path = Path(state_dir) / "sequence_state.json"
        self.sequence_id = sequence_id
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("version") != SEQUENCE_STATE_VERSION:
                raise ValueError("sequence state version mismatch")
            if state.get("sequence_id") != sequence_id:
                raise ValueError("sequence state belongs to another sequence")
            self._state = state
        else:
            self._state = {"version": SEQUENCE_STATE_VERSION,
                           "sequence_id": sequence_id,
                           "started_at": utc_now(),
                           "scenes": {}}
            self._save()

    def record_scene(self, scene_id: str, status: str, **data) -> None:
        previous = self._state["scenes"].get(scene_id, {})
        if previous.get("status") == "PROVEN" and status != "PROVEN":
            raise ValueError(f"scene {scene_id} already PROVEN; refusing {status}")
        entry = {**previous, "scene_id": scene_id, "status": status,
                 "updated_at": utc_now(), **data}
        self._state["scenes"][scene_id] = entry
        self._save()

    def scene_status(self, scene_id: str) -> str | None:
        entry = self._state["scenes"].get(scene_id)
        return entry.get("status") if entry else None

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False),
                             encoding="utf-8")


def execute_sequence(plan: dict, state_dir: Path,
                     run_scene: Callable[[dict, Path], dict]) -> dict:
    """Execute a validated sequence plan scene-by-scene in frozen order.

    ``run_scene(scene_entry, scene_state_dir)`` executes ONE scene through the
    scene layer (itself restart-safe) and returns a result dict with
    ``scene_complete``. Restart semantics mirror the scene layer: proven
    scenes never re-execute; an EXECUTING scene is re-entered (its own resume
    logic applies); terminal-unresolved scenes are never silently re-run.
    """
    plan = validate_sequence_plan(plan)
    state = SequenceState(state_dir, plan["sequence_id"])
    identity = sequence_plan_hash(plan)
    pinned = state._state.get("plan_sha256")
    if pinned is None:
        state._state["plan_sha256"] = identity
        state._save()
    elif pinned != identity:
        raise ValueError(
            "sequence plan changed after first execution; frozen plan identity "
            "mismatch — resume the frozen plan or start a new sequence")
    results = []
    for scene in plan["scenes"]:
        scene_id = scene["scene_id"]
        scene_dir = Path(state_dir) / f"scene_{scene_id}"
        scene_result_path = scene_dir / "scene_result.json"
        if scene_result_path.exists():
            results.append(json.loads(scene_result_path.read_text(encoding="utf-8")))
            continue
        status = state.scene_status(scene_id)
        if status not in (None, "EXECUTING"):
            results.append({"scene_id": scene_id, "scene_complete": False,
                            "note": f"durable terminal status {status}; not re-executed"})
            continue
        state.record_scene(scene_id, "EXECUTING")
        result = run_scene(scene, scene_dir)
        result = {**result, "scene_id": scene_id}
        scene_result_path.parent.mkdir(parents=True, exist_ok=True)
        scene_result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
        state.record_scene(scene_id, "PROVEN" if result.get("scene_complete")
                           else "UNRESOLVED")
        results.append(result)
    complete = all(r.get("scene_complete") for r in results) and \
        len(results) == len(plan["scenes"])
    return {"sequence_id": plan["sequence_id"], "results": results,
            "scenes_proven": sum(1 for r in results if r.get("scene_complete")),
            "scenes_total": len(plan["scenes"]),
            "sequence_complete": complete}


def load_sequence_plan(path: Path) -> dict:
    return validate_sequence_plan(json.loads(Path(path).read_text(encoding="utf-8")))
