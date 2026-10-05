"""QUALITY-V2-005 decomposition tests: frozen plan integrity, D1-D10
gates (positive + failure modes), preview manifest custody, previz
artifacts, and the V2-004 REJECT_ALL custody."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.director_blocking import (
    FROZEN_EDITORIAL_STATES, BlockingSpec, CameraCoveragePlan,
    DirectorIntent, SpatialStateChange, TravelPath, Waypoint,
    require_decomposition_gates, validate_decomposition_gates,
    validate_director_gates, validate_timing_invariant)
from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, EXTERNAL_AMBIGUITY_RULE,
    QUALITY_V2_CANONICAL_BASELINE)

PKG = ROOT / "projects/quality_v2_005_f2_decomposition"
V3 = ROOT / "projects/quality_v2_003_director_blocking"
V4 = ROOT / "projects/quality_v2_004_f2_blocking"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")


def pkg_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def plan():
    return pkg_json("projects/quality_v2_005_f2_decomposition/"
                    "f2_decomposition_plan_v2_005.json")


def live_pair():
    """Re-mint the live plan objects from the frozen JSON."""
    plan = pkg_json("projects/quality_v2_005_f2_decomposition/"
                    "f2_decomposition_plan_v2_005.json")
    def shot(key):
        raw = plan[key]
        return {"intent": DirectorIntent.model_validate(raw["intent"]),
                "blocking": BlockingSpec.model_validate(raw["blocking"]),
                "camera": CameraCoveragePlan.model_validate(raw["camera"]),
                "trim_s": raw["trim_s"],
                "gates_b6": raw["gates_B1_B10"]["gates"][
                    "B6_NO_REVERSAL"]["state"] == "PASS"}
    return shot("f2a_commit_to_cross"), shot("f2b_emerge_far_side")


# --- custody ------------------------------------------------------------

def test_01_reject_all_recorded():
    doc = pkg_json("projects/quality_v2_005_f2_decomposition/"
                   "v2_004_owner_decision.json")
    assert doc["V2_004_OWNER_DECISION"] == "REJECT_ALL"
    assert len(doc["reasons"]) == 4
    for rej in doc["rejections"]:
        assert rej["state_after"] == "OWNER_REJECTED"
        assert rej["state_before"] == "PROPOSED"
    assert doc["no_promotion"] is True
    assert doc["debt_QD-001_state"].startswith("ACTIVE")


def test_02_custody_and_frozen_identities():
    custody = pkg_json("projects/quality_v2_005_f2_decomposition/"
                       "start_custody_v2_005.json")
    plan3 = pkg_json("projects/quality_v2_003_director_blocking/"
                     "f2_director_plan_v2_003.json")
    assert custody["start_sha"] == "a1dec4d27882dddf27adeb91449d3fcc41e771ad"
    assert custody["frozen_director_identities"] == \
        plan3["semantic_identity"]["director_layer"]
    assert custody["canonical_f2_slot"]["duration_s"] == 5.6
    assert custody["f1_f2_f3_continuity"]["screen_direction"] == \
        "faces frame-left"


# --- frozen plan integrity ------------------------------------------------

def test_03_f2a_plan_shape(plan):
    a = plan["f2a_commit_to_cross"]
    assert a["blocking"]["start_zone"] == "BEFORE_GATE"
    assert a["blocking"]["end_zone"] == \
        "CENTER_GATE_OPENING:AT_THRESHOLD_COMMITTED"
    assert a["blocking"]["forbidden_zones"] == ["AT_ROCK", "BEYOND_GATE"]
    assert a["blocking"]["forbidden_reversal"] is True
    assert a["trim_s"] == 2.8
    wps = a["blocking"]["travel_path"]["ordered_waypoints"]
    assert wps[-1]["is_crossing"] is True
    assert wps[-1]["note"].startswith("arrives AT the threshold")


def test_04_f2b_plan_shape(plan):
    b = plan["f2b_emerge_far_side"]
    assert b["blocking"]["start_zone"] == \
        "CENTER_GATE_OPENING:CROSSING_OR_JUST_BEYOND"
    assert b["blocking"]["end_zone"] == "BEYOND_GATE:FAR_SIDE_CLEAR"
    assert b["blocking"]["forbidden_zones"] == ["AT_ROCK", "BEFORE_GATE"]
    wps = b["blocking"]["travel_path"]["ordered_waypoints"]
    assert wps[0]["is_crossing"] is True
    assert wps[-1]["zone"] == "BEYOND_GATE:FAR_SIDE_CLEAR"
    assert b["trim_s"] == 2.8


def test_05_editorial_states_and_ellipsis(plan):
    assert plan["editorial_states"] == dict(FROZEN_EDITORIAL_STATES)
    ell = plan["editorial_ellipsis"]
    assert ell["audience_inference"] == "He crossed."
    assert ell["legitimate_ellipsis"] is True
    assert ell["no_continuous_crossing_footage_required"] is True


def test_06_timing_plan_not_doubled(plan):
    timing = plan["timing_plan"]
    assert timing["f2a_trim_s"] + timing["f2b_trim_s"] == 5.6
    assert timing["allocation_s"] == 5.6
    assert timing["total_s"] == 5.6


def test_07_b1_b10_all_pass_both(plan):
    for key in ("f2a_commit_to_cross", "f2b_emerge_far_side"):
        gates = plan[key]["gates_B1_B10"]
        assert gates["all_pass"] is True and gates["blocked_by"] == []


def test_08_d1_d10_all_pass(plan):
    gates = plan["decomposition_gates"]
    assert gates["all_pass"] is True and gates["blocked_by"] == []
    assert set(gates["gates"]) == {
        "D1_STORY_MEANING_PRESERVED", "D2_EACH_SHOT_ONE_DOMINANT_ACTION",
        "D3_F2A_END_F2B_START_COMPATIBLE", "D4_FAR_SIDE_STATE_OBSERVABLE",
        "D5_ROCK_NOT_DESTINATION", "D6_NO_REVERSAL_REQUIRED",
        "D7_EDITORIAL_ELLIPSIS_LEGIBLE", "D8_F1_F2A_F2B_F3_CONTINUITY",
        "D9_DURATION_BOUNDED", "D10_CANONICAL_UNCHANGED"}


# --- D-gate failure modes (live guards) ------------------------------------

def test_09_d2_f2a_crossing_completes_refused():
    f2a, f2b = live_pair()
    a = dict(f2a)
    a["blocking"] = variant(f2a, travel_path=TravelPath(
        path_type="DIRECT_TRAVERSAL",
        ordered_waypoints=[
            Waypoint(zone="BEFORE_GATE"),
            Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True),
            Waypoint(zone="BEYOND_GATE")],
        required_crossing="CENTER_GATE_OPENING"))
    out = validate_decomposition_gates(
        story_meaning=_meaning(), f2a=a, f2b=f2b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing=_timing(), canonical=_canonical())
    assert "D2_EACH_SHOT_ONE_DOMINANT_ACTION" in out["blocked_by"]


def _mint(model_cls, id_field, prefix, data):
    from film_pipeline.director_blocking import _mint as m
    return m(model_cls, id_field, prefix, data)


def variant(shot_dict, **overrides):
    raw = shot_dict["blocking"].model_dump(
        mode="json", exclude={"blocking_spec_id"})
    raw["created_at"] = "t"
    raw.update(overrides)
    return _mint(BlockingSpec, "blocking_spec_id", "BS-", raw)


def _meaning():
    plan = pkg_json("projects/quality_v2_005_f2_decomposition/"
                    "f2_decomposition_plan_v2_005.json")
    return plan["story_meaning"]


def _timing():
    plan = pkg_json("projects/quality_v2_005_f2_decomposition/"
                    "f2_decomposition_plan_v2_005.json")
    return {"f2a_trim_s": plan["timing_plan"]["f2a_trim_s"],
            "f2b_trim_s": plan["timing_plan"]["f2b_trim_s"],
            "allocation_s": 5.6, "max_total_s": 6.4}


def _canonical():
    plan = pkg_json("projects/quality_v2_005_f2_decomposition/"
                    "f2_decomposition_plan_v2_005.json")
    return {"canonical_manifest_id": plan["preview_edit_manifest"][
        "edit_manifest_id"] + "_canonical",
        "preview_manifest_id": plan["preview_edit_manifest"][
            "edit_manifest_id"],
        "no_change_proof": True}


def test_10_d3_incompatible_families_refused():
    f2a, f2b = live_pair()
    b = dict(f2b)
    b["blocking"] = variant(f2b, start_zone="BEFORE_GATE")
    out = validate_decomposition_gates(
        story_meaning=_meaning(), f2a=f2a, f2b=b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing=_timing(), canonical=_canonical())
    assert "D3_F2A_END_F2B_START_COMPATIBLE" in out["blocked_by"]


def test_11_d5_rock_interaction_allowed_refused():
    f2a, f2b = live_pair()
    a = dict(f2a)
    a["blocking"] = variant(f2a, allowed_interactions=["ROCK_BRACE"])
    out = validate_decomposition_gates(
        story_meaning=_meaning(), f2a=a, f2b=f2b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing=_timing(), canonical=_canonical())
    assert "D5_ROCK_NOT_DESTINATION" in out["blocked_by"]


def test_12_d7_editorial_state_drift_refused():
    f2a, f2b = live_pair()
    states = dict(FROZEN_EDITORIAL_STATES)
    states["F2A_END_STATE"] = "MID_CROSSING"
    out = validate_decomposition_gates(
        story_meaning=_meaning(), f2a=f2a, f2b=f2b,
        editorial_states=states, timing=_timing(),
        canonical=_canonical())
    assert "D7_EDITORIAL_ELLIPSIS_LEGIBLE" in out["blocked_by"]


def test_13_d8_direction_conflict_refused():
    f2a, f2b = live_pair()
    b = dict(f2b)
    b["blocking"] = variant(f2b, screen_direction="faces frame-right")
    out = validate_decomposition_gates(
        story_meaning=_meaning(), f2a=f2a, f2b=b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing=_timing(), canonical=_canonical())
    assert "D8_F1_F2A_F2B_F3_CONTINUITY" in out["blocked_by"]


def test_14_d9_duration_doubling_refused():
    f2a, f2b = live_pair()
    out = validate_decomposition_gates(
        story_meaning=_meaning(), f2a=f2a, f2b=f2b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing={"f2a_trim_s": 5.6, "f2b_trim_s": 5.6,
                "allocation_s": 5.6, "max_total_s": 6.4},
        canonical=_canonical())
    assert "D9_DURATION_BOUNDED" in out["blocked_by"]


def test_15_d10_preview_equals_canonical_refused():
    f2a, f2b = live_pair()
    plan = pkg_json("projects/quality_v2_005_f2_decomposition/"
                    "f2_decomposition_plan_v2_005.json")
    out = validate_decomposition_gates(
        story_meaning=_meaning(), f2a=f2a, f2b=f2b,
        editorial_states=dict(FROZEN_EDITORIAL_STATES),
        timing=_timing(),
        canonical={"canonical_manifest_id": plan["preview_edit_manifest"][
            "edit_manifest_id"],
            "preview_manifest_id": plan["preview_edit_manifest"][
                "edit_manifest_id"],
            "no_change_proof": True})
    assert "D10_CANONICAL_UNCHANGED" in out["blocked_by"]


def test_16_require_wrapper_raises():
    f2a, f2b = live_pair()
    with pytest.raises(ValueError, match="BLOCKED_INVARIANT"):
        require_decomposition_gates(
            story_meaning=_meaning(), f2a=f2a, f2b=f2b,
            editorial_states={"F2A_END_STATE": "X",
                              "F2B_START_STATE": "Y",
                              "F2B_END_STATE": "Z"},
            timing=_timing(), canonical=_canonical())


# --- preview manifest custody ------------------------------------------------

def test_17_preview_manifest_shape(plan):
    preview = plan["preview_edit_manifest"]
    clips = preview["clips"]
    assert preview["preview_only"] is True
    assert preview["edit_manifest_id"] != \
        "edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590654b059c79" \
        "69d3"
    ids = [c["shot_id"] for c in clips]
    assert "SEQ7_F2C" not in ids
    assert "SEQ7_F2A" in ids and "SEQ7_F2B" in ids
    f2a = next(c for c in clips if c["shot_id"] == "SEQ7_F2A")
    f2b = next(c for c in clips if c["shot_id"] == "SEQ7_F2B")
    assert f2a["target_duration_s"] == 2.8
    assert f2b["target_duration_s"] == 2.8
    assert len(clips) == 31  # 30 canonical slots - 1 + 2
    orders = [c["order"] for c in clips]
    assert orders == list(range(1, len(clips) + 1))


def test_18_preview_total_not_doubled(plan):
    total = plan["preview_edit_manifest"]["total_duration_s"]
    assert total <= 194.55  # canonical 194.541667 minus rounding


# --- previz -------------------------------------------------------------------

def test_19_previz_artifacts_and_determinism():
    manifest = pkg_json("projects/quality_v2_005_f2_decomposition/"
                        "previz_manifest_v2_005.json")
    assert set(manifest["artifacts"]) == {
        "F2A_BLOCKING_TOPDOWN.png", "F2B_BLOCKING_TOPDOWN.png",
        "F2A_START_END_SCHEMATIC.png", "F2B_START_END_SCHEMATIC.png",
        "F2_DECOMPOSITION_PREVIZ.mp4"}
    for name, sha in manifest["sha256"].items():
        assert file_sha(ROOT / manifest["artifacts"][name]) == sha, name
    assert manifest["sequence"] == ["BEFORE_GATE (F2A)", "CUT",
                                    "BEYOND_GATE (F2B)"]


# --- invariants -----------------------------------------------------------------

def test_20_no_generation_no_mutation(plan):
    inv = plan["invariants"]
    assert inv["video_generation"] == 0 and inv["flow_submit"] == 0 \
        and inv["upload"] == 0 and inv["canonical_mutation"] == 0
    assert inv["rock_interaction"] == "FORBIDDEN COMPLETELY"
    assert not (PKG / "generate_ledger.json").exists()
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == \
        CANONICAL_MASTER_SHA256
    assert QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
    assert EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"
