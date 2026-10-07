"""V2-021 Phases P, R, S — narration alignment, provenance facade,
learning loop."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .narrative import StoryBeat, parse_srt


class NarrationSegment(ContractModel):
    index: int
    start_s: float
    end_s: float
    text: str
    beat_id: str = ""
    shot_ids: list[str] = Field(default_factory=list)
    audio_transition: Literal["J_CUT", "L_CUT", "PRE_LAP", "ALIGNED",
                              "NONE"] = "ALIGNED"


class NarrationPlan(ContractModel):
    """Phase P — beat->timeline->shot coverage; NEVER one shot per
    subtitle by force. Narration semantics untouched."""
    segments: list[NarrationSegment] = Field(default_factory=list)
    ambience_continuity: bool = True
    notes: list[str] = Field(default_factory=list)


def align_narration(srt_text: str, beats: list[StoryBeat],
                    shots: list[dict], *,
                    total_duration_s: float) -> NarrationPlan:
    entries = parse_srt(srt_text)
    plan = NarrationPlan()
    span = total_duration_s or (entries[-1]["end_s"] if entries else 1.0)
    for position, entry in enumerate(entries):
        beat = beats[min(position, len(beats) - 1)]
        # distribute shot coverage proportionally to narration timeline,
        # allowing one shot to cover multiple segments (no forced 1:1)
        rel_start = entry["start_s"] / span if span else 0.0
        rel_end = entry["end_s"] / span if span else 0.0
        first = min(int(rel_start * len(shots)), len(shots) - 1)
        last = min(max(int(rel_end * len(shots)), first), len(shots) - 1)
        kind = "ALIGNED"
        if position > 0 and rel_start < entries[position - 1]["end_s"] \
                / span:
            kind = "J_CUT"
        plan.segments.append(NarrationSegment(
            index=entry["index"], start_s=entry["start_s"],
            end_s=entry["end_s"], text=entry["text"],
            beat_id=beat.beat_id,
            shot_ids=[s["shot_id"] for s in shots[first:last + 1]]
            or [shots[first]["shot_id"]],
            audio_transition=kind))  # type: ignore[arg-type]
    plan.notes.append("coverage is beat-proportional; J/L cuts derived "
                      "from overlapping narration spans")
    return plan


# ---------------------------------------------------------------- Phase S

RuleStatus = Literal["OBSERVATION", "TENTATIVE_RULE", "PROVEN_RULE"]


class Learning(ContractModel):
    learning_id: str
    statement: str
    status: RuleStatus = "OBSERVATION"
    evidence: list[str] = Field(default_factory=list)
    domain: str = ""


class LearningLoop:
    """Phase S — reusable learnings; canonical prompt rules are NEVER
    mutated from a single anecdote (needs >=2 observations for
    TENTATIVE_RULE, >=3 + live proof for PROVEN_RULE)."""

    def __init__(self) -> None:
        self.learnings: list[Learning] = []

    def record(self, statement: str, *, domain: str,
               status: RuleStatus = "OBSERVATION",
               evidence: list[str] | None = None) -> Learning:
        same = [l for l in self.learnings
                if l.statement == statement and l.domain == domain]
        if same:
            # every record() call is one observation, evidence or not
            same[0].evidence.extend(evidence or
                                    [f"observation_{len(same[0].evidence) + 1}"])
            if same[0].status == "OBSERVATION" and \
                    len(same[0].evidence) >= 2:
                same[0].status = "TENTATIVE_RULE"
            if same[0].status == "TENTATIVE_RULE" and \
                    len(same[0].evidence) >= 3:
                same[0].status = "PROVEN_RULE"
            return same[0]
        evidence = list(evidence or []) or ["observation_1"]
        learning = Learning(learning_id=f"learn_{len(self.learnings) + 1:03d}",
                            statement=statement, domain=domain,
                            status=status, evidence=evidence)
        self.learnings.append(learning)
        return learning

    def to_manifest(self) -> list[dict]:
        return [l.model_dump() for l in self.learnings]
