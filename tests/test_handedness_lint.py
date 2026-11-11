"""A bare "left hand" / "right hand" is a label defect waiting to happen (film07 pilot: SC01_g17-g24 said Sam's left hand,
the picture showed the anatomical right, the far arm on screen-left). Every hand named in choreography or prop state must
be stated in both frames: "his right hand (the arm farther from camera, on screen-left)". The lint warns, it never blocks."""
import json
from pathlib import Path

import pytest

from film_pipeline.drama.handedness import bare_hand_mentions

ROOT = Path(__file__).resolve().parents[1]
FILM07 = ROOT / "films" / "film07_first_shift"
BOTH = "(the arm farther from camera, on screen-left)"


@pytest.mark.parametrize("text", [
    "SAM lifts the white mug in his right hand",
    "held in RUTH's left hand at chest height",
    "she raises her right arm",
    "the mug in his left-hand grip",
    "his right hand (screen-left)",              # one frame only
    "his right hand (the arm farther from camera)",
    "the white mug in his Right Hand.",
])
def test_bare_hands_are_flagged(text):
    assert bare_hand_mentions(text), text


@pytest.mark.parametrize("text", [
    f"SAM lifts the white mug in his right hand {BOTH}",
    "held in RUTH's right hand (the arm nearer the camera, on screen-left) at chest height",
    "her left arm (the arm farther from camera, on screen-right) hangs loose",
    "both hands visible and empty",
    "SAM stands at the right of the frame",
    "SAM's hands at his sides",
    "the left side of the counter",
    "",
])
def test_stated_in_both_frames_or_not_a_hand_is_clean(text):
    assert bare_hand_mentions(text) == []


def test_one_mention_with_the_frames_does_not_excuse_a_second_bare_one():
    text = f"he lifts it in his right hand {BOTH}, then takes it in his left hand"
    assert bare_hand_mentions(text) == ["left hand"]


def _planner():
    from film_pipeline.production.package import load_package
    from film_pipeline.production.plan import _Plan
    return _Plan(load_package(FILM07), None, None, None, frozenset())


needs_film07 = pytest.mark.skipif(not (FILM07 / "04_shots.json").is_file(), reason="film07 package not present")


@needs_film07
def test_plan_warns_on_a_bare_hand_in_a_hardened_scene_and_stays_quiet_otherwise():
    p = _planner()
    decl = next(g for g in p.shots.generations if g.generation_id == "SC05_g13")
    assert p.handedness_issues(decl) == []          # SC05 is authored with both frames
    phases = list(decl.choreography.phases)
    phases[1] = phases[1].model_copy(update={"description": "RUTH lifts her own empty mug in her right hand"})
    bare = decl.model_copy(update={"choreography": decl.choreography.model_copy(update={"phases": phases})})
    issues = p.handedness_issues(bare)
    assert [(i.check, i.severity) for i in issues] == [("HANDEDNESS_BARE", "WARN")]
    assert "right hand" in issues[0].detail and "SC05_g13" in issues[0].detail
    # a scene outside preflight.safeguard_scenes (accepted takes, frozen prompts) is not linted
    old = next(g for g in p.shots.generations if g.generation_id == "SC01_g16")
    assert p.handedness_issues(old) == []


@needs_film07
def test_no_film07_shot_after_sc02_names_a_bare_hand():
    p = _planner()
    scenes = set(p.pre.preflight.safeguard_scenes)
    bad = {g.generation_id: p.handedness_issues(g) for g in p.shots.generations if g.scene_id in scenes}
    assert {k: v for k, v in bad.items() if v} == {}
    # and the mug-in-hand states that exist are the both-frames form
    states = json.loads((FILM07 / "03_preprod.json").read_text(encoding="utf-8"))["states"]
    held = [v["props"]["the white mug:"] for k, v in states.items()
            if k.startswith("SC05_") and v["props"].get("the white mug:", "").startswith("held in")]
    assert held and all("screen-left" in h and "camera" in h for h in held)
