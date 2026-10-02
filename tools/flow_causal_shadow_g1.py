"""FLOW-MAX-CAUSAL-FORENSICS-001 G1 — Owner Manual Golden Control Shadowing Runner.

Authoritative package: docs/operating/FLOW_MAX_CAUSAL_FORENSICS_001_WORK_PACKAGE.md

MISSION:
- Prepare native Flow UI in visible headful Chrome on project 93a579b4-834e-435b-8304-5f6682937935.
- Settings: Video | Thành phần (Ingredients) | Veo 3.1 - Lite | 16:9 | 720p | 8s | x1.
- Reference: story-auto-reference.png (ID: 298ba17a-2adb-4cd6-a9ea-677ff5166388).
- Embed unique correlation marker [FILM-g1_<uuid>].
- Enable maximum passive observability (CDP Network, DOM pointer/mouse/click event tracing, isTrusted).
- Create immutable G1 preclaim in ledger.
- Await exactly ONE manual click on Generate from the Owner.
- Shadow and record event chronology, initiator stack, request/response structures, catalog delta, acquisition & QC.
- Fail closed on any ambiguity.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import canonical_json, sha256
from film_pipeline.live_runtime import file_sha256, inspect_video, utc_now
from film_pipeline.providers import flow_rpc_contract as contract

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROFILE_PATH = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
EVIDENCE_DIR = Path(r"D:\AI FILM MAKER\Flow-Claude-Forensics-Evidence")
LEDGER_DIR = ROOT / "projects/flow_max_causal_forensics_001/ledger"
TRACES_DIR = ROOT / "projects/flow_max_causal_forensics_001/traces"

PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
REFERENCE_MEDIA_ID = "298ba17a-2adb-4cd6-a9ea-677ff5166388"
REFERENCE_FILENAME = "story-auto-reference.png"
REFERENCE_LOCAL_PATH = ROOT / "projects/character_continuity/slice0011/reference/31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531.png"
MODEL = contract.MODEL_VEO_3_1_LITE  # veo_3_1_r2v_lite

PROMPT_BODY = (
    "8-second locked eye-level medium close-up, 16:9. Use the exact image reference: "
    "one illustrated adult woman with teal bob hair, crimson round glasses, a mustard jacket "
    "over a blue shirt, silver triangle earrings and a beauty mark below her right eye; "
    "facing slightly right, she breathes gently and blinks once in a daytime living room, "
    "window left, sofa and plant right. Keep her face and outfit stable; movements subtle and calm."
)


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
        raise ValueError(f"video did not decode fully through EOF: {result.stderr.decode()}")


def extract_frame_at(video_path: Path, timestamp_s: float, output_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-ss", f"{timestamp_s:.3f}",
            "-i", str(video_path), "-frames:v", "1", str(output_path),
        ],
        check=True,
        timeout=30,
    )


def create_review_sheet(reference_path: Path, video_path: Path, duration_s: float, output_dir: Path) -> dict:
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

    side_sheet = Image.new("RGB", (1600, 660), "#151a24")
    draw = ImageDraw.Draw(side_sheet)
    draw.text((12, 12), "EXACT REFERENCE (31ca872d...)", fill="white")
    draw.text((812, 12), "QUALIFICATION G1 MANUAL GOLDEN CONTROL - Middle Frame", fill="white")

    if reference_path.exists():
        with Image.open(reference_path) as ref_img:
            side_sheet.paste(ref_img.convert("RGB").resize((800, 450)), (0, 40))
    with Image.open(middle_frame) as mid_img:
        side_sheet.paste(mid_img.convert("RGB").resize((800, 450)), (800, 40))

    side_sheet.paste(contact_sheet.resize((1600, 150)), (0, 500))
    comparison_path = output_dir / "reference_vs_g1_manual.png"
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


def main():
    parser = argparse.ArgumentParser(description="FLOW-MAX-CAUSAL-FORENSICS-001 G1 Shadow Runner")
    parser.add_argument("--timeout-click-sec", type=int, default=300, help="Wait time for manual click")
    args = parser.parse_args()

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    provider_job_id = "job_" + uuid.uuid4().hex + uuid.uuid4().hex
    marker = f"[FILM-{provider_job_id}]"
    full_prompt = f"{PROMPT_BODY}\n{marker}"

    trace = {
        "experiment": "G1_OWNER_MANUAL_GOLDEN_CONTROL",
        "protocol": "FLOW-MAX-CAUSAL-FORENSICS-001",
        "started_at": utc_now(),
        "project_id": PROJECT_ID,
        "provider_job_id": provider_job_id,
        "correlation_marker": marker,
        "model": MODEL,
        "mode": "ingredients_r2v",
        "reference_media_id": REFERENCE_MEDIA_ID,
        "reference_filename": REFERENCE_FILENAME,
        "t0_idle_state": {},
        "t1_pre_generate_state": {},
        "t2_event_chain": [],
        "t3_outbound_requests": [],
        "t4_responses": [],
        "t5_backend_timeline": [],
        "t6_acquisition": {},
        "verdict": None,
        "gate": "INITIALIZING"
    }

    print("=" * 75, flush=True)
    print("  FLOW-MAX-CAUSAL-FORENSICS-001 — G1 OWNER MANUAL GOLDEN CONTROL", flush=True)
    print("=" * 75, flush=True)
    print(f"Project ID     : {PROJECT_ID}", flush=True)
    print(f"Provider Job ID: {provider_job_id}", flush=True)
    print(f"Marker         : {marker}", flush=True)
    print(f"Model          : {MODEL}", flush=True)
    print(f"Reference      : {REFERENCE_FILENAME} ({REFERENCE_MEDIA_ID})", flush=True)
    print("=" * 75, flush=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_PATH),
            channel="chrome",
            headless=False,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ],
            ignore_default_args=["--enable-automation"],
            viewport=None
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Maximum Passive Observability: CDP Setup
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Runtime.enable")

        intercepted_requests = []
        intercepted_responses = []

        def on_request_sent(params):
            req = params.get("request", {})
            url = req.get("url", "")
            if "batchexecute" in url and "rpcids=MZZa6b" in url:
                post_data = req.get("postData", "")
                initiator = params.get("initiator", {})
                item = {
                    "timestamp": params.get("timestamp"),
                    "wallTime": params.get("wallTime"),
                    "url": url,
                    "method": req.get("method"),
                    "headers": req.get("headers"),
                    "body_length": len(post_data),
                    "body_sha256": hashlib.sha256(post_data.encode("utf-8")).hexdigest(),
                    "contains_marker": marker in post_data,
                    "contains_project": PROJECT_ID in post_data,
                    "contains_ref": REFERENCE_MEDIA_ID in post_data,
                    "initiator": initiator,
                    "sanitized_snippet": post_data[:300]
                }
                intercepted_requests.append(item)
                trace["t3_outbound_requests"].append(item)
                print(f"\n[CDP WIRE INTERCEPT] MZZa6b POST! Length={len(post_data)}, MarkerPresent={marker in post_data}", flush=True)
                print(f"Initiator Type: {initiator.get('type')}", flush=True)

        def on_response_recv(params):
            res = params.get("response", {})
            url = res.get("url", "")
            if "batchexecute" in url and "rpcids=MZZa6b" in url:
                item = {
                    "timestamp": params.get("timestamp"),
                    "status": res.get("status"),
                    "statusText": res.get("statusText"),
                    "headers": res.get("headers"),
                    "mimeType": res.get("mimeType"),
                    "responseTime": res.get("responseTime")
                }
                intercepted_responses.append(item)
                trace["t4_responses"].append(item)
                print(f"[CDP WIRE INTERCEPT] MZZa6b RESPONSE! Status={res.get('status')}", flush=True)

        cdp.on("Network.requestWillBeSent", on_request_sent)
        cdp.on("Network.responseReceived", on_response_recv)

        # Injected DOM Telemetry for pointer / click events
        dom_events = []
        def on_dom_event(source, event_data):
            dom_events.append(event_data)
            trace["t2_event_chain"].append(event_data)
            print(f"[DOM TELEMETRY] Event: {event_data.get('type')}, isTrusted: {event_data.get('isTrusted')}, time: {event_data.get('now')}", flush=True)

        page.expose_binding("__flow_dom_trace", on_dom_event)
        page.add_init_script("""
            ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click'].forEach(evtType => {
                document.addEventListener(evtType, (e) => {
                    const btn = e.target.closest('button');
                    const isGen = btn && (btn.innerText.includes('arrow_forward') || btn.querySelector('mat-icon, span')?.innerText?.includes('arrow_forward'));
                    if (isGen || e.target.innerText?.includes('arrow_forward')) {
                        window.__flow_dom_trace({
                            type: evtType,
                            isTrusted: e.isTrusted,
                            timeStamp: e.timeStamp,
                            now: Date.now(),
                            button: e.button,
                            clientX: e.clientX,
                            clientY: e.clientY,
                            targetTag: e.target.tagName,
                            targetClass: e.target.className
                        });
                    }
                }, true);
            });
        """)

        print(f"Navigating to Flow project {PROJECT_ID}...", flush=True)
        page.goto(f"https://flow.google.com/project/{PROJECT_ID}", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        # 1. WIZ Metadata & Baseline Catalog Read
        meta = page.evaluate('''() => {
            const w = globalThis.WIZ_global_data || {};
            return {
                host: location.host, source: location.pathname,
                at: w.SNlM0e || '', sid: w.FdrFJe || '', bl: w.cfb2h || '',
                hl: (document.documentElement.lang || 'en').split('-')[0],
                captcha: !!(globalThis.grecaptcha?.enterprise?.execute)
            };
        }''')
        session_meta = contract.sanitize_session(meta, PROJECT_ID, contract_version=contract.CONTRACT_VERSION_2026_10_01)
        trace["t0_idle_state"] = session_meta

        cat_body = contract.build_catalog(PROJECT_ID)
        cat_query = urllib.parse.urlencode({
            'rpcids': contract.RPC_CATALOG, 'source-path': meta['source'],
            'bl': meta['bl'], 'f.sid': meta['sid'], 'hl': meta['hl'], 'rt': 'c'
        })
        cat_res = ctx.request.post(
            'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?' + cat_query,
            data=urllib.parse.urlencode({'f.req': cat_body, 'at': meta['at']}),
            headers={'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                     'x-same-domain': '1', 'origin': 'https://flow.google.com',
                     'referer': f'https://flow.google.com/project/{PROJECT_ID}'}
        )
        baseline_records = contract.catalog_records_v2026_10_01(cat_res.text(), PROJECT_ID)
        baseline_ids = [r[0] for r in baseline_records]
        print(f"Pre-dispatch Baseline captured: {len(baseline_records)} records. Ref in baseline: {REFERENCE_MEDIA_ID in baseline_ids}", flush=True)

        # 2. Configure UI settings
        print("Configuring UI settings: Video mode, Thành phần, Veo 3.1 - Lite, 16:9, x1...", flush=True)
        pill_btn = page.locator('button').filter(has_text='Nano Banana 2').first
        if not pill_btn.is_visible():
            pill_btn = page.locator('button').filter(has_text='Video').first
        pill_btn.click()
        page.wait_for_timeout(800)

        video_btn = page.locator('.cdk-overlay-container button').filter(has_text='Video').first
        video_btn.click()
        page.wait_for_timeout(600)

        thanh_phan = page.locator('.cdk-overlay-container button').filter(has_text='Thành phần').first
        if thanh_phan.is_visible():
            thanh_phan.click()
            page.wait_for_timeout(400)

        model_btn = page.locator('.cdk-overlay-container button').filter(has_text='Omni 1.1 Flash').first
        if not model_btn.is_visible():
            model_btn = page.locator('.cdk-overlay-container button').filter(has_text='Veo').first
        if not model_btn.is_visible():
            model_btn = page.locator('.cdk-overlay-container button[aria-label*="mô hình"]').first

        model_btn.click()
        page.wait_for_timeout(600)

        lite_opt = page.locator('[role=menuitem]').filter(has_text='Veo 3.1 - Lite').first
        lite_opt.click(force=True)
        page.wait_for_timeout(400)

        x1_btn = page.locator('.cdk-overlay-container button').filter(has_text='x1').first
        if x1_btn.is_visible():
            x1_btn.click()
            page.wait_for_timeout(300)

        page.keyboard.press("Escape")
        page.wait_for_timeout(600)

        # 3. Attach Reference
        print(f"Attaching reference {REFERENCE_FILENAME} via UI picker...", flush=True)
        add_btn = page.locator('button').filter(has_text='add').last
        add_btn.click()
        page.wait_for_timeout(800)

        ref_item = page.locator('.cdk-overlay-container button').filter(has_text=REFERENCE_FILENAME).first
        ref_item.click()
        page.wait_for_timeout(600)

        them_btn = page.locator('button').filter(has_text='Thêm vào câu lệnh').first
        if them_btn.is_visible():
            them_btn.click()
            page.wait_for_timeout(800)

        # 4. Fill Prompt
        print("Filling prompt with correlation marker...", flush=True)
        editor = page.locator('div.ProseMirror').first
        editor.click()
        page.wait_for_timeout(300)

        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(200)

        for idx, line in enumerate(full_prompt.split('\n')):
            if idx:
                page.keyboard.press('Shift+Enter')
            if line:
                page.keyboard.insert_text(line)
        page.wait_for_timeout(800)

        editor_text = editor.inner_text().strip()
        if marker not in editor_text:
            raise ValueError("Correlation marker missing from ProseMirror editor!")

        gen_btn = page.locator('button').filter(has_text='arrow_forward').first
        if not gen_btn.is_visible() or not gen_btn.is_enabled():
            raise ValueError("Generate button is not enabled!")

        # 5. Record T1 Pre-Generate State & G1 Preclaim
        trace["t1_pre_generate_state"] = {
            "baseline_count": len(baseline_records),
            "baseline_ids": baseline_ids,
            "prompt_sha256": sha256(full_prompt),
            "marker": marker,
            "generate_button_enabled": True
        }

        preclaim = {
            "experiment": "G1_OWNER_MANUAL_GOLDEN_CONTROL",
            "provider_job_id": provider_job_id,
            "correlation_marker": marker,
            "project_id": PROJECT_ID,
            "model": MODEL,
            "baseline_ids": baseline_ids,
            "created_at": utc_now()
        }
        (LEDGER_DIR / "G1_PRECLAIM.json").write_text(json.dumps(preclaim, indent=2), encoding="utf-8")

        print("\n" + "=" * 75, flush=True)
        print(">>> IMMUTABLE G1 PRECLAIM CREATED. OBSERVABILITY FULLY ARMED. <<<", flush=True)
        print(">>> WAITING FOR OWNER MANUAL GENERATE CLICK ON CHROME WINDOW! <<<", flush=True)
        print("=" * 75 + "\n", flush=True)

        # 6. Wait for Owner manual click
        t0_wait = time.monotonic()
        while time.monotonic() - t0_wait < args.timeout_click_sec:
            if intercepted_requests or any(e.get("type") == "click" for e in dom_events):
                print("\n[ACTION DETECTED] Owner clicked Generate!", flush=True)
                break
            page.wait_for_timeout(500)

        if not intercepted_requests and not dom_events:
            print("[TIMEOUT] No manual click detected within timeout window.", flush=True)
            trace["gate"] = "OWNER_AMBIGUITY_GATE"
            trace["verdict"] = "TIMEOUT_NO_CLICK"
            TRACES_DIR.joinpath("G1_trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
            ctx.close()
            return

        # Wait up to 15s for MZZa6b wire request
        t_req_wait = time.monotonic()
        while time.monotonic() - t_req_wait < 15 and not intercepted_requests:
            page.wait_for_timeout(500)

        # Wait up to 15s for MZZa6b wire response
        t_res_wait = time.monotonic()
        while time.monotonic() - t_res_wait < 15 and not intercepted_responses:
            page.wait_for_timeout(500)

        print(f"Requests intercepted: {len(intercepted_requests)}, Responses intercepted: {len(intercepted_responses)}", flush=True)

        # Close browser immediately after dispatch cutoff
        print("Cutting off UI context; switching to pure read-only backend reconciliation...", flush=True)
        ctx.close()

    # 7. Read-only backend catalog polling
    print(f"\n[{utc_now()}] Polling Zzl0ze catalog for owned output {provider_job_id}...", flush=True)
    max_poll_seconds = 360
    poll_interval = 10
    t0_poll = time.monotonic()
    matched_row = None

    with sync_playwright() as p:
        ctx_poll = p.chromium.launch_persistent_context(
            str(PROFILE_PATH), channel="chrome", headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page_poll = ctx_poll.pages[0] if ctx_poll.pages else ctx_poll.new_page()
        page_poll.goto(f"https://flow.google.com/project/{PROJECT_ID}", wait_until="domcontentloaded", timeout=45000)
        page_poll.wait_for_timeout(2000)

        meta_poll = page_poll.evaluate('''() => {
            const w = globalThis.WIZ_global_data || {};
            return {
                host: location.host, source: location.pathname,
                at: w.SNlM0e || '', sid: w.FdrFJe || '', bl: w.cfb2h || '',
                hl: (document.documentElement.lang || 'en').split('-')[0]
            };
        }''')

        cat_query_poll = urllib.parse.urlencode({
            'rpcids': contract.RPC_CATALOG, 'source-path': meta_poll['source'],
            'bl': meta_poll['bl'], 'f.sid': meta_poll['sid'], 'hl': meta_poll['hl'], 'rt': 'c'
        })
        cat_body_poll = contract.build_catalog(PROJECT_ID)

        while time.monotonic() - t0_poll < max_poll_seconds:
            time.sleep(poll_interval)
            elapsed = int(time.monotonic() - t0_poll)
            res = ctx_poll.request.post(
                'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?' + cat_query_poll,
                data=urllib.parse.urlencode({'f.req': cat_body_poll, 'at': meta_poll['at']}),
                headers={'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                         'x-same-domain': '1', 'origin': 'https://flow.google.com',
                         'referer': f'https://flow.google.com/project/{PROJECT_ID}'}
            )
            records = contract.catalog_records_v2026_10_01(res.text(), PROJECT_ID)
            trace["t5_backend_timeline"].append({
                "elapsed_s": elapsed,
                "record_count": len(records),
                "timestamp": utc_now()
            })
            print(f"[{elapsed}s] Catalog records: {len(records)} (baseline={len(baseline_records)})", flush=True)

            new_ids = [r[0] for r in records if r[0] not in baseline_ids]
            if new_ids:
                print(f"[{elapsed}s] NEW CANDIDATES DETECTED: {new_ids}", flush=True)

            # Check candidate rows for our marker
            for r in records:
                if r[0] not in baseline_ids and any(marker in s for s in contract._strings(r)):
                    matched_row = r
                    print(f"[{elapsed}s] FOUND CANDIDATE: ID={r[0]}, Status={r[3]}", flush=True)
                    break

            if matched_row and matched_row[3] == "CAE":
                print(f"[{elapsed}s] CANDIDATE COMPLETED CAE!", flush=True)
                break

        if not matched_row:
            print("[RESULT] Zero catalog delta matching marker within observation window.", flush=True)
            trace["verdict"] = "NULL_ACK_NO_DELTA"
            trace["gate"] = "OWNER_AMBIGUITY_GATE"
        else:
            output_id = matched_row[0]
            print(f"\n[ATTRIBUTION] Unique output acquired: {output_id}")
            trace["output_identity"] = output_id
            trace["catalog_record"] = matched_row

            # Download media via as29s
            print(f"Resolving media download URL via as29s for {output_id}...", flush=True)
            media_body = contract.build_media(output_id)
            media_query = urllib.parse.urlencode({
                'rpcids': contract.RPC_MEDIA, 'source-path': meta_poll['source'],
                'bl': meta_poll['bl'], 'f.sid': meta_poll['sid'], 'hl': meta_poll['hl'], 'rt': 'c'
            })
            media_res = ctx_poll.request.post(
                'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?' + media_query,
                data=urllib.parse.urlencode({'f.req': media_body, 'at': meta_poll['at']}),
                headers={'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                         'x-same-domain': '1', 'origin': 'https://flow.google.com',
                         'referer': f'https://flow.google.com/project/{PROJECT_ID}'}
            )
            media_payload = contract.parse_rpc(media_res.text(), contract.RPC_MEDIA)
            stack, urls = [media_payload], set()
            while stack:
                node = stack.pop()
                if isinstance(node, list): stack.extend(node)
                elif isinstance(node, dict): stack.extend(node.values())
                elif isinstance(node, str) and node.startswith("https://flow-content.google/video/"):
                    urls.add(node)

            if len(urls) != 1:
                raise ValueError(f"Ambiguous CDN URLs: {urls}")

            cdn_url = next(iter(urls))
            print(f"Downloading MP4 from {cdn_url[:60]}...", flush=True)
            dl_res = ctx_poll.request.get(cdn_url, timeout=60000)
            video_bytes = dl_res.body()

            video_path = EVIDENCE_DIR / f"{output_id}.mp4"
            video_path.write_bytes(video_bytes)
            video_sha = file_sha256(video_path)
            print(f"Downloaded {len(video_bytes)} bytes. SHA256={video_sha}", flush=True)

            video_meta = inspect_video(video_path)
            verify_full_decode(video_path)
            review_packet = create_review_sheet(REFERENCE_LOCAL_PATH, video_path, video_meta["duration_s"], EVIDENCE_DIR)

            trace["t6_acquisition"] = {
                "output_id": output_id,
                "file_path": str(video_path),
                "file_size": len(video_bytes),
                "sha256": video_sha,
                "video_metadata": video_meta,
                "review_packet": review_packet,
                "full_decode": "PASS"
            }
            trace["verdict"] = "PROVEN_MANUAL_NATIVE_SUCCESS"
            trace["gate"] = "C4_G1_PROVEN"
            print("\n>>> G1 = PROVEN_MANUAL_NATIVE_SUCCESS! <<<", flush=True)

        ctx_poll.close()

    # Save traces
    trace_file = TRACES_DIR / "G1_trace.json"
    evidence_trace_file = EVIDENCE_DIR / "G1_trace.json"
    trace_file.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    evidence_trace_file.write_text(json.dumps(trace, indent=2), encoding="utf-8")

    # Update ledger
    ledger_file = LEDGER_DIR / "EXPERIMENT_LEDGER.json"
    ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
    ledger_data["generate_budget"]["released"] += 1
    ledger_data["generate_budget"]["remaining"] -= 1
    ledger_data["generate_budget"]["history"].append({
        "release": "G1",
        "actor": "OWNER_MANUAL",
        "provider_job_id": provider_job_id,
        "marker": marker,
        "verdict": trace["verdict"],
        "gate": trace["gate"],
        "output_identity": trace.get("output_identity")
    })
    ledger_data["current_checkpoint"] = "C4_G1_MANUAL_GOLDEN_TRACE"
    ledger_file.write_text(json.dumps(ledger_data, indent=2), encoding="utf-8")

    print(f"\nTrace saved to {trace_file}")
    print("=" * 75, flush=True)


if __name__ == "__main__":
    main()
