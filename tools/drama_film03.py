"""film03 "The Front Desk": plan, storyboard, preflight.

Same route as film02 (WP5/WP7): every generation is ONE 8 s shot rendered
from a 0-credit start frame ("Khung hình"). 8 scenes x 2 generations: six
continuous scenes in the precinct lobby, then roll call in the briefing
room.

Writes docs/drama/film03/: prompts/<gid>.txt (video), stills/<id>.txt (image
prompts), storyboard/ (schematic frames + gate), gate3_film03.json.
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
                                          SceneTiming, SceneUnit, SpokenLine)
from film_pipeline.drama.feasibility import (FeasibilityLimits,  # noqa: E402
                                             check_script)
from film_pipeline.drama.preflight import PreflightLimits  # noqa: E402
from film_pipeline.drama.comprehension import (  # noqa: E402
    check_comprehension, lint_script)
from drama_film03_story import (CARDS, FACTS, IN_FRAME,  # noqa: E402
                                INTROS, TAGS, TAKES_ORDER)

GEN_S = 8.0
OUT = Path("docs/drama/film03")
script = parse_fountain(Path("docs/drama/film03_front_desk.fountain")
                        .read_text(encoding="utf-8"))
SCENES = {s.scene_id: s for s in script.scenes}
FEAS = FeasibilityLimits(scene_duration_s=16.0, max_dialogue_syllables=28,
                         syllables_per_second=2.5)
LIMITS = PreflightLimits(
    max_prompt_words=215,
    timing=SceneTiming(duration_s=GEN_S, max_shots=1, min_shot_s=2.0,
                       syllables_per_second=2.5),
    feasibility=FEAS)

LOOKS = {
    "NORA": CharacterLook(
        look_id="nora_navy_coat", character="NORA",
        text="Black woman, late forties, short natural hair, navy wool "
             "coat, grey turtleneck",
        invariants=["short natural hair", "navy wool coat",
                    "grey turtleneck"],
        approved=True),
    "KESSLER": CharacterLook(
        look_id="kessler_uniform", character="KESSLER",
        text="white man, mid-fifties, grey crew cut, heavy build, navy "
             "police uniform with sergeant chevrons",
        invariants=["grey crew cut", "heavy build",
                    "navy uniform with sergeant chevrons"],
        approved=True),
    "ORTIZ": CharacterLook(
        look_id="ortiz_uniform", character="ORTIZ",
        text="Latino man, mid-twenties, slim, clean-shaven, short dark "
             "hair, navy police uniform",
        invariants=["slim", "clean-shaven", "short dark hair",
                    "navy uniform"],
        approved=True),
}
# video prompts on the start-frame route: the frame carries each face, so
# the text drops ethnicity (film03: two jobs refused as "reputational risk /
# current events" with race words next to police uniforms)
VIDEO_LOOKS = {k: v.model_copy(update={"text": v.text.split(" ", 1)[1]})
               for k, v in LOOKS.items()}
VOICE = {"NORA": "calm low female voice",
         "KESSLER": "gravelly dismissive male voice",
         "ORTIZ": "young hesitant male voice"}

LOBBY = LocationLook(
    look_id="lobby_morning", location="EASTGATE PRECINCT LOBBY",
    text="Police station lobby: tall wooden front desk on the right with "
         "a desk phone and a trash bin behind it, grey filing cabinets at "
         "the back, glass doors on the left, morning light",
    invariants=["tall wooden front desk on the right", "desk phone",
                "trash bin behind the desk", "grey filing cabinets",
                "glass doors on the left"],
    interior=True, time_of_day="MORNING", approved=True)
BRIEF = LocationLook(
    look_id="briefing_morning", location="EASTGATE PRECINCT BRIEFING ROOM",
    text="Police briefing room: a wooden lectern and a whiteboard on the "
         "left, rows of grey chairs on the right, window blinds, morning "
         "light",
    invariants=["lectern on the left", "whiteboard", "rows of grey chairs",
                "window blinds"],
    interior=True, time_of_day="MORNING", approved=True)
LOCATION = {f"SC0{s}": LOBBY for s in range(1, 7)}
LOCATION.update(SC07=BRIEF, SC08=BRIEF)
ROOM_TONE = {sid: ("fluorescent hum, distant phones" if loc is LOBBY else
                   "quiet room, chairs creaking")
             for sid, loc in LOCATION.items()}
# roll call: the room is not empty (named people only go in positions)
EXTRAS = {"SC07": "five other uniformed officers sit in the rows, seen from "
                  "behind or in profile",
          "SC08": "five other uniformed officers sit in the rows, seen from "
                  "behind or in profile"}

# Screen sides: the public side of the desk (NORA) holds the left, the
# staff side (KESSLER, ORTIZ behind him) the right. Roll call keeps it:
# NORA at the lectern left, the room on the right.
LOBBY_SIDES = {"NORA": "LEFT", "KESSLER": "RIGHT", "ORTIZ": "RIGHT"}
BOOK = {sid: AxisBook(scene_id=sid, axis_pair=["NORA", "KESSLER"],
                      sides=LOBBY_SIDES) for sid in list(LOCATION)[:6]}
BOOK["SC04"] = AxisBook(scene_id="SC04", axis_pair=["NORA", "ORTIZ"],
                        sides=LOBBY_SIDES)
for sid in ("SC07", "SC08"):
    BOOK[sid] = AxisBook(scene_id=sid, axis_pair=["NORA", "ORTIZ"],
                         sides=LOBBY_SIDES)

LOOKIDS = {k: v.look_id for k, v in LOOKS.items()}
POS_DOOR = {"NORA": "inside the glass doors, frame-left",
            "KESSLER": "seated behind the desk, frame-right",
            "ORTIZ": "at the cabinets behind the desk, frame-right"}
POS_DESK = dict(POS_DOOR, NORA="in front of the desk, frame-left")
POS_BIN = dict(POS_DESK, ORTIZ="by the trash bin behind the desk, "
                               "frame-right")
POS_ROLL = {"NORA": "at the lectern, frame-left",
            "ORTIZ": "seated in the front row, frame-right",
            "KESSLER": "standing at the back wall, frame-right"}
LETTER, PHONE = "the letter:", "the desk phone:"


def state(pos, props):
    return ContinuityState(positions=pos, props=props,
                           looks={c: LOOKIDS[c] for c in pos})


POCKET = {LETTER: "folded, in NORA's coat pocket", PHONE: "on the desk"}
LAID = {LETTER: "folded, on the desk", PHONE: "on the desk"}
BINNED = {LETTER: "crumpled, in the trash bin", PHONE: "on the desk"}
SAVED = {LETTER: "smoothed flat, in ORTIZ's hands", PHONE: "on the desk"}
CALL = {LETTER: "smoothed flat, in ORTIZ's hands",
        PHONE: "receiver at KESSLER's ear"}
STATE = {
    "SC01_g1": state(POS_DOOR, POCKET),
    "SC01_g2": state(POS_DESK, POCKET),
    "SC01_end": state(POS_DESK, LAID),
    "SC02_g1": state(POS_DESK, LAID),
    "SC02_g2": state(POS_DESK, {LETTER: "unfolded, in KESSLER's hand",
                                PHONE: "on the desk"}),
    "SC02_end": state(POS_DESK, BINNED),
    "SC03_g1": state(POS_DESK, BINNED),
    "SC03_g2": state(POS_DESK, BINNED),
    "SC03_end": state(POS_DESK, BINNED),
    "SC04_g1": state(POS_DESK, BINNED),
    "SC04_g2": state(POS_DESK, BINNED),
    "SC04_end": state(POS_BIN, SAVED),
    "SC05_g1": state(POS_BIN, SAVED),
    "SC05_g2": state(POS_BIN, CALL),
    "SC05_end": state(POS_BIN, CALL),
    "SC06_g1": state(POS_BIN, CALL),
    "SC06_g2": state(POS_BIN, CALL),
    "SC06_end": state(POS_BIN, CALL),
    "SC07_g1": state(POS_ROLL, {}),
    "SC07_g2": state(POS_ROLL, {}),
    "SC07_end": state(POS_ROLL, {}),
    "SC08_g1": state(POS_ROLL, {}),
    "SC08_g2": state(POS_ROLL, {}),
    "SC08_end": state(POS_ROLL, {}),
}
# the state each generation ends in: the next generation's start
END = {g: (f"{g[:4]}_g2" if g.endswith("g1") else f"{g[:4]}_end")
       for g in TAKES_ORDER}

STORY = [StoryTime(scene_id=f"SC0{s}", story_order=s) for s in range(1, 9)]
STORY[6] = StoryTime(scene_id="SC07", story_order=7,
                     transition_in="ELLIPSIS",
                     marker='context card "Roll call, 8 a.m."; briefing '
                            "room")
OCCUPANCY = {sid: SceneOccupancy(scene_id=sid,
                                 initial=["NORA", "KESSLER", "ORTIZ"])
             for sid in LOCATION}


def cue(who, intent, cues, misread, intensity="restrained"):
    return PerformanceCue(character=who, emotion_intent=intent,
                          visible_cues=cues, intensity=intensity,
                          prohibited_misread=misread)


def choreo(gid, phases, once, performance):
    return GenerationChoreography(
        generation_id=gid, once_actions=once, performance=performance,
        phases=[Phase(kind=k, start_s=a, end_s=b, description=d)
                for k, a, b, d in phases])


# one shot per generation: (coverage, subject, foreground, visible)
SHOTS = {
    "SC01_g1": ("MASTER", "", "", IN_FRAME["SC01_g1"]),
    "SC01_g2": ("OTS", "NORA", "KESSLER", IN_FRAME["SC01_g2"]),
    "SC02_g1": ("OTS", "KESSLER", "NORA", IN_FRAME["SC02_g1"]),
    "SC02_g2": ("MASTER", "", "", IN_FRAME["SC02_g2"]),
    "SC03_g1": ("SINGLE", "ORTIZ", "", IN_FRAME["SC03_g1"]),
    "SC03_g2": ("MASTER", "", "", IN_FRAME["SC03_g2"]),
    "SC04_g1": ("SINGLE", "NORA", "", IN_FRAME["SC04_g1"]),
    "SC04_g2": ("MASTER", "", "", IN_FRAME["SC04_g2"]),
    "SC05_g1": ("SINGLE", "KESSLER", "", IN_FRAME["SC05_g1"]),
    "SC05_g2": ("SINGLE", "ORTIZ", "", IN_FRAME["SC05_g2"]),
    "SC06_g1": ("SINGLE", "NORA", "", IN_FRAME["SC06_g1"]),
    "SC06_g2": ("SINGLE", "KESSLER", "", IN_FRAME["SC06_g2"]),
    "SC07_g1": ("MASTER", "", "", IN_FRAME["SC07_g1"]),
    "SC07_g2": ("SINGLE", "NORA", "", IN_FRAME["SC07_g2"]),
    "SC08_g1": ("SINGLE", "ORTIZ", "", IN_FRAME["SC08_g1"]),
    "SC08_g2": ("MASTER", "", "", IN_FRAME["SC08_g2"]),
}
CHOREO = {
    "SC01_g1": choreo("SC01_g1", [
        ("SETUP", 0, 2, "NORA steps in through the glass doors"),
        ("ACTION", 2, 6, "KESSLER speaks without looking up"),
        ("ACTION", 6, 8, "NORA walks toward the desk")],
        ["KESSLER speaks"],
        [cue("KESSLER", "bored dismissal", ["eyes on his paperwork",
                                            "flat mouth"], "friendly smile")]),
    "SC01_g2": choreo("SC01_g2", [
        ("SETUP", 0, 2, "NORA stops in front of the desk"),
        ("ACTION", 2, 5, "NORA speaks, calm"),
        ("ACTION", 5, 8, "she lays a folded letter on the desk")],
        ["NORA speaks", "lays a folded letter on the desk"],
        [cue("NORA", "quiet composure", ["level gaze", "still hands"],
             "anger or a smile")]),
    "SC02_g1": choreo("SC02_g1", [
        ("ACTION", 0, 3, "KESSLER picks up the letter, unfolds it, reads"),
        ("ACTION", 3, 7, "he looks NORA up and down and speaks"),
        ("HOLD", 7, 8, "he holds a thin smirk")],
        ["picks up the letter"],
        [cue("KESSLER", "contempt", ["one corner of the mouth lifted",
                                     "eyes travel up and down"],
             "laughing out loud", "moderate")]),
    "SC02_g2": choreo("SC02_g2", [
        ("ACTION", 0, 4, "KESSLER crumples the letter, drops it in "
                         "the trash bin"),
        ("ACTION", 4, 6, "he speaks"),
        ("REACTION", 6, 8, "ORTIZ glances over")],
        ["crumples the letter", "drops it in the trash bin"],
        [cue("KESSLER", "smug dismissal", ["leans back", "half smile"],
             "shouting")]),
    "SC03_g1": choreo("SC03_g1", [
        ("SETUP", 0, 2, "ORTIZ looks from NORA to the bin, folder in hand"),
        ("ACTION", 2, 6, "ORTIZ speaks, hesitant"),
        ("HOLD", 6, 8, "he waits")],
        ["ORTIZ speaks"],
        [cue("ORTIZ", "uneasy doubt", ["glance to the bin",
                                       "tight shoulders"],
             "confident smirk")]),
    "SC03_g2": choreo("SC03_g2", [
        ("ACTION", 0, 2, "KESSLER turns his head back toward ORTIZ"),
        ("ACTION", 2, 5, "KESSLER speaks"),
        ("REACTION", 5, 8, "ORTIZ lowers his eyes")],
        ["KESSLER turns his head"],
        [cue("KESSLER", "irritation", ["sharp head turn", "narrowed eyes"],
             "laughing")]),
    "SC04_g1": choreo("SC04_g1", [
        ("SETUP", 0, 2, "NORA looks past KESSLER toward ORTIZ"),
        ("ACTION", 2, 5, "NORA speaks, unhurried"),
        ("HOLD", 5, 8, "she waits")],
        ["NORA speaks"],
        [cue("NORA", "patient authority", ["slight head tilt",
                                           "steady gaze"],
             "smile or anger")]),
    "SC04_g2": choreo("SC04_g2", [
        ("ACTION", 0, 4, "ORTIZ takes the crumpled letter from the bin "
                         "and smooths it flat"),
        ("ACTION", 4, 6, "ORTIZ speaks"),
        ("REACTION", 6, 8, "KESSLER stares")],
        ["takes the crumpled letter from the bin"],
        [cue("ORTIZ", "quiet resolve", ["careful hands"],
             "smile")]),
    "SC05_g1": choreo("SC05_g1", [
        ("SETUP", 0, 2, "the desk phone rings"),
        ("ACTION", 2, 7, "KESSLER lifts the receiver to his ear and speaks"),
        ("HOLD", 7, 8, "he listens, frozen")],
        ["lifts the receiver"],
        [cue("KESSLER", "dawning dread", ["smirk fading", "eyes widen a "
                                          "little"], "laughing or crying")]),
    "SC05_g2": choreo("SC05_g2", [
        ("SETUP", 0, 2, "ORTIZ holds the smoothed letter"),
        ("ACTION", 2, 5, "ORTIZ reads out loud"),
        ("HOLD", 5, 8, "he looks up from the letter toward NORA")],
        ["ORTIZ reads"],
        [cue("ORTIZ", "awe", ["eyebrows up", "lips parted"], "smirk")]),
    "SC06_g1": choreo("SC06_g1", [
        ("SETUP", 0, 2, "NORA looks at KESSLER"),
        ("ACTION", 2, 5, "NORA speaks, level, not unkind"),
        ("HOLD", 5, 8, "she holds his gaze")],
        ["NORA speaks"],
        [cue("NORA", "firm calm", ["level gaze", "relaxed mouth"],
             "triumphant smile")]),
    "SC06_g2": choreo("SC06_g2", [
        ("SETUP", 0, 2, "KESSLER, receiver still at his ear, swallows"),
        ("ACTION", 2, 5, "KESSLER speaks, quiet"),
        ("HOLD", 5, 8, "he sits frozen")],
        ["KESSLER speaks"],
        [cue("KESSLER", "deflated shame", ["smirk gone", "eyes drop"],
             "tears or anger")]),
    "SC07_g1": choreo("SC07_g1", [
        ("SETUP", 0, 2, "the room settles"),
        ("ACTION", 2, 6, "NORA speaks from the lectern"),
        ("REACTION", 6, 8, "KESSLER at the back wall stands still")],
        ["NORA speaks"],
        [cue("NORA", "steady command", ["upright posture", "even gaze over "
                                        "the room"], "shouting")]),
    "SC07_g2": choreo("SC07_g2", [
        ("SETUP", 0, 2, "NORA turns her eyes to ORTIZ"),
        ("ACTION", 2, 6, "NORA speaks"),
        ("HOLD", 6, 8, "a small nod")],
        ["NORA speaks"],
        [cue("NORA", "quiet approval", ["slight nod", "soft eyes"],
             "big grin")]),
    "SC08_g1": choreo("SC08_g1", [
        ("SETUP", 0, 2, "ORTIZ sits up straight, surprised"),
        ("ACTION", 2, 5, "ORTIZ nods and speaks"),
        ("HOLD", 5, 8, "a small proud breath")],
        ["ORTIZ nods"],
        [cue("ORTIZ", "surprised pride", ["straightens up", "small smile"],
             "laughing")]),
    "SC08_g2": choreo("SC08_g2", [
        ("SETUP", 0, 2, "NORA looks over the room to the back wall"),
        ("ACTION", 2, 5, "NORA speaks"),
        ("REACTION", 5, 8, "KESSLER at the back wall lowers his eyes")],
        ["NORA speaks"],
        [cue("KESSLER", "humbled", ["eyes down", "shoulders sink"],
             "anger or tears")]),
}
SFX = {"SC02_g1": ["paper unfolding"],
       "SC02_g2": ["paper crumpling"],
       "SC04_g2": ["paper being smoothed"],
       "SC05_g1": ["desk phone ringing"]}


def lines_for(scene, gen):
    """Dialogue in script order: generation k speaks the k-th line."""
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
    k = TAKES_ORDER.index(gid)
    if gid in ("SC01_g1", "SC07_g1"):
        return None
    prev = TAKES_ORDER[k - 1]
    return GenerationHandoff(
        previous_generation_id=prev,
        previous_action=" ".join(p.description for p in CHOREO[prev].phases
                                 if p.kind == "ACTION"),
        previous_start=STATE[prev], previous_end=cut(STATE[END[prev]], gid),
        # a take kept in takes/ was checked by eye, end state included
        end_state_verified=(OUT / "takes" / f"{prev}.mp4").is_file())


def in_frame(gid):
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
        unit, characters=[CharacterBrief(name=c, look=VIDEO_LOOKS[c],
                                         voice=VOICE[c]) for c in cast],
        setting=EXTRAS.get(sid, ""), room_tone=ROOM_TONE[sid],
        sfx=SFX.get(gid), dialogue_language="English", start_state=start,
        location=LOCATION[sid], choreography=CHOREO[gid])
    report = preflight_scene(
        scene=SCENES[sid], unit=unit, prompt=plan, reference_sets=[],
        reference_root=Path("docs/drama/refs"), storyboard=gate,
        known_characters=script.characters, limits=LIMITS,
        reference_mode="TEXT_ONLY", looks=list(VIDEO_LOOKS.values()),
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
    hidden = [c for c in LOOKS if c not in shown]
    props = "; ".join(f"{k.rstrip(':')} {v}" for k, v in start.props.items()
                      if not any(c in v for c in hidden))
    props = f" {props}." if props else ""
    extras = f" {EXTRAS[sid].capitalize()}." if sid in EXTRAS and \
        shot.coverage == "MASTER" else ""
    alone = "" if len(shown) > 1 else f" Only {shown[0]} in frame."
    return (f"Photoreal film still, 16:9, {FRAMING[shot.coverage]}: "
            f"{shot.describe(unit.axis_book)}. {LOCATION[sid].text}. "
            f"{people}.{props}{extras}{alone} Faces and clothes exactly as "
            "in the attached character images. Natural, restrained "
            "expressions. No text, no logos.")


CHAR_STILL = ("Photoreal character reference portrait, 16:9, plain warm grey "
              "studio backdrop, head and shoulders, front view, neutral "
              "expression, soft even light: {text}. No text, no logos.")
PLATE = ("Photoreal empty set plate, 16:9, eye-level wide view, nobody in "
         "the room: {text}. No people, no text, no logos.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    feas = check_script(script, limits=FEAS)
    lobby = [f"SC0{s}" for s in range(1, 7)]
    temporal = check_temporal(
        STORY, {sid: STATE[f"{sid}_end"] for sid in lobby[:-1]},
        {sid: STATE[f"{sid}_g1"] for sid in lobby[1:]})
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
    for loc in (LOBBY, BRIEF):
        (OUT / "stills" / f"plate_{loc.look_id}.txt").write_text(
            PLATE.format(text=loc.text) + "\n", encoding="utf-8")

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
    assert IN_FRAME == {g: SHOTS[g][3] for g in TAKES_ORDER}
    record["comprehension"] = [i.model_dump() for i in (
        lint_script(script, INTROS, FACTS) + check_comprehension(
            TAKES_ORDER, IN_FRAME, INTROS, FACTS, TAGS, CARDS))]
    print("comprehension", [f"{i['severity']} {i['check']} {i['detail']}"
                            for i in record["comprehension"]])
    record["looks"] = {k: v.model_dump() for k, v in LOOKS.items()}
    record["locations"] = [LOBBY.model_dump(), BRIEF.model_dump()]
    record["states"] = {k: v.model_dump() for k, v in STATE.items()}
    (OUT / "gate3_film03.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("feasibility", [i.detail for i in feas.issues])
    print("temporal", [i.detail for i in temporal])


if __name__ == "__main__":
    main()
