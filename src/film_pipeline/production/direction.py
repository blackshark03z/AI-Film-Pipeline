"""Director's treatment and per-scene direction (`02_direction.json`), and the Gate 2 checks decidable from it.

Models import only `core` and `drama` so `sections.DirectionSection` can embed them; the gate function takes the
loaded package duck-typed (`pkg.typed` holds story, direction, shots).
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from film_pipeline.core import ContractModel
from film_pipeline.drama.coverage import Coverage

Ident = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]

Device = Literal["insert", "push", "hold", "reaction"]
TransitionKind = Literal["CUT", "DISSOLVE", "MATCH", "J_CUT", "L_CUT"]
Intensity = Annotated[int, Field(ge=0, le=5)]
MAX_EMOTIONAL_JUMP = 2  # between consecutive scenes, per character, without a stated cause beat


class Vision(ContractModel):
    tone: Text
    references: list[Text] = Field(default_factory=list)  # as words, never images or titles pasted as prompts


class VisualRule(ContractModel):
    rule: Text
    why: Text


class POV(ContractModel):
    whose: Ident  # character id whose view the scene favours
    audience_knows: list[Ident] = Field(default_factory=list)  # comprehension fact ids the audience holds here
    characters_know: dict[Ident, list[Ident]] = Field(default_factory=dict)  # character id -> fact ids


class Emphasis(ContractModel):
    moment: Text
    device: Device
    generation_id: Ident | None = None  # shot that carries it
    fact_id: Ident | None = None  # the reveal it serves, if any


class Curve(ContractModel):
    start: Intensity
    end: Intensity


class Hold(ContractModel):
    generation_id: Ident
    seconds: float = Field(gt=0)
    why: Text


class Pacing(ContractModel):
    target_avg_shot_s: float = Field(gt=0)
    holds: list[Hold] = Field(default_factory=list)


class Transition(ContractModel):
    kind: TransitionKind
    reason: Text


class SceneDirection(ContractModel):
    pov: POV
    emphasis: list[Emphasis] = Field(default_factory=list)
    curve: dict[Ident, Curve]  # character id -> intensity at start / end of the scene
    jump_cause_beat: Ident | None = None  # beat that justifies a big emotional jump INTO this scene
    pacing: Pacing
    transition_in: Transition
    transition_out: Transition


class Reveal(ContractModel):
    """A fact the audience learns at a given moment; it must be staged with an emphasis device."""

    fact_id: Ident  # StoryFact.fact_id in the comprehension block
    scene_id: Ident


class DirectionPlan(ContractModel):
    """The director-owned part of `02_direction.json` (comprehension/translations stay in DirectionSection)."""

    vision: Vision | None = None
    visual_rules: list[VisualRule] = Field(default_factory=list)
    scenes: dict[Ident, SceneDirection] = Field(default_factory=dict)
    reveals: list[Reveal] = Field(default_factory=list)
    coverage_plan: dict[Ident, list[Coverage]] = Field(default_factory=dict)  # beat id -> required shot types


def direction_issues(pkg) -> list[str]:
    """Gate 2 BLOCK rules: treatment complete, emotional continuity, beat coverage, staged reveals."""
    direction = pkg.typed.get("direction")
    story = pkg.typed.get("story")
    shots = pkg.typed.get("shots")
    if direction is None:
        return ["direction not loaded"]
    out: list[str] = []
    if story is None:
        out.append("Gate 2 needs a valid 01_story.json (beats and scenes)")
    if shots is None:
        out.append("Gate 2 needs a valid 04_shots.json (carrier shots)")
    if direction.vision is None:
        out.append("vision missing (tone + references)")
    if not direction.visual_rules:
        out.append("visual_rules missing (at least one rule with its why)")
    if story is None or shots is None:
        return out

    facts = {f.fact_id for f in direction.comprehension.facts}
    gens_by_scene: dict[str, list] = {}
    for g in shots.generations:
        gens_by_scene.setdefault(g.scene_id, []).append(g)

    # scenes <-> direction
    out += [f"scene {sid} has no direction" for sid in story.scenes if sid not in direction.scenes]
    out += [f"direction for unknown scene {sid}" for sid in direction.scenes if sid not in story.scenes]

    beat_ids = {b.id for a in story.structure for b in a.beats}
    for sid, d in direction.scenes.items():
        gids = {g.generation_id for g in gens_by_scene.get(sid, [])}
        for fid in d.pov.audience_knows:
            if fid not in facts:
                out.append(f"{sid}: pov.audience_knows unknown fact {fid!r}")
        for who, known in d.pov.characters_know.items():
            if who not in story.characters:
                out.append(f"{sid}: pov.characters_know unknown character {who!r}")
            out += [f"{sid}: {who} knows unknown fact {fid!r}" for fid in known if fid not in facts]
        if d.pov.whose not in story.characters:
            out.append(f"{sid}: pov.whose {d.pov.whose!r} is not a story character")
        out += [f"{sid}: curve for unknown character {who!r}" for who in d.curve if who not in story.characters]
        for e in d.emphasis:
            if e.generation_id is not None and e.generation_id not in gids:
                out.append(f"{sid}: emphasis carrier {e.generation_id!r} is not a shot of this scene")
            if e.fact_id is not None and e.fact_id not in facts:
                out.append(f"{sid}: emphasis for unknown fact {e.fact_id!r}")
        for h in d.pacing.holds:
            if h.generation_id not in gids:
                out.append(f"{sid}: hold on {h.generation_id!r}, not a shot of this scene")
        if d.jump_cause_beat is not None and d.jump_cause_beat not in beat_ids:
            out.append(f"{sid}: jump_cause_beat {d.jump_cause_beat!r} is not a beat")

    # emotional continuity between consecutive scenes (story scene order)
    order = [sid for sid in story.scenes if sid in direction.scenes]
    for prev_id, next_id in zip(order, order[1:]):
        prev, nxt = direction.scenes[prev_id], direction.scenes[next_id]
        for who, curve in nxt.curve.items():
            if who in prev.curve and abs(curve.start - prev.curve[who].end) > MAX_EMOTIONAL_JUMP \
                    and nxt.jump_cause_beat is None:
                out.append(f"emotional jump {who} {prev.curve[who].end}->{curve.start} between {prev_id} and "
                           f"{next_id} has no jump_cause_beat")

    # every reveal staged with an emphasis device
    for r in direction.reveals:
        if r.fact_id not in facts:
            out.append(f"reveal of unknown fact {r.fact_id!r}")
        elif r.scene_id not in direction.scenes:
            out.append(f"reveal {r.fact_id}: unknown scene {r.scene_id!r}")
        elif not any(e.fact_id == r.fact_id for e in direction.scenes[r.scene_id].emphasis):
            out.append(f"reveal {r.fact_id} in {r.scene_id} has no emphasis device")

    # every beat has carrier shots, and the planned coverage exists
    for beat in (b for a in story.structure for b in a.beats):
        carriers = [g for sid in beat.scene_ids for g in gens_by_scene.get(sid, [])]
        if not carriers:
            out.append(f"beat {beat.id} has no carrier shot in 04_shots")
            continue
        required = direction.coverage_plan.get(beat.id)
        if not required:
            out.append(f"beat {beat.id} has no coverage_plan")
            continue
        have = {g.coverage for g in carriers}
        out += [f"beat {beat.id}: planned {cov} but no shot of that type" for cov in required if cov not in have]
    out += [f"coverage_plan for unknown beat {b!r}" for b in direction.coverage_plan if b not in beat_ids]
    return out
