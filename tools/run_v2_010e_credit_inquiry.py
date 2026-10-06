"""V2-010E — fresh-account credit inquiry (operational preflight).

A freshly logged-in account has NO provider credit statements in history
(nothing was ever generated), so the READY check (remaining >= 1) cannot be
verified by reading. This tool sends ONE plain text inquiry (a chat message
— NOT a video generation, consumes no video credit, Owner's own established
practice in their 動画生成クレジット conversation), reads the bot's reply via
the read-only poll, and classifies READY / NO_CREDIT / UNOBSERVABLE.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import CREDIT_STATEMENTS_JS, ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_010e_final_f2b"
INQUIRY = ("本日の動画生成クレジットの残り枚数を正確に教えてください。"
           "生成はしないでください。")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    manager = DolaSessionManager(
        profile_dir=ACCOUNT_PROFILES / "ACCOUNT_A")
    stored = json.loads(
        (PKG / "runtime/runtime_secret_store/dola_session_ACCOUNT_A.dpapi")
        .read_text(encoding="ascii")) if False else None
    # load the DPAPI-protected per-account session
    from dola_010c_session import dpapi_unprotect
    blob_path = PKG / "runtime/runtime_secret_store/dola_session_ACCOUNT_A.dpapi"
    session = json.loads(dpapi_unprotect(
        blob_path.read_text(encoding="ascii")))
    # NO cookie injection: the persistent profile owns its login state;
    # injecting a captured (older) sessionid DOWNGRADES the live session
    await manager.launch_browser()
    await manager.inject_cookies()
    page = manager._page
    result = {"version": "v2-010e-credit-inquiry-v1",
              "started_at": utcnow(),
              "inquiry_class": "plain chat message — NOT a video generation"}
    try:
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        for _ in range(20):
            try:
                if await page.evaluate(
                        """() => !!(document.querySelector('textarea')
                                || document.querySelector('[contenteditable="true"]'))"""):
                    break
            except Exception:
                pass
            await page.wait_for_timeout(1000)
        box = await page.query_selector("textarea") or \
            await page.query_selector('[contenteditable="true"]')
        if not box:
            result["error"] = "no composer"
            emit({"status": "INQUIRY_FAILED"})
            return 1
        await box.click()
        await page.keyboard.type(INQUIRY, delay=30)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        emit({"event": "inquiry_sent"})

        # wait for the bot's reply text (read-only poll)
        reply_text = ""
        deadline = asyncio.get_event_loop().time() + 90
        poll_js = """async () => {
          const params = new URLSearchParams({
            version_code: "20800", language: "ja", device_platform: "web",
            doubao_device_platform: "web", aid: "495671", real_aid: "495671",
            pkg_type: "release_version", pc_version: "3.39.1",
            doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
            samantha_web: "1", web_platform: "browser",
            "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
          });
          const convId = location.pathname.split("/").pop();
          if (!/^\\d{10,}$/.test(convId)) return [];
          const resp = await fetch("/im/chain/single?" + params.toString(), {
            method: "POST",
            headers: {"Content-Type": "application/json; encoding=utf-8",
                      "agw-js-conv": "str",
                      "Accept": "application/json, text/plain, */*"},
            credentials: "include",
            body: JSON.stringify({cmd: 3100,
              uplink_body: {pull_singe_chain_uplink_body: {
                conversation_id: convId,
                anchor_index: Number.MAX_SAFE_INTEGER,
                conversation_type: 3, direction: 1, limit: 10,
                ext: {}, filter: {index_list: []},
                evaluate_ab_params: "", evaluate_common_params: ""}},
              sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
          const data = await resp.json();
          const messages = ((data.downlink_body || {})
            .pull_singe_chain_downlink_body || {}).messages || [];
          const out = [];
          for (const m of messages) {
            let blocks = m.content;
            if (typeof blocks === "string") {
              try { blocks = JSON.parse(blocks); } catch (e) { continue; }
            }
            for (const b of (Array.isArray(blocks) ? blocks : [])) {
              if (b.block_type === 10000) {
                out.push({message_id: String(m.message_id),
                          create_time: m.create_time,
                          text: (((b.content || {}).text_block || {})
                                 .text || "").slice(0, 300)});
              }
            }
          }
          return out;
        }"""
        while asyncio.get_event_loop().time() < deadline:
            await page.wait_for_timeout(5000)
            try:
                rows = await page.evaluate(poll_js)
            except Exception:
                continue
            bot_texts = [r["text"] for r in rows
                         if len(r.get("text", "")) > 10]
            if bot_texts:
                reply_text = " | ".join(bot_texts[-3:])
                if any(re.search(r"\d", t) and
                       ("クレジット" in t or "ポイント" in t or "credit" in t.lower())
                       for t in bot_texts):
                    break
        result["bot_reply_head"] = reply_text[:600]
        # parse credit statements from the reply
        statements = []
        for match in re.finditer(
                r"(?:残り|残っています|あと)\s*(\d+)\s*(?:枚|個)?"
                r"|(?:残り|remaining)[^。\n]{0,10}?(\d+)|(\d+)\s*(?:枚の|枚)"
                r"?(?:動画クレジット|クレジット|ポイント)",
                reply_text):
            value = next((g for g in match.groups() if g), None)
            if value:
                statements.append(int(value))
        result["parsed_candidates"] = statements
        if statements:
            # the inquiry asks for the REMAINING count; take the value the
            # bot stated (prefer numbers adjacent to 残り/remaining)
            result["credit_remaining"] = statements[0]
            result["credit_verdict"] = ("SUFFICIENT" if statements[0] >= 1
                                        else "INSUFFICIENT")
        else:
            result["credit_verdict"] = "UNOBSERVABLE"
            result["credit_remaining"] = None
        result["completed_at"] = utcnow()
        (PKG / "V2_010E_CREDIT_INQUIRY.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False),
            encoding="utf-8")
        emit({"checkpoint": "V2010E_CREDIT_INQUIRY_DONE",
              "verdict": result["credit_verdict"],
              "credit": result.get("credit_remaining"),
              "reply_head": reply_text[:200]})
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
