"""QUALITY-V2-003 director-layer tests: authority layering, contracts,
gates B1-B10, semantic identity, compiler boundary, previz renderer,
and the Director-model availability custody."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import film_pipeline.director_blocking as db
from film_pipeline.director_blocking import (
    AUTHORITY_LAYERING, AUTHORITY_LAYER_MEANINGS, BlockingSpec,
    CameraCoveragePlan, DirectorIntent, SpatialStateChange, TravelPath,
    Waypoint, assert_compile_authorities_present,
    assert_compiler_respected_authority, director_semantic_identity,
    make_blocking_spec, make_camera_coverage_plan, make_director_intent,
    require_director_gates, validate_director_gates)

PKG = ROOT / "projects/quality_v2_003_director_blocking"

A_SRC = {"dramatic_purpose": "SEQ7_F2.json",
         "viewer_must_understand": "owner_approved_f2_intent_v2_002.json",
         "primary_action_objective": "owner_approved_f2_intent_v2_002.json",
         "required_visual_change": "owner_approved_f2_intent_v2_002.json",
         "required_end_read": "owner_approved_f2_intent_v2_002.json",
         "forbidden_interpretations": "owner_approved_f2_intent_v2_002.json"}
B_SRC = {"zones": "V2-003 package Owner truth",
         "travel_path": "V2-003 package Owner truth",
         "crossing": "V2-003 package Owner truth",
         "interactions": "V2-003 package Owner truth",
         "continuity": "SEQ7 plan"}
C_SRC = {"camera_position_intent": "coverage rule",
         "subject_regions": "blocking zones"}


def make_intent(**kw):
    base = dict(shot_id="SEQ7_F2C",
                dramatic_purpose="pass the gate against the gust",
                viewer_must_understand=["he crosses the gate"],
                primary_action_objective="PASS THROUGH THE GATE AGAINST "
                                         "THE GUST",
                required_visual_change="BEFORE_GATE -> BEYOND_GATE",
                required_end_read="he is on the far side",
                forbidden_interpretations=["the rock is his destination"],
                authority_sources=dict(A_SRC),
                director_model_receipt={"model": "gpt-6-sol",
                                        "thinking_effort": "HIGH"},
                created_at="2026-10-04T00:00:00Z")
    base.update(kw)
    return make_director_intent(**base)


def make_blocking(**kw):
    base = dict(shot_id="SEQ7_F2C",
                start_zone="BEFORE_GATE", target_zone="BEYOND_GATE",
                end_zone="BEYOND_GATE:FAR_SIDE_CLEAR",
                screen_direction="faces frame-left",
                travel_path=TravelPath(
                    path_type="DIRECT_TRAVERSAL",
                    ordered_waypoints=[
                        Waypoint(zone="BEFORE_GATE"),
                        Waypoint(zone="CENTER_GATE_OPENING",
                                 is_crossing=True,
                                 note="CENTER_GATE_OPENING"),
                        Waypoint(zone="BEYOND_GATE:FAR_SIDE_CLEAR")],
                    required_crossing="CENTER_GATE_OPENING"),
                start_body_orientation="facing the gate, leaning into "
                                       "the gust",
                end_body_orientation="facing onward, settled",
                required_spatial_state_change=SpatialStateChange(
                    from_zone="BEFORE_GATE", to_zone="BEYOND_GATE"),
                forbidden_interactions=["ROCK_CONTACT", "ROCK_BRACE",
                                        "ROCK_CIRCLE", "ROCK_SHELTER"],
                forbidden_zones=["AT_ROCK"],
                forbidden_reversal=True, must_exit_start_zone=True,
                must_reach_target_zone=True,
                visibility_requirements=[
                    "both sides of the threshold distinguishable"],
                continuity_bindings={"previous_shot_id": "SEQ7_F1",
                                     "next_shot_id": "SEQ7_F3"},
                authority_sources=dict(B_SRC),
                created_at="2026-10-04T00:00:00Z")
    base.update(kw)
    return make_blocking_spec(**base)


def make_camera(**kw):
    base = dict(shot_id="SEQ7_F2C",
                camera_position_intent="static full-shot beside the gate, "
                                       "profile to the path",
                framing="WS", axis="perpendicular to the travel path",
                screen_direction="faces frame-left",
                subject_start_region="BEFORE_GATE",
                subject_end_region="BEYOND_GATE:FAR_SIDE_CLEAR",
                required_action_visibility=True,
                required_crossing_visibility=True,
                occlusion_constraints=[], camera_motion="locked",
                forbidden_camera_behavior=["orbit", "camera reversal",
                                           "axis cross"],
                authority_sources=dict(C_SRC),
                created_at="2026-10-04T00:00:00Z")
    base.update(kw)
    return make_camera_coverage_plan(**base)


# --- authority layering (P2) --------------------------------------------

def test_01_authority_layering_frozen():
    assert AUTHORITY_LAYERING == (
        "NarrativeBeat", "ActionIntent", "DirectorIntent", "BlockingSpec",
        "PerformanceSpec", "CameraCoveragePlan", "ShotSpec",
        "PromptCompiler", "Provider")
    assert AUTHORITY_LAYER_MEANINGS["PromptCompiler"] == \
        "deterministic translation only"
    assert AUTHORITY_LAYER_MEANINGS["Provider"] == "never authority"
    assert AUTHORITY_LAYERING.index("DirectorIntent") < \
        AUTHORITY_LAYERING.index("BlockingSpec") < \
        AUTHORITY_LAYERING.index("CameraCoveragePlan")


def test_02_reuse_analysis_recorded():
    """core.Blocking (start/beats/end prose) and core.Camera exist; the
    delta is the structured spatial/coverage semantics."""
    from film_pipeline.core import Blocking as LegacyBlocking
    fields = set(LegacyBlocking.model_fields)
    assert {"start", "action_beats", "end"} <= fields
    assert not {"start_zone", "target_zone", "travel_path"} & fields


# --- contracts (P3-P5) ----------------------------------------------------

def test_03_intent_identity_and_authority_completeness():
    intent = make_intent()
    assert intent.director_intent_id.startswith("DI-")
    with pytest.raises(ValueError, match="authority sources"):
        make_intent(authority_sources={k: v for k, v in A_SRC.items()
                                       if k != "required_end_read"})
    with pytest.raises(ValueError, match="identity mismatch"):
        DirectorIntent.model_validate(
            {**intent.model_dump(mode="json"),
             "director_intent_id": "DI-" + "0" * 16})


def test_04_blocking_identity_and_neutrality():
    blocking = make_blocking()
    assert blocking.blocking_spec_id.startswith("BS-")
    dump = json.dumps(blocking.model_dump(mode="json")).lower()
    assert "provider" not in dump  # provider-neutral by construction
    with pytest.raises(ValueError, match="identity mismatch"):
        BlockingSpec.model_validate(
            {**blocking.model_dump(mode="json"),
             "blocking_spec_id": "BS-" + "0" * 16})


def test_05_camera_identity_and_binding():
    camera = make_camera()
    assert camera.camera_plan_id.startswith("CC-")
    with pytest.raises(ValueError, match="authority sources"):
        make_camera(authority_sources={"camera_position_intent": "x"})


# --- gates B1-B10 (P6) -----------------------------------------------------

def test_06_valid_f2_shape_plan_passes_all_ten():
    result = require_director_gates(
        make_intent(), make_blocking(), make_camera(),
        previous_screen_direction="faces frame-left",
        next_screen_direction="faces frame-left")
    assert result["all_pass"] and result["blocked_by"] == []
    assert set(result["gates"]) == {
        "B1_START_END_DISTINCT", "B2_TARGET_REACHED", "B3_PATH_HAS_PROGRESS",
        "B4_NO_FORBIDDEN_INTERACTION", "B5_NO_CIRCLING", "B6_NO_REVERSAL",
        "B7_CROSSING_OBSERVABLE", "B8_END_STATE_OBSERVABLE",
        "B9_CONTINUITY_COMPATIBLE", "B10_AUTHORITY_COMPLETE"}


def test_07_b1_same_start_end_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(start_zone="AT_ROCK",
                                     end_zone="AT_ROCK"), make_camera())
    assert "B1_START_END_DISTINCT" in out["blocked_by"]


def test_08_b2_target_never_reached_refused():
    out = validate_director_gates(
        make_intent(),
        make_blocking(required_spatial_state_change=SpatialStateChange(
            from_zone="BEFORE_GATE", to_zone="AT_ROCK")),
        make_camera())
    assert "B2_TARGET_REACHED" in out["blocked_by"]


def test_09_b3_path_without_progress_refused():
    out = validate_director_gates(
        make_intent(),
        make_blocking(travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE"),
                Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True),
                Waypoint(zone="AT_ROCK")],
            required_crossing="CENTER_GATE_OPENING")),
        make_camera())
    assert "B3_PATH_HAS_PROGRESS" in out["blocked_by"]


def test_10_b4_forbidden_interaction_in_plan_refused():
    out = validate_director_gates(
        make_intent(),
        make_blocking(allowed_interactions=["ROCK_BRACE"]), make_camera())
    assert "B4_NO_FORBIDDEN_INTERACTION" in out["blocked_by"]
    out = validate_director_gates(
        make_intent(),
        make_blocking(travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE"),
                Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True,
                         note="brief ROCK_BRACE at the stone"),
                Waypoint(zone="BEYOND_GATE")],
            required_crossing="CENTER_GATE_OPENING")),
        make_camera())
    assert "B4_NO_FORBIDDEN_INTERACTION" in out["blocked_by"]


def test_11_b5_circling_refused_unless_authorized():
    looping = TravelPath(
        path_type="DIRECT_TRAVERSAL",
        ordered_waypoints=[
            Waypoint(zone="BEFORE_GATE"),
            Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True),
            Waypoint(zone="BEYOND_GATE"),
            Waypoint(zone="BEFORE_GATE:EDGE"),
            Waypoint(zone="BEYOND_GATE")],
        required_crossing="CENTER_GATE_OPENING")
    out = validate_director_gates(make_intent(),
                                  make_blocking(travel_path=looping),
                                  make_camera())
    assert "B5_NO_CIRCLING" in out["blocked_by"]
    src = dict(B_SRC)
    src["path_loop_authorization"] = "narrative authority (SEQ7 plan)"
    ok = make_blocking(
        travel_path=looping.model_copy(
            update={"path_type": "AUTHORIZED_LOOP"}),
        authority_sources=src)
    out = validate_director_gates(make_intent(), ok, make_camera())
    assert "B5_NO_CIRCLING" not in out["blocked_by"]


def test_12_b6_reversal_refused():
    out = validate_director_gates(
        make_intent(),
        make_blocking(travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE"),
                Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True),
                Waypoint(zone="BEYOND_GATE"),
                Waypoint(zone="BEFORE_GATE:EDGE")],
            required_crossing="CENTER_GATE_OPENING")),
        make_camera())
    assert "B6_NO_REVERSAL" in out["blocked_by"]


def test_13_b7_crossing_hidden_or_occluded_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(required_crossing_visibility=False))
    assert "B7_CROSSING_OBSERVABLE" in out["blocked_by"]
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(occlusion_constraints=[
            "CENTER_GATE_OPENING hidden behind the slab"]))
    assert "B7_CROSSING_OBSERVABLE" in out["blocked_by"]
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(camera_motion="slow orbit",
                    forbidden_camera_behavior=["orbit"]))
    assert "B7_CROSSING_OBSERVABLE" in out["blocked_by"]


def test_14_b8_geography_collapse_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(subject_start_region="BEFORE_GATE",
                    subject_end_region="BEFORE_GATE:EDGE"))
    assert "B8_END_STATE_OBSERVABLE" in out["blocked_by"]
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(subject_start_region="SOMEWHERE_ELSE"))
    assert "B8_END_STATE_OBSERVABLE" in out["blocked_by"]


def test_15_b9_continuity_conflict_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(), make_camera(),
        previous_screen_direction="faces frame-right")
    assert "B9_CONTINUITY_COMPATIBLE" in out["blocked_by"]
    src = dict(B_SRC)
    out = validate_director_gates(
        make_intent(),
        make_blocking(continuity_bindings={
            "previous_shot_id": "SEQ7_F1", "next_shot_id": "SEQ7_F3",
            "screen_direction_flip_authorized": True}),
        make_camera(), previous_screen_direction="faces frame-right")
    assert "B9_CONTINUITY_COMPATIBLE" not in out["blocked_by"]


def test_16_b10_incomplete_authority_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(), make_camera(shot_id="SEQ7_F9"))
    assert "B10_AUTHORITY_COMPLETE" in out["blocked_by"]
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        require_director_gates(make_intent(), make_blocking(),
                               make_camera(shot_id="SEQ7_F9"))


# --- semantic identity (P11) ------------------------------------------------

def test_17_identity_changes_with_blocking_and_camera():
    intent, blocking, camera = make_intent(), make_blocking(), make_camera()
    ident = director_semantic_identity("base_sha", intent, blocking, camera)
    same = director_semantic_identity("base_sha", intent, blocking, camera)
    assert ident["generation_semantic_identity"] == \
        same["generation_semantic_identity"]
    blocking2 = make_blocking(**{**blocking.model_dump(
        mode="json", exclude={"blocking_spec_id"}),
        "end_body_orientation": "turned"})
    camera2 = make_camera(**{**camera.model_dump(
        mode="json", exclude={"camera_plan_id"}), "framing": "MS"})
    assert director_semantic_identity(
        "base_sha", intent, blocking2, camera)[
        "generation_semantic_identity"] != \
        ident["generation_semantic_identity"]
    assert director_semantic_identity(
        "base_sha", intent, blocking, camera2)[
        "generation_semantic_identity"] != \
        ident["generation_semantic_identity"]
    assert ident["v1_identity_untouched"] is True


def test_18_identity_refuses_mixed_shots():
    with pytest.raises(ValueError, match="one shot"):
        director_semantic_identity("base_sha", make_intent(),
                                   make_blocking(shot_id="OTHER"),
                                   make_camera())


# --- compiler boundary (P12) --------------------------------------------------

def test_19_compile_authority_refusals():
    with pytest.raises(ValueError, match="REFUSE_COMPILE"):
        assert_compile_authorities_present(action_intent={})
    with pytest.raises(ValueError, match="REFUSE_COMPILE"):
        assert_compile_authorities_present(
            action_intent={}, director_intent=make_intent(),
            blocking_spec=make_blocking(), performance_spec={},
            camera_coverage_plan=make_camera())
    assert_compile_authorities_present(
        action_intent={"trigger": "gust"}, director_intent=make_intent(),
        blocking_spec=make_blocking(),
        performance_spec={"primary_action": "advances"},
        camera_coverage_plan=make_camera())


def test_20_compiler_respects_authority():
    blocking = make_blocking()
    assert_compiler_respected_authority(
        "he advances through the gate. End: BEYOND_GATE FAR_SIDE_CLEAR",
        blocking)
    with pytest.raises(ValueError, match="ROCK_BRACE"):
        assert_compiler_respected_authority(
            "he braces on the rock then continues. End: BEYOND_GATE",
            blocking)
    with pytest.raises(ValueError, match="end spatial read"):
        assert_compiler_respected_authority(
            "he wanders near the entrance", blocking)


# --- Director model custody (P1) ---------------------------------------------

def test_21_director_model_unavailable_recorded():
    binding = json.loads((PKG / "director_model_binding_v2_003.json")
                         .read_text(encoding="utf-8"))
    receipt = binding["availability_receipt"]
    assert receipt["requested_model"] == "gpt-6-sol"
    assert receipt["requested_thinking_effort"] == "HIGH"
    assert receipt["exact_model_available"] is False
    assert receipt["result"] == "DIRECTOR_MODEL_UNAVAILABLE"
    assert binding["director_work_state"] == "BLOCKED_ON_DIRECTOR_MODEL"
    assert binding["binding"]["substitution_policy"].startswith("No silent")


def test_22_no_f2_director_plan_authored_by_worker():
    """Without the Director model, no F2 director artifacts may exist:
    that would be a silent worker substitution of the Director role."""
    f2_plans = [p for p in PKG.glob("*F2*")
                if p.suffix in {".json", ".png", ".mp4"}]
    assert f2_plans == [], f2_plans


def test_23_v2_002_reject_all_custody():
    decision = json.loads((PKG / "v2_002_owner_decision.json").read_text(
        encoding="utf-8"))
    assert decision["V2_002_OWNER_DECISION"] == "REJECT_ALL"
    assert decision["debt_QD-001_state"].startswith("ACTIVE")
    assert len(decision["rejections"]) == 2
    for rej in decision["rejections"]:
        assert rej["state_after"] == "OWNER_REJECTED"
        assert rej["state_before"] == "QUALITY_REVIEW_READY"
    assert decision["no_promotion"] is True


def test_24_governance_module_surface_has_no_provider_or_generate():
    public = [n for n, v in vars(db).items()
              if callable(v) and not n.startswith("_")]
    assert not any("generate" in n.lower() or "provider_call" in n.lower()
                   for n in public)


# --- previz renderer (P9) on the synthetic fixture -----------------------------

def test_25_previz_renderer_proven_on_synthetic_fixture(tmp_path):
    fixture = make_blocking().model_dump(mode="json")
    fixture_path = tmp_path / "SYNTHETIC_GATE_FIXTURE_blocking.json"
    fixture_path.write_text(json.dumps(fixture, indent=1), encoding="utf-8")
    out = tmp_path / "previz"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/build_v2_003_previz.py"),
         str(fixture_path), str(out),
         "SYNTHETIC GATE FIXTURE (not the F2 plan)"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    for name in ("BLOCKING_TOPDOWN.png", "START_FRAME_SCHEMATIC.png",
                 "END_FRAME_SCHEMATIC.png"):
        produced = out / name
        assert produced.exists() and produced.stat().st_size > 1000
    assert (out / "BLOCKING_PREVIZ.mp4").exists()


def test_26_start_custody_and_layering_doc():
    custody = json.loads((PKG / "start_custody_v2_003.json").read_text(
        encoding="utf-8"))
    assert custody["v2_002_final_revision"] == \
        "b460948c9d2ba1a3e676e827c46930563c1a1180"
    assert custody["v1_frozen_baseline"] == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
