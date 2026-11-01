"""Drama pre-production (2026-10-31 P0 backlog).

script (Fountain) -> feasibility (Gate 1) -> bible refs -> axis book ->
coverage / 15 s scene unit -> storyboard (Gate 2) -> scene prompt ->
preflight (Gate 3) -> post-render handoff QC between generations.
Nothing here talks to a provider.
"""
from .axis import AxisBook, ShotAxisRecord, axis_record, check_axis
from .bible import (
    CharacterLook,
    CharacterReferenceSet,
    ReferenceImage,
    attachment_plan,
    hash_file,
    reference_strategy_for,
    register_reference,
)
from .continuity import ContinuityState, GenerationHandoff
from .coverage import CoveragePlanner, CoverageShot, SceneTiming, SceneUnit
from .feasibility import (
    FeasibilityIssue,
    FeasibilityLimits,
    FeasibilityReport,
    check_cross_cut,
    check_scene,
    check_script,
)
from .generation import GenerationPlan, GenerationSpec, split_unit
from .preflight import PreflightLimits, PreflightReport, preflight_scene
from .post import (
    PostManifest,
    SubtitleCue,
    assemble,
    clamp_cues,
    cue_offsets,
    normalize_loudness,
    write_srt,
)
from .prompt import CharacterBrief, ScenePromptPlan, compile_scene_prompt
from .qc import (
    HandoffCheck,
    HandoffQC,
    character_sheet,
    extract_frame,
    handoff_sheet,
)
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
    "CharacterLook", "CharacterReferenceSet", "ReferenceImage",
    "attachment_plan",
    "hash_file", "reference_strategy_for", "register_reference",
    "ContinuityState", "GenerationHandoff",
    "CoveragePlanner", "CoverageShot", "SceneTiming", "SceneUnit",
    "FeasibilityIssue", "FeasibilityLimits", "FeasibilityReport",
    "check_cross_cut", "check_scene", "check_script",
    "GenerationPlan", "GenerationSpec", "split_unit",
    "PreflightLimits", "PreflightReport", "preflight_scene",
    "PostManifest", "SubtitleCue", "assemble", "clamp_cues", "cue_offsets",
    "normalize_loudness", "write_srt",
    "CharacterBrief", "ScenePromptPlan", "compile_scene_prompt",
    "HandoffCheck", "HandoffQC", "character_sheet", "extract_frame",
    "handoff_sheet",
    "Script", "ScriptElement", "ScriptScene", "count_vi_syllables",
    "parse_fountain",
    "StoryboardGate", "render_schematic_frame",
]
