"""Validation and preflight gate for XIANXIA60 Look Development and Reference Assets.

Verifies:
1. CharacterV1 contracts against schemas/character.schema.json
2. AssetV1 records against schemas/asset.schema.json
3. Cross-layer mapping with X01-X12 ShotSpecs (characters, look_states, location, references)
4. Fail-closed reference binding gate (asserts UNBOUND, zero fake sha256, zero fake media_ids)
5. Master compilation SHA256 immutability
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import validate_contract

ACCEPTED_MASTER_SHA256 = "f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b"
LOOK_DEV_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "look_development"
SHOTS_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "shots"
MASTER_PATH = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "XIANXIA60_COMPILATION.json"


class LookDevPreflightGateError(Exception):
    """Raised when preflight rules are violated."""


def validate_character_specs() -> dict[str, dict]:
    """Validate CharacterV1 specs for White Cultivator and Black Cultivator."""
    white_path = LOOK_DEV_DIR / "character_white_cultivator.json"
    black_path = LOOK_DEV_DIR / "character_black_cultivator.json"

    if not white_path.exists() or not black_path.exists():
        raise LookDevPreflightGateError("Missing character design files in look_development/")

    white_data = json.loads(white_path.read_text(encoding="utf-8"))
    black_data = json.loads(black_path.read_text(encoding="utf-8"))

    validate_contract("character", white_data)
    validate_contract("character", black_data)

    assert white_data["character_id"] == "WHITE_CULTIVATOR"
    assert black_data["character_id"] == "BLACK_CULTIVATOR"

    # Validate look states
    white_look_ids = {ls["look_state_id"] for ls in white_data["look_states"]}
    black_look_ids = {ls["look_state_id"] for ls in black_data["look_states"]}

    assert "LOOK_WHITE_ROBE_V1" in white_look_ids
    assert "LOOK_BLACK_ROBE_V1" in black_look_ids

    return {"WHITE_CULTIVATOR": white_data, "BLACK_CULTIVATOR": black_data}


def validate_reference_ledger() -> list[dict]:
    """Validate AssetV1 records and fail-closed preflight bindings."""
    ledger_path = LOOK_DEV_DIR / "reference_asset_ledger.json"
    if not ledger_path.exists():
        raise LookDevPreflightGateError("Missing reference_asset_ledger.json")

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    records = ledger["records"]
    assert len(records) == 5, f"Expected 5 canonical references, got {len(records)}"

    expected_asset_ids = {
        "CHAR_WHITE_CULTIVATOR_REF_V1",
        "CHAR_BLACK_CULTIVATOR_REF_V1",
        "WARDROBE_WHITE_ROBE_V1",
        "WARDROBE_BLACK_ROBE_V1",
        "LOC_VAN_DAI_TERRACE_REF_V1",
    }

    found_ids = set()
    for rec in records:
        validate_contract("asset", rec)
        found_ids.add(rec["asset_id"])

        # Strict fail-closed integrity checks:
        # Since no real image exists on disk, sha256 and provider_asset_id MUST be None
        assert rec["uri_or_path"].startswith("UNBOUND:"), f"Asset {rec['asset_id']} must report UNBOUND"
        assert rec["sha256"] is None, f"Asset {rec['asset_id']} fabricated sha256!"
        assert rec["provider_asset_id"] is None, f"Asset {rec['asset_id']} fabricated provider_asset_id!"
        assert rec["rights_metadata"].get("binding_status") == "UNBOUND"
        assert rec["rights_metadata"].get("missing_action") == "OWNER_IMAGE_SOURCE_REQUIRED"

    assert found_ids == expected_asset_ids, f"Mismatch in canonical asset IDs: {found_ids} vs {expected_asset_ids}"
    return records


def validate_cross_layer_shotspec_mapping(characters: dict[str, dict], records: list[dict]) -> dict[str, int]:
    """Verify that all 12 ShotSpecs correctly map to Character, Location, and Reference IDs."""
    record_ids = {r["asset_id"] for r in records}
    char_ids = set(characters.keys())
    look_state_ids = {
        ls["look_state_id"]
        for c in characters.values()
        for ls in c["look_states"]
    }

    shot_files = sorted(SHOTS_DIR.glob("X*.json"))
    assert len(shot_files) == 12, f"Expected 12 ShotSpec files, got {len(shot_files)}"

    for shot_file in shot_files:
        shot = json.loads(shot_file.read_text(encoding="utf-8"))
        # Validate characters
        for cref in shot["characters"]:
            assert cref["character_id"] in char_ids, f"Unknown character {cref['character_id']} in {shot_file.name}"
            assert cref["look_state_id"] in look_state_ids, f"Unknown look_state {cref['look_state_id']} in {shot_file.name}"

        # Validate environment
        env = shot.get("environment")
        assert env is not None, f"Missing environment in {shot_file.name}"
        assert env["location_id"] == "LOC_VAN_DAI_TERRACE"

        # Validate references mapping
        refs = shot.get("references", {})
        for ref_list_key in ("character_asset_ids", "wardrobe_asset_ids", "location_asset_ids"):
            for aid in refs.get(ref_list_key, []):
                assert aid in record_ids, f"Reference {aid} in {shot_file.name} not tracked in ledger"

    return {"mapped_shots": len(shot_files)}


def verify_master_compilation_immutability() -> str:
    """Ensure accepted XIANXIA60_COMPILATION.json is not modified."""
    data = MASTER_PATH.read_bytes()
    computed_sha = hashlib.sha256(data).hexdigest()
    if computed_sha != ACCEPTED_MASTER_SHA256:
        raise LookDevPreflightGateError(
            f"Master compilation modified! Expected {ACCEPTED_MASTER_SHA256}, got {computed_sha}"
        )
    return computed_sha


def run_full_validation() -> dict:
    chars = validate_character_specs()
    records = validate_reference_ledger()
    mapping_stats = validate_cross_layer_shotspec_mapping(chars, records)
    master_sha = verify_master_compilation_immutability()

    return {
        "status": "PASS",
        "character_specs_validated": list(chars.keys()),
        "reference_records_validated": len(records),
        "unbound_fail_closed_verified": True,
        "shotspec_cross_layer_mapping": mapping_stats,
        "master_compilation_sha256": master_sha,
        "master_compilation_immutable": True,
    }


if __name__ == "__main__":
    result = run_full_validation()
    print(json.dumps(result, indent=2))
