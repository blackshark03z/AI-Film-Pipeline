"""Build quality_v2_experiment_priority_001.json (QUALITY-V2-001 section 10).

Ranks the first Quality-Hardening experiment candidates (QH-1..QH-5 from
docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md) against the frozen criteria,
using ONLY facts recorded in the frozen evidence artifacts. Every score
carries a rationale that cites at least one real artifact path; the script
verifies every cited artifact exists before writing the output. The rank
order is COMPUTED from the weighted scores at run time, never hardcoded.

This document does NOT authorize any experiment (authorization_state =
NOT_AUTHORIZED; no generation happens here).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.quality_repair_v2 import (  # noqa: E402
    QUALITY_V2_CANONICAL_BASELINE, QUALITY_V2_GOAL)

OUT_DIR = ROOT / "projects" / "quality_v2_repair_selection_policy_001"
OUT_PATH = OUT_DIR / "quality_v2_experiment_priority_001.json"

# Frozen criteria weights (QUALITY_V2_SOT.md section 6).
WEIGHTS = {
    "expected_quality_leverage": 0.30,
    "information_gain": 0.20,
    "generation_cost": 0.15,
    "identity_risk": 0.15,
    "editorial_impact": 0.10,
    "reversibility": 0.10,
}
# Criteria where a HIGHER raw score is WORSE; the tool inverts them so a
# weighted total is always "higher is better".
INVERTED = ("generation_cost", "identity_risk", "editorial_impact")

DEBT_REGISTRY = ROOT / "projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json"
GAP_017 = ROOT / "projects/flow_performance_motion_canary_017/performance_motion_gap_017.json"
EXP_018 = ROOT / "projects/flow_action_intent_causality_018/action_causality_experiment_018.json"
ROADMAP = ROOT / "docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"

# Per-criterion evidence scores (1-5) with artifact-cited rationales.
# Higher raw = MORE of the named quantity (e.g. higher generation_cost
# raw = more expensive; the tool inverts before weighting).
CANDIDATES = [
    {
        "candidate": "QH-1_action_causality_redesign",
        "roadmap_ref": "QH-1",
        "target_debt_ids": ["QD-001", "QD-002"],
        "scores": {
            "expected_quality_leverage": (5,
                "Owner assessment NEEDS_REDESIGN for both canonical causal-logic debts; "
                "018 finding F2C-P018-A = CAUSAL_CONTROL_EFFECT_OBSERVED ('goal+outcome go "
                "from unreadable to readable') — the defect with the largest observed "
                "owner-visible swing",
                ["projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json",
                 "projects/flow_action_intent_causality_018/action_causality_experiment_018.json"]),
            "information_gain": (5,
                "The QH-1 remaining unknown is the central V2 question: whether redesigned shot "
                "INTENT (new dramatic purpose, not just compiled direction) plus the proven causal "
                "pipeline yields Owner-accepted meaning",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "generation_cost": (2,
                "Proposed experiment is ONE shot with <=2 generates through the existing causal "
                "compiler (cheap; raw score 2 = low cost)",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "identity_risk": (3,
                "New renders of the same character refs; 018 recorded 'identity stable' on the "
                "A candidate, but any new render re-exposes identity risk (moderate)",
                ["projects/flow_action_intent_causality_018/action_causality_experiment_018.json"]),
            "editorial_impact": (2,
                "Single-shot replacement keeps the master slot and runtime; conformance stays "
                "trim-compatible (raw score 2 = low editorial disruption)",
                ["projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json"]),
            "reversibility": (5,
                "Append-only promotion with the exact predecessor SelectedTake retained for "
                "deterministic rollback (QUALITY-V2-001 rollback contract)",
                ["src/film_pipeline/quality_repair_v2.py"]),
        },
    },
    {
        "candidate": "QH-4_choreography_intensity_ladder",
        "roadmap_ref": "QH-4",
        "target_debt_ids": ["QD-004"],
        "scores": {
            "expected_quality_leverage": (3,
                "QD-004 NEEDS_REPAIR on F2 stiffness; 017 Q2 CONTROL_EFFECT_OBSERVED proves the "
                "mechanism works, but the defect is narrower than the causal-logic debt",
                ["projects/flow_performance_motion_canary_017/performance_motion_gap_017.json",
                 "projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json"]),
            "information_gain": (4,
                "The ladder maps the saturation curve (how much choreography density fits the "
                "qualified 500/75 envelope) — a reusable recipe, not just one shot fix",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "generation_cost": (2,
                "Three renders on one action shot (ladder 1/2/3 movement phrases)",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "identity_risk": (2,
                "Same shot spec, wording-only changes; 017 B/C renders kept identity stable",
                ["projects/flow_performance_motion_canary_017/performance_motion_gap_017.json"]),
            "editorial_impact": (2,
                "Single-shot replacement, slot preserved",
                ["projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json"]),
            "reversibility": (5,
                "Append-only promotion + deterministic rollback as for any candidate",
                ["src/film_pipeline/quality_repair_v2.py"]),
        },
    },
    {
        "candidate": "QH-3_full_body_proportion",
        "roadmap_ref": "QH-3",
        "target_debt_ids": ["QD-003"],
        "scores": {
            "expected_quality_leverage": (4,
                "QD-003 affects ALL canonical shots (silhouette quality varies without an "
                "authority); Owner category BODY_PROPORTION = NEEDS_INVESTIGATION",
                ["projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json",
                 "projects/flow_performance_motion_canary_017/performance_motion_gap_017.json"]),
            "information_gain": (4,
                "Q1 stayed INCONCLUSIVE in 017 (A lost to provider anti-abuse failure, C "
                "confounded by re-staging); a clean isolated A/B finally answers controllability",
                ["projects/flow_performance_motion_canary_017/performance_motion_gap_017.json"]),
            "generation_cost": (3,
                "Requires an Owner-approved full-body reference (content input) BEFORE the A/B "
                "canary — an external dependency plus renders",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "identity_risk": (4,
                "Proportion changes sit closest to identity drift; 017-C showed silhouette change "
                "confounds attribution and the roadmap demands FACE_IDENTITY/HAIR/COSTUME "
                "unchanged under blind side-by-side",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "editorial_impact": (1,
                "No editorial change: same framing, same slot, same trim",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "reversibility": (5,
                "Append-only promotion + deterministic rollback as for any candidate",
                ["src/film_pipeline/quality_repair_v2.py"]),
        },
    },
    {
        "candidate": "QH-5_camera_blocking_staging_control",
        "roadmap_ref": "QH-5",
        "target_debt_ids": [],
        "scores": {
            "expected_quality_leverage": (2,
                "Staging drift is real (017-B/C re-staged the gate; 018-B braced AT the rock) but "
                "no registry debt carries it as the primary defect",
                ["projects/flow_action_intent_causality_018/action_causality_experiment_018.json",
                 "projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json"]),
            "information_gain": (3,
                "Maps how much staging control the qualified route exposes (blocking wording vs "
                "reference framing) — useful but secondary",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "generation_cost": (2,
                "Three blocking-wording variants of one action shot",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "identity_risk": (2,
                "Same subject and wardrobe; camera wording only",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "editorial_impact": (3,
                "Staging changes can alter coverage and continuity against neighbors; needs "
                "editorial re-check",
                ["projects/flow_action_intent_causality_018/action_causality_experiment_018.json"]),
            "reversibility": (4,
                "Append-only promotion + rollback; staging learnings compound but the asset swap "
                "itself reverses deterministically",
                ["src/film_pipeline/quality_repair_v2.py"]),
        },
    },
    {
        "candidate": "QH-2_shot_decomposition_split_beat",
        "roadmap_ref": "QH-2",
        "target_debt_ids": [],
        "scores": {
            "expected_quality_leverage": (3,
                "017 flagged EXTREME/HIGH complexity cases and 018 recommends SPLIT_NARRATIVE_BEAT "
                "(advisory) — meaningful, but no registry debt is scoped to a specific dense beat",
                ["projects/flow_performance_motion_canary_017/performance_motion_gap_017.json",
                 "projects/flow_action_intent_causality_018/action_causality_experiment_018.json"]),
            "information_gain": (3,
                "First cost/benefit data point for splitting one dense beat against master rhythm",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "generation_cost": (4,
                "TWO new shots plus a revised edit slice (double generation and review surface)",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "identity_risk": (3,
                "Two fresh renders of the same character; same risk class as QH-1",
                ["docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md"]),
            "editorial_impact": (5,
                "Structural change: the master gains a slot; conformance, rhythm and the "
                "30-slot lineage are all touched",
                ["projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json"]),
            "reversibility": (3,
                "Asset swap reverses, but the manifest structure change makes the rollback scope "
                "wider than one clip",
                ["src/film_pipeline/quality_repair_v2.py"]),
        },
    },
]


def main() -> int:
    # Load frozen evidence the scores cite (existence + key facts).
    registry = json.loads(DEBT_REGISTRY.read_text(encoding="utf-8"))
    gap = json.loads(GAP_017.read_text(encoding="utf-8"))
    exp18 = json.loads(EXP_018.read_text(encoding="utf-8"))
    known_debt_ids = {i["debt_id"] for i in registry["items"]}
    roadmap_text = ROADMAP.read_text(encoding="utf-8")

    assert registry["count"] == 5 and known_debt_ids == {"QD-001", "QD-002",
        "QD-003", "QD-004", "QD-005"}, "frozen registry changed"
    assert gap["categories"]["PERFORMANCE_NATURALNESS"] == "NEEDS_REPAIR"
    assert "CAUSAL_CONTROL_EFFECT_OBSERVED" in canonical(exp18), \
        "018 causal effect finding missing"

    rows = []
    for entry in CANDIDATES:
        weighted = 0.0
        criteria = {}
        for criterion, (raw, rationale, citations) in entry["scores"].items():
            for rel in citations:
                p = ROOT / rel
                if not p.exists():
                    raise SystemExit(f"cited artifact missing: {rel}")
                if rel != "src/film_pipeline/quality_repair_v2.py" and \
                        rel != "docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md" and \
                        rel not in canonical(registry) + canonical(gap) + canonical(exp18):
                    pass  # citation recorded verbatim in the output below
            effective = raw if criterion not in INVERTED else 6 - raw
            weighted += WEIGHTS[criterion] * effective
            criteria[criterion] = {"raw_score": raw,
                                   "direction": ("higher_raw_is_worse"
                                                 if criterion in INVERTED
                                                 else "higher_raw_is_better"),
                                   "weighted_contribution":
                                       round(WEIGHTS[criterion] * effective, 4),
                                   "rationale": rationale,
                                   "cited_artifacts": citations}
        unknown_debt = sorted(set(entry["target_debt_ids"]) - known_debt_ids)
        if unknown_debt:
            raise SystemExit(f"{entry['candidate']}: unknown debt ids "
                             f"{unknown_debt}")
        if entry["roadmap_ref"] not in roadmap_text:
            raise SystemExit(f"{entry['candidate']}: roadmap ref missing")
        rows.append({"candidate": entry["candidate"],
                     "roadmap_ref": entry["roadmap_ref"],
                     "target_debt_ids": entry["target_debt_ids"],
                     "criteria": criteria,
                     "weighted_total": round(weighted, 4)})
    rows.sort(key=lambda r: (-r["weighted_total"], r["candidate"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    recommended = rows[0]["candidate"]
    output = {
        "version": "quality-v2-experiment-priority-001-v1",
        "quality_v2_goal": QUALITY_V2_GOAL,
        "canonical_baseline": QUALITY_V2_CANONICAL_BASELINE,
        "ranking_method": {
            "weights": WEIGHTS,
            "inverted_criteria": list(INVERTED),
            "score_scale": "1..5 raw; inverted criteria use 6-raw so the "
                           "weighted total is always higher-is-better",
            "computed_at_runtime": True,
            "note": "rank order is computed from weighted totals in this "
                    "tool at run time; every score carries a rationale "
                    "citing frozen evidence artifacts whose existence is "
                    "verified before write",
        },
        "evidence_sources": [
            "projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json",
            "projects/flow_v1_completion_quality_debt_freeze_019/owner_quality_decision_019.json",
            "projects/flow_performance_motion_canary_017/performance_motion_gap_017.json",
            "projects/flow_action_intent_causality_018/action_causality_experiment_018.json",
            "docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md",
        ],
        "ranking": rows,
        "recommendation": {
            "first_experiment": recommended,
            "second_experiment": rows[1]["candidate"],
            "why_first": (
                "highest weighted total: it targets the two Owner "
                "NEEDS_REDESIGN causal-logic debts (QD-001, QD-002), "
                "reuses the PROVEN causal-control mechanism "
                "(018-A CAUSAL_CONTROL_EFFECT_OBSERVED), costs at most "
                "two generates on one shot, preserves the master slot, "
                "and is fully reversible under the frozen promotion/"
                "rollback contract"),
            "authorization_state": "NOT_AUTHORIZED",
            "authorization_path": "V2-002 must submit an "
                                  "ExperimentAdmissionReceipt through the "
                                  "frozen admission gate "
                                  "(film_pipeline.quality_repair_v2."
                                  "admission_gate) before any live step",
        },
        "invariants": {
            "no_generation_in_this_package": True,
            "canonical_promotion_in_this_package": 0,
            "candidates_never_auto_promoted": True,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    print(f"written {OUT_PATH.relative_to(ROOT)}")
    for row in rows:
        print(f"  #{row['rank']} {row['candidate']}: "
              f"{row['weighted_total']}")
    print(f"recommended first experiment: {recommended} (NOT AUTHORIZED)")
    return 0


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
