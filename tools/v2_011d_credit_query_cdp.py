"""V2-011D RESUME — ONE credit state query over the authenticated login Chrome.

This sends ONE provider message (ACCOUNT_STATE_QUERY_MUTATION — never called
read-only). Authorized because the fresh Dola account has NO existing
statements: no true read-only credit mechanism exists (governance correction
option 4, minimum necessary = 1 for the whole discovery).
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

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
CDP = "http://127.0.0.1:9334"
INQUIRY = ("本日の動画生成クレジットの残り枚数を正確に教えてください。"
           "生成はしないでください。")

POLL_JS = """async () => {
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


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    page = next((p for p in ctx.pages if "dola.com" in (p.url or "")), None)
    if page is None:
        emit({"status": "NO_DOLA_PAGE"})
        await pw.stop()
        return 1
    state = await page.evaluate(
        """() => !!(document.querySelector('textarea')
                || document.querySelector('[contenteditable="true"]'))""")
    if not state:
        emit({"status": "NO_COMPOSER"})
        await pw.stop()
        return 1
    box = await page.query_selector("textarea") or \
        await page.query_selector('[contenteditable="true"]')
    await box.click()
    await page.keyboard.type(INQUIRY, delay=30)
    await page.wait_for_timeout(500)
    await page.keyboard.press("Enter")
    emit({"event": "ACCOUNT_STATE_QUERY_MUTATION_SENT", "at": utcnow()})

    reply_text = ""
    deadline = asyncio.get_event_loop().time() + 150
    while asyncio.get_event_loop().time() < deadline:
        await page.wait_for_timeout(5000)
        try:
            rows = await page.evaluate(POLL_JS)
        except Exception:
            continue
        bot_texts = [r["text"] for r in rows if len(r.get("text", "")) > 10]
        if bot_texts:
            reply_text = " | ".join(bot_texts[-3:])
            if any(re.search(r"\d", t) and
                   ("クレジット" in t or "ポイント" in t or "credit" in t.lower())
                   for t in bot_texts):
                break
    emit({"reply_head": reply_text[:300]})
    statements = []
    for match in re.finditer(
            r"(?:残り|残っています|あと)\s*(\d+)\s*(?:枚|個)?"
            r"|(?:残り|remaining)[^。\n]{0,10}?(\d+)|(\d+)\s*(?:枚の|枚)"
            r"?(?:動画クレジット|クレジット|ポイント)",
            reply_text):
        value = next((g for g in match.groups() if g), None)
        if value:
            statements.append(int(value))
    credit = statements[0] if statements else None
    verdict = ("SUFFICIENT" if (credit or 0) >= 1 else
               "INSUFFICIENT" if credit is not None else "UNOBSERVABLE")
    record = {
        "version": "v2-011d-f3r-credit-gate-v1",
        "recorded_at": utcnow(),
        "account_opaque_id": "ACCOUNT_D (owner-manual login, fresh Dola account)",
        "ledger_class": "ACCOUNT_STATE_QUERY_MUTATION #1 (one provider "
                        "message; separate ledger from F3R video-generation "
                        "authority; never called read-only)",
        "question": INQUIRY,
        "bot_reply_head": reply_text[:600],
        "parsed_candidates": statements,
        "credit_remaining": credit,
        "verdict": verdict,
    }
    (PKG / "V2_011D_F3R_CREDIT_GATE.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    log_path = PKG / "V2_011D_RESUME_OBSERVATION_LOG.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {
        "version": "v2-011d-resume-observation-log-v1",
        "account_state_query_mutations_sent": 0, "observations": []}
    log["observations"].append({
        "kind": "ACCOUNT_STATE_QUERY_MUTATION", "sent": True,
        "at": utcnow(), "account": "ACCOUNT_D",
        "credit_remaining": credit, "verdict": verdict})
    log["account_state_query_mutations_sent"] = \
        log.get("account_state_query_mutations_sent", 0) + 1
    log_path.write_text(json.dumps(log, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    emit({"checkpoint": "V2011D_CREDIT_GATE",
          "verdict": verdict, "credit": credit})
    await pw.stop()
    return 0 if verdict == "SUFFICIENT" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
