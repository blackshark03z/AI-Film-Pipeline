import asyncio
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_dispatch_journal import (
    ASSET_DOWNLOADED, CREATION_BOUND, TERMINAL_SUCCESS, DispatchJournal
)
from film_pipeline.providers.dola_production import DolaAssetVariantResolver
from film_pipeline.providers.dola_production.observability import decode_media_url
from film_pipeline.providers.dola_production.variants import _host_allowed, extract_renditions
from v2_020_runner import PULL_RAW_JS, download_allowlisted, technical_qc, extract_frames
from run_s08_unknown_quota_trial import (
    PRIMARY_ROOT, PRIMARY_ASSETS, generate_contact_sheet, generate_s01_s08_preview, save_json
)

ISOLATED_DIR = ROOT / "isolated_s08_candidate_002"
REVIEW_DIR = ROOT / "OWNER_REVIEW/FILM120_S08_CANDIDATE_002"
PROFILE_DIR = PRIMARY_ROOT / "projects/quality_v2_010e_final_f2b/runtime/account_profiles/ACCOUNT_A"
CONVERSATION_ID = "38418286049107729"

async def reconcile_and_package():
    print(f"[RECONCILE] Connecting read-only to Dola conversation {CONVERSATION_ID}...")
    manager = DolaSessionManager(profile_dir=PROFILE_DIR)
    try:
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(4)
        rows = await page.evaluate(PULL_RAW_JS, {"conversationId": CONVERSATION_ID})
        print(f"[RECONCILE] Fetched {len(rows)} messages in conversation.")
    finally:
        await manager.close()

    creation = None
    for r in rows:
        creations = r.get("creations") or []
        for c in creations:
            if c.get("id") and c.get("type") == 2:
                creation = c
                break
        if creation:
            break

    if not creation:
        raise RuntimeError(f"No type-2 creation found in conversation {CONVERSATION_ID}")

    creation_id = str(creation.get("id"))
    video_model_raw = creation.get("video_model_raw")
    download_url = creation.get("download_url")

    print(f"[RECONCILE] Found Creation ID: {creation_id}")
    print(f"[RECONCILE] Video Model Raw: {bool(video_model_raw)}")

    creation_obj = {
        "id": creation_id,
        "video": {
            "status": creation.get("status"),
            "download_url": download_url,
            "video_model": video_model_raw if isinstance(video_model_raw, str) else json.dumps(video_model_raw or {})
        }
    }

    resolver = DolaAssetVariantResolver()
    selection = resolver.select(creation_obj)
    variant_authority = selection.authority
    print(f"[RECONCILE] Variant Authority: {variant_authority}")

    target_url = None
    if selection.variant is not None:
        for r in extract_renditions(creation_obj):
            if str(r.get("_list_key")) == selection.variant.list_key:
                url = decode_media_url(r.get(selection.variant.field))
                if url and _host_allowed(url):
                    target_url = url
                    print(f"[RECONCILE] Selected unwatermarked rendition URL")
                break

    if target_url is None:
        target_url = download_url
        print(f"[RECONCILE] Fallback to primary download_url")

    # 1. Download asset to isolated_dir/assets/S08.mp4
    assets_dir = ISOLATED_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_file = assets_dir / "S08.mp4"

    print(f"[RECONCILE] Downloading allowlisted media to {asset_file}...")
    total_bytes = download_allowlisted(target_url, asset_file)
    asset_sha = hashlib.sha256(asset_file.read_bytes()).hexdigest()
    print(f"[RECONCILE] Download complete: {total_bytes} bytes, SHA256={asset_sha}")

    # 2. Extract frames & technical QC
    frames_dir = ISOLATED_DIR / "frames" / "S08"
    frames_extracted = extract_frames(asset_file, frames_dir)
    tech = technical_qc(asset_file, frames_dir)
    tech["frames_extracted"] = frames_extracted
    print(f"[RECONCILE] Technical QC: {tech}")

    # 3. Copy to OWNER_REVIEW
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    review_mp4 = REVIEW_DIR / "S08.mp4"
    review_mp4.write_bytes(asset_file.read_bytes())
    sheet_path = REVIEW_DIR / "S08_contact_sheet.png"
    generate_contact_sheet(frames_dir, sheet_path)
    print(f"[RECONCILE] Contact sheet generated at {sheet_path}")

    # 4. Generate S01-S08 Preview
    preview_mp4 = REVIEW_DIR / "S01_S08_PREVIEW.mp4"
    preview_ok = generate_s01_s08_preview(review_mp4, preview_mp4)
    print(f"[RECONCILE] S01-S08 preview generated ({preview_ok}) at {preview_mp4}")

    # 5. Manifest
    manifest = {
        "version": "v2-022-s08-candidate-manifest-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shot_id": "S08",
        "account": "ACCOUNT_A",
        "conversation_id": CONVERSATION_ID,
        "creation_id": creation_id,
        "asset_sha256": asset_sha,
        "asset_size": total_bytes,
        "variant_authority": variant_authority,
        "technical_qc": tech,
        "preview_ok": preview_ok,
        "preview_path": str(preview_mp4) if preview_ok else None,
        "reconciled": True,
    }
    save_json(REVIEW_DIR / "MANIFEST.json", manifest)

    # 6. Update journal with reconciliation events
    journal_path = ISOLATED_DIR / "dispatch_journal_S08.jsonl"
    journal = DispatchJournal(journal_path, "")
    journal.append(CREATION_BOUND, {
        "creation_ids": [creation_id],
        "conversation_id": CONVERSATION_ID,
        "reconciled": True
    })
    journal.append(ASSET_DOWNLOADED, {
        "sha256": asset_sha,
        "size": total_bytes
    })
    journal.append(TERMINAL_SUCCESS, {
        "sha256": asset_sha
    })
    print(f"[RECONCILE] Journal updated with CREATION_BOUND, ASSET_DOWNLOADED, TERMINAL_SUCCESS")

    # 7. Update s08_trial_state.json
    state_path = ISOLATED_DIR / "s08_trial_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "REVIEW_READY"
    state["conversation"] = CONVERSATION_ID
    state["creation_ids"] = [creation_id]
    state["asset"] = str(asset_file)
    state["sha256"] = asset_sha
    state["variant_authority"] = variant_authority
    state["technical"] = tech
    state["reconciled"] = True
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_json(state_path, state)
    print(f"[RECONCILE] Trial state updated to REVIEW_READY with full technical QC")
    print(f"[RECONCILE] SUCCESS! All artifacts packaged cleanly.")

if __name__ == "__main__":
    asyncio.run(reconcile_and_package())
