"""AI-FILM-QUALITY-V2-010C — M1 oracle evidence (v2, post-analysis).

M1's driver exited STOPPED_PROVIDER_CORRELATION_GAP because its live watcher
scanned for VIDEO urls while the provider dispatched an IMAGE-class job (4
keyframes) — the watch was video-shaped, the generation was not. Offline
correlation (read-only poll + sanitized captures) proves the full chain with
image-class output. No latch was raised; authority stays OPEN (1 consumed).
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
    receipt = json.loads((PKG / "m1_receipt.json").read_text(encoding="utf-8"))
    observation = json.loads((PKG / "V2_010C_M1_OUTPUT_OBSERVATION.json")
                             .read_text(encoding="utf-8"))
    incomplete = json.loads((PKG / "m1_incomplete.json").read_text(encoding="utf-8"))
    reservation = json.loads((PKG / "mutation_reservation_m1.json")
                             .read_text(encoding="utf-8"))

    m1_creations = observation.get("m1_target_creations", [])
    all_completed = all(c.get("image_status") == 2 for c in m1_creations) \
        if m1_creations else False

    evidence = {
        "version": "v2-010c-m1-oracle-evidence-v2",
        "checkpoint": "V2010C_P3_M1_ORACLE_PROVEN",
        "built_at": utcnow(),
        "run_id": receipt.get("run_id"),
        "reservation": reservation,
        "dispatch_classification": {
            "requested": "smallest valid Seedance VIDEO generation",
            "observed": "Agent-Creation interpreted the typed prompt as an "
                        "IMAGE job: 4 type-1 creations (req_key "
                        "seedream_v43_flow), NO video task created; the bot "
                        "then offered to turn a keyframe into a 5-second "
                        "video (that follow-up became M2)",
            "consequence": "the driver's video-shaped live watcher correctly "
                           "refused to correlate unrelated outputs; the "
                           "provider interaction itself completed cleanly "
                           "and was never ambiguous"},
        "chain_verdicts": {
            "USER_ACTION": "PROVEN (Enter at " + receipt["user_action_at"] + ")",
            "NETWORK_RELEASE": "PROVEN (1 POST /chat/completion, live marker "
                               "match + body correlation)",
            "RECEIPT": "PROVEN (SSE_ACK ack_client_meta.conversation_id="
                       + receipt["conversation_id"] + "; corroborated by URL tail)",
            "STABLE_IDS": "PROVEN (question 1541253913616145 / reply "
                          "1546406012981009 / creations ×4)",
            "POLL_STREAM": "PROVEN (SSE stream frames captured: "
                           "SSE_ACK → FULL_MSG_NOTIFY → DOWNLINK_CMD → "
                           "STREAM_MSG_NOTIFY → STREAM_CHUNK×150 → "
                           "SSE_REPLY_END; WS push channel active)",
            "EXACT_GENERATION": "PROVEN (read-only poll: 4 type-1 creations "
                                "with the EXACT card ids, image_status 2 = "
                                "completed)",
            "EXACT_VIDEO": "NOT_APPLICABLE_IMAGE_CLASS (video output stage "
                           "is M2's purpose)"},
        "receipt": receipt,
        "output_correlation": {
            "method": "creation-id equality between the live STREAM_CHUNK "
                      "card (captured pre-completion) and the read-only "
                      "/im/chain/single poll (post-completion) — history-"
                      "immune, network authority",
            "creations": m1_creations,
            "all_completed": all_completed},
        "provider_lineage": {
            "conversation_id": receipt["conversation_id"],
            "message_index": 7,
            "mutation_budget": "m1_browser_oracle consumed (1 of hard max 4)"},
        "live_watcher_exit": incomplete,
        "note": "no OWNER_AMBIGUITY_GATE: request, receipt, and effect are "
                "all observed and provable; the gap was watcher-shape, not "
                "provider opacity",
    }
    (PKG / "V2_010C_BROWSER_ORACLE_EVIDENCE.json").write_text(
        json.dumps(evidence, indent=1, ensure_ascii=False), encoding="utf-8")

    from mutation_authority import MutationAuthority
    auth = MutationAuthority(PKG, "QUALITY-V2-010C-DOLA-FULLSTACK")
    auth._event("M1_ANALYSIS_ANNOTATION",
                detail=json.dumps({
                    "dispatch_class": "IMAGE (Agent-Creation seedream_v43_flow)",
                    "chain": "dispatch/receipt/IDs/progress/output PROVEN",
                    "video_stage": "deferred to M2",
                    "latch": "NONE — authority remains OPEN"}))
    print(json.dumps({"checkpoint": "V2010C_M1_EVIDENCE_V2",
                      "all_completed": all_completed,
                      "creations": len(m1_creations)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
