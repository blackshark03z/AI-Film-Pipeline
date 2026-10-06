"""AI-FILM-QUALITY-V2-010C — READ-ONLY conversation observation.

No provider mutation: navigation + in-page /im/chain/single poll only.
Purpose:
  1. observe M1's four image creations (ids 40033753389997329…) completion
  2. observe the CURRENT shape of completed VIDEO creations (type 2 +
     download_url) from the SAME conversation's history
  3. correlate outputs by creation id (network authority, history-immune)

Everything returned from the page is sanitized IN THE PAGE: signed URLs are
reduced to scheme+host+path; values like msToken never reach Python.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_capture import NetworkCapture, sanitize_capture
from dola_010c_session import (ORIGIN, PKG, DolaSessionManager,
                               load_session_encrypted)

CONVERSATION_ID = "38417972940811793"
M1_CREATION_IDS = {"40033753389997329", "40033753389997585",
                   "40033753389997841", "40033753389998097"}
M1_REPLY_MESSAGE_ID = "1546406012981009"

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
  const status = resp.status;
  const rawText = await resp.text();
  let data = null;
  try { data = JSON.parse(rawText); } catch (e) {}
  const debug = {
    status,
    raw_head: rawText.slice(0, 400),
    top_keys: data && typeof data === "object" ? Object.keys(data) : null,
    downlink_keys: data && data.downlink_body ? Object.keys(data.downlink_body) : null,
  };
  const cleanUrl = (u) => {
    if (typeof u !== "string" || !u.startsWith("http")) return u;
    try { const p = new URL(u); return p.origin + p.pathname; }
    catch (e) { return "UNPARSEABLE"; }
  };
  const out = {debug, conversation_id: conversationId, messages: []};
  const messages = ((data.downlink_body || {})
    .pull_singe_chain_downlink_body || {}).messages || [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
    }
    const creations = [];
    for (const block of (Array.isArray(blocks) ? blocks : [])) {
      if (block.block_type !== 2074) continue;
      const cb = (block.content || {}).creation_block || {};
      for (const c of (cb.creations || [])) {
        creations.push({
          id: c.id, type: c.type,
          gen_task_type: (c.gen_detail || {}).task_type,
          image_status: (c.image || {}).status,
          image_url_path: cleanUrl((c.image || {}).url || (c.image || {}).download_url),
          video_status: (c.video || {}).status,
          video_url_path: cleanUrl((c.video || {}).download_url ||
                                   (c.video || {}).url),
          video_duration_ms: (c.video || {}).duration,
        });
      }
    }
    out.messages.push({
      message_id: m.message_id,
      local_message_id: m.local_message_id,
      reply_to: m.reply_to_message_id || m.parent_message_id || null,
      index_in_conv: m.index_in_conv,
      create_time: m.create_time,
      creation_count: creations.length,
      creations,
    });
  }
  return out;
}"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    run_id = "obs_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    stored = load_session_encrypted()
    if not stored:
        print(json.dumps({"status": "STOPPED_SESSION_GAP"}))
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
    try:
        await page.goto(f"{ORIGIN}/chat/{CONVERSATION_ID}", timeout=60000,
                        wait_until="domcontentloaded")
    except Exception as error:
        await capture.stop()
        await manager.close()
        print(json.dumps({"status": "STOPPED_SESSION_GAP",
                          "reason": type(error).__name__}))
        return 1
    await page.wait_for_timeout(8000)
    await page.screenshot(path=str(PKG / "screenshots_m1" / "06_observation.png"))

    poll = await page.evaluate(POLL_JS, {"conversationId": CONVERSATION_ID})
    await page.wait_for_timeout(2000)

    # ---- correlate ---------------------------------------------------------
    m1_creations = []
    history_video_shapes = []
    for message in poll.get("messages", []):
        for creation in message.get("creations", []):
            record = {"message_id": message.get("message_id"),
                      "reply_to": message.get("reply_to"),
                      "index_in_conv": message.get("index_in_conv"),
                      **creation}
            if str(creation.get("id")) in M1_CREATION_IDS or \
                    str(message.get("message_id")) == M1_REPLY_MESSAGE_ID:
                m1_creations.append(record)
            if creation.get("type") == 2 and creation.get("video_url_path"):
                history_video_shapes.append(record)

    result = {
        "version": "v2-010c-m1-output-observation-v1",
        "checkpoint": "V2010C_P3B_M1_OUTPUT_OBSERVATION",
        "observed_at": utcnow(),
        "poll_status": poll.get("status"),
        "message_count": len(poll.get("messages", [])),
        "m1_target_creations": m1_creations,
        "m1_reply_message_seen": any(
            str(m.get("message_id")) == M1_REPLY_MESSAGE_ID
            for m in poll.get("messages", [])),
        "history_video_creation_shapes": history_video_shapes[:6],
        "history_video_count": len(history_video_shapes),
    }
    (PKG / "V2_010C_M1_OUTPUT_OBSERVATION.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")

    if capture.raw_path.exists():
        sanitize_capture(capture.raw_path,
                         PKG / "V2_010C_OBSERVATION_CAPTURE_SANITIZED.json")
    summary = await capture.stop()
    await manager.close()
    result["capture_summary"] = {"events": summary.get("events")}
    print(json.dumps({"checkpoint": "V2010C_OBSERVATION_DONE",
                      "poll_status": poll.get("status"),
                      "messages": result["message_count"],
                      "m1_creations": [
                          {k: c.get(k) for k in ("id", "type", "image_status",
                                                 "video_status", "video_url_path")}
                          for c in m1_creations],
                      "history_video_shapes": len(history_video_shapes)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
