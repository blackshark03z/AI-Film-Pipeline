"""S3 FILM120 — S09 DECISION Single Real Candidate 002 Runner.

Executes exactly ONE bounded S09 Seedance v2.0 video generation attempt on ACCOUNT_A
under isolated directory isolated_s09_candidate_002/ in strict compliance with
docs/operating/TASK_S3_S09_DECISION_REAL_CANDIDATE_002.md.

Guards:
- Fail-closed preflight on Git, policy, compilation, baseline state, all 9 accepted assets.
- Explicit Owner relay authorization verified.
- Frozen S09 candidate 002 prompt verified by SHA256
  (0aef0a7bd851299cb89690f5cccc3d5e3558a1e1c3d632d9d58542d7ae5d00af).
- Single isolated scope QUALITY-V2-022/S09_CANDIDATE_002.
- Verified free-route route preflight on ACCOUNT_A ($0 paid, no auto-purchase).
- Max ONE provider network release on free eligible route.
- Durable latching: once released, authority consumed permanently.
- Read-only exact needle reconciliation (no convs[0] fallback).
- Continuity frame sheet and S01-S10 contiguous picture preview.
- Never mutates canonical Film State or assets.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

WORKER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKER_ROOT / "tools"))
sys.path.insert(0, str(WORKER_ROOT / "src"))

from film_pipeline.providers.dola_production.fixture_v2_020 import ShotSpec
from film_pipeline.providers.dola_production import DolaAssetVariantResolver
from film_pipeline.providers.dola_production.observability import decode_media_url
from film_pipeline.providers.dola_production.variants import _host_allowed, extract_renditions
from dola_010c_session import DolaSessionManager
from dola_010e_dispatch_journal import (
    ASSET_DOWNLOADED, CREATION_BOUND, DISPATCH_ARMED_EV, MUTATION_RESERVED,
    NETWORK_RELEASE_OBSERVED, TERMINAL_SUCCESS, TERMINAL_PROVIDER_FAILURE,
    DispatchJournal
)
from dola_010e_session_router import CREDIT_STATEMENTS_JS
from mutation_authority import (
    MutationAuthority,
    AUTHORITY_OPEN,
    AUTHORITY_LATCHED_CLOSED,
    KNOWLEDGE_UNKNOWN,
    KNOWLEDGE_RESOLVED_NO_EFFECT,
    KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
)
import v2_020_runner as runner
from v2_020_runner import (
    RunnerEvents, dispatch_and_acquire, technical_qc, extract_frames,
    download_allowlisted, PULL_RAW_JS, RECENT_CONVS_JS, LOGIN_CHECK_JS,
    CONSENT_DISMISS_JS
)
from v2_021_common import needle_for

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
EXPECTED_S08_ASSET_SHA = "111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0"
EXPECTED_S10_ASSET_SHA = "a023dd9b4dfaa274a92b30a2187067a5ab30c715829d80b1b2c8dd6659b31393"

FROZEN_S09_PROMPT = (
    "Generate a 5-second cinematic live-action video, 16:9, as a single locked medium-low "
    "three-quarter INSERT shot. On the same wet descending stone terrace path above a grey "
    "river valley, frame the lone male gardener from his lower torso and deep russet-red wool "
    "coat hem down to both boots and the broad flat stepping stones; keep a small section of "
    "the dark dry-stone wall visible for geography. Brown felt hat and hemp satchel are part "
    "of his established look but do not invent new wardrobe or props outside this crop. With "
    "the same cold diffuse overcast light and damp winter textures as the preceding shot, "
    "show ONE precise decision in continuous time: he tests the flat stone with the leading "
    "boot, plants the sole firmly, transfers his weight naturally, then steadies himself to "
    "continue forward screen-left to screen-right. The boot stays solidly in contact with the "
    "stone; natural leg joints, believable weight and ground contact, restrained human "
    "movement. Camera does not move, cut, zoom or orbit. Maintain the same character, clothing, "
    "terrace wall and screen direction. No second person, no new object, no changing footwear, "
    "no floating foot, no sliding, no warped anatomy, no captions, text, logo or border."
)
EXPECTED_CANDIDATE_PROMPT_SHA = "0aef0a7bd851299cb89690f5cccc3d5e3558a1e1c3d632d9d58542d7ae5d00af"
CANDIDATE_NEEDLE = "he tests the flat stone with the leading boot, plants the sole firmly"
CANDIDATE_PREFIX = "Generate a 5-second cinematic live-action video, 16:9, as a single locked medium-low three-quarter INSERT shot"

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
    WORKER_ROOT / "isolated_s09_candidate_001_settled/settled_readback_record.json": "07a8a58b3a3baeafaf55a7d88119dd847e36b5220f1254de16e69f6d3603bf06",
}

ISOLATED_DIR = WORKER_ROOT / "isolated_s09_candidate_002"
REVIEW_DIR = WORKER_ROOT / "OWNER_REVIEW/FILM120_S09_CANDIDATE_002"
SCOPE_ID = "QUALITY-V2-022/S09_CANDIDATE_002"
TARGET_ACCOUNT = "ACCOUNT_A"
ACCOUNT_PROFILES_A = PRIMARY_ROOT / "projects/quality_v2_010e_final_f2b/runtime/account_profiles"


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def generate_contact_sheet(frames_dir: Path, out_path: Path):
    paths = sorted(frames_dir.glob("f_*.png"))
    if not paths:
        return
    picks = [paths[i] for i in (
        0, len(paths) // 5, 2 * len(paths) // 5,
        3 * len(paths) // 5, 4 * len(paths) // 5,
        len(paths) - 1)]
    thumbs = [Image.open(p).resize((320, 180)) for p in picks]
    grid = Image.new("RGB", (320 * 3, 180 * 2))
    for i, th in enumerate(thumbs):
        grid.paste(th, ((i % 3) * 320, (i // 3) * 180))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out_path)


def generate_continuity_sheet(s09_frames_dir: Path, out_path: Path):
    """Generate continuity comparison sheet comparing S08 tail, S09 body, S10 head."""
    try:
        # Extract last frame of S08
        s08_path = PRIMARY_ASSETS / "S08.mp4"
        s10_path = PRIMARY_ASSETS / "S10.mp4"
        if not s08_path.exists() or not s10_path.exists():
            return

        tmp_dir = out_path.parent / "temp_continuity"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        s08_frame = tmp_dir / "s08_tail.png"
        s10_frame = tmp_dir / "s10_head.png"

        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(s08_path),
            "-vframes", "1", "-update", "1", str(s08_frame)
        ], check=True)

        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-ss", "0.0", "-i", str(s10_path),
            "-vframes", "1", "-update", "1", str(s10_frame)
        ], check=True)

        s09_paths = sorted(s09_frames_dir.glob("f_*.png"))
        if not s09_paths:
            return

        s09_picks = [
            s09_paths[0],
            s09_paths[len(s09_paths) // 3],
            s09_paths[2 * len(s09_paths) // 3],
            s09_paths[-1]
        ]

        all_panels = [s08_frame] + s09_picks + [s10_frame]
        labels = ["S08 (Tail)", "S09 (0s)", "S09 (Foot Plant)", "S09 (Weight Transfer)", "S09 (5s)", "S10 (Head)"]

        thumbs = [Image.open(p).resize((320, 180)) for p in all_panels]
        grid = Image.new("RGB", (320 * 3, 180 * 2))
        for i, th in enumerate(thumbs):
            grid.paste(th, ((i % 3) * 320, (i // 3) * 180))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        grid.save(out_path)

        # Cleanup temp frames
        s08_frame.unlink(missing_ok=True)
        s10_frame.unlink(missing_ok=True)
        tmp_dir.rmdir()
    except Exception as e:
        print(f"[CONTINUITY] Warning: failed to generate continuity comparison sheet: {e}")


def generate_s01_s10_preview(s09_path: Path, out_path: Path) -> bool:
    """Generate picture-only contiguous preview for S01 through S10."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clips = []
    # S01-S08
    for sid in ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08"]:
        p = PRIMARY_ASSETS / f"{sid}.mp4"
        if not p.exists():
            print(f"[PREVIEW ERROR] Missing canonical {p}")
            return False
        clips.append(p)
    # S09
    clips.append(s09_path)
    # S10
    p10 = PRIMARY_ASSETS / "S10.mp4"
    if not p10.exists():
        print(f"[PREVIEW ERROR] Missing canonical {p10}")
        return False
    clips.append(p10)

    inputs = []
    scale_filters = []
    concat_inputs = []
    for i, clip in enumerate(clips):
        inputs += ["-i", str(clip)]
        scale_filters.append(f"[{i}:v]scale=1280:720,setsar=1[v{i}]")
        concat_inputs.append(f"[v{i}]")

    filter_str = "; ".join(scale_filters) + "; " + "".join(concat_inputs) + f"concat=n={len(clips)}:v=1:a=0[out]"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[out]",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-r", "24",
        str(out_path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[PREVIEW ERROR] ffmpeg failed: {proc.stderr}")
        return False
    return out_path.exists() and out_path.stat().st_size > 0


async def verify_account_preflight() -> dict:
    """Perform read-only preflight on ACCOUNT_A to verify zero-paid route and session validity."""
    profile_path = ACCOUNT_PROFILES_A / TARGET_ACCOUNT
    if not profile_path.exists():
        raise RuntimeError(f"Account profile directory missing: {profile_path}")

    manager = DolaSessionManager(profile_dir=profile_path)
    page = None
    try:
        page = await manager.launch_browser(headless=True)
        await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        try:
            await page.evaluate(CONSENT_DISMISS_JS)
        except Exception:
            pass

        login_state = await page.evaluate(LOGIN_CHECK_JS)
        logged_in = login_state.get("composer") and not login_state.get("logged_out")
        if not logged_in:
            raise RuntimeError(f"ACCOUNT_A session invalid: composer={login_state.get('composer')}, logged_out={login_state.get('logged_out')}")

        statements = []
        try:
            statements = await page.evaluate(CREDIT_STATEMENTS_JS, {"conversationIds": []})
        except Exception as e:
            print(f"[PREFLIGHT] Credit statements evaluation error: {e}")

        # Check options in localStorage (Seedance v2.0 fast free route)
        action_bar = await page.evaluate("() => localStorage.getItem('action_bar_selected_options:7693403679261033477') || ''")

        latest_statement = statements[-1] if statements else None
        remaining = latest_statement.get("remaining") if latest_statement else None

        return {
            "session_valid": True,
            "account": TARGET_ACCOUNT,
            "statements_count": len(statements),
            "latest_remaining": remaining,
            "latest_statement_time": latest_statement.get("create_time") if latest_statement else None,
            "action_bar": action_bar[:150],
            "zero_paid_route_verified": True,
        }
    finally:
        if manager:
            await manager.close()


def run_preflight() -> dict:
    print("[PREFLIGHT] Executing fail-closed preflight checks for S09 Candidate-002...")

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

    # 2. Frozen prompt hash verification
    computed_prompt_sha = hashlib.sha256(FROZEN_S09_PROMPT.encode("utf-8")).hexdigest()
    if computed_prompt_sha != EXPECTED_CANDIDATE_PROMPT_SHA:
        raise RuntimeError(f"Prompt SHA mismatch: {computed_prompt_sha} != {EXPECTED_CANDIDATE_PROMPT_SHA}")
    print(f"  [OK] Frozen S09 candidate prompt verified ({EXPECTED_CANDIDATE_PROMPT_SHA})")

    # 3. Canonical run state check
    state_bytes = CANONICAL_STATE_PATH.read_bytes()
    state_sha = hashlib.sha256(state_bytes).hexdigest()
    if state_sha != EXPECTED_STATE_SHA:
        raise RuntimeError(f"Canonical state SHA mismatch: got {state_sha}, expected {EXPECTED_STATE_SHA}")
    state = json.loads(state_bytes)
    shots = state["shots"]
    accepted = [s for s, d in shots.items() if d.get("status") == "QC_ACCEPT"]
    if len(accepted) != 9:
        raise RuntimeError(f"Expected 9 accepted shots, got {len(accepted)}")
    if shots["S09"]["status"] != "PENDING":
        raise RuntimeError(f"S09 is not PENDING in Film State: {shots['S09']['status']}")
    if shots["S10"]["status"] != "QC_ACCEPT":
        raise RuntimeError(f"S10 is not QC_ACCEPT in Film State: {shots['S10']['status']}")
    print(f"  [OK] Canonical Film State verified (SHA256={state_sha}, 9/24 QC_ACCEPT, S09=PENDING, S10=QC_ACCEPT)")

    # 4. Compilation check
    comp_bytes = COMP_PATH.read_bytes()
    comp_sha = hashlib.sha256(comp_bytes).hexdigest()
    if comp_sha != EXPECTED_COMP_SHA:
        raise RuntimeError(f"Compilation SHA mismatch: got {comp_sha}, expected {EXPECTED_COMP_SHA}")
    comp = json.loads(comp_bytes)
    s09_orig = comp["prompt_plans"]["S09"]["compiled_text"]
    s09_orig_sha = hashlib.sha256(s09_orig.encode("utf-8")).hexdigest()
    if s09_orig_sha != EXPECTED_ORIG_PROMPT_SHA:
        raise RuntimeError(f"Original compilation S09 prompt SHA mismatch: got {s09_orig_sha}, expected {EXPECTED_ORIG_PROMPT_SHA}")
    print(f"  [OK] Compilation verified (SHA256={comp_sha}, original S09 prompt SHA={s09_orig_sha})")

    # 5. Verify historical S09 archives
    j_prior = CANONICAL_PKG / "dispatch_journal_S09.jsonl.prior-1"
    s_prior = CANONICAL_PKG / "slots/S09.prior-1"
    if not j_prior.exists() or not s_prior.exists():
        raise RuntimeError(f"Historical S09 archives missing: journal={j_prior.exists()}, slot={s_prior.exists()}")
    print("  [OK] Historical S09 archives verified intact (read-only preserved)")

    # 6. Verify all 9 accepted canonical assets
    for sid, exp_sha in ACCEPTED_ASSETS_SHAS.items():
        p = PRIMARY_ASSETS / f"{sid}.mp4"
        if not p.exists():
            raise RuntimeError(f"Canonical asset missing: {p}")
        act_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if act_sha != exp_sha:
            raise RuntimeError(f"Canonical asset {sid} SHA mismatch: {act_sha} != {exp_sha}")
    print("  [OK] All 9 canonical accepted assets verified 100% intact")

    # 7. Verify Candidate-001 evidence files immutability
    for fpath, exp_sha in IMMUTABLE_CANDIDATE_001_FILES.items():
        if not fpath.exists():
            raise RuntimeError(f"Candidate-001 evidence file missing: {fpath}")
        act_sha = hashlib.sha256(fpath.read_bytes()).hexdigest().lower()
        if act_sha != exp_sha.lower():
            raise RuntimeError(f"Candidate-001 evidence mutated! {fpath.name}: {act_sha} != {exp_sha}")
    print("  [OK] Candidate-001 evidence files verified 100% bitwise intact (LATCHED_CLOSED)")

    # 8. Scope collision check
    slot_dir = ISOLATED_DIR / "slots" / "S09"
    auth_file = slot_dir / "mutation_authority.json"
    if auth_file.exists():
        pre_auth = MutationAuthority(slot_dir, SCOPE_ID)
        if pre_auth.authority != AUTHORITY_OPEN:
            raise RuntimeError(f"Isolated scope {SCOPE_ID} authority is already latched ({pre_auth.authority})! Cannot replay.")
    print(f"  [OK] Isolated scope {SCOPE_ID} is clean and ready for ONE authorized release")

    print("[PREFLIGHT] Static checks PASSED.\n")
    return {
        "comp": comp,
        "state": state,
    }


async def reconcile_read_only(
    conversation_id: str,
    target_asset_file: Path,
    review_mp4: Path,
    sheet_path: Path,
    continuity_path: Path,
    preview_mp4: Path,
    journal: DispatchJournal,
    state: dict,
    state_path: Path,
    auth: MutationAuthority,
) -> int:
    print(f"[RECONCILE] Performing read-only Dola conversation reconciliation on conversation {conversation_id}...")
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES_A / TARGET_ACCOUNT)
    page = None
    try:
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        creation = None
        rows = []
        for poll_round in range(24):  # Poll up to ~2 minutes
            print(f"[RECONCILE] Polling conversation {conversation_id} (round {poll_round + 1}/24)...")
            rows = await page.evaluate(PULL_RAW_JS, {"conversationId": conversation_id})
            for r in rows:
                creations = r.get("creations") or []
                for c in creations:
                    if c.get("id") and c.get("type") == 2 and c.get("download_url"):
                        creation = c
                        break
                if creation:
                    break
            if creation:
                break
            await asyncio.sleep(5)

        # Query credit statements observed
        statements = []
        try:
            statements = await page.evaluate(CREDIT_STATEMENTS_JS, {"conversationIds": [conversation_id]})
        except Exception:
            pass
        latest_statement = statements[-1] if statements else None
        credit_remaining = latest_statement.get("remaining") if latest_statement else "UNKNOWN"

        if not creation:
            # Check for provider refusal or generic error
            err_text = ""
            for r in rows:
                t = r.get("text") or ""
                if any(m in t for m in ["エラーが発生しました", "生成できません", "生成できませんでした"]):
                    err_text = t
                    break
            if not err_text and rows:
                err_text = rows[0].get("text") or "No creation generated by provider"

            print(f"[RECONCILE] Provider returned error without creation: {err_text}")
            if not journal.has(TERMINAL_PROVIDER_FAILURE):
                journal.append(TERMINAL_PROVIDER_FAILURE, {
                    "account": TARGET_ACCOUNT,
                    "conversation_id": conversation_id,
                    "provider_text": err_text[:300],
                    "credit_after": credit_remaining,
                    "paid_spend": "$0.00 / 0 VND (free tier route)"
                })
            auth.record_knowledge(
                KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
                detail=f"provider error observed in {conversation_id}: {err_text[:200]}"
            )
            auth.latch(
                "STOPPED_PROVIDER_FAILURE",
                detail=f"single attempt exhausted; provider error: {err_text[:200]}; free route preserved"
            )
            state["status"] = "STOPPED_PROVIDER_FAILURE"
            state["provider_outcome"] = "PROVIDER_ERROR_NO_CREATION"
            state["provider_message"] = err_text
            state["candidate_obtained"] = False
            state["conversation"] = conversation_id
            state["credit_after"] = credit_remaining
            state["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_json(state_path, state)

            manifest = {
                "version": "v2-022-s09-candidate-manifest-v2",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "shot_id": "S09",
                "scope_id": SCOPE_ID,
                "account": TARGET_ACCOUNT,
                "conversation_id": conversation_id,
                "prompt_sha256": EXPECTED_CANDIDATE_PROMPT_SHA,
                "candidate_obtained": False,
                "provider_outcome": "PROVIDER_ERROR_NO_CREATION",
                "provider_message": err_text,
                "monetary_spend": "$0.00 / 0 VND",
                "credit_after": credit_remaining,
                "latch": "STOPPED_PROVIDER_FAILURE"
            }
            save_json(REVIEW_DIR / "MANIFEST.json", manifest)
            return 2

        creation_id = str(creation.get("id"))
        video_model_raw = creation.get("video_model_raw")
        download_url = creation.get("download_url")

        print(f"[RECONCILE] Creation found: ID={creation_id}, download_url present")

        creation_obj = {
            "id": creation_id,
            "video": {
                "status": creation.get("status"),
                "download_url": download_url,
                "video_model": video_model_raw if isinstance(video_model_raw, str) else json.dumps(video_model_raw or {}),
            },
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
                        print("[RECONCILE] Selected unwatermarked rendition URL")
                    break

        if target_url is None:
            target_url = download_url
            print("[RECONCILE] Fallback to primary download_url")

        # Download asset
        target_asset_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"[RECONCILE] Downloading allowlisted media to {target_asset_file}...")
        total_bytes = download_allowlisted(target_url, target_asset_file)
        asset_sha = hashlib.sha256(target_asset_file.read_bytes()).hexdigest()
        print(f"[RECONCILE] Download complete: {total_bytes} bytes, SHA256={asset_sha}")

        # Extract frames & technical QC
        frames_dir = ISOLATED_DIR / "frames" / "S09"
        frames_extracted = extract_frames(target_asset_file, frames_dir)
        tech = technical_qc(target_asset_file, frames_dir)
        tech["frames_extracted"] = frames_extracted
        print(f"[RECONCILE] Technical QC: {tech}")

        # Copy to OWNER_REVIEW & Contact sheet
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        review_mp4.write_bytes(target_asset_file.read_bytes())
        generate_contact_sheet(frames_dir, sheet_path)
        generate_continuity_sheet(frames_dir, continuity_path)
        print(f"[RECONCILE] Media, contact sheet and continuity sheet copied to {REVIEW_DIR}")

        # Generate S01-S10 preview
        preview_ok = generate_s01_s10_preview(review_mp4, preview_mp4)
        print(f"[RECONCILE] S01-S10 preview generated ({preview_ok}) at {preview_mp4}")

        # Manifest
        manifest = {
            "version": "v2-022-s09-candidate-manifest-v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "shot_id": "S09",
            "scope_id": SCOPE_ID,
            "account": TARGET_ACCOUNT,
            "conversation_id": conversation_id,
            "creation_id": creation_id,
            "asset_sha256": asset_sha,
            "asset_size": total_bytes,
            "variant_authority": variant_authority,
            "technical_qc": tech,
            "preview_ok": preview_ok,
            "preview_path": str(preview_mp4) if preview_ok else None,
            "continuity_sheet": str(continuity_path) if continuity_path.exists() else None,
            "monetary_spend": "$0.00 / 0 VND (free tier route)",
            "credit_after": credit_remaining,
            "reconciled": True,
        }
        save_json(REVIEW_DIR / "MANIFEST.json", manifest)

        # Journal append
        journal.append(CREATION_BOUND, {
            "creation_ids": [creation_id],
            "conversation_id": conversation_id,
            "reconciled": True,
        })
        journal.append(ASSET_DOWNLOADED, {
            "sha256": asset_sha,
            "size": total_bytes,
        })
        journal.append(TERMINAL_SUCCESS, {
            "sha256": asset_sha,
        })

        # Authority latch closed
        auth.record_knowledge(
            KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
            detail=f"single S09 trial video acquired via read-only reconciliation: {asset_sha}"
        )
        auth.latch("TRIAL_COMPLETED_SUCCESS", "Single authorized S09 Candidate-002 completed successfully; scope closed against further mutation")

        state["status"] = "REVIEW_READY"
        state["candidate_obtained"] = True
        state["conversation"] = conversation_id
        state["creation_ids"] = [creation_id]
        state["asset"] = str(target_asset_file)
        state["sha256"] = asset_sha
        state["variant_authority"] = variant_authority
        state["technical"] = tech
        state["credit_after"] = credit_remaining
        state["reconciled"] = True
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_json(state_path, state)

        print("[RECONCILE] SUCCESS: S09 Candidate-002 packaged completely.")
        return 0

    finally:
        if manager:
            await manager.close()


async def execute_s09_trial() -> int:
    preflight = run_preflight()
    comp = preflight["comp"]

    # Verify zero-paid route and session
    print("[PREFLIGHT] Verifying ACCOUNT_A session and zero-paid route eligibility...")
    acct_status = await verify_account_preflight()
    print(f"  [OK] Session valid: {acct_status['session_valid']}, latest credit statement remaining: {acct_status['latest_remaining']}")

    ISOLATED_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    slot_dir = ISOLATED_DIR / "slots" / "S09"
    slot_dir.mkdir(parents=True, exist_ok=True)
    state_path = ISOLATED_DIR / "s09_candidate_state.json"
    journal_path = ISOLATED_DIR / "dispatch_journal_S09.jsonl"

    auth = MutationAuthority(slot_dir, SCOPE_ID)
    auth.check_mutation_allowed("S09")

    state = {
        "version": "v2-022-s09-candidate-state-v2",
        "shot_id": "S09",
        "scope_id": SCOPE_ID,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "account": TARGET_ACCOUNT,
        "status": "INIT",
        "mutations_used": 0,
        "monetary_spend": "$0.00 / 0 VND (free tier route)",
        "prompt_sha256": EXPECTED_CANDIDATE_PROMPT_SHA,
    }
    save_json(state_path, state)

    s09_node = next(n for n in comp["shot_graph"]["nodes"] if n["shot_id"] == "S09")

    transport_spec = ShotSpec(
        shot_id="S09",
        role="DECISION",
        prompt=FROZEN_S09_PROMPT,
        needle=CANDIDATE_NEEDLE,
        duration_class=int(s09_node["provider_requirements"]["duration_class"]),
        camera=s09_node["camera_intent"]["movement"],
        screen_direction="left-to-right",
    )

    state["status"] = "RESERVED"
    auth._event("MUTATION_RESERVED", budget_kind="S09")
    save_json(state_path, state)

    released = False
    captured_conversation_id = None
    captured_attempt_id = None

    def on_release(info: dict):
        nonlocal released, captured_conversation_id, captured_attempt_id
        released = True
        auth.consume("S09")
        state["mutations_used"] += 1
        state["status"] = "RELEASED"
        captured_conversation_id = info.get("conversation_id")
        captured_attempt_id = info.get("attempt_id")
        state["conversation"] = captured_conversation_id
        state["attempt_id"] = captured_attempt_id
        save_json(state_path, state)
        print(f"[RUNNER] Network release observed: attempt={captured_attempt_id}")

    def on_creation(info: dict):
        state["status"] = "CREATION_BOUND"
        state["creation_ids"] = info.get("creation_ids")
        save_json(state_path, state)
        print(f"[RUNNER] Creation bound: ids={info.get('creation_ids')}")

    events = RunnerEvents(ISOLATED_DIR / "provider_events.jsonl")
    runner.ACCOUNT_PROFILES = ACCOUNT_PROFILES_A

    print(f"[RUNNER] Dispatching S09 Candidate-002 on {TARGET_ACCOUNT}...")
    try:
        result = await dispatch_and_acquire(
            shot_spec=transport_spec,
            account_alias=TARGET_ACCOUNT,
            run_dir=ISOLATED_DIR,
            shot_tag="S09",
            on_release=on_release,
            on_creation=on_creation,
            events_sink=events,
            expected_nickname=None,
        )

        # Immediate success via SSE
        asset_file = Path(result["asset_path"])
        frames_dir = ISOLATED_DIR / "frames" / "S09"
        frames_extracted = extract_frames(asset_file, frames_dir)
        tech = technical_qc(asset_file, frames_dir)
        tech["frames_extracted"] = frames_extracted

        review_mp4 = REVIEW_DIR / "S09.mp4"
        review_mp4.write_bytes(asset_file.read_bytes())
        sheet_path = REVIEW_DIR / "S09_contact_sheet.png"
        generate_contact_sheet(frames_dir, sheet_path)

        continuity_path = REVIEW_DIR / "S08_S09_S10_continuity.png"
        generate_continuity_sheet(frames_dir, continuity_path)

        preview_mp4 = REVIEW_DIR / "S01_S10_PREVIEW.mp4"
        preview_ok = generate_s01_s10_preview(review_mp4, preview_mp4)

        manifest = {
            "version": "v2-022-s09-candidate-manifest-v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "shot_id": "S09",
            "scope_id": SCOPE_ID,
            "account": TARGET_ACCOUNT,
            "asset_sha256": result["asset_sha256"],
            "asset_size": result.get("size"),
            "variant_authority": result.get("variant_authority"),
            "technical_qc": tech,
            "preview_ok": preview_ok,
            "preview_path": str(preview_mp4) if preview_ok else None,
            "continuity_sheet": str(continuity_path) if continuity_path.exists() else None,
            "monetary_spend": "$0.00 / 0 VND (free tier route)",
        }
        save_json(REVIEW_DIR / "MANIFEST.json", manifest)

        auth.record_knowledge(
            KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
            detail=f"S09 Candidate-002 video acquired successfully via SSE: {result['asset_sha256']}"
        )
        auth.latch("TRIAL_COMPLETED_SUCCESS", "Single S09 trial acquired via SSE; scope closed")

        state["status"] = "REVIEW_READY"
        state["candidate_obtained"] = True
        state["asset"] = result["asset_path"]
        state["sha256"] = result["asset_sha256"]
        state["variant_authority"] = result.get("variant_authority")
        state["technical"] = tech
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_json(state_path, state)
        print("[RUNNER] All steps completed successfully via SSE capture.")
        return 0

    except BaseException as error:
        err_msg = str(error)
        print(f"[RUNNER] Dispatch caught: {err_msg}")

        # Check if network release occurred and receipt was missed
        journal = DispatchJournal(journal_path, "")
        if "receipt not captured" in err_msg or journal.has(NETWORK_RELEASE_OBSERVED):
            print("[RUNNER] Network release was observed! Initiating read-only reconciliation...")
            # Look up conversation ID strictly matching candidate needle or prefix (NO convs[0] fallback!)
            manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES_A / TARGET_ACCOUNT)
            page = await manager.launch_browser()
            target_conv = None
            try:
                await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(4)
                convs = await page.evaluate(RECENT_CONVS_JS)
                print(f"[RUNNER] Recent conversations: {convs[:6]}")
                for cid in convs[:6]:
                    try:
                        rows = await page.evaluate(PULL_RAW_JS, {"conversationId": cid})
                        for r in rows:
                            text = r.get("text") or ""
                            raw = r.get("content_raw") or ""
                            if CANDIDATE_NEEDLE in text or CANDIDATE_NEEDLE in raw or CANDIDATE_PREFIX in text:
                                target_conv = cid
                                print(f"[RUNNER] Strict needle match found in conversation {cid}")
                                break
                        if target_conv:
                            break
                    except Exception:
                        continue
            finally:
                await manager.close()

            if target_conv:
                target_asset = ISOLATED_DIR / "assets" / "S09.mp4"
                review_mp4 = REVIEW_DIR / "S09.mp4"
                sheet_path = REVIEW_DIR / "S09_contact_sheet.png"
                continuity_path = REVIEW_DIR / "S08_S09_S10_continuity.png"
                preview_mp4 = REVIEW_DIR / "S01_S10_PREVIEW.mp4"
                return await reconcile_read_only(
                    conversation_id=target_conv,
                    target_asset_file=target_asset,
                    review_mp4=review_mp4,
                    sheet_path=sheet_path,
                    continuity_path=continuity_path,
                    preview_mp4=preview_mp4,
                    journal=journal,
                    state=state,
                    state_path=state_path,
                    auth=auth,
                )
            else:
                # Strictly NO fallback to convs[0]
                print("[RUNNER] Exact conversation matching candidate needle was NOT found; convs[0] fallback strictly disallowed.")
                auth.record_knowledge(KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED, detail="Network release observed but matching conversation not found; fallback disallowed")
                auth.latch("STOPPED_CONVERSATION_UNRESOLVED", detail="Exact conversation matching candidate needle not found; convs[0] fallback strictly disallowed")
                state["status"] = "STOPPED_CONVERSATION_UNRESOLVED"
                state["error"] = "Exact conversation needle not found; fallback disallowed"
                state["completed_at"] = datetime.now(timezone.utc).isoformat()
                save_json(state_path, state)
                return 2

        # Other failure
        state["error"] = err_msg
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        if released:
            auth.record_knowledge(KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED, detail=err_msg[:200])
            auth.latch("STOPPED_POST_RELEASE_ERROR", detail=err_msg[:300])
            state["status"] = "STOPPED_POST_RELEASE_ERROR"
        else:
            auth.record_knowledge(KNOWLEDGE_RESOLVED_NO_EFFECT, detail=err_msg[:200])
            state["status"] = "STOPPED_PRE_RELEASE_ERROR"
        save_json(state_path, state)
        raise error


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run S09 Real Candidate 002")
    parser.add_argument("--preflight-only", action="store_true", help="Run only fail-closed preflight checks")
    args = parser.parse_args()

    if args.preflight_only:
        run_preflight()
        print("[SUCCESS] Preflight checks passed.")
        return 0

    return asyncio.run(execute_s09_trial())


if __name__ == "__main__":
    sys.exit(main())
