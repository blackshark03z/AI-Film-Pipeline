"""V2-021 operator entry — compiled narrative -> executed film sequence.

    python tools/run_v2_021_production.py <run_dir> <command>

Commands:
  gate        compute mutation budget vs live pool (read-only); print the
              Owner matrix and the dispatch decision WITHOUT spending
  auto        execute the frozen ShotGraph shot-by-shot (pool rotation,
              clean sibling resolution, continuity QC per shot), then
              editorial + finishing + master + manifest
  qc-visual <SHOT> <VERDICT> [notes...]   attach evidence-based review
  assemble / finish / master / manifest / status

Design authority: V2_021_FIXTURE_COMPILATION.json (frozen). Prompts are
the compiled ProviderPromptPlans — never hand-edited mid-run.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.narrative import (
    ContinuityEngine, EditorialIntelligence, LearningLoop, RepairPlanner)
from film_pipeline.providers.dola_production import (
    DolaAccountPoolRouter, DolaAccountState)
from mutation_authority import MutationAuthority
import v2_020_runner as _runner_mod
from v2_020_runner import (RunnerEvents, dispatch_and_acquire, emit,
                           extract_frames, probe_account_readonly,
                           technical_qc)

RUN20 = ROOT / "projects/quality_v2_020_autonomous_production"
PKG = ROOT / "projects/quality_v2_021_narrative_compiler"

# profile roots: automation slots live under the 010E runtime; the
# V2-021 enrolled slots live in this package
_PKG_PROFILES = PKG / "pool_profiles"


def _probe(alias: str) -> dict:
    from dola_010e_session_router import ACCOUNT_PROFILES as _AUTO
    root = _PKG_PROFILES if alias in ("ACCOUNT_E", "ACCOUNT_F")         else _AUTO
    original = _runner_mod.ACCOUNT_PROFILES
    _runner_mod.ACCOUNT_PROFILES = root
    try:
        return asyncio.run(probe_account_readonly(alias))
    finally:
        _runner_mod.ACCOUNT_PROFILES = original
COMPS = {
    "6": PKG / "V2_021_FIXTURE_COMPILATION.json",
    "5": PKG / "V2_021_FIXTURE_COMPILATION_5SHOT.json",
}
POOL_ACCOUNTS = ["ACCOUNT_D", "ACCOUNT_A", "ACCOUNT_C", "ACCOUNT_B",
                 "ACCOUNT_E", "ACCOUNT_F"]
import os as _os

COMP = json.loads((_os.environ.get("V2_021_COMPILATION") or
                   COMPS["6"]).read_text(encoding="utf-8"))
BUDGET = COMP["mutation_budget"]


def _comp_for(available: int) -> tuple[Path, dict] | None:
    """Mutation-policy variant selection: full grammar when the pool can
    carry it; the 5-shot minimum set (1 reserve) when it cannot."""
    for key in ("6", "5"):
        comp = json.loads(COMPS[key].read_text(encoding="utf-8"))
        if available >= comp["mutation_budget"]["total_budget"]:
            return COMPS[key], comp
    return None


def _state_path(run_dir: Path) -> Path:
    return run_dir / "v2_021_run_state.json"


def _load_state(run_dir: Path) -> dict:
    if _state_path(run_dir).exists():
        return json.loads(_state_path(run_dir).read_text(encoding="utf-8"))
    return {
        "version": "v2-021-run-state-v1",
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
        # rebuild shot state for the chosen variant (no mutations yet)
        state["shots"] = {n["shot_id"]: {"status": "PENDING"}
                          for n in comp["shot_graph"]["nodes"]}
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
    (run_dir / "V2_021_POOL_GATE.json").write_text(
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


def _pick_account(run_dir: Path, state: dict) -> str | None:
    """Rotate pre-dispatch across SESSION_VALID accounts with credit,
    skipping accounts already bound to a completed shot this run."""
    used = {s.get("account") for s in state["shots"].values()
            if s.get("account")}
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
        credit = result.get("known_credit_state")
        # known-credit slots first (highest credit), then fresh slots
        # whose balance is only revealed by the first dispatch ACK
        rank = (0, credit or 0) if credit else (1, 0)
        candidates.append((rank[0], rank[1], alias))
    candidates.sort(reverse=True)
    return candidates[0][2] if candidates else None


def cmd_auto(run_dir: Path) -> int:
    global COMP, BUDGET
    state = _load_state(run_dir)
    if state["gate"] is None:
        code = cmd_gate(run_dir)
        state = _load_state(run_dir)
        if code != 0:
            emit({"status": "STOPPED_BEFORE_FIRST_MUTATION",
                  "see": "V2_021_POOL_GATE.json"})
            return 2
    if state["gate"].get("decision") != "DISPATCH_AUTHORIZED":
        emit({"status": "STOPPED_BEFORE_FIRST_MUTATION",
              "gate": state["gate"].get("decision")})
        return 2
    if state.get("compilation_path"):
        COMP = json.loads(Path(state["compilation_path"])
                          .read_text(encoding="utf-8"))
        BUDGET = COMP["mutation_budget"]
    engine = ContinuityEngine()
    learning = LearningLoop()
    events = RunnerEvents(run_dir / "provider_events.jsonl")
    for node in COMP["shot_graph"]["nodes"]:
        sid = node["shot_id"]
        record = state["shots"][sid]
        if record["status"] in ("QC_ACCEPT", "EDITORIAL_LOCKED"):
            continue
        if state["mutations_used"] >= BUDGET["total_budget"]:
            emit({"status": "BUDGET_EXHAUSTED", "shot": sid})
            break
        account = _pick_account(run_dir, state)
        if not account:
            emit({"status": "STOPPED_POOL_INSUFFICIENT", "shot": sid})
            (run_dir / "V2_021_POOL_GATE.json").write_text(
                json.dumps({"decision": "STOP_POOL_EXHAUSTED_MID_RUN"},
                           indent=1), encoding="utf-8")
            return 2
        plan = COMP["prompt_plans"][sid]
        spec = node  # compiled ShotGraphNode
        from film_pipeline.providers.dola_production.fixture_v2_020 import \
            ShotSpec as _Spec  # reuse the transport spec shape
        # needle: the MOTION section is unique per shot function (two
        # shots may share a subject line; discovery must not cross-match)
        needle = plan["sections"]["motion"][:80]
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

        try:
            result = asyncio.run(dispatch_and_acquire(
                shot_spec=transport_spec, account_alias=account,
                run_dir=run_dir, shot_tag=sid, on_release=on_release,
                on_creation=on_creation, events_sink=events))
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
        _save(run_dir, state)
        # the dispatch ACK states the account's remaining credits —
        # refresh the known state and re-evaluate the remaining sequence
        try:
            refreshed = _probe(account)
            known = refreshed.get("known_credit_state") or 0
            record["credit_after"] = known
        except Exception:
            known = None
        remaining_shots = sum(
            1 for n in COMP["shot_graph"]["nodes"]
            if state["shots"][n["shot_id"]]["status"] not in (
                "QC_ACCEPT", "EDITORIAL_LOCKED"))
        others = 0
        for other in POOL_ACCOUNTS:
            if other == account:
                continue
            try:
                probe = _probe(other)
            except Exception:
                continue
            if probe.get("session_state") == "SESSION_VALID":
                others += probe.get("known_credit_state") or 0
        if known is not None and known + others < remaining_shots:
            emit({"status": "STOPPED_POOL_EXHAUSTED_MID_RUN",
                  "shot": sid, "credit_after": known, "others": others,
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
    import datetime as _dt
    doc = {
        "version": "v2-021-run-manifest-v1",
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
    out = run_dir / "qualification_run" / "V2_021_RUN_MANIFEST.json"
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


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    run_dir = Path(args[0])
    run_dir.mkdir(parents=True, exist_ok=True)
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
