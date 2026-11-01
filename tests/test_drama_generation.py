"""Scene -> 8 s generations, state chaining and sequential render gating."""
from __future__ import annotations

from pathlib import Path

import pytest

from film_pipeline.drama import (
    AxisBook, ContinuityState, CoveragePlanner, GenerationPlan,
    GenerationSpec, HandoffQC, parse_fountain, split_unit,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "drama" / \
    "sample_scene_vi.fountain"


def _state(letter: str) -> ContinuityState:
    return ContinuityState(positions={"MAI": "at the table, frame-left"},
                           props={"letter": letter},
                           looks={"MAI": "mai_kitchen"})


START = _state("folded in MAI's hand")
MID = _state("torn pieces on the table")
END = _state("pocketed")


@pytest.fixture()
def unit16():
    script = parse_fountain(FIXTURE.read_text(encoding="utf-8"))
    scene = script.scenes[0]
    unit = CoveragePlanner().plan(
        scene, AxisBook.for_pair(scene.scene_id, "MAI", "HÙNG"))
    base = unit.shots[0]
    marks = [(0.0, 3.0), (3.0, 8.0), (8.0, 11.5), (11.5, 16.0)]
    shots = [base.model_copy(update={"shot_id": f"S{i}", "start_s": a,
                                     "end_s": b})
             for i, (a, b) in enumerate(marks, 1)]
    return unit.model_copy(update={"shots": shots, "duration_s": 16.0})


def _plan(unit16, mid_start=MID) -> GenerationPlan:
    g1, g2 = split_unit(unit16)
    return GenerationPlan(scene_id=unit16.scene_id, generations=[
        GenerationSpec(generation_id="SC01_g1", index=1, unit=g1,
                       action="tear", start_state=START, end_state=MID),
        GenerationSpec(generation_id="SC01_g2", index=2, unit=g2,
                       action="pocket", start_state=mid_start,
                       end_state=END)])


def test_split_rebases_marks_per_window(unit16):
    g1, g2 = split_unit(unit16)
    assert [(s.start_s, s.end_s) for s in g1.shots] == [(0, 3), (3, 8)]
    assert [(s.start_s, s.end_s) for s in g2.shots] == [(0, 3.5),
                                                        (3.5, 8)]
    assert g1.duration_s == g2.duration_s == 8.0
    assert g2.timing_problems() == []


def test_split_rejects_straddling_shot_and_odd_duration(unit16):
    shots = list(unit16.shots)
    shots[1] = shots[1].model_copy(update={"end_s": 9.0})
    with pytest.raises(ValueError, match="straddles"):
        split_unit(unit16.model_copy(update={"shots": shots}))
    with pytest.raises(ValueError, match="multiple"):
        split_unit(unit16.model_copy(update={"duration_s": 15.0}))


def test_plan_reports_state_chain_mismatch_by_key(unit16):
    assert _plan(unit16).problems() == []
    bad = _plan(unit16, mid_start=_state("folded in MAI's hand"))
    assert bad.problems() == ["SC01_g2: start_state.props != SC01_g1 "
                              "end_state.props"]


def test_plan_reports_bad_indices_and_duplicate_ids(unit16):
    plan = _plan(unit16)
    plan.generations[1].index = 3
    plan.generations[1].generation_id = "SC01_g1"
    problems = plan.problems()
    assert any("duplicate" in p for p in problems)
    assert any("indices" in p for p in problems)


def test_dispatch_is_gated_on_verified_qc(unit16):
    plan = _plan(unit16)
    assert plan.dispatchable(1, {})
    assert not plan.dispatchable(2, {})
    qc = HandoffQC.from_end_state("SC01_g1", "SC01_g2", MID)
    assert not plan.dispatchable(2, {"SC01_g1": qc})     # all PENDING
    qc.reviewer = "Owner"
    for check in qc.checks:
        qc.review(check.item, "PASS")
    assert plan.dispatchable(2, {"SC01_g1": qc})


def test_handoff_for_follows_qc(unit16):
    plan = _plan(unit16)
    assert plan.handoff_for(1, None) is None
    unverified = plan.handoff_for(2, None)
    assert unverified.end_state_verified is False
    assert unverified.previous_end == MID
    qc = HandoffQC.from_end_state("SC01_g1", "SC01_g2", MID)
    qc.reviewer = "Owner"
    for check in qc.checks:
        qc.review(check.item, "PASS")
    assert plan.handoff_for(2, qc).end_state_verified is True
