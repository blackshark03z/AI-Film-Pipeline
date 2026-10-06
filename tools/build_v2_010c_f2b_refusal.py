"""AI-FILM-QUALITY-V2-010C — F2B final evidence: explicit provider refusal.

The F2B dispatch was released (SSE_ACK receipt for the message) but the
provider REFUSED the generation before any generation effect:

    現在のパラメーターで生成すると、2動画クレジットが使用されます。
    本日は残り1のみです。パラメーターを変更してもう一度お試しください。
    ("Generating with the current parameters will use 2 video credits.
      Today only 1 remains. Change the parameters and try again.")

Classification: STOPPED_PROVIDER_CREDIT_REFUSAL — deterministic, explicit,
externally checkable; NOT an ambiguity (no latch), NOT a correlation gap.
The F2B=ONE authority is spent; a parameter-corrected F2B (5s class, 1
credit) requires a NEW Owner authorization in a fresh scope.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
sys.path.insert(0, str(ROOT / "tools"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    receipt = json.loads((PKG / "f2b_receipt.json").read_text(encoding="utf-8"))
    runner_evidence = json.loads((PKG / "V2_010C_F2B_EVIDENCE.json")
                                 .read_text(encoding="utf-8"))

    refusal = {
        "version": "v2-010c-f2b-refusal-evidence-v1",
        "checkpoint": "V2010C_P7_F2B_REFUSAL",
        "built_at": utcnow(),
        "status": "STOPPED_PROVIDER_CREDIT_REFUSAL",
        "run_id": receipt.get("run_id"),
        "receipt": receipt,
        "dispatch": {
            "video_mode_text": receipt.get("video_mode_text"),
            "reference_attached": receipt.get("reference_attached"),
            "released": True,
            "receipt_state": "SSE_ACK captured for the message "
                             "(conversation 38417972940811793)",
        },
        "provider_response": {
            "class": "EXPLICIT_REFUSAL_CREDIT_INSUFFICIENT",
            "message_ja": "現在のパラメーターで生成すると、2動画クレジットが"
                          "使用されます。本日は残り1のみです。パラメーターを"
                          "変更してもう一度お試しください。",
            "message_en": "Generating with the current parameters will use 2 "
                          "video credits. Today only 1 remains. Please change "
                          "the parameters and try again.",
            "generation_effect": "NONE — provider refused BEFORE generating; "
                                 "no video credits spent on the refusal",
        },
        "credit_accounting": {
            "observed_costs": {"5s_video": 1, "10s_video": 2},
            "sequence": ["M2 5s video → 1 credit", "F2A 10s video → 2 credits",
                         "remainder: 1", "F2B 10s-class default → needs 2 > 1"],
            "arithmetic_consistent": True,
            "note": "F2A's 10.08s output despite the 5-second prompt text "
                    "proves the 動画を作成 mode default is the 10s class; a "
                    "5s-class F2B would fit the remaining credit"},
        "runner_record": runner_evidence.get("status"),
        "authority_disposition": {
            "mutation_budget": "f2b_dola consumed (4 of HARD MAX 4 used: "
                               "M1, M2, F2A, F2B-slot)",
            "retry": "PROHIBITED — F2B = ONE, no retry",
            "reauthorization_path": "NEW Owner-authorized scope may dispatch "
                                    "ONE F2B at the 5s class (1 credit, "
                                    "trim-compatible with the 2.8s editorial "
                                    "slots) through the SAME qualified "
                                    "adapter",
            "latch": "NONE — refusal is explicit, knowledge RESOLVED_NO_"
                     "EFFECT for the F2B generation"},
        "qc": {
            "TRANSPORT_QC": "NOT_APPLICABLE_NO_GENERATION",
            "TECHNICAL_QC": "NOT_APPLICABLE_NO_GENERATION",
            "CREATIVE_QC": "NOT_APPLICABLE_NO_GENERATION"},
    }
    (PKG / "V2_010C_F2B_EVIDENCE.json").write_text(
        json.dumps(refusal, indent=1, ensure_ascii=False), encoding="utf-8")

    from mutation_authority import MutationAuthority
    auth = MutationAuthority(PKG, "QUALITY-V2-010C-DOLA-FULLSTACK")
    auth.record_knowledge(
        "RESOLVED_NO_EFFECT",
        "F2B: provider refused generation BEFORE any effect (2 video "
        "credits needed, 1 remaining); explicit and deterministic; no latch")
    auth._event("F2B_PROVIDER_CREDIT_REFUSAL",
                detail=json.dumps({"needs": 2, "remaining": 1,
                                   "class": "10s default"}))
    print(json.dumps({"checkpoint": "V2010C_F2B_REFUSAL_RECORDED",
                      "status": refusal["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
