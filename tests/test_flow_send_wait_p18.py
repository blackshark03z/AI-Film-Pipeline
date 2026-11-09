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


class _Page:
    """Fake Flow gallery: job state and screenshot per poll come from scripted lists."""
    url = "https://labs.google/fx/tools/flow/project/p"

    def __init__(self, shots, failed=None):
        self.shots, self.failed, self.mouse = list(shots), list(failed or []), SimpleNamespace(move=self._noop)
        self.png, self.rects = shots[0]

    async def _noop(self, *_):
        return None

    async def evaluate(self, js, *_a):
        if js == fs.JS_JOB_STATE:
            return {"running": False, "failed": self.failed.pop(0) if self.failed else 0}
        if js == fs.JS_VIDEO_RECTS:
            if self.shots:
                self.png, self.rects = self.shots.pop(0)
            return self.rects
        if js == "window.devicePixelRatio":
            return 1.375
        return ""

    async def screenshot(self):
        return self.png

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
