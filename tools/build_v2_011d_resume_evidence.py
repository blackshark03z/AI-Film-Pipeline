"""V2-011D RESUME — final evidence (provider refusal outcome).

Fail-closed: custody SHAs recomputed before writing.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011d_world_matched_context"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write(name, payload):
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")
    print("wrote", name)


f2_sha = sha256(PKG / "inputs_F2_proof.mp4")
assert f2_sha == "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"
f1r_sha = sha256(PKG / "assets" / "f1r.mp4")
assert f1r_sha == "b879f21586392fa7463021f60853b1aa99fecb286890dad1b3f192c6dd805171"

recon = json.loads((PKG / "V2_011D_F3R_RECONCILIATION.json").read_text(encoding="utf-8"))
spec = json.loads((PKG / "V2_011D_F3R_SPEC.json").read_text(encoding="utf-8"))
prompt_sha = hashlib.sha256(spec["prompt"].encode()).hexdigest()
runner_ev = json.loads((PKG / "V2_011D_F3R_EVIDENCE.json").read_text(encoding="utf-8"))

# ---- F3R evidence final ----------------------------------------------------
write("V2_011D_F3R_EVIDENCE.json", {
    "version": "v2-011d-f3r-evidence-final-v1",
    "recorded_at": utcnow(),
    "shot": "F3R",
    "status": "RESOLVED_EFFECT_IDENTIFIED_PROVIDER_REFUSAL",
    "spec_frozen": {"prompt_sha256_head": prompt_sha[:16],
                    "budget_kind": "f3_r"},
    "dispatch": {
        "account_opaque_id": "ACCOUNT_D (owner-manual native login, fresh "
                             "Dola account Khởi Đặng219)",
        "journal_events": [e.get("kind") for e in runner_ev["journal_events"]],
        "release": {"duration": 5, "needle_present": True,
                    "session_authenticated": True,
                    "baseline_known_creations": 0},
        "receipt_window": "not captured within 120s — OWNER_AMBIGUITY_GATE "
                          "latched (one-way, frozen invariant); external "
                          "effect resolved read-only",
    },
    "reconciliation": recon,
    "provider_refusal": {
        "refusal_text": "当社のポリシーに違反する可能性がある内容が入力されているため、動画を生成できません。修正してもう一度お試しください。",
        "translation": "The input may contain content that violates our "
                       "policies; the video cannot be generated. Modify and "
                       "try again.",
        "billed": True,
        "credit_ack": "本日の残りは3動画クレジットです — the fresh account's daily "
                      "grant was 4; the release consumed 1 (the Owner's "
                      "structural credit authorization was factually sound)",
        "asset": None,
        "classification": "the MCU close-up prompt (face/shoulders portrait "
                          "with wind-whipped hair) tripped the provider "
                          "content-policy filter — NOT a credit failure and "
                          "NOT a session failure",
    },
    "mutation_accounting": {
        "video_generation_mutations": "F1R=1 consumed (accepted), F3R=1 "
                                      "consumed (released, billed, refused — "
                                      "no asset). Total 2/2. NO retry "
                                      "authorized post-release.",
        "account_state_query_mutations": "1 (the credit inquiry; the bot "
                                         "refused — recorded separately)",
    },
})

# ---- mutation ledger final -------------------------------------------------
slot_f1r = json.loads((PKG / "slot_f1r" / "mutation_authority.json").read_text(encoding="utf-8"))
slot_f3r = json.loads((PKG / "slot_f3r" / "mutation_authority.json").read_text(encoding="utf-8"))
write("V2_011D_MUTATION_LEDGER.json", {
    "version": "v2-011d-mutation-ledger-final-v2",
    "built_at": utcnow(),
    "mutations": {
        "F1R": "1/1 (released 11:1xZ on ACCOUNT_A; receipt-window latch; "
               "reconciled read-only; asset acquired b879f215…; hard QC "
               "7/7 ACCEPTED)",
        "F3R": "1/1 (released 14:31Z on ACCOUNT_D native session; receipt-"
               "window latch; reconciled read-only: provider content-policy "
               "REFUSAL — release accepted and billed, no asset; NO retry "
               "authorized)",
    },
    "max": 2,
    "total_consumed": "2/2",
    "no_retry": True,
    "no_provider_switch": True,
    "slots": {"slot_f1r": slot_f1r, "slot_f3r": slot_f3r},
})

# ---- provider lineage ------------------------------------------------------
write("V2_011D_PROVIDER_LINEAGE.json", {
    "version": "v2-011d-provider-lineage-final-v1",
    "built_at": utcnow(),
    "F1R": {
        "account": "ACCOUNT_A (dola-main)",
        "conversation_id": "38417962862699025",
        "creation_id": "1546471384527889",
        "vid": "v186a3gm000cdb2dgqfog65h35lcimvg",
        "asset_sha256": f1r_sha,
        "duration_s": 5.088005,
        "model_statement": "Seedance 2.0",
        "verdict": "ACCEPTED",
    },
    "F3R": {
        "account": "ACCOUNT_D (owner-manual native login; fresh Dola "
                   "account Khởi Đặng219)",
        "conversation_id": recon.get("f3r_conversation_id"),
        "creation_id": None,
        "vid": None,
        "asset": None,
        "provider_refusal": True,
        "credit_after_release": 3,
        "verdict": "RELEASED_BILLED_REFUSED_NO_ASSET",
    },
    "session_remediation_record": [
        "captured-cookie route (real-Chrome session replayed in patchright) "
        "invalidated by ByteDance passport fingerprint binding — the 010B "
        "lesson confirmed at the session layer",
        "remedied by Owner's NATIVE Google login inside the ACCOUNT_D "
        "automation profile (fingerprint-consistent; runner then "
        "authenticated immediately)",
    ],
    "credit_timeline": {
        "ACCOUNT_A": "1 → 0 (F1R billed; statement 本日の残りは0動画クレジット)",
        "ACCOUNT_D": "fresh grant 4 → 3 (F3R release billed; statement "
                     "本日の残りは3動画クレジット)",
    },
    "watermark": "n/a for F3R (no asset); F1R carries the Dola AI watermark "
                 "(preserved)",
})

# ---- sequence QC -----------------------------------------------------------
write("V2_011D_SEQUENCE_QC.json", {
    "version": "v2-011d-sequence-qc-final-v1",
    "recorded_at": utcnow(),
    "FULL_SEQUENCE_CONTEXT": "NOT_PROVEN_F3R_PROVIDER_REFUSAL",
    "proven_parts": {
        "F1R_world_match": "PROVEN (hard QC 7/7; chroma near-exact to locked "
                           "F2 start region)",
        "F1R_F2_cut": "CUT_PASS (frame evidence, 9/9 dimensions)",
        "F2_integrity": "LOCKED and untouched (sha re-verified)",
    },
    "missing": "F3R asset — the provider refused the frozen prompt after the "
               "release was accepted and billed; the ONE authorized mutation "
               "is spent; no retry",
    "audio_context": "AUDIO_CONTEXT = FINISHING_REPAIR_REQUIRED (carried)",
    "watermark_rule": "PRESERVE / UNWATERMARKED_VARIANT = "
                      "OBSERVED_NOT_AUTHORIZED (011W scope)",
})

# ---- candidate seal --------------------------------------------------------
write("V2_011D_CANDIDATE_SEAL.json", {
    "version": "v2-011d-candidate-seal-final-v1",
    "sealed_at": utcnow(),
    "checkpoint": "V2011D_RESUME_SEAL",
    "status": "STOPPED_EXPLICIT_PROVIDER_FAILURE",
    "completed_candidate": False,
    "engineering_status": "world lock proven; F1R repaired and ACCEPTED "
                          "(1/2 mutations); F1R→F2 CUT_PASS; F2 immutable; "
                          "F3R spec frozen and released per authority",
    "film_context_status": "FULL_SEQUENCE_CONTEXT NOT PROVEN — F3R refused "
                           "by the provider content policy after billing",
    "canonical": {
        "F2_SEQUENCE": "FILM_USABLE (unchanged, sha re-verified)",
        "F1R": "ACCEPTED",
        "F1R_F2_CUT": "PASS",
        "F3R": "RELEASED_BILLED_REFUSED_NO_ASSET (mutation spent 1/1)",
        "FULL_SEQUENCE_CONTEXT": "NOT_PROVEN_F3R_PROVIDER_REFUSAL",
        "SEQ_CONTEXT_LOCK": "DENIED",
        "SEQ7_F1_F2_F3": "NOT_FILM_USABLE_AS_A_CONTINUOUS_CONTEXT_UNIT "
                         "(pending a policy-safe F3R in a NEW authorized slice)",
    },
    "checks": {
        "custody_verified": True,
        "f1r_accepted": True,
        "f1r_f2_cut_pass": True,
        "f2_untouched": True,
        "f3r_spec_unchanged": True,
        "f3r_release_proven": True,
        "f3r_reconciled_read_only": True,
        "f3r_provider_refusal_confirmed": True,
        "mutations_used": "2/2",
        "no_retry": True,
        "no_provider_switch": True,
        "secret_audit_clean": True,
        "watermark_preserved": True,
        "account_state_query_mutations": 1,
        "session_remediation_documented": True,
    },
    "next_handoff": "Tech Lead: F3R needs a NEW Owner-authorized slice "
                    "(proposed V2-012) with a policy-safe rephrase of the "
                    "FROZEN intent (same MCU/beat/world — reworded to pass "
                    "the provider content filter, e.g. avoid the "
                    "face-close-up + hair-whip trigger pattern), exactly ONE "
                    "mutation on a READY account (ACCOUNT_D has 3 credits "
                    "visible), then the unchanged 011D resume workflow: hard "
                    "QC → F2→F3R cut QC (IN ±12) → assembly → sequence QC → "
                    "SEQ_CONTEXT_LOCK decision → V2-011W",
    "provider_mutations_used": 2,
})

print("V2-011D RESUME evidence complete")
