"""Authoring helper for film07 "The First Shift": script.fountain, 01_story, 02_direction, 03_preprod, 04_shots.

Re-run after edits (python films/film07_first_shift/_author.py). Inputs: the Owner-approved draft under
docs/production/pilots/film07_first_shift (beats.json: 12 scenes x 25 generations, script.fountain, budget.json).
Registered stills / history in 03_preprod.json and 04_shots.json are kept across re-runs.

Staging rules (film05/film06 lessons): two people, one location, static eye-level camera; dialogue = a CLOSE single of
the speaker with the listener OFF_FRAME on the axis side; one prop action per action generation, one actor at a time,
no hand-overs and no contact. Every state change (position, prop) happens inside an action generation.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
from film_pipeline.drama.script import parse_fountain  # noqa: E402
from film_pipeline.production.sections import PreprodSection, ShotDecl, shot_design_ids  # noqa: E402

DRAFT = REPO / "docs/production/pilots/film07_first_shift"
BEATS = json.loads((DRAFT / "beats.json").read_text(encoding="utf-8"))
OWNER_STATEMENT = "Duyệt, chạy pilot"
OWNER_EVIDENCE = (
    "Owner khoikk03, chat 2026-11-11 (UTC+7), statement \"Duyệt, chạy pilot\" answering: Duyệt film07 \"The First "
    "Shift\" với trần pilot 535 / toàn phim 3.210 credits? (brief, rights summary: RUTH/SAM fictional, film06 "
    "generated likeness reused, new diner counter/door/morning extension, no music, original script); recorded in "
    "docs/production/pilots/film07_first_shift/budget.json owner_approval")

# --------------------------------------------------------------------------------------------------------------------
# script.fountain: the approved draft, front matter and headings normalised for the parser
# --------------------------------------------------------------------------------------------------------------------
PREAMBLE = """Title: The First Shift
Credit: original drama; names, events and dialogue are new (not film06 text)
Author: Codex (screenplay draft); production package by Claude
Format: 12 scenes, 300 Flow generations of 6 s (Omni 1.2 Flash 360p), each used at about 5.5 s; English dialogue, Vietnamese subtitles; no music
Tests: P20 second long film; pilot SC01-SC02 first (50 generations), the rest only after the pilot QC passes and the Owner is told
Approval: Owner 2026-11-11 \"Duyệt, chạy pilot\" (budget.json owner_approval); source draft SHA-256 c45ac9dcdfc09cefb4f11c8efc868ed132aa0c288d379c991eb856c4ec3bf92c

[[Opening card: 3 seconds. THE FIRST SHIFT. AI-generated drama. Body: 300 beats at an intended 5.5 seconds each; actual performance and trims are measured on the takes.]]

RUTH KELLER is the same fictional woman in her sixties as in Six A.M.; SAM DOYLE is the same fictional twenty-one-year-old man. Her pale blue uniform and white apron, his grey hoodie and the red vinyl booth are the reused visual references. His shoes are now dry. This is their first working morning, not a revision of their earlier conversation.

The diner is empty. Morning light reaches the familiar red booth. The counter and doorway are new extensions of the set. No other person is seen or heard. A CLOSED PERMANENTLY notice lies on the counter. There is no music.

"""
_HEAD = re.compile(r"^INT\. KELLER'S DINER - (?P<area>[A-Z /]+) - (?P<time>DAWN|EARLY MORNING|MORNING)$")


def build_script() -> str:
    draft = (DRAFT / "script.fountain").read_text(encoding="utf-8").replace("\r\n", "\n")
    body = draft[draft.index("INT. KELLER'S DINER"):]
    out: list[str] = []
    for line in body.split("\n"):
        m = _HEAD.match(line)
        if m:
            out += [f"INT. KELLER'S DINER - {m['time']}", "", f"[[area: {m['area'].lower()}]]"]
        else:
            out.append(line)
    return PREAMBLE + "\n".join(out).rstrip("\n") + "\n"


SCRIPT_TEXT = build_script()
(HERE / "script.fountain").write_text(SCRIPT_TEXT, encoding="utf-8", newline="\n")
SCRIPT = parse_fountain(SCRIPT_TEXT)
LINES = {s.scene_id: {e.text: e.line_no for e in s.elements if e.kind == "dialogue"} for s in SCRIPT.scenes}
assert len(SCRIPT.scenes) == 12

# --------------------------------------------------------------------------------------------------------------------
# looks, places, props
# --------------------------------------------------------------------------------------------------------------------
RUTH_LOOK = ("woman in her sixties, grey hair pinned up in a loose bun, reading glasses on a cord around her neck, "
             "pale blue diner uniform dress with a white apron")
SAM_LOOK = "man in his early twenties, short dark curly hair, thin face, damp grey hoodie with the hood down"
LOC = "diner_morning"
LOC_TEXT = ("Small diner in the early morning, nobody else in it: a long counter with a row of red vinyl stools and a back "
            "shelf of white mugs, a pale front window and an open doorway on the right, and the high red vinyl booth "
            "against the far wall on the left")

# position key -> (state text, mark, posture, facing)
POS = {
    "R_CTR": ("standing behind the counter, frame-left", "ctr_ruth", "standing behind the counter, hands at her sides", "SAM"),
    "S_CUST": ("standing on the customer side of the counter, frame-right", "ctr_sam",
               "standing at the counter, hands at his sides", "RUTH"),
    "S_DOOR": ("standing in the open doorway at the right edge of the frame", "door_sam",
               "standing in the doorway, hands at his sides", "RUTH"),
    "R_BSTAND": ("standing beside the far booth seat, frame-left", "bth_ruth_stand",
                 "standing beside the booth, hands at her sides", "SAM"),
    "S_BSTAND": ("standing beside the near booth seat, frame-right", "bth_sam_stand",
                 "standing beside the booth, hands at his sides", "RUTH"),
    "R_BSEAT": ("seated on the far booth seat across the table, frame-left", "bth_ruth_seat",
                "seated in the booth, back against the high red booth seat, hands folded on the table edge", "SAM"),
    "S_BSEAT": ("seated on the near booth seat across the table, frame-right", "bth_sam_seat",
                "seated in the booth, back against the high red booth seat, hands in the front pocket of his hoodie", "RUTH"),
}
KIND = {"R_CTR": "counter", "S_CUST": "counter", "S_DOOR": "door", "R_BSTAND": "bstand", "S_BSTAND": "bstand",
        "R_BSEAT": "bseat", "S_BSEAT": "bseat"}

# off-frame listener placement, by the listener's position key
OFF = {
    "R_CTR": ("LEFT", "RUTH stands behind the counter off frame-left, wholly out of shot"),
    "S_CUST": ("RIGHT", "SAM stands on the customer side of the counter off frame-right, wholly out of shot"),
    "S_DOOR": ("RIGHT", "SAM stands in the open doorway off frame-right, wholly out of shot"),
    "R_BSTAND": ("LEFT", "RUTH stands beside the booth off frame-left, wholly out of shot"),
    "S_BSTAND": ("RIGHT", "SAM stands beside the booth off frame-right, wholly out of shot"),
    "R_BSEAT": ("LEFT", "RUTH sits off frame-left across the table, wholly out of shot"),
    "S_BSEAT": ("RIGHT", "SAM sits off frame-right across the table, wholly out of shot"),
}

# single composition by speaker position key
COMPOSE = {
    "R_CTR": ("close single on RUTH standing behind the counter: head and shoulders, the counter edge low in the frame, "
              "the back shelf of white mugs behind her, SAM out of frame to the right"),
    "S_CUST": ("close single on SAM standing on the customer side of the counter: head and shoulders, the counter edge "
               "low in the frame, the pale front window behind him, RUTH out of frame to the left"),
    "S_DOOR": ("close single on SAM standing in the open doorway: head and shoulders, the door frame beside him and "
               "daylight outside behind him, RUTH out of frame to the left"),
    "R_BSTAND": ("close single on RUTH standing beside the booth: head and shoulders against the high red booth back, "
                 "the table edge low in the frame, SAM out of frame to the right"),
    "S_BSTAND": ("close single on SAM standing beside the booth: head and shoulders against the high red booth back, "
                 "the table edge low in the frame, RUTH out of frame to the left"),
    "R_BSEAT": ("close single on RUTH seated in the booth: head and shoulders against the high red booth back, "
                "the table edge at the bottom of frame, SAM out of frame to the right"),
    "S_BSEAT": ("close single on SAM seated in the booth: head and shoulders against the high red booth back, "
                "the table edge at the bottom of frame, RUTH out of frame to the left"),
}
CAMPOS = {"counter": ("cB_ctr", "cC_ctr"), "door": ("cB_door", "cC_ctr"), "bstand": ("cB_bth", "cC_bth"),
          "bseat": ("cB_bth", "cC_bth")}  # (camera on SAM, camera on RUTH)

MASTER_TXT = {
    "counter": ("wide shot from the doorway end of the counter: RUTH behind the counter on the left, SAM on the customer "
                "side on the right, the back shelf of white mugs and the pale front window behind them"),
    "booth": ("master from the open end of the booth: RUTH on the left and SAM on the right across the booth table, "
              "the high red booth backs and the table between them"),
}

# prop key (state key, ends with ':') -> design id
PROPS = {
    "the closure notice:": "prop_notice", "the white mug:": "prop_mug1", "the second mug:": "prop_mug2",
    "the cloth:": "prop_cloth", "the paper:": "prop_paper", "the notebook:": "prop_notebook",
    "the menu card:": "prop_menu", "the wage sheet:": "prop_wages", "the open card:": "prop_open",
}
NOTICE_ON_COUNTER = "lying flat on the counter, face up"

# per-scene staging: start positions, start props, and the changes made by the action generations
# event key: generation number; value: (who -> position key, prop -> text or None)
SC = {
    "SC01": dict(area="counter", tod="DAWN", light="dawn", r="R_CTR", s="S_DOOR",
                 props={"the closure notice:": NOTICE_ON_COUNTER},
                 ev={1: ({"SAM": "S_CUST"}, {}),
                     8: ({}, {"the white mug:": "standing on the counter"}),
                     16: ({}, {"the white mug:": "held in SAM's right hand at chest height"}),
                     24: ({}, {"the white mug:": "standing on the counter"})}),
    "SC02": dict(area="counter", tod="DAWN", light="dawn", r="R_BSTAND", s="S_CUST",
                 props={"the closure notice:": NOTICE_ON_COUNTER},
                 ev={1: ({"SAM": "S_BSTAND"}, {}), 7: ({"SAM": "S_BSEAT"}, {}), 14: ({"RUTH": "R_BSEAT"}, {}),
                     24: ({"SAM": "S_BSTAND"}, {})}),
    "SC03": dict(area="counter", tod="EARLY MORNING", light="early", r="R_CTR", s="S_CUST",
                 props={"the white mug:": "standing on the counter"},
                 ev={6: ({}, {"the second mug:": "standing at the far end"}),
                     20: ({}, {"the cloth:": "lying folded on the counter"})}),
    "SC04": dict(area="booth", tod="MORNING", light="morning", r="R_BSEAT", s="S_BSEAT", props={},
                 ev={7: ({}, {"the paper:": "lying flat on RUTH's side of the booth table"}),
                     20: ({}, {"the notebook:": "lying closed beside SAM's elbow on the booth table"})}),
    "SC05": dict(area="counter", tod="MORNING", light="morning", r="R_CTR", s="S_CUST",
                 props={"the white mug:": "standing on the counter on RUTH's side"},
                 ev={13: ({}, {"the white mug:": "held in RUTH's right hand (the arm nearer the camera, on screen-left)"}),
                     20: ({}, {"the white mug:": "standing on the counter on RUTH's side"})}),
    "SC06": dict(area="booth", tod="MORNING", light="morning", r="R_BSEAT", s="S_BSEAT", props={},
                 ev={7: ({}, {"the closure notice:": "lying folded on RUTH's side of the booth table"}),
                     19: ({}, {"the notebook:": "lying closed on SAM's side of the booth table"})}),
    "SC07": dict(area="counter", tod="MORNING", light="morning", r="R_CTR", s="S_CUST",
                 props={"the cloth:": "lying folded on the counter in front of SAM"},
                 ev={7: ({}, {"the menu card:": "lying flat on the counter at RUTH's end, beyond SAM's reach"}),
                     19: ({}, {"the cloth:": "lying folded on the counter beside the two empty cup spaces"})}),
    "SC08": dict(area="booth", tod="MORNING", light="morning", r="R_BSEAT", s="S_BSEAT", props={},
                 ev={8: ({}, {"the wage sheet:": "lying flat on RUTH's side of the booth table"})}),
    "SC09": dict(area="counter", tod="MORNING", light="morning", r="R_CTR", s="S_CUST",
                 props={"the white mug:": "standing at SAM's elbow",
                        "the second mug:": "standing beside the first"},
                 ev={6: ({}, {"the white mug:": "standing in the near cup space"}),
                     20: ({}, {"the second mug:": "standing in the far cup space"})}),
    "SC10": dict(area="booth", tod="MORNING", light="morning", r="R_CTR", s="S_BSTAND", props={},
                 ev={8: ({"SAM": "S_DOOR"}, {}), 21: ({"SAM": "S_CUST"}, {})}),
    "SC11": dict(area="booth", tod="MORNING", light="morning", r="R_BSEAT", s="S_BSEAT", props={}, ev={}),
    "SC12": dict(area="counter", tod="MORNING", light="morning", r="R_CTR", s="S_CUST", props={},
                 ev={25: ({}, {"the open card:": "standing on the clear counter beside the till"})}),
}
# an action generation's own staging: (coverage, camera key, visible, subject, phases, once, perf who, gaze)
# phases are (kind, start, end, text, motion)

LIGHT = {
    "dawn": dict(key_direction="SIDE_RIGHT", quality="SOFT", colour_temp_k=5200, contrast="MEDIUM",
                 motivation="cool pale dawn light through the front window, one warm lamp over the counter",
                 practicals=[{"kind": "WINDOW", "note": "front window, cool pale dawn light"},
                             {"kind": "LAMP", "note": "warm lamp over the counter, still on"}]),
    "early": dict(key_direction="SIDE_RIGHT", quality="SOFT", colour_temp_k=4600, contrast="MEDIUM",
                  motivation="soft early daylight through the front window, the counter lamp switched off",
                  practicals=[{"kind": "WINDOW", "note": "front window, soft early daylight"}]),
    "morning": dict(key_direction="SIDE_RIGHT", quality="SOFT", colour_temp_k=4200, contrast="LOW",
                    motivation="warm morning sun through the front window and the open doorway",
                    practicals=[{"kind": "WINDOW", "note": "front window, warm morning sun"}]),
}

CUES = {  # scene -> (RUTH, SAM): (intent, visible cues, prohibited misread)
    "SC01": (("dry, guarded", ["level look", "flat mouth"], "anger"), ("careful, polite", ["eyes steady", "small swallow"], "anger")),
    "SC02": (("honest, tired", ["lowered eyes", "steady voice"], "pity"), ("direct, hurt", ["eyes on her", "tight jaw"], "anger")),
    "SC03": (("plain, practical", ["steady eyes", "small nod"], "impatience"), ("focused, curious", ["attentive eyes", "slight nod"], "boredom")),
    "SC04": (("matter-of-fact, uneasy", ["steady eyes", "a small frown"], "anger"), ("measured, firm", ["level look", "small nod"], "anger")),
    "SC05": (("candid, careful", ["soft eyes", "slow blink"], "pity"), ("guarded, honest", ["level look", "mouth easing"], "anger")),
    "SC06": (("tired, truthful", ["lowered eyes", "a long breath"], "self-pity"), ("patient, steady", ["attentive eyes", "small nod"], "pity")),
    "SC07": (("practical, dry", ["steady eyes", "half-smile"], "mockery"), ("careful, practical", ["attentive eyes", "slight frown"], "doubt")),
    "SC08": (("honest, exposed", ["steady eyes", "still mouth"], "defensiveness"), ("careful, exact", ["level look", "small nod"], "suspicion")),
    "SC09": (("candid, humble", ["soft eyes", "small nod"], "authority"), ("clear, composed", ["steady eyes", "slight nod"], "challenge")),
    "SC10": (("restrained, giving space", ["still posture", "soft eyes"], "pressure"), ("thoughtful, wary", ["eyes down then up", "slow breath"], "fear")),
    "SC11": (("steady, businesslike", ["level look", "small nod"], "coldness"), ("deliberate, clear", ["steady eyes", "small nod"], "coldness")),
    "SC12": (("dry, warm", ["slight smile", "steady eyes"], "mockery"), ("easy, determined", ["small smile", "steady eyes"], "smugness")),
}
MANNER = {"SC01": "guardedly", "SC02": "plainly", "SC03": "practically", "SC04": "evenly", "SC05": "carefully",
          "SC06": "tiredly", "SC07": "dryly", "SC08": "exactly", "SC09": "humbly", "SC10": "quietly", "SC11": "steadily",
          "SC12": "warmly"}

# --------------------------------------------------------------------------------------------------------------------
# continuity states
# --------------------------------------------------------------------------------------------------------------------
def pose(key):
    text, mark, posture, facing = POS[key]
    return {"mark": mark, "posture": posture, "facing": facing}


def make_state(cfg, r, s, props, tod):
    return {
        "positions": {"RUTH": POS[r][0], "SAM": POS[s][0]},
        "props": dict(props), "looks": {"RUTH": "ruth_apron", "SAM": "sam_hoodie"},
        "lighting": cfg["light"], "time_of_day": tod, "location": LOC,
        "blocking": {"RUTH": pose(r), "SAM": pose(s)},
    }


def gid(sc, n):
    return f"{sc}_g{n:02d}"


states: dict[str, dict] = {}
timeline: dict[str, list[tuple[str, str, dict]]] = {}  # scene -> per generation (ruth key, sam key, props) at its START
for sc, cfg in SC.items():
    r, s, props = cfg["r"], cfg["s"], dict(cfg["props"])
    timeline[sc] = []
    for n in range(1, 26):
        states[gid(sc, n)] = make_state(cfg, r, s, props, cfg["tod"])
        timeline[sc].append((r, s, dict(props)))
        who, pr = cfg["ev"].get(n, ({}, {}))
        r, s = who.get("RUTH", r), who.get("SAM", s)
        props.update(pr)
    states[f"{sc}_end"] = make_state(cfg, r, s, props, cfg["tod"])

# --------------------------------------------------------------------------------------------------------------------
# generations
# --------------------------------------------------------------------------------------------------------------------
def cam(size, composition, lens="NORMAL", repeat=""):
    c = {"size": size, "angle": "EYE_LEVEL", "height": "EYE", "movement": "STATIC", "lens_intent": lens,
         "composition": composition}
    if repeat:
        c["declared_repeat"] = repeat
    return c


REPEAT = "static alternating close singles are the deliberate grammar of this two-person talking scene"
GAZE_OBJ = {"counter": "counter", "door": "doorway", "bstand": "booth_table", "bseat": "booth_table"}

# action generations: n -> phases, once, who acts, camera kind, visible, gaze/subject notes
def phases(*items):
    return [dict(kind=k, start_s=a, end_s=b, description=d, **({"motion": m} if m else {})) for (k, a, b, d, m) in items]


ACTIONS = {
    ("SC01", 1): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter; SAM waits in the open doorway at the right edge of the frame", ""),
        ("ACTION", 1.0, 4.0, "SAM walks in through the doorway at an ordinary pace and stops on the customer side of the counter", "walk_across_room"),
        ("HOLD", 4.0, 6.0, "SAM stands at the counter facing RUTH, both quite still", "")),
        once=["SAM walks in through the doorway"]),
    ("SC01", 8): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter, SAM stands on the customer side with his hands at his sides", ""),
        ("ACTION", 1.0, 2.6, "RUTH sets one empty white mug down on the counter between them", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "the white mug stands still on the counter", ""),
        ("HOLD", 4.0, 6.0, "both stay still, SAM's hands away from the mug", "")),
        once=["RUTH sets one empty white mug down"], tracked=("the white mug", "still")),
    ("SC01", 16): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter with her hands at her sides, the white mug stands on the counter", ""),
        ("ACTION", 1.0, 2.8, "SAM lifts the white mug from the counter in his right hand", "pick_up_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "SAM holds the white mug at chest height", ""),
        ("HOLD", 4.0, 6.0, "both stay still, RUTH's hands stay on her own side", "")),
        once=["SAM lifts the white mug"]),
    ("SC01", 24): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM holds the white mug at chest height, RUTH stands behind the counter", ""),
        ("ACTION", 1.0, 2.8, "SAM sets the white mug down on the counter in its original place", "put_down_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "the white mug stands still on the counter between them", ""),
        ("HOLD", 4.0, 6.0, "both stay still, RUTH does not reach toward the mug", "")),
        once=["SAM sets the white mug down"]),
    ("SC02", 1): dict(cov="SINGLE", cam="counter", close=("SAM", "close on SAM at the counter, the pale front window behind him; he turns and walks out of the frame toward the booth, leaving the counter edge and the window behind"), visible=["SAM"], subject="SAM", who="SAM", gaze="booth_table", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM stands on the customer side of the counter, looking toward the booth", ""),
        ("ACTION", 1.0, 4.0, "SAM walks away from the counter toward the booth and out of the frame", "walk_across_room"),
        ("HOLD", 4.0, 6.0, "the counter is empty of people, the pale window light holds", "")),
        once=["SAM walks away from the counter toward the booth"]),
    ("SC02", 7): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands beside the far booth seat, SAM stands beside the near booth seat", ""),
        ("ACTION", 1.0, 3.0, "SAM sits down on the near booth seat", "sit_down"),
        ("HOLD", 3.0, 6.0, "SAM sits against the high red booth back, RUTH stays standing across the table", "")),
        once=["SAM sits down on the near booth seat"]),
    ("SC02", 14): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM sits on the near booth seat, RUTH stands beside the far booth seat", ""),
        ("ACTION", 1.0, 3.0, "RUTH sits down on the far booth seat", "sit_down"),
        ("HOLD", 3.0, 6.0, "both sit facing each other across the booth table", "")),
        once=["RUTH sits down on the far booth seat"]),
    ("SC02", 24): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH and SAM sit facing each other across the booth table", ""),
        ("ACTION", 1.0, 3.0, "SAM stands up beside the near booth seat", "stand_up"),
        ("HOLD", 3.0, 6.0, "SAM stands beside the booth, RUTH stays seated across the table", "")),
        once=["SAM stands up beside the near booth seat"]),
    ("SC03", 6): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter, SAM on the customer side, one white mug on the counter at RUTH's end", ""),
        ("ACTION", 1.0, 2.6, "RUTH sets a second empty mug down on the far end of the counter, away from SAM", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "two separate mugs stand still on the counter", ""),
        ("HOLD", 4.0, 6.0, "both stay still, SAM's hands at his sides", "")),
        once=["RUTH sets a second empty mug down"]),
    ("SC03", 20): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM stands on the customer side with a folded cloth in his hand, RUTH stands behind the counter", ""),
        ("ACTION", 1.0, 2.8, "SAM lays the folded cloth on the clear end of the counter", "put_down_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "the folded cloth lies still on the counter", ""),
        ("HOLD", 4.0, 6.0, "both stay still, RUTH does not move", "")),
        once=["SAM lays the folded cloth on the clear end of the counter"]),
    ("SC04", 7): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH and SAM sit facing each other across the booth table", ""),
        ("ACTION", 1.0, 2.6, "RUTH lays one plain sheet of paper on her own side of the table", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "the sheet of paper lies flat on RUTH's side", ""),
        ("HOLD", 4.0, 6.0, "both sit still, SAM's hands stay in his hoodie pocket", "")),
        once=["RUTH lays one plain sheet of paper on her own side"]),
    ("SC04", 20): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH and SAM sit facing each other, SAM holds a small closed notebook", ""),
        ("ACTION", 1.0, 2.6, "SAM lays his small notebook down beside his elbow, clear of RUTH's paper", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "the notebook lies closed beside SAM's elbow", ""),
        ("HOLD", 4.0, 6.0, "both sit still", "")),
        once=["SAM lays his small notebook down"]),
    ("SC05", 13): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter, her own empty mug stands on the counter on her side, SAM stands on the customer side", ""),
        ("ACTION", 1.0, 2.8, "RUTH lifts her own empty mug from the counter", "pick_up_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "RUTH holds her mug at chest height", ""),
        ("HOLD", 4.0, 6.0, "both stay still, SAM does not reach toward her", "")),
        once=["RUTH lifts her own empty mug"]),
    ("SC05", 20): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH holds her own mug at chest height, SAM stands on the customer side", ""),
        ("ACTION", 1.0, 2.8, "RUTH sets her mug back down on the counter on her own side", "put_down_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "the mug stands still on RUTH's side of the counter", ""),
        ("HOLD", 4.0, 6.0, "both stay still", "")),
        once=["RUTH sets her mug back down"]),
    ("SC06", 7): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH and SAM sit facing each other across the booth table, RUTH holds a folded paper notice", ""),
        ("ACTION", 1.0, 2.6, "RUTH lays the folded notice down on her own side of the table", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "the folded notice lies still on RUTH's side", ""),
        ("HOLD", 4.0, 6.0, "both sit still", "")),
        once=["RUTH lays the folded notice down"]),
    ("SC06", 19): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH and SAM sit facing each other, SAM holds a closed notebook", ""),
        ("ACTION", 1.0, 2.6, "SAM lays his closed notebook down on his own side of the table", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "the notebook lies closed on SAM's side, away from RUTH's reach", ""),
        ("HOLD", 4.0, 6.0, "both sit still", "")),
        once=["SAM lays his closed notebook down"]),
    ("SC07", 7): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter holding a plain menu card, SAM stands on the customer side", ""),
        ("ACTION", 1.0, 2.6, "RUTH lays the plain menu card flat on the counter at her end", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "the menu card lies still, beyond SAM's reach", ""),
        ("HOLD", 4.0, 6.0, "both stay still", "")),
        once=["RUTH lays the plain menu card flat on the counter"]),
    ("SC07", 19): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM holds the folded cloth, RUTH stands behind the counter, two empty cup spaces on the counter", ""),
        ("ACTION", 1.0, 2.8, "SAM lays the folded cloth on the counter beside the two cup spaces", "put_down_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "the cloth lies still, both cup spaces clear", ""),
        ("HOLD", 4.0, 6.0, "both stay still, RUTH stays clear of his reach", "")),
        once=["SAM lays the folded cloth on the counter"]),
    ("SC08", 8): dict(cov="MASTER", cam="booth", visible=["RUTH", "SAM"], subject="RUTH", who="RUTH", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH and SAM sit facing each other, RUTH holds one sheet of paper", ""),
        ("ACTION", 1.0, 2.6, "RUTH lays the wage sheet down flat on her own side of the table", "put_down_small_object"),
        ("CONSEQUENCE", 2.6, 4.0, "the wage sheet lies still on RUTH's side", ""),
        ("HOLD", 4.0, 6.0, "both sit still", "")),
        once=["RUTH lays the wage sheet down"]),
    ("SC09", 6): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM stands on the customer side with an empty mug beside his elbow, RUTH stands behind the counter", ""),
        ("ACTION", 1.0, 2.8, "SAM sets one empty mug into the clear cup space on his side of the counter", "put_down_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "the mug stands still in its cup space", ""),
        ("HOLD", 4.0, 6.0, "both stay still", "")),
        once=["SAM sets one empty mug into the clear cup space"]),
    ("SC09", 20): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM stands on the customer side, a second clean mug beside his elbow, RUTH stands behind the counter", ""),
        ("ACTION", 1.0, 2.8, "SAM sets a second clean empty mug into the other cup space", "put_down_small_object"),
        ("CONSEQUENCE", 2.8, 4.0, "both mugs stand still in their cup spaces", ""),
        ("HOLD", 4.0, 6.0, "both stay still, RUTH stays clear of his reach", "")),
        once=["SAM sets a second clean empty mug into the other cup space"]),
    ("SC10", 8): dict(cov="SINGLE", cam="booth", close=("SAM", "close on SAM beside the booth, the high red booth back behind him; he turns and walks out of the frame toward the doorway, leaving the booth behind"), visible=["SAM"], subject="SAM", who="SAM", gaze="doorway", ph=phases(
        ("SETUP", 0.0, 1.0, "SAM stands beside the near booth seat, looking toward the doorway", ""),
        ("ACTION", 1.0, 4.0, "SAM walks away from the booth toward the doorway and out of the frame", "walk_across_room"),
        ("HOLD", 4.0, 6.0, "the booth stands empty of people, daylight holds on the red seats", "")),
        once=["SAM walks away from the booth toward the doorway"]),
    ("SC10", 21): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter; SAM waits in the open doorway at the right edge of the frame", ""),
        ("ACTION", 1.0, 4.0, "SAM walks back in through the doorway at an ordinary pace and stops on the customer side of the counter", "walk_across_room"),
        ("HOLD", 4.0, 6.0, "SAM stands at the counter facing RUTH, both quite still", "")),
        once=["SAM walks back in through the doorway"]),
    ("SC12", 25): dict(cov="MASTER", cam="counter", visible=["RUTH", "SAM"], subject="SAM", who="SAM", ph=phases(
        ("SETUP", 0.0, 1.0, "RUTH stands behind the counter and SAM on the customer side, the counter clear beside the till", ""),
        ("ACTION", 1.0, 2.8, "SAM sets a small freestanding card that says OPEN down on the clear counter", "put_down_small_object"),
        ("CONSEQUENCE", 2.8, 4.5, "the small OPEN card stands still on the counter", ""),
        ("HOLD", 4.5, 6.0, "both stay still, RUTH well clear of his reach", "")),
        once=["SAM sets a small freestanding card that says OPEN down"]),
}
# reaction generations: n -> (speaker, phases, gaze)
REACTIONS = {
    ("SC03", 13): ("SAM", "SAM looks down at the two separate mugs on the counter, then lifts his eyes thoughtfully", "counter"),
    ("SC04", 14): ("RUTH", "RUTH meets SAM's look and takes a quiet moment before she goes on", "SAM"),
    ("SC05", 6): ("SAM", "SAM stands still with both hands visible and empty, his jaw easing slightly", "RUTH"),
    ("SC06", 13): ("RUTH", "RUTH sits quietly, her eyes resting on the table in front of her", "booth_table"),
    ("SC08", 18): ("SAM", "SAM studies RUTH's face and takes his time before the next question", "RUTH"),
    ("SC11", 13): ("SAM", "SAM holds a quiet, deliberate look at RUTH before the next question", "RUTH"),
}

PRIOR_BOTH: list[str] = []  # generations (in order) that show both people together
gens: list[dict] = []
order_cache: dict[str, str] = {}


def perf(ch, cue, intensity="restrained"):
    intent, cues, misread = cue
    return {"character": ch, "emotion_intent": intent, "visible_cues": cues, "intensity": intensity,
            "prohibited_misread": misread}


def other(who):
    return "SAM" if who == "RUTH" else "RUTH"


def anchor_for(listener, key, est):
    side, text = OFF[key]
    return {"mode": "OFF_FRAME", "side": side, "placement": text, "established_by": est}


for beat_scene in BEATS["scenes"]:
    sc = beat_scene["scene_id"]
    cfg = SC[sc]
    cues = {"RUTH": CUES[sc][0], "SAM": CUES[sc][1]}
    prev = None
    for n, b in enumerate(beat_scene["beats"], start=1):
        g_id = gid(sc, n)
        assert b["generation_id"] == g_id
        r_key, s_key, _ = timeline[sc][n - 1]
        keys = {"RUTH": r_key, "SAM": s_key}
        end_state = gid(sc, n + 1) if n < 25 else f"{sc}_end"
        base = {"generation_id": g_id, "scene_id": sc, "start_state": g_id, "end_state": end_state,
                "previous_generation_id": prev, "sfx": [], "readout": [], "duration_s": 6, "version": 1}
        est = PRIOR_BOTH[-1] if PRIOR_BOTH else None
        if b["kind"] == "dialogue":
            who, listener = b["speaker"], other(b["speaker"])
            words = len(b["text_en"].split())
            act_end = round(min(5.5, 0.5 + words / 2.6), 1)
            sx = keys[who]
            kind = KIND[sx]
            line_no = LINES[sc][b["text_en"]]
            manner = MANNER[sc]
            # the stage action in beats.json must agree with the position this author tracks
            claim = b["stage_action"]
            expect = {"counter": ("behind the counter", "customer side"), "door": ("doorway",),
                      "bstand": ("beside the booth", "beside the near booth seat"),
                      "bseat": ("seated on the near booth seat", "seated on the far booth seat")}[kind]
            if not any(e in claim for e in expect) and "remains standing in a static" not in claim.split(
                    "behind")[0][:60] + "remains standing in a static":
                raise SystemExit(f"{g_id}: tracked position {sx} disagrees with beat: {claim[:90]}")
            ph = [("SETUP", 0.0, 0.5, f"{who} looks at {listener}", ""),
                  ("ACTION", 0.5, act_end, f"{who} speaks to {listener} {manner}", ""),
                  ("HOLD", act_end, 6.0, f"{who} holds {listener}'s look, quite still", "")]
            g = dict(base, coverage="SINGLE", subject=who, foreground="", visible=[who], dialogue=[line_no],
                     choreography={"generation_id": g_id, "phases": phases(*ph), "once_actions": [f"{who} speaks to {listener}"],
                                   "gesture_budget": 1, "performance": [perf(who, cues[who])]},
                     design_refs=[], camera=cam("CLOSE", COMPOSE[sx], repeat=REPEAT),
                     camera_position=CAMPOS[kind][0 if who == "SAM" else 1], addressees={str(line_no): [listener]},
                     listener_anchors={listener: anchor_for(listener, keys[listener], est)}, gaze_target=listener)
            if who == "SAM" and kind == "door":
                g["camera_position"] = "cB_door"
            if who == "RUTH" and kind in ("door",):
                g["camera_position"] = "cC_ctr"
        elif b["kind"] == "reaction":
            who, text, gaze = REACTIONS[(sc, n)]
            listener = other(who)
            sx = keys[who]
            kind = KIND[sx]
            ph = [("SETUP", 0.0, 1.5, f"{who} looks toward {listener if gaze in ('RUTH', 'SAM') else 'the table'}", ""),
                  ("ACTION", 1.5, 2.4, text, "glance"),
                  ("CONSEQUENCE", 2.4, 4.0, f"{who} stays with what they see", ""),
                  ("HOLD", 4.0, 6.0, f"{who} holds the quiet look, nobody speaks", "")]
            g = dict(base, coverage="SINGLE", subject=who, foreground="", visible=[who], dialogue=[],
                     choreography={"generation_id": g_id, "phases": phases(*ph), "once_actions": [text],
                                   "gesture_budget": 1, "performance": [perf(who, cues[who])]},
                     design_refs=[], camera=cam("CLOSE", COMPOSE[sx], repeat=REPEAT),
                     camera_position=CAMPOS[kind][0 if who == "SAM" else 1], gaze_target=gaze)
            g["listener_anchors"] = {listener: anchor_for(listener, keys[listener], est)}
        else:
            a = ACTIONS[(sc, n)]
            kind = a["cam"]
            visible = a["visible"]
            g = dict(base, coverage=a["cov"], subject=a["subject"], foreground="", visible=visible, dialogue=[],
                     choreography={"generation_id": g_id, "phases": a["ph"], "once_actions": a["once"], "gesture_budget": 1,
                                   "performance": [perf(a["who"], cues[a["who"]])]},
                     design_refs=[], camera=cam("WIDE", MASTER_TXT[kind], "WIDE_ESTABLISH"),
                     camera_position={"counter": "cA_ctr", "booth": "cA_bth"}[kind])
            if a.get("close"):
                g["camera"] = cam("CLOSE", a["close"][1], repeat=REPEAT)
                g["camera_position"] = {"counter": "cB_ctr", "booth": "cB_bth"}[kind]
            if a.get("gaze"):
                g["gaze_target"] = a["gaze"]
            if len(visible) == 1:  # the other person is in the room, out of frame: place them so the prompt does not summon a stranger
                absent = other(visible[0])
                g["listener_anchors"] = {absent: anchor_for(absent, keys[absent], est)}
            if a.get("tracked"):
                pass
            if len(visible) == 2:
                PRIOR_BOTH.append(g_id)
        gens.append(g)
        prev = g_id

# a generation after an off-screen walk starts from a changed place: mark the deliberate skip
BY_ID = {g["generation_id"]: g for g in gens}
BY_ID["SC02_g02"]["handoff_ellipsis"] = "SAM's last steps to the booth happen off screen during the previous generation"
BY_ID["SC10_g09"]["handoff_ellipsis"] = "SAM's last steps to the doorway happen off screen during the previous generation"

# --------------------------------------------------------------------------------------------------------------------
# 03_preprod
# --------------------------------------------------------------------------------------------------------------------
# 30 (film06: 28): SC11 and SC12 carry 273 / 266 words in 150 s, over the scaled 262 of the default; speech stays 109 s of 150 s
feas = {"max_speakers": 2, "max_in_frame": 3, "max_dialogue_syllables": 30, "scene_duration_s": 16.0, "min_silence_s": 3.0,
        "syllables_per_second": 2.5}
layout = {
    "zones": [{"id": "counter_zone", "label": "counter and back shelf", "box": [0.3, 0.05, 0.95, 0.5]},
              {"id": "booth_zone", "label": "red booth", "box": [0.05, 0.55, 0.55, 0.95]},
              {"id": "door_zone", "label": "open doorway", "box": [0.7, 0.55, 0.95, 0.95]}],
    "objects": [
        {"id": "counter", "label": "long counter", "zone": "counter_zone",
         "placement": "runs along the room, RUTH's side behind it, the customer side in front", "at": [0.6, 0.3]},
        {"id": "back_shelf", "label": "back shelf of white mugs", "zone": "counter_zone",
         "placement": "on the wall behind the counter", "at": [0.6, 0.08]},
        {"id": "front_window", "label": "pale front window", "zone": "counter_zone",
         "placement": "in the front wall beside the counter, daylight outside", "at": [0.9, 0.3]},
        {"id": "doorway", "label": "open doorway", "zone": "door_zone",
         "placement": "in the front wall at the right edge of the counter frame, daylight outside", "at": [0.85, 0.75]},
        {"id": "booth_table", "label": "booth table", "zone": "booth_zone",
         "placement": "between the two high red vinyl booth seats", "at": [0.3, 0.75]},
        {"id": "seat_left", "label": "high red vinyl booth seat", "zone": "booth_zone",
         "placement": "along the left side of the booth table (the far seat)", "at": [0.15, 0.75]},
        {"id": "seat_right", "label": "high red vinyl booth seat", "zone": "booth_zone",
         "placement": "along the right side of the booth table (the near seat)", "at": [0.45, 0.75]},
    ],
    "cameras": [
        {"id": "cA_ctr", "zone": "counter_zone", "view": MASTER_TXT["counter"],
         "sees": ["counter", "back_shelf", "front_window", "doorway"], "at": [0.75, 0.5], "look_at": "counter"},
        {"id": "cB_ctr", "zone": "counter_zone",
         "view": "close on SAM on the customer side of the counter, daylight window behind him",
         "sees": ["counter", "front_window"], "at": [0.55, 0.45], "look_at": "counter"},
        {"id": "cC_ctr", "zone": "counter_zone", "view": "close on RUTH behind the counter, the back shelf behind her",
         "sees": ["counter", "back_shelf"], "at": [0.8, 0.45], "look_at": "back_shelf"},
        {"id": "cB_door", "zone": "door_zone", "view": "close on SAM in the open doorway, daylight behind him",
         "sees": ["doorway"], "at": [0.75, 0.6], "look_at": "doorway"},
        {"id": "cA_bth", "zone": "booth_zone", "view": MASTER_TXT["booth"],
         "sees": ["booth_table", "seat_left", "seat_right"], "at": [0.3, 0.92], "look_at": "booth_table"},
        {"id": "cB_bth", "zone": "booth_zone", "view": "close on SAM at the near booth seat, high red booth back behind him",
         "sees": ["booth_table", "seat_right"], "at": [0.2, 0.9], "look_at": "seat_right"},
        {"id": "cC_bth", "zone": "booth_zone", "view": "close on RUTH at the far booth seat, high red booth back behind her",
         "sees": ["booth_table", "seat_left"], "at": [0.4, 0.9], "look_at": "seat_left"},
    ],
    "marks": [
        {"id": "ctr_ruth", "at": [0.6, 0.15], "zone": "counter_zone"},
        {"id": "ctr_sam", "at": [0.6, 0.42], "zone": "counter_zone"},
        {"id": "door_sam", "at": [0.85, 0.72], "zone": "door_zone"},
        {"id": "bth_ruth_stand", "at": [0.12, 0.65], "zone": "booth_zone"},
        {"id": "bth_sam_stand", "at": [0.48, 0.65], "zone": "booth_zone"},
        {"id": "bth_ruth_seat", "at": [0.15, 0.75], "zone": "booth_zone"},
        {"id": "bth_sam_seat", "at": [0.45, 0.75], "zone": "booth_zone"},
    ],
}

designs = {
    "RUTH_look": {"kind": "look", "version": 1, "owner": "RUTH", "note": "locked CharacterLook text (film06 look reused)"},
    "RUTH_costume": {"kind": "costume", "version": 1, "owner": "RUTH", "note": "pale blue diner uniform dress, white apron"},
    "SAM_look": {"kind": "look", "version": 1, "owner": "SAM", "note": "locked CharacterLook text (film06 look reused)"},
    "SAM_costume": {"kind": "costume", "version": 1, "owner": "SAM", "note": "grey hoodie, hood down; shoes now dry"},
    f"loc_{LOC}": {"kind": "location", "version": 1, "owner": LOC, "note": "diner counter, doorway, window and booth by morning light"},
}
PROP_NOTE = {
    "prop_notice": "the closure notice is a controlled static graphic: its words are composited and checked in post, never trusted to the model",
    "prop_open": "the OPEN card is a controlled static graphic: its word is composited and checked in post, never trusted to the model",
}
for key, did in PROPS.items():
    designs[did] = {"kind": "prop", "version": 1, "prop": key.rstrip(":"), "note": PROP_NOTE.get(did, "plain prop, no readable text")}

scenes = {}
for i, sc in enumerate(SC, start=1):
    cfg = SC[sc]
    scenes[sc] = {
        "location": LOC,
        "axis": {"scene_id": sc, "axis_pair": ["RUTH", "SAM"], "sides": {"RUTH": "LEFT", "SAM": "RIGHT"}},
        "occupancy": {"scene_id": sc, "initial": ["RUTH", "SAM"], "events": []},
        "story_time": ({"scene_id": sc, "story_order": float(i), "transition_in": "LINEAR", "marker": "", "source_conflict": ""} if i == 1 else
                       {"scene_id": sc, "story_order": float(i), "transition_in": "ELLIPSIS", "source_conflict": "",
                        "marker": "a few minutes later the same morning: the two of them are in a new part of the diner and on a new topic"}),
        "extras": "",
        "lighting": LIGHT[cfg["light"]],
        "encounter_id": "first_morning",
    }


def rights_entry(subject, kind, note):
    return {"subject": subject, "kind": kind, "status": "original", "evidence": OWNER_EVIDENCE, "note": note}


rights = [
    rights_entry("RUTH", "character", "fictional character; generated likeness reused from film06 (Owner-accepted); originality approved by the Owner for film07"),
    rights_entry("SAM", "character", "fictional character; generated likeness reused from film06 (Owner-accepted); originality approved by the Owner for film07"),
    rights_entry(LOC, "location", "fictional diner; reuses the film06 red booth and adds a new counter, doorway and early-morning light; extension approved by the Owner for film07"),
    {"subject": "none (room tone and SFX are generated or CC0)", "kind": "music", "status": "original",
     "evidence": OWNER_EVIDENCE, "note": "no music in film07 (Owner-approved summary: no music)"},
    rights_entry("script.fountain", "source", "original script, model-written for film07; no outside text"),
    rights_entry("none (no real person's likeness)", "likeness", "faces are generated, not modelled on a real person"),
]

preprod = {
    "feasibility": feas,
    "preflight": {"max_prompt_words": 230,   # 215 + the two SC03+ safeguard sentences (<= 229 words, film02 ran 165-220)
                  "timing": {"duration_s": 6.0, "max_shots": 1, "min_shot_s": 2.0, "syllables_per_second": 2.5,
                             "establish_s": 1.5, "reaction_s": 3.0},
                  "feasibility": feas, "interaction_contract": True,
                  # video prompt: off-screen listener fully out of frame + "No one speaks."; SC01-SC02 have accepted takes
                  "safeguard_scenes": [f"SC{n:02d}" for n in range(3, 13)]},
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
        LOC: {"look": {"look_id": LOC, "location": "KELLER'S DINER", "text": LOC_TEXT,
                       "invariants": ["long counter with red vinyl stools", "back shelf of white mugs", "pale front window",
                                      "open doorway on the right", "high red vinyl booth on the left"],
                       "interior": True, "time_of_day": "", "weather_outside": "",
                       "environment_rules": ["soft daylight from the front window stays steady the whole shot; nobody else is in the diner"], "approved": True},
              "room_tone": "quiet empty diner, a refrigerator hum, a clock ticking, faint street air through the open door",
              "layout": layout}
    },
    "scenes": scenes,
    "states": states,
    "still_templates": {
        "framing": {"MASTER": "wide shot of the diner with both people in frame",
                    "OTS": "medium over-the-shoulder shot of the two people",
                    "SINGLE": "close-up of one person, head and shoulders, the counter or booth edge low in the frame",
                    "TWO_SHOT": "medium two-shot of both people",
                    "REACTION": "close-up of one person listening"},
        "character": "Photoreal character reference portrait, 16:9, plain warm grey studio backdrop, head and shoulders, front view, neutral expression, soft even light: {text}. No text, no logos.",
        "plate": "Photoreal empty set plate, 16:9, eye-level wide view, nobody in the room: {text}. No people, no text, no logos.",
        "pose": True,
    },
    "accepted_overlong": {},
    "designs": designs,
    "rights": rights,
    "risk_fallbacks": {},
    "stills": {},
}
old = HERE / "03_preprod.json"
if old.exists():
    try:
        prev = json.loads(old.read_text(encoding="utf-8"))
        preprod["stills"] = prev.get("stills", {})
        preprod["accepted_overlong"] = prev.get("accepted_overlong", {})
        preprod["risk_fallbacks"] = prev.get("risk_fallbacks", {})
    except json.JSONDecodeError:
        pass

# pin design versions the way the shot depends on them
typed_pre = PreprodSection.model_validate(preprod)
for g in gens:
    decl = ShotDecl.model_validate(g)
    g["design_refs"] = [f"{d}@{typed_pre.designs[d].version}" for d in shot_design_ids(typed_pre, decl)]
    # the tracked-still declarations are optional; none are used for the pilot

shots = {"generations": gens, "history": []}
old_shots = HERE / "04_shots.json"
if old_shots.exists():
    try:
        shots["history"] = json.loads(old_shots.read_text(encoding="utf-8")).get("history", [])
    except json.JSONDecodeError:
        pass

# --------------------------------------------------------------------------------------------------------------------
# 01_story
# --------------------------------------------------------------------------------------------------------------------
SC_STORY = {
    "SC01": ("Establish the first morning, the counter and the CLOSED PERMANENTLY notice.",
             "Sam came to start work; Ruth let the notice stand unexplained.",
             "Ruth admits the closure notice predates her offer; Sam asks what he is there for.", "trust", "-"),
    "SC02": ("Name the pity Sam suspects and the last morning Ruth planned.",
             "Sam wants the truth about the invitation; Ruth wants one proper morning before she closes.",
             "Ruth admits she planned a last morning together; Sam insists they talk about real work.", "trust", "+"),
    "SC03": ("Find one small, definite place to begin.",
             "Sam needs a clear task; Ruth has forgotten how to explain the work.",
             "They define one counter station and Ruth admits she needs help explaining.", "trust", "+"),
    "SC04": ("Settle pay for the morning and what is not promised.",
             "Sam asks for pay and a defined shift; Ruth cannot promise a next one.",
             "A paid three-hour morning; no further shift promised.", "trust", "+"),
    "SC05": ("Separate Sam's savings and the old money from the job.",
             "Sam fears the job is a repayment; Ruth fears she has hidden too much.",
             "Sam keeps his savings; the job must stand on its own terms.", "trust", "+"),
    "SC06": ("Ruth says why she was closing and what she cannot manage.",
             "Ruth would rather hide behind the notice; Sam asks her to say what she wants.",
             "Ruth chooses to test a smaller opening instead of closing or pretending.", "trust", "+"),
    "SC07": ("Define what the diner can honestly offer with two inexperienced hands.",
             "Ruth wants to open everything again; Sam needs instructions that hold.",
             "Counter-only service; Ruth owns telling people the limits.", "trust", "+"),
    "SC08": ("Test whether a trial week is funded or only hoped for.",
             "Sam will not work on hope; Ruth will not take his savings.",
             "A finite wage reserve is identified and may not become Sam's investment.", "trust", "+"),
    "SC09": ("Agree how training, corrections and refusals will work.",
             "Mistakes are certain; blame is not.",
             "Both accept the rules: ask, explain, pay for time, stop rather than hide mistakes.", "trust", "+"),
    "SC10": ("Give Sam room to choose without guilt, then hear what he decides.",
             "Sam's habit of leaving before he is refused against Ruth's wish not to pressure him.",
             "Sam returns with a conditional offer of one week, not a rescue promise.", "trust", "+"),
    "SC11": ("Turn the offer into mutual terms.",
             "Hours, pay, cancellation and no promise of survival.",
             "Five paid mornings, daily check-ins and a decision after the trial.", "trust", "+"),
    "SC12": ("Begin a modest real shift instead of celebrating a rescue.",
             "A tired owner and a careful employee find the first task.",
             "Sam sets the OPEN card on the counter; the trial begins and the future stays uncertain.", "trust", "+"),
}
story = {
    "concept": "On his first morning at Ruth Keller's diner Sam Doyle finds a closure notice and has to learn whether the job is real before he works a single shift.",
    "theme": "A kindness is only fair when it can be refused: the truth and clear terms come before any promise.",
    "genre": "Quiet two-hander drama (a long conversation at a diner counter and booth, about 27 minutes)",
    "audience": {"who": "General online audience watching English-language dramas with Vietnamese subtitles; anyone who has been offered help that felt like pity.",
                 "expectation": "A patient, realistic negotiation between two decent people that ends on a small, honest start, not a rescue."},
    "premise": "Ruth Keller offered Sam Doyle a job at her diner; on the morning of his first shift he finds a printed CLOSED PERMANENTLY notice on the counter and asks whether the offer was ever real.",
    "central_conflict": "Sam wants a real job on fair, clear terms and refuses to be anyone's rescuer; Ruth wants one last good morning and cannot admit she cannot run the place alone.",
    "logline": {"text": "On his first morning, Sam Doyle finds a closure notice in Ruth Keller's diner and asks her for the truth, so a real, paid trial of the job can begin on fair terms.",
                "protagonist": "SAM", "goal": "a real, paid job on fair terms", "obstacle": "Ruth hid that she planned to close"},
    "structure": [
        {"id": "ACT1", "name": "The notice", "beats": [
            {"id": "B1", "function": "SETUP", "scene_ids": ["SC01"], "summary": "Sam arrives on time and sees the notice; Ruth admits it was printed before her offer."},
            {"id": "B2", "function": "INCITING", "scene_ids": ["SC02"], "summary": "Ruth admits she planned a last morning; Sam demands to talk about real work."}]},
        {"id": "ACT2", "name": "Terms", "beats": [
            {"id": "B3", "function": "ESCALATION", "scene_ids": ["SC03"], "summary": "They start with one counter station and clear instructions."},
            {"id": "B4", "function": "ESCALATION", "scene_ids": ["SC04"], "summary": "Pay for the morning is settled; no later shift is promised."},
            {"id": "B5", "function": "MIDPOINT", "scene_ids": ["SC05"], "summary": "Sam's savings and the old money are separated from the job."},
            {"id": "B6", "function": "CRISIS", "scene_ids": ["SC06"], "summary": "Ruth says what she cannot manage and chooses to test a smaller opening."},
            {"id": "B7", "function": "CRISIS", "scene_ids": ["SC07"], "summary": "They define a counter-only service with two seats."},
            {"id": "B8", "function": "CRISIS", "scene_ids": ["SC08"], "summary": "A finite wage reserve is named; Sam's savings may not fill gaps."},
            {"id": "B9", "function": "CRISIS", "scene_ids": ["SC09"], "summary": "They agree how mistakes, corrections and refusals work."}]},
        {"id": "ACT3", "name": "The trial", "beats": [
            {"id": "B10", "function": "CLIMAX", "scene_ids": ["SC10"], "summary": "Sam steps to the doorway to choose freely and returns with a conditional offer of one week."},
            {"id": "B11", "function": "CLIMAX", "scene_ids": ["SC11"], "summary": "Five paid mornings, daily checks and a decision after the trial, with no promise of survival."},
            {"id": "B12", "function": "RESOLUTION", "scene_ids": ["SC12"], "summary": "The first task is given; Sam sets an OPEN card on the counter."}]},
    ],
    "plot": ("Sam arrives on time for his first shift and finds the closure notice (SC01); Ruth admits she planned a last morning (SC02). "
             "They begin with one small station (SC03), settle pay (SC04), separate Sam's savings and the old money from the job (SC05), "
             "Ruth says why she was closing (SC06), and they define a smaller opening (SC07), a finite wage reserve (SC08) and rules for "
             "mistakes (SC09). Sam goes to the doorway to choose freely and returns with a conditional offer (SC10); they fix five paid "
             "mornings (SC11) and begin the first task, Sam setting an OPEN card on the counter (SC12)."),
    "subplots": [],
    "characters": {
        "SAM": {"id": "SAM", "name": "Sam Doyle", "role": "protagonist",
                "want": "A real job on clear terms, and a true answer about why he was asked.",
                "need": "To choose to stay for his own reasons, not to repay or rescue.",
                "flaw": "He leaves places before anyone can turn him down.",
                "arc_change": "From waiting to be refused to choosing the trial week himself, on his own terms.",
                "change_scene_id": "SC10"},
        "RUTH": {"id": "RUTH", "name": "Ruth Keller", "role": "supporting",
                 "want": "One proper morning, and someone to share the work.",
                 "need": "To say plainly what she can and cannot do and ask for help.",
                 "flaw": "She hides what she plans behind dry, practical remarks.",
                 "arc_change": "From letting a printed notice decide for her to choosing a smaller opening in her own words.",
                 "change_scene_id": "SC06"},
    },
    "scenes": {sc: {"purpose": p, "conflict": c, "outcome": o, "value": v, "shift": s} for sc, (p, c, o, v, s) in SC_STORY.items()},
    "source_note": ("Original script written for this film; the two characters, the diner and their earlier conversation come from film06 "
                    "(Owner-accepted) as visual references only: no film06 line, ending or outcome is changed. Names, events and "
                    "dialogue of film07 are new; no outside text."),
    "rewrite_log": [
        {"version": 1, "date": "2026-11-10", "reason": "First draft by Codex for Owner review (docs/production/pilots/film07_first_shift).",
         "changed": "docs/production/pilots/film07_first_shift/script.fountain, beats.json"},
        {"version": 2, "date": "2026-11-11",
         "reason": ("Owner approved the film ('Duyệt, chạy pilot'); package built from the approved draft without a change of meaning, "
                    "dialogue or order. Only the scene headings (area moved to an [[area:]] note so the parser reads the time of day) "
                    "and the front matter changed; draft script SHA-256 c45ac9dcdfc09cefb4f11c8efc868ed132aa0c288d379c991eb856c4ec3bf92c."),
         "changed": "films/film07_first_shift/script.fountain"},
    ],
}

# --------------------------------------------------------------------------------------------------------------------
# 02_direction
# --------------------------------------------------------------------------------------------------------------------
def dl(sc, n):
    b = BEATS["scenes"][int(sc[2:]) - 1]["beats"][n - 1]
    return b["text_en"]


FACTS = [
    ("diner_closing", "A printed notice says the diner is closing permanently", "SC01_g10",
     [("DIALOGUE", "SC01_g10")]),
    ("notice_before_offer", "The closure notice was printed before Ruth offered Sam the job", "SC01_g23",
     [("DIALOGUE", "SC01_g22")]),
    ("last_morning_planned", "Ruth planned this as one last proper morning before closing", "SC02_g12",
     [("DIALOGUE", "SC02_g11")]),
    ("ruth_cannot_run_alone", "Ruth cannot open and close everything alone any more", "SC06_g09",
     [("DIALOGUE", "SC06_g08")]),
    ("two_seat_counter", "The diner will open as a two-seat counter with coffee and toast", "SC07_g19",
     [("DIALOGUE", "SC07_g18")]),
    ("wage_reserve", "There is a fixed wage reserve for the trial week, 225 dollars", "SC08_g18",
     [("DIALOGUE", "SC08_g17")]),
    ("trial_terms", "Sam and Ruth agree five paid mornings and a decision after the trial", "SC11_g21",
     [("DIALOGUE", "SC11_g01"), ("DIALOGUE", "SC11_g12")]),
    ("open_card", "The diner puts up an OPEN card; the trial begins", "SC12_g25",
     [("DIALOGUE", "SC12_g23"), ("VISUAL", "SC12_g25")]),
]
facts = []
for fid, text, needed, carriers in FACTS:
    cl = []
    for kind, g_id in carriers:
        sc, n = g_id.split("_g")[0], int(g_id.split("_g")[1])
        detail = dl(sc, n) if kind == "DIALOGUE" else "SAM sets the small OPEN card on the counter"
        cl.append({"kind": kind, "generation_id": g_id, "detail": detail})
    facts.append({"fact_id": fid, "text": text, "needed_by": needed, "carriers": cl})

KNOWN_AFTER = {"SC01": ["diner_closing", "notice_before_offer"], "SC02": ["last_morning_planned"], "SC06": ["ruth_cannot_run_alone"],
               "SC07": ["two_seat_counter"], "SC08": ["wage_reserve"], "SC11": ["trial_terms"], "SC12": ["open_card"]}
known: list[str] = []
POV = {"SC01": "SAM", "SC02": "SAM", "SC03": "SAM", "SC04": "SAM", "SC05": "SAM", "SC06": "RUTH", "SC07": "RUTH",
       "SC08": "SAM", "SC09": "SAM", "SC10": "SAM", "SC11": "RUTH", "SC12": "SAM"}
CURVE = {"SAM": [(3, 3), (3, 4), (3, 2), (2, 3), (3, 3), (3, 2), (2, 2), (2, 3), (3, 2), (2, 3), (3, 2), (2, 1)],
         "RUTH": [(2, 3), (3, 3), (3, 2), (2, 3), (3, 2), (2, 3), (3, 2), (2, 3), (3, 2), (2, 3), (3, 2), (2, 2)]}
EMPH = {"SC01": ("Ruth admits the notice was printed before her offer", "hold", "SC01_g22", "notice_before_offer"),
        "SC02": ("Ruth names the last morning she planned", "hold", "SC02_g11", "last_morning_planned"),
        "SC11": ("Sam holds a quiet look before the terms are sealed", "reaction", "SC11_g13", "trial_terms"),
        "SC12": ("Sam sets the OPEN card on the counter", "hold", "SC12_g25", "open_card")}
HOLDS = {"SC01": ("SC01_g22", 1.0, "hold on Ruth after she admits the notice came first"),
         "SC02": ("SC02_g11", 1.0, "hold on Ruth after she names the last morning"),
         "SC03": ("SC03_g13", 3.0, "Sam's quiet look at the two mugs"),
         "SC04": ("SC04_g14", 3.0, "Ruth's quiet moment of admission"),
         "SC05": ("SC05_g06", 3.0, "Sam's easing jaw"),
         "SC06": ("SC06_g13", 3.0, "Ruth sits quietly with the choice"),
         "SC07": ("SC07_g18", 1.0, "hold on Ruth agreeing to two seats"),
         "SC08": ("SC08_g18", 3.0, "Sam takes his time before the next question"),
         "SC09": ("SC09_g25", 1.0, "hold on Ruth admitting she is still learning"),
         "SC10": ("SC10_g25", 1.0, "hold on Ruth answering as an employer"),
         "SC11": ("SC11_g13", 3.0, "Sam's deliberate look"),
         "SC12": ("SC12_g25", 1.5, "the OPEN card stays still on the counter")}
scenes_dir = {}
for i, sc in enumerate(SC):
    known = sorted(set(known) | set(sum((KNOWN_AFTER.get(s, []) for s in list(SC)[:i + 1]), [])))
    scenes_dir[sc] = {
        "pov": {"whose": POV[sc], "audience_knows": list(known), "characters_know": {"SAM": list(known), "RUTH": list(known)}},
        "emphasis": ([{"moment": EMPH[sc][0], "device": EMPH[sc][1], "generation_id": EMPH[sc][2], "fact_id": EMPH[sc][3]}]
                     if sc in EMPH else []),
        "curve": {"SAM": {"start": CURVE["SAM"][i][0], "end": CURVE["SAM"][i][1]},
                  "RUTH": {"start": CURVE["RUTH"][i][0], "end": CURVE["RUTH"][i][1]}},
        "pacing": {"target_avg_shot_s": 6.0, "holds": [{"generation_id": HOLDS[sc][0], "seconds": HOLDS[sc][1], "why": HOLDS[sc][2]}]},
        "transition_in": ({"kind": "CUT", "reason": "title card, then a hard cut into the diner at dawn"} if sc == "SC01" else
                          {"kind": "CUT", "reason": "continuous morning, the same two people"}),
        "transition_out": {"kind": "CUT", "reason": "continuous morning, the same two people"},
    }

translations = {"THE FIRST SHIFT": "CA LÀM ĐẦU TIÊN", "owns the diner": "chủ quán ăn", "starting his first shift": "bắt đầu ca làm đầu tiên"}
for sc in BEATS["scenes"]:
    for b in sc["beats"]:
        if b["kind"] == "dialogue":
            translations[b["text_en"]] = b["text_vi"]

by_scene_cov: dict[str, set[str]] = {}
for g in gens:
    by_scene_cov.setdefault(g["scene_id"], set()).add(g["coverage"])
coverage_plan = {}
for act in story["structure"]:
    for beat in act["beats"]:
        have = set().union(*(by_scene_cov[s] for s in beat["scene_ids"]))
        coverage_plan[beat["id"]] = [c for c in ("MASTER", "SINGLE") if c in have]

direction = {
    "vision": {"tone": "Plain, patient and close: two people talking at a diner counter and booth in early light, the turns carried by faces and small pauses, never by speeches or camera tricks.",
               "references": ["an empty diner at dawn seen at standing and seated eye level, cool window light warming through the morning",
                              "a low-key negotiation drama played in pauses and glances"]},
    "visual_rules": [
        {"rule": "Static eye-level camera, no dutch angles, no handheld shake.", "why": "The turn comes from Ruth's face and Sam's answer, not from the camera."},
        {"rule": "Keep Ruth screen-left and Sam screen-right in every shot of the counter and the booth.", "why": "The distance between them stays readable and the cut never flips who is where."},
        {"rule": "One person moves or handles one prop at a time, never together; no hand-over and no contact.", "why": "Hands on small props and two bodies in contact are the least reliable things the video model does (film01, film04)."},
        {"rule": "Singles keep the counter edge or the high red booth back in frame.", "why": "film05: a close single at table height reads as standing or seated by chance; the furniture makes posture readable."},
        {"rule": "The closure notice and the OPEN card are static graphics composited and checked in post.", "why": "Generated text on a prop cannot be trusted to read correctly."},
    ],
    "reveals": [{"fact_id": "notice_before_offer", "scene_id": "SC01"}, {"fact_id": "last_morning_planned", "scene_id": "SC02"},
                {"fact_id": "trial_terms", "scene_id": "SC11"}, {"fact_id": "open_card", "scene_id": "SC12"}],
    "coverage_plan": coverage_plan,
    "scenes": scenes_dir,
    "comprehension": {
        "intros": [{"character": "RUTH", "label": "RUTH KELLER", "relation": "owns the diner", "needed_by": "SC01_g02", "carriers": []},
                   {"character": "SAM", "label": "SAM DOYLE", "relation": "starting his first shift", "needed_by": "SC01_g01", "carriers": []}],
        "facts": facts,
        "tags": [{"character": "SAM", "generation_id": "SC01_g01", "start_s": 0.3, "end_s": 3.3, "anchor_x": None, "anchor_y": None},
                 {"character": "RUTH", "generation_id": "SC01_g02", "start_s": 0.3, "end_s": 3.3, "anchor_x": None, "anchor_y": None}],
        "cards": [],
    },
    "translations": translations,
}

(HERE / "01_story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "02_direction.json").write_text(json.dumps(direction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "03_preprod.json").write_text(json.dumps(preprod, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "04_shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote script + 01-04:", len(gens), "generations,", sum(g["duration_s"] for g in gens), "s")
