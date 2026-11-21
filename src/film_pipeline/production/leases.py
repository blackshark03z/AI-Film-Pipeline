"""Account leases for Flow sends (generate's side of ``agentic/lease_pool.py``).

Every live send in ``generate()`` is admitted by the S1 broker (``agentic/broker.py``); a Flow send holds a lease
from the machine-wide pool (``<state dir>/lease_pool.sqlite3``):
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

import hashlib
import json
import math
import os
from datetime import date
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
    pool = AccountLeasePool(takes_dir(root) / REHEARSAL_DB, min_reserve_credits=0.0, cooldown_s=0.0, honor_halt=False,
                            machine_caps={}, provider_caps={})
    name = (account or "").strip() or REHEARSAL_ACCOUNT
    pool.register_account(name, 1e9)
    return pool, name


def _package_id(root: Path) -> str:
    import hashlib
    return hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode()).hexdigest()[:10]


def lease_key(film_id: str, take_id: str, root: Path) -> str:
    """``<film_id>:<take_id>@<package>``: one send of one package copy (a worktree or rehearsal copy of the same film
    numbers its takes on its own, so its sends are distinct)."""
    return f"{film_id}:{take_id}@{_package_id(root)}"


def film_scope(film_id: str, root: Path) -> str:
    """``<film_id>@<package>``: the broker's per-film budget scope. A package copy keeps its own ledger and numbers its
    takes on its own, so its reservations are its own."""
    return f"{film_id}@{_package_id(root)}"


def legacy_scan(films_dir: Path) -> dict[str, Any]:
    """Read the receipts of every film package in ``films_dir`` for ``Broker.import_legacy``. ``rows``: the sends made
    before S1 (sent, no ``broker`` flag): the charged amount in the receipt's unit on its ``sent_on`` day. ``problems``:
    every receipt whose spend cannot be known (unreadable, not a JSON object, a pre-S1 send without its day or with an
    unreadable amount), with its path and the sha256 of its bytes; none is skipped silently, the import stays
    incomplete until each is resolved. ``seen``: the key of every receipt read without a problem. Read without the
    other films' locks (receipts are written atomically), as the pre-S1 daily cap read them."""
    from film_pipeline.agentic.broker import UNITS, known_providers, valid_day
    from film_pipeline.production.money import receipt_charged
    from film_pipeline.production.takes import takes_dir
    rows: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    seen: list[str] = []
    providers = known_providers()
    folder_root = Path(films_dir)
    for other in sorted(folder_root.iterdir()) if folder_root.is_dir() else []:
        folder = takes_dir(other) / "intents"
        if not folder.is_dir():
            continue
        package = _package_id(other)
        header_id = _header_film_id(other)
        package_scope = film_scope(header_id, other) if header_id else ""
        for path in sorted(folder.glob("*.intent.json")):
            take_id = path.name[:-len(".intent.json")]
            key = f"{package}:{take_id}"

            def problem(why: str, data: bytes | None) -> None:
                problems.append({"key": key, "path": str(path), "problem": why, "film_key": package_scope,
                                 "sha256": hashlib.sha256(data).hexdigest() if data is not None else ""})
            try:
                data = path.read_bytes()
            except OSError as exc:
                problem(f"unreadable ({type(exc).__name__})", None)
                continue
            try:
                body = json.loads(data.decode("utf-8"))
            except ValueError:
                problem("not valid UTF-8 JSON", data)
                continue
            if not isinstance(body, dict):
                problem("not a JSON object", data)
                continue
            if not body.get("sent") or body.get("broker"):   # a dry run, or a send the broker already holds
                seen.append(key)
                continue
            # every field the spend is counted by must be stated in the receipt; nothing defaults silently, except
            # the one documented convention: a receipt without a provider or unit is a Flow receipt in credits
            # (every record before provider adapters is one), and only then
            sent_on = body.get("sent_on")
            if sent_on in (None, ""):
                # written before receipts carried their day: the file's last-modified local day is an upper bound
                # of the send day (a receipt is only rewritten after its send), so today's spend is never missed
                try:
                    sent_on = date.fromtimestamp(path.stat().st_mtime).isoformat()
                except OSError as exc:
                    problem(f"a pre-S1 send without sent_on whose file time is unreadable ({type(exc).__name__})",
                            data)
                    continue
            elif not valid_day(sent_on):
                problem(f"a pre-S1 send with an invalid sent_on day ({sent_on!r})", data)
                continue
            raw_unit, raw_provider = body.get("cost_unit"), body.get("provider")
            if raw_unit in (None, "") and raw_provider in (None, "", "flow"):
                unit, provider = "credits", "flow"
            elif raw_unit not in UNITS:
                problem(f"a pre-S1 send with no known cost_unit ({raw_unit!r})", data)
                continue
            elif raw_provider in (None, "") and raw_unit == "credits":
                unit, provider = "credits", "flow"
            elif raw_provider not in providers:
                problem(f"a pre-S1 send with no known provider ({raw_provider!r})", data)
                continue
            else:
                unit, provider = str(raw_unit), str(raw_provider)
            field_name = "expected_credits" if unit == "credits" else "expected_cost"
            price = body.get(field_name)
            if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price < 0:
                problem(f"a pre-S1 send without an explicit amount ({field_name}: {price!r})", data)
                continue
            body_id = body.get("film_id")
            if body_id is not None and not (isinstance(body_id, str) and body_id.strip()):
                problem(f"a pre-S1 send with an invalid film_id ({body_id!r})", data)
                continue
            if header_id and body_id and body_id != header_id:
                problem(f"a pre-S1 send of film {body_id!r} in the package of {header_id!r}", data)
                continue
            film_id = header_id or body_id
            if not film_id:
                problem("a pre-S1 send whose film is unknown (no film_id, film.json unreadable)", data)
                continue
            try:
                charged = receipt_charged(body)
            except (KeyError, ValueError):
                charged = True   # an unknown route: count it (never undercount money)
            price = float(price)
            rows.append({"key": key, "lease_key": str(body.get("lease_key") or ""),
                         "take_id": take_id, "account": str(body.get("account") or ""),
                         "film_key": film_scope(film_id, other), "provider": provider,
                         "unit": unit, "amount": price if charged else 0.0,
                         "price": price, "day": sent_on})
            seen.append(key)
    return {"rows": rows, "problems": problems, "seen": seen}


def _header_film_id(package: Path) -> str:
    """The ``film_id`` of a package's ``film.json`` ('' when it cannot be read)."""
    try:
        head = json.loads((Path(package) / "film.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    film_id = head.get("film_id") if isinstance(head, dict) else None
    return film_id.strip() if isinstance(film_id, str) else ""


def import_films_dir(pool: Any, films_dir: Path) -> dict[str, Any]:
    """``pool.import_legacy`` of everything ``legacy_scan`` read in ``films_dir`` (rows, problems, seen keys)."""
    scan = legacy_scan(films_dir)
    return pool.import_legacy(films_dir, scan["rows"], problems=scan["problems"], seen=scan["seen"])


def import_legacy_spend(pool: Any, root: Path) -> str:
    """Import the pre-S1 spend of ``root``'s films directory (its siblings and itself) into ``pool`` (idempotent, one
    row per receipt) and return the directory key admission checks (``AdmitRequest.legacy_root``). An unreadable
    receipt leaves the import incomplete: capped admission is then refused (LEGACY_RECEIPT_UNREADABLE). Reads files:
    call it outside film_lock and outside any broker transaction."""
    return import_films_dir(pool, Path(root).resolve().parent)["root"]


def pinned_account(account_scope: str | None) -> str | None:
    """The account a send is pinned to (the argument, else ``AFP_FLOW_ACCOUNT``), or None for the pool's choice."""
    value = account_scope if account_scope is not None else os.environ.get("AFP_FLOW_ACCOUNT", "")
    return value.strip() or None


def settle_take(root: Path, take_id: str, *, db: Path | None = None) -> dict[str, Any]:
    """Release the lease of an already-sent take once its receipt is resolved (the uncertain-lease path). The spend
    follows the money ledger: the receipt's expected amount in its own unit when its (resolved) result is charged,
    else 0."""
    from film_pipeline.production.money import receipt_amount, receipt_charged, receipt_result, unresolved_sends
    from film_pipeline.production.recovery import resolved_receipt
    from film_pipeline.production.takes import load_log, takes_dir
    from film_pipeline.production.runtime import film_lock
    root = Path(root)
    path = takes_dir(root) / "intents" / f"{take_id}.intent.json"
    # F2: read and validate the receipt evidence under film_lock, release it, then settle through the broker
    with film_lock(root, timeout_s=15.0):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        key = str(receipt.get("lease_key") or "")
        if not key:
            raise ValueError(f"{take_id}: the receipt records no account lease")
        resolved = resolved_receipt(root, take_id, receipt)
        if receipt.get("sent") and unresolved_sends(load_log(root, receipt.get("film_id", "")), {take_id: resolved}):
            raise ValueError(f"{take_id}: the send is unresolved ({receipt_result(resolved)}); run afp-film reconcile "
                             f"first")
        spent = receipt_amount(resolved) if receipt.get("sent") and receipt_charged(resolved) else 0.0
    db_file = Path(db) if db else Path(receipt["lease_db"]) if receipt.get("lease_db") else None
    if db_file is not None and db_file.resolve() == (takes_dir(root) / REHEARSAL_DB).resolve():
        # a rehearsal's private pool: no cooldown, no reserve, no halt (as when its send took the lease)
        from film_pipeline.agentic.lease_pool import AccountLeasePool
        pool = AccountLeasePool(db_file, min_reserve_credits=0.0, cooldown_s=0.0, honor_halt=False, machine_caps={},
                                provider_caps={})
    else:
        pool = machine_pool(db_file)
    lease = pool.settle(key, credits_spent=spent, note=f"settled from receipt {take_id}: {resolved.get('result')}")
    return {"take_id": take_id, "lease": {k: v for k, v in lease.items() if k != "lease_token"}, "credits_spent": spent,
            "result": resolved.get("result")}
