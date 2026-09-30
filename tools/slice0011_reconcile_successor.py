"""Exact consumed successor reconciliation: no submit/upload/captcha or allocation."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

from film_pipeline.core import canonical_json, sha256
from film_pipeline.dispatch_evidence import intent_hash
from film_pipeline.live_runtime import Asset, file_sha256, inspect_video, utc_now
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from film_pipeline.slice0011 import (ROOT, PROJECT_ID, ACCOUNT_ID, REFERENCE_ASSET_ID,
    RPC_CONTRACT, _reference_binding, _ExactMediaTransport, _full_decode)
from film_pipeline.slice0011_successor import REFERENCE_MEDIA_ID, historical_snapshot, read_successor
from film_pipeline.store import SQLiteStore

JOB = 'job_4d11911518710248299682693a3fdb48ec1426ffc0a6ab6d45de615596060d40'
ATTEMPT = 'attempt_9723d6dd168ac7fe47baf03ad5fd33ef8f9e0c21cf6f8bcc83cfa002a46822aa'
MARKER = '[FILM-' + JOB + ']'
BASELINE = ['347f9951-5bbc-4910-b6fd-3a17c74e29d2', REFERENCE_MEDIA_ID,
    '78203d6c-16b9-4cae-a66c-a1f7de58275f', '86a88de1-62a6-4ad6-9df0-07c2a501f2d0']
DATABASE = ROOT / 'projects/character_continuity/slice0011/runtime.sqlite'
OUTPUT = DATABASE.parent / 'successor_reconciliation_v1'


class ReadOnlySession(FlowReferenceRpcSession):
    def _rpc_body(self, rpc_id, body, **options):
        if rpc_id not in {contract.RPC_CATALOG, contract.RPC_MEDIA}:
            raise OwnerAmbiguityGate('reconciliation forbids generation/upload/unrelated RPC')
        return super()._rpc_body(rpc_id, body, **options)

    def captcha(self, action):
        raise OwnerAmbiguityGate('reconciliation forbids generation captcha')


def frozen_job(store):
    job = read_successor(store)
    if (job is None or job.provider_job_id != JOB or job.generation_attempt_id != ATTEMPT
            or job.dispatch_count != 1 or job.pre_dispatch_snapshot['catalog_ids'] != BASELINE
            or job.correlation_evidence['correlation_marker'] != MARKER
            or job.correlation_evidence['rpc_request_hash'] != '0144fdec7c100466800650379420e9150e4e8b75ac4b80387174f0eed0a56ea4'
            or job.correlation_evidence['submission_prompt_hash'] != 'e3dd2ff58e391cb029765c3a8d1a1ec01551592daf0430a304e2ab1b5004d003'
            or intent_hash(job) != '360f5c7b945f21298b5afd5908175b70894e71b208b966c324d08c8a46622396'):
        raise OwnerAmbiguityGate('exact consumed frozen successor required')
    receipt = ReferenceUploadStore(store.path).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID,
        store.read_reference_asset(REFERENCE_ASSET_ID))
    if receipt is None or _reference_binding(receipt) != job.correlation_evidence['reference_binding']:
        raise OwnerAmbiguityGate('frozen exact reference receipt changed')
    return job


def inspect_record(row):
    """Qualified identity facts only; never persist the raw authenticated record."""
    result = {'output_identity': row[0], 'exact_project': row[1] == PROJECT_ID,
        'record_length': len(row), 'status': row[3] if re.fullmatch(r'[A-Z_]{1,20}', row[3]) else 'unqualified',
        'new_vs_baseline': row[0].lower() not in BASELINE}
    def slot(*indices):
        try:
            value = row
            for index in indices:
                value = value[index]
            return value
        except (IndexError, TypeError, KeyError):
            return None
    prompt = slot(5, 1)
    model = slot(5, 6, 1, 0, 0)
    references = slot(5, 6, 1, 1)
    valid_refs = (isinstance(references, list) and all(isinstance(r, list) and len(r) == 3
        and r[0] is None and r[1] == 4 and isinstance(r[2], str) and contract.UUID_RE.fullmatch(r[2]) for r in references))
    prompt_lineage = slot(5, 6, 2)
    redundant = row[7] if len(row) == 8 else None
    result.update(primary_prompt_present=isinstance(prompt, str),
        primary_prompt_sha256=sha256(prompt) if isinstance(prompt, str) else None,
        exact_primary_marker=isinstance(prompt, str) and prompt.count(MARKER) == 1 and prompt.count('[FILM-') == 1,
        exact_model=model == 'abra_r2v_8s', model='abra_r2v_8s' if model == 'abra_r2v_8s' else 'other_or_absent',
        reference_slot_well_formed=bool(valid_refs),
        reference_media_ids=[r[2] for r in references] if valid_refs else [],
        exact_reference=references == [[None, 4, REFERENCE_MEDIA_ID]],
        prompt_lineage_present=prompt_lineage is not None,
        prompt_lineage_marker_agrees=(slot(5, 6, 2, 0, 2, 0, 0, 0).count(MARKER) == 1
            if isinstance(slot(5, 6, 2, 0, 2, 0, 0, 0), str) else None),
        redundant_lineage_present=redundant is not None,
        redundant_model_agrees=slot(7, 0, 12) == 'abra_r2v_8s' if redundant is not None else None,
        redundant_identity_agrees=slot(7, 2) == [row[0]] if redundant is not None else None,
        redundant_marker_agrees=(slot(7, 0, 7).count(MARKER) == 1
            if isinstance(slot(7, 0, 7), str) else None))
    try:
        accepted = contract.match_r2v_output([row], PROJECT_ID, REFERENCE_MEDIA_ID, JOB, baseline_ids=BASELINE)
        result.update(matcher_would_accept=accepted is not None, matcher_reason='accepted' if accepted else 'no_exact_marker')
    except contract.ContractError as exc:
        result.update(matcher_would_accept=False, matcher_reason=exc.code)
    return result


def differential(records):
    contract._validate_catalog_rows(records, PROJECT_ID)
    ids = sorted(row[0].lower() for row in records)
    delta = sorted(set(ids) - set(BASELINE))
    candidates = [inspect_record(row) for row in records if row[0].lower() in delta]
    report = {'current_catalog_ids': ids, 'frozen_baseline_ids': BASELINE, 'exact_delta_ids': delta,
        'every_new_record_examined': candidates, 'all_record_identity_checks': [inspect_record(row) for row in records]}
    try:
        owned = contract.match_r2v_output(records, PROJECT_ID, REFERENCE_MEDIA_ID, JOB, baseline_ids=BASELINE)
    except contract.ContractError as exc:
        return {**report, 'verdict': 'CONFLICTING_OR_NONUNIQUE_OUTPUT', 'matcher_error': exc.code,
                'matcher_would_accept': False, 'attributed_output_id': None}, None
    return {**report, 'verdict': 'UNIQUE_EXISTING_OUTPUT_RECOVERED' if owned else 'NO_DURABLE_OUTPUT_OBSERVED',
            'matcher_would_accept': owned is not None, 'attributed_output_id': owned[0] if owned else None}, owned


def story_controls():
    """Actual sealed acquired Story Auto journals and hash-verified local MP4s."""
    root = Path(r'D:\Story Auto\evidence\flow-real-product-journey-20260921\projects\prj_flow_real_product\assets\opening\flow')
    controls = []
    for path in sorted(root.glob('*/flow_rpc_attempt.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        seal = hashlib.sha256(json.dumps({k:v for k,v in data.items() if k != 'seal'}, sort_keys=True,
            separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        diagnostic = data.get('submission_diagnostic', {})
        media = path.parent / 'output.mp4'
        if data.get('seal') != seal or data.get('state') != 'ACQUIRED' or not media.is_file():
            continue
        if file_sha256(media) != data.get('output_sha256'):
            continue
        counts = diagnostic.get('type_counts')
        expected = {'null','boolean','number','string','array','object'}
        if not isinstance(counts, dict) or set(counts) != expected or any(type(v) is not int for v in counts.values()):
            continue
        if diagnostic.get('classification') != 'PARSED_NOT_ACCEPTANCE_PROOF':
            continue
        controls.append({'journal': str(path), 'state': 'ACQUIRED', 'seal_verified': True,
            'output_file': str(media), 'output_sha256': data['output_sha256'], 'output_hash_verified': True,
            'parsed': True, 'type_counts': counts, 'truncated': diagnostic.get('truncated'),
            'response_bytes_len': None, 'response_shape_hash': None})
    return {'actual_successful_controls': controls, 'distinct_output_hashes': len({c['output_sha256'] for c in controls}),
        'successor': {'parsed': True, 'response_bytes_len': 228,
            'type_counts_normalized': {'null': 1, 'boolean': 0, 'number': 0, 'string': 0, 'array': 0, 'object': 0}},
        'material_type_structure_difference_observed': bool(controls) and all(c['type_counts'] != {
            'null': 1, 'boolean': 0, 'number': 0, 'string': 0, 'array': 0, 'object': 0} for c in controls),
        'limits': 'Successful journals store type counts but not response byte lengths/type-shape hashes. No raw responses reconstructed. Difference is advisory and proves no admission/rejection semantics for null-only acknowledgment.'}


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(canonical_json(value))


def acquire_reconciled(store, session, output_id, proof_hash):
    """One exact receipt path authorized by durable reconciliation, not a generic bypass."""
    proof = json.loads((OUTPUT / 'catalog_reconciliation.json').read_text(encoding='utf-8'))
    job = frozen_job(store)
    candidate = next((c for c in proof['every_new_record_examined'] if c['output_identity'] == output_id), None)
    if (sha256(proof) != proof_hash or proof.get('verdict') != 'UNIQUE_EXISTING_OUTPUT_RECOVERED'
            or proof.get('job') != JOB or proof.get('attempt') != ATTEMPT
            or proof.get('frozen_intent_hash') != intent_hash(job)
            or proof.get('attributed_output_id') != output_id or proof.get('matcher_would_accept') is not True
            or candidate is None or not all(candidate.get(k) is True for k in (
                'exact_project','exact_reference','exact_model','exact_primary_marker','new_vs_baseline','matcher_would_accept'))
            or proof.get('frozen_baseline_ids') != BASELINE or output_id.lower() in BASELINE
            or job.external_job_id != output_id or session.project_id != PROJECT_ID):
        raise OwnerAmbiguityGate('exact durable reconciliation authorization required for acquisition')
    bindings = store.read_output_bindings(JOB)
    if len(bindings) != 1 or bindings[0]['output_id'] != output_id:
        raise OwnerAmbiguityGate('exact reconciled binding required')
    directory = OUTPUT.absolute() / 'videos'
    directory.mkdir(exist_ok=True)
    final = directory / (sha256(output_id)[:24] + '.mp4')
    staging = final.with_name(final.stem + '.partial.mp4')
    if any(p.is_symlink() for p in (final, staging, *directory.parents)) or final.exists() or staging.exists():
        raise OwnerAmbiguityGate('reconciliation acquisition destination not fresh and owned')
    intent = {'binding_hash': bindings[0]['binding_hash'], 'final_path': str(final),
        'staging_path': str(staging), 'rendition': 'official-720p'}
    store.save_acquisition_record(JOB, output_id, intent)
    # Reuse the strict transport's exact media identity, MP4/8s/16:9 and full EOF
    # validation. The ordinary runtime ambiguity guard remains unchanged.
    fetched = asyncio.run(_ExactMediaTransport(session).fetch(job, output_id, staging))
    if fetched != staging:
        raise OwnerAmbiguityGate('unexpected reconciliation acquisition path')
    metadata = inspect_video(staging)
    digest = file_sha256(staging)
    receipt = {**intent, **metadata, 'sha256': digest, 'file_size': staging.stat().st_size}
    store.save_acquisition_record(JOB, output_id, receipt, completed=True)
    if store.read_acquisition_record(JOB, output_id, completed=True) != receipt:
        raise OwnerAmbiguityGate('reconciled receipt integrity failed')
    if file_sha256(staging) != digest or inspect_video(staging) != metadata:
        raise OwnerAmbiguityGate('reconciled staging bytes changed')
    os.link(staging, final)  # No overwrite; only promote these exact validated bytes.
    staging.unlink()
    _full_decode(final)
    asset = Asset(asset_id='asset_' + sha256({'job': JOB, 'provider_asset_id': output_id, 'sha256': digest}),
        uri_or_path=str(final), sha256=digest, mime_type=metadata['mime_type'], duration_s=metadata['duration_s'],
        width=metadata['width'], height=metadata['height'], file_size=final.stat().st_size,
        source_attempt_id=ATTEMPT, provider_job_id=JOB, provider_asset_id=output_id,
        rights_metadata={'identity_binding': bindings[0], 'acquisition_receipt': receipt})
    store.save_asset(asset)
    return asset


def run(cookie):
    if OUTPUT.exists():
        raise OwnerAmbiguityGate('reconciliation evidence directory already exists; no repetition')
    store = SQLiteStore(DATABASE)
    job = frozen_job(store)
    before = file_sha256(DATABASE)
    with sqlite3.connect(f'file:{DATABASE.as_posix()}?mode=ro', uri=True) as connection:
        historical_before = historical_snapshot(connection)
    OUTPUT.mkdir()
    report = {'gate': 'OWNER_AMBIGUITY_GATE', 'attempt': ATTEMPT, 'job': JOB,
        'frozen_intent_hash': intent_hash(job),
        'project': PROJECT_ID, 'reference': REFERENCE_MEDIA_ID, 'model': 'abra_r2v_8s', 'marker': MARKER,
        'base_revision': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'database_before_sha256': before, 'story_auto_response_comparison': story_controls(),
        'additional_mzza6b_submits': 0, 'reference_uploads': 0, 'shot_b_submits': 0,
        'dola_seedance_calls': 0, 'provider_switch': 0, 'blind_retry': 0,
        'asset': None, 'technical_qc': None, 'selected_take_created': False}
    session = ReadOnlySession(cookie_path=cookie, project_id=PROJECT_ID)
    try:
        with session:
            report['session_metadata'] = contract.sanitize_session(session.metadata(), PROJECT_ID)
            records = session.catalog()
            report['catalog_fingerprint'] = session.catalog_fingerprint
            if session.catalog_fingerprint != contract.QUALIFIED_BASELINE_FINGERPRINT:
                raise OwnerAmbiguityGate('catalog contract drift')
            finding, owned = differential(records)
            report.update(finding)
            report['database_after_readonly_sha256'] = file_sha256(DATABASE)
            if report['database_after_readonly_sha256'] != before:
                raise OwnerAmbiguityGate('read-only reconciliation changed ledger')
            write_new(OUTPUT / 'catalog_reconciliation.json', report)
            if owned is not None:
                # Owner permits binding/acquisition ONLY after strict read-only
                # reconciliation. Preserve every historical ambiguity fact.
                if frozen_job(store) != job:
                    raise OwnerAmbiguityGate('frozen successor changed during reconciliation')
                identity = owned[0]
                store.record_dispatch_fact(JOB, 'PROVIDER_ACCEPTANCE_OBSERVED',
                    {'request_hash': job.correlation_evidence['rpc_request_hash'],
                     'provider_reference': REFERENCE_MEDIA_ID, 'contract': RPC_CONTRACT})
                store.record_dispatch_fact(JOB, 'REMOTE_IDENTITY_OBSERVED',
                    {'output_id': identity, 'method': 'rpc_catalog_exact_prompt_reference'})
                store.bind_output(JOB, identity)
                updated = job.model_copy(update={'external_job_id': identity, 'status': 'SUCCEEDED',
                    'submission_state': 'SUBMITTED', 'submitted_at': job.submitted_at or utc_now(), 'last_checked_at': utc_now()})
                store.save_provider_job(updated)
                asset = acquire_reconciled(store, session, identity, sha256(report))
                report['asset'] = asset.model_dump(mode='json')
                spec = importlib.util.spec_from_file_location('successor_review', ROOT / 'tools/slice0011_successor_live.py')
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                packet = module.build_review(DATABASE, asset, OUTPUT)
                report.update(technical_qc=packet['technical'], review_packet=str(OUTPUT/'character_review.json'),
                              gate='OWNER_CHARACTER_CONTINUITY_REVIEW_GATE')
    except Exception as exc:
        report.update(stop_type=type(exc).__name__, gate='OWNER_AMBIGUITY_GATE')
        if 'verdict' not in report:
            report['verdict'] = 'CONFLICTING_OR_NONUNIQUE_OUTPUT'
    finally:
        report['provider_rpc_calls'] = dict(session.rpc_call_counts)
        with sqlite3.connect(f'file:{DATABASE.as_posix()}?mode=ro', uri=True) as connection:
            historical_after = historical_snapshot(connection)
        report.update(historical_unchanged=historical_before == historical_after,
            historical_before_sha256=sha256(historical_before), historical_after_sha256=sha256(historical_after),
            database_final_sha256=file_sha256(DATABASE), ambiguity_cleared=False)
        if not report['historical_unchanged']:
            report['gate'] = 'OWNER_AMBIGUITY_GATE'
        write_new(OUTPUT / 'final_report.json', report)
        print(json.dumps({'verdict': report['verdict'], 'gate': report['gate'],
            'provider_rpc_calls': report['provider_rpc_calls'], 'delta': report.get('exact_delta_ids'),
            'historical_unchanged': report['historical_unchanged'], 'report': str(OUTPUT/'final_report.json')}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--cookie', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.cookie)
    except Exception as exc:
        print(json.dumps({'gate':'OWNER_AMBIGUITY_GATE','stop_type':type(exc).__name__}),flush=True)
        raise SystemExit(1)
