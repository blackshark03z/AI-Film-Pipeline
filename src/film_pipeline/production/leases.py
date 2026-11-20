"""Account leases for Flow sends (generate's side of ``agentic/lease_pool.py``).

Every live Flow send in ``generate()`` holds a lease from the machine-wide pool (``<state dir>/lease_pool.sqlite3``):
key ``<film_id>:<take_id>@<package>``, a fresh holder per generate call, the account pinned by ``account_scope`` /
``AFP_FLOW_ACCOUNT`` or chosen by the pool. Settings: ``AFP_LEASE_COOLDOWN_S`` (default 60 s between sends on one
account) and ``AFP_LEASE_MIN_RESERVE`` (default 20 credits an account keeps).

A rehearsal's mock send leases from a private pool inside the rehearsal package (``<film>/takes/lease_pool.sqlite3``,
one synthetic account, no cooldown, no reserve), so rehearsals exercise leases without the machine pool.

A send whose outcome is unknown (the sender raised, or an AMBIGUOUS result) leaves its lease
QUARANTINED_PENDING_RECONCILE: the account is not leased again until ``settle_take`` (``afp-film lease settle --film F
--take TID``) releases it, which it does only once the receipt is resolved (``afp-film reconcile`` first).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:   # imported lazily: agentic/__init__ pulls in the planner
    from film_pipeline.agentic.lease_pool import AccountLeasePool


BLOCKER = "NO_ACCOUNT_LEASE"
REHEARSAL_ACCOUNT = "rehearsal-mock"
REHEARSAL_DB = "lease_pool.sqlite3"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def machine_pool(db: Path | None = None) -> "AccountLeasePool":
    from film_pipeline.agentic.lease_pool import AccountLeasePool, default_db_path
    return AccountLeasePool(db or default_db_path(), min_reserve_credits=_env_float("AFP_LEASE_MIN_RESERVE", 20.0),
                            cooldown_s=_env_float("AFP_LEASE_COOLDOWN_S", 60.0))


def rehearsal_pool(root: Path, account: str | None = None) -> "tuple[AccountLeasePool, str]":
    """The rehearsal package's private pool with its synthetic account registered (idempotent)."""
    from film_pipeline.agentic.lease_pool import AccountLeasePool
    from film_pipeline.production.takes import takes_dir
    pool = AccountLeasePool(takes_dir(root) / REHEARSAL_DB, min_reserve_credits=0.0, cooldown_s=0.0, honor_halt=False)
    name = (account or "").strip() or REHEARSAL_ACCOUNT
    pool.register_account(name, 1e9)
    return pool, name


def lease_key(film_id: str, take_id: str, root: Path) -> str:
    """``<film_id>:<take_id>@<package>``: one send of one package copy (a worktree or rehearsal copy of the same film
    numbers its takes on its own, so its sends are distinct)."""
    import hashlib
    package = hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode()).hexdigest()[:10]
    return f"{film_id}:{take_id}@{package}"


def pinned_account(account_scope: str | None) -> str | None:
    """The account a send is pinned to (the argument, else ``AFP_FLOW_ACCOUNT``), or None for the pool's choice."""
    value = account_scope if account_scope is not None else os.environ.get("AFP_FLOW_ACCOUNT", "")
    return value.strip() or None


def settle_take(root: Path, take_id: str, *, db: Path | None = None) -> dict[str, Any]:
    """Release the lease of an already-sent take once its receipt is resolved (the uncertain-lease path). Spent credits
    follow the money ledger: the receipt's ``expected_credits`` when its (resolved) result is charged, else 0."""
    from film_pipeline.production.money import receipt_charged, receipt_result, unresolved_sends
    from film_pipeline.production.recovery import resolved_receipt
    from film_pipeline.production.takes import load_log, takes_dir
    root = Path(root)
    path = takes_dir(root) / "intents" / f"{take_id}.intent.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    key = str(receipt.get("lease_key") or "")
    if not key:
        raise ValueError(f"{take_id}: the receipt records no account lease")
    resolved = resolved_receipt(root, take_id, receipt)
    if receipt.get("sent") and unresolved_sends(load_log(root, receipt.get("film_id", "")), {take_id: resolved}):
        raise ValueError(f"{take_id}: the send is unresolved ({receipt_result(resolved)}); run afp-film reconcile first")
    spent = float(resolved.get("expected_credits") or 0.0) if receipt.get("sent") and receipt_charged(resolved) else 0.0
    db_file = Path(db) if db else Path(receipt["lease_db"]) if receipt.get("lease_db") else None
    if db_file is not None and db_file.resolve() == (takes_dir(root) / REHEARSAL_DB).resolve():
        # a rehearsal's private pool: no cooldown, no reserve, no halt (as when its send took the lease)
        from film_pipeline.agentic.lease_pool import AccountLeasePool
        pool = AccountLeasePool(db_file, min_reserve_credits=0.0, cooldown_s=0.0, honor_halt=False)
    else:
        pool = machine_pool(db_file)
    lease = pool.settle(key, credits_spent=spent, note=f"settled from receipt {take_id}: {resolved.get('result')}")
    return {"take_id": take_id, "lease": {k: v for k, v in lease.items() if k != "lease_token"}, "credits_spent": spent,
            "result": resolved.get("result")}
