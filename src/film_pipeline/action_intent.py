"""Action-intent causal layer (Package-018).

EXTENDS existing truth; never parallels it:

- ActionIntent (core.py, optional ShotSpec field, legacy-identity
  stable) — why the character acts now and to what end; every field
  must be recoverable from authoritative upstream truth.
- Causal legibility contract: deterministic checks over the intent +
  observability classification (an editorial/narrative contract, NOT
  semantic-model authority — nothing here scores a video).
- Shot causality graph: previous -> target -> following with explicit
  edge states; the target action must alter a relevant state or
  intentionally maintain one.
- Causal complexity: extends the 017 physical classifier with causal
  beats (trigger/decision/locomotion/interaction/reaction/recovery);
  too many beats in one short generation recommends SPLIT_NARRATIVE_BEAT
  / INSERT_REACTION_SHOT / ESTABLISH_TRIGGER — advisory only.
"""
from __future__ import annotations

from .core import ActionIntent, canonical_json, sha256

LEGIBILITY_CHECKS = (
    "TRIGGER_VISIBLE_OR_CONTEXTUALLY_ESTABLISHED",
    "GOAL_INFERABLE",
    "ACTION_SERVES_GOAL",
    "CONTACT_HAS_FUNCTION",
    "OUTCOME_VISIBLE",
    "REACTION_MATCHES_OUTCOME",
    "NEXT_STATE_CHANGED",
)
LEGIBILITY_CLASSES = ("LEGIBLE", "PARTIALLY_LEGIBLE", "NOT_LEGIBLE",
                      "INCONCLUSIVE")
OBSERVABILITY_CLASSES = (
    "VISUALLY_SELF_CONTAINED",
    "REQUIRES_PREVIOUS_SHOT_CONTEXT",
    "REQUIRES_REACTION_CUE",
    "REQUIRES_ESTABLISHING_CUE",
    "REQUIRES_SHOT_SPLIT",
    "UNFILMABLE_AS_CURRENT_SHOT",
)


def check_causal_legibility(intent: ActionIntent, *,
                            contact_present: bool) -> dict:
    """Deterministic contract checks over the recovered intent.

    A shot must not pass merely because animation is natural and
    identity is stable — these checks ask whether the causal structure
    (trigger -> goal -> action -> outcome -> next state) is present in
    the shot's own design."""
    checks = {}
    checks["TRIGGER_VISIBLE_OR_CONTEXTUALLY_ESTABLISHED"] = (
        "PASS (trigger stated: " + intent.trigger[:80] + ")"
        if intent.trigger else
        "FAIL (no trigger in the recovered intent)")
    checks["GOAL_INFERABLE"] = (
        "PASS (goal stated: " + intent.character_goal[:80] + ")"
        if intent.character_goal else
        "FAIL (no character goal recovered)")
    checks["ACTION_SERVES_GOAL"] = (
        "PASS (chosen action binds to the goal)" if
        intent.chosen_action and intent.character_goal else
        "FAIL (action without a goal, or goal without an action)")
    checks["CONTACT_HAS_FUNCTION"] = (
        "PASS (contact declared: " +
        intent.visual_legibility_requirements[0][:80] + ")" if
        contact_present and intent.visual_legibility_requirements else
        ("PASS (no contact event in this shot)" if not contact_present
         else "FAIL (contact present but no declared function)"))
    checks["OUTCOME_VISIBLE"] = (
        "PASS (intended outcome stated: " +
        intent.intended_outcome[:80] + ")" if intent.intended_outcome
        else "FAIL (no intended outcome)")
    checks["REACTION_MATCHES_OUTCOME"] = (
        "PASS (reaction bound to the outcome)" if
        intent.resulting_state else
        "INCONCLUSIVE (no resulting state declared)")
    checks["NEXT_STATE_CHANGED"] = (
        "PASS (next state: " + intent.next_decision[:80] + ")" if
        intent.next_decision else
        "FAIL (nothing changes and no state is intentionally held)")
    failed = [k for k, v in checks.items() if v.startswith("FAIL")]
    inconclusive = [k for k, v in checks.items()
                    if v.startswith("INCONCLUSIVE")]
    if failed:
        legibility = ("NOT_LEGIBLE" if len(failed) >= 3
                      else "PARTIALLY_LEGIBLE")
    elif inconclusive:
        legibility = "PARTIALLY_LEGIBLE"
    else:
        legibility = "LEGIBLE"
    return {"checks": checks, "failed": failed,
            "inconclusive": inconclusive, "legibility": legibility,
            "anti_pattern_guard": "a shot never passes merely because "
            "animation is natural + identity stable; meaning must be "
            "present in the design"}


def classify_observability(intent: ActionIntent, *,
                           trigger_visible_in_frame: bool,
                           framing: str = "") -> dict:
    """Can this intent actually be understood visually inside the
    current shot? Recommendations only — no automatic edit rewrite."""
    cu_framing = framing.upper() in ("CU", "MCU", "ECU")
    if intent.trigger and not trigger_visible_in_frame and cu_framing:
        cls = "REQUIRES_PREVIOUS_SHOT_CONTEXT"
        rec = ("the trigger lives in the preceding shot; keep the "
               "reaction legible instead of restating the event")
    elif intent.trigger and not trigger_visible_in_frame:
        cls = "REQUIRES_ESTABLISHING_CUE"
        rec = ("add the minimum in-frame cue for the trigger (e.g. the "
               "wind's visible effect) — nothing beyond authority")
    elif intent.trigger and trigger_visible_in_frame and \
            intent.visual_legibility_requirements:
        cls = "REQUIRES_REACTION_CUE"
        rec = ("the trigger is in frame; the reaction cue completes the "
               "causal read")
    else:
        cls = "VISUALLY_SELF_CONTAINED"
        rec = "the intent reads inside this shot alone"
    return {"observability": cls, "recommendation": rec,
            "rule": "recommendations only; the edit is never rewritten "
                    "automatically"}


def classify_causal_complexity(intent: ActionIntent, *,
                               locomotion: bool = False,
                               interaction: bool = False,
                               camera_locked: bool = True) -> dict:
    """Causal complexity: how many distinct causal beats must ONE short
    generation communicate? Advisory recommendations only."""
    beats = []
    if intent.trigger:
        beats.append("trigger")
    if intent.character_goal and intent.motivation:
        beats.append("decision")
    if locomotion:
        beats.append("locomotion")
    if interaction:
        beats.append("interaction")
    if intent.resulting_state:
        beats.append("reaction")
    if intent.next_decision:
        beats.append("recovery")
    recommendations = []
    if len(beats) >= 5:
        recommendations.append("SPLIT_NARRATIVE_BEAT")
    if "trigger" in beats and "reaction" in beats and len(beats) >= 5:
        recommendations.append("INSERT_REACTION_SHOT")
    if "trigger" in beats and not intent.perception:
        recommendations.append("ESTABLISH_TRIGGER")
    if not recommendations:
        recommendations.append("NONE")
    return {"causal_beats": beats, "count": len(beats),
            "recommendations": recommendations,
            "rule": "advisory only; no automatic restructuring"}


def build_shot_causality_graph(edges: list[dict]) -> dict:
    """Assemble the local causal graph; enforce the state-change
    invariant on every target shot."""
    validated = []
    for edge in edges:
        changed = bool(edge.get("outcome_alters_state")) or \
            bool(edge.get("maintains_state_intentionally"))
        if not changed:
            raise ValueError(
                f"meaningless action chain refused: target "
                f"{edge.get('target_shot')} alters no relevant state "
                f"and maintains none intentionally")
        validated.append({**edge, "state_change_invariant": "PASS"})
    return {"version": "shot-causality-graph-v1",
            "edges": validated,
            "invariant": "the target action must alter at least one "
                         "relevant state or clearly maintain a "
                         "necessary state intentionally"}
