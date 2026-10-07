"""V2-021 — narrative compiler offline tests (no network)."""
from __future__ import annotations

import pytest

from film_pipeline.narrative import (
    CharacterBible, ContinuityEngine, DirectorCompiler, EditorialIntelligence,
    IdentityContinuityLedger, IdentityEvidence, LearningLoop,
    NarrativeCompiler, ReferenceStrategy, RepairPlanner, ShotTruth,
    StoryBeat,
    StoryGraph, WorldState, WorldStateGraph, align_narration,
    compile_prompt, parse_srt,
)

PROSE = (
    "A lone courier crosses a cold mountain pass, carrying a sealed "
    "letter for a village beyond. At the top of the pass she finds an "
    "abandoned traveler's pack beside the trail. She hesitates, afraid "
    "of what it might hold. She opens it and finds a second letter "
    "bearing her own name. She looks up: the pass is empty, only wind. "
    "She tucks the letter inside her coat and walks on, faster now."
)

CAST = [{"name": "The Courier",
         "desire": "deliver the sealed letter",
         "bible": {"age_band": "late 20s", "hair": "dark braid",
                   "body_build": "lean endurance",
                   "skin_tone": "wind-tanned",
                   "signature_wardrobe": "slate-blue hooded travel cloak, "
                                         "leather satchel",
                   "persistent_accessories": ["leather satchel"]}}]


@pytest.fixture(scope="module")
def compiled():
    compiler = NarrativeCompiler()
    return compiler.compile(source_text=PROSE, source_kind="prose",
                            cast=CAST,
                            world_facts={"location": "cold mountain pass"})


def test_beats_not_time_slices(compiled):
    functions = [e.function for e in compiled["events"]]
    assert functions[0] in ("ESTABLISH", "APPROACH")
    assert "DISCOVER" in functions
    assert "REVEAL" in functions
    assert functions[-1] in ("PAYOFF", "RESOLVE")
    # beats group consecutive same-function events; more than one beat and
    # each beat has a typed function
    assert len(compiled["beats"]) >= 4
    assert all(b.event_ids for b in compiled["beats"])


def test_every_event_answers_who_wants_change(compiled):
    for event in compiled["events"]:
        assert event.who, event.text
        assert event.wants
        assert event.what_changes
        assert event.audience_understands


def test_causality_and_reveals(compiled):
    relations = compiled["causality"]
    assert len(relations) == len(compiled["events"]) - 1
    assert any(r.relation == "causes" for r in relations)
    reveals = compiled["reveals"]
    assert len(reveals) == 1
    assert "name" in reveals[0].knowledge_change or \
        reveals[0].knowledge_change


def test_story_graph_traceability(compiled):
    graph = StoryGraph().build_from_compiled(
        compiled, cast=CAST, locations=["cold mountain pass"],
        objects=["abandoned pack", "second letter"])
    ids = [n.node_id for n in graph.nodes.values()]
    assert any(i.startswith("char_") for i in ids)
    assert any(i.startswith("loc_") for i in ids)
    assert graph.trace_shot(["ev_01", "char_the_courier"])
    assert not graph.trace_shot(["ev_99"])


def test_world_state_no_spontaneous_change():
    world = WorldState(location="mountain pass", weather="overcast",
                       architecture="none")
    graph = WorldStateGraph(world)
    changed = world.model_copy(update={"weather": "clear sky"})
    with pytest.raises(ValueError):
        graph.push_shot_state("shot_01", changed, justified_by_event="")


def test_world_state_delta_and_justified_change():
    world = WorldState(location="mountain pass", weather="overcast",
                       props_present=[])
    graph = WorldStateGraph(world)
    after = world.model_copy(update={
        "props_present": ["abandoned pack"], "held_objects": ["letter"]})
    transition = graph.push_shot_state("shot_02", after,
                                       justified_by_event="ev_02 discover")
    assert "props_present" in transition.delta
    assert graph.to_manifest()["states"][1]["shot"] == "shot_02"


def test_character_bible_identity_wardrobe_not_enough():
    bible = CharacterBible(
        character_id="courier", name="The Courier", age_band="late 20s",
        hair="dark braid", skin_tone="wind-tanned",
        signature_wardrobe="slate-blue hooded cloak",
        persistent_accessories=["leather satchel"])
    ledger = IdentityContinuityLedger(bible)
    # wardrobe matches but face not visible -> never PASS
    weak = ledger.evaluate(IdentityEvidence(
        shot_id="S01", framing="WIDE", face_visible=False,
        hard_constraints_observed=["slate-blue hooded cloak"]))
    assert weak.verdict == "WEAK"
    assert any("wardrobe" in v for v in weak.violations)
    # close framing without facial geometry check -> WEAK
    close = ledger.evaluate(IdentityEvidence(
        shot_id="S04", framing="MEDIUM_CLOSE", face_visible=True,
        hard_constraints_observed=["dark braid", "wind-tanned"]))
    assert close.verdict == "WEAK"
    # close + facial geometry checked -> PASS
    close.facial_geometry_checked = True
    ok = ledger.evaluate(close)
    assert ok.verdict == "PASS"
    assert len(bible.identity_fingerprint()) == 16


def test_director_min_shot_set_and_rhythm():
    compiler = NarrativeCompiler()
    compiled = compiler.compile(source_text=PROSE, cast=CAST)
    director = DirectorCompiler()
    graph, intents = director.design(
        compiled["beats"], world_state=WorldState(
            location="mountain pass", weather="overcast"), cast=CAST)
    assert 4 <= len(intents) <= 8
    # no decorative shot without classification
    for node in graph.nodes:
        assert node.story_node_ids or node.function in (
            "ATMOSPHERE", "RHYTHM", "TRANSITION")
    # rhythm: at most 2 consecutive same (size, movement)
    pairs = [(n.camera_intent["shot_size"], n.camera_intent["movement"])
             for n in graph.nodes]
    for i in range(2, len(pairs)):
        assert not (pairs[i] == pairs[i - 1] == pairs[i - 2]), pairs
    # edges typed and traceable
    assert all(e.kind for e in graph.edges)
    assert len(graph.edges) == len(graph.nodes) - 1


def test_prompt_compiler_structured_sections():
    truth = ShotTruth(
        subject="a lone female courier", wardrobe="slate-blue hooded cloak",
        world="cold overcast mountain pass, dark natural rock",
        blocking="she stops beside a fallen pack at frame left foreground",
        camera="medium shot, eye level, locked frame",
        motion="she kneels and reaches toward the pack",
        lighting="overcast diffuse, no hard shadows",
        environmental_causality=["wind presses the cloak against her"],
        continuity_anchors=["same cloak and satchel as the previous shot",
                            "travel continues left-to-right"],
        negative_constraints=["no text, no logos, no readable letters,",
                              "no other people, no weapons, no buildings."])
    plan = compile_prompt(truth, strategy=ReferenceStrategy())
    for section in ("subject", "world", "blocking", "camera", "motion",
                    "lighting", "continuity_anchors",
                    "negative_constraints"):
        assert plan.sections.get(section)
    assert plan.reference_strategy == "TEXT_ANCHOR_ONLY"
    assert len(plan.sha256) == 64
    assert "no readable letters" in plan.compiled_text
    # determinism
    assert plan.compiled_text == compile_prompt(
        truth, strategy=ReferenceStrategy()).compiled_text


def test_continuity_engine_false_failure_guards():
    engine = ContinuityEngine()
    # medium darker than wide: advisory metrics alone CANNOT fail a shot
    report = engine.evaluate_shot(
        shot_id="S02",
        technical={"decode_ok": True, "duration_s": 5.1, "height": 720,
                   "fps": 24.0, "black_frame_ratio": 0.0,
                   "freeze_frame_ratio": 0.0},
        evidence={
            "shot_local": {
                "IDENTITY": {"verdict": "PASS",
                             "evidence": "cloak+satchel+braid on keyframes"},
                "WORLD": {"verdict": "PASS",
                          "evidence": "same rock wall family"},
                "LIGHTING": {"verdict": "PASS",
                             "evidence": "overcast diffuse",
                             "metrics": {"mean_luma": 45.6}},
            }})
    assert report.verdict == "ACCEPT"
    # similar average color but wrong geography -> FAIL on WORLD
    bad = engine.evaluate_shot(
        shot_id="S03",
        technical={"decode_ok": True},
        evidence={"shot_local": {
            "WORLD": {"verdict": "FAIL",
                      "evidence": "red desert strata, not the pass",
                      "metrics": {"mean_luma": 90, "palette": "similar"}}},
            "cut": {"GEOGRAPHY": {"verdict": "FAIL",
                                  "evidence": "rock strata changed"}}})
    assert bad.verdict == "REPAIR_REQUIRED"
    assert bad.failure_class in ("PROMPT_REPAIRABLE",)


def test_repair_planner_minimal_delta():
    engine = ContinuityEngine()
    report = engine.evaluate_shot(
        shot_id="S05",
        technical={"decode_ok": True},
        evidence={"shot_local": {
            "SCREEN_DIRECTION": {"verdict": "FAIL",
                                 "evidence": "travel runs right-to-left"},
            "IDENTITY": {"verdict": "PASS", "evidence": "consistent"},
            "WORLD": {"verdict": "PASS", "evidence": "consistent"}}})
    truth = {"subject": "courier", "world": "pass", "screen_direction":
             "left-to-right"}
    plan = RepairPlanner().plan(report, truth)
    assert plan["changed_dimensions"] == {"screen_direction":
                                          "left-to-right"}
    assert "subject" in plan["accepted_truths_kept"]


def test_editorial_trim_before_regeneration():
    engine = ContinuityEngine()
    report = engine.evaluate_shot(
        shot_id="S06", technical={"decode_ok": True},
        evidence={"cut": {"MOTION": {"verdict": "FAIL",
                                     "evidence": "entrance mid-blink"}}})
    proposal = EditorialIntelligence().propose_trim(
        qc_report=report, junction_metrics={"tail_trim_frames": 6})
    assert proposal["regenerate"] is False
    assert 0 < proposal["trim_frames"] <= 12


def test_narration_alignment_not_one_to_one():
    srt = ("1\n00:00:00,000 --> 00:00:03,000\nShe crossed the pass.\n\n"
           "2\n00:00:03,000 --> 00:00:06,000\nThe letter burned in her "
           "satchel.\n\n"
           "3\n00:00:06,000 --> 00:00:09,000\nWind only.\n")
    beats = [StoryBeat(beat_id="b1", event_ids=["ev_01"],
                       function="APPROACH", summary="crossing"),
             StoryBeat(beat_id="b2", event_ids=["ev_02"],
                       function="REVEAL", summary="letter"),
             StoryBeat(beat_id="b3", event_ids=["ev_03"],
                       function="AFTERMATH", summary="wind")]
    shots = [{"shot_id": "S01"}, {"shot_id": "S02"}, {"shot_id": "S03"},
             {"shot_id": "S04"}]
    plan = align_narration(srt, beats, shots, total_duration_s=9.0)
    assert len(plan.segments) == 3
    covered = {sid for seg in plan.segments for sid in seg.shot_ids}
    assert covered <= {"S01", "S02", "S03", "S04"}
    assert plan.ambience_continuity is True


def test_srt_parser_deterministic():
    entries = parse_srt("1\n00:00:01,500 --> 00:00:02,500\nHello.\n")
    assert entries[0]["start_s"] == 1.5 and entries[0]["text"] == "Hello."


def test_learning_loop_promotion():
    loop = LearningLoop()
    first = loop.record("negative 'no text' prevents glyph artifacts",
                        domain="prompting")
    assert first.status == "OBSERVATION"
    loop.record("negative 'no text' prevents glyph artifacts",
                domain="prompting", evidence=["run2"])
    second = loop.learnings[0]
    assert second.status == "TENTATIVE_RULE"
    loop.record("negative 'no text' prevents glyph artifacts",
                domain="prompting", evidence=["run3"])
    assert loop.learnings[0].status == "PROVEN_RULE"
