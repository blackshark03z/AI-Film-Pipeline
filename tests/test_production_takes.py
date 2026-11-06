import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from film_pipeline.drama import autoqc
from film_pipeline.drama.autoqc import AutoQCReport
from film_pipeline.drama.scene_bible import RuleIssue
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.qc_model import MIN_LEVEL, TAKE_GROUPS

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
KNOWN = {"SC01_g1", "SC01_g2"}


def film(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    return load_package(root)


def clip(tmp_path, name, payload=b"clip-bytes"):
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def register(pkg, tmp_path, gid="SC01_g1", payload=b"clip-bytes", **kw):
    return T.register_take(pkg.root, pkg.header.film_id, gid, clip(tmp_path, f"{gid}_{len(payload)}.mp4", payload),
                           prompt_text="the sent prompt", route="start_frame+Khung hinh", model="veo-omni-flash",
                           credits=12, known_generations=KNOWN | {"SC02_g1"}, **kw)


def passing_review(sheet):
    qc = sheet["qc"]
    for c in qc["checks"]:
        c.update(result="PASS", level=MIN_LEVEL[c["group"]], evidence="reviews/x.png", reviewer="human:owner")
    return sheet


def test_register_numbers_takes_per_generation_and_dedupes_by_bytes(tmp_path):
    pkg = film(tmp_path)
    first, created = register(pkg, tmp_path)
    assert created and first.take_id == "SC01_g1_t1" and first.status == "GENERATED"
    again, created = register(pkg, tmp_path)
    assert not created and again.take_id == "SC01_g1_t1"
    second, created = register(pkg, tmp_path, payload=b"another take")
    assert created and second.take_id == "SC01_g1_t2" and second.output_sha256 != first.output_sha256
    with pytest.raises(ValueError, match="already take SC01_g1_t1 of SC01_g1"):
        register(pkg, tmp_path, gid="SC01_g2")  # the same file cannot be a take of two generations
    other, _ = register(pkg, tmp_path, gid="SC01_g2", payload=b"g2 take")
    assert other.take_id == "SC01_g2_t1"
    assert [t.take_id for t in T.load_log(pkg.root, pkg.header.film_id).takes] == [
        "SC01_g1_t1", "SC01_g1_t2", "SC01_g2_t1"]


def test_register_records_provenance_hashes(tmp_path):
    pkg = film(tmp_path)
    still = clip(tmp_path, "start.png", b"png")
    entry, _ = register(pkg, tmp_path, start_frame=still)
    assert entry.prompt_sha256 == T.sha256_text("the sent prompt") and entry.start_frame_sha256 == T.sha256_file(still)
    assert entry.route == "start_frame+Khung hinh" and entry.model == "veo-omni-flash" and entry.credits == 12


def test_register_refuses_bad_input(tmp_path):
    pkg = film(tmp_path)
    good = clip(tmp_path, "a.mp4")
    base = dict(route="r", model="m", credits=12, known_generations=KNOWN)
    with pytest.raises(ValueError, match="unknown generation"):
        T.register_take(pkg.root, "f", "SC99_g1", good, prompt_text="p", **base)
    with pytest.raises(ValueError, match="missing or empty"):
        T.register_take(pkg.root, "f", "SC01_g1", clip(tmp_path, "e.mp4", b""), prompt_text="p", **base)
    with pytest.raises(ValueError, match="prompt text"):
        T.register_take(pkg.root, "f", "SC01_g1", good, prompt_text="  ", **base)
    with pytest.raises(ValueError, match="start frame"):
        T.register_take(pkg.root, "f", "SC01_g1", good, prompt_text="p", start_frame=tmp_path / "no.png", **base)
    assert not (pkg.root / "takes" / "index.json").exists()  # nothing half-written


def test_dailies_template_carries_the_shot_questions_and_a_blank_qc(tmp_path):
    pkg = film(tmp_path)
    entry, _ = register(pkg, tmp_path)
    sheet = T.dailies_template(pkg, entry, T.script_dialogue(pkg))
    decl = next(g for g in pkg.typed["shots"].generations if g.generation_id == "SC01_g1")
    groups = [q["group"] for q in sheet["questions"]]
    assert groups.count("action") >= len(decl.choreography.phases) and "camera" in groups and "spatial" in groups
    assert any(f"Line {n}" in q["question"] for n in decl.dialogue for q in sheet["questions"])
    assert [c["group"] for c in sheet["qc"]["checks"]] == list(TAKE_GROUPS)
    assert all(c["result"] == "UNASSESSED" for c in sheet["qc"]["checks"])
    assert sheet["qc"]["output_sha256"] == entry.output_sha256
    assert sheet["shot"]["start_state"] == decl.start_state and sheet["shot"]["phases"]


def test_write_dailies_only_for_new_takes_and_never_overwrites(tmp_path):
    pkg = film(tmp_path)
    register(pkg, tmp_path)
    first = T.write_dailies(pkg, pkg.root)
    assert [w["take_id"] for w in first] == ["SC01_g1_t1"]
    sheet = pkg.root / "takes" / "dailies" / "SC01_g1_t1.review.json"
    assert sheet.is_file()
    sheet.write_text('{"filled": true}', encoding="utf-8")
    assert T.write_dailies(pkg, pkg.root) == [] and sheet.read_text(encoding="utf-8") == '{"filled": true}'
    register(pkg, tmp_path, payload=b"second")
    assert [w["take_id"] for w in T.write_dailies(pkg, pkg.root)] == ["SC01_g1_t2"]


def test_ingest_accepts_a_fully_human_reviewed_take(tmp_path):
    pkg = film(tmp_path)
    entry, _ = register(pkg, tmp_path)
    sheet = passing_review(T.dailies_template(pkg, entry))
    result = T.ingest_review(pkg.root, pkg.header.film_id, sheet)
    assert result["status"] == "ACCEPTED" and Path(result["review"]).is_file()
    assert T.load_log(pkg.root, pkg.header.film_id).get(entry.take_id).status == "ACCEPTED"


def test_ingest_partial_and_rejecting_reviews_set_the_status(tmp_path):
    pkg = film(tmp_path)
    entry, _ = register(pkg, tmp_path)
    sheet = T.dailies_template(pkg, entry)
    assert T.ingest_review(pkg.root, pkg.header.film_id, sheet)["status"] == "INCOMPLETE"
    sheet = passing_review(sheet)
    motion = next(c for c in sheet["qc"]["checks"] if c["group"] == "motion")
    motion.update(result="FAIL", severity="P0")
    result = T.ingest_review(pkg.root, pkg.header.film_id, sheet)
    assert result["status"] == "REJECTED" and "motion(136)" in result["reasons"][0]


def test_ingest_refuses_a_review_for_other_bytes_or_a_cheating_record(tmp_path):
    pkg = film(tmp_path)
    entry, _ = register(pkg, tmp_path)
    sheet = passing_review(T.dailies_template(pkg, entry))
    stale = json.loads(json.dumps(sheet))
    stale["qc"]["output_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="not bound to this take's bytes"):
        T.ingest_review(pkg.root, pkg.header.film_id, stale)
    cheat = json.loads(json.dumps(sheet))
    cheat["qc"]["checks"][0]["reviewer"] = "auto:vision"  # an auto tool passing the narrative group
    with pytest.raises(ValidationError, match="auto tool may only WARN"):
        T.ingest_review(pkg.root, pkg.header.film_id, cheat)
    wrong = json.loads(json.dumps(sheet))
    wrong["qc"]["take_id"] = "SC01_g1_t9"
    with pytest.raises(KeyError):
        T.ingest_review(pkg.root, pkg.header.film_id, wrong)
    assert T.load_log(pkg.root, pkg.header.film_id).get(entry.take_id).status == "GENERATED"


def test_auto_evidence_skips_cleanly_without_models(tmp_path, monkeypatch):
    pkg = film(tmp_path)
    entry, _ = register(pkg, tmp_path)
    monkeypatch.setattr(autoqc, "models_available", lambda: False)
    checks, note = T.auto_evidence(pkg, entry, tmp_path / "x.mp4")
    assert checks == [] and "skipped" in note


def test_auto_evidence_turns_findings_into_warnings_only(tmp_path, monkeypatch):
    pkg = film(tmp_path)
    entry, _ = register(pkg, tmp_path)
    monkeypatch.setattr(autoqc, "models_available", lambda: True)
    report = AutoQCReport(clip="c", issues=[RuleIssue(check="SHOT_SCALE_MISMATCH", severity="WARN", detail="planned MS"),
                                            RuleIssue(check="SET_DRIFT", severity="WARN", detail="set changed")])
    monkeypatch.setattr(autoqc, "run_autoqc", lambda *a, **k: report)
    checks, note = T.auto_evidence(pkg, entry, tmp_path / "x.mp4")
    assert [(c.group, c.result, c.reviewer) for c in checks] == [("camera", "WARN", "auto:autoqc"),
                                                                 ("spatial", "WARN", "auto:autoqc")]
    assert "2 warning" in note


def test_dailies_embed_autoqc_note_when_clips_given(tmp_path, monkeypatch):
    pkg = film(tmp_path)
    entry, _ = register(pkg, tmp_path)
    monkeypatch.setattr(autoqc, "models_available", lambda: False)
    T.write_dailies(pkg, pkg.root, clips_dir=tmp_path)
    sheet = json.loads((pkg.root / "takes" / "dailies" / "SC01_g1_t1.review.json").read_text(encoding="utf-8"))
    assert "skipped" in sheet["auto_evidence"]["note"] and sheet["auto_evidence"]["warnings"] == []


def test_cli_register_review_ingest_roundtrip(tmp_path):
    pkg = film(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("the sent prompt", encoding="utf-8")
    mp4 = clip(tmp_path, "t.mp4")

    def run(*args):
        done = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8")
        return done.returncode, json.loads(done.stdout)

    film_arg = ("--film", str(pkg.root))
    code, body = run("takes", *film_arg, "--register", "SC01_g1", "--clip", str(mp4), "--prompt", str(prompt),
                     "--model", "veo-omni-flash", "--credits", "12")
    assert code == 0 and body["created"] and body["take"]["take_id"] == "SC01_g1_t1"
    code, body = run("takes", *film_arg, "--register", "SC01_g1", "--clip", str(mp4))
    assert code == 2 and "--prompt" in body["error"]
    code, body = run("review", *film_arg)
    assert code == 0 and [w["take_id"] for w in body["written"]] == ["SC01_g1_t1"] and body["pending"] == ["SC01_g1_t1"]
    sheet_path = pkg.root / "takes" / "dailies" / "SC01_g1_t1.review.json"
    filled = tmp_path / "filled.json"
    filled.write_text(json.dumps(passing_review(json.loads(sheet_path.read_text(encoding="utf-8")))), encoding="utf-8")
    code, body = run("review", *film_arg, "--ingest", str(filled))
    assert code == 0 and body["status"] == "ACCEPTED"
    code, body = run("takes", *film_arg)
    assert body["takes"][0]["status"] == "ACCEPTED"
    bad = json.loads(filled.read_text(encoding="utf-8"))
    bad["qc"]["output_sha256"] = "1" * 64
    filled.write_text(json.dumps(bad), encoding="utf-8")
    code, body = run("review", *film_arg, "--ingest", str(filled))
    assert code == 2 and "not bound" in body["error"]
