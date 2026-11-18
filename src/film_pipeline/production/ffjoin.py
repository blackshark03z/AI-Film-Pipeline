"""Bounded FFmpeg runs and lossless joins of rendered video chunks."""
from __future__ import annotations

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
