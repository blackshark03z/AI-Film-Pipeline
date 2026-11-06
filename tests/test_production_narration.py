import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_e2e import fixture_direction, media, source_srt

from film_pipeline import e2e
from film_pipeline.production.gates import evaluate_gate, evaluate_gates
from film_pipeline.production.narration import build_package
from film_pipeline.production.package import PackageError, load_package

FILM = Path(__file__).resolve().parents[1] / "tools" / "film.py"


def run(*args):
    return subprocess.run([sys.executable, str(FILM), *args], capture_output=True, text=True, encoding="utf-8")


@pytest.fixture
def project(tmp_path):
    audio, srt = tmp_path / "source.mp3", tmp_path / "source.srt"
    media(audio)
    source_srt(srt)
    root = tmp_path / "e2e_project"
    e2e.prepare(audio, srt, 18, 55, root)
    return root


def complete_plan(root):
    path = root / "shots.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    for shot in plan["shots"]:
        shot.update(visual_intent="Visible story beat from the source text",
                    image_prompt="Police station, same adult characters",
                    video_prompt="Animate only the action described in source text")
        fixture_direction(shot)
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def set_rights(pkg_dir, value):
    story = json.loads((pkg_dir / "01_story.json").read_text(encoding="utf-8"))
    story["rights_status"] = value
    (pkg_dir / "01_story.json").write_text(json.dumps(story), encoding="utf-8")


def test_import_builds_a_valid_package(project, tmp_path):
    out = tmp_path / "films" / "n1"
    result = build_package(project, out, film_id="n1", title="Narration one")
    assert result["sentences"] == 3 and result["shots"] == 8
    pkg = load_package(out)
    assert pkg.header.profile == "narration" and pkg.issues == []
    assert set(pkg.typed) == {"story", "shots"}
    story = pkg.typed["story"]
    assert [s.cue_ids for s in story.sentences] == [[1], [2], [3]]
    assert story.source.audio_start_s == 18 and story.source.audio_end_s == 55
    # every sentence is carried by at least one shot and the project path is stored relative to the package
    assert {sid for s in pkg.typed["shots"].shots for sid in s.sentence_ids} == {"S01", "S02", "S03"}
    assert not Path(story.source.project).is_absolute() or Path(story.source.project) == project.resolve()


def test_gate1_needs_owner_for_rights_then_passes(project, tmp_path):
    out = tmp_path / "n2"
    build_package(project, out)
    res = evaluate_gate(load_package(out), "1")
    assert res.status == "OWNER_PENDING" and "rights_status=unknown" in res.issues[0]
    set_rights(out, "cleared")
    assert evaluate_gate(load_package(out), "1").status == "PASS"


def test_gate2_matches_e2e_plan_review(project, tmp_path):
    out = tmp_path / "n3"
    build_package(project, out)
    assert e2e.status(project)["plan_review_required"] is True
    blocked = evaluate_gate(load_package(out), "2")
    assert blocked.status == "BLOCK" and any("visual_intent" in i for i in blocked.issues)
    complete_plan(project)
    build_package(project, out, refresh=True)
    assert e2e.status(project)["plan_review_required"] is False
    res = evaluate_gate(load_package(out), "2")
    assert res.status == "PASS", res.issues


def test_source_change_blocks_gate1(project, tmp_path):
    out = tmp_path / "n4"
    build_package(project, out)
    set_rights(out, "cleared")
    (project / "source" / "audio.mp3").write_bytes(b"drift")
    res = evaluate_gate(load_package(out), "1")
    assert res.status == "BLOCK" and any("audio source" in i and "changed" in i for i in res.issues)


def test_edited_sentences_block_gate1(project, tmp_path):
    out = tmp_path / "n5"
    build_package(project, out)
    story = json.loads((out / "01_story.json").read_text(encoding="utf-8"))
    story["sentences"][0]["text"] = "She leaves."
    (out / "01_story.json").write_text(json.dumps(story), encoding="utf-8")
    res = evaluate_gate(load_package(out), "1")
    assert res.status == "BLOCK" and "sentences differ from the SRT (re-import with refresh)" in res.issues


def test_stale_shots_and_uncarried_sentences_block_gate2(project, tmp_path):
    out = tmp_path / "n6"
    build_package(project, out)
    complete_plan(project)  # plan changed after import: package shots are stale only if windows/meaning differ
    plan = json.loads((project / "shots.json").read_text(encoding="utf-8"))
    plan["shots"][0]["timeline_out_s"] = 3.0
    plan["shots"][1]["timeline_in_s"] = 3.0
    (project / "shots.json").write_text(json.dumps(plan), encoding="utf-8")
    res = evaluate_gate(load_package(out), "2")
    assert res.status == "BLOCK" and "SHOT_01: timeline differs from the project plan (re-import with refresh)" in res.issues
    shots = json.loads((out / "04_shots.json").read_text(encoding="utf-8"))
    for s in shots["shots"]:
        s["sentence_ids"] = [x for x in s["sentence_ids"] if x != "S03"]
    (out / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    res = evaluate_gate(load_package(out), "2")
    assert "sentence S03 is carried by no shot" in res.issues


def test_action_meaning_is_carried_and_checked(project, tmp_path):
    complete_plan(project)
    plan = json.loads((project / "shots.json").read_text(encoding="utf-8"))
    # SHOT_03 overlaps cue 2 ("He takes the badge."): initiator words must come from the source sentence
    plan["shots"][2]["action_meaning"] = {"source_cues": [2], "initiator": "He", "action": "takes",
                                          "receiver": "the badge"}
    (project / "shots.json").write_text(json.dumps(plan), encoding="utf-8")
    out = tmp_path / "n7"
    build_package(project, out)
    pkg = load_package(out)
    assert pkg.issues == []
    assert pkg.typed["shots"].shots[2].action_meaning.initiator == "He"
    res = evaluate_gate(pkg, "2")
    # e2e demands choreography for a declared action; the package must report exactly what e2e reports
    assert res.status == "BLOCK"
    assert any("stage the action with choreography phases" in i for i in res.issues)
    assert e2e.status(project)["direction_issues"] == [i for i in res.issues if i in e2e.status(project)["direction_issues"]]
    assert e2e.status(project)["plan_review_required"] is True


def test_import_refuses_overwrite_and_refresh_keeps_rights(project, tmp_path):
    out = tmp_path / "n8"
    build_package(project, out)
    with pytest.raises(PackageError, match="refusing to overwrite"):
        build_package(project, out)
    set_rights(out, "cleared")
    header_before = (out / "film.json").read_text(encoding="utf-8")
    build_package(project, out, refresh=True)
    assert json.loads((out / "01_story.json").read_text(encoding="utf-8"))["rights_status"] == "cleared"
    assert (out / "film.json").read_text(encoding="utf-8") == header_before
    with pytest.raises(PackageError, match="nothing to refresh"):
        build_package(project, tmp_path / "missing", refresh=True)
    with pytest.raises(PackageError, match="not a valid E2E project"):
        build_package(tmp_path, tmp_path / "n9")


def test_cli_import_then_status_matches_e2e_status(project, tmp_path):
    out = tmp_path / "n10"
    made = run("narration", "import", "--project", str(project), "--out", str(out), "--film-id", "n10")
    assert made.returncode == 0, made.stdout + made.stderr
    st = run("narration", "status", "--film", str(out))
    report = json.loads(st.stdout)
    assert report["e2e"] == json.loads(json.dumps(e2e.status(project)))
    assert report["package"]["gates"]["1"]["status"] == "OWNER_PENDING"
    assert report["package"]["gates"]["2"]["status"] == "BLOCK"
    assert st.returncode == 1  # a BLOCKed gate fails the command
    # the same package through the generic commands
    val = run("validate", "--film", str(out))
    assert val.returncode == 1 and json.loads(val.stdout)["gates"]["2"]["status"] == "BLOCK"


def test_cli_narration_status_rejects_a_drama_package(tmp_path):
    run("new", "d1", "--profile", "drama", "--root", str(tmp_path))
    bad = run("narration", "status", "--film", str(tmp_path / "d1"))
    assert bad.returncode == 2 and "not narration" in bad.stdout


def test_cli_prepare_delegates_to_e2e(tmp_path):
    audio, srt = tmp_path / "a.mp3", tmp_path / "a.srt"
    media(audio)
    source_srt(srt)
    out = tmp_path / "prepared"
    done = run("narration", "prepare", "--audio", str(audio), "--srt", str(srt), "--start", "18", "--end", "55",
               "--out", str(out))
    assert done.returncode == 0, done.stdout + done.stderr
    assert (out / "project.json").is_file() and json.loads(done.stdout)["shot_count"] == 8


def test_narration_scaffold_still_validates_cleanly(tmp_path):
    run("new", "bare", "--profile", "narration", "--root", str(tmp_path))
    pkg = load_package(tmp_path / "bare")
    res = {r.gate: r for r in evaluate_gates(pkg)}
    assert res["1"].status == "BLOCK" and "story empty" in res["1"].issues
    assert res["2"].status == "BLOCK" and "shots empty" in res["2"].issues
