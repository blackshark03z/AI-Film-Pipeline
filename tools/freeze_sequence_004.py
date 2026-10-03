"""Freeze the SEQ004 two-scene sequence plan + ten ShotSpec fixtures."""
import json
from pathlib import Path


def spec(shot_id, scene_id, purpose, shot_type, framing, lens, role, behavior,
         beats, start, end, invariants, env=None):
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
                   "lens_intent": lens, "movement": {"type": "locked"}},
        "environment": env or {"time_of_day": "dawn", "weather": "clear",
                               "atmosphere": "cold summit above cloud-sea"},
        "blocking": {"start": start, "action_beats": beats, "end": end},
        "continuity": {"screen_direction": "faces frame-left",
                       "eyeline": "toward frame-left horizon",
                       "start_state": {}, "end_state": {},
                       "critical_invariants": invariants},
    }


A = "SCENE_A_DAWN_STANCE"
B = "SCENE_B_VALLEY_PASS"
ENV_B = {"time_of_day": "morning", "weather": "clear",
         "atmosphere": "high valley pass below the summits, bright thin light"}
S = {
    "SEQ4_A1": spec("SEQ4_A1", A,
        "Establish the swordsman's dawn summit before the descent.",
        "establishing", "EWS", "wide", "tiny lone figure at frame center",
        "still; cloak stirs lightly",
        ["mist drifts past the summit", "cloak stirs in light wind"],
        "figure centered, back three-quarter to camera", "composition unchanged",
        ["white robes and sword unchanged", "summit and cloud-sea stable",
         "dawn light from frame-left"]),
    "SEQ4_A2": spec("SEQ4_A2", A,
        "The swordsman turns from the vista and steps toward the descent path.",
        "action", "WS", "wide", "figure turning and stepping frame-left",
        "one measured step; cloak sways",
        ["a turn toward frame-left", "two slow steps down-ridge"],
        "standing at the summit center", "mid-step onto the descent path",
        ["same robes and sword", "ridge geography stable",
         "dawn light from frame-left"]),
    "SEQ4_A3": spec("SEQ4_A3", A,
        "Descending the ridge, he pauses to grip the hilt with resolve.",
        "action", "MS", "normal", "figure from waist up on the ridge path",
        "hand closes on the hilt; eyes narrow",
        ["a firm step stops", "hand closes on the hilt"],
        "walking the ridge path", "paused, hand on hilt",
        ["same robes", "hilt wrap consistent", "dawn light from frame-left"]),
    "SEQ4_A4": spec("SEQ4_A4", A,
        "Close on his face: the quiet decision to leave the summit.",
        "performance", "MCU", "portrait",
        "face and shoulders, front three-quarter",
        "one slow breath; gaze drops toward the path",
        ["a slow exhale", "gaze settles down-ridge"],
        "chest-up, gaze on the horizon", "gaze lowered toward the path",
        ["no face identity drift", "same hair and headband",
         "dawn light from frame-left"]),
    "SEQ4_A5": spec("SEQ4_A5", A,
        "Button: he steps out of frame, leaving the empty summit.", "cutaway",
        "WS", "wide", "figure exiting frame-left",
        "two steps carry him past frame-left edge",
        ["steady steps frame-left", "cloak trails past the edge"],
        "figure at frame center", "figure exits frame-left; summit empty",
        ["empty-summit geography stable", "no new elements enter",
         "dawn light from frame-left"]),
    "SEQ4_B1": spec("SEQ4_B1", B,
        "New space: establish the high valley pass below the summit.",
        "establishing", "EWS", "wide",
        "small figure entering frame-right on the pass",
        "figure descends onto the pass",
        ["long slope revealed below", "figure moves frame-left"],
        "figure enters frame-right", "figure mid-pass",
        ["valley pass geography stable", "wardrobe unchanged",
         "morning light consistent"], env=ENV_B),
    "SEQ4_B2": spec("SEQ4_B2", B,
        "Re-entry: closer on the swordsman making the pass in steady strides.",
        "action", "MS", "normal", "figure from waist up, walking",
        "three unhurried strides",
        ["strides settle into rhythm", "cloak sways across the frame"],
        "entering the pass frame-right", "striding mid-pass",
        ["same robes and sword", "pass geography stable",
         "morning light consistent"], env=ENV_B),
    "SEQ4_B3": spec("SEQ4_B3", B,
        "Escalation: wind funnels through the pass; he braces against it.",
        "action", "WS", "wide", "full figure bracing against wind",
        "cloak whips; he plants his footing",
        ["a gust sweeps the pass", "he plants his stance against it"],
        "walking freely", "braced stance against the wind",
        ["robes and sword unchanged", "wind direction from the valley",
         "morning light consistent"], env=ENV_B),
    "SEQ4_B4": spec("SEQ4_B4", B,
        "Close detail: knuckles tighten on the hilt against the wind.",
        "insert", "ECU", "telephoto", "hands and hilt only",
        "fingers tighten one notch; still otherwise",
        ["knuckles whiten", "hilt wrap flexes"],
        "hand loose on the hilt", "firm grip settled",
        ["hilt wrap and blade consistent", "no extra hands",
         "morning light consistent"], env=ENV_B),
    "SEQ4_B5": spec("SEQ4_B5", B,
        "Resolution: past the funnel, he strides on into the bright valley.",
        "hero", "WS", "wide", "full figure striding frame-left",
        "stride lengthens; the valley opens ahead",
        ["a last gust passes", "he strides out of the wind"],
        "braced at the funnel's edge", "striding into the open valley",
        ["same robes and sword", "valley pass stable",
         "morning light consistent"], env=ENV_B),
}

REF = "7b725f7b-4da5-4455-a6f2-135c4ba22397"
plan = {"sequence_id": "SEQ004_SWORDSMAN_DESCENT", "scenes": [
    {"scene_id": A,
     "narrative_purpose":
         "Scene A - dawn decision: the swordsman leaves his summit.",
     "shots": [{"shot_id": sid, "fixture": f"fixtures/sequence004/{sid}.json",
                "continuity": {"kind": "reference", "media_id": REF}}
               for sid in ("SEQ4_A1", "SEQ4_A2", "SEQ4_A3",
                           "SEQ4_A4", "SEQ4_A5")]},
    {"scene_id": B,
     "narrative_purpose":
         "Scene B - morning passage: the descent continues through the "
         "valley pass.",
     "shots": [{"shot_id": sid, "fixture": f"fixtures/sequence004/{sid}.json",
                "continuity": {"kind": "reference", "media_id": REF}}
               for sid in ("SEQ4_B1", "SEQ4_B2", "SEQ4_B3",
                           "SEQ4_B4", "SEQ4_B5")]}]}
plan["frozen_note"] = (
    "Frozen before the first live mutation: 2 scenes, 10 shot slots, "
    "same-reference continuity throughout (last-frame mechanism already "
    "PROVEN in Scene-003; no upload budget needed for this sequence).")

out = Path("fixtures/sequence004")
out.mkdir(parents=True, exist_ok=True)
for name, s in S.items():
    (out / f"{name}.json").write_text(
        json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(out / "sequence_plan_004.json").write_text(
    json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("froze", len(S), "specs + sequence plan")
