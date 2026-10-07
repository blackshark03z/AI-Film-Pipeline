"""V2-020 Phase 6 — frozen qualification fixture spec.

Three-shot micro-sequence in ONE consistent cold overcast mountain pass.
NON-PRODUCTION: this is system proof, not a film deliverable. SEQ7 is
untouched. Frozen: world, character, wardrobe, palette, travel direction,
camera grammar. One consistent adult traveler, no weapons, no architecture,
no text/logo.
"""
from __future__ import annotations

from film_pipeline.core import ContractModel


class ShotSpec(ContractModel):
    shot_id: str
    role: str                      # ARRIVAL / TRAVERSAL / SETTLE
    prompt: str
    needle: str                    # unique phrase for conversation discovery
    duration_class: int = 5
    camera: str
    screen_direction: str = "left-to-right"


class FixtureSpec(ContractModel):
    fixture_id: str
    title: str
    world: str
    character: str
    wardrobe: str
    palette: str
    travel_direction: str
    camera_grammar: str
    forbidden: list[str]
    shots: list[ShotSpec]


PROMPT_PREFIX = ("Generate a 5-second cinematic video, 16:9, "
                 "natural overcast daylight, muted cold grey-blue palette, "
                 "subtle constant wind moving grass and jacket fabric. ")
WORLD_BODY = (
    "A cold overcast mountain pass: continuous dark natural rock walls "
    "closing into a narrow walkable gap, low grey sky, patchy dry pale "
    "grass on rocky ground, no buildings, no gates, no signs, no other "
    "people. ")
CHARACTER_BODY = (
    "One adult traveler with short dark hair, wearing a dark olive "
    "weatherproof jacket, dark trousers, hiking boots and a small grey "
    "backpack. ")
NEGATIVE_TAIL = (
    " Natural realistic style, steady image quality, no text, no logos, "
    "no captions, no animals, no vehicles.")

FIXTURE = FixtureSpec(
    fixture_id="V2_020_MOUNTAIN_PASS_QUAL",
    title="Mountain Pass Qualification Micro-Sequence (NON-PRODUCTION)",
    world=WORLD_BODY,
    character=CHARACTER_BODY,
    wardrobe="dark olive jacket, dark trousers, hiking boots, grey backpack",
    palette="muted cold grey-blue overcast; dark natural rock; pale grass",
    travel_direction="the traveler moves LEFT to RIGHT in every shot",
    camera_grammar="A locked WIDE establish; B lateral MEDIUM tracking; "
                   "C locked WIDE settle",
    forbidden=["weapons", "architecture", "text", "logos", "animals",
               "vehicles", "other people"],
    shots=[
        ShotSpec(
            shot_id="QA_SHOT_A",
            role="ARRIVAL",
            prompt=PROMPT_PREFIX + WORLD_BODY + CHARACTER_BODY +
            "Locked wide establishing shot: the traveler enters from the "
            "left edge of frame and walks right toward the narrow pass "
            "gap, small in frame, steady natural walking pace, wind "
            "pressing the jacket." + NEGATIVE_TAIL,
            needle="enters from the left edge of frame and walks right",
            duration_class=5,
            camera="locked wide, static tripod, eye level",
        ),
        ShotSpec(
            shot_id="QA_SHOT_B",
            role="TRAVERSAL",
            prompt=PROMPT_PREFIX + WORLD_BODY + CHARACTER_BODY +
            "Lateral medium tracking shot at walking height, camera "
            "moving parallel on the traveler's right: the traveler walks "
            "briskly left to right across the frame over rocky ground "
            "beside the dark rock wall, jacket fabric rippling in the "
            "wind, face turned away in profile." + NEGATIVE_TAIL,
            needle="camera moving parallel on the traveler's right",
            duration_class=5,
            camera="lateral medium tracking, same direction as walk",
        ),
        ShotSpec(
            shot_id="QA_SHOT_C",
            role="SETTLE",
            prompt=PROMPT_PREFIX + WORLD_BODY + CHARACTER_BODY +
            "Locked wide static shot: the traveler arrives from the left, "
            "stops at a flat natural rock slab, turns and sits facing "
            "right, rests hands on knees, breath settling, jacket "
            "fluttering gently in the wind." + NEGATIVE_TAIL,
            needle="stops at a flat natural rock slab, turns and sits",
            duration_class=5,
            camera="locked wide, static tripod, eye level",
        ),
    ],
)
