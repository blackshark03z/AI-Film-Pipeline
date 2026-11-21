"""S2-lite intake (lane contract §7, AFP side): read what a Muse lane left in its job dir (§8) and decide, per child, what
AFP may believe (§10). Synchronous, from the direct CLI; no daemon, no Muse process, no network.

**Custody rule (§0).** A child is RESULT only with exact evidence; NOT_SENT only when the broker committed it
(``lease_children`` final NOT_SENT = fenced: the lane's proof 1 or 2, or an ``api.settle_not_sent`` this intake commits for
proof 3). Everything missing, malformed or contradictory is AMBIGUOUS (the account stays HELD in the broker): never RESULT,
never NOT_SENT, never a permission to resend.

**Per-child RESULT (§10 #7).** All of: the lane reports ``custody: RESULT`` for the slot with the request's exact
``child_key`` and ``request_id``; the broker child is past the pre-Enter check (SUBMITTING or settled, never PREPARING or
NOT_SENT); the film ledger holds exactly one attempt at ``(batch_id, slot_id, request_id)`` whose identity matches the
request, which is not fenced, not ``result_eligible: false`` and not RESULT_CORRUPT; exactly one ``<slot_id>_receipt.json``
carries the exact batch_id + slot_id + request_id (and, if it names one, the shot_id) and a sha256; exactly one
``<slot_id>.mp4`` exists, is not listed in ``integrity_failed.json`` / ``integrity_failed/`` and its sha256 equals the
receipt's in the job dir AND in both staging copies; a ``batch_receipt.json`` entry for the slot, if any, agrees.
FAILED_TERMINAL needs the same identity and an explicit failure status in the slot receipt (and the lane saying so).

**Phases.** A (no lock): read the lane files, copy them into ``<muse film>/.staging/<job_dir>/`` and
``<film>/.staging/<job_dir>/``, verify each copy's sha256, read the ledger and the broker's child rows, call
``settle_not_sent`` where §0 proof 3 applies, decide. B (``film_lock`` -> film ledger lock, short, NO broker call):
re-check the ledger, atomic renames out of staging, take log, ledger updates, then ONE job-DB transaction with every state
change and its event row (F1). C (no lock): AFP halt (exit 4 / ``muse_halt.json`` / ``halt_publication: PENDING``), broker
``settle`` of the RESULT / FAILED_TERMINAL children, events projection, staging cleanup. A decided job is never
re-decided: a second intake only retries the phase C steps that did not complete (idempotent).

Integrity failures are quarantined, never deleted: the job dir is never modified, and staging holds copies only.

Layout assumed under the job dir (the contract names the files, not every path; confirm with the Muse TL): clips and
receipts under ``BATCHES_V2/<batch_id>/`` at any depth, ``integrity_failed.json`` in that dir or the job dir,
``lane_result.json`` / ``render_fingerprints.json`` / ``unconfirmed_*.json`` / ``verified_clips/`` in the job dir.
Not in S2-lite: ``qc-audit`` and the UI projection (they run Muse; the job row says ``qc_pending``), resuming a pending Muse
halt publication (reported, not done), stills batches.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from film_pipeline.agentic import broker_api
from film_pipeline.agentic.broker import SCHEMA_VERSION as BROKER_SCHEMA_VERSION
from film_pipeline.agentic.broker import default_db_path
from film_pipeline.agentic.lane_jobs import (NON_BLOCKING_CHILD_STATES, JobStore, _now, add_event, canonical,
                                             project_events_safely, sha256_file)
from film_pipeline.agentic.lane_ledger import (LedgerError, attempt_digest, attempts_of_batch, film_ledger_lock,
                                               read_ledger, update_attempts)

_SHA = re.compile(r"^[0-9a-f]{64}$")
OK_STATUSES = {"ok", "completed"}
FAILED_STATUSES = {"failed", "error", "failed_terminal"}
# ledger statuses under which a RESULT may still be recorded (the lane may or may not have updated its attempt yet)
BROKER_FAILURE_OUTCOMES = {"PROVIDER_FAILED", "REJECTED_POLICY", "NOT_SUBMITTED", "NOT_SENT"}
RESULT_OK_STATUSES ={"PENDING_SEND", "UNCONFIRMED", "EXPIRED_NEEDS_RECONCILE"}
LANE_CUSTODY = ("NOT_SENT_PROVEN", "RESULT", "FAILED_TERMINAL", "AMBIGUOUS")
EXIT_OK, EXIT_ATTENTION, EXIT_USAGE, EXIT_ERROR = 0, 1, 2, 3


@dataclass
class Decision:
    slot: dict[str, Any]
    state: str                     # REGISTERED | NOT_SENT | FAILED_TERMINAL | AMBIGUOUS
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    clip: Path | None = None       # the verified staged AFP copy (REGISTERED only)
    sha: str = ""
    attempt_key: tuple[str, str, str] | None = None
    attempt_digest: str = ""
    ledger_status: str = ""        # what to write on the attempt (RESOLVED) for a settled child
    ledger_reason: str = ""
    fenced: bool = False
    quarantine: list[tuple[Path, str]] = field(default_factory=list)   # (staged AFP copy, file name)
    alarms: list[tuple[str, str]] = field(default_factory=list)        # (code, detail)
    take_id: str = ""


@dataclass
class Evidence:
    batch_dir: Path
    clips: dict[str, list[Path]] = field(default_factory=dict)
    slot_receipts: dict[str, list[Path]] = field(default_factory=dict)
    batch_receipts: list[Path] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    failed_names: set[str] = field(default_factory=set)
    failed_problem: str = ""
    problems: list[str] = field(default_factory=list)


# ---- phase A: reading ---------------------------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_lane_result(job_dir: Path, request: dict[str, Any]) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """``(lane_result or None, problem, children by slot_id)``; a slot named twice maps to ``None`` (duplicate)."""
    path = job_dir / "lane_result.json"
    try:
        data = _read_json(path)
    except FileNotFoundError:
        return None, "LANE_RESULT_MISSING", {}
    except (OSError, ValueError):
        return None, "LANE_RESULT_INVALID", {}
    if not isinstance(data, dict) or not isinstance(data.get("children"), list) \
            or not all(isinstance(c, dict) for c in data["children"]):
        return None, "LANE_RESULT_INVALID", {}
    for key, want in (("batch_id", request["batch_id"]), ("muse_tag", request["muse_tag"])):
        if data.get(key) not in (None, want):
            return None, f"LANE_RESULT_{key.upper()}_MISMATCH", {}
    by_slot: dict[str, Any] = {}
    for child in data["children"]:
        slot_id = child.get("slot_id")
        by_slot[slot_id] = None if slot_id in by_slot else child
    return data, "", by_slot


def discover(job_dir: Path, request: dict[str, Any]) -> Evidence:
    """The lane's files for this batch. Symlinks are never followed; nothing is read twice or modified."""
    batch_id = request["batch_id"]
    ev = Evidence(batch_dir=job_dir / "BATCHES_V2" / batch_id)
    slots = {s["slot_id"] for s in request["slots"]}
    if ev.batch_dir.is_dir() and not ev.batch_dir.is_symlink():
        for path in sorted(ev.batch_dir.rglob("*")):
            if path.is_symlink():
                ev.problems.append(f"symlink ignored: {path.name}")
                continue
            if not path.is_file() or "integrity_failed" in path.relative_to(ev.batch_dir).parts[:-1]:
                continue
            name = path.name
            if name.endswith(".mp4"):
                if path.stem in slots:
                    ev.clips.setdefault(path.stem, []).append(path)
                else:
                    ev.unknown.append(f"clip {name}")
            elif name == "batch_receipt.json":
                ev.batch_receipts.append(path)
            elif name.endswith("_receipt.json"):
                slot = name[: -len("_receipt.json")]
                if slot in slots:
                    ev.slot_receipts.setdefault(slot, []).append(path)
                else:
                    ev.unknown.append(f"receipt {name}")
    for where in (ev.batch_dir, job_dir):
        listing = where / "integrity_failed.json"
        if listing.is_file():
            try:
                clips = (_read_json(listing) or {}).get("clips")
                if not isinstance(clips, list) or not all(isinstance(c, str) for c in clips):
                    raise ValueError("clips")
                ev.failed_names |= {Path(c).stem for c in clips}
            except (OSError, ValueError, AttributeError):
                ev.failed_problem = f"{listing.name} is unreadable or invalid"
    qdir = ev.batch_dir / "integrity_failed"
    if qdir.is_dir():
        ev.failed_names |= {p.stem for p in qdir.iterdir() if p.is_file()}
    return ev


def _copy_verified(src: Path, dst: Path) -> str:
    """Copy ``src`` to ``dst`` and verify the copy's sha256 against the source's; returns it."""
    want = sha256_file(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    if sha256_file(dst) != want:
        raise OSError(f"{dst}: the copy does not match its source hash")
    return want


def stage(job_dir: Path, ev: Evidence, stage_roots: tuple[Path, Path]) -> dict[str, str]:
    """Step 1 of §7: copy the lane's evidence into both staging dirs (clips of the request's slots, every receipt,
    ``render_fingerprints.json``, ``integrity_failed.json``, ``lane_result.json``, the job-dir ledgers, ``verified_clips/``)
    and verify each copy. Returns ``{relative posix path: sha256}``. Raises OSError on any failure."""
    files: list[Path] = [p for ps in ev.clips.values() for p in ps] + [p for ps in ev.slot_receipts.values() for p in ps] \
        + ev.batch_receipts
    for name in ("lane_result.json", "render_fingerprints.json", "integrity_failed.json", "unconfirmed_submissions.json",
                 "unconfirmed_keyframes.json", "muse_halt.json"):
        for base in (job_dir, ev.batch_dir):
            if (base / name).is_file() and not (base / name).is_symlink() and (base / name) not in files:
                files.append(base / name)
    vc = job_dir / "verified_clips"
    if vc.is_dir() and not vc.is_symlink():
        files += [p for p in sorted(vc.rglob("*")) if p.is_file() and not p.is_symlink()]
    shas: dict[str, str] = {}
    for src in files:
        rel = src.relative_to(job_dir)
        digests = {_copy_verified(src, root / rel) for root in stage_roots}
        if len(digests) != 1:
            raise OSError(f"{rel}: the two staging copies differ")
        shas[rel.as_posix()] = digests.pop()
    return shas


def read_broker_children(db: Path, lease_key: str, child_keys: list[str]) -> dict[str, Any]:
    """``{child_key: row | None}`` read-only from the broker database, or ``{"__error__": text}``. The row: phase,
    outcome, final, amount (the reservation). A broker database that is absent or of another schema is an error."""
    try:
        if not Path(db).is_file():
            return {"__error__": f"broker database {db} does not exist"}
        with closing(sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True, timeout=30.0)) as conn:
            conn.row_factory = sqlite3.Row
            if int(conn.execute("PRAGMA user_version").fetchone()[0]) != BROKER_SCHEMA_VERSION:
                return {"__error__": "broker database has another schema version"}
            out: dict[str, Any] = {}
            for key in child_keys:
                row = conn.execute(
                    "SELECT c.phase, c.outcome, c.final, c.spent, r.amount FROM lease_children c "
                    "JOIN leases l ON l.lease_key = c.lease_key AND l.lease_token = c.lease_token "
                    "LEFT JOIN reservations r ON r.lease_token = c.lease_token AND r.child_key = c.child_key "
                    "WHERE c.lease_key = ? AND c.child_key = ?", (lease_key, key)).fetchall()
                out[key] = dict(row[0]) if len(row) == 1 else ({"__many__": True} if row else None)
            return out
    except (sqlite3.Error, OSError) as exc:
        return {"__error__": f"{type(exc).__name__}: {exc}"[:200]}


def _identity_mismatches(att: dict[str, Any], slot: dict[str, Any], request: dict[str, Any]) -> list[str]:
    want = {"film_id": request["film_id"], "wave_id": request["wave_id"], "batch_id": request["batch_id"],
            "slot_id": slot["slot_id"], "child_key": slot["child_key"], "request_id": slot["request_id"],
            "shot_id": slot["shot_id"], "shot_version": slot["shot_version"], "take_index": slot["take_index"],
            "account_id": request["account_id"], "input_digest": slot["input_digest"]}
    return [k for k, v in want.items() if att.get(k) != v]


def _parse_receipt(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        data = _read_json(path)
    except (OSError, ValueError):
        return None, "RECEIPT_MALFORMED"
    return (data, "") if isinstance(data, dict) else (None, "RECEIPT_MALFORMED")


def _receipt_problem(rec: dict[str, Any], slot: dict[str, Any], request: dict[str, Any]) -> str:
    for key, want in (("batch_id", request["batch_id"]), ("slot_id", slot["slot_id"]),
                      ("request_id", slot["request_id"])):
        if rec.get(key) != want:
            return f"RECEIPT_IDENTITY_MISMATCH:{key}"
    if "shot_id" in rec and rec["shot_id"] != slot["shot_id"]:
        return "RECEIPT_IDENTITY_MISMATCH:shot_id"
    return ""


def _status_class(rec: dict[str, Any]) -> str:
    status = rec.get("status")
    if status is None:
        return "ok"
    if isinstance(status, str) and status.lower() in OK_STATUSES:
        return "ok"
    if isinstance(status, str) and status.lower() in FAILED_STATUSES:
        return "failed"
    return "unknown"


def _batch_entries(ev: Evidence, slot: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """The ``batch_receipt.json`` entries that name this slot (by slot_id or request_id). ``(entries, problem)``."""
    out: list[dict[str, Any]] = []
    for path in ev.batch_receipts:
        rec, problem = _parse_receipt(path)
        if rec is None:
            return [], "BATCH_RECEIPT_MALFORMED"
        for group in ("shots", "failed_shots"):
            items = rec.get(group, [])
            if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
                return [], "BATCH_RECEIPT_MALFORMED"
            out += [{**i, "__group": group} for i in items
                    if i.get("slot_id") == slot["slot_id"] or i.get("request_id") == slot["request_id"]]
    return out, ""


# ---- the decision -------------------------------------------------------------------------------------------------
@dataclass
class Context:
    request: dict[str, Any]
    job: dict[str, Any]
    lane: dict[str, Any] | None
    lane_problem: str
    lane_children: dict[str, Any]
    evidence: Evidence
    stage_afp: Path
    stage_shas: dict[str, str]
    ledger: dict[str, Any] | None
    ledger_problem: str
    broker: dict[str, Any]
    broker_db: Path
    settle_not_sent: bool = True


def decide_child(slot: dict[str, Any], ctx: Context) -> Decision:
    request = ctx.request
    d = Decision(slot=slot, state="AMBIGUOUS", reason="")
    sid = slot["slot_id"]
    batch_id = request["batch_id"]
    key = (batch_id, sid, slot["request_id"])

    def ambiguous(reason: str, **evidence: Any) -> Decision:
        d.state, d.reason = "AMBIGUOUS", reason
        d.evidence.update(evidence)
        return d

    if ctx.broker.get("__error__"):
        return ambiguous("BROKER_UNREADABLE", detail=ctx.broker["__error__"])
    bro = ctx.broker.get(slot["child_key"])
    if bro is None or bro.get("__many__"):
        return ambiguous("BROKER_CHILD_MISSING" if bro is None else "BROKER_CHILD_NOT_UNIQUE")
    lane = ctx.lane_children.get(sid, "absent")
    if lane is None:
        return ambiguous("LANE_RESULT_DUPLICATE_SLOT")
    lane_entry = lane if isinstance(lane, dict) else None
    custody = lane_entry.get("custody") if lane_entry else None
    if lane_entry is not None:
        d.evidence["lane_custody"], d.evidence["lane_reason"] = custody, str(lane_entry.get("reason", ""))[:200]
        if lane_entry.get("child_key") not in (None, slot["child_key"]) \
                or lane_entry.get("request_id") not in (None, slot["request_id"]):
            return ambiguous("LANE_IDENTITY_MISMATCH")
        if custody not in LANE_CUSTODY:
            return ambiguous("LANE_CUSTODY_INVALID")
    ev = ctx.evidence
    clips, receipts = ev.clips.get(sid, []), ev.slot_receipts.get(sid, [])
    batch_entries, bproblem = _batch_entries(ev, slot)
    has_files = bool(clips or receipts or batch_entries)
    d.evidence["broker"] = {"phase": bro["phase"], "outcome": bro["outcome"], "final": bool(bro["final"])}

    attempt: dict[str, Any] | None = None
    if ctx.ledger is not None:
        found = attempts_of_batch(ctx.ledger, batch_id, sid)
        if len(found) > 1:
            return ambiguous("LEDGER_ATTEMPT_DUPLICATE")
        if found:
            attempt = found[0]
            bad = _identity_mismatches(attempt, slot, request)
            if bad:
                return ambiguous("LEDGER_IDENTITY_MISMATCH", fields=bad)
            d.attempt_key, d.attempt_digest = key, attempt_digest(attempt)
            d.evidence["ledger"] = {"status": attempt.get("status"), "reason": attempt.get("reason"),
                                    "fenced": attempt.get("fenced")}

    final = bool(bro["final"])
    # -- the broker committed a NOT_SENT (the only proof): contradictions first --------------------------------------
    if final and bro["outcome"] == "NOT_SENT":
        if custody not in (None, "NOT_SENT_PROVEN") or has_files:
            return ambiguous("CONTRADICTION_NOT_SENT_WITH_EVIDENCE")
        if ctx.ledger is None:   # a missing/invalid ledger never establishes NOT_SENT: held, loud
            d.alarms.append(("LEDGER_UNREADABLE_NOT_SENT", ctx.ledger_problem))
            return ambiguous("FILM_LEDGER_UNREADABLE_OR_INVALID", detail=ctx.ledger_problem)
        if attempt is None and lane_entry is not None:
            d.alarms.append(("LEDGER_ATTEMPT_MISSING", sid))
            return ambiguous("LEDGER_ATTEMPT_MISSING")
        elif attempt is not None and (attempt.get("status") == "RESOLVED" and attempt.get("reason") != "NOT_SENT"):
            return ambiguous("LEDGER_CONTRADICTS_NOT_SENT")
        d.state, d.reason, d.fenced = "NOT_SENT", "BROKER_COMMITTED_NOT_SENT", True
        d.ledger_status, d.ledger_reason = "RESOLVED", "NOT_SENT"
        return d
    if ctx.ledger is None:
        return ambiguous("FILM_LEDGER_UNREADABLE_OR_INVALID", detail=ctx.ledger_problem)
    # -- never passed the pre-Enter check ------------------------------------------------------------------------------
    if bro["phase"] == "PREPARING" and not final:
        if lane_entry is not None or has_files or attempt is not None:
            return ambiguous("CHILD_PREPARING_WITH_EVIDENCE", lane=bool(lane_entry), files=has_files,
                             attempt=attempt is not None)
        if not ctx.settle_not_sent:
            return ambiguous("NO_ATTEMPT_NOT_SETTLED")
        out = broker_api.settle_not_sent(
            slot["child_key"], f"lane intake {batch_id}: no film-ledger attempt and no lane or receipt evidence for "
                               f"{sid} (valid ledger read)", lease_key=ctx.job["lease_key"], db=ctx.broker_db)
        if out.get("ok"):
            d.state, d.reason, d.fenced = "NOT_SENT", "SETTLE_NOT_SENT_COMMITTED", True
            return d
        return ambiguous("SETTLE_NOT_SENT_REFUSED", code=out.get("code"))
    # -- possibly sent: only exact evidence can make it a RESULT or a proven failure -------------------------------------
    if lane_entry is None:
        return ambiguous("LANE_RESULT_MISSING" if ctx.lane is None else "NO_RESULT_IN_BATCH",
                         problem=ctx.lane_problem)
    if custody not in ("RESULT", "FAILED_TERMINAL"):
        return ambiguous("LANE_CUSTODY_" + str(custody))
    if lane_entry.get("child_key") != slot["child_key"] or lane_entry.get("request_id") != slot["request_id"]:
        return ambiguous("LANE_IDENTITY_INCOMPLETE")   # a result needs the exact identity, not an absent field
    # the broker's own record must not contradict a result
    if bro["phase"] == "UNKNOWN" or (final and bro["outcome"] in BROKER_FAILURE_OUTCOMES) \
            or (final and custody == "FAILED_TERMINAL" and bro["outcome"] == "PASSED"):
        return ambiguous("BROKER_STATE_CONTRADICTS_LANE", phase=bro["phase"], outcome=bro["outcome"])
    if attempt is None:
        d.alarms.append(("LEDGER_ATTEMPT_MISSING", sid))
        return ambiguous("LEDGER_ATTEMPT_MISSING")
    status = attempt.get("status")
    if attempt.get("fenced") is True or attempt.get("result_eligible") is False:
        return ambiguous("LEDGER_ATTEMPT_FENCED_OR_INELIGIBLE")
    if not (status in RESULT_OK_STATUSES or (status == "RESOLVED" and attempt.get("reason") == "RESULT_RECEIVED")
            or (status == "RESOLVED" and attempt.get("reason") == "FAILED_TERMINAL" and custody == "FAILED_TERMINAL")):
        return ambiguous("LEDGER_STATUS_" + str(status))
    if ev.failed_problem:
        return ambiguous("INTEGRITY_LIST_UNREADABLE", detail=ev.failed_problem)
    if bproblem:
        return ambiguous(bproblem)
    if len(receipts) != 1:
        return ambiguous("RECEIPT_MISSING" if not receipts else "RECEIPT_DUPLICATE_SLOT")
    rec, problem = _parse_receipt(receipts[0])
    if rec is None:
        return ambiguous(problem)
    problem = _receipt_problem(rec, slot, request)
    if problem:
        return ambiguous(problem)
    cls = _status_class(rec)
    if cls == "unknown":
        return ambiguous("RECEIPT_STATUS_UNKNOWN", status=str(rec.get("status"))[:40])
    sha = rec.get("sha256")
    if cls == "ok" and (not isinstance(sha, str) or not _SHA.match(sha)):
        return ambiguous("RECEIPT_SHA_MISSING")
    for entry in batch_entries:   # the batch receipt may say more; it may never say something else
        if entry.get("slot_id") not in (None, sid) or entry.get("request_id") not in (None, slot["request_id"]) \
                or (cls == "ok" and entry.get("sha256") not in (None, sha)) \
                or (entry["__group"] == "failed_shots") != (cls == "failed") \
                or (entry.get("status") is not None and _status_class(entry) != cls):
            return ambiguous("BATCH_RECEIPT_CONTRADICTS_SLOT_RECEIPT")
    if cls == "failed":
        if custody != "FAILED_TERMINAL" or clips:
            return ambiguous("LANE_RECEIPT_DISAGREE")
        d.state, d.reason = "FAILED_TERMINAL", "RECEIPT_EXPLICIT_FAILURE"
        d.evidence["receipt_status"] = str(rec.get("status"))[:40]
        d.ledger_status, d.ledger_reason = "RESOLVED", "FAILED_TERMINAL"
        return d
    if custody != "RESULT":
        return ambiguous("LANE_RECEIPT_DISAGREE")
    if sid in ev.failed_names:
        d.quarantine += [(ctx.stage_afp / p.relative_to(Path(ctx.job["job_dir_path"])), p.name) for p in clips]
        return ambiguous("INTEGRITY_FAILED", detail="listed in integrity_failed")
    if len(clips) != 1:
        return ambiguous("CLIP_MISSING" if not clips else "CLIP_DUPLICATE_SLOT")
    rel = clips[0].relative_to(Path(ctx.job["job_dir_path"])).as_posix()
    staged = ctx.stage_afp / rel
    actual = ctx.stage_shas.get(rel)
    if actual != sha or not staged.is_file() or sha256_file(staged) != sha:
        d.quarantine.append((staged, clips[0].name))
        d.alarms.append(("INTEGRITY_FAILED", f"{sid}: clip sha256 != receipt sha256"))
        return ambiguous("INTEGRITY_FAILED", detail="clip sha256 does not equal the receipt's", clip_sha=str(actual)[:12],
                         receipt_sha=str(sha)[:12])
    if staged.stat().st_size == 0:
        return ambiguous("CLIP_EMPTY")
    d.state, d.reason, d.clip, d.sha = "REGISTERED", "RESULT_EXACT_EVIDENCE", staged, sha
    d.ledger_status, d.ledger_reason = "RESOLVED", "RESULT_RECEIVED"
    return d


# ---- phase B: commit helpers ---------------------------------------------------------------------------------------
def merge_move(src_dir: Path, dst_dir: Path, conflict_dir: Path) -> list[str]:
    """Move every file of ``src_dir`` into ``dst_dir``: the whole directory by one atomic rename when ``dst_dir`` does
    not exist, else file by file (same sha256 already there: kept; a different one: the new file goes to ``conflict_dir``,
    nothing is overwritten or deleted). Returns the conflicting relative paths."""
    if not src_dir.is_dir():
        return []
    if not dst_dir.exists():
        dst_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src_dir, dst_dir)
        return []
    conflicts: list[str] = []
    for src in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
        elif sha256_file(dst) != sha256_file(src):
            alt = conflict_dir / rel
            alt.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, alt)
            conflicts.append(rel.as_posix())
    return conflicts


def _place_file(src: Path, dst: Path) -> bool:
    """Atomically place ``src`` at ``dst``; False (nothing changed) when ``dst`` exists with other bytes."""
    if dst.exists():
        return sha256_file(dst) == sha256_file(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)
    return True


def _take_file_name(slot: dict[str, Any]) -> str:
    return f"{slot['shot_id']}_v{slot['shot_version']}_t{slot['take_index']}.mp4"


def _aggregate(states: list[str]) -> str:
    if any(s == "AMBIGUOUS" for s in states):
        return "AMBIGUOUS"
    if any(s == "REGISTERED" for s in states):
        return "REGISTERED"
    if any(s == "FAILED_TERMINAL" for s in states):
        return "FAILED"
    return "NOT_SENT"


def _history(attempt: dict[str, Any], job_dir: str, status: str, reason: str, note: str = "") -> None:
    history = attempt.setdefault("history", [])
    if not isinstance(history, list):
        return
    entry = {"at": _now(), "by": "afp-intake", "job": job_dir, "status": status, "reason": reason}
    if note:
        entry["note"] = note
    if not any(isinstance(h, dict) and all(h.get(k) == entry[k] for k in ("by", "job", "status", "reason"))
               for h in history):
        history.append(entry)


# ---- the intake ---------------------------------------------------------------------------------------------------
def _result(job: dict[str, Any], store: JobStore, **extra: Any) -> dict[str, Any]:
    kids = store.children(job["job_key"])
    row = store.find_job(job["job_key"]) or job
    states = [c["state"] for c in kids]
    attention = row["state"] in ("AMBIGUOUS", "ADMITTED", "QUEUED") or any(s == "AMBIGUOUS" for s in states) \
        or bool(extra.get("alarms")) or bool(extra.get("error"))
    return {"ok": not extra.get("error"), "code": extra.pop("code", "OK" if not attention else "ATTENTION"),
            "reason": extra.pop("reason", ""), "job_key": row["job_key"], "job_dir": row["job_dir"],
            "state": row["state"], "changed": extra.pop("changed", False),
            "children": [{"slot_id": c["slot_id"], "state": c["state"], "reason": c["reason"], "take_id": c["take_id"]}
                         for c in kids], "attention": attention, **extra}


def intake_job(ref: str, *, store: JobStore | None = None, broker_db: Path | str | None = None,
               lane_exit_code: int | None = None, settle_broker: bool = True,
               settle_unsent: bool = True) -> dict[str, Any]:
    """Intake one job (``job_key`` or ``job_dir``): see the module docstring. Returns a JSON-serialisable dict
    (``ok``, ``code``, ``state``, ``children``, ``alarms``, ...); never raises for bad lane files."""
    store = store or JobStore()
    job = store.find_job(ref)
    if job is None:
        return {"ok": False, "code": "NOT_FOUND", "reason": f"no job {ref!r}"}
    broker_db = Path(broker_db) if broker_db else default_db_path()
    if job["state"] == "QUEUED":
        return {"ok": False, "code": "JOB_NOT_ADMITTED", "reason": f"{job['job_key']} has no batch_request.json yet "
                                                                 f"(prepare it again)"}
    job_dir = Path(job["job_dir_path"])
    afp_root, muse_film = Path(job["film_root"]), Path(job["muse_film"])
    if lane_exit_code is None:
        lane_exit_code = job["lane_exit_code"]
    if job["state"] != "ADMITTED":   # decided: never re-decide, only finish the post-commit steps
        out = _post_commit(job, store, broker_db, lane_exit_code, settle_broker, afp_root, None, [])
        return _result(job, store, changed=False, post=out, alarms=[], note="already intaken")

    # -- A: the frozen request and the lane's files (no lock) ---------------------------------------------------------
    request_path = job_dir / "batch_request.json"
    try:
        raw = request_path.read_bytes()
        request = json.loads(raw)
        request_ok = sha256_text_bytes(raw) == job["request_sha256"]
    except (OSError, ValueError):
        request, request_ok = None, False
    kids = store.children(job["job_key"])
    if not isinstance(request, dict) or not request_ok or request.get("batch_id") != job["job_dir"] \
            or [s.get("slot_id") for s in request.get("slots", [])] != [k["slot_id"] for k in kids]:
        decisions = [Decision(slot={"slot_id": k["slot_id"], "child_key": k["child_key"], "shot_id": k["shot_id"],
                                    "shot_version": k["shot_version"], "take_index": k["take_index"],
                                    "request_id": k["request_id"], "input_digest": k["input_digest"]},
                              state="AMBIGUOUS", reason="REQUEST_MODIFIED_OR_MISSING") for k in kids]
        return _commit_only_ambiguous(job, store, decisions, lane_exit_code, broker_db, afp_root)
    lane, lane_problem, lane_children = read_lane_result(job_dir, request)
    ev = discover(job_dir, request)
    stage_muse = muse_film / ".staging" / job["job_dir"]
    stage_afp = afp_root / ".staging" / job["job_dir"]
    for root in (stage_muse, stage_afp):   # staging holds copies only; a left-over one is ours to rebuild
        shutil.rmtree(root, ignore_errors=True)
    try:
        shas = stage(job_dir, ev, (stage_muse, stage_afp))
    except OSError as exc:
        return {"ok": False, "code": "STAGING_FAILED", "reason": f"{type(exc).__name__}: {exc}"[:300],
                "job_key": job["job_key"], "state": job["state"], "changed": False}
    try:
        ledger, ledger_problem = read_ledger(muse_film), ""
    except LedgerError as exc:
        ledger, ledger_problem = None, str(exc)
    broker = read_broker_children(broker_db, job["lease_key"], [s["child_key"] for s in request["slots"]])
    ctx = Context(request=request, job=job, lane=lane, lane_problem=lane_problem, lane_children=lane_children,
                  evidence=ev, stage_afp=stage_afp, stage_shas=shas, ledger=ledger, ledger_problem=ledger_problem,
                  broker=broker, broker_db=broker_db, settle_not_sent=settle_unsent)
    slots = [{**s, "slot_id": s["slot_id"]} for s in request["slots"]]
    decisions = [decide_child(s, ctx) for s in slots]
    alarms: list[tuple[str, str]] = [("UNKNOWN_EVIDENCE", u) for u in ev.unknown] + \
        [("EVIDENCE_PROBLEM", p) for p in ev.problems]
    if lane is not None and "lease_token" in json.dumps(lane):
        alarms.append(("TOKEN_FIELD_IN_LANE_RESULT", "lane_result.json carries a lease_token field"))

    # -- B: commit (film_lock -> film ledger lock; no broker call) --------------------------------------------------------
    from film_pipeline.production.runtime import WriterBusy, film_lock
    try:
        with film_lock(afp_root, timeout_s=30.0):
            with film_ledger_lock(muse_film):
                _commit(job, request, ctx, decisions, ledger, alarms, store, lane, lane_exit_code, afp_root, muse_film,
                        stage_muse, stage_afp)
    except WriterBusy as exc:
        return {"ok": False, "code": "FILM_BUSY", "reason": str(exc), "job_key": job["job_key"],
                "state": job["state"], "changed": False}
    except TimeoutError as exc:
        return {"ok": False, "code": "LEDGER_LOCK_BUSY", "reason": str(exc), "job_key": job["job_key"],
                "state": job["state"], "changed": False}
    # -- C: post-commit (no lock) -------------------------------------------------------------------------------------
    fresh = store.find_job(job["job_key"]) or job
    post = _post_commit(fresh, store, broker_db, lane_exit_code, settle_broker, afp_root, lane, decisions)
    for root in (stage_muse, stage_afp):
        shutil.rmtree(root, ignore_errors=True)
    project_events_safely(store, afp_root, job["film_id"])
    return _result(job, store, changed=True, post=post, alarms=[{"code": c, "detail": d} for c, d in alarms] +
                   [{"code": c, "slot_id": d.slot["slot_id"], "detail": x} for d in decisions for c, x in d.alarms])


def sha256_text_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _commit(job: dict[str, Any], request: dict[str, Any], ctx: Context, decisions: list[Decision],
            ledger: dict[str, Any] | None, alarms: list[tuple[str, str]], store: JobStore, lane: dict[str, Any] | None,
            lane_exit_code: int | None, afp_root: Path, muse_film: Path, stage_muse: Path, stage_afp: Path) -> None:
    from film_pipeline.production.takes import register_take
    batch_id, job_dir_name = request["batch_id"], job["job_dir"]
    # 1. the ledger as it is now (the lane cannot write it: we hold its lock): a changed attempt is a contradiction
    if ledger is not None:
        try:
            now_ledger = read_ledger(muse_film)
        except LedgerError as exc:
            now_ledger = None
            alarms.append(("LEDGER_BECAME_UNREADABLE", str(exc)))
        for d in decisions:
            if d.state == "AMBIGUOUS" or d.attempt_key is None:
                continue
            found = [] if now_ledger is None else \
                [a for a in attempts_of_batch(now_ledger, batch_id, d.slot["slot_id"])
                 if a.get("request_id") == d.slot["request_id"]]
            if len(found) != 1 or attempt_digest(found[0]) != d.attempt_digest:
                d.state, d.reason, d.clip = "AMBIGUOUS", "LEDGER_CHANGED_DURING_INTAKE", None
    # 2. files: the Muse side (BATCHES_V2/<batch>, verified_clips), the AFP side (takes, quarantine, evidence)
    conflict_root = afp_root / "takes" / "jobs" / job_dir_name / "intake_conflicts"
    for rel, dst_root in (("BATCHES_V2/" + batch_id, muse_film / "BATCHES_V2" / batch_id),):
        for c in merge_move(stage_muse / rel, dst_root, muse_film / ".staging" / "conflicts" / job_dir_name / rel):
            alarms.append(("MUSE_FILE_CONFLICT", c))
    for d in decisions:
        slot = d.slot
        for staged, name in d.quarantine:
            if staged.is_file():
                dst = afp_root / "takes" / "quarantine" / job_dir_name / name
                if not _place_file(staged, dst):
                    shutil.copyfile(staged, dst.with_name(f"{dst.stem}.{sha256_file(staged)[:12]}{dst.suffix}"))
        if d.state == "REGISTERED" and d.clip is not None:
            dst = afp_root / "takes" / _take_file_name(slot)
            if not _place_file(d.clip, dst):
                d.state, d.reason, d.clip = "AMBIGUOUS", "TAKE_FILE_CONFLICT", None
                continue
            prompt_file = afp_root / "takes" / "jobs" / job_dir_name / slot["slot_id"] / "prompt.txt"
            try:
                prompt = prompt_file.read_text(encoding="utf-8")
                entry, _created = register_take(
                    afp_root, job["film_id"], slot["shot_id"], dst, prompt_text=prompt, route=f"muse:{request['kind']}",
                    model=f"muse@{request['muse_tag']}", credits=0.0, shot_version=slot["shot_version"],
                    provider="muse", provider_job_id=f"{batch_id}:{slot['slot_id']}:{slot['request_id']}",
                    cost_unit="muse_requests", cost_amount=_amount(ctx, slot) or 1.0)
                d.take_id = entry.take_id
            except (OSError, ValueError) as exc:
                d.state, d.reason = "AMBIGUOUS", "TAKE_REGISTER_REFUSED"
                d.evidence["detail"] = f"{type(exc).__name__}: {exc}"[:200]
    # verified_clips/<sid>.mp4 become canonical on the Muse side only for a shot whose slot was registered; the rest stays
    # as evidence copies in the film package (a held slot is never promoted)
    vc_src = stage_muse / "verified_clips"
    if vc_src.is_dir():
        ok_shots = {d.slot["shot_id"] for d in decisions if d.state == "REGISTERED"}
        for p in sorted(vc_src.rglob("*")):
            if not p.is_file() or p.stem not in ok_shots:
                continue
            if not _place_file(p, muse_film / "verified_clips" / p.relative_to(vc_src)):
                alarms.append(("VERIFIED_CLIP_CONFLICT", p.name))
    for c in merge_move(stage_afp, afp_root / "takes" / "jobs" / job_dir_name / "intake", conflict_root):
        alarms.append(("AFP_EVIDENCE_CONFLICT", c))
    # 3. the ledger: update the attempts the lane published (never create one)
    if ledger is not None:
        patches: dict[tuple[str, str, str], Any] = {}
        for d in decisions:
            if d.attempt_key is None:
                continue
            patches[d.attempt_key] = _patch_for(d, job_dir_name)
        try:
            res = update_attempts(muse_film, patches)
            for key in res["missing"] + res["changed"]:
                alarms.append(("LEDGER_UPDATE_SKIPPED", f"{key[1]}"))
        except LedgerError as exc:
            alarms.append(("LEDGER_UPDATE_FAILED", str(exc)))
    # 4. ONE job-DB transaction: the children, the job, their events (F1)
    _write_decisions(store, job, decisions, alarms, lane, lane_exit_code)


def _amount(ctx: Context, slot: dict[str, Any]) -> float | None:
    row = ctx.broker.get(slot["child_key"])
    if isinstance(row, dict) and row.get("amount") is not None:
        return float(row["amount"])
    return None


def _patch_for(d: Decision, job_dir: str):
    def patch(attempt: dict[str, Any]) -> None:
        if d.state in ("REGISTERED", "FAILED_TERMINAL", "NOT_SENT"):
            attempt["status"], attempt["reason"] = d.ledger_status, d.ledger_reason
            if d.state == "NOT_SENT":
                attempt["fenced"] = True
            _history(attempt, job_dir, d.ledger_status, d.ledger_reason)
        else:
            _history(attempt, job_dir, "AMBIGUOUS", d.reason, note="held by AFP intake; status unchanged")
    return patch


def _write_decisions(store: JobStore, job: dict[str, Any], decisions: list[Decision], alarms: list[tuple[str, str]],
                     lane: dict[str, Any] | None, lane_exit_code: int | None) -> None:
    states = [d.state for d in decisions]
    new_state = _aggregate(states)
    with store.transaction() as conn:
        cur = conn.execute("SELECT state FROM jobs WHERE job_key = ?", (job["job_key"],)).fetchone()
        if cur is None or cur["state"] != "ADMITTED":   # decided by a concurrent intake: nothing to write
            return
        at = _now()
        for d in decisions:
            conn.execute("UPDATE children SET state = ?, reason = ?, evidence = ?, take_id = ?, clip_sha256 = ?, "
                         "updated_at = ? WHERE job_key = ? AND slot_id = ? AND state = 'PENDING'",
                         (d.state, d.reason, canonical(d.evidence), d.take_id, d.sha, at, job["job_key"],
                          d.slot["slot_id"]))
            add_event(conn, film_id=job["film_id"], job_key=job["job_key"], slot_id=d.slot["slot_id"],
                      kind={"REGISTERED": "CHILD_REGISTERED", "NOT_SENT": "CHILD_NOT_SENT",
                            "FAILED_TERMINAL": "CHILD_FAILED_TERMINAL", "AMBIGUOUS": "CHILD_AMBIGUOUS"}[d.state],
                      state=d.state, reason=d.reason,
                      payload={"take_id": d.take_id, "clip_sha256": d.sha, "child_key": d.slot["child_key"]})
            for code, detail in d.alarms:
                add_event(conn, film_id=job["film_id"], job_key=job["job_key"], slot_id=d.slot["slot_id"], kind="ALARM",
                          state=code, reason=detail)
        for code, detail in alarms:
            add_event(conn, film_id=job["film_id"], job_key=job["job_key"], kind="ALARM", state=code, reason=detail)
        conn.execute("UPDATE jobs SET state = ?, intake_at = ?, updated_at = ?, lane_exit_code = ?, qc_pending = ? "
                     "WHERE job_key = ?", (new_state, at, at, lane_exit_code, 1 if "REGISTERED" in states else 0,
                                           job["job_key"]))
        add_event(conn, film_id=job["film_id"], job_key=job["job_key"], kind="JOB_" + new_state, state=new_state,
                  payload={"children": {d.slot["slot_id"]: d.state for d in decisions},
                           "lane_status": _safe_status(lane)})


def _safe_status(lane: dict[str, Any] | None) -> str | None:
    """The lane's status word for the event payload: a short plain word only (the lane file is untrusted; a structured
    value could carry a token)."""
    status = (lane or {}).get("status")
    return status[:40] if isinstance(status, str) and status.replace("_", "").isalnum() else None


def _commit_only_ambiguous(job: dict[str, Any], store: JobStore, decisions: list[Decision], lane_exit_code: int | None,
                           broker_db: Path, afp_root: Path) -> dict[str, Any]:
    _write_decisions(store, job, decisions, [("REQUEST_MODIFIED_OR_MISSING", job["job_key"])], None, lane_exit_code)
    project_events_safely(store, afp_root, job["film_id"])
    return _result(job, store, changed=True, alarms=[{"code": "REQUEST_MODIFIED_OR_MISSING", "detail": job["job_key"]}])


# ---- phase C: after the commit ---------------------------------------------------------------------------------------
def _halt_signals(job: dict[str, Any], lane: dict[str, Any] | None, lane_exit_code: int | None) -> list[str]:
    why: list[str] = []
    if lane_exit_code == 4:
        why.append("lane exit code 4 (HALTED)")
    if (Path(job["job_dir_path"]) / "muse_halt.json").is_file():
        why.append("muse_halt.json in the job dir")
    if (lane or {}).get("halt_publication") == "PENDING":
        why.append("lane_result halt_publication PENDING")
    return why


def _post_commit(job: dict[str, Any], store: JobStore, broker_db: Path, lane_exit_code: int | None, settle_broker: bool,
                 afp_root: Path, lane: dict[str, Any] | None, decisions: list[Decision]) -> dict[str, Any]:
    """The steps after the job DB commit; each is retried by a later intake until it is recorded done."""
    post: dict[str, Any] = {}
    if lane is None:
        try:
            lane = json.loads((Path(job["job_dir_path"]) / "lane_result.json").read_text(encoding="utf-8"))
            lane = lane if isinstance(lane, dict) else None
        except (OSError, ValueError):
            lane = None
    why = _halt_signals(job, lane, lane_exit_code)
    if why and not job["halt_set"]:
        from film_pipeline.production.halt import set_halt
        try:
            set_halt(f"Muse lane {job['job_dir']} on {job['account_id']} stopped: {'; '.join(why)}",
                     source="lane-intake:muse", account=job["account_id"], film_id=job["film_id"],
                     evidence=job["job_dir"], db=broker_db)
            with store.transaction() as conn:
                conn.execute("UPDATE jobs SET halt_set = 1 WHERE job_key = ?", (job["job_key"],))
                add_event(conn, film_id=job["film_id"], job_key=job["job_key"], kind="HALT_SET", reason="; ".join(why))
                if (lane or {}).get("halt_publication") == "PENDING":
                    add_event(conn, film_id=job["film_id"], job_key=job["job_key"], kind="ALARM",
                              state="MUSE_HALT_PUBLICATION_PENDING",
                              reason="the Muse halt is not published; resume it (S2-lite does not) and tell the Owner")
            post["halt_set"] = True
        except Exception as exc:   # a halt that could not be set is loud, and retried by the next intake
            post["halt_set"] = False
            post["halt_error"] = f"{type(exc).__name__}: {exc}"[:200]
    elif why:
        post["halt_set"] = True
    if settle_broker and not job["broker_settled"] and job["state"] != "ADMITTED":
        kids = [c for c in store.children(job["job_key"]) if c["state"] in ("REGISTERED", "FAILED_TERMINAL")]
        info = read_broker_children(broker_db, job["lease_key"], [c["child_key"] for c in kids])
        failures = []
        for c in kids:
            row = info.get(c["child_key"])
            if info.get("__error__") or not isinstance(row, dict):
                failures.append(f"{c['slot_id']}: broker child unreadable")
                continue
            amount = float(row["amount"]) if row.get("amount") is not None else None
            if amount is None:
                failures.append(f"{c['slot_id']}: no reservation amount")
                continue
            out = broker_api.settle(job["lease_key"], spent=amount, child_key=c["child_key"],
                                    note=f"lane intake {job['job_dir']}: {c['state']}", db=broker_db)
            if not out.get("ok"):
                failures.append(f"{c['slot_id']}: {out.get('code')}")
        with store.transaction() as conn:
            if failures:
                add_event(conn, film_id=job["film_id"], job_key=job["job_key"], kind="ALARM",
                          state="BROKER_SETTLE_FAILED", reason="; ".join(failures))
            else:
                won = conn.execute("UPDATE jobs SET broker_settled = 1 WHERE job_key = ? AND broker_settled = 0",
                                   (job["job_key"],)).rowcount
                if won:   # two concurrent intakes: the broker settle is idempotent, the event is recorded once
                    add_event(conn, film_id=job["film_id"], job_key=job["job_key"], kind="BROKER_SETTLED",
                              payload={"children": [c["child_key"] for c in kids]})
        post["broker_settled"] = not failures
        if failures:
            post["broker_settle_failures"] = failures
    project_events_safely(store, afp_root, job["film_id"])
    return post
