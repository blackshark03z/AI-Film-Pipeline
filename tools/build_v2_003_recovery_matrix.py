"""AI-FILM-QUALITY-V2-003 — Phase 14: the package recovery matrix.

reused: the 117 frozen cases from V2-001 (89) + V2-002 (28), each still
executed live by their existing test files.
package: 30 V2-003-specific cases, each executed against its live guard
by tests/test_v2_003_recovery_001.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.quality_repair_v2 import list_recovery_cases

OUT = ROOT / "projects/quality_v2_003_director_blocking" / \
    "recovery_matrix_v2_003.json"

PACKAGE_CASES = [
    {"case_id": "V2-003-RC-001", "category": "DIRECTOR_AUTHORITY",
     "scenario": "missing DirectorIntent at compile time",
     "expected": "REFUSED", "enforced_by": "assert_compile_authorities_present"},
    {"case_id": "V2-003-RC-002", "category": "DIRECTOR_AUTHORITY",
     "scenario": "missing BlockingSpec at compile time",
     "expected": "REFUSED", "enforced_by": "assert_compile_authorities_present"},
    {"case_id": "V2-003-RC-003", "category": "GATES",
     "scenario": "same start/end zone with traversal required",
     "expected": "REFUSED", "enforced_by": "B1_START_END_DISTINCT"},
    {"case_id": "V2-003-RC-004", "category": "GATES",
     "scenario": "path loops around the rock",
     "expected": "REFUSED", "enforced_by": "B5_NO_CIRCLING"},
    {"case_id": "V2-003-RC-005", "category": "GATES",
     "scenario": "path ends at the rock (target never reached)",
     "expected": "REFUSED", "enforced_by": "B3_PATH_HAS_PROGRESS"},
    {"case_id": "V2-003-RC-006", "category": "GATES",
     "scenario": "path reverses after crossing",
     "expected": "REFUSED", "enforced_by": "B6_NO_REVERSAL"},
    {"case_id": "V2-003-RC-007", "category": "GATES",
     "scenario": "spatial state change never reaches the target zone",
     "expected": "REFUSED", "enforced_by": "B2_TARGET_REACHED"},
    {"case_id": "V2-003-RC-008", "category": "CAMERA",
     "scenario": "crossing hidden by camera visibility flag",
     "expected": "REFUSED", "enforced_by": "B7_CROSSING_OBSERVABLE"},
    {"case_id": "V2-003-RC-009", "category": "CAMERA",
     "scenario": "tight framing collapses start/end geography",
     "expected": "REFUSED", "enforced_by": "B8_END_STATE_OBSERVABLE"},
    {"case_id": "V2-003-RC-010", "category": "CAMERA",
     "scenario": "camera crosses the axis unexpectedly",
     "expected": "REFUSED", "enforced_by": "B7 motion-vs-forbidden scan"},
    {"case_id": "V2-003-RC-011", "category": "CAMERA",
     "scenario": "start/end visually indistinguishable regions",
     "expected": "REFUSED", "enforced_by": "B8 region binding"},
    {"case_id": "V2-003-RC-012", "category": "COMPILER",
     "scenario": "compiler invents a path around/with the rock",
     "expected": "REFUSED",
     "enforced_by": "assert_compiler_respected_authority"},
    {"case_id": "V2-003-RC-013", "category": "COMPILER",
     "scenario": "compiler invents a rock brace",
     "expected": "REFUSED",
     "enforced_by": "assert_compiler_respected_authority"},
    {"case_id": "V2-003-RC-014", "category": "COMPILER",
     "scenario": "compiled prompt lacks the required end spatial read",
     "expected": "REFUSED",
     "enforced_by": "assert_compiler_respected_authority"},
    {"case_id": "V2-003-RC-015", "category": "IDENTITY",
     "scenario": "worker changes Director output silently after minting",
     "expected": "REFUSED", "enforced_by": "contract identity derivation"},
    {"case_id": "V2-003-RC-016", "category": "IDENTITY",
     "scenario": "Director invents a story event without authority",
     "expected": "REFUSED", "enforced_by": "authority-source completeness"},
    {"case_id": "V2-003-RC-017", "category": "IDENTITY",
     "scenario": "different BlockingSpec yields the same generation identity",
     "expected": "REFUSED", "enforced_by": "director_semantic_identity"},
    {"case_id": "V2-003-RC-018", "category": "IDENTITY",
     "scenario": "different CameraCoveragePlan yields the same identity",
     "expected": "REFUSED", "enforced_by": "director_semantic_identity"},
    {"case_id": "V2-003-RC-019", "category": "GATES",
     "scenario": "missing authority source on a semantic field",
     "expected": "REFUSED", "enforced_by": "B10_AUTHORITY_COMPLETE"},
    {"case_id": "V2-003-RC-020", "category": "CONTINUITY",
     "scenario": "F1/F3 screen-direction continuity conflict",
     "expected": "REFUSED", "enforced_by": "B9_CONTINUITY_COMPATIBLE"},
    {"case_id": "V2-003-RC-021", "category": "BASELINE",
     "scenario": "V1 baseline mutation",
     "expected": "UNCHANGED",
     "enforced_by": "QUALITY_V2_CANONICAL_BASELINE + git custody"},
    {"case_id": "V2-003-RC-022", "category": "BASELINE",
     "scenario": "canonical mutation by this package",
     "expected": "UNCHANGED", "enforced_by": "master sha256 == 976876a1…"},
    {"case_id": "V2-003-RC-023", "category": "CUSTODY",
     "scenario": "provider call attempted by the governance layer",
     "expected": "UNCHANGED", "enforced_by": "module surface scan"},
    {"case_id": "V2-003-RC-024", "category": "CUSTODY",
     "scenario": "video generation attempted by this package",
     "expected": "UNCHANGED",
     "enforced_by": "no generate ledger exists in the package dir"},
    {"case_id": "V2-003-RC-025", "category": "MODEL",
     "scenario": "silent model downgrade",
     "expected": "REFUSED",
     "enforced_by": "availability receipt + BLOCKED_ON_DIRECTOR_MODEL + "
                    "no worker-authored F2 plan"},
    {"case_id": "V2-003-RC-026", "category": "MODEL",
     "scenario": "director model unavailable",
     "expected": "FAILED_CLOSED",
     "enforced_by": "DIRECTOR_MODEL_UNAVAILABLE receipt"},
    {"case_id": "V2-003-RC-027", "category": "MODEL",
     "scenario": "Owner ambiguity rule regression",
     "expected": "UNCHANGED", "enforced_by": "EXTERNAL_AMBIGUITY_RULE"},
    {"case_id": "V2-003-RC-028", "category": "PREVIZ",
     "scenario": "previz renders differently for the same plan",
     "expected": "REFUSED",
     "enforced_by": "deterministic byte-identical re-render"},
    {"case_id": "V2-003-RC-029", "category": "PREVIZ",
     "scenario": "previz written outside its declared planning directory",
     "expected": "REFUSED", "enforced_by": "out-dir-only writes"},
    {"case_id": "V2-003-RC-030", "category": "GATES",
     "scenario": "empty authority string counted as present",
     "expected": "REFUSED",
     "enforced_by": "validators require non-empty authority values"},
]


def main() -> int:
    reused_v2_001 = list_recovery_cases()
    v2_002 = json.loads((ROOT / "projects/quality_v2_002_f2_causality_"
                         "experiment/recovery_matrix_v2_002.json")
                        .read_text(encoding="utf-8"))
    reused_total = len(reused_v2_001) + v2_002["package_cases"]["count"]
    ids = [c["case_id"] for c in PACKAGE_CASES]
    assert len(set(ids)) == len(ids) and len(PACKAGE_CASES) >= 30
    total = reused_total + len(PACKAGE_CASES)
    if total < 100:
        raise SystemExit("matrix must carry >=100 cases")
    output = {
        "version": "recovery-matrix-v2-003-v1",
        "count_total": total,
        "reused_cases": {
            "count": reused_total,
            "v2_001_governance": len(reused_v2_001),
            "v2_002_package": v2_002["package_cases"]["count"],
            "executed_by": ["tests/test_quality_v2_recovery_matrix_001.py",
                            "tests/test_quality_v2_002_recovery_001.py"]},
        "package_cases": {
            "count": len(PACKAGE_CASES),
            "executed_by": "tests/test_v2_003_recovery_001.py",
            "cases": PACKAGE_CASES},
        "external_ambiguity_rule": "OWNER_AMBIGUITY_GATE",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"count_total": total,
                      "package_cases": len(PACKAGE_CASES)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
