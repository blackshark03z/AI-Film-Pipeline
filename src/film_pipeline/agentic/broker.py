"""Studio broker v2 (STUDIO_ARCHITECTURE.md §3, §5, §6, §9; milestone S1).

One machine-wide SQLite database, ``<state dir>/lease_pool.sqlite3`` (``$AFP_STATE_DIR`` else ``~/.afp``; the file of
the step-4 lease pool, migrated in place by ``PRAGMA user_version``), is the authority for:

* **accounts** of every provider: admin status, slots per job kind, epoch, quota source (a constant balance with an
  optional daily quota, or a *probed* ``weekly_remaining_pct``), re-login bookkeeping and the profile-ownership claim;
* **batch leases**: one exclusive lease per account (``leases``), holding 1..slots **children** (``lease_children``) of
  one film and one job kind, each with its own outcome. An admission without an account (an HTTP provider) is a lease
  with ``account_id = ''``: it holds reservations only;
* **reservations** (one per child, in the child's unit): reserved at admission, turned into a spend or a release when
  the child settles. Every cap sums them: per-account daily quota, per-film budget, per-provider daily cap and the
  machine-wide daily cap per unit across providers (F3). The day is the local date stored on the reservation.

Every state change is one short ``BEGIN IMMEDIATE`` transaction: a **leaf lock** (F2). Nothing else is acquired while
it is held but the halt-file lock (``production_halt.json.lock``, innermost): admission, the pre-Enter check and the
allocator claim/release take it inside their transaction, read every stop signal (``halt.stop_signals``: the AFP
halt, the Muse halt ``$MUSE_HALT_FILE``, ``halt_pending/`` markers) and
the allocator claim (``allocator_owner.json``) under it and hold it until their COMMIT; ``halt.set_halt`` takes the broker
lock, then the halt-file lock. Lock order: broker transaction -> halt-file lock; Muse takes the halt-file lock alone.
No provider I/O and no waiting inside.

Admission and the pre-Enter check refuse unless the allocator claim (``allocator_owner.json``) exists and names
``afp-broker`` (``allocator_claim`` writes it, idempotent; ``allocator_release`` removes it, only while no lease is
live and no child unresolved here).

Lease states: ``ACTIVE`` (held by its holder), ``QUARANTINED_PENDING_RECONCILE`` (HELD: a child is AMBIGUOUS or the
account warned; never released automatically) and ``RELEASED`` (every child final). Child phases: ``PREPARING`` (admitted,
Enter not reached: releasable as NOT_SENT), ``SUBMITTING`` (the pre-Enter check passed: uncertain until an outcome is
known), ``UNKNOWN`` (migrated from the step-4 pool: never released as unsent) and ``DONE``.

Displayed account states: FREE, BUSY, COOLDOWN, NEEDS_LOGIN, QUARANTINED, HELD, HALTED (``account_state``). The
stored admin ``status`` is ACTIVE, COOLDOWN_QUARANTINE (shown QUARANTINED), NEEDS_LOGIN or HALTED; the others derive
from leases, cooldown and the machine halt.

Secrets: the broker stores no cookie, password or token of any provider, and never lists browser profiles.
"""
from __future__ import annotations

import json
import math
import os
import socket
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from film_pipeline.production.halt import (OWNER, _BY_RE, halt_file_lock, read_owner, remove_owner_locked,
                                           set_halt, state_dir, stop_signals, write_owner_locked)

SCHEMA_VERSION = 5
DB_FILENAME = "lease_pool.sqlite3"
UNCERTAIN = "QUARANTINED_PENDING_RECONCILE"
_HELD = ("ACTIVE", UNCERTAIN)
UNITS = ("credits", "VND", "USD", "muse_requests")
JOB_KINDS = ("video", "stills")
DEFAULT_SLOTS = {"flow": {"video": 1, "stills": 1}, "muse": {"video": 6, "stills": 4}}
ADMIN_STATUSES = ("ACTIVE", "COOLDOWN_QUARANTINE", "NEEDS_LOGIN", "HALTED")
SHOWN_STATES = ("FREE", "BUSY", "COOLDOWN", "NEEDS_LOGIN", "QUARANTINED", "HELD", "HALTED")
WARNING_KINDS = ("CAPTCHA", "VERIFICATION", "UNUSUAL_ACTIVITY", "ACCOUNT_WARNING")
RELOGIN_INTERVAL_S = 2 * 3600.0
RELOGIN_MAX_FAILURES = 2
DEFAULT_PROBE_MAX_AGE_S = 6 * 3600.0
DEFAULT_RESERVE_PCT = 10.0
_PROCESS_HOLDER: tuple[int, str] | None = None


class NotSent(RuntimeError):
    """The pre-Enter (or pre-login) check lost the halt, the epoch or the lease: nothing was submitted."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}; nothing was submitted")
        self.code = code
        self.reason = reason


def valid_day(day: object) -> bool:
    """A real calendar day written ``YYYY-MM-DD`` (the form reservations store and caps query)."""
    if not isinstance(day, str) or len(day) != 10:
        return False
    try:
        return date.fromisoformat(day).isoformat() == day
    except ValueError:
        return False


def known_providers() -> frozenset[str]:
    """The providers spend can be recorded for: every provider of the capability registry, and Muse."""
    from film_pipeline.providers.capability import load_registry
    return frozenset({e.provider for e in load_registry().values()} | {"muse"})


def _check_legacy_row(r: Mapping[str, Any]) -> None:
    """A legacy row is written only with a known unit, provider and calendar day and finite amounts >= 0."""
    if r.get("unit") not in UNITS:
        raise ValueError(f"legacy row {r.get('key')!r}: unit {r.get('unit')!r} is not one of {UNITS}")
    if r.get("provider") not in known_providers():
        raise ValueError(f"legacy row {r.get('key')!r}: unknown provider {r.get('provider')!r}")
    if not valid_day(r.get("day")):
        raise ValueError(f"legacy row {r.get('key')!r}: day {r.get('day')!r} is not YYYY-MM-DD")
    for field_name in ("amount", "price"):
        if r.get(field_name) is not None:
            _check_spent(r[field_name])


def default_db_path() -> Path:
    """The machine-wide broker: ``<state dir>/lease_pool.sqlite3`` (``--db`` overrides it on the CLI)."""
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


def local_day(ts: float | None = None) -> str:
    """The local calendar date (the day a reservation counts against)."""
    return (date.today() if ts is None else datetime.fromtimestamp(ts).date()).isoformat()


def _norm_cdp(endpoint: str) -> str:
    from film_pipeline.production.runtime import normalize_cdp
    return normalize_cdp(endpoint) if endpoint.strip() else ""


def _cap_value(value: Any) -> float | None:
    """A configured cap: a number, or None / "unlimited" for no cap."""
    if value is None or (isinstance(value, str) and value.strip().lower() == "unlimited"):
        return None
    cap = float(value)
    return None if math.isinf(cap) else cap


def default_caps() -> tuple[dict[str, float | None], dict[str, dict[str, float | None]]]:
    """(machine daily caps per unit, provider daily caps per unit) from ``providers/routes.json``."""
    from film_pipeline.providers.route import route_defaults
    defaults = route_defaults()
    machine = {u: _cap_value(v) for u, v in defaults.daily_caps.items()}
    provider = {p: {u: _cap_value(v) for u, v in caps.items()} for p, caps in defaults.provider_daily_caps.items()}
    return machine, provider


@dataclass
class Child:
    """One job of a batch: ``child_key`` is unique in the batch; ``amount`` is its price in the batch unit (None: the
    route has no price and cannot be admitted); ``shot_key`` names its shot version (two takes of one shot version are
    never in one batch)."""

    child_key: str
    amount: float | None
    take_id: str = ""
    shot_key: str = ""


@dataclass
class AdmitRequest:
    lease_key: str
    children: list[Child]
    unit: str = "credits"
    provider: str | None = None          # None: any provider (the step-4 pool API)
    job_kind: str = "video"
    film_id: str = ""
    film_key: str = ""                   # per-film budget scope (default: film_id)
    generation_id: str = ""
    shot_version: int = 1
    holder: str | None = None
    account_id: str | None = None        # pin one account
    needs_account: bool = True           # False: an HTTP provider, reservations only
    epoch: int | None = None             # a lane's epoch: refused unless it is the account's current one
    film_cap: float | None = None        # None: not checked here; math.inf: unlimited
    film_baseline: float = 0.0           # this film's spend in ``unit`` known outside the broker (its ledger)
    # take id -> what film_baseline already counts for it in ``unit`` (0: known to the ledger, nothing verified);
    # a plain set gives no credit (fail closed)
    film_counted: Mapping[str, float] | frozenset[str] = field(default_factory=dict)
    legacy_root: str | None = None       # the films directory whose pre-S1 receipts must be imported first
    day: str | None = None               # local date (default: today)
    now: float | None = None



def _check_spent(spent: float) -> None:
    """A settlement amount is finite and >= 0 (a negative spend would release a reservation and restore capacity)."""
    if not math.isfinite(float(spent)) or float(spent) < 0:
        raise ValueError(f"spent must be a finite amount >= 0, got {spent!r}")

class Broker:
    """The machine broker (see the module docstring). ``honor_halt=False`` only for a rehearsal's private pool."""

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        min_reserve_credits: float = 20.0,
        cooldown_s: float = 60.0,
        honor_halt: bool = True,
        machine_caps: dict[str, Any] | None = None,
        provider_caps: dict[str, dict[str, Any]] | None = None,
        require_owner: bool = True,
    ) -> None:
        self.require_owner = require_owner   # False only for a private rehearsal pool (no real account)
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.min_reserve_credits = float(min_reserve_credits)
        self.cooldown_s = float(cooldown_s)
        self.honor_halt = honor_halt
        if machine_caps is None or provider_caps is None:
            dm, dp = default_caps()
            machine_caps = dm if machine_caps is None else machine_caps
            provider_caps = dp if provider_caps is None else provider_caps
        self.machine_caps = {u: _cap_value(v) for u, v in machine_caps.items()}
        self.provider_caps = {p: {u: _cap_value(v) for u, v in c.items()} for p, c in provider_caps.items()}
        self._init_db()

    # ---- connection / transaction (the leaf lock) -------------------------------------------------------------------
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

    @contextmanager
    def _tx_locked(self, conn: sqlite3.Connection):
        """``BEGIN IMMEDIATE``, then the halt-file lock, held until after COMMIT (or ROLLBACK): what is read under it
        (halt, Muse halt, allocator claim) cannot change before this transaction's writes are durable."""
        conn.execute("BEGIN IMMEDIATE")
        try:
            with halt_file_lock():
                try:
                    yield
                    if conn.in_transaction:
                        conn.execute("COMMIT")
                finally:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")

    @contextmanager
    def transaction(self):
        """One short broker transaction (tests and the halt use it as the broker lock)."""
        with closing(self._connect()) as conn, self._tx(conn):
            yield conn

    # ---- schema ---------------------------------------------------------------------------------------------------
    def _init_db(self) -> None:
        with closing(self._connect()) as conn, self._tx(conn):
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if version >= SCHEMA_VERSION:
                return
            if version < 2:
                self._schema_v1(conn)
                self._migrate_v2(conn)
            if version < 3:
                self._migrate_v3(conn)
            self._migrate_v4(conn)
            self._migrate_v5(conn)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _schema_v1(conn: sqlite3.Connection) -> None:
        """The step-4 pool, created or upgraded exactly as it was (v1 leases keyed by generation id, v3 columns)."""
        conn.execute("""CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY, credits REAL NOT NULL, status TEXT NOT NULL,
            quarantined_reason TEXT NOT NULL DEFAULT '', cooldown_until REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL)""")
        leases_v2 = """(lease_key TEXT PRIMARY KEY, film_id TEXT NOT NULL DEFAULT '', generation_id TEXT NOT NULL,
            shot_version INTEGER NOT NULL DEFAULT 1, account_id TEXT NOT NULL, lease_token TEXT NOT NULL DEFAULT '',
            leased_at REAL NOT NULL, state TEXT NOT NULL, settled_credits REAL NOT NULL DEFAULT 0.0)"""
        conn.execute("CREATE TABLE IF NOT EXISTS leases " + leases_v2)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(leases)").fetchall()}
        if "lease_key" not in cols:
            conn.execute("CREATE TABLE leases_v2 " + leases_v2)
            conn.execute("INSERT INTO leases_v2 (lease_key, generation_id, account_id, leased_at, state) "
                         "SELECT generation_id, generation_id, account_id, leased_at, state FROM leases")
            conn.execute("DROP TABLE leases")
            conn.execute("ALTER TABLE leases_v2 RENAME TO leases")
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(leases)").fetchall()}
        for col in ("holder", "note"):
            if col not in cols:
                conn.execute(f"ALTER TABLE leases ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        acols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
        for col in ("cdp_endpoint", "project"):
            if col not in acols:
                conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        conn.execute("""CREATE TABLE IF NOT EXISTS account_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, account_id TEXT NOT NULL, action TEXT NOT NULL,
            by TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '', prior_status TEXT NOT NULL DEFAULT '',
            prior_reason TEXT NOT NULL DEFAULT '')""")

    @staticmethod
    def _migrate_v2(conn: sqlite3.Connection) -> None:
        """Broker v2: provider, slots, epoch, quota source, re-login and profile claim on accounts; batch fields on
        leases; children and reservations. Every step-4 lease keeps its state: ACTIVE stays ACTIVE with one child of
        UNKNOWN phase (never released as unsent), uncertain stays held with one AMBIGUOUS child, RELEASED stays
        settled."""
        add_acct = {
            "provider": "TEXT NOT NULL DEFAULT 'flow'", "label": "TEXT NOT NULL DEFAULT ''",
            "slots": "TEXT NOT NULL DEFAULT ''", "epoch": "INTEGER NOT NULL DEFAULT 1",
            "quota_mode": "TEXT NOT NULL DEFAULT 'constant'", "quota_unit": "TEXT NOT NULL DEFAULT 'credits'",
            "daily_quota": "REAL", "weekly_remaining_pct": "REAL", "probed_at": "REAL",
            "probe_max_age_s": f"REAL NOT NULL DEFAULT {DEFAULT_PROBE_MAX_AGE_S}",
            "reserve_pct": f"REAL NOT NULL DEFAULT {DEFAULT_RESERVE_PCT}",
            "reprobe_requested": "INTEGER NOT NULL DEFAULT 0",
            "relogin_last_at": "REAL NOT NULL DEFAULT 0.0", "relogin_failures": "INTEGER NOT NULL DEFAULT 0",
            "relogin_pending": "INTEGER NOT NULL DEFAULT 0",
            "profile_claimant": "TEXT NOT NULL DEFAULT ''", "profile_claim_epoch": "INTEGER NOT NULL DEFAULT 0",
        }
        acols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
        for col, decl in add_acct.items():
            if col not in acols:
                conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} {decl}")
        add_lease = {"provider": "TEXT NOT NULL DEFAULT ''", "job_kind": "TEXT NOT NULL DEFAULT 'video'",
                     "epoch": "INTEGER NOT NULL DEFAULT 0", "day": "TEXT NOT NULL DEFAULT ''",
                     "film_key": "TEXT NOT NULL DEFAULT ''", "unit": "TEXT NOT NULL DEFAULT 'credits'"}
        lcols = {r["name"] for r in conn.execute("PRAGMA table_info(leases)").fetchall()}
        for col, decl in add_lease.items():
            if col not in lcols:
                conn.execute(f"ALTER TABLE leases ADD COLUMN {col} {decl}")
        conn.execute("""CREATE TABLE IF NOT EXISTS lease_children (
            id INTEGER PRIMARY KEY AUTOINCREMENT, lease_key TEXT NOT NULL, lease_token TEXT NOT NULL,
            child_key TEXT NOT NULL, take_id TEXT NOT NULL DEFAULT '', shot_key TEXT NOT NULL DEFAULT '',
            film_key TEXT NOT NULL DEFAULT '', phase TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT '',
            final INTEGER NOT NULL DEFAULT 0, spent REAL NOT NULL DEFAULT 0.0, note TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL, UNIQUE (lease_token, child_key))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, lease_key TEXT NOT NULL, lease_token TEXT NOT NULL,
            child_key TEXT NOT NULL, take_id TEXT NOT NULL DEFAULT '', account_id TEXT NOT NULL DEFAULT '',
            film_key TEXT NOT NULL DEFAULT '', provider TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL,
            amount REAL NOT NULL, spent REAL NOT NULL DEFAULT 0.0, day TEXT NOT NULL, state TEXT NOT NULL,
            created_at REAL NOT NULL, settled_at REAL NOT NULL DEFAULT 0.0,
            price_known INTEGER NOT NULL DEFAULT 1, UNIQUE (lease_token, child_key))""")
        # spend sent before S1 (receipts without ``broker``), imported once per films directory (``import_legacy``):
        # admission refuses until the importing caller's directory is recorded here
        conn.execute("""CREATE TABLE IF NOT EXISTS legacy_imports (
            root TEXT PRIMARY KEY, imported_at TEXT NOT NULL, receipts INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_res_day ON reservations(day, unit, state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_res_film ON reservations(film_key, unit, state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_children_lease ON lease_children(lease_key, lease_token)")
        # one exclusive lease per account; an account-less admission (HTTP provider) is not an account lease
        conn.execute("DROP INDEX IF EXISTS idx_leases_active_account")
        conn.execute("CREATE UNIQUE INDEX idx_leases_active_account ON leases(account_id) "
                     "WHERE state = 'ACTIVE' AND account_id != ''")
        at = _iso_now()
        for lease in conn.execute("SELECT * FROM leases").fetchall():
            token = lease["lease_token"]
            if conn.execute("SELECT 1 FROM lease_children WHERE lease_key = ? AND lease_token = ?",
                            (lease["lease_key"], token)).fetchone():
                continue
            state = lease["state"]
            if state == "RELEASED":
                phase, outcome, final, spent = "DONE", "SETTLED", 1, float(lease["settled_credits"] or 0.0)
            elif state == UNCERTAIN:
                phase, outcome, final, spent = "UNKNOWN", "AMBIGUOUS", 0, 0.0
            else:   # ACTIVE (or an unknown legacy state): held by its holder, phase unknown
                phase, outcome, final, spent = "UNKNOWN", "", 0, 0.0
            conn.execute("INSERT INTO lease_children (lease_key, lease_token, child_key, take_id, film_key, phase, "
                         "outcome, final, spent, note, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (lease["lease_key"], token, lease["lease_key"], lease["generation_id"], lease["film_id"],
                          phase, outcome, final, spent, "migrated from the step-4 pool", at))
            day = local_day(float(lease["leased_at"] or 0.0) or None)
            conn.execute("INSERT INTO reservations (lease_key, lease_token, child_key, take_id, account_id, film_key, "
                         "provider, unit, amount, spent, day, state, created_at, settled_at, price_known) "
                         "VALUES (?, ?, ?, ?, ?, ?, 'flow', 'credits', 0.0, ?, ?, ?, ?, ?, ?)",
                         (lease["lease_key"], token, lease["lease_key"], lease["generation_id"], lease["account_id"],
                          lease["film_id"], spent, day, "SPENT" if (final and spent) else "RELEASED" if final
                          else "RESERVED", float(lease["leased_at"] or 0.0), 0.0, 1 if final else 0))
            conn.execute("UPDATE leases SET provider = 'flow', day = ?, film_key = film_id WHERE lease_key = ?",
                         (day, lease["lease_key"]))

    @staticmethod
    def _migrate_v3(conn: sqlite3.Connection) -> None:
        """Broker v3: pre-S1 receipt evidence that could not be read. ``import_legacy`` records each such receipt in
        ``legacy_unresolved`` and leaves its films directory's import incomplete (``legacy_imports.complete`` 0);
        capped admission is refused until an operator resolves it (``resolve_legacy``, who and why recorded)."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(legacy_imports)").fetchall()}
        if "complete" not in cols:
            conn.execute("ALTER TABLE legacy_imports ADD COLUMN complete INTEGER NOT NULL DEFAULT 1")
        conn.execute("""CREATE TABLE IF NOT EXISTS legacy_unresolved (
            root TEXT NOT NULL, key TEXT NOT NULL, path TEXT NOT NULL DEFAULT '', problem TEXT NOT NULL,
            sha256 TEXT NOT NULL DEFAULT '', found_at TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '',
            resolved_by TEXT NOT NULL DEFAULT '', resolved_reason TEXT NOT NULL DEFAULT '',
            resolved_amount REAL NOT NULL DEFAULT 0.0, resolved_unit TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (root, key))""")

    @staticmethod
    def _migrate_v4(conn: sqlite3.Connection) -> None:
        """Broker v4: an unreadable receipt keeps the film scope of its package (``film.json``), so its resolved
        charge counts against that film's budget."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(legacy_unresolved)").fetchall()}
        if "film_key" not in cols:
            conn.execute("ALTER TABLE legacy_unresolved ADD COLUMN film_key TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _migrate_v5(conn: sqlite3.Connection) -> None:
        """Broker v5: a child that passed the pre-Enter check is bound to the lane incarnation that asked (only that
        incarnation may report ENTER_NOT_ISSUED), and every check / ENTER_NOT_ISSUED decision is audited."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(lease_children)").fetchall()}
        if "incarnation" not in cols:
            conn.execute("ALTER TABLE lease_children ADD COLUMN incarnation TEXT NOT NULL DEFAULT ''")
        conn.execute("""CREATE TABLE IF NOT EXISTS child_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, lease_key TEXT NOT NULL, child_key TEXT NOT NULL,
            action TEXT NOT NULL, incarnation TEXT NOT NULL DEFAULT '', epoch INTEGER, reason TEXT NOT NULL DEFAULT '')""")

    @staticmethod
    def _audit(conn: sqlite3.Connection, lease_key: str, child_key: str, action: str, *, incarnation: str = "",
               epoch: int | None = None, reason: str = "") -> None:
        conn.execute("INSERT INTO child_audit (at, lease_key, child_key, action, incarnation, epoch, reason) VALUES "
                     "(?, ?, ?, ?, ?, ?, ?)", (_iso_now(), lease_key, child_key, action, incarnation, epoch,
                                               reason[:300]))

    # ---- accounts -------------------------------------------------------------------------------------------------
    def register_account(
        self,
        account_id: str,
        credits: float | None = None,
        *,
        status: str = "ACTIVE",
        provider: str | None = None,
        label: str | None = None,
        slots: dict[str, int] | None = None,
        quota_mode: str | None = None,
        quota_unit: str | None = None,
        daily_quota: float | None = None,
        probe_max_age_s: float | None = None,
        reserve_pct: float | None = None,
        cdp_endpoint: str | None = None,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Add or update an account (None = keep the stored value). A quarantined account keeps its status (only
        ``unquarantine`` / ``set_state`` returns it)."""
        aid = account_id.strip()
        if not aid:
            raise ValueError("account_id cannot be empty")
        if status not in ADMIN_STATUSES:
            raise ValueError(f"status must be one of {ADMIN_STATUSES}")
        if quota_mode is not None and quota_mode not in ("constant", "probed"):
            raise ValueError("quota_mode must be constant or probed")
        if quota_unit is not None and quota_unit not in UNITS:
            raise ValueError(f"quota_unit must be one of {UNITS}")
        if slots is not None:
            bad = [k for k, v in slots.items() if k not in JOB_KINDS or int(v) < 1]
            if bad:
                raise ValueError(f"slots: job kinds are {JOB_KINDS}, each at least 1 ({bad})")
        now_iso = _iso_now()
        with closing(self._connect()) as conn, self._tx(conn):
            exists = conn.execute("SELECT 1 FROM accounts WHERE account_id = ?", (aid,)).fetchone()
            if exists is None:
                conn.execute("INSERT INTO accounts (account_id, credits, status, updated_at, provider) "
                             "VALUES (?, ?, ?, ?, ?)", (aid, float(credits or 0.0), status, now_iso,
                                                         (provider or "flow").strip()))
            else:
                conn.execute("UPDATE accounts SET status = CASE WHEN status IN ('COOLDOWN_QUARANTINE', 'NEEDS_LOGIN', "
                             "'HALTED') THEN status ELSE ? END, updated_at = ? WHERE account_id = ?",
                             (status, now_iso, aid))
            updates: dict[str, Any] = {
                "credits": None if credits is None else float(credits),
                "provider": None if provider is None or exists is None else provider.strip(),
                "label": None if label is None else label.strip(),
                "slots": None if slots is None else json.dumps({k: int(v) for k, v in slots.items()}, sort_keys=True),
                "quota_mode": quota_mode, "quota_unit": quota_unit,
                "daily_quota": daily_quota, "probe_max_age_s": probe_max_age_s, "reserve_pct": reserve_pct,
                "cdp_endpoint": None if cdp_endpoint is None else _norm_cdp(cdp_endpoint),
                "project": None if project is None else project.strip(),
            }
            for col, value in updates.items():
                if value is not None:
                    conn.execute(f"UPDATE accounts SET {col} = ? WHERE account_id = ?", (value, aid))
            if quota_mode == "probed" and quota_unit is None:
                conn.execute("UPDATE accounts SET quota_unit = 'muse_requests' WHERE account_id = ? "
                             "AND quota_unit = 'credits'", (aid,))
            return dict(conn.execute("SELECT * FROM accounts WHERE account_id = ?", (aid,)).fetchone())

    @staticmethod
    def _slots(acct: sqlite3.Row | dict[str, Any]) -> dict[str, int]:
        own = json.loads(acct["slots"]) if acct["slots"] else {}
        return {**DEFAULT_SLOTS.get(acct["provider"], {"video": 1, "stills": 1}), **own}

    def record_probe(self, account_id: str, weekly_remaining_pct: float, *, probed_at: float | None = None) -> dict:
        """A lane's quota probe (Muse: ``weekly_remaining_pct`` from the Settings page). Clears a re-probe request."""
        pct = float(weekly_remaining_pct)
        if not 0.0 <= pct <= 100.0:
            raise ValueError("weekly_remaining_pct must be within 0..100")
        ts = float(time.time() if probed_at is None else probed_at)
        with closing(self._connect()) as conn, self._tx(conn):
            if conn.execute("UPDATE accounts SET weekly_remaining_pct = ?, probed_at = ?, reprobe_requested = 0, "
                            "updated_at = ? WHERE account_id = ?", (pct, ts, _iso_now(), account_id)).rowcount == 0:
                raise KeyError(f"unknown account {account_id!r}")
            return dict(conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone())

    def bump_epoch(self, account_id: str | None = None) -> dict[str, int]:
        """Fence old lanes (F1): +1 on one account's epoch, or on every account (daemon start). A lease admitted under
        an older epoch fails its pre-Enter check (NOT_SENT); a profile claim of an older epoch is void."""
        with closing(self._connect()) as conn, self._tx(conn):
            if account_id is None:
                conn.execute("UPDATE accounts SET epoch = epoch + 1, updated_at = ?", (_iso_now(),))
            elif conn.execute("UPDATE accounts SET epoch = epoch + 1, updated_at = ? WHERE account_id = ?",
                              (_iso_now(), account_id)).rowcount == 0:
                raise KeyError(f"unknown account {account_id!r}")
            return {r["account_id"]: int(r["epoch"]) for r in conn.execute("SELECT account_id, epoch FROM accounts")}

    def set_state(self, account_id: str, state: str, *, by: str, reason: str) -> dict[str, Any]:
        """Admin: set an account's stored status (FREE/ACTIVE, QUARANTINED, NEEDS_LOGIN, HALTED), logged in
        ``account_history``. Leaving QUARANTINED needs the production halt cleared; leaving NEEDS_LOGIN resets the
        re-login failure count (the Owner refreshed the login)."""
        if not isinstance(by, str) or not _BY_RE.match(by):
            raise ValueError("set_state: 'by' must match ^(human|agent):[A-Za-z0-9_.-]+$")
        if not isinstance(reason, str) or len(reason.strip()) < 3:
            raise ValueError("set_state: reason must be at least 3 characters")
        target = {"FREE": "ACTIVE", "QUARANTINED": "COOLDOWN_QUARANTINE"}.get(state.upper(), state.upper())
        if target not in ADMIN_STATUSES:
            raise ValueError(f"set_state: state must be FREE, QUARANTINED, NEEDS_LOGIN or HALTED (BUSY, COOLDOWN and "
                             f"HELD follow from leases), not {state!r}")
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown account {account_id!r}")
            if row["status"] == "COOLDOWN_QUARANTINE" and target != "COOLDOWN_QUARANTINE" and self._halted():
                raise RuntimeError("set_state refused: production is halted; clear the halt first "
                                   "(afp-film halt clear --by ... --reason ...)")
            at = _iso_now()
            conn.execute("UPDATE accounts SET status = ?, quarantined_reason = ?, updated_at = ?, relogin_failures = "
                         "CASE WHEN ? = 'NEEDS_LOGIN' THEN relogin_failures ELSE 0 END WHERE account_id = ?",
                         (target, reason.strip() if target != "ACTIVE" else "", at, target, account_id))
            conn.execute("INSERT INTO account_history (at, account_id, action, by, reason, prior_status, prior_reason) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (at, account_id, f"set_state:{target}", by, reason.strip(),
                                                          row["status"], row["quarantined_reason"]))
            return dict(conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone())

    # ---- halt -----------------------------------------------------------------------------------------------------
    def _stop_refusal(self) -> tuple[str, str]:
        """``(code, reason)`` of the first stop signal (``halt.stop_signals``: the AFP halt, the Muse halt, a pending
        halt marker; unreadable => refused), ``("", "")`` when none. Read under
        the halt-file lock where it decides (admission, the pre-Enter check)."""
        return stop_signals() if self.honor_halt else ("", "")

    def _halted(self) -> bool:
        return bool(self._stop_refusal()[0])

    def _halt_reason(self) -> str:
        return self._stop_refusal()[1]

    def _owner_refusal(self) -> tuple[str, str]:
        """``(code, reason)`` unless the allocator claim names ``afp-broker`` (read under the halt-file lock)."""
        if not self.require_owner:
            return "", ""
        claim = read_owner()
        if claim["problem"]:
            return "ALLOCATOR_UNKNOWN", (f"the allocator claim is {claim['problem']} (allocator_owner.json in the "
                                         f"state dir): nothing is allocated"
                                         + ("; claim it: afp-film broker allocator-claim"
                                            if claim["problem"] == "absent" else "; repair it by hand"))
        if claim["owner"] != OWNER:
            return "ALLOCATOR_NOT_OWNED", f"the allocator claim names {claim['owner']!r}, not {OWNER}: nothing is " \
                                          f"allocated"
        return "", ""

    # ---- usage ----------------------------------------------------------------------------------------------------
    @staticmethod
    def _usage(conn: sqlite3.Connection, where: str, args: Iterable[Any]) -> float:
        row = conn.execute("SELECT COALESCE(SUM(CASE WHEN state = 'RESERVED' THEN amount WHEN state = 'SPENT' "
                           f"THEN spent ELSE 0 END), 0) FROM reservations WHERE {where}", tuple(args)).fetchone()
        return float(row[0] or 0.0)

    def daily_usage(self, unit: str, day: str | None = None, *, provider: str | None = None) -> float:
        """Reserved + spent in ``unit`` on ``day`` (local date), machine-wide or for one provider. Read-only."""
        d = day or local_day()
        with closing(self._connect()) as conn:
            if provider is None:
                return self._usage(conn, "unit = ? AND day = ?", (unit, d))
            return self._usage(conn, "unit = ? AND day = ? AND provider = ?", (unit, d, provider))

    # ---- eligibility ----------------------------------------------------------------------------------------------
    def _account_refusal(self, conn: sqlite3.Connection, acct: sqlite3.Row, req: AdmitRequest, total: float,
                         ts: float, day: str) -> tuple[str, bool]:
        """Why ``acct`` cannot take this batch ('' = it can), and whether a re-probe is requested."""
        aid = acct["account_id"]
        if acct["status"] != "ACTIVE":
            return f"{aid} is {acct['status']} ({acct['quarantined_reason']})", False
        held = conn.execute("SELECT lease_key, state FROM leases WHERE account_id = ? AND state IN (?, ?) LIMIT 1",
                            (aid, *_HELD)).fetchone()
        if held is not None:
            return f"{aid} is busy (lease {held['lease_key']} {held['state']})", False
        if acct["cooldown_until"] > ts:
            return f"{aid} cools down for {acct['cooldown_until'] - ts:.0f} s", False
        slots = self._slots(acct).get(req.job_kind, 0)
        if len(req.children) > slots:
            return f"{aid} has {slots} {req.job_kind} slot(s); the batch has {len(req.children)}", False
        if acct["quota_mode"] == "probed":
            pct, at = acct["weekly_remaining_pct"], acct["probed_at"]
            if pct is None or at is None or ts - float(at) > float(acct["probe_max_age_s"]):
                age = "never probed" if at is None else f"probe is {ts - float(at):.0f} s old"
                return f"{aid}: {age} (max {acct['probe_max_age_s']:g} s); re-probe requested", True
            if float(pct) < float(acct["reserve_pct"]):
                return f"{aid}: weekly quota {float(pct):g}% is below the reserve {acct['reserve_pct']:g}%; " \
                       f"re-probe requested", True
        else:
            if acct["quota_unit"] != req.unit:
                return f"{aid} keeps its quota in {acct['quota_unit']}, not {req.unit}", False
            if acct["credits"] - total < self.min_reserve_credits:
                unit = "credits" if req.unit == "credits" else req.unit
                return f"{aid} has {acct['credits']:g} {unit}; needs {total:g} + reserve " \
                       f"{self.min_reserve_credits:g}", False
            if acct["daily_quota"] is not None:
                used = self._usage(conn, "account_id = ? AND unit = ? AND day = ?", (aid, req.unit, day))
                if used + total > float(acct["daily_quota"]):
                    return f"{aid} daily quota: {used:g} used on {day} + {total:g} > {acct['daily_quota']:g}", False
        return "", False

    def _cap_refusal(self, conn: sqlite3.Connection, req: AdmitRequest, total: float, day: str) -> tuple[str, str]:
        """The caps that do not depend on the account: the film budget and the machine daily cap per unit (F3). A
        reservation is credited only with what the ledger baseline verifiably counts for it in the same unit
        (``film_counted[take_id]``), and only when it is the only live reservation of that take id in the film scope
        (admission keeps it so under a film budget): it adds ``max(0, its amount - that credit)``. Rows that share a
        take id are ambiguous (which one the ledger covers is unknown) and are counted in full; so is a take the
        ledger knows with no verified amount (an unreadable receipt, a fallback price in another unit). An overcount
        refuses, never overspends."""
        unit = req.unit
        in_unit = "" if unit == "credits" else f" {unit}"
        if req.film_cap is not None and not math.isinf(req.film_cap):
            rows = conn.execute("SELECT take_id, state, amount, spent FROM reservations WHERE film_key = ? AND unit = ? "
                                "AND state IN ('RESERVED', 'SPENT')", (req.film_key or req.film_id, unit)).fetchall()
            per_take: dict[str, int] = {}
            for r in rows:
                if r["take_id"]:
                    per_take[r["take_id"]] = per_take.get(r["take_id"], 0) + 1
            credit = req.film_counted if isinstance(req.film_counted, Mapping) else {}
            extra = 0.0
            for r in rows:
                own = float(r["amount"] if r["state"] == "RESERVED" else r["spent"])
                if r["take_id"] and per_take.get(r["take_id"]) == 1:
                    own = max(0.0, own - float(credit.get(r["take_id"]) or 0.0))
                extra += own
            spent = float(req.film_baseline) + extra
            if spent + total > float(req.film_cap):
                return "BUDGET_EXCEEDED", f"{spent:g} spent + {total:g} > cap {req.film_cap:g}{in_unit}"
        mcap = self.machine_caps.get(unit)
        if mcap is not None:
            used = self._usage(conn, "unit = ? AND day = ?", (unit, day))
            if used + total > mcap:
                return "BUDGET_DAILY_EXCEEDED", f"{used:g} spent on {day} + {total:g} > daily cap {mcap:g}{in_unit}"
        return "", ""

    def _provider_cap_refusal(self, conn: sqlite3.Connection, provider: str, unit: str, total: float,
                              day: str) -> tuple[str, str]:
        """The provider's daily cap, for the provider the admission resolved (the request's, or the account's)."""
        pcap = self.provider_caps.get(provider, {}).get(unit) if provider else None
        if pcap is None:
            return "", ""
        used = self._usage(conn, "unit = ? AND day = ? AND provider = ?", (unit, day, provider))
        if used + total > pcap:
            in_unit = "" if unit == "credits" else f" {unit}"
            return "PROVIDER_DAILY_EXCEEDED", f"{provider}: {used:g} spent on {day} + {total:g} > daily cap " \
                                              f"{pcap:g}{in_unit}"
        return "", ""

    def _legacy_refusal(self, conn: sqlite3.Connection, req: AdmitRequest, provider: str) -> tuple[str, str]:
        """Spend sent before S1 must be in the broker before anything is admitted against a daily cap: the caller's
        films directory must be imported (``import_legacy``); a caller without one is refused while any daily cap
        applies and no directory was ever imported. While any pre-S1 receipt on this machine could not be read
        (``legacy_unresolved``), a capped admission is refused: its spend is unknown. Returns ``(code, reason)``,
        ``("", "")`` when admission may go on."""
        capped = self.machine_caps.get(req.unit) is not None or any(
            caps.get(req.unit) is not None for p, caps in self.provider_caps.items() if not provider or p == provider)
        if capped or (req.film_cap is not None and not math.isinf(req.film_cap)):
            bad = conn.execute("SELECT root, key, problem, (SELECT COUNT(*) FROM legacy_unresolved WHERE resolved_at "
                               "= '') AS n FROM legacy_unresolved WHERE resolved_at = '' ORDER BY root, key "
                               "LIMIT 1").fetchone()
            if bad is not None:
                return "LEGACY_RECEIPT_UNREADABLE", (
                    f"{bad['n']} pre-S1 receipt(s) could not be read, so their spend is unknown; first {bad['key']} "
                    f"({bad['problem']}) under {bad['root']}: repair the file and import again (afp-film broker "
                    f"import-legacy --films-dir D), or record what it charged (afp-film broker import-resolve "
                    f"--films-dir D --key K --by human:<id> --reason R [--amount A --unit U --day YYYY-MM-DD "
                    f"--provider P])")
            # a step-4 send still open at migration counts at its receipt's price, which only the import knows
            unpriced = conn.execute("SELECT lease_key FROM reservations WHERE state = 'RESERVED' AND price_known = 0 "
                                    "ORDER BY id LIMIT 1").fetchone()
            if unpriced is not None:
                return "LEGACY_IMPORT_PENDING", (
                    f"the open step-4 send {unpriced['lease_key']} has no known price: import its films directory "
                    f"(afp-film broker import-legacy --films-dir D) or settle it (afp-film lease settle)")
        if req.legacy_root is not None:
            if conn.execute("SELECT 1 FROM legacy_imports WHERE root = ?", (req.legacy_root,)).fetchone() is None:
                return "LEGACY_IMPORT_PENDING", f"the pre-S1 receipts of {req.legacy_root} are not imported into the " \
                                                f"broker yet"
            return "", ""
        if capped and conn.execute("SELECT 1 FROM legacy_imports LIMIT 1").fetchone() is None:
            return "LEGACY_IMPORT_PENDING", "no pre-S1 receipts were ever imported into the broker (afp-film broker " \
                                            "import-legacy --films-dir D)"
        return "", ""

    # ---- pre-S1 spend --------------------------------------------------------------------------------------------
    @staticmethod
    def legacy_root_key(films_dir: Path | str) -> str:
        return os.path.normcase(str(Path(films_dir).resolve()))

    def import_legacy(self, films_dir: Path | str, rows: list[dict[str, Any]], *,
                      problems: Iterable[dict[str, Any]] = (), seen: Iterable[str] | None = None,
                      brokered: Iterable[dict[str, Any]] = (),
                      scopes: Mapping[str, str] | None = None) -> dict[str, Any]:
        """Record the spend of receipts sent before S1 (read by the caller, outside this transaction) as SPENT or
        RELEASED reservations, once per receipt: the dedup key is the reservation identity (``legacy`` token + the
        receipt key), so a second import updates the same row (a receipt resolved since) and never adds it again. A
        receipt whose step-4 lease is already in the broker (migrated) is never added twice: while that migrated
        reservation is open (custody held) it is priced from the receipt (``price``) and stays RESERVED; once settled
        it keeps its settled spend; in every state it takes the receipt's take id and film scope, so the film ledger's
        credit for that take applies to it. Marks ``films_dir`` imported.

        ``problems`` are the receipts that could not be read (``key``, ``path``, ``problem``, ``sha256``): each is
        recorded in ``legacy_unresolved`` and the import of ``films_dir`` stays incomplete (capped admission is
        refused, LEGACY_RECEIPT_UNREADABLE) until every one is resolved: by ``resolve_legacy`` (kept while the file's
        bytes stay the same; a changed file asks again) or by a later import that reads it (``seen``: the keys of
        every receipt read this time). A receipt that vanished stays unresolved: deleting evidence resolves nothing.
        ``brokered``: receipts marked as broker sends (``key``, ``lease_key``, ``take_id``, ``path``, ``sha256``,
        ``film_key``): read (``seen``) only when this broker holds a reservation of that lease and take, else each is a
        problem (Codex R7-2: a marker alone proves nothing). ``scopes`` (package id -> film scope): a resolved charge
        that has no film scope (resolved by a v3 broker) is bound to its package's scope; when that scope is unknown the
        receipt is reopened (Codex R7-1: a charge outside every film budget is spend nobody counts).

        Each row: ``key`` (unique per receipt), ``lease_key`` (the step-4 lease key or ''), ``take_id``, ``account``,
        ``film_key``, ``provider``, ``unit``, ``amount`` (charged amount, 0 when not charged), ``price`` (the
        receipt's reserved amount), ``day``."""
        root = self.legacy_root_key(films_dir)
        ts = time.time()
        imported = skipped = priced = 0
        rows = list(rows)
        for r in rows:   # before any write: a bad row fails the whole import (nothing half-recorded)
            _check_legacy_row(r)
        with closing(self._connect()) as conn, self._tx(conn):
            for r in rows:
                migrated = conn.execute("SELECT id, state, lease_token, child_key, film_key FROM reservations WHERE "
                                        "lease_key = ? AND lease_token != 'legacy'",
                                        (r["lease_key"],)).fetchall() if r.get("lease_key") else []
                if migrated:
                    price = float(r["price"] if r.get("price") is not None else r.get("amount") or 0.0)
                    for m in migrated:
                        # bind the row to its exact receipt (the step-4 row named the generation, e.g. g1, and the
                        # bare film id): take identity and film scope, in every state; a settled row keeps its spend
                        take_id, film_key = r.get("take_id") or "", r.get("film_key") or m["film_key"]
                        if take_id:
                            conn.execute("UPDATE reservations SET take_id = ?, film_key = ? WHERE id = ?",
                                         (take_id, film_key, m["id"]))
                            conn.execute("UPDATE lease_children SET take_id = ?, film_key = ? WHERE lease_token = ? "
                                         "AND child_key = ?", (take_id, film_key, m["lease_token"], m["child_key"]))
                        if m["state"] == "RESERVED":
                            conn.execute("UPDATE reservations SET amount = ?, unit = ?, provider = ?, film_key = ?, "
                                         "day = ?, price_known = 1 WHERE id = ?",
                                         (price, r["unit"], r.get("provider") or "flow", r.get("film_key", ""),
                                          r["day"], m["id"]))
                            priced += 1
                    skipped += 1
                    continue
                amount = float(r.get("amount") or 0.0)
                state = "SPENT" if amount > 0 else "RELEASED"
                conn.execute("INSERT INTO reservations (lease_key, lease_token, child_key, take_id, account_id, film_key, "
                             "provider, unit, amount, spent, day, state, created_at, settled_at) VALUES "
                             "(?, 'legacy', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(lease_token, child_key) DO "
                             "UPDATE SET take_id = excluded.take_id, account_id = excluded.account_id, film_key = "
                             "excluded.film_key, provider = excluded.provider, unit = excluded.unit, amount = "
                             "excluded.amount, spent = excluded.spent, state = excluded.state, day = excluded.day, "
                             "settled_at = excluded.settled_at",
                             (f"legacy:{r['key']}", r["key"], r.get("take_id", ""), r.get("account", ""),
                              r.get("film_key", ""), r.get("provider", ""), r["unit"], amount, amount, r["day"], state,
                              ts, ts))
                imported += 1
            at = _iso_now()
            found = {str(p["key"]): p for p in problems}
            readable = set(seen) if seen is not None else set()
            for b in brokered:
                held = conn.execute("SELECT 1 FROM reservations WHERE lease_key = ? AND child_key = ? AND lease_token != "
                                    "'legacy' LIMIT 1", (str(b["lease_key"]), str(b["take_id"]))).fetchone()
                if held is not None:
                    readable.add(str(b["key"]))
                else:
                    found[str(b["key"])] = {**b, "problem": f"a broker-marked send that this broker holds no record of "
                                                            f"(lease {b['lease_key']}, take {b['take_id']})"}
            for key, p in found.items():
                old = conn.execute("SELECT sha256 FROM legacy_unresolved WHERE root = ? AND key = ?",
                                   (root, key)).fetchone()
                film_key = str(p.get("film_key") or "")   # the package's film scope ('' when film.json is unreadable)
                if old is not None and old["sha256"] == str(p.get("sha256") or ""):   # same bytes: keep its resolution
                    conn.execute("UPDATE legacy_unresolved SET path = ?, problem = ?, film_key = ? WHERE root = ? AND "
                                 "key = ?", (str(p.get("path") or ""), str(p["problem"]), film_key, root, key))
                    continue
                conn.execute("INSERT INTO legacy_unresolved (root, key, path, problem, sha256, found_at, film_key) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(root, key) DO UPDATE SET path = excluded.path, "
                             "problem = excluded.problem, sha256 = excluded.sha256, found_at = excluded.found_at, "
                             "film_key = excluded.film_key, resolved_at = '', resolved_by = '', resolved_reason = '', "
                             "resolved_amount = 0.0, resolved_unit = ''",
                             (root, key, str(p.get("path") or ""), str(p["problem"]), str(p.get("sha256") or ""), at,
                              film_key))
            for row in conn.execute("SELECT key FROM legacy_unresolved WHERE root = ? AND resolved_at = ''",
                                    (root,)).fetchall():
                if row["key"] not in found and row["key"] in readable:   # repaired: this import read it
                    conn.execute("UPDATE legacy_unresolved SET resolved_at = ?, resolved_by = 'import', "
                                 "resolved_reason = 'the receipt was read by a later import' WHERE root = ? AND key = ?",
                                 (at, root, row["key"]))
            # a charge resolved before film scopes were recorded (v3) counts against its film's budget
            for rec in conn.execute("SELECT u.key, u.film_key, r.id FROM legacy_unresolved u JOIN reservations r ON "
                                    "r.lease_token = 'legacy' AND r.child_key = u.key WHERE u.root = ? AND u.resolved_at "
                                    "!= '' AND r.film_key = '' AND (r.amount > 0 OR r.spent > 0)",
                                    (root,)).fetchall():
                scope = rec["film_key"] or str((scopes or {}).get(rec["key"].split(":", 1)[0]) or "")
                if scope:
                    conn.execute("UPDATE reservations SET film_key = ?, take_id = CASE WHEN take_id = '' THEN ? ELSE "
                                 "take_id END WHERE id = ?", (scope, rec["key"].split(":", 1)[-1], rec["id"]))
                    conn.execute("UPDATE legacy_unresolved SET film_key = ? WHERE root = ? AND key = ?",
                                 (scope, root, rec["key"]))
                else:
                    conn.execute("UPDATE legacy_unresolved SET resolved_at = '', problem = ? WHERE root = ? AND "
                                 "key = ?", ("a resolved charge whose film scope is unknown (its package's film.json "
                                             "is unreadable): repair film.json and import again", root, rec["key"]))
            open_keys = [r["key"] for r in conn.execute("SELECT key FROM legacy_unresolved WHERE root = ? AND "
                                                        "resolved_at = '' ORDER BY key", (root,)).fetchall()]
            conn.execute("INSERT INTO legacy_imports (root, imported_at, receipts, complete) VALUES (?, ?, ?, ?) "
                         "ON CONFLICT(root) DO UPDATE SET imported_at = excluded.imported_at, receipts = "
                         "excluded.receipts, complete = excluded.complete", (root, at, imported, 0 if open_keys else 1))
        return {"root": root, "imported": imported, "skipped_migrated": skipped, "priced_migrated": priced,
                "complete": not open_keys, "unresolved": open_keys}

    def resolve_legacy(self, films_dir: Path | str, key: str, *, by: str, reason: str, amount: float | None = None,
                       unit: str = "", day: str = "", provider: str = "") -> dict[str, Any]:
        """Operator: reconcile one pre-S1 receipt ``import_legacy`` could not read, with who and why recorded.
        ``amount`` > 0 records what it charged: a SPENT legacy reservation (the receipt's own identity, so a later
        readable import updates the same row) in ``unit`` (one of ``UNITS``) on ``day`` (a real ``YYYY-MM-DD``) for
        ``provider`` (a known provider), scoped to the film of the receipt's package as the import recorded it; it
        never lowers a spend already recorded for the receipt. No amount (or 0): the operator states it charged
        nothing. Refused (nothing changes) when any of these is invalid or the receipt's film scope is unknown (repair
        the package's ``film.json`` and import again). Once every unreadable receipt of ``films_dir`` is resolved, its
        import is complete."""
        if not isinstance(by, str) or not _BY_RE.match(by):
            raise ValueError("resolve_legacy: 'by' must match ^(human|agent):[A-Za-z0-9_.-]+$")
        if not isinstance(reason, str) or len(reason.strip()) < 3:
            raise ValueError("resolve_legacy: reason must be at least 3 characters")
        spent = 0.0 if amount is None else float(amount)
        _check_spent(spent)
        if spent > 0 or unit or day or provider:
            if unit not in UNITS:
                raise ValueError(f"resolve_legacy: --unit must be one of {', '.join(UNITS)}, not {unit!r}")
            if not valid_day(day):
                raise ValueError(f"resolve_legacy: --day must be a real calendar day YYYY-MM-DD, not {day!r}")
            if provider not in known_providers():
                raise ValueError(f"resolve_legacy: --provider must be one of {', '.join(sorted(known_providers()))}, "
                                 f"not {provider!r}")
        root = self.legacy_root_key(films_dir)
        ts = time.time()
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM legacy_unresolved WHERE root = ? AND key = ?", (root, key)).fetchone()
            if row is None:
                raise KeyError(f"no unreadable pre-S1 receipt {key!r} under {root}")
            film_key = row["film_key"]
            if not film_key:
                raise ValueError(f"resolve_legacy: the film scope of {key!r} is unknown (its package's film.json is "
                                 f"unreadable): repair film.json and import again")
            if spent > 0:
                prior = conn.execute("SELECT unit, amount FROM reservations WHERE lease_token = 'legacy' AND "
                                     "child_key = ?", (key,)).fetchone()
                if prior is not None and prior["amount"] > 0 and prior["unit"] != unit:
                    raise ValueError(f"resolve_legacy: {key!r} already counts {prior['amount']:g} {prior['unit']}; "
                                     f"a charge in {unit} cannot replace it")
                conn.execute("INSERT INTO reservations (lease_key, lease_token, child_key, take_id, account_id, "
                             "film_key, provider, unit, amount, spent, day, state, created_at, settled_at) VALUES "
                             "(?, 'legacy', ?, ?, '', ?, ?, ?, ?, ?, ?, 'SPENT', ?, ?) ON CONFLICT(lease_token, "
                             "child_key) DO UPDATE SET take_id = excluded.take_id, film_key = excluded.film_key, "
                             "provider = excluded.provider, unit = excluded.unit, day = excluded.day, amount = "
                             "MAX(amount, excluded.amount), spent = MAX(spent, excluded.spent), state = 'SPENT', "
                             "settled_at = excluded.settled_at",
                             (f"legacy:{key}", key, key.split(":", 1)[-1], film_key, provider, unit, spent, spent, day,
                              ts, ts))
            conn.execute("UPDATE legacy_unresolved SET resolved_at = ?, resolved_by = ?, resolved_reason = ?, "
                         "resolved_amount = ?, resolved_unit = ? WHERE root = ? AND key = ?",
                         (_iso_now(), by, reason.strip(), spent, unit if spent > 0 else "", root, key))
            open_keys = [r["key"] for r in conn.execute("SELECT key FROM legacy_unresolved WHERE root = ? AND "
                                                        "resolved_at = '' ORDER BY key", (root,)).fetchall()]
            if not open_keys:
                conn.execute("UPDATE legacy_imports SET complete = 1 WHERE root = ?", (root,))
        return {"root": root, "key": key, "film_key": film_key, "resolved_by": by, "amount": spent,
                "unit": unit if spent > 0 else "", "complete": not open_keys, "unresolved": open_keys}

    @staticmethod
    def _replay_mismatch(conn: sqlite3.Connection, lease: sqlite3.Row, req: AdmitRequest) -> str:
        """What differs between an ACTIVE lease and a request that would reuse it ('' when it is an exact replay):
        the film scope, unit, job kind, provider (when the request names one) and every child with its price."""
        if lease["unit"] != req.unit:
            return f"unit {lease['unit']} != {req.unit}"
        if lease["film_key"] != (req.film_key or req.film_id):
            return "film scope"
        if lease["job_kind"] != req.job_kind:
            return f"job kind {lease['job_kind']} != {req.job_kind}"
        if (req.provider or "").strip() and lease["provider"] != req.provider.strip():
            return f"provider {lease['provider']} != {req.provider}"
        held = sorted((r["child_key"], r["take_id"], round(float(r["amount"]), 6)) for r in conn.execute(
            "SELECT child_key, take_id, amount FROM reservations WHERE lease_token = ?", (lease["lease_token"],)))
        asked = sorted((c.child_key, c.take_id, round(float(c.amount), 6)) for c in req.children)   # type: ignore[arg-type]
        return "" if held == asked else "children or prices"

    @staticmethod
    def _batch_refusal(req: AdmitRequest) -> str:
        if not req.lease_key.strip():
            return "the lease key is empty"
        if not req.children:
            return "a batch needs at least one child"
        if req.job_kind not in JOB_KINDS:
            return f"job kind must be one of {JOB_KINDS}"
        keys = [c.child_key for c in req.children]
        if len(set(keys)) != len(keys) or not all(k.strip() for k in keys):
            return "child keys must be unique and non-empty"
        if not all(c.take_id.strip() and c.shot_key.strip() for c in req.children):
            return "every child names its take id and its shot version (shot_key); neither may be omitted"
        if not (req.film_key or req.film_id).strip():
            return "an admission names its film (film_key or film_id)"
        takes = [c.take_id for c in req.children]
        if len(set(takes)) != len(takes):
            return "take ids must be unique in a batch"
        shots = [c.shot_key for c in req.children]
        if len(set(shots)) != len(shots):
            return "two takes of one shot version are never in one batch"
        if req.epoch is not None and not (req.account_id or "").strip():
            return "an epoch belongs to one account: pin the account"
        return ""

    # ---- admission ------------------------------------------------------------------------------------------------
    def admit(self, req: AdmitRequest) -> dict[str, Any]:
        """Atomic admission (one short transaction, the halt-file lock held until COMMIT): halt (AFP and Muse), the
        allocator claim, epoch, the batch lease, the take identity (an earlier unresolved child of the same film + shot
        version on any lease or account refuses ``SHOT_VERSION_UNRESOLVED``; a take id is used once per film unless
        every earlier attempt is settled NOT_SENT, and then only under a fresh child key), and the reservations against
        the per-account quota, the per-film budget, the per-provider daily cap and the machine daily cap per unit.
        Returns ``{"ok": True, "lease": {...}}`` (the token appears here once and is never re-issued: a replay of a
        held lease is ``LEASE_EXISTS``) or ``{"ok": False, "code": ..., "reason": ..., "reprobe": [...]}``."""
        who = (req.holder or process_holder()).strip()
        pinned = (req.account_id or "").strip() or None
        ts = float(time.time() if req.now is None else req.now)
        day = req.day or local_day(None if req.now is None else ts)
        key = req.lease_key

        def refuse(code: str, reason: str, **extra: Any) -> dict[str, Any]:
            return {"ok": False, "code": code, "reason": reason, "reprobe": [], **extra}

        bad = self._batch_refusal(req)
        if bad:
            return refuse("BATCH_INVALID", bad)
        if req.unit not in UNITS or any(c.amount is None or not math.isfinite(float(c.amount)) or float(c.amount) < 0
                                         for c in req.children):
            return refuse("NO_PRICE", f"the route has no price in a known unit ({req.unit}); it cannot be admitted")
        total = round(sum(float(c.amount) for c in req.children), 6)   # type: ignore[arg-type]
        with closing(self._connect()) as conn, self._tx_locked(conn):
            code, why = self._stop_refusal()   # Owner rule: a halt stops ALL admission until explicitly cleared
            if code:
                return refuse(code, why)
            code, why = self._owner_refusal()
            if code:
                return refuse(code, why)
            existing = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            if existing is not None:
                if existing["state"] == "ACTIVE":
                    if existing["holder"] == who and (pinned is None or existing["account_id"] == pinned):
                        diff = self._replay_mismatch(conn, existing, req)
                        if diff:
                            return refuse("LEASE_HELD", f"lease {key} is held with a different admission ({diff}); "
                                                        f"a replay must repeat it exactly")
                        # the token is issued once, at the admission that created the lease; a caller that lost it
                        # cannot get it back (it holds the lease for reconcile instead)
                        return refuse("LEASE_EXISTS", f"lease {key} is already held by this caller; its token was "
                                                      f"issued once and is never re-issued")
                    return refuse("LEASE_HELD", f"lease {key} is held by another caller")
                if existing["state"] == UNCERTAIN:
                    return refuse("LEASE_HELD", f"lease {key} is {UNCERTAIN}; settle it after reconcile "
                                                f"(afp-film lease settle)")
            provider = (req.provider or "").strip()
            if not req.needs_account and not provider:
                return refuse("BATCH_INVALID", "an admission without an account must name its provider")
            legacy_code, legacy = self._legacy_refusal(conn, req, provider)
            if legacy:
                return refuse(legacy_code, legacy)
            film_key = req.film_key or req.film_id
            for c in req.children:   # one unresolved send per film + shot version, on any lease or account
                held = conn.execute(
                    "SELECT c.lease_key, c.child_key, c.phase, c.outcome FROM lease_children c JOIN leases l "
                    "ON l.lease_key = c.lease_key WHERE c.final = 0 AND c.film_key = ? AND (c.shot_key = ? OR "
                    "(c.shot_key = '' AND l.generation_id || ':v' || l.shot_version = ?)) LIMIT 1",
                    (film_key, c.shot_key, c.shot_key)).fetchone()
                if held is not None:
                    return refuse("SHOT_VERSION_UNRESOLVED",
                                  f"shot version {c.shot_key} of {film_key} has an unresolved child ({held['child_key']} "
                                  f"of lease {held['lease_key']}: {held['phase']} {held['outcome']}".rstrip()
                                  + "); settle it first")
            for c in req.children:   # take identity: one send per take id, for every film (capped or not)
                earlier = conn.execute("SELECT child_key, final, outcome FROM lease_children WHERE film_key = ? AND "
                                       "take_id = ?", (film_key, c.take_id)).fetchall()
                if any(not (e["final"] and e["outcome"] == "NOT_SENT") for e in earlier):
                    return refuse("TAKE_REUSED", f"take {c.take_id} of {film_key} already has an attempt that is "
                                                 f"not settled NOT_SENT; a new send needs a new take id")
                if any(e["child_key"] == c.child_key for e in earlier):
                    return refuse("TAKE_REUSED", f"take {c.take_id} of {film_key} was attempted under child key "
                                                 f"{c.child_key}; a new attempt after NOT_SENT needs a fresh child key")
                # the fence: a child settled NOT_SENT is never admitted again, under any take id
                fenced = conn.execute("SELECT lease_key FROM lease_children WHERE film_key = ? AND child_key = ? AND "
                                      "final = 1 AND outcome = 'NOT_SENT' LIMIT 1", (film_key, c.child_key)).fetchone()
                if fenced is not None:
                    return refuse("CHILD_FENCED", f"child {c.child_key} of {film_key} was settled NOT_SENT (lease "
                                                  f"{fenced['lease_key']}) and is fenced; a new attempt needs a fresh "
                                                  f"child key")
            film_capped = req.film_cap is not None and not math.isinf(req.film_cap)
            for c in req.children if film_capped else ():   # take identity decides what the film budget counts
                if c.take_id in req.film_counted:
                    return refuse("TAKE_REUSED", f"take {c.take_id} of {film_key} is already in the film's money "
                                                 f"ledger; a new send needs a new take id")
            for c in req.children:   # a pre-S1 / migrated reservation of the take (no child history) also counts
                dup = conn.execute("SELECT lease_key FROM reservations WHERE film_key = ? AND take_id = ? AND state IN "
                                   "('RESERVED', 'SPENT') LIMIT 1", (film_key, c.take_id)).fetchone()
                if dup is not None:
                    return refuse("TAKE_REUSED", f"take {c.take_id} of {film_key} is already reserved or spent "
                                                 f"(lease {dup['lease_key']}); a new send needs a new take id")
            code, why = self._cap_refusal(conn, req, total, day)
            if code:
                return refuse(code, why)
            account: sqlite3.Row | None = None
            if not req.needs_account:
                code, why = self._provider_cap_refusal(conn, provider, req.unit, total, day)
                if code:
                    return refuse(code, why)
            else:
                rows = conn.execute("SELECT * FROM accounts ORDER BY credits DESC, account_id ASC").fetchall()
                if not rows:
                    return refuse("NO_ACCOUNT_LEASE", f"no registered account in {self.db_path} "
                                                      f"(afp-film lease register --account ID --credits N)")
                if provider:
                    rows = [r for r in rows if r["provider"] == provider]
                if pinned:
                    rows = [r for r in rows if r["account_id"] == pinned]
                    if not rows:
                        return refuse("NO_ACCOUNT_LEASE", f"pinned account {pinned} is not registered in {self.db_path}"
                                      + (f" for provider {provider}" if provider else ""))
                if not rows:
                    return refuse("NO_ACCOUNT_LEASE", f"no registered {provider} account in {self.db_path}")
                if req.epoch is not None and int(req.epoch) != int(rows[0]["epoch"]):   # a fenced lane learns it first
                    return refuse("STALE_EPOCH", f"{rows[0]['account_id']}: epoch {req.epoch} is not the current "
                                                 f"epoch {rows[0]['epoch']}")
                why_not, reprobe, cap_codes = [], [], []
                for row in rows:
                    reason, probe = self._account_refusal(conn, row, req, total, ts, day)
                    if not reason:
                        # the provider cap of the provider this candidate resolves to (finding: an account-inferred
                        # provider must not bypass its provider's daily cap)
                        code, reason = self._provider_cap_refusal(conn, provider or row["provider"], req.unit, total,
                                                                  day)
                        if code:
                            cap_codes.append(code)
                    if not reason:
                        account = row
                        break
                    why_not.append(reason)
                    if probe:
                        reprobe.append(row["account_id"])
                if reprobe:
                    conn.executemany("UPDATE accounts SET reprobe_requested = 1 WHERE account_id = ?",
                                     [(a,) for a in reprobe])
                if account is None:
                    code = cap_codes[0] if cap_codes else "NO_ACCOUNT_LEASE"
                    return refuse(code, ("pinned account " if pinned else "no eligible account: ")
                                  + "; ".join(why_not or ["none eligible"]), reprobe=reprobe)
                if req.epoch is not None and int(req.epoch) != int(account["epoch"]):
                    return refuse("STALE_EPOCH", f"{account['account_id']}: epoch {req.epoch} is not the current "
                                                 f"epoch {account['epoch']}")
                provider = provider or account["provider"]
            token = uuid.uuid4().hex
            aid = account["account_id"] if account is not None else ""
            epoch = int(account["epoch"]) if account is not None else 0
            conn.execute(
                """INSERT INTO leases (lease_key, film_id, generation_id, shot_version, account_id, lease_token, leased_at,
                                       state, settled_credits, holder, note, provider, job_kind, epoch, day, film_key, unit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 0.0, ?, '', ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(lease_key) DO UPDATE SET
                       film_id = excluded.film_id, generation_id = excluded.generation_id,
                       shot_version = excluded.shot_version, account_id = excluded.account_id,
                       lease_token = excluded.lease_token, leased_at = excluded.leased_at, state = 'ACTIVE',
                       settled_credits = 0.0, holder = excluded.holder, note = '', provider = excluded.provider,
                       job_kind = excluded.job_kind, epoch = excluded.epoch, day = excluded.day,
                       film_key = excluded.film_key, unit = excluded.unit""",
                (key, req.film_id.strip(), req.generation_id or key, int(req.shot_version), aid, token, ts, who,
                 provider, req.job_kind, epoch, day, film_key, req.unit))
            at = _iso_now()
            for c in req.children:
                conn.execute("INSERT INTO lease_children (lease_key, lease_token, child_key, take_id, shot_key, film_key, "
                             "phase, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'PREPARING', ?)",
                             (key, token, c.child_key, c.take_id, c.shot_key, film_key, at))
                conn.execute("INSERT INTO reservations (lease_key, lease_token, child_key, take_id, account_id, film_key, "
                             "provider, unit, amount, day, state, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                             "'RESERVED', ?)", (key, token, c.child_key, c.take_id, aid, film_key, provider, req.unit,
                                                float(c.amount), day, ts))   # type: ignore[arg-type]
            lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone()
            return {"ok": True, "lease": self._lease_view(conn, lease)}

    @staticmethod
    def _lease_view(conn: sqlite3.Connection, lease: sqlite3.Row) -> dict[str, Any]:
        acct = conn.execute("SELECT cdp_endpoint, project FROM accounts WHERE account_id = ?",
                            (lease["account_id"],)).fetchone() if lease["account_id"] else None
        children = [dict(r) for r in conn.execute(
            "SELECT child_key, take_id, phase, outcome, final, spent FROM lease_children WHERE lease_key = ? "
            "AND lease_token = ? ORDER BY id", (lease["lease_key"], lease["lease_token"])).fetchall()]
        return {**dict(lease), "cdp_endpoint": acct["cdp_endpoint"] if acct else "",
                "project": acct["project"] if acct else "", "children": children}

    def availability(self, *, cost_credits: float = 6.0, account_id: str | None = None, now: float | None = None,
                     provider: str | None = None, unit: str = "credits", job_kind: str = "video",
                     batch_size: int = 1) -> tuple[bool, str]:
        """Read-only: would an account be leasable now (dry runs)? Takes no lease, writes nothing."""
        stop = self._stop_refusal()[1]
        if stop:
            return False, stop
        why_owner = self._owner_refusal()[1]
        if why_owner:
            return False, why_owner
        ts = float(time.time() if now is None else now)
        req = AdmitRequest(lease_key="?", children=[Child(f"c{i}", cost_credits / max(1, batch_size))
                                                    for i in range(max(1, batch_size))],
                           unit=unit, provider=provider, job_kind=job_kind)
        pinned = (account_id or "").strip() or None
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY credits DESC, account_id ASC").fetchall()
            if not rows:
                return False, f"no registered account in {self.db_path} (afp-film lease register --account ID --credits N)"
            if provider:
                rows = [r for r in rows if r["provider"] == provider]
            if pinned:
                rows = [r for r in rows if r["account_id"] == pinned]
                if not rows:
                    return False, f"pinned account {pinned} is not registered in {self.db_path}"
            why = []
            for row in rows:
                reason, _ = self._account_refusal(conn, row, req, float(cost_credits), ts, local_day())
                if not reason:
                    reason = self._provider_cap_refusal(conn, provider or row["provider"], unit, float(cost_credits),
                                                        local_day())[1]
                if not reason:
                    return True, ""
                why.append(reason)
            return False, ("pinned account " if pinned else "no eligible account: ") + "; ".join(why or ["none eligible"])

    # ---- the lane's pre-Enter check -------------------------------------------------------------------------------
    def before_enter(self, lease_key: str, *, lease_token: str, child_key: str | None = None,
                     child_keys: Iterable[str] | None = None, epoch: int | None = None, incarnation: str = "",
                     now: float | None = None) -> dict[str, Any]:
        """Immediately before the provider Enter, in one short transaction with the halt-file lock held until COMMIT:
        re-check the lease (token, ACTIVE), the halt (AFP and Muse), the allocator claim, the account and the epoch,
        then move EVERY named child PREPARING -> SUBMITTING bound to ``incarnation`` (the lane process that asked), or
        none of them.

        Returns ``{"go", "code", "reason", "proven", "children"}``. ``proven`` True: the broker closed every named
        child NOT_SENT in this transaction (nothing may be sent). ``proven`` False with ``go`` False: possibly sent:
        ``ALREADY_SUBMITTING`` (a child already passed a check: a lost reply; the caller treats it as AMBIGUOUS),
        ``CHILD_NOT_PREPARING`` (it already has another outcome) or ``LEASE_LOST`` with no child under this token;
        nothing is changed then."""
        if child_key is not None and child_keys is not None:
            raise ValueError("pass child_key or child_keys, not both")
        keys = [child_key] if child_key is not None else list(child_keys or [])
        if not keys or not all(isinstance(k, str) and k.strip() for k in keys) or len(set(keys)) != len(keys):
            raise ValueError("the pre-Enter check needs one or more distinct, non-empty child keys")
        incarnation = (incarnation or "").strip()
        ts = float(time.time() if now is None else now)

        def answer(go: bool, code: str = "", reason: str = "", proven: bool = False) -> dict[str, Any]:
            return {"go": go, "code": code, "reason": reason, "proven": proven, "children": keys}

        with closing(self._connect()) as conn, self._tx_locked(conn):
            lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
            rows = {k: conn.execute("SELECT * FROM lease_children WHERE lease_key = ? AND lease_token = ? AND "
                                    "child_key = ?", (lease_key, lease_token, k)).fetchone() for k in keys}
            submitting = [k for k, r in rows.items() if r is not None and r["phase"] == "SUBMITTING" and not r["final"]]
            if submitting:   # a lost reply: never a second Enter, and never a NOT_SENT for a child that may be out
                return answer(False, "ALREADY_SUBMITTING",
                              f"{', '.join(submitting)} already passed the pre-Enter check: possibly sent; treat it as "
                              f"AMBIGUOUS and reconcile")
            other = [f"{k} is {r['phase']} {r['outcome']}".strip() for k, r in rows.items() if r is not None
                     and not (r["phase"] == "PREPARING" and not r["final"])
                     and not (r["final"] and r["outcome"] == "NOT_SENT")]
            if other:
                return answer(False, "CHILD_NOT_PREPARING", "; ".join(other) + ": possibly sent; never re-entered")
            missing = [k for k, r in rows.items() if r is None]
            if missing:
                return answer(False, "LEASE_LOST", f"{', '.join(missing)} is not a child of {lease_key} under this "
                                                   f"token: possibly sent by another attempt; nothing changed")
            code, reason = "", ""
            stop, owner = self._stop_refusal(), self._owner_refusal()
            closed = [k for k, r in rows.items() if r["final"]]
            acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (lease["account_id"],)).fetchone() \
                if lease is not None and lease["account_id"] else None
            if closed:
                code, reason = "ALREADY_NOT_SENT", f"{', '.join(closed)} is already NOT_SENT: the batch cannot go whole"
            elif lease is None or lease["lease_token"] != lease_token or lease["state"] != "ACTIVE":
                code, reason = "LEASE_LOST", f"lease {lease_key} is " + (
                    lease["state"] if lease is not None and lease["lease_token"] == lease_token
                    else "not held with this token")
            elif stop[0]:
                code, reason = stop
            elif owner[0]:
                code, reason = owner
            elif acct is not None and acct["status"] != "ACTIVE":
                code, reason = "ACCOUNT_NOT_ACTIVE", f"{acct['account_id']} is {acct['status']}"
            elif acct is not None and (int(lease["epoch"]) != int(acct["epoch"])
                                       or (epoch is not None and int(epoch) != int(acct["epoch"]))):
                code, reason = "STALE_EPOCH", f"{acct['account_id']} epoch is {acct['epoch']} (lease " \
                                              f"{lease['epoch']}, lane {epoch if epoch is not None else '-'})"
            elif acct is None and epoch is not None and int(epoch) != int(lease["epoch"]):
                code, reason = "STALE_EPOCH", f"lease epoch is {lease['epoch']} (lane {epoch})"
            if code:
                for k, r in rows.items():
                    if not r["final"]:   # PREPARING children exist only under the lease's current token
                        self._close_child(conn, lease, r, "NOT_SENT", 0.0, ts, note=f"{code}: {reason}"[:300],
                                          cooldown=0.0)
                    self._audit(conn, lease_key, k, "CHECK_NOT_SENT", incarnation=incarnation, epoch=epoch,
                                reason=f"{code}: {reason}")
                return answer(False, code, reason, proven=True)
            at = _iso_now()
            for k, r in rows.items():
                conn.execute("UPDATE lease_children SET phase = 'SUBMITTING', incarnation = ?, updated_at = ? "
                             "WHERE id = ?", (incarnation, at, r["id"]))
                self._audit(conn, lease_key, k, "CHECK_GO", incarnation=incarnation, epoch=int(lease["epoch"]))
            return answer(True)

    def enter_not_issued(self, lease_key: str, *, lease_token: str, child_key: str, incarnation: str, epoch: int,
                         reason: str = "", now: float | None = None) -> dict[str, Any]:
        """The lane proves it never issued the Enter for a child that passed the pre-Enter check (SUBMITTING): close it
        NOT_SENT. Accepted only from the live holder: the same lease token, the lease still ACTIVE (not released, held
        or re-admitted), the incarnation the check bound, and the epoch still current (lease and account). Anything
        else is refused (``ENTER_NOT_ISSUED_REFUSED``) and a SUBMITTING child is held AMBIGUOUS for reconcile. Both
        decisions are audited (``child_audit``)."""
        ts = float(time.time() if now is None else now)
        incarnation = (incarnation or "").strip()
        note = ("ENTER_NOT_ISSUED: " + reason.strip()).strip()[:300]
        with closing(self._connect()) as conn, self._tx(conn):
            lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
            child = conn.execute("SELECT * FROM lease_children WHERE lease_key = ? AND lease_token = ? AND "
                                 "child_key = ?", (lease_key, lease_token, child_key)).fetchone()
            acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (lease["account_id"],)).fetchone() \
                if lease is not None and lease["account_id"] else None
            why = ""
            if lease is None or lease["lease_token"] != lease_token:
                why = f"lease {lease_key} is not held with this token"
            elif child is None:
                why = f"{child_key} is not a child of {lease_key}"
            elif lease["state"] != "ACTIVE":
                why = f"lease {lease_key} is {lease['state']}"
            elif child["phase"] != "SUBMITTING" or child["final"]:
                why = f"{child_key} is {child['phase']} {child['outcome']}".strip()
            elif not incarnation or child["incarnation"] != incarnation:
                why = f"{child_key} passed its check under another lane incarnation"
            elif int(epoch) != int(lease["epoch"]) or (acct is not None and int(acct["epoch"]) != int(lease["epoch"])):
                why = f"epoch {epoch} is not current (lease {lease['epoch']}" \
                      + (f", account {acct['epoch']})" if acct is not None else ")")
            elif acct is not None and acct["status"] != "ACTIVE":
                why = f"{acct['account_id']} is {acct['status']}"
            if not why:
                self._close_child(conn, lease, child, "NOT_SENT", 0.0, ts, note=note, cooldown=0.0)
                self._audit(conn, lease_key, child_key, "ENTER_NOT_ISSUED", incarnation=incarnation, epoch=int(epoch),
                            reason=note)
                return {"ok": True, "code": "", "reason": "", "outcome": "NOT_SENT"}
            outcome = child["outcome"] if child is not None else ""
            if child is not None and lease is not None and lease["lease_token"] == lease_token \
                    and child["phase"] == "SUBMITTING" and not child["final"]:
                self._close_child(conn, lease, child, "AMBIGUOUS", 0.0, ts, final=False,
                                  note=f"ENTER_NOT_ISSUED refused: {why}"[:300])
                outcome = "AMBIGUOUS"
            self._audit(conn, lease_key, child_key, "ENTER_NOT_ISSUED_REFUSED", incarnation=incarnation,
                        epoch=int(epoch), reason=why)
            return {"ok": False, "code": "ENTER_NOT_ISSUED_REFUSED",
                    "reason": f"{why}: the child stays for reconcile (possibly sent)", "outcome": outcome}

    def settle_not_sent(self, child_key: str, *, evidence: str, lease_key: str | None = None,
                        lease_token: str | None = None, now: float | None = None) -> dict[str, Any]:
        """Atomic NOT_SENT settlement (one transaction): a child still PREPARING never passed the pre-Enter check, the
        only way to SUBMITTING, so it is provably unsent: close it terminal NOT_SENT and fence it (a later check is
        NOT_SENT_PROVEN with no Enter; an admission naming it is CHILD_FENCED). A child past the check (SUBMITTING or
        a migrated UNKNOWN phase) is refused (``CHILD_PAST_ENTER``: possibly sent) and nothing changes; a child already
        NOT_SENT is an idempotent success. ``lease_key`` picks the lease when the child key is not unique;
        ``lease_token``, when given, must be the lease's. Audited (``child_audit``)."""
        evidence = (evidence or "").strip()
        if len(evidence) < 3:
            raise ValueError("settle_not_sent needs the evidence (at least 3 characters)")
        ts = float(time.time() if now is None else now)
        with closing(self._connect()) as conn, self._tx(conn):
            q = ("SELECT c.* FROM lease_children c JOIN leases l ON l.lease_key = c.lease_key AND "
                 "l.lease_token = c.lease_token WHERE c.child_key = ?")
            args: tuple[Any, ...] = (child_key,)
            if lease_key:
                q += " AND c.lease_key = ?"
                args += (lease_key,)
            rows = conn.execute(q, args).fetchall()
            if not rows:
                raise KeyError(f"no child {child_key!r}" + (f" in lease {lease_key!r}" if lease_key else ""))
            if len(rows) > 1:
                return {"ok": False, "code": "CHILD_AMBIGUOUS", "reason": f"{child_key} is a child of "
                        f"{len(rows)} leases: name the lease (--lease-key)"}
            child = rows[0]
            lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (child["lease_key"],)).fetchone()
            if lease_token is not None and lease_token != lease["lease_token"]:
                raise ValueError(f"lease_token mismatch for {lease['lease_key']!r}")
            base = {"lease_key": lease["lease_key"], "child_key": child_key}
            if child["final"]:
                if child["outcome"] == "NOT_SENT":
                    return {"ok": True, "code": "", "reason": "already NOT_SENT", **base, "outcome": "NOT_SENT",
                            "fenced": True, "changed": False, "lease_state": lease["state"]}
                return {"ok": False, "code": "CHILD_FINAL", "reason": f"{child_key} is already {child['outcome']}",
                        **base, "outcome": child["outcome"]}
            if child["phase"] != "PREPARING":
                self._audit(conn, lease["lease_key"], child_key, "SETTLE_NOT_SENT_REFUSED",
                            reason=f"{child['phase']}: {evidence}")
                return {"ok": False, "code": "CHILD_PAST_ENTER", "reason": f"{child_key} is {child['phase']}: it "
                        f"passed the pre-Enter check and is possibly sent; reconcile it (settle)", **base,
                        "outcome": child["outcome"], "possibly_sent": True}
            note = f"SETTLED_NOT_SENT: {evidence}"[:300]
            self._close_child(conn, lease, child, "NOT_SENT", 0.0, ts, note=note, cooldown=0.0)
            self._audit(conn, lease["lease_key"], child_key, "SETTLE_NOT_SENT", reason=evidence)
            state = conn.execute("SELECT state FROM leases WHERE lease_key = ?", (lease["lease_key"],)).fetchone()[0]
            return {"ok": True, "code": "", "reason": "", **base, "outcome": "NOT_SENT", "fenced": True,
                    "changed": True, "lease_state": state}

    # ---- the allocator claim --------------------------------------------------------------------------------------
    def allocator_claim(self, *, by: str = "") -> dict[str, Any]:
        """Bootstrap the allocator claim ``{"owner": "afp-broker", ...}`` (``allocator_owner.json``): BEGIN IMMEDIATE,
        then the halt-file lock; idempotent (a valid ``afp-broker`` claim is kept, ``changed`` False). A claim file
        that cannot be trusted (``ALLOCATOR_UNKNOWN``) or names another owner (``ALLOCATOR_NOT_OWNED``) is never
        overwritten: repair it by hand."""
        with closing(self._connect()) as conn, self._tx_locked(conn):
            claim = read_owner()
            if claim["problem"] == "absent":
                written = write_owner_locked(by or process_holder())
                return {"ok": True, "code": "", "reason": "", "owner": OWNER, "changed": True,
                        "claimed_at": written["claimed_at"]}
            if claim["problem"]:
                return {"ok": False, "code": "ALLOCATOR_UNKNOWN",
                        "reason": f"the allocator claim is {claim['problem']}: repair it by hand; it is never "
                                  f"overwritten"}
            if claim["owner"] != OWNER:
                return {"ok": False, "code": "ALLOCATOR_NOT_OWNED",
                        "reason": f"the allocator claim names {claim['owner']!r}: it is never overwritten"}
            return {"ok": True, "code": "", "reason": "", "owner": OWNER, "changed": False,
                    "claimed_at": claim["claimed_at"]}

    def allocator_release(self, *, by: str = "") -> dict[str, Any]:
        """Remove the ``afp-broker`` claim: BEGIN IMMEDIATE, then the halt-file lock; refused (``OWNER_BUSY``) while a
        lease is live (not RELEASED) or a child unresolved in this broker; idempotent when there is no claim. A claim
        that cannot be trusted or names another owner is never removed (repair it by hand)."""
        with closing(self._connect()) as conn, self._tx_locked(conn):
            claim = read_owner()
            if claim["problem"] == "absent":
                return {"ok": True, "code": "", "reason": "", "changed": False}
            if claim["problem"]:
                return {"ok": False, "code": "ALLOCATOR_UNKNOWN",
                        "reason": f"the allocator claim is {claim['problem']}: repair it by hand; it is never removed"}
            if claim["owner"] != OWNER:
                return {"ok": False, "code": "ALLOCATOR_NOT_OWNED",
                        "reason": f"the allocator claim names {claim['owner']!r}: it is never removed"}
            live = conn.execute("SELECT lease_key, state FROM leases WHERE state != 'RELEASED' LIMIT 1").fetchone()
            open_child = conn.execute("SELECT lease_key, child_key FROM lease_children WHERE final = 0 "
                                      "LIMIT 1").fetchone()
            if live is not None or open_child is not None:
                what = (f"lease {live['lease_key']} is {live['state']}" if live is not None
                        else f"child {open_child['child_key']} of {open_child['lease_key']} is unresolved")
                return {"ok": False, "code": "OWNER_BUSY", "reason": f"{what}: settle every lease and child first"}
            remove_owner_locked()
            return {"ok": True, "code": "", "reason": "", "changed": True, "released_by": by or process_holder()}

    # ---- settlement -----------------------------------------------------------------------------------------------
    def _close_child(self, conn: sqlite3.Connection, lease: sqlite3.Row, child: sqlite3.Row, outcome: str,
                     spent: float, ts: float, *, note: str = "", cooldown: float | None = None,
                     final: bool = True) -> None:
        """Give one child its outcome (``final=False``: AMBIGUOUS, the lease is held), settle its reservation, and
        settle the batch once every child is final. A spend that is negative or not finite is refused (ValueError,
        the transaction rolls back: nothing changes)."""
        _check_spent(spent)
        conn.execute("UPDATE lease_children SET phase = CASE WHEN ? THEN 'DONE' ELSE phase END, outcome = ?, "
                     "final = ?, spent = ?, note = CASE WHEN ? != '' THEN ? ELSE note END, updated_at = ? WHERE id = ?",
                     (final, outcome, int(final), float(spent), note, note, _iso_now(), child["id"]))
        if final:
            conn.execute("UPDATE reservations SET state = ?, spent = ?, settled_at = ? WHERE lease_token = ? "
                         "AND child_key = ?", ("SPENT" if spent > 0 else "RELEASED", float(spent), ts,
                                               lease["lease_token"], child["child_key"]))
            if spent > 0 and lease["account_id"]:
                conn.execute("UPDATE accounts SET credits = MAX(0.0, credits - ?), updated_at = ? WHERE account_id = ? "
                             "AND quota_mode = 'constant' AND quota_unit = ?",
                             (float(spent), _iso_now(), lease["account_id"], lease["unit"]))
        self._settle_batch(conn, lease["lease_key"], ts, cooldown, note)

    def _settle_batch(self, conn: sqlite3.Connection, lease_key: str, ts: float, cooldown: float | None,
                      note: str = "") -> None:
        lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
        children = conn.execute("SELECT * FROM lease_children WHERE lease_key = ? AND lease_token = ?",
                                (lease_key, lease["lease_token"])).fetchall()
        if lease["state"] == "RELEASED":
            return
        if all(c["final"] for c in children):
            spent = round(sum(float(c["spent"]) for c in children), 6)
            cd = self.cooldown_s if cooldown is None else float(cooldown)
            conn.execute("UPDATE leases SET state = 'RELEASED', settled_credits = ?, note = CASE WHEN ? != '' THEN ? "
                         "ELSE note END WHERE lease_key = ?", (spent, note, note, lease_key))
            if lease["account_id"]:
                conn.execute("UPDATE accounts SET cooldown_until = MAX(cooldown_until, ?), updated_at = ? "
                             "WHERE account_id = ?", (ts + cd if cd > 0 else 0.0, _iso_now(), lease["account_id"]))
        elif any(c["outcome"] == "AMBIGUOUS" for c in children) and lease["state"] != UNCERTAIN:
            held = next(c for c in children if c["outcome"] == "AMBIGUOUS")
            conn.execute("UPDATE leases SET state = ?, note = ? WHERE lease_key = ?",
                         (UNCERTAIN, (held["note"] or note or "a child is AMBIGUOUS")[:300], lease_key))

    def _lease_and_child(self, conn: sqlite3.Connection, lease_key: str, lease_token: str | None,
                         child_key: str | None) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
        lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
        if lease is None:
            raise KeyError(f"no lease found for {lease_key!r}")
        if lease_token is not None and lease["lease_token"] != lease_token:
            raise ValueError(f"lease_token mismatch for {lease_key!r}")
        q = "SELECT * FROM lease_children WHERE lease_key = ? AND lease_token = ? AND final = 0"
        args: tuple[Any, ...] = (lease_key, lease["lease_token"])
        if child_key is not None:
            q += " AND child_key = ?"
            args += (child_key,)
        return lease, conn.execute(q + " ORDER BY id", args).fetchall()

    def finish_child(self, lease_key: str, *, lease_token: str, child_key: str, outcome: str, spent: float,
                     cooldown_s: float | None = None, now: float | None = None) -> dict[str, Any]:
        """The holder knows a child's outcome: settle it (``spent`` > 0: a spend, else a release). ``outcome`` AMBIGUOUS
        holds the child (and the account) until ``settle_child``."""
        _check_spent(spent)
        ts = float(time.time() if now is None else now)
        with closing(self._connect()) as conn, self._tx(conn):
            lease, children = self._lease_and_child(conn, lease_key, lease_token, child_key)
            for child in children:
                ambiguous = outcome == "AMBIGUOUS"
                self._close_child(conn, lease, child, outcome, 0.0 if ambiguous else float(spent), ts,
                                  cooldown=cooldown_s, final=not ambiguous, note=outcome if ambiguous else "")
            return self._lease_view(conn, conn.execute("SELECT * FROM leases WHERE lease_key = ?",
                                                       (lease_key,)).fetchone())

    def release_unsent(self, lease_key: str, *, lease_token: str, child_key: str | None = None,
                       now: float | None = None) -> dict[str, Any]:
        """Release children that never reached the Enter (phase PREPARING) as NOT_SENT: nothing spent, no cooldown.
        Returns ``{"released": [...], "uncertain": [...]}``; a SUBMITTING or UNKNOWN child is never released here (the
        caller holds it: ``mark_uncertain``)."""
        ts = float(time.time() if now is None else now)
        with closing(self._connect()) as conn, self._tx(conn):
            lease, children = self._lease_and_child(conn, lease_key, lease_token, child_key)
            released, uncertain = [], []
            for child in children:
                if child["phase"] == "PREPARING" and child["outcome"] != "AMBIGUOUS":
                    self._close_child(conn, lease, child, "NOT_SENT", 0.0, ts, cooldown=0.0)
                    released.append(child["child_key"])
                else:
                    uncertain.append(child["child_key"])
            return {"released": released, "uncertain": uncertain}

    def hold_child(self, lease_key: str, *, lease_token: str, reason: str, child_key: str | None = None,
                   now: float | None = None) -> dict[str, Any]:
        """The outcome of an open child is unknown (crash after SUBMITTING, AMBIGUOUS result): hold it, and with it the
        account (state HELD), until ``settle_child`` after reconcile. No halt is set."""
        ts = float(time.time() if now is None else now)
        with closing(self._connect()) as conn, self._tx(conn):
            lease, children = self._lease_and_child(conn, lease_key, lease_token, child_key)
            for child in children:
                self._close_child(conn, lease, child, "AMBIGUOUS", 0.0, ts, final=False, note=reason.strip()[:300])
            if lease["state"] == "ACTIVE" and not children:
                conn.execute("UPDATE leases SET state = ?, note = ? WHERE lease_key = ?",
                             (UNCERTAIN, reason.strip()[:300], lease_key))
            return dict(conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone())

    def settle_child(self, lease_key: str, *, spent: float, child_key: str | None = None, note: str = "",
                     cooldown_s: float | None = None, now: float | None = None) -> dict[str, Any]:
        """The reconcile path (no token): give held/open children their resolved outcome. Call it only once the
        child's receipt is resolved (``production.leases.settle_take`` checks that)."""
        _check_spent(spent)
        ts = float(time.time() if now is None else now)
        with closing(self._connect()) as conn, self._tx(conn):
            lease, children = self._lease_and_child(conn, lease_key, None, child_key)
            for i, child in enumerate(children):
                self._close_child(conn, lease, child, "SETTLED", float(spent) if i == 0 else 0.0, ts,
                                  cooldown=cooldown_s, note=note or "settled")
            self._settle_batch(conn, lease_key, ts, cooldown_s, note or "settled")
            return dict(conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone())

    # ---- account warnings -----------------------------------------------------------------------------------------
    def account_warning(self, account_id: str, reason: str, *, kind: str = "ACCOUNT_WARNING",
                        release_active_leases: bool = False, source: str = "lease_pool", film_id: str = "",
                        take_id: str = "") -> dict[str, Any]:
        """CAPTCHA, verification or unusual activity (Owner policy): in one broker transaction quarantine the account,
        hold its in-flight children (never released as unsent) and set the machine-wide halt. Nothing is solved,
        evaded or moved to another account."""
        if kind not in WARNING_KINDS:
            raise ValueError(f"kind must be one of {WARNING_KINDS}")
        why = reason.strip() or "account warning"
        ts = time.time()
        with closing(self._connect()) as conn, self._tx(conn):
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown account {account_id!r}")
            conn.execute("UPDATE accounts SET status = 'COOLDOWN_QUARANTINE', quarantined_reason = ?, updated_at = ? "
                         "WHERE account_id = ?", (why, _iso_now(), account_id))
            for lease in conn.execute("SELECT * FROM leases WHERE account_id = ? AND state IN (?, ?)",
                                      (account_id, *_HELD)).fetchall():
                if release_active_leases:   # the operator proved nothing was submitted
                    for child in conn.execute("SELECT * FROM lease_children WHERE lease_key = ? AND lease_token = ? "
                                              "AND final = 0", (lease["lease_key"], lease["lease_token"])).fetchall():
                        self._close_child(conn, lease, child, "NOT_SENT", 0.0, ts, cooldown=0.0)
                    conn.execute("UPDATE leases SET state = 'RELEASED' WHERE lease_key = ?", (lease["lease_key"],))
                elif lease["state"] == "ACTIVE":
                    conn.execute("UPDATE lease_children SET outcome = 'AMBIGUOUS', note = ?, updated_at = ? "
                                 "WHERE lease_key = ? AND lease_token = ? AND final = 0",
                                 (f"{kind}: {why}"[:300], _iso_now(), lease["lease_key"], lease["lease_token"]))
                    conn.execute("UPDATE leases SET state = ?, note = ? WHERE lease_key = ?",
                                 (UNCERTAIN, f"{kind}: {why}"[:300], lease["lease_key"]))
            # inside the broker transaction: no admission and no pre-Enter check can pass between the two
            set_halt(why, source=source, account=account_id, film_id=film_id, take_id=take_id, evidence=kind,
                     lock=False)
            return dict(conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone())

    # ---- re-login (§9: kept in the broker so it survives restarts) -------------------------------------------------
    def before_login(self, account_id: str, *, cause: str, epoch: int, lease_key: str | None = None,
                     lease_token: str | None = None, claimant: str | None = None,
                     now: float | None = None) -> dict[str, Any]:
        """A lane asks to re-log in. Only an expired authentication qualifies; at most one attempt per account per 2 h.
        In the same transaction, which records the attempt: the halt, the account status, the lane's ``epoch`` (it must
        be the account's current one) and the lane's ownership of the account: either its lease (``lease_key`` +
        ``lease_token``, ACTIVE or held, on this account and admitted under the current epoch) or its profile claim
        (``claimant``, claimed under the current epoch). Losing any of them: ``go`` False, no login."""
        ts = float(time.time() if now is None else now)
        with closing(self._connect()) as conn, self._tx(conn):
            acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if acct is None:
                raise KeyError(f"unknown account {account_id!r}")

            def no(code: str, reason: str) -> dict[str, Any]:
                return {"go": False, "code": code, "reason": reason}

            if cause != "AUTH_EXPIRED":
                return no("RELOGIN_NOT_ALLOWED", f"only an expired login triggers a re-login, not {cause!r}")
            if self._halted():
                return no("PRODUCTION_HALT", self._halt_reason())
            if acct["status"] != "ACTIVE":
                return no("ACCOUNT_NOT_ACTIVE", f"{account_id} is {acct['status']}")
            if epoch is None or int(epoch) != int(acct["epoch"]):
                return no("STALE_EPOCH", f"{account_id} epoch is {acct['epoch']}, the lane has {epoch}")
            owner = False
            if lease_key and lease_token:
                lease = conn.execute("SELECT * FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
                owner = (lease is not None and lease["lease_token"] == lease_token
                         and lease["account_id"] == account_id and lease["state"] in _HELD
                         and int(lease["epoch"]) == int(acct["epoch"]))
            if not owner and claimant and claimant.strip():
                owner = (acct["profile_claimant"] == claimant.strip()
                         and int(acct["profile_claim_epoch"]) == int(acct["epoch"]))
            if not owner:
                return no("NOT_OWNER", f"{account_id}: the caller holds neither a lease of the current epoch on it nor "
                                       f"its profile claim")
            last = float(acct["relogin_last_at"] or 0.0)
            if last and ts - last < RELOGIN_INTERVAL_S:
                return no("RELOGIN_THROTTLED", f"{account_id}: last re-login {ts - last:.0f} s ago; at most one per "
                                               f"{RELOGIN_INTERVAL_S:.0f} s")
            conn.execute("UPDATE accounts SET relogin_last_at = ?, relogin_pending = 1, updated_at = ? "
                         "WHERE account_id = ?", (ts, _iso_now(), account_id))
            return {"go": True, "code": "", "reason": ""}

    def record_login_result(self, account_id: str, *, ok: bool) -> dict[str, Any]:
        """The result of a re-login attempt: success resets the failure count; the 2nd consecutive failure marks the
        account NEEDS_LOGIN (the Owner is told; work continues on the other accounts). Only the result of an attempt
        ``before_login`` authorised (``relogin_pending``) is recorded."""
        with closing(self._connect()) as conn, self._tx(conn):
            acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if acct is None:
                raise KeyError(f"unknown account {account_id!r}")
            if not int(acct["relogin_pending"]):
                raise ValueError(f"{account_id}: no re-login attempt is pending (before_login first)")
            failures = 0 if ok else int(acct["relogin_failures"]) + 1
            status = acct["status"]
            if failures >= RELOGIN_MAX_FAILURES and status == "ACTIVE":
                status = "NEEDS_LOGIN"
            conn.execute("UPDATE accounts SET relogin_failures = ?, relogin_pending = 0, status = ?, "
                         "quarantined_reason = CASE WHEN ? = 'NEEDS_LOGIN' AND status = 'ACTIVE' THEN ? "
                         "ELSE quarantined_reason END, updated_at = ? WHERE account_id = ?",
                         (failures, status, status, f"{failures} consecutive re-login failures", _iso_now(),
                          account_id))
            return dict(conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone())

    # ---- profile ownership (M9) -----------------------------------------------------------------------------------
    def claim_profile(self, account_id: str, *, claimant: str, epoch: int) -> dict[str, Any]:
        """A lane claims its account's browser profile for its life. Non-blocking: a live claim of another claimant
        (same epoch) refuses at once, never queues; a claim from an older epoch is void (its lane was fenced)."""
        who = claimant.strip()
        if not who:
            raise ValueError("claimant cannot be empty")
        with closing(self._connect()) as conn, self._tx(conn):
            acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if acct is None:
                raise KeyError(f"unknown account {account_id!r}")
            if int(epoch) != int(acct["epoch"]):
                return {"ok": False, "code": "STALE_EPOCH",
                        "reason": f"{account_id} epoch is {acct['epoch']}, the claimant has {epoch}"}
            live = acct["profile_claimant"] and int(acct["profile_claim_epoch"]) == int(acct["epoch"])
            if live and acct["profile_claimant"] != who:
                return {"ok": False, "code": "PROFILE_CLAIMED",
                        "reason": f"{account_id}: the profile is owned by another lane of epoch {acct['epoch']}"}
            conn.execute("UPDATE accounts SET profile_claimant = ?, profile_claim_epoch = ?, updated_at = ? "
                         "WHERE account_id = ?", (who, int(epoch), _iso_now(), account_id))
            return {"ok": True, "code": "", "reason": ""}

    def release_profile(self, account_id: str, *, claimant: str) -> bool:
        with closing(self._connect()) as conn, self._tx(conn):
            return conn.execute("UPDATE accounts SET profile_claimant = '', profile_claim_epoch = 0, updated_at = ? "
                                "WHERE account_id = ? AND profile_claimant = ?",
                                (_iso_now(), account_id, claimant.strip())).rowcount == 1

    # ---- views ----------------------------------------------------------------------------------------------------
    def account_state(self, conn: sqlite3.Connection, acct: sqlite3.Row, ts: float, halted: bool) -> str:
        if acct["status"] == "COOLDOWN_QUARANTINE":
            return "QUARANTINED"
        if acct["status"] in ("NEEDS_LOGIN", "HALTED"):
            return acct["status"]
        if halted:
            return "HALTED"
        if conn.execute("SELECT 1 FROM leases WHERE account_id = ? AND state = ?", (acct["account_id"], UNCERTAIN)
                        ).fetchone():
            return "HELD"
        if conn.execute("SELECT 1 FROM leases WHERE account_id = ? AND state = 'ACTIVE'", (acct["account_id"],)
                        ).fetchone():
            return "BUSY"
        if acct["cooldown_until"] > ts:
            return "COOLDOWN"
        return "FREE"

    def accounts_view(self, *, now: float | None = None) -> list[dict[str, Any]]:
        """One row per account, by id and label only: state, film, children in flight (n/slots), quota or probe age,
        epoch, held reason. No CDP endpoint, profile path, cookie or token."""
        ts = float(time.time() if now is None else now)
        halted = self._halted()
        out = []
        with closing(self._connect()) as conn:
            for acct in conn.execute("SELECT * FROM accounts ORDER BY account_id").fetchall():
                lease = conn.execute("SELECT * FROM leases WHERE account_id = ? AND state IN (?, ?) ORDER BY leased_at "
                                     "DESC LIMIT 1", (acct["account_id"], *_HELD)).fetchone()
                n = 0
                kind = "video"
                if lease is not None:
                    kind = lease["job_kind"]
                    n = conn.execute("SELECT COUNT(*) FROM lease_children WHERE lease_key = ? AND lease_token = ? AND "
                                     "final = 0", (lease["lease_key"], lease["lease_token"])).fetchone()[0]
                slots = self._slots(acct).get(kind, 1)
                if acct["quota_mode"] == "probed":
                    age = None if acct["probed_at"] is None else round(ts - float(acct["probed_at"]))
                    quota = {"mode": "probed", "weekly_remaining_pct": acct["weekly_remaining_pct"],
                             "probe_age_s": age, "max_age_s": acct["probe_max_age_s"], "reserve_pct": acct["reserve_pct"],
                             "reprobe_requested": bool(acct["reprobe_requested"])}
                else:
                    quota = {"mode": "constant", "unit": acct["quota_unit"], "remaining": acct["credits"],
                             "daily_quota": acct["daily_quota"]}
                state = self.account_state(conn, acct, ts, halted)
                held = ""
                if state == "HELD" and lease is not None:
                    held = lease["note"]
                elif state in ("QUARANTINED", "NEEDS_LOGIN", "HALTED"):
                    held = acct["quarantined_reason"] or (self._halt_reason() if state == "HALTED" else "")
                out.append({"account": acct["account_id"], "label": acct["label"], "provider": acct["provider"],
                            "state": state, "film": lease["film_id"] if lease is not None else "",
                            "in_flight": f"{n}/{slots}", "job_kind": kind, "quota": quota, "epoch": int(acct["epoch"]),
                            "held_reason": held, "relogin_failures": int(acct["relogin_failures"])})
        return out

    def snapshot(self) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY account_id").fetchall()]
            leases = [{k: v for k, v in dict(r).items() if k != "lease_token"}   # a token is the holder's proof
                      for r in conn.execute("SELECT * FROM leases ORDER BY lease_key").fetchall()]
            return {"db": str(self.db_path), "schema_version": SCHEMA_VERSION,
                    "min_reserve_credits": self.min_reserve_credits, "cooldown_s": self.cooldown_s,
                    "accounts": accounts, "leases": leases}
