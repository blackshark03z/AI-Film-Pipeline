"""V2-020 — read-only conversation diagnosis (no composer interaction)."""
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
from v2_020_runner import PULL_RAW_JS, RECENT_CONVS_JS

NEEDLE = sys.argv[2] if len(sys.argv) > 2 else "camera moving parallel"


async def main() -> int:
    account = sys.argv[1]
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / account)
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
        convs = await page.evaluate(RECENT_CONVS_JS)
        for conv in convs[:8]:
            try:
                rows = await page.evaluate(PULL_RAW_JS,
                                           {"conversationId": conv})
            except Exception:
                continue
            if not any(NEEDLE in (r.get("text") or "") for r in rows):
                continue
            out = {"conversation_id": conv, "rows": [
                {"text": (r.get("text") or "")[:600],
                 "creations": r.get("creations", [])}
                for r in rows[:6]]}
            print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])
            return 0
        print(json.dumps({"status": "CONVERSATION_NOT_FOUND",
                          "checked": len(convs)}))
        return 1
    finally:
        try:
            await manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
