"""Send ONE Flow generation and bind its output by identity, not gallery order.

Usage (repo root):
  python tools/drama_flow_ui/flow_send.py PROMPT_FILE OUT_MP4 [--attach TITLE|tok:TAIL ...]
                                          [--upload FILE ...] [--timeout 600]
                                          [--image] [--start tok:TAIL] [--start-file F]
                                          [--end tok:TAIL] [--end-file F]

Custody (WP1b):
  1. baseline = the set of /asb/ thumbnail tokens in the gallery before send;
  2. batchexecute responses are read in memory while the job runs (never
     written; no signed URL, cookie or token is persisted);
  3. the output is the ONE new token absent from the baseline; it is
     network-bound when a decoded response frame holds both that token and
     the prompt text (``NETWORK_PROMPT_MATCH``), else ``NEW_TILE_ONLY``
     (images only). A video with no network match is bound from its detail
     page (``DETAIL_PROMPT_MATCH``, see ``flow_bind.py``);
  4. the video under that exact tile is downloaded and hashed.
Result: PASSED, BLOCKED, SEND_FAILED, AMBIGUOUS, UNBOUND or TIMEOUT, written as a JSON
manifest next to OUT_MP4 (``<stem>.take.json``). Every send spends credits.
Never reads cookies, never closes the browser.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_bind as fb  # noqa: E402

CDP = "http://127.0.0.1:9333"
TOKEN_RE = re.compile(r"/asb/([A-Za-z0-9_\-]{24,})")
PLUS_XY = (358, 662)          # composer "+" (CSS px, 1280x720 viewport)
START_XY = (379, 563)         # "Khung hình" start-frame slot (fallback; the slot is found by its button text)
END_DX = 98                   # the end slot sits this many CSS px right of the start slot (measured, 56 px buttons)
SLOT_LABEL = {"start": "Bắt đầu", "end": "Kết thúc"}
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
JS_PICKER_AT = r"""(t) => { const i = [...document.images].find(
    i => { const r = i.getBoundingClientRect();
        return (i.currentSrc || i.src).includes(t) && r.width > 0
            && r.width < 80 && r.y > 0 && r.bottom < innerHeight });
    if (!i) return null; const r = i.getBoundingClientRect();
    return [r.x + r.width / 2, r.y + r.height / 2] }"""

# what a click at (x, y) would hit really is that item
JS_HIT = r"""([t, x, y]) => { const e = document.elementFromPoint(x, y);
    const i = e && (e.tagName === 'IMG' ? e : e.querySelector('img'));
    return !!i && (i.currentSrc || i.src).includes(t) }"""

# the filled slot shows a copy under another media id: compare pixels
# (the start and end slots are 98 px apart: take the image NEAREST to the point, within 60 px)
JS_SLOT_BYTES = r"""async ([x, y]) => { let i = null, best = 60;
    for (const m of document.images) { const r = m.getBoundingClientRect();
        if (!(r.width > 0)) continue;
        const d = Math.hypot(r.x + r.width / 2 - x, r.y + r.height / 2 - y);
        if (d < best) { best = d; i = m } }
    if (!i) return null; const r = await fetch(i.currentSrc || i.src);
    return Array.from(new Uint8Array(await r.arrayBuffer())) }"""

# centre of the visible frame-slot button by its text ("Bắt đầu" start, "Kết thúc" end); the GPM window size changes
JS_FRAME_SLOT = r"""(label) => { const b = [...document.querySelectorAll('button')].find(b => {
    const r = b.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.y < innerHeight
        && (b.innerText || '').includes(label) });
    if (!b) return null; const r = b.getBoundingClientRect();
    return [r.x + r.width / 2, r.y + r.height / 2] }"""

# centres of the picker thumbnails in view: the picker's item column
JS_PICKER_CENTRES = r"""() => [...document.images].map(i => i.getBoundingClientRect())
    .filter(r => r.width > 0 && r.width < 80 && r.y > 0 && r.bottom < innerHeight)
    .map(r => [r.x + r.width / 2, r.y + r.height / 2])"""
SLOT_DIFF_MAX = 4.0      # mean abs grey diff at 64x36; the same still scores 0-1,
                         # a sibling still of the same room 7 (film04 plate), others >= 40
PICKER_MARGIN = 3.0      # the best picker match must beat the runner-up by this much


def slot_diff(data: bytes, still: Path) -> float:
    import cv2
    import numpy as np

    def grey(img):
        return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),
                          (64, 36)).astype(float)
    a = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return float(np.abs(grey(a) - grey(cv2.imread(str(still)))).mean())

JS_VIDEO_AT =r"""([x, y]) => { const v = [...document.querySelectorAll('video')]
    .find(v => { const r = v.getBoundingClientRect();
        return r.left <= x && x <= r.right && r.top <= y && y <= r.bottom });
    return v ? (v.currentSrc || v.src) : null }"""


# over each picker's item column: "+" attach list, start-frame slot list
ATTACH_LIST_XY, START_LIST_XY = (384, 400), (142, 400)


# the composer "+" (add-menu trigger); fixed PLUS_XY only when it is not in the DOM
JS_PLUS = r"""() => { const b = [...document.querySelectorAll('button.add-menu-trigger')].find(b => {
    const r = b.getBoundingClientRect(); return r.width > 0 && r.y < innerHeight && r.bottom > 0 });
    if (!b) return null; const r = b.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2] }"""


async def _plus_xy(page) -> tuple[float, float]:
    """The composer "+", found in the DOM: the GPM window size changes (1397x655 on 2026-11-08), PLUS_XY then misses."""
    xy = await page.evaluate(JS_PLUS)
    return (xy[0], xy[1]) if xy else PLUS_XY


async def _slot_xy(page, which: str) -> tuple[float, float]:
    """Centre of the start/end slot button, found by its text; fixed coordinates only when the text is not there."""
    xy = await page.evaluate(JS_FRAME_SLOT, SLOT_LABEL[which])
    if xy:
        return xy[0], xy[1]
    return START_XY if which == "start" else (START_XY[0] + END_DX, START_XY[1])


async def _list_xy(page) -> tuple[float, float]:
    """Where to wheel the open picker: median of its visible thumbnails (START_LIST_XY when none shows)."""
    centres = await page.evaluate(JS_PICKER_CENTRES)
    if not centres:
        return START_LIST_XY
    return statistics.median(c[0] for c in centres), statistics.median(c[1] for c in centres)


async def _fill_frame_slot(page, which: str, tok: str, still: Path | None, rec: dict) -> str | None:
    """Put a gallery image into the start or end "Khung hình" slot; None = done, else the failure result.

    By position: after a failed job the slot still holds the old frame; the first click then only clears it, so
    click again."""
    name = which.upper()
    slot = await _slot_xy(page, which)
    xy = None
    for _ in range(2):
        await page.mouse.click(*slot)
        await page.wait_for_timeout(1500)
        over = await _list_xy(page)
        xy = await _picker_find(page, tok[4:], over)
        rec[f"{which}_found_by"] = "token_tail"
        if xy is None and still:   # tail changed: use pixels
            xy = await _picker_find_image(page, Path(still), over)
            rec[f"{which}_found_by"] = "pixels"
        if xy is not None:
            break
    await page.wait_for_timeout(500)
    if xy is None:
        return f"{name}_NOT_FOUND {tok}"
    await page.mouse.click(*xy)
    await page.wait_for_timeout(800)
    add = page.get_by_text("Thêm vào câu lệnh", exact=True)
    if await add.count():   # some picker states fill the slot directly
        await add.click()
    await page.wait_for_timeout(2000)
    # film03 SC02_g2/SC03_g1: the slot stayed empty and Flow made a
    # text-only video; check the slot holds this frame before paying
    if still:
        data = await page.evaluate(JS_SLOT_BYTES, list(slot))
        diff = slot_diff(bytes(data), Path(still)) if data else None
        rec[f"{which}_slot_diff"] = diff and round(diff, 1)
        if diff is None or diff > SLOT_DIFF_MAX:
            return f"{name}_NOT_SET {tok}"
    return None


async def _picker_to_top(page, over: tuple[int, int], wheels: int = 12):
    """The picker reopens at its last scroll position (film04 SC01_g1 t7: it
    opened mid-list, the search only wheeled down and never saw the newest
    still at the top). Both searches start from the top."""
    await page.mouse.move(*over)
    for _ in range(wheels):
        await page.mouse.wheel(0, -1000)
        await page.wait_for_timeout(150)


async def _picker_find(page, tok: str, over: tuple[int, int],
                       scrolls: int = 16):
    """The picker renders only the items in view (about 15; film03 lost
    its lobby plate after three new stills): wheel down until it shows.

    No scrollIntoView: the list is a cdk virtual scroll that recycles its
    <img> nodes, so after a programmatic scroll the node found showed a
    neighbour and the click picked it (film03: NORA attached for KESSLER,
    wrong start frames). Click only where elementFromPoint hits the item."""
    await _picker_to_top(page, over)
    for _ in range(scrolls + 1):
        await page.wait_for_timeout(300)
        xy = await page.evaluate(JS_PICKER_AT, tok)
        if xy is not None and await page.evaluate(JS_HIT, [tok, *xy]):
            await page.wait_for_timeout(300)
            if await page.evaluate(JS_PICKER_AT, tok) == xy:
                return xy
            continue
        await page.mouse.move(*over)
        await page.mouse.wheel(0, 250)
        await page.wait_for_timeout(500)
    return None


JS_PICKER_THUMBS = r"""async () => { const out = [];
    for (const i of document.images) { const r = i.getBoundingClientRect();
        if (!(r.width > 0 && r.width < 80 && r.y > 0 && r.bottom < innerHeight)) continue;
        try { const b = await (await fetch(i.currentSrc || i.src)).arrayBuffer();
            out.push([r.x + r.width / 2, r.y + r.height / 2, Array.from(new Uint8Array(b))]);
        } catch (_) {} }
    return out }"""


async def _picker_find_image(page, still: Path, over: tuple[int, int],
                             scrolls: int = 16):
    """Find the picker item that IS the approved still, by its pixels.

    A thumbnail token tail changes between page loads (P3-05 attempt 4: the
    same still showed under another token), so the tail cannot name it. The
    pixels can: one picker image must match the still (diff <=
    SLOT_DIFF_MAX) and beat the runner-up by PICKER_MARGIN (a sibling still of
    the same room scores about 7). Otherwise None. The slot is checked again
    after the click (start_slot_diff)."""
    await _picker_to_top(page, over)
    for _ in range(scrolls + 1):
        await page.wait_for_timeout(300)
        scored = []
        for x, y, data in await page.evaluate(JS_PICKER_THUMBS):
            try:
                scored.append((slot_diff(bytes(data), still), x, y))
            except Exception:  # noqa: BLE001 - undecodable thumbnail
                continue
        scored.sort()
        if scored and scored[0][0] <= SLOT_DIFF_MAX:
            if len(scored) == 1 or scored[1][0] >= scored[0][0] + PICKER_MARGIN:
                return scored[0][1], scored[0][2]
            return None   # two near-identical candidates: refuse
        await page.mouse.move(*over)
        await page.mouse.wheel(0, 250)
        await page.wait_for_timeout(500)
    return None


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


JS_SCROLL_STEP = r"""(y) => { let moved = false;
    document.querySelectorAll('*').forEach(e => {
        if (e.clientHeight > 300 && e.scrollHeight > e.clientHeight + 50
            && getComputedStyle(e).overflowY !== 'visible') {
            const was = e.scrollTop; e.scrollTop = y; if (e.scrollTop !== was) moved = true } });
    return moved }"""

# video containers with their absolute grid position (scroller-relative), so a
# recycled virtual-list node or a repeated title never counts twice
JS_VIDEO_GRID = r"""() => [...document.querySelectorAll('flow-grid-tile-container')]
    .filter(c => c.querySelector('flow-video-tile')).map(c => {
        let s = c.parentElement;
        while (s && !(s.clientHeight > 300 && s.scrollHeight > s.clientHeight + 50
                      && getComputedStyle(s).overflowY !== 'visible')) s = s.parentElement;
        const r = c.getBoundingClientRect(), sr = s ? s.getBoundingClientRect() : {top: 0};
        return [Math.round((r.top - sr.top + (s ? s.scrollTop : 0)) / 8),
                Math.round(r.left / 8), c.getAttribute('aria-label') || ''] })"""

# mark the n-th video tile of the grid at scroll 0 (top-to-bottom, left-to-right)
JS_MARK_NTH = r"""(n) => { document.querySelectorAll('[data-vp-n]').forEach(e => e.removeAttribute('data-vp-n'));
    const cs = [...document.querySelectorAll('flow-grid-tile-container')]
        .filter(c => c.querySelector('flow-video-tile'))
        .map(c => { const r = c.getBoundingClientRect(); return [r.top, r.left, c] })
        .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    if (!cs[n]) return false; cs[n][2].setAttribute('data-vp-n', '1'); return true }"""

JS_MARKED_TOKEN = r"""() => { const c = document.querySelector('[data-vp-n]');
    const i = c && c.querySelector('img');
    const m = i && (i.currentSrc || i.src).match(/\/asb\/([A-Za-z0-9_\-]{24,})/);
    return m ? m[1] : null }"""


async def video_count(page) -> int:
    """Number of video tiles in the (virtualised) gallery, each counted once by
    its grid position; scrolled through top to bottom, then back to the top."""
    seen: set[tuple[int, int]] = set()
    for y in range(0, 40000, 400):
        moved = await page.evaluate(JS_SCROLL_STEP, y)
        await page.wait_for_timeout(600)
        seen.update((a, b) for a, b, _ in await page.evaluate(JS_VIDEO_GRID))
        if not moved and y > 0:
            break
    await page.evaluate(JS_TOP)
    await page.wait_for_timeout(500)
    return len(seen)


async def read_nth_detail(page, n: int, home: str) -> dict | None:
    """Open the n-th video tile (gallery at scroll 0), read its detail page
    (URL has the media id, body has the prompt), come back to the gallery."""
    await page.evaluate(JS_TOP)
    await page.wait_for_timeout(500)
    if not await page.evaluate(JS_MARK_NTH, n):
        return None
    await page.locator("[data-vp-n] flow-video-tile").first.click(timeout=8000)
    await page.wait_for_timeout(3500)
    out = {"url": page.url, "text": await page.evaluate("document.body.innerText")}
    await page.goto(home, timeout=45000)
    await page.wait_for_timeout(4000)
    await page.evaluate(JS_TOP)
    return out


async def front_snapshot(page, home: str) -> dict:
    """Before the send: how many videos exist and which media id is in front."""
    n = await video_count(page)
    d = await read_nth_detail(page, 0, home) if n else None
    return {"n": n, "front_id": fb.media_id_from_url(d["url"]) if d else None}


async def detail_bind(page, pre: dict, prompt: str, rec: dict) -> str | None:
    """P12-01: bind the new front video tile; returns its thumbnail token.

    Proof, not position: one more tile than before, the old front tile now
    second (same media id), the new front tile is a different media id and
    its detail page holds the whole sent prompt."""
    home = page.url
    n_after = await video_count(page)
    front = second = None
    if n_after == pre["n"] + 1:
        front = await read_nth_detail(page, 0, home)
        if pre["n"]:
            second = await read_nth_detail(page, 1, home)
    verdict = fb.decide_front(pre["n"], n_after, pre["front_id"], front, second, prompt)
    rec["detail_bind"] = {"n_before": pre["n"], "n_after": n_after,
                          **{k: (v[-8:] if k == "media_id" else v) for k, v in verdict.items()}}
    if verdict["result"] != "BOUND":
        rec["result"] = verdict["result"]
        return None
    await page.evaluate(JS_MARK_NTH, 0)
    for _ in range(6):   # the thumbnail of a finished tile can load late
        tok = await page.evaluate(JS_MARKED_TOKEN)
        if tok:
            rec["binding"] = verdict["binding"]
            rec["media_id_tail"] = verdict["media_id"][-8:]
            return tok
        await page.wait_for_timeout(5000)
        await page.evaluate(JS_MARK_NTH, 0)
    rec["result"], rec["detail_bind"]["why"] = "UNBOUND", "bound tile has no thumbnail token"
    return None


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
           **({"end": args.end} if args.end else {}),
           "upload": [Path(u).name for u in args.upload],
           "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(CDP, timeout=30000)
        ctx = browser.contexts[0]
        page = next(p for p in ctx.pages if "flow.google" in p.url)
        rec["project"] = page.url.rsplit("/", 1)[-1][:36]
        # the click coordinates above are calibrated for 1280x720 CSS px; a GPM window of another size shifts them
        await page.set_viewport_size({"width": 1280, "height": 720})
        await page.keyboard.press("Escape")
        await page.evaluate(JS_TOP)
        await page.wait_for_timeout(1500)
        baseline = set(await page.evaluate(JS_TOKENS))
        # P12-01: the video count and the front media id BEFORE the send; a lazy
        # thumbnail can make an old clip look new by token, a media id never changes
        pre = None if args.image else await front_snapshot(page, page.url)
        bodies: list[str] = []

        trace: list[dict] = []   # P3-05: where does a video result arrive? paths only, never bodies or signed URLs

        async def on_response(resp):
            # video jobs answer on batchexecute, image jobs on a REST call
            wanted = "batchexecute" in resp.url or "generate" in resp.url.lower()
            seen = resp.request.resource_type in ("xhr", "fetch") and "flow.google" in resp.url
            if len(bodies) < MAX_BODIES and (wanted or seen):
                try:
                    body = await resp.text()
                except Exception:  # noqa: BLE001 - body may be gone
                    return
                if wanted:
                    bodies.append(body)
                if len(trace) < 80:
                    trace.append({"path": resp.url.split("?")[0].split("flow.google.com")[-1][-90:], "bytes": len(body),
                                  "status": resp.status, "kept": wanted, "_body": body})
        page.on("response", on_response)

        for f in args.upload:
            async with page.expect_file_chooser(timeout=15000) as fc:
                await page.mouse.click(*await _plus_xy(page))
                await page.wait_for_timeout(1200)
                await page.get_by_text("Tải nội dung", exact=False).last.click()
            await (await fc.value).set_files([f])
            await page.wait_for_timeout(15000)
            await page.keyboard.press("Escape")
        for which, tok, still in (("start", args.start, args.start_file), ("end", args.end, args.end_file)):
            if tok:   # "Khung hình" mode: image into the start / end frame slot (start first)
                failed = await _fill_frame_slot(page, which, tok, Path(still) if still else None, rec)
                if failed:
                    rec["result"] = failed
                    return rec
        for title in args.attach:
            await page.mouse.click(*await _plus_xy(page))
            await page.wait_for_timeout(1500)
            if title.startswith(("tok:", "file:")):   # picker item by thumbnail token, or by the pixels of a local copy
                over = await _list_xy(page)
                over = over if over != START_LIST_XY else ATTACH_LIST_XY
                # token tails change between page loads (2026-11-08: tok:4a20dabf of the approved film04 still was gone)
                xy = (await _picker_find(page, title[4:], over) if title.startswith("tok:")
                      else await _picker_find_image(page, Path(title[5:]), over))
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
        for entry in trace:   # booleans only: which response mentions the prompt / a new tile
            body = entry.pop("_body")
            entry["has_prompt"] = prompt[:30] in body or json.dumps(prompt[:30])[1:-1] in body
            entry["has_new_token"] = any(t in body for t in new)
        rec["net_trace"] = trace
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
        elif len(new) == 1 and not bound and args.image:
            token, rec["binding"] = next(iter(new)), "NEW_TILE_ONLY"
        elif not args.image and not bound:
            # film03: four failed video jobs each "found" one new tile -- an
            # older take's re-issued thumbnail -- and saved that take again;
            # P3-05: Omni Flash never puts the prompt on the network. A video
            # is kept only when the gallery has exactly one more video, the old
            # front video is now second and the new front video's detail page
            # holds the whole sent prompt (DETAIL_PROMPT_MATCH).
            token = await detail_bind(page, pre, prompt, rec)
            if token is None:
                tail = await page.evaluate(
                    "document.body.innerText.slice(0, 1500)")
                rec["page_hint"] = [ln for ln in tail.splitlines()
                                    if re.search(r"(?i)không|lỗi|policy|chính sách|thất bại|error", ln)][:5]
                return rec
        else:
            rec["result"] = "AMBIGUOUS"
            rec["bound_tiles"] = len(bound)
            return rec
        rec["output_token_sha256"] = _sha(token)
        rec["token_tail"] = token[-10:]   # media id tail for --attach/--start
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
    ap.add_argument("--attach", nargs="*", default=[],
                    help="picker items: TITLE, tok:TAIL, or file:PATH (found by the pixels of that local image)")
    ap.add_argument("--upload", nargs="*", default=[])
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--start", default="",
                    help="tok:TAIL of a gallery image for the start frame")
    ap.add_argument("--start-file", default="",
                    help="local copy of that frame: the filled slot must "
                         "match it before anything is sent")
    ap.add_argument("--end", default="",
                    help="tok:TAIL of a gallery image for the end frame")
    ap.add_argument("--end-file", default="",
                    help="local copy of the end frame: the filled end slot must match it")
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
