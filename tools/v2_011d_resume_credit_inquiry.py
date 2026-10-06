"""V2-011D RESUME — credit inquiry (V2-010E established text mechanism).

Usage: v2_011d_resume_credit_inquiry.py ACCOUNT_A|ACCOUNT_C

ONE plain text inquiry (a chat message — NOT a video generation, consumes no
video credit, Owner's own established practice), read-only reply poll.
Writes V2_011D_F3R_CREDIT_GATE.json (verdict SUFFICIENT unlocks the F3R
runner gate). Never persists secrets.
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
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
INQUIRY = ("本日の動画生成クレジットの残り枚数を正確に教えてください。"
           "生成はしないでください。")
OPAQUE = sys.argv[1] if len(sys.argv) > 1 else "ACCOUNT_A"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / OPAQUE)
    await manager.launch_browser()
    page = manager._page
    result = {"version": "v2-011d-resume-credit-inquiry-v1",
              "account_opaque_id": OPAQUE,
              "started_at": utcnow(),
              "inquiry_class": "plain chat message — NOT a video generation "
                               "(V2-010E established practice)",
              "question": INQUIRY}
    try:
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        logged_out = False
        for _ in range(24):
            try:
                state = await page.evaluate(
                    """() => {
                        const t = (document.body && document.body.innerText)
                            || '';
                        return {
                            out: /(^|\\n)\\s*ログイン\\s*(\\n|$)/.test(t)
                                || /\\bLog\\s?in\\b|\\bSign\\s?in\\b/.test(t),
                            composer: !!(document.querySelector('textarea')
                                || document.querySelector('[contenteditable="true"]')),
                        };
                    }""")
                if state.get("composer") and not state.get("out"):
                    break
                if state.get("out"):
                    logged_out = True
                    break
            except Exception:
                pass
            await page.wait_for_timeout(1000)
        if logged_out:
            result["credit_verdict"] = "LOGIN_REQUIRED"
            result["credit_remaining"] = None
            result["verdict"] = "LOGIN_REQUIRED"
            result["completed_at"] = utcnow()
            (PKG / "V2_011D_F3R_CREDIT_GATE.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": "LOGIN_REQUIRED"})
            return 1
        box = await page.query_selector("textarea") or \
            await page.query_selector('[contenteditable="true"]')
        if not box:
            result["error"] = "no composer"
            result["credit_verdict"] = "UNOBSERVABLE"
            result["verdict"] = "UNOBSERVABLE"
            (PKG / "V2_011D_F3R_CREDIT_GATE.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": "INQUIRY_FAILED"})
            return 1
        await box.click()
        await page.keyboard.type(INQUIRY, delay=30)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        emit({"event": "inquiry_sent", "account": OPAQUE})

        reply_text = ""
        deadline = asyncio.get_event_loop().time() + 120
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
            result["credit_remaining"] = statements[0]
            result["credit_verdict"] = ("SUFFICIENT" if statements[0] >= 1
                                        else "INSUFFICIENT")
        else:
            result["credit_verdict"] = "UNOBSERVABLE"
            result["credit_remaining"] = None
        result["verdict"] = result["credit_verdict"]
        result["completed_at"] = utcnow()
        (PKG / "V2_011D_F3R_CREDIT_GATE.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False),
            encoding="utf-8")
        emit({"checkpoint": "V2011D_RESUME_CREDIT_INQUIRY",
              "account": OPAQUE,
              "verdict": result["credit_verdict"],
              "credit": result.get("credit_remaining"),
              "reply_head": reply_text[:200]})
        return 0 if result["credit_verdict"] == "SUFFICIENT" else 1
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
