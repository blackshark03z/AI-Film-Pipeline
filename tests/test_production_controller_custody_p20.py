import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from film_pipeline.production import recovery as R, takes as T, generate as G
from film_pipeline.production.runtime import run_async, writer
from film_pipeline.production.money import credit_ledger
from test_production_generate import film, still, backlog
from test_production_recovery_p20 import bound

# a live generate() send leases a Flow account from the isolated machine pool (tests/conftest.py)
pytestmark = pytest.mark.usefixtures("flow_lease_account")


def test_async_bridge_uses_controller_process_even_inside_an_existing_loop():
    async def work():
        return os.getpid()
    async def caller():
        return run_async(work)
    assert asyncio.run(caller()) == os.getpid()


@pytest.mark.parametrize("phase", ["PREPARING", "SUBMITTING"])
def test_hard_controller_death_stops_native_python_actions_and_preserves_journal(tmp_path, phase):
    pkg = film(tmp_path, 100)
    still(tmp_path)
    backlog(tmp_path, "OWNER_GO_LIVE: YES")
    helper = tmp_path / "controller.py"
    helper.write_text('''import asyncio,json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from film_pipeline.production import generate as G, preflight as P
from film_pipeline.production.package import load_package
from film_pipeline.providers.flow_ui_adapter import flow_tool
root=Path(sys.argv[2]); phase=sys.argv[3]
P.check=lambda *a,**k: {"ok":True}
async def fake(args,before_submit=None):
    if phase=="SUBMITTING":
        before_submit({"project":"owned-project"})
        (root/"FIRST_SUBMIT.txt").write_text("mock only")
    (root/"controller-ready.json").write_text(json.dumps({"pid":os.getpid()}))
    await asyncio.sleep(2)
    (root/"LATE_ACTION.txt").write_text("must never happen after controller death")
    if phase=="PREPARING": before_submit({"project":"owned-project"})
    return {"result":"PASSED"}
flow_tool("flow_send").run=fake
G.generate(load_package(root/"film"),"SC01_g1",dry_run=False,stills_dir=root/"stills",
           backlog=root/"backlog.md",start_token="tok:owned")
''', encoding="utf-8")
    with (tmp_path / "controller.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, str(helper), str(Path(__file__).resolve().parents[1] / "src"),
                                 str(tmp_path), phase], stdout=log, stderr=log)
        ready = tmp_path / "controller-ready.json"
        deadline = time.monotonic() + 15
        while not ready.is_file() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.is_file(), (tmp_path / "controller.log").read_text(encoding="utf-8")
        actual_pid = json.loads(ready.read_text())["pid"]
        assert actual_pid != os.getpid()
        os.kill(actual_pid, signal.SIGTERM)
        proc.wait(timeout=10)
    with writer(pkg.root, flow=True):
        pass
    time.sleep(2.2)
    assert not (tmp_path / "LATE_ACTION.txt").exists()
    assert (tmp_path / "FIRST_SUBMIT.txt").exists() == (phase == "SUBMITTING")
    intent = pkg.root / "takes/intents/SC01_g1_t1.intent.json"
    original = intent.read_bytes()
    assert json.loads(original)["dispatch_phase"] == phase
    result = R.reconcile(pkg, "SC01_g1_t1", runner=bound if phase == "SUBMITTING" else lambda *a: pytest.fail("never submitted"))
    assert result["resolved"] and intent.read_bytes() == original
    assert len(T.load_log(pkg.root, pkg.header.film_id).takes) == (1 if phase == "SUBMITTING" else 0)
    again = R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("no repeat effect"))
    assert again["resolved"]
    receipts = G._sent_receipts(pkg.root, pkg.header.film_id, {"SC01_g1": 8})
    assert credit_ledger(T.load_log(pkg.root, pkg.header.film_id), receipts)["spent"] == (8 if phase == "SUBMITTING" else 0)
