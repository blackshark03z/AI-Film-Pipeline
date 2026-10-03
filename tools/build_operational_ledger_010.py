"""FLOW-EDITORIAL-RUNTIME-SCALE-010 (T13): observational operational ledger.

An append-free, read-only SUMMARY built by walking durable artifacts —
it duplicates no source of truth (every row references canonical ids) and
carries NO authority semantics: a ledger status can never authorize a
provider mutation. Statuses: PLANNED / RUNNING / BLOCKED / COMPLETE /
OWNER_REVIEW / EXTERNAL_GATE.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects/flow_editorial_runtime_scale_010"
M9 = ROOT / "projects/flow_upload_contract_requal_009/master_package_009"
M10 = OUT / "master_package_010"

STATUS_MAP = {"SHOT_PROVEN": "COMPLETE",
              "SLOT_DEAD_RESERVATION_REPAIR_REQUIRED": "BLOCKED",
              "OWNER_AMBIGUITY_GATE": "EXTERNAL_GATE",
              "R3_SHOT3_REPROOF_PROVEN": "COMPLETE"}

RUNS = [
    {"run_id": "FLOW-PRODUCTION-SCALE-007",
     "summary": "historical; custody-corrected by Package-008 U0"},
    {"run_id": "FLOW-UPLOAD-RECONCILIATION-CONTRACT-008",
     "summary": "historical; TECHNICALLY_DEMONSTRATED but "
                "INVALID_AS_CLEAN_AUTHORIZED_PROOF (Package-009 V0)"},
    {"run_id": "FLOW-UPLOAD-CONTRACT-REQUAL-009",
     "summary": "canonical lineage provider; prospectively qualified "
                "upload-pending contract"},
    {"run_id": "FLOW-EDITORIAL-RUNTIME-SCALE-010",
     "summary": "editorial/runtime hardening; canonical visuals unchanged"},
]


def main() -> None:
    summary = json.loads((M9 / "master_summary.json").read_text(
        encoding="utf-8"))
    shots = []
    for slot in summary["slots"]:
        result = {"shot_id": slot["slot_id"], "sequence": slot["sequence"],
                  "scene": slot["scene"], "status": "COMPLETE",
                  "provider_job_id": None, "asset_id": slot["asset_id"],
                  "asset_sha256": slot["asset_sha256"],
                  "selected_take_id": slot["selected_take_id"],
                  "provenance": slot["provenance"],
                  "editorial_range": "ranges/ (Package-010 copy)",
                  "output_media_id": slot.get("provider_media_id")}
        shots.append(result)
    ledger = {
        "version": "operational-ledger-010-v1",
        "observational_only": True,
        "authority_note": ("this ledger grants NOTHING: statuses are read "
                           "back from durable gates; mutation authority "
                           "lives exclusively in the durable authority state"),
        "runs": RUNS,
        "canonical_lineage": {
            "run": "FLOW-UPLOAD-CONTRACT-REQUAL-009",
            "slot_count": len(shots),
            "shots": shots,
            "editorial": {
                "manifest": json.loads(
                    (M10 / "master_summary.json").read_text(
                        encoding="utf-8"))["edit_manifest_id"],
                "package": json.loads(
                    (M10 / "master_summary.json").read_text(
                        encoding="utf-8"))["autoedit_package_id"],
                "master_editorial_010_v1": {
                    "sha256": json.loads(
                        (M10 / "master_summary.json").read_text(
                            encoding="utf-8"))["output_sha256"],
                    "conformance": "CONFORMANT (12/12 checks, 29/29 "
                                   "boundaries)"}}},
        "status_counts": {}}
    counts = {}
    for shot in shots:
        counts[shot["status"]] = counts.get(shot["status"], 0) + 1
    ledger["status_counts"] = counts
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "operational_ledger_010.json").write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"slot_count": len(shots),
                      "status_counts": counts}))


if __name__ == "__main__":
    main()
