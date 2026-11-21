"""S1 broker addendum from the AFP<->Muse lane-contract reviews (S1_ADDENDUM_SPEC items 1-16): the cross-lease
shot-version block and required identity, the lost pre-Enter reply (ALREADY_SUBMITTING, never NOT_SENT), every stop
signal inside the halt-file lock boundary (AFP halt, Muse halt, pending markers), the read-only status, the atomic
batch check, ENTER_NOT_ISSUED and incarnation binding, the allocator claim/release, the token issued once and read from
stdin, rebind after a fenced NOT_SENT, and the atomic NOT_SENT settlement. P1 scope freeze: items 13 (Muse obligations),
15 (send-stop event), 16 (unwritten flags) and the allocator transfer protocol are M3 backlog."""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import threading

import pytest

from film_pipeline import cli
from film_pipeline.agentic import broker_api as api
from film_pipeline.agentic.broker import AdmitRequest, Broker, Child
from film_pipeline.production import halt as H

NO_CAPS = {"machine_caps": {}, "provider_caps": {}}


def http(key, take, shot, *, film="f", amount=1.0, **kw):
    """An account-less (HTTP provider) admission of one take of one shot version."""
    kw.setdefault("holder", "h")
    return AdmitRequest(lease_key=key, children=[Child(take, amount, take_id=take, shot_key=shot)], film_id=film,
                        needs_account=False, provider="http-test", **kw)


def on(account, key, take, shot, *, film="f"):
    """A Flow admission of one take of one shot version pinned to ``account``."""
    return AdmitRequest(lease_key=key, children=[Child(take, 6.0, take_id=take, shot_key=shot)], film_id=film,
                        provider="flow", account_id=account, holder="h")


def _flow_broker(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    broker.register_account("A", 1000.0, provider="flow")
    broker.register_account("B", 1000.0, provider="flow")
    return broker


# ---- item 1: one unresolved child per film + shot version, on any account or lease ---------------------------------
def test_an_unresolved_child_blocks_its_shot_version_on_every_account_and_lease(tmp_path):
    broker = _flow_broker(tmp_path)
    first = broker.admit(on("A", "L1", "t1", "g1:v1"))
    assert first["ok"]
    token = first["lease"]["lease_token"]
    other = on("B", "L2", "t2", "g1:v1")   # another account, another lease, another take
    refused = broker.admit(other)
    assert refused["code"] == "SHOT_VERSION_UNRESOLVED" and "L1" in refused["reason"]   # PREPARING
    assert broker.before_enter("L1", lease_token=token, child_key="t1")["go"]
    assert broker.admit(other)["code"] == "SHOT_VERSION_UNRESOLVED"                      # SUBMITTING
    broker.hold_child("L1", lease_token=token, reason="the reply was lost", child_key="t1")
    with sqlite3.connect(broker.db_path) as conn:
        assert conn.execute("SELECT state FROM leases WHERE lease_key = 'L1'").fetchone()[0] == \
            "QUARANTINED_PENDING_RECONCILE"
    assert broker.admit(other)["code"] == "SHOT_VERSION_UNRESOLVED"                      # AMBIGUOUS, lease held
    assert broker.admit(http("H1", "t3", "g1:v1"))["code"] == "SHOT_VERSION_UNRESOLVED"  # no account at all
    # another shot version, or the same shot version of another film, is not held by it
    assert broker.admit(on("B", "L3", "t4", "g1:v2"))["ok"]
    assert broker.admit(http("H2", "t5", "g1:v1", film="other"))["ok"]
    # once reconciled the shot version is free again (a new take id: t1 is spent)
    broker.settle_child("L1", spent=6.0, child_key="t1")
    assert broker.admit(http("H3", "t6", "g1:v1"))["ok"]


def test_a_migrated_step4_lease_without_a_shot_key_blocks_its_generation_identity(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    assert broker.admit(http("H1", "t1", "g1:v1"))["ok"]
    with sqlite3.connect(broker.db_path) as conn:   # a step-4 row: the identity is the lease's generation + version
        conn.execute("UPDATE lease_children SET shot_key = '', phase = 'UNKNOWN' WHERE lease_key = 'H1'")
        conn.execute("UPDATE leases SET generation_id = 'g1', shot_version = 1 WHERE lease_key = 'H1'")
    assert broker.admit(http("H2", "t2", "g1:v1"))["code"] == "SHOT_VERSION_UNRESOLVED"


@pytest.mark.parametrize("child, film", [
    (Child("c", 1.0, shot_key="g1:v1"), "f"),          # no take id
    (Child("c", 1.0, take_id="c"), "f"),                # no shot version
    (Child("c", 1.0, take_id="c", shot_key="g1:v1"), ""),   # no film
])
def test_the_identity_of_every_child_is_required(tmp_path, child, film):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    out = broker.admit(AdmitRequest(lease_key="L", children=[child], film_id=film, needs_account=False,
                                    provider="http-test", holder="h"))
    assert out["code"] == "BATCH_INVALID"


def test_a_take_id_is_unique_in_its_film_without_a_budget_cap(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    first = broker.admit(http("H1", "t1", "g1:v1"))   # no film cap: Muse's uncapped policy
    assert first["ok"]
    assert broker.admit(http("H2", "t1", "g2:v1"))["code"] == "TAKE_REUSED"   # still reserved
    token = first["lease"]["lease_token"]
    assert broker.before_enter("H1", lease_token=token, child_key="t1")["go"]
    broker.finish_child("H1", lease_token=token, child_key="t1", outcome="PASSED", spent=1.0)
    assert broker.admit(http("H3", "t1", "g2:v1"))["code"] == "TAKE_REUSED"   # spent
    assert broker.admit(http("H4", "t1", "g2:v1", film="other"))["ok"]         # another film's take numbering


def test_the_step4_pool_api_keeps_working_with_identities(tmp_path):
    from film_pipeline.agentic.lease_pool import AccountLeasePool
    pool = AccountLeasePool(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, **NO_CAPS)
    pool.register_account("A", 1000.0)
    lease = pool.acquire("g1", now=10.0)
    assert lease is not None
    pool.release("g1", credits_spent=6.0, now=11.0, lease_token=lease["lease_token"])
    again = pool.acquire("g1", now=12.0)   # the same generation sent again after a spend
    assert again is not None and again["lease_token"] != lease["lease_token"]




# ---- item 2: a lost pre-Enter reply ----------------------------------------------------------------------------------
def test_a_repeated_pre_enter_check_is_already_submitting_never_not_sent(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    lease = broker.admit(http("H1", "t1", "g1:v1"))["lease"]
    token = lease["lease_token"]
    assert api.check_before_enter("H1", token, "t1", db=db)["ok"]
    again = api.check_before_enter("H1", token, "t1", db=db)   # the first reply was lost: the caller asks again
    assert again["code"] == "ALREADY_SUBMITTING" and api.exit_code(again) == 1 and again["possibly_sent"]
    assert "possibly sent" in again["reason"] and "AMBIGUOUS" in again["reason"]
    with sqlite3.connect(db) as conn:   # nothing was closed or released
        assert conn.execute("SELECT phase, final FROM lease_children WHERE child_key = 't1'").fetchone() == \
            ("SUBMITTING", 0)
        assert conn.execute("SELECT state FROM reservations WHERE child_key = 't1'").fetchone() == ("RESERVED",)
    # a child that already has an outcome: possibly sent, never NOT_SENT
    broker.finish_child("H1", lease_token=token, child_key="t1", outcome="PASSED", spent=1.0)
    done = api.check_before_enter("H1", token, "t1", db=db)
    assert done["code"] == "CHILD_NOT_PREPARING" and done["possibly_sent"]
    # a proven pre-submit refusal (the halt while the child is PREPARING) is NOT_SENT_PROVEN, also when asked again
    lease2 = broker.admit(http("H2", "t2", "g2:v1"))["lease"]
    H.set_halt("test", source="test")
    first = api.check_before_enter("H2", lease2["lease_token"], "t2", db=db)
    assert first["code"] == "NOT_SENT_PROVEN" and first["cause"] == "PRODUCTION_HALT" and not first["possibly_sent"]
    second = api.check_before_enter("H2", lease2["lease_token"], "t2", db=db)
    assert second["code"] == "NOT_SENT_PROVEN" and not second["possibly_sent"]
    # another token names no child of this lease: nothing is decided, and it is not a proof
    lost = api.check_before_enter("H2", "not-the-token", "t2", db=db)
    assert lost["code"] == "LEASE_LOST" and lost["possibly_sent"]


def test_the_check_verb_help_says_a_repeat_is_possibly_sent(capsys):
    with pytest.raises(SystemExit):
        cli.main(["broker", "--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "ALREADY_SUBMITTING" in text and "possibly sent" in text and "NOT_SENT_PROVEN" in text
    assert "ALREADY_SUBMITTING" in api.check_before_enter.__doc__ and "NOT_SENT_PROVEN" in api.check_before_enter.__doc__


# ---- item 3: every stop signal in the halt-file lock boundary --------------------------------------------------------
def _publish_muse_halt(path, timeout_s):
    """Muse's side of the contract: write its halt file while holding the shared halt-file lock."""
    with api.halt_file_lock(timeout_s=timeout_s):
        path.write_text(json.dumps({"reason": "BLOCKED", "detail": "captcha on a Muse account"}), encoding="utf-8")


def test_a_configured_muse_halt_file_halts_admission_and_the_pre_enter_check(tmp_path, monkeypatch):
    db = tmp_path / "pool.sqlite3"
    muse = tmp_path / "muse_halt.json"
    monkeypatch.setenv("MUSE_HALT_FILE", str(muse))
    broker = Broker(db, **NO_CAPS)
    lease = broker.admit(http("H1", "t1", "g1:v1"))["lease"]   # configured but absent: no halt
    assert lease is not None
    _publish_muse_halt(muse, 5.0)
    refused = broker.admit(http("H2", "t2", "g2:v1"))
    assert refused["code"] == "PRODUCTION_HALT" and "Muse" in refused["reason"]
    check = api.check_before_enter("H1", lease["lease_token"], "t1", db=db)
    assert check["code"] == "NOT_SENT_PROVEN" and check["cause"] == "PRODUCTION_HALT"
    muse.write_text("{not json", encoding="utf-8")   # unreadable: still halted
    assert broker.admit(http("H3", "t3", "g3:v1"))["code"] == "PRODUCTION_HALT"
    monkeypatch.delenv("MUSE_HALT_FILE")   # not configured: Muse has no halt here
    assert broker.admit(http("H4", "t4", "g4:v1"))["ok"]
    assert api.halt_file_lock_path() == str(H.halt_path()) + ".lock"


def test_a_muse_halt_published_during_the_check_waits_for_its_commit(tmp_path, monkeypatch):
    """Write order 1: the check reads no halt and commits SUBMITTING; Muse's publication cannot land in between."""
    db = tmp_path / "pool.sqlite3"
    muse = tmp_path / "muse_halt.json"
    monkeypatch.setenv("MUSE_HALT_FILE", str(muse))
    broker = Broker(db, **NO_CAPS)
    lease = broker.admit(http("H1", "t1", "g1:v1"))["lease"]
    read, go_on, result = threading.Event(), threading.Event(), {}
    real = Broker._stop_refusal

    def slow(self):   # the check has read every stop signal; hold it here, before the commit
        out = real(self)
        read.set()
        go_on.wait(10)
        return out

    monkeypatch.setattr(Broker, "_stop_refusal", slow)
    worker = threading.Thread(target=lambda: result.update(
        broker.before_enter("H1", lease_token=lease["lease_token"], child_key="t1")))
    worker.start()
    assert read.wait(10)
    with pytest.raises(TimeoutError):   # between the check and the commit: Muse cannot publish
        _publish_muse_halt(muse, 0.3)
    go_on.set()
    worker.join(10)
    monkeypatch.setattr(Broker, "_stop_refusal", real)
    assert result["go"] and not muse.exists()
    _publish_muse_halt(muse, 5.0)   # after the commit it publishes, and the next check sees it
    assert broker.admit(http("H2", "t2", "g2:v1"))["code"] == "PRODUCTION_HALT"


def test_a_muse_halt_published_first_holds_the_check_until_it_is_written(tmp_path, monkeypatch):
    """Write order 2: Muse holds the lock while it writes; the check waits, then sees the halt: NOT_SENT_PROVEN."""
    db = tmp_path / "pool.sqlite3"
    muse = tmp_path / "muse_halt.json"
    monkeypatch.setenv("MUSE_HALT_FILE", str(muse))
    broker = Broker(db, **NO_CAPS)
    lease = broker.admit(http("H1", "t1", "g1:v1"))["lease"]
    holding, written, result = threading.Event(), threading.Event(), {}

    def muse_side():
        with api.halt_file_lock(timeout_s=5.0):
            holding.set()
            written.wait(10)
            muse.write_text(json.dumps({"reason": "BLOCKED"}), encoding="utf-8")

    publisher = threading.Thread(target=muse_side)
    publisher.start()
    assert holding.wait(10)
    worker = threading.Thread(target=lambda: result.update(
        api.check_before_enter("H1", lease["lease_token"], "t1", db=db)))
    worker.start()
    worker.join(0.5)
    assert worker.is_alive() and not result   # waiting for the halt-file lock, nothing decided
    written.set()
    publisher.join(10)
    worker.join(10)
    assert result["code"] == "NOT_SENT_PROVEN" and result["cause"] == "PRODUCTION_HALT"


def test_an_account_warning_and_admissions_take_the_two_locks_in_one_order(tmp_path):
    """Broker transaction, then the halt-file lock, everywhere: a warning racing admissions never deadlocks."""
    broker = _flow_broker(tmp_path)
    errors: list[BaseException] = []

    def admissions():
        try:
            for i in range(20):
                broker.admit(http(f"H{i}", f"t{i}", f"g{i}:v1"))
        except BaseException as exc:   # pragma: no cover - reported below
            errors.append(exc)

    worker = threading.Thread(target=admissions)
    worker.start()
    broker.account_warning("A", "captcha", kind="CAPTCHA")
    worker.join(30)
    assert not worker.is_alive() and not errors and H.read_halt() is not None


# ---- item 12: pending halt markers ----------------------------------------------------------------------------------
def _marker(name="muse-lane1-inc1", **body):
    H.pending_dir().mkdir(parents=True, exist_ok=True)
    path = H.pending_dir() / f"{name}.json"
    path.write_text(json.dumps({"provider": "muse", "account_id": "m1", "reason": "captcha", "ts": "t", **body}),
                    encoding="utf-8")
    return path


def test_a_pending_marker_refuses_admission_and_the_check(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    lease = broker.admit(http("H1", "t1", "g1:v1"))["lease"]
    path = _marker()
    refused = broker.admit(http("H2", "t2", "g2:v1"))
    assert refused["code"] == "HALT_PENDING" and path.name in refused["reason"]
    check = api.check_before_enter("H1", lease["lease_token"], "t1", db=db)
    assert check["code"] == "NOT_SENT_PROVEN" and check["cause"] == "HALT_PENDING"
    path.unlink()
    assert broker.admit(http("H3", "t3", "g3:v1"))["ok"]


def test_an_unreadable_pending_dir_refuses(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    H.pending_dir().write_text("not a directory", encoding="utf-8")   # cannot be listed
    refused = broker.admit(http("H1", "t1", "g1:v1"))
    assert refused["code"] == "HALT_PENDING" and "cannot be listed" in refused["reason"]


def test_a_marker_that_is_not_json_named_is_ignored(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    H.pending_dir().mkdir(parents=True)
    (H.pending_dir() / "note.txt").write_text("x", encoding="utf-8")   # markers are *.json
    assert broker.admit(http("H1", "t1", "g1:v1"))["ok"]


def test_halt_clear_publishes_pending_markers_first_and_removes_only_those(tmp_path, monkeypatch):
    m1 = _marker("muse-lane1-inc1")
    with pytest.raises(RuntimeError, match="--include-pending"):   # not without the flag, even with no halt
        H.clear_halt("human:owner", "reviewed")
    assert m1.exists()
    real = H.pending_markers
    late: list = []

    def racing():   # a sender latches a new marker right after the clear read the dir
        out = real()
        if not late:
            late.append(_marker("muse-lane2-inc9", reason="later block"))
        return out

    monkeypatch.setattr(H, "pending_markers", racing)
    entry = H.clear_halt("human:owner", "reviewed the markers", include_pending=True)
    monkeypatch.setattr(H, "pending_markers", real)
    assert entry["published_pending"] == ["halt_pending/muse-lane1-inc1"]
    assert not m1.exists() and all(p.exists() for p in late)   # the newer one stays
    assert H.read_halt() is None   # the halt was cleared ...
    history = [json.loads(line) for line in H.history_path().read_text(encoding="utf-8").splitlines()]
    sources = [h["event"]["source"] for h in history if h["action"] == "set"]
    assert sources == ["halt_pending:muse-lane1-inc1"]   # ... after publishing it
    assert history[-1]["action"] == "clear" and "captcha" in history[-1]["cleared_halt"]["reason"]
    assert H.stop_signals()[0] == "HALT_PENDING"   # the newer marker keeps every gate refusing


def test_halt_clear_keeps_the_first_halt_and_refuses_an_unreadable_pending_dir(capsys):
    H.set_halt("the first warning", source="test")
    _marker()
    assert cli.main(["halt", "clear", "--by", "human:owner", "--reason", "reviewed"]) == 1
    assert "--include-pending" in json.loads(capsys.readouterr().out)["error"]
    assert cli.main(["halt", "clear", "--by", "human:owner", "--reason", "reviewed", "--include-pending"]) == 0
    cleared = json.loads(capsys.readouterr().out)["cleared"]
    assert cleared["cleared_halt"]["reason"] == "the first warning"   # the marker was appended, the first halt kept
    assert any(e["source"] == "halt_pending:muse-lane1-inc1" for e in cleared["cleared_halt"]["events"])
    H.set_halt("again", source="test")
    H.pending_dir().rmdir()
    H.pending_dir().write_text("not a dir", encoding="utf-8")
    with pytest.raises(RuntimeError, match="cannot be listed"):
        H.clear_halt("human:owner", "reviewed", include_pending=True)
    assert H.read_halt() is not None


# ---- item 4: read-only status ----------------------------------------------------------------------------------------
def test_status_is_read_only_and_names_no_secret(tmp_path, capsys):
    db = tmp_path / "pool.sqlite3"
    absent = api.status(db=db)
    assert absent["ok"] and absent["live"] is False and not db.exists()   # a status never creates the broker
    Broker(db, **NO_CAPS)
    before = db.read_bytes()
    _marker()
    out = api.status(db=db)
    assert out["live"] is True and out["schema_version"] == 5 and out["owner"] == "afp-broker"
    assert out["db"] == str(db) and out["halt_lock"] == api.halt_file_lock_path()
    assert out["pending_markers"] == ["muse-lane1-inc1.json"]
    assert out["stop_code"] == "HALT_PENDING" and out["halted"] is False
    assert not any(k.startswith(("send_stop", "unwritten", "muse_obligations", "claim_epoch")) for k in out)
    assert db.read_bytes() == before
    text = json.dumps(out).lower()
    assert not any(word in text for word in ("cookie", "password", "token", "cdp"))
    assert cli.main(["broker", "status", "--json", "--db", str(db)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["live"] is True and printed["owner"] == "afp-broker"


# ---- item 5: the atomic batch check ----------------------------------------------------------------------------------
def _batch(broker, key="B1", n=3, film="f"):
    kids = [Child(f"{key}c{i}", 1.0, take_id=f"{key}t{i}", shot_key=f"{key}g{i}:v1") for i in range(n)]
    out = broker.admit(AdmitRequest(lease_key=key, children=kids, film_id=film, needs_account=False,
                                    provider="http-test", holder="h"))
    assert out["ok"], out
    return out["lease"]["lease_token"], [k.child_key for k in kids]


def _phases(db, keys):
    with sqlite3.connect(db) as conn:
        return [conn.execute("SELECT phase || ':' || outcome FROM lease_children WHERE child_key = ? ORDER BY id DESC",
                             (k,)).fetchone()[0] for k in keys]


def _admit_child(broker, key, child, take, shot, film="f"):
    return broker.admit(AdmitRequest(lease_key=key, children=[Child(child, 1.0, take_id=take, shot_key=shot)],
                                     film_id=film, needs_account=False, provider="http-test", holder="h"))


def test_the_batch_check_moves_every_child_or_none(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    token, keys = _batch(broker)
    ok = api.check_before_enter("B1", token, child_keys=keys, incarnation="inc-A", db=db)
    assert ok["ok"] and ok["children"] == keys and _phases(db, keys) == ["SUBMITTING:"] * 3
    # one child already SUBMITTING: the whole batch is refused, nothing else moves
    token2, keys2 = _batch(broker, "B2")
    assert broker.before_enter("B2", lease_token=token2, child_key=keys2[1], incarnation="inc-A")["go"]
    again = api.check_before_enter("B2", token2, child_keys=keys2, incarnation="inc-A", db=db)
    assert again["code"] == "ALREADY_SUBMITTING" and again["possibly_sent"]
    assert _phases(db, keys2) == ["PREPARING:", "SUBMITTING:", "PREPARING:"]
    # a stop signal: every child closed NOT_SENT in the same transaction
    token3, keys3 = _batch(broker, "B3")
    H.set_halt("stop", source="test")
    no = api.check_before_enter("B3", token3, child_keys=keys3, db=db)
    assert no["code"] == "NOT_SENT_PROVEN" and _phases(db, keys3) == ["DONE:NOT_SENT"] * 3
    with pytest.raises(ValueError):
        broker.before_enter("B3", lease_token=token3, child_keys=[keys3[0], keys3[0]])
    assert api.check_before_enter("B3", token3, db=db)["code"] == "USAGE"   # no child at all


def test_the_check_verb_takes_repeatable_children_and_the_incarnation(tmp_path, capsys, monkeypatch):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    token, keys = _batch(broker, n=2)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"lease_token": token}) + "\n"))
    code = cli.main(["broker", "check", "--db", str(db), "--lease-key", "B1", "--child", keys[0], "--child", keys[1],
                     "--incarnation", "inc-A", "--token-stdin"])
    out = capsys.readouterr().out
    assert code == 0 and json.loads(out)["children"] == keys and token not in out
    with sqlite3.connect(db) as conn:
        assert {r[0] for r in conn.execute("SELECT incarnation FROM lease_children")} == {"inc-A"}


# ---- items 6 + 8: ENTER_NOT_ISSUED and the incarnation binding --------------------------------------------------------
def _submitting(broker, account="A", key="L1", take="t1", shot="g1:v1", inc="inc-A"):
    lease = broker.admit(on(account, key, take, shot))["lease"]
    assert broker.before_enter(key, lease_token=lease["lease_token"], child_key=take, incarnation=inc)["go"]
    return lease


def test_enter_not_issued_from_the_live_holder_closes_and_fences_the_child(tmp_path):
    broker = _flow_broker(tmp_path)
    db = broker.db_path
    lease = _submitting(broker)
    out = api.mark("L1", lease["lease_token"], "t1", "NOT_SENT", reason="ENTER_NOT_ISSUED page error",
                   incarnation="inc-A", epoch=lease["epoch"], db=db)
    assert out["ok"] and out["outcome"] == "NOT_SENT"
    assert _phases(db, ["t1"]) == ["DONE:NOT_SENT"]
    # fenced: a later check never lets it out, an admission naming it is refused
    later = api.check_before_enter("L1", lease["lease_token"], "t1", db=db)
    assert later["code"] == "NOT_SENT_PROVEN" and later["cause"] == "ALREADY_NOT_SENT"
    fenced = broker.admit(AdmitRequest(lease_key="L2", children=[Child("t1", 6.0, take_id="t9", shot_key="g1:v1")],
                                       film_id="f", provider="flow", account_id="B", holder="h"))
    assert fenced["code"] == "CHILD_FENCED"
    with sqlite3.connect(db) as conn:
        assert [r[0] for r in conn.execute("SELECT action FROM child_audit ORDER BY id")] == \
            ["CHECK_GO", "ENTER_NOT_ISSUED", "CHECK_NOT_SENT"]


@pytest.mark.parametrize("change", ["incarnation", "epoch", "held", "token", "missing_incarnation"])
def test_enter_not_issued_is_refused_unless_everything_matches(tmp_path, change):
    broker = _flow_broker(tmp_path)
    db = broker.db_path
    lease = _submitting(broker)
    token, inc, epoch = lease["lease_token"], "inc-A", lease["epoch"]
    if change == "incarnation":
        inc = "inc-B"   # a restarted lane proves nothing about the earlier one
    elif change == "epoch":
        broker.bump_epoch("A")
    elif change == "held":
        broker.hold_child("L1", lease_token=token, reason="lost", child_key="t1")
    elif change == "token":
        token = "another-token"
    elif change == "missing_incarnation":
        inc = ""
    out = api.mark("L1", token, "t1", "NOT_SENT", reason="ENTER_NOT_ISSUED", incarnation=inc, epoch=epoch, db=db)
    assert not out["ok"]
    if change == "missing_incarnation":
        assert out["code"] == "USAGE"
    else:
        assert out["code"] == "ENTER_NOT_ISSUED_REFUSED" and out["possibly_sent"]
    with sqlite3.connect(db) as conn:   # never NOT_SENT, never final
        assert conn.execute("SELECT phase, final FROM lease_children WHERE child_key = 't1'").fetchone() == \
            ("SUBMITTING", 0)


def test_a_plain_not_sent_mark_never_clears_a_submitting_child(tmp_path):
    broker = _flow_broker(tmp_path)
    lease = _submitting(broker)
    out = api.mark("L1", lease["lease_token"], "t1", "NOT_SENT", db=broker.db_path)
    assert out["code"] == "CHILD_PAST_ENTER" and _phases(broker.db_path, ["t1"]) == ["SUBMITTING:"]


def test_an_acquire_replay_never_returns_the_token_again(tmp_path):
    broker = Broker(tmp_path / "pool.sqlite3", **NO_CAPS)
    first = broker.admit(http("H1", "t1", "g1:v1"))
    replay = broker.admit(http("H1", "t1", "g1:v1"))
    assert first["ok"] and first["lease"]["lease_token"]
    assert replay["code"] == "LEASE_EXISTS" and "lease" not in replay
    assert first["lease"]["lease_token"] not in json.dumps(replay)


# ---- item 9: rebind after a fenced NOT_SENT ------------------------------------------------------------------------
def test_a_take_is_rebound_only_after_every_attempt_is_fenced_not_sent(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    assert broker.admit(http("H1", "t1", "g1:v1"))["ok"]
    open_attempt = _admit_child(broker, "H2", "c2", "t1", "g1:v1")   # the first attempt is still open
    assert open_attempt["code"] in ("SHOT_VERSION_UNRESOLVED", "TAKE_REUSED")
    assert api.settle_not_sent("t1", "the lane never reached the page", db=db)["ok"]
    same_key = broker.admit(http("H3", "t1", "g1:v1"))
    assert same_key["code"] == "TAKE_REUSED" and "fresh child key" in same_key["reason"]
    rebound = _admit_child(broker, "H4", "c4", "t1", "g1:v1")
    assert rebound["ok"]
    with sqlite3.connect(db) as conn:   # the history is kept
        assert conn.execute("SELECT child_key, outcome FROM lease_children WHERE take_id = 't1' ORDER BY id"
                            ).fetchall() == [("t1", "NOT_SENT"), ("c4", "")]
    token = rebound["lease"]["lease_token"]
    assert broker.before_enter("H4", lease_token=token, child_key="c4")["go"]
    broker.finish_child("H4", lease_token=token, child_key="c4", outcome="PASSED", spent=1.0)
    again = _admit_child(broker, "H5", "c5", "t1", "g1:v1")
    assert again["code"] == "TAKE_REUSED"   # an attempt that may have been sent is never rebound


# ---- item 14: atomic NOT_SENT settlement ---------------------------------------------------------------------------
def test_settle_not_sent_closes_and_fences_a_preparing_child_and_refuses_a_submitting_one(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    token, keys = _batch(broker, n=2)
    out = api.settle_not_sent(keys[0], "lane crashed before the page loaded", db=db)
    assert out["ok"] and out["fenced"] and out["changed"] and out["lease_state"] == "ACTIVE"
    assert api.settle_not_sent(keys[0], "again", db=db)["changed"] is False   # idempotent
    assert api.check_before_enter("B1", token, keys[0], db=db)["code"] == "NOT_SENT_PROVEN"
    assert broker.before_enter("B1", lease_token=token, child_key=keys[1])["go"]
    past = api.settle_not_sent(keys[1], "I think it was not sent", db=db)
    assert past["code"] == "CHILD_PAST_ENTER" and past["possibly_sent"] and _phases(db, keys[1:]) == ["SUBMITTING:"]
    assert api.settle_not_sent(keys[1], "", db=db)["code"] == "USAGE"   # evidence required
    assert api.settle_not_sent("nope", "evidence", db=db)["code"] == "NOT_FOUND"
    assert api.settle_not_sent(keys[1], "evidence", lease_token="wrong", db=db)["code"] == "TOKEN_MISMATCH"


def test_settle_not_sent_releases_a_held_preparing_child(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    token, keys = _batch(broker, n=1)
    broker.hold_child("B1", lease_token=token, reason="unsure", child_key=keys[0])   # never passed the check
    out = api.settle_not_sent(keys[0], "no check ever passed", db=db)
    assert out["ok"] and out["lease_state"] == "RELEASED"


@pytest.mark.parametrize("first", ["settle", "check"])
def test_settle_not_sent_and_the_check_race_in_both_orders(tmp_path, first):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    token, keys = _batch(broker, n=1)

    def settle():
        return api.settle_not_sent(keys[0], "the lane died before Enter", db=db)

    def check():
        return api.check_before_enter("B1", token, keys[0], db=db)

    if first == "settle":
        s, c = settle(), check()
        assert s["ok"] and c["code"] == "NOT_SENT_PROVEN"   # settled first: never an Enter
    else:
        c, s = check(), settle()
        assert c["ok"] and s["code"] == "CHILD_PAST_ENTER"   # checked first: never a NOT_SENT
    # truly concurrent: exactly one of the two wins, never both
    token2, keys2 = _batch(broker, "B2", n=1)
    barrier, out = threading.Barrier(2), {}

    def run(name, fn):
        barrier.wait(10)
        out[name] = fn()

    threads = [threading.Thread(target=run, args=("s", lambda: api.settle_not_sent(keys2[0], "racing", db=db))),
               threading.Thread(target=run, args=("c", lambda: api.check_before_enter("B2", token2, keys2[0],
                                                                                        db=db)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert out["s"]["ok"] != out["c"]["ok"]


# ---- item 11: the token on stdin, never in any output ---------------------------------------------------------------
def test_the_token_is_read_from_stdin_and_never_printed(tmp_path, capsys, monkeypatch, caplog):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    token, keys = _batch(broker, n=3)
    seen = []

    def run(argv, stdin_line):
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_line))
        code = cli.main(["broker", *argv, "--db", str(db), "--token-stdin"])
        text = capsys.readouterr()
        seen.append(text.out + text.err)
        return code, json.loads(text.out)

    good = json.dumps({"lease_token": token}) + "\n"
    assert run(["check", "--lease-key", "B1", "--child", keys[0], "--incarnation", "i1"], good)[0] == 0
    assert run(["mark", "--lease-key", "B1", "--child", keys[0], "--state", "PASSED", "--spent", "1"], good)[0] == 0
    assert run(["settle-not-sent", "--child", keys[1], "--evidence", "never checked", "--lease-key", "B1"],
               good)[0] == 0
    wrong = json.dumps({"lease_token": token[:8] + "-wrong"}) + "\n"
    assert run(["check", "--lease-key", "B1", "--child", keys[2]], wrong)[1]["code"] == "LEASE_LOST"
    assert run(["settle", "--lease-key", "B1", "--spent", "0"], wrong)[1]["code"] == "TOKEN_MISMATCH"
    code, bad = run(["release", "--lease-key", "B1"], "garbage " + token + "\n")   # malformed: input never echoed
    assert code == 2 and bad["code"] == "USAGE"
    assert run(["release", "--lease-key", "B1"], good)[0] == 0
    both = cli.main(["broker", "release", "--db", str(db), "--lease-key", "B1", "--token", token, "--token-stdin"])
    seen.append(capsys.readouterr().out)
    assert both == 2
    assert not any(token in text for text in seen) and token not in caplog.text
    assert cli.main(["broker", "status", "--db", str(db), "--token", "x"]) == 2   # a verb without a token refuses one
    capsys.readouterr()


# ---- item 7 (P1 scope freeze): allocator claim / release ------------------------------------------------------------
def test_allocator_claim_and_release_round_trip(tmp_path, capsys):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    H.owner_path().unlink()   # a fresh machine: no claim
    assert broker.admit(http("H0", "t0", "g0:v1"))["code"] == "ALLOCATOR_UNKNOWN"
    assert api.status(db=db)["live"] is False
    assert cli.main(["broker", "allocator-claim", "--by", "human:owner", "--db", str(db)]) == 0
    claimed = json.loads(capsys.readouterr().out)
    assert claimed["ok"] and claimed["changed"] is True and claimed["owner"] == "afp-broker"
    body = json.loads(H.owner_path().read_text(encoding="utf-8"))
    assert body["owner"] == "afp-broker" and body["claimed_by"] == "human:owner" and "claim_epoch" not in body
    again = api.allocator_claim(db=db)   # idempotent: the claim is kept
    assert again["ok"] and again["changed"] is False
    assert json.loads(H.owner_path().read_text(encoding="utf-8")) == body
    lease = broker.admit(http("H1", "t1", "g1:v1"))
    assert lease["ok"] and api.status(db=db)["live"] is True
    busy = api.allocator_release(db=db)   # refused while a lease is live
    assert busy["code"] == "OWNER_BUSY" and "H1" in busy["reason"] and H.owner_path().exists()
    tok = lease["lease"]["lease_token"]
    assert broker.before_enter("H1", lease_token=tok, child_key="t1")["go"]
    broker.hold_child("H1", lease_token=tok, reason="the reply was lost", child_key="t1")
    assert api.allocator_release(db=db)["code"] == "OWNER_BUSY"   # a held lease / an unresolved child
    broker.settle_child("H1", spent=1.0, child_key="t1")
    assert cli.main(["broker", "allocator-release", "--by", "human:owner", "--db", str(db)]) == 0
    released = json.loads(capsys.readouterr().out)
    assert released["ok"] and released["changed"] is True and not H.owner_path().exists()
    assert api.allocator_release(db=db)["changed"] is False   # idempotent
    assert broker.admit(http("H2", "t2", "g2:v1"))["code"] == "ALLOCATOR_UNKNOWN"
    assert api.allocator_claim(db=db)["changed"] is True
    assert broker.admit(http("H3", "t3", "g3:v1"))["ok"]


def test_only_the_claiming_database_may_release_the_machine_claim(tmp_path):
    """Codex R8-1: the claim is machine-wide; an unrelated (empty) broker database must not remove it."""
    db, other = tmp_path / "pool.sqlite3", tmp_path / "other.sqlite3"
    broker = Broker(db, **NO_CAPS)
    H.owner_path().unlink()
    assert api.allocator_claim(db=db)["ok"]
    assert json.loads(H.owner_path().read_text(encoding="utf-8"))["db"] == os.path.normcase(str(db.resolve()))
    lease = broker.admit(http("H1", "t1", "g1:v1"))
    assert lease["ok"]
    refused = api.allocator_release(db=other)   # the other database has no lease of its own
    assert refused["code"] == "WRONG_DATABASE" and H.owner_path().exists()
    hand_written = {"owner": "afp-broker", "claimed_at": "t", "claimed_by": "x"}   # no db recorded: refused too
    H.owner_path().write_text(json.dumps(hand_written), encoding="utf-8")
    assert api.allocator_release(db=db)["code"] == "WRONG_DATABASE"


def test_another_database_cannot_allocate_under_the_claim_of_the_claiming_one(tmp_path):
    """Codex R9-1: claim A -> admission/check through B is refused, so A's release cannot strand B's work."""
    a, b = tmp_path / "a.sqlite3", tmp_path / "b.sqlite3"
    broker_a, broker_b = Broker(a, **NO_CAPS), Broker(b, **NO_CAPS)
    H.owner_path().unlink()
    assert api.allocator_claim(db=a)["ok"]
    refused = broker_b.admit(http("H1", "t1", "g1:v1"))
    assert refused["code"] == "ALLOCATOR_NOT_OWNED" and "nothing is allocated here" in refused["reason"]
    assert api.allocator_claim(db=b)["code"] == "WRONG_DATABASE"   # an existing claim is never taken over
    lease = broker_a.admit(http("H2", "t2", "g2:v1"))
    assert lease["ok"]
    assert not api.check_before_enter("H2", lease["lease"]["lease_token"], "t2", db=b)["ok"]   # b has no such lease


def test_a_pre_login_check_serializes_with_a_halt_published_under_the_halt_file_lock(tmp_path, monkeypatch):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, cooldown_s=0.0, **NO_CAPS)
    broker.register_account("m1", provider="muse", quota_mode="probed")
    epoch = broker.accounts_view()[0]["epoch"]
    assert broker.claim_profile("m1", claimant="c1", epoch=epoch)["ok"]
    halt_file = tmp_path / "muse_halt.json"
    monkeypatch.setenv("MUSE_HALT_FILE", str(halt_file))
    out: dict = {}
    with api.halt_file_lock():   # Muse is publishing its halt: a login decision must wait for the lock
        worker = threading.Thread(target=lambda: out.update(broker.before_login(
            "m1", cause="AUTH_EXPIRED", epoch=epoch, claimant="c1")))
        worker.start()
        worker.join(1.0)
        assert worker.is_alive()   # blocked on the halt-file lock, not deciding on a stale read
        halt_file.write_text(json.dumps({"reason": "captcha"}), encoding="utf-8")
    worker.join(30)
    assert not worker.is_alive() and out["go"] is False and out["code"] == "PRODUCTION_HALT"


def test_the_check_refuses_without_the_claim(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    lease = broker.admit(http("H1", "t1", "g1:v1"))["lease"]
    H.owner_path().unlink()   # removed by hand (allocator-release refuses while the lease is live)
    check = api.check_before_enter("H1", lease["lease_token"], "t1", db=db)
    assert check["code"] == "NOT_SENT_PROVEN" and check["cause"] == "ALLOCATOR_UNKNOWN"


def test_an_unreadable_claim_refuses_and_is_never_overwritten(tmp_path):
    db = tmp_path / "pool.sqlite3"
    broker = Broker(db, **NO_CAPS)
    for body, code in (("{not json", "ALLOCATOR_UNKNOWN"), (json.dumps(["afp-broker"]), "ALLOCATOR_UNKNOWN"),
                       (json.dumps({"owner": ""}), "ALLOCATOR_UNKNOWN"), ("", "ALLOCATOR_UNKNOWN"),
                       (json.dumps({"owner": "muse-standalone"}), "ALLOCATOR_NOT_OWNED")):
        H.owner_path().write_text(body, encoding="utf-8")
        assert broker.admit(http("H1", "t1", "g1:v1"))["code"] == code
        assert api.allocator_claim(db=db)["code"] == code
        assert api.allocator_release(db=db)["code"] == code
        assert H.owner_path().read_text(encoding="utf-8") == body
