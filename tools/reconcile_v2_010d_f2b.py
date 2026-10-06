"""V2-010D — post-crash READ-ONLY reconciliation of the released F2B_010D.

The runner crashed between the user action and receipt-first persistence,
but the raw capture proves EXACTLY ONE /chat/completion release
(2026-10-06T02:59:51Z, request_id 8052.765) with the 5s video-mode state
gated pre-dispatch. This tool:
  1. latches the scope (OWNER_AMBIGUITY_GATE — the letter of the ambiguity
     rule; latch never blocks read-only reconciliation),
  2. resolves external-effect knowledge by read-only poll,
  3. if a NEW type-2 creation completed → acquires the exact video and
     records the deterministic lineage (no further mutation exists or is
     needed: CDN download is asset acquisition, not a provider mutation).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-010D-F2B-COMPLETION"
PKG = ROOT / "projects/quality_v2_010d_f2b_completion"
RELEASE_UTC = "2026-10-06T02:59:51"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority != "LATCHED_CLOSED":
        auth.latch("F2B_010D_RELEASE_WITHOUT_RECEIPT_PERSISTENCE",
                   "runner crashed between user action and receipt-first "
                   "persistence; raw capture proves exactly one "
                   "/chat/completion release at " + RELEASE_UTC + "Z")
        emit({"event": "ambiguity_latch_recorded"})

    # ---- read-only reconciliation -----------------------------------------
    adapter = DolaBrowserAdapter010D(run_id="recon_" +
                                     datetime.now(timezone.utc)
                                     .strftime("%Y%m%dT%H%M%S"))
    try:
        await adapter.open()
        await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        poll = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
    except Exception as error:
        emit({"status": "RECONCILIATION_BLOCKED",
              "reason": type(error).__name__})
        await adapter.close(sanitize_to=None)
        return 1

    replies = poll.get("replies", [])
    texts = poll.get("texts", [])
    # known ids from 010C (M1 images ×4, M2 video, F2A video)
    known = set()
    f2a = json.loads((ROOT / "projects/quality_v2_010c_dola_fullstack/"
                      "V2_010C_F2A_EVIDENCE.json").read_text(encoding="utf-8"))
    for cid in (f2a.get("qc", {}).get("TRANSPORT_QC", {})
                .get("creation_ids") or []):
        known.add(cid)
    known |= {"40033753389997329", "40033753389997585",
              "40033753389997841", "40033753389998097",
              "1543843763689489"}
    fresh = [r for r in replies if r.get("creation_id") not in known]
    done = [r for r in fresh if r.get("type") == 2
            and r.get("video_download_url")]
    emit({"event": "reconciliation_poll",
          "total_replies": len(replies),
          "fresh_records": len(fresh),
          "done_videos": len(done),
          "texts_sample": [t[:120] for t in texts[:3]]})

    result = {"version": "v2-010d-reconciliation-v1",
              "checkpoint": "V2010D_P5_RECONCILIATION",
              "reconciled_at": utcnow(),
              "release_utc": RELEASE_UTC + "Z",
              "fresh_records": fresh,
              "done_videos": done,
              "credit_texts": [t for t in texts
                               if "クレジット" in t or "credit" in t.lower()]}
    urls = {r["video_download_url"] for r in done}
    if len(urls) == 1:
        video_url = urls.pop()
        assets = PKG / "assets"
        dest = assets / "f2b010d_recovered.mp4"
        try:
            meta = await adapter.download(video_url, dest)
        except Exception as error:
            await adapter.close(sanitize_to=None)
            result["status"] = "RECONCILIATION_DOWNLOAD_FAILED"
            result["reason"] = type(error).__name__
            (PKG / "V2_010D_RECONCILIATION.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": result["status"]})
            return 1
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        result.update({
            "status": "RESOLVED_EFFECT_IDENTIFIED",
            "asset": {"path": str(dest), "sha256": sha,
                      "host": video_url.split("/")[2], **meta},
            "creation_ids": sorted({r["creation_id"] for r in done}),
            "message_ids": sorted({r["message_id"] for r in done})})
        auth.record_knowledge("RESOLVED_EFFECT_IDENTIFIED",
                              "the released F2B_010D request produced a "
                              "completed video (read-only reconciliation)")
    elif done or fresh:
        result["status"] = "RESOLVED_PARTIAL_NO_SINGLE_URL"
        auth.record_knowledge("RESOLVED_EFFECT_IDENTIFIED",
                              "provider effect observed but correlation "
                              "not single-valued")
    else:
        refusal_texts = [t for t in texts
                         if "クレジット" in t or "credit" in t.lower()]
        if refusal_texts:
            result["status"] = "RESOLVED_NO_EFFECT_PROVIDER_REFUSED"
            result["refusal_text"] = refusal_texts[0][:300]
        else:
            result["status"] = "UNRESOLVED_NO_NEW_RECORDS"
        auth.record_knowledge("RESOLVED_NO_EFFECT"
                              if refusal_texts else "UNKNOWN",
                              json.dumps(refusal_texts)[:250])
    await adapter.close(sanitize_to=PKG / "V2_010D_RECON_CAPTURE_SANITIZED.json")
    result["completed_at"] = utcnow()
    (PKG / "V2_010D_RECONCILIATION.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    emit({"checkpoint": "V2010D_RECONCILIATION_DONE",
          "status": result["status"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
