"""Drama P0 #16 — scene prompt with time-marked shots, dialogue and sound.

One 15-second generation = one prompt. Section order is fixed (Gate 3):

    characters + references -> setting -> shots by time mark
    -> dialogue (who says what, voice) -> sound -> prohibitions

Dialogue stays in Vietnamese exactly as written in the script; the rest of
the prompt is English, which the provider follows more reliably.
"""
from __future__ import annotations

import hashlib

from pydantic import Field

from ..core import ContractModel
from .bible import CharacterReferenceSet, attachment_plan
from .coverage import SceneUnit

SECTION_ORDER = ("characters", "setting", "shots", "dialogue", "sound",
                 "prohibitions")

DEFAULT_PROHIBITIONS = (
    "No on-screen text, subtitles or logos.",
    "No touching.",
    "Nobody looks into the lens.",
)


class CharacterBrief(ContractModel):
    name: str
    appearance: str            # identity + scene look, one clause
    voice: str = ""            # e.g. "low, tired male voice, Hanoi accent"


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
                         max_reference_images: int | None = None
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
        cast.append(f"{brief.name}{ref}: {brief.appearance}{where}.")
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
    sound = [s for s in [room_tone, *(sfx or [])] if s]
    sections = {
        "characters": " ".join(cast),
        "setting": setting.strip().rstrip(".") + ".",
        "shots": (f"{unit.duration_s:g}s scene, 16:9, hard cuts at the "
                  "marks. " + " ".join(shots)),
        "dialogue": ("Vietnamese dialogue, lip-synced: "
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
