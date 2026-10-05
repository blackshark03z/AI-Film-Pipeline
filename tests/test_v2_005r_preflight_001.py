"""QUALITY-V2-005R reference-compatibility preflight tests: mechanical
classification, the far-side conflict rule, the amended strategy, the
atomic-pair decision contract, and the package invariants."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from reference_preflight_v2_005r import (
    BOUND_REF, BOUND_REF_SHA, IDENTITY_REF, IDENTITY_REF_SHA,
    classify_reference, environment_correlation,
    far_side_geography_conflict)

from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, EXTERNAL_AMBIGUITY_RULE,
    QUALITY_V2_CANONICAL_BASELINE)

PKG = ROOT / "projects/quality_v2_005r_reference_preflight"
V6 = ROOT / "projects/quality_v2_006_f2_decomposed_live"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010")

NEAR_SIDE_VISUAL = ("full scene: the gate rock slab at frame-left, the "
                    "subject standing beside it at the gate mouth on "
                    "the NEAR side, camera viewing from the near side, "
                    "far side occluded by the rock; no gate geography "
                    "beyond it is visible")
IDENTITY_VISUAL = ("chest_up_portrait: full scene is clouds and distant "
                   "peaks only; no gate geography anywhere in frame")


def pkg_json(name):
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_01_custody_pinned_exact_head():
    custody = pkg_json("custody_v2_005r.json")
    assert custody["v2_005_final_head"] == \
        "b92e03710d5aec6a48527b4fc24c4ef35deb41c7"
    assert custody["bound_reference"]["asset_sha256"] == BOUND_REF_SHA
    plan5 = json.loads((ROOT / "projects/quality_v2_005_f2_decomposition/"
                        "f2_decomposition_plan_v2_005.json").read_text(
                            encoding="utf-8"))
    assert custody["f2a_blocking_spec_id"] == \
        plan5["f2a_commit_to_cross"]["blocking"]["blocking_spec_id"]
    assert custody["f2b_blocking_spec_id"] == \
        plan5["f2b_emerge_far_side"]["blocking"]["blocking_spec_id"]


def test_02_reference_classified_from_actual_bytes():
    ref = pkg_json("reference_classification_v2_005r.json")
    assert ref["classification"]["sha256"] == BOUND_REF_SHA
    assert ref["classification"]["reference_type"] == \
        "FULL_FRAME_ENVIRONMENTAL"
    assert ref["classification"]["dimensions"] == [1280, 720]
    assert ref["visual_read"]["encodes_near_side_geography"] is True
    assert ref["visual_read"]["far_side_visible"] is False
    assert ref["materially_constrains_camera_geography"] is True
    assert ref["environment_correlation_vs_canonical_f2c_first_frame"] \
        > 0.5


def test_03_full_frame_near_side_reference_conflicts_with_far_side():
    cls = classify_reference(BOUND_REF, expected_sha=BOUND_REF_SHA,
                             subject_extent=NEAR_SIDE_VISUAL)
    out = far_side_geography_conflict(
        cls, environment_correlation(BOUND_REF, BOUND_REF),
        {"encodes_near_side_geography": True})
    assert out["conflict"] is True


def test_04_identity_only_reference_accepted_for_far_side():
    cls = classify_reference(IDENTITY_REF, expected_sha=IDENTITY_REF_SHA,
                             subject_extent=IDENTITY_VISUAL)
    assert cls["reference_type"] == "IDENTITY_ONLY"
    out = far_side_geography_conflict(
        cls, 0.1, {"encodes_near_side_geography": False})
    assert out["conflict"] is False


def test_05_unknown_reference_type_is_inconclusive():
    cls = classify_reference(BOUND_REF, expected_sha=BOUND_REF_SHA,
                             subject_extent="an unclassifiable frame")
    assert cls["reference_type"] == "UNKNOWN"
    out = far_side_geography_conflict(cls, 0.8, {"encodes_near_side_"
                                                 "geography": True})
    assert out["conflict"] is None


def test_06_missing_exact_asset_sha_refused():
    cls = classify_reference(BOUND_REF, expected_sha="f" * 64,
                             subject_extent=NEAR_SIDE_VISUAL)
    assert cls["reference_type"] == "UNKNOWN"
    assert "sha mismatch" in cls["reason"]


def test_07_reference_camera_contradiction_recorded():
    compat = pkg_json("compatibility_v2_005r.json")
    # F2B requires gate-behind / BEFORE_GATE forbidden; the bound
    # near-side reference contradicts exactly that
    assert compat["F2B_REFERENCE_COMPATIBLE_with_bound_full_frame"] \
        is False
    assert compat["F2A_REFERENCE_COMPATIBLE"] is True
    assert compat["F2B_REFERENCE_COMPATIBLE_with_identity_only"] is True


def test_08_decision_is_conflict_and_v2_006_not_ready():
    preflight = pkg_json("reference_preflight_v2_005r.json")
    assert preflight["status"] == "F2B_REFERENCE_GEOGRAPHY_CONFLICT"
    assert preflight["v2_006_ready"] is False
    assert preflight["invariants"]["generation"] == 0
    assert preflight["invariants"]["flow_submit"] == 0
    assert preflight["invariants"]["upload"] == 0
    assert preflight["invariants"]["provider_switch"] is False
    assert preflight["invariants"]["canonical_mutation"] == 0


def test_09_amended_strategy_reuses_qualified_identity_reference():
    preflight = pkg_json("reference_preflight_v2_005r.json")
    amendment = preflight["reference_strategy_amendment_for_v2_006"]
    assert amendment["F2A_reference"]["sha256"] == BOUND_REF_SHA
    assert amendment["F2B_reference"]["sha256"] == IDENTITY_REF_SHA
    assert amendment["F2B_reference"]["media_id"] == \
        "7b725f7b-4da5-4455-a6f2-135c4ba22397"
    assert amendment["uploads_required"] == 0
    assert amendment["provider_switch"] is False
    assert preflight["smallest_next_qualification"][
        "requires_owner_authorization"] is True
    # the identity reference really is already qualified: provenance in
    # the durable store with the exact sha
    assert file_sha(IDENTITY_REF) == IDENTITY_REF_SHA


def test_10_atomic_pair_decision_contract():
    template = json.loads((V6 /
                           "owner_decision_template_v2_006.template.json")
                          .read_text(encoding="utf-8"))
    assert template["decision_options"] == ["SELECT_F2A_F2B_PAIR",
                                            "REJECT_ALL", "KEEP_CANONICAL",
                                            "NEEDS_REPAIR", "DEFER"]
    assert template["removed_options"] == ["SELECT_A (alone)",
                                           "SELECT_B (alone)"]
    assert template["decision"] is None
    assert "no option selects F2A alone" in \
        template["atomic_pair_contract"]
    handoff = (ROOT / "docs/quality-v2/"
               "V2_006_F2_DECOMPOSED_LIVE_HANDOFF.md").read_text(
                   encoding="utf-8")
    assert "V2_006_READY = false" in handoff
    assert "SELECT_F2A_F2B_PAIR" in handoff
    assert "SELECT_A (alone)" not in handoff.split("Decision options")[1]


def test_11_invariants_canonical_and_ambiguity():
    assert file_sha(MASTER / "master_editorial_010_v1.mp4") == \
        CANONICAL_MASTER_SHA256
    assert QUALITY_V2_CANONICAL_BASELINE == \
        "14ba281d12c15a5678a3fe1b3f0242f577512e5f"
    assert EXTERNAL_AMBIGUITY_RULE == "OWNER_AMBIGUITY_GATE"
    assert not (PKG / "generate_ledger.json").exists()
    assert not list(PKG.glob("**/*.mp4"))  # no render, no reel here
