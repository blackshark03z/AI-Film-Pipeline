"""Hover a gallery tile at CSS (x, y), then download the <video> that appears
under that point (URL not persisted)."""
import asyncio, hashlib, sys
from pathlib import Path

async def main(x, y, out):
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        b = await pw.chromium.connect_over_cdp("http://127.0.0.1:9333")
        page = [p for p in b.contexts[0].pages if "flow.google" in p.url][0]
        await page.mouse.move(x, y)
        await page.wait_for_timeout(2500)
        src = await page.evaluate("""([x, y]) => {
            const vs = [...document.querySelectorAll('video')].filter(v => {
                const r = v.getBoundingClientRect();
                return r.left <= x && x <= r.right && r.top <= y && y <= r.bottom; });
            const v = vs[0]; return v ? (v.currentSrc || v.src) : null }""", [x, y])
        if not src:
            print("no video under point"); return
        resp = await b.contexts[0].request.get(src, timeout=300000)
        print("status", resp.status, resp.headers.get("content-type"))
        raw = await resp.body()
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_bytes(raw)
        print("saved", out, len(raw), hashlib.sha256(raw).hexdigest())
    finally:
        await pw.stop()

asyncio.run(main(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]))
