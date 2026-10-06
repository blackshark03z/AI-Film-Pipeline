"""V2-010E — dump the credit conversation on ACCOUNT_A (read-only)."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager, dpapi_unprotect
from dola_010e_session_router import ACCOUNT_PROFILES, CREDIT_STATEMENTS_JS

PKG = ROOT / "projects/quality_v2_010e_final_f2b"

LIST_CONVS_JS = """async () => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
    samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const resp = await fetch("/im/chain/recent_conv?" + params.toString(), {
    method: "POST",
    headers: {"Content-Type": "application/json; encoding=utf-8",
              "agw-js-conv": "str",
              "Accept": "application/json, text/plain, */*"},
    credentials: "include",
    body: JSON.stringify({cmd: 3200, uplink_body: {
      pull_recent_conv_chain_uplink_body: {limit: 20,
        message_count_per_conv: 2, api_version: 1, conv_version: 0,
        direction: 3, option: {not_need_message: false,
          need_complete_conversation: true, need_coco_conversation: true,
          need_coco_bot: true, need_pc_pin_chain: true,
          pc_pin_query_type: 0}}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  const data = await resp.json();
  const cells = ((data.downlink_body || {})
    .pull_recent_conv_chain_downlink_body || {}).cells || [];
  return cells.map(c => ({id: (c.conversation || {}).conversation_id || c.id,
                          title: ((c.conversation || {}).name) ||
                                 ((c.conversation || {}).title) || ""}));
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
  return messages.map(m => {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
    }
    let text = "";
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type === 10000) {
        text += (((b.content || {}).text_block || {}).text || "");
      }
    }
    return {message_id: String(m.message_id), create_time: m.create_time,
            text: text.slice(0, 500)};
  });
}"""


async def main() -> int:
    blob_path = PKG / "runtime/runtime_secret_store/dola_session_ACCOUNT_A.dpapi"
    session = json.loads(dpapi_unprotect(blob_path.read_text(encoding="ascii")))
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_A")
    # NO cookie injection: the persistent profile owns its login state;
    # injecting a captured (older) sessionid DOWNGRADES the live session
    await manager.launch_browser()
    page = manager._page
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
        convs = await page.evaluate(LIST_CONVS_JS)
        print(json.dumps({"conversations": convs[:10]}, ensure_ascii=False))
        dump = []
        for conv in convs[:6]:
            try:
                messages = await page.evaluate(
                    PULL_JS, {"conversationId": conv["id"]})
            except Exception as error:
                messages = [{"error": type(error).__name__}]
            dump.append({"conversation": conv, "messages": messages})
        (PKG / "V2_010E_ACCOUNT_A_CONVERSATION_DUMP.json").write_text(
            json.dumps(dump, indent=1, ensure_ascii=False), encoding="utf-8")
        for entry in dump:
            print("=== conv", entry["conversation"]["id"],
                  repr(entry["conversation"]["title"])[:50], "===")
            for m in entry["messages"][:6]:
                ts = m.get("create_time")
                when = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                    "%m-%d %H:%M") if isinstance(ts, (int, float)) else "?"
                print(f"  {when}Z {m.get('text', '')[:150]}")
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
