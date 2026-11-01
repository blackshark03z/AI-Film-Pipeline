"""Gate 3 — fail-closed preflight before a drama scene is sent to Dola.

Aggregates the P0 checks; any BLOCK means the scene is not dispatched.
Rules come from the 2026-10-31 handoff (section 5); ``(*)`` limits are
assumptions to re-measure on the first test scene.

``reference_mode="TEXT_ONLY"`` is the no-reference route (a provider that
blocks reference faces): reference checks are skipped, and every character
in frame must instead carry an approved ``CharacterLook`` whose text is in
the prompt. ``generation_index`` > 1 requires a ``GenerationHandoff`` from
the previous generation of the same scene.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .bible import CharacterLook, CharacterReferenceSet
from .continuity import ContinuityState, GenerationHandoff
from .coverage import SceneTiming, SceneUnit
from .choreography import GenerationChoreography
from .feasibility import (FeasibilityLimits, check_cross_cut, check_repetition,
                          check_scene)
from .prompt import SECTION_ORDER, ScenePromptPlan
from .scene_bible import (LocationLook, SceneOccupancy,
                          check_environment)
from .script import ScriptScene
from .storyboard import StoryboardGate

# scene state carried across the cut between two scenes
CONTINUITY_KEYS = ("positions", "props", "looks", "lighting", "time_of_day")


class PreflightLimits(ContractModel):
    max_prompt_words: int = 120          # (*)
    timing: SceneTiming = Field(default_factory=SceneTiming)
    feasibility: FeasibilityLimits = Field(default_factory=FeasibilityLimits)


class PreflightIssue(ContractModel):
    check: str
    severity: Literal["BLOCK", "WARN"]
    detail: str


class PreflightReport(ContractModel):
    scene_id: str
    issues: list[PreflightIssue] = Field(default_factory=list)

    @property
    def verdict(self) -> Literal["PASS", "BLOCKED"]:
        return "BLOCKED" if any(i.severity == "BLOCK"
                                for i in self.issues) else "PASS"


def preflight_scene(*, scene: ScriptScene, unit: SceneUnit,
                    prompt: ScenePromptPlan,
                    reference_sets: list[CharacterReferenceSet],
                    reference_root: Path,
                    storyboard: StoryboardGate,
                    known_characters: list[str],
                    previous_end_state: dict | ContinuityState | None = None,
                    start_state: dict | ContinuityState | None = None,
                    limits: PreflightLimits | None = None,
                    reference_mode: Literal["IMAGE", "TEXT_ONLY"] = "IMAGE",
                    looks: list[CharacterLook] | None = None,
                    generation_index: int = 1,
                    handoff: GenerationHandoff | None = None,
                    location: LocationLook | None = None,
                    occupancy: SceneOccupancy | None = None,
                    choreography: GenerationChoreography | None = None
                    ) -> PreflightReport:
    limits = limits or PreflightLimits()
    report = PreflightReport(scene_id=scene.scene_id)

    def add(check: str, detail: str, severity: str = "BLOCK") -> None:
        report.issues.append(PreflightIssue(check=check, detail=detail,
                                            severity=severity))  # type: ignore[arg-type]

    if unit.scene_id != scene.scene_id or prompt.scene_id != scene.scene_id:
        add("SCENE_MISMATCH", "script scene, scene unit and prompt disagree")
    issues, _ = check_scene(scene, known_characters=known_characters,
                            limits=limits.feasibility)
    for issue in issues:
        add(f"FEASIBILITY:{issue.rule}", issue.detail, issue.severity)
    for problem in unit.axis_problems():
        add("AXIS", problem)
    for problem in unit.timing_problems(limits.timing):
        add("TIMING", problem)
    by_name = {r.name: r for r in reference_sets}
    in_frame = {c for s in unit.shots for c in s.axis.visible}
    if reference_mode == "IMAGE":
        # every character in frame needs an approved, hash-verified reference
        for name in sorted(in_frame):
            ref_set = by_name.get(name)
            if ref_set is None:
                add("REFERENCE", f"{name}: no reference set")
                continue
            for problem in ref_set.problems(reference_root):
                add("REFERENCE", problem)
        attached = {a["character"] for a in prompt.reference_attachments}
        for name in sorted(in_frame - attached):
            add("REFERENCE", f"{name}: reference not attached to the prompt")
    elif prompt.reference_attachments:
        add("REFERENCE", "TEXT_ONLY route but the prompt attaches references")
    # locked looks: required on the text-only route, checked when given.
    # A character named by the start state is described to the model even
    # when the storyboard keeps them out of frame, so they need a look too
    # (film01 SC03_g2: an unnamed officer replaced DOYLE).
    look_by_name = {lk.character: lk for lk in looks or []}
    stated = set()
    if isinstance(start_state, ContinuityState):
        stated = set(start_state.positions) | set(start_state.looks)
    elif isinstance(start_state, dict):
        stated = set(start_state.get("positions") or {}) | \
            set(start_state.get("looks") or {})
    if looks is not None or reference_mode == "TEXT_ONLY":
        cast_text = prompt.sections.get("characters", "")
        for name in sorted(in_frame | stated):
            look = look_by_name.get(name)
            if look is None:
                add("LOOK", f"{name}: no locked look")
                continue
            for problem in look.problems():
                add("LOOK", problem)
            if look.text not in cast_text:
                add("LOOK", f"{name}: prompt does not carry the locked look "
                            f"text for {look.look_id}")
            ref_set = by_name.get(name)
            if reference_mode == "IMAGE" and ref_set is not None and                     ref_set.look_id != look.look_id:
                add("LOOK", f"{name}: reference shows {ref_set.look_id}, "
                            f"look is {look.look_id}")
    if location is not None:
        setting_text = prompt.sections.get("setting", "")
        for problem in location.problems():
            add("LOCATION", problem)
        if location.text not in setting_text:
            add("LOCATION", f"prompt does not carry the locked location "
                            f"text for {location.look_id}")
        for issue in check_environment(scene, location, [setting_text]):
            add(issue.check, issue.detail, issue.severity)
        if isinstance(start_state, ContinuityState) and                 start_state.location and                 start_state.location != location.look_id:
            add("LOCATION", f"start state is at {start_state.location!r}, "
                            f"location is {location.look_id}")
    if occupancy is not None:
        here = occupancy.present_at(generation_index)
        named = set(in_frame) | stated
        for name in sorted(named - here):
            where = "in frame" if name in in_frame else "named"
            add("OCCUPANCY", f"{name} is {where} but not present in the "
                             f"scene at generation {generation_index}")
        for problem in occupancy.problems():
            add("OCCUPANCY", problem)
    if choreography is not None:
        for issue in choreography.problems(unit.duration_s):
            add(issue.check, issue.detail, issue.severity)
        loop_text = " ".join([prompt.sections.get("shots", ""),
                              prompt.sections.get("setting", "")])
        for issue in check_repetition(loop_text, scene.scene_id):
            add(f"FEASIBILITY:{issue.rule}", issue.detail, issue.severity)
        for cue in choreography.performance:
            if cue.character not in known_characters:
                add("PERFORMANCE", f"{cue.character}: unknown character")
    for problem in storyboard.problems([unit]):
        add("STORYBOARD", problem)
    if prompt.word_count > limits.max_prompt_words:
        add("PROMPT_LENGTH", f"{prompt.word_count} words > "
                             f"{limits.max_prompt_words}")
    present = [k for k in SECTION_ORDER if prompt.sections.get(k)]
    if list(prompt.sections) != list(SECTION_ORDER):
        add("PROMPT_ORDER", f"sections {list(prompt.sections)} not in "
                            f"order {list(SECTION_ORDER)}")
    for required in ("characters", "setting", "shots", "prohibitions"):
        if required not in present:
            add("PROMPT_SECTION", f"empty section: {required}")
    if generation_index > 1 and handoff is None and             previous_end_state is None:
        add("STATE", f"generation {generation_index} has no handoff from "
                     "the previous generation")
    if handoff is not None:
        previous_end_state = handoff.previous_end
        for issue in check_cross_cut(
                scene_id=scene.scene_id,
                previous_action=handoff.previous_action,
                previous_start=handoff.previous_start,
                previous_end=handoff.previous_end,
                end_state_verified=handoff.end_state_verified):
            add(f"FEASIBILITY:{issue.rule}", issue.detail, issue.severity)
    if isinstance(previous_end_state, ContinuityState):
        previous_end_state = previous_end_state.as_dict()
    if isinstance(start_state, ContinuityState):
        if start_state.describe() and not prompt.sections.get("continuity"):
            add("STATE", "start state is not compiled into the prompt")
        start_state = start_state.as_dict()
    if previous_end_state is not None:
        if start_state is None:
            add("STATE", "previous scene declares an end state; this scene "
                         "declares no start state")
        else:
            for key in CONTINUITY_KEYS:
                if previous_end_state.get(key) != start_state.get(key):
                    add("STATE", f"{key}: previous end "
                                 f"{previous_end_state.get(key)!r} != start "
                                 f"{start_state.get(key)!r}")
            # location compared apart: dict states may omit the key
            if (previous_end_state.get("location") or "") !=                     (start_state.get("location") or ""):
                add("STATE", f"location: previous end "
                             f"{previous_end_state.get('location')!r} != "
                             f"start {start_state.get('location')!r}")
    return report
