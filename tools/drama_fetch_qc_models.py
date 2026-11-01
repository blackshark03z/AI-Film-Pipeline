"""Download the OpenCV zoo face models used by drama/autoqc.py (WP4).

Models live outside the repo (never commit them): default cache dir is
%LOCALAPPDATA%/film_pipeline/models, override with FILM_PIPELINE_MODELS.
Each file is verified against a pinned sha256 and byte size on every run.
Usage: python tools/drama_fetch_qc_models.py
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

_RAW = "https://github.com/opencv/opencv_zoo/raw/main/models/"
_LFS = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"

# name -> (path in zoo, sha256, size in bytes), pinned after first download
MODELS: dict[str, tuple[str, str, int]] = {
    "face_detection_yunet_2023mar.onnx": (
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        232589),
    "face_recognition_sface_2021dec.onnx": (
        "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        38696353),
}


def models_dir() -> Path:
    env = os.environ.get("FILM_PIPELINE_MODELS")
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    return Path(base) / "film_pipeline" / "models"


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read()


def _is_lfs_pointer(data: bytes) -> bool:
    return len(data) < 1024 and data.startswith(b"version https://git-lfs")


def _verify(data: bytes, sha: str, size: int) -> bool:
    return len(data) == size and hashlib.sha256(data).hexdigest() == sha


def main() -> int:
    out_dir = models_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (rel, sha, size) in MODELS.items():
        dest = out_dir / name
        if dest.exists() and _verify(dest.read_bytes(), sha, size):
            print(f"ok (cached) {dest}")
            continue
        data = _download(_RAW + rel)
        if _is_lfs_pointer(data):
            data = _download(_LFS + rel)
        if not _verify(data, sha, size):
            print(f"FAIL checksum mismatch for {name}", file=sys.stderr)
            return 1
        dest.write_bytes(data)
        print(f"downloaded {dest} size={len(data)} "
              f"sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
