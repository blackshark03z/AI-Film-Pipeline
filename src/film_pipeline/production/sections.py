"""Typed stage sections of a Production Package; they reuse `film_pipeline.drama` models.

Introduced with P0-04 for the drama profile: 02_direction (viewer comprehension), 03_preprod (looks,
locations, scenes, continuity states, limits, still templates), 04_shots (one declaration per 8 s generation).
Stages not listed here stay permissive dicts in `package.py` until their phase types them.
"""
from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from film_pipeline.core import ContractModel
from film_pipeline.drama import (AxisBook, CharacterLook, ContinuityState, LocationLook, SceneOccupancy,
                                 StoryTime)
from film_pipeline.drama.choreography import GenerationChoreography
from film_pipeline.drama.coverage import Coverage
from film_pipeline.drama.comprehension import ContextCard, CharacterIntro, IdentityTag, StoryFact
from film_pipeline.drama.feasibility import FeasibilityLimits
from film_pipeline.drama.preflight import PreflightLimits
from film_pipeline.production.story import StorySection


# ids become file names (prompts/<id>.txt) and dict keys: no separators, dots or spaces
Ident = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
_IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _bad_keys(label: str, keys) -> None:
    bad = [k for k in keys if not _IDENT.match(k)]
    if bad:
        raise ValueError(f"{label}: invalid ids {bad} (letters, digits, - and _ only)")


class ComprehensionSpec(ContractModel):
    """What the viewer must know, and which shot/card/tag carries it."""

    intros: list[CharacterIntro] = Field(default_factory=list)
    facts: list[StoryFact] = Field(default_factory=list)
    tags: list[IdentityTag] = Field(default_factory=list)
    cards: list[ContextCard] = Field(default_factory=list)


class DirectionSection(ContractModel):
    """`02_direction.json`."""

    comprehension: ComprehensionSpec = Field(default_factory=ComprehensionSpec)
    translations: dict[str, str] = Field(default_factory=dict)  # sidecar: English text -> second language


class CharacterSpec(ContractModel):
    look: CharacterLook
    video_text: str  # description used in video prompts (the start frame carries the face; no ethnicity words)
    voice: str


class LocationSpec(ContractModel):
    look: LocationLook
    room_tone: str = ""


class SceneSpec(ContractModel):
    location: str  # LocationLook.look_id
    axis: AxisBook
    occupancy: SceneOccupancy
    story_time: StoryTime
    extras: str = ""  # unnamed people present (never in positions)


class StillTemplates(ContractModel):
    framing: dict[str, str]  # coverage kind -> framing phrase
    character: str  # contains {text}
    plate: str  # contains {text}


class PreprodSection(ContractModel):
    """`03_preprod.json`."""

    feasibility: FeasibilityLimits
    preflight: PreflightLimits
    characters: dict[str, CharacterSpec]
    locations: dict[str, LocationSpec]  # key = LocationLook.look_id
    scenes: dict[str, SceneSpec]
    states: dict[str, ContinuityState]  # key = state id (e.g. SC02_g1, SC02_end)
    still_templates: StillTemplates
    # generation_id -> reason: prompts known to exceed preflight.max_prompt_words once the start prefix is added
    accepted_overlong: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _references_resolve(self) -> "PreprodSection":
        for label, keys in (("characters", self.characters), ("locations", self.locations),
                            ("scenes", self.scenes), ("states", self.states),
                            ("accepted_overlong", self.accepted_overlong)):
            _bad_keys(label, keys)
        for sid, scene in self.scenes.items():
            if scene.location not in self.locations:
                raise ValueError(f"scene {sid}: unknown location {scene.location!r}")
        return self


class ShotDecl(ContractModel):
    """One generation = one 8 s shot rendered from a start frame."""

    generation_id: Ident
    scene_id: Ident
    coverage: Coverage
    subject: str = ""
    foreground: str = ""
    visible: list[str]
    dialogue: list[int]  # script line numbers of the dialogue spoken in this shot; [] = silent
    start_state: Ident
    end_state: Ident  # state the next generation starts from
    previous_generation_id: Ident | None = None  # None = no handoff (opening of a continuous chain)
    choreography: GenerationChoreography
    sfx: list[str] = Field(default_factory=list)


class ShotsSection(ContractModel):
    """`04_shots.json` — generations in production order."""

    generations: list[ShotDecl]

    @model_validator(mode="after")
    def _ids_unique_and_chained(self) -> "ShotsSection":
        ids = [g.generation_id for g in self.generations]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate generation_id")
        for index, g in enumerate(self.generations):
            prev = g.previous_generation_id
            if prev is not None and (prev not in ids or ids.index(prev) >= index):
                raise ValueError(f"{g.generation_id}: previous_generation_id {prev!r} must be an earlier generation")
            if g.choreography.generation_id != g.generation_id:
                raise ValueError(f"{g.generation_id}: choreography belongs to {g.choreography.generation_id!r}")
        return self


def check_references(typed: dict) -> list[str]:
    """Cross-section references between 03_preprod and 04_shots; returns issue strings (empty = consistent)."""
    pre, shots = typed.get("preprod"), typed.get("shots")
    if pre is None or shots is None:
        return []
    out: list[str] = []
    for g in shots.generations:
        gid = g.generation_id
        if g.scene_id not in pre.scenes:
            out.append(f"04_shots.json: {gid}: unknown scene_id {g.scene_id!r}")
        for field in ("start_state", "end_state"):
            if getattr(g, field) not in pre.states:
                out.append(f"04_shots.json: {gid}: unknown {field} {getattr(g, field)!r}")
        for who in (*g.visible, *(c for c in (g.subject, g.foreground) if c)):
            if who not in pre.characters:
                out.append(f"04_shots.json: {gid}: unknown character {who!r}")
    return out


TYPED_SECTIONS: dict[str, type[ContractModel]] = {
    "story": StorySection,
    "direction": DirectionSection,
    "preprod": PreprodSection,
    "shots": ShotsSection,
}
