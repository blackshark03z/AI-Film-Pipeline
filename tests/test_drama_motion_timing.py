"""Motion timing (phase length vs the motion library) and stop-target checks (film04 SC01_g1 t9/t10)."""
import json
from pathlib import Path

from film_pipeline.drama.choreography import GenerationChoreography, Phase
from film_pipeline.drama.motion_library import MOTION_LIBRARY
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
GID = "SC01_g1"
LAYOUT = {"zones": [{"id": "booth", "label": "clerk booth"}],
          "objects": [{"id": "shutter", "label": "roll-down shutter", "zone": "booth", "placement": "above the window"}],
          "cameras": [{"id": "wide", "zone": "booth", "view": "from the hall", "sees": ["shutter"]}]}


def choreo(action, setup=(0.0, 2.0), **action_kw):
    """SETUP then ACTION then a REACTION, 8 s in total; `action` = (start, end)."""
    a0, a1 = action
    phases = [Phase(kind="SETUP", start_s=setup[0], end_s=setup[1], description="she stands at the booth"),
              Phase(kind="ACTION", start_s=a0, end_s=a1, description="she pulls the roll-down shutter", **action_kw),
              Phase(kind="REACTION", start_s=a1, end_s=8.0, description="she looks at the window")]
    return GenerationChoreography(generation_id="g", phases=phases)


def checks(c, duration=8.0):
    return sorted(i.check for i in c.problems(duration))


def test_phase_matching_the_motion_adds_nothing():
    c = choreo((2.0, 4.0), motion="lower_roll_shutter_partial", stops_at="shutter")
    assert checks(c) == []


def test_phases_without_motion_add_nothing():
    assert checks(choreo((2.0, 7.0))) == []
    assert checks(choreo((2.0, 2.2))) == []


def test_unknown_motion_blocks():
    c = choreo((2.0, 4.0), motion="levitate")
    assert checks(c) == ["MOTION_UNKNOWN"]


def test_time_fill_when_the_phase_is_much_longer_than_the_motion():
    c = choreo((2.0, 7.0), motion="lower_roll_shutter_partial", stops_at="shutter")  # 5 s for a <= 2.5 s pull
    assert checks(c) == ["TIME_FILL"]
    assert "overshoot" in c.problems(8.0)[0].detail


def test_time_fill_boundary_is_max_times_1_25():
    spec = MOTION_LIBRARY["raise_roll_shutter"]
    ok = choreo((2.0, 2.0 + spec.max_s * 1.25), motion="raise_roll_shutter")
    assert checks(ok) == []
    over = choreo((2.0, 2.0 + spec.max_s * 1.25 + 0.2), motion="raise_roll_shutter")
    assert checks(over) == ["TIME_FILL"]


def test_rushed_when_the_phase_is_shorter_than_the_motion():
    c = choreo((2.0, 2.5), motion="lower_roll_shutter_partial", stops_at="shutter")
    assert checks(c) == ["RUSHED"]


def test_mid_travel_without_a_stop_target_blocks():
    c = choreo((2.0, 4.0), motion="lower_roll_shutter_partial")
    assert checks(c) == ["STOP_TARGET"]
    # an end-of-travel motion needs none
    assert checks(choreo((2.0, 4.0), motion="raise_roll_shutter")) == []


# -- plan-level checks (location layout) -------------------------------------------------------------------------
def film(tmp_path, *, desc="KESSLER pulls the roll-down shutter down to the window sill", stops_at="shutter",
         end_pose="", end_frame=False, layout=True):
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    if layout:
        pre["locations"]["lobby_morning"]["layout"] = LAYOUT
    (root / "03_preprod.json").write_text(json.dumps(pre), encoding="utf-8")
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    g = next(x for x in shots["generations"] if x["generation_id"] == GID)
    g["choreography"]["once_actions"] = []
    action = next(p for p in g["choreography"]["phases"] if p["kind"] == "ACTION")
    action["description"] = desc
    if stops_at:
        action["stops_at"] = stops_at
    g["end_pose"], g["end_frame"] = end_pose, end_frame
    (root / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    return load_package(root)


def plan_checks(tmp_path, **kw):
    pkg = film(tmp_path, **kw)
    result = plan_package(pkg, tmp_path / "out", storyboard=False)
    issues = result.record["generations"][GID]["issues"]
    return sorted((i["check"], i["detail"]) for i in issues if i["check"] in ("STOP_TARGET", "TARGET_CONFLICT"))


def test_named_stop_object_passes(tmp_path):
    assert plan_checks(tmp_path) == []


def test_no_stops_at_means_no_new_check(tmp_path):
    assert plan_checks(tmp_path, stops_at="", desc="KESSLER speaks without looking up halfway") == []


def test_unknown_stop_object_blocks(tmp_path):
    found = plan_checks(tmp_path, stops_at="ghost")
    assert [c for c, _ in found] == ["STOP_TARGET"] and "not an object" in found[0][1]


def test_stop_object_without_layout_blocks(tmp_path):
    found = plan_checks(tmp_path, layout=False)
    assert [c for c, _ in found] == ["STOP_TARGET"]


def test_description_must_name_the_stop_object_label(tmp_path):
    found = plan_checks(tmp_path, desc="KESSLER pulls it down to the window sill")
    assert [c for c, _ in found] == ["STOP_TARGET"] and "roll-down shutter" in found[0][1]


def test_label_match_is_case_insensitive(tmp_path):
    assert plan_checks(tmp_path, desc="KESSLER pulls the Roll-Down Shutter to the sill") == []


def test_vague_position_words_conflict_in_the_action_phase(tmp_path):
    found = plan_checks(tmp_path, desc="KESSLER pulls the roll-down shutter halfway down")
    assert [c for c, _ in found] == ["TARGET_CONFLICT"] and "halfway" in found[0][1]


def test_vague_position_words_conflict_in_the_end_pose(tmp_path):
    found = plan_checks(tmp_path, end_pose="the shutter stands in the middle")
    assert [c for c, _ in found] == ["TARGET_CONFLICT"] and "end_pose" in found[0][1]


def test_end_frame_end_pose_must_mention_the_stop_object(tmp_path):
    found = plan_checks(tmp_path, end_frame=True, end_pose="her hands rest on the counter")
    assert any(c == "TARGET_CONFLICT" and "end_pose must mention" in d for c, d in found)
    ok = plan_checks(tmp_path / "ok", end_frame=True, end_pose="the roll-down shutter reaches the window sill")
    assert not any("end_pose must mention" in d for _, d in ok)
