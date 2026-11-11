"""Send ONE Flow generation and bind its output by identity, not gallery order.

Usage (repo root):
  python tools/drama_flow_ui/flow_send.py PROMPT_FILE OUT_MP4 [--attach TITLE|tok:TAIL ...]
                                          [--upload FILE ...] [--timeout 600]
                                          [--image] [--start tok:TAIL] [--start-file F]
                                          [--end tok:TAIL] [--end-file F] [--upload-frames]
                                          [--model NAME] [--duration SECONDS]

Custody (WP1b):
  1. baseline = the set of /asb/ thumbnail tokens in the gallery before send;
  2. batchexecute responses are read in memory while the job runs (never
     written; no signed URL, cookie or token is persisted);
  3. the output is the ONE new token absent from the baseline; it is
     network-bound when a decoded response frame holds both that token and
     the prompt text (``NETWORK_PROMPT_MATCH``), else ``NEW_TILE_ONLY``
     (images only);
  4. the image under that exact tile is saved and hashed.
Videos (P18-01) never use tokens, titles or the video count: the wait ends on a tile whose PIXELS are new and the
clip is bound by its detail page media id + whole prompt, not registered and not in the gallery before the send
(``RECONCILE_PROMPT_MATCH``, see ``reconcile_bind``), then downloaded and hashed.
With --upload-frames the start (and end) still is uploaded inside the send (--start-file / --end-file, start first so
the end is the newest) and picked as the newest picker item, checked by pixels; --start/--end tokens are then not needed.
Result: PASSED, BLOCKED, SEND_FAILED, FLOW_FAILED, AMBIGUOUS, UNBOUND or TIMEOUT, written as a JSON
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
# Flow shows its UI in the account language: the Vietnamese account says "Bắt đầu"/"Kết thúc", the English one "Start"/"End"
SLOT_LABEL = {"start": ["Bắt đầu", "Start"], "end": ["Kết thúc", "End"]}
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
JS_FRAME_SLOT = r"""(arg) => { const labels = Array.isArray(arg) ? arg : [arg]; const b = [...document.querySelectorAll('button')].find(b => {
    const r = b.getBoundingClientRect(), t = (b.innerText || '').trim();
    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.y < innerHeight
        && labels.some(l => t === l || (!/^[ -~]*$/.test(l) && t.includes(l))) });
    if (!b) return null; const r = b.getBoundingClientRect();
    return [r.x + r.width / 2, r.y + r.height / 2] }"""

# centres of the picker thumbnails in view: the picker's item column
JS_PICKER_CENTRES = r"""() => [...document.images].map(i => i.getBoundingClientRect())
    .filter(r => r.width > 0 && r.width < 80 && r.y > 0 && r.bottom < innerHeight)
    .map(r => [r.x + r.width / 2, r.y + r.height / 2])"""
SLOT_DIFF_MAX = 4.0      # mean abs grey diff at 64x36; the same still scores 0-1,
                         # a sibling still of the same room 7 (film04 plate), others >= 40
PICKER_MARGIN = 3.0      # the best picker match must beat the runner-up by this much
SAME_STILL_MAX = 1.0     # ...unless the two are one still uploaded twice (their own diff at most this)


def _grey(data: bytes):
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype(float)


def slot_diff(data: bytes, still: Path) -> float:
    return float(abs(_grey(data) - _grey(Path(still).read_bytes())).mean())


def same_image(a: bytes, b: bytes) -> bool:
    """Two picker thumbnails of one still uploaded twice: equal bytes, or pixels within SAME_STILL_MAX."""
    if a == b:
        return True
    try:
        return float(abs(_grey(a) - _grey(b)).mean()) <= SAME_STILL_MAX
    except Exception:  # noqa: BLE001 - undecodable thumbnail
        return False

JS_VIDEO_AT =r"""([x, y]) => { const v = [...document.querySelectorAll('video')]
    .find(v => { const r = v.getBoundingClientRect();
        return r.left <= x && x <= r.right && r.top <= y && y <= r.bottom });
    return v ? (v.currentSrc || v.src) : null }"""


# over each picker's item column: "+" attach list, start-frame slot list
ATTACH_LIST_XY, START_LIST_XY = (384, 400), (142, 400)
LIST_COLUMN_TOL = 60   # px: a picker thumbnail sits within this of the list column centre


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


async def _fill_frame_slot(page, which: str, tok: str, still: Path | None, rec: dict,
                           newest_k: int | None = None) -> str | None:
    """Put a gallery image into the start or end "Khung hình" slot; None = done, else the failure result.

    By position: after a failed job the slot still holds the old frame; the first click then only clears it, so
    click again.

    ``newest_k`` set = upload mode: the still was uploaded in this send, so it is one of the newest k picker items
    (pixels check only those, no search)."""
    name = which.upper()
    slot = await _slot_xy(page, which)
    xy = None
    uploaded = False
    for _ in range(2):
        await page.mouse.click(*slot)
        await page.wait_for_timeout(1500)
        if newest_k is not None and not uploaded:
            # Video mode has no composer "+" (2026-11-08): upload from inside this slot's picker
            uploaded = await _upload_in_picker(page, Path(still))
            if not uploaded:   # picker not open: the first click only cleared an old frame
                continue
        over = await _list_xy(page)
        if newest_k is not None:
            xy = await _picker_newest(page, Path(still), over, newest_k)
            rec[f"{which}_found_by"] = "upload_newest"
        else:
            xy = await _picker_find(page, tok[4:], over)
            rec[f"{which}_found_by"] = "token_tail"
            if xy is None and still:   # tail changed: use pixels
                xy = await _picker_find_image(page, Path(still), over)
                rec[f"{which}_found_by"] = "pixels"
        if xy is not None:
            break
    await page.wait_for_timeout(500)
    if xy is None:
        return f"{name}_NOT_FOUND upload" if newest_k is not None else f"{name}_NOT_FOUND {tok}"
    await page.mouse.click(*xy)
    await page.wait_for_timeout(800)
    add = page.get_by_text(ADD_TO_PROMPT_RE)
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
                scored.append((slot_diff(bytes(data), still), x, y, bytes(data)))
            except Exception:  # noqa: BLE001 - undecodable thumbnail
                continue
        scored.sort(key=lambda s: s[:3])
        if scored and scored[0][0] <= SLOT_DIFF_MAX:
            # a runner-up that is the same image is the same still uploaded twice (film04 SC01_g2 t2/t3: two copies
            # of the v2 start, both 1.7; SC02_g1 t1: its start reuses end_SC01_g1, thumbnails 2 bytes apart);
            # either copy is right, so take the best
            if (len(scored) == 1 or scored[1][0] >= scored[0][0] + PICKER_MARGIN
                    or same_image(scored[1][3], scored[0][3])):
                return scored[0][1], scored[0][2]
            return None   # two near-identical candidates: refuse
        await page.mouse.move(*over)
        await page.mouse.wheel(0, 250)
        await page.wait_for_timeout(500)
    return None


async def _picker_newest(page, still: Path, over: tuple[int, int], k: int):
    """Upload mode: the still was uploaded in this send, so it is among the newest k picker items (top of the list).

    Scroll to the top, read the visible thumbnails once (no wheel down), keep the first k by (y, x) and score them by
    pixels. The best must score <= SLOT_DIFF_MAX and be the only one within PICKER_MARGIN of that bound, unless its
    competitor is the same image (one still uploaded twice). Otherwise None: an uploaded still outside the newest k
    is a failure, never something to search for."""
    await _picker_to_top(page, over)
    await page.wait_for_timeout(300)
    # only the list column: small page images (the header avatar at y~38, 2026-11-08) would sort above the list
    col = [t for t in await page.evaluate(JS_PICKER_THUMBS) if abs(t[0] - over[0]) <= LIST_COLUMN_TOL]
    thumbs = sorted(col, key=lambda t: (t[1], t[0]))[:k]
    scored = []
    for x, y, data in thumbs:
        try:
            scored.append((slot_diff(bytes(data), still), x, y, bytes(data)))
        except Exception:  # noqa: BLE001 - undecodable thumbnail
            continue
    scored.sort(key=lambda s: s[:3])
    if not scored or scored[0][0] > SLOT_DIFF_MAX:
        return None
    close = [s for s in scored if s[0] <= SLOT_DIFF_MAX + PICKER_MARGIN]
    if len(close) == 1 or all(same_image(c[3], scored[0][3]) for c in close[1:]):
        return scored[0][1], scored[0][2]
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


# the picker's confirm button ("Add to prompt" is the English wording, unverified: a miss is harmless, the slot is checked)
ADD_TO_PROMPT_RE = re.compile(r"^(Thêm vào câu lệnh|Add to prompt)$")
# a rejected job tile: "Không thành công" (vi); English wordings are best guesses, a miss only delays failure detection
FAILED_WORDS = ("Không thành công", "Unsuccessful", "Something went wrong")
FAILED_TEXT = FAILED_WORDS[0]   # the Vietnamese wording; kept for callers that need one marker
FAILED_JS_RE = "/" + "|".join(FAILED_WORDS) + "/g"


def has_failed_text(text: str) -> bool:
    return any(w in (text or "") for w in FAILED_WORDS)


# Flow job state on the gallery page: a running job shows "NN%" (0-99), a rejected one "Không thành công"
JS_JOB_STATE = r"""() => { const t = document.body.innerText;
  return {running: /^\s*\d{1,2}%\s*$/m.test(t),
          failed: 0}; }"""
JS_JOB_STATE = JS_JOB_STATE.replace("failed: 0", "failed: (t.match(" + FAILED_JS_RE + ") || []).length")


# The gallery is a virtual list that mixes images and videos: a young project shows only its first rows at scroll 0.
# Keys are "row:col" of the tile's container in absolute (scroll-independent) 40 px cells.
JS_VIDEO_KEYS = r"""() => { let top = 0;
    document.querySelectorAll('*').forEach(e => { if (e.clientHeight > 300 && e.scrollHeight > e.clientHeight + 50
        && getComputedStyle(e).overflowY !== 'visible' && e.scrollTop > top) top = e.scrollTop });
    const keys = [...document.querySelectorAll('flow-grid-tile-container')].filter(c => c.querySelector('flow-video-tile'))
        .map(c => { const r = c.getBoundingClientRect(); return Math.round((r.top + top) / 40) + ':' + Math.round(r.left / 40) });
    return {top, keys} }"""

JS_MARK_KEY = r"""(key) => { document.querySelectorAll('[data-vp-n]').forEach(e => e.removeAttribute('data-vp-n'));
    let top = 0;
    document.querySelectorAll('*').forEach(e => { if (e.clientHeight > 300 && e.scrollHeight > e.clientHeight + 50
        && getComputedStyle(e).overflowY !== 'visible' && e.scrollTop > top) top = e.scrollTop });
    for (const c of document.querySelectorAll('flow-grid-tile-container')) {
        if (!c.querySelector('flow-video-tile')) continue;
        const r = c.getBoundingClientRect();
        if (Math.round((r.top + top) / 40) + ':' + Math.round(r.left / 40) === key) { c.setAttribute('data-vp-n', '1'); return true } }
    return false }"""

SCROLL_STEP_PX = 500   # below the 720 px viewport, so no row is skipped between two steps


async def mark_nth_video(page, n: int) -> bool:
    """Mark the n-th video tile (top-to-bottom, left-to-right), scrolling the virtual grid when the first rows hold fewer.
    False only once the grid is scrolled to its end and no n-th video exists: the gallery is exhausted."""
    if await page.evaluate(JS_MARK_NTH, n):
        return True
    seen: dict[str, float] = {}
    y = 0
    while True:
        state = await page.evaluate(JS_VIDEO_KEYS)
        for key in state["keys"]:
            seen.setdefault(key, state["top"])
        if len(seen) > n:
            break
        y += SCROLL_STEP_PX
        if not await page.evaluate(JS_SCROLL_STEP, y):
            return False
        await page.wait_for_timeout(700)
    key = sorted(seen, key=lambda k: tuple(int(p) for p in k.split(":")))[n]
    if seen[key] != state["top"]:
        await page.evaluate(JS_SCROLL_STEP, seen[key])
        await page.wait_for_timeout(700)
    return bool(await page.evaluate(JS_MARK_KEY, key))


# P18-01: the first K video tiles of the gallery at scroll 0 (top-to-bottom, left-to-right), CSS px rects in the viewport
JS_VIDEO_RECTS = r"""(k) => [...document.querySelectorAll('flow-grid-tile-container')]
    .filter(c => c.querySelector('flow-video-tile')).map(c => c.getBoundingClientRect())
    .filter(r => r.width > 20 && r.height > 20 && r.bottom > 0 && r.top < innerHeight)
    .sort((a, b) => a.top - b.top || a.left - b.left).slice(0, k)
    .map(r => [r.x, r.y, r.width, r.height])"""

TILE_SIG_SIZE = (32, 18)   # grey thumbnail signature (w, h)
TILE_SAME_MAX = 6.0        # mean abs grey diff: a re-issued thumbnail (same frame, new token) scores ~0-3
WAIT_MIN_S = 45            # Omni Flash 360p clips took 80-140 s on film05; never bind before this
WAIT_POLL_S = 10
VANISHED_AFTER_S = 600     # flow_reconcile.SETTLE_S: no clip this long after the submit -> the job vanished
MIN_SCAN = 6               # flow_reconcile.MIN_SCAN: ... and only after this many newest detail pages were read


def tile_signatures(png: bytes, rects: list, dpr: float) -> list:
    """Grey signatures of the tiles at `rects` (CSS px) in a viewport screenshot (device px = CSS px * dpr)."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    h, w = img.shape[:2]
    sigs = []
    for x, y, rw, rh in rects:
        x0, y0 = max(0, int(x * dpr)), max(0, int(y * dpr))
        x1, y1 = min(w, int((x + rw) * dpr)), min(h, int((y + rh) * dpr))
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        sigs.append(cv2.resize(img[y0:y1, x0:x1], TILE_SIG_SIZE, interpolation=cv2.INTER_AREA).astype(float))
    return sigs


def new_tiles(baseline: list, current: list, tol: float = TILE_SAME_MAX) -> int:
    """How many current tiles match no baseline tile by pixels (P18-01: a re-issued thumbnail keeps its pixels but gets
    a new token; film05 SC01_g1/SC01_g2/SC05_g1 ended the token wait at 38-59 s on such tiles)."""
    return sum(1 for c in current if not any(float(abs(c - b).mean()) <= tol for b in baseline))


def wait_verdict(elapsed: float, timeout: float, running: bool, failed_new: bool, fresh: int) -> str:
    """One step of the video wait: FAILED (a new failed tile), BIND (a tile with new pixels, no job running, at least
    WAIT_MIN_S in; or the timeout) or WAIT. No early BLOCKED: Omni Flash shows no pending signal, so a quiet page
    is not a block (a refused prompt stays in the composer: SEND_FAILED)."""
    if failed_new and not running:  # a failed tile while a job still renders may be another job's (Codex 2026-11-09)
        return "FAILED"
    if elapsed >= timeout:
        return "BIND"
    if running:
        return "WAIT"
    return "BIND" if fresh and elapsed >= WAIT_MIN_S else "WAIT"


async def gallery_signatures(page, k: int = 8) -> list:
    """Pixel signatures of the first k video tiles (gallery at scroll 0, mouse parked off the grid)."""
    await page.evaluate(JS_TOP)
    await page.mouse.move(2, 2)
    await page.wait_for_timeout(800)
    rects = await page.evaluate(JS_VIDEO_RECTS, k)
    if not rects:
        return []
    dpr = await page.evaluate("window.devicePixelRatio") or 1.0
    png = await viewport_png(page)
    return tile_signatures(png, rects, float(dpr)) if png else []


async def viewport_png(page, timeout_s: float = 15.0) -> bytes | None:
    """A viewport screenshot (JPEG bytes) over CDP, or None. P18-06 (film05 SC02_g2 v3): `page.screenshot` waited 30 s for fonts on
    the GPM Flow tab and the exception ended the send; pixels only steer the wait, so a missing shot never fails one."""
    import base64
    try:
        cdp = await page.context.new_cdp_session(page)
        try:
            # JPEG: on the GPM Flow tab a PNG capture hung for 20 s while JPEG returned in ~1 s (2026-11-09)
            shot = await asyncio.wait_for(cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 85}),
                                          timeout_s)
        finally:
            await cdp.detach()
        return base64.b64decode(shot["data"])
    except Exception:  # noqa: BLE001 - no pixels: every tile reads as new and reconcile_bind decides alone
        return None


async def flow_failed(page, failed_before: int, wait_s: float) -> bool:
    """True once the gallery shows one more "Không thành công" tile than before the send (polled up to wait_s)."""
    end = time.time() + wait_s
    while True:
        try:
            if (await page.evaluate(JS_JOB_STATE))["failed"] > failed_before:
                return True
        except Exception:  # noqa: BLE001 - page navigating; try again
            pass
        if time.time() >= end:
            return False
        await page.wait_for_timeout(3000)


async def read_nth_detail(page, n: int, home: str) -> dict | None:
    """Open the n-th video tile (gallery at scroll 0), read its detail page
    (URL has the media id, body has the prompt), come back to the gallery."""
    await page.evaluate(JS_TOP)
    await page.wait_for_timeout(500)
    if not await mark_nth_video(page, n):
        return None
    await page.locator("[data-vp-n] flow-video-tile").first.click(timeout=8000)
    await page.wait_for_timeout(3500)
    out = {"url": page.url, "text": await page.evaluate("document.body.innerText")}
    await page.goto(home, timeout=45000)
    await page.wait_for_timeout(4000)
    await page.evaluate(JS_TOP)
    return out


async def front_snapshot(page, home: str, scan: int = 6) -> dict:
    """Before the send: how many videos exist, which media id is in front and the media ids of the newest `scan`
    videos (P17-05, Codex review: reconcile_bind must never bind a clip that existed before this send)."""
    # P18-01: no video_count here (film05: 37->30, 32->41 on an unchanged gallery); read until a tile is missing
    ids: list[str] = []
    front = None
    for i in range(scan):
        d = await read_nth_detail(page, i, home)
        if d is None:
            break
        mid = fb.media_id_from_url(d["url"])
        if i == 0:
            front = mid
        if mid:
            ids.append(mid)
    return {"front_id": front, "before_ids": ids, "signatures": await gallery_signatures(page)}


# the newest video tile's text: a job still rendering shows its progress (live SC05_g1 v4, 8 s after the submit:
# "play_circle 0% The given image is the first frame..."; a finished clip shows no percentage)
JS_FRONT_TILE_TEXT = r"""() => { const cs = [...document.querySelectorAll('flow-grid-tile-container')]
    .filter(c => c.querySelector('flow-video-tile'))
    .map(c => { const r = c.getBoundingClientRect(); return [r.top, r.left, c] })
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    return cs.length ? (cs[0][2].innerText || '').slice(0, 120) : null }"""
RENDERING_TILE_RE = re.compile(r"(?m)^\s*\d{1,2}%\s*$|\b\d{1,2}%")


STRAY_RECHECKS = 4          # P19-02: re-reads of a new front tile that shows no percentage yet
STRAY_RECHECK_MS = 4000


async def _starts_rendering(page, home: str, mid: str) -> bool:
    """P19-02: a job Flow has only just queued shows no percentage yet (film06, 5 of 17 sends: the front tile read
    "play_circle The given image is the first frame..." 8 s after the submit, and that same media id was the clip
    bound later), so "no percentage" alone does not mean finished. A finished clip never shows a percentage again,
    so re-read the front tile a few times: if it starts rendering and is still the same media id, it is this send's."""
    for _ in range(STRAY_RECHECKS):
        await page.wait_for_timeout(STRAY_RECHECK_MS)
        await page.evaluate(JS_TOP)
        if RENDERING_TILE_RE.search(await page.evaluate(JS_FRONT_TILE_TEXT) or ""):
            d = await read_nth_detail(page, 0, home)
            return bool(d) and fb.media_id_from_url(d["url"]) == mid
    return False


async def submit_tile(page, home: str, before_ids: list[str], known: set[str]) -> dict:
    """P18-07: this send's own tile, read right after the submit. Flow puts a new job first, so the newest video tile
    is ours when its media id existed neither before the send (`before_ids`) nor as a registered take; its media id
    and pixels are the send's identity. Anything else (an old clip still in front, no tile yet) leaves the identity
    unknown and the bind falls back to the prompt match. Only a tile still rendering (a progress percentage; a new
    tile showing none is read again a few times, P19-02) is taken: a new tile that is already a finished clip 8 s
    after the submit cannot be this send's (Omni Flash takes 45 s+); it is an earlier job that finished meanwhile.
    film05 SC02_g2 v4: a pixel check before the submit fired on every send (the start-frame upload changes the
    gallery), so finished-or-not is read after the submit instead."""
    await page.evaluate(JS_TOP)
    front_text = await page.evaluate(JS_FRONT_TILE_TEXT)
    rendering = bool(RENDERING_TILE_RE.search(front_text or ""))
    d = await read_nth_detail(page, 0, home)
    mid = fb.media_id_from_url(d["url"]) if d else None
    sigs = await gallery_signatures(page, k=1)
    own = {"media_id": None, "pixels": [round(float(sigs[0].mean()), 1)] if sigs else [],
           "front_text": " ".join((front_text or "").split())[:60]}
    if not mid:
        own["why"] = "NO_TILE"
    elif mid in before_ids or fb.is_known(mid, known):
        own["why"] = "OLD_TILE_IN_FRONT"
    elif not rendering and not await _starts_rendering(page, home, mid):
        # a new tile still showing no percentage after the re-reads is a finished clip: not this send's job
        own.update(why="STRAY_IN_FRONT", stray_tail=mid[-8:])
    else:
        own.update(media_id=mid, failed_at_submit=has_failed_text(d.get("text")))
    return own


def own_tile_only(res: dict, details: list[dict], own_id: str, prompt: str) -> dict:
    """P18-07: with the send's own media id known, only that tile binds; any other unregistered clip holding the
    prompt is a stray (an earlier unbound job of the same shot finishing late) and is reported, never bound."""
    ids = [fb.media_id_from_url((d or {}).get("url", "")) for d in details]
    strays = [m for m in (res.get("media_ids") or [res.get("media_id")]) if m and m != own_id]
    own_text = (details[ids.index(own_id)] or {}).get("text", "") if own_id in ids else ""
    if has_failed_text(own_text):
        return {"result": "NOT_IN_GALLERY", "why": "own tile failed", "strays": strays}
    if own_id in ids and fb.prompt_on_page(prompt, own_text):
        return {"result": "BOUND", "media_id": own_id, "index": ids.index(own_id), "strays": strays}
    return {"result": "NOT_IN_GALLERY", "why": "own tile not among the scanned clips", "strays": strays}


def own_tile_state(details: list[dict], own_id: str) -> str:
    """FAILED (own tile shows the failure), OK (own tile present, not failed) or MISSING."""
    for d in details:
        if fb.media_id_from_url((d or {}).get("url", "")) == own_id:
            return "FAILED" if has_failed_text((d or {}).get("text")) else "OK"
    return "MISSING"


async def reconcile_bind(page, ctx, prompt: str, out: Path, rec: dict, deadline: float, failed_before: int,
                         before_ids: list[str], scan: int = 6, own_id: str | None = None,
                         seen: list | None = None) -> bool:
    """P17-05: when the detail bind fails, bind like flow_reconcile does, inside the send: the newest `scan` video tiles
    are read (detail page: media id + prompt) until exactly one clip holds the whole prompt that is neither a
    registered take nor one of `before_ids` (videos that existed before this send), polled every 20 s until `deadline`
    or a new failed tile. Right before the download the tile at that index is read again and must still be that clip.
    film05: 5 of 13 sends needed flow_reconcile after the send. Returns True when it set rec["result"] (PASSED or the
    download failure); any error is recorded and returns False, so the paid send's record is still written."""
    import flow_reconcile as fr   # local: flow_reconcile imports this module
    tries, retries, res = 0, 0, {}
    try:
        known = fr.known_ids(out.parent, out.parent, frozenset({out.stem})) | set(before_ids)
        while True:
            tries += 1
            details = await fr.scan_gallery(page, scan)
            if seen is not None:
                seen[:] = details
            res = fb.reconcile(prompt, details, known)
            if own_id:
                res = own_tile_only(res, details, own_id, prompt)
                for m in res.get("strays", []):
                    tails = rec.setdefault("stray_media_tails", [])
                    if m[-8:] not in tails:
                        tails.append(m[-8:])
            if res["result"] == "BOUND":
                again = await read_nth_detail(page, res["index"], page.url)
                if again and fb.media_id_from_url(again["url"]) == res["media_id"]:
                    failed = await fr.download_nth(page, ctx, res["index"], out, media_id=res["media_id"], prompt=prompt)
                    rec["reconcile_bind"] = {"tries": tries, "media_id_tail": res["media_id"][-8:],
                                             "download": failed or "SAVED", "download_retries": retries}
                    if failed and time.time() < deadline:
                        # P18-01 (film05 SC02_g2 v1, SC03_g2): the bound clip's tile can still be rendering (no
                        # <video> under it yet); its media id is known, so poll again instead of ending the send
                        retries += 1
                        await page.wait_for_timeout(20000)
                        continue
                    if failed:
                        rec["result"] = failed
                        return True
                    data = out.read_bytes()
                    rec.update(result="PASSED", binding="RECONCILE_PROMPT_MATCH", media_id=res["media_id"], media_id_tail=res["media_id"][-8:],
                               file=out.name, sha256=_sha(data), bytes=len(data), duration_s=probe_duration(out))
                    return True
                res = {"result": "MOVED", "why": "the gallery moved before the download"}
            # P18-07: with the own tile known only its own failure ends the poll; a page-wide count can be a stray's
            failed_now = (own_tile_state(details, own_id) == "FAILED" if own_id else
                          (await page.evaluate(JS_JOB_STATE))["failed"] > failed_before)
            if time.time() >= deadline or failed_now:
                rec["reconcile_bind"] = {"tries": tries, "result": res["result"], "scanned": len(details)}
                return False
            await page.wait_for_timeout(20000)
    except Exception as e:  # noqa: BLE001 - never lose the record of a paid send
        rec["reconcile_bind"] = {"tries": tries, "error": f"{type(e).__name__}: {str(e)[:160]}"}
        return False


async def _video_wait_and_bind(page, ctx, args, prompt: str, out: Path, rec: dict, pre: dict, t0: float,
                               failed_before: int) -> dict:
    """P18-01: wait for and bind a video send by identity only -- never by token, title or video count.

    Wait: every WAIT_POLL_S the first video tiles are compared by pixels with the ones before the send (a re-issued
    thumbnail keeps its pixels); see `wait_verdict`. Bind: `reconcile_bind` (detail page media id + whole prompt, not
    a registered take, not a clip that existed before the send), polled until the send timeout. film05: flow_send
    bound 5/13 sends itself because the token wait ended at 38-59 s and `video_count` read 37->30, 32->41."""
    wait = {"polls": 0, "fresh_max": 0}
    rec["wait"] = wait
    own_id = ((pre or {}).get("own") or {}).get("media_id")
    seen: list = []
    verdict = await _wait_for_verdict(page, args, pre, t0, failed_before, wait)
    # a FAILED page still gets one bind scan: the failed tile is page-wide (Codex review 2026-11-09). P18-07: with the
    # own tile known, a page-wide failed tile proves nothing; the bind polls on until the own tile binds or fails
    deadline = t0 + args.timeout if verdict == "BIND" or own_id else 0.0
    if await reconcile_bind(page, ctx, prompt, out, rec, deadline, failed_before, pre.get("before_ids", []),
                            own_id=own_id, seen=seen):
        rec["elapsed_s"] = round(time.time() - t0)
        if verdict == "FAILED":
            rec["stray_failures"] = 1   # the failed tile was another job's: this send's own clip bound
        return rec
    rec["elapsed_s"] = round(time.time() - t0)
    if wait.get("running"):
        # Codex 2026-11-09: a job still rendering at the deadline may yet deliver this clip; a provider-failure label
        # here would auto-resend and pay twice, so it stays an unbound charged send for P17-07 to settle later
        rec["result"], rec["job_running"] = "UNBOUND", True
        return rec
    if own_id:
        # P18-07: with the own tile known, only that tile can prove a provider failure
        state = own_tile_state(seen, own_id)
        rec["own_tile"] = state
        if state == "FAILED":
            rec["result"] = "FLOW_FAILED"
            return rec
        if verdict == "FAILED":
            rec["stray_failures"] = 1
        if state == "OK":   # own job still there, no clip yet: never a vanished job
            rec["result"] = "UNBOUND"
            return rec
    elif verdict == "FAILED" or await flow_failed(page, failed_before, 30):
        rec["result"] = "FLOW_FAILED"
        return rec
    rb = rec.get("reconcile_bind") or {}
    last = rb.get("result")
    if (verdict == "BIND" and rec["elapsed_s"] >= VANISHED_AFTER_S and last == "NOT_IN_GALLERY"
            and rb.get("scanned", 0) >= MIN_SCAN):
        # P18-03 (film05 SC02_g2 12:09, SC04_g1 13:23): the job vanished -- no clip holds the prompt among the newest
        # MIN_SCAN videos 10 min after the submit; a provider failure, proven inside the send (as P17-07 does later)
        rec["result"], rec["provider_no_clip"] = "FLOW_FAILED_NO_CLIP", True
        return rec
    rec["result"] = ("AMBIGUOUS" if last == "AMBIGUOUS" else
                     "TIMEOUT" if not wait["fresh_max"] and verdict == "BIND" else "UNBOUND")
    tail = await page.evaluate("document.body.innerText.slice(0, 1500)")
    rec["page_hint"] = [ln for ln in tail.splitlines()
                        if re.search(r"(?i)không|lỗi|policy|chính sách|thất bại|error", ln)][:5]
    return rec


async def _wait_for_verdict(page, args, pre: dict, t0: float, failed_before: int, wait: dict) -> str:
    """Poll the gallery every WAIT_POLL_S until `wait_verdict` says FAILED or BIND (see there)."""
    verdict = "WAIT"
    while verdict == "WAIT":
        await page.wait_for_timeout(WAIT_POLL_S * 1000)
        wait["polls"] += 1
        try:
            job = await page.evaluate(JS_JOB_STATE)
            fresh = new_tiles(pre.get("signatures") or [], await gallery_signatures(page))
        except Exception:  # noqa: BLE001 - page navigating; poll again
            job, fresh = {"running": True, "failed": failed_before}, 0
        wait["fresh_max"] = max(wait["fresh_max"], fresh)
        wait["running"] = bool(job["running"])
        verdict = wait_verdict(time.time() - t0, args.timeout, job["running"], job["failed"] > failed_before, fresh)
    wait["verdict"], wait["at_s"] = verdict, round(time.time() - t0)
    return verdict


def probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True,
            timeout=60).stdout.strip()
        return float(out)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


# composer settings (model + clip length): the chip is the button whose text has "Video" and "giây"
SETTINGS_CHIP_RE = re.compile(r"Video[\s\S]*(?:giây|\d+s\b)")   # vi "… 6 giây", en "Video · 360p · 6s"
# image mode shows another chip ("Nano Banana ... crop_16_9 x1"): any composer chip carries the aspect icon and the count
SETTINGS_CHIP_ANY_RE = re.compile(r"(?:Video|Hình ảnh|Image|Nano Banana)[\s\S]*crop_\d+_\d+[\s\S]*x\d")
SETTINGS_CHIP_ATTEMPTS = 3   # bounded retries for "settings chip not found" before the send is refused (0 credits)
MODEL_BUTTON_RE = re.compile(r"Omni|Veo")
DURATION_RE = re.compile(r"(?:Độ dài|Length)\s*(\d+)\s*(?:giây|Sec)")
COST_RE = re.compile(r"(?:tốn|will use)\s*(\d+)\s*(?:tín dụng|credits?)")
MIN_DURATION_S, MAX_DURATION_S = 3, 15   # the slider runs 3..15 s in 1 s steps; Home = 3 s

JS_OPTION_XY = r"""(name) => { const vis = e => { const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' };
    const hits = [...document.querySelectorAll('body *')].filter(e => vis(e)
        && !(e.innerText || '').includes('arrow_drop_down')
        && (e.innerText || '').trim().startsWith(name));
    if (!hits.length) return null;
    hits.sort((a, b) => a.getBoundingClientRect().width * a.getBoundingClientRect().height
        - b.getBoundingClientRect().width * b.getBoundingClientRect().height);
    const r = hits[0].getBoundingClientRect();
    return [r.x + r.width / 2, r.y + r.height / 2] }"""


def parse_duration_s(text: str) -> int | None:
    """Clip length shown in the composer settings ("Độ dài 8 giây"), or None."""
    m = DURATION_RE.search(text or "")
    return int(m.group(1)) if m else None


def parse_cost(text: str) -> int | None:
    """Credits the settings panel says the send costs ("tốn 8 tín dụng"), or None."""
    m = COST_RE.search(text or "")
    return int(m.group(1)) if m else None


def model_label(button_text: str) -> str:
    """The model name on the dropdown button: icon ligature and line breaks removed."""
    return " ".join((button_text or "").replace("arrow_drop_down", " ").split())


def model_matches(button_text: str, name: str) -> bool:
    return model_label(button_text).startswith(name)


def slider_presses(seconds: int) -> int:
    """ArrowRight presses after Home (3 s) that land the duration slider on `seconds`."""
    if not MIN_DURATION_S <= seconds <= MAX_DURATION_S:
        raise ValueError(f"duration {seconds} s outside {MIN_DURATION_S}-{MAX_DURATION_S}")
    return seconds - MIN_DURATION_S


async def _find_settings_chip(page, attempts: int = SETTINGS_CHIP_ATTEMPTS):
    """The composer settings chip (video chip, or the image-mode chip), retried a bounded number of times; None if absent.

    film07 pilot: right after an image-mode still the chip was briefly missing / not the video chip and the send died
    SETTINGS_NOT_SET. Each retry presses Escape (closes a stray popup) and waits for the composer to settle."""
    for attempt in range(max(1, attempts)):
        for pattern in (SETTINGS_CHIP_RE, SETTINGS_CHIP_ANY_RE):
            chip = page.locator("button").filter(has_text=pattern).first
            if await chip.count():
                return chip
        if attempt + 1 < attempts:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1500)
    return None


RADIO_ALIASES = {"Khung hình": ("Khung hình", "Frames"), "Thành phần": ("Thành phần", "Ingredients"),
                 "Hình ảnh": ("Hình ảnh", "Image")}   # Vietnamese label -> its wording in every UI language we drive


def _radio_re(label: str):
    # has_text matches textContent, where the icon ligature runs into the label ("videocamVideo"): case-sensitive substring
    return re.compile("|".join(re.escape(x) for x in RADIO_ALIASES.get(label, (label,))))


async def _ensure_radio(page, label: str, what: str) -> str | None:
    """Select the settings-menu radio whose text ends in `label` and verify it is checked. None = fine."""
    radio = page.locator("button[role=radio]").filter(has_text=_radio_re(label)).first
    if not await radio.count():
        return f"SETTINGS_NOT_SET {what} option {label!r} not found"
    if await radio.get_attribute("aria-checked") != "true":
        await radio.click()
        await page.wait_for_timeout(800)
        radio = page.locator("button[role=radio]").filter(has_text=_radio_re(label)).first
        if not await radio.count() or await radio.get_attribute("aria-checked") != "true":
            return f"SETTINGS_NOT_SET {what} did not switch to {label!r}"
    return None


async def _set_composer_settings(page, model: str, duration: int | None, rec: dict,
                                 expected_credits: float | None = None, mode: str | None = None,
                                 resolution: str | None = None, submode: str | None = None) -> str | None:
    """Set mode / model / resolution / clip length in the composer settings menu and verify each. None = fine, else a result string.

    mode="Video" and resolution="360p" are forced before every video send: an image-mode still leaves the composer in
    image mode (film07 pilot SETTINGS_NOT_SET). submode="Khung hình" is forced for start-frame sends: after an image-mode
    detour the video composer comes back without the frame slots (film07 SC03_g01_t1 START_NOT_FOUND upload)."""
    chip = await _find_settings_chip(page)
    if chip is None:
        return "SETTINGS_NOT_SET settings chip not found"
    await chip.click()
    await page.wait_for_timeout(800)
    if mode:
        failed = await _ensure_radio(page, mode, "mode")
        if failed:
            return failed
        rec["mode_set"] = mode
    if submode:
        failed = await _ensure_radio(page, submode, "video sub-mode")
        if failed:
            return failed
        rec["submode_set"] = submode
    if model:
        dropdown = page.locator("button").filter(has_text="arrow_drop_down").filter(has_text=MODEL_BUTTON_RE).first
        if not await dropdown.count():
            return "SETTINGS_NOT_SET model dropdown not found"
        if not model_matches(await dropdown.inner_text(), model):
            await dropdown.click()
            await page.wait_for_timeout(600)
            xy = await page.evaluate(JS_OPTION_XY, model)
            if xy is None:
                return f"SETTINGS_NOT_SET model option {model!r} not found"
            await page.mouse.click(*xy)
            await page.wait_for_timeout(800)
        shown = model_label(await dropdown.inner_text())
        rec["model_set"] = shown
        if not shown.startswith(model):
            return f"SETTINGS_NOT_SET model shows {shown!r}, wanted {model!r}"
    if resolution:   # after the model: the resolution options depend on it
        failed = await _ensure_radio(page, resolution, "resolution")
        if failed:
            return failed
        rec["resolution_set"] = resolution
    if duration is not None:
        try:
            presses = slider_presses(duration)
        except ValueError as e:
            return f"SETTINGS_NOT_SET {e}"
        slider = page.locator("input[type=range], [role=slider]").first  # Flow renders a range input
        if not await slider.count():
            return "SETTINGS_NOT_SET duration slider not found"
        await slider.focus()
        await page.keyboard.press("Home")
        for _ in range(presses):
            await page.keyboard.press("ArrowRight")
        await page.wait_for_timeout(500)
    body = await page.evaluate("() => document.body.innerText")
    shown_s, cost = parse_duration_s(body), parse_cost(body)
    if duration is not None:
        rec["duration_set"] = shown_s
    if cost is not None:
        rec["flow_credits"] = cost
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)
    if mode or resolution or duration is not None:
        chip = await _find_settings_chip(page) or chip
        chip_text = await chip.inner_text()
        if mode and mode not in chip_text:
            return f"SETTINGS_NOT_SET chip does not show {mode}"
        if resolution and resolution not in chip_text:
            return f"SETTINGS_NOT_SET chip does not show {resolution}"
    if duration is not None:
        if shown_s != duration:
            return f"SETTINGS_NOT_SET duration shows {shown_s}, wanted {duration}"
        if f"{duration} giây" not in chip_text and not re.search(rf"\b{duration}s\b", chip_text):
            return f"SETTINGS_NOT_SET chip does not show {duration} giây"
    if expected_credits is not None and cost != expected_credits:
        return f"PRE_SUBMIT_ERROR CREDIT_QUOTE_MISMATCH shown={cost} reserved={expected_credits:g}"
    return None


async def _upload_in_picker(page, f: Path) -> bool:
    """Upload one local file through the open frame picker's "Tải nội dung" button; False when no picker is open."""
    btn = page.locator("text=/Tải nội dung|Upload media/ >> visible=true")
    if not await btn.count():
        return False
    async with page.expect_file_chooser(timeout=15000) as fc:
        await btn.last.click()
    await (await fc.value).set_files([str(f)])
    await page.wait_for_timeout(15000)
    return True


async def _upload(page, f) -> None:
    """Upload one local file through the composer "+" > "Tải nội dung" file chooser."""
    async with page.expect_file_chooser(timeout=15000) as fc:
        await page.mouse.click(*await _plus_xy(page))
        await page.wait_for_timeout(1200)
        await page.get_by_text(re.compile(r"Tải nội dung|Upload media")).last.click()
    await (await fc.value).set_files([f])
    await page.wait_for_timeout(15000)
    await page.keyboard.press("Escape")


async def run(args, before_submit=None) -> dict:
    from patchright.async_api import async_playwright
    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    out = Path(args.out)
    rec = {"prompt_file": str(args.prompt_file), "prompt_sha256": _sha(prompt),
           "prompt_words": len(prompt.split()), "attach": args.attach,
           "start": args.start,
           **({"end": args.end} if args.end else {}),
           "upload": [Path(u).name for u in args.upload],
           "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    rec.update(submission_phase="PREPARING", result="PREPARING")
    checkpoint(out, rec)
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(CDP, timeout=30000)
        ctx = browser.contexts[0]
        page = next((p for p in ctx.pages if "flow.google" in p.url), None)
        if page is None:   # 2026-11-09 SC03_g1 t1: no Flow tab crashed here and the receipt counted as a send
            rec["result"] = "PRE_SUBMIT_ERROR NO_FLOW_TAB"
            return rec
        rec["project"] = page.url.rsplit("/", 1)[-1][:36]
        # the click coordinates above are calibrated for 1280x720 CSS px; a GPM window of another size shifts them
        await page.set_viewport_size({"width": 1280, "height": 720})
        await page.keyboard.press("Escape")
        await page.evaluate(JS_TOP)
        await page.wait_for_timeout(1500)
        baseline = set(await page.evaluate(JS_TOKENS))
        failed_before = (await page.evaluate(JS_JOB_STATE))["failed"]
        # P12-01: the video count and the front media id BEFORE the send; a lazy
        # thumbnail can make an old clip look new by token, a media id never changes
        try:
            pre = None if args.image else await front_snapshot(page, page.url)
        except Exception as e:  # noqa: BLE001 - P18-06: before the prompt is typed nothing is sent (0 credits)
            rec["result"] = f"PRE_SUBMIT_ERROR {type(e).__name__}"
            rec["error"] = str(e).splitlines()[0][:200] if str(e) else ""
            return rec
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

        try:   # nothing is submitted before the prompt Enter: any failure here costs no credits
            for f in args.upload:
                await _upload(page, f)
            # frame stills are uploaded inside their slot picker (_fill_frame_slot), each then the newest picker item
            uploaded = [f for f in (args.start_file, args.end_file) if f] if args.upload_frames else []
            rec["frames_uploaded"] = [Path(f).name for f in uploaded]
            if args.model or args.duration is not None:   # a mode change can clear frame slots
                # every video send forces video mode + resolution: an image-mode still leaves the composer in image mode
                video = not args.image and bool(args.model)
                failed = await _set_composer_settings(page, args.model, args.duration, rec,
                                                      mode="Video" if video else None,
                                                      resolution=args.resolution if video else None,
                                                      submode="Khung hình" if video and (args.start or args.start_file) else None)
                if failed:
                    rec["result"] = failed
                    return rec
            for which, tok, still in (("start", args.start, args.start_file), ("end", args.end, args.end_file)):
                if tok or (args.upload_frames and still):   # "Khung hình" mode: image into the start / end frame slot (start first)
                    failed = await _fill_frame_slot(page, which, tok, Path(still) if still else None, rec,
                                                    newest_k=1 if args.upload_frames else None)
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
                add = page.get_by_text(ADD_TO_PROMPT_RE)
                if await add.count():   # image mode attaches on the click itself
                    await add.click()
                await page.wait_for_timeout(1500)
            if args.expected_credits is not None:  # frames/ingredients may change the final quote
                failed = await _set_composer_settings(page, "", None, rec, args.expected_credits)
                if failed:
                    rec["result"] = failed
                    return rec
        except Exception as e:  # noqa: BLE001 - recorded as a pre-submit result, not a lost send
            rec["result"] = f"PRE_SUBMIT_ERROR {type(e).__name__}"
            rec["error"] = str(e).splitlines()[0][:200] if str(e) else ""
            return rec

        box = page.locator("textarea, [contenteditable='true']").first
        # Codex 2026-11-09: re-read the failed-tile count right before the submit, so a job that failed during the
        # snapshot and composer setup is not taken for this send's failure
        failed_before = (await page.evaluate(JS_JOB_STATE))["failed"]
        await box.click()
        await box.fill(prompt)
        await page.wait_for_timeout(500)
        if before_submit is not None:
            before_submit(rec)
        # submitting_at: a death between Enter and the SUBMITTED checkpoint still leaves a send time to settle from
        rec.update(before_ids=(pre or {}).get("before_ids", []), result="PENDING", submission_phase="SUBMITTING",
                   submitting_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        checkpoint(out, rec)
        await page.keyboard.press("Enter")
        t0 = time.time()
        await page.wait_for_timeout(8000)
        left = await box.evaluate("e => (e.value ?? e.innerText) || ''")
        if prompt[:40] in left:
            rec["result"] = "SUBMIT_UNCONFIRMED"
            return rec

        if not args.image:
            try:
                import flow_reconcile as fr   # local: flow_reconcile imports this module
                known = fr.known_ids(out.parent, out.parent, frozenset({out.stem}))
                pre["own"] = await submit_tile(page, page.url, pre.get("before_ids", []), known)
            except Exception as e:  # noqa: BLE001 - the identity only narrows the bind; the send goes on without it
                pre["own"] = {"media_id": None, "why": f"ERROR {type(e).__name__}"}
            own = pre["own"]
            rec["own_tile_at_submit"] = {k: (v[-8:] if k == "media_id" and v else v) for k, v in own.items()}
            rec["before_ids"] = pre.get("before_ids", [])
            rec.update(result="PENDING", submission_phase="SUBMITTED", submitted_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
            checkpoint(out, rec)
            return await _video_wait_and_bind(page, ctx, args, prompt, out, rec, pre, t0, failed_before)

        probe = prompt[:30]
        new: set[str] = set()
        failed_seen = False
        while time.time() - t0 < args.timeout:
            await page.wait_for_timeout(10000)
            await page.evaluate(JS_TOP)
            new = set(await page.evaluate(JS_TOKENS)) - baseline
            pending = await page.evaluate(
                "(p) => document.body.innerText.includes(p)", probe)
            job = await page.evaluate(JS_JOB_STATE)
            if job["failed"] > failed_before:
                # a failed tile is page-wide: it may be an older job. Stop waiting, but only call this send
                # FLOW_FAILED when no new clip can be bound to its prompt (Codex review 2026-11-09)
                failed_seen = True
                break
            # film04: binding at 18 s while the new tile still read "47%" gave UNBOUND; wait for the job to end
            pending = pending or job["running"]
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
        if not new and failed_seen:
            rec["result"] = "FLOW_FAILED"
            return rec
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


def build_parser() -> argparse.ArgumentParser:
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
    ap.add_argument("--upload-frames", action="store_true",
                    help="upload --start-file / --end-file inside the send (start first) and pick them as the newest "
                         "picker items by pixels; --start / --end tokens are not needed")
    ap.add_argument("--model", default="",
                    help="composer model name (dropdown text must start with it), e.g. 'Omni 1.2 Flash'")
    ap.add_argument("--resolution", default="360p",
                    help="video resolution forced before a video send (film takes: 360p only)")
    ap.add_argument("--duration", type=int, default=None,
                    help="clip length in seconds (3-15), set on the settings slider")
    ap.add_argument("--expected-credits", type=float,
                    help="refuse before submit if the displayed credit quote differs from the reserved amount")
    ap.add_argument("--image", action="store_true",
                    help="composer is in image mode; save the output image")
    return ap


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.start and not args.upload_frames:
        ap.error("--start tok:TAIL is required unless --upload-frames is given")
    if args.upload_frames and not args.start_file:
        ap.error("--upload-frames needs --start-file")
    return args


def checkpoint(out: Path, record: dict) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from film_pipeline.production.runtime import atomic_json
    atomic_json(Path(out).with_suffix(".take.json"), record)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    rec = asyncio.run(run(args))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    checkpoint(out, rec)
    print(rec.get("result"), rec.get("binding", ""), rec.get("sha256", ""),
          f"{rec.get('elapsed_s', '?')}s")


if __name__ == "__main__":
    main()
