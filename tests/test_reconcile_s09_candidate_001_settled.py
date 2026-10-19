"""Tests for S09 Candidate-001 Settled Read-Only Exact Provider Reconciliation."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pytest
import reconcile_s09_candidate_001_settled as reconciler


def test_frozen_prompt_hash():
    prompt_bytes = reconciler.FROZEN_S09_PROMPT.encode("utf-8")
    sha = hashlib.sha256(prompt_bytes).hexdigest()
    assert sha == reconciler.EXPECTED_CANDIDATE_PROMPT_SHA
    assert sha == "880d734aa5097b839c8be4740a4c4b320fff1e77d371614da494169085d146a1"


def test_preflight_passes_on_real_environment():
    res = reconciler.run_preflight()
    assert res["comp"] is not None
    assert res["state"] is not None


def test_preflight_fails_on_corrupt_prompt(monkeypatch):
    monkeypatch.setattr(reconciler, "FROZEN_S09_PROMPT", "corrupted prompt")
    with pytest.raises(RuntimeError, match="Prompt SHA mismatch"):
        reconciler.run_preflight()


def test_preflight_fails_on_corrupt_state(tmp_path, monkeypatch):
    fake_state = tmp_path / "fake_state.json"
    fake_state.write_text('{"tampered": true}', encoding="utf-8")
    monkeypatch.setattr(reconciler, "CANONICAL_STATE_PATH", fake_state)
    with pytest.raises(RuntimeError, match="Canonical state SHA mismatch"):
        reconciler.run_preflight()


def test_preflight_fails_on_tampered_candidate_001_evidence(tmp_path, monkeypatch):
    fake_evidence = tmp_path / "fake_journal.jsonl"
    fake_evidence.write_text("tampered", encoding="utf-8")
    tampered_dict = dict(reconciler.IMMUTABLE_CANDIDATE_001_FILES)
    # Point one entry to the tampered file
    key = list(tampered_dict.keys())[0]
    tampered_dict[fake_evidence] = tampered_dict.pop(key)
    monkeypatch.setattr(reconciler, "IMMUTABLE_CANDIDATE_001_FILES", tampered_dict)
    with pytest.raises(RuntimeError, match="Candidate-001 evidence mutated"):
        reconciler.run_preflight()


def test_post_immutability_verification():
    # Calling on real untouched files must succeed cleanly
    reconciler.verify_post_immutability()
