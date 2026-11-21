import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from muse_studio.core.account_manager import AccountManager
from muse_studio.core.autoprod_orchestrator import BusyAccountDetector
from muse_studio.core.headless_muse_client import QuotaExceededException
from muse_studio.core.lane_leases import LaneContext, LeaseRegistry, read_lane_file
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine
from muse_studio.lane import main as lane_main
from muse_studio.pool_runner import main as pool_runner_main
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project


REPO_ROOT = Path(__file__).resolve().parents[2]

ACQUIRE_SCRIPT = r"""
import sys, time
from muse_studio.core.lane_leases import LeaseRegistry
reg = LeaseRegistry(sys.argv[1])
lane, start, cands, n = sys.argv[2], float(sys.argv[3]), sys.argv[4].split(","), int(sys.argv[5])
while time.time() < start:
    time.sleep(0.002)
held, new, skipped = reg.acquire(lane, "/proj/" + lane, cands, n)
print(",".join(held))
"""


def _make_accounts(tmp_path: Path, n: int, status: str = "READY", **extra):
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    ids = []
    for i in range(n):
        a = mgr.add_account(name=f"Acc_{i + 1}", **extra)
        mgr.update_account(a["id"], status=status)
        ids.append(a["id"])
    return mgr, ids


def _lane_cli(argv, capsys):
    rc = lane_main(argv)
    out = capsys.readouterr().out
    return rc, json.loads(out)


def _acc_args(tmp_path: Path):
    return ["--accounts-file", str(tmp_path / "accounts.json"), "--profiles-dir", str(tmp_path / "profiles")]


def _env():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


# ---- registry: multi-process safety ----------------------------------------------------------------------------
def test_concurrent_acquire_from_many_processes_never_double_grants(tmp_path: Path):
    reg_path = tmp_path / "leases.json"
    cands = [f"acc_{i:02d}" for i in range(8)]
    start = time.time() + 3.0
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", ACQUIRE_SCRIPT, str(reg_path), f"lane_{k}", str(start), ",".join(cands), "2"],
            cwd=str(REPO_ROOT), env=_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for k in range(6)
    ]
    grants = {}
    for k, p in enumerate(procs):
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0, err
        grants[f"lane_{k}"] = [x for x in out.strip().split(",") if x]

    all_granted = [a for g in grants.values() for a in g]
    assert len(all_granted) == len(set(all_granted)), f"double grant: {grants}"
    assert len(all_granted) == 8, "12 requested from 8 free accounts: exactly 8 must be granted"
    assert all(len(g) <= 2 for g in grants.values())

    # No lost write: the registry holds exactly what every process was told it got.
    snap = LeaseRegistry(reg_path).live_leases()
    assert {aid: rec["lane_id"] for aid, rec in snap.items()} == {
        a: lane for lane, g in grants.items() for a in g
    }


def test_concurrent_lane_open_cli_processes_split_accounts(tmp_path: Path):
    _make_accounts(tmp_path, 4)
    reg_path = tmp_path / "leases.json"
    env = _env()
    env["MUSE_LEASES_FILE"] = str(reg_path)
    procs = []
    for k in range(3):
        proj = tmp_path / f"proj_{k}"
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "muse_studio.lane", "open", "--lane", f"L{k}", "--project", str(proj), "-n", "2",
             *_acc_args(tmp_path)],
            cwd=str(REPO_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ))
    outs = []
    for p in procs:
        out, err = p.communicate(timeout=180)
        outs.append((p.returncode, json.loads(out)))
    granted = [a for rc, o in outs for a in o.get("accounts", [])]
    assert len(granted) == len(set(granted)) == 4
    assert sorted(rc for rc, _ in outs) in ([0, 0, 2], [0, 0, 0])


# ---- lane CLI ----------------------------------------------------------------------------------------------------
def test_open_is_idempotent_and_tops_up(tmp_path: Path, capsys):
    _, ids = _make_accounts(tmp_path, 4)
    proj = tmp_path / "proj"
    rc, first = _lane_cli(["open", "--lane", "A", "--project", str(proj), "-n", "2", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and first["granted"] == 2 and first["requested"] == 2
    lane_doc = read_lane_file(proj)
    assert lane_doc["lane_id"] == "A" and lane_doc["status"] == "open" and lane_doc["accounts"] == first["accounts"]

    time.sleep(1.1)
    rc, again = _lane_cli(["open", "--lane", "A", "--project", str(proj), "-n", "2", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and again["accounts"] == first["accounts"] and again["newly_granted"] == []
    assert again["expires_at"] > first["expires_at"], "re-open must extend the leases"
    assert read_lane_file(proj)["opened_at"] == lane_doc["opened_at"]

    rc, more = _lane_cli(["open", "--lane", "A", "--project", str(proj), "-n", "3", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and more["granted"] == 3 and set(first["accounts"]) < set(more["accounts"])

    # A second lane only gets what is left; the first lane's accounts are reported as leased.
    rc, other = _lane_cli(
        ["open", "--lane", "B", "--project", str(tmp_path / "projB"), "-n", "3", *_acc_args(tmp_path)], capsys
    )
    assert rc == 0 and other["granted"] == 1
    assert not set(other["accounts"]) & set(more["accounts"])
    assert all(other["skipped"][a] == "LEASED_BY_A" for a in more["accounts"])


def test_open_grants_nothing_exits_2(tmp_path: Path, capsys):
    _make_accounts(tmp_path, 2, status="UNCHECKED")
    rc, out = _lane_cli(["open", "--lane", "A", "--project", str(tmp_path / "p"), "-n", "2", *_acc_args(tmp_path)], capsys)
    assert rc == 2 and out["error"] == "NO_ACCOUNTS_GRANTED" and out["granted"] == 0
    assert set(out["skipped"].values()) == {"NOT_READY_UNCHECKED"}


def test_open_respects_accounts_filter_busy_and_profile_lock(tmp_path: Path, capsys):
    mgr, ids = _make_accounts(tmp_path, 4)
    mgr.update_account(ids[0], status="BUSY")
    locked_dir = tmp_path / "profiles" / ids[1]
    locked_dir.mkdir(parents=True, exist_ok=True)
    (locked_dir / "SingletonLock").write_text("x")
    rc, out = _lane_cli(
        ["open", "--lane", "A", "--project", str(tmp_path / "p"), "-n", "4", "--accounts", ",".join(ids[:3]),
         *_acc_args(tmp_path)], capsys,
    )
    assert rc == 0 and out["accounts"] == [ids[2]]
    assert out["skipped"][ids[0]] == "ACCOUNT_STATUS_BUSY"
    assert out["skipped"][ids[1]] == "BROWSER_PROFILE_OS_LOCKED"
    assert ids[3] not in out["skipped"] and ids[3] not in out["accounts"]


def test_expiry_and_gc(tmp_path: Path, capsys):
    reg = LeaseRegistry(tmp_path / "leases.json")
    held, _, _ = reg.acquire("A", "/p", ["x1", "x2"], 2, ttl_hours=0.5 / 3600)
    assert held == ["x1", "x2"]
    assert reg.holder_of("x1") == "A"
    time.sleep(0.7)
    assert reg.live_leases() == {}, "lease must die at expires_at"
    assert set(reg.snapshot()) == {"x1", "x2"}, "expired records stay until gc"
    dropped = reg.gc()
    assert sorted(d["id"] for d in dropped) == ["x1", "x2"]
    assert reg.snapshot() == {}
    # Another lane can take an expired lease straight away (acquire also purges expired records).
    reg.acquire("A", "/p", ["x2"], 1, ttl_hours=0.3 / 3600)
    time.sleep(0.5)
    held_b, _, skipped_b = reg.acquire("B", "/q", ["x2"], 1)
    assert held_b == ["x2"] and skipped_b == {}
    # renew never revives an expired lease
    reg.acquire("C", "/r", ["x3"], 1, ttl_hours=0.3 / 3600)
    time.sleep(0.5)
    held_c, expired_c = reg.renew("C")
    assert held_c == [] and expired_c == ["x3"]

    rc, out = _lane_cli(["gc", "--leases-file", str(tmp_path / "leases.json")], capsys)
    assert rc == 0 and out["dropped_count"] == 0


def test_close_releases_and_marks_lane_file(tmp_path: Path, capsys):
    _make_accounts(tmp_path, 3)
    proj = tmp_path / "proj"
    rc, opened = _lane_cli(["open", "--lane", "A", "--project", str(proj), "-n", "2", *_acc_args(tmp_path)], capsys)
    assert rc == 0
    rc, renewed = _lane_cli(["renew", "--lane", "A", "--ttl-hours", "2"], capsys)
    assert rc == 0 and renewed["accounts"] == opened["accounts"]
    rc, closed = _lane_cli(["close", "--lane", "A"], capsys)
    assert rc == 0 and closed["released"] == opened["accounts"]
    assert read_lane_file(proj)["status"] == "closed"
    assert LeaseRegistry().live_leases() == {}
    rc, renewed = _lane_cli(["renew", "--lane", "A"], capsys)
    assert rc == 2 and renewed["error"] == "LANE_HAS_NO_LIVE_LEASES"
    # Released accounts are free for another lane.
    rc, b = _lane_cli(["open", "--lane", "B", "--project", str(tmp_path / "pb"), "-n", "3", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and b["granted"] == 3


def test_open_refuses_project_held_by_other_open_lane(tmp_path: Path, capsys):
    _make_accounts(tmp_path, 3)
    proj = tmp_path / "proj"
    assert _lane_cli(["open", "--lane", "A", "--project", str(proj), "-n", "1", *_acc_args(tmp_path)], capsys)[0] == 0
    rc, out = _lane_cli(["open", "--lane", "B", "--project", str(proj), "-n", "1", *_acc_args(tmp_path)], capsys)
    assert rc == 3 and out["error"] == "PROJECT_IN_USE"


def test_status_never_prints_secrets(tmp_path: Path, capsys):
    secret_cookie = "session_token=SUPERSECRETCOOKIE123"
    secret_pw = "Pa55w0rdSECRET"
    secret_proxy = "http://user:proxypassSECRET@10.0.0.1:8080"
    mgr, ids = _make_accounts(
        tmp_path, 2, email="lane@example.test", raw_cookie=secret_cookie, password=secret_pw, proxy=secret_proxy
    )
    mgr.update_account(ids[0], usage_info={"weekly_remaining_pct": 40, "bonus_remaining_pct": 0})
    _lane_cli(["open", "--lane", "A", "--project", str(tmp_path / "p"), "-n", "1", *_acc_args(tmp_path)], capsys)
    rc = lane_main(["status", *_acc_args(tmp_path)])
    raw = capsys.readouterr().out
    assert rc == 0
    for secret in ("SUPERSECRETCOOKIE123", secret_pw, "proxypassSECRET", "10.0.0.1"):
        assert secret not in raw
    data = json.loads(raw)
    assert {a["id"] for a in data["accounts"]} == set(ids)
    leased = [a for a in data["accounts"] if a["lease"]]
    assert len(leased) == 1 and leased[0]["lease"]["lane_id"] == "A"
    assert leased[0]["lease"]["heartbeat_age_s"] >= 0
    assert data["lanes"]["A"]["accounts"] == [leased[0]["id"]]
    rc = lane_main(["status", "--lane", "A", *_acc_args(tmp_path)])
    only_a = json.loads(capsys.readouterr().out)
    assert [a["id"] for a in only_a["accounts"]] == [leased[0]["id"]]


# ---- selection -------------------------------------------------------------------------------------------------
def test_selection_without_lane_skips_leased_accounts(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 3)
    LeaseRegistry().acquire("A", "/p", [ids[0]], 1)
    avail, skipped = BusyAccountDetector.select_uncontended_ready_accounts(mgr)
    assert ids[0] not in avail and skipped[ids[0]] == "LEASED_BY_A"
    # The holder lane itself still sees it.
    avail_a, _ = BusyAccountDetector.select_uncontended_ready_accounts(mgr, lane_id="A")
    assert ids[0] in avail_a

    cap = ParallelPoolEngine(account_manager=mgr, sync_ui=False).inspect_capacity()
    assert ids[0] not in cap["active_account_ids"] + cap["standby_account_ids"]
    assert cap["skipped_busy_accounts"][ids[0]] == "LEASED_BY_A"


def test_selection_with_lane_only_uses_lane_accounts(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 5)
    reg = LeaseRegistry()
    reg.acquire("A", "/p", ids[:2], 2)
    reg.acquire("B", "/q", ids[2:3], 1)
    engine = ParallelPoolEngine(account_manager=mgr, sync_ui=False, lane=LaneContext("A", reg))
    cap = engine.inspect_capacity()
    assert sorted(cap["active_account_ids"]) == sorted(ids[:2]) and cap["standby_account_ids"] == []
    assert cap["lane_id"] == "A"
    # Asking for accounts outside the lane yields nothing extra.
    cap2 = engine.inspect_capacity(only_accounts={ids[3], ids[0]})
    assert cap2["active_account_ids"] == [ids[0]]


# ---- worker rotation + heartbeat + lease loss --------------------------------------------------------------------
def _fake_video_client_factory(seed: Path, telemetry, on_call=None):
    seed_bytes = seed.read_bytes()

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False):
            telemetry.append(account_id)
            if on_call:
                on_call(account_id)
            await asyncio.sleep(0.03)
            out = Path(output_dir) / "verified_clips"
            out.mkdir(parents=True, exist_ok=True)
            verified = {}
            for idx, s in enumerate(shots, start=1):
                p = out / f"shot_{idx:02d}.mp4"
                p.write_bytes(seed_bytes)
                verified[s.shot_id] = {"path": str(p), "bytes": p.stat().st_size}
            return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}

    return Client


def test_worker_rotation_never_leaves_the_lane(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LANE_HEARTBEAT_S", "1")
    mgr, ids = _make_accounts(tmp_path, 5)
    for i, aid in enumerate(ids):
        # Non-lane accounts have the most quota, so a lane-blind rotation would pick them first.
        mgr.update_account(aid, usage_info={"weekly_remaining_pct": 10 if i < 2 else 100})
    reg = LeaseRegistry()
    reg.acquire("A", "/p", ids[:2], 2)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=12)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    used = []

    def on_call(aid):
        if aid == ids[0] and used.count(ids[0]) == 1:
            mgr.update_account(aid, status="COOLDOWN")
            raise QuotaExceededException("out of credits")

    engine = ParallelPoolEngine(
        account_manager=mgr,
        client_factory=_fake_video_client_factory(seed, used, on_call),
        qc_evaluator=lambda cp, ss, **kw: {"verdict": "PASS", "defects": [], "metrics": {}},
        sync_ui=False,
        lane=LaneContext("A", reg),
    )
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=2, simulate=False)
    assert set(used) <= set(ids[:2]), f"rotation escaped the lane: {used}"
    assert ids[1] in used, "standby inside the lane must take over after the quota failure"
    assert res["status"] == "COMPLETED"
    assert res["lane"]["lane_id"] == "A" and res["lane"]["renewals"] >= 2


def test_lease_lost_mid_run_stops_dispatch_and_is_reported(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 3)
    reg = LeaseRegistry()
    reg.acquire("A", "/p", ids[:2], 2)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=24)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    used = []

    def on_call(aid):
        if len(used) == 1:
            # Simulate the lease of ids[1] expiring / being closed while the run is in flight.
            with reg._transaction() as data:
                data["leases"].pop(ids[1], None)

    engine = ParallelPoolEngine(
        account_manager=mgr,
        client_factory=_fake_video_client_factory(seed, used, on_call),
        qc_evaluator=lambda cp, ss, **kw: {"verdict": "PASS", "defects": [], "metrics": {}},
        sync_ui=False,
        lane=LaneContext("A", reg),
    )
    res = engine.run_videos(project_dir=proj, max_accounts=2, max_rounds=2, simulate=False)
    assert ids[2] not in used, "a non-lane account must never be used"
    assert used.count(ids[1]) <= 1, "no new batch may be dispatched on an account whose lease was lost"
    assert res["lane"]["lost_leases"] == [ids[1]]
    assert res["status"] == "COMPLETED", "the remaining lane account finishes the queue"


def test_legacy_run_drops_account_leased_mid_run(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 2)
    reg = LeaseRegistry()
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=24)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    used = []

    def on_call(aid):
        if len(used) == 1:
            reg.acquire("A", "/p", [ids[1]], 1)

    engine = ParallelPoolEngine(
        account_manager=mgr,
        client_factory=_fake_video_client_factory(seed, used, on_call),
        qc_evaluator=lambda cp, ss, **kw: {"verdict": "PASS", "defects": [], "metrics": {}},
        sync_ui=False,
    )
    res = engine.run_videos(project_dir=proj, max_accounts=2, max_rounds=2, simulate=False)
    assert used.count(ids[1]) <= 1, "a lane lease taken mid-run must stop a legacy run from using the account"
    assert res["lane"]["leased_by_other_lane_mid_run"] == [ids[1]]


# ---- pool_runner + lane.json -------------------------------------------------------------------------------------
def test_pool_runner_auto_detects_lane_json_in_simulate(tmp_path: Path, capsys):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=8)
    rc, opened = _lane_cli(
        ["open", "--simulate", "--lane", "SIM", "--project", str(proj), "-n", "2", *_acc_args(tmp_path)], capsys
    )
    assert rc == 0 and opened["accounts"] == ["sim_acc_01", "sim_acc_02"]
    lane_doc = read_lane_file(proj)
    assert lane_doc["simulate"] is True and lane_doc["leases_file"] == os.environ["MUSE_LEASES_FILE"]

    # A second simulated lane gets different sim ids.
    rc, other = _lane_cli(
        ["open", "--simulate", "--lane", "SIM2", "--project", str(tmp_path / "p2"), "-n", "2"], capsys
    )
    assert rc == 0 and other["accounts"] == ["sim_acc_03", "sim_acc_04"]

    rc = pool_runner_main(["videos", str(proj), "--simulate", "--no-ui-sync", *_acc_args(tmp_path)])
    res = json.loads(capsys.readouterr().out)
    assert rc == 0, res
    assert res["lane"]["lane_id"] == "SIM"
    assert sorted(res["capacity"]["active_account_ids"]) == ["sim_acc_01", "sim_acc_02"]
    assert res["passed_count"] == 8

    rc = pool_runner_main(["capacity", "--lane", "SIM2", "--simulate", *_acc_args(tmp_path)])
    cap = json.loads(capsys.readouterr().out)
    assert rc == 0 and sorted(cap["active_account_ids"]) == ["sim_acc_03", "sim_acc_04"]

    # Closed lane.json is ignored -> legacy behaviour.
    _lane_cli(["close", "--lane", "SIM", "--simulate"], capsys)
    assert read_lane_file(proj)["status"] == "closed"
    rc = pool_runner_main(["capacity", "--simulate", "--max-accounts", "1", *_acc_args(tmp_path)])
    cap = json.loads(capsys.readouterr().out)
    assert cap["lane_id"] is None


def test_simulate_lane_without_env_uses_temp_registry_not_real(tmp_path: Path, monkeypatch, capsys):
    from muse_studio.core import lane_leases

    monkeypatch.delenv("MUSE_LEASES_FILE", raising=False)
    monkeypatch.setattr(lane_leases.tempfile, "gettempdir", lambda: str(tmp_path))
    real = lane_leases.real_leases_path()
    before = real.read_bytes() if real.exists() else None
    rc, out = _lane_cli(["open", "--simulate", "--lane", "S", "--project", str(tmp_path / "p"), "-n", "1"], capsys)
    assert rc == 0 and Path(out["leases_file"]) == tmp_path / lane_leases.SIM_LEASES_FILE_NAME
    after = real.read_bytes() if real.exists() else None
    assert before == after, "simulate must not touch the real registry"


def test_simulate_run_on_real_registry_lane_is_read_only(tmp_path: Path, monkeypatch):
    from muse_studio.core import lane_leases
    from muse_studio.pool_runner import _resolve_lane, build_parser

    fake_real = tmp_path / "real_leases.json"
    monkeypatch.delenv("MUSE_LEASES_FILE", raising=False)
    monkeypatch.setattr(lane_leases, "real_leases_path", lambda: fake_real)
    import muse_studio.pool_runner as pr
    monkeypatch.setattr(pr, "real_leases_path", lambda: fake_real)
    LeaseRegistry(fake_real).acquire("REAL", "/p", ["acc_x"], 1)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "lane.json").write_text(json.dumps({"lane_id": "REAL", "status": "open", "leases_file": str(fake_real)}))
    args = build_parser().parse_args(["keyframes", str(proj), "--simulate"])
    lane = _resolve_lane(args)
    assert lane.lane_id == "REAL" and lane.read_only
    before = fake_real.read_bytes()
    lane.renew()
    assert fake_real.read_bytes() == before


# ---- review fixes: fail closed, simulate isolation, bulk verify ------------------------------------------------
def test_corrupt_registry_fails_closed_and_is_not_overwritten(tmp_path: Path):
    from muse_studio.core.lane_leases import LeaseRegistryError

    mgr, ids = _make_accounts(tmp_path, 2)
    reg = LeaseRegistry()
    reg.path.write_text("{not json", encoding="utf-8")
    with pytest.raises(LeaseRegistryError):
        reg.acquire("A", "/p", ids, 1)
    with pytest.raises(LeaseRegistryError):
        BusyAccountDetector.select_uncontended_ready_accounts(mgr)
    assert reg.path.read_text(encoding="utf-8") == "{not json"


def test_simulate_lane_cli_refuses_to_mutate_real_registry(tmp_path: Path, monkeypatch, capsys):
    import muse_studio.lane as lane_mod

    fake_real = tmp_path / "real_leases.json"
    monkeypatch.setattr(lane_mod, "real_leases_path", lambda: fake_real)
    LeaseRegistry(fake_real).acquire("REAL", str(tmp_path / "proj"), ["acc_x"], 1)
    before = fake_real.read_bytes()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "lane.json").write_text(json.dumps({"lane_id": "REAL", "status": "open", "leases_file": str(fake_real)}))
    for argv in (
        ["open", "--simulate", "--lane", "REAL", "--project", str(proj), "-n", "1"],
        ["close", "--simulate", "--lane", "REAL", "--project", str(proj)],
        ["renew", "--simulate", "--lane", "REAL", "--leases-file", str(fake_real)],
        ["gc", "--simulate", "--leases-file", str(fake_real)],
    ):
        rc, out = _lane_cli(argv, capsys)
        assert rc == 1 and out["error"] == "SIMULATE_REAL_REGISTRY", argv
    monkeypatch.setenv("MUSE_LEASES_FILE", str(fake_real))
    rc, out = _lane_cli(["close", "--simulate", "--lane", "REAL"], capsys)
    assert rc == 1 and out["error"] == "SIMULATE_REAL_REGISTRY"
    assert fake_real.read_bytes() == before
    rc, out = _lane_cli(["status", "--simulate", "--lane", "REAL", *_acc_args(tmp_path)], capsys)
    assert rc == 0 and out["lanes"]["REAL"]["accounts"] == ["acc_x"]


def test_bulk_accounts_verify_skips_leased_accounts(tmp_path: Path, monkeypatch):
    import argparse
    import muse_studio.cli as cli_mod

    mgr, ids = _make_accounts(tmp_path, 3, status="UNCHECKED")
    LeaseRegistry().acquire("A", "/p", [ids[0]], 1)
    touched = []
    monkeypatch.setattr(mgr, "auto_login_and_verify", lambda aid: touched.append(aid) or {"status": "READY"})
    monkeypatch.setattr(cli_mod, "AccountManager", lambda: mgr)
    cli_mod.cmd_accounts_verify(argparse.Namespace(account_id=None))
    assert ids[0] not in touched and set(touched) == set(ids[1:])
