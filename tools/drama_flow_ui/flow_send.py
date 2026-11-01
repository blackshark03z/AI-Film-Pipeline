"""Send ONE Flow generation and bind its output by identity, not gallery order.

Usage (repo root):
  python tools/drama_flow_ui/flow_send.py PROMPT_FILE OUT_MP4 [--attach TITLE|tok:TAIL ...]
                                          [--upload FILE ...] [--timeout 600]
                                          [--image] [--start tok:TAIL]

Custody (WP1b):
  1. baseline = the set of /asb/ thumbnail tokens in the gallery before send;
  2. batchexecute responses are read in memory while the job runs (never
     written; no signed URL, cookie or token is persisted);
  3. the output is the ONE new token absent from the baseline; it is
     network-bound when a decoded response frame holds both that token and
     the prompt text (``NETWORK_PROMPT_MATCH``), else ``NEW_TILE_ONLY``;
  4. the video under that exact tile is downloaded and hashed.
Result: PASSED, BLOCKED, SEND_FAILED, AMBIGUOUS or TIMEOUT, written as a JSON
manifest next to OUT_MP4 (``<stem>.take.json``). Every send spends credits.
Never reads cookies, never closes the browser.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

CDP = "http://127.0.0.1:9333"
TOKEN_RE = re.compile(r"/asb/([A-Za-z0-9_\-]{24,})")
PLUS_XY = (358, 662)          # composer "+" (CSS px, 1280x720 viewport)
MAX_BODIES = 400

# videos show an /asb/ thumbnail; generated images a flow-content /image/ URL
JS_TOKENS = r"""() => [...document.images].map(i => {
    const m = (i.currentSrc || i.src).match(
        /(?:\/asb\/|flow-content\.google\/image\/)([A-Za-z0-9_\-]{24,})/);
    return m ? m[1] : null }).filter(Boolean)"""

# the gallery scrolls inside a container, not the window
JS_TOP = r"""() => { window.scrollTo(0, 0); document.querySelectorAll('*')
    .forEach(e => { if (e.scrollTop > 0) e.scrollTop = 0 }) }"""

JS_TILE_RECT = r"""(tok) => { const i = [...document.images].find(
    i => (i.currentSrc || i.src).includes(tok));
    if (!i) return null; i.scrollIntoView({block: 'center'});
    const r = i.getBoundingClientRect();
    return [r.x + r.width / 2, r.y + r.height / 2] }"""

# picker items by token: the same token also sits on the gallery tile behind
# the overlay, only the small picker thumbnail is clickable
JS_PICKER_XY = r"""(t) => { const i = [...document.images].find(
    i => (i.currentSrc || i.src).includes(t)
        && i.getBoundingClientRect().width < 80);
    if (!i) return null; const r = i.getBoundingClientRect();
    return [r.x + r.width / 2, r.y + r.height / 2] }"""

JS_VIDEO_AT = r"""([x, y]) => { const v = [...document.querySelectorAll('video')]
    .find(v => { const r = v.getBoundingClientRect();
        return r.left <= x && x <= r.right && r.top <= y && y <= r.bottom });
    return v ? (v.currentSrc || v.src) : null }"""


def _sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _frames(body: str):
    """Decoded JSON frames of a batchexecute body, nested strings expanded."""
    def expand(v, depth=0):
        if depth > 8:
            return v
        if isinstance(v, str) and v.strip()[:1] in "[{":
            try:
                return expand(json.loads(v), depth + 1)
            except ValueError:
                return v
        if isinstance(v, list):
            return [expand(x, depth + 1) for x in v]
        if isinstance(v, dict):
            return {k: expand(x, depth + 1) for k, x in v.items()}
        return v
    for line in body.splitlines():
        if line[:1] in "[{":
            try:
                yield expand(json.loads(line))
            except ValueError:
                continue


def _subtrees_with(frame, token: str):
    """Smallest list/dict nodes whose serialisation contains the token."""
    out = []

    def walk(v):
        if isinstance(v, (list, dict)):
            items = v if isinstance(v, list) else list(v.values())
            hit = [x for x in items
                   if token in json.dumps(x, ensure_ascii=False)]
            for x in hit:
                walk(x)
            if token in json.dumps(v, ensure_ascii=False):
                out.append(v)
    walk(frame)
    return out


def bind(bodies: list[str], token: str, prompt: str) -> bool:
    """True when one response record holds the token and the prompt text."""
    probe = " ".join(prompt.split())[:80]
    for body in bodies:
        if token not in body:
            continue
        for frame in _frames(body):
            for node in _subtrees_with(frame, token):
                text = " ".join(json.dumps(node, ensure_ascii=False).split())
                # record-level match: keep nodes small enough to be one item
                if probe in text.replace('\\"', '"') and len(text) < 60000:
                    return True
    return False


def probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True,
            timeout=60).stdout.strip()
        return float(out)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


async def run(args) -> dict:
    from patchright.async_api import async_playwright
    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    out = Path(args.out)
    rec = {"prompt_file": str(args.prompt_file), "prompt_sha256": _sha(prompt),
           "prompt_words": len(prompt.split()), "attach": args.attach,
           "start": args.start,
           "upload": [Path(u).name for u in args.upload],
           "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(CDP, timeout=30000)
        ctx = browser.contexts[0]
        page = next(p for p in ctx.pages if "flow.google" in p.url)
        rec["project"] = page.url.rsplit("/", 1)[-1][:36]
        await page.keyboard.press("Escape")
        await page.evaluate(JS_TOP)
        await page.wait_for_timeout(1500)
        baseline = set(await page.evaluate(JS_TOKENS))
        bodies: list[str] = []

        async def on_response(resp):
            # video jobs answer on batchexecute, image jobs on a REST call
            if len(bodies) < MAX_BODIES and ("batchexecute" in resp.url or
                                             "generate" in resp.url.lower()):
                try:
                    bodies.append(await resp.text())
                except Exception:  # noqa: BLE001 - body may be gone
                    pass
        page.on("response", on_response)

        for f in args.upload:
            async with page.expect_file_chooser(timeout=15000) as fc:
                await page.mouse.click(*PLUS_XY)
                await page.wait_for_timeout(1200)
                await page.get_by_text("Tải nội dung", exact=False).last.click()
            await (await fc.value).set_files([f])
            await page.wait_for_timeout(15000)
            await page.keyboard.press("Escape")
        if args.start:   # "Khung hình" mode: image into the start-frame slot
            await page.get_by_text("Bắt đầu", exact=True).last.click()
            await page.wait_for_timeout(1500)
            xy = await page.evaluate(JS_PICKER_XY, args.start[4:])
            if xy is None:
                rec["result"] = f"START_NOT_FOUND {args.start}"
                return rec
            await page.mouse.click(*xy)
            await page.wait_for_timeout(800)
            await page.get_by_text("Thêm vào câu lệnh", exact=True).click()
            await page.wait_for_timeout(2000)
        for title in args.attach:
            await page.mouse.click(*PLUS_XY)
            await page.wait_for_timeout(1500)
            if title.startswith("tok:"):   # picker item by thumbnail token
                xy = await page.evaluate(JS_PICKER_XY, title[4:])
                if xy is None:
                    rec["result"] = f"ATTACH_NOT_FOUND {title}"
                    return rec
                await page.mouse.click(*xy)
            else:
                await page.locator(f"text={title} >> visible=true").first.click()
            await page.wait_for_timeout(800)
            add = page.get_by_text("Thêm vào câu lệnh", exact=True)
            if await add.count():   # image mode attaches on the click itself
                await add.click()
            await page.wait_for_timeout(1500)

        box = page.locator("textarea, [contenteditable='true']").first
        await box.click()
        await box.fill(prompt)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        t0 = time.time()
        await page.wait_for_timeout(8000)
        left = await box.evaluate("e => (e.value ?? e.innerText) || ''")
        if prompt[:40] in left:
            rec["result"] = "SEND_FAILED"
            return rec

        probe = prompt[:30]
        new: set[str] = set()
        while time.time() - t0 < args.timeout:
            await page.wait_for_timeout(10000)
            await page.evaluate(JS_TOP)
            new = set(await page.evaluate(JS_TOKENS)) - baseline
            pending = await page.evaluate(
                "(p) => document.body.innerText.includes(p)", probe)
            if new and not pending:
                break
            if not new and not pending and time.time() - t0 > 30:
                break
        rec["elapsed_s"] = round(time.time() - t0)
        page.remove_listener("response", on_response)
        rec["responses_seen"] = len(bodies)
        if not new:
            tail = await page.evaluate(
                "document.body.innerText.slice(0, 1500)")
            rec["result"] = ("TIMEOUT" if rec["elapsed_s"] >= args.timeout
                             else "BLOCKED")
            rec["page_hint"] = [ln for ln in tail.splitlines()
                                if re.search(r"(?i)không|lỗi|policy|chính sách|thất bại|error", ln)][:5]
            return rec
        # lazy-loaded thumbnails can also be "new": the network binding
        # decides between several candidates, never gallery position
        bound = {t for t in new if bind(bodies, t, prompt)}
        rec["new_tiles"] = len(new)
        if len(bound) == 1:
            token, rec["binding"] = next(iter(bound)), "NETWORK_PROMPT_MATCH"
        elif len(new) == 1 and not bound:
            token, rec["binding"] = next(iter(new)), "NEW_TILE_ONLY"
        else:
            rec["result"] = "AMBIGUOUS"
            rec["bound_tiles"] = len(bound)
            return rec
        rec["output_token_sha256"] = _sha(token)
        if args.image:   # image generations (0 credits): fetch the tile image
            data = bytes(await page.evaluate(
                """async (t) => { const i = [...document.images].find(
                       i => (i.currentSrc || i.src).includes(t));
                   const r = await fetch(i.currentSrc || i.src);
                   return Array.from(new Uint8Array(await r.arrayBuffer())) }""",
                token))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            rec.update(result="PASSED", file=out.name, sha256=_sha(data),
                       bytes=len(data))
            return rec
        xy = await page.evaluate(JS_TILE_RECT, token)
        await page.mouse.move(*xy)
        await page.wait_for_timeout(2500)
        src = await page.evaluate(JS_VIDEO_AT, xy)
        if not src:
            rec["result"] = "NO_VIDEO_UNDER_TILE"
            return rec
        resp = await ctx.request.get(src, timeout=300000)
        ctype = resp.headers.get("content-type", "")
        data = await resp.body()
        if resp.status != 200 or not ctype.startswith("video/"):
            rec["result"] = f"DOWNLOAD_FAILED {resp.status} {ctype}"
            return rec
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        rec.update(result="PASSED", file=out.name, sha256=_sha(data),
                   bytes=len(data), duration_s=probe_duration(out))
        return rec
    finally:
        rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        await pw.stop()   # disconnect only; browser and tab stay open


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt_file")
    ap.add_argument("out")
    ap.add_argument("--attach", nargs="*", default=[])
    ap.add_argument("--upload", nargs="*", default=[])
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--start", default="",
                    help="tok:TAIL of a gallery image for the start frame")
    ap.add_argument("--image", action="store_true",
                    help="composer is in image mode; save the output image")
    args = ap.parse_args()
    rec = asyncio.run(run(args))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = out.with_suffix(".take.json")
    manifest.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(rec.get("result"), rec.get("binding", ""), rec.get("sha256", ""),
          f"{rec.get('elapsed_s', '?')}s")


if __name__ == "__main__":
    main()
