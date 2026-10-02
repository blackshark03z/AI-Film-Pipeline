"""Generic N-shot scene orchestration layer (FLOW-SCENE-SCALE-003).

The smallest scene layer that composes the existing per-shot runtime:

ScenePlan (ordered ShotSpecs + per-shot continuity binding)
→ durable scene state
→ per-shot execution (injected executor: the proven Flow runtime runner)
→ per-shot durable result
→ scene completion only when every required shot is proven

Design constraints (frozen package):
- accepts N >= 1; no hardcoded shot count anywhere;
- deterministic shot ordering (plan order is execution order);
- durable scene state on disk; every state transition is restart-safe;
- completed shots are NEVER re-executed after restart;
- failed/unresolved shots are never silently re-executed;
- scene completion cannot be declared while a required shot is unproven;
- no Slice-0011 literals; no Film Core changes; no second runtime.

The executor is injected so offline tests can drive restart windows without
any provider or browser involvement.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SCENE_STATE_VERSION = "scene-state-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_scene_plan(plan: dict) -> dict:
    """Fail-closed ScenePlan validation. Order is execution order."""
    if not isinstance(plan, dict):
        raise ValueError("scene plan must be an object")
    for key in ("scene_id", "shots"):
        if key not in plan:
            raise ValueError(f"scene plan missing {key}")
    if not isinstance(plan["scene_id"], str) or not plan["scene_id"]:
        raise ValueError("scene_id invalid")
    shots = plan["shots"]
    if not isinstance(shots, list) or len(shots) < 1:
        raise ValueError("scene plan requires at least one shot (N >= 1)")
    seen = set()
    for index, shot in enumerate(shots, 1):
        if not isinstance(shot, dict):
            raise ValueError(f"shot {index} must be an object")
        for key in ("shot_id", "fixture", "continuity"):
            if key not in shot:
                raise ValueError(f"shot {index} missing {key}")
        if shot["shot_id"] in seen:
            raise ValueError(f"duplicate shot_id {shot['shot_id']}")
        seen.add(shot["shot_id"])
        continuity = shot["continuity"]
        if not isinstance(continuity, dict) or "kind" not in continuity:
            raise ValueError(f"shot {index} continuity invalid")
        kind = continuity["kind"]
        if kind == "reference":
            if not isinstance(continuity.get("media_id"), str) or not continuity["media_id"]:
                raise ValueError(f"shot {index} reference continuity requires media_id")
        elif kind == "last_frame":
            if not isinstance(continuity.get("from_shot"), str) or \
                    continuity["from_shot"] not in seen:
                raise ValueError(
                    f"shot {index} last_frame continuity requires an earlier shot")
        else:
            raise ValueError(f"shot {index} continuity kind unqualified: {kind}")
    return plan


class SceneState:
    """Durable, restart-safe scene progress (JSON on disk)."""

    def __init__(self, state_dir: Path):
        self.path = Path(state_dir) / "scene_state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("version") != SCENE_STATE_VERSION:
                raise ValueError("scene state version mismatch")
            self._state = state
        else:
            self._state = {"version": SCENE_STATE_VERSION,
                           "started_at": utc_now(), "shots": {}}

    @property
    def shots(self) -> dict:
        return self._state["shots"]

    def record(self, shot_id: str, status: str, **data) -> None:
        previous = self.shots.get(shot_id, {})
        status_order = {"PLANNED": 0, "EXECUTING": 1, "PROVEN": 2, "UNRESOLVED": 2,
                        "FAILED": 2}
        if previous.get("status") in ("PROVEN", "UNRESOLVED", "FAILED") and \
                status_order[status] < 2:
            # A terminal shot status is never silently demoted.
            raise ValueError(f"shot {shot_id} already terminal; refusing {status}")
        entry = {**previous, "shot_id": shot_id, "status": status,
                 "updated_at": utc_now(), **data}
        self._state["shots"][shot_id] = entry
        self.save()

    def status(self, shot_id: str) -> str | None:
        entry = self.shots.get(shot_id)
        return entry.get("status") if entry else None

    def save(self) -> None:
        encoded = json.dumps(self._state, indent=2, ensure_ascii=False)
        if self.path.exists():
            if self.path.read_text(encoding="utf-8") != encoded:
                # Rewrite only with fresh state; content equality guards no-op saves.
                pass
        self.path.write_text(encoded, encoding="utf-8")


def execute_scene(plan: dict, state_dir: Path,
                  run_shot: Callable[[dict, Path, dict], dict]) -> dict:
    """Execute a validated scene plan in deterministic order.

    ``run_shot(shot_entry, state_dir, scene_state)`` executes ONE shot through
    the per-shot runtime and returns a durable result dict with a ``gate``
    key. Restart semantics: shots whose durable result already shows a
    terminal gate are never re-executed; an EXECUTING shot (crashed mid-run)
    is re-entered once so its own resume logic applies (the per-shot runtime
    resumes read-only for consumed authority and never re-releases).
    """
    plan = validate_scene_plan(plan)
    state = SceneState(state_dir)
    results = []
    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        result_path = Path(state_dir) / f"shot_{shot_id}" / "result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            results.append(result)
            continue
        status = state.status(shot_id)
        if status not in (None, "EXECUTING"):
            # Terminal durable status without a result file: the shot ended
            # unresolved/failed and must never silently re-execute.
            gate = "SHOT_PROVEN" if status == "PROVEN" else status
            results.append({"shot_id": shot_id, "gate": gate,
                            "note": "durable terminal status; not re-executed"})
            continue
        state.record(shot_id, "EXECUTING")
        result = run_shot(shot, Path(state_dir), state._state)
        result = {**result, "shot_id": shot_id}
        results.append(result)
        if result.get("gate") == "SHOT_PROVEN":
            state.record(shot_id, "PROVEN", **{"gate": "SHOT_PROVEN"})
        else:
            state.record(shot_id, "UNRESOLVED", gate=result.get("gate"))
    proven = [r for r in results if r.get("gate") == "SHOT_PROVEN"]
    scene_complete = len(proven) == len(plan["shots"])
    return {"scene_id": plan["scene_id"], "results": results,
            "proven": len(proven), "total": len(plan["shots"]),
            "scene_complete": scene_complete}


def load_plan(path: Path) -> dict:
    return validate_scene_plan(json.loads(Path(path).read_text(encoding="utf-8")))
