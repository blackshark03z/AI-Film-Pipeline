"""Regression tests for the round-2 review of the autonomous-lane flow (one test group per review item)."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import muse_studio.cli as cli
import muse_studio.pool_runner as pool_runner
from muse_studio.core.account_manager import AccountManager
from muse_studio.core.autoprod_orchestrator import _load_render_checkpoint, _render_fingerprint
from muse_studio.core.headless_muse_client import (
    GenerationFailedException,
    HeadlessMuseClient,
    QuotaExceededException,
)
from muse_studio.core.lane_leases import LeaseConflictError, LeaseRegistry, read_lane_file
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine
from muse_studio.lane import main as lane_main
from muse_studio.pool_runner import main as pool_runner_main
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project


def _make_accounts(tmp_path: Path, n: int):
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    ids = []
    for i in range(n):
        a = mgr.add_account(name=f"Acc_{i + 1}")
        mgr.update_account(a["id"], status="READY")
        ids.append(a["id"])
    return mgr, ids


def _acc_args(tmp_path: Path):
    return ["--accounts-file", str(tmp_path / "accounts.json"), "--profiles-dir", str(tmp_path / "profiles")]


def _lane_cli(argv, capsys):
    rc = lane_main(argv)
    return rc, json.loads(capsys.readouterr().out)


def _submitted(exc):
    exc.submitted = True
    return exc


# ---- item 1: a lane id is bound to its project ---------------------------------------------------------------------
def test_reopen_same_lane_from_other_project_is_refused(tmp_path: Path, capsys):
    _make_accounts(tmp_path, 3)
    p1, p2 = str(tmp_path / "p1"), str(tmp_path / "p2")
    rc, out = _lane_cli(["open", "--lane", "A", "--project", p1, "-n", "2", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and len(out["accounts"]) == 2
    held = out["accounts"]

    rc, out = _lane_cli(["open", "--lane", "A", "--project", p2, "-n", "2", *_acc_args(tmp_path)], capsys)
    assert rc == 3 and out["error"] == "LANE_ID_IN_USE"
    assert sorted(LeaseRegistry().lane_accounts("A")) == sorted(held), "leases must not move to the other project"
    assert read_lane_file(Path(p2)) is None

    for sub in ("renew", "close"):
        rc, out = _lane_cli([sub, "--lane", "A", "--project", p2], capsys)
        assert rc == 3 and out["error"] == "LANE_ID_IN_USE", sub
    assert sorted(LeaseRegistry().lane_accounts("A")) == sorted(held)

    rc, out = _lane_cli(["renew", "--lane", "A", "--project", p1], capsys)
    assert rc == 0 and sorted(out["accounts"]) == sorted(held)


def test_reopen_with_smaller_n_keeps_held_leases(tmp_path: Path, capsys):
    _make_accounts(tmp_path, 3)
    p1 = str(tmp_path / "p1")
    rc, out = _lane_cli(["open", "--lane", "A", "--project", p1, "-n", "3", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and len(out["accounts"]) == 3
    rc, out = _lane_cli(["open", "--lane", "A", "--project", p1, "-n", "1", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and len(out["accounts"]) == 3 and out["held_exceeds_requested"] is True
    assert len(LeaseRegistry().lane_accounts("A")) == 3, "no silent release on a smaller re-open"


# ---- item 2: the project claim lives in the registry, checked and claimed in one transaction ----------------------
def test_second_lane_on_same_project_is_refused_even_without_lane_json(tmp_path: Path, capsys):
    _make_accounts(tmp_path, 3)
    proj = tmp_path / "proj"
    rc, out = _lane_cli(["open", "--lane", "A", "--project", str(proj), "-n", "1", *_acc_args(tmp_path)], capsys)
    assert rc == 0
    assert LeaseRegistry().project_holder(str(proj)) == "A"
    (proj / "lane.json").unlink()  # the registry, not lane.json, is the source of truth

    rc, out = _lane_cli(["open", "--lane", "B", "--project", str(proj), "-n", "1", *_acc_args(tmp_path)], capsys)
    assert rc == 3 and out["error"] == "PROJECT_IN_USE"
    assert LeaseRegistry().lane_accounts("B") == []
    assert not (proj / "lane.json").exists(), "lane.json is written only after a successful claim"


def test_project_claim_honours_old_format_registry(tmp_path: Path):
    reg_path = Path(LeaseRegistry().path)
    now = datetime.now(timezone.utc)
    proj = str((tmp_path / "proj").resolve())
    rec = {
        "lane_id": "OLD", "project_dir": proj,
        "acquired_at": now.isoformat(timespec="milliseconds"),
        "heartbeat_at": now.isoformat(timespec="milliseconds"),
        "expires_at": (now + timedelta(hours=1)).isoformat(timespec="milliseconds"),
        "host": "h", "pid": 1,
    }
    reg_path.write_text(json.dumps({"version": 1, "leases": {"acc_old": rec}}), encoding="utf-8")
    with pytest.raises(LeaseConflictError) as ei:
        LeaseRegistry().acquire("NEW", proj, ["acc_new"], 1)
    assert ei.value.code == "PROJECT_IN_USE"


# ---- items 3 + 5: one send per shot per run, submitted batches are never resent ------------------------------------
def _video_client_factory(seed: Path, calls, behaviour):
    seed_bytes = seed.read_bytes()

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False):
            calls.append((account_id, [s.shot_id for s in shots]))
            behaviour(len(calls))
            await asyncio.sleep(0.01)
            out = Path(output_dir) / "verified_clips"
            out.mkdir(parents=True, exist_ok=True)
            verified = {}
            for idx, s in enumerate(shots, start=1):
                p = out / f"shot_{idx:02d}.mp4"
                p.write_bytes(seed_bytes)
                verified[s.shot_id] = {"path": str(p), "bytes": p.stat().st_size}
            return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}

    return Client


def _video_engine(tmp_path, behaviour, verdict="PASS"):
    mgr, _ = _make_accounts(tmp_path, 2)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    calls = []
    engine = ParallelPoolEngine(
        account_manager=mgr,
        client_factory=_video_client_factory(seed, calls, behaviour),
        qc_evaluator=lambda cp, ss, **kw: {"verdict": verdict, "defects": [] if verdict == "PASS" else ["BLUR"],
                                           "metrics": {}},
        sync_ui=False,
    )
    return engine, calls


def _sent_shots(calls):
    out = {}
    for _, sids in calls:
        for sid in sids:
            out[sid] = out.get(sid, 0) + 1
    return out


@pytest.mark.parametrize("exc_factory", [
    lambda: _submitted(QuotaExceededException("quota after send")),
    lambda: _submitted(RuntimeError("browser crashed after send")),
])
def test_submitted_batch_is_never_resent(tmp_path: Path, exc_factory):
    def behaviour(n):
        if n == 1:
            raise exc_factory()

    engine, calls = _video_engine(tmp_path, behaviour)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=6)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=3, simulate=False)
    assert len(calls) == 1, f"a submitted batch was resent: {calls}"
    assert set(_sent_shots(calls).values()) == {1}
    assert res["sends_by_shot"] == _sent_shots(calls)
    assert res["status"] == "INCOMPLETE"
    assert sorted(res["submitted_unconfirmed_shot_ids"]) == sorted(calls[0][1])
    assert {f["reason"] for f in res["failed_shots"]} == {"SUBMITTED_UNCONFIRMED"}


def test_unsent_batch_fails_over_once_to_standby(tmp_path: Path):
    def behaviour(n):
        if n == 1:
            raise QuotaExceededException("quota before send")

    engine, calls = _video_engine(tmp_path, behaviour)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=6)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, simulate=False)
    assert len(calls) == 2 and calls[0][0] != calls[1][0]
    assert res["status"] == "COMPLETED"
    assert set(res["sends_by_shot"].values()) == {1}, "the failed attempt never reached Muse"


def test_max_rounds_1_no_auto_repair_sends_each_qc_failed_shot_once(tmp_path: Path):
    engine, calls = _video_engine(tmp_path, lambda n: None, verdict="FAIL")
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=8)
    res = engine.run_videos(project_dir=proj, max_accounts=2, max_rounds=1, auto_repair=False, simulate=False)
    sent = _sent_shots(calls)
    assert len(sent) == 8 and set(sent.values()) == {1}
    assert res["sends_by_shot"] == sent
    assert res["status"] == "INCOMPLETE"
    assert sorted(f["shot_id"] for f in res["failed_shots"]) == sorted(sent)
    assert {f["reason"] for f in res["failed_shots"]} == {"QC_REJECT"}


# ---- item 8: keyframes with missing / unverified images are not COMPLETED ------------------------------------------
def _kf_project(tmp_path: Path, n_chars: int = 4) -> Path:
    proj = tmp_path / "kf_proj"
    proj.mkdir(parents=True, exist_ok=True)
    bible = {
        "project_title": "KF",
        "characters": [
            {"id": f"CHAR_{i:02d}", "name": f"C{i}", "look_verbatim": f"A {30 + i}-year-old person #{i}",
             "anchor_image": f"char_{i:02d}.png", "axis_gaze": "looking screen-right"}
            for i in range(1, n_chars + 1)
        ],
        "locations": [{"id": "LOC_1", "name": "Room", "look_verbatim": "room", "set_facts": ["desk"]}],
    }
    (proj / "story_bible.json").write_text(json.dumps(bible), encoding="utf-8")
    (proj / "shots_manifest.json").write_text(json.dumps({"shots": []}), encoding="utf-8")
    return proj


def test_keyframes_missing_image_is_incomplete_and_pool_runner_exits_nonzero(tmp_path: Path, monkeypatch, capsys):
    mgr, _ = _make_accounts(tmp_path, 1)
    dropped = []

    class DroppingClient:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False):
            res = await HeadlessMuseClient(self.account_manager).generate_keyframes_batch(
                account_id=account_id, keyframes=keyframes, batch_id=batch_id, output_dir=output_dir, simulate=True
            )
            kf_id = sorted(res["keyframes"])[0]
            res["keyframes"].pop(kf_id)
            dropped.append(kf_id)
            return res

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=DroppingClient, sync_ui=False)
    monkeypatch.setattr(pool_runner, "_build_engine", lambda args: engine)
    proj = _kf_project(tmp_path)
    rc = pool_runner_main(["keyframes", str(proj)])
    res = json.loads(capsys.readouterr().out)
    assert res["status"] == "INCOMPLETE" and rc == 1
    assert set(dropped) <= set(res["missing_keyframes"]) and dropped


def test_keyframes_submitted_batch_is_not_resent(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 2)
    sent = []

    class FailingAfterSendClient:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False):
            sent.extend(k.kf_id for k in keyframes)
            raise _submitted(GenerationFailedException("no image after send"))

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=FailingAfterSendClient, sync_ui=False)
    res = engine.run_keyframes(project_dir=_kf_project(tmp_path), max_accounts=1, simulate=False)
    assert len(sent) == len(set(sent)) == 4, f"submitted keyframes were resent: {sent}"
    assert res["status"] == "INCOMPLETE"
    assert sorted(res["missing_keyframes"]) == sorted(sent)
    assert any(e.get("submitted") for e in res["batch_errors"])


# ---- item 4: `cli keyframes` resolves the lane like pool_runner -----------------------------------------------------
def _capture_kf(monkeypatch, mgr):
    seen = {}

    async def fake_generate(project_dir, account_ids, client, simulate, include_setups=False,
                            include_turnarounds=False):
        seen["account_ids"] = list(account_ids)
        return {"rejected": []}

    monkeypatch.setattr(cli.KeyframeComposer, "generate_and_verify_keyframes", staticmethod(fake_generate))
    monkeypatch.setattr(cli, "AccountManager", lambda: mgr)
    monkeypatch.setattr(cli, "HeadlessMuseClient", lambda m: None)
    monkeypatch.setattr(cli, "cmd_accounts_verify", lambda a: pytest.fail("bulk verify must not run"))
    return seen


def test_cli_keyframes_uses_lane_accounts_only(tmp_path: Path, monkeypatch, capsys):
    mgr, ids = _make_accounts(tmp_path, 4)
    proj = tmp_path / "proj"
    reg = LeaseRegistry()
    reg.acquire("OTHER", str(tmp_path / "other"), ids[:1], 1)
    rc, out = _lane_cli(["open", "--lane", "A", "--project", str(proj), "-n", "2", *_acc_args(tmp_path)], capsys)
    assert rc == 0
    lane_ids = out["accounts"]
    seen = _capture_kf(monkeypatch, mgr)

    # Round 15: a real `cli keyframes` never sends (one production send path: pool_runner keyframes).
    rc = cli.main(["keyframes", str(proj)])
    rep = json.loads(capsys.readouterr().out)
    assert rc == 2 and rep["status"] == "REFUSED_USE_POOL_RUNNER" and "account_ids" not in seen

    rc = cli.main(["keyframes", str(proj), "--simulate"])  # lane auto-detected from lane.json
    rep = json.loads(capsys.readouterr().out)
    assert rc == 0 and rep["lane"]["lane_id"] == "A"
    assert seen["account_ids"] and all(a.startswith("sim_acc_") for a in seen["account_ids"])
    assert not set(seen["account_ids"]) & set(ids), "a dry run selected a real account"


def test_cli_keyframes_without_lane_skips_leased_and_simulate_uses_sim_ids(tmp_path: Path, monkeypatch, capsys):
    mgr, ids = _make_accounts(tmp_path, 3)
    LeaseRegistry().acquire("OTHER", str(tmp_path / "other"), ids[:2], 2)
    seen = _capture_kf(monkeypatch, mgr)
    proj = tmp_path / "proj"
    proj.mkdir()
    assert cli.main(["keyframes", str(proj)]) == 2  # real run refused: pool_runner keyframes
    capsys.readouterr()
    assert "account_ids" not in seen
    assert cli.main(["keyframes", str(proj), "--simulate"]) == 0
    capsys.readouterr()
    assert seen["account_ids"] == ["sim_acc_01"]


# ---- item 6: render fingerprints survive qc-audit; a verified clip without one is stale -----------------------------
def test_qc_audit_preserves_render_fingerprints(tmp_path: Path, monkeypatch, capsys):
    # The kept clip's fingerprint survives qc-audit; shots without a kept clip (or gone) carry none (review 6 #1).
    from muse_studio.core.film_qc_engine import FilmQCEngine

    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    manifest = json.loads((proj / "shots_manifest.json").read_text(encoding="utf-8"))
    sid = "SHOT_001_CH01"
    good = _render_fingerprint(next(s for s in manifest["shots"] if s["shot_id"] == sid), False)
    canonical = proj / "verified_clips" / f"{sid}.mp4"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes(b"\x00" * (110 * 1024))
    audit = proj / "qc_audit_report.json"
    audit.write_text(json.dumps({
        "passed_clips": {sid: str(canonical)},
        "per_shot_qc": {sid: {"verdict": "PASS", "take": 1, "clip_path": str(canonical)}},
        "render_fingerprints": {sid: good, "SHOT_002_CH01": "fp_no_clip", "GONE_SHOT": "fp2"},
    }), encoding="utf-8")
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", staticmethod(
        lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {"quality_score": 50.0}}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    data = json.loads(audit.read_text(encoding="utf-8"))
    assert data["render_fingerprints"] == {sid: good}
    assert data["passed_clips"] == {sid: str(canonical)}


def test_verified_clip_without_fingerprint_is_stale(tmp_path: Path):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    manifest = json.loads((proj / "shots_manifest.json").read_text(encoding="utf-8"))
    shots = {s["shot_id"]: s for s in manifest["shots"]}
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\x00" * 64)
    audit = tmp_path / "audit.json"
    sid = "SHOT_001_CH01"

    audit.write_text(json.dumps({"passed_clips": {sid: str(clip)}}), encoding="utf-8")
    passed, _, fps = _load_render_checkpoint(audit, shots, simulate=False)
    assert passed == {} and fps == {}

    good = _render_fingerprint(shots[sid], False)
    audit.write_text(json.dumps({"passed_clips": {sid: str(clip)}, "render_fingerprints": {sid: good}}),
                     encoding="utf-8")
    passed, _, fps = _load_render_checkpoint(audit, shots, simulate=False)
    assert passed == {sid: str(clip)} and fps == {sid: good}


# ---- item 7: assemble never falls back to raw clips when an audit exists ---------------------------------------------
def test_assemble_refuses_raw_fallback_when_audit_has_no_passed_clip(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    (proj / "qc_audit_report.json").write_text(json.dumps({"passed_clips": {}}), encoding="utf-8")
    monkeypatch.setattr(cli, "_discover_existing_clip_map",
                        lambda *a, **k: pytest.fail("raw BATCHES fallback used despite an audit"))
    monkeypatch.setattr(cli.MasterAssembler, "assemble_project",
                        staticmethod(lambda **k: pytest.fail("assembled without QC-passed clips")))
    rc = cli.main(["assemble", str(proj)])
    out = json.loads(capsys.readouterr().out)
    assert rc != 0 and out["error"] == "NO_QC_PASSED_CLIPS"


def test_assemble_without_audit_still_uses_raw_clips(tmp_path: Path, monkeypatch, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    used = {}
    monkeypatch.setattr(cli, "_discover_existing_clip_map", lambda *a, **k: used.setdefault("raw", {}))
    monkeypatch.setattr(cli.MasterAssembler, "assemble_project", staticmethod(lambda **k: {"success": True}))
    assert cli.main(["assemble", str(proj)]) == 0
    capsys.readouterr()
    assert "raw" in used


# ---- item 9: preflight --no-srt-gate -----------------------------------------------------------------------------
def test_preflight_no_srt_gate_is_reported(tmp_path: Path, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    srt = proj / "source.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nA line that no shot covers.\n", encoding="utf-8")
    report = proj / "preflight_report.json"

    cli.main(["preflight", str(proj), "--srt", str(srt)])
    capsys.readouterr()
    gated = json.loads(report.read_text(encoding="utf-8"))
    assert gated["srt_gate"] in ("PASS", "FAIL") and "srt_coverage" in gated

    cli.main(["preflight", str(proj), "--srt", str(srt), "--no-srt-gate"])
    capsys.readouterr()
    skipped = json.loads(report.read_text(encoding="utf-8"))
    assert skipped["srt_gate"] == "SKIPPED_BY_FLAG"
    assert "srt_coverage" not in skipped
    assert not any(e["shot_id"] == "SRT_COVERAGE" for e in skipped["errors"])


# ---- item 10: --simulate never selects or writes real accounts -----------------------------------------------------
def test_simulate_never_selects_or_writes_real_accounts(tmp_path: Path, capsys):
    mgr, ids = _make_accounts(tmp_path, 3)
    engine = ParallelPoolEngine(account_manager=mgr, sync_ui=False)
    cap = engine.inspect_capacity(max_accounts=2, simulate=True)
    assert cap["active_account_ids"] and all(a.startswith("sim_acc_") for a in cap["active_account_ids"])
    assert not set(cap["active_account_ids"] + cap["standby_account_ids"]) & set(ids)

    before = (tmp_path / "accounts.json").read_bytes()
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=6)
    rc = pool_runner_main(["videos", str(proj), "--simulate", "--no-ui-sync", *_acc_args(tmp_path)])
    res = json.loads(capsys.readouterr().out)
    assert rc == 0, res
    assert all(a.startswith("sim_acc_") for a in res["capacity"]["active_account_ids"])
    assert (tmp_path / "accounts.json").read_bytes() == before, "a dry run wrote accounts.json"
