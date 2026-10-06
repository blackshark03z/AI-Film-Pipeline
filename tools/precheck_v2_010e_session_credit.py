"""V2-010E Phase 3 — read-only session + credit precheck.

Credit state is read from the PROVIDER-VISIBLE credit surface (the
動画生成クレジット sidebar destination), NOT inferred from chat history.
Verdicts: SUFFICIENT / INSUFFICIENT / UNOBSERVABLE.
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

from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID

PKG = ROOT / "projects/quality_v2_010e_final_f2b"

CREDIT_PAGE_TEXT_JS = """() => (document.body ? document.body.innerText : '')
    .split('\\n').map(t => t.trim()).filter(t => t && t.length <= 80)
    .slice(0, 250)"""


def parse_credit_statements(messages: list[dict]) -> dict:
    """Extract timestamped remaining-credit statements from provider ack
    texts; the LATEST statement wins (provider-visible truth)."""
    statements = []
    patterns = (
        re.compile(r"残りは?\s*(\d+)\s*(?:動画)?クレジット"),
        re.compile(r"残り[はも]?[^。]{0,6}?(\d+)"),
        re.compile(r"(\d+)\s*(?:動画クレジット|video credits?)\s*(?:が残|left|remaining)",
                   re.I),
    )
    for message in messages:
        text = message.get("text") or ""
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                statements.append({
                    "create_time": message.get("create_time"),
                    "message_id": message.get("message_id"),
                    "remaining": int(match.group(1)),
                    "source_text": match.group(0)[:100]})
                break
    if not statements:
        return {}
    statements.sort(key=lambda s: (s.get("create_time") or 0))
    return statements[-1]


CREDIT_HISTORY_JS = """async ({conversationId}) => {
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
    body: JSON.stringify({cmd: 3100,
      uplink_body: {pull_singe_chain_uplink_body: {
        conversation_id: conversationId,
        anchor_index: Number.MAX_SAFE_INTEGER,
        conversation_type: 3, direction: 1, limit: 20,
        ext: {}, filter: {index_list: []},
        evaluate_ab_params: "", evaluate_common_params: "",
      }},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"}),
    credentials: "include"});
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
            text: text.slice(0, 400)};
  });
}"""


async def main() -> int:
    result = {"version": "v2-010e-session-credit-precheck-v1",
              "checkpoint": "V2010E_P3_SESSION_CREDIT_PRECHECK",
              "started_at": datetime.now(timezone.utc).isoformat(),
              "method": "provider credit surface (sidebar 動画生成クレジット "
                        "destination) — chat-history texts are NOT used"}
    adapter = DolaBrowserAdapter010D(run_id="precheck_" +
                                     datetime.now(timezone.utc)
                                     .strftime("%Y%m%dT%H%M%S"))
    try:
        await adapter.open()
        try:
            await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        except Exception as error:
            result.update({"session": "INVALID",
                           "reason": type(error).__name__})
            await adapter.close(sanitize_to=None)
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            (PKG / "V2_010E_SESSION_CREDIT_PRECHECK.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            print(json.dumps({"session": "INVALID"}))
            return 1
        poll = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
        result["session"] = "SESSION_VALID" if poll.get("ok") else "INVALID"
        result["read_only_poll_ok"] = bool(poll.get("ok"))

        # navigate to the provider credit surface (read-only) and identify
        # the conversation id it lands on
        clicked = False
        for text in ("動画生成クレジット", "Video generation credit",
                     "クレジット"):
            try:
                locator = adapter.page.get_by_text(text, exact=True).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue
        await adapter.page.wait_for_timeout(5000)
        await adapter.page.screenshot(path=str(
            PKG / "credit_surface.png"))
        credit_conv = ""
        try:
            tail = (adapter.page.url or "").rstrip("/").split("/")[-1]
            if tail.isdigit() and len(tail) >= 10:
                credit_conv = tail
        except Exception:
            pass
        result["credit_surface_clicked"] = clicked
        result["credit_conversation_id"] = credit_conv

        # provider-visible remaining-credit statements, timestamped, from
        # BOTH conversations (ours + the credit surface) — latest wins
        all_statements = []
        for conv in filter(None, {SEEDANCE_CONVERSATION_ID, credit_conv}):
            try:
                messages = await adapter.page.evaluate(
                    CREDIT_HISTORY_JS, {"conversationId": conv})
            except Exception:
                continue
            for message in messages:
                single = parse_credit_statements([message])
                if single:
                    single["conversation_id"] = conv
                    all_statements.append(single)
        all_statements.sort(key=lambda s: (s.get("create_time") or 0))
        result["credit_statements"] = all_statements[-6:]
        if all_statements:
            latest = all_statements[-1]
            result["credit_value"] = latest["remaining"]
            result["credit_source"] = latest
            result["credit_verdict"] = ("SUFFICIENT" if latest["remaining"] >= 1
                                        else "INSUFFICIENT")
        else:
            result["credit_verdict"] = "UNOBSERVABLE"
            result["credit_value"] = None
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"[:200]
        result["credit_verdict"] = "UNOBSERVABLE"
    finally:
        await adapter.close(sanitize_to=None)
    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    (PKG / "V2_010E_SESSION_CREDIT_PRECHECK.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"session": result.get("session"),
                      "credit_verdict": result.get("credit_verdict"),
                      "credit_value": result.get("credit_value"),
                      "parse_source": (result.get("credit_parse") or {})
                      .get("source_text")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
