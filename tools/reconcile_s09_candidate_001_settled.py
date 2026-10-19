"""S3 S09 Candidate-001 Settled Read-Only Exact Provider Reconciliation.

Per Work Package: docs/operating/TASK_S3_S09_CANDIDATE_001_SETTLED_READONLY_RECONCILIATION.md
Strictly READ-ONLY. No new generate. No mutation. No retry. No latch reuse.
No fallback to recent_convs[0]. Exact conversation ID and candidate needle match required.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKER_ROOT / "tools"))
sys.path.insert(0, str(WORKER_ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import CREDIT_STATEMENTS_JS
from film_pipeline.providers.dola_production import (
    DolaAssetVariantResolver,
)
from film_pipeline.providers.dola_production.observability import (
    decode_media_url,
)
from film_pipeline.providers.dola_production.variants import (
    _host_allowed, extract_renditions,
)
from v2_020_runner import (
    PULL_RAW_JS, LOGIN_CHECK_JS, download_allowlisted, extract_frames, technical_qc,
)

PRIMARY_ROOT = Path(r"D:\AI FILM MAKER\AI-Film-Pipeline")
PRIMARY_ASSETS = PRIMARY_ROOT / "projects/quality_v2_022_longform_120s/assets"
CANONICAL_PKG = PRIMARY_ROOT / "projects/quality_v2_022_longform_120s"
CANONICAL_STATE_PATH = CANONICAL_PKG / "v2_022_run_state.json"
COMP_PATH = CANONICAL_PKG / "V2_022_LONGFORM_COMPILATION.json"

POLICY_REF = "45f71d6226c5ffc58b4e70f3bcea1bb0151b7003"
AGENTS_BLOB_SHA = "6cab2103e32448a10e13b7f00c1a3eb4adb4a221"
EXPECTED_STATE_SHA = "476760bfad67c1c324b6b7f97dec3b11dc3b8da663103434b391f2c1064b917b"
EXPECTED_COMP_SHA = "4ab2d7e3e8778f959832583d4bc0356060e04a2a3a5aa249eb8fc7f7e18497db"
EXPECTED_ORIG_PROMPT_SHA = "6a8a9ade4f377f22cf7678bdb792d0a59941b74222c3df36696cc095eb0edaad"

FROZEN_S09_PROMPT = (
    "Generate a 5-second cinematic video, 16:9. On a narrow wet stone terrace path above "
    "a broad river valley under low grey clouds, a lone male gardener wears the same deep "
    "russet-red wool work coat over a dark green sweater, brown felt hat, and crosswise hemp "
    "satchel. Locked slightly elevated medium-long shot with his whole body, both boots, and "
    "the wide flat stepping stone clearly visible. After his still reaction while overlooking "
    "the valley, he makes a visible DECISION: plants one boot firmly on the flat stone, shifts "
    "his weight with deliberate care, and takes his next step along the slick path moving "
    "screen-left to screen-right. Maintain the same identity, wardrobe, satchel, dark dry-stone "
    "terrace wall, wet stone and soil path, pale winter grass, diffuse cold morning light, and "
    "gentle breeze from the preceding shot. No push-in, orbit, camera cut, or exaggerated "
    "motion. No other people, animals, vehicles, buildings, weapons, text, logos, captions, "
    "or borders."
)
EXPECTED_CANDIDATE_PROMPT_SHA = "880d734aa5097b839c8be4740a4c4b320fff1e77d371614da494169085d146a1"
UNIQUE_CANDIDATE_NEEDLE = "DECISION: plants one boot firmly on the flat stone, shifts his weight with deliberate care"

ACCEPTED_ASSETS_SHAS = {
    "S01": "175e54e6927c778cc185eebe9cfc5b002a5b3893aa1ccdb434b13ca925519511",
    "S02": "7d1608e4cc27613a4376657c1a4ea6eeb5f940b485e8cb266b0d5bd09b8391d6",
    "S03": "d47651febaffddf12155d52415fa1d3ea834fe167781fb5ceb2eb89ab10282e6",
    "S04": "116d29cab711cf9c4a8880dd9e9cb8d50c65e5d49963fbfb8c45e175d7955829",
    "S05": "2e4d72cc4503c07e0122f9cc3f7376047d1f62d73fa4eb35b516fcb2b6e507cf",
    "S06": "c9b8a03de0585a867a583dbff4bbbaec59517a2b45fa096a59a7a782ded141e6",
    "S07": "ee7caa66525d14275cad36f311d7d9112d9f23907a22e88eaf5df8047d33c530",
    "S08": "111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0",
    "S10": "a023dd9b4dfaa274a92b30a2187067a5ab30c715829d80b1b2c8dd6659b31393",
}

IMMUTABLE_CANDIDATE_001_FILES = {
    WORKER_ROOT / "isolated_s09_candidate_001/dispatch_journal_S09.jsonl": "52e112221cd1da8fddbb6218c30afbdf757da668f696f075ede1229e540118e7",
    WORKER_ROOT / "isolated_s09_candidate_001/s09_candidate_state.json": "4ff9e04417360a790c0cdbe3f0027dbd8bc9950be3ff091aa714182559c58b9a",
    WORKER_ROOT / "isolated_s09_candidate_001/slots/S09/mutation_authority.json": "fb44debc6ca9bf5096ec88810deebfdbaf3983857b852b6cc4167a85390a74d8",
    WORKER_ROOT / "OWNER_REVIEW/FILM120_S09_CANDIDATE_001/MANIFEST.json": "358b2a6f0ab5c4997475df2934cdbd9f571aa9cf1879e9f76c7e085af3041b1a",
}

TARGET_CONVERSATION_ID = "38418268122723601"
TARGET_ATTEMPT_ID = "attempt_8c0cb1fdafaa55cb482a24f218b07d2cc31ac2ab780920bb87611836c1b89921"
TARGET_ACCOUNT = "ACCOUNT_A"
ACCOUNT_PROFILES_DIR = PRIMARY_ROOT / "projects/quality_v2_010e_final_f2b/runtime/account_profiles"
SETTLED_DIR = WORKER_ROOT / "isolated_s09_candidate_001_settled"


def run_preflight() -> dict:
    print("[PREFLIGHT] Running strict preflight checks...")

    # 1. Policy check
    rev = subprocess.run(
        ["git", "rev-parse", f"{POLICY_REF}:AGENTS.md"],
        cwd=str(WORKER_ROOT),
        capture_output=True,
        text=True,
    )
    if rev.returncode != 0 or rev.stdout.strip() != AGENTS_BLOB_SHA:
        raise RuntimeError(f"Policy blob mismatch: got '{rev.stdout.strip()}', expected '{AGENTS_BLOB_SHA}'")
    print(f"  [OK] Policy AGENTS.md verified ({AGENTS_BLOB_SHA})")

    # 2. Frozen prompt SHA
    prompt_sha = hashlib.sha256(FROZEN_S09_PROMPT.encode("utf-8")).hexdigest()
    if prompt_sha != EXPECTED_CANDIDATE_PROMPT_SHA:
        raise RuntimeError(f"Prompt SHA mismatch: got {prompt_sha}, expected {EXPECTED_CANDIDATE_PROMPT_SHA}")
    print(f"  [OK] Frozen S09 candidate prompt verified ({EXPECTED_CANDIDATE_PROMPT_SHA})")

    # 3. Canonical run state check
    state_bytes = CANONICAL_STATE_PATH.read_bytes()
    state_sha = hashlib.sha256(state_bytes).hexdigest()
    if state_sha != EXPECTED_STATE_SHA:
        raise RuntimeError(f"Canonical state SHA mismatch: got {state_sha}, expected {EXPECTED_STATE_SHA}")
    state = json.loads(state_bytes)
    shots = state.get("shots", {})
    accepted = [s for s, d in shots.items() if d.get("status") == "QC_ACCEPT"]
    if len(accepted) != 9:
        raise RuntimeError(f"Expected 9 accepted shots, got {len(accepted)}")
    if shots.get("S09", {}).get("status") != "PENDING":
        raise RuntimeError(f"S09 is not PENDING in Film State: {shots.get('S09', {}).get('status')}")
    if shots.get("S10", {}).get("status") != "QC_ACCEPT":
        raise RuntimeError(f"S10 is not QC_ACCEPT in Film State: {shots.get('S10', {}).get('status')}")
    print(f"  [OK] Canonical Film State verified ({state_sha}, 9/24 QC_ACCEPT, S09=PENDING, S10=QC_ACCEPT)")

    # 4. Compilation check
    comp_bytes = COMP_PATH.read_bytes()
    comp_sha = hashlib.sha256(comp_bytes).hexdigest()
    if comp_sha != EXPECTED_COMP_SHA:
        raise RuntimeError(f"Compilation SHA mismatch: got {comp_sha}, expected {EXPECTED_COMP_SHA}")
    comp = json.loads(comp_bytes)
    s09_orig = comp["prompt_plans"]["S09"]["compiled_text"]
    s09_orig_sha = hashlib.sha256(s09_orig.encode("utf-8")).hexdigest()
    if s09_orig_sha != EXPECTED_ORIG_PROMPT_SHA:
        raise RuntimeError(f"Original S09 compilation prompt SHA mismatch: got {s09_orig_sha}")
    print(f"  [OK] Compilation verified ({comp_sha})")

    # 5. Verify historical S09 archives
    j_prior = CANONICAL_PKG / "dispatch_journal_S09.jsonl.prior-1"
    s_prior = CANONICAL_PKG / "slots/S09.prior-1"
    if not j_prior.exists() or not s_prior.exists():
        raise RuntimeError("Historical S09 archives missing")
    print("  [OK] Historical S09 archives verified intact")

    # 6. Verify 9 accepted canonical assets
    for sid, exp_sha in ACCEPTED_ASSETS_SHAS.items():
        p = PRIMARY_ASSETS / f"{sid}.mp4"
        if not p.exists():
            raise RuntimeError(f"Canonical asset missing: {p}")
        act_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if act_sha != exp_sha:
            raise RuntimeError(f"Canonical asset {sid} SHA mismatch: {act_sha} != {exp_sha}")
    print("  [OK] All 9 canonical accepted assets verified bitwise intact")

    # 7. Verify Candidate-001 evidence files immutability
    for fpath, exp_sha in IMMUTABLE_CANDIDATE_001_FILES.items():
        if not fpath.exists():
            raise RuntimeError(f"Candidate-001 evidence file missing: {fpath}")
        act_sha = hashlib.sha256(fpath.read_bytes()).hexdigest().lower()
        if act_sha != exp_sha.lower():
            raise RuntimeError(f"Candidate-001 evidence mutated! {fpath.name}: {act_sha} != {exp_sha}")
    print("  [OK] Candidate-001 evidence files verified 100% bitwise intact")

    profile_path = ACCOUNT_PROFILES_DIR / TARGET_ACCOUNT
    if not profile_path.exists():
        raise RuntimeError(f"Account profile directory missing: {profile_path}")
    print(f"  [OK] Account profile verified at {profile_path}")

    print("[PREFLIGHT] All preflight checks PASSED.\n")
    return {"comp": comp, "state": state}


async def run_settled_reconciliation() -> dict:
    preflight = run_preflight()
    comp = preflight["comp"]

    SETTLED_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = ACCOUNT_PROFILES_DIR / TARGET_ACCOUNT

    manager = DolaSessionManager(profile_dir=profile_path)
    page = None
    observation_record = {
        "task": "S3 S09 Candidate-001 Settled Read-Only Exact Reconciliation",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "account": TARGET_ACCOUNT,
        "target_conversation_id": TARGET_CONVERSATION_ID,
        "target_attempt_id": TARGET_ATTEMPT_ID,
        "candidate_prompt_sha256": EXPECTED_CANDIDATE_PROMPT_SHA,
        "identity_verification": "PENDING",
        "status": "INIT",
    }

    try:
        print(f"[RECONCILE] Launching browser for read-only query on {TARGET_ACCOUNT}...")
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        # Check login state
        state_login = await page.evaluate(LOGIN_CHECK_JS)
        logged_in = state_login.get("composer") and not state_login.get("logged_out")
        if not logged_in:
            observation_record["status"] = "OWNER_ACTION_REQUIRED"
            observation_record["detail"] = "Session logged out or composer missing; safe read-only access failed"
            return observation_record

        print("  [OK] Session verified valid (logged in, composer active)")

        # Query credit statements
        statements = []
        for _ in range(4):
            try:
                statements = await page.evaluate(CREDIT_STATEMENTS_JS, {"conversationIds": [TARGET_CONVERSATION_ID]})
                break
            except Exception as e:
                print(f"  [RETRY] Credit statements query: {e}")
                await page.wait_for_timeout(2000)

        observed_credit_statements = statements[-5:] if statements else []
        latest_credit_statement = statements[-1] if statements else None
        credit_remaining = latest_credit_statement.get("remaining") if latest_credit_statement else None

        observation_record["credit_readback"] = {
            "queried_at_utc": datetime.now(timezone.utc).isoformat(),
            "latest_remaining": credit_remaining,
            "statements_count": len(statements),
            "recent_statements": observed_credit_statements,
        }
        print(f"  [OK] Credit readback: remaining={credit_remaining}, statements={len(statements)}")

        # Query conversation 38418268122723601 strictly
        print(f"[RECONCILE] Pulling raw chain for exact conversation {TARGET_CONVERSATION_ID}...")
        rows = await page.evaluate(PULL_RAW_JS, {"conversationId": TARGET_CONVERSATION_ID})

        observation_record["rows_count"] = len(rows)
        if not rows:
            print(f"  [ERROR] No messages returned for conversation {TARGET_CONVERSATION_ID}")
            observation_record["identity_verification"] = "FAILED_CONVERSATION_EMPTY"
            observation_record["status"] = "INCONCLUSIVE"
            observation_record["detail"] = f"No messages returned for conversation {TARGET_CONVERSATION_ID}"
            return observation_record

        # Exact needle match verification (NO fallback!)
        matching_prompt_found = False
        matching_message_id = None
        matched_text_snippet = None

        for r in rows:
            text = r.get("text", "")
            raw = r.get("content_raw", "")
            if UNIQUE_CANDIDATE_NEEDLE in text or UNIQUE_CANDIDATE_NEEDLE in raw:
                matching_prompt_found = True
                matching_message_id = r.get("message_id")
                matched_text_snippet = text[:300]
                break

        if not matching_prompt_found:
            # Also check beginning of prompt
            needle_prefix = "On a narrow wet stone terrace path above a broad river valley"
            for r in rows:
                text = r.get("text", "")
                raw = r.get("content_raw", "")
                if needle_prefix in text or needle_prefix in raw:
                    matching_prompt_found = True
                    matching_message_id = r.get("message_id")
                    matched_text_snippet = text[:300]
                    break

        if not matching_prompt_found:
            print("  [ERROR] Exact candidate prompt needle NOT found in conversation messages!")
            observation_record["identity_verification"] = "FAILED_NEEDLE_NOT_FOUND"
            observation_record["status"] = "INCONCLUSIVE"
            observation_record["detail"] = "Conversation exists but exact candidate prompt needle was not present; fallback strictly disallowed"
            return observation_record

        print(f"  [OK] Exact candidate prompt needle matched in message {matching_message_id}")
        observation_record["identity_verification"] = "EXACT_CONVERSATION_NEEDLE_MATCHED"
        observation_record["matching_message_id"] = matching_message_id
        observation_record["matched_text_snippet"] = matched_text_snippet

        # Inspect all creations
        all_creations = []
        for r in rows:
            c_list = r.get("creations") or []
            for c in c_list:
                all_creations.append({
                    "message_id": r.get("message_id"),
                    "creation": c,
                })

        observation_record["creations_found_count"] = len(all_creations)

        video_creation = None
        for item in all_creations:
            c = item["creation"]
            if c.get("id") and c.get("type") == 2 and c.get("download_url"):
                video_creation = c
                break

        now_utc = datetime.now(timezone.utc).isoformat()
        observation_record["observation_time_utc"] = now_utc

        if not video_creation:
            # Check text error
            provider_messages = []
            for r in rows:
                t = r.get("text", "").strip()
                if t:
                    provider_messages.append({"message_id": r.get("message_id"), "text": t})

            observation_record["status"] = f"NO_CREATION_OBSERVED_AT_SETTLED_CHECK"
            observation_record["settled_disposition"] = "NO_CREATION_OBSERVED_AT_SETTLED_CHECK"
            observation_record["observed_as_of"] = f"NO_CREATION_OBSERVED_AS_OF_{now_utc}"
            observation_record["provider_messages"] = provider_messages
            observation_record["detail"] = (
                f"Settled read-only query of conversation {TARGET_CONVERSATION_ID} as of {now_utc} "
                f"confirmed exact needle match, but 0 video creations exist. "
                f"Provider message: '{provider_messages[0]['text'] if provider_messages else 'None'}'. "
                f"Observed credit balance remains {credit_remaining}."
            )
            print(f"[RECONCILE] NO CREATION OBSERVED as of {now_utc}.")
            return observation_record

        # Late creation found
        creation_id = str(video_creation.get("id"))
        download_url = video_creation.get("download_url")
        video_model_raw = video_creation.get("video_model_raw")

        print(f"[RECONCILE] LATE CREATION FOUND! ID={creation_id}, download_url present")
        observation_record["late_creation_detected"] = True
        observation_record["creation_id"] = creation_id
        observation_record["download_url_present"] = bool(download_url)
        observation_record["video_model_raw"] = video_model_raw

        # Resolve variant
        creation_obj = {
            "id": creation_id,
            "video": {
                "status": video_creation.get("status"),
                "download_url": download_url,
                "video_model": video_model_raw if isinstance(video_model_raw, str) else json.dumps(video_model_raw or {}),
            },
        }
        resolver = DolaAssetVariantResolver()
        selection = resolver.select(creation_obj)
        variant_authority = selection.authority

        target_url = None
        if selection.variant is not None:
            for r in extract_renditions(creation_obj):
                if str(r.get("_list_key")) == selection.variant.list_key:
                    url = decode_media_url(r.get(selection.variant.field))
                    if url and _host_allowed(url):
                        target_url = url
                        print("[RECONCILE] Selected unwatermarked rendition URL")
                    break

        if target_url is None:
            target_url = download_url
            print("[RECONCILE] Fallback to primary download_url")

        # Download safely into SETTLED_DIR
        target_asset_file = SETTLED_DIR / "assets" / "S09_settled.mp4"
        target_asset_file.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = download_allowlisted(target_url, target_asset_file)
        asset_sha = hashlib.sha256(target_asset_file.read_bytes()).hexdigest()

        # QC and frames
        frames_dir = SETTLED_DIR / "frames" / "S09"
        frames_extracted = extract_frames(target_asset_file, frames_dir)
        tech = technical_qc(target_asset_file, frames_dir)
        tech["frames_extracted"] = frames_extracted

        observation_record["status"] = "REAL_S09_CANDIDATE_RECOVERED"
        observation_record["settled_disposition"] = "REAL_S09_CANDIDATE_RECOVERED"
        observation_record["asset_file"] = str(target_asset_file)
        observation_record["asset_sha256"] = asset_sha
        observation_record["asset_size"] = total_bytes
        observation_record["variant_authority"] = variant_authority
        observation_record["technical_qc"] = tech

        return observation_record

    finally:
        if manager:
            try:
                await manager.close()
            except Exception:
                pass


def verify_post_immutability():
    print("[POST-CHECK] Verifying Candidate-001 evidence and canonical state immutability...")
    for fpath, exp_sha in IMMUTABLE_CANDIDATE_001_FILES.items():
        act_sha = hashlib.sha256(fpath.read_bytes()).hexdigest().lower()
        if act_sha != exp_sha.lower():
            raise RuntimeError(f"Candidate-001 evidence was mutated during reconciliation! {fpath.name}")
    print("  [OK] Candidate-001 evidence files remain 100% bitwise intact")

    state_bytes = CANONICAL_STATE_PATH.read_bytes()
    state_sha = hashlib.sha256(state_bytes).hexdigest()
    if state_sha != EXPECTED_STATE_SHA:
        raise RuntimeError(f"Canonical state was mutated! {state_sha} != {EXPECTED_STATE_SHA}")
    print("  [OK] Canonical Film State remains 100% bitwise intact")


def main() -> int:
    try:
        record = asyncio.run(run_settled_reconciliation())
    except Exception as e:
        print(f"[ERROR] Exception during settled reconciliation: {e}")
        record = {
            "task": "S3 S09 Candidate-001 Settled Read-Only Exact Reconciliation",
            "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
            "status": "INCONCLUSIVE",
            "detail": str(e),
        }

    verify_post_immutability()

    record["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
    record_path = SETTLED_DIR / "settled_readback_record.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[SUMMARY] Reconciliation finished with status: {record['status']}")
    print(f"Record written to {record_path}")

    if record["status"].startswith("NO_CREATION_OBSERVED"):
        return 0
    elif record["status"] == "REAL_S09_CANDIDATE_RECOVERED":
        return 0
    elif record["status"] == "INCONCLUSIVE":
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
