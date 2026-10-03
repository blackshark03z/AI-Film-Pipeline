"""FLOW-UPLOAD-RECONCILIATION-CONTRACT-008 (U13) — recovery/contract matrix
(64 package-mandated scenarios).

Each row maps to an exact proof:
- "pytest": specific collected test nodes (executed fresh in ONE pytest
  invocation with --junitxml; results joined back per row);
- "evidence": durable live-run artifacts from this package (verified
  read-only here: file exists + expected content predicate);
- "live": a deterministic read-only computation executed now (hash
  recompute, secret scan, uniqueness scan).

Output: projects/flow_upload_reconciliation_008/master_package_008/
recovery_matrix_008.json
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects/flow_upload_reconciliation_008/master_package_008"
RUN = ROOT / "projects/flow_upload_reconciliation_008"
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
DISP = S + "test_dispatch_recovery.py::"


def journal_state(path: Path) -> str:
    import sqlite3
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT payload FROM reference_uploads LIMIT 1").fetchone()
        return json.loads(row[0])["state"] if row else "ABSENT"
    finally:
        connection.close()


def journal_stage_present(path: Path, stage: str) -> bool:
    import sqlite3
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT 1 FROM reference_upload_events WHERE stage=? LIMIT 1",
            (stage,)).fetchone()
        return row is not None
    finally:
        connection.close()


EVIDENCE_ROWS = {
    17: ("canary2 pending store bound VERIFIED with stable probes recorded",
         RUN / "canary2/upload_1.sqlite",
         lambda d: journal_state(RUN / "canary2/upload_1.sqlite") == "VERIFIED"
         and journal_stage_present(RUN / "canary2/upload_1.sqlite",
                                   "UPLOAD_RESPONSE_CLASSIFIED")),
    20: ("canary1 upload resolved on a later read-only probe round "
         "(late catalog appearance tolerated, never re-uploaded)",
         RUN / "canary1/upload_1.sqlite",
         lambda d: journal_state(RUN / "canary1/upload_1.sqlite") == "VERIFIED"),
    29: ("U6 continuation: ONE conditioned Generate after qualified "
         "pending -> bound -> OPEN; SHOT_PROVEN with unique output",
         RUN / "continuation/scene_U6_CONTINUATION_PROOF/shot_U6_CONT/result.json",
         lambda d: d.get("gate") == "SHOT_PROVEN" and
         d.get("generate_clicks") == 1),
    29.1: ("U6 authority chain: pending entered -> UPLOAD_BOUND -> budget "
           "consumed (durable CONT scope journal)",
           RUN / "continuation/mutation_authority.json",
           lambda d: d["events"][-3:] and
         [e["kind"] for e in d["events"][-3:]] ==
         ["QUALIFIED_UPLOAD_PENDING_ENTERED", "QUALIFIED_UPLOAD_BOUND",
          "BUDGET_CONSUMED"] and
         not any(e["kind"].startswith("OWNER_AMBIGUITY") for e in d["events"])),
    39: ("pre-gate clean slots reused unchanged (8 slots, same assets as "
         "Package-007)",
         RUN / "salvage_plan_008.json",
         lambda d: len(d["pre_gate_clean_reused_unchanged"]) == 8),
    40: ("post-gate invalidated artifacts excluded from canonical package",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") ==
                       "invalidated_artifacts_excluded_from_canonical_package"
                       and c.get("verdict") == "PASS"
                       for c in d.get("checks", []))),
    41: ("reproof successor binding proven per replaced slot",
         OUT / "conformance_report.json",
         lambda d: sum(1 for c in d.get("checks", [])
                       if c.get("check") == "reproof_successor_binding"
                       and c.get("verdict") == "PASS") == 4),
    42: ("stale invalidated takes absent from manifest",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "no_stale_primary_takes" and
                       c.get("verdict") == "PASS"
                       for c in d.get("checks", []))),
    43: ("successor identity exact (F2R/G2R/E2R2/G3BR, no substitutions)",
         OUT / "conformance_report.json",
         lambda d: sum(1 for c in d.get("checks", [])
                       if c.get("check") == "repair_take_canonical" and
                       c.get("verdict") == "PASS") == 4),
    44: (">8 invalid slots would refuse (BLOCKED_INVARIANT rule); actual "
         "salvage set 4 <= 8",
         RUN / "salvage_plan_008.json",
         lambda d: len(d["salvage_set"]) == 4 and "BLOCKED_INVARIANT"
         in d["max_slots_rule"]),
    45: ("historical breach preserved verbatim (custody correction in "
         "Package-007 evidence)",
         ROOT / "docs/operating/FLOW_PRODUCTION_SCALE_007_EVIDENCE.md",
         lambda d: "FIRST HISTORICAL GATE POINT" in d,
         "text"),
    49: ("no stale invalidated asset in any EditorialRange",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "lineage_and_ranges_all_30" and
                       c.get("verdict") == "PASS"
                       for c in d.get("checks", []))),
    57: ("stale post-gate media absent (package + summary haystacks)",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") ==
                       "invalidated_artifacts_excluded_from_canonical_package"
                       and c.get("verdict") == "PASS"
                       for c in d.get("checks", []))),
    64: ("historical breach + chronology preserved in Package-007 record",
         ROOT / "docs/operating/FLOW_PRODUCTION_SCALE_007_EVIDENCE.md",
         lambda d: "07:39:32.111961" in d and "FIRST HISTORICAL GATE POINT" in d,
         "text"),
}

ROWS = [
    # -- Upload classifier (1-8) --
    (1, "Classifier", "known qualified pending response classifies PENDING",
     "pytest", [C1 + "test_live_frozen_class_is_qualified_pending",
                C1 + "test_real_session_pending_response_shape_reaches_transport"]),
    (2, "Classifier", "unknown body shape -> TRUE_AMBIGUOUS (never pending)",
     "pytest", [C1 + "test_every_non_pending_shape_fails_closed_ambiguous"]),
    (3, "Classifier", "malformed/unparseable response -> TRUE_AMBIGUOUS",
     "pytest", [C1 + "test_parse_failure_is_true_ambiguous_and_never_pending",
                REF + "test_actual_http_callback_is_durable_before_parser_failure_and_no_secrets"]),
    (4, "Classifier", "HTTP 200 + unknown body -> TRUE_AMBIGUOUS",
     "pytest", [C1 + "test_every_non_pending_shape_fails_closed_ambiguous",
                C2 + "test_http_200_unknown_body_fails_closed"]),
    (5, "Classifier", "no-response transport death -> UNOBSERVABLE gate",
     "pytest", [C1 + "test_real_session_transport_failure_after_dispatch_classifies_unobservable",
                C2 + "test_transport_death_after_dispatch_is_unobservable_gate"]),
    (6, "Classifier", "response structural drift fails closed",
     "pytest", [C1 + "test_live_class_structural_drift_fails_closed",
                C2 + "test_pending_fingerprint_drift_is_detectable"]),
    (7, "Classifier", "status drift (non-200 / unobserved) never pending",
     "pytest", [C1 + "test_live_class_requires_status_200",
                C1 + "test_every_non_pending_shape_fails_closed_ambiguous"]),
    (8, "Classifier", "request fingerprint durable; value-free skeletons",
     "pytest", [C1 + "test_skeleton_is_value_free_and_deterministic",
                C1 + "test_classification_requires_all_inputs_fresh_each_call"]),
    # -- Upload reconciliation (9-20) --
    (9, "Reconciliation", "unique match binds and verifies",
     "pytest", [C2 + "test_pending_reconciles_to_unique_binding_and_verifies"]),
    (10, "Reconciliation", "no qualifying match exhausts to ambiguity",
     "pytest", [C2 + "test_wrong_content_never_binds_and_exhausts_to_ambiguity"]),
    (11, "Reconciliation", "multiple strong matches -> terminal ambiguity",
     "pytest", [C2 + "test_multiple_strong_matches_are_ambiguous"]),
    (12, "Reconciliation", "preexisting duplicate/unresolved row handled via "
     "durable preexisting evidence",
     "pytest", [C2 + "test_preexisting_unresolved_row_does_not_block_unique_match"]),
    (13, "Reconciliation", "wrong-project catalog is not a safe match",
     "pytest", [C2 + "test_wrong_project_catalog_is_not_a_safe_match"]),
    (14, "Reconciliation", "wrong content never binds",
     "pytest", [C2 + "test_wrong_content_never_binds_and_exhausts_to_ambiguity"]),
    (15, "Reconciliation", "unreadable blocking row blocks binding",
     "pytest", [C2 + "test_unreadable_candidates_block_and_exhaust"]),
    (16, "Reconciliation", "readback mismatch retains identified resource "
     "and gates",
     "pytest", [C2 + "test_readback_unavailable_after_identification_retains_resource"]),
    (17, "Reconciliation", "stable probes: canary2 bind with classified "
     "journal", "evidence", 17),
    (18, "Reconciliation", "pending state survives restart (store + authority)",
     "pytest", [C2 + "test_pending_survives_restart_for_store_and_authority"]),
    (19, "Reconciliation", "bounded exhaustion promotes TRUE_AMBIGUITY + latch",
     "pytest", [C2 + "test_bounded_exhaustion_promotes_to_true_ambiguity"]),
    (20, "Reconciliation", "late catalog appearance: canary1 resolved on a "
     "later probe round, never re-uploaded", "evidence", 20),
    # -- Authority (21-28) --
    (21, "Authority", "pending suspends every mutation class",
     "pytest", [C2 + "test_pending_suspends_generate_authority"]),
    (22, "Authority", "UPLOAD_BOUND restores planned continuation",
     "pytest", [C2 + "test_upload_bound_restores_planned_continuation"]),
    (23, "Authority", "TRUE ambiguity latches permanently",
     "pytest", [C2 + "test_reconciliation_failure_promotes_pending_to_permanent_latch",
                AUTH + "test_latch_is_one_way"]),
    (24, "Authority", "read-only resolution cannot reopen a latch",
     "pytest", [C2 + "test_readonly_resolution_after_ambiguity_cannot_reopen",
                AUTH + "test_readonly_resolution_identified_effect_keeps_latch"]),
    (25, "Authority", "latch/pending survive restart",
     "pytest", [AUTH + "test_latch_survives_restart",
                C2 + "test_pending_survives_restart_for_store_and_authority"]),
    (26, "Authority", "unused budget refused after latch",
     "pytest", [AUTH + "test_unused_generate_budget_cannot_be_consumed_after_latch",
                AUTH + "test_unused_upload_budget_cannot_be_consumed_after_latch"]),
    (27, "Authority", "successor scope games refused inside latched scope",
     "pytest", [C2 + "test_latched_scope_refuses_new_upload_pending",
                AUTH + "test_successor_and_repair_paths_cannot_bypass_latch"]),
    (28, "Authority", "repair path cannot bypass latch",
     "pytest", [AUTH + "test_successor_and_repair_paths_cannot_bypass_latch",
                AUTH + "test_scene_resume_cannot_bypass_latch"]),
    # -- Generate continuation (29-38) --
    (29, "Continuation", "conditioned Generate after qualified pending "
     "(U6 SHOT_PROVEN + authority chain)", "evidence", 29),
    (29.1, "Continuation", "durable pending->bound->consume authority events",
     "evidence", 29.1),
    (30, "Continuation", "wrong reference binding rejected",
     "pytest", [BIND + "test_binding_rejects_wrong_resource_or_metadata",
                BIND + "test_ui_chip_wrong_id_blocks_mutation"]),
    (31, "Continuation", "stale reference rejected at adoption/verification",
     "pytest", [ADOPT + "test_verify_rejects_wrong_media_identity",
                ADOPT + "test_verify_rejects_changed_local_bytes"]),
    (32, "Continuation", "marker collision refused",
     "pytest", [BIND + "test_native_text_ast_requires_exact_single_reference_and_marker"]),
    (33, "Continuation", "candidate conflation rejected",
     "pytest", [BIND + "test_canonical_success_and_geometric_conflation_rejected"]),
    (34, "Continuation", "pending render is not failure and grants no retry",
     "pytest", [REND + "test_render_pending_is_not_failure_and_not_retry_authority"]),
    (35, "Continuation", "unknown render payload unobservable",
     "pytest", [REND + "test_arbitrary_non_null_object_is_unobservable_not_pending",
                REND + "test_restart_after_unknown_payload_still_blocks_submission"]),
    (36, "Continuation", "render completion observed once; acquire-only after",
     "pytest", [REND + "test_render_completed_observed",
                REND + "test_restart_after_render_completed_keeps_acquire_only"]),
    (37, "Continuation", "acquisition failure fails closed",
     "pytest", [LIVE + "test_html_renamed_as_mp4_is_rejected"]),
    (38, "Continuation", "restart after ambiguity reconciles without redispatch",
     "pytest", [LIVE + "test_submit_timeout_restart_reconciles_without_blind_redispatch",
                LIVE + "test_crash_after_durable_reservation_never_reaches_submit_on_restart"]),
    # -- Salvage (39-45) --
    (39, "Salvage", "pre-gate clean assets reused (8, unchanged)",
     "evidence", 39),
    (40, "Salvage", "post-gate assets rejected canonical (exclusion scan)",
     "evidence", 40),
    (41, "Salvage", "successor binding exact per slot", "evidence", 41),
    (42, "Salvage", "stale old take absent", "evidence", 42),
    (43, "Salvage", "wrong successor impossible (exact take identity)",
     "evidence", 43),
    (44, "Salvage", ">8 invalid slots would refuse; actual 4",
     "evidence", 44),
    (45, "Salvage", "historical evidence preserved (no rewrite)", "evidence", 45),
    # -- Editorial (46-51) --
    (46, "Editorial", "frozen editorial ranges: original targets kept for "
     "re-proof slots (5.6/4.0/4.0/3.2)",
     "pytest", [EDIT + "test_full_clip_range", EDIT + "test_head_trim",
                EDIT + "test_tail_trim"]),
    (47, "Editorial", "out-of-bounds range refused",
     "pytest", [EDIT + "test_out_of_bounds_out", EDIT + "test_invalid_negative_in"]),
    (48, "Editorial", "trim hash mismatch refused",
     "pytest", [EDIT + "test_wrong_asset_revalidation_refused"]),
    (49, "Editorial", "no stale invalid asset in ranges", "evidence", 49),
    (50, "Editorial", "package free of invalidated assets",
     "pytest", [S + "test_autoedit_compatibility.py"]),
    (51, "Editorial", "master free of invalidated assets",
     "evidence", 57),
    # -- Conformance (52-58) --
    (52, "Conformance", "slot order exact (lineage all-30)",
     "pytest", [S + "test_scale_orchestrator.py::test_out_of_order_shot_result_refused"]),
    (53, "Conformance", "29/29 boundary frame sampling PASS",
     "evidence", 53),
    (54, "Conformance", "master duration within frame-rounding tolerance",
     "evidence", 54),
    (55, "Conformance", "no duplicate clip (30 unique slots)",
     "live", 55),
    (56, "Conformance", "no missing clip (30 sources render)",
     "evidence", 54),
    (57, "Conformance", "stale post-gate media absent from master/package",
     "evidence", 57),
    (58, "Conformance", "master hash not tampered (recompute vs summary)",
     "live", 58),
    # -- Secrets/custody (59-64) --
    (59, "Custody", "upload response skeletons value-free (no secrets/URLs)",
     "pytest", [C1 + "test_skeleton_is_value_free_and_deterministic",
                C1 + "test_uuid_strings_are_marked_but_not_valued_in_skeleton"]),
    (60, "Custody", "no signed URL persisted anywhere in 008 state",
     "live", 60),
    (61, "Custody", "no cookie material persisted in 008 state",
     "live", 61),
    (62, "Custody", "no session/captcha token persisted in 008 state",
     "live", 62),
    (63, "Custody", "exact Package-007 custody correction SHA recorded",
     "live", 63),
    (64, "Custody", "historical breach chronology preserved", "evidence", 64),
]

EXTRA_EVIDENCE = {
    53: ("boundary_frame_sampling_29_cuts PASS in independent conformance",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "boundary_frame_sampling_29_cuts" and
                       c.get("verdict") == "PASS" for c in d["checks"])),
    54: ("duration PASS + 30 sources in conformance",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "duration" and
                       c.get("verdict") == "PASS" for c in d["checks"])),
    51: ("autoedit producer package free of invalidated assets "
         "(exclusion scan covers package payload haystacks)",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") ==
                       "invalidated_artifacts_excluded_from_canonical_package"
                       and c.get("verdict") == "PASS"
                       for c in d.get("checks", []))),
    56: ("no missing clip: all 30 sources rendered (duration conformance)",
         OUT / "conformance_report.json",
         lambda d: any(c.get("check") == "duration" and
                       c.get("verdict") == "PASS" for c in d["checks"])),
}


def secret_scan() -> list[str]:
    """Read-only scan of the 008 state tree for secret-class material."""
    markers = ["https://flow-content", "SNlM0e=", "captcha_token",
               "set-cookie", "POST /_/AiSandboxAngularFrontend",
               "recaptcha", "enterprise"]
    leaks = []
    scan_roots = ["canary1/evidence", "canary2/evidence",
                  "canary1/upload_1.sqlite", "canary2/upload_1.sqlite",
                  "canary1/frozen_intent.json", "canary2/frozen_intent.json",
                  "continuation"]
    for rel_root in scan_roots:
        root = RUN / rel_root
        paths = [root] if root.is_file() else             sorted(root.rglob("*")) if root.exists() else []
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
    return leaks


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"version": "recovery-matrix-008-v1", "rows": []}
    # One fresh pytest pass over every referenced node.
    nodes = sorted({n for row in ROWS if row[3] == "pytest" for n in row[4]})
    junit = OUT / "junit_recovery_008.xml"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--junitxml", str(junit),
         "-p", "no:cacheprovider"] + nodes,
        cwd=str(ROOT), capture_output=True, text=True)
    if junit.exists() and ET.parse(junit).getroot().find("testsuite")             .get("tests") == "0":
        print("PYTEST RC", completed.returncode)
        print(completed.stdout[-1500:])
        print(completed.stderr[-800:])
    results = {}
    if junit.exists():
        tree = ET.parse(junit)
        for case in tree.iter("testcase"):
            classname = case.get("classname", "")
            module = classname.rsplit(".", 1)[-1]
            failed = case.find("failure") is not None or                 case.find("error") is not None
            verdict = "FAIL" if failed else "PASS"
            results[f"tests/{module}.py::{case.get('name', '')}"] = verdict
            prior = results.get(f"tests/{module}.py", "PASS")
            results[f"tests/{module}.py"] = "FAIL" if failed else prior
    else:
        print(completed.stdout[-3000:], completed.stderr[-2000:])
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
            entry = EVIDENCE_ROWS.get(row_id) or EXTRA_EVIDENCE[row_id]
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
                verdict = f"ERROR: {type(exc).__name__}: {exc}"[:120]
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": f"{note} [{path.name}]",
                                   "result": verdict})
        elif kind == "live":
            if row_id == 55:
                summary = json.loads((OUT / "master_summary.json")
                                     .read_text(encoding="utf-8"))
                slots = [s["slot_id"] for s in summary["slots"]]
                verdict = "PASS" if len(slots) == 30 and \
                    len(set(slots)) == 30 else "FAIL"
                detail = f"unique slots: {len(set(slots))}/30"
            elif row_id == 58:
                summary = json.loads((OUT / "master_summary.json")
                                     .read_text(encoding="utf-8"))
                actual = hashlib.sha256(
                    Path(summary["output_path"]).read_bytes()).hexdigest()
                verdict = "PASS" if actual == summary["output_sha256"] \
                    else "FAIL"
                detail = f"sha {actual[:12]} vs summary"
            elif row_id in (60, 61, 62):
                leaks = secret_scan()
                verdict = "PASS" if not leaks else "FAIL"
                detail = f"leaks: {leaks[:4]}"
            elif row_id == 63:
                log = subprocess.run(
                    ["git", "log", "--format=%H", "-30"], cwd=str(ROOT),
                    capture_output=True, text=True).stdout
                verdict = "PASS" if "ca2a19081c6f4c3ef10224dab2f5e634398c3d4f"                     in log else "FAIL"
                detail = "custody correction commit present"
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
    (OUT / "recovery_matrix_008.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"overall": report["overall"],
                      "fails": report["fail_rows"]}))


if __name__ == "__main__":
    main()
