"""Scene bible: locked location, environment causality, occupancy, story
time (film01 SC03_g2 background drift; Muse "rain inside", teaser as
continuous)."""
from __future__ import annotations

from pathlib import Path

import pytest

from film_pipeline.drama import (
    AxisBook, CharacterBrief, CharacterLook, ContinuityState, CoveragePlanner,
    LocationLook, OccupancyEvent, PreflightLimits, SceneOccupancy, StoryboardGate, StoryTime,
    check_environment, check_temporal, compile_scene_prompt, parse_fountain,
    preflight_scene, render_schematic_frame,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "drama" / \
    "sample_scene_vi.fountain"

MAI = CharacterLook(look_id="mai_kitchen", character="MAI",
                    text="woman in her 50s, short tightly curled grey hair",
                    invariants=["grey hair"], approved=True)
HUNG = CharacterLook(look_id="hung_jacket", character="HÙNG",
                     text="man in his 20s, black buzz cut, green jacket",
                     invariants=["buzz cut"], approved=True)
KITCHEN = LocationLook(
    look_id="kitchen_night", location="BẾP NHÀ CŨ",
    text="Old kitchen, warm yellow lamp, wooden table, window over the sink",
    invariants=["window over the sink"], interior=True, time_of_day="NIGHT",
    weather_outside="rain",
    environment_rules=["interior is dry; rain only visible through the "
                       "window"], approved=True)
LOBBY = LocationLook(
    look_id="lobby_day", location="Police station lobby",
    text="Police station lobby, grey morning light, wooden front counter, "
         "EXIT sign over the glass door",
    invariants=["EXIT sign above the door"], time_of_day="MORNING",
    approved=True)


@pytest.fixture()
def sample():
    script = parse_fountain(FIXTURE.read_text(encoding="utf-8"))
    scene = script.scenes[0]
    book = AxisBook.for_pair(scene.scene_id, "MAI", "HÙNG")
    return script, scene, CoveragePlanner().plan(scene, book)


def _kwargs(tmp_path, sample, *, setting, location=None, compile_with=None,
            **extra):
    script, scene, unit = sample
    briefs = [CharacterBrief(name="MAI", look=MAI),
              CharacterBrief(name="HÙNG", look=HUNG)]
    prompt = compile_scene_prompt(unit, characters=briefs, setting=setting,
                                  location=compile_with)
    gate = StoryboardGate(tmp_path)
    render_schematic_frame(unit, unit.shots[0], tmp_path / "sb.png")
    gate.register(unit.scene_id, unit.shots[0].shot_id, "sb.png")
    gate.review(unit.shots[0].shot_id, status="APPROVED", reviewer="Owner")
    return dict(scene=scene, unit=unit, prompt=prompt, reference_sets=[],
                reference_root=tmp_path, storyboard=gate,
                known_characters=script.characters,
                reference_mode="TEXT_ONLY", looks=[MAI, HUNG],
                location=location, **extra)


def _checks(report, name):
    return [i for i in report.issues if i.check == name]


# ------------------------------------------------------------ location

def test_location_problems():
    assert KITCHEN.problems() == []
    bad = LocationLook(look_id="x", location="L", text=" ", interior=True,
                       weather_outside="rain")
    found = " | ".join(bad.problems())
    assert "no text" in found and "no invariants" in found
    assert "not approved" in found and "no environment rules" in found


def test_location_text_is_copied_verbatim(sample):
    _, _, unit = sample
    briefs = [CharacterBrief(name="MAI", look=MAI),
              CharacterBrief(name="HÙNG", look=HUNG)]
    plan = compile_scene_prompt(unit, characters=briefs,
                                setting="Late evening", location=LOBBY)
    assert plan.sections["setting"].startswith(LOBBY.text + ". ")
    assert plan.sections["setting"].endswith("Late evening.")
    plan = compile_scene_prompt(unit, characters=briefs, setting="",
                                location=KITCHEN)
    assert KITCHEN.text in plan.sections["setting"]
    assert "interior is dry" in plan.sections["setting"]


def test_preflight_passes_with_location(tmp_path, sample):
    kw = _kwargs(tmp_path, sample, setting="Night", location=KITCHEN,
                 compile_with=KITCHEN,
                 limits=PreflightLimits(max_prompt_words=200))
    report = preflight_scene(**kw)
    assert report.verdict == "PASS", report.issues


def test_preflight_blocks_when_location_text_missing(tmp_path, sample):
    kw = _kwargs(tmp_path, sample, setting="Some kitchen", location=KITCHEN)
    report = preflight_scene(**kw)
    assert any("does not carry the locked location" in i.detail
               for i in _checks(report, "LOCATION"))
    assert report.verdict == "BLOCKED"


@pytest.mark.parametrize("text,blocked", [
    ("heavy rain falls on the table", True),
    ("rain on the window", False),
    ("rain seen through the glass", False),
    ("mưa ngoài cửa sổ", False),
    ("mưa trong phòng", True),
    ("a strong wind in the room", True),
    ("quiet room", False),
])
def test_interior_weather_needs_qualifier(sample, text, blocked):
    _, scene, _ = sample
    issues = check_environment(scene, KITCHEN, [text])
    found = [i for i in issues if i.check == "ENVIRONMENT_CAUSALITY"]
    assert bool(found) is blocked
    assert all(i.severity == "BLOCK" for i in found)


@pytest.mark.parametrize("scene_tod,loc_tod,blocked", [
    ("ĐÊM", "NIGHT", False), ("NIGHT", "MORNING", True),
    ("SÁNG", "DAY", False), ("DUSK", "NIGHT", True),
    ("DAWN", "BÌNH MINH", False), ("", "NIGHT", False),
    # an inherited time cannot contradict the location (film01 SC03)
    ("LOBBY - CONTINUOUS", "MORNING", False), ("LATER", "NIGHT", False),
])
def test_time_of_day_mismatch(sample, scene_tod, loc_tod, blocked):
    _, scene, _ = sample
    scene = scene.model_copy(update={"time_of_day": scene_tod})
    loc = KITCHEN.model_copy(update={"time_of_day": loc_tod})
    found = [i for i in check_environment(scene, loc, [])
             if i.check == "TIME_OF_DAY"]
    assert bool(found) is blocked


def test_preflight_blocks_time_of_day(tmp_path, sample):
    loc = KITCHEN.model_copy(update={"time_of_day": "MORNING"})
    report = preflight_scene(**_kwargs(tmp_path, sample, setting="x",
                                       location=loc, compile_with=loc))
    assert _checks(report, "TIME_OF_DAY")


# ----------------------------------------------------------- occupancy

def test_occupancy_present_at_and_problems():
    occ = SceneOccupancy(scene_id="S", initial=["NORA"], events=[
        OccupancyEvent(generation_index=2, character="DOYLE", kind="ENTER"),
        OccupancyEvent(generation_index=3, character="NORA", kind="EXIT")])
    assert occ.present_at(1) == {"NORA"}
    assert occ.present_at(2) == {"NORA", "DOYLE"}
    assert occ.present_at(3) == {"DOYLE"}
    assert occ.problems() == []
    bad = SceneOccupancy(scene_id="S", initial=["NORA"], events=[
        OccupancyEvent(generation_index=1, character="NORA", kind="ENTER"),
        OccupancyEvent(generation_index=2, character="DOYLE", kind="EXIT")])
    assert len(bad.problems()) == 2


def test_in_frame_character_must_be_present(tmp_path, sample):
    ok = SceneOccupancy(scene_id="SC01", initial=["MAI", "HÙNG"])
    report = preflight_scene(**_kwargs(tmp_path, sample, setting="x",
                                       occupancy=ok))
    assert not _checks(report, "OCCUPANCY")
    late = SceneOccupancy(scene_id="SC01", initial=["MAI"], events=[
        OccupancyEvent(generation_index=2, character="HÙNG", kind="ENTER")])
    report = preflight_scene(**_kwargs(tmp_path, sample, setting="x",
                                       occupancy=late))
    found = _checks(report, "OCCUPANCY")
    assert found and "HÙNG" in found[0].detail
    assert report.verdict == "BLOCKED"


# -------------------------------------------------------- story time

def _st(sid, order, kind="LINEAR", marker="", conflict=""):
    return StoryTime(scene_id=sid, story_order=order, transition_in=kind,
                     marker=marker, source_conflict=conflict)


def _state(props=None, look="a"):
    return ContinuityState(props=props or {}, looks={"NORA": look},
                           positions={"NORA": "counter"})


def test_linear_cut_backwards_blocks():
    issues = check_temporal([_st("A", 2), _st("B", 1)], {}, {})
    assert [(i.check, i.severity) for i in issues] == \
        [("TEMPORAL_ORDER", "BLOCK")]


def test_flashback_without_marker_blocks():
    issues = check_temporal([_st("A", 2), _st("B", 1, "FLASHBACK")], {}, {})
    assert [i.check for i in issues] == ["TEMPORAL_READABILITY"]


def test_flashback_with_marker_allows_prop_reset():
    scenes = [_st("A", 2), _st("B", 1, "FLASHBACK", "title card 'Earlier'")]
    issues = check_temporal(scenes, {"A": _state({"key": "pocket"})},
                            {"B": _state({"key": "counter"})})
    assert issues == []


def test_flashback_cannot_change_the_look():
    scenes = [_st("A", 2), _st("B", 1, "FLASHBACK", "title card")]
    issues = check_temporal(scenes, {"A": _state(look="a")},
                            {"B": _state(look="b")})
    assert [i.check for i in issues] == ["IDENTITY"]


def test_linear_state_mismatch_blocks_per_key():
    issues = check_temporal([_st("A", 1), _st("B", 2)],
                            {"A": _state({"key": "pocket"})},
                            {"B": _state({"key": "counter"})})
    assert [i.check for i in issues] == ["STATE"]


def test_source_conflict_warns():
    issues = check_temporal([_st("A", 1, conflict="script says dusk")],
                            {}, {})
    assert [(i.check, i.severity) for i in issues] == \
        [("SOURCE_CONFLICT", "WARN")]
