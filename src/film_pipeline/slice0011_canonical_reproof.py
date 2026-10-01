"""Fixed Owner grant for one canonical-reference Shot A, never a retry grant."""
import json
from contextlib import closing

from .core import canonical_json, sha256
from .dispatch_evidence import append_fact, intent_hash
from .live_runtime import GenerationAttempt, ProviderJob, make_provider_job, utc_now
from .providers.flow_reference_binding import verify_attestation
from .providers.flow_reference_upload import OwnerAmbiguityGate
from .providers.flow_r2v_prompt import compile_flow_r2v_prompt
from .providers import flow_rpc_contract as contract
from .slice0011 import (PROJECT_ID, ACCOUNT_ID, REFERENCE_ASSET_ID, REFERENCE_SHA256,
                       compile_character_paths, _reference_binding)
from .slice0011_successor import historical_snapshot as original_snapshot, PLAN_HASH
from .store import SQLiteStore

REFERENCE_MEDIA_ID = '53b5a413-7bb5-4f97-9be4-2461794a7d80'
MODEL = 'veo_3_1_r2v_lite'
SHOT_ID = 'CHAR_CONTINUITY_A'
AUTHORITY = {'version': 'slice0011-canonical-a-reproof-20261001-v1',
    'source': 'Owner current chat REPAIR CANONICAL REFERENCE MAPPING + RE-PROVE SHOT A',
    'shot_id': SHOT_ID, 'project_id': PROJECT_ID, 'reference_media_id': REFERENCE_MEDIA_ID,
    'max_generate': 1, 'max_upload': 0, 'max_retry': 0, 'shot_b': False,
    'model': MODEL, 'duration_s': 8, 'aspect_ratio': '16:9', 'output_count': 1}
AUTHORITY_ID = 'canonical_reproof_' + sha256(AUTHORITY)
HISTORICAL_JOBS = (
    'job_26f3a0b279b6d43ca6ad4cff7084ebc552f0ba7ad792c8519e74fd526490a6b8',
    'job_4d11911518710248299682693a3fdb48ec1426ffc0a6ab6d45de615596060d40')
TABLE = 'slice0011_canonical_reproof'


def _schema(c):
    c.execute(f'CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY, job_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)')
    c.execute(f'CREATE TABLE IF NOT EXISTS {TABLE}_consumption (id TEXT PRIMARY KEY, job_id TEXT UNIQUE NOT NULL)')
    for table in (TABLE, TABLE + '_consumption'):
        for action in ('UPDATE', 'DELETE'):
            c.execute(f'CREATE TRIGGER IF NOT EXISTS {table}_no_{action} BEFORE {action} ON {table} '
                      "BEGIN SELECT RAISE(ABORT,'immutable one-shot Owner authority'); END")


def historical_snapshot(c):
    result = original_snapshot(c)
    # The first authority's snapshot covers canonical/reference rows and its
    # parent. Capture both old jobs and every old journal/binding here.
    for job_id in HISTORICAL_JOBS:
        row = c.execute('SELECT * FROM provider_jobs WHERE id=?', (job_id,)).fetchall()
        if len(row) != 1 or row[0][3] != 1:
            raise OwnerAmbiguityGate('EXACT_HISTORICAL_JOB_REQUIRED')
        old = json.loads(row[0][4])
        if old['status'] != 'INCONCLUSIVE' or old['external_job_id'] is not None:
            raise OwnerAmbiguityGate('HISTORICAL_STATE_CHANGED')
        result[job_id] = {'job': row,
            'attempt': c.execute('SELECT * FROM generation_attempts WHERE id=?', (row[0][1],)).fetchall()}
        for table in ('dispatch_journal', 'output_bindings', 'acquisition_intents', 'acquisition_receipts'):
            result[job_id][table] = c.execute(f'SELECT * FROM {table} WHERE job_id=? ORDER BY 1,2', (job_id,)).fetchall()
    return result


def _verified(store, attestation, evidence_dir):
    expected = {'asset_id': REFERENCE_ASSET_ID, 'source_sha256': REFERENCE_SHA256,
        'project_id': PROJECT_ID, 'media_id': REFERENCE_MEDIA_ID, 'account_id': ACCOUNT_ID,
        'provider_id': 'flow_veo', 'version': 'flow-canonical-reference-v1'}
    if any(attestation.get(k) != v for k, v in expected.items()):
        raise OwnerAmbiguityGate('CANONICAL_REPROOF_SCOPE_MISMATCH')
    asset = store.read_reference_asset(REFERENCE_ASSET_ID)
    return verify_attestation(store, asset, attestation, media_id=REFERENCE_MEDIA_ID,
                              project_id=PROJECT_ID, evidence_dir=evidence_dir)


def _all_jobs(c):
    return sorted(r[0] for r in c.execute('SELECT j.id FROM provider_jobs j JOIN generation_attempts a '
        "ON a.id=j.generation_attempt_id WHERE json_extract(a.payload,'$.shot_id')=?", (SHOT_ID,)))


def _intent(attestation, history):
    return {'authority_id': AUTHORITY_ID, 'authority': AUTHORITY,
        'attestation_id': attestation['attestation_id'], 'attestation_sha256': sha256(attestation),
        'historical_snapshot_sha256': history, 'contract': contract.CONTRACT_VERSION_2026_10_01}


def freeze_reproof(db_path, session, attestation, evidence_dir):
    store = SQLiteStore(db_path)
    _verified(store, attestation, evidence_dir)
    if session.project_id != PROJECT_ID:
        raise OwnerAmbiguityGate('CANONICAL_REPROOF_PROJECT_MISMATCH')
    reference, _, paths = compile_character_paths(db_path)
    shot, plan, decision = paths[0]
    if shot.shot_id != SHOT_ID or sha256(plan) != PLAN_HASH:
        raise OwnerAmbiguityGate('CANONICAL_REPROOF_PLAN_CHANGED')
    records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
    with closing(store._connect()) as c:
        history = sha256(historical_snapshot(c))
    attempt = GenerationAttempt(generation_attempt_id='attempt_' + sha256({'authority': AUTHORITY_ID, 'plan': PLAN_HASH}),
        shot_id=SHOT_ID, shot_spec_version=shot.spec_version, shot_spec_hash=sha256(shot),
        prompt_plan_hash=PLAN_HASH, routing_decision_id=decision.routing_decision_id,
        provider_id='flow_veo', status='created', started_at=utc_now())
    job = make_provider_job(attempt, project_binding_id=sha256(PROJECT_ID), pre_dispatch_snapshot={
        'catalog_ids': sorted(r[0] for r in records), 'project_id': PROJECT_ID,
        'catalog_fingerprint': session.catalog_fingerprint})
    compiled = compile_flow_r2v_prompt(plan, job.provider_job_id, model=MODEL)
    prompt = compiled.text.replace('\n', ' ')
    if any(compiled.marker in s for row in records for s in contract._strings(row)):
        raise OwnerAmbiguityGate('CANONICAL_REPROOF_MARKER_ALREADY_EXISTS')
    from .providers.flow_reference_upload import ReferenceUploadStore
    receipt = ReferenceUploadStore(db_path).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID, reference)
    job = job.model_copy(update={'correlation_evidence': {'prompt': prompt,
        'prompt_plan_hash': PLAN_HASH, 'submission_prompt_hash': sha256(prompt),
        'correlation_marker': compiled.marker, 'provider_prompt_compiler': compiled.version,
        'reference_binding': _reference_binding(receipt), 'native_ui_intent': _intent(attestation, history)}})
    with closing(store._connect()) as c:
        with c:
            c.execute('BEGIN IMMEDIATE')
            _schema(c)
            if c.execute(f'SELECT 1 FROM {TABLE}').fetchone():
                raise OwnerAmbiguityGate('CANONICAL_REPROOF_ALREADY_FROZEN_NO_REALLOCATION')
            if _all_jobs(c) != sorted(HISTORICAL_JOBS) or sha256(historical_snapshot(c)) != history:
                raise OwnerAmbiguityGate('HISTORY_OR_JOB_SET_CHANGED')
            store._insert_immutable(c, 'shot_specs', sha256(shot), canonical_json(shot.payload()))
            store._insert_immutable(c, 'prompt_plans', PLAN_HASH, canonical_json(plan.payload()), sha256(shot))
            store._insert_immutable(c, 'routing_decisions', decision.routing_decision_id, canonical_json(decision.payload()), PLAN_HASH)
            store._insert_immutable(c, 'generation_attempts', attempt.generation_attempt_id,
                canonical_json(attempt.payload()), sha256(shot), PLAN_HASH, decision.routing_decision_id)
            c.execute('INSERT INTO provider_jobs VALUES (?,?,?,?,?)', (job.provider_job_id,
                attempt.generation_attempt_id, 'flow_veo', 0, canonical_json(job.model_dump(mode='json'))))
            c.execute(f'INSERT INTO {TABLE} VALUES (?,?,?)', (AUTHORITY_ID, job.provider_job_id,
                canonical_json({'intent_hash': intent_hash(job), 'native_ui_intent': job.correlation_evidence['native_ui_intent']})))
    return store.read_provider_job(job.provider_job_id)


def reserve_reproof_dispatch(store, job_id, attestation, evidence_dir):
    _verified(store, attestation, evidence_dir)
    frozen_job = store.read_provider_job(job_id)
    shot, plan, decision, _ = store.read_path(frozen_job.generation_attempt_id)
    if (shot.shot_id != SHOT_ID or sha256(plan) != PLAN_HASH
            or frozen_job.provider_id != 'flow_veo'
            or frozen_job.project_binding_id != sha256(PROJECT_ID)
            or frozen_job.correlation_evidence['prompt'] != compile_flow_r2v_prompt(
                plan, job_id, model=MODEL).text.replace('\n', ' ')):
        raise OwnerAmbiguityGate('CANONICAL_REPROOF_PATH_CHANGED')
    with closing(store._connect()) as c:
        with c:
            c.execute('BEGIN IMMEDIATE')
            record = c.execute(f'SELECT job_id,payload FROM {TABLE} WHERE id=?', (AUTHORITY_ID,)).fetchone()
            if not record or record[0] != job_id:
                raise OwnerAmbiguityGate('UNKNOWN_CANONICAL_REPROOF_JOB')
            facts = json.loads(record[1])
            job = ProviderJob.model_validate_json(c.execute('SELECT payload FROM provider_jobs WHERE id=?', (job_id,)).fetchone()[0])
            history = sha256(historical_snapshot(c))
            if (job.dispatch_count != 0 or facts['intent_hash'] != intent_hash(job)
                    or facts['native_ui_intent'] != _intent(attestation, history)
                    or job.correlation_evidence['native_ui_intent'] != facts['native_ui_intent']
                    or _all_jobs(c) != sorted([*HISTORICAL_JOBS, job_id])
                    or c.execute(f'SELECT 1 FROM {TABLE}_consumption').fetchone()):
                raise OwnerAmbiguityGate('CANONICAL_REPROOF_CONSUMED_OR_INTENT_CHANGED')
            reserved = job.model_copy(update={'dispatch_count': 1, 'submission_state': 'SUBMISSION_RESERVED', 'status': 'INCONCLUSIVE'})
            c.execute(f'INSERT INTO {TABLE}_consumption VALUES (?,?)', (AUTHORITY_ID, job_id))
            c.execute('UPDATE provider_jobs SET dispatch_count=1,payload=? WHERE id=?', (canonical_json(reserved.model_dump(mode='json')), job_id))
            append_fact(c, job_id, 'RESERVED', {'intent_hash': intent_hash(reserved)})
    return reserved
