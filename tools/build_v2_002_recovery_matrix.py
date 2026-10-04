"""AI-FILM-QUALITY-V2-002 — Phase 16: the package recovery matrix.

Two sections:
- reused_governance_cases: the 89 frozen QUALITY-V2-001 cases, each
  executed against its live guard by
  tests/test_quality_v2_recovery_matrix_001.py (unchanged, re-proven).
- package_cases: V2-002-specific cases, each executed against its live
  guard by tests/test_quality_v2_002_recovery_001.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.quality_repair_v2 import list_recovery_cases

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"

PACKAGE_CASES = [
    {"case_id": "V2-002-RC-001", "category": "AUTHORITY",
     "scenario": "wrong V1 baseline bound in the package records",
     "expected": "REFUSED",
     "enforced_by": "QUALITY_V2_CANONICAL_BASELINE binding + git ancestry"},
    {"case_id": "V2-002-RC-002", "category": "AUTHORITY",
     "scenario": "wrong F2 canonical predecessor bound to a candidate",
     "expected": "REFUSED",
     "enforced_by": "planned-render registry take binding + governed mint"},
    {"case_id": "V2-002-RC-003", "category": "AUTHORITY",
     "scenario": "wrong QD target on a planned render",
     "expected": "REFUSED",
     "enforced_by": "registry debt ids + governed candidate debt binding"},
    {"case_id": "V2-002-RC-004", "category": "BUDGET",
     "scenario": "admission receipt missing before live work",
     "expected": "REFUSED", "enforced_by": "admission_gate BLOCKED_INVARIANT"},
    {"case_id": "V2-002-RC-005", "category": "BUDGET",
     "scenario": "generate budget configured above 2",
     "expected": "REFUSED",
     "enforced_by": "ledger max_primary == 2 + driver budget check"},
    {"case_id": "V2-002-RC-006", "category": "BUDGET",
     "scenario": "third Generate attempt after 2/2 consumed",
     "expected": "REFUSED",
     "enforced_by": "driver raises before any run_live_shot call"},
    {"case_id": "V2-002-RC-007", "category": "BUDGET",
     "scenario": "duplicate dispatch of the same provider job",
     "expected": "REFUSED",
     "enforced_by": "store dispatch reservation dispatch_count == 1"},
    {"case_id": "V2-002-RC-008", "category": "CUSTODY",
     "scenario": "ambiguous provider effect after a submit",
     "expected": "FAILED_CLOSED",
     "enforced_by": "MutationAuthority one-way latch (throwaway scope)"},
    {"case_id": "V2-002-RC-009", "category": "CUSTODY",
     "scenario": "blind retry after a completed candidate result",
     "expected": "REFUSED",
     "enforced_by": "durable result.json short-circuit + consumed ledger"},
    {"case_id": "V2-002-RC-010", "category": "BLIND_REVIEW",
     "scenario": "candidate mislabeled on the blind reel",
     "expected": "REFUSED",
     "enforced_by": "deterministic blind draw recomputed vs answer key"},
    {"case_id": "V2-002-RC-011", "category": "BLIND_REVIEW",
     "scenario": "intent answer leaked into the blind section",
     "expected": "REFUSED",
     "enforced_by": "leak scan over blind packet + manifest blind rows"},
    {"case_id": "V2-002-RC-012", "category": "BLIND_REVIEW",
     "scenario": "blind answers recorded after the key was opened",
     "expected": "REFUSED",
     "enforced_by": "answered_blind flag + ordering discipline in packet"},
    {"case_id": "V2-002-RC-013", "category": "CRITICAL_NEGATIVES",
     "scenario": "candidate ends bracing at the rock",
     "expected": "REFUSED",
     "enforced_by": "blind answers + negative check recorded per candidate"},
    {"case_id": "V2-002-RC-014", "category": "CRITICAL_NEGATIVES",
     "scenario": "candidate takes cover behind the rock",
     "expected": "REFUSED",
     "enforced_by": "blind answers + negative check recorded per candidate"},
    {"case_id": "V2-002-RC-015", "category": "CRITICAL_NEGATIVES",
     "scenario": "through-state absent in a candidate",
     "expected": "REFUSED",
     "enforced_by": "blind Q4/Q5 answers + ACTION_CAUSALITY target gate"},
    {"case_id": "V2-002-RC-016", "category": "IDENTITY",
     "scenario": "identity drift hidden behind improved action logic",
     "expected": "REFUSED",
     "enforced_by": "IDENTITY hard block (V2-001 C3/C5) + identity receipt"},
    {"case_id": "V2-002-RC-017", "category": "REVIEW_CONTRACT",
     "scenario": "performance improves but narrative logic worsens",
     "expected": "REFUSED",
     "enforced_by": "C5 evaluate_acceptance (no aggregate compensation)"},
    {"case_id": "V2-002-RC-018", "category": "EDITORIAL",
     "scenario": "logic improves but editorial fit fails",
     "expected": "REFUSED",
     "enforced_by": "C6 + validate_editorial_receipt compatibility gate"},
    {"case_id": "V2-002-RC-019", "category": "EDITORIAL",
     "scenario": "canonical EditManifest modified by the preview",
     "expected": "UNCHANGED",
     "enforced_by": "preview-only successor + editorial_plan_010 hash"},
    {"case_id": "V2-002-RC-020", "category": "DECISION_RIGHTS",
     "scenario": "worker forges the Owner selection",
     "expected": "REFUSED",
     "enforced_by": "V2-001 owner decision guards + template decision null"},
    {"case_id": "V2-002-RC-021", "category": "DECISION_RIGHTS",
     "scenario": "candidate promoted inside V2-002",
     "expected": "REFUSED",
     "enforced_by": "no OWNER_SELECTED state + no promotion ledger event"},
    {"case_id": "V2-002-RC-022", "category": "CANONICAL",
     "scenario": "canonical master mutated by the experiment",
     "expected": "UNCHANGED",
     "enforced_by": "master sha256 == frozen 976876a1…"},
    {"case_id": "V2-002-RC-023", "category": "CANONICAL",
     "scenario": "a V2 candidate appears in the canonical lineage",
     "expected": "UNCHANGED",
     "enforced_by": "canonical slot 24 range file binding unchanged"},
    {"case_id": "V2-002-RC-024", "category": "REFERENCE",
     "scenario": "stale reference binding used for the renders",
     "expected": "REFUSED",
     "enforced_by": "frozen F2C binding + attestation files present"},
    {"case_id": "V2-002-RC-025", "category": "CUSTODY",
     "scenario": "wrong output identity bound to an asset",
     "expected": "REFUSED",
     "enforced_by": "acquired bytes sha256 == acquisition receipt sha256"},
    {"case_id": "V2-002-RC-026", "category": "REVIEW_CONTRACT",
     "scenario": "trade-off hidden from the Owner surface",
     "expected": "REFUSED",
     "enforced_by": "tradeoff_summary exposed per candidate in template"},
    {"case_id": "V2-002-RC-027", "category": "REVIEW_CONTRACT",
     "scenario": "aggregate score introduced into the receipt",
     "expected": "REFUSED", "enforced_by": "no_aggregate_score const true"},
    {"case_id": "V2-002-RC-028", "category": "CUSTODY",
     "scenario": "output attribution ambiguous (non-unique marker row)",
     "expected": "FAILED_CLOSED",
     "enforced_by": "0 ambiguous events in the ledger + unique output ids"},
]


def main() -> int:
    reused = list_recovery_cases()
    ids = [c["case_id"] for c in PACKAGE_CASES]
    if len(set(ids)) != len(ids) or len(PACKAGE_CASES) < 20:
        raise SystemExit("package case table invalid")
    output = {
        "version": "recovery-matrix-v2-002-v1",
        "count_total": len(reused) + len(PACKAGE_CASES),
        "reused_governance_cases": {
            "count": len(reused),
            "source": "film_pipeline.quality_repair_v2.RECOVERY_CASES",
            "executed_by": "tests/test_quality_v2_recovery_matrix_001.py",
            "case_ids": [c["case_id"] for c in reused]},
        "package_cases": {
            "count": len(PACKAGE_CASES),
            "executed_by": "tests/test_quality_v2_002_recovery_001.py",
            "cases": PACKAGE_CASES},
        "external_ambiguity_rule": "OWNER_AMBIGUITY_GATE (any ambiguous "
                                   "external effect; one submit, no retry)",
    }
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "recovery_matrix_v2_002.json").write_text(
        json.dumps(output, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"count_total": output["count_total"],
                      "package_cases": len(PACKAGE_CASES)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
