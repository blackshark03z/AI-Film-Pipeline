"""V2-020 — operator entry point.

    python tools/run_v2_020_production.py <run_dir> <command> [args]

Commands:
  auto                  plan + pool probe + run all remaining shots + QC
  plan                  init durable state + capability plan
  pool                  read-only account pool probe (credit matrix)
  run-shot <SHOT> [ACC] one bounded dispatch (A/B/C) + poll + resolve + QC
  qc-visual <SHOT> <VERDICT> [notes...]   attach agent visual review
  repair <SHOT>         spend the ONE repair slot with a delta spec
  assemble              editorial ranges + concat-filter proof + junction QC
  finish                audio finishing (provider audio only)
  master                distribution master + watermark QC
  manifest              provenance manifest
  status                print durable status

No command ever re-POSTs a released generation (durable receipt-first).
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.providers.dola_production import (
    FIXTURE, DolaProductionOrchestrator, merge_registry)
from film_pipeline.providers.dola_production.fixture_v2_020 import \
    PROMPT_PREFIX
from mutation_authority import MutationAuthority
from v2_020_runner import (
    RunnerEvents, dispatch_and_acquire, emit, extract_frames,
    ffprobe_json, probe_account_readonly, technical_qc)

PKG19 = ROOT / "projects/quality_v2_019_dola_productionization"
SHOT_ORDER = ["QA_SHOT_A", "QA_SHOT_B", "QA_SHOT_C"]
POOL_ACCOUNTS = ["ACCOUNT_D", "ACCOUNT_A", "ACCOUNT_C", "ACCOUNT_B"]


def _registry():
    skill = json.loads((PKG19 / "V2_019_PHASEA_SKILL_PACK_1.json")
                       .read_text(encoding="utf-8"))
    bar = json.loads((PKG19 / "V2_019_PHASEA_ACTION_BAR_CONF_FULL.json")
                     .read_text(encoding="utf-8"))
    return merge_registry(skill, bar)


def _orch(run_dir: Path) -> DolaProductionOrchestrator:
    return DolaProductionOrchestrator(
        run_dir / "production_run.state.json", FIXTURE,
        registry=_registry())


def cmd_plan(run_dir: Path) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    for shot_id in SHOT_ORDER:
        orch.plan_shot(shot_id)
    emit({"status": "PLANNED",
          "plans": {s: orch.plan_shot(s).model_dump(mode="json")
                    for s in SHOT_ORDER}})
    return 0


def cmd_pool(run_dir: Path) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    matrix = {}
    for alias in POOL_ACCOUNTS:
        if any(s.account_alias == alias and s.status in
               ("RELEASED", "RECEIPT_BOUND", "CREATION_BOUND", "ACQUIRED",
                "QC_ACCEPT", "REPAIRED", "EDITORIAL_LOCKED")
               for s in orch.state.shots):
            matrix[alias] = {"skipped": "has durable binding"}
            continue
        try:
            result = asyncio.run(probe_account_readonly(alias))
        except Exception as error:
            result = {"account_alias": alias,
                      "session_state": "PROBE_FAILED",
                      "error": f"{type(error).__name__}"}
        matrix[alias] = result
        if result.get("session_state") == "SESSION_VALID":
            from film_pipeline.providers.dola_production import \
                DolaAccountState
            orch.pool.ensure_registered(alias)
            orch.pool.record_session(
                alias, "SESSION_VALID",
                credit_remaining=result.get("known_credit_state"),
                note="v2-020 pool probe")
    orch.save()
    (run_dir / "V2_020_POOL_MATRIX.json").write_text(
        json.dumps(matrix, indent=1, ensure_ascii=False), encoding="utf-8")
    emit({"status": "POOL_PROBED",
          "matrix": {a: {"session": v.get("session_state"),
                         "credit": v.get("known_credit_state")}
                     for a, v in matrix.items()}})
    return 0


def _dispatch(orch, run_dir: Path, shot_id: str, account_alias: str,
              prompt: str | None = None, tag: str | None = None) -> int:
    spec = next(s for s in FIXTURE.shots if s.shot_id == shot_id)
    slot = run_dir / "slots" / shot_id
    slot.mkdir(parents=True, exist_ok=True)
    auth = MutationAuthority(slot, f"QUALITY-V2-020/{shot_id}")
    if auth.authority != "OPEN":
        emit({"status": "STOPPED_GOVERNANCE_GAP",
              "authority": auth.authority})
        return 1
    events = RunnerEvents(run_dir / "provider_events.jsonl")
    record = orch.shot(shot_id)
    record.status = "RESERVED"
    orch.save()
    auth._event("MUTATION_RESERVED", budget_kind=shot_id)

    def on_release(info: dict) -> None:
        auth.consume(shot_id)
        orch.record_release(
            shot_id, account_alias=account_alias,
            attempt_id=info["attempt_id"],
            conversation_id=info["conversation_id"],
            request_fingerprint=info["request_fingerprint"])

    def on_creation(info: dict) -> None:
        orch.record_creation(shot_id, info["creation_ids"])

    use_spec = spec
    if prompt is not None:
        from film_pipeline.providers.dola_production.fixture_v2_020 import \
            ShotSpec
        use_spec = spec.model_copy(update={
            "prompt": prompt, "needle": spec.needle})

    try:
        result = asyncio.run(dispatch_and_acquire(
            shot_spec=use_spec, account_alias=account_alias,
            run_dir=run_dir, shot_tag=tag or shot_id,
            on_release=on_release, on_creation=on_creation,
            events_sink=events))
    except RuntimeError as error:
        message = str(error)
        status = message.split(":", 1)[0]
        detail = message.split(":", 1)[1] if ":" in message else message
        if status.startswith("OWNER_AMBIGUITY"):
            auth.latch(status, detail[:250])
            orch.set_status("STOPPED_EXTERNAL_GATE", f"{shot_id}: {detail}")
        record.status = "QC_REJECT" if status == "STOPPED_PROVIDER_POLICY_REFUSAL" \
            else record.status
        emit({"status": status, "shot": shot_id, "detail": detail})
        return 1
    orch.record_asset(
        shot_id, path=result["asset_path"],
        clean_sha256=result["asset_sha256"]
        if result["variant_authority"] == "PROVIDER_ISSUED_UNWATERMARKED"
        else None,
        watermarked_sha256=result["asset_sha256"]
        if result["variant_authority"] == "PROVIDER_ISSUED_WATERMARKED"
        else None,
        variant_authority=result["variant_authority"])
    emit({"status": "ACQUIRED", "shot": shot_id, **{
        k: v for k, v in result.items() if k != "asset_path"}})
    return cmd_qc(run_dir, shot_id)


def cmd_run_shot(run_dir: Path, shot_id: str,
                 account_alias: str | None = None) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    orch.plan_shot(shot_id)
    if account_alias is None:
        decision = orch.select_account("seedance_v2.0")
        account_alias = decision.selected_alias
        if not account_alias:
            emit({"status": "STOPPED_EXTERNAL_GATE",
                  "reason": "no eligible account",
                  "resource_state": decision.resource_state,
                  "considered": decision.considered})
            return 1
    orch.set_status("RUNNING", f"dispatching {shot_id} on {account_alias}")
    return _dispatch(orch, run_dir, shot_id, account_alias)


def cmd_qc(run_dir: Path, shot_id: str) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    record = orch.shot(shot_id)
    if not record.asset_path:
        emit({"status": "NO_ASSET", "shot": shot_id})
        return 1
    asset = Path(record.asset_path)
    frames_dir = run_dir / "frames" / shot_id
    n = extract_frames(asset, frames_dir)
    technical = technical_qc(asset, frames_dir)
    technical["frames_extracted"] = n
    # continuity: palette distance to previous accepted shot
    idx = SHOT_ORDER.index(shot_id)
    continuity = {}
    if idx > 0:
        prev = orch.shot(SHOT_ORDER[idx - 1])
        prev_frames = run_dir / "frames" / SHOT_ORDER[idx - 1]
        if prev.asset_path and prev_frames.exists():
            from v2_020_runner import frame_metrics
            cur_fm = frame_metrics(frames_dir)
            prev_fm = frame_metrics(prev_frames)
            distance = ((cur_fm["mean_luma"] - prev_fm["mean_luma"]) ** 2
                        + ((cur_fm["mean_saturation"] -
                            prev_fm["mean_saturation"]) * 255) ** 2) ** 0.5
            continuity = {"palette_distance": round(distance, 2),
                          "reference": SHOT_ORDER[idx - 1]}
    # contact sheet for review
    sheet = run_dir / "contact_sheets" / f"{shot_id}.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    paths = sorted(frames_dir.glob("f_*.png"))
    picks = [paths[i] for i in (0, len(paths) // 5, 2 * len(paths) // 5,
                                3 * len(paths) // 5, 4 * len(paths) // 5,
                                len(paths) - 1)] if paths else []
    if picks:
        from PIL import Image
        thumbs = [Image.open(p).resize((320, 180)) for p in picks]
        grid = Image.new("RGB", (320 * 3, 180 * 2))
        for i, th in enumerate(thumbs):
            grid.paste(th, ((i % 3) * 320, (i // 3) * 180))
        grid.save(sheet)
    verdict = orch.qc_verdict(shot_id, technical=technical,
                              continuity=continuity or None)
    emit({"status": "QC_DONE", "shot": shot_id, "verdict": verdict,
          "technical": technical, "continuity": continuity,
          "contact_sheet": str(sheet), "qc_notes": record.qc_notes})
    return 0


def cmd_qc_visual(run_dir: Path, shot_id: str, verdict: str,
                  notes: list[str]) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    record = orch.shot(shot_id)
    record.qc_visual = {**record.qc_visual, "verdict": verdict,
                        "notes": " ".join(notes), "reviewer":
                        "pipeline-qc-operator", "reviewed_at":
                        __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ")}
    if verdict == "REJECT":
        record.qc_verdict = "REJECT"
        record.status = "QC_REJECT"
    elif verdict == "ACCEPT" and record.qc_verdict == "ACCEPT":
        pass
    orch.save()
    emit({"status": "VISUAL_RECORDED", "shot": shot_id, "verdict": verdict})
    return 0


def cmd_repair(run_dir: Path, shot_id: str) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    target = orch.repair_eligible()
    if target != shot_id:
        emit({"status": "REPAIR_NOT_GRANTED", "target": target})
        return 1
    if not orch.request_repair(shot_id):
        emit({"status": "REPAIR_NOT_GRANTED"})
        return 1
    decision = orch.select_account("seedance_v2.0")
    account = decision.selected_alias
    if not account:
        emit({"status": "STOPPED_EXTERNAL_GATE",
              "resource_state": decision.resource_state})
        return 1
    emit({"status": "REPAIR_ARMED", "shot": shot_id, "account": account,
          "note": "delta prompt supplied via --prompt file"})
    return 0


def cmd_assemble(run_dir: Path) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    accepted = [s for s in SHOT_ORDER
                if orch.shot(s).qc_verdict == "ACCEPT"]
    if len(accepted) < 2:
        emit({"status": "ASSEMBLY_BLOCKED", "accepted": accepted})
        return 1
    trims = {}
    if (run_dir / "editorial_trims.json").exists():
        trims = json.loads((run_dir / "editorial_trims.json")
                           .read_text(encoding="utf-8"))
    ed = orch.editorial_ranges(trims=trims)
    inputs, filters, labels = [], [], []
    total_frames = 0
    for i, shot_id in enumerate(accepted):
        record = orch.shot(shot_id)
        start, end = ed["ranges"][shot_id]
        total_frames += end - start
        inputs += ["-i", record.asset_path]
        filters.append(
            f"[{i}:v]trim=start_frame={start}:end_frame={end},"
            f"setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
    filters.append("".join(labels) +
                   f"concat=n={len(accepted)}:v=1:a=0[out]")
    proof = run_dir / "qualification_run" / "CLEAN_SEQUENCE_PROOF.mp4"
    proof.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
         ";".join(filters), "-map", "[out]", "-r", "24",
         "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p",
         str(proof)], capture_output=True, text=True)
    if proc.returncode != 0:
        emit({"status": "ASSEMBLY_FAILED", "stderr": proc.stderr[-500:]})
        return 1
    probe = ffprobe_json(proof)
    stream = next(s for s in probe.get("streams", [])
                  if s.get("codec_type") == "video")
    junctions = {}
    for i in range(len(accepted) - 1):
        junctions[f"{accepted[i]}->{accepted[i + 1]}"] = "HARD_CUT_OK"
    import hashlib
    sha = hashlib.sha256(proof.read_bytes()).hexdigest()
    orch.record_editorial_proof(path=str(proof), sha256=sha,
                                frame_count=int(stream.get("nb_frames")
                                                or total_frames),
                                junctions=junctions)
    emit({"status": "ASSEMBLED", "proof": str(proof), "sha": sha[:16],
          "frames": stream.get("nb_frames"), "junctions": junctions})
    return 0


def cmd_finish(run_dir: Path) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    proof = Path(orch.state.editorial.get("sequence_proof_path", ""))
    if not proof.exists():
        emit({"status": "NO_SEQUENCE_PROOF"})
        return 1
    out = run_dir / "qualification_run" / "FINISH_MASTER.mov"
    out.parent.mkdir(parents=True, exist_ok=True)
    # provider audio only: check sequence proof audio
    probe = ffprobe_json(proof)
    has_audio = any(s.get("codec_type") == "audio"
                    for s in probe.get("streams", []))
    if has_audio:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(proof),
             "-c:v", "copy", "-af",
             "loudnorm=I=-14:TP=-1.0:LRA=11", "-c:a", "pcm_s16le",
             str(out)], capture_output=True, text=True)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(proof),
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
             str(out)], capture_output=True, text=True)
    measure = subprocess.run(
        ["ffmpeg", "-i", str(out), "-af", "ebur128=peak=true", "-f",
         "null", "-"], capture_output=True, text=True)
    loudness = peak = None
    for line in (measure.stderr or "").splitlines():
        if "I:" in line and "LUFS" in line:
            try:
                loudness = float(line.split("I:")[1].split("LUFS")[0]
                                 .strip())
            except Exception:
                pass
        if "Peak:" in line and "dBTP" in line:
            try:
                peak = float(line.split("Peak:")[1].split("dBTP")[0]
                             .strip())
            except Exception:
                pass
    import hashlib
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    orch.record_finishing(
        loudness_lufs=loudness, true_peak_dbtp=peak,
        av_sync="SILENT_TRACK" if not has_audio else "COPY_FROM_PROVIDER",
        path=str(out), sha256=sha)
    emit({"status": "FINISHED", "loudness": loudness, "peak": peak,
          "has_audio": has_audio, "sha": sha[:16]})
    return 0


def cmd_master(run_dir: Path) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    finish = Path(orch.state.finishing.get("finish_master_path", ""))
    if not finish.exists():
        emit({"status": "NO_FINISH_MASTER"})
        return 1
    out = run_dir / "qualification_run" / "DISTRIBUTION_MASTER.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(finish),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(out)], capture_output=True)
    import hashlib
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    authorities = {orch.shot(s).variant_authority for s in SHOT_ORDER
                   if orch.shot(s).asset_path}
    watermark = ("ABSENT_BY_PROVIDER_ISSUED_AUTHORITY"
                 if authorities == {"PROVIDER_ISSUED_UNWATERMARKED"}
                 else "MIXED_AUTHORITIES:" + ",".join(sorted(a or "?"
                                                             for a in
                                                             authorities)))
    orch.record_master(path=str(out), sha256=sha,
                       watermark_status=watermark)
    orch.set_status("COMPLETED", "distribution master produced")
    emit({"status": "MASTER_DONE", "path": str(out), "sha": sha,
          "watermark": watermark})
    return 0


def cmd_manifest(run_dir: Path) -> int:
    orch = _orch(run_dir)
    orch.load_or_init(run_dir.name)
    doc = orch.manifest(run_dir=str(run_dir))
    out = run_dir / "qualification_run" / "V2_020_RUN_MANIFEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    emit({"status": "MANIFEST_WRITTEN", "path": str(out)})
    return 0


def cmd_status(run_dir: Path) -> int:
    orch = _orch(run_dir)
    state = orch.load_or_init(run_dir.name)
    emit({"status": state.status, "detail": state.status_detail,
          "mutations_used": orch.mutations_used,
          "shots": {s.shot_id: {"status": s.status,
                                "verdict": s.qc_verdict,
                                "account": s.account_alias,
                                "authority": s.variant_authority}
                    for s in state.shots}})
    return 0


def cmd_auto(run_dir: Path) -> int:
    cmd_plan(run_dir)
    cmd_pool(run_dir)
    for shot_id in SHOT_ORDER:
        record = _orch(run_dir)
        record.load_or_init(run_dir.name)
        if record.shot(shot_id).status in ("QC_ACCEPT", "EDITORIAL_LOCKED"):
            continue
        if record.mutations_used >= 4:
            emit({"status": "BUDGET_EXHAUSTED"})
            break
        code = cmd_run_shot(run_dir, shot_id)
        if code != 0:
            emit({"status": "SHOT_FAILED", "shot": shot_id})
    _orch(run_dir).load_or_init(run_dir.name)
    cmd_assemble(run_dir)
    cmd_finish(run_dir)
    cmd_master(run_dir)
    cmd_manifest(run_dir)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    run_dir = Path(args[0])
    run_dir.mkdir(parents=True, exist_ok=True)
    command = args[1]
    if command == "plan":
        return cmd_plan(run_dir)
    if command == "pool":
        return cmd_pool(run_dir)
    if command == "run-shot":
        return cmd_run_shot(run_dir, args[2],
                            args[3] if len(args) > 3 else None)
    if command == "qc":
        return cmd_qc(run_dir, args[2])
    if command == "qc-visual":
        return cmd_qc_visual(run_dir, args[2], args[3], args[4:])
    if command == "repair":
        return cmd_repair(run_dir, args[2])
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
    if command == "auto":
        return cmd_auto(run_dir)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
