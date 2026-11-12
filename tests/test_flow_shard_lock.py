"""Shard parallelism step 1: the Flow composer lock is keyed by the CDP endpoint the process drives."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import runtime as RT
from film_pipeline.production.runtime import WriterBusy, writer

SRC = str(Path(__file__).resolve().parents[1] / "src")
CHILD = ("from pathlib import Path; import sys; from film_pipeline.production.runtime import writer,WriterBusy\n"
         "try:\n with writer(Path(sys.argv[1]),flow=True): print('FREE')\nexcept WriterBusy: print('BUSY')")


def child(root, cdp=None):
    env = {k: v for k, v in os.environ.items() if k != "AFP_FLOW_CDP"}
    env["PYTHONPATH"] = SRC
    if cdp is not None:
        env["AFP_FLOW_CDP"] = cdp
    done = subprocess.run([sys.executable, "-c", CHILD, str(root)], capture_output=True, text=True, env=env, timeout=20)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture(autouse=True)
def default_endpoint(monkeypatch, tmp_path):
    monkeypatch.delenv("AFP_FLOW_CDP", raising=False)
    # a live shard may hold the real machine-wide lock: use a private lock directory (children inherit it)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))


def test_default_endpoint_keeps_the_legacy_lock_key(monkeypatch):
    assert RT.flow_cdp() == "http://127.0.0.1:9333"
    assert RT.flow_lock_key() == "flow-ui-composer"
    for spelled in ("http://localhost:9333", "http://127.0.0.1:9333/", "127.0.0.1:9333"):
        monkeypatch.setenv("AFP_FLOW_CDP", spelled)
        assert RT.flow_lock_key() == "flow-ui-composer", spelled


def test_default_endpoint_is_still_exclusive_across_films(tmp_path):
    with writer(tmp_path / "filmA", flow=True):
        assert child(tmp_path / "filmB") == "BUSY"
        assert child(tmp_path / "filmB", "http://localhost:9333") == "BUSY"


def test_same_custom_endpoint_is_busy(tmp_path, monkeypatch):
    monkeypatch.setenv("AFP_FLOW_CDP", "http://127.0.0.1:9401")
    with writer(tmp_path / "filmA", flow=True):
        assert child(tmp_path / "filmB", "http://127.0.0.1:9401") == "BUSY"
        assert child(tmp_path / "filmB", "http://localhost:9401") == "BUSY"


def test_different_endpoints_do_not_block_each_other(tmp_path, monkeypatch):
    monkeypatch.setenv("AFP_FLOW_CDP", "http://127.0.0.1:9401")
    with writer(tmp_path / "filmA", flow=True):
        assert child(tmp_path / "filmB", "http://127.0.0.1:9402") == "FREE"
        assert child(tmp_path / "filmB") == "FREE"          # the default endpoint is another profile
    with writer(tmp_path / "filmA", flow=True):
        pass


def test_default_endpoint_holder_does_not_block_a_shard(tmp_path):
    with writer(tmp_path / "filmA", flow=True):
        assert child(tmp_path / "filmB", "http://127.0.0.1:9403") == "FREE"


def test_explicit_cdp_argument_overrides_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("AFP_FLOW_CDP", "http://127.0.0.1:9401")
    with writer(tmp_path / "filmA", flow=True, cdp="http://127.0.0.1:9404"):
        assert child(tmp_path / "filmB", "http://127.0.0.1:9404") == "BUSY"
        assert child(tmp_path / "filmB", "http://127.0.0.1:9401") == "FREE"


def test_the_film_root_lock_is_unchanged_by_the_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("AFP_FLOW_CDP", "http://127.0.0.1:9405")
    with writer(tmp_path / "film", flow=True):
        assert child(tmp_path / "film", "http://127.0.0.1:9406") == "BUSY"   # same root, other profile
