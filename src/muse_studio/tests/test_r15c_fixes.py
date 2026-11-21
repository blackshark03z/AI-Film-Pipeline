"""Codex r15c fixes (muse side). Tmp stores only: never the real halt, `~/.afp` or `accounts.json`."""
import asyncio
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import muse_studio.cli as cli
import muse_studio.core.queue_dispatcher as qd
from muse_studio.core.autoprod_orchestrator import _clip_currently_excluded, _load_render_checkpoint
from muse_studio.core.autoprod_orchestrator import _render_fingerprint
from muse_studio.core.batch_packager import INTEGRITY_FAILED_FILE, BatchPackager
from muse_studio.tests.test_lane_review_r2 import _make_accounts
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project
from muse_studio.tests.test_review6_fixes import _audit
from muse_studio.tests.test_review7_fixes import _two_take_audit, _shots


@pytest.fixture(autouse=True)
def _temp_lease_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path / "lane_leases.json"))


# ---- 1. the canonical copy written by qc-audit is judged through its source batch + recorded copy SHA ----------------
def _canonical(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, c1, _ = _two_take_audit(proj, monkeypatch, capsys)
    canonical = proj / "verified_clips" / f"{sid}.mp4"
    audit = _audit(proj)
    assert audit["passed_clips"][sid] == str(canonical), "qc-audit no longer writes the canonical path"
    rec = audit["per_shot_qc"][sid]
    assert rec["copy_sha256"] == hashlib.sha256(canonical.read_bytes()).hexdigest()
    assert Path(rec["clip_path"]) == c1  # provenance: the source batch clip
    return proj, sid, c1, canonical, rec


def test_canonical_copy_is_trusted_while_its_source_is_clean(tmp_path: Path, monkeypatch, capsys):
    _, _, _, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    assert not cli._clip_integrity_bad(canonical, rec)
    assert not _clip_currently_excluded(str(canonical), rec)


def test_canonical_copy_rejected_when_its_source_batch_clip_is_excluded(tmp_path: Path, monkeypatch, capsys):
    proj, sid, c1, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    BatchPackager.record_integrity_failure(c1.parent.parent, c1.name)  # excluded AFTER the audit
    assert cli._clip_integrity_bad(canonical, rec)
    assert _clip_currently_excluded(str(canonical), rec)
    # the real readers: assemble and the render checkpoint both refuse the canonical path
    rc = cli.main(["assemble", str(proj)])
    assert rc == 1 and json.loads(capsys.readouterr().out)["error"] == "NO_QC_PASSED_CLIPS"
    shot = _shots(proj)[sid]
    audit_p = proj / "qc_audit_report.json"
    audit = json.loads(audit_p.read_text(encoding="utf-8"))
    audit["render_fingerprints"][sid] = _render_fingerprint(shot, False)
    audit_p.write_text(json.dumps(audit), encoding="utf-8")
    assert _load_render_checkpoint(audit_p, {sid: shot}, False)[0] == {}
    assert canonical.exists() and c1.exists(), "nothing may be deleted"


def test_canonical_copy_rejected_when_the_source_exclusion_list_is_unreadable(tmp_path: Path, monkeypatch, capsys):
    _, _, c1, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    (c1.parent.parent / INTEGRITY_FAILED_FILE).write_text("null", encoding="utf-8")
    assert cli._clip_integrity_bad(canonical, rec)
    assert _clip_currently_excluded(str(canonical), rec)


def test_canonical_copy_rejected_when_the_copy_no_longer_matches_its_recorded_sha(tmp_path: Path, monkeypatch, capsys):
    _, _, _, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    canonical.write_bytes(canonical.read_bytes() + b"tampered")
    assert cli._clip_integrity_bad(canonical, rec)
    assert _clip_currently_excluded(str(canonical), rec)


# ---- 2. a failed quarantine stops the shot: the next attempt must not overwrite the kept clip ----------------------
def _dispatch_project(tmp_path: Path, monkeypatch, quarantine_fails: bool):
    from muse_studio.core.project_manager import ProjectManager

    mgr, _ = _make_accounts(tmp_path, 1)
    pm = ProjectManager(projects_dir=tmp_path / "projects")
    pid = pm.create_project("Quarantine", mode="batch_parallel")["id"]
    pm.add_shot(pid, prompt="Shot A")
    calls = []

    async def fake_generate(self, prompt, reference_images, output_clip_path, **kw):
        calls.append(len(calls) + 1)
        Path(output_clip_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_clip_path).write_bytes(f"TAKE{len(calls)}".encode())
        return {"success": True, "output_path": str(output_clip_path)}

    monkeypatch.setattr(qd.MuseBrowserWorker, "generate_shot", fake_generate)
    monkeypatch.setattr(qd.FilmQCEngine, "validate_shot_preflight", staticmethod(lambda s, p=None: (True, [])))
    monkeypatch.setattr(qd.FilmQCEngine, "evaluate_generated_clip",
                        staticmethod(lambda *a, **k: {"verdict": "REJECT", "defects": ["bad"]}))
    if quarantine_fails:
        monkeypatch.setattr(qd.QueueDispatcher, "_quarantine_rejected_clip", staticmethod(lambda clip: None))
    return mgr, pm, pid, calls


def test_failed_quarantine_stops_the_shot_and_the_next_attempt_never_overwrites(tmp_path: Path, monkeypatch):
    mgr, pm, pid, calls = _dispatch_project(tmp_path, monkeypatch, quarantine_fails=True)

    async def scenario():
        d = qd.QueueDispatcher(mgr, pm)
        assert (await d.start(pid, concurrency=1, simulate=False))["success"]
        for _ in range(40):  # long enough for several 1.5 s dispatch ticks: a requeue would show up as call #2
            await asyncio.sleep(0.25)
        await d.stop()

    asyncio.run(scenario())
    shot = pm.get_project(pid)["shots"][0]
    assert calls == [1], f"the shot was retried after a failed quarantine: {calls}"
    assert shot["status"] == "FAILED" and "CLIP_PRESERVATION_FAILED" in shot["error"]
    kept = list((tmp_path / "projects").rglob("clips/*.mp4"))
    assert [p.read_bytes() for p in kept] == [b"TAKE1"], "the take that could not be quarantined was overwritten"


def test_successful_quarantine_gives_every_take_its_own_file(tmp_path: Path, monkeypatch):
    mgr, pm, pid, calls = _dispatch_project(tmp_path, monkeypatch, quarantine_fails=False)

    async def scenario():
        d = qd.QueueDispatcher(mgr, pm)
        assert (await d.start(pid, concurrency=1, simulate=False))["success"]
        for _ in range(80):
            await asyncio.sleep(0.25)
            if len(calls) >= 2 and not d._active_workers:
                break
        await d.stop()

    asyncio.run(scenario())
    assert len(calls) >= 2
    saved = sorted(p.read_bytes() for p in (tmp_path / "projects").rglob("qc_rejected/*.mp4"))
    assert saved[:2] == [b"TAKE1", b"TAKE2"], "a retried take replaced an earlier quarantined one"


# ---- 4. the video unpacker reads the CURRENT exclusion list ---------------------------------------------------------
def _video_zip(zp: Path, name: str, data: bytes):
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr(name, data)
        zf.writestr("batch_receipt.json", json.dumps({"shots": [
            {"shot_id": "S1", "output_file": name, "sha256": hashlib.sha256(data).hexdigest()}]}))


def test_unpack_batch_result_excludes_listed_names_and_fails_closed_on_a_bad_list(tmp_path: Path):
    data = b"V" * (BatchPackager.MIN_VIDEO_BYTES + 16)
    bdir = tmp_path / "batch"
    zp = tmp_path / "B1_result.zip"
    _video_zip(zp, "S1.mp4", data)
    ok = BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", expected_shot_ids=["S1"])
    assert ok["verified"] is True and "S1" in ok["verified_shots"]

    BatchPackager.record_integrity_failure(bdir, "S1.mp4")
    listed = BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", expected_shot_ids=["S1"])
    assert listed["verified"] is False and "S1" not in listed["verified_shots"]
    assert listed["integrity_failed_shots"] == ["S1"]
    assert (bdir / "verified_clips" / "S1.mp4").exists(), "an excluded clip must be kept, not deleted"

    (bdir / INTEGRITY_FAILED_FILE).write_text('{"clips": "S1.mp4"}', encoding="utf-8")  # malformed schema
    bad = BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", expected_shot_ids=["S1"])
    assert bad["verified"] is False and bad["verified_shots"] == {} and bad.get("integrity_list_unreadable") is True


# ---- 3. every `project_dir` path goes through the production guard ----------------------------------------------------
def test_project_dir_halt_paths_refuse_the_real_data_dir_and_afp(tmp_path: Path, monkeypatch):
    from muse_studio.core import send_halt

    monkeypatch.setenv("MUSE_HALT_FILE", str(tmp_path / "scratch_halt.json"))
    monkeypatch.setenv("AFP_STATE_DIR", str(tmp_path / "afp"))
    monkeypatch.delenv("AFP_HALT_FILE", raising=False)
    real_dir = Path(send_halt.__file__).resolve().parents[1] / "data"
    real_halt = real_dir / send_halt.HALT_FILE
    before = (real_halt.exists(), real_halt.read_bytes() if real_halt.exists() else None)
    for bad in (real_dir, Path.home() / ".afp"):
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.clear_halt(bad)
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.load_halt(bad)
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.publish_halt({"reason": "TEST"}, bad)
    assert not (tmp_path / "scratch_halt.json").exists(), "publish_halt wrote before the project path was checked"
    assert before == (real_halt.exists(), real_halt.read_bytes() if real_halt.exists() else None)
    # a scratch project dir still works end to end
    proj = tmp_path / "proj"
    proj.mkdir()
    send_halt.publish_halt({"reason": "TEST"}, proj)
    assert send_halt.load_halt(proj) is not None
    assert send_halt.clear_halt(proj) is not None and not (proj / send_halt.HALT_FILE).exists()
