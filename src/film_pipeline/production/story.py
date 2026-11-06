"""`01_story.json`: the story bible, and the Gate 1 (story_audio_lock) checks that can be decided from it.

Models only import `film_pipeline.core`, so `sections.py` can register `StorySection` without a cycle; the gate
functions take the loaded package duck-typed (`pkg.typed`, `pkg.script`).
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from film_pipeline.core import ContractModel

Ident = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]

BeatFunction = Literal["SETUP", "INCITING", "ESCALATION", "MIDPOINT", "CRISIS", "CLIMAX", "RESOLUTION"]
FUNCTION_ORDER: tuple[str, ...] = ("SETUP", "INCITING", "ESCALATION", "MIDPOINT", "CRISIS", "CLIMAX", "RESOLUTION")
REQUIRED_FUNCTIONS = ("SETUP", "INCITING", "CLIMAX", "RESOLUTION")  # a story without these has no shape
Role = Literal["protagonist", "antagonist", "supporting"]
RightsStatus = Literal["cleared", "pending", "restricted", "unknown"]


class Audience(ContractModel):
    who: Text
    expectation: Text  # what this audience expects from the genre / what they must walk away with


class Logline(ContractModel):
    text: Text
    protagonist: Ident  # StoryCharacter id
    goal: Text
    obstacle: Text


class Beat(ContractModel):
    id: Ident
    function: BeatFunction
    scene_ids: list[Ident] = Field(min_length=1)
    summary: Text


class Act(ContractModel):
    id: Ident
    name: Text
    beats: list[Beat] = Field(min_length=1)


class StoryCharacter(ContractModel):
    id: Ident  # same key as in 03_preprod.characters
    name: Text
    role: Role
    want: Text
    need: Text
    flaw: Text
    arc_change: str = ""  # how this person is different at the end; required for the protagonist
    change_scene_id: Ident | None = None  # the scene where the change happens


class StoryScene(ContractModel):
    purpose: Text
    conflict: Text
    outcome: Text
    value: Text  # the value at stake (e.g. recognition)
    shift: Literal["+", "-"]  # direction the value moves for the protagonist by the end of the scene


class Subplot(ContractModel):
    id: Ident
    summary: Text
    scene_ids: list[Ident] = Field(min_length=1)


class Adaptation(ContractModel):
    source: Text
    rights_status: RightsStatus
    fidelity_notes: str = ""


class Rewrite(ContractModel):
    version: int = Field(ge=1)
    date: Text
    reason: Text
    changed: Text


class StorySection(ContractModel):
    """`01_story.json`."""

    concept: Text
    theme: Text
    genre: Text
    audience: Audience
    premise: Text
    central_conflict: Text
    logline: Logline
    structure: list[Act] = Field(min_length=1)
    plot: Text
    subplots: list[Subplot] = Field(default_factory=list)
    characters: dict[Ident, StoryCharacter]
    scenes: dict[Ident, StoryScene]
    adaptation: Adaptation | None = None  # None = original work; set it whenever source material is used
    source_note: str = ""  # for originals: what (if anything) was taken from outside, and what was not
    rewrite_log: list[Rewrite] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ids(self) -> "StorySection":
        for cid, ch in self.characters.items():
            if ch.id != cid:
                raise ValueError(f"character key {cid!r} != its id {ch.id!r}")
        beat_ids = [b.id for a in self.structure for b in a.beats]
        if len(set(beat_ids)) != len(beat_ids):
            raise ValueError("duplicate beat id")
        return self


_WORD = re.compile(r"[A-Za-z0-9']+")


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if len(w) >= 4}


def story_issues(pkg) -> list[str]:
    """Gate 1 BLOCK rules decidable from the story bible (and the Fountain script, when the profile has one)."""
    story: StorySection | None = pkg.typed.get("story")
    if story is None:  # missing / empty / invalid are reported by the gate before this runs
        return ["story not loaded"]
    out: list[str] = []
    scene_ids = set(story.scenes)

    # scenes <-> beats
    beats = [b for a in story.structure for b in a.beats]
    in_beats: set[str] = set()
    for b in beats:
        for sid in b.scene_ids:
            if sid not in scene_ids:
                out.append(f"beat {b.id}: unknown scene {sid!r}")
            in_beats.add(sid)
    out += [f"scene {sid} appears in no beat" for sid in story.scenes if sid not in in_beats]

    # beat functions in order, with the load-bearing ones present
    rank = [FUNCTION_ORDER.index(b.function) for b in beats]
    if any(later < earlier for earlier, later in zip(rank, rank[1:])):
        out.append("beat functions out of order (expected " + " < ".join(FUNCTION_ORDER) + ")")
    present = {b.function for b in beats}
    out += [f"structure has no {fn} beat" for fn in REQUIRED_FUNCTIONS if fn not in present]

    # characters and arcs
    protagonists = [c for c in story.characters.values() if c.role == "protagonist"]
    if not protagonists:
        out.append("no protagonist")
    for c in story.characters.values():
        if c.change_scene_id is not None and c.change_scene_id not in scene_ids:
            out.append(f"character {c.id}: change scene {c.change_scene_id!r} does not exist")
        if c.role == "protagonist" and not (c.arc_change.strip() and c.change_scene_id):
            out.append(f"protagonist {c.id}: needs arc_change and an existing change_scene_id")

    # subplots
    for sp in story.subplots:
        out += [f"subplot {sp.id}: unknown scene {sid!r}" for sid in sp.scene_ids if sid not in scene_ids]

    # logline: protagonist + goal + obstacle
    lg = story.logline
    hero = story.characters.get(lg.protagonist)
    if hero is None or hero.role != "protagonist":
        out.append(f"logline protagonist {lg.protagonist!r} is not a protagonist in characters")
    elif hero.name.lower() not in lg.text.lower() and lg.protagonist.lower() not in lg.text.lower():
        out.append(f"logline does not name its protagonist ({hero.name})")
    if not _words(lg.goal) & _words(lg.text):
        out.append("logline does not state the goal")
    if not _words(lg.obstacle) & _words(lg.text):
        out.append("logline does not state the obstacle")

    # the script must be the same set of scenes as the story
    script = getattr(pkg, "script", None)
    if script is not None and script.scenes:
        script_ids = {s.scene_id for s in script.scenes}
        out += [f"script scene {sid} has no story entry" for sid in sorted(script_ids - scene_ids)]
        out += [f"story scene {sid} is not in script.fountain" for sid in sorted(scene_ids - script_ids)]

    # story characters must exist in preprod when both are present
    pre = pkg.typed.get("preprod")
    if pre is not None:
        out += [f"story character {cid} has no entry in 03_preprod.characters"
                for cid in story.characters if cid not in pre.characters]
    return out


def story_pending(pkg) -> list[str]:
    """Reasons Gate 1 needs the Owner even though the structure is sound (never PASS on unresolved rights)."""
    story: StorySection | None = pkg.typed.get("story")
    if story is not None and story.adaptation is not None and story.adaptation.rights_status != "cleared":
        return [f"adaptation of {story.adaptation.source!r}: rights_status={story.adaptation.rights_status} "
                "(Owner must clear rights)"]
    return []
