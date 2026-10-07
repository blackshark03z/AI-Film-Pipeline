"""V2-016 Phases 2-3 — Dola frontend static reconstruction (read-only).

Collects the script bundle URLs the authenticated app loads, fetches the
largest bundles, and greps them for Draft/Final/Seedance-2.5/upscale concepts.
No control is toggled, no generation is submitted.
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

PKG = ROOT / "projects/quality_v2_016_seedance25_capability"

CONCEPTS = [
    r"draft[_-]?mode", r"draft[_-]?task", r"draft[_-]?id", r"draftToFinal",
    r"draft[_-]?final", r"finalize", r"finaliz", r"upscale", r"enhance",
    r"seedance[_ -]?2\.5", r"seedance.{0,12}2\.5", r"2\.5", r"480p.{0,40}1080p",
    r"modelVersion", r"quality[_-]?upgrade", r"high[_-]?quality",
    r"videoModel", r"clip[_-]?generate",
]


def utcnow():
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    from patchright.async_api import async_playwright
    record = {"version": "v2-016-dola-frontend-re-v1",
              "checkpoint": "V2016_P3_FRONTEND_RE",
              "recorded_at": utcnow(),
              "mode": "READ-ONLY: loaded-bundle collection + static grep"}
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
        record["script_urls"] = scripts[:40]
        print("script bundles:", len(scripts))
        results = []
        for url in scripts[:25]:
            try:
                resp = await page.request.get(url)
                body = await resp.text()
            except Exception:
                continue
            hits = {}
            for c in CONCEPTS:
                found = re.findall(c, body, re.IGNORECASE)
                if found:
                    hits[c] = len(found)
            results.append({"url_head": url[:110], "size": len(body),
                            "concept_hits": hits})
            if hits:
                print(url[:80], "->", hits)
        record["bundle_scan"] = results
        # also scan runtime state objects for model/version info
        runtime = await page.evaluate(
            """() => {
              const out = {};
              try {
                const w = window;
                out.hasModelConfig = !!(w.__MODEL_CONFIG__ || w.__APP_CONFIG__);
                const texts = [];
                for (const k of Object.keys(w)) {
                  try {
                    const v = w[k];
                    if (v && typeof v === 'object' && JSON.stringify(v).toLowerCase().includes('seedance')) {
                      texts.push(k);
                    }
                  } catch (e) {}
                }
                out.seedance_globals = texts.slice(0, 10);
              } catch (e) {}
              return out;
            }""")
        record["runtime_state"] = runtime
        print("runtime:", runtime)

    try:
        await run()
    except Exception as e:
        record["run_error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            await manager.close()
        except Exception:
            pass
    (PKG / "V2_016_DOLA_FRONTEND_RE.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False)[:300000],
        encoding="utf-8")
    print("wrote V2_016_DOLA_FRONTEND_RE.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
