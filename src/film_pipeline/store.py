"""Small SQLite store for immutable shot/plan/route/attempt lineage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .core import (
    GenerationAttempt, PromptPlan, RoutingDecision, ShotSpec,
    canonical_json, sha256, validate_contract,
)


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def initialize(self) -> None:
        connection = self._connect()
        try:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name='provider_jobs'").fetchone():
                rows = connection.execute('SELECT payload FROM provider_jobs WHERE dispatch_count=1').fetchall()
                if any(json.loads(row[0]).get('dispatch_protocol', 'legacy-v1') == 'legacy-v1' for row in rows):
                    raise RuntimeError('LEGACY_HISTORY_READ_ONLY')
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS shot_specs (
                    hash TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prompt_plans (
                    hash TEXT PRIMARY KEY, shot_spec_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (shot_spec_hash) REFERENCES shot_specs(hash)
                );
                CREATE TABLE IF NOT EXISTS routing_decisions (
                    id TEXT PRIMARY KEY, prompt_plan_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (prompt_plan_hash) REFERENCES prompt_plans(hash)
                );
                CREATE TABLE IF NOT EXISTS generation_attempts (
                    id TEXT PRIMARY KEY, shot_spec_hash TEXT NOT NULL,
                    prompt_plan_hash TEXT NOT NULL, routing_decision_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (shot_spec_hash) REFERENCES shot_specs(hash),
                    FOREIGN KEY (prompt_plan_hash) REFERENCES prompt_plans(hash),
                    FOREIGN KEY (routing_decision_id) REFERENCES routing_decisions(id)
                );
                CREATE TABLE IF NOT EXISTS provider_jobs (
                    id TEXT PRIMARY KEY,
                    generation_attempt_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    dispatch_count INTEGER NOT NULL CHECK (dispatch_count IN (0, 1)),
                    payload TEXT NOT NULL,
                    FOREIGN KEY (generation_attempt_id) REFERENCES generation_attempts(id)
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    generation_attempt_id TEXT NOT NULL,
                    provider_job_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (generation_attempt_id) REFERENCES generation_attempts(id),
                    FOREIGN KEY (provider_job_id) REFERENCES provider_jobs(id)
                );
                CREATE TABLE IF NOT EXISTS dispatch_journal (
                    job_id TEXT NOT NULL REFERENCES provider_jobs(id), sequence INTEGER NOT NULL,
                    kind TEXT NOT NULL, subject TEXT NOT NULL, payload TEXT NOT NULL,
                    at TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY(job_id,sequence), UNIQUE(job_id,kind,subject)
                );
                CREATE TABLE IF NOT EXISTS output_bindings (
                    provider_id TEXT NOT NULL, project_binding_id TEXT NOT NULL, output_id TEXT NOT NULL,
                    job_id TEXT NOT NULL REFERENCES provider_jobs(id), payload TEXT NOT NULL,
                    PRIMARY KEY(provider_id,project_binding_id,output_id)
                );
                CREATE TABLE IF NOT EXISTS acquisition_intents (
                    job_id TEXT NOT NULL REFERENCES provider_jobs(id), output_id TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(job_id,output_id)
                );
                CREATE TABLE IF NOT EXISTS acquisition_receipts (
                    job_id TEXT NOT NULL REFERENCES provider_jobs(id), output_id TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(job_id,output_id)
                );
            """)
            for table in ('dispatch_journal', 'output_bindings', 'acquisition_intents', 'acquisition_receipts'):
                for action in ('UPDATE', 'DELETE'):
                    connection.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_immutable BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable dispatch evidence'); END")
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _insert_immutable(connection: sqlite3.Connection, table: str, key: str, payload: str, *extra: str) -> None:
        columns = {
            "shot_specs": ("hash", "payload"),
            "prompt_plans": ("hash", "shot_spec_hash", "payload"),
            "routing_decisions": ("id", "prompt_plan_hash", "payload"),
            "generation_attempts": ("id", "shot_spec_hash", "prompt_plan_hash", "routing_decision_id", "payload"),
        }[table]
        values = (key, *extra, payload)
        placeholders = ",".join("?" for _ in columns)
        connection.execute(f"INSERT OR IGNORE INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)
        stored = connection.execute(f"SELECT payload FROM {table} WHERE {columns[0]} = ?", (key,)).fetchone()
        if stored is None or stored[0] != payload:
            raise ValueError(f"immutable {table} identity collision: {key}")

    def save_path(self, shot: ShotSpec, plan: PromptPlan, route: RoutingDecision, attempt: GenerationAttempt) -> None:
        shot_hash, plan_hash = sha256(shot), sha256(plan)
        if (attempt.shot_spec_hash != shot_hash or attempt.prompt_plan_hash != plan_hash
                or attempt.routing_decision_id != route.routing_decision_id
                or attempt.provider_id != route.provider_id or plan.provider_id != route.provider_id
                or shot.shot_id != plan.shot_id or shot.shot_id != route.shot_id
                or attempt.shot_id != shot.shot_id or attempt.shot_spec_version != shot.spec_version):
            raise ValueError("path lineage mismatch")
        for name, item in (("shot_spec", shot), ("prompt_plan", plan), ("routing_decision", route), ("generation_attempt", attempt)):
            validate_contract(name, item.payload())
        connection = self._connect()
        try:
            with connection:
                self._insert_immutable(connection, "shot_specs", shot_hash, canonical_json(shot.payload()))
                self._insert_immutable(connection, "prompt_plans", plan_hash, canonical_json(plan.payload()), shot_hash)
                self._insert_immutable(connection, "routing_decisions", route.routing_decision_id, canonical_json(route.payload()), plan_hash)
                self._insert_immutable(connection, "generation_attempts", attempt.generation_attempt_id, canonical_json(attempt.payload()), shot_hash, plan_hash, route.routing_decision_id)
        finally:
            connection.close()

    def read_path(self, attempt_id: str) -> tuple[ShotSpec, PromptPlan, RoutingDecision, GenerationAttempt]:
        """Open a fresh handle and verify every persisted link before returning it."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT shot_spec_hash, prompt_plan_hash, routing_decision_id, payload FROM generation_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise KeyError(attempt_id)
            shot_hash, plan_hash, route_id, attempt_payload = row
            shot_row = connection.execute("SELECT payload FROM shot_specs WHERE hash = ?", (shot_hash,)).fetchone()
            plan_row = connection.execute("SELECT shot_spec_hash, payload FROM prompt_plans WHERE hash = ?", (plan_hash,)).fetchone()
            route_row = connection.execute("SELECT prompt_plan_hash, payload FROM routing_decisions WHERE id = ?", (route_id,)).fetchone()
            if shot_row is None or plan_row is None or route_row is None:
                raise ValueError("incomplete persisted lineage")
        finally:
            connection.close()
        shot = ShotSpec.model_validate(json.loads(shot_row[0]))
        plan = PromptPlan.model_validate(json.loads(plan_row[1]))
        route = RoutingDecision.model_validate(json.loads(route_row[1]))
        attempt = GenerationAttempt.model_validate(json.loads(attempt_payload))
        if (sha256(shot) != shot_hash or sha256(plan) != plan_hash
                or plan_row[0] != shot_hash or route_row[0] != plan_hash
                or route.routing_decision_id != route_id
                or attempt.generation_attempt_id != attempt_id
                or attempt.shot_spec_hash != shot_hash or attempt.prompt_plan_hash != plan_hash
                or attempt.routing_decision_id != route_id or attempt.provider_id != route.provider_id
                or shot.shot_id != plan.shot_id or shot.shot_id != attempt.shot_id):
            raise ValueError("persisted lineage integrity failure")
        return shot, plan, route, attempt

    # Runtime records are deliberately mutable: remote provider state changes as
    # it is reconciled.  Creative/planning records above remain immutable.
    def save_provider_job(self, job) -> None:
        from .live_runtime import ProviderJob

        if not isinstance(job, ProviderJob):
            raise TypeError("job must be ProviderJob")
        connection = self._connect()
        try:
            with connection:
                attempt = connection.execute(
                    "SELECT payload FROM generation_attempts WHERE id = ?",
                    (job.generation_attempt_id,),
                ).fetchone()
                if attempt is None or json.loads(attempt[0]).get("provider_id") != job.provider_id:
                    raise ValueError("provider job attempt lineage mismatch")
                existing = connection.execute(
                    "SELECT generation_attempt_id, provider_id, dispatch_count, payload FROM provider_jobs WHERE id = ?",
                    (job.provider_job_id,),
                ).fetchone()
                if existing is not None:
                    old = json.loads(existing[3])
                    if old.get('dispatch_protocol', 'legacy-v1') == 'legacy-v1' and existing[2] == 1:
                        raise RuntimeError('LEGACY_HISTORY_READ_ONLY')
                    if existing[:2] != (job.generation_attempt_id, job.provider_id):
                        raise ValueError("provider job identity collision")
                    if existing[2] > job.dispatch_count:
                        raise ValueError("provider job dispatch count cannot regress")
                    if existing[2] < job.dispatch_count:
                        raise ValueError('ATOMIC_RESERVATION_REQUIRED')
                    for field in ('project_binding_id', 'pre_dispatch_snapshot', 'dispatch_protocol'):
                        if old.get(field, 'legacy-v1' if field == 'dispatch_protocol' else None) != getattr(job, field):
                            raise ValueError('FROZEN_PROVIDER_INTENT_CHANGED')
                    for key in ('prompt', 'prompt_plan_hash', 'submission_prompt_hash', 'correlation_marker'):
                        if old['correlation_evidence'].get(key) != job.correlation_evidence.get(key):
                            raise ValueError('FROZEN_PROVIDER_INTENT_CHANGED')
                    if old.get('external_job_id') and old['external_job_id'] != job.external_job_id:
                        raise ValueError('EXTERNAL_IDENTITY_CHANGED')
                    if old.get('submission_state') == 'SUBMITTED' and job.submission_state != 'SUBMITTED':
                        raise ValueError('DISPATCH_EVIDENCE_CANNOT_REGRESS')
                elif job.dispatch_count:
                    raise ValueError('ATOMIC_RESERVATION_REQUIRED')
                connection.execute(
                    "INSERT INTO provider_jobs (id, generation_attempt_id, provider_id, dispatch_count, payload) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET dispatch_count=excluded.dispatch_count, payload=excluded.payload",
                    (job.provider_job_id, job.generation_attempt_id, job.provider_id,
                     job.dispatch_count, canonical_json(job.model_dump(mode="json"))),
                )
        finally:
            connection.close()

    def reserve_dispatch(self, provider_job_id: str):
        """Irreversibly consume the one-submit budget before calling transport.

        A crash between this commit and the browser action is intentionally
        uncertain.  Recovery reconciles this job and can never manufacture a
        second submit.
        """
        from .live_runtime import ProviderJob

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM provider_jobs WHERE id = ?", (provider_job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(provider_job_id)
            job = ProviderJob.model_validate(json.loads(row[0]))
            if job.dispatch_protocol == 'legacy-v1':
                raise RuntimeError('LEGACY_HISTORY_READ_ONLY')
            if job.dispatch_count == 1:
                raise RuntimeError("single dispatch budget already consumed")
            used = connection.execute(
                "SELECT COUNT(*) FROM provider_jobs WHERE dispatch_count = 1"
            ).fetchone()[0]
            if used:
                raise RuntimeError("single dispatch budget already consumed")
            reserved = job.model_copy(update={
                "dispatch_count": 1,
                "submission_state": "SUBMISSION_RESERVED",
                "status": "INCONCLUSIVE",
            })
            connection.execute(
                "UPDATE provider_jobs SET dispatch_count = 1, payload = ? WHERE id = ?",
                (canonical_json(reserved.model_dump(mode="json")), provider_job_id),
            )
            from .dispatch_evidence import append_fact, intent_hash
            append_fact(connection, provider_job_id, 'RESERVED', {'intent_hash': intent_hash(reserved)})
            connection.commit()
            return reserved
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def read_provider_job(self, provider_job_id: str):
        from .live_runtime import ProviderJob

        connection = self._connect()
        try:
            row = connection.execute("SELECT generation_attempt_id,provider_id,dispatch_count,payload FROM provider_jobs WHERE id = ?", (provider_job_id,)).fetchone()
            if row is None:
                raise KeyError(provider_job_id)
            job = ProviderJob.model_validate(json.loads(row[3]))
            if (job.provider_job_id != provider_job_id or row[:3] !=
                    (job.generation_attempt_id, job.provider_id, job.dispatch_count)):
                raise ValueError('PROVIDER_JOB_INTEGRITY_FAILURE')
            if job.dispatch_protocol != 'legacy-v1' and job.dispatch_count:
                from .dispatch_evidence import intent_hash
                facts = self.read_dispatch_facts(provider_job_id)
                if not facts or facts[0]['kind'] != 'RESERVED' or facts[0]['data']['intent_hash'] != intent_hash(job):
                    raise ValueError('FROZEN_PROVIDER_INTENT_INTEGRITY_FAILURE')
            return job
        finally:
            connection.close()

    def _writable_job(self, job_id):
        from .dispatch_evidence import PROTOCOL
        job = self.read_provider_job(job_id)
        if job.dispatch_protocol != PROTOCOL:
            raise RuntimeError('LEGACY_HISTORY_READ_ONLY')
        if job.dispatch_count != 1:
            raise RuntimeError('DISPATCH_NOT_RESERVED')
        return job

    def record_dispatch_fact(self, job_id, kind, data):
        from .dispatch_evidence import append_fact
        job = self._writable_job(job_id)
        if kind == 'PROMPT_VERIFIED' and data.get('prompt_sha256') != job.correlation_evidence.get('submission_prompt_hash'):
            raise ValueError('PROMPT_HASH_MISMATCH')
        if kind in {'PROVIDER_RESPONSE_OBSERVED', 'PROVIDER_ACCEPTANCE_OBSERVED'}:
            facts = self.read_dispatch_facts(job_id)
            request = next((f for f in facts if f['kind'] == 'GENERATE_REQUEST_OBSERVED'), None)
            if request is None or request['data']['request_hash'] != data.get('request_hash'):
                raise ValueError('RESPONSE_REQUEST_BINDING_MISMATCH')
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            append_fact(connection, job_id, kind, data)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def read_dispatch_facts(self, job_id):
        from .dispatch_evidence import read_facts
        connection = self._connect()
        try:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='dispatch_journal'").fetchone():
                return []
            return read_facts(connection, job_id)
        finally:
            connection.close()

    def bind_output(self, job_id, output_id):
        from .dispatch_evidence import append_fact, validate_fact
        job = self._writable_job(job_id)
        validate_fact('REMOTE_IDENTITY_OBSERVED', {'output_id': output_id, 'method': 'exact_attribution'})
        if output_id.startswith('response-tuple:'):
            from .providers.flow_response import _is_uuid
            parts = output_id.split(':')
            if len(parts) != 4 or not all(_is_uuid(part) for part in parts[1:]) or sha256(parts[2]) != job.project_binding_id:
                raise ValueError('OUTPUT_PROJECT_MISMATCH')
        if not any(f['kind'] == 'REMOTE_IDENTITY_OBSERVED' and f['data']['output_id'] == output_id
                   for f in self.read_dispatch_facts(job_id)):
            raise ValueError('OUTPUT_ATTRIBUTION_FACT_REQUIRED')
        plain = {'job_id': job_id, 'attempt_id': job.generation_attempt_id, 'provider_id': job.provider_id,
                 'project_binding_id': job.project_binding_id, 'output_id': output_id}
        binding = {**plain, 'binding_hash': sha256(plain)}
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT payload FROM output_bindings WHERE provider_id=? AND project_binding_id=? AND output_id=?',
                (job.provider_id, job.project_binding_id, output_id)).fetchone()
            payload = canonical_json(binding)
            if row and row[0] != payload:
                raise ValueError('OUTPUT_ALREADY_BOUND_TO_ANOTHER_ATTEMPT')
            connection.execute('INSERT OR IGNORE INTO output_bindings VALUES (?,?,?,?,?)',
                (job.provider_id, job.project_binding_id, output_id, job_id, payload))
            append_fact(connection, job_id, 'IDENTITY_BOUND', {'output_id': output_id, 'binding_hash': binding['binding_hash']})
            connection.commit()
            return binding
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def read_output_bindings(self, job_id):
        job = self.read_provider_job(job_id)
        connection = self._connect()
        try:
            rows = connection.execute('SELECT provider_id,project_binding_id,output_id,payload FROM output_bindings WHERE job_id=? ORDER BY output_id', (job_id,)).fetchall()
        finally:
            connection.close()
        result = []
        for provider, project, output, payload in rows:
            binding = json.loads(payload)
            plain = {k: v for k, v in binding.items() if k != 'binding_hash'}
            if (binding['binding_hash'] != sha256(plain) or binding.get('job_id') != job_id
                    or binding.get('attempt_id') != job.generation_attempt_id
                    or binding.get('provider_id') != provider or binding.get('project_binding_id') != project
                    or (provider, project, output) != (job.provider_id, job.project_binding_id, binding.get('output_id'))):
                raise ValueError('OUTPUT_BINDING_INTEGRITY_FAILURE')
            if not any(f['kind'] == 'IDENTITY_BOUND' and f['data'] == {'output_id': output, 'binding_hash': binding['binding_hash']}
                       for f in self.read_dispatch_facts(job_id)):
                raise ValueError('OUTPUT_BINDING_JOURNAL_MISMATCH')
            result.append(binding)
        return result

    def save_acquisition_record(self, job_id, output_id, data, *, completed=False):
        from .dispatch_evidence import append_fact
        self._writable_job(job_id)
        keys = {'binding_hash', 'final_path', 'staging_path', 'rendition'}
        if completed:
            keys |= {'sha256', 'file_size', 'mime_type', 'duration_s', 'width', 'height'}
        if set(data) != keys or data['rendition'] != 'official-720p':
            raise ValueError('INVALID_ACQUISITION_RECORD')
        if any(not isinstance(data[k], str) or '://' in data[k] or not Path(data[k]).is_absolute()
               for k in ('final_path', 'staging_path')):
            raise ValueError('INVALID_ACQUISITION_PATH')
        if completed:
            intent = self.read_acquisition_record(job_id, output_id)
            if intent is None or any(data[k] != v for k, v in intent.items()):
                raise ValueError('ACQUISITION_RECEIPT_INTENT_MISMATCH')
        bindings = self.read_output_bindings(job_id)
        binding = next((b for b in bindings if b['output_id'] == output_id), None)
        if binding is None or data.get('binding_hash') != binding['binding_hash']:
            raise ValueError('ACQUISITION_BINDING_MISMATCH')
        table = 'acquisition_receipts' if completed else 'acquisition_intents'
        payload = canonical_json(data)
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            existing = connection.execute(f'SELECT payload FROM {table} WHERE job_id=? AND output_id=?', (job_id, output_id)).fetchone()
            if existing and existing[0] != payload:
                raise ValueError('ACQUISITION_RECORD_CHANGED')
            connection.execute(f'INSERT OR IGNORE INTO {table} VALUES (?,?,?)', (job_id, output_id, payload))
            kind = 'DOWNLOAD_VALIDATED' if completed else 'DOWNLOAD_STARTED'
            fact = {'output_id': output_id, 'sha256': data['sha256'], 'receipt_hash': sha256(data)} if completed else {'output_id': output_id, 'intent_hash': sha256(data)}
            append_fact(connection, job_id, kind, fact)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def read_acquisition_record(self, job_id, output_id, *, completed=False):
        table = 'acquisition_receipts' if completed else 'acquisition_intents'
        connection = self._connect()
        try:
            row = connection.execute(f'SELECT payload FROM {table} WHERE job_id=? AND output_id=?', (job_id, output_id)).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        data = json.loads(row[0])
        kind, key = ('DOWNLOAD_VALIDATED', 'receipt_hash') if completed else ('DOWNLOAD_STARTED', 'intent_hash')
        fact = next((f for f in self.read_dispatch_facts(job_id) if f['kind'] == kind and f['data']['output_id'] == output_id), None)
        if fact is None or fact['data'][key] != sha256(data):
            raise ValueError('ACQUISITION_RECORD_INTEGRITY_FAILURE')
        return data

    def save_asset(self, asset) -> None:
        from .live_runtime import Asset

        if not isinstance(asset, Asset):
            raise TypeError("asset must be Asset")
        self._writable_job(asset.provider_job_id)
        binding = next((b for b in self.read_output_bindings(asset.provider_job_id)
                        if b['output_id'] == asset.provider_asset_id), None)
        receipt = self.read_acquisition_record(asset.provider_job_id, asset.provider_asset_id, completed=True)
        if (binding is None or receipt is None or asset.sha256 != receipt['sha256']
                or asset.uri_or_path != receipt['final_path'] or asset.file_size != receipt['file_size']
                or asset.rights_metadata != {'identity_binding': binding, 'acquisition_receipt': receipt}):
            raise ValueError('ASSET_ACQUISITION_LINEAGE_MISMATCH')
        connection = self._connect()
        try:
            with connection:
                job = connection.execute(
                    "SELECT generation_attempt_id FROM provider_jobs WHERE id = ?", (asset.provider_job_id,)
                ).fetchone()
                if job is None or job[0] != asset.source_attempt_id:
                    raise ValueError("asset provider job lineage mismatch")
                payload = canonical_json(asset.model_dump(mode="json"))
                connection.execute(
                    "INSERT OR IGNORE INTO assets (id, generation_attempt_id, provider_job_id, payload) VALUES (?, ?, ?, ?)",
                    (asset.asset_id, asset.source_attempt_id, asset.provider_job_id, payload),
                )
                stored = connection.execute("SELECT payload FROM assets WHERE id = ?", (asset.asset_id,)).fetchone()
                if stored is None or stored[0] != payload:
                    raise ValueError("immutable asset identity collision")
                from .dispatch_evidence import append_fact
                append_fact(connection, asset.provider_job_id, 'ASSET_PERSISTED',
                            {'output_id': asset.provider_asset_id, 'asset_id': asset.asset_id})
        finally:
            connection.close()

    def read_runtime_lineage(self, attempt_id: str, provider_job_id: str):
        from .live_runtime import Asset

        path = self.read_path(attempt_id)
        job = self.read_provider_job(provider_job_id)
        if job.generation_attempt_id != attempt_id:
            raise ValueError("provider job does not belong to attempt")
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT payload FROM assets WHERE provider_job_id = ? ORDER BY id", (provider_job_id,)
            ).fetchall()
        finally:
            connection.close()
        assets = tuple(Asset.model_validate(json.loads(row[0])) for row in rows)
        if any(asset.source_attempt_id != attempt_id for asset in assets):
            raise ValueError("asset does not belong to attempt")
        return (*path, job, assets)
