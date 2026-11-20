"""SQLite WAL atomic multi-account lease pool with IMMEDIATE transactions, lease tokens, cooldown, and quarantine."""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from film_pipeline.production.halt import is_halted, set_halt


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lease_key(generation_id: str, *, film_id: str = "", shot_version: int = 1) -> str:
    fid = film_id.strip()
    if fid:
        return f"{fid}:{generation_id}:v{int(shot_version)}"
    if int(shot_version) != 1:
        return f"{generation_id}:v{int(shot_version)}"
    return generation_id


class AccountLeasePool:
    """Atomic single-worktree lease manager for multi-account Flow / provider execution."""

    def __init__(
        self,
        db_path: Path,
        *,
        min_reserve_credits: float = 20.0,
        cooldown_s: float = 60.0,
    ) -> None:
        self.db_path = Path(db_path)
        self.min_reserve_credits = float(min_reserve_credits)
        self.cooldown_s = float(cooldown_s)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def _tx(self, conn: sqlite3.Connection):
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            if conn.in_transaction:
                conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

    def _init_db(self) -> None:
        with closing(self._connect()) as conn, self._tx(conn):
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    credits REAL NOT NULL,
                    status TEXT NOT NULL,
                    quarantined_reason TEXT NOT NULL DEFAULT '',
                    cooldown_until REAL NOT NULL DEFAULT 0.0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leases (
                    lease_key TEXT PRIMARY KEY,
                    film_id TEXT NOT NULL DEFAULT '',
                    generation_id TEXT NOT NULL,
                    shot_version INTEGER NOT NULL DEFAULT 1,
                    account_id TEXT NOT NULL,
                    lease_token TEXT NOT NULL DEFAULT '',
                    leased_at REAL NOT NULL,
                    state TEXT NOT NULL,
                    settled_credits REAL NOT NULL DEFAULT 0.0
                )
                """
            )
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(leases)").fetchall()}
            if "lease_key" not in cols:
                conn.execute(
                    """
                    CREATE TABLE leases_v2 (
                        lease_key TEXT PRIMARY KEY,
                        film_id TEXT NOT NULL DEFAULT '',
                        generation_id TEXT NOT NULL,
                        shot_version INTEGER NOT NULL DEFAULT 1,
                        account_id TEXT NOT NULL,
                        lease_token TEXT NOT NULL DEFAULT '',
                        leased_at REAL NOT NULL,
                        state TEXT NOT NULL,
                        settled_credits REAL NOT NULL DEFAULT 0.0
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO leases_v2 (lease_key, generation_id, account_id, leased_at, state)
                    SELECT generation_id, generation_id, account_id, leased_at, state FROM leases
                    """
                )
                conn.execute("DROP TABLE leases")
                conn.execute("ALTER TABLE leases_v2 RENAME TO leases")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_leases_active_account "
                "ON leases(account_id) WHERE state = 'ACTIVE'"
            )

    def register_account(self, account_id: str, credits: float, *, status: str = "ACTIVE") -> dict[str, Any]:
        aid = account_id.strip()
        if not aid:
            raise ValueError("account_id cannot be empty")
        now_iso = _iso_now()
        with closing(self._connect()) as conn, self._tx(conn):
            conn.execute(
                """
                INSERT INTO accounts (account_id, credits, status, quarantined_reason, cooldown_until, updated_at)
                VALUES (?, ?, ?, '', 0.0, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    credits = excluded.credits,
                    status = CASE WHEN accounts.status = 'COOLDOWN_QUARANTINE' THEN accounts.status ELSE excluded.status END,
                    updated_at = excluded.updated_at
                """,
                (aid, float(credits), status, now_iso),
            )
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (aid,)).fetchone()
            return dict(row)

    def acquire(
        self,
        generation_id: str,
        *,
        cost_credits: float = 6.0,
        now: float | None = None,
        film_id: str = "",
        shot_version: int = 1,
    ) -> dict[str, Any] | None:
        """Atomically lease ``generation_id`` to an eligible healthy account under BEGIN IMMEDIATE."""
        if is_halted():   # Owner rule: a halt (any account warning) stops ALL leasing until explicitly cleared
            return None
        ts = float(time.time() if now is None else now)
        key = _lease_key(generation_id, film_id=film_id, shot_version=shot_version)
        with closing(self._connect()) as conn, self._tx(conn):
            existing = conn.execute(
                "SELECT * FROM leases WHERE lease_key = ?",
                (key,),
            ).fetchone()
            if existing is not None:
                if existing["state"] == "ACTIVE":
                    return dict(existing)
                if existing["state"] == "QUARANTINED_PENDING_RECONCILE":
                    return None

            candidate = conn.execute(
                """
                SELECT a.* FROM accounts a
                WHERE a.status = 'ACTIVE'
                  AND (a.credits - ?) >= ?
                  AND a.cooldown_until <= ?
                  AND NOT EXISTS (
                      SELECT 1 FROM leases l WHERE l.account_id = a.account_id AND l.state = 'ACTIVE'
                  )
                ORDER BY a.credits DESC, a.account_id ASC
                LIMIT 1
                """,
                (float(cost_credits), self.min_reserve_credits, ts),
            ).fetchone()
            if candidate is None:
                return None

            token = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO leases (lease_key, film_id, generation_id, shot_version, account_id, lease_token, leased_at, state, settled_credits)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 0.0)
                ON CONFLICT(lease_key) DO UPDATE SET
                    film_id = excluded.film_id,
                    generation_id = excluded.generation_id,
                    shot_version = excluded.shot_version,
                    account_id = excluded.account_id,
                    lease_token = excluded.lease_token,
                    leased_at = excluded.leased_at,
                    state = 'ACTIVE',
                    settled_credits = 0.0
                """,
                (key, film_id.strip(), generation_id, int(shot_version), candidate["account_id"], token, ts),
            )
            lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            return dict(lease)

    def release(
        self,
        generation_id: str,
        *,
        credits_spent: float = 0.0,
        cooldown_s: float | None = None,
        now: float | None = None,
        lease_token: str | None = None,
        film_id: str = "",
        shot_version: int = 1,
    ) -> dict[str, Any]:
        ts = float(time.time() if now is None else now)
        cd = self.cooldown_s if cooldown_s is None else float(cooldown_s)
        key = _lease_key(generation_id, film_id=film_id, shot_version=shot_version)
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            if row is None:
                raise KeyError(f"no lease found for {generation_id!r}")
            if lease_token is not None and row["lease_token"] != lease_token:
                raise ValueError(f"lease_token mismatch for {generation_id!r}")
            if row["state"] == "RELEASED":
                return dict(row)
            aid = row["account_id"]
            spent = float(credits_spent)
            conn.execute(
                "UPDATE leases SET state = 'RELEASED', settled_credits = ? WHERE lease_key = ?",
                (spent, key),
            )
            conn.execute(
                """
                UPDATE accounts
                SET credits = MAX(0.0, credits - ?),
                    cooldown_until = ?,
                    updated_at = ?
                WHERE account_id = ?
                """,
                (spent, ts + cd, _iso_now(), aid),
            )
            updated = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            return dict(updated)

    def quarantine_account(
        self,
        account_id: str,
        reason: str,
        *,
        release_active_leases: bool = False,
    ) -> dict[str, Any]:
        """Put an account into COOLDOWN_QUARANTINE; retains unresolved leases unless proven NOT_SUBMITTED."""
        with closing(self._connect()) as conn, self._tx(conn):
            conn.execute(
                """
                UPDATE accounts
                SET status = 'COOLDOWN_QUARANTINE',
                    quarantined_reason = ?,
                    updated_at = ?
                WHERE account_id = ?
                """,
                (reason.strip() or "account warning", _iso_now(), account_id),
            )
            if release_active_leases:
                conn.execute(
                    "UPDATE leases SET state = 'RELEASED' "
                    "WHERE account_id = ? AND state IN ('ACTIVE', 'QUARANTINED_PENDING_RECONCILE')",
                    (account_id,),
                )
            else:
                conn.execute(
                    "UPDATE leases SET state = 'QUARANTINED_PENDING_RECONCILE' WHERE account_id = ? AND state = 'ACTIVE'",
                    (account_id,),
                )
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown account {account_id!r}")
            result = dict(row)
        set_halt(reason.strip() or "account warning", source="lease_pool", account=account_id)
        return result

    def snapshot(self) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY account_id").fetchall()]
            leases = [dict(r) for r in conn.execute("SELECT * FROM leases ORDER BY lease_key").fetchall()]
            return {
                "min_reserve_credits": self.min_reserve_credits,
                "cooldown_s": self.cooldown_s,
                "accounts": accounts,
                "leases": leases,
            }
