"""Small typed write-through evidence journal and conservative recovery policy.

Append order is observation order. Strength is a monotonic high-water mark,
not a claim that browser/network callbacks arrived in causal order.
"""
import json
import re
from dataclasses import dataclass

from .core import canonical_json, sha256


PROTOCOL = 'flow-dispatch-evidence-v1'
RANK = {
    'AMBIGUOUS_EVIDENCE': 0,
    'OBSERVATION_FAILURE': 0,
    'RESERVED': 1, 'PROMPT_VERIFIED': 2, 'CLICK_ARMED': 3,
    'RPC_REQUEST_ARMED': 4,
    'TRUSTED_CLICK_OBSERVED': 4, 'PROMPT_ACCEPTANCE_TRANSITION': 4,
    'GENERATE_REQUEST_OBSERVED': 5, 'PROVIDER_RESPONSE_OBSERVED': 6,
    'PROVIDER_ACCEPTANCE_OBSERVED': 7, 'REMOTE_IDENTITY_OBSERVED': 8,
    'IDENTITY_BOUND': 9, 'DOWNLOAD_STARTED': 10,
    'DOWNLOAD_VALIDATED': 11, 'ASSET_PERSISTED': 12,
}
FIELDS = {
    'AMBIGUOUS_EVIDENCE': {'diagnostic'},
    'OBSERVATION_FAILURE': {'diagnostic'},
    'RESERVED': {'intent_hash'}, 'PROMPT_VERIFIED': {'prompt_sha256'}, 'CLICK_ARMED': set(),
    'RPC_REQUEST_ARMED': {'request_hash', 'body_sha256', 'contract'},
    'TRUSTED_CLICK_OBSERVED': set(), 'PROMPT_ACCEPTANCE_TRANSITION': set(),
    'GENERATE_REQUEST_OBSERVED': {'request_hash', 'body_sha256', 'contract'},
    'PROVIDER_RESPONSE_OBSERVED': {'request_hash', 'status'},
    'PROVIDER_ACCEPTANCE_OBSERVED': {'request_hash', 'provider_reference', 'contract'},
    'REMOTE_IDENTITY_OBSERVED': {'output_id', 'method'},
    'IDENTITY_BOUND': {'output_id', 'binding_hash'},
    'DOWNLOAD_STARTED': {'output_id', 'intent_hash'},
    'DOWNLOAD_VALIDATED': {'output_id', 'sha256', 'receipt_hash'},
    'ASSET_PERSISTED': {'output_id', 'asset_id'},
}


def intent_hash(job):
    return sha256({'job': job.provider_job_id, 'attempt': job.generation_attempt_id,
        'provider': job.provider_id, 'project': job.project_binding_id,
        'baseline': job.pre_dispatch_snapshot, 'protocol': job.dispatch_protocol,
        'prompt': {k: job.correlation_evidence.get(k) for k in
                   ('prompt', 'prompt_plan_hash', 'submission_prompt_hash',
                    'correlation_marker', 'reference_binding', 'rpc_request_hash')}})


def validate_fact(kind, data):
    if kind not in FIELDS or not isinstance(data, dict) or set(data) != FIELDS[kind]:
        raise ValueError('INVALID_DISPATCH_FACT')
    for key, value in data.items():
        if key == 'status':
            if type(value) is not int or not 100 <= value <= 599:
                raise ValueError('INVALID_RESPONSE_STATUS')
        elif key.endswith('sha256') or key.endswith('_hash'):
            if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
                raise ValueError('INVALID_EVIDENCE_HASH')
        elif not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_:.-]{1,300}', value):
            raise ValueError('UNSAFE_DISPATCH_EVIDENCE')
    return data


def append_fact(connection, job_id, kind, data):
    """Caller owns the transaction, including reservation/binding when needed."""
    validate_fact(kind, data)
    existing = connection.execute('SELECT payload FROM dispatch_journal WHERE job_id=? AND kind=? AND subject=?',
                                  (job_id, kind, data.get('output_id', ''))).fetchone()
    encoded = canonical_json(data)
    if existing:
        if existing[0] != encoded:
            raise ValueError('CONFLICTING_DISPATCH_FACT')
        return
    previous = connection.execute('SELECT sequence,digest FROM dispatch_journal WHERE job_id=? ORDER BY sequence DESC LIMIT 1',
                                  (job_id,)).fetchone()
    seq, prior = (previous[0] + 1, previous[1]) if previous else (1, '0' * 64)
    from .live_runtime import utc_now
    at = utc_now()
    digest = sha256({'job': job_id, 'sequence': seq, 'kind': kind, 'payload': data, 'at': at, 'previous': prior})
    connection.execute('INSERT INTO dispatch_journal VALUES (?,?,?,?,?,?,?,?)',
                       (job_id, seq, kind, data.get('output_id', ''), encoded, at, prior, digest))


def read_facts(connection, job_id):
    result = []
    prior = '0' * 64
    rows = connection.execute('SELECT sequence,kind,subject,payload,at,previous,digest FROM dispatch_journal WHERE job_id=? ORDER BY sequence',
                              (job_id,)).fetchall()
    for expected, (seq, kind, subject, payload, at, previous, digest) in enumerate(rows, 1):
        data = validate_fact(kind, json.loads(payload))
        if (seq != expected or previous != prior or subject != data.get('output_id', '')
                or digest != sha256({'job': job_id, 'sequence': seq, 'kind': kind, 'payload': data, 'at': at, 'previous': previous})):
            raise ValueError('DISPATCH_JOURNAL_INTEGRITY_FAILURE')
        result.append({'kind': kind, 'data': data, 'at': at})
        prior = digest
    return result


@dataclass(frozen=True)
class RecoveryDecision:
    classification: str
    action: str
    may_submit: bool = False
    strength: int = 0


def recovery_decision(job, facts, *, bound=False, acquired=False):
    if job.dispatch_protocol != PROTOCOL:
        return RecoveryDecision('LEGACY_HISTORY_READ_ONLY', 'STOP')
    kinds = {f['kind'] for f in facts}
    strength = max((RANK[k] for k in kinds), default=0)
    if job.dispatch_count == 0:
        return RecoveryDecision('NOT_RESERVED', 'REQUIRES_FRESH_AUTHORIZATION', strength=strength)
    if 'RESERVED' not in kinds:
        return RecoveryDecision('INCONCLUSIVE', 'STOP', strength=strength)
    if 'AMBIGUOUS_EVIDENCE' in kinds:
        return RecoveryDecision('INCONCLUSIVE', 'RECONCILE_ONLY', strength=strength)
    if acquired:
        return RecoveryDecision('ACQUIRED', 'RECOVER_ASSET', strength=strength)
    if bound:
        return RecoveryDecision('OUTPUT_BOUND', 'ACQUIRE_ONLY', strength=strength)
    if 'REMOTE_IDENTITY_OBSERVED' in kinds:
        return RecoveryDecision('OUTPUT_OBSERVED', 'BIND_EXACT_IDENTITY', strength=strength)
    if 'PROVIDER_ACCEPTANCE_OBSERVED' in kinds:
        return RecoveryDecision('DISPATCH_CONFIRMED', 'RECONCILE_ONLY', strength=strength)
    return RecoveryDecision('INCONCLUSIVE', 'RECONCILE_ONLY', strength=strength)


class EvidenceSink:
    def __init__(self, store, job_id):
        self.store, self.job_id = store, job_id

    def record(self, kind, data=None):
        self.store.record_dispatch_fact(self.job_id, kind, data or {})

    def facts(self):
        return self.store.read_dispatch_facts(self.job_id)

    def bindings(self):
        return self.store.read_output_bindings(self.job_id)
