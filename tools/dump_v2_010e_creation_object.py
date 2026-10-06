"""V2-010E — one-shot: dump the FULL creation object of the completed F2B
video (all keys of the video dict) to locate the download URL field."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_010e_final_f2b"
CONV = "38417852184170001"
CREATION = "1546437193256465"

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
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { continue; }
    }
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type !== 2074) continue;
      for (const c of (((b.content || {}).creation_block || {})
          .creations || [])) {
        if (String(c.id) === "__CREATION__") return c;
      }
    }
  }
  return null;
}""".replace("__CREATION__", CREATION)


async def main() -> int:
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_A")
    await manager.launch_browser()
    page = manager._page
    try:
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        creation = await page.evaluate(PULL_RAW_JS,
                                       {"conversationId": CONV})
        out = PKG / "V2_010E_F2B_CREATION_OBJECT.json"
        out.write_text(json.dumps(creation, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        video = (creation or {}).get("video") or {}
        print(json.dumps({
            "creation_id": (creation or {}).get("id"),
            "type": (creation or {}).get("type"),
            "video_keys": sorted(video.keys()),
            "download_url_head": (video.get("download_url") or "")[:100],
            "url_head": (video.get("url") or "")[:100],
        }, ensure_ascii=False))
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
