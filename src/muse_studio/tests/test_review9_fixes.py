"""Regression tests for review 9 of the round-8 fixes (one group per finding)."""
import hashlib
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

import pytest

import muse_studio.cli as cli
from muse_studio.core import autoprod_orchestrator as ao
from muse_studio.core import batch_packager as bp
from muse_studio.core.autoprod_orchestrator import SessionLock, _render_fingerprint
from muse_studio.core.batch_packager import BatchPackager
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.parallel_pool_engine import UNCONFIRMED_FILE
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project
from muse_studio.tests.test_review6_fixes import BIG, _audit, _fake_eval, _make_batch, _shots, _video_engine_pass
from muse_studio.tests.test_review7_fixes import _two_take_audit, _write_ledger


def _bad_receipt(clip: Path, sid: str) -> None:
    """A receipt next to the clip whose SHA-256 does not match it (an older, never-quarantined integrity failure)."""
    (clip.parent / "batch_receipt.json").write_text(json.dumps({"shots": [
        {"shot_id": sid, "output_file": clip.name, "sha256": "0" * 64}]}), encoding="utf-8")


# ---- r9#1: discovery honours receipts and durable exclusions -----------------------------------------------------------
def test_discovery_skips_old_unquarantined_sha_mismatch(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    bad = _make_batch(proj, "POOL_OLD_R01_B01", sid, b"BAD", fingerprint=_render_fingerprint(shot, False))
    _bad_receipt(bad, sid)
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"BAD": 99.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    assert sid not in _audit(proj)["passed_clips"], "an SHA-mismatched clip passed the audit"


def test_discovery_skips_canonical_copy_of_a_bad_clip(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    fp = _render_fingerprint(shot, False)
    bad = _make_batch(proj, "POOL_OLD_R01_B01", sid, b"BAD", fingerprint=fp)
    _bad_receipt(bad, sid)
    canonical = proj / "verified_clips" / f"{sid}.mp4"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bad, canonical)  # an older audit already copied the bad clip into the canonical slot
    (proj / "qc_audit_report.json").write_text(json.dumps({
        "passed_clips": {sid: str(canonical)}, "render_fingerprints": {sid: fp},
        "per_shot_qc": {sid: {"verdict": "PASS", "clip_path": str(bad), "take": 1, "batch_id": "POOL_OLD_R01_B01"}},
    }), encoding="utf-8")
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"BAD": 99.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    assert sid not in _audit(proj)["passed_clips"], "the canonical copy of an SHA-mismatched clip passed"


def test_failed_quarantine_leaves_durable_exclusion(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid = next(iter(_shots(proj)))
    bad = b"BAD".ljust(8, b"\x00") + b"\x00" * BIG
    zp = tmp_path / "res.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("shot_01.mp4", bad)
        zf.writestr("batch_receipt.json", json.dumps({"shots": [
            {"shot_id": sid, "output_file": "shot_01.mp4", "sha256": "0" * 64}]}))
    bdir = proj / "BATCHES_V2" / "POOL_Q_R01_B01"
    bdir.mkdir(parents=True)
    man = bdir / "POOL_Q_R01_B01_manifest.json"
    man.write_text(json.dumps({"shots": [{"slot_id": "shot_01", "shot_id": sid}]}), encoding="utf-8")

    def no_replace(*a, **k):
        raise OSError("file in use")

    real_unlink = Path.unlink

    def guarded_unlink(self, *a, **k):
        if self.name == "shot_01.mp4":
            raise OSError("file in use")
        return real_unlink(self, *a, **k)

    monkeypatch.setattr(bp.os, "replace", no_replace)
    monkeypatch.setattr(Path, "unlink", guarded_unlink)
    try:
        BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", handoff_manifest_path=man)
    finally:
        monkeypatch.undo()
    assert (bdir / "verified_clips" / "shot_01.mp4").exists()  # both rename and unlink failed
    record = json.loads((bdir / "integrity_failed.json").read_text(encoding="utf-8"))
    assert "shot_01.mp4" in record["clips"]
    (bdir / "verified_clips" / "batch_receipt.json").unlink()  # only the durable record may exclude it now
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"BAD": 99.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    assert sid not in _audit(proj)["passed_clips"], "a clip with a failed quarantine was audited"


def test_discovery_keeps_clip_with_matching_receipt(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    good = _make_batch(proj, "POOL_OK_R01_B01", sid, b"GOOD", fingerprint=_render_fingerprint(shot, False))
    (good.parent / "batch_receipt.json").write_text(json.dumps({"shots": [
        {"shot_id": sid, "output_file": good.name, "sha256": hashlib.sha256(good.read_bytes()).hexdigest()}]}),
        encoding="utf-8")
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"GOOD": 70.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    assert sid in _audit(proj)["passed_clips"]


# ---- r9#2: a corrupt / empty result zip never releases a pending send --------------------------------------------------
def _pending_with_zip(tmp_path: Path, zip_bytes):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    bid = "POOL_Z_R01_B01"
    bdir = proj / "BATCHES_V2" / bid
    bdir.mkdir(parents=True)
    zp = bdir / f"{bid}_result.zip"
    if zip_bytes is None:
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("shot_01.mp4", b"\x00" * 4096)
    else:
        zp.write_bytes(zip_bytes)
    _write_ledger(proj, [{"shot_id": sid, "batch_id": bid, "take": 1, "status": "PENDING_SEND",
                          "submitted_epoch": time.time(), "fingerprint": _render_fingerprint(shot, False)}])
    return proj, sid


@pytest.mark.parametrize("zip_bytes", [b"", b"PK\x03\x04 truncated download"])
def test_corrupt_result_zip_keeps_send_blocked(tmp_path: Path, zip_bytes):
    proj, sid = _pending_with_zip(tmp_path, zip_bytes)
    engine, calls = _video_engine_pass(tmp_path, lambda n: None)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    assert calls == [], "a corrupt result zip released a pending send"
    assert [e["status"] for e in res["unconfirmed_submissions"]] == ["RESULT_CORRUPT"]
    assert res["unconfirmed_released"] == []

    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False,
                            release_unconfirmed=[sid])
    assert len(calls) == 1 and res["unconfirmed_released"][0]["reason"] == "MANUAL"


def test_valid_result_zip_releases_pending_send(tmp_path: Path):
    proj, _ = _pending_with_zip(tmp_path, None)
    engine, calls = _video_engine_pass(tmp_path, lambda n: None)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    assert [e["reason"] for e in res["unconfirmed_released"]] == ["RESULT_RECEIVED"]
    assert len(calls) == 1


# ---- r9#3: a failed metadata write after the OS lock never leaks the lock ----------------------------------------------
def test_session_lock_metadata_failure_releases_os_lock(tmp_path: Path, monkeypatch):
    real_fsync = os.fsync
    state = {"fail": True}

    def flaky_fsync(fd):
        if state.pop("fail", False):
            raise OSError("disk full")
        return real_fsync(fd)

    monkeypatch.setattr(ao.os, "fsync", flaky_fsync)
    with pytest.raises(OSError):
        SessionLock(tmp_path, session_tag="first").acquire()
    lk = SessionLock(tmp_path, session_tag="second")
    lk.acquire()  # SessionConflictError here = the first attempt leaked its OS lock
    lk.release()


# ---- r9#4: the canonical copy keeps a promoted take when its source clip is gone -------------------------------------
def test_qc_audit_keeps_promoted_take_from_canonical_copy(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, _, c2 = _two_take_audit(proj, monkeypatch, capsys)
    assert cli.main(["promote-take", str(proj), sid, "2"]) == 0
    capsys.readouterr()
    c2.unlink()  # the promoted take's source clip is gone; the canonical copy is still that take
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    rec = _audit(proj)["per_shot_qc"][sid]
    assert rec["take"] == 2 and rec.get("selected_by") == "promote-take", "the audit dropped the promoted take"
    assert (proj / "verified_clips" / f"{sid}.mp4").read_bytes()[:1] == b"B"
