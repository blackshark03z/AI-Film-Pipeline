"""V2-021 — fresh-account credit inquiry (V2-010E precedent).

ONE plain chat text message per freshly enrolled account ("today's
remaining video credits — do NOT generate"). This is an
ACCOUNT_STATE_QUERY_MUTATION on its own ledger — NOT a video generation;
it consumes no video credit. The provider's reply makes the credit state
OBSERVABLE for the mutation-budget gate.
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
from dola_010e_session_router import CREDIT_STATEMENTS_JS

PKG = ROOT / "projects/quality_v2_021_narrative_compiler"
PROFILE_ROOT = PKG / "pool_profiles"
INQUIRY = ("本日の動画生成クレジットの残り枚数を正確に教えてください。"
           "生成はしないでください。")

SEND_JS = """async ({text}) => {
  const box = document.querySelector('textarea')
      || document.querySelector('[contenteditable="true"]');
  if (!box) return false;
  box.click();
  if (box.tagName === 'TEXTAREA') {
    box.value = text;
    box.dispatchEvent(new Event('input', {bubbles: true}));
  } else {
    box.textContent = text;
    box.dispatchEvent(new InputEvent('input', {bubbles: true}));
  }
  await new Promise(r => setTimeout(r, 600));
  return true;
}"""


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def inquire(alias: str) -> dict:
    manager = DolaSessionManager(profile_dir=PROFILE_ROOT / alias)
    result = {"alias": alias, "inquiry_class": "ACCOUNT_STATE_QUERY "
              "(plain text; no video generation)",
              "at": datetime.now(timezone.utc).isoformat()}
    try:
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        for _ in range(15):
            ok = await page.evaluate(
                """() => !!(document.querySelector('textarea')
                        || document.querySelector('[contenteditable="true"]'))""")
            if ok:
                break
            await page.wait_for_timeout(2000)
        box = await page.query_selector("textarea") or \
            await page.query_selector('[contenteditable="true"]')
        if not box:
            result["status"] = "NO_COMPOSER"
            return result
        await box.click()
        await page.keyboard.type(INQUIRY, delay=25)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        emit({"event": "inquiry_sent", "alias": alias})
        reply = ""
        deadline = asyncio.get_event_loop().time() + 120
        while asyncio.get_event_loop().time() < deadline:
            await page.wait_for_timeout(5000)
            try:
                statements = await page.evaluate(CREDIT_STATEMENTS_JS,
                                                 {"conversationIds": []})
            except Exception:
                continue
            if statements:
                latest = statements[-1]
                result.update({
                    "status": "OBSERVED",
                    "known_credit_state": latest.get("remaining"),
                    "latest_statement": latest,
                    "statement_count": len(statements)})
                emit({"event": "credit_observed", "alias": alias,
                      "remaining": latest.get("remaining")})
                return result
        result["status"] = "UNOBSERVABLE"
        return result
    except Exception as error:
        result["status"] = "ERROR"
        result["error"] = f"{type(error).__name__}: {error}"[:200]
        return result
    finally:
        try:
            await manager.close()
        except Exception:
            pass


async def main() -> int:
    out = {}
    ledger = []
    ledger_path = PKG / "V2_021_QUERY_MUTATION_LEDGER.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for alias in sys.argv[1:] or ["ACCOUNT_E", "ACCOUNT_F"]:
        result = await inquire(alias)
        out[alias] = result
        ledger.append({"alias": alias, "kind": "ACCOUNT_STATE_QUERY",
                       "at": result.get("at"),
                       "status": result.get("status")})
    ledger_path.write_text(json.dumps(
        {"version": "v2-021-query-mutation-ledger-v1",
         "note": "text inquiries only; 0 video mutations",
         "entries": ledger}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    (PKG / "V2_021_FRESH_CREDIT_STATES.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    emit({"status": "INQUIRY_DONE",
          "credits": {a: r.get("known_credit_state")
                      for a, r in out.items()}})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
