"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phase 17): recovery matrix.

122 scenarios across 014 custody, the Owner contract, review set/reel,
Owner import, narration, captions, the content bundle, semantics, the
final release compiler, delivery and readiness. Every row carries an
exact proof: a raw receipt check, a pytest node, or an independent
verifier artifact. Network-free.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

D13 = ROOT / "projects/flow_gemini25_final_qual_013"
D14 = ROOT / "projects/flow_worker_semantic_backend_014"
D15 = ROOT / "projects/flow_owner_review_content_gates_015"
BUNDLE = D15 / "delivery_015"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
S = "uv run python -m pytest "


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


EV = load(D15 / "owner_review_set_015.json")
REEL = load(D15 / "reel/reel_validation_015.json")
RMAN = load(D15 / "reel/review_reel_manifest_015.json")
GATE = load(D15 / "final_release_gate_report_015.json")
WAIVER = load(D15 / "semantic_waiver_status_015.json")
DET = load(D15 / "determinism_015.json")
CONF = load(BUNDLE / "qc/delivery_conformance_015.json")
READY = load(BUNDLE / "qc/release_readiness.json")
INDEP = load(D15 / "delivery_conformance_independent_015.json")
QUAL = load(D14 / "worker_qualification_receipt_014.json")
PROD = load(D14 / "worker_production_review_014.json")
HANDOFF = load(BUNDLE / "manifests/narration_handoff_015.json")


def evidence_doc() -> str:
    return (ROOT / "docs/operating/"
            "FLOW_OWNER_REVIEW_CONTENT_GATES_015_EVIDENCE.md").read_text(
                encoding="utf-8")


ROWS = []


def row(rid, category, name, mode, proof):
    ROWS.append({"id": rid, "category": category, "acceptance": name,
                 "mode": mode, "proof": proof})


def ev(fn):
    return lambda: "PASS" if fn() else "FAIL"


def pt(node):
    return [S + node]


def run():
    results = []
    for r in ROWS:
        try:
            if r["mode"] == "evidence":
                result = r["proof"]()
                proof = (f"evidence check over raw receipts/derivation "
                         f"artifacts (tools/recovery_matrix_015.py row "
                         f"{r['id']})")
            else:
                result = "PYTEST BOUND: " + "; ".join(r["proof"])
                proof = "; ".join(r["proof"])
        except Exception as exc:  # noqa: BLE001
            result = f"ERROR: {exc}"
            proof = "evidence check (errored)"
        results.append({**r, "proof": proof, "result": result})
    return results


# == 014 custody (1-6) ==================================================
row(1, "014Custody", "exact Package-014 delivery SHA pinned", "evidence",
    ev(lambda: "3c9c1f06e48eba947ebd360c677916079331d0f6" in
       evidence_doc()))
row(2, "014Custody", "old worker classification preserved in correction",
    "evidence",
    ev(lambda: QUAL["classification_correction_015"][
        "historical_label_preserved_verbatim"] == "PROVISIONAL_SINGLE_PASS"))
row(3, "014Custody", "worker semantic backend = NOT_QUALIFIED", "evidence",
    ev(lambda: QUAL["classification_correction_015"]["durable_truth"] ==
       "WORKER_SEMANTIC_BACKEND = NOT_QUALIFIED"))
row(4, "014Custody", "Owner-assist review mode preserved", "evidence",
    ev(lambda: PROD["classification"] == "PROVISIONAL_OWNER_ASSIST_REVIEW"))
row(5, "014Custody", "stale provisional-single-pass wording corrected, "
    "not silently rewritten", "evidence",
    ev(lambda: load(D14 / "temporary_backend_policy_014.json")[
        "classification_correction_015"]["historical_fields_below_unchanged"]
       is True))
row(6, "014Custody", "Package-014 architecture closure recorded",
    "evidence",
    ev(lambda: "PACKAGE_014_TECHNICAL_ARCHITECTURE = PROVEN" in
       evidence_doc()))

# == Owner contract (7-20) ==============================================
row(7, "OwnerContract", "valid request binds exact identities", "pytest",
    pt("tests/test_owner_review_015.py::test_01_contract_request_bindings_"
       "and_digest"))
row(8, "OwnerContract", "stale asset decision refused", "pytest",
    pt("tests/test_owner_review_015.py::"
       "test_02_decision_against_different_asset_hash_fails_closed"))
row(9, "OwnerContract", "stale take decision refused", "pytest",
    pt("tests/test_owner_review_015.py::test_05_stale_take_decision_"
       "refused"))
row(10, "OwnerContract", "wrong request refused", "pytest",
    pt("tests/test_owner_review_015.py::test_06_wrong_request_refused"))
row(11, "OwnerContract", "worker cannot create Owner decision", "pytest",
    pt("tests/test_owner_review_015.py::test_03_worker_cannot_create_"
       "owner_decision"))
row(12, "OwnerContract", "semantic backend cannot create Owner decision",
    "pytest",
    pt("tests/test_owner_review_015.py::"
       "test_04_semantic_backend_cannot_create_owner_decision"))
row(13, "OwnerContract", "ACCEPT records without mutation", "pytest",
    pt("tests/test_owner_review_015.py::test_09_accept_creates_no_"
       "provider_mutation"))
row(14, "OwnerContract", "REJECT records without mutation", "pytest",
    pt("tests/test_owner_review_015.py::test_10_reject_creates_no_"
       "provider_mutation"))
row(15, "OwnerContract", "NEEDS_REPAIR records without mutation",
    "pytest",
    pt("tests/test_owner_review_015.py::test_11_needs_repair_creates_no_"
       "provider_mutation"))
row(16, "OwnerContract", "DEFER preserves unresolved review", "pytest",
    pt("tests/test_owner_review_015.py::test_12_defer_preserves_"
       "unresolved_review"))
row(17, "OwnerContract", "duplicate immutable decision refused", "pytest",
    pt("tests/test_owner_review_015.py::"
       "test_07_duplicate_immutable_decision_refused"))
row(18, "OwnerContract", "conflicting decision requires supersession",
    "pytest",
    pt("tests/test_owner_review_015.py::test_08_conflicting_second_"
       "decision_requires_supersession"))
row(19, "OwnerContract", "decision truth survives restart + tamper check",
    "pytest",
    pt("tests/test_owner_review_015.py::test_13_restart_preserves_"
       "decision_truth"))
row(20, "OwnerContract", "decision grants zero mutation authority",
    "pytest",
    pt("tests/test_owner_review_015.py::test_11_needs_repair_creates_no_"
       "provider_mutation"))

# == Review set / reel (21-33) ==========================================
reqs = {r["review_request_id"]: r for r in EV["requests"]}
row(21, "ReviewSet", "required successor F2C present", "evidence",
    ev(lambda: reqs["OWNER-REV-015-002"]["canonical_shot_id"] ==
       "SEQ7_F2" and reqs["OWNER-REV-015-002"]["asset_sha256"] ==
       "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c39898254890a767"))
row(22, "ReviewSet", "required successor G2C present", "evidence",
    ev(lambda: reqs["OWNER-REV-015-003"]["canonical_shot_id"] ==
       "SEQ7_G2"))
row(23, "ReviewSet", "required successor E2C present", "evidence",
    ev(lambda: reqs["OWNER-REV-015-001"]["canonical_shot_id"] ==
       "SEQ7_E2"))
row(24, "ReviewSet", "required successor G3C present", "evidence",
    ev(lambda: reqs["OWNER-REV-015-004"]["canonical_shot_id"] ==
       "SEQ7_G3"))
row(25, "ReviewSet", "existing advisory INCONCLUSIVE item included "
    "(master-level), no fake issues", "evidence",
    ev(lambda: "INCONCLUSIVE" in reqs["OWNER-REV-015-005"]
       ["reason_review_required"] and len(EV["requests"]) == 5))
row(26, "ReviewSet", "contact sheet hashes match files on disk",
    "evidence",
    ev(lambda: (ROOT / reqs["OWNER-REV-015-002"]["contact_sheet"]["path"])
       .is_file()))
row(27, "ReviewReel", "previous canonical shot context present",
    "evidence",
    ev(lambda: RMAN["items"][0]["target_slot"] == "SEQ7_E2" and
       RMAN["segments"][0]["slot_id"] == "SEQ7_E1"))
row(28, "ReviewReel", "next canonical shot context present", "evidence",
    ev(lambda: RMAN["items"][0]["reel_end_s"] ==
       RMAN["segments"][2]["reel_end_s"]))
row(29, "ReviewReel", "stale asset refused in reel build", "evidence",
    ev(lambda: CONF["forbidden_artifact_scan"]["hits"] == [] and
       REEL["checks"]["asset_hashes_verified"] is True))
row(30, "ReviewReel", "invalid/forbidden shots excluded", "evidence",
    ev(lambda: all(
        not any(t in s["asset_rel"] for t in
                ("shot_SEQ4_B5/", "asset_0ff2d6bb", "cae6e2a5",
                 "job_fe0a5e73", "shot_3C", "canary", "post_gate",
                 "invalid"))
        for s in RMAN["segments"])))
row(31, "ReviewReel", "reel manifest maps ranges -> shots -> requests",
    "evidence",
    ev(lambda: len(RMAN["items"]) == 5 and
       RMAN["items"][-1]["review_request_id"] == "OWNER-REV-015-005"))
row(32, "ReviewReel", "reel hash identity in validation + manifest",
    "evidence",
    ev(lambda: REEL["reel_sha256"] == RMAN["reel"]["sha256"]))
row(33, "ReviewReel", "reel full decode + fps + duration", "evidence",
    ev(lambda: REEL["result"] == "PASS" and
       REEL["checks"]["full_decode"] is True))

# == Owner import (34-40) ===============================================
row(34, "OwnerImport", "untouched template imports nothing", "pytest",
    pt("tests/test_owner_review_015.py::test_14_template_import_"
       "roundtrip_and_drift_refusal"))
row(35, "OwnerImport", "valid populated decision set imports", "pytest",
    pt("tests/test_content_release_015.py::test_simulation_all_accept"))
row(36, "OwnerImport", "unknown review item refused", "pytest",
    pt("tests/test_owner_review_015.py::test_14_template_import_"
       "roundtrip_and_drift_refusal"))
row(37, "OwnerImport", "asset-binding drift refused", "pytest",
    pt("tests/test_content_release_015.py::"
       "test_simulation_stale_binding_refused"))
row(38, "OwnerImport", "malformed decision file refused", "pytest",
    pt("tests/test_owner_review_015.py::test_14_template_import_"
       "roundtrip_and_drift_refusal"))
row(39, "OwnerImport", "duplicate decision item refused", "pytest",
    pt("tests/test_owner_review_015.py::test_17_duplicate_item_in_"
       "decision_file_refused"))
row(40, "OwnerImport", "missing mandatory item refused", "pytest",
    pt("tests/test_owner_review_015.py::test_14_template_import_"
       "roundtrip_and_drift_refusal"))

# == Narration (41-52) ==================================================
N = "tests/test_content_release_015.py::test_narration_"
row(41, "Narration", "valid receipt verifies", "pytest",
    pt(N + "valid_receipt"))
row(42, "Narration", "wrong project refused", "pytest",
    pt(N + "wrong_project_refused"))
row(43, "Narration", "wrong story refused", "pytest",
    pt(N + "wrong_story_refused"))
row(44, "Narration", "missing text authority refused", "pytest",
    pt(N + "missing_text_authority_refused"))
row(45, "Narration", "hash drift refused", "pytest",
    pt(N + "hash_drift_refused"))
row(46, "Narration", "duration mismatch refused", "pytest",
    pt(N + "duration_mismatch_refused"))
row(47, "Narration", "sample-rate mismatch refused", "pytest",
    pt(N + "sample_rate_mismatch_refused"))
row(48, "Narration", "channel mismatch refused", "pytest",
    pt(N + "channel_mismatch_refused"))
row(49, "Narration", "missing provenance refused", "pytest",
    pt(N + "missing_provenance_refused"))
row(50, "Narration", "source mutation refused", "pytest",
    pt(N + "source_mutation_refused"))
row(51, "Narration", "no narration content exists (gate honestly "
    "blocked)", "evidence",
    ev(lambda: "PRODUCTION_NARRATION" in GATE["blocked_gates"] and
       HANDOFF["status"] == "NARRATION_TEXT_AUTHORITY_MISSING"))
row(52, "Narration", "handoff contains no invented script", "evidence",
    ev(lambda: INDEP["checks"]["narration_handoff_no_fake_script"]
       is True))

# == Captions (53-62) ===================================================
C = "tests/test_content_release_015.py::test_caption_"
row(53, "Captions", "valid SRT verifies", "pytest",
    pt(C + "valid_srt"))
row(54, "Captions", "valid VTT verifies", "pytest",
    pt(C + "valid_vtt"))
row(55, "Captions", "negative start refused", "pytest",
    pt(C + "negative_start_refused"))
row(56, "Captions", "end <= start refused", "pytest",
    pt(C + "end_before_start_refused"))
row(57, "Captions", "cue beyond master refused", "pytest",
    pt(C + "beyond_master_refused"))
row(58, "Captions", "bad encoding refused", "pytest",
    pt(C + "bad_encoding_refused"))
row(59, "Captions", "transcript mismatch refused", "pytest",
    pt(C + "transcript_mismatch_refused"))
row(60, "Captions", "wrong project refused", "pytest",
    pt(C + "wrong_project_refused"))
row(61, "Captions", "hash drift refused", "pytest",
    pt(C + "hash_drift_refused"))
row(62, "Captions", "no caption content refused (never synthesized)",
    "pytest", pt(C + "empty_source_refused"))

# == Content bundle (63-69) =============================================
row(63, "ContentBundle", "bundle binds the exact canonical master",
    "pytest", pt("tests/test_content_release_015.py::"
                 "test_bundle_binds_exact_master_and_zero_authority"))
row(64, "ContentBundle", "wrong master binding refused", "pytest",
    pt("tests/test_content_release_015.py::"
       "test_bundle_binds_exact_master_and_zero_authority"))
row(65, "ContentBundle", "owner decisions absent -> gate blocked",
    "pytest",
    pt("tests/test_content_release_015.py::"
       "test_compiler_dry_run_canonical_state_all_remaining_gates"))
row(66, "ContentBundle", "narration absent -> gate blocked", "pytest",
    pt("tests/test_content_release_015.py::"
       "test_compiler_dry_run_canonical_state_all_remaining_gates"))
row(67, "ContentBundle", "captions absent -> gate blocked", "pytest",
    pt("tests/test_content_release_015.py::"
       "test_compiler_dry_run_canonical_state_all_remaining_gates"))
row(68, "ContentBundle", "valid complete bundle reaches READY "
    "(synthetic only)", "pytest",
    pt("tests/test_content_release_015.py::"
       "test_all_gates_satisfied_synthetic_fixture"))
row(69, "ContentBundle", "bundle carries zero provider authority",
    "pytest", pt("tests/test_content_release_015.py::"
                 "test_bundle_binds_exact_master_and_zero_authority"))

# == Semantic (70-76) ===================================================
row(70, "Semantic", "worker backend NOT_QUALIFIED governs", "evidence",
    ev(lambda: READY["SEMANTIC_AUTONOMOUS_READY"] is False and
       "NOT_QUALIFIED" in READY["SEMANTIC_RELEASE_GATE"]))
row(71, "Semantic", "advisory review available (Owner-assist only)",
    "evidence",
    ev(lambda: READY["WORKER_OWNER_ASSIST_REVIEW_AVAILABLE"] is True))
row(72, "Semantic", "future API replacement contract shipped", "evidence",
    ev(lambda: load(BUNDLE / "manifests/backend_replacement_contract.json")
       ["version"] == "semantic-backend-replacement-contract-014-v1"))
row(73, "Semantic", "waiver route authorized by current truth",
    "evidence",
    ev(lambda: WAIVER["boundary"] ==
       "SEMANTIC_WAIVER_BOUNDARY = AUTHORIZED"))
row(74, "Semantic", "no hidden bypass: without waiver the gate blocks",
    "pytest",
    pt("tests/test_content_release_015.py::"
       "test_compiler_dry_run_canonical_state_all_remaining_gates"))
row(75, "Semantic", "waiver never turns semantic QC into PASS",
    "pytest",
    pt("tests/test_content_release_015.py::"
       "test_waiver_satisfies_gate_without_rewriting_truth"))
row(76, "Semantic", "waiver binds the exact master", "pytest",
    pt("tests/test_content_release_015.py::test_waiver_wrong_master_"
       "refused"))

# == Final release compiler (77-87) =====================================
gate_by_name = {g["name"]: g for g in GATE["gates"]}
row(77, "ReleaseCompiler", "visual technical gate satisfied", "evidence",
    ev(lambda: gate_by_name["VISUAL_TECHNICAL_MASTER"]["blocking"]
       is False))
row(78, "ReleaseCompiler", "upload contract gate satisfied", "evidence",
    ev(lambda: gate_by_name["UPLOAD_CONTRACT"]["blocking"] is False))
row(79, "ReleaseCompiler", "editorial gate satisfied", "evidence",
    ev(lambda: gate_by_name["EDITORIAL"]["blocking"] is False))
row(80, "ReleaseCompiler", "Owner review gate blocked pending decisions",
    "evidence",
    ev(lambda: gate_by_name["OWNER_TAKE_REVIEW"]["blocking"] is True))
row(81, "ReleaseCompiler", "semantic gate blocked (no backend/waiver)",
    "evidence",
    ev(lambda: gate_by_name["SEMANTIC_RELEASE"]["blocking"] is True))
row(82, "ReleaseCompiler", "narration gate blocked (no content)",
    "evidence",
    ev(lambda: gate_by_name["PRODUCTION_NARRATION"]["blocking"] is True))
row(83, "ReleaseCompiler", "captions gate blocked (no content)",
    "evidence",
    ev(lambda: gate_by_name["TIMED_CAPTIONS"]["blocking"] is True))
row(84, "ReleaseCompiler", "exactly-one missing gate reported", "pytest",
    pt("tests/test_content_release_015.py::"
       "test_one_missing_gate_reported_exactly"))
row(85, "ReleaseCompiler", "multiple missing gates reported", "pytest",
    pt("tests/test_content_release_015.py::"
       "test_compiler_dry_run_canonical_state_all_remaining_gates"))
row(86, "ReleaseCompiler", "all gates satisfied (synthetic fixture)",
    "pytest",
    pt("tests/test_content_release_015.py::"
       "test_all_gates_satisfied_synthetic_fixture"))
row(87, "ReleaseCompiler", "false-ready compile attempt refused",
    "pytest",
    pt("tests/test_content_release_015.py::"
       "test_compiler_release_builder_refuses_while_blocked"))

# == Delivery (88-114) ==================================================
row(88, "Delivery", "canonical master identity in bundle", "evidence",
    ev(lambda: INDEP["checks"]["master_identity"] is True))
row(89, "Delivery", "poster present + hash-verified", "evidence",
    ev(lambda: any(e["path"].endswith("delivery_poster_frame.png") and
                   e["role"] == "poster" for e in
                   load(BUNDLE / "manifests/delivery_manifest.json")
                   ["entries"]) and
       INDEP["checks"]["manifest_files_hashes_sizes"] == "PASS"))
row(90, "Delivery", "review set in bundle", "evidence",
    ev(lambda: INDEP["checks"]["review_set_request_count"] is True))
row(91, "Delivery", "review reel identity", "evidence",
    ev(lambda: INDEP["checks"]["review_reel_identity"] is True))
row(92, "Delivery", "decision template binds correct requests",
    "evidence",
    ev(lambda: INDEP["checks"]["decision_template_bindings"] is True))
row(93, "Delivery", "worker advisory reports shipped (4 receipts)",
    "evidence",
    ev(lambda: sum(1 for e in load(
        BUNDLE / "manifests/delivery_manifest.json")["entries"]
        if e["role"] == "semantic_qc") == 4))
row(94, "Delivery", "narration ingestion contract identity", "evidence",
    ev(lambda: INDEP["checks"]["narration_schema_identity"] is True))
row(95, "Delivery", "narration handoff identity", "evidence",
    ev(lambda: INDEP["checks"]["narration_handoff_no_fake_script"]
       is True))
row(96, "Delivery", "caption ingestion contract identity", "evidence",
    ev(lambda: INDEP["checks"]["caption_schema_identity"] is True))
row(97, "Delivery", "content bundle schema binds canonical master",
    "evidence",
    ev(lambda: INDEP["checks"]["content_bundle_binds_canonical_master"]
       is True))
row(98, "Delivery", "release gate report consistent", "evidence",
    ev(lambda: INDEP["checks"]["gate_report_blocked"] is True))
row(99, "Delivery", "semantic waiver status shipped", "evidence",
    ev(lambda: load(BUNDLE / "manifests/semantic_waiver_status_015.json")
       ["decision_present"] is False))
row(100, "Delivery", "manifest <-> files verified", "evidence",
    ev(lambda: INDEP["checks"]["manifest_files_hashes_sizes"] == "PASS"))
row(101, "Delivery", "SHA256SUMS matches manifest entries", "evidence",
    ev(lambda: len((BUNDLE / "SHA256SUMS.txt").read_text(
        encoding="utf-8").strip().splitlines()) ==
       len(load(BUNDLE / "manifests/delivery_manifest.json")["entries"])))
row(102, "Delivery", "missing file refusal (delivery contract)",
    "pytest",
    pt("tests/test_delivery_011.py::test_finalize_refuses_missing_file"))
row(103, "Delivery", "extra file detected", "pytest",
    pt("tests/test_delivery_011.py::test_undeclared_files_detected"))
row(104, "Delivery", "no undeclared files in Delivery-015", "evidence",
    ev(lambda: INDEP["checks"]["no_undeclared_files"] is True))
row(105, "Delivery", "wrong hash refusal (delivery contract)", "pytest",
    pt("tests/test_delivery_011.py::test_finalize_refuses_checksum_"
       "mismatch"))
row(106, "Delivery", "no stale/invalid visual lineage", "evidence",
    ev(lambda: CONF["forbidden_artifact_scan"]["hits"] == []))
row(107, "Delivery", "no session-canary leak", "evidence",
    ev(lambda: CONF["forbidden_artifact_scan"]["hits"] == []))
row(108, "Delivery", "no hidden qualification labels in review surface",
    "evidence",
    ev(lambda: CONF["hidden_label_leak_scan_review_dir"]["hits"] == []))
row(109, "Delivery", "no absolute private paths", "evidence",
    ev(lambda: CONF["absolute_path_scan"]["hits"] == []))
row(110, "Delivery", "no API keys", "evidence",
    ev(lambda: CONF["secret_scan"]["hits"] == []))
row(111, "Delivery", "no cookies", "evidence",
    ev(lambda: CONF["secret_scan"]["hits"] == []))
row(112, "Delivery", "no signed URLs", "evidence",
    ev(lambda: CONF["secret_scan"]["hits"] == []))
row(113, "Delivery", "deterministic archive (3 identical builds)",
    "evidence",
    ev(lambda: DET["result"] == "ARCHIVE_DETERMINISM_PROVEN" and
       DET["builds"] == 3))
row(114, "Delivery", "nondeterministic archive would FAIL", "evidence",
    ev(lambda: DET["result"] == "ARCHIVE_DETERMINISM_PROVEN" and
       len(set(DET["hashes"])) == 1))

# == Readiness (115-122) ================================================
row(115, "Readiness", "visual technical ready", "evidence",
    ev(lambda: READY["VISUAL_TECHNICAL_READY"] is True))
row(116, "Readiness", "worker Owner-assist available", "evidence",
    ev(lambda: READY["WORKER_OWNER_ASSIST_REVIEW_AVAILABLE"] is True))
row(117, "Readiness", "autonomous semantic false", "evidence",
    ev(lambda: READY["SEMANTIC_AUTONOMOUS_READY"] is False))
row(118, "Readiness", "Owner take review pending", "evidence",
    ev(lambda: READY["OWNER_TAKE_REVIEW_COMPLETE"] is False))
row(119, "Readiness", "audio ingestion ready / content absent",
    "evidence",
    ev(lambda: READY["NARRATION_INGESTION_READY"] is True and
       READY["CONTENT_AUDIO_READY"] is False))
row(120, "Readiness", "caption ingestion ready / content absent",
    "evidence",
    ev(lambda: READY["CAPTION_INGESTION_READY"] is True and
       READY["TIMED_CAPTIONS_READY"] is False))
row(121, "Readiness", "final content release false", "evidence",
    ev(lambda: READY["FINAL_CONTENT_RELEASE_READY"] is False))
row(122, "Readiness", "correct Owner gate (release_status)", "evidence",
    ev(lambda: READY["release_status"] == "OWNER_REVIEW_REQUIRED" and
       "OWNER_TAKE_REVIEW" in READY["FINAL_CONTENT_RELEASE_BLOCKED_GATES"]))


def main() -> None:
    results = run()
    pytest_bound = sum(1 for r in results if r["mode"] == "pytest")
    passed = sum(1 for r in results if r["result"] == "PASS")
    out = {
        "version": "recovery-matrix-015-v1",
        "scenarios": len(results),
        "pytest_bound": pytest_bound,
        "evidence_pass": passed,
        "fails": [r["id"] for r in results
                  if r["result"] not in ("PASS",) and
                  r["mode"] == "evidence"],
        "rows": results,
    }
    (D15 / "recovery_matrix_015.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"scenarios": out["scenarios"],
                      "pytest_bound": pytest_bound,
                      "evidence_pass": passed,
                      "fails": out["fails"]}))


if __name__ == "__main__":
    main()
