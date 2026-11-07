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
    # film04 now carries the Owner's real start still for SC01_g1 (and its local media is not copied): start with none
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre.pop("stills", None)
    # gate mechanics only: the end-state sentence (P13-03) puts three not-yet-restaged shots over the word limit
    pre["preflight"]["end_state_in_prompt"] = False
    (root / "03_preprod.json").write_text(json.dumps(pre, ensure_ascii=False, indent=2), encoding="utf-8")
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


def set_header(root, **changes):
    path = root / "film.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key, value in changes.items():
        if isinstance(value, dict):
            data[key] = {**data.get(key, {}), **value}
        else:
            data[key] = value
    path.write_text(json.dumps(data), encoding="utf-8")


def test_gate3_a_planning_header_field_makes_the_plan_stale_but_bookkeeping_does_not(tmp_path):
    """P11-04: language / fps / aspect / clip length feed the plan; budget, disclosure, rehearsal and gates do not."""
    root = clone(tmp_path)
    planned(root, storyboard=False)
    before = GC.plan_inputs_sha(root)
    assert GC.HEADER_KEY in before
    set_header(root, budget={"credits_estimate": 99.0}, disclosure={"ai_label": "title_card"}, rehearsal=True)
    assert GC.plan_inputs_sha(root) == before
    assert not any("stale" in i for i in gate(root, "3").issues)
    for field, value in (("fps", 30), ("generation_s", 6), ("language", "vi"), ("aspect", "9:16")):
        raw = (root / "film.json").read_text(encoding="utf-8")
        set_header(root, **{field: value})
        res = gate(root, "3")
        assert res.status == "BLOCK" and "stale" in res.issues[0] and GC.HEADER_KEY in res.issues[0], field
        (root / "film.json").write_text(raw, encoding="utf-8")
    assert not any("stale" in i for i in gate(root, "3").issues)


def test_gate3_spelling_out_a_default_is_not_a_planning_change(tmp_path):
    root = clone(tmp_path)
    before = GC.plan_inputs_sha(root)[GC.HEADER_KEY]
    set_header(root, fps=load_package(root).header.fps, generation_s=load_package(root).header.generation_s)
    assert GC.plan_inputs_sha(root)[GC.HEADER_KEY] == before


def test_gate3_approval_does_not_survive_a_changed_or_deleted_storyboard_frame(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    root = clone(tmp_path)
    planned(root, approve_storyboard="Reviewer")
    assert gate(root, "3").status == "PASS"
    frames = sorted((GC.plan_dir(root) / "storyboard").rglob("*.png"))
    assert len(frames) == 12
    original = frames[0].read_bytes()
    Image.new("RGB", (640, 360), (250, 0, 0)).save(frames[0])  # swapped after the Owner approved it
    res = gate(root, "3")
    assert res.status == "BLOCK" and any("changed after it was approved" in i for i in res.issues)
    frames[0].write_bytes(original)
    assert gate(root, "3").status == "PASS"
    frames[1].unlink()
    res = gate(root, "3")
    assert res.status == "BLOCK" and any("approved storyboard frame is missing" in i for i in res.issues)


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
        clip = root / "media" / "takes" / f"{decl.generation_id}.mp4"  # where the accepted bytes are expected
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(f"clip {n}".encode())
        entry, _ = T.register_take(root, pkg.header.film_id, decl.generation_id, clip, prompt_text="sent", route="r", model="m",
                                   credits=1, shot_version=decl.version)
        entries.append(entry)
    return entries


def test_gate4_no_take_blocks_unreviewed_is_pending_all_accepted_passes(tmp_path):
    root = clone(tmp_path)
    pkg = load_package(root)
    res = gate(pkg, "4")
    assert res.status == "BLOCK" and res.issues[0] == f"SC01_g1: no take of shot version {pkg.typed['shots'].generations[0].version}"
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
    assert f"no take of shot version {pkg.typed['shots'].generations[0].version} (older: SC01_g1_t1)" in gate(root, "4").issues[0]


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
    (media / entry.output_file).write_bytes(b"other bytes")
    assert any("clip on disk changed" in i for i in gate(root, "4").issues)


def accepted_one(tmp_path, prompt="sent"):
    root = clone(tmp_path)
    pkg = load_package(root)
    clip = root / "media" / "takes" / "SC01_g1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"clip")
    decl = pkg.typed["shots"].generations[0]
    entry, _ = T.register_take(root, pkg.header.film_id, decl.generation_id, clip, prompt_text=prompt, route="r", model="m",
                               credits=1, shot_version=decl.version)
    T.ingest_review(root, pkg.header.film_id, sheet_pass(T.dailies_template(pkg, entry)))
    return root, pkg, entry, clip


def only_one_generation_left(res):
    """The film has 12 generations; the other 11 have no take. Keep what is about SC01_g1."""
    return [i for i in res.issues if i.startswith("SC01_g1")]


def test_gate4_a_missing_accepted_clip_is_a_block_not_a_pass(tmp_path):
    root, pkg, entry, clip = accepted_one(tmp_path)
    assert not any("SC01_g1_t1" in i for i in gate(root, "4").issues)
    clip.unlink()
    assert any("SC01_g1_t1: the accepted clip is missing" in i for i in gate(root, "4").issues)


def test_gate4_a_changed_prompt_makes_an_accepted_take_stale_without_a_version_bump(tmp_path):
    root, pkg, entry, clip = accepted_one(tmp_path)
    prompt = GC.plan_dir(root) / "prompts" / "SC01_g1.txt"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("sent" + chr(10), encoding="utf-8")  # the plan emits exactly what the take was made from
    assert not any("SC01_g1_t1" in i for i in gate(root, "4").issues)
    prompt.write_text("sent, but now with a different action" + chr(10), encoding="utf-8")
    assert any("SC01_g1_t1: the prompt changed after this take was generated" in i for i in gate(root, "4").issues)


def test_gate4_review_after_dailies_and_ingest_points_at_the_stored_review(tmp_path):
    root = clone(tmp_path)
    pkg = load_package(root)
    clip = root / "media" / "takes" / "SC01_g1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"clip")
    decl = pkg.typed["shots"].generations[0]
    T.register_take(root, pkg.header.film_id, decl.generation_id, clip, prompt_text="sent", route="r", model="m", credits=1,
                    shot_version=decl.version)
    T.write_dailies(pkg, root)
    log = T.load_log(root, pkg.header.film_id)
    assert log.takes[0].review_file == "dailies/SC01_g1_t1.review.json"
    sheet_path = T.takes_dir(root) / log.takes[0].review_file
    filled = sheet_pass(json.loads(sheet_path.read_text(encoding="utf-8")))
    T.ingest_review(root, pkg.header.film_id, filled)
    log = T.load_log(root, pkg.header.film_id)
    assert log.takes[0].review_file == "reviews/SC01_g1_t1.qc.json" and log.takes[0].status == "ACCEPTED"
    assert not any("SC01_g1_t1" in i for i in gate(root, "4").issues)  # used to raise on the wrapped sheet
    # a log written before this fix still points at the wrapped sheet: it is unwrapped, not rejected
    sheet_path.write_text(json.dumps({**filled, "qc": {**filled["qc"], "output_sha256": log.takes[0].output_sha256}}), encoding="utf-8")
    log.takes[0].review_file = "dailies/SC01_g1_t1.review.json"
    T.save_log(root, log)
    assert not any("SC01_g1_t1" in i for i in gate(root, "4").issues)


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


def test_gate6_acceptance_is_bound_to_the_disclosure_policy_the_archive_was_built_under(tmp_path):
    """P11-05: an archive built under one ai_label setting cannot be accepted after the setting changed."""
    root = clone(tmp_path)
    archive = root / "delivery"
    archive.mkdir()
    (archive / DL.MANIFEST).write_text(json.dumps({"film_id": "film04_last_ticket", "title": "T", "created": "x", "release_ready": True}), encoding="utf-8")

    def policy_issues(**item):
        sha = DL.sha256_file(archive / DL.MANIFEST)
        (root / "07_delivery.json").write_text(json.dumps({"delivery": {"manifest_sha256": sha, **item}}), encoding="utf-8")
        return [i for i in GC.master_issues(load_package(root)) if "disclosure policy" in i or "ai_label" in i]

    assert load_package(root).header.disclosure.ai_label == "always"
    assert not policy_issues(ai_label="always")
    changed = policy_issues(ai_label="title_card")
    assert len(changed) == 1 and "title_card" in changed[0] and "always" in changed[0] and "deliver again" in changed[0]
    legacy = policy_issues()  # a delivery recorded before the policy was kept
    assert len(legacy) == 1 and "records no disclosure policy" in legacy[0]


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
