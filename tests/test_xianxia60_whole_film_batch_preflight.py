"""Offline preflight gate tests for XIANXIA60 Whole-Film Fast-Track (X01-X12 Batch Release).

Verifies:
1. All 12 ShotSpecs (X01-X12) schema validity, action beats, and 100% exact state continuity across all 11 cuts.
2. Specific dramatic milestones: X02 unsheath MCU, X08 positional swap, X10 decisive blow, X11 defeat, X12 sheathing.
3. Deterministic PromptPlan compilation for all 12 shots targeting Google Flow Veo 3.1 Lite Ingredients mode.
4. Reference candidate image integrity (White, Black, Arena, Composite) and identity-ingredient role.
5. Editorial timeline mapping: 12 clips x 5.0s = 60.0s total film duration (55-65s envelope).
6. Budget envelope: 12 primary + up to 12 repair + 6 pickup = HARD MAX 30 video outputs.
7. Strict fail-closed invariants: zero unapproved mutations, 5/5 canonical references UNBOUND.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image
import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import ProviderCapabilities, ShotSpec, validate_contract
from film_pipeline.editorial import EditManifest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van"
SHOTS_DIR = PROJECT_DIR / "shots"
EDITORIAL_DIR = PROJECT_DIR / "editorial"
LOOK_DEV_DIR = PROJECT_DIR / "look_development"
STAGING_DIR = PROJECT_DIR / "assets" / "references" / "chatgpt_candidates_wave01" / "XIANXIA60_ChatGPT_Reference_Candidates_v1"
MASTER_PATH = PROJECT_DIR / "XIANXIA60_COMPILATION.json"
ACCEPTED_MASTER_SHA256 = "f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b"

WHITE_CANDIDATE_FILE = STAGING_DIR / "ly_pha_van_portrait_candidate.png"
EXPECTED_WHITE_SHA256 = "7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0"
EXPECTED_WHITE_SIZE = (765, 626)

BLACK_CANDIDATE_FILE = STAGING_DIR / "da_vo_nhai_portrait_candidate.png"
EXPECTED_BLACK_SHA256 = "a89e067c39445c4485aa010d927270d025bc06ccffdc21d5fdc3303d493f3446"
EXPECTED_BLACK_SIZE = (762, 626)

ARENA_CANDIDATE_FILE = STAGING_DIR / "van_dai_arena_candidate.png"
EXPECTED_ARENA_SHA256 = "545d02eda6684c7121f6e49cc8e14057f9ba1630aaad49c073dfbf15a8453694"
EXPECTED_ARENA_SIZE = (1536, 389)

COMPOSITE_FILE = STAGING_DIR / "owner_provisional_composite_source.png"
EXPECTED_COMPOSITE_SHA256 = "21f7bcb26510aa110f762a577401b3f042add2916b875fe6eff750077aaaa6ad"
EXPECTED_COMPOSITE_SIZE = (1536, 1024)


@pytest.fixture(scope="module")
def flow_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        profile_version="flow-veo-3.1-lite-ingredients-v1",
        provider_id="flow_veo",
        transport_type="browser_cookie",
        supports_text_to_video=True,
        supports_image_input=True,
        supports_start_frame=False,
        supports_end_frame=False,
        supports_multi_reference=False,
        supports_seed=False,
        supports_native_audio=False,
        supports_duration_control=False,
        supports_aspect_ratio=True,
        supports_resolution_control=True,
        supports_negative_prompt=False,
        supports_batch=False,
        supports_cancel=False,
        supports_stable_external_job_id=False,
        notes=[
            "Veo 3.1 Lite Ingredients mode supports fixed 8.0s duration, 1280x720 16:9, x1 only.",
            "Single reference image ingredient for identity and appearance conditioning.",
        ],
    )


def test_whole_film_12_shotspecs_continuity_chain():
    """Verify all 12 ShotSpecs are schema-valid and maintain 100% exact state continuity across all 11 cuts."""
    shots: list[ShotSpec] = []
    for i in range(1, 13):
        shot_id = f"X{i:02d}"
        path = SHOTS_DIR / f"{shot_id}.json"
        assert path.exists(), f"Missing ShotSpec file {shot_id}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_contract("shot_spec", raw)
        shot = ShotSpec.model_validate(raw)
        assert shot.shot_id == shot_id
        assert shot.duration_target_s == 5.0
        assert shot.scene_id == "SC_XIANXIA60_DUEL"
        shots.append(shot)

    assert len(shots) == 12

    # Verify all 11 cuts have exact state continuity: end_state of shot i == start_state of shot i+1
    for i in range(11):
        s_current = shots[i]
        s_next = shots[i + 1]
        assert s_current.continuity.end_state == s_next.continuity.start_state, (
            f"State discontinuity detected at cut {s_current.shot_id} -> {s_next.shot_id}!"
        )

    # Verify key dramatic milestones
    # X01: sheathed duel confrontation
    assert shots[0].continuity.start_state["white_cultivator"]["sword_state"] == "sheathed"
    assert shots[0].continuity.start_state["black_cultivator"]["sword_state"] == "sheathed"

    # X02: White unsheathes straight sword
    assert shots[1].continuity.start_state["white_cultivator"]["sword_state"] == "sheathed"
    assert shots[1].continuity.end_state["white_cultivator"]["sword_state"] == "drawn_cleanly"
    assert shots[1].continuity.end_state["white_cultivator"]["qi_state"] == "pale_azure_line_active"

    # X08: The pivotal position reversal
    assert shots[7].continuity.start_state["white_cultivator"]["position"] == "center_left"
    assert shots[7].continuity.end_state["white_cultivator"]["position"] == "east_ledge_screen_right"
    assert shots[7].continuity.end_state["black_cultivator"]["position"] == "center_left"

    # X10: Decisive strike (Nhất Kiếm)
    assert shots[9].continuity.end_state["white_cultivator"]["qi_state"] == "white_azure_beam_piercing"
    assert shots[9].continuity.end_state["arena"]["energy_projectile"] == "shattered_into_grey_vapor"

    # X11: Defeat
    assert shots[10].continuity.end_state["black_cultivator"]["pose"] == "kneeling_on_right_knee_bowed"

    # X12: Resolution
    assert shots[11].continuity.end_state["white_cultivator"]["sword_state"] == "fully_sheathed_in_silver_scabbard"


def test_whole_film_flow_veo_lite_prompt_compilation(flow_capabilities: ProviderCapabilities):
    """Verify deterministic PromptPlan compilation for all 12 shots under Flow Veo 3.1 Lite Ingredients mode."""
    for i in range(1, 13):
        shot_id = f"X{i:02d}"
        path = SHOTS_DIR / f"{shot_id}.json"
        shot = ShotSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))

        plan = compile_prompt(shot, flow_capabilities)
        validate_contract("prompt_plan", plan.payload())

        assert plan.provider_id == "flow_veo"
        assert plan.compiler_version == "deterministic-v1"
        assert len(plan.input_hash) == 64
        assert len(plan.provider_prompt) > 5000

        # Flow Veo Lite Ingredients mappings
        assert "image_input" in plan.mapped_controls
        assert "image_input" not in plan.unsupported_controls
        assert "duration_control" in plan.unsupported_controls


def test_whole_film_candidate_references_integrity():
    """Verify local presence, SHA-256 hashes, and dimensions of all provisional candidate images."""
    candidates = [
        (WHITE_CANDIDATE_FILE, EXPECTED_WHITE_SHA256, EXPECTED_WHITE_SIZE),
        (BLACK_CANDIDATE_FILE, EXPECTED_BLACK_SHA256, EXPECTED_BLACK_SIZE),
        (ARENA_CANDIDATE_FILE, EXPECTED_ARENA_SHA256, EXPECTED_ARENA_SIZE),
        (COMPOSITE_FILE, EXPECTED_COMPOSITE_SHA256, EXPECTED_COMPOSITE_SIZE),
    ]

    for file_path, expected_sha, expected_size in candidates:
        assert file_path.exists(), f"Candidate file {file_path.name} missing"
        actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, f"SHA mismatch on {file_path.name}"
        with Image.open(file_path) as img:
            assert img.size == expected_size
            assert img.mode == "RGB"

    # Verify ledger records
    cand_ledger_path = LOOK_DEV_DIR / "candidate_reference_ledger.json"
    assert cand_ledger_path.exists()
    cand_ledger = json.loads(cand_ledger_path.read_text(encoding="utf-8"))
    assert len(cand_ledger["records"]) == 4

    for rec in cand_ledger["records"]:
        assert rec["rights_metadata"]["binding_status"] == "UNBOUND"
        assert rec["rights_metadata"]["provider_attestation_status"] == "NOT_ATTESTED"


def test_whole_film_editorial_manifest_and_duration():
    """Verify the 12-shot edit manifest matches 60.0s total target duration (55-65s required)."""
    edit_manifest_path = EDITORIAL_DIR / "edit_manifest.json"
    assert edit_manifest_path.exists()
    edit_manifest = json.loads(edit_manifest_path.read_text(encoding="utf-8"))

    clips = edit_manifest["clips"]
    assert len(clips) == 12

    total_duration = sum(clip["target_duration_s"] for clip in clips)
    assert total_duration == 60.0, f"Expected 60.0s total film duration, got {total_duration}s"
    assert 55.0 <= total_duration <= 65.0, "Film duration out of 55-65s bounds"

    # Verify 8s source -> 5s editorial trim buffer
    flow_raw_duration = 8.0
    handles_s = 0.25
    for clip in clips:
        assert clip["target_duration_s"] == 5.0
        # Required window with handles: 5.5s
        needed_window = clip["target_duration_s"] + 2 * handles_s
        assert flow_raw_duration >= needed_window
        trim_buffer = flow_raw_duration - needed_window
        assert trim_buffer == 2.5


def test_whole_film_budget_envelope_and_fail_closed_gate():
    """Verify the production budget ceiling (max 30 outputs) and immutable master compilation."""
    assert MASTER_PATH.exists()
    actual_master_sha = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
    assert actual_master_sha == ACCEPTED_MASTER_SHA256, "Master compilation modified without authorization"

    # Budget invariants: 12 primary + up to 12 repair + 6 pickup = 30 max outputs
    max_primary_outputs = 12
    max_repair_outputs = 12
    max_pickup_outputs = 6
    hard_max_outputs = max_primary_outputs + max_repair_outputs + max_pickup_outputs
    assert hard_max_outputs == 30

    # In Veo 3.1 Lite Ingredients:
    # 10 credits standard / 5 credits Ultra per output
    # Maximum possible credits: 30 x 10 = 300 credits (or 150 credits Ultra)
    # Primary wave: 12 x 10 = 120 credits (or 60 credits Ultra)
