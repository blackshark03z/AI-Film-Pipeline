"""SC03 v2 through the continuity pipeline: locked looks, generation
states, TEXT_ONLY preflight. Writes docs/drama/film01_prompts/v2/."""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from film_pipeline.drama import (CharacterBrief, CharacterLook,  # noqa: E402
                                 ContinuityState, GenerationHandoff,
                                 StoryboardGate, compile_scene_prompt,
                                 preflight_scene)
from film_pipeline.drama.coverage import SceneTiming  # noqa: E402
from film_pipeline.drama.feasibility import FeasibilityLimits  # noqa: E402
from film_pipeline.drama.preflight import PreflightLimits  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "sb", Path(__file__).with_name("sb_first_day.py"))
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)

OUT = Path("docs/drama/film01_prompts/v2")
LOOKS = {
    "NORA": CharacterLook(
        look_id="nora_navy_blazer_text", character="NORA",
        text="Black woman, mid-fifties, short grey-streaked hair, navy "
             "blazer, white top",
        invariants=["short grey-streaked hair, not curled, not "
                    "shoulder-length", "navy blazer", "white top"],
        approved=True),
    "DOYLE": CharacterLook(
        look_id="doyle_patrol_text", character="DOYLE",
        text="white police sergeant, mid-forties, heavy-set, sandy hair, "
             "ruddy face, navy patrol uniform",
        invariants=["heavy-set", "sandy hair", "ruddy clean-shaven face",
                    "navy patrol uniform"],
        approved=True),
}
VOICE = {"NORA": "calm female voice", "DOYLE": "loud mocking voice"}
SETTING = "Police station lobby, grey morning light, wooden front counter"
ACTION = {
    1: "NORA sets a folded letter on the counter; DOYLE tears it in half "
       "twice and lays the four pieces flat on the counter in front of her",
    2: "NORA gathers the four paper pieces from the counter, pockets them "
       "and looks at him patiently",
}
SFX = {1: ["paper tearing"]}
POS = {"NORA": "standing at the counter, frame-left",
       "DOYLE": "behind the counter, frame-right"}
LOOKIDS = {k: v.look_id for k, v in LOOKS.items()}
STATE = {
    "g1_start": ContinuityState(positions=POS, looks=LOOKIDS, props={
        "the letter:": "folded, in NORA's hand"}),
    "g1_end": ContinuityState(positions=POS, looks=LOOKIDS, props={
        "the letter:": "torn into four pieces, lying on the counter in "
                       "front of NORA"}),
    "g2_end": ContinuityState(positions=POS, looks=LOOKIDS, props={
        "the letter:": "folded pieces, in NORA's jacket pocket"}),
}

scene = next(s for s in sb.script.scenes if s.scene_id == "SC03")
unit = sb.plan_unit(scene)
gate = StoryboardGate(Path("docs/drama/storyboard_film01"))
limits = PreflightLimits(
    timing=SceneTiming(duration_s=8.0, max_shots=4, min_shot_s=2.0,
                       syllables_per_second=2.5),
    feasibility=FeasibilityLimits(scene_duration_s=16.0,
                                  max_dialogue_syllables=28,
                                  syllables_per_second=2.5))


def sub_unit(gen):
    lo = (gen - 1) * 8.0
    shots = [s.model_copy(update={"start_s": round(s.start_s - lo, 3),
                                  "end_s": round(s.end_s - lo, 3)})
             for s in unit.shots if lo <= s.start_s < lo + 8.0]
    return unit.model_copy(update={"shots": shots, "duration_s": 8.0})


def build(gen, verified=False):
    sub = sub_unit(gen)
    start = STATE["g1_start"] if gen == 1 else STATE["g1_end"]
    stated = set(start.positions) if gen == 2 else set()
    cast = [c for c in LOOKS
            if c in stated or any(c in s.axis.visible for s in sub.shots)]
    plan = compile_scene_prompt(
        sub, characters=[CharacterBrief(name=c, look=LOOKS[c],
                                        voice=VOICE[c]) for c in cast],
        setting=f"{SETTING}. {ACTION[gen]}", room_tone="quiet lobby hum",
        sfx=SFX.get(gen), dialogue_language="English",
        start_state=start if gen == 2 else None)
    handoff = None
    if gen == 2:
        handoff = GenerationHandoff(
            previous_generation_id="SC03_g1", previous_action=ACTION[1],
            previous_start=STATE["g1_start"], previous_end=STATE["g1_end"],
            end_state_verified=verified)
    report = preflight_scene(
        scene=scene, unit=sub, prompt=plan, reference_sets=[],
        reference_root=Path("docs/drama/refs"), storyboard=gate,
        known_characters=sb.script.characters, limits=limits,
        reference_mode="TEXT_ONLY", looks=list(LOOKS.values()),
        generation_index=gen, handoff=handoff,
        start_state=start if gen == 2 else None)
    return plan, report


if __name__ == "__main__":
    verified = "--g1-verified" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    record = {}
    for gen in (1, 2):
        plan, report = build(gen, verified)
        gid = f"SC03_g{gen}"
        (OUT / f"{gid}.txt").write_text(plan.compiled_text + "\n",
                                        encoding="utf-8")
        record[gid] = {"words": plan.word_count, "verdict": report.verdict,
                       "issues": [i.model_dump() for i in report.issues]}
        print(gid, report.verdict, plan.word_count, "words",
              [f"{i.check}: {i.detail[:90]}" for i in report.issues])
    record["states"] = {k: v.model_dump() for k, v in STATE.items()}
    record["looks"] = {k: v.model_dump() for k, v in LOOKS.items()}
    Path("docs/drama/gate3_film01_sc03_v2.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
