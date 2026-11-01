"""Film KPI ledger (WP4).

Counts what a film cost against what it delivered, so the pipeline can be
judged by numbers instead of impressions: how many generations were usable
on the first pass, credits per usable second (block investigation is booked
apart, it is research and not production), re-renders per 100 s, and one
``DefectRecord`` per defect naming the stage that should have caught it.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core import ContractModel

DefectCategory = Literal["IDENTITY", "SET", "PROP_LOGIC", "SHOT_SCALE",
                         "PERFORMANCE", "TIMING", "PROVIDER_BLOCK",
                         "TOOLING", "SUBTITLE", "AUDIO"]


class DefectRecord(ContractModel):
    generation_id: str
    category: DefectCategory
    stage_missed: str
    fixed_by: str


class FilmKPI(ContractModel):
    film_id: str
    generations_planned: int = Field(ge=0)
    generations_sent: int = Field(ge=0)
    generations_blocked: int = Field(ge=0)
    generations_first_pass_accepted: int = Field(ge=0)
    credits_total: float = Field(ge=0)
    credits_investigation: float = Field(ge=0)
    usable_seconds: float = Field(ge=0)
    rerenders: int = Field(ge=0)
    defects: list[DefectRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def first_pass_usable_rate(self) -> float:
        """First-pass accepted generations / generations planned."""
        if not self.generations_planned:
            return 0.0
        return self.generations_first_pass_accepted / self.generations_planned

    @property
    def credits_per_usable_second(self) -> float:
        """Production credits (investigation excluded) per usable second."""
        if not self.usable_seconds:
            return 0.0
        return (self.credits_total - self.credits_investigation) \
            / self.usable_seconds

    @property
    def rerenders_per_100s(self) -> float:
        if not self.usable_seconds:
            return 0.0
        return self.rerenders * 100.0 / self.usable_seconds

    def defects_by_category(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.defects:
            out[d.category] = out.get(d.category, 0) + 1
        return out
