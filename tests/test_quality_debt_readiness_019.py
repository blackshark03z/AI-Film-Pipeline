"""Quality debt + readiness axes invariants (Package-019 V4-V5)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from film_pipeline.quality_debt import (QualityDebtItem, ReadinessAxes,
                                        validate_debt_cannot_satisfy_release_gates)

ROOT = Path(__file__).resolve().parents[1]
D19 = ROOT / "projects/flow_v1_completion_quality_debt_freeze_019"


def make_debt(**kw) -> QualityDebtItem:
    base = dict(
        project="swordsman_film", scope="SEQ7_F2", category="TEST",
        affected_canonical_artifacts=["SEQ7_F2"],
        observed_problem="x", owner_assessment="NEEDS_REDESIGN",
        current_impact="y", known_evidence=["e"],
        attempts_already_performed=["a"], what_improved="i",
        what_remains_unresolved="u",
        release_impact="gates stay blocked",
        future_track="AI_FILM_QUALITY_HARDENING_V2")
    base.update(kw)
    return QualityDebtItem(**base)


def test_01_debt_item_parse_and_digest():
    debt = make_debt(debt_id="QD-099")
    assert debt.status == "ACTIVE"
    assert debt.accepted_for_technical_completion is True
    assert debt.digest() == debt.digest()


def test_02_debt_cannot_satisfy_release_gates():
    debt = make_debt(debt_id="QD-098")
    gates = {"OWNER_TAKE_REVIEW": False, "SEMANTIC_RELEASE": False}
    out = validate_debt_cannot_satisfy_release_gates(debt, gates)
    assert out["gates"]["OWNER_TAKE_REVIEW"] is False
    with pytest.raises(ValueError, match="may not satisfy"):
        validate_debt_cannot_satisfy_release_gates(
            debt, {"OWNER_TAKE_REVIEW": True})


def test_03_registry_frozen_with_five_items_and_rule():
    registry = json.loads((D19 / "quality_debt_registry_019.json")
                          .read_text(encoding="utf-8"))
    assert registry["count"] == 5
    assert [i["debt_id"] for i in registry["items"]] == [
        "QD-001", "QD-002", "QD-003", "QD-004", "QD-005"]
    assert "may NOT silently satisfy" in registry["rule"]
    for i in registry["items"]:
        assert i["status"] == "ACTIVE"
        assert i["accepted_for_technical_completion"] is True
        assert i["future_track"] == "AI_FILM_QUALITY_HARDENING_V2"


def test_04_readiness_axes_current_truth():
    axes = ReadinessAxes(
        project="swordsman_film", pipeline_technical_ready=True,
        film_creative_quality_accepted=False,
        final_content_release_ready=False,
        content_gates={"OWNER_TAKE_REVIEW": False,
                       "SEMANTIC_RELEASE": False,
                       "PRODUCTION_NARRATION": False,
                       "TIMED_CAPTIONS": False},
        derived_from="flow_v1_completion_quality_debt_freeze_019")
    assert axes.pipeline_technical_ready is True
    assert axes.film_creative_quality_accepted is False


def test_05_false_aggregate_ready_refused():
    with pytest.raises(ValueError, match="false aggregate"):
        ReadinessAxes(
            project="p", pipeline_technical_ready=False,
            film_creative_quality_accepted=False,
            final_content_release_ready=True,
            content_gates={}, derived_from="test")


def test_06_creative_acceptance_implies_technical_refused():
    with pytest.raises(ValueError, match="creative acceptance"):
        ReadinessAxes(
            project="p", pipeline_technical_ready=False,
            film_creative_quality_accepted=True,
            final_content_release_ready=False,
            content_gates={}, derived_from="test")


def test_07_content_ready_does_not_imply_creative_accepted():
    # a hypothetical all-gates-satisfied state must NOT flip the
    # creative axis automatically — the axes are independent inputs
    axes = ReadinessAxes(
        project="p", pipeline_technical_ready=True,
        film_creative_quality_accepted=False,
        final_content_release_ready=False,
        content_gates={"OWNER_TAKE_REVIEW": True,
                       "SEMANTIC_RELEASE": True,
                       "PRODUCTION_NARRATION": True,
                       "TIMED_CAPTIONS": True},
        derived_from="synthetic")
    assert axes.film_creative_quality_accepted is False
    assert axes.final_content_release_ready is False


def test_08_technical_ready_does_not_imply_creative_accepted():
    axes = ReadinessAxes(
        project="swordsman_film", pipeline_technical_ready=True,
        film_creative_quality_accepted=False,
        final_content_release_ready=False, content_gates={},
        derived_from="flow_v1_completion_quality_debt_freeze_019")
    # the V1 completion does not make the film accepted
    assert not (axes.pipeline_technical_ready and
                axes.film_creative_quality_accepted)
