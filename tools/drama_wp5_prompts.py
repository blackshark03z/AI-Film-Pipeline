"""WP5 conditioning A/B on film01 SC03_g2: build and preflight the prompts.

Arms (one 8 s Flow generation each, Omni 1.1 Flash 720p):
  A0 text-only control  - the accepted take SC03_g2.mp4 (no new spend)
  V1 + SC03_g1 video    - the previous generation as an ingredient
  I1 + SC03_g1 end frame
  P1 + empty-set plate  - location image without people
  F1 start frame        - Flow image (plate + look text) in "Khung hình" mode
  R1 rich text-only     - WP2 location look + WP3 choreography, ~150 words
Writes docs/drama/wp5/prompts/*.txt and docs/drama/wp5/prompts.json.
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from film_pipeline.drama import CharacterBrief, compile_scene_prompt  # noqa: E402
from film_pipeline.drama.choreography import (  # noqa: E402
    GenerationChoreography, PerformanceCue, Phase)
from film_pipeline.drama.preflight import PreflightLimits, preflight_scene  # noqa: E402
from film_pipeline.drama.scene_bible import LocationLook  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "sc03", Path("tools/drama_flow_ui/sc03_v2.py"))
sc03 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc03)

OUT = Path("docs/drama/wp5/prompts")
BASE = Path("docs/drama/film01_prompts/noref/SC03_g2.txt").read_text(
    encoding="utf-8").strip()

LOBBY = LocationLook(
    look_id="station_lobby_v1", location="police station lobby",
    text="Police station lobby: long wooden counter, blue-grey walls, red "
         "EXIT sign over the back door, framed portraits and a wall clock "
         "behind, grey morning light",
    invariants=["red EXIT sign above the back door", "wooden front counter",
                "framed portraits on the back wall", "round wall clock"],
    interior=True, time_of_day="morning", approved=True)

CHOREO = GenerationChoreography(
    generation_id="SC03_g2",
    phases=[Phase(kind="ACTION", start_s=0, end_s=3.5,
                  description="NORA gathers the pieces from the counter"),
            Phase(kind="ACTION", start_s=3.5, end_s=6,
                  description="she pockets them in her jacket"),
            Phase(kind="HOLD", start_s=6, end_s=8,
                  description="she looks at DOYLE, still")],
    once_actions=["gathers the pieces", "pockets them"],
    gesture_budget=1,
    performance=[PerformanceCue(
        character="NORA", emotion_intent="quiet resolve",
        visible_cues=["steady gaze", "slight chin lift"],
        intensity="restrained", prohibited_misread="smile or tears")])

# WP5 measures adherence at the rich prompt's natural length (Dola-era 120
# is an assumption); the arm records its word count
WORDS = 170

PREFIX = {
    "V1": "Continue from the attached video: same room, same two people, "
          "same camera side, same light.",
    "I1": "The attached image is the last frame of the previous shot: keep "
          "the room, the counter and both people exactly as shown.",
    "P1": "The attached image shows the empty set: keep this room, the "
          "counter, the EXIT sign and the wall portraits exactly.",
    "F1": "The video starts on the given start frame: keep this room, both "
          "people and their positions exactly.",
}


def rich():
    sub = sc03.sub_unit(2)
    start = sc03.STATE["g1_end"]
    start = start.model_copy(update={"location": LOBBY.look_id})
    plan = compile_scene_prompt(
        sub, characters=[CharacterBrief(name=c, look=sc03.LOOKS[c],
                                        voice=sc03.VOICE[c])
                         for c in ("NORA", "DOYLE")],
        setting="", room_tone="quiet lobby hum", dialogue_language="English",
        start_state=start, location=LOBBY, choreography=CHOREO)
    report = preflight_scene(
        scene=sc03.scene, unit=sub, prompt=plan, reference_sets=[],
        reference_root=Path("docs/drama/refs"), storyboard=sc03.gate,
        known_characters=sc03.sb.script.characters,
        limits=PreflightLimits(max_prompt_words=WORDS,
                               timing=sc03.limits.timing,
                               feasibility=sc03.limits.feasibility),
        reference_mode="TEXT_ONLY", looks=list(sc03.LOOKS.values()),
        generation_index=2, location=LOBBY, choreography=CHOREO,
        handoff=sc03.GenerationHandoff(
            previous_generation_id="SC03_g1", previous_action=sc03.ACTION[1],
            previous_start=sc03.STATE["g1_start"].model_copy(
                update={"location": LOBBY.look_id}),
            previous_end=start, end_state_verified=True),
        start_state=start)
    return plan, report


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    record = {"base_prompt": "docs/drama/film01_prompts/noref/SC03_g2.txt",
              "location": LOBBY.model_dump(), "arms": {}}
    for arm, prefix in PREFIX.items():
        text = f"{prefix} {BASE}"
        (OUT / f"{arm}.txt").write_text(text + "\n", encoding="utf-8")
        record["arms"][arm] = {"words": len(text.split())}
    plan, report = rich()
    (OUT / "R1.txt").write_text(plan.compiled_text + "\n", encoding="utf-8")
    record["arms"]["R1"] = {
        "words": plan.word_count, "verdict": report.verdict,
        "issues": [i.model_dump() for i in report.issues]}
    Path("docs/drama/wp5/prompts.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    for arm, info in record["arms"].items():
        print(arm, info)
