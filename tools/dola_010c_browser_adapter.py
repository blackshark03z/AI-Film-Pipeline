"""AI-FILM-QUALITY-V2-010C — Layer 8: production browser adapter.

DolaBrowserNetworkAdapter — the evidence-selected transport (Route B/C
hybrid): managed authenticated browser runtime (DOLA_RE_PROFILE) with UI
trigger ONLY for dispatch, network authority for EVERY identity:

    receipt   = SSE_ACK ack_client_meta.conversation_id (+ URL corroboration)
    job       = creation ids from the STREAM_CHUNK card / poll
    output    = type-2 creation video.download_url from /im/chain/single
    download  = signed CDN URL (transport-only, never persisted)

Everything identity-bearing comes from captured network facts — Film Core
never depends on DOM selectors for identity. Governed callers reserve and
consume MutationAuthority budgets receipt-first.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dola_010c_capture import NetworkCapture, SIGNED_URL_QUERY_RE
from dola_010c_session import ORIGIN, DolaSessionManager, load_session_encrypted

SEEDANCE_CONVERSATION_ID = "38417972940811793"
VIDEO_MODE_TEXTS = ["動画を作成", "Create video", "创建视频", "影片生成"]
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
  if (!resp.ok) return {ok: false, status: resp.status, replies: [], texts: []};
  const data = await resp.json();
  const messages = ((data.downlink_body || {})
    .pull_singe_chain_downlink_body || {}).messages || [];
  const replies = [];
  const texts = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
    }
    for (const block of (Array.isArray(blocks) ? blocks : [])) {
      if (block.block_type === 2074) {
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
      } else if (block.block_type === 10000) {
        const t = ((block.content || {}).text_block || {}).text;
        if (t) texts.push(String(t).slice(0, 400));
      }
    }
  }
  return {ok: true, status: resp.status, replies, texts};
}"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DolaBrowserAdapter:
    """One governed browser transport session (submit/poll/download)."""

    provider = "seedance_dola_browser"

    def __init__(self, *, run_id: str, capture_raw_dir: Path | None = None) -> None:
        self.run_id = run_id
        self.manager = DolaSessionManager()
        self.capture: NetworkCapture | None = None
        self.page = None
        self.events: list[dict] = []

    def event(self, step: str, **data) -> None:
        self.events.append({"step": step, "utc": utcnow(), **data})

    # ---- lifecycle ---------------------------------------------------------

    async def open(self) -> None:
        stored = load_session_encrypted()
        if not stored:
            raise RuntimeError("SESSION_GAP: no encrypted session")
        self.manager._cookie_header = "; ".join(
            f"{c['name']}={c['value']}" for c in stored["cookies"])
        self.manager.cookie_source = "dpapi_store"
        await self.manager.launch_browser()
        await self.manager.inject_cookies()
        self.page = self.manager._page
        self.capture = NetworkCapture(self.manager._context, self.page,
                                      self.run_id)
        await self.capture.start()
        self.event("capture_active")

    async def close(self, *, sanitize_to: Path | None = None) -> dict:
        summary: dict = {}
        if self.capture:
            if sanitize_to and self.capture.raw_path.exists():
                from dola_010c_capture import sanitize_capture
                summary["sanitized"] = sanitize_capture(
                    self.capture.raw_path, sanitize_to)
            summary["stop"] = await self.capture.stop()
        await self.manager.close()
        return summary

    # ---- surface -----------------------------------------------------------

    async def goto_conversation(self, conversation_id: str) -> None:
        await self.page.goto(f"{ORIGIN}/chat/{conversation_id}",
                             timeout=60000, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(6000)
        self.event("conversation_open", conversation_id=conversation_id)

    async def enable_video_mode(self) -> str | None:
        """Click the composer video-mode button; returns the matched text."""
        for text in VIDEO_MODE_TEXTS:
            try:
                locator = self.page.get_by_text(text, exact=True).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=5000)
                    await self.page.wait_for_timeout(1200)
                    self.event("video_mode_selected", text=text)
                    return text
            except Exception:
                continue
        self.event("video_mode_not_found")
        return None

    async def attach_reference(self, image_path: Path,
                               timeout_s: int = 90) -> bool:
        """Upload a reference image through the native file input; wait for
        the TOS upload responses. Returns False when the surface is absent."""
        try:
            file_input = self.page.locator('input[type="file"]').first
            await file_input.wait_for(state="attached", timeout=15000)
        except Exception:
            self.event("reference_input_absent")
            return False
        uploads = {"prepare": 0, "tos": 0}

        def on_response(response):
            url = response.url
            if "/alice/resource/prepare_upload" in url:
                uploads["prepare"] += 1
            if "/upload/v1/" in url:
                uploads["tos"] += 1

        self.page.on("response", on_response)
        try:
            await file_input.set_input_files(str(image_path))
            deadline = asyncio.get_event_loop().time() + timeout_s
            while asyncio.get_event_loop().time() < deadline:
                if uploads["prepare"] >= 1 and uploads["tos"] >= 1:
                    await self.page.wait_for_timeout(1500)
                    self.event("reference_uploaded", **uploads)
                    return True
                await self.page.wait_for_timeout(500)
            self.event("reference_upload_timeout", **uploads)
            return False
        except Exception as error:
            self.event("reference_upload_error", error=type(error).__name__)
            return False
        finally:
            self.page.remove_listener("response", on_response)

    async def baseline_creations(self, conversation_id: str) -> set[str]:
        poll = await self.page.evaluate(POLL_JS,
                                        {"conversationId": conversation_id})
        return {r.get("creation_id") for r in poll.get("replies", [])}

    # ---- dispatch ----------------------------------------------------------

    async def submit(self, prompt: str, *, conversation_id: str,
                     expected_needle: str | None = None) -> dict:
        """UI trigger (type + Enter) + network-release correlation.
        Receipt-first: caller persists the returned facts BEFORE consuming
        any budget. Raises RuntimeError on pre-dispatch failures."""
        box = await self.page.query_selector("textarea") or \
            await self.page.query_selector('[contenteditable="true"]')
        if not box:
            raise RuntimeError("DISPATCH_GAP: composer not found")
        await box.click()
        await self.page.keyboard.type(prompt, delay=30)
        await self.page.wait_for_timeout(600)
        user_action_at = utcnow()
        self.event("user_action_enter")
        await self.page.keyboard.press("Enter")

        # correlate the released /chat/completion request (body + hashes)
        deadline = asyncio.get_event_loop().time() + 60
        release = None
        while asyncio.get_event_loop().time() < deadline and not release:
            await self.page.wait_for_timeout(1000)
            for entry in self.capture.recent:
                if entry.get("kind") != "REQ" or entry.get("method") != "POST":
                    continue
                if entry.get("utc", "") < user_action_at:
                    continue
                if "/chat/completion" not in (entry.get("url") or ""):
                    continue
                post_data = await self.capture.get_post_data(
                    entry.get("request_id"))
                needle = expected_needle or prompt
                if post_data and needle[:20] in post_data:
                    body = post_data.encode("utf-8")
                    release = {
                        "request_id": entry.get("request_id"),
                        "url": SIGNED_URL_QUERY_RE.sub(
                            r"\1=REDACTED", entry.get("url", "")),
                        "body_sha256": hashlib.sha256(body).hexdigest(),
                        "body_len": len(body),
                        "utc": entry.get("utc"),
                        "body_structure": json.loads(post_data)
                        if post_data.startswith("{") else None}
        if not release:
            raise RuntimeError("DISPATCH_GAP: no /chat/completion release "
                               "observed after user action")
        self.event("network_release_correlated",
                   request_id=release["request_id"],
                   body_sha256=release["body_sha256"])
        return {"user_action_at": user_action_at, "release": release,
                "receipt_at": utcnow()}

    # ---- progress ----------------------------------------------------------

    async def poll_replies(self, conversation_id: str) -> dict:
        return await self.page.evaluate(POLL_JS,
                                        {"conversationId": conversation_id})

    async def wait_for_new_video(self, conversation_id: str, *,
                                 known_creation_ids: set[str],
                                 known_message_ids: set[str],
                                 timeout_s: int = 1500,
                                 on_progress=None) -> list[dict]:
        """Network-authority completion wait: NEW type-2 creations with
        download_url, correlated by creation/message ids absent from the
        pre-dispatch baseline."""
        deadline = asyncio.get_event_loop().time() + timeout_s
        last_state = None
        while asyncio.get_event_loop().time() < deadline:
            await self.page.wait_for_timeout(6000)
            try:
                poll = await self.poll_replies(conversation_id)
            except Exception:
                continue
            if not poll.get("ok"):
                continue
            fresh = [r for r in poll.get("replies", [])
                     if r.get("creation_id") not in known_creation_ids
                     and r.get("message_id") not in known_message_ids]
            done = [r for r in fresh if r.get("type") == 2
                    and r.get("video_download_url")]
            if on_progress and len(fresh) != last_state:
                last_state = len(fresh)
                on_progress(len(fresh), len(done))
            if done:
                return done
        return []

    # ---- acquisition ---------------------------------------------------------

    async def download(self, video_url: str, destination: Path) -> dict:
        """Exact acquisition of the correlated output; signed URL is
        transport-only and never persisted anywhere."""

        def _fetch() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            candidate = destination.with_suffix(destination.suffix + ".candidate")
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(video_url), timeout=300) as resp, \
                        candidate.open("wb") as out:
                    total = 0
                    while True:
                        part = resp.read(256 * 1024)
                        if not part:
                            break
                        total += len(part)
                        out.write(part)
                sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
                candidate.replace(destination)
                self.event("downloaded", size=total, sha256=sha)
            except Exception:
                candidate.unlink(missing_ok=True)
                raise

        await asyncio.to_thread(_fetch)
        return self.probe(destination)

    @staticmethod
    def probe(path: Path) -> dict:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height,codec_name,r_frame_rate",
             "-of", "json", str(path)], capture_output=True, text=True)
        data = json.loads(probe.stdout or "{}")
        stream = next((s for s in data.get("streams", [])
                       if "width" in s), {})
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
             "-map", "0:v:0", "-f", "null", "-"],
            capture_output=True).returncode == 0
        return {"duration_s": data.get("format", {}).get("duration"),
                "width": stream.get("width"), "height": stream.get("height"),
                "codec": stream.get("codec_name"),
                "fps": stream.get("r_frame_rate"), "full_decode": decode,
                "size": path.stat().st_size}
