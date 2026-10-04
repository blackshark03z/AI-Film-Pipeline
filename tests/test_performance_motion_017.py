"""Performance/motion control layer tests (Package-017 Phases 2-6)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import (References, ShotSpec, load_shot,
                                validate_contract)
from film_pipeline.motion_qc import (MOTION_DIMENSIONS,
                                     MotionReviewPacket,
                                     build_motion_packet,
                                     record_motion_observations)
from film_pipeline.performance import (BodyProportionAuthority,
                                       PerformanceBeat, PerformanceSpec,
                                       classify_action_complexity)
from film_pipeline.performance_compiler import compile_performance_r2v_prompt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_scene_scale_003 import flow_capabilities  # noqa: E402

F2C_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2C_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"


def body_authority(**overrides) -> BodyProportionAuthority:
    fields = dict(
        character_id="swordsman_white_robes",
        identity_version="swordsman_white_robes_v1",
        authority_basis="no full-body reference exists; chest-up portrait "
                        "only; Owner directional constraint recorded",
        avoid_short_compact_silhouette=True)
    fields.update(overrides)
    return BodyProportionAuthority(**fields)


def perf_spec(**overrides) -> PerformanceSpec:
    fields = dict(
        primary_action="drives a step through a hard gust",
        locomotion="one decisive driving step",
        weight_transfer="weight rolls over the planted front foot",
        foot_plant="front foot plants visibly before the mass passes",
        motion_energy="moderate")
    fields.update(overrides)
    return PerformanceSpec(**fields)


MINI_SHOT = {
    "schema_version": "1.0.0", "spec_version": 1,
    "shot_id": "SEQ7_F2C_P017_TEST", "scene_id": "SCENE_F_STORM_GATE",
    "dramatic_purpose": "inside the gate the wind funnels hard",
    "duration_target_s": 8, "shot_type": "action",
    "characters": [{"character_id": "swordsman_white_robes",
                    "identity_version": "swordsman_white_robes_v1",
                    "look_state_id": "white_robes_cloud_summit_dawn_v1",
                    "behavior_state": "shoulder lowered into the wind"}],
    "camera": {"framing": "MS", "height": "eye_level",
               "lens_intent": "normal", "movement": {"type": "locked"}},
    "environment": {"time_of_day": "midday", "weather": "storm front",
                    "atmosphere": "narrow rock gate"},
    "blocking": {"start": "gate mouth", "action_beats": [
                    "a hard gust hits", "he drives a step through it"],
                 "end": "through the worst gust", "prop_interactions": []},
    "performance": {"observable_beats": [], "forbidden": []},
    "lighting": {},
    "continuity": {"screen_direction": "faces frame-left",
                   "eyeline": "down the road ahead", "start_state": {},
                   "end_state": {},
                   "critical_invariants": ["wardrobe unchanged"]},
}


def make_plan(spec: PerformanceSpec | None = None):
    payload = json.loads(json.dumps(MINI_SHOT))
    if spec is not None:
        payload["performance_spec"] = json.loads(spec.model_dump_json())
    validate_contract("shot_spec", payload)
    shot = ShotSpec.model_validate(payload)
    shot = shot.model_copy(
        update={"references": References(other_asset_ids=[F2C_REF])})
    caps = flow_capabilities()
    plan = compile_prompt(shot, caps, reference_hashes={
        F2C_REF: F2C_REF_SHA})
    return plan, shot


def test_01_performance_spec_minimal_and_beats():
    quiet = PerformanceSpec(primary_action="one long exhale")
    assert quiet.filled_biomechanics() == {}
    full = perf_spec(beats=[PerformanceBeat(label="anticipation",
                                            description="shoulder loads")])
    assert full.digest() == full.digest()
    assert list(full.filled_biomechanics())[:2] == ["locomotion",
                                                   "weight_transfer"]


def test_02_body_authority_refuses_fake_precision():
    authority = body_authority()
    assert authority.body_proportion_exact_authority == "UNKNOWN"
    assert authority.directional_constraints() != []
    with pytest.raises(ValueError, match="without exact authority"):
        body_authority(stature="180cm")
    with pytest.raises(ValueError, match="without exact authority"):
        body_authority(body_build="slender but athletic")


def test_03_action_complexity_classifier():
    low = classify_action_complexity(
        perf_spec(primary_action="one long exhale", locomotion="",
                  weight_transfer="", foot_plant="", motion_energy="low"))
    assert low["motion_risk_class"] == "LOW"
    assert low["recommendation"].startswith("NONE")
    extreme = classify_action_complexity(
        perf_spec(primary_action="draw weapon and run and strike",
                  action_intent="draw weapon while running",
                  contact_event="blade meets the gust-bent branch",
                  reaction="body recoils from the parry",
                  motion_energy="high", hip_torso_rotation="full twist"),
        camera_locked=False)
    assert extreme["motion_risk_class"] in ("HIGH", "EXTREME")
    assert extreme["recommendation"].startswith("SPLIT_SHOT")


def test_04_legacy_shot_spec_unchanged_and_new_field_parses():
    legacy = load_shot(ROOT / "fixtures/requal009/SEQ7_F2C.json")
    assert legacy.performance_spec is None
    payload = json.loads((ROOT / "fixtures/requal009/SEQ7_F2C.json")
                         .read_text(encoding="utf-8"))
    payload["performance_spec"] = {
        "schema_version": "performance-spec-v1",
        "primary_action": "drives a step",
        "beats": [{"label": "plant", "description": "foot plants",
                   "approx_start_s": 2.0}]}
    validate_contract("shot_spec", payload)
    parsed = ShotSpec.model_validate(payload)
    assert parsed.performance_spec.primary_action == "drives a step"


def test_05_compiler_block_only_when_present():
    plan_legacy, _ = make_plan(None)
    assert "performance_spec" not in plan_legacy.canonical_blocks[
        "ACTION / PERFORMANCE"]
    plan_new, _ = make_plan(perf_spec())
    block = plan_new.canonical_blocks["ACTION / PERFORMANCE"]
    assert block["performance_spec"]["primary_action"] == \
        "drives a step through a hard gust"
    from film_pipeline.flow_r2v_runtime import compact_r2v_prompt
    prompt = compact_r2v_prompt(
        plan_legacy, "job_" + "0" * 64, model="veo_3_1_r2v_lite").text
    assert "Movement" not in prompt and prompt.count("[FILM-") == 1


def test_06_performance_compiler_renders_body_and_movement():
    plan, _ = make_plan(perf_spec())
    prompt = compile_performance_r2v_prompt(
        plan, "job_" + "1" * 64, model="veo_3_1_r2v_lite",
        performance_spec=perf_spec(), body_authority=body_authority())
    text = prompt.text
    assert "tall, long-legged, non-compact silhouette" in text
    assert text.startswith("Movement") is False
    assert "Movement:" in text
    body = text.rsplit(" [FILM-", 1)[0]
    assert len(body) <= 500 and len(text.split()) <= 76
    assert prompt.version == "flow-r2v-performance-compact-v1"
    assert text.count("[FILM-") == 1


def test_07_performance_compiler_overlength_fails_closed():
    # the movement clause is phrase-capped, so overlength must come from
    # the creative prose itself (same fail-closed rule as the compact
    # composer)
    long_shot = json.loads(json.dumps(MINI_SHOT))
    long_shot["dramatic_purpose"] = ("inside the gate the wind funnels "
                                     "hard and the whole ridge seems to "
                                     "lean into the storm as one mass")
    long_shot["blocking"]["action_beats"] = [
        "a hard gust hits and the grass flattens in long waves",
        "he drives a step through it while the gate walls stream",
        "his robes crack against him in long heavy folds"]
    long_shot["performance"]["observable_beats"] = [
        "effort shows in posture while the shoulders lower"]
    validate_contract("shot_spec", long_shot)
    shot = ShotSpec.model_validate(long_shot).model_copy(
        update={"references": References(other_asset_ids=[F2C_REF])})
    plan = compile_prompt(shot, flow_capabilities(), reference_hashes={
        F2C_REF: F2C_REF_SHA})
    with pytest.raises(Exception, match="PROMPT_LIMIT"):
        compile_performance_r2v_prompt(
            plan, "job_" + "2" * 64, model="veo_3_1_r2v_lite",
            performance_spec=perf_spec(primary_action="x"),
            body_authority=body_authority())


def test_08_movement_clause_bounded_no_stuffing():
    spec = perf_spec(
        anticipation="coils against the wind",
        locomotion="one driving step",
        weight_transfer="rolls over the planted foot",
        foot_plant="plants before mass passes",
        hip_torso_rotation="counter-rotation through the gust",
        arm_countermotion="arms counter-swing",
        contact_event="robes crack")
    plan, _ = make_plan(spec)
    prompt = compile_performance_r2v_prompt(
        plan, "job_" + "3" * 64, model="veo_3_1_r2v_lite",
        performance_spec=spec, body_authority=body_authority())
    movement = [part for part in prompt.text.split(". ")
                if part.startswith("Movement:")][0]
    assert movement.count(";") <= 4  # MAX_MOVEMENT_PHRASES = 5
    assert "contact event" not in movement  # capped out


def make_video(tmp_path: Path) -> Path:
    video = tmp_path / "motion_src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=duration=4:size=320x240:rate=24",
         "-pix_fmt", "yuv420p", str(video)], check=True)
    return video


def test_09_motion_packet_built_and_sealed(tmp_path):
    video = make_video(tmp_path)
    packet = build_motion_packet(
        packet_id="MOT-Q017-TEST", subject_label="unit test motion",
        video_path=video, out_base=tmp_path, trim_start_s=0.5,
        trim_end_s=3.0, fps=10, created_at="2026-10-04T00:00:00+00:00")
    assert packet.sampling_fps == 10
    assert 8 <= len(packet.frame_files) <= 40
    assert packet.digest() == packet.digest()
    assert (tmp_path / "MOT-Q017-TEST" / "packet.json").is_file()
    record = record_motion_observations(
        packet, reviewer_identity="build_worker_glmanalyst",
        reviewed_at="2026-10-04T00:00:01+00:00",
        observations={dim: ("INCONCLUSIVE", "synthetic source")
                      for dim in MOTION_DIMENSIONS})
    assert "advisory" in record["authority"]
    assert record["packet_digest"] == packet.digest()


def test_10_motion_observations_fail_closed(tmp_path):
    video = make_video(tmp_path)
    packet = build_motion_packet(
        packet_id="MOT-Q017-TEST2", subject_label="unit test motion",
        video_path=video, out_base=tmp_path, trim_start_s=0.0,
        trim_end_s=2.0, fps=8, created_at="2026-10-04T00:00:00+00:00")
    good = {dim: ("PASS", "") for dim in MOTION_DIMENSIONS}
    with pytest.raises(ValueError, match="missing motion dimensions"):
        record_motion_observations(packet, reviewer_identity="w",
                                   reviewed_at="t",
                                   observations=dict(list(good.items())[:-1]))
    bad = dict(good)
    bad["GAIT_NATURALNESS"] = ("MAYBE", "")
    with pytest.raises(ValueError, match="unqualified motion verdict"):
        record_motion_observations(packet, reviewer_identity="w",
                                   reviewed_at="t", observations=bad)
    dup = dict(good)
    dup["EXTRA_DIM"] = ("PASS", "")
    with pytest.raises(ValueError, match="unknown motion dimension"):
        record_motion_observations(packet, reviewer_identity="w",
                                   reviewed_at="t", observations=dup)


def test_11_motion_packet_trims_enforced(tmp_path):
    video = make_video(tmp_path)
    with pytest.raises(ValueError, match="trim end"):
        build_motion_packet(
            packet_id="MOT-Q017-BAD", subject_label="x",
            video_path=video, out_base=tmp_path, trim_start_s=2.0,
            trim_end_s=2.0, fps=10, created_at="t")
    packet = build_motion_packet(
        packet_id="MOT-Q017-DIM", subject_label="x", video_path=video,
        out_base=tmp_path, trim_start_s=0.0, trim_end_s=1.5, fps=8,
        created_at="t")
    assert sorted(packet.dimensions) == sorted(MOTION_DIMENSIONS)
