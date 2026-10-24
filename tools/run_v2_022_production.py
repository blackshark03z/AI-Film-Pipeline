"""V2-022 operator entry — 120-second longform mission (24 shots x 5s).

    python tools/run_v2_022_production.py <run_dir> <command>

Commands:
  gate        compute mutation budget vs live pool (read-only); print the
              Owner matrix and the dispatch decision WITHOUT spending
  auto        execute the frozen ShotGraph shot-by-shot (pool rotation,
              clean sibling resolution, continuity QC per shot); resumes
              across days as the pool quota refreshes; then editorial +
              finishing + master + manifest
  qc-visual <SHOT> <VERDICT> [notes...]   attach evidence-based review
  verify     read-only compilation integrity report (digest, state pin,
             trust anchor; never authorizes, never mutates state)
  assemble / finish / master / manifest / status

Design authority: V2_022_LONGFORM_COMPILATION.json (frozen, 24 shots;
Owner-authorized budget cap 27 = 24 shots + 1 repair reserve + 2
evidenced day-1 refusal extensions — see the mutation-budget rationale
in build_v2_022_compilation.py for the dated 25 -> 26 -> 27 lineage).
Prompts are the compiled ProviderPromptPlans —
never hand-edited mid-run. Derived from the live-proven V2-021 operator
flow; differences: single compilation (no 6/5 variant selection) and the
v2-022 state/manifest namespace.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.narrative import (
    ContinuityEngine, EditorialIntelligence, LearningLoop, RepairPlanner)
from film_pipeline.providers.dola_production import (
    DolaAccountPoolRouter, DolaAccountState)
from dola_010e_dispatch_journal import (
    ASSET_DOWNLOADED, CREATION_BOUND, DISPATCH_ARMED_EV,
    NETWORK_RELEASE_OBSERVED, SSE_RECEIPT_CAPTURED, TERMINAL_SUCCESS,
    DispatchJournal)
from mutation_authority import MutationAuthority
from v2_021_common import enrolled_profile_root, needle_for
import v2_020_runner as _runner_mod
from v2_020_runner import (RunnerEvents, dispatch_and_acquire, emit,
                           extract_frames, probe_account_readonly,
                           technical_qc)

# a shot whose journal shows any post-arm event has a latched provider
# mutation: it must be reconciled read-only, never re-dispatched
LATCHED_JOURNAL_KINDS = (DISPATCH_ARMED_EV, NETWORK_RELEASE_OBSERVED,
                         SSE_RECEIPT_CAPTURED, CREATION_BOUND,
                         ASSET_DOWNLOADED, TERMINAL_SUCCESS)
SKIP_STATUSES = ("QC_ACCEPT", "EDITORIAL_LOCKED", "RELEASED",
                 "RECEIPT_BOUND", "CREATION_BOUND", "ACQUIRED",
                 "ACQUIRED_AWAITING_VISUAL_QC")

RUN20 = ROOT / "projects/quality_v2_020_autonomous_production"
PKG = ROOT / "projects/quality_v2_022_longform_120s"


def _stale_overrides() -> dict:
    path = PKG / "stale_credit_overrides.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


@contextmanager
def _profile_root(alias: str):
    """Alias -> the profile root that holds its enrolled browser state.

    Mapping lives in v2_021_common (single source of truth shared with
    the reconcile and recover tools); this context manager only routes
    it into the runner module the dispatch flow reads.
    """
    original = _runner_mod.ACCOUNT_PROFILES
    _runner_mod.ACCOUNT_PROFILES = enrolled_profile_root(alias, original)
    try:
        yield
    finally:
        _runner_mod.ACCOUNT_PROFILES = original


def _probe(alias: str) -> dict:
    with _profile_root(alias):
        return asyncio.run(probe_account_readonly(alias))
COMP_PATH = PKG / "V2_022_LONGFORM_COMPILATION.json"
POOL_ACCOUNTS = ["ACCOUNT_D", "ACCOUNT_A", "ACCOUNT_C", "ACCOUNT_B",
                 "ACCOUNT_E", "ACCOUNT_F"]


class CompilationUnavailableError(RuntimeError):
    """Fail-closed bootstrap: the frozen V2-022 compilation is absent,
    unreadable, malformed or disagrees with the run state.

    The runtime compilation under projects/ is Git-ignored by design, so
    a fresh clean checkout does NOT have it. Importing this module and
    running read-only helpers (status on an existing run, help, tests)
    must stay possible; every path that would init run state, authorize
    a gate or dispatch a paid mutation must refuse with this error
    instead of crashing or synthesizing a compilation."""


def _compilation_path() -> Path:
    override = os.environ.get("V2_022_COMPILATION")
    return Path(override) if override else COMP_PATH


def load_compilation(path: Path | None = None) -> dict:
    """Load and structurally validate a V2-022 compilation; fail closed.

    Never synthesizes a live-approved compilation: the caller gets either
    a structurally consistent frozen document or an informative
    CompilationUnavailableError. A deterministic rebuild produced by
    tools/build_v2_022_compilation.py is fine for read-only simulation
    and tests but stays NON-AUTHORITATIVE for spend authority."""
    target = Path(path) if path is not None else _compilation_path()
    sample_hint = ("regenerate a deterministic, NON-AUTHORITATIVE sample "
                   "via `python tools/build_v2_022_compilation.py`, or "
                   "set V2_022_COMPILATION to an explicit frozen copy")
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise CompilationUnavailableError(
            f"V2-022 compilation missing: {target}. The runtime "
            f"compilation is Git-ignored; fresh checkouts do not carry "
            f"it. To continue read-only: {sample_hint}. Paid mutation "
            f"requires the genuinely frozen Owner-authorized file — "
            f"refusing to proceed.") from error
    except OSError as error:
        raise CompilationUnavailableError(
            f"V2-022 compilation unreadable: {target}: {error}") \
            from error
    try:
        comp = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CompilationUnavailableError(
            f"V2-022 compilation is not valid JSON: {target}: {error}") \
            from error
    problems: list[str] = []
    if not isinstance(comp, dict):
        problems.append("document is not a JSON object")
    else:
        graph = comp.get("shot_graph")
        budget = comp.get("mutation_budget")
        plans = comp.get("prompt_plans")
        nodes = graph.get("nodes") if isinstance(graph, dict) else None
        # type-check every nested container BEFORE indexing it: a wrong
        # container type (list/str where an object is required) must
        # route to this fail-closed error, never a raw AttributeError
        if not isinstance(graph, dict):
            problems.append("shot_graph must be a JSON object")
        if not isinstance(plans, dict):
            problems.append("prompt_plans must be a JSON object")
        if not isinstance(budget, dict):
            problems.append("mutation_budget must be a JSON object")
        if not isinstance(nodes, list) or not nodes:
            problems.append("shot_graph.nodes must be a non-empty list")
        else:
            bad = [i for i, node in enumerate(nodes)
                   if not isinstance(node, dict)
                   or not isinstance(node.get("shot_id"), str)
                   or not node.get("shot_id")]
            if bad:
                problems.append(
                    "shot_graph.nodes entries must be objects with a "
                    f"non-empty string shot_id (bad indexes: {bad[:4]})")
            elif isinstance(plans, dict):
                unplanned = [node["shot_id"] for node in nodes
                             if node["shot_id"] not in plans]
                if unplanned:
                    problems.append("prompt_plans missing shot ids: "
                                    f"{unplanned[:4]}")
        if isinstance(budget, dict):
            for key in ("total_budget", "planned_shots", "rule"):
                if key not in budget:
                    problems.append(f"mutation_budget.{key} missing")
        if isinstance(nodes, list) and nodes \
                and all(isinstance(node, dict) for node in nodes) \
                and isinstance(budget, dict):
            if len(nodes) != budget.get("planned_shots"):
                problems.append(
                    f"shot_graph.nodes ({len(nodes)}) disagrees with "
                    f"mutation_budget.planned_shots "
                    f"({budget.get('planned_shots')})")
    if problems:
        raise CompilationUnavailableError(
            f"V2-022 compilation malformed: {target}: "
            + "; ".join(problems))
    return comp


def _require_compilation() -> dict:
    """Bind the frozen compilation to COMP/BUDGET once (fail closed)."""
    global COMP, BUDGET
    if COMP is None:
        COMP = load_compilation()
        BUDGET = COMP["mutation_budget"]
    return COMP


def _compilation_sha256(path: Path) -> str:
    """Full-file SHA-256 of the frozen compilation bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _trusted_compilation_digest(path: Path) -> str | None:
    """Explicit, deliberate trust anchor for a compilation file: the
    V2_022_COMPILATION_SHA256 env var (visible operator intent) or a
    `<file>.sha256` sidecar created when the compilation was frozen.
    A structurally valid load alone is NEVER spend authority, and the
    builder never writes an anchor — pinning a digest is a separate,
    visible human act, so a regenerated sample cannot authorize paid
    generation by itself."""
    env = os.environ.get("V2_022_COMPILATION_SHA256", "").strip()
    if env:
        return env.split()[0].lower()
    sidecar = Path(str(path) + ".sha256")
    if sidecar.exists():
        try:
            fields = sidecar.read_text(encoding="utf-8").split()
        except OSError:
            return None
        return fields[0].lower() if fields else None
    return None


# Lazily loaded frozen compilation (see _require_compilation); None in a
# fresh checkout until an authorized path needs it
COMP: dict | None = None
BUDGET: dict | None = None


def _comp_for(available: int) -> tuple[Path, dict] | None:
    """Single frozen compilation (no variant selection). The mission
    starts when the pool can fund at least one shot today; mid-run
    guards still stop at exhaustion and the mission resumes as the
    daily quota refreshes. A fundable pool without a usable compilation
    fails closed rather than dispatching unbound."""
    if available < 1:
        return None
    path = _compilation_path()
    return path, load_compilation(path)


def _activate_comp(state: dict) -> None:
    """Bind module-level COMP/BUDGET to the run's chosen compilation.

    The state file is the run's authority: a fresh CLI process (auto,
    manifest) must execute/document the SAME variant the gate selected.
    Without this the import-time default leaks in — the V2-021 executed
    run's manifest documented a 6-node shot graph beside its 5-shot
    execution record. State and compilation must AGREE on identity,
    planned shots, gate budget AND full-file SHA-256: the gate pins the
    digest of the file it authorized, and any later byte change to the
    compilation (e.g. edited prompt_plans with identical metadata) is
    an integrity failure. A legacy state without a pinned digest is
    UNVERIFIED/AUTHORITY_REQUIRED unless an explicit trust anchor
    vouches for the current bytes — never silently approved, never
    auto-rebound."""
    global COMP, BUDGET
    path = state.get("compilation_path")
    if not path:
        # pre-gate planning surface only (fresh state init / ungated
        # manifest): structural load, no paid authority involved
        _require_compilation()
        return
    target = Path(path)
    if not target.exists():
        raise CompilationUnavailableError(
            f"run state names compilation {path} which no longer exists; "
            f"refusing to silently substitute a different compilation")
    comp = load_compilation(target)
    digest = _compilation_sha256(target)
    pinned = state.get("compilation_sha256")
    if pinned:
        if str(pinned).lower() != digest:
            raise CompilationUnavailableError(
                f"compilation integrity failure: state-pinned SHA-256 "
                f"{pinned} != current file digest {digest} at {target}; "
                f"the frozen design changed after authorization — stop "
                f"and reconcile evidence, never re-dispatch")
    else:
        anchor = _trusted_compilation_digest(target)
        if anchor is None:
            raise CompilationUnavailableError(
                f"run state carries no compilation SHA-256 and no trusted "
                f"anchor exists for {target}; legacy state is "
                f"UNVERIFIED/AUTHORITY_REQUIRED — run the read-only "
                f"`verify` command to report the current digest, pin it "
                f"deliberately (V2_022_COMPILATION_SHA256 or a "
                f"{target}.sha256 sidecar) and re-gate")
        if anchor != digest:
            raise CompilationUnavailableError(
                f"compilation integrity failure: trusted anchor "
                f"{anchor} != current file digest {digest} at {target}")
    identity = comp.get("fixture_id", comp.get("version"))
    recorded_identity = state.get("fixture_id")
    if recorded_identity is not None and identity != recorded_identity:
        raise CompilationUnavailableError(
            f"run state fixture identity '{recorded_identity}' "
            f"disagrees with compilation '{identity}' at {path}; "
            f"refusing to rebind run identity")
    recorded_planned = state.get("planned_shots")
    if recorded_planned is not None and \
            comp["mutation_budget"]["planned_shots"] != recorded_planned:
        raise CompilationUnavailableError(
            f"run state planned_shots {recorded_planned} disagrees with "
            f"compilation "
            f"{comp['mutation_budget']['planned_shots']} at {path}")
    gate_budget = (state.get("gate") or {}).get("computed_budget")
    if gate_budget is not None and \
            comp["mutation_budget"]["total_budget"] != gate_budget:
        raise CompilationUnavailableError(
            f"gate-computed budget {gate_budget} disagrees with "
            f"compilation total_budget "
            f"{comp['mutation_budget']['total_budget']} at {path}")
    COMP = comp
    BUDGET = comp["mutation_budget"]


def _state_path(run_dir: Path) -> Path:
    return run_dir / "v2_022_run_state.json"


def _load_state(run_dir: Path) -> dict:
    if _state_path(run_dir).exists():
        return json.loads(_state_path(run_dir).read_text(encoding="utf-8"))
    # initializing a NEW run state needs the frozen shot graph — fail
    # closed (informative) when no usable compilation exists; resuming
    # an EXISTING run stays read-only and compilation-free
    comp = _require_compilation()
    return {
        "version": "v2-022-run-state-v1",
        "fixture_id": comp["fixture_id"] if "fixture_id" in comp else
        comp["version"],
        "shots": {sid: {"status": "PENDING"} for sid in
                  (n["shot_id"] for n in comp["shot_graph"]["nodes"])},
        "mutations_used": 0, "repairs": [], "gate": None,
    }


def _save(run_dir: Path, state: dict) -> None:
    tmp = _state_path(run_dir).with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    import os
    os.replace(tmp, _state_path(run_dir))


def cmd_gate(run_dir: Path) -> int:
    # the gate cannot state a budget or authorize anything without the
    # frozen compilation — refuse BEFORE any account probe (zero
    # provider access when the design authority is missing)
    _require_compilation()
    state = _load_state(run_dir)
    matrix = {}
    total_available = 0
    for alias in POOL_ACCOUNTS:
        try:
            result = _probe(alias)
        except Exception:
            result = {"account_alias": alias,
                      "session_state": "PROBE_FAILED"}
        matrix[alias] = {"session": result.get("session_state"),
                         "credit": result.get("known_credit_state"),
                         "statements": (result.get("credit_statements")
                                        or [])[-1:]}
        if result.get("session_state") == "SESSION_VALID" and \
                result.get("known_credit_state"):
            total_available += result["known_credit_state"]
    # fresh-enrolled slots have UNOBSERVABLE credit (the provider states
    # the balance only inside a generation ACK). They are eligible for a
    # BOUNDED first dispatch at the observed daily quota (3/account,
    # observed on two accounts); the gate re-verifies after every ACK.
    EXPECTED_QUOTA = 3
    unobservable = [a for a, v in matrix.items()
                    if v.get("session") == "SESSION_VALID"
                    and v.get("credit") is None]
    expected_total = total_available + EXPECTED_QUOTA * len(unobservable)
    chosen = _comp_for(max(total_available, expected_total))
    if chosen is None:
        budget = BUDGET["total_budget"]
        decision = "STOP_BEFORE_FIRST_MUTATION"
        state["gate"] = {
            "probed_at": json.dumps(matrix),
            "total_available_credits": total_available,
            "expected_total_with_quota": expected_total,
            "unobservable_slots": unobservable,
            "computed_budget": budget,
            "decision": decision,
            "rule": BUDGET["rule"],
        }
    else:
        comp_path, comp = chosen
        budget = comp["mutation_budget"]["total_budget"]
        digest = _compilation_sha256(comp_path)
        pinned = state.get("compilation_sha256")
        # a mid-run re-gate may stand on the run's own previously pinned
        # digest; a first gate needs an explicit trust anchor
        pinned_ok = (pinned is not None and str(pinned).lower() == digest
                     and state.get("compilation_path") == str(comp_path))
        anchor = _trusted_compilation_digest(comp_path)
        anchor_ok = anchor is not None and anchor == digest
        if pinned_ok or anchor_ok:
            decision = ("DISPATCH_AUTHORIZED"
                        if total_available >= budget
                        else "DISPATCH_AUTHORIZED_EXPECTED")
            state["compilation_path"] = str(comp_path)
            state["compilation_sha256"] = digest
            state["planned_shots"] = comp["mutation_budget"]["planned_shots"]
            # (re)build shot state for the chosen variant WITHOUT
            # destroying progress: a standalone re-gate mid-run must
            # preserve existing records; records for shots that leave
            # the graph are archived under retired_shots, never dropped
            previous = state.get("shots") or {}
            nodes = [n["shot_id"] for n in comp["shot_graph"]["nodes"]]
            retired = state.setdefault("retired_shots", {})
            for sid, record in previous.items():
                if sid not in nodes:
                    retired.setdefault(sid, record)
            state["shots"] = {sid: previous.get(sid) or {"status": "PENDING"}
                              for sid in nodes}
            state["gate"] = {
                "probed_at": json.dumps(matrix),
                "total_available_credits": total_available,
                "expected_total_with_quota": expected_total,
                "unobservable_slots": unobservable,
                "computed_budget": budget,
                "compilation": str(comp_path),
                "compilation_sha256": digest,
                "variant_shots": comp["mutation_budget"]["planned_shots"],
                "decision": decision,
                "rule": comp["mutation_budget"]["rule"],
            }
        else:
            # fail closed BEFORE authorizing anything: a structurally
            # valid file with no deliberate digest provenance is not
            # spend authority, and anchor!=file means the frozen design
            # changed after pinning
            decision = ("STOP_COMPILATION_TRUST_MISSING" if anchor is None
                        else "STOP_COMPILATION_TRUST_MISMATCH")
            state["gate"] = {
                "probed_at": json.dumps(matrix),
                "total_available_credits": total_available,
                "expected_total_with_quota": expected_total,
                "unobservable_slots": unobservable,
                "computed_budget": budget,
                "decision": decision,
                "rule": comp["mutation_budget"]["rule"],
                "unpinned_digest": digest,
                "pin_instruction":
                    "pin the frozen compilation digest deliberately "
                    "(set V2_022_COMPILATION_SHA256 or create "
                    f"{comp_path}.sha256) and re-run gate; a regenerated "
                    "builder sample is never spend authority by itself",
            }
    _save(run_dir, state)
    (run_dir / "V2_022_POOL_GATE.json").write_text(
        json.dumps({"budget": budget, "pool": matrix,
                    "total_available": total_available,
                    "decision": decision,
                    "owner_matrix_required": decision !=
                    "DISPATCH_AUTHORIZED"},
                   indent=1, ensure_ascii=False), encoding="utf-8")
    emit({"status": decision, "budget": budget,
          "available": total_available,
          "pool": {a: v["credit"] for a, v in matrix.items()}})
    return 0 if decision == "DISPATCH_AUTHORIZED" else 2


def _pick_account(run_dir: Path, state: dict,
                  shot_id: str | None = None) -> str | None:
    """Rotate pre-dispatch across SESSION_VALID accounts with credit,
    skipping accounts already bound to a completed shot this run. A
    per-shot account_plan (operator-authored) is honored when that
    account still holds a valid session, else rotation resumes."""
    planned = (state.get("account_plan") or {}).get(shot_id)
    overrides = _stale_overrides()
    candidates = []
    for order, alias in enumerate(POOL_ACCOUNTS):
        override = overrides.get(alias) or {}
        if override.get("hard_blocked_today"):
            continue
        try:
            result = _probe(alias)
        except Exception:
            continue
        if result.get("session_state") != "SESSION_VALID":
            continue
        credit = result.get("known_credit_state")
        if credit is not None:
            credit = int(credit)
            if "effective_credit" in override:
                # Evidenced consumption can supersede a stale statement.
                credit = min(credit, int(override["effective_credit"]))
            if credit <= 0:
                continue  # never spend cap against a known-zero account
        candidates.append((
            0 if credit is not None else 1,  # known-positive before unknown
            0 if alias == planned else 1,    # plan preference, not bypass
            -(credit or 0),                  # prefer observed headroom
            order, alias))
    if planned and not any(item[-1] == planned for item in candidates):
        emit({"event": "planned_account_unavailable", "shot": shot_id,
              "account": planned, "reason": "session/credit/hard-block"})
    candidates.sort()
    return candidates[0][-1] if candidates else None


def _tranche_viable(known_after: int | None,
                    others: list[int | None]) -> bool:
    """Tranche doctrine for the quota-fed mission: continue while ANY
    account can fund the next shot (known credit >= 1, or an
    unobservable balance, which the next ACK re-verifies)."""
    if known_after is None or known_after >= 1:
        return True
    return any(c is None or c >= 1 for c in others)


def _receipt_miss_streak_stop(streak: int) -> bool:
    """A receipt-miss is a latched release whose delivery failed (one is
    recoverable read-only); a consecutive streak means the session or
    transport degraded — stop and recover before burning more of the
    Owner-authorized cap."""
    return streak >= 2


def cmd_auto(run_dir: Path) -> int:
    state = _load_state(run_dir)
    if state["gate"] is None:
        code = cmd_gate(run_dir)
        state = _load_state(run_dir)
        if code != 0:
            emit({"status": "STOPPED_BEFORE_FIRST_MUTATION",
                  "see": "V2_022_POOL_GATE.json"})
            return 2
    if state["gate"].get("decision") not in (
            "DISPATCH_AUTHORIZED", "DISPATCH_AUTHORIZED_EXPECTED"):
        emit({"status": "STOPPED_BEFORE_FIRST_MUTATION",
              "gate": state["gate"].get("decision")})
        return 2
    _activate_comp(state)
    engine = ContinuityEngine()
    learning = LearningLoop()
    events = RunnerEvents(run_dir / "provider_events.jsonl")
    miss_streak = 0
    for node in COMP["shot_graph"]["nodes"]:
        sid = node["shot_id"]
        record = state["shots"][sid]
        if record["status"] in SKIP_STATUSES:
            continue
        journal_path = run_dir / f"dispatch_journal_{sid}.jsonl"
        if journal_path.exists():
            journal = DispatchJournal(journal_path, "")
            if any(journal.has(kind) for kind in LATCHED_JOURNAL_KINDS):
                emit({"status": "SKIPPED_RELEASE_LATCHED", "shot": sid,
                      "reason": "journal holds a provider release; use "
                                "read-only reconciliation, never "
                                "re-dispatch"})
                continue
        effective_budget = state.get(
            "effective_budget", BUDGET["total_budget"])
        if state["mutations_used"] >= effective_budget:
            emit({"status": "BUDGET_EXHAUSTED", "shot": sid})
            break
        account = _pick_account(run_dir, state, shot_id=sid)
        if not account:
            emit({"status": "STOPPED_POOL_INSUFFICIENT", "shot": sid})
            (run_dir / "V2_022_POOL_GATE.json").write_text(
                json.dumps({"decision": "STOP_POOL_EXHAUSTED_MID_RUN"},
                           indent=1), encoding="utf-8")
            return 2
        plan = COMP["prompt_plans"][sid]
        spec = node  # compiled ShotGraphNode
        from film_pipeline.providers.dola_production.fixture_v2_020 import \
            ShotSpec as _Spec  # reuse the transport spec shape
        needle = needle_for(COMP, sid)
        transport_spec = _Spec(
            shot_id=sid, role=node["function"],
            prompt=plan["compiled_text"],
            needle=needle,
            duration_class=node["provider_requirements"]["duration_class"],
            camera=node["camera_intent"]["movement"],
            screen_direction=node["continuity_constraints"][0].split()
           [-1] if node["continuity_constraints"] else "left-to-right")

        slot = run_dir / "slots" / sid
        slot.mkdir(parents=True, exist_ok=True)
        auth = MutationAuthority(slot, f"QUALITY-V2-021/{sid}")
        if auth.authority != "OPEN":
            emit({"status": "STOPPED_GOVERNANCE_GAP", "shot": sid})
            return 1
        record["status"] = "RESERVED"
        record["account"] = account
        _save(run_dir, state)
        auth._event("MUTATION_RESERVED", budget_kind=sid)

        def on_release(info: dict, _sid=sid, _auth=auth) -> None:
            _auth.consume(_sid)
            state["mutations_used"] += 1
            record.update({"status": "RELEASED",
                           "conversation": info["conversation_id"],
                           "attempt_id": info["attempt_id"]})
            _save(run_dir, state)

        def on_creation(info: dict, _sid=sid) -> None:
            record.update({"status": "CREATION_BOUND",
                           "creation_ids": info["creation_ids"]})
            _save(run_dir, state)

        identities = {}
        ident_path = PKG / "slot_identities.json"
        if ident_path.exists():
            identities = json.loads(
                ident_path.read_text(encoding="utf-8"))
        expected_nick = (identities.get(account) or {}).get("nickname")
        try:
            with _profile_root(account):
                result = asyncio.run(dispatch_and_acquire(
                    shot_spec=transport_spec, account_alias=account,
                    run_dir=run_dir, shot_tag=sid, on_release=on_release,
                    on_creation=on_creation, events_sink=events,
                    expected_nickname=expected_nick))
        except RuntimeError as error:
            message = str(error)
            record["status"] = "FAILED"
            record["error"] = message[:200]
            _save(run_dir, state)
            emit({"status": message.split(":")[0], "shot": sid})
            if message.startswith("OWNER_AMBIGUITY_GATE:receipt"):
                # consecutive receipt-misses: each one is a latched
                # release whose delivery failed; one is recoverable
                # read-only, a streak means the session/transport
                # degraded — stop and recover before burning more
                # of the Owner-authorized cap (day-1 live: 4 misses
                # in a row produced 3 recoveries + 1 refusal repair)
                miss_streak += 1
                if _receipt_miss_streak_stop(miss_streak):
                    emit({"status": "STOPPED_RECEIPT_MISS_STREAK",
                          "shot": sid, "streak": miss_streak,
                          "recover": "run read-only recovery "
                                     "(v2_021_recover.py scan/bind) "
                                     "before any resume"})
                    state["gate"]["receipt_miss_streak_stop"] = miss_streak
                    _save(run_dir, state)
                    return 2
            else:
                miss_streak = 0
            continue
        record.update({"status": "ACQUIRED", "asset": result["asset_path"],
                       "sha256": result["asset_sha256"],
                       "authority": result["variant_authority"]})
        record.pop("error", None)
        _save(run_dir, state)
        # the dispatch ACK states the account's remaining credits —
        # refresh the known state and re-evaluate the remaining sequence
        try:
            refreshed = _probe(account)
            known_credit = refreshed.get("known_credit_state")
        except Exception:
            known_credit = None
        record["credit_after"] = known_credit
        # Tranche doctrine (v2-022): the mission is quota-fed across
        # days, so the run continues while ANY account can fund the NEXT
        # shot; it stops only when no dispatch is currently possible and
        # resumes as the daily quota refreshes. A SESSION_VALID slot with
        # unobservable balance counts as fundable (each ACK re-verifies).
        remaining_shots = sum(
            1 for n in COMP["shot_graph"]["nodes"]
            if state["shots"][n["shot_id"]]["status"] in (
                "PENDING", "FAILED"))
        others = []
        overrides = _stale_overrides()
        for other in POOL_ACCOUNTS:
            if other == account:
                continue
            if (overrides.get(other) or {}).get("hard_blocked_today"):
                continue   # provider daily-count cap: excluded for today
            try:
                probe = _probe(other)
            except Exception:
                continue
            if probe.get("session_state") == "SESSION_VALID":
                others.append(probe.get("known_credit_state"))
        others_total = sum(c if c is not None else 1 for c in others)
        known = known_credit if known_credit is not None else 1
        if not _tranche_viable(known_credit, others):
            emit({"status": "STOPPED_POOL_EXHAUSTED_MID_RUN",
                  "shot": sid, "credit_after": known,
                  "others": others_total,
                  "remaining_shots": remaining_shots})
            state["gate"]["mid_run_stop"] = True
            _save(run_dir, state)
            return 2
        learning.record("clean sibling resolution succeeded on free route",
                        domain="variants", evidence=[sid])
        # technical QC + evidence scaffold (contact sheet for review)
        asset = Path(result["asset_path"])
        frames = extract_frames(asset, run_dir / "frames" / sid)
        tech = technical_qc(asset, run_dir / "frames" / sid)
        tech["frames_extracted"] = frames
        record["technical"] = tech
        record["status"] = "ACQUIRED_AWAITING_VISUAL_QC"
        # contact sheet for evidence-based visual review (Phase M)
        sheet = run_dir / "contact_sheets" / f"{sid}.png"
        sheet.parent.mkdir(parents=True, exist_ok=True)
        paths = sorted((run_dir / "frames" / sid).glob("f_*.png"))
        if paths:
            from PIL import Image
            picks = [paths[i] for i in (
                0, len(paths) // 5, 2 * len(paths) // 5,
                3 * len(paths) // 5, 4 * len(paths) // 5,
                len(paths) - 1)]
            thumbs = [Image.open(pp).resize((320, 180)) for pp in picks]
            grid = Image.new("RGB", (320 * 3, 180 * 2))
            for i, th in enumerate(thumbs):
                grid.paste(th, ((i % 3) * 320, (i // 3) * 180))
            grid.save(sheet)
        record["contact_sheet"] = str(sheet)
        _save(run_dir, state)
        emit({"status": "ACQUIRED", "shot": sid, "frames": frames,
              "authority": result["variant_authority"],
              "contact_sheet": str(sheet)})
    _save(run_dir, state)
    emit({"status": "EXECUTION_PHASE_COMPLETE",
          "mutations_used": state["mutations_used"]})
    return 0


def cmd_qc_visual(run_dir: Path, shot_id: str, verdict: str,
                  notes: list[str]) -> int:
    state = _load_state(run_dir)
    record = state["shots"][shot_id]
    engine = ContinuityEngine()
    dimensions = {}
    for dim in engine.DIMENSIONS:
        dimensions[dim] = {"verdict": "PASS",
                           "evidence": " ".join(notes) or
                                       "evidence-based review"}
    if verdict != "ACCEPT":
        dimensions["WORLD"] = {"verdict": "FAIL",
                               "evidence": " ".join(notes)}
    report = engine.evaluate_shot(
        shot_id=shot_id, technical=record.get("technical", {}),
        evidence={"shot_local": dimensions})
    record["qc_verdict"] = report.verdict
    record["qc_failure_class"] = report.failure_class
    record["status"] = {"ACCEPT": "QC_ACCEPT",
                        "REPAIR_REQUIRED": "QC_REPAIR_REQUIRED",
                        "REJECT": "QC_REJECT"}[report.verdict]
    _save(run_dir, state)
    emit({"status": "VISUAL_RECORDED", "shot": shot_id,
          "verdict": report.verdict})
    return 0


def cmd_assemble(run_dir: Path) -> int:
    state = _load_state(run_dir)
    accepted = [sid for sid, r in state["shots"].items()
                if r.get("qc_verdict") == "ACCEPT"]
    if len(accepted) < 2:
        emit({"status": "ASSEMBLY_BLOCKED", "accepted": accepted})
        return 1
    trims_path = run_dir / "editorial_trims.json"
    trims = json.loads(trims_path.read_text(encoding="utf-8")) \
        if trims_path.exists() else {}
    inputs, filters, vlabels = [], [], []
    total = 0
    for i, sid in enumerate(accepted):
        rec = state["shots"][sid]
        frames = int(rec["technical"]["frames_extracted"])
        trim = int(trims.get(sid, 0))
        end = max(frames - trim, 1)
        total += end
        inputs += ["-i", rec["asset"]]
        filters.append(f"[{i}:v]trim=start_frame=0:end_frame={end},"
                       f"setpts=PTS-STARTPTS[v{i}]")
        vlabels.append(f"[v{i}]")
    filters.append("".join(vlabels) +
                   f"concat=n={len(accepted)}:v=1:a=0[out]")
    out = run_dir / "qualification_run" / "SEQUENCE_PROOF.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
         ";".join(filters), "-map", "[out]", "-c:v", "libx264",
         "-crf", "14", "-pix_fmt", "yuv420p", str(out)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        emit({"status": "ASSEMBLY_FAILED", "stderr": proc.stderr[-400:]})
        return 1
    count = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-count_frames", "-show_entries", "stream=nb_read_frames",
         "-of", "csv=p=0", str(out)], capture_output=True, text=True)
    state["editorial"] = {
        "accepted": accepted,
        "ranges": {sid: [0, max(
            int(state["shots"][sid]["technical"]["frames_extracted"])
            - int(trims.get(sid, 0)), 1)] for sid in accepted},
        "proof": str(out), "sha256": hashlib.sha256(
            out.read_bytes()).hexdigest(),
        "frames": int(count.stdout.strip() or 0)}
    _save(run_dir, state)
    emit({"status": "ASSEMBLED", "frames": state["editorial"]["frames"],
          "sha": state["editorial"]["sha256"][:16]})
    return 0


def cmd_finish(run_dir: Path) -> int:
    state = _load_state(run_dir)
    proof = Path(state["editorial"]["proof"])
    fm = run_dir / "qualification_run" / "FINISH_MASTER.mov"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(proof),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-shortest", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "128k", str(fm)], capture_output=True)
    state["finishing"] = {"path": str(fm),
                          "sha256": hashlib.sha256(
                              fm.read_bytes()).hexdigest(),
                          "note": "silent-track finish (doubles or "
                                  "silent provider audio)"}
    _save(run_dir, state)
    emit({"status": "FINISHED", "sha": state["finishing"]["sha256"][:16]})
    return 0


def cmd_master(run_dir: Path) -> int:
    state = _load_state(run_dir)
    fm = Path(state["finishing"]["path"])
    dm = run_dir / "qualification_run" / "DISTRIBUTION_MASTER.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(fm),
                    "-c:v", "copy", "-af",
                    "loudnorm=I=-14:TP=-1.2:LRA=11", "-c:a", "aac",
                    "-b:a", "192k", "-movflags", "+faststart", str(dm)],
                   capture_output=True)
    authorities = {r.get("authority") for r in state["shots"].values()
                   if r.get("asset")}
    watermark = ("ABSENT_BY_PROVIDER_ISSUED_AUTHORITY"
                 if authorities == {"PROVIDER_ISSUED_UNWATERMARKED"}
                 else "MIXED:" + ",".join(sorted(str(a) for a in
                                                 authorities)))
    state["master"] = {"path": str(dm), "sha256": hashlib.sha256(
        dm.read_bytes()).hexdigest(), "watermark": watermark}
    state["status"] = "COMPLETED"
    _save(run_dir, state)
    emit({"status": "MASTER_DONE", "sha": state["master"]["sha256"],
          "watermark": watermark})
    return 0


def cmd_manifest(run_dir: Path) -> int:
    state = _load_state(run_dir)
    _activate_comp(state)
    import datetime as _dt
    doc = {
        "version": "v2-022-run-manifest-v1",
        "generated_at": _dt.datetime.now(
            _dt.timezone.utc).isoformat(),
        "input": COMP["input"],
        "story_graph": COMP["story_graph"],
        "shot_graph": COMP["shot_graph"],
        "prompt_plans": {sid: {"sha256": p["sha256"]}
                         for sid, p in COMP["prompt_plans"].items()},
        "execution": state,
        "learning": state.get("learning", []),
    }
    out = run_dir / "qualification_run" / "V2_022_RUN_MANIFEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    emit({"status": "MANIFEST_WRITTEN", "path": str(out)})
    return 0


def cmd_status(run_dir: Path) -> int:
    state = _load_state(run_dir)
    emit({"mutations_used": state["mutations_used"],
          "gate": (state.get("gate") or {}).get("decision"),
          "shots": {sid: {"status": r["status"],
                          "verdict": r.get("qc_verdict"),
                          "authority": r.get("authority")}
                    for sid, r in state["shots"].items()}})
    return 0


def cmd_verify(run_dir: Path) -> int:
    """Read-only integrity report for compilation provenance.

    Never mutates run state and never authorizes anything: it reports
    the current full-file SHA-256, whether the run state pins a digest,
    and which deliberate pinning step (env var or sidecar) an
    AUTHORITY_REQUIRED / legacy state needs before gate will authorize.
    This is the migration/report path for pre-integrity run states."""
    state = json.loads(_state_path(run_dir).read_text(
        encoding="utf-8")) if _state_path(run_dir).exists() else {}
    path = Path(state.get("compilation_path") or _compilation_path())
    report = {"command": "verify", "compilation": str(path)}
    if not path.exists():
        report["status"] = "COMPILATION_MISSING"
        emit(report)
        return 4
    try:
        load_compilation(path)
        report["structure"] = "OK"
    except CompilationUnavailableError as error:
        report["status"] = "COMPILATION_MALFORMED"
        report["error"] = str(error)[:300]
        emit(report)
        return 4
    digest = _compilation_sha256(path)
    report["sha256"] = digest
    pinned = state.get("compilation_sha256")
    anchor = _trusted_compilation_digest(path)
    if pinned:
        report["state_pinned"] = pinned
        report["status"] = ("INTEGRITY_OK" if str(pinned).lower() == digest
                            else "INTEGRITY_MISMATCH")
    elif anchor is not None:
        report["anchor"] = anchor
        report["status"] = ("ANCHOR_OK_STATE_UNPINNED"
                            if anchor == digest else "ANCHOR_MISMATCH")
    else:
        report["status"] = "AUTHORITY_REQUIRED"
        report["pin_instruction"] = (
            f"pin the digest deliberately: create {path}.sha256 "
            "containing the reported sha256 (or set "
            "V2_022_COMPILATION_SHA256), then re-run gate; a structural "
            "load or a regenerated builder sample is not authority")
    emit(report)
    return 0 if report["status"] in ("INTEGRITY_OK",
                                     "ANCHOR_OK_STATE_UNPINNED") else 2


def _acquire_run_lock(run_dir: Path) -> Path | None:
    lock = run_dir / "run.lock"
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return lock
    except FileExistsError:
        return None


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    run_dir = Path(args[0])
    run_dir.mkdir(parents=True, exist_ok=True)
    lock = None
    if args[1] in ("auto", "gate"):
        lock = _acquire_run_lock(run_dir)
        if lock is None:
            emit({"status": "STOPPED_RUN_LOCKED",
                  "reason": "another runner instance holds run.lock "
                            "(zombie protection); delete the lock only "
                            "after verifying no runner process lives"})
            return 3
    try:
        return _dispatch_command(run_dir, args)
    except CompilationUnavailableError as error:
        emit({"status": "COMPILATION_UNAVAILABLE",
              "error": str(error)[:500],
              "action": "fail-closed: no state init, no probe, no "
                        "dispatch; regenerate a non-authoritative "
                        "sample with tools/build_v2_022_compilation.py "
                        "for read-only simulation only"})
        return 4
    finally:
        if lock is not None:
            lock.unlink(missing_ok=True)


def _dispatch_command(run_dir: Path, args: list[str]) -> int:
    command = args[1]
    if command == "gate":
        return cmd_gate(run_dir)
    if command == "auto":
        return cmd_auto(run_dir)
    if command == "qc-visual":
        return cmd_qc_visual(run_dir, args[2], args[3], args[4:])
    if command == "assemble":
        return cmd_assemble(run_dir)
    if command == "finish":
        return cmd_finish(run_dir)
    if command == "master":
        return cmd_master(run_dir)
    if command == "manifest":
        return cmd_manifest(run_dir)
    if command == "status":
        return cmd_status(run_dir)
    if command == "verify":
        return cmd_verify(run_dir)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
