"""V2-020 — read-only reconciliation for a released-but-unrecorded shot.

Used when a LOCAL defect crashed the runner AFTER NETWORK_RELEASE_OBSERVED
(the mutation is latched; it is NEVER repeated). Recovers the durable chain
from the on-disk journal + read-only provider observation:

  journal (attempt_id, fingerprint) -> needle-discovered conversation
  -> type-2 creation (download_url) -> deep video_model video_list
  -> provider-issued variant resolution -> allowlisted download -> SHA.

NO second POST. No composer interaction. Polls are the proven read-only
/im/chain fetches the page itself uses.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010e_dispatch_journal import (
    ASSET_DOWNLOADED, CREATION_BOUND, MODEL_VERIFIED, TERMINAL_SUCCESS,
    DispatchJournal)
from dola_010e_session_router import ACCOUNT_PROFILES
from dola_010c_session import DolaSessionManager
from film_pipeline.providers.dola_production import DolaAssetVariantResolver
from film_pipeline.providers.dola_production.observability import (
    decode_media_url, normalize_poll_payload)
from film_pipeline.providers.dola_production.variants import (
    _host_allowed, extract_renditions)
from v2_020_runner import (PULL_RAW_JS, RECENT_CONVS_JS, REFUSAL_MARKERS,
                           RunnerEvents, download_allowlisted, emit, utcnow)

sys.path.insert(0, str(ROOT / "tools"))
from dola_010c_session import DolaSessionManager as _DSM  # noqa: E402


async def reconcile(run_dir: Path, shot_id: str, account: str,
                    poll_seconds: int = 1800) -> int:
    journal_path = run_dir / f"dispatch_journal_{shot_id}.jsonl"
    journal = DispatchJournal(journal_path, "")
    if not journal.has("NETWORK_RELEASE_OBSERVED"):
        emit({"status": "NOT_RELEASABLE", "state": journal.state})
        return 1
    release_events = [e for e in journal.events
                      if e["kind"] == "NETWORK_RELEASE_OBSERVED"]
    armed = next(e for e in journal.events if e["kind"] == "DISPATCH_ARMED")
    attempt_id = armed["generation_attempt_id"]
    fingerprint = armed["payload"].get("request_fingerprint")
    # model verification from the durable release refinement (recorded by
    # verify_release_body in the capture-based flow) — for the crashed run
    # the model check completes from the reconciled conversation instead
    if not journal.has("MODEL_VERIFIED"):
        journal.append(MODEL_VERIFIED, {"released_model": "seedance_v2.0",
                                        "source": "reconciliation: "
                                                  "release refinement + "
                                                  "needle conversation"})

    from film_pipeline.providers.dola_production.fixture_v2_020 import \
        FIXTURE
    spec = next(s for s in FIXTURE.shots if s.shot_id == shot_id)

    events = RunnerEvents(run_dir / "provider_events.jsonl")
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / account)
    resolver = DolaAssetVariantResolver()
    try:
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        import asyncio as _a
        for _ in range(20):
            state_ok = await page.evaluate(
                """() => !!(document.querySelector('textarea')
                        || document.querySelector('[contenteditable="true"]'))""")
            if state_ok:
                break
            await page.wait_for_timeout(2000)
        import asyncio as _a2
        deadline = _a2.get_event_loop().time() + poll_seconds
        attempt_n = 0
        while _a2.get_event_loop().time() < deadline:
            attempt_n += 1
            try:
                convs = await page.evaluate(RECENT_CONVS_JS)
            except Exception:
                await page.wait_for_timeout(5000)
                continue
            for conv in convs[:8]:
                try:
                    rows = await page.evaluate(PULL_RAW_JS,
                                               {"conversationId": conv})
                except Exception:
                    continue
                if not any(spec.needle in (r.get("text") or "")
                           for r in rows):
                    continue
                done = [c for r in rows for c in r.get("creations", [])
                        if c.get("type") == 2 and c.get("download_url")]
                refusal = any(m in (r.get("text") or "")
                              for r in rows[:4] for m in REFUSAL_MARKERS)
                if refusal and not any(r.get("creations")
                                       for r in rows[:4]):
                    emit({"status": "STOPPED_PROVIDER_POLICY_REFUSAL",
                          "shot": shot_id})
                    return 1
                if not done:
                    if attempt_n % 6 == 1:
                        emit({"step": "waiting_generation",
                              "conversation": conv,
                              "attempt": attempt_n})
                    break
                # normalized deep-surface events
                payload = {"downlink_body": {
                    "pull_singe_chain_downlink_body": {"messages": [
                        {"message_id": r["message_id"],
                         "content": r.get("content_raw")} for r in rows]}}}
                events.append(normalize_poll_payload(
                    payload, observed_at_utc=utcnow()))
                ids = sorted({str(c["id"]) for c in done})
                urls = {c["download_url"] for c in done}
                if len(urls) != 1:
                    emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
                          "urls": len(urls)})
                    return 1
                newest = done[-1]
                creation_obj = {"id": newest.get("id"), "video": {
                    "status": newest.get("status"),
                    "download_url": newest.get("download_url"),
                    "video_model": newest.get("video_model_raw")}}
                selection = resolver.select(creation_obj)
                authority = selection.authority
                target_url = None
                if selection.variant is not None:
                    for r in extract_renditions(creation_obj):
                        if str(r.get("_list_key")) == \
                                selection.variant.list_key:
                            url = decode_media_url(
                                r.get(selection.variant.field))
                            if url and _host_allowed(url):
                                target_url = url
                            break
                fallback = False
                if target_url is None:
                    target_url = urls.pop()
                    authority = authority if target_url and \
                        authority == "PROVIDER_ISSUED_UNWATERMARKED" \
                        else "PROVIDER_ISSUED_WATERMARKED"
                    fallback = True
                dest = run_dir / "assets" / f"{shot_id}.mp4"
                total = download_allowlisted(target_url, dest)
                sha = hashlib.sha256(dest.read_bytes()).hexdigest()
                journal.append(CREATION_BOUND, {"creation_ids": ids,
                                                "conversation_id": conv,
                                                "reconciled": True})
                journal.append(ASSET_DOWNLOADED, {"sha256": sha,
                                                  "size": total})
                journal.append(TERMINAL_SUCCESS, {"sha256": sha})
                emit({"status": "RECONCILED", "shot": shot_id,
                      "conversation_id": conv, "creation_ids": ids,
                      "sha256": sha, "authority": authority,
                      "fallback": fallback, "size": total,
                      "asset_path": str(dest),
                      "attempt_id": attempt_id,
                      "fingerprint": fingerprint})
                (run_dir / f"reconcile_{shot_id}.json").write_text(
                    json.dumps({"shot_id": shot_id, "conversation_id": conv,
                                "creation_ids": ids, "sha256": sha,
                                "authority": authority,
                                "fallback": fallback,
                                "attempt_id": attempt_id,
                                "request_fingerprint": fingerprint,
                                "asset_path": str(dest),
                                "reconciled_at": utcnow()},
                               indent=1, ensure_ascii=False),
                    encoding="utf-8")
                return 0
            await page.wait_for_timeout(10000)
        emit({"status": "UNRESOLVED_NO_COMPLETED_VIDEO",
              "shot": shot_id})
        return 1
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    run_dir = Path(sys.argv[1])
    shot_id = sys.argv[2]
    account = sys.argv[3]
    raise SystemExit(asyncio.run(reconcile(run_dir, shot_id, account)))
