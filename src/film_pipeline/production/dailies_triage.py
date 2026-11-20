"""Advisory Pre-Dailies Triage Scanner (168 categories 133-138, informed by R44).

Computes non-authoritative technical triage metrics on a generated take MP4:
1. Edge-intrusion delta (left/right 8% vertical strips vs first frame / start still).
2. Bottom-right corner mark signal (variance in the 12% x 12% Gemini sparkle corner).
3. Gap-aware border camera stability (R44F signal for STATIC camera declarations).
4. Audio speech-activity trim hint (dead-air lead/tail + active speech ratio).
5. Dense edge-intrusion detector (``edge_intrusion``) on single-visible takes -> ``EDGE_INTRUSION_SUSPECT`` signal.

HARD INVARIANT: ``triage_take`` NEVER writes review files and NEVER auto-PASSes any human QC group.
"""
from __future__ import annotations

import array
from concurrent.futures import ThreadPoolExecutor
import json
import math
import statistics
import subprocess
from pathlib import Path
from typing import Any

from film_pipeline.production.ffjoin import render_workers
from film_pipeline.production.runtime import atomic_json

AN_W, AN_H = 64, 36
EDGE_COLS = 5       # ~8% of 64px width on left and right
CORNER_COLS = 8     # bottom-right ~12.5% width
CORNER_ROWS = 5     # bottom-right ~13.9% height
TRIAGE_CACHE_VERSION = 3
# Calibration (docs/production/edge_intrusion_calibration_20261120.md): held-out targets recall >= 0.80 at
# FPR <= 0.15 were NOT met, so the signal is advisory INFO (never WARN, never an auto-reject).
EDGE_INTRUSION_SEVERITY = "INFO"
EDGE_INTRUSION_NOTE = (
    "advisory only: calibrated recall 0.78 / FPR 0.076 (film07 held-out) and 0.75 / 0.074 (film08); "
    "targets 0.80 / 0.15 not met; inspect the flagged edge and time range, the reviewer decides"
)


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
    if decl is None or (getattr(decl, "previous_generation_id", None) and not getattr(decl, "independent_still", False)):
        return None
    pre = pkg.typed.get("preprod") if hasattr(pkg, "typed") else None
    if pre is None:
        return None
    rec = pre.stills.get(decl.generation_id)
    if rec is None:
        return None
    path = Path(pkg.root) / rec.file
    return path if path.is_file() else None


def _audio_triage_stats(clip: Path, *, hop_s: float = 0.05) -> tuple[list[float], int]:
    """Single-pass 8 kHz mono s16le decode returning `(rms_dbfs_per_hop, peak_abs_sample)`."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        capture_output=True, check=True, timeout=60,
    ).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) // 2 * 2])
    if not samples:
        return [], 0
    peak = max(abs(max(samples)), abs(min(samples)))
    hop = max(1, int(8000 * hop_s))
    dbs: list[float] = []
    for i in range(0, len(samples) - hop + 1, hop):
        window = samples[i:i + hop]
        mean_sq = sum(v * v for v in window) / hop
        dbs.append(-120.0 if mean_sq <= 0 else max(-120.0, 10.0 * math.log10(mean_sq / 32768.0 ** 2)))
    return dbs, peak


def _edge_intrusion_signal(
    take_id: str,
    clip: Path,
    clip_sha: str,
    decl: Any,
    signals: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run the dense edge-intrusion detector on single-visible takes; append its signal when SUSPECT."""
    visible = list(getattr(decl, "visible", None) or []) if decl is not None else []
    if len(visible) != 1:
        return {"status": "skipped", "reason": f"visible count {len(visible)} (detector runs on single-visible takes)"}
    try:
        from film_pipeline.production import edge_intrusion as EI
    except ImportError as exc:  # numpy/opencv are the optional "qc" extra
        return {"status": "unavailable", "reason": str(exc)[:160]}
    try:
        res = EI.detect_clip(clip, visible_count=1, clip_sha256=clip_sha)
    except Exception as exc:  # noqa: BLE001 - advisory scanner must not break triage
        return {"status": "error", "reason": str(exc)[:160]}
    if res["verdict"] == "SUSPECT":
        sig = EI.make_signal(res, take_id, EDGE_INTRUSION_SEVERITY)
        signals.append(sig)
        if EDGE_INTRUSION_SEVERITY == "WARN":
            warnings.append(sig)
    return {
        "status": "ok",
        "detector": res["detector"],
        "detector_version": res["detector_version"],
        "verdict": res["verdict"],
        "score": res["score"],
        "sides": res["sides"],
        "time_ranges": res["time_ranges"],
        "face_status": res["face_status"],
        "analysis_fps": res["analysis_fps"],
        "frames_analysed": res["frames_analysed"],
        "runtime_s": res["runtime_s"],
        "severity": EDGE_INTRUSION_SEVERITY,
        "message": EDGE_INTRUSION_NOTE,
    }


def triage_cache_path(root: Path, take_id: str) -> Path:
    return Path(root) / "media" / "triage" / f"{take_id}.json"


def load_cached_triage(root: Path, take_id: str, expected_sha256: str) -> dict[str, Any] | None:
    if not expected_sha256:
        return None
    cpath = triage_cache_path(root, take_id)
    if not cpath.is_file():
        return None
    try:
        doc = json.loads(cpath.read_text(encoding="utf-8"))
        if (
            isinstance(doc, dict)
            and doc.get("triage_cache_version") == TRIAGE_CACHE_VERSION
            and doc.get("output_sha256") == expected_sha256
            and isinstance(doc.get("warnings"), list)
        ):
            return doc
    except (OSError, ValueError):
        pass
    return None


def triage_take(
    pkg: Any,
    take_id: str,
    *,
    clips_dir: Path | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Scan one generated take clip and emit assist-only QC metrics & WARN alerts (never bypasses human QC)."""
    from film_pipeline.production.takes import load_log, sha256_file

    root = Path(pkg.root)
    log = load_log(root, pkg.header.film_id)
    entry = log.get(take_id)
    base_dir = Path(clips_dir) if clips_dir is not None else root / "media" / "takes"
    clip = base_dir / entry.output_file
    if not clip.is_file():
        clip_alt = base_dir / Path(entry.output_file).name
        if clip_alt.is_file():
            clip = clip_alt
        else:
            raise FileNotFoundError(f"Take clip not found for triage: {clip}")
    actual_sha = sha256_file(clip)
    hash_verified = not entry.output_sha256 or actual_sha == entry.output_sha256

    if use_cache and clips_dir is None and hash_verified:
        cached_doc = load_cached_triage(root, take_id, actual_sha)
        if cached_doc is not None:
            return cached_doc

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

    # Frame-to-frame motion, border stability (R44F), and exposure flicker
    border_deltas: list[float] = []
    frame_motion_deltas: list[float] = []
    frame_lumas = [sum(f) / max(len(f), 1) for f in frames]
    luma_jumps = [abs(b - a) for a, b in zip(frame_lumas, frame_lumas[1:])]
    for a, b in zip(frames, frames[1:]):
        top = _region_mean_abs_diff(a, b, range(0, AN_W), range(0, 4))
        left = _region_mean_abs_diff(a, b, range(0, 4), all_rows)
        right = _region_mean_abs_diff(a, b, range(AN_W - 4, AN_W), all_rows)
        border_deltas.append((top + left + right) / 3.0)
        frame_motion_deltas.append(_region_mean_abs_diff(a, b, range(0, AN_W), all_rows))
    med_border = statistics.median(border_deltas) if border_deltas else 0.0
    max_border = max(border_deltas) if border_deltas else 0.0
    max_motion = max(frame_motion_deltas) if frame_motion_deltas else 0.0
    max_luma_jump = max(luma_jumps) if luma_jumps else 0.0

    # Audio speech activity & peak clipping check
    hop_s = 0.05
    try:
        dbs, peak_sample = _audio_triage_stats(clip, hop_s=hop_s)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        dbs, peak_sample = [], 0
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
    signals: list[dict[str, Any]] = []
    edge_metrics = _edge_intrusion_signal(take_id, clip, actual_sha, decl, signals, warnings)
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
    if len(frames) >= 4 and max_motion < 0.45:
        warnings.append({
            "code": "FROZEN_TAKE_RISK",
            "severity": "WARN",
            "detail": f"picture shows near-zero motion across sampled frames (max_delta={max_motion:.2f}); check for static image masquerade",
        })
    if max_luma_jump >= 35.0:
        warnings.append({
            "code": "LUMA_FLICKER_SPIKE",
            "severity": "WARN",
            "detail": f"abrupt exposure jump between sampled frames (max_luma_jump={max_luma_jump:.1f})",
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
    elif decl is not None and decl.dialogue and duration_s >= 3.0 and 0.08 <= active_ratio < 0.95 and tail_silence < 0.06:
        warnings.append({
            "code": "SPEECH_TRUNCATED_AT_TAIL",
            "severity": "WARN",
            "detail": f"speech remains active to clip end (trailing_silence={tail_silence:.3f}s); verify final word was not cut off",
        })
    if peak_sample >= 32700:
        warnings.append({
            "code": "AUDIO_CLIPPING_RISK",
            "severity": "WARN",
            "detail": f"raw take audio hits near full-scale peak ({peak_sample}/32767); check for distortion",
        })
    if not hash_verified:
        warnings.append({
            "code": "TAKE_HASH_MISMATCH",
            "severity": "WARN",
            "detail": f"clip sha256 {actual_sha[:12]} differs from logged output_sha256 {entry.output_sha256[:12]}",
        })

    result = {
        "take_id": take_id,
        "generation_id": entry.generation_id,
        "clip": str(clip),
        "output_sha256": actual_sha,
        "hash_verified": hash_verified,
        "duration_s": round(duration_s, 3),
        "advisory_only": True,
        "auto_pass_forbidden": True,
        "triage_cache_version": TRIAGE_CACHE_VERSION,
        "metrics": {
            "frames_sampled": len(frames),
            "baseline": "start_still" if still_path is not None else "frame_0",
            "left_edge_max_delta": round(max_left, 2),
            "right_edge_max_delta": round(max_right, 2),
            "center_median_delta": round(med_center, 2),
            "frame_motion_max_delta": round(max_motion, 2),
            "luma_max_jump": round(max_luma_jump, 2),
            "corner_mark_median_std": round(med_corner_std, 2),
            "border_median_delta": round(med_border, 2),
            "border_max_delta": round(max_border, 2),
            "audio_peak_sample": peak_sample,
            "speech_active_ratio": round(active_ratio, 3),
            "leading_silence_s": lead_silence,
            "trailing_silence_s": tail_silence,
            "suggested_src_in_s": sug_in,
            "suggested_src_out_s": sug_out,
            "edge_intrusion": edge_metrics,
        },
        "warnings": warnings,
        "signals": signals,
    }
    if use_cache and clips_dir is None and hash_verified:
        try:
            atomic_json(triage_cache_path(root, take_id), result)
        except OSError:
            pass
    return result


def triage_batch(
    pkg: Any,
    take_ids: list[str] | None = None,
    *,
    clips_dir: Path | None = None,
    jobs: int | None = None,
    use_cache: bool = True,
) -> dict[str, dict[str, Any]]:
    """Run `triage_take` across multiple takes concurrently using bounded worker threads."""
    from film_pipeline.production.takes import load_log

    root = Path(pkg.root)
    if take_ids is None:
        log = load_log(root, pkg.header.film_id)
        ids = [t.take_id for t in log.takes]
    else:
        ids = list(take_ids)
    if not ids:
        return {}
    workers = render_workers(jobs)

    def _one(tid: str) -> tuple[str, dict[str, Any]]:
        try:
            return tid, triage_take(pkg, tid, clips_dir=clips_dir, use_cache=use_cache)
        except Exception as exc:  # noqa: BLE001
            return tid, {
                "take_id": tid,
                "advisory_only": True,
                "auto_pass_forbidden": True,
                "metrics": {},
                "warnings": [{"code": "TRIAGE_ERROR", "severity": "WARN", "detail": str(exc)[:160]}],
                "signals": [],
            }

    if len(ids) > 1 and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pairs = list(pool.map(_one, ids))
    else:
        pairs = [_one(tid) for tid in ids]
    return dict(pairs)
