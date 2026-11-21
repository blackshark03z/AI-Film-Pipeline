"""Review of round 13 (stop-all): every send path honours one halt, and only a visible challenge halts."""
import asyncio
import json
from pathlib import Path

import pytest

from muse_studio.tests import _halt_env  # noqa: F401  (scratch MUSE_HALT_FILE / AFP_STATE_DIR even without the conftest)

from muse_studio.core.account_manager import AccountManager
from muse_studio.core.headless_muse_client import (
    BlockedException,
    GenerationFailedException,
    HeadlessMuseClient,
    LeaseLostException,
    QuotaExceededException,
)
from muse_studio.core.keyframe_composer import KeyframeComposer
from muse_studio.core.parallel_pool_engine import HALT_FILE, UNCONFIRMED_FILE, ParallelPoolEngine
KF_LEDGER_FILE = "unconfirmed_keyframes.json"
from muse_studio.tests.test_lane_review_r2 import _kf_project, _make_accounts, _submitted
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project


@pytest.fixture(autouse=True)
def _temp_lease_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path / "lane_leases.json"))


def _clips(output_dir, shots):
    out = Path(output_dir) / "verified_clips"
    out.mkdir(parents=True, exist_ok=True)
    verified = {}
    for idx, s in enumerate(shots, start=1):
        p = out / f"shot_{idx:02d}.mp4"
        p.write_bytes(b"\x00" * 2048)
        verified[s.shot_id] = {"path": str(p), "bytes": p.stat().st_size}
    return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}


# ---- 1. a worker mid-upload never sends after another account hit a CAPTCHA ------------------------------------------
def test_video_worker_mid_upload_does_not_send_after_halt(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 3)
    started, sent = [], []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False, lease_guard=None):
            n = len(started)
            started.append(account_id)
            if n == 1:
                await asyncio.sleep(0.02)
                raise BlockedException("BLOCKED: CAPTCHA")
            await asyncio.sleep(0.15)  # still uploading when the other account is blocked
            if lease_guard is not None and not lease_guard():
                raise LeaseLostException("guard refused before submit")
            sent.append(account_id)
            return _clips(output_dir, shots)

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False,
                                qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}})
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=12)
    res = engine.run_videos(project_dir=proj, max_accounts=2, max_rounds=3, simulate=False)
    assert sent == [], f"a batch was submitted after the halt: {sent}"
    assert len(started) == 2 and res["status"] == "HALTED"
    entries = json.loads((proj / UNCONFIRMED_FILE).read_text(encoding="utf-8"))["entries"]
    assert {e["status"] for e in entries} == {"RESOLVED"} and {e["reason"] for e in entries} == {"NOT_SENT"}


def test_keyframe_worker_mid_upload_does_not_send_after_halt(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 3)
    started, sent = [], []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False, lease_guard=None):
            n = len(started)
            started.append(account_id)
            if n == 1:
                await asyncio.sleep(0.02)
                raise BlockedException("BLOCKED: CAPTCHA")
            await asyncio.sleep(0.15)
            if lease_guard is not None and not lease_guard():
                raise LeaseLostException("guard refused before submit")
            sent.append(account_id)
            return await HeadlessMuseClient(self.account_manager).generate_keyframes_batch(
                account_id=account_id, keyframes=keyframes, batch_id=batch_id, output_dir=output_dir, simulate=True)

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False)
    res = engine.run_keyframes(project_dir=_kf_project(tmp_path, n_chars=8), max_accounts=2, simulate=False)
    assert sent == [], f"a keyframe batch was submitted after the halt: {sent}"
    assert len(started) == 2 and res["status"] == "HALTED"


# ---- 3. a keyframe batch blocked after Enter is never resent, not even after --clear-halt ----------------------------
def test_submitted_keyframes_survive_clear_halt(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 2)
    sent = []
    mode = {"block": True}

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False):
            sent.append([k.kf_id for k in keyframes])
            if mode["block"]:
                raise _submitted(BlockedException("BLOCKED: verification page after submit"))
            return await HeadlessMuseClient(self.account_manager).generate_keyframes_batch(
                account_id=account_id, keyframes=keyframes, batch_id=batch_id, output_dir=output_dir, simulate=True)

    proj = _kf_project(tmp_path)
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False)
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    assert res["status"] == "HALTED" and len(sent) == 1
    first = sorted(sent[0])
    ledger = json.loads((proj / KF_LEDGER_FILE).read_text(encoding="utf-8"))["entries"]
    assert {e["status"] for e in ledger} == {"UNCONFIRMED"} and sorted(e["kf_id"] for e in ledger) == first

    mode["block"] = False
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False, clear_halt=True)
    assert len(sent) == 1, f"--clear-halt resent unreconciled keyframes: {sent[1:]}"
    assert sorted(e["kf_id"] for e in res["unconfirmed_keyframes"]) == first
    assert not (proj / HALT_FILE).exists()

    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False, release_unconfirmed=True)
    assert len(sent) == 2 and sorted(sent[1]) == first, "an explicit release did not allow the resend"


def test_pending_keyframe_send_blocks_resume(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 1)
    sent = []

    class Crash:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False):
            sent.append([k.kf_id for k in keyframes])
            raise KeyboardInterrupt  # the process dies mid-send

    proj = _kf_project(tmp_path)
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Crash, sync_ui=False)
    with pytest.raises(KeyboardInterrupt):
        engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    ledger = json.loads((proj / KF_LEDGER_FILE).read_text(encoding="utf-8"))["entries"]
    assert {e["status"] for e in ledger} == {"PENDING_SEND"}
    engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    assert len(sent) == 1, "a keyframe batch pending since a crash was resent"


# ---- 2. other entry points: composer, cli keyframes, autoprod ----------------------------------------------------------
def _composer_client(mgr, calls, exc):
    class C:
        account_manager = mgr

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, simulate=False, **kw):
            calls.append(account_id)
            raise exc
    return C()


@pytest.mark.parametrize("exc", [
    BlockedException("BLOCKED: CAPTCHA"),
    _submitted(GenerationFailedException("no image after send")),
])
def test_composer_never_fails_over_a_block_or_a_submitted_batch(tmp_path: Path, exc):
    mgr, ids = _make_accounts(tmp_path, 2)
    calls = []
    with pytest.raises(type(exc)):
        asyncio.run(KeyframeComposer._dispatch_kf_batch_with_failover(
            client=_composer_client(mgr, calls, exc), account_ids=ids, start_offset=0, chunk=[],
            batch_id="KF_X", out_dir=tmp_path / "kf", simulate=False))
    assert len(calls) == 1, f"failed over to another account: {calls}"


def test_composer_quota_still_fails_over(tmp_path: Path):
    mgr, ids = _make_accounts(tmp_path, 2)
    calls = []
    with pytest.raises(QuotaExceededException):
        asyncio.run(KeyframeComposer._dispatch_kf_batch_with_failover(
            client=_composer_client(mgr, calls, QuotaExceededException("out of credits")), account_ids=ids,
            start_offset=0, chunk=[], batch_id="KF_X", out_dir=tmp_path / "kf", simulate=False))
    assert len(calls) == 2


# cli keyframes / autoprod real runs: replaced in round 15 (they no longer send; see test_stop_all_r15.py).


# ---- 4. a challenge after a login step is BLOCKED, not an ordinary ERROR -----------------------------------------------
def test_login_challenge_after_log_in_click_is_blocked(tmp_path: Path):
    page = tmp_path / "login.html"
    page.write_text(
        "<html><body><h1>Muse</h1>"
        "<button onclick=\"var d=document.createElement('div');d.setAttribute('role','dialog');"
        "d.textContent='We detected unusual activity on this account.';document.body.appendChild(d);\">"
        "Log in</button></body></html>", encoding="utf-8")
    mgr, ids = _make_accounts(tmp_path, 1)
    mgr.update_account(ids[0], status="UNCHECKED")
    res = mgr.auto_login_and_verify(ids[0], page.as_uri())
    assert res["status"] == "BLOCKED", res
    assert mgr.get_account(ids[0])["error_message"].startswith("BLOCKED:")


# ---- 5. only a visible challenge or a system notice halts --------------------------------------------------------------
COMPOSER = '<main><div class="chat"><div class="message">{msg}</div></div><textarea placeholder="Message"></textarea>' \
           '<input type="file"></main>'


async def _probe(html: str):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.route("**/*", lambda route: route.abort())  # offline: no request leaves the test
            await page.set_content(html)
            await HeadlessMuseClient._check_page_errors(page)
        finally:
            await browser.close()


@pytest.mark.parametrize("html", [
    COMPOSER.format(msg='MARCUS: "Verify your identity," he says. Suspicious activity on the dock.'),
    COMPOSER.format(msg="ok") + '<script src="https://cdn.example.com/recaptcha-helper.js"></script>',
    COMPOSER.format(msg="ok") + '<div class="grecaptcha-badge"><iframe src="https://www.google.com/recaptcha/api2/'
                                'anchor?size=invisible" width="256" height="60"></iframe></div>',
    COMPOSER.format(msg="ok") + '<div role="dialog" style="display:none">We noticed unusual activity</div>',
])
def test_no_halt_without_a_visible_challenge(html):
    asyncio.run(_probe(html))


@pytest.mark.parametrize("html", [
    COMPOSER.format(msg="ok") + '<iframe src="https://newassets.hcaptcha.com/captcha/v1/x" width="300" '
                                'height="150"></iframe>',
    COMPOSER.format(msg="ok") + '<div role="dialog" aria-modal="true">We noticed unusual activity on your '
                                'account.</div>',
    '<body><h2>Verify you are human</h2><p>Checking your browser.</p></body>',
])
def test_visible_challenge_halts(html):
    with pytest.raises(BlockedException):
        asyncio.run(_probe(html))


def test_quota_text_is_still_quota():
    with pytest.raises(QuotaExceededException):
        asyncio.run(_probe(COMPOSER.format(msg="ok") + "<p>You are out of credits</p>"))


def _sync_detect(html: str):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/*", lambda route: route.abort())
            page.set_content(html)
            return AccountManager._detect_captcha_or_block(page)
        finally:
            browser.close()


def test_login_detector_ignores_otp_form_and_catches_dialog():
    assert _sync_detect('<h2>Verify it\'s you</h2><input aria-label="6-digit security code">') is None
    msg = _sync_detect('<div role="alertdialog">Your account has been locked.</div>')
    assert msg and msg.startswith("BLOCKED:")
