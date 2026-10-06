"""V2-011D RESUME — Owner-manual login monitor (CDP attach, read-only).

Attaches to the Owner's login Chrome (port 9334, separate user-data dir),
polls until the Dola session is authenticated, then reads EXISTING credit
statements (read-only API pull — no message created). Does NOT close the
browser. Ledger: everything here is READ_ONLY observation.
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

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
CDP = "http://127.0.0.1:9334"

LOGIN_CHECK_JS = """() => {
    const t = (document.body && document.body.innerText) || '';
    return {
        logged_out: /(^|\\n)\\s*ログイン\\s*(\\n|$)/.test(t)
            || /\\bLog\\s?in\\b|\\bSign\\s?in\\b/.test(t)
            || /Đăng nhập|Đăng ký/i.test(t),
        composer: !!(document.querySelector('textarea')
            || document.querySelector('[contenteditable="true"]')),
    };
}"""

STATEMENTS_JS = """async () => {
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
      pull_recent_conv_chain_uplink_body: {limit: 10,
        message_count_per_conv: 2, api_version: 1, conv_version: 0,
        direction: 3, option: {not_need_message: false,
          need_complete_conversation: true, need_coco_conversation: true,
          need_coco_bot: true, need_pc_pin_chain: true,
          pc_pin_query_type: 0}}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  const data = await recent.json();
  const cells = ((data.downlink_body || {})
    .pull_recent_conv_chain_downlink_body || {}).cells || [];
  const convIds = cells.map(c => (c.conversation || {}).conversation_id
    || c.id).filter(id => /^\\d{10,}$/.test(String(id))).slice(0, 6);
  const statements = [];
  for (const conversation_id of convIds) {
    const resp = await fetch("/im/chain/single?" + params.toString(), {
      method: "POST", headers, credentials: "include",
      body: JSON.stringify({cmd: 3100, uplink_body: {
        pull_singe_chain_uplink_body: {conversation_id,
          anchor_index: Number.MAX_SAFE_INTEGER, conversation_type: 3,
          direction: 1, limit: 10, ext: {}, filter: {index_list: []},
          evaluate_ab_params: "", evaluate_common_params: ""}},
        sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
    const d2 = await resp.json();
    const messages = ((d2.downlink_body || {})
      .pull_singe_chain_downlink_body || {}).messages || [];
    for (const m of messages) {
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
      const pats = [/残りは?\\s*(\\d+)\\s*(?:動画)?クレジット/,
                    /残り[はも]?[^。]{0,6}?(\\d+)/,
                    /(\\d+)\\s*(?:動画)?クレジット/];
      for (const p of pats) {
        const match = p.exec(text);
        if (match) {
          statements.push({conversation_id,
            message_id: String(m.message_id), create_time: m.create_time,
            remaining: parseInt(match[1], 10),
            source_text: match[0].slice(0, 80)});
          break;
        }
      }
    }
  }
  statements.sort((a, b) => (a.create_time || 0) - (b.create_time || 0));
  return statements;
}"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    page = None
    for p in ctx.pages:
        if "dola.com" in (p.url or ""):
            page = p
            break
    if page is None:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        if "dola.com" not in (page.url or ""):
            await page.goto("https://www.dola.com/chat", timeout=60000,
                            wait_until="domcontentloaded")
    emit({"event": "attached", "page_url": (page.url or "")[:120]})

    deadline = asyncio.get_event_loop().time() + 1800
    authed = False
    while asyncio.get_event_loop().time() < deadline:
        try:
            state = await page.evaluate(LOGIN_CHECK_JS)
        except Exception:
            await asyncio.sleep(3)
            continue
        if state.get("composer") and not state.get("logged_out"):
            authed = True
            break
        await asyncio.sleep(4)
    if not authed:
        emit({"status": "LOGIN_NOT_COMPLETED_WITHIN_WINDOW"})
        await pw.stop()
        return 1
    emit({"event": "dola_session_authenticated", "at": utcnow()})
    await asyncio.sleep(2)
    try:
        statements = await page.evaluate(STATEMENTS_JS)
    except Exception as error:
        statements = []
        emit({"event": "statement_read_error",
              "error": type(error).__name__})
    emit({"event": "statements_read", "count": len(statements),
          "statements": statements[-3:]})
    out = {"version": "v2-011d-owner-login-observation-v1",
           "observed_at": utcnow(),
           "dola_session_authenticated": True,
           "account_url_identity": "visible in UI (Owner's chosen identity)",
           "existing_statements": statements,
           "credit_observation_class": "READ_ONLY (no message created)",
           "statement_fresh_for_current_epoch": bool(statements)}
    (PKG / "V2_011D_OWNER_LOGIN_OBSERVATION.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    emit({"checkpoint": "V2011D_OWNER_LOGIN_OBSERVED",
          "statements": len(statements)})
    await pw.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
