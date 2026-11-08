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


def test_image_search_takes_a_second_upload_of_the_same_still_but_refuses_a_close_sibling(monkeypatch):
    # film04 SC01_g2 t2/t3: the v2 start was uploaded twice (same bytes, both score 1.7); the search refused it
    scores = {"copy": 1.7, "sibling": 2.0}
    monkeypatch.setattr(fs, "slot_diff", lambda data, _still: scores.get(data.decode(), 40.0))
    page = _VirtualListPage(["copy", "plate", "copy", "plate2"], top=0)
    assert asyncio.run(fs._picker_find_image(page, Path("start.jpg"), fs.START_LIST_XY)) == (142, 100)
    page = _VirtualListPage(["copy", "sibling", "plate", "plate2"], top=0)
    assert asyncio.run(fs._picker_find_image(page, Path("start.jpg"), fs.START_LIST_XY, scrolls=0)) is None


# --- P13-05: start and end slots -------------------------------------------------------------------------------

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

import pytest  # noqa: E402

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to run the page scripts")


def _node(fn_src: str, arg, dom: str):
    """Run one page script against a stub DOM; returns its JSON result."""
    code = (f"{dom}\nconst fn = ({fn_src});\n"
            f"Promise.resolve(fn({json.dumps(arg)})).then(v => console.log(JSON.stringify(v)));")
    done = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(done.stdout)


_RECT = "const R = (x, y, w, h) => ({x, y, width: w, height: h, bottom: y + h});\n"


@needs_node
def test_slot_is_found_by_its_button_text():
    dom = _RECT + """globalThis.innerHeight = 655;
    const B = (t, r) => ({innerText: t, getBoundingClientRect: () => r});
    globalThis.document = {querySelectorAll: () => [B('Thêm', R(10, 10, 40, 40)), B('Bắt đầu', R(300, 500, 56, 56)),
        B('Kết thúc', R(398, 500, 56, 56)), B('Kết thúc', R(398, 900, 56, 56))]};"""
    assert _node(fs.JS_FRAME_SLOT, "Bắt đầu", dom) == [328, 528]
    assert _node(fs.JS_FRAME_SLOT, "Kết thúc", dom) == [426, 528]   # the copy below the viewport is not visible
    assert _node(fs.JS_FRAME_SLOT, "Nothing", dom) is None


@needs_node
def test_slot_bytes_come_from_the_nearest_image_within_60px():
    dom = _RECT + """const I = (src, r) => ({currentSrc: src, src, getBoundingClientRect: () => r});
    globalThis.document = {images: [I('start', R(300, 500, 56, 56)), I('end', R(398, 500, 56, 56)),
        I('zero', R(0, 0, 0, 0))]};
    globalThis.fetch = async (u) => ({arrayBuffer: async () => new TextEncoder().encode(u).buffer});"""
    as_text = lambda v: bytes(v).decode() if v else v  # noqa: E731
    assert as_text(_node(fs.JS_SLOT_BYTES, [426, 528], dom)) == "end"      # the end slot, not the first image near it
    assert as_text(_node(fs.JS_SLOT_BYTES, [328, 528], dom)) == "start"
    assert _node(fs.JS_SLOT_BYTES, [700, 528], dom) is None


class _Locator:
    async def count(self):
        return 0


class _SlotPage:
    """Composer with a start and an end slot; `texts` False = the slot labels are not in the page."""

    def __init__(self, texts=True, thumbs=((150, 100), (150, 148), (150, 196))):
        self.texts, self.thumbs, self.clicks = texts, list(thumbs), []
        self.mouse = self
        self.slot_asked = []

    async def click(self, x, y):
        self.clicks.append((x, y))

    async def wait_for_timeout(self, _ms):
        pass

    def get_by_text(self, *_a, **_k):
        return _Locator()

    async def evaluate(self, js, *args):
        if js is fs.JS_FRAME_SLOT:
            self.slot_asked.append(args[0])
            if not self.texts:
                return None
            return {"Bắt đầu": [330, 520], "Kết thúc": [428, 520]}[args[0]]
        if js is fs.JS_PICKER_CENTRES:
            return [list(t) for t in self.thumbs]
        if js is fs.JS_SLOT_BYTES:
            return list(b"slot")
        raise AssertionError(js[:40])


def _patch_picker(monkeypatch, seen):
    async def find(_page, tok, over, scrolls=16):
        seen.append((tok, over))
        return (150, 148)
    monkeypatch.setattr(fs, "_picker_find", find)
    monkeypatch.setattr(fs, "slot_diff", lambda data, _still: 0.2)


def test_slot_uses_found_coordinates_and_the_picker_median(monkeypatch):
    seen = []
    _patch_picker(monkeypatch, seen)
    page, rec = _SlotPage(), {}
    assert asyncio.run(fs._fill_frame_slot(page, "end", "tok:ENDTAIL", Path("end.png"), rec)) is None
    assert page.slot_asked == ["Kết thúc"]
    assert page.clicks[0] == (428, 520) and page.clicks[-1] == (150, 148)
    assert seen == [("ENDTAIL", (150, 148))]            # median of the visible thumbnails
    assert rec["end_found_by"] == "token_tail" and rec["end_slot_diff"] == 0.2


def test_slot_falls_back_to_fixed_coordinates(monkeypatch):
    seen = []
    _patch_picker(monkeypatch, seen)
    page = _SlotPage(texts=False, thumbs=())
    assert asyncio.run(fs._fill_frame_slot(page, "start", "tok:S", None, {})) is None
    assert page.clicks[0] == fs.START_XY and seen[0][1] == fs.START_LIST_XY
    page = _SlotPage(texts=False, thumbs=())
    assert asyncio.run(fs._fill_frame_slot(page, "end", "tok:E", None, {})) is None
    assert page.clicks[0] == (fs.START_XY[0] + 98, fs.START_XY[1])


def test_slot_failures_name_the_slot(monkeypatch):
    seen = []
    _patch_picker(monkeypatch, seen)
    monkeypatch.setattr(fs, "slot_diff", lambda data, _still: 40.0)
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "end", "tok:E", Path("e.png"), {})) == "END_NOT_SET tok:E"
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "start", "tok:S", Path("s.png"), {})) == "START_NOT_SET tok:S"

    async def nothing(*_a, **_k):
        return None
    monkeypatch.setattr(fs, "_picker_find", nothing)
    monkeypatch.setattr(fs, "_picker_find_image", nothing)
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "end", "tok:E", Path("e.png"), {})) == "END_NOT_FOUND tok:E"
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "start", "tok:S", None, {})) == "START_NOT_FOUND tok:S"


def test_end_slot_is_filled_after_the_start_slot():
    # run() needs a live browser: check the order of the two slots in its fill loop
    src = Path(fs.__file__).read_text(encoding="utf-8")
    loop = src[src.index("for which, tok, still in"):][:200]
    assert loop.index('("start", args.start') < loop.index('("end", args.end')


class _PlusPage:
    def __init__(self, xy):
        self.xy = xy

    async def evaluate(self, js, *_):
        assert js is fs.JS_PLUS
        return self.xy


def test_plus_is_found_in_the_dom_and_falls_back_to_fixed_coordinates():
    # 2026-11-08: the GPM window was 1397x655; the "+" sat at (417, 598), not PLUS_XY (358, 662)
    assert asyncio.run(fs._plus_xy(_PlusPage([417.3, 598.5]))) == (417.3, 598.5)
    assert asyncio.run(fs._plus_xy(_PlusPage(None))) == fs.PLUS_XY


def test_settings_text_parsers():
    body = "Veo\nĐộ dài 12 giây\nSố lượng 1\nSẽ tốn 14 tín dụng"
    assert fs.parse_duration_s(body) == 12
    assert fs.parse_cost(body) == 14
    assert fs.parse_duration_s("Độ dài  8  giây") == 8
    assert fs.parse_duration_s("no settings here") is None
    assert fs.parse_cost("") is None


def test_model_label_and_match():
    assert fs.model_label("Omni 1.2 Flash\narrow_drop_down") == "Omni 1.2 Flash"
    assert fs.model_matches("Omni 1.2 Flash\narrow_drop_down", "Omni 1.2 Flash")
    assert not fs.model_matches("Omni Flash arrow_drop_down", "Omni 1.2 Flash")
    assert not fs.model_matches("", "Omni 1.2 Flash")


def test_slider_presses_from_home():
    assert fs.slider_presses(3) == 0
    assert fs.slider_presses(8) == 5
    assert fs.slider_presses(15) == 12
    for bad in (2, 16):
        try:
            fs.slider_presses(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} accepted")
