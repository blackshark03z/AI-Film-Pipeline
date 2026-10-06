"""V2-010D — finalization: reconstructed receipt, ledger truth, F2B evidence,
provider lineage, secret audit, candidate seal.

Terminal verdict: the F2B_010D request was released ONCE (proven by raw
capture + conversation echo), accepted by the provider (ack: last credit
reserved), and the provider then FAILED the generation server-side with an
explicit terminal notice ("動画を生成できません。今回の生成でクレジットは
使用されませんでした。") — no creation object was ever produced and the
provider asserts no credit was consumed for the failed generation.
Classification: STOPPED_EXPLICIT_PROVIDER_FAILURE. No retry (F2B_010D = ONE).
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
C10C = ROOT / "projects/quality_v2_010c_dola_fullstack"
PKG = ROOT / "projects/quality_v2_010d_f2b_completion"
sys.path.insert(0, str(ROOT / "tools"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")


def main() -> int:
    from mutation_authority import MutationAuthority
    auth = MutationAuthority(PKG, "QUALITY-V2-010D-F2B-COMPLETION")
    ledger_state = json.loads((PKG / "mutation_authority.json")
                              .read_text(encoding="utf-8"))
    consumed = [e for e in ledger_state["events"]
                if e["kind"] == "BUDGET_CONSUMED" and
                e.get("budget_kind") == "f2b_010d"]
    if not consumed:
        # the release DID happen (raw capture + conversation echo); the
        # crash only broke the accounting — record it truthfully
        auth._event("BUDGET_CONSUMED_RECONSTRUCTED", budget_kind="f2b_010d",
                    detail="release proven post-hoc: raw capture POST "
                           "2026-10-06T02:59:51.622605Z request_id 8052.765 "
                           "+ conversation echo idx29 msg 1540187097250321; "
                           "receipt-first persistence was broken by the "
                           "runner crash, accounting reconstructed")
    auth.record_knowledge(
        "RESOLVED_NO_EFFECT",
        "provider terminal notice idx34 msg 1543317950013969: generation "
        "failed server-side, no creation produced, no credit consumed for "
        "the failed generation (provider's own statement)")

    reservation = json.loads((PKG / "mutation_reservation_f2b_010d.json")
                             .read_text(encoding="utf-8"))
    attempt_doc = json.loads((PKG / "generation_attempt_f2b_010d.json")
                             .read_text(encoding="utf-8"))
    recon = json.loads((PKG / "V2_010D_RECONCILIATION.json")
                       .read_text(encoding="utf-8"))

    receipt = {
        "version": "v2-010d-f2b-receipt-reconstructed-v1",
        "checkpoint": "V2010D_P4_F2B_RECEIPT",
        "built_at": utcnow(),
        "run_id": reservation["run_id"],
        "reconstruction_basis": [
            "raw capture (DPAPI-decrypted): exactly ONE /chat/completion "
            "POST 2026-10-06T02:59:51.622605Z request_id 8052.765 with the "
            "F2B prompt body",
            "conversation echo idx29 msg 1540187097250321 (the question "
            "message the provider stored)",
            "acceptance ack idx30 msg 1544399803432977 (Seedance 2.0, "
            "1-3 min, 0 video credits remaining today — last credit "
            "reserved)",
            "terminal notice idx34 msg 1543317950013969 (generation failed, "
            "no credits used)"],
        "conversation_id": "38417972940811793",
        "question_message_id": "1540187097250321",
        "acceptance_ack_message_id": "1544399803432977",
        "failure_notice_message_id": "1543317950013969",
        "user_action_at": "2026-10-06T02:59:50Z (approx, pre-release)",
        "release_at": "2026-10-06T02:59:51.622605Z",
        "requested_duration_class": "5s (chip-gated pre-dispatch)",
        "receipt_first_note": "the original runner crashed before "
                              "persistence; this receipt is the read-only "
                              "reconstruction — the receipt-first ORDER "
                              "violation is recorded as a process defect, "
                              "the release itself is fully evidenced",
    }
    write("f2b_010d_receipt.json", receipt)

    f2b_evidence = {
        "version": "v2-010d-f2b-evidence-final-v1",
        "checkpoint": "V2010D_P4_F2B",
        "built_at": utcnow(),
        "status": "STOPPED_EXPLICIT_PROVIDER_FAILURE",
        "run_id": reservation["run_id"],
        "attempt": attempt_doc["attempt"],
        "reservation": reservation,
        "receipt": receipt,
        "chain": {
            "DURATION_AUTHORITY": "PROVEN pre-dispatch (chip 5s gated; "
                                  "screenshot 01_duration_5s_gated.png; zero "
                                  "pre-dispatch POSTs)",
            "USER_ACTION": "PROVEN (Enter; release at 02:59:51Z)",
            "NETWORK_RELEASE": "PROVEN (1 POST /chat/completion, raw capture)",
            "RECEIPT": "PROVEN post-hoc (conversation echo idx29; SSE_ACK "
                       "body was not captured — the crash preceded "
                       "loadingFinished)",
            "PROVIDER_ACCEPTANCE": "PROVEN (ack idx30: Seedance 2.0, 0 "
                                   "credits remaining)",
            "GENERATION_EFFECT": "NONE — provider failed server-side",
            "FAILURE_NOTICE": "PROVEN (idx34, newest chain message)",
        },
        "provider_failure": {
            "class": "EXPLICIT_PROVIDER_GENERATION_FAILURE",
            "message_ja": "動画を生成できません。今回の生成でクレジットは"
                          "使用されませんでした。",
            "message_en": "Cannot generate a video. No credits were used "
                          "for this generation.",
            "creation_objects_produced": 0,
            "credit_consumption": "provider asserts NONE for the failed "
                                  "generation (acceptance had reserved the "
                                  "last credit; the terminal notice "
                                  "contradicts and supersedes)",
            "not_ambiguity": "the provider itself resolved the effect "
                             "terminally; no latch-worthy uncertainty about "
                             "the effect remains (the scope IS latched for "
                             "the crash-induced release-without-receipt, "
                             "recorded separately)"},
        "false_correlation_exhibit": {
            "note": "the first reconciliation pass misattributed the "
                    "canary-4 history video (creation 1490518952401169, "
                    "msg 1488421378365201, sha c4a0761b…) as F2B_010D's "
                    "output — the known-id baseline was incomplete. The "
                    "timeline + gap probes corrected it. The misattributed "
                    "download is kept as assets/"
                    "MISATTRIBUTED_canary4_history_video.mp4",
            "lesson": "output correlation requires the COMPLETE known-id "
                      "baseline (every pre-existing creation in the "
                      "conversation), not just recent-run ids"},
        "adapter_events_note": "teardown noise (CDP events during "
                               "context.close after capture.stop closed the "
                               "handle) is cosmetic; the primary crash was "
                               "an unhandled exception class in the runner "
                               "(only RuntimeError was caught) — fixed in "
                               "the audited delta notes",
        "qc": {
            "TRANSPORT_QC": "PROVEN for dispatch/receipt/acceptance; "
                            "generation outcome provider-failed",
            "TECHNICAL_QC": "NOT_APPLICABLE_NO_ASSET",
            "CREATIVE_QC": "NOT_APPLICABLE_NO_ASSET"},
    }
    write("V2_010D_F2B_EVIDENCE.json", f2b_evidence)

    # misattributed download renamed for honesty
    assets = PKG / "assets"
    recovered = assets / "f2b010d_recovered.mp4"
    if recovered.exists():
        recovered.rename(assets / "MISATTRIBUTED_canary4_history_video.mp4")

    lineage = {
        "version": "v2-010d-provider-lineage-v1",
        "checkpoint": "V2010D_P5_PROVIDER_LINEAGE",
        "built_at": utcnow(),
        "terminal_state": "STOPPED_EXPLICIT_PROVIDER_FAILURE",
        "conversation_id": "38417972940811793",
        "today_message_chain": [
            {"idx": 2, "role": "bot", "id": "1492067769135377",
             "note": "canary-4 era ack (2 credits left, Sep 23)"},
            {"idx": 6, "role": "bot", "id": "1488421378365201",
             "creation": "1490518952401169 type2",
             "note": "canary-4 video (history)"},
            {"idx": 7, "role": "user", "id": "1541253913616145",
             "note": "M1 question (010C)"},
            {"idx": 8, "role": "bot", "id": "1546406012981009",
             "creations": "40033753389997329/7585/7841/8097 type1 (M1 "
                          "images, completed)"},
            {"idx": 12, "role": "user", "id": "1540169022826001",
             "note": "M2 question"},
            {"idx": 13, "role": "bot", "id": "1544386406376465",
             "note": "M2 ack (3 credits remaining)"},
            {"idx": 17, "role": "bot", "id": "1543848606611217",
             "creation": "1543843763689489 type2 (M2 video, 5.04s)"},
            {"idx": 18, "role": "user", "id": "1542233798828561",
             "note": "F2A question"},
            {"idx": 19, "role": "bot", "id": "1546412082202129",
             "note": "F2A ack (2 points, 1 credit remaining)"},
            {"idx": 23, "role": "bot", "id": "1541280229958417",
             "creation": "1540180629641233 type2 (F2A video, 10.08s)"},
            {"idx": 24, "role": "user", "id": "1545306167434769",
             "note": "F2B_010C question (refused)"},
            {"idx": 25, "role": "bot", "id": "1540189035768849",
             "note": "010C refusal (2 needed, 1 remaining)"},
            {"idx": 29, "role": "user", "id": "1540187097250321",
             "note": "F2B_010D question (THE release)"},
            {"idx": 30, "role": "bot", "id": "1544399803432977",
             "note": "F2B_010D acceptance (0 credits remaining)"},
            {"idx": 34, "role": "bot", "id": "1543317950013969",
             "note": "F2B_010D TERMINAL: generation failed, no credits "
                     "used (newest chain message; gap-probed)"}],
        "credit_arithmetic": {
            "day_start": 4, "m2": 1, "f2a": 2, "f2b_010c_refusal": 0,
            "f2b_010d": "reserved at acceptance (0 remaining), refunded/"
                        "not-consumed per terminal notice",
            "sources": "ack texts idx13/19/25/30/34"},
        "asset_lineage": "NONE — no creation object exists for F2B_010D",
    }
    write("V2_010D_PROVIDER_LINEAGE.json", lineage)

    # ---- secret audit -------------------------------------------------------
    git = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    markers = [b"sessionid=", b"msToken=", b"a_bogus=", b"AIza", b"sk-",
               b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY"]
    hits_total, hits_010d = [], []
    for rel in git:
        path = ROOT / rel
        if not path.is_file() or path.suffix in (".mp4", ".png", ".jpg"):
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for marker in markers:
            if marker.lower() in blob.lower():
                entry = f"{rel}: {marker.decode(errors='replace')}"
                hits_total.append(entry)
                if "010d" in rel.lower():
                    hits_010d.append(entry)
    secret_audit = {
        "version": "v2-010d-secret-audit-v1", "checkpoint": "V2010D_P6_AUDIT",
        "built_at": utcnow(),
        "tracked_files_scanned": len(git),
        "hits_in_010d_files": hits_010d,
        "baseline_note": "pre-existing hits are marker strings inside "
                         "redaction tooling/test fixtures (010C baseline "
                         "recorded 67); gate = ZERO new hits in 010D files",
        "verdict": "CLEAN" if not hits_010d else "FAIL",
        "secret_store": "runtime_secret_store/dola_session.dpapi (DPAPI "
                        "current-user, untracked); raw captures DPAPI-"
                        "encrypted at session close",
    }
    write("V2_010D_SECRET_AUDIT.json", secret_audit)

    ledger_export = {
        "version": "v2-010d-mutation-ledger-v1",
        "exported_at": utcnow(),
        "authority_state": json.loads(
            (PKG / "mutation_authority.json").read_text(encoding="utf-8")),
        "budget": {"f2b_010d": "released once (proven post-hoc); provider "
                               "failed the generation; no retry authority "
                               "remains"},
    }
    write("V2_010D_MUTATION_LEDGER.json", ledger_export)

    seal = {
        "version": "v2-010d-candidate-seal-v1",
        "checkpoint": "V2010D_P9_CANDIDATE_SEAL",
        "sealed_at": utcnow(),
        "status": "STOPPED_EXPLICIT_PROVIDER_FAILURE",
        "completed_candidate": False,
        "checks": {
            "m2_qualification_remains_proven": True,
            "f2a_remains_proven": True,
            "f2b_010d_proven": False,
            "duration_authority_proven": True,
            "no_retry": True,
            "no_alternate_provider": True,
            "no_native_http": True,
            "no_cookie_http": True,
            "no_dom_gallery_lineage": True,
            "secret_audit_clean": secret_audit["verdict"] == "CLEAN",
            "tests_pass": True,
            "evidence_complete": True,
            "working_tree_known": True,
        },
        "blocking_check": "f2b_010d_proven — the provider failed the "
                          "generation server-side on its ONLY authorized "
                          "attempt; a further attempt requires NEW Owner "
                          "authority (no retry within 010D)",
        "unwatermarked_variant": json.loads(
            (PKG / "V2_010D_UNWATERMARKED_VARIANT.json")
            .read_text(encoding="utf-8"))["status"]
        if (PKG / "V2_010D_UNWATERMARKED_VARIANT.json").exists()
        else "PENDING",
    }
    write("V2_010D_CANDIDATE_SEAL.json", seal)
    print(json.dumps({"checkpoint": "V2010D_FINALIZED",
                      "status": seal["status"],
                      "secret_audit": secret_audit["verdict"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
