"""P18-01: the video wait ends on new tile PIXELS and the bind uses media id + whole prompt (never tokens or counts).

film05 page states these tests replay (take manifests, 2026-11-09): SC01_g1 the token wait ended at 38 s on 16
re-issued thumbnails; SC01_g2 video_count read 37->30; SC03_g1 32->41; SC02_g2 v1 the bound tile was still rendering."""
import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "drama_flow_ui"))
import flow_reconcile as fr  # noqa: E402
import flow_send as fs  # noqa: E402

PROMPT = "The waitress sets one cup on the table and looks at the man."
MID_NEW, MID_OLD = "aaaaaaaa-2222-3333-4444-5555aacbb523", "bbbbbbbb-2222-3333-4444-55555c258895"


def _frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = cv2.resize(rng.integers(0, 255, (9, 16, 3), dtype=np.uint8), (320, 180), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(img, (5, 5), 0)


def _gallery(frames: list[np.ndarray], quality: int = 92) -> tuple[bytes, list]:
    """A viewport screenshot (PNG) holding the given thumbnails in one row, plus their CSS rects at dpr 1.375."""
    dpr = 1.375
    canvas = np.full((int(720 * dpr), int(1280 * dpr), 3), 30, np.uint8)
    rects = []
    for i, f in enumerate(frames):
        # each thumbnail goes through a JPEG round trip at `quality`: a re-issued thumbnail is the same frame re-encoded
        ok, jpg = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, quality])
        f = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        x, y, w, h = 20 + i * 300, 100, 280, 158
        tile = cv2.resize(f, (int(w * dpr), int(h * dpr)))
        canvas[int(y * dpr):int(y * dpr) + tile.shape[0], int(x * dpr):int(x * dpr) + tile.shape[1]] = tile
        rects.append([x, y, w, h])
    return cv2.imencode(".png", canvas)[1].tobytes(), rects


def _sigs(frames, quality=92):
    png, rects = _gallery(frames, quality)
    return fs.tile_signatures(png, rects, 1.375)


def test_reissued_thumbnails_are_not_new_but_a_new_clip_is():
    # film05 SC01_g1: 16 "new" tokens after 38 s, none of them a new clip
    old = [_frame(i) for i in range(4)]
    before = _sigs(old)
    assert fs.new_tiles(before, _sigs(old, quality=60)) == 0
    assert fs.new_tiles(before, _sigs([_frame(99)] + old[:3], quality=60)) == 1


def test_wait_verdict_replays_the_film05_timelines():
    # the token wait bound at 38-59 s; the pixel wait keeps waiting while nothing new is on screen
    assert fs.wait_verdict(38, 600, running=False, failed_new=False, fresh=0) == "WAIT"
    assert fs.wait_verdict(30, 600, running=False, failed_new=False, fresh=1) == "WAIT"     # too early
    assert fs.wait_verdict(80, 600, running=True, failed_new=False, fresh=1) == "WAIT"
    assert fs.wait_verdict(80, 600, running=False, failed_new=False, fresh=1) == "BIND"
    assert fs.wait_verdict(41, 600, running=False, failed_new=True, fresh=0) == "FAILED"    # SC03_g1 t1
    assert fs.wait_verdict(600, 600, running=False, failed_new=False, fresh=0) == "BIND"    # vanished job: last scan
    # Codex 2026-11-09: a failed tile while a job still renders may be another job's; wait for the running one
    assert fs.wait_verdict(41, 600, running=True, failed_new=True, fresh=0) == "WAIT"


class _Page:
    """Fake Flow gallery: job state and screenshot per poll come from scripted lists."""
    url = "https://labs.google/fx/tools/flow/project/p"

    def __init__(self, shots, failed=None, running=False):
        self.running = running
        self.shots, self.failed, self.mouse = list(shots), list(failed or []), SimpleNamespace(move=self._noop)
        self.png, self.rects = shots[0]

    async def _noop(self, *_):
        return None

    async def evaluate(self, js, *_a):
        if js == fs.JS_JOB_STATE:
            return {"running": self.running, "failed": self.failed.pop(0) if self.failed else 0}
        if js == fs.JS_VIDEO_RECTS:
            if self.shots:
                self.png, self.rects = self.shots.pop(0)
            return self.rects
        if js == "window.devicePixelRatio":
            return 1.375
        return ""

    @property
    def context(self):
        page = self

        class _Cdp:
            async def send(self, method, _params):
                import base64
                assert method == "Page.captureScreenshot" and _params["format"] == "jpeg"
                return {"data": base64.b64encode(page.png).decode()}

            async def detach(self):
                return None

        class _Ctx:
            async def new_cdp_session(self, _page):
                return _Cdp()
        return _Ctx()

    async def wait_for_timeout(self, _ms):
        return None


def _detail(mid):
    return {"url": f"https://labs.google/fx/tools/flow/project/p/edit/{mid}", "text": "x " + PROMPT}


def _patch(monkeypatch, scans, downloads=None, clock=None):
    it, dl = iter(scans), iter(downloads or [None] * 10)

    async def scan(_page, _n):
        return next(it)

    async def download(_page, _ctx, _n, out):
        failed = next(dl)
        if failed is None:
            out.write_bytes(b"video")
        return failed

    async def nth(_page, n, _home):
        return _detail(MID_NEW)

    monkeypatch.setattr(fr, "scan_gallery", scan)
    monkeypatch.setattr(fr, "download_nth", download)
    monkeypatch.setattr(fs, "read_nth_detail", nth)
    if clock:
        monkeypatch.setattr(fs.time, "time", clock)


def _clock(step):
    t = {"now": 1000.0}

    def now():
        t["now"] += step
        return t["now"]
    return now


def _pre(old):
    png, rects = _gallery(old)
    return {"front_id": MID_OLD, "before_ids": [MID_OLD], "signatures": fs.tile_signatures(png, rects, 1.375)}


def test_send_binds_by_media_id_after_the_pixels_change(tmp_path, monkeypatch):
    # SC01_g2/SC05_g1 v2: video_count went down (37->30, 45->39) although a clip was added; counts decide nothing now
    old = [_frame(i) for i in range(4)]
    shots = [_gallery(old, 60)] * 6 + [_gallery([_frame(7)] + old[:3])] * 4
    _patch(monkeypatch, [[_detail(MID_OLD)], [_detail(MID_NEW), _detail(MID_OLD)]], clock=_clock(5))
    rec: dict = {}
    args = SimpleNamespace(timeout=600, image=False)
    out = tmp_path / "SC01_g2_t1.mp4"
    page = _Page(shots)
    res = asyncio.run(fs._video_wait_and_bind(page, None, args, PROMPT, out, rec, _pre(old), 1000.0, 0))
    assert res["result"] == "PASSED" and res["binding"] == "RECONCILE_PROMPT_MATCH"
    assert res["media_id_tail"] == MID_NEW[-8:] and res["wait"]["verdict"] == "BIND" and res["wait"]["polls"] >= 7


def test_a_still_rendering_tile_is_downloaded_on_a_later_poll(tmp_path, monkeypatch):
    # SC02_g2 v1: the front tile had no video yet ("no media id for the front video"); the media id is bound, retry
    _patch(monkeypatch, [[_detail(MID_NEW)]] * 3, downloads=["NO_VIDEO_UNDER_TILE", None], clock=_clock(1))
    rec: dict = {}
    out = tmp_path / "SC02_g2_t1.mp4"
    assert asyncio.run(fs.reconcile_bind(_Page([_gallery([_frame(1)])]), None, PROMPT, out, rec, 1100.0, 0, []))
    assert rec["result"] == "PASSED" and rec["reconcile_bind"]["download_retries"] == 1 and out.read_bytes() == b"video"


def test_a_new_failed_tile_without_a_clip_is_flow_failed(tmp_path, monkeypatch):
    # SC03_g1 t1: "Không thành công" tile; one bind scan still runs (the failed tile is page-wide)
    old = [_frame(i) for i in range(3)]

    async def no_fail(*_a):
        return False
    monkeypatch.setattr(fs, "flow_failed", no_fail)
    _patch(monkeypatch, [[_detail(MID_OLD)]], clock=_clock(5))
    rec: dict = {}
    page = _Page([_gallery(old)] * 4, failed=[0, 0, 1, 1, 1, 1])
    res = asyncio.run(fs._video_wait_and_bind(page, None, SimpleNamespace(timeout=600), PROMPT,
                                              tmp_path / "X_t1.mp4", rec, _pre(old), 1000.0, 0))
    assert res["result"] == "FLOW_FAILED" and res["wait"]["verdict"] == "FAILED"
    assert res["reconcile_bind"]["tries"] == 1


def test_a_vanished_job_times_out_after_one_last_scan(tmp_path, monkeypatch):
    # SC02_g2 v1 / SC04_g1 v1 (12:09, 13:23): no tile, no failed tile; TIMEOUT, not a wrong clip
    old = [_frame(i) for i in range(3)]

    async def no_fail(*_a):
        return False
    monkeypatch.setattr(fs, "flow_failed", no_fail)
    _patch(monkeypatch, [[_detail(MID_OLD)]], clock=_clock(60))
    rec: dict = {}
    page = _Page([_gallery(old, 70)] * 20)
    res = asyncio.run(fs._video_wait_and_bind(page, None, SimpleNamespace(timeout=600), PROMPT,
                                              tmp_path / "X_t1.mp4", rec, _pre(old), 1000.0, 0))
    assert res["result"] == "TIMEOUT" and res["wait"]["fresh_max"] == 0 and not (tmp_path / "X_t1.mp4").exists()


def test_a_vanished_job_is_a_provider_failure_after_a_full_scan_ten_minutes_in(tmp_path, monkeypatch):
    # P18-03: proven inside the send (as flow_reconcile's P17-07 does 10 min later), so generate can resend at once
    old = [_frame(i) for i in range(3)]

    async def no_fail(*_a):
        return False
    monkeypatch.setattr(fs, "flow_failed", no_fail)
    others = [_detail(MID_OLD)] + [{"url": f"https://x/edit/cccccccc-2222-3333-4444-55555555000{i}", "text": "other"}
                                   for i in range(5)]
    _patch(monkeypatch, [others], clock=_clock(60))
    rec: dict = {}
    res = asyncio.run(fs._video_wait_and_bind(_Page([_gallery(old)] * 20), None, SimpleNamespace(timeout=600), PROMPT,
                                              tmp_path / "X_t1.mp4", rec, _pre(old), 1000.0, 0))
    assert res["result"] == "FLOW_FAILED_NO_CLIP" and res["provider_no_clip"] and res["reconcile_bind"]["scanned"] == 6


def test_no_screenshot_means_no_pixels_never_a_crash(monkeypatch):
    # P18-06 live (film05 SC02_g2 v3): page.screenshot waited 30 s for fonts and the exception ended the send
    class _Cdp:
        async def send(self, *_a):
            raise TimeoutError("captureScreenshot")

        async def detach(self):
            return None

    class _Ctx:
        async def new_cdp_session(self, _page):
            return _Cdp()

    class _NoShot(_Page):
        context = _Ctx()
    assert asyncio.run(fs.gallery_signatures(_NoShot([_gallery([_frame(1)])]))) == []
    # with no baseline pixels every tile reads as new: the wait binds at WAIT_MIN_S and reconcile_bind decides
    assert fs.new_tiles([], _sigs([_frame(1)])) == 1


def test_an_error_before_the_prompt_is_typed_is_a_pre_submit_error(tmp_path, monkeypatch):
    # P18-06 live: the crash in front_snapshot left the receipt NO_MANIFEST, which the ledger reads as a paid send
    class _Kb:
        async def press(self, *_a):
            return None

    class _Flow(_Page):
        url = "https://flow.google.com/project/p"
        keyboard = _Kb()

        async def set_viewport_size(self, *_a):
            return None

    flow = _Flow([_gallery([_frame(1)])])

    class _Browser:
        contexts = [SimpleNamespace(pages=[flow])]

    class _Chromium:
        async def connect_over_cdp(self, *_a, **_k):
            return _Browser()

    class _Pw:
        chromium = _Chromium()

        async def stop(self):
            return None

    class _Start:
        async def start(self):
            return _Pw()

    async def boom(*_a, **_k):
        raise TimeoutError("Page.screenshot: Timeout 30000ms exceeded.")

    import patchright.async_api as pa
    monkeypatch.setattr(pa, "async_playwright", lambda: _Start())
    monkeypatch.setattr(fs, "front_snapshot", boom)
    prompt = tmp_path / "p.txt"
    prompt.write_text(PROMPT, encoding="utf-8")
    args = fs.parse_args([str(prompt), str(tmp_path / "SC02_g2_t3.mp4"), "--upload-frames", "--start-file",
                          str(tmp_path / "s.png"), "--model", "Omni 1.2 Flash", "--duration", "7"])
    rec = asyncio.run(fs.run(args))
    assert rec["result"] == "PRE_SUBMIT_ERROR TimeoutError" and "screenshot" in rec["error"]


def test_a_job_still_running_at_the_deadline_is_never_a_provider_failure(tmp_path, monkeypatch):
    # Codex 2026-11-09: FLOW_FAILED_NO_CLIP would auto-resend and pay twice while the first job may still deliver
    old = [_frame(i) for i in range(3)]

    async def no_fail(*_a):
        return False
    monkeypatch.setattr(fs, "flow_failed", no_fail)
    others = [_detail(MID_OLD)] + [{"url": f"https://x/edit/cccccccc-2222-3333-4444-55555555000{i}", "text": "other"}
                                   for i in range(5)]
    _patch(monkeypatch, [others], clock=_clock(60))
    rec: dict = {}
    page = _Page([_gallery(old)] * 20, running=True)
    res = asyncio.run(fs._video_wait_and_bind(page, None, SimpleNamespace(timeout=600), PROMPT,
                                              tmp_path / "X_t1.mp4", rec, _pre(old), 1000.0, 0))
    assert res["result"] == "UNBOUND" and res["job_running"] and not res.get("provider_no_clip")

# P18-07 stray-job guard. Recorded state it replays: film05 runs one send at a time; an earlier send of the same shot
# that ended UNBOUND while its job still rendered (Codex 2026-11-09) finishes late during the next send, so the gallery
# holds two unregistered clips with the same whole prompt, and its failure, if it fails, is a page-wide failed tile.
MID_OWN, MID_STRAY = "dddddddd-2222-3333-4444-5555000000aa", "eeeeeeee-2222-3333-4444-5555000000bb"


def _failed(mid):
    return {"url": f"https://labs.google/fx/tools/flow/project/p/edit/{mid}", "text": "x " + PROMPT + " " + fs.FAILED_TEXT}


def _patch_scans(monkeypatch, scans, clock):
    """Each gallery scan returns the next recorded list; a detail re-read reads the current list."""
    state = {"now": [], "it": iter(scans)}

    async def scan(_page, _n):
        state["now"] = next(state["it"], state["now"])
        return state["now"]

    async def nth(_page, n, _home):
        return state["now"][n] if n < len(state["now"]) else None

    async def download(_page, _ctx, n, out):
        if fs.FAILED_TEXT in state["now"][n]["text"] or state["now"][n]["text"].startswith("rendering"):
            return "NO_VIDEO_UNDER_TILE"
        out.write_bytes(state["now"][n]["url"][-8:].encode())
        return None
    monkeypatch.setattr(fr, "scan_gallery", scan)
    monkeypatch.setattr(fr, "download_nth", download)
    monkeypatch.setattr(fs, "read_nth_detail", nth)
    monkeypatch.setattr(fs.time, "time", clock)


def _pre_own(old, own=MID_OWN):
    return {**_pre(old), "own": {"media_id": own}}


def test_own_tile_only_binds_the_send_s_own_clip_never_a_stray():
    stray_only = [_detail(MID_STRAY), _detail(MID_OLD)]
    res = fs.own_tile_only({"result": "BOUND", "media_id": MID_STRAY, "index": 0}, stray_only, MID_OWN, PROMPT)
    assert res["result"] == "NOT_IN_GALLERY" and res["strays"] == [MID_STRAY]
    both = [_detail(MID_OWN), _detail(MID_STRAY), _detail(MID_OLD)]
    res = fs.own_tile_only({"result": "AMBIGUOUS", "media_ids": [MID_OWN, MID_STRAY]}, both, MID_OWN, PROMPT)
    assert res == {"result": "BOUND", "media_id": MID_OWN, "index": 0, "strays": [MID_STRAY]}
    assert fs.own_tile_state(both, MID_OWN) == "OK" and fs.own_tile_state(stray_only, MID_OWN) == "MISSING"
    assert fs.own_tile_state([_failed(MID_OWN)], MID_OWN) == "FAILED"


def test_a_stray_clip_finishing_first_is_not_bound_the_own_clip_is(tmp_path, monkeypatch):
    # the stray (same prompt, not registered, not there before the send) finishes first; without the own media id
    # the prompt match alone would have bound it as this send's clip
    old = [_frame(i) for i in range(3)]
    shots = [_gallery([_frame(8)] + old[:2])] * 20
    scans = [[{"url": _detail(MID_OWN)["url"], "text": "rendering"}, _detail(MID_STRAY), _detail(MID_OLD)],
             [_detail(MID_OWN), _detail(MID_STRAY), _detail(MID_OLD)]]
    _patch_scans(monkeypatch, scans, _clock(5))
    rec: dict = {}
    out = tmp_path / "SC02_g2_t5.mp4"
    res = asyncio.run(fs._video_wait_and_bind(_Page(shots), None, SimpleNamespace(timeout=600), PROMPT, out, rec,
                                              _pre_own(old), 1000.0, 0))
    assert res["result"] == "PASSED" and res["media_id_tail"] == MID_OWN[-8:]
    assert out.read_bytes() == MID_OWN[-8:].encode() and res["stray_media_tails"] == [MID_STRAY[-8:]]


def test_a_stray_job_failing_late_is_not_this_send_s_failure(tmp_path, monkeypatch):
    # a failed tile appears (the stray's) while the own tile is fine: keep waiting, then bind the own clip
    old = [_frame(i) for i in range(3)]
    shots = [_gallery(old)] * 3 + [_gallery([_frame(8)] + old[:2])] * 20
    stray_failed = _failed(MID_STRAY)
    scans = [[{"url": _detail(MID_OWN)["url"], "text": "rendering " + PROMPT}, stray_failed, _detail(MID_OLD)],
             [_detail(MID_OWN), stray_failed, _detail(MID_OLD)]]
    _patch_scans(monkeypatch, scans, _clock(5))
    rec: dict = {}
    page = _Page(shots, failed=[0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    res = asyncio.run(fs._video_wait_and_bind(page, None, SimpleNamespace(timeout=600), PROMPT,
                                              tmp_path / "X_t2.mp4", rec, _pre_own(old), 1000.0, 0))
    assert res["result"] == "PASSED" and res["media_id_tail"] == MID_OWN[-8:] and res["stray_failures"] == 1


def test_the_own_tile_failing_is_flow_failed(tmp_path, monkeypatch):
    old = [_frame(i) for i in range(3)]
    _patch_scans(monkeypatch, [[_failed(MID_OWN), _detail(MID_OLD)]], _clock(5))
    page = _Page([_gallery(old)] * 6, failed=[0, 0, 1, 1, 1, 1])
    res = asyncio.run(fs._video_wait_and_bind(page, None, SimpleNamespace(timeout=600), PROMPT,
                                              tmp_path / "X_t2.mp4", {}, _pre_own(old), 1000.0, 0))
    assert res["result"] == "FLOW_FAILED" and res["own_tile"] == "FAILED"


def test_an_own_tile_still_there_at_the_deadline_is_never_a_vanished_job(tmp_path, monkeypatch):
    # P18-03 would call 6 scanned pages without the prompt a vanished job; the own tile is there, so it is not
    old = [_frame(i) for i in range(3)]
    others = [{"url": _detail(MID_OWN)["url"], "text": "rendering"}] + [
        {"url": f"https://x/edit/cccccccc-2222-3333-4444-55555555000{i}", "text": "other"} for i in range(5)]
    _patch_scans(monkeypatch, [others], _clock(60))

    async def no_fail(*_a):
        return False
    monkeypatch.setattr(fs, "flow_failed", no_fail)
    res = asyncio.run(fs._video_wait_and_bind(_Page([_gallery(old)] * 20), None, SimpleNamespace(timeout=600), PROMPT,
                                              tmp_path / "X_t2.mp4", {}, _pre_own(old), 1000.0, 0))
    assert res["result"] == "UNBOUND" and res["own_tile"] == "OK" and not res.get("provider_no_clip")


def test_submit_tile_takes_only_a_new_unfinished_tile_in_front(monkeypatch):
    # film05 SC02_g2 v4 (23:32): a pixel check before the submit fired on the start-frame upload, so the send had no
    # identity. SC05_g1 v4 (23:43): 8 s after the submit the own tile read 'play_circle 0% ...' and its media id
    # (5e84dd42) was the clip bound later; a tile with no percentage is already finished, so not this send's
    async def sigs(_page, k=8):
        return [np.zeros(fs.TILE_SIG_SIZE[::-1])]
    monkeypatch.setattr(fs, "gallery_signatures", sigs)

    class _Front:
        def __init__(self, text):
            self.text = text

        async def evaluate(self, js, *_a):
            return self.text if js == fs.JS_FRONT_TILE_TEXT else None

        async def wait_for_timeout(self, _ms):   # P19-02: a tile with no percentage is read again first
            pass
    monkeypatch.setattr(fs, "STRAY_RECHECK_MS", 0)
    rendering = "favorite redo more_vert play_circle 0% The given image is the first frame. A single"  # live, 23:43
    for front, text, want, why in ((MID_OWN, rendering, MID_OWN, None),
                                   (MID_OWN, "play_circle Woman speaks to old man", None, "STRAY_IN_FRONT"),
                                   (MID_OLD, "play_circle 360p", None, "OLD_TILE_IN_FRONT"),
                                   (MID_STRAY, rendering, None, "OLD_TILE_IN_FRONT")):
        async def nth(_page, _n, _home, mid=front):
            return _detail(mid)
        monkeypatch.setattr(fs, "read_nth_detail", nth)
        own = asyncio.run(fs.submit_tile(_Front(text), "home", [MID_OLD], {MID_STRAY[-8:]}))
        assert own["media_id"] == want and own.get("why") == why


def test_submit_tile_waits_for_a_just_queued_own_tile_to_show_its_percentage(monkeypatch):
    # P19-02, film06 (5 of 17 sends): 8 s after the submit the own tile read "play_circle The given image is the
    # first frame..." with no percentage yet, so it was called a stray; the same media id was the clip bound later
    async def sigs(_page, k=8):
        return [np.zeros(fs.TILE_SIG_SIZE[::-1])]
    monkeypatch.setattr(fs, "gallery_signatures", sigs)
    monkeypatch.setattr(fs, "STRAY_RECHECK_MS", 0)
    queued = "play_circle The given image is the first frame. A single unbroken shot"   # live, film06 SC03_g2
    rendering = "play_circle 3% The given image is the first frame. A single unbroken shot"

    class _Front:
        def __init__(self, texts):
            self.texts, self.waits = list(texts), 0

        async def evaluate(self, js, *_a):
            if js != fs.JS_FRONT_TILE_TEXT:
                return None
            return self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]

        async def wait_for_timeout(self, _ms):
            self.waits += 1

    def nth_of(mids):
        seq = list(mids)

        async def nth(_page, _n, _home):
            return _detail(seq.pop(0) if len(seq) > 1 else seq[0])
        return nth
    # queued, then rendering on the 2nd re-read, same media id -> own
    page = _Front([queued, queued, rendering])
    monkeypatch.setattr(fs, "read_nth_detail", nth_of([MID_OWN]))
    own = asyncio.run(fs.submit_tile(page, "home", [MID_OLD], set()))
    assert own["media_id"] == MID_OWN and "why" not in own and page.waits == 2
    # a finished clip never shows a percentage: still a stray after every re-read
    page = _Front(["play_circle Woman speaks to old man"])
    own = asyncio.run(fs.submit_tile(page, "home", [MID_OLD], set()))
    assert own["media_id"] is None and own["why"] == "STRAY_IN_FRONT" and page.waits == fs.STRAY_RECHECKS
    # the percentage belongs to a different tile that came in front meanwhile -> no identity taken
    page = _Front([queued, rendering])
    monkeypatch.setattr(fs, "read_nth_detail", nth_of([MID_OWN, MID_STRAY]))
    own = asyncio.run(fs.submit_tile(page, "home", [MID_OLD], set()))
    assert own["media_id"] is None and own["why"] == "STRAY_IN_FRONT"
