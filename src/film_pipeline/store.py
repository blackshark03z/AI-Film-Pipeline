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
        return connection

    def initialize(self) -> None:
        connection = self._connect()
        try:
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
            """)
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
                    "SELECT generation_attempt_id, provider_id, dispatch_count FROM provider_jobs WHERE id = ?",
                    (job.provider_job_id,),
                ).fetchone()
                if existing is not None:
                    if existing[:2] != (job.generation_attempt_id, job.provider_id):
                        raise ValueError("provider job identity collision")
                    if existing[2] > job.dispatch_count:
                        raise ValueError("provider job dispatch count cannot regress")
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
            row = connection.execute("SELECT payload FROM provider_jobs WHERE id = ?", (provider_job_id,)).fetchone()
            if row is None:
                raise KeyError(provider_job_id)
            return ProviderJob.model_validate(json.loads(row[0]))
        finally:
            connection.close()

    def save_asset(self, asset) -> None:
        from .live_runtime import Asset

        if not isinstance(asset, Asset):
            raise TypeError("asset must be Asset")
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
