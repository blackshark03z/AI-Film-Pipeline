"""Choreography phases, performance cues and the repetition rule (Muse:
key placed twice, "continues" loops; contempt rendered as a happy grin)."""
from __future__ import annotations

from pathlib import Path

import pytest

from film_pipeline.drama import (
    AxisBook, CharacterBrief, CharacterLook, CoveragePlanner,
    GenerationChoreography, PerformanceCue, Phase, StoryboardGate,
    check_repetition, compile_scene_prompt, parse_fountain, preflight_scene,
    render_schematic_frame,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "drama" / \
    "sample_scene_vi.fountain"
MAI = CharacterLook(look_id="mai_kitchen", character="MAI",
                    text="woman in her 50s, short grey hair",
                    invariants=["grey hair"], approved=True)
HUNG = CharacterLook(look_id="hung_jacket", character="HÙNG",
                     text="man in his 20s, green jacket",
                     invariants=["green jacket"], approved=True)
CUE = PerformanceCue(character="MAI", emotion_intent="contempt",
                     visible_cues=["one-sided closed-lip smirk",
                                   "narrowed eyes"],
                     prohibited_misread="broad happy grin")


def _chor(phases=None, **kw):
    phases = phases or [
        Phase(kind="SETUP", start_s=0, end_s=2, description="MAI waits"),
        Phase(kind="ACTION", start_s=2, end_s=5,
              description="MAI places the key on the counter"),
        Phase(kind="REACTION", start_s=5, end_s=8, description="HÙNG nods")]
    return GenerationChoreography(generation_id="G1", phases=phases, **kw)


def _checks(issues, name):
    return [i for i in issues if i.check == name]


def test_valid_choreography_has_no_problems():
    assert _chor().problems(8.0) == []


def test_phase_count_and_contiguity():
    one = _chor([Phase(kind="ACTION", start_s=0, end_s=8, description="x")])
    assert _checks(one.problems(8.0), "CHOREOGRAPHY")
    gap = _chor([Phase(kind="SETUP", start_s=0, end_s=2, description="a"),
                 Phase(kind="ACTION", start_s=3, end_s=8, description="b")])
    assert any("gap/overlap" in i.detail for i in gap.problems(8.0))
    assert any("last phase ends" in i.detail for i in _chor().problems(10.0))
    no_action = _chor([Phase(kind="SETUP", start_s=0, end_s=4,
                             description="a"),
                       Phase(kind="REACTION", start_s=4, end_s=8,
                             description="b")])
    assert any("no ACTION" in i.detail for i in no_action.problems(8.0))


def test_trailing_hold_warns_not_blocks():
    chor = _chor([Phase(kind="ACTION", start_s=0, end_s=3, description="a"),
                  Phase(kind="HOLD", start_s=3, end_s=8, description="b")])
    issues = chor.problems(8.0)
    assert [(i.check, i.severity) for i in issues] == \
        [("TAIL_WITHOUT_FUNCTION", "WARN")]


def test_once_action_must_be_in_an_action_phase():
    ok = _chor(once_actions=["places the key on the counter"])
    assert ok.problems(8.0) == []
    bad = _chor(once_actions=["tear the letter"])
    assert _checks(bad.problems(8.0), "CHOREOGRAPHY")
    in_setup = _chor(once_actions=["MAI waits"])
    assert _checks(in_setup.problems(8.0), "CHOREOGRAPHY")


def test_performance_cue_validation_and_text():
    assert CUE.prompt_text() == (
        "MAI: contempt — one-sided closed-lip smirk, narrowed eyes; "
        "restrained; not a broad happy grin.")
    many = CUE.model_copy(update={"visible_cues": list("abcd")})
    none = CUE.model_copy(update={"visible_cues": []})
    nomis = CUE.model_copy(update={"prohibited_misread": ""})
    for cue in (many, none, nomis):
        issues = _chor(performance=[cue]).problems(8.0)
        assert _checks(issues, "PERFORMANCE")


def test_timing_text():
    text = _chor(once_actions=["places the key on the counter"]).timing_text()
    assert text == (
        "Timing: 0-2s setup: MAI waits; 2-5s action: MAI places the key on "
        "the counter; 5-8s reaction: HÙNG nods. Happens exactly once: "
        "places the key on the counter.")
    assert "exactly once" not in _chor().timing_text()


@pytest.mark.parametrize("text,blocked", [
    ("NORA places the key once", False),
    ("DOYLE keeps tapping the counter", True),
    ("Hùng tiếp tục gõ bàn", True),
    ("she looks again at him", True),
    ("it repeats over and over", True),
    ("the discontinued sign", False),
])
def test_repetition_rule(text, blocked):
    issues = check_repetition(text)
    assert bool(issues) is blocked
    assert all(i.rule == "UNCONTROLLED_REPEAT" and i.severity == "BLOCK"
               for i in issues)


@pytest.fixture()
def sample():
    script = parse_fountain(FIXTURE.read_text(encoding="utf-8"))
    scene = script.scenes[0]
    book = AxisBook.for_pair(scene.scene_id, "MAI", "HÙNG")
    return script, scene, CoveragePlanner().plan(scene, book)


def _briefs():
    return [CharacterBrief(name="MAI", look=MAI),
            CharacterBrief(name="HÙNG", look=HUNG)]


def test_compiled_prompt_has_timing_and_performance_section(sample):
    _, _, unit = sample
    plan = compile_scene_prompt(unit, characters=_briefs(), setting="Kitchen",
                                choreography=_chor(performance=[CUE]))
    assert "Timing: 0-2s setup" in plan.sections["shots"]
    assert plan.sections["performance"] == CUE.prompt_text()
    text = plan.compiled_text
    assert text.index("Shot 1 (0-") < text.index("MAI: contempt") < \
        text.index("dialogue, lip-synced")
    assert list(plan.sections)[3:6] == ["shots", "performance", "dialogue"]
    bare = compile_scene_prompt(unit, characters=_briefs(), setting="Kitchen")
    assert bare.sections["performance"] == ""
    assert "Timing:" not in bare.compiled_text


def _preflight(tmp_path, sample, chor, setting="Kitchen"):
    script, scene, unit = sample
    plan = compile_scene_prompt(unit, characters=_briefs(), setting=setting,
                                choreography=chor)
    gate = StoryboardGate(tmp_path)
    render_schematic_frame(unit, unit.shots[0], tmp_path / "sb.png")
    gate.register(unit.scene_id, unit.shots[0].shot_id, "sb.png")
    gate.review(unit.shots[0].shot_id, status="APPROVED", reviewer="Owner")
    return preflight_scene(
        scene=scene, unit=unit, prompt=plan, reference_sets=[],
        reference_root=tmp_path, storyboard=gate,
        known_characters=script.characters, reference_mode="TEXT_ONLY",
        looks=[MAI, HUNG], choreography=chor)


def test_preflight_warn_only_still_passes(tmp_path, sample):
    _, _, unit = sample
    d = unit.duration_s
    chor = _chor([Phase(kind="ACTION", start_s=0, end_s=d - 4,
                        description="a"),
                  Phase(kind="HOLD", start_s=d - 4, end_s=d,
                        description="b")])
    report = _preflight(tmp_path, sample, chor)
    assert [i.severity for i in report.issues] == ["WARN"], report.issues
    assert report.verdict == "PASS"


def test_preflight_blocks_bad_choreography_repeat_and_unknown_cue(tmp_path,
                                                                  sample):
    _, _, unit = sample
    d = unit.duration_s
    cue = CUE.model_copy(update={"character": "GHOST"})
    chor = _chor([Phase(kind="SETUP", start_s=0, end_s=2, description="a"),
                  Phase(kind="ACTION", start_s=2, end_s=d, description="b")],
                 performance=[cue])
    report = _preflight(tmp_path, sample, chor,
                        setting="Kitchen, MAI keeps tapping")
    checks = {i.check for i in report.issues}
    assert "FEASIBILITY:UNCONTROLLED_REPEAT" in checks
    assert "PERFORMANCE" in checks
    assert report.verdict == "BLOCKED"


def test_single_shot_framing_does_not_trip_the_repeat_rule(sample):
    # film01 WP5: the compiler's own "one continuous shot" was flagged by
    # UNCONTROLLED_REPEAT; single-shot framing must stay loop-neutral
    _, _, unit = sample
    one = unit.model_copy(update={"shots": unit.shots[:1]})
    plan = compile_scene_prompt(one, characters=_briefs(), setting="Kitchen",
                                choreography=_chor())
    assert "a single shot, no cuts" in plan.sections["shots"]
    assert not check_repetition(plan.sections["shots"])
