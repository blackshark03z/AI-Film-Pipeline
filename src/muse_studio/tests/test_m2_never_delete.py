"""PRE-TAG M2 (lane contract v8 section 10 #11): a received clip is never deleted, even when quarantine fails."""
import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

import muse_studio.cli as cli
import muse_studio.core.batch_packager as bp
from muse_studio.core.batch_packager import BatchPackager, IntegrityUnpersistedError
from muse_studio.core.headless_muse_client import HeadlessMuseClient
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine
from muse_studio.tests.test_lane_review_r2 import _make_accounts
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project

BIG = 200 * 1024


@pytest.fixture(autouse=True)
def _temp_lease_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path / "lane_leases.json"))


def _batch(tmp_path: Path):
    """A project with 2 shots and a result zip whose second clip does not match its receipt SHA-256."""
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    shots = sorted(s["shot_id"] for s in json.loads((proj / "shots_manifest.json").read_text(encoding="utf-8"))["shots"])
    s1, s2 = shots[:2]
    good, bad = b"GOOD".ljust(8, b"\x00") + b"\x00" * BIG, b"BAD".ljust(8, b"\x00") + b"\x00" * BIG
    zp = tmp_path / "res.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("shot_01.mp4", good)
        zf.writestr("shot_02.mp4", bad)
        zf.writestr("batch_receipt.json", json.dumps({"shots": [
            {"shot_id": s1, "output_file": "shot_01.mp4", "sha256": hashlib.sha256(good).hexdigest()},
            {"shot_id": s2, "output_file": "shot_02.mp4", "sha256": "0" * 64},
        ]}))
    bdir = proj / "BATCHES_V2" / "POOL_X_R01_B01"
    bdir.mkdir(parents=True)
    man = bdir / "POOL_X_R01_B01_manifest.json"
    man.write_text(json.dumps({"shots": [{"slot_id": "shot_01", "shot_id": s1},
                                         {"slot_id": "shot_02", "shot_id": s2}]}), encoding="utf-8")
    return proj, bdir, man, zp, (s1, s2)


def _fail_replace_for(monkeypatch, name_part: str):
    real = os.replace

    def fake(src, dst, *a, **k):
        if name_part in str(src):
            raise PermissionError("simulated: file held open")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(bp.os, "replace", fake)


def test_failed_quarantine_keeps_the_file_listed_and_never_selected(tmp_path: Path, monkeypatch):
    proj, bdir, man, zp, (s1, s2) = _batch(tmp_path)
    _fail_replace_for(monkeypatch, "shot_02.mp4")
    res = BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", handoff_manifest_path=man)
    bad = bdir / "verified_clips" / "shot_02.mp4"
    assert bad.exists(), "a received clip was deleted when its quarantine move failed"
    assert "shot_02.mp4" in BatchPackager.read_integrity_failed(bdir)[1]
    assert s2 in res["integrity_failed_shots"] and s2 not in res["verified_shots"] and s1 in res["verified_shots"]
    assert res["clips"]["shot_02"]["quarantine_failed"] is True
    assert res["verified"] is False and "status" not in res
    # every reader of clip candidates honours the exclusion
    assert cli._clip_integrity_bad(bad)
    cand = cli._discover_all_clip_candidates(proj, json.loads((proj / "shots_manifest.json").read_text("utf-8")))
    assert bad not in cand.get(s2, []) and not any(Path(p) == bad for ps in cand.values() for p in ps)
    existing = cli._discover_existing_clip_map(proj, json.loads((proj / "shots_manifest.json").read_text("utf-8")))
    assert Path(existing.get(s2, "")) != bad


def test_unreadable_exclusion_list_is_failed_closed_by_readers(tmp_path: Path):
    proj, bdir, man, zp, (s1, s2) = _batch(tmp_path)
    BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", handoff_manifest_path=man)
    (bdir / bp.INTEGRITY_FAILED_FILE).write_text("{not json", encoding="utf-8")
    assert BatchPackager.read_integrity_failed(bdir)[0] is False
    assert cli._clip_integrity_bad(bdir / "verified_clips" / "shot_01.mp4")  # list unknown: nothing is trusted
    with pytest.raises(OSError):  # and the unreadable list is never overwritten (it may hold earlier exclusions)
        BatchPackager.record_integrity_failure(bdir, "shot_02.mp4")


def test_unpersistable_exclusion_with_failed_move_stops(tmp_path: Path, monkeypatch):
    proj, bdir, man, zp, (s1, s2) = _batch(tmp_path)
    _fail_replace_for(monkeypatch, "shot_02.mp4")

    def boom(batch_dir, clip_name):
        raise OSError("simulated: disk full")

    monkeypatch.setattr(BatchPackager, "record_integrity_failure", staticmethod(boom))
    with pytest.raises(IntegrityUnpersistedError) as ei:
        BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", handoff_manifest_path=man)
    assert ei.value.status == "INTEGRITY_UNPERSISTED" and ei.value.clips == ["shot_02.mp4"]
    assert (bdir / "verified_clips" / "shot_02.mp4").exists(), "the clip was deleted"
    assert s2 not in ei.value.results.get("verified_shots", {}) and ei.value.results["verified"] is False


def test_unpersisted_but_quarantined_is_not_a_stop(tmp_path: Path, monkeypatch):
    """The move worked, so the clip is out of every candidate directory: no stop."""
    proj, bdir, man, zp, (s1, s2) = _batch(tmp_path)

    def boom(batch_dir, clip_name):
        raise OSError("simulated: disk full")

    monkeypatch.setattr(BatchPackager, "record_integrity_failure", staticmethod(boom))
    res = BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", handoff_manifest_path=man)
    assert res["clips"]["shot_02"]["quarantined"] is True
    assert (bdir / "integrity_failed" / "shot_02.mp4").exists()


def test_engine_stops_with_integrity_unpersisted_and_marks_batch_unconfirmed(tmp_path: Path, monkeypatch, capsys):
    import muse_studio.pool_runner as pool_runner

    mgr, _ = _make_accounts(tmp_path, 2)
    sent = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False, lease_guard=None):
            sent.append(batch_id)
            exc = IntegrityUnpersistedError("clip shot_02.mp4 could be neither listed nor quarantined",
                                            results={"verified": False}, clips=["shot_02.mp4"])
            exc.submitted = True  # the client tags every post-send failure
            raise exc

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False,
                                qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}})
    monkeypatch.setattr(pool_runner, "_build_engine", lambda args: engine)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=12)
    rc = pool_runner.main(["videos", str(proj), "--max-accounts", "2", "--max-rounds", "3"])
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "INTEGRITY_UNPERSISTED" and rc == 5
    assert "INTEGRITY_UNPERSISTED" in captured.err and "shot_02.mp4" in captured.err
    assert res["integrity_unpersisted"][0]["clips"] == ["shot_02.mp4"]
    assert len(sent) <= 2, "dispatching went on after the integrity stop"
    ledger = json.loads((proj / "unconfirmed_submissions.json").read_text(encoding="utf-8"))["entries"]
    assert ledger and {e["status"] for e in ledger} == {"UNCONFIRMED"}, "children must be UNCONFIRMED, never RESULT"
    assert not any(e.get("reason") == "RESULT_RECEIVED" for e in ledger)
