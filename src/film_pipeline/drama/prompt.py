"""Drama P0 #16 — scene prompt with time-marked shots, dialogue and sound.

One 15-second generation = one prompt. Section order is fixed (Gate 3):

    characters + references -> setting -> continuity (start state)
    -> shots by time mark -> performance cues -> dialogue (who says what, voice) -> sound
    -> prohibitions

A brief bound to a ``CharacterLook`` uses the look's locked text verbatim,
never a per-script description.

Dialogue stays in Vietnamese exactly as written in the script; the rest of
the prompt is English, which the provider follows more reliably.
"""
from __future__ import annotations

import hashlib

from pydantic import Field

from ..core import ContractModel
from .bible import CharacterLook, CharacterReferenceSet, attachment_plan
from .choreography import GenerationChoreography
from .continuity import ContinuityState
from .coverage import SceneUnit
from .scene_bible import LocationLook

SECTION_ORDER = ("characters", "setting", "continuity", "shots",
                 "performance", "dialogue", "sound", "prohibitions")

DEFAULT_PROHIBITIONS = (
    "No on-screen text, subtitles or logos.",
    "No touching.",
    "Nobody looks into the lens.",
)


class CharacterBrief(ContractModel):
    name: str
    appearance: str = ""       # identity + scene look, one clause
    voice: str = ""            # e.g. "low, tired male voice, Hanoi accent"
    look: CharacterLook | None = None   # locked look; wins over appearance

    @property
    def appearance_text(self) -> str:
        return self.look.text if self.look else self.appearance


class ScenePromptPlan(ContractModel):
    scene_id: str
    duration_s: float
    sections: dict[str, str]
    compiled_text: str
    word_count: int
    reference_attachments: list[dict] = Field(default_factory=list)
    sha256: str


def count_words(text: str) -> int:
    """Whitespace tokens, so a time mark like ``(4.6-7.6s):`` is one word."""
    return len(text.split())


def compile_scene_prompt(unit: SceneUnit, *,
                         characters: list[CharacterBrief],
                         setting: str,
                         room_tone: str = "",
                         sfx: list[str] | None = None,
                         prohibitions: tuple[str, ...] = DEFAULT_PROHIBITIONS,
                         reference_sets: list[CharacterReferenceSet]
                         | None = None,
                         max_reference_images: int | None = None,
                         dialogue_language: str = "Vietnamese",
                         start_state: ContinuityState | None = None,
                         location: LocationLook | None = None,
                         choreography: GenerationChoreography | None = None
                         ) -> ScenePromptPlan:
    attachments = attachment_plan(reference_sets or [],
                                  max_images=max_reference_images)
    referenced = {a["character"] for a in attachments}
    book = unit.axis_book
    cast = []
    for brief in characters:
        side = book.sides.get(brief.name)
        ref = " (see reference image)" if brief.name in referenced else ""
        where = f", always frame-{side.lower()}" if side else ""
        cast.append(f"{brief.name}{ref}: {brief.appearance_text}{where}.")
    shots = []
    for index, shot in enumerate(unit.shots, start=1):
        shots.append(f"Shot {index} ({shot.start_s:g}-{shot.end_s:g}s): "
                     f"{shot.describe(book)}.")
    voices = {b.name: b.voice for b in characters if b.voice}
    dialogue = []
    for index, shot in enumerate(unit.shots, start=1):
        for line in shot.lines:
            voice = f", {voices[line.character]}" \
                if line.character in voices else ""
            dialogue.append(f'{line.character} (shot {index}{voice}): '
                            f'"{line.text}"')
    setting_text = setting.strip().rstrip(".") + "."
    if location is not None:
        # locked set text verbatim, then environment rules, then the rest
        lt = location.text.strip()
        parts = [lt if lt.endswith(".") else lt + "."]
        if location.environment_rules:
            parts.append("; ".join(location.environment_rules).rstrip(".")
                         + ".")
        if setting.strip():
            parts.append(setting_text)
        setting_text = " ".join(parts)
    # cut marks only mean something when the generation holds several shots
    framing = ("hard cuts at the marks" if len(shots) > 1
               else "one continuous shot")
    shots_text = (f"{unit.duration_s:g}s scene, 16:9, {framing}. "
                  + " ".join(shots))
    performance = ""
    if choreography is not None:
        shots_text += " " + choreography.timing_text()
        performance = " ".join(c.prompt_text()
                               for c in choreography.performance)
    sound = [s for s in [room_tone, *(sfx or [])] if s]
    sections = {
        "characters": " ".join(cast),
        "setting": setting_text,
        "continuity": start_state.describe() if start_state else "",
        "shots": shots_text,
        "performance": performance,
        "dialogue": (f"{dialogue_language} dialogue, lip-synced: "
                     + " ".join(dialogue)) if dialogue else "",
        "sound": ("Sound: " + "; ".join(sound) + ".") if sound else "",
        "prohibitions": " ".join(prohibitions),
    }
    text = " ".join(sections[k] for k in SECTION_ORDER if sections[k])
    return ScenePromptPlan(
        scene_id=unit.scene_id, duration_s=unit.duration_s,
        sections=sections, compiled_text=text, word_count=count_words(text),
        reference_attachments=attachments,
        sha256=hashlib.sha256(text.encode()).hexdigest())
