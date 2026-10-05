"""AI-FILM-QUALITY-V2-008 — Phase 16: the package recovery matrix.
415 total cases (333 reused frozen + 82 package-specific)."""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = (ROOT / "projects/quality_v2_008_world_anchored_live" /
       "recovery_matrix_v2_008.json")
PACKAGE_CASES = [
    {"case_id": "V2-008-RC-001", "category": "REFERENCE", "scenario": "frame extracted at the wrong timestamp", "expected": "REFUSED", "enforced_by": "frame_s=6.6 frozen + sha compare vs V2-007"},
    {"case_id": "V2-008-RC-002", "category": "REFERENCE", "scenario": "frame SHA mismatch vs V2-007 recorded", "expected": "REFUSED", "enforced_by": "BLOCKED_INVARIANT on mismatch"},
    {"case_id": "V2-008-RC-003", "category": "REFERENCE", "scenario": "wrong source video used for extraction", "expected": "REFUSED", "enforced_by": "result.json provenance binding"},
    {"case_id": "V2-008-RC-004", "category": "UPLOAD", "scenario": "upload response ambiguous (TRUE_AMBIGUOUS)", "expected": "FAILED_CLOSED", "enforced_by": "classifier -> OwnerAmbiguityGate; latch"},
    {"case_id": "V2-008-RC-005", "category": "UPLOAD", "scenario": "upload duplicate/nonunique media", "expected": "FAILED_CLOSED", "enforced_by": "reconcile multiple-strong-match refusal"},
    {"case_id": "V2-008-RC-006", "category": "UPLOAD", "scenario": "wrong provider media bound to F2B", "expected": "REFUSED", "enforced_by": "binding identity == qualification receipt"},
    {"case_id": "V2-008-RC-007", "category": "UPLOAD", "scenario": "second reference upload attempted", "expected": "REFUSED", "enforced_by": "ledger max_uploads=1 + BLOCKED_INVARIANT"},
    {"case_id": "V2-008-RC-008", "category": "UPLOAD", "scenario": "hidden upload", "expected": "REFUSED", "enforced_by": "upload ledger + upload_count=1 assertion"},
    {"case_id": "V2-008-RC-009", "category": "UPLOAD", "scenario": "unresolved catalog row blocks without pre-existing evidence", "expected": "FAILED_CLOSED", "enforced_by": "strict default observed live; resolved with durable V2-006 baselines"},
    {"case_id": "V2-008-RC-010", "category": "F2A_PLAN", "scenario": "old long-approach plan reused", "expected": "REFUSED", "enforced_by": "plan_revision=2 + identity change proof"},
    {"case_id": "V2-008-RC-011", "category": "F2A_PLAN", "scenario": "previous plan deleted", "expected": "REFUSED", "enforced_by": "preserved_previous assertion"},
    {"case_id": "V2-008-RC-012", "category": "F2A_QC", "scenario": "F2A sword draw", "expected": "REFUSED", "enforced_by": "A9 NO_SWORD_DRAW"},
    {"case_id": "V2-008-RC-013", "category": "F2A_QC", "scenario": "F2A guard stance", "expected": "REFUSED", "enforced_by": "A9 + B17 class"},
    {"case_id": "V2-008-RC-014", "category": "F2A_QC", "scenario": "F2A metal gate", "expected": "REFUSED", "enforced_by": "A11 NO_METAL_GATE"},
    {"case_id": "V2-008-RC-015", "category": "F2A_QC", "scenario": "F2A arrival late", "expected": "REFUSED", "enforced_by": "A5 threshold by 2.4s"},
    {"case_id": "V2-008-RC-016", "category": "F2A_QC", "scenario": "F2A full crossing in-shot", "expected": "REFUSED", "enforced_by": "A6"},
    {"case_id": "V2-008-RC-017", "category": "F2A_QC", "scenario": "F2A rock interaction", "expected": "REFUSED", "enforced_by": "A7"},
    {"case_id": "V2-008-RC-018", "category": "F2A_QC", "scenario": "F2A reversal", "expected": "REFUSED", "enforced_by": "A8"},
    {"case_id": "V2-008-RC-019", "category": "F2B_REF", "scenario": "old identity-only reference reused", "expected": "REFUSED", "enforced_by": "driver assert refbind_57abbee5 absent"},
    {"case_id": "V2-008-RC-020", "category": "F2B_REF", "scenario": "old near-side reference reused for F2B", "expected": "REFUSED", "enforced_by": "driver assert fecf669e absent + sha equality"},
    {"case_id": "V2-008-RC-021", "category": "F2B_REF", "scenario": "multi-reference attempt", "expected": "REFUSED", "enforced_by": "exactly ONE reference per shot"},
    {"case_id": "V2-008-RC-022", "category": "F2B_QC", "scenario": "fortress world", "expected": "REFUSED", "enforced_by": "B12 NO_FORTRESS"},
    {"case_id": "V2-008-RC-023", "category": "F2B_QC", "scenario": "warm cloud world", "expected": "REFUSED", "enforced_by": "B14"},
    {"case_id": "V2-008-RC-024", "category": "F2B_QC", "scenario": "metal gate", "expected": "REFUSED", "enforced_by": "B13"},
    {"case_id": "V2-008-RC-025", "category": "F2B_QC", "scenario": "incompatible architecture", "expected": "REFUSED", "enforced_by": "B15"},
    {"case_id": "V2-008-RC-026", "category": "F2B_QC", "scenario": "gate in front instead of behind", "expected": "REFUSED", "enforced_by": "B2"},
    {"case_id": "V2-008-RC-027", "category": "F2B_QC", "scenario": "F2B sword draw", "expected": "REFUSED", "enforced_by": "B16"},
    {"case_id": "V2-008-RC-028", "category": "F2B_QC", "scenario": "F2B guard action", "expected": "REFUSED", "enforced_by": "B17"},
    {"case_id": "V2-008-RC-029", "category": "F2B_QC", "scenario": "F2B far side after 2.4s", "expected": "REFUSED", "enforced_by": "B6"},
    {"case_id": "V2-008-RC-030", "category": "F2B_QC", "scenario": "F2B starts near-side", "expected": "REFUSED", "enforced_by": "B1"},
    {"case_id": "V2-008-RC-031", "category": "PAIR", "scenario": "pair evaluated with a failed half", "expected": "REFUSED", "enforced_by": "both hard sets required"},
    {"case_id": "V2-008-RC-032", "category": "PAIR", "scenario": "F2A passes / F2B fails", "expected": "REFUSED", "enforced_by": "pair refused"},
    {"case_id": "V2-008-RC-033", "category": "PAIR", "scenario": "F2B passes / F2A fails", "expected": "REFUSED", "enforced_by": "pair refused"},
    {"case_id": "V2-008-RC-034", "category": "PAIR", "scenario": "half-selection", "expected": "REFUSED", "enforced_by": "atomic template"},
    {"case_id": "V2-008-RC-035", "category": "PAIR", "scenario": "pair timing exceeds 5.6s", "expected": "REFUSED", "enforced_by": "P10 + frozen windows"},
    {"case_id": "V2-008-RC-036", "category": "PAIR", "scenario": "direction mismatch across cut", "expected": "REFUSED", "enforced_by": "P3"},
    {"case_id": "V2-008-RC-037", "category": "PAIR", "scenario": "world mismatch across cut", "expected": "REFUSED", "enforced_by": "P4 decisive"},
    {"case_id": "V2-008-RC-038", "category": "PAIR", "scenario": "gate geometry incompatible across cut", "expected": "REFUSED", "enforced_by": "P5"},
    {"case_id": "V2-008-RC-039", "category": "PAIR", "scenario": "loitering read", "expected": "REFUSED", "enforced_by": "P6"},
    {"case_id": "V2-008-RC-040", "category": "PAIR", "scenario": "goal unclear", "expected": "REFUSED", "enforced_by": "P7"},
    {"case_id": "V2-008-RC-041", "category": "PAIR", "scenario": "outcome unclear", "expected": "REFUSED", "enforced_by": "P8"},
    {"case_id": "V2-008-RC-042", "category": "PAIR", "scenario": "F1/F3 continuity break", "expected": "REFUSED", "enforced_by": "P9"},
    {"case_id": "V2-008-RC-043", "category": "CUSTODY", "scenario": "retry after a submit", "expected": "REFUSED", "enforced_by": "durable short-circuit + budget"},
    {"case_id": "V2-008-RC-044", "category": "CUSTODY", "scenario": "third Generate", "expected": "REFUSED", "enforced_by": "budget exhausted before any call"},
    {"case_id": "V2-008-RC-045", "category": "CUSTODY", "scenario": "provider switch", "expected": "REFUSED", "enforced_by": "frozen route binding"},
    {"case_id": "V2-008-RC-046", "category": "CUSTODY", "scenario": "wrong asset mapping (cid dispatch)", "expected": "REFUSED", "enforced_by": "custody==file sha equality"},
    {"case_id": "V2-008-RC-047", "category": "CUSTODY", "scenario": "ambiguous generate effect", "expected": "FAILED_CLOSED", "enforced_by": "latch + all later authority dies"},
    {"case_id": "V2-008-RC-048", "category": "CUSTODY", "scenario": "ambiguous upload effect", "expected": "FAILED_CLOSED", "enforced_by": "upload latch; NO Generate after"},
    {"case_id": "V2-008-RC-049", "category": "CUSTODY", "scenario": "duplicate dispatch", "expected": "REFUSED", "enforced_by": "dispatch_count == 1"},
    {"case_id": "V2-008-RC-050", "category": "CUSTODY", "scenario": "wrong output identity", "expected": "REFUSED", "enforced_by": "acquired sha == receipt"},
    {"case_id": "V2-008-RC-051", "category": "DECISION", "scenario": "worker auto-select", "expected": "REFUSED", "enforced_by": "no_owner_decision_minted"},
    {"case_id": "V2-008-RC-052", "category": "DECISION", "scenario": "worker claims Owner acceptance", "expected": "REFUSED", "enforced_by": "template decision null"},
    {"case_id": "V2-008-RC-053", "category": "DECISION", "scenario": "promotion attempt in-package", "expected": "REFUSED", "enforced_by": "promotion ledger EMPTY"},
    {"case_id": "V2-008-RC-054", "category": "CANONICAL", "scenario": "canonical mutation", "expected": "UNCHANGED", "enforced_by": "master/take/manifest proofs"},
    {"case_id": "V2-008-RC-055", "category": "CANONICAL", "scenario": "canonical F2 replaced", "expected": "UNCHANGED", "enforced_by": "take sha == e84ba56c"},
    {"case_id": "V2-008-RC-056", "category": "BASELINE", "scenario": "V1 baseline mutation", "expected": "UNCHANGED", "enforced_by": "baseline constant + git custody"},
    {"case_id": "V2-008-RC-057", "category": "IDENTITY", "scenario": "identity regression in either half", "expected": "REFUSED", "enforced_by": "identity receipts + hard blocks"},
    {"case_id": "V2-008-RC-058", "category": "IDENTITY", "scenario": "world continuity auto-accepted on inconclusive", "expected": "REFUSED", "enforced_by": "no auto-accept rule"},
    {"case_id": "V2-008-RC-059", "category": "REVIEW", "scenario": "aggregate score introduced", "expected": "REFUSED", "enforced_by": "no_aggregate_score"},
    {"case_id": "V2-008-RC-060", "category": "REVIEW", "scenario": "review copies diverge", "expected": "REFUSED", "enforced_by": "sha equality"},
    {"case_id": "V2-008-RC-061", "category": "REVIEW", "scenario": "reel order tampered", "expected": "REFUSED", "enforced_by": "manifest order"},
    {"case_id": "V2-008-RC-062", "category": "REVIEW", "scenario": "question missing", "expected": "REFUSED", "enforced_by": "7 verbatim"},
    {"case_id": "V2-008-RC-063", "category": "REVIEW", "scenario": "template pre-filled", "expected": "REFUSED", "enforced_by": "decision null"},
    {"case_id": "V2-008-RC-064", "category": "FREEZE", "scenario": "semantic identity collision", "expected": "REFUSED", "enforced_by": "collision check"},
    {"case_id": "V2-008-RC-065", "category": "FREEZE", "scenario": "envelope shortening", "expected": "FAILED_CLOSED", "enforced_by": "BLOCKED_INVARIANT"},
    {"case_id": "V2-008-RC-066", "category": "FREEZE", "scenario": "F2A wire loses close-start", "expected": "REFUSED", "enforced_by": "required tokens"},
    {"case_id": "V2-008-RC-067", "category": "FREEZE", "scenario": "F2B wire loses gate-behind", "expected": "REFUSED", "enforced_by": "required tokens"},
    {"case_id": "V2-008-RC-068", "category": "FREEZE", "scenario": "story meaning drift", "expected": "REFUSED", "enforced_by": "D1 anchors"},
    {"case_id": "V2-008-RC-069", "category": "GATES", "scenario": "F2A timing invariant fail", "expected": "REFUSED", "enforced_by": "validate_timing_invariant"},
    {"case_id": "V2-008-RC-070", "category": "GATES", "scenario": "decomposition gate fail", "expected": "REFUSED", "enforced_by": "D1-D10"},
    {"case_id": "V2-008-RC-071", "category": "GATES", "scenario": "director gate fail", "expected": "REFUSED", "enforced_by": "B1-B10"},
    {"case_id": "V2-008-RC-072", "category": "MODEL", "scenario": "authorization scope exceeded", "expected": "REFUSED", "enforced_by": "scope: ONE upload + pacing delta ONLY"},
    {"case_id": "V2-008-RC-073", "category": "MODEL", "scenario": "ambiguity rule regression", "expected": "UNCHANGED", "enforced_by": "EXTERNAL_AMBIGUITY_RULE"},
    {"case_id": "V2-008-RC-074", "category": "MODEL", "scenario": "silent model downgrade", "expected": "REFUSED", "enforced_by": "receipt chain"},
    {"case_id": "V2-008-RC-075", "category": "CUSTODY", "scenario": "start HEAD drift", "expected": "REFUSED", "enforced_by": "custody start_sha equality"},
    {"case_id": "V2-008-RC-076", "category": "CUSTODY", "scenario": "frozen plan id drift", "expected": "REFUSED", "enforced_by": "custody binding"},
    {"case_id": "V2-008-RC-077", "category": "CUSTODY", "scenario": "QC verdict without evidence", "expected": "REFUSED", "enforced_by": "verdict+evidence structure"},
    {"case_id": "V2-008-RC-078", "category": "CUSTODY", "scenario": "measured times without strip basis", "expected": "REFUSED", "enforced_by": "strips bound"},
    {"case_id": "V2-008-RC-079", "category": "CUSTODY", "scenario": "alternate scope bypass", "expected": "REFUSED", "enforced_by": "single scope rule"},
    {"case_id": "V2-008-RC-080", "category": "CUSTODY", "scenario": "null-ack interpreted", "expected": "FAILED_CLOSED", "enforced_by": "EXTERNAL_AMBIGUITY_RULE"},
    {"case_id": "V2-008-RC-081", "category": "REVIEW", "scenario": "pair presented READY when refused", "expected": "REFUSED", "enforced_by": "manifest==governance"},
    {"case_id": "V2-008-RC-082", "category": "REFERENCE", "scenario": "old still trusted blindly without re-extraction", "expected": "REFUSED", "enforced_by": "deterministic re-extraction + sha compare"},
]
def main() -> int:
    reused = {"v2_001": 89, "v2_002": 28, "v2_003": 30, "v2_004": 62,
              "v2_005": 52, "v2_006": 72}
    ids = [c["case_id"] for c in PACKAGE_CASES]
    assert len(set(ids)) == len(ids) and len(PACKAGE_CASES) >= 80
    total = sum(reused.values()) + len(PACKAGE_CASES)
    output = {"version": "recovery-matrix-v2-008-v1", "count_total": total,
              "reused_cases": {"count": sum(reused.values()),
                               "breakdown": reused},
              "package_cases": {"count": len(PACKAGE_CASES),
                                "executed_by":
                                    "tests/test_v2_008_recovery_001.py",
                                "cases": PACKAGE_CASES},
              "external_ambiguity_rule": "OWNER_AMBIGUITY_GATE"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"count_total": total,
                      "package_cases": len(PACKAGE_CASES)}))
if __name__ == "__main__":
    main()
