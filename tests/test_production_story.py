import copy
import json
from pathlib import Path

import pytest

from film_pipeline.production.gates import evaluate_gate
from film_pipeline.production.package import load_package

FILM03 = Path(__file__).resolve().parents[1] / "films" / "film03_front_desk"


def _clone(tmp_path, mutate=None, drop_preprod=False):
    """Copy film03 into tmp_path, optionally mutating the story dict."""
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json",
                 "04_shots.json"):
        if drop_preprod and name in ("03_preprod.json", "04_shots.json"):
            continue
        (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    if mutate:
        story = json.loads((tmp_path / "01_story.json").read_text(encoding="utf-8"))
        mutate(story)
        (tmp_path / "01_story.json").write_text(json.dumps(story), encoding="utf-8")
    return load_package(tmp_path)


def gate1(tmp_path, mutate=None, **kw):
    return evaluate_gate(_clone(tmp_path, mutate, **kw), "1")


def test_film03_story_passes_gate1():
    pkg = load_package(FILM03)
    assert not [i for i in pkg.issues if "01_story" in i]
    res = evaluate_gate(pkg, "1")
    assert res.status == "PASS", res.issues


def test_schema_errors_become_blocking_issues(tmp_path):
    res = gate1(tmp_path, lambda s: s.pop("logline"))
    assert res.status == "BLOCK" and any("01_story.json" in i and "logline" in i for i in res.issues)
    res = gate1(tmp_path, lambda s: s["scenes"]["SC03"].update(conflict=""))
    assert res.status == "BLOCK" and any("conflict" in i for i in res.issues)
    res = gate1(tmp_path, lambda s: s["scenes"]["SC03"].update(shift="up"))
    assert res.status == "BLOCK"


def test_scene_in_no_beat_blocks(tmp_path):
    def drop(s):
        s["structure"][2]["beats"][1]["scene_ids"] = ["SC07"]  # SC08 now orphaned
    res = gate1(tmp_path, drop)
    assert res.status == "BLOCK" and "scene SC08 appears in no beat" in res.issues


def test_beat_with_unknown_scene_blocks(tmp_path):
    res = gate1(tmp_path, lambda s: s["structure"][0]["beats"][0].update(scene_ids=["SC99"]))
    assert res.status == "BLOCK" and any("unknown scene 'SC99'" in i for i in res.issues)


def test_beat_functions_must_be_in_order(tmp_path):
    def swap(s):
        beats = s["structure"][1]["beats"]
        beats[0]["function"], beats[1]["function"] = beats[1]["function"], beats[0]["function"]
    res = gate1(tmp_path, swap)
    assert res.status == "BLOCK" and any("out of order" in i for i in res.issues)


def test_structure_needs_load_bearing_beats(tmp_path):
    def no_climax(s):
        s["structure"][2]["beats"][0]["function"] = "RESOLUTION"
    res = gate1(tmp_path, no_climax)
    assert res.status == "BLOCK" and "structure has no CLIMAX beat" in res.issues


def test_protagonist_arc_needs_existing_change_scene(tmp_path):
    res = gate1(tmp_path, lambda s: s["characters"]["NORA"].update(change_scene_id="SC42"))
    assert res.status == "BLOCK" and any("change scene 'SC42' does not exist" in i for i in res.issues)
    res = gate1(tmp_path, lambda s: s["characters"]["NORA"].update(change_scene_id=None))
    assert res.status == "BLOCK" and any("protagonist NORA" in i for i in res.issues)
    res = gate1(tmp_path, lambda s: s["characters"]["NORA"].update(arc_change=""))
    assert res.status == "BLOCK" and any("protagonist NORA" in i for i in res.issues)
    # a supporting character may have no arc
    res = gate1(tmp_path, lambda s: s["characters"]["ORTIZ"].update(arc_change="", change_scene_id=None))
    assert res.status == "PASS", res.issues


def test_no_protagonist_blocks(tmp_path):
    res = gate1(tmp_path, lambda s: s["characters"]["NORA"].update(role="supporting"))
    assert res.status == "BLOCK" and "no protagonist" in res.issues


@pytest.mark.parametrize("field,expected", [
    ("protagonist", "does not name its protagonist"),
    ("goal", "does not state the goal"),
    ("obstacle", "does not state the obstacle"),
])
def test_logline_must_carry_protagonist_goal_obstacle(tmp_path, field, expected):
    def cut(s):
        if field == "protagonist":
            s["logline"]["text"] = "A woman has a rough first morning at a desk where nobody knows her and her papers go missing."
        elif field == "goal":
            s["logline"]["goal"] = "reconcile the budget quarterly"
        else:
            s["logline"]["obstacle"] = "mountainous weather conditions"
    res = gate1(tmp_path, cut)
    assert res.status == "BLOCK" and any(expected in i for i in res.issues), res.issues


def test_logline_protagonist_must_be_a_protagonist(tmp_path):
    res = gate1(tmp_path, lambda s: s["logline"].update(protagonist="KESSLER"))
    assert res.status == "BLOCK" and any("is not a protagonist" in i for i in res.issues)


def test_story_and_script_scenes_must_match(tmp_path):
    def extra(s):
        s["scenes"]["SC09"] = copy.deepcopy(s["scenes"]["SC08"])
        s["structure"][2]["beats"][1]["scene_ids"].append("SC09")
    res = gate1(tmp_path, extra)
    assert res.status == "BLOCK" and "story scene SC09 is not in script.fountain" in res.issues

    def missing(s):
        del s["scenes"]["SC08"]
        s["structure"][2]["beats"][1]["scene_ids"] = ["SC07"]
        s["characters"]["NORA"]["change_scene_id"] = "SC07"
        s["subplots"][0]["scene_ids"] = ["SC03", "SC04"]
    res = gate1(tmp_path, missing)
    assert res.status == "BLOCK" and "script scene SC08 has no story entry" in res.issues


def test_story_character_must_exist_in_preprod(tmp_path):
    def ghost(s):
        s["characters"]["GHOST"] = {**s["characters"]["ORTIZ"], "id": "GHOST"}
    res = gate1(tmp_path, ghost)
    assert res.status == "BLOCK" and "story character GHOST has no entry in 03_preprod.characters" in res.issues
    # without a preprod stage there is nothing to compare against
    other = tmp_path / "nopre"
    other.mkdir()
    assert gate1(other, ghost, drop_preprod=True).status == "PASS"


def test_character_key_must_match_id(tmp_path):
    res = gate1(tmp_path, lambda s: s["characters"]["NORA"].update(id="NORAH"))
    assert res.status == "BLOCK" and any("!= its id" in i for i in res.issues)


def test_uncleared_adaptation_is_owner_pending_not_pass(tmp_path):
    def adapt(status):
        return lambda s: s.update(adaptation={"source": "novel X", "rights_status": status})
    for status in ("pending", "restricted", "unknown"):
        res = gate1(tmp_path, adapt(status))
        assert res.status == "OWNER_PENDING" and "rights_status=" + status in res.issues[0]
    assert gate1(tmp_path, adapt("cleared")).status == "PASS"


def test_pending_does_not_mask_a_block(tmp_path):
    def both(s):
        s["adaptation"] = {"source": "novel X", "rights_status": "pending"}
        del s["scenes"]["SC08"]
    res = gate1(tmp_path, both)
    assert res.status == "BLOCK"


def test_gate_runs_for_narration_profile_without_script(tmp_path):
    pkg = _clone(tmp_path)
    header = json.loads((tmp_path / "film.json").read_text(encoding="utf-8"))
    header["profile"] = "narration"
    (tmp_path / "film.json").write_text(json.dumps(header), encoding="utf-8")
    (tmp_path / "script.fountain").unlink()
    res = evaluate_gate(load_package(tmp_path), "1")
    assert res.status == "PASS", res.issues
    assert pkg.script is not None
