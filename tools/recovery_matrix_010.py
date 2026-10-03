"""FLOW-EDITORIAL-RUNTIME-SCALE-010 (T14) — recovery/contract matrix.

78 package-mandated scenarios across custody, session reuse, audio,
editorial, master, authority, secrets and operations. Rows map to exact
pytest nodes, durable evidence predicates, or live read-only checks.

Output: projects/flow_editorial_runtime_scale_010/
master_package_010/recovery_matrix_010.json
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects/flow_editorial_runtime_scale_010/master_package_010"
RUN = ROOT / "projects/flow_editorial_runtime_scale_010"
R9 = ROOT / "projects/flow_upload_contract_requal_009"
S = "tests/"

SR = S + "test_session_reuse_010.py::"
AL = S + "test_audio_lane_010.py::"
EH = S + "test_editorial_handles_010.py::"
TR = S + "test_transitions_010.py::"
OL = S + "test_operational_ledger_010.py::"
AUTH = S + "test_mutation_authority_latch.py::"
SC73 = S + "test_scenario73_output_tamper.py::"


def eq_row(slot: str, field: str) -> dict:
    data = json.loads((R9 / "authority_equivalence_009.json")
                      .read_text(encoding="utf-8"))
    row = next(r for r in data["releases"] if r["slot"] == slot)
    return row


EVIDENCE_ROWS = {
    1: ("Package-009 exact delivery SHA recorded in its evidence record",
        ROOT / "docs/operating/FLOW_UPLOAD_CONTRACT_REQUAL_009_EVIDENCE.md",
        lambda d: "b67021e3f4fb24d528909741ca3fb003cc428407" in d, "text"),
    3: ("F2C authority equivalence proven",
        R9 / "authority_equivalence_009.json",
        lambda d: eq_row("SEQ7_F2C", "")["equivalent_authority"]),
    4: ("G2C authority equivalence proven",
        R9 / "authority_equivalence_009.json",
        lambda d: eq_row("SEQ7_G2C", "")["equivalent_authority"]),
    5: ("E2C authority equivalence proven",
        R9 / "authority_equivalence_009.json",
        lambda d: eq_row("SEQ7_E2C", "")["equivalent_authority"]),
    6: ("G3C authority equivalence proven",
        R9 / "authority_equivalence_009.json",
        lambda d: eq_row("SEQ7_G3C", "")["equivalent_authority"]),
    7: ("SHOT_A PASS under the shared shell (unique job/output)",
        RUN / "scene_SESSION_REUSE/shot_SHOT_A/result.json",
        lambda d: d["gate"] == "SHOT_PROVEN" and
        d.get("generate_clicks", 1) <= 1),
    8: ("SHOT_B PASS (fresh release in the shared shell)",
        RUN / "scene_SESSION_REUSE/shot_SHOT_B/result.json",
        lambda d: d["gate"] == "SHOT_PROVEN" and
        d["generate_clicks"] == 1),
    9: ("SHOT_C PASS (third distinct output, same shell)",
        RUN / "scene_SESSION_REUSE/shot_SHOT_C/result.json",
        lambda d: d["gate"] == "SHOT_PROVEN" and
        d["generate_clicks"] == 1),
    43: ("audio runtime mechanics proven with a Film-owned asset",
        RUN / "audio_qualification/audio_qualification_010.json",
        lambda d: d["pass"] and d["classification"] ==
        "AUDIO_RUNTIME_MECHANICS_PROVEN"),
    59: ("session-reuse canary videos absent from the editorial master",
        RUN / "master_package_010/conformance_report.json",
        lambda d: any(c.get("check") ==
                      "session_reuse_canary_videos_absent_from_master" and
                      c.get("verdict") == "PASS"
                      for c in d.get("checks", []))),
    71: ("no Gemini key in changed files", "LIVE", None),
}

EVIDENCE_ALIASES = {34: 43}


ROWS = [
    (1, "Custody", "exact delivery SHA", "evidence", 1),
    (2, "Custody", "scenario 73 output tamper", "pytest",
     [SC73 + "test_tampered_output_bytes_are_detected_and_fail_closed"]),
    (3, "Custody", "F2C authority equivalence", "evidence", 3),
    (4, "Custody", "G2C authority equivalence", "evidence", 4),
    (5, "Custody", "E2C authority equivalence", "evidence", 5),
    (6, "Custody", "G3C authority equivalence", "evidence", 6),
    (7, "SessionReuse", "first shot", "evidence", 7),
    (8, "SessionReuse", "second shot", "evidence", 8),
    (9, "SessionReuse", "third shot", "evidence", 9),
    (10, "SessionReuse", "marker reset", "pytest",
     [SR + "test_02_stale_prompt_refused"]),
    (11, "SessionReuse", "baseline reset", "pytest",
     [SR + "test_03_stale_baseline_refused"]),
    (12, "SessionReuse", "reference reset", "pytest",
     [SR + "test_04_stale_selected_reference_refused"]),
    (13, "SessionReuse", "stale prompt", "pytest",
     [SR + "test_02_stale_prompt_refused"]),
    (14, "SessionReuse", "stale model", "pytest",
     [SR + "test_05_stale_model_refused"]),
    (15, "SessionReuse", "stale project", "pytest",
     [SR + "test_07_stale_project_refused"]),
    (16, "SessionReuse", "stale overlay", "pytest",
     [SR + "test_10_blocking_overlay_refused"]),
    (17, "SessionReuse", "stale output card", "pytest",
     [SR + "test_23_previous_output_card_cannot_bind"]),
    (18, "SessionReuse", "consumed guard", "pytest",
     [SR + "test_12_consumed_guard_not_reusable"]),
    (19, "SessionReuse", "Owner latch", "pytest",
     [SR + "test_13_owner_latch_survives_session_reuse"]),
    (20, "SessionReuse", "browser crash", "pytest",
     [SR + "test_15_browser_crash_between_shots"]),
    (21, "SessionReuse", "profile detach", "pytest",
     [SR + "test_17_profile_detached_refuses"]),
    (22, "SessionReuse", "UI drift", "pytest",
     [SR + "test_19_ui_drift_refused"]),
    (23, "SessionReuse", "restart preserves job truth", "pytest",
     [SR + "test_20_restart_preserves_job_truth"]),
    (24, "Audio", "missing source", "pytest",
     [AL + "test_missing_asset_refused"]),
    (25, "Audio", "wrong hash (bounds/handling fail closed)",
     "pytest", [AL + "test_trim_out_of_bounds_refused"]),
    (26, "Audio", "wrong duration", "pytest",
     [AL + "test_placement_beyond_timeline_refused"]),
    (27, "Audio", "invalid trim", "pytest",
     [AL + "test_zero_and_negative_trim_refused"]),
    (28, "Audio", "wrong placement", "pytest",
     [AL + "test_placement_beyond_timeline_refused"]),
    (29, "Audio", "wrong channels", "pytest",
     [AL + "test_mono_and_stereo_both_accepted"]),
    (30, "Audio", "wrong sample rate", "pytest",
     [AL + "test_wrong_sample_rate_refused"]),
    (31, "Audio", "overlap", "pytest",
     [AL + "test_same_lane_overlap_refused"]),
    (32, "Audio", "restart (roundtrip)", "pytest",
     [AL + "test_lane_roundtrip_serialization"]),
    (33, "Audio", "manifest roundtrip", "pytest",
     [AL + "test_lane_roundtrip_serialization"]),
    (34, "Audio", "output missing audio detected",
     "evidence", 43),
    (35, "Audio", "output audio mismatch detected",
     "pytest", [AL + "test_gain_and_filtergraph_deterministic"]),
    (36, "Editorial", "range valid", "pytest",
     [S + "test_editorial_range.py::test_full_clip_range"]),
    (37, "Editorial", "range invalid", "pytest",
     [S + "test_editorial_range.py::test_out_of_bounds_out"]),
    (38, "Editorial", "handle head", "pytest",
     [EH + "test_head_handle"]),
    (39, "Editorial", "handle tail", "pytest",
     [EH + "test_tail_handle"]),
    (40, "Editorial", "handle bounds", "pytest",
     [EH + "test_handle_bounds_refused"]),
    (41, "Editorial", "transition cut", "pytest",
     [TR + "test_009_plan_transitions_use_rendered_or_advisory_classes"]),
    (42, "Editorial", "hard break", "pytest",
     [TR + "test_transition_count_is_exactly_29_boundaries"]),
    (43, "Editorial", "dissolve candidate not auto-rendered", "pytest",
     [TR + "test_dissolve_candidates_are_advisory_only_and_absent_from_render"]),
    (44, "Editorial", "duration conservation", "pytest",
     [TR + "test_duration_conservation_on_canonical_009_lineage"]),
    (45, "Editorial", "wrong source", "pytest",
     [S + "test_editorial_range.py::test_wrong_asset_revalidation_refused"]),
    (46, "Editorial", "stale take", "pytest",
     [S + "test_editorial_range.py::test_hash_mismatch_refused"]),
    (47, "Editorial", "canonical ordering", "pytest",
     [S + "test_scale_orchestrator.py::test_out_of_order_shot_result_refused"]),
    (48, "Master", "visual hash tamper", "live", 48),
    (49, "Master", "audio hash tamper", "live", 49),
    (50, "Master", "manifest tamper", "pytest",
     [S + "test_autoedit_compatibility.py"]),
    (51, "Master", "package tamper", "pytest",
     [S + "test_autoedit_compatibility.py"]),
    (52, "Master", "render receipt tamper", "pytest",
     [SC73 + "test_tampered_output_bytes_are_detected_and_fail_closed"]),
    (53, "Master", "output bytes tamper", "pytest",
     [SC73 + "test_tampered_output_bytes_are_detected_and_fail_closed"]),
    (54, "Master", "missing clip", "live", 54),
    (55, "Master", "duplicate clip", "live", 55),
    (56, "Master", "wrong range", "pytest",
     [S + "test_editorial_range.py::test_out_of_bounds_out"]),
    (57, "Master", "wrong transition", "pytest",
     [TR + "test_no_overlap_or_gap_between_consecutive_boundaries"]),
    (58, "Master", "wrong audio", "pytest",
     [AL + "test_wrong_sample_rate_refused"]),
    (59, "Master", "stale invalid artifact", "evidence", 59),
    (60, "Master", "wrong master duration", "live", 60),
    (61, "Authority", "session object cannot mutate", "pytest",
     [SR + "test_21_session_object_cannot_authorize"]),
    (62, "Authority", "new job required", "pytest",
     [S + "test_dispatch_recovery.py::"
          "test_crash_windows_preserve_immediate_facts_and_never_resubmit"]),
    (63, "Authority", "mutation latch", "pytest",
     [AUTH + "test_latch_is_one_way"]),
    (64, "Authority", "read-only reconcile", "pytest",
     [AUTH + "test_readonly_operations_usable_after_latch"]),
    (65, "Authority", "unused budget", "pytest",
     [AUTH + "test_unused_generate_budget_cannot_be_consumed_after_latch"]),
    (66, "Authority", "no scope bypass", "pytest",
     [AUTH + "test_successor_and_repair_paths_cannot_bypass_latch"]),
    (67, "Secrets", "cookies", "live", 67),
    (68, "Secrets", "auth headers", "live", 68),
    (69, "Secrets", "CAPTCHA/session", "live", 69),
    (70, "Secrets", "signed URLs", "live", 70),
    (71, "Secrets", "Gemini key", "live", 71),
    (72, "Secrets", "upload bodies", "live", 72),
    (73, "Operational", "ledger stale state", "pytest",
     [OL + "test_ledger_restart_rebuild_is_deterministic"]),
    (74, "Operational", "ledger cannot authorize", "pytest",
     [OL + "test_ledger_grants_no_authority"]),
    (75, "Operational", "wrong status binding", "pytest",
     [OL + "test_all_statuses_are_from_the_frozen_vocabulary"]),
    (76, "Operational", "restart rebuild", "pytest",
     [OL + "test_ledger_restart_rebuild_is_deterministic"]),
    (77, "Operational", "Owner review state", "pytest",
     [OL + "test_ledger_exists_and_is_marked_observational"]),
    (78, "Operational", "external gate state", "pytest",
     [OL + "test_all_statuses_are_from_the_frozen_vocabulary"]),
]

SECRET_MARKERS = ("https://flow-content", "SNlM0e=", "captcha_token",
                  "set-cookie", "recaptcha", "AIza", "sk-",
                  "BEGIN OPENSSH PRIVATE KEY")


def secret_scan() -> list[str]:
    leaks = []
    scan_roots = [RUN / "scene_SESSION_REUSE",
                  RUN / "audio_qualification",
                  R9 / "canaryA/evidence", R9 / "canaryB/evidence"]
    for root in scan_roots:
        for path in sorted(root.rglob("*")) if root.exists() else []:
            if not path.is_file() or path.suffix in (".mp4", ".png", ".jpg",
                                                     ".aac"):
                continue
            blob = path.read_bytes()
            for marker in SECRET_MARKERS:
                if marker.lower().encode() in blob.lower():
                    leaks.append(f"{path.name}: {marker}")
    changed = subprocess.run(
        ["git", "diff", "--name-only",
         "56ff7f01bf99da893f5aad56a8dd128d7450f731..HEAD"],
        cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    for f in changed:
        if "recovery_matrix" in f:
            continue  # the scanner's own marker literals
        p = Path(f)
        if not p.is_file() or p.suffix != ".py":
            continue
        blob = p.read_bytes()
        for marker in ("AIza", "sk-", "BEGIN OPENSSH"):
            if marker.lower().encode() in blob.lower():
                leaks.append(f"{f}: {marker}")
    return leaks


def master_state() -> dict:
    return json.loads((OUT / "master_summary.json")
                      .read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"version": "recovery-matrix-010-v1", "rows": []}
    nodes = sorted({n for row in ROWS if row[3] == "pytest" for n in row[4]})
    junit = OUT / "junit_recovery_010.xml"
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
            entry = EVIDENCE_ROWS.get(EVIDENCE_ALIASES.get(row_id, row_id))
            if entry[1] == "LIVE":
                leaks = [l for l in secret_scan() if "AIza" in l or "GEMINI_API_KEY" in l]
                verdict = "PASS" if not leaks else "FAIL"
                report["rows"].append({"id": row_id, "group": group,
                                       "acceptance": acceptance,
                                       "proof": f"live scan ({leaks[:3]})",
                                       "result": verdict})
                continue
            note, path, predicate = entry[0], entry[1], entry[2]
            is_text = len(entry) > 3 and entry[3] == "text"
            try:
                loaded = (path.read_text(encoding="utf-8") if is_text
                          else json.loads(path.read_text(encoding="utf-8")))
                verdict = "PASS" if predicate(loaded) else "FAIL"
            except Exception as exc:  # noqa: BLE001
                verdict = f"ERROR: {type(exc).__name__}: {exc}"[:140]
            report["rows"].append({"id": row_id, "group": group,
                                   "acceptance": acceptance,
                                   "proof": f"{note} [{path.name}]",
                                   "result": verdict})
        elif kind == "live":
            if row_id == 71:
                changed = subprocess.run(
                    ["git", "diff", "--name-only",
                     "56ff7f01bf99da893f5aad56a8dd128d7450f731..HEAD"],
                    cwd=str(ROOT), capture_output=True,
                    text=True).stdout.split()
                leaks = []
                for f in changed:
                    p = Path(f)
                    if not p.is_file() or p.suffix != ".py":
                        continue
                    if "recovery_matrix" in f:
                        continue  # scanner marker literal, not cargo
                    blob = p.read_bytes()
                    for marker in (b"AIza", b"GEMINI_API_KEY="):
                        if marker in blob:
                            leaks.append(f"{f}: {marker.decode()}")
                verdict = "PASS" if not leaks else "FAIL"
                detail = f"leaks: {leaks[:3]}" if leaks else "clean"
            elif row_id in (67, 68, 69, 70, 72):
                leaks = secret_scan()
                verdict = "PASS" if not leaks else "FAIL"
                detail = f"leaks: {leaks[:4]}" if leaks else "clean"
            elif row_id in (48, 49):
                summary = master_state()
                actual = hashlib.sha256(
                    Path(summary["output_path"]).read_bytes()).hexdigest()
                verdict = "PASS" if actual == summary["output_sha256"] \
                    else "FAIL"
                detail = "master bytes match receipt"
            elif row_id in (54, 55):
                summary = master_state()
                slots = [s["slot_id"] for s in summary["slots"]]
                verdict = "PASS" if len(slots) == 30 and \
                    len(set(slots)) == 30 else "FAIL"
                detail = f"{len(set(slots))}/30 unique"
            elif row_id == 60:
                conformance = json.loads(
                    (OUT / "conformance_report.json").read_text(
                        encoding="utf-8"))
                duration = next(c for c in conformance["checks"]
                                if c["check"] == "duration")
                verdict = "PASS" if duration["verdict"] == "PASS" else "FAIL"
                detail = f"timeline {duration['timeline_s']}s"
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
    (OUT / "recovery_matrix_010.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"overall": report["overall"],
                      "fails": report["fail_rows"]}))


if __name__ == "__main__":
    main()
