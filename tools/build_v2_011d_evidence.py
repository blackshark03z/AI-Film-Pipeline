"""V2-011D final evidence builder — fail-closed (recomputes every custody SHA).

Slice outcome: F1R PROVEN+ACCEPTED (world-matched), F1R->F2 CUT_PASS,
F3R UNRELEASED — STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH (0 credits visible
on every enumerable account). F2 locked and untouched throughout.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
F2_PROOF = PKG / "inputs_F2_proof.mp4"
F2_EXPECT = "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"


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


f2_sha = sha256(F2_PROOF)
assert f2_sha == F2_EXPECT, "F2 proof custody mismatch"
f1r_sha = sha256(PKG / "assets" / "f1r.mp4")
qc = json.loads((PKG / "V2_011D_F1R_QC.json").read_text(encoding="utf-8"))
assert qc["asset"]["sha256"] == f1r_sha, "F1R QC sha drift"
dump = json.loads((PKG / "V2_011D_F1R_CREATION_DUMP.json").read_text(encoding="utf-8"))
creation = dump["type2_creations"][0]["creation"]
runner_ev = json.loads((PKG / "V2_011D_F1R_EVIDENCE.json").read_text(encoding="utf-8"))
print("custody re-verified: F2", f2_sha[:8], "| F1R", f1r_sha[:8])

# ---- context cut QC -------------------------------------------------------
write("V2_011D_CONTEXT_CUT_QC.json", {
    "version": "v2-011d-context-cut-qc-v1",
    "checkpoint": "V2011D_CUT_QC",
    "recorded_at": utcnow(),
    "F1R_to_F2": {
        "junction": "F1R selected end -> HARD CUT -> locked F2 frame 0",
        "base_boundary": {"f1r_last_frame": 114, "f2_frame": 0},
        "trim_window": "F1R OUT exclusive 103..121 (base 115 = F1-slot parity; asset has 121 frames so +12 clips to +6)",
        "inspected": {
            "f1r_frames": "103..120",
            "f2_locked_frames": "0..14",
            "sheet": "owner_review_011d/F1R_F2_JUNCTION.png",
            "full_res_pair": "frames/PAIR_F1R_n114_F2_n0.png",
        },
        "dimensions": {
            "geography": {"verdict": "PASS", "evidence": "same world family: continuous natural dark rock ridge, single narrow gap, road funnels in, no architecture, no bypass — the 011C freestanding-gate/open-field failure is resolved"},
            "lighting": {"verdict": "PASS", "evidence": "cold blue-grey storm both sides (F1R luma 67.80 / U 139.04 / V 114.94 vs F2 start region 83.63 / 139.85 / 114.52 — chroma near-exact, F1R slightly darker/mistier)"},
            "palette": {"verdict": "PASS", "evidence": "continuous cold storm family; no warm light anywhere"},
            "weather": {"verdict": "PASS", "evidence": "heavy overcast + wind-driven mist both sides"},
            "screen_direction": {"verdict": "PASS", "evidence": "faces/travels frame-left both sides"},
            "travel_direction": {"verdict": "PASS", "evidence": "right-to-left approach into the pass"},
            "motion_phase": {"verdict": "PASS", "evidence": "mid-stride lean-into-gust on both sides of the cut"},
            "identity": {"verdict": "PASS", "evidence": "white robes, black sash, topknot, streaming headband; no weapon either side"},
            "causal_action": {"verdict": "PASS", "evidence": "arrive at the pass -> enter/commit: the F2A commit beat lands"},
        },
        "observations": [
            "ridge scale: F1R's extreme WS renders the ridge monumental; F2 shows the human-scale entry — reads as establishing-shot scale rendering of the same landmark (walkable opening at the gap base), not a landmark identity break",
            "character-scale cut-in (tiny WS figure -> mid figure) is standard grammar",
        ],
        "verdict": "CUT_PASS",
    },
    "F2_to_F3R": {
        "verdict": "NOT_EVALUATED_F3R_UNRELEASED",
        "reason": "F3R generation blocked by the fail-closed credit gate (0 credits provider-visible on every enumerable account); the frozen F3R spec is ready for the successor slice",
    },
    "critical_failures_not_averaged": True,
})

# ---- editorial ranges ------------------------------------------------------
write("V2_011D_EDITORIAL_RANGES.json", {
    "version": "v2-011d-editorial-ranges-v1",
    "checkpoint": "V2011D_RANGES",
    "fps_rule": "24 fps nearest-frame boundary resolution (011B/011C rule)",
    "F1R": {
        "asset_sha256": f1r_sha,
        "provider_frames": 121,
        "base_selected_frames": [0, 114],
        "base_out_note": "IN=0 frozen; base OUT exclusive 115 = F1 slot editorial-target parity (4.791667s)",
        "allowed_trim": "OUT exclusive 103..121 (+/-12 clipped by asset length)",
        "junction_qc_base_used": True,
    },
    "F2_LOCKED": {
        "asset_sha256": f2_sha,
        "frames": [0, 133],
        "immutable": True,
    },
    "F3R": {
        "asset_sha256": None,
        "status": "UNRELEASED (spec frozen: V2_011D_F3R_SPEC.json)",
        "planned_base": [0, 76],
        "planned_trim": "IN 0..12; OUT follows IN (IN+77) preserving the 3.208333s F3 slot duration",
    },
})

# ---- credit gate final -----------------------------------------------------
inquiry = json.loads((PKG / "V2_011D_F3R_CREDIT_GATE.json").read_text(encoding="utf-8"))
write("V2_011D_F3R_CREDIT_GATE.json", {
    "version": "v2-011d-f3r-credit-gate-final-v1",
    "recorded_at": utcnow(),
    "required_credit": 1,
    "account_observations": [
        {"account": "ACCOUNT_A", "state": "0 credit — provider statement in the F1R conversation (本日の残りは0動画クレジットです) after billing the F1R mutation"},
        {"account": "ACCOUNT_B", "state": "LOGIN_REQUIRED (no sessionid in DPAPI store; manual login is Owner-side)"},
        {"account": "ACCOUNT_C", "state": "NO_CREDIT — provider statement 残りは0動画クレジット observed read-only at 2026-10-06T11:51:07Z (router probe)"},
    ],
    "inquiry_attempt": {
        "mechanism": "V2-010E established text inquiry (no video credit consumed)",
        "outcome": inquiry.get("credit_verdict"),
        "note": "the inquiry navigation hit a transient logged-out UI state; the subsequent router probe reached the session and observed the decisive 0-credit statement",
    },
    "verdict": "INSUFFICIENT (0 credits visible across all enumerable accounts)",
    "consequence": "F3R pre-render gate FAILS CLOSED — no dispatch attempted; F3R mutation remains UNRELEASED (0/1)",
    "daily_window_note": "provider daily credit reset expected at JST midnight (≈16:00 UTC, ≈3.5h after this record) — a successor slice may release F3R with exactly ONE generate",
})

# ---- mutation ledger final -------------------------------------------------
slot_f1r = json.loads((PKG / "slot_f1r" / "mutation_authority.json").read_text(encoding="utf-8"))
f3r_slot_path = PKG / "slot_f3r" / "mutation_authority.json"
slot_f3r = (json.loads(f3r_slot_path.read_text(encoding="utf-8"))
            if f3r_slot_path.exists() else
            {"status": "NOT_CREATED — pre-render gates precede authority "
                       "instantiation; the F3R credit gate failed closed "
                       "before any reservation existed"})
write("V2_011D_MUTATION_LEDGER.json", {
    "version": "v2-011d-mutation-ledger-final-v1",
    "built_at": utcnow(),
    "mutations": {
        "F1R": "1/1 (released 2026-10-06T11:1xZ; receipt-window OWNER_AMBIGUITY_GATE latch — one-way per frozen invariant; external effect RESOLVED_EFFECT_IDENTIFIED by read-only reconciliation: completed video acquired and hard-QC ACCEPTED)",
        "F3R": "0/1 (UNRELEASED — pre-dispatch credit gate failed closed: 0 credits visible on all enumerable accounts)",
    },
    "max": 2,
    "no_retry": True,
    "no_provider_switch": True,
    "credit_authority": "provider-visible statements (010E/011R rule)",
    "slots": {"slot_f1r": slot_f1r, "slot_f3r": slot_f3r},
})

# ---- provider lineage ------------------------------------------------------
write("V2_011D_PROVIDER_LINEAGE.json", {
    "version": "v2-011d-provider-lineage-v1",
    "built_at": utcnow(),
    "account_F1R": "ACCOUNT_A (dola-main)",
    "F1R": {
        "conversation_id": dump["f1r_conversation_id"],
        "creation_id": creation.get("id"),
        "vid": creation.get("video", {}).get("vid"),
        "provider_filehash": creation.get("video", {}).get("download_filehash"),
        "asset_sha256": f1r_sha,
        "duration_s": creation.get("video", {}).get("duration"),
        "model_statement": "Seedance 2.0",
    },
    "F3R": None,
    "credit_timeline": {
        "before_011D": "ACCOUNT_A 1 remaining (011R provider ack; confirmed by the 011D precheck probe: READY credit=1)",
        "after_F1R": "ACCOUNT_A 0 (provider statement in the F1R conversation)",
        "ACCOUNT_C": "0 observed read-only (残りは0動画クレジット)",
        "note": "provider statements are the credit authority",
    },
    "delivery_shape_variance": "the limit-20 conversation poll returned the completed type-2 creation WITHOUT download_url; the limit-10 poll returns the full object (signed URL). Recorded so future runners/reconcilers poll with limit<=10 for Seedance 2.0 deliveries",
    "watermark": "Dola AI watermark present on F1R (PRESERVED per policy; 011W will handle watermark authority separately)",
})

# ---- sequence QC -----------------------------------------------------------
write("V2_011D_SEQUENCE_QC.json", {
    "version": "v2-011d-sequence-qc-v1",
    "checkpoint": "V2011D_SEQUENCE_QC",
    "recorded_at": utcnow(),
    "FULL_SEQUENCE_CONTEXT": "NOT_PROVEN_F3R_UNRELEASED",
    "provable_parts": {
        "F1R_world_match": "PROVEN (hard QC 7/7 PASS; chroma near-exact to locked F2 start region)",
        "F1R_F2_cut": "CUT_PASS (frame evidence; all 9 required dimensions PASS)",
        "F2_integrity": "LOCKED and untouched (proof sha re-verified)",
    },
    "missing_for_full_sequence": [
        "F3R generation (1 credit) — the only missing piece",
        "then F2->F3R cut QC + full assembly + sequence QC per the frozen spec",
    ],
    "audio_context": "AUDIO_CONTEXT = FINISHING_REPAIR_REQUIRED carried forward (011C measured 7.2 dB / 11.8 dB ambience steps at the context cuts; F1R ambience level to be matched in the finishing mix)",
    "watermark_rule": "PRESERVE — no removal/concealment; UNWATERMARKED_VARIANT = OBSERVED_NOT_AUTHORIZED (011W scope)",
})

# ---- candidate seal --------------------------------------------------------
write("V2_011D_CANDIDATE_SEAL.json", {
    "version": "v2-011d-candidate-seal-v1",
    "sealed_at": utcnow(),
    "checkpoint": "V2011D_SEAL",
    "status": "STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH",
    "engineering_status": "F1R repair PROVEN and ACCEPTED; F1R->F2 CUT_PASS; F2 immutable; F3R spec frozen; all governance artifacts written",
    "film_context_status": "FULL_SEQUENCE_CONTEXT NOT PROVEN — F3R missing (external credit gate)",
    "canonical": {
        "F2_SEQUENCE": "FILM_USABLE (unchanged, sha re-verified)",
        "F1R": "ACCEPTED (world-matched context repair, 1/1 mutation)",
        "F1R_F2_CUT": "PASS",
        "F3R": "UNRELEASED (0/1, spec frozen)",
        "FULL_SEQUENCE_CONTEXT": "NOT_PROVEN_F3R_UNRELEASED",
        "SEQ_CONTEXT_LOCK": "DENIED (pending F3R)",
    },
    "checks": {
        "world_lock_derived_from_F2_imagery": True,
        "f1r_spec_frozen_before_dispatch": True,
        "prerender_gates_enforced": True,
        "f1r_release_proven": True,
        "f1r_receipt_window_latched": True,
        "f1r_reconciled_read_only": True,
        "f1r_hard_qc_accepted_7_of_7": True,
        "f1r_f2_cut_pass_with_frame_evidence": True,
        "f2_untouched_sha_verified": True,
        "f3r_credit_gate_failed_closed": True,
        "f3r_unspent": True,
        "no_retry": True,
        "secret_audit_clean": True,
        "watermark_preserved": True,
        "mutations_used": "1/2",
    },
    "next_handoff": "Tech Lead: when provider credit is available (daily reset ≈ JST midnight / Owner top-up), run the F3R successor slice — ONE generate per the frozen V2_011D_F3R_SPEC.json on a READY account, then F2->F3R cut QC + full assembly + sequence QC + SEQ_CONTEXT_LOCK decision. After SEQ_CONTEXT_LOCK=GRANTED, return for V2-011W (Dola unwatermarked asset authority qualification) — NOT finishing",
    "provider_mutations_used": 1,
})

print("V2-011D evidence complete")
