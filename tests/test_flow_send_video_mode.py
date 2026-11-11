"""Before every video send flow_send forces video mode + Omni 1.2 Flash 360p and verifies them (film07 pilot:
an image-mode still left the composer in image mode and the next video send died SETTINGS_NOT_SET)."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "drama_flow_ui"))
import flow_send as fs  # noqa: E402


class _El:
    def __init__(self, text, click=None, attrs=None):
        self.text, self._click, self.attrs = text, click, attrs or {}


class _Loc:
    def __init__(self, page, sel, filters=()):
        self.page, self.sel, self.filters = page, sel, tuple(filters)

    def filter(self, has_text=None):
        return _Loc(self.page, self.sel, self.filters + (has_text,))

    @property
    def first(self):
        return self

    def _els(self):
        out = self.page.elements(self.sel)
        for f in self.filters:
            out = [e for e in out if (f.search(e.text) if hasattr(f, "search") else f.lower() in e.text.lower())]
        return out

    async def count(self):
        return len(self._els())

    async def click(self):
        el = self._els()[0]
        self.page.clicks.append(el.text)
        if el._click:
            el._click()

    async def focus(self):
        pass

    async def inner_text(self):
        return self._els()[0].text

    async def get_attribute(self, name):
        return self._els()[0].attrs.get(name)


class FakeComposer:
    """Flow composer: a chip, and a settings menu with mode / resolution radios, a model dropdown, a duration slider."""

    def __init__(self, mode="image", res="720p", chip_after=0, stuck_mode=False, sub="Thành phần", lang="vi"):
        self.mode, self.res, self.dur, self.sub, self.lang = mode, res, 3, sub, lang
        self.menu = False
        self.chip_after, self.polls, self.stuck_mode = chip_after, 0, stuck_mode
        self.clicks, self.keys = [], []
        self.keyboard = SimpleNamespace(press=self._press)

    async def _press(self, key):
        self.keys.append(key)
        if key == "Escape":
            self.menu = False
        elif key == "ArrowRight":
            self.dur += 1
        elif key == "Home":
            self.dur = 3

    def _set_mode(self, m):
        if not self.stuck_mode:
            self.mode = m

    def _set_sub(self, s):
        self.sub = s

    def _set_res(self, r):
        self.res = r

    def elements(self, sel):
        if sel == "button":
            self.polls += 1
            if self.polls <= self.chip_after:
                return []
            unit = f"{self.dur}s" if self.lang == "en" else f"{self.dur} giây"
            chip = (f"Video · {self.res} · {unit} crop_16_9 x1" if self.mode == "video"
                    else "Nano Banana 2.1 crop_16_9 x1")
            els = [_El("home"), _El(chip, click=lambda: setattr(self, "menu", True))]
            if self.menu:
                els += self._radios()
                if self.mode == "video":
                    els.append(_El("Omni 1.2 Flash arrow_drop_down"))
            return els
        if sel == "button[role=radio]":
            return self._radios() if self.menu else []
        if sel.startswith("input[type=range]"):
            return [_El("")] if self.menu and self.mode == "video" else []
        raise AssertionError(sel)

    def _radios(self):
        def flag(b):
            return "true" if b else "false"
        en = self.lang == "en"
        return [_El("imageImage" if en else "imageHình ảnh", lambda: self._set_mode("image"), {"aria-checked": flag(self.mode == "image")}),
                _El("videocamVideo", lambda: self._set_mode("video"), {"aria-checked": flag(self.mode == "video")}),
                _El("crop_freeFrames" if en else "crop_freeKhung hình", lambda: self._set_sub("Khung hình"), {"aria-checked": flag(self.sub == "Khung hình")}),
                _El("chrome_extensionIngredients" if en else "chrome_extensionThành phần", lambda: self._set_sub("Thành phần"), {"aria-checked": flag(self.sub == "Thành phần")}),
                _El("360pinfo", lambda: self._set_res("360p"), {"aria-checked": flag(self.res == "360p")}),
                _El("720p", lambda: self._set_res("720p"), {"aria-checked": flag(self.res == "720p")})]

    def locator(self, sel):
        return _Loc(self, sel)

    async def wait_for_timeout(self, _ms):
        pass

    async def evaluate(self, script, *_args):
        if self.lang == "en":
            return f"Length\n{self.dur} Sec\nGenerating will use {self.dur} credits"
        return f"Độ dài {self.dur} giây\nSẽ tốn {self.dur} tín dụng"


def _run(page, **kw):
    rec = {}
    kw.setdefault("mode", "Video")
    kw.setdefault("resolution", "360p")
    return asyncio.run(fs._set_composer_settings(page, "Omni 1.2 Flash", 6, rec, **kw)), rec


def test_image_mode_composer_is_switched_back_to_video_360p_and_verified():
    page = FakeComposer(mode="image", res="720p")
    result, rec = _run(page)
    assert result is None
    assert page.mode == "video" and page.res == "360p" and page.dur == 6
    assert rec["mode_set"] == "Video" and rec["resolution_set"] == "360p"


def test_start_frame_send_forces_the_khung_hinh_sub_mode():
    page = FakeComposer(mode="image", res="720p")           # after an image detour the sub-mode is the ingredients one
    result, rec = _run(page, submode="Khung hình")
    assert result is None and page.sub == "Khung hình" and rec["submode_set"] == "Khung hình"
    ok, _ = _run(FakeComposer(mode="video", res="360p", sub="Khung hình"), submode="Khung hình")
    assert ok is None


def test_english_ui_account_is_driven_the_same_way():
    """The second Flow account (khoia1k57) shows English labels: Frames, a '6s' chip, 'Length 6 Sec', 'will use 6 credits'."""
    page = FakeComposer(mode="image", res="720p", lang="en")
    result, rec = _run(page, submode="Khung hình", expected_credits=6)
    assert result is None and page.mode == "video" and page.res == "360p" and page.dur == 6
    assert page.sub == "Khung hình" and rec["flow_credits"] == 6 and rec["duration_set"] == 6
    mismatch, _ = _run(FakeComposer(mode="video", res="360p", sub="Khung hình", lang="en"), expected_credits=7)
    assert mismatch.startswith("PRE_SUBMIT_ERROR CREDIT_QUOTE_MISMATCH")


def test_ui_text_parsers_read_both_languages():
    assert fs.parse_duration_s("Độ dài 8 giây") == 8 and fs.parse_duration_s("Length\n8 Sec") == 8
    assert fs.parse_cost("Sẽ tốn 8 tín dụng") == 8 and fs.parse_cost("Generating will use 48 credits") == 48
    assert fs.SETTINGS_CHIP_RE.search("Video · 360p · 6s crop_16_9 x1") and fs.SETTINGS_CHIP_RE.search("Video · 360p · 6 giây")
    assert fs.has_failed_text("Không thành công") and fs.has_failed_text("Unsuccessful") and not fs.has_failed_text("Done")
    assert fs.SLOT_LABEL["start"] == ["Bắt đầu", "Start"] and fs.SLOT_LABEL["end"] == ["Kết thúc", "End"]


def test_video_mode_composer_needs_no_mode_click():
    page = FakeComposer(mode="video", res="360p")
    result, _ = _run(page)
    assert result is None
    assert "videocamVideo" not in page.clicks and "360pinfo" not in page.clicks


def test_mode_that_does_not_stick_is_refused_before_submit():
    result, _ = _run(FakeComposer(mode="image", stuck_mode=True))
    assert result and result.startswith("SETTINGS_NOT_SET") and "Video" in result


def test_settings_chip_is_retried_a_bounded_number_of_times():
    late = FakeComposer(mode="video", res="360p", chip_after=2)   # chip missing for a few polls, then there
    result, _ = _run(late)
    assert result is None
    never = FakeComposer(mode="video", res="360p", chip_after=10_000)
    result, _ = _run(never)
    assert result == "SETTINGS_NOT_SET settings chip not found"
    assert never.polls <= 2 * fs.SETTINGS_CHIP_ATTEMPTS   # bounded: two locator lookups per attempt at most


def _patched_run(tmp_path, monkeypatch, *extra):
    import patchright.async_api as pa
    page = SimpleNamespace(url="https://flow.google.com/project/owned", set_viewport_size=AsyncMock(),
                           keyboard=SimpleNamespace(press=AsyncMock()), wait_for_timeout=AsyncMock(), on=Mock())
    page.evaluate = AsyncMock(side_effect=lambda js: {"failed": 0} if js == fs.JS_JOB_STATE else [])
    browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[page])])
    pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=AsyncMock(return_value=browser)), stop=AsyncMock())
    monkeypatch.setattr(pa, "async_playwright", lambda: SimpleNamespace(start=AsyncMock(return_value=pw)))
    monkeypatch.setattr(fs, "front_snapshot", AsyncMock(return_value={"before_ids": []}))
    monkeypatch.setattr(fs, "_fill_frame_slot", AsyncMock(return_value=None))
    seen = []

    async def settings(page, model, duration, record, expected_credits=None, mode=None, resolution=None, submode=None):
        seen.append({"model": model, "mode": mode, "resolution": resolution, "submode": submode})
        return "SETTINGS_NOT_SET stop here"
    monkeypatch.setattr(fs, "_set_composer_settings", settings)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("original fictional dialogue", encoding="utf-8")
    args = fs.parse_args([str(prompt), str(tmp_path / "out.mp4"), "--start", "tok:owned", *extra])
    return asyncio.run(fs.run(args)), seen


def test_every_video_send_forces_video_mode_and_360p(tmp_path, monkeypatch):
    result, seen = _patched_run(tmp_path, monkeypatch, "--model", "Omni 1.2 Flash", "--duration", "6")
    assert result["result"].startswith("SETTINGS_NOT_SET")
    assert seen == [{"model": "Omni 1.2 Flash", "mode": "Video", "resolution": "360p", "submode": "Khung hình"}]


def test_image_sends_do_not_force_video_mode(tmp_path, monkeypatch):
    _, seen = _patched_run(tmp_path, monkeypatch, "--image", "--model", "Nano Banana 2.1")
    assert seen == [{"model": "Nano Banana 2.1", "mode": None, "resolution": None, "submode": None}]


def test_start_frame_send_asks_for_the_khung_hinh_sub_mode(tmp_path, monkeypatch):
    still = tmp_path / "s.jpg"
    still.write_bytes(b"x")
    _, seen = _patched_run(tmp_path, monkeypatch, "--model", "Omni 1.2 Flash", "--duration", "6", "--start-file", str(still))
    assert seen[0]["submode"] == "Khung hình"
