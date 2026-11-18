"""Bounded FFmpeg runs and lossless joins of rendered video chunks."""
from __future__ import annotations

import functools
import os
import subprocess
from pathlib import Path
from typing import Sequence

# Colour description every joined chunk is rewritten to (BT.709, limited range). Chunks that went through different
# filter graphs come out of libx264 with different VUI colour tags (one untagged, one bt709); when such chunks are
# stream-copied into one file, the decoder reports a colour change at the join and the ffmpeg CLI re-initialises the
# filter graph. If that graph holds a `concat` filter (the title/body/end assembly) it never finishes (FFmpeg 9.0.1).
_BT709_VUI = ("h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:"
              "video_full_range_flag=0")


class FfmpegTimeout(RuntimeError):
    """An FFmpeg run exceeded its bound and was killed."""


def run_ffmpeg(cmd: Sequence[str], *, timeout_s: float) -> subprocess.CompletedProcess:
    """Run ``cmd`` and fail loudly instead of blocking forever when FFmpeg stalls."""
    try:
        return subprocess.run(list(cmd), check=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise FfmpegTimeout(f"ffmpeg did not finish within {timeout_s:.0f}s: {' '.join(map(str, cmd[:6]))} ...") from exc


def ffconcat_path(path: Path) -> str:
    """Resolve and escape a filesystem path for an FFmpeg concat demuxer entry."""
    return path.resolve().as_posix().replace("'", r"'\''")


def media_timeout(seconds: float, *, factor: float = 20.0, floor: float = 600.0) -> float:
    """A generous wall-clock bound for work on ``seconds`` of media."""
    return max(floor, factor * seconds)


def join_video_chunks(concat_list: Path, out: Path, *, timeout_s: float = 1800.0) -> Path:
    """Stream-copy the chunks listed in ``concat_list`` into ``out`` (no re-encode, frame-exact), with one colour tag."""
    run_ffmpeg(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-c", "copy", "-bsf:v", _BT709_VUI, str(out)], timeout_s=timeout_s)
    return out


@functools.lru_cache(maxsize=1)
def nvenc_available() -> bool:
    """True only when FFmpeg advertises h264_nvenc AND a tiny 1-frame hardware encode succeeds."""
    try:
        enc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if enc.returncode != 0 or "h264_nvenc" not in (enc.stdout or ""):
            return False
        probe = subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=64x64:r=24:d=0.05",
             "-frames:v", "1", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        return probe.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def use_hwaccel(hwaccel: bool | None = None) -> bool:
    """Resolve whether NVENC hardware H.264 encoding should be used."""
    if hwaccel is not None:
        return bool(hwaccel) and nvenc_available()
    env = os.environ.get("AFP_HWACCEL", "").strip().lower()
    return env in ("1", "true", "yes", "nvenc") and nvenc_available()


def render_workers(requested: int | None = None, *, hwaccel: bool = False) -> int:
    """Bounded worker count for parallel chunk FFmpeg renders."""
    if requested is not None:
        return max(1, int(requested))
    raw = os.environ.get("AFP_RENDER_JOBS", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    if hwaccel:
        return 2
    return min(4, max(1, (os.cpu_count() or 2) // 2))


def video_encode_args(profile: str = "master", *, hwaccel: bool | None = None) -> tuple[list[str], str]:
    """Return ``(ffmpeg_args, encoder_name)`` for CPU libx264 (default) or GPU h264_nvenc."""
    if use_hwaccel(hwaccel):
        cq = "16" if profile == "fine_intermediate" else "19"
        return (["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", cq, "-b:v", "0", "-pix_fmt", "yuv420p"],
                "h264_nvenc")
    if profile == "fine_intermediate":
        return (["-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p"], "libx264")
    return (["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"], "libx264")
