"""Offline edge-intrusion detector for single-person takes (upgrade plan step 5).

Finds an off-frame person (usually the listener) whose head, hair, shoulder or arm intrudes at the
left/right/bottom frame edge of a shot that declares fewer visible people.

Two feature families, both computed on every sampled frame (default ``analysis_fps`` = 12):

* ``edge_band``: per-frame change of the outer edge strips against the first frame, after compensating
  global camera motion (LK-tracked corners on the frame centre + RANSAC similarity, phase-correlation
  fallback). Only pixels that the reference actually covers are compared, so a pan does not count.
  A side is flagged when the changed fraction of the strip stays above ``band_level`` for at least
  ``min_persist_s`` seconds.
* ``faces``: OpenCV YuNet face boxes (``face_detection_yunet_2023mar.onnx``, OpenCV Zoo, Apache-2.0).
  A face that touches the edge margin and is not the primary subject, or more faces than declared
  visible people, persisting ``min_persist_s``. When the model is missing the detector degrades to the
  edge-band feature and reports ``face_status = "missing_model"``.

Advisory only: the verdict never accepts or rejects a take by itself.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

DETECTOR_NAME = "edge_intrusion"
DETECTOR_VERSION = "1.0.0"
SIGNAL_CODE = "EDGE_INTRUSION_SUSPECT"
ANALYSIS_W, ANALYSIS_H = 320, 180
FACE_W = 320
GRID_ROWS, GRID_COLS = 12, 64   # 15 x 5 px cells at the analysis size
BLOB_BAND = 0.15              # strip analysed for edge-attached blobs
FACE_STRIDE = 2               # faces on every 2nd analysed frame (6 fps at the default 12 fps)
MODEL_ENV = "AFP_YUNET_MODEL"
_DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"


@dataclass(frozen=True)
class Params:
    edge_feature: str = "band"     # "band" | "band_contrast" | "band_onesided" | "blob"
    other_side_weight: float = 1.0  # band_onesided: weight of the opposite strip subtracted per frame
    band_frac: float = 0.08        # strip width as a fraction of the frame width (bottom: of height)
    diff_level: int = 20           # 0-255 gray difference counted as "changed" (20 or 35 are precomputed)
    band_level: float = 0.30       # changed fraction of the strip that counts as intrusion in one frame
    min_persist_s: float = 0.75    # consecutive seconds a side must stay above band_level
    band_rows: float = 1.0         # side strips use the top band_rows of the height (1.0 = full height)
    use_bottom: bool = False
    use_faces: bool = True
    face_score: float = 0.70
    face_edge_margin: float = 0.03  # face box within this fraction of the width from a side edge
    face_min_h: float = 0.10       # face box height as a fraction of the frame height
    score_threshold: float = 1.0   # verdict SUSPECT when score >= this


# Shipped operating point (docs/production/edge_intrusion_calibration_20261120.md): the film08-tuned config,
# which held out on film07 at recall 0.78 / FPR 0.076 and scores recall 0.75 / FPR 0.074 on film08. The
# pre-registered film07-tuned config overfitted (film08 held-out recall 0.75 / FPR 0.214). Targets (recall >= 0.80
# at FPR <= 0.15 on held-out) are not met by either, so triage emits this signal as advisory INFO only.
DEFAULT_PARAMS = Params(
    edge_feature="band_contrast", band_frac=0.04, diff_level=20, band_level=0.325, min_persist_s=0.5,
    band_rows=0.5, use_bottom=False, use_faces=False,
)


def default_face_model_path() -> Path:
    env = os.environ.get(MODEL_ENV, "").strip()
    return Path(env) if env else _DEFAULT_MODEL


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _load_face_detector(model_path: Path | None) -> tuple[Any, str]:
    import cv2

    path = Path(model_path) if model_path is not None else default_face_model_path()
    if not path.is_file():
        return None, "missing_model"
    if not hasattr(cv2, "FaceDetectorYN"):
        return None, "unsupported_opencv"
    try:
        det = cv2.FaceDetectorYN.create(str(path), "", (FACE_W, 180), 0.5, 0.3, 50)
    except Exception:  # noqa: BLE001 - a corrupt model must not break triage
        return None, "load_failed"
    return det, "ok"


def _estimate_increment(cv2: Any, np: Any, prev: Any, cur: Any) -> tuple[Any, int]:
    """Frame-to-frame similarity (prev -> cur) from LK-tracked corners, phase-correlation fallback.

    Corners come from the inner 88% of the width so an intruder in the outer strips does not steer it.
    Implausible increments (|scale-1| > 4%, rotation > 2 deg or > 30 px per analysed frame) fall back to
    a pure translation.
    """
    h, w = prev.shape
    mask = np.zeros_like(prev)
    mask[:, int(w * 0.06):int(w * 0.94)] = 255
    p0 = cv2.goodFeaturesToTrack(prev, 300, 0.01, 6, mask=mask)
    if p0 is not None and len(p0) >= 12:
        p0 = p0.astype(np.float32)
        p1, st, _err = cv2.calcOpticalFlowPyrLK(
            prev, cur, p0, None, winSize=(21, 21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
        )
        ok = st.reshape(-1) == 1
        if ok.sum() >= 12:
            m, inl = cv2.estimateAffinePartial2D(p0[ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=1.0)
            n_in = int(inl.sum()) if inl is not None else 0
            if m is not None and n_in >= 12:
                scale = float(np.hypot(m[0, 0], m[1, 0]))
                rot = abs(float(np.degrees(np.arctan2(m[1, 0], m[0, 0]))))
                if abs(scale - 1.0) <= 0.04 and rot <= 2.0 and abs(m[0, 2]) <= 30 and abs(m[1, 2]) <= 30:
                    return m.astype(np.float32), n_in
    x0, x1 = int(w * 0.2), int(w * 0.8)
    win = cv2.createHanningWindow((x1 - x0, h), cv2.CV_32F)
    (dx, dy), _resp = cv2.phaseCorrelate(np.float32(prev[:, x0:x1]), np.float32(cur[:, x0:x1]), win)
    return np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32), 0


def _cells(np: Any, mask: Any) -> Any:
    h, w = mask.shape
    return mask.reshape(GRID_ROWS, h // GRID_ROWS, GRID_COLS, w // GRID_COLS).sum(axis=(1, 3)).astype(np.float32)


def _edge_blobs(cv2: Any, np: Any, changed: Any) -> list[tuple[float, float, float]]:
    """Largest changed blob touching the outer edge, per side: (area of strip, height frac, depth frac)."""
    h, w = changed.shape
    bw, bh = int(w * BLOB_BAND), int(h * BLOB_BAND)
    kernel = np.ones((3, 3), np.uint8)
    out = []
    for strip in (changed[:, :bw], changed[:, w - bw:][:, ::-1], changed[h - bh:, :][::-1, :].T):
        m = cv2.morphologyEx(strip.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        n, _lab, stats, _c = cv2.connectedComponentsWithStats(m, connectivity=8)
        best = (0.0, 0.0, 0.0)
        sh, sw = strip.shape
        for i in range(1, n):
            x, _y, cw, ch, area = stats[i]
            if x <= 1 and area / (sh * sw) > best[0]:
                best = (area / (sh * sw), ch / sh, cw / sw)
        out.append(best)
    return out


def extract_features(
    clip: Path,
    *,
    analysis_fps: float = 12.0,
    face_model_path: Path | None = None,
    use_faces: bool = True,
) -> dict[str, Any]:
    """Decode the clip densely and return per-frame edge/face features (numpy arrays + metadata)."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        raise ValueError(f"cannot open clip: {clip}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    step = max(1, int(round(src_fps / max(analysis_fps, 1e-3))))
    det, face_status = (_load_face_detector(face_model_path) if use_faces else (None, "disabled"))

    times: list[float] = []
    col20: list[Any] = []
    col35: list[Any] = []
    row20: list[Any] = []
    row35: list[Any] = []
    grid20: list[Any] = []
    grid35: list[Any] = []
    inliers: list[int] = []
    shifts: list[tuple[float, float, float]] = []
    faces: list[Any] = []
    ref = prev = None
    acc = np.eye(3, dtype=np.float32)
    blobs: list[Any] = []
    ones = np.ones((ANALYSIS_H, ANALYSIS_W), np.uint8)
    idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % step:
            continue
        t = idx / src_fps
        small = cv2.resize(frame, (ANALYSIS_W, ANALYSIS_H), interpolation=cv2.INTER_AREA)
        gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        if ref is None:
            ref = gray
            n_in = -1
        else:
            inc, n_in = _estimate_increment(cv2, np, prev, gray)
            acc = np.vstack([inc, [0, 0, 1]]).astype(np.float32) @ acc
        prev = gray
        m = acc[:2]
        warped = cv2.warpAffine(ref, m, (ANALYSIS_W, ANALYSIS_H), flags=cv2.INTER_LINEAR, borderValue=0)
        valid = cv2.warpAffine(ones, m, (ANALYSIS_W, ANALYSIS_H), flags=cv2.INTER_NEAREST, borderValue=0) > 0
        diff = cv2.absdiff(gray, warped)
        vcount_col = np.maximum(valid.sum(axis=0), 1)
        vcount_row = np.maximum(valid.sum(axis=1), 1)
        c20 = ((diff > 20) & valid)
        c35 = ((diff > 35) & valid)
        blobs.append(_edge_blobs(cv2, np, c20))
        col20.append((c20.sum(axis=0) / vcount_col).astype(np.float16))
        col35.append((c35.sum(axis=0) / vcount_col).astype(np.float16))
        row20.append((c20.sum(axis=1) / vcount_row).astype(np.float16))
        row35.append((c35.sum(axis=1) / vcount_row).astype(np.float16))
        vcell = np.maximum(_cells(np, valid), 1)
        grid20.append((_cells(np, c20) / vcell).astype(np.float16))
        grid35.append((_cells(np, c35) / vcell).astype(np.float16))
        inliers.append(n_in)
        scale = float(np.hypot(m[0, 0], m[1, 0]))
        shifts.append((float(m[0, 2]), float(m[1, 2]), scale))
        times.append(t)
        if det is not None and faces and (len(times) - 1) % FACE_STRIDE:
            faces.append(faces[-1])
        elif det is not None:
            fh = int(round(frame.shape[0] * FACE_W / frame.shape[1]))
            fimg = cv2.resize(frame, (FACE_W, fh), interpolation=cv2.INTER_AREA) if frame.shape[1] != FACE_W else frame
            det.setInputSize((FACE_W, fimg.shape[0]))
            _n, res = det.detect(fimg)
            if res is None:
                faces.append(np.zeros((0, 5), np.float32))
            else:
                boxes = res[:, [0, 1, 2, 3, 14]].astype(np.float32)
                boxes[:, [0, 2]] /= FACE_W
                boxes[:, [1, 3]] /= fimg.shape[0]
                faces.append(boxes)  # x, y, w, h (normalised), score
    cap.release()
    if not times:
        raise ValueError(f"no decoded frames in {clip}")
    return {
        "times": np.asarray(times, np.float32),
        "col20": np.stack(col20), "col35": np.stack(col35),
        "row20": np.stack(row20), "row35": np.stack(row35),
        "grid20": np.stack(grid20), "grid35": np.stack(grid35),  # [T, GRID_ROWS, GRID_COLS] changed fraction
        "blobs": np.asarray(blobs, np.float32),  # [T, (left, right, bottom), (area, height, depth)]
        "inliers": np.asarray(inliers, np.int32),
        "motion": np.asarray(shifts, np.float32),
        "faces": faces,
        "face_status": face_status,
        "src_fps": float(src_fps),
        "step": step,
    }


def _persistent_runs(flags: Any, times: Any, min_s: float, dt: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start = None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if (times[i - 1] - times[start]) + dt >= min_s - 1e-6:
                runs.append((start, i - 1))
            start = None
    return runs


def _sliding_min_max(series: Any, n: int) -> float:
    """Highest level the series keeps for n consecutive samples."""
    import numpy as np

    if len(series) == 0:
        return 0.0
    n = max(1, min(n, len(series)))
    win = np.lib.stride_tricks.sliding_window_view(np.asarray(series, np.float32), n)
    return float(win.min(axis=1).max())


def score_features(feat: dict[str, Any], visible_count: int, params: Params = DEFAULT_PARAMS) -> dict[str, Any]:
    """Turn cached features into a scored verdict (pure function, used by calibration and triage)."""
    import numpy as np

    times = np.asarray(feat["times"], np.float32)
    dt = float(feat["step"]) / float(feat["src_fps"])
    n_persist = max(1, int(round(params.min_persist_s / dt)))
    col = np.asarray(feat["col20" if params.diff_level <= 20 else "col35"], np.float32)
    row = np.asarray(feat["row20" if params.diff_level <= 20 else "row35"], np.float32)
    bw = max(1, int(round(ANALYSIS_W * params.band_frac)))
    bh = max(1, int(round(ANALYSIS_H * params.band_frac)))
    if params.edge_feature == "blob":
        blobs = np.asarray(feat["blobs"], np.float32)
        series = {"left": blobs[:, 0, 0], "right": blobs[:, 1, 0]}
        if params.use_bottom:
            series["bottom"] = blobs[:, 2, 0]
    else:
        series = {"left": col[:, :bw].mean(axis=1), "right": col[:, -bw:].mean(axis=1)}
        if params.band_rows < 1.0 and "grid20" in feat:
            # Side strips limited to head height: the subject's own shoulders fill the lower corners of a
            # close single, an off-frame listener's head enters at head height.
            grid = np.asarray(feat["grid20" if params.diff_level <= 20 else "grid35"], np.float32)
            nr = max(1, int(round(GRID_ROWS * params.band_rows)))
            kc = max(1, int(round(GRID_COLS * params.band_frac)))
            series = {"left": grid[:, :nr, :kc].mean(axis=(1, 2)), "right": grid[:, :nr, -kc:].mean(axis=(1, 2))}
            inner_g = {"left": grid[:, :nr, kc:2 * kc].mean(axis=(1, 2)), "right": grid[:, :nr, -2 * kc:-kc].mean(axis=(1, 2))}
        else:
            inner_g = None
        if params.use_bottom:
            series["bottom"] = row[:, -bh:].mean(axis=1)
        if params.edge_feature == "band_contrast":
            inner = {"left": col[:, bw:2 * bw].mean(axis=1), "right": col[:, -2 * bw:-bw].mean(axis=1),
                     "bottom": row[:, -2 * bh:-bh].mean(axis=1)}
            if inner_g is not None:
                inner.update(inner_g)
            series = {k: np.clip(v - 0.5 * inner[k], 0.0, None) for k, v in series.items()}
        elif params.edge_feature == "band_onesided":
            # Camera push-ins and reframes change both side strips; an intruder changes one side.
            raw = dict(series)
            series = {k: np.clip(v - params.other_side_weight * np.maximum.reduce(
                [o for kk, o in raw.items() if kk != k]), 0.0, None) for k, v in raw.items()}

    sides: dict[str, dict[str, Any]] = {}
    for side, s in series.items():
        level = _sliding_min_max(s, n_persist)
        runs = _persistent_runs(s >= params.band_level, times, params.min_persist_s, dt)
        sides[side] = {"edge_level": level, "edge_score": level / max(params.band_level, 1e-6), "runs": runs}

    face_runs: dict[str, list[tuple[int, int]]] = {"left": [], "right": []}
    face_score = 0.0
    if params.use_faces and feat.get("face_status") == "ok":
        flags = {"left": np.zeros(len(times), bool), "right": np.zeros(len(times), bool)}
        primary = None
        for fb in feat["faces"][: max(1, n_persist)]:
            good = [b for b in fb if b[4] >= params.face_score and b[3] >= params.face_min_h]
            if good:
                primary = max(good, key=lambda b: b[2] * b[3])
                break
        for i, fb in enumerate(feat["faces"]):
            good = [b for b in fb if b[4] >= params.face_score and b[3] >= params.face_min_h]
            if not good:
                continue
            main = max(good, key=lambda b: b[2] * b[3]) if primary is None else min(
                good, key=lambda b: abs((b[0] + b[2] / 2) - (primary[0] + primary[2] / 2)))
            for b in good:
                cx = b[0] + b[2] / 2
                extra = len(good) > max(visible_count, 1) and b is not main
                at_left = b[0] <= params.face_edge_margin
                at_right = b[0] + b[2] >= 1.0 - params.face_edge_margin
                if (at_left or at_right) and (b is not main or primary is None or abs(cx - (primary[0] + primary[2] / 2)) > 0.25):
                    extra = True
                if extra:
                    flags["left" if cx < 0.5 else "right"][i] = True
        for side in ("left", "right"):
            face_runs[side] = _persistent_runs(flags[side], times, params.min_persist_s, dt)
            if face_runs[side]:
                face_score = max(face_score, 2.0)

    flagged_sides: list[str] = []
    ranges: list[list[float]] = []
    best = 0.0
    for side, info in sides.items():
        side_score = info["edge_score"]
        runs = list(info["runs"])
        if side in face_runs and face_runs[side]:
            side_score = max(side_score, face_score)
            runs += face_runs[side]
        best = max(best, side_score)
        if side_score >= params.score_threshold and runs:
            flagged_sides.append(side)
            for a, b in runs:
                ranges.append([round(float(times[a]), 2), round(float(times[b]) + dt, 2)])
    ranges.sort()
    merged: list[list[float]] = []
    for r in ranges:
        if merged and r[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], r[1])
        else:
            merged.append(list(r))
    verdict = "SUSPECT" if flagged_sides else "CLEAR"
    return {
        "detector": DETECTOR_NAME,
        "detector_version": DETECTOR_VERSION,
        "verdict": verdict,
        "score": round(float(best), 4),
        "sides": flagged_sides,
        "time_ranges": merged,
        "face_status": feat.get("face_status", "disabled"),
        "frames_analysed": int(len(times)),
        "analysis_fps": round(1.0 / dt, 2),
        "side_levels": {k: round(float(v["edge_level"]), 4) for k, v in sides.items()},
        "params": asdict(params),
    }


def detect_clip(
    clip: Path,
    *,
    visible_count: int = 1,
    params: Params | None = None,
    face_model_path: Path | None = None,
    clip_sha256: str | None = None,
) -> dict[str, Any]:
    """Run the detector on one clip; never raises for a missing face model (degrades to edge-band)."""
    p = params or DEFAULT_PARAMS
    t0 = time.perf_counter()
    feat = extract_features(Path(clip), face_model_path=face_model_path, use_faces=p.use_faces)
    out = score_features(feat, visible_count, p)
    out["clip"] = str(clip)
    out["clip_sha256"] = clip_sha256 or sha256_file(Path(clip))
    out["visible_count"] = int(visible_count)
    out["runtime_s"] = round(time.perf_counter() - t0, 3)
    return out


def make_signal(result: dict[str, Any], take_id: str, severity: str) -> dict[str, Any]:
    """The exact triage signal shape referenced by reviewed-defect records."""
    if severity not in ("WARN", "INFO"):
        raise ValueError(f"severity must be WARN or INFO, got {severity!r}")
    return {
        "code": SIGNAL_CODE,
        "detector": DETECTOR_NAME,
        "detector_version": DETECTOR_VERSION,
        "take_id": take_id,
        "clip_sha256": result["clip_sha256"],
        "sides": list(result["sides"]),
        "time_ranges": [[float(a), float(b)] for a, b in result["time_ranges"]],
        "score": float(result["score"]),
        "severity": severity,
    }


def with_params(**overrides: Any) -> Params:
    return replace(DEFAULT_PARAMS, **overrides)
