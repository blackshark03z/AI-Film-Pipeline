"""Typed stage sections of a Production Package; they reuse `film_pipeline.drama` models.

Introduced with P0-04 for the drama profile: 02_direction (viewer comprehension), 03_preprod (looks,
locations, scenes, continuity states, limits, still templates), 04_shots (one declaration per 8 s generation).
Stages not listed here stay permissive dicts in `package.py` until their phase types them.
"""
from __future__ import annotations

from pydantic import Field, model_validator

from film_pipeline.core import ContractModel
from film_pipeline.drama import (AxisBook, CharacterLook, ContinuityState, LocationLook, SceneOccupancy,
                                 StoryTime)
from film_pipeline.drama.choreography import GenerationChoreography
from film_pipeline.drama.comprehension import ContextCard, CharacterIntro, IdentityTag, StoryFact
from film_pipeline.drama.feasibility import FeasibilityLimits
from film_pipeline.drama.preflight import PreflightLimits


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

    @model_validator(mode="after")
    def _references_resolve(self) -> "PreprodSection":
        for sid, scene in self.scenes.items():
            if scene.location not in self.locations:
                raise ValueError(f"scene {sid}: unknown location {scene.location!r}")
        return self


class ShotDecl(ContractModel):
    """One generation = one 8 s shot rendered from a start frame."""

    generation_id: str
    scene_id: str
    coverage: str  # MASTER | OTS | SINGLE
    subject: str = ""
    foreground: str = ""
    visible: list[str]
    start_state: str
    end_state: str  # state the next generation starts from
    previous_generation_id: str | None = None  # None = no handoff (opening of a continuous chain)
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
        for g in self.generations:
            if g.previous_generation_id is not None and g.previous_generation_id not in ids:
                raise ValueError(f"{g.generation_id}: unknown previous_generation_id {g.previous_generation_id!r}")
            if g.choreography.generation_id != g.generation_id:
                raise ValueError(f"{g.generation_id}: choreography belongs to {g.choreography.generation_id!r}")
        return self


TYPED_SECTIONS: dict[str, type[ContractModel]] = {
    "direction": DirectionSection,
    "preprod": PreprodSection,
    "shots": ShotsSection,
}
