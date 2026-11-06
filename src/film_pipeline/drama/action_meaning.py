"""SRT sentence -> faithful action (Owner rule, 2026-11-06).

SHOT08 "Brennan shoved Irene. She staggered back." was prompted and judged
against a self-added deep backbend; several takes failed a requirement the
source never stated. The operator declares the sentence's meaning using the
source's own words; this module only checks that declaration against the
SRT and the shot's choreography. It never reads the video or infers meaning.

* Cue boundaries are subtitle packaging: a declared sentence must include
  every cue it spans.
* Initiator, action, receiver and consequence must be copied from the
  source sentence, so the requirement cannot drift from what was said.
* The choreography must stage one ACTION before the REACTION/CONSEQUENCE.
* Escalations the source does not state are only warned about, because a
  prompt may legitimately negate them ("without falling").
"""
from __future__ import annotations

import re

from pydantic import Field

from ..core import ContractModel
from .choreography import GenerationChoreography
from .scene_bible import RuleIssue

_SENTENCE_END = re.compile(r"[.!?…][\"'”’)\]]*$")
ESCALATIONS = ("backbend", "arch", "fall", "fell", "collapse", "injur", "blood",
               "knock", "slam", "punch", "hit", "grab", "grip", "again", "twice")


def sentences(cues: list[dict]) -> list[dict]:
    """Join consecutive cues until the text ends a sentence."""
    found, pending = [], []
    for cue in cues:
        if not cue["text"].strip():
            continue
        pending.append(cue)
        if _SENTENCE_END.search(cue["text"].strip()):
            found.append(_sentence(pending))
            pending = []
    if pending:
        found.append(_sentence(pending))
    return found


def _sentence(cues: list[dict]) -> dict:
    return {"cue_ids": [c["index"] for c in cues], "start_s": cues[0]["start_s"],
            "end_s": cues[-1]["end_s"], "text": " ".join(c["text"].strip() for c in cues)}


def _contains(text: str, words: str) -> bool:
    return re.search(r"\b" + re.escape(words.strip().lower()) + r"\b", text.lower()) is not None


class ActionMeaning(ContractModel):
    source_cues: list[int] = Field(min_length=1)
    initiator: str
    action: str
    receiver: str = ""
    direction: str = ""
    consequence: str = ""

    def source_text(self, cues: list[dict]) -> str:
        wanted = set(self.source_cues)
        return " ".join(c["text"].strip() for c in cues if c["index"] in wanted)

    def problems(self, shot_id: str, cues: list[dict], window: tuple[float, float],
                 choreography: GenerationChoreography | None) -> list[RuleIssue]:
        found: list[RuleIssue] = []

        def block(detail: str) -> None:
            found.append(RuleIssue(check="ACTION_MEANING", severity="BLOCK",
                                   detail=f"{shot_id}: {detail}"))

        by_id = {c["index"]: c for c in cues}
        unknown = [i for i in self.source_cues if i not in by_id]
        if unknown:
            block(f"source cues {unknown} are not in the SRT")
            return found
        declared = set(self.source_cues)
        for sentence in sentences(cues):
            ids = set(sentence["cue_ids"])
            if ids & declared and not ids <= declared:
                block(f"sentence {sentence['text']!r} spans cues {sorted(ids)}; "
                      "declare the whole sentence")
        if not any(by_id[i]["end_s"] > window[0] and by_id[i]["start_s"] < window[1]
                   for i in self.source_cues):
            block("source cues do not overlap this shot's timeline window")
        text = self.source_text(cues)
        for field in ("initiator", "action", "receiver", "direction", "consequence"):
            value = getattr(self, field)
            if value.strip() and not _contains(text, value):
                block(f"{field} {value!r} is not in the source sentence; copy its words")
        if not self.initiator.strip() or not self.action.strip():
            block("declare who initiates and the action")
        if choreography is None:
            block("stage the action with choreography phases")
            return found
        kinds = [p.kind for p in choreography.phases]
        if "ACTION" not in kinds:
            return found  # GenerationChoreography.problems already blocks this.
        if not choreography.once_actions:
            block("name the initiating action in once_actions so it happens once")
        if self.consequence.strip() and not {"REACTION", "CONSEQUENCE"} & set(
                kinds[kinds.index("ACTION") + 1:]):
            block("the stated consequence needs a REACTION/CONSEQUENCE phase after the ACTION")
        return found

    def escalations(self, cues: list[dict], directed_text: str) -> list[str]:
        """Escalation words in the direction that the source never states."""
        source = self.source_text(cues).lower()
        directed = directed_text.lower()
        return [w for w in ESCALATIONS
                if re.search(r"\b" + w, directed) and not re.search(r"\b" + w, source)]

    def qc_questions(self) -> list[str]:
        receiver = f" {self.receiver}" if self.receiver.strip() else ""
        questions = [f"Does {self.initiator} visibly {self.action}{receiver} once, "
                     "before any reaction?"]
        if self.consequence.strip():
            who = self.receiver.strip() or self.initiator
            questions.append(f"Does {who}'s reaction ({self.consequence}) follow from that "
                             "contact, without an added deeper pose or fall?")
        questions += ["Is the chain setup -> contact -> reaction -> aftermath visible "
                      "without a cut hiding it?",
                      "No cooperative approach, repeated action or event the source "
                      "does not state?"]
        return questions
