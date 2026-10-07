"""V2-021 Phases I-J — deterministic PromptCompiler + reference strategy.

Separates WHAT MUST BE TRUE (typed shot truth) from HOW THE PROVIDER IS
ASKED TO RENDER IT (structured prompt sections). No giant mixed-authority
prose: each section has one job, and continuity anchors are explicit.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core import ContractModel

PromptSection = Literal[
    "subject", "world", "blocking", "camera", "motion", "lighting",
    "environmental_causality", "continuity_anchors", "negative_constraints",
]


class ShotTruth(ContractModel):
    """WHAT MUST BE TRUE — provider-independent shot identity."""
    subject: str
    wardrobe: str
    world: str
    blocking: str
    camera: str
    motion: str
    lighting: str
    environmental_causality: list[str] = Field(default_factory=list)
    continuity_anchors: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)


class ProviderPromptPlan(ContractModel):
    """HOW THE PROVIDER IS ASKED — structured, ordered, provider-shaped."""
    target_provider_family: str          # e.g. "seedance_free_route"
    sections: dict[str, str] = Field(default_factory=dict)
    compiled_text: str = ""
    reference_strategy: str = "TEXT_ANCHOR_ONLY"
    reference_lineage: list[str] = Field(default_factory=list)
    sha256: str = ""


class ReferenceStrategy(ContractModel):
    """Phase J — references only where the provider capability truly
    supports them. seedance_v2.0 free route: support_video_ref=false ->
    TEXT_ANCHOR_ONLY; portrait/world reference images are recorded as
    lineage but NOT claimed to condition the provider."""
    mode: Literal["TEXT_ANCHOR_ONLY", "IMAGE_REFERENCE"] = \
        "TEXT_ANCHOR_ONLY"
    supports_video_ref: bool = False
    lineage: list[str] = Field(default_factory=list)


def compile_prompt(truth: ShotTruth, *, strategy: ReferenceStrategy,
                   prefix: str = "Generate a 5-second cinematic video, "
                                 "16:9.") -> ProviderPromptPlan:
    parts = [prefix]
    parts.append(f"{truth.world}")
    parts.append(f"{truth.subject}, {truth.wardrobe}.")
    parts.append(f"{truth.camera} {truth.blocking}")
    if truth.motion:
        parts.append(truth.motion)
    if truth.lighting:
        parts.append(truth.lighting)
    for anchor in truth.continuity_anchors:
        parts.append(anchor)
    for cause in truth.environmental_causality:
        parts.append(cause)
    if truth.negative_constraints:
        parts.append(" " + " ".join(truth.negative_constraints))
    text = " ".join(p.strip() for p in parts if p.strip())
    import hashlib
    return ProviderPromptPlan(
        target_provider_family="seedance_free_route",
        sections={
            "subject": truth.subject, "world": truth.world,
            "blocking": truth.blocking, "camera": truth.camera,
            "motion": truth.motion, "lighting": truth.lighting,
            "environmental_causality": "; ".join(
                truth.environmental_causality),
            "continuity_anchors": "; ".join(truth.continuity_anchors),
            "negative_constraints": " ".join(truth.negative_constraints),
        },
        compiled_text=text,
        reference_strategy=strategy.mode,
        reference_lineage=list(strategy.lineage),
        sha256=hashlib.sha256(text.encode()).hexdigest())
