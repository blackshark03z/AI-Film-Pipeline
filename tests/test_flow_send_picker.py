"""The start-frame picker reopens at its last scroll position; the search must still see the top items."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "drama_flow_ui"))
import flow_send as fs  # noqa: E402


class _Mouse:
    def __init__(self, page):
        self.page = page

    async def move(self, *_):
        pass

    async def wheel(self, _dx, dy):
        step = 1 if dy > 0 else -1
        top = self.page.top + step * max(1, abs(dy) // 250)
        self.page.top = max(0, min(top, len(self.page.items) - self.page.window))


class _VirtualListPage:
    """Shows `window` items starting at `top`; each item is (key, x, y)."""

    def __init__(self, items, top, window=5):
        self.items, self.top, self.window = items, top, window
        self.mouse = _Mouse(self)

    async def wait_for_timeout(self, _ms):
        pass

    async def evaluate(self, js, *_):
        assert js is fs.JS_PICKER_THUMBS
        shown = self.items[self.top:self.top + self.window]
        return [[142, 100 + 48 * i, list(key.encode())] for i, key in enumerate(shown)]


def test_image_search_finds_the_newest_still_when_the_picker_opens_mid_list(monkeypatch):
    # film04 SC01_g1 t7: the approved still sat at the top, the picker opened scrolled down
    monkeypatch.setattr(fs, "slot_diff", lambda data, _still: 0.5 if data == b"still" else 40.0)
    items = ["still"] + [f"plate{i}" for i in range(20)]
    page = _VirtualListPage(items, top=12)
    xy = asyncio.run(fs._picker_find_image(page, Path("start.jpg"), fs.START_LIST_XY))
    assert xy == (142, 100)
