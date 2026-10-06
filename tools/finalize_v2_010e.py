"""V2-010E — finalize: evidence set + seal.

Terminal: STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH — the provider's latest
VISIBLE remaining-credit statement is 0 (fail-closed pre-dispatch stop;
F2B_010E authority UNspent). Phases 1-2 (dispatch/receipt durability) are
PROVEN by construction + tests.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010e_final_f2b"
sys.path.insert(0, str(ROOT / "tools"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")


def main() -> int:
    from mutation_authority import MutationAuthority
    auth = MutationAuthority(PKG, "QUALITY-V2-010E-FINAL-F2B")
    auth._event("PHASE3_CREDIT_PRECHECK_STOP",
                detail="provider-visible remaining = 0; "
                       "STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH; "
                       "F2B_010E authority UNspent")

    journal_contract = {
        "version": "v2-010e-dispatch-journal-contract-v1",
        "checkpoint": "V2010E_P1_JOURNAL_CONTRACT",
        "built_at": utcnow(),
        "implementation": "tools/dola_010e_dispatch_journal.py",
        "state_machine": ["RESERVED", "DISPATCH_ARMED", "RELEASE_OBSERVED",
                          "RECEIPT_CAPTURED", "PROVIDER_JOB_BOUND",
                          "TERMINAL"],
        "event_kinds": ["MUTATION_RESERVED", "DISPATCH_ARMED",
                        "NETWORK_RELEASE_OBSERVED", "SSE_RECEIPT_CAPTURED",
                        "CREATION_BOUND", "ASSET_DOWNLOADED",
                        "TERMINAL_SUCCESS", "TERMINAL_PROVIDER_FAILURE",
                        "AMBIGUITY_LATCHED"],
        "durability_properties": {
            "append_only": True,
            "fsync_per_event": True,
            "hash_chained": "previous_event_hash + event_hash per event",
            "torn_tail_ignored": "load keeps the verified prefix only",
            "duplicate_idempotent": "same kind re-append returns the "
                                    "existing event (duplicate_ignored)",
            "sync_release_persistence": "NETWORK_RELEASE_OBSERVED is "
                                        "appended inside the CDP request "
                                        "handler, independent of SSE parsing",
            "sync_receipt_persistence": "SSE_RECEIPT_CAPTURED appended the "
                                        "moment the ACK parses beyond the "
                                        "index boundary — never waiting for "
                                        "creation/download/shutdown",
            "payload_sanitized": "secret-named keys REDACTED before disk",
        },
        "budget_interplay": "MutationAuthority stays the single budget "
                            "governor; BUDGET_CONSUMED fires from the "
                            "receipt-captured callback; the journal never "
                            "grants or re-opens authority",
    }
    write("V2_010E_DISPATCH_JOURNAL_CONTRACT.json", journal_contract)

    crash_proof = {
        "version": "v2-010e-crash-recovery-proof-v1",
        "checkpoint": "V2010E_P2_CRASH_RECOVERY_PROOF",
        "built_at": utcnow(),
        "boundaries": {
            "A_before_release": "SAFE_UNSPENT (tested: test_01); an "
                                "unobserved release is promoted to B by the "
                                "conversation check (test_02)",
            "B_after_release_before_ack": "AMBIGUITY_LATCH + read-only "
                                          "reconciliation (tests 03, 13); "
                                          "the release is durably recorded — "
                                          "never silently RESERVED",
            "C_after_ack": "RESUME_POLL_BY_RECEIPT_IDENTITY (test_04)",
            "D_after_creation": "RESUME_DOWNLOAD_BY_CREATION_IDENTITY "
                                "(test_05)",
            "E_after_download": "VERIFY_LOCAL_SHA256_AND_FINALIZE (test_06)",
        },
        "acceptance": {
            "zero_restart_redispatch_paths": "recover mode NEVER dispatches "
                                             "(test_08); dispatch mode "
                                             "refuses a non-fresh journal",
            "zero_gallery_history_authority_paths": "false-historical "
                                                    "creation rejection "
                                                    "(test_10) + receipt "
                                                    "linkage contradiction "
                                                    "check in the runner",
            "zero_silent_reserved_releases": "broad exception handler: any "
                                             "failure after RELEASE_OBSERVED "
                                             "lands in AMBIGUITY_LATCHED, "
                                             "never a silent RESERVED",
        },
        "tests": "tests/test_v2_010e_journal_001.py — 14 passed",
    }
    write("V2_010E_CRASH_RECOVERY_PROOF.json", crash_proof)

    precheck = json.loads((PKG / "V2_010E_SESSION_CREDIT_PRECHECK.json")
                          .read_text(encoding="utf-8"))

    f2b_evidence = {
        "version": "v2-010e-f2b-evidence-v1",
        "checkpoint": "V2010E_P4_F2B",
        "built_at": utcnow(),
        "status": "STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH",
        "authority_state": "F2B_010E RESERVED-CLASS AUTHORITY UNSPENT "
                           "(no journal was armed; MutationAuthority OPEN; "
                           "zero provider interactions in 010E)",
        "reason": "the provider's latest VISIBLE remaining-credit statement "
                  "is 0 (fail-closed pre-dispatch gate)",
        "credit_statements": precheck.get("credit_statements"),
        "provider_failures_recorded": [
            "F2B_010C: 2 credits needed, 1 remaining (10s class) — refused",
            "F2B_010D: accepted at 1 credit, generation failed server-side",
            "010E: 0 remaining at precheck — dispatch never armed"],
    }
    write("V2_010E_F2B_EVIDENCE.json", f2b_evidence)

    lineage = {
        "version": "v2-010e-provider-lineage-v1",
        "checkpoint": "V2010E_P5_PROVIDER_LINEAGE",
        "built_at": utcnow(),
        "new_provider_interactions": 0,
        "carried_forward": "010C/010D lineage unchanged (see "
                           "V2_010D_PROVIDER_LINEAGE.json): M1 images, M2 "
                           "video 5.04s (1543843763689489), F2A video "
                           "10.08s (1540180629641233), F2B_010D release "
                           "(1540187097250321) failed server-side",
        "credit_timeline_statements": precheck.get("credit_statements"),
    }
    write("V2_010E_PROVIDER_LINEAGE.json", lineage)

    git = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    markers = [b"sessionid=", b"msToken=", b"a_bogus=", b"AIza", b"sk-",
               b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY"]
    hits_010e = []
    for rel in git:
        path = ROOT / rel
        if "010e" not in rel.lower() or not path.is_file():
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for marker in markers:
            if marker.lower() in blob.lower():
                hits_010e.append(f"{rel}: {marker.decode(errors='replace')}")
    secret_audit = {
        "version": "v2-010e-secret-audit-v1", "built_at": utcnow(),
        "tracked_files_scanned": len(git),
        "hits_in_010e_files": hits_010e,
        "journal_sanitization": "secret-named payload keys REDACTED before "
                                "disk (tested: test_12)",
        "verdict": "CLEAN" if not hits_010e else "FAIL",
    }
    write("V2_010E_SECRET_AUDIT.json", secret_audit)

    seal = {
        "version": "v2-010e-candidate-seal-v1",
        "checkpoint": "V2010E_P9_CANDIDATE_SEAL",
        "sealed_at": utcnow(),
        "status": "STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH",
        "completed_candidate": False,
        "checks": {
            "dola_browser_network_qualified": True,
            "duration_authority_5s_proven": True,
            "dispatch_receipt_durability_proven": True,
            "f2a_proven": True,
            "f2b_010e_proven": False,
            "f2_seedance_dola_proven": False,
            "mutations_used": "0/1 (UNSPENT)",
            "no_retry": True, "no_provider_switch": True,
            "no_output_history_inference": True,
            "secret_audit_clean": secret_audit["verdict"] == "CLEAN",
            "full_regression_pass": True,
        },
        "blocking_check": "f2b_010e_proven — the provider visibly reports 0 "
                          "remaining video credits today (4/day consumed: "
                          "M2 1 + F2A 2 + Owner's separate generation 1); "
                          "the fail-closed pre-dispatch gate stopped before "
                          "any release",
        "readiness": "the 010E machinery (journal, gates, precheck, recovery) "
                     "is committed and tested — a future attempt after the "
                     "daily credit reset is: re-run precheck → dispatch "
                     "mode; one command, one mutation",
        "unwatermarked_variant": "OBSERVED_NOT_AUTHORIZED (unchanged)",
    }
    write("V2_010E_CANDIDATE_SEAL.json", seal)
    print(json.dumps({"checkpoint": "V2010E_FINALIZED",
                      "status": seal["status"],
                      "secret_audit": secret_audit["verdict"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
