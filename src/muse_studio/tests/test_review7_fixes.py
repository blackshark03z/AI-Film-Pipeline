"""Regression tests for review 7 of the multi-take / unconfirmed-submission code (one group per finding)."""
import asyncio
import hashlib
import json
import threading
import time
import zipfile
from pathlib import Path

import pytest

import muse_studio.cli as cli
from muse_studio.core import autoprod_orchestrator as ao
from muse_studio.core import headless_muse_client as hmc
from muse_studio.core.autoprod_orchestrator import SessionConflictError, SessionLock, _render_fingerprint
from muse_studio.core.batch_packager import BatchPackager
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.headless_muse_client import HeadlessMuseClient
from muse_studio.core.parallel_pool_engine import UNCONFIRMED_FILE
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project
from muse_studio.tests.test_review6_fixes import (
    BIG, _FakeAccounts, _FakePage, _audit, _fake_eval, _make_batch, _shots, _take_engine, _video_engine_pass,
)


def _ledger(proj: Path):
    return json.loads((proj / UNCONFIRMED_FILE).read_text(encoding="utf-8"))["entries"]


def _write_ledger(proj: Path, entries):
    (proj / UNCONFIRMED_FILE).write_text(json.dumps({"entries": entries}), encoding="utf-8")


# ---- r7#1: a SHA-mismatched clip is quarantined at unpack and never audited -----------------------------------------
def test_sha_mismatch_clip_is_quarantined_and_never_audited(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    s1, s2 = sorted(_shots(proj))
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
    res = BatchPackager.unpack_batch_result(zp, bdir / "verified_clips", handoff_manifest_path=man)
    assert s2 in res["integrity_failed_shots"] and s2 not in res["verified_shots"]
    assert not (bdir / "verified_clips" / "shot_02.mp4").exists(), "the bad clip stayed among the candidates"
    assert (bdir / "integrity_failed" / "shot_02.mp4").exists(), "the bad clip must be kept for inspection"

    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"GOOD": 70.0, "BAD": 99.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    assert s1 in audit["passed_clips"]
    assert s2 not in audit["passed_clips"], "qc-audit re-admitted an integrity-failed clip"


# ---- r7#2: a bookkeeping failure after submit keeps the original exception and its `submitted` flag -------------------
@pytest.mark.parametrize("exc_cls", [hmc.QuotaExceededException, hmc.SessionInvalidException])
def test_account_update_failure_keeps_submitted_flag(tmp_path: Path, monkeypatch, exc_cls):
    real_sleep = asyncio.sleep

    async def fast_sleep(*a, **k):
        await real_sleep(0)

    class BrokenAccounts(_FakeAccounts):
        def update_account(self, *a, **k):
            raise OSError("accounts.json is locked")

    monkeypatch.setattr(hmc.asyncio, "sleep", fast_sleep)
    page = _FakePage()
    client = HeadlessMuseClient(BrokenAccounts())
    client.enable_warm_pool(True)
    client._warm_sessions["acc_x"] = (None, None, page)

    async def noop(*a, **k):
        return None

    async def ready(*a, **k):
        return True

    async def page_errors(cls, p, *a, **k):
        if "press:Enter" in p.events:
            raise exc_cls("out of usage after send")

    monkeypatch.setattr(HeadlessMuseClient, "_start_fresh_chat", staticmethod(noop))
    monkeypatch.setattr(HeadlessMuseClient, "_check_page_errors", classmethod(page_errors))
    monkeypatch.setattr(HeadlessMuseClient, "_is_chat_ready", staticmethod(ready))
    zp = tmp_path / "h.zip"
    zp.write_bytes(b"x")
    with pytest.raises(BaseException) as ei:
        asyncio.run(client._dispatch_zip_and_wait_result("acc_x", zp, "msg", tmp_path / "r.zip", timeout_seconds=5))
    assert "press:Enter" in page.events
    assert isinstance(ei.value, exc_cls), f"the original exception was replaced by {ei.value!r}"
    assert getattr(ei.value, "submitted", False), "the submitted flag was lost"


# ---- r7#3: the ledger holds a pending entry before dispatch; a pending entry or an old in-flight batch blocks ----------
def test_pending_entry_is_persisted_before_dispatch(tmp_path: Path):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    seen = []

    def behaviour(n):
        ledger = proj / UNCONFIRMED_FILE
        entries = json.loads(ledger.read_text(encoding="utf-8"))["entries"] if ledger.exists() else []
        seen.append({e["shot_id"]: e.get("status") for e in entries})

    engine, calls = _video_engine_pass(tmp_path, behaviour)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    assert res["status"] == "COMPLETED"
    assert seen and set(seen[0]) == set(calls[0][1]), f"no durable record before the send: {seen}"
    assert set(seen[0].values()) == {"PENDING_SEND"}
    after = _ledger(proj)
    assert after and all(e["status"] == "RESOLVED" for e in after), after
    assert res["unconfirmed_submissions"] == []


def test_pending_entry_left_by_a_crash_blocks_resend(tmp_path: Path):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    sid, shot = sorted(_shots(proj).items())[0]
    _write_ledger(proj, [{"shot_id": sid, "batch_id": "POOL_CRASHED_R01_B01", "take": 1, "status": "PENDING_SEND",
                          "submitted_epoch": time.time(), "fingerprint": _render_fingerprint(shot, False)}])
    engine, calls = _video_engine_pass(tmp_path, lambda n: None)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    assert sid not in {s for _, sids in calls for s in sids}, "a shot whose send may be in flight was resent"
    assert sid in res["submitted_unconfirmed_shot_ids"]


def test_legacy_project_with_inflight_batch_dir_blocks_resend(tmp_path: Path):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    s1, s2 = sorted(_shots(proj))
    bid = "POOL_101010_R01_B01"
    bdir = proj / "BATCHES_V2" / bid
    bdir.mkdir(parents=True)
    (bdir / f"{bid}_manifest.json").write_text(
        json.dumps({"shots": [{"slot_id": "shot_01", "shot_id": s1}]}), encoding="utf-8")
    assert not (proj / UNCONFIRMED_FILE).exists()
    engine, calls = _video_engine_pass(tmp_path, lambda n: None)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    sent = {s for _, sids in calls for s in sids}
    assert s1 not in sent, "an old-code batch with no result was resent"
    assert s2 in sent
    blocked = {e["shot_id"]: e for e in res["unconfirmed_submissions"]}
    assert s1 in blocked and blocked[s1]["batch_id"] == bid


# ---- r7#4: TTL expiry never releases by itself; release is explicit (all or per shot); history is kept ----------------
def test_expired_entry_needs_reconcile_and_stays_blocking(tmp_path: Path):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    _write_ledger(proj, [{"shot_id": sid, "batch_id": "B", "take": 1, "submitted_epoch": time.time() - 3 * 3600,
                          "fingerprint": _render_fingerprint(shot, False)}])
    engine, calls = _video_engine_pass(tmp_path, lambda n: None)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, unconfirmed_ttl_min=120)
    assert calls == [], "an expired, unreconciled submission was resent"
    assert res["unconfirmed_submissions"][0]["status"] == "EXPIRED_NEEDS_RECONCILE"
    assert [e["shot_id"] for e in res["unconfirmed_expired"]] == [sid]
    assert _ledger(proj)[0]["status"] == "EXPIRED_NEEDS_RECONCILE", "the expired entry was dropped from the ledger"


def test_release_unconfirmed_per_shot_keeps_history(tmp_path: Path):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    shots = sorted(_shots(proj).items())
    _write_ledger(proj, [{"shot_id": sid, "batch_id": "B", "take": 1, "submitted_epoch": time.time(),
                          "fingerprint": _render_fingerprint(sh, False)} for sid, sh in shots])
    (s1, _), (s2, _) = shots
    engine, calls = _video_engine_pass(tmp_path, lambda n: None)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, release_unconfirmed=[s1])
    assert {s for _, sids in calls for s in sids} == {s1}, "per-shot release sent the wrong shots"
    assert [e["reason"] for e in res["unconfirmed_released"]] == ["MANUAL"]
    by_shot = {}
    for e in _ledger(proj):
        by_shot.setdefault(e["shot_id"], []).append(e)
    assert by_shot[s1][0]["status"] == "RELEASED" and by_shot[s1][0]["reason"] == "MANUAL"
    assert by_shot[s2][0]["status"] == "UNCONFIRMED"


def test_pool_runner_release_unconfirmed_shot_flag():
    from muse_studio.pool_runner import build_parser

    ns = build_parser().parse_args(["videos", "P", "--release-unconfirmed-shot", "S1",
                                    "--release-unconfirmed-shot", "S2"])
    assert ns.release_unconfirmed_shot == ["S1", "S2"] and not ns.release_unconfirmed


# ---- r7#5: the project lock is a real OS lock and every project-state writer takes it -------------------------------
def test_session_lock_is_exclusive_under_race(monkeypatch, tmp_path: Path):
    barrier = threading.Barrier(2, timeout=2)

    def racing_write(path, data):
        # Both sessions passed the "is there a lock?" check before either writes (the window a real race hits).
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(ao, "_write_json_atomic", racing_write)
    wins, locks = [], []

    def grab(tag):
        lk = SessionLock(tmp_path, session_tag=tag)
        try:
            lk.acquire()
            wins.append(tag)
            locks.append(lk)
        except SessionConflictError:
            pass

    threads = [threading.Thread(target=grab, args=(t,)) for t in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    for lk in locks:
        lk.release()
    assert len(wins) == 1, f"two sessions acquired the project lock: {wins}"


@pytest.mark.parametrize("argv", [["qc-audit"], ["promote-take", "_SID_", "1"]])
def test_project_state_cli_writers_take_the_project_lock(tmp_path: Path, monkeypatch, capsys, argv):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    _make_batch(proj, "POOL_A_R01_B01", sid, b"A", fingerprint=_render_fingerprint(shot, False))
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"A": 70.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    before = (proj / "qc_audit_report.json").read_bytes()
    argv = [a.replace("_SID_", sid) for a in argv]
    with SessionLock(proj, session_tag="pool_videos"):
        rc = cli.main([argv[0], str(proj), *argv[1:]])
    out = capsys.readouterr().out
    assert rc == 3, f"{argv[0]} ran while another session held the project ({rc}): {out[-300:]}"
    assert (proj / "qc_audit_report.json").read_bytes() == before


# ---- r7#6: batch ids are unique per invocation and an existing batch's sidecar is never overwritten ------------------
def test_batch_ids_unique_across_invocations_in_same_second(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(time, "strftime", lambda *a, **k: "120000")
    engine, calls = _take_engine(tmp_path, lambda b, s: None)  # every take rejected: the shot is sent again
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    first = {p.parent.name: p.read_bytes() for p in (proj / "BATCHES_V2").glob("*/render_fingerprints.json")}
    mp = proj / "shots_manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    manifest["shots"][0]["compiled_prompt"] += " Restaged."
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    after = {p.parent.name: p.read_bytes() for p in (proj / "BATCHES_V2").glob("*/render_fingerprints.json")}
    assert len(after) == 2, f"two invocations shared a batch dir: {sorted(after)}"
    for name, data in first.items():
        assert after[name] == data, "the sidecar of an earlier batch was overwritten"


# ---- r7#7/#8/#10: promote-take source integrity, kept choice, legacy refusal ------------------------------------------
def _two_take_audit(proj: Path, monkeypatch, capsys, fingerprint=True):
    sid, shot = next(iter(_shots(proj).items()))
    fp = _render_fingerprint(shot, False) if fingerprint else None
    c1 = _make_batch(proj, "POOL_P_R01_B01_T1", sid, b"A", fingerprint=fp)
    c2 = _make_batch(proj, "POOL_P_R01_B02_T2", sid, b"B", fingerprint=fp)
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"A": 80.0, "B": 40.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    return sid, c1, c2


def test_promote_take_never_substitutes_a_different_clip(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, c1, _ = _two_take_audit(proj, monkeypatch, capsys)
    assert cli.main(["qc-audit", str(proj)]) == 0  # the canonical copy of take 1 is now a candidate too
    capsys.readouterr()
    assert cli.main(["promote-take", str(proj), sid, "2"]) == 0
    capsys.readouterr()
    canonical = proj / "verified_clips" / f"{sid}.mp4"
    assert canonical.read_bytes()[:1] == b"B"
    c1.unlink()  # take 1's immutable source is gone
    rc = cli.main(["promote-take", str(proj), sid, "1"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["error"] == "CLIP_MISSING", out
    assert canonical.read_bytes()[:1] == b"B"


def test_qc_audit_keeps_promoted_take(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, _, c2 = _two_take_audit(proj, monkeypatch, capsys)
    assert cli.main(["promote-take", str(proj), sid, "2"]) == 0
    capsys.readouterr()
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    rec = _audit(proj)["per_shot_qc"][sid]
    assert rec["take"] == 2 and rec.get("selected_by") == "promote-take", "a later audit dropped the promoted take"
    assert Path(rec["clip_path"]) == c2
    assert (proj / "verified_clips" / f"{sid}.mp4").read_bytes()[:1] == b"B"


def test_qc_audit_drops_promoted_take_once_it_no_longer_passes(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, _, _ = _two_take_audit(proj, monkeypatch, capsys)
    assert cli.main(["promote-take", str(proj), sid, "2"]) == 0
    capsys.readouterr()
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"A": 80.0, "B": None}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    rec = _audit(proj)["per_shot_qc"][sid]
    assert rec["take"] == 1 and rec.get("selected_by") != "promote-take"


def test_promote_take_refuses_legacy_take_without_fingerprint(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, _, _ = _two_take_audit(proj, monkeypatch, capsys, fingerprint=False)
    before = (proj / "qc_audit_report.json").read_bytes()
    rc = cli.main(["promote-take", str(proj), sid, "2"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["error"] == "TAKE_UNPROVEN", out
    assert "videos" in out["message"]
    assert (proj / "qc_audit_report.json").read_bytes() == before


# ---- r7#9: every candidate has its own strip; promote never reuses the mutable canonical strip ----------------------
def test_single_take_candidate_has_its_own_strip(tmp_path: Path):
    engine, _ = _take_engine(tmp_path, lambda b, s: 60.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    sid = next(iter(_shots(proj)))
    cand = _audit(proj)["per_shot_qc"][sid]["candidates"][0]
    canonical = proj / "qc_strips" / f"{sid}_strip.jpg"
    assert cand["strip_path"] and Path(cand["strip_path"]) != canonical, "the candidate strip is the mutable canonical"
    assert Path(cand["strip_path"]).read_bytes().endswith(cand["batch_id"].encode())


def test_promote_take_does_not_reuse_canonical_strip(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, _, _ = _two_take_audit(proj, monkeypatch, capsys)
    canonical_strip = proj / "qc_strips" / f"{sid}_strip.jpg"
    canonical_strip.write_bytes(b"strip-of-take-1")
    ap = proj / "qc_audit_report.json"
    audit = json.loads(ap.read_text(encoding="utf-8"))
    for c in audit["per_shot_qc"][sid]["candidates"]:
        c["strip_path"] = str(canonical_strip)  # an older record pointing every candidate at the canonical strip
    ap.write_text(json.dumps(audit), encoding="utf-8")
    monkeypatch.setattr(FilmQCEngine, "generate_qc_strip", staticmethod(
        lambda clip, out, **kw: (Path(out).write_bytes(b"regen:" + Path(clip).read_bytes()[:1]), Path(out))[1]))
    assert cli.main(["promote-take", str(proj), sid, "2"]) == 0
    capsys.readouterr()
    assert canonical_strip.read_bytes() == b"regen:B", "promote reused another take's strip"
