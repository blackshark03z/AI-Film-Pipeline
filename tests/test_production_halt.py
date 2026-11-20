"""Owner rule: any Flow account warning halts ALL sending on this machine until an explicit, accountable clear."""
import json
from pathlib import Path

import pytest

from film_pipeline.agentic.lease_pool import AccountLeasePool
from film_pipeline.cli import main as cli_main
from film_pipeline.production import generate as G
from film_pipeline.production import halt as H
from film_pipeline.production import preflight as P
from film_pipeline.production import recovery as R
from film_pipeline.production import takes as T
from test_production_generate import FakeRunner, backlog, film, still

# a live generate() send leases a Flow account from the isolated machine pool (tests/conftest.py)
pytestmark = pytest.mark.usefixtures("flow_lease_account")

GO = "OWNER_GO_LIVE: YES"


def history():
    path = H.history_path()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def live(pkg, tmp_path, runner, **kw):
    return G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, GO), runner=runner, **kw)


def test_fixture_isolates_the_halt_file_from_the_real_home(tmp_path):
    assert not H.halt_path().is_relative_to(Path.home() / ".afp")
    assert H.halt_path().parent == H.history_path().parent


def test_default_location_uses_state_dir_then_home(monkeypatch, tmp_path):
    monkeypatch.delenv("AFP_HALT_FILE")
    monkeypatch.setenv("AFP_STATE_DIR", str(tmp_path / "state"))
    assert H.halt_path() == tmp_path / "state" / "production_halt.json"
    monkeypatch.delenv("AFP_STATE_DIR")
    assert H.halt_path() == Path.home() / ".afp" / "production_halt.json"


def test_set_read_and_first_halt_is_kept(tmp_path):
    assert H.read_halt() is None and not H.is_halted()
    first = H.set_halt("unusual activity", source="generate", account="acct_a", film_id="f1", take_id="SC01_g1_t1")
    assert H.is_halted() and H.read_halt()["reason"] == "unusual activity"
    assert first["events"][0]["account"] == "acct_a" and first["set_at"][-6:].count(":") == 1   # ISO with UTC offset
    second = H.set_halt("captcha", source="flow_pool_runner", account="acct_b", evidence="verify it is you")
    assert second["reason"] == "unusual activity" and second["source"] == "generate"
    assert [e["reason"] for e in H.read_halt()["events"]] == ["unusual activity", "captcha"]
    assert [h["action"] for h in history()] == ["set", "set"]
    assert not list(H.halt_path().parent.glob("*.tmp"))


def test_clear_validates_writes_history_and_removes_the_file():
    with pytest.raises(RuntimeError, match="not halted"):
        H.clear_halt("human:owner", "nothing to clear")
    H.set_halt("unusual activity", source="generate")
    for bad_by in ("owner", "robot:x", "human:", "human:a b", ""):
        with pytest.raises(ValueError, match="by"):
            H.clear_halt(bad_by, "looked at the account")
    with pytest.raises(ValueError, match="reason"):
        H.clear_halt("human:owner", "ok")
    assert H.is_halted()
    done = H.clear_halt("agent:tech-lead.1", "account checked by hand")
    assert not H.is_halted() and not H.halt_path().exists()
    assert done["by"] == "agent:tech-lead.1" and done["cleared_halt"]["reason"] == "unusual activity"
    assert [h["action"] for h in history()] == ["set", "clear"] and history()[-1]["cleared_halt"]["reason"]
    with pytest.raises(RuntimeError, match="not halted"):
        H.clear_halt("human:owner", "again")


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", ""])
def test_unreadable_halt_file_counts_as_halted(content):
    H.halt_path().parent.mkdir(parents=True, exist_ok=True)
    H.halt_path().write_text(content, encoding="utf-8")
    assert H.is_halted() and H.read_halt()["reason"] == "unreadable halt file"
    recorded = H.set_halt("real warning", source="generate")   # a corrupt file is replaced, not trusted
    assert recorded["reason"] == "real warning" and json.loads(H.halt_path().read_text(encoding="utf-8"))["reason"]
    H.clear_halt("human:owner", "removed corrupt state")
    assert not H.is_halted()


def test_dry_run_reports_the_halt_as_a_live_only_blocker(tmp_path):
    pkg = film(tmp_path, 100)
    H.set_halt("unusual activity", source="generate")
    done = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, GO))
    halted = [b for b in done["payload"]["blockers"] if b["code"] == "PRODUCTION_HALT"]
    assert halted and halted[0]["live_only"] and "unusual activity" in halted[0]["detail"] and not done["ready_to_send"]


def test_live_send_is_refused_while_halted_and_works_after_clear(tmp_path):
    pkg = film(tmp_path, 100)
    H.set_halt("unusual activity", source="generate", account="acct_a")
    runner = FakeRunner()
    refused = live(pkg, tmp_path, runner)
    assert not refused["sent"] and [r["code"] for r in refused["refused"]] == ["PRODUCTION_HALT"] and not runner.calls
    assert "unusual activity" in refused["refused"][0]["detail"]
    H.clear_halt("human:owner", "account verified")
    done = live(pkg, tmp_path, runner)
    assert done["sent"] and len(runner.calls) == 1


def test_before_submit_aborts_when_the_halt_appears_and_leaves_no_take(tmp_path, monkeypatch):
    pkg = film(tmp_path, 100)
    monkeypatch.setattr(P, "check", lambda *a, **k: {"ok": True})
    entered = []

    def controller(argv, out, before_submit=None):
        H.set_halt("unusual activity", source="flow_pool_runner", account="acct_other")   # another account warns
        entered.append("before_submit")
        before_submit({"project": "owned-project"})
        entered.append("enter")   # must never be reached
        return {"result": "PASSED"}

    monkeypatch.setattr(G, "controller_runner", controller)
    with pytest.raises(RuntimeError, match="PRODUCTION_HALT"):
        G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO))
    assert entered == ["before_submit"]
    receipt = json.loads((pkg.root / "takes/intents/SC01_g1_t1.intent.json").read_text(encoding="utf-8"))
    assert receipt["dispatch_phase"] == "PREPARING"
    assert not [t for t in T.load_log(pkg.root, pkg.header.film_id).takes if t.status == "PASSED"]
    assert T.load_log(pkg.root, pkg.header.film_id).takes == []
    result = R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: {"result": "AMBIGUOUS"})
    assert result["resolved"] and result["result"] == "PRE_SUBMIT_ERROR CONTROLLER_NOT_DISPATCHED"


@pytest.mark.parametrize("outcome", ["FLOW_ACCOUNT_WARNING", "PRE_SUBMIT_ERROR FLOW_ACCOUNT_WARNING"])
def test_an_account_warning_in_the_send_sets_the_halt_and_never_resends(tmp_path, outcome, flow_lease_account):
    for acct in ("acct_a", "acct_b"):
        flow_lease_account.register_account(acct, 1000.0)
    pkg = film(tmp_path, 100)
    runner = FakeRunner(outcome)
    done = live(pkg, tmp_path, runner, account_scope="acct_a")
    assert done["sent"] and done["manifest_result"] == outcome and "auto_resend" not in done
    assert len(runner.calls) == 1
    recorded = H.read_halt()
    assert recorded and recorded["source"] == "generate" and recorded["reason"] == outcome
    assert recorded["account"] == "acct_a" and recorded["film_id"] == pkg.header.film_id
    assert recorded["take_id"] == "SC01_g1_t1"
    again = live(pkg, tmp_path, runner, account_scope="acct_b")   # another account is refused too
    assert "PRODUCTION_HALT" in [r["code"] for r in again["refused"]] and len(runner.calls) == 1


def test_lease_quarantine_halts_everything_until_cleared(tmp_path):
    pool = AccountLeasePool(tmp_path / "leases.sqlite3", min_reserve_credits=20.0)
    pool.register_account("acct_a", 100.0)
    pool.register_account("acct_b", 90.0)
    pool.quarantine_account("acct_a", "unusual activity")
    recorded = H.read_halt()
    assert recorded["source"] == "lease_pool" and recorded["account"] == "acct_a" and recorded["reason"] == "unusual activity"
    assert pool.acquire("g1", cost_credits=6.0, now=1000.0) is None   # healthy acct_b is refused as well
    H.clear_halt("human:owner", "warning reviewed")
    lease = pool.acquire("g1", cost_credits=6.0, now=1000.0)
    assert lease is not None and lease["account_id"] == "acct_b"


def test_pool_runner_assert_safe_sets_the_halt():
    pytest.importorskip("websockets")
    from film_pipeline.providers._flow_ui import flow_pool_runner as FPR
    with pytest.raises(RuntimeError, match="ACCOUNT_WARNING_OR_CAPTCHA"):
        FPR.FlowTab.assert_safe([("text", "Unusual activity detected on your account", 1)])
    recorded = H.read_halt()
    assert recorded and recorded["source"] == "flow_pool_runner" and "ACCOUNT_WARNING_OR_CAPTCHA" in recorded["reason"]
    with pytest.raises(RuntimeError, match="PRODUCTION_HALT"):
        FPR._refuse_if_halted()


def test_preflight_send_reports_the_halt_as_an_issue(tmp_path):
    clean = P.check(tmp_path, operation="send")
    assert not any("production halted" in i for i in clean["issues"])
    H.set_halt("unusual activity", source="generate")
    send = P.check(tmp_path, operation="send")
    assert not send["ok"]
    assert any(i.startswith("production halted: unusual activity") and "halt clear --by" in i for i in send["issues"])
    render = P.check(tmp_path, operation="render")
    assert not any("production halted" in i for i in render["issues"])


def test_cli_halt_status_set_clear(capsys):
    def run(*argv):
        code = cli_main(["halt", *argv])
        return code, json.loads(capsys.readouterr().out)

    code, body = run("status")
    assert code == 0 and body["ok"] and body["halted"] is False and body["halt"] is None
    code, body = run("set")
    assert code == 1 and not body["ok"]
    code, body = run("set", "--reason", "unusual activity seen by hand")
    assert code == 0 and body["halted"] and body["halt"]["source"] == "cli"
    code, body = run("status")
    assert body["halted"] and body["halt"]["reason"] == "unusual activity seen by hand"
    code, body = run("clear", "--by", "someone", "--reason", "checked")
    assert code == 1 and not body["ok"] and H.is_halted()
    code, body = run("clear", "--by", "human:owner", "--reason", "account checked by hand")
    assert code == 0 and body["ok"] and body["halted"] is False and not H.is_halted()
    code, body = run("clear", "--by", "human:owner", "--reason", "again")
    assert code == 1 and "not halted" in body["error"]
