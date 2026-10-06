"""AI-FILM-QUALITY-V2-010C — slider-captcha gap solver (PIL, no OpenCV).

Port of the Owner's live-proven Story Auto approach (find_gap_x via template
match) to a PIL-only implementation. Best-effort: on low confidence the
caller must stop for the operator instead of forcing a retry.
"""
from __future__ import annotations

import io
from PIL import Image


def _edge_profile(im: Image.Image) -> list[float]:
    gray = im.convert("L")
    w, h = gray.size
    px = gray.load()
    # vertical-gradient magnitude per column = vertical-edge density
    profile = [0.0] * w
    for x in range(1, w):
        total = 0
        for y in range(0, h, 2):
            total += abs(px[x, y] - px[x - 1, y])
        profile[x] = total / max(1, h // 2)
    return profile


def find_gap_x(bg_bytes: bytes, piece_bytes: bytes) -> tuple[int, float]:
    """Locate the notch x-position (bg pixel space) of the slider puzzle.

    Returns (gap_x, confidence). Confidence is heuristic: the sharpness of
    the best column-candidate edge alignment versus the median.
    """
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
    piece = Image.open(io.BytesIO(piece_bytes)).convert("RGBA")
    piece = piece.crop(piece.getbbox())  # trim transparent margin
    pw, ph = piece.size
    # piece alpha tells where the actual puzzle shape is
    alpha = piece.split()[3]
    a_px = alpha.load()
    a_w, a_h = alpha.size
    col_has_shape = [any(a_px[x, y] > 40 for y in range(0, a_h, 3))
                     for x in range(a_w)]
    piece_edges = piece.convert("L")
    p_px = piece_edges.load()
    p_profile = [0.0] * a_w
    for x in range(1, a_w):
        if not col_has_shape[x]:
            continue
        total = 0
        for y in range(0, a_h, 2):
            if col_has_shape[x] and col_has_shape[x - 1]:
                total += abs(p_px[x, y] - p_px[x - 1, y])
        p_profile[x] = total / max(1, a_h // 2)

    bg_edges = bg.convert("L")
    b_px = bg_edges.load()
    bw, bh = bg_edges.size
    b_profile = [0.0] * bw
    for x in range(1, bw):
        total = 0
        for y in range(0, bh, 2):
            total += abs(b_px[x, y] - b_px[x - 1, y])
        b_profile[x] = total / max(1, bh // 2)

    # slide the piece edge-profile over the background edge profile; the
    # notch is where piece VERTICAL edges align with strong bg VERTICAL edges
    best_x, best_score, scores = 0, -1.0, []
    for offset in range(0, bw - a_w):
        score = 0.0
        count = 0
        for x in range(2, a_w - 2, 2):
            if not col_has_shape[x]:
                continue
            score += p_profile[x] * b_profile[offset + x]
            count += 1
        score = score / max(1, count)
        scores.append(score)
        if score > best_score:
            best_score, best_x = score, offset
    ranked = sorted(scores, reverse=True)
    median = ranked[len(ranked) // 2] if ranked else 0.0
    confidence = 0.0
    if median > 0:
        confidence = min(1.0, (best_score - median) / (median + 1e-6))
    return best_x, confidence
