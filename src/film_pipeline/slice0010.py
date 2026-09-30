"""Bounded two-shot entrypoint over existing per-shot lineage and live adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .canary import run_canary
from .autoedit_export import export_film_package
from .core import load_shot, sha256
from .editorial import EditClip, EditorialStore, make_edit_manifest
from .editorial_runner import real_rough_cut
from .live_runtime import Asset, LiveRuntimeExecutor, file_sha256
from .providers.flow_network import FlowNetworkTransport
from .providers.flow_veo import FlowConfig
from .providers.flow_veo import FlowVeoProvider
from .qc import (QCStore, HumanDecision, QCEvidence, SelectedTake,
                 human_decision, owner_approval_evidence)
from .qc_runner import run_qc
from .sequence import validate_shot_sequence
from .store import SQLiteStore


SHOT1_ATTEMPT = "attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5"
SHOT1_JOB = "job_62eab53994a2b8b1bde875b67f0068da97798a02f8aa75f8765d042edb07f0ea"
SHOT1_TAKE = "take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b"
SHOT1_ASSET = "asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01"
SHOT1_SHA256 = "c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf"
SHOT2_PATH = Path(__file__).resolve().parents[2] / "fixtures/flow_canary_shot2.json"
SHOT2_CRITERIA = {
    "visual": (
        ("insert_detail_framing", "Is this a locked detail view of the empty alley pavement?"),
        ("night_rain_alley", "Is the setting a rainy urban alley at night?"),
        ("empty_no_people", "Are people absent throughout the shot?"),
        ("wet_pavement_reflections", "Are wet pavement and reflected light visible?"),
    ),
    "continuity": (
        ("locked_detail_composition", "Is the detail camera effectively locked throughout?"),
        ("rain_night_consistency", "Do night and rain remain present throughout?"),
    ),
    "editorial": (
        ("insert_usefulness", "Does this detail shot offer a usable quiet rain and reflection insert?"),
    ),
}


def require_paired_continuity_evidence(rows: list[QCEvidence], predecessor: Asset) -> None:
    matches = [row for row in rows if row.gate == "continuity"
               and row.criterion == "paired_scene_continuity"
               and row.evaluator_type == "ffmpeg"]
    source = {"path": predecessor.uri_or_path, "sha256": predecessor.sha256}
    if (len(matches) != 1 or matches[0].verdict != "uncertain"
            or source not in matches[0].source_artifacts
            or len(matches[0].source_artifacts) < 4):
        raise ValueError("exact paired Shot 1 continuity evidence required")


def verify_predecessor(db_path: Path) -> dict:
    """Freshly resolve the approved first shot before a second-shot reservation."""
    runtime = SQLiteStore(db_path)
    shot, plan, route, attempt, job, assets = runtime.read_runtime_lineage(SHOT1_ATTEMPT, SHOT1_JOB)
    if (shot.shot_id != "FLOW_CANARY_001" or shot.scene_id != "FLOW_CANARY"
            or attempt.shot_id != shot.shot_id or job.status != "SUCCEEDED"
            or job.dispatch_count != 1 or len(assets) != 1
            or assets[0].asset_id != SHOT1_ASSET or assets[0].sha256 != SHOT1_SHA256
            or file_sha256(Path(assets[0].uri_or_path)) != SHOT1_SHA256):
        raise ValueError("Shot 1 exact lineage or media mismatch")
    clip = EditClip(order=1, shot_id=shot.shot_id, selected_take_id=SHOT1_TAKE,
                    asset_id=SHOT1_ASSET, target_duration_s=assets[0].duration_s)
    resolved = EditorialStore(runtime).resolve_manifest(make_edit_manifest("flow_canary", [clip]))
    if (len(resolved) != 1 or resolved[0].attempt_id != SHOT1_ATTEMPT
            or resolved[0].asset_sha256 != SHOT1_SHA256):
        raise ValueError("Shot 1 approved SelectedTake provenance mismatch")
    shot2 = load_shot(SHOT2_PATH)
    validate_shot_sequence((shot, shot2))
    return {"shot_id": shot.shot_id, "scene_id": shot.scene_id,
            "shot_spec_hash": sha256(shot), "prompt_plan_id": plan.prompt_plan_id,
            "routing_decision_id": route.routing_decision_id,
            "selected_take_id": SHOT1_TAKE, "asset_id": SHOT1_ASSET,
            "asset_sha256": SHOT1_SHA256, "shot2_spec_hash": sha256(shot2)}


async def run_second_shot(config: FlowConfig, *, db_path: Path, output_dir: Path,
                          authorize_new_submit: bool = False, poll_limit: int = 60,
                          poll_interval: float = 5) -> dict:
    predecessor = verify_predecessor(db_path)
    outcome = await run_canary(config, authorize_new_submit=authorize_new_submit,
        runtime_path=db_path, shot_path=SHOT2_PATH, output_dir=output_dir,
        poll_limit=poll_limit, poll_interval=poll_interval)
    return {"predecessor": predecessor, **outcome}


async def recover_second_shot(config: FlowConfig, *, db_path: Path,
                              output_dir: Path, poll_limit: int = 60,
                              poll_interval: float = 5) -> dict:
    """Read-only provider reconciliation and exact acquisition; no submit path."""
    predecessor = verify_predecessor(db_path)
    provider = FlowVeoProvider(config)
    health = await provider.preflight()
    if health.state != "READY":
        return {"result": "INCONCLUSIVE", "diagnostic": health.diagnostic_code,
                "dispatch_count": 0}
    store = SQLiteStore(db_path)
    connection = store._connect()
    try:
        rows = connection.execute("SELECT provider_jobs.id FROM provider_jobs "
            "JOIN generation_attempts ON generation_attempts.id=provider_jobs.generation_attempt_id "
            "WHERE json_extract(generation_attempts.payload,'$.shot_id')='FLOW_CANARY_002'").fetchall()
    finally:
        connection.close()
    if len(rows) != 1:
        raise ValueError("exactly one Shot 2 intent required for recovery")
    job = store.read_provider_job(rows[0][0])
    if job.dispatch_count != 1:
        raise ValueError("recovery requires one prior durable reservation")
    transport = FlowNetworkTransport(config)
    try:
        await transport.open()
        if job.project_binding_id != sha256(transport.project_id):
            raise ValueError("recovery project binding mismatch")
        executor = LiveRuntimeExecutor(store, transport)
        for _ in range(poll_limit):
            job = await executor.reconcile(job.provider_job_id)
            if job.status in {"SUCCEEDED", "FAILED", "INCONCLUSIVE"}:
                break
            await asyncio.sleep(poll_interval)
        if job.status != "SUCCEEDED":
            return {"result": "INCONCLUSIVE", "dispatch_count": 1,
                    "terminal_state": job.status, "provider_job_id": job.provider_job_id}
        assets = await executor.download_assets(job.provider_job_id, output_dir)
        shot, plan, route, attempt, read_job, read_assets = SQLiteStore(db_path).read_runtime_lineage(
            job.generation_attempt_id, job.provider_job_id)
        if (shot.shot_id != "FLOW_CANARY_002"
                or sha256(shot) != sha256(load_shot(SHOT2_PATH))
                or read_job != job
                or read_assets != assets or len(assets) != 1
                or file_sha256(Path(assets[0].uri_or_path)) != assets[0].sha256):
            raise ValueError("Shot 2 recovery lineage or bytes mismatch")
        return {"result": "PROVEN", "predecessor": predecessor,
                "generation_attempt_id": attempt.generation_attempt_id,
                "provider_job_id": job.provider_job_id, "dispatch_count": 1,
                "asset_id": assets[0].asset_id, "asset_sha256": assets[0].sha256,
                "prompt_plan_id": plan.prompt_plan_id,
                "routing_decision_id": route.routing_decision_id,
                "fresh_readback": True}
    finally:
        await transport.close()


def run_second_shot_qc(db_path: Path, output_dir: Path, *,
                       gemini_key_file: Path | None = None,
                       gemini_model: str | None = None) -> dict:
    verify_predecessor(db_path)
    store = SQLiteStore(db_path)
    connection = store._connect()
    try:
        rows = connection.execute("SELECT provider_jobs.id,generation_attempts.id "
            "FROM provider_jobs JOIN generation_attempts ON "
            "generation_attempts.id=provider_jobs.generation_attempt_id "
            "JOIN shot_specs ON shot_specs.hash=generation_attempts.shot_spec_hash "
            "WHERE json_extract(shot_specs.payload,'$.shot_id')='FLOW_CANARY_002'").fetchall()
    finally:
        connection.close()
    if len(rows) != 1:
        raise ValueError("exactly one Shot 2 ProviderJob required")
    job_id, attempt_id = rows[0]
    shot, _, _, _, job, assets = store.read_runtime_lineage(attempt_id, job_id)
    if (sha256(shot) != sha256(load_shot(SHOT2_PATH)) or job.dispatch_count != 1
            or job.status != "SUCCEEDED" or len(assets) != 1):
        raise ValueError("Shot 2 exact output lineage unavailable")
    _, _, _, _, _, predecessor_assets = store.read_runtime_lineage(SHOT1_ATTEMPT, SHOT1_JOB)
    result = run_qc(db_path, attempt_id, job_id, assets[0].asset_id,
        output_dir, gemini_key_file=gemini_key_file, gemini_model=gemini_model,
        criteria=SHOT2_CRITERIA, predecessor_asset=predecessor_assets[0])
    return {"shot_id": shot.shot_id, "generation_attempt_id": attempt_id,
            "provider_job_id": job_id, **result}


def require_approved_second_take(runtime: SQLiteStore, take_id: str,
                                 predecessor_shot, predecessor_asset: Asset) -> SelectedTake:
    """Read back the exact planned pair and Owner-reviewed QC before rendering."""
    connection = runtime._connect()
    try:
        row = connection.execute("SELECT asset_id,report_id,payload FROM selected_takes WHERE id=?",
                                 (take_id,)).fetchone()
        if row is None:
            raise ValueError("Shot 2 SelectedTake missing")
        take = SelectedTake.model_validate(json.loads(row[2]))
        asset_row = connection.execute("SELECT payload FROM assets WHERE id=?",
                                       (row[0],)).fetchone()
        if asset_row is None:
            raise ValueError("Shot 2 Asset missing")
        asset = Asset.model_validate(json.loads(asset_row[0]))
    finally:
        connection.close()
    if (take.selected_take_id != take_id or take.shot_id != "FLOW_CANARY_002"
            or take.asset_id != asset.asset_id or take.qc_report_id != row[1]
            or take.generation_attempt_id != asset.source_attempt_id):
        raise ValueError("Shot 2 SelectedTake lineage mismatch")
    shot, _, _, _, job, assets = runtime.read_runtime_lineage(
        asset.source_attempt_id, asset.provider_job_id)
    if (sha256(shot) != sha256(load_shot(SHOT2_PATH)) or job.status != "SUCCEEDED"
            or job.dispatch_count != 1 or asset not in assets
            or file_sha256(Path(asset.uri_or_path)) != asset.sha256):
        raise ValueError("Shot 2 planned Asset mismatch")
    validate_shot_sequence((predecessor_shot, shot))
    qc = QCStore(runtime)
    final, read_take = qc.read(asset, take.qc_report_id)
    if (read_take != take or final.report["decision"] != "pass"
            or final.prior_report_id is None or final.human_decision_id is None):
        raise ValueError("Shot 2 Owner approval lineage missing")
    pending, pending_disposition = qc.read(asset, final.prior_report_id)
    if (pending.report["decision"] != "needs_human_review"
            or pending_disposition is not None or pending.human_decision_id is not None
            or not pending.report["technical"]["pass"]):
        raise ValueError("Shot 2 pending paired review missing")
    connection = runtime._connect()
    try:
        evidence_rows = [QCEvidence.model_validate(json.loads(connection.execute(
            "SELECT payload FROM qc_evidence WHERE id=?", (key,)).fetchone()[0]))
                         for key in pending.evidence_ids]
        human_row = connection.execute("SELECT payload FROM human_qc_decisions WHERE id=?",
                                       (final.human_decision_id,)).fetchone()
    finally:
        connection.close()
    require_paired_continuity_evidence(evidence_rows, predecessor_asset)
    if human_row is None:
        raise ValueError("Shot 2 Owner decision missing")
    human = HumanDecision.model_validate(json.loads(human_row[0]))
    if (human.decision_id != final.human_decision_id or human.reviewer_id != "owner"
            or human.source != "owner_explicit_review" or human.action != "APPROVE"
            or take.reviewer_id != "owner"):
        raise ValueError("Shot 2 explicit Owner approval missing")
    return take


def assemble_approved_scene(db_path: Path, *, output_dir: Path,
                            package_dir: Path, media_root: Path) -> dict:
    """Produce the existing Film manifest, rough cut and export after Owner approval."""
    verify_predecessor(db_path)
    runtime = SQLiteStore(db_path)
    predecessor_shot, _, _, _, _, predecessor_assets = runtime.read_runtime_lineage(
        SHOT1_ATTEMPT, SHOT1_JOB)
    connection = runtime._connect()
    try:
        rows = connection.execute("SELECT id FROM selected_takes "
            "WHERE json_extract(payload,'$.shot_id')='FLOW_CANARY_002'").fetchall()
    finally:
        connection.close()
    if len(rows) != 1:
        raise ValueError("exactly one approved Shot 2 SelectedTake required")
    require_approved_second_take(runtime, rows[0][0], predecessor_shot,
                                 predecessor_assets[0])
    ordered = [SHOT1_TAKE, rows[0][0]]
    render = real_rough_cut(db_path, project_id="flow_canary",
        selected_take_ids=ordered, output_dir=output_dir)
    if render["clip_count"] != 2 or render["selected_take_ids"] != ordered:
        raise ValueError("two-shot render order mismatch")
    package = export_film_package(db_path, manifest_id=render["manifest_id"],
        media_root=media_root, destination=package_dir)
    if package["media_count"] != 2:
        raise ValueError("two real media entries required")
    return {"rough_cut": render, "autoedit_package": package}


def finalize_second_shot_approval(db_path: Path, *, pending_report_id: str,
                                  expected_asset_sha256: str) -> dict:
    """Append the Owner's explicit approval without altering Shot 1 history."""
    verify_predecessor(db_path)
    runtime = SQLiteStore(db_path)
    connection = runtime._connect()
    try:
        rows = connection.execute("SELECT payload FROM assets WHERE "
            "json_extract(payload,'$.sha256')=?", (expected_asset_sha256,)).fetchall()
    finally:
        connection.close()
    if len(rows) != 1:
        raise ValueError("exact Shot 2 Asset SHA-256 is not unique")
    asset = Asset.model_validate(json.loads(rows[0][0]))
    shot, _, _, _, job, assets = runtime.read_runtime_lineage(
        asset.source_attempt_id, asset.provider_job_id)
    if (shot.shot_id != "FLOW_CANARY_002" or job.status != "SUCCEEDED"
            or sha256(shot) != sha256(load_shot(SHOT2_PATH))
            or asset not in assets or file_sha256(Path(asset.uri_or_path)) != asset.sha256):
        raise ValueError("Shot 2 Asset lineage or bytes mismatch")
    prior_shot, _, _, _, _, prior_assets = runtime.read_runtime_lineage(SHOT1_ATTEMPT, SHOT1_JOB)
    validate_shot_sequence((prior_shot, shot))
    qc = QCStore(runtime)
    pending, disposition = qc.read(asset, pending_report_id)
    if (pending.report["decision"] != "needs_human_review" or disposition is not None
            or pending.human_decision_id is not None
            or not pending.report["technical"]["pass"]):
        raise ValueError("Shot 2 report is not eligible for Owner approval")
    connection = runtime._connect()
    try:
        evidence_rows = [QCEvidence.model_validate(json.loads(connection.execute(
            "SELECT payload FROM qc_evidence WHERE id=?", (key,)).fetchone()[0]))
                         for key in pending.evidence_ids]
    finally:
        connection.close()
    require_paired_continuity_evidence(evidence_rows, prior_assets[0])
    used_advisory = any(row.evaluator_type == "vlm" for row in evidence_rows)
    human = human_decision(asset=asset, reviewer_id="owner", action="APPROVE",
        visual_pass=True, continuity_pass=True, editorial_pass=True,
        notes=["Owner explicitly approved Shot 2 after the paired scene review."],
        vlm_assisted=used_advisory, source="owner_explicit_review")
    final, take = qc.save(asset, evidence_rows + owner_approval_evidence(asset),
                          human, prior_report_id=pending_report_id)
    readback, read_take = QCStore(SQLiteStore(db_path)).read(asset, final.report["qc_report_id"])
    if (readback != final or read_take != take or not isinstance(take, SelectedTake)
            or take.shot_id != "FLOW_CANARY_002" or take.asset_id != asset.asset_id):
        raise ValueError("Shot 2 approval fresh readback mismatch")
    connection = runtime._connect()
    try:
        shot1 = connection.execute("SELECT payload FROM selected_takes WHERE id=?",
                                   (SHOT1_TAKE,)).fetchone()
        shot2_count = connection.execute("SELECT COUNT(*) FROM selected_takes WHERE "
            "json_extract(payload,'$.shot_id')='FLOW_CANARY_002'").fetchone()[0]
    finally:
        connection.close()
    if shot1 is None or shot2_count != 1:
        raise ValueError("SelectedTake count or Shot 1 history changed")
    return {"human_decision_id": human.decision_id,
            "final_report_id": final.report["qc_report_id"],
            "selected_take_id": take.selected_take_id,
            "selection_authority": take.selection_authority,
            "fresh_readback": True}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="One bounded Flow Generate for FLOW_CANARY_002")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--authorize-one-generate", action="store_true")
    parser.add_argument("--poll-limit", type=int, default=60)
    parser.add_argument("--poll-interval", type=float, default=5)
    args = parser.parse_args()
    result = asyncio.run(run_second_shot(FlowConfig.from_environment(), db_path=args.db,
        output_dir=args.output_dir, authorize_new_submit=args.authorize_one_generate,
        poll_limit=args.poll_limit, poll_interval=args.poll_interval))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
