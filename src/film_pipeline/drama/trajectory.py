"""Trajectory QC: measure how a moved prop travels in a take (film04 SC01_g1 t9/t10: the shutter overshot and came back).

A measurement for the reviewer, never an acceptance: `judge_motion` returns findings that FLAG a take for a closer look.
Nothing here marks a take as good.

* ``motion_curve``  dense optical flow (Farneback) inside a region of interest; cumulative displacement along one axis.
* ``judge_motion``  signs the curve by the declared direction and checks it for no motion, reversal and motion outside
                    the ACTION window; direction "still" flags any travel of a prop that must not move.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

WIDTH = 320            # frames are resized to this width before the flow is computed
MOVING_PX = 0.3        # flow magnitude above this counts as a moving pixel
MIN_MOVING_FRAC = 0.02  # fewer moving pixels than this share of the ROI = no motion in that step
LEAD_S, TAIL_S = 0.5, 0.75   # slack around the ACTION window before motion counts as outside it
_SIGN = {"down": 1.0, "right": 1.0, "up": -1.0, "left": -1.0}


def motion_curve(clip: Path, roi: tuple[float, float, float, float], axis: Literal["x", "y"],
                 fps: float = 12) -> list[tuple[float, float]]:
    """Cumulative displacement (pixels of the 320-wide frame) along `axis` inside `roi`, per sampled timestamp."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        raise ValueError(f"cannot open {clip}")
    native = cap.get(cv2.CAP_PROP_FPS) or fps
    step = max(1, round(native / fps))
    comp = 0 if axis == "x" else 1
    curve: list[tuple[float, float]] = []
    prev = None
    total = 0.0
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                h, w = frame.shape[:2]
                small = cv2.resize(frame, (WIDTH, max(1, round(h * WIDTH / w))))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                x0, y0, x1, y1 = roi
                sh, sw = gray.shape
                crop = gray[int(y0 * sh):max(int(y0 * sh) + 1, int(y1 * sh)),
                            int(x0 * sw):max(int(x0 * sw) + 1, int(x1 * sw))]
                if prev is not None:
                    flow = cv2.calcOpticalFlowFarneback(prev, crop, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                    mag = np.hypot(flow[..., 0], flow[..., 1])
                    moving = mag > MOVING_PX
                    if moving.mean() >= MIN_MOVING_FRAC:
                        total += float(np.median(flow[..., comp][moving]))
                curve.append((index / native, total))
                prev = crop
            index += 1
    finally:
        cap.release()
    return curve


def judge_still(curve: list[tuple[float, float]], *, min_travel_px: float = 4.0) -> dict:
    """Findings for a prop that must not move: any travel past `min_travel_px` either way (film04 SC02_g1 t1: the
    pinned shutter was pushed up at 0.75 s and dropped back at 3 s; autoqc saw nothing)."""
    if not curve:
        return {"findings": [], "peak_t": 0.0, "peak": 0.0, "final": 0.0, "curve": []}
    peak_t, peak = max(curve, key=lambda p: abs(p[1]))
    findings = []
    if abs(peak) > min_travel_px:
        findings.append({"check": "PINNED_PROP_MOVED", "severity": "P0",
                         "detail": f"a prop pinned as unchanged moved {abs(peak):.1f}px at {peak_t:.1f}s "
                                   f"(final {curve[-1][1]:.1f}px)"})
    return {"findings": findings, "peak_t": round(peak_t, 3), "peak": round(abs(peak), 2),
            "final": round(curve[-1][1], 2), "curve": [(round(t, 3), round(d, 2)) for t, d in curve]}


def judge_motion(curve: list[tuple[float, float]], *, direction: Literal["down", "up", "left", "right", "still"],
                 action: tuple[float, float], reversal_frac: float = 0.15, outside_frac: float = 0.10,
                 min_travel_px: float = 4.0) -> dict:
    """Findings for a displacement curve; the declared direction is positive. FLAG material, not an acceptance."""
    if direction == "still":
        return judge_still(curve, min_travel_px=min_travel_px)
    sign = _SIGN[direction]
    signed = [(t, sign * d) for t, d in curve]
    findings: list[dict[str, str]] = []
    if not signed:
        return {"findings": [{"check": "NO_MOTION", "severity": "P1", "detail": "empty curve"}],
                "peak_t": 0.0, "peak": 0.0, "final": 0.0, "curve": []}
    peak_t, peak = max(signed, key=lambda p: p[1])
    final = signed[-1][1]
    if peak < min_travel_px:
        findings.append({"check": "NO_MOTION", "severity": "P1",
                         "detail": f"peak travel {peak:.1f}px < {min_travel_px:g}px in the declared direction ({direction})"})
    elif peak - final > reversal_frac * peak:
        findings.append({"check": "MOTION_REVERSAL", "severity": "P1",
                         "detail": f"moved past the stop and came back: peak {peak:.1f}px at {peak_t:.1f}s, "
                                   f"final {final:.1f}px"})
    if peak >= min_travel_px:
        before, after = action[0] - LEAD_S, action[1] + TAIL_S
        early = sum(abs(b[1] - a[1]) for a, b in zip(signed, signed[1:]) if b[0] <= before)
        late = sum(abs(b[1] - a[1]) for a, b in zip(signed, signed[1:]) if a[0] >= after)
        if early > outside_frac * peak or late > outside_frac * peak:
            findings.append({"check": "MOTION_OUTSIDE_ACTION", "severity": "P2",
                             "detail": f"travel outside the ACTION window {action[0]:g}-{action[1]:g}s: "
                                       f"{early:.1f}px before, {late:.1f}px after (peak {peak:.1f}px)"})
    return {"findings": findings, "peak_t": round(peak_t, 3), "peak": round(peak, 2), "final": round(final, 2),
            "curve": [(round(t, 3), round(d, 2)) for t, d in curve]}


def plot_curve(curve: list[tuple[float, float]], action: tuple[float, float], out: Path,
               size: tuple[int, int] = (800, 400)) -> None:
    """Draw displacement over time with cv2 (time on x, displacement on y, ACTION window shaded)."""
    import cv2
    import numpy as np

    w, h = size
    img = np.full((h, w, 3), 255, np.uint8)
    if curve:
        ts, ds = [t for t, _ in curve], [d for _, d in curve]
        t_max = max(max(ts), action[1], 1e-6)
        lo, hi = min(0.0, min(ds)), max(0.0, max(ds))
        span = (hi - lo) or 1.0
        left, right, top, bottom = 50, w - 10, 10, h - 30

        def px(t: float, d: float) -> tuple[int, int]:
            return (int(left + (right - left) * t / t_max), int(bottom - (bottom - top) * (d - lo) / span))

        shade = img.copy()
        cv2.rectangle(shade, (px(action[0], lo)[0], top), (px(action[1], lo)[0], bottom), (220, 235, 255), -1)
        img = cv2.addWeighted(shade, 0.8, img, 0.2, 0)
        cv2.line(img, px(0, 0), px(t_max, 0), (180, 180, 180), 1)
        pts = np.array([px(t, d) for t, d in curve], np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [pts], False, (200, 60, 20), 2)
        cv2.putText(img, f"0..{t_max:.1f}s  {lo:.0f}..{hi:.0f}px", (left, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (60, 60, 60), 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
