"""Gate 3 — fail-closed preflight before a drama scene is sent to Dola.

Aggregates the P0 checks; any BLOCK means the scene is not dispatched.
Rules come from the 2026-10-31 handoff (section 5); ``(*)`` limits are
assumptions to re-measure on the first test scene.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .bible import CharacterReferenceSet
from .coverage import SceneTiming, SceneUnit
from .feasibility import FeasibilityLimits, check_scene
from .prompt import SECTION_ORDER, ScenePromptPlan
from .script import ScriptScene
from .storyboard import StoryboardGate

# scene state carried across the cut between two scenes
CONTINUITY_KEYS = ("positions", "props", "lighting", "time_of_day")


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
                    previous_end_state: dict | None = None,
                    start_state: dict | None = None,
                    limits: PreflightLimits | None = None
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
    # every character in frame needs an approved, hash-verified reference
    by_name = {r.name: r for r in reference_sets}
    in_frame = {c for s in unit.shots for c in s.axis.visible}
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
    return report
