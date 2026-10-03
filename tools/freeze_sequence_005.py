"""Freeze SEQ005 two-scene sequence plan + eight ShotSpec fixtures."""
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
        "environment": env or {"time_of_day": "morning", "weather": "clear",
                               "atmosphere": "green valley floor in thin bright light"},
        "blocking": {"start": start, "action_beats": beats, "end": end},
        "continuity": {"screen_direction": "faces frame-left",
                       "eyeline": "down the valley path",
                       "start_state": {}, "end_state": {},
                       "critical_invariants": invariants},
    }


C = "SCENE_C_VALLEY_FLOOR"
D = "SCENE_D_STREAM_REST"
ENV_D = {"time_of_day": "late morning", "weather": "clear",
         "atmosphere": "quiet stream bank in dappled green light"}
S = {
    "SEQ5_C1": spec("SEQ5_C1", C,
        "New space: the valley floor opens green below the pass.", "establishing",
        "EWS", "wide", "small figure entering across the meadow",
        "figure walks frame-left across the meadow",
        ["long grass parts along the path", "figure moves steadily frame-left"],
        "figure enters frame-right", "figure mid-meadow",
        ["valley floor geography stable", "wardrobe unchanged",
         "morning light consistent"]),
    "SEQ5_C2": spec("SEQ5_C2", C,
        "Closer: the descent done, he walks lighter on flat ground.", "action",
        "MS", "normal", "figure from waist up, walking",
        "relaxed stride; sword settled at the side",
        ["stride loosens", "eyes take in the valley"],
        "walking into frame-right", "walking steadily frame-left",
        ["same robes and sword", "meadow path stable",
         "morning light consistent"]),
    "SEQ5_C3": spec("SEQ5_C3", C,
        "He pauses where the meadow breaks toward the trees.", "performance",
        "MCU", "portrait", "face and shoulders, front three-quarter",
        "one slow look back up the valley; then forward",
        ["a glance back up-ridge", "a breath; he turns forward"],
        "standing still, facing camera", "facing down-valley",
        ["no face identity drift", "same hair and headband",
         "morning light consistent"]),
    "SEQ5_C4": spec("SEQ4_C4" if False else "SEQ5_C4", C,
        "Wide button: the figure becomes small between the meadow and the treeline.",
        "cutaway", "WS", "wide", "small figure walking toward the treeline",
        "steady steps toward the trees", ["figure shrinks toward the treeline",
        "grass sways in a light breeze"], "figure mid-meadow",
        "figure near the treeline edge",
        ["treeline geography stable", "no new elements",
         "morning light consistent"]),
    "SEQ5_D1": spec("SEQ5_D1", D,
        "New space: a quiet stream bank under dappled light.", "establishing",
        "WS", "wide", "figure arriving at the stream bank",
        "figure stops at the water's edge",
        ["water glints past the bank", "figure stands still at the edge"],
        "figure enters frame-right", "standing at the water's edge",
        ["stream bank geography stable", "wardrobe unchanged",
         "late-morning light consistent"], env=ENV_D),
    "SEQ5_D2": spec("SEQ5_D2", D,
        "He kneels to drink; the sword lies across his knees.", "action",
        "MS", "normal", "figure kneeling at the water",
        "kneels; scoops water; drinks once",
        ["kneels onto one knee", "one slow drink"],
        "standing at the edge", "kneeling, drinking",
        ["same robes", "stream flow direction stable",
         "late-morning light consistent"], env=ENV_D),
    "SEQ5_D3": spec("SEQ5_D3", D,
        "Detail: the sword planted upright in the bank earth beside him.",
        "insert", "ECU", "telephoto", "sword hilt and planted blade only",
        "the planted blade stands still; a droplet slides down",
        ["blade stands planted", "one droplet slides down the steel"],
        "blade planted upright", "blade still planted",
        ["hilt wrap and blade consistent", "no hands in frame",
         "late-morning light consistent"], env=ENV_D),
    "SEQ5_D4": spec("SEQ5_D4", D,
        "Resolution: he rises, takes up the sword, and walks on along the stream.",
        "hero", "WS", "wide", "full figure rising and walking frame-left",
        "rises; takes the sword; strides on",
        ["rises in one motion", "walks on along the bank"],
        "kneeling by the stream", "walking away frame-left along the bank",
        ["same robes and sword", "stream bank stable",
         "late-morning light consistent"], env=ENV_D),
}

REF = "7b725f7b-4da5-4455-a6f2-135c4ba22397"
plan = {"sequence_id": "SEQ005_VALLEY_STREAM", "scenes": [
    {"scene_id": C,
     "narrative_purpose":
         "Scene C - arrival: the swordsman reaches the valley floor.",
     "shots": [{"shot_id": sid, "fixture": f"fixtures/sequence005/{sid}.json",
                "continuity": {"kind": "reference", "media_id": REF}}
               for sid in ("SEQ5_C1", "SEQ5_C2", "SEQ5_C3", "SEQ5_C4")]},
    {"scene_id": D,
     "narrative_purpose":
         "Scene D - rest and onward: a stream bank pause, then the road again.",
     "shots": [{"shot_id": sid, "fixture": f"fixtures/sequence005/{sid}.json",
                "continuity": {"kind": "reference", "media_id": REF}}
               for sid in ("SEQ5_D1", "SEQ5_D2", "SEQ5_D3", "SEQ5_D4")]}]}
plan["frozen_note"] = (
    "Frozen before the first live mutation: 2 scenes, 8 shot slots, "
    "same-reference continuity; CONTINUITY_UPLOADS budget unused (mechanism "
    "PROVEN in Scene-003; no new upload required). Prompt wording avoids "
    "concrete-noun metaphors (Scene-004 funnel lesson).")

out = Path("fixtures/sequence005")
out.mkdir(parents=True, exist_ok=True)
for name, s in S.items():
    (out / f"{name}.json").write_text(
        json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(out / "sequence_plan_005.json").write_text(
    json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("froze", len(S), "specs + sequence plan 005")
