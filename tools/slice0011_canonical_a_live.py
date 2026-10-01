"""One Owner-authorized native UI Shot A. No upload, retry or Shot B path."""
import json
import subprocess
import time
from contextlib import closing
from pathlib import Path

from film_pipeline.core import sha256
from film_pipeline.live_runtime import utc_now
from film_pipeline.store import SQLiteStore
from film_pipeline.providers import flow_rpc_contract as c
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_binding import attest_existing_reference, verify_attestation, write_immutable
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_canonical_ui import prepare_inputs, verify_chip, OneGenerateGuard
from film_pipeline.slice0011 import ROOT, PROJECT_ID, ACCOUNT_ID, REFERENCE_ASSET_ID, _acquire_bound
from film_pipeline.slice0011_canonical_reproof import (REFERENCE_MEDIA_ID, MODEL, TABLE,
    AUTHORITY_ID, freeze_reproof, reserve_reproof_dispatch)
from slice0011_successor_live import build_review

DATABASE = ROOT / 'projects/character_continuity/slice0011/runtime.sqlite'
OUTPUT = ROOT / 'projects/character_continuity/canonical_a_reproof_20261001'
PROFILE = Path('D:/Video/AutoVideoPipeline/scratch/google_flow_slice0011_manual')


class NativeSession(FlowReferenceRpcSession):
    def _rpc_body(self, rpc_id, body, **kwargs):
        if rpc_id not in {c.RPC_CATALOG, c.RPC_MEDIA}:
            raise OwnerAmbiguityGate('DIRECT_PROVIDER_MUTATION_FORBIDDEN')
        return super()._rpc_body(rpc_id, body, **kwargs)


def run():
    result_path = OUTPUT / 'live_result.json'
    if result_path.exists():
        raise OwnerAmbiguityGate('DURABLE_STOP_EXISTS_NO_REDISPATCH')
    store = SQLiteStore(DATABASE)
    with closing(store._connect()) as connection:
        if connection.execute('SELECT 1 FROM sqlite_master WHERE name=?', (TABLE,)).fetchone():
            if connection.execute(f'SELECT 1 FROM {TABLE}').fetchone():
                raise OwnerAmbiguityGate('EXISTING_REPROOF_REQUIRES_READ_ONLY_RECONCILIATION')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    # Tested code must be committed. Unrelated untracked owner work is preserved.
    source_scope = ['src', 'tests', 'tools/slice0011_canonical_a_live.py', 'tools/slice0011_successor_live.py']
    if (subprocess.check_output(['git', 'diff', 'HEAD', '--name-only', '--', *source_scope], cwd=ROOT, text=True).strip()
            or subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *source_scope], cwd=ROOT, text=True).strip()):
        raise OwnerAmbiguityGate('TESTED_SOURCE_REVISION_NOT_CLEAN')
    report = {'authority_id': AUTHORITY_ID, 'source_revision': revision,
        'state': 'OWNER_AMBIGUITY_GATE', 'generate_clicks': 0, 'provider_generate_requests': 0,
        'retries': 0, 'uploads': 0, 'shot_b_generates': 0, 'started_at': utc_now()}
    guard = None
    job = None
    try:
        with NativeSession(profile_path=PROFILE, project_id=PROJECT_ID, native_ui=True) as session:
            # Block mutations before the reservation exists, including uploads.
            def preflight_guard(route):
                r = route.request
                body = r.post_data or ''
                if any(token in r.url or token in body for token in ('MZZa6b', 'maseQ')):
                    route.abort()
                    raise OwnerAmbiguityGate('PREFLIGHT_MUTATION_BLOCKED')
                route.continue_()
            pattern = '**/batchexecute?*'
            session.page.context.route(pattern, preflight_guard)
            reference = store.read_reference_asset(REFERENCE_ASSET_ID)
            attestation = attest_existing_reference(store, reference, session, account_id=ACCOUNT_ID,
                media_id=REFERENCE_MEDIA_ID, evidence_dir=OUTPUT / 'reference')
            report['reference_attestation'] = attestation
            job = freeze_reproof(DATABASE, session, attestation, OUTPUT / 'reference')
            report['job_id'] = job.provider_job_id
            report['attempt_id'] = job.generation_attempt_id
            records = session.catalog(contract_version=c.CONTRACT_VERSION_2026_10_01)
            if sorted(r[0] for r in records) != job.pre_dispatch_snapshot['catalog_ids']:
                raise OwnerAmbiguityGate('BASELINE_CHANGED_BEFORE_UI_PREPARATION')
            ui = prepare_inputs(session, records, media_id=REFERENCE_MEDIA_ID,
                prompt=job.correlation_evidence['prompt'])
            report['ui_preflight'] = ui
            write_immutable(OUTPUT / 'pre_generate_proof.json', report)
            verify_attestation(store, reference, attestation, media_id=REFERENCE_MEDIA_ID,
                project_id=PROJECT_ID, evidence_dir=OUTPUT / 'reference')
            reserved = reserve_reproof_dispatch(store, job.provider_job_id, attestation, OUTPUT / 'reference')
            guard = OneGenerateGuard(store, reserved, PROJECT_ID, REFERENCE_MEDIA_ID)
            session.page.context.unroute(pattern, preflight_guard)
            session.page.context.route(pattern, guard.route)
            verify_chip(session.page, REFERENCE_MEDIA_ID)
            if session.page.locator('div.ProseMirror[contenteditable="true"]').inner_text() != job.correlation_evidence['prompt']:
                raise OwnerAmbiguityGate('PROMPT_CHANGED_AT_MUTATION_BOUNDARY')
            store.record_dispatch_fact(job.provider_job_id, 'PROMPT_VERIFIED', {'prompt_sha256': ui['prompt_sha256']})
            store.record_dispatch_fact(job.provider_job_id, 'CLICK_ARMED', {})
            guard.armed = True
            report['generate_clicks'] = 1
            session.page.locator('button.generate-icon-button').click(timeout=15000)
            print('ONE_NATIVE_GENERATE_CLICK_ISSUED', flush=True)
            deadline = time.monotonic() + 240
            row = None
            while time.monotonic() < deadline:
                session.page.wait_for_timeout(15000)
                if guard.error:
                    raise OwnerAmbiguityGate(guard.error)
                if guard.sent != 1:
                    if guard.seen or time.monotonic() > deadline - 195:
                        raise OwnerAmbiguityGate('EXACT_NATIVE_REQUEST_NOT_OBSERVED')
                    continue
                records = session.catalog(contract_version=c.CONTRACT_VERSION_2026_10_01)
                row = c.match_r2v_output_v2026_10_01(records, PROJECT_ID, REFERENCE_MEDIA_ID,
                    'story-auto-reference.png', job.provider_job_id,
                    baseline_ids=job.pre_dispatch_snapshot['catalog_ids'], model=MODEL)
                print('BACKEND_RECONCILIATION_' + ('BOUND' if row else 'PENDING'), flush=True)
                if row is not None:
                    break
            if row is None or guard.sent != 1 or guard.error:
                raise OwnerAmbiguityGate('BACKEND_IDENTITY_NOT_PROVEN')
            output_id = row[0]
            ast = row[5][6][2][0][2][0]
            text = ast[0][0] if len(ast) == 1 else ast[1][0].strip()
            if text != job.correlation_evidence['prompt']:
                raise OwnerAmbiguityGate('BACKEND_EXACT_PROMPT_MISMATCH')
            report['backend_lineage'] = {'output_id': output_id, 'project_id': row[1],
                'reference_ids': [r[2] for r in row[5][6][1][1]], 'model': MODEL,
                'prompt_sha256': sha256(text), 'baseline_absent': True}
            request = next(f['data'] for f in store.read_dispatch_facts(job.provider_job_id) if f['kind'] == 'GENERATE_REQUEST_OBSERVED')
            store.record_dispatch_fact(job.provider_job_id, 'PROVIDER_ACCEPTANCE_OBSERVED',
                {'request_hash': request['request_hash'], 'provider_reference': REFERENCE_MEDIA_ID, 'contract': request['contract']})
            store.record_dispatch_fact(job.provider_job_id, 'REMOTE_IDENTITY_OBSERVED',
                {'output_id': output_id, 'method': 'backend_exact_marker_reference_model'})
            store.bind_output(job.provider_job_id, output_id)
            bound = reserved.model_copy(update={'submission_state': 'SUBMITTED', 'status': 'SUCCEEDED',
                'external_job_id': output_id, 'submitted_at': utc_now(), 'last_checked_at': utc_now()})
            store.save_provider_job(bound)
            acquired = session.bound_media(output_id, 'video')
            report['media_readback'] = acquired.evidence
            write_immutable(OUTPUT / 'backend_identity.json', {
                'backend_lineage': report['backend_lineage'], 'readback': acquired.evidence})
        # Close the synchronous browser before the acquisition executor starts
        # its asynchronous loop. It receives only the already-bound exact bytes.
        class ExactDownloadedMedia:
            def media(self, requested_id, kind):
                if requested_id != output_id or kind != 'video':
                    raise OwnerAmbiguityGate('CACHED_OUTPUT_IDENTITY_MISMATCH')
                return acquired.data
        asset = _acquire_bound(DATABASE, ExactDownloadedMedia(), bound, OUTPUT / 'acquisition')
        report['asset'] = asset.model_dump(mode='json')
        report['review'] = build_review(DATABASE, asset, OUTPUT)
        report['state'] = 'OWNER_CHARACTER_CONTINUITY_REVIEW_GATE'
    except Exception as exc:
        report['diagnostic_type'] = type(exc).__name__
        # Gate codes are authored locally. Never persist arbitrary browser errors.
        if isinstance(exc, OwnerAmbiguityGate): report['diagnostic'] = str(exc)
        if job is not None and store.read_provider_job(job.provider_job_id).dispatch_count:
            store.record_dispatch_fact(job.provider_job_id, 'AMBIGUOUS_EVIDENCE', {'diagnostic': 'canonical_reproof_owner_gate'})
    finally:
        if guard:
            report['provider_generate_requests'] = guard.sent
            report['observed_generate_requests'] = guard.seen
        report['finished_at'] = utc_now()
        write_immutable(result_path, report)
    print(json.dumps({'state': report['state'], 'generate_clicks': report['generate_clicks'],
        'provider_generate_requests': report['provider_generate_requests'], 'result': str(result_path)}), flush=True)
    return report


if __name__ == '__main__':
    run()
