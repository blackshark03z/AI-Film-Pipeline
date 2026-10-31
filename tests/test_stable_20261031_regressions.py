"""Regressions fixed in the 2026-10-31 stable-release audit."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.delivery import DeliveryEntry  # noqa: E402


@pytest.mark.parametrize("bad", ["C:/abs/a.mp4", "C:\\abs\\a.mp4", "D:a.mp4",
                                 "\\\\server\\share\\a.mp4", "/abs/a.mp4",
                                 "a/../../b.mp4", "a\\..\\..\\b.mp4"])
def test_delivery_rejects_absolute_or_escaping_paths_on_every_os(bad):
    with pytest.raises(ValueError, match="relative"):
        DeliveryEntry(role="master", path=bad, sha256="0" * 64, bytes=1,
                      media_type="video/mp4", source_lineage="x")


def test_delivery_accepts_plain_relative_path():
    DeliveryEntry(role="master", path="out/a.mp4", sha256="0" * 64, bytes=1,
                  media_type="video/mp4", source_lineage="x")


def _login_probe_script() -> str:
    src = (ROOT / "tools/dola_010e_session_router.py").read_text(encoding="utf-8")
    match = re.search(r'page\.evaluate\(\s*r?"""(.*?)"""', src, re.S)
    assert match, "login probe script not found"
    return match.group(1)


def test_dola_logged_out_probe_regex_is_single_line_js():
    # A raw newline inside a JS regex literal is a SyntaxError; the old code
    # swallowed it and reported logged_out=False (fail-open).
    script = _login_probe_script()
    for literal in re.findall(r"/\(\^\|.*?/\.test", script, re.S):
        assert "\n" not in literal


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_dola_logged_out_probe_executes_in_js():
    body = _login_probe_script().replace("document.body && document.body.innerText", "T")
    js = f"const T = 'Home\\nログイン\\nMore'; console.log(({body})());"
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "true"


def test_scene_scale_tool_imports_without_local_evidence():
    import importlib
    module = importlib.import_module("run_scene_scale_003")
    assert callable(module.base_reference_binding)
