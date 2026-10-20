"""Tests for S11 Real Candidate 001 Runner."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import pytest
import run_s11_real_candidate_001 as runner


def test_frozen_prompt_hash():
    prompt_bytes = runner.FROZEN_S11_PROMPT.encode("utf-8")
    sha = hashlib.sha256(prompt_bytes).hexdigest()
    assert sha == runner.EXPECTED_CANDIDATE_PROMPT_SHA
    assert sha == "143e8e2cf3d097024cb89a4468b836f534f3b5f77cd3d211bec89bc5ab0f1eed"


def test_needle_and_prefix_in_prompt():
    assert runner.CANDIDATE_NEEDLE in runner.FROZEN_S11_PROMPT
    assert runner.CANDIDATE_PREFIX in runner.FROZEN_S11_PROMPT


def test_canonical_accepted_assets():
    for sid, exp_sha in runner.ACCEPTED_ASSETS_SHAS.items():
        p = runner.PRIMARY_ASSETS / f"{sid}.mp4"
        assert p.exists(), f"Missing canonical asset {p}"
        act_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        assert act_sha == exp_sha, f"Asset {sid} SHA mismatch: {act_sha} != {exp_sha}"


def test_prior_evidence_immutability():
    for fpath, exp_sha in runner.IMMUTABLE_PRIOR_FILES.items():
        assert fpath.exists(), f"Missing prior candidate file: {fpath}"
        act_sha = hashlib.sha256(fpath.read_bytes()).hexdigest().lower()
        assert act_sha == exp_sha.lower(), f"Prior file mutated: {fpath.name}"


def test_preflight_passes_on_clean_scope(tmp_path, monkeypatch):
    clean_iso = tmp_path / "clean_iso"
    monkeypatch.setattr(runner, "ISOLATED_DIR", clean_iso)
    res = runner.run_preflight()
    assert res["comp"] is not None
    assert res["state"] is not None


def test_preflight_detects_latched_scope(tmp_path, monkeypatch):
    iso = tmp_path / "latched_iso"
    slot_dir = iso / "slots" / "S11"
    slot_dir.mkdir(parents=True, exist_ok=True)
    auth_file = slot_dir / "mutation_authority.json"
    auth_file.write_text(json.dumps({
        "version": "mutation-authority-v1",
        "scope_id": runner.SCOPE_ID,
        "mutation_authority": "LATCHED_CLOSED",
        "external_effect_knowledge": "RESOLVED_EFFECT_IDENTIFIED",
        "latch_reason": "TEST_LATCH",
        "events": []
    }), encoding="utf-8")
    monkeypatch.setattr(runner, "ISOLATED_DIR", iso)
    with pytest.raises(RuntimeError, match="authority is already latched"):
        runner.run_preflight()


def test_post_execution_real_scope_is_latched():
    slot_dir = runner.ISOLATED_DIR / "slots" / "S11"
    assert slot_dir.exists(), "Real scope slot dir missing"
    auth_file = slot_dir / "mutation_authority.json"
    assert auth_file.exists(), "Mutation authority missing"
    data = json.loads(auth_file.read_text(encoding="utf-8"))
    assert data["mutation_authority"] == "LATCHED_CLOSED"
    assert data["external_effect_knowledge"] == "RESOLVED_EFFECT_IDENTIFIED"


def test_preflight_fails_on_corrupt_prompt(tmp_path, monkeypatch):
    clean_iso = tmp_path / "clean_iso"
    monkeypatch.setattr(runner, "ISOLATED_DIR", clean_iso)
    monkeypatch.setattr(runner, "FROZEN_S11_PROMPT", "Corrupted prompt text")
    with pytest.raises(RuntimeError, match="Prompt SHA mismatch"):
        runner.run_preflight()


def test_preflight_fails_on_corrupt_state(tmp_path, monkeypatch):
    clean_iso = tmp_path / "clean_iso"
    monkeypatch.setattr(runner, "ISOLATED_DIR", clean_iso)
    fake_state = tmp_path / "fake_state.json"
    fake_state.write_text('{"tampered": true}', encoding="utf-8")
    monkeypatch.setattr(runner, "CANONICAL_STATE_PATH", fake_state)
    with pytest.raises(RuntimeError, match="Canonical state SHA mismatch"):
        runner.run_preflight()


def test_preflight_fails_on_corrupt_compilation(tmp_path, monkeypatch):
    clean_iso = tmp_path / "clean_iso"
    monkeypatch.setattr(runner, "ISOLATED_DIR", clean_iso)
    fake_comp = tmp_path / "fake_comp.json"
    fake_comp.write_text('{"tampered": true}', encoding="utf-8")
    monkeypatch.setattr(runner, "COMP_PATH", fake_comp)
    with pytest.raises(RuntimeError, match="Compilation SHA mismatch"):
        runner.run_preflight()


def test_preflight_fails_on_missing_canonical_asset(tmp_path, monkeypatch):
    clean_iso = tmp_path / "clean_iso"
    monkeypatch.setattr(runner, "ISOLATED_DIR", clean_iso)
    tampered_assets = dict(runner.ACCEPTED_ASSETS_SHAS)
    tampered_assets["S01"] = "0" * 64
    monkeypatch.setattr(runner, "ACCEPTED_ASSETS_SHAS", tampered_assets)
    with pytest.raises(RuntimeError, match="Canonical asset S01 SHA mismatch"):
        runner.run_preflight()
