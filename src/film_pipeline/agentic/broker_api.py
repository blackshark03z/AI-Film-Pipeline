"""The broker's stable public API for external lane processes (S1; e.g. ``python -m muse_studio.pool_runner``).

Every function opens the machine broker (``<state dir>/lease_pool.sqlite3``, or ``db``), runs one short transaction
and returns a JSON-serialisable dict with at least ``ok`` (bool), ``code`` (str) and ``reason`` (str). The same
operations are CLI verbs: ``afp-film broker acquire|check|mark|release|settle|halt|login-check|login-result|claim|
probe|import-legacy|import-resolve|status|allocator-claim|allocator-release|settle-not-sent`` print that dict as JSON and exit with ``EXIT_*`` below.

Only account ids, lease keys, child keys and amounts cross this API: never a cookie, password, profile path or CDP
endpoint. The lease token is returned once, by the ``acquire`` that created the lease (a replay is ``LEASE_EXISTS``,
without it); it never appears in any other result, error or log. A lane keeps it in memory and gives it to the CLI on
stdin (``--token-stdin``: one JSON line ``{"lease_token": "..."}``), never on the command line (``--token`` is for
tests). A halt set here is never cleared automatically (``afp-film halt clear --by ... --reason ...``).

Admission and the pre-Enter check refuse unless the allocator claim (``allocator_owner.json`` in the state dir) exists
and names ``afp-broker`` (``ALLOCATOR_UNKNOWN`` when it is missing or unreadable); ``allocator_claim`` writes it,
``allocator_release`` removes it. Both also honour the Muse halt file (``$MUSE_HALT_FILE``). Lock order:
broker transaction (BEGIN IMMEDIATE) -> halt-file lock (``halt_file_lock_path()``), the lock held until COMMIT; Muse
publishes its halt holding only the halt-file lock (``halt_file_lock()``), never a broker transaction inside it.

Lane protocol for one batch:
  1. ``acquire(account_id, lease_key, children, ...)``: the exclusive batch lease and its reservations, or a refusal.
     Every child names its take id and shot version; one unresolved child per film + shot version on the machine.
  2. immediately before the provider Enter: ``check_before_enter(lease_key, token, child_keys=[...],
     incarnation=<this lane process>)``: every named child goes PREPARING -> SUBMITTING in one transaction, or none.
     ``ok`` True: press Enter. ``code`` NOT_SENT_PROVEN: do not press Enter; the broker closed the children NOT_SENT.
     Any other refusal (``ALREADY_SUBMITTING``: a check already passed, its reply was lost) is POSSIBLY SENT
     (``possibly_sent`` True): never press Enter again, treat the children as AMBIGUOUS and reconcile.
  3. per child once its outcome is known: ``mark(..., state=<final outcome>, spent=...)``, or ``state="AMBIGUOUS"``
     when it is unknown (the account stays HELD until ``settle``). A child that passed the check but whose Enter this
     same lane incarnation provably never issued: ``mark(..., state="NOT_SENT", reason="ENTER_NOT_ISSUED ...",
     incarnation=..., epoch=...)``; refused (and held AMBIGUOUS) unless the lease is still live under this token, epoch
     and incarnation.
  4. ``release(lease_key, lease_token)`` gives back children that never reached the Enter.
  5. ``settle(lease_key, child_key, spent)`` after reconcile resolves an AMBIGUOUS child (no token).
     ``settle_not_sent(child_key, evidence)`` closes a child still PREPARING as NOT_SENT and fences it (SUBMITTING:
     refused, possibly sent).
  CAPTCHA / verification / unusual activity: ``halt(provider, account_id, reason, kind)``.
  Re-login (only an expired login): ``check_before_login(...)`` right before the attempt, then ``login_result(...)``.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from film_pipeline.agentic.broker import (SCHEMA_VERSION, WARNING_KINDS, AdmitRequest, Broker, Child,
                                          default_db_path)

EXIT_OK = 0          # done (a check that says go, a lease taken, a child marked, ...)
EXIT_REFUSED = 1     # refused by policy: NOT_SENT_PROVEN, ALREADY_SUBMITTING, no lease, halt, epoch, cap
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
    """Take the exclusive batch lease of ``account_id`` for ``children`` (``[{"child_key", "amount", "take_id",
    "shot_key"}]``, 1..slots of one film and one job kind; take id and shot version are required) and reserve their
    amounts in ``unit`` against the account quota, the film's budget (resolved from ``film_root``, the film package:
    fail closed without it), the provider's and the machine's daily caps. Returns ``{"ok": True, "lease": {...,
    "lease_token"}}`` (the only result that carries the token) or a refusal (``code``: PRODUCTION_HALT,
    HALT_PENDING, ALLOCATOR_NOT_OWNED, ALLOCATOR_UNKNOWN, NO_ACCOUNT_LEASE, CHILD_FENCED, LEASE_HELD, LEASE_EXISTS (a replay: the token is never
    re-issued), SHOT_VERSION_UNRESOLVED, TAKE_REUSED, STALE_EPOCH, NO_PRICE, BATCH_INVALID, FILM_BUDGET_UNAVAILABLE,
    BUDGET_NOT_SET, LEGACY_IMPORT_PENDING or a cap code; ``reprobe``: accounts to probe again)."""
    if not (account_id or "").strip():
        return _no("USAGE", "acquire needs an account id")
    if not (provider or "").strip():
        return _no("USAGE", "acquire needs the provider")
    kids = [Child(str(c["child_key"]), None if c.get("amount") is None else float(c["amount"]),
                  take_id=str(c.get("take_id") or ""), shot_key=str(c.get("shot_key") or "")) for c in children]
    if not all(k.take_id.strip() and k.shot_key.strip() for k in kids):
        return _no("BATCH_INVALID", "every child names its take_id and shot_key")
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
    recorded; ``amount`` > 0 (with ``unit``, ``day``, ``provider``) records what it charged against the film of the
    receipt's package, none: it charged nothing. An invalid unit, day or provider, or an unknown film scope: USAGE,
    nothing changes."""
    if not key:
        return _no("USAGE", "import-resolve needs --key")
    return _ok(**_broker(db).resolve_legacy(films_dir, key, by=by, reason=reason, amount=amount, unit=unit, day=day,
                                            provider=provider))


@_guard
def check_before_enter(lease_key: str, lease_token: str, child_key: str | None = None, *,
                       child_keys: list[str] | None = None, epoch: int | None = None, incarnation: str = "",
                       db: str | Path | None = None) -> dict[str, Any]:
    """Immediately before the provider Enter, in one transaction holding the halt-file lock until COMMIT: lease (token,
    ACTIVE), halt (AFP and Muse), allocator claim, account and epoch; then EVERY child (``child_key``, or the batch
    ``child_keys``) goes PREPARING -> SUBMITTING bound to ``incarnation`` (the lane process), or none does.

    * ``ok`` True: press Enter (``phase`` SUBMITTING).
    * ``code`` NOT_SENT_PROVEN (``cause``: PRODUCTION_HALT, HALT_PENDING, STALE_EPOCH, LEASE_LOST,
      ACCOUNT_NOT_ACTIVE, ALLOCATOR_NOT_OWNED, ALLOCATOR_UNKNOWN, ALREADY_NOT_SENT; ``possibly_sent`` False): the only
      proven pre-submit refusal, given only while every named child is still PREPARING (or already NOT_SENT and
      fenced). Do not press Enter; the broker closed every named child terminal NOT_SENT and fenced it in this same
      transaction.
    * ``code`` ALREADY_SUBMITTING: a child already passed this check (a lost reply): possibly sent. Never press Enter
      again; treat it as AMBIGUOUS (``mark(..., "AMBIGUOUS")``) and reconcile.
    * any other refusal (CHILD_NOT_PREPARING, LEASE_LOST with no child under this token): possibly sent too
      (``possibly_sent`` True); nothing was changed."""
    out = _broker(db).before_enter(lease_key, lease_token=lease_token, child_key=child_key, child_keys=child_keys,
                                   epoch=epoch, incarnation=incarnation)
    if out["go"]:
        return _ok(phase="SUBMITTING", children=out["children"])
    if out["proven"]:
        return _no("NOT_SENT_PROVEN", out["reason"], cause=out["code"], possibly_sent=False, children=out["children"])
    return _no(out["code"], out["reason"], possibly_sent=True, children=out["children"])


@_guard
def mark(lease_key: str, lease_token: str, child_key: str, state: str, *, spent: float = 0.0, reason: str = "",
         epoch: int | None = None, incarnation: str = "", db: str | Path | None = None) -> dict[str, Any]:
    """Mark one child: SUBMITTING (only through ``check_before_enter``), AMBIGUOUS (outcome unknown: the account
    stays HELD until ``settle``), or a final outcome (PASSED, PROVIDER_FAILED, REJECTED_POLICY, NOT_SUBMITTED;
    ``spent`` > 0 turns the reservation into a spend). NOT_SENT closes a child that never reached the Enter; for a
    child that passed the check (SUBMITTING) only ``reason`` ENTER_NOT_ISSUED from the live holder (same token,
    ``epoch`` current, the same ``incarnation`` that passed the check, lease not released or re-epoched) closes it
    NOT_SENT; otherwise ENTER_NOT_ISSUED_REFUSED and the child is held AMBIGUOUS for reconcile (audited both ways)."""
    state = state.strip().upper()
    if state not in MARK_STATES:
        return _no("USAGE", f"state must be one of {MARK_STATES}")
    broker = _broker(db)
    if state == "SUBMITTING":
        return check_before_enter(lease_key, lease_token, child_key, epoch=epoch, incarnation=incarnation, db=db)
    if state == "AMBIGUOUS":
        lease = broker.hold_child(lease_key, lease_token=lease_token, child_key=child_key,
                                  reason=reason or "outcome unknown")
        return _ok(lease_state=lease["state"])
    if state == "NOT_SENT" and reason.strip().upper().startswith("ENTER_NOT_ISSUED"):
        if epoch is None or not (incarnation or "").strip():
            return _no("USAGE", "ENTER_NOT_ISSUED needs the lane's epoch and incarnation")
        rest = reason.strip()[len("ENTER_NOT_ISSUED"):].strip(" :")
        out = broker.enter_not_issued(lease_key, lease_token=lease_token, child_key=child_key,
                                      incarnation=incarnation, epoch=int(epoch), reason=rest)
        if out["ok"]:
            return _ok(outcome="NOT_SENT")
        return _no(out["code"], out["reason"], outcome=out["outcome"], possibly_sent=True)
    if state == "NOT_SENT":
        out = broker.release_unsent(lease_key, lease_token=lease_token, child_key=child_key)
        if out["uncertain"]:
            return _no("CHILD_PAST_ENTER", f"{child_key} passed the pre-Enter check: mark its outcome, AMBIGUOUS, or "
                                           f"NOT_SENT with reason ENTER_NOT_ISSUED")
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
           lease_token: str | None = None, db: str | Path | None = None) -> dict[str, Any]:
    """The reconcile path: give a held/open child (or all of them) its resolved spend. No token is needed; one given
    (``--token-stdin``) must be the lease's (TOKEN_MISMATCH otherwise)."""
    broker = _broker(db)
    if lease_token:
        _require_token(broker, lease_key, lease_token)
    lease = broker.settle_child(lease_key, spent=float(spent), child_key=child_key, note=note)
    return _ok(lease_state=lease["state"])


def _require_token(broker: Broker, lease_key: str, lease_token: str) -> None:
    with broker.transaction() as conn:
        row = conn.execute("SELECT lease_token FROM leases WHERE lease_key = ?", (lease_key,)).fetchone()
    if row is None:
        raise KeyError(f"no lease found for {lease_key!r}")
    if row["lease_token"] != lease_token:
        raise ValueError(f"lease_token mismatch for {lease_key!r}")


@_guard
def settle_not_sent(child_key: str, evidence: str, *, lease_key: str = "", lease_token: str = "",
                    db: str | Path | None = None) -> dict[str, Any]:
    """Atomic NOT_SENT settlement of one child, in one transaction. A child still PREPARING (it never passed the
    pre-Enter check) becomes terminal NOT_SENT and FENCED: a later check is NOT_SENT_PROVEN (no Enter) and an admission
    naming it is CHILD_FENCED; a new attempt needs a fresh child key. A child past the check (SUBMITTING) is refused
    (``CHILD_PAST_ENTER``, ``possibly_sent`` True) and nothing changes; reconcile it with ``settle``. Already NOT_SENT:
    ok (``changed`` False). ``evidence`` (why it is known unsent) is required and audited; ``lease_key`` picks the
    lease when the child key is not unique; a ``lease_token`` given must be the lease's."""
    if not (child_key or "").strip():
        return _no("USAGE", "settle-not-sent needs the child key (--child)")
    out = _broker(db).settle_not_sent(child_key.strip(), evidence=evidence, lease_key=lease_key.strip() or None,
                                      lease_token=lease_token or None)
    if out["ok"]:
        return _ok(**{k: v for k, v in out.items() if k not in ("ok", "code", "reason")})
    return _no(out["code"], out["reason"], **{k: v for k, v in out.items() if k not in ("ok", "code", "reason")})


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


# ---- the halt-file lock (shared with Muse), status and the allocator claim -------------------------------------
def halt_file_lock_path() -> str:
    """The halt-file lock (``<state dir>/production_halt.json.lock``): the innermost lock of the machine. Muse takes
    it, and nothing else, while it writes its halt file; it never opens a broker transaction while holding it."""
    from film_pipeline.production.halt import halt_lock_path
    return str(halt_lock_path())


@contextmanager
def halt_file_lock(timeout_s: float = 60.0) -> Iterator[None]:
    """Hold the halt-file lock (a byte lock on Windows, ``flock`` elsewhere; TimeoutError after ``timeout_s``)."""
    from film_pipeline.production.halt import halt_file_lock as _lock
    with _lock(timeout_s):
        yield


def _schema_version(path: Path) -> int | None:
    """``PRAGMA user_version`` read from the database header (bytes 60..63): no connection, no lock, no write."""
    try:
        with path.open("rb") as handle:
            header = handle.read(100)
    except OSError:
        return None
    if len(header) < 64 or not header.startswith(b"SQLite format 3\x00"):
        return None
    return int.from_bytes(header[60:64], "big")


@_guard
def status(*, db: str | Path | None = None) -> dict[str, Any]:
    """Read-only: is the AFP broker live? ``live`` True when its database exists with the current schema and the
    allocator claim names ``afp-broker``. Also: the database path, the claim (``owner``, ``owner_problem``), every stop
    signal (``stop_code`` / ``stop_reason``: the first one a check would refuse on; ``halted``, ``muse_halted``,
    ``pending_markers``) and the halt-file lock path. Opens nothing for writing, creates nothing, and carries no token,
    cookie, password or profile path."""
    from film_pipeline.production import halt as H
    path = Path(db) if db else default_db_path()
    exists = path.is_file()
    schema = _schema_version(path) if exists else None
    claim = H.read_owner()
    afp_halt, muse_halt = H.read_halt(), H.read_muse_halt()
    muse_path = H.muse_halt_path()
    m_problem, markers = H.pending_markers()
    stop_code, stop_reason = H.stop_signals()
    return _ok(live=bool(schema == SCHEMA_VERSION and not claim["problem"] and claim["owner"] == H.OWNER),
               db=str(path), db_exists=exists, schema_version=schema, expected_schema_version=SCHEMA_VERSION,
               owner=claim["owner"] or None, owner_problem=claim["problem"],
               stop_code=stop_code, stop_reason=stop_reason,
               halted=afp_halt is not None, halt_reason=(afp_halt or {}).get("reason", ""),
               muse_halt_file=str(muse_path) if muse_path else None, muse_halted=muse_halt is not None,
               pending_markers=[p.name for p in markers], pending_problem=m_problem,
               halt_lock=halt_file_lock_path())


@_guard
def allocator_claim(*, by: str = "", db: str | Path | None = None) -> dict[str, Any]:
    """Bootstrap the allocator claim ``{"owner": "afp-broker", ...}`` under the broker transaction, then the halt-file
    lock. Idempotent (``changed`` False when already claimed). A claim file that cannot be trusted
    (``ALLOCATOR_UNKNOWN``) or names another owner (``ALLOCATOR_NOT_OWNED``) is never overwritten."""
    out = _broker(db).allocator_claim(by=by)
    if not out["ok"]:
        return _no(out["code"], out["reason"])
    return _ok(**{k: v for k, v in out.items() if k not in ("ok", "code", "reason")})


@_guard
def allocator_release(*, by: str = "", db: str | Path | None = None) -> dict[str, Any]:
    """Remove the ``afp-broker`` claim under the same locks; refused (``OWNER_BUSY``) while any lease is live or any
    child unresolved in this broker. Idempotent when there is no claim. After it every admission and check refuses
    ``ALLOCATOR_UNKNOWN``."""
    out = _broker(db).allocator_release(by=by)
    if not out["ok"]:
        return _no(out["code"], out["reason"])
    return _ok(**{k: v for k, v in out.items() if k not in ("ok", "code", "reason")})
