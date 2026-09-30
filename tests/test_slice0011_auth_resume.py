"""Offline restoration proof; no real Flow session or production ledger mutation."""
import importlib.util
import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

from film_pipeline.core import canonical_json, sha256
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.slice0011 import PROJECT_ID
from film_pipeline import slice0011_successor as successor
from test_slice0011_successor import parent, snapshot
from test_flow_r2v_compact import OTHER_OUTPUT


@pytest.fixture
def entry(parent, tmp_path, monkeypatch):
    database, store, _, session, _ = parent
    spec = importlib.util.spec_from_file_location('auth_resume_test', Path(__file__).parents[1] / 'tools/slice0011_auth_resume.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    previous = {'gate': 'OWNER_AMBIGUITY_GATE', 'stop_type': 'OwnerAuthRequired',
        'rpc_calls': {}, 'mzza6b_submits': 0, 'reference_uploads': 0, 'shot_b_submits': 0,
        'dola_seedance_calls': 0, 'asset': None, 'output_identity': None,
        'historical_unchanged': True, 'historical_before_hash': sha256(json.loads(snapshot(database))),
        'historical_after_hash': sha256(json.loads(snapshot(database))),
        'project_id': PROJECT_ID, 'reference_media_id': successor.REFERENCE_MEDIA_ID}
    prior_path = tmp_path / 'previous.json'
    prior_path.write_text(canonical_json(previous), encoding='utf-8')
    monkeypatch.setattr(module, 'DATABASE', database)
    monkeypatch.setattr(module, 'PREVIOUS', prior_path)
    monkeypatch.setattr(module, 'PREVIOUS_HASH', module.file_sha256(prior_path))
    monkeypatch.setattr(module, 'RESTORATION', tmp_path / 'restoration')
    monkeypatch.setattr(module, 'OUTPUT', tmp_path / 'continued_successor')
    return module, previous


@pytest.mark.parametrize('field,value', [('mzza6b_submits', 1), ('reference_uploads', 1),
    ('rpc_calls', {'Zzl0ze': 1}), ('stop_type', 'FlowReferenceRpcDrift'),
    ('successor_attempt_id', 'already_allocated'), ('provider_job_id', 'already_allocated'),
    ('historical_unchanged', False), ('project_id', OTHER_OUTPUT), ('reference_media_id', OTHER_OUTPUT)])
def test_prior_stop_scope_is_exact_before_provider_access(parent, entry, monkeypatch, field, value):
    database, store, _, _, _ = parent
    module, previous = entry
    factory = Mock(side_effect=AssertionError('provider must not open'))
    monkeypatch.setattr(module, 'AuthPreflightSession', factory)
    with pytest.raises(OwnerAmbiguityGate):
        module.validate_previous_stop(store, {**previous, field: value})
    factory.assert_not_called()


def test_existing_allocation_cannot_restore_allowance(parent, entry):
    database, store, _, session, receipt = parent
    module, previous = entry
    successor.freeze_successor(database, session, receipt)
    with pytest.raises(OwnerAmbiguityGate):
        module.validate_previous_stop(store, previous)


@pytest.mark.parametrize('defect', ['absent', 'duplicate', 'unresolved', 'changed_bytes', 'contract', 'none'])
def test_reference_preflight_is_exhaustive_unique_and_non_mutating(parent, entry, monkeypatch, defect):
    database, store, _, session, _ = parent
    module, _ = entry
    before = module.file_sha256(database)
    monkeypatch.setattr(contract, 'sanitize_session', lambda meta, project: {'metadata_coherent': True})
    records = [[successor.REFERENCE_MEDIA_ID, PROJECT_ID, None, 'CAE', None, None, None],
               [OTHER_OUTPUT, PROJECT_ID, None, 'CAE', None, None, None]]
    session.catalog.return_value = records
    session.media.side_effect = lambda identity, kind: b'exact' if identity == successor.REFERENCE_MEDIA_ID else b'other'
    def compare(source, data):
        return {'strong_match': data == b'exact', 'provider_media_sha256': '2' * 64}
    monkeypatch.setattr(module, 'image_comparison', compare)
    if defect == 'absent':
        records.pop(0)
    elif defect == 'duplicate':
        session.media.side_effect = lambda *args: b'exact'
    elif defect == 'unresolved':
        session.media.side_effect = lambda identity, kind: b'exact' if identity == successor.REFERENCE_MEDIA_ID else None
    elif defect == 'changed_bytes':
        monkeypatch.setattr(module, 'image_comparison', lambda *args: {'strong_match': True, 'provider_media_sha256': '3' * 64})
        records.pop(1)
    elif defect == 'contract':
        session.catalog_fingerprint = 'unqualified'
    if defect == 'none':
        proof = module.reference_preflight(session, store)
        assert proof['reference_uniquely_verified'] and proof['reference_usable']
        assert len(proof['image_candidates']) == 2
        assert session.media.call_count == 2
    else:
        with pytest.raises(OwnerAmbiguityGate):
            module.reference_preflight(session, store)
    assert module.file_sha256(database) == before
    session.submit_once.assert_not_called()
    session.upload_reference.assert_not_called()


def test_preflight_session_blocks_generation_upload_before_transport(entry):
    module, _ = entry
    session = module.AuthPreflightSession(cookie_path=Path('unused'), project_id=PROJECT_ID)
    for rpc in ('MZZa6b', 'maseQ', 'other'):
        with pytest.raises(OwnerAmbiguityGate):
            session._rpc_body(rpc, 'never_sent')
    with pytest.raises(OwnerAmbiguityGate):
        session.captcha('VIDEO_GENERATION')
    assert session.rpc_call_counts == {}


def test_failed_auth_is_durable_gate_without_allocation_and_no_repeated_session(parent, entry, monkeypatch):
    database, store, _, _, _ = parent
    module, _ = entry
    before = module.file_sha256(database)
    class FailedSession:
        rpc_call_counts = {}
        def __enter__(self):
            raise RuntimeError('secret_dummy_exception')
        def __exit__(self, *args):
            pass
    factory = Mock(return_value=FailedSession())
    monkeypatch.setattr(module, 'AuthPreflightSession', factory)
    result = module.run(Path('unused'), Path('unused'), preflight_only=True)
    assert result['gate'] == 'OWNER_AUTH_REVIEW_GATE'
    assert 'secret_dummy_exception' not in canonical_json(result)
    assert module.file_sha256(database) == before and successor.read_successor(store) is None
    with pytest.raises(OwnerAmbiguityGate):
        module.run(Path('unused'), Path('unused'))
    factory.assert_called_once()


def test_preflight_only_pass_cannot_allocate_or_call_generation(parent, entry, monkeypatch):
    database, store, _, session, _ = parent
    module, _ = entry
    before = module.file_sha256(database)
    class OfflineSession:
        rpc_call_counts = {'Zzl0ze': 1, 'as29s': 2}
        def __enter__(self):
            return session
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(module, 'AuthPreflightSession', Mock(return_value=OfflineSession()))
    monkeypatch.setattr(module, 'reference_preflight', lambda *args: {'all_five_checks_pass': True})
    result = module.run(Path('unused'), Path('unused'), preflight_only=True)
    assert result['gate'] == 'AUTH_RESTORATION_PREFLIGHT_PASS'
    assert module.file_sha256(database) == before and successor.read_successor(store) is None
    session.submit_once.assert_not_called()


def test_phase_two_only_delegates_after_complete_read_only_proof(parent, entry, monkeypatch):
    from types import SimpleNamespace
    database, store, _, session, _ = parent
    module, _ = entry
    prior_bytes = module.PREVIOUS.read_bytes()
    class OfflineSession:
        rpc_call_counts = {'Zzl0ze': 1, 'as29s': 2}
        def __enter__(self):
            return session
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(module, 'AuthPreflightSession', Mock(return_value=OfflineSession()))
    monkeypatch.setattr(module, 'reference_preflight', lambda *args: {'all_five_checks_pass': True})
    delegated = SimpleNamespace(run=Mock(return_value={'gate': 'OWNER_AMBIGUITY_GATE', 'mzza6b_submits': 1}))
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
    monkeypatch.setattr(module.importlib.util, 'spec_from_file_location', Mock(return_value=spec))
    monkeypatch.setattr(module.importlib.util, 'module_from_spec', Mock(return_value=delegated))
    result = module.run(Path('cookie_fixture'), Path('original_brief_fixture'))
    assert result['gate'] == 'OWNER_AMBIGUITY_GATE'
    delegated.run.assert_called_once_with(Path('cookie_fixture'), Path('original_brief_fixture'))
    assert delegated.OUTPUT == module.OUTPUT
    assert module.PREVIOUS.read_bytes() == prior_bytes
    with pytest.raises(OwnerAmbiguityGate):
        module.run(Path('cookie_fixture'), Path('original_brief_fixture'))
    delegated.run.assert_called_once()
