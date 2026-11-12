"""Read-only runtime checks; no provider submission, authentication changes or installation."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from .runtime import flow_cdp, flow_project

MIN_SCRATCH_GIB = 20.0      # long renders (cut/titles/mix/versions/finish/benchmark): scratch for the whole pass
SEND_RESERVE_GIB = 4.0      # a single Flow send/download keeps only the standing reserve ...
SEND_TAKE_BOUND_GIB = 0.5   # ... plus a conservative bound for one take and its still (a 6-15 s 360p clip is a few MB)
OPERATIONS = ("render", "send")


def required_free_gib(operation: str = "render", expected_bytes: int = 0) -> float:
    if operation == "render":
        return MIN_SCRATCH_GIB
    if operation == "send":
        return SEND_RESERVE_GIB + max(SEND_TAKE_BOUND_GIB, expected_bytes / 2**30)
    raise ValueError(f"unknown preflight operation {operation!r}; use one of {OPERATIONS}")


def check(root: Path, *, probe_flow: bool = False, operation: str = "render", expected_bytes: int = 0) -> dict:
    """``operation`` picks the disk rule: ``render`` keeps the 20 GiB long-render rule (default), ``send`` needs the
    4 GiB reserve plus the expected download (stills, sends and reconcile)."""
    need = required_free_gib(operation, expected_bytes)
    issues, warnings = [], []
    volumes = {}
    for name, path in {"output": Path(root), "scratch": Path(tempfile.gettempdir())}.items():
        while not path.exists():
            path = path.parent
        free = shutil.disk_usage(path).free / 2**30
        volumes[name] = {"path": str(path), "free_gib": round(free, 3)}
        if free < need:
            issues.append(f"{name} has {free:.2f}GiB free; {operation} needs at least {need:g}GiB")
    tools = {}
    for name in ("ffmpeg", "ffprobe"):
        exe = shutil.which(name)
        if not exe:
            issues.append(name + " is missing")
        else:
            result = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=10)
            tools[name] = result.stdout.splitlines()[0] if result.stdout else "unavailable"
            if result.returncode:
                issues.append(name + " cannot start")
    if importlib.util.find_spec("PIL") is None:
        issues.append("Pillow is missing")
    model = Path(os.environ.get("AFP_VOSK_MODEL") or Path.home() / ".cache/vosk/vosk-model-small-en-us-0.15")
    stt_python = sys.executable if importlib.util.find_spec("vosk") else os.environ.get("AFP_STT_PYTHON") or shutil.which("python")
    stt_ready = False
    if stt_python and model.is_dir():
        try:
            stt_ready = subprocess.run([stt_python, "-c", "import vosk"], capture_output=True, timeout=15).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not stt_ready:
        warnings.append("dialogue STT unavailable: check the Vosk model and AFP_STT_PYTHON; no speech PASS is inferred")
    session = "NOT_PROBED"
    if probe_flow:
        try:
            with urllib.request.urlopen(flow_cdp() + "/json/list", timeout=5) as response:
                pages = json.load(response)
            pinned = flow_project()
            present = any(("flow.google" in p.get("url", "") or "/tools/flow" in p.get("url", ""))
                          and (not pinned or f"/project/{pinned}" in p.get("url", "")) for p in pages)
            session = "FLOW_TAB_PRESENT" if present else "NO_FLOW_TAB"
        except (OSError, ValueError):
            session = "CDP_UNAVAILABLE"
        if session != "FLOW_TAB_PRESENT":
            issues.append("Flow session unavailable; reconnect it without submitting another job")
    return {"ok": not issues, "issues": issues, "warnings": warnings, "python": sys.version.split()[0],
            "tools": tools, "volumes": volumes, "required_free_gib": need, "operation": operation,
            "stt_ready": stt_ready, "stt_python": stt_python if stt_ready else None, "provider_session": session}
