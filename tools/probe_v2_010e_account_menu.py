"""V2-010E — read-only account-menu credit surface exploration."""
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


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


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
    result = {"version": "v2-010e-account-menu-probe-v1", "started_at": utcnow()}
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

        async def surface_texts() -> list[str]:
            try:
                return await page.evaluate(
                    """() => [...document.querySelectorAll(
                            'button, [role=button], [role=menuitem], a, div, span')]
                        .map(el => (el.innerText || '').trim())
                        .filter(t => t && t.length <= 40)
                        .slice(0, 300)""")
            except Exception:
                return []

        # open the account menu (bottom-left profile chip or top-right icon)
        clicked = None
        for text in ("Đặng Văn Khởi", "アカウント", "Account", "設定"):
            try:
                locator = page.get_by_text(text, exact=False).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=5000)
                    clicked = text
                    break
            except Exception:
                continue
        await page.wait_for_timeout(2000)
        menu_texts = await surface_texts()
        await page.screenshot(path=str(PKG / "account_menu_010e.png"))
        result["clicked"] = clicked
        result["menu_texts"] = [t for t in menu_texts if t][:80]

        # look for a credits entry and open it
        credit_entry = None
        for t in menu_texts:
            if re.search(r"クレジット|credit|ポイント|プラン|plan|残り", t, re.I):
                if len(t) <= 30:
                    credit_entry = t
                    break
        if credit_entry:
            try:
                locator = page.get_by_text(credit_entry, exact=False).first
                await locator.click(timeout=5000)
                await page.wait_for_timeout(4000)
            except Exception:
                pass
            page_texts = await surface_texts()
            result["credit_surface_texts"] = [t for t in page_texts if t][:120]
            await page.screenshot(path=str(PKG / "credit_menu_010e.png"))
            joined = " | ".join(result.get("credit_surface_texts", []))
            match = re.search(
                r"(?:残り|remaining)[^|]{0,14}?(\d+)|(\d+)\s*(?:枚の|枚)?"
                r"(?:動画クレジット|クレジット|クレジット残)",
                joined, re.I)
            if match:
                result["credit_value"] = int(next(
                    g for g in match.groups() if g))
                result["credit_source_text"] = match.group(0)[:120]
        result["completed_at"] = utcnow()
        (PKG / "V2_010E_ACCOUNT_MENU_PROBE.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False),
            encoding="utf-8")
        emit({"checkpoint": "V2010E_MENU_PROBE_DONE",
              "clicked": clicked, "credit_entry": credit_entry,
              "credit_value": result.get("credit_value")})
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
