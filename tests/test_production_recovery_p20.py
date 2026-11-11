import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import generate as G, takes as T
from film_pipeline.production import recovery as R
from film_pipeline.production.runtime import WriterBusy, writer
from film_pipeline.production.money import credit_ledger
from test_production_generate import film, still, backlog


def interrupted(tmp_path):
    pkg = film(tmp_path, estimate=100)
    def crash(argv, out):
        raise RuntimeError("interrupted after submit")
    with pytest.raises(RuntimeError, match="interrupted"):
        G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path),
                   backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=crash)
    path = pkg.root / "takes/intents/SC01_g1_t1.intent.json"
    return pkg, path, path.read_bytes()


def bound(pkg, rid, prompt, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"downloaded-clip")
    return {"result": "BOUND", "download": "SAVED", "media_id": "native-media-123",
            "sha256": T.sha256_file(out), "prompt_sha256": T.sha256_text(prompt)}


def test_interrupted_send_keeps_exact_prompt_and_reconcile_survives_replan(tmp_path):
    pkg, receipt, original = interrupted(tmp_path)
    snapshot = receipt.with_name("SC01_g1_t1.prompt.txt")
    prompt = snapshot.read_text(encoding="utf-8").strip()
    assert T.sha256_text(prompt) == json.loads(original)["prompt_sha256"]
    (pkg.root / "media/plan/prompts/SC01_g1.txt").write_text("changed after send", encoding="utf-8")
    calls = []
    def runner(*args):
        calls.append(args[2])
        return bound(*args)
    result = R.reconcile(pkg, "SC01_g1_t1", runner=runner)
    assert result["resolved"] and result["take"]["status"] == "GENERATED"
    assert receipt.read_bytes() == original and calls == [prompt]
    assert T.load_log(pkg.root, pkg.header.film_id).takes[0].credits == 8
    sent = G._sent_receipts(pkg.root, pkg.header.film_id, {"SC01_g1": 8})
    assert sent["SC01_g1_t1"]["result"] == "PASSED"
    again = R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("must not contact provider again"))
    assert again["resolved"] and len(T.load_log(pkg.root, pkg.header.film_id).takes) == 1


def test_ambiguous_reconcile_keeps_reservation_and_original_receipt(tmp_path):
    pkg, path, original = interrupted(tmp_path)
    result = R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: {"result": "AMBIGUOUS"})
    assert not result["resolved"] and path.read_bytes() == original
    sent = G._sent_receipts(pkg.root, pkg.header.film_id, {"SC01_g1": 8})
    assert sent["SC01_g1_t1"]["result"] == "PENDING"
    assert credit_ledger(T.load_log(pkg.root, pkg.header.film_id), sent)["spent"] == 8


@pytest.mark.parametrize("outcome", ["UNBOUND", "AMBIGUOUS", "TIMEOUT", "MANIFEST_HASH_MISMATCH", "PASSED"])
def test_reported_but_unresolved_send_also_blocks_the_next_generation(tmp_path, outcome):
    pkg, path, original = interrupted(tmp_path)
    receipt = json.loads(original)
    receipt["result"] = outcome
    path.write_text(json.dumps(receipt), encoding="utf-8")
    pending = R.pending_receipts(pkg)
    assert pending and pending[0]["take_id"] == "SC01_g1_t1"
    result = G.generate(pkg, "SC01_g2", dry_run=False, stills_dir=still(tmp_path),
                        backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"),
                        runner=lambda *a: pytest.fail("uncertain previous send forbids a new one"))
    assert "SEND_PENDING" in {r["code"] for r in result["refused"]}


def test_download_hash_mismatch_never_registers_a_take(tmp_path):
    pkg, _, _ = interrupted(tmp_path)
    def corrupt(*args):
        return {**bound(*args), "sha256": "f" * 64}
    with pytest.raises(ValueError, match="hash"):
        R.reconcile(pkg, "SC01_g1_t1", runner=corrupt)
    assert not T.load_log(pkg.root, pkg.header.film_id).takes


def test_reconcile_rejects_changed_legacy_prompt_without_provider_call(tmp_path):
    pkg, path, _ = interrupted(tmp_path)
    path.with_name("SC01_g1_t1.prompt.txt").unlink()
    (pkg.root / "media/plan/prompts/SC01_g1.txt").write_text("new plan", encoding="utf-8")
    with pytest.raises(ValueError, match="prompt"):
        R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("no provider call"))


def test_two_processes_cannot_write_the_same_film(tmp_path):
    root = tmp_path / "film"
    code = "from pathlib import Path; from film_pipeline.production.runtime import writer,WriterBusy\ntry:\n with writer(Path(__import__('sys').argv[1])): print('UNSAFE')\nexcept WriterBusy: print('BUSY')"
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    with writer(root):
        child = subprocess.run([sys.executable, "-c", code, str(root)], capture_output=True,
                               text=True, env=env, timeout=15)
    assert child.returncode == 0 and child.stdout.strip() == "BUSY", child.stderr
    with writer(root):
        with writer(root):
            pass


def test_process_death_releases_flow_lock_but_keeps_pending_budget(tmp_path):
    pkg, receipt, original = interrupted(tmp_path)
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    code = ("from pathlib import Path; import os,sys; from film_pipeline.production.runtime import writer\n"
            "with writer(Path(sys.argv[1]), flow=True):\n print('LOCKED',flush=True)\n os._exit(17)")
    child = subprocess.run([sys.executable, "-c", code, str(pkg.root)], capture_output=True,
                           text=True, env=env, timeout=15)
    assert child.returncode == 17 and child.stdout.strip() == "LOCKED"
    with writer(pkg.root, flow=True):
        pass
    assert receipt.read_bytes() == original
    sent = G._sent_receipts(pkg.root, pkg.header.film_id, {"SC01_g1": 8})
    assert credit_ledger(T.load_log(pkg.root, pkg.header.film_id), sent)["spent"] == 8
    blocked = G.generate(pkg, "SC01_g2", dry_run=False, stills_dir=still(tmp_path),
                         backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"),
                         runner=lambda *a: pytest.fail("a pending send forbids another submission"))
    assert blocked["refused"]


def test_flow_composer_is_exclusive_across_different_films(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    code = ("from pathlib import Path; import sys; from film_pipeline.production.runtime import writer,WriterBusy\n"
            "try:\n with writer(Path(sys.argv[1]),flow=True): print('UNSAFE')\nexcept WriterBusy: print('BUSY')")
    with writer(tmp_path / "filmA", flow=True):
        child = subprocess.run([sys.executable, "-c", code, str(tmp_path / "filmB")], capture_output=True,
                               text=True, env=env, timeout=15)
    assert child.returncode == 0 and child.stdout.strip() == "BUSY", child.stderr


def test_reconcile_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="take"):
        R.reconcile(film(tmp_path), "../private", runner=bound)


def test_crash_after_download_reuses_verified_bytes_before_register(tmp_path, monkeypatch):
    pkg, _, _ = interrupted(tmp_path)
    register = T.register_take
    def crash(*a, **kw):
        raise RuntimeError("before registration")
    monkeypatch.setattr(T, "register_take", crash)
    with pytest.raises(RuntimeError, match="before registration"):
        R.reconcile(pkg, "SC01_g1_t1", runner=bound)
    monkeypatch.setattr(T, "register_take", register)
    result = R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("download must be reusable"))
    assert result["resolved"] and len(T.load_log(pkg.root, pkg.header.film_id).takes) == 1


def test_truncated_legacy_resolution_can_be_reconciled_without_a_new_send(tmp_path):
    pkg, _, original = interrupted(tmp_path)
    partial = pkg.root / "media/takes/SC01_g1_t1.reconcile.json"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text('{"result":', encoding="utf-8")
    result = R.reconcile(pkg, "SC01_g1_t1", runner=bound)
    assert result["resolved"]
    assert (pkg.root / "takes/intents/SC01_g1_t1.intent.json").read_bytes() == original


@pytest.mark.parametrize("initial", ["PENDING", "UNBOUND"])
@pytest.mark.parametrize("native_result,spent", [("PRE_SUBMIT_ERROR NO_FLOW_TAB", 0), ("FLOW_FAILED", 8)])
def test_proven_failure_clears_pending_without_a_new_send(tmp_path, initial, native_result, spent):
    pkg, path, original = interrupted(tmp_path)
    receipt = json.loads(original)
    receipt["result"] = initial
    path.write_text(json.dumps(receipt), encoding="utf-8")
    original = path.read_bytes()
    native = pkg.root / "media/takes/SC01_g1_t1.take.json"
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text(json.dumps({"prompt_sha256": receipt["prompt_sha256"], "result": native_result}), encoding="utf-8")
    result = R.reconcile(pkg, "SC01_g1_t1", runner=lambda *a: pytest.fail("no new provider operation"))
    assert result["resolved"] and path.read_bytes() == original
    sent = G._sent_receipts(pkg.root, pkg.header.film_id, {"SC01_g1": 8})
    assert credit_ledger(T.load_log(pkg.root, pkg.header.film_id), sent)["spent"] == spent
    assert R.pending_receipts(pkg) == []
