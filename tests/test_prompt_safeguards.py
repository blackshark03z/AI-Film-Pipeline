"""Video-prompt safeguards for scenes that have no accepted takes yet (film07 pilot rejects: an off-screen listener
walked into frame x4, an invented line appeared in a silent shot).

* an OFF_FRAME listener gets "<name> stays fully out of frame ..." in the video prompt;
* a shot with no dialogue gets "No one speaks.";
* both only in scenes named by `preflight.safeguard_scenes`, so accepted takes of other scenes keep their prompt hash.
"""
import json
from pathlib import Path

import pytest

from film_pipeline.drama.prompt import (NO_ONE_SPEAKS, CharacterBrief, compile_scene_prompt, out_of_frame_sentence)

ROOT = Path(__file__).resolve().parents[1]
FILM07 = ROOT / "films" / "film07_first_shift"


def _unit(lines=()):
    from film_pipeline.drama.axis import AxisBook
    from film_pipeline.drama.coverage import CoverageShot, SceneUnit, SpokenLine
    from film_pipeline.drama.axis import axis_record
    book = AxisBook.for_pair("S1", "RUTH", "SAM")
    shot = CoverageShot(shot_id="S1_S1", coverage="SINGLE", shot_size="CLOSE", subject="RUTH", foreground="",
                        start_s=0.0, end_s=6.0, lines=[SpokenLine(character="RUTH", text=t, syllables=4, line_no=i)
                                                       for i, t in enumerate(lines, start=1)],
                        action="RUTH listens", axis=axis_record(book, "S1_S1", ["RUTH"]))
    return SceneUnit(scene_id="S1", duration_s=6.0, shots=[shot], axis_book=book)


def _compile(unit, **kw):
    cast = [CharacterBrief(name="RUTH", appearance="older woman", handle="the older woman")]
    return compile_scene_prompt(unit, characters=cast, setting="a diner", style="start_frame",
                                handles={"SAM": "the young man"}, **kw)


def test_default_compile_is_byte_identical_without_safeguards():
    unit = _unit()
    assert _compile(unit).sha256 == _compile(unit, out_of_frame=[], silent_line=False).sha256


def test_out_of_frame_listener_and_silent_line_are_added_when_asked():
    plan = _compile(_unit(), out_of_frame=["SAM"], silent_line=True)
    # names become handles in the start-frame style
    assert "The young man stays fully out of frame: no part of the young man enters the frame." in plan.compiled_text
    assert out_of_frame_sentence("SAM") == "SAM stays fully out of frame: no part of SAM enters the frame."
    assert plan.sections["dialogue"] == NO_ONE_SPEAKS
    assert NO_ONE_SPEAKS in plan.compiled_text


def test_silent_line_never_goes_with_dialogue():
    plan = _compile(_unit(["Hello there"]), silent_line=True)
    assert NO_ONE_SPEAKS not in plan.compiled_text and "Hello there" in plan.compiled_text


# --- the real film07 package: SC01-SC02 accepted takes must not go stale; SC03+ get the lines ------------------------

needs_film07 = pytest.mark.skipif(not (FILM07 / "takes" / "index.json").is_file(), reason="film07 package not present")


@pytest.fixture(scope="module")
def film07_prompts(tmp_path_factory):
    from film_pipeline.production.package import load_package
    from film_pipeline.production.plan import plan_package
    out = tmp_path_factory.mktemp("film07_plan")
    plan_package(load_package(FILM07), out, takes_dir=FILM07 / "takes", storyboard=False)
    return {p.stem: p.read_text(encoding="utf-8") for p in (out / "prompts").glob("*.txt")}


@needs_film07
def test_accepted_film07_takes_do_not_go_stale(film07_prompts):
    from film_pipeline.production.gate_checks import _prompt_rebind_issue
    from film_pipeline.production.takes import TakeEntry, sha256_text
    index = json.loads((FILM07 / "takes" / "index.json").read_text(encoding="utf-8"))["takes"]
    accepted = [t for t in index if t["status"] == "ACCEPTED"]
    assert accepted, "film07 has accepted takes"
    stale = []
    for t in accepted:
        current = sha256_text(film07_prompts[t["generation_id"]].strip())
        if current != t["prompt_sha256"]:
            if _prompt_rebind_issue(FILM07, TakeEntry.model_validate(t), current) != "":
                stale.append(t["take_id"])
    assert stale == []


@needs_film07
def test_film07_scenes_without_takes_get_the_safeguards(film07_prompts):
    shots = json.loads((FILM07 / "04_shots.json").read_text(encoding="utf-8"))["generations"]
    pre = json.loads((FILM07 / "03_preprod.json").read_text(encoding="utf-8"))["preflight"]
    scenes = set(pre["safeguard_scenes"])
    assert scenes == {f"SC{n:02d}" for n in range(3, 13)}
    silent = off = 0
    for g in shots:
        text, inside = film07_prompts[g["generation_id"]], g["scene_id"] in scenes
        has_off = any(a["mode"] == "OFF_FRAME" for a in g.get("listener_anchors", {}).values())
        assert (NO_ONE_SPEAKS in text) == (inside and not g.get("dialogue")), g["generation_id"]
        assert ("enters the frame." in text) == (inside and has_off), g["generation_id"]
        silent += inside and not g.get("dialogue")
        off += inside and has_off
    assert silent and off   # the film really has both kinds of shot after SC02
