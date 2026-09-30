"""Owner-authorized restoration of the exact zero-RPC auth stop; one original grant."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from pathlib import Path

from film_pipeline.core import canonical_json, sha256
from film_pipeline.live_runtime import file_sha256
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_transport import image_comparison
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from film_pipeline.slice0011 import ROOT, PROJECT_ID, ACCOUNT_ID, REFERENCE_ASSET_ID
from film_pipeline.slice0011_successor import REFERENCE_MEDIA_ID, historical_snapshot, read_successor
from film_pipeline.store import SQLiteStore

SLICE_ROOT = ROOT / 'projects/character_continuity/slice0011'
DATABASE = SLICE_ROOT / 'runtime.sqlite'
PREVIOUS = SLICE_ROOT / 'successor_a_compact_v1/live_result.json'
PREVIOUS_HASH = '98951453497d3e171e00dc4cd0d351019b8644619a73a8c42098ced806b6aaba'
RESTORATION = SLICE_ROOT / 'auth_restoration_v1'
OUTPUT = SLICE_ROOT / 'successor_a_compact_v1_auth_restored'


class AuthPreflightSession(FlowReferenceRpcSession):
    def _rpc_body(self, rpc_id, body, **options):
        if rpc_id not in {contract.RPC_CATALOG, contract.RPC_MEDIA}:
            raise OwnerAmbiguityGate('auth preflight forbids generation, upload and unrelated RPCs')
        return super()._rpc_body(rpc_id, body, **options)

    def captcha(self, action):
        raise OwnerAmbiguityGate('auth preflight cannot request generation captcha')


def validate_previous_stop(store, previous):
    """Reject every stop other than the exact Owner-authorized preallocation auth stop."""
    zero = ('mzza6b_submits', 'reference_uploads', 'shot_b_submits', 'dola_seedance_calls')
    if (previous.get('gate') != 'OWNER_AMBIGUITY_GATE'
            or previous.get('stop_type') != 'OwnerAuthRequired'
            or any(type(previous.get(k)) is not int or previous[k] != 0 for k in zero)
            or previous.get('rpc_calls') != {} or previous.get('asset') is not None
            or previous.get('output_identity') is not None
            or previous.get('successor_attempt_id') is not None
            or previous.get('provider_job_id') is not None
            or previous.get('historical_unchanged') is not True
            or previous.get('project_id') != PROJECT_ID
            or previous.get('reference_media_id') != REFERENCE_MEDIA_ID
            or read_successor(store) is not None):
        raise OwnerAmbiguityGate('only the exact zero-RPC preallocation auth stop may resume')
    with sqlite3.connect(f'file:{store.path.as_posix()}?mode=ro', uri=True) as connection:
        current = sha256(historical_snapshot(connection))
        counts = [connection.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                  for t in ('generation_attempts', 'provider_jobs')]
    if (counts != [1, 1] or current != previous.get('historical_before_hash')
            or current != previous.get('historical_after_hash')):
        raise OwnerAmbiguityGate('historical ledger or allocation boundary changed')
    return current


def reference_preflight(session, store):
    """Read-only exhaustive image verification, with no reference lifecycle mutation."""
    asset = store.read_reference_asset(REFERENCE_ASSET_ID)
    receipt = ReferenceUploadStore(store.path).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    if receipt is None or receipt['media_id'] != REFERENCE_MEDIA_ID:
        raise OwnerAmbiguityGate('exact verified receipt unavailable')
    source = Path(asset.uri_or_path).read_bytes()
    if file_sha256(Path(asset.uri_or_path)) != asset.sha256:
        raise OwnerAmbiguityGate('exact local reference bytes changed')
    metadata = contract.sanitize_session(session.metadata(), PROJECT_ID)
    records = session.catalog()
    contract._validate_catalog_rows(records, PROJECT_ID)
    if session.catalog_fingerprint != contract.QUALIFIED_BASELINE_FINGERPRINT:
        raise OwnerAmbiguityGate('auth catalog contract not qualified')
    matches, candidates = [], []
    for row in records:
        if len(row) != 7:
            continue
        data = session.media(row[0], 'image')
        if not data:
            raise OwnerAmbiguityGate('reference candidate readback unresolved')
        comparison = image_comparison(source, data)
        candidates.append({'media_id': row[0], 'comparison': comparison})
        if comparison['strong_match']:
            matches.append(row[0].lower())
    if matches != [REFERENCE_MEDIA_ID]:
        raise OwnerAmbiguityGate('exact reference is absent or non-unique')
    comparison = next(c['comparison'] for c in candidates if c['media_id'].lower() == REFERENCE_MEDIA_ID)
    if comparison['provider_media_sha256'] != receipt['provider_media_sha256']:
        raise OwnerAmbiguityGate('verified reference remote bytes changed')
    return {'session_valid': True, 'exact_project_accessible': True, 'catalog_read_succeeded': True,
        'metadata': metadata, 'catalog_fingerprint': session.catalog_fingerprint,
        'catalog_ids': sorted(row[0].lower() for row in records), 'reference_media_id': REFERENCE_MEDIA_ID,
        'reference_uniquely_verified': True, 'reference_usable': True, 'image_candidates': candidates}


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(canonical_json(value))


def run(cookie, original_brief, *, preflight_only=False):
    proof_path = RESTORATION / ('read_only_preflight.json' if preflight_only else 'execution_preflight.json')
    if proof_path.exists() or (OUTPUT / 'live_result.json').exists():
        raise OwnerAmbiguityGate('durable restoration stop/proof already recorded; no automatic repetition')
    first_proof = RESTORATION / 'read_only_preflight.json'
    if not preflight_only and first_proof.exists():
        if json.loads(first_proof.read_text(encoding='utf-8')).get('gate') != 'AUTH_RESTORATION_PREFLIGHT_PASS':
            raise OwnerAmbiguityGate('prior auth preflight stopped; Owner review required')
    if file_sha256(PREVIOUS) != PREVIOUS_HASH:
        raise OwnerAmbiguityGate('exact prior auth-stop evidence required')
    previous = json.loads(PREVIOUS.read_text(encoding='utf-8'))
    store = SQLiteStore(DATABASE)
    history_hash = validate_previous_stop(store, previous)
    before = file_sha256(DATABASE)
    report = {'gate': 'OWNER_AUTH_REVIEW_GATE', 'prior_stop_sha256': PREVIOUS_HASH,
        'historical_snapshot_sha256': history_hash, 'database_before_sha256': before,
        'mzza6b_submits': 0, 'reference_uploads': 0, 'successor_allocations': 0,
        'provider_job_allocations': 0, 'shot_b_submits': 0, 'dola_seedance_calls': 0}
    session = AuthPreflightSession(cookie_path=cookie, project_id=PROJECT_ID)
    try:
        with session:
            report['proof'] = reference_preflight(session, store)
        report['database_after_sha256'] = file_sha256(DATABASE)
        report['historical_after_sha256'] = validate_previous_stop(store, previous)
        if report['database_after_sha256'] != before:
            raise OwnerAmbiguityGate('read-only preflight changed ledger bytes')
        report['gate'] = 'AUTH_RESTORATION_PREFLIGHT_PASS'
    except Exception as exc:
        report['stop_type'] = type(exc).__name__  # Never authenticated exception text.
        report['gate'] = 'OWNER_AUTH_REVIEW_GATE'
    report['rpc_calls'] = dict(session.rpc_call_counts)
    RESTORATION.mkdir(parents=True, exist_ok=True)
    write_new(proof_path, report)
    print(json.dumps({'gate': report['gate'], 'rpc_calls': report['rpc_calls'],
                      'proof': str(proof_path)}), flush=True)
    if report['gate'] != 'AUTH_RESTORATION_PREFLIGHT_PASS' or preflight_only:
        return report
    # New Owner decision authorizes this exact continuation. Preserve the old
    # durable stop untouched; reuse the ORIGINAL immutable single allowance.
    spec = importlib.util.spec_from_file_location('authorized_successor', ROOT / 'tools/slice0011_successor_live.py')
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    entry.OUTPUT = OUTPUT
    result = entry.run(cookie, original_brief)
    if result.get('stop_type') == 'OwnerAuthRequired' and result.get('mzza6b_submits') == 0 and 'provider_job_id' not in result:
        final = {**result, 'gate': 'OWNER_AUTH_REVIEW_GATE'}
    else:
        final = result
    write_new(RESTORATION / 'continuation_result.json', {'auth_preflight': str(proof_path), **final})
    print(json.dumps({'gate': final['gate'], 'mzza6b_submits': final['mzza6b_submits']}), flush=True)
    return final


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cookie', type=Path, required=True)
    parser.add_argument('--original-brief', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    try:
        run(args.cookie, args.original_brief, preflight_only=args.preflight_only)
    except Exception as exc:
        print(json.dumps({'gate': 'OWNER_AUTH_REVIEW_GATE', 'stop_type': type(exc).__name__}), flush=True)
        raise SystemExit(1)
