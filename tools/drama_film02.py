"""film02 "The Spare Key" (WP7 benchmark): plan, storyboard, preflight.

Route from WP5: every generation is ONE 8 s shot rendered from a start frame
("Khung hình"). The start frame is a 0-credit Flow image built from the
location plate and the character stills, QC'd before any video credit.

Writes docs/drama/film02/: prompts/<gid>.txt (video), stills/<id>.txt (image
prompts), storyboard/ (schematic frames + gate), gate3_film02.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from film_pipeline.drama import (AxisBook, CharacterBrief,  # noqa: E402
                                 CharacterLook, ContinuityState,
                                 GenerationHandoff, LocationLook,
                                 SceneOccupancy, StoryboardGate, StoryTime,
                                 check_temporal, compile_scene_prompt,
                                 parse_fountain, preflight_scene,
                                 render_schematic_frame)
from film_pipeline.drama.axis import axis_record  # noqa: E402
from film_pipeline.drama.choreography import (  # noqa: E402
    GenerationChoreography, PerformanceCue, Phase)
from film_pipeline.drama.coverage import (_SIZE, CoverageShot,  # noqa: E402
                                          SceneTiming, SceneUnit)
from film_pipeline.drama.feasibility import (FeasibilityLimits,  # noqa: E402
                                             check_script)
from film_pipeline.drama.preflight import PreflightLimits  # noqa: E402
from film_pipeline.drama.comprehension import (  # noqa: E402
    check_comprehension, lint_script)
from drama_film02_story import (CARDS, FACTS, IN_FRAME,  # noqa: E402
                                INTROS, TAGS, TAKES_ORDER)

GEN_S = 8.0
OUT = Path("docs/drama/film02")
script = parse_fountain(Path("docs/drama/film02_spare_key.fountain")
                        .read_text(encoding="utf-8"))
SCENES = {s.scene_id: s for s in script.scenes}
FEAS = FeasibilityLimits(scene_duration_s=16.0, max_dialogue_syllables=28,
                         syllables_per_second=2.5)
LIMITS = PreflightLimits(
    # WP5 measured 165 words text-only; on the start-frame route the image
    # carries look and set, so WP7 measures adherence up to 215 words
    max_prompt_words=215,
    timing=SceneTiming(duration_s=GEN_S, max_shots=1, min_shot_s=2.0,
                       syllables_per_second=2.5),
    feasibility=FEAS)

LOOKS = {
    "ELENA": CharacterLook(
        look_id="elena_cardigan", character="ELENA",
        text="Latina woman, early forties, long dark ponytail, grey "
             "cardigan, white blouse",
        invariants=["long dark ponytail", "grey cardigan", "white blouse"],
        approved=True),
    "MARCUS": CharacterLook(
        look_id="marcus_leather", character="MARCUS",
        text="Latino man, late thirties, short black hair, stubble, brown "
             "leather jacket",
        invariants=["short black hair", "stubble", "brown leather jacket"],
        approved=True),
    "ROSA": CharacterLook(
        look_id="rosa_black_dress", character="ROSA",
        text="Latina woman, mid-sixties, silver bun, black dress, glasses "
             "on a chain",
        invariants=["silver bun", "black dress", "glasses on a chain"],
        approved=True),
}
VOICE = {"ELENA": "low steady female voice",
         "MARCUS": "smooth mocking male voice",
         "ROSA": "dry elderly female voice"}

ROOM = ("Old kitchen: yellow lamp over a wooden table, floral wallpaper, "
        "window over the sink on the right wall")
NIGHT = LocationLook(
    look_id="kitchen_night", location="MOTHER'S KITCHEN",
    text=f"{ROOM}, night, rain streaking the window glass outside",
    invariants=["yellow lamp over the table", "wooden table",
                "floral wallpaper", "window over the sink on the right"],
    interior=True, time_of_day="NIGHT", weather_outside="rain",
    environment_rules=["room dry, rain only outside the glass"],
    approved=True)
MORNING = LocationLook(
    look_id="kitchen_morning", location="MOTHER'S KITCHEN",
    text=f"{ROOM}, morning, warm sunlight through the window, no rain",
    invariants=NIGHT.invariants, interior=True, time_of_day="MORNING",
    approved=True)
LOCATION = {"SC01": NIGHT, "SC02": MORNING, "SC03": NIGHT}
ROOM_TONE = {"SC01": "soft rain on the window, refrigerator hum",
             "SC02": "birdsong outside, quiet kitchen",
             "SC03": "soft rain on the window, refrigerator hum"}

# Screen sides. Night: ROSA and ELENA hold the left (allies), MARCUS the
# right. Flashback: ROSA left, ELENA across the table on the right.
BOOK = {
    "SC01": AxisBook(scene_id="SC01", axis_pair=["ELENA", "MARCUS"],
                     sides={"ELENA": "LEFT", "ROSA": "LEFT",
                            "MARCUS": "RIGHT"}),
    "SC02": AxisBook.for_pair("SC02", "ROSA", "ELENA"),
    "SC03": AxisBook(scene_id="SC03", axis_pair=["ELENA", "MARCUS"],
                     sides={"ELENA": "LEFT", "ROSA": "LEFT",
                            "MARCUS": "RIGHT"}),
}

LOOKIDS = {k: v.look_id for k, v in LOOKS.items()}
POS_NIGHT = {"ROSA": "seated at the table, frame-left",
             "ELENA": "standing at the counter behind ROSA, frame-left",
             "MARCUS": "standing in the doorway, frame-right"}
POS_TABLE = dict(POS_NIGHT, MARCUS="standing at the table, frame-right")
POS_MORNING = {"ROSA": "seated at the table, frame-left",
               "ELENA": "seated across the table, frame-right"}
BRASS, IRON = "the brass key:", "the iron key:"


def state(pos, props, looks=None):
    return ContinuityState(positions=pos, props=props,
                           looks={c: LOOKIDS[c] for c in (looks or pos)})


STATE = {
    "SC01_g1": state(POS_NIGHT, {BRASS: "on a red ribbon, on the table"}),
    "SC01_g2": state(POS_TABLE, {BRASS: "on a red ribbon, on the table"}),
    "SC01_end": state(POS_TABLE, {BRASS: "in MARCUS's jacket pocket"}),
    "SC02_g1": state(POS_MORNING, {BRASS: "on a red ribbon, on the table",
                                   IRON: "in ROSA's hand"}),
    "SC02_g2": state(POS_MORNING, {BRASS: "on a red ribbon, on the table",
                                   IRON: "on the table in front of ELENA"}),
    "SC02_end": state(POS_MORNING, {BRASS: "on a red ribbon, on the table",
                                    IRON: "in ELENA's closed hand"}),
    "SC03_g1": state(POS_TABLE, {BRASS: "in MARCUS's jacket pocket"}),
    "SC03_g2": state(POS_TABLE, {BRASS: "in MARCUS's jacket pocket"}),
    "SC03_end": state(POS_TABLE, {BRASS: "in MARCUS's jacket pocket"}),
}
END = {"SC01_g1": "SC01_g2", "SC01_g2": "SC01_end", "SC02_g1": "SC02_g2",
       "SC02_g2": "SC02_end", "SC03_g1": "SC03_g2", "SC03_g2": "SC03_end"}

STORY = [StoryTime(scene_id="SC01", story_order=1),
         StoryTime(scene_id="SC02", story_order=0, transition_in="FLASHBACK",
                   marker='title card "That morning"; warm sunlight, no rain'),
         StoryTime(scene_id="SC03", story_order=2)]
OCCUPANCY = {"SC01": SceneOccupancy(scene_id="SC01",
                                    initial=["ROSA", "ELENA", "MARCUS"]),
             "SC02": SceneOccupancy(scene_id="SC02",
                                    initial=["ROSA", "ELENA"]),
             "SC03": SceneOccupancy(scene_id="SC03",
                                    initial=["ROSA", "ELENA", "MARCUS"])}


def cue(who, intent, cues, misread, intensity="restrained"):
    return PerformanceCue(character=who, emotion_intent=intent,
                          visible_cues=cues, intensity=intensity,
                          prohibited_misread=misread)


# one shot per generation: (coverage, subject, foreground, visible)
SHOTS = {
    "SC01_g1": ("MASTER", "", "", ["ROSA", "ELENA", "MARCUS"]),
    "SC01_g2": ("OTS", "MARCUS", "ELENA", ["ELENA", "MARCUS"]),
    "SC02_g1": ("MASTER", "", "", ["ROSA", "ELENA"]),
    "SC02_g2": ("OTS", "ELENA", "ROSA", ["ROSA", "ELENA"]),
    "SC03_g1": ("SINGLE", "ELENA", "", ["ELENA"]),
    "SC03_g2": ("MASTER", "", "", ["ROSA", "ELENA", "MARCUS"]),
}
CHOREO = {
    "SC01_g1": GenerationChoreography(
        generation_id="SC01_g1", phases=[
            Phase(kind="SETUP", start_s=0, end_s=2,
                  description="all three still, rain on the window"),
            Phase(kind="ACTION", start_s=2, end_s=6,
                  description="MARCUS speaks from the doorway"),
            Phase(kind="REACTION", start_s=6, end_s=8,
                  description="ELENA watches him, silent")],
        once_actions=["MARCUS speaks"],
        performance=[cue("MARCUS", "bitter resentment",
                         ["tight jaw", "flat stare"], "open shouting")]),
    "SC01_g2": GenerationChoreography(
        generation_id="SC01_g2", phases=[
            Phase(kind="ACTION", start_s=0, end_s=4,
                  description="MARCUS picks up the brass key and puts it "
                              "in his jacket pocket"),
            Phase(kind="ACTION", start_s=4, end_s=7,
                  description="he sneers at ELENA and speaks"),
            Phase(kind="HOLD", start_s=7, end_s=8,
                  description="he holds the sneer")],
        once_actions=["picks up the brass key", "puts it in his jacket "
                      "pocket"],
        performance=[cue("MARCUS", "contempt",
                         ["one corner of the mouth lifted", "narrowed eyes"],
                         "friendly smile or laugh", "moderate")]),
    "SC02_g1": GenerationChoreography(
        generation_id="SC02_g1", phases=[
            Phase(kind="ACTION", start_s=0, end_s=4,
                  description="ROSA slides the iron key across to ELENA"),
            Phase(kind="ACTION", start_s=4, end_s=7,
                  description="ROSA speaks, hands still"),
            Phase(kind="REACTION", start_s=7, end_s=8,
                  description="ELENA looks down at the key")],
        once_actions=["slides the iron key"],
        performance=[cue("ROSA", "quiet conspiracy",
                         ["lowered voice", "steady eyes"], "smile or wink")]),
    "SC02_g2": GenerationChoreography(
        generation_id="SC02_g2", phases=[
            Phase(kind="ACTION", start_s=0, end_s=3,
                  description="ELENA closes her fingers around the iron key"),
            Phase(kind="ACTION", start_s=3, end_s=6,
                  description="she nods once and speaks"),
            Phase(kind="HOLD", start_s=6, end_s=8,
                  description="she holds ROSA's gaze")],
        once_actions=["closes her fingers around the iron key", "nods once"],
        performance=[cue("ELENA", "resigned certainty",
                         ["small exhale", "level gaze"], "tears or a smile")]),
    "SC03_g1": GenerationChoreography(
        generation_id="SC03_g1", phases=[
            Phase(kind="SETUP", start_s=0, end_s=2,
                  description="ELENA looks at MARCUS, calm"),
            Phase(kind="ACTION", start_s=2, end_s=5,
                  description="ELENA speaks"),
            Phase(kind="HOLD", start_s=5, end_s=8,
                  description="she holds his gaze, still")],
        once_actions=["ELENA speaks"],
        performance=[cue("ELENA", "calm, almost kind",
                         ["steady gaze", "relaxed mouth"],
                         "smirk or anger")]),
    "SC03_g2": GenerationChoreography(
        generation_id="SC03_g2", phases=[
            Phase(kind="ACTION", start_s=0, end_s=4,
                  description="ROSA looks up at MARCUS and speaks"),
            Phase(kind="REACTION", start_s=4, end_s=7,
                  description="MARCUS's sneer fades; he glances at the "
                              "rainy window"),
            Phase(kind="HOLD", start_s=7, end_s=8,
                  description="nobody moves")],
        once_actions=["ROSA looks up"],
        performance=[cue("MARCUS", "deflation",
                         ["the lip curl drops", "eyes drift to the window"],
                         "fear or tears")]),
}
SFX = {"SC01_g2": ["small metal key clink"],
       "SC02_g1": ["iron key sliding on wood"]}


def lines_for(scene, gen):
    """Dialogue in script order: generation k speaks the k-th line."""
    from film_pipeline.drama.coverage import SpokenLine
    spoken = [SpokenLine(character=e.character, text=e.text,
                         syllables=e.syllables, line_no=e.line_no)
              for e in scene.elements if e.kind == "dialogue"]
    return spoken[gen - 1:gen]


def unit_for(gid):
    sid, gen = gid[:4], int(gid[-1])
    cov, subject, fg, visible = SHOTS[gid]
    book = BOOK[sid]
    shot = CoverageShot(
        shot_id=f"{sid}_S{gen}", coverage=cov, shot_size=_SIZE[cov],
        subject=subject, foreground=fg, start_s=0.0, end_s=GEN_S,
        lines=lines_for(SCENES[sid], gen),
        action=" ".join(p.description for p in CHOREO[gid].phases
                        if p.kind == "ACTION"),
        axis=axis_record(book, f"{sid}_S{gen}", visible))
    return SceneUnit(scene_id=sid, duration_s=GEN_S, shots=[shot],
                     axis_book=book)


def handoff_for(gid):
    sid, gen = gid[:4], int(gid[-1])
    if gen == 1 and sid != "SC03":
        return None
    prev = {"SC03_g1": "SC01_g2"}.get(gid, f"{sid}_g{gen - 1}")
    return GenerationHandoff(
        previous_generation_id=prev,
        previous_action=" ".join(p.description for p in CHOREO[prev].phases
                                 if p.kind == "ACTION"),
        # the part of the previous end this shot shows
        previous_start=STATE[prev], previous_end=cut(STATE[END[prev]], gid),
        end_state_verified=False)


def in_frame(gid):
    """Start state cut to the people the single shot shows."""
    return cut(STATE[gid], gid)


def cut(full, gid):
    visible = set(SHOTS[gid][3])
    return full.model_copy(update={
        "positions": {c: p for c, p in full.positions.items()
                      if c in visible},
        "looks": {c: v for c, v in full.looks.items() if c in visible}})


def build(gid, gate):
    sid = gid[:4]
    unit = unit_for(gid)
    start = in_frame(gid)
    cast = list(start.positions)
    plan = compile_scene_prompt(
        unit, characters=[CharacterBrief(name=c, look=LOOKS[c],
                                         voice=VOICE[c]) for c in cast],
        setting="", room_tone=ROOM_TONE[sid], sfx=SFX.get(gid),
        dialogue_language="English", start_state=start,
        location=LOCATION[sid], choreography=CHOREO[gid])
    report = preflight_scene(
        scene=SCENES[sid], unit=unit, prompt=plan, reference_sets=[],
        reference_root=Path("docs/drama/refs"), storyboard=gate,
        known_characters=script.characters, limits=LIMITS,
        reference_mode="TEXT_ONLY", looks=list(LOOKS.values()),
        generation_index=int(gid[-1]), handoff=handoff_for(gid),
        start_state=start, location=LOCATION[sid],
        occupancy=OCCUPANCY[sid], choreography=CHOREO[gid])
    return unit, plan, report


FRAMING = {"MASTER": "wide shot of the whole room",
           "OTS": "medium over-the-shoulder shot",
           "SINGLE": "medium close-up"}


def still_prompt(gid, unit):
    """Start-frame image: the shot's first instant, stills attached."""
    sid = gid[:4]
    shot = unit.shots[0]
    start = STATE[gid]
    shown = [c for c in start.positions
             if c in shot.axis.visible or shot.coverage == "MASTER"]
    people = "; ".join(f"{c} ({LOOKS[c].text}) {start.positions[c]}"
                       for c in shown)
    # a prop placed on someone out of frame would summon a stranger
    # (film02 SC03_g1: "the key in MARCUS's pocket" drew an unknown man)
    hidden = [c for c in LOOKS if c not in shown]
    props = "; ".join(f"{k.rstrip(':')} {v}" for k, v in start.props.items()
                      if not any(c in v for c in hidden))
    props = f" {props}." if props else ""
    alone = "" if len(shown) > 1 else f" Only {shown[0]} in frame."
    return (f"Photoreal film still, 16:9, {FRAMING[shot.coverage]}: "
            f"{shot.describe(unit.axis_book)}. {LOCATION[sid].text}. "
            f"{people}.{props}{alone} Faces and clothes exactly as in the "
            "attached character images. Natural, restrained expressions. "
            "No text, no logos.")


CHAR_STILL = ("Photoreal character reference portrait, 16:9, plain warm grey "
              "studio backdrop, head and shoulders, front view, neutral "
              "expression, soft even light: {text}. No text, no logos.")
PLATE = ("Photoreal empty set plate, 16:9, eye-level wide view, nobody in "
         "the room: {text}. No people, no text, no logos.")
# second plate of the same room: rendered with the first plate attached
RELIGHT = ("The exact room of the attached image: same layout, furniture, "
           "wallpaper, lamp and window positions, same camera. Only the time "
           "changes: {text}. Lamp off. Nobody in the room. No text, no logos.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    feas = check_script(script, limits=FEAS)
    temporal = check_temporal(
        STORY, {"SC01": STATE["SC01_end"], "SC02": STATE["SC02_end"]},
        {"SC02": STATE["SC02_g1"], "SC03": STATE["SC03_g1"]})
    gate = StoryboardGate(OUT / "storyboard")
    units = {gid: unit_for(gid) for gid in SHOTS}
    for gid, unit in units.items():
        shot = unit.shots[0]
        rel = f"{gid}.png"
        render_schematic_frame(unit, shot, OUT / "storyboard" / rel,
                               width=640)
        gate.register(unit.scene_id, shot.shot_id, rel)
        gate.review(shot.shot_id, status="APPROVED",
                    reviewer="Tech Lead (Owner-delegated)")
    gate.save()

    (OUT / "prompts").mkdir(exist_ok=True)
    (OUT / "stills").mkdir(exist_ok=True)
    for name, look in LOOKS.items():
        (OUT / "stills" / f"char_{name}.txt").write_text(
            CHAR_STILL.format(text=look.text) + "\n", encoding="utf-8")
    (OUT / "stills" / f"plate_{NIGHT.look_id}.txt").write_text(
        PLATE.format(text=NIGHT.text) + "\n", encoding="utf-8")
    (OUT / "stills" / f"plate_{MORNING.look_id}.txt").write_text(
        RELIGHT.format(text="morning, warm sunlight through the window, no "
                            "rain") + "\n", encoding="utf-8")

    record = {"feasibility": [i.model_dump() for i in feas.issues],
              "temporal": [i.model_dump() for i in temporal],
              "generations": {}}
    for gid in SHOTS:
        unit, plan, report = build(gid, gate)
        text = ("Starts on the given frame; same room, people and places. "
                + plan.compiled_text)
        (OUT / "prompts" / f"{gid}.txt").write_text(text + "\n",
                                                    encoding="utf-8")
        still = still_prompt(gid, unit)
        (OUT / "stills" / f"start_{gid}.txt").write_text(still + "\n",
                                                        encoding="utf-8")
        record["generations"][gid] = {
            "words": len(text.split()), "verdict": report.verdict,
            "still_words": len(still.split()),
            "issues": [i.model_dump() for i in report.issues]}
        print(gid, report.verdict, len(text.split()), "words",
              [f"{i.severity} {i.check}: {i.detail[:100]}"
               for i in report.issues])
    # what the viewer must know, before any credit (tags unplaced here)
    assert IN_FRAME == {g: SHOTS[g][3] for g in TAKES_ORDER}
    record["comprehension"] = [i.model_dump() for i in (
        lint_script(script, INTROS, FACTS) + check_comprehension(
            TAKES_ORDER, IN_FRAME, INTROS, FACTS, TAGS, CARDS))]
    print("comprehension", [f"{i['severity']} {i['check']}"
                            for i in record["comprehension"]])
    record["looks"] = {k: v.model_dump() for k, v in LOOKS.items()}
    record["locations"] = [NIGHT.model_dump(), MORNING.model_dump()]
    record["states"] = {k: v.model_dump() for k, v in STATE.items()}
    (OUT / "gate3_film02.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("feasibility", [i.detail for i in feas.issues])
    print("temporal", [i.detail for i in temporal])


if __name__ == "__main__":
    main()
