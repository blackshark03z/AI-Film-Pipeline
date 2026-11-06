import json
from pathlib import Path

import pytest

from film_pipeline.production.gates import evaluate_gate
from film_pipeline.production.package import load_package

FILM03 = Path(__file__).resolve().parents[1] / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def gate2(tmp_path, mutate=None, skip=()):
    for name in FILES:
        if name not in skip:
            (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    if mutate:
        data = json.loads((tmp_path / "02_direction.json").read_text(encoding="utf-8"))
        mutate(data)
        (tmp_path / "02_direction.json").write_text(json.dumps(data), encoding="utf-8")
    return evaluate_gate(load_package(tmp_path), "2")


def test_film03_direction_passes_gate2():
    pkg = load_package(FILM03)
    assert not [i for i in pkg.issues if "02_direction" in i]
    res = evaluate_gate(pkg, "2")
    assert res.status == "PASS", res.issues


def test_gate2_blocks_when_story_missing(tmp_path):
    res = gate2(tmp_path, skip=("01_story.json",))
    assert res.status == "BLOCK" and any("01_story.json" in i for i in res.issues)


def test_gate2_blocks_when_shots_missing(tmp_path):
    res = gate2(tmp_path, skip=("04_shots.json", "03_preprod.json"))
    assert res.status == "BLOCK" and any("04_shots.json" in i for i in res.issues)


def test_treatment_must_be_present(tmp_path):
    res = gate2(tmp_path, lambda d: (d.pop("vision"), d.update(visual_rules=[])))
    assert res.status == "BLOCK"
    assert "vision missing (tone + references)" in res.issues
    assert any(i.startswith("visual_rules missing") for i in res.issues)


def test_every_scene_needs_direction(tmp_path):
    res = gate2(tmp_path, lambda d: d["scenes"].pop("SC04"))
    assert res.status == "BLOCK" and "scene SC04 has no direction" in res.issues
    res = gate2(tmp_path, lambda d: d["scenes"].update(SC99=d["scenes"]["SC01"]))
    assert "direction for unknown scene SC99" in res.issues


def test_schema_ranges_enforced(tmp_path):
    res = gate2(tmp_path, lambda d: d["scenes"]["SC01"]["curve"]["NORA"].update(end=6))
    assert res.status == "BLOCK" and any("02_direction.json" in i for i in res.issues)
    res = gate2(tmp_path, lambda d: d["scenes"]["SC01"]["emphasis"].append(
        {"moment": "x marks", "device": "zoom"}))
    assert res.status == "BLOCK"
    res = gate2(tmp_path, lambda d: d["scenes"]["SC01"]["transition_in"].update(kind="WIPE"))
    assert res.status == "BLOCK"


def test_emotional_jump_needs_a_cause_beat(tmp_path):
    def jump(d):
        d["scenes"]["SC03"]["curve"]["ORTIZ"] = {"start": 5, "end": 5}  # SC02 ended at 2 -> jump of 3
    res = gate2(tmp_path, jump)
    assert res.status == "BLOCK"
    assert any("emotional jump ORTIZ 2->5 between SC02 and SC03" in i for i in res.issues)

    def jump_with_cause(d):
        jump(d)
        d["scenes"]["SC03"]["jump_cause_beat"] = "B3"
    assert gate2(tmp_path, jump_with_cause).status == "PASS"

    def jump_of_exactly_two(d):
        d["scenes"]["SC03"]["curve"]["ORTIZ"] = {"start": 4, "end": 4}  # 2 -> 4
    assert gate2(tmp_path, jump_of_exactly_two).status == "PASS"


def test_cause_beat_must_exist(tmp_path):
    res = gate2(tmp_path, lambda d: d["scenes"]["SC03"].update(jump_cause_beat="B99"))
    assert res.status == "BLOCK" and any("jump_cause_beat 'B99' is not a beat" in i for i in res.issues)


def test_reveal_without_emphasis_device_blocks(tmp_path):
    def strip(d):
        d["scenes"]["SC05"]["emphasis"] = []
    res = gate2(tmp_path, strip)
    assert res.status == "BLOCK" and "reveal lieutenant_confirms in SC05 has no emphasis device" in res.issues


def test_reveal_must_name_known_fact_and_scene(tmp_path):
    res = gate2(tmp_path, lambda d: d["reveals"].append({"fact_id": "nope", "scene_id": "SC05"}))
    assert "reveal of unknown fact 'nope'" in res.issues
    res = gate2(tmp_path, lambda d: d["reveals"].append({"fact_id": "time_jump", "scene_id": "SC42"}))
    assert "reveal time_jump: unknown scene 'SC42'" in res.issues


def test_emphasis_carrier_must_be_a_shot_of_the_scene(tmp_path):
    res = gate2(tmp_path, lambda d: d["scenes"]["SC05"]["emphasis"][0].update(generation_id="SC01_g1"))
    assert res.status == "BLOCK" and any("emphasis carrier 'SC01_g1'" in i for i in res.issues)


def test_pov_facts_and_characters_must_exist(tmp_path):
    res = gate2(tmp_path, lambda d: d["scenes"]["SC01"]["pov"]["audience_knows"].append("ghost_fact"))
    assert any("unknown fact 'ghost_fact'" in i for i in res.issues)
    res = gate2(tmp_path, lambda d: d["scenes"]["SC01"]["pov"].update(whose="GHOST"))
    assert any("pov.whose 'GHOST'" in i for i in res.issues)
    res = gate2(tmp_path, lambda d: d["scenes"]["SC01"]["pov"]["characters_know"].update(GHOST=["nora_is_captain"]))
    assert any("unknown character 'GHOST'" in i for i in res.issues)


def test_hold_must_be_on_a_shot_of_the_scene(tmp_path):
    res = gate2(tmp_path, lambda d: d["scenes"]["SC01"]["pacing"]["holds"][0].update(generation_id="SC02_g1"))
    assert res.status == "BLOCK" and any("hold on 'SC02_g1'" in i for i in res.issues)


def test_coverage_plan_must_be_met_by_carrier_shots(tmp_path):
    res = gate2(tmp_path, lambda d: d["coverage_plan"].update(B5=["SINGLE", "TWO_SHOT"]))
    assert res.status == "BLOCK" and "beat B5: planned TWO_SHOT but no shot of that type" in res.issues


def test_beat_without_coverage_plan_blocks(tmp_path):
    res = gate2(tmp_path, lambda d: d["coverage_plan"].pop("B6"))
    assert res.status == "BLOCK" and "beat B6 has no coverage_plan" in res.issues
    res = gate2(tmp_path, lambda d: d["coverage_plan"].update(B42=["MASTER"]))
    assert "coverage_plan for unknown beat 'B42'" in res.issues


def test_beat_without_any_shot_blocks(tmp_path):
    for name in FILES:
        (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    shots = json.loads((tmp_path / "04_shots.json").read_text(encoding="utf-8"))
    shots["generations"] = [g for g in shots["generations"] if g["scene_id"] != "SC06"]
    (tmp_path / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    res = evaluate_gate(load_package(tmp_path), "2")
    assert res.status == "BLOCK" and "beat B6 has no carrier shot in 04_shots" in res.issues


@pytest.mark.parametrize("name", ["tone", "references"])
def test_vision_fields(tmp_path, name):
    def bad(d):
        d["vision"][name] = "" if name == "tone" else ["ok words", ""]
    assert gate2(tmp_path, bad).status == "BLOCK"
