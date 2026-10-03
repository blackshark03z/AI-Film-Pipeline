"""Package-008 U3: qualified upload-pending state machine + mutation
authority integration. Offline proofs; no live provider claims."""
import hashlib
import io
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from film_pipeline.live_runtime import Asset
from film_pipeline.store import SQLiteStore
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_upload import (
    ReferenceUploadStore, OwnerAmbiguityGate, _key)
from film_pipeline.providers.flow_reference_transport import FlowReferenceTransport
from film_pipeline.providers.flow_upload_classifier import (
    QUALIFIED_PENDING, TRUE_AMBIGUOUS, UNOBSERVABLE,
    classify_upload_response, pending_fingerprint_matches,
    QualifiedUploadPending, UploadResponseAmbiguous)
from tests.test_upload_classifier_008 import (
    FROZEN_FINGERPRINT, LIVE_PENDING_SKELETON, build_payload)
from mutation_authority import (
    AUTHORITY_LATCHED_CLOSED, AUTHORITY_OPEN,
    AUTHORITY_SUSPENDED_UPLOAD_PENDING, MutationAuthority)

PROJECT = '11111111-2222-3333-4444-555555555555'
REMOTE = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
OTHER = '99999999-8888-7777-6666-555555555555'
ACCOUNT = 'project_scoped_unverified_account'


def png(color=(20, 80, 140)):
    image = Image.new('RGB', (128, 72), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((6, 8, 45, 60), fill=(190, 35, 50))
    stream = io.BytesIO()
    image.save(stream, 'PNG')
    return stream.getvalue()


def make_asset(tmp_path, color=(20, 80, 140)):
    path = tmp_path / f'reference_{color[0]}.png'
    data = png(color)
    path.write_bytes(data)
    return Asset(asset_id=f'asset_test_{color[0]}', asset_type='image',
        origin='reference', uri_or_path=str(path.resolve()),
        sha256=hashlib.sha256(data).hexdigest(), mime_type='image/png',
        width=128, height=72, file_size=len(data),
        rights_metadata={'source_kind': 'deterministic_synthetic_fixture'})


PENDING_RESULT = classify_upload_response(
    200, build_payload(LIVE_PENDING_SKELETON), project_id=PROJECT,
    request_id=PROJECT)


class PendingSession:
    """Simulates the real maseQ session: POST taken, response matches the
    qualified pending class (one POST, no identity from response)."""

    project_id = PROJECT
    catalog_fingerprint = contract.QUALIFIED_BASELINE_FINGERPRINT

    def __init__(self, remote_bytes=None):
        self.uploads = 0
        self.remote = {} if remote_bytes is None else {REMOTE: remote_bytes}

    def upload_reference(self, data, request_id, *, before_post,
                         on_http_response, on_identified):
        before_post(hashlib.sha256(data).hexdigest())
        self.uploads += 1
        on_http_response(200, 651)
        raise QualifiedUploadPending(PENDING_RESULT.classification,
                                     PENDING_RESULT.reason,
                                     PENDING_RESULT.skeleton,
                                     PENDING_RESULT.fingerprint)

    def catalog(self):
        return [[identity, PROJECT, 'IMAGE', 'CAE', None, None, None]
                for identity in self.remote]

    def media(self, identity, kind):
        return self.remote.get(identity)


class Session(PendingSession):
    """Completing session variant (direct identity envelope)."""

    def __init__(self, remote_bytes=None):
        super().__init__(remote_bytes)
        self.remote = {} if remote_bytes is None else {REMOTE: remote_bytes}

    def upload_reference(self, data, request_id, *, before_post,
                         on_http_response, on_identified):
        before_post(hashlib.sha256(data).hexdigest())
        self.uploads += 1
        self.remote[REMOTE] = data
        on_http_response(200, 2758)
        on_identified(REMOTE)
        return REMOTE


def setup(tmp_path, session=None, color=(20, 80, 140)):
    asset = make_asset(tmp_path, color)
    runtime = SQLiteStore(tmp_path / 'runtime.sqlite')
    runtime.initialize()
    runtime.save_reference_asset(asset)
    store = ReferenceUploadStore(runtime.path)
    session = session if session is not None else Session()
    transport = FlowReferenceTransport(store, session, account_id=ACCOUNT,
        evidence_dir=tmp_path / 'evidence', interval_s=0, probes=2)
    key = _key('flow_veo', PROJECT, ACCOUNT, asset)
    return asset, store, session, transport, key


def authority(tmp_path):
    return MutationAuthority(tmp_path / 'scope', 'TEST-008-SCOPE')


# 1 — known qualified pending response -------------------------------------
def test_qualified_pending_response_enters_durable_pending(tmp_path):
    asset, store, session, transport, key = setup(tmp_path, PendingSession())
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    stages = [e['stage'] for e in store.events(key)]
    assert stages == ['LOCAL_RESERVED', 'REQUEST_ARMED', 'HTTP_RESPONSE_OBSERVED',
                      'UPLOAD_RESPONSE_CLASSIFIED']
    progress = store.read_progress(key)
    assert progress['effective_state'] == 'QUALIFIED_PENDING_RECONCILIATION'
    classified = [e for e in store.events(key)
                  if e['stage'] == 'UPLOAD_RESPONSE_CLASSIFIED'][0]
    assert classified['data']['classification'] == QUALIFIED_PENDING
    assert len(classified['data']['skeleton_hash']) == 64
    evidence_files = list((tmp_path / 'evidence').glob('*.json'))
    assert evidence_files and 'secret' not in evidence_files[0].read_text().lower()
    assert session.uploads == 1


# 2 — unknown response shape ------------------------------------------------
def test_unknown_response_shape_raises_gate_and_records_ambiguous(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)

    def unknown_shape(*args, **kwargs):
        kwargs['before_post']('1' * 64)
        raise UploadResponseAmbiguous(TRUE_AMBIGUOUS, 'payload_shape_unqualified',
                                      {'dict': {}}, 'a' * 64)
    session.upload_reference = Mock(side_effect=unknown_shape)
    with pytest.raises(OwnerAmbiguityGate, match='no re-upload'):
        transport.ensure_verified(asset)
    progress = store.read_progress(key)
    assert progress['effective_state'] == 'FAILED_AMBIGUOUS'
    classified = [e for e in store.events(key)
                  if e['stage'] == 'UPLOAD_RESPONSE_CLASSIFIED'][0]
    assert classified['data']['classification'] == TRUE_AMBIGUOUS


# 3 — malformed response -----------------------------------------------------
def test_malformed_response_transport_failure_records_gate(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)

    def broken(*args, **kwargs):
        kwargs['before_post']('1' * 64)
        raise ValueError('simulated parser crash')
    session.upload_reference = Mock(side_effect=broken)
    with pytest.raises(OwnerAmbiguityGate, match='no re-upload'):
        transport.ensure_verified(asset)
    assert store.read_progress(key)['effective_state'] == 'FAILED_AMBIGUOUS'


# 4 — HTTP 200 + unknown body ------------------------------------------------
def test_http_200_unknown_body_fails_closed(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)

    def unknown_body(*args, **kwargs):
        kwargs['before_post']('1' * 64)
        raise UploadResponseAmbiguous(TRUE_AMBIGUOUS, 'payload_shape_unqualified',
                                      {'list': []}, 'b' * 64)
    session.upload_reference = Mock(side_effect=unknown_body)
    with pytest.raises(OwnerAmbiguityGate):
        transport.ensure_verified(asset)
    assert store.read_progress(key)['effective_state'] == 'FAILED_AMBIGUOUS'


# 5 — transport failure before bytes ----------------------------------------
def test_transport_death_after_dispatch_is_unobservable_gate(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)

    def lost(*args, **kwargs):
        kwargs['before_post']('1' * 64)
        raise TimeoutError('wire dead')
    session.upload_reference = Mock(side_effect=lost)
    with pytest.raises(OwnerAmbiguityGate):
        transport.ensure_verified(asset)
    assert store.read_progress(key)['effective_state'] == 'FAILED_AMBIGUOUS'


# 6 — exact unique catalog match after pending ------------------------------
def test_pending_reconciles_to_unique_binding_and_verifies(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=png()), color=(20, 80, 140))
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    receipt = transport.reconcile_only(asset)
    assert receipt['media_id'] == REMOTE
    assert store.read_progress(key)['effective_state'] == 'REMOTE_RESOURCE_VERIFIED'
    assert session.uploads == 1  # never a second POST


# 7 — multiple strong matches ------------------------------------------------
def test_multiple_strong_matches_are_ambiguous(tmp_path):
    asset, store, session, transport, key = setup(tmp_path, PendingSession())
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    session.remote[REMOTE] = png()
    session.remote[OTHER] = png()
    with pytest.raises(OwnerAmbiguityGate, match='multiple strong'):
        transport.reconcile_only(asset)


# 8 — preexisting identical media (durable pre-upload evidence) --------------
def test_preexisting_unresolved_row_does_not_block_unique_match(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=png()))
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    session.remote[OTHER] = b'unreadable-blocker'
    session.media = Mock(side_effect=lambda identity, kind: (
        session.remote[identity] if identity == REMOTE else None))
    receipt = transport.reconcile_only(asset, preexisting_ids=[OTHER])
    assert receipt['media_id'] == REMOTE


# 9 — wrong-project match -----------------------------------------------------
def test_wrong_project_catalog_is_not_a_safe_match(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=png()))
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    session.catalog = lambda: [[REMOTE, OTHER, 'IMAGE', 'CAE', None, None, None]]
    with pytest.raises(Exception, match='PROJECT_MISMATCH'):
        transport.reconcile_only(asset)


# 10 — content mismatch -------------------------------------------------------
def test_wrong_content_never_binds_and_exhausts_to_ambiguity(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=png((1, 2, 3))),
        color=(20, 80, 140))
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    # The only catalog candidate carries different content: no strong match
    # ever forms, so bounded reconciliation exhausts (fail-closed ambiguity).
    with pytest.raises(OwnerAmbiguityGate,
                       match='bounded catalog reconciliation unresolved'):
        transport.reconcile_only(asset)
    assert store.read_progress(key)['effective_state'] == \
        'QUALIFIED_PENDING_RECONCILIATION'


# 11 — readback unavailable ---------------------------------------------------
def test_unreadable_candidates_block_and_exhaust(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=None))
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    # The only candidate row is present but its readback never resolves:
    # an unresolved row not covered by preexisting evidence blocks binding.
    with pytest.raises(OwnerAmbiguityGate,
                       match='bounded catalog reconciliation unresolved'):
        transport.reconcile_only(asset)
    assert store.read_progress(key)['effective_state'] == \
        'QUALIFIED_PENDING_RECONCILIATION'


# 11b — readback unavailable AFTER identification retains the resource --------
def test_readback_unavailable_after_identification_retains_resource(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=png()))
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    # Single-probe transport: the probe identifies the resource (first
    # readback), then verification readbacks fail — the identified resource
    # stays retained and durable.
    single = FlowReferenceTransport(store, session, account_id=ACCOUNT,
        evidence_dir=tmp_path / 'evidence2', interval_s=0, probes=1,
        readbacks=2)
    remote = session.remote
    calls = {'n': 0}

    def flaky(identity, kind):
        calls['n'] += 1
        return remote.get(identity) if calls['n'] == 1 else None
    session.media = flaky
    with pytest.raises(OwnerAmbiguityGate, match='readback unavailable'):
        single.reconcile_only(asset)
    assert store.read_progress(key)['effective_state'] == \
        'REMOTE_RESOURCE_IDENTIFIED'


# 12 — pending survives restart ----------------------------------------------
def test_pending_survives_restart_for_store_and_authority(tmp_path):
    asset, store, session, transport, key = setup(tmp_path, PendingSession())
    scope = authority(tmp_path)
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    scope.enter_upload_pending(key, PENDING_RESULT.fingerprint, 'canary')
    # Fresh processes: new objects over the same durable state.
    store2 = ReferenceUploadStore(store.db_path)
    authority2 = MutationAuthority(tmp_path / 'scope', 'TEST-008-SCOPE')
    assert store2.read_progress(key)['effective_state'] == \
        'QUALIFIED_PENDING_RECONCILIATION'
    assert authority2.authority == AUTHORITY_SUSPENDED_UPLOAD_PENDING
    with pytest.raises(OwnerAmbiguityGate, match='UPLOAD_PENDING_SUSPENDED'):
        authority2.check_mutation_allowed('primary_generate')


# 13 — pending forbids Generate ----------------------------------------------
def test_pending_suspends_generate_authority(tmp_path):
    scope = authority(tmp_path)
    scope.check_mutation_allowed('primary_generate')  # OPEN baseline
    scope.enter_upload_pending('refup_x', 'c' * 64)
    with pytest.raises(OwnerAmbiguityGate, match='UPLOAD_PENDING_SUSPENDED'):
        scope.check_mutation_allowed('primary_generate')
    with pytest.raises(OwnerAmbiguityGate, match='UPLOAD_PENDING_SUSPENDED'):
        scope.check_mutation_allowed('continuity_upload')


# 14 — pending forbids second upload -----------------------------------------
def test_pending_never_grants_a_second_upload(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=png()))
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    # Re-entry always routes to read-only reconciliation, never the POST path.
    receipt = transport.ensure_verified(asset)
    assert receipt['media_id'] == REMOTE
    assert session.uploads == 1
    with pytest.raises(OwnerAmbiguityGate, match='arm already consumed'):
        store.arm_local(key, 'd' * 64)


# 15 — successful bind permits next mutation ---------------------------------
def test_upload_bound_restores_planned_continuation(tmp_path):
    scope = authority(tmp_path)
    scope.enter_upload_pending('refup_x', 'c' * 64)
    scope.upload_bound('refup_x')
    assert scope.authority == AUTHORITY_OPEN
    scope.check_mutation_allowed('primary_generate')  # no raise
    scope.consume('primary_generate')


# 16 — ambiguity latches -------------------------------------------------------
def test_reconciliation_failure_promotes_pending_to_permanent_latch(tmp_path):
    scope = authority(tmp_path)
    scope.enter_upload_pending('refup_x', 'c' * 64)
    scope.promote_pending_to_ambiguity('refup_x', 'bounded exhaustion')
    assert scope.authority == AUTHORITY_LATCHED_CLOSED
    with pytest.raises(OwnerAmbiguityGate, match='MUTATION_LATCHED_CLOSED'):
        scope.check_mutation_allowed('primary_generate')
    with pytest.raises(OwnerAmbiguityGate):
        scope.consume('repair_generate')


# 17 — read-only resolution after ambiguity never reopens the latch ----------
def test_readonly_resolution_after_ambiguity_cannot_reopen(tmp_path):
    scope = authority(tmp_path)
    scope.enter_upload_pending('refup_x', 'c' * 64)
    scope.promote_pending_to_ambiguity('refup_x', 'nonunique matches')
    scope.record_knowledge('RESOLVED_EFFECT_IDENTIFIED', 'catalog unique match')
    assert scope.authority == AUTHORITY_LATCHED_CLOSED
    with pytest.raises(OwnerAmbiguityGate, match='suspended pending state'):
        scope.upload_bound('refup_x')
    with pytest.raises(OwnerAmbiguityGate, match='MUTATION_LATCHED_CLOSED'):
        scope.check_mutation_allowed('primary_generate')


# 18 — response-shape drift ----------------------------------------------------
def test_pending_fingerprint_drift_is_detectable():
    frozen = classify_upload_response(200, build_payload(LIVE_PENDING_SKELETON),
                                      project_id=PROJECT, request_id=PROJECT)
    drifted_payload = build_payload(LIVE_PENDING_SKELETON)
    drifted_payload[0].append('drift')
    drifted = classify_upload_response(200, drifted_payload,
                                       project_id=PROJECT, request_id=PROJECT)
    assert frozen.classification == QUALIFIED_PENDING
    assert drifted.classification == TRUE_AMBIGUOUS  # drift never pending
    assert not pending_fingerprint_matches(frozen.fingerprint, drifted.fingerprint)
    assert pending_fingerprint_matches(frozen.fingerprint, frozen.fingerprint)
    assert not pending_fingerprint_matches('short', frozen.fingerprint)
    assert not pending_fingerprint_matches(None, frozen.fingerprint)


# 19 — catalog schema drift ----------------------------------------------------
def test_catalog_contract_drift_blocks_reconciliation(tmp_path):
    asset, store, session, transport, key = setup(tmp_path, PendingSession())
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    session.catalog_fingerprint = 'drifted-fingerprint'
    with pytest.raises(OwnerAmbiguityGate, match='catalog contract drift'):
        transport.reconcile_only(asset)


# 20 — bounded exhaustion ------------------------------------------------------
def test_bounded_exhaustion_promotes_to_true_ambiguity(tmp_path):
    asset, store, session, transport, key = setup(
        tmp_path, PendingSession(remote_bytes=None))
    scope = authority(tmp_path)
    with pytest.raises(QualifiedUploadPending):
        transport.ensure_verified(asset)
    scope.enter_upload_pending(key, PENDING_RESULT.fingerprint)
    with pytest.raises(OwnerAmbiguityGate, match='bounded catalog reconciliation'):
        transport.reconcile_only(asset)
    scope.promote_pending_to_ambiguity(key, 'bounded exhaustion, zero matches')
    assert scope.authority == AUTHORITY_LATCHED_CLOSED


# Authority edge cases --------------------------------------------------------
def test_pending_state_machine_refuses_conflicting_transitions(tmp_path):
    scope = authority(tmp_path)
    scope.enter_upload_pending('refup_a', 'c' * 64)
    with pytest.raises(OwnerAmbiguityGate, match='different qualified upload'):
        scope.enter_upload_pending('refup_b', 'd' * 64)
    assert scope.enter_upload_pending('refup_a', 'c' * 64).get('already_pending')
    with pytest.raises(OwnerAmbiguityGate, match='disagrees'):
        scope.upload_bound('refup_b')
    with pytest.raises(OwnerAmbiguityGate, match='disagrees'):
        scope.promote_pending_to_ambiguity('refup_b', 'x')


def test_latched_scope_refuses_new_upload_pending(tmp_path):
    scope = authority(tmp_path)
    scope.latch('GENERATE_AMBIGUITY', 'historical breach class')
    with pytest.raises(OwnerAmbiguityGate, match='latched'):
        scope.enter_upload_pending('refup_x', 'c' * 64)


def test_bound_and_pending_history_is_durable(tmp_path):
    scope = authority(tmp_path)
    scope.enter_upload_pending('refup_a', 'c' * 64)
    scope.upload_bound('refup_a')
    reloaded = MutationAuthority(tmp_path / 'scope', 'TEST-008-SCOPE')
    assert reloaded.authority == AUTHORITY_OPEN
    assert reloaded._state['uploads_bound'][0]['reservation_id'] == 'refup_a'
    kinds = [event['kind'] for event in reloaded._state['events']]
    assert 'QUALIFIED_UPLOAD_PENDING_ENTERED' in kinds
    assert 'QUALIFIED_UPLOAD_BOUND' in kinds
