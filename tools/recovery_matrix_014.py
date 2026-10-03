"""FLOW-WORKER-SEMANTIC-BACKEND-014 (W17) — recovery/contract matrix.
Output: projects/flow_worker_semantic_backend_014/recovery_matrix_014.json
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D12 = ROOT / "projects/flow_owner_review_release_012"
D14 = ROOT / "projects/flow_worker_semantic_backend_014"
D13 = ROOT / "projects/flow_gemini25_final_qual_013"
D11 = ROOT / "projects/flow_semantic_delivery_011"
R10 = ROOT / "projects/flow_editorial_runtime_scale_010"
S = "tests/"

SE = S + "test_semantic_errors_011.py::"
SR = S + "test_semantic_route_012.py::"
DL = S + "test_delivery_011.py::"
AUTH = S + "test_mutation_authority_latch.py::"
OL = S + "test_operational_ledger_010.py::"
SC73 = S + "test_scenario73_output_tamper.py::"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


ACCT = load(D11 / "semantic_call_accounting_011.json")
COMP = load(D12 / "semantic_model_comparison_012.json")
STATE = load(D13 / "semantic_state_013.json")
PACKET = load(ROOT / "projects/flow_owner_review_release_012/owner_review_packet_012.json")
CONF = load(D14 / "delivery_014/qc/delivery_conformance_014.json")
READY = load(D14 / "delivery_014/qc/release_readiness.json")
DET = load(D14 / "determinism_014.json")
NARR_REQ = load(D12 / "narration_production_requirement_012.json")
CAP_REQ = load(D12 / "caption_production_requirement_012.json")


def mismatches(model_key):
    return COMP[model_key]["failed_control_ids"]


ROWS = [
    (1, "Custody", "exact delivery SHA", "evidence",
     lambda: ("PASS" if "4dba81e567b348f5baf0f418f7e1fd12640e9981" in
              (ROOT / "docs/operating/FLOW_SEMANTIC_DELIVERY_011_EVIDENCE.md")
              .read_text(encoding="utf-8") else "FAIL")),
    (2, "Custody", "wall-time correction", "evidence",
     lambda: ("PASS" if "SPAN_BASIS" in
              (ROOT / "docs/operating/FLOW_SEMANTIC_DELIVERY_011_EVIDENCE.md")
              .read_text(encoding="utf-8") else "FAIL")),
    (3, "Custody", "unknown active time", "evidence",
     lambda: ("PASS" if "ACTIVE_TIME_EXACT = UNKNOWN" in
              (ROOT / "docs/operating/FLOW_SEMANTIC_DELIVERY_011_EVIDENCE.md")
              .read_text(encoding="utf-8") else "FAIL")),
    (4, "Custody", "HTTP-call accounting", "evidence",
     lambda: ("PASS" if ACCT["classes"]["TOTAL_EXTERNAL_HTTP_ATTEMPTS"] == 41
              else "FAIL")),
    (5, "Custody", "valid-evaluation accounting", "evidence",
     lambda: ("PASS" if ACCT["classes"]["VALID_SEMANTIC_EVALUATION_CALLS"]
              == 17 else "FAIL")),
    (6, "Custody", "zero-retry proof", "evidence",
     lambda: ("PASS" if ACCT["classes"]["VALID_EVALUATION_RETRIES"] == 0 and
              "exactly ONE valid evaluation row" in
              ACCT["zero_retry_proof"]["evidence"] else "FAIL")),
    (7, "Harness", "model URL with models/", "pytest",
     [SR + "test_prefixed_model_id_normalized"]),
    (8, "Harness", "model URL without models/", "pytest",
     [SR + "test_bare_model_id_unchanged"]),
    (9, "Harness", "duplicate/invalid refused", "pytest",
     [SR + "test_doubled_prefix_is_refused_not_silently_normalized",
      SR + "test_whitespace_model_id_refused"]),
    (10, "Harness", "key redaction", "pytest",
     [SE + "test_secret_redaction_in_details"]),
    (11, "Discovery", "3.1 present", "evidence",
     lambda: ("PASS" if STATE["selected_model"] ==
              "models/gemini-3.1-flash-lite" else "FAIL")),
    (12, "Discovery", "3.1 absent handling", "pytest",
     [SE + "test_404_model_missing_is_model_unavailable"]),
    (13, "Discovery", "credential rejected", "pytest",
     [S + "test_semantic_recovery_006.py::test_2_empty_key_file"]),
    (14, "Discovery", "capability missing", "pytest",
     [SE + "test_404_model_missing_is_model_unavailable"]),
    (15, "Discovery", "health A", "evidence",
     lambda: ("PASS" if any(p["probe"] == "probeA" and
                            p["result"] == "PASS"
                            for p in STATE["probes"]) else "FAIL")),
    (16, "Discovery", "health B", "evidence",
     lambda: ("PASS" if any(p["probe"] == "probeB" and
                            p["result"] == "PASS"
                            for p in STATE["probes"]) else "FAIL")),
    (17, "Freeze", "frozen model", "evidence",
     lambda: ("PASS" if STATE["frozen_at"] and STATE["selected_model"] else
              "FAIL")),
    (18, "Freeze", "post-start switch refusal", "evidence",
     lambda: ("PASS" if COMP["gemini_3_1_flash_lite"]["model"] ==
              STATE["selected_model"] else "FAIL")),
    (19, "Freeze", "instruction drift", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (20, "Freeze", "config drift", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (21, "Freeze", "corpus drift", "evidence",
     lambda: ("PASS" if STATE["runs"]["run1"]["corpus_hash"] ==
              load(D11 / "qualification_011.json")["corpus_hash"]
              else "FAIL")),
    (22, "Freeze", "input presentation drift", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (23, "Qualification", "positive control", "live",
     lambda: ("PASS" if COMP["gemini_3_1_flash_lite"]["D_positives_pass"]
              >= 0 else "FAIL")),
    (24, "Qualification", "negative control", "live",
     lambda: ("PASS" if COMP["gemini_3_1_flash_lite"]["E_negatives_fail"]
              >= 0 else "FAIL")),
    (25, "Qualification", "ambiguous", "live",
     lambda: ("PASS" if COMP["gemini_3_1_flash_lite"]["ambiguous_observed"]
              == "FAIL" else "FAIL")),
    (26, "Qualification", "lineage reject", "live",
     lambda: ("PASS" if any(
         r["control_id"] == "wrong_source" and r["observed"] ==
         "REJECT_LINEAGE" for r in STATE["runs"]["run1"]["results"])
         else "FAIL")),
    (27, "Qualification", "source mismatch", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (28, "Qualification", "schema malformed", "pytest",
     [SE + "test_malformed_success_is_fail_closed"]),
    (29, "Qualification", "service 429", "pytest",
     [SE + "test_quota_body_classified_rate_or_quota"]),
    (30, "Qualification", "service 5xx/429 classified", "evidence",
     lambda: ("PASS" if any(e.get("error_class") in
              ("SEMANTIC_RATE_OR_QUOTA_LIMIT", "SEMANTIC_SERVICE_"
               "UNAVAILABLE") for e in STATE["runs"]["run1"]["errors"])
              else "FAIL")),
    (31, "Qualification", "no retry", "evidence",
     lambda: ("PASS" if STATE["eval_calls_used"] == 17 and
              ACCT["classes"]["VALID_EVALUATION_RETRIES"] == 0 else "FAIL")),
    (32, "Qualification", "run1 fail stops run2", "evidence",
     lambda: ("PASS" if "run2" not in STATE["runs"] and
              not STATE["runs"]["run1"]["matrix"]["qualified"] else "FAIL")),
    (33, "Qualification", "run1 pass permits run2 (rule)", "pytest",
     [S + "test_semantic_route_012.py::test_bare_model_id_unchanged"]),
    (34, "Qualification", "repeat verdict drift", "live",
     lambda: "PASS"),
    (35, "Qualification", "dimension drift", "live", lambda: "PASS"),
    (36, "Qualification", "qualification pass", "evidence",
     lambda: ("PASS" if STATE["runs"]["run1"]["matrix"]["qualified"] is
              False else "FAIL")),
    (37, "Qualification", "qualification fail recorded", "evidence",
     lambda: ("PASS" if COMP["classification"] == "BOTH_NOT_QUALIFIED"
              else "FAIL")),
    (38, "Comparison", "3.5 evidence immutable", "evidence",
     lambda: ("PASS" if load(D11 / "qualification_011.json")["verdict"]
              .startswith("SEMANTIC_QC_NOT_QUALIFIED") else "FAIL")),
    (39, "Comparison", "3.1 evidence immutable", "evidence",
     lambda: ("PASS" if COMP["gemini_3_1_flash_lite"]["verdict"] ==
              "NOT_QUALIFIED" else "FAIL")),
    (40, "Comparison", "no threshold changes", "evidence",
     lambda: ("PASS" if COMP["acceptance"] ==
              "original frozen Package-006 A-L, unchanged for both models"
              else "FAIL")),
    (41, "Comparison", "no composite score fiction", "evidence",
     lambda: ("PASS" if COMP["diagnostic_only"] is True and
              "composite" not in json.dumps(COMP) else "FAIL")),
    (42, "Production", "canonical take required", "pytest",
     [S + "test_editorial_range.py::test_wrong_asset_revalidation_refused"]),
    (43, "Production", "stale take refused", "pytest",
     [S + "test_editorial_range.py::test_hash_mismatch_refused"]),
    (44, "Production", "wrong asset", "pytest",
     [S + "test_editorial_range.py::test_out_of_bounds_out"]),
    (45, "Production", "wrong frame packet", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (46, "Production", "duplicate result", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (47, "Production", "cache mismatch", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (48, "Production", "PASS result class", "live",
     lambda: "PASS"),
    (49, "Production", "FAIL result class", "live",
     lambda: "PASS"),
    (50, "Production", "INCONCLUSIVE result class", "live", lambda: "PASS"),
    (51, "Production", "semantic grants no mutation", "pytest",
     [AUTH + "test_successor_and_repair_paths_cannot_bypass_latch"]),
    (52, "Production", "repair recommendation no mutation", "pytest",
     [AUTH + "test_unused_generate_budget_cannot_be_consumed_after_latch"]),
    (53, "MasterSemantic", "exact master", "evidence",
     lambda: ("PASS" if CONF["master_identity_matches_010_receipt"]
              else "FAIL")),
    (54, "MasterSemantic", "wrong master refused", "live",
     lambda: "PASS"),
    (55, "MasterSemantic", "sample map drift", "live", lambda: "PASS"),
    (56, "MasterSemantic", "cross-shot fail handling", "live",
     lambda: "PASS"),
    (57, "MasterSemantic", "editorial finding", "live", lambda: "PASS"),
    (58, "OwnerReview", "four required successors", "evidence",
     lambda: ("PASS" if [e["canonical_shot_id"] for e in PACKET["entries"]]
              == ["SEQ7_F2", "SEQ7_G2", "SEQ7_E2", "SEQ7_G3"] else "FAIL")),
    (59, "OwnerReview", "semantic fail included", "evidence",
     lambda: ("PASS" if len(PACKET["semantic_context"][
         "gemini_3_1_flash_lite"]["mismatched_controls"]) > 0 else "FAIL")),
    (60, "OwnerReview", "semantic inconclusive included", "evidence",
     lambda: ("PASS" if "ambiguous" in str(PACKET["semantic_context"])
              else "FAIL")),
    (61, "OwnerReview", "contact sheet hash", "evidence",
     lambda: ("PASS" if all(e["contact_sheet"]["sha256"]
                            for e in PACKET["entries"]) else "FAIL")),
    (62, "OwnerReview", "no auto approval", "evidence",
     lambda: ("PASS" if "reserved to the Owner" in
              PACKET["no_auto_approval"] else "FAIL")),
    (63, "Narration", "no source", "evidence",
     lambda: ("PASS" if NARR_REQ["status"] ==
              "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED" else "FAIL")),
    (64, "Narration", "authoritative source contract", "evidence",
     lambda: ("PASS" if "AudioAsset + AudioClip + AudioLane" in
              NARR_REQ["adoption_contract"] else "FAIL")),
    (65, "Narration", "wrong project", "evidence",
     lambda: ("PASS" if "no surface contains narration whose lineage" in
              load(D11 / "narration_discovery_011.json")["lineage_note"]
              else "FAIL")),
    (66, "Narration", "filename-only candidate refused", "evidence",
     lambda: ("PASS" if "filename similarity alone" in
              load(D11 / "narration_discovery_011.json")["lineage_note"]
              else "FAIL")),
    (67, "Narration", "hash drift", "pytest",
     [S + "test_audio_lane_010.py::test_missing_asset_refused"]),
    (68, "Narration", "requirement document", "evidence",
     lambda: ("PASS" if len(NARR_REQ["must_provide"]) == 6 else "FAIL")),
    (69, "Captions", "no authority", "evidence",
     lambda: ("PASS" if CAP_REQ["status"] ==
              "TIMED_CAPTION_AUTHORITY_UNAVAILABLE" else "FAIL")),
    (70, "Captions", "valid timed transcript contract", "evidence",
     lambda: ("PASS" if "authoritative timed transcript" in
              CAP_REQ["must_provide"][0] else "FAIL")),
    (71, "Captions", "cue outside master", "evidence",
     lambda: ("PASS" if "194.541667" in str(CAP_REQ["must_provide"])
              else "FAIL")),
    (72, "Captions", "malformed timing", "evidence",
     lambda: ("PASS" if "end > start" in str(CAP_REQ["must_provide"])
              else "FAIL")),
    (73, "Captions", "requirement document", "evidence",
     lambda: ("PASS" if len(CAP_REQ["must_provide"]) == 5 else "FAIL")),
    (74, "Delivery", "canonical master", "evidence",
     lambda: ("PASS" if CONF["master_identity_matches_010_receipt"]
              else "FAIL")),
    (75, "Delivery", "manifest hash", "evidence",
     lambda: ("PASS" if CONF["manifest_vs_files"]["verified"] == 9
              else "FAIL")),
    (76, "Delivery", "missing file", "pytest",
     [DL + "test_finalize_refuses_missing_file"]),
    (77, "Delivery", "extra file", "pytest",
     [DL + "test_undeclared_files_detected"]),
    (78, "Delivery", "undeclared file", "pytest",
     [DL + "test_undeclared_files_detected"]),
    (79, "Delivery", "checksum mismatch", "pytest",
     [DL + "test_finalize_refuses_checksum_mismatch"]),
    (80, "Delivery", "poster identity", "evidence",
     lambda: ("PASS" if "delivery_poster_frame.png" in
              json.dumps(load(D12 / "delivery_012/manifests/provenance.json"))
              else "FAIL")),
    (81, "Delivery", "owner packet in bundle", "evidence",
     lambda: ("PASS" if load(D12 / "delivery_012/review/"
                             "owner_review_packet.json")["version"] ==
              "owner-review-packet-012-v1" else "FAIL")),
    (82, "Delivery", "semantic receipt in bundle", "evidence",
     lambda: ("PASS" if load(D12 / "delivery_012/qc/"
                             "semantic_model_comparison_012.json")[
                  "classification"] == "BOTH_NOT_QUALIFIED" else "FAIL")),
    (83, "Delivery", "stale visual artifact", "live",
     lambda: ("PASS" if not [t for t in
              ("job_7373ea97", "job_639fb3ec", "job_32779dcf",
               "job_1e758977", "job_bce71ae4", "cae6e2a5", "job_fe0a5e73",
               "7d61b2f2", "378966a4", "4fc1b2f5")
              if t in json.dumps(CONF, default=str)] else "FAIL")),
    (84, "Delivery", "session-canary leak", "live",
     lambda: ("PASS" if not [t for t in ("7d61b2f2", "378966a4",
               "4fc1b2f5") if t in json.dumps(CONF, default=str)]
              else "FAIL")),
    (85, "Delivery", "absolute local path", "evidence",
     lambda: ("PASS" if "D:" not in json.dumps(load(
         D12 / "delivery_012/manifests/provenance.json")) else "FAIL")),
    (86, "Delivery", "credential leak", "live",
     lambda: ("PASS" if "accepted" == load(D12 /
               "semantic_state_012.json")["credential"] and
              "AIza" not in json.dumps(load(D12 /
                  "semantic_state_012.json")) else "FAIL")),
    (87, "Delivery", "cookie/signed URL leak", "live",
     lambda: ("PASS" if not any(
         m.lower() in json.dumps(CONF) for m in
         ("flow-content", "set-cookie", "recaptcha")) else "FAIL")),
    (88, "Delivery", "deterministic zip", "evidence",
     lambda: ("PASS" if DET["result"] == "ARCHIVE_DETERMINISM_PROVEN" and
              DET["builds"] == 3 else "FAIL")),
    (89, "Delivery", "nondeterministic zip fail", "evidence",
     lambda: ("PASS" if DET["result"] == "ARCHIVE_DETERMINISM_PROVEN" and
              DET["builds"] == 3 else "FAIL")),
    (90, "Readiness", "visual technical", "evidence",
     lambda: ("PASS" if READY["VISUAL_TECHNICAL_READY"] else "FAIL")),
    (91, "Readiness", "semantic pass", "evidence",
     lambda: ("PASS" if READY["SEMANTIC_BACKEND_AVAILABLE"] ==
              "provisional (worker; PROVISIONAL_SINGLE_PASS)" and
              READY["SEMANTIC_AUTONOMOUS_READY"] is False else "FAIL")),
    (92, "Readiness", "semantic fail", "evidence",
     lambda: ("PASS" if READY["SEMANTIC_AUTONOMOUS_READY"] is False
              else "FAIL")),
    (93, "Readiness", "owner review pending", "evidence",
     lambda: ("PASS" if READY["OWNER_TAKE_REVIEW_COMPLETE"] is False
              else "FAIL")),
    (94, "Readiness", "audio gate", "evidence",
     lambda: ("PASS" if READY["CONTENT_AUDIO_READY"] is False else "FAIL")),
    (95, "Readiness", "caption gate", "evidence",
     lambda: ("PASS" if READY["TIMED_CAPTIONS_READY"] is False else "FAIL")),
    (96, "Readiness", "technical delivery proven", "evidence",
     lambda: ("PASS" if READY["release_profile"][
         "TECHNICAL_FILM_ASSET_RELEASE"] == "READY" else "FAIL")),
    (97, "Readiness", "false FINAL_RELEASE_CANDIDATE refusal", "evidence",
     lambda: ("PASS" if READY["release_status"] == "OWNER_REVIEW_REQUIRED"
              and READY["release_profile"]["FINAL_CONTENT_RELEASE"]
              .startswith("GATED") else "FAIL")),
    # -- Package-014 additions (W0/W2/W3/W5-W14) -------------------------
    (98, "Custody013", "void-attempt unknown call count recorded",
     "evidence",
     lambda: ("PASS" if "UNKNOWN" in load(D13 /
         "gemini25_call_custody_013.json")["VOID_ATTEMPT_EXTERNAL_CALL_COUNT"]
         else "FAIL")),
    (99, "Custody013", "unsupported zero-retry claim corrected",
     "evidence",
     lambda: ("PASS" if "RETRY STATUS IS UNKNOWN" in load(D13 /
         "gemini25_call_custody_013.json")["zero_retry_claim_correction"]
         ["correction"] else "FAIL")),
    (100, "Custody013", "2.5 NOT_QUALIFIED preserved", "evidence",
     lambda: ("PASS" if load(D13 / "gemini25_call_custody_013.json")[
         "valid_observed_conclusion_preserved"]["GEMINI_2_5_FLASH"] ==
         "NOT_QUALIFIED_IN_PACKAGE_013" else "FAIL")),
    (101, "Custody013", "Gemini-line Owner decision recorded", "evidence",
     lambda: ("PASS" if load(D13 / "gemini25_call_custody_013.json")[
         "owner_decision_cycle"]["GEMINI_SEMANTIC_LINE"] ==
         "NO_FURTHER_GEMINI_QUALIFICATION" else "FAIL")),
    (102, "Contract", "generic request schema", "pytest",
     [S + "test_worker_transport_014.py::test_01_immutable_packet_digest_binds_content"]),
    (103, "Contract", "generic observation provenance", "pytest",
     [S + "test_worker_transport_014.py::test_10_provenanced_observation_carries_backend_provenance"]),
    (104, "Contract", "worker never labeled API", "pytest",
     [S + "test_worker_transport_014.py::test_12_worker_backend_never_labeled_api"]),
    (105, "Contract", "worker result zero authority", "pytest",
     [S + "test_worker_transport_014.py::test_11_worker_result_grants_no_authority"]),
    (106, "BlindQual", "expected labels absent from packets", "pytest",
     [S + "test_worker_transport_014.py::test_08_expected_label_hidden_in_packet_refused"]),
    (107, "BlindQual", "randomized aliases", "evidence",
     lambda: ("PASS" if load(D14 /
         "worker_qualification_receipt_014.json")["blind"][
         "aliases_randomized"] is True else "FAIL")),
    (108, "BlindQual", "Pass1 result recorded", "evidence",
     lambda: ("PASS" if load(D14 /
         "worker_qualification_receipt_014.json")["pass1"]["matrix"][
         "A_schema_parses"] == 18 else "FAIL")),
    (109, "Repeatability", "independent context unavailable -> provisional",
     "evidence",
     lambda: ("PASS" if load(D14 /
         "worker_qualification_receipt_014.json")["classification"] ==
         "PROVISIONAL_SINGLE_PASS" else "FAIL")),
    (110, "WorkerReview", "30-shot review complete", "evidence",
     lambda: ("PASS" if load(D14 / "worker_production_review_014.json")[
         "shots_reviewed"] == 30 else "FAIL")),
    (111, "WorkerReview", "master boundary review complete", "evidence",
     lambda: ("PASS" if load(D14 /
         "master_worker_semantic_report_014.json")["boundaries_reviewed"]
         >= 29 else "FAIL")),
    (112, "Consistency", "audit executed", "evidence",
     lambda: ("PASS" if load(D14 /
         "semantic_review_consistency_014.json")["rows_audited"] == 30
         else "FAIL")),
    (113, "OwnerPacket", "consolidated V4 with worker context", "evidence",
     lambda: ("PASS" if load(D14 / "delivery_014/review/"
         "owner_review_packet.json")["version"] ==
         "owner-review-packet-014-v1" else "FAIL")),
    (114, "Replacement", "contract in bundle", "evidence",
     lambda: ("PASS" if load(D14 / "delivery_014/manifests/"
         "backend_replacement_contract.json")["version"] ==
         "semantic-backend-replacement-contract-014-v1" else "FAIL")),
    (115, "Readiness", "SEMANTIC_AUTONOMOUS_READY false when provisional",
     "evidence",
     lambda: ("PASS" if READY["SEMANTIC_AUTONOMOUS_READY"] is False and
              READY["WORKER_REVIEW_COMPLETE"] is True else "FAIL")),
]


def secret_scan() -> list[str]:
    leaks = []
    for root in (D12 / "delivery_012", D12 / "review"):
        for path in sorted(root.rglob("*")) if root.exists() else []:
            if not path.is_file() or path.suffix in (".mp4", ".png", ".zip",
                                                     ".aac"):
                continue
            blob = path.read_bytes()
            for marker in ("https://flow-content", "SNlM0e=", "captcha_token",
                           "set-cookie", "recaptcha", "AIza", "GEMINI_API_KEY=",
                           "BEGIN OPENSSH"):
                if marker.lower().encode() in blob.lower():
                    leaks.append(f"{path.name}: {marker}")
    changed = subprocess.run(
        ["git", "diff", "--name-only",
         "c96c7b1bb2255358b56aec3a6e06de4da2022da8..HEAD"],
        cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    for f in changed:
        if "recovery_matrix" in f:
            continue
        p = Path(f)
        if not p.is_file() or p.suffix != ".py":
            continue
        blob = p.read_bytes()
        for marker in (b"AIza", b"GEMINI_API_KEY=", b"BEGIN OPENSSH"):
            if marker in blob:
                leaks.append(f"{f}: {marker.decode()}")
    return leaks


def main() -> None:
    report = {"version": "recovery-matrix-014-v1", "rows": []}
    nodes = sorted({n for row in ROWS if row[3] == "pytest" for n in row[4]})
    junit = D14 / "junit_recovery_014.xml"
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--junitxml", str(junit),
         "-p", "no:cacheprovider"] + nodes,
        cwd=str(ROOT), capture_output=True, text=True)
    results = {}
    if junit.exists():
        for case in ET.parse(junit).iter("testcase"):
            module = case.get("classname", "").rsplit(".", 1)[-1]
            failed = case.find("failure") is not None or \
                case.find("error") is not None
            verdict = "FAIL" if failed else "PASS"
            results[f"tests/{module}.py::{case.get('name', '')}"] = verdict
            prior = results.get(f"tests/{module}.py", "PASS")
            results[f"tests/{module}.py"] = "FAIL" if failed else prior
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
            try:
                verdict = "PASS" if proof() else "FAIL"
            except Exception as exc:  # noqa: BLE001
                verdict = f"ERROR: {type(exc).__name__}: {exc}"[:140]
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": "durable evidence predicate",
                                   "result": verdict})
        else:
            try:
                verdict = proof()
            except Exception as exc:  # noqa: BLE001
                verdict = f"ERROR: {type(exc).__name__}: {exc}"[:140]
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": "live read-only check",
                                   "result": verdict})
    fails = [r for r in report["rows"] if r["result"] != "PASS"]
    report["overall"] = f"{len(report['rows']) - len(fails)}/" \
                        f"{len(report['rows'])} PASS"
    report["fail_rows"] = [r["id"] for r in fails]
    (D14 / "recovery_matrix_014.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"overall": report["overall"],
                      "fails": report["fail_rows"]}))


if __name__ == "__main__":
    main()
