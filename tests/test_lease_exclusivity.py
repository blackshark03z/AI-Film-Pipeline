"""Upgrade step 4A: account leases are exclusive across callers, processes and films; generate() is the one sender."""
import json
import multiprocessing as mp
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.agentic.lease_pool import UNCERTAIN, AccountLeasePool, default_db_path
from film_pipeline.production import generate as G
from film_pipeline.production import halt as H
from film_pipeline.production import leases as L
from film_pipeline.providers._flow_ui import flow_send as FS

from test_production_generate import FakeRunner, backlog, film, still

ROOT = Path(__file__).resolve().parents[1]


def pool_with(tmp_path, *accounts, credits=100.0, **kw):
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=10.0, **kw)
    for a in accounts:
        pool.register_account(a, credits)
    return pool


# ---- the pool ----------------------------------------------------------------------------------------------------

def test_default_db_is_the_machine_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("AFP_STATE_DIR", str(tmp_path / "state"))
    assert default_db_path() == tmp_path / "state" / "lease_pool.sqlite3"
    assert AccountLeasePool().db_path == default_db_path()


def test_a_second_holder_cannot_get_an_active_lease_and_the_same_holder_is_idempotent(tmp_path):
    pool = pool_with(tmp_path, "a1", "a2")
    first = pool.acquire("g1", cost_credits=6.0, now=10.0, holder="h1")
    assert first is not None and first["holder"] == "h1"
    assert pool.acquire("g1", cost_credits=6.0, now=10.0, holder="h2") is None
    lease, why = pool.acquire_or_reason("g1", cost_credits=6.0, now=10.0, holder="h2")
    assert lease is None and "held by another caller" in why
    again = pool.acquire("g1", cost_credits=6.0, now=11.0, holder="h1")
    assert again["lease_token"] == first["lease_token"] and again["account_id"] == first["account_id"]
    # the default holder is unique per process, never the explicit "h1"
    assert pool.acquire("g1", cost_credits=6.0, now=11.0) is None


def test_release_needs_the_matching_token(tmp_path):
    pool = pool_with(tmp_path, "a1")
    lease = pool.acquire("g1", cost_credits=6.0, now=10.0, holder="h1")
    with pytest.raises(ValueError, match="lease_token"):
        pool.release("g1", credits_spent=6.0, now=11.0)
    with pytest.raises(ValueError, match="lease_token mismatch"):
        pool.release("g1", credits_spent=6.0, now=11.0, lease_token="wrong")
    assert pool.snapshot()["leases"][0]["state"] == "ACTIVE"
    done = pool.release("g1", credits_spent=6.0, now=11.0, lease_token=lease["lease_token"])
    assert done["state"] == "RELEASED" and pool.snapshot()["accounts"][0]["credits"] == 94.0
    assert all("lease_token" not in row for row in pool.snapshot()["leases"])   # status never shows a token


def test_an_uncertain_lease_keeps_its_account_until_settled(tmp_path):
    pool = pool_with(tmp_path, "a1", cooldown_s=0.0)
    lease = pool.acquire("g1", cost_credits=6.0, now=10.0, holder="h1")
    pool.mark_uncertain(lease["lease_key"], lease_token=lease["lease_token"], reason="sender crashed")
    assert pool.acquire("g2", cost_credits=6.0, now=20.0, holder="h1") is None
    ok, why = pool.availability(cost_credits=6.0, now=20.0)
    assert not ok and f"lease g1 {UNCERTAIN}" in why
    assert not H.is_halted()   # a crash is not an account warning
    pool.settle(lease["lease_key"], credits_spent=6.0, now=30.0)
    assert pool.acquire("g2", cost_credits=6.0, now=31.0, holder="h1")["account_id"] == "a1"


def test_pinned_account_and_registered_profile(tmp_path):
    pool = pool_with(tmp_path, "a1", "a2")
    pool.register_account("a2", 100.0, cdp_endpoint="localhost:9444", project="proj-2")
    lease = pool.acquire("g1", cost_credits=6.0, now=10.0, holder="h", account_id="a2")
    assert (lease["account_id"], lease["cdp_endpoint"], lease["project"]) == ("a2", "http://127.0.0.1:9444", "proj-2")
    lease2, why = pool.acquire_or_reason("g2", cost_credits=6.0, now=10.0, holder="h", account_id="a2")
    assert lease2 is None and "a2 is busy" in why
    _, why = pool.acquire_or_reason("g3", cost_credits=6.0, now=10.0, holder="h", account_id="zz")
    assert "zz is not registered" in why


def test_the_migration_adds_holder_and_profile_columns_to_an_old_db(tmp_path):
    db = tmp_path / "old.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE accounts (account_id TEXT PRIMARY KEY, credits REAL NOT NULL, status TEXT NOT NULL, "
                     "quarantined_reason TEXT NOT NULL DEFAULT '', cooldown_until REAL NOT NULL DEFAULT 0.0, "
                     "updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE leases (lease_key TEXT PRIMARY KEY, film_id TEXT NOT NULL DEFAULT '', generation_id "
                     "TEXT NOT NULL, shot_version INTEGER NOT NULL DEFAULT 1, account_id TEXT NOT NULL, lease_token TEXT "
                     "NOT NULL DEFAULT '', leased_at REAL NOT NULL, state TEXT NOT NULL, settled_credits REAL NOT NULL "
                     "DEFAULT 0.0)")
        conn.execute("INSERT INTO accounts VALUES ('a1', 100, 'ACTIVE', '', 0, 'x')")
        conn.execute("INSERT INTO leases VALUES ('g1', '', 'g1', 1, 'a1', 'tok', 1.0, 'ACTIVE', 0)")
    pool = AccountLeasePool(db)
    AccountLeasePool(db)   # idempotent
    snap = pool.snapshot()
    assert snap["leases"][0]["holder"] == "" and snap["accounts"][0]["cdp_endpoint"] == ""
    assert pool.acquire("g1", cost_credits=6.0, now=10.0) is None   # an old ACTIVE lease has no holder: nobody gets it


def _race(db: str, key: str, barrier, out) -> None:
    pool = AccountLeasePool(Path(db), min_reserve_credits=0.0)
    barrier.wait()
    lease = pool.acquire(key, cost_credits=1.0, now=100.0)
    out.put((key, lease["account_id"] if lease else None))


def test_two_processes_race_for_the_only_account_and_exactly_one_wins(tmp_path):
    db = tmp_path / "race.sqlite3"
    AccountLeasePool(db, min_reserve_credits=0.0).register_account("only", 10.0)
    ctx = mp.get_context("spawn")
    barrier, out = ctx.Barrier(2), ctx.Queue()
    procs = [ctx.Process(target=_race, args=(str(db), key, barrier, out)) for key in ("film_a:g1_t1", "film_b:g1_t1")]
    for p in procs:
        p.start()
    results = [out.get(timeout=120) for _ in procs]
    for p in procs:
        p.join(timeout=60)
    assert sorted(r[1] is not None for r in results) == [False, True]
    assert [r[1] for r in results if r[1]] == ["only"]


# ---- generate() takes the lease ----------------------------------------------------------------------------------

def live(tmp_path, runner, estimate=100, **kw):
    pkg = kw.pop("pkg", None) or film(tmp_path, estimate)
    return pkg, G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                           backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=runner, **kw)


def test_live_send_without_a_registered_account_is_refused(tmp_path):
    runner = FakeRunner()
    _, done = live(tmp_path, runner)
    assert not done["sent"] and [r["code"] for r in done["refused"]] == ["NO_ACCOUNT_LEASE"] and not runner.calls
    assert "no registered account" in done["refused"][0]["detail"]
    assert json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))["refused"] == ["NO_ACCOUNT_LEASE"]


def test_dry_run_reports_lease_availability_and_takes_none(tmp_path):
    pkg = film(tmp_path, 100)
    dry = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=still(tmp_path), start_token="tok:abc",
                     backlog=backlog(tmp_path))
    assert dry["ready_to_send"] and [w["code"] for w in dry["payload"]["warnings"]] == ["NO_ACCOUNT_LEASE"]
    pool = L.machine_pool()
    pool.register_account("acct-1", 500.0)
    dry = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=still(tmp_path), start_token="tok:abc",
                     backlog=backlog(tmp_path))
    assert "NO_ACCOUNT_LEASE" not in [w["code"] for w in dry["payload"]["warnings"]] and pool.snapshot()["leases"] == []


def test_live_send_leases_releases_with_spent_credits_and_cooldown_blocks_the_next(tmp_path, monkeypatch):
    monkeypatch.setenv("AFP_LEASE_COOLDOWN_S", "600")
    pool = L.machine_pool()
    pool.register_account("acct-1", 500.0, cdp_endpoint="127.0.0.1:9555", project="proj-1")
    runner = FakeRunner()
    pkg, done = live(tmp_path, runner)
    assert done["sent"] and done["manifest_result"] == "PASSED" and len(runner.calls) == 1
    receipt = json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
    assert receipt["account"] == "acct-1" and receipt["lease_key"] == L.lease_key(pkg.header.film_id, "SC01_g1_t1", pkg.root)
    assert receipt["lease_holder"] and receipt["lease_db"] == str(default_db_path()) and "lease_token" not in receipt
    assert receipt["cdp"] == "http://127.0.0.1:9555" and receipt["project"] == "proj-1"
    snap = pool.snapshot()
    assert snap["leases"][0]["state"] == "RELEASED" and snap["leases"][0]["settled_credits"] == 8.0
    assert snap["accounts"][0]["credits"] == 492.0
    other = FakeRunner()
    _, second = live(tmp_path / "second_film", other)   # another film, same machine pool
    assert [r["code"] for r in second["refused"]] == ["NO_ACCOUNT_LEASE"] and not other.calls
    assert "acct-1 cools down" in second["refused"][0]["detail"]


def test_a_not_submitted_send_spends_nothing(tmp_path, flow_lease_account):
    live(tmp_path, FakeRunner("START_NOT_FOUND"))
    snap = flow_lease_account.snapshot()
    assert snap["leases"][0]["state"] == "RELEASED" and snap["leases"][0]["settled_credits"] == 0.0
    assert snap["accounts"][0]["credits"] == 1_000_000.0


def test_an_account_warning_quarantines_the_account_and_halts(tmp_path, flow_lease_account):
    _, done = live(tmp_path, FakeRunner("FLOW_ACCOUNT_WARNING"))
    assert done["sent"] and "auto_resend" not in done and H.is_halted()
    snap = flow_lease_account.snapshot()
    assert snap["accounts"][0]["status"] == "COOLDOWN_QUARANTINE" and snap["leases"][0]["state"] == UNCERTAIN
    assert any(e["source"] == "lease_pool" for e in H.read_halt()["events"])


class RaisingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, out):
        self.calls.append(argv)
        raise RuntimeError("controller died mid-send")


def test_a_runner_that_raises_leaves_the_lease_held_until_settled(tmp_path, flow_lease_account):
    with pytest.raises(RuntimeError, match="controller died"):
        pkg, _ = live(tmp_path, RaisingRunner())
    snap = flow_lease_account.snapshot()
    assert snap["leases"][0]["state"] == UNCERTAIN and "controller died" in snap["leases"][0]["note"]
    assert not H.is_halted()
    runner = FakeRunner()
    other = film(tmp_path / "other", 100)
    header = json.loads((Path(other.root) / "film.json").read_text(encoding="utf-8"))
    (Path(other.root) / "film.json").write_text(json.dumps({**header, "film_id": "film_other"}), encoding="utf-8")
    from film_pipeline.production.package import load_package
    _, again = live(tmp_path / "other", runner, pkg=load_package(other.root))   # the only account is not selectable
    assert [r["code"] for r in again["refused"]] == ["NO_ACCOUNT_LEASE"] and "busy" in again["refused"][0]["detail"]
    root = tmp_path / "film"
    with pytest.raises(ValueError, match="reconcile first"):   # the receipt is still PENDING
        L.settle_take(root, "SC01_g1_t1")
    # reconcile proved nothing was submitted (the overlay recovery.resolved_receipt reads) -> settle releases it
    intent = root / "takes" / "intents" / "SC01_g1_t1.intent.json"
    body = json.loads(intent.read_text(encoding="utf-8"))
    intent.write_text(json.dumps({**body, "result": "PRE_SUBMIT_ERROR CONTROLLER_NOT_DISPATCHED"}), encoding="utf-8")
    settled = L.settle_take(root, "SC01_g1_t1")
    assert settled["credits_spent"] == 0.0 and settled["lease"]["state"] == "RELEASED"
    _, third = live(tmp_path / "third", FakeRunner())
    assert third["sent"]


def test_settle_through_the_cli(tmp_path, flow_lease_account):
    with pytest.raises(RuntimeError):
        live(tmp_path, RaisingRunner())
    intent = tmp_path / "film" / "takes" / "intents" / "SC01_g1_t1.intent.json"
    body = json.loads(intent.read_text(encoding="utf-8"))
    intent.write_text(json.dumps({**body, "result": "FLOW_FAILED"}), encoding="utf-8")   # charged, no clip
    from film_pipeline.cli import main
    assert main(["lease", "settle", "--film", str(tmp_path / "film"), "--take", "SC01_g1_t1"]) == 0
    snap = flow_lease_account.snapshot()
    assert snap["leases"][0]["state"] == "RELEASED" and snap["leases"][0]["settled_credits"] == 8.0


def test_a_rehearsal_mock_leases_from_its_own_pool(tmp_path):
    pkg = film(tmp_path, 100)
    header = json.loads((Path(pkg.root) / "film.json").read_text(encoding="utf-8"))
    header["rehearsal"] = True
    (Path(pkg.root) / "film.json").write_text(json.dumps(header), encoding="utf-8")
    from film_pipeline.production.package import load_package
    pkg = load_package(pkg.root)
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path), runner=FakeRunner())   # a mock: no go-live, no machine pool
    assert done["sent"] and done["payload"]["account"] == L.REHEARSAL_ACCOUNT
    local = Path(pkg.root) / "takes" / "lease_pool.sqlite3"
    assert done["payload"]["lease_db"] == str(local)
    assert AccountLeasePool(local).snapshot()["leases"][0]["state"] == "RELEASED"
    assert not default_db_path().exists() or AccountLeasePool().snapshot()["leases"] == []


# ---- warning wording and the retired runner ----------------------------------------------------------------------

@pytest.mark.parametrize("text", ["We noticed some unusual activity on your account",
                                  "Chúng tôi nhận thấy hoạt động bất thường",
                                  "Please verify you are human", "Verify it's you", "Hãy xác minh bạn là người"])
def test_account_warning_wording_matches_the_pool_runner_set(text):
    import re
    runner_src = (ROOT / "src/film_pipeline/providers/_flow_ui/flow_pool_runner.py").read_text(encoding="utf-8")
    warn_re = re.compile(re.search(r'WARN_RE = re\.compile\(\s*r"([^"]+)"', runner_src).group(1), re.I)
    assert warn_re.pattern == FS.ACCOUNT_WARNING_PATTERN   # the same wording set as the retired pool runner
    assert FS.has_account_warning(text) and warn_re.search(text)
    assert "/" + FS.ACCOUNT_WARNING_PATTERN + "/i.test(t)" in FS.JS_JOB_STATE
    assert not FS.has_account_warning("a quiet scene at the front desk")


def test_flow_send_copies_stay_identical():
    pkg = ROOT / "src" / "film_pipeline" / "providers" / "_flow_ui" / "flow_send.py"
    assert (ROOT / "tools" / "drama_flow_ui" / "flow_send.py").read_bytes() == pkg.read_bytes()


def test_flow_pool_runner_refuses_to_send():
    pytest.importorskip("websockets")
    from film_pipeline.providers._flow_ui import flow_pool_runner as FPR
    assert FPR.main(["--account", "02", "--action", "submit"]) == 2
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "drama_flow_ui" / "flow_pool_runner.py")],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 2 and "afp-film generate" in done.stderr
