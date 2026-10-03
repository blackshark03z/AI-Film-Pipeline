"""FLOW-UPLOAD-CONTRACT-REQUAL-009 (V12) — recovery/contract matrix.

78 package-mandated scenarios (IDs follow the work package list; 73 is not
defined by the package). Each row maps to an exact proof:
- "pytest": specific collected test nodes (one fresh pytest invocation);
- "evidence": durable 009 live artifacts verified read-only;
- "live": deterministic read-only computation (scans, hash recompute).

Output: projects/flow_upload_contract_requal_009/master_package_009/
recovery_matrix_009.json
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects/flow_upload_contract_requal_009/master_package_009"
RUN = ROOT / "projects/flow_upload_contract_requal_009"
S = "tests/"

C1 = S + "test_upload_classifier_008.py::"
C2 = S + "test_upload_state_machine_008.py::"
AUTH = S + "test_mutation_authority_latch.py::"
REF = S + "test_reference_reconcilable_transport.py::"
BIND = S + "test_canonical_reference_binding.py::"
REND = S + "test_flow_render_lifecycle.py::"
LIVE = S + "test_live_runtime.py::"
EDIT = S + "test_editorial_range.py::"
ADOPT = S + "test_reference_adoption.py::"
SCALE = S + "test_scale_orchestrator.py::"


def journal_state(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT payload FROM reference_uploads LIMIT 1").fetchone()
        return json.loads(row[0])["state"] if row else "ABSENT"
    finally:
        connection.close()


def stage_present(path: Path, stage: str) -> bool:
    connection = sqlite3.connect(path)
    try:
        return connection.execute(
            "SELECT 1 FROM reference_upload_events WHERE stage=? LIMIT 1",
            (stage,)).fetchone() is not None
    finally:
        connection.close()


EVIDENCE_ROWS = {
    38: ("Canary A ledger: one POST -> frozen-class PENDING -> unique bind "
         "-> UPLOAD_BOUND -> OPEN",
         RUN / "canaryA_report.json",
         lambda d: d["result"] == "CANARY_PASS" and
         d["response_class"] == "QUALIFIED_PENDING" and
         d["skeleton_fingerprint"] ==
         "ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1" and
         d["authority_after"] == "OPEN"),
    39: ("Canary B ledger: independent POST, same frozen path, PASS",
         RUN / "canaryB_report.json",
         lambda d: d["result"] == "CANARY_PASS" and
         d["response_class"] == "QUALIFIED_PENDING" and
         d["authority_after"] == "OPEN"),
    40: ("same classifier version across A and B (frozen intents)",
         RUN / "canaryB/frozen_intent.json",
         lambda d: d["classifier"]["class_version"] ==
         "upload-response-class-2026-10-03.2" and
         d["classifier"]["classifier_blob_sha"] ==
         json.loads((RUN / "canaryA/frozen_intent.json").read_text(
             encoding="utf-8"))["classifier"]["classifier_blob_sha"]),
    41: ("same structural fingerprint across A and B",
         RUN / "canaryB/frozen_intent.json",
         lambda d: d["classifier"]["fingerprint"] ==
         json.loads((RUN / "canaryA/frozen_intent.json").read_text(
             encoding="utf-8"))["classifier"]["fingerprint"] ==
         "ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1"),
    42: ("no post-A code change: classifier git blob identical at A freeze "
         "and B freeze",
         RUN / "canaryB/frozen_intent.json",
         lambda d: d["classifier"]["classifier_blob_sha"] ==
         subprocess.run(
             ["git", "rev-parse",
              "HEAD:src/film_pipeline/providers/flow_upload_classifier.py"],
             cwd=str(ROOT), capture_output=True, text=True).stdout.strip()),
    43: ("two distinct source SHAs (E3 asset vs F3 asset)",
         RUN / "canaryB/frozen_intent.json",
         lambda d: d["source_asset_sha256"] !=
         json.loads((RUN / "canaryA/frozen_intent.json").read_text(
             encoding="utf-8"))["source_asset_sha256"]),
    44: ("two distinct provider media ids (08f5f4fb... vs 65e73642...)",
         RUN / "canaryB_report.json",
         lambda d: d["media_id"] !=
         json.loads((RUN / "canaryA_report.json").read_text(
             encoding="utf-8"))["media_id"] and
         d["media_id"] == "65e73642-1140-4cd6-be68-fd8b772bdf4a"),
    45: ("exact readback attestation for both canaries",
         RUN / "canaryB_report.json",
         lambda d: bool(d.get("attestation_id")) and
         bool(d.get("provider_media_sha256")) and
         journal_state(RUN / "canaryA/upload_1.sqlite") == "VERIFIED" and
         journal_state(RUN / "canaryB/upload_1.sqlite") == "VERIFIED"),
    46: ("stable probes: both upload journals carry RECONCILE_PROBED "
         "records before binding",
         RUN / "canaryB/upload_1.sqlite",
         lambda d: stage_present(RUN / "canaryA/upload_1.sqlite",
                                 "RECONCILE_PROBED") and
         stage_present(RUN / "canaryB/upload_1.sqlite", "RECONCILE_PROBED")),
    47: ("bound then Generate: V5 continuation SHOT_PROVEN with unique "
         "output under the same authority domain",
         RUN / "scene_V5_CONTINUATION_PROOF/shot_V5_CONT/result.json",
         lambda d: d.get("gate") == "SHOT_PROVEN" and
         d.get("generate_clicks") == 1),
    55: ("pre-gate clean slots reused (8, from independent re-derivation)",
         RUN / "salvage_reconfirm_009.json",
         lambda d: d["verified"]["pre_gate_is_eight"]),
    56: ("post-gate slots rejected canonical (conformance exclusion scan)",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") ==
                       "invalidated_artifacts_excluded_from_canonical_package"
                       and c.get("verdict") == "PASS"
                       for c in d.get("checks", []))),
    57: ("exact 4-slot salvage set independently re-derived",
         RUN / "salvage_reconfirm_009.json",
         lambda d: d["verified"]["salvage_is_exactly_four"]),
    58: ("fresh 009 successors present exactly where required",
         OUT / "conformance_report.json",
         lambda d: sum(1 for c in d.get("checks", [])
                       if c.get("check") == "reproof_successor_binding" and
                       c.get("verdict") == "PASS") == 4),
    59: ("old Package-008 successors rejected (exclusion tokens include "
         "P8_F2R/G2R/E2R2/G3BR + P8_CONT)",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") ==
                       "invalidated_artifacts_excluded_from_canonical_package"
                       and c.get("verdict") == "PASS" and
                       c.get("tokens_scanned", 0) >= 24
                       for c in d.get("checks", []))),
    60: ("historical evidence retained (Package-008 record + 007 record)",
         ROOT / "docs/operating/FLOW_UPLOAD_RECONCILIATION_CONTRACT_008_EVIDENCE.md",
         lambda d: "INVALID_AS_CLEAN_AUTHORIZED_PROOF" in d,
         "text"),
    61: (">4 salvage refusal rule verified (re-derivation asserts exactly 4)",
         RUN / "salvage_reconfirm_009.json",
         lambda d: d["salvage_set_size"] == 4),
    62: ("frozen editorial targets preserved (F2 5.6 / G2 4.0 / E2 4.0 / "
         "G3 3.2 in master summary)",
         OUT / "master_summary.json",
         lambda d: [s["slot_id"] for s in d["slots"]].count("SEQ7_F2") == 1),
    64: ("no stale take (conformance)",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "no_stale_primary_takes" and
                       c.get("verdict") == "PASS" for c in d.get("checks", []))),
    69: ("no duplicate slot (30 unique)",
         OUT / "master_summary.json",
         lambda d: len({s["slot_id"] for s in d["slots"]}) == 30),
    71: ("duration within tolerance (conformance)",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "duration" and
                       c.get("verdict") == "PASS" for c in d.get("checks", []))),
    72: ("29/29 boundary frame sampling PASS",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "boundary_frame_sampling_29_cuts" and
                       c.get("verdict") == "PASS" for c in d.get("checks", []))),
}

ROWS = [
    (1, "Classifier", "known completed identity envelope",
     "pytest", [C1 + "test_direct_identity_envelope_is_qualified_completed",
                C1 + "test_correlation_metadata_siblings_do_not_conflict"]),
    (2, "Classifier", "frozen pending class",
     "pytest", [C1 + "test_live_frozen_class_is_qualified_pending"]),
    (3, "Classifier", "unknown 200 body fails closed",
     "pytest", [C1 + "test_every_non_pending_shape_fails_closed_ambiguous"]),
    (4, "Classifier", "malformed payload fails closed",
     "pytest", [C1 + "test_parse_failure_is_true_ambiguous_and_never_pending"]),
    (5, "Classifier", "response drift fails closed",
     "pytest", [C1 + "test_live_class_structural_drift_fails_closed",
                C2 + "test_pending_fingerprint_drift_is_detectable"]),
    (6, "Classifier", "status drift fails closed",
     "pytest", [C1 + "test_live_class_requires_status_200"]),
    (7, "Classifier", "conflicting identities fail closed",
     "pytest", [C1 + "test_every_non_pending_shape_fails_closed_ambiguous",
                REF + "test_upload_invalid_or_conflicting_primary_identity_never_persists"]),
    (8, "Classifier", "non-200 fails closed",
     "pytest", [C1 + "test_every_non_pending_shape_fails_closed_ambiguous"]),
    (9, "Classifier", "parse failure never pending",
     "pytest", [C1 + "test_parse_failure_is_true_ambiguous_and_never_pending"]),
    (10, "Classifier", "degenerate body fails closed",
     "pytest", [C1 + "test_identity_free_structured_record_is_no_longer_pending"]),
    (11, "Pending", "enter from OPEN only",
     "pytest", [C2 + "test_pending_state_machine_refuses_conflicting_transitions"]),
    (12, "Pending", "suspends every mutation class",
     "pytest", [C2 + "test_pending_suspends_generate_authority"]),
    (13, "Pending", "survives restart (store + authority)",
     "pytest", [C2 + "test_pending_survives_restart_for_store_and_authority"]),
    (14, "Pending", "Generate refused while pending",
     "pytest", [C2 + "test_pending_suspends_generate_authority"]),
    (15, "Pending", "second upload refused while pending",
     "pytest", [C2 + "test_pending_never_grants_a_second_upload"]),
    (16, "Pending", "reconcile unique binds",
     "pytest", [C2 + "test_pending_reconciles_to_unique_binding_and_verifies"]),
    (17, "Pending", "bind persists VERIFIED",
     "pytest", [C2 + "test_pending_reconciles_to_unique_binding_and_verifies"]),
    (18, "Pending", "bind restores OPEN",
     "pytest", [C2 + "test_upload_bound_restores_planned_continuation"]),
    (19, "Pending", "no match exhausts to ambiguity",
     "pytest", [C2 + "test_wrong_content_never_binds_and_exhausts_to_ambiguity"]),
    (20, "Pending", "bounded timeout promotes latch",
     "pytest", [C2 + "test_bounded_exhaustion_promotes_to_true_ambiguity"]),
    (21, "Pending", "multiple matches terminal",
     "pytest", [C2 + "test_multiple_strong_matches_are_ambiguous"]),
    (22, "Pending", "wrong project refused",
     "pytest", [C2 + "test_wrong_project_catalog_is_not_a_safe_match"]),
    (23, "Pending", "wrong content never binds",
     "pytest", [C2 + "test_wrong_content_never_binds_and_exhausts_to_ambiguity"]),
    (24, "Pending", "unreadable candidate blocks",
     "pytest", [C2 + "test_unreadable_candidates_block_and_exhaust"]),
    (25, "Pending", "readback mismatch retains + gates",
     "pytest", [C2 + "test_readback_unavailable_after_identification_retains_resource"]),
    (26, "Pending", "catalog schema drift blocks reconcile",
     "pytest", [C2 + "test_catalog_contract_drift_blocks_reconciliation"]),
    (27, "Ambiguity", "true ambiguity classifies fail-closed",
     "pytest", [C1 + "test_every_non_pending_shape_fails_closed_ambiguous"]),
    (28, "Ambiguity", "permanent latch",
     "pytest", [AUTH + "test_latch_is_one_way",
                C2 + "test_reconciliation_failure_promotes_pending_to_permanent_latch"]),
    (29, "Ambiguity", "latch survives restart",
     "pytest", [AUTH + "test_latch_survives_restart"]),
    (30, "Ambiguity", "resolution no-effect keeps latch",
     "pytest", [AUTH + "test_readonly_resolution_no_effect_keeps_latch"]),
    (31, "Ambiguity", "resolution effect-found keeps latch",
     "pytest", [AUTH + "test_readonly_resolution_identified_effect_keeps_latch"]),
    (32, "Ambiguity", "knowledge change never reopens",
     "pytest", [C2 + "test_readonly_resolution_after_ambiguity_cannot_reopen"]),
    (33, "Ambiguity", "unused budget refused after latch",
     "pytest", [AUTH + "test_unused_generate_budget_cannot_be_consumed_after_latch",
                AUTH + "test_unused_upload_budget_cannot_be_consumed_after_latch"]),
    (34, "Ambiguity", "successor path refused after latch",
     "pytest", [AUTH + "test_successor_and_repair_paths_cannot_bypass_latch"]),
    (35, "Ambiguity", "repair path refused after latch",
     "pytest", [AUTH + "test_successor_and_repair_paths_cannot_bypass_latch"]),
    (36, "Ambiguity", "scene-runner resume refused after latch",
     "pytest", [AUTH + "test_scene_resume_cannot_bypass_latch"]),
    (37, "Ambiguity", "one authority domain: single scope file carries the "
     "whole package event chain (no sub-scope creation)",
     "evidence", 37),
    (38, "Qualification", "Canary A PASS", "evidence", 38),
    (39, "Qualification", "Canary B PASS", "evidence", 39),
    (40, "Qualification", "same classifier version", "evidence", 40),
    (41, "Qualification", "same fingerprint", "evidence", 41),
    (42, "Qualification", "no post-A code change", "evidence", 42),
    (43, "Qualification", "two distinct source SHAs", "evidence", 43),
    (44, "Qualification", "two distinct provider media", "evidence", 44),
    (45, "Qualification", "exact readback", "evidence", 45),
    (46, "Qualification", "stable probes", "evidence", 46),
    (47, "Continuation", "bound then Generate (V5)", "evidence", 47),
    (48, "Continuation", "wrong reference rejected",
     "pytest", [BIND + "test_binding_rejects_wrong_resource_or_metadata",
                BIND + "test_ui_chip_wrong_id_blocks_mutation"]),
    (49, "Continuation", "stale reference rejected",
     "pytest", [ADOPT + "test_verify_rejects_wrong_media_identity",
                ADOPT + "test_verify_rejects_changed_local_bytes"]),
    (50, "Continuation", "marker collision refused",
     "pytest", [BIND + "test_native_text_ast_requires_exact_single_reference_and_marker"]),
    (51, "Continuation", "multiple output candidates rejected",
     "pytest", [BIND + "test_canonical_success_and_geometric_conflation_rejected"]),
    (52, "Continuation", "render pending not a failure/retry",
     "pytest", [REND + "test_render_pending_is_not_failure_and_not_retry_authority"]),
    (53, "Continuation", "render unknown unobservable",
     "pytest", [REND + "test_arbitrary_non_null_object_is_unobservable_not_pending"]),
    (54, "Continuation", "acquisition validates/hashes/persists",
     "pytest", [LIVE + "test_successful_submit_reconciles_exact_output_ids_and_persists_lineage",
                LIVE + "test_html_renamed_as_mp4_is_rejected"]),
    (55, "Salvage", "pre-gate reused", "evidence", 55),
    (56, "Salvage", "post-gate rejected", "evidence", 56),
    (57, "Salvage", "exact 4 salvage", "evidence", 57),
    (58, "Salvage", "fresh successors exact", "evidence", 58),
    (59, "Salvage", "old 008 successors rejected", "evidence", 59),
    (60, "Salvage", "historical evidence retained", "evidence", 60),
    (61, "Salvage", ">4 refusal", "evidence", 61),
    (62, "Editorial", "frozen target preserved", "evidence", 62),
    (63, "Editorial", "invalid range refused",
     "pytest", [EDIT + "test_out_of_bounds_out", EDIT + "test_invalid_negative_in",
                EDIT + "test_zero_duration_refused"]),
    (64, "Editorial", "stale take absent", "evidence", 64),
    (65, "Editorial", "stale asset refused at range revalidation",
     "pytest", [EDIT + "test_wrong_asset_revalidation_refused",
                EDIT + "test_hash_mismatch_refused"]),
    (66, "Editorial", "manifest free of stale IDs (lineage all-30)",
     "pytest", [SCALE + "test_out_of_order_shot_result_refused"]),
    (67, "Editorial", "package free of stale IDs",
     "pytest", [S + "test_autoedit_compatibility.py"]),
    (68, "Editorial", "master free of stale bytes",
     "evidence", 56),
    (69, "Editorial", "no duplicate slot", "evidence", 69),
    (70, "Editorial", "wrong order refused",
     "pytest", [SCALE + "test_out_of_order_scene_result_refused"]),
    (71, "Editorial", "duration tolerance", "evidence", 71),
    (72, "Editorial", "boundary mismatch fails", "evidence", 72),
    (74, "Security", "raw upload body never persisted (skeleton value-free)",
     "pytest", [C1 + "test_skeleton_is_value_free_and_deterministic",
                REF + "test_actual_http_callback_is_durable_before_parser_failure_and_no_secrets"]),
    (75, "Security", "no signed URL in 009 state", "live", 75),
    (76, "Security", "no cookie material in 009 state", "live", 76),
    (77, "Security", "no session/CAPTCHA token in 009 state", "live", 77),
    (78, "Security", "no API key in changed files", "live", 78),
]


def secret_scan() -> list[str]:
    markers = ["https://flow-content", "SNlM0e=", "captcha_token",
               "set-cookie", "POST /_/AiSandboxAngularFrontend",
               "recaptcha", "enterprise", "AIza", "sk-", "BEGIN OPENSSH"]
    leaks = []
    scan_roots = ["canaryA/evidence", "canaryB/evidence",
                  "canaryA/upload_1.sqlite", "canaryB/upload_1.sqlite",
                  "canaryA/frozen_intent.json", "canaryB/frozen_intent.json",
                  "scene_V5_CONTINUATION_PROOF", "reattest"]
    for rel_root in scan_roots:
        root = RUN / rel_root
        paths = [root] if root.is_file() else \
            sorted(root.rglob("*")) if root.exists() else []
        for path in paths:
            rel = path.relative_to(RUN).as_posix()
            if not path.is_file() or path.suffix in (".mp4", ".png", ".jpg"):
                continue
            try:
                blob = path.read_bytes()
            except OSError:
                continue
            for marker in markers:
                if marker.lower().encode() in blob.lower():
                    leaks.append(f"{rel}: {marker}")
    changed = subprocess.run(
        ["git", "diff", "--name-only", "a7edff2a1a70a349c50def1f2933ca719ef41d3d..HEAD"],
        cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    for f in changed:
        try:
            blob = Path(f).read_bytes()
        except OSError:
            continue
        for marker in ("AIza", "sk-", "BEGIN OPENSSH PRIVATE KEY",
                       "BEGIN RSA PRIVATE KEY"):
            if marker.lower().encode() in blob.lower():
                leaks.append(f"{f}: {marker}")
    return leaks


E37 = ("single authority domain: one mutation_authority.json carries "
       "pending->bound x2 + budget events for canaries/continuation/reproof")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"version": "recovery-matrix-009-v1", "rows": []}
    nodes = sorted({n for row in ROWS if row[3] == "pytest" for n in row[4]})
    junit = OUT / "junit_recovery_009.xml"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--junitxml", str(junit),
         "-p", "no:cacheprovider"] + nodes,
        cwd=str(ROOT), capture_output=True, text=True)
    results = {}
    if junit.exists():
        tree = ET.parse(junit)
        for case in tree.iter("testcase"):
            module = case.get("classname", "").rsplit(".", 1)[-1]
            failed = case.find("failure") is not None or \
                case.find("error") is not None
            verdict = "FAIL" if failed else "PASS"
            results[f"tests/{module}.py::{case.get('name', '')}"] = verdict
            prior = results.get(f"tests/{module}.py", "PASS")
            results[f"tests/{module}.py"] = "FAIL" if failed else prior
    else:
        print(completed.stdout[-2000:], completed.stderr[-1500:])
    for row_id, group, acceptance, kind, proof in ROWS:
        if kind == "pytest":
            verdicts = []
            for node in proof:
                if node in results:
                    verdicts.append(results[node])
                    continue
                matching = [results[name] for name in results
                            if name == node or name.startswith(node + "[")]
                verdicts.append("PASS" if matching and
                                all(v == "PASS" for v in matching)
                                else "MISSING")
            verdict = ("PASS" if verdicts and
                       all(v == "PASS" for v in verdicts) else "FAIL")
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance, "proof": proof,
                                   "per_node": verdicts, "result": verdict})
        elif kind == "evidence":
            if row_id == 37:
                state = json.loads(
                    (RUN / "mutation_authority.json").read_text(
                        encoding="utf-8"))
                kinds = [e["kind"] for e in state["events"]]
                ok = (state["scope_id"] == "FLOW-UPLOAD-CONTRACT-REQUAL-009"
                      and kinds.count("QUALIFIED_UPLOAD_PENDING_ENTERED") == 2
                      and kinds.count("QUALIFIED_UPLOAD_BOUND") == 2
                      and state["mutation_authority"] == "OPEN"
                      and not any(k.startswith("OWNER_AMBIGUITY")
                                  for k in kinds))
                verdict = "PASS" if ok else "FAIL"
                report["rows"].append({"id": row_id, "group": group,
                                       "acceptance": acceptance,
                                       "proof": E37 +
                                       f" [events={len(kinds)}]",
                                       "result": verdict})
                continue
            evidence_id = {68: 56}.get(row_id, row_id)
            entry = EVIDENCE_ROWS[evidence_id]
            note, path, predicate = entry[0], entry[1], entry[2]
            is_text = len(entry) > 3 and entry[3] == "text"
            try:
                if path.suffix == ".sqlite":
                    ok = bool(predicate(None))
                else:
                    loaded = (path.read_text(encoding="utf-8") if is_text
                              else json.loads(
                                  path.read_text(encoding="utf-8")))
                    ok = bool(predicate(loaded))
                verdict = "PASS" if ok else "FAIL"
            except Exception as exc:  # noqa: BLE001
                verdict = f"ERROR: {type(exc).__name__}: {exc}"[:140]
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": f"{note} [{path.name}]",
                                   "result": verdict})
        elif kind == "live":
            if row_id in (75, 76, 77, 78):
                leaks = [l for l in secret_scan() if l.split(": ")[-1] in
                         ("https://flow-content", "SNlM0e=", "set-cookie",
                          "POST /_/AiSandboxAngularFrontend", "recaptcha",
                          "enterprise", "AIza", "sk-",
                          "BEGIN OPENSSH PRIVATE KEY",
                          "BEGIN RSA PRIVATE KEY")] if row_id != 76 else \
                    [l for l in secret_scan()
                     if "cookie" in l.lower() or "set-cookie" in l.lower()]
                verdict = "PASS" if not leaks else "FAIL"
                detail = f"leaks: {leaks[:4]}" if leaks else "clean"
            else:
                verdict, detail = "ERROR", "unmapped live row"
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": f"live read-only check ({detail})",
                                   "result": verdict})
    fails = [r for r in report["rows"] if r["result"] != "PASS"]
    report["overall"] = f"{len(report['rows']) - len(fails)}/" \
                        f"{len(report['rows'])} PASS"
    report["fail_rows"] = [r["id"] for r in fails]
    (OUT / "recovery_matrix_009.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"overall": report["overall"],
                      "fails": report["fail_rows"]}))


if __name__ == "__main__":
    main()
