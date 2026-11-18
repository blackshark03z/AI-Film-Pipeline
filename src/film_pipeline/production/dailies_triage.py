"""Advisory Pre-Dailies Triage Scanner (168 categories 133-138, informed by R44).

Computes non-authoritative technical triage metrics on a generated take MP4:
1. Edge-intrusion delta (left/right 8% vertical strips vs first frame / start still).
2. Bottom-right corner mark signal (variance in the 12% x 12% Gemini sparkle corner).
3. Gap-aware border camera stability (R44F signal for STATIC camera declarations).
4. Audio speech-activity trim hint (dead-air lead/tail + active speech ratio).

HARD INVARIANT: ``triage_take`` NEVER writes review files and NEVER auto-PASSes any human QC group.
"""
from __future__ import annotations

import math
import statistics
import subprocess
from pathlib import Path
from typing import Any

from film_pipeline.production.mix import _frames_db

AN_W, AN_H = 64, 36
EDGE_COLS = 5       # ~8% of 64px width on left and right
CORNER_COLS = 8     # bottom-right ~12.5% width
CORNER_ROWS = 5     # bottom-right ~13.9% height


def _probe_duration_s(clip: Path) -> float:
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True, check=True, timeout=60,
    )
    return float((done.stdout or "0").strip() or 0.0)


def _gray_frames(media: Path, *, max_frames: int = 12, duration_s: float | None = None) -> list[bytes]:
    frame_bytes = AN_W * AN_H
    scale_vf = f"scale={AN_W}:{AN_H}:flags=area,format=gray"
    if duration_s is not None and duration_s > 0.2 and max_frames > 1:
        head_budget = max_frames - 1
        fps_expr = f"fps={max(0.05, head_budget / duration_s):.4f}"
        vf = f"{fps_expr},{scale_vf}"
        head_raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(media), "-an", "-vf", vf,
             "-frames:v", str(head_budget), "-f", "rawvideo", "-"],
            capture_output=True, check=True, timeout=60,
        ).stdout
        tail_proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-sseof", "-0.1", "-i", str(media), "-an", "-vf", scale_vf,
             "-frames:v", "1", "-f", "rawvideo", "-"],
            capture_output=True, check=False, timeout=60,
        )
        tail_raw = tail_proc.stdout if tail_proc.returncode == 0 and len(tail_proc.stdout) >= frame_bytes else b""
        if not tail_raw:
            tail_seek = max(0.0, duration_s - 0.1)
            tail_raw = subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", f"{tail_seek:.3f}", "-i", str(media), "-an", "-vf", scale_vf,
                 "-frames:v", "1", "-f", "rawvideo", "-"],
                capture_output=True, check=False, timeout=60,
            ).stdout
        frames = [head_raw[i * frame_bytes:(i + 1) * frame_bytes] for i in range(len(head_raw) // frame_bytes)]
        if len(tail_raw) >= frame_bytes:
            frames.append(tail_raw[:frame_bytes])
        return frames
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(media), "-an", "-vf", scale_vf,
         "-frames:v", str(max_frames), "-f", "rawvideo", "-"],
        capture_output=True, check=True, timeout=60,
    ).stdout
    count = len(raw) // frame_bytes
    return [raw[i * frame_bytes:(i + 1) * frame_bytes] for i in range(count)]


def _region_mean_abs_diff(a: bytes, b: bytes, cols: range, rows: range) -> float:
    total = 0.0
    n = 0
    for y in rows:
        base = y * AN_W
        for x in cols:
            total += abs(a[base + x] - b[base + x])
            n += 1
    return total / max(n, 1)


def _corner_std(frame: bytes) -> float:
    vals = [
        frame[y * AN_W + x]
        for y in range(AN_H - CORNER_ROWS, AN_H)
        for x in range(AN_W - CORNER_COLS, AN_W)
    ]
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return math.sqrt(var)


def _reference_still(pkg: Any, decl: Any) -> Path | None:
    if decl is None or getattr(decl, "previous_generation_id", None):
        return None
    pre = pkg.typed.get("preprod") if hasattr(pkg, "typed") else None
    if pre is None:
        return None
    rec = pre.stills.get(decl.generation_id)
    if rec is None:
        return None
    path = Path(pkg.root) / rec.file
    return path if path.is_file() else None


def triage_take(pkg: Any, take_id: str, *, clips_dir: Path | None = None) -> dict[str, Any]:
    """Scan one generated take clip and emit assist-only QC metrics & WARN alerts (never bypasses human QC)."""
    from film_pipeline.production.takes import load_log, sha256_file

    root = Path(pkg.root)
    log = load_log(root, pkg.header.film_id)
    entry = log.get(take_id)
    base_dir = Path(clips_dir) if clips_dir is not None else root / "media" / "takes"
    clip = base_dir / entry.output_file
    if not clip.is_file():
        raise FileNotFoundError(f"Take clip not found for triage: {clip}")
    actual_sha = sha256_file(clip)
    hash_verified = not entry.output_sha256 or actual_sha == entry.output_sha256

    shots = pkg.typed.get("shots") if hasattr(pkg, "typed") else None
    decl = next((g for g in shots.generations if g.generation_id == entry.generation_id), None) if shots else None
    duration_s = _probe_duration_s(clip)
    frames = _gray_frames(clip, max_frames=12, duration_s=duration_s)
    if not frames:
        raise ValueError(f"No decoded video frames found in {clip}")

    still_path = _reference_still(pkg, decl)
    ref_frame = frames[0]
    if still_path is not None:
        still_frames = _gray_frames(still_path, max_frames=1)
        if still_frames:
            ref_frame = still_frames[0]

    left_cols = range(0, EDGE_COLS)
    right_cols = range(AN_W - EDGE_COLS, AN_W)
    center_cols = range(12, AN_W - 12)
    all_rows = range(0, AN_H)

    left_deltas = [_region_mean_abs_diff(ref_frame, f, left_cols, all_rows) for f in frames]
    right_deltas = [_region_mean_abs_diff(ref_frame, f, right_cols, all_rows) for f in frames]
    center_deltas = [_region_mean_abs_diff(ref_frame, f, center_cols, all_rows) for f in frames]

    max_left = max(left_deltas)
    max_right = max(right_deltas)
    med_center = statistics.median(center_deltas)

    corner_stds = [_corner_std(f) for f in frames]
    med_corner_std = statistics.median(corner_stds)

    # Border motion for R44F camera stability
    border_deltas: list[float] = []
    for a, b in zip(frames, frames[1:]):
        top = _region_mean_abs_diff(a, b, range(0, AN_W), range(0, 4))
        left = _region_mean_abs_diff(a, b, range(0, 4), all_rows)
        right = _region_mean_abs_diff(a, b, range(AN_W - 4, AN_W), all_rows)
        border_deltas.append((top + left + right) / 3.0)
    med_border = statistics.median(border_deltas) if border_deltas else 0.0
    max_border = max(border_deltas) if border_deltas else 0.0

    # Audio speech activity for leading/trailing trim hints
    hop_s = 0.05
    try:
        dbs = _frames_db(clip, hop_s=hop_s)
    except (subprocess.CalledProcessError, OSError):
        dbs = []
    active = [db > -45.0 for db in dbs]
    active_count = sum(1 for v in active if v)
    active_ratio = active_count / len(active) if active else 0.0
    if active_count > 0:
        first_idx = next(i for i, v in enumerate(active) if v)
        last_idx = len(active) - 1 - next(i for i, v in enumerate(reversed(active)) if v)
        lead_silence = round(first_idx * hop_s, 3)
        tail_silence = round(max(0.0, duration_s - (last_idx + 1) * hop_s), 3)
        sug_in = round(max(0.0, first_idx * hop_s - 0.15), 3)
        sug_out = round(min(duration_s, (last_idx + 1) * hop_s + 0.15), 3)
    else:
        lead_silence = round(duration_s, 3)
        tail_silence = round(duration_s, 3)
        sug_in = 0.0
        sug_out = round(duration_s, 3)

    warnings: list[dict[str, Any]] = []
    if max(max_left, max_right) >= 25.0 and (max(max_left, max_right) >= med_center * 1.4 or max(max_left, max_right) >= 35.0):
        side = "left" if max_left >= max_right else "right"
        warnings.append({
            "code": "EDGE_INTRUSION_RISK",
            "severity": "WARN",
            "detail": f"frame-{side} 8% strip shifted sharply vs baseline (left={max_left:.1f}, right={max_right:.1f}, center_med={med_center:.1f})",
        })
    if med_corner_std < 4.5:
        warnings.append({
            "code": "CORNER_MARK_LOW_SIGNAL",
            "severity": "WARN",
            "detail": f"bottom-right corner region shows very low texture contrast (median std={med_corner_std:.2f}); inspect watermark preservation",
        })
    cam_move = decl.camera.movement if decl is not None and decl.camera is not None else ""
    if cam_move == "STATIC" and max_border >= 18.0:
        warnings.append({
            "code": "CAMERA_JITTER_SPIKE",
            "severity": "WARN",
            "detail": f"STATIC camera border jump spike max={max_border:.1f} (median={med_border:.1f})",
        })
    if decl is not None and decl.dialogue and active_ratio < 0.08:
        warnings.append({
            "code": "SPEECH_ACTIVITY_LOW",
            "severity": "WARN",
            "detail": f"dialogue shot has only {active_ratio:.1%} audio frames above -45 dBFS; verify spoken line",
        })
    if not hash_verified:
        warnings.append({
            "code": "TAKE_HASH_MISMATCH",
            "severity": "WARN",
            "detail": f"clip sha256 {actual_sha[:12]} differs from logged output_sha256 {entry.output_sha256[:12]}",
        })

    return {
        "take_id": take_id,
        "generation_id": entry.generation_id,
        "clip": str(clip),
        "output_sha256": actual_sha,
        "hash_verified": hash_verified,
        "duration_s": round(duration_s, 3),
        "advisory_only": True,
        "auto_pass_forbidden": True,
        "metrics": {
            "frames_sampled": len(frames),
            "baseline": "start_still" if still_path is not None else "frame_0",
            "left_edge_max_delta": round(max_left, 2),
            "right_edge_max_delta": round(max_right, 2),
            "center_median_delta": round(med_center, 2),
            "corner_mark_median_std": round(med_corner_std, 2),
            "border_median_delta": round(med_border, 2),
            "border_max_delta": round(max_border, 2),
            "speech_active_ratio": round(active_ratio, 3),
            "leading_silence_s": lead_silence,
            "trailing_silence_s": tail_silence,
            "suggested_src_in_s": sug_in,
            "suggested_src_out_s": sug_out,
        },
        "warnings": warnings,
    }
