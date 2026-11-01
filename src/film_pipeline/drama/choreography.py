"""Per-generation choreography and performance cues (WP3).

* Phases - film01/Muse generations had a tail with no function and actions
  that happened twice. A generation is 2-4 contiguous phases with at least
  one ACTION; each "happens exactly once" action must live in an ACTION
  phase; a long trailing HOLD is flagged.
* ``PerformanceCue`` - emotion is stated as visible cues plus what it must
  not be misread as (Muse: contempt rendered as a broad happy grin).
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .scene_bible import RuleIssue

TOLERANCE = 1e-3


class Phase(ContractModel):
    kind: Literal["SETUP", "ACTION", "CONSEQUENCE", "REACTION", "HOLD"]
    start_s: float
    end_s: float
    description: str


class PerformanceCue(ContractModel):
    character: str
    emotion_intent: str
    visible_cues: list[str] = Field(default_factory=list)   # 1-3
    intensity: Literal["restrained", "moderate", "strong"] = "restrained"
    prohibited_misread: str = ""

    def prompt_text(self) -> str:
        return (f"{self.character}: {self.emotion_intent} — "
                f"{', '.join(self.visible_cues)}; {self.intensity}; "
                f"not a {self.prohibited_misread}.")


class GenerationChoreography(ContractModel):
    generation_id: str
    phases: list[Phase] = Field(default_factory=list)
    once_actions: list[str] = Field(default_factory=list)
    gesture_budget: int = 1
    performance: list[PerformanceCue] = Field(default_factory=list)

    def problems(self, duration_s: float, *, max_hold_s: float = 3.0
                 ) -> list[RuleIssue]:
        found: list[RuleIssue] = []

        def add(check: str, severity: str, detail: str) -> None:
            found.append(RuleIssue(check=check, severity=severity,  # type: ignore[arg-type]
                                   detail=f"{self.generation_id}: {detail}"))

        phases = self.phases
        if not 2 <= len(phases) <= 4:
            add("CHOREOGRAPHY", "BLOCK", f"{len(phases)} phases; need 2-4")
        if phases:
            if abs(phases[0].start_s) > TOLERANCE:
                add("CHOREOGRAPHY", "BLOCK",
                    f"first phase starts at {phases[0].start_s:g}s, not 0")
            for a, b in zip(phases, phases[1:]):
                if abs(a.end_s - b.start_s) > TOLERANCE:
                    add("CHOREOGRAPHY", "BLOCK",
                        f"gap/overlap between {a.end_s:g}s and "
                        f"{b.start_s:g}s")
            if abs(phases[-1].end_s - duration_s) > TOLERANCE:
                add("CHOREOGRAPHY", "BLOCK",
                    f"last phase ends at {phases[-1].end_s:g}s, not "
                    f"{duration_s:g}s")
            last = phases[-1]
            if last.kind == "HOLD" and last.end_s - last.start_s > max_hold_s:
                add("TAIL_WITHOUT_FUNCTION", "WARN",
                    f"trailing hold {last.end_s - last.start_s:g}s > "
                    f"{max_hold_s:g}s")
        actions = [p for p in phases if p.kind == "ACTION"]
        if not actions:
            add("CHOREOGRAPHY", "BLOCK", "no ACTION phase")
        action_text = " ".join(p.description for p in actions).lower()
        for once in self.once_actions:
            if once.lower() not in action_text:
                add("CHOREOGRAPHY", "BLOCK",
                    f"once-action {once!r} not in an ACTION phase")
        for cue in self.performance:
            if not 1 <= len(cue.visible_cues) <= 3:
                add("PERFORMANCE", "BLOCK",
                    f"{cue.character}: {len(cue.visible_cues)} visible "
                    "cues; need 1-3")
            if not cue.prohibited_misread.strip():
                add("PERFORMANCE", "BLOCK",
                    f"{cue.character}: no prohibited_misread")
        return found

    def timing_text(self) -> str:
        parts = [f"{p.start_s:g}-{p.end_s:g}s {p.kind.lower()}: "
                 f"{p.description.strip().rstrip('.')}"
                 for p in self.phases]
        text = "Timing: " + "; ".join(parts) + "."
        if self.once_actions:
            text += " Happens exactly once: " + \
                "; ".join(self.once_actions) + "."
        return text
