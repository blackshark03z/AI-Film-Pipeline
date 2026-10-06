"""V2-010E — open the credit conversation in the UI and read rendered texts."""
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

from dola_010c_session import DolaSessionManager, dpapi_unprotect
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_010e_final_f2b"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    blob_path = PKG / "runtime/runtime_secret_store/dola_session_ACCOUNT_A.dpapi"
    session = json.loads(dpapi_unprotect(blob_path.read_text(encoding="ascii")))
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_A")
    # NO cookie injection: the persistent profile owns its login state;
    # injecting a captured (older) sessionid DOWNGRADES the live session
    await manager.launch_browser()
    page = manager._page
    result = {"version": "v2-010e-credit-conversation-read-v1",
              "read_at": utcnow()}
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
        clicked = None
        for _ in range(3):
            try:
                locator = page.get_by_text("クレジット残数確認", exact=True).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=5000)
                    clicked = "クレジット残数確認"
                    break
            except Exception as error:
                if "strict" in str(error).lower():
                    continue
                await page.wait_for_timeout(1000)
        await page.wait_for_timeout(6000)
        result["clicked"] = clicked
        result["url_tail"] = (page.url or "")[-60:]
        body = await page.evaluate(
            "() => (document.body && document.body.innerText) || ''")
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        result["conversation_texts"] = lines[:80]
        await page.screenshot(path=str(PKG / "credit_conv_account_a.png"))
        joined = "\n".join(lines)
        matches = []
        for match in re.finditer(
                r"(?:残り|残っています|あと|remaining)[^0-9\n]{0,8}(\d+)"
                r"|(\d+)\s*(?:枚|個)?\s*(?:動画クレジット|クレジット|ポイント)",
                joined):
            value = next((g for g in match.groups() if g), None)
            if value is not None:
                matches.append({"value": int(value),
                                "context": joined[max(0, match.start() - 30):
                                                   match.end() + 30][:120]})
        result["credit_matches"] = matches
        (PKG / "V2_010E_CREDIT_CONVERSATION_READ.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False),
            encoding="utf-8")
        print(json.dumps({"clicked": clicked,
                          "matches": matches[:6],
                          "text_head": lines[:14]}, ensure_ascii=False))
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
