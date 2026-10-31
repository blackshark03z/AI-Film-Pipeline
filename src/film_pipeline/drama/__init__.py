"""Drama pre-production (2026-10-31 P0 backlog).

script (Fountain) -> feasibility (Gate 1) -> bible refs -> axis book ->
coverage / 15 s scene unit -> storyboard (Gate 2) -> scene prompt ->
preflight (Gate 3). Nothing here talks to a provider.
"""
from .axis import AxisBook, ShotAxisRecord, axis_record, check_axis
from .bible import (
    CharacterReferenceSet,
    ReferenceImage,
    attachment_plan,
    hash_file,
    reference_strategy_for,
    register_reference,
)
from .coverage import CoveragePlanner, CoverageShot, SceneTiming, SceneUnit
from .feasibility import (
    FeasibilityIssue,
    FeasibilityLimits,
    FeasibilityReport,
    check_scene,
    check_script,
)
from .preflight import PreflightLimits, PreflightReport, preflight_scene
from .prompt import CharacterBrief, ScenePromptPlan, compile_scene_prompt
from .script import (
    Script,
    ScriptElement,
    ScriptScene,
    count_vi_syllables,
    parse_fountain,
)
from .storyboard import StoryboardGate, render_schematic_frame

__all__ = [
    "AxisBook", "ShotAxisRecord", "axis_record", "check_axis",
    "CharacterReferenceSet", "ReferenceImage", "attachment_plan",
    "hash_file", "reference_strategy_for", "register_reference",
    "CoveragePlanner", "CoverageShot", "SceneTiming", "SceneUnit",
    "FeasibilityIssue", "FeasibilityLimits", "FeasibilityReport",
    "check_scene", "check_script",
    "PreflightLimits", "PreflightReport", "preflight_scene",
    "CharacterBrief", "ScenePromptPlan", "compile_scene_prompt",
    "Script", "ScriptElement", "ScriptScene", "count_vi_syllables",
    "parse_fountain",
    "StoryboardGate", "render_schematic_frame",
]
