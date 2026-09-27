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
