"""Continuity across the cut between two generations of one scene.

A 16 s scene is rendered as two independent 8 s generations. The second
generation knows nothing about how the first one actually ended, so each
generation declares a start and an end state (who stands where, where each
prop is, which look each character wears). The start state is compiled into
the prompt, and preflight blocks a generation whose start state does not
match the previous generation's end state.

``GenerationHandoff`` carries the previous generation into preflight;
``end_state_verified`` is set only from a reviewed post-render QC
(``qc.HandoffQC``), never from the plan alone.
"""
from __future__ import annotations

from pydantic import Field

from ..core import ContractModel


class ContinuityState(ContractModel):
    positions: dict[str, str] = Field(default_factory=dict)  # NORA: "..."
    props: dict[str, str] = Field(default_factory=dict)      # prop: where
    looks: dict[str, str] = Field(default_factory=dict)      # NORA: look_id
    lighting: str = ""
    time_of_day: str = ""
    location: str = ""     # LocationLook.look_id

    def as_dict(self) -> dict:
        return self.model_dump()

    def describe(self) -> str:
        """Prompt sentence for the start of a generation ("" if empty)."""
        parts = [f"{who} {where}" for who, where in self.positions.items()]
        parts += [f"{prop} {where}" for prop, where in self.props.items()]
        if not parts:
            return ""
        return "Continues from the previous shot: " + "; ".join(parts) + "."


class GenerationHandoff(ContractModel):
    previous_generation_id: str
    previous_action: str
    previous_start: ContinuityState
    previous_end: ContinuityState
    end_state_verified: bool = False   # from a reviewed qc.HandoffQC
