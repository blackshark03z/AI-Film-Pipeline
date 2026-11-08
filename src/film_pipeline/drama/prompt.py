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
import re
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .bible import CharacterLook, CharacterReferenceSet, attachment_plan
from .choreography import GenerationChoreography
from .continuity import ContinuityState
from .coverage import SceneUnit
from .scene_bible import LocationLook

SECTION_ORDER = ("characters", "setting", "continuity", "shots",
                 "performance", "dialogue", "sound", "prohibitions")

# emitted text order of the start-frame style; the sections dict keeps SECTION_ORDER (Gate 3 PROMPT_ORDER)
START_FRAME_TEXT_ORDER = ("characters", "shots", "continuity", "performance", "dialogue", "sound",
                          "setting", "prohibitions")

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
    handle: str = ""           # generic name for the start-frame style, e.g. "the woman"

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


def _sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip()
    return not before or before[-1] in ".!?]"


def _capitalise(text: str) -> str:
    """Upper-case the first letter of the text and of every sentence or timecode ("[2-6s] she" -> "[2-6s] She")."""
    return re.sub(r"(^|[.!?\]]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def apply_handles(text: str, handles: dict[str, str]) -> str:
    """Replace each whole-word, case-sensitive character name with its handle (capitalised at a sentence start)."""
    handles = {n: h for n, h in handles.items() if n and h}
    if not text or not handles:
        return text
    names = sorted(handles, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(n) for n in names) + r")(?!\w)")

    def swap(m: re.Match) -> str:
        handle = handles[m.group(1)]
        if _sentence_start(m.string, m.start()):
            return handle[0].upper() + handle[1:]
        return handle
    return pattern.sub(swap, text)


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
                         end_state: ContinuityState | None = None,
                         location: LocationLook | None = None,
                         choreography: GenerationChoreography | None = None,
                         style: Literal["full", "start_frame"] = "full",
                         handles: dict[str, str] | None = None
                         ) -> ScenePromptPlan:
    """style="start_frame": the image carries looks and set, the prompt describes motion only (P13-04).
    `handles` adds names of characters who are not in `characters` (out of frame) to the name->handle map."""
    start_frame = style == "start_frame"
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
    name_to_handle = {**(handles or {}), **{b.name: b.handle for b in characters if b.handle}}
    dialogue = []
    for index, shot in enumerate(unit.shots, start=1):
        for line in shot.lines:
            if start_frame:
                who = name_to_handle.get(line.character) or line.character
                # P14-05: the same voice words in every shot, so a character keeps one voice across generations
                voice = voices.get(line.character, "").strip()
                how = f", in {'an' if voice[:1].lower() in 'aeiou' else 'a'} {voice}," if voice else ""
                dialogue.append(f"{who[0].upper() + who[1:]}{how} says in {dialogue_language}: {line.text}")
                continue
            voice = f", {voices[line.character]}" \
                if line.character in voices else ""
            dialogue.append(f'{line.character} (shot {index}{voice}): '
                            f'"{line.text}"')
    setting_text = setting.strip().rstrip(".") + "."
    if location is not None:
        # locked set text verbatim, then environment rules, then the rest
        lt = location.text.strip()
        parts = [] if start_frame else [lt if lt.endswith(".") else lt + "."]
        if location.environment_rules:
            parts.append("; ".join(location.environment_rules).rstrip(".")
                         + ".")
        if setting.strip():
            parts.append(setting_text)
        setting_text = " ".join(parts)
    # cut marks only mean something when the generation holds several shots;
    # never "continuous", which invites a loop (feasibility UNCONTROLLED_REPEAT)
    framing = ("hard cuts at the marks" if len(shots) > 1
               else "a single shot, no cuts")
    shots_text = (f"{unit.duration_s:g}s scene, 16:9, {framing}. "
                  + " ".join(shots))
    if start_frame and len(unit.shots) == 1:
        # "unbroken", not "continuous": Google's Omni guide offers both; ours invites a loop (UNCONTROLLED_REPEAT)
        shots_text = (f"A single unbroken {unit.duration_s:g}s shot, no scene cuts, 16:9: "
                      f"{unit.shots[0].describe(book)}.")
    performance = ""
    if choreography is not None:
        if start_frame:
            shots_text += " " + choreography.timecode_text()
            if choreography.once_actions:
                shots_text += " This happens exactly once: " + "; ".join(choreography.once_actions) + "."
        else:
            shots_text += " " + choreography.timing_text()
        performance = " ".join(c.motion_text() if start_frame else c.prompt_text()
                               for c in choreography.performance)
    sound = [s for s in [room_tone, *(sfx or [])] if s]
    if start_frame:
        visible = {c for shot in unit.shots for c in shot.axis.visible}
        if len(visible) < 2:
            prohibitions = tuple(p for p in prohibitions if p != "No touching.")
        continuity = " ".join(t for t in (
            end_state.describe_change(start_state or ContinuityState()),
            end_state.describe_static(start_state or ContinuityState())) if t) if end_state else ""
        dialogue_text = " ".join(dialogue)
        sound_text = ("Sound design: " + "; ".join(sound) + ".") if sound else ""
    else:
        continuity = " ".join(t for t in (
            start_state.describe() if start_state else "",
            end_state.describe_change(start_state or ContinuityState())
            if end_state else "") if t)
        dialogue_text = (f"{dialogue_language} dialogue, lip-synced: "
                         + " ".join(dialogue)) if dialogue else ""
        sound_text = ("Sound: " + "; ".join(sound) + ".") if sound else ""
    sections = {
        "characters": "" if start_frame else " ".join(cast),
        "setting": setting_text,
        "continuity": continuity,
        "shots": shots_text,
        "performance": performance,
        "dialogue": dialogue_text,
        "sound": sound_text,
        "prohibitions": " ".join(prohibitions),
    }
    if start_frame:
        sections = {k: _capitalise(apply_handles(v, name_to_handle)) for k, v in sections.items()}
    # start-frame style reads action first (Google: subject + action, then the rest), the end state right after it
    order = START_FRAME_TEXT_ORDER if start_frame else SECTION_ORDER
    text = " ".join(sections[k] for k in order if sections[k])
    return ScenePromptPlan(
        scene_id=unit.scene_id, duration_s=unit.duration_s,
        sections=sections, compiled_text=text, word_count=count_words(text),
        reference_attachments=attachments,
        sha256=hashlib.sha256(text.encode()).hexdigest())
