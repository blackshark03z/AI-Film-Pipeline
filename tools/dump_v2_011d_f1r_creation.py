"""V2-011D — one-shot diagnostic: dump the FULL creation object(s) of the
F1R conversation (all keys of the video dict) to locate the download URL
field. READ-ONLY: conversation pull + local dump, no dispatch, no clicks on
generations.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
PROMPT_NEEDLE = "Establishing WIDE shot from the side"

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

PULL_RAW_JS = """async ({conversationId}) => {
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
  const found = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { continue; }
    }
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type !== 2074) continue;
      for (const c of (((b.content || {}).creation_block || {})
          .creations || [])) {
        if (c.type === 2) {
          found.push({message_id: String(m.message_id),
                      create_time: m.create_time, creation: c});
        }
      }
    }
  }
  return found;
}"""


PULL_TEXTS_JS = """async ({conversationId}) => {
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
  const texts = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { continue; }
    }
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type === 10000) {
        texts.push((((b.content || {}).text_block || {}).text || "")
                   .slice(0, 120));
      }
    }
  }
  return texts;
}"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_A")
    await manager.launch_browser()
    page = manager._page
    out = {"version": "v2-011d-creation-dump-v1",
           "dumped_at": utcnow(), "mode": "READ_ONLY diagnostic"}
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
        convs = await page.evaluate(TIMELINE_JS)
        target = None
        for conv in convs[:6]:
            texts = await page.evaluate(
                PULL_TEXTS_JS, {"conversationId": conv["id"]})
            if not any(PROMPT_NEEDLE in t for t in texts):
                continue
            probe = await page.evaluate(PULL_RAW_JS,
                                        {"conversationId": conv["id"]})
            if probe:
                target = conv["id"]
                out["f1r_conversation_id"] = target
                out["type2_creations"] = probe
                break
        (PKG / "V2_011D_F1R_CREATION_DUMP.json").write_text(
            json.dumps(out, indent=1, ensure_ascii=False),
            encoding="utf-8")
        print(json.dumps({"checkpoint": "DUMP_DONE",
                          "conv": out.get("f1r_conversation_id"),
                          "n_creations": len(out.get("type2_creations", []))},
                         ensure_ascii=False))
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
