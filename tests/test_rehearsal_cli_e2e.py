"""Upgrade step 4B: a rehearsal runs through the real `afp-film` CLI (subprocesses), with injected faults.

Every test owns its state: a rehearsal copy of film03's skeleton (the package tests/test_production_rehearsal.py uses),
its own AFP_STATE_DIR, an AFP_HALT_FILE inside the copy, its own composer-lock directory (LOCALAPPDATA) and a dead
AFP_FLOW_CDP (127.0.0.1:1), so nothing here can reach a Flow browser, the machine halt or the machine lease pool.
`afp-film generate` on a rehearsal package always uses rehearsal.mock_runner; `AFP_REHEARSAL_FAULT` picks the failure."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from film_pipeline.agentic.lease_pool import UNCERTAIN, AccountLeasePool
from film_pipeline.production import generate as G
from film_pipeline.production import rehearsal as R
from film_pipeline.production import takes as T
from film_pipeline.production.leases import REHEARSAL_ACCOUNT, REHEARSAL_DB
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
GIDS = ("SC01_g1", "SC07_g1")   # two scenes, each the first shot of its scene (no hand-off from a previous take)
DEAD_CDP = "http://127.0.0.1:1"
HELD = ("ACTIVE", UNCERTAIN)
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="needs ffmpeg")
pytestmark = needs_ffmpeg


def _entry_point() -> list[str]:
    exe = Path(sys.executable).parent / ("afp-film.exe" if os.name == "nt" else "afp-film")
    return [str(exe)] if exe.is_file() else [sys.executable, "-m", "film_pipeline"]


def _env(base: Path, root: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in {"AFP_FLOW_ACCOUNT", "AFP_FLOW_PROJECT", "AFP_REHEARSAL_FAULT", "AFP_LEASE_COOLDOWN_S"}}
    env.update({"PYTHONIOENCODING": "utf-8", "AFP_STATE_DIR": str(base / "state"),
                "AFP_HALT_FILE": str(root / "takes" / "production_halt.json"),
                "LOCALAPPDATA": str(base / "localappdata"), "AFP_FLOW_CDP": DEAD_CDP, **extra})
    return env


def body(done) -> dict:
    text = done.stdout
    return json.JSONDecoder().raw_decode(text[text.index("{"):])[0]


class Rehearsal:
    """One isolated rehearsal copy plus the means to drive it through the CLI."""

    def __init__(self, base: Path, root: Path):
        self.base, self.root = base, root
        self.header = json.loads((root / "film.json").read_text(encoding="utf-8"))
        self.film_id = self.header["film_id"]
        self.db = root / "takes" / REHEARSAL_DB
        self.halt_file = root / "takes" / "production_halt.json"

    def env(self, **extra: str) -> dict[str, str]:
        return _env(self.base, self.root, **extra)

    def cli(self, *args: str, fault: str = "", timeout: int = 600, **extra: str) -> subprocess.CompletedProcess:
        env = self.env(**({"AFP_REHEARSAL_FAULT": fault} if fault else {}), **extra)
        return subprocess.run([*_entry_point(), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, timeout=timeout, check=False)

    def popen(self, *args: str, fault: str = "", **extra: str) -> subprocess.Popen:
        env = self.env(**({"AFP_REHEARSAL_FAULT": fault} if fault else {}), **extra)
        return subprocess.Popen([*_entry_point(), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", env=env)

    def generate(self, gid: str, fault: str = "", *, auto_resend: bool = False, **extra: str):
        args = ["generate", "--film", str(self.root), "--gid", gid, "--start-token", "tok:REHEARSAL", "--no-critic"]
        return self.cli(*args, *([] if auto_resend else ["--no-auto-resend"]), fault=fault, **extra)

    # ---- what is on disk ---------------------------------------------------------------------------------------
    def takes(self) -> list:
        return list(T.load_log(self.root, self.film_id).takes)

    def receipt(self, take_id: str) -> dict:
        return json.loads((self.root / "takes" / "intents" / f"{take_id}.intent.json").read_text(encoding="utf-8"))

    def sent_receipts(self) -> list[str]:
        return sorted(p.name.split(".")[0] for p in (self.root / "takes" / "intents").glob("*.intent.json")
                      if json.loads(p.read_text(encoding="utf-8")).get("sent"))

    def clip(self, take_id: str) -> Path:
        return self.root / "media" / "takes" / f"{take_id}.mp4"

    def pool(self) -> dict:
        done = self.cli("lease", "status", "--db", str(self.db))
        assert done.returncode == 0, done.stderr
        return body(done)

    def lease_states(self) -> dict[str, str]:
        return {row["lease_key"].split(":", 1)[1].split("@")[0]: row["state"] for row in self.pool()["leases"]}

    def account(self) -> dict:
        return next(a for a in self.pool()["accounts"] if a["account_id"] == REHEARSAL_ACCOUNT)

    def refused(self, done) -> list[str]:
        assert done.returncode != 0, done.stdout
        return [r["code"] for r in body(done)["refused"]]

    def reconcile_in_process(self, take_id: str, monkeypatch, runner):
        """The existing reconcile with an injected scan (the CLI one needs a live Flow tab): same code, same checks."""
        from film_pipeline.production.recovery import reconcile
        monkeypatch.setenv("AFP_FLOW_CDP", DEAD_CDP)
        monkeypatch.setenv("LOCALAPPDATA", str(self.base / "localappdata"))
        return reconcile(load_package(self.root), take_id, runner=runner)


def _bound_runner(clip_bytes: bytes | None = None):
    """What a successful Flow scan returns: the job finished, its clip is downloaded and bound to the prompt."""
    def run(pkg, take_id, prompt, out):
        if clip_bytes is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(clip_bytes)
        return {"result": "BOUND", "download": "SAVED", "media_id": "media-rehearsal", "sha256": T.sha256_file(out),
                "prompt_sha256": T.sha256_text(prompt)}
    return run


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    """A planned rehearsal package with approved placeholder stills for GIDS, built once through the CLI."""
    base = tmp_path_factory.mktemp("rehearsal_template")
    root = base / "film"
    root.mkdir()
    for name in FILES:
        shutil.copy(FILM03 / name, root / name)
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header["rehearsal"] = True
    (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    rh = Rehearsal(base, root)
    steps = [("plan", "--film", str(root), "--out", str(root / "media" / "plan"), "--approve-storyboard", R.BOT)]
    for gid in GIDS:
        frame = root / "media" / "plan" / "storyboard" / f"{gid}.png"
        steps.append(("stills", "--film", str(root), "--register", gid, "--image", str(frame), "--source", "REHEARSAL placeholder"))
        steps.append(("stills", "--film", str(root), "--approve", gid, "--by", R.BOT))
    for args in steps:
        done = rh.cli(*args)
        if args[0] == "plan":   # film03's plan exits 1 while SC03_g1 is preflight-BLOCKED; the two shots used here must pass
            assert all(body(done)["generations"][g]["verdict"] == "PASS" for g in GIDS), done.stdout[-600:]
            continue
        assert done.returncode == 0, (args, done.stdout[-400:], done.stderr[-400:])
    return base


@pytest.fixture
def rh(template, tmp_path):
    """A fresh copy of the template with its own state; the copy lives at tmp_path/film (a rehearsal needs no media)."""
    root = tmp_path / "film"
    shutil.copytree(template / "film", root)
    return Rehearsal(tmp_path, root)


# ---- the guard and the fault switch ------------------------------------------------------------------------------

def test_the_fault_switch_is_honoured_only_inside_a_rehearsal_package(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    (plain / "media" / "takes").mkdir(parents=True)
    (plain / "film.json").write_text(json.dumps({"film_id": "x"}), encoding="utf-8")
    marked = tmp_path / "marked"
    (marked / "media" / "takes").mkdir(parents=True)
    (marked / "film.json").write_text(json.dumps({"film_id": "x", "rehearsal": True}), encoding="utf-8")
    monkeypatch.setenv(R.FAULT_ENV, "crash_after_submit")
    assert R._fault(plain / "media" / "takes" / "a_t1.mp4") == ""
    assert R._fault(marked / "media" / "takes" / "a_t1.mp4") == "crash_after_submit"
    monkeypatch.setenv(R.FAULT_ENV, "slow:2.5")
    assert R._fault(marked / "media" / "takes" / "a_t1.mp4") == "slow:2.5"
    monkeypatch.setenv(R.FAULT_ENV, "explode")
    assert R._fault(plain / "media" / "takes" / "a_t1.mp4") == ""
    with pytest.raises(ValueError, match="explode"):
        R._fault(marked / "media" / "takes" / "a_t1.mp4")


def test_generate_on_a_package_without_the_flag_does_not_use_the_mock(rh, tmp_path):
    header = json.loads((rh.root / "film.json").read_text(encoding="utf-8"))
    header.pop("rehearsal")
    (rh.root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    no_go = tmp_path / "backlog.md"
    no_go.write_text("OWNER_GO_LIVE: NO\n", encoding="utf-8")   # a real package is refused before any sender is reached
    done = rh.cli("generate", "--film", str(rh.root), "--gid", GIDS[0], "--start-token", "tok:x", "--no-critic",
                  "--backlog", str(no_go), fault="crash_after_submit")
    assert done.returncode == 1 and "OWNER_GO_LIVE_NO" in rh.refused(done)
    assert not rh.sent_receipts() and not rh.takes()


# ---- (a) happy path ----------------------------------------------------------------------------------------------

def test_happy_path_two_scenes_generate_review_cut_lock_deliver_through_the_cli(rh):
    film = str(rh.root)
    dry = rh.cli("generate", "--film", film, "--gid", GIDS[0], "--dry-run", "--no-critic", "--start-token", "tok:REHEARSAL")
    assert dry.returncode == 0 and body(dry)["ready_to_send"], dry.stdout[-600:]
    for gid in GIDS:
        done = rh.generate(gid)
        assert done.returncode == 0, (done.stdout[-600:], done.stderr[-600:])
        out = body(done)
        assert out["manifest_result"] == "PASSED" and out["take"]["take_id"] == f"{gid}_t1" and out["take"]["credits"] == 0.0
        sheet = rh.root / "media" / "review" / f"{gid}_t1.qc.json"
        sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.write_text(json.dumps(R._review_sheet(rh.root, rh.film_id, f"{gid}_t1", gid)), encoding="utf-8")
        ingested = rh.cli("review", "--film", film, "--ingest", str(sheet))
        assert ingested.returncode == 0 and body(ingested)["status"] == "ACCEPTED", ingested.stdout[-600:]
    assert [t.take_id for t in rh.takes()] == [f"{g}_t1" for g in GIDS]
    assert all(rh.clip(f"{g}_t1").is_file() for g in GIDS)
    assert set(rh.lease_states().values()) == {"RELEASED"}   # both sends gave the account back
    assert (rh.root / "takes" / "send_log.jsonl").read_text(encoding="utf-8").count("\n") == 2
    # the edit list, then the rest of the chain (the same verbs rehearse() runs)
    title = [{"text": rh.header["title"].upper(), "size": 96}, {"text": "Generated with AI", "size": 28}]
    # three events (24 s of body): the body label is checked on five sampled frames of the noisy mock footage, and with a
    # 16 s body one of them lands on a frame where the label is not detected (see the report)
    order = [GIDS[0], GIDS[1], GIDS[0]]
    (rh.root / "05_edit.json").write_text(json.dumps({"events": [{"event_id": f"E{n}", "kind": "TAKE", "take_id": f"{g}_t1"}
                                                                 for n, g in enumerate(order, 1)], "title": title}), encoding="utf-8")
    gen = rh.root / "generators.json"
    gen.write_text(json.dumps([{"role": "video+audio", "name": "REHEARSAL mock", "model": "ffmpeg still+tone",
                                "settings": R.STAMP}]), encoding="utf-8")
    cut_dir = rh.root / "media" / "cut"
    report = str(cut_dir / "titled_cut.cut.json")
    chain = [
        ("cut", "--film", film, "--render", "--out", str(cut_dir / "cut.mp4")),
        ("lock", "--film", film, "--lock", "--by", R.BOT, "--reason", R.STAMP),
        ("grade", "--film", film, "--render", "--out", str(cut_dir / "graded.mp4")),
        ("titles", "--film", film, "--generators-file", str(gen), "--render", "--color", "--out", str(cut_dir / "titled_cut.mp4")),
        ("mix", "--film", film, "--cut", str(cut_dir / "titled_cut.mp4"), "--out", str(cut_dir / "mixed.mp4")),
        ("mastercheck", "--film", film, "--cut-report", report),
        ("versions", "--film", film, "--no-portrait", "--cut-report", report, "--generators-file", str(gen)),
        ("deliver", "--film", film, "--no-portrait", "--cut-report", report, "--generators-file", str(gen)),
    ]
    for args in chain:
        done = rh.cli(*args)
        assert done.returncode == 0, (args[0], done.stdout[-800:], done.stderr[-400:])
    from film_pipeline.production.deliver import current_archive
    manifest = json.loads((current_archive(rh.root) / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["files"] and R.STAMP in (current_archive(rh.root) / "MANIFEST.json").read_text(encoding="utf-8")
    accept = rh.cli("deliver", "--film", film, "--accept", "Owner")
    assert accept.returncode != 0   # a rehearsal is never releasable


# ---- (b) crash right after the SUBMITTING receipt ----------------------------------------------------------------

def test_crash_after_submit_keeps_custody_until_reconcile_and_settle(rh, monkeypatch):
    gid, other = GIDS
    died = rh.generate(gid, "crash_after_submit")
    assert died.returncode == R.CRASH_EXIT, (died.stdout[-400:], died.stderr[-400:])
    receipt = rh.receipt(f"{gid}_t1")
    assert receipt["sent"] and receipt["result"] == "PENDING" and receipt["dispatch_phase"] == "SUBMITTING"
    assert not rh.clip(f"{gid}_t1").exists() and not rh.takes()
    # custody: the dead process could not clean up, so its lease is still held (it was never marked uncertain)
    assert rh.lease_states()[f"{gid}_t1"] in HELD and receipt["lease_key"].startswith(f"{rh.film_id}:{gid}_t1@")
    pool = AccountLeasePool(rh.db, min_reserve_credits=0.0, cooldown_s=0.0, honor_halt=False)
    lease, why = pool.acquire_or_reason("elsewhere", cost_credits=0.0, film_id="other_film", holder="someone-else")
    assert lease is None and "busy" in why   # no other caller can take that (only) account
    # the same gid again, and another gid: refused on the pending receipt, nothing sent
    assert rh.refused(rh.generate(gid)) == ["SEND_PENDING"]
    assert rh.refused(rh.generate(other)) == ["SEND_PENDING"]
    assert rh.sent_receipts() == [f"{gid}_t1"]
    # settle is refused while the receipt is unresolved
    early = rh.cli("lease", "settle", "--film", str(rh.root), "--take", f"{gid}_t1")
    assert early.returncode == 1 and "unresolved" in body(early)["error"]
    # the existing reconcile command needs a live Flow tab to scan: against a dead endpoint it cannot resolve this receipt
    cli_reconcile = rh.cli("reconcile", "--film", str(rh.root), "--take-id", f"{gid}_t1", timeout=300)
    assert cli_reconcile.returncode != 0 and not rh.takes()
    # the same reconcile with an injected scan that found the finished job resolves it, then settle gives the account back
    resolved = rh.reconcile_in_process(f"{gid}_t1", monkeypatch, _bound_runner(b"clip found by the reconcile scan"))
    assert resolved["resolved"] and resolved["take"]["take_id"] == f"{gid}_t1"
    settled = rh.cli("lease", "settle", "--film", str(rh.root), "--take", f"{gid}_t1")
    assert settled.returncode == 0 and body(settled)["lease"]["state"] == "RELEASED" and body(settled)["credits_spent"] == 0.0
    assert set(rh.lease_states().values()) == {"RELEASED"}
    again = rh.generate(other)   # sending works again
    assert again.returncode == 0 and body(again)["take"]["take_id"] == f"{other}_t1"


# ---- (c) crash after the clip is on disk, before it is registered ------------------------------------------------

def test_crash_after_download_leaves_an_unregistered_clip_until_reconcile(rh, monkeypatch):
    gid, other = GIDS
    died = rh.generate(gid, "crash_after_download")
    assert died.returncode == R.CRASH_EXIT, (died.stdout[-400:], died.stderr[-400:])
    clip = rh.clip(f"{gid}_t1")
    assert clip.is_file() and clip.stat().st_size > 1000
    assert rh.takes() == []   # evidence on disk, but not a take
    receipt = rh.receipt(f"{gid}_t1")
    assert receipt["result"] == "PENDING" and rh.lease_states()[f"{gid}_t1"] in HELD
    assert rh.refused(rh.generate(gid)) == ["SEND_PENDING"] and rh.refused(rh.generate(other)) == ["SEND_PENDING"]
    assert not rh.cli("lease", "settle", "--film", str(rh.root), "--take", f"{gid}_t1").returncode == 0
    assert rh.cli("reconcile", "--film", str(rh.root), "--take-id", f"{gid}_t1", timeout=300).returncode != 0
    assert rh.takes() == []
    sha = hashlib.sha256(clip.read_bytes()).hexdigest()
    resolved = rh.reconcile_in_process(f"{gid}_t1", monkeypatch, _bound_runner())   # the scan binds the clip already on disk
    assert resolved["resolved"] and resolved["take"]["output_sha256"] == sha
    assert [t.take_id for t in rh.takes()] == [f"{gid}_t1"]
    assert rh.cli("lease", "settle", "--film", str(rh.root), "--take", f"{gid}_t1").returncode == 0
    assert rh.generate(other).returncode == 0


# ---- (d) crash before the submit ---------------------------------------------------------------------------------

def test_crash_before_submit_releases_the_lease_for_nothing(rh):
    gid = GIDS[0]
    died = rh.generate(gid, "crash_before_submit")
    assert died.returncode != 0 and "crash_before_submit" in died.stderr
    receipt = rh.receipt(f"{gid}_t1")
    assert receipt["result"] == "PENDING" and receipt["dispatch_phase"] == "PREPARING"   # the Enter was never reached
    assert not rh.clip(f"{gid}_t1").exists() and not rh.takes()
    snap = rh.pool()
    assert [(l["state"], l["settled_credits"]) for l in snap["leases"]] == [("RELEASED", 0.0)]   # given back, nothing charged
    assert next(a for a in snap["accounts"] if a["account_id"] == REHEARSAL_ACCOUNT)["status"] == "ACTIVE"
    # the PENDING receipt still blocks a resend until the (offline) reconcile qualifies it as never dispatched
    assert rh.refused(rh.generate(gid)) == ["SEND_PENDING"]
    rec = rh.cli("reconcile", "--film", str(rh.root), "--take-id", f"{gid}_t1")
    assert rec.returncode == 0 and body(rec)["result"] == "PRE_SUBMIT_ERROR CONTROLLER_NOT_DISPATCHED"
    ok = rh.generate(gid)
    assert ok.returncode == 0 and body(ok)["take"]["take_id"] == f"{gid}_t2"


# ---- provider failure (no account problem) -----------------------------------------------------------------------

def test_provider_failed_gives_the_account_back_and_registers_nothing(rh):
    gid = GIDS[0]
    done = rh.generate(gid, "provider_failed")
    assert done.returncode == 1 and body(done)["manifest_result"] == "FLOW_FAILED" and not rh.takes()
    assert set(rh.lease_states().values()) == {"RELEASED"} and not rh.halt_file.exists()
    assert rh.generate(gid).returncode == 0


# ---- (e) account warning: halt, quarantine, no resend, the way back ----------------------------------------------

def test_account_warning_halts_quarantines_and_needs_an_explicit_way_back(rh, monkeypatch):
    gid, other = GIDS
    done = rh.generate(gid, "account_warning", auto_resend=True)   # even with auto-resend allowed, no second send
    assert done.returncode == 1 and body(done)["manifest_result"] == "FLOW_ACCOUNT_WARNING"
    assert "auto_resend" not in body(done) and rh.sent_receipts() == [f"{gid}_t1"] and not rh.takes()
    halt = rh.cli("halt", "status")
    assert body(halt)["halted"] and body(halt)["halt_file"] == str(rh.halt_file)   # the rehearsal's own halt, not the machine's
    assert not (Path(rh.env()["AFP_STATE_DIR"]) / "production_halt.json").exists()
    account = rh.account()
    assert account["status"] == "COOLDOWN_QUARANTINE" and "FLOW_ACCOUNT_WARNING" in account["quarantined_reason"]
    assert rh.lease_states()[f"{gid}_t1"] == UNCERTAIN
    # the next send is refused and nothing is sent again
    nxt = rh.refused(rh.generate(other))
    assert set(nxt) & {"PRODUCTION_HALT", "NO_ACCOUNT_LEASE", "SEND_PENDING"}, nxt
    assert rh.sent_receipts() == [f"{gid}_t1"]
    # the way back: unquarantine is refused while the halt is set, and for bad input
    args = ("lease", "unquarantine", "--db", str(rh.db), "--account", REHEARSAL_ACCOUNT, "--by", "agent:tester", "--reason", "checked")
    early = rh.cli(*args)
    assert early.returncode == 1 and "halted" in body(early)["error"] and rh.account()["status"] == "COOLDOWN_QUARANTINE"
    cleared = rh.cli("halt", "clear", "--by", "agent:tester", "--reason", "rehearsal fault")
    assert cleared.returncode == 0 and not rh.halt_file.exists()
    bad = rh.cli("lease", "unquarantine", "--db", str(rh.db), "--account", REHEARSAL_ACCOUNT, "--by", "tester", "--reason", "checked")
    assert bad.returncode == 1 and "by" in body(bad)["error"] and rh.account()["status"] == "COOLDOWN_QUARANTINE"
    # the account is back, but the send that warned is still unresolved and holds its lease
    restored = rh.cli(*args)
    assert restored.returncode == 0 and rh.account()["status"] == "ACTIVE", restored.stdout[-400:]
    event = body(restored)["unquarantined"]
    assert event["by"] == "agent:tester" and event["prior_status"] == "COOLDOWN_QUARANTINE"
    again = rh.cli(*args)
    assert again.returncode == 1 and "not quarantined" in body(again)["error"]
    import sqlite3
    with sqlite3.connect(rh.db) as conn:   # logged
        rows = conn.execute("SELECT account_id, action, by, reason FROM account_history").fetchall()
    assert rows == [(REHEARSAL_ACCOUNT, "unquarantine", "agent:tester", "checked")]
    # unquarantine alone does not restore sending: the warned send is an unresolved AMBIGUOUS receipt and still holds its lease
    assert rh.refused(rh.generate(other)) == ["SEND_PENDING"] and rh.sent_receipts() == [f"{gid}_t1"]   # never auto-resent
    assert rh.lease_states()[f"{gid}_t1"] == UNCERTAIN
    early_settle = rh.cli("lease", "settle", "--film", str(rh.root), "--take", f"{gid}_t1")
    assert early_settle.returncode == 1 and "unresolved" in body(early_settle)["error"]
    # reconcile (a scan that finds the job finished) resolves it, settle gives the lease back, and sending works again
    resolved = rh.reconcile_in_process(f"{gid}_t1", monkeypatch, _bound_runner(b"clip of the send that warned"))
    assert resolved["resolved"]
    assert rh.cli("lease", "settle", "--film", str(rh.root), "--take", f"{gid}_t1").returncode == 0
    assert set(rh.lease_states().values()) == {"RELEASED"}
    assert rh.generate(other).returncode == 0


# ---- (f) two generates for the same gid at once ------------------------------------------------------------------

@pytest.mark.parametrize("second_cdp,codes", [(None, {"FILM_BUSY"}), ("http://127.0.0.1:2", {"SEND_PENDING", "NO_ACCOUNT_LEASE"})],
                         ids=["same_flow_profile", "another_flow_profile"])
def test_concurrent_duplicates_send_exactly_once(rh, second_cdp, codes):
    gid = GIDS[0]
    first = rh.popen("generate", "--film", str(rh.root), "--gid", gid, "--start-token", "tok:REHEARSAL", "--no-critic",
                     "--no-auto-resend", fault="slow:6")
    try:
        deadline = time.time() + 120
        receipt = rh.root / "takes" / "intents" / f"{gid}_t1.intent.json"
        while time.time() < deadline:   # wait until the first is inside its send
            if receipt.is_file() and json.loads(receipt.read_text(encoding="utf-8")).get("dispatch_phase") == "SUBMITTING":
                break
            assert first.poll() is None, first.communicate()
            time.sleep(0.2)
        else:
            pytest.fail("the first generate never reached SUBMITTING")
        extra = {"AFP_FLOW_CDP": second_cdp} if second_cdp else {}
        second = rh.generate(gid, **extra)
        out1, err1 = first.communicate(timeout=300)
    finally:
        if first.poll() is None:
            first.kill()
    assert first.returncode == 0, (out1[-400:], err1[-400:])
    assert second.returncode != 0
    out2 = body(second)
    code = "FILM_BUSY" if str(out2.get("error", "")).startswith("FILM_BUSY") else (rh.refused(second) or [""])[0]
    assert code in codes, second.stdout[-500:]
    assert [t.take_id for t in rh.takes()] == [f"{gid}_t1"]     # exactly one take
    assert rh.sent_receipts() == [f"{gid}_t1"]                   # exactly one send
    pool = rh.pool()
    assert [(l["state"], l["settled_credits"]) for l in pool["leases"]] == [("RELEASED", 0.0)]   # no lease left, no charge
    lines = (rh.root / "takes" / "send_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


# ---- (g) the film's credit cap ----------------------------------------------------------------------------------

def test_a_rehearsal_is_exempt_from_the_credit_cap(rh):
    """FINDING: generate skips the budget check for a rehearsal (expected credits are 0), so the cap cannot be exhausted
    by a rehearsal: even a cap of 1 credit lets every send through. The live cap path is covered in-process below."""
    header = json.loads((rh.root / "film.json").read_text(encoding="utf-8"))
    header["budget"] = {"credits_estimate": 1, "cap_factor": 1.0}
    (rh.root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    for gid in GIDS:
        done = rh.generate(gid)
        assert done.returncode == 0, done.stdout[-900:]
        assert body(done)["payload"]["expected_credits"] == 0.0


def test_cap_exhaustion_refuses_the_second_send_and_leaves_no_lease(tmp_path, flow_lease_account):
    """The budget blocker on a live-style send (injected runner, isolated machine pool): the second send is refused
    before it asks for a lease, so none is left held and the account is leasable at once."""
    from test_production_generate import FakeRunner, backlog, film, still
    pkg = film(tmp_path, 8)   # cap 12: one 8-credit send fits, two do not
    kw = dict(dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc", backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"),
              auto_resend=0)
    first = G.generate(pkg, GIDS[0], runner=FakeRunner("FLOW_FAILED"), **kw)   # a failed send is still charged
    assert first["sent"] and first["payload"]["take_id"] == "SC01_g1_t1"
    runner = FakeRunner()
    second = G.generate(pkg, GIDS[0], runner=runner, **kw)
    assert not second["sent"] and [r["code"] for r in second["refused"]] == ["BUDGET_EXCEEDED"] and not runner.calls
    snap = flow_lease_account.snapshot()
    assert [(l["state"], l["settled_credits"]) for l in snap["leases"]] == [("RELEASED", 8.0)]   # only the first send's lease
    assert flow_lease_account.availability(cost_credits=8.0)[0]
