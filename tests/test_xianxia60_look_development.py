"""Focused tests for XIANXIA60 Look Development and Reference Preflight.

Verifies:
1. CharacterV1 schema compliance for White Cultivator & Black Cultivator
2. Location specification & spatial axis rules for Van Dai Terrace
3. Visual style bible, color palette, weapon dimensions, and optics
4. Concept schematics mandatory warning labels
5. Reference asset ledger schema compliance and fail-closed unbound enforcement
6. Full cross-layer congruence across all 12 ShotSpecs (X01-X12)
7. Immutability of accepted master compilation SHA256
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from film_pipeline.core import validate_contract

ROOT = Path(__file__).resolve().parents[1]
LOOK_DEV_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "look_development"
SHOTS_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "shots"
MASTER_COMPILATION_PATH = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "XIANXIA60_COMPILATION.json"
ACCEPTED_MASTER_SHA256 = "f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b"


@pytest.fixture(scope="module")
def white_cultivator_data() -> dict:
    path = LOOK_DEV_DIR / "character_white_cultivator.json"
    assert path.exists(), "character_white_cultivator.json not found"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def black_cultivator_data() -> dict:
    path = LOOK_DEV_DIR / "character_black_cultivator.json"
    assert path.exists(), "character_black_cultivator.json not found"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def location_data() -> dict:
    path = LOOK_DEV_DIR / "location_van_dai_terrace.json"
    assert path.exists(), "location_van_dai_terrace.json not found"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def style_bible_data() -> dict:
    path = LOOK_DEV_DIR / "visual_style_bible.json"
    assert path.exists(), "visual_style_bible.json not found"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ledger_data() -> dict:
    path = LOOK_DEV_DIR / "reference_asset_ledger.json"
    assert path.exists(), "reference_asset_ledger.json not found"
    return json.loads(path.read_text(encoding="utf-8"))


def test_character_white_cultivator_schema_and_look_states(white_cultivator_data):
    """CharacterV1 schema validation and core attributes for White Cultivator."""
    validate_contract("character", white_cultivator_data)
    assert white_cultivator_data["character_id"] == "WHITE_CULTIVATOR"
    assert white_cultivator_data["identity_version"] == "v1.0.0-lookdev-draft"

    vis = white_cultivator_data["visual_identity"]
    assert "early 20s" in vis["age_range"] or "21-24" in vis["age_range"]
    assert "ngân quan" in vis["hair"] or "silver crown" in vis["hair"]
    assert "slender" in vis["body_proportions"].lower()
    assert len(vis["unique_traits"]) >= 3

    beh = white_cultivator_data["behavioral_identity"]
    assert len(beh["baseline"]) >= 3
    assert len(beh["forbidden"]) >= 3

    # Check look state
    states = white_cultivator_data["look_states"]
    assert len(states) >= 1
    ls0 = states[0]
    assert ls0["look_state_id"] == "LOOK_WHITE_ROBE_V1"
    assert "Thanh Sương" in str(ls0["accessories"])


def test_character_black_cultivator_schema_and_look_states(black_cultivator_data):
    """CharacterV1 schema validation and core attributes for Black Cultivator."""
    validate_contract("character", black_cultivator_data)
    assert black_cultivator_data["character_id"] == "BLACK_CULTIVATOR"
    assert black_cultivator_data["identity_version"] == "v1.0.0-lookdev-draft"

    vis = black_cultivator_data["visual_identity"]
    assert "late 20s" in vis["age_range"] or "27-29" in vis["age_range"]
    assert "broad" in vis["body_proportions"].lower()
    assert "pauldron" in str(vis["unique_traits"]).lower() or "leather" in str(vis["unique_traits"]).lower()

    beh = black_cultivator_data["behavioral_identity"]
    assert len(beh["baseline"]) >= 3
    assert len(beh["forbidden"]) >= 3

    # Check look state
    states = black_cultivator_data["look_states"]
    assert len(states) >= 1
    ls0 = states[0]
    assert ls0["look_state_id"] == "LOOK_BLACK_ROBE_V1"
    assert "Huyền Minh" in str(ls0["accessories"])


def test_van_dai_terrace_location_and_landmarks(location_data):
    """Location specification, 180-degree axis, and cardinal landmarks."""
    assert location_data["location_id"] == "LOC_VAN_DAI_TERRACE"
    assert location_data["location_version"] == "LOC_V1"

    landmarks = location_data["cardinal_landmarks"]
    assert "north" in landmarks and "south" in landmarks
    assert "east" in landmarks and "west" in landmarks
    assert "center" in landmarks

    rules = location_data["spatial_continuity_rules"]
    assert "south" in rules["camera_axis_restriction"].lower()
    assert "x08" in rules["spatial_inversion_x08"].lower()


def test_visual_style_bible_palette_and_weapons(style_bible_data):
    """Visual style bible, color palette, weapon specs, and lens assignments."""
    palette = style_bible_data["color_palette"]["primary_hues"]
    assert palette["white_cultivator_robe"]["hex"] == "#F8F9FA"
    assert palette["black_cultivator_robe"]["hex"] == "#1C1D21"
    assert palette["white_cultivator_qi"]["hex"] == "#81D4FA"
    assert palette["black_cultivator_qi"]["hex"] == "#6A1B9A"

    weapons = style_bible_data["weapons_and_props"]
    assert weapons["sword_white_cultivator"]["blade_length_cm"] == 92.0
    assert weapons["sword_black_cultivator"]["blade_length_cm"] == 105.0
    assert weapons["sword_black_cultivator"]["blade_width_cm"] == 14.0

    lenses = style_bible_data["camera_and_optics_bible"]["lens_choices"]
    assert 28 in [lenses["establishing_wide"]["focal_mm"]]
    assert 40 in [lenses["full_dynamic_two_shot"]["focal_mm"]]
    assert 85 in [lenses["intense_closeup_payoff"]["focal_mm"]]


def test_concept_schematics_warning_labels():
    """Concept schematics must carry mandatory warning labels."""
    svg_path = LOOK_DEV_DIR / "concept_schematics.svg"
    md_path = LOOK_DEV_DIR / "concept_schematics.md"

    assert svg_path.exists()
    assert md_path.exists()

    svg_text = svg_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")

    expected_notice = "CONCEPT SCHEMATIC — NOT PHOTOREAL IDENTITY REFERENCE"
    assert expected_notice in svg_text
    assert expected_notice in md_text


def test_reference_asset_ledger_schema_and_fail_closed(ledger_data):
    """AssetV1 schema compliance and strict fail-closed UNBOUND assertions."""
    records = ledger_data["records"]
    assert len(records) == 5

    expected_ids = {
        "CHAR_WHITE_CULTIVATOR_REF_V1",
        "CHAR_BLACK_CULTIVATOR_REF_V1",
        "WARDROBE_WHITE_ROBE_V1",
        "WARDROBE_BLACK_ROBE_V1",
        "LOC_VAN_DAI_TERRACE_REF_V1",
    }
    actual_ids = set()

    for rec in records:
        validate_contract("asset", rec)
        actual_ids.add(rec["asset_id"])

        # Strict fail-closed integrity assertions:
        assert rec["uri_or_path"].startswith("UNBOUND:")
        assert rec["sha256"] is None, f"Asset {rec['asset_id']} must not fabricate sha256"
        assert rec["provider_asset_id"] is None, f"Asset {rec['asset_id']} must not fabricate provider_asset_id"
        assert rec["rights_metadata"]["qualification_tier"] == "DESIGN_CANDIDATE"
        assert rec["rights_metadata"]["binding_status"] == "UNBOUND"
        assert rec["rights_metadata"]["missing_action"] == "OWNER_IMAGE_SOURCE_REQUIRED"

    assert actual_ids == expected_ids


def test_cross_layer_shotspec_to_lookdev_congruence(white_cultivator_data, black_cultivator_data, ledger_data):
    """All 12 ShotSpecs (X01-X12) must map cleanly to lookdev entities and ledger IDs."""
    char_ids = {"WHITE_CULTIVATOR", "BLACK_CULTIVATOR"}
    look_state_ids = {"LOOK_WHITE_ROBE_V1", "LOOK_BLACK_ROBE_V1"}
    ledger_ids = {r["asset_id"] for r in ledger_data["records"]}

    shot_files = sorted(SHOTS_DIR.glob("X*.json"))
    assert len(shot_files) == 12

    for shot_file in shot_files:
        shot = json.loads(shot_file.read_text(encoding="utf-8"))
        for c in shot["characters"]:
            assert c["character_id"] in char_ids
            assert c["look_state_id"] in look_state_ids

        assert shot["environment"]["location_id"] == "LOC_VAN_DAI_TERRACE"

        refs = shot.get("references", {})
        for key in ("character_asset_ids", "wardrobe_asset_ids", "location_asset_ids"):
            for ref_id in refs.get(key, []):
                assert ref_id in ledger_ids, f"Unrecognized reference {ref_id} in {shot_file.name}"


def test_master_compilation_remains_strictly_immutable():
    """Master compilation SHA256 must match accepted baseline byte-for-byte."""
    data = MASTER_COMPILATION_PATH.read_bytes()
    computed_sha = hashlib.sha256(data).hexdigest()
    assert computed_sha == ACCEPTED_MASTER_SHA256, (
        f"Master compilation was altered! Expected {ACCEPTED_MASTER_SHA256}, got {computed_sha}"
    )
