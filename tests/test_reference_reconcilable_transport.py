"""Offline state-machine proof; no live provider qualification is claimed."""
import hashlib
import io
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest
from PIL import Image, ImageDraw

from film_pipeline.live_runtime import Asset
from film_pipeline.store import SQLiteStore
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcSession, FlowReferenceRpcDrift, OwnerAuthRequired)
from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore, OwnerAmbiguityGate, _key
from film_pipeline.providers.flow_reference_transport import FlowReferenceTransport, image_comparison

PROJECT = '11111111-2222-3333-4444-555555555555'
REMOTE = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
OTHER = '99999999-8888-7777-6666-555555555555'
ACCOUNT = 'project_scoped_unverified_account'


def png(color=(20, 80, 140), pattern=True):
    image = Image.new('RGB', (128, 72), color)
    if pattern:
        draw = ImageDraw.Draw(image)
        draw.rectangle((6, 8, 45, 60), fill=(190, 35, 50))
        draw.ellipse((58, 10, 109, 62), fill=(50, 190, 130))
    stream = io.BytesIO()
    image.save(stream, 'PNG')
    return stream.getvalue()


class Crash(BaseException):
    pass


class Session:
    project_id = PROJECT
    catalog_fingerprint = contract.QUALIFIED_BASELINE_FINGERPRINT

    def __init__(self):
        self.uploads = self.catalogs = self.reads = 0
        self.remote = {}
        self.mode = 'normal'
        self.delays = 0
        self.on_read = lambda: None

    def upload_reference(self, data, request_id, *, before_post, on_http_response, on_identified):
        before_post(hashlib.sha256(data).hexdigest())
        self.uploads += 1
        if self.mode != 'not_received':
            self.remote[REMOTE] = data
        if self.mode in ('lost_response', 'not_received'):
            raise TimeoutError('simulated response loss')
        on_http_response(200, 100)
        if self.mode == 'parse_failure':
            raise ValueError('simulated parser failure')
        on_identified(REMOTE)
        if self.mode == 'crash_after_identity':
            raise Crash()
        return REMOTE

    def catalog(self):
        self.catalogs += 1
        return [[identity, PROJECT, 'IMAGE', 'CAE', None, None, None] for identity in self.remote]

    def media(self, identity, kind):
        self.reads += 1
        self.on_read()
        if self.delays:
            self.delays -= 1
            return None
        return self.remote.get(identity)


def setup(tmp_path):
    path = tmp_path / 'reference.png'
    data = png()
    path.write_bytes(data)
    asset = Asset(asset_id='asset_test_reference', asset_type='image', origin='reference',
        uri_or_path=str(path.resolve()), sha256=hashlib.sha256(data).hexdigest(),
        mime_type='image/png', width=128, height=72, file_size=len(data),
        rights_metadata={'source_kind': 'deterministic_synthetic_fixture'})
    runtime = SQLiteStore(tmp_path / 'runtime.sqlite')
    runtime.initialize()
    runtime.save_reference_asset(asset)
    store, session = ReferenceUploadStore(runtime.path), Session()
    transport = FlowReferenceTransport(store, session, account_id=ACCOUNT,
        evidence_dir=tmp_path / 'evidence', interval_s=0, probes=2)
    key = _key('flow_veo', PROJECT, ACCOUNT, asset)
    return asset, store, session, transport, key


def test_normal_identity_is_durable_before_readback(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    session.on_read = lambda: assert_identified(store, key)
    receipt = transport.ensure_verified(asset)
    assert receipt['media_id'] == REMOTE and session.uploads == 1
    stages = [e['stage'] for e in store.events(key)]
    assert stages == ['LOCAL_RESERVED', 'REQUEST_ARMED', 'HTTP_RESPONSE_OBSERVED',
                      'REMOTE_RESOURCE_IDENTIFIED', 'REMOTE_RESOURCE_VERIFIED']


def assert_identified(store, key):
    assert ReferenceUploadStore(store.db_path).read_progress(key)['effective_state'] == 'REMOTE_RESOURCE_IDENTIFIED'


def test_crash_before_effect_preserves_local_intent_and_can_arm_once(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    store.reserve_local('flow_veo', PROJECT, ACCOUNT, asset)
    assert store.read_progress(key)['upload_attempts'] == 0
    assert session.uploads == 0
    transport.ensure_verified(asset)
    assert session.uploads == 1


@pytest.mark.parametrize('mode', ['lost_response', 'parse_failure'])
def test_lost_or_unparsed_response_readonly_reconciliation(tmp_path, mode):
    asset, store, session, transport, key = setup(tmp_path)
    session.mode = mode
    with pytest.raises(OwnerAmbiguityGate, match='upload armed'):
        transport.ensure_verified(asset)
    assert store.read_progress(key)['media_id'] is None
    if mode == 'parse_failure':
        assert any(e['stage'] == 'HTTP_RESPONSE_OBSERVED' for e in store.events(key))
    receipt = transport.reconcile_only(asset)
    assert receipt['media_id'] == REMOTE and session.uploads == 1


def test_crash_after_identity_restarts_verification_only(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    session.mode = 'crash_after_identity'
    with pytest.raises(Crash):
        transport.ensure_verified(asset)
    assert_identified(store, key)
    receipt = FlowReferenceTransport(ReferenceUploadStore(store.db_path), session,
        account_id=ACCOUNT, evidence_dir=tmp_path / 'evidence', interval_s=0).ensure_verified(asset)
    assert receipt['media_id'] == REMOTE and session.uploads == 1


def test_cdn_delay_retains_id_through_all_readbacks(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    session.delays = 2
    session.on_read = lambda: assert_identified(store, key)
    transport.ensure_verified(asset)
    assert session.reads == 3 and session.uploads == 1


def test_verified_reference_reused_across_shots_without_network(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    first = transport.ensure_verified(asset)
    session.catalog = Mock(side_effect=AssertionError('network forbidden'))
    session.media = Mock(side_effect=AssertionError('network forbidden'))
    session.upload_reference = Mock(side_effect=AssertionError('upload forbidden'))
    assert transport.ensure_verified(asset) == first
    session.upload_reference.assert_not_called()
    session.catalog.assert_not_called()
    session.media.assert_not_called()


def test_catalog_miss_is_unresolved_never_absence_or_retry(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    session.mode = 'not_received'
    with pytest.raises(OwnerAmbiguityGate):
        transport.ensure_verified(asset)
    with pytest.raises(OwnerAmbiguityGate, match='unresolved'):
        transport.reconcile_only(asset)
    assert session.uploads == 1
    assert store.read_progress(key)['effective_state'] == 'FAILED_AMBIGUOUS'


@pytest.mark.parametrize('second', ['matching', 'unreadable'])
def test_all_candidates_exhausted_before_identity_binding(tmp_path, second):
    asset, store, session, transport, key = setup(tmp_path)
    store.reserve_once('flow_veo', PROJECT, ACCOUNT, asset)  # Legacy uncertain row.
    session.remote = {REMOTE: Path(asset.uri_or_path).read_bytes(),
                      OTHER: Path(asset.uri_or_path).read_bytes() if second == 'matching' else None}
    with pytest.raises(OwnerAmbiguityGate):
        transport.reconcile_only(asset)
    assert store.read_progress(key)['media_id'] is None
    assert session.reads >= 2 and session.uploads == 0


def test_source_mutation_rejected_without_reservation_or_upload(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    Path(asset.uri_or_path).write_bytes(png((25, 80, 140)))
    with pytest.raises(ValueError, match='mutation'):
        transport.ensure_verified(asset)
    assert store.read_progress(key) is None and session.uploads == 0


def test_uniform_color_dhash_collision_is_not_a_strong_match():
    result = image_comparison(png((10, 10, 10), False), png((220, 220, 220), False))
    assert result['dhash256_distance'] == 0 and not result['strong_match']


def test_resource_identity_immutable_and_journal_append_only(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    transport.ensure_verified(asset)
    with pytest.raises(OwnerAmbiguityGate, match='changed'):
        store.record_identified(key, OTHER, method='upload_response', evidence_hash='0' * 64)
    with sqlite3.connect(store.db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            connection.execute('DELETE FROM reference_upload_events')


def test_concurrent_arm_consumes_only_one_budget(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    store.reserve_local('flow_veo', PROJECT, ACCOUNT, asset)
    def arm():
        try:
            store.arm_local(key, '1' * 64)
            return 'armed'
        except OwnerAmbiguityGate:
            return 'refused'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: arm(), range(2))) == ['armed', 'refused']
    assert sum(e['stage'] == 'REQUEST_ARMED' for e in store.events(key)) == 1


def test_frozen_legacy_payload_untouched_until_unique_recovery(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    store.reserve_once('flow_veo', PROJECT, ACCOUNT, asset)
    with sqlite3.connect(store.db_path) as connection:
        before = connection.execute('SELECT payload FROM reference_uploads').fetchone()[0]
    assert store.read_progress(key)['effective_state'] == 'LEGACY_RESERVED_UNCERTAIN'
    with pytest.raises(OwnerAmbiguityGate):
        transport.reconcile_only(asset)
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute('SELECT payload FROM reference_uploads').fetchone()[0] == before
    assert session.uploads == 0


def test_legacy_payload_tamper_is_detected(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    store.reserve_once('flow_veo', PROJECT, ACCOUNT, asset)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE reference_uploads SET media_id=?", (REMOTE,))
    with pytest.raises(ValueError, match='integrity'):
        store.read_progress(key)


def test_rpc_upload_persists_id_without_calling_media_and_allows_nested_metadata():
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    session.captcha = Mock(return_value='test_captcha')
    session.rpc = Mock(return_value=[[REMOTE, None, None]])
    session.media = Mock(side_effect=AssertionError('verification forbidden here'))
    order = []
    session.upload_reference(png(), PROJECT, before_post=lambda _: order.append('armed'),
        on_http_response=lambda *args: None, on_identified=lambda _: order.append('identified'))
    assert order == ['armed', 'identified']
    session.media.assert_not_called()
    session.rpc.return_value = [[REMOTE, [OTHER]]]
    identified = Mock()
    assert session.upload_reference(png(), PROJECT, before_post=lambda _: None,
        on_http_response=lambda *args: None, on_identified=identified) == REMOTE
    identified.assert_called_once_with(REMOTE)


@pytest.mark.parametrize('payload', [
    [[REMOTE, PROJECT], [PROJECT, None]],
    [[REMOTE, {'client': OTHER, 'correlation': [OTHER]}]],
    [[REMOTE, contract._new_uuid(PROJECT, 'upload-client')],
     [contract._new_uuid(PROJECT, 'upload-session'), None]],
])
def test_upload_primary_slot_allows_project_client_and_correlation_metadata(payload):
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    session.captcha = Mock(return_value='test_captcha')
    session.rpc = Mock(return_value=payload)
    session.media = Mock(side_effect=AssertionError('verification forbidden here'))
    identified = Mock()
    assert session.upload_reference(png(), PROJECT, before_post=lambda _: None,
        on_http_response=lambda *args: None, on_identified=identified) == REMOTE
    identified.assert_called_once_with(REMOTE)
    session.media.assert_not_called()


@pytest.mark.parametrize('payload', [
    [], [REMOTE],
    [[PROJECT]], [[PROJECT.upper()]],
    [[contract._new_uuid(PROJECT, 'upload-client')]],
    [[REMOTE, None], [OTHER, None]],
])
def test_upload_invalid_or_conflicting_primary_identity_never_persists(payload):
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    session.captcha = Mock(return_value='test_captcha')
    session.rpc = Mock(return_value=payload)
    identified = Mock()
    with pytest.raises(OwnerAmbiguityGate):
        session.upload_reference(png(), PROJECT, before_post=lambda _: None,
            on_http_response=lambda *args: None, on_identified=identified)
    identified.assert_not_called()


@pytest.mark.parametrize('payload_json', [
    '[[]]', '[[null]]', '[["not-a-uuid"]]',
])
def test_degenerate_identity_free_record_classifies_qualified_pending(payload_json):
    # Package-008 U2 frozen contract: a structured record claiming no media
    # identity inside a parsed maseQ response is the pre-registered qualified
    # PENDING class — never a persisted identity, never a re-upload grant.
    # Safety comes from the read-only reconciliation phase, not the shape.
    from film_pipeline.providers.flow_upload_classifier import QualifiedUploadPending
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    session.captcha = Mock(return_value='test_captcha')
    session.metadata = Mock(return_value={'source': '/project/' + PROJECT,
        'bl': 'x', 'sid': 'x', 'hl': 'en', 'at': 'x'})
    response = Mock(status=200)
    response.text.return_value = ")]}'\n\n9\n" + json.dumps(
        [["wrb.fr", "maseQ", payload_json, None, "generic"]]) + '\n'
    session.page = Mock()
    session.page.context.request.post.return_value = response
    identified = Mock()
    with pytest.raises(QualifiedUploadPending):
        session.upload_reference(png(), PROJECT, before_post=lambda _: None,
            on_http_response=lambda *args: None, on_identified=identified)
    identified.assert_not_called()


CDN_FIXTURES = Path(__file__).parent / 'fixtures/flow_reference_cdn'


@pytest.mark.parametrize('name,local_sha,remote_sha', [
    ('canary', 'dc766e136c039ce4ae25f78dc7555c161a6178e8c835cf3d37600b4d7d0e8b0e',
     '93fa8edf3093a62f6053b5ae95352d7355d803329b00cb55f336c559216d8c89'),
    ('character', '31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531',
     'af0ad578968002fd6cdfa864cbf2acbafaf3e8f140d8decbb2990cca7f71012f'),
])
def test_actual_flow_cdn_recompression_matches_with_distinct_byte_hashes(name, local_sha, remote_sha):
    source = (CDN_FIXTURES / f'{name}-source.png').read_bytes()
    observed = (CDN_FIXTURES / f'{name}-cdn.bin').read_bytes()
    assert hashlib.sha256(source).hexdigest() == local_sha
    assert hashlib.sha256(observed).hexdigest() == remote_sha
    comparison = image_comparison(source, observed)
    assert source != observed and comparison['strong_match']
    assert comparison['dhash256_distance'] == 0
    assert comparison['large_difference_fraction'] > .002
    assert comparison['method'] == 'conservative_rgb_and_detail'


@pytest.mark.parametrize('left,right', [('canary', 'character'), ('character', 'canary')])
def test_cdn_cross_reference_negative_fails(left, right):
    comparison = image_comparison((CDN_FIXTURES / f'{left}-source.png').read_bytes(),
                                  (CDN_FIXTURES / f'{right}-cdn.bin').read_bytes())
    assert not comparison['strong_match']
    assert comparison['max_channel_mae'] > 100 and comparison['dhash256_distance'] > 100


def test_localized_mutation_does_not_hide_in_low_global_error():
    source = (CDN_FIXTURES / 'canary-source.png').read_bytes()
    image = Image.open(io.BytesIO(source)).convert('RGB')
    ImageDraw.Draw(image).rectangle((0, 0, 63, 63), fill='white')
    stream = io.BytesIO()
    image.save(stream, 'PNG')
    result = image_comparison(source, stream.getvalue())
    assert result['max_channel_mae'] < 3 and not result['strong_match']


def test_expected_recovery_identity_disagreement_stops_before_binding(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    store.reserve_once('flow_veo', PROJECT, ACCOUNT, asset)
    session.remote[REMOTE] = Path(asset.uri_or_path).read_bytes()
    with pytest.raises(OwnerAmbiguityGate, match='Owner evidence'):
        transport.reconcile_only(asset, expected_media_id=OTHER)
    assert store.read_progress(key)['media_id'] is None and session.uploads == 0


def test_owner_canary_recovery_keeps_ambiguity_history_and_restarts_without_network(tmp_path, monkeypatch):
    from film_pipeline import reference_qualification as qualifier
    monkeypatch.setattr(qualifier, 'QUALIFICATION_ROOT', tmp_path / 'qualification')
    monkeypatch.setattr(qualifier, 'CANARY_MEDIA_ID', REMOTE)
    database, asset = qualifier.canary_reference()
    store = ReferenceUploadStore(database)
    project = qualifier.PROJECT_ID
    key = _key('flow_veo', project, ACCOUNT, asset)
    store.reserve_local('flow_veo', project, ACCOUNT, asset)
    store.arm_local(key, '1' * 64)
    store.record_event(key, 'HTTP_RESPONSE_OBSERVED', {'status': 200, 'response_bytes_len': 647})
    store.record_event(key, 'FAILED_AMBIGUOUS', {'diagnostic': 'upload_response_unresolved'})
    history = store.events(key)
    session = Session()
    session.project_id = project
    session.rpc_call_counts = {}
    session.remote[REMOTE] = (CDN_FIXTURES / 'canary-cdn.bin').read_bytes()
    session.remote[OTHER] = (CDN_FIXTURES / 'character-cdn.bin').read_bytes()
    session.catalog = lambda: [[identity, project, 'IMAGE', 'CAE', None, None, None]
                               for identity in session.remote]
    session.__class__.__enter__ = lambda self: self
    session.__class__.__exit__ = lambda self, *args: None
    session.upload_reference = Mock(side_effect=AssertionError('re-upload forbidden'))
    monkeypatch.setattr(qualifier, 'FlowReferenceRpcSession', lambda **kwargs: session)
    result = qualifier.recover_existing_canary(Path('unused'))
    assert result['qualification_mode'] == 'recovered_existing_upload'
    assert result['identity_method'] == 'catalog_strong_match'
    assert result['original_response_identity_observed'] is False
    assert result['upload_post_invocations_this_run'] == 0
    assert store.events(key)[:4] == history
    assert store.read_progress(key)['effective_state'] == 'REMOTE_RESOURCE_VERIFIED'
    session.upload_reference.assert_not_called()
    monkeypatch.setattr(qualifier, 'FlowReferenceRpcSession', Mock(side_effect=AssertionError('network forbidden')))
    assert qualifier.read_live_qualification() == result
    assert qualifier.recover_existing_canary(Path('unused')) == result
    evidence_path = qualifier.QUALIFICATION_ROOT / 'evidence' / f"{result['reconciliation_evidence_hash']}.json"
    evidence = json.loads(evidence_path.read_text())
    evidence['unresolved'] = [OTHER]
    evidence_path.write_text(json.dumps(evidence))
    with pytest.raises(OwnerAmbiguityGate, match='evidence mismatch'):
        qualifier.read_live_qualification()


def test_actual_http_callback_is_durable_before_parser_failure_and_no_secrets(tmp_path):
    asset, store, _, _, key = setup(tmp_path)
    store.reserve_local('flow_veo', PROJECT, ACCOUNT, asset)
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    secret = 'secret_dummy_never_persist'
    session.captcha = Mock(return_value=secret)
    session.metadata = Mock(return_value={'source': '/project/' + PROJECT,
        'bl': secret, 'sid': secret, 'hl': 'en', 'at': secret})
    response = Mock(status=200)
    response.text.return_value = ")]}'\nnot-json"
    session.page = Mock()
    session.page.context.request.post.return_value = response
    with pytest.raises(Exception, match='TRUE_AMBIGUOUS'):
        session.upload_reference(Path(asset.uri_or_path).read_bytes(), PROJECT,
            before_post=lambda digest: store.arm_local(key, digest),
            on_http_response=lambda status, length: store.record_event(key,
                'HTTP_RESPONSE_OBSERVED', {'status': status, 'response_bytes_len': length}),
            on_identified=lambda identity: store.record_identified(key, identity,
                method='upload_response', evidence_hash='2' * 64))
    assert [event['stage'] for event in store.events(key)] == [
        'LOCAL_RESERVED', 'REQUEST_ARMED', 'HTTP_RESPONSE_OBSERVED']
    assert secret.encode() not in store.db_path.read_bytes()
    assert session.rpc_call_counts['maseQ'] == 1
    session.page.context.request.post.assert_called_once()


def test_verification_failure_keeps_identified_resource_and_never_reuploads(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    session.delays = 20
    with pytest.raises(OwnerAmbiguityGate, match='retained'):
        transport.ensure_verified(asset)
    assert_identified(store, key)
    session.delays = 0
    assert transport.ensure_verified(asset)['media_id'] == REMOTE
    assert session.uploads == 1


def test_complete_requires_prior_durable_identity(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    reserved = store.reserve_once('flow_veo', PROJECT, ACCOUNT, asset)
    with pytest.raises(OwnerAmbiguityGate, match='identified'):
        store.complete(reserved, REMOTE, '1' * 64)


def test_wrong_project_catalog_is_not_a_safe_miss(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    store.reserve_once('flow_veo', PROJECT, ACCOUNT, asset)
    session.catalog = lambda: [[REMOTE, OTHER, 'IMAGE', 'CAE', None, None, None]]
    with pytest.raises(contract.ContractError, match='PROJECT_MISMATCH'):
        transport.reconcile_only(asset)
    assert session.uploads == 0 and store.read_progress(key)['media_id'] is None


@pytest.mark.parametrize('checkpoint', ['identified', 'verified_before_artifact'])
def test_canary_orchestrator_restart_reconstructs_qualification_without_upload(tmp_path, monkeypatch, checkpoint):
    from film_pipeline import reference_qualification as qualifier
    monkeypatch.setattr(qualifier, 'QUALIFICATION_ROOT', tmp_path / 'qualification')
    database, asset = qualifier.canary_reference()
    store = ReferenceUploadStore(database)
    project = qualifier.PROJECT_ID
    key = _key('flow_veo', project, ACCOUNT, asset)
    store.reserve_local('flow_veo', project, ACCOUNT, asset)
    store.arm_local(key, '1' * 64)
    store.record_event(key, 'HTTP_RESPONSE_OBSERVED', {'status': 200, 'response_bytes_len': 100})
    store.record_identified(key, REMOTE, method='upload_response', evidence_hash='2' * 64)
    session = Session()
    session.project_id = project
    session.rpc_call_counts = {}
    session.remote[REMOTE] = Path(asset.uri_or_path).read_bytes()
    session.__class__.__enter__ = lambda self: self
    session.__class__.__exit__ = lambda self, *args: None
    session.upload_reference = Mock(side_effect=AssertionError('re-upload forbidden'))
    if checkpoint == 'verified_before_artifact':
        FlowReferenceTransport(store, session, account_id=ACCOUNT,
            evidence_dir=qualifier.QUALIFICATION_ROOT / 'evidence').verify_identified(
                asset, store.read_progress(key))
    monkeypatch.setattr(qualifier, 'FlowReferenceRpcSession', lambda **kwargs: session)
    result = qualifier.run_live_canary(Path('unused'))
    assert result['result'] == 'LIVE_UPLOAD_CANARY_PASS'
    assert result['upload_post_invocations_this_run'] == 0
    assert qualifier.read_live_qualification() == result
    assert qualifier.run_live_canary(Path('unused')) == result
    session.upload_reference.assert_not_called()


@pytest.mark.parametrize('login_required', [True, False])
def test_session_bootstrap_failure_stops_before_rpc_and_preserves_safe_auth_gate(monkeypatch, login_required):
    import playwright.sync_api
    from film_pipeline.providers import flow_reference_rpc as rpc
    driver = MagicMock()
    browser = driver.chromium.launch.return_value
    page = browser.new_context.return_value.new_page.return_value
    page.wait_for_function.side_effect = TimeoutError('secret_dummy_browser_failure')
    page.evaluate.return_value = login_required
    monkeypatch.setattr(playwright.sync_api, 'sync_playwright', lambda: Mock(start=lambda: driver))
    monkeypatch.setattr(rpc, 'read_cookie_export', lambda path: [])
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    expected = OwnerAuthRequired if login_required else FlowReferenceRpcDrift
    with pytest.raises(expected) as stopped:
        session.__enter__()
    assert 'secret_dummy_browser_failure' not in str(stopped.value)
    assert "location.pathname === '/about'" in page.evaluate.call_args.args[0]
    page.context.request.post.assert_not_called()
    assert session.rpc_call_counts == {}
    browser.close.assert_called_once()
    driver.stop.assert_called_once()


def test_reconcile_unique_match_with_baseline_covered_dead_row(tmp_path):
    """A permanently unreadable row that is durably proven pre-existing
    (frozen baseline) cannot be the uploaded media; it must not block the
    unique strong match. An unresolved row WITHOUT that durable evidence
    still blocks (strict default)."""
    asset, store, session, transport, key = setup(tmp_path)
    dead_row = "99999999-8888-7777-6666-555555555555"
    session.remote = {REMOTE: png(), OTHER: png(color=(9, 9, 9), pattern=False),
                      dead_row: None}
    store.reserve_local('flow_veo', PROJECT, ACCOUNT, asset)
    store.arm_local(key, '0' * 64)
    store.record_event(key, 'FAILED_AMBIGUOUS', {'diagnostic': 'upload_response_unresolved'})
    resolved = transport.reconcile_only(asset, preexisting_ids={dead_row})
    assert resolved['media_id'] == REMOTE


def test_reconcile_unknown_dead_row_still_blocks(tmp_path):
    asset, store, session, transport, key = setup(tmp_path)
    dead_row = "99999999-8888-7777-6666-555555555555"
    session.remote = {REMOTE: png(), OTHER: png(color=(9, 9, 9), pattern=False),
                      dead_row: None}
    store.reserve_local('flow_veo', PROJECT, ACCOUNT, asset)
    store.arm_local(key, '0' * 64)
    store.record_event(key, 'FAILED_AMBIGUOUS', {'diagnostic': 'upload_response_unresolved'})
    with pytest.raises(OwnerAmbiguityGate, match='unresolved; no re-upload'):
        transport.reconcile_only(asset)
