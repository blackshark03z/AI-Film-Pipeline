"""P10-01: gates 3, 4 and 6 read evidence on disk and give a verdict - never NOT_RUN, never PASS unchecked."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from film_pipeline.production import deliver as DL
from film_pipeline.production import gate_checks as GC
from film_pipeline.production import takes as T
from film_pipeline.production.gates import evaluate_gate
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package
from film_pipeline.production.qc_model import MIN_LEVEL

ROOT = Path(__file__).resolve().parents[1]
FILM04 = ROOT / "films" / "film04_last_ticket"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json",
         "05_edit.json", "06_post.json", "07_delivery.json", "ledger.json")


def clone(tmp_path):
    root = tmp_path / "film04"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM04 / name, root / name)
    return root


def planned(root, **kw):
    plan_package(load_package(root), GC.plan_dir(root), **kw)
    return load_package(root)


def gate(root_or_pkg, gid):
    pkg = load_package(root_or_pkg) if isinstance(root_or_pkg, Path) else root_or_pkg
    return evaluate_gate(pkg, gid)


# ----------------------------------------------------------------------------- gate 3

def test_gate3_without_a_plan_blocks(tmp_path):
    res = gate(clone(tmp_path), "3")
    assert res.status == "BLOCK" and "run film.py plan" in res.issues[0]


def test_gate3_pending_storyboard_is_owner_pending_and_approval_passes(tmp_path):
    pytest.importorskip("PIL")
    root = clone(tmp_path)
    planned(root)
    res = gate(root, "3")
    assert res.status == "OWNER_PENDING" and "12 frame(s)" in res.issues[0]
    planned(root, approve_storyboard="Reviewer")
    assert gate(root, "3").status == "PASS"


def test_gate3_stale_plan_and_real_blocks(tmp_path):
    root = clone(tmp_path)
    planned(root, storyboard=False)
    res = gate(root, "3")
    assert res.status == "BLOCK" and any("no storyboard frame" in i for i in res.issues)  # not a pending, a defect
    shots = root / "04_shots.json"
    shots.write_text(shots.read_text(encoding="utf-8") + "\n", encoding="utf-8")  # any byte change makes the plan stale
    res = gate(root, "3")
    assert res.status == "BLOCK" and "stale" in res.issues[0] and "04_shots.json" in res.issues[0]
    path = GC.plan_dir(root) / "gate3.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["generations"]["SC01_g1"]["issues"].append({"check": "LOOK", "severity": "BLOCK", "detail": "lost the look"})
    path.write_text(json.dumps(record), encoding="utf-8")
    meta = GC.plan_dir(root) / GC.PLAN_META
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["planned_from"] = GC.plan_inputs_sha(root)
    meta.write_text(json.dumps(data), encoding="utf-8")
    assert "SC01_g1 LOOK: lost the look" in gate(root, "3").issues


def test_plan_sidecar_keeps_gate3_json_unchanged_in_shape(tmp_path):
    root = clone(tmp_path)
    planned(root, storyboard=False)
    base = GC.plan_dir(root)
    assert (base / GC.PLAN_META).is_file()
    assert set(json.loads((base / "gate3.json").read_text(encoding="utf-8"))) >= {"feasibility", "generations", "states"}


# ----------------------------------------------------------------------------- gate 4

def sheet_pass(sheet):
    for c in sheet["qc"]["checks"]:
        c.update(result="PASS", level=MIN_LEVEL[c["group"]], evidence="reviews/x.png", reviewer="human:owner")
    return sheet


def register_all(root, pkg, upto=None):
    entries = []
    for n, decl in enumerate(pkg.typed["shots"].generations[:upto]):
        clip = root / f"{decl.generation_id}.mp4"
        clip.write_bytes(f"clip {n}".encode())
        entry, _ = T.register_take(root, pkg.header.film_id, decl.generation_id, clip, prompt_text="sent", route="r", model="m",
                                   credits=1, shot_version=decl.version)
        entries.append(entry)
    return entries


def test_gate4_no_take_blocks_unreviewed_is_pending_all_accepted_passes(tmp_path):
    root = clone(tmp_path)
    pkg = load_package(root)
    res = gate(pkg, "4")
    assert res.status == "BLOCK" and res.issues[0] == "SC01_g1: no take of shot version 1"
    entries = register_all(root, pkg)
    res = gate(root, "4")
    assert res.status == "OWNER_PENDING" and "waits for a human review" in res.issues[0]
    for entry in entries[:-1]:
        T.ingest_review(root, pkg.header.film_id, sheet_pass(T.dailies_template(pkg, entry)))
    res = gate(root, "4")
    assert res.status == "OWNER_PENDING" and len(res.issues) == 1 and entries[-1].generation_id in res.issues[0]
    T.ingest_review(root, pkg.header.film_id, sheet_pass(T.dailies_template(pkg, entries[-1])))
    assert gate(root, "4").status == "PASS"


def test_gate4_rejected_take_blocks_and_an_old_shot_version_does_not_count(tmp_path):
    root = clone(tmp_path)
    pkg = load_package(root)
    entries = register_all(root, pkg, upto=1)
    sheet = sheet_pass(T.dailies_template(pkg, entries[0]))
    next(c for c in sheet["qc"]["checks"] if c["group"] == "motion").update(result="FAIL", severity="P0")
    sheet["qc"]["cause"] = "PROMPT"
    assert T.ingest_review(root, pkg.header.film_id, sheet)["status"] == "REJECTED"
    res = gate(root, "4")
    assert res.status == "BLOCK" and res.issues[0].startswith("SC01_g1: every take is rejected")
    log = T.load_log(root, pkg.header.film_id)
    log.takes[0].shot_version = 7
    log.takes[0].status = "ACCEPTED"
    T.save_log(root, log)
    assert "no take of shot version 1 (older: SC01_g1_t1)" in gate(root, "4").issues[0]


def test_gate4_accepted_without_a_review_or_with_changed_bytes_blocks(tmp_path):
    root = clone(tmp_path)
    pkg = load_package(root)
    entry = register_all(root, pkg, upto=1)[0]
    log = T.load_log(root, pkg.header.film_id)
    log.takes[0].status = "ACCEPTED"  # a hand edit of the log, no review behind it
    T.save_log(root, log)
    assert "ACCEPTED in the log without a stored review" in gate(root, "4").issues[0]
    log.takes[0].status = "GENERATED"
    T.save_log(root, log)
    T.ingest_review(root, pkg.header.film_id, sheet_pass(T.dailies_template(pkg, entry)))
    media = root / "media" / "takes"
    media.mkdir(parents=True)
    (media / entry.output_file).write_bytes(b"other bytes")
    assert any("clip on disk changed" in i for i in gate(root, "4").issues)


# ----------------------------------------------------------------------------- gate 6 + acceptance

def delivery_pkg(**item):
    return SimpleNamespace(stages={"delivery": {"delivery": {"manifest_sha256": "a" * 64, "release_ready": True, **item}}})


def test_gate6_clean_delivery_is_pending_until_the_owner_accepts_this_manifest():
    assert "has not accepted" in GC.master_pending(delivery_pkg())[0]
    stale = delivery_pkg(owner_acceptance={"by": "Owner", "manifest_sha256": "b" * 64})
    assert "has not accepted" in GC.master_pending(stale)[0]
    ok = delivery_pkg(owner_acceptance={"by": "Owner", "manifest_sha256": "a" * 64})
    assert GC.master_pending(ok) == []
    assert "release_ready is false" in GC.master_pending(delivery_pkg(release_ready=False))[0]


def test_gate6_blocks_without_evidence(tmp_path):
    root = clone(tmp_path)
    (root / "06_post.json").write_text('{"x": {"locked_against": ""}}', encoding="utf-8")
    (root / "07_delivery.json").write_text('{"delivery": {"manifest_sha256": "' + "a" * 64 + '"}}', encoding="utf-8")
    res = gate(root, "6")
    assert res.status == "BLOCK"
    assert any("master_qc.json" in i for i in res.issues) and any("delivery archive" in i for i in res.issues)


def test_accept_refuses_unless_everything_else_passes_and_never_writes(tmp_path):
    root = clone(tmp_path)
    before = (root / "07_delivery.json").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="cannot accept: gate 3"):
        DL.accept_delivery(load_package(root), "Owner")
    with pytest.raises(ValueError, match="name"):
        DL.accept_delivery(load_package(root), " ")
    assert (root / "07_delivery.json").read_text(encoding="utf-8") == before


def test_accept_records_the_current_manifest_when_all_gates_pass(tmp_path, monkeypatch):
    root = clone(tmp_path)
    (root / "07_delivery.json").write_text(json.dumps({"delivery": {"manifest_sha256": "a" * 64, "release_ready": True}}), encoding="utf-8")
    green = [SimpleNamespace(gate=g, name="n", status="PASS", issues=[]) for g in "123456"]
    monkeypatch.setattr("film_pipeline.production.gates.evaluate_gates", lambda pkg: green)
    monkeypatch.setattr(GC, "master_issues", lambda pkg: [])
    pkg = load_package(root)
    out = DL.accept_delivery(pkg, " Owner ")
    assert out == {"accepted_by": "Owner", "manifest_sha256": "a" * 64}
    item = json.loads((root / "07_delivery.json").read_text(encoding="utf-8"))["delivery"]
    assert item["owner_acceptance"]["by"] == "Owner" and item["owner_acceptance"]["manifest_sha256"] == "a" * 64
    assert GC.master_pending(load_package(root)) == []
    (root / "07_delivery.json").write_text(json.dumps({"delivery": {"manifest_sha256": "a" * 64, "release_ready": False}}), encoding="utf-8")
    with pytest.raises(ValueError, match="release_ready is false"):
        DL.accept_delivery(load_package(root), "Owner")


def test_cli_accept_is_refused_on_an_unfinished_film(tmp_path):
    import os
    import subprocess
    import sys
    root = clone(tmp_path)
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "film.py"), "deliver", "--film", str(root), "--accept", "Owner"],
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
    assert done.returncode == 1 and "cannot accept" in json.loads(done.stdout)["error"]
    assert "owner_acceptance" not in (root / "07_delivery.json").read_text(encoding="utf-8")
