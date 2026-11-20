"""S1 Broker v2 (STUDIO_ARCHITECTURE §5-§6, §9): schema migration, exclusive batch leases, atomic admission against every
cap, day rollover, re-login bookkeeping, probes, HELD batches, halt and epoch fencing, F2 lock order, accounts CLI."""
import json
import math
import multiprocessing as mp
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from film_pipeline.agentic import broker as B
from film_pipeline.agentic.broker import UNCERTAIN, AdmitRequest, Broker, Child
from film_pipeline.agentic.lease_pool import AccountLeasePool
from film_pipeline.production import generate as G
from film_pipeline.production import halt as H

from test_production_generate import backlog, film, still

ROOT = Path(__file__).resolve().parents[1]
NO_CAPS = {"machine_caps": {}, "provider_caps": {}}


def req(key, *amounts, **kw):
    kw.setdefault("holder", "h")
    if kw.get("needs_account") is False:
        kw.setdefault("provider", "http-test")   # an account-less admission names its provider
    return AdmitRequest(lease_key=key, children=[Child(f"{key}#{i}", a, take_id=f"{key}#{i}")
                                                 for i, a in enumerate(amounts)], **kw)


# ---- migration from the step-4 pool -------------------------------------------------------------------------------

def _step4_db(db: Path) -> None:
    """A step-4 pool exactly as the step-4 code left it (v3 columns, the old unique index, no user_version)."""
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE accounts (account_id TEXT PRIMARY KEY, credits REAL NOT NULL, status TEXT NOT NULL, "
                     "quarantined_reason TEXT NOT NULL DEFAULT '', cooldown_until REAL NOT NULL DEFAULT 0.0, "
                     "updated_at TEXT NOT NULL, cdp_endpoint TEXT NOT NULL DEFAULT '', project TEXT NOT NULL DEFAULT '')")
        conn.execute("CREATE TABLE leases (lease_key TEXT PRIMARY KEY, film_id TEXT NOT NULL DEFAULT '', generation_id "
                     "TEXT NOT NULL, shot_version INTEGER NOT NULL DEFAULT 1, account_id TEXT NOT NULL, lease_token TEXT "
                     "NOT NULL DEFAULT '', leased_at REAL NOT NULL, state TEXT NOT NULL, settled_credits REAL NOT NULL "
                     "DEFAULT 0.0, holder TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '')")
        conn.execute("CREATE TABLE account_history (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, account_id "
                     "TEXT NOT NULL, action TEXT NOT NULL, by TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '', "
                     "prior_status TEXT NOT NULL DEFAULT '', prior_reason TEXT NOT NULL DEFAULT '')")
        conn.execute("CREATE UNIQUE INDEX idx_leases_active_account ON leases(account_id) WHERE state = 'ACTIVE'")
        conn.executemany("INSERT INTO accounts VALUES (?, ?, ?, ?, 0, 'x', '127.0.0.1:9555', 'p')", [
            ("a-active", 500.0, "ACTIVE", ""), ("a-uncertain", 500.0, "ACTIVE", ""),
            ("a-quarantined", 500.0, "COOLDOWN_QUARANTINE", "FLOW_ACCOUNT_WARNING unusual activity"),
            ("a-free", 500.0, "ACTIVE", "")])
        conn.executemany("INSERT INTO leases VALUES (?, 'f', ?, 1, ?, ?, 1000.0, ?, ?, 'holder-1', ?)", [
            ("f:g1_t1@p", "g1", "a-active", "tok-a", "ACTIVE", 0.0, ""),
            ("f:g2_t1@p", "g2", "a-uncertain", "tok-u", UNCERTAIN, 0.0, "send raised"),
            ("f:g3_t1@p", "g3", "a-quarantined", "tok-q", UNCERTAIN, 0.0, "FLOW_ACCOUNT_WARNING"),
            ("f:g4_t1@p", "g4", "a-free", "tok-r", "RELEASED", 8.0, "")])


def test_migration_keeps_every_active_uncertain_and_quarantined_lease(tmp_path):
    db = tmp_path / "pool.sqlite3"
    _step4_db(db)
    pool = AccountLeasePool(db, min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    AccountLeasePool(db, **NO_CAPS)   # idempotent
    snap = pool.snapshot()
    assert snap["schema_version"] == 2
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    states = {lease["lease_key"]: lease["state"] for lease in snap["leases"]}
    assert states == {"f:g1_t1@p": "ACTIVE", "f:g2_t1@p": UNCERTAIN, "f:g3_t1@p": UNCERTAIN, "f:g4_t1@p": "RELEASED"}
    assert next(a for a in snap["accounts"] if a["account_id"] == "a-quarantined")["status"] == "COOLDOWN_QUARANTINE"
    view = {a["account"]: a["state"] for a in pool.accounts_view(now=2000.0)}
    assert view == {"a-active": "BUSY", "a-uncertain": "HELD", "a-quarantined": "QUARANTINED", "a-free": "FREE"}
    # none of the three held accounts can be admitted; the free one can
    for acct in ("a-active", "a-uncertain", "a-quarantined"):
        out = pool.admit(req("new", 6.0, account_id=acct, now=2000.0))
        assert not out["ok"] and out["code"] == "NO_ACCOUNT_LEASE", out
    assert pool.admit(req("new", 6.0, now=2000.0))["lease"]["account_id"] == "a-free"
    # a migrated ACTIVE lease (phase unknown) is never released as unsent; its holder still releases it with the token
    assert pool.release_unsent("f:g1_t1@p", lease_token="tok-a") == {"released": [], "uncertain": ["f:g1_t1@p"]}
    with pytest.raises(ValueError):
        pool.release(lease_key="f:g1_t1@p", lease_token="wrong")
    assert pool.release(lease_key="f:g1_t1@p", lease_token="tok-a", credits_spent=8.0)["state"] == "RELEASED"
    # an uncertain one settles through the reconcile path
    assert pool.settle("f:g2_t1@p", credits_spent=0.0)["state"] == "RELEASED"
    assert {a["account"]: a["state"] for a in pool.accounts_view(now=2000.0)}["a-uncertain"] == "FREE"


# ---- exclusive leases across OS processes ------------------------------------------------------------------------

def _admit_worker(db: str, kwargs: dict, amounts: list, caps: dict, barrier, out) -> None:
    broker = Broker(Path(db), min_reserve_credits=0.0, cooldown_s=0.0, **caps)
    barrier.wait()
    got = broker.admit(req(kwargs.pop("lease_key"), *amounts, **kwargs))
    out.put((got["ok"], got.get("code", ""), (got.get("lease") or {}).get("account_id")))


def _race(db: Path, jobs: list[tuple[dict, list]], caps: dict) -> list[tuple]:
    ctx = mp.get_context("spawn")
    barrier, out = ctx.Barrier(len(jobs)), ctx.Queue()
    procs = [ctx.Process(target=_admit_worker, args=(str(db), kw, amounts, caps, barrier, out)) for kw, amounts in jobs]
    for p in procs:
        p.start()
    results = [out.get(timeout=180) for _ in procs]
    for p in procs:
        p.join(timeout=60)
    return results


def test_competing_processes_never_double_book_an_account(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, min_reserve_credits=0.0, **NO_CAPS)
    for acct in ("acct-1", "acct-2"):
        broker.register_account(acct, 1000.0)
    jobs = [({"lease_key": f"film{i}:g1_t1@p", "holder": f"h{i}", "film_id": f"film{i}"}, [1.0]) for i in range(6)]
    results = _race(db, jobs, NO_CAPS)
    won = [r[2] for r in results if r[0]]
    assert sorted(won) == ["acct-1", "acct-2"]
    assert all(r[1] == "NO_ACCOUNT_LEASE" for r in results if not r[0])
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM leases WHERE state = 'ACTIVE'").fetchone()[0] == 2


def test_a_reservation_race_never_overspends_a_cap(tmp_path):
    """Machine cap per unit aggregated across providers, per-provider cap, and per-film budget, under a race."""
    db = tmp_path / "pool.sqlite3"
    caps = {"machine_caps": {"VND": 10000}, "provider_caps": {"vilao": {"VND": 6000}}}
    Broker(db, **caps).import_legacy(tmp_path, [])   # nothing was spent before S1
    day = "2026-11-20"
    # 8 sends of 3,000 VND from 8 films on two providers: the vilao cap admits 2, the machine cap 3 in total
    jobs = [({"lease_key": f"film{i}:t@p", "holder": f"h{i}", "film_id": f"film{i}", "unit": "VND",
              "provider": "vilao" if i % 2 else "other-http", "needs_account": False, "day": day}, [3000.0])
            for i in range(8)]
    results = _race(db, jobs, caps)
    broker = Broker(db, **caps)
    assert sum(r[0] for r in results) == 3
    assert broker.daily_usage("VND", day) <= 10000 and broker.daily_usage("VND", day, provider="vilao") <= 6000
    assert {r[1] for r in results if not r[0]} <= {"BUDGET_DAILY_EXCEEDED", "PROVIDER_DAILY_EXCEEDED"}
    # one film's budget: 5 sends of 2,000 under a 5,000 cap (1,000 already in its ledger) admit exactly 2
    jobs = [({"lease_key": f"one:t{i}@p", "holder": f"h{i}", "film_id": "one", "film_key": "one@p", "unit": "VND",
              "provider": "x", "needs_account": False, "film_cap": 5000.0, "film_baseline": 1000.0,
              "day": "2026-11-21"}, [2000.0]) for i in range(5)]
    results = _race(db, jobs, NO_CAPS)
    assert sum(r[0] for r in results) == 2
    assert {r[1] for r in results if not r[0]} == {"BUDGET_EXCEEDED"}


def test_film_counted_takes_are_not_counted_twice_and_unpriced_or_unlimited(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    first = broker.admit(req("f:t1@p", 2000.0, unit="VND", needs_account=False, film_id="f", film_key="f@p",
                             film_cap=5000.0))
    assert first["ok"]
    # the film's ledger now counts f:t1@p#0 (its receipt): the reservation is not added again
    again = broker.admit(req("f:t2@p", 2900.0, unit="VND", needs_account=False, film_id="f", film_key="f@p",
                             film_cap=5000.0, film_baseline=2000.0, film_counted={"f:t1@p#0": 2000.0}))
    assert again["ok"]
    # a plain set of take ids gives no credit (fail closed): 2000 ledger + 2000 + 2900 + 100 > 5000
    assert broker.admit(req("f:t6@p", 100.0, unit="VND", needs_account=False, film_id="f", film_key="f@p",
                            film_cap=5000.0, film_baseline=2000.0,
                            film_counted=frozenset({"f:t1@p#0"})))["code"] == "BUDGET_EXCEEDED"
    assert broker.admit(req("f:t3@p", 1.0, unit="EUR", needs_account=False))["code"] == "NO_PRICE"
    assert broker.admit(req("f:t4@p", None, unit="VND", needs_account=False))["code"] == "NO_PRICE"
    assert broker.admit(req("f:t5@p", 1e9, unit="VND", needs_account=False, film_cap=math.inf))["ok"]


def test_unlimited_caps_in_the_package_and_routes():
    from film_pipeline.production.package import Budget
    assert math.isinf(Budget.model_validate({"caps": {"muse_requests": "unlimited"}}).cap_for("muse_requests"))
    assert B._cap_value("unlimited") is None and B._cap_value(None) is None and B._cap_value(5) == 5.0


# ---- day rollover ------------------------------------------------------------------------------------------------

def test_day_rollover_uses_the_day_stored_on_the_reservation(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", machine_caps={"VND": 10000}, provider_caps={})
    broker.import_legacy(tmp_path, [])
    a = broker.admit(req("a", 8000.0, unit="VND", needs_account=False, day="2026-11-20"))
    assert a["ok"]
    assert broker.admit(req("b", 5000.0, unit="VND", needs_account=False, day="2026-11-20"))["code"] == \
        "BUDGET_DAILY_EXCEEDED"
    b = broker.admit(req("b", 5000.0, unit="VND", needs_account=False, day="2026-11-21"))
    assert b["ok"]
    # settled on the next day, the spend stays on the day it was reserved
    broker.finish_child("a", lease_token=a["lease"]["lease_token"], child_key="a#0", outcome="PASSED", spent=8000.0)
    assert broker.daily_usage("VND", "2026-11-20") == 8000.0 and broker.daily_usage("VND", "2026-11-21") == 5000.0
    # a release frees the day's room
    broker.finish_child("b", lease_token=b["lease"]["lease_token"], child_key="b#0", outcome="NOT_SUBMITTED", spent=0.0)
    assert broker.daily_usage("VND", "2026-11-21") == 0.0
    # without an explicit day the local date of ``now`` is used
    ts = 1_800_000_000.0
    c = broker.admit(req("c", 1.0, unit="VND", needs_account=False, now=ts))
    assert c["lease"]["day"] == B.local_day(ts)


# ---- re-login bookkeeping survives a restart -----------------------------------------------------------------------

def test_relogin_throttle_survives_a_restart_and_two_failures_need_login(tmp_path):
    db = tmp_path / "pool.sqlite3"
    first = Broker(db, **NO_CAPS)
    first.register_account("m1", provider="muse", quota_mode="probed")
    assert first.claim_profile("m1", claimant="lane-A", epoch=1)["ok"]
    login = {"epoch": 1, "claimant": "lane-A"}
    assert first.before_login("m1", cause="UNUSUAL_ACTIVITY", now=1000.0, **login)["code"] == "RELOGIN_NOT_ALLOWED"
    assert first.before_login("m1", cause="AUTH_EXPIRED", now=1000.0, **login)["go"]
    first.record_login_result("m1", ok=False)
    with pytest.raises(ValueError, match="no re-login attempt is pending"):   # only an authorised attempt counts
        first.record_login_result("m1", ok=True)
    restarted = Broker(db, **NO_CAPS)   # a new process
    out = restarted.before_login("m1", cause="AUTH_EXPIRED", now=1000.0 + 3600, **login)
    assert out["code"] == "RELOGIN_THROTTLED"
    assert restarted.before_login("m1", cause="AUTH_EXPIRED", now=1000.0 + B.RELOGIN_INTERVAL_S + 1, **login)["go"]
    acct = Broker(db, **NO_CAPS).record_login_result("m1", ok=False)
    assert acct["status"] == "NEEDS_LOGIN" and acct["relogin_failures"] == 2
    again = Broker(db, **NO_CAPS)
    assert again.before_login("m1", cause="AUTH_EXPIRED", now=1e6, **login)["code"] == "ACCOUNT_NOT_ACTIVE"
    assert {a["account"]: a["state"] for a in again.accounts_view()}["m1"] == "NEEDS_LOGIN"
    assert not again.admit(req("k", 1.0, unit="muse_requests", provider="muse"))["ok"]


def test_a_successful_relogin_resets_the_failure_count(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    broker.claim_profile("m1", claimant="lane-A", epoch=1)
    t = 1000.0
    for ok, failures in ((False, 1), (True, 0), (False, 1)):
        assert broker.before_login("m1", cause="AUTH_EXPIRED", epoch=1, claimant="lane-A", now=t)["go"]
        acct = broker.record_login_result("m1", ok=ok)
        assert acct["relogin_failures"] == failures and acct["status"] == "ACTIVE"
        t += B.RELOGIN_INTERVAL_S + 1


def test_a_login_needs_the_current_epoch_and_the_lease_or_the_profile_claim(tmp_path):
    """Finding 4: a lane that lost its lease (or never had it) is never told to log in to an account another batch
    now uses, and an epoch is mandatory."""
    broker = Broker(tmp_path / "pool.sqlite3", cooldown_s=0.0, **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    broker.record_probe("m1", 80.0)
    first = broker.admit(req("k1", 1.0, unit="muse_requests", provider="muse", account_id="m1", epoch=1,
                             holder="lane-A"))["lease"]
    with pytest.raises(TypeError):   # no epoch, no login
        broker.before_login("m1", cause="AUTH_EXPIRED")    # type: ignore[call-arg]
    assert broker.before_login("m1", cause="AUTH_EXPIRED", epoch=1)["code"] == "NOT_OWNER"
    assert broker.before_login("m1", cause="AUTH_EXPIRED", epoch=1, lease_key="k1",
                               lease_token="forged")["code"] == "NOT_OWNER"
    assert broker.before_login("m1", cause="AUTH_EXPIRED", epoch=1, claimant="lane-A")["code"] == "NOT_OWNER"
    # the lease is settled and the account goes to another batch, same epoch: the old token is worthless
    broker.finish_child("k1", lease_token=first["lease_token"], child_key="k1#0", outcome="PASSED", spent=1.0)
    second = broker.admit(req("k2", 1.0, unit="muse_requests", provider="muse", account_id="m1", epoch=1,
                              holder="lane-B"))["lease"]
    stale = broker.before_login("m1", cause="AUTH_EXPIRED", epoch=1, lease_key="k1", lease_token=first["lease_token"])
    assert stale["code"] == "NOT_OWNER"
    assert broker.before_login("m1", cause="AUTH_EXPIRED", epoch=1, lease_key="k2",
                               lease_token=second["lease_token"])["go"]


# ---- probed quota ------------------------------------------------------------------------------------------------

def test_a_stale_or_low_probe_is_refused_with_a_reprobe_request(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed", probe_max_age_s=3600, reserve_pct=10)
    now = 100_000.0
    never = broker.admit(req("k", 1.0, unit="muse_requests", provider="muse", now=now))
    assert never["code"] == "NO_ACCOUNT_LEASE" and never["reprobe"] == ["m1"] and "never probed" in never["reason"]
    broker.record_probe("m1", 50.0, probed_at=now - 7200)
    stale = broker.admit(req("k", 1.0, unit="muse_requests", provider="muse", now=now))
    assert not stale["ok"] and stale["reprobe"] == ["m1"] and "re-probe" in stale["reason"]
    assert broker.accounts_view(now=now)[0]["quota"]["reprobe_requested"] is True
    broker.record_probe("m1", 5.0, probed_at=now)
    low = broker.admit(req("k", 1.0, unit="muse_requests", provider="muse", now=now))
    assert not low["ok"] and "below the reserve" in low["reason"]
    broker.record_probe("m1", 40.0, probed_at=now)
    assert broker.accounts_view(now=now)[0]["quota"]["reprobe_requested"] is False
    assert broker.admit(req("k", 1.0, unit="muse_requests", provider="muse", now=now))["ok"]


# ---- batches -----------------------------------------------------------------------------------------------------

def test_an_ambiguous_child_keeps_the_account_held_until_settled(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", cooldown_s=0.0, **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    broker.record_probe("m1", 80.0)
    lease = broker.admit(req("f:batch1@p", 1.0, 1.0, 1.0, unit="muse_requests", provider="muse",
                             film_id="f"))["lease"]
    tok = lease["lease_token"]
    assert [c["child_key"] for c in lease["children"]] == ["f:batch1@p#0", "f:batch1@p#1", "f:batch1@p#2"]
    for c in lease["children"]:
        assert broker.before_enter("f:batch1@p", lease_token=tok, child_key=c["child_key"])["go"]
    # never a second Enter for one child
    assert broker.before_enter("f:batch1@p", lease_token=tok, child_key="f:batch1@p#0")["code"] == "CHILD_NOT_PREPARING"
    assert broker.accounts_view()[0]["in_flight"] == "3/6"
    broker.finish_child("f:batch1@p", lease_token=tok, child_key="f:batch1@p#0", outcome="PASSED", spent=1.0)
    broker.finish_child("f:batch1@p", lease_token=tok, child_key="f:batch1@p#1", outcome="AMBIGUOUS", spent=1.0)
    broker.finish_child("f:batch1@p", lease_token=tok, child_key="f:batch1@p#2", outcome="PROVIDER_FAILED", spent=0.0)
    view = broker.accounts_view()[0]
    assert view["state"] == "HELD" and view["in_flight"] == "1/6" and view["held_reason"] == "AMBIGUOUS"
    assert not broker.admit(req("f:batch2@p", 1.0, unit="muse_requests", provider="muse"))["ok"]
    assert broker.release_unsent("f:batch1@p", lease_token=tok)["uncertain"] == ["f:batch1@p#1"]
    assert broker.settle_child("f:batch1@p", child_key="f:batch1@p#1", spent=1.0)["state"] == "RELEASED"
    assert broker.accounts_view()[0]["state"] == "FREE"
    assert broker.daily_usage("muse_requests", lease["day"]) == 2.0


def test_a_batch_respects_slots_one_film_one_kind(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    broker.register_account("flow-1", 1000.0)
    out = broker.admit(req("k", 1.0, 1.0, provider="flow"))
    assert out["code"] == "NO_ACCOUNT_LEASE" and "1 video slot" in out["reason"]
    dup = AdmitRequest(lease_key="k", children=[Child("a", 1.0, shot_key="g1:v1"), Child("b", 1.0, shot_key="g1:v1")])
    assert broker.admit(dup)["code"] == "BATCH_INVALID"
    assert broker.admit(req("k", 1.0, job_kind="audio"))["code"] == "BATCH_INVALID"


def test_preparing_children_release_but_submitting_ones_are_held(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", cooldown_s=0.0, **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    broker.record_probe("m1", 80.0)
    lease = broker.admit(req("k", 1.0, 1.0, unit="muse_requests", provider="muse"))["lease"]
    tok = lease["lease_token"]
    assert broker.before_enter("k", lease_token=tok, child_key="k#0")["go"]
    assert broker.release_unsent("k", lease_token=tok) == {"released": ["k#1"], "uncertain": ["k#0"]}
    with pytest.raises(ValueError):
        broker.release_unsent("k", lease_token="not-the-token")
    broker.hold_child("k", lease_token=tok, reason="crash after the Enter")
    assert broker.accounts_view()[0]["state"] == "HELD"


# ---- halt and epoch fencing --------------------------------------------------------------------------------------

def test_a_halt_between_admission_and_enter_gives_not_sent(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    broker.register_account("flow-1", 1000.0)
    lease = broker.admit(req("k", 6.0))["lease"]
    H.set_halt("another account warned", source="test")
    out = broker.before_enter("k", lease_token=lease["lease_token"], child_key="k#0")
    assert out == {"go": False, "code": "PRODUCTION_HALT", "reason": out["reason"]}
    snap = broker.snapshot()
    assert snap["leases"][0]["state"] == "RELEASED" and snap["accounts"][0]["credits"] == 1000.0
    with sqlite3.connect(broker.db_path) as conn:
        assert conn.execute("SELECT outcome FROM lease_children").fetchone()[0] == "NOT_SENT"
        assert conn.execute("SELECT state FROM reservations").fetchone()[0] == "RELEASED"
    assert broker.admit(req("k2", 6.0))["code"] == "PRODUCTION_HALT"
    assert broker.before_login("flow-1", cause="AUTH_EXPIRED", epoch=1)["code"] == "PRODUCTION_HALT"


def test_set_halt_takes_the_broker_lock(tmp_path):
    broker = Broker(**NO_CAPS)   # the machine broker: same state dir as the halt
    conn = sqlite3.connect(broker.db_path, timeout=0.1, isolation_level=None)
    conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            with H.broker_lock():
                pass
    finally:
        conn.execute("ROLLBACK")
        conn.close()
    H.set_halt("now it can", source="test")
    assert H.is_halted()


def test_an_old_epoch_is_refused(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", cooldown_s=600.0, **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    broker.record_probe("m1", 80.0)
    assert broker.claim_profile("m1", claimant="lane-A", epoch=1)["ok"]
    second = broker.claim_profile("m1", claimant="lane-B", epoch=1)
    assert second["code"] == "PROFILE_CLAIMED"   # refused at once, never queued
    lease = broker.admit(req("k", 1.0, 1.0, unit="muse_requests", provider="muse", account_id="m1", epoch=1))["lease"]
    assert broker.before_enter("k", lease_token=lease["lease_token"], child_key="k#0", epoch=1)["go"]
    assert broker.bump_epoch("m1") == {"m1": 2}   # the lane is fenced
    out = broker.before_enter("k", lease_token=lease["lease_token"], child_key="k#1", epoch=1)
    assert out["code"] == "STALE_EPOCH"
    assert broker.claim_profile("m1", claimant="lane-A", epoch=1)["code"] == "STALE_EPOCH"
    assert broker.claim_profile("m1", claimant="lane-B", epoch=2)["ok"]   # the old claim is void
    assert broker.before_login("m1", cause="AUTH_EXPIRED", epoch=1, claimant="lane-A")["code"] == "STALE_EPOCH"
    broker.settle_child("k", spent=1.0)
    assert broker.admit(req("k2", 1.0, unit="muse_requests", provider="muse", account_id="m1",
                            epoch=1))["code"] == "STALE_EPOCH"


def test_a_captcha_quarantines_the_account_holds_its_children_and_halts(tmp_path):
    broker = Broker(**NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    broker.record_probe("m1", 80.0)
    lease = broker.admit(req("k", 1.0, 1.0, unit="muse_requests", provider="muse"))["lease"]
    assert broker.before_enter("k", lease_token=lease["lease_token"], child_key="k#0")["go"]
    broker.account_warning("m1", "a CAPTCHA appeared", kind="CAPTCHA")
    assert H.is_halted() and H.read_halt()["source"] == "lease_pool"
    view = broker.accounts_view()[0]
    assert view["state"] == "QUARANTINED"
    assert broker.snapshot()["leases"][0]["state"] == UNCERTAIN
    # nothing in flight is released as unsent after a warning
    assert broker.release_unsent("k", lease_token=lease["lease_token"])["released"] == []


# ---- generate() through the broker -------------------------------------------------------------------------------

class HaltingRunner:
    """Sets the halt after admission, then reaches the pre-Enter checkpoint like the real sender."""
    takes_before_submit = True

    def __init__(self):
        self.submitted = False

    def __call__(self, argv, out, before_submit):
        H.set_halt("FLOW_ACCOUNT_WARNING on another account", source="test")
        before_submit({"project": ""})
        self.submitted = True
        return {"result": "PASSED"}


def test_generate_a_halt_after_admission_is_not_sent(tmp_path, flow_lease_account):
    pkg = film(tmp_path, 100)
    runner = HaltingRunner()
    with pytest.raises(RuntimeError, match="PRODUCTION_HALT"):
        G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                   backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=runner)
    assert not runner.submitted
    snap = flow_lease_account.snapshot()
    assert [lease["state"] for lease in snap["leases"]] == ["RELEASED"]
    receipt = json.loads((pkg.root / "takes" / "intents" / "SC01_g1_t1.intent.json").read_text(encoding="utf-8"))
    assert receipt["dispatch_phase"] == "PREPARING" and receipt["broker"] is True
    with sqlite3.connect(flow_lease_account.db_path) as conn:
        assert conn.execute("SELECT outcome FROM lease_children").fetchone()[0] == "NOT_SENT"


def test_generate_never_takes_the_broker_inside_film_lock(tmp_path, flow_lease_account, monkeypatch):
    """F2: film_lock and the broker transaction are leaf locks; neither is taken while the other is held."""
    from test_production_generate import FakeRunner
    depth = {"film": 0}
    real = G.film_lock

    @contextmanager
    def counting(*a, **kw):
        with real(*a, **kw):
            depth["film"] += 1
            try:
                yield
            finally:
                depth["film"] -= 1

    real_tx = Broker._tx

    @contextmanager
    def guarded_tx(self, conn):
        assert depth["film"] == 0, "a broker transaction inside film_lock"
        with real_tx(self, conn):
            yield

    monkeypatch.setattr(G, "film_lock", counting)
    monkeypatch.setattr(Broker, "_tx", guarded_tx)
    runner = FakeRunner()
    done = G.generate(film(tmp_path, 100), "SC01_g1", dry_run=False, stills_dir=still(tmp_path),
                      start_token="tok:abc", backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=runner)
    assert done["sent"] and runner.calls
    assert flow_lease_account.snapshot()["leases"][0]["state"] == "RELEASED"


def test_generate_reserves_against_the_machine_daily_cap(tmp_path, flow_lease_account, monkeypatch):
    from test_production_generate import FakeRunner
    monkeypatch.setattr(B, "default_caps", lambda: ({"credits": 10.0}, {}))
    # another film already reserved 5 credits today; this send's 8 would pass the cap
    broker = Broker()
    broker.import_legacy(tmp_path, [])
    assert broker.admit(req("other:t1@p", 5.0, film_id="other", needs_account=False, provider="vilao"))["ok"]
    runner = FakeRunner()
    done = G.generate(film(tmp_path, 100), "SC01_g1", dry_run=False, stills_dir=still(tmp_path),
                      start_token="tok:abc", backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=runner)
    assert not done["sent"] and [r["code"] for r in done["refused"]] == ["BUDGET_DAILY_EXCEEDED"] and not runner.calls


# ---- accounts CLI ------------------------------------------------------------------------------------------------

def test_accounts_cli_lists_by_id_and_label_and_never_prints_a_profile(tmp_path):
    db = tmp_path / "pool.sqlite3"

    def cli(*args):
        done = subprocess.run([sys.executable, "-m", "film_pipeline.cli", "accounts", *args, "--db", str(db)],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)
        return done.returncode, done.stdout

    code, out = cli("register", "--account", "flow-1", "--label", "Flow one", "--credits", "500",
                    "--cdp-endpoint", "127.0.0.1:9555", "--project", "proj-secret")
    assert code == 0 and "9555" not in out and "proj-secret" not in out
    code, out = cli("set-state", "--account", "flow-1", "--state", "NEEDS_LOGIN", "--by", "agent:t", "--reason", "expired")
    assert code == 0
    code, out = cli("list")
    body = json.loads(out)
    assert code == 0 and body["readonly"] is True and "9555" not in out and "cookie" not in out.lower()
    assert body["accounts"] == [{"account": "flow-1", "label": "Flow one", "provider": "flow", "state": "NEEDS_LOGIN",
                                 "film": "", "in_flight": "0/1", "job_kind": "video",
                                 "quota": {"mode": "constant", "unit": "credits", "remaining": 500.0,
                                           "daily_quota": None},
                                 "epoch": 1, "held_reason": "expired", "relogin_failures": 0}]
    code, out = cli("set-state", "--account", "flow-1", "--state", "BUSY", "--by", "agent:t", "--reason", "nope")
    assert code == 1 and "BUSY" in out


# ---- Codex review 1 (2026-11-20) ---------------------------------------------------------------------------------

def test_admission_is_refused_until_the_pre_s1_spend_is_imported_and_the_import_is_deduplicated(tmp_path):
    """Finding 1: legacy receipts are imported once (durable dedup) before any capped admission."""
    broker = Broker(tmp_path / "pool.sqlite3", machine_caps={"VND": 50000}, provider_caps={})
    early = broker.admit(req("a", 4158.0, unit="VND", needs_account=False, provider="vilao", day="2026-11-20"))
    assert early["code"] == "LEGACY_IMPORT_PENDING"
    films = tmp_path / "films"
    root = Broker.legacy_root_key(films)
    pending = broker.admit(req("a", 4158.0, unit="VND", needs_account=False, provider="vilao", day="2026-11-20",
                               legacy_root=root))
    assert pending["code"] == "LEGACY_IMPORT_PENDING"
    row = {"key": "pkg:X_t1", "lease_key": "", "take_id": "X_t1", "account": "", "film_key": "other@pkg",
           "provider": "vilao", "unit": "VND", "amount": 48000.0, "day": "2026-11-20"}
    broker.import_legacy(films, [row])
    broker.import_legacy(films, [row])   # a second import never adds it again
    assert broker.daily_usage("VND", "2026-11-20") == 48000.0
    out = broker.admit(req("a", 4158.0, unit="VND", needs_account=False, provider="vilao", day="2026-11-20",
                           legacy_root=root))
    assert out["code"] == "BUDGET_DAILY_EXCEEDED"
    # the receipt resolved as not charged since: the same row is updated, the room comes back
    broker.import_legacy(films, [{**row, "amount": 0.0}])
    assert broker.daily_usage("VND", "2026-11-20") == 0.0
    assert broker.admit(req("a", 4158.0, unit="VND", needs_account=False, provider="vilao", day="2026-11-20",
                            legacy_root=root))["ok"]


def test_a_receipt_whose_step4_lease_was_migrated_is_not_imported_twice(tmp_path):
    db = tmp_path / "pool.sqlite3"
    _step4_db(db)
    broker = Broker(db, **NO_CAPS)
    out = broker.import_legacy(tmp_path, [{"key": "p:g4_t1", "lease_key": "f:g4_t1@p", "take_id": "g4_t1",
                                           "provider": "flow", "unit": "credits", "amount": 8.0, "day": "1970-01-01"}])
    assert out["imported"] == 0 and out["skipped_migrated"] == 1 and out["priced_migrated"] == 0


def test_an_open_step4_send_counts_at_its_receipt_price_and_blocks_capped_admission_until_priced(tmp_path):
    """Codex R2-1: a migrated open reservation has no price until its receipt is imported; then it counts (held)."""
    db = tmp_path / "pool.sqlite3"
    _step4_db(db)
    today = B.local_day()
    pool = AccountLeasePool(db, min_reserve_credits=0.0, cooldown_s=0.0, machine_caps={"credits": 10.0},
                            provider_caps={})
    pool.import_legacy(tmp_path / "elsewhere", [])
    refused = pool.admit(req("n1", 4.0, film_id="f2"))
    assert refused["code"] == "LEGACY_IMPORT_PENDING" and "no known price" in refused["reason"]
    assert pool.admit(req("n0", 4.0, film_id="f2", needs_account=False, unit="muse_requests"))["ok"]   # uncapped unit
    rows = [{"key": f"p:{g}_t1", "lease_key": f"f:{g}_t1@p", "take_id": f"{g}_t1", "provider": "flow",
             "unit": "credits", "amount": 3.0 if g == "g2" else 0.0, "price": 3.0, "day": today}
            for g in ("g1", "g2", "g3", "g4")]
    for _ in range(2):   # idempotent: priced once, never added
        out = pool.import_legacy(tmp_path, rows)
        assert out == {**out, "imported": 0, "skipped_migrated": 4, "priced_migrated": 3}
        assert pool.daily_usage("credits") == 9.0   # three open sends at 3; the settled one stays on its own day
    over = pool.admit(req("n1", 4.0, film_id="f2"))
    assert over["code"] == "BUDGET_DAILY_EXCEEDED", over
    assert pool.admit(req("n2", 1.0, film_id="f2"))["ok"]
    snap = {r["lease_key"]: r for r in pool.snapshot()["leases"]}
    assert snap["f:g2_t1@p"]["state"] == UNCERTAIN and snap["f:g1_t1@p"]["state"] == "ACTIVE"   # custody kept


def _take_req(key, take, amount, **kw):
    kw.setdefault("film_cap", 10.0)
    kw.setdefault("film_baseline", 4.0)
    kw.setdefault("film_counted", {"old": 4.0})
    return AdmitRequest(lease_key=key, children=[Child(f"{key}#0", amount, take_id=take)], holder="h",
                        film_id="f", film_key="f@p", needs_account=False, provider="http-test", **kw)


def test_a_reused_take_id_cannot_slip_past_the_film_budget(tmp_path):
    """Codex R2-2: take ids decide what the ledger already covers, so one take id is one live reservation."""
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    ledger = pool.admit(_take_req("L0", "old", 4.0))
    assert ledger["code"] == "TAKE_REUSED" and "money ledger" in ledger["reason"]
    first = pool.admit(_take_req("L1", "new", 4.0))
    assert first["ok"]
    assert pool.admit(_take_req("L1", "new", 4.0))["reused"]          # the exact replay stays idempotent
    again = pool.admit(_take_req("L2", "new", 4.0))
    assert again["code"] == "TAKE_REUSED" and "L1" in again["reason"]
    assert pool.admit(_take_req("L3", "other", 4.0))["code"] == "BUDGET_EXCEEDED"   # 4 ledger + 4 held + 4 > 10
    pool.release_unsent("L1", lease_token=first["lease"]["lease_token"])
    assert pool.admit(_take_req("L4", "new", 4.0))["ok"]               # a released take may be sent again
    # without a film budget take ids do not matter (the step-4 facade keys takes by generation id)
    assert pool.admit(_take_req("L5", "new", 1.0, film_cap=None))["ok"]


def test_reservations_sharing_a_ledger_take_id_are_all_counted(tmp_path):
    """Codex R3-1: when rows share a take id (made with no film budget) the ledger's row is unknown: count them all."""
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    for key, amount in (("D1", 8.0), ("D2", 2.0)):
        assert pool.admit(_take_req(key, "old", amount, film_cap=None))["ok"]
    out = pool.admit(_take_req("D3", "x", 1.0, film_baseline=2.0, film_cap=12.0, film_counted={"old": 2.0}))
    # 2 ledger + 8 + 2 (both "old" rows: which one the ledger covers is unknown) + 1 > 12
    assert out["code"] == "BUDGET_EXCEEDED" and "12 spent" in out["reason"]
    single = AccountLeasePool(tmp_path / "one.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    assert single.admit(_take_req("S1", "old", 4.0, film_cap=None))["ok"]
    assert single.admit(_take_req("S2", "x", 6.0))["ok"]   # the one "old" row is the ledger's 4: 4 + 6 <= 10


def test_a_replay_must_repeat_the_admission_exactly(tmp_path):
    """Codex R3-2: the same key and holder with another price, child, unit or scope is not a replay."""
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    assert pool.admit(_take_req("R1", "t1", 1.0, film_cap=1.0, film_baseline=0.0))["ok"]
    assert pool.admit(_take_req("R1", "t1", 1.0, film_cap=1.0, film_baseline=0.0))["reused"]
    pricier = pool.admit(_take_req("R1", "t1", 9.0, film_cap=1.0, film_baseline=0.0))
    assert pricier["code"] == "LEASE_HELD" and "children or prices" in pricier["reason"]
    other_unit = pool.admit(_take_req("R1", "t1", 1.0, film_cap=1.0, film_baseline=0.0, unit="VND"))
    assert other_unit["code"] == "LEASE_HELD" and "unit" in other_unit["reason"]


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_a_negative_or_non_finite_spend_is_refused_and_changes_nothing(tmp_path, bad):
    """Codex R3-3: a malformed settlement never releases a reservation or restores cap capacity."""
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    pool.register_account("a1", 100.0)
    lease = pool.admit(req("N1", 6.0, film_id="f"))["lease"]
    child = lease["children"][0]["child_key"]
    assert pool.before_enter("N1", lease_token=lease["lease_token"], child_key=child)["go"]
    with pytest.raises(ValueError, match="finite amount >= 0"):
        pool.finish_child("N1", lease_token=lease["lease_token"], child_key=child, outcome="PASSED", spent=bad)
    with pytest.raises(ValueError, match="finite amount >= 0"):
        pool.settle_child("N1", spent=bad)
    assert pool.daily_usage("credits") == 6.0   # still reserved
    assert pool.finish_child("N1", lease_token=lease["lease_token"], child_key=child, outcome="PASSED", spent=6.0)
    assert pool.daily_usage("credits") == 6.0


def test_legacy_rows_read_pre_s1_receipts_only(tmp_path):
    from film_pipeline.production import leases as L
    intents = tmp_path / "films" / "a" / "takes" / "intents"
    intents.mkdir(parents=True)
    base = {"sent": True, "result": "PASSED", "provider": "vilao", "provider_model": "h3-480p", "cost_unit": "VND",
            "expected_cost": 4158, "sent_on": "2026-11-19", "film_id": "a"}
    (intents / "g_t1.intent.json").write_text(json.dumps(base), encoding="utf-8")
    (intents / "g_t2.intent.json").write_text(json.dumps({**base, "broker": True}), encoding="utf-8")   # in the broker
    (intents / "g_t3.intent.json").write_text(json.dumps({**base, "sent": False}), encoding="utf-8")    # a dry run
    (intents / "g_t4.intent.json").write_text("{not json", encoding="utf-8")
    rows = L.legacy_rows(tmp_path / "films")
    assert [(r["take_id"], r["unit"], r["amount"], r["day"]) for r in rows] == [("g_t1", "VND", 4158.0, "2026-11-19")]
    assert rows[0]["film_key"] == L.film_scope("a", tmp_path / "films" / "a")


def test_a_provider_inferred_from_the_account_is_held_to_its_daily_cap(tmp_path):
    """Finding 2: the step-4 API passes no provider; the account's provider cap still applies, in the transaction."""
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0,
                            machine_caps={}, provider_caps={"flow": {"credits": 10.0}})
    pool.import_legacy(tmp_path, [])
    for acct in ("flow-1", "flow-2"):
        pool.register_account(acct, 1000.0)
    first, _ = pool.acquire_or_reason("g1", cost_credits=6.0, film_id="f", holder="h1")
    assert first is not None and first["provider"] == "flow"
    second, why = pool.acquire_or_reason("g2", cost_credits=6.0, film_id="f", holder="h2")
    assert second is None and "daily cap 10" in why
    assert pool.admit(req("g3", 6.0, film_id="f"))["code"] == "PROVIDER_DAILY_EXCEEDED"
    assert pool.daily_usage("credits", provider="flow") == 6.0
    ok, why = pool.availability(cost_credits=6.0)
    assert not ok and "daily cap" in why


def _muse_film(tmp_path, caps):
    from film_pipeline.production.package import load_package
    pkg = film(tmp_path, 100)
    header = json.loads((pkg.root / "film.json").read_text(encoding="utf-8"))
    header.setdefault("budget", {})["caps"] = caps
    (pkg.root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    return load_package(pkg.root)


def test_the_lane_api_resolves_the_film_budget_and_fails_closed(tmp_path, monkeypatch):
    """Finding 3: broker_api.acquire takes the film package; no package or no cap refuses; an exhausted budget
    refuses; the scope is the one direct generate uses."""
    from film_pipeline.agentic import broker_api as api
    from film_pipeline.production import leases as L
    monkeypatch.setenv("AFP_LEASE_COOLDOWN_S", "0")
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, cooldown_s=0.0, **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    broker.record_probe("m1", 80.0)
    kids = [{"child_key": "c1", "amount": 1.0}, {"child_key": "c2", "amount": 1.0}]
    common = {"unit": "muse_requests", "provider": "muse", "db": db}
    assert api.acquire("m1", "k", kids, film_root=None, **common)["code"] == "FILM_BUDGET_UNAVAILABLE"
    assert api.acquire("m1", "k", kids, film_root=tmp_path / "nope", **common)["code"] == "FILM_BUDGET_UNAVAILABLE"
    none = _muse_film(tmp_path / "none", {})
    assert api.acquire("m1", "k", kids, film_root=none.root, **common)["code"] == "BUDGET_NOT_SET"
    small = _muse_film(tmp_path / "small", {"muse_requests": 3})
    got = api.acquire("m1", "k", kids, film_root=small.root, **common)
    assert got["ok"] and got["lease"]["film_id"] == small.header.film_id
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT DISTINCT film_key FROM reservations WHERE lease_token != 'legacy'").fetchall() == \
            [(L.film_scope(small.header.film_id, small.root),)]
    token = got["lease"]["lease_token"]
    for c in ("c1", "c2"):
        assert api.check_before_enter("k", token, c, db=db)["ok"]
        assert api.mark("k", token, c, "PASSED", spent=1.0, db=db)["ok"]
    over = api.acquire("m1", "k2", kids, film_root=small.root, **common)   # 2 spent + 2 > 3
    assert over["code"] == "BUDGET_EXCEEDED"
    unlimited = _muse_film(tmp_path / "unl", {"muse_requests": "unlimited"})
    assert api.acquire("m1", "k3", kids, film_root=unlimited.root, **common)["ok"]


def test_lease_settle_never_takes_the_broker_inside_film_lock(tmp_path, flow_lease_account, monkeypatch):
    """Finding 5 (F2): `afp-film lease settle` reads the receipt under film_lock and settles after releasing it."""
    from film_pipeline import cli
    from film_pipeline.production import runtime
    from test_production_generate import FakeRunner
    pkg = film(tmp_path, 100)
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=FakeRunner())
    assert done["sent"]
    depth = {"film": 0, "tx": 0}
    real = runtime.film_lock

    @contextmanager
    def counting(*a, **kw):
        with real(*a, **kw):
            depth["film"] += 1
            try:
                yield
            finally:
                depth["film"] -= 1

    real_tx = Broker._tx

    @contextmanager
    def guarded_tx(self, conn):
        assert depth["film"] == 0, "a broker transaction inside film_lock"
        depth["tx"] += 1
        with real_tx(self, conn):
            yield

    monkeypatch.setattr(runtime, "film_lock", counting)
    monkeypatch.setattr(Broker, "_tx", guarded_tx)
    assert cli.main(["lease", "settle", "--film", str(pkg.root), "--take", "SC01_g1_t1"]) == 0
    assert depth["tx"] >= 1


def _api(db, *args):
    done = subprocess.run([sys.executable, "-m", "film_pipeline.cli", "broker", *args, "--db", str(db)],
                          cwd=ROOT, capture_output=True, text=True, timeout=180)
    return done.returncode, json.loads(done.stdout)


def test_an_external_lane_process_drives_the_broker_api(tmp_path):
    """S1 item 5: the public API from a separate OS process (the wrapped Muse pool_runner will call it this way): JSON
    out, stable exit codes, only account ids cross it."""
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, cooldown_s=0.0)
    broker.register_account("m1", provider="muse", quota_mode="probed", cdp_endpoint="127.0.0.1:9777")
    pkg = _muse_film(tmp_path, {"muse_requests": "unlimited"})
    code, out = _api(db, "probe", "--account", "m1", "--weekly-remaining-pct", "80")
    assert code == 0 and out["ok"]
    code, out = _api(db, "claim", "--account", "m1", "--claimant", "lane-1", "--epoch", "1")
    assert code == 0
    code, out = _api(db, "claim", "--account", "m1", "--claimant", "lane-2", "--epoch", "1")
    assert code == 1 and out["code"] == "PROFILE_CLAIMED"
    batch = ["--account", "m1", "--provider", "muse", "--unit", "muse_requests", "--lease-key", "B1",
             "--child", "s1=1", "--child", "s2=1", "--child", "s3=1"]
    code, out = _api(db, "acquire", *batch)
    assert code == 1 and out["code"] == "FILM_BUDGET_UNAVAILABLE"   # no film: fail closed
    code, out = _api(db, "acquire", *batch, "--film", str(pkg.root), "--epoch", "1", "--holder", "lane-1")
    assert code == 0 and out["lease"]["account_id"] == "m1" and len(out["lease"]["children"]) == 3
    assert "9777" not in json.dumps(out) and "cdp" not in json.dumps(out)
    token = out["lease"]["lease_token"]
    code, out = _api(db, "check", "--lease-key", "B1", "--token", token, "--child", "s1", "--epoch", "1")
    assert code == 0 and out["phase"] == "SUBMITTING"
    code, out = _api(db, "mark", "--lease-key", "B1", "--token", token, "--child", "s1", "--state", "PASSED",
                     "--spent", "1")
    assert code == 0
    code, out = _api(db, "check", "--lease-key", "B1", "--token", token, "--child", "s2", "--epoch", "1")
    assert code == 0
    code, out = _api(db, "mark", "--lease-key", "B1", "--token", token, "--child", "s2", "--state", "AMBIGUOUS",
                     "--reason", "auth expired after Enter")
    assert code == 0 and out["lease_state"] == UNCERTAIN
    code, out = _api(db, "release", "--lease-key", "B1", "--token", "wrong")
    assert code == 3 and out["code"] == "TOKEN_MISMATCH"
    code, out = _api(db, "release", "--lease-key", "B1", "--token", token)
    assert code == 0 and out["released"] == ["s3"] and out["uncertain"] == ["s2"]   # past the Enter: held
    assert {a["account"]: a["state"] for a in Broker(db).accounts_view()}["m1"] == "HELD"
    code, out = _api(db, "login-check", "--account", "m1", "--cause", "AUTH_EXPIRED")
    assert code == 2 and out["code"] == "USAGE"   # no epoch, no login
    code, out = _api(db, "login-check", "--account", "m1", "--cause", "AUTH_EXPIRED", "--epoch", "1",
                     "--lease-key", "B1", "--token", token)
    assert code == 0 and out["ok"]
    code, out = _api(db, "login-result", "--account", "m1", "--result", "ok")
    assert code == 0 and out["relogin_failures"] == 0
    code, out = _api(db, "settle", "--lease-key", "B1", "--child", "s2", "--spent", "1", "--reason", "reconciled")
    assert code == 0 and out["lease_state"] == "RELEASED"
    code, out = _api(db, "halt", "--provider", "muse", "--account", "m1", "--kind", "CAPTCHA", "--reason", "captcha")
    assert code == 0 and out["halted"] and H.is_halted()
    code, out = _api(db, "acquire", *batch[:-4], "--film", str(pkg.root))
    assert code == 1 and out["code"] == "PRODUCTION_HALT"
    assert {a["account"]: a["state"] for a in Broker(db).accounts_view()}["m1"] == "QUARANTINED"


def test_a_database_error_is_a_json_error_with_exit_3_not_a_traceback(tmp_path, monkeypatch):
    """Codex R2-3: a busy or broken broker DB keeps the public contract (code ERROR, exit 3)."""
    from film_pipeline.agentic import broker_api as A

    def busy(self, *a, **k):
        raise sqlite3.OperationalError("database is locked")

    db = tmp_path / "pool.sqlite3"
    Broker(db).register_account("m1", provider="muse", quota_mode="probed")
    monkeypatch.setattr(Broker, "record_probe", busy)
    out = A.probe("m1", weekly_remaining_pct=50.0, db=db)
    assert out["ok"] is False and out["code"] == "ERROR" and "database is locked" in out["reason"]
    assert A.exit_code(out) == 3
    broken = tmp_path / "not-a-db"
    broken.mkdir()
    code, body = _api(broken, "probe", "--account", "m1", "--weekly-remaining-pct", "50")
    assert code == 3 and body["code"] == "ERROR"


def test_a_ledger_take_is_credited_only_with_its_verified_amount_in_the_unit(tmp_path):
    """Codex R4-1: an unreadable receipt (fallback price in another unit) must not erase the broker's own spend."""
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    vnd = dict(unit="VND", film_cap=5000.0, film_baseline=0.0)
    first = pool.admit(_take_req("V1", "vt1", 4158.0, film_counted={}, **vnd))
    assert first["ok"]
    token = first["lease"]["lease_token"]
    assert pool.before_enter("V1", lease_token=token, child_key="V1#0")["go"]
    pool.finish_child("V1", lease_token=token, child_key="V1#0", outcome="PASSED", spent=4158.0)
    # the ledger knows vt1 but counts nothing for it in VND: the broker's 4158 still counts
    out = pool.admit(_take_req("V2", "vt2", 4158.0, film_counted={"vt1": 0.0}, **vnd))
    assert out["code"] == "BUDGET_EXCEEDED" and "4158 spent" in out["reason"]
    # a partial verified amount credits only that much: 1000 ledger + (4158 - 1000) + 900 > 5000
    out = pool.admit(_take_req("V3", "vt3", 900.0, **{**vnd, "film_baseline": 1000.0}, film_counted={"vt1": 1000.0}))
    assert out["code"] == "BUDGET_EXCEEDED"
    # fully verified: 4158 ledger + 0 + 800 <= 5000
    assert pool.admit(_take_req("V4", "vt4", 800.0, **{**vnd, "film_baseline": 4158.0},
                                film_counted={"vt1": 4158.0}))["ok"]


def test_film_budget_reports_the_verified_amount_per_take_in_the_unit(tmp_path):
    pkg = film(tmp_path, 100)
    numbers = G.film_budget(pkg, "VND")
    assert isinstance(numbers["film_counted"], dict)
    assert all(v == 0.0 for v in numbers["film_counted"].values())


def test_an_unregistered_account_halt_takes_the_selected_broker_lock(tmp_path, monkeypatch):
    """Codex R4-2: ``broker halt --db B`` serializes with B's admissions, not the default broker's."""
    from film_pipeline.agentic import broker_api as A
    from film_pipeline.production import halt as Hm
    monkeypatch.setenv("AFP_STATE_DIR", str(tmp_path / "state"))
    db = tmp_path / "b.sqlite3"
    Broker(db)
    locked = []
    real = Hm.broker_lock

    @contextmanager
    def spy(enabled=True, db=None):
        locked.append(db)
        with real(enabled, db):
            yield

    monkeypatch.setattr(Hm, "broker_lock", spy)
    out = A.halt("muse", "ghost", "CAPTCHA on Settings", kind="CAPTCHA", db=db)
    assert out["ok"] and out["account_status"] == "UNREGISTERED"
    assert [Path(d).resolve() for d in locked] == [db.resolve()]
    assert H.is_halted()


def test_a_migrated_reservation_takes_its_receipts_take_id_so_the_ledger_credit_applies(tmp_path):
    """Codex R5-2: migration -> import -> reconcile -> next admission: the step-4 row named the generation (g1), the
    ledger names the take (g1_t1); bound to its receipt, the settled spend is credited once, not counted twice."""
    db = tmp_path / "pool.sqlite3"
    _step4_db(db)
    pool = AccountLeasePool(db, min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    today = B.local_day()
    rows = [{"key": f"p:{g}_t1", "lease_key": f"f:{g}_t1@p", "take_id": f"{g}_t1", "provider": "flow",
             "unit": "credits", "amount": amount, "price": price, "day": today, "film_key": scope}
            for g, amount, price, scope in (("g1", 4.0, 4.0, "f@p"), ("g2", 3.0, 3.0, "other@p"),
                                            ("g3", 3.0, 3.0, "other@p"), ("g4", 8.0, 8.0, "f@p"))]
    pool.import_legacy(tmp_path, rows)
    pool.settle_child("f:g1_t1@p", spent=4.0)   # the reconcile of the open step-4 send
    with sqlite3.connect(db) as conn:
        bound = dict(conn.execute("SELECT lease_key, take_id || '|' || film_key FROM reservations WHERE lease_key IN "
                                  "('f:g1_t1@p', 'f:g4_t1@p')").fetchall())
    assert bound == {"f:g1_t1@p": "g1_t1|f@p", "f:g4_t1@p": "g4_t1|f@p"}
    ledger = {"film_cap": 18.0, "film_baseline": 12.0, "film_counted": {"g1_t1": 4.0, "g4_t1": 8.0}}
    assert pool.admit(_take_req("n6", "g5_t1", 6.0, **ledger))["ok"]   # 12 + 0 + 0 + 6 <= 18


def test_a_clear_never_erases_a_warning_set_through_another_broker(tmp_path, monkeypatch):
    """Codex R5-1: clear (default broker) and a warning via ``--db B`` share one halt-file lock: a clear paused after
    its read makes the warning wait, and the warning survives."""
    import threading
    import time as _time
    from film_pipeline.agentic import broker_api as A
    monkeypatch.setenv("AFP_STATE_DIR", str(tmp_path / "state"))
    H.set_halt("first warning", source="test")
    db = tmp_path / "b.sqlite3"
    Broker(db)
    paused, go, results = threading.Event(), threading.Event(), []
    real_read = H.read_halt

    def slow_read():
        out = real_read()
        if threading.current_thread().name == "clear":
            paused.set()
            go.wait(10)
        return out

    monkeypatch.setattr(H, "read_halt", slow_read)
    clear = threading.Thread(target=lambda: H.clear_halt("human:owner", "checked the account"), name="clear")
    clear.start()
    assert paused.wait(10)
    warn = threading.Thread(target=lambda: results.append(A.halt("muse", "ghost", "CAPTCHA on Settings",
                                                                 kind="CAPTCHA", db=db)))
    warn.start()
    _time.sleep(0.5)
    assert warn.is_alive()   # waits for the clear's halt-file lock
    go.set()
    clear.join(10)
    warn.join(30)
    assert results and results[0]["ok"]
    assert H.is_halted() and "CAPTCHA" in H.halt_reason()
