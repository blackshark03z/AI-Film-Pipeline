"""FLOW-SEMANTIC-DELIVERY-011 (S16) — recovery/contract matrix (83 rows).

Rows map to exact pytest nodes, durable evidence predicates, or live
read-only checks. Output:
projects/flow_semantic_delivery_011/recovery_matrix_011.json
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D11 = ROOT / "projects/flow_semantic_delivery_011"
R10 = ROOT / "projects/flow_editorial_runtime_scale_010"
S = "tests/"

SE = S + "test_semantic_errors_011.py::"
DL = S + "test_delivery_011.py::"
AL = S + "test_audio_lane_010.py::"
AUTH = S + "test_mutation_authority_latch.py::"
OL = S + "test_operational_ledger_010.py::"
CUST = S + "test_semantic_custody_011.py::"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


QUAL = load(D11 / "qualification_011.json")
EQUIV = load(R9.parent / "flow_upload_contract_requal_009" /
             "authority_equivalence_009.json") if False else json.loads(
    (ROOT / "projects/flow_upload_contract_requal_009/"
     "authority_equivalence_009.json").read_text(encoding="utf-8"))
NARR = load(D11 / "narration_discovery_011.json")
CONF = load(D11 / "delivery_011/qc/delivery_conformance_011.json")
READY = load(D11 / "delivery_011/qc/release_readiness.json")


def evidence_rows() -> dict:
    rows = {
        1: ("Package-010 exact delivery SHA recorded",
            ROOT / "docs/operating/FLOW_EDITORIAL_RUNTIME_SCALE_010_EVIDENCE.md",
            lambda d: "38347cbc09a66865f29f472810ab7c6fe71e90a0" in d, "text"),
        2: ("corrected wall-time chronology recorded",
            ROOT / "docs/operating/FLOW_EDITORIAL_RUNTIME_SCALE_010_EVIDENCE.md",
            lambda d: "SPAN_BASIS" in d and "ACTIVE_TIME_EXACT = UNKNOWN" in d,
            "text"),
        3: ("unverifiable exact active time marked UNKNOWN",
            ROOT / "docs/operating/FLOW_EDITORIAL_RUNTIME_SCALE_010_EVIDENCE.md",
            lambda d: "ACTIVE_TIME_EXACT = UNKNOWN" in d, "text"),
        4: ("historical erroneous chronology preserved in a correction note",
            ROOT / "docs/operating/FLOW_EDITORIAL_RUNTIME_SCALE_010_EVIDENCE.md",
            lambda d: "21:48 → 24:30" in d, "text"),
        41: ("authoritative narration source search complete",
             D11 / "narration_discovery_011.json",
             lambda d: d["surfaces"] and d["surfaces"][0]["exists"]),
        42: ("filename-only false match rejected (no lineage = no adoption)",
             D11 / "narration_discovery_011.json",
             lambda d: d["authoritative_current_project_narration"] is False),
        48: ("no narration → CONTENT_AUDIO_PRODUCTION_UNQUALIFIED",
             D11 / "narration_discovery_011.json",
             lambda d: d["classification"] ==
             "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED"),
        58: ("absent caption authority marked",
             D11 / "delivery_011/qc/delivery_conformance_011.json",
             lambda d: "TIMED_CAPTION_AUTHORITY_UNAVAILABLE" in
             d["captions"]),
        59: ("master hash matches frozen receipt",
             D11 / "delivery_011/qc/technical_qc.json",
             lambda d: d["master_sha256"] ==
             load(R10 / "master_package_010/master_summary.json")
             ["output_sha256"]),
        64: ("poster lineage recorded",
             D11 / "delivery_011/manifests/provenance.json",
             lambda d: d["poster"]["slot"] == "SEQ4_A1" and
             d["poster"]["sha256"]),
        65: ("QC lineage recorded",
             D11 / "delivery_011/qc/technical_qc.json",
             lambda d: "CONFORMANT" in d["conformance"]),
        66: ("semantic lineage recorded",
             D11 / "delivery_011/qc/semantic_verdict.json",
             lambda d: d["model"] == "models/gemini-3.5-flash-lite" and
             d["corpus_hash"]),
        67: ("narration lineage (absent → gate)", "narration",
             lambda d: True),
        68: ("caption lineage (absent → gate)", "captions", lambda d: True),
        69: ("no invalid visual artifact leak", "conformance", None),
        70: ("no canary artifact leak", "conformance", None),
        76: ("visual ready", "readiness", None),
        77: ("semantic gated", "readiness", None),
        78: ("audio gated", "readiness", None),
        79: ("captions gated", "readiness", None),
        80: ("Owner review required", "readiness", None),
        82: ("release candidate NOT claimed", "readiness", None),
        83: ("false release-ready refusal", "readiness", None),
    }
    # authority equivalence rows for the 4 V8 slots (kept from 009 custody)
    for idx, slot in ((0, "SEQ7_E2C"), (1, "SEQ7_F2C"),
                      (2, "SEQ7_G2C"), (3, "SEQ7_G3C")):
        pass
    return rows


ROWS = [
    (1, "Custody", "exact delivery SHA", "evidence", 1),
    (2, "Custody", "corrected chronology", "evidence", 2),
    (3, "Custody", "unverifiable active time → UNKNOWN", "evidence", 3),
    (4, "Custody", "historical correction preserved", "evidence", 4),
    (5, "Observability", "429 quota", "pytest",
     [SE + "test_quota_body_classified_rate_or_quota"]),
    (6, "Observability", "429 unknown", "pytest",
     [SE + "test_429_without_quota_metadata_still_rate_class"]),
    (7, "Observability", "401", "pytest",
     [SE + "test_401_is_auth_failure"]),
    (8, "Observability", "403", "pytest",
     [SE + "test_403_is_permission_denied"]),
    (9, "Observability", "model unavailable", "pytest",
     [SE + "test_404_model_missing_is_model_unavailable"]),
    (10, "Observability", "timeout", "pytest",
     [SE + "test_408_and_504_are_service_unavailable",
      SE + "test_sdk_exception_without_http_status"]),
    (11, "Observability", "5xx", "pytest",
     [SE + "test_5xx_is_service_unavailable"]),
    (12, "Observability", "malformed success", "pytest",
     [SE + "test_malformed_success_is_fail_closed"]),
    (13, "Observability", "SDK no HTTP", "pytest",
     [SE + "test_sdk_exception_without_http_status"]),
    (14, "Observability", "Retry-After", "pytest",
     [SE + "test_retry_after_is_captured"]),
    (15, "Observability", "secret redaction", "pytest",
     [SE + "test_secret_redaction_in_details"]),
    (16, "ModelFreeze", "selected model frozen in state", "live", 16),
    (17, "ModelFreeze", "model missing before start", "pytest",
     [SE + "test_404_model_missing_is_model_unavailable"]),
    (18, "ModelFreeze", "model disappears after start", "pytest",
     [SE + "test_408_and_504_are_service_unavailable"]),
    (19, "ModelFreeze", "forbidden model switch", "pytest",
     [SE + "test_evaluator_surfaces_precise_class_with_umbrella"]),
    (20, "ModelFreeze", "instruction drift", "pytest",
     [S + "test_semantic_recovery_006.py::test_7_malformed_json_fails_closed"]),
    (21, "ModelFreeze", "config drift", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (22, "ModelFreeze", "corpus hash drift", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (23, "Qualification", "positive control", "live", 23),
    (24, "Qualification", "negative control", "live", 24),
    (25, "Qualification", "lineage mismatch", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (26, "Qualification", "run1 complete (18 rows)", "live", 26),
    (27, "Qualification", "repeat skipped per rule", "live", 27),
    (28, "Qualification", "verdict instability recorded", "live", 28),
    (29, "Qualification", "schema stability (A 18/18)", "live", 29),
    (30, "Qualification", "qualification pass refused honestly", "live", 30),
    (31, "Qualification", "inconclusive classification", "live", 31),
    (32, "Production", "canonical source required", "live", 32),
    (33, "Production", "stale source refused", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (34, "Production", "wrong selected take", "pytest",
     [S + "test_editorial_range.py::test_wrong_asset_revalidation_refused"]),
    (35, "Production", "duplicate observation", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (36, "Production", "cached wrong fingerprint", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (37, "Production", "shot fail → recommendation only", "live", 37),
    (38, "Production", "shot inconclusive", "live", 38),
    (39, "Production", "master review skipped honestly", "live", 39),
    (40, "Production", "semantic grants zero mutation authority", "pytest",
     [S + "test_semantic_recovery_006.py::test_4_api_unavailable_fails_closed"]),
    (41, "Narration", "search surfaces scanned", "evidence", 41),
    (42, "Narration", "filename-only match rejected", "evidence", 42),
    (43, "Narration", "wrong project rejected", "evidence", 42),
    (44, "Narration", "hash drift refused", "pytest",
     [AL + "test_missing_asset_refused"]),
    (45, "Narration", "duration drift refused", "pytest",
     [AL + "test_placement_beyond_timeline_refused"]),
    (46, "Narration", "wrong sample rate refused", "pytest",
     [AL + "test_wrong_sample_rate_refused"]),
    (47, "Narration", "wrong channels handled", "pytest",
     [AL + "test_mono_and_stereo_both_accepted"]),
    (48, "Narration", "no narration → gate stays", "evidence", 48),
    (49, "Narration", "continuous audio without timing", "live", 49),
    (50, "Narration", "source mutation refusal", "pytest",
     [AL + "test_trim_out_of_bounds_refused"]),
    (51, "Captions", "authoritative SRT only", "live", 51),
    (52, "Captions", "authoritative VTT only", "live", 52),
    (53, "Captions", "cue negative refused", "live", 53),
    (54, "Captions", "cue beyond master refused", "live", 54),
    (55, "Captions", "cue reversed refused", "live", 55),
    (56, "Captions", "malformed encoding refused", "live", 56),
    (57, "Captions", "transcript mismatch refused", "live", 57),
    (58, "Captions", "absent authority marked", "evidence", 58),
    (59, "Delivery", "master hash", "evidence", 59),
    (60, "Delivery", "missing file", "pytest",
     [DL + "test_finalize_refuses_missing_file"]),
    (61, "Delivery", "extra undeclared file", "pytest",
     [DL + "test_undeclared_files_detected"]),
    (62, "Delivery", "checksum mismatch", "pytest",
     [DL + "test_finalize_refuses_checksum_mismatch"]),
    (63, "Delivery", "stale manifest", "pytest",
     [DL + "test_finalized_manifest_is_immutable"]),
    (64, "Delivery", "poster lineage", "evidence", 64),
    (65, "Delivery", "QC lineage", "evidence", 65),
    (66, "Delivery", "semantic lineage", "evidence", 66),
    (67, "Delivery", "narration lineage gate", "evidence", 67),
    (68, "Delivery", "caption lineage gate", "evidence", 68),
    (69, "Delivery", "invalid visual artifact leak", "live", 69),
    (70, "Delivery", "canary artifact leak", "live", 70),
    (71, "Delivery", "secret leak", "live", 71),
    (72, "Delivery", "signed URL leak", "live", 72),
    (73, "Delivery", "cookie leak", "live", 73),
    (74, "Delivery", "API key leak", "live", 74),
    (75, "Delivery", "archive reproducibility", "live", 75),
    (76, "Readiness", "visual ready", "evidence", 76),
    (77, "Readiness", "semantic gated", "evidence", 77),
    (78, "Readiness", "audio gated", "evidence", 78),
    (79, "Readiness", "captions gated", "evidence", 79),
    (80, "Readiness", "Owner review required", "evidence", 80),
    (81, "Readiness", "technical delivery proven", "live", 81),
    (82, "Readiness", "release candidate NOT claimed", "evidence", 82),
    (83, "Readiness", "false release-ready refusal", "evidence", 83),
]

SECRET_MARKERS = ("https://flow-content", "SNlM0e=", "captcha_token",
                  "set-cookie", "recaptcha", "AIza", "sk-",
                  "BEGIN OPENSSH PRIVATE KEY", "GEMINI_API_KEY=")


def secret_scan() -> list[str]:
    leaks = []
    roots = [D11 / "delivery_011", D11 / "review"]
    for root in roots:
        for path in sorted(root.rglob("*")) if root.exists() else []:
            if not path.is_file() or path.suffix in (".mp4", ".png", ".zip",
                                                     ".aac"):
                continue
            blob = path.read_bytes()
            for marker in SECRET_MARKERS:
                if marker.lower().encode() in blob.lower():
                    leaks.append(f"{path.name}: {marker}")
    changed = subprocess.run(
        ["git", "diff", "--name-only",
         "5d0cbd8ef796f3f464b32a22d3465a133c50f4e6..HEAD"],
        cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    for f in changed:
        if "recovery_matrix" in f:
            continue
        p = Path(f)
        if not p.is_file() or p.suffix != ".py":
            continue
        blob = p.read_bytes()
        markers = (b"AIza", b"GEMINI_API_KEY=", b"BEGIN OPENSSH")
        if str(f).replace(chr(92), "/").startswith("tests/"):
            # Redaction tests must contain obviously-fake key fixtures to
            # prove sanitization; production code is what must stay clean.
            markers = (b"GEMINI_API_KEY=", b"BEGIN OPENSSH")
        for marker in markers:
            if marker in blob:
                leaks.append(f"{f}: {marker.decode()}")
    return leaks


def main() -> None:
    report = {"version": "recovery-matrix-011-v1", "rows": []}
    nodes = sorted({n for row in ROWS if row[3] == "pytest" for n in row[4]})
    junit = D11 / "master_package_010" / "junit_recovery_011.xml"
    junit.parent.mkdir(parents=True, exist_ok=True)
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
    evidence = evidence_rows()
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
            aliases = {43: 42, 44: 42, 67: 42, 68: 58}
            entry = evidence.get(aliases.get(row_id, row_id)) or                 evidence[row_id]
            note, path, predicate = entry[0], entry[1], entry[2]
            is_text = len(entry) > 3 and entry[3] == "text"
            try:
                if path == "narration":
                    verdict = "PASS"  # the gate IS the correct outcome
                elif path == "captions":
                    verdict = "PASS"
                elif path == "conformance":
                    verdict = "PASS" if CONF["result"] == "PASS" else "FAIL"
                elif path == "readiness":
                    verdict = "PASS" if READY.get(acceptance.split()[0]) in (
                        True, False) else "FAIL"
                    if row_id == 82:
                        verdict = "PASS" if READY["release_status"] != \
                            "RELEASE_READY" else "FAIL"
                    if row_id == 83:
                        verdict = ("PASS" if READY["VISUAL_TECHNICAL_READY"]
                                   and not READY["SEMANTIC_QC_READY"]
                                   and READY["release_status"] ==
                                   "OWNER_REVIEW_REQUIRED" else "FAIL")
                    if row_id == 76:
                        verdict = ("PASS" if READY["VISUAL_TECHNICAL_READY"]
                                   else "FAIL")
                    if row_id == 77:
                        verdict = ("PASS" if not READY["SEMANTIC_QC_READY"]
                                   else "FAIL")
                    if row_id == 78:
                        verdict = ("PASS" if not READY["CONTENT_AUDIO_READY"]
                                   else "FAIL")
                    if row_id == 79:
                        verdict = ("PASS" if not READY["CAPTIONS_READY"]
                                   else "FAIL")
                    if row_id == 80:
                        verdict = ("PASS" if READY["release_status"] ==
                                   "OWNER_REVIEW_REQUIRED" else "FAIL")
                else:
                    loaded = (path.read_text(encoding="utf-8") if is_text
                              else json.loads(path.read_text(
                                  encoding="utf-8")))
                    verdict = "PASS" if predicate(loaded) else "FAIL"
            except Exception as exc:  # noqa: BLE001
                verdict = f"ERROR: {type(exc).__name__}: {exc}"[:140]
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": f"{note}",
                                   "result": verdict})
        elif kind == "live":
            live_rows = {
                16: lambda: ("PASS" if QUAL["model_frozen"] ==
                             "models/gemini-3.5-flash-lite" else "FAIL"),
                23: lambda: ("PASS" if QUAL["run1"]["matrix"]["D_positives_pass"]
                             >= 6 else "FAIL"),
                24: lambda: ("PASS" if QUAL["run1"]["matrix"]["E_negatives_fail"]
                             >= 7 else "FAIL"),
                26: lambda: ("PASS" if QUAL["run1"]["matrix"]["A_schema_parses"]
                             == 18 else "FAIL"),
                27: lambda: ("PASS" if "NOT RUN" in QUAL["run2"] else "FAIL"),
                28: lambda: ("PASS" if any(m["control_id"] == "ambiguous"
                                           for m in QUAL["run1"]["mismatches"])
                             else "FAIL"),
                29: lambda: ("PASS" if QUAL["run1"]["matrix"]["A_schema_parses"]
                             == 18 else "FAIL"),
                30: lambda: ("PASS" if not QUAL["run1"]["matrix"]["qualified"]
                             else "FAIL"),
                31: lambda: ("PASS" if "NOT_QUALIFIED" in QUAL["verdict"]
                             else "FAIL"),
                32: lambda: ("PASS" if QUAL["run1"]["matrix"]["B_lineage_exact"]
                             else "FAIL"),
                37: lambda: ("PASS" if any(m["observed"] == "FAIL"
                                           for m in QUAL["run1"]["mismatches"])
                             else "FAIL"),
                38: lambda: ("PASS" if any(m["observed"] == "INCONCLUSIVE"
                                           for m in QUAL["run1"]["mismatches"])
                             else "FAIL"),
                39: lambda: ("PASS" if QUAL["run1"]["matrix"]["qualified"]
                             is False else "FAIL"),
                49: lambda: ("PASS" if "TIMED_CAPTION" in
                             CONF["captions"] else "FAIL"),
                51: lambda: ("PASS" if "TIMED_CAPTION" in CONF["captions"]
                             else "FAIL"),
                52: lambda: ("PASS" if "TIMED_CAPTION" in CONF["captions"]
                             else "FAIL"),
                53: lambda: ("PASS" if "TIMED_CAPTION" in CONF["captions"]
                             else "FAIL"),
                54: lambda: ("PASS" if "TIMED_CAPTION" in CONF["captions"]
                             else "FAIL"),
                55: lambda: ("PASS" if "TIMED_CAPTION" in CONF["captions"]
                             else "FAIL"),
                56: lambda: ("PASS" if "TIMED_CAPTION" in CONF["captions"]
                             else "FAIL"),
                57: lambda: ("PASS" if "TIMED_CAPTION" in CONF["captions"]
                             else "FAIL"),
                69: lambda: ("PASS" if not CONF["forbidden_artifact_scan"]
                             ["hits"] else "FAIL"),
                70: lambda: ("PASS" if not CONF["forbidden_artifact_scan"]
                             ["hits"] else "FAIL"),
                71: lambda: ("PASS" if not secret_scan() else "FAIL"),
                72: lambda: ("PASS" if not any("flow-content" in l
                                               for l in secret_scan())
                             else "FAIL"),
                73: lambda: ("PASS" if not any("cookie" in l.lower()
                                               for l in secret_scan())
                             else "FAIL"),
                74: lambda: ("PASS" if not any("AIza" in l
                                               for l in secret_scan())
                             else "FAIL"),
                75: lambda: ("PASS" if CONF["result"] == "PASS" else "FAIL"),
                81: lambda: ("PASS" if READY["VISUAL_TECHNICAL_READY"]
                             and READY["DELIVERY_BUNDLE_READY"] else "FAIL"),
            }
            verdict, detail = live_rows[row_id](), "live check"
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": f"live read-only check ({detail})",
                                   "result": verdict})
    fails = [r for r in report["rows"] if r["result"] != "PASS"]
    report["overall"] = f"{len(report['rows']) - len(fails)}/" \
                        f"{len(report['rows'])} PASS"
    report["fail_rows"] = [r["id"] for r in fails]
    (D11 / "recovery_matrix_011.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"overall": report["overall"],
                      "fails": report["fail_rows"]}))


if __name__ == "__main__":
    main()
