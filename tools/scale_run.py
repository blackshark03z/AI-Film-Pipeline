"""Large-scale production-run orchestration (FLOW-PRODUCTION-SCALE-007, Q1).

The smallest generic scale layer above the proven chain — it does NOT
re-implement execution; it composes production_run → sequence_runner →
scene_runner and adds the scale-level custody the frozen package requires:

    ProductionRun → SequencePlan[] → ScenePlan[] → ShotSpec[]

Scale requirements proven here:
- historical immutable sequences (adopted, read-only) alongside fresh live
  sequences; N scenes, N shots; deterministic ordering at every level;
- durable run state with the WHOLE nested plan identity pinned at first run
  (the flat run-layer pin covers sequence ids/modes only);
- per-slot result isolation: one state directory per sequence/scene/shot, no
  collision; every durable result must carry the exact slot path it belongs
  to (wrong-sequence/wrong-scene/wrong-shot results fail closed);
- order integrity: results must be contiguous in frozen order — a result for
  slot k with any earlier slot's result missing is out-of-order state and is
  refused (out-of-order scene/shot refusal; missing-result detection);
- consumed ProviderJob bindings are unique per run: one ProviderJob binds to
  at most one slot, ever (duplicate-binding refusal; at-most-once custody
  visible at scale);
- continuity reference media is project-scoped: a live sequence declares its
  allowed reference media ids; a slot bound to a media id outside its
  sequence scope is refused before any execution (cross-project media
  identity);
- restart-safe at every level: completed shots/scenes/sequences never
  re-execute (delegated layers guarantee this; proven here at 30-slot scale);
- run completion cannot be declared with any unproven sequence/scene/shot.

No provider, Film Core, or AutoEdit assumptions in this layer. The live
executor is injected so offline tests drive restart windows with no
provider or browser involvement.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable

SCALE_STATE_VERSION = "scale-run-state-v1"
TERMINAL_GATES = ("SHOT_PROVEN", "R3_SHOT3_REPROOF_PROVEN")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_scale_plan(plan: dict) -> dict:
    """Fail-closed nested scale-plan validation.

    Plan shape:
        {"run_id", "project_id",
         "sequences": [{"sequence_id", "mode": "adopted"|"live",
                        "state_ref"|"plan_ref",
                        "media_scope": [media_id, ...]   # live only, optional
                        "scenes": [...]                  # live only
                       }]}
    Live sequence scenes follow the sequence_runner shape. Shot ids are
    unique across the WHOLE run; scene ids unique within their sequence;
    continuity reference media ids must lie inside the declaring sequence's
    media_scope (when declared).
    """
    if not isinstance(plan, dict) or not isinstance(plan.get("run_id"), str) \
            or not plan["run_id"]:
        raise ValueError("run_id invalid")
    if not isinstance(plan.get("project_id"), str) or not plan["project_id"]:
        raise ValueError("scale plan requires project_id")
    sequences = plan.get("sequences")
    if not isinstance(sequences, list) or len(sequences) < 1:
        raise ValueError("scale plan requires at least one sequence")
    seen_sequences, seen_shots = set(), set()
    slot_count = 0
    for index, sequence in enumerate(sequences, 1):
        if not isinstance(sequence, dict) or \
                not isinstance(sequence.get("sequence_id"), str) or \
                not sequence["sequence_id"]:
            raise ValueError(f"sequence {index} sequence_id invalid")
        if sequence["sequence_id"] in seen_sequences:
            raise ValueError(f"duplicate sequence_id {sequence['sequence_id']}")
        seen_sequences.add(sequence["sequence_id"])
        mode = sequence.get("mode")
        if mode == "adopted":
            if not isinstance(sequence.get("state_ref"), str) or \
                    not sequence["state_ref"]:
                raise ValueError(f"adopted sequence {sequence['sequence_id']} "
                                 f"requires state_ref")
        elif mode == "live":
            if not isinstance(sequence.get("plan_ref"), str) or \
                    not sequence["plan_ref"]:
                raise ValueError(f"live sequence {sequence['sequence_id']} "
                                 f"requires plan_ref")
            media_scope = sequence.get("media_scope")
            if media_scope is not None and not (
                    isinstance(media_scope, list) and
                    all(isinstance(m, str) and m for m in media_scope)):
                raise ValueError(f"sequence {sequence['sequence_id']} "
                                 f"media_scope invalid")
            scenes = sequence.get("scenes")
            if not isinstance(scenes, list) or len(scenes) < 1:
                raise ValueError(f"live sequence {sequence['sequence_id']} "
                                 f"requires >= 1 scene")
            seen_scenes = set()
            for scene in scenes:
                if not isinstance(scene, dict) or \
                        not isinstance(scene.get("scene_id"), str) or \
                        not scene["scene_id"]:
                    raise ValueError(f"sequence {sequence['sequence_id']} "
                                     f"scene entry invalid")
                if scene["scene_id"] in seen_scenes:
                    raise ValueError(
                        f"duplicate scene_id {scene['scene_id']} in sequence "
                        f"{sequence['sequence_id']}")
                seen_scenes.add(scene["scene_id"])
                shots = scene.get("shots")
                if not isinstance(shots, list) or len(shots) < 1:
                    raise ValueError(
                        f"scene {scene['scene_id']} requires >= 1 shot")
                for shot in shots:
                    if not isinstance(shot, dict) or \
                            not isinstance(shot.get("shot_id"), str) or \
                            not shot["shot_id"]:
                        raise ValueError(
                            f"scene {scene['scene_id']} shot entry invalid")
                    if shot["shot_id"] in seen_shots:
                        raise ValueError(
                            f"duplicate shot_id {shot['shot_id']} across run")
                    seen_shots.add(shot["shot_id"])
                    slot_count += 1
                    continuity = shot.get("continuity")
                    if not isinstance(continuity, dict) or \
                            "kind" not in continuity:
                        raise ValueError(
                            f"shot {shot['shot_id']} continuity invalid")
                    if continuity["kind"] == "reference" and \
                            isinstance(media_scope, list) and \
                            continuity.get("media_id") not in media_scope:
                        raise ValueError(
                            f"shot {shot['shot_id']} references media "
                            f"{continuity.get('media_id')!r} outside sequence "
                            f"{sequence['sequence_id']} media scope "
                            f"(cross-project media identity)")
                    target = shot.get("editorial_target_duration")
                    if target is not None and (
                            not isinstance(target, (int, float)) or
                            isinstance(target, bool) or target <= 0):
                        raise ValueError(
                            f"shot {shot['shot_id']} "
                            f"editorial_target_duration invalid")
        else:
            raise ValueError(
                f"sequence {sequence['sequence_id']} mode unqualified: {mode}")
    plan = {**plan, "slot_count": slot_count}
    return plan


def scale_plan_hash(plan: dict) -> str:
    """Whole-run plan identity: every sequence, scene, shot, continuity,
    and frozen editorial target (drift on any frozen field is refused)."""
    canonical = {
        "run_id": plan["run_id"],
        "project_id": plan["project_id"],
        "sequences": [
            {"sequence_id": s["sequence_id"], "mode": s["mode"],
             "scenes": [
                 {"scene_id": sc["scene_id"],
                  "shots": [{"shot_id": sh["shot_id"],
                             "fixture": sh.get("fixture"),
                             "continuity": sh["continuity"],
                             "editorial_target_duration":
                                 sh.get("editorial_target_duration")}
                            for sh in sc["shots"]]}
                 for sc in s.get("scenes", [])]}
            for s in plan["sequences"]],
    }
    return sha256(json.dumps(canonical, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


class ScaleRunState:
    """Durable scale-level progress + ProviderJob binding ledger (JSON)."""

    def __init__(self, state_dir: Path, run_id: str):
        self.path = Path(state_dir) / "scale_run_state.json"
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("version") != SCALE_STATE_VERSION:
                raise ValueError("scale run state version mismatch")
            if state.get("run_id") != run_id:
                raise ValueError("scale run state belongs to another run")
            self._state = state
        else:
            self._state = {"version": SCALE_STATE_VERSION,
                           "run_id": run_id, "started_at": utc_now(),
                           "sequences": {}, "provider_job_bindings": {}}
            self._save()

    def record_sequence(self, sequence_id: str, status: str, **data) -> None:
        previous = self._state["sequences"].get(sequence_id, {})
        if previous.get("status") == "PROVEN" and status != "PROVEN":
            raise ValueError(
                f"sequence {sequence_id} already PROVEN; refusing {status}")
        self._state["sequences"][sequence_id] = {
            **previous, "status": status, "updated_at": utc_now(), **data}
        self._save()

    def sequence_status(self, sequence_id: str) -> str | None:
        entry = self._state["sequences"].get(sequence_id)
        return entry.get("status") if entry else None

    def bind_provider_job(self, provider_job_id: str, slot_path: str) -> None:
        """Bind a consumed ProviderJob to exactly one slot, forever."""
        if not provider_job_id:
            return
        existing = self._state["provider_job_bindings"].get(provider_job_id)
        if existing is not None and existing != slot_path:
            raise ValueError(
                f"duplicate ProviderJob binding: {provider_job_id} already "
                f"bound to {existing}; refused for {slot_path}")
        self._state["provider_job_bindings"][provider_job_id] = slot_path
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2,
                                        ensure_ascii=False), encoding="utf-8")


def verify_scene_order_integrity(scene_dir: Path, scene: dict) -> None:
    """Contiguity + identity checks over a scene's durable shot results.

    Refuses: a shot result for slot k while any earlier slot in the frozen
    order has no result (out-of-order / missing); a result whose content
    belongs to a different shot (wrong-slot result); a PROVEN shot status
    whose result file is gone (missing result); a result for slot k while
    an earlier slot is PROVEN-without-result (history rewrite).
    """
    scene_state_path = Path(scene_dir) / "scene_state.json"
    statuses = {}
    if scene_state_path.exists():
        scene_state = json.loads(scene_state_path.read_text(encoding="utf-8"))
        statuses = scene_state.get("shots", {})
    seen_missing = False
    for shot in scene["shots"]:
        shot_id = shot["shot_id"]
        result_path = Path(scene_dir) / f"shot_{shot_id}" / "result.json"
        if not result_path.exists():
            if statuses.get(shot_id, {}).get("status") == "PROVEN":
                raise ValueError(
                    f"shot {shot_id} carries a durable PROVEN status but its "
                    f"result file is missing: stale/missing result")
            seen_missing = True
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("shot_id") != shot_id:
            raise ValueError(
                f"shot result in slot {shot_id} carries shot_id "
                f"{result.get('shot_id')!r}: wrong-slot result")
        if seen_missing:
            raise ValueError(
                f"out-of-order scene state: result for {shot_id} exists while "
                f"an earlier shot result is missing in scene "
                f"{scene['scene_id']}")


def verify_sequence_order_integrity(sequence_dir: Path,
                                    sequence: dict) -> None:
    """Contiguity + identity checks over a live sequence's scene results."""
    sequence_state_path = Path(sequence_dir) / "sequence_state.json"
    statuses = {}
    if sequence_state_path.exists():
        sequence_state = json.loads(
            sequence_state_path.read_text(encoding="utf-8"))
        statuses = sequence_state.get("scenes", {})
    seen_missing = False
    for scene in sequence["scenes"]:
        scene_id = scene["scene_id"]
        scene_dir = Path(sequence_dir) / f"scene_{scene_id}"
        result_path = scene_dir / "scene_result.json"
        if not result_path.exists():
            if statuses.get(scene_id, {}).get("status") == "PROVEN":
                raise ValueError(
                    f"scene {scene_id} carries a durable PROVEN status but "
                    f"its result file is missing: stale/missing result")
            verify_scene_order_integrity(scene_dir, scene)
            seen_missing = True
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("scene_id") != scene_id:
            raise ValueError(
                f"scene result in slot {scene_id} carries scene_id "
                f"{result.get('scene_id')!r}: wrong-scene result")
        planned_shots = [s["shot_id"] for s in scene["shots"]]
        result_shots = [r.get("shot_id") for r in result.get("results", [])]
        if result_shots and result_shots != planned_shots:
            raise ValueError(
                f"scene result for {scene_id} does not carry the planned "
                f"shot order: wrong-scene result")
        if seen_missing:
            raise ValueError(
                f"out-of-order sequence state: result for scene {scene_id} "
                f"exists while an earlier scene result is missing in "
                f"sequence {sequence['sequence_id']}")
        verify_scene_order_integrity(scene_dir, scene)


def _bind_results_to_slots(state: ScaleRunState, sequence_id: str,
                           results: list) -> None:
    """Ledger every ProviderJob a live result carries (unique per run)."""
    sequence_dir = state.path.parent / f"sequence_{sequence_id}"
    for result in results:
        provider_job_id = result.get("provider_job_id") or \
            (result.get("asset") or {}).get("provider_job_id")
        if not provider_job_id:
            continue
        shot_id = result.get("shot_id")
        if not shot_id:
            continue
        slot = f"{sequence_id}/{shot_id}"
        state.bind_provider_job(provider_job_id, slot)


def execute_scale_run(plan: dict, state_dir: Path,
                      run_live_sequence: Callable[[dict, Path], dict],
                      adopted_loader: Callable[[dict], dict],
                      run_flat: Callable[..., dict]) -> dict:
    """Execute the whole nested plan through the proven flat run layer.

    ``run_flat(flat_run_dict, state_dir, run_live_sequence, adopted_loader)``
    is ``production_run.execute_production_run`` (injected to keep this
    module import-light). This wrapper adds: whole-plan identity pinning,
    order-integrity verification, ProviderJob binding ledger, and
    completion gating on every slot.
    """
    plan = validate_scale_plan(plan)
    state = ScaleRunState(state_dir, plan["run_id"])
    identity = scale_plan_hash(plan)
    pinned = state._state.get("plan_sha256")
    if pinned is None:
        state._state["plan_sha256"] = identity
        state._save()
    elif pinned != identity:
        raise ValueError(
            "scale plan changed after first execution; whole-run plan "
            "identity mismatch")

    flat_run = {"run_id": plan["run_id"], "sequences": [
        {"sequence_id": s["sequence_id"], "mode": s["mode"],
         **({"state_ref": s["state_ref"]} if s["mode"] == "adopted"
            else {"plan_ref": s["plan_ref"]})}
        for s in plan["sequences"]]}

    def supervised_live_sequence(entry, sequence_state_dir):
        sequence = next(s for s in plan["sequences"]
                        if s["sequence_id"] == entry["sequence_id"])
        verify_sequence_order_integrity(sequence_state_dir, sequence)
        result = run_live_sequence(entry, sequence_state_dir)
        verify_sequence_order_integrity(sequence_state_dir, sequence)
        complete = bool(result.get("complete", result.get("sequence_complete")))
        state.record_sequence(entry["sequence_id"],
                              "PROVEN" if complete else "UNRESOLVED")
        # The flat run layer expects "complete"; keep both keys.
        return {**result, "complete": complete}

    def supervised_adopted(state_ref):
        # production_run calls adopted_loader(Path(state_ref)); locate the
        # declaring sequence to keep the scale ledger in step.
        sequence = next(s for s in plan["sequences"]
                        if s["mode"] == "adopted" and
                        Path(s["state_ref"]) == Path(state_ref))
        # Adopted sequences are read-only: verify and never regenerate.
        snapshot = adopted_loader(Path(state_ref))
        state.record_sequence(sequence["sequence_id"], "PROVEN",
                              adopted=True,
                              adopted_shot_count=len(snapshot["shots"]))
        return snapshot

    result = run_flat(flat_run, state_dir, supervised_live_sequence,
                      supervised_adopted)
    for sequence in plan["sequences"]:
        sequence_id = sequence["sequence_id"]
        run_result_path = Path(state_dir) / f"sequence_{sequence_id}" / \
            "run_result.json"
        if run_result_path.exists():
            run_result = json.loads(
                run_result_path.read_text(encoding="utf-8"))
            if run_result.get("sequence_id") not in (None, sequence_id):
                raise ValueError(
                    f"run result in slot sequence_{sequence_id} carries "
                    f"sequence_id {run_result.get('sequence_id')!r}: "
                    f"wrong-sequence result")
        if sequence["mode"] == "live":
            _bind_results_to_slots(state, sequence_id,
                                   _collect_shot_results(
                                       Path(state_dir) /
                                       f"sequence_{sequence_id}",
                                       sequence))
    if result.get("run_complete"):
        for sequence in plan["sequences"]:
            if state.sequence_status(sequence["sequence_id"]) != "PROVEN":
                raise ValueError(
                    f"run_complete declared with sequence "
                    f"{sequence['sequence_id']} not PROVEN at scale layer")
    adopted_slots = sum(
        (state._state["sequences"].get(s["sequence_id"], {})
         .get("adopted_shot_count") or 0)
        for s in plan["sequences"] if s["mode"] == "adopted")
    return {**result, "scale_plan_sha256": identity,
            "live_slot_count": plan["slot_count"],
            "adopted_slot_count": adopted_slots,
            "slot_count": plan["slot_count"] + adopted_slots}


def _collect_shot_results(sequence_dir: Path, sequence: dict) -> list:
    results = []
    for scene in sequence.get("scenes", []):
        scene_dir = Path(sequence_dir) / f"scene_{scene['scene_id']}"
        for shot in scene["shots"]:
            result_path = scene_dir / f"shot_{shot['shot_id']}" / "result.json"
            if result_path.exists():
                results.append(json.loads(
                    result_path.read_text(encoding="utf-8")))
    return results


def load_scale_plan(path: Path) -> dict:
    return validate_scale_plan(json.loads(
        Path(path).read_text(encoding="utf-8")))
