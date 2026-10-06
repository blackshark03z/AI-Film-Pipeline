"""AI-FILM-QUALITY-V2-010C — M2 browser VIDEO qualification (optional slot).

ONE authorized browser video generation through the reconstructed current
transport (UI trigger + network authority in the managed authenticated
browser runtime). Proves the full VIDEO lineage end-to-end:

    USER ACTION → POST /chat/completion release → SSE_ACK receipt
      → stable IDs (question/message/creation) → creation card
      → completion (poll /im/chain/single, correct uplink schema)
      → type-2 creation with download_url → EXACT VIDEO sha256

M1 (image-class) proved dispatch/receipt/IDs/output-correlation; M2 proves
the video-output stage. All request facts are persisted IMMEDIATELY at
correlation (receipt-first ordering).
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
from dola_010c_session import (ORIGIN, PKG, DolaSessionManager,
                               load_session_encrypted)
from film_pipeline.core import GenerationAttempt
from film_pipeline.execution import sha256
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-010C-DOLA-FULLSTACK"
CONVERSATION_ID = "38417972940811793"
M2_PROMPT = ("Turn the first lighthouse image into a short 5-second "
             "cinematic video with gentle waves and sunrise light movement")
PROMPT_SHA = hashlib.sha256(M2_PROMPT.encode("utf-8")).hexdigest()
SHOT_ID = "V2_010C_M2_VIDEO_QUAL"
BUDGET_KIND = "m2_browser_video_qualification"

CONVERSATION_ID_RE = re.compile(r'"conversation_id"\s*:\s*"(\d{10,})"')

POLL_JS = """async ({conversationId}) => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1", doubao_pc_version: "3.39.1",
    region: "VN", sys_region: "VN", samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const resp = await fetch("/im/chain/single?" + params.toString(), {
    method: "POST",
    headers: {"Content-Type": "application/json; encoding=utf-8",
              "agw-js-conv": "str",
              "Accept": "application/json, text/plain, */*"},
    body: JSON.stringify({
      cmd: 3100,
      uplink_body: {pull_singe_chain_uplink_body: {
        conversation_id: conversationId,
        anchor_index: Number.MAX_SAFE_INTEGER,
        conversation_type: 3,
        direction: 1,
        limit: 20,
        ext: {},
        filter: {index_list: []},
        evaluate_ab_params: "",
        evaluate_common_params: "",
      }},
      sequence_id: crypto.randomUUID(),
      channel: 2,
      version: "1",
    }),
    credentials: "include",
  });
  if (!resp.ok) return {ok: false, status: resp.status, replies: []};
  const data = await resp.json();
  const messages = ((data.downlink_body || {})
    .pull_singe_chain_downlink_body || {}).messages || [];
  const replies = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
    }
    for (const block of (Array.isArray(blocks) ? blocks : [])) {
      if (block.block_type !== 2074) continue;
      const cb = (block.content || {}).creation_block || {};
      for (const c of (cb.creations || [])) {
        replies.push({
          message_id: String(m.message_id),
          local_message_id: m.local_message_id || null,
          reply_to: m.reply_to_message_id || m.parent_message_id || null,
          creation_id: c.id ? String(c.id) : null,
          type: c.type,
          video_status: (c.video || {}).status ?? null,
          video_download_url: (c.video || {}).download_url || null,
        });
      }
    }
  }
  return {ok: true, status: resp.status, replies};
}"""


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
        "shot_spec_hash": sha256({"shot_id": SHOT_ID,
                                  "purpose": "M2 video qualification"}),
        "prompt_plan_hash": sha256({"prompt_sha256": PROMPT_SHA}),
        "routing_decision_id": "route_v2_010c_browser_network",
        "provider_id": "seedance_dola",
        "request_id": "m2_video_qual",
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


async def main() -> int:
    run_id = "m2_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    chain = {"run_id": run_id, "prompt_sha256": PROMPT_SHA, "events": [],
             "verdicts": {}}

    def event(step: str, **data) -> None:
        chain["events"].append({"step": step, "utc": utcnow(), **data})
        emit({"event": step, **data})

    screenshots = PKG / "screenshots_m2"
    screenshots.mkdir(parents=True, exist_ok=True)

    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority != "OPEN":
        emit({"status": "STOPPED_GOVERNANCE_GAP", "authority": auth.authority})
        return 1
    attempt = build_attempt()
    reservation = {
        "version": "v2-010c-mutation-reservation-v1",
        "budget_kind": BUDGET_KIND, "run_id": run_id,
        "attempt_id": attempt.generation_attempt_id,
        "intent": {"prompt_sha256": PROMPT_SHA,
                   "conversation_id": CONVERSATION_ID,
                   "target": "5-second video from M1 keyframe",
                   "purpose": "M2 browser video qualification"},
        "request_fingerprint_placeholder": hashlib.sha256(
            json.dumps({"prompt_sha256": PROMPT_SHA}, sort_keys=True)
            .encode()).hexdigest(),
        "created_at": utcnow()}
    write_pkg("mutation_reservation_m2.json", reservation)
    auth._event("MUTATION_RESERVED", budget_kind=BUDGET_KIND, detail=run_id)
    event("governance_pre_dispatch", attempt_id=attempt.generation_attempt_id)

    stored = load_session_encrypted()
    if not stored:
        emit({"status": "STOPPED_SESSION_GAP", "reason": "no encrypted session"})
        return 1
    manager = DolaSessionManager()
    manager._cookie_header = "; ".join(
        f"{c['name']}={c['value']}" for c in stored["cookies"])
    manager.cookie_source = "dpapi_store"
    await manager.launch_browser()
    await manager.inject_cookies()
    page = manager._page

    capture = NetworkCapture(manager._context, page, run_id)
    await capture.start()
    event("capture_active")

    async def close_all() -> None:
        if capture.raw_path.exists():
            sanitize_capture(capture.raw_path,
                             PKG / "V2_010C_M2_CAPTURE_SANITIZED.json")
        await capture.stop()
        await manager.close()

    # ---- pre-dispatch baseline poll (read-only) ---------------------------
    try:
        await page.goto(f"{ORIGIN}/chat/{CONVERSATION_ID}", timeout=60000,
                        wait_until="domcontentloaded")
    except Exception as error:
        await close_all()
        emit({"status": "STOPPED_SESSION_GAP",
              "reason": f"navigation failed: {type(error).__name__}"})
        return 1
    await page.wait_for_timeout(6000)
    baseline = await page.evaluate(POLL_JS, {"conversationId": CONVERSATION_ID})
    known_creation_ids = {r.get("creation_id") for r in baseline.get("replies", [])}
    known_message_ids = {r.get("message_id") for r in baseline.get("replies", [])}
    event("baseline_poll", existing_creations=len(known_creation_ids),
          existing_messages=len(known_message_ids))

    # ---- dispatch ----------------------------------------------------------
    box = await page.query_selector("textarea") or \
        await page.query_selector('[contenteditable="true"]')
    if not box:
        await close_all()
        emit({"status": "STOPPED_PROTOCOL_RECONSTRUCTION_GAP",
              "reason": "no composer in conversation"})
        return 1
    await box.click()
    await page.keyboard.type(M2_PROMPT, delay=40)
    await page.wait_for_timeout(600)
    user_action_at = utcnow()
    event("user_action_enter", prompt_sha256=PROMPT_SHA)
    await page.keyboard.press("Enter")
    await page.screenshot(path=str(screenshots / "01_dispatched.png"))

    # ---- receipt (SSE ack / URL tail) ---------------------------------------
    conversation_ok = False
    deadline = time.time() + 60
    while time.time() < deadline and not conversation_ok:
        await page.wait_for_timeout(1000)
        conversation_ok = CONVERSATION_ID.lower() in (page.url or "").lower()
    if not conversation_ok:
        await close_all()
        emit({"status": "STOPPED_PRE_DISPATCH",
              "reason": "conversation context lost after submit"})
        return 1

    # correlate the released request IMMEDIATELY (receipt-first facts)
    release_requests = []
    seen_ids: set[str] = set()
    for entry in capture.recent:
        if entry.get("kind") != "REQ" or entry.get("method") != "POST":
            continue
        if entry.get("utc", "") < user_action_at:
            continue
        if "/chat/completion" not in (entry.get("url") or ""):
            continue
        rid = entry.get("request_id")
        if not rid or rid in seen_ids:
            continue
        seen_ids.add(rid)
        post_data = await capture.get_post_data(rid)
        if post_data and M2_PROMPT[:20] in post_data:
            body = post_data.encode("utf-8")
            release_requests.append({
                "request_id": rid,
                "url": SIGNED_URL_QUERY_RE.sub(r"\1=REDACTED",
                                               entry.get("url", "")),
                "query_params": {k: ("<REDACTED>" if k in
                                     ("msToken", "a_bogus", "fp") else v)
                                 for k, v in ([part.split("=", 1) for part in
                                               entry.get("url", "").split("?")[-1]
                                               .split("&") if "=" in part])},
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "body_len": len(body),
                "utc": entry.get("utc"),
                "body_structure": json.loads(post_data)
                if post_data.startswith("{") else None})
    if not release_requests:
        await close_all()
        emit({"status": "STOPPED_PRE_DISPATCH",
              "reason": "no /chat/completion release with prompt observed"})
        return 1
    event("network_release_correlated", releases=len(release_requests))

    receipt_doc = {
        "version": "v2-010c-m2-receipt-v1", "run_id": run_id,
        "conversation_id": CONVERSATION_ID,
        "user_action_at": user_action_at, "receipt_at": utcnow(),
        "release_request_count": len(release_requests)}
    write_pkg("m2_receipt.json", receipt_doc)
    auth.consume(BUDGET_KIND)
    attempt.provider_job_id = CONVERSATION_ID
    attempt.status = "running"
    write_pkg("generation_attempt_m2.json", {
        "attempt": json.loads(attempt.model_dump_json()),
        "reservation": reservation,
        "release_requests": release_requests})
    event("receipt_first_persisted_and_budget_consumed")

    # ---- completion poll (network authority; creation-id correlation) ------
    new_records: list[dict] = []
    deadline = time.time() + 1500
    last_state = 0
    while time.time() < deadline:
        await page.wait_for_timeout(6000)
        try:
            poll = await page.evaluate(POLL_JS, {"conversationId": CONVERSATION_ID})
        except Exception:
            continue
        if not poll.get("ok"):
            continue
        fresh = [r for r in poll.get("replies", [])
                 if r.get("creation_id") not in known_creation_ids
                 and r.get("message_id") not in known_message_ids]
        done = [r for r in fresh if r.get("type") == 2 and
                r.get("video_download_url")]
        if len(fresh) != last_state:
            last_state = len(fresh)
            event("poll_progress", new_records=len(fresh),
                  done_videos=len(done))
        if done:
            new_records = done
            break
    if not new_records:
        await close_all()
        write_pkg("m2_incomplete.json", {
            "status": "STOPPED_PROVIDER_CORRELATION_GAP",
            "conversation_id": CONVERSATION_ID,
            "reason": "no NEW type-2 creation with download_url within 1500s"})
        emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
              "reason": "no new completed video within 1500s"})
        return 1
    # determinism: all completed NEW records must agree on one video URL
    urls = {r["video_download_url"] for r in new_records}
    if len(urls) != 1:
        await close_all()
        write_pkg("m2_incomplete.json", {
            "status": "STOPPED_PROVIDER_CORRELATION_GAP",
            "reason": "multiple distinct download URLs for the new video",
            "urls": len(urls)})
        emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
              "reason": "multiple distinct download URLs"})
        return 1
    video_url = urls.pop()
    event("video_url_correlated",
          host=video_url.split("/")[2] if "/" in video_url else "?",
          records=len(new_records),
          message_ids=sorted({r["message_id"] for r in new_records}),
          creation_ids=sorted({r["creation_id"] for r in new_records}))

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
        write_pkg("m2_incomplete.json", {
            "status": "STOPPED_PROVIDER_CORRELATION_GAP",
            "reason": f"download failed: {type(error).__name__}",
            "video_url_host": video_url.split("/")[2] if "/" in video_url else "?"})
        emit({"status": "STOPPED_PROVIDER_CORRELATION_GAP",
              "reason": "download failed"})
        return 1
    asset_sha = hashlib.sha256(candidate_file.read_bytes()).hexdigest()
    candidate_file.replace(dest)
    event("downloaded", size=total, sha256=asset_sha)

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
    await page.screenshot(path=str(screenshots / "02_completed.png"))

    sanitized_summary = sanitize_capture(
        capture.raw_path, PKG / "V2_010C_M2_CAPTURE_SANITIZED.json") \
        if capture.raw_path.exists() else None
    capture_summary = await capture.stop()
    await manager.close()

    chain["verdicts"] = {
        "USER_ACTION": "PROVEN" if user_action_at else "FAILED",
        "NETWORK_RELEASE": "PROVEN" if release_requests else "FAILED",
        "RECEIPT": "PROVEN",
        "STABLE_IDS": "PROVEN" if new_records else "FAILED",
        "POLL_STREAM": "PROVEN",
        "EXACT_GENERATION": "PROVEN" if len(urls | {video_url}) == 1 else "FAILED",
        "EXACT_VIDEO": "PROVEN" if decode else "FAILED",
    }
    attempt.status = "succeeded"
    attempt.completed_at = utcnow()
    attempt.output_asset_ids = [f"asset_sha256:{asset_sha[:16]}"]
    evidence = {
        "version": "v2-010c-m2-qualification-evidence-v1",
        "checkpoint": "V2010C_P6_M2_VIDEO_QUALIFICATION",
        "status": "PROVEN" if all(v == "PROVEN" for v in
                                  chain["verdicts"].values()) else "PARTIAL",
        "run_id": run_id,
        "attempt": json.loads(attempt.model_dump_json()),
        "reservation": reservation,
        "chain": chain,
        "receipt": receipt_doc,
        "release_request_facts": [{k: v for k, v in r.items()
                                   if k != "body_structure"}
                                  for r in release_requests],
        "video_records": new_records,
        "asset": {"path_class": "projects/.../assets/" + dest.name,
                  "sha256": asset_sha, "size": total,
                  "duration_s": probe_data.get("format", {}).get("duration"),
                  "width": stream.get("width"), "height": stream.get("height"),
                  "codec": stream.get("codec_name"), "full_decode": decode},
        "capture_summary": capture_summary,
        "capture_sanitized": sanitized_summary,
    }
    write_pkg("V2_010C_M2_QUALIFICATION_EVIDENCE.json", evidence)
    emit({"checkpoint": "V2010C_M2_QUALIFICATION_COMPLETE",
          "verdicts": chain["verdicts"], "asset_sha256": asset_sha[:16],
          "duration_s": probe_data.get("format", {}).get("duration")})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
