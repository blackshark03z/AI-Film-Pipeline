"""FLOW-V1-COMPLETION-QUALITY-DEBT-FREEZE-019 (Phase V4): freeze the
quality debt registry — five explicit debt items bound to 017/018
evidence, plus the frozen gate rule demonstration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.quality_debt import (QualityDebtItem,
                                        validate_debt_cannot_satisfy_release_gates)

D19 = ROOT / "projects/flow_v1_completion_quality_debt_freeze_019"
D19.mkdir(parents=True, exist_ok=True)


def item(**kw):
    base = dict(project="swordsman_film", status="ACTIVE",
                accepted_for_technical_completion=True,
                future_track="AI_FILM_QUALITY_HARDENING_V2",
                release_impact="the defect remains visible in the "
                               "canonical film; no release gate is "
                               "satisfied by this debt — the content "
                               "gates stay blocked until real "
                               "Owner/content inputs arrive")
    base.update(kw)
    return QualityDebtItem(**base)


ITEMS = [
    item(debt_id="QD-001", scope="SEQ7_F2 / SEQ7_F2C (canonical)",
         category="ACTION_CAUSAL_LOGIC",
         affected_canonical_artifacts=["SEQ7_F2 (master slot 24)",
                                       "master_editorial_010_v1.mp4"],
         observed_problem="the visible action does not communicate WHY "
                          "he acts or WHAT changes: goal and outcome "
                          "unreadable in the canonical take",
         owner_assessment="NEEDS_REDESIGN (F2_ACTION_LOGIC, "
                          "owner_quality_decision_019.json)",
         current_impact="the shot plays as generic struggle in wind; "
                        "story causality is carried by neighbors only",
         known_evidence=[
             "projects/flow_action_intent_causality_018/"
             "baseline_action_legibility_018.json rows F2C (canonical): "
             "NOT_LEGIBLE (goal+outcome)",
             "projects/flow_performance_motion_canary_017/"
             "motion_packets/MOT-Q017-BASE-F2C (40-frame evidence: "
             "glide-like, occluded)",
             "projects/flow_action_intent_causality_018/"
             "action_authority_trace_018.json (intent RESOLVED "
             "upstream)"],
         attempts_already_performed=[
             "Package-017 canaries B/C (motion-only + combined): "
             "motion improved, meaning still ambiguous",
             "Package-018 canaries A/B (causal intent compiled): "
             "meaning rendered visibly in A (796040db...), B partial"],
         what_improved="018-A demonstrably renders trigger/outcome; the "
                       "causal compiler works",
         what_remains_unresolved="canonical F2 still needs a redesigned "
                                 "action logic; 018-A is not promoted "
                                 "(Owner: NEEDS_REDESIGN + "
                                 "FURTHER_V1_VIDEO_REGENERATION "
                                 "DISALLOWED)"),
    item(debt_id="QD-002", scope="SEQ7_G3 / SEQ7_G3C (canonical)",
         category="ACTION_CAUSAL_LOGIC",
         affected_canonical_artifacts=["SEQ7_G3 (master slot 29)",
                                       "master_editorial_010_v1.mp4"],
         observed_problem="the release/settle beat is unreadable "
                          "standalone: the canonical take reads as a "
                          "speech-like mouth opening; the completed-arc "
                          "trigger lives in G2 and is not in frame",
         owner_assessment="NEEDS_REDESIGN (G3_ACTION_LOGIC)",
         current_impact="the close beat underplays its own meaning "
                        "without the cut's adjacency",
         known_evidence=[
             "baseline_action_legibility_018.json rows G3C (canonical): "
             "NOT_LEGIBLE standalone",
             "flow_performance_motion_canary_017 evidence: "
             "mouth-artifact finding on the 32-frame baseline packet",
             "shot_causality_graph_018.json G2->G3->G4 edges"],
         attempts_already_performed=[
             "Package-017 canary D: mouth artifact eliminated, settle "
             "subtle",
             "Package-018 canary C: release-of-effort reads "
             "(d4b427d7...), minor hair-pin drift flagged"],
         what_improved="018-C reads the reaction correctly; the fix "
                       "mechanism is proven",
         what_remains_unresolved="canonical G3 not redesigned; 018-C not "
                                 "promoted; framing-bound causal "
                                 "completeness"),
    item(debt_id="QD-003",
         scope="character body rendering (all canonical shots)",
         category="BODY_PROPORTION_CONTROL",
         affected_canonical_artifacts=["canonical 30-slot lineage"],
         observed_problem="body proportions can appear too short/"
                          "compact; no full-body reference exists so "
                          "exact proportion authority is UNKNOWN",
         owner_assessment="NEEDS_INVESTIGATION (Package-017 gap "
                          "receipt); directional constraint recorded "
                          "(avoid short/compact silhouette)",
         current_impact="silhouette quality varies by shot without an "
                        "authority to direct it",
         known_evidence=[
             "flow_performance_motion_canary_017 evidence Q1 = "
             "INCONCLUSIVE (proportion candidate A lost to a provider "
             "anti-abuse failure; C confounded by re-staging)",
             "fixtures/character_bible/"
             "swordsman_white_robes_body_v1.json (chest-up reference "
             "only)"],
         attempts_already_performed=[
             "017 candidate A (proportion-only): "
             "PROVIDER_RENDER_FAILED_NOT_CHARGED, no retry permitted",
             "017 candidate C (combined): silhouette reads leaner but "
             "attribution confounded"],
         what_improved="the mechanism exists (BodyProportionAuthority "
                       "v1 + directional constraint compiled)",
         what_remains_unresolved="whether proportion is controllable on "
                                 "this provider is UNKNOWN until a "
                                 "clean isolated experiment runs in the "
                                 "V2 track"),
    item(debt_id="QD-004",
         scope="performance naturalness (action shots)",
         category="PERFORMANCE_NATURALNESS",
         affected_canonical_artifacts=["SEQ7_F2 (master slot 24)"],
         observed_problem="canonical action reads stiff/mannequin-like "
                          "(unit-body lean, little segment "
                          "articulation)",
         owner_assessment="NEEDS_REPAIR (Package-017 gap receipt)",
         current_impact="physical action believability below the "
                        "film's bar in the canonical take",
         known_evidence=[
             "baseline motion observations 017: PERFORMANCE_STIFFNESS "
             "FAIL on F2C",
             "017 matrix 104/104 (B/C materially more natural under "
             "the same provider)"],
         attempts_already_performed=[
             "017 B/C choreography canaries: CONTROL_EFFECT_OBSERVED "
             "(stride, weight transfer, counter-rotation render)"],
         what_improved="choreography direction is proven effective "
                       "(017 Q2); stiffness is NOT a provider ceiling "
                       "for this shot class",
         what_remains_unresolved="canonical F2 retains the stiff take; "
                                 "candidates not promoted"),
    item(debt_id="QD-005", scope="temporal motion quality judgment",
         category="TEMPORAL_MOTION_QUALITY",
         affected_canonical_artifacts=[
             "all canonical shots (3-frame sampling limit)"],
         observed_problem="the qualified 3-frame semantic sampling "
                          "cannot judge temporal motion; motion defects "
                          "could hide in canonical takes",
         owner_assessment="INSUFFICIENT_CURRENT_SAMPLING (Package-017 "
                          "gap receipt); Owner judged temporal quality "
                          "on the review reel (master-level request)",
         current_impact="temporal quality remains an Owner-judgment "
                        "surface rather than an automated one",
         known_evidence=[
             "014 production review: visual temporal INCONCLUSIVE on "
             "all 30 shots",
             "motion_qc.py MotionReviewPacket v1 proven offline (dense "
             "8-12 fps evidence)"],
         attempts_already_performed=[
             "017 built the dense-frame packet boundary and reviewed "
             "all baselines/candidates as motion"],
         what_improved="motion is finally reviewable AS motion (packets "
                       "+ grids + compare reels)",
         what_remains_unresolved="no autonomous temporal QC backend "
                                 "exists (semantic backend "
                                 "NOT_QUALIFIED); Owner review remains "
                                 "the authority"),
]


def main() -> None:
    registry = {
        "version": "quality-debt-registry-019-v1",
        "rule": "quality debt may NOT silently satisfy a release-"
                "quality gate; it means technical pipeline completion "
                "may proceed while creative quality remains explicitly "
                "unresolved",
        "owner_decision_binding": "owner_quality_decision_019.json "
                                  "(ACCEPT_KNOWN_QUALITY_DEBT; "
                                  "FURTHER_V1_VIDEO_REGENERATION = "
                                  "DISALLOWED for V1)",
        "items": [json.loads(i.model_dump_json()) for i in ITEMS],
        "count": len(ITEMS)}
    registry["gate_rule_check"] = validate_debt_cannot_satisfy_release_gates(
        ITEMS[0], {"OWNER_TAKE_REVIEW": False, "SEMANTIC_RELEASE": False,
                   "PRODUCTION_NARRATION": False,
                   "TIMED_CAPTIONS": False})
    (D19 / "quality_debt_registry_019.json").write_text(
        json.dumps(registry, indent=1), encoding="utf-8")
    print("V4 registry frozen:", [i.debt_id for i in ITEMS])


if __name__ == "__main__":
    main()
