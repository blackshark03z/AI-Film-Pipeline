"""The film send ledger (lane contract §5, §8): ``<muse film>/film_send_ledger.json`` under the OS lock
``<muse film>/.film_ledger.lock``.

The lane writes it (the PENDING_SEND record before Enter and its own updates); AFP intake only UPDATES attempts it finds
there and never creates one (§5 "After the record"). Intake takes this lock for one short read-modify-replace and never
calls the broker while holding it (§6 lock order).

File shape (the contract fixes the field names of an attempt, not the container; this is the shape intake reads, and a
file that does not have it is INVALID, which is AMBIGUOUS for every child of the batch, never a NOT_SENT)::

    {"entries": [{"take_identity": {"shot_id", "shot_version", "take_index"},
                  "attempts": [{"film_id", "wave_id", "batch_id", "slot_id", "child_key", "request_id", "shot_id",
                                "shot_version", "take_index", "account_id", "input_digest", "recorded_at",
                                "status", "reason", "result_eligible", "fenced", "history": [...]}]}]}

An attempt is addressed by ``(batch_id, slot_id, request_id)`` (§5). A missing, unreadable or invalid ledger never
establishes NOT_SENT (§0).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from film_pipeline.production.runtime import atomic_json

LEDGER_NAME = "film_send_ledger.json"
LOCK_NAME = ".film_ledger.lock"
LOCK_TIMEOUT_S = 30.0

# the statuses of §5 / §10; BLOCKING ones keep the shot version closed to every other wave
BLOCKING_STATUSES = ("PENDING_SEND", "UNCONFIRMED", "EXPIRED_NEEDS_RECONCILE", "RESULT_CORRUPT", "AMBIGUOUS")


class LedgerError(Exception):
    """The film ledger is absent, unreadable or invalid (never a proof of anything)."""


def ledger_path(muse_film: Path | str) -> Path:
    return Path(muse_film) / LEDGER_NAME


@contextmanager
def film_ledger_lock(muse_film: Path | str, timeout_s: float = LOCK_TIMEOUT_S) -> Iterator[None]:
    """Exclusive 1-byte OS lock on ``.film_ledger.lock`` (``msvcrt.locking`` on Windows, ``flock`` elsewhere): the
    primitive Muse's SessionLock uses. TimeoutError after ``timeout_s``."""
    lock = Path(muse_film) / LOCK_NAME
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        if lock.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"film ledger lock {lock} busy for {timeout_s:g}s") from exc
                time.sleep(0.02)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_ledger(muse_film: Path | str) -> dict[str, Any]:
    """The parsed ledger, or ``LedgerError`` (absent, unreadable, not the expected shape)."""
    path = ledger_path(muse_film)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LedgerError(f"{LEDGER_NAME} is absent") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise LedgerError(f"{LEDGER_NAME} is unreadable: {type(exc).__name__}") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise LedgerError(f"{LEDGER_NAME} is not valid JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise LedgerError(f"{LEDGER_NAME} has no 'entries' list")
    for entry in data["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("attempts"), list) \
                or not all(isinstance(a, dict) for a in entry["attempts"]):
            raise LedgerError(f"{LEDGER_NAME} has an entry without an 'attempts' list of objects")
    return data


def attempts_of_batch(ledger: dict[str, Any], batch_id: str, slot_id: str) -> list[dict[str, Any]]:
    """Every attempt of this batch and slot (a well-formed ledger holds exactly one)."""
    return [a for e in ledger["entries"] for a in e["attempts"]
            if a.get("batch_id") == batch_id and a.get("slot_id") == slot_id]


def attempt_digest(attempt: dict[str, Any]) -> str:
    """A stable fingerprint of one attempt, to see that it did not change between the intake read and its commit."""
    return hashlib.sha256(json.dumps(attempt, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def update_attempts(muse_film: Path | str, patches: dict[tuple[str, str, str], Callable[[dict[str, Any]], None]],
                    *, expect: dict[tuple[str, str, str], str] | None = None) -> dict[str, Any]:
    """Under the CALLER's ``film_ledger_lock``: re-read the ledger, apply ``patches[(batch, slot, request)](attempt)``
    to the one attempt addressed by each key, and write tmp + fsync + replace. Never creates an attempt. ``expect`` maps a
    key to the ``attempt_digest`` the caller decided on: an attempt that changed since is NOT patched.

    Returns ``{"updated": [keys], "missing": [keys], "changed": [keys]}`` (``missing``: no attempt, or more than one, at
    that address; ``changed``: its digest differs from ``expect``). Raises ``LedgerError`` when the ledger is invalid.
    """
    ledger = read_ledger(muse_film)
    updated: list[tuple[str, str, str]] = []
    missing: list[tuple[str, str, str]] = []
    changed: list[tuple[str, str, str]] = []
    for key, patch in patches.items():
        batch_id, slot_id, request_id = key
        found = [a for a in attempts_of_batch(ledger, batch_id, slot_id) if a.get("request_id") == request_id]
        if len(found) != 1:
            missing.append(key)
        elif expect and key in expect and attempt_digest(found[0]) != expect[key]:
            changed.append(key)
        else:
            patch(found[0])
            updated.append(key)
    if updated:
        atomic_json(ledger_path(muse_film), ledger)
    return {"updated": updated, "missing": missing, "changed": changed}
