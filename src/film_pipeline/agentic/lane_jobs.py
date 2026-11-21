"""S2-lite job rows, frozen inputs and ``batch_request.json`` (STUDIO_ARCHITECTURE §3, §4, §7, §9; lane contract §5).

One **job** = one Muse batch = one lane's slice of one wave (``film_id`` + ``wave_id`` + ``kind`` + ``account_id``).
``job_key = <film_id>:<wave_id>:<kind>:<account_id>`` and ``job_dir`` = the first 12 hex digits of sha256(``job_key``)
(colons are invalid in Windows paths, F6); it is also the batch id (``batch_id == job_dir``, contract §5). Its slots are
the job's children, each one take identity ``(film, shot_id, shot_version, take_index)``.

The job database ``<state dir>/studio_jobs.sqlite3`` (or ``--jobs-db``) holds jobs, children and events. Custody of the
account and its money stays in the broker database; this one holds the film side: which frozen input digest a job
carries, which batch request was written, what intake decided per child. Each state change and its event row are one
SQLite transaction (F1); ``films/<id>/events.jsonl`` is a projection of the rows (``project_events``).

``prepare_job`` freezes the inputs (§4: prompt text and input files copied into ``<film>/takes/jobs/<job_dir>/`` with
their sha256), creates the Muse job dir ``<muse film>/jobs/<job_dir>/`` EXCLUSIVELY and writes ``batch_request.json``
exactly as contract §5 shows it: no lease token (the request has no field for one, and a spec that names a secret-like
key is refused). It makes no broker call: the admission (``broker acquire``) happened before, and ``lease_key`` /
``epoch`` / ``wave_id`` come from it. Spawning the lane is S5.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from film_pipeline.production.halt import state_dir
from film_pipeline.production.runtime import atomic_json, atomic_text

JOBS_DB_FILENAME = "studio_jobs.sqlite3"
SCHEMA_VERSION = 1
CONTRACT = "afp-muse-lane/1"
KINDS = ("video",)   # S2-lite: stills intake is not built yet, so a stills job is refused at prepare, not stranded
QUALITIES = ("max",)

# job states (STUDIO_ARCHITECTURE §3); QUEUED = row + frozen assets durable, ADMITTED = batch request written for a
# broker-admitted lease, the rest are what intake decides
JOB_STATES = ("QUEUED", "ADMITTED", "REGISTERED", "NOT_SENT", "FAILED", "AMBIGUOUS")
# child states (contract §10): REGISTERED = a RESULT that intake copied and put in the take log
CHILD_STATES = ("PENDING", "REGISTERED", "NOT_SENT", "FAILED_TERMINAL", "AMBIGUOUS")
NON_BLOCKING_CHILD_STATES = ("REGISTERED", "NOT_SENT", "FAILED_TERMINAL")

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SECRET_KEY = re.compile(r"token|password|passwd|secret|cookie|credential|api[_-]?key", re.I)
SPEC_KEYS = {"film_root", "muse_film", "wave_id", "kind", "account_id", "lease_key", "epoch", "muse_tag", "quality",
             "slots"}
SLOT_KEYS = {"slot_id", "child_key", "shot_id", "shot_version", "take_index", "input_digest", "request_id",
             "depends_on", "rebind_of", "prompt_text", "inputs"}


class SpecError(ValueError):
    """The prepare spec is invalid (``code`` names why)."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code, self.reason = code, reason


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def default_jobs_db() -> Path:
    return state_dir() / JOBS_DB_FILENAME


def make_job_key(film_id: str, wave_id: str, kind: str, account_id: str) -> str:
    return f"{film_id}:{wave_id}:{kind}:{account_id}"


def job_dir_name(job_key: str) -> str:
    """The 12-hex job id: first 12 hex digits of sha256(job_key) (colons are invalid in Windows paths, F6)."""
    return hashlib.sha256(job_key.encode("utf-8")).hexdigest()[:12]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# ---- the store ---------------------------------------------------------------------------------------------------
_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
  job_key TEXT PRIMARY KEY, job_dir TEXT NOT NULL UNIQUE, film_id TEXT NOT NULL, film_root TEXT NOT NULL,
  muse_film TEXT NOT NULL, wave_id TEXT NOT NULL, kind TEXT NOT NULL, account_id TEXT NOT NULL,
  lease_key TEXT NOT NULL, epoch INTEGER NOT NULL, muse_tag TEXT NOT NULL, quality TEXT NOT NULL,
  state TEXT NOT NULL, frozen_digest TEXT NOT NULL, request_sha256 TEXT NOT NULL DEFAULT '',
  job_dir_path TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, intake_at TEXT NOT NULL DEFAULT '',
  lane_exit_code INTEGER, broker_settled INTEGER NOT NULL DEFAULT 0, halt_set INTEGER NOT NULL DEFAULT 0,
  qc_pending INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS children (
  job_key TEXT NOT NULL, slot_id TEXT NOT NULL, child_key TEXT NOT NULL, shot_id TEXT NOT NULL,
  shot_version INTEGER NOT NULL, take_index INTEGER NOT NULL, input_digest TEXT NOT NULL, request_id TEXT NOT NULL,
  rebind_of TEXT NOT NULL DEFAULT '', state TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
  evidence TEXT NOT NULL DEFAULT '{}', take_id TEXT NOT NULL DEFAULT '', clip_sha256 TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL, PRIMARY KEY (job_key, slot_id), UNIQUE (job_key, child_key),
  UNIQUE (job_key, shot_id, shot_version));
CREATE INDEX IF NOT EXISTS idx_children_identity ON children(shot_id, shot_version, take_index);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, film_id TEXT NOT NULL, job_key TEXT NOT NULL,
  slot_id TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL, state TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '',
  payload TEXT NOT NULL DEFAULT '{}', projected INTEGER NOT NULL DEFAULT 0);
"""


class JobStore:
    """The S2-lite job database. Every method opens its own short connection; ``transaction`` is ``BEGIN IMMEDIATE``."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_jobs_db()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if int(conn.execute("PRAGMA user_version").fetchone()[0]) < SCHEMA_VERSION:
                    for stmt in filter(None, (s.strip() for s in _DDL.split(";"))):
                        conn.execute(stmt)
                    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                if conn.in_transaction:
                    conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def read(self, sql: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with closing(self._connect()) as conn:
            return conn.execute(sql, args).fetchall()

    def find_job(self, ref: str) -> dict[str, Any] | None:
        """A job by ``job_key`` or by ``job_dir`` (= batch id)."""
        rows = self.read("SELECT * FROM jobs WHERE job_key = ? OR job_dir = ?", (ref, ref))
        return dict(rows[0]) if rows else None

    def children(self, job_key: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.read("SELECT * FROM children WHERE job_key = ? ORDER BY slot_id", (job_key,))]

    def events(self, *, film_id: str | None = None, job_key: str | None = None) -> list[dict[str, Any]]:
        q, args = "SELECT * FROM events WHERE 1=1", []
        if film_id:
            q, args = q + " AND film_id = ?", args + [film_id]
        if job_key:
            q, args = q + " AND job_key = ?", args + [job_key]
        return [dict(r) for r in self.read(q + " ORDER BY id", tuple(args))]


def add_event(conn: sqlite3.Connection, *, film_id: str, job_key: str, kind: str, slot_id: str = "", state: str = "",
              reason: str = "", payload: dict[str, Any] | None = None) -> None:
    """An event row, written inside the caller's transaction (F1: the same txn as the state change it reports)."""
    conn.execute("INSERT INTO events (at, film_id, job_key, slot_id, kind, state, reason, payload) VALUES "
                 "(?, ?, ?, ?, ?, ?, ?, ?)", (_now(), film_id, job_key, slot_id, kind, state, reason[:300],
                                              json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)))


def project_events(store: JobStore, film_root: Path | str, film_id: str) -> int:
    """Append the not yet projected event rows of ``film_id`` to ``<film>/events.jsonl`` (id-keyed, so a crash between
    the append and the mark replays without duplicating) and mark them. Returns how many were appended."""
    rows = store.read("SELECT * FROM events WHERE film_id = ? AND projected = 0 ORDER BY id", (film_id,))
    if not rows:
        return 0
    path = Path(film_root) / "events.jsonl"
    seen: set[int] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(int(json.loads(line)["id"]))
            except (ValueError, KeyError, TypeError):
                continue
    fresh = [r for r in rows if int(r["id"]) not in seen]
    if fresh:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for r in fresh:
                handle.write(json.dumps({"id": r["id"], "at": r["at"], "film_id": r["film_id"], "job_key": r["job_key"],
                                         "slot_id": r["slot_id"], "kind": r["kind"], "state": r["state"],
                                         "reason": r["reason"], "payload": json.loads(r["payload"])},
                                        ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
    with store.transaction() as conn:
        conn.executemany("UPDATE events SET projected = 1 WHERE id = ?", [(r["id"],) for r in rows])
    return len(fresh)


# ---- the spec ----------------------------------------------------------------------------------------------------
def _name(value: Any, what: str) -> str:
    if not isinstance(value, str) or not _NAME.match(value):
        raise SpecError("SPEC_INVALID", f"{what} must match {_NAME.pattern}: {value!r}")
    return value


def _int(value: Any, what: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise SpecError("SPEC_INVALID", f"{what} must be an integer >= {minimum}: {value!r}")
    return value


def _reject_secrets(value: Any, where: str = "spec") -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            if _SECRET_KEY.search(str(key)):
                raise SpecError("SECRET_IN_SPEC", f"{where}.{key}: a capability or secret never enters a request")
            _reject_secrets(inner, f"{where}.{key}")
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            _reject_secrets(inner, f"{where}[{i}]")


def read_film_id(film_root: Path) -> str:
    """The film id of the AFP package (``film.json``), never taken from the spec alone."""
    path = Path(film_root) / "film.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        film_id = data["film_id"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SpecError("FILM_UNKNOWN", f"{film_root} is not a film package (film.json unreadable or has no film_id)") \
            from exc
    if not isinstance(film_id, str) or not film_id.strip():
        raise SpecError("FILM_UNKNOWN", f"{path}: film_id is empty")
    return film_id


def normalize_spec(spec: Any) -> dict[str, Any]:
    """Validate a prepare spec and return it normalized (request ids resolved). Unknown keys are refused."""
    if not isinstance(spec, dict):
        raise SpecError("SPEC_INVALID", "the spec must be a JSON object")
    _reject_secrets(spec)
    extra = set(spec) - SPEC_KEYS
    if extra:
        raise SpecError("SPEC_INVALID", f"unknown spec keys: {sorted(extra)}")
    for key in ("film_root", "muse_film", "wave_id", "kind", "account_id", "lease_key", "epoch", "muse_tag", "slots"):
        if key not in spec:
            raise SpecError("SPEC_INVALID", f"the spec needs {key!r}")
    kind = spec["kind"]
    if kind not in KINDS:
        raise SpecError("KIND_NOT_SUPPORTED", f"kind must be one of {KINDS} (S2-lite intake has no stills path): {kind!r}")
    quality = spec.get("quality", "max")
    if quality not in QUALITIES:
        raise SpecError("SPEC_INVALID", f"quality must be one of {QUALITIES}")
    lease_key = spec["lease_key"]
    if not isinstance(lease_key, str) or not lease_key.strip():
        raise SpecError("SPEC_INVALID", "lease_key must be a non-empty string")
    muse_tag = spec["muse_tag"]
    if not isinstance(muse_tag, str) or not muse_tag.strip():
        raise SpecError("SPEC_INVALID", "muse_tag must be a non-empty string")
    out: dict[str, Any] = {
        "film_root": str(spec["film_root"]), "muse_film": str(spec["muse_film"]),
        "wave_id": _name(spec["wave_id"], "wave_id"), "kind": kind, "account_id": _name(spec["account_id"], "account_id"),
        "lease_key": lease_key, "epoch": _int(spec["epoch"], "epoch", minimum=0), "muse_tag": muse_tag,
        "quality": quality, "slots": []}
    slots = spec["slots"]
    max_slots = {"video": 6, "stills": 4}[kind]
    if not isinstance(slots, list) or not 1 <= len(slots) <= max_slots:
        raise SpecError("SPEC_INVALID", f"slots must be a list of 1..{max_slots}")
    seen_slot, seen_child, seen_version = set(), set(), set()
    for i, raw in enumerate(slots):
        if not isinstance(raw, dict):
            raise SpecError("SPEC_INVALID", f"slots[{i}] must be an object")
        extra = set(raw) - SLOT_KEYS
        if extra:
            raise SpecError("SPEC_INVALID", f"slots[{i}]: unknown keys {sorted(extra)}")
        for key in ("slot_id", "child_key", "shot_id", "shot_version", "take_index", "input_digest", "prompt_text"):
            if key not in raw:
                raise SpecError("SPEC_INVALID", f"slots[{i}] needs {key!r}")
        slot_id = _name(raw["slot_id"], f"slots[{i}].slot_id")
        child_key = raw["child_key"]
        if not isinstance(child_key, str) or not child_key.strip():
            raise SpecError("SPEC_INVALID", f"slots[{i}].child_key must be a non-empty string")
        shot_id = _name(raw["shot_id"], f"slots[{i}].shot_id")
        version = _int(raw["shot_version"], f"slots[{i}].shot_version")
        digest = raw["input_digest"]
        if not isinstance(digest, str) or not _SHA.match(digest):
            raise SpecError("SPEC_INVALID", f"slots[{i}].input_digest must be a lowercase sha256")
        prompt = raw["prompt_text"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise SpecError("SPEC_INVALID", f"slots[{i}].prompt_text is required (its hash is the take's provenance)")
        if slot_id in seen_slot or child_key in seen_child:
            raise SpecError("SPEC_INVALID", f"slots[{i}]: duplicate slot_id or child_key")
        if (shot_id, version) in seen_version:
            raise SpecError("SPEC_INVALID", f"slots[{i}]: two takes of {shot_id} v{version} never share a batch")
        seen_slot.add(slot_id), seen_child.add(child_key), seen_version.add((shot_id, version))
        deps = raw.get("depends_on", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise SpecError("SPEC_INVALID", f"slots[{i}].depends_on must be a list of strings")
        rebind = raw.get("rebind_of")
        if rebind is not None and not (isinstance(rebind, dict) and set(rebind) == {"batch_id", "request_id"}
                                       and all(isinstance(v, str) and v for v in rebind.values())):
            raise SpecError("SPEC_INVALID", f"slots[{i}].rebind_of is null or {{batch_id, request_id}}")
        inputs = raw.get("inputs", [])
        if not isinstance(inputs, list):
            raise SpecError("SPEC_INVALID", f"slots[{i}].inputs must be a list")
        for j, item in enumerate(inputs):
            if not (isinstance(item, dict) and set(item) == {"role", "path"} and isinstance(item["path"], str)):
                raise SpecError("SPEC_INVALID", f"slots[{i}].inputs[{j}] must be {{role, path}}")
            _name(item["role"], f"slots[{i}].inputs[{j}].role")
        out["slots"].append({
            "slot_id": slot_id, "child_key": child_key, "shot_id": shot_id, "shot_version": version,
            "take_index": _int(raw["take_index"], f"slots[{i}].take_index"), "input_digest": digest,
            "request_id": raw.get("request_id") or "", "depends_on": deps, "rebind_of": rebind,
            "prompt_text": prompt, "inputs": inputs})
    return out


def _freeze(slots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Read every input file and hash it (nothing is written yet). Returns slot_id -> {prompt_sha256, inputs}."""
    frozen: dict[str, dict[str, Any]] = {}
    for slot in slots:
        files = []
        for item in slot["inputs"]:
            path = Path(item["path"])
            if not path.is_file():
                raise SpecError("INPUT_MISSING", f"{slot['slot_id']}: input {item['role']} {path} is not a file")
            files.append({"role": item["role"], "name": path.name, "sha256": sha256_file(path), "src": str(path)})
        frozen[slot["slot_id"]] = {"prompt_sha256": sha256_text(slot["prompt_text"]), "inputs": files}
    return frozen


def _frozen_digest(job_key: str, spec: dict[str, Any], frozen: dict[str, dict[str, Any]]) -> str:
    body = {"job_key": job_key, "kind": spec["kind"], "account_id": spec["account_id"], "lease_key": spec["lease_key"],
            "epoch": spec["epoch"], "muse_tag": spec["muse_tag"], "quality": spec["quality"],
            "slots": [{"slot_id": s["slot_id"], "child_key": s["child_key"], "shot_id": s["shot_id"],
                       "shot_version": s["shot_version"], "take_index": s["take_index"],
                       "input_digest": s["input_digest"], "request_id": s["request_id"], "depends_on": s["depends_on"],
                       "rebind_of": s["rebind_of"], "prompt_sha256": frozen[s["slot_id"]]["prompt_sha256"],
                       "inputs": [{"role": f["role"], "sha256": f["sha256"]} for f in frozen[s["slot_id"]]["inputs"]]}
                      for s in spec["slots"]]}
    return sha256_text(canonical(body))


def build_batch_request(job: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """``batch_request.json`` exactly as contract §5 shows it (key order included); no capability, no token."""
    return {
        "contract": CONTRACT, "film_id": job["film_id"], "wave_id": spec["wave_id"], "batch_id": job["job_dir"],
        "kind": spec["kind"], "account_id": spec["account_id"],
        "lease": {"lease_key": spec["lease_key"], "epoch": spec["epoch"]},
        "muse_tag": spec["muse_tag"], "quality": spec["quality"],
        "slots": [{"slot_id": s["slot_id"], "child_key": s["child_key"], "shot_id": s["shot_id"],
                   "shot_version": s["shot_version"], "take_index": s["take_index"], "input_digest": s["input_digest"],
                   "request_id": s["request_id"], "depends_on": s["depends_on"], "rebind_of": s["rebind_of"]}
                  for s in spec["slots"]]}


def _refuse(code: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "code": code, "reason": reason, **extra}


def _identity_refusal(conn: sqlite3.Connection, film_id: str, job_key: str, slot: dict[str, Any]) -> tuple[str, str] | None:
    """The take-identity rules (contract §3, §5): an identity is unique for the life of the film unless this slot is a
    valid rebind of a NOT_SENT attempt; no other job may hold an unresolved child of the same shot version."""
    rows = conn.execute(
        "SELECT c.*, j.job_dir, j.film_id FROM children c JOIN jobs j ON j.job_key = c.job_key WHERE j.film_id = ? AND "
        "c.job_key != ? AND c.shot_id = ? AND c.shot_version = ?", (film_id, job_key, slot["shot_id"],
                                                                    slot["shot_version"])).fetchall()
    for row in rows:
        if row["state"] not in NON_BLOCKING_CHILD_STATES:
            return ("SHOT_VERSION_BUSY", f"{slot['shot_id']} v{slot['shot_version']} has an unresolved child "
                                         f"({row['state']}) in job {row['job_dir']}")
    same = [r for r in rows if int(r["take_index"]) == slot["take_index"]]
    rebind = slot["rebind_of"]
    if not same:
        if rebind is not None:
            return "REBIND_REFUSED", "rebind_of names an attempt that does not exist for this take identity"
        return None
    if rebind is None:
        return "TAKE_IDENTITY_EXISTS", f"{slot['shot_id']} v{slot['shot_version']} take {slot['take_index']} already " \
                                       f"has an attempt: a new attempt needs rebind_of"
    if any(r["state"] != "NOT_SENT" for r in same):
        return "REBIND_REFUSED", "an earlier attempt of this identity is not settled NOT_SENT"
    if not any(r["job_dir"] == rebind["batch_id"] and r["request_id"] == rebind["request_id"] for r in same):
        return "REBIND_REFUSED", "rebind_of does not name an attempt of this take identity"
    return None


def prepare_job(spec_raw: Any, *, store: JobStore | None = None) -> dict[str, Any]:
    """Freeze a batch and write its ``batch_request.json``. Idempotent: the same job key with the same frozen digest
    returns the existing job (a QUEUED one is resumed); a different digest is refused while the job is live. Makes no
    broker call and sends nothing."""
    try:
        spec = normalize_spec(spec_raw)
        film_root, muse_film = Path(spec["film_root"]), Path(spec["muse_film"])
        film_id = read_film_id(film_root)
        job_key = make_job_key(film_id, spec["wave_id"], spec["kind"], spec["account_id"])
        for slot in spec["slots"]:
            if not slot["request_id"]:
                slot["request_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"afp-lane:{job_key}:{slot['slot_id']}"))
        frozen = _freeze(spec["slots"])
    except SpecError as exc:
        return _refuse(exc.code, exc.reason)
    store = store or JobStore()
    digest = _frozen_digest(job_key, spec, frozen)
    job_dir = job_dir_name(job_key)
    job_dir_path = muse_film / "jobs" / job_dir
    afp_frozen = film_root / "takes" / "jobs" / job_dir
    job = {"film_id": film_id, "job_dir": job_dir}
    request = build_batch_request(job, spec)
    request_text = json.dumps(request, indent=2, ensure_ascii=False) + "\n"
    request_sha = sha256_text(request_text)

    resume = False
    with store.transaction() as conn:
        existing = conn.execute("SELECT * FROM jobs WHERE job_key = ?", (job_key,)).fetchone()
        if existing is not None:
            if existing["frozen_digest"] != digest:
                return _refuse("JOB_DIGEST_CONFLICT", f"{job_key} exists with another frozen input digest "
                                                      f"({existing['state']}); a changed input needs a new wave/job")
            if existing["state"] != "QUEUED":
                return {"ok": True, "code": "OK", "reason": "", "created": False, **_summary(existing)}
            resume = True
        else:
            clash = conn.execute("SELECT job_key FROM jobs WHERE job_dir = ?", (job_dir,)).fetchone()
            if clash is not None:   # 48 bits of sha256: not expected, but never share a directory
                return _refuse("JOB_DIR_COLLISION", f"{job_dir} already names {clash['job_key']}")
            for slot in spec["slots"]:
                bad = _identity_refusal(conn, film_id, job_key, slot)
                if bad:
                    return _refuse(*bad, slot_id=slot["slot_id"])
            at = _now()
            conn.execute(
                "INSERT INTO jobs (job_key, job_dir, film_id, film_root, muse_film, wave_id, kind, account_id, lease_key, "
                "epoch, muse_tag, quality, state, frozen_digest, job_dir_path, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?)",
                (job_key, job_dir, film_id, str(film_root), str(muse_film), spec["wave_id"], spec["kind"],
                 spec["account_id"], spec["lease_key"], spec["epoch"], spec["muse_tag"], spec["quality"], digest,
                 str(job_dir_path), at, at))
            for s in spec["slots"]:
                conn.execute(
                    "INSERT INTO children (job_key, slot_id, child_key, shot_id, shot_version, take_index, input_digest, "
                    "request_id, rebind_of, state, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)",
                    (job_key, s["slot_id"], s["child_key"], s["shot_id"], s["shot_version"], s["take_index"],
                     s["input_digest"], s["request_id"], canonical(s["rebind_of"]) if s["rebind_of"] else "", at))
            add_event(conn, film_id=film_id, job_key=job_key, kind="JOB_QUEUED", state="QUEUED",
                      payload={"job_dir": job_dir, "frozen_digest": digest, "slots": [s["slot_id"] for s in spec["slots"]]})

    try:
        # the Muse job dir is created EXCLUSIVELY (contract §5); a QUEUED job of ours may resume a partial one
        job_dir_path.parent.mkdir(parents=True, exist_ok=True)
        job_dir_path.mkdir(exist_ok=resume)
        afp_frozen.parent.mkdir(parents=True, exist_ok=True)
        afp_frozen.mkdir(exist_ok=resume)
    except FileExistsError:
        return _refuse("JOB_DIR_EXISTS", f"{job_dir_path} or {afp_frozen} already exists for a job with no row; it is "
                                         f"never reused", job_key=job_key)
    except OSError as exc:
        return _refuse("JOB_DIR_ERROR", f"{type(exc).__name__}: {exc}"[:300], job_key=job_key)
    try:
        frozen_doc = {"job_key": job_key, "job_dir": job_dir, "frozen_digest": digest, "slots": []}
        for s in spec["slots"]:
            slot_dir = afp_frozen / s["slot_id"]
            slot_dir.mkdir(exist_ok=True)
            atomic_text(slot_dir / "prompt.txt", s["prompt_text"])
            files = []
            for f in frozen[s["slot_id"]]["inputs"]:
                dst = slot_dir / f"{f['role']}__{f['name']}"
                shutil.copy2(f["src"], dst)
                if sha256_file(dst) != f["sha256"]:
                    raise OSError(f"{dst}: the frozen copy does not match its source hash")
                files.append({"role": f["role"], "file": dst.name, "sha256": f["sha256"]})
            frozen_doc["slots"].append({"slot_id": s["slot_id"], "prompt_sha256": frozen[s["slot_id"]]["prompt_sha256"],
                                        "input_digest": s["input_digest"], "inputs": files})
        atomic_json(afp_frozen / "frozen.json", frozen_doc)
        atomic_text(job_dir_path / "batch_request.json", request_text)
    except OSError as exc:
        return _refuse("FREEZE_FAILED", f"{type(exc).__name__}: {exc}"[:300], job_key=job_key)
    with store.transaction() as conn:
        conn.execute("UPDATE jobs SET state = 'ADMITTED', request_sha256 = ?, updated_at = ? WHERE job_key = ? AND "
                     "state = 'QUEUED'", (request_sha, _now(), job_key))
        add_event(conn, film_id=film_id, job_key=job_key, kind="JOB_ADMITTED", state="ADMITTED",
                  payload={"job_dir": job_dir, "lease_key": spec["lease_key"], "epoch": spec["epoch"],
                           "request_sha256": request_sha})
        row = conn.execute("SELECT * FROM jobs WHERE job_key = ?", (job_key,)).fetchone()
    project_events_safely(store, film_root, film_id)
    return {"ok": True, "code": "OK", "reason": "", "created": not resume, **_summary(row),
            "batch_request": str(job_dir_path / "batch_request.json"), "frozen_dir": str(afp_frozen)}


def project_events_safely(store: JobStore, film_root: Path | str, film_id: str) -> None:
    """The events.jsonl projection is repairable (the rows are authoritative): a failure here never fails a command."""
    try:
        project_events(store, film_root, film_id)
    except (OSError, sqlite3.Error):
        pass


def _summary(job: Any) -> dict[str, Any]:
    keys = ("job_key", "job_dir", "film_id", "state", "frozen_digest", "request_sha256", "job_dir_path")
    return {k: job[k] for k in keys}
