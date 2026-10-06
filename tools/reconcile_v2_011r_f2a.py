"""V2-010E — post-crash READ-ONLY reconciliation on ACCOUNT_A.

The F2B_010E release is durable (journal NETWORK_RELEASE_OBSERVED at
2026-10-06T05:30:04Z, request 16212.1692). The runner crashed on a regex
template bug AFTER release; the scope is latched. This tool resolves the
external-effect knowledge read-only: find the F2B conversation on
ACCOUNT_A, wait for the type-2 creation, acquire the exact video, and
record the deterministic lineage. No mutation is possible or attempted
(latch stays closed; downloads are asset acquisition).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
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

PKG = ROOT / "projects/quality_v2_011r_targeted_repair"
JOURNAL = PKG / "dispatch_journal_f2b_010e.jsonl"
RELEASE_UTC = "2026-10-06T06:32"
PROMPT_NEEDLE = "the shot ends while he is inside that gap"

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
        direction: 1, limit: 20, ext: {}, filter: {index_list: []},
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
    from dola_010e_dispatch_journal import CREATION_BOUND, ASSET_DOWNLOADED, TERMINAL_SUCCESS
    spec = json.loads((ROOT / "projects/quality_v2_011r_targeted_repair/V2_011R_REPAIR_SPECS.json").read_text(encoding="utf-8"))
    prompt_sha = hashlib.sha256(spec["prompts"]["F2A-R"].encode()).hexdigest()
    attempt_id = "attempt_" + prompt_sha[:0] + hashlib.sha256(json.dumps({"shot_spec_hash": "011r_f2a_r", "prompt_sha256": prompt_sha}, sort_keys=True).encode()).hexdigest()[:0] or "attempt_011r_f2a_r"
    journal = DispatchJournal(JOURNAL, "attempt_011r_f2a_r")
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_A")
    await manager.launch_browser()
    page = manager._page
    result = {"version": "v2-011r-reconciliation-v1",
              "started_at": utcnow(), "release_utc": RELEASE_UTC + "Z"}
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

        f2b_conv = None
        f2b_reply = None
        f2b_refusal = None
        deadline = asyncio.get_event_loop().time() + 1200
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
                        f2b_conv = conv["id"]
                        creations = row.get("creations") or []
                        done = [c for c in creations
                                if c.get("type") == 2 and
                                c.get("download_url")]
                        if done:
                            f2b_reply = done
                if f2b_conv == conv["id"]:
                    # progressive diagnosis: emit the newest texts
                    newest = [r.get("text", "")[:130] for r in rows[:4]]
                    emit({"step": "f2b_conv_state",
                          "attempt": attempt,
                          "creations": [
                              {k: c.get(k) for k in ("id", "type",
                                                     "v_status")}
                              for r in rows
                              for c in (r.get("creations") or [])],
                          "texts": newest})
                    refusal = any(
                        "生成できません" in (r.get("text") or "")
                        or "クレジット" in (r.get("text") or "")
                        for r in rows[:4])
                    if refusal and not any(
                            r.get("creations") for r in rows[:4]):
                        f2b_refusal = newest
                if f2b_reply:
                    break
            if f2b_reply:
                break
            if f2b_refusal:
                result["status"] = "STOPPED_EXPLICIT_PROVIDER_FAILURE"
                result["refusal_texts"] = f2b_refusal
                (PKG / "V2_011R_F2A_R_RECONCILIATION.json").write_text(
                    json.dumps(result, indent=1, ensure_ascii=False),
                    encoding="utf-8")
                emit({"status": result["status"]})
                return 1
            await page.wait_for_timeout(10000)

        result["f2b_conversation_id"] = f2b_conv
        if not f2b_reply:
            result["status"] = "UNRESOLVED_NO_COMPLETED_VIDEO"
            result["note"] = "no type-2 creation with download_url " \
                             "appeared within the window"
            (PKG / "V2_011R_F2A_R_RECONCILIATION.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": result["status"]})
            return 1
        urls = {r["download_url"] for r in f2b_reply}
        if len(urls) != 1:
            result["status"] = "UNRESOLVED_MULTIPLE_URLS"
            result["urls"] = len(urls)
            (PKG / "V2_011R_F2A_R_RECONCILIATION.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": result["status"]})
            return 1
        video_url = urls.pop()
        creation_ids = sorted({str(r["id"]) for r in f2b_reply})
        assets = PKG / "assets"
        dest = assets / "f2a_r.mp4"
        assets.mkdir(exist_ok=True)
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
        import subprocess
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height,codec_name,r_frame_rate",
             "-of", "json", str(dest)], capture_output=True, text=True)
        meta = json.loads(probe.stdout or "{}")
        stream = next((s for s in meta.get("streams", [])
                       if "width" in s), {})
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-i", str(dest),
             "-map", "0:v:0", "-f", "null", "-"], capture_output=True
        ).returncode == 0
        result.update({
            "status": "RESOLVED_EFFECT_IDENTIFIED",
            "f2b_conversation_id": f2b_conv,
            "creation_ids": creation_ids,
            "asset": {"path": str(dest), "sha256": asset_sha,
                      "size": total, "host": video_url.split("/")[2],
                      "duration_s": meta.get("format", {}).get("duration"),
                      "width": stream.get("width"),
                      "height": stream.get("height"),
                      "codec": stream.get("codec_name"),
                      "fps": stream.get("r_frame_rate"),
                      "full_decode": decode}})
        (PKG / "V2_011R_F2A_R_RECONCILIATION.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False),
            encoding="utf-8")
        emit({"checkpoint": "V2010E_RECONCILIATION_RESOLVED",
              "sha256": asset_sha[:16],
              "duration": result["asset"]["duration_s"],
              "decode": decode})
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
