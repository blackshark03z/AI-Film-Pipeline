import sys
from pathlib import Path

studio_dir = Path(__file__).resolve().parent.parent
repo_root = studio_dir.parent

for p in (str(repo_root), str(studio_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

import os
import tempfile

import pytest

# Module level, before any test module is imported: even code that runs outside a test (collection, a thread that
# outlives its test) resolves a scratch halt, never the production `data/muse_halt.json` / `~/.afp/halt_pending/`.
# (`send_halt.halt_path()` also refuses to resolve the production path under pytest.)
_SESSION_HALT_DIR = Path(tempfile.mkdtemp(prefix="muse_test_halt_"))
os.environ["MUSE_HALT_FILE"] = str(_SESSION_HALT_DIR / "muse_halt.json")
os.environ["AFP_STATE_DIR"] = str(_SESSION_HALT_DIR / "afp")
os.environ.pop("AFP_HALT_FILE", None)


@pytest.fixture(autouse=True)
def _isolated_lane_leases(tmp_path_factory, monkeypatch):
    """Never let tests read or write the production lane registry (`data/lane_leases.json`)."""
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path_factory.mktemp("lane_leases") / "lane_leases.json"))


@pytest.fixture(autouse=True)
def _isolated_halt(tmp_path_factory, monkeypatch):
    """Never let tests read or write the real machine-wide halt (`data/muse_halt.json`, `~/.afp/halt_pending/`)."""
    base = tmp_path_factory.mktemp("halt")
    monkeypatch.setenv("MUSE_HALT_FILE", str(base / "muse_halt.json"))
    monkeypatch.setenv("AFP_STATE_DIR", str(base / "afp"))
    monkeypatch.delenv("AFP_HALT_FILE", raising=False)
    from muse_studio.core import send_halt

    def _reset():
        for mod in (send_halt, sys.modules.get("core.send_halt")):
            if mod is not None:
                mod._reset_memory()

    _reset()
    yield
    _reset()
