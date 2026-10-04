"""FLOW-ACTION-INTENT-CAUSALITY-018 (Phases 3-5, 8-9): causality graph,
per-shot legibility/observability records, baseline MEANING review, and
the generation decision.

Meaning review distinguishes MOTION_NATURALNESS (017 territory, frozen
there) from ACTION_MEANING (this package). Every judgment below was
made against the dense frame grids and side-by-side stills on disk from
Package-017 (no new viewing medium needed — the same frames are the
evidence).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.action_intent import (
    ActionIntent, build_shot_causality_graph, check_causal_legibility,
    classify_causal_complexity, classify_observability)

D17 = ROOT / "projects/flow_performance_motion_canary_017"
D18 = ROOT / "projects/flow_action_intent_causality_018"

F2_INTENT = ActionIntent(
    trigger="a hard gust funnels hard (through the rock gate)",
    perception="the funneled wind hits him inside the gate",
    character_goal="the road onward (through the gate)",
    motivation="the storm front is the obstacle; the road continues beyond",
    obstacle_or_pressure="wind direction constant against him",
    chosen_action="he drives a step through the funnel",
    intended_outcome="he breaks through the worst gust",
    resulting_state="the effort shows and is held",
    next_decision="the cost is held at the rock wall (F3)",
    visual_legibility_requirements=[
        "the gate contact pushes the drive onward"])
G3_INTENT = ActionIntent(
    trigger="the draw's arc completed (G2)",
    perception="the effort leaving the body",
    character_goal="release the effort",
    motivation="resolution: one clean answer, then the road again",
    obstacle_or_pressure="",
    chosen_action="one long exhale; shoulders settle",
    intended_outcome="face at rest, eyes forward",
    resulting_state="the faintest ease",
    next_decision="the walk resumes (G4)")


def main() -> None:
    # Phase 3+4: legibility + observability of the recovered intents
    f2_leg = check_causal_legibility(F2_INTENT, contact_present=True)
    f2_obs = classify_observability(F2_INTENT, trigger_visible_in_frame=True,
                                    framing="MS")
    g3_leg = check_causal_legibility(G3_INTENT, contact_present=False)
    g3_obs = classify_observability(G3_INTENT,
                                    trigger_visible_in_frame=False,
                                    framing="CU")
    # Phase 5: causality graph (state-change invariant enforced)
    graph = build_shot_causality_graph([
        {"previous_shot": "SEQ7_F1",
         "target_shot": "SEQ7_F2",
         "following_shot": "SEQ7_F3",
         "incoming_world_state": "close to the rock gate, leaning "
                                 "(F1 end state)",
         "character_knowledge_state": "feels the storm funnel through "
                                      "the gate",
         "character_goal": F2_INTENT.character_goal,
         "action": F2_INTENT.chosen_action,
         "outcome": F2_INTENT.intended_outcome,
         "outgoing_world_state": "pressed near the rock wall (F3 start "
                                 "state)",
         "outcome_alters_state": True},
        {"previous_shot": "SEQ7_G2",
         "target_shot": "SEQ7_G3",
         "following_shot": "SEQ7_G4",
         "incoming_world_state": "sword sheathed; hands settling (G2 end "
                                 "state)",
         "character_knowledge_state": "the arc is complete; the effort "
                                      "leaves the body",
         "character_goal": G3_INTENT.character_goal,
         "action": G3_INTENT.chosen_action,
         "outcome": G3_INTENT.intended_outcome,
         "outgoing_world_state": "the walk resumes (G4 start state)",
         "outcome_alters_state": True,
         "maintains_state_intentionally": False}])

    # Phase 7: causal complexity of the targets
    f2_cx = classify_causal_complexity(F2_INTENT, locomotion=True,
                                       interaction=True)
    g3_cx = classify_causal_complexity(G3_INTENT, locomotion=False,
                                       interaction=False)

    # Phase 8: baseline MEANING review (motion naturalness frozen in 017)
    baseline = {
        "version": "baseline-action-legibility-018-v1",
        "distinction": "MOTION_NATURALNESS was 017's question and stays "
                       "frozen there; this review judges ACTION_MEANING "
                       "only",
        "review_basis": "Package-017 dense frame grids + side-by-side "
                        "stills (same frames, same evidence)",
        "rows": {
            "F2C (canonical)": {
                "MOTION_NATURALNESS": "stiff/glide-like (017 finding, "
                                      "unchanged)",
                "ACTION_MEANING": {
                    "trigger_read": "PARTIAL (robes/hair blow, but the "
                                    "funneling gust itself is not "
                                    "established in the waist-up frame)",
                    "goal_read": "NO (the drive reads as generic "
                                 "struggle; direction and purpose "
                                 "unclear)",
                    "contact_function_read": "NO (hand to rock reads as "
                                             "balance, not as pushing "
                                             "through)",
                    "outcome_read": "NO (window ends mid-gust; no "
                                    "through-state)",
                    "legibility": "NOT_LEGIBLE (goal and outcome "
                                  "absent; trigger partial)"},
                "viewer_answer": "a man struggles in wind at rocks; WHY "
                                 "and TO WHAT END stay unclear"},
            "F2C-P017-B": {
                "MOTION_NATURALNESS": "materially improved (017)",
                "ACTION_MEANING": {
                    "trigger_read": "PARTIAL (wind visible via robes)",
                    "goal_read": "PARTIAL (dynamic movement through the "
                                 "gate area, purpose still generic)",
                    "contact_function_read": "NO (gate contact not "
                                             "restaged)",
                    "outcome_read": "NO",
                    "legibility": "PARTIALLY_LEGIBLE"},
                "viewer_answer": "an urgent run through rocks; why is "
                                 "still guesswork"},
            "F2C-P017-C": {
                "MOTION_NATURALNESS": "materially improved (017)",
                "ACTION_MEANING": {
                    "trigger_read": "PARTIAL",
                    "goal_read": "PARTIAL (pushing onward past the "
                                 "gate)",
                    "contact_function_read": "PARTIAL (hand on rock "
                                             "reads as pushing off)",
                    "outcome_read": "NO (no clear through-state)",
                    "legibility": "PARTIALLY_LEGIBLE (best of the F2 "
                                  "surfaces)"},
                "viewer_answer": "he pushes past the rocks in wind; "
                                 "whether he succeeds stays unclear"},
            "G3C (canonical)": {
                "MOTION_NATURALNESS": "static torso; mouth artifact "
                                      "(017 finding)",
                "ACTION_MEANING": {
                    "trigger_read": "NO (the G2 arc is not in frame; "
                                    "nothing signals completion)",
                    "goal_read": "NO (reads as speech-like mouth "
                                 "opening)",
                    "contact_function_read": "NO contact",
                    "outcome_read": "NO",
                    "legibility": "NOT_LEGIBLE standalone"},
                "viewer_answer": "a man opens his mouth slightly; the "
                                 "release is unreadable"},
            "G3C-P017-D": {
                "MOTION_NATURALNESS": "improved (mouth closed; settle "
                                      "subtle)",
                "ACTION_MEANING": {
                    "trigger_read": "NO (no in-frame completion cue)",
                    "goal_read": "PARTIAL (a quiet release reads, but "
                                 "of WHAT is unknown)",
                    "contact_function_read": "NO contact",
                    "outcome_read": "PARTIAL (face eases)",
                    "legibility": "PARTIALLY_LEGIBLE "
                                  "(context-dependent)"},
                "viewer_answer": "a quiet exhale; why he exhales is not "
                                 "in the frame"}
        }
    }

    # Phase 9: the generation decision
    decision = {
        "version": "generation-decision-018-v1",
        "existing_candidates_sufficient": False,
        "reason": ("no existing surface conveys the recovered intent: "
                   "F2 family lacks a readable goal/outcome; the G3 "
                   "family cannot show release-of-effort causally; "
                   "prompt/shot control can reasonably improve both "
                   "(the causal chain fits the qualified envelope)"),
        "authorized": {"max_new_generates": 3,
                       "candidates": ["F2C-P018-A", "F2C-P018-B",
                                      "G3C-P018-C"]}}
    if decision["existing_candidates_sufficient"]:
        decision["classification"] = "EXISTING_CANDIDATE_CAUSALLY_SUFFICIENT"
    else:
        decision["classification"] = "CANARY_REQUIRED_WITHIN_BUDGET"

    out = {"version": "causal-review-018-v1",
           "legibility_contracts": {
               "F2": {**f2_leg, "observability": f2_obs,
                      "causal_complexity": f2_cx},
               "G3": {**g3_leg, "observability": g3_obs,
                      "causal_complexity": g3_cx}},
           "shot_causality_graph": graph,
           "baseline_action_legibility": baseline,
           "generation_decision": decision}
    (D18 / "baseline_action_legibility_018.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    # the graph is also frozen standalone as required
    (D18 / "shot_causality_graph_018.json").write_text(
        json.dumps(graph, indent=1), encoding="utf-8")
    print(json.dumps({"F2_legibility": f2_leg["legibility"],
                      "G3_legibility": g3_leg["legibility"],
                      "F2_observability": f2_obs["observability"],
                      "G3_observability": g3_obs["observability"],
                      "decision": decision["classification"]}))


if __name__ == "__main__":
    main()
