"""Authoring helper for film06 03_preprod.json + 04_shots.json (kept with the package; re-run after edits).

Both people stay seated in one booth for the whole film (film05 lesson: close singles at table height read as
standing or seated by chance). Every single and OTS keeps the high red booth back and the table edge in frame.
The envelope and the mug are placed before the film starts and never handled.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from film_pipeline.drama.script import parse_fountain  # noqa: E402

RUTH_LOOK = ("woman in her sixties, grey hair pinned up in a loose bun, reading glasses on a cord around her neck, "
             "pale blue diner uniform dress with a white apron")
SAM_LOOK = "man in his early twenties, short dark curly hair, thin face, damp grey hoodie with the hood down"

ENV = "the envelope:"
MUG = "the mug:"
ENV_S = "a thick white envelope lying flat in the middle of the table"
MUG_S = "a white coffee mug on the table in front of RUTH"


def pose(mark, posture, facing):
    return {"mark": mark, "posture": posture, "facing": facing}


RUTH_SEATED = pose("ruth_seat", "seated in the booth, back against the high red booth seat, hands folded on the table edge "
                                "in front of her", "SAM")
SAM_SEATED = pose("sam_seat", "seated in the booth, back against the high red booth seat, hands in the front pocket of "
                              "his hoodie", "RUTH")


def state():
    return {
        "positions": {"RUTH": "seated in the booth across the table, frame-left",
                      "SAM": "seated in the booth across the table, frame-right"},
        "props": {ENV: ENV_S, MUG: MUG_S},
        "looks": {"RUTH": "ruth_apron", "SAM": "sam_hoodie"},
        "lighting": "", "time_of_day": "", "location": "",
        "blocking": {"RUTH": RUTH_SEATED, "SAM": SAM_SEATED},
    }


SCENES = ["SC01", "SC02", "SC03", "SC04", "SC05", "SC06", "SC07"]
GIDS = ["SC01_g1", "SC01_g2", "SC02_g1", "SC02_g2", "SC02_g3", "SC02_g4", "SC03_g1", "SC03_g2",
        "SC04_g1", "SC04_g2", "SC04_g3", "SC05_g1", "SC05_g2", "SC06_g1", "SC06_g2", "SC07_g1", "SC07_g2"]
states = {gid: state() for gid in GIDS}
for sc in SCENES:
    states[f"{sc}_end"] = state()

lighting = {
    "key_direction": "SIDE_LEFT", "quality": "SOFT", "colour_temp_k": 3200, "contrast": "MEDIUM",
    "motivation": "a warm lamp hanging over the booth table, blue night and a red glow through the rain-streaked window",
    "practicals": [{"kind": "LAMP", "note": "warm lamp hanging low over the booth table"},
                   {"kind": "WINDOW", "note": "rain-streaked window beside the booth, blue night with a red glow"}],
}

scenes = {}
for i, sc in enumerate(SCENES, start=1):
    scenes[sc] = {
        "location": "diner_night",
        "axis": {"scene_id": sc, "axis_pair": ["RUTH", "SAM"], "sides": {"RUTH": "LEFT", "SAM": "RIGHT"}},
        "occupancy": {"scene_id": sc, "initial": ["RUTH", "SAM"], "events": []},
        "story_time": {"scene_id": sc, "story_order": float(i), "transition_in": "LINEAR", "marker": "", "source_conflict": ""},
        "extras": "",
        "lighting": lighting,
        "encounter_id": "booth_confession",
    }

layout = {
    "zones": [{"id": "booth", "label": "diner booth", "box": [0.05, 0.05, 0.95, 0.95]}],
    "objects": [
        {"id": "table", "label": "booth table", "zone": "booth",
         "placement": "between the two booth seats, its far end against the window", "at": [0.5, 0.5]},
        {"id": "window", "label": "rain-streaked window", "zone": "booth",
         "placement": "at the far end of the booth table, blue night and a red glow outside", "at": [0.5, 0.06]},
        {"id": "lamp", "label": "warm lamp", "zone": "booth",
         "placement": "hanging low over the middle of the booth table", "at": [0.5, 0.45]},
        {"id": "seat_left", "label": "high red vinyl booth seat", "zone": "booth",
         "placement": "along the left side of the table", "at": [0.25, 0.5]},
        {"id": "seat_right", "label": "high red vinyl booth seat", "zone": "booth",
         "placement": "along the right side of the table", "at": [0.75, 0.5]},
        {"id": "envelope", "label": "thick white envelope", "zone": "booth",
         "placement": "flat in the middle of the table", "at": [0.5, 0.52]},
        {"id": "mug", "label": "white coffee mug", "zone": "booth",
         "placement": "on the table in front of RUTH", "at": [0.4, 0.5]},
    ],
    "cameras": [
        {"id": "A", "zone": "booth",
         "view": "Camera at the open end of the booth at seated eye level, looking along the table to the window: RUTH seated on the left, SAM seated on the right, the window between them",
         "sees": ["table", "window", "lamp", "seat_left", "seat_right", "envelope", "mug"], "at": [0.5, 0.92], "look_at": "table"},
        {"id": "B", "zone": "booth",
         "view": "Camera at the open end of the booth, just left of the table, facing SAM across the table: SAM against his high red booth back",
         "sees": ["table", "window", "seat_right", "envelope", "mug"], "at": [0.35, 0.8], "look_at": "seat_right"},
        {"id": "C", "zone": "booth",
         "view": "Camera at the open end of the booth, just right of the table, facing RUTH across the table: RUTH against her high red booth back",
         "sees": ["table", "window", "seat_left", "envelope", "mug"], "at": [0.65, 0.8], "look_at": "seat_left"},
        {"id": "D", "zone": "booth",
         "view": "Camera low and close at the table edge, looking along the tabletop at the envelope",
         "sees": ["table", "envelope", "window"], "at": [0.5, 0.66], "look_at": "envelope"},
    ],
    "marks": [
        {"id": "ruth_seat", "at": [0.28, 0.5], "zone": "booth"},
        {"id": "sam_seat", "at": [0.72, 0.5], "zone": "booth"},
    ],
}

feas = {"max_speakers": 2, "max_in_frame": 3, "max_dialogue_syllables": 28, "scene_duration_s": 16.0,
        "min_silence_s": 3.0, "syllables_per_second": 2.5}

designs = {
    "RUTH_look": {"kind": "look", "version": 1, "owner": "RUTH", "note": "locked CharacterLook text"},
    "RUTH_costume": {"kind": "costume", "version": 1, "owner": "RUTH", "note": "pale blue diner uniform dress, white apron"},
    "SAM_look": {"kind": "look", "version": 1, "owner": "SAM", "note": "locked CharacterLook text"},
    "SAM_costume": {"kind": "costume", "version": 1, "owner": "SAM", "note": "damp grey hoodie, hood down"},
    "loc_diner_night": {"kind": "location", "version": 1, "owner": "diner_night"},
    "prop_envelope": {"kind": "prop", "version": 1, "prop": "the envelope"},
    "prop_mug": {"kind": "prop", "version": 1, "prop": "the mug"},
}


def pending(subject, kind, what):
    return {"subject": subject, "kind": kind, "status": "pending", "evidence": "",
            "note": f"{what}, model-written for this film; Owner to confirm originality"}


rights = [
    pending("RUTH", "character", "fictional character"),
    pending("SAM", "character", "fictional character"),
    pending("diner_night", "location", "fictional set"),
    {"subject": "none (room tone and SFX are generated or CC0)", "kind": "music", "status": "original",
     "evidence": "films/film06_six_am has no music stage", "note": "no music track in the film"},
    pending("script.fountain", "source", "original script"),
    {"subject": "none (no real person's likeness)", "kind": "likeness", "status": "pending", "evidence": "",
     "note": "faces are generated, not modelled on a real person; Owner to confirm"},
]

preprod = {
    "feasibility": feas,
    "preflight": {"max_prompt_words": 215,
                  "timing": {"duration_s": 8.0, "max_shots": 1, "min_shot_s": 2.0, "syllables_per_second": 2.5,
                             "establish_s": 1.5, "reaction_s": 3.0},
                  "feasibility": feas, "interaction_contract": True},
    "characters": {
        "RUTH": {"look": {"look_id": "ruth_apron", "character": "RUTH", "text": RUTH_LOOK,
                          "invariants": ["grey hair in a loose bun", "reading glasses on a cord", "pale blue uniform dress",
                                         "white apron"], "approved": True},
                 "video_text": RUTH_LOOK, "voice": "dry, low female voice", "handle": "the older woman"},
        "SAM": {"look": {"look_id": "sam_hoodie", "character": "SAM", "text": SAM_LOOK,
                         "invariants": ["short dark curly hair", "thin face", "grey hoodie, hood down"], "approved": True},
                "video_text": SAM_LOOK, "voice": "quiet, unsteady young male voice", "handle": "the young man"},
    },
    "locations": {
        "diner_night": {
            "look": {"look_id": "diner_night", "location": "KELLER'S DINER",
                     "text": ("Small closed diner at night: one booth with high red vinyl seats beside a rain-streaked "
                              "window, a warm lamp hanging over the booth table, the rest of the diner dark"),
                     "invariants": ["high red vinyl booth seats", "rain-streaked window beside the booth",
                                    "warm lamp over the booth table", "the rest of the diner dark"],
                     "interior": True, "time_of_day": "NIGHT", "weather_outside": "steady rain",
                     "environment_rules": ["rain runs down the window the whole time; the light never changes"],
                     "approved": True},
            "room_tone": "quiet diner hum, a refrigerator, rain on the window",
            "layout": layout,
        }
    },
    "scenes": scenes,
    "states": states,
    "still_templates": {
        "framing": {"MASTER": "wide shot of the whole booth",
                    "OTS": "medium over-the-shoulder shot, both people seated, the table between them",
                    "SINGLE": "close-up of one seated person, head and shoulders against the high red booth back",
                    "TWO_SHOT": "medium two-shot of both people seated across the table",
                    "REACTION": "insert close-up of the table, nobody in frame"},
        "character": "Photoreal character reference portrait, 16:9, plain warm grey studio backdrop, head and shoulders, front view, neutral expression, soft even light: {text}. No text, no logos.",
        "plate": "Photoreal empty set plate, 16:9, seated eye-level wide view, nobody in the room: {text}. No people, no text, no logos.",
        "pose": True,
    },
    "accepted_overlong": {},
    "designs": designs,
    "rights": rights,
    "risk_fallbacks": {},
    "stills": {},
}

# keep stills registered by `film.py stills --register` across re-runs
old = HERE / "03_preprod.json"
if old.exists():
    try:
        prev = json.loads(old.read_text(encoding="utf-8"))
        preprod["stills"] = prev.get("stills", {})
        preprod["accepted_overlong"] = prev.get("accepted_overlong", {})
    except json.JSONDecodeError:
        pass

BASE_REFS = ["RUTH_look@1", "RUTH_costume@1", "SAM_look@1", "SAM_costume@1", "loc_diner_night@1", "prop_envelope@1",
             "prop_mug@1"]

# dialogue -> script line number (the character-cue line, as parse_fountain numbers it)
_script = parse_fountain((HERE / "script.fountain").read_text(encoding="utf-8"))
LINE = {e.text: e.line_no for s in _script.scenes for e in s.elements if e.kind == "dialogue"}


def ln(text):
    return [LINE[text]]


def cam(size, composition, lens="NORMAL"):
    return {"size": size, "angle": "EYE_LEVEL", "height": "EYE", "movement": "STATIC", "lens_intent": lens,
            "composition": composition}


def perf(ch, intent, cues, intensity="restrained", misread="anger"):
    return {"character": ch, "emotion_intent": intent, "visible_cues": cues, "intensity": intensity,
            "prohibited_misread": misread}


def gen(gid, coverage, subject, foreground, visible, phases, once, performance, dialogue, camera, campos, duration,
        addressees=None, anchors=None, gaze=None, readout=None, **extra):
    sc = gid.split("_")[0]
    g = {
        "generation_id": gid, "scene_id": sc, "coverage": coverage, "subject": subject, "foreground": foreground,
        "visible": visible, "start_state": gid, "end_state": f"{sc}_end", "previous_generation_id": None,
        "choreography": {"generation_id": gid,
                         "phases": [dict(kind=k, start_s=a, end_s=b, description=d, **({"motion": m} if m else {}))
                                    for (k, a, b, d, m) in phases],
                         "once_actions": once, "gesture_budget": 1, "performance": performance},
        "sfx": [], "dialogue": dialogue, "design_refs": BASE_REFS, "camera": camera, "camera_position": campos,
        "readout": readout or [], "duration_s": duration, "version": 1,
    }
    if addressees:
        g["addressees"] = addressees
    if anchors:
        g["listener_anchors"] = anchors
    if gaze:
        g["gaze_target"] = gaze
    g.update(extra)
    return g


OFF_LEFT = {"mode": "OFF_FRAME", "side": "LEFT", "placement": "RUTH sits off frame-left across the table, wholly out of shot",
            "established_by": "SC01_g1"}
OFF_RIGHT = {"mode": "OFF_FRAME", "side": "RIGHT", "placement": "SAM sits off frame-right across the table, wholly out of shot",
             "established_by": "SC01_g1"}

SAM_SINGLE = ("close single on SAM seated in the booth: head and shoulders against the high red booth back, "
              "the table edge at the bottom of frame, RUTH out of frame to the left")
RUTH_SINGLE = ("close single on RUTH seated in the booth: head and shoulders against the high red booth back, "
               "the table edge at the bottom of frame, SAM out of frame to the right")
MASTER = ("master from the open end of the booth: RUTH seated on the left, SAM seated on the right, both against the high "
          "red booth backs, the rain-streaked window between them, the envelope and the mug on the table")
OTS_SAM = ("over RUTH's shoulder onto SAM seated across the table: the back of RUTH's grey bun and blue shoulder at the "
           "left edge, SAM on the right against his high red booth back, the envelope on the table between them")
OTS_RUTH = ("over SAM's shoulder onto RUTH seated across the table: SAM's curly hair and grey hoodie shoulder at the "
            "right edge, RUTH on the left against her high red booth back, the envelope on the table between them")


def ruth_single(gid, phases, line, intent, cues, duration, gaze="SAM", misread="anger"):
    return gen(gid, "SINGLE", "RUTH", "", ["RUTH"], phases, ["RUTH speaks to SAM"] if line else [],
               [perf("RUTH", intent, cues, misread=misread)], ln(line) if line else [], cam("CLOSE", RUTH_SINGLE),
               "C", duration, addressees={str(LINE[line]): ["SAM"]} if line else None, anchors={"SAM": OFF_RIGHT},
               gaze=gaze)


def sam_single(gid, phases, line, intent, cues, duration, gaze="RUTH", misread="anger"):
    return gen(gid, "SINGLE", "SAM", "", ["SAM"], phases, ["SAM speaks to RUTH"] if line else [],
               [perf("SAM", intent, cues, misread=misread)], ln(line) if line else [], cam("CLOSE", SAM_SINGLE),
               "B", duration, addressees={str(LINE[line]): ["RUTH"]} if line else None, anchors={"RUTH": OFF_LEFT},
               gaze=gaze)


L01 = "We closed an hour ago."
L02 = "I know. I waited till the last customer left."
L03 = "Ten years ago, somebody took money from your till."
L04 = "Three hundred and forty dollars. On a Tuesday."
L05 = "It's in the envelope. All of it, and some more."
L06 = "Why now?"
L07 = "I'm twenty-one. I want to start my life owing no one."
L08 = "I knew it was you. Your red bike was out front."
L09 = "You were eleven. You came back for pie every Sunday after."
L10 = "Please. Take it."
L11 = "My cook quits on Friday."
L12 = "You'd hire me?"
L13 = "I'd hire somebody who comes back."
L14 = "Keep the money. Buy shoes that don't slip. Six a.m."

gens = [
    gen("SC01_g1", "MASTER", "RUTH", "", ["RUTH", "SAM"],
        [("SETUP", 0.0, 2.0, "RUTH and SAM sit facing each other across the booth table, rain streaking the window", ""),
         ("ACTION", 2.0, 5.0, "RUTH speaks to SAM", ""),
         ("HOLD", 5.0, 7.0, "SAM holds her look and does not answer yet", "")],
        ["RUTH speaks to SAM"],
        [perf("RUTH", "dry, tired", ["level look", "flat mouth"])],
        ln(L01), cam("WIDE", MASTER, "WIDE_ESTABLISH"),
        "A", 7, addressees={str(LINE[L01]): ["SAM"]}, anchors={"SAM": {"mode": "VISIBLE"}}, gaze="SAM"),
    sam_single("SC01_g2",
               [("SETUP", 0.0, 1.0, "SAM looks across the table at RUTH", ""),
                ("ACTION", 1.0, 6.0, "SAM speaks to RUTH", ""),
                ("HOLD", 6.0, 8.0, "SAM waits, hands in his hoodie pocket, eyes on RUTH", "")],
               L02, "nervous, determined", ["eyes stay on her", "small swallow"], 8),
    gen("SC02_g1", "OTS", "SAM", "RUTH", ["SAM", "RUTH"],
        [("SETUP", 0.0, 1.0, "SAM sits looking at RUTH", ""),
         ("ACTION", 1.0, 6.5, "SAM speaks to RUTH, slowly", ""),
         ("HOLD", 6.5, 8.0, "SAM waits, eyes on RUTH", "")],
        ["SAM speaks to RUTH"],
        [perf("SAM", "ashamed, steady", ["eyes on her", "tight jaw"], misread="anger")],
        ln(L03), cam("MEDIUM", OTS_SAM),
        "B", 8, addressees={str(LINE[L03]): ["RUTH"]}, anchors={"RUTH": {"mode": "OTS_FOREGROUND"}}, gaze="RUTH"),
    ruth_single("SC02_g2",
                [("SETUP", 0.0, 1.0, "RUTH looks across the table at SAM", ""),
                 ("ACTION", 1.0, 6.0, "RUTH speaks to SAM, flat and exact", ""),
                 ("HOLD", 6.0, 8.0, "RUTH holds his look, quite still", "")],
                L04, "exact, unsurprised", ["steady eyes", "one raised eyebrow"], 8),
    sam_single("SC02_g3",
               [("SETUP", 0.0, 1.0, "SAM looks at RUTH", ""),
                ("ACTION", 1.0, 2.0, "SAM glances down at the table and back up to RUTH", "glance"),
                ("ACTION", 2.0, 7.0, "SAM speaks to RUTH", ""),
                ("HOLD", 7.0, 8.0, "SAM waits, eyes on RUTH", "")],
               L05, "earnest, anxious", ["quick glance down", "eyes back on her"], 8),
    gen("SC02_g4", "REACTION", "", "", [],
        [("SETUP", 0.0, 1.5, "the thick white envelope lies flat on the booth table, nobody in frame, no hands", ""),
         ("ACTION", 1.5, 4.0, "everything stays still; only the rain streaks the window beyond", "")],
        ["only the rain streaks the window"],
        [], [], cam("CLOSE", "insert along the tabletop: the thick white envelope in the foreground, the rain-streaked window blurred beyond", "SHALLOW_ISOLATE"),
        "D", 4,
        readout=[{"fact": "the money is in the envelope", "evidence": ["envelope"]}]),
    ruth_single("SC03_g1",
                [("SETUP", 0.0, 1.0, "RUTH looks at SAM", ""),
                 ("ACTION", 1.0, 2.5, "RUTH speaks to SAM, quietly", ""),
                 ("HOLD", 2.5, 5.0, "RUTH waits for his answer, eyes on SAM", "")],
                L06, "searching", ["narrowed eyes", "still mouth"], 5),
    sam_single("SC03_g2",
               [("SETUP", 0.0, 1.0, "SAM looks at RUTH", ""),
                ("ACTION", 1.0, 7.0, "SAM speaks to RUTH", ""),
                ("HOLD", 7.0, 8.0, "SAM swallows and holds her look", "")],
               L07, "plain, sincere", ["steady eyes", "small swallow"], 8, misread="joy"),
    ruth_single("SC04_g1",
                [("SETUP", 0.0, 1.0, "RUTH looks at SAM", ""),
                 ("ACTION", 1.0, 5.5, "RUTH speaks to SAM, gently", ""),
                 ("HOLD", 5.5, 7.0, "RUTH holds his look, almost smiling", "")],
                L08, "gentle, knowing", ["soft eyes", "corner of the mouth lifts"], 7, misread="mockery"),
    sam_single("SC04_g2",
               [("HOLD", 0.0, 2.5, "SAM stares at RUTH, frozen, lips parted", ""),
                ("ACTION", 2.5, 3.5, "SAM exhales slowly", ""),
                ("HOLD", 3.5, 5.0, "SAM stares on at RUTH, eyes wet", "")],
               None, "stunned", ["frozen stare", "lips parted"], 5, misread="fear"),
    gen("SC04_g3", "OTS", "RUTH", "SAM", ["RUTH", "SAM"],
        [("SETUP", 0.0, 1.0, "RUTH looks at SAM", ""),
         ("ACTION", 1.0, 8.0, "RUTH speaks to SAM, warmly", ""),
         ("HOLD", 8.0, 10.0, "RUTH holds his look, still", "")],
        ["RUTH speaks to SAM"],
        [perf("RUTH", "warm, matter-of-fact", ["soft eyes", "small nod"], misread="pity")],
        ln(L09), cam("MEDIUM", OTS_RUTH),
        "C", 10, addressees={str(LINE[L09]): ["SAM"]}, anchors={"SAM": {"mode": "OTS_FOREGROUND"}}, gaze="SAM"),
    sam_single("SC05_g1",
               [("SETUP", 0.0, 1.5, "SAM looks down at the table", ""),
                ("ACTION", 1.5, 2.5, "SAM raises his eyes to RUTH", "glance"),
                ("ACTION", 2.5, 4.5, "SAM speaks to RUTH, pleading", ""),
                ("HOLD", 4.5, 6.0, "SAM waits, eyes on RUTH", "")],
               L10, "pleading", ["eyes up to her", "brows drawn together"], 6, gaze="RUTH", misread="anger"),
    ruth_single("SC05_g2",
                [("HOLD", 0.0, 2.5, "RUTH looks down at the table for a long moment, quite still", ""),
                 ("ACTION", 2.5, 3.5, "RUTH raises her eyes to SAM", "glance"),
                 ("ACTION", 3.5, 6.5, "RUTH speaks to SAM, dry", ""),
                 ("HOLD", 6.5, 8.0, "RUTH holds his look", "")],
                L11, "deciding, dry", ["long look down", "eyes up to him"], 8),
    sam_single("SC06_g1",
               [("SETUP", 0.0, 1.0, "SAM looks at RUTH", ""),
                ("ACTION", 1.0, 3.0, "SAM speaks to RUTH, unsure", ""),
                ("HOLD", 3.0, 5.0, "SAM waits, eyes on RUTH, barely breathing", "")],
               L12, "disbelief", ["raised brows", "still"], 5, misread="joy"),
    ruth_single("SC06_g2",
                [("SETUP", 0.0, 1.0, "RUTH looks at SAM", ""),
                 ("ACTION", 1.0, 4.5, "RUTH speaks to SAM, plainly", ""),
                 ("HOLD", 4.5, 6.0, "RUTH holds his look", "")],
                L13, "plain, warm", ["steady eyes", "small nod"], 6, misread="pity"),
    gen("SC07_g1", "OTS", "RUTH", "SAM", ["RUTH", "SAM"],
        [("SETUP", 0.0, 1.0, "RUTH looks at SAM", ""),
         ("ACTION", 1.0, 6.5, "RUTH speaks to SAM, dry and kind", ""),
         ("HOLD", 6.5, 8.0, "RUTH holds his look, a small smile", "")],
        ["RUTH speaks to SAM"],
        [perf("RUTH", "dry, kind", ["small smile", "steady eyes"], misread="mockery")],
        ln(L14), cam("MEDIUM", OTS_RUTH),
        "C", 8, addressees={str(LINE[L14]): ["SAM"]}, anchors={"SAM": {"mode": "OTS_FOREGROUND"}}, gaze="SAM"),
    gen("SC07_g2", "MASTER", "SAM", "", ["RUTH", "SAM"],
        [("HOLD", 0.0, 1.5, "SAM and RUTH sit facing each other across the booth table", ""),
         ("ACTION", 1.5, 4.0, "SAM smiles and nods slowly", ""),
         ("HOLD", 4.0, 7.0, "both sit still, rain streaking the window", "")],
        ["SAM smiles and nods slowly"],
        [perf("SAM", "relieved, grateful", ["slow smile", "nod"], misread="laughter"),
         perf("RUTH", "content", ["small smile"], misread="sadness")],
        [], cam("WIDE", MASTER, "WIDE_ESTABLISH"),
        "A", 7, anchors={"RUTH": {"mode": "VISIBLE"}}, gaze="RUTH"),
]

READOUTS = {
    "SC01_g1": [{"fact": "the diner is closed and they are alone", "evidence": ["RUTH", "SAM"]}],
    "SC01_g2": [{"fact": "he waited for everyone to leave", "evidence": ["SAM"]}],
    "SC02_g1": [{"fact": "he took money from her till years ago", "evidence": ["SAM"]}],
    "SC02_g2": [{"fact": "she remembers the exact sum", "evidence": ["RUTH"]}],
    "SC02_g3": [{"fact": "the money is in the envelope", "evidence": ["SAM"]}],
    "SC03_g1": [{"fact": "she asks why he came now", "evidence": ["RUTH"]}],
    "SC03_g2": [{"fact": "he wants to owe no one", "evidence": ["SAM"]}],
    "SC04_g1": [{"fact": "she always knew it was him", "evidence": ["RUTH"]}],
    "SC04_g2": [{"fact": "he never knew she knew", "evidence": ["SAM"]}],
    "SC04_g3": [{"fact": "he kept coming back as a boy", "evidence": ["RUTH"]}],
    "SC05_g1": [{"fact": "he begs her to take the money", "evidence": ["SAM"]}],
    "SC05_g2": [{"fact": "she will not take it; she needs a cook", "evidence": ["RUTH"]}],
    "SC06_g1": [{"fact": "he cannot believe she would hire him", "evidence": ["SAM"]}],
    "SC06_g2": [{"fact": "she offers him the job", "evidence": ["RUTH"]}],
    "SC07_g1": [{"fact": "he will keep the money and start at six", "evidence": ["RUTH"]}],
    "SC07_g2": [{"fact": "he accepts", "evidence": ["SAM", "envelope"]}],
}
for g in gens:
    if g["generation_id"] in READOUTS:
        g["readout"] = READOUTS[g["generation_id"]]
# chain every generation to the one before it in the same scene (state handoff; nobody moves, so start == end)
CHAIN = {}
for a, b in zip(GIDS, GIDS[1:]):
    if a.split("_")[0] == b.split("_")[0]:
        CHAIN[b] = a
for g in gens:
    gid = g["generation_id"]
    if gid in CHAIN:
        g["previous_generation_id"] = CHAIN[gid]
    nxt = [k for k, v in CHAIN.items() if v == gid]
    if nxt:
        g["end_state"] = nxt[0]
VERSIONS: dict[str, int] = {}
for g in gens:
    g["version"] = VERSIONS.get(g["generation_id"], 1)
assert [g["generation_id"] for g in gens] == GIDS

shots = {"generations": gens, "history": []}
old_shots = HERE / "04_shots.json"
if old_shots.exists():
    try:
        shots["history"] = json.loads(old_shots.read_text(encoding="utf-8")).get("history", [])
    except json.JSONDecodeError:
        pass

(HERE / "03_preprod.json").write_text(json.dumps(preprod, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "04_shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote 03_preprod.json, 04_shots.json:", len(gens), "generations,", sum(g["duration_s"] for g in gens), "s")
