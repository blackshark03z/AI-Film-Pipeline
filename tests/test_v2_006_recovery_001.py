"""QUALITY-V2-006 package recovery cases: every V2-006-specific
adversarial/recovery case executed against its live guard."""
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
    FROZEN_EDITORIAL_STATES, BlockingSpec, validate_decomposition_gates)
from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, EXTERNAL_AMBIGUITY_RULE,
    QUALITY_V2_CANONICAL_BASELINE)

PKG = ROOT / "projects/quality_v2_006_f2_decomposed_live"
V5 = ROOT / "projects/quality_v2_005_f2_decomposition"
V6 = ROOT / "projects/quality_v2_006_f2_decomposed_live"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")


def pkg_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def gov():
    return pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                    "candidates_governance_v2_006.json")


@pytest.fixture(scope="module")
def freeze():
    return pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                    "experiment_freeze_v2_006.json")


# RC-001..003 — split-reference guards
def test_rc001_003_split_reference_guards(freeze):
    a = freeze["candidates"][0]["reference_binding"]
    b = freeze["candidates"][1]["reference_binding"]
    assert a["media_id"] == "8f2f5277-aae8-44b5-a5b7-c197d1d7c115"
    assert a["reference_type"] == "FULL_FRAME_ENVIRONMENTAL"
    assert b["media_id"] == "7b725f7b-4da5-4455-a6f2-135c4ba22397"
    assert b["reference_type"] == "IDENTITY_ONLY"
    assert b["source_frame_sha256"] == \
        "ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4ddf0bc3a0ca4e8"
    assert b["source_frame_sha256"] != a["source_frame_sha256"]
    # the F2B scene dir must not contain the near-side attestation
    f2b_att = list((PKG / "scene_SCENE_F_FAR_SIDE" /
                    "continuity_reference" / "attestation").glob("*"))
    assert not any(p.name.startswith("fecf669e") for p in f2b_att)
    assert any(p.name.startswith("refbind_57abbee5") for p in f2b_att)


# RC-004..005 — uploads / provider
def test_rc004_005_no_upload_no_switch():
    ledger = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                      "generate_ledger.json")
    assert ledger["max_uploads"] == 0 and ledger["uploads"] == []
    assert ledger["max_primary"] == 2
    assert "clean-pro-qualified" in json.dumps(
        pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                 "experiment_admission_v2_006.json"))


# RC-006..010 — F2A QC verdicts (recorded with evidence)
def test_rc006_010_f2a_verdicts(gov):
    entry = next(c for c in gov["candidates"]
                 if c["candidate_id"] == "F2A-V2-006")
    qc = entry["spatial_qc"]
    assert qc["A6_DOES_NOT_CROSS_FULLY"]["verdict"] == "PASS"
    assert qc["A5_REACHES_THRESHOLD"]["verdict"] == "FAIL"
    assert qc["A10_END_STATE_AT_THRESHOLD_READABLE"]["verdict"] == "FAIL"
    assert entry["review_refusal"]["hard_fails"]
    for check in entry["review_refusal"]["hard_fails"]:
        if check in qc:
            assert qc[check]["verdict"] == "FAIL"
            assert qc[check]["evidence"]


# RC-011..016 — F2B QC verdicts
def test_rc011_016_f2b_verdicts(gov):
    entry = next(c for c in gov["candidates"]
                 if c["candidate_id"] == "F2B-V2-006")
    qc = entry["spatial_qc"]
    assert qc["B2_GATE_BEHIND_SUBJECT"]["verdict"] == "PASS"
    assert qc["B1_START_ALREADY_CROSSING_OR_BEYOND"]["verdict"] == "FAIL"
    assert qc["B5_FAR_SIDE_REACHED"]["verdict"] == "FAIL"
    assert qc["B6_FAR_SIDE_READABLE_BY_2_4S"]["verdict"] == "FAIL"
    assert qc["B10_END_STATE_DISTINCT_AND_CLEAR"]["verdict"] == "FAIL"
    assert qc["WORLD_CONTINUITY"]["verdict"] == "FAIL"
    assert "identity-only" in json.dumps(qc["WORLD_CONTINUITY"][
        "evidence"]).lower() or "world" in json.dumps(
        qc["WORLD_CONTINUITY"]["evidence"]).lower()


# RC-017..022 — pair atomicity
def test_rc017_022_pair_atomicity(gov):
    pair = gov["atomic_pair"]
    assert pair["pair_state"] == "REFUSED"
    assert pair["allowed_owner_decisions"] == ["SELECT_F2A_F2B_PAIR",
                                               "REJECT_ALL",
                                               "KEEP_CANONICAL",
                                               "NEEDS_REPAIR", "DEFER"]
    states = [c["state"] for c in gov["candidates"]]
    assert all(s in ("PROPOSED", "TECHNICALLY_VALID") for s in states)
    refusal_map = {c["candidate_id"]: c["review_refusal"]["hard_fails"]
                   for c in gov["candidates"]}
    assert refusal_map["F2A-V2-006"] and refusal_map["F2B-V2-006"]


# RC-023 — custody == file sha per candidate (the cid dispatch bug class)
def test_rc023_custody_matches_files(gov):
    for entry in gov["candidates"]:
        p = Path(entry["custody"]["video"])
        assert p.exists()
        assert file_sha(p) == entry["custody"]["asset_sha256"], \
            entry["candidate_id"]
    shas = {c["custody"]["asset_sha256"] for c in gov["candidates"]}
    assert len(shas) == 2  # two DISTINCT renders


# RC-024..026 — decision rights
def test_rc024_026_decision_rights(gov):
    template = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                        "owner_f2_pair_decision_v2_006.template.json")
    assert template["decision"] is None
    assert template["selected_pair"] is None
    assert gov["no_owner_decision_minted"] is True
    assert gov["no_promotion_executed"] is True
    for name in (PKG / ".").glob("*ledger*.json"):
        assert "PROMOTION_COMMITTED" not in name.read_text(
            encoding="utf-8")


# RC-027..029 — canonical
def test_rc027_029_canonical_unchanged():
    proof = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                     "canonical_no_change_v2_006.json")
    assert proof["canonical_master_unchanged"] is True
    assert proof["canonical_f2_take_unchanged"] is True
    assert proof["edit_manifest_unchanged"] is True
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == \
        CANONICAL_MASTER_SHA256


# RC-030..032 — budget
def test_rc030_032_budget(monkeypatch):
    ledger = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                      "generate_ledger.json")
    assert ledger["max_primary"] == 2
    assert len(ledger["primary_consumed"]) == 2
    import run_quality_v2_006_experiment as driver
    calls = []
    monkeypatch.setattr(driver.base, "run_live_shot",
                        lambda *a, **k: calls.append(a))
    from film_pipeline.providers.flow_reference_upload import \
        OwnerAmbiguityGate
    with pytest.raises(OwnerAmbiguityGate):
        driver.main()
    assert calls == []


# RC-033..035 — attribution custody
def test_rc033_035_attribution():
    ledger = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                      "generate_ledger.json")
    assert len(ledger["primary_consumed"]) == 2
    freeze = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                      "experiment_freeze_v2_006.json")
    for cand in freeze["candidates"]:
        scene = ("scene_SCENE_F_STORM_GATE"
                 if cand["candidate_id"].startswith("F2A-")
                 else "scene_SCENE_F_FAR_SIDE")
        result = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                          f"{scene}/shot_{cand['shot_id']}/result.json")
        video = Path(result["asset"]["uri_or_path"])
        assert file_sha(video) == result["asset"]["sha256"]
    import sqlite3
    con = sqlite3.connect(ROOT / "projects/flow_production_harden_002/"
                          "requal_current_build/runtime.sqlite")
    try:
        for cand in freeze["candidates"]:
            scene = ("scene_SCENE_F_STORM_GATE"
                     if cand["candidate_id"].startswith("F2A-")
                     else "scene_SCENE_F_FAR_SIDE")
            result = pkg_json("projects/quality_v2_006_f2_decomposed_"
                              f"live/{scene}/shot_{cand['shot_id']}/"
                              "result.json")
            row = con.execute(
                "SELECT dispatch_count FROM provider_jobs WHERE id=?",
                (result["provider_job_id"],)).fetchone()
            assert row is not None and row[0] == 1
    finally:
        con.close()


# RC-036..037 — admission + attestation
def test_rc036_037_admission_attestation():
    admission = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                         "experiment_admission_v2_006.json")
    assert admission["gate_result"]["status"] == "ADMITTED"
    assert admission["receipt"]["max_generate_budget"] == 2
    freeze = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                      "experiment_freeze_v2_006.json")
    for cand in freeze["candidates"]:
        att_id = cand["reference_binding"]["attestation_id"]
        assert (PKG / "scene_SCENE_F_STORM_GATE" /
                "continuity_reference" / "attestation" /
                f"{att_id}.json").exists() or \
            (ROOT / "projects/flow_production_harden_002/"
             "requal_current_build/reference/attestation" /
             f"{att_id}.json").exists()


# RC-038..039 — identity/world
def test_rc038_039_identity_world(gov):
    obs = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                   "observations_v2_006.json")
    for cid, entry in obs["candidates"].items():
        assert entry["identity_receipt"]["identity_continuity"] == \
            "UNCHANGED"
        assert entry["spatial_qc"]["WORLD_CONTINUITY"]["verdict"] == \
            "FAIL"
    # no auto-accept: both refusals stand despite identity passing
    for entry in gov["candidates"]:
        assert entry["state"] in ("PROPOSED", "TECHNICALLY_VALID")


# RC-040..044 — review surface
def test_rc040_044_review_surface():
    manifest = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                        "owner_review_manifest_v2_006.json")
    assert manifest["pair_state"] == "REFUSED"
    segs = [s for s in manifest["segments"] if s["asset_sha256"]]
    assert [s["label"] for s in segs] == ["BASELINE F2", "NEW F2A",
                                          "NEW F2B"]
    template = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                        "owner_f2_pair_decision_v2_006.template.json")
    assert template["decision_options"][0] == "SELECT_F2A_F2B_PAIR"
    assert template["decision"] is None
    from build_v2_006_owner_surface import QUESTIONS
    assert len(QUESTIONS) == 7
    for name, info in manifest["review_copies"].items():
        assert file_sha(ROOT / "OWNER_REVIEW/V2_006" / name) == \
            info["sha256"]


# RC-045..049 — freeze/conformance
def test_rc045_049_freeze_conformance(freeze):
    a, b = freeze["candidates"]
    assert a["generation_semantic_identity"] != \
        b["generation_semantic_identity"]
    assert a["reference_binding"] != b["reference_binding"]
    for cand in freeze["candidates"]:
        assert cand["creative_body_chars"] <= 500
        assert cand["creative_body_words"] <= 74
    assert "sets himself" in a["creative_body"].lower()
    assert "behind" in b["creative_body"].lower()
    # F2B must not import the F2A near-side geography
    assert "near side" not in b["creative_body"].lower()


# RC-050..054 — model/custody
def test_rc050_054_model_custody():
    custody = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                       "custody_v2_006.json")
    assert custody["start_sha"] == "6af0e7490e985d859b7148fc1b25ffa60c4d5b72"
    assert custody["owner_authorization"][
        "AUTHORIZE_SPLIT_REFERENCE"] == "YES"
    assert "ONLY the reference-strategy amendment" in custody[
        "owner_authorization"]["scope"]
    plan5 = pkg_json("projects/quality_v2_005_f2_decomposition/"
                     "f2_decomposition_plan_v2_005.json")
    assert custody["bindings"]["frozen_f2a"]["blocking_spec_id"] == \
        plan5["f2a_commit_to_cross"]["blocking"]["blocking_spec_id"]
    amendment = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                         "split_reference_amendment_v2_006.json")
    assert amendment["uploads"] == 0
    assert amendment["identity_reference_bytes_verified"] is True


# RC-055..056 — technical
def test_rc055_056_technical():
    tech = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                    "technical_qc_v2_006.json")
    for cid in ("F2A", "F2B"):
        assert tech["shots"][cid]["full_decode"] is True
        assert tech["shots"][cid]["ffprobe"]["duration_s"] == 8.0


# RC-057..062 — pair gates recorded
def test_rc057_062_pair_gates_recorded(gov):
    assert gov["atomic_pair"]["pair_state"] == "REFUSED"
    obs = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                   "observations_v2_006.json")
    for cid, entry in obs["candidates"].items():
        for check, verdict in entry["spatial_qc"].items():
            assert verdict["verdict"] in ("PASS", "FAIL")
            assert verdict["evidence"]


# RC-063..064 — scene separation + windows
def test_rc063_064_scene_and_windows(freeze):
    assert (PKG / "scene_SCENE_F_FAR_SIDE").exists()
    assert (PKG / "scene_SCENE_F_STORM_GATE").exists()
    for cand in freeze["candidates"]:
        assert cand["editorial_target_duration"] == 2.8


# RC-065 — pair join provenance
def test_rc065_pair_join_provenance():
    tech = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                    "technical_qc_v2_006.json")
    pair_path = ROOT / tech["pair_join"]["path"]
    assert file_sha(pair_path) == tech["pair_join"]["sha256"]
    manifest = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                        "owner_review_manifest_v2_006.json")
    assert manifest["review_copies"]["NEW_F2_PAIR.mp4"]["sha256"] == \
        tech["pair_join"]["sha256"]


# RC-066..067 — no selection/promotion
def test_rc066_067_no_selection_promotion(gov):
    for entry in gov["candidates"]:
        assert "OWNER_SELECTED" not in json.dumps(entry)
    for p in PKG.glob("*ledger*.json"):
        assert "PROMOTION_COMMITTED" not in p.read_text(
            encoding="utf-8")


# RC-068..070 — QC structure
def test_rc068_070_qc_structure(gov):
    for entry in gov["candidates"]:
        assert entry["review_refusal"]["hard_fails"]
        assert entry["spatial_qc"] and entry["camera_qc"]


# RC-071..072 — ambiguity + presentation
def test_rc071_072_ambiguity_and_presentation():
    assert EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"
    ma = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                  "mutation_authority.json")
    assert ma["mutation_authority"] == "OPEN"
    gov_ = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                    "candidates_governance_v2_006.json")
    manifest = pkg_json("projects/quality_v2_006_f2_decomposed_live/"
                        "owner_review_manifest_v2_006.json")
    assert manifest["pair_state"] == gov_["atomic_pair"]["pair_state"]
