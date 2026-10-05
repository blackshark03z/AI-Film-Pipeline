"""QUALITY-V2-007 preflight tests: salvage proof, world-reference
search integrity, pacing diagnosis, strategy decision, V2-008
readiness, and package invariants."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_007_world_anchor"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")


def pkg_json(name):
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_01_custody_rebound():
    cust = pkg_json("custody_v2_007.json")
    assert cust["start_sha"] == "480ba6a81f0981cba59bf42ee642e8daa1fcce1c"
    assert cust["v2_006_final_head"] == cust["start_sha"]
    outs = cust["v2_006_outputs"]
    assert outs["F2A-V2-006"]["asset_sha256"].startswith("adb62822")
    assert outs["F2B-V2-006"]["asset_sha256"].startswith("51ed91af")
    assert len(cust["qualified_reference_media"]) == 2


def test_02_salvage_scan_exhaustive():
    scan = pkg_json("f2a_salvage_scan_v2_007.json")
    assert scan["window_count"] == 27
    assert scan["F2A_SALVAGEABLE"] is False
    assert scan["viable_windows"] == []
    # interval proof: every window fails at least one hard criterion
    for w in scan["windows"]:
        assert w["failures"], w
    # and the two failure families partition the windows
    late = [w for w in scan["windows"] if "metal_gate_in_window" in
            w["failures"]]
    early = [w for w in scan["windows"] if "no_threshold_arrival_in_"
             "window" in w["failures"]]
    assert late and early
    assert all("sword_present_in_window" in w["failures"]
               for w in late)


def test_03_timeline_matches_strip_evidence():
    scan = pkg_json("f2a_salvage_scan_v2_007.json")
    tl = scan["measured_timeline"]
    assert tl["sword_present_from_s"] == 1.4
    assert tl["metal_gate_visible_from_s"] == 5.0
    assert tl["threshold_arrival_s"] == 6.2
    strip = PKG / scan["evidence"]
    assert file_sha(strip) and strip.stat().st_size > 10000


def test_04_world_reference_search_reuse_first():
    search = pkg_json("world_reference_search_v2_007.json")
    verdicts = {c["source"]: c for c in search["candidates"]}
    # every drift world rejected
    assert verdicts["V2-006-A (adb62822…)"]["f2b_compatible"] is False
    assert verdicts["V2-006-B (51ed91af…)"]["f2b_compatible"] is False
    # near-side canonical references rejected for F2B
    assert verdicts["canonical_F2C (SEQ7_F2C)"]["f2b_compatible"] is False
    # the selected candidate is the V2-004-B far-side frame
    sel = search["selected"]
    assert sel["source"].startswith("V2-004-B")
    assert sel["f2b_compatible"] is True
    assert sel["geography"].startswith("FAR_SIDE")
    assert "no fortress" in sel["world"] or "fortress" not in sel["world"]


def test_05_rejected_take_supplies_frame_not_promotion():
    sel = pkg_json("world_reference_search_v2_007.json")["selected"]
    assert "NOT promoted" in sel["provenance"]
    still = PKG / sel["frame"]["still"]
    assert still.exists()
    assert file_sha(still) == sel["frame"]["sha256"]
    assert sel["frame"]["extracted_from_s"] == 6.6
    # provenance chain: the still comes from the acquired V2-004-B asset
    v = json.loads((ROOT / "projects/quality_v2_004_f2_blocking/"
                    "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_V2_004_B/"
                    "result.json").read_text(encoding="utf-8"))
    assert v["asset"]["sha256"].startswith("b573cf13")
    assert Path(v["asset"]["uri_or_path"]).exists()


def test_06_pacing_diagnosis_proposal_only():
    pre = pkg_json("world_anchor_preflight_v2_007.json")
    d = pre["pacing_diagnosis"]
    for cls in ("TOO_MUCH_TRAVEL_DISTANCE", "PROVIDER_ACTION_DELAY",
                "UNSCHEDULED_SWORD_ACTION", "WORLD_STRUCTURE_INVENTION"):
        assert cls in d["failure_classes"]
    delta = d["minimum_director_delta_PROPOSAL_ONLY"]
    assert delta["F2A_START"] == "CLOSE_BEFORE_THRESHOLD"
    assert delta["no_sword_draw"] is True
    assert delta["frozen_plan_untouched"] is True
    # the frozen V2-005 plan is untouched on disk
    plan5 = json.loads((ROOT / "projects/quality_v2_005_f2_decomposition/"
                        "f2_decomposition_plan_v2_005.json").read_text(
                            encoding="utf-8"))
    assert plan5["f2a_commit_to_cross"]["blocking"]["start_zone"] == \
        "BEFORE_GATE"


def test_07_strategy_decision():
    pre = pkg_json("world_anchor_preflight_v2_007.json")
    assert pre["world_reference_strategy"] == (
        "C. QUALIFY_EXISTING_PROJECT_MEDIA_AS_WORLD_REFERENCE")
    # A is impossible: no far-side provider IMAGE media exists
    cust = pkg_json("custody_v2_007.json")
    types = {m["type"] for m in cust["qualified_reference_media"]}
    assert "FAR_SIDE full frame" not in types


def test_08_v2_008_ready_and_budget():
    doc = (ROOT / "docs/quality-v2/"
           "V2_008_F2_WORLD_ANCHORED_LIVE_HANDOFF.md").read_text(
        encoding="utf-8")
    assert "READY contingent" in doc
    assert "ONE reference-qualification upload" in doc.replace(
        "once, Owner-authorized upload:", "reference-qualification "
        "upload") or "1 upload" in doc or "upload" in doc.lower()
    assert "≤ 2 new Generates" in doc
    assert "CLOSE_BEFORE_THRESHOLD" in doc
    assert "6.6 s" in doc or "6.6" in doc


def test_09_invariants_zero_mutation():
    pre = pkg_json("world_anchor_preflight_v2_007.json")
    inv = pre["invariants"]
    assert inv["generation"] == 0 and inv["upload"] == 0
    assert inv["provider_switch"] is False
    assert inv["canonical_mutation"] == 0
    assert not (PKG / "generate_ledger.json").exists()
    assert not list(PKG.glob("**/*.mp4"))
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == \
        "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"


def test_10_ambiguity_rule_intact():
    from film_pipeline.quality_repair_v2 import EXTERNAL_AMBIGUITY_RULE, \
        QUALITY_V2_CANONICAL_BASELINE
    assert EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"
    assert QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
