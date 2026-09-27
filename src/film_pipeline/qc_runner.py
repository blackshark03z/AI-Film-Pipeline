"""Read-only provider-side SLICE-0007 QC runner and human decision entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import quote

from .core import canonical_json
from .live_runtime import Asset, file_sha256
from .qc import QCStore, POLICY_VERSION, evidence, human_decision, technical_evidence
from .qc_media import (CONTINUITY_CRITERIA, EDITORIAL_CRITERIA, VISUAL_CRITERIA,
                       gemini_advisory, make_review_media)
from .store import SQLiteStore


def exact_lineage(db_path: Path, attempt_id: str, job_id: str, asset_id: str):
    store = SQLiteStore(db_path)
    shot, plan, route, attempt, job, assets = store.read_runtime_lineage(attempt_id, job_id)
    matching = [asset for asset in assets if asset.asset_id == asset_id]
    if len(matching) != 1 or job.status != "SUCCEEDED" or job.dispatch_count != 1:
        raise ValueError("exact proven Asset lineage unavailable")
    asset = matching[0]
    return store, shot, asset


def write_review_packet(output_dir: Path, shot, asset: Asset, record, media: dict,
                        vlm: dict, evidence_rows: list, elapsed_s: float) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = record.report
    def link(path: str) -> str:
        relative = os.path.relpath(Path(path).resolve(), output_dir.resolve()).replace("\\", "/")
        return quote(relative, safe="/:._-")
    lines = [
        "# SLICE-0007 human QC review packet", "",
        f"Asset: `{asset.asset_id}`", f"SHA-256: `{asset.sha256}`",
        f"Video: [open exact video]({link(asset.uri_or_path)})", "",
        "## Frozen shot intent", "",
        f"Shot: `{shot.shot_id}`; purpose: {shot.dramatic_purpose}",
        f"Target: {shot.duration_target_s}s, {shot.shot_type}, {shot.camera.framing}, "
        f"{shot.camera.height}, {shot.camera.lens_intent}, {shot.camera.movement.type} camera.",
        f"Environment: {shot.environment.time_of_day}, {shot.environment.weather}, "
        f"{shot.environment.atmosphere}.",
        f"Blocking: {shot.blocking.start}; {'; '.join(shot.blocking.action_beats)}; {shot.blocking.end}.",
        "Critical invariants: " + "; ".join(shot.continuity.critical_invariants), "",
        "## Evidence and gates", "",
        (f"Contact sheet: [five timestamped frames]({link(media['contact_sheet']['path'])})"
         if media["contact_sheet"] else "Contact sheet unavailable: technical media gate failed."), "",
    ]
    for frame in media["frames"]:
        lines.append(f"- {frame['time_s']}s: [frame]({link(frame['path'])}) · SHA-256 `{frame['sha256']}`")
    lines += ["", "Temporal signals are advisory: " + canonical_json(media["signals"]), ""]
    for gate in ("technical", "visual", "continuity", "editorial"):
        item = report[gate]
        state = ("PASS" if item["pass"] else
                 "PENDING HUMAN REVIEW" if any(code.endswith("_HUMAN_REVIEW_REQUIRED")
                                                for code in item["issues"]) else "FAIL")
        lines += [f"- **{gate}**: {state}; issues: {', '.join(item['issues']) or 'none'}"]
    lines += ["", f"VLM run: {canonical_json(vlm)}", ""]
    advisory = [e for e in evidence_rows if e.evaluator_type == "vlm"]
    if advisory:
        lines += ["### Advisory observations", ""]
        for item in sorted(advisory, key=lambda e: (e.gate, e.criterion)):
            lines.append(f"- **{item.gate}/{item.criterion}**: {item.verdict}; "
                         f"confidence {item.confidence}; {item.observation} "
                         f"(evidence `{item.evidence_id}`)")
    lines += ["",
              "## Owner decision", "",
              "Choose **APPROVE**, **REJECT**, or **NEEDS_REVIEW** after viewing the exact video and evidence.",
              "APPROVE requires all visual, continuity and editorial criteria to pass. "
              "REJECT requires a failed gate and structured failure code. Technical or critical continuity "
              "failure prevents SelectedTake. No repair generation is authorized here.", "",
              f"Current report: `{report['qc_report_id']}` · `{report['decision']}`", "",
              f"Measured local QC wall clock: {elapsed_s:.3f}s; human review minutes: unknown; total cost: unknown.",
              ""]
    path = output_dir / "REVIEW_PACKET.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_qc(db_path: Path, attempt_id: str, job_id: str, asset_id: str,
           output_dir: Path, *, gemini_key_file: Path | None = None,
           gemini_model: str | None = None) -> dict:
    started = time.perf_counter()
    store, shot, asset = exact_lineage(db_path, attempt_id, job_id, asset_id)
    technical, metadata = technical_evidence(shot, asset)
    technical_pass = bool(metadata) and all(e.verdict == "pass" for e in technical)
    if technical_pass:
        visual, media = make_review_media(asset, output_dir)
    else:
        visual = [evidence(asset=asset, evaluator_type="ffmpeg", evaluator_version=POLICY_VERSION,
                           gate=gate, criterion=criterion,
                           observation="Visual review withheld until technical source is valid",
                           verdict="uncertain")
                  for gate, criteria in (("visual", VISUAL_CRITERIA),
                                         ("continuity", CONTINUITY_CRITERIA),
                                         ("editorial", EDITORIAL_CRITERIA))
                  for criterion, _ in criteria]
        media = {"frames": [], "contact_sheet": None, "signals": {}}
    vlm = {"used": False, "reason": "no qualified configured model", "cost": "unknown"}
    if technical_pass and gemini_key_file and gemini_model:
        try:
            advisory, vlm = gemini_advisory(asset, media["frames"],
                                            key_file=gemini_key_file, model=gemini_model)
            visual.extend(advisory)
        except (OSError, ValueError, RuntimeError):
            vlm = {"used": False, "reason": "configured advisory unavailable or malformed",
                   "model": gemini_model, "cost": "unknown"}
    qc = QCStore(store)
    record, disposition = qc.save(asset, technical + visual)
    fresh, fresh_disposition = QCStore(SQLiteStore(db_path)).read(asset, record.report["qc_report_id"])
    if fresh != record or fresh_disposition != disposition:
        raise ValueError("fresh QC readback mismatch")
    elapsed = time.perf_counter() - started
    packet = write_review_packet(output_dir, shot, asset, record, media, vlm,
                                 technical + visual, elapsed)
    return {"report_id": record.report["qc_report_id"], "decision": record.report["decision"],
            "asset_id": asset.asset_id, "asset_sha256": asset.sha256,
            "duration_s": metadata.get("duration_s"), "width": metadata.get("width"),
            "height": metadata.get("height"), "gates": {g: record.report[g] for g in
                                               ("technical", "visual", "continuity", "editorial")},
            "evidence_count": len(technical + visual), "disposition":
            "REPAIR_DECISION" if isinstance(disposition, dict) else "NEEDS_HUMAN_REVIEW",
            "fresh_readback": True, "packet": str(packet), "packet_sha256": file_sha256(packet),
            "vlm": vlm, "qc_wall_clock_s": round(elapsed, 3)}


def decide(db_path: Path, attempt_id: str, job_id: str, asset_id: str,
           pending_report_id: str, reviewer_id: str, action: str,
           visual_pass: bool | None, continuity_pass: bool | None,
           editorial_pass: bool | None, failure_codes: list[str],
           failure_observations: dict[str, str], notes: list[str],
           vlm_assisted: bool = False):
    store, shot, asset = exact_lineage(db_path, attempt_id, job_id, asset_id)
    qc = QCStore(store)
    pending, _ = qc.read(asset, pending_report_id)
    c = store._connect()
    try:
        rows = [c.execute("SELECT payload FROM qc_evidence WHERE id=?", (key,)).fetchone()
                for key in pending.evidence_ids]
    finally:
        c.close()
    if any(row is None for row in rows):
        raise ValueError("pending report evidence missing")
    from .qc import QCEvidence
    evidence_rows = [QCEvidence.model_validate(json.loads(row[0])) for row in rows]
    human = human_decision(asset=asset, reviewer_id=reviewer_id, action=action,
                           visual_pass=visual_pass, continuity_pass=continuity_pass,
                           editorial_pass=editorial_pass, failure_codes=failure_codes,
                           failure_observations=failure_observations,
                           notes=notes, vlm_assisted=vlm_assisted)
    record, disposition = qc.save(asset, evidence_rows, human)
    fresh, fresh_disposition = QCStore(SQLiteStore(db_path)).read(asset, record.report["qc_report_id"])
    if fresh != record or fresh_disposition != disposition:
        raise ValueError("fresh human QC readback mismatch")
    return {"report_id": record.report["qc_report_id"], "decision": record.report["decision"],
            "disposition": disposition.model_dump(mode="json") if hasattr(disposition, "model_dump") else disposition,
            "fresh_readback": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact Asset QC; no provider Generate path")
    parser.add_argument("action", choices=["run", "decide"])
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--gemini-key-file", type=Path)
    parser.add_argument("--gemini-model")
    parser.add_argument("--pending-report-id")
    parser.add_argument("--reviewer-id")
    parser.add_argument("--human-action", choices=["APPROVE", "REJECT", "NEEDS_REVIEW"])
    for gate in ("visual", "continuity", "editorial"):
        parser.add_argument(f"--{gate}-pass", choices=["yes", "no", "unknown"])
    parser.add_argument("--failure-code", action="append", default=[])
    parser.add_argument("--failure-observation", action="append", default=[],
                        help="CODE=concrete observation, one per rejected failure code")
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--vlm-assisted", action="store_true",
                        help="Reviewer explicitly used VLM observations in the decision")
    args = parser.parse_args()
    if args.action == "run":
        if not args.output_dir:
            parser.error("run requires --output-dir")
        result = run_qc(args.db, args.attempt_id, args.job_id, args.asset_id,
                        args.output_dir, gemini_key_file=args.gemini_key_file,
                        gemini_model=args.gemini_model)
    else:
        if not args.pending_report_id or not args.reviewer_id or not args.human_action:
            parser.error("decide requires report, reviewer, and human action")
        value = lambda name: {"yes": True, "no": False, "unknown": None, None: None}[
            getattr(args, name + "_pass")]
        observations = {}
        for item in args.failure_observation:
            if "=" not in item:
                parser.error("failure observation must be CODE=observation")
            code, observation = item.split("=", 1)
            observations[code] = observation
        result = decide(args.db, args.attempt_id, args.job_id, args.asset_id,
                        args.pending_report_id, args.reviewer_id, args.human_action,
                        value("visual"), value("continuity"), value("editorial"),
                        args.failure_code, observations, args.note, args.vlm_assisted)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
