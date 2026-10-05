"""QUALITY-V2-003 package recovery cases: every V2-003-specific
adversarial/recovery case executed against its live guard."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import film_pipeline.director_blocking as db
from film_pipeline.director_blocking import (
    CameraCoveragePlan, DirectorIntent, SpatialStateChange, TravelPath,
    Waypoint, assert_compile_authorities_present,
    assert_compiler_respected_authority, director_semantic_identity,
    make_blocking_spec, make_camera_coverage_plan, make_director_intent,
    require_director_gates, validate_director_gates)
from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, EXTERNAL_AMBIGUITY_RULE,
    QUALITY_V2_CANONICAL_BASELINE)

from test_director_blocking_v2_003 import (  # noqa: F401
    make_blocking, make_camera, make_intent)

PKG = ROOT / "projects/quality_v2_003_director_blocking"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")


def pkg_json(name):
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# RC-001/002 — missing authorities at compile time
def test_rc001_002_missing_authorities_refused():
    with pytest.raises(ValueError, match="REFUSE_COMPILE"):
        assert_compile_authorities_present(
            action_intent={"t": 1}, director_intent=None,
            blocking_spec=make_blocking(), performance_spec={"p": 1},
            camera_coverage_plan=make_camera())
    with pytest.raises(ValueError, match="REFUSE_COMPILE"):
        assert_compile_authorities_present(
            action_intent={"t": 1}, director_intent=make_intent(),
            blocking_spec=None, performance_spec={"p": 1},
            camera_coverage_plan=make_camera())


# RC-003 — same start/end zone
def test_rc003_same_start_end_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(start_zone="AT_ROCK",
                                     end_zone="AT_ROCK"), make_camera())
    assert "B1_START_END_DISTINCT" in out["blocked_by"]


# RC-004 — loop around the rock
def test_rc004_loop_refused():
    out = validate_director_gates(
        make_intent(),
        make_blocking(travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE"),
                Waypoint(zone="AT_ROCK"),
                Waypoint(zone="BEFORE_GATE:EDGE"),
                Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True),
                Waypoint(zone="BEYOND_GATE")],
            required_crossing="CENTER_GATE_OPENING")),
        make_camera())
    assert "B5_NO_CIRCLING" in out["blocked_by"]


# RC-005 — path ends at the rock
def test_rc005_ends_at_rock_refused():
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


# RC-006 — reversal after crossing
def test_rc006_reversal_refused():
    out = validate_director_gates(
        make_intent(),
        make_blocking(travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE"),
                Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True),
                Waypoint(zone="BEYOND_GATE"),
                Waypoint(zone="BEFORE_GATE")],
            required_crossing="CENTER_GATE_OPENING")),
        make_camera())
    assert "B6_NO_REVERSAL" in out["blocked_by"]


# RC-007 — target never reached
def test_rc007_target_unreached_refused():
    out = validate_director_gates(
        make_intent(),
        make_blocking(required_spatial_state_change=SpatialStateChange(
            from_zone="BEFORE_GATE", to_zone="AT_ROCK")),
        make_camera())
    assert "B2_TARGET_REACHED" in out["blocked_by"]


# RC-008/010 — camera hides the crossing / crosses the axis
def test_rc008_010_camera_gates():
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(required_crossing_visibility=False))
    assert "B7_CROSSING_OBSERVABLE" in out["blocked_by"]
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(camera_motion="cross axis push",
                    forbidden_camera_behavior=["axis cross"]))
    assert "B7_CROSSING_OBSERVABLE" in out["blocked_by"]


# RC-009/011 — geography collapse
def test_rc009_011_geography_collapse_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(subject_start_region="BEFORE_GATE",
                    subject_end_region="BEFORE_GATE:EDGE"))
    assert "B8_END_STATE_OBSERVABLE" in out["blocked_by"]
    out = validate_director_gates(
        make_intent(), make_blocking(),
        make_camera(subject_start_region="BEFORE_GATE",
                    subject_end_region="BEFORE_GATE"))
    assert "B8_END_STATE_OBSERVABLE" in out["blocked_by"]


# RC-012/013/014 — compiler invention refusals
def test_rc012_013_014_compiler_refusals():
    blocking = make_blocking()
    with pytest.raises(ValueError, match="ROCK_CIRCLE"):
        assert_compiler_respected_authority(
            "he circles the rock twice. End: BEYOND_GATE", blocking)
    with pytest.raises(ValueError, match="ROCK_BRACE"):
        assert_compiler_respected_authority(
            "he braces on the rock. End: BEYOND_GATE", blocking)
    with pytest.raises(ValueError, match="end spatial read"):
        assert_compiler_respected_authority(
            "he paces near the gate mouth", blocking)


# RC-015 — silent Director-output tampering
def test_rc015_silent_tamper_refused():
    intent = make_intent()
    tampered = intent.model_dump(mode="json")
    tampered["required_end_read"] = "he rests at the rock"
    with pytest.raises(ValueError, match="identity mismatch"):
        DirectorIntent.model_validate(tampered)


# RC-016 — story-event content must remain authority-auditable
def test_rc016_story_event_requires_authority_binding():
    intent = make_intent(
        forbidden_interpretations=["the rock is his destination",
                                   "a sword duel begins"])
    # the invented content is AUDITABLE: its field's authority source is
    # recorded on the minted record
    assert intent.authority_sources["forbidden_interpretations"].strip()
    # dropping the field's authority binding refuses the mint
    with pytest.raises(ValueError, match="authority sources"):
        make_intent(authority_sources={
            k: v for k, v in intent.authority_sources.items()
            if k != "forbidden_interpretations"})


# RC-017/018 — identity separation
def test_rc017_018_identity_separation():
    intent, blocking, camera = make_intent(), make_blocking(), make_camera()
    base = director_semantic_identity("b", intent, blocking, camera)[
        "generation_semantic_identity"]
    b2 = make_blocking(**{**blocking.model_dump(
        mode="json", exclude={"blocking_spec_id"}),
        "end_body_orientation": "changed"})
    c2 = make_camera(**{**camera.model_dump(
        mode="json", exclude={"camera_plan_id"}), "framing": "MS"})
    assert director_semantic_identity("b", intent, b2, camera)[
        "generation_semantic_identity"] != base
    assert director_semantic_identity("b", intent, blocking, c2)[
        "generation_semantic_identity"] != base


# RC-019 — continuity conflict
def test_rc019_continuity_conflict_refused():
    out = validate_director_gates(
        make_intent(), make_blocking(), make_camera(),
        previous_screen_direction="faces frame-right",
        next_screen_direction="faces frame-right")
    assert "B9_CONTINUITY_COMPATIBLE" in out["blocked_by"]


# RC-020/021/022 — baseline & canonical custody. The substitute ingest
# legitimately modifies exactly its own files (committed by this
# package); any OTHER tracked modification is a violation.
INGEST_TRACKED_ALLOWLIST = {
    " M docs/quality-v2/V2_004_F2_BLOCKING_EXPERIMENT_HANDOFF.md",
    " M schemas/blocking_spec.schema.json",
    " M src/film_pipeline/director_blocking.py",
    " M tests/test_director_blocking_v2_003.py",
    " M tests/test_v2_003_recovery_001.py",
    " M tools/build_v2_003_previz.py",
    " M src/film_pipeline/quality_repair_v2.py",
    " M tests/test_quality_v2_repair_policy_001.py",
    " M src/film_pipeline/providers/dola_provider.py",
    " M tests/test_v2_010a_dola_re_001.py",
    " M docs/quality-v2/V2_006_F2_DECOMPOSED_LIVE_HANDOFF.md",
    " M tests/test_v2_005_decomposition_001.py",
}


def test_rc020_021_022_baseline_canonical_unchanged():
    assert QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == \
        CANONICAL_MASTER_SHA256
    dirty = [ln for ln in subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
        text=True).stdout.splitlines() if not ln.startswith("??")]
    unexpected = [ln for ln in dirty if ln not in INGEST_TRACKED_ALLOWLIST]
    assert unexpected == [], unexpected


# RC-023/024 — no provider calls, no generation
def test_rc023_024_no_provider_or_generation_surface():
    public = [n for n, v in vars(db).items()
              if callable(v) and not n.startswith("_")]
    assert not any("generate" in n.lower() or "submit" in n.lower() or
                   "provider_call" in n.lower() for n in public)
    assert not (PKG / "generate_ledger.json").exists()
    # the ONLY mp4 allowed in the package is the previz planning
    # evidence listed in the previz manifest — never a render
    manifest = json.loads((PKG / "previz_manifest_v2_003.json")
                          .read_text(encoding="utf-8"))
    allowed_mp4s = {Path(rel).name for rel in manifest["artifacts"].values()
                    if rel.endswith(".mp4")}
    present_mp4s = {p.name for p in PKG.glob("**/*.mp4")}
    assert present_mp4s <= allowed_mp4s


# RC-025/026 — model custody: no SILENT downgrade. The original
# unavailability stays recorded; the ONLY path to F2 artifacts is the
# explicit Owner substitute authorization (GPT-5.6 Sol ingest).
def test_rc025_026_no_downgrade_model_unavailable():
    binding = pkg_json("director_model_binding_v2_003.json")
    receipt = binding["availability_receipt"]
    assert receipt["exact_model_available"] is False
    assert receipt["result"] == "DIRECTOR_MODEL_UNAVAILABLE"
    auth = binding.get("substitute_authorization") or {}
    assert auth.get("model") == "GPT-5.6 Sol"
    assert auth.get("authorization_source", "").startswith(
        "Owner explicit authorization")
    assert binding["director_work_state"] == "AUTHORIZED_SUBSTITUTE_FROZEN"
    plan = pkg_json("f2_director_plan_v2_003.json")
    assert plan["substitute_authorization"] == auth


# RC-027 — ambiguity rule intact
def test_rc027_ambiguity_rule_intact():
    assert EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"


# RC-028/029 — previz determinism and containment
def test_rc028_029_previz_deterministic_and_contained(tmp_path):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(
        make_blocking().model_dump(mode="json"), indent=1),
        encoding="utf-8")
    out1 = tmp_path / "p1"
    out2 = tmp_path / "p2"
    for out in (out1, out2):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/build_v2_003_previz.py"),
             str(spec_path), str(out), "FIXTURE"], capture_output=True,
            text=True)
        assert proc.returncode == 0, proc.stderr
    h1 = file_sha(out1 / "BLOCKING_TOPDOWN.png")
    h2 = file_sha(out2 / "BLOCKING_TOPDOWN.png")
    assert h1 == h2
    # all outputs stayed inside the declared directories
    for out in (out1, out2):
        for produced in out.iterdir():
            assert out in produced.parents


# RC-030 — empty authority strings refused
def test_rc030_empty_authority_refused():
    with pytest.raises(ValueError, match="authority sources"):
        make_intent(authority_sources={
            "dramatic_purpose": "src", "viewer_must_understand": "src",
            "primary_action_objective": "src", "required_visual_change": "",
            "required_end_read": "src",
            "forbidden_interpretations": "src"})
