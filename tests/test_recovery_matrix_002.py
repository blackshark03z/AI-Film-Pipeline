"""PHASE 5 — focused recovery-matrix scenarios for the hardened lifecycle.

Covers the matrix rows not already proven by the dispatch-recovery, render-
lifecycle, and boundary suites: partial acquisition staging, receipt/bytes
mismatch, the global invariant that consumed authority can never yield
may_submit=True, and explicit (never silent) session failure when the
qualified profile is missing.
"""
import asyncio
import subprocess
from pathlib import Path

import pytest

from film_pipeline.core import sha256
from film_pipeline.dispatch_evidence import recovery_decision
from film_pipeline.live_runtime import LiveRuntimeExecutor
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.store import SQLiteStore
from test_dispatch_recovery import REQUEST
from test_live_runtime import FakeTransport, make_executor
from test_reference_reconcilable_transport import PROJECT

OUTPUT_ID = "remote-output-1"


def drive_to_bound(tmp_path):
    """Reserve → submit → reconcile → bind one output; returns helpers."""
    executor, store, attempt, job = make_executor(tmp_path, FakeTransport())
    asyncio.run(executor.submit_once(job.provider_job_id))
    executor2 = LiveRuntimeExecutor(store, FakeTransport())
    asyncio.run(executor2.reconcile(job.provider_job_id))
    store.bind_output(job.provider_job_id, OUTPUT_ID)
    return store, job


def test_staging_without_receipt_is_discarded_and_refetched(tmp_path):
    store, job = drive_to_bound(tmp_path)
    destination = tmp_path / "videos"
    staging = destination / (sha256(OUTPUT_ID)[:24] + ".partial.mp4")
    destination.mkdir(parents=True, exist_ok=True)
    # Emulate a crashed partial download: garbage staging bytes, no receipt,
    # no promoted asset.
    staging.write_bytes(b"partial-garbage")
    executor = LiveRuntimeExecutor(SQLiteStore(store.path), FakeTransport())
    assets = asyncio.run(executor.download_assets(job.provider_job_id, destination))
    assert len(assets) == 1
    assert assets[0].provider_asset_id == OUTPUT_ID
    assert not staging.exists()
    assert (destination / (sha256(OUTPUT_ID)[:24] + ".mp4")).exists()


def test_existing_destination_without_receipt_fails_closed(tmp_path):
    store, job = drive_to_bound(tmp_path)
    destination = tmp_path / "videos"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / (sha256(OUTPUT_ID)[:24] + ".mp4")).write_bytes(b"orphan")
    executor = LiveRuntimeExecutor(SQLiteStore(store.path), FakeTransport())
    with pytest.raises(ValueError, match="EXISTING_FILE_WITHOUT_ACQUISITION_RECEIPT"):
        asyncio.run(executor.download_assets(job.provider_job_id, destination))


def test_receipt_bytes_mismatch_fails_closed(tmp_path):
    store, job = drive_to_bound(tmp_path)
    destination = tmp_path / "videos"
    executor = LiveRuntimeExecutor(SQLiteStore(store.path), FakeTransport())
    assets = asyncio.run(executor.download_assets(job.provider_job_id, destination))
    assert len(assets) == 1
    # Tamper with the promoted asset after the receipt exists.
    Path(assets[0].uri_or_path).write_bytes(b"tampered-after-receipt")
    fresh = LiveRuntimeExecutor(SQLiteStore(store.path), FakeTransport())
    # Fail-closed either at media inspection or at the receipt comparison;
    # tampered bytes can never silently pass.
    with pytest.raises(ValueError, match="MISMATCH|ffprobe rejected"):
        asyncio.run(fresh.download_assets(job.provider_job_id, destination))


def test_consumed_authority_never_yields_may_submit(tmp_path):
    """Every consumed-state fact combination must keep may_submit False."""
    executor, store, attempt, job = make_executor(tmp_path, FakeTransport())
    reserved = store.reserve_dispatch(job.provider_job_id)
    reserved_fact = store.read_dispatch_facts(job.provider_job_id)[0]
    combos = [
        [],
        [{"kind": "GENERATE_REQUEST_OBSERVED", "data": REQUEST}],
        [{"kind": "GENERATE_REQUEST_OBSERVED", "data": REQUEST},
         {"kind": "PROVIDER_RESPONSE_OBSERVED",
          "data": {"request_hash": REQUEST["request_hash"], "status": 200}}],
        [{"kind": "PROVIDER_ACCEPTANCE_OBSERVED",
          "data": {"request_hash": REQUEST["request_hash"],
                   "provider_reference": "ack", "contract": "offline"}}],
        [{"kind": "REMOTE_IDENTITY_OBSERVED",
          "data": {"output_id": OUTPUT_ID, "method": "test"}}],
        [{"kind": "IDENTITY_BOUND",
          "data": {"output_id": OUTPUT_ID, "binding_hash": "b" * 64}}],
        [{"kind": "RENDER_PENDING_OBSERVED",
          "data": {"output_id": OUTPUT_ID, "basis": "as29s_null_media_row_present"}}],
        [{"kind": "RENDER_STATE_UNRESOLVED",
          "data": {"output_id": OUTPUT_ID,
                   "basis": "as29s_null_media_row_absent_attempt_1"}}],
        [{"kind": "RENDER_COMPLETED_OBSERVED",
          "data": {"output_id": OUTPUT_ID, "basis": "as29s_media_resolved"}}],
        [{"kind": "ADMITTED_RENDER_DROPPED",
          "data": {"output_id": OUTPUT_ID,
                   "basis": "persistent_disappearance_across_bounded_policy"}}],
        [{"kind": "AMBIGUOUS_EVIDENCE", "data": {"diagnostic": "test"}}],
        [{"kind": "OBSERVATION_FAILURE",
          "data": {"diagnostic": "FLOW_REFERENCE_RPC_READ_UNAVAILABLE"}}],
    ]
    for extra in combos:
        decision = recovery_decision(reserved, [reserved_fact] + extra,
                                     bound=True, acquired=False)
        assert decision.may_submit is False, extra


def test_profile_unavailable_is_explicit_not_silent(tmp_path):
    """A missing qualified profile is an explicit session failure, never a
    silent fallback to another profile/account."""
    session = FlowReferenceRpcSession(profile_path=tmp_path / "does-not-exist",
                                      project_id=PROJECT, native_ui=True)
    with pytest.raises(Exception):
        session.__enter__()
