"""Exact catalog differential and read-only absence; no live provider operations."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from test_flow_r2v_compact import row, OUTPUT, OTHER_OUTPUT


@pytest.fixture
def entry():
    spec = importlib.util.spec_from_file_location('successor_reconciliation_test', Path(__file__).parents[1] / 'tools/slice0011_reconcile_successor.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('case,verdict', [('absent','NO_DURABLE_OUTPUT_OBSERVED'),
    ('unique','UNIQUE_EXISTING_OUTPUT_RECOVERED'), ('multiple','CONFLICTING_OR_NONUNIQUE_OUTPUT'),
    ('wrong_reference','CONFLICTING_OR_NONUNIQUE_OUTPUT'), ('wrong_model','CONFLICTING_OR_NONUNIQUE_OUTPUT'),
    ('baseline_marker','CONFLICTING_OR_NONUNIQUE_OUTPUT'), ('lineage_conflict','CONFLICTING_OR_NONUNIQUE_OUTPUT')])
def test_differential_keeps_all_ownership_requirements(entry, case, verdict):
    records = [] if case == 'absent' else [row(prompt='Compact creative body. ' + entry.MARKER)]
    if case == 'multiple':
        records.append(row(prompt='Compact creative body. ' + entry.MARKER, output=OTHER_OUTPUT))
    elif case == 'wrong_reference':
        records[0][5][6][1][1][0][2] = OTHER_OUTPUT
    elif case == 'wrong_model':
        records[0][5][6][1][0][0] = 'abra_t2v_8s'
    elif case == 'baseline_marker':
        records[0][0] = entry.BASELINE[-1]
    elif case == 'lineage_conflict':
        records[0][7][0][12] = 'abra_t2v_8s'
    report, owned = entry.differential(records)
    assert report['verdict'] == verdict
    assert report['matcher_would_accept'] == (case == 'unique')
    assert (owned is not None) == (case == 'unique')
    assert len(report['every_new_record_examined']) == len(report['exact_delta_ids'])
    if case == 'unique':
        candidate = report['every_new_record_examined'][0]
        assert all(candidate[k] for k in ('exact_project','exact_reference','exact_model','exact_primary_marker','new_vs_baseline'))


def test_readonly_session_rejects_generation_upload_captcha(entry):
    session = entry.ReadOnlySession(cookie_path=Path('unused'), project_id=entry.PROJECT_ID)
    for rpc in ('MZZa6b','maseQ','unknown'):
        with pytest.raises(OwnerAmbiguityGate):
            session._rpc_body(rpc,'never_sent')
    with pytest.raises(OwnerAmbiguityGate):
        session.captcha('VIDEO_GENERATION')
    assert session.rpc_call_counts == {}


def test_no_output_reconciliation_does_not_mutate_any_ledger_row(entry, tmp_path, monkeypatch):
    from test_flow_r2v_compact import prepared
    from film_pipeline.store import SQLiteStore
    database, _, _, job = prepared(tmp_path)
    store = SQLiteStore(database)
    store.reserve_dispatch(job.provider_job_id)
    store.record_dispatch_fact(job.provider_job_id,'AMBIGUOUS_EVIDENCE',{'diagnostic':'temporary_ambiguity_fixture'})
    before = database.read_bytes()
    monkeypatch.setattr(entry,'DATABASE',database)
    monkeypatch.setattr(entry,'OUTPUT',tmp_path/'read_only_result')
    monkeypatch.setattr(entry,'frozen_job',lambda store: store.read_provider_job(job.provider_job_id))
    monkeypatch.setattr(entry,'story_controls',lambda: {'actual_successful_controls':[]})
    session = Mock(catalog_fingerprint=entry.contract.QUALIFIED_BASELINE_FINGERPRINT)
    session.catalog.return_value = []
    class OfflineSession:
        rpc_call_counts = {'Zzl0ze':1}
        def __getattr__(self, name):
            return getattr(session, name)
        def __enter__(self):
            return session
        def __exit__(self,*args):
            pass
    monkeypatch.setattr(entry,'ReadOnlySession',lambda **kwargs: OfflineSession())
    monkeypatch.setattr(entry.contract,'sanitize_session',lambda *args: {'metadata_coherent':True})
    report = entry.run(Path('unused'))
    assert report['verdict']=='NO_DURABLE_OUTPUT_OBSERVED'
    assert report['gate']=='OWNER_AMBIGUITY_GATE'
    assert database.read_bytes()==before
    assert report['database_before_sha256']==report['database_final_sha256']
    assert report['ambiguity_cleared'] is False
    session.media.assert_not_called()
    session.submit_once.assert_not_called()
    session.upload_reference.assert_not_called()


@pytest.mark.parametrize('outcome', ['acquired', 'download_failed'])
def test_existing_unique_output_recovers_without_submit_or_ambiguity_clear(entry, tmp_path, monkeypatch, outcome):
    import sqlite3
    import subprocess
    from test_flow_r2v_compact import prepared
    from film_pipeline.store import SQLiteStore
    database, _, _, job = prepared(tmp_path)
    store = SQLiteStore(database)
    store.reserve_dispatch(job.provider_job_id)
    request={'request_hash':job.correlation_evidence['rpc_request_hash'],'body_sha256':'3'*64,'contract':entry.RPC_CONTRACT}
    store.record_dispatch_fact(job.provider_job_id,'RPC_REQUEST_ARMED',request)
    store.record_dispatch_fact(job.provider_job_id,'GENERATE_REQUEST_OBSERVED',request)
    store.record_dispatch_fact(job.provider_job_id,'PROVIDER_RESPONSE_OBSERVED',{'request_hash':request['request_hash'],'status':200})
    store.record_dispatch_fact(job.provider_job_id,'AMBIGUOUS_EVIDENCE',{'diagnostic':'temporary_ambiguity_fixture'})
    ambiguity_before = [f for f in store.read_dispatch_facts(job.provider_job_id) if f['kind']=='AMBIGUOUS_EVIDENCE']
    for name,value in [('DATABASE',database),('OUTPUT',tmp_path/'recovered'),('JOB',job.provider_job_id),
        ('ATTEMPT',job.generation_attempt_id),('MARKER','[FILM-'+job.provider_job_id+']'),('BASELINE',[])]:
        monkeypatch.setattr(entry,name,value)
    monkeypatch.setattr(entry,'frozen_job',lambda store: store.read_provider_job(job.provider_job_id))
    monkeypatch.setattr(entry,'story_controls',lambda: {'actual_successful_controls':[]})
    session = Mock(catalog_fingerprint=entry.contract.QUALIFIED_BASELINE_FINGERPRINT)
    session.catalog.return_value = [row(prompt=job.correlation_evidence['prompt'])]
    if outcome=='acquired':
        video=tmp_path/'exact_bytes.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=24:duration=8',
            '-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
        session.media.return_value=video.read_bytes()
    else:
        session.media.side_effect=ValueError('offline_acquisition_failure')
    class OfflineSession:
        rpc_call_counts={'Zzl0ze':1}
        def __getattr__(self,name):
            return getattr(session,name)
        def __enter__(self):
            return session
        def __exit__(self,*args):
            pass
    monkeypatch.setattr(entry,'ReadOnlySession',lambda **kwargs:OfflineSession())
    session.project_id=entry.PROJECT_ID
    monkeypatch.setattr(entry.contract,'sanitize_session',lambda *args:{'metadata_coherent':True})
    report=entry.run(Path('unused'))
    assert report['verdict']=='UNIQUE_EXISTING_OUTPUT_RECOVERED'
    assert report['matcher_would_accept'] and report['attributed_output_id']==OUTPUT
    assert report['ambiguity_cleared'] is False
    assert store.read_provider_job(job.provider_job_id).dispatch_count==1
    assert store.read_output_bindings(job.provider_job_id)[0]['output_id']==OUTPUT
    assert [f for f in store.read_dispatch_facts(job.provider_job_id) if f['kind']=='AMBIGUOUS_EVIDENCE']==ambiguity_before
    if outcome=='acquired':
        assert report['gate']=='OWNER_CHARACTER_CONTINUITY_REVIEW_GATE'
        assert report['asset']['sha256']==entry.file_sha256(video)
        assert all(r['verdict']=='pass' for r in report['technical_qc'])
        with sqlite3.connect(database) as c:
            assert c.execute('SELECT COUNT(*) FROM selected_takes').fetchone()[0]==0
    else:
        assert report['gate']=='OWNER_AMBIGUITY_GATE' and report['asset'] is None
    session.submit_once.assert_not_called()
    session.upload_reference.assert_not_called()
    import asyncio
    from film_pipeline.live_runtime import LiveRuntimeExecutor
    with pytest.raises(RuntimeError,match='AMBIGUOUS_EVIDENCE_REQUIRES_RECONCILIATION'):
        asyncio.run(LiveRuntimeExecutor(store,Mock()).download_assets(job.provider_job_id,tmp_path/'ordinary'))
    session.media.reset_mock()
    with pytest.raises(OwnerAmbiguityGate,match='durable reconciliation authorization'):
        entry.acquire_reconciled(store,session,OUTPUT,'0'*64)
    session.media.assert_not_called()
