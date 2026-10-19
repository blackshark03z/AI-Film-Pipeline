import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pytest

import promote_s08_candidate_002 as promoter


@pytest.fixture
def mock_isolated_env(tmp_path, monkeypatch):
    """Creates a mock isolated sandbox mirroring primary and worker trees."""
    fake_primary = tmp_path / "primary"
    fake_worker = tmp_path / "worker"

    # Setup primary dirs
    pkg = fake_primary / "projects/quality_v2_022_longform_120s"
    assets_dir = pkg / "assets"
    sheets_dir = pkg / "contact_sheets"
    frames_dir = pkg / "frames"
    assets_dir.mkdir(parents=True)
    sheets_dir.mkdir(parents=True)
    frames_dir.mkdir(parents=True)

    # Construct an unpromoted sandbox baseline state
    state = json.loads(promoter.CANONICAL_STATE_PATH.read_text(encoding="utf-8"))
    state["shots"]["S08"] = {
        "status": "PENDING",
        "account": "ACCOUNT_F",
        "conversation": None,
        "attempt_id": "attempt_b3cc3d00dc84e7ad3cde03c6bc624cd42feb5a5161867f6c0274ed19223763a6",
        "repair_needed": False,
        "repairs": state["shots"]["S08"].get("repairs", []),
    }
    state_bytes = json.dumps(state, indent=1, ensure_ascii=False).encode("utf-8")
    state_file = pkg / "v2_022_run_state.json"
    state_file.write_bytes(state_bytes)
    sandbox_baseline_sha = hashlib.sha256(state_bytes).hexdigest()
    monkeypatch.setattr(promoter, "BASELINE_STATE_SHA256", sandbox_baseline_sha)

    # Create dummy assets for the 8 baseline accepted shots with real hashes
    for sid, exp_sha in promoter.ACCEPTED_BASELINE_SHAS.items():
        real_asset = promoter.CANONICAL_ASSETS_DIR / f"{sid}.mp4"
        shutil.copy2(real_asset, assets_dir / f"{sid}.mp4")

    # Monkeypatch paths
    monkeypatch.setattr(promoter, "PRIMARY_ROOT", fake_primary)
    monkeypatch.setattr(promoter, "CANONICAL_PKG", pkg)
    monkeypatch.setattr(promoter, "CANONICAL_STATE_PATH", state_file)
    monkeypatch.setattr(promoter, "CANONICAL_ASSETS_DIR", assets_dir)
    monkeypatch.setattr(promoter, "CANONICAL_SHEETS_DIR", sheets_dir)
    monkeypatch.setattr(promoter, "CANONICAL_FRAMES_DIR", frames_dir)

    return {
        "pkg": pkg,
        "state_file": state_file,
        "assets_dir": assets_dir,
    }


def test_preflight_passes_on_real_environment():
    result = promoter.run_preflight()
    assert result["is_already_promoted"] is True
    assert result["manifest"]["shot_id"] == "S08"
    assert result["manifest"]["creation_id"] == promoter.EXPECTED_CREATION_ID


def test_preflight_fails_on_corrupt_state(mock_isolated_env):
    state_file = mock_isolated_env["state_file"]
    state_file.write_text('{"tampered": true}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="Canonical state SHA mismatch"):
        promoter.run_preflight()


def test_preflight_fails_on_corrupt_candidate_sha(mock_isolated_env, monkeypatch):
    fake_review_mp4 = mock_isolated_env["pkg"] / "fake_review.mp4"
    fake_review_mp4.write_bytes(b"corrupt")
    monkeypatch.setattr(promoter, "CANDIDATE_REVIEW_MP4", fake_review_mp4)
    with pytest.raises(RuntimeError, match="Review MP4 SHA mismatch"):
        promoter.run_preflight()


def test_destination_collision_guard(mock_isolated_env):
    colliding = mock_isolated_env["assets_dir"] / "S08.mp4"
    colliding.write_bytes(b"foreign media bytes")
    with pytest.raises(RuntimeError, match="Collision: target S08.mp4 exists"):
        promoter.run_preflight()


def test_continuity_engine_evaluation():
    manifest = json.loads(promoter.CANDIDATE_MANIFEST_PATH.read_text(encoding="utf-8"))
    verdict, failure_class = promoter.evaluate_continuity_qc(manifest["technical_qc"])
    assert verdict == "ACCEPT"
    assert failure_class is None


def test_sandboxed_safe_promotion_lifecycle(mock_isolated_env):
    preflight = promoter.run_preflight()
    assert preflight["is_already_promoted"] is False

    promoter.stage_and_copy_assets()
    target_s08 = mock_isolated_env["assets_dir"] / "S08.mp4"
    assert target_s08.exists()
    assert promoter._file_sha256(target_s08) == promoter.EXPECTED_CANDIDATE_SHA256

    qc_verdict, qc_failure = promoter.evaluate_continuity_qc(preflight["manifest"]["technical_qc"])
    sha_after = promoter.mutate_film_state(preflight["manifest"], qc_verdict, qc_failure)

    readback = promoter.readback_prove()
    assert readback["accepted_count"] == 9
    assert readback["pending_count"] == 15
    assert "S08" in readback["accepted_shots"]
    assert "S09" in readback["pending_shots"]
    assert "S10" in readback["accepted_shots"]

    # Verify preserved repairs in S08
    state = json.loads(mock_isolated_env["state_file"].read_text(encoding="utf-8"))
    s08 = state["shots"]["S08"]
    assert len(s08["repairs"]) == 1
    assert "day-1 hard refusal" in s08["repairs"][0]["reason"]
    assert state["mutations_used"] == 11
    assert s08["account"] == "ACCOUNT_A"
    assert s08["attempt_id"] == promoter.EXPECTED_ATTEMPT_ID
    assert s08["recovered"]["creation_id"] == promoter.EXPECTED_CREATION_ID
    assert s08["status"] == "QC_ACCEPT"

    # Idempotent re-run on promoted state
    preflight2 = promoter.run_preflight()
    assert preflight2["is_already_promoted"] is True
