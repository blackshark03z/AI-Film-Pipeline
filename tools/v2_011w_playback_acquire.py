"""V2-011W — acquire the provider-issued playback stream (read-only).

The player's <video>.currentSrc IS a provider-delivered URL (unmodified,
in-page). This tool fetches that exact URL from the authenticated page
context, transfers the bytes to disk in robust base64 chunks, and records
the URL structure (lr marker + param names; signed values never persisted).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_011w_unwatermarked_authority"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def structure(u: str) -> dict:
    p = urlparse(u)
    q = parse_qsl(p.query)
    return {"host": p.netloc, "path_head": p.path[:100],
            "path_tail": p.path[-60:],
            "lr": next((v for k, v in q if k.lower() == "lr"), None),
            "param_names": sorted(k for k, _ in q)}


async def main() -> int:
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        str(ACCOUNT_PROFILES / "ACCOUNT_D"), headless=False,
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run"],
        locale="ja-JP", timezone_id="Asia/Tokyo", accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    record = {"version": "v2-011w-playback-acquisition-v1",
              "built_at": utcnow(),
              "mode": "READ-ONLY acquisition of the exact in-page player "
                      "src URL (provider-issued, unmodified) — a normal "
                      "asset download of an existing creation"}
    try:
        await page.goto("https://www.dola.com/chat/38417944671772433",
                        timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        for _ in range(5):
            await page.keyboard.press("End")
            await page.wait_for_timeout(600)
        await page.evaluate("""() => {
          const btn = document.querySelector(
            '[class*=play],[aria-label*=play],[aria-label*=再生]');
          if (btn) { btn.click(); return; }
          const poster = document.querySelector(
            '[class*=video-player],[class*=player],[class*=video]');
          if (poster) poster.click();
        }""")
        await page.wait_for_timeout(6000)
        srcs = await page.evaluate(
            """() => Array.from(document.querySelectorAll('video'))
               .map(v => v.currentSrc || v.src || '').filter(Boolean)""")
        record["player_src_structural"] = [structure(s) for s in srcs]
        print("player srcs:", json.dumps(record["player_src_structural"],
                                         ensure_ascii=False, indent=1))
        if not srcs:
            record["status"] = "NO_PLAYER_SRC"
            (PKG / "V2_011W_PLAYBACK_ACQUISITION.json").write_text(
                json.dumps(record, indent=1, ensure_ascii=False),
                encoding="utf-8")
            await ctx.close()
            await pw.stop()
            return 1
        url = srcs[0]
        n = await page.evaluate(
            """async (u) => {
              const r = await fetch(u, {credentials: 'include'});
              if (!r.ok) return {error: 'http_' + r.status};
              const buf = new Uint8Array(await r.arrayBuffer());
              window.__v011wbuf = buf;
              return {len: buf.length};
            }""", url)
        if "error" in n:
            record["status"] = "FETCH_FAILED"
            record["fetch_error"] = n["error"]
            (PKG / "V2_011W_PLAYBACK_ACQUISITION.json").write_text(
                json.dumps(record, indent=1, ensure_ascii=False),
                encoding="utf-8")
            await ctx.close()
            await pw.stop()
            return 1
        total = n["len"]
        print("fetched bytes:", total)
        step = 262144
        sha = hashlib.sha256()
        out = PKG / "downloads" / "f3r_012_playback_stream.mp4"
        out.parent.mkdir(exist_ok=True)
        with out.open("wb") as f:
            off = 0
            while off < total:
                b64 = await page.evaluate(
                    """([off, step]) => {
                      const buf = window.__v011wbuf;
                      const end = Math.min(off + step, buf.length);
                      let bin = '';
                      const chunk = buf.subarray(off, end);
                      const k = 8192;
                      for (let i = 0; i < chunk.length; i += k) {
                        bin += String.fromCharCode.apply(
                          null, chunk.subarray(i, Math.min(i + k, chunk.length)));
                      }
                      return btoa(bin);
                    }""", [off, step])
                raw = base64.b64decode(b64)
                f.write(raw)
                sha.update(raw)
                off += step
                if off % (step * 4) == 0:
                    print("  transferred", off, "/", total)
        record["acquired"] = {"path": str(out), "size": total,
                              "sha256": sha.hexdigest(),
                              "url_structure": structure(url)}
        print("ACQUIRED sha256:", sha.hexdigest())
        record["status"] = "ACQUIRED"
        (PKG / "V2_011W_PLAYBACK_ACQUISITION.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False),
            encoding="utf-8")
        print("wrote V2_011W_PLAYBACK_ACQUISITION.json")
    finally:
        await ctx.close()
        await pw.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
