"""Focused test suite for S3 XIANXIA60 pre-production compilation.

Validates the full Film Core chain on real XIANXIA60 data:
NarrativeCompiler -> StoryGraph -> DirectorCompiler/ShotGraph ->
ShotSpec (X01-X12) -> Prompt Compiler (compile_prompt) ->
EditManifest (make_edit_manifest).

Deterministic; offline; 0 provider network actions, $0 paid.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.compiler import BLOCK_ORDER, compile_prompt
from film_pipeline.core import (
    PromptPlan, ProviderCapabilities, ShotSpec, canonical_json, load_shot,
    sha256, validate_contract,
)
from film_pipeline.editorial import EditClip, EditManifest, make_edit_manifest
from build_xianxia60_compilation import (
    CAST, PROSE, SHOTS_RAW, WORLD_INITIAL, build_compilation,
)

PROJECT_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van"
SHOTS_DIR = PROJECT_DIR / "shots"
PROMPTS_DIR = PROJECT_DIR / "prompts"
EDITORIAL_DIR = PROJECT_DIR / "editorial"
STORYBOARD_DIR = PROJECT_DIR / "storyboard"
COMPILATION_FILE = PROJECT_DIR / "XIANXIA60_COMPILATION.json"


@pytest.fixture(scope="module")
def compilation_data():
    """Ensure compilation has run and return loaded master JSON."""
    if not COMPILATION_FILE.is_file():
        rc = build_compilation()
        assert rc == 0
    data = json.loads(COMPILATION_FILE.read_text(encoding="utf-8"))
    return data


def test_xianxia60_compilation_executes_and_yields_valid_master(compilation_data):
    """Verify master compilation output existence, version, and metadata."""
    assert compilation_data["version"] == "xianxia60-compilation-v1"
    meta = compilation_data["metadata"]
    assert meta["film_title"] == "Nhất Kiếm Phá Vân"
    assert meta["shot_count"] == 12
    assert meta["target_runtime_s"] == 60.0
    assert "White Cultivator" in meta["characters"][0]
    assert "Black Cultivator" in meta["characters"][1]


def test_xianxia60_narrative_and_director_beat_structure(compilation_data):
    """Verify 12 events, 12 beats, 12 director intents, and typed functions."""
    events = compilation_data["narrative"]["events"]
    beats = compilation_data["narrative"]["beats"]
    shot_nodes = compilation_data["shot_graph"]["nodes"]

    assert len(events) == 12
    assert len(beats) == 12
    assert len(shot_nodes) == 12

    expected_functions = [
        "ESTABLISH", "DECISION", "APPROACH", "DISCOVER",
        "REACTION", "PRESSURE", "DISCOVER", "DECISION",
        "PRESSURE", "PAYOFF", "AFTERMATH", "RESOLVE"
    ]
    actual_event_functions = [e["function"] for e in events]
    assert actual_event_functions == expected_functions

    # Rhythm check: no two consecutive beats share the exact same function
    for i in range(len(beats) - 1):
        assert beats[i]["function"] != beats[i + 1]["function"], (
            f"Consecutive beat function collision at beats {i} and {i+1}: {beats[i]['function']}"
        )


def test_xianxia60_character_bibles_and_fingerprints(compilation_data):
    """Verify CharacterBibles, identity fingerprints, and hard constraints."""
    bibles = compilation_data["character_bibles"]
    white = bibles["white_cultivator"]
    black = bibles["black_cultivator"]

    assert white["age_band"] == "early 20s"
    assert "white Daoist martial robes" in white["signature_wardrobe"]
    assert black["age_band"] == "late 20s"
    assert "charcoal-black martial robes" in black["signature_wardrobe"]

    # Fingerprints must be non-empty and mutually distinct
    from film_pipeline.narrative import CharacterBible
    wb = CharacterBible(**white)
    bb = CharacterBible(**black)
    assert wb.identity_fingerprint() == "edb2d2d99cd0fae0"
    assert bb.identity_fingerprint() == "451172ec254174f6"
    assert wb.identity_fingerprint() != bb.identity_fingerprint()


def test_xianxia60_world_state_and_transitions(compilation_data):
    """Verify WorldStateGraph transitions are justified by story events."""
    world_manifest = compilation_data["world_state_graph"]
    states = world_manifest["states"]
    transitions = world_manifest["transitions"]

    assert len(states) == 13  # shot_00 initial + 12 shots
    assert len(transitions) == 12

    # Every transition must have a justified story event
    for t in transitions:
        assert t["justified_by_event"].startswith("ev_")


def test_xianxia60_all_12_shotspecs_schema_and_model_valid():
    """Verify all 12 individual ShotSpec files pass JSON schema and Pydantic validation."""
    shot_files = sorted(SHOTS_DIR.glob("X*.json"))
    assert len(shot_files) == 12

    total_duration = 0.0
    for path in shot_files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_contract("shot_spec", raw)

        shot = load_shot(path)
        assert shot.schema_version == "1.0.0"
        assert shot.spec_version == 1
        assert shot.scene_id == "SC_XIANXIA60_DUEL"
        assert shot.duration_target_s == 5.0
        assert len(shot.characters) == 2
        assert shot.environment is not None
        assert shot.camera is not None
        assert shot.blocking is not None
        assert shot.continuity is not None
        assert shot.performance_spec is not None
        assert shot.action_intent is not None

        # Verify performance_spec biomechanics
        assert len(shot.performance_spec.primary_action) > 0
        assert shot.performance_spec.motion_energy in ("low", "moderate", "high")
        assert shot.performance_spec.motion_risk_class in ("LOW", "MEDIUM", "HIGH", "EXTREME")

        # Verify action_intent dramatic causality
        assert len(shot.action_intent.character_goal) > 0
        assert len(shot.action_intent.chosen_action) > 0

        total_duration += shot.duration_target_s

    assert total_duration == 60.0


def test_xianxia60_all_12_promptplans_schema_and_degradation():
    """Verify all 12 PromptPlans validate against schema and reflect provider capability degradation."""
    plan_files = sorted(PROMPTS_DIR.glob("X*_plan.json"))
    assert len(plan_files) == 12

    for path in plan_files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_contract("prompt_plan", raw)

        plan = PromptPlan.model_validate(raw)
        assert plan.compiler_version == "deterministic-v1"
        assert plan.provider_id == "seedance_v2_planning"

        # Check all 10 canonical blocks
        assert list(plan.canonical_blocks.keys()) == list(BLOCK_ORDER)

        # Check honest capability degradation on limited profile
        assert "duration_control" in plan.unsupported_controls
        assert "native_audio" in plan.unsupported_controls
        assert "negative_prompt" in plan.unsupported_controls
        assert len(plan.degraded_controls) == len(plan.unsupported_controls)
        assert len(plan.warnings) == len(plan.unsupported_controls)

        # Textual fallbacks must contain the underlying intent
        assert "duration_control" in plan.mapped_controls["text_fallbacks"]
        assert "no modern clothing" in plan.provider_prompt


def test_xianxia60_edit_manifest_schema_and_timeline():
    """Verify EditManifest validates against schema and produces a 60.0s timeline."""
    manifest_file = EDITORIAL_DIR / "edit_manifest.json"
    assert manifest_file.is_file()

    raw = json.loads(manifest_file.read_text(encoding="utf-8"))
    validate_contract("edit_manifest", raw)

    manifest = EditManifest.model_validate(raw)
    assert manifest.project_id == "xianxia60_nhat_kiem_pha_van"
    assert len(manifest.clips) == 12

    # Verify contiguous 1..12 clip order
    orders = [c.order for c in manifest.clips]
    assert orders == list(range(1, 13))

    # Verify timeline calculation
    timeline_s = sum(c.target_duration_s for c in manifest.clips)
    assert timeline_s == 60.0

    # Verify all clips are planning placeholders
    for clip in manifest.clips:
        assert clip.selected_take_id.startswith("take_placeholder_")
        assert clip.asset_id.startswith("asset_placeholder_")
        assert "PRE-PRODUCTION PLANNING PLACEHOLDER" in (clip.notes or "")


def test_xianxia60_spatial_continuity_180_degree_axis(compilation_data):
    """Verify strict preservation of the 180-degree South camera axis."""
    shots = compilation_data["shot_specs"]

    # X01 to X07: White on screen-left, Black on screen-right
    for sid in ["X01", "X02", "X03", "X04", "X05", "X06", "X07"]:
        shot = shots[sid]
        invariants = " ".join(shot["continuity"]["critical_invariants"])
        assert "screen-left" in invariants.lower() or "screen_left" in invariants.lower() or "left" in shot["continuity"]["screen_direction"]

    # X08: The aerial leap that inverts tactical positions
    x08 = shots["X08"]
    assert x08["blocking"]["start"].startswith("White cultivator kicks off") or "leaping" in x08["dramatic_purpose"].lower() or "leap" in x08["dramatic_purpose"].lower()
    assert "right" in " ".join(x08["continuity"]["critical_invariants"]).lower()

    # X10: The decisive strike where White (now on right) thrusts leftward
    x10 = shots["X10"]
    assert "right" in " ".join(x10["continuity"]["critical_invariants"]).lower()


def test_xianxia60_end_to_end_lineage_traceability(compilation_data):
    """Verify unbroken lineage: Beat -> ShotGraphNode -> ShotSpec hash -> PromptPlan -> EditManifest."""
    lineage = compilation_data["lineage_traceability"]
    assert len(lineage) == 12

    for i in range(1, 13):
        sid = f"X{i:02d}"
        node_id = f"S{i:02d}"
        beat_id = f"beat_{i:02d}"

        entry = lineage[sid]
        assert entry["beat_id"] == beat_id
        assert entry["shot_graph_node"] == node_id
        assert entry["edit_clip_order"] == i
        assert len(entry["shot_spec_hash"]) == 64
        assert len(entry["prompt_input_hash"]) == 64
        assert entry["duration_s"] == 5.0


def test_xianxia60_preproduction_bounds_enforced(compilation_data):
    """Verify pre-production safety bounds: 0 provider releases, 0 cost, explicit pending lock."""
    system_status = compilation_data["system_status"]
    assert system_status["film_core_technical_pass"] is True
    assert system_status["provider_generate_authorized"] is False
    assert system_status["owner_creative_lock"] == "PENDING_INDEPENDENT_PROVE_AND_OWNER_REVIEW"

    budget = compilation_data["provider_budget_proposal"]
    assert budget["financial_state_at_WP"] == "0 NEW PROVIDER ACTIONS / $0 PAID"
    assert budget["proposed_wave_1_scope"]["cost_ceiling_usd"] == 0.0
    assert budget["proposed_wave_1_scope"]["candidate_shots"] == ["X04", "X08", "X10"]
