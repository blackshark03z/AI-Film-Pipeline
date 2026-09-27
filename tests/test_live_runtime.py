import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import ProviderCapabilities, load_shot, validate_contract
from film_pipeline.execution import DryRunProvider, route
from film_pipeline.live_runtime import LiveRuntimeExecutor, inspect_video
from film_pipeline.store import SQLiteStore


ROOT = Path(__file__).resolve().parents[1]


class FakeTransport:
    def __init__(self, *, fail_submit=False, state="SUCCEEDED"):
        self.fail_submit = fail_submit
        self.state = state
        self.submits = 0
        self.polls = 0

    async def snapshot(self):
        return {"existing_asset_ids": ["old-asset"]}

    async def submit(self, job, prompt):
        self.submits += 1
        assert job.dispatch_count == 1
        assert prompt == job.correlation_evidence["prompt"]
        if self.fail_submit:
            raise TimeoutError("response lost")
        return {"external_job_id": "remote-job-1", "correlation_evidence": {"submit_id": "remote-job-1"}}

    async def poll(self, job):
        self.polls += 1
        return {"status": self.state, "external_job_id": "remote-job-1",
                "correlation_evidence": {"output_ids": ["remote-output-1"]}}

    async def fetch(self, job, output_id, destination):
        completed = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=16x16:d=0.1", "-an", str(destination)],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode:
            raise RuntimeError("ffmpeg fixture creation failed")
        return destination


def make_executor(tmp_path, transport, *, project_binding_id="safe-project-binding"):
    raw_profile = json.loads((ROOT / "tests/fixtures/provider_full.json").read_text())
    validate_contract("provider_capabilities", raw_profile)
    profile = ProviderCapabilities.model_validate(raw_profile)
    shot = load_shot(ROOT / "fixtures/flow_canary.json")
    plan = compile_prompt(shot, profile)
    decision = route(shot, [plan], [profile], {profile.provider_id: True})
    dry = DryRunProvider()
    request = dry.build_request(plan, decision)
    attempt = dry.create_attempt(shot, plan, decision, request, started_at="2026-09-27T00:00:00+00:00")
    store = SQLiteStore(tmp_path / "runtime.sqlite")
    executor = LiveRuntimeExecutor(store, transport)
    job = executor.freeze_path(shot, plan, decision, attempt, project_binding_id=project_binding_id,
                               pre_dispatch_snapshot={"existing_asset_ids": ["old-asset"]})
    return executor, store, attempt, job


def test_submit_timeout_restart_reconciles_without_blind_redispatch(tmp_path):
    transport = FakeTransport(fail_submit=True)
    executor, store, attempt, job = make_executor(tmp_path, transport)

    with pytest.raises(TimeoutError):
        asyncio.run(executor.submit_once(job.provider_job_id))
    assert transport.submits == 1
    persisted = SQLiteStore(store.path).read_provider_job(job.provider_job_id)
    assert persisted.dispatch_count == 1
    assert persisted.status == "INCONCLUSIVE"

    # A fresh executor models process restart. It sees the durable reservation;
    # reconciliation is read-only and a second submit is forbidden.
    restarted_transport = FakeTransport(state="RUNNING")
    restarted = LiveRuntimeExecutor(SQLiteStore(store.path), restarted_transport)
    reconciled = asyncio.run(restarted.reconcile(job.provider_job_id))
    assert reconciled.status == "RUNNING"
    assert restarted_transport.submits == 0
    with pytest.raises(RuntimeError, match="budget already consumed"):
        asyncio.run(restarted.submit_once(job.provider_job_id))
    assert restarted_transport.submits == 0
    path = SQLiteStore(store.path).read_runtime_lineage(attempt.generation_attempt_id, job.provider_job_id)
    assert path[4].dispatch_count == 1
    assert path[5] == ()


def test_crash_after_durable_reservation_never_reaches_submit_on_restart(tmp_path):
    transport = FakeTransport()
    executor, store, _attempt, job = make_executor(tmp_path, transport)
    # This models a process dying after the durable commit and before the
    # browser call. The conservative reservation consumes the budget.
    reserved = store.reserve_dispatch(job.provider_job_id)
    assert reserved.dispatch_count == 1
    restarted = LiveRuntimeExecutor(SQLiteStore(store.path), FakeTransport())
    with pytest.raises(RuntimeError, match="budget already consumed"):
        asyncio.run(restarted.submit_once(job.provider_job_id))
    assert restarted.transport.submits == 0


def test_successful_submit_reconciles_exact_output_ids_and_persists_lineage(tmp_path):
    transport = FakeTransport()
    executor, store, attempt, job = make_executor(tmp_path, transport)
    submitted = asyncio.run(executor.submit_once(job.provider_job_id))
    assert submitted.dispatch_count == 1
    assert submitted.external_job_id == "remote-job-1"
    reconciled = asyncio.run(executor.reconcile(job.provider_job_id))
    assert reconciled.status == "SUCCEEDED"
    assert reconciled.correlation_evidence["output_ids"] == ["remote-output-1"]
    assert SQLiteStore(store.path).read_runtime_lineage(attempt.generation_attempt_id, job.provider_job_id)[4] == reconciled


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg tools required")
def test_downloaded_video_is_validated_hashed_and_survives_fresh_readback(tmp_path):
    transport = FakeTransport()
    executor, store, attempt, job = make_executor(tmp_path, transport)
    asyncio.run(executor.submit_once(job.provider_job_id))
    asyncio.run(executor.reconcile(job.provider_job_id))
    assets = asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / "outputs"))
    assert len(assets) == 1
    assert assets[0].duration_s and assets[0].duration_s > 0
    assert assets[0].sha256
    lineage = SQLiteStore(store.path).read_runtime_lineage(attempt.generation_attempt_id, job.provider_job_id)
    assert lineage[5] == assets


def test_html_renamed_as_mp4_is_rejected(tmp_path):
    fake_video = tmp_path / "error.mp4"
    fake_video.write_text("<html>not a video</html>", encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError)):
        inspect_video(fake_video)
