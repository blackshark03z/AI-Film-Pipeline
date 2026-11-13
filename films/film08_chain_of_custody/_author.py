"""Authoring helper for film08 "Chain of Custody": script.fountain, 01_story, 02_direction, 03_preprod, 04_shots.

Re-run after edits (python films/film08_chain_of_custody/_author.py). Inputs: the Owner-approved draft under
docs/production/pilots/film08_chain_of_custody (beats.json: 12 scenes x 25 generations, script.fountain).
Registered stills / history in 03_preprod.json and 04_shots.json are kept across re-runs.

Adapted from films/film07_first_shift/_author.py. Staging rules (film05..film07 lessons): one location, static
eye-level camera; dialogue = a CLOSE single of the speaker with every listener OFF_FRAME and "No one speaks." for silent
shots; one prop action per action generation, one actor at a time, no hand-overs and no contact; handedness stated in
both frames; locked looks are never re-described in prompts; props are preset between scenes. Three people share the
room (SC01-SC11: HOLLIS, ELI, NAOMI; SC12: ELI, CALVIN, NAOMI), so a close single anchors only the person addressed.

Reference images do not exist yet: media/stills/char_<NAME>.png and plate_records_room.png are planned paths. Nothing
here records an approval or a hash for them (images are found by file name, never listed in 03_preprod.json).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
from film_pipeline.drama.script import parse_fountain  # noqa: E402
from film_pipeline.production.sections import PreprodSection, ShotDecl, shot_design_ids  # noqa: E402

DRAFT = REPO / "docs/production/pilots/film08_chain_of_custody"
BEATS = json.loads((DRAFT / "beats.json").read_text(encoding="utf-8"))
DRAFT_SHA = hashlib.sha256((DRAFT / "script.fountain").read_bytes()).hexdigest()
SRT_SHA = "f5f9b7c219233b8eeea7e3f0649f1b2e74b7830580808b5ec52c4b44d40b6787"
OWNER_EVIDENCE = ("Owner-approved brief 2026-11-14 (\"Approve, write the script\"): "
                  "docs/production/pilots/film08_chain_of_custody/BRIEF.md line 3; budget cap in BUDGET.md")
REFS_JSON = HERE / "media/stills/references.json"
REFS = {r["file"]: r for r in json.loads(REFS_JSON.read_text(encoding="utf-8"))["refs"]}
for _f, _r in REFS.items():  # the recorded hash must match the file on disk; never invent one
    assert hashlib.sha256((HERE / "media/stills" / _f).read_bytes()).hexdigest() == _r["sha256"], _f
REF_EVIDENCE = "films/film08_chain_of_custody/media/stills/references.json"


def ref_note(fname):
    r = REFS[fname]
    return f"reference {fname} sha256 {r['sha256']}, {r['review']}, {r['approved_by']} {r['approved_at']} ({REF_EVIDENCE})"


SC12_SHARES_ENCOUNTER = True  # see the encounter note in the scenes block

# --------------------------------------------------------------------------------------------------------------------
# script.fountain: the approved draft with the SC12 heading normalised for the parser (time of day AFTERNOON)
# --------------------------------------------------------------------------------------------------------------------
def build_script() -> str:
    draft = (DRAFT / "script.fountain").read_text(encoding="utf-8").replace("\r\n", "\n")
    draft = draft.replace(
        "Format: 12 scenes;",
        f"Approval: Owner 2026-11-14 (BRIEF.md, BUDGET.md); source draft SHA-256 {DRAFT_SHA}\n"
        "Format: 12 scenes;", 1)
    draft = draft.replace(
        "INT. LINWOOD COUNTY COURTHOUSE - RECORDS ROOM - AFTERNOON, ONE MONTH LATER",
        "INT. LINWOOD COUNTY COURTHOUSE - RECORDS ROOM - AFTERNOON\n\n[[one month later]]")
    return draft.rstrip("\n") + "\n"


SCRIPT_TEXT = build_script()
(HERE / "script.fountain").write_text(SCRIPT_TEXT, encoding="utf-8", newline="\n")
SCRIPT = parse_fountain(SCRIPT_TEXT)
assert len(SCRIPT.scenes) == 12
LINES: dict[str, dict[str, int]] = {}
for _s in SCRIPT.scenes:
    LINES[_s.scene_id] = {}
    for _e in _s.elements:
        if _e.kind == "dialogue":
            assert _e.text not in LINES[_s.scene_id], f"{_s.scene_id}: duplicate dialogue text {_e.text!r}"
            LINES[_s.scene_id][_e.text] = _e.line_no

# --------------------------------------------------------------------------------------------------------------------
# looks, places, props
# --------------------------------------------------------------------------------------------------------------------
LOOKS = {
    "NAOMI": ("naomi_coat", "woman in her late thirties, short natural hair, calm composed face, gold stud earrings, long cream coat over a navy blouse",
              ["short natural hair", "long cream coat", "navy blouse", "gold stud earrings"]),
    "HOLLIS": ("hollis_khaki", "man of about fifty-five, weathered tired face, sandy-grey hair, tan county uniform shirt "
               "with brown epaulettes and a dark tie", ["sandy-grey hair", "tan county uniform shirt", "brown epaulettes", "dark tie"]),
    "ELI": ("eli_khaki", "man of about twenty-six, short black hair, clean-shaven, tan county uniform shirt, a small body camera "
            "clipped to his chest with a steady green light and a radio on his left shoulder",
            ["short black hair", "tan county uniform shirt", "chest body camera", "left shoulder radio"]),
    "CALVIN": ("calvin_jacket", "man of about forty-five, close-cropped greying hair, short grey beard, tired face, green canvas jacket over a grey t-shirt",
               ["close-cropped greying hair", "short grey beard", "green canvas jacket", "grey t-shirt"]),
}
VOICE = {"NAOMI": "calm, even female voice", "HOLLIS": "low, gravelly male voice", "ELI": "young, careful male voice",
         "CALVIN": "slow, low male voice"}
HANDLE = {"NAOMI": "the woman", "HOLLIS": "the older man", "ELI": "the young man", "CALVIN": "the bearded man"}
LOOK_ID = {c: v[0] for c, v in LOOKS.items()}
LOC = "records_room"
LOC_TEXT = ("Plain courthouse records room, nobody else in it: a long wooden counter with a staff side and a customer side, a desk "
            "with a computer behind the counter, two waiting chairs against the green wall on the left, shelves of "
            "archive boxes behind the counter, and one frosted-glass hallway door on the right")

# position key -> (state text, mark, posture, facing)
POS = {
    "H_CTR": ("standing behind the counter", "ctr_hollis", "standing upright behind the counter", "NAOMI"),
    "N_CUST": ("standing at the counter, frame-left", "ctr_naomi", "standing upright at the counter", "HOLLIS"),
    "N_CHAIR": ("seated in the waiting chair, frame-left", "chair_naomi",
                "seated upright in the chair, hands folded in her lap", "HOLLIS"),
    "N_BACK": ("standing a step back from the counter, frame-left", "back_naomi", "standing upright, hands at her sides", "HOLLIS"),
    "E_DOOR": ("standing by the door, frame-right", "door_eli", "standing upright beside the door", "HOLLIS"),
    "E_CTR": ("standing behind the counter, frame-right", "ctr_eli", "standing upright behind the counter", "NAOMI"),
    "C_DOOR": ("standing in the doorway, frame-right", "door_calvin", "standing in the doorway", "ELI"),
    "C_CUST": ("standing at the counter, centre", "ctr_calvin",
               "standing upright at the counter", "ELI"),
    "H_OUT": ("standing outside the door", "door_hollis", "standing in the hallway", "NAOMI"),
}
# phrase the beat's stage_action must use for the position this author tracks
STAGE_PHRASE = {
    "H_CTR": "behind the records counter", "E_CTR": "behind the records counter",
    "N_CUST": "customer side of the counter", "C_CUST": "customer side of the counter",
    "N_CHAIR": "seated in a waiting chair", "N_BACK": "one step back from the counter", "E_DOOR": "beside the hallway door",
}
# off-frame listener placement, by the listener's position key; side is computed from the left-to-right order below
OFF_TEXT = {
    "H_CTR": "HOLLIS stands behind the records counter",
    "N_CUST": "NAOMI stands on the customer side of the counter",
    "N_CHAIR": "NAOMI sits in a waiting chair against the wall",
    "N_BACK": "NAOMI stands a step back from the counter",
    "E_DOOR": "ELI stands beside the hallway door",
    "E_CTR": "ELI stands behind the records counter",
    "C_DOOR": "CALVIN stands in the hallway doorway",
    "C_CUST": "CALVIN stands on the customer side of the counter",
    "H_OUT": "HOLLIS stands outside the hallway door",
}
# screen order, left to right, per scene group
ORDER_MORNING = {"NAOMI": 0, "HOLLIS": 1, "ELI": 2}
ORDER_AFTERNOON = {"NAOMI": 0, "CALVIN": 1, "ELI": 2}

# single composition by speaker position key
SIDE_OUT = {"H_CTR": "on both sides", "N_CUST": "to the right", "N_CHAIR": "to the right", "N_BACK": "to the right",
            "E_DOOR": "to the left", "E_CTR": "to the left", "C_CUST": "on both sides"}
COMPOSE = {
    "H_CTR": "close single on HOLLIS standing behind the records counter: head and shoulders, the counter edge low in the frame, "
             "the archive-box shelves behind him, everyone else out of frame %s" % SIDE_OUT["H_CTR"],
    "N_CUST": "close single on NAOMI standing on the customer side of the counter: head and shoulders, the counter edge low in "
              "the frame, the green wall behind her, everyone else out of frame %s" % SIDE_OUT["N_CUST"],
    "N_CHAIR": "close single on NAOMI seated in a waiting chair: head and shoulders against the green wall, the chair back "
               "beside her, everyone else out of frame %s" % SIDE_OUT["N_CHAIR"],
    "N_BACK": "close single on NAOMI standing a step back from the counter: head and shoulders, the green wall behind her, "
              "the counter edge at the bottom of the frame, everyone else out of frame %s" % SIDE_OUT["N_BACK"],
    "E_DOOR": "close single on ELI standing beside the hallway door: head and shoulders, the frosted-glass door frame beside him, the chest "
              "body camera in view, everyone else out of frame %s" % SIDE_OUT["E_DOOR"],
    "E_CTR": "close single on ELI standing behind the records counter: head and shoulders, the counter edge low in the frame, "
             "the archive-box shelves behind him, everyone else out of frame %s" % SIDE_OUT["E_CTR"],
    "C_CUST": "close single on CALVIN standing on the customer side of the counter: head and shoulders, the counter edge low "
              "in the frame, the green wall behind him, everyone else out of frame %s" % SIDE_OUT["C_CUST"],
}
CAMPOS = {"H_CTR": "c_hollis", "N_CUST": "c_naomi_cust", "N_CHAIR": "c_naomi_chair", "N_BACK": "c_naomi_back",
          "E_DOOR": "c_eli_door", "E_CTR": "c_eli_ctr", "C_CUST": "c_calvin"}
MASTER_TXT = {
    "morning": ("wide shot of the records room from the customer side: NAOMI on the customer side of the counter on the left, the counter "
                "across the middle with HOLLIS standing behind it, shelves of archive boxes behind the counter, ELI standing beside the "
                "frosted-glass hallway door on the right, two waiting chairs against the green wall on the left"),
    "afternoon": ("wide shot of the records room from the customer side: NAOMI on the left, CALVIN in the middle on the customer side of the "
                  "counter, the counter across the middle with ELI standing behind it on the right, shelves of archive boxes behind the "
                  "counter, the frosted-glass hallway door on the right, two waiting chairs against the green wall on the left"),
}

# prop key (state key, ends with ':') -> design id
PROPS = {
    "the brown packet:": "prop_packet", "the ledger:": "prop_ledger", "the ID card:": "prop_idcard",
    "the notebook:": "prop_notebook", "the cover page:": "prop_coverpage", "the radio:": "prop_radio", "the pen:": "prop_pen",
}
P_PACKET_CUST = "lying sealed on the counter, red seal up"
P_PACKET_NEAR = "lying sealed on the counter, red seal up"
P_PACKET_UNDER = "lying sealed under HOLLIS's right hand, red seal up"
P_PACKET_HELD = "held in HOLLIS's hands, red seal toward him"
P_PACKET_THUMB = "held in HOLLIS's hands, his right thumb under the red seal's edge"
P_PACKET_CRACKED = "held in HOLLIS's hands, red seal cracked and broken"
P_PACKET_OPEN = "open on the counter, papers halfway out, face down"
P_LEDGER_OPEN = "lying open on the counter, pages facing HOLLIS, away from the camera"
P_LEDGER_SHUT = "lying closed on the counter"
P_CARD_CTR = "lying on the counter beside the packet"
P_CARD_HAND = "held in HOLLIS's left hand"
P_CARD_DESK = "lying on the desk"
P_NB_POCKET = "in ELI's chest pocket"
P_NB_HAND = "held closed in ELI's right hand"

# per-scene staging: start positions, start props, and the changes made by the action generations
# event key: generation number; value: (who -> position key, prop -> text)
SC = {
    "SC01": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CUST", ELI="E_DOOR"),
                 props={"the brown packet:": "held flat in NAOMI's hands", "the ledger:": P_LEDGER_OPEN},
                 ev={1: ({}, {"the brown packet:": "lying sealed on the counter, red seal up"}),
                     25: ({}, {"the ledger:": "lying closed under HOLLIS's right hand"})}),
    "SC02": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CUST", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_CUST, "the ledger:": P_LEDGER_SHUT},
                 ev={25: ({}, {"the ID card:": P_CARD_CTR})}),
    "SC03": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CUST", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_CUST, "the ledger:": P_LEDGER_SHUT, "the ID card:": P_CARD_CTR},
                 ev={1: ({}, {"the ID card:": P_CARD_HAND}), 9: ({"NAOMI": "N_CHAIR"}, {})}),
    "SC04": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CHAIR", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_NEAR, "the ledger:": P_LEDGER_SHUT, "the ID card:": P_CARD_HAND}, ev={}),
    "SC05": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CHAIR", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_NEAR, "the ledger:": P_LEDGER_SHUT, "the ID card:": P_CARD_HAND},
                 ev={1: ({}, {"the brown packet:": P_PACKET_UNDER}), 2: ({"NAOMI": "N_CUST"}, {})}),
    "SC06": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CUST", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_UNDER, "the ledger:": P_LEDGER_SHUT, "the ID card:": P_CARD_HAND,
                        "the notebook:": P_NB_POCKET},
                 ev={2: ({}, {"the notebook:": P_NB_HAND})}),
    "SC07": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CUST", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_UNDER, "the ledger:": P_LEDGER_SHUT,
                        "the notebook:": P_NB_HAND},
                 ev={22: ({}, {"the brown packet:": P_PACKET_HELD})}),
    "SC08": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CUST", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_HELD, "the ledger:": P_LEDGER_SHUT,
                        "the notebook:": P_NB_HAND},
                 ev={24: ({}, {"the brown packet:": P_PACKET_UNDER})}),
    "SC09": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_CUST", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_UNDER, "the ledger:": P_LEDGER_SHUT,
                        "the notebook:": P_NB_HAND},
                 ev={18: ({"NAOMI": "N_BACK"}, {}), 24: ({}, {"the brown packet:": P_PACKET_THUMB})}),
    "SC10": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_BACK", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_THUMB, "the ledger:": P_LEDGER_SHUT,
                        "the notebook:": P_NB_HAND},
                 ev={1: ({}, {"the brown packet:": P_PACKET_CRACKED}), 5: ({}, {"the brown packet:": P_PACKET_OPEN}),
                     6: ({}, {"the cover page:": "held in HOLLIS's right hand, printed side away from the camera"})}),
    "SC11": dict(tod="MORNING", light="morning", pos=dict(HOLLIS="H_CTR", NAOMI="N_BACK", ELI="E_DOOR"),
                 props={"the brown packet:": P_PACKET_OPEN, "the ledger:": P_LEDGER_SHUT,
                        "the cover page:": "lying face down on the counter"},
                 ev={16: ({}, {"the radio:": "held in ELI's right hand at his mouth"}),
                     17: ({}, {"the radio:": "held in ELI's right hand at chest height"}),
                     24: ({"HOLLIS": "H_OUT"}, {})}),
    "SC12": dict(tod="AFTERNOON", light="afternoon", pos=dict(ELI="E_CTR", NAOMI="N_CUST"),
                 props={"the ledger:": "lying open on the counter, page away from the camera",
                        "the pen:": "lying beside the ledger"},
                 ev={16: ({"CALVIN": "C_CUST"}, {})}),
}
ENTER = {"SC12": ("CALVIN", 16, "C_DOOR")}   # character enters at generation n, standing at the given key at its start
EXIT = {"SC11": ("HOLLIS", 25)}              # present through generation 24 (the walk-out), gone from generation 25
CAST = {"SC%02d" % i: ["HOLLIS", "NAOMI", "ELI"] for i in range(1, 12)}
CAST["SC12"] = ["ELI", "NAOMI", "CALVIN"]

LIGHT = {
    "morning": dict(key_direction="SIDE_RIGHT", quality="SOFT", colour_temp_k=4600, contrast="MEDIUM",
                    motivation="pale morning daylight from a high window on the right wall and flat ceiling lights",
                    practicals=[{"kind": "WINDOW", "note": "high window on the right wall, pale morning daylight"},
                                {"kind": "OVERHEAD", "note": "flat ceiling lights, on"}]),
    "afternoon": dict(key_direction="SIDE_RIGHT", quality="SOFT", colour_temp_k=3800, contrast="MEDIUM",
                      motivation="warm low afternoon sun from the high window on the right wall and flat ceiling lights",
                      practicals=[{"kind": "WINDOW", "note": "high window on the right wall, warm afternoon sun"},
                                  {"kind": "OVERHEAD", "note": "flat ceiling lights, on"}]),
}

# performance cues: (intent, visible cues, prohibited misread) by character and scene number
def cue_for(ch: str, n: int):
    if ch == "NAOMI":
        if n <= 3:
            return ("calm, exact", ["level look", "still mouth"], "arrogance")
        if n <= 5:
            return ("composed, patient", ["steady eyes", "slow blink"], "smugness")
        if n <= 9:
            return ("firm, steady, warning", ["steady eyes", "slow nod"], "threat")
        if n <= 11:
            return ("quiet, giving him room", ["still posture", "soft eyes"], "triumph")
        return ("warm, tired", ["slight smile", "soft eyes"], "smugness")
    if ch == "HOLLIS":
        if n <= 3:
            return ("guarded, impatient", ["tight jaw", "flat stare"], "friendliness")
        if n == 4:
            return ("probing, uneasy", ["narrowed eyes", "small swallow"], "confidence")
        if n <= 7:
            return ("forceful, wary", ["set jaw", "hard stare"], "calm")
        if n <= 9:
            return ("rattled, stubborn", ["tight mouth", "shifting eyes"], "amusement")
        if n == 10:
            return ("shaken, denying", ["draining colour", "slow breath"], "anger")
        return ("cornered, pleading", ["wet eyes", "small swallow"], "menace")
    if ch == "ELI":
        if n <= 5:
            return ("uneasy, watchful", ["wary eyes", "still posture"], "boredom")
        if n <= 9:
            return ("steadying, resolved", ["level look", "firm mouth"], "defiance")
        if n <= 11:
            return ("resolved, sorry", ["steady eyes", "slow nod"], "coldness")
        return ("easy, quietly proud", ["small smile", "steady eyes"], "smugness")
    return ("quiet, moved", ["wet eyes", "slow breath"], "anger")  # CALVIN


def manner_for(ch: str, n: int) -> str:
    if ch == "NAOMI":
        return "warmly" if n == 12 else "calmly" if n <= 5 else "steadily" if n <= 9 else "quietly"
    if ch == "HOLLIS":
        return "curtly" if n <= 3 else "warily" if n == 4 else "sharply" if n <= 7 else "tersely" if n <= 9 else "hoarsely" if n == 10 else "pleadingly"
    if ch == "ELI":
        return "carefully" if n <= 5 else "firmly" if n <= 9 else "steadily" if n <= 11 else "easily"
    return "slowly"


# --------------------------------------------------------------------------------------------------------------------
# continuity states
# --------------------------------------------------------------------------------------------------------------------
def pose(key):
    text, mark, posture, facing = POS[key]
    return {"mark": mark, "posture": posture, "facing": facing}


def gid(sc, n):
    return f"{sc}_g{n:02d}"


def make_state(sc, keys, props, n):
    """State at the start of generation n (n = 26 for the scene end). `keys` = character -> position key."""
    who = list(keys)
    if sc in ENTER and n < ENTER[sc][1] and ENTER[sc][0] in who and n != ENTER[sc][1]:
        pass
    cfg = SC[sc]
    return {
        "positions": {c: POS[k][0] for c, k in keys.items()},
        "props": dict(props), "looks": {c: LOOK_ID[c] for c in keys},
        "lighting": cfg["light"], "time_of_day": cfg["tod"], "location": LOC,
        "blocking": {c: pose(k) for c, k in keys.items()},
    }


states: dict[str, dict] = {}
timeline: dict[str, list[tuple[dict, dict]]] = {}  # scene -> per generation (position keys, props) at its START
for sc, cfg in SC.items():
    keys, props = dict(cfg["pos"]), dict(cfg["props"])
    timeline[sc] = []
    for n in range(1, 27):
        view = dict(keys)
        if sc in ENTER and n >= ENTER[sc][1] - 0:  # the entrant is positioned from the generation of the ENTER on
            who, at, start_key = ENTER[sc]
            view[who] = keys.get(who, start_key)
        if n <= 25:
            states[gid(sc, n)] = make_state(sc, view, props, n)
            timeline[sc].append((view, dict(props)))
        else:
            states[f"{sc}_end"] = make_state(sc, view, props, n)
        if n <= 25:
            who_ev, pr = cfg["ev"].get(n, ({}, {}))
            keys.update(who_ev)
            props.update(pr)
            if sc in ENTER and n == ENTER[sc][1] - 1:
                pass
if "SC12" in ENTER:
    pass
# close inserts show only what is in frame: out-of-frame props are dropped from the start state to keep prompts short
for _gid, _keep in {"SC11_g16": (), "SC09_g24": ("packet",), "SC10_g01": ("packet",), "SC12_g25": ("ledger",)}.items():
    states[_gid]["props"] = {k: v for k, v in states[_gid]["props"].items() if any(w in k for w in _keep)}

# --------------------------------------------------------------------------------------------------------------------
# generations
# --------------------------------------------------------------------------------------------------------------------
def cam(size, composition, lens="NORMAL", repeat=""):
    c = {"size": size, "angle": "EYE_LEVEL", "height": "EYE", "movement": "STATIC", "lens_intent": lens,
         "composition": composition}
    if repeat:
        c["declared_repeat"] = repeat
    return c


REPEAT = "static close singles on whoever speaks are the deliberate grammar of this talking scene; the room never changes"


def phases(*items):
    return [dict(kind=k, start_s=a, end_s=b, description=d, **({"motion": m} if m else {})) for (k, a, b, d, m) in items]


def act(setup, action, consequence, hold, motion, t=(1.0, 2.8, 4.0), end=6.0):
    return phases(("SETUP", 0.0, t[0], setup, ""), ("ACTION", t[0], t[1], action, motion),
                  ("CONSEQUENCE", t[1], t[2], consequence, ""), ("HOLD", t[2], end, hold, ""))


# action generations: coverage MASTER shows everyone present; "close" is a single of the actor (gaze at an object)
ACTIONS = {
    ("SC01", 1): dict(who="NAOMI", ph=act("NAOMI stands on the customer side of the counter holding the sealed brown packet flat in both hands",
                                          "NAOMI sets the sealed brown packet down on the counter beside the open ledger and lifts both hands away",
                                          "the sealed brown packet lies still on the counter, NAOMI's hands now empty at her sides",
                                          "all three stay still, HOLLIS's hands on his own side", "put_down_small_object"),
                      once=["NAOMI sets the sealed brown packet down"]),
    ("SC01", 25): dict(who="HOLLIS", ph=act("HOLLIS stands behind the counter, the ledger lies open in front of him",
                                            "HOLLIS closes the ledger with his right hand",
                                            "the ledger lies closed, HOLLIS's right hand flat on its cover",
                                            "all three stay still, NAOMI's hands at her sides", ""),
                       once=["HOLLIS closes the ledger"]),
    ("SC02", 25): dict(who="NAOMI", ph=act("NAOMI stands at the counter, her right hand at the edge of her coat pocket",
                                           "NAOMI sets a plastic ID card down on the counter beside the sealed packet with her right hand",
                                           "the ID card lies still beside the sealed packet, NAOMI's right hand back at her side",
                                           "all three stay still, HOLLIS does not reach for it", "put_down_small_object"),
                       once=["NAOMI sets the ID card down"]),
    ("SC03", 1): dict(who="HOLLIS", ph=act("HOLLIS stands behind the counter, the ID card lies on the counter beside the sealed packet",
                                           "HOLLIS picks up the ID card in his left hand and holds it close to his face",
                                           "HOLLIS holds the ID card in his left hand, the sealed packet still on the counter",
                                           "all three stay still, NAOMI's hands at her sides", "pick_up_small_object"),
                       once=["HOLLIS picks up the ID card"]),
    ("SC03", 9): dict(who="NAOMI", ph=act("NAOMI stands on the customer side of the counter, a waiting chair against the wall beside her",
                                          "NAOMI sits down in the nearer waiting chair against the wall",
                                          "NAOMI sits upright in the chair, her eyes on the sealed packet on the counter",
                                          "all three stay still, HOLLIS holds the ID card in his left hand", "sit_down", t=(1.0, 3.0, 4.0)),
                      once=["NAOMI sits down in the waiting chair"]),
    ("SC05", 1): dict(who="HOLLIS", ph=act("HOLLIS stands behind the counter, the sealed packet lies on the counter near NAOMI's chair side",
                                           "HOLLIS slides the sealed packet along the counter toward himself with his right hand",
                                           "HOLLIS holds his right hand flat on top of the sealed packet at his side of the counter",
                                           "all three stay still, NAOMI stays seated", ""),
                       once=["HOLLIS slides the sealed packet toward himself"]),
    ("SC05", 2): dict(who="NAOMI", ph=act("NAOMI sits in the waiting chair, HOLLIS's right hand flat on the sealed packet",
                                          "NAOMI rises from the chair and steps back to the customer side of the counter",
                                          "NAOMI stands at the counter, her hands at her sides",
                                          "all three stay still, HOLLIS's right hand stays flat on the sealed packet", "stand_up", t=(1.0, 3.0, 4.0)),
                      once=["NAOMI rises from the chair"]),
    ("SC06", 2): dict(who="ELI", ph=act("ELI stands beside the hallway door with his hands at his sides",
                                        "ELI takes a small notebook from his chest pocket with his right hand",
                                        "ELI holds the small notebook closed in his right hand",
                                        "all three stay still, HOLLIS and NAOMI stay in their places", "pick_up_small_object"),
                      once=["ELI takes the notebook from his chest pocket"]),
    ("SC07", 22): dict(who="HOLLIS", ph=act("HOLLIS stands behind the counter, his right hand flat on the sealed packet",
                                            "HOLLIS lifts the sealed packet in both hands and turns it over, the red wax seal toward himself",
                                            "HOLLIS holds the sealed packet in both hands, the red wax seal toward himself",
                                            "all three stay still, NAOMI's hands at her sides", "pick_up_small_object"),
                       once=["HOLLIS lifts the sealed packet in both hands"]),
    ("SC08", 24): dict(who="HOLLIS", ph=act("HOLLIS holds the sealed packet in both hands behind the counter",
                                            "HOLLIS sets the sealed packet down on the counter with his right hand resting on it",
                                            "the sealed packet lies on the counter under HOLLIS's right hand",
                                            "all three stay still, NAOMI's hands at her sides", "put_down_small_object"),
                       once=["HOLLIS sets the sealed packet down"]),
    ("SC09", 18): dict(who="NAOMI", ph=act("NAOMI stands at the customer side of the counter, HOLLIS's right hand on the sealed packet",
                                           "NAOMI takes one deliberate step back from the counter",
                                           "NAOMI stands one step back from the counter, her hands hanging at her sides",
                                           "all three stay still, HOLLIS's right hand stays on the sealed packet", "walk_across_room", t=(1.0, 2.6, 4.0)),
                       once=["NAOMI steps back from the counter"]),
    ("SC09", 24): dict(who="HOLLIS", close=("HOLLIS", "close on HOLLIS behind the counter: head and shoulders, both hands holding the packet low in the frame"),
                       gaze="brown_packet",
                       ph=act("HOLLIS holds the sealed packet in both hands at the counter edge",
                              "HOLLIS slides his right thumb under the edge of the red wax seal",
                              "HOLLIS's right thumb rests under the edge of the red wax seal, both hands still on the packet",
                              "HOLLIS holds quite still, his eyes on the seal", ""),
                       once=["HOLLIS slides his right thumb under the edge of the seal"]),
    ("SC10", 1): dict(who="HOLLIS", close=("HOLLIS", "close on HOLLIS behind the counter: head and shoulders, both hands holding the packet low in the frame"),
                      gaze="brown_packet",
                      ph=act("HOLLIS holds the packet in both hands, right thumb under the red seal",
                             "HOLLIS pushes his right thumb up and the red wax seal cracks",
                             "HOLLIS holds the packet, the red seal cracked",
                             "HOLLIS holds quite still, his eyes on the broken seal", ""),
                      once=["HOLLIS breaks the red wax seal"]),
    ("SC10", 5): dict(who="HOLLIS", ph=act("HOLLIS stands behind the counter holding the opened packet in both hands, the seal broken",
                                           "HOLLIS draws a thin stack of papers halfway out of the packet onto the counter, the pages face down",
                                           "the papers lie halfway out of the packet on the counter, the pages face down",
                                           "all three stay still, NAOMI's hands at her sides", ""),
                      once=["HOLLIS draws the papers halfway out of the packet"]),
    ("SC11", 16): dict(who="ELI", close=("ELI", "close on ELI standing beside the hallway door: head and shoulders, the frosted-glass door frame beside him, "
                                         "the chest body camera in view; he raises his hand to his shoulder"),
                       gaze="shoulder_radio",
                       ph=act("ELI stands by the door, the radio on his left shoulder",
                              "ELI unclips the radio and raises it to his mouth",
                              "ELI holds the radio at his mouth in his right hand",
                              "ELI holds quite still, the radio at his mouth", "pick_up_small_object"),
                       once=["ELI raises the radio to his mouth"]),
    ("SC11", 24): dict(who="HOLLIS", ph=phases(
        ("SETUP", 0.0, 1.0, "HOLLIS stands behind the counter, NAOMI one step back from it, ELI beside the hallway door", ""),
        ("ACTION", 1.0, 4.0, "HOLLIS walks out from behind the counter and leaves through the hallway door without looking back", "walk_across_room"),
        ("HOLD", 4.0, 6.0, "the counter is empty on the staff side, NAOMI and ELI stay where they are", "")),
        once=["HOLLIS walks out through the hallway door"]),
    ("SC12", 16): dict(who="CALVIN", ph=phases(
        ("SETUP", 0.0, 1.0, "ELI stands behind the counter and NAOMI on the customer side; CALVIN waits in the hallway doorway", ""),
        ("ACTION", 1.0, 4.0, "CALVIN walks in through the hallway door at an ordinary pace and stops on the customer side of the counter", "walk_across_room"),
        ("HOLD", 4.0, 6.0, "CALVIN stands at the counter facing ELI, all three quite still", "")),
        once=["CALVIN walks in through the hallway door"]),
    ("SC12", 25): dict(who="CALVIN", close=("CALVIN", "close on CALVIN standing at the customer side of the counter: head and shoulders, his right hand "
                                            "with the pen low in the frame over the open ledger, the ledger page out of focus, the green wall behind him"),
                       gaze="ledger",
                       ph=phases(
                           ("SETUP", 0.0, 1.0, "CALVIN stands at the counter, the pen beside the ledger", ""),
                           ("ACTION", 1.0, 3.5, "CALVIN picks up the pen in his right hand and draws it across the ledger page", ""),
                           ("CONSEQUENCE", 3.5, 5.0, "CALVIN sets the pen down beside the ledger", "put_down_small_object"),
                           ("HOLD", 5.0, 6.0, "the pen lies still beside the ledger", "")),
                       once=["CALVIN signs the ledger page with the pen"]),
}
# reaction generations: (scene, n) -> (who, action text, gaze target, composition override)
REACTIONS = {
    ("SC01", 12): ("ELI", "ELI watches the counter, the green light on his chest camera steady, his face carefully neutral", "counter", None),
    ("SC02", 19): ("HOLLIS", "HOLLIS studies NAOMI's face for a long moment, jaw tight, saying nothing", "NAOMI", None),
    ("SC03", 15): ("HOLLIS", "HOLLIS types at the desk computer with his right hand, then stares at the screen without blinking", "desk_computer",
                   "close single on HOLLIS standing at the desk behind the counter: head and shoulders, the computer screen edge-on at the "
                   "edge of the frame, archive-box shelves behind him, everyone else out of frame on both sides"),
    ("SC04", 10): ("ELI", "ELI glances aside, then down at the floor, uneasy", "floor", None),
    ("SC04", 17): ("NAOMI", "NAOMI holds her face completely still, hands folded in her lap, giving nothing back", "HOLLIS", None),
    ("SC06", 9): ("HOLLIS", "HOLLIS turns slowly to look at ELI, surprised, his mouth tightening", "ELI", None),
    ("SC07", 8): ("NAOMI", "NAOMI looks at HOLLIS steadily and says nothing, letting the question hang", "HOLLIS", None),
    ("SC08", 10): ("HOLLIS", "HOLLIS tilts the packet in his hands to study the custody form on its back, the form turned away from the camera, his lips moving silently",
                   "brown_packet", None),
    ("SC09", 6): ("HOLLIS", "HOLLIS glances toward ELI and the hallway door, as though measuring who is watching him", "ELI", None),
    ("SC10", 6): ("HOLLIS", "HOLLIS lifts the top page close to his face, its printed side turned away from the camera, and the colour slowly drains from his face",
                  "cover_page", None),
    ("SC11", 1): ("HOLLIS", "HOLLIS stands motionless, staring down at the opened packet, both hands flat on the counter edge", "brown_packet", None),
    ("SC12", 11): ("NAOMI", "NAOMI takes that in quietly with a small, tired nod", "ELI", None),
}
REACTION_MOTION = {"glance"}

gens: list[dict] = []
wides: list[tuple[str, str, set[str]]] = []  # (generation id, scene id, visible) of every generation showing 2+ people


def perf(ch, n):
    intent, cues, misread = cue_for(ch, n)
    return {"character": ch, "emotion_intent": intent, "visible_cues": cues, "intensity": "restrained",
            "prohibited_misread": misread}


def side_of(sc, speaker, listener):
    order = ORDER_AFTERNOON if sc == "SC12" else ORDER_MORNING
    return "RIGHT" if order[listener] > order[speaker] else "LEFT"


def established_by(sc, speaker, listener):
    """Latest earlier generation that shows speaker and listener together, in this scene or its encounter."""
    for g_id, g_sc, vis in reversed(wides):
        same = g_sc == sc or (SC12_SHARES_ENCOUNTER or "SC12" not in (g_sc, sc))
        if same and {speaker, listener} <= vis:
            return g_id
    return None


def anchor_for(sc, speaker, listener, key):
    side = side_of(sc, speaker, listener)
    text = f"{OFF_TEXT[key]} off frame-{side.lower()}, wholly out of shot"
    return {"mode": "OFF_FRAME", "side": side, "placement": text, "established_by": established_by(sc, speaker, listener)}


for beat_scene in BEATS["scenes"]:
    sc = beat_scene["scene_id"]
    num = int(sc[2:])
    cfg = SC[sc]
    prev = None
    for n, b in enumerate(beat_scene["beats"], start=1):
        g_id = gid(sc, n)
        assert b["generation_id"] == g_id
        keys = timeline[sc][n - 1][0]
        present = set(CAST[sc])
        if sc in EXIT and n >= EXIT[sc][1]:
            present.discard(EXIT[sc][0])
        if sc in ENTER and n < ENTER[sc][1]:
            present.discard(ENTER[sc][0])
        end_state = gid(sc, n + 1) if n < 25 else f"{sc}_end"
        base = {"generation_id": g_id, "scene_id": sc, "start_state": g_id, "end_state": end_state,
                "previous_generation_id": prev, "sfx": [], "readout": [], "duration_s": 6, "version": 1}
        if b["kind"] == "dialogue":
            who = b["speaker"]
            to = b["addressee"]
            line_no = LINES[sc][b["text_en"]]
            sx = keys[who]
            claim = b["stage_action"]
            if STAGE_PHRASE[sx] not in claim:
                raise SystemExit(f"{g_id}: tracked position {sx} disagrees with beat: {claim[:90]}")
            manner = manner_for(who, num)
            if to == "RADIO":
                to_what, anchors, addressees, gaze = "the radio", {}, {str(line_no): ["SELF"]}, "shoulder_radio"
            else:
                to_what, gaze = to, to
                anchors = {to: anchor_for(sc, who, to, keys[to])}
                addressees = {str(line_no): [to]}
            ph = [("SETUP", 0.0, 0.5, f"{who} looks at {to_what}", ""),
                  ("ACTION", 0.5, round(min(5.5, 0.5 + len(b["text_en"].split()) / 2.6), 1), f"{who} speaks to {to_what} {manner}", ""),
                  ("HOLD", round(min(5.5, 0.5 + len(b["text_en"].split()) / 2.6), 1), 6.0, f"{who} holds {to_what}'s look, quite still" if to != "RADIO" else f"{who} holds the radio near his mouth, quite still", "")]
            g = dict(base, coverage="SINGLE", subject=who, foreground="", visible=[who], dialogue=[line_no],
                     choreography={"generation_id": g_id, "phases": phases(*ph), "once_actions": [f"{who} speaks to {to_what}"],
                                   "gesture_budget": 1, "performance": [perf(who, num)]},
                     design_refs=[], camera=cam("CLOSE", COMPOSE[sx], repeat=REPEAT), camera_position=CAMPOS[sx],
                     addressees=addressees, listener_anchors=anchors, gaze_target=gaze)
        elif b["kind"] == "reaction":
            who, text, gaze, comp = REACTIONS[(sc, n)]
            sx = keys[who]
            ph = [("SETUP", 0.0, 1.5, f"{who} looks toward {gaze if gaze in ('NAOMI', 'HOLLIS', 'ELI') else 'the ' + gaze.replace('_', ' ')}", ""),
                  ("ACTION", 1.5, 2.4, text, "glance"),
                  ("CONSEQUENCE", 2.4, 4.0, f"{who} stays with what they see", ""),
                  ("HOLD", 4.0, 6.0, f"{who} holds the quiet look, nobody speaks", "")]
            anchors = {}
            if gaze in ("NAOMI", "HOLLIS", "ELI", "CALVIN"):
                anchors[gaze] = anchor_for(sc, who, gaze, keys[gaze])
            g = dict(base, coverage="SINGLE", subject=who, foreground="", visible=[who], dialogue=[],
                     choreography={"generation_id": g_id, "phases": phases(*ph), "once_actions": [text],
                                   "gesture_budget": 1, "performance": [perf(who, num)]},
                     design_refs=[], camera=cam("CLOSE", comp or COMPOSE[sx], repeat=REPEAT),
                     camera_position="c_hollis_desk" if comp else CAMPOS[sx], gaze_target=gaze, listener_anchors=anchors)
        else:
            a = ACTIONS[(sc, n)]
            close = a.get("close")
            visible = [close[0]] if close else sorted(present, key=lambda c: (ORDER_AFTERNOON if sc == "SC12" else ORDER_MORNING)[c])
            tod = "afternoon" if sc == "SC12" else "morning"
            g = dict(base, coverage="SINGLE" if close else "MASTER", subject=a["who"], foreground="", visible=visible, dialogue=[],
                     choreography={"generation_id": g_id, "phases": a["ph"], "once_actions": ([o for o in a["once"] if o.lower() in " ".join(p["description"] for p in a["ph"] if p["kind"] == "ACTION").lower()] or [next(p["description"] for p in a["ph"] if p["kind"] == "ACTION")]), "gesture_budget": 1,
                                   "performance": [perf(a["who"], num)]},
                     design_refs=[],
                     camera=cam("CLOSE", close[1], repeat=REPEAT) if close else cam("WIDE", MASTER_TXT[tod], "WIDE_ESTABLISH"),
                     camera_position=CAMPOS[keys[a["who"]]] if close else ("cA_rec12" if sc == "SC12" else "cA_rec"))
            if close:
                g["gaze_target"] = a["gaze"]
                o = "NAOMI" if "NAOMI" in present and a["who"] != "NAOMI" else sorted(present - {a["who"]})[0]
                g["listener_anchors"] = {o: anchor_for(sc, a["who"], o, keys[o])}
        if len(g["visible"]) >= 2:
            wides.append((g_id, sc, set(g["visible"])))
        gens.append(g)
        prev = g_id

BY_ID = {g["generation_id"]: g for g in gens}
for g_id, why in (("SC11_g25", "HOLLIS's last steps out through the hallway door happen during the previous generation"),):
    BY_ID[g_id]["handoff_ellipsis"] = why

# --------------------------------------------------------------------------------------------------------------------
# 03_preprod
# --------------------------------------------------------------------------------------------------------------------
feas = {"max_speakers": 3,  # three people speak in every scene (one per shot); the scene-level count would otherwise block
         "max_in_frame": 3, "max_dialogue_syllables": 30, "scene_duration_s": 16.0, "min_silence_s": 3.0,
        "syllables_per_second": 2.5}
layout = {
    "zones": [{"id": "counter_zone", "label": "counter, staff side and archive shelves", "box": [0.3, 0.05, 0.75, 0.5]},
              {"id": "customer_zone", "label": "customer side and waiting chairs", "box": [0.02, 0.5, 0.75, 0.98]},
              {"id": "door_zone", "label": "frosted-glass hallway door", "box": [0.75, 0.05, 0.98, 0.7]}],
    "objects": [
        {"id": "counter", "label": "long wooden counter", "zone": "counter_zone",
         "placement": "runs across the middle of the room, the staff side behind it, the customer side in front", "at": [0.5, 0.45]},
        {"id": "ledger", "label": "open ledger", "zone": "counter_zone",
         "placement": "on the counter on the staff side, its pages facing the staff side", "at": [0.5, 0.43]},
        {"id": "brown_packet", "label": "sealed brown packet", "zone": "counter_zone",
         "placement": "on the counter, where the scene state puts it", "at": [0.45, 0.45]},
        {"id": "cover_page", "label": "page held in front of him", "zone": "counter_zone",
         "placement": "held in HOLLIS's right hand, the printed side turned away from the camera", "at": [0.5, 0.3]},
        {"id": "desk_computer", "label": "desk computer", "zone": "counter_zone",
         "placement": "on the desk behind the staff side of the counter, the screen turned away from the camera", "at": [0.6, 0.15]},
        {"id": "archive_shelves", "label": "shelves of archive boxes", "zone": "counter_zone",
         "placement": "along the wall behind the counter", "at": [0.5, 0.08]},
        {"id": "waiting_chairs", "label": "two waiting chairs", "zone": "customer_zone",
         "placement": "side by side against the green wall on the left", "at": [0.08, 0.6]},
        {"id": "hallway_door", "label": "frosted-glass hallway door", "zone": "door_zone",
         "placement": "in the wall on the right", "at": [0.9, 0.3]},
        {"id": "floor", "label": "floor", "zone": "customer_zone", "placement": "the plain floor of the room", "at": [0.5, 0.9]},
        {"id": "shoulder_radio", "label": "shoulder radio", "zone": "door_zone",
         "placement": "on ELI's left shoulder, or held near his mouth once he unclips it", "at": [0.85, 0.35]},
    ],
    "cameras": [
        {"id": "cA_rec", "zone": "customer_zone", "view": MASTER_TXT["morning"],
         "sees": ["counter", "ledger", "brown_packet", "archive_shelves", "waiting_chairs", "hallway_door"], "at": [0.5, 0.97], "look_at": "counter"},
        {"id": "cA_rec12", "zone": "customer_zone", "view": MASTER_TXT["afternoon"],
         "sees": ["counter", "ledger", "archive_shelves", "waiting_chairs", "hallway_door"], "at": [0.5, 0.97], "look_at": "counter"},
        {"id": "c_hollis", "zone": "customer_zone", "view": "close on HOLLIS behind the counter, shelves of archive boxes behind him",
         "sees": ["counter", "brown_packet", "archive_shelves"], "at": [0.5, 0.7], "look_at": "archive_shelves"},
        {"id": "c_hollis_desk", "zone": "customer_zone", "view": "close on HOLLIS at the desk computer behind the counter",
         "sees": ["desk_computer", "archive_shelves"], "at": [0.55, 0.7], "look_at": "desk_computer"},
        {"id": "c_naomi_cust", "zone": "counter_zone", "view": "close on NAOMI on the customer side of the counter, the green wall behind her",
         "sees": ["counter"], "at": [0.4, 0.2], "look_at": "counter"},
        {"id": "c_naomi_chair", "zone": "counter_zone", "view": "close on NAOMI seated in a waiting chair, the green wall behind her",
         "sees": ["waiting_chairs"], "at": [0.3, 0.3], "look_at": "waiting_chairs"},
        {"id": "c_naomi_back", "zone": "counter_zone", "view": "close on NAOMI a step back from the counter, the green wall behind her",
         "sees": ["counter"], "at": [0.4, 0.2], "look_at": "counter"},
        {"id": "c_eli_door", "zone": "customer_zone", "view": "close on ELI beside the frosted-glass hallway door",
         "sees": ["hallway_door", "shoulder_radio"], "at": [0.8, 0.8], "look_at": "hallway_door"},
        {"id": "c_eli_ctr", "zone": "customer_zone", "view": "close on ELI behind the counter, shelves of archive boxes behind him",
         "sees": ["counter", "archive_shelves"], "at": [0.6, 0.7], "look_at": "archive_shelves"},
        {"id": "c_calvin", "zone": "counter_zone", "view": "close on CALVIN on the customer side of the counter, the green wall behind him",
         "sees": ["counter", "ledger"], "at": [0.5, 0.2], "look_at": "counter"},
    ],
    "marks": [
        {"id": "ctr_hollis", "at": [0.5, 0.25], "zone": "counter_zone"},
        {"id": "ctr_eli", "at": [0.62, 0.25], "zone": "counter_zone"},
        {"id": "ctr_naomi", "at": [0.25, 0.6], "zone": "customer_zone"},
        {"id": "back_naomi", "at": [0.25, 0.8], "zone": "customer_zone"},
        {"id": "chair_naomi", "at": [0.08, 0.65], "zone": "customer_zone"},
        {"id": "ctr_calvin", "at": [0.5, 0.6], "zone": "customer_zone"},
        {"id": "door_eli", "at": [0.85, 0.4], "zone": "door_zone"},
        {"id": "door_calvin", "at": [0.9, 0.3], "zone": "door_zone"},
        {"id": "door_hollis", "at": [0.95, 0.2], "zone": "door_zone"},
    ],
}

designs = {}
for ch, (lid, text, inv) in LOOKS.items():
    designs[f"{ch}_look"] = {"kind": "look", "version": 1, "owner": ch, "note": "locked CharacterLook text; " + ref_note(f"char_{ch}.jpg")}
designs["NAOMI_costume"] = {"kind": "costume", "version": 1, "owner": "NAOMI", "note": "long cream coat over a navy blouse"}
designs["HOLLIS_costume"] = {"kind": "costume", "version": 1, "owner": "HOLLIS", "note": "tan county uniform shirt, brown epaulettes, dark tie"}
designs["ELI_costume"] = {"kind": "costume", "version": 1, "owner": "ELI", "note": "tan county uniform shirt, chest body camera, left shoulder radio"}
designs["CALVIN_costume"] = {"kind": "costume", "version": 1, "owner": "CALVIN", "note": "green canvas jacket over a grey t-shirt (SC12 only)"}
designs[f"loc_{LOC}"] = {"kind": "location", "version": 1, "owner": LOC,
                         "note": "courthouse records room: counter with ledger, desk and computer, two waiting chairs, archive shelves, one hallway door; " + ref_note("plate_records_room.jpg")}
PROP_NOTE = {
    "prop_packet": "sealed brown packet with a red wax seal; any custody form on its back stays turned away from the camera, no readable text",
    "prop_ledger": "open ledger; its pages face the staff side or are out of focus, never legible",
    "prop_coverpage": "grand jury cover page; its printed side is always turned away from the camera, never legible",
    "prop_idcard": "plain plastic ID card; seen only from the back or edge-on, no readable text",
}
for key, did in PROPS.items():
    designs[did] = {"kind": "prop", "version": 1, "prop": key.rstrip(":"), "note": PROP_NOTE.get(did, "plain prop, no readable text")}

scenes = {}
for i, sc in enumerate(SC, start=1):
    cfg = SC[sc]
    afternoon = sc == "SC12"
    initial = list(CAST[sc]) if sc != "SC12" else ["NAOMI", "ELI"]
    events = []
    if sc in ENTER:
        events.append({"generation_index": ENTER[sc][1], "character": ENTER[sc][0], "kind": "ENTER"})
    if sc in EXIT:
        events.append({"generation_index": EXIT[sc][1], "character": EXIT[sc][0], "kind": "EXIT"})
    pair = ["NAOMI", "ELI"]
    sides = {pair[0]: "LEFT", pair[1]: "RIGHT"}
    scenes[sc] = {
        "location": LOC,
        "axis": {"scene_id": sc, "axis_pair": pair, "sides": sides},
        "occupancy": {"scene_id": sc, "initial": initial, "events": events},
        "story_time": ({"scene_id": sc, "story_order": float(i), "transition_in": "LINEAR", "marker": "", "source_conflict": ""} if i == 1 else
                       {"scene_id": sc, "story_order": float(i), "transition_in": "ELLIPSIS", "source_conflict": "",
                        "marker": ("afternoon, one month later: ELI now stands behind the counter, the room looks the same and the light is warmer"
                                   if afternoon else "a few minutes later the same morning: the same three people in the same room, the clock nearer eleven")}),
        "extras": "",
        "lighting": LIGHT[cfg["light"]],
        # SC12 shares the encounter of SC01-SC11: the only wide shots that show NAOMI and ELI together before SC12's first
        # dialogue are SC11's; a month later is not continuous, but the same two people and the same room are what the
        # off-frame check needs established (pipeline limit: a scene cannot open with dialogue singles otherwise).
        "encounter_id": "records_room" if (sc != "SC12" or SC12_SHARES_ENCOUNTER) else "month_later",
    }


def rights_entry(subject, kind, note, status="original"):
    return {"subject": subject, "kind": kind, "status": status, "evidence": OWNER_EVIDENCE, "note": note}


def ref_entry(subject, kind, fname, note):
    return {"subject": subject, "kind": kind, "status": "original", "evidence": OWNER_EVIDENCE + "; " + REF_EVIDENCE,
            "note": note + "; " + ref_note(fname)}


rights = [
    ref_entry("NAOMI", "character", "char_NAOMI.jpg", "original fictional character (Dr. Naomi Bell); Owner-approved brief 2026-11-14"),
    ref_entry("HOLLIS", "character", "char_HOLLIS.jpg", "original fictional character (Sgt. Wade Hollis); Owner-approved brief 2026-11-14"),
    ref_entry("ELI", "character", "char_ELI.jpg", "original fictional character (Deputy Eli Moreno); Owner-approved brief 2026-11-14"),
    ref_entry("CALVIN", "character", "char_CALVIN.jpg", "original fictional character (Calvin Reed, SC12 only); Owner-approved brief 2026-11-14"),
    ref_entry(LOC, "location", "plate_records_room.jpg", "original fictional courthouse records room (Linwood County); Owner-approved brief 2026-11-14"),
    {"subject": "none (room tone and SFX are generated or CC0)", "kind": "music", "status": "original",
     "evidence": OWNER_EVIDENCE, "note": "no music in film08 (Owner-approved brief: no music)"},
    rights_entry("script.fountain", "source", "premise-only adaptation of an outside story (source SRT sha256 " + SRT_SHA +
                 "): the premise is the only thing taken; names, setting, structure, dialogue and ending are new and model-written for film08"),
    rights_entry("none (no real person's likeness)", "likeness", "faces are generated, not modelled on a real person"),
]

preprod = {
    "feasibility": feas,
    "preflight": {"max_prompt_words": 230,
                  "timing": {"duration_s": 6.0, "max_shots": 1, "min_shot_s": 2.0, "syllables_per_second": 2.5,
                             "establish_s": 1.5, "reaction_s": 3.0},
                  "feasibility": feas, "interaction_contract": True,
                  # video prompt: off-screen listener fully out of frame + "No one speaks." (no accepted takes yet, so all scenes)
                  "safeguard_scenes": [f"SC{n:02d}" for n in range(1, 13)]},
    "characters": {ch: {"look": {"look_id": lid, "character": ch, "text": text, "invariants": inv, "approved": True},
                        "video_text": text, "voice": VOICE[ch], "handle": HANDLE[ch]} for ch, (lid, text, inv) in LOOKS.items()},
    "locations": {
        LOC: {"look": {"look_id": LOC, "location": "LINWOOD COUNTY COURTHOUSE RECORDS ROOM", "text": LOC_TEXT,
                       "invariants": ["long counter with a staff side and a customer side", "desk and computer behind the counter",
                                      "two waiting chairs against the green wall on the left",
                                      "shelves of archive boxes behind the counter", "one frosted-glass hallway door on the right"],
                       "interior": True, "time_of_day": "", "weather_outside": "",
                       "environment_rules": ["window light and ceiling lights stay steady; nobody else is in the room"],
                       "approved": True},
              "room_tone": "quiet records room, a ceiling-light hum, a wall clock ticking",
              "layout": layout}
    },
    "scenes": scenes,
    "states": states,
    "still_templates": {
        "framing": {"MASTER": "wide shot of the records room with everyone present in frame",
                    "OTS": "medium over-the-shoulder shot of two people",
                    "SINGLE": "close-up of one person, head and shoulders, the counter, wall or door frame behind them",
                    "TWO_SHOT": "medium two-shot of two people",
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

typed_pre = PreprodSection.model_validate(preprod)
for g in gens:
    decl = ShotDecl.model_validate(g)
    g["design_refs"] = [f"{d}@{typed_pre.designs[d].version}" for d in shot_design_ids(typed_pre, decl)]

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
CONFLICT = {
    "SC01": "Naomi needs a signature on the ledger; Hollis wants to know what is inside before he gives it.",
    "SC02": "Hollis demands her name and authority; Naomi gives only what the ledger needs.",
    "SC03": "Hollis hunts for a flaw in her record; Naomi has none and will not be hurried.",
    "SC04": "Every guess Hollis makes about the audit exposes what he fears.",
    "SC05": "Hollis takes the packet under his hand; Naomi warns him that a broken seal cannot be closed.",
    "SC06": "Hollis wants Eli to write what did not happen; Eli will not.",
    "SC07": "Hollis names who might be behind the audit; Naomi neither confirms nor denies and warns him again.",
    "SC08": "Hollis calls the seal paperwork; Naomi shows him it exists to protect everyone, including him.",
    "SC09": "Hollis decides that hesitating in front of Eli is worse than acting; Naomi warns him a third time.",
    "SC10": "Hollis opens the packet and finds himself named; he asks Eli to turn the camera off and Eli refuses.",
    "SC11": "Hollis begs Eli to protect him; Eli has to choose whether to make the call.",
    "SC12": "Eli runs the room under a new rule; Calvin Reed finally comes for what was taken from him.",
}
SHIFT = ["-", "-", "-", "-", "+", "+", "+", "+", "+", "+", "+", "+"]
story = {
    "concept": ("In a courthouse records room a young deputy watches his sergeant open a sealed packet after three warnings and has to "
                "decide whether to make the call that turns the opening into evidence."),
    "theme": "A seal exists so that no one, however sure of himself, can change what is inside; the one who breaks it writes his own page.",
    "genre": "One-room procedural drama (a standoff over a sealed packet at a records counter, about 27 minutes)",
    "audience": {"who": "General online audience watching English-language dramas with Vietnamese subtitles; anyone who has watched a powerful person hang himself with his own hands.",
                 "expectation": "A patient, tense one-room confrontation with no violence that ends in accountability and a quiet release."},
    "premise": ("Dr. Naomi Bell, an evidence auditor for the federal court, brings a sealed packet to the county records room to be logged out "
                "to the grand jury by eleven; Sgt. Hollis, who runs the room, refuses to log what he has not seen, while Deputy Eli Moreno's body "
                "camera records every minute."),
    "central_conflict": ("Hollis wants to control what leaves his room and to learn what the audit knows; Naomi will not tell him and will not "
                         "touch the seal; Eli must decide whether to keep following his sergeant or keep the record honest."),
    "logline": {"text": ("Deputy Eli Moreno must keep the record honest when the sergeant who trained him ignores three warnings and "
                         "breaks a court seal on camera, even though protecting that sergeant would be easier."),
                "protagonist": "ELI", "goal": "keep the record honest", "obstacle": "the sergeant who trained him"},
    "structure": [
        {"id": "ACT1", "name": "The log", "beats": [
            {"id": "B1", "function": "SETUP", "scene_ids": ["SC01"], "summary": "Naomi brings a sealed packet; Hollis refuses to log it unseen and closes the ledger."},
            {"id": "B2", "function": "INCITING", "scene_ids": ["SC02"], "summary": "Hollis demands her name and authority and orders Eli to stop her leaving."}]},
        {"id": "ACT2", "name": "Three warnings", "beats": [
            {"id": "B3", "function": "ESCALATION", "scene_ids": ["SC03"], "summary": "Her record is clean; Hollis keeps her card and makes her sit."},
            {"id": "B4", "function": "ESCALATION", "scene_ids": ["SC04"], "summary": "Hollis guesses at old cases and names Calvin Reed, exposing his fear."},
            {"id": "B5", "function": "MIDPOINT", "scene_ids": ["SC05"], "summary": "Hollis takes the packet under his hand; Naomi gives the first warning."},
            {"id": "B6", "function": "CRISIS", "scene_ids": ["SC06"], "summary": "Eli refuses to write a report of what did not happen and keeps the camera running."},
            {"id": "B7", "function": "CRISIS", "scene_ids": ["SC07"], "summary": "Naomi will not say who is behind the audit and warns Hollis a second time."},
            {"id": "B8", "function": "CRISIS", "scene_ids": ["SC08"], "summary": "She shows what a seal is for; Eli learns that opening it cannot be undone."},
            {"id": "B9", "function": "CRISIS", "scene_ids": ["SC09"], "summary": "Third warning; Naomi steps back and Hollis starts to break the seal."}]},
        {"id": "ACT3", "name": "The call", "beats": [
            {"id": "B10", "function": "CLIMAX", "scene_ids": ["SC10"], "summary": "The cover sheet names Hollis; he asks Eli to turn the camera off and Eli refuses."},
            {"id": "B11", "function": "CLIMAX", "scene_ids": ["SC11"], "summary": "Eli calls upstairs; Hollis walks out on his own and Naomi asks Eli to log the opening."},
            {"id": "B12", "function": "RESOLUTION", "scene_ids": ["SC12"], "summary": "A month later Eli runs the room under a two-signature rule and Calvin Reed signs for his belongings."}]},
    ],
    "plot": ("Naomi brings a sealed packet to be logged out by eleven and Hollis closes the ledger on it (SC01); he demands her name and orders "
             "Eli to stop her leaving (SC02), keeps her card (SC03) and guesses at old cases, naming Calvin Reed (SC04). He takes the packet under "
             "his hand and she warns him the first time (SC05); Eli refuses to write what did not happen (SC06); she warns him a second time (SC07), "
             "explains the seal (SC08) and warns him a third time (SC09). Hollis breaks the seal and finds himself named; Eli refuses to turn the "
             "camera off (SC10); Eli calls upstairs and Hollis walks out on his own (SC11). A month later Eli runs the room under a new rule and "
             "Calvin Reed signs for his property (SC12)."),
    "subplots": [],
    "characters": {
        "ELI": {"id": "ELI", "name": "Deputy Eli Moreno", "role": "protagonist",
                "want": "To keep his place and his sergeant's good opinion.",
                "need": "To keep the record true even when it costs him the man who trained him.",
                "flaw": "He defers to whoever speaks loudest in the room.",
                "arc_change": "From standing quietly by the door to making the call on his own judgement.",
                "change_scene_id": "SC11"},
        "NAOMI": {"id": "NAOMI", "name": "Dr. Naomi Bell", "role": "supporting",
                  "want": "To deliver the sealed packet to the grand jury unopened.",
                  "need": "To let the process, not her, show what the seal protects.",
                  "flaw": "She will not explain, so the warnings sound like threats.",
                  "arc_change": "", "change_scene_id": None},
        "HOLLIS": {"id": "HOLLIS", "name": "Sgt. Wade Hollis", "role": "antagonist",
                   "want": "To know what is inside before it leaves his room.",
                   "need": "To stop and let himself be accountable.",
                   "flaw": "He cannot bear to be seen hesitating.",
                   "arc_change": "", "change_scene_id": None},
        "CALVIN": {"id": "CALVIN", "name": "Calvin Reed", "role": "supporting",
                   "want": "To be heard and to have his property back.",
                   "need": "To be believed.",
                   "flaw": "He no longer expects to be believed.", "arc_change": "", "change_scene_id": None},
    },
    "scenes": {sc: {"purpose": BEATS["scenes"][i]["goal"], "conflict": CONFLICT[sc], "outcome": BEATS["scenes"][i]["outcome"],
                    "value": "integrity", "shift": SHIFT[i]} for i, sc in enumerate(SC)},
    "source_note": ("Premise-only adaptation of an outside story (source SRT sha256 " + SRT_SHA + "): a federal auditor, a sealed file, an official "
                    "who is warned three times and opens it himself, a file that turns out to be about him, and a wrongly convicted man freed. "
                    "Names, setting, conflict mechanics, scene structure, dialogue and ending are new; no source text, audio or metadata is used."),
    "rewrite_log": [
        {"version": 1, "date": "2026-11-14", "reason": "First draft by the Tech Lead for Owner review (docs/production/pilots/film08_chain_of_custody).",
         "changed": "docs/production/pilots/film08_chain_of_custody/script.fountain, beats.json"},
        {"version": 2, "date": "2026-11-14",
         "reason": ("Owner approved the film brief; package built from the draft without a change of meaning, dialogue or order. Only the SC12 "
                    f"heading changed (time of day AFTERNOON, 'one month later' as a note) and an Approval line was added; draft script SHA-256 {DRAFT_SHA}."),
         "changed": "films/film08_chain_of_custody/script.fountain"},
    ],
}

# --------------------------------------------------------------------------------------------------------------------
# 02_direction
# --------------------------------------------------------------------------------------------------------------------
def dl(sc, n):
    return BEATS["scenes"][int(sc[2:]) - 1]["beats"][n - 1]["text_en"]


VISUAL_DETAIL = {"SC10_g01": "HOLLIS breaks the red wax seal of the packet", "SC12_g16": "CALVIN walks in through the hallway door",
                 "SC12_g25": "CALVIN signs the ledger page with the pen"}
FACTS = [
    ("exhibit_due_3B", "A sealed exhibit has to reach grand jury room 3B upstairs by eleven", "SC01_g09", [("DIALOGUE", "SC01_g08")]),
    ("calvin_reed_named", "Hollis fears the old case of Calvin Reed, who was convicted nine years ago", "SC04_g18",
     [("DIALOGUE", "SC04_g16"), ("DIALOGUE", "SC04_g18")]),
    ("hollis_trained_eli", "Hollis calls Eli 'son' as a form of address: he trained Eli, they are not related", "SC06_g08",
     [("DIALOGUE", "SC06_g07")]),
    ("seal_cannot_go_back", "Once the wax seal is broken it cannot be closed again and the opener's name is recorded", "SC05_g12",
     [("DIALOGUE", "SC05_g11")]),
    ("form_names_only_naomi", "The custody form on the packet carries only Naomi's name and times", "SC08_g12", [("DIALOGUE", "SC08_g11")]),
    ("three_warnings", "Naomi warned Hollis three times not to open the packet", "SC09_g22",
     [("DIALOGUE", "SC05_g21"), ("DIALOGUE", "SC07_g23"), ("DIALOGUE", "SC09_g15")]),
    ("hollis_opens_on_camera", "Hollis breaks the seal in front of Eli's body camera", "SC10_g02",
     [("VISUAL", "SC10_g01"), ("DIALOGUE", "SC10_g02")]),
    ("hollis_is_the_subject", "The grand jury cover sheet names Hollis as the subject of an investigation into six cases", "SC10_g15",
     [("DIALOGUE", "SC10_g09"), ("DIALOGUE", "SC10_g14")]),
    ("eli_will_not_switch_off", "Eli refuses to turn his body camera off", "SC11_g13", [("DIALOGUE", "SC10_g25")]),
    ("calvin_weight_changed", "Calvin Reed's evidence weighed eleven grams at intake and fifty-two at trial in Hollis's handwriting", "SC11_g07",
     [("DIALOGUE", "SC11_g05"), ("DIALOGUE", "SC11_g06")]),
    ("hollis_called_upstairs", "The clerk upstairs has called Hollis up and he leaves on his own", "SC11_g20", [("DIALOGUE", "SC11_g19")]),
    ("hollis_indicted", "Hollis has been indicted and suspended, his certification gone", "SC12_g10", [("DIALOGUE", "SC12_g09")]),
    ("calvin_collects", "Calvin Reed has come to collect his belongings after nine years", "SC12_g16",
     [("DIALOGUE", "SC12_g15"), ("VISUAL", "SC12_g16")]),
    ("calvin_signs", "Calvin signs the ledger for his belongings", "SC12_g25", [("DIALOGUE", "SC12_g24"), ("VISUAL", "SC12_g25")]),
]
facts = []
for fid, text, needed, carriers in FACTS:
    cl = []
    for kind, g_id in carriers:
        sc_, n_ = g_id.split("_g")[0], int(g_id.split("_g")[1])
        cl.append({"kind": kind, "generation_id": g_id, "detail": dl(sc_, n_) if kind == "DIALOGUE" else VISUAL_DETAIL[g_id]})
    facts.append({"fact_id": fid, "text": text, "needed_by": needed, "carriers": cl})

KNOWN_AFTER = {"SC01": ["exhibit_due_3B"], "SC04": ["calvin_reed_named"], "SC05": ["seal_cannot_go_back"], "SC08": ["form_names_only_naomi"],
               "SC09": ["three_warnings"], "SC10": ["hollis_opens_on_camera", "hollis_is_the_subject", "eli_will_not_switch_off"],
               "SC11": ["calvin_weight_changed", "hollis_called_upstairs"], "SC12": ["hollis_indicted", "calvin_collects", "calvin_signs"]}
POV = {"SC01": "NAOMI", "SC02": "NAOMI", "SC03": "NAOMI", "SC04": "HOLLIS", "SC05": "NAOMI", "SC06": "ELI", "SC07": "NAOMI", "SC08": "ELI",
       "SC09": "ELI", "SC10": "ELI", "SC11": "ELI", "SC12": "ELI"}
CURVE = {
    "ELI": [(2, 3), (3, 3), (3, 3), (3, 4), (4, 3), (3, 4), (4, 3), (3, 4), (4, 4), (4, 5), (5, 3), (2, 1)],
    "NAOMI": [(2, 2), (2, 2), (2, 2), (2, 3), (3, 3), (3, 3), (3, 3), (3, 3), (3, 4), (4, 3), (3, 3), (2, 2)],
    "HOLLIS": [(3, 3), (3, 4), (4, 3), (3, 4), (4, 4), (4, 3), (3, 4), (4, 4), (4, 5), (5, 5), (5, 3), None],
    "CALVIN": [None] * 11 + [(2, 3)],
}
EMPH = {"SC01": ("The packet has to reach room 3B by eleven", "hold", "SC01_g08", "exhibit_due_3B"),
        "SC05": ("Naomi says the seal cannot go back", "hold", "SC05_g11", "seal_cannot_go_back"),
        "SC09": ("Naomi's third warning", "hold", "SC09_g15", "three_warnings"),
        "SC10": ("The cover sheet names Hollis", "hold", "SC10_g14", "hollis_is_the_subject"),
        "SC11": ("The clerk calls Hollis upstairs", "hold", "SC11_g19", "hollis_called_upstairs"),
        "SC12": ("Calvin signs for his belongings", "hold", "SC12_g25", "calvin_signs")}
HOLDS = {"SC01": ("SC01_g08", 1.0, "hold on Naomi after she names the deadline"),
         "SC02": ("SC02_g19", 3.0, "Hollis studies her face"),
         "SC03": ("SC03_g15", 3.0, "Hollis stares at the clean record"),
         "SC04": ("SC04_g17", 3.0, "Naomi gives nothing back"),
         "SC05": ("SC05_g11", 1.0, "hold on Naomi after the first warning"),
         "SC06": ("SC06_g09", 3.0, "Hollis turns on Eli"),
         "SC07": ("SC07_g08", 3.0, "Naomi lets the question hang"),
         "SC08": ("SC08_g10", 3.0, "Hollis studies the custody form"),
         "SC09": ("SC09_g15", 1.0, "hold on Naomi after the third warning"),
         "SC10": ("SC10_g14", 1.0, "hold on Naomi after she names the six cases"),
         "SC11": ("SC11_g19", 1.0, "hold on Eli after he says the clerk wants Hollis upstairs"),
         "SC12": ("SC12_g25", 1.5, "the pen lies still beside the signed ledger")}
scenes_dir = {}
known: list[str] = []
for i, sc in enumerate(SC):
    known = sorted(set(known) | set(KNOWN_AFTER.get(sc, [])))
    cast_here = CAST[sc]
    curve = {c: {"start": CURVE[c][i][0], "end": CURVE[c][i][1]} for c in cast_here if CURVE[c][i] is not None}
    scenes_dir[sc] = {
        "pov": {"whose": POV[sc], "audience_knows": list(known), "characters_know": {c: list(known) for c in cast_here}},
        "emphasis": ([{"moment": EMPH[sc][0], "device": EMPH[sc][1], "generation_id": EMPH[sc][2], "fact_id": EMPH[sc][3]}] if sc in EMPH else []),
        "curve": curve,
        "pacing": {"target_avg_shot_s": 6.0, "holds": [{"generation_id": HOLDS[sc][0], "seconds": HOLDS[sc][1], "why": HOLDS[sc][2]}]},
        "transition_in": ({"kind": "CUT", "reason": "title card, then a hard cut into the records room"} if sc == "SC01" else
                          {"kind": "CUT", "reason": "continuous morning, the same room" if sc != "SC12" else "a month later, the same room in afternoon light"}),
        "transition_out": {"kind": "CUT", "reason": "continuous morning, the same room" if sc != "SC11" else "a month later, the same room in afternoon light"},
    }

translations = {"CHAIN OF CUSTODY": "CHUỖI LƯU GIỮ", "evidence auditor for the federal court": "kiểm toán viên bằng chứng của tòa liên bang",
                "runs the county records room": "quản lý phòng hồ sơ của hạt", "county deputy, six months on the job": "phó cảnh sát hạt, mới vào nghề sáu tháng",
                "here for his belongings": "đến nhận lại tài sản của mình"}
for s_ in BEATS["scenes"]:
    for b in s_["beats"]:
        if b["kind"] == "dialogue":
            translations[b["text_en"]] = b["text_vi"]

by_scene_cov: dict[str, set[str]] = {}
for g in gens:
    by_scene_cov.setdefault(g["scene_id"], set()).add(g["coverage"])
coverage_plan = {}
for act_ in story["structure"]:
    for beat in act_["beats"]:
        have = set().union(*(by_scene_cov[s] for s in beat["scene_ids"]))
        coverage_plan[beat["id"]] = [c for c in ("MASTER", "SINGLE") if c in have]

direction = {
    "vision": {"tone": "Plain, tense and close: three people in one courthouse records room, the turns carried by faces and long pauses, never by speeches, violence or camera tricks.",
               "references": ["a courthouse records room in flat morning light seen at standing and seated eye level",
                              "a low-key procedural standoff played in pauses and glances"]},
    "visual_rules": [
        {"rule": "Static eye-level camera, no dutch angles, no handheld shake.", "why": "The turn comes from the faces, not from the camera."},
        {"rule": "Keep Hollis screen-left, Eli in the middle and Naomi screen-right in the morning scenes; Eli screen-left and Naomi screen-right in the last scene.",
         "why": "Everyone's place stays readable and the cut never flips who is where."},
        {"rule": "One person moves or handles one prop at a time, never together; no hand-over and no contact.", "why": "Hands on small props and two bodies in contact are the least reliable things the video model does (film01, film04)."},
        {"rule": "Paper never shows legible text: pages stay face down, turned away from the camera or out of focus.", "why": "Generated text on a prop cannot be trusted to read correctly."},
        {"rule": "Singles keep the counter edge, the green wall or the door frame in frame.", "why": "film05: a close single reads as standing or seated by chance; the furniture makes posture readable."},
    ],
    "reveals": [{"fact_id": "seal_cannot_go_back", "scene_id": "SC05"}, {"fact_id": "three_warnings", "scene_id": "SC09"},
                {"fact_id": "hollis_is_the_subject", "scene_id": "SC10"}, {"fact_id": "hollis_called_upstairs", "scene_id": "SC11"},
                {"fact_id": "calvin_signs", "scene_id": "SC12"}],
    "coverage_plan": coverage_plan,
    "scenes": scenes_dir,
    "comprehension": {
        "intros": [{"character": "NAOMI", "label": "DR. NAOMI BELL", "relation": "evidence auditor for the federal court", "needed_by": "SC01_g02", "carriers": []},
                   {"character": "HOLLIS", "label": "SGT. WADE HOLLIS", "relation": "runs the county records room", "needed_by": "SC01_g03", "carriers": []},
                   {"character": "ELI", "label": "DEPUTY ELI MORENO", "relation": "county deputy, six months on the job", "needed_by": "SC01_g12", "carriers": []},
                   {"character": "CALVIN", "label": "CALVIN REED", "relation": "here for his belongings", "needed_by": "SC12_g17", "carriers": []}],
        "facts": facts,
        "tags": [{"character": "NAOMI", "generation_id": "SC01_g02", "start_s": 0.3, "end_s": 4.8, "anchor_x": None, "anchor_y": None},
                 {"character": "HOLLIS", "generation_id": "SC01_g03", "start_s": 0.3, "end_s": 4.8, "anchor_x": None, "anchor_y": None},
                 {"character": "ELI", "generation_id": "SC01_g12", "start_s": 0.3, "end_s": 4.8, "anchor_x": None, "anchor_y": None},
                 {"character": "CALVIN", "generation_id": "SC12_g17", "start_s": 0.3, "end_s": 4.8, "anchor_x": None, "anchor_y": None}],
        "cards": [],
    },
    "translations": translations,
}

(HERE / "01_story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "02_direction.json").write_text(json.dumps(direction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "03_preprod.json").write_text(json.dumps(preprod, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "04_shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote script + 01-04:", len(gens), "generations,", sum(g["duration_s"] for g in gens), "s")
