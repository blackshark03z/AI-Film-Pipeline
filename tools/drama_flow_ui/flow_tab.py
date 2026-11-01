"""Drive ONE Dola tab inside a running GPM profile over CDP.

Usage: gpm_tab.py <command> [arg]
  open                 open (or reuse) our tab on /chat
  shot <file>          screenshot our tab
  text                 print visible body text (trimmed)
  click <text>         click the first visible element with exact text
  type <text>          type into the composer and press Enter
  imgs                 list large <img> sources on the page
  save <dir>           download large images (in-page fetch) to dir
  js <expr>            evaluate expression
Never reads, prints or exports cookies. Never closes the GPM browser.
"""
import asyncio
import json
import sys
from pathlib import Path

ONECLICK = Path("D:/AI FILM MAKER/AI-Film-Pipeline-OneClick")
sys.path.insert(0, str(ONECLICK / "tools"))
from dola_gpm_adapter import GpmApi, _cdp_endpoint  # noqa: E402

import os
PROFILE_ID = os.environ.get("GPM_PROFILE", "63c2627e-0c31-4afc-b0bc-6f750dd20ec2")
MARK = "claude_ref_tab"


async def main(cmd: str, arg: str) -> None:
    from patchright.async_api import async_playwright
    endpoint = "http://127.0.0.1:9333"
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(endpoint, timeout=30000)
        context = browser.contexts[0]
        page = None
        for candidate in context.pages:
            try:
                if "flow.google" in candidate.url or "labs.google" in candidate.url:
                    page = candidate
            except Exception:
                pass
        if page is None:
            page = context.pages[0]
        if cmd == "open":
            print(page.url)
        elif cmd == "front":
            await page.bring_to_front()
            print(await page.evaluate("document.visibilityState"))
        elif cmd == "shot":
            await page.screenshot(path=arg)
            print("saved", arg)
        elif cmd == "text":
            body = await page.evaluate("document.body.innerText")
            print(body[-3000:])
        elif cmd == "click":
            exact = not arg.startswith("~")
            await page.get_by_text(arg.lstrip("~"), exact=exact).last.click(
                timeout=10000)
            await page.wait_for_timeout(1500)
            print("clicked", arg)
        elif cmd == "clickxy":
            x, y = (float(v) for v in arg.split())
            await page.mouse.click(x, y)
            await page.wait_for_timeout(1500)
            print("clicked at", x, y)
        elif cmd == "menu":
            # click and inspect in the same connection (popovers may close
            # when the CDP client reconnects)
            x, y, shot = arg.split(" ", 2)
            await page.mouse.click(float(x), float(y))
            await page.wait_for_timeout(1500)
            await page.screenshot(path=shot)
            print(await page.evaluate("""[...document.querySelectorAll(
                '[data-radix-popper-content-wrapper],[role=menu],'
                + '[role=listbox],[role=dialog]')].map(e => e.innerText)"""))
        elif cmd == "kmenu":
            # open a radix menu button by keyboard; arg = "<prefix>|<shot>"
            prefix, shot = arg.split("|", 1)
            btn = page.locator("[aria-haspopup=menu]").filter(
                has_text=prefix).first
            await btn.focus()
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=shot)
            print(await btn.get_attribute("data-state"))
            print(await page.evaluate("""[...document.querySelectorAll(
                '[role=menu]')].map(e => e.innerText)"""))
        elif cmd == "upload":
            # arg = "<x> <y>|<menu item text>|file1|file2..."
            xy, item, *files = arg.split("|")
            x, y = (float(v) for v in xy.split())
            if item == "!":   # "+" opens the file chooser directly
                async with page.expect_file_chooser(timeout=15000) as fc:
                    await page.mouse.click(x, y)
                await (await fc.value).set_files(files)
                await page.wait_for_timeout(15000)
                print("uploaded", len(files))
                return
            await page.mouse.click(x, y)
            await page.wait_for_timeout(1200)
            if item:
                async with page.expect_file_chooser(timeout=15000) as fc:
                    await page.get_by_text(item, exact=True).last.click()
                chooser = await fc.value
                await chooser.set_files(files)
            else:   # menu not rendered: feed the file input directly
                inputs = page.locator('input[type="file"]')
                print("file inputs:", await inputs.count())
                await inputs.last.set_input_files(files)
            await page.wait_for_timeout(15000)
            print("uploaded", len(files))
        elif cmd == "status":
            info = await page.evaluate("""() => ({
                url: location.href,
                videos: [...document.querySelectorAll('video')].map(v => ({
                    src: (v.currentSrc || v.src || '').slice(0, 200),
                    dur: v.duration})),
                tail: (document.querySelector('main') || document.body)
                    .innerText.slice(-900)})""")
            print(json.dumps(info, ensure_ascii=False, default=str))
        elif cmd == "getvideo":
            # download the last video link; signed URL is transport-only
            import hashlib
            import urllib.request
            href = await page.evaluate("""() => { const a = [...document
                .querySelectorAll('a[href*="/video/"]')].pop();
                return a ? a.href : null }""")
            if not href:
                print("no video link")
                return
            out = Path(arg)
            out.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(href, timeout=300) as resp:
                data = resp.read()
            out.write_bytes(data)
            print("saved", out, len(data), hashlib.sha256(data).hexdigest())
        elif cmd == "attach":
            await page.locator('input[type="file"]').first.set_input_files(
                arg.split("|"))
            await page.wait_for_timeout(8000)
            print("attached", arg)
        elif cmd == "key":
            await page.keyboard.press(arg)
            await page.wait_for_timeout(800)
            print("pressed", arg)
        elif cmd == "type":
            box = page.locator("textarea, [contenteditable='true']").first
            await box.click()
            await box.fill(arg)
            await page.wait_for_timeout(500)
            await page.keyboard.press("Enter")
            print("sent")
        elif cmd in ("imgs", "save"):
            srcs = await page.evaluate("""() => [...document.images]
                .filter(i => i.naturalWidth >= 512)
                .map(i => ({src: i.currentSrc || i.src,
                            w: i.naturalWidth, h: i.naturalHeight}))""")
            if cmd == "imgs":
                for s in srcs:
                    print(s["w"], s["h"], s["src"][:160])
            else:
                out = Path(arg)
                out.mkdir(parents=True, exist_ok=True)
                for n, s in enumerate(srcs):
                    data = await page.evaluate(
                        """async (u) => { const r = await fetch(u);
                           const b = new Uint8Array(await r.arrayBuffer());
                           return Array.from(b); }""", s["src"])
                    target = out / f"img_{n:02d}_{s['w']}x{s['h']}.bin"
                    target.write_bytes(bytes(data))
                    print("saved", target, len(data))
        elif cmd == "js":
            print(json.dumps(await page.evaluate(arg), ensure_ascii=False,
                             default=str)[:3000])
    finally:
        await pw.stop()   # disconnect only; GPM browser and tab stay open


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(sys.argv[1], " ".join(sys.argv[2:])))
