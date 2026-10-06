"""V2-011D — post-latch READ-ONLY reconciliation for F3R on ACCOUNT_A.

The F3R release is durable (journal NETWORK_RELEASE_OBSERVED, 5s chip
verified, needle present). The SSE receipt was not captured within 120s →
OWNER_AMBIGUITY_GATE latched (one-way, per frozen invariant). This tool
resolves the external-effect knowledge READ-ONLY: find the F3R conversation
by prompt needle, wait for the type-2 creation, acquire the exact video,
hash-verify, extract full 24fps frames. No dispatch is possible or attempted
(the latch stays closed; downloads are asset acquisition).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import ACCOUNT_PROFILES
from dola_010e_dispatch_journal import DispatchJournal
from mutation_authority import MutationAuthority

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
JOURNAL = PKG / "dispatch_journal_f3r.jsonl"
SLOT = PKG / "slot_f3r"
SPEC = json.loads(
    (PKG / "V2_011D_F3R_SPEC.json").read_text(encoding="utf-8"))
# needle must fall within the FIRST ~260 chars of the prompt text: the
# conversation poll slices each message's text to 300 chars, and the UI may
# split long prompts across text blocks — the head is the reliable anchor
# (same convention as the 011R runner's spec_prompt[:40] discovery needle)
PROMPT_NEEDLE = "Medium close-up portrait:"
RELEASE_NOTE = "F3R release durable in dispatch_journal_f3r.jsonl (NETWORK_RELEASE_OBSERVED, 5s chip, needle present)"

TIMELINE_JS = """async () => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
    samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const headers = {"Content-Type": "application/json; encoding=utf-8",
                   "agw-js-conv": "str",
                   "Accept": "application/json, text/plain, */*"};
  const recent = await fetch("/im/chain/recent_conv?" + params.toString(), {
    method: "POST", headers, credentials: "include",
    body: JSON.stringify({cmd: 3200, uplink_body: {
      pull_recent_conv_chain_uplink_body: {limit: 20,
        message_count_per_conv: 2, api_version: 1, conv_version: 0,
        direction: 3, option: {not_need_message: false,
          need_complete_conversation: true, need_coco_conversation: true,
          need_coco_bot: true, need_pc_pin_chain: true,
          pc_pin_query_type: 0}}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  const data = await recent.json();
  const cells = ((data.downlink_body || {})
    .pull_recent_conv_chain_downlink_body || {}).cells || [];
  return cells.map(c => ({id: (c.conversation || {}).conversation_id ||
                          c.id || ""})).filter(c => /^\\d{10,}$/.test(c.id));
}"""

PULL_JS = """async ({conversationId}) => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
    samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const resp = await fetch("/im/chain/single?" + params.toString(), {
    method: "POST",
    headers: {"Content-Type": "application/json; encoding=utf-8",
              "agw-js-conv": "str",
              "Accept": "application/json, text/plain, */*"},
    credentials: "include",
    body: JSON.stringify({cmd: 3100,
      uplink_body: {pull_singe_chain_uplink_body: {
        conversation_id: conversationId,
        anchor_index: Number.MAX_SAFE_INTEGER, conversation_type: 3,
        direction: 1, limit: 10, ext: {}, filter: {index_list: []},
        evaluate_ab_params: "", evaluate_common_params: ""}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  const data = await resp.json();
  const messages = ((data.downlink_body || {})
    .pull_singe_chain_downlink_body || {}).messages || [];
  const rows = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
    }
    let text = "";
    const creations = [];
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type === 2074) {
        for (const c of (((b.content || {}).creation_block || {})
            .creations || [])) {
          creations.push({id: c.id ? String(c.id) : null, type: c.type,
            v_status: (c.video || {}).status ?? null,
            download_url: (c.video || {}).download_url || null});
        }
      } else if (b.block_type === 10000) {
        text += (((b.content || {}).text_block || {}).text || "");
      }
    }
    rows.push({message_id: String(m.message_id),
               create_time: m.create_time, text: text.slice(0, 300),
               creations});
  }
  return rows;
}"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    auth = MutationAuthority(SLOT, "QUALITY-V2-011D-WORLD-MATCHED-CONTEXT/F3R")
    journal = DispatchJournal(JOURNAL, "attempt_f3r_reconcile")
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_D")
    await manager.launch_browser()
    page = manager._page
    result = {"version": "v2-011d-reconciliation-v1",
              "shot": "F3R",
              "started_at": utcnow(),
              "mode": "READ_ONLY (latch closed; acquisition only)",
              "release_note": RELEASE_NOTE}
    try:
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        for _ in range(15):
            try:
                if await page.evaluate(
                        """() => !!(document.querySelector('textarea')
                                || document.querySelector('[contenteditable="true"]'))"""):
                    break
            except Exception:
                pass
            await page.wait_for_timeout(1000)

        f3r_conv = None
        f3r_reply = None
        refusal_texts = None
        deadline = asyncio.get_event_loop().time() + 1800
        attempt = 0
        while asyncio.get_event_loop().time() < deadline:
            attempt += 1
            try:
                convs = await page.evaluate(TIMELINE_JS)
            except Exception as error:
                emit({"step": "recent_conv_retry",
                      "error": type(error).__name__})
                await page.wait_for_timeout(5000)
                continue
            for conv in convs[:6]:
                try:
                    rows = await page.evaluate(
                        PULL_JS, {"conversationId": conv["id"]})
                except Exception:
                    continue
                for row in rows:
                    if PROMPT_NEEDLE in (row.get("text") or ""):
                        f3r_conv = conv["id"]
                        done = [c for c in (row.get("creations") or [])
                                if c.get("type") == 2 and
                                c.get("download_url")]
                        if done:
                            f3r_reply = done
                if f3r_conv == conv["id"]:
                    newest = [r.get("text", "")[:130] for r in rows[:4]]
                    if attempt % 3 == 1:
                        emit({"step": "f3r_conv_state", "attempt": attempt,
                              "creations": [
                                  {k: c.get(k) for k in ("id", "type",
                                                         "v_status")}
                                  for r in rows
                                  for c in (r.get("creations") or [])],
                              "texts": newest})
                    refusal = any("生成できません" in (r.get("text") or "")
                                  for r in rows[:4])
                    if refusal and not any(
                            r.get("creations") for r in rows[:4]):
                        refusal_texts = newest
                if f3r_reply:
                    break
            if f3r_reply or refusal_texts:
                break
            await page.wait_for_timeout(10000)

        result["f3r_conversation_id"] = f3r_conv
        if refusal_texts and not f3r_reply:
            result["status"] = "RESOLVED_EFFECT_IDENTIFIED_PROVIDER_REFUSAL"
            result["refusal_texts"] = refusal_texts
            auth.record_knowledge(
                "RESOLVED_EFFECT_IDENTIFIED",
                "provider refused the released F3R request — no asset")
            (PKG / "V2_011D_F3R_RECONCILIATION.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": result["status"]})
            return 1
        if not f3r_reply:
            result["status"] = "UNRESOLVED_NO_COMPLETED_VIDEO"
            result["note"] = ("no type-2 creation with download_url appeared "
                              "within the read-only window; latch stays "
                              "closed; re-run this tool to keep polling")
            (PKG / "V2_011D_F3R_RECONCILIATION.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": result["status"]})
            return 1
        urls = {r["download_url"] for r in f3r_reply}
        if len(urls) != 1:
            result["status"] = "UNRESOLVED_MULTIPLE_URLS"
            result["urls"] = len(urls)
            (PKG / "V2_011D_F3R_RECONCILIATION.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": result["status"]})
            return 1
        video_url = urls.pop()
        creation_ids = sorted({str(r["id"]) for r in f3r_reply})
        assets = PKG / "assets"
        assets.mkdir(exist_ok=True)
        dest = assets / "f3r.mp4"
        candidate = dest.with_suffix(".mp4.candidate")
        with urllib.request.urlopen(urllib.request.Request(video_url),
                                    timeout=300) as resp, \
                candidate.open("wb") as out:
            total = 0
            while True:
                part = resp.read(256 * 1024)
                if not part:
                    break
                total += len(part)
                out.write(part)
        asset_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
        candidate.replace(dest)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height,codec_name,r_frame_rate,nb_frames",
             "-of", "json", str(dest)], capture_output=True, text=True)
        meta = json.loads(probe.stdout or "{}")
        stream = next((s for s in meta.get("streams", [])
                       if "width" in s), {})
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-i", str(dest),
             "-map", "0:v:0", "-f", "null", "-"], capture_output=True
        ).returncode == 0
        frames_dir = PKG / "frames_f3r"
        frames_dir.mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(dest),
                        "-vsync", "0", "-start_number", "0",
                        str(frames_dir / "F3R_%04d.png")], capture_output=True)
        n_frames = len(list(frames_dir.glob("F3R_*.png")))
        result.update({
            "status": "RESOLVED_EFFECT_IDENTIFIED",
            "f3r_conversation_id": f3r_conv,
            "creation_ids": creation_ids,
            "asset": {"path": str(dest), "sha256": asset_sha,
                      "size": total, "host": video_url.split("/")[2],
                      "duration_s": meta.get("format", {}).get("duration"),
                      "width": stream.get("width"),
                      "height": stream.get("height"),
                      "codec": stream.get("codec_name"),
                      "fps": stream.get("r_frame_rate"),
                      "nb_frames": stream.get("nb_frames"),
                      "full_decode": decode},
            "frames_extracted": n_frames})
        auth.record_knowledge(
            "RESOLVED_EFFECT_IDENTIFIED",
            f"released F3R produced its completed video; acquired "
            f"sha256 {asset_sha[:16]}…; frames {n_frames}")
        (PKG / "V2_011D_F3R_RECONCILIATION.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False),
            encoding="utf-8")
        emit({"checkpoint": "V2011D_F3R_RECONCILED",
              "sha256": asset_sha[:16],
              "duration": result["asset"]["duration_s"],
              "frames": n_frames, "decode": decode})
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
