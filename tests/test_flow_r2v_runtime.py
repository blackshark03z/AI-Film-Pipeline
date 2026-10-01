"""Offline end-to-end proof for the generic Flow R2V runtime orchestration.

Every provider behavior here is a frozen/synthetic local double. No live
provider access, mutation, upload, or read exists in this module, and no
Slice-0011 identity, authority ID or historical state is referenced.
"""
import hashlib
import re
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from film_pipeline.core import ProviderCapabilities, References, load_shot, sha256
from film_pipeline.dispatch_evidence import recovery_decision
from film_pipeline.flow_r2v_runtime import (
    COMPACT_VERSION,
    FlowR2VShotRuntime,
    compact_r2v_prompt,
)
from film_pipeline.live_runtime import LiveRuntimeExecutor
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_r2v_prompt import film_marker
from film_pipeline.store import SQLiteStore

from test_canonical_reference_binding import bound
from test_flow_contract_20261001 import make_veo31_video_record
from test_flow_r2v_boundary import OUTPUT_ID, REFERENCE_FILENAME, native_request, route_of, video_row
from test_reference_reconcilable_transport import ACCOUNT, OTHER, PROJECT, REMOTE, png, setup

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_FILENAME_2 = 'reference.png'
SECOND_OUTPUT_ID = 'e3c1f211-2299-4c55-8d01-9fa0b7c4e333'


def flow_capabilities(provider_id='flow_veo'):
    payload = {
        'profile_version': 'flow-r2v-runtime-synthetic-v1',
        'provider_id': provider_id,
        'transport_type': 'other',
        'supports_text_to_video': True,
        'supports_image_input': True,
        'supports_duration_control': True,
    }
    from film_pipeline.core import validate_contract
    validate_contract('provider_capabilities', payload)
    return ProviderCapabilities.model_validate(payload)


def ordinary_r2v_shot(reference_asset_id, shot_id='FLOW_R2V_RUNTIME_ORDINARY_001'):
    """An ordinary synthetic shot: canonical schema, one exact image reference."""
    shot = load_shot(ROOT / 'fixtures/flow_canary.json')
    return shot.model_copy(update={
        'shot_id': shot_id,
        'references': References(other_asset_ids=[reference_asset_id])})


def mp4_fixture(path, seconds=8, width=320, height=240):
    """A locally generated, technically valid MP4 (no provider involvement)."""
    completed = subprocess.run(
        ['ffmpeg', '-y', '-f', 'lavfi', '-i',
         f'color=c=gray:s={width}x{height}:d={seconds}', '-an',
         '-pix_fmt', 'yuv420p', str(path)],
        capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError('ffmpeg fixture creation failed: ' + completed.stderr[-400:])
    return path.read_bytes()


class FixtureAcquisitionTransport:
    """Frozen synthetic acquisition double: writes one exact local fixture."""

    def __init__(self, data, *, corrupt=False):
        self.data = data
        self.corrupt = corrupt
        self.fetches = 0

    async def fetch(self, job, output_id, destination):
        self.fetches += 1
        destination.write_bytes(b'tampered-bytes' if self.corrupt else self.data)
        return destination


@pytest.fixture
def runtime_env(tmp_path):
    """Fully offline runtime environment: attested reference + frozen job."""
    asset, upload_store, session, transport, _key = setup(tmp_path)
    transport.ensure_verified(asset)  # offline upload double; no live upload
    session.bound_media = lambda identity, kind: bound()[3]
    attestation_dir = tmp_path / 'attestation'
    from film_pipeline.providers.flow_reference_binding import attest_existing_reference
    attestation = attest_existing_reference(
        SQLiteStore(upload_store.db_path), asset, session, account_id=ACCOUNT,
        media_id=REMOTE, evidence_dir=attestation_dir)
    store = SQLiteStore(upload_store.db_path)
    runtime = FlowR2VShotRuntime(store, project_id=PROJECT, account_id=ACCOUNT)
    shot = ordinary_r2v_shot(asset.asset_id)
    frozen = runtime.freeze(shot, flow_capabilities(), reference_asset=asset,
        reference_media_id=REMOTE, reference_filename=REFERENCE_FILENAME_2,
        baseline_catalog_ids=[OTHER], started_at='2026-10-01T00:00:00+00:00')
    return SimpleNamespace(asset=asset, attestation=attestation,
        attestation_dir=attestation_dir, runtime=runtime, store=store, shot=shot,
        frozen=frozen, baseline=[OTHER], tmp_path=tmp_path)


def reserve(env):
    return env.runtime.reserve(env.frozen, attestation=env.attestation,
                               evidence_dir=env.attestation_dir)


def release_request(env):
    """Simulate the one browser-created qualified request and its transport facts."""
    guard = env.runtime.arm_native_guard(env.frozen)
    prompt = env.store.read_provider_job(
        env.frozen.job.provider_job_id).correlation_evidence['prompt']
    request = route_of(native_request(prompt))
    guard.route(request)
    assert guard.sent == 1
    env.runtime.observe_provider_response(env.frozen, status=200)
    env.runtime.observe_provider_acceptance(env.frozen,
                                            provider_reference='remote-acceptance-1')
    return guard


def own_output(env, output_id=OUTPUT_ID, baseline=None):
    marker = film_marker(env.frozen.job.provider_job_id)
    row = make_veo31_video_record(output_id, PROJECT, REMOTE, REFERENCE_FILENAME_2,
        marker, model=contract.MODEL_VEO_3_1_LITE)
    return env.runtime.attribute_backend_output(env.frozen, [row]), row


def bind_media(env, output_id, data):
    payload, _ = video_row(output_id, size=len(data))
    return env.runtime.boundary.acquire_bound_media(payload, intent=env.frozen.intent,
        media_id=output_id, data=data,
        response_url=f'https://flow-content.google/video/{output_id}',
        status=200, headers={'content-type': 'video/mp4',
                             'content-length': str(len(data))})


def acquired_destination(env, output_id):
    return (env.tmp_path / 'assets' / f"{sha256(output_id)[:24]}.mp4")


# The exact offline end-to-end vertical: ordinary shot → QC-handoff eligibility.
def test_generic_r2v_shot_end_to_end_offline(tmp_path, runtime_env):
    env, runtime, frozen = runtime_env, runtime_env.runtime, runtime_env.frozen
    job_id = frozen.job.provider_job_id

    prompt = frozen.job.correlation_evidence['prompt']
    marker = film_marker(job_id)
    body = prompt.split('\n')[0]
    assert prompt.endswith('\n' + marker)
    assert prompt.count('[FILM-') == 1
    assert len(body) <= 500 and len(body.split()) <= 75
    assert frozen.job.correlation_evidence['provider_prompt_compiler'] == COMPACT_VERSION
    assert frozen.plan.mapped_controls['image_input'] == [
        {'asset_id': env.asset.asset_id, 'sha256': env.asset.sha256}]

    reserved = reserve(env)
    assert reserved.dispatch_count == 1
    facts = env.store.read_dispatch_facts(job_id)
    assert [fact['kind'] for fact in facts[:2]] == ['RESERVED', 'MUTATION_INTENT_BOUND']
    assert facts[1]['data']['reference_media_id'] == REMOTE
    assert facts[1]['data']['attestation_id'] == env.attestation['attestation_id']
    assert facts[1]['data']['prompt_sha256'] == sha256(prompt)

    release_request(env)

    output_id, row = own_output(env)
    assert output_id == OUTPUT_ID
    assert env.store.read_output_bindings(job_id)[0]['output_id'] == OUTPUT_ID

    data = mp4_fixture(tmp_path / 'fixture.mp4')
    media = bind_media(env, OUTPUT_ID, data)
    assert media.evidence['sha256'] == hashlib.sha256(data).hexdigest()

    transport = FixtureAcquisitionTransport(data)
    asset = runtime.acquire(frozen, transport=transport,
                            destination_dir=tmp_path / 'assets', media=media)
    assert transport.fetches == 1
    assert asset.provider_job_id == job_id
    assert asset.source_attempt_id == frozen.attempt.generation_attempt_id
    assert asset.provider_asset_id == OUTPUT_ID
    assert asset.sha256 == hashlib.sha256(data).hexdigest()

    fresh = env.store.read_runtime_lineage(frozen.attempt.generation_attempt_id, job_id)
    fresh_shot, fresh_plan, fresh_route, fresh_attempt, fresh_job, fresh_assets = fresh
    assert fresh_shot.shot_id == env.shot.shot_id
    assert fresh_job.status == 'SUCCEEDED' and fresh_job.dispatch_count == 1
    assert len(fresh_assets) == 1 and fresh_assets[0].asset_id == asset.asset_id

    eligibility = runtime.qc_eligibility(frozen, asset)
    assert eligibility['exact_lineage'] is True
    assert eligibility['technical_pass'] is True
    assert eligibility['metadata']['duration_s'] == pytest.approx(8.0, abs=0.5)


# 1: lineage mismatch at freeze fails before anything is persisted.
def test_freeze_rejects_reference_hash_mismatch(tmp_path, runtime_env):
    shot = ordinary_r2v_shot(OTHER)  # declares a reference that is not persisted
    with pytest.raises(ValueError):
        runtime_env.runtime.freeze(shot, flow_capabilities(),
            reference_asset=runtime_env.asset, reference_media_id=REMOTE,
            baseline_catalog_ids=[OTHER], started_at='2026-10-01T00:00:01+00:00')
    with sqlite3.connect(runtime_env.store.path) as connection:
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert jobs == 1  # only the valid frozen job exists


# 1 (restart form): modified inputs cannot rebinding a frozen shot.
def test_restart_with_changed_spec_fails_closed(runtime_env):
    env = runtime_env
    changed = env.shot.model_copy(update={'spec_version': 2})
    with pytest.raises(OwnerAmbiguityGate, match='RESTART'):
        env.runtime.freeze(changed, flow_capabilities(),
            reference_asset=env.asset, reference_media_id=REMOTE,
            reference_filename=REFERENCE_FILENAME_2, baseline_catalog_ids=[OTHER],
            started_at='2026-10-01T00:00:02+00:00')


def test_restart_with_identical_inputs_resumes_same_job(runtime_env):
    env = runtime_env
    again = env.runtime.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, baseline_catalog_ids=[OTHER],
        started_at='2099-01-01T00:00:00+00:00')
    assert again.job.provider_job_id == env.frozen.job.provider_job_id
    assert again.job.correlation_evidence['prompt'] == \
        env.frozen.job.correlation_evidence['prompt']


# 2: a non-Flow route/provider cannot enter the runtime at all.
def test_freeze_rejects_non_flow_provider(runtime_env):
    env = runtime_env
    unclaimed = ordinary_r2v_shot(env.asset.asset_id,
                                  shot_id='FLOW_R2V_RUNTIME_NONFLOW_002')
    with pytest.raises(OwnerAmbiguityGate, match='PROVIDER_UNQUALIFIED'):
        env.runtime.freeze(unclaimed, flow_capabilities('provider_full'),
            reference_asset=env.asset, reference_media_id=REMOTE,
            baseline_catalog_ids=[OTHER], started_at='2026-10-01T00:00:03+00:00')
    with sqlite3.connect(env.store.path) as connection:
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert jobs == 1  # nothing was persisted for the rejected provider


# 3 + 4: attestation is mandatory and scope-exact before any reservation.
@pytest.mark.parametrize('attestation', [None, 'tampered'])
def test_runtime_reservation_requires_valid_attestation(runtime_env, attestation):
    env = runtime_env
    if attestation == 'tampered':
        attestation = {**env.attestation,
                       'attestation_id': 'refbind_' + 'c' * 64}
    elif attestation is None:
        attestation = {}
    with pytest.raises(OwnerAmbiguityGate):
        env.runtime.reserve(env.frozen, attestation=attestation,
                            evidence_dir=env.attestation_dir)
    assert env.store.read_provider_job(
        env.frozen.job.provider_job_id).dispatch_count == 0


# 5: account scope drift fails closed at the composed boundary.
def test_account_scope_drift_blocked(runtime_env):
    env = runtime_env
    other = FlowR2VShotRuntime(env.store, project_id=PROJECT,
                               account_id='other_scope_account')
    with pytest.raises(OwnerAmbiguityGate, match='SCOPE_MISMATCH'):
        other.reserve(env.frozen, attestation=env.attestation,
                      evidence_dir=env.attestation_dir)
    assert env.store.read_provider_job(
        env.frozen.job.provider_job_id).dispatch_count == 0


# 6: the frozen prompt cannot drift after freeze.
def test_frozen_prompt_cannot_be_rewritten(runtime_env):
    env = runtime_env
    job = env.store.read_provider_job(env.frozen.job.provider_job_id)
    drifted = job.model_copy(update={'correlation_evidence': {
        **job.correlation_evidence, 'prompt': job.correlation_evidence['prompt'] + ' x'}})
    with pytest.raises(ValueError, match='FROZEN_PROVIDER_INTENT_CHANGED'):
        env.store.save_provider_job(drifted)


# 7: neither the guard nor attribution works before the durable reservation.
def test_mutation_before_reservation_blocked(runtime_env):
    env = runtime_env
    with pytest.raises(OwnerAmbiguityGate, match='NOT_RESERVED'):
        env.runtime.arm_native_guard(env.frozen)
    with pytest.raises(OwnerAmbiguityGate, match='NOT_RESERVED'):
        env.runtime.attribute_backend_output(env.frozen, [])
    assert env.store.read_output_bindings(env.frozen.job.provider_job_id) == []


def test_provider_facts_require_observed_request(runtime_env):
    reserve(runtime_env)
    with pytest.raises(OwnerAmbiguityGate, match='REQUEST_NOT_OBSERVED'):
        runtime_env.runtime.observe_provider_response(runtime_env.frozen, status=200)
    with pytest.raises(OwnerAmbiguityGate, match='REQUEST_NOT_OBSERVED'):
        runtime_env.runtime.observe_provider_acceptance(
            runtime_env.frozen, provider_reference='remote-acceptance-x')


# 8: duplicate/re-entry mutation is reconciliation only.
def test_duplicate_reservation_rejected(runtime_env):
    reserve(runtime_env)
    with pytest.raises(OwnerAmbiguityGate, match='RECONCILE_ONLY'):
        reserve(runtime_env)
    with pytest.raises(RuntimeError, match='budget already consumed'):
        runtime_env.store.reserve_dispatch(runtime_env.frozen.job.provider_job_id)


# 9: observed request plus acceptance without a backend output stays unresolved.
def test_request_without_backend_output_stays_unresolved(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    marker = film_marker(env.frozen.job.provider_job_id)
    unrelated = make_veo31_video_record(OUTPUT_ID, PROJECT, REMOTE,
        REFERENCE_FILENAME_2, film_marker('job_' + 'd' * 64),
        model=contract.MODEL_VEO_3_1_LITE)
    assert env.runtime.attribute_backend_output(env.frozen, [unrelated]) is None
    job_id = env.frozen.job.provider_job_id
    assert env.store.read_output_bindings(job_id) == []
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    transport = FixtureAcquisitionTransport(data)
    with pytest.raises(OwnerAmbiguityGate, match='NOT_SUCCEEDED'):
        env.runtime.acquire(env.frozen, transport=transport,
                            destination_dir=tmp_path / 'assets',
                            media=bind_media(env, OUTPUT_ID, data))
    assert transport.fetches == 0
    decision = recovery_decision(env.store.read_provider_job(job_id),
                                 env.store.read_dispatch_facts(job_id))
    assert decision.classification == 'DISPATCH_CONFIRMED'
    assert decision.may_submit is False


# 10: a preexisting output in the frozen baseline cannot be owned.
def test_preexisting_output_cannot_be_owned(runtime_env):
    env = runtime_env
    reserve(env)
    marker = film_marker(env.frozen.job.provider_job_id)
    # OTHER is part of the frozen pre-dispatch baseline catalog snapshot.
    row = make_veo31_video_record(OTHER, PROJECT, REMOTE, REFERENCE_FILENAME_2,
        marker, model=contract.MODEL_VEO_3_1_LITE)
    with pytest.raises(contract.ContractError, match='PREEXISTING'):
        env.runtime.attribute_backend_output(env.frozen, [row])
    assert env.store.read_output_bindings(env.frozen.job.provider_job_id) == []


# 11: wrong reference/model lineage cannot be owned.
@pytest.mark.parametrize('reference,model', [
    (OTHER, contract.MODEL_VEO_3_1_LITE),
    (REMOTE, contract.MODEL_VEO_3_1_FAST_LANDSCAPE),
])
def test_wrong_lineage_cannot_be_owned(runtime_env, reference, model):
    env = runtime_env
    reserve(env)
    marker = film_marker(env.frozen.job.provider_job_id)
    row = make_veo31_video_record(OUTPUT_ID, PROJECT, reference,
        REFERENCE_FILENAME_2, marker, model=model)
    with pytest.raises(contract.ContractError):
        env.runtime.attribute_backend_output(env.frozen, [row])
    assert env.store.read_output_bindings(env.frozen.job.provider_job_id) == []


# 12: multiple marker-matching candidates are ambiguous, never owned.
def test_multiple_candidates_fail_closed(runtime_env):
    env = runtime_env
    reserve(env)
    marker = film_marker(env.frozen.job.provider_job_id)
    rows = [make_veo31_video_record(output_id, PROJECT, REMOTE,
        REFERENCE_FILENAME_2, marker, model=contract.MODEL_VEO_3_1_LITE)
        for output_id in (OUTPUT_ID, SECOND_OUTPUT_ID)]
    with pytest.raises(contract.ContractError, match='COLLISION'):
        env.runtime.attribute_backend_output(env.frozen, rows)


# 13: an output owned by another ProviderJob cannot be rebound here.
def test_output_of_another_job_cannot_be_rebound(runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    output_id, _ = own_output(env)
    # A second ordinary shot reserves its own budget and claims the same output.
    second_shot = ordinary_r2v_shot(env.asset.asset_id,
                                    shot_id='FLOW_R2V_RUNTIME_ORDINARY_002')
    second_frozen = env.runtime.freeze(second_shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, baseline_catalog_ids=[OTHER],
        started_at='2026-10-01T00:10:00+00:00')
    env.runtime.reserve(second_frozen, attestation=env.attestation,
                        evidence_dir=env.attestation_dir)
    env.store.record_dispatch_fact(second_frozen.job.provider_job_id,
        'REMOTE_IDENTITY_OBSERVED', {'output_id': output_id, 'method': 'test_claim'})
    with pytest.raises(ValueError, match='OUTPUT_ALREADY_BOUND'):
        env.runtime.boundary.bind_owned_output(
            second_frozen.job.provider_job_id, output_id)


# 14: media identity/project/resource mismatch fails closed.
def test_media_identity_mismatch_blocked(runtime_env):
    env = runtime_env
    reserve(env)
    payload, _ = video_row(OUTPUT_ID)
    payload[1] = OTHER
    with pytest.raises(contract.ContractError):
        env.runtime.boundary.acquire_bound_media(payload, intent=env.frozen.intent,
            media_id=OUTPUT_ID, data=b'x' * 4,
            response_url=f'https://flow-content.google/video/{OUTPUT_ID}',
            status=200, headers={'content-type': 'video/mp4', 'content-length': '4'})


# 15: declared bytes and downloaded bytes must both be exact.
def test_download_bytes_mismatch_blocked(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    # Declared size disagreeing with the payload fails at the boundary.
    payload, _ = video_row(OUTPUT_ID, size=len(data) + 1)
    with pytest.raises(contract.ContractError):
        env.runtime.boundary.acquire_bound_media(payload, intent=env.frozen.intent,
            media_id=OUTPUT_ID, data=data,
            response_url=f'https://flow-content.google/video/{OUTPUT_ID}',
            status=200, headers={'content-type': 'video/mp4',
                                 'content-length': str(len(data))})
    # Bytes that differ from the bound evidence cannot become the Asset.
    media = bind_media(env, OUTPUT_ID, data)
    # Non-video bytes fail even earlier, at technical media validation.
    transport = FixtureAcquisitionTransport(data, corrupt=True)
    with pytest.raises(ValueError):
        env.runtime.acquire(env.frozen, transport=transport,
                            destination_dir=tmp_path / 'assets', media=media)
    # Technically valid but different bytes still cannot pass as the bound
    # output: the runtime's bound-media SHA gate rejects the drift.
    other_bytes = mp4_fixture(tmp_path / 'fixture_other.mp4', width=328)
    assert other_bytes != data
    transport = FixtureAcquisitionTransport(other_bytes)
    with pytest.raises(OwnerAmbiguityGate, match='ACQUIRED_BYTES_DRIFT'):
        env.runtime.acquire(env.frozen, transport=transport,
                            destination_dir=tmp_path / 'assets', media=media)
    from film_pipeline.live_runtime import file_sha256
    persisted = list((tmp_path / 'assets').glob('*.mp4'))
    assert hashlib.sha256(data).hexdigest() not in {
        file_sha256(path) for path in persisted}


# 16: an existing local file without an acquisition receipt is rejected.
def test_existing_file_without_receipt_rejected(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    destination = acquired_destination(env, OUTPUT_ID)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b'unattributed preexisting bytes')
    media = bind_media(env, OUTPUT_ID, data)
    with pytest.raises(ValueError, match='EXISTING_FILE_WITHOUT_ACQUISITION_RECEIPT'):
        env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                            destination_dir=destination.parent, media=media)


# 17: partial/staging bytes are never accepted as the final Asset.
def test_staging_bytes_never_become_asset(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    staging = acquired_destination(env, OUTPUT_ID).with_name(
        acquired_destination(env, OUTPUT_ID).stem + '.partial.mp4')
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_bytes(b'partial garbage')
    media = bind_media(env, OUTPUT_ID, data)
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                                destination_dir=staging.parent, media=media)
    assert asset.sha256 == hashlib.sha256(data).hexdigest()
    assert not staging.exists()


# 18: restart after reservation can never create a second mutation.
def test_restart_after_reservation_stays_reconcile_only(runtime_env):
    env = runtime_env
    reserve(env)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    again = restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, baseline_catalog_ids=[OTHER],
        started_at='2099-01-01T00:00:00+00:00')
    assert again.job.provider_job_id == env.frozen.job.provider_job_id
    with pytest.raises(OwnerAmbiguityGate, match='RECONCILE_ONLY'):
        restarted.reserve(again, attestation=env.attestation,
                          evidence_dir=env.attestation_dir)
    decision = recovery_decision(env.store.read_provider_job(again.job.provider_job_id),
                                 env.store.read_dispatch_facts(again.job.provider_job_id))
    assert decision.may_submit is False
    assert decision.action == 'RECONCILE_ONLY'


# 19: restart after exact output binding continues acquisition only.
def test_restart_after_binding_continues_acquisition(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    media = bind_media(env, OUTPUT_ID, data)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    asset = restarted.acquire(restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, baseline_catalog_ids=[OTHER],
        started_at='2099-01-01T00:00:00+00:00'),
        transport=FixtureAcquisitionTransport(data),
        destination_dir=tmp_path / 'assets', media=media)
    assert asset.sha256 == hashlib.sha256(data).hexdigest()
    restarted_executor = LiveRuntimeExecutor(env.store, FixtureAcquisitionTransport(data))
    decision = restarted_executor.recovery_decision(env.frozen.job.provider_job_id)
    assert decision.classification == 'ACQUIRED'
    assert decision.may_submit is False


# 20: restart after completed acquisition yields the same exact Asset, no fetch.
def test_restart_after_acquisition_is_idempotent(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    media = bind_media(env, OUTPUT_ID, data)
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                                destination_dir=tmp_path / 'assets', media=media)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    refrozen = restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, baseline_catalog_ids=[OTHER],
        started_at='2099-01-01T00:00:00+00:00')
    second_transport = FixtureAcquisitionTransport(data)
    same = restarted.acquire(refrozen, transport=second_transport,
                             destination_dir=tmp_path / 'assets', media=media)
    assert second_transport.fetches == 0
    assert (same.asset_id, same.sha256, same.uri_or_path) == \
           (asset.asset_id, asset.sha256, asset.uri_or_path)
    lineage = env.store.read_runtime_lineage(refrozen.attempt.generation_attempt_id,
                                             refrozen.job.provider_job_id)
    assert len(lineage[5]) == 1


# 21: QC gates reject tampered Asset bytes on fresh readback.
def test_qc_rejects_tampered_asset_bytes(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    media = bind_media(env, OUTPUT_ID, data)
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                                destination_dir=tmp_path / 'assets', media=media)
    assert env.runtime.qc_eligibility(env.frozen, asset)['technical_pass'] is True
    path = Path(asset.uri_or_path)
    original = path.read_bytes()
    path.write_bytes(original[:-1] + bytes([original[-1] ^ 0xFF]))
    result = env.runtime.qc_eligibility(env.frozen, asset)
    assert result['exact_lineage'] is True
    assert result['technical_pass'] is False
    path.write_bytes(original)


# 22: the generic runtime has no Slice-0011 semantic dependency.
def test_runtime_module_has_no_slice_coupling():
    source = (ROOT / 'src' / 'film_pipeline' / 'flow_r2v_runtime.py').read_text(
        encoding='utf-8')
    assert not re.search(r'slice0011|slice0010|CHAR_CONTINUITY|reference_qualification',
                         source)


# Compact adapter: qualified envelope enforcement is mechanical and fail-closed.
def test_compact_prompt_is_deterministic_and_marked(runtime_env):
    env = runtime_env
    job_id = env.frozen.job.provider_job_id
    plan = env.frozen.plan
    first = compact_r2v_prompt(plan, job_id, model=contract.MODEL_VEO_3_1_LITE)
    second = compact_r2v_prompt(plan, job_id, model=contract.MODEL_VEO_3_1_LITE)
    assert first == second
    assert first.text.endswith('\n' + first.marker)
    assert first.marker == film_marker(job_id)
    assert first.version == COMPACT_VERSION


def _compile_plan_for(env, shot):
    from film_pipeline.flow_r2v_runtime import compile_plan
    return compile_plan(shot, flow_capabilities(), env.asset)


def test_compact_prompt_rejects_marker_injection(runtime_env):
    env = runtime_env
    poisoned = env.shot.model_copy(update={
        'dramatic_purpose': 'Establish [FILM-job_' + 'a' * 64 + '] marker injection.'})
    plan = _compile_plan_for(env, poisoned)
    with pytest.raises(OwnerAmbiguityGate, match='MARKER_COLLISION'):
        compact_r2v_prompt(plan, env.frozen.job.provider_job_id,
                           model=contract.MODEL_VEO_3_1_LITE)


def test_compact_prompt_rejects_unqualified_duration(runtime_env):
    env = runtime_env
    changed = env.shot.model_copy(update={'duration_target_s': 6})
    plan = _compile_plan_for(env, changed)
    with pytest.raises(OwnerAmbiguityGate, match='DURATION_UNSUPPORTED'):
        compact_r2v_prompt(plan, env.frozen.job.provider_job_id,
                           model=contract.MODEL_VEO_3_1_LITE)


def test_compact_prompt_rejects_over_limit_body(runtime_env):
    env = runtime_env
    verbose = env.shot.model_copy(update={
        'dramatic_purpose': 'Establish an extraordinarily detailed rain-soaked '
                            'urban alley at night with layered reflections, steam, '
                            'distant traffic, neon signage, puddle ripples and a '
                            'slow cathartic reveal of the skyline beyond. ' * 3})
    plan = _compile_plan_for(env, verbose)
    with pytest.raises(OwnerAmbiguityGate, match='COMPACT_PROMPT_LIMIT'):
        compact_r2v_prompt(plan, env.frozen.job.provider_job_id,
                           model=contract.MODEL_VEO_3_1_LITE)
