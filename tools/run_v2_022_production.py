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
  assemble / finish / master / manifest / status

Design authority: V2_022_LONGFORM_COMPILATION.json (frozen, 24 shots,
Owner-authorized cap 25). Prompts are the compiled ProviderPromptPlans —
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
import os as _os

COMP = json.loads(Path(_os.environ.get("V2_022_COMPILATION")
                       or COMP_PATH).read_text(encoding="utf-8"))
BUDGET = COMP["mutation_budget"]


def _comp_for(available: int) -> tuple[Path, dict] | None:
    """Single frozen compilation (no variant selection). The mission
    starts when the pool can fund at least one shot today; mid-run
    guards still stop at exhaustion and the mission resumes as the
    daily quota refreshes."""
    comp = json.loads(COMP_PATH.read_text(encoding="utf-8"))
    if available >= 1:
        return COMP_PATH, comp
    return None


def _activate_comp(state: dict) -> None:
    """Bind module-level COMP/BUDGET to the run's chosen compilation.

    The state file is the run's authority: a fresh CLI process (auto,
    manifest) must execute/document the SAME variant the gate selected.
    Without this the import-time default leaks in — the V2-021 executed
    run's manifest documented a 6-node shot graph beside its 5-shot
    execution record.
    """
    global COMP, BUDGET
    path = state.get("compilation_path")
    if path and Path(path).exists():
        COMP = json.loads(Path(path).read_text(encoding="utf-8"))
        BUDGET = COMP["mutation_budget"]


def _state_path(run_dir: Path) -> Path:
    return run_dir / "v2_022_run_state.json"


def _load_state(run_dir: Path) -> dict:
    if _state_path(run_dir).exists():
        return json.loads(_state_path(run_dir).read_text(encoding="utf-8"))
    return {
        "version": "v2-022-run-state-v1",
        "fixture_id": COMP["fixture_id"] if "fixture_id" in COMP else
        COMP["version"],
        "shots": {sid: {"status": "PENDING"} for sid in
                  (n["shot_id"] for n in COMP["shot_graph"]["nodes"])},
        "mutations_used": 0, "repairs": [], "gate": None,
    }


def _save(run_dir: Path, state: dict) -> None:
    tmp = _state_path(run_dir).with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    import os
    os.replace(tmp, _state_path(run_dir))


def cmd_gate(run_dir: Path) -> int:
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
        decision = ("DISPATCH_AUTHORIZED"
                    if total_available >= budget
                    else "DISPATCH_AUTHORIZED_EXPECTED")
        state["compilation_path"] = str(comp_path)
        state["planned_shots"] = comp["mutation_budget"]["planned_shots"]
        # (re)build shot state for the chosen variant WITHOUT destroying
        # progress: a standalone re-gate mid-run must preserve existing
        # records; records for shots that leave the graph are archived
        # under retired_shots, never dropped
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
            "variant_shots": comp["mutation_budget"]["planned_shots"],
            "decision": decision,
            "rule": comp["mutation_budget"]["rule"],
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
    plan = state.get("account_plan") or {}
    if shot_id and shot_id in plan:
        planned = plan[shot_id]
        try:
            result = _probe(planned)
        except Exception:
            result = {}
        if result.get("session_state") == "SESSION_VALID":
            return planned
        emit({"event": "planned_account_unavailable", "shot": shot_id,
              "account": planned, "session": result.get("session_state")})
    completed = {"RELEASED", "RECEIPT_BOUND", "CREATION_BOUND",
                 "ACQUIRED", "ACQUIRED_AWAITING_VISUAL_QC", "QC_ACCEPT",
                 "EDITORIAL_LOCKED"}
    used = {s.get("account") for s in state["shots"].values()
            if s.get("account") and s.get("status") in completed}
    candidates = []
    for alias in POOL_ACCOUNTS:
        if alias in used:
            continue
        try:
            result = _probe(alias)
        except Exception:
            continue
        if result.get("session_state") != "SESSION_VALID":
            continue
        override = _stale_overrides().get(alias)
        if override is not None and override.get("hard_blocked_today"):
            continue   # provider daily-count cap: excluded for today
        credit = result.get("known_credit_state")
        if override is not None and credit is not None:
            # statement-arithmetic correction (documented in
            # stale_credit_overrides.json): the latest visible statement
            # predates a known later consumption on the same account
            credit = min(credit, int(override.get("effective_credit", 0)))
        # known credit>0 first, then fresh (balance revealed by first
        # ACK), known-zero LAST (a dispatch there would refuse)
        if credit:
            rank = (0, credit)
        elif credit is None:
            rank = (1, 0)
        else:
            rank = (2, 0)
        candidates.append((rank[0], rank[1], alias))
    candidates.sort(reverse=True)
    return candidates[0][2] if candidates else None


def _tranche_viable(known_after: int | None,
                    others: list[int | None]) -> bool:
    """Tranche doctrine for the quota-fed mission: continue while ANY
    account can fund the next shot (known credit >= 1, or an
    unobservable balance, which the next ACK re-verifies)."""
    if known_after is None or known_after >= 1:
        return True
    return any(c is None or c >= 1 for c in others)


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
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
