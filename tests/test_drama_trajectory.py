"""Trajectory QC: a moved prop is measured with optical flow; the result flags a take, it never accepts one."""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from film_pipeline.drama.trajectory import judge_motion, motion_curve

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
W, H, FPS, SECONDS = 320, 180, 12, 8
ROI = (0.2, 0.0, 0.8, 1.0)


def _frame(y: float) -> np.ndarray:
    img = np.full((H, W, 3), 128, np.uint8)
    top = int(round(y))
    for row in range(0, 50, 5):           # horizontal stripes: the vertical motion is well defined
        shade = 30 if (row // 5) % 2 == 0 else 230
        img[top + row:top + row + 5, 100:220] = shade
    return img


def make_clip(path: Path, y_of_t) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    assert writer.isOpened()
    for i in range(FPS * SECONDS):
        writer.write(_frame(y_of_t(i / FPS)))
    writer.release()
    return path


def ramp(t, t0, t1, a, b):
    return a + (b - a) * min(1.0, max(0.0, (t - t0) / (t1 - t0)))


def slide_then_hold(t):            # down 20 -> 100 px during 2-4 s, then still
    return ramp(t, 2.0, 4.0, 20, 100)


def slide_past_and_back(t):        # down to 110 during 2-4 s, back up to 40 during 4.2-5.5 s
    return ramp(t, 2.0, 4.0, 20, 110) if t < 4.2 else ramp(t, 4.2, 5.5, 110, 40)


def slide_then_again(t):           # down during 2-4 s (the ACTION window), moves on during the hold at 6-7.5 s
    return ramp(t, 2.0, 4.0, 20, 80) if t < 6 else ramp(t, 6.0, 7.5, 80, 125)


def judged(path, direction="down", action=(2.0, 4.0)):
    curve = motion_curve(path, ROI, "y")
    return judge_motion(curve, direction=direction, action=action)


def names(result):
    return [f["check"] for f in result["findings"]]


def test_slide_then_hold_passes(tmp_path):
    result = judged(make_clip(tmp_path / "a.mp4", slide_then_hold))
    assert names(result) == []
    assert 60 < result["peak"] < 100 and abs(result["final"] - result["peak"]) < 8
    assert 3.0 <= result["peak_t"] <= 8.0


def test_slide_past_a_point_and_back_is_a_reversal(tmp_path):
    result = judged(make_clip(tmp_path / "b.mp4", slide_past_and_back))
    assert "MOTION_REVERSAL" in names(result)
    assert result["peak"] - result["final"] > 0.15 * result["peak"]


def test_motion_during_the_hold_is_outside_the_action(tmp_path):
    result = judged(make_clip(tmp_path / "c.mp4", slide_then_again))
    assert "MOTION_OUTSIDE_ACTION" in names(result)
    assert "MOTION_REVERSAL" not in names(result)


def test_a_still_clip_has_no_motion(tmp_path):
    result = judged(make_clip(tmp_path / "d.mp4", lambda t: 40))
    assert names(result) == ["NO_MOTION"]


def test_the_wrong_declared_direction_is_no_motion(tmp_path):
    result = judged(make_clip(tmp_path / "e.mp4", slide_then_hold), direction="up")
    assert "NO_MOTION" in names(result)


def test_a_pinned_prop_that_goes_up_and_back_is_flagged(tmp_path):
    # film04 SC02_g1 t1: the shutter pinned as unchanged was pushed up at 0.75 s and dropped back at 3 s
    up_and_back = lambda t: ramp(t, 0.75, 1.25, 80, 30) if t < 3 else ramp(t, 3.0, 3.75, 30, 80)  # noqa: E731
    result = judged(make_clip(tmp_path / "f.mp4", up_and_back), direction="still")
    assert names(result) == ["PINNED_PROP_MOVED"] and result["findings"][0]["severity"] == "P0"
    assert result["peak"] > 20 and result["peak_t"] >= 0.75


def test_a_pinned_prop_that_stays_put_passes(tmp_path):
    result = judged(make_clip(tmp_path / "g.mp4", lambda t: 40), direction="still")
    assert names(result) == []


def test_judge_motion_on_a_plain_curve():
    good = [(i / 2, min(i, 10) * 1.0) for i in range(20)]
    assert judge_motion(good, direction="down", action=(0.0, 5.0))["findings"] == []
    mirrored = [(t, -d) for t, d in good]
    assert judge_motion(mirrored, direction="up", action=(0.0, 5.0))["findings"] == []
    back = [(i / 2, 10 - abs(10 - i)) for i in range(21)]
    assert [f["check"] for f in judge_motion(back, direction="down", action=(0.0, 10.0))["findings"]] == ["MOTION_REVERSAL"]


# -- CLI ---------------------------------------------------------------------------------------------------------
def package(tmp_path, tracked):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    if tracked:
        shots["generations"][0]["tracked"] = {"object": "shutter", "roi": list(ROI), "axis": "y", "direction": "down"}
    (root / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    return root


def run_cli(*args):
    done = subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
    return done.returncode, json.loads(done.stdout)


def test_cli_pass_flag_and_error(tmp_path):
    clip = make_clip(tmp_path / "ok.mp4", slide_then_hold)  # SC01_g1's first ACTION phase is 2-6 s
    root = package(tmp_path, tracked=True)
    plot = tmp_path / "curve.png"
    code, out = run_cli("motion", "--film", root, "--gid", "SC01_g1", "--clip", clip, "--plot", plot)
    assert code == 0 and out["verdict"] == "PASS" and out["findings"] == []
    assert "not an acceptance" in out["note"] and plot.is_file()
    back = make_clip(tmp_path / "back.mp4", slide_past_and_back)
    code, out = run_cli("motion", "--film", root, "--gid", "SC01_g1", "--clip", back)
    assert code == 1 and out["verdict"] == "FLAG" and any(f["check"] == "MOTION_REVERSAL" for f in out["findings"])


def test_cli_without_tracked_is_an_error(tmp_path):
    clip = make_clip(tmp_path / "ok.mp4", slide_then_hold)
    code, out = run_cli("motion", "--film", package(tmp_path, tracked=False), "--gid", "SC01_g1", "--clip", clip)
    assert code == 2 and "tracked" in out["error"]


def test_tracked_roi_is_validated():
    from film_pipeline.production.sections import TrackedMotion
    with pytest.raises(ValueError):
        TrackedMotion(object="shutter", roi=(0.6, 0.0, 0.4, 1.0), axis="y", direction="down")
