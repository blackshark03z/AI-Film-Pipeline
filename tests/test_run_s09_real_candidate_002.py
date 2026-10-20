"""Tests for S09 Real Candidate 002 Runner."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import pytest
import run_s09_real_candidate_002 as runner


def test_frozen_prompt_hash():
    prompt_bytes = runner.FROZEN_S09_PROMPT.encode("utf-8")
    sha = hashlib.sha256(prompt_bytes).hexdigest()
    assert sha == runner.EXPECTED_CANDIDATE_PROMPT_SHA
    assert sha == "0aef0a7bd851299cb89690f5cccc3d5e3558a1e1c3d632d9d58542d7ae5d00af"


def test_needle_in_prompt():
    assert runner.CANDIDATE_NEEDLE in runner.FROZEN_S09_PROMPT
    assert runner.CANDIDATE_PREFIX in runner.FROZEN_S09_PROMPT


def test_candidate_001_immutability():
    for fpath, exp_sha in runner.IMMUTABLE_CANDIDATE_001_FILES.items():
        assert fpath.exists(), f"Missing Candidate-001 file: {fpath}"
        act_sha = hashlib.sha256(fpath.read_bytes()).hexdigest().lower()
        assert act_sha == exp_sha.lower(), f"Candidate-001 file mutated: {fpath.name}"


def test_preflight_passes_on_clean_scope():
    res = runner.run_preflight()
    assert res["comp"] is not None
    assert res["state"] is not None


def test_preflight_detects_latched_scope(tmp_path, monkeypatch):
    iso = tmp_path / "latched_iso"
    slot_dir = iso / "slots" / "S09"
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


def test_preflight_fails_on_corrupt_prompt(monkeypatch):
    monkeypatch.setattr(runner, "FROZEN_S09_PROMPT", "Corrupted prompt text")
    with pytest.raises(RuntimeError, match="Prompt SHA mismatch"):
        runner.run_preflight()


def test_preflight_fails_on_corrupt_state(tmp_path, monkeypatch):
    fake_state = tmp_path / "fake_state.json"
    fake_state.write_text('{"tampered": true}', encoding="utf-8")
    monkeypatch.setattr(runner, "CANONICAL_STATE_PATH", fake_state)
    with pytest.raises(RuntimeError, match="Canonical state SHA mismatch"):
        runner.run_preflight()


def test_preflight_fails_on_corrupt_compilation(tmp_path, monkeypatch):
    fake_comp = tmp_path / "fake_comp.json"
    fake_comp.write_text('{"tampered": true}', encoding="utf-8")
    monkeypatch.setattr(runner, "COMP_PATH", fake_comp)
    with pytest.raises(RuntimeError, match="Compilation SHA mismatch"):
        runner.run_preflight()
