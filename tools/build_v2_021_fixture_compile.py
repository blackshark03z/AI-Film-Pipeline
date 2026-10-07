"""V2-021 — fixture freeze + full compilation evidence.

Compiles the frozen courier-pass narrative into the complete chain:
NarrativeGraph -> StoryGraph -> DirectorTreatment -> ShotGraph ->
structured PromptPlans -> mutation budget. Deterministic; no network.
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

PKG = ROOT / "projects/quality_v2_021_narrative_compiler"

PROSE = (
    "A lone courier crosses a cold mountain pass, carrying a sealed "
    "letter for a village beyond the ridge. At the top of the pass she "
    "finds an abandoned traveler's pack beside the trail. She "
    "hesitates, afraid of what it might hold. She opens it and finds a "
    "second letter bearing her own name. She looks up: the pass is "
    "empty, only wind. She tucks the letter inside her coat and walks "
    "on, faster now."
)

CAST = [{
    "name": "The Courier",
    "desire": "deliver the sealed letter and get through the pass",
    "bible": {
        "age_band": "late 20s",
        "face_geometry_family": "angular wind-worn features, high "
                                "cheekbones",
        "hair": "dark hair in a low braid",
        "body_build": "lean endurance build",
        "skin_tone": "wind-tanned fair",
        "signature_wardrobe": "slate-blue hooded travel cloak over dark "
                              "wool layers, worn leather satchel "
                              "crosswise",
        "persistent_accessories": ["leather satchel", "worn gloves"],
    },
}]

WORLD = WorldState(
    location="cold overcast mountain pass: continuous dark natural rock "
             "walls, narrow walkable gap, patchy pale grass on rocky "
             "ground, low grey sky",
    time_of_day="late afternoon", weather="overcast, constant wind",
    lighting="diffuse cold grey, no hard shadows",
    terrain="rocky trail through a natural gap",
    architecture="none", props_present=["sealed letter in satchel"],
    character_position="mid-crossing", character_orientation="facing "
                                                             "right (travel)",
    wardrobe_state="clean, wind-pressed", damage_dirt="light trail dust",
    held_objects=[], camera_side_of_axis="north", screen_direction=
    "left-to-right")

NEGATIVES = ["no text, no logos, no readable letters anywhere,",
             "no other people, no weapons, no buildings, no gates,",
             "no animals, no vehicles, no captions."]


def truth_for(shot: dict, character: CharacterBible) -> ShotTruth:
    size = shot["camera_intent"]["shot_size"]
    movement = shot["camera_intent"]["movement"]
    subject_by_size = {
        "WIDE": "a lone female courier seen at distance, small in frame",
        "EXTREME_WIDE": "a lone female courier, tiny against the pass",
        "MEDIUM": "a lone female courier from the waist up",
        "MEDIUM_CLOSE": "the female courier in profile from the shoulders "
                        "up, face partially turned away",
    }
    camera_by_size = {
        "WIDE": "Wide establishing shot, locked static frame, eye level.",
        "EXTREME_WIDE": "Extreme wide shot, locked static frame, eye "
                        "level.",
        "MEDIUM": "Medium shot, locked frame, eye level.",
        "MEDIUM_CLOSE": "Medium-close profile shot, locked frame, eye "
                        "level.",
    }
    motion_by_function = {
        "ESTABLISH": "She crosses the frame left to right at a steady, "
                     "tired walking pace, cloak pressed by the wind.",
        "DISCOVER": "She decelerates to a stop, her gaze dropping toward "
                    "a fallen dark leather pack half-hidden at the foot "
                    "of the rocks.",
        "PRESSURE": "She stands motionless beside the pack, breath "
                    "visible, gloved hands tense, afraid to touch it.",
        "REVEAL": "She holds an opened folded letter in both gloved "
                  "hands, an aged blank sheet with a dark wax seal, and "
                  "her face turns slowly toward it in profile.",
        "REVEAL_AFTERMATH": "She holds an opened folded letter in both "
                            "gloved hands, an aged blank sheet with a "
                            "dark wax seal, then slowly lifts her gaze "
                            "from the letter to scan the entirely empty "
                            "mountain pass, only wind moving the grass.",
        "AFTERMATH": "She stands frozen, head lifting slowly from the "
                     "letter to scan the entirely empty pass.",
        "RESOLVE": "She slips the letter inside her cloak and strides "
                   "away left to right, exiting the frame at a clearly "
                   "quicker pace.",
    }
    anchors = [
        "The traveler wears the same slate-blue hooded cloak, dark wool "
        "layers and crosswise leather satchel throughout.",
        "Travel direction stays left-to-right across the whole sequence.",
        "The same cold overcast mountain pass with dark natural rock "
        "walls and pale grass continues.",
    ]
    causality = ["constant wind moves the cloak fabric and the pale "
                 "grass throughout the shot"]
    state_label = shot["character_state"].get("The Courier", "")
    blocking = state_label if len(state_label) > 40 else ""
    return ShotTruth(
        subject=subject_by_size.get(size, subject_by_size["MEDIUM"]),
        wardrobe=character.signature_wardrobe,
        world=WORLD.location,
        blocking=blocking,
        camera=camera_by_size.get(size, camera_by_size["MEDIUM"]),
        motion=motion_by_function.get(shot["function"], "steady movement"),
        lighting=WORLD.lighting,
        environmental_causality=causality,
        continuity_anchors=anchors,
        negative_constraints=list(NEGATIVES))


def main() -> int:
    variant = sys.argv[1] if len(sys.argv) > 1 else "6"
    compiler = NarrativeCompiler()
    compiled = compiler.compile(source_text=PROSE, source_kind="prose",
                                cast=CAST,
                                world_facts={"location": WORLD.location})
    bible = CharacterBible(character_id="courier", name="The Courier",
                           **CAST[0]["bible"])
    story_graph = StoryGraph().build_from_compiled(
        compiled, cast=CAST, locations=["cold mountain pass"],
        objects=["abandoned pack", "second letter bearing her name"])

    beats = compiled["beats"]
    if variant == "5":
        # minimum-set variant: AFTERMATH folds into the REVEAL shot as
        # one continuous camera action (letter -> lifting gaze to the
        # empty pass); story information is unchanged
        merged = []
        for beat in beats:
            if beat.function == "AFTERMATH" and merged and                     merged[-1].function == "REVEAL":
                merged[-1].event_ids.extend(beat.event_ids)
                merged[-1].summary = (merged[-1].summary +
                                      "; " + beat.summary)[:220]
                continue
            merged.append(beat)
        beats = merged
        for beat in beats:
            if beat.function == "REVEAL" and len(beat.event_ids) == 2:
                beat.function = "REVEAL"  # grammar key stays; motion
                # override happens in truth_for via event count
    director = DirectorCompiler(screen_direction="left-to-right",
                                light_direction=WORLD.lighting)
    shot_graph, intents = director.design(
        beats, world_state=WORLD, cast=CAST)

    strategy = ReferenceStrategy(supports_video_ref=False,
                                 mode="TEXT_ANCHOR_ONLY",
                                 lineage=["character bible fingerprint "
                                          + bible.identity_fingerprint()])
    plans = {}
    for node in shot_graph.nodes:
        node_dict = node.model_dump()
        if variant == "5" and node.function == "REVEAL" and                 len(node.story_node_ids) == 2:
            node_dict["function"] = "REVEAL_AFTERMATH"
        truth = truth_for(node_dict, bible)
        plans[node.shot_id] = compile_prompt(
            truth, strategy=strategy).model_dump()

    # world state graph: one explicit state per shot (props evolve only
    # when the story changes them)
    world_graph = WorldStateGraph(WORLD)
    for node in shot_graph.nodes:
        props = list(WORLD.props_present)
        held = list(WORLD.held_objects)
        position = WORLD.character_position
        if node.function == "DISCOVER":
            props = props + ["abandoned pack at the trailside"]
        if node.function == "REVEAL":
            props = props + ["second letter bearing her name"]
            held = ["opened second letter"]
            position = "stopped at the pack"
        if node.function == "RESOLVE":
            held = []
            props = [p for p in props
                     if p != "sealed letter in satchel"] + \
                ["both letters inside the cloak"]
            position = "walking out, quicker pace"
        state = WORLD.model_copy(update={
            "props_present": props, "held_objects": held,
            "character_position": position})
        world_graph.push_shot_state(
            node.shot_id, state,
            justified_by_event=node.story_node_ids[0])

    # mutation budget (computed BEFORE any dispatch)
    n_shots = len(shot_graph.nodes)
    budget = {
        "version": "v2-021-mutation-budget-v1",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "planned_shots": n_shots,
        "base_mutations": n_shots,
        "repair_reserve": 2 if n_shots >= 6 else 1,
        "total_budget": n_shots + (2 if n_shots >= 6 else 1),
        "rationale": "6-shot full grammar carries 2 reserves; the "
                     "5-shot minimum set halves continuity exposure "
                     "and runs with 1 reserve",
        "rule": "design-then-spend; no exploratory prompt debugging; "
                "STOP BEFORE FIRST MUTATION if the known authorized pool "
                "cannot cover this budget",
        "required_credit_floor": n_shots,
    }

    doc = {
        "version": "v2-021-fixture-compilation-v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "input": {"source_kind": "prose", "text": PROSE,
                  "estimated_scene_seconds": "30-60"},
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
    dst = PKG / ("V2_021_FIXTURE_COMPILATION.json" if variant == "6"
                 else "V2_021_FIXTURE_COMPILATION_5SHOT.json")
    dst.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({
        "saved": str(dst),
        "events": len(compiled["events"]),
        "beats": len(compiled["beats"]),
        "shots": n_shots,
        "functions": [n.function for n in shot_graph.nodes],
        "budget": budget["total_budget"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
