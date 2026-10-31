"""Drama pre-production P0 (2026-10-31 handoff) — offline, no provider."""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from film_pipeline.drama import (
    AxisBook, CharacterBrief, CharacterReferenceSet, CoveragePlanner,
    PreflightLimits, ReferenceImage, SceneTiming, ShotAxisRecord,
    StoryboardGate, attachment_plan, check_axis, check_script,
    compile_scene_prompt, count_vi_syllables, hash_file, parse_fountain,
    preflight_scene, reference_strategy_for, register_reference,
    render_schematic_frame,
)
from film_pipeline.narrative import (
    NarrativeCompiler, ReferenceStrategy, ShotTruth, compile_prompt,
)
from film_pipeline.narrative.prompting import audio_from_shot_spec

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "drama" / \
    "sample_scene_vi.fountain"
SAMPLE = FIXTURE.read_text(encoding="utf-8")


def _scene(body: str, heading: str = "NỘI. PHÒNG KHÁCH - NGÀY") -> str:
    return f"{heading}\n\n{body.strip()}\n"


@pytest.fixture()
def sample():
    script = parse_fountain(SAMPLE)
    scene = script.scenes[0]
    book = AxisBook.for_pair(scene.scene_id, "MAI", "HÙNG")
    return script, scene, book, CoveragePlanner().plan(scene, book)


# ------------------------------------------------------------ #1 Fountain

def test_fountain_parses_vietnamese_scene(sample):
    script, scene, _, _ = sample
    assert script.title_page["title"] == "Cảnh mẫu kiểm thử"
    assert (scene.setting, scene.location, scene.time_of_day) == \
        ("INT", "BẾP NHÀ CŨ", "ĐÊM")
    assert scene.notes["look"].startswith("ánh đèn vàng")
    kinds = [(e.kind, e.character) for e in scene.elements]
    assert kinds == [("action", ""), ("dialogue", "HÙNG"),
                     ("dialogue", "MAI"), ("dialogue", "HÙNG"),
                     ("action", "")]
    assert scene.dialogue[1].parenthetical == "không quay lại"
    # the [[beat]] note directly above the cue tags it and hides nothing
    assert scene.dialogue[2].beat == "REVEAL"
    assert scene.dialogue_syllables == 15
    assert script.characters == ["HÙNG", "MAI"]


def test_syllables_ignore_parentheticals_and_normalise_diacritics():
    assert count_vi_syllables("Con đã mua vé rồi.") == 5
    assert count_vi_syllables("(thì thầm) Đi đi.") == 2
    decomposed = unicodedata.normalize("NFD", _scene(
        "MAI\nXin chào.\n"))
    scene = parse_fountain(decomposed).scenes[0]
    assert scene.dialogue[0].character == "MAI"
    assert scene.location == "PHÒNG KHÁCH"


def test_offscreen_voice_is_heard_not_in_frame():
    scene = parse_fountain(_scene("""
LAN đứng một mình.

LAN
Ai đó?

MẸ (V.O.)
Mẹ đây.
""")).scenes[0]
    assert scene.speakers == ["LAN", "MẸ"]
    assert scene.characters_present(["LAN", "MẸ"]) == ["LAN"]


def test_transition_and_english_heading():
    script = parse_fountain(
        "INT. KITCHEN - NIGHT\n\nANNA waits.\n\nCUT TO:\n\n"
        "EXT. STREET - NIGHT\n\nANNA walks out.\n")
    assert [s.setting for s in script.scenes] == ["INT", "EXT"]
    assert script.scenes[0].elements[-1].kind == "transition"


def test_narrative_compiler_accepts_fountain():
    text = SAMPLE + "\nNGOẠI. SÂN GA - SÁNG\n\nHÙNG đứng một mình.\n"
    compiled = NarrativeCompiler().compile(source_text=text,
                                           source_kind="fountain")
    events = compiled["events"]
    assert [e.who for e in events[1:4]] == [["HÙNG"], ["MAI"], ["HÙNG"]]
    assert events[3].function == "REVEAL"          # explicit note
    assert events[4].function == "REACTION"        # "sững sờ" cue
    assert compiled["transitions"][-1].kind == "LOCATION_TRANSITION"
    assert compiled["reveals"]


# ----------------------------------------------------------- #3 feasibility

@pytest.mark.parametrize("action,rule", [
    ("HÙNG đấm vào mặt MAI.", "CONTACT_OR_FIGHT"),
    ("Hai người ôm chầm lấy nhau.", "COMPLEX_EMBRACE"),
    ("MAI giật lấy chiếc chìa khóa.", "FAST_SMALL_HANDOFF"),
    ("Trên màn hình điện thoại hiện tin nhắn.", "READABLE_TEXT"),
])
def test_feasibility_blocks_unrenderable_action(action, rule):
    report = check_script(parse_fountain(_scene(
        f"{action}\n\nMAI\nThôi.\n")))
    assert report.verdict == "BLOCKED"
    assert rule in {i.rule for i in report.issues}


@pytest.mark.parametrize("action", [
    "MAI đánh rơi chiếc thìa.",            # dropping is not fighting
    "Họ nói về cuộc hôn nhân cũ.",         # 'hôn nhân' is not a kiss
])
def test_feasibility_avoids_false_blocks(action):
    report = check_script(parse_fountain(_scene(
        f"{action}\n\nMAI\nThôi.\n")))
    assert report.verdict == "PASS", report.issues


def test_feasibility_ignores_fights_mentioned_in_dialogue():
    report = check_script(parse_fountain(_scene(
        "MAI\nHôm qua nó đánh nhau ở trường.\n")))
    assert report.verdict == "PASS"


def test_feasibility_blocks_three_speakers_and_long_dialogue():
    long_line = " ".join(["chữ"] * 50)    # ~13 s of speech in a 15 s scene
    report = check_script(parse_fountain(_scene(f"""
AN
Một.

BÌNH
Hai.

CHI
{long_line}
""")))
    rules = {i.rule for i in report.issues}
    assert {"TOO_MANY_SPEAKERS", "DIALOGUE_TOO_LONG",
            "NO_ROOM_FOR_REACTION"} <= rules


def test_feasibility_counts_silent_characters_in_frame():
    report = check_script(parse_fountain(_scene(
        "AN, BÌNH, CHI và DŨNG ngồi quanh bàn.\n\nAN\nĂn đi.\n")),
        extra_characters=["BÌNH", "CHI", "DŨNG"])
    assert "TOO_MANY_IN_FRAME" in {i.rule for i in report.issues}


# ---------------------------------------------------------- #5 references

def _png(path: Path, shade: int) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (shade, shade, shade)).save(path)


def _ref_set(root: Path, name: str, *, approved: bool = True
             ) -> CharacterReferenceSet:
    images = []
    for shade, angle in enumerate(("FRONT", "THREE_QUARTER", "PROFILE")):
        rel = f"refs/{name}_{angle.lower()}.png"
        _png(root / rel, 40 * shade + len(name))
        image = register_reference(root, angle=angle, relative_path=rel)
        images.append(image.model_copy(update={"approved": approved}))
    return CharacterReferenceSet(character_id=name.lower(), name=name,
                                 synthetic_person=True, look_id="look_01",
                                 images=images)


def test_reference_set_is_hash_pinned(tmp_path):
    ref = _ref_set(tmp_path, "MAI")
    assert ref.problems(tmp_path) == []
    _png(tmp_path / "refs/MAI_profile.png", 250)
    assert any("changed after approval" in p for p in ref.problems(tmp_path))


def test_reference_set_requires_synthetic_approved_full_turnaround(tmp_path):
    ref = _ref_set(tmp_path, "MAI", approved=False).model_copy(
        update={"synthetic_person": False})
    ref.images.pop()
    problems = " | ".join(ref.problems(tmp_path))
    assert "not attested as a synthetic person" in problems
    assert "not approved" in problems
    assert "missing PROFILE" in problems


def test_attachment_plan_keeps_every_front_first(tmp_path):
    sets = [_ref_set(tmp_path, "MAI"), _ref_set(tmp_path, "HÙNG")]
    plan = attachment_plan(sets, max_images=3)
    assert [(p["character"], p["angle"]) for p in plan] == [
        ("MAI", "FRONT"), ("HÙNG", "FRONT"), ("MAI", "THREE_QUARTER")]
    strategy = reference_strategy_for(sets, provider_supports_image_ref=True)
    assert strategy.mode == "IMAGE_REFERENCE" and len(strategy.lineage) == 6
    text_only = reference_strategy_for(sets,
                                       provider_supports_image_ref=False)
    assert text_only.mode == "TEXT_ANCHOR_ONLY"


def test_image_reference_mode_needs_capability_and_lineage():
    with pytest.raises(ValueError, match="IMAGE_REFERENCE"):
        ReferenceStrategy(mode="IMAGE_REFERENCE")
    assert ReferenceStrategy().mode == "TEXT_ANCHOR_ONLY"


# ---------------------------------------------------------------- #9 axis

def test_axis_book_detects_flips_eyelines_and_undeclared_crossing():
    book = AxisBook.for_pair("SC01", "MAI", "HÙNG")
    assert book.eyeline_toward_partner("MAI") == "screen-right"
    shots = [
        ShotAxisRecord(shot_id="ok", visible={"MAI": "LEFT"},
                       eyelines={"MAI": "screen-right"}),
        ShotAxisRecord(shot_id="flip", visible={"MAI": "RIGHT"}),
        ShotAxisRecord(shot_id="eye", visible={"HÙNG": "RIGHT"},
                       eyelines={"HÙNG": "screen-right"}),
        ShotAxisRecord(shot_id="lens", eyelines={"MAI": "camera"}),
        ShotAxisRecord(shot_id="cross", visible={"MAI": "RIGHT"},
                       crosses_axis=True),
        ShotAxisRecord(shot_id="declared", visible={"MAI": "RIGHT"},
                       crosses_axis=True,
                       cross_justification="MAI walks around the table "
                                           "on camera"),
    ]
    flagged = {p.split(":")[0] for p in check_axis(book, shots)}
    assert flagged == {"flip", "eye", "lens", "cross"}


def test_axis_pair_must_hold_opposite_sides():
    with pytest.raises(ValueError, match="opposite"):
        AxisBook(scene_id="x", axis_pair=["A", "B"],
                 sides={"A": "LEFT", "B": "LEFT"})


# ------------------------------------------------- #10 / #11 coverage+unit

def test_dialogue_coverage_master_ots_single_reaction(sample):
    _, _, _, unit = sample
    assert [(s.coverage, s.subject) for s in unit.shots] == [
        ("MASTER", ""), ("OTS", "MAI"), ("SINGLE", "HÙNG"),
        ("REACTION", "MAI")]
    assert unit.shots[1].foreground == "HÙNG"
    assert unit.timing_problems() == [] and unit.axis_problems() == []
    assert unit.shots[-1].end_s == 15.0
    assert all(s.duration_s >= 2.0 for s in unit.shots)


def test_reveal_from_same_speaker_gets_a_punch_in():
    scene = parse_fountain(_scene("""
LINH
Bác sửa được không ạ?

ÔNG TƯ
Cái này, bác sửa rồi.

[[beat: REVEAL]]
ÔNG TƯ
Cho bố cháu.
""")).scenes[0]
    unit = CoveragePlanner().plan(scene, AxisBook.for_pair(
        scene.scene_id, "LINH", "ÔNG TƯ"))
    assert [(s.coverage, s.subject) for s in unit.shots] == [
        ("MASTER", ""), ("OTS", "ÔNG TƯ"), ("SINGLE", "ÔNG TƯ"),
        ("REACTION", "LINH")]


def test_long_exchange_is_merged_into_shot_budget():
    body = "\n\n".join(f"{'AN' if i % 2 == 0 else 'BÌNH'}\nCâu số {i}."
                       for i in range(6))
    scene = parse_fountain(_scene(body)).scenes[0]
    unit = CoveragePlanner().plan(scene, AxisBook.for_pair(
        scene.scene_id, "AN", "BÌNH"))
    assert len(unit.shots) == 4
    assert unit.shots[0].coverage == "MASTER"
    assert unit.shots[-1].coverage == "REACTION"
    assert "TWO_SHOT" in {s.coverage for s in unit.shots}
    assert sum(len(s.lines) for s in unit.shots) == 6
    assert unit.timing_problems() == []


def test_timing_problems_catch_gaps_and_short_shots(sample):
    _, _, _, unit = sample
    broken = unit.model_copy(deep=True)
    broken.shots[1].start_s += 0.5
    broken.shots[2].end_s = broken.shots[2].start_s + 1.0
    problems = " | ".join(broken.timing_problems(SceneTiming()))
    assert "gap/overlap" in problems and "< min 2s" in problems


# --------------------------------------------------------- #12 storyboard

def test_storyboard_gate_needs_approved_unchanged_first_frame(
        tmp_path, sample):
    _, _, _, unit = sample
    gate = StoryboardGate(tmp_path)
    first = unit.shots[0]
    render_schematic_frame(unit, first, tmp_path / "sb" / "s1.png")
    assert gate.problems([unit]) == [f"{first.shot_id}: no storyboard frame"]
    gate.register(unit.scene_id, first.shot_id, "sb/s1.png")
    assert "PENDING" in gate.problems([unit])[0]
    with pytest.raises(ValueError):
        gate.review(first.shot_id, status="APPROVED", reviewer=" ")
    gate.review(first.shot_id, status="APPROVED", reviewer="Owner")
    assert gate.problems([unit]) == []
    gate.save()
    assert StoryboardGate(tmp_path).problems([unit]) == []
    render_schematic_frame(unit, unit.shots[2], tmp_path / "sb" / "s1.png")
    assert "changed after review" in gate.problems([unit])[0]


# ------------------------------------------------------- #16 prompt/audio

def test_scene_prompt_orders_sections_and_keeps_vietnamese(tmp_path,
                                                          sample):
    _, _, _, unit = sample
    refs = [_ref_set(tmp_path, "MAI"), _ref_set(tmp_path, "HÙNG")]
    plan = compile_scene_prompt(
        unit, characters=[
            CharacterBrief(name="MAI", appearance="woman in her 50s",
                           voice="soft, tired"),
            CharacterBrief(name="HÙNG", appearance="man in his 20s")],
        setting="Old kitchen at night", room_tone="rain on glass",
        reference_sets=refs)
    text = plan.compiled_text
    order = [text.index(marker) for marker in (
        "MAI (see reference image)", "Old kitchen", "Shot 1 (0-",
        'HÙNG (shot 1): "Mẹ vẫn chưa ngủ à?"', "Sound: rain on glass",
        "No on-screen text")]
    assert order == sorted(order)
    assert 'MAI (shot 2, soft, tired): "Con định đi thật sao?"' in text
    assert "always frame-left" in text
    assert len(plan.reference_attachments) == 6
    assert plan.word_count == len(text.split())


def test_shot_truth_audio_is_optional_and_backward_compatible():
    base = dict(subject="a courier", wardrobe="blue cloak", world="a pass",
                blocking="", camera="wide", motion="", lighting="")
    silent = compile_prompt(ShotTruth(**base), strategy=ReferenceStrategy())
    assert "Dialogue" not in silent.compiled_text
    assert "dialogue" not in silent.sections
    audio = audio_from_shot_spec(
        {"audio": {"dialogue": "Con đã mua vé rồi.",
                   "dialogue_character_id": "c_hung",
                   "room_tone": "kitchen hum", "sfx_intent": None}},
        character_names={"c_hung": "HÙNG"})
    voiced = compile_prompt(ShotTruth(**base, **audio),
                            strategy=ReferenceStrategy())
    assert 'Dialogue: HÙNG: "Con đã mua vé rồi."' in voiced.compiled_text
    assert voiced.compiled_text.startswith(silent.compiled_text[:40])
    assert "Sound: kitchen hum." in voiced.compiled_text


# ------------------------------------------------------- Gate 3 preflight

def _ready(tmp_path, sample, *, approve: bool = True):
    script, scene, _, unit = sample
    refs = [_ref_set(tmp_path, "MAI"), _ref_set(tmp_path, "HÙNG")]
    prompt = compile_scene_prompt(
        unit, characters=[CharacterBrief(name="MAI", appearance="woman"),
                          CharacterBrief(name="HÙNG", appearance="man")],
        setting="Old kitchen at night", reference_sets=refs)
    gate = StoryboardGate(tmp_path)
    render_schematic_frame(unit, unit.shots[0], tmp_path / "sb.png")
    gate.register(unit.scene_id, unit.shots[0].shot_id, "sb.png")
    if approve:
        gate.review(unit.shots[0].shot_id, status="APPROVED",
                    reviewer="Owner")
    return dict(scene=scene, unit=unit, prompt=prompt, reference_sets=refs,
                reference_root=tmp_path, storyboard=gate,
                known_characters=script.characters)


def test_preflight_passes_a_prepared_scene(tmp_path, sample):
    report = preflight_scene(**_ready(tmp_path, sample))
    assert report.verdict == "PASS", report.issues


def test_preflight_is_fail_closed(tmp_path, sample):
    kwargs = _ready(tmp_path, sample, approve=False)
    kwargs["reference_sets"] = kwargs["reference_sets"][:1]
    report = preflight_scene(
        **kwargs, limits=PreflightLimits(max_prompt_words=10),
        previous_end_state={"lighting": "warm lamp"},
        start_state={"lighting": "daylight"})
    checks = {i.check for i in report.issues}
    assert report.verdict == "BLOCKED"
    assert {"STORYBOARD", "REFERENCE", "PROMPT_LENGTH", "STATE"} <= checks


def test_reference_files_hash_helper(tmp_path):
    _png(tmp_path / "a.png", 1)
    image = ReferenceImage(angle="FRONT", path="a.png",
                           sha256=hash_file(tmp_path / "a.png"))
    assert len(image.sha256) == 64
