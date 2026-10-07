"""V2-016 Phase 3b — extract 'finalize'/'2.5' contexts from Dola bundles."""
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

PKG = ROOT / "projects/quality_v2_016_seedance25_capability"

CONCEPTS = [r"finalize", r"draft", r"seedance", r"upscale", r"enhance"]


def utcnow():
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    from patchright.async_api import async_playwright
    record = {"version": "v2-016-dola-bundle-contexts-v1",
              "recorded_at": utcnow()}
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_D")

    async def run():
        await manager.launch_browser()
        page = manager._page
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        scripts = await page.evaluate(
            """() => Array.from(document.querySelectorAll('script[src]'))
               .map(s => s.src).filter(s => s.includes('.js'))""")
        contexts = {}
        for url in scripts[:25]:
            try:
                resp = await page.request.get(url)
                body = await resp.text()
            except Exception:
                continue
            short = url.split("/")[-1][:24]
            for c in CONCEPTS:
                for m in list(re.finditer(c, body, re.IGNORECASE))[:14]:
                    ctx = body[max(0, m.start() - 150):m.end() + 200]
                    ctx = ctx.replace("\n", " ")
                    contexts.setdefault(short + "|" + c, []).append(ctx[:330])
        record["contexts"] = contexts
        print("context groups:", len(contexts))
        for k, v in contexts.items():
            print("==", k, f"({len(v)} hits)")
            print("  ", v[0][:260])

    try:
        await run()
    except Exception as e:
        record["run_error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            await manager.close()
        except Exception:
            pass
    (PKG / "V2_016_DOLA_BUNDLE_CONTEXTS.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False)[:400000],
        encoding="utf-8")
    print("wrote V2_016_DOLA_BUNDLE_CONTEXTS.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
