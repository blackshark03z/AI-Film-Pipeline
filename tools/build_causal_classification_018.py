"""FLOW-ACTION-INTENT-CAUSALITY-018 (Phase 14): causal effect
classification — candidates vs baselines, Q1-Q4 answered explicitly.
Judgments made against the dense grids + the blind packet answers.
"""
from __future__ import annotations

import json
from pathlib import Path

D17 = Path("projects/flow_performance_motion_canary_017")
D18 = Path("projects/flow_action_intent_causality_018")


def main() -> None:
    experiment = {
        "version": "action-causality-experiment-018-v1",
        "scope_limit": "classification applies ONLY within this "
                       "observed experiment (three submissions, two "
                       "shot families, one provider route); worker "
                       "judgments are advisory",
        "submissions": {"authorized": 3, "consumed": 3, "retries": 0,
                        "uploads": 0,
                        "note": "two earlier launches failed LOCALLY "
                                "(hook bug + stale-result short-circuit) "
                                "before any mutation; ledger stayed 0 "
                                "until the fixed run"},
        "findings": {
            "F2C-P018-A": {
                "classification": "CAUSAL_CONTROL_EFFECT_OBSERVED",
                "evidence": "the gust renders VISIBLY between the gate "
                            "stones (trigger), the drive reads as "
                            "passing through, and he emerges past the "
                            "gate (outcome); blind worker answer for "
                            "the clip matched trigger/goal/outcome; "
                            "identity stable",
                "vs_baseline": "goal+outcome go from unreadable to "
                               "readable"},
            "F2C-P018-B": {
                "classification": "PARTIAL_EFFECT",
                "evidence": "the reaction cue renders (arm-shield "
                            "brace into the blast) and the wind cause "
                            "is unmistakable, but the staging drifted "
                            "to bracing AT the rock rather than "
                            "driving THROUGH; through-state less clear "
                            "than A",
                "vs_baseline": "cause clearly readable; goal partially"},
            "G3C-P018-C": {
                "classification": "CAUSAL_CONTROL_EFFECT_OBSERVED "
                                  "(REACTION_CAUSALITY)",
                "evidence": "the exhale reads as release-of-effort "
                            "(closed mouth, softening jaw, visible "
                            "shoulder drop, eyes ease forward) instead "
                            "of the baseline's speech-like artifact; "
                            "the completed-arc trigger remains "
                            "context-dependent by framing (CU)",
                "vs_baseline": "reaction now matches the recovered "
                               "outcome; minor hair-pin drift flagged"},
            "F2C-P017-C (017 best, unchanged)": {
                "classification": "ACTION_STILL_AMBIGUOUS",
                "evidence": "motion natural, meaning unclear "
                            "(018 baseline review)"},
            "G3C-P017-D (017 best, unchanged)": {
                "classification": "ACTION_STILL_AMBIGUOUS "
                                  "(standalone)",
                "evidence": "release partially readable but its cause "
                            "is not in the frame"}},
        "questions": {
            "Q1_does_action_intent_improve_understanding": {
                "answer": "YES (within this experiment)",
                "evidence": "both causal-compiled F2 candidates and the "
                            "causal G3 candidate were read correctly by "
                            "the (contaminated) worker viewer on blind "
                            "structure, and the visible causal markers "
                            "(gust burst, through-emergence, shoulder "
                            "drop) are on the frames themselves; the "
                            "Owner's blind view is the deciding "
                            "authority"},
            "Q2_does_the_action_have_readable_purpose": {
                "answer": "F2C-P018-A: YES (through the gate, road "
                          "onward); F2C-P018-B: PARTIAL (pressing on "
                          "against the wind); G3C-P018-C: PARTIAL in CU "
                          "(release reads; what was completed needs the "
                          "G2 context the master cut already provides)"},
            "Q3_does_contact_or_reaction_cause_the_next_state": {
                "answer": "A: the gust visibly causes the drive and the "
                          "drive visibly produces the through-state; "
                          "C: the exhale visibly produces the settle; "
                          "B: the brace reads as reaction but its "
                          "through-outcome is less visible"},
            "Q4_remaining_problem_generation_quality_or_upstream": {
                "answer": "UPSTREAM_EDITORIAL_CONTEXT, not generation "
                          "quality and not missing architecture: G3's "
                          "trigger lives in G2 by design "
                          "(REQUIRES_PREVIOUS_SHOT_CONTEXT) and the "
                          "canonical master cut already supplies that "
                          "adjacency; F2's remaining gap is staging "
                          "choice variety, not capability"}},
        "identity_guard": "no material identity regression observed; "
                          "G3C-P018-C minor hair-pin drift flagged; "
                          "nothing promoted regardless",
        "advisory": "all classifications advisory; Owner decides from "
                    "the compare reel"}
    (D18 / "action_causality_experiment_018.json").write_text(
        json.dumps(experiment, indent=1), encoding="utf-8")
    print(json.dumps({"Q1": experiment["questions"]
                      ["Q1_does_action_intent_improve_understanding"]
                      ["answer"],
                      "findings": {k: v["classification"] for k, v in
                                   experiment["findings"].items()}}))


if __name__ == "__main__":
    main()
