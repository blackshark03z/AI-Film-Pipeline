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
from mutation_authority import MutationAuthority
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


async def run_trial():
    ISOLATED_DIR.mkdir(parents=True, exist_ok=True)
    state_path = ISOLATED_DIR / "s08_trial_state.json"
    state = {
        "version": "v2-022-s08-trial-state-v1",
        "shot_id": "S08",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "account": "ACCOUNT_A",
        "status": "INIT",
        "mutations_used": 0,
        "monetary_spend": "$0.00 / 0 VND",
    }
    save_json(state_path, state)

    # 1. Setup compilation & ShotSpec
    comp = json.loads(COMP_PATH.read_text(encoding="utf-8"))
    s08_plan = comp["prompt_plans"]["S08"]
    s08_prompt = s08_plan["compiled_text"]
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
    slot_dir = ISOLATED_DIR / "slots" / "S08"
    slot_dir.mkdir(parents=True, exist_ok=True)
    auth = MutationAuthority(slot_dir, "QUALITY-V2-022/S08_TRIAL_001")
    if auth.authority != "OPEN":
        state["status"] = "STOPPED_MUTATION_LATCHED"
        save_json(state_path, state)
        print("STOPPED: Mutation authority not OPEN.")
        return 1

    state["status"] = "RESERVED"
    auth._event("MUTATION_RESERVED", budget_kind="S08")
    save_json(state_path, state)

    def on_release(info: dict):
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

    events = RunnerEvents(ISOLATED_DIR / "provider_events.jsonl")

    # 3. Configure profile mapping for ACCOUNT_A
    account = "ACCOUNT_A"
    runner.ACCOUNT_PROFILES = ACCOUNT_PROFILES_A

    print(f"[TRIAL] Starting single S08 video trial on {account}...")
    print(f"[TRIAL] Profile root: {runner.ACCOUNT_PROFILES / account}")
    print(f"[TRIAL] Target prompt SHA: {hashlib.sha256(s08_prompt.encode()).hexdigest()}")

    try:
        result = await dispatch_and_acquire(
            shot_spec=transport_spec,
            account_alias=account,
            run_dir=ISOLATED_DIR,
            shot_tag="S08",
            on_release=on_release,
            on_creation=on_creation,
            events_sink=events,
            expected_nickname=None,
        )
    except Exception as error:
        err_msg = str(error)
        state["error"] = err_msg
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_json(state_path, state)
        print(f"[TRIAL] Error during dispatch/acquire: {err_msg}")
        return 2

    # 4. Acquisition SUCCESS
    state["status"] = "ACQUIRED"
    state["asset"] = result["asset_path"]
    state["sha256"] = result["asset_sha256"]
    state["variant_authority"] = result.get("variant_authority")
    save_json(state_path, state)
    print(f"[TRIAL] Asset acquired successfully: {result['asset_path']}")

    # 5. Technical QC & frames
    asset_file = Path(result["asset_path"])
    frames_dir = ISOLATED_DIR / "frames" / "S08"
    frames_extracted = extract_frames(asset_file, frames_dir)
    tech = technical_qc(asset_file, frames_dir)
    tech["frames_extracted"] = frames_extracted
    state["technical"] = tech
    save_json(state_path, state)
    print(f"[TRIAL] Technical QC: {tech}")

    # 6. Copy to OWNER_REVIEW
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    review_mp4 = REVIEW_DIR / "S08.mp4"
    review_mp4.write_bytes(asset_file.read_bytes())
    sheet_path = REVIEW_DIR / "S08_contact_sheet.png"
    generate_contact_sheet(frames_dir, sheet_path)

    # 7. S01-S08 Preview
    preview_mp4 = REVIEW_DIR / "S01_S08_PREVIEW.mp4"
    preview_ok = generate_s01_s08_preview(review_mp4, preview_mp4)
    print(f"[TRIAL] S01-S08 preview generated: {preview_ok}")

    # 8. Manifest
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
    save_json(REVIEW_DIR / "MANIFEST.json", manifest)
    state["status"] = "REVIEW_READY"
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_json(state_path, state)
    print("[TRIAL] All steps completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_trial()))
