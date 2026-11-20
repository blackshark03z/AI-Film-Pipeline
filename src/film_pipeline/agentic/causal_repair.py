"""Causal Repair Router with hard 2-strike budget and immediate content-refusal halt.

Routing is driven by REVIEWED defect codes (`production.defects`, recorded on a take review) or, for v1 data, by the
review's broad cause. Unreviewed detector signals never trigger a repair. An unknown code or unknown action STOPs
(`STOP_UNKNOWN_DEFECT`, no automatic retry): there is no default repair.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from film_pipeline.production.defects import DEFECTS, KNOWN_ACTIONS
from film_pipeline.production.retake import retake_plan
from film_pipeline.production.takes import load_log, takes_dir

STOP_UNKNOWN_DEFECT = "STOP_UNKNOWN_DEFECT"

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


def _reviewed_defect_codes(root: Path, entry: Any) -> list[str] | None:
    """Defect codes on the take's stored review; None when the review carries no reviewed-defect data (v1 path).

    Read from the raw JSON so that a code that left the registry is still seen (and STOPs) instead of failing validation.
    A v2 review of a rejected take with no defect cannot be routed: it yields [] (STOP).
    """
    rel = str(getattr(entry, "review_file", "") or "")
    path = takes_dir(root) / rel if rel else None
    if path is None or not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    defects = raw.get("defects") if isinstance(raw, dict) else None
    if defects:
        return [str(d.get("code", "")) if isinstance(d, dict) else "" for d in defects]
    if isinstance(raw, dict) and int(raw.get("evidence_version", 1) or 1) >= 2:
        return []
    return None


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

        spec = DEFECTS.get(code)
        legacy = _CAUSAL_ACTIONS.get(code)
        if spec is None and legacy is None:  # no default repair: an unclassified code must not trigger a retry
            return self._stop(generation_id, code, failed_attempts, limit,
                              f"unknown defect/failure code {code!r}: not in the reviewed-defect registry or the cause table")

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

        if spec is not None:  # reviewed defect: the registry fixes the action and whether a plain retry is allowed
            action, auto_retry = spec.repair_action, spec.auto_retry_allowed
        else:  # v1 cause-based path
            action, auto_retry = legacy[min(max(failed_attempts - 1, 0), len(legacy) - 1)], True  # type: ignore[index]
        if action not in KNOWN_ACTIONS:
            return self._stop(generation_id, code, failed_attempts, limit, f"repair action {action!r} for {code} is not a known action")
        return {
            "generation_id": generation_id,
            "failure_code": code,
            "failed_attempts": failed_attempts,
            "max_attempts": limit,
            "action": action,
            "auto_retry_allowed": auto_retry,
            "escalate": False,
            "halted": False,
            "reason": detail or f"Bounded causal repair attempt {failed_attempts}/{limit} -> {action}"
            + ("" if auto_retry else " (no blind retry: change the start frame / prompt / staging first)"),
        }

    @staticmethod
    def _stop(generation_id: str, code: str, failed_attempts: int, limit: int, reason: str) -> dict[str, Any]:
        return {
            "generation_id": generation_id,
            "failure_code": code,
            "failed_attempts": failed_attempts,
            "max_attempts": limit,
            "action": STOP_UNKNOWN_DEFECT,
            "auto_retry_allowed": False,
            "escalate": True,
            "halted": True,
            "reason": reason,
        }

    def route_defects(
        self,
        generation_id: str,
        defect_codes: list[str],
        *,
        failed_attempts: int = 1,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        """Route a take's reviewed defect codes; the most restrictive row wins (STOP > halt > escalate > no retry > retry)."""
        codes = list(dict.fromkeys(str(c or "").strip().upper() for c in defect_codes))
        if not codes:
            return self._stop(generation_id, "", failed_attempts, self.max_attempts if max_attempts is None else int(max_attempts),
                              "no reviewed defect to route; a detector signal alone never triggers a repair")
        limit = self.max_attempts if max_attempts is None else int(max_attempts)
        rows = [self.route(generation_id, c, failed_attempts=failed_attempts, max_attempts=max_attempts) if c in DEFECTS
                else self._stop(generation_id, c, failed_attempts, limit, f"{c or 'blank'!r} is not a reviewed defect code")
                for c in codes]

        def rank(r: dict[str, Any]) -> int:
            return (r["action"] == STOP_UNKNOWN_DEFECT) * 8 + r["halted"] * 4 + r["escalate"] * 2 + (not r["auto_retry_allowed"])

        out = dict(max(rows, key=rank))  # max keeps the first of equals
        out["defect_codes"] = codes
        out["actions"] = [r["action"] for r in rows]
        return out

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
            reviewed = _reviewed_defect_codes(Path(pkg.root), latest)
            if reviewed is not None:  # reviewed defects (v2 data) decide; the cause is only the v1 fallback
                routed = self.route_defects(g.generation_id, reviewed, failed_attempts=len(all_rejected))
            else:
                cause = str(latest.cause or "").strip().upper()
                routed = self.route(g.generation_id, cause, failed_attempts=len(all_rejected))
            r_row = retake_by_gid.get(g.generation_id, {})
            routed["retake_action"] = r_row.get("action", "")
            routed["rejected_in_version"] = len(rejected_current)
            routed["total_rejected_across_versions"] = len(all_rejected)
            out.append(routed)
        return out
