"""Verification of XIANXIA60 Owner-Provisional ChatGPT Candidate Import (TASK-S3).

Verifies:
1. Physical existence of all imported files in staging directory.
2. Byte-exact SHA256 integrity, dimensions, and MIME type against candidate manifest.
3. Schema compliance of candidate reference records against schemas/asset.schema.json.
4. Non-fabrication invariants: no fake provider IDs, no premature visual lock.
5. Strict fail-closed preservation of canonical reference_asset_ledger.json (5/5 UNBOUND).
6. Immutability of accepted master compilation SHA256.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image
import pytest

from film_pipeline.core import validate_contract

ROOT = Path(__file__).resolve().parents[1]
LOOK_DEV_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "look_development"
STAGING_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "assets" / "references" / "chatgpt_candidates_wave01" / "XIANXIA60_ChatGPT_Reference_Candidates_v1"
ACCEPTED_MASTER_SHA256 = "f21b7b0f15c05cfa8f38ca385b58abf7bc9b2a479bc8a46f01e4b6949ff4ea5b"
MASTER_PATH = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "XIANXIA60_COMPILATION.json"

EXPECTED_FILES = {
    "owner_provisional_composite_source.png": {
        "sha256": "21f7bcb26510aa110f762a577401b3f042add2916b875fe6eff750077aaaa6ad",
        "size": (1536, 1024),
        "length": 2676300,
    },
    "ly_pha_van_portrait_candidate.png": {
        "sha256": "7cb5c496bb1b67f16bb7b09f4ca9bf625873240e14fde23769421cd59120a3e0",
        "size": (765, 626),
        "length": 692216,
    },
    "da_vo_nhai_portrait_candidate.png": {
        "sha256": "a89e067c39445c4485aa010d927270d025bc06ccffdc21d5fdc3303d493f3446",
        "size": (762, 626),
        "length": 698657,
    },
    "van_dai_arena_candidate.png": {
        "sha256": "545d02eda6684c7121f6e49cc8e14057f9ba1630aaad49c073dfbf15a8453694",
        "size": (1536, 389),
        "length": 1070488,
    },
    "candidate_manifest.json": {
        "sha256": "c2d1ecee1fd614fc3679add419760cd58ce207f449cdb062d191c8089da5bc38",
        "length": 3740,
    },
    "README_IMPORT.md": {
        "sha256": "13a6383b292aea00d12c1f6ba5c99577a3034e0b1f9fba0206671a4da3afef09",
        "length": 3002,
    },
}


def test_staging_files_exist_and_hashes_match():
    """All 6 files in candidate package must physically exist with byte-exact SHA256."""
    assert STAGING_DIR.exists(), f"Staging directory {STAGING_DIR} does not exist"
    for filename, meta in EXPECTED_FILES.items():
        file_path = STAGING_DIR / filename
        assert file_path.exists(), f"Missing staging file: {filename}"
        assert file_path.stat().st_size == meta["length"], f"Size mismatch for {filename}"
        actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_sha == meta["sha256"], f"SHA256 mismatch for {filename}"

        if filename.endswith(".png"):
            with Image.open(file_path) as img:
                assert img.size == meta["size"], f"Dimension mismatch for {filename}: {img.size} vs {meta['size']}"
                assert img.mode == "RGB", f"Color mode mismatch for {filename}"


def test_candidate_manifest_consistency():
    """Validate candidate_manifest.json contents against WP parameters."""
    manifest_path = STAGING_DIR / "candidate_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["film"] == "Nhat Kiem Pha Van / XIANXIA60"
    assert manifest["source_generation_id"] == "aaa9a666-817b-4932-9046-1a235e3cbea0"
    assert manifest["source_sha256"] == EXPECTED_FILES["owner_provisional_composite_source.png"]["sha256"]
    assert manifest["candidate_count"] == 3
    assert manifest["provider_actual_media_id"] is None

    # Check candidates
    for cand in manifest["candidates"]:
        fn = cand["file"]
        assert fn in EXPECTED_FILES
        assert cand["sha256"] == EXPECTED_FILES[fn]["sha256"]
        assert cand["local_binding_status"] == "UNBOUND"
        assert cand["provider_attestation_status"] == "NOT_ATTESTED"


def test_candidate_reference_ledger_schema_and_integrity():
    """Candidate ledger records must comply with schemas/asset.schema.json and remain UNBOUND."""
    ledger_path = LOOK_DEV_DIR / "candidate_reference_ledger.json"
    assert ledger_path.exists(), "candidate_reference_ledger.json not found"

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["ledger_status"] == "OWNER_PROVISIONAL_CANDIDATES_IMPORTED_UNBOUND"
    assert ledger["source_generation_id"] == "aaa9a666-817b-4932-9046-1a235e3cbea0"

    # Canonical status in candidate ledger confirms all 5 remain UNBOUND
    for canon_id, status in ledger["canonical_reference_status"].items():
        assert status == "UNBOUND", f"Canonical ref {canon_id} must be UNBOUND"

    records = ledger["records"]
    assert len(records) == 4, f"Expected 4 candidate records, got {len(records)}"

    for rec in records:
        # Validate against asset.schema.json via film_pipeline core
        validate_contract("asset", rec)

        # Asset origin constraints
        assert rec["asset_type"] == "image"
        assert rec["source_attempt_id"] is None
        assert rec["provider_asset_id"] is None

        # Check physical existence of referenced path
        asset_file = ROOT / rec["uri_or_path"]
        assert asset_file.exists(), f"Asset path {rec['uri_or_path']} does not exist on disk"
        computed_sha = hashlib.sha256(asset_file.read_bytes()).hexdigest()
        assert computed_sha == rec["sha256"], f"Hash mismatch for {rec['asset_id']}"

        # Non-fabrication & guard checks
        rm = rec["rights_metadata"]
        assert rm["binding_status"] == "UNBOUND"
        assert rm["provider_attestation_status"] == "NOT_ATTESTED"
        assert "NOT_VISUAL_LOCKED" in rm["candidate_status"]


def test_canonical_reference_ledger_unmodified_fail_closed():
    """Canonical reference_asset_ledger.json must remain strictly 5/5 UNBOUND with no fake IDs."""
    canon_path = LOOK_DEV_DIR / "reference_asset_ledger.json"
    assert canon_path.exists()
    canon_data = json.loads(canon_path.read_text(encoding="utf-8"))

    assert canon_data["unbound_references_count"] == 5
    assert canon_data["bound_references_count"] == 0
    assert len(canon_data["records"]) == 5

    for rec in canon_data["records"]:
        validate_contract("asset", rec)
        assert rec["uri_or_path"].startswith("UNBOUND:")
        assert rec["sha256"] is None
        assert rec["provider_asset_id"] is None
        assert rec["rights_metadata"]["binding_status"] == "UNBOUND"


def test_master_compilation_immutable():
    """Master compilation SHA256 must remain identical to frozen truth."""
    actual_sha = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
    assert actual_sha == ACCEPTED_MASTER_SHA256
