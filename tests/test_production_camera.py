import json
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production.camera import (PROMPT_FIELDS, CameraSetup, blocking, camera_issues, camera_report)
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

FILM03 = Path(__file__).resolve().parents[1] / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def clone(tmp_path, pre=None, shots=None):
    for name in FILES:
        (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    for name, mutate in (("03_preprod.json", pre), ("04_shots.json", shots)):
        if mutate:
            data = json.loads((tmp_path / name).read_text(encoding="utf-8"))
            mutate(data)
            (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    return load_package(tmp_path)


def found(pkg):
    assert pkg.issues == [], pkg.issues
    return camera_issues(pkg.typed["preprod"], pkg.typed["shots"])


def checks(issues, severity="BLOCK"):
    return [i.check for i in issues if i.severity == severity]


def sub(tmp_path, name):
    (tmp_path / name).mkdir()
    return tmp_path / name


def gen(shots, gid):
    return next(g for g in shots["generations"] if g["generation_id"] == gid)


def test_film03_camera_and_lighting_plan_is_clean():
    pkg = load_package(FILM03)
    assert pkg.issues == []
    report = camera_report(pkg.typed["preprod"], pkg.typed["shots"])
    assert report["ok"] and report["issues"] == []
    assert len(report["shots"]) == 16 and set(report["scenes"]) == {f"SC0{n}" for n in range(1, 9)}
    assert report["prompt_fields"] == list(PROMPT_FIELDS) == ["size"]


def test_declared_sizes_match_the_size_the_prompt_actually_uses():
    # the one field that reaches the prompt is derived from the coverage type; the plan must not contradict it
    pkg = load_package(FILM03)
    expected = {"MASTER": "WIDE", "OTS": "MEDIUM_CLOSE", "SINGLE": "CLOSE"}
    for g in pkg.typed["shots"].generations:
        assert g.camera.size == expected[g.coverage], g.generation_id


def test_packages_without_a_camera_plan_are_not_forced(tmp_path):
    def strip_pre(pre):
        for s in pre["scenes"].values():
            s.pop("lighting")

    def strip_shots(shots):
        for g in shots["generations"]:
            g.pop("camera")
    assert found(clone(tmp_path, pre=strip_pre, shots=strip_shots)) == []


def test_half_planned_film_blocks(tmp_path):
    def drop_one(shots):
        gen(shots, "SC04_g2").pop("camera")
    assert "CAMERA_MISSING" in checks(found(clone(tmp_path, shots=drop_one)))

    def drop_scene(pre):
        pre["scenes"]["SC08"].pop("lighting")
    issues = found(clone(sub(tmp_path, "x"), pre=drop_scene))
    assert "LIGHT_MISSING" in checks(issues) and any("SC08" in i.detail for i in issues)


def test_reverse_camera_needs_a_crossing_note_and_then_warns(tmp_path):
    with pytest.raises(ValueError, match="needs a crossing_note"):
        CameraSetup(size="MEDIUM", side="REVERSE")

    def cross(shots):
        gen(shots, "SC02_g1")["camera"].update(side="REVERSE", crossing_note="")
    assert any("crossing_note" in i for i in clone(tmp_path, shots=cross).issues)  # schema error = package issue

    def motivated(shots):
        gen(shots, "SC02_g1")["camera"].update(side="REVERSE", crossing_note="camera tracks across the line")
    sub_dir = sub(tmp_path, "ok")
    issues = found(clone(sub_dir, shots=motivated))
    assert "CAMERA_AXIS_CROSS" in checks(issues, "WARN") and not blocking(issues)


def fake_shots(*specs):
    from types import SimpleNamespace
    return SimpleNamespace(generations=[
        SimpleNamespace(generation_id=gid, scene_id=scene, camera=CameraSetup(size=size, **extra))
        for gid, scene, size, extra in specs])


def test_three_identical_sizes_in_one_scene_block_unless_declared():
    from film_pipeline.production.camera import _size_runs
    out = []
    _size_runs(fake_shots(("A_g1", "A", "MEDIUM", {}), ("A_g2", "A", "MEDIUM", {}), ("A_g3", "A", "MEDIUM", {})), out)
    assert [(i.check, i.severity) for i in out] == [("CAMERA_SIZE_RUN", "BLOCK")]
    out = []
    declared = {"declared_repeat": "locked-off observation"}
    _size_runs(fake_shots(("A_g1", "A", "MEDIUM", {}), ("A_g2", "A", "MEDIUM", declared),
                          ("A_g3", "A", "MEDIUM", declared)), out)
    assert out == []
    out = []  # two in a row, or a run broken by another size, is fine
    _size_runs(fake_shots(("A_g1", "A", "MEDIUM", {}), ("A_g2", "A", "MEDIUM", {}), ("A_g3", "A", "CLOSE", {}),
                          ("A_g4", "A", "CLOSE", {})), out)
    assert out == []


def test_size_run_across_scenes_is_a_warning_and_declared_repeats_clear_it(tmp_path):
    def mono(shots):
        for gid in ("SC03_g2", "SC04_g1", "SC04_g2"):
            gen(shots, gid)["camera"]["size"] = "WIDE"
            gen(shots, gid)["camera"]["lens_intent"] = "WIDE_ESTABLISH"
    issues = found(clone(tmp_path, shots=mono))
    runs = [i for i in issues if i.check == "CAMERA_SIZE_RUN"]
    assert runs and runs[0].severity == "WARN" and "SC03_g2..SC04_g2" in runs[0].detail

    def declared(shots):
        mono(shots)
        for gid in ("SC04_g1", "SC04_g2"):
            gen(shots, gid)["camera"]["declared_repeat"] = "static observation, on purpose"
    sub_dir = sub(tmp_path, "d")
    assert "CAMERA_SIZE_RUN" not in checks(found(clone(sub_dir, shots=declared)), "WARN")


def test_size_against_coverage(tmp_path):
    def master_close(shots):
        gen(shots, "SC01_g1")["camera"]["size"] = "CLOSE"
    assert "CAMERA_SIZE_COVERAGE" in checks(found(clone(tmp_path, shots=master_close)))

    def single_wide(shots):
        gen(shots, "SC05_g1")["camera"]["size"] = "WIDE"
    sub_dir = sub(tmp_path, "s")
    assert "CAMERA_SIZE_COVERAGE" in checks(found(clone(sub_dir, shots=single_wide)))

    def one_step_off(shots):
        gen(shots, "SC05_g1")["camera"]["size"] = "MEDIUM_CLOSE"
    sub_dir = sub(tmp_path, "o")
    assert not [i for i in found(clone(sub_dir, shots=one_step_off)) if i.check == "CAMERA_SIZE_COVERAGE"]

    def two_steps_off(shots):
        gen(shots, "SC05_g1")["camera"]["size"] = "MEDIUM"
    sub_dir = sub(tmp_path, "t")
    issues = found(clone(sub_dir, shots=two_steps_off))
    assert "CAMERA_SIZE_COVERAGE" in checks(issues, "WARN") and not blocking(issues)


def test_lens_intent_against_size_and_millimetres(tmp_path):
    def lens(shots):
        gen(shots, "SC01_g1")["camera"].update(lens_intent="TELE_COMPRESS", lens_mm=135)
        gen(shots, "SC05_g1")["camera"].update(lens_intent="WIDE_ESTABLISH", lens_mm=24)
    issues = found(clone(tmp_path, shots=lens))
    warned = [i.detail for i in issues if i.check == "CAMERA_LENS_SIZE"]
    assert any("SC01_g1" in d for d in warned) and any("SC05_g1" in d for d in warned)

    def mm(shots):
        gen(shots, "SC01_g1")["camera"].update(lens_intent="WIDE_ESTABLISH", lens_mm=85)
    sub_dir = sub(tmp_path, "o")
    assert any("85 mm" in i.detail for i in found(clone(sub_dir, shots=mm)))


def test_key_light_jump_between_scenes_of_one_location_warns(tmp_path):
    def flip(pre):
        pre["scenes"]["SC03"]["lighting"]["key_direction"] = "BACK"
    issues = found(clone(tmp_path, pre=flip))
    jump = [i for i in issues if i.check == "LIGHT_JUMP"]
    assert jump and jump[0].severity == "WARN" and "SC03" in jump[0].detail and not blocking(issues)


def test_schema_rejects_unmotivated_or_impossible_light_and_lens(tmp_path):
    def no_motivation(pre):
        pre["scenes"]["SC01"]["lighting"]["motivation"] = ""
    assert any("03_preprod.json" in i for i in clone(tmp_path, pre=no_motivation).issues)

    def kelvin(pre):
        pre["scenes"]["SC01"]["lighting"]["colour_temp_k"] = 20
    sub_dir = sub(tmp_path, "t")
    assert any("colour_temp_k" in i for i in clone(sub_dir, pre=kelvin).issues)

    def bad_enum(shots):
        gen(shots, "SC01_g1")["camera"]["angle"] = "SIDEWAYS"
    sub_dir = sub(tmp_path, "m")
    assert any("04_shots.json" in i for i in clone(sub_dir, shots=bad_enum).issues)


def test_prompt_hint_is_optional_text_not_part_of_the_compiled_prompt(tmp_path):
    cam = CameraSetup(size="CLOSE", angle="LOW", movement="PUSH_IN")
    assert cam.prompt_hint() == "close shot, low angle, push in"
    assert CameraSetup(size="WIDE").prompt_hint() == "wide shot"
    plan = plan_package(load_package(FILM03), tmp_path / "out", storyboard=False)
    text = (tmp_path / "out" / "prompts" / "SC01_g1.txt").read_text(encoding="utf-8").lower()
    assert "tele compress" not in text and "shallow isolate" not in text and "side_left" not in text
    assert "camera" not in plan.record


def test_plan_blocks_on_a_camera_error_and_records_it(tmp_path):
    def master_close(shots):
        gen(shots, "SC01_g1")["camera"]["size"] = "CLOSE"
    root = tmp_path / "film"
    root.mkdir()
    result = plan_package(clone(root, shots=master_close), tmp_path / "out", storyboard=False)
    assert any(p.startswith("CAMERA CAMERA_SIZE_COVERAGE") for p in result.problems)
    assert any(i["check"] == "CAMERA_SIZE_COVERAGE" for i in result.record["camera"])


def test_cli_camera(tmp_path):
    tool = Path(__file__).resolve().parents[1] / "tools" / "film.py"
    ok = subprocess.run([sys.executable, str(tool), "camera", "--film", str(FILM03)],
                        capture_output=True, text=True, encoding="utf-8")
    body = json.loads(ok.stdout)
    assert ok.returncode == 0 and body["ok"] and len(body["shots"]) == 16 and body["prompt_fields"] == ["size"]

    def master_close(shots):
        gen(shots, "SC01_g1")["camera"]["size"] = "CLOSE"
    clone(tmp_path, shots=master_close)
    bad = subprocess.run([sys.executable, str(tool), "camera", "--film", str(tmp_path)],
                         capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 1 and not json.loads(bad.stdout)["ok"]
