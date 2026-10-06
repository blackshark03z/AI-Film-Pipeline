"""V2-010E — verify ACCOUNT_A authentication state (screenshot + UI probes)."""
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
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_010e_final_f2b"


async def main() -> int:
    blob_path = PKG / "runtime/runtime_secret_store/dola_session_ACCOUNT_A.dpapi"
    session = json.loads(dpapi_unprotect(blob_path.read_text(encoding="ascii")))
    names = [c["name"] for c in session["cookies"]]
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
        state = await page.evaluate(
            """() => {
                const t = (document.body && document.body.innerText) || '';
                return {
                    login_button: /(^|\\n)\\s*ログイン\\s*(\\n|$)/.test(t)
                        || /\\bLog\\s?in\\b|\\bSign\\s?in\\b/.test(t)
                        || /đăng nhập/i.test(t),
                    avatar_like: !!document.querySelector(
                        'img[alt*=avatar], [class*=avatar], [class*=Avatar]'),
                    history_hint: /最近|Recent/.test(t),
                    body_head: t.slice(0, 300),
                };
            }""")
        await page.screenshot(path=str(PKG / "verify_account_a.png"))
        print(json.dumps({"cookie_names": sorted(set(names)),
                          "url": page.url[-50:], **state}, ensure_ascii=False))
        return 0
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
