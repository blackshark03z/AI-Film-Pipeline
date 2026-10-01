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
    QualifiedFlowCatalogCapability,
    compact_r2v_prompt,
    qualified_catalog_snapshot,
    qualify_flow_catalog_source,
)
from film_pipeline.live_runtime import LiveRuntimeExecutor
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
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


def offline_flow_session(records, *, project_id=PROJECT):
    """Test-only seam: an EXACT, FRESH FlowReferenceRpcSession constructed
    without opening a browser. Exactly like production, the fresh session's
    catalog_fingerprint is None until its first qualified catalog read —
    nothing is pre-qualified here. The concrete class catalog() method is
    patched per-test by the autouse fixture below and emulates the real
    lifecycle: one read → validate/establish the qualified fingerprint →
    return records. Production qualification checks stay untouched."""
    session = FlowReferenceRpcSession(profile_path=Path('offline-unused'),
                                      project_id=project_id)
    session._offline_rows = [list(row) for row in records]
    session._offline_calls = 0
    return session


@pytest.fixture(autouse=True)
def _offline_flow_catalog(monkeypatch):
    """Patch the concrete FlowReferenceRpcSession.catalog implementation for
    the duration of each test (restored afterwards), emulating the real
    read lifecycle: before the read the fingerprint is None; the read itself
    establishes the qualified baseline fingerprint and returns records.
    Only the concrete class is patched — capabilities bind capture to this
    class function, so this seam is the single offline path and weakens no
    production check."""
    def offline_catalog(self, *, contract_version=contract.CONTRACT_VERSION):
        self._offline_calls += 1
        self.catalog_fingerprint = contract.QUALIFIED_BASELINE_FINGERPRINT
        return [list(row) for row in self._offline_rows]
    monkeypatch.setattr(FlowReferenceRpcSession, 'catalog', offline_catalog)
    yield


def catalog_capability(records, *, project_id=PROJECT):
    """Mint a production capability for an offline exact-type Flow session."""
    return qualify_flow_catalog_source(
        offline_flow_session(records, project_id=project_id))


@pytest.fixture
def runtime_env(tmp_path, _offline_flow_catalog):
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
    session_double = offline_flow_session(catalog_records(OTHER))
    catalog_source = qualify_flow_catalog_source(session_double)
    frozen = runtime.freeze(shot, flow_capabilities(), reference_asset=asset,
        reference_media_id=REMOTE, reference_filename=REFERENCE_FILENAME_2,
        catalog_source=catalog_source, started_at='2026-10-01T00:00:00+00:00')
    return SimpleNamespace(asset=asset, attestation=attestation,
        attestation_dir=attestation_dir, runtime=runtime, store=store, shot=shot,
        frozen=frozen, catalog_source=catalog_source, session=session_double,
        tmp_path=tmp_path)


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


def media_payload(env, output_id, data):
    """Qualified synthetic as29s video record declaring exactly these bytes."""
    payload, _ = video_row(output_id, size=len(data))
    return payload


def catalog_records(*ids, project=PROJECT):
    """Synthetic qualified provider catalog rows (image-shape)."""
    return [[identity, project, 'IMAGE', 'CAE', None, None, None] for identity in ids]


def acquired_destination(env, output_id):
    return (env.tmp_path / 'assets' / f"{sha256(output_id)[:24]}.mp4")


# The exact offline end-to-end vertical: ordinary shot → QC-handoff eligibility.
def test_generic_r2v_shot_end_to_end_offline(tmp_path, runtime_env):
    env, runtime, frozen = runtime_env, runtime_env.runtime, runtime_env.frozen
    job_id = frozen.job.provider_job_id

    prompt = frozen.job.correlation_evidence['prompt']
    marker = film_marker(job_id)
    body = prompt[:len(prompt) - len(marker) - 1]
    assert prompt.endswith(' ' + marker)
    assert '\n' not in prompt  # qualified native-UI single-line serialization
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
    payload = media_payload(env, OUTPUT_ID, data)

    transport = FixtureAcquisitionTransport(data)
    asset = runtime.acquire(frozen, transport=transport,
                            destination_dir=tmp_path / 'assets', media_payload=payload)
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
            catalog_source=runtime_env.catalog_source,
            started_at='2026-10-01T00:00:01+00:00')
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
            reference_filename=REFERENCE_FILENAME_2, catalog_source=env.catalog_source,
            started_at='2026-10-01T00:00:02+00:00')


def test_restart_with_identical_inputs_resumes_same_job(runtime_env):
    env = runtime_env
    again = env.runtime.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=env.catalog_source,
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
            catalog_source=env.catalog_source, started_at='2026-10-01T00:00:03+00:00')
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
                            media_payload=media_payload(env, OUTPUT_ID, data))
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
        reference_filename=REFERENCE_FILENAME_2, catalog_source=env.catalog_source,
        started_at='2026-10-01T00:10:00+00:00')
    env.runtime.reserve(second_frozen, attestation=env.attestation,
                        evidence_dir=env.attestation_dir)
    env.store.record_dispatch_fact(second_frozen.job.provider_job_id,
        'REMOTE_IDENTITY_OBSERVED', {'output_id': output_id, 'method': 'test_claim'})
    with pytest.raises(ValueError, match='OUTPUT_ALREADY_BOUND'):
        env.runtime.boundary.bind_owned_output(
            second_frozen.job.provider_job_id, output_id)


# 14: media identity/project/resource mismatch fails closed inside the
# runtime-owned verification (no caller evidence exists anymore).
def test_media_identity_mismatch_blocked(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    payload = media_payload(env, OUTPUT_ID, data)
    payload[1] = OTHER  # wrong project row
    with pytest.raises(OwnerAmbiguityGate, match='MEDIA_PAYLOAD_UNQUALIFIED'):
        env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                            destination_dir=tmp_path / 'assets', media_payload=payload)
    wrong_id = media_payload(env, OTHER, data)  # payload for another media id
    with pytest.raises(OwnerAmbiguityGate, match='MEDIA_PAYLOAD_UNQUALIFIED'):
        env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                            destination_dir=tmp_path / 'assets', media_payload=wrong_id)


# 15: declared bytes and downloaded bytes must both be exact, and the exact
# flow_media contract is enforced by the runtime BEFORE anything persists.
def test_download_bytes_mismatch_blocked(tmp_path, runtime_env):
    env = runtime_env
    job_id = env.frozen.job.provider_job_id
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    payload = media_payload(env, OUTPUT_ID, data)
    # A payload declaring a wrong byte size passes parsing but cannot bind the
    # actual staged bytes: the qualified size contract fails before anything
    # persists.
    oversized, _ = video_row(OUTPUT_ID, size=len(data) + 1)
    with pytest.raises(contract.ContractError):
        env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                            destination_dir=tmp_path / 'assets', media_payload=oversized)
    # An adapter delivering different valid bytes cannot pass: the runtime
    # binds the parsed resource to the staged bytes before any receipt or
    # Asset can exist.
    other_bytes = mp4_fixture(tmp_path / 'fixture_other.mp4', width=640)
    assert len(other_bytes) != len(data)  # fixture premise: sizes must differ
    assert other_bytes != data
    with pytest.raises(contract.ContractError):
        env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(other_bytes),
                            destination_dir=tmp_path / 'assets', media_payload=payload)
    # Non-video bytes fail the same runtime-owned gate.
    with pytest.raises(contract.ContractError):
        env.runtime.acquire(env.frozen,
                            transport=FixtureAcquisitionTransport(data, corrupt=True),
                            destination_dir=tmp_path / 'assets', media_payload=payload)
    # Nothing was persisted: no receipt, no Asset, despite the lying transport.
    assert env.store.read_acquisition_record(job_id, OUTPUT_ID, completed=True) is None
    assert env.store.read_runtime_lineage(
        env.frozen.attempt.generation_attempt_id, job_id)[5] == ()


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
    payload = media_payload(env, OUTPUT_ID, data)
    with pytest.raises(ValueError, match='EXISTING_FILE_WITHOUT_ACQUISITION_RECEIPT'):
        env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                            destination_dir=destination.parent, media_payload=payload)


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
    payload = media_payload(env, OUTPUT_ID, data)
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                                destination_dir=staging.parent, media_payload=payload)
    assert asset.sha256 == hashlib.sha256(data).hexdigest()
    assert not staging.exists()


# 18: restart after reservation can never create a second mutation.
def test_restart_after_reservation_stays_reconcile_only(runtime_env):
    env = runtime_env
    reserve(env)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    again = restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=env.catalog_source,
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
    payload = media_payload(env, OUTPUT_ID, data)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    asset = restarted.acquire(restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=env.catalog_source,
        started_at='2099-01-01T00:00:00+00:00'),
        transport=FixtureAcquisitionTransport(data),
        destination_dir=tmp_path / 'assets', media_payload=payload)
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
    payload = media_payload(env, OUTPUT_ID, data)
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                                destination_dir=tmp_path / 'assets', media_payload=payload)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    refrozen = restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=env.catalog_source,
        started_at='2099-01-01T00:00:00+00:00')
    second_transport = FixtureAcquisitionTransport(data)
    same = restarted.acquire(refrozen, transport=second_transport,
                             destination_dir=tmp_path / 'assets', media_payload=payload)
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
    payload = media_payload(env, OUTPUT_ID, data)
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                                destination_dir=tmp_path / 'assets', media_payload=payload)
    assert env.runtime.qc_eligibility(env.frozen, asset)['technical_pass'] is True
    path = Path(asset.uri_or_path)
    original = path.read_bytes()
    path.write_bytes(original[:-1] + bytes([original[-1] ^ 0xFF]))
    result = env.runtime.qc_eligibility(env.frozen, asset)
    assert result['exact_lineage'] is True
    assert result['technical_pass'] is False
    path.write_bytes(original)


# C3/F1 adversarial reproduction: a hand-frozen foreign job without the frozen
# baseline snapshot must fail closed at reservation AND attribution.
def test_hostile_job_without_baseline_snapshot_fails_closed(runtime_env):
    from film_pipeline.core import canonical_json
    env = runtime_env
    job = env.frozen.job
    hostile_id = 'job_' + 'e' * 64
    hostile = job.model_copy(update={'provider_job_id': hostile_id,
                                     'pre_dispatch_snapshot': {}})
    with sqlite3.connect(env.store.path) as connection:
        connection.execute('INSERT INTO provider_jobs VALUES (?,?,?,?,?)',
            (hostile.provider_job_id, job.generation_attempt_id, job.provider_id, 0,
             canonical_json(hostile.model_dump(mode='json'))))
    handle = SimpleNamespace(job=SimpleNamespace(provider_job_id=hostile_id),
                             intent=env.frozen.intent)
    with pytest.raises(OwnerAmbiguityGate, match='BASELINE|CATALOG'):
        env.runtime.reserve(handle, attestation=env.attestation,
                            evidence_dir=env.attestation_dir)
    assert env.store.read_provider_job(hostile_id).dispatch_count == 0
    # Even a hostile job that obtained a reservation elsewhere cannot attribute
    # without the frozen pre-dispatch baseline.
    env.runtime.boundary.reserve_mutation(handle.job.provider_job_id,
        intent=env.frozen.intent, asset=env.asset, attestation=env.attestation,
        evidence_dir=env.attestation_dir)
    marker = film_marker(hostile_id)
    row = make_veo31_video_record(OUTPUT_ID, PROJECT, REMOTE, REFERENCE_FILENAME_2,
        marker, model=contract.MODEL_VEO_3_1_LITE)
    with pytest.raises(OwnerAmbiguityGate, match='BASELINE|CATALOG'):
        env.runtime.attribute_backend_output(handle, [row])
    assert env.store.read_output_bindings(hostile_id) == []


# C3/F1 companion: a valid frozen baseline cannot be silently substituted.
def test_baseline_project_drift_blocked(runtime_env):
    env = runtime_env
    foreign = FlowR2VShotRuntime(env.store, project_id=OTHER, account_id=ACCOUNT)
    with pytest.raises(OwnerAmbiguityGate, match='SCOPE_MISMATCH|PROJECT'):
        foreign.reserve(env.frozen, attestation=env.attestation,
                        evidence_dir=env.attestation_dir)


# C3/F3 adversarial reproduction: unqualified model fails at construction.
def test_runtime_rejects_unqualified_model_at_construction(runtime_env):
    with pytest.raises(OwnerAmbiguityGate):
        FlowR2VShotRuntime(runtime_env.store, project_id=PROJECT,
                           account_id=ACCOUNT, model='abra_r2v_8s')


# C3/F4 adversarial reproduction: restart classification is a runtime concern
# and never reports submit authority after reservation.
def test_recovery_classification_is_runtime_exposed(runtime_env):
    env = runtime_env
    fresh = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    before = fresh.recovery(env.frozen)
    assert before.classification == 'NOT_RESERVED'
    assert before.may_submit is False
    reserve(env)
    after = fresh.recovery(env.frozen)
    assert after.classification == 'INCONCLUSIVE'
    assert after.may_submit is False
    assert after.action == 'RECONCILE_ONLY'


# RUNTIME-HARDEN-001 Gap 1: the exact Techlead forged-BoundMedia reproduction
# can no longer reach Asset persistence.
def test_forged_bound_media_cannot_reach_asset_persistence(tmp_path, runtime_env):
    from film_pipeline.providers.flow_media import BoundMedia
    env = runtime_env
    job_id = env.frozen.job.provider_job_id
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    unrelated = mp4_fixture(tmp_path / 'unrelated.mp4', width=640)
    assert len(unrelated) != len(data)  # fixture premise: sizes must differ
    payload = media_payload(env, OUTPUT_ID, data)
    # The exact forged object: internally consistent evidence claiming the
    # unrelated bytes the adapter delivers (sha256/byte_size both match them).
    forged = BoundMedia(unrelated, {'version': 'flow-bound-media-20261001-v1',
        'media_id': OUTPUT_ID, 'project_id': PROJECT, 'kind': 'video',
        'response_id': OUTPUT_ID, 'response_project_id': PROJECT,
        'resource_host': 'flow-content.google', 'resource_path': f'/video/{OUTPUT_ID}',
        'response_status': 200, 'redirects': 0, 'byte_size': len(unrelated),
        'sha256': hashlib.sha256(unrelated).hexdigest(), 'mime_type': 'video/mp4',
        'width': None, 'height': None})
    # The runtime no longer accepts caller-created evidence at all...
    with pytest.raises(TypeError):
        env.runtime.acquire(env.frozen,
            transport=FixtureAcquisitionTransport(unrelated),
            destination_dir=tmp_path / 'assets', media=forged)
    # ...and the runtime-owned flow_media verification refuses the lying
    # bytes against the qualified payload before any receipt or Asset exists.
    with pytest.raises(contract.ContractError):
        env.runtime.acquire(env.frozen,
            transport=FixtureAcquisitionTransport(unrelated),
            destination_dir=tmp_path / 'assets', media_payload=payload)
    assert env.store.read_acquisition_record(job_id, OUTPUT_ID, completed=True) is None
    assert env.store.read_runtime_lineage(
        env.frozen.attempt.generation_attempt_id, job_id)[5] == ()
    # The honest path still persists exactly the qualified payload's bytes.
    asset = env.runtime.acquire(env.frozen,
        transport=FixtureAcquisitionTransport(data),
        destination_dir=tmp_path / 'assets', media_payload=payload)
    assert asset.sha256 == hashlib.sha256(data).hexdigest()


# RUNTIME-HARDEN-001 Gap 2: snapshot identity is content-bound.
def test_qualified_snapshot_identity_is_content_bound(runtime_env):
    from film_pipeline.flow_r2v_runtime import qualified_catalog_snapshot
    env = runtime_env
    full = qualified_catalog_snapshot(catalog_records(OTHER, SECOND_OUTPUT_ID),
                                      project_id=PROJECT)
    again = qualified_catalog_snapshot(catalog_records(OTHER, SECOND_OUTPUT_ID),
                                       project_id=PROJECT)
    assert full == again  # deterministic immutable identity
    omitted = qualified_catalog_snapshot(catalog_records(OTHER), project_id=PROJECT)
    assert omitted['catalog_ids'] != full['catalog_ids']
    assert omitted['snapshot_sha256'] != full['snapshot_sha256']
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG'):
        qualified_catalog_snapshot(catalog_records(OTHER, project=OTHER),
                                   project_id=PROJECT)
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG'):
        qualified_catalog_snapshot(catalog_records('not-a-uuid'), project_id=PROJECT)
    # The frozen job carries the derived snapshot; its identity recomputes.
    snap = env.frozen.job.pre_dispatch_snapshot
    basis = {'catalog_fingerprint': snap['catalog_fingerprint'],
             'catalog_ids': snap['catalog_ids'], 'project_id': snap['project_id']}
    assert snap['snapshot_sha256'] == sha256(basis)
    assert snap['catalog_ids'] == [OTHER.lower()]


# RUNTIME-HARDEN-001 Gap 2: an omitted preexisting row cannot be smuggled
# through a tampered snapshot, and cannot preserve the frozen identity.
def test_tampered_baseline_snapshot_cannot_attribute(runtime_env):
    from film_pipeline.core import canonical_json
    env = runtime_env
    job_id = env.frozen.job.provider_job_id
    stored = env.store.read_provider_job(job_id)
    tampered = stored.model_copy(update={'pre_dispatch_snapshot': {
        **stored.pre_dispatch_snapshot, 'catalog_ids': []}})
    with sqlite3.connect(env.store.path) as connection:
        connection.execute('UPDATE provider_jobs SET payload=? WHERE id=?',
            (canonical_json(tampered.model_dump(mode='json')), job_id))
    with pytest.raises(OwnerAmbiguityGate, match='BASELINE'):
        env.runtime.reserve(env.frozen, attestation=env.attestation,
                            evidence_dir=env.attestation_dir)
    assert env.store.read_provider_job(job_id).dispatch_count == 0
    # A post-reservation attempt against the tampered snapshot still fails
    # closed: the snapshot identity no longer recomputes, so attribution is
    # unreachable and no binding can appear.
    env.runtime.boundary.reserve_mutation(job_id, intent=env.frozen.intent,
        asset=env.asset, attestation=env.attestation,
        evidence_dir=env.attestation_dir)
    with pytest.raises(OwnerAmbiguityGate, match='BASELINE'):
        env.runtime.attribute_backend_output(env.frozen, [])
    assert env.store.read_output_bindings(job_id) == []


# RUNTIME-HARDEN-001 Gap 3: the freeze transaction is atomic.
def test_store_freeze_transaction_is_atomic(tmp_path, runtime_env):
    env = runtime_env
    store = env.store
    shot = ordinary_r2v_shot(env.asset.asset_id, shot_id='FLOW_R2V_ATOMIC_003')
    like = '%FLOW_R2V_ATOMIC_003%'

    def crash(self, connection, job):
        raise RuntimeError('simulated crash between path and job')

    from unittest.mock import patch
    with patch.object(SQLiteStore, '_insert_provider_job', crash):
        with pytest.raises(RuntimeError, match='simulated crash'):
            env.runtime.freeze(shot, flow_capabilities(), reference_asset=env.asset,
                reference_media_id=REMOTE, reference_filename=REFERENCE_FILENAME_2,
                catalog_source=env.catalog_source,
                started_at='2026-10-01T02:00:00+00:00')
    with sqlite3.connect(store.path) as connection:
        partial = {table: connection.execute(
            f'SELECT COUNT(*) FROM {table} WHERE payload LIKE ?', (like,)).fetchone()[0]
            for table in ('shot_specs', 'prompt_plans', 'routing_decisions',
                          'generation_attempts')}
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert partial == {'shot_specs': 0, 'prompt_plans': 0, 'routing_decisions': 0,
                       'generation_attempts': 0}
    assert jobs == 1  # only the pre-existing environment job
    # After the simulated failure the restart freezes cleanly: complete path
    # plus exactly one ProviderJob, and the shot can reserve.
    refrozen = env.runtime.freeze(shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2,
        catalog_source=env.catalog_source,
        started_at='2026-10-01T02:00:00+00:00')
    with sqlite3.connect(store.path) as connection:
        attempts = connection.execute(
            "SELECT COUNT(*) FROM generation_attempts WHERE json_extract(payload,'$.shot_id')=?",
            (shot.shot_id,)).fetchone()[0]
        shot_jobs = connection.execute(
            'SELECT COUNT(*) FROM provider_jobs WHERE id=?',
            (refrozen.job.provider_job_id,)).fetchone()[0]
    assert attempts == 1 and shot_jobs == 1
    env.runtime.reserve(refrozen, attestation=env.attestation,
                        evidence_dir=env.attestation_dir)
    assert env.store.read_provider_job(
        refrozen.job.provider_job_id).dispatch_count == 1


# RUNTIME-HARDEN-001 Gap 3: after commit the path is complete and exactly one
# ProviderJob exists for the frozen attempt.
def test_freeze_commit_produces_complete_path_and_one_job(runtime_env):
    env = runtime_env
    with sqlite3.connect(env.store.path) as connection:
        attempts = connection.execute(
            "SELECT COUNT(*) FROM generation_attempts WHERE json_extract(payload,'$.shot_id')=?",
            (env.shot.shot_id,)).fetchone()[0]
        jobs = connection.execute(
            'SELECT COUNT(*) FROM provider_jobs WHERE generation_attempt_id=?',
            (env.frozen.attempt.generation_attempt_id,)).fetchone()[0]
    assert attempts == 1 and jobs == 1
    shot, plan, route, attempt = env.store.read_path(
        env.frozen.attempt.generation_attempt_id)
    assert (shot.shot_id, plan.shot_id, route.shot_id) == (env.shot.shot_id,) * 3


# Self-review: the idempotent restart path cannot be subverted by a lying
# transport either — no fetch happens and the verified bytes are re-bound.
def test_restart_idempotent_acquisition_ignores_lying_transport(tmp_path, runtime_env):
    env = runtime_env
    reserve(env)
    release_request(env)
    own_output(env)
    data = mp4_fixture(tmp_path / 'fixture.mp4')
    unrelated = mp4_fixture(tmp_path / 'unrelated.mp4', width=640)
    assert len(unrelated) != len(data)  # fixture premise: sizes must differ
    payload = media_payload(env, OUTPUT_ID, data)
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
                                destination_dir=tmp_path / 'assets', media_payload=payload)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    refrozen = restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2,
        catalog_source=env.catalog_source,
        started_at='2099-01-01T00:00:00+00:00')
    liar = FixtureAcquisitionTransport(unrelated)
    same = restarted.acquire(refrozen, transport=liar,
                             destination_dir=tmp_path / 'assets', media_payload=payload)
    assert liar.fetches == 0
    assert (same.asset_id, same.sha256, same.uri_or_path) == \
           (asset.asset_id, asset.sha256, asset.uri_or_path)
    assert Path(same.uri_or_path).read_bytes() == data


THIRD_ID = '7c9e6679-7425-40de-944b-e07fc1f90ae7'


# RUNTIME-HARDEN-001 R2 proof 1 + 9: the runtime API has no raw-record path —
# the exact Techlead attack (forcing an empty/incomplete subset as authority)
# is no longer expressible.
def test_freeze_has_no_raw_record_path(runtime_env):
    env = runtime_env
    base = dict(reference_asset=env.asset, reference_media_id=REMOTE,
                reference_filename=REFERENCE_FILENAME_2,
                catalog_source=catalog_capability(catalog_records(OTHER)),
                started_at='2026-10-02T00:00:00+00:00')
    with pytest.raises(TypeError):
        env.runtime.freeze(env.shot, flow_capabilities(),
                           baseline_catalog_records=[], **base)
    with pytest.raises(TypeError):
        env.runtime.freeze(env.shot, flow_capabilities(),
                           baseline_catalog_ids=[OTHER], **base)
    import inspect
    params = set(inspect.signature(env.runtime.freeze).parameters)
    assert 'catalog_source' in params
    assert not any('record' in name or 'baseline' in name or name.endswith('_ids')
                   for name in params)


# RUNTIME-HARDEN-001 R3: the exact Techlead forgery — a five-line duck-typed
# object that merely looks like a catalog source — is rejected before any
# ProviderJob can exist.
def test_fake_subset_source_rejected(runtime_env):
    from film_pipeline.core import ProviderCapabilities
    env = runtime_env

    class FakeSubsetSource:
        catalog_fingerprint = contract.QUALIFIED_BASELINE_FINGERPRINT

        def catalog(self):
            return []

    shot = ordinary_r2v_shot(env.asset.asset_id, shot_id='FLOW_R2V_R3_FAKE_001')
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_SOURCE_UNQUALIFIED'):
        env.runtime.freeze(shot, flow_capabilities(), reference_asset=env.asset,
            reference_media_id=REMOTE, reference_filename=REFERENCE_FILENAME_2,
            catalog_source=FakeSubsetSource(),
            started_at='2026-10-02T01:01:00+00:00')
    with sqlite3.connect(env.store.path) as connection:
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert jobs == 1  # nothing persisted for the forged source
    # Even a capability look-alike wrapper around a real capability is rejected.
    class Wrapper:
        def __init__(self, capability):
            self._capability = capability

        def capture(self):
            return self._capability.capture()

        @property
        def fingerprint(self):
            return self._capability.fingerprint

        @property
        def project_id(self):
            return self._capability.project_id

    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_SOURCE_UNQUALIFIED'):
        env.runtime.freeze(env.shot.model_copy(update={'shot_id': 'FLOW_R2V_R3_FAKE_002'}),
            flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
            reference_filename=REFERENCE_FILENAME_2,
            catalog_source=Wrapper(env.catalog_source),
            started_at='2026-10-02T01:02:00+00:00')
    # A capability minted for another project cannot freeze this runtime's shot.
    foreign = catalog_capability(catalog_records(OTHER), project_id=OTHER)
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_SOURCE_PROJECT_MISMATCH'):
        env.runtime.freeze(env.shot.model_copy(update={'shot_id': 'FLOW_R2V_R3_FAKE_003'}),
            flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
            reference_filename=REFERENCE_FILENAME_2, catalog_source=foreign,
            started_at='2026-10-02T01:03:00+00:00')
    # The real qualified path is the only accepted shape.
    real = catalog_capability(catalog_records(OTHER))
    frozen = env.runtime.freeze(env.shot.model_copy(update={'shot_id': 'FLOW_R2V_R3_REAL_004'}),
        flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=real,
        started_at='2026-10-02T01:04:00+00:00')
    assert frozen.job.pre_dispatch_snapshot['catalog_ids'] == [OTHER.lower()]


# RUNTIME-HARDEN-001 R4: the exact Techlead inheritance forgery — a subclass
# overriding catalog() — is rejected by BOTH minting entry points.
def test_subclass_cannot_mint_capability(runtime_env):
    env = runtime_env

    class FakeQualifiedSubclass(FlowReferenceRpcSession):
        def __init__(self):
            self.project_id = PROJECT
            self.catalog_fingerprint = contract.QUALIFIED_BASELINE_FINGERPRINT

        def catalog(self, **kwargs):
            return []

    forged = FakeQualifiedSubclass()
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_SOURCE_UNQUALIFIED'):
        qualify_flow_catalog_source(forged)
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_SOURCE_UNQUALIFIED'):
        QualifiedFlowCatalogCapability(FakeQualifiedSubclass())
    with sqlite3.connect(env.store.path) as connection:
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert jobs == 1  # nothing persisted for the forged subclass


# R4: even on an EXACT-type session, instance-attribute shadowing cannot
# replace catalog semantics: capture binds to the concrete class function.
# The shadowed liar returns []; the class implementation returns the real
# observation — the frozen snapshot proves which one the runtime consumed.
def test_instance_shadowing_cannot_replace_catalog_semantics(runtime_env):
    env = runtime_env
    shadowed = offline_flow_session(catalog_records(OTHER))
    shadow_calls = []

    def liar(**kwargs):
        shadow_calls.append(1)
        return []

    shadowed.catalog = liar  # instance attribute, not the class function
    capability = qualify_flow_catalog_source(shadowed)  # exact type + qualified state
    assert type(shadowed) is FlowReferenceRpcSession
    frozen = env.runtime.freeze(
        env.shot.model_copy(update={'shot_id': 'FLOW_R2V_R4_SHADOW_001'}),
        flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=capability,
        started_at='2026-10-02T02:00:00+00:00')
    # The concrete class implementation produced the snapshot; the shadowed
    # instance attribute was never consulted.
    assert frozen.job.pre_dispatch_snapshot['catalog_ids'] == [OTHER.lower()]
    assert shadowed._offline_calls == 1
    assert shadow_calls == []


# R4 proof 9: no test-only authority bypass exists in production code — the
# runtime module contains no offline/test seam markers, and the qualification
# binds to the exact concrete boundary required.
def test_runtime_module_has_no_test_seam():
    source = (ROOT / 'src' / 'film_pipeline' / 'flow_r2v_runtime.py').read_text(
        encoding='utf-8')
    assert not re.search(r'_offline|test-only|monkeypatch|TEST_ONLY|offline_rows',
                         source)
    assert 'type(self.session) is not FlowReferenceRpcSession' in source
    assert 'FlowReferenceRpcSession.catalog(self.session)' in source


# RUNTIME-HARDEN-001 R5 proof 1 + 2 + 12: a fresh exact-type session with a
# None fingerprint mints the capability, and minting performs ZERO catalog
# reads. A fresh session has no _offline_rows, so any attempted read inside
# minting would crash this test loudly instead of passing silently.
def test_fresh_session_mints_capability_with_zero_reads(runtime_env):
    fresh = FlowReferenceRpcSession(profile_path=Path('fresh-unused'),
                                    project_id=PROJECT)
    assert type(fresh) is FlowReferenceRpcSession
    assert fresh.catalog_fingerprint is None  # exactly the production state
    capability = qualify_flow_catalog_source(fresh)  # no read; no exception
    assert fresh.catalog_fingerprint is None  # mint performed zero reads
    assert not hasattr(fresh, '_offline_calls')  # the class impl never ran
    # Proof 12: the mint-time check contains no fingerprint precondition.
    import inspect
    from film_pipeline.flow_r2v_runtime import QualifiedFlowCatalogCapability
    assert 'catalog_fingerprint' not in inspect.getsource(
        QualifiedFlowCatalogCapability.__post_init__)


# R5 proofs 3 + 4 + 5: a fresh freeze performs EXACTLY ONE catalog read; that
# same read takes the fingerprint from None to qualified; and the exact
# records it returned become the frozen snapshot.
def test_fresh_session_lifecycle_single_read(runtime_env):
    env = runtime_env
    fresh = offline_flow_session(catalog_records(OTHER, SECOND_OUTPUT_ID))
    capability = qualify_flow_catalog_source(fresh)
    assert fresh.catalog_fingerprint is None  # before: unqualified
    frozen = env.runtime.freeze(
        ordinary_r2v_shot(env.asset.asset_id, shot_id='FLOW_R2V_R5_FRESH_001'),
        flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=capability,
        started_at='2026-10-02T03:00:00+00:00')
    assert fresh._offline_calls == 1  # exactly one authoritative read
    snap = frozen.job.pre_dispatch_snapshot
    assert fresh.catalog_fingerprint == contract.QUALIFIED_BASELINE_FINGERPRINT
    assert snap['catalog_fingerprint'] == contract.QUALIFIED_BASELINE_FINGERPRINT
    assert snap['catalog_ids'] == sorted({OTHER.lower(), SECOND_OUTPUT_ID.lower()})
    basis = {'catalog_fingerprint': snap['catalog_fingerprint'],
             'catalog_ids': snap['catalog_ids'], 'project_id': snap['project_id']}
    assert snap['snapshot_sha256'] == sha256(basis)
    # The snapshot fingerprint is the one the capture read established, and
    # the fingerprint of the capability's session is the same single fact.
    assert snap['catalog_fingerprint'] == fresh.catalog_fingerprint


# R5 proof 6: a read that returns qualified-shape records but fails to
# establish the qualified fingerprint fails closed at capture; nothing
# persists.
def test_capture_without_established_baseline_fails_closed(runtime_env, monkeypatch):
    env = runtime_env

    def drifting_catalog(self, *, contract_version=contract.CONTRACT_VERSION):
        self._offline_calls += 1
        self.catalog_fingerprint = None  # the read established no baseline
        return [list(row) for row in self._offline_rows]

    monkeypatch.setattr(FlowReferenceRpcSession, 'catalog', drifting_catalog)
    fresh = offline_flow_session(catalog_records(OTHER))
    capability = qualify_flow_catalog_source(fresh)
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_BASELINE_DRIFT'):
        env.runtime.freeze(
            ordinary_r2v_shot(env.asset.asset_id, shot_id='FLOW_R2V_R5_DRIFT_002'),
            flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
            reference_filename=REFERENCE_FILENAME_2, catalog_source=capability,
            started_at='2026-10-02T03:01:00+00:00')
    with sqlite3.connect(env.store.path) as connection:
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert jobs == 1  # only the environment's valid frozen job


# R5 proof 7: project scope drift after minting fails closed — both at the
# freeze entry gate and at capture itself.
def test_project_drift_during_capture_fails_closed(runtime_env):
    env = runtime_env
    fresh = offline_flow_session(catalog_records(OTHER))
    capability = qualify_flow_catalog_source(fresh)
    fresh.project_id = OTHER  # scope drifts after the capability was minted
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_SOURCE_PROJECT_MISMATCH'):
        capability.capture()
    with pytest.raises(OwnerAmbiguityGate, match='CATALOG_SOURCE_PROJECT_MISMATCH'):
        env.runtime.freeze(
            ordinary_r2v_shot(env.asset.asset_id, shot_id='FLOW_R2V_R5_DRIFT_003'),
            flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
            reference_filename=REFERENCE_FILENAME_2, catalog_source=capability,
            started_at='2026-10-02T03:02:00+00:00')
    with sqlite3.connect(env.store.path) as connection:
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert jobs == 1


# R2 proof 2: the runtime asks the source exactly once, itself.
def test_runtime_captures_source_exactly_once(runtime_env):
    env = runtime_env
    session_double = offline_flow_session(catalog_records(OTHER, SECOND_OUTPUT_ID))
    source = qualify_flow_catalog_source(session_double)
    assert session_double._offline_calls == 0
    frozen = env.runtime.freeze(
        ordinary_r2v_shot(env.asset.asset_id, shot_id='FLOW_R2V_CAPTURE_002'),
        flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=source,
        started_at='2026-10-02T00:01:00+00:00')
    assert session_double._offline_calls == 1
    # A restart resume re-freezes without consulting the source again.
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    resumed = restarted.freeze(env.shot.model_copy(update={
        'shot_id': 'FLOW_R2V_CAPTURE_002'}), flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=source,
        started_at='2099-01-01T00:00:00+00:00')
    assert session_double._offline_calls == 1
    assert resumed.job.provider_job_id == frozen.job.provider_job_id


# R2 proof 3 + 4: the frozen snapshot is exactly the source observation,
# normalized; no caller hook exists to omit a row from that same source.
def test_snapshot_contains_exactly_source_observation(runtime_env):
    env = runtime_env
    ids = [OTHER, SECOND_OUTPUT_ID, THIRD_ID]
    source = catalog_capability(catalog_records(*ids))
    frozen = env.runtime.freeze(
        ordinary_r2v_shot(env.asset.asset_id, shot_id='FLOW_R2V_CAPTURE_003'),
        flow_capabilities(), reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=source,
        started_at='2026-10-02T00:02:00+00:00')
    snap = frozen.job.pre_dispatch_snapshot
    assert snap['catalog_ids'] == sorted({value.lower() for value in ids})
    basis = {'catalog_fingerprint': snap['catalog_fingerprint'],
             'catalog_ids': snap['catalog_ids'], 'project_id': snap['project_id']}
    assert snap['snapshot_sha256'] == sha256(basis)
    # The same source cannot yield a B-less snapshot: only the runtime reads
    # it, and no filtering parameter exists (proof 1 inspects the signature).


# R2 proof 5: rows appended/replaced after capture cannot change the frozen
# snapshot or its identity.
def test_post_capture_mutation_cannot_change_frozen_snapshot(runtime_env):
    env = runtime_env
    snap = env.frozen.job.pre_dispatch_snapshot
    frozen_ids, frozen_hash = snap['catalog_ids'], snap['snapshot_sha256']
    env.session._offline_rows.append([SECOND_OUTPUT_ID, PROJECT, 'IMAGE', 'CAE', None, None, None])
    env.session._offline_rows[0][0] = THIRD_ID  # replace in place
    basis = {'catalog_fingerprint': snap['catalog_fingerprint'],
             'catalog_ids': snap['catalog_ids'], 'project_id': snap['project_id']}
    assert snap['catalog_ids'] == frozen_ids
    assert snap['snapshot_sha256'] == frozen_hash == sha256(basis)
    # The frozen snapshot still verifies and authorizes normally.
    reserve(env)
    assert env.store.read_provider_job(
        env.frozen.job.provider_job_id).dispatch_count == 1


# R2 proof 6: wrong fingerprint/project/shape sources fail closed, nothing
# persisted. Unqualified fingerprints fail at capability minting; wrong
# project rows and malformed rows fail at freeze-time contract validation.
# Each freeze attempt uses a fresh shot so the runtime-owned capture path
# (not a restart resume) is the code under test.
def test_unqualified_catalog_source_fails_closed(runtime_env):
    env = runtime_env

    def attempt(n, source):
        with pytest.raises(OwnerAmbiguityGate):
            env.runtime.freeze(
                ordinary_r2v_shot(env.asset.asset_id, shot_id=f'FLOW_R2V_BADSRC_{n:03d}'),
                flow_capabilities(), reference_asset=env.asset,
                reference_media_id=REMOTE, reference_filename=REFERENCE_FILENAME_2,
                catalog_source=source, started_at=f'2026-10-02T00:03:0{n:02d}+00:00')

    attempt(2, catalog_capability(catalog_records(OTHER, project=OTHER)))
    attempt(3, catalog_capability([OUTPUT_ID]))  # malformed row shape
    attempt(4, object())  # not a catalog source at all
    with sqlite3.connect(env.store.path) as connection:
        jobs = connection.execute('SELECT COUNT(*) FROM provider_jobs').fetchone()[0]
    assert jobs == 1  # only the environment's valid frozen job


# R2 proof 7: restart reuses the exact frozen snapshot and never re-captures.
def test_restart_reuses_frozen_snapshot_without_recapture(runtime_env):
    env = runtime_env
    original = env.frozen.job.pre_dispatch_snapshot
    fresh_double = offline_flow_session(catalog_records(SECOND_OUTPUT_ID, THIRD_ID))
    fresh_source = qualify_flow_catalog_source(fresh_double)
    restarted = FlowR2VShotRuntime(env.store, project_id=PROJECT, account_id=ACCOUNT)
    resumed = restarted.freeze(env.shot, flow_capabilities(),
        reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename=REFERENCE_FILENAME_2, catalog_source=fresh_source,
        started_at='2099-01-01T00:00:00+00:00')
    assert fresh_double._offline_calls == 0  # historical truth is not re-captured
    assert resumed.job.pre_dispatch_snapshot == original
    assert resumed.job.provider_job_id == env.frozen.job.provider_job_id


# R2 proof 8 + 9: the Techlead case — the true source contains OTHER, the
# caller attempts to force an empty subset, and no path can freeze it; the
# captured preexisting row can never be owned.
def test_techlead_empty_subset_omission_case(runtime_env):
    env = runtime_env
    # The environment's source observation contains OTHER; the frozen snapshot
    # therefore contains OTHER (captured by the runtime, not asserted).
    snap = env.frozen.job.pre_dispatch_snapshot
    assert OTHER.lower() in snap['catalog_ids']
    # The caller cannot force the empty subset the old API accepted.
    with pytest.raises(TypeError):
        env.runtime.freeze(env.shot, flow_capabilities(),
            reference_asset=env.asset, reference_media_id=REMOTE,
            reference_filename=REFERENCE_FILENAME_2,
            baseline_catalog_records=[], catalog_source=env.catalog_source,
            started_at='2026-10-02T00:04:00+00:00')
    # With the true capture as the frozen baseline, the omitted row can no
    # longer be owned: presenting it fresh fails as preexisting.
    reserve(env)
    release_request(env)
    marker = film_marker(env.frozen.job.provider_job_id)
    row = make_veo31_video_record(OTHER, PROJECT, REMOTE, REFERENCE_FILENAME_2,
        marker, model=contract.MODEL_VEO_3_1_LITE)
    with pytest.raises(contract.ContractError, match='PREEXISTING'):
        env.runtime.attribute_backend_output(env.frozen, [row])
    assert env.store.read_output_bindings(env.frozen.job.provider_job_id) == []


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
    assert first.text.endswith(' ' + first.marker)
    assert '\n' not in first.text  # qualified native-UI single-line serialization
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
