"""FLOW-PRODUCTION-SCALE-007 (L14) — large-run recovery matrix (58 scenarios).

Each package-mandated scenario maps to an exact proof:
- "pytest": specific collected test nodes (executed fresh by this tool in
  ONE pytest invocation with --junitxml; results joined back per row);
- "evidence": durable live-run artifacts from this package (each verified
  read-only here: file exists + expected content marker).

Output: projects/flow_production_scale_007/master_package_007/
recovery_matrix.json (machine-readable, per-row results).
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects/flow_production_scale_007/master_package_007"
RUN_DIR = ROOT / "projects/flow_production_scale_007"

S = "tests/"

EVIDENCE_ROWS = {
    34: ("repair releases durably proven (2/3 budget)",
         RUN_DIR / "generate_ledger.json",
         lambda d: len(d.get("repair_consumed", [])) == 2),
    28: ("armed-but-unresolved upload reconciled read-only (F2, G2); "
         "no re-upload",
         RUN_DIR / "sequence_SEQ007_DAYLIGHT_ROAD/scene_SCENE_F_STORM_GATE/"
         "continuity_ledger.json",
         lambda d: any(b.get("reconciled") for b in d.get("bindings", []))),
    31: ("conditioned shot restart after reconciliation: F2/G2 re-entered "
         "loudly and proven",
         RUN_DIR / "reentry_record.json",
         lambda d: bool(d.get("reentries"))),
    37: ("stale original take not selected: master manifest carries "
         "successor takes for repaired slots",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "no_stale_primary_takes" and
                       c.get("verdict") == "PASS" for c in d.get("checks",
                                                                  []))),
}

ROWS = [
    (1, "ProductionRun", "fresh run start; durable state created",
     "pytest", [S + "test_scale_orchestrator.py::test_full_30_slot_scale_run"]),
    (2, "ProductionRun", "adopted historical run enters read-only",
     "pytest", [S + "test_scale_orchestrator.py::test_adopted_sequence_never_calls_live_executor"]),
    (3, "ProductionRun", "historical hash drift refused",
     "pytest", [S + "test_editorial_range.py::test_wrong_asset_revalidation_refused",
                S + "test_editorial_range.py::test_hash_mismatch_refused",
                S + "test_production_run.py::test_adopted_snapshot_fails_on_unproven_or_missing"]),
    (4, "ProductionRun", "fresh live sequence start (restart at slot 1)",
     "pytest", [S + "test_scale_orchestrator.py::test_restart_never_regenerates_completed_slots[slot-1]"]),
    (5, "ProductionRun", "mid-sequence restart (slot N/2)",
     "pytest", [S + "test_scale_orchestrator.py::test_restart_never_regenerates_completed_slots[slot-N/2]"]),
    (6, "ProductionRun", "between-scenes: stale PROVEN without result refused",
     "pytest", [S + "test_scale_orchestrator.py::test_missing_earlier_scene_result_refused_on_resume"]),
    (7, "ProductionRun", "final-shot restart",
     "pytest", [S + "test_scale_orchestrator.py::test_restart_never_regenerates_completed_slots[final-slot]"]),
    (8, "ProductionRun", "whole-run plan hash drift refused (incl. editorial targets)",
     "pytest", [S + "test_scale_orchestrator.py::test_whole_run_plan_hash_drift_refused",
                S + "test_scale_orchestrator.py::test_editorial_target_drift_refused"]),
    (9, "ProductionRun", "out-of-order scene results refused",
     "pytest", [S + "test_scale_orchestrator.py::test_out_of_order_scene_result_refused"]),
    (10, "ProductionRun", "out-of-order / wrong-slot shot results refused",
     "pytest", [S + "test_scale_orchestrator.py::test_out_of_order_shot_result_refused",
                S + "test_scale_orchestrator.py::test_wrong_shot_result_refused"]),
    (11, "Provider", "durable reservation; crash before submit never reaches provider",
     "pytest", [S + "test_live_runtime.py::test_crash_after_durable_reservation_never_reaches_submit_on_restart"]),
    (12, "Provider", "release facts preserved; never resubmit",
     "pytest", [S + "test_dispatch_recovery.py::test_crash_windows_preserve_immediate_facts_and_never_resubmit"]),
    (13, "Provider", "timeout/ambiguity reconciles without blind redispatch",
     "pytest", [S + "test_live_runtime.py::test_submit_timeout_restart_reconciles_without_blind_redispatch"]),
    (14, "Provider", "ambiguity latches authority closed (durable, one-way)",
     "pytest", [S + "test_mutation_authority_latch.py::test_generate_ambiguity_latches_closed",
                S + "test_mutation_authority_latch.py::test_latch_survives_restart",
                S + "test_mutation_authority_latch.py::test_latch_is_one_way"]),
    (15, "Provider", "render pending is not failure and grants no retry",
     "pytest", [S + "test_flow_render_lifecycle.py::test_render_pending_is_not_failure_and_not_retry_authority"]),
    (16, "Provider", "unknown render payload unobservable; blocks submission",
     "pytest", [S + "test_flow_render_lifecycle.py::test_arbitrary_non_null_object_is_unobservable_not_pending",
                S + "test_flow_render_lifecycle.py::test_restart_after_unknown_payload_still_blocks_submission"]),
    (17, "Provider", "render completed observed; acquire-only after restart",
     "pytest", [S + "test_flow_render_lifecycle.py::test_render_completed_observed",
                S + "test_flow_render_lifecycle.py::test_restart_after_render_completed_keeps_acquire_only"]),
    (18, "Provider", "drop threshold count not met stays unresolved",
     "pytest", [S + "test_flow_render_lifecycle.py::test_disappearances_one_and_two_stay_unresolved"]),
    (19, "Provider", "drop requires threshold AND minimum elapsed window",
     "pytest", [S + "test_flow_render_lifecycle.py::test_threshold_inside_minimum_window_is_still_unresolved",
                S + "test_flow_render_lifecycle.py::test_threshold_plus_minimum_elapsed_window_terminal_drop"]),
    (20, "Provider", "acquisition validates, hashes and persists lineage",
     "pytest", [S + "test_live_runtime.py::test_successful_submit_reconciles_exact_output_ids_and_persists_lineage"]),
    (21, "Provider", "acquisition tamper refused (fake media / receipt mismatch)",
     "pytest", [S + "test_live_runtime.py::test_html_renamed_as_mp4_is_rejected",
                S + "test_recovery_matrix_002.py::test_receipt_bytes_mismatch_fails_closed"]),
    (22, "Provider", "marker binding: exact single reference + marker required",
     "pytest", [S + "test_canonical_reference_binding.py::test_native_text_ast_requires_exact_single_reference_and_marker"]),
    (23, "Provider", "duplicate/ambiguous candidate conflation rejected",
     "pytest", [S + "test_canonical_reference_binding.py::test_canonical_success_and_geometric_conflation_rejected"]),
    (24, "Provider", "wrong project/scope binding blocks mutation",
     "pytest", [S + "test_canonical_reference_binding.py::test_ui_chip_wrong_id_blocks_mutation",
                S + "test_dispatch_recovery.py::test_wrong_request_response_and_secret_keys_are_rejected"]),
    (25, "Provider", "wrong reference resource rejected at binding",
     "pytest", [S + "test_canonical_reference_binding.py::test_binding_rejects_wrong_resource_or_metadata"]),
    (26, "Continuity", "last-frame extraction deterministic",
     "pytest", [S + "test_recovery_matrix_007.py::test_last_frame_extraction_deterministic"]),
    (27, "Continuity", "upload identity durable before readback (reserved)",
     "pytest", [S + "test_reference_reconcilable_transport.py::test_normal_identity_is_durable_before_readback"]),
    (28, "Continuity", "upload ambiguity: armed/unresolved → read-only reconcile, never re-upload",
     "mixed", [S + "test_reference_reconcilable_transport.py::test_lost_or_unparsed_response_readonly_reconciliation"], 28),
    (29, "Continuity", "upload resolved: crash after identity re-verifies only",
     "pytest", [S + "test_reference_reconcilable_transport.py::test_crash_after_identity_restarts_verification_only"]),
    (30, "Continuity", "reference readback mismatch rejected",
     "pytest", [S + "test_reference_adoption.py::test_verify_rejects_wrong_media_identity",
                S + "test_reference_adoption.py::test_verify_rejects_changed_local_bytes"]),
    (31, "Continuity", "conditioned shot restart after upload reconciliation",
     "evidence", [], 31),
    (32, "Repair", "repair decision exists before any repair mutation",
     "pytest", [S + "test_qc_kernel.py::test_human_rejection_makes_repair_without_transport_retry"]),
    (33, "Repair", "repair budget ceiling enforced",
     "pytest", [S + "test_recovery_matrix_007.py::test_repair_budget_ceiling_enforced"]),
    (34, "Repair", "repair releases durably proven (2/3)",
     "evidence", [], 34),
    (35, "Repair", "repair restart routes via terminal drop decision",
     "pytest", [S + "test_flow_render_lifecycle.py::test_restart_after_drop_routes_to_repair"]),
    (36, "Repair", "original and repair coexist; canonical = successor",
     "pytest", [S + "test_recovery_matrix_007.py::test_repair_successor_canonical_over_stale_original"]),
    (37, "Repair", "stale original take not selected in master",
     "evidence", [], 37),
    (38, "Editorial", "invalid negative source_in refused",
     "pytest", [S + "test_editorial_range.py::test_invalid_negative_in"]),
    (39, "Editorial", "out-of-bounds source_out refused",
     "pytest", [S + "test_editorial_range.py::test_out_of_bounds_out"]),
    (40, "Editorial", "zero-duration range refused",
     "pytest", [S + "test_editorial_range.py::test_zero_duration_refused"]),
    (41, "Editorial", "asset duration drift refused on revalidation",
     "pytest", [S + "test_editorial_range.py::test_asset_duration_drift_refused"]),
    (42, "Editorial", "stale asset (hash mismatch) refused",
     "pytest", [S + "test_editorial_range.py::test_wrong_asset_revalidation_refused"]),
    (43, "Editorial", "wrong take changes range identity",
     "pytest", [S + "test_editorial_range.py::test_identity_is_deterministic_and_field_sensitive"]),
    (44, "Editorial", "duplicate clip order in manifest refused",
     "pytest", [S + "test_editorial_slice.py::test_manifest_identity_order_trim_and_machine_path_independence"]),
    (45, "Editorial", "wrong slot order result refused",
     "pytest", [S + "test_scale_orchestrator.py::test_wrong_scene_result_refused_on_resume"]),
    (46, "Editorial", "range survives restart roundtrip",
     "pytest", [S + "test_editorial_range.py::test_write_read_restart_roundtrip"]),
    (47, "Editorial", "range serialization tamper caught by identity",
     "pytest", [S + "test_editorial_range.py::test_write_read_conflict_then_identity_readback"]),
    (48, "AutoEdit", "missing source / wrong hash refused at resolution",
     "pytest", [S + "test_editorial_slice.py::test_invalid_source_bounds_target_missing_and_wrong_hash"]),
    (49, "AutoEdit", "wrong checksum requires actual byte verification",
     "pytest", [S + "test_autoedit_compatibility.py::test_hash_mismatch_requires_actual_byte_verification"]),
    (50, "AutoEdit", "wrong range: filtergraph honors trims per clip",
     "pytest", [S + "test_editorial_slice.py::test_multi_clip_filtergraph_orders_trims_normalizes_and_preserves_audio"]),
    (51, "AutoEdit", "producer package tamper and overwrite rejected",
     "pytest", [S + "test_autoedit_compatibility.py::test_package_tamper_and_overwrite_are_rejected"]),
    (52, "AutoEdit", "output receipt/bytes mismatch fails closed",
     "pytest", [S + "test_recovery_matrix_002.py::test_receipt_bytes_mismatch_fails_closed"]),
    (53, "AutoEdit", "master byte tamper: changed validated bytes not recovered",
     "pytest", [S + "test_dispatch_recovery.py::test_changed_validated_bytes_are_not_recovered",
                S + "test_qc_kernel.py::test_changed_asset_before_human_approval_cannot_commit_selected_take"]),
    (54, "AutoEdit", "stale master: immutable single receipt per manifest",
     "pytest", [S + "test_editorial_slice.py::test_real_sqlite_approved_resolution_persistence_and_rejections"]),
    (55, "AutoEdit", "V1/V2 confusion: portable locators reject machine paths",
     "pytest", [S + "test_autoedit_compatibility.py::test_portable_locator_schema_rejects_machine_paths_and_traversal"]),
    (56, "Authority", "old latched scope refuses every mutation path",
     "pytest", [S + "test_mutation_authority_latch.py::test_successor_and_repair_paths_cannot_bypass_latch",
                S + "test_mutation_authority_latch.py::test_scene_resume_cannot_bypass_latch"]),
    (57, "Authority", "unused budget cannot be consumed after latch",
     "pytest", [S + "test_mutation_authority_latch.py::test_unused_generate_budget_cannot_be_consumed_after_latch",
                S + "test_mutation_authority_latch.py::test_unused_upload_budget_cannot_be_consumed_after_latch"]),
    (58, "Authority", "fresh Owner-authorized scope starts OPEN",
     "pytest", [S + "test_mutation_authority_latch.py::test_new_owner_authorized_scope_starts_fresh"]),
]


def main() -> None:
    pytest_nodes = sorted({node for row in ROWS if row[3] != "evidence"
                           for node in row[4]})
    junit = OUT / "recovery_matrix_junit.xml"
    completed = subprocess.run(
        ["uv", "run", "pytest", *pytest_nodes, "-q", "--junitxml",
         str(junit)], cwd=str(ROOT), capture_output=True, text=True,
        timeout=1800, check=False)
    results = {}
    if junit.exists():
        tree = ET.parse(junit)
        for case in tree.iter("testcase"):
            classname, name = case.get("classname"), case.get("name")
            base = name.split("[")[0]
            failed = case.find("failure") is not None or \
                case.find("error") is not None
            skipped = case.find("skipped") is not None
            verdict = "FAIL" if failed else "SKIP" if skipped else "PASS"
            key = f"{classname}.{base}"
            prior = results.get(key)
            results[key] = ("FAIL" if "FAIL" in (prior, verdict)
                            else "SKIP" if "SKIP" in (prior, verdict)
                            else "PASS")
    rows_out = []
    for row in ROWS:
        num, klass, scenario, kind, nodes = row[0], row[1], row[2], row[3], \
            row[4]
        entry = {"id": num, "class": klass, "scenario": scenario,
                 "proof_kind": kind, "result": "PASS"}
        if kind in ("pytest", "mixed"):
            verdicts = []
            for node in nodes:
                mod = node.split("::")[0][:-3].replace("/", ".").replace(
                    "\\", ".")
                test = node.split("::")[-1].split("[")[0]
                key = f"{mod}.{test}"
                verdicts.append(results.get(key, "NOT_RUN"))
            entry["proofs"] = [{"type": "pytest", "node": n, "result": v}
                               for n, v in zip(nodes, verdicts)]
            if any(v != "PASS" for v in verdicts):
                entry["result"] = "FAIL"
        if kind in ("evidence", "mixed"):
            num_key = row[5]
            _desc, path, check = EVIDENCE_ROWS[num_key]
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                ok = bool(check(data))
                entry.setdefault("proofs", []).append(
                    {"type": "evidence", "path": str(path),
                     "result": "PASS" if ok else "FAIL"})
                if not ok:
                    entry["result"] = "FAIL"
            except (OSError, json.JSONDecodeError) as exc:
                entry.setdefault("proofs", []).append(
                    {"type": "evidence", "path": str(path),
                     "result": f"ERROR: {exc}"})
                entry["result"] = "FAIL"
        rows_out.append(entry)
    passed = sum(1 for r in rows_out if r["result"] == "PASS")
    matrix = {"version": "recovery-matrix-007-v1",
              "scenario_count": len(rows_out), "passed": passed,
              "failed": len(rows_out) - passed, "rows": rows_out}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "recovery_matrix.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"scenario_count": len(rows_out), "passed": passed,
                      "failed": len(rows_out) - passed}))
    if passed != len(rows_out):
        for r in rows_out:
            if r["result"] != "PASS":
                print(json.dumps(r), flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
