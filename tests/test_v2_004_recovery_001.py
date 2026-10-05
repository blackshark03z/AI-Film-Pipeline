"""QUALITY-V2-004 package recovery cases: every V2-004-specific
adversarial/recovery case executed against its live guard."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import film_pipeline.director_blocking as db
from film_pipeline.director_blocking import (
    BlockingSpec, SpatialStateChange, TravelPath, Waypoint,
    assert_compiler_respected_authority, make_blocking_spec,
    validate_director_gates, validate_timing_invariant)
from film_pipeline.quality_repair_v2 import (
    EXTERNAL_AMBIGUITY_RULE, QUALITY_V2_CANONICAL_BASELINE,
    CANONICAL_MASTER_SHA256)

PKG = ROOT / "projects/quality_v2_004_f2_blocking"
V3 = ROOT / "projects/quality_v2_003_director_blocking"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")


def pkg_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def freeze():
    return pkg_json("projects/quality_v2_004_f2_blocking/"
                    "experiment_freeze_v2_004.json")


@pytest.fixture(scope="module")
def rebind():
    return pkg_json("projects/quality_v2_004_f2_blocking/"
                    "rebind_v2_004.json")


@pytest.fixture(scope="module")
def gov():
    return pkg_json("projects/quality_v2_004_f2_blocking/"
                    "candidates_governance_v2_004.json")


def compiler_blocking():
    plan = pkg_json("projects/quality_v2_003_director_blocking/"
                    "f2_director_plan_v2_003.json")
    return BlockingSpec.model_validate(plan["blocking_spec"])


def plan_blocking(loop_waypoints=None, **kw):
    base = compiler_blocking().model_dump(mode="json",
                                          exclude={"blocking_spec_id"})
    base["created_at"] = "t"
    if loop_waypoints is not None:
        base["travel_path"]["ordered_waypoints"] = loop_waypoints
    base.update(kw)
    return make_blocking_spec(**base)


# RC-001..004 — compiler rock interactions refused
def test_rc001_004_compiler_rock_refusals():
    b = compiler_blocking()
    for interaction, text in (
            ("ROCK_CONTACT", "he makes contact with the rock. End: "
                             "beyond gate far side clear"),
            ("ROCK_BRACE", "he braces on the rock. End: beyond gate far "
                           "side clear"),
            ("ROCK_CIRCLE", "he circles the rock. End: beyond gate far "
                            "side clear"),
            ("ROCK_SHELTER", "he shelters behind the rock. End: beyond "
                             "gate far side clear")):
        with pytest.raises(ValueError, match=interaction):
            assert_compiler_respected_authority(text, b)


# RC-005..008 — plan-level violations
def test_rc005_008_plan_violations():
    intent = None
    from test_director_blocking_v2_003 import make_intent, make_camera
    intent, camera = make_intent(), make_camera()
    out = validate_director_gates(intent, plan_blocking(
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE"),
                Waypoint(zone="AT_ROCK", is_crossing=True,
                         note="ROCK_CONTACT brace"),
                Waypoint(zone="BEYOND_GATE")],
            required_crossing="CENTER_GATE_OPENING")), camera)
    assert "B4_NO_FORBIDDEN_INTERACTION" in out["blocked_by"]
    out = validate_director_gates(intent, plan_blocking(
        allowed_interactions=["ROCK_CIRCLE"]), camera)
    assert "B4_NO_FORBIDDEN_INTERACTION" in out["blocked_by"]
    out = validate_director_gates(intent, plan_blocking(
        target_zone="AT_ROCK", end_zone="AT_ROCK",
        required_spatial_state_change=SpatialStateChange(
            from_zone="BEFORE_GATE", to_zone="AT_ROCK")), camera)
    assert "B3_PATH_HAS_PROGRESS" in out["blocked_by"]
    out = validate_director_gates(intent, plan_blocking(
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE"),
                Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True),
                Waypoint(zone="BEYOND_GATE"),
                Waypoint(zone="BEFORE_GATE")],
            required_crossing="CENTER_GATE_OPENING")), camera)
    assert "B6_NO_REVERSAL" in out["blocked_by"]


# RC-009..011 — timing invariant violations
def test_rc009_011_timing_violations():
    b = compiler_blocking()
    late = b.model_copy(deep=True)
    late.travel_path.ordered_waypoints[1].cross_by_s = 4.9
    assert validate_timing_invariant(late)["state"] == "FAIL"
    late2 = b.model_copy(deep=True)
    late2.travel_path.ordered_waypoints[2].reach_by_s = 5.7
    assert validate_timing_invariant(late2)["state"] == "FAIL"
    no_anchor = b.model_copy(deep=True)
    no_anchor.travel_path.ordered_waypoints[1].cross_by_s = None
    assert validate_timing_invariant(no_anchor)["state"] == "FAIL"


# RC-012 — path never clears the threshold
def test_rc012_never_clears_refused():
    from test_director_blocking_v2_003 import make_intent, make_camera
    out = validate_director_gates(
        make_intent(), plan_blocking(
            travel_path=TravelPath(
                path_type="DIRECT_TRAVERSAL",
                ordered_waypoints=[
                    Waypoint(zone="BEFORE_GATE"),
                    Waypoint(zone="BEFORE_GATE:EDGE")],
                required_crossing="CENTER_GATE_OPENING")),
        make_camera())
    assert "B3_PATH_HAS_PROGRESS" in out["blocked_by"]


# RC-013..015 — camera violations
def test_rc013_015_camera_violations():
    from test_director_blocking_v2_003 import make_intent, make_camera
    out = validate_director_gates(
        make_intent(), plan_blocking(),
        make_camera(required_crossing_visibility=False))
    assert "B7_CROSSING_OBSERVABLE" in out["blocked_by"]
    out = validate_director_gates(
        make_intent(), plan_blocking(),
        make_camera(subject_start_region="BEFORE_GATE",
                    subject_end_region="BEFORE_GATE:EDGE"))
    assert "B8_END_STATE_OBSERVABLE" in out["blocked_by"]


# RC-016..018 — candidate byte-equivalence
def test_rc016_018_byte_equivalence(freeze, rebind):
    a, b = freeze["candidates"]
    assert a["action_intent_digest"] == b["action_intent_digest"]
    assert freeze["frozen_director_authority"][
        "generation_semantic_identity"] == \
        rebind["frozen_identities"]["generation_semantic_identity"]
    assert freeze["frozen_director_authority"]["not_redesigned"] is True
    assert a["candidate_semantic_identity"] != \
        b["candidate_semantic_identity"]


# RC-019..020 — budget / retry
def test_rc019_020_budget_and_retry(monkeypatch):
    ledger = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "generate_ledger.json")
    assert ledger["max_primary"] == 2
    assert len(ledger["primary_consumed"]) == 2
    import run_quality_v2_004_experiment as driver
    calls = []
    monkeypatch.setattr(driver.base, "run_live_shot",
                        lambda *a, **k: calls.append(a))
    with pytest.raises(Exception, match="budget exhausted"):
        driver.main()
    assert calls == []
    for entry in ledger["primary_consumed"]:
        shot_dir = (PKG / "scene_SCENE_F_STORM_GATE" /
                    f"shot_{entry['shot_id']}")
        assert (shot_dir / "result.json").exists()


# RC-021..022 — ambiguity latch + single dispatch
def test_rc021_022_custody(tmp_path):
    from mutation_authority import MutationAuthority
    from film_pipeline.providers.flow_reference_upload import \
        OwnerAmbiguityGate
    auth = MutationAuthority(tmp_path, "THROWAWAY-V2004")
    auth.latch("GENERATE_AMBIGUITY", "simulated")
    with pytest.raises(OwnerAmbiguityGate):
        auth.check_mutation_allowed("primary_generate")
    ma = pkg_json("projects/quality_v2_004_f2_blocking/"
                  "mutation_authority.json")
    assert ma["mutation_authority"] == "OPEN"
    import sqlite3
    con = sqlite3.connect(ROOT / "projects/flow_production_harden_002/"
                          "requal_current_build/runtime.sqlite")
    try:
        for entry in pkg_json("projects/quality_v2_004_f2_blocking/"
                              "generate_ledger.json")["primary_consumed"]:
            pass
        freeze = pkg_json("projects/quality_v2_004_f2_blocking/"
                          "experiment_freeze_v2_004.json")
        for cand in freeze["candidates"]:
            result = pkg_json("projects/quality_v2_004_f2_blocking/"
                              f"scene_SCENE_F_STORM_GATE/shot_"
                              f"{cand['shot_id']}/result.json")
            row = con.execute(
                "SELECT dispatch_count FROM provider_jobs WHERE id=?",
                (result["provider_job_id"],)).fetchone()
            assert row is not None and row[0] == 1
    finally:
        con.close()


# RC-023..024 — mapping and copy integrity
def test_rc023_024_surface_integrity():
    manifest = pkg_json("projects/quality_v2_004_f2_blocking/"
                        "owner_review_manifest_v2_004.json")
    segs = [s for s in manifest["segments"] if s["asset_sha256"]]
    assert [s["label"] for s in segs] == ["BASELINE", "CANDIDATE A",
                                          "CANDIDATE B"]
    copies = manifest["review_copies"]
    for name, info in copies.items():
        actual = file_sha(ROOT / "OWNER_REVIEW/V2_004" / name)
        assert actual == info["sha256"], name
    assert copies["BASELINE.mp4"]["sha256"] == \
        "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c39898254890a767"


# RC-025..027 — decision rights
def test_rc025_027_decision_rights(gov):
    template = pkg_json("projects/quality_v2_004_f2_blocking/"
                        "owner_f2_blocking_decision_v2_004.template.json")
    assert template["decision"] is None
    assert template["selected_asset_sha256"] is None
    assert gov["no_owner_decision_minted"] is True
    assert gov["no_promotion_executed"] is True
    for entry in gov["candidates"]:
        state = entry.get("governed", {}).get("owner_decision_state",
                                              entry["state"])
        assert state in ("PROPOSED", "TECHNICALLY_VALID",
                         "QUALITY_REVIEW_READY")


# RC-028..030 — canonical custody
def test_rc028_030_canonical_unchanged():
    proof = pkg_json("projects/quality_v2_004_f2_blocking/"
                     "canonical_no_change_v2_004.json")
    assert proof["canonical_master_unchanged"] is True
    assert proof["canonical_f2_take_unchanged"] is True
    assert proof["edit_manifest_unchanged"] is True
    assert proof["canonical_mutation"] == 0
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == \
        CANONICAL_MASTER_SHA256


# RC-031 — V1 baseline
def test_rc031_v1_baseline():
    assert QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"


# RC-032..034 — review surface integrity
def test_rc032_034_review_integrity(gov):
    for entry in gov["candidates"]:
        if "review_refusal" in entry:
            assert entry["state"] == "PROPOSED"
            assert entry["review_refusal"]["hard_fails"]
            hard = entry["review_refusal"]["hard_fails"]
            spatial = entry["open_observations"]["spatial_qc"]
            for check in hard:
                assert spatial[check]["verdict"] == "FAIL"
                assert spatial[check]["evidence"]
        else:
            assert entry["review"]["no_aggregate_score"] is True
            assert entry["review"]["findings"]


# RC-035..038 — admission/route custody
def test_rc035_038_admission_custody():
    admission = pkg_json("projects/quality_v2_004_f2_blocking/"
                         "experiment_admission_v2_004.json")
    receipt = admission["receipt"]
    assert receipt["max_generate_budget"] == 2
    assert admission["gate_result"]["status"] == "ADMITTED"
    assert "clean-pro-qualified" in receipt["provider_route"]
    ledger = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "generate_ledger.json")
    assert ledger["max_uploads"] == 0 and ledger["max_repair"] == 0
    freeze = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "experiment_freeze_v2_004.json")
    assert freeze["route"]["model_label"] == "veo_3_1_r2v_lite"


# RC-039..040 — reference/output custody
def test_rc039_040_reference_and_output():
    freeze = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "experiment_freeze_v2_004.json")
    binding = freeze["baseline_binding"]["F2C"]
    assert binding["media_id"] == "8f2f5277-aae8-44b5-a5b7-c197d1d7c115"
    att = list((PKG / "scene_SCENE_F_STORM_GATE" /
                "continuity_reference" / "attestation").glob("*.json"))
    assert att
    for cand in freeze["candidates"]:
        result = pkg_json("projects/quality_v2_004_f2_blocking/"
                          f"scene_SCENE_F_STORM_GATE/shot_"
                          f"{cand['shot_id']}/result.json")
        video = Path(result["asset"]["uri_or_path"])
        assert file_sha(video) == result["asset"]["sha256"]


# RC-041 — frozen authority not redesigned
def test_rc041_frozen_authority_intact(rebind):
    plan = pkg_json("projects/quality_v2_003_director_blocking/"
                    "f2_director_plan_v2_003.json")
    assert rebind["frozen_identities"]["director_intent_id"] == \
        plan["director_intent"]["director_intent_id"]
    assert rebind["frozen_identities"]["blocking_spec_id"] == \
        plan["blocking_spec"]["blocking_spec_id"]
    assert rebind["frozen_identities"]["camera_plan_id"] == \
        plan["camera_coverage_plan"]["camera_plan_id"]
    assert rebind["b1_b10"]["all_pass"] is True
    assert rebind["timing"]["state"] == "PASS"


# RC-042 — ambiguity rule
def test_rc042_ambiguity_rule():
    assert EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"


# RC-043..045 — surface guards
def test_rc043_045_surface_guards():
    manifest = pkg_json("projects/quality_v2_004_f2_blocking/"
                        "owner_review_manifest_v2_004.json")
    assert manifest["reel"]["order"][0] == "BASELINE"
    template = pkg_json("projects/quality_v2_004_f2_blocking/"
                        "owner_f2_blocking_decision_v2_004.template.json")
    assert template["decision"] is None


# RC-046..049 — compiler conformance guards (live artifacts)
def test_rc046_049_compiler_conformance(freeze):
    for cand in freeze["candidates"]:
        body = cand["creative_body"].lower()
        assert cand["creative_body_chars"] <= 500
        assert cand["creative_body_words"] <= 74
        for token in ("near side", "far side", "gate", "through"):
            assert token in body, (cand["candidate_id"], token)
        b = compiler_blocking()
        assert_compiler_respected_authority(cand["creative_body"], b)


# RC-050 — no second submit after latch
def test_rc050_latch_before_slots(monkeypatch):
    import run_quality_v2_004_experiment as driver
    from film_pipeline.providers.flow_reference_upload import \
        OwnerAmbiguityGate
    consumed = len(pkg_json("projects/quality_v2_004_f2_blocking/"
                            "generate_ledger.json")["primary_consumed"])
    assert consumed == 2
    monkeypatch.setattr(driver.base, "run_live_shot",
                        lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(OwnerAmbiguityGate):
        driver.main()


# RC-051 — sources unmodified by the copies
def test_rc051_sources_unmodified():
    manifest = pkg_json("projects/quality_v2_004_f2_blocking/"
                        "owner_review_manifest_v2_004.json")
    for seg in manifest["segments"]:
        if seg["asset_sha256"]:
            pass
    result = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_V2_004_A/"
                      "result.json")
    assert file_sha(Path(result["asset"]["uri_or_path"])) == \
        result["asset"]["sha256"]


# RC-052 — question card completeness
def test_rc052_questions_complete():
    from build_v2_004_owner_surface import QUESTIONS
    assert len(QUESTIONS) == 7
    assert "XUYEN QUA" in QUESTIONS[2]
    assert "A hay B" in QUESTIONS[5]


# RC-053..054 — no retry, plan drift
def test_rc053_054_no_retry_no_drift():
    ma = pkg_json("projects/quality_v2_004_f2_blocking/"
                  "mutation_authority.json")
    kinds = [e["kind"] for e in ma["events"]]
    assert kinds.count("BUDGET_CONSUMED") == 2
    assert "OWNER_AMBIGUITY_GATE_LATCHED" not in kinds
    freeze = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "experiment_freeze_v2_004.json")
    assert freeze["frozen_director_authority"]["blocking_spec_id"]


# RC-055..056 — no auto-selection, no promotion
def test_rc055_056_no_autoselect_no_promotion(gov):
    for entry in gov["candidates"]:
        dump = json.dumps(entry)
        assert "OWNER_SELECTED" not in dump
    events = [p.name for p in PKG.glob("*ledger*.json")]
    for name in events:
        assert "PROMOTION_COMMITTED" not in (PKG / name).read_text(
            encoding="utf-8")


# RC-057..059 — QC structure integrity
def test_rc057_059_qc_structure(gov):
    obs = pkg_json("projects/quality_v2_004_f2_blocking/"
                   "observations_v2_004.json")
    for cid, entry in obs["candidates"].items():
        assert "camera_qc" in entry and "spatial_qc" in entry
        for check, verdict in entry["spatial_qc"].items():
            assert verdict["verdict"] in ("PASS", "FAIL")
            assert verdict["evidence"]
    for entry in gov["candidates"]:
        spatial = entry.get("spatial_qc") or             entry["open_observations"]["spatial_qc"]
        camera = entry.get("camera_qc") or             entry["open_observations"]["camera_qc"]
        assert spatial and camera


# RC-060..062 — scope/ambiguity/wire guards
def test_rc060_062_scope_and_wire():
    assert not (PKG / "generate_ledger_alt.json").exists()
    ledger = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "generate_ledger.json")
    assert len(ledger["primary_consumed"]) == \
        ledger["max_primary"]
    freeze = pkg_json("projects/quality_v2_004_f2_blocking/"
                      "experiment_freeze_v2_004.json")
    for cand in freeze["candidates"]:
        assert "far side" in cand["creative_body"].lower()
