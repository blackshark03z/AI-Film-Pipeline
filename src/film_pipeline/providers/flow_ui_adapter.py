"""FlowUiAdapter: today's Google Flow send (`tools/drama_flow_ui/flow_send.py`) behind the ``VideoProvider`` shape.

Behaviour is the pre-adapter behaviour of ``production/generate.py`` moved here unchanged: the same argv, the same
manifest/result strings, the same ledger effect. Flow has no stable job id: a take binds by prompt text and media id
(flow_send's picker/binding), so ``provider_job_id`` stays empty and the adapter's own job handle is the output path.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .base import ProviderHealth
from .capability import ModelCapability, get_capability
from .request import GenerationRequest

ROOT = Path(__file__).resolve().parents[3]
FLOW_SEND = ROOT / "tools" / "drama_flow_ui" / "flow_send.py"
FLOW_MODEL = "Omni 1.2 Flash"  # the model name Flow's composer dropdown starts with
PLACEHOLDER_END_TOKEN = "tok:<TAIL_OF_UPLOADED_END_FRAME>"

Runner = Callable[[list[str], Path], dict[str, Any]]


def default_runner(argv: list[str], out: Path) -> dict[str, Any]:  # pragma: no cover - spends credits; P3-05 only
    """Run the sender and return its manifest plus `returncode`; `generate` refuses a manifest that does not belong to
    this send (the output must not exist before the send, so an old manifest cannot be mistaken for a new one)."""
    done = subprocess.run(argv, check=False)
    manifest = out.with_suffix(".take.json")
    body = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {"result": "NO_MANIFEST"}
    return {**body, "returncode": done.returncode}


class FlowUiAdapter:
    def __init__(self, cap: ModelCapability | None = None, runner: Runner | None = None,
                 flow_send: Path = FLOW_SEND, python: str | None = None) -> None:
        self.cap = cap or get_capability("flow")
        self.runner = runner
        self.flow_send = Path(flow_send)
        self.python = python or sys.executable
        self._manifests: dict[str, dict[str, Any]] = {}

    # ---- the send path generate.py uses ------------------------------------------------------------------------
    def build_argv(self, request: GenerationRequest, *, prompt_file: Path, start_token: str | None = None,
                   end_token: str | None = None) -> tuple[list[str], list[str]]:
        """(argv, preconditions). Token route (a start token is given): the stills are already in the Flow gallery.
        Upload route (no start token): flow_send uploads them inside the send, so they are the newest picker items and
        only a pixel check is needed."""
        if request.first_frame is None:
            raise ValueError("the Flow start-frame route needs a first frame")
        still, end = request.first_frame.path, request.last_frame.path if request.last_frame else None
        out = request.output
        upload = not start_token
        argv = [self.python, str(self.flow_send), str(prompt_file), str(out)]
        if upload:
            argv += ["--upload-frames", "--start-file", str(still)]
            preconditions = ["Flow composer is on Omni 1.2 Flash, 360p, video mode (flow_send sets model and duration)",
                             "flow_send uploads the start (and end) still inside the send; the newest picker item must "
                             "match it by pixels"]
        else:
            argv += ["--start", start_token, "--start-file", str(still)]
            preconditions = ["Flow composer is on Omni 1.2 Flash, 360p, video mode (flow_send sets model and duration)",
                             "the start still is uploaded to the Flow gallery (its tail is --start-token)"]
            if end is not None:
                preconditions.append("the end still is uploaded to the Flow gallery (its tail is --end-token)")
        argv += ["--model", self.cap.api_model or FLOW_MODEL, "--duration", str(int(request.duration_s))]
        if not upload and end is not None:
            argv += ["--end", end_token or PLACEHOLDER_END_TOKEN, "--end-file", str(end)]
        if upload and end is not None:
            argv += ["--end-file", str(end)]
        preconditions.append("GPM / Flow browser stays open; no cookies or captchas touched")
        return argv, preconditions

    def send(self, argv: list[str], out: Path) -> dict[str, Any]:
        """Run flow_send (or the injected runner) once; the manifest comes back unchanged."""
        manifest = (self.runner or default_runner)(argv, Path(out))
        self._manifests[str(out)] = manifest
        return manifest

    def normalize(self, raw: object) -> str:
        return self.cap.normalize(raw)

    # ---- VideoProvider ---------------------------------------------------------------------------------------
    def capabilities(self):
        return self.cap.provider_capabilities()

    def health(self) -> ProviderHealth:
        if not self.flow_send.is_file():
            return ProviderHealth(provider_id="flow", state="MISCONFIGURED", diagnostic_code="FLOW_SEND_MISSING",
                                  evidence=[str(self.flow_send)])
        # the browser session cannot be checked offline; flow_send itself fails PRE_SUBMIT_ERROR NO_FLOW_TAB
        return ProviderHealth(provider_id="flow", state="READY", diagnostic_code="BROWSER_NOT_PROBED")

    async def preflight(self) -> ProviderHealth:
        return self.health()

    async def submit(self, request: GenerationRequest, *, prompt_file: Path, start_token: str | None = None,
                     end_token: str | None = None) -> str:
        argv, _ = self.build_argv(request, prompt_file=prompt_file, start_token=start_token, end_token=end_token)
        self.send(argv, request.output_path)
        return request.output

    async def poll(self, provider_job_id: str) -> dict[str, Any]:
        manifest = self._manifests.get(provider_job_id, {"result": "PENDING"})
        return {**manifest, "normalized": self.normalize(manifest.get("result"))}

    async def fetch_outputs(self, provider_job_id: str) -> list[str]:
        manifest = self._manifests.get(provider_job_id, {})
        out = Path(provider_job_id)
        return [str(out)] if manifest.get("result") == "PASSED" and out.is_file() else []

    async def cancel(self, provider_job_id: str) -> bool:
        return False  # a Flow job cannot be cancelled from here
