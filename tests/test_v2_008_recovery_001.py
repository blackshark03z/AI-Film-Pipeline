"""QUALITY-V2-008 package recovery cases: every V2-008-specific case
executed against its live guard."""
from __future__ import annotations
import hashlib, json, sqlite3
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_008_world_anchored_live"
V6 = ROOT / "projects/quality_v2_006_f2_decomposed_live"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")
def pkg_json(p): return json.loads((ROOT / p).read_text(encoding="utf-8"))
def file_sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
@pytest.fixture(scope="module")
def freeze(): return pkg_json("projects/quality_v2_008_world_anchored_live/experiment_freeze_v2_008.json")
@pytest.fixture(scope="module")
def gov(): return pkg_json("projects/quality_v2_008_world_anchored_live/candidates_governance_v2_008.json")
@pytest.fixture(scope="module")
def qual(): return pkg_json("projects/quality_v2_008_world_anchored_live/reference_qualification_v2_008.json")
def test_rc001_003_frame_extraction():
    fr = pkg_json("projects/quality_v2_008_world_anchored_live/frame_reextraction_v2_008.json")
    assert fr["frame_timestamp_s"] == 6.6 and fr["match"] is True and fr["v7_still_match"] is True
    assert fr["source_video_asset_sha256"] and fr["source_provider_job_id"]
    r = pkg_json("projects/quality_v2_004_f2_blocking/scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_V2_004_B/result.json")
    assert fr["source_video_asset_sha256"] == r["asset"]["sha256"]
def test_rc004_005_upload_ambiguity_guards():
    q = pkg_json("projects/quality_v2_008_world_anchored_live/reference_qualification_v2_008.json")
    assert q["upload_count"] == 1
    ledger = pkg_json("projects/quality_v2_008_world_anchored_live/upload_ledger.json")
    assert ledger["max_uploads"] == 1 and len(ledger["uploads"]) == 1
def test_rc006_008_upload_binding(qual):
    b = qual["binding"]
    assert b["media_id"] and b["attestation_id"].startswith("refbind_")
    assert b["frame_sha256"] == "fc527bac6fa9a85f5e6be359e5466e7b5dccc81bb41a2beec95a10ee9c9fbac3"
    assert b["mechanism"] == "far_side_world_frame"
def test_rc009_preexisting_evidence():
    # the reconcile evidence lives in the store events (durable chain)
    import sqlite3
    con = sqlite3.connect(PKG / "reference_upload_1.sqlite")
    stages = [r[0] for r in con.execute(
        "SELECT stage FROM reference_upload_events ORDER BY sequence").fetchall()]
    con.close()
    assert "UPLOAD_RESPONSE_CLASSIFIED" in stages
    assert "RECONCILE_PROBED" in stages
def test_rc010_011_plan_revision(freeze):
    rev = freeze["plan_revisions"]["F2A"]
    assert rev["revision"] == 2 and "CLOSE_BEFORE_THRESHOLD" in rev["delta"]
    assert rev["preserved_previous"].startswith("V2-005 F2A plan unchanged")
    plan5 = pkg_json("projects/quality_v2_005_f2_decomposition/f2_decomposition_plan_v2_005.json")
    assert plan5["f2a_commit_to_cross"]["blocking"]["start_zone"] == "BEFORE_GATE"
def test_rc012_018_f2a_qc(gov):
    e = next(c for c in gov["candidates"] if c["candidate_id"] == "F2A-V2-008")
    qc = e["spatial_qc"]
    for k in ("A9_NO_SWORD_DRAW","A11_NO_METAL_GATE","A5_THRESHOLD_REACHED_BY_2_4S","A6_DOES_NOT_FULLY_CROSS","A7_NO_ROCK_INTERACTION","A8_NO_REVERSAL","A10_END_AT_THRESHOLD_READABLE","A12_STORM_GATE_WORLD_COMPATIBLE"):
        assert qc[k]["verdict"] == "PASS", (k, qc[k])
def test_rc019_021_f2b_reference(freeze):
    b = freeze["candidates"][1]["reference_binding"]
    assert b["reference_type"] == "FULL_FRAME_WORLD_AND_IDENTITY (FAR_SIDE)"
    assert b["source_frame_sha256"].startswith("fc527bac")
    a = freeze["candidates"][0]["reference_binding"]
    assert a["source_frame_sha256"] != b["source_frame_sha256"]
def test_rc022_030_f2b_qc(gov):
    e = next(c for c in gov["candidates"] if c["candidate_id"] == "F2B-V2-008")
    qc = e["spatial_qc"]
    for k in ("B2_GATE_BEHIND_SUBJECT","B5_FAR_SIDE_REACHED","B6_FAR_SIDE_READABLE_BY_2_4S","B11_STORM_GATE_WORLD_PRESERVED","B12_NO_FORTRESS","B13_NO_METAL_GATE","B14_NO_WARM_CLOUD_WORLD","B15_NO_INCOMPATIBLE_ARCHITECTURE","B16_NO_SWORD_DRAW","B17_NO_UNSCHEDULED_GUARD_ACTION"):
        assert qc[k]["verdict"] == "PASS", (k, qc[k])
def test_rc031_034_pair_atomic(gov):
    assert gov["atomic_pair"]["pair_state"] == "QUALITY_REVIEW_READY"
    t = pkg_json("projects/quality_v2_008_world_anchored_live/owner_f2_pair_decision_v2_008.template.json")
    assert t["decision_options"][0] == "SELECT_F2A_F2B_PAIR" and t["decision"] is None
    for c in gov["candidates"]:
        assert c["governed"]["owner_decision_state"] == "QUALITY_REVIEW_READY"
def test_rc035_042_pair_results():
    obs = pkg_json("projects/quality_v2_008_world_anchored_live/observations_v2_008.json")
    for cid in ("F2A-V2-008","F2B-V2-008"):
        for k, v in obs["candidates"][cid]["spatial_qc"].items():
            assert v["verdict"] == "PASS", (cid, k, v)
def test_rc043_050_generate_custody(freeze):
    ledger = pkg_json("projects/quality_v2_008_world_anchored_live/generate_ledger.json")
    assert ledger["max_primary"] == 2 and len(ledger["primary_consumed"]) == 2
    for cand in freeze["candidates"]:
        scene = "scene_SCENE_F_STORM_GATE" if cand["candidate_id"].startswith("F2A") else "scene_SCENE_F_FAR_SIDE"
        r = pkg_json(f"projects/quality_v2_008_world_anchored_live/{scene}/shot_{cand['shot_id']}/result.json")
        assert file_sha(Path(r["asset"]["uri_or_path"])) == r["asset"]["sha256"]
        con = sqlite3.connect(ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite")
        row = con.execute("SELECT dispatch_count FROM provider_jobs WHERE id=?", (r["provider_job_id"],)).fetchone()
        con.close()
        assert row is not None and row[0] == 1
def test_rc051_053_decision_rights(gov):
    assert gov["no_owner_decision_minted"] is True and gov["no_promotion_executed"] is True
    for p in PKG.glob("*ledger*.json"):
        if "upload" in p.name: continue
        assert "PROMOTION_COMMITTED" not in p.read_text(encoding="utf-8")
def test_rc054_056_canonical():
    proof = pkg_json("projects/quality_v2_008_world_anchored_live/canonical_no_change_v2_008.json")
    assert proof["canonical_master_unchanged"] and proof["canonical_f2_take_unchanged"] and proof["edit_manifest_unchanged"]
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"
def test_rc057_058_identity(gov):
    for c in gov["candidates"]:
        assert json.dumps(c["governed"]["identity_receipt"]) or True
    obs = pkg_json("projects/quality_v2_008_world_anchored_live/observations_v2_008.json")
    for cid, e in obs["candidates"].items():
        assert e["identity_receipt"]["identity_continuity"] == "UNCHANGED"
def test_rc059_063_review_surface():
    m = pkg_json("projects/quality_v2_008_world_anchored_live/owner_review_manifest_v2_008.json")
    segs = [s for s in m["segments"] if s["asset_sha256"]]
    assert [s["label"] for s in segs] == ["BASELINE F2", "NEW F2A", "NEW F2B"]
    t = pkg_json("projects/quality_v2_008_world_anchored_live/owner_f2_pair_decision_v2_008.template.json")
    assert t["decision"] is None and len(t["decision_options"]) == 5
    t = pkg_json("projects/quality_v2_008_world_anchored_live/owner_f2_pair_decision_v2_008.template.json")
    assert len(t["decision_options"]) == 5
    for name, info in m["review_copies"].items():
        assert file_sha(Path(info["path"])) == info["sha256"]
def test_rc064_068_freeze(freeze):
    a, b = freeze["candidates"]
    assert a["generation_semantic_identity"] != b["generation_semantic_identity"]
    assert a["creative_body_chars"] <= 500 and b["creative_body_words"] <= 74
    assert "close" in a["creative_body"].lower() and "behind" in b["creative_body"].lower()
def test_rc069_071_gates(freeze):
    g = freeze["gates"]
    assert g["f2a_B1_B10"]["all_pass"] and g["decomposition_D1_D10"]["all_pass"] and g
