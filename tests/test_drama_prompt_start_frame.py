"""P13-04: the start-frame prompt style - motion only, generic handles, timecodes, "Sound design:"."""
from __future__ import annotations

from pathlib import Path

import pytest

from film_pipeline.drama import (
    AxisBook, CharacterBrief, CharacterLook, ContinuityState, CoveragePlanner, GenerationChoreography,
    LocationLook, PerformanceCue, Phase, PreflightLimits, StoryboardGate, compile_scene_prompt, parse_fountain,
    preflight_scene, render_schematic_frame,
)
from film_pipeline.drama.prompt import SECTION_ORDER, apply_handles

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "drama" / "sample_scene_vi.fountain"
MAI = CharacterLook(look_id="mai_kitchen", character="MAI", text="woman in her 50s, short grey hair",
                    invariants=["grey hair"], approved=True)
HUNG = CharacterLook(look_id="hung_jacket", character="HÙNG", text="man in his 20s, green jacket",
                     invariants=["green jacket"], approved=True)
LOC = LocationLook(look_id="kitchen_old", location="kitchen", text="old kitchen with a blue table",
                   invariants=["blue table"], environment_rules=["rain stays outside"], approved=True)
HANDLES = {"MAI": "the woman", "HÙNG": "the young man"}
CUE = PerformanceCue(character="MAI", emotion_intent="contempt", visible_cues=["narrowed eyes"],
                     prohibited_misread="broad happy grin")


@pytest.fixture()
def sample():
    script = parse_fountain(FIXTURE.read_text(encoding="utf-8"))
    scene = script.scenes[0]
    book = AxisBook.for_pair(scene.scene_id, "MAI", "HÙNG")
    return script, scene, CoveragePlanner().plan(scene, book)


def _one(unit):
    return unit.model_copy(update={"shots": unit.shots[:1]})


def _briefs(handles=True):
    return [CharacterBrief(name="MAI", look=MAI, voice="low voice", handle="the woman" if handles else ""),
            CharacterBrief(name="HÙNG", look=HUNG, handle="the young man" if handles else "")]


def _chor(**kw):
    return GenerationChoreography(generation_id="G1", phases=[
        Phase(kind="SETUP", start_s=0, end_s=2, description="MAI waits."),
        Phase(kind="ACTION", start_s=2, end_s=5, description="she places the key; HÙNG watches"),
        Phase(kind="HOLD", start_s=5, end_s=8, description="HÙNG nods")], **kw)


def _compile(unit, **kw):
    args = dict(characters=_briefs(), setting="rain at the window", room_tone="rain on glass", sfx=["a cup set down"],
                location=LOC, style="start_frame", choreography=_chor(once_actions=["places the key"]))
    args.update(kw)
    return compile_scene_prompt(unit, **args)


def test_full_style_is_unchanged_by_default(sample):
    _, _, unit = sample
    plan = compile_scene_prompt(unit, characters=_briefs(), setting="Kitchen", location=LOC, choreography=_chor())
    same = compile_scene_prompt(unit, characters=_briefs(), setting="Kitchen", location=LOC, choreography=_chor(),
                                style="full")
    assert plan.compiled_text == same.compiled_text
    assert MAI.text in plan.sections["characters"] and LOC.text in plan.sections["setting"]
    assert "Timing:" in plan.sections["shots"] and plan.sections["sound"] == ""
    assert "MAI" in plan.compiled_text and "the woman" not in plan.compiled_text


def test_characters_section_is_empty_and_setting_drops_the_look(sample):  # 3a, 3b
    _, _, unit = sample
    s = _compile(unit).sections
    assert s["characters"] == ""
    assert LOC.text not in s["setting"] and MAI.text not in s["setting"]
    assert s["setting"] == "Rain stays outside. Rain at the window."  # sentence starts capitalised


def test_continuity_keeps_only_the_end_change(sample):  # 3c
    _, _, unit = sample
    start = ContinuityState(positions={"MAI": "by the table"}, props={"key": "in her hand"})
    end = ContinuityState(positions={"MAI": "by the table"}, props={"key": "on the counter"})
    s = _compile(unit, start_state=start, end_state=end).sections
    assert s["continuity"] == "Ends with key on the counter, held to the last frame."
    assert _compile(unit, start_state=start).sections["continuity"] == ""


def test_single_shot_and_timecodes(sample):  # 3d
    _, _, unit = sample
    one = _one(unit)
    shots = _compile(one, handles=HANDLES).sections["shots"]
    assert shots.startswith(f"A single unbroken {one.duration_s:g}s shot, no scene cuts, 16:9: ")
    assert "[0-2s] The woman waits. [2-5s] She places the key; the young man watches. [5-8s] The young man nods." in shots
    assert shots.endswith("This happens exactly once: places the key.")
    assert "Timing:" not in shots and "setup" not in shots and "Shot 1" not in shots
    assert "exactly once" not in _compile(one, choreography=_chor()).sections["shots"]
    multi = _compile(unit).sections["shots"]  # several shots keep the cut wording
    assert "hard cuts at the marks" in multi and "Shot 1 (0-" in multi and "single unbroken" not in multi
    assert "[0-2s]" in multi


def test_timecode_text_leaves_timing_text_alone():
    chor = _chor(once_actions=["places the key"])
    assert chor.timecode_text() == "[0-2s] MAI waits. [2-5s] she places the key; HÙNG watches. [5-8s] HÙNG nods."
    assert chor.timing_text().startswith("Timing: 0-2s setup: MAI waits;")


def test_handles_replace_names_everywhere_and_capitalise_sentence_starts(sample):  # 3e
    _, _, unit = sample
    chor = _chor(once_actions=["MAI places the key"], performance=[CUE])
    # HÙNG is not in the cast list yet is named in the phase text: the film-wide map covers him
    plan = _compile(_one(unit), characters=[_briefs()[0]], choreography=chor, handles=HANDLES)
    text = plan.compiled_text
    assert "MAI" not in text and "HÙNG" not in text
    assert "[2-5s] She places the key; the young man watches." in text
    assert "This happens exactly once: the woman places the key." in text
    assert plan.sections["performance"].startswith("The woman plays it restrained: contempt")


def test_apply_handles_is_whole_word_and_case_sensitive():
    assert apply_handles("MAI and MAIN, mai. MAI's cup", {"MAI": "the woman"}) == \
        "The woman and MAIN, mai. The woman's cup"
    assert apply_handles("a MAI", {"MAI": ""}) == "a MAI"
    assert apply_handles("a MAI", {}) == "a MAI"
    assert apply_handles("MA MAI", {"MA": "x", "MAI": "the woman"}) == "X the woman"


def test_name_without_handle_stays(sample):
    _, _, unit = sample
    plan = _compile(_one(unit), characters=_briefs(handles=False))
    assert "MAI" in plan.compiled_text and "the woman" not in plan.compiled_text


def test_dialogue_is_who_says_text_without_quotes(sample):  # 3f
    _, _, unit = sample
    dialogue = _compile(unit).sections["dialogue"]
    assert "lip-synced" not in dialogue and '"' not in dialogue
    assert "The young man says in Vietnamese: Mẹ vẫn chưa ngủ à?" in dialogue
    assert "The woman says in Vietnamese: " in dialogue
    plain = _compile(unit, characters=_briefs(handles=False)).sections["dialogue"]
    assert plain.startswith("HÙNG says in Vietnamese: Mẹ vẫn chưa ngủ à?")


def test_sound_design(sample):  # 3g
    _, _, unit = sample
    assert _compile(unit).sections["sound"] == "Sound design: rain on glass; a cup set down."
    assert _compile(unit, room_tone="", sfx=None).sections["sound"] == ""


def test_no_touching_dropped_unless_two_people_are_visible(sample):  # 3h
    _, _, unit = sample
    axis = unit.shots[0].axis
    solo = unit.shots[0].model_copy(update={"axis": axis.model_copy(update={"visible": ["MAI"]})})
    alone = _compile(unit.model_copy(update={"shots": [solo]}))
    assert "No touching." not in alone.sections["prohibitions"]
    assert "No on-screen text" in alone.sections["prohibitions"] and "Nobody looks" in alone.sections["prohibitions"]
    both = unit.shots[0].model_copy(update={"axis": axis.model_copy(update={"visible": ["MAI", "HÙNG"]})})
    assert "No touching." in _compile(unit.model_copy(update={"shots": [both]})).sections["prohibitions"]
    full = compile_scene_prompt(unit.model_copy(update={"shots": [solo]}), characters=_briefs(), setting="x")
    assert "No touching." in full.sections["prohibitions"]


def _preflight(tmp_path, sample, style):
    script, scene, unit = sample
    one = _one(unit)
    chor = _chor()
    plan = _compile(one, choreography=chor)  # always the start-frame prompt
    gate = StoryboardGate(tmp_path)
    render_schematic_frame(one, one.shots[0], tmp_path / "sb.png")
    gate.register(one.scene_id, one.shots[0].shot_id, "sb.png")
    gate.review(one.shots[0].shot_id, status="APPROVED", reviewer="Owner")
    return preflight_scene(
        scene=scene, unit=one, prompt=plan, reference_sets=[], reference_root=tmp_path, storyboard=gate,
        known_characters=script.characters, reference_mode="TEXT_ONLY", looks=[MAI, HUNG], location=LOC,
        limits=PreflightLimits(max_prompt_words=400, prompt_style=style), choreography=chor)


def test_preflight_skips_only_the_look_text_checks(tmp_path, sample):  # 5
    assert PreflightLimits().prompt_style == "start_frame"
    report = _preflight(tmp_path, sample, "start_frame")
    details = " ".join(i.detail for i in report.issues)
    assert "does not carry the locked" not in details, report.issues
    assert "empty section" not in details
    assert {i.check for i in report.issues} <= {"TIMING", "CHOREOGRAPHY"}, report.issues  # fixture timing only
    # the "full" route still requires the look text in the prompt (here it is the start_frame prompt, so it is missing)
    full = _preflight(tmp_path, sample, "full")
    assert any("does not carry the locked look" in i.detail for i in full.issues)
    assert any("does not carry the locked location" in i.detail for i in full.issues)


def test_preflight_still_blocks_a_missing_look(tmp_path, sample):
    script, scene, unit = sample
    one = _one(unit)
    report = preflight_scene(
        scene=scene, unit=one, prompt=_compile(one), reference_sets=[], reference_root=tmp_path,
        storyboard=StoryboardGate(tmp_path), known_characters=script.characters, reference_mode="TEXT_ONLY",
        looks=[MAI], limits=PreflightLimits(prompt_style="start_frame"))
    assert any(i.check == "LOOK" and "no locked look" in i.detail for i in report.issues)


def test_text_reads_action_then_end_state_and_never_says_continuous(sample):
    _, _, unit = sample
    end = ContinuityState(props={"key:": "on the counter"})
    plan = _compile(_one(unit), choreography=_chor(performance=[CUE]), end_state=end)
    text = plan.compiled_text
    # Google: subject + action first; the end state right after the timecodes, before mood/sound/setting
    assert text.index("[0-2s]") < text.index("Ends with key on the counter") < text.index("Sound design")
    assert "continuous" not in text.lower()  # feasibility UNCONTROLLED_REPEAT: "continuous" invites a loop
    assert "not a " not in plan.sections["performance"]
    assert list(plan.sections) == list(SECTION_ORDER)  # Gate 3 PROMPT_ORDER is about the record, not the text
