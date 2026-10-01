import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_slice0011_successor import parent
from film_pipeline import slice0011_successor as old
from film_pipeline import slice0011_canonical_reproof as new
from film_pipeline.core import canonical_json, sha256
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate


@pytest.fixture
def history(parent, monkeypatch, tmp_path):
    db, store, plan, session, receipt = parent
    second = old.freeze_successor(db, session, receipt)
    old.reserve_successor_dispatch(store, second.provider_job_id, old.AUTHORITY_ID)
    store.record_dispatch_fact(second.provider_job_id, 'AMBIGUOUS_EVIDENCE', {'diagnostic': 'historical_gate'})
    monkeypatch.setattr(new, 'HISTORICAL_JOBS', (old.PARENT_JOB, second.provider_job_id))
    # Grant unit tests isolate persisted reference verification, which is
    # exercised independently by binding tests and the live read-only preflight.
    monkeypatch.setattr(new, 'verify_attestation', lambda store, asset, attestation, **kw: attestation)
    proof = {'asset_id': new.REFERENCE_ASSET_ID, 'source_sha256': new.REFERENCE_SHA256,
        'project_id': new.PROJECT_ID, 'media_id': new.REFERENCE_MEDIA_ID,
        'account_id': new.ACCOUNT_ID, 'provider_id': 'flow_veo',
        'version': 'flow-canonical-reference-v1', 'attestation_id': 'refbind_' + 'a' * 64}
    return db, store, session, proof, tmp_path


def snapshot(store):
    with sqlite3.connect(store.path) as c:
        return sha256(new.historical_snapshot(c))


def test_fresh_grant_preserves_history_and_consumes_once(history):
    db, store, session, proof, directory = history
    before = snapshot(store)
    job = new.freeze_reproof(db, session, proof, directory)
    assert snapshot(store) == before
    assert job.correlation_evidence['reference_binding']['media_id'] == new.REFERENCE_MEDIA_ID
    with pytest.raises(RuntimeError): store.reserve_dispatch(job.provider_job_id)
    def reserve(_):
        try: return new.reserve_reproof_dispatch(store, job.provider_job_id, proof, directory)
        except OwnerAmbiguityGate: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, range(2)))
    assert sum(r is not None for r in results) == 1
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 1
    assert snapshot(store) == before
    with pytest.raises(OwnerAmbiguityGate): new.freeze_reproof(db, session, proof, directory)
    session.submit_once.assert_not_called()


@pytest.mark.parametrize('field,value', [('media_id', '347f9951-5bbc-4910-b6fd-3a17c74e29d2'),
    ('source_sha256', 'f' * 64), ('asset_id', 'other'), ('project_id', 'other'), ('account_id', 'other')])
def test_wrong_reference_or_scope_blocks_reservation(history, field, value):
    db, store, session, proof, directory = history
    job = new.freeze_reproof(db, session, proof, directory)
    with pytest.raises(OwnerAmbiguityGate):
        new.reserve_reproof_dispatch(store, job.provider_job_id, {**proof, field: value}, directory)
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 0


def test_attestation_failure_blocks_freeze_and_reservation(history, monkeypatch):
    db, store, session, proof, directory = history
    job = new.freeze_reproof(db, session, proof, directory)
    def reject(*args, **kwargs): raise OwnerAmbiguityGate('CONTENT_MISMATCH')
    monkeypatch.setattr(new, 'verify_attestation', reject)
    with pytest.raises(OwnerAmbiguityGate): new.reserve_reproof_dispatch(store, job.provider_job_id, proof, directory)
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 0


def test_changed_history_or_native_intent_cannot_be_promoted(history):
    db, store, session, proof, directory = history
    job = new.freeze_reproof(db, session, proof, directory)
    bad = job.model_copy(deep=True)
    bad.correlation_evidence['native_ui_intent']['attestation_sha256'] = 'b' * 64
    with pytest.raises(ValueError, match='FROZEN_PROVIDER_INTENT_CHANGED'): store.save_provider_job(bad)
    store.record_dispatch_fact(new.HISTORICAL_JOBS[1], 'OBSERVATION_FAILURE', {'diagnostic': 'history_changed'})
    with pytest.raises(OwnerAmbiguityGate): new.reserve_reproof_dispatch(store, job.provider_job_id, proof, directory)
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 0


def test_journal_failure_rolls_back_budget(history, monkeypatch):
    db, store, session, proof, directory = history
    job = new.freeze_reproof(db, session, proof, directory)
    def fail(*args, **kwargs): raise RuntimeError('journal_failure')
    monkeypatch.setattr(new, 'append_fact', fail)
    with pytest.raises(RuntimeError): new.reserve_reproof_dispatch(store, job.provider_job_id, proof, directory)
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 0
    with sqlite3.connect(db) as c:
        assert c.execute(f'SELECT COUNT(*) FROM {new.TABLE}_consumption').fetchone()[0] == 0
