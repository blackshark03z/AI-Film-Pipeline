"""film02 "The Spare Key": what the viewer must know (drama.comprehension).

Shared by the plan (tools/drama_film02.py, script-stage lint and plan
check) and the post (tools/drama_film02_post.py, tag placement and cards).
"""
from film_pipeline.drama.comprehension import (Carrier, CharacterIntro,
                                               ContextCard, IdentityTag,
                                               StoryFact)

TAKES_ORDER = ["SC01_g1", "SC01_g2", "SC02_g1", "SC02_g2", "SC03_g1",
               "SC03_g2"]
IN_FRAME = {"SC01_g1": ["ROSA", "ELENA", "MARCUS"],
            "SC01_g2": ["ELENA", "MARCUS"], "SC02_g1": ["ROSA", "ELENA"],
            "SC02_g2": ["ROSA", "ELENA"], "SC03_g1": ["ELENA"],
            "SC03_g2": ["ROSA", "ELENA", "MARCUS"]}
# film02 review: the older woman read as the mother, so "Your mother
# changed the locks" read as the mother talking about herself
INTROS = [
    CharacterIntro(character="ROSA", label="ROSA",
                   relation="their late mother's sister"),
    CharacterIntro(character="ELENA", label="ELENA",
                   relation="the elder daughter"),
    CharacterIntro(character="MARCUS", label="MARCUS",
                   relation="her younger brother"),
]
# Owner: everyone in the opening master is named there, one at a time.
# MARCUS's tag sits over his first line, so the speaker is named as he
# speaks. Anchors are left to tag_layout.auto_place (face + glare aware).
TAGS = [
    IdentityTag(character="ROSA", generation_id="SC01_g1", start_s=0.2,
                end_s=2.7),
    IdentityTag(character="MARCUS", generation_id="SC01_g1", start_s=2.7,
                end_s=4.9),
    IdentityTag(character="ELENA", generation_id="SC01_g1", start_s=5.0,
                end_s=7.2),
]
CARDS = [ContextCard(card_id="OPEN_card", before="SC01_g1",
                     lines=["After their mother's funeral"]),
         ContextCard(card_id="FLASHBACK_card", before="SC02_g1",
                     lines=["Earlier that morning"])]
FACTS = [
    StoryFact(fact_id="mother_dead", text="their mother has just died",
              needed_by="SC01_g1",
              carriers=[Carrier(kind="CARD", generation_id="SC01_g1")]),
    StoryFact(fact_id="flashback", text="SC02 happens before SC01",
              needed_by="SC02_g1",
              carriers=[Carrier(kind="CARD", generation_id="SC02_g1"),
                        Carrier(kind="VISUAL", generation_id="SC02_g1",
                                detail="sunlight, no rain, MARCUS absent")]),
    StoryFact(fact_id="back_to_night", text="SC03 continues SC01",
              needed_by="SC03_g1",
              carriers=[Carrier(kind="VISUAL", generation_id="SC03_g1",
                                detail="night lamp, rain on the glass")]),
    StoryFact(fact_id="brass_key_useless",
              text="the brass key MARCUS took opens nothing",
              needed_by="SC03_g2",
              carriers=[Carrier(kind="DIALOGUE", generation_id="SC02_g1",
                                detail="The brass one opens nothing.")]),
]
