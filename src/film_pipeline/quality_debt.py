"""Quality debt as first-class truth + separated readiness axes
(Package-019 Phases V4-V5).

QualityDebtItem: an explicit, durable record of an accepted creative
defect. Quality debt may NOT silently satisfy a release-quality gate —
it means technical pipeline completion may proceed while creative
quality remains explicitly unresolved.

ReadinessAxes: PIPELINE_TECHNICAL_READY, FILM_CREATIVE_QUALITY_
ACCEPTED and FINAL_CONTENT_RELEASE_READY are independent axes. Known
debt does NOT imply technical failure; technical completion does NOT
imply creative acceptance.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256

QUALITY_DEBT_VERSION = "quality-debt-item-v1"
READINESS_AXES_VERSION = "readiness-axes-v1"


class QualityDebtItem(ContractModel):
    """One accepted creative-quality defect with its evidence chain."""
    schema_version: Literal["quality-debt-item-v1"] = \
        QUALITY_DEBT_VERSION
    debt_id: str = Field(pattern=r"^QD-[0-9]{3}$")
    project: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    category: str = Field(min_length=1)
    affected_canonical_artifacts: list[str] = Field(min_length=1)
    observed_problem: str = Field(min_length=1)
    owner_assessment: str = Field(min_length=1)
    current_impact: str = Field(min_length=1)
    known_evidence: list[str] = Field(min_length=1)
    attempts_already_performed: list[str] = Field(min_length=1)
    what_improved: str
    what_remains_unresolved: str = Field(min_length=1)
    accepted_for_technical_completion: Literal[True] = True
    release_impact: str = Field(min_length=1)
    future_track: str = Field(min_length=1)
    status: Literal["ACTIVE", "RESOLVED"] = "ACTIVE"

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


def validate_debt_cannot_satisfy_release_gates(debt: QualityDebtItem,
                                               gates: dict) -> dict:
    """The frozen rule: recording debt never flips a release-quality
    gate. Returns the gate states unchanged or raises if a caller
    tried to pass debt as satisfaction."""
    for gate, satisfied in gates.items():
        if satisfied is True:
            raise ValueError(
                f"quality debt {debt.debt_id} may not satisfy release "
                f"gate {gate}; gates require real Owner/content inputs")
    return {"gates": gates,
            "rule": "quality debt never satisfies a release-quality "
                    "gate; it only documents accepted creative defects"}


class ReadinessAxes(ContractModel):
    """Three independent completion axes. No single boolean aggregate
    may collapse them."""
    schema_version: Literal["readiness-axes-v1"] = READINESS_AXES_VERSION
    project: str = Field(min_length=1)
    pipeline_technical_ready: bool
    film_creative_quality_accepted: bool
    final_content_release_ready: bool
    content_gates: dict[str, bool]
    derived_from: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_independent_axes(self):
        if self.final_content_release_ready and \
                not self.pipeline_technical_ready:
            raise ValueError(
                "content release cannot be ready while the technical "
                "pipeline is not (false aggregate refused)")
        if self.film_creative_quality_accepted and \
                not self.pipeline_technical_ready:
            raise ValueError(
                "creative acceptance cannot be declared while the "
                "technical pipeline is not proven (false implication "
                "refused)")
        return self
