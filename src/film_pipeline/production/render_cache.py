"""Small content-verified cache for resumable render intermediates."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


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


def save(cache_dir: Path | None, key: str, source: Path, suffix: str) -> Path:
    if cache_dir is None:
        return source
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    item = root / f"{key}{suffix}"
    meta = item.with_suffix(item.suffix + ".json")
    temp = item.with_name(item.name + f".{os.getpid()}.tmp")
    shutil.copyfile(source, temp)
    sha = digest(temp)
    os.replace(temp, item)
    tmp_meta = meta.with_name(meta.name + f".{os.getpid()}.tmp")
    tmp_meta.write_text(json.dumps({"key": key, "sha256": sha}), encoding="utf-8")
    os.replace(tmp_meta, meta)
    return item
