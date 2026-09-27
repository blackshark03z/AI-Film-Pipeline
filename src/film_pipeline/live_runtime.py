"""Durable execution records for the single-submit provider boundary.

This module contains no Flow/browser implementation.  It gives adapters a
small transport contract while making the external-effect reservation durable
before any submit call can happen.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import Field

from .core import ContractModel, GenerationAttempt, PromptPlan, RoutingDecision, ShotSpec, sha256
from .store import SQLiteStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProviderJob(ContractModel):
    provider_job_id: str
    generation_attempt_id: str
    provider_id: str
    project_binding_id: str
    submission_state: Literal["NOT_SUBMITTED", "SUBMISSION_RESERVED", "SUBMITTED"] = "NOT_SUBMITTED"
    status: Literal["NOT_SUBMITTED", "SUBMITTED", "RUNNING", "SUCCEEDED", "FAILED", "INCONCLUSIVE"] = "NOT_SUBMITTED"
    dispatch_count: Literal[0, 1] = 0
    submitted_at: str | None = None
    external_job_id: str | None = None
    pre_dispatch_snapshot: dict[str, Any] = Field(default_factory=dict)
    correlation_evidence: dict[str, Any] = Field(default_factory=dict)
    last_checked_at: str | None = None
    dispatch_protocol: str = 'legacy-v1'


class Asset(ContractModel):
    asset_id: str
    asset_type: str = "video"
    origin: Literal["source", "reference", "generated", "derived", "editorial"] = "generated"
    uri_or_path: str
    sha256: str
    mime_type: str | None = None
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    file_size: int
    source_attempt_id: str
    provider_job_id: str
    provider_asset_id: str | None = None
    rights_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderTransport(Protocol):
    async def snapshot(self) -> dict[str, Any]: ...
    async def submit(self, job: ProviderJob, prompt: str) -> dict[str, Any]: ...
    async def poll(self, job: ProviderJob) -> dict[str, Any]: ...
    async def fetch(self, job: ProviderJob, output_id: str, destination: Path) -> Path: ...


def make_provider_job(
    attempt: GenerationAttempt,
    *,
    project_binding_id: str,
    pre_dispatch_snapshot: dict[str, Any],
) -> ProviderJob:
    """Create an intent record whose identity is independent of wall-clock time."""
    basis = {
        "generation_attempt_id": attempt.generation_attempt_id,
        "provider_id": attempt.provider_id,
        "project_binding_id": project_binding_id,
        "pre_dispatch_snapshot": pre_dispatch_snapshot,
    }
    return ProviderJob(
        provider_job_id=f"job_{sha256(basis)}",
        generation_attempt_id=attempt.generation_attempt_id,
        provider_id=attempt.provider_id,
        project_binding_id=project_binding_id,
        pre_dispatch_snapshot=pre_dispatch_snapshot,
        dispatch_protocol='flow-dispatch-evidence-v1',
    )


def _safe_submit_result(result: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Only structured, non-secret IDs/evidence may cross this boundary."""
    external = result.get("external_job_id")
    evidence = result.get("correlation_evidence", {})
    if external is not None and not isinstance(external, str):
        raise ValueError("external_job_id must be a string")
    if not isinstance(evidence, dict):
        raise ValueError("correlation evidence must be an object")
    # URLs frequently carry tokens.  Transport adapters must use stable ids.
    encoded = json.dumps(evidence, sort_keys=True)
    if "token=" in encoded.lower() or "authorization" in encoded.lower() or "cookie" in encoded.lower():
        raise ValueError("secret-bearing correlation evidence is forbidden")
    return external, evidence


class LiveRuntimeExecutor:
    def __init__(self, store: SQLiteStore, transport: ProviderTransport):
        self.store = store
        self.transport = transport

    def freeze_path(self, shot: ShotSpec, plan: PromptPlan, route: RoutingDecision, attempt: GenerationAttempt,
                    *, project_binding_id: str, pre_dispatch_snapshot: dict[str, Any]) -> ProviderJob:
        self.store.initialize()
        self.store.save_path(shot, plan, route, attempt)
        job = make_provider_job(attempt, project_binding_id=project_binding_id,
                                pre_dispatch_snapshot=pre_dispatch_snapshot)
        # A compiled provider prompt is safe execution evidence and gives the
        # adapter the exact immutable request payload it must submit.
        # Execution-unique marker is transport correlation, not creative intent.
        # It is persisted before submission and must be echoed by owned outputs.
        submission_prompt = plan.provider_prompt + "\nExecution correlation: " + job.provider_job_id
        job = job.model_copy(update={"correlation_evidence": {
            "prompt": submission_prompt, "prompt_plan_hash": sha256(plan),
            "submission_prompt_hash": sha256(submission_prompt),
            "correlation_marker": job.provider_job_id,
        }})
        self.store.save_provider_job(job)
        return job

    async def submit_once(self, provider_job_id: str) -> ProviderJob:
        # reservation is committed first.  Any failure after that point is an
        # external uncertainty, never authority to submit again.
        job = self.store.reserve_dispatch(provider_job_id)
        if job.submission_state != "SUBMISSION_RESERVED":
            raise RuntimeError("provider job is not dispatchable")
        from .dispatch_evidence import EvidenceSink
        if hasattr(self.transport, 'set_evidence_sink'):
            self.transport.set_evidence_sink(EvidenceSink(self.store, provider_job_id), job)
        try:
            result = await self.transport.submit(job, job.correlation_evidence["prompt"])
            external_id, evidence = _safe_submit_result(result)
        except Exception:
            uncertain = job.model_copy(update={"status": "INCONCLUSIVE", "last_checked_at": utc_now()})
            self.store.save_provider_job(uncertain)
            raise
        facts = self.store.read_dispatch_facts(provider_job_id)
        if any(f['kind'] == 'AMBIGUOUS_EVIDENCE' for f in facts):
            uncertain = job.model_copy(update={'status': 'INCONCLUSIVE', 'last_checked_at': utc_now()})
            self.store.save_provider_job(uncertain)
            return uncertain
        accepted = next((f for f in facts if f['kind'] == 'PROVIDER_ACCEPTANCE_OBSERVED'), None)
        submitted = job.model_copy(update={
            "submission_state": "SUBMITTED" if accepted else "SUBMISSION_RESERVED",
            "status": "SUBMITTED" if accepted else "INCONCLUSIVE",
            "submitted_at": accepted['at'] if accepted else None,
            "external_job_id": external_id,
            "correlation_evidence": {**job.correlation_evidence, **evidence}, "last_checked_at": utc_now(),
        })
        self.store.save_provider_job(submitted)
        return submitted

    async def reconcile(self, provider_job_id: str) -> ProviderJob:
        job = self.store.read_provider_job(provider_job_id)
        self.store._writable_job(provider_job_id)  # Legacy consumed history is never rewritten.
        if job.dispatch_count != 1:
            raise RuntimeError("cannot reconcile an unreserved job")
        from .dispatch_evidence import EvidenceSink
        if hasattr(self.transport, 'set_evidence_sink'):
            self.transport.set_evidence_sink(EvidenceSink(self.store, provider_job_id), job)
        facts = self.store.read_dispatch_facts(provider_job_id)
        # An observed exact attribution is durable even if the process died
        # before its immutable binding transaction.
        if any(f['kind'] == 'AMBIGUOUS_EVIDENCE' for f in facts):
            uncertain = job.model_copy(update={'status': 'INCONCLUSIVE', 'last_checked_at': utc_now()})
            self.store.save_provider_job(uncertain)
            return uncertain
        for fact in facts:
            if fact['kind'] == 'REMOTE_IDENTITY_OBSERVED':
                self.store.bind_output(provider_job_id, fact['data']['output_id'])
        try:
            bindings = self.store.read_output_bindings(provider_job_id)
            report = ({'status': 'SUCCEEDED', 'output_ids': [b['output_id'] for b in bindings]}
                      if bindings else await self.transport.poll(job))
            state = report.get("status")
            if state not in {"SUBMITTED", "RUNNING", "SUCCEEDED", "FAILED", "INCONCLUSIVE"}:
                state = "INCONCLUSIVE"
            external_id, evidence = _safe_submit_result({
                "external_job_id": report.get("external_job_id", job.external_job_id),
                "correlation_evidence": report.get("correlation_evidence", job.correlation_evidence),
            })
            if "output_ids" in report:
                output_ids = report["output_ids"]
                if not isinstance(output_ids, list) or not all(isinstance(item, str) for item in output_ids):
                    raise ValueError("output_ids must be strings")
                evidence = {**evidence, "output_ids": sorted(set(output_ids))}
            if state == 'SUCCEEDED':
                outputs = evidence.get('output_ids', [])
                if not outputs:
                    raise ValueError('SUCCEEDED_WITHOUT_EXACT_OUTPUT')
                for output in outputs:
                    if not any(f['kind'] == 'REMOTE_IDENTITY_OBSERVED' and f['data']['output_id'] == output for f in self.store.read_dispatch_facts(provider_job_id)):
                        self.store.record_dispatch_fact(provider_job_id, 'REMOTE_IDENTITY_OBSERVED',
                            {'output_id': output, 'method': 'transport_exact_output'})
                    self.store.bind_output(provider_job_id, output)
            acceptance = next((f for f in self.store.read_dispatch_facts(provider_job_id)
                               if f['kind'] == 'PROVIDER_ACCEPTANCE_OBSERVED'), None)
            updated = job.model_copy(update={"status": state, "external_job_id": external_id,
                "submission_state": 'SUBMITTED' if acceptance else job.submission_state,
                "submitted_at": acceptance['at'] if acceptance else job.submitted_at,
                "correlation_evidence": {**job.correlation_evidence, **evidence}, "last_checked_at": utc_now()})
        except Exception:
            updated = job.model_copy(update={"status": "INCONCLUSIVE", "last_checked_at": utc_now()})
        self.store.save_provider_job(updated)
        return updated

    async def download_assets(self, provider_job_id: str, destination_dir: Path) -> tuple[Asset, ...]:
        job = self.store.read_provider_job(provider_job_id)
        self.store._writable_job(provider_job_id)
        bindings = self.store.read_output_bindings(provider_job_id)
        if any(f['kind'] == 'AMBIGUOUS_EVIDENCE' for f in self.store.read_dispatch_facts(provider_job_id)):
            raise RuntimeError('AMBIGUOUS_EVIDENCE_REQUIRES_RECONCILIATION')
        output_ids = [b['output_id'] for b in bindings]
        if not isinstance(output_ids, list) or not output_ids or not all(isinstance(item, str) for item in output_ids):
            raise RuntimeError("no correlated provider outputs")
        destination_dir.mkdir(parents=True, exist_ok=True)
        from .dispatch_evidence import EvidenceSink
        if hasattr(self.transport, 'set_evidence_sink'):
            self.transport.set_evidence_sink(EvidenceSink(self.store, provider_job_id), job)
        assets: list[Asset] = []
        for output_id in sorted(output_ids):
            # Filename derives from the proven remote identity, never list order.
            destination = destination_dir.absolute() / f"{sha256(output_id)[:24]}.mp4"
            staging = destination.with_name(destination.stem + '.partial.mp4')
            for path in (destination, staging):
                if any(p.is_symlink() for p in (path, *path.parents)):
                    raise ValueError('ACQUISITION_SYMLINK_FORBIDDEN')
            binding = next(b for b in bindings if b['output_id'] == output_id)
            intent = {'binding_hash': binding['binding_hash'], 'final_path': str(destination),
                      'staging_path': str(staging), 'rendition': 'official-720p'}
            self.store.save_acquisition_record(provider_job_id, output_id, intent)
            receipt = self.store.read_acquisition_record(provider_job_id, output_id, completed=True)
            if receipt is None:
                if destination.exists():
                    raise ValueError('EXISTING_FILE_WITHOUT_ACQUISITION_RECEIPT')
                if staging.exists():
                    # Exact owned staging path from durable acquisition intent;
                    # partial bytes are discarded, never accepted as an Asset.
                    staging.unlink()
                downloaded = await self.transport.fetch(job, output_id, staging)
                if downloaded != staging:
                    raise ValueError("transport returned an unexpected output path")
                metadata = inspect_video(staging)
                digest = file_sha256(staging)
                receipt = {**intent, **metadata, 'sha256': digest, 'file_size': staging.stat().st_size}
                self.store.save_acquisition_record(provider_job_id, output_id, receipt, completed=True)
            if any(receipt.get(k) != v for k, v in intent.items()):
                raise ValueError('ACQUISITION_RECEIPT_INTENT_MISMATCH')
            source = destination if destination.exists() else staging
            metadata = inspect_video(source)
            digest = file_sha256(source)
            if (digest != receipt['sha256'] or source.stat().st_size != receipt['file_size']
                    or any(metadata[k] != receipt[k] for k in metadata)):
                raise ValueError('ACQUISITION_RECEIPT_BYTES_MISMATCH')
            if not destination.exists():
                os.link(staging, destination)  # Atomic no-overwrite promotion.
                staging.unlink()
            asset = Asset(
                asset_id=f"asset_{sha256({'job': job.provider_job_id, 'provider_asset_id': output_id, 'sha256': digest})}",
                uri_or_path=str(destination), sha256=digest, mime_type=metadata["mime_type"],
                duration_s=metadata["duration_s"], width=metadata["width"], height=metadata["height"],
                file_size=destination.stat().st_size, source_attempt_id=job.generation_attempt_id,
                provider_job_id=job.provider_job_id, provider_asset_id=output_id,
                rights_metadata={"identity_binding": binding, 'acquisition_receipt': receipt},
            )
            self.store.save_asset(asset)
            self.store.record_dispatch_fact(provider_job_id, 'ASSET_PERSISTED',
                {'output_id': output_id, 'asset_id': asset.asset_id})
            assets.append(asset)
        return tuple(assets)

    def recovery_decision(self, provider_job_id):
        from .dispatch_evidence import recovery_decision
        job = self.store.read_provider_job(provider_job_id)
        if job.dispatch_protocol == 'legacy-v1':
            return recovery_decision(job, [])
        facts = self.store.read_dispatch_facts(provider_job_id)
        bindings = self.store.read_output_bindings(provider_job_id)
        acquired = bool(bindings) and all(self.store.read_acquisition_record(provider_job_id, b['output_id'], completed=True) for b in bindings)
        return recovery_decision(job, facts, bound=bool(bindings), acquired=acquired)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_video(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("downloaded output is empty")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required for technical media validation")
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration,format_name:stream=codec_type,width,height",
         "-of", "json", str(path)],
        check=False, capture_output=True, text=True, timeout=30,
    )
    if completed.returncode:
        raise ValueError("ffprobe rejected downloaded output")
    try:
        payload = json.loads(completed.stdout)
        duration = float(payload["format"]["duration"])
        video = next(stream for stream in payload["streams"] if stream.get("codec_type") == "video")
        width, height = int(video["width"]), int(video["height"])
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("downloaded output is not a valid video") from exc
    if duration <= 0 or width <= 0 or height <= 0:
        raise ValueError("downloaded output has invalid video metadata")
    return {"mime_type": mimetypes.guess_type(path.name)[0] or "video/mp4", "duration_s": duration,
            "width": width, "height": height}
