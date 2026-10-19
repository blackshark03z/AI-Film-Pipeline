"""Tests for S09 Real Candidate 001 Runner."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pytest
import run_s09_real_candidate_001 as runner


def test_frozen_prompt_hash():
    prompt_bytes = runner.FROZEN_S09_PROMPT.encode("utf-8")
    sha = hashlib.sha256(prompt_bytes).hexdigest()
    assert sha == runner.EXPECTED_CANDIDATE_PROMPT_SHA
    assert sha == "880d734aa5097b839c8be4740a4c4b320fff1e77d371614da494169085d146a1"


def test_preflight_detects_latched_scope():
    with pytest.raises(RuntimeError, match="authority is already latched"):
        runner.run_preflight()


def test_preflight_passes_on_clean_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ISOLATED_DIR", tmp_path / "clean_iso")
    res = runner.run_preflight()
    assert res["comp"] is not None
    assert res["state"] is not None


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
