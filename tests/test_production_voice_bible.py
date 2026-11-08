"""P14-05: each speaking character has one voice, written into every line and checked against a reference take."""
from types import SimpleNamespace

import pytest

from film_pipeline.production.sections import CharacterSpec, VoiceReference
from film_pipeline.production.takes import _questions

LOOK = {"look_id": "theo_rain_jacket", "character": "THEO", "text": "young man, olive green rain jacket",
        "invariants": ["olive green rain jacket"], "approved": True}


def _spec(ref=None):
    return CharacterSpec(look=LOOK, video_text="young man", voice="breathless young male voice", handle="the young man",
                         voice_reference=ref)


def _decl(lines):
    choreo = SimpleNamespace(phases=[], once_actions=[], performance=[])
    return SimpleNamespace(scene_id="SC01", readout=[], choreography=choreo, dialogue=lines, camera=None,
                           start_state="", end_state="")


def _pre(spec):
    return SimpleNamespace(scenes={}, locations={}, states={}, characters={"THEO": spec})


def audio(questions):
    return [q["question"] for q in questions if q["group"] == "audio"]


def test_reference_take_is_asked_about():
    spec = _spec(VoiceReference(take_id="SC01_g2_t2", start_s=4.0, end_s=7.0))
    asked = audio(_questions(_decl([15]), _pre(spec), {15: "THEO: One ticket to Halden. Please."}))
    assert asked == ["THEO sounds like the voice bible: breathless young male voice; same voice as SC01_g2_t2 4-7s?"]


def test_without_a_reference_the_first_accepted_take_becomes_it():
    asked = audio(_questions(_decl([15, 16]), _pre(_spec()), {15: "THEO: One.", 16: "THEO: Two."}))
    assert len(asked) == 1 and "no reference take yet" in asked[0]


def test_a_silent_shot_has_no_voice_question():
    assert audio(_questions(_decl([]), _pre(_spec()), {})) == []


def test_reference_range_is_ordered():
    with pytest.raises(ValueError):
        VoiceReference(take_id="SC01_g2_t2", start_s=7.0, end_s=4.0)
