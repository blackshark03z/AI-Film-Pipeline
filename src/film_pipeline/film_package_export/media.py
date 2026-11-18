"""Hashing and ffprobe helpers for the film_package exporter (read-only on the film folder)."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


class ExportError(Exception):
    """The film folder cannot be turned into a valid film_package; the message says why."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def frames(seconds: float, fps: Fraction) -> int:
    """Nearest frame boundary of a time in seconds."""
    return math.floor(float(seconds) * float(fps) + 0.5 + 1e-9)


def probe(path: Path) -> dict[str, Any]:
    """Video/audio facts of a media file: ``{"video": {...}|None, "audio": {...}|None, "duration_s": float}``."""
    exe = shutil.which("ffprobe")
    if not exe:
        raise ExportError("ffprobe not found on PATH (needed to measure the picture clock)")
    run = subprocess.run([exe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, check=False)
    if run.returncode != 0:
        raise ExportError(f"ffprobe failed on {path.name}: {run.stderr.strip()[:200]}")
    data = json.loads(run.stdout)
    out: dict[str, Any] = {"video": None, "audio": None, "duration_s": float(data.get("format", {}).get("duration") or 0)}
    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind == "video" and out["video"] is None:
            num, den = (stream.get("r_frame_rate") or "0/1").split("/")
            nb = stream.get("nb_frames")
            out["video"] = {"width": int(stream["width"]), "height": int(stream["height"]),
                            "fps": Fraction(int(num), int(den or 1)) if int(num) else None,
                            "nb_frames": int(nb) if nb and nb != "N/A" else None,
                            "duration_s": float(stream.get("duration") or out["duration_s"])}
        elif kind == "audio" and out["audio"] is None:
            out["audio"] = {"sample_rate": int(stream.get("sample_rate") or 0),
                            "duration_s": float(stream.get("duration") or out["duration_s"])}
    return out
