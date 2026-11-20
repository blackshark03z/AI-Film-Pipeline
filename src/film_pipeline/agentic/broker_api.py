"""The broker's stable public API for external lane processes (S1; e.g. ``python -m muse_studio.pool_runner``).

Every function opens the machine broker (``<state dir>/lease_pool.sqlite3``, or ``db``), runs one short transaction
and returns a JSON-serialisable dict with at least ``ok`` (bool), ``code`` (str) and ``reason`` (str). The same
operations are CLI verbs: ``afp-film broker acquire|check|mark|release|settle|halt|login-check|login-result|claim|
probe|import-legacy`` print that dict as JSON and exit
with ``EXIT_*`` below.

Only account ids, lease keys/tokens, child keys and amounts cross this API: never a cookie, password, profile path
or CDP endpoint. A halt set here is never cleared automatically (``afp-film halt clear --by ... --reason ...``).

Lane protocol for one batch:
  1. ``acquire(account_id, lease_key, children, ...)``: the exclusive batch lease and its reservations, or a refusal.
  2. per child, immediately before the provider Enter: ``check_before_enter(...)`` (= mark SUBMITTING). ``ok`` False
     means NOT_SENT: do not press Enter; the child is closed, nothing is charged.
  3. per child once its outcome is known: ``mark(..., state=<final outcome>, spent=...)``, or ``state="AMBIGUOUS"``
     when it is unknown (the account stays HELD until ``settle``).
  4. ``release(lease_key, lease_token)`` gives back children that never reached the Enter.
  5. ``settle(lease_key, child_key, spent)`` after reconcile resolves an AMBIGUOUS child (no token).
  CAPTCHA / verification / unusual activity: ``halt(provider, account_id, reason, kind)``.
  Re-login (only an expired login): ``check_before_login(...)`` right before the attempt, then ``login_result(...)``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from film_pipeline.agentic.broker import WARNING_KINDS, AdmitRequest, Broker, Child, default_db_path

EXIT_OK = 0          # done (a check that says go, a lease taken, a child marked, ...)
EXIT_REFUSED = 1     # refused by policy: NOT_SENT, no lease, halt, epoch, cap
EXIT_USAGE = 2       # bad arguments
EXIT_ERROR = 3       # unknown lease/account, token mismatch, database error

FINAL_STATES = ("PASSED", "PROVIDER_FAILED", "REJECTED_POLICY", "NOT_SUBMITTED", "NOT_SENT")
MARK_STATES = ("SUBMITTING", "AMBIGUOUS", *FINAL_STATES)


def _broker(db: str | Path | None) -> Broker:
    """The machine broker with the same settings as direct generate (``AFP_LEASE_COOLDOWN_S``, ``AFP_LEASE_MIN_RESERVE``)."""
    from film_pipeline.production.leases import _env_float
    return Broker(Path(db) if db else default_db_path(), min_reserve_credits=_env_float("AFP_LEASE_MIN_RESERVE", 20.0),
                  cooldown_s=_env_float("AFP_LEASE_COOLDOWN_S", 60.0))


def _ok(**extra: Any) -> dict[str, Any]:
    return {"ok": True, "code": "OK", "reason": "", **extra}


def _no(code: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "code": code, "reason": reason, **extra}


def exit_code(result: dict[str, Any]) -> int:
    """The CLI exit code of a result dict."""
    if result.get("ok"):
        return EXIT_OK
    return {"USAGE": EXIT_USAGE, "ERROR": EXIT_ERROR, "NOT_FOUND": EXIT_ERROR,
            "TOKEN_MISMATCH": EXIT_ERROR}.get(str(result.get("code")), EXIT_REFUSED)


def _guard(fn):
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except KeyError as exc:
            return _no("NOT_FOUND", str(exc.args[0] if exc.args else exc))
        except ValueError as exc:
            code = "TOKEN_MISMATCH" if "lease_token" in str(exc) else "USAGE"
            return _no(code, str(exc))
        except (sqlite3.Error, OSError) as exc:   # a busy or broken broker DB is an error, never a traceback
            return _no("ERROR", f"{type(exc).__name__}: {exc}")
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


def _public_lease(lease: dict[str, Any]) -> dict[str, Any]:
    keep = ("lease_key", "lease_token", "account_id", "provider", "job_kind", "film_id", "epoch", "day", "unit",
            "state", "holder")
    return {**{k: lease.get(k) for k in keep}, "children": [
        {k: c.get(k) for k in ("child_key", "take_id", "phase", "outcome", "final")} for c in lease.get("children", [])]}


def _film_admission(film_root: str | Path | None, unit: str, broker: Broker) -> dict[str, Any]:
    """The authoritative film side of an admission, resolved from the film package itself (fail closed): its id, the
    per-film budget scope shared with direct ``afp-film generate`` (``<film_id>@<package>``), its cap in ``unit``, its
    ledger spend and counted takes (read under film_lock, released before the broker is touched: F2), and its films
    directory's pre-S1 spend imported into the broker. ``{"ok": False, ...}`` when any of it is unavailable."""
    from film_pipeline.production import leases as L
    from film_pipeline.production.generate import film_budget
    from film_pipeline.production.package import load_package
    from film_pipeline.production.runtime import film_lock
    if not film_root or not str(film_root).strip():
        return _no("FILM_BUDGET_UNAVAILABLE", "acquire needs the film package (--film): its budget scopes the admission")
    root = Path(film_root)
    if not (root / "film.json").is_file():
        return _no("FILM_BUDGET_UNAVAILABLE", f"{root} is not a film package (no film.json)")
    try:
        with film_lock(root, timeout_s=15.0):
            pkg = load_package(root)
            numbers = film_budget(pkg, unit)
    except Exception as exc:   # an unreadable package or a busy film: no budget, no admission
        return _no("FILM_BUDGET_UNAVAILABLE", f"{root}: {type(exc).__name__}: {exc}"[:300])
    film_id = pkg.header.film_id
    cap = numbers["film_cap"]
    if cap is None and not (numbers["experiment"] and broker.machine_caps.get(unit) is not None):
        # as generate's BUDGET_NOT_SET: only an experiment film is held by the machine daily cap alone
        return _no("BUDGET_NOT_SET", f"{film_id}: film.json budget has no cap in {unit}")
    legacy_root = L.import_legacy_spend(broker, root)
    return _ok(film_id=film_id, film_key=L.film_scope(film_id, root), film_cap=cap,
               film_baseline=numbers["film_baseline"], film_counted=numbers["film_counted"], legacy_root=legacy_root)


@_guard
def acquire(account_id: str, lease_key: str, children: list[dict[str, Any]], *, unit: str, provider: str,
            film_root: str | Path | None, job_kind: str = "video", holder: str = "", epoch: int | None = None,
            day: str | None = None, db: str | Path | None = None) -> dict[str, Any]:
    """Take the exclusive batch lease of ``account_id`` for ``children`` (``[{"child_key", "amount", "take_id"?,
    "shot_key"?}]``, 1..slots of one film and one job kind) and reserve their amounts in ``unit`` against the account
    quota, the film's budget (resolved from ``film_root``, the film package: fail closed without it), the provider's
    and the machine's daily caps. Returns ``{"ok": True, "lease": {..., "lease_token"}}`` or a refusal (``code``:
    PRODUCTION_HALT, NO_ACCOUNT_LEASE, LEASE_HELD, STALE_EPOCH, NO_PRICE, BATCH_INVALID, FILM_BUDGET_UNAVAILABLE,
    BUDGET_NOT_SET, LEGACY_IMPORT_PENDING or a cap code; ``reprobe``: accounts to probe again)."""
    if not (account_id or "").strip():
        return _no("USAGE", "acquire needs an account id")
    if not (provider or "").strip():
        return _no("USAGE", "acquire needs the provider")
    kids = [Child(str(c["child_key"]), None if c.get("amount") is None else float(c["amount"]),
                  take_id=str(c.get("take_id") or ""), shot_key=str(c.get("shot_key") or "")) for c in children]
    broker = _broker(db)
    film = _film_admission(film_root, unit, broker)
    if not film["ok"]:
        return film
    out = broker.admit(AdmitRequest(
        lease_key=lease_key, children=kids, unit=unit, provider=provider, job_kind=job_kind, film_id=film["film_id"],
        film_key=film["film_key"], holder=holder or None, account_id=account_id, epoch=epoch, day=day,
        film_cap=film["film_cap"], film_baseline=film["film_baseline"], film_counted=film["film_counted"],
        legacy_root=film["legacy_root"]))
    if not out["ok"]:
        return _no(out["code"], out["reason"], reprobe=out.get("reprobe", []))
    return _ok(lease=_public_lease(out["lease"]))


@_guard
def check_before_login(account_id: str, *, cause: str, epoch: int, lease_key: str = "", lease_token: str = "",
                       claimant: str = "", db: str | Path | None = None) -> dict[str, Any]:
    """Immediately before a re-login attempt, in one transaction: the halt, the account status, the lane's epoch and its
    ownership of the account (its lease token or its profile claim), the cause (only AUTH_EXPIRED) and the throttle
    (one attempt per account per 2 h). ``ok`` False: do not log in."""
    out = _broker(db).before_login(account_id, cause=cause, epoch=epoch, lease_key=lease_key or None,
                                   lease_token=lease_token or None, claimant=claimant or None)
    return _ok() if out["go"] else _no("LOGIN_REFUSED", out["reason"], cause=out["code"])


@_guard
def login_result(account_id: str, *, ok: bool, db: str | Path | None = None) -> dict[str, Any]:
    """The result of an authorised re-login attempt; the 2nd consecutive failure marks the account NEEDS_LOGIN."""
    acct = _broker(db).record_login_result(account_id, ok=ok)
    return _ok(account_status=acct["status"], relogin_failures=int(acct["relogin_failures"]))


@_guard
def claim_profile(account_id: str, *, claimant: str, epoch: int, db: str | Path | None = None) -> dict[str, Any]:
    """A lane claims its account's browser profile for its life (non-blocking: a live claim of another lane refuses)."""
    out = _broker(db).claim_profile(account_id, claimant=claimant, epoch=epoch)
    return _ok() if out["ok"] else _no(out["code"], out["reason"])


@_guard
def probe(account_id: str, *, weekly_remaining_pct: float, db: str | Path | None = None) -> dict[str, Any]:
    """Record a quota probe (Muse: ``weekly_remaining_pct`` from the Settings page)."""
    acct = _broker(db).record_probe(account_id, weekly_remaining_pct)
    return _ok(account_id=acct["account_id"], weekly_remaining_pct=acct["weekly_remaining_pct"])


@_guard
def import_legacy(films_dir: str | Path, *, db: str | Path | None = None) -> dict[str, Any]:
    """Import the pre-S1 spend of every film package in ``films_dir`` (idempotent, one row per receipt). A receipt
    that cannot be read leaves the import incomplete: refused (LEGACY_RECEIPT_UNREADABLE, exit 1) with the
    ``unresolved`` keys; capped admission stays refused until each is repaired or resolved (``import_resolve``)."""
    from film_pipeline.production import leases as L
    if not Path(films_dir).is_dir():
        return _no("USAGE", f"{films_dir} is not a directory")
    out = L.import_films_dir(_broker(db), Path(films_dir))
    if not out["complete"]:
        return _no("LEGACY_RECEIPT_UNREADABLE", f"{len(out['unresolved'])} pre-S1 receipt(s) could not be read; "
                   f"repair them and import again, or record each with import-resolve", **out)
    return _ok(**out)


@_guard
def import_resolve(films_dir: str | Path, key: str, *, by: str, reason: str, amount: float | None = None,
                   unit: str = "", day: str = "", provider: str = "", db: str | Path | None = None) -> dict[str, Any]:
    """Operator: reconcile one unreadable pre-S1 receipt (``key`` as import-legacy listed it), with who and why
    recorded; ``amount`` > 0 (with ``unit``, ``day``, ``provider``) records what it charged, none: it charged
    nothing."""
    if not key:
        return _no("USAGE", "import-resolve needs --key")
    return _ok(**_broker(db).resolve_legacy(films_dir, key, by=by, reason=reason, amount=amount, unit=unit, day=day,
                                            provider=provider))


@_guard
def check_before_enter(lease_key: str, lease_token: str, child_key: str, *, epoch: int | None = None,
                       db: str | Path | None = None) -> dict[str, Any]:
    """Immediately before the provider Enter, in one transaction: halt + epoch + lease. ``ok`` True: the child is now
    SUBMITTING, press Enter. ``ok`` False (``code`` NOT_SENT, ``cause`` PRODUCTION_HALT / STALE_EPOCH / LEASE_LOST /
    ACCOUNT_NOT_ACTIVE / CHILD_NOT_PREPARING): do not press Enter; the child is closed NOT_SENT."""
    out = _broker(db).before_enter(lease_key, lease_token=lease_token, child_key=child_key, epoch=epoch)
    if out["go"]:
        return _ok(phase="SUBMITTING")
    return _no("NOT_SENT", out["reason"], cause=out["code"])


@_guard
def mark(lease_key: str, lease_token: str, child_key: str, state: str, *, spent: float = 0.0, reason: str = "",
         epoch: int | None = None, db: str | Path | None = None) -> dict[str, Any]:
    """Mark one child: SUBMITTING (only through ``check_before_enter``), AMBIGUOUS (outcome unknown: the account
    stays HELD until ``settle``), or a final outcome (PASSED, PROVIDER_FAILED, REJECTED_POLICY, NOT_SUBMITTED;
    ``spent`` > 0 turns the reservation into a spend). NOT_SENT closes a child that never reached the Enter."""
    state = state.strip().upper()
    if state not in MARK_STATES:
        return _no("USAGE", f"state must be one of {MARK_STATES}")
    broker = _broker(db)
    if state == "SUBMITTING":
        return check_before_enter(lease_key, lease_token, child_key, epoch=epoch, db=db)
    if state == "AMBIGUOUS":
        lease = broker.hold_child(lease_key, lease_token=lease_token, child_key=child_key,
                                  reason=reason or "outcome unknown")
        return _ok(lease_state=lease["state"])
    if state == "NOT_SENT":
        out = broker.release_unsent(lease_key, lease_token=lease_token, child_key=child_key)
        if out["uncertain"]:
            return _no("CHILD_PAST_ENTER", f"{child_key} passed the pre-Enter check: mark its outcome or AMBIGUOUS")
        return _ok(released=out["released"])
    lease = broker.finish_child(lease_key, lease_token=lease_token, child_key=child_key, outcome=state,
                                spent=float(spent))
    return _ok(lease_state=lease["state"])


@_guard
def release(lease_key: str, lease_token: str, *, db: str | Path | None = None) -> dict[str, Any]:
    """Give back every child that never reached the Enter (token required): NOT_SENT, no charge, no cooldown. A child
    past the Enter is never released here (``uncertain``): mark its outcome, AMBIGUOUS, or settle it."""
    if not lease_token:
        return _no("USAGE", "release needs the lease token")
    out = _broker(db).release_unsent(lease_key, lease_token=lease_token)
    return _ok(**out)


@_guard
def settle(lease_key: str, *, spent: float, child_key: str | None = None, note: str = "",
           db: str | Path | None = None) -> dict[str, Any]:
    """The reconcile path (no token): give a held/open child (or all of them) its resolved spend."""
    lease = _broker(db).settle_child(lease_key, spent=float(spent), child_key=child_key, note=note)
    return _ok(lease_state=lease["state"])


@_guard
def halt(provider: str, account_id: str, reason: str, *, kind: str = "ACCOUNT_WARNING",
         db: str | Path | None = None) -> dict[str, Any]:
    """CAPTCHA, verification or unusual activity on ``account_id``: quarantine it, hold its in-flight children and set
    the machine-wide halt, in one broker transaction. Never cleared automatically."""
    if kind not in WARNING_KINDS:
        return _no("USAGE", f"kind must be one of {WARNING_KINDS}")
    if not (account_id or "").strip() or not (provider or "").strip():
        return _no("USAGE", "halt needs a provider and an account id")
    why = f"{kind} on {provider}/{account_id}: {(reason or '').strip() or 'account warning'}"[:300]
    source = f"lane:{provider.strip()}"
    broker = _broker(db)
    try:
        acct = broker.account_warning(account_id.strip(), why, kind=kind, source=source)
    except KeyError:   # an account the broker does not know: the halt is set all the same, under this broker's lock
        from film_pipeline.production.halt import set_halt
        set_halt(why, source=source, account=account_id.strip(), evidence=kind, db=broker.db_path)
        return _ok(account_id=account_id.strip(), account_status="UNREGISTERED", halted=True)
    return _ok(account_id=acct["account_id"], account_status=acct["status"], halted=True)
