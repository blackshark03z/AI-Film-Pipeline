"""The step-4 lease pool API on top of the S1 broker (``agentic/broker.py``).

One machine-wide database is the authority for which account a send may use: ``default_db_path()`` is
``<state dir>/lease_pool.sqlite3`` (the same state dir as the production halt: ``$AFP_STATE_DIR`` else ``~/.afp``), so
every caller, process and film shares it. A lease belongs to one ``holder``: an ACTIVE lease is handed back only to the
holder that took it (idempotent for that holder), never to anyone else. ``release`` needs the lease token.

Lease states: ``ACTIVE`` (held), ``RELEASED`` (settled), ``QUARANTINED_PENDING_RECONCILE`` (uncertain: the send's outcome is
unknown or the account warned). An account with an ACTIVE or uncertain lease is never selected. An uncertain lease is
settled with ``settle`` once the send's receipt is resolved (``afp-film lease settle --film F --take TID``).

Each step-4 lease is a broker batch of one child (child key = lease key) priced in credits; the broker opens the same
database file and migrates it in place (``PRAGMA user_version`` 2).
"""
from __future__ import annotations

import time
from typing import Any

from film_pipeline.agentic.broker import (  # noqa: F401  (re-exported: the step-4 names)
    DB_FILENAME, UNCERTAIN, AdmitRequest, Broker, Child, default_db_path, new_holder, process_holder,
)
from film_pipeline.production.halt import _BY_RE, is_halted, read_halt

_HELD = ("ACTIVE", UNCERTAIN)


def _lease_key(generation_id: str, *, film_id: str = "", shot_version: int = 1) -> str:
    fid = film_id.strip()
    if fid:
        return f"{fid}:{generation_id}:v{int(shot_version)}"
    if int(shot_version) != 1:
        return f"{generation_id}:v{int(shot_version)}"
    return generation_id


class AccountLeasePool(Broker):
    """Atomic lease manager for multi-account provider execution, shared across processes and films (step-4 API)."""

    def __init__(self, db_path=None, *, min_reserve_credits: float = 20.0, cooldown_s: float = 60.0,
                 honor_halt: bool = True, **kw: Any) -> None:
        super().__init__(db_path, min_reserve_credits=min_reserve_credits, cooldown_s=cooldown_s,
                         honor_halt=honor_halt, **kw)

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
        key = lease_key or _lease_key(generation_id, film_id=film_id, shot_version=shot_version)
        # the step-4 identity: one child and take per acquire of the key (``key#n``), shot version ``<generation>:v<n>``
        from contextlib import closing
        with closing(self._connect()) as conn:
            n = conn.execute("SELECT COUNT(*) FROM reservations WHERE lease_key = ?", (key,)).fetchone()[0]
        child = Child(f"{key}#{n}", float(cost_credits), take_id=f"{key}#{n}",
                      shot_key=f"{generation_id}:v{int(shot_version)}")
        out = self.admit(AdmitRequest(lease_key=key, children=[child], unit="credits",
                                      film_id=film_id.strip() or "step4", generation_id=generation_id,
                                      shot_version=shot_version, holder=holder, account_id=account_id, now=now))
        return (out["lease"], "") if out["ok"] else (None, out["reason"])

    def acquire(self, generation_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Atomically lease ``generation_id`` (or ``lease_key``) to an eligible healthy account under BEGIN IMMEDIATE.

        An existing ACTIVE lease for the key is never returned again (its token was issued once): None.
        ``account_id`` pins the account. Keywords: see ``acquire_or_reason``."""
        return self.acquire_or_reason(generation_id, **kwargs)[0]

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
        """Release a lease the caller holds with its known outcome: the matching ``lease_token`` is required."""
        key = lease_key or _lease_key(generation_id, film_id=film_id, shot_version=shot_version)
        if not lease_token:
            raise ValueError(f"lease_token is required to release {key!r} (an uncertain lease: lease settle)")
        ts = float(time.time() if now is None else now)
        with self.transaction() as conn:
            lease, children = self._lease_and_child(conn, key, lease_token, None)
            if lease["state"] == "RELEASED":
                return dict(lease)
            for i, child in enumerate(children):
                self._close_child(conn, lease, child, "RELEASED", float(credits_spent) if i == 0 else 0.0, ts,
                                  cooldown=cooldown_s)
            self._settle_batch(conn, key, ts, cooldown_s)
            return dict(conn.execute("SELECT * FROM leases WHERE lease_key = ?", (key,)).fetchone())

    def mark_uncertain(self, lease_key: str, *, lease_token: str, reason: str) -> dict[str, Any]:
        """The holder lost track of its send (crash, unknown outcome): keep the lease held as QUARANTINED_PENDING_RECONCILE
        so its account is not reused until ``settle``. The account itself stays ACTIVE and no halt is set."""
        return self.hold_child(lease_key, lease_token=lease_token, reason=reason)

    def settle(self, lease_key: str, *, credits_spent: float, note: str = "", cooldown_s: float | None = None,
               now: float | None = None) -> dict[str, Any]:
        """Release a held (ACTIVE or uncertain) lease without its token. Only for the reconcile path: call it once the
        send's receipt is resolved (``production.leases.settle_take`` checks that)."""
        return self.settle_child(lease_key, spent=credits_spent, note=note, cooldown_s=cooldown_s, now=now)

    def quarantine_account(self, account_id: str, reason: str, *, release_active_leases: bool = False) -> dict[str, Any]:
        """Put an account into COOLDOWN_QUARANTINE and halt the machine; retains unresolved leases unless proven
        NOT_SUBMITTED (``release_active_leases``)."""
        return self.account_warning(account_id, reason, release_active_leases=release_active_leases)

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
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (aid,)).fetchone()
            if row is None:
                raise KeyError(f"unknown account {aid!r}")
            if row["status"] != "COOLDOWN_QUARANTINE":
                raise ValueError(f"account {aid} is {row['status']}, not quarantined")
            from film_pipeline.agentic.broker import _iso_now
            at = _iso_now()
            conn.execute("UPDATE accounts SET status = 'ACTIVE', quarantined_reason = '', updated_at = ? "
                         "WHERE account_id = ?", (at, aid))
            conn.execute("INSERT INTO account_history (at, account_id, action, by, reason, prior_status, prior_reason) "
                         "VALUES (?, ?, 'unquarantine', ?, ?, ?, ?)",
                         (at, aid, by, reason.strip(), row["status"], row["quarantined_reason"]))
            return {"account_id": aid, "action": "unquarantine", "at": at, "by": by, "reason": reason.strip(),
                    "prior_status": row["status"], "prior_reason": row["quarantined_reason"]}
