import json
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production.continuity import KINDS, blocking, continuity_issues, continuity_report, kind_of
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

FILM03 = Path(__file__).resolve().parents[1] / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
LETTER = "the letter:"


def clone(tmp_path, pre=None, shots=None):
    for name in FILES:
        (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    for name, mutate in (("03_preprod.json", pre), ("04_shots.json", shots)):
        if mutate:
            data = json.loads((tmp_path / name).read_text(encoding="utf-8"))
            mutate(data)
            (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    return load_package(tmp_path)


def sub(tmp_path, name):
    (tmp_path / name).mkdir()
    return tmp_path / name


def issues(pkg, include_temporal=True):
    assert pkg.issues == [], pkg.issues
    return continuity_issues(pkg.typed["preprod"], pkg.typed["shots"], include_temporal)


def checks(found, severity="BLOCK"):
    return [i.check for i in found if i.severity == severity]


def gen(shots, gid):
    return next(g for g in shots["generations"] if g["generation_id"] == gid)


def test_film03_is_clean_and_every_kind_is_reported():
    pkg = load_package(FILM03)
    report = continuity_report(pkg.typed["preprod"], pkg.typed["shots"])
    assert report["ok"] and report["issues"] == []
    assert tuple(report["by_kind"]) == KINDS and report["generations"] == 16


def test_letter_moves_pocket_to_bin_without_an_action_blocks(tmp_path):
    def teleport(pre):  # SC01_g1 starts with the letter in NORA's pocket; end it in the bin with no phase naming it
        pre["states"]["SC01_g2"]["props"][LETTER] = "crumpled, in the waste bin"
        pre["states"]["SC01_end"]["props"][LETTER] = "crumpled, in the waste bin"
    found = issues(clone(tmp_path, pre=teleport))
    hit = [i for i in found if i.check == "OBJECT_NO_CAUSE"]
    assert len(hit) == 1 and hit[0].severity == "BLOCK"
    assert "SC01_g1" in hit[0].detail and "the letter" in hit[0].detail and "waste bin" in hit[0].detail


def test_the_causing_action_clears_it(tmp_path):
    def teleport(pre):
        pre["states"]["SC01_g2"]["props"][LETTER] = "crumpled, in the waste bin"
        pre["states"]["SC01_end"]["props"][LETTER] = "crumpled, in the waste bin"
        pre["states"]["SC02_g1"]["props"][LETTER] = "crumpled, in the waste bin"
        pre["states"]["SC02_g2"]["props"][LETTER] = "crumpled, in the waste bin"

    def cause(shots):
        gen(shots, "SC01_g1")["choreography"]["phases"][2]["description"] = "NORA drops the letter in the waste bin"
    pkg = clone(tmp_path, pre=teleport, shots=cause)
    assert "OBJECT_NO_CAUSE" not in checks(issues(pkg, False))


def test_setup_phase_is_not_a_cause(tmp_path):
    def teleport(pre):
        pre["states"]["SC03_g2"]["props"][LETTER] = "in the waste bin"

    def only_setup(shots):
        for phase in gen(shots, "SC03_g1")["choreography"]["phases"]:
            phase["kind"] = "SETUP"
    pkg = clone(tmp_path, pre=teleport, shots=only_setup)
    # the letter has no phase of kind ACTION/CONSEQUENCE that names it -> the prop change is uncaused
    assert "OBJECT_NO_CAUSE" in checks(issues(pkg, False))


def test_prop_appearing_or_vanishing_needs_a_cause(tmp_path):
    def vanish(pre):
        for state in ("SC04_g2", "SC04_end"):
            pre["states"][state]["props"].pop("the desk phone:")
    found = issues(clone(tmp_path, pre=vanish), False)
    assert any(i.check == "OBJECT_NO_CAUSE" and "disappears" in i.detail for i in found)


def test_person_moves_in_a_generation_without_any_action_blocks(tmp_path):
    def stand_still_phases(shots):
        gen(shots, "SC01_g1")["choreography"]["phases"] = [
            {"kind": "HOLD", "start_s": 0.0, "end_s": 8.0, "description": "the lobby is quiet"}]
    found = issues(clone(tmp_path, shots=stand_still_phases), False)
    assert any(i.check == "SPATIAL_NO_ACTION" and "NORA" in i.detail for i in found if i.severity == "BLOCK")


def test_unnamed_mover_is_only_a_warning(tmp_path):
    def rename(shots):
        for phase in gen(shots, "SC01_g1")["choreography"]["phases"]:
            phase["description"] = phase["description"].replace("NORA", "the visitor")
    found = issues(clone(tmp_path, shots=rename), False)
    assert "SPATIAL_UNNAMED" in checks(found, "WARN") and "SPATIAL_NO_ACTION" not in checks(found)


def fork_state(source, new_id, patch):
    """pre-mutator: copy state `source` as `new_id` and apply `patch(state)`; returns the shots-mutator target."""
    def mutate(pre):
        state = json.loads(json.dumps(pre["states"][source]))
        patch(state)
        pre["states"][new_id] = state
    return mutate


def restart_from(gid, state_id):
    def mutate(shots):
        gen(shots, gid)["start_state"] = state_id
    return mutate


def test_handoff_mismatch_inside_a_scene_blocks_but_across_a_cut_only_warns(tmp_path):
    # SC02_g2 is chained from SC02_g1 (same scene) but starts from a state where the letter is elsewhere
    drift = fork_state("SC02_g2", "SC02_g2_alt", lambda s: s["props"].update({LETTER: "in KESSLER's hand"}))
    block = issues(clone(tmp_path, pre=drift, shots=restart_from("SC02_g2", "SC02_g2_alt")), False)
    assert "OBJECT_HANDOFF" in checks(block)

    # SC03_g1 is chained from SC02_g2 across a scene cut: a different prop place is only a warning
    cut = fork_state("SC03_g1", "SC03_g1_alt", lambda s: s["props"].update({LETTER: "in KESSLER's hand"}))
    warn = issues(clone(sub(tmp_path, "cut"), pre=cut, shots=restart_from("SC03_g1", "SC03_g1_alt")), False)
    assert "OBJECT_HANDOFF" in checks(warn, "WARN") and "OBJECT_HANDOFF" not in checks(warn)


def test_positions_must_continue_inside_a_scene_hand_off(tmp_path):
    jump = fork_state("SC02_g2", "SC02_g2_alt",
                      lambda s: s["positions"].update({"NORA": "behind the desk, frame-right"}))
    assert "SPATIAL_HANDOFF" in checks(issues(clone(tmp_path, pre=jump, shots=restart_from("SC02_g2", "SC02_g2_alt")),
                                              False))


def test_visual_continuity(tmp_path):
    def light(pre):
        pre["states"]["SC01_g1"]["lighting"] = "cold fluorescent"
        pre["states"]["SC01_g2"]["lighting"] = "warm tungsten"
    assert "VISUAL_LIGHTING_CHANGE" in checks(issues(clone(tmp_path, pre=light), False))

    def lamp(shots):
        gen(shots, "SC01_g1")["choreography"]["phases"][1]["description"] = "KESSLER switches the lamp on"
    ok = issues(clone(sub(tmp_path, "ok"), pre=light, shots=lamp), False)
    assert "VISUAL_LIGHTING_CHANGE" not in checks(ok)


def test_look_time_of_day_and_location_rules(tmp_path):
    def coat_off(pre):
        pre["states"]["SC01_g2"]["looks"]["NORA"] = "nora_shirt"
    assert "VISUAL_LOOK_CHANGE" in checks(issues(clone(tmp_path, pre=coat_off), False))

    def clock(pre):
        pre["states"]["SC01_g1"]["time_of_day"] = "morning"
        pre["states"]["SC01_g2"]["time_of_day"] = "evening"
    found = issues(clone(sub(tmp_path, "t"), pre=clock), False)
    assert {"VISUAL_TIME_OF_DAY_CHANGE", "TEMPORAL_SCENE_TIME"} <= set(checks(found))

    def place(pre):
        pre["states"]["SC01_g1"]["location"] = "briefing_morning"
    found = issues(clone(sub(tmp_path, "l"), pre=place), False)
    assert "VISUAL_SCENE_LOCATION" in checks(found)


def test_emotional_jump_is_a_warning_unless_a_reaction_beat_precedes(tmp_path):
    def spike(shots):
        gen(shots, "SC01_g1")["choreography"]["performance"][0]["intensity"] = "restrained"
        gen(shots, "SC01_g2")["choreography"]["performance"].append(
            {"character": "KESSLER", "emotion_intent": "rage", "visible_cues": ["clenched jaw"],
             "intensity": "strong", "prohibited_misread": "calm"})
    found = issues(clone(tmp_path, shots=spike), False)
    assert "EMOTIONAL_JUMP" in checks(found, "WARN") and found and not blocking(found)

    def beat(shots):
        spike(shots)
        gen(shots, "SC01_g1")["choreography"]["phases"][1]["kind"] = "REACTION"
    assert "EMOTIONAL_JUMP" not in checks(issues(clone(sub(tmp_path, "b"),
                                                       shots=beat), False), "WARN")


def test_repeated_once_action_warns_but_repeated_speech_does_not(tmp_path):
    def repeat(shots):
        gen(shots, "SC03_g2")["choreography"]["once_actions"] = ["lays a folded letter on the desk"]
        gen(shots, "SC03_g1")["choreography"]["once_actions"] = ["lays a folded letter on the desk"]
    found = issues(clone(tmp_path, shots=repeat), False)
    assert "ACTION_REPEATED" in checks(found, "WARN")
    assert not any(i.check == "ACTION_REPEATED" and "speaks" in i.detail for i in issues(load_package(FILM03)))


def test_missing_state_and_dangling_handoff_block(tmp_path):
    def broken(shots):
        gen(shots, "SC02_g1")["end_state"] = "NOPE"
    pkg = clone(tmp_path, shots=broken)
    found = continuity_issues(pkg.typed["preprod"], pkg.typed["shots"]) if pkg.typed else []
    # either the package refuses the dangling reference or the continuity bible does; never silently passes
    assert pkg.issues or "ACTION_STATE_MISSING" in checks(found)


def test_kind_of_and_blocking_format():
    assert kind_of("OBJECT_NO_CAUSE") == "OBJECT" and kind_of("TEMPORAL_ORDER") == "TEMPORAL"
    pkg = load_package(FILM03)
    assert blocking(continuity_issues(pkg.typed["preprod"], pkg.typed["shots"])) == []


def test_plan_blocks_on_a_continuity_error_and_records_findings(tmp_path):
    def teleport(pre):
        pre["states"]["SC01_g2"]["props"][LETTER] = "in the waste bin"
        pre["states"]["SC01_end"]["props"][LETTER] = "in the waste bin"
    pkg = clone(sub(tmp_path, "film"), pre=teleport)
    result = plan_package(pkg, tmp_path / "out", storyboard=False)
    assert any(p.startswith("CONTINUITY OBJECT_NO_CAUSE") for p in result.problems)
    assert any(i["check"] == "OBJECT_NO_CAUSE" for i in result.record["continuity"])
    clean = plan_package(load_package(FILM03), tmp_path / "clean", storyboard=False)
    assert "continuity" not in clean.record and not any("CONTINUITY" in p for p in clean.problems)


def test_cli_continuity(tmp_path):
    tool = Path(__file__).resolve().parents[1] / "tools" / "film.py"
    ok = subprocess.run([sys.executable, str(tool), "continuity", "--film", str(FILM03)],
                        capture_output=True, text=True, encoding="utf-8")
    assert ok.returncode == 0 and json.loads(ok.stdout)["ok"] is True

    def teleport(pre):
        pre["states"]["SC01_g2"]["props"][LETTER] = "in the waste bin"
        pre["states"]["SC01_end"]["props"][LETTER] = "in the waste bin"
    clone(tmp_path, pre=teleport)
    bad = subprocess.run([sys.executable, str(tool), "continuity", "--film", str(tmp_path)],
                         capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 1 and json.loads(bad.stdout)["by_kind"]["OBJECT"]["BLOCK"] >= 1


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_is_a_reported_bucket(kind):
    pkg = load_package(FILM03)
    assert kind in continuity_report(pkg.typed["preprod"], pkg.typed["shots"])["by_kind"]
