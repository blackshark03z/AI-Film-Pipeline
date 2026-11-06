import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from film_pipeline.core import sha256, canonical_json
from film_pipeline.dispatch_evidence import EvidenceSink
from film_pipeline.live_runtime import LiveRuntimeExecutor
from film_pipeline.store import SQLiteStore
from film_pipeline.providers.flow_dispatch_network import generate_request_metadata
from film_pipeline.providers.flow_network import FlowNetworkTransport
from film_pipeline.providers.flow_veo import FlowConfig
from film_pipeline.canary import run_canary
from test_live_runtime import FakeTransport, make_executor


class Crash(BaseException):
    """Models process loss, bypassing normal transport exception handling."""


REQUEST = {'request_hash': 'a' * 64, 'body_sha256': 'b' * 64, 'contract': 'fixture-generate-v1'}


class CrashingTransport(FakeTransport):
    def __init__(self, point):
        super().__init__(state='RUNNING')
        self.point = point

    def set_evidence_sink(self, sink, job):
        self.sink, self.job = sink, job

    async def submit(self, job, prompt):
        self.submits += 1
        def stop(point):
            if self.point == point: raise Crash(point)
        stop('F1')
        self.sink.record('PROMPT_VERIFIED', {'prompt_sha256': sha256(prompt)})
        stop('F2')
        self.sink.record('CLICK_ARMED')
        self.sink.record('TRUSTED_CLICK_OBSERVED')
        stop('F3')
        self.sink.record('GENERATE_REQUEST_OBSERVED', REQUEST)
        stop('F4')
        self.sink.record('PROVIDER_RESPONSE_OBSERVED', {'request_hash': REQUEST['request_hash'], 'status': 200})
        # Positive acceptance here is an explicitly qualified FAKE contract;
        # production Flow has no qualified acceptance decoder.
        self.sink.record('PROVIDER_ACCEPTANCE_OBSERVED', {'request_hash': REQUEST['request_hash'],
            'provider_reference': 'fixture-native-reference', 'contract': 'fixture-acceptance-v1'})
        stop('F5')
        self.sink.record('REMOTE_IDENTITY_OBSERVED', {'output_id': 'remote-output-1', 'method': 'fixture_exact_attribution'})
        stop('F6')
        self.sink.store.bind_output(job.provider_job_id, 'remote-output-1')
        stop('F7')
        return {'external_job_id': None}


def test_F5_provider_accepts_before_local_receipt_is_lost(tmp_path):
    class LostAcceptance(CrashingTransport):
        async def submit(self, job, prompt):
            self.submits += 1
            self.sink.record('GENERATE_REQUEST_OBSERVED', REQUEST)
            self.sink.record('PROVIDER_RESPONSE_OBSERVED',
                             {'request_hash': REQUEST['request_hash'], 'status': 200})
            self.provider_accepted = True  # Fake external fact never written locally.
            raise Crash('F5_BEFORE_DURABLE_ACCEPTANCE')

    transport = LostAcceptance('F5')
    executor, store, _, job = make_executor(tmp_path, transport)
    with pytest.raises(Crash):
        asyncio.run(executor.submit_once(job.provider_job_id))
    restarted = LiveRuntimeExecutor(SQLiteStore(store.path), FakeTransport(state='RUNNING'))
    assert transport.provider_accepted
    assert restarted.recovery_decision(job.provider_job_id).classification == 'INCONCLUSIVE'
    with pytest.raises(RuntimeError, match='budget already consumed'):
        asyncio.run(restarted.submit_once(job.provider_job_id))
    assert restarted.transport.submits == 0


@pytest.mark.parametrize('point', ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7'])
def test_crash_windows_preserve_immediate_facts_and_never_resubmit(tmp_path, point):
    transport = CrashingTransport(point)
    executor, store, attempt, job = make_executor(tmp_path, transport)
    with pytest.raises(Crash):
        asyncio.run(executor.submit_once(job.provider_job_id))
    fresh = SQLiteStore(store.path)
    restarted_transport = FakeTransport(state='RUNNING')
    restarted = LiveRuntimeExecutor(fresh, restarted_transport)
    persisted = fresh.read_provider_job(job.provider_job_id)
    assert persisted.dispatch_count == 1
    facts = fresh.read_dispatch_facts(job.provider_job_id)
    assert facts[0]['kind'] == 'RESERVED'
    decision = restarted.recovery_decision(job.provider_job_id)
    assert not decision.may_submit
    expected = {'F5': 'DISPATCH_CONFIRMED', 'F6': 'OUTPUT_OBSERVED', 'F7': 'OUTPUT_BOUND_UNOBSERVED'}.get(point, 'INCONCLUSIVE')
    assert decision.classification == expected
    with pytest.raises(RuntimeError, match='budget already consumed'):
        asyncio.run(restarted.submit_once(job.provider_job_id))
    reconciled = asyncio.run(restarted.reconcile(job.provider_job_id))
    assert restarted_transport.submits == 0
    if point in {'F6', 'F7'}:
        assert reconciled.status == 'SUCCEEDED'
        assert fresh.read_output_bindings(job.provider_job_id)[0]['attempt_id'] == attempt.generation_attempt_id
    if point in {'F5', 'F6', 'F7'}:
        assert reconciled.submission_state == 'SUBMITTED'


def test_F0_requires_fresh_authority_and_F1_real_process_exit_is_durable(tmp_path):
    executor, store, _, job = make_executor(tmp_path, FakeTransport())
    decision = executor.recovery_decision(job.provider_job_id)
    assert decision.classification == 'NOT_RESERVED' and not decision.may_submit
    program = "from film_pipeline.store import SQLiteStore;import os,sys;SQLiteStore(sys.argv[1]).reserve_dispatch(sys.argv[2]);os._exit(72)"
    # the child process does not inherit pytest's `pythonpath`; point it at the package this test imported
    src = str(Path(sys.modules['film_pipeline'].__file__).resolve().parent.parent)
    env = {**os.environ, 'PYTHONPATH': src + os.pathsep + os.environ.get('PYTHONPATH', '')}
    result = subprocess.run([sys.executable, '-c', program, str(store.path), job.provider_job_id], capture_output=True, env=env)
    assert result.returncode == 72
    fresh = SQLiteStore(store.path)
    assert fresh.read_provider_job(job.provider_job_id).dispatch_count == 1
    assert fresh.read_dispatch_facts(job.provider_job_id)[0]['kind'] == 'RESERVED'


def test_journal_highwater_never_regresses_for_late_callback_and_rows_are_immutable(tmp_path):
    executor, store, _, job = make_executor(tmp_path, FakeTransport())
    store.reserve_dispatch(job.provider_job_id)
    sink = EvidenceSink(store, job.provider_job_id)
    sink.record('GENERATE_REQUEST_OBSERVED', REQUEST)
    sink.record('PROVIDER_RESPONSE_OBSERVED', {'request_hash': REQUEST['request_hash'], 'status': 200})
    strength = executor.recovery_decision(job.provider_job_id).strength
    sink.record('TRUSTED_CLICK_OBSERVED')  # Legitimate late weaker callback.
    sink.record('TRUSTED_CLICK_OBSERVED')  # Idempotent identical fact.
    assert executor.recovery_decision(job.provider_job_id).strength == strength
    assert len(store.read_dispatch_facts(job.provider_job_id)) == 4
    assert executor.recovery_decision(job.provider_job_id).classification == 'INCONCLUSIVE'
    c = store._connect()
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        c.execute("DELETE FROM dispatch_journal WHERE job_id=?", (job.provider_job_id,))
    c.close()


def test_frozen_intent_and_journal_tamper_fail_closed(tmp_path):
    _, store, _, job = make_executor(tmp_path, FakeTransport())
    store.reserve_dispatch(job.provider_job_id)
    reserved = store.read_provider_job(job.provider_job_id)
    with pytest.raises(ValueError, match='FROZEN'):
        store.save_provider_job(reserved.model_copy(update={'project_binding_id': 'other'}))
    c = store._connect()
    payload = reserved.model_dump(mode='json')
    payload['correlation_evidence']['prompt'] = 'tampered'
    c.execute('UPDATE provider_jobs SET payload=? WHERE id=?', (canonical_json(payload), job.provider_job_id)); c.commit(); c.close()
    with pytest.raises(ValueError, match='INTEGRITY'):
        store.read_provider_job(job.provider_job_id)


def test_wrong_request_response_and_secret_keys_are_rejected(tmp_path):
    _, store, _, job = make_executor(tmp_path, FakeTransport())
    store.reserve_dispatch(job.provider_job_id)
    sink = EvidenceSink(store, job.provider_job_id)
    with pytest.raises(ValueError, match='REQUEST_BINDING'):
        sink.record('PROVIDER_RESPONSE_OBSERVED', {'request_hash': 'c' * 64, 'status': 200})
    with pytest.raises(ValueError, match='INVALID_DISPATCH_FACT'):
        sink.record('CLICK_ARMED', {'cookie': 'fake-secret-marker'})
    with pytest.raises(ValueError, match='PROMPT_HASH'):
        sink.record('PROMPT_VERIFIED', {'prompt_sha256': 'f' * 64})
    assert 'fake-secret-marker' not in json.dumps(store.read_dispatch_facts(job.provider_job_id))


def request_body(project='unit-project', prompt='exact prompt', rpc='MZZa6b'):
    return urlencode({'f.req': json.dumps([[[rpc, json.dumps([[project, prompt]]), None, 'generic']]]),
                      'at': 'fake-auth-marker'})


@pytest.mark.parametrize('method,url,body,matched', [
    ('POST', 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?private=fake', request_body(), True),
    ('GET', 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute', request_body(), False),
    ('POST', 'https://evil.example/_/AiSandboxAngularFrontend/data/batchexecute', request_body(), False),
    ('POST', 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute', request_body(project='other'), False),
    ('POST', 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute', request_body(prompt='exact prompt extra'), False),
    ('POST', 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute', request_body(rpc='unknown'), False),
])
def test_passive_request_classifier_exact_scope_and_no_secrets(method, url, body, matched):
    metadata = generate_request_metadata(method, url, body, 'unit-project', 'exact prompt')
    assert bool(metadata) == matched
    assert 'fake-auth-marker' not in json.dumps(metadata)
    assert 'private' not in json.dumps(metadata)


def test_http200_is_only_response_evidence_not_acceptance(tmp_path):
    _, store, _, job = make_executor(tmp_path, FakeTransport())
    store.reserve_dispatch(job.provider_job_id)
    transport = FlowNetworkTransport(FlowConfig())
    transport.set_evidence_sink(EvidenceSink(store, job.provider_job_id), job)
    request = SimpleNamespace(resource_type='xhr')
    transport._requests = {request.__class__: REQUEST['request_hash']}
    # Hashable identity stands for the same browser request object.
    request_object = object()
    transport._requests = {request_object: REQUEST['request_hash']}
    store.record_dispatch_fact(job.provider_job_id, 'GENERATE_REQUEST_OBSERVED', REQUEST)
    class Response:
        request = SimpleNamespace(resource_type='xhr')
        url = 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute'
        status = 200
        async def text(self): return 'unknown HTTP200 body'
    response = Response()
    # Provide resource_type on a stable hashable request object.
    class Request: resource_type = 'xhr'
    response.request = Request()
    transport._requests = {response.request: REQUEST['request_hash']}
    transport.decoder = SimpleNamespace(observe_body=lambda body: 0)
    transport._observer_failed = False
    asyncio.run(transport._observe(response))
    kinds = {f['kind'] for f in store.read_dispatch_facts(job.provider_job_id)}
    assert 'PROVIDER_RESPONSE_OBSERVED' in kinds
    assert 'PROVIDER_ACCEPTANCE_OBSERVED' not in kinds


def prepare_bound(tmp_path):
    executor, store, attempt, job = make_executor(tmp_path, FakeTransport())
    asyncio.run(executor.submit_once(job.provider_job_id))
    asyncio.run(executor.reconcile(job.provider_job_id))
    return executor, store, attempt, job


def test_F8_partial_download_recovers_exact_output_without_generate(tmp_path):
    executor, store, _, job = prepare_bound(tmp_path)
    async def partial(job, output, destination):
        destination.write_bytes(b'partial video')
        raise Crash('F8')
    executor.transport.fetch = partial
    with pytest.raises(Crash):
        asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / 'outputs'))
    fresh_transport = FakeTransport()
    fresh = LiveRuntimeExecutor(SQLiteStore(store.path), fresh_transport)
    assets = asyncio.run(fresh.download_assets(job.provider_job_id, tmp_path / 'outputs'))
    assert len(assets) == 1 and fresh_transport.submits == 0


class NoExternalTransport:
    async def submit(self, *args): raise AssertionError('no Generate')
    async def poll(self, *args): raise AssertionError('no provider query')
    async def fetch(self, *args): raise AssertionError('no second download')


@pytest.mark.parametrize('point', ['before_promotion', 'before_asset'])
def test_F9_receipt_and_immutable_file_recover_asset_without_network(tmp_path, monkeypatch, point):
    executor, store, attempt, job = prepare_bound(tmp_path)
    if point == 'before_asset':
        def crash(asset): raise Crash('F9')
        monkeypatch.setattr(store, 'save_asset', crash)
    else:
        from film_pipeline import live_runtime
        def crash(*args): raise Crash('F9')
        monkeypatch.setattr(live_runtime.os, 'link', crash)
    with pytest.raises(Crash):
        asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / 'outputs'))
    monkeypatch.undo()
    fresh = LiveRuntimeExecutor(SQLiteStore(store.path), NoExternalTransport())
    assert fresh.recovery_decision(job.provider_job_id).action == 'RECOVER_ASSET'
    assets = asyncio.run(fresh.download_assets(job.provider_job_id, tmp_path / 'outputs'))
    assert SQLiteStore(store.path).read_runtime_lineage(attempt.generation_attempt_id, job.provider_job_id)[5] == assets
    assert asyncio.run(fresh.download_assets(job.provider_job_id, tmp_path / 'outputs')) == assets


def test_existing_file_without_receipt_is_not_adopted(tmp_path):
    executor, _, _, job = prepare_bound(tmp_path)
    output = tmp_path / 'outputs'; output.mkdir()
    (output / (sha256('remote-output-1')[:24] + '.mp4')).write_bytes(b'unknown file')
    executor.transport = NoExternalTransport()
    with pytest.raises(ValueError, match='WITHOUT_ACQUISITION_RECEIPT'):
        asyncio.run(executor.download_assets(job.provider_job_id, output))


def test_changed_validated_bytes_are_not_recovered(tmp_path, monkeypatch):
    executor, store, _, job = prepare_bound(tmp_path)
    def crash(asset): raise Crash('F9')
    monkeypatch.setattr(store, 'save_asset', crash)
    with pytest.raises(Crash):
        asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / 'outputs'))
    path = next((tmp_path / 'outputs').glob('*.mp4'))
    path.write_bytes(b'changed bytes')
    fresh = LiveRuntimeExecutor(SQLiteStore(store.path), NoExternalTransport())
    with pytest.raises(ValueError):
        asyncio.run(fresh.download_assets(job.provider_job_id, tmp_path / 'outputs'))


def test_legacy_consumed_history_is_byte_identical_after_refused_recovery(tmp_path):
    _, store, _, job = make_executor(tmp_path, FakeTransport())
    c = store._connect()
    payload = job.model_dump(mode='json');payload.pop('dispatch_protocol')
    payload.update(dispatch_count=1, status='INCONCLUSIVE', submission_state='SUBMISSION_RESERVED')
    c.execute('UPDATE provider_jobs SET dispatch_count=1,payload=? WHERE id=?', (canonical_json(payload), job.provider_job_id));c.commit();c.close()
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    fresh = LiveRuntimeExecutor(SQLiteStore(store.path), NoExternalTransport())
    assert fresh.recovery_decision(job.provider_job_id).classification == 'LEGACY_HISTORY_READ_ONLY'
    with pytest.raises(RuntimeError, match='LEGACY_HISTORY_READ_ONLY'):
        store.initialize()
    with pytest.raises(RuntimeError, match='LEGACY_HISTORY_READ_ONLY'):
        asyncio.run(fresh.reconcile(job.provider_job_id))
    assert hashlib.sha256(store.path.read_bytes()).hexdigest() == before


def test_canary_has_no_implicit_live_authorization_or_historical_db_reuse():
    result = asyncio.run(run_canary(FlowConfig()))
    assert result['diagnostic'] == 'FRESH_GENERATE_AUTHORIZATION_REQUIRED'
    with pytest.raises(ValueError, match='FRESH_AUTHORIZED_RUNTIME_PATH'):
        asyncio.run(run_canary(FlowConfig(), authorize_new_submit=True))


def test_one_output_identity_cannot_bind_to_another_attempt(tmp_path):
    _, store, attempt, job = prepare_bound(tmp_path)
    shot, plan, routing, _ = store.read_path(attempt.generation_attempt_id)
    other = attempt.model_copy(update={'generation_attempt_id': 'attempt_other'})
    store.save_path(shot, plan, routing, other)
    # Test fixture simulates an imported competing reserved attempt; the public
    # reservation API itself already forbids two reservations in one canary DB.
    competitor = job.model_copy(update={'provider_job_id': 'job_other', 'generation_attempt_id': other.generation_attempt_id})
    store.save_provider_job(competitor)
    c = store._connect()
    payload = competitor.model_copy(update={'dispatch_count': 1}).model_dump(mode='json')
    c.execute('UPDATE provider_jobs SET dispatch_count=1,payload=? WHERE id=?', (canonical_json(payload), competitor.provider_job_id))
    from film_pipeline.dispatch_evidence import append_fact, intent_hash
    append_fact(c, competitor.provider_job_id, 'RESERVED', {'intent_hash': intent_hash(competitor)})
    c.commit();c.close()
    store.record_dispatch_fact(competitor.provider_job_id, 'REMOTE_IDENTITY_OBSERVED', {'output_id': 'remote-output-1', 'method': 'fixture_exact_attribution'})
    with pytest.raises(ValueError, match='ALREADY_BOUND'):
        store.bind_output(competitor.provider_job_id, 'remote-output-1')


def test_output_tuple_cannot_bind_to_another_project(tmp_path):
    _, store, _, job = make_executor(tmp_path, FakeTransport())
    store.reserve_dispatch(job.provider_job_id)
    output = 'response-tuple:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee:11111111-2222-3333-4444-555555555555:99999999-8888-7777-6666-555555555555'
    store.record_dispatch_fact(job.provider_job_id, 'REMOTE_IDENTITY_OBSERVED', {'output_id': output, 'method': 'fixture_exact_attribution'})
    with pytest.raises(ValueError, match='PROJECT_MISMATCH'):
        store.bind_output(job.provider_job_id, output)


def test_journal_corruption_is_detected_on_fresh_read(tmp_path):
    _, store, _, job = make_executor(tmp_path, FakeTransport())
    store.reserve_dispatch(job.provider_job_id)
    c = store._connect()
    c.execute('DROP TRIGGER dispatch_journal_update_immutable')
    c.execute("UPDATE dispatch_journal SET digest=? WHERE job_id=?", ('f' * 64, job.provider_job_id));c.commit();c.close()
    with pytest.raises(ValueError, match='INTEGRITY'):
        SQLiteStore(store.path).read_dispatch_facts(job.provider_job_id)


@pytest.mark.parametrize('failure', [None, 'CLICK_ARMED', 'TRUSTED_CLICK_OBSERVED', 'double_request',
                                     'never_enable', 'mutate_before_enable', 'mutate_on_pointerdown',
                                     'replace_guarded_button'])
def test_offline_browser_write_through_receipts_and_failure_boundaries(tmp_path, monkeypatch, failure):
    from patchright.async_api import async_playwright
    project = '11111111-2222-3333-4444-555555555555'
    executor, store, _, job = make_executor(tmp_path, FakeTransport(), project_binding_id=sha256(project))
    original = store.record_dispatch_fact
    if failure in {'CLICK_ARMED', 'TRUSTED_CLICK_OBSERVED'}:
        def failing(job_id, kind, data):
            if kind == failure: raise OSError('simulated durable write failure')
            return original(job_id, kind, data)
        monkeypatch.setattr(store, 'record_dispatch_fact', failing)
    async def run():
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                html = '<div class="ProseMirror" contenteditable="true" style="white-space:pre-wrap"></div><button class="generate-icon-button" disabled>Generate fixture</button>'
                async def route(request):
                    # ALL traffic is intercepted: this test cannot reach Flow.
                    if '/project/' in request.request.url:
                        await request.fulfill(content_type='text/html', body=html)
                    else:
                        await request.fulfill(content_type='application/json', body='{}')
                await page.route('**/*', route)
                transport = FlowNetworkTransport(FlowConfig())
                transport.page, transport.project_id = page, project
                transport._observe_page()
                await page.goto('https://flow.google.com/project/' + project)
                await page.evaluate("""([project,doubleRequest,neverEnable,mutateBeforeEnable,mutateOnPointerdown,expected])=>{
                  window.fixtureClicks=0;
                  const editor=document.querySelector('.ProseMirror');
                  const button=document.querySelector('button');
                  editor.addEventListener('input',()=>{
                    if(mutateBeforeEnable){
                      if(editor.innerText===expected&&!window.mutationScheduled){
                        window.mutationScheduled=true;
                        setTimeout(()=>{editor.innerText+=' altered';button.disabled=false},150);
                      }
                    }else if(!neverEnable)button.disabled=!editor.innerText.trim();
                  });
                  if(mutateOnPointerdown)button.addEventListener('pointerdown',()=>{editor.innerText+=' altered'},{once:true});
                  button.onclick=()=>{
                    window.fixtureClicks++;
                    const prompt=document.querySelector('.ProseMirror').innerText;
                    const payload=JSON.stringify([[["MZZa6b",JSON.stringify([[project,prompt]]),null,"generic"]]]);
                    const body=new URLSearchParams({'f.req':payload,'at':'fake-auth-marker'});
                    fetch('/_/AiSandboxAngularFrontend/data/batchexecute',{method:'POST',body});
                    if(doubleRequest)fetch('/_/AiSandboxAngularFrontend/data/batchexecute',{method:'POST',body});
                    document.querySelector('.ProseMirror').innerText='';
                  };
                }""", [project, failure == 'double_request', failure == 'never_enable',
                         failure == 'mutate_before_enable', failure == 'mutate_on_pointerdown',
                         job.correlation_evidence['prompt']])
                if failure == 'replace_guarded_button':
                    original_click = transport._click_pinned_generate
                    async def replace_then_click(element):
                        await page.evaluate("""()=>{
                          const button=document.querySelector('button');
                          const replacement=button.cloneNode(true);
                          replacement.onclick=()=>window.fixtureClicks++;
                          button.replaceWith(replacement);
                        }""")
                        await original_click(element)
                    transport._click_pinned_generate = replace_then_click
                executor.transport = transport
                if failure in {'CLICK_ARMED', 'TRUSTED_CLICK_OBSERVED', 'never_enable',
                               'mutate_before_enable', 'mutate_on_pointerdown', 'replace_guarded_button'}:
                    with pytest.raises(Exception):
                        await executor.submit_once(job.provider_job_id)
                else:
                    await executor.submit_once(job.provider_job_id)
                await page.wait_for_timeout(200)
                if transport._tasks:
                    await asyncio.gather(*list(transport._tasks))
                clicks = await page.evaluate('window.fixtureClicks')
                assert clicks == (0 if failure in {'CLICK_ARMED', 'never_enable',
                                                   'mutate_before_enable', 'mutate_on_pointerdown',
                                                   'replace_guarded_button'} else 1)
                facts = SQLiteStore(store.path).read_dispatch_facts(job.provider_job_id)
                kinds = {f['kind'] for f in facts}
                assert 'PROVIDER_ACCEPTANCE_OBSERVED' not in kinds
                if failure is None:
                    assert {'PROMPT_VERIFIED', 'CLICK_ARMED', 'TRUSTED_CLICK_OBSERVED',
                            'GENERATE_REQUEST_OBSERVED', 'PROVIDER_RESPONSE_OBSERVED'} <= kinds
                if failure == 'double_request':
                    assert 'AMBIGUOUS_EVIDENCE' in kinds
                if failure == 'never_enable':
                    assert 'PROMPT_VERIFIED' in kinds and 'CLICK_ARMED' not in kinds
                if failure == 'mutate_before_enable':
                    assert 'PROMPT_VERIFIED' in kinds and 'CLICK_ARMED' not in kinds
                if failure == 'mutate_on_pointerdown':
                    assert 'CLICK_ARMED' in kinds and 'TRUSTED_CLICK_OBSERVED' not in kinds
                if failure == 'replace_guarded_button':
                    assert 'CLICK_ARMED' in kinds and 'TRUSTED_CLICK_OBSERVED' not in kinds
                assert 'fake-auth-marker' not in json.dumps(facts)
                assert store.read_provider_job(job.provider_job_id).submitted_at is None
                with pytest.raises(RuntimeError, match='budget already consumed'):
                    await executor.submit_once(job.provider_job_id)
                assert await page.evaluate('window.fixtureClicks') == clicks
            finally:
                await browser.close()
    asyncio.run(run())
