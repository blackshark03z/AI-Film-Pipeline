"""A young Flow project holds fewer than MIN_SCAN videos and only the first rows render at scroll 0.

film07 SC01_g05_t1 (2026-11-11): the failed job left no clip; the project had 4 videos, 3 rendered at scroll 0, so
reconcile read 3 pages, could never reach MIN_SCAN=6 and the send stayed pending forever (deadlock: no new videos
without a new send). An exhausted gallery is a complete scan; the n-th video must be reachable by scrolling.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/drama_flow_ui"))
import flow_reconcile as fr
import flow_send as fs

HOME = "https://flow.google.com/project/p"


def _page(i: int) -> dict:
    return {"url": f"{HOME}/edit/11111111-2222-3333-4444-{i:012d}", "text": "other full prompt"}


def test_exhausted_small_gallery_is_a_complete_negative_scan():
    four = [_page(i) for i in range(4)]
    assert not fr.complete_negative_scan(four, HOME)                      # unknown whether more videos exist
    assert fr.complete_negative_scan(four, HOME, exhausted=True)          # every video of the project was read
    assert not fr.complete_negative_scan([], HOME, exhausted=True)        # an empty read proves nothing
    assert not fr.complete_negative_scan([*four, four[0]], HOME, exhausted=True)   # duplicates still refused
    assert not fr.complete_negative_scan(four, HOME + "2", exhausted=True)         # wrong project still refused


def _key(row: int) -> str:
    return f"{round(row / 40)}:0"


class _Grid:
    """Fake virtualised gallery: video tiles sit at absolute rows; only rows near the viewport are rendered."""
    def __init__(self, rows, viewport=720, total=3000):
        self.rows, self.viewport, self.total, self.top, self.marked = rows, viewport, total, 0, None

    def rendered(self):
        return [r for r in self.rows if self.top - 400 <= r <= self.top + self.viewport]

    async def evaluate(self, script, *args):
        if script == fs.JS_TOP:
            self.top = 0
        elif script == fs.JS_MARK_NTH:
            vis = sorted(r for r in self.rendered() if self.top <= r <= self.top + self.viewport)
            if args[0] < len(vis):
                self.marked = vis[args[0]]
                return True
            return False
        elif script == fs.JS_VIDEO_KEYS:
            return {"top": self.top, "keys": [_key(r) for r in self.rendered()]}
        elif script == fs.JS_SCROLL_STEP:
            was, self.top = self.top, min(args[0], self.total - self.viewport)
            return self.top != was
        elif script == fs.JS_MARK_KEY:
            hits = [r for r in self.rendered() if _key(r) == args[0]]
            self.marked = hits[0] if hits else None
            return bool(hits)
        return None

    async def wait_for_timeout(self, ms):
        return None


def test_nth_video_below_the_first_rows_is_reachable_by_scrolling():
    grid = _Grid(rows=[76, 411, 747, 2047])
    page = SimpleNamespace(evaluate=grid.evaluate, wait_for_timeout=grid.wait_for_timeout)
    assert asyncio.run(fs.mark_nth_video(page, 3))
    assert grid.marked == 2047
    asyncio.run(grid.evaluate(fs.JS_TOP))   # read_nth_detail returns to the top before every read
    assert asyncio.run(fs.mark_nth_video(page, 0))
    assert grid.marked == 76


def test_past_the_last_video_the_gallery_is_exhausted():
    grid = _Grid(rows=[76, 411, 747, 2047])
    page = SimpleNamespace(evaluate=grid.evaluate, wait_for_timeout=grid.wait_for_timeout)
    assert not asyncio.run(fs.mark_nth_video(page, 4))


def test_short_scan_is_exhausted_only_when_a_reload_rescan_returns_the_same_ordered_ids():
    first = [_page(i) for i in range(4)]
    assert fr.exhaustion_confirmed(first, [_page(i) for i in range(4)])              # same ordered set: confirmed
    assert not fr.exhaustion_confirmed(first, [_page(i) for i in range(5)])          # grid was still loading: longer
    assert not fr.exhaustion_confirmed(first, [_page(i) for i in (1, 0, 2, 3)])      # order differs: not stable
    assert not fr.exhaustion_confirmed([], [])                                      # empty proves nothing
    assert not fr.exhaustion_confirmed(first, [])                                   # second read failed


def test_confirm_reloads_the_project_and_rescans_before_trusting_a_short_scan():
    calls = []

    class P:
        url = HOME
        async def goto(self, url, **kw): calls.append(("goto", url))
        async def wait_for_timeout(self, ms): calls.append(("wait", ms))

    async def scan(page, n):
        calls.append(("scan", n))
        return [_page(i) for i in range(5)]   # the grid had finished loading

    orig, fr.scan_gallery = fr.scan_gallery, scan
    try:
        first = [_page(i) for i in range(4)]
        assert asyncio.run(fr.confirm_exhausted(P(), first, 30, HOME)) is False   # rescan came back longer
        assert [c[0] for c in calls][:3] == ["goto", "wait", "scan"]

        async def same(page, n): return [_page(i) for i in range(4)]
        fr.scan_gallery = same
        assert asyncio.run(fr.confirm_exhausted(P(), first, 30, HOME)) is True
        assert asyncio.run(fr.confirm_exhausted(P(), [_page(i) for i in range(30)], 30, HOME)) is False   # not short
    finally:
        fr.scan_gallery = orig
