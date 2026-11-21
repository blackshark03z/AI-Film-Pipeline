"""Codex review r15b: one regression test per confirmed finding (all stores are tmp dirs; never the real halt,
`~/.afp` or the real accounts.json)."""
import hashlib
import io
import json
import os
import threading
import zipfile
from pathlib import Path

import pytest

import muse_studio.cli as cli
import muse_studio.core.config as config
import muse_studio.core.queue_dispatcher as qd
from muse_studio.core import send_halt
from muse_studio.core.account_manager import AccountManager
from muse_studio.core.batch_packager import (
    INTEGRITY_FAILED_FILE, BatchPackager, IntegrityUnpersistedError)
from muse_studio.core.autoprod_orchestrator import _load_render_checkpoint, _render_fingerprint
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine, kf_result_image
from muse_studio.tests.test_lane_review_r2 import _make_accounts
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project
from muse_studio.tests.test_review6_fixes import _audit
from muse_studio.tests.test_review7_fixes import _two_take_audit

BIG = 200 * 1024


@pytest.fixture(autouse=True)
def _temp_lease_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path / "lane_leases.json"))


def _png(seed: int = 0) -> bytes:
    from PIL import Image
    raw = hashlib.sha256(str(seed).encode()).digest() * (256 * 256 * 3 // 32 + 1)
    buf = io.BytesIO()
    Image.frombytes("RGB", (256, 256), os.urandom(256 * 256 * 3)).save(buf, "PNG")
    del raw
    return buf.getvalue()


# ---- 1. ensure_directories() never writes accounts.json ---------------------------------------------------------
def test_ensure_directories_does_not_create_accounts_file(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "PROFILES_DIR", data / "profiles")
    monkeypatch.setattr(config, "PROJECTS_DIR", data / "projects")
    monkeypatch.setattr(config, "OUTPUT_DIR", data / "output")
    monkeypatch.setattr(config, "ACCOUNTS_FILE", data / "accounts.json")
    config.ensure_directories()
    assert data.is_dir() and not (data / "accounts.json").exists(), "an unlocked write could wipe accounts"
    mgr = AccountManager(storage_file=data / "accounts.json", profiles_dir=data / "profiles")
    assert (data / "accounts.json").exists() and mgr.list_accounts() == []


# ---- 2. bulk import passes only supplied fields; increment is atomic ---------------------------------------------
def test_bulk_import_does_not_overwrite_fields_it_did_not_supply(tmp_path: Path):
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    mgr.bulk_import_accounts("t1@example.test|inv1|pw-old|cookie-old|proxy-old")
    acc = mgr.get_account_by_email("t1@example.test")
    # A concurrent relogin saves a newer cookie and proxy after the importer read its copy.
    mgr.update_account(acc["id"], raw_cookie="cookie-new", proxy="proxy-new")
    mgr.bulk_import_accounts("t1@example.test|inv2")  # supplies only the invite code
    after = mgr.get_account(acc["id"])
    assert after["invite_code"] == "inv2"
    assert after["raw_cookie"] == "cookie-new" and after["proxy"] == "proxy-new" and after["password"] == "pw-old"
    assert after["status"] == "UNCHECKED"


def test_increment_account_is_atomic_under_threads(tmp_path: Path):
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    aid = mgr.add_account(name="Counter")["id"]
    n_threads, per = 6, 8

    def work():
        for _ in range(per):
            mgr.increment_account(aid, "total_rendered", 1)

    ts = [threading.Thread(target=work) for _ in range(n_threads)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert int(mgr.get_account(aid)["total_rendered"]) == n_threads * per


# ---- 2b. browser_worker counts a render atomically (no read-then-write of total_rendered) ----------------------------
def test_browser_worker_render_count_loses_no_concurrent_increment(tmp_path: Path):
    from muse_studio.core.browser_worker import MuseBrowserWorker

    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    aid = mgr.add_account(name="Worker")["id"]
    # two workers on one account, both holding the same stale snapshot (total_rendered == 0): the old
    # `account_data["total_rendered"] + 1` write-back made the second one overwrite the first
    w1, w2 = MuseBrowserWorker(aid, mgr), MuseBrowserWorker(aid, mgr)
    w1._record_render()
    w2._record_render()
    assert int(mgr.get_account(aid)["total_rendered"]) == 2
    assert mgr.get_account(aid).get("last_used")

    n_threads, per = 4, 6
    gate = threading.Barrier(n_threads)

    def work(w):
        gate.wait()
        for _ in range(per):
            w._record_render()

    ts = [threading.Thread(target=work, args=(MuseBrowserWorker(aid, mgr),)) for _ in range(n_threads)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert int(mgr.get_account(aid)["total_rendered"]) == 2 + n_threads * per


# ---- 3. _send_allowed refuses after an integrity stop ------------------------------------------------------------
def test_send_allowed_false_after_integrity_stop(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 1)
    engine = ParallelPoolEngine(account_manager=mgr, sync_ui=False)
    assert engine._send_allowed(ids[0]) is True
    engine._integrity_stop.append({"batch_id": "B", "clips": ["x.mp4"]})
    assert engine._send_allowed(ids[0]) is False


# ---- 4. promote-take / assemble / checkpoint re-check the CURRENT exclusion list ---------------------------------
def test_promote_take_refuses_an_excluded_clip_and_deletes_nothing(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, c1, c2 = _two_take_audit(proj, monkeypatch, capsys)
    BatchPackager.record_integrity_failure(c2.parent.parent, c2.name)  # excluded AFTER the audit was written
    rc = cli.main(["promote-take", str(proj), sid, "2"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["error"] == "CLIP_INTEGRITY_FAILED"
    assert c2.exists() and c1.exists(), "promote-take deleted a received clip"
    canonical = proj / "verified_clips" / f"{sid}.mp4"  # qc-audit already put the best take (A) there
    assert not canonical.exists() or canonical.read_bytes()[:1] == b"A", "an excluded clip reached the canonical slot"


def test_assemble_drops_clips_excluded_after_the_audit(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, _, c2 = _two_take_audit(proj, monkeypatch, capsys)
    audit = _audit(proj)
    audit["passed_clips"] = {sid: str(c2)}
    (proj / "qc_audit_report.json").write_text(json.dumps(audit), encoding="utf-8")
    BatchPackager.record_integrity_failure(c2.parent.parent, c2.name)
    rc = cli.main(["assemble", str(proj)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["error"] == "NO_QC_PASSED_CLIPS" and c2.exists()


def test_render_checkpoint_does_not_revive_an_excluded_clip(tmp_path: Path):
    bdir = tmp_path / "proj" / "BATCHES_V2" / "B1"
    (bdir / "verified_clips").mkdir(parents=True)
    clip = bdir / "verified_clips" / "shot_01.mp4"
    clip.write_bytes(b"x" * 64)
    shot = {"shot_id": "S1", "compiled_prompt": "p"}
    audit = tmp_path / "qc_audit_report.json"
    audit.write_text(json.dumps({"passed_clips": {"S1": str(clip)}, "per_shot_qc": {"S1": {"verdict": "PASS"}},
                                 "render_fingerprints": {"S1": _render_fingerprint(shot, False)}}), encoding="utf-8")
    assert _load_render_checkpoint(audit, {"S1": shot}, False)[0] == {"S1": str(clip)}
    BatchPackager.record_integrity_failure(bdir, clip.name)
    assert _load_render_checkpoint(audit, {"S1": shot}, False)[0] == {}
    assert clip.exists()


# ---- 5. keyframe results are checked against kf_receipt.json and the exclusion list -------------------------------
def _kf_zip(zp: Path, kf_id: str, img: bytes, sha: str):
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr(f"{kf_id}.png", img)
        zf.writestr("kf_receipt.json", json.dumps({"keyframes": [
            {"kf_id": kf_id, "output_file": f"{kf_id}.png", "sha256": sha}]}))


def test_unpack_keyframe_result_receipt_sha_mismatch_is_not_verified_and_kept(tmp_path: Path):
    img = _png(1)
    zp = tmp_path / "B_kf_result.zip"
    _kf_zip(zp, "kf_a", img, "0" * 64)
    ex = tmp_path / "batch" / "keyframes"
    res = BatchPackager.unpack_keyframe_result(zp, ex, expected_kf_ids=["kf_a"])
    assert res["verified"] is False and res["integrity_failed_keyframes"] == ["kf_a"] and "kf_a" not in res["keyframes"]
    assert (ex / "kf_a.png").exists(), "the received keyframe was deleted"
    ok, names = BatchPackager.read_integrity_failed(ex.parent)
    assert ok and names == {"kf_a.png"}
    # Next unpack: the file is now excluded by name, even with a (now matching) receipt.
    _kf_zip(zp, "kf_a", img, hashlib.sha256(img).hexdigest())
    res2 = BatchPackager.unpack_keyframe_result(zp, ex, expected_kf_ids=["kf_a"])
    assert res2["verified"] is False and res2["integrity_failed_keyframes"] == ["kf_a"]


def test_unpack_keyframe_result_matching_receipt_verifies(tmp_path: Path):
    img = _png(2)
    zp = tmp_path / "B_kf_result.zip"
    _kf_zip(zp, "kf_b", img, hashlib.sha256(img).hexdigest())
    res = BatchPackager.unpack_keyframe_result(zp, tmp_path / "batch" / "keyframes", expected_kf_ids=["kf_b"])
    assert res["verified"] is True and "kf_b" in res["keyframes"]


def test_kf_result_image_rejects_receipt_mismatch_and_excluded_names(tmp_path: Path):
    img = _png(3)
    out = tmp_path / "batch"
    out.mkdir()
    zp = out / "B1_kf_result.zip"
    _kf_zip(zp, "kf_c", img, "f" * 64)
    assert kf_result_image(out, "B1", "kf_c") is None, "a receipt SHA mismatch counted as evidence"
    _kf_zip(zp, "kf_c", img, hashlib.sha256(img).hexdigest())
    assert kf_result_image(out, "B1", "kf_c")["sha256"] == hashlib.sha256(img).hexdigest()
    BatchPackager.record_integrity_failure(out, "kf_c.png")
    assert kf_result_image(out, "B1", "kf_c") is None, "an excluded keyframe counted as evidence"
    (out / INTEGRITY_FAILED_FILE).write_text("null", encoding="utf-8")
    assert kf_result_image(out, "B1", "kf_c") is None, "an unreadable exclusion list must fail closed"


# ---- 6. a QC reject quarantines the clip, never unlinks it ---------------------------------------------------------
def test_qc_reject_moves_clip_to_quarantine(tmp_path: Path):
    clip = tmp_path / "S1.mp4"
    clip.write_bytes(b"clip-bytes")
    dest = qd.QueueDispatcher._quarantine_rejected_clip(clip)
    assert dest is not None and not clip.exists() and dest.read_bytes() == b"clip-bytes"
    assert dest.parent == tmp_path / "qc_rejected" and dest.name.startswith("S1_") and dest.suffix == ".mp4"
    clip.write_bytes(b"second")  # a second reject of the same shot never overwrites the first
    dest2 = qd.QueueDispatcher._quarantine_rejected_clip(clip)
    assert dest2 != dest and dest.read_bytes() == b"clip-bytes" and dest2.read_bytes() == b"second"


def test_qc_reject_failed_move_leaves_the_file(tmp_path: Path, monkeypatch):
    clip = tmp_path / "S2.mp4"
    clip.write_bytes(b"keep-me")

    def boom(*a, **k):
        raise PermissionError("simulated: file held open")

    monkeypatch.setattr(qd.shutil, "move", boom)
    assert qd.QueueDispatcher._quarantine_rejected_clip(clip) is None
    assert clip.read_bytes() == b"keep-me"


def test_dispatcher_source_never_unlinks_a_rejected_clip():
    src = Path(qd.__file__).read_text(encoding="utf-8")
    reject = src[src.index('qc_result["verdict"] == "REJECT"'):src.index("raise GenerationFailedException(f\"Hậu kiểm")]
    assert ".unlink(" not in reject and "_quarantine_rejected_clip" in reject


# ---- 7. an INTEGRITY_UNPERSISTED ledger entry stays blocking until released MANUAL ----------------------------------
def test_integrity_unpersisted_entry_is_not_auto_released_next_run(tmp_path: Path, monkeypatch):
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
            exc.submitted = True
            raise exc

    qc = lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}}  # noqa: E731
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False, qc_evaluator=qc)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=4)
    res = engine.run_videos(project_dir=proj, max_accounts=2, max_rounds=2, simulate=False)
    assert res["status"] == "INTEGRITY_UNPERSISTED"
    ledger_path = proj / "unconfirmed_submissions.json"
    entries = json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]
    assert entries and all(e.get("integrity_failure") == "INTEGRITY_UNPERSISTED" for e in entries)
    # The batch dir now holds a clip (as it does after a partial unpack): the old logic released it as RESULT_RECEIVED.
    for e in entries:
        vc = proj / "BATCHES_V2" / e["batch_id"] / "verified_clips"
        vc.mkdir(parents=True, exist_ok=True)
        (vc / "shot_01.mp4").write_bytes(b"x" * 64)
    engine2 = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False, qc_evaluator=qc)
    sent.clear()
    engine2.run_videos(project_dir=proj, max_accounts=2, max_rounds=1, simulate=False)
    after = json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]
    flagged = {e["batch_id"]: e for e in after if e.get("integrity_failure")}
    assert flagged and all(e["status"] != "RELEASED" for e in flagged.values()), "auto-released after integrity stop"
    assert not any(e.get("reason") == "RESULT_RECEIVED" for e in flagged.values())
    # Only an explicit manual release frees it.
    engine3 = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False, qc_evaluator=qc)
    engine3.run_videos(project_dir=proj, max_accounts=2, max_rounds=1, simulate=False, release_unconfirmed=True)
    final = json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]
    assert any(e.get("reason") == "MANUAL" for e in final if e.get("integrity_failure"))


# ---- 8. one integrity-list reader, fail closed (null included) ------------------------------------------------------
@pytest.mark.parametrize("payload,expect_ok,expect_names", [
    (None, True, set()),  # no file
    ('{"clips": ["a.mp4", "b.mp4"]}', True, {"a.mp4", "b.mp4"}),
    ("null", False, set()),
    ("[]", False, set()),
    ('{"clips": null}', False, set()),
    ('{"clips": ["a.mp4", 3]}', False, set()),
    ('{"clips": "a.mp4"}', False, set()),
    ("{not json", False, set()),
])
def test_read_integrity_failed_validates_schema_and_fails_closed(tmp_path: Path, payload, expect_ok, expect_names):
    if payload is not None:
        (tmp_path / INTEGRITY_FAILED_FILE).write_text(payload, encoding="utf-8")
    assert BatchPackager.read_integrity_failed(tmp_path) == (expect_ok, expect_names)
    assert not hasattr(BatchPackager, "integrity_failed_unreadable") and not hasattr(BatchPackager, "integrity_failed_names")


def test_record_integrity_failure_refuses_to_overwrite_an_unreadable_list(tmp_path: Path):
    (tmp_path / INTEGRITY_FAILED_FILE).write_text("null", encoding="utf-8")
    with pytest.raises(OSError):
        BatchPackager.record_integrity_failure(tmp_path, "a.mp4")
    assert (tmp_path / INTEGRITY_FAILED_FILE).read_text(encoding="utf-8") == "null"


# ---- 9. the pytest guard covers every signal / clear path ----------------------------------------------------------
def test_send_halt_guard_refuses_real_halt_and_afp_paths_under_pytest(tmp_path: Path, monkeypatch):
    afp_real = Path.home() / ".afp"
    real_halt = Path(send_halt.__file__).resolve().parents[1] / "data" / send_halt.HALT_FILE
    # MUSE_HALT_FILE inside ~/.afp, or the real Muse halt itself (or its lock).
    for bad in (afp_real / "muse_halt.json", real_halt, Path(str(real_halt) + ".lock")):
        monkeypatch.setenv("MUSE_HALT_FILE", str(bad))
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.halt_path()
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.send_stop()
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.clear_halt()
    monkeypatch.setenv("MUSE_HALT_FILE", str(tmp_path / "muse_halt.json"))
    monkeypatch.setenv("AFP_STATE_DIR", str(tmp_path / "afp"))
    # AFP_HALT_FILE was unguarded: pointing into ~/.afp or at the real halt is refused before any read.
    for bad in (afp_real / "halt.json", real_halt):
        monkeypatch.setenv("AFP_HALT_FILE", str(bad))
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.afp_halt_file()
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.send_stop()
    # A scratch AFP_HALT_FILE still works as a stop signal.
    scratch = tmp_path / "afp_halt.json"
    scratch.write_text(json.dumps({"reason": "TEST"}), encoding="utf-8")
    monkeypatch.setenv("AFP_HALT_FILE", str(scratch))
    sig = send_halt.send_stop()
    assert sig is not None and sig["signal"] == "AFP_HALT"


# ---- 10. run-pool returns exit 5 on INTEGRITY_UNPERSISTED; the contract documents it --------------------------------
def test_run_pool_returns_5_on_integrity_unpersisted(tmp_path: Path, monkeypatch, capsys):
    class FakeEngine:
        def __init__(self, *a, **k):
            pass

        def run_videos(self, **k):
            return {"status": "INTEGRITY_UNPERSISTED", "passed_count": 0, "total_shots": 3,
                    "remaining_shot_ids": ["a", "b", "c"]}

    monkeypatch.setattr(cli, "ParallelPoolEngine", FakeEngine)
    monkeypatch.setattr(cli, "AccountManager", lambda *a, **k: object())
    args = cli.build_parser().parse_args(["run-pool", str(tmp_path), "--simulate"])
    assert args.func(args) == 5
    assert "INTEGRITY_UNPERSISTED" in capsys.readouterr().err


def test_lane_contract_documents_exit_5():
    doc = Path(__file__).resolve().parents[2] / "docs" / "AFP_MUSE_LANE_CONTRACT.md"
    rows = [ln for ln in doc.read_text(encoding="utf-8").splitlines() if ln.startswith("| `5` |")]
    assert rows and "INTEGRITY_UNPERSISTED" in rows[0]
