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
         "atmosphere": "wind-flattened grass and racing cloud shadow at a "
                      "narrow rock gate"}
ENV_G = {"time_of_day": "late day", "weather": "clearing",
         "atmosphere": "open high plateau under long, low light"}


def spec(shot_id, scene_id, purpose, shot_type, framing, lens, role, behavior,
         beats, start, end, invariants, env, movement=None, eyeline=None,
         props=None, performance=None, lighting=None):
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
                   "movement": movement or {"type": "locked"}},
        "environment": env,
        "blocking": {"start": start, "action_beats": beats, "end": end,
                     "prop_interactions": props or []},
        "performance": performance or {"observable_beats": [],
                                       "forbidden": []},
        "lighting": lighting or {},
        "continuity": {"screen_direction": "faces frame-left",
                       "eyeline": eyeline or "down the road ahead",
                       "start_state": {}, "end_state": {},
                       "critical_invariants": invariants},
    }


SPECS = {
    # ---- SCENE E — DEPARTURE ------------------------------------------------
    "SEQ7_E1": spec(
        "SEQ7_E1", E,
        "Departure orientation: the stream rest is over; the road climbs "
        "toward a long ridge and he takes it.", "establishing",
        "EWS", "wide", "small figure leaving the stream bank onto the "
        "ridge road",
        "figure walks away from the water, frame-left along the road",
        ["the stream drops behind", "the ridge road opens ahead",
         "figure moves steadily frame-left"],
        "figure at the stream bank, frame-right",
        "figure small on the ridge road",
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
        "Interaction: he pauses at a leaning waymarker stone and resets the "
        "strap across his chest — a traveler's small ritual.", "insert",
        "MCU", "normal", "hands and chest at the waymarker stone",
        "one hand steadies the stone; the other pulls the strap tight",
        ["fingers find the strap", "the buckle draws tight",
         "a beat of stillness"],
        "standing at the waymarker", "strap set; hand leaving the stone",
        ["waymarker stone unchanged once seen", "strap and buckle simple "
         "leather", "morning light consistent"],
        ENV_E, props=["waymarker stone", "chest strap"]),
    "SEQ7_E4": spec(
        "SEQ7_E4", E,
        "Transition beat: he crests a rise and the path narrows toward a "
        "dark line of rock — the gate is visible far ahead.", "transition",
        "WS", "wide", "figure cresting the rise from below",
        "two more steps up, then a pause to look",
        ["the rise crests", "the narrow rock gate shows on the skyline",
         "he stops and looks"],
        "figure below the rise line", "figure still, looking down the road",
        ["rise geometry stable", "rock gate visible as a dark narrow line",
         "morning light consistent"], ENV_E),

    # ---- SCENE F — OBSTACLE -------------------------------------------------
    "SEQ7_F1": spec(
        "SEQ7_F1", F,
        "Obstacle established: the storm front arrives — wind flattens the "
        "grass and cloud shadow races across the approach to the rock gate.",
        "establishing", "WS", "wide",
        "figure leaning into wind on the approach",
        "grass bends in waves; the figure pushes on toward the gate",
        ["a gust flattens the grass", "cloud shadow sweeps the ground",
         "the figure leans and keeps moving"],
        "figure mid-approach, frame-right",
        "figure close to the rock gate, leaning",
        ["rock gate geography stable", "wardrobe unchanged, wind-blown only",
         "wind direction constant (against him)"],
        ENV_F,
        lighting={"key_direction": "flat storm light",
                  "contrast": "low, moving cloud shadow",
                  "notes": "racing shadow is the obstacle clock"}),
    "SEQ7_F2": spec(
        "SEQ7_F2", F,
        "Escalation: inside the gate the wind funnels; he crosses with "
        "his shoulder lowered, robes cracking.", "action",
        "MS", "normal", "figure from the waist up, forcing the passage",
        "shoulder lowered into the wind; one hard step at a time",
        ["a hard gust hits", "he drives a step through it",
         "robes crack flat against him"],
        "at the mouth of the gate", "through the worst of the funnel",
        ["rock gate walls consistent with SEQ7_F1 last frame",
         "wardrobe unchanged", "wind direction constant (against him)"],
        ENV_F,
        performance={"observable_beats": ["effort shows in the posture, "
                                          "not the face"],
                     "forbidden": ["no shouting", "no new wounds"]}),
    "SEQ7_F3": spec(
        "SEQ7_F3", F,
        "Performance: against the rock wall he sets his jaw and squints "
        "into the wind — the cost, held.", "performance",
        "MCU", "portrait", "face and shoulders, three-quarter",
        "jaw sets; eyes narrow against the wind; one breath",
        ["the jaw sets", "eyes narrow", "a slow breath through it"],
        "pressed near the rock wall", "still, holding against the wind",
        ["no face identity drift", "same hair and headband",
         "wind-blown hair only"], ENV_F),
    "SEQ7_F4": spec(
        "SEQ7_F4", F,
        "Button insert: a hand clamps the sword hilt; a pebble skitters "
        "past — hold, then move.", "insert",
        "ECU", "normal", "hand on the sword hilt",
        "the hand closes on the hilt; a pebble skips past the feet",
        ["fingers tighten on the wrap", "a pebble skips through frame",
         "the grip holds"],
        "hand near the hilt", "hand committed to the hilt",
        ["hilt and wrap unchanged", "no draw in this shot",
         "storm light consistent"], ENV_F, props=["sword hilt", "pebble"]),

    # ---- SCENE G — RESOLUTION ----------------------------------------------
    "SEQ7_G1": spec(
        "SEQ7_G1", G,
        "Re-entry: beyond the gate the land opens — a high plateau under "
        "long, low light; the storm is behind him.", "establishing",
        "EWS", "wide", "small figure stepping out of the gate onto the "
        "plateau",
        "figure walks out of the rock gate and stops at the open ground",
        ["the gate falls behind", "the plateau opens wide",
         "the light goes long and low"],
        "figure at the gate mouth", "figure standing on open plateau",
        ["plateau geography stable", "rock gate behind, frame-right",
         "late-day light consistent", "storm visually behind"],
        ENV_G),
    "SEQ7_G2": spec(
        "SEQ7_G2", G,
        "Decisive action: one clean draw, a single arc through the air, and "
        "the blade returns home — the day's answer.", "hero",
        "MS", "normal", "figure from the knees up, drawing",
        "draws the sword in one arc and resheathes without hurry",
        ["the draw begins", "one clean arc through the air",
         "the blade seats home"],
        "standing square, hands quiet", "sword sheathed; hands settling",
        ["plateau ground consistent with SEQ7_G1 last frame",
         "one continuous draw-and-resheath, no cuts inside the action",
         "wardrobe unchanged"], ENV_G,
        props=["sword"],
        performance={"observable_beats": ["the arc is unhurried and exact"],
                     "forbidden": ["no flourish", "no second draw"]}),
    "SEQ7_G3": spec(
        "SEQ7_G3", G,
        "Close beat: the exhale after the arc; shoulders settle; the day "
        "lets go.", "performance",
        "CU", "portrait", "face, front three-quarter",
        "one long exhale; the shoulders drop; the faintest ease",
        ["the exhale", "shoulders settle", "a small ease at the eyes"],
        "face still from the effort", "face at rest, eyes forward",
        ["no face identity drift", "same hair and headband",
         "late-day light consistent"], ENV_G),
    "SEQ7_G4": spec(
        "SEQ7_G4", G,
        "Resolution and exit: he walks on along the plateau as the light "
        "goes long, and the frame keeps the road, not the man.", "action",
        "WS", "wide", "figure walking away down the plateau road",
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
        "L2): 3 scenes x 4 shots = 12 required slots; same-reference "
        "continuity everywhere except two pre-committed within-scene "
        "last-frame slots (SEQ7_F2 from SEQ7_F1; SEQ7_G2 from SEQ7_G1); "
        "MAX_PRIMARY_GENERATES=12, MAX_REPAIR_GENERATES=3, "
        "MAX_CONTINUITY_UPLOADS=2; editorial_target_duration frozen before "
        "seeing any output. Prompt wording avoids concrete-noun metaphors "
        "(Scene-004 funnel lesson).")
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
                      "sequence_target_s": round(sum(EDITIORIAL_TARGETS.values()), 3),
                      "plan_sha256": sha256(canonical).hexdigest()}))


if __name__ == "__main__":
    main()
