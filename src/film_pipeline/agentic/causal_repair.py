"""Causal Repair Router with hard 2-strike budget and immediate content-refusal halt."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from film_pipeline.production.retake import retake_plan
from film_pipeline.production.takes import load_log

_CAUSAL_ACTIONS: dict[str, tuple[str, ...]] = {
    "PROMPT": ("rewrite_prompt_plain_single_action", "split_into_shorter_beat"),
    "START_FRAME": ("regenerate_start_still", "restage_clean_character_still"),
    "PROVIDER_LIMIT": ("retry_transient_once", "cover_with_insert_or_reaction"),
    "STAGING": ("simplify_choreography_phase", "restage_blocking_or_insert"),
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

        if not code or code == "UNKNOWN":
            return {
                "generation_id": generation_id,
                "failure_code": code or "UNCLASSIFIED",
                "failed_attempts": failed_attempts,
                "max_attempts": limit,
                "action": "CLASSIFY",
                "auto_retry_allowed": False,
                "escalate": False,
                "halted": False,
                "reason": detail or "Rejected take has no classified cause (PROMPT / START_FRAME / PROVIDER_LIMIT / STAGING)",
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
            "failure_code": code,
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
        retake_by_gid = {row["generation_id"]: row for row in retake_plan(log, shots)}
        out: list[dict[str, Any]] = []
        for g in shots.generations:
            all_takes = log.for_generation(g.generation_id)
            current = [t for t in all_takes if t.shot_version == g.version]
            if any(t.status == "ACCEPTED" for t in current):
                continue
            rejected_current = [t for t in current if t.status == "REJECTED"]
            if not rejected_current:
                continue
            all_rejected = [t for t in all_takes if t.status == "REJECTED"]
            latest = rejected_current[-1]
            cause = str(latest.cause or "").strip().upper()
            routed = self.route(g.generation_id, cause, failed_attempts=len(all_rejected))
            r_row = retake_by_gid.get(g.generation_id, {})
            routed["retake_action"] = r_row.get("action", "")
            routed["rejected_in_version"] = len(rejected_current)
            routed["total_rejected_across_versions"] = len(all_rejected)
            out.append(routed)
        return out
