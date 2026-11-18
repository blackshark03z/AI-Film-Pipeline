"""SQLite WAL atomic multi-account lease pool with credit reserve, cooldown, and quarantine."""
from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level="IMMEDIATE")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    credits REAL NOT NULL,
                    status TEXT NOT NULL,
                    quarantined_reason TEXT NOT NULL DEFAULT '',
                    cooldown_until REAL NOT NULL DEFAULT 0.0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS leases (
                    generation_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    leased_at REAL NOT NULL,
                    state TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def register_account(self, account_id: str, credits: float, *, status: str = "ACTIVE") -> dict[str, Any]:
        aid = account_id.strip()
        if not aid:
            raise ValueError("account_id cannot be empty")
        now_iso = _iso_now()
        with closing(self._connect()) as conn:
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
            conn.commit()
            return dict(row)

    def acquire(self, generation_id: str, *, cost_credits: float = 6.0, now: float | None = None) -> dict[str, Any] | None:
        """Atomically lease ``generation_id`` to an eligible healthy account respecting reserve & cooldown."""
        ts = float(time.time() if now is None else now)
        with closing(self._connect()) as conn:
            existing = conn.execute(
                "SELECT * FROM leases WHERE generation_id = ? AND state = 'ACTIVE'",
                (generation_id,),
            ).fetchone()
            if existing is not None:
                return dict(existing)

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
                conn.rollback()
                return None

            conn.execute(
                """
                INSERT INTO leases (generation_id, account_id, leased_at, state)
                VALUES (?, ?, ?, 'ACTIVE')
                ON CONFLICT(generation_id) DO UPDATE SET
                    account_id = excluded.account_id,
                    leased_at = excluded.leased_at,
                    state = 'ACTIVE'
                """,
                (generation_id, candidate["account_id"], ts),
            )
            lease = conn.execute("SELECT * FROM leases WHERE generation_id = ?", (generation_id,)).fetchone()
            conn.commit()
            return dict(lease)

    def release(
        self,
        generation_id: str,
        *,
        credits_spent: float = 0.0,
        cooldown_s: float | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        ts = float(time.time() if now is None else now)
        cd = self.cooldown_s if cooldown_s is None else float(cooldown_s)
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM leases WHERE generation_id = ?", (generation_id,)).fetchone()
            if row is None:
                raise KeyError(f"no lease found for {generation_id!r}")
            aid = row["account_id"]
            conn.execute("UPDATE leases SET state = 'RELEASED' WHERE generation_id = ?", (generation_id,))
            conn.execute(
                """
                UPDATE accounts
                SET credits = MAX(0.0, credits - ?),
                    cooldown_until = ?,
                    updated_at = ?
                WHERE account_id = ?
                """,
                (float(credits_spent), ts + cd, _iso_now(), aid),
            )
            updated = conn.execute("SELECT * FROM leases WHERE generation_id = ?", (generation_id,)).fetchone()
            conn.commit()
            return dict(updated)

    def quarantine_account(self, account_id: str, reason: str, *, release_active_leases: bool = True) -> dict[str, Any]:
        """Put an account into COOLDOWN_QUARANTINE without halting healthy accounts."""
        with closing(self._connect()) as conn:
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
                    "UPDATE leases SET state = 'RELEASED' WHERE account_id = ? AND state = 'ACTIVE'",
                    (account_id,),
                )
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown account {account_id!r}")
            conn.commit()
            return dict(row)

    def snapshot(self) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY account_id").fetchall()]
            leases = [dict(r) for r in conn.execute("SELECT * FROM leases ORDER BY generation_id").fetchall()]
            conn.commit()
            return {
                "min_reserve_credits": self.min_reserve_credits,
                "cooldown_s": self.cooldown_s,
                "accounts": accounts,
                "leases": leases,
            }
