"""Regression tests for review 6 of multi-take + lane code (one test group per finding)."""
import asyncio
import hashlib
import json
import time
import zipfile
from pathlib import Path

import pytest

import muse_studio.cli as cli
from muse_studio.core import headless_muse_client as hmc
from muse_studio.core.autoprod_orchestrator import _render_fingerprint
from muse_studio.core.batch_packager import BatchPackager
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.headless_muse_client import HeadlessMuseClient
from muse_studio.core.lane_leases import LaneContext, LeaseRegistry
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine
from muse_studio.tests.test_lane_review_r2 import _make_accounts, _sent_shots, _submitted, _video_client_factory
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project

BIG = 110 * 1024  # qc-audit ignores candidates under 100 KB


def _manifest(proj: Path):
    return json.loads((proj / "shots_manifest.json").read_text(encoding="utf-8"))


def _shots(proj: Path):
    return {s["shot_id"]: s for s in _manifest(proj)["shots"]}


def _audit(proj: Path):
    return json.loads((proj / "qc_audit_report.json").read_text(encoding="utf-8"))


def _make_batch(proj: Path, bid: str, sid: str, payload: bytes, fingerprint=None) -> Path:
    """A BATCHES_V2 batch dir with one clip in slot shot_01 (and optionally the engine's fingerprint sidecar)."""
    bdir = proj / "BATCHES_V2" / bid
    vdir = bdir / "verified_clips"
    vdir.mkdir(parents=True, exist_ok=True)
    (bdir / f"{bid}_manifest.json").write_text(
        json.dumps({"shots": [{"slot_id": "shot_01", "shot_id": sid}]}), encoding="utf-8")
    clip = vdir / "shot_01.mp4"
    clip.write_bytes(payload + b"\x00" * BIG)
    if fingerprint is not None:
        (bdir / "render_fingerprints.json").write_text(
            json.dumps({"batch_id": bid, "shots": {sid: fingerprint}}), encoding="utf-8")
    return clip


def _fake_eval(scores):
    """Patch for FilmQCEngine.evaluate_generated_clip: score by the clip's leading tag (None = reject)."""
    def fake(clip_path, shot_spec=None, min_duration_s=3.0, strip_output_path=None, **kw):
        tag = Path(clip_path).read_bytes()[:8].rstrip(b"\x00").decode()
        score = scores.get(tag)
        if score is None:
            return {"verdict": "REJECT", "defects": ["BLUR"], "metrics": {"quality_score": 0.0}}
        return {"verdict": "PASS", "defects": [], "metrics": {"quality_score": score}}
    return staticmethod(fake)


# ---- finding 1: qc-audit never lets an old-design take win, fingerprint comes from the winner ----------------------
def test_qc_audit_old_design_take_never_wins(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    current = _render_fingerprint(shot, False)
    _make_batch(proj, "POOL_1_R01_B01", sid, b"OLD", fingerprint="OLD_DESIGN_FP")
    new_clip = _make_batch(proj, "POOL_2_R01_B01", sid, b"NEW", fingerprint=current)
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"OLD": 90.0, "NEW": 80.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    canonical = Path(audit["passed_clips"][sid])
    assert canonical.read_bytes()[:3] == b"NEW", "a take of the old design won the audit"
    assert audit["render_fingerprints"][sid] == current
    assert Path(audit["per_shot_qc"][sid]["clip_path"]) == new_clip


def test_qc_audit_only_old_design_takes_is_not_passed(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid = next(iter(_shots(proj)))
    _make_batch(proj, "POOL_1_R01_B01", sid, b"OLD", fingerprint="OLD_DESIGN_FP")
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"OLD": 90.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    assert sid not in audit["passed_clips"] and sid not in audit["render_fingerprints"]
    assert audit["failed_or_missing"][0]["reason"] == "STALE_RENDER"


def test_qc_audit_legacy_takes_without_fingerprints_still_audited(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid = next(iter(_shots(proj)))
    _make_batch(proj, "OLD_BATCH_01", sid, b"A")
    _make_batch(proj, "OLD_BATCH_02", sid, b"B")
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"A": 50.0, "B": 70.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    assert Path(audit["passed_clips"][sid]).read_bytes()[:1] == b"B"
    assert sid not in audit["render_fingerprints"], "an unproven clip must not get a fingerprint"


def test_engine_writes_fingerprint_sidecar_per_batch(tmp_path: Path):
    engine, calls = _take_engine(tmp_path, lambda b, s: 50.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=2)
    shots = _shots(proj)
    sidecars = sorted((proj / "BATCHES_V2").glob("*/render_fingerprints.json"))
    assert len(sidecars) == len(calls) and sidecars
    for sc in sidecars:
        data = json.loads(sc.read_text(encoding="utf-8"))
        assert data["shots"] == {sid: _render_fingerprint(shots[sid], False) for sid in data["shots"]}


# ---- finding 8: qc-audit keeps winner metadata and per-take results ---------------------------------------------------
def test_qc_audit_keeps_take_metadata_and_candidates(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    current = _render_fingerprint(shot, False)
    c1 = _make_batch(proj, "POOL_9_R01_B01_T1", sid, b"T1", fingerprint=current)
    c2 = _make_batch(proj, "POOL_9_R01_B02_T2", sid, b"T2", fingerprint=current)
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"T1": 40.0, "T2": None}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    rec = _audit(proj)["per_shot_qc"][sid]
    assert rec["take"] == 1 and Path(rec["clip_path"]) == c1 and rec["verdict"] == "PASS"
    by_take = {c["take"]: c for c in rec["candidates"]}
    assert set(by_take) == {1, 2}
    assert Path(by_take[2]["clip_path"]) == c2 and by_take[2]["verdict"] == "REJECT"
    assert by_take[1]["fingerprint_status"] == "current"


# ---- finding 2: a lease lost during login/upload aborts before the submit keystroke -----------------------------------
class _FakeLocator:
    def __init__(self, page):
        self.page = page
        self.first = self

    async def set_input_files(self, path):
        self.page.events.append("upload")
        if self.page.on_upload:
            self.page.on_upload()

    async def click(self, *a, **k):
        pass

    async def fill(self, text):
        self.page.events.append("fill")


class _FakeKeyboard:
    def __init__(self, page):
        self.page = page

    async def press(self, key):
        self.page.events.append(f"press:{key}")


class _FakePage:
    def __init__(self, on_upload=None):
        self.events = []
        self.on_upload = on_upload
        self.keyboard = _FakeKeyboard(self)

    def is_closed(self):
        return False

    def locator(self, *a, **k):
        return _FakeLocator(self)

    async def evaluate(self, *a, **k):
        return {"widget": False, "text": "", "interstitial": False, "otp": False}  # no challenge on the page


class _FakeAccounts:
    def get_account(self, aid):
        return {"id": aid, "status": "READY"}

    def get_profile_dir(self, aid):
        return Path(".")

    def parse_proxy(self, raw):
        return None

    def update_account(self, *a, **k):
        pass


def test_client_checks_lease_right_before_submit(tmp_path: Path, monkeypatch):
    real_sleep = asyncio.sleep

    async def fast_sleep(*a, **k):
        await real_sleep(0)

    monkeypatch.setattr(hmc.asyncio, "sleep", fast_sleep)
    lease = {"held": True}
    page = _FakePage(on_upload=lambda: lease.update(held=False))
    client = HeadlessMuseClient(_FakeAccounts())
    client.enable_warm_pool(True)
    client._warm_sessions["acc_x"] = (None, None, page)

    async def noop(*a, **k):
        return None

    async def ready(*a, **k):
        return True

    monkeypatch.setattr(HeadlessMuseClient, "_start_fresh_chat", staticmethod(noop))
    monkeypatch.setattr(HeadlessMuseClient, "_check_page_errors", classmethod(lambda cls, p, *a, **k: noop()))
    monkeypatch.setattr(HeadlessMuseClient, "_is_chat_ready", staticmethod(ready))
    zp = tmp_path / "h.zip"
    zp.write_bytes(b"x")
    with pytest.raises(hmc.LeaseLostException) as ei:
        asyncio.run(client._dispatch_zip_and_wait_result(
            "acc_x", zp, "msg", tmp_path / "r.zip", timeout_seconds=1, lease_guard=lambda: lease["held"]))
    assert "press:Enter" not in page.events, "the batch was submitted after the lease was lost"
    assert not getattr(ei.value, "submitted", False)


def test_engine_lease_lost_during_dispatch_is_not_counted_as_sent(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 1)
    reg = LeaseRegistry()
    reg.acquire("L1", str(tmp_path / "proj"), ids, 1)
    lane = LaneContext("L1", reg)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    sent = []

    class Client(_video_client_factory(seed, [], lambda n: None)):
        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False, lease_guard=None):
            reg.release("L1")  # lease lost while logging in / uploading
            if lease_guard is not None and not lease_guard():
                raise hmc.LeaseLostException("lease lost before submit")
            sent.append(batch_id)
            return await super().generate_videos_batch(account_id, shots, batch_id, output_dir, timeout_seconds,
                                                       simulate)

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False, lane=lane,
                                qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}})
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    res = engine.run_videos(project_dir=proj, max_rounds=1, auto_repair=False)
    assert sent == [], "a batch was sent on a lost lease"
    assert res["sends_by_shot"] == {} and res["submitted_unconfirmed_shot_ids"] == []
    assert {f["reason"] for f in res["failed_shots"]} == {"NOT_DISPATCHED"}


# ---- finding 3: an error after a successful dispatch is a submitted batch, never resent -----------------------------
def test_post_dispatch_error_is_submitted_and_not_resent(tmp_path: Path, monkeypatch):
    mgr, _ = _make_accounts(tmp_path, 1)
    dispatched = []

    async def fake_dispatch(self, account_id, handoff_zip, relay_message, expected_result_zip, timeout_seconds=480,
                            lease_guard=None):
        dispatched.append(account_id)
        return expected_result_zip

    def boom(*a, **k):
        raise RuntimeError("unpack failed")

    monkeypatch.setattr(HeadlessMuseClient, "_dispatch_zip_and_wait_result", fake_dispatch)
    monkeypatch.setattr(BatchPackager, "unpack_batch_result", staticmethod(boom))
    engine = ParallelPoolEngine(account_manager=mgr, sync_ui=False,
                                qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}})
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=3, simulate=False)
    assert len(dispatched) == 1, f"a submitted batch was resent: {dispatched}"
    assert set(res["sends_by_shot"].values()) == {1} and len(res["sends_by_shot"]) == 2
    assert sorted(res["submitted_unconfirmed_shot_ids"]) == sorted(_shots(proj))


# ---- finding 4: a clip whose SHA-256 differs from the receipt is never verified -------------------------------------
def test_sha_mismatch_clip_excluded_but_good_clip_kept(tmp_path: Path):
    good, bad = b"G" * 4096, b"B" * 4096
    zp = tmp_path / "res.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("shot_01.mp4", good)
        zf.writestr("shot_02.mp4", bad)
        zf.writestr("batch_receipt.json", json.dumps({"shots": [
            {"shot_id": "S1", "output_file": "shot_01.mp4", "sha256": hashlib.sha256(good).hexdigest()},
            {"shot_id": "S2", "output_file": "shot_02.mp4", "sha256": "0" * 64},
        ]}))
    man = tmp_path / "m.json"
    man.write_text(json.dumps({"shots": [{"slot_id": "shot_01", "shot_id": "S1"},
                                         {"slot_id": "shot_02", "shot_id": "S2"}]}), encoding="utf-8")
    res = BatchPackager.unpack_batch_result(zp, tmp_path / "out", handoff_manifest_path=man, strict_min_bytes=1)
    assert "S1" in res["verified_shots"]
    assert "S2" not in res["verified_shots"], "an integrity-failed clip was verified"
    assert res["verified"] is False and "S2" in res["integrity_failed_shots"]


# ---- finding 5: unconfirmed submissions persist across invocations --------------------------------------------------
def test_unconfirmed_submission_blocks_resend_in_next_invocation(tmp_path: Path):
    def behaviour(n):
        if n == 1:
            raise _submitted(RuntimeError("browser crashed after send"))

    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    engine, calls = _video_engine_pass(tmp_path, behaviour)
    res1 = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    assert len(calls) == 1 and res1["status"] == "INCOMPLETE"
    blocked = sorted(_shots(proj))
    assert sorted(res1["submitted_unconfirmed_shot_ids"]) == blocked

    engine2, calls2 = _video_engine_pass(tmp_path / "b", lambda n: None)
    res2 = engine2.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False)
    assert calls2 == [], "a shot with an unreconciled send was resent by the next invocation"
    assert sorted(res2["submitted_unconfirmed_shot_ids"]) == blocked
    assert {f["reason"] for f in res2["failed_shots"]} == {"SUBMITTED_UNCONFIRMED"}
    assert {e["shot_id"] for e in res2["unconfirmed_submissions"]} == set(blocked)

    engine3, calls3 = _video_engine_pass(tmp_path / "c", lambda n: None)
    res3 = engine3.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, auto_repair=False,
                              release_unconfirmed=True)
    assert len(calls3) == 1 and res3["status"] == "COMPLETED"
    assert {e["reason"] for e in res3["unconfirmed_released"]} == {"MANUAL"}
    # Entries stay as history (review 7), none of them blocks any more.
    entries = json.loads((proj / "unconfirmed_submissions.json").read_text(encoding="utf-8"))["entries"]
    assert entries and all(e["status"] in ("RELEASED", "RESOLVED") for e in entries)


def test_unconfirmed_submission_past_ttl_needs_explicit_release(tmp_path: Path):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, shot = next(iter(_shots(proj).items()))
    old = time.time() - 3 * 3600
    (proj / "unconfirmed_submissions.json").write_text(json.dumps({"entries": [{
        "shot_id": sid, "batch_id": "B", "take": 1, "submitted_epoch": old,
        "fingerprint": _render_fingerprint(shot, False)}]}), encoding="utf-8")
    engine, calls = _video_engine_pass(tmp_path, lambda n: None)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, unconfirmed_ttl_min=120)
    assert calls == [] and res["unconfirmed_expired"][0]["status"] == "EXPIRED_NEEDS_RECONCILE"  # review 7: no auto release
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, unconfirmed_ttl_min=120,
                            release_unconfirmed=True)
    assert len(calls) == 1 and res["status"] == "COMPLETED"
    assert res["unconfirmed_released"][0]["reason"] == "MANUAL"


# ---- finding 6: a late rejected take never overwrites the kept take's strip -----------------------------------------
def test_late_rejected_take1_does_not_overwrite_kept_strip(tmp_path: Path):
    def scores(batch, sid):
        return None if "_T1" in batch else 80.0

    engine, _ = _take_engine(tmp_path, scores, delay=lambda bid: 0.3 if "_T1" in bid else 0.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    res = engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=2)
    assert res["status"] == "COMPLETED"
    sid = next(iter(_shots(proj)))
    rec = _audit(proj)["per_shot_qc"][sid]
    assert rec["take"] == 2
    strip = (proj / "qc_strips" / f"{sid}_strip.jpg").read_bytes()
    assert strip.endswith(b"_T2"), f"canonical strip is not the kept take's: {strip!r}"
    take1 = next(c for c in rec["candidates"] if c["take"] == 1)
    assert Path(take1["strip_path"]).read_bytes().endswith(b"_T1")


# ---- finding 7: promote-take puts a self-reviewed passing take into the canonical slot ------------------------------
def test_promote_take_switches_canonical_clip_strip_and_audit(tmp_path: Path, capsys):
    engine, _ = _take_engine(tmp_path, lambda b, s: 40.0 if "_T2" in b else 80.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    res = engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=2)
    assert res["status"] == "COMPLETED"
    sid, shot = next(iter(_shots(proj).items()))
    before = _audit(proj)
    assert before["per_shot_qc"][sid]["take"] == 1
    take2 = next(c for c in before["per_shot_qc"][sid]["candidates"] if c["take"] == 2)

    rc = cli.main(["promote-take", str(proj), sid, "2"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["promoted"]["take"] == 2
    after = _audit(proj)
    canonical = Path(after["passed_clips"][sid])
    assert canonical.read_bytes() == Path(take2["clip_path"]).read_bytes()
    rec = after["per_shot_qc"][sid]
    assert rec["take"] == 2 and rec["selected_by"] == "promote-take"
    assert Path(rec["clip_path"]) == Path(take2["clip_path"])
    assert after["render_fingerprints"][sid] == _render_fingerprint(shot, False)
    assert (proj / "qc_strips" / f"{sid}_strip.jpg").read_bytes().endswith(b"_T2")


def test_promote_take_refuses_rejected_or_unknown_take(tmp_path: Path, capsys):
    engine, _ = _take_engine(tmp_path, lambda b, s: None if "_T2" in b else 80.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=2)
    sid = next(iter(_shots(proj)))
    before = (proj / "qc_audit_report.json").read_bytes()
    assert cli.main(["promote-take", str(proj), sid, "2"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "TAKE_NOT_PASSING"
    assert cli.main(["promote-take", str(proj), sid, "7"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "TAKE_NOT_FOUND"
    assert (proj / "qc_audit_report.json").read_bytes() == before


# ---- finding 9: invalid manifest `takes` never beats the flag ----------------------------------------------------------
@pytest.mark.parametrize("raw", [0, -2, True, 2.5, "2", None])
def test_invalid_manifest_takes_falls_back_to_flag(tmp_path: Path, raw):
    engine, calls = _take_engine(tmp_path, lambda b, s: 50.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    mp = proj / "shots_manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    manifest["shots"][0]["takes"] = raw
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    res = engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=3)
    assert set(res["takes_by_shot"].values()) == {3}
    assert set(_sent_shots(calls).values()) == {3}


# ---- finding 10: simulate with a real lane context runs on synthetic accounts ------------------------------------------
def test_simulate_with_real_lane_context_dispatches_sim_accounts(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 2)
    reg_path = tmp_path / "real_leases.json"
    reg = LeaseRegistry(reg_path)
    reg.acquire("REAL", str(tmp_path / "proj"), ids, 2)
    before = reg_path.read_bytes()
    lane = LaneContext("REAL", reg, read_only=True)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    calls = []
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=_video_client_factory(seed, calls, lambda n: None),
                                sync_ui=False, lane=lane)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=3)
    res = engine.run_videos(project_dir=proj, max_rounds=1, simulate=True)
    assert res["status"] == "COMPLETED", res.get("failed_shots")
    assert calls and all(acc.startswith("sim_acc_") for acc, _ in calls)
    assert reg_path.read_bytes() == before


# ---- helpers ----------------------------------------------------------------------------------------------------------
def _video_engine_pass(tmp_path: Path, behaviour):
    tmp_path.mkdir(parents=True, exist_ok=True)
    mgr, _ = _make_accounts(tmp_path, 1)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    calls = []
    engine = ParallelPoolEngine(
        account_manager=mgr, client_factory=_video_client_factory(seed, calls, behaviour),
        qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}}, sync_ui=False,
    )
    return engine, calls


def _take_engine(tmp_path: Path, scores, delay=None):
    """Engine whose QC scores by batch id; each clip / strip carries its batch id so tests can tell takes apart."""
    mgr, _ = _make_accounts(tmp_path, 3)
    calls = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False):
            calls.append((account_id, [s.shot_id for s in shots]))
            await asyncio.sleep(delay(batch_id) if delay else 0.01)
            out = Path(output_dir) / "verified_clips"
            out.mkdir(parents=True, exist_ok=True)
            verified = {}
            for idx, s in enumerate(shots, start=1):
                p = out / f"shot_{idx:02d}.mp4"
                p.write_bytes(b"\x00" * 2048 + batch_id.encode())
                verified[s.shot_id] = {"path": str(p), "bytes": p.stat().st_size}
            return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}

    def qc(clip_path, shot, **kw):
        batch = Path(clip_path).parent.parent.name
        Path(kw["strip_output_path"]).write_bytes(b"strip:" + batch.encode())
        score = scores(batch, shot["shot_id"])
        if score is None:
            return {"verdict": "REJECT", "defects": ["BLUR"], "metrics": {"quality_score": 0.0}}
        return {"verdict": "PASS", "defects": [], "metrics": {"quality_score": score}}

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, qc_evaluator=qc, sync_ui=False)
    return engine, calls
