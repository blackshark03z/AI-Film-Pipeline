"""Round 15 (Codex review of round 14): one choke point before every submit and one machine-wide halt.

One regression test (at least) per finding 1-13, plus the halt-file lock / pending-marker rules of lane contract v8.
Every test runs with MUSE_HALT_FILE / AFP_STATE_DIR in tmp (conftest `_isolated_halt`): the real halt file is never
created, nothing leaves the machine (pages are local, requests are aborted).
"""
import asyncio
import json
import os
import re
import time
import zipfile
from pathlib import Path

import pytest

from muse_studio.tests import _halt_env  # noqa: F401  (scratch MUSE_HALT_FILE / AFP_STATE_DIR even without the conftest)

import muse_studio.cli as cli
import muse_studio.core.headless_muse_client as hmc
from muse_studio.core import send_halt
from muse_studio.core.account_manager import AccountManager
from muse_studio.core.batch_packager import KeyframeItem
from muse_studio.core.browser_worker import MuseBrowserWorker
from muse_studio.core.headless_muse_client import (
    BlockedException,
    HaltedException,
    HeadlessMuseClient,
    LeaseLostException,
    trip_block,
)
from muse_studio.core.parallel_pool_engine import (
    KF_LEDGER_FILE, ParallelPoolEngine, adopt_legacy_kf_batches, kf_result_image,
)
from muse_studio.tests.test_lane_review_r2 import _kf_project, _make_accounts
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project
from muse_studio.tests.test_review6_fixes import _FakeAccounts, _FakePage


@pytest.fixture(autouse=True)
def _temp_lease_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path / "lane_leases.json"))


def _halt_file() -> Path:
    return send_halt.halt_path()


def _other_process_halts(account_id="acc_other", batch_id="B_OTHER"):
    """What another Muse process leaves behind: the machine-wide halt file (this process's memory is untouched)."""
    path = _halt_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reason": "BLOCKED", "account_id": account_id, "batch_id": batch_id}),
                    encoding="utf-8")


def test_tests_never_touch_the_real_halt_file():
    real = Path(send_halt.__file__).resolve().parent.parent / "data" / "muse_halt.json"
    assert _halt_file().resolve() != real.resolve()


class _ChallengePage:
    """A page whose probe shows a visible CAPTCHA widget."""

    async def evaluate(self, *a, **k):
        return {"widget": True, "text": "", "interstitial": False, "otp": False}


def _warm_client(page, account_id="acc_a"):
    client = HeadlessMuseClient(_FakeAccounts())
    client.enable_warm_pool(True)
    client._warm_sessions[account_id] = (None, None, page)
    return client


def _stub_chat(monkeypatch):
    async def noop(*a, **k):
        return None

    async def ready(*a, **k):
        return True

    monkeypatch.setattr(HeadlessMuseClient, "_start_fresh_chat", staticmethod(noop))
    monkeypatch.setattr(HeadlessMuseClient, "_is_chat_ready", staticmethod(ready))


# ---- 1. a block halts every worker synchronously, before any awaited cleanup -----------------------------------------
def test_block_halts_other_worker_before_cleanup(tmp_path: Path, monkeypatch):
    real_sleep = asyncio.sleep

    async def fast_sleep(*a, **k):
        await real_sleep(0)

    monkeypatch.setattr(hmc.asyncio, "sleep", fast_sleep)
    _stub_chat(monkeypatch)

    async def scenario():
        uploaded = asyncio.Event()
        page_a = _FakePage(on_upload=uploaded.set)
        client = _warm_client(page_a)
        zp = tmp_path / "h.zip"
        zp.write_bytes(b"x")
        a = asyncio.create_task(client._dispatch_zip_and_wait_result(
            "acc_a", zp, "msg", tmp_path / "r.zip", timeout_seconds=1, lease_guard=lambda: True))
        await uploaded.wait()  # A is mid-upload
        with pytest.raises(BlockedException):
            await HeadlessMuseClient._check_page_errors(_ChallengePage(), "acc_b", "B_B")
        # B's cleanup never even starts here: the engine has not learned of the block yet.
        assert _halt_file().exists(), "the halt was not published at the moment of detection"
        res = await asyncio.gather(a, return_exceptions=True)
        return page_a, res[0]

    page_a, exc = asyncio.run(scenario())
    assert isinstance(exc, HaltedException), exc
    assert "press:Enter" not in page_a.events, "worker A submitted after another account was blocked"
    assert not getattr(exc, "submitted", False)


# ---- 2. the web UI path (/api/render/start -> QueueDispatcher -> MuseBrowserWorker) honours the stop -----------------
def test_browser_worker_refuses_while_halted(tmp_path: Path, monkeypatch):
    mgr, ids = _make_accounts(tmp_path, 1)
    worker = MuseBrowserWorker(ids[0], mgr)

    async def no_browser(*a, **k):
        pytest.fail("the browser was started while Muse sending is halted")

    monkeypatch.setattr(worker, "start", no_browser)
    _other_process_halts()
    with pytest.raises(HaltedException):
        asyncio.run(worker.generate_shot("p", [], tmp_path / "out.mp4", simulate=False))


def test_queue_dispatcher_never_requeues_a_block(tmp_path: Path, monkeypatch):
    import muse_studio.core.queue_dispatcher as qd
    from muse_studio.core.project_manager import ProjectManager

    mgr, ids = _make_accounts(tmp_path, 2)
    pm = ProjectManager(projects_dir=tmp_path / "projects")
    proj = pm.create_project("Halt", mode="batch_parallel")
    pid = proj["id"]
    pm.add_shot(pid, prompt="Shot A")
    pm.add_shot(pid, prompt="Shot B")
    calls = []

    async def blocked_generate(self, *a, **k):
        calls.append(self.account_id)
        raise trip_block("BLOCKED: CAPTCHA shown", self.account_id, "WEBUI")

    monkeypatch.setattr(qd.MuseBrowserWorker, "generate_shot", blocked_generate)
    monkeypatch.setattr(qd.FilmQCEngine, "validate_shot_preflight", staticmethod(lambda s, p=None: (True, [])))

    async def scenario():
        d = qd.QueueDispatcher(mgr, pm)
        assert (await d.start(pid, concurrency=1, simulate=False))["success"]
        for _ in range(80):
            await asyncio.sleep(0.1)
            if pm.get_project(pid)["status"] == "HALTED" and not d._active_workers:
                break
        again = await d.start(pid, concurrency=1, simulate=False)
        return d, again

    d, again = asyncio.run(scenario())
    shots = pm.get_project(pid)["shots"]
    assert calls == [ids[0]] or len(calls) == 1, f"a blocked shot was retried / requeued: {calls}"
    assert pm.get_project(pid)["status"] == "HALTED" and not d.is_running
    assert [s["status"] for s in shots].count("FAILED") == 1 and "BLOCKED" in shots[0]["error"]
    assert shots[1]["status"] == "PENDING", "the dispatcher kept dispatching after the block"
    assert not again["success"] and again["status"] == "HALTED", "start() ignored the machine-wide halt"


# ---- 3. the halt is machine-wide: project A blocks project B, and a running engine sees another process's halt ------
def test_halt_of_project_a_stops_engine_on_project_b(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 2)
    calls = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, **kw):
            calls.append(kw["account_id"])
            raise AssertionError("sent while halted")

    proj_a = tmp_path / "A"
    proj_a.mkdir()
    send_halt.publish_halt(send_halt.halt_info(BlockedException("BLOCKED"), "acc_x", "KF_A"), proj_a)
    send_halt._reset_memory()  # project B runs in another process: only the file is shared
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False)
    res = engine.run_keyframes(project_dir=_kf_project(tmp_path), max_accounts=1, simulate=False)
    assert res["status"] == "HALTED" and calls == []
    assert res["halt_path"] == str(_halt_file())


def test_running_engine_sees_halt_from_another_process(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 3)
    started, sent = [], []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False, lease_guard=None):
            started.append(account_id)
            if len(started) == 1:
                _other_process_halts()  # another lane / process is blocked meanwhile
            await asyncio.sleep(0.05)
            if lease_guard is not None and not lease_guard():
                raise LeaseLostException("guard refused before submit")
            sent.append(account_id)
            raise AssertionError("sent while halted")

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False,
                                qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}})
    res = engine.run_videos(project_dir=_seed_manifest_project(tmp_path / "proj", num_shots=12), max_accounts=2,
                            max_rounds=3, simulate=False)
    assert sent == [] and res["status"] == "HALTED"
    assert len(started) <= 2, f"workers kept dispatching after the halt: {started}"


def test_clear_halt_keeps_pending_markers_and_engine_still_refuses(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 1)
    _other_process_halts()
    pdir = send_halt.pending_dir()
    pdir.mkdir(parents=True, exist_ok=True)
    marker = pdir / "LANE_X-abc.json"
    marker.write_text(json.dumps({"provider": "muse", "reason": "BLOCKED"}), encoding="utf-8")
    engine = ParallelPoolEngine(account_manager=mgr, sync_ui=False)
    res = engine.run_keyframes(project_dir=_kf_project(tmp_path), max_accounts=1, simulate=False, clear_halt=True)
    assert not _halt_file().exists(), "--clear-halt did not remove the Muse halt"
    assert marker.exists(), "--clear-halt removed a halt_pending marker (Owner-only)"
    assert res["status"] == "HALTED" and res["halted"]["signal"] == "halt_pending"


def test_pool_runner_exits_4_with_halt_publication(tmp_path: Path, capsys):
    from muse_studio import pool_runner

    _make_accounts(tmp_path, 1)
    _other_process_halts()
    rc = pool_runner.main(["keyframes", str(_kf_project(tmp_path)), "--no-ui-sync",
                           "--accounts-file", str(tmp_path / "accounts.json"),
                           "--profiles-dir", str(tmp_path / "profiles")])
    out = capsys.readouterr().out
    res = json.loads(out[out.index("{"):])
    assert rc == send_halt.HALTED_EXIT_CODE == 4
    assert res["status"] == "HALTED" and res["halt_publication"] == "ALREADY_HALTED"


# ---- 4/5. ONE production send path: real `cli keyframes` and real autoprod refuse ------------------------------------
def test_cli_keyframes_real_run_is_refused(tmp_path: Path, monkeypatch, capsys):
    calls = []

    async def gen(*a, **k):
        calls.append(1)
        return {"rejected": []}

    mgr, _ = _make_accounts(tmp_path, 2)
    monkeypatch.setattr(cli.KeyframeComposer, "generate_and_verify_keyframes", staticmethod(gen))
    monkeypatch.setattr(cli, "AccountManager", lambda: mgr)
    monkeypatch.setattr(cli, "HeadlessMuseClient", lambda m: pytest.fail("a client was built for a real run"))
    monkeypatch.setattr(cli, "cmd_accounts_verify", lambda a: pytest.fail("bulk verify ran"))
    proj = tmp_path / "proj"
    proj.mkdir()
    rc = cli.main(["keyframes", str(proj)])
    rep = json.loads(capsys.readouterr().out)
    assert rc == 2 and calls == []
    assert rep["status"] == "REFUSED_USE_POOL_RUNNER" and "pool_runner keyframes" in rep["message"]
    with pytest.raises(SystemExit):
        cli.main(["keyframes", str(proj), "--clear-halt"])  # the flag left with the send path
    capsys.readouterr()


def test_autoprod_real_run_is_refused_before_any_account(tmp_path: Path, capsys):
    from muse_studio.autoprod import main as autoprod_main
    from muse_studio.core.autoprod_orchestrator import AutoprodOrchestrator

    script = tmp_path / "heal.txt"
    script.write_text("INT. OFFICE - NIGHT\n\nMARCUS\nCheck the silver badge.\n", encoding="utf-8")
    mgr, _ = _make_accounts(tmp_path, 2)
    mgr.auto_login_and_verify = lambda *a, **k: pytest.fail("autoprod logged in for a real run")
    calls = []

    class Client:
        def __init__(self, account_manager):
            pass

        async def generate_keyframes_batch(self, **kw):
            calls.append("kf")

        async def generate_videos_batch(self, **kw):
            calls.append("video")

    orch = AutoprodOrchestrator(account_manager=mgr, client_factory=Client, sync_ui=False)
    state = orch.run(input_path=script, project_dir=tmp_path / "proj", max_rounds=3, simulate=False, use_llm=False)
    assert state["status"] == "REFUSED_USE_POOL_RUNNER" and calls == []
    assert "pool_runner keyframes" in state["message"] and "pool_runner videos" in state["message"]

    rc = autoprod_main([str(script), "--project-dir", str(tmp_path / "proj2"), "--no-llm", "--no-ui-sync",
                        "--accounts-file", str(tmp_path / "accounts.json"),
                        "--profiles-dir", str(tmp_path / "profiles")])
    capsys.readouterr()
    assert rc == 2


# ---- 6. bulk verify stops at the first BLOCKED and publishes the halt -----------------------------------------------
def test_accounts_verify_stops_at_first_block(tmp_path: Path, monkeypatch, capsys):
    mgr, ids = _make_accounts(tmp_path, 3)
    seen = []

    def fake_login(aid, *a, **k):
        seen.append(aid)
        return {"status": "BLOCKED", "message": "BLOCKED: CAPTCHA at login"}

    mgr.auto_login_and_verify = fake_login
    monkeypatch.setattr(cli, "AccountManager", lambda: mgr)
    rc = cli.main(["accounts-verify"])
    capsys.readouterr()
    assert rc == 4 and seen == [ids[0]], f"verify went on after a block: {seen}"
    halt = json.loads(_halt_file().read_text(encoding="utf-8"))
    assert halt["reason"] == "BLOCKED" and halt["account_id"] == ids[0]


# ---- 7/8. keyframe ledger: legacy batches adopted, release only on a verified result of that submission -------------
def _sim_kf_layout(tmp_path: Path):
    """A keyframe project whose batches were handed off (manifests present) but whose results never arrived."""
    mgr, _ = _make_accounts(tmp_path, 1)
    proj = _kf_project(tmp_path)
    ParallelPoolEngine(account_manager=mgr, sync_ui=False).run_keyframes(project_dir=proj, max_accounts=1,
                                                                        simulate=True)
    batches = []
    for kind in ("anchors", "setups", "keyframes"):
        d = proj / "assets" / kind
        for f in d.glob("*.png"):
            f.unlink()  # the images never arrived
        for b in sorted((d / "_batches").glob("*")) if (d / "_batches").is_dir() else []:
            for rz in b.glob("*_kf_result.zip"):
                rz.unlink()
            m = json.loads((b / f"{b.name}_kf_manifest.json").read_text(encoding="utf-8"))
            batches.append((b.name, b, [e["kf_id"] for e in m["keyframes"]]))
    assert batches, "the dry run handed off no keyframe batch"
    return mgr, proj, batches


class _CountingKfClient:
    sent: list = []

    def __init__(self, account_manager):
        self.account_manager = account_manager

    async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                       simulate=False, **kw):
        _CountingKfClient.sent.extend(k.kf_id for k in keyframes)
        return await HeadlessMuseClient(self.account_manager).generate_keyframes_batch(
            account_id=account_id, keyframes=keyframes, batch_id=batch_id, output_dir=output_dir, simulate=True)


def test_legacy_keyframe_batches_are_adopted_not_resent(tmp_path: Path):
    mgr, proj, batches = _sim_kf_layout(tmp_path)
    assert not (proj / KF_LEDGER_FILE).exists()
    legacy = sorted(k for _, _, kfs in batches for k in kfs)
    _CountingKfClient.sent = []
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=_CountingKfClient, sync_ui=False)
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    assert not set(_CountingKfClient.sent) & set(legacy), f"legacy submissions resent: {_CountingKfClient.sent}"
    assert sorted(res["kf_legacy_adopted"]) == legacy and res["status"] != "COMPLETED"
    ledger = json.loads((proj / KF_LEDGER_FILE).read_text(encoding="utf-8"))["entries"]
    assert {e["status"] for e in ledger if e.get("legacy")} == {"UNCONFIRMED"}


def _result_zip(out_dir: Path, bid: str, kf_id: str, raw: bytes = None):
    zp = out_dir / f"{bid}_kf_result.zip"
    if raw is None:
        HeadlessMuseClient._simulate_keyframe_zip([KeyframeItem(kf_id=kf_id, prompt="x")], zp)
    else:
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr(f"{kf_id}.png", raw)
    return zp


def test_tiny_png_never_releases_and_verified_result_does(tmp_path: Path):
    mgr, proj, batches = _sim_kf_layout(tmp_path)
    bid, bdir, kfs = batches[0]
    kf = kfs[0]
    entry = {"kf_id": kf, "batch_id": bid, "account_id": "acc", "status": "UNCONFIRMED", "out_dir": str(bdir),
             "submitted_epoch": time.time() - 60}
    (proj / KF_LEDGER_FILE).write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    (proj / "assets" / "anchors" / f"{kf}.png").write_bytes(b"\x89")  # a 1-byte "image" in the asset dir
    _result_zip(bdir, bid, kf, raw=b"\x89")  # and in the result zip
    assert kf_result_image(bdir, bid, kf, entry["submitted_epoch"]) is None
    _CountingKfClient.sent = []
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=_CountingKfClient, sync_ui=False)
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    led = {e["kf_id"]: e for e in json.loads((proj / KF_LEDGER_FILE).read_text(encoding="utf-8"))["entries"]}
    assert led[kf]["status"] == "UNCONFIRMED", "a 1-byte PNG released an unreconciled submission"
    assert kf not in _CountingKfClient.sent and kf in res["withheld_keyframes"]

    # A result zip older than the submission belongs to an earlier send of the same batch id: not evidence.
    _result_zip(bdir, bid, kf)
    old = time.time() - 3600
    os.utime(bdir / f"{bid}_kf_result.zip", (old, old))
    assert kf_result_image(bdir, bid, kf, entry["submitted_epoch"]) is None

    _result_zip(bdir, bid, kf)  # a real image of this submission arrived
    (proj / "assets" / "anchors" / f"{kf}.png").unlink()
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    rel = [e for e in res.get("unconfirmed_released") or [] if e["kf_id"] == kf]
    assert rel and rel[0]["reason"] == "RESULT_RECEIVED" and rel[0]["result"]["bytes"] >= 5 * 1024


def test_unreadable_legacy_manifest_fails_closed(tmp_path: Path):
    b = tmp_path / "_batches" / "KF_ANCHOR_01"
    b.mkdir(parents=True)
    (b / "KF_ANCHOR_01_kf_manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        adopt_legacy_kf_batches([tmp_path / "_batches"], [])


# ---- 9-13. the detector, in a real (offline) Chromium page -----------------------------------------------------------
COMPOSER = '<main><div class="chat"><div class="message">{msg}</div></div><textarea placeholder="Message"></textarea>' \
           '<input type="file"></main>'
HCAPTCHA = '<iframe src="https://newassets.hcaptcha.com/captcha/v1/x" width="300" height="150"></iframe>'


async def _with_page(html: str, fn):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.route("**/*", lambda route: route.abort())  # offline: no request leaves the test
            await page.set_content(html)
            return await fn(page)
        finally:
            await browser.close()


def _probe(html: str):
    return asyncio.run(_with_page(html, lambda page: HeadlessMuseClient._check_page_errors(page, "acc_t")))


def test_challenge_shown_during_upload_is_caught_before_enter(tmp_path: Path, monkeypatch):
    """Finding 9: a hidden challenge iframe that appears while the zip uploads stops the real dispatch before Enter."""
    _stub_chat(monkeypatch)
    html = ('<main><textarea placeholder="Message"></textarea><input type="file" id="f"></main>'
            f'<div id="cap" style="display:none">{HCAPTCHA}</div>'
            "<script>window.__entered=false;"
            "document.getElementById('f').addEventListener('change',()=>{"
            "document.getElementById('cap').style.display='block'});"
            "document.addEventListener('keydown',e=>{if(e.key==='Enter')window.__entered=true;});</script>")
    zp = tmp_path / "h.zip"
    zp.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    async def run(page):
        client = _warm_client(page)
        with pytest.raises(BlockedException) as ei:
            await client._dispatch_zip_and_wait_result("acc_a", zp, "msg", tmp_path / "r.zip", timeout_seconds=1,
                                                       lease_guard=lambda: True)
        return ei.value, await page.evaluate("window.__entered")

    exc, entered = asyncio.run(_with_page(html, run))
    assert entered is False, "Enter was pressed with a challenge on screen"
    assert not getattr(exc, "submitted", False) and _halt_file().exists()


@pytest.mark.parametrize("html", [
    # finding 10: an interstitial overlay without a dialog role, composer still mounted underneath
    COMPOSER.format(msg="ok") + '<div style="position:fixed;inset:0;background:#fff;z-index:9">'
                                '<p>We detected unusual activity from your network.</p></div>',
    # a smaller layer painted over the composer
    COMPOSER.format(msg="ok") + '<div style="position:fixed;top:0;left:0;width:420px;height:220px;background:#fff;'
                                'z-index:9">Suspicious activity: please wait.</div>',
    # finding 12: Vietnamese human-check text
    '<body><h2>Vui lòng xác minh bạn là con người</h2></body>',
    COMPOSER.format(msg="ok") + '<div role="dialog">Tôi không phải là người máy</div>',
    COMPOSER.format(msg="ok") + '<div role="alert">Xác nhận bạn không phải người máy để tiếp tục</div>',
])
def test_overlay_and_vietnamese_challenges_halt(html):
    with pytest.raises(BlockedException):
        _probe(html)
    assert _halt_file().exists()


@pytest.mark.parametrize("html", [
    # the app shell (a large absolute layer) holds the composer and chat: never read as a notice
    '<div style="position:absolute;inset:0">' + COMPOSER.format(msg="He mentions unusual activity at the dock.")
    + '</div>',
    # finding 13: a CAPTCHA preloaded inside a transparent ancestor is not shown
    COMPOSER.format(msg="ok") + f'<div style="opacity:0">{HCAPTCHA}</div>',
    COMPOSER.format(msg="ok") + f'<div style="visibility:hidden">{HCAPTCHA}</div>',
])
def test_no_halt_without_a_visible_challenge_r15(html):
    _probe(html)
    assert not _halt_file().exists()


def test_hidden_ancestor_then_shown_halts():
    html = COMPOSER.format(msg="ok") + f'<div id="w" style="opacity:0">{HCAPTCHA}</div>'

    async def run(page):
        await HeadlessMuseClient._check_page_errors(page, "acc_t")  # hidden: no halt
        assert not _halt_file().exists()
        await page.evaluate("document.getElementById('w').style.opacity='1'")
        with pytest.raises(BlockedException):
            await HeadlessMuseClient._check_page_errors(page, "acc_t")

    asyncio.run(_with_page(html, run))
    assert _halt_file().exists()


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


def test_otp_form_exempts_only_the_otp_instructions():
    """Finding 11: next to a visible code field, an unusual-activity / locked notice still blocks."""
    otp = '<h2>Verify it\'s you</h2><p>Enter the code we emailed you.</p><input aria-label="6-digit security code">'
    assert _sync_detect(otp) is None
    assert (_sync_detect(otp + "<p>We detected unusual activity on this account.</p>") or "").startswith("BLOCKED:")
    assert (_sync_detect(otp + "<p>Your account has been locked.</p>") or "").startswith("BLOCKED:")
    assert (_sync_detect(otp + "<p>Tôi không phải là người máy</p>") or "").startswith("BLOCKED:")


# ---- halt-file lock (contract v8 §11): timeout -> pending marker -> every gate refuses ------------------------------
def test_lock_timeout_writes_pending_marker_and_gates_refuse(monkeypatch):
    monkeypatch.setenv("MUSE_HALT_LOCK_TIMEOUT_S", "0.2")
    send_halt.set_lane_id("LANE_T")
    try:
        with send_halt.halt_file_lock(1.0):  # another holder keeps the lock
            status = send_halt.publish_halt(send_halt.halt_info(BlockedException("BLOCKED"), "acc", "B1"))
            assert status == "PENDING"
            assert send_halt.send_stop()["signal"] == "MEMORY", "Enter was not disabled in memory first"
        markers = list(send_halt.pending_dir().glob("LANE_T-*.json"))
        assert len(markers) == 1 and "acc" in markers[0].read_text(encoding="utf-8")
        assert not _halt_file().exists()

        status_memory = send_halt.publication_status()
        send_halt._reset_memory()  # a different process: only the marker is visible
        stop = send_halt.send_stop()
        assert stop is not None and stop["signal"] == "halt_pending"
        with pytest.raises(HaltedException):
            hmc.raise_if_halted("acc_other")

        # back in the blocked process: finishing the publication writes the halt file under the lock
        send_halt._PUBLICATION, send_halt._PENDING_INFO = status_memory, {"reason": "BLOCKED", "account_id": "acc"}
        send_halt._MEMORY_HALT = {"reason": "BLOCKED", "account_id": "acc"}
        assert send_halt.finish_publication(window_s=2) == "PUBLISHED" and _halt_file().exists()
        send_halt.clear_halt()
        assert not _halt_file().exists() and markers[0].exists(), "clear removed a halt_pending marker"
        assert send_halt.load_halt() is not None
    finally:
        send_halt.set_lane_id(None)


def test_unreadable_halt_file_refuses():
    path = _halt_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{corrupt", encoding="utf-8")
    stop = send_halt.send_stop()
    assert stop is not None and stop["reason"] == "UNREADABLE"


# =====================================================================================================================
# Fixes A, B, C of the live-run review (lessons L37, L38)
# =====================================================================================================================
# ---- A. a test can never reach the production halt --------------------------------------------------------------------
def test_halt_paths_refuse_the_production_default_under_pytest(monkeypatch):
    monkeypatch.delenv("MUSE_HALT_FILE", raising=False)
    monkeypatch.delenv("AFP_STATE_DIR", raising=False)
    with pytest.raises(send_halt.ProductionHaltPathInTest):
        send_halt.halt_path()
    with pytest.raises(send_halt.ProductionHaltPathInTest):
        send_halt.pending_dir()
    with pytest.raises(send_halt.ProductionHaltPathInTest):
        send_halt.send_stop()  # the pre-Enter gate cannot even read the production halt


def test_scratch_halt_env_is_set_at_module_import():
    from muse_studio.tests import _halt_env

    assert os.environ.get("MUSE_HALT_FILE") and os.environ.get("AFP_STATE_DIR")
    real = Path(send_halt.__file__).resolve().parent.parent / "data"
    assert not str(send_halt.halt_path().resolve()).startswith(str(real.resolve()))
    assert not str(send_halt.pending_dir().resolve()).startswith(str((Path.home() / ".afp").resolve()))
    assert callable(_halt_env.ensure_scratch_halt_env)


# ---- B. a gate refusal is a HALT, never a silent loss -------------------------------------------------------------------
def _halted_exc(reason="OWNER_PAUSE", detail="pause production until the merge is done"):
    exc = HaltedException("Muse sending halted (MUSE_HALT_FILE: %s); not sent" % reason)
    exc.stop = {"reason": reason, "detail": detail, "signal": "MUSE_HALT_FILE"}
    return exc


def test_gate_refusal_without_standby_ends_halted_with_record_and_batch_errors(tmp_path: Path, monkeypatch, capsys):
    """The live-run defect: the refusal reached NOT_SENT, the requeued chunk had no account to take it and vanished."""
    import muse_studio.pool_runner as pool_runner

    mgr, _ = _make_accounts(tmp_path, 1)
    sent = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False, lease_guard=None):
            sent.append([k.kf_id for k in keyframes])
            raise _halted_exc()  # no halt file exists here: only the exception carries the stop record

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False)
    monkeypatch.setattr(pool_runner, "_build_engine", lambda args: engine)
    proj = _kf_project(tmp_path, n_chars=8)  # two chunks of 4
    rc = pool_runner.main(["keyframes", str(proj)])
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert rc == 4 and res["status"] == "HALTED"
    assert res["halted"]["reason"] == "OWNER_PAUSE"
    assert len(sent) == 1, "a refused chunk was retried / the next chunk was sent"
    # the halt line prints the record's own reason, never a made-up CAPTCHA
    assert "OWNER_PAUSE" in captured.err and "CAPTCHA" not in captured.err
    assert "pause production" in captured.err
    # nothing is dropped: every planned image is accounted for in batch_errors (refused chunk + undispatched chunk)
    err_ids = {k for e in res["batch_errors"] for k in e.get("kf_ids", [])}
    assert err_ids == set(res["missing_keyframes"]) and len(err_ids) == 8
    assert all(e["submitted"] is False for e in res["batch_errors"])


def test_not_sent_failure_without_account_left_is_reported_not_dropped(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 1)
    calls = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False, lease_guard=None):
            calls.append(batch_id)
            raise hmc.QuotaExceededException("out of usage")  # not submitted; no standby account exists

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False)
    proj = _kf_project(tmp_path, n_chars=4)
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    assert res["status"] == "INCOMPLETE"
    err_ids = {k for e in res["batch_errors"] for k in e.get("kf_ids", [])}
    assert err_ids == set(res["missing_keyframes"]) and err_ids, "a failed, requeued chunk vanished without a trace"
    assert any(e.get("not_dispatched") for e in res["batch_errors"])
    assert "KF_ANCHOR" in res["skipped_phases"]
    assert "no account was left" in res["skipped_phases_note"]


def test_later_phases_report_when_no_account_is_left(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 1)
    engine = ParallelPoolEngine(account_manager=mgr, client_factory=lambda m: None, sync_ui=False)
    chunks = [("KF_TURN_01_abc123", [KeyframeItem("T1", "p")], tmp_path / "o")]
    assert asyncio.run(engine._run_kf_chunks_parallel(chunks, [], [], None, False)) == []
    assert engine._kf_skipped_phases == ["KF_TURN"]
    assert engine._kf_batch_errors[0]["kf_ids"] == ["T1"] and engine._kf_batch_errors[0]["not_dispatched"]


def test_video_gate_refusal_is_a_halt_and_leftover_batches_are_reported(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 1)
    sent = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False, lease_guard=None):
            sent.append(batch_id)
            raise _halted_exc()

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False,
                                qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}})
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=12)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=3, simulate=False)
    assert res["status"] == "HALTED" and res["halted"]["reason"] == "OWNER_PAUSE"
    assert len(sent) == 1
    assert any("not sent" in str(e) for e in res["batch_errors"]), res["batch_errors"]


def test_halted_line_prints_the_records_own_reason():
    pause = send_halt.halted_line({"reason": "OWNER_PAUSE", "detail": "pause until merge", "signal": "MUSE_HALT_FILE"})
    assert "OWNER_PAUSE" in pause and "pause until merge" in pause and "CAPTCHA" not in pause
    block = send_halt.halted_line({"reason": "BLOCKED", "account_id": "a1", "batch_id": "b1"})
    assert "CAPTCHA" in block and "a1" in block


# ---- C. unique batch ids per run; no loose card match -----------------------------------------------------------------
def test_keyframe_batch_ids_are_unique_per_run_and_never_reuse_a_dir(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 1)
    seen = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False, lease_guard=None):
            seen.append((batch_id, Path(output_dir)))
            return await HeadlessMuseClient(self.account_manager).generate_keyframes_batch(
                account_id=account_id, keyframes=keyframes, batch_id=batch_id, output_dir=output_dir, simulate=True)

    proj = _kf_project(tmp_path, n_chars=4)
    ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False).run_keyframes(
        project_dir=proj, max_accounts=1, simulate=False)
    for png in (proj / "assets" / "anchors").glob("*.png"):
        png.unlink()  # run 2 must send the anchors again
    ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False).run_keyframes(
        project_dir=proj, max_accounts=1, simulate=False, release_unconfirmed=True)
    ids = [b for b, _ in seen]
    assert len(ids) == 2 and ids[0] != ids[1], ids
    assert all(re.fullmatch(r"KF_ANCHOR_\d{2}_[0-9a-f]{6}", b) for b in ids), ids
    assert seen[0][1] != seen[1][1]


def test_never_write_into_an_output_dir_holding_another_runs_files(tmp_path: Path):
    from muse_studio.core.parallel_pool_engine import _fresh_batch_dir

    used = tmp_path / "_batches" / "KF_ANCHOR_01"
    used.mkdir(parents=True)
    (used / "KF_ANCHOR_01_kf_result.zip").write_bytes(b"old run")
    bid, out = _fresh_batch_dir("KF_ANCHOR_01", used)
    assert bid != "KF_ANCHOR_01" and out != used and bid.startswith("KF_ANCHOR_01_") and out.name == bid
    empty = tmp_path / "_batches" / "KF_ANCHOR_02"
    assert _fresh_batch_dir("KF_ANCHOR_02", empty) == ("KF_ANCHOR_02", empty)


def test_legacy_kf_batch_dirs_are_still_adopted_next_to_unique_ids(tmp_path: Path):
    root = tmp_path / "_batches"
    for name in ("KF_ANCHOR_01", "KF_ANCHOR_01_ab12cd"):
        b = root / name
        b.mkdir(parents=True)
        (b / f"{name}_kf_manifest.json").write_text(
            json.dumps({"keyframes": [{"kf_id": "CHAR_01_ANCHOR"}]}), encoding="utf-8")
    ledger: list = []
    adopted = adopt_legacy_kf_batches([root], ledger)
    assert {e["batch_id"] for e in adopted} == {"KF_ANCHOR_01", "KF_ANCHOR_01_ab12cd"}


def test_attachment_card_needs_a_real_attachment_element():
    """A plain span/div holding the name (the user's own message, relay text) is never the result card."""
    name = "KF_ANCHOR_01_ab12cd_kf_result.zip"

    async def find(page):
        return await HeadlessMuseClient._find_attachment_card(page, name)

    plain = f'<div class="chat"><div class="msg"><span>{name}</span></div><p>{name}</p></div>'
    assert asyncio.run(_with_page(plain, find)) is None

    card = f'<div class="chat"><span>{name}</span><span role="button" class="group/card">{name}</span></div>'

    async def find_card(page):
        el = await HeadlessMuseClient._find_attachment_card(page, name)
        return None if el is None else await el.get_attribute("role")

    assert asyncio.run(_with_page(card, find_card)) == "button"


# =====================================================================================================================
# Codex review of r15: failover exhaustion, env pointing at production, non-file halt_pending entry
# =====================================================================================================================
def test_keyframe_failover_exhaustion_is_reported_not_dropped(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 3)  # one active + two standby: the chunk fails on all three (attempts 0, 1, 2)
    calls = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240,
                                           simulate=False, lease_guard=None):
            calls.append((account_id, batch_id))
            raise hmc.QuotaExceededException("out of usage before Enter")

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False)
    proj = _kf_project(tmp_path, n_chars=4)
    res = engine.run_keyframes(project_dir=proj, max_accounts=1, simulate=False)
    assert len(calls) == 3 and len({a for a, _ in calls}) == 3, calls
    assert res["status"] != "COMPLETED" and res["missing_keyframes"]
    exhausted = [e for e in res["batch_errors"] if e.get("reason") == "failover exhausted"]
    assert len(exhausted) == 1, res["batch_errors"]
    e = exhausted[0]
    assert e["submitted"] is False and e["not_dispatched"] is True and e["account_id"] == calls[-1][0]
    assert e["batch_id"] == calls[-1][1] and "out of usage" in e["error"]
    assert set(e["kf_ids"]) == set(res["missing_keyframes"])
    assert "KF_ANCHOR" in res["skipped_phases"]


def test_video_failover_exhaustion_is_reported_not_dropped(tmp_path: Path):
    mgr, _ = _make_accounts(tmp_path, 3)
    calls = []

    class Client:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480,
                                        simulate=False, lease_guard=None):
            calls.append((account_id, batch_id))
            raise hmc.QuotaExceededException("out of usage before Enter")

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=Client, sync_ui=False,
                                qc_evaluator=lambda *a, **k: {"verdict": "PASS", "defects": [], "metrics": {}})
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    res = engine.run_videos(project_dir=proj, max_accounts=1, max_rounds=1, simulate=False)
    assert len(calls) == 3, calls
    assert res["status"] == "INCOMPLETE"
    assert any("failover exhausted" in str(e) and calls[-1][1] in str(e) and calls[-1][0] in str(e)
               for e in res["batch_errors"]), res["batch_errors"]
    assert {f["reason"] for f in res["failed_shots"]} == {"NOT_DISPATCHED"}


def test_pytest_guard_refuses_env_pointing_at_the_real_halt_file(monkeypatch):
    real = Path(send_halt.__file__).resolve().parent.parent / "data" / "muse_halt.json"
    monkeypatch.setenv("MUSE_HALT_FILE", str(real))
    with pytest.raises(send_halt.ProductionHaltPathInTest):
        send_halt.halt_path()
    with pytest.raises(send_halt.ProductionHaltPathInTest):
        send_halt.send_stop()  # raised before any read of the real file


def test_pytest_guard_refuses_env_pointing_at_the_real_afp_dir(monkeypatch):
    real = Path.home() / ".afp"
    for value in (real, real / "halt_pending"):
        monkeypatch.setenv("AFP_STATE_DIR", str(value))
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.afp_state_dir()
        with pytest.raises(send_halt.ProductionHaltPathInTest):
            send_halt.pending_dir()


def test_non_file_halt_pending_entry_refuses(tmp_path: Path):
    pdir = send_halt.pending_dir()
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "incident.json").mkdir()  # a directory where a marker file belongs
    stop = send_halt.send_stop()
    assert stop is not None and stop["reason"] == "UNREADABLE" and stop["signal"] == "halt_pending"
    assert stop["marker"] == "incident.json"
    (pdir / "incident.json").rmdir()
    assert send_halt.send_stop() is None  # an empty pending dir does not stop sending
