"""A layout label that names a state ("open ledger") is written verbatim into still and video prompts; when the
generation's continuity state says the opposite ("the ledger: lying closed"), the prompt contradicts itself (film08
SC03_g09 / SC12_g25, 2026-11-15). The plan warns LABEL_STATE_CONFLICT; it never blocks."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILM08 = ROOT / "films" / "film08_chain_of_custody"
needs_film08 = pytest.mark.skipif(not (FILM08 / "04_shots.json").is_file(), reason="film08 package not present")


def _planner():
    from film_pipeline.production.package import load_package
    from film_pipeline.production.plan import _Plan
    return _Plan(load_package(FILM08), None, None, None, frozenset())


def _decl_with_ledger(p, word):
    for g in p.shots.generations:
        for sid in (g.start_state, g.end_state):
            if any("ledger" in k.lower() and word in v.lower() for k, v in p.state(sid).props.items()):
                return g
    raise AssertionError(f"no film08 generation with a {word} ledger")


@needs_film08
def test_open_label_against_closed_state_warns():
    p = _planner()
    decl = _decl_with_ledger(p, "closed")
    issues = p.label_state_issues(decl, ["The open ledger is on the counter."])
    assert [(i.check, i.severity) for i in issues] == [("LABEL_STATE_CONFLICT", "WARN")]
    assert "'open ledger'" in issues[0].detail and decl.generation_id in issues[0].detail


@needs_film08
def test_no_warning_when_label_not_emitted_or_state_agrees():
    p = _planner()
    closed = _decl_with_ledger(p, "closed")
    assert p.label_state_issues(closed, ["The ledger is on the counter."]) == []
    opened = next(g for g in p.shots.generations
                  if all("closed" not in v.lower() for sid in (g.start_state, g.end_state)
                         for k, v in p.state(sid).props.items() if "ledger" in k.lower())
                  and any("ledger" in k.lower() for k, v in p.state(g.start_state).props.items()))
    assert p.label_state_issues(opened, ["The open ledger is on the counter."]) == []
