"""Scratch halt environment for any test module that can publish or read a halt (Fix A, lessons L37).

`conftest.py` already sets these, but a module imported or run outside its conftest must still never resolve the real
machine-wide halt (`muse_studio/data/muse_halt.json`, `~/.afp/halt_pending/`). Importing this module sets them to a
scratch dir when unset. `send_halt.halt_path()` / `pending_dir()` additionally raise under pytest when they are unset.
"""
import os
import tempfile
from pathlib import Path


def ensure_scratch_halt_env() -> None:
    if os.environ.get("MUSE_HALT_FILE") and os.environ.get("AFP_STATE_DIR"):
        return
    base = Path(tempfile.mkdtemp(prefix="muse_test_halt_"))
    os.environ.setdefault("MUSE_HALT_FILE", str(base / "muse_halt.json"))
    os.environ.setdefault("AFP_STATE_DIR", str(base / "afp"))
    os.environ.pop("AFP_HALT_FILE", None)


ensure_scratch_halt_env()
