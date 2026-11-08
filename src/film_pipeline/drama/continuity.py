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

from typing import Any

from pydantic import Field, model_serializer

from ..core import ContractModel
from ..production.interaction import ActorPose


class ContinuityState(ContractModel):
    positions: dict[str, str] = Field(default_factory=dict)  # NORA: "..."
    props: dict[str, str] = Field(default_factory=dict)      # prop: where
    looks: dict[str, str] = Field(default_factory=dict)      # NORA: look_id
    lighting: str = ""
    time_of_day: str = ""
    location: str = ""     # LocationLook.look_id
    blocking: dict[str, ActorPose] = Field(default_factory=dict)  # NORA: mark + posture (interaction contract)

    @model_serializer(mode="wrap")
    def _omit_empty_blocking(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if not self.blocking:  # films without the interaction contract keep their golden dumps
            data.pop("blocking", None)
        return data

    def as_dict(self) -> dict:
        return self.model_dump()

    def describe(self) -> str:
        """Prompt sentence for the start of a generation ("" if empty)."""
        parts = [f"{who} {where}" for who, where in self.positions.items()]
        parts += [f"{prop} {where}" for prop, where in self.props.items()]
        if not parts:
            return ""
        return "Continues from the previous shot: " + "; ".join(parts) + "."

    def prop_changes(self, start: "ContinuityState") -> list[str]:
        """Props this end state moves or changes from `start`, as "<prop> <where>" clauses."""
        return [f"{prop.rstrip(':')} {where}" for prop, where in self.props.items() if start.props.get(prop) != where]

    def change_clauses(self, start: "ContinuityState") -> list[str]:
        """Everything this end state changes from `start`: props first, then people's positions (end-frame edit)."""
        return self.prop_changes(start) + [f"{who} {where}" for who, where in self.positions.items()
                                           if start.positions.get(who) != where]

    def describe_change(self, start: "ContinuityState") -> str:
        """Prompt sentence for the props this end state changes from `start`, held to the last frame ("" if none).
        A prompt that names only the start lets the model put things back: film04 SC01_g1 t2 pulled the shutter
        down, then it sprang up again to the one state the prompt named. People's moves stay in the action
        text (the word budget is tight)."""
        parts = self.prop_changes(start)
        if not parts:
            return ""
        return "Ends with " + "; ".join(parts) + ", held to the last frame."

    def describe_static(self, start: "ContinuityState") -> str:
        """Prompt sentence pinning the props this end state leaves as they were ("" if none).
        A prop the prompt does not name is free to move: film04 SC01_g2 t1 rolled the lowered shutter up by itself
        when the action mentioned the gap under it."""
        parts = [f"{prop.rstrip(':')} {where}" for prop, where in start.props.items() if self.props.get(prop) == where]
        if not parts:
            return ""
        return "Unchanged the whole shot, nothing moves it: " + "; ".join(parts) + "."


class GenerationHandoff(ContractModel):
    previous_generation_id: str
    previous_action: str
    previous_start: ContinuityState
    previous_end: ContinuityState
    end_state_verified: bool = False   # from a reviewed qc.HandoffQC
