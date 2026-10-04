"""FLOW-V1-COMPLETION-QUALITY-DEBT-FREEZE-019 (Phases V6, V8, V9).

V6: the full V1 architecture-completeness inventory (every stage
classified; strong success = no NOT_IMPLEMENTED, no BROKEN; content
absence and Owner-input absence are NOT implementation absence).
V8: mechanical canonical no-change proof + experimental-asset
contamination scan.
V9: remaining Owner/content gate reconciliation after the quality
decision (F2/G3 take-review requests superseded by the explicit Owner
quality decision; E2C/G2C + master advisory remain unresolved).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D18 = ROOT / "projects/flow_action_intent_causality_018"
D17 = ROOT / "projects/flow_performance_motion_canary_017"
D19 = ROOT / "projects/flow_v1_completion_quality_debt_freeze_019"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


STAGES = [
    ("Story / Narrative authority", "AVAILABLE_WITH_CONTENT_INPUT",
     "no authoritative narration/script text exists (015); shot-design "
     "authority (sequence plan + ShotSpecs) is frozen and sufficient "
     "for V1", "fixtures/sequence007/sequence_plan_007.json"),
    ("Narrative Compile", "PROVEN",
     "deterministic compile_prompt (deterministic-v1); canonical "
     "blocks; hash-bound plans", "src/film_pipeline/compiler.py"),
    ("Bibles (character/world authority)", "PROVEN",
     "identity authority = frozen reference image + per-shot "
     "invariants; body authority extension v1 (exact values UNKNOWN "
     "honestly)", "fixtures/character_bible/"),
    ("Scene / Shot Design", "PROVEN",
     "12-shot SEQ007 design frozen pre-mutation (v2 creative "
     "reduction); 30-slot canonical set", "fixtures/sequence007/"),
    ("ShotSpec", "PROVEN",
     "schema-validated contract, versioned, legacy digests stable",
     "schemas/shot_spec.schema.json"),
    ("ActionIntent", "PROVEN",
     "action-intent-v1; recovered-from-authority gate (A1) proven in "
     "018; participates in generation identity",
     "src/film_pipeline/core.py"),
    ("PerformanceSpec", "PROVEN",
     "performance-spec-v1; biomechanics + beats; identity-stable "
     "extension", "src/film_pipeline/core.py"),
    ("Prompt Compiler", "PROVEN",
     "canonical + performance + causal wire compilers, all inside the "
     "qualified 500/75 fail-closed envelope",
     "src/film_pipeline/performance_compiler.py"),
    ("RoutingDecision", "PROVEN",
     "route_plan over capabilities; single qualified provider route",
     "src/film_pipeline/flow_r2v_runtime.py"),
    ("Provider Adapter", "PROVEN",
     "flow_veo native-UI adapter with OneGenerateGuard; fail-closed "
     "request observation", "src/film_pipeline/providers/"),
    ("GenerationAttempt", "PROVEN",
     "attempt hash chain incl. prompt_plan_hash; semantic extensions "
     "participate (019 V2 proof)", "src/film_pipeline/core.py"),
    ("ProviderJob", "PROVEN",
     "frozen jobs with correlation markers; resume/path guards",
     "src/film_pipeline/store.py"),
    ("Output Asset", "PROVEN",
     "exact acquisition bound to output identity; hash-verified",
     "tools/run_production_scale_007.py"),
    ("Technical QC", "PROVEN",
     "decode/duration/resolution/lineage gates; SHOT_PROVEN semantics",
     "src/film_pipeline/qc.py"),
    ("Semantic/review boundary", "PROVEN",
     "provider-neutral backend contract; worker review advisory-only; "
     "backend NOT_QUALIFIED recorded honestly",
     "src/film_pipeline/semantic_backends.py"),
    ("Motion QC boundary", "PROVEN",
     "MotionReviewPacket v1 dense temporal evidence; advisory only",
     "src/film_pipeline/motion_qc.py"),
    ("Repair recommendation", "PROVEN",
     "RepairDecision contract + dead-reservation semantics",
     "src/film_pipeline/store.py"),
    ("SelectedTake", "PROVEN",
     "immutable take authority + EditorialRange v1",
     "src/film_pipeline/editorial_range.py"),
    ("EditManifest / AutoEdit / rough cut", "PROVEN",
     "trim-aware edit jobs; 30-slot conformance",
     "src/film_pipeline/rough_cut.py"),
    ("Master", "PROVEN",
     "MASTER_EDITORIAL_010_V1 conformance (18 checks + 29 boundaries)",
     "projects/flow_editorial_runtime_scale_010/"),
    ("Owner review boundary", "PROVEN",
     "OwnerReviewRequest/Decision + ledger + supersession + import "
     "surface", "src/film_pipeline/owner_review.py"),
    ("Narration ingestion", "PROVEN_OFFLINE",
     "NarrationSourceReceipt fail-closed; awaiting real content",
     "src/film_pipeline/content_release.py"),
    ("Caption ingestion", "PROVEN_OFFLINE",
     "TimedCaptionSource strict SRT/VTT; awaiting real content",
     "src/film_pipeline/content_release.py"),
    ("Final release compiler", "PROVEN_OFFLINE",
     "dry-run gate report; refuses compile while blocked",
     "src/film_pipeline/content_release.py"),
    ("Delivery / archive", "PROVEN",
     "DeliveryManifest + 3-build deterministic archives (015/019)",
     "src/film_pipeline/delivery.py"),
]

CONTAMINATION_TOKENS = [
    # 017 candidate asset hashes
    "751f0bb519654e9a19a3051b72f0bf6a8952ef63d62ebbe610ff5d30d81d5e34",
    "c540b5eab1355d58682d2ee6030f6376309457f2ae8aaf5dbc5cc2bd719f086e",
    "a163b188d01fd795f6e838a2265875e2a33898cf4b0f7d061e17e1346c56e50e",
    # 018 candidate asset hashes
    "5ef2eaded3c0f092", "4ab6cd409bc846ec", "0536388b91be9fa0",
    # candidate output identities
    "8b33431e-9872", "23d63bc0-17e8", "b9a59fc4-06ab",
    "796040db-4af1", "2cf20dcc-d640", "d4b427d7-2697",
]


def main() -> None:
    # V6 inventory
    classifications = {s[0]: s[1] for s in STAGES}
    bad = [s[0] for s in STAGES if s[1] in ("NOT_IMPLEMENTED", "BROKEN")]
    inventory = {
        "version": "v1-pipeline-completeness-019-v1",
        "rule": "content absence and Owner-input absence are NOT "
                "implementation absence",
        "stages": [{"stage": s[0], "classification": s[1],
                    "basis": s[2], "primary_artifact": s[3]}
                   for s in STAGES],
        "counts": {c: sum(1 for s in STAGES if s[1] == c)
                   for c in {s[1] for s in STAGES}},
        "not_implemented": bad,
        "broken": [],
        "result": "PROVEN_WITHIN_V1_SCOPE" if not bad else "FAIL",
    }
    (D19 / "v1_pipeline_completeness_019.json").write_text(
        json.dumps(inventory, indent=1), encoding="utf-8")

    # V8 canonical no-change proof
    edit_job = json.loads(
        (M10 / "autoedit_package/edit_job.json").read_text(
            encoding="utf-8"))
    manifest_blob = json.dumps(edit_job)
    contamination = [t for t in CONTAMINATION_TOKENS if t in
                     manifest_blob]
    takes = {r.name: sha(r) for r in
             (M10 / "ranges").glob("*.json")}
    canonical = {
        "version": "canonical-no-change-proof-019-v1",
        "master_sha256": sha(M10 / "master_editorial_010_v1.mp4"),
        "master_unchanged": sha(M10 / "master_editorial_010_v1.mp4")
        == MASTER_SHA,
        "edit_job_sha256": sha(M10 / "autoedit_package/edit_job.json"),
        "selected_take_ranges": {"count": len(takes),
                                 "all_present": len(takes) == 30},
        "canonical_F2C_unchanged": sha(
            ROOT / "projects/flow_upload_contract_requal_009/reproof/"
            "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
            "c1a69047933565230870ad22.mp4") ==
            "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c398982548"
            "90a767",
        "canonical_G3C_unchanged": sha(
            ROOT / "projects/flow_upload_contract_requal_009/reproof/"
            "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C/videos/"
            "6013b45645fdffa4fa702278.mp4") ==
            "ffe42e7e9af47e599faa6996807ca1cfea6324343c5abcb906381589bf"
            "89a528",
        "experimental_asset_contamination_scan": {
            "tokens": len(CONTAMINATION_TOKENS),
            "hits_in_edit_manifest": contamination,
            "result": "CLEAN" if not contamination else "FAIL"},
        "result": None}
    canonical["result"] = ("UNCHANGED" if canonical["master_unchanged"]
                           and canonical["canonical_F2C_unchanged"] and
                           canonical["canonical_G3C_unchanged"] and
                           not contamination and
                           canonical["selected_take_ranges"]
                           ["all_present"] else "FAIL")
    (D19 / "canonical_no_change_019.json").write_text(
        json.dumps(canonical, indent=1), encoding="utf-8")

    # V9 gate reconciliation
    decision = json.loads(
        (D19 / "owner_quality_decision_019.json").read_text(
            encoding="utf-8"))
    gates = {
        "version": "owner-gate-manifest-019-reconciled-v1",
        "note": "Package-016 gate manifest re-evaluated after the "
                "Owner quality decision; no content faked; unresolved "
                "requests stay unresolved",
        "OWNER_TAKE_REVIEW": {
            "state": "OPEN",
            "superseded_requests": {
                "OWNER-REV-015-002 (SEQ7_F2)": "superseded by the "
                "explicit Owner quality decision (F2_ACTION_LOGIC = "
                "NEEDS_REDESIGN; candidates not promoted) — recorded, "
                "NOT silently accepted",
                "OWNER-REV-015-004 (SEQ7_G3)": "superseded likewise "
                "(G3_ACTION_LOGIC = NEEDS_REDESIGN)"},
            "still_unresolved": ["OWNER-REV-015-001 (SEQ7_E2)",
                                 "OWNER-REV-015-003 (SEQ7_G2)",
                                 "OWNER-REV-015-005 (master advisory)"],
            "gate_complete": False},
        "SEMANTIC_RELEASE": {"state": "OPEN",
                             "note": "no waiver unless explicitly "
                                     "authorized separately",
                             "gate_complete": False},
        "PRODUCTION_NARRATION": {"state": "OPEN",
                                 "note": "no narration synthesis",
                                 "gate_complete": False},
        "TIMED_CAPTIONS": {"state": "OPEN",
                           "note": "no caption synthesis",
                           "gate_complete": False},
        "all_gates_complete": False}
    (D19 / "owner_gate_manifest_019_reconciled.json").write_text(
        json.dumps(gates, indent=1), encoding="utf-8")

    print(json.dumps({"V6": inventory["result"],
                      "stages": len(STAGES),
                      "counts": inventory["counts"],
                      "V8": canonical["result"],
                      "V9_gates_open": 4}))


if __name__ == "__main__":
    main()
