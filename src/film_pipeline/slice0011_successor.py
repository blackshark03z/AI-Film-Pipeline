"""One explicit Owner grant for a new A job; ordinary retry gates stay intact."""
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

from .core import canonical_json, sha256, validate_contract
from .dispatch_evidence import append_fact, intent_hash, read_facts
from .live_runtime import GenerationAttempt, ProviderJob, make_provider_job, utc_now
from .providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from .providers.flow_r2v_prompt import compile_flow_r2v_prompt, VERSION, MODEL
from .providers import flow_rpc_contract as contract
from .slice0011 import (PROJECT_ID, ACCOUNT_ID, REFERENCE_ASSET_ID, REFERENCE_SHA256,
                       RPC_CONTRACT, compile_character_paths, _reference_binding)
from .store import SQLiteStore

BASE_REVISION = '86acfeb1166717ab4ec76c689dd0e862c57ef134'
OWNER_BRIEF_SHA256 = '377ba947f30f3b8b664a33e5950889d261964ebecfa2374a369719b0ad60a54f'
AUTHORITY_ID = 'successor_authority_' + OWNER_BRIEF_SHA256
PARENT_ATTEMPT = 'attempt_3b7fa3f988caeb979db14c6332be05c535aca9af6c3514c459aa74302d48d4ca'
PARENT_JOB = 'job_26f3a0b279b6d43ca6ad4cff7084ebc552f0ba7ad792c8519e74fd526490a6b8'
SHOT_ID = 'CHAR_CONTINUITY_A'
REFERENCE_MEDIA_ID = '53b5a413-7bb5-4f97-9be4-2461794a7d80'
PLAN_HASH = 'cbc6cabae3fe2132c6ba6c3b49d78e9994ff3b670549f1980eff82e0cc9da324'
TABLE = 'slice0011_successors'


def _schema(connection):
    connection.execute(f'''CREATE TABLE IF NOT EXISTS {TABLE} (
        id TEXT PRIMARY KEY, parent_job TEXT NOT NULL UNIQUE REFERENCES provider_jobs(id),
        attempt_id TEXT NOT NULL UNIQUE REFERENCES generation_attempts(id),
        job_id TEXT NOT NULL UNIQUE REFERENCES provider_jobs(id), payload TEXT NOT NULL)''')
    connection.execute('''CREATE TABLE IF NOT EXISTS slice0011_successor_consumptions (
        authority_id TEXT PRIMARY KEY REFERENCES slice0011_successors(id),
        job_id TEXT NOT NULL UNIQUE REFERENCES provider_jobs(id), payload TEXT NOT NULL)''')
    for table in (TABLE, 'slice0011_successor_consumptions'):
        for action in ('UPDATE', 'DELETE'):
            connection.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_immutable "
                f"BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable successor authority'); END")


def historical_snapshot(connection) -> dict:
    """Exact pre-existing rows, including canonical/reference and dispatch evidence."""
    data = {}
    queries = {
        'attempt': ('SELECT * FROM generation_attempts WHERE id=?', (PARENT_ATTEMPT,)),
        'job': ('SELECT * FROM provider_jobs WHERE id=?', (PARENT_JOB,)),
        'journal': ('SELECT * FROM dispatch_journal WHERE job_id=? ORDER BY sequence', (PARENT_JOB,)),
        'bindings': ('SELECT * FROM output_bindings WHERE job_id=? ORDER BY output_id', (PARENT_JOB,)),
        'acquisition_intents': ('SELECT * FROM acquisition_intents WHERE job_id=? ORDER BY output_id', (PARENT_JOB,)),
        'acquisition_receipts': ('SELECT * FROM acquisition_receipts WHERE job_id=? ORDER BY output_id', (PARENT_JOB,)),
        'assets': ('SELECT * FROM assets WHERE generation_attempt_id=? OR id=? ORDER BY id', (PARENT_ATTEMPT, REFERENCE_ASSET_ID)),
        'shots': ('SELECT * FROM shot_specs ORDER BY hash', ()),
        'plans': ('SELECT * FROM prompt_plans ORDER BY hash', ()),
        'routes': ('SELECT * FROM routing_decisions ORDER BY id', ()),
        'reference_uploads': ('SELECT * FROM reference_uploads ORDER BY id', ()),
        'reference_events': ('SELECT * FROM reference_upload_events ORDER BY reservation_id,sequence', ()),
    }
    for key, (query, args) in queries.items():
        data[key] = connection.execute(query, args).fetchall()
    return data


def _parent(connection):
    raw = connection.execute('SELECT payload FROM provider_jobs WHERE id=?', (PARENT_JOB,)).fetchone()
    attempt = connection.execute('SELECT payload FROM generation_attempts WHERE id=?', (PARENT_ATTEMPT,)).fetchone()
    if raw is None or attempt is None:
        raise OwnerAmbiguityGate('exact historical attempt/job required')
    old, a = ProviderJob.model_validate(json.loads(raw[0])), json.loads(attempt[0])
    facts = read_facts(connection, PARENT_JOB)
    if (old.generation_attempt_id != PARENT_ATTEMPT or old.dispatch_count != 1
            or old.status != 'INCONCLUSIVE' or old.external_job_id is not None
            or a['shot_id'] != SHOT_ID or a['prompt_plan_hash'] != PLAN_HASH
            or old.project_binding_id != sha256(PROJECT_ID)
            or not any(f['kind'] == 'AMBIGUOUS_EVIDENCE' for f in facts)):
        raise OwnerAmbiguityGate('historical ambiguity must remain immutable')
    return old


def _validate_job(job, receipt):
    # No caller-defined allowance/project/shot/reference/compiler is accepted.
    expected = {'supersedes_attempt': PARENT_ATTEMPT, 'supersedes_job': PARENT_JOB,
        'successor_authority_id': AUTHORITY_ID, 'owner_brief_sha256': OWNER_BRIEF_SHA256,
        'provider_prompt_compiler': VERSION, 'prompt_plan_hash': PLAN_HASH}
    if (receipt is None or any(job.correlation_evidence.get(k) != v for k, v in expected.items())
            or job.provider_id != 'flow_veo' or job.project_binding_id != sha256(PROJECT_ID)
            or job.correlation_evidence.get('reference_binding') != _reference_binding(receipt)
            or receipt['media_id'] != REFERENCE_MEDIA_ID or receipt['reference_sha256'] != REFERENCE_SHA256
            or receipt['asset_id'] != REFERENCE_ASSET_ID):
        raise OwnerAmbiguityGate('successor authority scope mismatch')


def _record(connection):
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone():
        return None
    row = connection.execute(f'SELECT parent_job,attempt_id,job_id,payload FROM {TABLE} WHERE id=?', (AUTHORITY_ID,)).fetchone()
    if row is None:
        return None
    facts = json.loads(row[3])
    if (row[:3] != (PARENT_JOB, facts['attempt_id'], facts['job_id'])
            or facts['authority_id'] != AUTHORITY_ID or facts['owner_brief_sha256'] != OWNER_BRIEF_SHA256
            or facts['base_revision'] != BASE_REVISION or facts['max_new_submits'] != 1
            or facts['shot_id'] != SHOT_ID or facts['model'] != MODEL):
        raise OwnerAmbiguityGate('successor authority record invalid')
    return facts


def read_successor(store: SQLiteStore):
    with closing(store._connect()) as connection:
        facts = _record(connection)
        if facts is None:
            return None
        _parent(connection)
        if sha256(historical_snapshot(connection)) != facts['historical_snapshot_sha256']:
            raise OwnerAmbiguityGate('historical rows changed after authorization')
    job = store.read_provider_job(facts['job_id'])
    if job.generation_attempt_id != facts['attempt_id'] or intent_hash(job) != facts['intent_hash']:
        raise OwnerAmbiguityGate('successor frozen intent changed')
    path = store.read_path(job.generation_attempt_id)
    if path[0].shot_id != SHOT_ID or sha256(path[1]) != PLAN_HASH:
        raise OwnerAmbiguityGate('successor canonical path changed')
    return job


def freeze_successor(db_path: Path, session, receipt: dict):
    """Atomically allocate exactly one new attempt/job under this fixed grant."""
    store = SQLiteStore(db_path)
    prior = read_successor(store)
    if prior is not None:
        return prior
    reference, _, paths = compile_character_paths(db_path)
    shot, plan, decision = paths[0]
    actual = ReferenceUploadStore(db_path).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID, reference)
    if (receipt != actual or receipt['media_id'] != REFERENCE_MEDIA_ID or session.project_id != PROJECT_ID
            or shot.shot_id != SHOT_ID or sha256(plan) != PLAN_HASH):
        raise OwnerAmbiguityGate('exact successor reference/project/path required')
    with closing(store._connect()) as connection:
        _parent(connection)
        before = sha256(historical_snapshot(connection))
    records = session.catalog()
    if session.catalog_fingerprint != contract.QUALIFIED_BASELINE_FINGERPRINT:
        raise OwnerAmbiguityGate('successor catalog contract unqualified')
    snapshot = {'catalog_ids': sorted(row[0].lower() for row in records),
        'catalog_fingerprint': session.catalog_fingerprint, 'project_id': PROJECT_ID}
    attempt = GenerationAttempt(generation_attempt_id='attempt_' + sha256({
        'authority': AUTHORITY_ID, 'parent': PARENT_ATTEMPT, 'plan': PLAN_HASH}),
        shot_id=SHOT_ID, shot_spec_version=shot.spec_version, shot_spec_hash=sha256(shot),
        prompt_plan_hash=PLAN_HASH, routing_decision_id=decision.routing_decision_id,
        provider_id='flow_veo', status='created', started_at=utc_now())
    job = make_provider_job(attempt, project_binding_id=sha256(PROJECT_ID), pre_dispatch_snapshot=snapshot)
    compiled = compile_flow_r2v_prompt(plan, job.provider_job_id)
    if contract.match_r2v_output(records, PROJECT_ID, REFERENCE_MEDIA_ID, job.provider_job_id, baseline_ids=[]) is not None:
        raise OwnerAmbiguityGate('successor marker existed before intent freeze')
    prompt = compiled.text
    job = job.model_copy(update={'correlation_evidence': {
        'prompt': prompt, 'prompt_plan_hash': PLAN_HASH, 'submission_prompt_hash': sha256(prompt),
        'correlation_marker': compiled.marker, 'provider_prompt_compiler': VERSION,
        'reference_binding': _reference_binding(receipt),
        'rpc_request_hash': sha256({'contract': RPC_CONTRACT, 'project': PROJECT_ID,
            'prompt': prompt, 'reference_id': REFERENCE_MEDIA_ID, 'job_id': job.provider_job_id}),
        'supersedes_attempt': PARENT_ATTEMPT, 'supersedes_job': PARENT_JOB,
        'successor_authority_id': AUTHORITY_ID, 'owner_brief_sha256': OWNER_BRIEF_SHA256,
        'historical_snapshot_sha256': before}})
    _validate_job(job, receipt)
    facts = {'authority_id': AUTHORITY_ID, 'owner_brief_sha256': OWNER_BRIEF_SHA256,
        'base_revision': BASE_REVISION, 'shot_id': SHOT_ID, 'model': MODEL, 'max_new_submits': 1,
        'historical_snapshot_sha256': before, 'attempt_id': attempt.generation_attempt_id,
        'job_id': job.provider_job_id, 'intent_hash': intent_hash(job)}
    connection = store._connect()
    try:
        connection.execute('BEGIN IMMEDIATE')
        _schema(connection)
        existing = _record(connection)
        if existing is not None:
            connection.rollback()
            return read_successor(store)
        _parent(connection)
        if sha256(historical_snapshot(connection)) != before:
            raise OwnerAmbiguityGate('historical evidence changed during allocation')
        ids = connection.execute('SELECT id FROM generation_attempts WHERE json_extract(payload,\'$.shot_id\')=?', (SHOT_ID,)).fetchall()
        if ids != [(PARENT_ATTEMPT,)]:
            raise OwnerAmbiguityGate('another Shot A attempt exists; no allocation')
        for name, value in (('shot_spec', shot), ('prompt_plan', plan), ('routing_decision', decision), ('generation_attempt', attempt)):
            validate_contract(name, value.payload())
        store._insert_immutable(connection, 'shot_specs', sha256(shot), canonical_json(shot.payload()))
        store._insert_immutable(connection, 'prompt_plans', PLAN_HASH, canonical_json(plan.payload()), sha256(shot))
        store._insert_immutable(connection, 'routing_decisions', decision.routing_decision_id,
            canonical_json(decision.payload()), PLAN_HASH)
        store._insert_immutable(connection, 'generation_attempts', attempt.generation_attempt_id,
            canonical_json(attempt.payload()), sha256(shot), PLAN_HASH, decision.routing_decision_id)
        connection.execute('INSERT INTO provider_jobs VALUES (?,?,?,?,?)',
            (job.provider_job_id, attempt.generation_attempt_id, 'flow_veo', 0, canonical_json(job.model_dump(mode='json'))))
        connection.execute(f'INSERT INTO {TABLE} VALUES (?,?,?,?,?)',
            (AUTHORITY_ID, PARENT_JOB, attempt.generation_attempt_id, job.provider_job_id, canonical_json(facts)))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return read_successor(store)


def reserve_successor_dispatch(store: SQLiteStore, job_id: str, authority_id: str):
    """Consume the explicit grant and job budget in the same durable transaction."""
    if authority_id != AUTHORITY_ID:
        raise OwnerAmbiguityGate('unknown successor authority')
    reference = store.read_reference_asset(REFERENCE_ASSET_ID)
    receipt = ReferenceUploadStore(store.path).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID, reference)
    connection = store._connect()
    try:
        connection.execute('BEGIN IMMEDIATE')
        facts = _record(connection)
        if facts is None or facts['job_id'] != job_id:
            raise OwnerAmbiguityGate('job is not the authorized successor')
        _parent(connection)
        if sha256(historical_snapshot(connection)) != facts['historical_snapshot_sha256']:
            raise OwnerAmbiguityGate('historical rows changed; no successor reservation')
        row = connection.execute('SELECT payload FROM provider_jobs WHERE id=?', (job_id,)).fetchone()
        job = ProviderJob.model_validate(json.loads(row[0]))
        _validate_job(job, receipt)
        if job.generation_attempt_id != facts['attempt_id'] or intent_hash(job) != facts['intent_hash']:
            raise OwnerAmbiguityGate('successor authority intent mismatch')
        attempt_row = connection.execute('SELECT payload FROM generation_attempts WHERE id=?', (facts['attempt_id'],)).fetchone()
        attempt = json.loads(attempt_row[0])
        all_jobs = connection.execute('SELECT jobs.id FROM provider_jobs jobs JOIN generation_attempts attempts ON attempts.id=jobs.generation_attempt_id '
            'WHERE json_extract(attempts.payload,\'$.shot_id\')=? ORDER BY jobs.id', (SHOT_ID,)).fetchall()
        if (attempt['shot_id'] != SHOT_ID or attempt['prompt_plan_hash'] != PLAN_HASH
                or all_jobs != sorted([(PARENT_JOB,), (job_id,)])):
            raise OwnerAmbiguityGate('another or altered shot path; no successor reservation')
        used = connection.execute('SELECT jobs.id FROM provider_jobs jobs JOIN generation_attempts attempts ON attempts.id=jobs.generation_attempt_id '
            'WHERE jobs.dispatch_count=1 AND json_extract(attempts.payload,\'$.shot_id\')=? ORDER BY jobs.id', (SHOT_ID,)).fetchall()
        if (used != [(PARENT_JOB,)] or job.dispatch_count != 0
                or connection.execute('SELECT 1 FROM slice0011_successor_consumptions WHERE authority_id=?', (AUTHORITY_ID,)).fetchone()):
            raise OwnerAmbiguityGate('successor allowance consumed; no retry')
        reserved = job.model_copy(update={'dispatch_count': 1, 'submission_state': 'SUBMISSION_RESERVED', 'status': 'INCONCLUSIVE'})
        connection.execute('INSERT INTO slice0011_successor_consumptions VALUES (?,?,?)',
            (AUTHORITY_ID, job_id, canonical_json({'authority_id': AUTHORITY_ID, 'job_id': job_id, 'consumed_at': utc_now()})))
        connection.execute('UPDATE provider_jobs SET dispatch_count=1,payload=? WHERE id=?',
            (canonical_json(reserved.model_dump(mode='json')), job_id))
        append_fact(connection, job_id, 'RESERVED', {'intent_hash': intent_hash(reserved)})
        connection.commit()
        return reserved
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
