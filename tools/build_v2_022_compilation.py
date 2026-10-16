"""V2-022 — 120-second mission: freeze + full compilation.

Compiles the 24-beat gardener-terrace narrative into the complete chain
(NarrativeGraph -> StoryGraph -> DirectorTreatment -> ShotGraph ->
structured PromptPlans -> mutation budget), exactly like the V2-021
fixture compile — provider-proven grammar, one character, one location,
left-to-right travel, no readable text, no buildings.

24 shots x 5s = 120.0 seconds. Deterministic; no network.

Budget: Owner-authorized cap 25 (24 planned + 1 repair reserve).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.narrative import (
    CharacterBible, DirectorCompiler, NarrativeCompiler, ReferenceStrategy,
    ShotTruth, StoryGraph, WorldState, WorldStateGraph, compile_prompt)

PKG = ROOT / "projects/quality_v2_022_longform_120s"

PROSE = (
    "We see a narrow terrace path winding along a cold hillside above a "
    "river valley. "
    "A lone gardener in a deep russet coat walks the path left to right, "
    "carrying a wooden crate of seedling jars. "
    "Near the first stone terrace he notices that one of the jars has "
    "cracked open. "
    "He pauses beside the low wall, uncertain whether the small seedling "
    "can survive the cold. "
    "He decides to carry the cracked jar to the old planting bed by the "
    "lower bend. "
    "He climbs along the wet stone steps toward the lower bend of the "
    "path. "
    "At the narrow turn he hesitates, wary of the slick mud at the edge. "
    "His breath fogs in the cold air as he stares at the long fall below "
    "the path. "
    "He commits to the crossing, stepping carefully onto the wide flat "
    "stones. "
    "Where the jar cracked, he realizes that a single pale seed has "
    "spilled onto his glove. "
    "He looks up at the grey sky and takes a slow breath. "
    "For a moment the hillside is empty and silent except for distant "
    "water. "
    "Farther down he finds an old planting bed cut into the lowest "
    "terrace. "
    "The soil is thin and poor, and he is uncertain the seedling will "
    "hold. "
    "He reaches into the crate and chooses the healthiest of the "
    "remaining jars. "
    "The strongest jar reveals a second seed pressed against the glass. "
    "He tucks the cracked jar into the soil and continues along the bed. "
    "The terraces around him are quiet, the valley gone soft with mist. "
    "At the far end he spots a young tree staked beside the path. "
    "He stares at the small tree and his shoulders tremble once. "
    "He decides to plant the cracked jar's seedling at the foot of the "
    "young tree. "
    "He presses the pale seed into the wet dark soil and walks on along "
    "the terrace. "
    "Above the far ridge the sky is empty of cloud except one narrow "
    "band of warm light. "
    "He walks on faster toward the lower valley, at last west."
)

CAST = [{
    "name": "The Gardener",
    "desire": "carry the seedlings down the terraces and plant what can "
              "still be saved before the cold returns",
    "bible": {
        "age_band": "late 40s",
        "face_geometry_family": "weathered square face, strong jaw, deep "
                                "lines from wind",
        "hair": "short grey-brown hair under a felt hat",
        "body_build": "sturdy compact working build",
        "skin_tone": "sun-roughened tan",
        "signature_wardrobe": "deep russet-red wool work coat over a dark "
                              "green wool sweater, brown felt work hat, "
                              "crosswise hemp shoulder satchel",
        "persistent_accessories": ["brown felt work hat",
                                   "leather work gloves"],
    },
}]

WORLD = WorldState(
    location="narrow terrace path on a cold hillside above a river "
             "valley: weathered dry-stone terrace walls of dark natural "
             "rock, wet dark soil path, pale winter grass, low grey "
             "clouds",
    time_of_day="cold morning", weather="clearing after rain, steady "
                                        "breeze",
    lighting="diffuse cold grey light, no hard shadows",
    terrain="wet stone and soil path descending across old fruit "
            "terraces",
    architecture="none", props_present=["wooden crate of seedling jars"],
    character_position="mid-descent", character_orientation="facing "
                                                           "right "
                                                           "(travel)",
    wardrobe_state="clean, damp from rain", damage_dirt="mud on boots "
                                                        "and hem",
    held_objects=["wooden crate of seedling jars"],
    camera_side_of_axis="north", screen_direction="left-to-right")

NEGATIVES = ["no text, no logos, no readable writing anywhere,",
             "no other people, no weapons, no buildings, no gates,",
             "no animals, no vehicles, no captions, no borders."]

# one unique motion per shot (S01..S24) aligned to the compiled beat
# order — uniqueness is REQUIRED: the motion section is the discovery
# needle (first 80 chars), and duplicate needles cross-match
MOTIONS = [
    "He crosses the frame left to right along the terrace path at a "
    "slow, steady pace, the wooden crate held against his chest.",
    "He keeps a steady walking rhythm along the wet path, both gloved "
    "hands gripping the crate, coat hems moving with the breeze.",
    "He slows to a stop beside the first stone terrace edge and tilts "
    "the crate toward himself, examining the cracked jar.",
    "He stands still beside the low stone wall, head lowered toward "
    "the cracked jar, shoulders tense, unwilling to move on.",
    "He settles the crate more securely in his arms and resumes "
    "walking toward the lower bend of the path.",
    "He climbs the wet stone steps of the lower path one by one, "
    "keeping the crate level as his coat swings.",
    "He pauses at the narrow turn of the path, looking down at the "
    "slick dark mud at the edge, hesitant to step.",
    "He stands motionless at the edge and lifts his head slowly, "
    "breath visible, scanning the long drop to the river.",
    "He steps deliberately onto the wide flat stones, crossing the "
    "slick stretch with small careful strides.",
    "He holds the cracked jar close above his open glove and gazes at "
    "a single pale seed, his face in profile.",
    "His head tilts back toward the grey sky and he takes one long "
    "slow breath, jaw set.",
    "He stands small against the wide empty hillside, still as the "
    "mist drifts behind the terraces.",
    "He kneels at the lowest terrace bed, setting the crate down and "
    "looking over the thin dark soil before him.",
    "He hovers over the poor thin soil, one gloved hand pressed flat "
    "on the ground, unwilling to commit.",
    "He reaches deep into the crate and lifts the healthiest seedling "
    "jar out with both hands.",
    "He raises the strongest jar to eye level in profile and turns it "
    "slowly, showing a second seed pressed against the glass.",
    "He tucks the cracked jar into the soft soil at the bed's edge "
    "and smooths the earth around it with his glove.",
    "He straightens slowly and stands looking down at the planted "
    "jar, quiet and still as the valley softens with mist.",
    "He turns and spots the young staked tree at the far end of the "
    "terrace, its thin branches bare.",
    "He stares at the young tree from a distance, and one long shiver "
    "moves through his shoulders.",
    "He carries the crate to the foot of the young tree and kneels "
    "beside its stake, leaning over the dark soil.",
    "He presses the pale seed gently into the wet dark soil at the "
    "tree's base and pats the earth firm with his palm.",
    "He stands upright beside the young tree, tiny in the vast "
    "terraced hillside, hands empty at his sides.",
    "He shoulders the wooden crate and strides away left to right "
    "along the lower path, quicker now, toward the valley, at last.",
]


def truth_for(shot: dict, index: int, character: CharacterBible) -> ShotTruth:
    size = shot["camera_intent"]["shot_size"]
    subject_by_size = {
        "WIDE": "a lone male gardener seen at distance, small in frame",
        "EXTREME_WIDE": "a lone male gardener, tiny against the hillside",
        "MEDIUM": "a lone male gardener from the waist up",
        "MEDIUM_CLOSE": "the male gardener in profile from the shoulders "
                        "up, face partly turned from camera",
    }
    camera_by_size = {
        "WIDE": "Wide establishing shot, locked static frame, eye level.",
        "EXTREME_WIDE": "Extreme wide shot, locked static frame, eye "
                        "level.",
        "MEDIUM": "Medium shot, locked frame, eye level.",
        "MEDIUM_CLOSE": "Medium-close profile shot, locked frame, eye "
                        "level.",
    }
    anchors = [
        "The gardener wears the same deep russet-red wool work coat, "
        "felt hat and crosswise hemp satchel throughout.",
        "Travel direction stays left-to-right across the whole sequence.",
        "The same cold terraced hillside with dark dry-stone walls and "
        "a wet soil path continues.",
    ]
    causality = ["a steady breeze moves his coat fabric and the pale "
                 "winter grass throughout the shot"]
    state_label = shot["character_state"].get("The Gardener", "")
    blocking = state_label if len(state_label) > 40 else ""
    return ShotTruth(
        subject=subject_by_size.get(size, subject_by_size["MEDIUM"]),
        wardrobe=character.signature_wardrobe,
        world=WORLD.location,
        blocking=blocking,
        camera=camera_by_size.get(size, camera_by_size["MEDIUM"]),
        motion=MOTIONS[index],
        lighting=WORLD.lighting,
        environmental_causality=causality,
        continuity_anchors=anchors,
        negative_constraints=list(NEGATIVES))


def main() -> int:
    compiler = NarrativeCompiler()
    compiled = compiler.compile(source_text=PROSE, source_kind="prose",
                                cast=CAST,
                                world_facts={"location": WORLD.location})
    bible = CharacterBible(character_id="gardener", name="The Gardener",
                           **CAST[0]["bible"])
    story_graph = StoryGraph().build_from_compiled(
        compiled, cast=CAST, locations=["terraced hillside path"],
        objects=["wooden crate of seedling jars", "cracked jar",
                 "single pale seed", "young staked tree"])

    director = DirectorCompiler(screen_direction="left-to-right",
                                light_direction=WORLD.lighting)
    shot_graph, intents = director.design(
        compiled["beats"], world_state=WORLD, cast=CAST)

    n_shots = len(shot_graph.nodes)
    if n_shots != 24:
        raise SystemExit(
            f"compilation drift: expected exactly 24 shots (120s), got "
            f"{n_shots}; adjust PROSE (adjacent sentences must not share "
            f"a function class)")

    strategy = ReferenceStrategy(supports_video_ref=False,
                                 mode="TEXT_ANCHOR_ONLY",
                                 lineage=["character bible fingerprint "
                                          + bible.identity_fingerprint()])
    plans = {}
    for index, node in enumerate(shot_graph.nodes):
        truth = truth_for(node.model_dump(), index, bible)
        plans[node.shot_id] = compile_prompt(
            truth, strategy=strategy).model_dump()

    needles = [p["sections"]["motion"][:80] for p in plans.values()]
    if len(set(needles)) != n_shots:
        raise SystemExit("needle collision: MOTIONS entries must be "
                         "unique in their first 80 chars")

    # world state graph: one explicit state per shot (props evolve only
    # where the story changes them)
    world_graph = WorldStateGraph(WORLD)
    for node in shot_graph.nodes:
        props = list(WORLD.props_present)
        held = list(WORLD.held_objects)
        position = WORLD.character_position
        if node.function == "PRESSURE":
            position = "stopped at the terrace wall"
        elif node.function == "REACTION":
            position = "still, at the path edge"
        elif node.function == "DECISION":
            held = ["healthiest seedling jar"]
            position = "kneeling at the planting bed"
        elif node.function == "REVEAL":
            held = ["opened cracked jar"]
            position = "holding the jar at eye level"
        elif node.function == "PAYOFF":
            props = props + ["cracked jar planted in the soil"]
            held = []
            position = "standing at the planting bed"
        elif node.function == "AFTERMATH":
            position = "small against the open hillside"
        elif node.function == "RESOLVE":
            props = []
            held = ["empty wooden crate"]
            position = "walking out, quicker pace"
        state = WORLD.model_copy(update={
            "props_present": props, "held_objects": held,
            "character_position": position})
        world_graph.push_shot_state(
            node.shot_id, state,
            justified_by_event=node.story_node_ids[0])

    # mutation budget — Owner-authorized cap 25 (24 + 1 repair reserve)
    budget = {
        "version": "v2-022-mutation-budget-v1",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "planned_shots": n_shots,
        "base_mutations": n_shots,
        "repair_reserve": 1,
        "total_budget": n_shots + 1,
        "rationale": "120-second mission, 24 shots x 5s; Owner-authorized "
                     "cap 25 = 24 planned + 1 repair reserve; the daily "
                     "pool quota feeds the mission across multiple days",
        "rule": "design-then-spend; no exploratory prompt debugging; "
                "STOP BEFORE FIRST MUTATION if the authorized cap cannot "
                "cover this budget",
        "required_credit_floor": n_shots,
    }
    if budget["total_budget"] != 25:
        raise SystemExit("budget drift: Owner authorization is cap 25")

    doc = {
        "version": "v2-022-longform-compilation-v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "input": {"source_kind": "prose", "text": PROSE,
                  "estimated_scene_seconds": "120"},
        "narrative": {
            "events": [e.model_dump() for e in compiled["events"]],
            "beats": [b.model_dump() for b in compiled["beats"]],
            "causality": [c.model_dump() for c in compiled["causality"]],
            "reveals": [r.model_dump() for r in compiled["reveals"]],
            "objectives": [o.model_dump() for o in compiled["objectives"]],
            "transitions": [t.model_dump() for t in
                            compiled["transitions"]],
        },
        "story_graph": story_graph.to_manifest(),
        "character_bible": bible.model_dump(),
        "world_state_graph": world_graph.to_manifest(),
        "shot_graph": shot_graph.to_manifest(),
        "prompt_plans": plans,
        "reference_strategy": strategy.model_dump(),
        "mutation_budget": budget,
    }
    dst = PKG / "V2_022_LONGFORM_COMPILATION.json"
    dst.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({
        "saved": str(dst),
        "events": len(compiled["events"]),
        "beats": len(compiled["beats"]),
        "shots": n_shots,
        "seconds": n_shots * 5,
        "functions": [n.function for n in shot_graph.nodes],
        "budget": budget["total_budget"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
