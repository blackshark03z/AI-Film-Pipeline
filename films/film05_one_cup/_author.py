"""Authoring helper for film05 03_preprod.json + 04_shots.json (kept with the package; re-run after edits)."""
import json
from pathlib import Path

HERE = Path(__file__).parent

HAL_LOOK = "man in his seventies, short white hair, grey stubble, navy wool cardigan over a checked flannel shirt"
IRIS_LOOK = "woman in her thirties, dark hair in a short bob, camel wool coat buttoned over a black sweater"

KEY = "the key:"
MUGS = "the mugs:"
CHAIR = "the empty chair:"
KEY_S = "flat on the table in front of the empty chair"
MUGS_S = "two white mugs on the table, the second one steaming beside the key"
CHAIR_S = "pulled out from the table on the left"


def pose(mark, posture, facing):
    return {"mark": mark, "posture": posture, "facing": facing}


HAL_SEATED = pose("hal_chair", "seated at the table, hands resting in his lap", "IRIS")
IRIS_STANDING = pose("iris_stand", "standing beside the empty chair, coat buttoned, hands in her coat pockets", "HAL")
IRIS_SEATED = pose("iris_chair", "seated in the chair across the table from HAL, coat on, hands in her lap", "HAL")


def state(iris_pose=IRIS_STANDING, chair=CHAIR_S):
    seated = iris_pose is IRIS_SEATED
    return {
        "positions": {
            "IRIS": ("seated across the table, frame-left" if seated else "standing across the table, frame-left"),
            "HAL": "seated at the table, frame-right",
        },
        "props": {KEY: KEY_S, MUGS: MUGS_S, CHAIR: chair},
        "looks": {"IRIS": "iris_coat", "HAL": "hal_cardigan"},
        "lighting": "", "time_of_day": "", "location": "",
        "blocking": {"IRIS": iris_pose, "HAL": HAL_SEATED},
    }


GIDS = ["SC01_g1", "SC01_g2", "SC02_g1", "SC02_g2", "SC03_g1", "SC03_g2", "SC04_g1", "SC04_g2", "SC05_g1", "SC06_g1"]
states = {}
for gid in GIDS:
    states[gid] = state()
for sc in ["SC01", "SC02", "SC03", "SC04", "SC05"]:
    states[f"{sc}_end"] = state()
states["SC06_end"] = state(IRIS_SEATED)
states["SC06_end"]["props"].pop(CHAIR)

lighting = {
    "key_direction": "BACK", "quality": "SOFT", "colour_temp_k": 4500, "contrast": "MEDIUM",
    "motivation": "blue dawn light from the window behind the table, a warm pendant lamp above it",
    "practicals": [{"kind": "WINDOW", "note": "window behind the table, blue dawn"},
                   {"kind": "LAMP", "note": "warm pendant lamp over the table"}],
}

scenes = {}
for i, sc in enumerate(["SC01", "SC02", "SC03", "SC04", "SC05", "SC06"], start=1):
    scenes[sc] = {
        "location": "kitchen_dawn",
        "axis": {"scene_id": sc, "axis_pair": ["IRIS", "HAL"], "sides": {"IRIS": "LEFT", "HAL": "RIGHT"}},
        "occupancy": {"scene_id": sc, "initial": ["IRIS", "HAL"], "events": []},
        "story_time": {"scene_id": sc, "story_order": float(i), "transition_in": "LINEAR", "marker": "", "source_conflict": ""},
        "extras": "",
        "lighting": lighting,
        "encounter_id": "kitchen_goodbye",
    }

layout = {
    "zones": [{"id": "kitchen", "label": "kitchen", "box": [0.05, 0.05, 0.95, 0.95]}],
    "objects": [
        {"id": "table", "label": "square wooden table", "zone": "kitchen",
         "placement": "in the middle of the kitchen, the window behind it", "at": [0.5, 0.5]},
        {"id": "window", "label": "window", "zone": "kitchen",
         "placement": "in the back wall behind the table, blue dawn outside", "at": [0.5, 0.06]},
        {"id": "lamp", "label": "warm pendant lamp", "zone": "kitchen",
         "placement": "hanging low over the middle of the table", "at": [0.5, 0.48]},
        {"id": "kettle", "label": "kettle", "zone": "kitchen",
         "placement": "on the counter along the back wall, right of the window", "at": [0.82, 0.1]},
        {"id": "key", "label": "brass key", "zone": "kitchen",
         "placement": "flat on the table near the edge in front of the empty chair", "at": [0.42, 0.53]},
        {"id": "mug_hal", "label": "white mug", "zone": "kitchen",
         "placement": "on the table in front of HAL", "at": [0.6, 0.5]},
        {"id": "mug_iris", "label": "second white mug, steaming", "zone": "kitchen",
         "placement": "on the table in front of the empty chair, beside the key", "at": [0.45, 0.49]},
        {"id": "empty_chair", "label": "empty wooden chair", "zone": "kitchen",
         "placement": "pulled out from the table on the left side, facing HAL", "at": [0.32, 0.5]},
    ],
    "cameras": [
        {"id": "A", "zone": "kitchen",
         "view": "Camera in front of the table at seated eye level, facing the window: IRIS on the left, HAL on the right, the window between them",
         "sees": ["table", "window", "lamp", "kettle", "key", "mug_hal", "mug_iris", "empty_chair"], "at": [0.5, 0.92], "look_at": "table"},
        {"id": "B", "zone": "kitchen",
         "view": "Camera front-left, beyond the left end of the table, facing HAL across the table",
         "sees": ["table", "window", "kettle", "mug_hal", "mug_iris", "key"], "at": [0.2, 0.68], "look_at": "mug_hal"},
        {"id": "C", "zone": "kitchen",
         "view": "Camera front-right, beyond the right end of the table, facing IRIS across the table",
         "sees": ["table", "window", "key", "mug_iris", "empty_chair"], "at": [0.8, 0.68], "look_at": "empty_chair"},
        {"id": "D", "zone": "kitchen",
         "view": "Camera low and close at the table edge, looking along the tabletop at the key and the second mug",
         "sees": ["table", "key", "mug_iris"], "at": [0.44, 0.62], "look_at": "key"},
    ],
    "marks": [
        {"id": "hal_chair", "at": [0.68, 0.5], "zone": "kitchen"},
        {"id": "iris_stand", "at": [0.28, 0.58], "zone": "kitchen"},
        {"id": "iris_chair", "at": [0.32, 0.5], "zone": "kitchen"},
    ],
}

feas = {"max_speakers": 2, "max_in_frame": 3, "max_dialogue_syllables": 28, "scene_duration_s": 16.0,
        "min_silence_s": 3.0, "syllables_per_second": 2.5}

designs = {
    "IRIS_look": {"kind": "look", "version": 1, "owner": "IRIS", "note": "locked CharacterLook text"},
    "IRIS_costume": {"kind": "costume", "version": 1, "owner": "IRIS", "note": "camel wool coat buttoned over a black sweater"},
    "HAL_look": {"kind": "look", "version": 1, "owner": "HAL", "note": "locked CharacterLook text"},
    "HAL_costume": {"kind": "costume", "version": 1, "owner": "HAL", "note": "navy wool cardigan over a checked flannel shirt"},
    "loc_kitchen_dawn": {"kind": "location", "version": 1, "owner": "kitchen_dawn"},
    "prop_key": {"kind": "prop", "version": 1, "prop": "the key"},
    "prop_mugs": {"kind": "prop", "version": 1, "prop": "the mugs"},
}

pending = lambda subject, kind, what: {"subject": subject, "kind": kind, "status": "pending", "evidence": "",
                                        "note": f"{what}, model-written for this film; Owner to confirm originality"}
rights = [
    pending("IRIS", "character", "fictional character"),
    pending("HAL", "character", "fictional character"),
    pending("kitchen_dawn", "location", "fictional set"),
    {"subject": "none (room tone and SFX are generated or CC0)", "kind": "music", "status": "original",
     "evidence": "films/film05_one_cup has no music stage", "note": "no music track in the film"},
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
        "IRIS": {"look": {"look_id": "iris_coat", "character": "IRIS", "text": IRIS_LOOK,
                          "invariants": ["dark hair in a short bob", "camel wool coat", "black sweater"], "approved": True},
                 "video_text": IRIS_LOOK, "voice": "quiet clear female voice", "handle": "the woman"},
        "HAL": {"look": {"look_id": "hal_cardigan", "character": "HAL", "text": HAL_LOOK,
                         "invariants": ["short white hair", "grey stubble", "navy wool cardigan", "checked flannel shirt"], "approved": True},
                "video_text": HAL_LOOK, "voice": "low gravelly male voice", "handle": "the old man"},
    },
    "locations": {
        "kitchen_dawn": {
            "look": {"look_id": "kitchen_dawn", "location": "BRENNAN KITCHEN",
                     "text": "Small kitchen at dawn: square wooden table, two chairs, window behind with blue dawn light, warm pendant lamp, kettle on the counter",
                     "invariants": ["square wooden table", "window behind the table with blue dawn light",
                                    "warm pendant lamp over the table", "kettle on the counter"],
                     "interior": True, "time_of_day": "DAWN", "weather_outside": "clear, first light",
                     "environment_rules": ["the light outside the window grows slowly brighter, never changes colour"],
                     "approved": True},
            "room_tone": "quiet kitchen hum, a clock ticking",
            "layout": layout,
        }
    },
    "scenes": scenes,
    "states": states,
    "still_templates": {
        "framing": {"MASTER": "wide shot of the whole room", "OTS": "medium over-the-shoulder shot",
                    "SINGLE": "close-up", "TWO_SHOT": "medium two-shot of both people side by side",
                    "REACTION": "insert close-up of the set, nobody in frame"},
        "character": "Photoreal character reference portrait, 16:9, plain warm grey studio backdrop, head and shoulders, front view, neutral expression, soft even light: {text}. No text, no logos.",
        "plate": "Photoreal empty set plate, 16:9, eye-level wide view, nobody in the room: {text}. No people, no text, no logos.",
        "pose": True,
    },
    "accepted_overlong": {},
    "designs": designs,
    "rights": rights,
    "risk_fallbacks": {
        "SC06_g1": "if the sit-down does not render cleanly, cut on IRIS's line in a SINGLE and hold the end on the empty-chair master; no second send of the same staging",
    },
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

BASE_REFS = ["IRIS_look@1", "IRIS_costume@1", "HAL_look@1", "HAL_costume@1", "loc_kitchen_dawn@1", "prop_key@1", "prop_mugs@1"]


def cam(size, composition, lens="NORMAL"):
    return {"size": size, "angle": "EYE_LEVEL", "height": "EYE", "movement": "STATIC", "lens_intent": lens,
            "composition": composition}


def perf(ch, intent, cues, intensity="restrained", misread="anger"):
    return {"character": ch, "emotion_intent": intent, "visible_cues": cues, "intensity": intensity,
            "prohibited_misread": misread}


def gen(gid, coverage, subject, foreground, visible, phases, once, performance, dialogue, camera, campos, duration,
        addressees=None, anchors=None, gaze=None, end_state=None, readout=None, **extra):
    sc = gid.split("_")[0]
    g = {
        "generation_id": gid, "scene_id": sc, "coverage": coverage, "subject": subject, "foreground": foreground,
        "visible": visible, "start_state": gid, "end_state": end_state or f"{sc}_end", "previous_generation_id": None,
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


OFF_LEFT = {"mode": "OFF_FRAME", "side": "LEFT", "placement": "IRIS stands just off frame-left across the table",
            "established_by": "SC01_g1"}
OFF_RIGHT = {"mode": "OFF_FRAME", "side": "RIGHT", "placement": "HAL sits just off frame-right across the table",
             "established_by": "SC01_g1"}

gens = [
    gen("SC01_g1", "MASTER", "HAL", "", ["IRIS", "HAL"],
        [("SETUP", 0.0, 2.5, "IRIS stands still across the table; HAL looks down at the key on the table", ""),
         ("ACTION", 2.5, 3.3, "HAL raises his eyes to IRIS", "glance"),
         ("ACTION", 3.3, 6.0, "HAL speaks to IRIS", ""),
         ("HOLD", 6.0, 8.0, "IRIS holds his look and does not answer yet", "")],
        ["HAL speaks to IRIS"],
        [perf("HAL", "dry, guarded", ["level look", "flat mouth"])],
        [15], cam("WIDE", "master from the front of the table: IRIS standing on the left beside the empty chair, HAL seated on the right, the dawn window between them, the key and the two mugs on the table", "WIDE_ESTABLISH"),
        "A", 8, addressees={"15": ["IRIS"]}, anchors={"IRIS": {"mode": "VISIBLE"}}, gaze="IRIS",
        end_state="SC01_end",
        readout=[{"fact": "she has brought the key back", "evidence": ["IRIS", "key"]}]),
    gen("SC01_g2", "SINGLE", "IRIS", "", ["IRIS"],
        [("SETUP", 0.0, 1.5, "IRIS looks down at HAL across the table", ""),
         ("ACTION", 1.5, 5.0, "IRIS speaks to HAL", ""),
         ("HOLD", 5.0, 7.0, "IRIS waits, her hands in her coat pockets, eyes on HAL", "")],
        ["IRIS speaks to HAL"],
        [perf("IRIS", "steady, holding back", ["small swallow", "eyes stay on him"])],
        [18], cam("CLOSE", "close single on IRIS standing, the dawn window soft behind her left shoulder, HAL out of frame to the right"),
        "C", 7, addressees={"18": ["HAL"]}, anchors={"HAL": OFF_RIGHT}, gaze="HAL"),
    gen("SC02_g1", "OTS", "HAL", "IRIS", ["HAL", "IRIS"],
        [("SETUP", 0.0, 1.5, "HAL sits looking up at IRIS", ""),
         ("ACTION", 1.5, 3.5, "HAL speaks to IRIS", ""),
         ("HOLD", 3.5, 6.0, "HAL waits for her answer, eyes on IRIS", "")],
        ["HAL speaks to IRIS"],
        [perf("HAL", "tired, a little bitter", ["raised eyebrows", "slow breath"])],
        [23], cam("MEDIUM", "over IRIS's left shoulder onto HAL seated at the table: the back of IRIS's coat and bob at the left edge, HAL on the right looking up at her"),
        "B", 6, addressees={"23": ["IRIS"]}, anchors={"IRIS": {"mode": "OTS_FOREGROUND"}}, gaze="IRIS"),
    gen("SC02_g2", "SINGLE", "IRIS", "", ["IRIS"],
        [("SETUP", 0.0, 1.0, "IRIS looks down at HAL", ""),
         ("ACTION", 1.0, 4.5, "IRIS speaks to HAL", ""),
         ("HOLD", 4.5, 7.0, "IRIS lifts her chin slightly and holds his look", "")],
        ["IRIS speaks to HAL"],
        [perf("IRIS", "firm, proud", ["chin lifts", "steady eyes"], misread="joy")],
        [26], cam("CLOSE", "close single on IRIS standing, the dawn window behind her, HAL out of frame to the right"),
        "C", 7, addressees={"26": ["HAL"]}, anchors={"HAL": OFF_RIGHT}, gaze="HAL"),
    gen("SC03_g1", "SINGLE", "HAL", "", ["HAL"],
        [("SETUP", 0.0, 1.5, "HAL looks down at the key", ""),
         ("ACTION", 1.5, 4.5, "HAL speaks to IRIS without looking up", ""),
         ("ACTION", 4.5, 5.5, "HAL raises his eyes to IRIS", "glance"),
         ("HOLD", 5.5, 7.0, "HAL holds her look", "")],
        ["HAL speaks to IRIS"],
        [perf("HAL", "hurt, pointed", ["eyes down", "tight jaw"])],
        [33], cam("CLOSE", "close single on HAL seated, the kettle and the window soft behind him, IRIS out of frame to the left"),
        "B", 7, addressees={"33": ["IRIS"]}, anchors={"IRIS": OFF_LEFT}, gaze="key"),
    gen("SC03_g2", "OTS", "IRIS", "HAL", ["IRIS", "HAL"],
        [("SETUP", 0.0, 1.0, "IRIS looks down at HAL", ""),
         ("ACTION", 1.0, 5.0, "IRIS speaks to HAL, quietly", ""),
         ("HOLD", 5.0, 8.0, "IRIS stays still, eyes wet, waiting for him", "")],
        ["IRIS speaks to HAL"],
        [perf("IRIS", "hurt, controlled", ["eyes glisten", "slow breath"], misread="shouting")],
        [36], cam("MEDIUM", "over HAL's right shoulder onto IRIS standing across the table: HAL's white hair and cardigan shoulder at the right edge, IRIS on the left looking down at him"),
        "C", 8, addressees={"36": ["HAL"]}, anchors={"HAL": {"mode": "OTS_FOREGROUND"}}, gaze="HAL"),
    gen("SC04_g1", "SINGLE", "HAL", "", ["HAL"],
        [("HOLD", 0.0, 3.0, "HAL looks at the key on the table for a long moment, quite still", ""),
         ("ACTION", 3.0, 4.0, "HAL raises his eyes to IRIS", "glance"),
         ("ACTION", 4.0, 7.0, "HAL speaks to IRIS, gently", ""),
         ("HOLD", 7.0, 8.0, "HAL's face softens", "")],
        ["HAL speaks to IRIS"],
        [perf("HAL", "letting go, tender", ["long look down", "softening eyes"], misread="tears")],
        [43], cam("CLOSE", "close single on HAL seated, the window soft behind him, IRIS out of frame to the left"),
        "B", 8, addressees={"43": ["IRIS"]}, anchors={"IRIS": OFF_LEFT}, gaze="IRIS"),
    gen("SC04_g2", "REACTION", "", "", [],
        [("SETUP", 0.0, 1.5, "the brass key lies flat beside the second white mug on the wooden table, nobody in frame, no hands", ""),
         ("ACTION", 1.5, 4.0, "everything stays still; only thin steam rises from the mug in the dawn light", "")],
        ["only thin steam rises from the mug"],
        [], [], cam("INSERT", "insert along the tabletop: the brass key in the foreground, the second white mug just behind it with thin steam rising, the window blurred beyond", "SHALLOW_ISOLATE"),
        "D", 4,
        readout=[{"fact": "he made her a cup of tea before she came", "evidence": ["mug_iris", "key"]}]),
    gen("SC05_g1", "SINGLE", "IRIS", "", ["IRIS"],
        [("SETUP", 0.0, 1.0, "IRIS looks down at the table", ""),
         ("ACTION", 1.0, 2.0, "IRIS's eyes move from the key to the steaming mug", "glance"),
         ("ACTION", 2.0, 4.5, "IRIS speaks to HAL, almost a whisper", ""),   # v2: was 2-3.5 s, 'tea' clipped
         ("HOLD", 4.5, 6.0, "IRIS looks up at HAL, her face softening", "")],
        ["IRIS speaks to HAL"],
        [perf("IRIS", "moved, surprised", ["eyes soften", "lips part"], misread="laughter")],
        [52], cam("CLOSE", "close single on IRIS standing, the dawn window behind her, HAL out of frame to the right"),
        "C", 6, addressees={"52": ["HAL"]}, anchors={"HAL": OFF_RIGHT}, gaze="mug_iris"),
    gen("SC06_g1", "MASTER", "IRIS", "", ["IRIS", "HAL"],
        [("SETUP", 0.0, 1.0, "IRIS stands by the empty chair", ""),
         ("ACTION", 1.0, 3.0, "IRIS sits down in the empty chair", "sit_down"),
         ("ACTION", 3.0, 5.5, "IRIS speaks to HAL; HAL nods slowly", ""),
         ("HOLD", 5.5, 8.0, "both sit still as the window brightens", "")],
        ["IRIS sits down in the empty chair", "HAL nods slowly"],
        [perf("IRIS", "decided, warm", ["small smile"], misread="sadness"),
         perf("HAL", "relieved", ["shoulders drop"], misread="tears")],
        [59], cam("WIDE", "master from the front of the table, as SC01_g1: IRIS on the left, HAL seated on the right, the window between them, the key and the two mugs on the table", "WIDE_ESTABLISH"),
        "A", 8, addressees={"59": ["HAL"]}, anchors={"HAL": {"mode": "VISIBLE"}}, gaze="HAL",
        end_frame=True,
        end_pose="IRIS sits in the chair across the table from HAL, coat still on, hands in her lap, facing him; HAL seated, facing her"),
]
READOUTS = {
    "SC01_g2": [{"fact": "she came to say goodbye in person", "evidence": ["IRIS"]}],
    "SC02_g1": [{"fact": "he expects she is leaving again", "evidence": ["HAL"]}],
    "SC02_g2": [{"fact": "she is moving to Lisbon for a job", "evidence": ["IRIS"]}],
    "SC03_g1": [{"fact": "he thinks she will leave like her mother did", "evidence": ["HAL"]}],
    "SC03_g2": [{"fact": "she will not be compared to her mother", "evidence": ["IRIS"]}],
    "SC04_g1": [{"fact": "he gives the key back to her", "evidence": ["HAL"]}],
    "SC05_g1": [{"fact": "she sees he made her tea", "evidence": ["IRIS", "mug_iris"]}],
    "SC06_g1": [{"fact": "she stays for one cup before she goes", "evidence": ["IRIS", "empty_chair"]}],
}
for g in gens:
    if g['generation_id'] in READOUTS:
        g['readout'] = READOUTS[g['generation_id']]
CHAIN = {"SC01_g2": "SC01_g1", "SC02_g2": "SC02_g1", "SC03_g2": "SC03_g1", "SC04_g2": "SC04_g1"}
for g in gens:
    gid = g["generation_id"]
    if gid in CHAIN:
        g["previous_generation_id"] = CHAIN[gid]
    if gid in CHAIN.values():
        g["end_state"] = [k for k, v in CHAIN.items() if v == gid][0]
# v1 sends that made no Flow clip (no video tile, no failed tile left; reconcile NOT_IN_GALLERY): SC02_g2 2026-11-09 12:09,
# SC04_g1 2026-11-09; v2 = same prompt
# SC05_g1 v2 (2026-11-09): speak phase 2-4.5 s after dialoguecheck heard "t" for "tea" in t1
VERSIONS = {"SC02_g2": 2, "SC04_g1": 2, "SC05_g1": 2}
for g in gens:
    g["version"] = VERSIONS.get(g["generation_id"], 1)
# SC06_g1 ends seated
for g in gens:
    if g["generation_id"] == "SC06_g1":
        g["end_state"] = "SC06_end"

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
