"""Continuity between generations, locked looks and handoff QC
(film01 lessons: hair drift, torn-letter pieces across the 8 s cut)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from film_pipeline.drama import (
    AxisBook, CharacterBrief, CharacterLook, ContinuityState,
    CoveragePlanner, GenerationHandoff, HandoffQC, PreflightLimits,
    StoryboardGate,
    check_cross_cut, character_sheet, compile_scene_prompt, handoff_sheet,
    parse_fountain, preflight_scene, render_schematic_frame,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "drama" / \
    "sample_scene_vi.fountain"

MAI = CharacterLook(look_id="mai_kitchen", character="MAI",
                    text="woman in her 50s, short tightly curled grey hair, "
                         "brown cardigan",
                    invariants=["short tightly curled grey hair",
                                "brown cardigan"], approved=True)
HUNG = CharacterLook(look_id="hung_jacket", character="HÙNG",
                     text="man in his 20s, black buzz cut, green jacket",
                     invariants=["black buzz cut", "green jacket"],
                     approved=True)

G1_START = ContinuityState(positions={"MAI": "at the table, frame-left"},
                           props={"letter": "folded in MAI's hand"},
                           looks={"MAI": "mai_kitchen"})
G1_END = ContinuityState(positions={"MAI": "at the table, frame-left"},
                         props={"letter": "torn pieces on the floor at "
                                          "MAI's feet"},
                         looks={"MAI": "mai_kitchen"})
TEAR = "HÙNG tears the letter, the pieces fall at her feet"


@pytest.fixture()
def sample():
    script = parse_fountain(FIXTURE.read_text(encoding="utf-8"))
    scene = script.scenes[0]
    book = AxisBook.for_pair(scene.scene_id, "MAI", "HÙNG")
    return script, scene, CoveragePlanner().plan(scene, book)


def _text_only(tmp_path, sample, *, briefs=None, start_state=None):
    script, scene, unit = sample
    briefs = briefs or [CharacterBrief(name="MAI", look=MAI),
                        CharacterBrief(name="HÙNG", look=HUNG)]
    prompt = compile_scene_prompt(unit, characters=briefs,
                                  setting="Old kitchen at night",
                                  start_state=start_state)
    gate = StoryboardGate(tmp_path)
    render_schematic_frame(unit, unit.shots[0], tmp_path / "sb.png")
    gate.register(unit.scene_id, unit.shots[0].shot_id, "sb.png")
    gate.review(unit.shots[0].shot_id, status="APPROVED", reviewer="Owner")
    return prompt, dict(scene=scene, unit=unit, prompt=prompt,
                        reference_sets=[], reference_root=tmp_path,
                        storyboard=gate, known_characters=script.characters,
                        reference_mode="TEXT_ONLY", looks=[MAI, HUNG])


# ------------------------------------------------------------ locked looks

def test_locked_look_text_is_copied_verbatim(sample):
    _, _, unit = sample
    plan = compile_scene_prompt(
        unit, characters=[CharacterBrief(name="MAI", look=MAI,
                                         appearance="ignored"),
                          CharacterBrief(name="HÙNG", look=HUNG)],
        setting="Old kitchen at night")
    assert f"MAI: {MAI.text}" in plan.compiled_text
    assert "ignored" not in plan.compiled_text


def test_text_only_route_passes_without_references(tmp_path, sample):
    _, kwargs = _text_only(tmp_path, sample)
    report = preflight_scene(**kwargs)
    assert report.verdict == "PASS", report.issues


def test_text_only_route_blocks_free_text_and_unapproved_looks(tmp_path,
                                                              sample):
    briefs = [CharacterBrief(name="MAI", appearance="woman, grey bob"),
              CharacterBrief(name="HÙNG", look=HUNG)]
    _, kwargs = _text_only(tmp_path, sample, briefs=briefs)
    kwargs["looks"] = [MAI, HUNG.model_copy(update={"approved": False})]
    issues = [i.detail for i in preflight_scene(**kwargs).issues
              if i.check == "LOOK"]
    assert any("MAI: prompt does not carry the locked look" in d
               for d in issues)
    assert any("hung_jacket not approved" in d for d in issues)


def test_text_only_route_needs_a_look_per_character(tmp_path, sample):
    _, kwargs = _text_only(tmp_path, sample)
    kwargs["looks"] = [MAI]
    report = preflight_scene(**kwargs)
    assert "HÙNG: no locked look" in [i.detail for i in report.issues]


# --------------------------------------------------- generation handoff

def test_start_state_is_compiled_between_setting_and_shots(sample):
    _, _, unit = sample
    plan = compile_scene_prompt(
        unit, characters=[CharacterBrief(name="MAI", look=MAI),
                          CharacterBrief(name="HÙNG", look=HUNG)],
        setting="Old kitchen at night", start_state=G1_END)
    text = plan.compiled_text
    assert ("Continues from the previous shot: MAI at the table, "
            "frame-left; letter torn pieces on the floor at MAI's feet."
            ) in text
    assert text.index("Old kitchen") < text.index("Continues from") < \
        text.index("Shot 1 (0-")


def test_character_named_by_start_state_needs_its_look_in_prompt(
        tmp_path, sample):
    state = G1_END.model_copy(update={
        "positions": {"MAI": "at the table, frame-left",
                      "HÙNG": "by the door, frame-right"}})
    _, kwargs = _text_only(tmp_path, sample,
                           briefs=[CharacterBrief(name="MAI", look=MAI)],
                           start_state=state)
    kwargs["unit"] = kwargs["unit"].model_copy(update={"shots": [
        s for s in kwargs["unit"].shots if "HÙNG" not in s.axis.visible]})
    report = preflight_scene(**kwargs, start_state=state)
    assert ("HÙNG: prompt does not carry the locked look text for "
            "hung_jacket") in [i.detail for i in report.issues
                               if i.check == "LOOK"]


def test_second_generation_without_handoff_is_blocked(tmp_path, sample):
    _, kwargs = _text_only(tmp_path, sample)
    report = preflight_scene(**kwargs, generation_index=2)
    assert any(i.check == "STATE" and "no handoff" in i.detail
               for i in report.issues)


def test_handoff_mismatch_and_missing_prompt_state_block(tmp_path, sample):
    _, kwargs = _text_only(tmp_path, sample)       # prompt has no state
    handoff = GenerationHandoff(previous_generation_id="SC03_g1",
                                previous_action="MAI waits",
                                previous_start=G1_START,
                                previous_end=G1_END)
    moved = G1_END.model_copy(update={"props": {"letter": "on the counter"}})
    report = preflight_scene(**kwargs, generation_index=2, handoff=handoff,
                             start_state=moved)
    details = [i.detail for i in report.issues if i.check == "STATE"]
    assert "start state is not compiled into the prompt" in details
    assert any(d.startswith("props: previous end") for d in details)


def test_uncontrolled_outcome_across_the_cut_blocks_until_verified(
        tmp_path, sample):
    _, kwargs = _text_only(tmp_path, sample, start_state=G1_END)
    # the fixture scene is long; only the cut is under test here
    kwargs["limits"] = PreflightLimits(max_prompt_words=400)
    handoff = GenerationHandoff(previous_generation_id="SC03_g1",
                                previous_action=TEAR,
                                previous_start=G1_START,
                                previous_end=G1_END)
    report = preflight_scene(**kwargs, generation_index=2, handoff=handoff,
                             start_state=G1_END)
    assert [i.check for i in report.issues] == [
        "FEASIBILITY:CROSS_CUT_DEPENDENCY"]
    verified = handoff.model_copy(update={"end_state_verified": True})
    report = preflight_scene(**kwargs, generation_index=2, handoff=verified,
                             start_state=G1_END)
    assert report.verdict == "PASS", report.issues


@pytest.mark.parametrize("action, blocked", [
    (TEAR, True),
    ("Hùng xé lá thư, mảnh giấy rơi xuống sàn", True),
    ("HÙNG lays the torn pieces on the counter in front of her", True),
    ("HÙNG places the letter on the counter in front of her", False),
])
def test_cross_cut_rule(action, blocked):
    end = G1_END.model_copy(update={"props": {"letter": "on the counter"}})
    issues = check_cross_cut(scene_id="SC03", previous_action=action,
                             previous_start=G1_START, previous_end=end)
    assert bool(issues) is blocked


def test_unchanged_props_never_trigger_the_cross_cut_rule():
    assert check_cross_cut(scene_id="SC03", previous_action=TEAR,
                           previous_start=G1_END, previous_end=G1_END) == []


# ------------------------------------------------------------ handoff QC

def test_handoff_qc_checklist_needs_reviewer_and_all_pass():
    qc = HandoffQC.from_end_state("SC03_g1", "SC03_g2", G1_END, looks=[MAI])
    assert [c.item for c in qc.checks] == ["position:MAI", "prop:letter",
                                           "look:MAI"]
    assert qc.checks[2].expected == "short tightly curled grey hair; " \
                                    "brown cardigan"
    for check in qc.checks:
        qc.review(check.item, "PASS")
    assert not qc.verified                       # no reviewer yet
    qc.reviewer = "Owner"
    assert qc.verified
    qc.review("prop:letter", "FAIL", "pieces stayed behind the counter")
    handoff = qc.to_handoff(previous_action=TEAR, previous_start=G1_START,
                            previous_end=G1_END)
    assert handoff.end_state_verified is False


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="ffmpeg not installed")
def test_handoff_and_character_sheets(tmp_path):
    from PIL import Image
    clips = {}
    for name, colour in (("g1", "red"), ("g2", "blue")):
        clip = tmp_path / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color=c={colour}:s=160x90:d=2", "-pix_fmt",
                        "yuv420p", str(clip)], check=True)
        clips[name] = clip
    pair = handoff_sheet(clips["g1"], clips["g2"], tmp_path / "pair.png",
                         height=90)
    with Image.open(pair) as img:
        assert img.size == (320, 90)
        assert img.getpixel((100, 60))[0] > 200        # g1 end is red
        assert img.getpixel((260, 60))[2] > 200        # g2 start is blue
    sheet = character_sheet(clips, tmp_path / "cast.png",
                            frames_per_clip=3, height=45)
    with Image.open(sheet) as img:
        assert img.size == (240, 90)
