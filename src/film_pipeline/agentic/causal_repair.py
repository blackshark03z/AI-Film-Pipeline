"""Causal Repair Router with hard 2-strike budget and immediate content-refusal halt."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from film_pipeline.production.takes import load_log

_CAUSAL_ACTIONS: dict[str, tuple[str, ...]] = {
    "OFF_FRAME_INTRUSION": ("enable_de_personify_off_frame", "upgrade_single_to_ots"),
    "AXIS_EYELINE_DRIFT": ("restage_start_still", "reframe_safe_edge"),
    "PROP_CONTINUITY_BREAK": ("restage_start_still", "pin_end_frame_prop_state"),
    "PROP_CONTUINITY_BREAK": ("restage_start_still", "pin_end_frame_prop_state"),
    "DIALOGUE_TRUNCATED": ("trim_or_pace_line", "split_into_shorter_beat"),
    "CAMERA_INSTABILITY": ("reframe_safe_edge", "restage_start_still"),
    "PROVIDER_CONTENT_REFUSAL": ("HALT_HUMAN_DECISION",),
}


class CausalRepairRouter:
    """Deterministic failure-code -> bounded retake strategy router (never loops > max_attempts)."""

    def __init__(self, *, max_attempts: int = 2) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = int(max_attempts)

    def route(
        self,
        generation_id: str,
        failure_code: str,
        *,
        failed_attempts: int = 1,
        max_attempts: int | None = None,
        detail: str = "",
    ) -> dict[str, Any]:
        code = str(failure_code or "").strip().upper()
        limit = self.max_attempts if max_attempts is None else int(max_attempts)

        if code == "PROVIDER_CONTENT_REFUSAL":
            return {
                "generation_id": generation_id,
                "failure_code": code,
                "failed_attempts": failed_attempts,
                "max_attempts": limit,
                "action": "HALT_HUMAN_DECISION",
                "auto_retry_allowed": False,
                "escalate": True,
                "halted": True,
                "reason": detail or "Provider content/moderation refusal requires explicit Owner decision; never reword or bypass",
            }

        if failed_attempts >= limit:
            return {
                "generation_id": generation_id,
                "failure_code": code,
                "failed_attempts": failed_attempts,
                "max_attempts": limit,
                "action": "ESCALATE_TO_TECH_LEAD",
                "auto_retry_allowed": False,
                "escalate": True,
                "halted": False,
                "reason": detail or f"Exhausted max_attempts={limit} repair budget without ACCEPTED take",
            }

        options = _CAUSAL_ACTIONS.get(code, ("restage_start_still",))
        idx = min(max(failed_attempts - 1, 0), len(options) - 1)
        action = options[idx]
        return {
            "generation_id": generation_id,
            "failure_code": code or "UNKNOWN",
            "failed_attempts": failed_attempts,
            "max_attempts": limit,
            "action": action,
            "auto_retry_allowed": True,
            "escalate": False,
            "halted": False,
            "reason": detail or f"Bounded causal repair attempt {failed_attempts}/{limit} -> {action}",
        }

    def diagnose_take_log(self, pkg: Any) -> list[dict[str, Any]]:
        """Inspect rejected current-version takes in `takes/index.json` without mutating files."""
        shots = pkg.typed.get("shots")
        if shots is None:
            return []
        log = load_log(Path(pkg.root), pkg.header.film_id)
        out: list[dict[str, Any]] = []
        for g in shots.generations:
            takes = [t for t in log.for_generation(g.generation_id) if t.shot_version == g.version]
            if any(t.status == "ACCEPTED" for t in takes):
                continue
            rejected = [t for t in takes if t.status == "REJECTED"]
            if not rejected:
                continue
            latest = rejected[-1]
            cause = (latest.cause or "OFF_FRAME_INTRUSION").upper()
            out.append(self.route(g.generation_id, cause, failed_attempts=len(rejected)))
        return out
