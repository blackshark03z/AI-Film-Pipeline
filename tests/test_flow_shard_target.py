"""Shard parallelism step 2: every process names its Flow profile (AFP_FLOW_CDP) and project (AFP_FLOW_PROJECT);
the send journal records them and reconcile never scans a different profile or project."""
import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

from film_pipeline.production import generate as G, recovery as R, takes as T
from film_pipeline.production import runtime as RT
from test_production_generate import FakeRunner, backlog, film, still

# a live generate() send leases a Flow account from the isolated machine pool (tests/conftest.py)
pytestmark = pytest.mark.usefixtures("flow_lease_account")

TOOLS = Path(__file__).resolve().parents[1] / "tools" / "drama_flow_ui"
sys.path.insert(0, str(TOOLS))
import flow_reconcile as fr  # noqa: E402
import flow_send as fs  # noqa: E402

GO = "OWNER_GO_LIVE: YES"
A, B = "http://127.0.0.1:9411", "http://127.0.0.1:9412"
PROJ_A, PROJ_B = "aaaaaaaa-1111-2222-3333-444444444444", "bbbbbbbb-1111-2222-3333-444444444444"
FLOW_URL = "https://flow.google.com/project/"


@pytest.fixture(autouse=True)
def private_locks(monkeypatch, tmp_path):
    monkeypatch.delenv("AFP_FLOW_CDP", raising=False)
    monkeypatch.delenv("AFP_FLOW_PROJECT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))   # a live shard may hold the real lock


class Page:
    def __init__(self, url):
        self.url = url


def send(pkg, tmp_path, runner, **kw):
    return G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, GO), runner=runner, **kw)


def receipt_of(pkg, take="SC01_g1_t1"):
    return json.loads((pkg.root / "takes/intents" / f"{take}.intent.json").read_text(encoding="utf-8"))


# ---- the sender / reconciler choose the target from the environment ------------------------------------------------
def test_sender_endpoint_defaults_to_9333_and_follows_the_environment(monkeypatch):
    assert fs.cdp_endpoint() == "http://127.0.0.1:9333"
    monkeypatch.setenv("AFP_FLOW_CDP", "localhost:9411")
    assert fs.cdp_endpoint() == A
    assert fr.fs.cdp_endpoint() == A


def test_pinned_project_picks_that_tab_only():
    tabs = [Page(FLOW_URL + PROJ_A), Page(FLOW_URL + PROJ_B)]
    assert fs.select_flow_page(tabs, PROJ_B) is tabs[1]
    assert fs.select_flow_page(tabs, "") is tabs[0]                    # unpinned = today's behaviour
    assert fs.select_flow_page(tabs[:1], PROJ_B) is None               # the other profile's project is never used
    assert fs.select_flow_page([Page("https://example.com")], "") is None


def test_project_selection_rejects_lookalikes_and_detail_tabs():
    wrong = [
        Page(f"https://flow.google.com.example.org/project/{PROJ_A}"),
        Page(f"https://example.org/?next={FLOW_URL}{PROJ_A}"),
        Page(FLOW_URL + PROJ_A + "-other"),
        Page(FLOW_URL + PROJ_A + "/edit/media"),
    ]
    exact = Page(FLOW_URL + PROJ_A + "/?view=grid")
    assert fs.select_flow_page(wrong, PROJ_A) is None
    assert fs.select_flow_page(wrong + [exact], PROJ_A) is exact
    assert fs.flow_project_id("https://labs.google/fx/tools/flow/project/" + PROJ_A) == PROJ_A


# ---- the send journal records the target ----------------------------------------------------------------------------
def test_receipt_and_send_log_record_endpoint_and_project(tmp_path, monkeypatch):
    monkeypatch.setenv("AFP_FLOW_CDP", A)
    monkeypatch.setenv("AFP_FLOW_PROJECT", PROJ_A)
    pkg = film(tmp_path, 100)
    send(pkg, tmp_path, FakeRunner("PASSED"))
    assert receipt_of(pkg)["cdp"] == A and receipt_of(pkg)["project"] == PROJ_A
    line = json.loads((pkg.root / "takes/send_log.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert line["cdp"] == A and line["project"] == PROJ_A


def test_unpinned_default_process_records_the_default_endpoint(tmp_path):
    pkg = film(tmp_path, 100)
    send(pkg, tmp_path, FakeRunner("PASSED"))
    assert receipt_of(pkg)["cdp"] == "http://127.0.0.1:9333" and not receipt_of(pkg).get("project")


# ---- reconcile is scoped to the profile and project of the send -------------------------------------------------------
def interrupted(tmp_path, monkeypatch, cdp=A, project=PROJ_A):
    monkeypatch.setenv("AFP_FLOW_CDP", cdp)
    if project:
        monkeypatch.setenv("AFP_FLOW_PROJECT", project)
    pkg = film(tmp_path, 100)

    def crash(argv, out, before_submit=None):
        before_submit({"project": ""})
        raise RuntimeError("interrupted after submit")
    crash.takes_before_submit = True
    with pytest.raises(RuntimeError, match="interrupted"):
        send(pkg, tmp_path, crash)
    return pkg


def bound(pkg, rid, prompt, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"downloaded-clip")
    return {"result": "BOUND", "download": "SAVED", "media_id": "native-media-123",
            "sha256": T.sha256_file(out), "prompt_sha256": T.sha256_text(prompt)}


def test_reconcile_refuses_a_different_profile_without_scanning(tmp_path, monkeypatch):
    pkg = interrupted(tmp_path, monkeypatch)
    monkeypatch.setenv("AFP_FLOW_CDP", B)
    with pytest.raises(ValueError, match="FLOW_TARGET_MISMATCH"):
        R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("must not scan another profile"))


def test_reconcile_refuses_a_different_project_without_scanning(tmp_path, monkeypatch):
    pkg = interrupted(tmp_path, monkeypatch)
    monkeypatch.setenv("AFP_FLOW_PROJECT", PROJ_B)
    with pytest.raises(ValueError, match="FLOW_TARGET_MISMATCH"):
        R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("must not scan another project"))


def test_reconcile_on_the_same_profile_and_project_proceeds(tmp_path, monkeypatch):
    pkg = interrupted(tmp_path, monkeypatch)
    result = R.reconcile(pkg, "SC01_g1_t1", runner=bound)
    assert result["resolved"] and result["take"]["status"] == "GENERATED"


def test_a_legacy_receipt_belongs_to_the_default_endpoint(tmp_path, monkeypatch):
    pkg = interrupted(tmp_path, monkeypatch, cdp="http://127.0.0.1:9333", project="")
    path = pkg.root / "takes/intents/SC01_g1_t1.intent.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("cdp")
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("AFP_FLOW_CDP", A)                              # a shard must not claim an old default send
    with pytest.raises(ValueError, match="FLOW_TARGET_MISMATCH"):
        R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("no scan"))
    monkeypatch.delenv("AFP_FLOW_CDP")
    assert R.reconcile(pkg, "SC01_g1_t1", runner=bound)["resolved"]


def test_target_problem_rules(monkeypatch):
    monkeypatch.setenv("AFP_FLOW_CDP", A)
    assert RT.flow_target_problem({"cdp": A, "project": PROJ_A}) is None      # process unpinned: project not enforced
    monkeypatch.setenv("AFP_FLOW_PROJECT", PROJ_A)
    assert RT.flow_target_problem({"cdp": A, "project": PROJ_A}) is None
    assert "project" in RT.flow_target_problem({"cdp": A, "project": PROJ_B})
    assert "project" in RT.flow_target_problem({"cdp": A, "project": PROJ_A + "-other"})
    assert "endpoint" in RT.flow_target_problem({"cdp": B, "project": PROJ_A})


# ---- the native scanner never touches a tab of another project ---------------------------------------------------------
def fake_patchright(monkeypatch, pages, connected):
    class Context:
        def __init__(self):
            self.pages = pages

    class Browser:
        contexts = [Context()]

    class Chromium:
        async def connect_over_cdp(self, endpoint, timeout=0):
            connected.append(endpoint)
            return Browser()

    class Pw:
        chromium = Chromium()

        async def stop(self):
            pass

    class Starter:
        async def start(self):
            return Pw()
    module = types.ModuleType("patchright.async_api")
    module.async_playwright = lambda: Starter()
    monkeypatch.setitem(sys.modules, "patchright", types.ModuleType("patchright"))
    monkeypatch.setitem(sys.modules, "patchright.async_api", module)


def scan_args(tmp_path, rid="SC01_g1_t1"):
    return fr.build_parser().parse_args(["--receipts", str(tmp_path / "intents"), "--takes-index", str(tmp_path / "takes/index.json"),
                                        "--ids", rid, "--out-dir", str(tmp_path / "out")])


def write_receipt(tmp_path, **extra):
    (tmp_path / "intents").mkdir(parents=True, exist_ok=True)
    prompt = "a prompt"
    (tmp_path / "intents/SC01_g1_t1.prompt.txt").write_text(prompt, encoding="utf-8")
    (tmp_path / "intents/SC01_g1_t1.intent.json").write_text(
        json.dumps({"generation_id": "SC01_g1", "prompt_sha256": fr._sha(prompt), **extra}), encoding="utf-8")


def test_native_scan_skips_a_receipt_of_another_profile_without_connecting(tmp_path, monkeypatch):
    connected = []
    fake_patchright(monkeypatch, [Page(FLOW_URL + PROJ_A)], connected)
    monkeypatch.setenv("AFP_FLOW_CDP", B)
    write_receipt(tmp_path, cdp=A, project=PROJ_A)
    results = asyncio.run(fr.run(scan_args(tmp_path)))
    assert results["SC01_g1_t1"]["result"] == "WRONG_PROFILE" and connected == []


def test_native_scan_with_no_tab_of_the_pinned_project_does_not_scan(tmp_path, monkeypatch):
    connected = []
    fake_patchright(monkeypatch, [Page(FLOW_URL + PROJ_B)], connected)
    monkeypatch.setenv("AFP_FLOW_CDP", A)
    monkeypatch.setenv("AFP_FLOW_PROJECT", PROJ_A)
    write_receipt(tmp_path, cdp=A, project=PROJ_A)
    results = asyncio.run(fr.run(scan_args(tmp_path)))
    assert connected == [A] and results["SC01_g1_t1"]["result"] == "NO_FLOW_TAB"


def test_native_scan_uses_receipt_project_when_unpinned(tmp_path, monkeypatch):
    connected = []
    fake_patchright(monkeypatch, [Page(FLOW_URL + PROJ_B)], connected)
    monkeypatch.setenv("AFP_FLOW_CDP", A)
    write_receipt(tmp_path, cdp=A, project=PROJ_A)
    results = asyncio.run(fr.run(scan_args(tmp_path)))
    assert connected == [A] and results["SC01_g1_t1"]["result"] == "NO_FLOW_TAB"
