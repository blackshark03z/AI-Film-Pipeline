"""Bounded reference-grounded character-continuity production entrypoint."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid
import asyncio
import json
from pathlib import Path

from .compiler import compile_prompt
from .core import ProviderCapabilities, load_shot, sha256
from .execution import route
from .live_runtime import (Asset, GenerationAttempt, LiveRuntimeExecutor,
                           file_sha256, inspect_video, make_provider_job, utc_now)
from .providers import flow_rpc_contract as rpc_contract
from .providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from .providers.flow_r2v_prompt import compile_flow_r2v_prompt, VERSION as R2V_PROMPT_VERSION
from .sequence import validate_shot_sequence
from .store import SQLiteStore


ROOT = Path(__file__).resolve().parents[2]
SHOT_A_PATH = ROOT / "fixtures/character_continuity_shot_a.json"
SHOT_B_PATH = ROOT / "fixtures/character_continuity_shot_b.json"
REFERENCE_SOURCE = Path(
    "D:/Story Auto/evidence/goal54/fixtures/r1_character.png")
REFERENCE_SCRIPT = (
    "D:/Story Auto/story-auto/tools/goal54_make_reference_fixture.py")
REFERENCE_SHA256 = "31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531"
REFERENCE_ASSET_ID = "asset_" + sha256({"origin": "reference", "asset_type": "image",
                                         "sha256": REFERENCE_SHA256})
CHARACTER_ID = "CHAR_CONTINUITY_001"
IDENTITY_VERSION = "ID_V1"
LOOK_STATE_ID = "LOOK_V1"
PROJECT_ID = "f6b40e79-d6f8-4354-80ae-c863260e96f5"
# Project access is observed. The human-readable Google account is only
# Owner-attested; the private catalog does not expose verified account identity.
ACCOUNT_ID = "project_scoped_unverified_account"
RPC_CONTRACT = "flow_rpc_r2v_20260920_1"


def validate_character_pair(reference_asset_id: str = REFERENCE_ASSET_ID):
    """Require one exact character and reference in both ordered ShotSpecs."""
    first, second = load_shot(SHOT_A_PATH), load_shot(SHOT_B_PATH)
    validate_shot_sequence((first, second))
    for shot in (first, second):
        if (len(shot.characters) != 1
                or (shot.characters[0].character_id,
                    shot.characters[0].identity_version,
                    shot.characters[0].look_state_id)
                != (CHARACTER_ID, IDENTITY_VERSION, LOOK_STATE_ID)
                or shot.references is None
                or shot.references.character_asset_ids != [reference_asset_id]
                or any((shot.references.location_asset_ids,
                        shot.references.wardrobe_asset_ids,
                        shot.references.other_asset_ids))
                or shot.duration_target_s != 8):
            raise ValueError("exact character/reference/8-second pair required")
    if first.shot_id == second.shot_id or first.scene_id != second.scene_id:
        raise ValueError("two distinct shots in one scene required")
    return first, second


def freeze_reference(db_path: Path, destination_dir: Path, *,
                     source_path: Path = REFERENCE_SOURCE) -> Asset:
    """Copy a programmatically drawn fixture once into local immutable Asset storage."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(db_path)
    store.initialize()
    destination = destination_dir.resolve() / f"{REFERENCE_SHA256}.png"
    if not destination.is_file():
        if not source_path.is_file() or file_sha256(source_path) != REFERENCE_SHA256:
            raise ValueError("qualified synthetic reference source unavailable")
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".reference-", suffix=".png",
                                              dir=destination.parent)
        os.close(handle)
        staging = Path(temporary)
        try:
            shutil.copyfile(source_path, staging)
            if file_sha256(staging) != REFERENCE_SHA256:
                raise ValueError("reference copy SHA mismatch")
            if destination.exists():
                raise ValueError("reference destination changed during import")
            os.rename(staging, destination)
        finally:
            staging.unlink(missing_ok=True)
    if file_sha256(destination) != REFERENCE_SHA256:
        raise ValueError("reference destination SHA mismatch")
    asset = Asset(asset_id=REFERENCE_ASSET_ID, asset_type="image", origin="reference",
        uri_or_path=str(destination), sha256=REFERENCE_SHA256, mime_type="image/png",
        width=1280, height=720, file_size=destination.stat().st_size,
        rights_metadata={"source_kind": "deterministic_synthetic_fixture",
            "source_sha256": REFERENCE_SHA256,
            "source_script": REFERENCE_SCRIPT,
            "personal_data": "none; fictional illustrated character"})
    store.save_reference_asset(asset)
    if SQLiteStore(db_path).read_reference_asset(REFERENCE_ASSET_ID) != asset:
        raise ValueError("reference Asset fresh readback mismatch")
    return asset


def reference_capabilities() -> ProviderCapabilities:
    """A separate, bounded profile; existing T2V capability remains unchanged."""
    return ProviderCapabilities(
        profile_version="flow-rpc-reference-video-2026-09-20.1",
        provider_id="flow_veo", transport_type="browser_cookie",
        supports_text_to_video=True, supports_image_input=True,
        notes=["Private observed Flow batchexecute transport, not a public API.",
               "Single PNG reference, abra_r2v_8s, 8 seconds, 16:9, one output.",
               "No start/end-frame or multi-reference capability claimed."])


def compile_character_paths(db_path: Path):
    """Freshly bind both plans and routes to the same exact reference bytes."""
    reference = SQLiteStore(db_path).read_reference_asset(REFERENCE_ASSET_ID)
    if reference.sha256 != REFERENCE_SHA256:
        raise ValueError("reference Asset SHA changed")
    shots = validate_character_pair(reference.asset_id)
    profile = reference_capabilities()
    paths = []
    for shot in shots:
        plan = compile_prompt(shot, profile,
                              reference_hashes={reference.asset_id: reference.sha256})
        if (plan.mapped_controls.get("image_input") != [
                {"asset_id": reference.asset_id, "sha256": reference.sha256}]
                or "image_input" in plan.unsupported_controls
                or "image_input" in plan.mapped_controls.get("text_fallbacks", {})):
            raise ValueError("real image_input mapping required")
        decision = route(shot, [plan], [profile], {profile.provider_id: True},
                         required_controls={"image_input"})
        if decision.provider_id != "flow_veo":
            raise ValueError("Flow reference route required")
        paths.append((shot, plan, decision))
    return reference, profile, tuple(paths)


def upload_reference_once(db_path: Path, session, reference: Asset,
                          *, project_id: str = PROJECT_ID,
                          account_id: str = ACCOUNT_ID) -> dict:
    """One durable reservation, one upload, one verified provider media ID."""
    if project_id != PROJECT_ID or account_id != ACCOUNT_ID:
        raise ValueError("SLICE-0011 upload authority is project scoped and fixed")
    if session.project_id != project_id:
        raise ValueError("session project differs from upload project")
    frozen = SQLiteStore(db_path).read_reference_asset(REFERENCE_ASSET_ID)
    if (reference != frozen or reference.asset_id != REFERENCE_ASSET_ID
            or reference.sha256 != REFERENCE_SHA256):
        raise ValueError("only the frozen SLICE-0011 reference may be uploaded")
    uploads = ReferenceUploadStore(db_path)
    from .providers.flow_reference_upload import _key
    progress = uploads.read_progress(_key("flow_veo", project_id, account_id, reference))
    if progress is None or progress['effective_state'] != 'REMOTE_RESOURCE_VERIFIED':
        raise OwnerAmbiguityGate('forensic reference recovery required; no production upload authorized')
    return uploads.read_verified('flow_veo', project_id, account_id, reference)


def _existing_job_for_shot(store: SQLiteStore, shot_id: str):
    """A restart resumes the same job; it cannot create another attempt."""
    with sqlite3.connect(store.path) as connection:
        ids = [row[0] for row in connection.execute(
            "SELECT id FROM generation_attempts WHERE "
            "json_extract(payload,'$.shot_id')=?", (shot_id,)).fetchall()]
        if not ids:
            return None
        if len(ids) != 1:
            raise OwnerAmbiguityGate("multiple local attempts for one shot")
        jobs = [row[0] for row in connection.execute(
            "SELECT id FROM provider_jobs WHERE generation_attempt_id=?", (ids[0],)).fetchall()]
    if len(jobs) != 1:
        raise OwnerAmbiguityGate("existing shot has incomplete provider job lineage")
    return store.read_provider_job(jobs[0])


def _require_acquired_shot_a(store: SQLiteStore) -> None:
    first = _existing_job_for_shot(store, "CHAR_CONTINUITY_A")
    if first is None or first.status != "SUCCEEDED" or first.dispatch_count != 1:
        raise ValueError("Shot A must be acquired before Shot B")
    shot, _, _, _, job, assets = store.read_runtime_lineage(
        first.generation_attempt_id, first.provider_job_id)
    if (shot.shot_id != "CHAR_CONTINUITY_A" or job != first or len(assets) != 1
            or file_sha256(Path(assets[0].uri_or_path)) != assets[0].sha256):
        raise ValueError("Shot A exact acquired Asset required before Shot B")


def freeze_shot_job(db_path: Path, session, path: tuple,
                    reference_receipt: dict):
    """Freeze prompt, single image binding and baseline before the only submit."""
    shot, plan, decision = path
    if path not in compile_character_paths(db_path)[2]:
        raise ValueError("only the two frozen SLICE-0011 shot paths are authorized")
    store = SQLiteStore(db_path)
    if shot.shot_id == "CHAR_CONTINUITY_B":
        _require_acquired_shot_a(store)
    reference = store.read_reference_asset(REFERENCE_ASSET_ID)
    if (reference.sha256 != reference_receipt["reference_sha256"]
            or reference.asset_id != reference_receipt["asset_id"]
            or reference_receipt["project_id"] != session.project_id
            or reference_receipt["account_id"] != ACCOUNT_ID
            or plan.mapped_controls.get("image_input") != [
                {"asset_id": reference.asset_id, "sha256": reference.sha256}]):
        raise ValueError("reference binding does not match frozen shot")
    prior = _existing_job_for_shot(store, shot.shot_id)
    if prior is not None:
        old_shot, old_plan, old_route, _ = store.read_path(prior.generation_attempt_id)
        if ((old_shot, old_plan, old_route) != (shot, plan, decision)
                or prior.correlation_evidence.get("reference_binding") !=
                _reference_binding(reference_receipt)
                or prior.project_binding_id != sha256(session.project_id)):
            raise OwnerAmbiguityGate("restart path differs from frozen provider intent")
        return prior
    records = session.catalog()
    if session.catalog_fingerprint != rpc_contract.QUALIFIED_BASELINE_FINGERPRINT:
        raise ValueError("FLOW_REFERENCE_RPC_DRIFT")
    snapshot = {"catalog_ids": sorted(row[0].lower() for row in records),
                "catalog_fingerprint": session.catalog_fingerprint,
                "project_id": session.project_id}
    started = utc_now()
    basis = {"shot_spec_hash": sha256(shot), "prompt_plan_hash": sha256(plan),
             "routing_decision_id": decision.routing_decision_id,
             "provider_id": decision.provider_id, "started_at": started}
    attempt = GenerationAttempt(generation_attempt_id="attempt_" + sha256(basis),
        shot_id=shot.shot_id, shot_spec_version=shot.spec_version,
        shot_spec_hash=sha256(shot), prompt_plan_hash=sha256(plan),
        routing_decision_id=decision.routing_decision_id,
        provider_id=decision.provider_id, status="created", started_at=started)
    preview = make_provider_job(attempt, project_binding_id=sha256(session.project_id),
                                pre_dispatch_snapshot=snapshot)
    compiled = compile_flow_r2v_prompt(plan, preview.provider_job_id)
    prompt = compiled.text
    # Empty baseline here detects marker reuse before a fresh intent is frozen.
    if rpc_contract.match_r2v_output(records, session.project_id, reference_receipt['media_id'],
                                    preview.provider_job_id, baseline_ids=[]) is not None:
        raise OwnerAmbiguityGate("exact output existed before this shot was dispatched")
    request_hash = sha256({"contract": RPC_CONTRACT, "project": session.project_id,
        "prompt": prompt, "reference_id": reference_receipt["media_id"],
        "job_id": preview.provider_job_id})
    # Keep the canonical path unchanged. Only this provider's job evidence owns
    # its compact wire prompt; the generic Film compiler/runtime stays neutral.
    store.save_path(shot, plan, decision, attempt)
    job = preview.model_copy(update={'correlation_evidence': {
        'prompt': prompt, 'prompt_plan_hash': sha256(plan),
        'submission_prompt_hash': sha256(prompt), 'correlation_marker': compiled.marker,
        'provider_prompt_compiler': compiled.version,
        'reference_binding': _reference_binding(reference_receipt), 'rpc_request_hash': request_hash}})
    store.save_provider_job(job)
    if job.provider_job_id != preview.provider_job_id:
        raise ValueError("provider job identity changed during freeze")
    return store.read_provider_job(job.provider_job_id)


def _reference_binding(receipt: dict) -> dict:
    return {key: receipt[key] for key in ("asset_id", "reference_sha256",
                                          "project_id", "media_id",
                                          "provider_media_sha256")}


def _match_job_output(records, session, job):
    binding = job.correlation_evidence['reference_binding']
    if job.correlation_evidence.get('provider_prompt_compiler') == R2V_PROMPT_VERSION:
        return rpc_contract.match_r2v_output(records, session.project_id, binding['media_id'],
            job.provider_job_id, baseline_ids=job.pre_dispatch_snapshot['catalog_ids'])
    # Immutable legacy jobs keep their original exact-prompt contract. No
    # reinterpretation or rewrite of the ambiguous Shot A is authorized.
    return rpc_contract.match_output(records, session.project_id,
        job.correlation_evidence['prompt'], binding['media_id'])


class _ExactMediaTransport:
    def __init__(self, session):
        self.session = session

    async def fetch(self, job, output_id: str, destination: Path) -> Path:
        data = self.session.media(output_id, "video")
        if data is None:
            raise ValueError("exact provider video media unavailable")
        with destination.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        meta = inspect_video(destination)
        if (meta["mime_type"] != "video/mp4"
                or abs(meta["duration_s"] - 8) > .15
                or abs(meta["width"] / meta["height"] - 16 / 9) > .03):
            raise ValueError("SHOT_TECHNICAL_QC_FAIL")
        _full_decode(destination)
        return destination


def _full_decode(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required for full video decode")
    result = subprocess.run([ffmpeg, "-v", "error", "-xerror", "-i", str(path),
                             "-map", "0:v:0", "-f", "null", "-"],
                            capture_output=True, timeout=180)
    if result.returncode:
        raise ValueError("video did not decode fully through EOF")


def _acquire_bound(db_path: Path, session, job, output_dir: Path) -> Asset:
    store = SQLiteStore(db_path)
    bindings = store.read_output_bindings(job.provider_job_id)
    if len(bindings) != 1 or bindings[0]["output_id"] != store.read_provider_job(
            job.provider_job_id).external_job_id:
        raise OwnerAmbiguityGate("one exact bound output required")
    assets = asyncio.run(LiveRuntimeExecutor(store, _ExactMediaTransport(session))
                         .download_assets(job.provider_job_id, output_dir))
    if len(assets) != 1:
        raise OwnerAmbiguityGate("shot acquisition returned multiple Assets")
    asset = assets[0]
    meta = inspect_video(Path(asset.uri_or_path))
    if (asset.mime_type != "video/mp4" or abs(meta["duration_s"] - 8) > .15
            or abs(meta["width"] / meta["height"] - 16 / 9) > .03):
        raise ValueError("SHOT_TECHNICAL_QC_FAIL")
    _full_decode(Path(asset.uri_or_path))
    return asset


def submit_and_acquire_shot(db_path: Path, session, job, output_dir: Path,
                            *, poll_seconds: int = 600, progress=None,
                            successor_authority_id: str | None = None) -> Asset:
    """Consume one submit budget, then bind and acquire only one exact owned row."""
    store = SQLiteStore(db_path)
    fresh = store.read_provider_job(job.provider_job_id)
    if fresh != job:
        raise OwnerAmbiguityGate("provider job changed before execution")
    frozen_path = store.read_path(job.generation_attempt_id)[:3]
    if frozen_path not in compile_character_paths(db_path)[2]:
        raise ValueError("only the two frozen SLICE-0011 shots may submit")
    if frozen_path[0].shot_id == "CHAR_CONTINUITY_B":
        _require_acquired_shot_a(store)
    binding = job.correlation_evidence["reference_binding"]
    request_hash = job.correlation_evidence["rpc_request_hash"]
    prompt = job.correlation_evidence["prompt"]
    receipt = ReferenceUploadStore(db_path).read_verified("flow_veo", PROJECT_ID,
        ACCOUNT_ID, store.read_reference_asset(REFERENCE_ASSET_ID))
    if (binding["project_id"] != session.project_id
            or binding["asset_id"] != REFERENCE_ASSET_ID
            or binding["reference_sha256"] != REFERENCE_SHA256
            or receipt is None or binding != _reference_binding(receipt)
            or request_hash != sha256({"contract": RPC_CONTRACT,
                "project": session.project_id, "prompt": prompt,
                "reference_id": binding["media_id"], "job_id": job.provider_job_id})):
        raise OwnerAmbiguityGate("frozen request/reference identity mismatch")
    if job.dispatch_count != 0:
        raise OwnerAmbiguityGate("shot submit already reserved; no redispatch")
    if job.correlation_evidence.get('provider_prompt_compiler') == R2V_PROMPT_VERSION:
        compiled = compile_flow_r2v_prompt(frozen_path[1], job.provider_job_id)
        if (prompt != compiled.text or job.correlation_evidence.get('correlation_marker') != compiled.marker
                or job.correlation_evidence.get('submission_prompt_hash') != sha256(prompt)):
            raise OwnerAmbiguityGate('compact provider prompt differs from frozen canonical intent')
    baseline = session.catalog()
    if sorted(row[0].lower() for row in baseline) != job.pre_dispatch_snapshot["catalog_ids"]:
        raise OwnerAmbiguityGate("provider catalog changed after frozen baseline")
    if _match_job_output(baseline, session, job) is not None:
        raise OwnerAmbiguityGate("pre-submit output ownership collision")
    if successor_authority_id is None:
        reserved = store.reserve_dispatch(job.provider_job_id)
    else:
        from .slice0011_successor import reserve_successor_dispatch
        reserved = reserve_successor_dispatch(store, job.provider_job_id, successor_authority_id)
    try:
        request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, job.provider_job_id))

        def before_post(body_sha):
            store.record_dispatch_fact(job.provider_job_id, "RPC_REQUEST_ARMED",
                {"request_hash": request_hash, "body_sha256": body_sha,
                 "contract": RPC_CONTRACT})

        submit_options = {'before_post': before_post}
        if job.correlation_evidence.get('provider_prompt_compiler') == R2V_PROMPT_VERSION:
            submit_options['on_diagnostics'] = lambda diagnostic: store.record_dispatch_fact(
                job.provider_job_id, 'R2V_RESPONSE_DIAGNOSTICS', {'request_hash': request_hash, **diagnostic})
        session.submit_once(prompt, binding["media_id"], request_id, **submit_options)
        armed = next(f for f in store.read_dispatch_facts(job.provider_job_id)
                     if f["kind"] == "RPC_REQUEST_ARMED")
        store.record_dispatch_fact(job.provider_job_id, "GENERATE_REQUEST_OBSERVED",
            armed["data"])
        store.record_dispatch_fact(job.provider_job_id, "PROVIDER_RESPONSE_OBSERVED",
            {"request_hash": request_hash, "status": 200})
        deadline = time.monotonic() + poll_seconds
        while True:
            row = _match_job_output(session.catalog(), session, job)
            if row is not None:
                output_id = row[0]
                if output_id.lower() in job.pre_dispatch_snapshot["catalog_ids"]:
                    raise OwnerAmbiguityGate("output existed in pre-dispatch catalog")
                store.record_dispatch_fact(job.provider_job_id,
                    "PROVIDER_ACCEPTANCE_OBSERVED", {"request_hash": request_hash,
                    "provider_reference": binding["media_id"], "contract": RPC_CONTRACT})
                store.record_dispatch_fact(job.provider_job_id,
                    "REMOTE_IDENTITY_OBSERVED", {"output_id": output_id,
                    "method": "rpc_catalog_exact_prompt_reference"})
                store.bind_output(job.provider_job_id, output_id)
                bound = reserved.model_copy(update={"submission_state": "SUBMITTED",
                    "status": "SUCCEEDED", "submitted_at": utc_now(),
                    "external_job_id": output_id, "last_checked_at": utc_now()})
                store.save_provider_job(bound)
                break
            if time.monotonic() >= deadline:
                raise OwnerAmbiguityGate("exact output absent at bounded deadline")
            if progress:
                progress(shot_id=store.read_path(job.generation_attempt_id)[0].shot_id,
                         seconds_remaining=max(0, round(deadline - time.monotonic())))
            time.sleep(3)
    except Exception as exc:
        try:
            store.record_dispatch_fact(job.provider_job_id, "AMBIGUOUS_EVIDENCE",
                {"diagnostic": "reference_video_effect_requires_owner"})
        except Exception:
            pass
        raise OwnerAmbiguityGate("shot reserved; no redispatch; Owner review required") from exc
    try:
        return _acquire_bound(db_path, session, job, output_dir)
    except Exception as exc:
        if not any(f['kind'] == 'AMBIGUOUS_EVIDENCE' for f in store.read_dispatch_facts(job.provider_job_id)):
            store.record_dispatch_fact(job.provider_job_id, 'AMBIGUOUS_EVIDENCE',
                                       {'diagnostic': 'exact_acquisition_requires_owner'})
        raise OwnerAmbiguityGate('exact acquisition failed; no retry; Owner review required') from exc


def reconcile_and_acquire_shot(db_path: Path, session, job,
                               output_dir: Path) -> Asset:
    """After restart, read exact catalog/binding and acquire; never submit."""
    store = SQLiteStore(db_path)
    job = store.read_provider_job(job.provider_job_id)
    if store.read_path(job.generation_attempt_id)[:3] not in compile_character_paths(db_path)[2]:
        raise OwnerAmbiguityGate("recovery path differs from frozen two-shot plan")
    if job.dispatch_count != 1 or job.project_binding_id != sha256(session.project_id):
        raise OwnerAmbiguityGate("reserved shot/project required for reconciliation")
    facts = store.read_dispatch_facts(job.provider_job_id)
    if any(f["kind"] == "AMBIGUOUS_EVIDENCE" for f in facts):
        raise OwnerAmbiguityGate("Owner ambiguity gate already recorded")
    request = next((f for f in facts if f["kind"] == "GENERATE_REQUEST_OBSERVED"), None)
    binding = job.correlation_evidence["reference_binding"]
    receipt = ReferenceUploadStore(db_path).read_verified("flow_veo", PROJECT_ID,
        ACCOUNT_ID, store.read_reference_asset(REFERENCE_ASSET_ID))
    if (request is None
            or request["data"]["request_hash"] != job.correlation_evidence["rpc_request_hash"]
            or binding["project_id"] != session.project_id
            or binding["reference_sha256"] != REFERENCE_SHA256
            or binding["asset_id"] != REFERENCE_ASSET_ID
            or receipt is None or binding != _reference_binding(receipt)):
        raise OwnerAmbiguityGate("reserved request/reference cannot be reconciled")
    try:
        row = _match_job_output(session.catalog(), session, job)
    except Exception as exc:
        raise OwnerAmbiguityGate("provider catalog cannot be reconciled") from exc
    if row is None or row[0].lower() in job.pre_dispatch_snapshot["catalog_ids"]:
        raise OwnerAmbiguityGate("exact output not proven after restart")
    output_id = row[0]
    prior = store.read_output_bindings(job.provider_job_id)
    if prior and (len(prior) != 1 or prior[0]["output_id"] != output_id):
        raise OwnerAmbiguityGate("persisted output binding disagrees with provider")
    if job.external_job_id not in (None, output_id):
        raise OwnerAmbiguityGate("provider output identity changed after restart")
    acceptance = next((f for f in facts if f["kind"] == "PROVIDER_ACCEPTANCE_OBSERVED"), None)
    if acceptance is None:
        store.record_dispatch_fact(job.provider_job_id, "PROVIDER_ACCEPTANCE_OBSERVED",
            {"request_hash": request["data"]["request_hash"],
             "provider_reference": binding["media_id"], "contract": RPC_CONTRACT})
    store.record_dispatch_fact(job.provider_job_id, "REMOTE_IDENTITY_OBSERVED",
        {"output_id": output_id, "method": "rpc_catalog_exact_prompt_reference"})
    store.bind_output(job.provider_job_id, output_id)
    updated = job.model_copy(update={"submission_state": "SUBMITTED",
        "status": "SUCCEEDED", "submitted_at": job.submitted_at or utc_now(),
        "external_job_id": output_id, "last_checked_at": utc_now()})
    store.save_provider_job(updated)
    return _acquire_bound(db_path, session, updated, output_dir)
