"""Bounded CHAR_CONTINUITY_A live canary using flow-batchexecute/2026-10-01.1.

Execution constraints:
- Contract: flow-batchexecute/2026-10-01.1
- Model: veo_3_1_r2v_fast_landscape
- Aspect: 16:9 / enum 2
- Reference: asset_70834935ccb760367645411d115c0c24243f4dd921182ef4b9502cad382062ff
- Reference source SHA: 31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531
- Max reference uploads: 1 (0 used if pre-existing verified in baseline)
- Max MZZa6b submits: 1
- Retries: 0
- Shot B: 0
- Dola/Seedance: 0
- Fresh baseline captured immediately before mutation
- Fail-closed acquisition and verification
- Final gate: OWNER_CHARACTER_CONTINUITY_REVIEW_GATE on success, OWNER_AMBIGUITY_GATE on any failure
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw

from film_pipeline.core import canonical_json, sha256
from film_pipeline.live_runtime import file_sha256, inspect_video
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_r2v_prompt import film_marker
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
    OwnerAuthRequired,
)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID = "f6b40e79-d6f8-4354-80ae-c863260e96f5"
REFERENCE_ASSET_ID = "asset_70834935ccb760367645411d115c0c24243f4dd921182ef4b9502cad382062ff"
REFERENCE_SHA256 = "31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531"
REFERENCE_PATH = ROOT / "projects/character_continuity/slice0011/reference/31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531.png"
REFERENCE_MEDIA_ID = "53b5a413-7bb5-4f97-9be4-2461794a7d80"
REFERENCE_FILENAME = "story-auto-reference.png"

TARGET_MODEL = contract.MODEL_VEO_3_1_FAST_LANDSCAPE
CONTRACT_VERSION = contract.CONTRACT_VERSION_2026_10_01

PROMPT_BODY = (
    "8-second locked eye-level medium close-up, 16:9. Use the exact image reference: "
    "one illustrated adult woman with teal bob hair, crimson round glasses, a mustard jacket "
    "over a blue shirt, silver triangle earrings and a beauty mark below her right eye; "
    "facing slightly right, she breathes gently and blinks once in a daytime living room, "
    "window left, sofa and plant right. Keep her face and outfit stable; movements subtle and calm."
)


def write_exact(path: Path, data: dict) -> None:
    encoded = canonical_json(data)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise OwnerAmbiguityGate("immutable evidence file differs")
        return
    with path.open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def verify_full_decode(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required for full video decode")
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True,
        timeout=180,
    )
    if result.returncode:
        raise ValueError("video did not decode fully through EOF")


def extract_frame_at(video_path: Path, timestamp_s: float, output_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            f"{timestamp_s:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ],
        check=True,
        timeout=30,
    )


def create_review_sheet(
    reference_path: Path, video_path: Path, duration_s: float, output_dir: Path
) -> dict:
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    sample_times = [0.2, 2.0, 4.0, 6.0, min(7.8, duration_s - 0.2)]
    frame_paths = []
    for i, t in enumerate(sample_times):
        fpath = frames_dir / f"frame_{i}_{t:.3f}s.jpg"
        extract_frame_at(video_path, t, fpath)
        frame_paths.append(fpath)

    middle_frame = frames_dir / "middle_frame.png"
    extract_frame_at(video_path, duration_s / 2.0, middle_frame)

    # 1. Contact sheet of sampled frames
    contact_width = 1600
    single_w = contact_width // len(sample_times)
    single_h = int(single_w * 9 / 16)
    contact_sheet = Image.new("RGB", (contact_width, single_h), "#000000")
    for i, fpath in enumerate(frame_paths):
        with Image.open(fpath) as img:
            thumb = img.convert("RGB").resize((single_w, single_h), Image.Resampling.LANCZOS)
            contact_sheet.paste(thumb, (i * single_w, 0))
    contact_path = output_dir / "contact_sheet.jpg"
    contact_sheet.save(contact_path, quality=90)

    # 2. Side-by-side comparison: Reference vs Middle Frame
    side_sheet = Image.new("RGB", (1600, 660), "#151a24")
    draw = ImageDraw.Draw(side_sheet)
    draw.text((12, 12), "EXACT REFERENCE (31ca872d...)", fill="white")
    draw.text((812, 12), "CANARY VEO 3.1 OUTPUT - Middle Frame (4.0s)", fill="white")

    with Image.open(reference_path) as ref_img:
        side_sheet.paste(ref_img.convert("RGB").resize((800, 450)), (0, 40))
    with Image.open(middle_frame) as mid_img:
        side_sheet.paste(mid_img.convert("RGB").resize((800, 450)), (800, 40))

    # Add contact sheet below
    side_sheet.paste(contact_sheet.resize((1600, 150)), (0, 500))
    comparison_path = output_dir / "reference_vs_canary_a.png"
    side_sheet.save(comparison_path)

    return {
        "contact_sheet": str(contact_path),
        "contact_sheet_sha256": file_sha256(contact_path),
        "comparison": str(comparison_path),
        "comparison_sha256": file_sha256(comparison_path),
        "middle_frame": str(middle_frame),
        "middle_frame_sha256": file_sha256(middle_frame),
        "frames": [str(p) for p in frame_paths],
    }


def run_canary(cookie_path: Path, output_dir: Path) -> dict:
    start_time = time.monotonic()
    iso_start = datetime.now(timezone.utc).isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)

    result_file = output_dir / "canary_result.json"
    if result_file.exists():
        raise OwnerAmbiguityGate("canary_result.json already exists; no retry permitted")

    # 1. Verify reference
    if not REFERENCE_PATH.exists():
        raise OwnerAmbiguityGate(f"Reference file missing at {REFERENCE_PATH}")
    actual_ref_sha = file_sha256(REFERENCE_PATH)
    if actual_ref_sha != REFERENCE_SHA256:
        raise OwnerAmbiguityGate(f"Reference SHA mismatch: expected {REFERENCE_SHA256}, got {actual_ref_sha}")

    # 2. Get implementation git revision
    try:
        impl_rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        impl_rev = "unknown"

    report = {
        "contract_version": CONTRACT_VERSION,
        "implementation_revision": impl_rev,
        "started_at": iso_start,
        "model": TARGET_MODEL,
        "aspect": "16:9",
        "aspect_enum": 2,
        "reference_asset": REFERENCE_ASSET_ID,
        "reference_sha256": REFERENCE_SHA256,
        "reference_media_id": REFERENCE_MEDIA_ID,
        "reference_filename": REFERENCE_FILENAME,
        "project_id": PROJECT_ID,
        "provider_prompt_body_characters": len(PROMPT_BODY),
        "prompt_body": PROMPT_BODY,
        "reference_uploads": 0,
        "mzza6b_submits": 0,
        "retries": 0,
        "shot_b_submits": 0,
        "dola_seedance_calls": 0,
        "gate": "OWNER_AMBIGUITY_GATE",
        "output_identity": None,
        "video_asset": None,
        "technical_qc": None,
        "review_packet": None,
    }

    # 3. Create correlation ID and provider prompt with marker
    provider_job_id = "job_" + uuid.uuid4().hex + uuid.uuid4().hex
    marker = film_marker(provider_job_id)
    full_prompt = f"{PROMPT_BODY}\n{marker}"
    report["provider_job_id"] = provider_job_id
    report["correlation_marker"] = marker
    report["full_prompt"] = full_prompt

    session = FlowReferenceRpcSession(cookie_path=cookie_path, project_id=PROJECT_ID)
    try:
        with session:
            meta = session.metadata()
            report["sanitized_session"] = contract.sanitize_session(
                meta, PROJECT_ID, contract_version=CONTRACT_VERSION
            )

            # 4. Capture fresh baseline immediately before mutation
            records = session.catalog(contract_version=CONTRACT_VERSION)
            baseline_ids = [r[0] for r in records]
            baseline_fingerprint = session.catalog_fingerprint
            report["baseline"] = {
                "catalog_fingerprint": baseline_fingerprint,
                "catalog_count": len(records),
                "catalog_ids": baseline_ids,
            }

            # Verify that reference media ID is in baseline
            if REFERENCE_MEDIA_ID not in baseline_ids:
                raise OwnerAmbiguityGate(
                    f"Reference {REFERENCE_MEDIA_ID} not found in project baseline"
                )

            # 5. Acquire Captcha token for VIDEO_GENERATION
            print(f"[{datetime.now(timezone.utc).isoformat()}] Requesting enterprise reCAPTCHA token...", flush=True)
            captcha_token = session.captcha("VIDEO_GENERATION")
            report["captcha_token_length"] = len(captcha_token)

            # 6. Build MZZa6b request
            request_id = str(uuid.uuid4())
            body = contract.build_video_v2026_10_01(
                project_id=PROJECT_ID,
                prompt=full_prompt,
                reference_id=REFERENCE_MEDIA_ID,
                reference_filename=REFERENCE_FILENAME,
                captcha=captcha_token,
                request_id=request_id,
                model=TARGET_MODEL,
                aspect=2,
            )
            report["mzza6b_request_id"] = request_id

            # 7. Single MZZa6b submit (BUDGET: EXACTLY 1 SUBMIT, 0 RETRIES)
            print(f"[{datetime.now(timezone.utc).isoformat()}] Dispatching sole MZZa6b generation request...", flush=True)
            response_diag = None
            http_status = None
            http_bytes = 0

            def on_diag(d):
                nonlocal response_diag
                response_diag = d

            def on_http(st, ln):
                nonlocal http_status, http_bytes
                http_status = st
                http_bytes = ln

            raw_response = session._rpc_body(
                contract.RPC_VIDEO,
                body,
                on_http_response=on_http,
                on_submission_diagnostics=on_diag,
            )
            report["mzza6b_submits"] = 1
            report["http_status"] = http_status
            report["response_bytes_len"] = http_bytes
            report["response_diagnostics"] = response_diag

            if http_status != 200:
                raise OwnerAmbiguityGate(f"HTTP status non-200: {http_status}")
            if response_diag and response_diag.get("type_counts", {}).get("null", 0) > 0 and response_diag.get("type_counts", {}).get("list", 0) == 0:
                raise OwnerAmbiguityGate("Provider returned null payload ACK (model deprecated or rejected)")

            # 8. Poll catalog for owned output
            print(f"[{datetime.now(timezone.utc).isoformat()}] Polling catalog Zzl0ze for owned output...", flush=True)
            max_poll_seconds = 600
            poll_interval = 10
            poll_t0 = time.monotonic()
            matched_row = None

            while time.monotonic() - poll_t0 < max_poll_seconds:
                poll_elapsed = int(time.monotonic() - poll_t0)
                time.sleep(poll_interval)
                current_records = session.catalog(contract_version=CONTRACT_VERSION)
                matched = contract.match_r2v_output_v2026_10_01(
                    current_records,
                    PROJECT_ID,
                    REFERENCE_MEDIA_ID,
                    REFERENCE_FILENAME,
                    provider_job_id,
                    baseline_ids=baseline_ids,
                    model=TARGET_MODEL,
                )
                if matched is not None:
                    matched_row = matched
                    print(f"[{datetime.now(timezone.utc).isoformat()}] Owned output matched! ID={matched[0]}, Status={matched[3]} after {poll_elapsed}s", flush=True)
                    break
                print(f"[{datetime.now(timezone.utc).isoformat()}] Polling... {poll_elapsed}s elapsed, records in catalog: {len(current_records)}", flush=True)

            if matched_row is None:
                raise OwnerAmbiguityGate(f"Polling timeout ({max_poll_seconds}s): no uniquely owned output appeared")

            output_id = matched_row[0]
            report["output_identity"] = output_id
            report["catalog_record_status"] = matched_row[3]
            report["catalog_record"] = matched_row

            # 9. Download media via as29s
            print(f"[{datetime.now(timezone.utc).isoformat()}] Downloading video bytes via as29s for {output_id}...", flush=True)
            video_bytes = session.media(output_id, "video")
            if not video_bytes or len(video_bytes) < 100_000:
                raise OwnerAmbiguityGate("Media download empty or truncated")

            video_path = output_dir / f"{output_id}.mp4"
            with video_path.open("xb") as stream:
                stream.write(video_bytes)
                stream.flush()
                os.fsync(stream.fileno())

            video_sha = file_sha256(video_path)
            report["video_asset"] = {
                "output_id": output_id,
                "file_path": str(video_path),
                "file_size": len(video_bytes),
                "sha256": video_sha,
            }

            # 10. Technical QC & Full Decode
            print(f"[{datetime.now(timezone.utc).isoformat()}] Running technical inspection and full EOF decode...", flush=True)
            video_meta = inspect_video(video_path)
            report["video_metadata"] = video_meta

            # Validate technical QC constraints
            duration = video_meta["duration_s"]
            aspect_ratio = video_meta["width"] / video_meta["height"]
            if abs(duration - 8.0) > 0.3:
                raise OwnerAmbiguityGate(f"Duration {duration}s deviates from expected 8.0s")
            if abs(aspect_ratio - 16 / 9) > 0.05:
                raise OwnerAmbiguityGate(f"Aspect ratio {aspect_ratio} deviates from 16:9")

            verify_full_decode(video_path)
            report["full_decode_eof"] = "PASS"

            # 11. Create review sheet and comparison frame
            print(f"[{datetime.now(timezone.utc).isoformat()}] Generating character continuity review packet...", flush=True)
            review_packet = create_review_sheet(REFERENCE_PATH, video_path, duration, output_dir)
            report["review_packet"] = review_packet
            report["technical_qc"] = {
                "duration_s": duration,
                "width": video_meta["width"],
                "height": video_meta["height"],
                "codec": video_meta.get("codec"),
                "mime_type": video_meta.get("mime_type"),
                "full_decode": "PASS",
                "verdict": "PASS",
            }

            # SUCCESS: STOP AT OWNER_CHARACTER_CONTINUITY_REVIEW_GATE
            report["gate"] = "OWNER_CHARACTER_CONTINUITY_REVIEW_GATE"
            report["completed_at"] = datetime.now(timezone.utc).isoformat()
            report["elapsed_s"] = round(time.monotonic() - start_time, 2)
            print(f"[{datetime.now(timezone.utc).isoformat()}] SUCCESS: Reached OWNER_CHARACTER_CONTINUITY_REVIEW_GATE!", flush=True)

    except Exception as exc:
        report["stop_type"] = type(exc).__name__
        report["stop_reason"] = str(exc)
        report["gate"] = "OWNER_AMBIGUITY_GATE"
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_s"] = round(time.monotonic() - start_time, 2)
        print(f"[{datetime.now(timezone.utc).isoformat()}] STOPPED AT OWNER_AMBIGUITY_GATE: {type(exc).__name__}: {exc}", flush=True)

    finally:
        write_exact(result_file, report)
        print(f"Canary report written to {result_file}", flush=True)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cookie",
        type=Path,
        default=ROOT / "projects/character_continuity/slice0011/auth_restoration_v1/restored.cookies",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "projects/character_continuity/canary_20261001",
    )
    args = parser.parse_args()
    report = run_canary(args.cookie, args.output)
    if report["gate"] != "OWNER_CHARACTER_CONTINUITY_REVIEW_GATE":
        sys.exit(1)
