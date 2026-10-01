"""Offline proof matrix for the reusable Flow R2V provider boundary.

Each test proves one productized behavior of
``film_pipeline.flow_r2v_boundary`` with frozen/synthetic evidence only.
No live provider access of any kind exists in this module.
"""
import hashlib
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from film_pipeline.dispatch_evidence import intent_hash
from film_pipeline.flow_r2v_boundary import (
    RECONCILE_ONLY,
    FlowR2VBoundary,
    MutationIntent,
    mutation_state,
)
from film_pipeline.live_runtime import ProviderJob
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_canonical_ui import NativeUiProfile, verify_settings
from film_pipeline.providers.flow_reference_binding import attest_existing_reference
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_r2v_prompt import film_marker
from film_pipeline.store import SQLiteStore
from film_pipeline.core import canonical_json

from test_canonical_reference_binding import bound
from test_flow_contract_20261001 import make_veo31_video_record
from test_live_runtime import FakeTransport, make_executor
from test_reference_reconcilable_transport import ACCOUNT, OTHER, PROJECT, REMOTE, png, setup

REFERENCE_FILENAME = 'reference.png'
OUTPUT_ID = 'c7b34a11-2299-4c55-8d01-9fa0b7c4e111'


@pytest.fixture
def env(tmp_path):
    """A fully offline boundary environment: attested reference plus one frozen job."""
    asset, upload_store, session, transport, key = setup(tmp_path)
    transport.ensure_verified(asset)  # Offline transport double; no live upload.
    runtime = SQLiteStore(upload_store.db_path)
    session.bound_media = lambda identity, kind: bound()[3]
    directory = tmp_path / 'attestation'
    attestation = attest_existing_reference(runtime, asset, session, account_id=ACCOUNT,
        media_id=REMOTE, evidence_dir=directory)
    executor, store, attempt, job = make_executor(tmp_path, FakeTransport())
    boundary = FlowR2VBoundary(SQLiteStore(runtime.path), project_id=PROJECT, account_id=ACCOUNT)
    return SimpleNamespace(asset=asset, session=session, runtime=runtime, store=store,
        attempt=attempt, job=job, boundary=boundary, directory=directory,
        intent=boundary.intent(reference_media_id=REMOTE), attestation=attestation)


def native_request(prompt, reference=REMOTE, project=PROJECT, model=contract.MODEL_VEO_3_1_LITE,
                   filename=REFERENCE_FILENAME):
    import json
    from urllib.parse import urlencode
    envelope = json.loads(contract.build_video_v2026_10_01(project, prompt, reference,
        filename, 'fixture_captcha', OTHER, model=model))
    payload = json.loads(envelope[0][0][1])
    payload[0][0][0] = [None, None, [[[prompt]]]]
    envelope[0][0][1] = json.dumps(payload)
    return urlencode({'f.req': json.dumps(envelope)})


def video_row(media_id, project=PROJECT, url=None, size=None, extra_url=None):
    """A minimal qualified as29s video-shape payload for exact-acquisition tests."""
    data = b'fixture-video-bytes'
    url = url or f'https://flow-content.google/video/{media_id}'
    meta = [None] * 14
    meta[13] = size if size is not None else len(data)
    lineage = [None] * 9
    lineage[8] = url
    return [media_id, project, None, 'CAE', extra_url, meta, None,
            [lineage, None, [media_id]]], data


def guarded(env):
    stub = SimpleNamespace(provider_job_id=env.job.provider_job_id,
        correlation_evidence={'prompt': env.job.correlation_evidence['prompt']})
    guard = env.boundary.request_guard(stub, env.intent)
    guard.armed = True
    return guard


def route_of(body):
    r = Mock()
    r.request.method = 'POST'
    r.request.url = 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=MZZa6b'
    r.request.post_data = body
    return r


def record_and_bind(env, output_id=OUTPUT_ID):
    env.store.record_dispatch_fact(env.job.provider_job_id, 'REMOTE_IDENTITY_OBSERVED',
        {'output_id': output_id, 'method': 'boundary_backend_attribution'})
    return env.boundary.bind_owned_output(env.job.provider_job_id, output_id)


def db_snapshot(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# 1 + 5 + 9 + 14: attested reference permits reservation, one mutation
# opportunity, unique fresh output ownership and exact acquisition.
def test_attested_reference_permits_reservation_and_single_mutation(tmp_path, env):
    assert env.boundary.store.read_provider_job(env.job.provider_job_id).dispatch_count == 0
    reserved = env.boundary.reserve_mutation(env.job.provider_job_id, asset=env.asset,
        attestation=env.attestation, media_id=REMOTE, evidence_dir=env.directory)
    assert reserved.dispatch_count == 1
    assert mutation_state(reserved).state == RECONCILE_ONLY
    facts = env.store.read_dispatch_facts(env.job.provider_job_id)
    assert facts[0]['kind'] == 'RESERVED'
    assert facts[0]['data']['intent_hash'] == intent_hash(reserved)

    prompt = env.job.correlation_evidence['prompt']
    guard = guarded(env)
    first, duplicate = route_of(native_request(prompt)), route_of(native_request(prompt))
    guard.route(first)
    guard.route(duplicate)
    first.continue_.assert_called_once()
    duplicate.abort.assert_called_once()
    assert guard.sent == 1 and guard.seen == 2

    marker = film_marker(env.job.provider_job_id)
    row = make_veo31_video_record(OUTPUT_ID, PROJECT, REMOTE, REFERENCE_FILENAME, marker,
        model=contract.MODEL_VEO_3_1_LITE)
    assert env.boundary.attribute_output([row], intent=env.intent, prompt=prompt,
        provider_job_id=env.job.provider_job_id, baseline_ids=[OTHER],
        reference_filename=REFERENCE_FILENAME) == row
    binding = record_and_bind(env)
    assert binding['output_id'] == OUTPUT_ID
    assert binding['attempt_id'] == env.attempt.generation_attempt_id

    payload, data = video_row(OUTPUT_ID)
    media = env.boundary.acquire_bound_media(payload, intent=env.intent, media_id=OUTPUT_ID,
        data=data, response_url=f'https://flow-content.google/video/{OUTPUT_ID}',
        status=200, headers={'content-type': 'video/mp4', 'content-length': str(len(data))})
    assert media.evidence['media_id'] == OUTPUT_ID
    assert media.evidence['project_id'] == PROJECT
    assert media.evidence['resource_path'] == f'/video/{OUTPUT_ID}'
    assert media.evidence['sha256'] == hashlib.sha256(data).hexdigest()
    assert media.evidence['response_status'] == 200 and media.evidence['redirects'] == 0


# 2 + 3: wrong reference, wrong provider media ID or wrong scope is rejected.
@pytest.mark.parametrize('media_id', [OTHER, '347f9951-5bbc-4910-b6fd-3a17c74e29d2'])
def test_reservation_requires_attestation_for_exact_media_id(env, media_id):
    with pytest.raises(OwnerAmbiguityGate):
        env.boundary.reserve_mutation(env.job.provider_job_id, asset=env.asset,
            attestation=env.attestation, media_id=media_id, evidence_dir=env.directory)
    assert env.store.read_provider_job(env.job.provider_job_id).dispatch_count == 0


def test_geometric_readback_content_fails_attestation(tmp_path):
    asset, upload_store, session, transport, key = setup(tmp_path)
    receipt = transport.ensure_verified(asset)
    runtime = SQLiteStore(upload_store.db_path)
    geometric = bound(png((220, 10, 10), pattern=False))[3]
    session.bound_media = lambda identity, kind: geometric
    with pytest.raises(OwnerAmbiguityGate):
        attest_existing_reference(runtime, asset, session, account_id=ACCOUNT,
            media_id=REMOTE, evidence_dir=tmp_path / 'attestation')
    # Even an internally consistent receipt cannot qualify wrong content.
    from film_pipeline.providers.flow_reference_binding import reference_attestation
    conflated = {**receipt, 'provider_media_sha256': geometric.evidence['sha256']}
    with pytest.raises(OwnerAmbiguityGate, match='CONTENT_MISMATCH'):
        reference_attestation(asset, conflated, geometric, project_id=PROJECT, media_id=REMOTE)


# 4: tampered reference evidence fails closed.
@pytest.mark.parametrize('defect', ['json_copy', 'file', 'id'])
def test_tampered_attestation_blocks_reservation(env, defect):
    attestation = {**env.attestation}
    if defect == 'json_copy':
        attestation['readback'] = {**attestation['readback'], 'byte_size': 1}
    elif defect == 'id':
        attestation['attestation_id'] = 'refbind_' + 'b' * 64
    if defect == 'file':
        (env.directory / (env.attestation['attestation_id'] + '.json')).write_text('{}')
    with pytest.raises(OwnerAmbiguityGate):
        env.boundary.verify_reference(env.asset, attestation, media_id=REMOTE,
            evidence_dir=env.directory)
    with pytest.raises(OwnerAmbiguityGate):
        env.boundary.reserve_mutation(env.job.provider_job_id, asset=env.asset,
            attestation=attestation, media_id=REMOTE, evidence_dir=env.directory)
    assert env.store.read_provider_job(env.job.provider_job_id).dispatch_count == 0


# 6: re-entry after the mutation boundary is reconciliation only.
def test_reentry_after_consumption_is_reconciliation_only(env):
    env.boundary.reserve_mutation(env.job.provider_job_id, asset=env.asset,
        attestation=env.attestation, media_id=REMOTE, evidence_dir=env.directory)
    with pytest.raises(OwnerAmbiguityGate, match='RECONCILE_ONLY'):
        env.boundary.reserve_mutation(env.job.provider_job_id, asset=env.asset,
            attestation=env.attestation, media_id=REMOTE, evidence_dir=env.directory)
    assert env.store.read_provider_job(env.job.provider_job_id).dispatch_count == 1
    with pytest.raises(RuntimeError, match='budget already consumed'):
        env.store.reserve_dispatch(env.job.provider_job_id)
    job = env.boundary.reconciliation_only(env.job.provider_job_id)
    assert mutation_state(job).state == RECONCILE_ONLY


def test_reconciliation_only_refuses_unconsumed_dispatch(env):
    with pytest.raises(OwnerAmbiguityGate, match='NOT_YET_CONSUMED'):
        env.boundary.reconciliation_only(env.job.provider_job_id)


# 7: the browser-created request must match the frozen intent exactly.
@pytest.mark.parametrize('defect', ['reference', 'project', 'model', 'count', 'creative'])
def test_native_request_intent_mismatch_is_rejected(env, defect):
    prompt = env.job.correlation_evidence['prompt']
    if defect == 'reference':
        body = native_request(prompt, reference=OTHER)
    elif defect == 'project':
        body = native_request(prompt, project=OTHER)
    elif defect == 'model':
        body = native_request(prompt, model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE)
    elif defect == 'count':
        import json
        from urllib.parse import parse_qs, urlencode
        envelope = json.loads(parse_qs(native_request(prompt))['f.req'][0])
        payload = json.loads(envelope[0][0][1])
        payload[0] = [payload[0][0], payload[0][0]]
        envelope[0][0][1] = json.dumps(payload)
        body = urlencode({'f.req': json.dumps(envelope)})
    else:
        import json
        from urllib.parse import parse_qs, urlencode
        envelope = json.loads(parse_qs(native_request(prompt))['f.req'][0])
        payload = json.loads(envelope[0][0][1])
        payload[0][0][0] = [None, None, [[['WRONG CREATIVE PROMPT']]]]
        payload[1].append(prompt)
        envelope[0][0][1] = json.dumps(payload)
        body = urlencode({'f.req': json.dumps(envelope)})
    with pytest.raises(OwnerAmbiguityGate):
        env.boundary.observe_native_request('POST',
            'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=MZZa6b',
            body, intent=env.intent, prompt=prompt)


def test_guard_uses_the_intent_ui_profile(env):
    profile = NativeUiProfile(wire_model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE,
        contract_tag='native-ui-r2v-test-v1')
    intent = env.boundary.intent(reference_media_id=REMOTE, model=profile.wire_model,
        ui_profile=profile)
    prompt = env.job.correlation_evidence['prompt']
    observed = env.boundary.observe_native_request('POST',
        'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=MZZa6b',
        native_request(prompt, model=profile.wire_model), intent=intent, prompt=prompt)
    assert observed['contract'] == 'native-ui-r2v-test-v1'


# 8: outbound request plus HTTP success without a backend output stays unresolved.
def test_http_success_without_backend_output_stays_unresolved(env):
    env.boundary.reserve_mutation(env.job.provider_job_id, asset=env.asset,
        attestation=env.attestation, media_id=REMOTE, evidence_dir=env.directory)
    prompt = env.job.correlation_evidence['prompt']
    guard = guarded(env)
    guard.route(route_of(native_request(prompt)))
    assert guard.sent == 1  # One exact request released; HTTP success is implied.
    marker = film_marker(env.job.provider_job_id)
    unrelated = make_veo31_video_record(OUTPUT_ID, PROJECT, REMOTE, REFERENCE_FILENAME,
        film_marker('job_' + 'd' * 64), model=contract.MODEL_VEO_3_1_LITE)
    assert env.boundary.attribute_output([unrelated], intent=env.intent, prompt=prompt,
        provider_job_id=env.job.provider_job_id, baseline_ids=[OTHER],
        reference_filename=REFERENCE_FILENAME) is None
    assert env.store.read_output_bindings(env.job.provider_job_id) == []
    persisted = env.store.read_provider_job(env.job.provider_job_id)
    assert persisted.dispatch_count == 1
    assert mutation_state(persisted).state == RECONCILE_ONLY


# 10: a preexisting output cannot be claimed.
def test_preexisting_output_cannot_be_claimed(env):
    marker = film_marker(env.job.provider_job_id)
    row = make_veo31_video_record(OUTPUT_ID, PROJECT, REMOTE, REFERENCE_FILENAME, marker,
        model=contract.MODEL_VEO_3_1_LITE)
    with pytest.raises(contract.ContractError, match='PREEXISTING'):
        env.boundary.attribute_output([row], intent=env.intent,
            prompt=env.job.correlation_evidence['prompt'],
            provider_job_id=env.job.provider_job_id, baseline_ids=[OUTPUT_ID],
            reference_filename=REFERENCE_FILENAME)


# 11: wrong-reference lineage cannot be claimed.
@pytest.mark.parametrize('reference', [OTHER, '347f9951-5bbc-4910-b6fd-3a17c74e29d2'])
def test_wrong_reference_lineage_cannot_be_claimed(env, reference):
    marker = film_marker(env.job.provider_job_id)
    row = make_veo31_video_record(OUTPUT_ID, PROJECT, reference, REFERENCE_FILENAME, marker,
        model=contract.MODEL_VEO_3_1_LITE)
    with pytest.raises(contract.ContractError):
        env.boundary.attribute_output([row], intent=env.intent,
            prompt=env.job.correlation_evidence['prompt'],
            provider_job_id=env.job.provider_job_id, baseline_ids=[],
            reference_filename=REFERENCE_FILENAME)


# 12: marker collision / multiple candidates fail closed.
def test_marker_collision_fails_closed(env):
    marker = film_marker(env.job.provider_job_id)
    rows = [make_veo31_video_record(output_id, PROJECT, REMOTE, REFERENCE_FILENAME, marker,
        model=contract.MODEL_VEO_3_1_LITE)
        for output_id in (OUTPUT_ID, 'd7b34a11-2299-4c55-8d01-9fa0b7c4e222')]
    with pytest.raises(contract.ContractError, match='COLLISION'):
        env.boundary.attribute_output(rows, intent=env.intent,
            prompt=env.job.correlation_evidence['prompt'],
            provider_job_id=env.job.provider_job_id, baseline_ids=[],
            reference_filename=REFERENCE_FILENAME)


# 13: malformed provider contracts fail closed.
def test_malformed_provider_contract_fails_closed(env):
    payload, data = video_row(OUTPUT_ID)
    payload[1] = OTHER
    with pytest.raises(contract.ContractError):
        env.boundary.acquire_bound_media(payload, intent=env.intent, media_id=OUTPUT_ID,
            data=data, response_url=f'https://flow-content.google/video/{OUTPUT_ID}',
            status=200, headers={'content-type': 'video/mp4',
                                 'content-length': str(len(data))})
    with pytest.raises(contract.ContractError):
        env.boundary.attribute_output([[OUTPUT_ID]], intent=env.intent,
            prompt='p', provider_job_id=env.job.provider_job_id, baseline_ids=[],
            reference_filename=REFERENCE_FILENAME)


# 14 (duplicate forms) + 15: identical representations of one resource normalize.
def test_identical_duplicate_representations_normalize(env):
    payload, data = video_row(OUTPUT_ID)
    first = env.boundary.acquire_bound_media(payload, intent=env.intent, media_id=OUTPUT_ID,
        data=data, response_url=f'https://flow-content.google/video/{OUTPUT_ID}',
        status=200, headers={'content-type': 'video/mp4', 'content-length': str(len(data))})
    second = env.boundary.acquire_bound_media(list(payload),
        intent=env.intent, media_id=OUTPUT_ID, data=data,
        response_url=f'https://flow-content.google/video/{OUTPUT_ID}',
        status=200, headers={'content-type': 'video/mp4', 'content-length': str(len(data))})
    assert first.evidence == second.evidence
    resource = env.boundary.normalize_bound_media([payload, payload], intent=env.intent,
        media_id=OUTPUT_ID)
    assert resource.media_id == OUTPUT_ID


# 16: different media resources stay ambiguous.
def test_different_resources_stay_ambiguous(env):
    payload, _ = video_row(OUTPUT_ID)
    resized = video_row(OUTPUT_ID, size=999)[0]
    with pytest.raises(OwnerAmbiguityGate, match='AMBIGUOUS'):
        env.boundary.normalize_bound_media([payload, resized], intent=env.intent,
            media_id=OUTPUT_ID)
    conflicted = video_row(OUTPUT_ID,
        extra_url=f'https://flow-content.google/video/{OTHER}')[0]
    with pytest.raises(contract.ContractError, match='CARDINALITY'):
        env.boundary.acquire_bound_media(conflicted, intent=env.intent, media_id=OUTPUT_ID,
            data=b'fixture-video-bytes',
            response_url=f'https://flow-content.google/video/{OUTPUT_ID}',
            status=200, headers={'content-type': 'video/mp4', 'content-length': '19'})
    with pytest.raises(contract.ContractError, match='IDENTITY_MISMATCH'):
        env.boundary.acquire_bound_media(resized, intent=env.intent, media_id=OUTPUT_ID,
            data=b'fixture-video-bytes',
            response_url=f'https://flow-content.google/video/{OUTPUT_ID}-2',
            status=200, headers={'content-type': 'video/mp4', 'content-length': '19'})


# 17: historical Slice-0011 style jobs stay byte-identical across boundary use.
def test_historical_jobs_unchanged_by_boundary_operations(tmp_path):
    executor, store, attempt, job = make_executor(tmp_path, FakeTransport())
    store.reserve_dispatch(job.provider_job_id)
    legacy = ProviderJob(provider_job_id='job_' + 'c' * 64,
        generation_attempt_id=attempt.generation_attempt_id, provider_id='flow_veo',
        project_binding_id='legacy-binding', dispatch_count=1, submission_state='SUBMITTED',
        status='INCONCLUSIVE', dispatch_protocol='legacy-v1',
        correlation_evidence={'prompt': 'legacy prompt'})
    connection = sqlite3.connect(store.path)
    try:
        with connection:
            connection.execute('INSERT INTO provider_jobs VALUES (?,?,?,?,?)',
                (legacy.provider_job_id, legacy.generation_attempt_id, 'flow_veo', 1,
                 canonical_json(legacy.model_dump(mode='json'))))
    finally:
        connection.close()
    before = db_snapshot(store.path)
    boundary = FlowR2VBoundary(store, project_id=PROJECT, account_id=ACCOUNT)
    with pytest.raises(OwnerAmbiguityGate):
        boundary.reserve_mutation(job.provider_job_id, asset=SimpleNamespace(),
            attestation={}, media_id=REMOTE, evidence_dir=tmp_path)
    with pytest.raises(OwnerAmbiguityGate):
        boundary.reserve_mutation(legacy.provider_job_id, asset=SimpleNamespace(),
            attestation={}, media_id=REMOTE, evidence_dir=tmp_path)
    assert boundary.attribute_output([], intent=boundary.intent(reference_media_id=REMOTE),
        prompt='p', provider_job_id=job.provider_job_id, baseline_ids=[],
        reference_filename=REFERENCE_FILENAME) is None
    assert boundary.reconciliation_only(job.provider_job_id).dispatch_count == 1
    assert db_snapshot(store.path) == before
    restored = store.read_provider_job(legacy.provider_job_id)
    assert restored.dispatch_protocol == 'legacy-v1' and restored.dispatch_count == 1


# Qualified envelope: volatility stays outside; anything unqualified fails closed.
@pytest.mark.parametrize('field,value', [
    ('model', 'abra_r2v_8s'), ('model', 'veo_3_1_r2v_turbo'),
    ('output_count', 2), ('duration_s', 4), ('resolution', '1080p'),
    ('aspect_ratio', '9:16'), ('contract_version', 'flow-batchexecute/2026-09-20.1'),
])
def test_mutation_intent_rejects_unqualified_envelope(field, value):
    with pytest.raises(OwnerAmbiguityGate):
        MutationIntent(project_id=PROJECT, account_id=ACCOUNT, reference_media_id=REMOTE,
            **{field: value})


def test_mutation_intent_rejects_bad_ids():
    with pytest.raises(Exception):
        MutationIntent(project_id='not-a-uuid', account_id=ACCOUNT, reference_media_id=REMOTE)
    with pytest.raises(Exception):
        MutationIntent(project_id=PROJECT, account_id=ACCOUNT, reference_media_id='53b5')


# Productization target: the generic boundary and UI transport are slice-free.
def test_boundary_and_ui_transport_do_not_import_slice_components():
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'film_pipeline'
    for name in ('flow_r2v_boundary.py', 'providers/flow_canonical_ui.py'):
        source = (root / name).read_text(encoding='utf-8')
        assert not re.search(r'slice0011|CHAR_CONTINUITY', source), name


# UI profile parameterization: locale labels are transport data, not code.
def test_ui_profile_is_parameterizable():
    profile = NativeUiProfile(settings_tokens=('Video', '·', '720p', '8', 'seconds', 'crop_16_9', 'x1'),
        model_group_aria='Select model group',
        checked_toggles=frozenset({'videocam\nVideo', 'crop_16_9\n16:9', 'x1'}),
        model_label='Veo 3.1 - Fast')
    page = Mock()
    locator = page.locator.return_value
    locator.count.return_value = 1
    locator.wait_for.return_value = None
    locator.all_inner_texts.return_value = ['videocam\nVideo', 'crop_16_9\n16:9', 'x1']
    locator.inner_text.side_effect = ['Video · 720p 8 seconds crop_16_9 x1', 'Veo 3.1 - Fast']
    verify_settings(page, profile)
    assert locator.inner_text.call_count == 2
    page.locator.side_effect = None


def test_default_profile_settings_mismatch_still_blocks():
    page = Mock()
    locator = page.locator.return_value
    locator.count.return_value = 1
    locator.inner_text.return_value = 'Video · 720p 4 giây crop_16_9 x1'
    with pytest.raises(OwnerAmbiguityGate, match='SETTINGS'):
        verify_settings(page)
