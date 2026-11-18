"""Small content-verified cache for resumable render intermediates."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any

_PROD_DIR = Path(__file__).resolve().parent
_RENDER_IMPL_PATHS = [
    p for p in (
        _PROD_DIR / "render_cache.py",
        _PROD_DIR / "edit.py",
        _PROD_DIR / "versions.py",
        _PROD_DIR / "titles.py",
        _PROD_DIR / "ffjoin.py",
        _PROD_DIR.parent / "drama" / "post.py",
    ) if p.is_file()
]
_RENDER_IMPL_SHA = hashlib.sha256(b"".join(p.read_bytes() for p in _RENDER_IMPL_PATHS)).hexdigest()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def key_for(*, sources: list[Path], settings: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({
        "sources": [digest(Path(p)) for p in sources],
        "settings": settings, "render_cache_version": 2,
        "render_impl_sha": _RENDER_IMPL_SHA,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def cached(cache_dir: Path | None, key: str, suffix: str) -> Path | None:
    if cache_dir is None:
        return None
    item = Path(cache_dir) / f"{key}{suffix}"
    meta = item.with_suffix(item.suffix + ".json")
    try:
        record = json.loads(meta.read_text(encoding="utf-8"))
        if record == {"key": key, "sha256": digest(item)}:
            return item
    except (OSError, ValueError):
        pass
    return None


def _replace_with_retry(src: Path, dst: Path, *, attempts: int = 3, delay_s: float = 0.05) -> None:
    for idx in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if idx == attempts - 1:
                raise
            time.sleep(delay_s)


def save(cache_dir: Path | None, key: str, source: Path, suffix: str) -> Path:
    if cache_dir is None:
        return source
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    item = root / f"{key}{suffix}"
    meta = item.with_suffix(item.suffix + ".json")
    tid = threading.get_ident()
    temp = item.with_name(f"{item.name}.{os.getpid()}.{tid}.tmp")
    tmp_meta = meta.with_name(f"{meta.name}.{os.getpid()}.{tid}.tmp")
    try:
        shutil.copyfile(source, temp)
        sha = digest(temp)
        try:
            _replace_with_retry(temp, item)
        except PermissionError:
            if cached(root, key, suffix) is not None:
                return item
            raise
        tmp_meta.write_text(json.dumps({"key": key, "sha256": sha}), encoding="utf-8")
        try:
            _replace_with_retry(tmp_meta, meta)
        except PermissionError:
            if cached(root, key, suffix) is not None:
                return item
            raise
        return item
    finally:
        temp.unlink(missing_ok=True)
        tmp_meta.unlink(missing_ok=True)
