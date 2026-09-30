"""Offline proof of the one-grant successor boundary; TEMP databases only."""
import importlib.util
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from film_pipeline.core import canonical_json, sha256
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from film_pipeline.slice0011 import (PROJECT_ID, ACCOUNT_ID, REFERENCE_ASSET_ID,
                                    compile_character_paths, _existing_job_for_shot, submit_and_acquire_shot)
from film_pipeline.store import SQLiteStore
from film_pipeline import slice0011_successor as successor
from test_flow_r2v_compact import prepared, row, OUTPUT, OTHER_OUTPUT, framed
from film_pipeline.providers import flow_rpc_contract as contract


@pytest.fixture
def parent(tmp_path, monkeypatch):
    database, plan, session, job = prepared(tmp_path)
    store = SQLiteStore(database)
    store.reserve_dispatch(job.provider_job_id)
    store.record_dispatch_fact(job.provider_job_id, 'AMBIGUOUS_EVIDENCE', {'diagnostic': 'historical_owner_gate'})
    monkeypatch.setattr(successor, 'PARENT_JOB', job.provider_job_id)
    monkeypatch.setattr(successor, 'PARENT_ATTEMPT', job.generation_attempt_id)
    receipt = ReferenceUploadStore(database).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID,
                                                          store.read_reference_asset(REFERENCE_ASSET_ID))
    return database, store, plan, session, receipt


def snapshot(database):
    with sqlite3.connect(database) as connection:
        return canonical_json(successor.historical_snapshot(connection))


def counts(database):
    with sqlite3.connect(database) as connection:
        return [connection.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                for t in ('generation_attempts', 'provider_jobs')]


def test_allocation_is_unique_atomic_and_preserves_old_and_canonical(parent):
    database, store, plan, session, receipt = parent
    before = snapshot(database)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: successor.freeze_successor(database, session, receipt), range(2)))
    job = jobs[0]
    assert jobs[1] == job and successor.freeze_successor(database, session, receipt) == job
    assert counts(database) == [2, 2] and snapshot(database) == before
    assert store.read_path(job.generation_attempt_id)[1] == plan
    assert sha256(plan) == successor.PLAN_HASH
    assert job.correlation_evidence['supersedes_attempt'] == successor.PARENT_ATTEMPT
    assert job.provider_job_id != successor.PARENT_JOB
    prompt = job.correlation_evidence['prompt']
    assert len(prompt.rsplit('\n', 1)[0]) == 430
    assert prompt.count('[FILM-') == 1 and prompt.endswith('[FILM-' + job.provider_job_id + ']')
    with pytest.raises(OwnerAmbiguityGate, match='multiple'):
        _existing_job_for_shot(store, 'CHAR_CONTINUITY_A')
    with pytest.raises(RuntimeError, match='consumed'):
        store.reserve_dispatch(job.provider_job_id)  # Ordinary shot budget is unchanged.


def test_allocation_rolls_back_path_job_and_authority_on_fault(parent, monkeypatch):
    database, store, _, session, receipt = parent
    before = snapshot(database)
    original = SQLiteStore._insert_immutable
    def fault(connection, table, *args):
        if table == 'generation_attempts':
            raise RuntimeError('injected_crash')
        return original(connection, table, *args)
    monkeypatch.setattr(SQLiteStore, '_insert_immutable', staticmethod(fault))
    with pytest.raises(RuntimeError, match='injected'):
        successor.freeze_successor(database, session, receipt)
    assert counts(database) == [1, 1] and snapshot(database) == before
    assert successor.read_successor(store) is None


def test_concurrent_reservation_consumes_authority_once(parent):
    database, store, _, session, receipt = parent
    job = successor.freeze_successor(database, session, receipt)
    before = snapshot(database)
    def reserve(_):
        try:
            return successor.reserve_successor_dispatch(store, job.provider_job_id, successor.AUTHORITY_ID)
        except OwnerAmbiguityGate:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        reserved = list(pool.map(reserve, range(2)))
    assert sum(value is not None for value in reserved) == 1
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT COUNT(*) FROM slice0011_successor_consumptions').fetchone()[0] == 1
    assert snapshot(database) == before
    assert store.read_dispatch_facts(job.provider_job_id)[0]['kind'] == 'RESERVED'


def test_reservation_rolls_back_consumption_and_count_on_fact_failure(parent, monkeypatch):
    database, store, _, session, receipt = parent
    job = successor.freeze_successor(database, session, receipt)
    monkeypatch.setattr(successor, 'append_fact', Mock(side_effect=RuntimeError('journal_crash')))
    with pytest.raises(RuntimeError, match='journal_crash'):
        successor.reserve_successor_dispatch(store, job.provider_job_id, successor.AUTHORITY_ID)
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 0
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT COUNT(*) FROM slice0011_successor_consumptions').fetchone()[0] == 0


def test_reserved_before_post_crash_cannot_submit_after_restart(parent, tmp_path):
    database, store, _, session, receipt = parent
    job = successor.freeze_successor(database, session, receipt)
    successor.reserve_successor_dispatch(store, job.provider_job_id, successor.AUTHORITY_ID)
    with pytest.raises(OwnerAmbiguityGate, match='no redispatch'):
        submit_and_acquire_shot(database, session, successor.read_successor(store), tmp_path,
                               successor_authority_id=successor.AUTHORITY_ID, poll_seconds=0)
    session.submit_once.assert_not_called()


@pytest.mark.parametrize('field,value', [('supersedes_attempt', 'another_attempt'),
    ('successor_authority_id', 'another_grant'), ('provider_prompt_compiler', 'legacy'),
    ('historical_snapshot_sha256', 'f' * 64), ('owner_brief_sha256', 'e' * 64)])
def test_successor_provenance_is_frozen(parent, field, value):
    database, store, _, session, receipt = parent
    job = successor.freeze_successor(database, session, receipt)
    modified = job.model_copy(update={'correlation_evidence': {**job.correlation_evidence, field: value}})
    with pytest.raises(ValueError, match='FROZEN_PROVIDER_INTENT_CHANGED'):
        store.save_provider_job(modified)


@pytest.mark.parametrize('defect', ['wrong_project', 'wrong_reference', 'wrong_authority', 'changed_history', 'wrong_shot'])
def test_wrong_scope_or_changed_history_fails_closed(parent, defect, monkeypatch):
    database, store, _, session, receipt = parent
    before = snapshot(database)
    if defect == 'wrong_project':
        session.project_id = OTHER_OUTPUT
        with pytest.raises(OwnerAmbiguityGate):
            successor.freeze_successor(database, session, receipt)
        assert counts(database) == [1, 1]
    elif defect == 'wrong_reference':
        with pytest.raises(OwnerAmbiguityGate):
            successor.freeze_successor(database, session, {**receipt, 'media_id': OTHER_OUTPUT})
        assert counts(database) == [1, 1]
    else:
        job = successor.freeze_successor(database, session, receipt)
        if defect == 'wrong_authority':
            with pytest.raises(OwnerAmbiguityGate, match='authority'):
                successor.reserve_successor_dispatch(store, job.provider_job_id, 'wrong')
        elif defect == 'changed_history':
            store.record_dispatch_fact(successor.PARENT_JOB, 'OBSERVATION_FAILURE', {'diagnostic': 'external_changed_history'})
            with pytest.raises(OwnerAmbiguityGate, match='historical'):
                successor.reserve_successor_dispatch(store, job.provider_job_id, successor.AUTHORITY_ID)
        else:
            with sqlite3.connect(database) as connection:
                raw = json.loads(connection.execute('SELECT payload FROM generation_attempts WHERE id=?', (job.generation_attempt_id,)).fetchone()[0])
                raw['shot_id'] = 'CHAR_CONTINUITY_B'
                connection.execute('UPDATE generation_attempts SET payload=? WHERE id=?', (canonical_json(raw), job.generation_attempt_id))
            with pytest.raises((OwnerAmbiguityGate, ValueError)):
                submit_and_acquire_shot(database, session, job, Path(database).parent,
                                       successor_authority_id=successor.AUTHORITY_ID, poll_seconds=0)
        assert store.read_provider_job(job.provider_job_id).dispatch_count == 0
    if defect != 'changed_history':
        assert snapshot(database) == before
    session.submit_once.assert_not_called()


@pytest.mark.parametrize('outcome', ['absent', 'conflicting', 'unique'])
def test_one_submit_outcomes_preserve_history_and_fail_closed(parent, tmp_path, monkeypatch, outcome):
    database, store, _, session, receipt = parent
    job = successor.freeze_successor(database, session, receipt)
    before = snapshot(database)
    def submit(prompt, reference, request_id, *, before_post, on_diagnostics):
        assert store.read_provider_job(job.provider_job_id).dispatch_count == 1
        before_post('3' * 64)
        on_diagnostics(contract.submission_diagnostics(framed(None)))
        if outcome != 'absent':
            session.catalog.return_value = [row(prompt=prompt)]
            if outcome == 'conflicting':
                session.catalog.return_value.append(row(prompt=prompt, output=OTHER_OUTPUT))
    session.submit_once.side_effect = submit
    if outcome == 'unique':
        from film_pipeline import slice0011
        monkeypatch.setattr(slice0011, '_acquire_bound', lambda db, s, j, out: 'exact_offline_asset')
        assert submit_and_acquire_shot(database, session, job, tmp_path,
            successor_authority_id=successor.AUTHORITY_ID, poll_seconds=0) == 'exact_offline_asset'
        assert store.read_provider_job(job.provider_job_id).external_job_id == OUTPUT
    else:
        with pytest.raises(OwnerAmbiguityGate, match='no redispatch'):
            submit_and_acquire_shot(database, session, job, tmp_path,
                successor_authority_id=successor.AUTHORITY_ID, poll_seconds=0)
        assert store.read_output_bindings(job.provider_job_id) == []
    assert snapshot(database) == before
    assert counts(database) == [2, 2]
    session.submit_once.assert_called_once()
    session.upload_reference.assert_not_called()
    with pytest.raises(OwnerAmbiguityGate):
        submit_and_acquire_shot(database, session, successor.read_successor(store), tmp_path,
            successor_authority_id=successor.AUTHORITY_ID, poll_seconds=0)
    session.submit_once.assert_called_once()


def test_successor_session_rejects_uploads_and_second_video_before_transport(monkeypatch):
    spec = importlib.util.spec_from_file_location('successor_live', Path(__file__).parents[1] / 'tools/slice0011_successor_live.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    session = module.SuccessorSession(cookie_path=Path('unused'), project_id=PROJECT_ID)
    with pytest.raises(OwnerAmbiguityGate, match='forbids'):
        session._rpc_body('maseQ', 'never sent')
    session.rpc_call_counts['MZZa6b'] = 1
    with pytest.raises(OwnerAmbiguityGate, match='no retry'):
        session._rpc_body('MZZa6b', 'never sent')


@pytest.fixture
def live_entry(parent, tmp_path, monkeypatch):
    database, store, plan, session, receipt = parent
    spec = importlib.util.spec_from_file_location('successor_live_test', Path(__file__).parents[1] / 'tools/slice0011_successor_live.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'DATABASE', database)
    monkeypatch.setattr(module, 'OUTPUT', tmp_path / 'successor_evidence')
    monkeypatch.setattr(module, 'PARENT_JOB', successor.PARENT_JOB)
    monkeypatch.setattr(module, 'PARENT_ATTEMPT', successor.PARENT_ATTEMPT)
    monkeypatch.setattr(module, 'require_production_reference', lambda: None)
    brief = tmp_path / 'authority.txt'
    brief.write_text('offline authority fixture', encoding='utf-8')
    monkeypatch.setattr(module, 'OWNER_BRIEF_SHA256', module.file_sha256(brief))
    session.rpc_call_counts = {}
    class OfflineSession:
        def __getattr__(self, name):
            return getattr(session, name)
        def __enter__(self):
            return session
        def __exit__(self, *args):
            return False
        @property
        def rpc_call_counts(self):
            return session.rpc_call_counts
    factory = Mock(return_value=OfflineSession())
    monkeypatch.setattr(module, 'SuccessorSession', factory)
    def bounded(*args, **kwargs):
        return submit_and_acquire_shot(*args, **kwargs, poll_seconds=0)
    monkeypatch.setattr(module, 'submit_and_acquire_shot', bounded)
    return module, brief, factory


@pytest.mark.parametrize('outcome', ['absent', 'download_failure', 'unique'])
def test_complete_cli_preserves_history_reports_stop_and_never_restarts(parent, live_entry, monkeypatch, tmp_path, outcome):
    import subprocess
    from PIL import Image
    from film_pipeline import slice0011
    database, store, _, session, _ = parent
    module, brief, factory = live_entry
    before = snapshot(database)
    def submit(prompt, reference, request_id, *, before_post, on_diagnostics):
        session.rpc_call_counts['MZZa6b'] = 1
        before_post('3' * 64)
        on_diagnostics(contract.submission_diagnostics(framed(None)))
        if outcome != 'absent':
            session.catalog.return_value = [row(prompt=prompt)]
    session.submit_once.side_effect = submit
    if outcome == 'download_failure':
        monkeypatch.setattr(slice0011, '_acquire_bound', Mock(side_effect=ValueError('offline_download_failure')))
    elif outcome == 'unique':
        video = tmp_path / 'exact_offline_video.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
            'testsrc2=size=640x360:rate=24:duration=8', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)], check=True)
        session.media.return_value = video.read_bytes()
    report = module.run(Path('unused_cookie'), brief)
    job_id = report['provider_job_id']
    assert report['historical_unchanged'] and snapshot(database) == before
    assert report['mzza6b_submits'] == 1 and report['successor_dispatch_count'] == 1
    assert report['shot_b_submits'] == report['reference_uploads'] == report['dola_seedance_calls'] == 0
    assert counts(database) == [2, 2]
    assert report == json.loads((module.OUTPUT / 'live_result.json').read_text())
    facts = store.read_dispatch_facts(job_id)
    if outcome == 'unique':
        assert report['gate'] == 'OWNER_CHARACTER_CONTINUITY_REVIEW_GATE'
        assert report['output_identity'] == OUTPUT
        packet = json.loads((module.OUTPUT / 'character_review.json').read_text())
        middle = packet['full_resolution_middle']
        assert module.file_sha256(Path(middle['path'])) == middle['sha256']
        with Image.open(middle['path']) as image:
            assert image.size == (640, 360)
        assert all(r['verdict'] == 'pass' for r in packet['technical'])
        assert packet['selected_take_created'] is False
        with sqlite3.connect(database) as connection:
            assert connection.execute('SELECT COUNT(*) FROM selected_takes').fetchone()[0] == 0
    else:
        assert report['gate'] == 'OWNER_AMBIGUITY_GATE' and report['asset'] is None
        assert sum(f['kind'] == 'AMBIGUOUS_EVIDENCE' for f in facts) == 1
    with pytest.raises(OwnerAmbiguityGate, match='durable successor stop'):
        module.run(Path('unused_cookie'), brief)
    factory.assert_called_once()
    session.submit_once.assert_called_once()
    session.upload_reference.assert_not_called()


def test_pre_reservation_baseline_drift_is_terminal_before_provider_restart(parent, live_entry):
    database, store, _, session, _ = parent
    module, brief, factory = live_entry
    before = snapshot(database)
    session.catalog.side_effect = [[], [row(output=OTHER_OUTPUT)]]
    report = module.run(Path('unused_cookie'), brief)
    assert report['gate'] == 'OWNER_AMBIGUITY_GATE'
    assert report['successor_dispatch_count'] == report['mzza6b_submits'] == 0
    assert counts(database) == [2, 2] and snapshot(database) == before
    with pytest.raises(OwnerAmbiguityGate, match='durable successor stop'):
        module.run(Path('unused_cookie'), brief)
    factory.assert_called_once()
    session.submit_once.assert_not_called()
