"""Offline preflight gate tests for XIANXIA60 Shot X02 First Video Calibration (Gate A).

Verifies:
1. Exact X02 ShotSpec contract and physical action invariants (White unsheath MCU).
2. White cultivator candidate image integrity, SHA-256, and identity-ingredient role (NOT start frame).
3. Deterministic PromptPlan compilation for Flow Veo 3.1 Lite Ingredients mode.
4. Editorial timing mapping: 8.0s Flow raw source -> 5.0s editorial cut (5.5s with handles).
5. Strict offline fail-closed invariants: 5/5 canonical references UNBOUND, zero provider mutation.
6. Immutability of accepted master compilation SHA256.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image
import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import ProviderCapabilities, ShotSpec, validate_contract

ROOT = Path(__file__).resolve().parents[1]
SHOTS_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "shots"
LOOK_DEV_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "look_development"
STAGING_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "assets" / "references" / "chatgpt_candidates_wave01" / "XIANXIA60_ChatGPT_Reference_Candidates_v1"
MASTER_PATH = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "XIANXIA60_COMPILATION.json"
ACCEPTED_MASTER_SHA256 = "f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b"

WHITE_CANDIDATE_FILE = STAGING_DIR / "ly_pha_van_portrait_candidate.png"
EXPECTED_WHITE_SHA256 = "7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0"
EXPECTED_WHITE_SIZE = (765, 626)


def test_x02_shotspec_contract_and_action_invariants():
    """Verify X02 ShotSpec structure, unsheath action beats, and continuity states."""
    x02_path = SHOTS_DIR / "X02.json"
    assert x02_path.exists(), "X02.json not found"

    raw = json.loads(x02_path.read_text(encoding="utf-8"))
    validate_contract("shot_spec", raw)

    shot = ShotSpec.model_validate(raw)
    assert shot.shot_id == "X02"
    assert shot.scene_id == "SC_XIANXIA60_DUEL"
    assert shot.duration_target_s == 5.0
    assert shot.editorial.handles_s == 0.25

    # Camera invariants
    assert shot.camera.framing == "MCU"
    assert shot.camera.height == "eye_level"
    assert shot.camera.movement.type == "locked"

    # Action invariants: White cultivator unsheathing straight sword facing screen-right
    assert shot.continuity.screen_direction == "left-to-right"
    assert shot.continuity.eyeline == "screen_right"

    # Continuity start state vs end state: sword starts sheathed, ends drawn at 45 degrees
    start_white = shot.continuity.start_state["white_cultivator"]
    assert start_white["sword_state"] == "sheathed"
    assert start_white["pose"] == "hand_on_sword_hilt"

    end_white = shot.continuity.end_state["white_cultivator"]
    assert end_white["sword_state"] == "drawn_cleanly"
    assert end_white["pose"] == "straight_guard_at_45_degrees"
    assert end_white["qi_state"] == "pale_azure_line_active"

    # Action beats verify scabbard draw sequence
    action_beats = shot.blocking.action_beats
    assert len(action_beats) == 3
    assert any("silver-wrapped sword hilt" in beat for beat in action_beats)
    assert any("crisp linear draw" in beat for beat in action_beats)
    assert any("pale azure qi ignites" in beat for beat in action_beats)


def test_white_cultivator_reference_candidate_identity_ingredient_integrity():
    """Verify White cultivator candidate image bytes, hash, and non-start-frame role."""
    assert WHITE_CANDIDATE_FILE.exists(), "White cultivator candidate image missing in staging"

    actual_bytes = WHITE_CANDIDATE_FILE.read_bytes()
    assert len(actual_bytes) == 692216
    actual_sha = hashlib.sha256(actual_bytes).hexdigest()
    assert actual_sha == EXPECTED_WHITE_SHA256

    with Image.open(WHITE_CANDIDATE_FILE) as img:
        assert img.size == EXPECTED_WHITE_SIZE
        assert img.mode == "RGB"

    # Check candidate ledger record
    cand_ledger_path = LOOK_DEV_DIR / "candidate_reference_ledger.json"
    assert cand_ledger_path.exists()
    cand_ledger = json.loads(cand_ledger_path.read_text(encoding="utf-8"))

    white_recs = [r for r in cand_ledger["records"] if r["asset_id"] == "CANDIDATE_CHAR_WHITE_CULTIVATOR_WAVE01_V1"]
    assert len(white_recs) == 1
    rec = white_recs[0]

    assert rec["sha256"] == EXPECTED_WHITE_SHA256
    assert rec["rights_metadata"]["binding_status"] == "UNBOUND"
    assert rec["rights_metadata"]["provider_attestation_status"] == "NOT_ATTESTED"

    # Crucial semantic invariant: Candidate image depicts sword already extended forward.
    # Therefore, it CANNOT serve as a video start/first frame for an unsheathing shot.
    # It serves ONLY as an identity and style ingredient for reference conditioning.
    limitations = rec["rights_metadata"]["technical_limitations"]
    assert any("lacks front, side profile, and full-body" in lim for lim in limitations)


def test_flow_veo_lite_ingredients_capability_and_plan_compilation():
    """Verify deterministic compilation of X02 for Flow Veo 3.1 Lite Ingredients mode."""
    x02_path = SHOTS_DIR / "X02.json"
    shot = ShotSpec.model_validate(json.loads(x02_path.read_text(encoding="utf-8")))

    flow_caps = ProviderCapabilities(
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

    plan = compile_prompt(shot, flow_caps)
    validate_contract("prompt_plan", plan.payload())

    assert plan.provider_id == "flow_veo"
    assert plan.compiler_version == "deterministic-v1"
    assert plan.input_hash == "360b968d04f35bb4aa12170ffda5f3aeac9e74897e2276ff49e8173de51f7733"

    # Image input mapped directly (supported in Ingredients mode)
    assert "image_input" in plan.mapped_controls
    assert "image_input" not in plan.unsupported_controls

    # Expected honest degradations
    assert "duration_control" in plan.unsupported_controls
    assert "multi_reference" in plan.unsupported_controls
    assert "native_audio" in plan.unsupported_controls
    assert "negative_prompt" in plan.unsupported_controls


def test_editorial_timing_mapping_8s_to_5s():
    """Verify editorial mapping of 8.0s Flow raw source to 5.0s target scene with handles."""
    x02_path = SHOTS_DIR / "X02.json"
    shot = ShotSpec.model_validate(json.loads(x02_path.read_text(encoding="utf-8")))

    flow_raw_duration_s = 8.0
    scene_target_duration_s = shot.duration_target_s  # 5.0s
    handles_s = shot.editorial.handles_s  # 0.25s
    required_headroom_s = scene_target_duration_s + (2 * handles_s)  # 5.5s

    assert flow_raw_duration_s >= required_headroom_s
    # Max trim buffer available for in-point selection
    trim_buffer_s = flow_raw_duration_s - required_headroom_s  # 2.5s
    assert trim_buffer_s == 2.5

    # Performance beats fit within the 5.0s active window
    beats = shot.performance_spec.beats
    assert beats[0].label == "grip_tighten" and beats[0].approx_start_s == 0.5
    assert beats[1].label == "blade_draw" and beats[1].approx_start_s == 1.5
    assert beats[2].label == "guard_lock" and beats[2].approx_start_s == 3.2
    assert max(b.approx_start_s for b in beats) < scene_target_duration_s


def test_fail_closed_zero_mutation_invariants():
    """Verify that canonical reference ledger remains 5/5 UNBOUND and master is immutable."""
    canon_ledger_path = LOOK_DEV_DIR / "reference_asset_ledger.json"
    canon_data = json.loads(canon_ledger_path.read_text(encoding="utf-8"))

    assert canon_data["unbound_references_count"] == 5
    assert canon_data["bound_references_count"] == 0
    for rec in canon_data["records"]:
        assert rec["uri_or_path"].startswith("UNBOUND:")
        assert rec["sha256"] is None
        assert rec["provider_asset_id"] is None

    # Master compilation must remain untouched
    actual_master_sha = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
    assert actual_master_sha == ACCEPTED_MASTER_SHA256
