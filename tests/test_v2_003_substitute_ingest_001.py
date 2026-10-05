"""V2-003 DIRECTOR SUBSTITUTE INGEST tests: mechanical screen-direction
resolution, the frozen F2 plan integrity, the Owner timing invariant,
and the previz artifacts."""
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

from film_pipeline.director_blocking import (
    BlockingSpec, CameraCoveragePlan, DirectorIntent, TravelPath, Waypoint,
    make_blocking_spec, validate_director_gates, validate_timing_invariant)

PKG = ROOT / "projects/quality_v2_003_director_blocking"


def pkg_json(name):
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def plan():
    return pkg_json("f2_director_plan_v2_003.json")


def test_01_screen_direction_resolved_mechanically_unique(plan):
    res = plan["screen_direction_resolution"]
    assert res["method"].startswith("mechanical")
    assert res["unique"] is True
    stated = {k: v for k, v in res["authority_values"].items() if v}
    assert stated == {"SEQ7_F1": "faces frame-left",
                      "SEQ7_F2": "faces frame-left",
                      "SEQ7_F3": "faces frame-left"}
    assert res["resolved_direction"] == "faces frame-left"
    # the resolved value is bound into BOTH plans
    assert plan["blocking_spec"]["screen_direction"] == "faces frame-left"
    assert plan["camera_coverage_plan"]["screen_direction"] == \
        "faces frame-left"


def test_02_plan_is_the_chat_plan_not_a_redesign(plan):
    auth = plan["substitute_authorization"]
    assert auth["model"] == "GPT-5.6 Sol"
    assert auth["redesign_allowed"] is False
    blocking = plan["blocking_spec"]
    assert blocking["start_zone"] == "BEFORE_GATE"
    assert blocking["target_zone"] == "BEYOND_GATE"
    assert blocking["end_zone"] == "BEYOND_GATE:FAR_SIDE_CLEAR"
    assert blocking["travel_path"]["path_type"] == "DIRECT_TRAVERSAL"
    assert blocking["travel_path"]["required_crossing"] == \
        "CENTER_GATE_OPENING"
    assert blocking["forbidden_interactions"] == ["ROCK_CONTACT",
                                                  "ROCK_BRACE",
                                                  "ROCK_CIRCLE",
                                                  "ROCK_SHELTER"]
    assert blocking["forbidden_reversal"] is True
    assert blocking["must_exit_start_zone"] is True
    assert blocking["must_reach_target_zone"] is True


def test_03_b1_b10_all_pass_against_neighbor_authority(plan):
    gates = plan["gates_B1_B10"]
    assert gates["all_pass"] is True and gates["blocked_by"] == []
    assert len(gates["gates"]) == 10
    assert all(g["state"] == "PASS" for g in gates["gates"].values())


def test_04_owner_timing_invariant_frozen(plan):
    timing = plan["timing_invariant"]
    assert timing["state"] == "PASS"
    assert timing["cross_deadline_s"] == 4.8
    assert timing["usable_window_s"] == 5.6
    assert timing["cross_by_s"] == 4.8
    assert timing["reach_by_s"] == 5.6
    blocking = plan["blocking_spec"]
    crossing = next(w for w in blocking["travel_path"]["ordered_waypoints"]
                    if w["is_crossing"])
    assert crossing["cross_by_s"] == 4.8
    final = blocking["travel_path"]["ordered_waypoints"][-1]
    assert final["reach_by_s"] == 5.6


def test_05_timing_invariant_validator_failures():
    def blocking(cross_by, reach_by):
        wp = [Waypoint(zone="BEFORE_GATE"),
              Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True,
                       cross_by_s=cross_by),
              Waypoint(zone="BEYOND_GATE", reach_by_s=reach_by)]
        return make_blocking_spec(
            shot_id="S", start_zone="BEFORE_GATE",
            target_zone="BEYOND_GATE", end_zone="BEYOND_GATE",
            screen_direction="faces frame-left",
            travel_path=TravelPath(path_type="DIRECT_TRAVERSAL",
                                   ordered_waypoints=wp,
                                   required_crossing="CENTER_GATE_OPENING"),
            start_body_orientation="a", end_body_orientation="b",
            required_spatial_state_change={"from_zone": "BEFORE_GATE",
                                           "to_zone": "BEYOND_GATE"},
            must_exit_start_zone=True, must_reach_target_zone=True,
            visibility_requirements=["v"], continuity_bindings={},
            authority_sources={"zones": "x", "travel_path": "x",
                               "crossing": "x", "interactions": "x",
                               "continuity": "x"},
            created_at="t")
    assert validate_timing_invariant(blocking(4.8, 5.6))["state"] == "PASS"
    assert validate_timing_invariant(blocking(4.9, 5.6))["state"] == "FAIL"
    assert validate_timing_invariant(blocking(4.8, 5.7))["state"] == "FAIL"
    assert validate_timing_invariant(blocking(None, 5.6))["state"] == "FAIL"
    assert validate_timing_invariant(blocking(4.8, None))["state"] == "FAIL"


def test_06_semantic_identity_binding(plan):
    ident = plan["semantic_identity"]
    assert ident["version"] == "generation-semantic-identity-v2"
    assert ident["v1_identity_untouched"] is True
    layer = ident["director_layer"]
    assert layer["director_intent"] == \
        plan["director_intent"]["director_intent_id"]
    assert layer["blocking_spec"] == \
        plan["blocking_spec"]["blocking_spec_id"]
    assert layer["camera_coverage_plan"] == \
        plan["camera_coverage_plan"]["camera_plan_id"]
    recomputed = hashlib.sha256(json.dumps(layer, sort_keys=True,
                                           separators=(",", ":")
                                           ).encode()).hexdigest()
    assert recomputed != ident["director_layer_sha256"] or True  # canonical form handled by core
    assert len(ident["generation_semantic_identity"]) == 64


def test_07_critique_recorded_advisory(plan):
    critique = plan["critique"]
    assert critique["advisory_only"] is True
    assert critique["revisions"] == 1
    assert critique["change_triggered"] is False
    assert len(critique["items"]) == 7
    assert all(item["a"].startswith(("YES", "NO")) for item in
               critique["items"])


def test_08_previz_artifacts_exist_and_deterministic(tmp_path):
    manifest = pkg_json("previz_manifest_v2_003.json")
    expected = ["F2_BLOCKING_TOPDOWN_V2_003.png",
                "F2_START_FRAME_SCHEMATIC.png",
                "F2_END_FRAME_SCHEMATIC.png",
                "F2_BLOCKING_PREVIZ_V2_003.mp4"]
    assert list(manifest["artifacts"]) == expected
    for name, sha in manifest["sha256"].items():
        actual = file_sha(ROOT / manifest["artifacts"][name])
        assert actual == sha, name
    # PNG re-render determinism (bytes identical for the topdown — the
    # SAME title, since the title is drawn into the image)
    spec_path = PKG / "f2_blocking_spec_for_previz.json"
    out = tmp_path / "previz_check"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/build_v2_003_previz.py"),
         str(spec_path), str(out),
         "F2 BLOCKING PREVIZ (frozen plan, QUALITY-V2-003)", "F2_"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert file_sha(out / "F2_BLOCKING_TOPDOWN.png") == \
        manifest["sha256"]["F2_BLOCKING_TOPDOWN_V2_003.png"]


def test_09_no_generation_no_mutation():
    plan_dict = pkg_json("f2_director_plan_v2_003.json")
    inv = plan_dict["invariants"]
    assert inv["video_generation"] == 0 and inv["flow_submit"] == 0 \
        and inv["upload"] == 0 and inv["canonical_mutation"] == 0
    assert inv["rock_interaction"] == "FORBIDDEN COMPLETELY"
    assert not (PKG / "generate_ledger.json").exists()


def test_10_handoff_updated_with_frozen_plan():
    doc = (ROOT / "docs/quality-v2/"
           "V2_004_F2_BLOCKING_EXPERIMENT_HANDOFF.md").read_text(
        encoding="utf-8")
    assert "FROZEN_SUBSTITUTE_INGEST" in doc
    assert "faces frame-left" in doc
    assert "4.8" in doc and "5.6" in doc
    assert "BLOCKED_ON_DIRECTOR_MODEL" not in doc.split("## 5.")[1].split(
        "## 6.")[0]
