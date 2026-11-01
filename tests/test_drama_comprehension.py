from film_pipeline.drama import (Carrier, CharacterIntro, ContextCard,
                                 IdentityTag, StoryFact, SubtitleCue,
                                 check_comprehension, read_time)

TIMELINE = ["SC01_g1", "SC01_g2", "SC02_g1"]
IN_FRAME = {"SC01_g1": ["ROSA", "ELENA", "MARCUS"],
            "SC01_g2": ["ELENA", "MARCUS"], "SC02_g1": ["ROSA", "ELENA"]}
ROSA = CharacterIntro(character="ROSA", label="ROSA",
                      relation="their late mother's sister")
ELENA = CharacterIntro(character="ELENA", label="ELENA",
                       relation="the elder daughter")
MARCUS = CharacterIntro(character="MARCUS", label="MARCUS",
                        relation="her younger brother", needed_by="SC01_g2")
TAGS = [IdentityTag(character="ROSA", generation_id="SC01_g1", start_s=0.2,
                    end_s=2.7, anchor_x=0.3),
        IdentityTag(character="ELENA", generation_id="SC01_g1", start_s=4.4,
                    end_s=6.6, anchor_x=0.2),
        IdentityTag(character="MARCUS", generation_id="SC01_g2", start_s=0.3,
                    end_s=2.6, anchor_x=0.7)]


def checks(**kw):
    args = dict(timeline=TIMELINE, in_frame=IN_FRAME,
                intros=[ROSA, ELENA, MARCUS], tags=TAGS)
    args.update(kw)
    return [(i.check, i.severity) for i in check_comprehension(**args)]


def test_film02_plan_with_tags_passes():
    assert checks() == []


def test_unintroduced_character_on_screen_blocks():
    assert ("IDENTITY_UNDECLARED", "BLOCK") in checks(intros=[ELENA, MARCUS])


def test_older_woman_without_any_carrier_blocks():
    # film02 defect: ROSA read as the mother, nothing said who she was
    assert ("FACT_UNCARRIED", "BLOCK") in checks(tags=TAGS[1:])


def test_dialogue_carrier_replaces_a_tag():
    rosa = ROSA.model_copy(update={"carriers": [Carrier(
        kind="DIALOGUE", generation_id="SC01_g1",
        detail="Aunt Rosa, she was your sister")]})
    assert checks(intros=[rosa, ELENA, MARCUS], tags=TAGS[1:]) == []


def test_fact_must_be_told_before_it_is_needed():
    late = StoryFact(fact_id="mother_dead", text="their mother has died",
                     needed_by="SC01_g1", carriers=[Carrier(
                         kind="DIALOGUE", generation_id="SC01_g2")])
    assert ("FACT_UNCARRIED", "BLOCK") in checks(facts=[late])
    card = late.model_copy(update={"carriers": [Carrier(
        kind="CARD", generation_id="SC01_g1")]})
    assert checks(facts=[card]) == []


def test_tag_on_a_shot_without_the_character_blocks():
    bad = TAGS[2].model_copy(update={"generation_id": "SC02_g1"})
    assert ("TAG_OFF_SCREEN", "BLOCK") in checks(tags=TAGS[:2] + [bad])


def test_tag_too_short_to_read_and_overlapping_tags_block():
    short = TAGS[0].model_copy(update={"end_s": 1.0})
    assert ("TAG_TOO_SHORT", "BLOCK") in checks(tags=[short, *TAGS[1:]])
    clash = TAGS[1].model_copy(update={"start_s": 2.0})
    assert ("TAG_OVERLAP", "BLOCK") in checks(tags=[TAGS[0], clash, TAGS[2]])


def test_tag_over_dialogue_is_a_warning():
    cue = SubtitleCue(generation_id="SC01_g1", start_s=2.5, end_s=4.0,
                      text="So she left the house to you.")
    assert checks(cues=[cue]) == [("TAG_OVER_DIALOGUE", "WARN")]


def test_card_reading_rules():
    ok = ContextCard(card_id="open", before="SC01_g1",
                     lines=["After their mother's funeral"])
    assert 2.0 <= ok.duration() <= 3.0
    assert checks(cards=[ok]) == []
    three = ok.model_copy(update={"lines": ["a", "b", "c"]})
    assert ("CARD_TOO_LONG", "BLOCK") in checks(cards=[three])
    wordy = ok.model_copy(update={"lines": [
        "Their mother died last week and left", "the family house to Elena"]})
    assert ("CARD_TOO_LONG", "BLOCK") in checks(cards=[wordy])
    held = ok.model_copy(update={"duration_s": 5.0})
    assert ("CARD_DURATION", "BLOCK") in checks(cards=[held])


def test_read_time_has_a_floor():
    assert read_time(["Later"]) == 2.0
    assert read_time(["After their mother's funeral"]) == 2.4


# ------------------------------------------------------ script stage

from pathlib import Path  # noqa: E402

from film_pipeline.drama import parse_fountain  # noqa: E402
from film_pipeline.drama.comprehension import kin_roots, lint_script  # noqa: E402

FILM02 = parse_fountain(Path("docs/drama/film02_spare_key.fountain")
                        .read_text(encoding="utf-8"))


def test_kin_words_fold_to_roots():
    assert kin_roots("Mom always liked you best.") == {"mother"}
    assert kin_roots("Your mother changed the locks.") == {"mother"}
    assert kin_roots("Keep it, Marcus.") == set()


def test_film02_script_as_first_written_is_blocked():
    # what the plan looked like before the Owner review: no intros, no facts
    found = {(i.check, i.detail.split()[0]) for i in lint_script(FILM02, [])}
    assert {("IDENTITY_UNDECLARED", "MARCUS"), ("IDENTITY_UNDECLARED", "ROSA"),
            ("IDENTITY_UNDECLARED", "ELENA")} <= found
    assert ("OFFSCREEN_PERSON", "MARCUS") in found      # "Mom ..."
    hint = next(i.detail for i in lint_script(FILM02, [])
                if "ROSA" in i.detail)
    assert "AUNT ROSA" in hint


def test_film02_script_with_intros_and_facts_passes():
    dead = StoryFact(fact_id="mother_dead", text="their mother has just died",
                     needed_by="SC01_g1")
    assert lint_script(FILM02, [ROSA, ELENA, MARCUS], [dead]) == []
    plain = ROSA.model_copy(update={"relation": "family friend"})
    assert [i.check for i in lint_script(FILM02, [plain, ELENA, MARCUS])] \
        == ["OFFSCREEN_PERSON"] * 2
