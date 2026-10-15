"""V2-021 — read-only provider-side recovery for interrupted-run shots.

The per-shot dispatch journals of the interrupted run were overwritten by
later interrupted attempts (reservation-only), so the V2-020 reconcile
tool (which requires a durable NETWORK_RELEASE_OBSERVED in the current
journal) cannot bind them. This tool recovers the provider-side truth
read-only:

  scan <account> [<account> ...]
      For each account: discover recent conversations that contain a
      frozen shot's unique motion needle; list completed creations
      (type-2, download_url) with message timestamps. No downloads.

  bind <shot> <account> <conversation_id> [--expect-sha256 H]
       [--dest PATH] [--note TEXT]
      Re-locate the needle conversation, resolve the provider-issued
      variant exactly like the dispatch flow (never the bare URL when a
      deep variant exists), download allowlisted to a candidate file,
      verify the optional expected SHA-256, atomically place the asset
      and write recover_<shot>.json evidence.

NO dispatch, NO composer interaction, NO POST. Read-only surface only:
the same /im/chain fetches the page itself uses.
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

from dola_010c_session import DolaSessionManager  # noqa: E402
from dola_010e_session_router import ACCOUNT_PROFILES  # noqa: E402
from film_pipeline.providers.dola_production import (  # noqa: E402
    DolaAssetVariantResolver)
from film_pipeline.providers.dola_production.observability import (  # noqa: E402
    decode_media_url)
from film_pipeline.providers.dola_production.variants import (  # noqa: E402
    _host_allowed, extract_renditions)
from v2_020_runner import (CONSENT_DISMISS_JS, PULL_RAW_JS,  # noqa: E402
                           RECENT_CONVS_JS, REFUSAL_MARKERS,
                           download_allowlisted, emit, utcnow)

PKG = ROOT / "projects/quality_v2_021_narrative_compiler"
_PKG_PROFILES = PKG / "pool_profiles"
COMP = json.loads((PKG / "V2_021_FIXTURE_COMPILATION_5SHOT.json")
                  .read_text(encoding="utf-8"))
SHOT_IDS = [n["shot_id"] for n in COMP["shot_graph"]["nodes"]]


def profile_root(alias: str) -> Path:
    return _PKG_PROFILES if alias in ("ACCOUNT_E", "ACCOUNT_F") \
        else ACCOUNT_PROFILES


def needle_for(shot_id: str) -> str:
    return COMP["prompt_plans"][shot_id]["sections"]["motion"][:80]


async def _open(alias: str):
    manager = DolaSessionManager(profile_dir=profile_root(alias) / alias)
    page = await manager.launch_browser()
    await page.goto("https://www.dola.com/chat", timeout=60000,
                    wait_until="domcontentloaded")
    try:
        await page.evaluate(CONSENT_DISMISS_JS)
    except Exception:
        pass
    for _ in range(15):
        ok = await page.evaluate(
            "() => !!(document.querySelector('textarea') || "
            "document.querySelector('[contenteditable=\"true\"]'))")
        if ok:
            break
        await page.wait_for_timeout(2000)
    return manager, page


def _done_from_rows(rows: list[dict]) -> list[dict]:
    done = []
    for row in rows:
        for c in row.get("creations", []):
            if c.get("type") == 2 and c.get("download_url") and c.get("id"):
                done.append({
                    "id": str(c["id"]),
                    "status": c.get("status"),
                    "download_url": c.get("download_url"),
                    "video_model_raw": c.get("video_model_raw"),
                    "message_id": row.get("message_id"),
                    "create_time": row.get("create_time"),
                })
    return done


def _refusal(rows: list[dict]) -> bool:
    return any(m in (r.get("text") or "")
               for r in rows[:4] for m in REFUSAL_MARKERS)


async def scan(accounts: list[str]) -> int:
    result = {}
    for alias in accounts:
        entry = {"account": alias, "shots": {}}
        manager = None
        try:
            manager, page = await _open(alias)
            convs = await page.evaluate(RECENT_CONVS_JS)
            entry["recent_conversations"] = len(convs)
            for conv in convs[:10]:
                try:
                    rows = await page.evaluate(
                        PULL_RAW_JS, {"conversationId": conv})
                except Exception:
                    continue
                for sid in SHOT_IDS:
                    needle = needle_for(sid)
                    if not any(needle in (r.get("text") or "")
                               for r in rows):
                        continue
                    done = _done_from_rows(rows)
                    needle_rows = [{"message_id": r.get("message_id"),
                                    "create_time": r.get("create_time")}
                                   for r in rows
                                   if needle in (r.get("text") or "")]
                    urls = sorted({d["download_url"] for d in done})
                    entry["shots"].setdefault(sid, []).append({
                        "conversation_id": conv,
                        "needle_rows": needle_rows,
                        "done_creations": done,
                        "distinct_download_urls": len(urls),
                        "refusal": _refusal(rows),
                    })
            emit({"event": "account_scanned", "account": alias,
                  "hits": {s: len(v) for s, v in entry["shots"].items()}})
        except Exception as error:  # noqa: BLE001
            entry["error"] = f"{type(error).__name__}: {error}"[:200]
            emit({"event": "account_scan_failed", "account": alias,
                  "error": entry["error"]})
        finally:
            if manager is not None:
                try:
                    await manager.close()
                except Exception:
                    pass
        result[alias] = entry
    out = PKG / "V2_021_RECOVERY_SCAN.json"
    out.write_text(json.dumps({"scanned_at": utcnow(), "accounts": result},
                              indent=1, ensure_ascii=False),
                   encoding="utf-8")
    emit({"status": "SCAN_DONE", "path": str(out)})
    return 0


async def bind(shot_id: str, alias: str, conversation_id: str,
               expect_sha256: str | None, dest: str | None,
               note: str) -> int:
    needle = needle_for(shot_id)
    manager = None
    try:
        manager, page = await _open(alias)
        rows = await page.evaluate(PULL_RAW_JS,
                                   {"conversationId": conversation_id})
        if not any(needle in (r.get("text") or "") for r in rows):
            emit({"status": "NEEDLE_NOT_IN_CONVERSATION",
                  "shot": shot_id, "conversation": conversation_id})
            return 1
        done = _done_from_rows(rows)
        if not done:
            emit({"status": "NO_COMPLETED_CREATION", "shot": shot_id})
            return 1
        urls = {d["download_url"] for d in done}
        if len(urls) != 1:
            emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
                  "shot": shot_id, "distinct_urls": len(urls)})
            return 1
        newest = done[-1]
        creation_obj = {"id": newest.get("id"), "video": {
            "status": newest.get("status"),
            "download_url": newest.get("download_url"),
            "video_model": newest.get("video_model_raw")}}
        creation_id = newest.get("id")
        resolver = DolaAssetVariantResolver()
        selection = resolver.select(creation_obj)
        authority = selection.authority
        target_url = None
        if selection.variant is not None:
            for r in extract_renditions(creation_obj):
                if str(r.get("_list_key")) == selection.variant.list_key:
                    url = decode_media_url(r.get(selection.variant.field))
                    if url and _host_allowed(url):
                        target_url = url
                    break
        fallback = False
        if target_url is None and authority == "PROVIDER_ISSUED_UNWATERMARKED":
            emit({"status": "CLEAN_VARIANT_RESOLUTION_GAP",
                  "shot": shot_id, "creation": creation_id})
            return 1
        if target_url is None:
            target_url = urls.pop()
            authority = "PROVIDER_ISSUED_WATERMARKED"
            fallback = True
        dest_path = Path(dest) if dest else PKG / "assets" / f"{shot_id}.mp4"
        candidate = dest_path.with_suffix(".mp4.recover-candidate")
        total = download_allowlisted(target_url, candidate)
        sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if expect_sha256 and sha != expect_sha256.lower():
            emit({"status": "SHA_MISMATCH", "shot": shot_id,
                  "expected": expect_sha256.lower(), "actual": sha,
                  "candidate_kept": str(candidate)})
            return 1
        if dest_path.exists() and not expect_sha256:
            emit({"status": "DEST_EXISTS_REFUSED", "dest": str(dest_path)})
            candidate.unlink(missing_ok=True)
            return 1
        import os as _os
        _os.replace(candidate, dest_path)
        evidence = {
            "version": "v2-021-recovery-bind-v1",
            "shot_id": shot_id, "account": alias,
            "conversation_id": conversation_id,
            "creation_ids": [d["id"] for d in done],
            "bound_creation_id": creation_id,
            "asset_path": str(dest_path), "sha256": sha, "size": total,
            "authority": authority, "watermarked_fallback": fallback,
            "selection_reason": selection.reason,
            "download_host": target_url.split("/")[2],
            "expected_sha256": expect_sha256,
            "method": note or ("read-only provider-side bind: needle "
                               "conversation + single completed creation; "
                               "per-attempt journal was overwritten by a "
                               "later interrupted attempt"),
            "bound_at": utcnow(),
        }
        (PKG / f"recover_{shot_id}.json").write_text(
            json.dumps(evidence, indent=1, ensure_ascii=False),
            encoding="utf-8")
        emit({"status": "BOUND", "shot": shot_id, "sha256": sha,
              "authority": authority, "fallback": fallback,
              "size": total, "asset_path": str(dest_path)})
        return 0
    finally:
        if manager is not None:
            try:
                await manager.close()
            except Exception:
                pass


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "scan":
        return asyncio.run(scan(args[1:]))
    if args[0] == "bind":
        shot_id, alias, conv = args[1], args[2], args[3]
        expect, dest, note = None, None, ""
        rest = args[4:]
        i = 0
        while i < len(rest):
            if rest[i] == "--expect-sha256":
                expect = rest[i + 1]
                i += 2
            elif rest[i] == "--dest":
                dest = rest[i + 1]
                i += 2
            elif rest[i] == "--note":
                note = rest[i + 1]
                i += 2
            else:
                print(f"unknown option {rest[i]}")
                return 2
        return asyncio.run(bind(shot_id, alias, conv, expect, dest, note))
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
