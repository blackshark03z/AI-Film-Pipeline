"""FLOW-PRODUCTION-SCALE-007 (L2) — freeze Sequence C + 12 ShotSpec fixtures.

RUN007_FLOW_SWORDSMAN_SCALE:
- Sequence A (ADOPTED, read-only): SEQ004_SWORDSMAN_DESCENT (10 proven shots,
  Package-004);
- Sequence B (ADOPTED, read-only): SEQ005_VALLEY_STREAM (8 proven shots,
  Package-005);
- Sequence C (LIVE, this package): SEQ007_DAYLIGHT_ROAD — 3 scenes × 4 shots
  = 12 required slots.

Continuation of the established single-protagonist day: dawn summit ritual
(A) → valley pass descent (A) → valley-floor arrival (B/C) → stream rest and
onward (B/D) → the daylight road: ridge approach (departure), storm gate
(obstacle), high plateau (resolution). No new main identity; the qualified
base reference remains the reference authority for same-reference shots.

editorial_target_duration is frozen BEFORE any generation and is NOT the
provider duration (provider generates 8 s; the edit may use 2.0–6.4 s).
Durations are NOT tuned after seeing clips: targets derive from the frozen
scene design (varied pacing, no 8-second monotony).

Two continuity uploads are pre-committed to within-scene last-frame slots
where the frozen design predicts meaningful benefit:
- SEQ7_F2 conditioned on SEQ7_F1's last frame (obstacle escalation);
- SEQ7_G2 conditioned on SEQ7_G1's last frame (decisive action follows the
  geography re-entry exactly).
All other shots use the same-reference mechanism (budget conservation).

REVISION v2 (pre-execution, zero mutations consumed): the v1 freeze
(1bd32e6) never reached a Generate — 10/12 fixtures were refused at the
compact-prompt gate (FLOW_R2V_COMPACT_PROMPT_LIMIT, 500 chars / 75 words)
BEFORE any provider effect. This v2 applies the required explicit creative
reduction: same shots, same narrative function, same frozen editorial
targets, tighter prose. No threshold was changed; no post-mutation drift.
"""
import json
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures/sequence007"

BASE_MEDIA_ID = "7b725f7b-4da5-4455-a6f2-135c4ba22397"

E = "SCENE_E_RIDGE_APPROACH"
F = "SCENE_F_STORM_GATE"
G = "SCENE_G_HIGH_PLATEAU"

ENV_E = {"time_of_day": "morning", "weather": "clear",
         "atmosphere": "long green ridge road in climbing light"}
ENV_F = {"time_of_day": "midday", "weather": "storm front",
         "atmosphere": "wind-flattened grass at a narrow rock gate"}
ENV_G = {"time_of_day": "late day", "weather": "clearing",
         "atmosphere": "open high plateau under long low light"}


def spec(shot_id, scene_id, purpose, shot_type, framing, lens, role, behavior,
         beats, start, end, invariants, env, props=None, performance=None,
         forbidden=None, lighting=None):
    return {
        "schema_version": "1.0.0", "spec_version": 1,
        "shot_id": shot_id, "scene_id": scene_id,
        "dramatic_purpose": purpose, "duration_target_s": 8,
        "shot_type": shot_type,
        "characters": [{
            "character_id": "swordsman_white_robes",
            "identity_version": "swordsman_white_robes_v1",
            "look_state_id": "white_robes_cloud_summit_dawn_v1",
            "role_in_shot": role, "behavior_state": behavior}],
        "camera": {"framing": framing, "height": "eye_level",
                   "lens_intent": lens,
                   "movement": {"type": "locked"}},
        "environment": env,
        "blocking": {"start": start, "action_beats": beats, "end": end,
                     "prop_interactions": props or []},
        "performance": {"observable_beats": performance or [],
                        "forbidden": forbidden or []},
        "lighting": lighting or {},
        "continuity": {"screen_direction": "faces frame-left",
                       "eyeline": "down the road ahead",
                       "start_state": {}, "end_state": {},
                       "critical_invariants": invariants},
    }


SPECS = {
    # ---- SCENE E — DEPARTURE ------------------------------------------------
    "SEQ7_E1": spec(
        "SEQ7_E1", E,
        "Departure: the rest is over; the road climbs toward the long ridge.",
        "establishing", "EWS", "wide",
        "small figure leaving the stream bank",
        "walks away from the water, frame-left along the road",
        ["the stream drops behind", "the ridge road opens ahead",
         "he moves steadily frame-left"],
        "at the stream bank, frame-right", "small on the ridge road",
        ["ridge road geography stable", "wardrobe unchanged",
         "morning light consistent", "stream bank left behind frame-right"],
        ENV_E),
    "SEQ7_E2": spec(
        "SEQ7_E2", E,
        "Movement: the walk settles into a traveler's rhythm on the climb.",
        "action", "MS", "normal", "figure from the waist up, walking",
        "steady climbing stride; sword settled at the side",
        ["stride lengthens on the slope", "robes swing with the walk",
         "breath stays even"],
        "walking into frame-right", "walking steadily frame-left",
        ["same robes and sword", "road surface stable",
         "morning light consistent"], ENV_E),
    "SEQ7_E3": spec(
        "SEQ7_E3", E,
        "Interaction: a small traveler's ritual at a leaning waymarker.",
        "insert", "MCU", "normal", "hands and chest at the stone",
        "steadies the stone; pulls the chest strap tight",
        ["fingers find the strap", "the buckle draws tight",
         "a beat of stillness"],
        "standing at the waymarker", "strap set; hand leaving the stone",
        ["waymarker stone unchanged once seen",
         "strap and buckle simple leather", "morning light consistent"],
        ENV_E, props=["chest strap"]),
    "SEQ7_E4": spec(
        "SEQ7_E4", E,
        "Transition: he crests a rise; the rock gate shows far ahead.",
        "transition", "WS", "wide", "figure cresting the rise from below",
        "two steps up, then a pause to look",
        ["the rise crests", "a dark narrow gate line shows on the skyline",
         "he stops and looks"],
        "figure below the rise line", "still, looking down the road",
        ["rise geometry stable", "rock gate visible as a dark narrow line",
         "morning light consistent"], ENV_E),

    # ---- SCENE F — OBSTACLE -------------------------------------------------
    "SEQ7_F1": spec(
        "SEQ7_F1", F,
        "Obstacle: the storm front meets him at the narrow rock gate.",
        "establishing", "WS", "wide",
        "figure leaning into wind",
        "he pushes on toward the gate through the gusts",
        ["a gust flattens the grass", "cloud shadow sweeps past",
         "he leans and keeps moving"],
        "mid-approach, frame-right", "close to the rock gate, leaning",
        ["rock gate geography stable", "wardrobe unchanged, wind-blown only",
         "wind direction constant against him"],
        ENV_F,
        lighting={"key_direction": "flat storm light",
                  "contrast": "low, moving cloud shadow",
                  "notes": "racing shadow is the obstacle clock"}),
    "SEQ7_F2": spec(
        "SEQ7_F2", F,
        "Escalation: inside the gate the wind funnels hard.",
        "action", "MS", "normal", "figure from the waist up",
        "shoulder lowered into the wind",
        ["a hard gust hits", "he drives a step through it",
         "robes crack against him"],
        "at the mouth of the gate", "through the worst gust",
        ["rock gate walls consistent with SEQ7_F1 last frame",
         "wardrobe unchanged", "wind direction constant against him"],
        ENV_F,
        performance=["effort shows in posture"],
        forbidden=["no shouting"]),
    "SEQ7_F3": spec(
        "SEQ7_F3", F,
        "Performance: against the rock wall he sets his jaw; the cost, held.",
        "performance", "MCU", "portrait", "face and shoulders, three-quarter",
        "jaw sets; eyes narrow against the wind",
        ["the jaw sets", "eyes narrow", "a slow breath through it"],
        "pressed near the rock wall", "still, holding against the wind",
        ["no face identity drift", "same hair and headband",
         "wind-blown hair only"], ENV_F),
    "SEQ7_F4": spec(
        "SEQ7_F4", F,
        "Button: a hand clamps the sword hilt; a pebble skips past.",
        "insert", "ECU", "normal", "hand on the sword hilt",
        "the hand closes on the hilt as a pebble skips past",
        ["fingers tighten on the wrap", "a pebble skips through frame",
         "the grip holds"],
        "hand near the hilt", "hand committed to the hilt",
        ["hilt and wrap unchanged", "no draw in this shot",
         "storm light consistent"], ENV_F, props=["sword hilt", "pebble"]),

    # ---- SCENE G — RESOLUTION ----------------------------------------------
    "SEQ7_G1": spec(
        "SEQ7_G1", G,
        "Re-entry: beyond the gate the land opens to a high plateau.",
        "establishing", "EWS", "wide",
        "small figure stepping out of the gate",
        "walks out of the rock gate and stops at the open ground",
        ["the gate falls behind", "the plateau opens wide",
         "the light goes long"],
        "at the gate mouth", "standing on open plateau",
        ["plateau geography stable", "rock gate behind, frame-right",
         "late-day light consistent", "storm visually behind"],
        ENV_G),
    "SEQ7_G2": spec(
        "SEQ7_G2", G,
        "Decisive action: one clean draw, one arc, the blade home.",
        "hero", "MS", "normal", "figure from the knees up, drawing",
        "draws the sword in one arc and resheathes",
        ["the draw begins", "one clean arc through the air",
         "the blade seats home"],
        "standing square, hands quiet", "sword sheathed; hands settling",
        ["plateau ground consistent with SEQ7_G1 last frame",
         "one continuous draw-and-resheath, no cuts inside the action",
         "wardrobe unchanged"], ENV_G,
        props=["sword"],
        forbidden=["no second draw"]),
    "SEQ7_G3": spec(
        "SEQ7_G3", G,
        "Close beat: the exhale after the arc; shoulders settle; the day "
        "lets go.", "performance",
        "CU", "portrait", "face, front three-quarter",
        "one long exhale; the shoulders drop; a small ease",
        ["the exhale", "shoulders settle", "a small ease at the eyes"],
        "face still from the effort", "face at rest, eyes forward",
        ["no face identity drift", "same hair and headband",
         "late-day light consistent"], ENV_G),
    "SEQ7_G4": spec(
        "SEQ7_G4", G,
        "Resolution: he walks on into the long light; the road holds.",
        "action", "WS", "wide", "figure walking away down the plateau road",
        "an even walk into the long light, smaller and smaller",
        ["the walk resumes", "the figure shrinks into the light",
         "the road holds the frame"],
        "figure mid-frame, walking", "figure near frame-left edge, small",
        ["plateau road geography stable", "wardrobe unchanged",
         "late-day light consistent", "exit frame-left"], ENV_G),
}

EDITIORIAL_TARGETS = {
    "SEQ7_E1": 6.0, "SEQ7_E2": 4.0, "SEQ7_E3": 3.2, "SEQ7_E4": 2.4,
    "SEQ7_F1": 4.8, "SEQ7_F2": 5.6, "SEQ7_F3": 3.2, "SEQ7_F4": 2.0,
    "SEQ7_G1": 5.6, "SEQ7_G2": 4.0, "SEQ7_G3": 3.2, "SEQ7_G4": 6.4,
}


def continuity_for(shot_id: str) -> dict:
    if shot_id == "SEQ7_F2":
        return {"kind": "last_frame", "from_shot": "SEQ7_F1"}
    if shot_id == "SEQ7_G2":
        return {"kind": "last_frame", "from_shot": "SEQ7_G1"}
    return {"kind": "reference", "media_id": BASE_MEDIA_ID}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    scenes = [
        (E, "Departure: the rest is over; the road climbs toward the ridge.",
         ["SEQ7_E1", "SEQ7_E2", "SEQ7_E3", "SEQ7_E4"]),
        (F, "Obstacle: the storm front meets him at the narrow rock gate.",
         ["SEQ7_F1", "SEQ7_F2", "SEQ7_F3", "SEQ7_F4"]),
        (G, "Resolution: beyond the gate, one clean answer, then the road "
            "again into the long light.",
         ["SEQ7_G1", "SEQ7_G2", "SEQ7_G3", "SEQ7_G4"]),
    ]
    plan = {"sequence_id": "SEQ007_DAYLIGHT_ROAD", "scenes": []}
    for scene_id, purpose, shot_ids in scenes:
        shots = []
        for shot_id in shot_ids:
            (OUT / f"{shot_id}.json").write_text(
                json.dumps(SPECS[shot_id], indent=2, ensure_ascii=False) +
                "\n", encoding="utf-8")
            shots.append({
                "shot_id": shot_id,
                "fixture": f"fixtures/sequence007/{shot_id}.json",
                "continuity": continuity_for(shot_id),
                "editorial_target_duration":
                    EDITIORIAL_TARGETS[shot_id],
                "editorial_duration_note":
                    "frozen before any generation; NOT the provider "
                    "duration; never tuned after seeing clips to hide "
                    "defects"})
        plan["scenes"].append({"scene_id": scene_id,
                               "narrative_purpose": purpose,
                               "shots": shots})
    plan["frozen_note"] = (
        "Frozen before the first live mutation (FLOW-PRODUCTION-SCALE-007 "
        "L2, revision v2): v1 (1bd32e6) never reached a Generate — 10/12 "
        "fixtures were refused at the compact-prompt gate pre-mutation; v2 "
        "applies the required explicit creative reduction with zero "
        "mutations consumed and no threshold change. 3 scenes x 4 shots = "
        "12 required slots; same-reference continuity everywhere except two "
        "pre-committed within-scene last-frame slots (SEQ7_F2 from SEQ7_F1; "
        "SEQ7_G2 from SEQ7_G1); MAX_PRIMARY_GENERATES=12, "
        "MAX_REPAIR_GENERATES=3, MAX_CONTINUITY_UPLOADS=2; "
        "editorial_target_duration frozen before seeing any output.")
    (OUT / "sequence_plan_007.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    scene_targets = {}
    for scene_id, _purpose, shot_ids in scenes:
        scene_targets[scene_id] = round(
            sum(EDITIORIAL_TARGETS[s] for s in shot_ids), 3)
    print(json.dumps({"fixtures": len(SPECS),
                      "scene_targets_s": scene_targets,
                      "sequence_target_s": round(
                          sum(EDITIORIAL_TARGETS.values()), 3),
                      "plan_sha256": sha256(canonical).hexdigest()}))


if __name__ == "__main__":
    main()
