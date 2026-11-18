"""Capability-Aware Hybrid Provider Router & 3-Checkpoint Human Loop Status."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from film_pipeline.agentic.scheduler import WaveDAGScheduler
from film_pipeline.production.gates import evaluate_gates
from film_pipeline.production.sections import shot_seconds
from film_pipeline.providers.capability import DEFAULT_MODEL, DEFAULT_PROVIDER, get_capability
from film_pipeline.providers.route import resolve_route


class CapabilityRouter:
    """Selects provider lane from proven shot capabilities and tracks Owner CP1-CP3 checkpoints."""

    def route_shot(
        self,
        decl: Any,
        *,
        pkg_header: Any | None = None,
        duration_s: float | None = None,
        strict_face_lock_from_still: bool | None = None,
        multi_location_cast_anchor: bool = False,
        blocking_probe: bool = False,
        budget_remaining: float | None = None,
    ) -> dict[str, Any]:
        gid = decl.generation_id
        if duration_s is not None:
            secs = float(duration_s)
        elif getattr(decl, "duration_s", None) is not None:
            secs = float(decl.duration_s)
        elif pkg_header is not None:
            secs = shot_seconds(decl, pkg_header)
        else:
            secs = float(getattr(decl, "seconds", None) or 6.0)

        if blocking_probe:
            return {
                "generation_id": gid,
                "lane": "vilao_probe",
                "provider": "vilao",
                "model": "h3-480p",
                "duration_s": secs,
                "estimated_credits": 0.0,
                "cost_unit": "USD",
                "budget_blocked": False,
                "reason": "low-cost blocking/pacing probe",
            }

        strict = bool(strict_face_lock_from_still) if strict_face_lock_from_still is not None else bool(decl.visible)
        if multi_location_cast_anchor and not strict:
            return {
                "generation_id": gid,
                "lane": "muse_gateway",
                "provider": "muse",
                "model": "Muse (browser-relay)",
                "duration_s": secs,
                "estimated_credits": 0.0,
                "cost_unit": "muse_requests",
                "budget_blocked": False,
                "reason": "multi-location scene without strict start-frame face lock routed to Muse relay",
            }

        if pkg_header is not None or getattr(decl, "route", None) is not None:
            spec = resolve_route(pkg_header or type("_H", (), {"route": None, "experiment": False})(), decl)
            cap = spec.capability()
            tier = spec.tier
        else:
            cap = get_capability(DEFAULT_PROVIDER, DEFAULT_MODEL)
            tier = "TEST"
        est_credits = cap.price_of(secs, tier)
        lane = "flow_omni_flash" if (cap.provider, cap.model) == ("flow", "omni-1.2-flash") else f"{cap.provider}_{cap.model}"
        model_label = "omni-1.2-flash-360p" if (cap.provider, cap.model) == ("flow", "omni-1.2-flash") else cap.model
        blocked = budget_remaining is not None and float(budget_remaining) < est_credits
        return {
            "generation_id": gid,
            "lane": lane,
            "provider": cap.provider,
            "model": model_label,
            "duration_s": secs,
            "estimated_credits": est_credits,
            "cost_unit": cap.price.unit,
            "budget_blocked": blocked,
            "reason": (
                f"insufficient {cap.price.unit} ({budget_remaining} < {est_credits})"
                if blocked
                else "strict cast/face lock from start still or chained end frame"
            ),
        }

    def checkpoint_plan(
        self,
        pkg: Any,
        *,
        wave_info: dict[str, Any] | None = None,
        gate_results: list[Any] | None = None,
    ) -> dict[str, Any]:
        results = gate_results if gate_results is not None else evaluate_gates(pkg)
        gates = {r.gate: r.status for r in results}
        shots = pkg.typed.get("shots")
        if wave_info is None:
            wave_info = WaveDAGScheduler(pkg).plan_waves() if shots is not None else {"accepted_count": 0, "total_generations": 0}

        if all(gates.get(g) == "PASS" for g in ("1", "2", "3")):
            cp1_status = "APPROVED"
        elif any(gates.get(g) == "OWNER_PENDING" for g in ("1", "2", "3")):
            cp1_status = "OWNER_PENDING"
        else:
            cp1_status = "BLOCKED"

        # CP2: Pilot reel covers first 2 scenes in order; approval requires pilot_approval.json or Gate 6 PASS
        pilot_total, pilot_done = 0, 0
        if shots is not None:
            scene_order: list[str] = []
            for g in shots.generations:
                if g.scene_id not in scene_order:
                    scene_order.append(g.scene_id)
                if len(scene_order) == 2 and g.scene_id not in scene_order:
                    break
            pilot_scenes = set(scene_order[:2])
            pilot_gens = [g for g in shots.generations if g.scene_id in pilot_scenes]
            pilot_total = len(pilot_gens)
            from film_pipeline.production.takes import load_log
            log = load_log(Path(pkg.root), pkg.header.film_id)
            by_id = {g.generation_id: g.version for g in pilot_gens}
            acc = {
                t.generation_id
                for t in log.takes
                if t.status == "ACCEPTED" and t.shot_version == by_id.get(t.generation_id)
            }
            pilot_done = len(acc)
        pilot_approved = gates.get("6") == "PASS"
        pilot_path = Path(pkg.root) / "takes" / "pilot_approval.json"
        if not pilot_approved and pilot_path.is_file():
            try:
                pdoc = json.loads(pilot_path.read_text(encoding="utf-8"))
                if pdoc.get("approved") is True and pdoc.get("film_id") == pkg.header.film_id:
                    pilot_approved = True
            except (OSError, ValueError, AttributeError):
                pilot_approved = False
        if pilot_total > 0 and pilot_done == pilot_total:
            cp2_status = "APPROVED" if pilot_approved else "READY_FOR_PILOT_REVIEW"
        else:
            cp2_status = "PENDING"

        if gates.get("6") == "PASS":
            cp3_status = "APPROVED"
        elif all(gates.get(g) == "PASS" for g in ("1", "2", "3", "4", "5")) and gates.get("6") == "OWNER_PENDING":
            cp3_status = "OWNER_PENDING"
        else:
            cp3_status = "BLOCKED"

        return {
            "film_id": pkg.header.film_id,
            "gates": gates,
            "checkpoints": {
                "CP1_brief_cast_budget": {"status": cp1_status, "gates": {g: gates.get(g) for g in ("1", "2", "3")}},
                "CP2_pilot_scene_reel": {"status": cp2_status, "accepted": pilot_done, "total": pilot_total},
                "CP3_master_acceptance": {
                    "status": cp3_status,
                    "gates": {g: gates.get(g) for g in ("4", "5", "6")},
                    "accepted": wave_info["accepted_count"],
                    "total_generations": wave_info["total_generations"],
                },
            },
        }
