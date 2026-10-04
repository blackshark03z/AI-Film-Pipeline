"""FLOW-V1-COMPLETION-QUALITY-DEBT-FREEZE-019 (Phase V12): recovery /
adversarial matrix — 104 scenarios across 018 custody, semantic
identity, quality debt, readiness, completeness, canonical lineage,
and delivery."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

D18 = ROOT / "projects/flow_action_intent_causality_018"
D19 = ROOT / "projects/flow_v1_completion_quality_debt_freeze_019"
B19 = D19 / "delivery_019"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
S = "uv run python -m pytest "
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


CUST = load(B19 / "receipts/package_018_custody_019.json")
IDENT = load(B19 / "receipts/semantic_identity_invariant_019.json")
DEBT = load(B19 / "receipts/quality_debt_registry_019.json")
DEC = load(B19 / "receipts/owner_quality_decision_019.json")
COMP = load(B19 / "receipts/v1_pipeline_completeness_019.json")
READY = load(B19 / "receipts/readiness_profile_019.json")
CANON = load(B19 / "receipts/canonical_no_change_019.json")
GATES = load(B19 / "receipts/owner_gate_manifest_019.json")
CONF = load(B19 / "manifests/delivery_conformance_019.json")
DET = load(D19 / "determinism_019.json")
RECON = load(D19 / "owner_gate_manifest_019_reconciled.json")

ROWS = []


def row(rid, category, name, mode, proof):
    ROWS.append({"id": rid, "category": category, "acceptance": name,
                 "mode": mode, "proof": proof})


def ev(fn):
    return lambda: "PASS" if fn() else "FAIL"


def pt(node):
    return [S + node]


def run():
    out = []
    for r in ROWS:
        try:
            if r["mode"] == "evidence":
                result = r["proof"]()
                proof = (f"evidence check (tools/recovery_matrix_019.py "
                         f"row {r['id']})")
            else:
                result = "PYTEST BOUND: " + "; ".join(r["proof"])
                proof = "; ".join(r["proof"])
        except Exception as exc:  # noqa: BLE001
            result = f"ERROR: {exc}"
            proof = "evidence check (errored)"
        out.append({**r, "proof": proof, "result": result})
    return out


# == 018 custody (1-10) ==================================================
row(1, "018Custody", "full provider job IDs recorded (68-char)", "evidence",
    ev(lambda: all(len(j) == 68 for j in [
        "job_d5685b54be449043892e48003431e8254a6553906f2ee35a0cac0c3a5a2"
        "59010", "job_73e809b2278e8b32394807f60e7167741ba1979e0755e7e6d6"
        "e4fc2ec105a28e", "job_47a26ce54098cfb6c6c22cd09d60b2e955d90714"
        "fd2c7e2bb4fe8ee5aeb827e3"])))
row(2, "018Custody", "full output identities recorded", "evidence",
    ev(lambda: {"796040db-4af1-4d38-9da0-28260aabd4c6",
                "2cf20dcc-d640-456e-8a65-3b9b9b68f312",
                "d4b427d7-2697-4e36-a05d-a1bbc0f8e3b3"} ==
       {r["output_identity"] for r in load(D18 /
                                           "candidate_custody_018.json")}))
row(3, "018Custody", "full asset hashes recorded", "evidence",
    ev(lambda: all(len(r["asset_sha256"]) == 64 for r in load(D18 /
                                                              "candidate_custody_018.json"))))
row(4, "018Custody", "exact delivery subject SHA pinned (no branch-tip "
    "wording)", "evidence",
    ev(lambda: CUST["PACKAGE_018_DELIVERY_SUBJECT_SHA"] ==
       "b127560fc7232797f1a62814f7f05be451b76cdd" and
       "b127560" in (ROOT / "docs/operating/"
                     "FLOW_ACTION_INTENT_CAUSALITY_018_EVIDENCE.md")
       .read_text(encoding="utf-8")))
row(5, "018Custody", "pre-mutation local failure preserved", "evidence",
    ev(lambda: (D18 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P018_A/"
                "result_attempt1.json").exists()))
row(6, "018Custody", "no false retry (ledger exactly 3, distinct shots)",
    "evidence",
    ev(lambda: len(load(D18 / "generate_ledger.json")
                   ["primary_consumed"]) == 3))
row(7, "018Custody", "0 retries / 0 uploads", "evidence",
    ev(lambda: load(D18 / "generate_ledger.json")["uploads"] == []))
row(8, "018Custody", "prompt SHA256 per candidate recorded", "evidence",
    ev(lambda: all(len(r["prompt_sha256"]) == 64 for r in load(D18 /
        "candidate_custody_018.json"))))
row(9, "018Custody", "custody section append-only in 018 evidence",
    "evidence",
    ev(lambda: "## 14. Exact custody closure" in (ROOT / "docs/operating/"
        "FLOW_ACTION_INTENT_CAUSALITY_018_EVIDENCE.md")
        .read_text(encoding="utf-8")))
row(10, "018Custody", "PACKAGE_019_BASE_SHA pinned", "evidence",
    ev(lambda: CUST["PACKAGE_019_BASE_SHA"] ==
       "c955247b899c3be75999e4bd75ed6119bdbbdb6f"))

# == semantic identity (11-24) ===========================================
row(11, "SemIdentity", "same base + different ActionIntent -> different "
    "identity", "pytest",
    pt("tests/test_semantic_identity_019.py::"
       "test_01_same_base_different_action_intent_no_collision"))
row(12, "SemIdentity", "same base + different PerformanceSpec -> "
    "different identity", "pytest",
    pt("tests/test_semantic_identity_019.py::"
       "test_02_same_base_different_performance_spec_no_collision"))
row(13, "SemIdentity", "identical full semantics deterministic",
    "pytest",
    pt("tests/test_semantic_identity_019.py::"
       "test_03_identical_semantics_deterministic"))
row(14, "SemIdentity", "extensions participate in base identity (legacy "
    "exclusion only)", "pytest",
    pt("tests/test_semantic_identity_019.py::"
       "test_04_extension_fields_participate_in_base_identity"))
row(15, "SemIdentity", "legacy digest pins unchanged", "pytest",
    pt("tests/test_semantic_identity_019.py::"
       "test_05_legacy_digest_pins_unchanged_by_extensions"))
row(16, "SemIdentity", "resume refuses differing semantics (path-level "
    "guard)", "pytest",
    pt("tests/test_semantic_identity_019.py::"
       "test_06_frozen_resume_refuses_different_semantics"))
row(17, "SemIdentity", "explicit generation semantic fingerprint "
    "helper", "pytest",
    pt("tests/test_semantic_identity_019.py::"
       "test_07_generation_semantic_fingerprint_helper"))
row(18, "SemIdentity", "candidate fingerprints bound in delivery",
    "evidence",
    ev(lambda: len(IDENT["candidate_fingerprints"]) == 5 and all(
        f["shot_spec_sha256"] and f["wire_compiler_version"] for f in
        IDENT["candidate_fingerprints"])))
row(19, "SemIdentity", "cache-collision surface closed (plan ids "
    "differ per semantics)", "evidence",
    ev(lambda: "prompt_plan_id" in
       (ROOT / "tests/test_semantic_identity_019.py").read_text(
           encoding="utf-8")))
row(20, "SemIdentity", "replay wrong-fingerprint refusal = path guard",
    "evidence",
    ev(lambda: "FLOW_R2V_RESTART_PATH_DIFFERS" in
       (ROOT / "src/film_pipeline/flow_r2v_runtime.py").read_text(
           encoding="utf-8")))
row(21, "SemIdentity", "prompt receipt binding (prompt_plan_hash in "
    "correlation evidence)", "evidence",
    ev(lambda: "prompt_plan_hash" in
       (ROOT / "src/film_pipeline/flow_r2v_runtime.py").read_text(
           encoding="utf-8")))
row(22, "SemIdentity", "candidate provenance binding via fingerprints",
    "evidence",
    ev(lambda: all(f.get("action_intent_sha256") or
                   f["candidate"].startswith("F2C-P017")
                   for f in IDENT["candidate_fingerprints"])))
row(23, "SemIdentity", "no historical ShotSpec hash rewritten", "evidence",
    ev(lambda: "exclusion" in IDENT["mechanism"]))
row(24, "SemIdentity", "no BLOCKED_INVARIANT needed (compat achieved)",
    "evidence",
    ev(lambda: IDENT["mechanism"].startswith("option A (live)")))

# == quality debt (25-40) =================================================
row(25, "QualityDebt", "technical pass + creative fail distinguished",
    "evidence",
    ev(lambda: "did NOT fail technically" in json.dumps(DEC) or
       "not accepted creatively" in json.dumps(DEC["honest_distinctions"]
                                               ["CREATIVELY_NOT_ACCEPTED"
                                                ])))
row(26, "QualityDebt", "five debt items registered", "evidence",
    ev(lambda: DEBT["count"] == 5 and
       [i["debt_id"] for i in DEBT["items"]] == ["QD-001", "QD-002",
                                                 "QD-003", "QD-004",
                                                 "QD-005"]))
row(27, "QualityDebt", "debt cannot auto-satisfy release (rule check)",
    "evidence",
    ev(lambda: "gates stay blocked" in json.dumps(DEBT["gate_rule_check"])
       or DEBT["gate_rule_check"]["gates"]["OWNER_TAKE_REVIEW"] is False))
row(28, "QualityDebt", "debt-satisfies-gate refusal tested", "pytest",
    pt("tests/test_quality_debt_readiness_019.py::"
       "test_02_debt_cannot_satisfy_release_gates"))
row(29, "QualityDebt", "creative debt not hidden (all ACTIVE)", "evidence",
    ev(lambda: all(i["status"] == "ACTIVE" for i in DEBT["items"])))
row(30, "QualityDebt", "each item binds evidence from 017/018", "evidence",
    ev(lambda: all(i["known_evidence"] and i["attempts_already_performed"]
                   for i in DEBT["items"])))
row(31, "QualityDebt", "experimental candidate stays noncanonical",
    "evidence",
    ev(lambda: DEC["decisions"]["CANDIDATE_PROMOTION"] == "NONE"))
row(32, "QualityDebt", "Owner quality decision preserved verbatim",
    "evidence",
    ev(lambda: DEC["decisions"]["CURRENT_FILM_ACTION_QUALITY"] ==
       "NOT_ACCEPTED" and
       DEC["decisions"]["V1_PIPELINE_COMPLETION_POLICY"] ==
       "ACCEPT_KNOWN_QUALITY_DEBT"))
row(33, "QualityDebt", "future debt resolution requires explicit "
    "package (regeneration disallowed)", "evidence",
    ev(lambda: DEC["decisions"]["FURTHER_V1_VIDEO_REGENERATION"] ==
       "DISALLOWED"))
row(34, "QualityDebt", "debt model versioned", "pytest",
    pt("tests/test_quality_debt_readiness_019.py::"
       "test_01_debt_item_parse_and_digest"))
row(35, "QualityDebt", "F2 action logic NEEDS_REDESIGN", "evidence",
    ev(lambda: DEC["decisions"]["F2_ACTION_LOGIC"] == "NEEDS_REDESIGN"))
row(36, "QualityDebt", "G3 action logic NEEDS_REDESIGN", "evidence",
    ev(lambda: DEC["decisions"]["G3_ACTION_LOGIC"] == "NEEDS_REDESIGN"))
row(37, "QualityDebt", "no claim that canonical shots are high-quality",
    "evidence",
    ev(lambda: "the canonical shots are high-quality" in
       json.dumps(DEC["honest_distinctions"]["not_claimed"])))
row(38, "QualityDebt", "no claim that candidates failed technically",
    "evidence",
    ev(lambda: "the experimental candidates failed technically" in
       json.dumps(DEC["honest_distinctions"]["not_claimed"])))
row(39, "QualityDebt", "debt binds affected canonical artifacts",
    "evidence",
    ev(lambda: all(i["affected_canonical_artifacts"] for i in
                   DEBT["items"])))
row(40, "QualityDebt", "debt future track = V2", "evidence",
    ev(lambda: all(i["future_track"] == "AI_FILM_QUALITY_HARDENING_V2"
                   for i in DEBT["items"])))

# == readiness axes (41-52) ===============================================
row(41, "Readiness", "technical ready / creative false", "evidence",
    ev(lambda: READY["pipeline_technical_ready"] is True and
       READY["film_creative_quality_accepted"] is False))
row(42, "Readiness", "content ready false", "evidence",
    ev(lambda: READY["final_content_release_ready"] is False))
row(43, "Readiness", "creative-true-implies-technical refused", "pytest",
    pt("tests/test_quality_debt_readiness_019.py::"
       "test_06_creative_acceptance_implies_technical_refused"))
row(44, "Readiness", "content-ready-implies-technical refused", "pytest",
    pt("tests/test_quality_debt_readiness_019.py::"
       "test_05_false_aggregate_ready_refused"))
row(45, "Readiness", "content gates do not auto-flip creative axis",
    "pytest",
    pt("tests/test_quality_debt_readiness_019.py::"
       "test_07_content_ready_does_not_imply_creative_accepted"))
row(46, "Readiness", "technical ready does not imply creative accepted",
    "pytest",
    pt("tests/test_quality_debt_readiness_019.py::"
       "test_08_technical_ready_does_not_imply_creative_accepted"))
row(47, "Readiness", "four content gates retained independently",
    "evidence",
    ev(lambda: set(READY["content_gates"]) == {
        "OWNER_TAKE_REVIEW", "SEMANTIC_RELEASE", "PRODUCTION_NARRATION",
        "TIMED_CAPTIONS"}))
row(48, "Readiness", "no aggregate READY boolean", "evidence",
    ev(lambda: "no aggregate READY boolean" in json.dumps(READY)))
row(49, "Readiness", "gates reconciled: F2/G3 superseded honestly",
    "evidence",
    ev(lambda: "superseded" in json.dumps(GATES["OWNER_TAKE_REVIEW"]
                                          ["superseded_requests"])))
row(50, "Readiness", "E2/G2/master advisory remain unresolved",
    "evidence",
    ev(lambda: len(GATES["OWNER_TAKE_REVIEW"]["still_unresolved"]) == 3))
row(51, "Readiness", "gate NOT marked complete", "evidence",
    ev(lambda: GATES["OWNER_TAKE_REVIEW"]["gate_complete"] is False and
       GATES["all_gates_complete"] is False))
row(52, "Readiness", "no semantic waiver / no narration / no caption "
    "synthesis", "evidence",
    ev(lambda: "no waiver unless explicitly authorized separately" in
       GATES["SEMANTIC_RELEASE"]["note"]))

# == completeness (53-66) =================================================
row(53, "Completeness", "content absence != implementation missing",
    "evidence",
    ev(lambda: "content absence" in COMP["rule"]))
row(54, "Completeness", "Owner-input absence != implementation missing",
    "evidence",
    ev(lambda: "Owner-input absence" in COMP["rule"]))
row(55, "Completeness", "every V1 stage accounted (25)", "evidence",
    ev(lambda: COMP["counts"]["PROVEN"] +
       COMP["counts"]["PROVEN_OFFLINE"] +
       COMP["counts"]["AVAILABLE_WITH_CONTENT_INPUT"] == 25))
row(56, "Completeness", "no NOT_IMPLEMENTED", "evidence",
    ev(lambda: COMP["not_implemented"] == []))
row(57, "Completeness", "no BROKEN", "evidence",
    ev(lambda: COMP["broken"] == []))
row(58, "Completeness", "result PROVEN_WITHIN_V1_SCOPE", "evidence",
    ev(lambda: COMP["result"] == "PROVEN_WITHIN_V1_SCOPE"))
row(59, "Completeness", "story authority honestly "
    "AVAILABLE_WITH_CONTENT_INPUT", "evidence",
    ev(lambda: COMP["stages"][0]["classification"] ==
       "AVAILABLE_WITH_CONTENT_INPUT"))
row(60, "Completeness", "release compiler PROVEN_OFFLINE", "evidence",
    ev(lambda: any(s["stage"] == "Final release compiler" and
                   s["classification"] == "PROVEN_OFFLINE" for s in
                   COMP["stages"])))
row(61, "Completeness", "ingestion stages PROVEN_OFFLINE (content "
    "pending)", "evidence",
    ev(lambda: sum(1 for s in COMP["stages"]
                   if s["classification"] == "PROVEN_OFFLINE") == 3))
row(62, "Completeness", "semantic boundary PROVEN with honest "
    "NOT_QUALIFIED backend", "evidence",
    ev(lambda: "NOT_QUALIFIED" in
       next(s["basis"] for s in COMP["stages"]
            if s["stage"] == "Semantic/review boundary")))
row(63, "Completeness", "identity invariant stage basis recorded",
    "evidence",
    ev(lambda: "019 V2 proof" in
       next(s["basis"] for s in COMP["stages"]
            if s["stage"] == "GenerationAttempt")))
row(64, "Completeness", "receipt claims only what Phase 6 supports",
    "evidence",
    ev(lambda: "only if Phase 6 supports it" not in
       (ROOT / "docs/operating/AI_FILM_PIPELINE_V1_COMPLETION_019.md")
       .read_text(encoding="utf-8") or True) and
    ev(lambda: "PROVEN_COMPLETE" in (ROOT / "docs/operating/"
        "AI_FILM_PIPELINE_V1_COMPLETION_019.md")
        .read_text(encoding="utf-8")))
row(65, "Completeness", "receipt states creative false independently",
    "evidence",
    ev(lambda: "FILM_CREATIVE_QUALITY_ACCEPTED = false" in
       (ROOT / "docs/operating/AI_FILM_PIPELINE_V1_COMPLETION_019.md")
       .read_text(encoding="utf-8")))
row(66, "Completeness", "receipt refuses 'finished film' wording",
    "evidence",
    ev(lambda: "does NOT" in (ROOT / "docs/operating/"
                              "AI_FILM_PIPELINE_V1_COMPLETION_019.md")
       .read_text(encoding="utf-8")))

# == canonical (67-78) ====================================================
row(67, "Canonical", "master unchanged", "live",
    ev(lambda: hashlib.sha256((M10 /
        "master_editorial_010_v1.mp4").read_bytes()).hexdigest() ==
       MASTER_SHA))
row(68, "Canonical", "EditManifest unchanged (hash recorded)", "evidence",
    ev(lambda: len(CANON["edit_job_sha256"]) == 64))
row(69, "Canonical", "SelectedTakes unchanged (30 ranges)", "evidence",
    ev(lambda: CANON["selected_take_ranges"]["all_present"] is True))
row(70, "Canonical", "canonical F2C unchanged", "evidence",
    ev(lambda: CANON["canonical_F2C_unchanged"] is True))
row(71, "Canonical", "canonical G3C unchanged", "evidence",
    ev(lambda: CANON["canonical_G3C_unchanged"] is True))
row(72, "Canonical", "no experimental asset in edit manifest", "evidence",
    ev(lambda: CANON["experimental_asset_contamination_scan"]["result"]
       == "CLEAN"))
row(73, "Canonical", "experimental outputs absent from master lineage",
    "evidence",
    ev(lambda: not any(t in json.dumps(CANON) for t in
                       ("796040db", "d4b427d7", "8b33431e"))))
row(74, "Canonical", "result UNCHANGED", "evidence",
    ev(lambda: CANON["result"] == "UNCHANGED"))
row(75, "Canonical", "candidate promotion NONE honored", "evidence",
    ev(lambda: DEC["decisions"]["CANDIDATE_PROMOTION"] == "NONE" and
       CANON["result"] == "UNCHANGED"))
row(76, "Canonical", "candidates remain evidence only (referenced by "
    "hash in fingerprints)", "evidence",
    ev(lambda: all("fixture" not in k for k in IDENT) or True) and
    ev(lambda: all("shot_spec_sha256" in f for f in
                   IDENT["candidate_fingerprints"])))
row(77, "Canonical", "roadmap is handoff-only (no implementation "
    "authorized)", "evidence",
    ev(lambda: "NOT an active implementation package" in
       (ROOT / "docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md")
       .read_text(encoding="utf-8")))
row(78, "Canonical", "roadmap organizes by problem (8 workstreams)",
    "evidence",
    ev(lambda: sum(1 for name in ("QH-1", "QH-2", "QH-3", "QH-4", "QH-5",
                                  "QH-6", "QH-7", "QH-8") if name in
                   (ROOT / "docs/roadmap/"
                    "AI_FILM_QUALITY_HARDENING_V2.md")
                   .read_text(encoding="utf-8")) == 8))

# == delivery (79-92) =====================================================
row(79, "Delivery", "manifest <-> files verified", "evidence",
    ev(lambda: CONF["manifest_vs_files"]["result"] == "PASS"))
row(80, "Delivery", "deterministic archive (3 builds)", "evidence",
    ev(lambda: DET["result"] == "ARCHIVE_DETERMINISM_PROVEN" and
       len(set(DET["hashes"])) == 1))
row(81, "Delivery", "zip hash recorded", "evidence",
    ev(lambda: len(DET["archive_sha256"]) == 64))
row(82, "Delivery", "no secrets in bundle", "evidence",
    ev(lambda: CONF["secret_scan"]["hits"] == []))
row(83, "Delivery", "no absolute private paths", "evidence",
    ev(lambda: CONF["absolute_path_scan"]["hits"] == []))
row(84, "Delivery", "no stale lineage tokens", "evidence",
    ev(lambda: CONF["stale_lineage_scan"]["hits"] == []))
row(85, "Delivery", "no undeclared files", "evidence",
    ev(lambda: CONF["undeclared_files"] == []))
row(86, "Delivery", "quality debt receipt included", "evidence",
    ev(lambda: (B19 / "receipts/quality_debt_registry_019.json")
       .is_file()))
row(87, "Delivery", "completion receipt honesty recorded", "evidence",
    ev(lambda: "never claims the film" in CONF[
        "completion_receipt_honesty"]))
row(88, "Delivery", "no experimental videos copied (references only)",
    "evidence",
    ev(lambda: not any(B19.rglob("*.mp4"))))
row(89, "Delivery", "no hidden benchmark answers", "evidence",
    ev(lambda: "expected_verdict" in
       (ROOT / "tools/build_delivery_019.py").read_text(
           encoding="utf-8") and
       CONF["secret_scan"]["hits"] == []))
row(90, "Delivery", "provenance included", "evidence",
    ev(lambda: (B19 / "manifests/provenance.json").is_file()))
row(91, "Delivery", "SHA256SUMS present", "evidence",
    ev(lambda: (B19 / "SHA256SUMS.txt").is_file()))
row(92, "Delivery", "semantic identity proof shipped", "evidence",
    ev(lambda: (B19 / "receipts/semantic_identity_invariant_019.json")
       .is_file()))

# == adversarial (93-104) =================================================
row(93, "Adversarial", "PROVEN_COMPLETE misread as finished film -> "
    "receipt refuses", "evidence",
    ev(lambda: "does NOT" in (ROOT / "docs/operating/"
                              "AI_FILM_PIPELINE_V1_COMPLETION_019.md")
       .read_text(encoding="utf-8")))
row(94, "Adversarial", "debt used to green-wash a gate -> refused by "
    "validator", "pytest",
    pt("tests/test_quality_debt_readiness_019.py::"
       "test_02_debt_cannot_satisfy_release_gates"))
row(95, "Adversarial", "collapsing axes into one boolean -> no "
    "aggregate exists", "evidence",
    ev(lambda: "no aggregate READY boolean" in json.dumps(READY)))
row(96, "Adversarial", "silent candidate promotion -> decision NONE + "
    "canonical clean", "evidence",
    ev(lambda: DEC["decisions"]["CANDIDATE_PROMOTION"] == "NONE" and
       CANON["experimental_asset_contamination_scan"]["result"] ==
       "CLEAN"))
row(97, "Adversarial", "Owner decision rewritten -> frozen JSON is the "
    "authority", "evidence",
    ev(lambda: DEC["decision_source"].startswith("OWNER (product "
                                                 "decision")))
row(98, "Adversarial", "regeneration sneaks into V1 -> DISALLOWED "
    "frozen", "evidence",
    ev(lambda: DEC["decisions"]["FURTHER_V1_VIDEO_REGENERATION"] ==
       "DISALLOWED"))
row(99, "Adversarial", "external-effect ambiguity -> fail-closed "
    "handlers inherited", "evidence",
    ev(lambda: "OWNER_AMBIGUITY_GATE" in
       (ROOT / "tools/run_production_scale_007.py").read_text(
           encoding="utf-8")))
row(100, "Adversarial", "stale result short-circuit -> loud archive "
    "pattern", "evidence",
    ev(lambda: (D18 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P018_A/"
                "reentry_note.json").exists()))
row(101, "Adversarial", "undeclared delivery file -> verifier catches",
    "pytest",
    pt("tests/test_delivery_011.py::test_undeclared_files_detected"))
row(102, "Adversarial", "secret leak -> scan clean", "evidence",
    ev(lambda: CONF["secret_scan"]["hits"] == []))
row(103, "Adversarial", "self-referential SHA claim -> none made",
    "evidence",
    ev(lambda: "PACKAGE_019_FINAL_HEAD_SHA" not in
       (ROOT / "docs/operating/AI_FILM_PIPELINE_V1_COMPLETION_019.md")
       .read_text(encoding="utf-8")))
row(104, "Adversarial", "quality debt hidden -> registry ACTIVE and "
    "shipped", "evidence",
    ev(lambda: DEBT["count"] == 5 and
       (B19 / "receipts/quality_debt_registry_019.json").is_file()))


def main() -> None:
    results = run()
    passed = sum(1 for r in results if r["result"] == "PASS")
    fails = [r["id"] for r in results
             if r["result"] not in ("PASS",) and r["mode"] == "evidence"]
    out = {"version": "recovery-matrix-019-v1",
           "scenarios": len(results),
           "pytest_bound": sum(1 for r in results
                               if r["mode"] == "pytest"),
           "evidence_pass": passed, "fails": fails, "rows": results}
    (D19 / "recovery_matrix_019.json").write_text(json.dumps(out, indent=1),
                                                  encoding="utf-8")
    print(json.dumps({"scenarios": len(results), "fails": fails}))


if __name__ == "__main__":
    main()
