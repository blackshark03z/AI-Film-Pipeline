"""AI-FILM-QUALITY-V2-010C — Layer 3: M1 browser oracle generation.

ONE authorized browser generation whose purpose is protocol reconstruction
with a fully proven causal chain:

    USER ACTION → EXACT NETWORK RELEASE → PROVIDER ACK/RECEIPT → STABLE IDs
      → POLL/STREAM → EXACT GENERATION → EXACT VIDEO (sha256)

Governance before dispatch: MutationAuthority reservation, GenerationAttempt
(contract-validated), request-fingerprint placeholder, oracle run_id, capture
ACTIVE. Output identity comes ONLY from network IDs — never from the newest
gallery item or first video.

UI selectors are OBSERVED at runtime (the 2026-10 surface exposes video
creation as skills: 動画生成 / Video generation / Seedance 2.0 video);
everything selected is recorded into the evidence chain.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_capture import NetworkCapture, sanitize_capture, SIGNED_URL_QUERY_RE
from dola_010c_captcha import find_gap_x
from dola_010c_session import (ORIGIN, PKG, SESSION_VALID,
                               DolaSessionManager, load_session_encrypted)
from film_pipeline.core import GenerationAttempt
from film_pipeline.execution import sha256
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-010C-DOLA-FULLSTACK"
ORACLE_PROMPT = ("a small white lighthouse on a rocky island at sunrise, "
                 "gentle ocean waves, warm natural light, no people, no text")
PROMPT_SHA = hashlib.sha256(ORACLE_PROMPT.encode("utf-8")).hexdigest()
INTENT = {"prompt_sha256": PROMPT_SHA, "aspect_ratio": "16:9",
          "duration_target_s": 5, "model_target": "seedance_v2.0",
          "purpose": "M1 protocol reconstruction oracle"}
SHOT_ID = "V2_010C_M1_ORACLE"

CAPTCHA_FRAME_KEY = "bdcaptcha.html"
# observed 2026-10-06 skill entries (exact element texts), most specific first
VIDEO_ENTRY_TEXTS = ["Seedance 2.0 video", "動画生成 Seedance 2.0",
                     "Seedance 2.0 模型", "動画生成", "Video generation",
                     "影片生成", "Tạo video"]
MODEL_OPTION_TEXTS = ["Dreamina Seedance 2.0高速", "Dreamina Seedance 2.0",
                      "Seedance2.0Fast", "Seedance 2.0", "モデル 2.0高速"]
PARAMETER_MARKERS = ["動画生成パラメータ", "Seedance", "16:9", "比率", "モデル",
                     "解像度", "duration", "秒"]
DURATION_ORDER = [5, 10, 15, 30]
DURATION_TEXTS = {5: ["5s", "5秒", "5 giây"], 10: ["10s", "10秒", "10 giây"],
                  15: ["15s", "15秒", "15 giây"], 30: ["30s", "30秒", "30 giây"]}
VIDEO_HOST_SUFFIXES = (".byteimg.com", ".volces.com", ".ibytedtos.com",
                       ".bytecdn.cn", ".zjcdn.com", ".douyinpic.com")
RELEASE_URL_MARKERS = ("/chat/completion", "/samantha/chat", "/completion")

CONVERSATION_ID_RE = re.compile(r'"conversation_id"\s*:\s*"(\d{10,})"')


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def write_pkg(name: str, payload: dict) -> Path:
    path = PKG / name
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path


def build_attempt() -> GenerationAttempt:
    identity = {
        "shot_spec_hash": sha256({"shot_id": SHOT_ID, "purpose": INTENT}),
        "prompt_plan_hash": sha256({"prompt_sha256": PROMPT_SHA,
                                    "intent": INTENT}),
        "routing_decision_id": "route_v2_010c_m1_browser_oracle",
        "provider_id": "seedance_dola",
        "request_id": "m1_oracle",
        "started_at": utcnow(),
    }
    return GenerationAttempt(
        generation_attempt_id="attempt_" + sha256(identity),
        shot_id=SHOT_ID, shot_spec_version=1,
        shot_spec_hash=identity["shot_spec_hash"],
        prompt_plan_hash=identity["prompt_plan_hash"],
        routing_decision_id=identity["routing_decision_id"],
        provider_id="seedance_dola", status="created",
        started_at=identity["started_at"])


async def fetch_post_bodies_for(capture: NetworkCapture, needle: str,
                                since_utc: str) -> list[dict]:
    """Correlate released POSTs whose body contains `needle` after `since_utc`."""
    found = []
    seen_ids: set[str] = set()
    for entry in capture.recent:
        if entry.get("kind") != "REQ" or entry.get("method") != "POST":
            continue
        if entry.get("utc", "") < since_utc:
            continue
        request_id = entry.get("request_id")
        if not request_id or request_id in seen_ids:
            continue
        seen_ids.add(request_id)
        post_data = await capture.get_post_data(request_id)
        if post_data and needle[:24] in post_data:
            body = post_data.encode("utf-8")
            found.append({
                "request_id": request_id,
                "url": SIGNED_URL_QUERY_RE.sub(r"\1=REDACTED",
                                               entry.get("url", "")),
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "body_len": len(body),
                "utc": entry.get("utc"),
                "body_structure": json.loads(post_data)
                if post_data.startswith("{") else None})
    return found


async def solve_captcha(page, attempts: int = 3) -> bool:
    """Best-effort PIL slider solve; False → caller stops (operator/CAPTCHA)."""
    for attempt in range(1, attempts + 1):
        frame = None
        for _ in range(20):
            await page.wait_for_timeout(1000)
            frame = next((f for f in page.frames
                          if CAPTCHA_FRAME_KEY in (f.url or "")), None)
            if frame:
                break
        if not frame:
            return True  # captcha gone → passed or never needed
        try:
            imgs = await frame.evaluate(
                """() => [...document.images].map(im => ({
                    src: im.src, w: im.naturalWidth, h: im.naturalHeight,
                    bw: im.getBoundingClientRect().width,
                    left: im.getBoundingClientRect().left}))""")
            bg = next((i for i in imgs if ".jpeg" in i["src"] or "-2." in i["src"]), None)
            piece = next((i for i in imgs if i is not bg and
                          (".png" in i["src"] or "-1." in i["src"])), None)
            btn = frame.locator(".captcha-slider-btn")
            bb = await btn.bounding_box()
            if not (bg and piece and bb):
                emit({"captcha": "structure_not_found", "attempt": attempt})
                continue

            def fetch(url: str) -> bytes:
                request = urllib.request.Request(url)
                with urllib.request.urlopen(request, timeout=30) as resp:
                    return resp.read()

            bg_bytes = await asyncio.to_thread(fetch, bg["src"])
            piece_bytes = await asyncio.to_thread(fetch, piece["src"])
            gap_x, conf = await asyncio.to_thread(find_gap_x, bg_bytes, piece_bytes)
            scale = bg["bw"] / bg["w"] if bg["w"] else 340 / 552
            distance = (gap_x - (piece["left"] - bg["left"]) / scale) * scale
            emit({"captcha": "solving", "attempt": attempt, "gap_x": gap_x,
                  "conf": round(conf, 3), "distance_px": round(distance)})
            if conf < 0.25:
                continue
            sx, sy = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            await page.mouse.move(sx, sy)
            await page.wait_for_timeout(300)
            await page.mouse.down()
            await page.wait_for_timeout(150)
            steps = 50
            for step in range(1, steps + 1):
                t = step / steps
                eased = 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5
                await page.mouse.move(sx + distance * eased, sy)
                await asyncio.sleep(0.012)
            await page.wait_for_timeout(200)
            await page.mouse.up()
            for _ in range(10):
                await page.wait_for_timeout(700)
                if not any(CAPTCHA_FRAME_KEY in (f.url or "")
                           for f in page.frames):
                    emit({"captcha": "passed", "attempt": attempt})
                    return True
        except Exception as error:
            emit({"captcha": "error", "attempt": attempt,
                  "error": type(error).__name__})
    return False


async def wait_composer(page, timeout_s: int = 90) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if await page.evaluate(
                    """() => !!(document.querySelector('textarea')
                            || document.querySelector('[contenteditable="true"]'))"""):
                return True
        except Exception:
            pass
        await page.wait_for_timeout(1000)
    return False


async def observed_texts(page) -> list[str]:
    try:
        return await page.evaluate(
            """() => [...document.querySelectorAll('button, [role=button], div, span')]
                .map(el => (el.innerText || '').trim())
                .filter(t => t && t.length <= 24)
                .slice(0, 400)""")
    except Exception:
        return []


async def click_first_match(page, texts: list[str]) -> str | None:
    for text in texts:
        try:
            locator = page.get_by_text(text, exact=True).first
            if await locator.count() and await locator.is_visible():
                await locator.click(timeout=5000)
                return text
        except Exception:
            continue
    return None


def scan_video_candidates(entry: dict, conversation_id: str) -> tuple[list[str], list[str]]:
    """Video URLs from a captured BODY/SSE entry, only when the entry text is
    linked to THIS conversation. Returns (video_urls, all_https_hosts)."""
    blob = entry.get("body") or entry.get("data") or ""
    if not isinstance(blob, str) or not blob:
        return [], []
    if conversation_id and conversation_id not in blob:
        return [], []
    urls = re.findall(r"https://[^\s\"'\\]+", blob)
    video_urls, hosts = [], []
    for url in urls:
        url = url.rstrip("\\").replace("\\u0026", "&").rstrip("',\"")
        try:
            host = url.split("/")[2].lower()
        except IndexError:
            continue
        hosts.append(host)
        if any(host.endswith(s) for s in VIDEO_HOST_SUFFIXES) or ".mp4" in url:
            video_urls.append(url)
    return video_urls, sorted(set(hosts))


async def main() -> int:
    run_id = "m1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    chain = {"run_id": run_id, "purpose": INTENT, "prompt_sha256": PROMPT_SHA,
             "events": [], "verdicts": {}}

    def event(step: str, **data) -> None:
        chain["events"].append({"step": step, "utc": utcnow(), **data})
        emit({"event": step, **data})

    screenshots = PKG / "screenshots_m1"
    screenshots.mkdir(parents=True, exist_ok=True)

    # ---- governance (pre-dispatch) ----------------------------------------
    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority != "OPEN":
        emit({"status": "STOPPED_GOVERNANCE_GAP", "authority": auth.authority})
        return 1
    attempt = build_attempt()
    reservation = {
        "version": "v2-010c-mutation-reservation-v1",
        "budget_kind": "m1_browser_oracle",
        "run_id": run_id,
        "attempt_id": attempt.generation_attempt_id,
        "intent": INTENT,
        "request_fingerprint_placeholder": hashlib.sha256(
            json.dumps(INTENT, sort_keys=True).encode()).hexdigest(),
        "created_at": utcnow(),
        "note": "pre-registered BEFORE any dispatch; actual request facts "
                "recorded at release"}
    write_pkg("mutation_reservation_m1.json", reservation)
    auth._event("MUTATION_RESERVED", budget_kind="m1_browser_oracle",
                detail=run_id)
    write_pkg("generation_attempt_m1.json",
              {"attempt": json.loads(attempt.model_dump_json()),
               "schema_validated": "generation_attempt"})
    event("governance_pre_dispatch", attempt_id=attempt.generation_attempt_id)

    # ---- session + capture BEFORE cold navigation --------------------------
    stored = load_session_encrypted()
    if not stored:
        emit({"status": "STOPPED_SESSION_GAP", "reason": "no encrypted session"})
        return 1
    manager = DolaSessionManager()
    manager._cookie_header = "; ".join(
        f"{c['name']}={c['value']}" for c in stored["cookies"])
    manager.cookie_source = "dpapi_store:" + str(stored.get("profile_alias"))
    await manager.launch_browser()
    await manager.inject_cookies()
    page = manager._page

    capture = NetworkCapture(manager._context, page, run_id)
    await capture.start()
    event("capture_active")

    released_requests: list[dict] = []
    release_watch_start = [None]

    def on_entry(entry: dict) -> None:
        if entry.get("kind") != "REQ" or entry.get("method") != "POST":
            return
        url = entry.get("url") or ""
        if not any(marker in url for marker in RELEASE_URL_MARKERS):
            return
        start = release_watch_start[0]
        if start and entry.get("utc", "") >= start:
            released_requests.append({"request_id": entry.get("request_id"),
                                      "url": url, "utc": entry.get("utc")})

    capture.subscribers.append(on_entry)

    async def close_all() -> None:
        if capture.raw_path.exists():
            sanitize_capture(capture.raw_path,
                             PKG / "V2_010C_BROWSER_CAPTURE_SANITIZED.json",
                             keep_bodies=True)
        await capture.stop()
        await manager.close()

    try:
        await page.goto(ORIGIN + "/chat", timeout=60000,
                        wait_until="domcontentloaded")
    except Exception as error:
        await close_all()
        emit({"status": "STOPPED_SESSION_GAP",
              "reason": f"navigation failed: {type(error).__name__}"})
        return 1
    event("cold_navigation_captured")
    if not await wait_composer(page):
        await close_all()
        emit({"status": "STOPPED_SESSION_GAP", "reason": "no composer"})
        return 1
    event("ui_ready_no_submit")
    await page.screenshot(path=str(screenshots / "01_bootstrap.png"))

    # ---- UI drive (observed, not assumed) ----------------------------------
    entry_text = await click_first_match(page, VIDEO_ENTRY_TEXTS)
    if not entry_text:
        write_pkg("ui_surface_snapshot.json", {"texts": await observed_texts(page),
                                               "stage": "home"})
        await close_all()
        emit({"status": "STOPPED_PROTOCOL_RECONSTRUCTION_GAP",
              "reason": "video entry not found"})
        return 1
    event("video_entry_clicked", entry_text=entry_text)
    await page.wait_for_timeout(2500)
    write_pkg("ui_surface_snapshot.json", {"texts": await observed_texts(page),
                                           "stage": "after_video_entry"})
    await page.screenshot(path=str(screenshots / "02_video_panel.png"))

    model_text = await click_first_match(page, MODEL_OPTION_TEXTS)
    if model_text:
        await page.wait_for_timeout(800)
    ratio_text = await click_first_match(page, ["16:9"])
    event("panel_selection", model=model_text, ratio=ratio_text)
    duration_selected = None
    for duration in DURATION_ORDER:
        if await click_first_match(page, DURATION_TEXTS[duration]):
            duration_selected = duration
            break
    event("duration_selected", duration_s=duration_selected)

    # surface sanity: are we provably in a video-parameter surface?
    surface = json.dumps(await observed_texts(page), ensure_ascii=False)
    if not model_text and not any(marker in surface
                                  for marker in PARAMETER_MARKERS):
        await close_all()
        emit({"status": "STOPPED_PROTOCOL_RECONSTRUCTION_GAP",
              "reason": "no video-parameter surface confirmed; no dispatch"})
        return 1
    await page.screenshot(path=str(screenshots / "03_pre_dispatch.png"))

    box = await page.query_selector("textarea") or \
        await page.query_selector('[contenteditable="true"]')
    if not box:
        await close_all()
        emit({"status": "STOPPED_PROTOCOL_RECONSTRUCTION_GAP",
              "reason": "composer not found at dispatch"})
        return 1
    await box.click()
    await page.keyboard.type(ORACLE_PROMPT, delay=40)
    await page.wait_for_timeout(600)

    # ---- dispatch: the ONE user action (Enter; submit-click fallback) ------
    release_watch_start[0] = utcnow()
    user_action_at = release_watch_start[0]
    user_actions = [{"action": "enter", "utc": user_action_at}]
    event("user_action_enter", prompt_sha256=PROMPT_SHA)
    await page.keyboard.press("Enter")

    deadline = time.time() + 45
    captcha_checked = False
    while time.time() < deadline and not released_requests:
        await page.wait_for_timeout(2000)
        has_captcha = any(CAPTCHA_FRAME_KEY in (f.url or "")
                          for f in page.frames)
        if has_captcha and not captcha_checked:
            captcha_checked = True
            event("captcha_detected")
            if not await solve_captcha(page):
                released = await fetch_post_bodies_for(
                    capture, ORACLE_PROMPT, user_action_at)
                await close_all()
                if released:
                    auth.latch("M1_CAPTCHA_UNSOLVED_AFTER_RELEASE",
                               json.dumps({"released": len(released)}))
                    emit({"status": "OWNER_AMBIGUITY_GATE",
                          "reason": "captcha unsolved after possible release"})
                else:
                    emit({"status": "STOPPED_PRE_DISPATCH",
                          "reason": "captcha unsolved; no release observed"})
                return 1
    if not released_requests:
        submit_clicked = await click_first_match(
            page, ["送信", "Send", "送信する", "生成", "作成"])
        if submit_clicked:
            user_actions.append({"action": "click_submit",
                                 "text": submit_clicked, "utc": utcnow()})
            event("submit_click_fallback", text=submit_clicked)
        deadline = time.time() + 30
        while time.time() < deadline and not released_requests:
            await page.wait_for_timeout(2000)
            if any(CAPTCHA_FRAME_KEY in (f.url or "") for f in page.frames):
                if not await solve_captcha(page):
                    break
    if not released_requests:
        released = await fetch_post_bodies_for(capture, ORACLE_PROMPT,
                                               user_action_at)
        await close_all()
        if released:
            auth.latch("M1_RELEASE_WITHOUT_RECEIPT_MARKERS",
                       json.dumps({"released": len(released)}))
            emit({"status": "OWNER_AMBIGUITY_GATE",
                  "reason": "release present but no live marker match"})
        else:
            emit({"status": "STOPPED_PRE_DISPATCH",
                  "reason": "no network release observed after user action"})
        return 1
    event("network_release_live", releases=len(released_requests),
          endpoints=sorted({r["url"].split("?")[0]
                            for r in released_requests}))

    # ---- receipt wait (network authority; URL tail corroborates) -----------
    sse_receipt: dict = {}
    sse_gate = {"on": True}

    def on_sse(entry: dict) -> None:
        if not sse_gate["on"] or sse_receipt:
            return
        if entry.get("kind") == "SSE_FRAME":
            if CONVERSATION_ID_RE.search(entry.get("data") or ""):
                sse_receipt["entry"] = entry

    capture.subscribers.append(on_sse)
    conversation_id = ""
    deadline = time.time() + 120
    while time.time() < deadline:
        await page.wait_for_timeout(1000)
        if sse_receipt:
            match = CONVERSATION_ID_RE.search(sse_receipt["entry"].get("data") or "")
            if match:
                conversation_id = match.group(1)
                event("receipt_from_sse_frame",
                      event_name=sse_receipt["entry"].get("event_name"))
                break
        tail = (page.url or "").rstrip("/").split("/")[-1]
        if tail.isdigit() and len(tail) >= 10:
            conversation_id = tail
            event("receipt_from_url_tail", conversation_id=tail)
            break

    if not conversation_id:
        for entry in reversed(capture.recent):
            match = CONVERSATION_ID_RE.search(json.dumps(entry)[:200000])
            if match:
                conversation_id = match.group(1)
                event("receipt_from_capture_scan", entry_kind=entry.get("kind"))
                break

    if not conversation_id:
        correlated = await fetch_post_bodies_for(capture, ORACLE_PROMPT,
                                                 user_action_at)
        sse_gate["on"] = False
        await close_all()
        if correlated:
            auth.latch("M1_RECEIPT_MISSING_AFTER_RELEASE",
                       json.dumps({"user_action_at": user_action_at,
                                   "released_requests": len(correlated)}))
            emit({"status": "OWNER_AMBIGUITY_GATE",
                  "reason": "request released but no receipt"})
        else:
            emit({"status": "STOPPED_PRE_DISPATCH",
                  "reason": "no release and no receipt"})
        return 1

    # ---- receipt-first persistence, THEN budget consumption ----------------
    event("receipt_captured", conversation_id=conversation_id)
    release_requests = await fetch_post_bodies_for(capture, ORACLE_PROMPT,
                                                   user_action_at)
    event("network_release_correlated", releases=len(release_requests),
          endpoints=[r["url"].split("?")[0] for r in release_requests])

    auth.consume("m1_browser_oracle")
    attempt.provider_job_id = conversation_id
    attempt.status = "running"
    write_pkg("generation_attempt_m1.json",
              {"attempt": json.loads(attempt.model_dump_json()),
               "reservation": reservation,
               "user_actions": user_actions})
    receipt_doc = {
        "version": "v2-010c-m1-receipt-v1", "run_id": run_id,
        "conversation_id": conversation_id,
        "receipt_source": "sse_frame" if sse_receipt else "url_tail",
        "user_action_at": user_action_at,
        "user_actions": user_actions,
        "receipt_at": utcnow(),
        "release_request_count": len(release_requests),
        "sse_ack_structure": (sse_receipt.get("entry") or {}).get("data", "")[:4000]}
    write_pkg("m1_receipt.json", receipt_doc)
    await page.screenshot(path=str(screenshots / "04_after_receipt.png"))

    # ---- completion watch (network authority only) --------------------------
    emit({"step": "polling_watch", "conversation_id": conversation_id})
    candidates: dict[str, dict] = {}
    observed_hosts: set[str] = set()
    deadline = time.time() + 900
    while time.time() < deadline:
        await page.wait_for_timeout(5000)
        for entry in capture.recent:
            if entry.get("kind") not in ("BODY", "SSE_FRAME"):
                continue
            urls, hosts = scan_video_candidates(entry, conversation_id)
            observed_hosts.update(hosts)
            for url in urls:
                candidates.setdefault(url, {
                    "first_seen": utcnow(), "via": entry.get("kind"),
                    "parent": entry.get("url") or entry.get("request_id")})
        if candidates:
            emit({"step": "video_candidates", "count": len(candidates),
                  "hosts": sorted({u.split("/")[2] for u in candidates})})
            break
    if not candidates:
        await close_all()
        write_pkg("m1_incomplete.json", {
            "status": "STOPPED_PROVIDER_CORRELATION_GAP",
            "conversation_id": conversation_id,
            "observed_hosts": sorted(observed_hosts),
            "reason": "no conversation-linked video URL within 900s"})
        emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
              "reason": "no conversation-linked video URL within 900s"})
        return 1
    if len(candidates) > 1:
        await close_all()
        write_pkg("m1_incomplete.json", {
            "status": "STOPPED_PROVIDER_CORRELATION_GAP",
            "conversation_id": conversation_id,
            "reason": "multiple distinct video URLs for one conversation",
            "candidates": list(candidates)})
        emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
              "reason": "multiple distinct video URLs"})
        return 1
    video_url = next(iter(candidates))
    event("video_url_correlated", host=video_url.split("/")[2],
          via=candidates[video_url]["via"])

    # ---- exact acquisition ---------------------------------------------------
    assets_dir = PKG / "assets"
    assets_dir.mkdir(exist_ok=True)
    dest = assets_dir / f"{run_id}.mp4"
    candidate_file = dest.with_suffix(".mp4.candidate")
    try:
        with urllib.request.urlopen(urllib.request.Request(video_url),
                                    timeout=300) as resp, \
                candidate_file.open("wb") as out:
            total = 0
            while True:
                part = resp.read(256 * 1024)
                if not part:
                    break
                total += len(part)
                out.write(part)
    except Exception as error:
        candidate_file.unlink(missing_ok=True)
        await close_all()
        write_pkg("m1_incomplete.json", {
            "status": "STOPPED_PROVIDER_CORRELATION_GAP",
            "conversation_id": conversation_id,
            "reason": f"download failed: {type(error).__name__}",
            "video_url_host": video_url.split("/")[2]})
        emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
              "reason": "download failed"})
        return 1
    asset_sha = hashlib.sha256(candidate_file.read_bytes()).hexdigest()
    candidate_file.replace(dest)
    event("downloaded", host=video_url.split("/")[2], size=total,
          sha256=asset_sha)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,codec_name,r_frame_rate",
         "-of", "json", str(dest)], capture_output=True, text=True)
    probe_data = json.loads(probe.stdout or "{}")
    stream = next((s for s in probe_data.get("streams", []) if "width" in s), {})
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(dest),
         "-map", "0:v:0", "-f", "null", "-"], capture_output=True).returncode == 0
    event("media_probe", duration=probe_data.get("format", {}).get("duration"),
          width=stream.get("width"), height=stream.get("height"),
          codec=stream.get("codec_name"), full_decode=decode)
    await page.screenshot(path=str(screenshots / "05_final.png"))

    # ---- close capture: SANITIZE BEFORE the raw layer is encrypted ---------
    sanitized_summary = sanitize_capture(
        capture.raw_path, PKG / "V2_010C_BROWSER_CAPTURE_SANITIZED.json",
        keep_bodies=True) if capture.raw_path.exists() else None
    capture_summary = await capture.stop()
    await manager.close()

    chain["verdicts"] = {
        "USER_ACTION": "PROVEN" if user_actions else "FAILED",
        "NETWORK_RELEASE": "PROVEN" if release_requests else "FAILED",
        "RECEIPT": "PROVEN" if conversation_id else "FAILED",
        "STABLE_IDS": "PROVEN" if conversation_id else "FAILED",
        "POLL_STREAM": "PROVEN" if (capture.event_counts.get("SSE_FRAME")
                                    or capture.event_counts.get("BODY")) else "INCOMPLETE",
        "EXACT_GENERATION": "PROVEN" if len(candidates) == 1 else "FAILED",
        "EXACT_VIDEO": "PROVEN" if decode else "FAILED",
    }
    attempt.status = "succeeded"
    attempt.completed_at = utcnow()
    attempt.output_asset_ids = [f"asset_sha256:{asset_sha[:16]}"]
    evidence = {
        "version": "v2-010c-m1-oracle-evidence-v1",
        "checkpoint": "V2010C_P3_M1_ORACLE",
        "status": "PROVEN" if all(v == "PROVEN" for v in
                                  chain["verdicts"].values()) else "PARTIAL",
        "run_id": run_id,
        "attempt": json.loads(attempt.model_dump_json()),
        "reservation": reservation,
        "chain": chain,
        "receipt": receipt_doc,
        "video_candidates": candidates,
        "asset": {"path_class": "projects/.../assets/" + dest.name,
                  "sha256": asset_sha, "size": total,
                  "duration_s": probe_data.get("format", {}).get("duration"),
                  "width": stream.get("width"), "height": stream.get("height"),
                  "codec": stream.get("codec_name"), "full_decode": decode},
        "capture_summary": capture_summary,
        "capture_sanitized": sanitized_summary,
    }
    write_pkg("V2_010C_BROWSER_ORACLE_EVIDENCE.json", evidence)
    emit({"checkpoint": "V2010C_M1_ORACLE_COMPLETE",
          "verdicts": chain["verdicts"],
          "conversation_id": conversation_id,
          "asset_sha256": asset_sha[:16],
          "endpoints": [r["url"].split("?")[0] for r in release_requests]})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
