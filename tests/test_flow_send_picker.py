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


def test_same_image_compares_pixels_not_only_bytes(tmp_path):
    # film04 SC02_g1 t1: the start reuses end_SC01_g1; Flow served the two uploads 2 bytes apart (119392 / 119394)
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    img = np.full((90, 160, 3), 60, np.uint8)
    img[20:60, 40:120] = 200
    a = cv2.imencode(".png", img)[1].tobytes()
    b = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1].tobytes() + b"\0\0"
    other = img.copy()
    other[20:60, 40:120] = 120
    assert fs.same_image(a, a) and fs.same_image(a, b)
    assert not fs.same_image(a, cv2.imencode(".png", other)[1].tobytes()) and not fs.same_image(a, b"junk")


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


def test_composer_quote_must_match_reserved_credits_before_submission():
    class Control:
        @property
        def first(self): return self
        def filter(self, **kwargs): return self
        async def count(self): return 1
        async def click(self): pass
        async def focus(self): pass
        async def press(self, key): pass
        async def inner_text(self): return "Omni 1.2 Flash / 6 giây"
    class Page:
        keyboard = Control()
        def __init__(self, cost): self.cost = cost
        def locator(self, selector): return Control()
        async def wait_for_timeout(self, ms): pass
        async def evaluate(self, script): return f"Độ dài 6 giây\n{self.cost}"
    for shown, allowed in [("Sẽ tốn 6 tín dụng", True), ("Sẽ tốn 7 tín dụng", False), ("", False)]:
        record = {}
        result = asyncio.run(fs._set_composer_settings(Page(shown), "", 6, record, expected_credits=6))
        assert (result is None) == allowed
        if not allowed:
            assert result.startswith("PRE_SUBMIT_ERROR CREDIT_QUOTE_MISMATCH")


def test_send_rechecks_quote_after_frames_and_never_submits_on_price_change(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    import patchright.async_api as pa
    page = SimpleNamespace(url="https://flow.google.com/project/owned", set_viewport_size=AsyncMock(),
                           keyboard=SimpleNamespace(press=AsyncMock()), wait_for_timeout=AsyncMock(), on=Mock())
    page.evaluate = AsyncMock(side_effect=lambda js: {"failed": 0} if js == fs.JS_JOB_STATE else [])
    browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[page])])
    pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=AsyncMock(return_value=browser)), stop=AsyncMock())
    monkeypatch.setattr(pa, "async_playwright", lambda: SimpleNamespace(start=AsyncMock(return_value=pw)))
    monkeypatch.setattr(fs, "front_snapshot", AsyncMock(return_value={"before_ids": []}))
    events = []
    async def frame(*args, **kwargs):
        events.append("frame")
    async def settings(page, model, duration, record, expected_credits=None):
        events.append("quote" if expected_credits is not None else "settings")
        if expected_credits is not None:
            assert events[-2] == "frame"
            return "PRE_SUBMIT_ERROR CREDIT_QUOTE_MISMATCH shown=7 reserved=6"
    monkeypatch.setattr(fs, "_fill_frame_slot", frame)
    monkeypatch.setattr(fs, "_set_composer_settings", settings)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("original fictional dialogue", encoding="utf-8")
    args = fs.parse_args([str(prompt), str(tmp_path / "out.mp4"), "--start", "tok:owned",
                          "--model", "Omni 1.2 Flash", "--duration", "6", "--expected-credits", "6"])
    result = asyncio.run(fs.run(args))
    assert result["result"].startswith("PRE_SUBMIT_ERROR CREDIT_QUOTE_MISMATCH")
    assert events == ["settings", "frame", "quote"]
    assert all(call.args != ("Enter",) for call in page.keyboard.press.call_args_list)


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


# --- P16-08: frames uploaded inside the send --------------------------------------------------------------------

def _scores(monkeypatch, table):
    monkeypatch.setattr(fs, "slot_diff", lambda data, _still: table.get(data.decode(), 40.0))


def test_newest_one_is_found_at_the_top_even_when_the_picker_opened_mid_list(monkeypatch):
    _scores(monkeypatch, {"start": 0.5})
    page = _VirtualListPage(["start"] + [f"plate{i}" for i in range(20)], top=12)
    assert asyncio.run(fs._picker_newest(page, Path("s.png"), fs.START_LIST_XY, 1)) == (142, 100)


def test_an_uploaded_still_outside_the_newest_k_fails_without_scrolling_down(monkeypatch):
    _scores(monkeypatch, {"start": 0.5})
    page = _VirtualListPage(["plate0", "plate1", "start"], top=0)
    downs = []
    real = page.mouse.wheel

    async def wheel(dx, dy):
        downs.append(dy)
        await real(dx, dy)
    page.mouse.wheel = wheel
    assert asyncio.run(fs._picker_newest(page, Path("s.png"), fs.START_LIST_XY, 2)) is None
    assert all(dy < 0 for dy in downs)   # only the scroll to the top


def test_with_two_uploads_the_end_is_first_and_the_start_second(monkeypatch):
    # each still scores low only against its own thumbnail
    monkeypatch.setattr(fs, "slot_diff", lambda data, still: 0.5 if data.decode() == Path(still).stem else 40.0)
    page = _VirtualListPage(["end", "start", "plate"], top=0)
    assert asyncio.run(fs._picker_newest(page, Path("end.png"), fs.START_LIST_XY, 2)) == (142, 100)
    assert asyncio.run(fs._picker_newest(page, Path("start.png"), fs.START_LIST_XY, 2)) == (142, 148)


def test_a_near_twin_within_k_is_refused_but_a_duplicate_upload_is_taken(monkeypatch):
    _scores(monkeypatch, {"start": 0.5, "twin": 2.0})
    page = _VirtualListPage(["start", "twin", "plate"], top=0)
    assert asyncio.run(fs._picker_newest(page, Path("s.png"), fs.START_LIST_XY, 2)) is None
    _scores(monkeypatch, {"start": 0.5, "start2": 0.6})
    monkeypatch.setattr(fs, "same_image", lambda a, b: True)
    page = _VirtualListPage(["start", "start2", "plate"], top=0)
    assert asyncio.run(fs._picker_newest(page, Path("s.png"), fs.START_LIST_XY, 2)) == (142, 100)


def test_upload_mode_slot_records_upload_newest_and_names_the_failure(monkeypatch):
    seen = []

    async def newest(_page, _still, over, k):
        seen.append((over, k))
        return (150, 148)
    ups = []

    async def upload(_page, f):
        ups.append(f.name)
        return True
    monkeypatch.setattr(fs, "_upload_in_picker", upload)
    monkeypatch.setattr(fs, "_picker_newest", newest)
    monkeypatch.setattr(fs, "slot_diff", lambda data, _still: 0.2)
    page, rec = _SlotPage(), {}
    assert asyncio.run(fs._fill_frame_slot(page, "start", "", Path("s.png"), rec, newest_k=2)) is None
    assert rec["start_found_by"] == "upload_newest" and seen == [((150, 148), 2)] and ups == ["s.png"]

    async def nothing(*_a, **_k):
        return None
    monkeypatch.setattr(fs, "_picker_newest", nothing)
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "start", "", Path("s.png"), {}, newest_k=1)) == "START_NOT_FOUND upload"
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "end", "", Path("e.png"), {}, newest_k=1)) == "END_NOT_FOUND upload"


def test_upload_frames_parses_without_a_start_token():
    args = fs.parse_args(["p.txt", "o.mp4", "--upload-frames", "--start-file", "s.png", "--end-file", "e.png"])
    assert args.upload_frames and args.start == "" and args.end_file == "e.png"
    with pytest.raises(SystemExit):
        fs.parse_args(["p.txt", "o.mp4"])


def test_upload_mode_uploads_once_inside_the_picker_after_a_clearing_click(monkeypatch):
    """Video mode has no composer "+": the still is uploaded from the slot picker; when the first slot click only
    cleared an old frame (no picker open), the second click opens it and the upload happens exactly once."""
    calls = []

    async def upload(_page, f):
        calls.append(f.name)
        return len(calls) > 1   # first call: no picker visible

    async def newest(*_a):
        return (150, 148)
    monkeypatch.setattr(fs, "_upload_in_picker", upload)
    monkeypatch.setattr(fs, "_picker_newest", newest)
    monkeypatch.setattr(fs, "slot_diff", lambda data, _still: 0.2)
    rec = {}
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "start", "", Path("s.png"), rec, newest_k=1)) is None
    assert calls == ["s.png", "s.png"] and rec["start_found_by"] == "upload_newest"


def test_upload_mode_with_no_picker_at_all_fails_before_submit(monkeypatch):
    async def upload(_page, _f):
        return False
    monkeypatch.setattr(fs, "_upload_in_picker", upload)
    assert asyncio.run(fs._fill_frame_slot(_SlotPage(), "start", "", Path("s.png"), {}, newest_k=1)) == "START_NOT_FOUND upload"


def test_pre_submit_error_costs_no_credit():
    from types import SimpleNamespace
    from film_pipeline.production.generate import credit_ledger
    led = credit_ledger(SimpleNamespace(takes=[]), {"SC02_g1_t5": {"result": "PRE_SUBMIT_ERROR TimeoutError",
                                                                   "expected_credits": 5.0}})
    assert led["pre_submit"] == ["SC02_g1_t5"] and led["spent"] == 0


def test_newest_ignores_small_page_images_outside_the_list_column(monkeypatch):
    """Live 2026-11-08: the header avatar (x 1219, y 38) sorted above the list and was taken as the newest item."""
    class _Page(_VirtualListPage):
        async def evaluate(self, js, *a):
            return [[1219, 38, list(b"avatar")]] + await super().evaluate(js, *a)
    _scores(monkeypatch, {"start": 0.4})
    page = _Page(["start", "plate", "other"], top=0)
    assert asyncio.run(fs._picker_newest(page, Path("s.png"), (162, 300), 1)) == (142, 100)


def test_no_flow_tab_is_a_pre_submit_error(monkeypatch, tmp_path):
    # 2026-11-09 film04 SC03_g1 t1: no Flow tab -> StopIteration crash, the receipt read NO_MANIFEST and used an AMBER send
    import types
    from types import SimpleNamespace

    class _Ctx:
        pages = [SimpleNamespace(url="https://chatgpt.com/")]

    class _Browser:
        contexts = [_Ctx()]

    class _PW:
        class chromium:  # noqa: N801
            @staticmethod
            async def connect_over_cdp(*_a, **_k):
                return _Browser()

        async def stop(self):
            return None

    class _Starter:
        async def start(self):
            return _PW()

    fake = types.ModuleType("patchright.async_api")
    fake.async_playwright = lambda: _Starter()
    monkeypatch.setitem(sys.modules, "patchright.async_api", fake)
    prompt = tmp_path / "p.txt"
    prompt.write_text("a prompt", encoding="utf-8")
    args = SimpleNamespace(prompt_file=str(prompt), out=str(tmp_path / "o.mp4"), attach=[], start="", end="", upload=[])
    rec = asyncio.run(fs.run(args))
    assert rec["result"] == "PRE_SUBMIT_ERROR NO_FLOW_TAB"



class _Page:
    """Fake Flow page for reconcile_bind: no failed tile, waits return at once."""
    url = "https://labs.google/fx/tools/flow/project/p"

    async def evaluate(self, *_a):
        return {"running": False, "failed": 0}

    async def wait_for_timeout(self, _ms):
        return None


PROMPT_R = "The old man looks down at the brass key and speaks to the woman."
MID_NEW, MID_OLD = "11111111-2222-3333-4444-5555aaaaaaaa", "11111111-2222-3333-4444-5555bbbbbbbb"


def _detail(mid):
    return {"url": f"https://labs.google/fx/tools/flow/project/p/edit/{mid}", "text": "x " + PROMPT_R}


def _patch(monkeypatch, rounds, at_index=None, saved=None):
    import flow_reconcile as fr
    it = iter(rounds)

    async def scan(_page, _n):
        return next(it)

    async def download(_page, _ctx, n, out):
        out.write_bytes(b"video")
        if saved is not None:
            saved.append(n)
        return None

    async def nth(_page, n, _home):
        return at_index(n) if at_index else None

    monkeypatch.setattr(fr, "scan_gallery", scan)
    monkeypatch.setattr(fr, "download_nth", download)
    monkeypatch.setattr(fs, "read_nth_detail", nth)


def test_reconcile_bind_saves_the_one_new_clip_that_holds_the_prompt(tmp_path, monkeypatch):
    # P17-05: film05 needed flow_reconcile after 5 of 13 sends; flow_send now binds the same way inside the send
    import time
    saved: list = []
    _patch(monkeypatch, [[], [_detail(MID_NEW)]], at_index=lambda n: _detail(MID_NEW), saved=saved)
    rec: dict = {"result": "UNBOUND"}
    out = tmp_path / "SC03_g1_t1.mp4"
    assert asyncio.run(fs.reconcile_bind(_Page(), None, PROMPT_R, out, rec, time.time() + 60, 0, []))
    assert rec["result"] == "PASSED" and rec["binding"] == "RECONCILE_PROMPT_MATCH"
    assert rec["reconcile_bind"]["tries"] == 2 and saved == [0] and out.read_bytes() == b"video"


def test_reconcile_bind_never_takes_a_clip_that_existed_before_the_send(tmp_path, monkeypatch):
    # Codex review: an older unresolved retake with the same prompt must not pass as this send's clip
    _patch(monkeypatch, [[_detail(MID_OLD)]])
    rec: dict = {"result": "UNBOUND"}
    assert not asyncio.run(fs.reconcile_bind(_Page(), None, PROMPT_R, tmp_path / "X_t2.mp4", rec, 0.0, 0, [MID_OLD]))
    assert rec["result"] == "UNBOUND" and rec["reconcile_bind"]["result"] == "NOT_IN_GALLERY"


def test_reconcile_bind_does_not_download_when_the_gallery_moved(tmp_path, monkeypatch):
    # Codex review: another clip landed in front between the scan and the download
    _patch(monkeypatch, [[_detail(MID_NEW)]], at_index=lambda n: _detail(MID_OLD))
    rec: dict = {"result": "UNBOUND"}
    out = tmp_path / "X_t1.mp4"
    assert not asyncio.run(fs.reconcile_bind(_Page(), None, PROMPT_R, out, rec, 0.0, 0, []))
    assert rec["reconcile_bind"]["result"] == "MOVED" and not out.exists()


def test_reconcile_bind_records_an_error_instead_of_raising(tmp_path, monkeypatch):
    import flow_reconcile as fr

    async def boom(_page, _n):
        raise RuntimeError("page closed")

    monkeypatch.setattr(fr, "scan_gallery", boom)
    rec: dict = {"result": "UNBOUND"}
    assert not asyncio.run(fs.reconcile_bind(_Page(), None, PROMPT_R, tmp_path / "X_t1.mp4", rec, 0.0, 0, []))
    assert rec["result"] == "UNBOUND" and rec["reconcile_bind"]["error"].startswith("RuntimeError")
