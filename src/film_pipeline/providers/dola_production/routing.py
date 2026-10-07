"""V2-019 Phase J — cost/quality plan router (capability-aware).

Only exposes plan modes the capability registry actually proves. A
DRAFT_THEN_FINAL plan is refused unless the registry says true draft->final
exists — an ordinary low-resolution generation is never renamed "draft".
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...core import ContractModel
from .capability import DolaCapabilityRegistry

PlanMode = Literal[
    "NORMAL_FINAL",
    "DRAFT_THEN_FINAL",
    "LOW_COST_EXPLORATION",
    "REFERENCE_HEAVY",
    "HIGH_QUALITY_FINAL",
]


class GenerationPlan(ContractModel):
    plan_mode: PlanMode
    model_id: str
    expected_generations: int
    expected_credits_per_generation: int | None = None
    expected_total_credits: int | None = None
    rationale: str
    draft_supported: bool = False


class DolaPlanRouter:
    def __init__(self, registry: DolaCapabilityRegistry, *,
                 base_video_credit: int = 1) -> None:
        self._registry = registry
        self._base = base_video_credit

    def plan(self, *, model_id: str, mode: PlanMode = "NORMAL_FINAL",
             duration: str | None = None,
             resolution: str | None = None) -> GenerationPlan:
        model = self._registry.model(model_id)
        if model is None:
            raise ValueError("model not in delivered registry: " + model_id)
        supported, reason = self._registry.supports_request(
            model_id=model_id, duration=duration, resolution=resolution)
        if not supported:
            raise ValueError("request not supported by registry: " + reason)
        multiplier = model.credit_multiplier or 1
        per_generation = self._base * multiplier
        if mode == "DRAFT_THEN_FINAL":
            if not self._registry.true_draft_final_supported:
                raise ValueError(
                    "DRAFT_THEN_FINAL refused: provider has no true "
                    "draft->final lineage (a low-resolution generation is "
                    "not a draft)")
            return GenerationPlan(
                plan_mode=mode, model_id=model_id, expected_generations=2,
                expected_credits_per_generation=per_generation,
                expected_total_credits=per_generation * 2,
                rationale="provider draft->final lineage", draft_supported=True)
        if mode == "NORMAL_FINAL":
            return GenerationPlan(
                plan_mode=mode, model_id=model_id, expected_generations=1,
                expected_credits_per_generation=per_generation,
                expected_total_credits=per_generation,
                rationale="single generation on the proven normal route")
        if mode == "LOW_COST_EXPLORATION":
            cheapest = min(
                (m for m in self._registry.models()
                 if m.gate == "FREE"),
                key=lambda m: m.credit_multiplier or 1, default=None)
            if cheapest is None:
                raise ValueError("no free exploration model delivered")
            return GenerationPlan(
                plan_mode=mode, model_id=cheapest.model_id,
                expected_generations=1,
                expected_credits_per_generation=self._base,
                expected_total_credits=self._base,
                rationale="cheapest delivered free model for director "
                          "exploration")
        raise ValueError("plan mode not proven available on Dola: " + mode)
