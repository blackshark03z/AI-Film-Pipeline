"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phase 11 + 12): run the final
content release compiler in dry-run gate-report mode against canonical
truth, and record the semantic waiver boundary status.

Canonical inputs: the Package-010 master receipt + the DeliveryManifest
truth of delivery_014 + an input bundle bound to the canonical master
(no content inputs yet). Expected result: FINAL_CONTENT_RELEASE_BLOCKED
with the exact remaining gates derived — not assumed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.content_release import (
    ContentReleaseInputBundle, FinalContentReleaseCompiler)

D14 = ROOT / "projects/flow_worker_semantic_backend_014"
D15 = ROOT / "projects/flow_owner_review_content_gates_015"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"


def main() -> None:
    master_receipt = json.loads(
        (M10 / "master_summary.json").read_text(encoding="utf-8"))
    manifest_truth = json.loads(
        (D14 / "delivery_014/manifests/delivery_manifest.json").read_text(
            encoding="utf-8"))
    bundle = ContentReleaseInputBundle(
        project="swordsman_film", master_sha256=MASTER_SHA,
        canonical_lineage_version="master-editorial-010-v1",
        notes="no content inputs yet; dry-run gate report")
    compiler = FinalContentReleaseCompiler(
        project="swordsman_film", master_receipt=master_receipt,
        manifest_truth=manifest_truth, bundle=bundle,
        semantic_autonomous_ready=False, semantic_waiver=None)
    report = compiler.gate_report()

    # the frozen release-contract truth drives the semantic gate policy:
    # Package-011 authorizes "a semantic model that passes the frozen
    # corpus OR an Owner waiver". No waiver decision exists yet.
    waiver_status = {
        "version": "semantic-waiver-status-015-v1",
        "boundary": "SEMANTIC_WAIVER_BOUNDARY = AUTHORIZED",
        "authority_basis": ("Package-011 release contract: release "
                            "requires Owner review + either a semantic "
                            "model that passes the frozen corpus or an "
                            "Owner waiver (docs/operating/"
                            "FLOW_SEMANTIC_DELIVERY_011_EVIDENCE.md "
                            "section 12)"),
        "decision_present": False,
        "effect_when_present": "SEMANTIC_QC_GATE = OWNER_WAIVED for the "
                               "release gate only",
        "truth_unchanged": {
            "WORKER_SEMANTIC_BACKEND": "NOT_QUALIFIED",
            "SEMANTIC_AUTONOMOUS_READY": False,
            "rule": "a waiver NEVER rewrites semantic observations to "
                    "PASS and never flips SEMANTIC_AUTONOMOUS_READY"},
        "schema": "SemanticQCWaiverDecision v1 "
                  "(src/film_pipeline/content_release.py): project, "
                  "exact master sha256, reason, known limitations, "
                  "date, decision_source = OWNER",
        "no_hidden_bypass": "the waiver is a recorded Owner decision "
                            "object; there is no flag, default, or "
                            "implicit route that waives the gate"}

    D15.mkdir(parents=True, exist_ok=True)
    (D15 / "final_release_gate_report_015.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8")
    (D15 / "semantic_waiver_status_015.json").write_text(
        json.dumps(waiver_status, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"release_state": report["release_state"],
                      "blocked_gates": report["blocked_gates"],
                      "waiver_boundary": waiver_status["boundary"]}))


if __name__ == "__main__":
    main()
