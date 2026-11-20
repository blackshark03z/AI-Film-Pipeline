"""SQLite WAL atomic multi-account lease pool with IMMEDIATE transactions, lease tokens, holders, cooldown, and quarantine.

One machine-wide pool is the authority for which Flow account a send may use: ``default_db_path()`` is
``<state dir>/lease_pool.sqlite3`` (the same state dir as the production halt: ``$AFP_STATE_DIR`` else ``~/.afp``), so
every caller, process and film shares it. A lease belongs to one ``holder``: an ACTIVE lease is handed back only to the
holder that took it (idempotent for that holder), never to anyone else. ``release`` needs the lease token.

Lease states: ``ACTIVE`` (held), ``RELEASED`` (settled), ``QUARANTINED_PENDING_RECONCILE`` (uncertain: the send's outcome is
unknown or the account warned). An account with an ACTIVE or uncertain lease is never selected. An uncertain lease is
settled with ``settle`` once the send's receipt is resolved (``afp-film lease settle --film F --take TID``).
"""
from __future__ import annotations

import os
import socket
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from film_pipeline.production.halt import _BY_RE, is_halted, read_halt, set_halt, state_dir

DB_FILENAME = "lease_pool.sqlite3"
UNCERTAIN = "QUARANTINED_PENDING_RECONCILE"
_HELD = ("ACTIVE", UNCERTAIN)
_PROCESS_HOLDER: tuple[int, str] | None = None


def default_db_path() -> Path:
    """The machine-wide pool: ``<state dir>/lease_pool.sqlite3`` (``--db`` overrides it on the CLI)."""
    return state_dir() / DB_FILENAME


def new_holder() -> str:
    """A fresh holder id ``host:pid:uuid``: two callers never share one by accident."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"


def process_holder() -> str:
    """The default holder of this process (unique per process, regenerated after a fork)."""
    global _PROCESS_HOLDER
    if _PROCESS_HOLDER is None or _PROCESS_HOLDER[0] != os.getpid():
        _PROCESS_HOLDER = (os.getpid(), new_holder())
    return _PROCESS_HOLDER[1]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lease_key(generation_id: str, *, film_id: str = "", shot_version: int = 1) -> str:
    fid = film_id.strip()
    if fid:
        return f"{fid}:{generation_id}:v{int(shot_version)}"
    if int(shot_version) != 1:
        return f"{generation_id}:v{int(shot_version)}"
    return generation_id


def _norm_cdp(endpoint: str) -> str:
    from film_pipeline.production.runtime import normalize_cdp
    return normalize_cdp(endpoint) if endpoint.strip() else ""


class AccountLeasePool:
    """Atomic lease manager for multi-account Flow / provider execution, shared across processes and films."""

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        min_reserve_credits: float = 20.0,
        cooldown_s: float = 60.0,
        honor_halt: bool = True,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.min_reserve_credits = float(min_reserve_credits)
        self.cooldown_s = float(cooldown_s)
        self.honor_halt = honor_halt   # False only for a rehearsal's private pool (a mock send ignores the halt)
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
            # v3 (idempotent): lease holder + note; per-account Flow profile (CDP endpoint) and project
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(leases)").fetchall()}
            for col in ("holder", "note"):
                if col not in cols:
                    conn.execute(f"ALTER TABLE leases ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            acols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
            for col in ("cdp_endpoint", "project"):
                if col not in acols:
                    conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            conn.execute(   # who returned which quarantined account to service, and why (like the halt history)
                """
                CREATE TABLE IF NOT EXISTS account_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    by TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    prior_status TEXT NOT NULL DEFAULT '',
                    prior_reason TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_leases_active_account "
                "ON leases(account_id) WHERE state = 'ACTIVE'"
            )

    def register_account(
        self,
        account_id: str,
        credits: float,
        *,
        status: str = "ACTIVE",
        cdp_endpoint: str | None = None,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Add or update an account. ``cdp_endpoint`` / ``project`` (None = keep) name the Flow profile and project a
        lease on this account must use."""
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
            if cdp_endpoint is not None:
                conn.execute("UPDATE accounts SET cdp_endpoint = ? WHERE account_id = ?", (_norm_cdp(cdp_endpoint), aid))
            if project is not None:
                conn.execute("UPDATE accounts SET project = ? WHERE account_id = ?", (project.strip(), aid))
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (aid,)).fetchone()
            return dict(row)

    @staticmethod
    def _with_account(conn: sqlite3.Connection, lease: sqlite3.Row) -> dict[str, Any]:
        acct = conn.execute("SELECT cdp_endpoint, project FROM accounts WHERE account_id = ?",
                            (lease["account_id"],)).fetchone()
        return {**dict(lease), "cdp_endpoint": acct["cdp_endpoint"] if acct else "",
                "project": acct["project"] if acct else ""}

    def _unavailable(self, conn: sqlite3.Connection, cost: float, ts: float, account_id: str | None) -> str:
        """Why no account can be leased (the same rules as the candidate query)."""
        rows = conn.execute("SELECT * FROM accounts ORDER BY account_id").fetchall()
        if not rows:
            return f"no registered account in {self.db_path} (afp-film lease register --account ID --credits N)"
        if account_id:
            rows = [r for r in rows if r["account_id"] == account_id]
            if not rows:
                return f"pinned account {account_id} is not registered in {self.db_path}"
        why = []
        for r in rows:
            held = conn.execute(
                "SELECT lease_key, state FROM leases WHERE account_id = ? AND state IN (?, ?) LIMIT 1",
                (r["account_id"], *_HELD)).fetchone()
            if r["status"] != "ACTIVE":
                why.append(f"{r['account_id']} is {r['status']} ({r['quarantined_reason']})")
            elif held is not None:
                why.append(f"{r['account_id']} is busy (lease {held['lease_key']} {held['state']})")
            elif r["cooldown_until"] > ts:
                why.append(f"{r['account_id']} cools down for {r['cooldown_until'] - ts:.0f} s")
            elif r["credits"] - cost < self.min_reserve_credits:
                why.append(f"{r['account_id']} has {r['credits']:g} credits; needs {cost:g} + reserve "
                           f"{self.min_reserve_credits:g}")
        return ("pinned account " if account_id else "no eligible account: ") + "; ".join(why or ["none eligible"])

    def acquire_or_reason(
        self,
        generation_id: str,
        *,
        cost_credits: float = 6.0,
        now: float | None = None,
        film_id: str = "",
        shot_version: int = 1,
        holder: str | None = None,
        account_id: str | None = None,
        lease_key: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """``acquire`` plus, when it returns None, why (decided inside the same IMMEDIATE transaction)."""
        if self.honor_halt and is_halted():   # Owner rule: a halt stops ALL leasing until explicitly cleared
            return None, f"production halted: {(read_halt() or {}).get('reason', '')}"
        who = (holder or process_holder()).strip()
        pinned = (account_id or "").strip() or None
        ts = float(time.time() if now is None else now)
        key = lease_key or _lease_key(generation_id, film_id=film_id, shot_version=shot_version)
        with closing(self._connect()) as conn, self._tx(conn):
            existing = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            if existing is not None:
                if existing["state"] == "ACTIVE":
                    if existing["holder"] == who and (pinned is None or existing["account_id"] == pinned):
                        return self._with_account(conn, existing), ""
                    return None, f"lease {key} is held by another caller"
                if existing["state"] == UNCERTAIN:
                    return None, f"lease {key} is {UNCERTAIN}; settle it after reconcile (afp-film lease settle)"

            candidate = conn.execute(
                f"""
                SELECT a.* FROM accounts a
                WHERE a.status = 'ACTIVE'
                  AND (? IS NULL OR a.account_id = ?)
                  AND (a.credits - ?) >= ?
                  AND a.cooldown_until <= ?
                  AND NOT EXISTS (
                      SELECT 1 FROM leases l WHERE l.account_id = a.account_id AND l.state IN ('ACTIVE', '{UNCERTAIN}')
                  )
                ORDER BY a.credits DESC, a.account_id ASC
                LIMIT 1
                """,
                (pinned, pinned, float(cost_credits), self.min_reserve_credits, ts),
            ).fetchone()
            if candidate is None:
                return None, self._unavailable(conn, float(cost_credits), ts, pinned)

            token = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO leases (lease_key, film_id, generation_id, shot_version, account_id, lease_token, leased_at,
                                    state, settled_credits, holder, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 0.0, ?, '')
                ON CONFLICT(lease_key) DO UPDATE SET
                    film_id = excluded.film_id,
                    generation_id = excluded.generation_id,
                    shot_version = excluded.shot_version,
                    account_id = excluded.account_id,
                    lease_token = excluded.lease_token,
                    leased_at = excluded.leased_at,
                    state = 'ACTIVE',
                    settled_credits = 0.0,
                    holder = excluded.holder,
                    note = ''
                """,
                (key, film_id.strip(), generation_id, int(shot_version), candidate["account_id"], token, ts, who),
            )
            lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            return self._with_account(conn, lease), ""

    def acquire(self, generation_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Atomically lease ``generation_id`` (or ``lease_key``) to an eligible healthy account under BEGIN IMMEDIATE.

        An existing ACTIVE lease for the key is returned only to the same ``holder`` (default: this process); any other
        holder gets None. ``account_id`` pins the account. Keywords: see ``acquire_or_reason``."""
        return self.acquire_or_reason(generation_id, **kwargs)[0]

    def availability(self, *, cost_credits: float = 6.0, account_id: str | None = None,
                     now: float | None = None) -> tuple[bool, str]:
        """Read-only: would an account be leasable now (dry runs)? Takes no lease."""
        if self.honor_halt and is_halted():
            return False, f"production halted: {(read_halt() or {}).get('reason', '')}"
        ts = float(time.time() if now is None else now)
        pinned = (account_id or "").strip() or None
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"""
                SELECT 1 FROM accounts a
                WHERE a.status = 'ACTIVE' AND (? IS NULL OR a.account_id = ?) AND (a.credits - ?) >= ?
                  AND a.cooldown_until <= ?
                  AND NOT EXISTS (SELECT 1 FROM leases l WHERE l.account_id = a.account_id
                                  AND l.state IN ('ACTIVE', '{UNCERTAIN}'))
                LIMIT 1
                """,
                (pinned, pinned, float(cost_credits), self.min_reserve_credits, ts),
            ).fetchone()
            return (True, "") if row is not None else (False, self._unavailable(conn, float(cost_credits), ts, pinned))

    def _settle_row(self, conn: sqlite3.Connection, row: sqlite3.Row, spent: float, ts: float, cd: float,
                    note: str) -> dict[str, Any]:
        conn.execute(
            "UPDATE leases SET state = 'RELEASED', settled_credits = ?, note = ? WHERE lease_key = ?",
            (spent, note or row["note"], row["lease_key"]),
        )
        conn.execute(
            """
            UPDATE accounts
            SET credits = MAX(0.0, credits - ?),
                cooldown_until = ?,
                updated_at = ?
            WHERE account_id = ?
            """,
            (spent, ts + cd, _iso_now(), row["account_id"]),
        )
        return dict(conn.execute("SELECT * FROM leases WHERE lease_key = ?", (row["lease_key"],)).fetchone())

    def release(
        self,
        generation_id: str = "",
        *,
        credits_spent: float = 0.0,
        cooldown_s: float | None = None,
        now: float | None = None,
        lease_token: str | None = None,
        film_id: str = "",
        shot_version: int = 1,
        lease_key: str | None = None,
    ) -> dict[str, Any]:
        """Release a lease the caller holds: the matching ``lease_token`` is required (ValueError otherwise)."""
        ts = float(time.time() if now is None else now)
        cd = self.cooldown_s if cooldown_s is None else float(cooldown_s)
        key = lease_key or _lease_key(generation_id, film_id=film_id, shot_version=shot_version)
        if not lease_token:
            raise ValueError(f"lease_token is required to release {key!r} (an uncertain lease: lease settle)")
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            if row is None:
                raise KeyError(f"no lease found for {key!r}")
            if row["lease_token"] != lease_token:
                raise ValueError(f"lease_token mismatch for {key!r}")
            if row["state"] == "RELEASED":
                return dict(row)
            return self._settle_row(conn, row, float(credits_spent), ts, cd, "")

    def mark_uncertain(self, lease_key: str, *, lease_token: str, reason: str) -> dict[str, Any]:
        """The holder lost track of its send (crash, unknown outcome): keep the lease held as QUARANTINED_PENDING_RECONCILE
        so its account is not reused until ``settle``. The account itself stays ACTIVE and no halt is set."""
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
            if row is None:
                raise KeyError(f"no lease found for {lease_key!r}")
            if row["lease_token"] != lease_token:
                raise ValueError(f"lease_token mismatch for {lease_key!r}")
            if row["state"] == "ACTIVE":
                conn.execute("UPDATE leases SET state = ?, note = ? WHERE lease_key = ?",
                             (UNCERTAIN, reason.strip()[:300], lease_key))
            return dict(conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone())

    def settle(
        self,
        lease_key: str,
        *,
        credits_spent: float,
        note: str = "",
        cooldown_s: float | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Release a held (ACTIVE or uncertain) lease without its token. Only for the reconcile path: call it once the
        send's receipt is resolved (``production.leases.settle_take`` checks that)."""
        ts = float(time.time() if now is None else now)
        cd = self.cooldown_s if cooldown_s is None else float(cooldown_s)
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
            if row is None:
                raise KeyError(f"no lease found for {lease_key!r}")
            if row["state"] == "RELEASED":
                return dict(row)
            return self._settle_row(conn, row, float(credits_spent), ts, cd, note or "settled")

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

    def unquarantine_account(self, account_id: str, *, by: str, reason: str) -> dict[str, Any]:
        """Return a quarantined account to ACTIVE and log who did it (table ``account_history``). Refused while the
        production halt is set (clear it first: ``afp-film halt clear``) and for an account that is not quarantined.
        Its held leases are untouched: an uncertain one still needs ``lease settle`` after reconcile."""
        if not isinstance(by, str) or not _BY_RE.match(by):
            raise ValueError("unquarantine: 'by' must match ^(human|agent):[A-Za-z0-9_.-]+$")
        if not isinstance(reason, str) or len(reason.strip()) < 3:
            raise ValueError("unquarantine: reason must be at least 3 characters")
        if is_halted():
            raise RuntimeError(f"unquarantine refused: production is halted ({(read_halt() or {}).get('reason', '')}); "
                               f"clear the halt first (afp-film halt clear --by ... --reason ...)")
        aid = account_id.strip()
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (aid,)).fetchone()
            if row is None:
                raise KeyError(f"unknown account {aid!r}")
            if row["status"] != "COOLDOWN_QUARANTINE":
                raise ValueError(f"account {aid} is {row['status']}, not quarantined")
            at = _iso_now()
            conn.execute("UPDATE accounts SET status = 'ACTIVE', quarantined_reason = '', updated_at = ? WHERE account_id = ?",
                         (at, aid))
            conn.execute("INSERT INTO account_history (at, account_id, action, by, reason, prior_status, prior_reason) "
                         "VALUES (?, ?, 'unquarantine', ?, ?, ?, ?)",
                         (at, aid, by, reason.strip(), row["status"], row["quarantined_reason"]))
            return {"account_id": aid, "action": "unquarantine", "at": at, "by": by, "reason": reason.strip(),
                    "prior_status": row["status"], "prior_reason": row["quarantined_reason"]}

    def snapshot(self) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY account_id").fetchall()]
            leases = [{k: v for k, v in dict(r).items() if k != "lease_token"}   # a token is the holder's proof
                      for r in conn.execute("SELECT * FROM leases ORDER BY lease_key").fetchall()]
            return {
                "db": str(self.db_path),
                "min_reserve_credits": self.min_reserve_credits,
                "cooldown_s": self.cooldown_s,
                "accounts": accounts,
                "leases": leases,
            }
