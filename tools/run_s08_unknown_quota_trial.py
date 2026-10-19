"""S3 Film120 — S08 Single Unknown-Quota Free-Route Trial Runner.

Executes exactly ONE bounded S08 Seedance v2.0 generation attempt on ACCOUNT_A
under isolated directory isolated_s08_single_trial_001/.
"""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.providers.dola_production.fixture_v2_020 import ShotSpec
from dola_010e_dispatch_journal import DispatchJournal
from mutation_authority import (
    MutationAuthority,
    AUTHORITY_OPEN,
    AUTHORITY_LATCHED_CLOSED,
    KNOWLEDGE_UNKNOWN,
    KNOWLEDGE_RESOLVED_NO_EFFECT,
    KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
import v2_020_runner as runner
from v2_020_runner import RunnerEvents, dispatch_and_acquire, technical_qc, extract_frames
from v2_021_common import needle_for

PRIMARY_ROOT = Path(r"D:\AI FILM MAKER\AI-Film-Pipeline")
PRIMARY_ASSETS = PRIMARY_ROOT / "projects/quality_v2_022_longform_120s/assets"
COMP_PATH = PRIMARY_ROOT / "projects/quality_v2_022_longform_120s/V2_022_LONGFORM_COMPILATION.json"

ISOLATED_DIR = ROOT / "isolated_s08_single_trial_001"
REVIEW_DIR = ROOT / "OWNER_REVIEW/FILM120_S08_UNKNOWN_QUOTA_TRIAL_001"

ACCOUNT_PROFILES_A = PRIMARY_ROOT / "projects/quality_v2_010e_final_f2b/runtime/account_profiles"
ACCOUNT_PROFILES_EF = PRIMARY_ROOT / "projects/quality_v2_021_narrative_compiler/pool_profiles"


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def inspect_journal_release_state(journal_path: Path) -> str:
    """Inspect dispatch journal for release events.
    Returns:
        'CONFIRMED_RELEASE': NETWORK_RELEASE_OBSERVED or MODEL_VERIFIED or SSE_RECEIPT_CAPTURED or CREATION_BOUND or ASSET_DOWNLOADED or TERMINAL_SUCCESS
        'ARMED': DISPATCH_ARMED present without release observation
        'UNKNOWN_OR_ARMED': malformed, unreadable, corrupted, or partial journal after possible transport
        'PRE_RELEASE': confirmed pre-release (MUTATION_RESERVED only and valid journal, or no journal file)
    """
    if not journal_path.exists():
        return "PRE_RELEASE"
    try:
        raw = journal_path.read_text(encoding="utf-8").strip()
        if not raw:
            return "UNKNOWN_OR_ARMED"
        lines = raw.splitlines()
    except Exception:
        return "UNKNOWN_OR_ARMED"

    has_confirmed_release = False
    has_armed = False
    has_reserved = False
    has_malformed = False

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            if not isinstance(ev, dict):
                has_malformed = True
                continue
            k = ev.get("kind") or ev.get("event")
            if k in ("NETWORK_RELEASE_OBSERVED", "MODEL_VERIFIED", "SSE_RECEIPT_CAPTURED", "CREATION_BOUND", "ASSET_DOWNLOADED", "TERMINAL_SUCCESS"):
                has_confirmed_release = True
            elif k == "DISPATCH_ARMED":
                has_armed = True
            elif k == "MUTATION_RESERVED":
                has_reserved = True
            else:
                has_malformed = True
        except Exception:
            has_malformed = True

    if has_confirmed_release:
        return "CONFIRMED_RELEASE"
    if has_malformed or has_armed:
        return "UNKNOWN_OR_ARMED" if has_malformed else "ARMED"
    if has_reserved and not has_malformed:
        return "PRE_RELEASE"

    return "UNKNOWN_OR_ARMED"


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


def generate_s01_s08_preview(s08_path: Path, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clips = []
    for sid in ["S01", "S02", "S03", "S04", "S05", "S06", "S07"]:
        p = PRIMARY_ASSETS / f"{sid}.mp4"
        if not p.exists():
            return False
        clips.append(p)
    clips.append(s08_path)

    inputs = []
    vlabels = []
    for i, clip in enumerate(clips):
        inputs += ["-i", str(clip)]
        vlabels.append(f"[{i}:v]")

    filter_str = "".join(vlabels) + f"concat=n={len(clips)}:v=1:a=0[out]"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[out]",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-r", "24",
        str(out_path)
    ]
    proc = subprocess.run(cmd, capture_output=True)
    return proc.returncode == 0 and out_path.exists()


async def run_trial(
    isolated_dir: Path | None = None,
    review_dir: Path | None = None,
    scope_id: str = "QUALITY-V2-022/S08_TRIAL_001",
    account: str = "ACCOUNT_A",
    dispatch_fn=None,
    prompt_override: str | None = None,
):
    target_dir = isolated_dir or ISOLATED_DIR
    target_review_dir = review_dir or REVIEW_DIR
    target_dispatch = dispatch_fn or dispatch_and_acquire

    slot_dir = target_dir / "slots" / "S08"
    state_path = target_dir / "s08_trial_state.json"
    auth_file = slot_dir / "mutation_authority.json"

    # C2 PRE-CHECK: On an existing latched scope, STOP BEFORE writing/overwriting
    # s08_trial_state.json or any other artifact. Resolve existing auth.authority
    # first using read-only state.
    if auth_file.exists():
        pre_auth = MutationAuthority(slot_dir, scope_id)
        if pre_auth.authority != AUTHORITY_OPEN:
            print(f"STOPPED: Mutation authority not OPEN (current: {pre_auth.authority}). Preserving existing state and evidence.")
            return 1

    # 1. Setup compilation & ShotSpec
    comp = json.loads(COMP_PATH.read_text(encoding="utf-8"))
    s08_plan = comp["prompt_plans"]["S08"]
    s08_prompt = prompt_override or s08_plan["compiled_text"]
    s08_needle = needle_for(comp, "S08")
    s08_node = next(n for n in comp["shot_graph"]["nodes"] if n["shot_id"] == "S08")

    transport_spec = ShotSpec(
        shot_id="S08",
        role=s08_node["function"],
        prompt=s08_prompt,
        needle=s08_needle,
        duration_class=s08_node["provider_requirements"]["duration_class"],
        camera=s08_node["camera_intent"]["movement"],
        screen_direction="left-to-right",
    )

    # 2. Setup MutationAuthority
    slot_dir.mkdir(parents=True, exist_ok=True)
    auth = MutationAuthority(slot_dir, scope_id)
    if auth.authority != AUTHORITY_OPEN:
        print(f"STOPPED: Mutation authority not OPEN (current: {auth.authority}).")
        return 1

    try:
        auth.check_mutation_allowed("S08")
    except OwnerAmbiguityGate as gate_err:
        print(f"STOPPED: Mutation authority check failed: {gate_err}")
        return 1

    target_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "version": "v2-022-s08-trial-state-v1",
        "shot_id": "S08",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "account": account,
        "status": "INIT",
        "mutations_used": 0,
        "monetary_spend": "$0.00 / 0 VND",
    }
    save_json(state_path, state)

    state["status"] = "RESERVED"
    auth._event("MUTATION_RESERVED", budget_kind="S08")
    save_json(state_path, state)

    released = False
    acquired = False

    def on_release(info: dict):
        nonlocal released
        released = True
        auth.consume("S08")
        state["mutations_used"] += 1
        state["status"] = "RELEASED"
        state["conversation"] = info.get("conversation_id")
        state["attempt_id"] = info.get("attempt_id")
        save_json(state_path, state)
        print(f"[TRIAL] Released to provider: attempt={info.get('attempt_id')}")

    def on_creation(info: dict):
        state["status"] = "CREATION_BOUND"
        state["creation_ids"] = info.get("creation_ids")
        save_json(state_path, state)
        print(f"[TRIAL] Creation bound: ids={info.get('creation_ids')}")

    events = RunnerEvents(target_dir / "provider_events.jsonl")

    # 3. Configure profile mapping for account
    runner.ACCOUNT_PROFILES = ACCOUNT_PROFILES_A

    print(f"[TRIAL] Starting single S08 video trial on {account}...")
    print(f"[TRIAL] Profile root: {runner.ACCOUNT_PROFILES / account}")
    print(f"[TRIAL] Target prompt SHA: {hashlib.sha256(s08_prompt.encode()).hexdigest()}")

    try:
        # Step A: Dispatch and acquire media
        result = await target_dispatch(
            shot_spec=transport_spec,
            account_alias=account,
            run_dir=target_dir,
            shot_tag="S08",
            on_release=on_release,
            on_creation=on_creation,
            events_sink=events,
            expected_nickname=None,
        )
        acquired = True

        # Step B: Acquisition SUCCESS
        state["status"] = "ACQUIRED"
        state["asset"] = result["asset_path"]
        state["sha256"] = result["asset_sha256"]
        state["variant_authority"] = result.get("variant_authority")
        save_json(state_path, state)
        print(f"[TRIAL] Asset acquired successfully: {result['asset_path']}")

        # Step C: Technical QC & frames
        asset_file = Path(result["asset_path"])
        frames_dir = target_dir / "frames" / "S08"
        frames_extracted = extract_frames(asset_file, frames_dir)
        tech = technical_qc(asset_file, frames_dir)
        tech["frames_extracted"] = frames_extracted
        state["technical"] = tech
        save_json(state_path, state)
        print(f"[TRIAL] Technical QC: {tech}")

        # Step D: Copy to OWNER_REVIEW & Contact sheet
        target_review_dir.mkdir(parents=True, exist_ok=True)
        review_mp4 = target_review_dir / "S08.mp4"
        review_mp4.write_bytes(asset_file.read_bytes())
        sheet_path = target_review_dir / "S08_contact_sheet.png"
        generate_contact_sheet(frames_dir, sheet_path)

        # Step E: S01-S08 Preview
        preview_mp4 = target_review_dir / "S01_S08_PREVIEW.mp4"
        preview_ok = generate_s01_s08_preview(review_mp4, preview_mp4)
        print(f"[TRIAL] S01-S08 preview generated: {preview_ok}")

        # Step F: Manifest
        manifest = {
            "version": "v2-022-s08-candidate-manifest-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "shot_id": "S08",
            "account": account,
            "asset_sha256": result["asset_sha256"],
            "asset_size": result.get("size"),
            "variant_authority": result.get("variant_authority"),
            "technical_qc": tech,
            "preview_ok": preview_ok,
            "preview_path": str(preview_mp4) if preview_ok else None,
        }
        save_json(target_review_dir / "MANIFEST.json", manifest)

        # Step G: Durable one-shot scope latch on success
        try:
            auth.record_knowledge(
                KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
                detail=f"single trial video acquired successfully: {result['asset_sha256']}"
            )
            auth.latch("TRIAL_COMPLETED_SUCCESS", "Single authorized trial completed successfully; scope closed against further mutation")
        except Exception as latch_err:
            print(f"[CRITICAL] Fail-closed: unable to record latch on success: {latch_err}", file=sys.stderr)
            raise RuntimeError(f"FAIL_CLOSED_LATCH_ERROR: {latch_err}") from latch_err

        state["status"] = "REVIEW_READY"
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_json(state_path, state)
        print("[TRIAL] All steps completed successfully.")
        return 0

    except BaseException as error:
        err_msg = str(error) or type(error).__name__
        state["error"] = err_msg
        state["completed_at"] = datetime.now(timezone.utc).isoformat()

        journal_file = target_dir / "dispatch_journal_S08.jsonl"
        j_state = inspect_journal_release_state(journal_file)
        is_post_release = released or acquired or (j_state == "CONFIRMED_RELEASE")
        is_ambiguous = (not is_post_release) and (j_state in ("ARMED", "UNKNOWN_OR_ARMED"))

        try:
            if is_post_release:
                auth.record_knowledge(
                    KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
                    detail=f"provider network release observed: {err_msg[:200]}"
                )
                if any(m in err_msg for m in ("クレジットは使用されませんでした", "STOPPED_PROVIDER_GENERATION_FAILED_NO_CREDIT")):
                    gate_kind = "STOPPED_PROVIDER_GENERATION_FAILED_NO_CREDIT"
                    state["provider_outcome"] = "GENERIC_PROVIDER_GENERATION_FAILURE_ZERO_CREDIT"
                elif "STOPPED_PROVIDER_POLICY_REFUSAL" in err_msg:
                    gate_kind = "STOPPED_PROVIDER_POLICY_REFUSAL"
                    state["provider_outcome"] = "PROVIDER_POLICY_REFUSAL"
                elif "receipt not captured" in err_msg or "RECEIPT_MISS" in err_msg:
                    gate_kind = "STOPPED_RECEIPT_MISS"
                    state["provider_outcome"] = "RECEIPT_MISS"
                elif isinstance(error, asyncio.CancelledError):
                    gate_kind = "STOPPED_CANCELLED_POST_RELEASE"
                    state["provider_outcome"] = "CANCELLED_POST_RELEASE"
                elif isinstance(error, (asyncio.TimeoutError, TimeoutError)) or "timeout" in err_msg.lower():
                    gate_kind = "STOPPED_TIMEOUT_POST_RELEASE"
                    state["provider_outcome"] = "TIMEOUT_POST_RELEASE"
                elif "QC_FAILURE" in err_msg or "extract_frames" in err_msg or "technical_qc" in err_msg:
                    gate_kind = "STOPPED_POST_ACQUISITION_QC_ERROR"
                    state["provider_outcome"] = "POST_ACQUISITION_QC_ERROR"
                elif "preview" in err_msg.lower() or "manifest" in err_msg.lower():
                    gate_kind = "STOPPED_POST_ACQUISITION_REVIEW_ERROR"
                    state["provider_outcome"] = "POST_ACQUISITION_REVIEW_ERROR"
                else:
                    gate_kind = "STOPPED_POST_RELEASE_ERROR"
                    state["provider_outcome"] = "ERROR_POST_RELEASE"

                auth.latch(gate_kind, detail=err_msg[:300])
                state["status"] = gate_kind

            elif is_ambiguous:
                auth.record_knowledge(
                    KNOWLEDGE_UNKNOWN,
                    detail=f"ambiguous release or journal ({j_state}): {err_msg[:200]}"
                )
                auth.latch("STOPPED_AMBIGUOUS_RELEASE", detail=err_msg[:300])
                state["status"] = "STOPPED_AMBIGUOUS_RELEASE"
                state["provider_outcome"] = "AMBIGUOUS_RELEASE"

            else:
                auth.record_knowledge(
                    KNOWLEDGE_RESOLVED_NO_EFFECT,
                    detail=f"confirmed pre-release failure: {err_msg[:200]}"
                )
                state["status"] = "STOPPED_PRE_RELEASE_ERROR"
                state["provider_outcome"] = "PRE_RELEASE_FAILURE"

            save_json(state_path, state)
        except Exception as latch_err:
            print(f"[CRITICAL] Fail-closed: unable to record latch/knowledge: {latch_err}", file=sys.stderr)
            state["status"] = "FAIL_CLOSED_LATCH_WRITE_ERROR"
            state["latch_error"] = str(latch_err)
            try:
                save_json(state_path, state)
            except Exception:
                pass
            raise RuntimeError(f"FAIL_CLOSED_LATCH_ERROR: {latch_err}") from latch_err

        if isinstance(error, KeyboardInterrupt):
            print(f"[TRIAL] Interrupted by user; fail-closed latch preserved: {state['status']}", file=sys.stderr)
            raise error

        print(f"[TRIAL] Finished with status: {state['status']}, error: {err_msg}")
        return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(run_trial()))
