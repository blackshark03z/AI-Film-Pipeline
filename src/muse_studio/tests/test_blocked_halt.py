"""A CAPTCHA, verification or unusual-activity page stops ALL Muse sending (never a failover to another account)."""
import asyncio
import json
from pathlib import Path

import pytest

from muse_studio.tests import _halt_env  # noqa: F401  (scratch MUSE_HALT_FILE / AFP_STATE_DIR even without the conftest)

import muse_studio.pool_runner as pool_runner
from muse_studio.core.account_manager import AccountManager
from muse_studio.core.headless_muse_client import (
    BlockedException,
    HeadlessMuseClient,
    QuotaExceededException,
    SessionInvalidException,
)
from muse_studio.core.parallel_pool_engine import HALT_FILE, UNCONFIRMED_FILE, ParallelPoolEngine
from muse_studio.tests.test_lane_review_r2 import _kf_project, _make_accounts, _submitted
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project


@pytest.fixture(autouse=True)
def _temp_lease_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path / "lane_leases.json"))


def _engine_3acc(tmp_path: Path, behaviour, delay=0.01):
    """Three READY accounts and a client that records every dispatch (account, shot ids)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    mgr, _ = _make_accounts(tmp_path, 3)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    calls = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False):
            calls.append((account_id, [s.shot_id for s in shots]))
            behaviour(len(calls))
            await asyncio.sleep(delay)
            out = Path(output_dir) / "verified_clips"
            out.mkdir(parents=True, exist_ok=True)
            verified = {}
            for idx, s in enumerate(shots, start=1):
                p = out / f"shot_{idx:02d}.mp4"
                p.write_bytes(seed.read_bytes())
                verified[s.shot_id] = {"path": str(p), "bytes": p.stat().st_size}
            return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}

    engine = ParallelPoolEngine(
        account_manager=mgr, client_factory=Client,
        qc_evaluator=lambda cp, ss, **kw: {"verdict": "PASS", "defects": [], "metrics": {}}, sync_ui=False,
    )
    return engine, calls, mgr


def _captcha_first(n):
    if n == 1:
        raise BlockedException("BLOCKED: CAPTCHA / human check on the Muse page")


# ---- client: page markers (the probe result; the DOM probe itself runs in a real browser in test_stop_all_r14) -----
class _Body:
    def __init__(self, text):
        self.text = text

    async def inner_text(self, timeout=None):
        return self.text


class _Page:
    """`evaluate` returns what the visible-UI probe reports: a visible widget, or text of system UI regions."""

    def __init__(self, widget=False, text="", body=""):
        self.probe = {"widget": widget, "text": text, "interstitial": bool(text), "otp": False}
        self.body = body

    async def evaluate(self, js):
        return self.probe

    def locator(self, sel):
        return _Body(self.body)


@pytest.mark.parametrize("widget, text", [
    (True, ""),
    (False, "Please verify you are human"),
    (False, "We noticed unusual activity on your account."),
    (False, "Verify it's you to continue"),
    (False, "Your account is temporarily blocked."),
    (False, "Phát hiện hoạt động bất thường"),
])
def test_page_check_raises_blocked(widget, text):
    with pytest.raises(BlockedException):
        asyncio.run(HeadlessMuseClient._check_page_errors(_Page(widget, text)))


def test_page_check_quota_is_still_quota():
    with pytest.raises(QuotaExceededException):
        asyncio.run(HeadlessMuseClient._check_page_errors(_Page(body="You are out of credits")))


def test_blocked_is_not_a_session_or_quota_failure():
    assert not issubclass(BlockedException, (SessionInvalidException, QuotaExceededException))


# ---- login path ---------------------------------------------------------------------------------------------------------
class _SyncBody:
    def __init__(self, text):
        self.text = text

    def inner_text(self, timeout=None):
        return self.text


class _SyncPage:
    def __init__(self, body):
        self.body = body

    def evaluate(self, js):
        return {"widget": False, "text": self.body, "interstitial": True, "otp": False}

    def locator(self, sel):
        return _SyncBody(self.body)


def test_login_detects_unusual_activity_as_block():
    msg = AccountManager._detect_captcha_or_block(_SyncPage("Suspicious activity detected. Verify your identity."))
    assert msg and msg.startswith("BLOCKED:")


def test_login_blocked_result_raises_blocked(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 1)
    mgr.update_account(ids[0], status="UNCHECKED")
    mgr.auto_login_and_verify = lambda aid, url=None: {"status": "BLOCKED", "message": "BLOCKED: CAPTCHA"}
    with pytest.raises(BlockedException):
        asyncio.run(HeadlessMuseClient(mgr)._ensure_logged_in(ids[0]))


def test_capacity_login_block_halts_before_any_dispatch(tmp_path: Path):
    engine, calls, mgr = _engine_3acc(tmp_path, lambda n: None)
    first = mgr.list_accounts()[0]["id"]
    mgr.update_account(first, status="UNCHECKED")

    def login(aid, url=None):
        mgr.update_account(aid, status="ERROR", error_message="BLOCKED: CAPTCHA at login")
        return {"status": "BLOCKED", "message": "BLOCKED: CAPTCHA at login"}

    mgr.auto_login_and_verify = login
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=6)
    res = engine.run_videos(project_dir=proj, max_accounts=2, max_rounds=1, simulate=False)
    assert calls == [], f"sent after a login CAPTCHA: {calls}"
    assert res["status"] == "HALTED" and res["halted"]["reason"] == "BLOCKED"
    assert res["halted"]["account_id"] == first
    assert (proj / HALT_FILE).exists()


# ---- videos -------------------------------------------------------------------------------------------------------------
def test_captcha_before_enter_halts_run_without_failover(tmp_path: Path):
    engine, calls, mgr = _engine_3acc(tmp_path, _captcha_first)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=12)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=3, simulate=False)
    assert len(calls) == 1, f"a blocked batch failed over or more batches were sent: {calls}"
    assert res["status"] == "HALTED"
    halted = res["halted"]
    assert halted["reason"] == "BLOCKED" and halted["account_id"] == calls[0][0] and halted["batch_id"]
    acc = mgr.get_account(calls[0][0])
    assert acc["status"] in ("ERROR", "LOGGED_OUT") and acc["error_message"].startswith("BLOCKED:")
    saved = json.loads((proj / HALT_FILE).read_text(encoding="utf-8"))
    assert saved["reason"] == "BLOCKED" and saved["account_id"] == calls[0][0]
    ledger = json.loads((proj / UNCONFIRMED_FILE).read_text(encoding="utf-8"))["entries"]
    assert all(e["status"] == "RESOLVED" and e.get("reason") == "NOT_SENT" for e in ledger)


def test_in_flight_batch_on_other_account_is_collected_then_nothing_more(tmp_path: Path):
    def behaviour(n):  # batch 1 is in flight on account A when account B hits the CAPTCHA
        if n == 2:
            raise BlockedException("BLOCKED: CAPTCHA / human check on the Muse page")

    engine, calls, _ = _engine_3acc(tmp_path, behaviour, delay=0.2)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=18)  # 3 batches of 6 on 2 accounts
    res = engine.run_videos(project_dir=proj, max_accounts=2, max_rounds=3, simulate=False)
    assert len(calls) == 2, f"a batch was dispatched after the halt: {calls}"
    assert calls[0][0] != calls[1][0]
    assert res["passed_count"] == 6, "the batch already in flight on the other account was not collected"
    assert res["status"] == "HALTED"


def test_captcha_after_enter_is_unconfirmed_and_not_resent(tmp_path: Path):
    def behaviour(n):
        if n == 1:
            raise _submitted(BlockedException("BLOCKED: verification page after submit"))

    engine, calls, _ = _engine_3acc(tmp_path, behaviour)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=6)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=3, simulate=False)
    assert len(calls) == 1
    assert res["status"] == "HALTED"
    assert sorted(res["submitted_unconfirmed_shot_ids"]) == sorted(calls[0][1])
    ledger = json.loads((proj / UNCONFIRMED_FILE).read_text(encoding="utf-8"))["entries"]
    assert {e["status"] for e in ledger} == {"UNCONFIRMED"}


def test_quota_still_fails_over(tmp_path: Path):
    def behaviour(n):
        if n == 1:
            raise QuotaExceededException("quota before send")

    engine, calls, _ = _engine_3acc(tmp_path, behaviour)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=6)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, simulate=False)
    assert len(calls) == 2 and calls[0][0] != calls[1][0]
    assert res["status"] == "COMPLETED" and "halted" not in res
    assert not (proj / HALT_FILE).exists()


# ---- persisted halt -----------------------------------------------------------------------------------------------------
def test_halt_file_blocks_next_run_and_clear_halt_releases_it(tmp_path: Path, monkeypatch, capsys):
    engine, calls, _ = _engine_3acc(tmp_path, _captcha_first)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=6)
    engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, simulate=False)
    assert (proj / HALT_FILE).exists()

    engine2, calls2, _ = _engine_3acc(tmp_path / "second", lambda n: None)
    monkeypatch.setattr(pool_runner, "_build_engine", lambda args: engine2)
    rc = pool_runner.main(["videos", str(proj), "--max-rounds", "1"])
    out = capsys.readouterr()
    assert rc == 4, out.out
    assert calls2 == [], "a halted project sent again"
    assert "--clear-halt" in out.err and len(out.err.strip().splitlines()) == 1
    assert (proj / HALT_FILE).exists()

    # simulate ignores the halt but reports it
    res = engine2.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, simulate=True)
    assert res.get("halt_file", {}).get("reason") == "BLOCKED" and res["status"] != "HALTED"
    assert (proj / HALT_FILE).exists()
    calls2.clear()

    rc = pool_runner.main(["videos", str(proj), "--max-rounds", "1", "--clear-halt"])
    capsys.readouterr()
    assert rc == 0 and calls2, "--clear-halt did not release the project"
    assert not (proj / HALT_FILE).exists()


# ---- keyframes ----------------------------------------------------------------------------------------------------------
def test_keyframes_captcha_halts_without_failover(tmp_path: Path, monkeypatch, capsys):
    mgr, _ = _make_accounts(tmp_path, 3)
    sent = []

    class BlockedClient:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False):
            sent.append((account_id, batch_id))
            raise BlockedException("BLOCKED: CAPTCHA on keyframe send")

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=BlockedClient, sync_ui=False)
    proj = _kf_project(tmp_path)
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    assert len(sent) == 1, f"a blocked keyframe batch failed over: {sent}"
    assert res["status"] == "HALTED" and res["halted"]["account_id"] == sent[0][0]
    assert (proj / HALT_FILE).exists()
    assert mgr.get_account(sent[0][0])["error_message"].startswith("BLOCKED:")

    monkeypatch.setattr(pool_runner, "_build_engine", lambda args: engine)
    rc = pool_runner.main(["keyframes", str(proj)])
    capsys.readouterr()
    assert rc == 4 and len(sent) == 1, "the halted project sent keyframes again"
