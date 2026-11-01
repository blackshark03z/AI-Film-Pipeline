"""Automated post-render QC assist (WP4).

These are ASSIST signals: every finding is a WARN, never a BLOCK, and a human
reviewer still decides. Face detection (YuNet) and recognition (SFace) come
from OpenCV; set matching uses ORB + RANSAC. cv2 / numpy are imported lazily
(extra ``qc``) and the ONNX models live outside the repo
(``tools/drama_fetch_qc_models.py``).

Thresholds were calibrated on the film01 clips in
``docs/drama/film01_takes/noref/``: SC01_g1 (identity anchors), the ten
accepted clips SC0{1..5}_g{1,2} (negative controls) and the rejected takes
SC03_g1_rejected_hair / _curly / SC03_g2_rejected_wrong_doyle (known
defects). See ``docs/drama/film01_takes/qc/autoqc_film01.json`` for the
numbers and for what the checks do NOT catch.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from ..core import ContractModel
from .scene_bible import RuleIssue

YUNET_FILE = "face_detection_yunet_2023mar.onnx"
SFACE_FILE = "face_recognition_sface_2021dec.onnx"

# Calibrated thresholds (see module docstring).
# SFace documents 0.363 as the same-person cosine, but film01 renders are
# AI video: accepted clips of the SAME actor score 0.34-0.8 against anchors
# from another clip, the wrong DOYLE scored 0.15 (min 0.08). Thresholds sit
# in the gap (single defect sample, so treat as a coarse floor).
IDENTITY_MEAN_MIN = 0.25
IDENTITY_MIN_MIN = 0.16
PEOPLE_MIN_HEIGHT = 0.05
SCALE_BANDS = (("ECU", 0.50), ("CU", 0.30), ("MCU", 0.18), ("MS", 0.09))
SCALE_ORDER = ("ECU", "CU", "MCU", "MS", "WS")

ShotScale = Literal["ECU", "CU", "MCU", "MS", "WS", "NO_FACE"]
Side = Literal["left", "right", "center"]


# ---------------------------------------------------------------- models

class FaceBox(ContractModel):
    x: float
    y: float
    w: float
    h: float
    score: float
    center_x_norm: float
    height_ratio: float            # h / frame height
    landmarks: list[float] = Field(default_factory=list)   # 5 points, x/y


class IdentityAnchor(ContractModel):
    character: str
    clip: str
    at_s: float
    screen_side: Side
    embedding: list[float]
    head_hist: list[float] = Field(default_factory=list)


class CharacterIdentity(ContractModel):
    character: str
    frames_seen: int
    mean_similarity: float | None = None
    min_similarity: float | None = None
    variance: float | None = None
    mean_head_similarity: float | None = None
    min_head_similarity: float | None = None


class IdentityReport(ContractModel):
    clip: str
    characters: list[CharacterIdentity]
    issues: list[RuleIssue] = Field(default_factory=list)


class ShotScaleReport(ContractModel):
    clip: str
    planned: str
    per_frame: list[str]
    majority: str
    band_distance: int | None = None
    issues: list[RuleIssue] = Field(default_factory=list)


class SetSimilarity(ContractModel):
    orb_inlier_ratio: float
    inliers: int
    good_matches: int
    hsv_correlation: float


class HandoffSetReport(ContractModel):
    previous_clip: str
    next_clip: str
    similarity: SetSimilarity
    issues: list[RuleIssue] = Field(default_factory=list)


class AutoQCReport(ContractModel):
    clip: str
    identity: IdentityReport | None = None
    shot_scale: ShotScaleReport | None = None
    handoff_set: HandoffSetReport | None = None
    issues: list[RuleIssue] = Field(default_factory=list)


# ---------------------------------------------------------- pure logic

def shot_scale_from_ratio(height_ratio: float | None) -> ShotScale:
    """Band the largest face height ratio; ``None`` means no face."""
    if height_ratio is None:
        return "NO_FACE"
    for name, low in SCALE_BANDS:
        if height_ratio > low:
            return name  # type: ignore[return-value]
    return "WS"


def scale_distance(a: str, b: str) -> int | None:
    if a not in SCALE_ORDER or b not in SCALE_ORDER:
        return None
    return abs(SCALE_ORDER.index(a) - SCALE_ORDER.index(b))


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def people_faces(boxes: list[FaceBox]) -> list[FaceBox]:
    """Drop tiny faces (wall portraits, background extras): smaller than
    5% of the frame height or than 40% of the largest face."""
    if not boxes:
        return []
    floor = max(PEOPLE_MIN_HEIGHT, 0.4 * max(b.height_ratio for b in boxes))
    return [b for b in boxes if b.height_ratio >= floor]


def pick_face_on_side(boxes: list[FaceBox], side: str) -> FaceBox | None:
    """Best (largest x score) face on a screen side; centre is |cx-0.5|<0.15."""
    def ok(b: FaceBox) -> bool:
        if side == "left":
            return b.center_x_norm < 0.5
        if side == "right":
            return b.center_x_norm >= 0.5
        return abs(b.center_x_norm - 0.5) < 0.15
    cands = [b for b in boxes if ok(b)]
    return max(cands, key=lambda b: b.score * b.h, default=None)


def assign_faces_by_side(boxes: list[FaceBox], side_of: dict[str, str]
                         ) -> dict[str, FaceBox]:
    """Character -> face by screen side. Needs >= 2 faces: a lone face is
    ambiguous (over-the-shoulder shots) and is left to the caller, which
    matches it against the anchors. With more faces than characters the
    biggest face on each side wins; one face is never given to two."""
    if len(boxes) < 2:
        return {}
    out: dict[str, FaceBox] = {}
    for who, side in side_of.items():
        face = pick_face_on_side(boxes, side)
        if face is not None and all(face is not f for f in out.values()):
            out[who] = face
    return out


# ------------------------------------------------------------- models/io

def models_dir() -> Path:
    env = os.environ.get("FILM_PIPELINE_MODELS")
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    return Path(base) / "film_pipeline" / "models"


def _model_path(name: str) -> Path:
    path = models_dir() / name
    if not path.is_file():
        raise FileNotFoundError(
            f"QC model {name} not found in {models_dir()}; run "
            "`python tools/drama_fetch_qc_models.py` (needs extra `qc`)")
    return path


def models_available() -> bool:
    try:
        _model_path(YUNET_FILE), _model_path(SFACE_FILE)
        return True
    except FileNotFoundError:
        return False


_CACHE: dict[str, Any] = {}


def _detector():
    import cv2
    if "yunet" not in _CACHE:
        _CACHE["yunet"] = cv2.FaceDetectorYN.create(
            str(_model_path(YUNET_FILE)), "", (320, 320), 0.7, 0.3, 50)
    return _CACHE["yunet"]


def _recognizer():
    import cv2
    if "sface" not in _CACHE:
        _CACHE["sface"] = cv2.FaceRecognizerSF.create(
            str(_model_path(SFACE_FILE)), "")
    return _CACHE["sface"]


# ---------------------------------------------------------------- frames

def _open(clip: Path):
    import cv2
    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        raise OSError(f"cannot open {clip}")
    return cap


def _read_at(cap, index: int):
    import cv2
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(index, 0))
    ok, frame = cap.read()
    return frame if ok else None


def clip_duration(clip: Path) -> float:
    import cv2
    cap = _open(clip)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        return cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    finally:
        cap.release()


def frame_at(clip: Path, at_s: float):
    import cv2
    cap = _open(clip)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        frame = _read_at(cap, int(round(at_s * fps)))
    finally:
        cap.release()
    if frame is None:
        raise OSError(f"no frame at {at_s}s in {clip}")
    return frame


def sample_frames(clip: Path, n: int = 8, *, start_s: float = 0.0,
                  end_s: float | None = None) -> list:
    """``n`` frames at the centres of equal slices of [start_s, end_s]."""
    import cv2
    cap = _open(clip)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        end = min(end_s if end_s is not None else total / fps, total / fps)
        frames = []
        for i in range(n):
            t = start_s + (end - start_s) * (i + 0.5) / n
            frame = _read_at(cap, int(t * fps))
            if frame is not None:
                frames.append(frame)
        return frames
    finally:
        cap.release()


def first_frame(clip: Path):
    return frame_at(clip, 0.0)


def last_frame(clip: Path):
    import cv2
    cap = _open(clip)
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for back in range(1, 12):
            frame = _read_at(cap, total - back)
            if frame is not None:
                return frame
    finally:
        cap.release()
    raise OSError(f"no last frame in {clip}")


# ----------------------------------------------------------------- faces

def detect_faces(frame, *, min_score: float = 0.7) -> list[FaceBox]:
    height, width = frame.shape[:2]
    det = _detector()
    det.setInputSize((width, height))
    det.setScoreThreshold(min_score)
    _, rows = det.detect(frame)
    boxes = []
    for r in [] if rows is None else rows:
        x, y, w, h = (float(v) for v in r[:4])
        boxes.append(FaceBox(
            x=x, y=y, w=w, h=h, score=float(r[14]),
            center_x_norm=(x + w / 2) / width, height_ratio=h / height,
            landmarks=[float(v) for v in r[4:14]]))
    return sorted(boxes, key=lambda b: b.x)


def _face_row(box: FaceBox):
    import numpy as np
    return np.array([box.x, box.y, box.w, box.h, *box.landmarks, box.score],
                    dtype=np.float32)


def face_embedding(frame, box: FaceBox) -> list[float]:
    rec = _recognizer()
    aligned = rec.alignCrop(frame, _face_row(box))
    return [float(v) for v in rec.feature(aligned).flatten()]


# ------------------------------------------------------- head / hair crop

def _head_crop(frame, box: FaceBox):
    """Hair strip: from 0.8 face heights above the box to the brow line."""
    height, width = frame.shape[:2]
    x0 = int(max(box.x - 0.2 * box.w, 0))
    x1 = int(min(box.x + 1.2 * box.w, width))
    y0 = int(max(box.y - 0.8 * box.h, 0))
    y1 = int(min(box.y + 0.1 * box.h, height))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return frame[y0:y1, x0:x1]


def head_histogram(frame, box: FaceBox) -> list[float]:
    """Colour (HSV) + gradient-orientation histogram of the hair strip."""
    import cv2
    import numpy as np
    crop = _head_crop(frame, box)
    if crop is None:
        return []
    crop = cv2.resize(crop, (64, 48))
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    col = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 8],
                       [0, 180, 0, 256, 0, 256]).flatten()
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    mag, ang = cv2.cartToPolar(gx, gy)
    tex, _ = np.histogram(ang, bins=12, range=(0, 2 * np.pi), weights=mag)
    col = col / max(col.sum(), 1e-9)
    tex = tex / max(tex.sum(), 1e-9)
    return [float(v) for v in np.concatenate([col, tex])]


def head_region_similarity(hist_a: list[float], hist_b: list[float]
                           ) -> float:
    """Histogram intersection of the colour part + texture part (0..1)."""
    if not hist_a or not hist_b:
        return 0.0
    n = 8 * 4 * 8
    col = sum(min(a, b) for a, b in zip(hist_a[:n], hist_b[:n]))
    tex = sum(min(a, b) for a, b in zip(hist_a[n:], hist_b[n:]))
    return 0.5 * col + 0.5 * tex


# --------------------------------------------------------------- identity

def anchor_from_clip(character: str, clip: Path, at_s: float, side: Side
                     ) -> IdentityAnchor:
    frame = frame_at(clip, at_s)
    box = pick_face_on_side(people_faces(detect_faces(frame)), side)
    if box is None:
        raise ValueError(f"no face on the {side} side of {clip} at {at_s}s")
    return IdentityAnchor(
        character=character, clip=str(clip), at_s=at_s, screen_side=side,
        embedding=face_embedding(frame, box),
        head_hist=head_histogram(frame, box))


def _stats(values: list[float]) -> tuple[float, float, float]:
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, min(values), var


def identity_report(clip: Path, anchors: list[IdentityAnchor], *,
                    side_of: dict[str, str], n: int = 8,
                    mean_min: float = IDENTITY_MEAN_MIN,
                    min_min: float = IDENTITY_MIN_MIN,
                    window: tuple[float, float] | None = None
                    ) -> IdentityReport:
    by_char: dict[str, list[IdentityAnchor]] = {}
    for a in anchors:
        by_char.setdefault(a.character, []).append(a)
    sims: dict[str, list[float]] = {c: [] for c in by_char}
    heads: dict[str, list[float]] = {c: [] for c in by_char}

    def score(who: str, emb: list[float], hist: list[float]):
        sims[who].append(max(cosine(emb, a.embedding) for a in by_char[who]))
        if hist:
            heads[who].append(max(head_region_similarity(hist, a.head_hist)
                                  for a in by_char[who] if a.head_hist))

    kw = {} if window is None else {"start_s": window[0], "end_s": window[1]}
    for frame in sample_frames(clip, n, **kw):
        boxes = people_faces(detect_faces(frame))
        assigned = assign_faces_by_side(
            boxes, {c: s for c, s in side_of.items() if c in by_char})
        if assigned:
            for who, box in assigned.items():
                score(who, face_embedding(frame, box),
                      head_histogram(frame, box))
        elif len(boxes) == 1:
            box = boxes[0]
            emb = face_embedding(frame, box)
            best = max(by_char, key=lambda c: max(
                cosine(emb, a.embedding) for a in by_char[c]))
            score(best, emb, head_histogram(frame, box))

    chars, issues = [], []
    for who in by_char:
        if not sims[who]:
            chars.append(CharacterIdentity(character=who, frames_seen=0))
            continue
        mean, low, var = _stats(sims[who])
        h = heads[who]
        chars.append(CharacterIdentity(
            character=who, frames_seen=len(sims[who]), mean_similarity=mean,
            min_similarity=low, variance=var,
            mean_head_similarity=sum(h) / len(h) if h else None,
            min_head_similarity=min(h) if h else None))
        if mean < mean_min or low < min_min:
            issues.append(RuleIssue(
                check="IDENTITY_DRIFT", severity="WARN",
                detail=f"{who}: mean {mean:.2f} (min {mean_min}), "
                       f"lowest {low:.2f} (min {min_min}) in {clip.name}"))
    return IdentityReport(clip=str(clip), characters=chars, issues=issues)


# ------------------------------------------------------------- shot scale

def shot_scale(frame) -> ShotScale:
    boxes = detect_faces(frame)
    return shot_scale_from_ratio(
        max((b.height_ratio for b in boxes), default=None))


def judge_scale(planned: str, per_frame: list[str]
                ) -> tuple[str, int | None]:
    """Majority scale (faces only unless none) and its band distance."""
    seen = [s for s in per_frame if s != "NO_FACE"]
    pool = seen or per_frame
    majority = max(set(pool), key=lambda s: (pool.count(s),
                                             -SCALE_ORDER.index(s)
                                             if s in SCALE_ORDER else 0))
    if majority == "NO_FACE":
        # no face found: only a wide plan is compatible
        return majority, 0 if planned == "WS" else None
    return majority, scale_distance(planned, majority)


def shot_scale_report(clip: Path, planned: str, n: int = 8, *,
                      window: tuple[float, float] | None = None
                      ) -> ShotScaleReport:
    kw = {} if window is None else {"start_s": window[0], "end_s": window[1]}
    per_frame = [shot_scale(f) for f in sample_frames(clip, n, **kw)]
    majority, dist = judge_scale(planned, per_frame)
    issues = []
    if dist is None or dist > 1:
        issues.append(RuleIssue(
            check="SHOT_SCALE_MISMATCH", severity="WARN",
            detail=f"planned {planned}, rendered {majority} in {clip.name}"))
    return ShotScaleReport(clip=str(clip), planned=planned,
                           per_frame=list(per_frame), majority=majority,
                           band_distance=dist, issues=issues)


# -------------------------------------------------------------- set match

def _background_mask(frame, boxes: list[FaceBox]):
    """255 where background; people masked from 0.3 heads above the face,
    2.2 face-widths wide, down to the frame bottom."""
    import numpy as np
    height, width = frame.shape[:2]
    mask = np.full((height, width), 255, dtype=np.uint8)
    for b in boxes:
        x0 = int(max(b.x + b.w / 2 - 1.1 * b.w, 0))
        x1 = int(min(b.x + b.w / 2 + 1.1 * b.w, width))
        y0 = int(max(b.y - 0.3 * b.h, 0))
        mask[y0:height, x0:x1] = 0
    return mask


def set_similarity(frame_a, frame_b) -> SetSimilarity:
    import cv2
    import numpy as np
    mask_a = _background_mask(frame_a, detect_faces(frame_a, min_score=0.5))
    mask_b = _background_mask(frame_b, detect_faces(frame_b, min_score=0.5))
    orb = cv2.ORB_create(nfeatures=2000)
    ga = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
    ka, da = orb.detectAndCompute(ga, mask_a)
    kb, db = orb.detectAndCompute(gb, mask_b)
    good, inliers = [], 0
    if da is not None and db is not None and len(ka) >= 4 and len(kb) >= 4:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        for pair in matcher.knnMatch(da, db, k=2):
            if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance:
                good.append(pair[0])
    if len(good) >= 4:
        src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        _, inl = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        inliers = int(inl.sum()) if inl is not None else 0
    hists = []
    for frame, mask in ((frame_a, mask_a), (frame_b, mask_b)):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], mask, [30, 32], [0, 180, 0, 256])
        hists.append(cv2.normalize(hist, hist).flatten())
    corr = float(cv2.compareHist(hists[0], hists[1], cv2.HISTCMP_CORREL))
    return SetSimilarity(
        orb_inlier_ratio=inliers / len(good) if good else 0.0,
        inliers=inliers, good_matches=len(good), hsv_correlation=corr)


# film01 within-scene handoffs gave 6-11 RANSAC inliers, unrelated shots 0-2.
# Only "no shared structure at all" is flagged; the SC03 drift was not (11).
SET_MIN_INLIERS = 4


def handoff_set_report(prev_clip: Path, next_clip: Path, *,
                       min_inliers: int | None = None) -> HandoffSetReport:
    sim = set_similarity(last_frame(prev_clip), first_frame(next_clip))
    issues = []
    floor = SET_MIN_INLIERS if min_inliers is None else min_inliers
    if sim.inliers < floor:
        issues.append(RuleIssue(
            check="SET_DRIFT", severity="WARN",
            detail=f"background match {sim.inliers} inliers (min {floor}), "
                   f"hsv {sim.hsv_correlation:.2f}: {prev_clip.name} -> "
                   f"{next_clip.name}"))
    return HandoffSetReport(previous_clip=str(prev_clip),
                            next_clip=str(next_clip), similarity=sim,
                            issues=issues)


def run_autoqc(clip: Path, *, anchors: list[IdentityAnchor] | None = None,
               side_of: dict[str, str] | None = None,
               planned_scale: str | None = None,
               previous_clip: Path | None = None, n: int = 8
               ) -> AutoQCReport:
    report = AutoQCReport(clip=str(clip))
    if anchors:
        report.identity = identity_report(clip, anchors,
                                          side_of=side_of or {}, n=n)
        report.issues += report.identity.issues
    if planned_scale:
        report.shot_scale = shot_scale_report(clip, planned_scale, n)
        report.issues += report.shot_scale.issues
    if previous_clip is not None:
        report.handoff_set = handoff_set_report(previous_clip, clip)
        report.issues += report.handoff_set.issues
    return report
