"""Explainable synthetic routing and a dry provider boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .core import (
    ContractModel, GenerationAttempt, PromptPlan, ProviderCapabilities,
    RoutingDecision, ShotSpec, sha256, validate_contract,
)


def route(
    shot: ShotSpec,
    plans: list[PromptPlan],
    profiles: list[ProviderCapabilities],
    availability: dict[str, bool],
) -> RoutingDecision:
    """Prefer an available profile that loses the fewest requested controls."""
    profile_by_id = {profile.provider_id: profile for profile in profiles}
    if len(profile_by_id) != len(profiles):
        raise ValueError("duplicate provider IDs")
    candidates = []
    for plan in plans:
        profile = profile_by_id.get(plan.provider_id)
        if profile is None or plan.shot_id != shot.shot_id:
            raise ValueError("plan/profile/shot identity mismatch")
        if availability.get(plan.provider_id, False) and profile.supports_text_to_video:
            candidates.append(plan)
    if not candidates:
        raise ValueError("no available text-to-video provider")
    candidates.sort(key=lambda plan: (len(plan.unsupported_controls), plan.provider_id))
    selected = candidates[0]
    required = sorted((set(selected.mapped_controls) | set(selected.unsupported_controls)) - {"text_fallbacks"})
    if "text_to_video" not in required:
        required.insert(0, "text_to_video")
    fallback_ids = [plan.provider_id for plan in candidates[1:]]
    reasons = [
        f"{selected.provider_id} is available and supports text-to-video",
        f"fewest unsupported requested controls: {len(selected.unsupported_controls)}",
    ]
    if fallback_ids:
        reasons.append(f"fallback order: {', '.join(fallback_ids)}")
    else:
        reasons.append("no available fallback")
    core: dict[str, Any] = {
        "shot_id": shot.shot_id,
        "provider_id": selected.provider_id,
        "plan_input_hash": selected.input_hash,
        "required_capabilities": required,
        "fallback_provider_ids": fallback_ids,
        "policy": "available-fewest-unsupported-v1",
    }
    decision = RoutingDecision(
        routing_decision_id=f"route_{sha256(core)}",
        shot_id=shot.shot_id,
        provider_id=selected.provider_id,
        reasons=reasons,
        required_capabilities=required,
        difficulty={"unsupported_control_count": len(selected.unsupported_controls)},
        fallback_provider_ids=fallback_ids,
        benchmark_policy_version="available-fewest-unsupported-v1",
    )
    validate_contract("routing_decision", decision.payload())
    return decision


class DryRunRequest(ContractModel):
    provider_id: str
    shot_id: str
    prompt_plan_hash: str
    routing_decision_id: str
    prompt: str
    mapped_controls: dict[str, Any]
    unsupported_controls: list[str]
    request_id: str


class DryRunProvider:
    """No submit, polling, network, credentials, or browser state."""

    def build_request(self, plan: PromptPlan, decision: RoutingDecision) -> DryRunRequest:
        if plan.provider_id != decision.provider_id or plan.shot_id != decision.shot_id:
            raise ValueError("plan and route disagree")
        basis = {
            "provider_id": plan.provider_id,
            "shot_id": plan.shot_id,
            "prompt_plan_hash": sha256(plan),
            "routing_decision_id": decision.routing_decision_id,
        }
        return DryRunRequest(
            **basis,
            prompt=plan.provider_prompt,
            mapped_controls=plan.mapped_controls,
            unsupported_controls=plan.unsupported_controls,
            request_id=f"dry_{sha256(basis)}",
        )

    def create_attempt(
        self,
        shot: ShotSpec,
        plan: PromptPlan,
        decision: RoutingDecision,
        request: DryRunRequest,
        *,
        started_at: str | None = None,
    ) -> GenerationAttempt:
        if request.prompt_plan_hash != sha256(plan) or request.routing_decision_id != decision.routing_decision_id:
            raise ValueError("dry request lineage mismatch")
        if shot.shot_id != plan.shot_id or shot.spec_version != plan.shot_spec_version:
            raise ValueError("shot and plan lineage mismatch")
        if request.provider_id != decision.provider_id or request.shot_id != shot.shot_id:
            raise ValueError("dry request and route disagree")
        started_at = started_at or datetime.now(timezone.utc).isoformat()
        identity = {
            "shot_spec_hash": sha256(shot),
            "prompt_plan_hash": sha256(plan),
            "routing_decision_id": decision.routing_decision_id,
            "provider_id": decision.provider_id,
            "request_id": request.request_id,
            "started_at": started_at,
        }
        attempt = GenerationAttempt(
            generation_attempt_id=f"attempt_{sha256(identity)}",
            shot_id=shot.shot_id,
            shot_spec_version=shot.spec_version,
            shot_spec_hash=identity["shot_spec_hash"],
            prompt_plan_hash=identity["prompt_plan_hash"],
            routing_decision_id=decision.routing_decision_id,
            provider_id=decision.provider_id,
            status="created",
            started_at=started_at,
        )
        validate_contract("generation_attempt", attempt.payload())
        return attempt
