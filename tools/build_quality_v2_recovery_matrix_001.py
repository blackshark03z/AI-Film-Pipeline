"""Build recovery_matrix_v2_001.json (QUALITY-V2-001 section 12).

Emits the frozen adversarial/recovery case table from the single source
of truth (film_pipeline.quality_repair_v2.RECOVERY_CASES). Each case is
PROVEN by an executing test in tests/test_quality_v2_recovery_matrix_001.py
which fails if any case lacks a live guard exercise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.quality_repair_v2 import (  # noqa: E402
    ACCEPTANCE_CONDITIONS, QUALITY_V2_CANONICAL_BASELINE, QUALITY_V2_GOAL,
    list_recovery_cases)

OUT_DIR = ROOT / "projects" / "quality_v2_repair_selection_policy_001"
OUT_PATH = OUT_DIR / "recovery_matrix_v2_001.json"


def main() -> int:
    cases = list_recovery_cases()
    if len(cases) < 80:
        raise SystemExit(f"recovery matrix must carry >=80 cases, has "
                         f"{len(cases)}")
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate recovery case ids")
    categories: dict[str, int] = {}
    for case in cases:
        categories[case["category"]] = categories.get(case["category"], 0) + 1
        for field in ("category", "scenario", "expected", "enforced_by"):
            if not case.get(field):
                raise SystemExit(f"{case['case_id']}: missing {field}")
    output = {
        "version": "recovery-matrix-v2-001-v1",
        "quality_v2_goal": QUALITY_V2_GOAL,
        "canonical_baseline": QUALITY_V2_CANONICAL_BASELINE,
        "count": len(cases),
        "categories": dict(sorted(categories.items())),
        "required_topic_coverage": {
            "candidate_valid_but_identity_regresses": "RC-004",
            "motion_improves_identity_regresses": "RC-013",
            "motion_improves_logic_worsens": "RC-087",
            "logic_improves_camera_breaks": "RC-014",
            "candidate_selected_without_owner": "RC-023",
            "wrong_asset_sha": "RC-001",
            "wrong_canonical_predecessor": "RC-045",
            "stale_edit_manifest": "RC-046",
            "master_rebuild_failure": "RC-050",
            "partial_promotion": "RC-051",
            "rollback_mismatch": "RC-059",
            "quality_debt_closed_too_early": "RC-065",
            "worker_score_auto_promotes": "RC-029",
            "aggregate_score_hides_regression": "RC-015",
            "ambiguous_provider_output": "RC-088",
            "blind_retry": "RC-089",
            "wrong_experiment_baseline": "RC-074",
            "unbounded_generation_budget": "RC-077",
            "v1_baseline_mutation": "RC-081",
        },
        "external_ambiguity_rule": "any future external-effect ambiguity "
                                   "remains OWNER_AMBIGUITY_GATE (frozen "
                                   "custody pattern: one submit, no retry)",
        "acceptance_conditions": [c[1] for c in ACCEPTANCE_CONDITIONS],
        "cases": cases,
        "proof": "every case is executed against its live guard by "
                 "tests/test_quality_v2_recovery_matrix_001.py",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    print(f"written {OUT_PATH.relative_to(ROOT)}: {len(cases)} cases "
          f"across {len(categories)} categories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
