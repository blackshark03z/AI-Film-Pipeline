"""Typed stage sections of a Production Package; they reuse `film_pipeline.drama` models.

Introduced with P0-04 for the drama profile: 02_direction (viewer comprehension), 03_preprod (looks,
locations, scenes, continuity states, limits, still templates), 04_shots (one declaration per 8 s generation).
Stages not listed here stay permissive dicts in `package.py` until their phase types them.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from film_pipeline.core import ContractModel
from film_pipeline.drama import (AxisBook, CharacterLook, ContinuityState, LocationLook, SceneOccupancy,
                                 StoryTime)
from film_pipeline.drama.choreography import GenerationChoreography
from film_pipeline.drama.coverage import Coverage
from film_pipeline.drama.comprehension import ContextCard, CharacterIntro, IdentityTag, StoryFact
from film_pipeline.drama.feasibility import FeasibilityLimits
from film_pipeline.drama.preflight import PreflightLimits
from film_pipeline.production.camera import CameraSetup, LightingPlan
from film_pipeline.production.direction import DirectionPlan
from film_pipeline.production.edit import EditSection
from film_pipeline.production.planning import RightsEntry
from film_pipeline.production.set_layout import Readout, SetLayout
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


class DirectionSection(DirectionPlan):
    """`02_direction.json`: director's plan (see direction.py) + viewer comprehension."""

    comprehension: ComprehensionSpec = Field(default_factory=ComprehensionSpec)
    translations: dict[str, str] = Field(default_factory=dict)  # sidecar: English text -> second language


class CharacterSpec(ContractModel):
    look: CharacterLook
    video_text: str  # description used in video prompts (the start frame carries the face; no ethnicity words)
    voice: str
    handle: str = ""  # how a start-frame prompt names the person, e.g. "the woman"


class LocationSpec(ContractModel):
    look: LocationLook
    room_tone: str = ""
    layout: SetLayout | None = None  # set_layout.py: zones, objects and named camera positions


class SceneSpec(ContractModel):
    location: str  # LocationLook.look_id
    axis: AxisBook
    occupancy: SceneOccupancy
    story_time: StoryTime
    extras: str = ""  # unnamed people present (never in positions)
    lighting: LightingPlan | None = None  # camera.py: key light plan for the scene (all scenes or none)


class StillTemplates(ContractModel):
    framing: dict[str, str]  # coverage kind -> framing phrase
    character: str  # contains {text}
    plate: str  # contains {text}
    pose: bool = False  # state the SETUP pose as the still's first instant (off keeps film03's frozen golden prompts)


DesignKind = Literal["look", "costume", "hair_makeup", "prop", "location"]
_CHARACTER_KINDS = ("look", "costume", "hair_makeup")
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]*)@([1-9][0-9]*)$")


class DesignEntry(ContractModel):
    """A versioned design decision. Shots pin `id@version`; bumping the version makes every dependent pin stale."""

    kind: DesignKind
    version: int = Field(ge=1)
    owner: Ident | None = None  # character id (look/costume/hair_makeup) or location id (location)
    prop: str = ""  # kind prop: the name used in continuity-state props, e.g. "the letter"
    note: str = ""


def _prop_key(name: str) -> str:
    return name.strip().rstrip(":").strip().lower()


class StillRecord(ContractModel):
    """One registered start still (`03_preprod.json` `stills[<generation_id>]`, see stills.py)."""

    file: str  # path relative to the film root, under media/stills/
    sha256: str
    prompt_sha256: str  # sha256 of the still prompt text the image was made for
    source: str = ""
    credits: float = Field(default=0.0, ge=0)
    registered_at: str = ""
    approved_by: str = ""
    approved_at: str = ""


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
    designs: dict[str, DesignEntry] = Field(default_factory=dict)  # design id -> versioned entry
    rights: list[RightsEntry] = Field(default_factory=list)  # planning.py: legal/rights ledger
    risk_fallbacks: dict[str, str] = Field(default_factory=dict)  # generation_id -> fallback coverage for a HIGH risk
    stills: dict[str, StillRecord] = Field(default_factory=dict)  # generation_id (or "end:<generation_id>") -> registered still (stills.py)

    @model_validator(mode="after")
    def _references_resolve(self) -> "PreprodSection":
        for label, keys in (("characters", self.characters), ("locations", self.locations),
                            ("scenes", self.scenes), ("states", self.states), ("stills", self.stills),
                            ("accepted_overlong", self.accepted_overlong), ("designs", self.designs)):
            _bad_keys(label, [k.removeprefix("end:") for k in keys] if label == "stills" else keys)
        for did, d in self.designs.items():
            if d.kind in _CHARACTER_KINDS and d.owner not in self.characters:
                raise ValueError(f"design {did}: {d.kind} needs a character owner (got {d.owner!r})")
            if d.kind == "location" and d.owner not in self.locations:
                raise ValueError(f"design {did}: location needs a location owner (got {d.owner!r})")
            if d.kind == "prop" and not d.prop.strip():
                raise ValueError(f"design {did}: prop needs the prop name used in continuity states")
        for sid, scene in self.scenes.items():
            if scene.location not in self.locations:
                raise ValueError(f"scene {sid}: unknown location {scene.location!r}")
        return self


class TrackedMotion(ContractModel):
    """A prop the trajectory QC measures (see drama/trajectory.py): where to look and which way it moves.
    direction "still": the prop must not move at all (film04 SC02_g1 t1: the pinned shutter went up and came back)."""

    object: Ident
    roi: tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of the frame
    axis: Literal["x", "y"]
    direction: Literal["down", "up", "left", "right", "still"]

    @model_validator(mode="after")
    def _roi_ok(self) -> "TrackedMotion":
        x0, y0, x1, y1 = self.roi
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError(f"roi {self.roi} must satisfy 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1")
        return self


class ShotDecl(ContractModel):
    """One generation = one shot of 3-15 s rendered from a start frame."""

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
    design_refs: list[Annotated[str, StringConstraints(pattern=_PIN.pattern)]] = Field(default_factory=list)
    # `id@version` of the designs this shot was planned against (checked against 03_preprod.designs)
    camera: CameraSetup | None = None  # camera.py: size/angle/height/movement/lens (all shots or none)
    camera_position: str = ""  # set_layout.py: id of a camera position of the location's layout
    readout: list[Readout] = Field(default_factory=list)  # set_layout.py: what the viewer must read, and the evidence
    version: int = Field(default=1, ge=1)  # retake.py: bumped when a pickup replaces this shot's design
    repair_of: str = ""  # "<generation_id>@v<N>": the version this one replaces
    repair_reason: str = ""
    # an approved end still pins the end state (first/last-frame interpolation, sent in Flow's "Ket thuc" slot)
    end_frame: bool = False
    # the end still's pose, written as a still image (a HOLD phase says what does not move, which an image cannot
    # show); empty = the last phase's description
    end_pose: str = ""
    duration_s: int | None = Field(default=None, ge=3, le=15)  # None = the film header's generation_s
    tracked: TrackedMotion | None = None  # trajectory.py: the moved prop the motion QC measures


def shot_seconds(decl: ShotDecl, header) -> float:
    """Length of one generation: its own `duration_s`, else the film header's `generation_s`."""
    return float(decl.duration_s if decl.duration_s is not None else header.generation_s)


class ShotsSection(ContractModel):
    """`04_shots.json` — generations in production order."""

    generations: list[ShotDecl]
    history: list[ShotDecl] = Field(default_factory=list)  # superseded versions, kept verbatim (never rendered)

    @model_validator(mode="after")
    def _ids_unique_and_chained(self) -> "ShotsSection":
        ids = [g.generation_id for g in self.generations]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate generation_id")
        current = {g.generation_id: g.version for g in self.generations}
        for old in self.history:
            if old.generation_id not in current or old.version >= current[old.generation_id]:
                raise ValueError(f"history {old.generation_id}@v{old.version}: not older than the current version")
        for index, g in enumerate(self.generations):
            prev = g.previous_generation_id
            if prev is not None and (prev not in ids or ids.index(prev) >= index):
                raise ValueError(f"{g.generation_id}: previous_generation_id {prev!r} must be an earlier generation")
            if g.choreography.generation_id != g.generation_id:
                raise ValueError(f"{g.generation_id}: choreography belongs to {g.choreography.generation_id!r}")
        return self


def shot_design_ids(pre: PreprodSection, decl: ShotDecl) -> list[str]:
    """Design ids a shot depends on: owners in frame, its location, props named in its start/end states."""
    people = {*decl.visible, *(c for c in (decl.subject, decl.foreground) if c)}
    scene = pre.scenes.get(decl.scene_id)
    props = {_prop_key(k) for name in (decl.start_state, decl.end_state) if name in pre.states
             for k in pre.states[name].props}
    found = []
    for did, d in pre.designs.items():
        if ((d.kind in _CHARACTER_KINDS and d.owner in people)
                or (d.kind == "location" and scene is not None and scene.location == d.owner)
                or (d.kind == "prop" and _prop_key(d.prop) in props)):
            found.append(did)
    return found


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
        if pre.designs:
            out += _pin_issues(pre, g)
    return out


def _pin_issues(pre: PreprodSection, g: ShotDecl) -> list[str]:
    out: list[str] = []
    pins: dict[str, int] = {}
    for ref in g.design_refs:
        did, version = _PIN.match(ref).groups()
        if did in pins:
            out.append(f"04_shots.json: {g.generation_id}: design {did} pinned twice")
        pins[did] = int(version)
        if did not in pre.designs:
            out.append(f"04_shots.json: {g.generation_id}: pins unknown design {did!r}")
    for did in shot_design_ids(pre, g):
        current = pre.designs[did].version
        if did not in pins:
            out.append(f"04_shots.json: {g.generation_id}: design {did} is not pinned (pin {did}@{current})")
        elif pins[did] != current:
            out.append(f"04_shots.json: {g.generation_id}: pinned {did}@{pins[did]} but current is "
                       f"{did}@{current} (re-plan and re-render this shot)")
    return out


TYPED_SECTIONS: dict[str, type[ContractModel]] = {
    "story": StorySection,
    "direction": DirectionSection,
    "preprod": PreprodSection,
    "shots": ShotsSection,
    "edit": EditSection,
}
