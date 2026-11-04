"""Operator entry into the existing single-submit Flow R2V runtime."""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .core import ProviderCapabilities, ShotSpec, sha256
from .e2e import _project, references_for_shot
from .flow_r2v_runtime import FlowR2VShotRuntime, qualify_flow_catalog_source
from .live_runtime import Asset, file_sha256
from .providers import flow_rpc_contract as contract
from .providers.flow_canonical_ui import prepare_inputs, verify_chip
from .providers.flow_reference_binding import attest_existing_reference, adopt_existing_reference
from .providers.flow_reference_rpc import FlowReferenceRpcSession, FlowReferenceRpcDrift
from .providers.flow_reference_transport import FlowReferenceTransport
from .providers.flow_reference_upload import ReferenceUploadStore, _key
from .qc import QCStore, evidence, technical_evidence
from .store import SQLiteStore

MAX_SUBMISSIONS = 14  # Ten initial shots plus four Owner-authorized repairs.
ACCOUNT_ALIAS = "clean-pro-qualified"


def shot_spec(shot: dict, reference_id: str) -> ShotSpec:
    """The reviewed prompt is never shortened or silently rewritten here."""
    return ShotSpec.model_validate({
        "schema_version": "1.0.0", "spec_version": 1,
        "shot_id": shot["shot_id"], "scene_id": "E2E",
        "dramatic_purpose": shot["visual_intent"], "duration_target_s": 8,
        "shot_type": "action", "characters": [],
        "camera": {"framing": "MS", "height": "eye_level", "lens_intent": "normal",
                   "movement": {"type": "locked"}},
        "environment": {},
        "blocking": {"start": "reference pose", "action_beats": [shot["video_prompt"]],
                     "end": "hold"},
        "continuity": {"screen_direction": None, "eyeline": None,
                       "start_state": {}, "end_state": {}, "critical_invariants": []},
        "references": {"other_asset_ids": [reference_id]},
    })


def remaining_budget(store: SQLiteStore, project_id: str) -> int:
    connection = store._connect()
    try:
        ids = [row[0] for row in connection.execute("SELECT id FROM provider_jobs")]
    finally:
        connection.close()
    jobs = [store.read_provider_job(job_id) for job_id in ids]
    used = sum(job.project_binding_id == sha256(project_id) and job.dispatch_count == 1
               for job in jobs)
    return max(0, MAX_SUBMISSIONS - used)


class _DownloadedMedia:
    def __init__(self, media):
        self.media = media

    async def fetch(self, job, output_id, destination):
        if output_id != self.media.evidence["media_id"]:
            raise ValueError("Flow download identity changed")
        Path(destination).write_bytes(self.media.data)
        return destination


def _ingredients_mode(page):
    summary = page.locator("button.settings-trigger-button")
    summary.click(timeout=5000)
    try:
        page.get_by_role("radio", name=re.compile("Thành phần")).click(timeout=5000)
        for _ in range(20):
            checked = page.locator(".cdk-overlay-pane mat-button-toggle.mat-button-toggle-checked").all_inner_texts()
            if any("Thành phần" in text for text in checked):
                return
            page.wait_for_timeout(250)
        raise ValueError("Flow ingredients mode did not become selected")
    finally:
        summary.click(timeout=5000)


def run_shot(root: Path, db_path: Path, project_id: str, profile: Path,
             shot_id: str, poll_seconds: int = 300) -> dict:
    """Resume one exact job; acquisition stops at machine QC pending a person."""
    root, profile = Path(root).resolve(), Path(profile).resolve()
    meta, plan = _project(root)
    if not meta.get("locked_plan_sha256") or meta.get("flow_project_id") != project_id:
        raise ValueError("reviewed plan must be locked to this exact Flow project")
    if not profile.is_dir() or not 1 <= poll_seconds <= 1800:
        raise ValueError("existing Flow profile and finite polling duration required")
    matches = [shot for shot in plan["shots"] if shot["shot_id"] == shot_id]
    if len(matches) != 1:
        raise ValueError("one planned shot ID required")
    shot = matches[0]
    if shot["timeline_out_s"] - shot["timeline_in_s"] > 8:
        raise ValueError("planned shot exceeds the qualified eight-second Veo clip")
    refs = references_for_shot(root, shot_id)
    if len(refs) != 1:
        raise ValueError("one exact ChatGPT reference receipt required for this shot")
    from PIL import Image
    image_path = root / refs[0]["path"]
    with Image.open(image_path) as image:
        width, height = image.size
        mime_type = Image.MIME.get(image.format)
    reference = Asset(asset_id="asset_" + refs[0]["sha256"], asset_type="image", origin="reference",
        uri_or_path=str(image_path), sha256=refs[0]["sha256"], mime_type=mime_type,
        width=width, height=height, file_size=image_path.stat().st_size,
        rights_metadata={"source_kind": "chatgpt_web", "chat_url": refs[0]["chat_url"],
                         "profile_email": refs[0]["profile_email"], "tab_index": 2})
    store = SQLiteStore(db_path)
    store.initialize()
    QCStore(store).initialize()
    store.save_reference_asset(reference)
    capabilities = ProviderCapabilities(profile_version="flow-native-r2v-20261003-v2",
        provider_id="flow_veo", transport_type="other", supports_image_input=True,
        supports_duration_control=True)
    runtime = FlowR2VShotRuntime(store, project_id=project_id, account_id=ACCOUNT_ALIAS)
    evidence_dir = root / "flow" / shot_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with FlowReferenceRpcSession(profile_path=profile, project_id=project_id, native_ui=True) as session:
        # The existing upload journal deliberately permits one image only.
        # Reuse one such journal per image; adopt its verified readback into
        # the film runtime rather than migrating or weakening old journals.
        original_uploads = ReferenceUploadStore(db_path)
        original_uploads.initialize()
        key = _key('flow_veo', project_id, ACCOUNT_ALIAS, reference)
        use_original = original_uploads.read_progress(key) is not None
        upload_db = (db_path if use_original else
                     root / 'flow' / 'reference_uploads' / reference.sha256 / 'upload.sqlite')
        upload_db.parent.mkdir(parents=True, exist_ok=True)
        uploads = ReferenceUploadStore(upload_db)
        uploads.initialize()
        reference_receipt = FlowReferenceTransport(uploads, session, account_id=ACCOUNT_ALIAS,
            evidence_dir=evidence_dir / "upload").ensure_verified(reference)
        if use_original:
            attestation_dir = evidence_dir / "attestation"
            attestation = attest_existing_reference(store, reference, session,
                account_id=ACCOUNT_ALIAS, media_id=reference_receipt["media_id"], evidence_dir=attestation_dir)
        else:
            reference_dir = root / 'readbacks' / reference.sha256[:16]
            attestation_dir = evidence_dir / 'attestation'
            reference, attestation = adopt_existing_reference(store, session,
                account_id=ACCOUNT_ALIAS, media_id=reference_receipt['media_id'],
                reference_dir=reference_dir, attestation_dir=attestation_dir)
            if attestation['readback']['sha256'] != reference_receipt['provider_media_sha256']:
                raise ValueError('verified upload and adopted reference bytes differ')
        spec = shot_spec(shot, reference.asset_id)
        frozen = runtime.freeze(spec, capabilities, reference_asset=reference,
            reference_media_id=reference_receipt["media_id"],
            catalog_source=qualify_flow_catalog_source(session))
        job_id = frozen.job.provider_job_id
        job = store.read_provider_job(job_id)
        prompt = job.correlation_evidence["prompt"]
        if not job.dispatch_count:
            if remaining_budget(store, project_id) <= 0:
                raise ValueError("Flow submission budget exhausted; no new request")
            # Upload RPCs do not refresh the editor's in-memory picker cache.
            session.page.reload(wait_until='domcontentloaded', timeout=30000)
            session.page.locator('button.settings-trigger-button').wait_for(timeout=15000)
            _ingredients_mode(session.page)
            records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            prepare_inputs(session, records, media_id=reference_receipt["media_id"], prompt=prompt)
            runtime.reserve(frozen, attestation=attestation, evidence_dir=attestation_dir)
            guard = runtime.arm_native_guard(frozen)
            session.page.context.route("**/batchexecute?*", guard.route)

            def response_observed(response):
                if "MZZa6b" in response.url:
                    runtime.observe_provider_response(frozen, status=response.status)

            session.page.on("response", response_observed)
            verify_chip(session.page, reference_receipt["media_id"])
            store.record_dispatch_fact(job_id, "PROMPT_VERIFIED", {"prompt_sha256": sha256(prompt)})
            store.record_dispatch_fact(job_id, "CLICK_ARMED", {})
            session.page.locator("button.generate-icon-button").click(timeout=10000)
            release_deadline = time.monotonic() + 30
            while not guard.sent and not guard.error and time.monotonic() < release_deadline:
                session.page.wait_for_timeout(250)
            if guard.error or guard.sent != 1:
                raise ValueError("Flow request not released: " + str(guard.error or "unobserved"))
            print(json.dumps({"shot_id": shot_id, "provider_job_id": job_id,
                              "state": "REQUEST_RELEASED"}), flush=True)
        deadline = time.monotonic() + poll_seconds
        while time.monotonic() < deadline:
            try:
                records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            except FlowReferenceRpcDrift:
                # An unqualified pending row grants neither ownership nor a
                # retry. Keep observing the same reserved job within the cap.
                session.page.wait_for_timeout(5000)
                continue
            try:
                output_id = runtime.attribute_backend_output(frozen, records)
            except contract.ContractError as error:
                if str(error) != "OUTPUT_STATUS_UNQUALIFIED":
                    raise
                output_id = None
            if output_id:
                render = runtime.observe_render_state(frozen, session=session)
                if render.state == "RENDER_COMPLETED":
                    runtime.observe_provider_acceptance(frozen, provider_reference="backend:" + output_id)
                    media = session.bound_media(output_id, "video")
                    # Sync Playwright owns a running loop; acquisition uses
                    # asyncio.run on already-downloaded bytes, without browser calls.
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        asset = executor.submit(runtime.acquire, frozen,
                            transport=_DownloadedMedia(media), destination_dir=root / "media",
                            media_payload=render.payload).result()
                    runtime.qc_eligibility(frozen, asset)
                    rows, _ = technical_evidence(frozen.shot, asset)
                    for gate in ("visual", "continuity", "editorial"):
                        rows.append(evidence(asset=asset, evaluator_type="temporal_heuristic",
                            evaluator_version="operator-review-pending-v1", gate=gate,
                            criterion="operator_review_pending", verdict="uncertain",
                            observation="Not evaluated; explicit operator review required.",
                            source_artifacts=[{"path": asset.uri_or_path, "sha256": asset.sha256}]))
                    report, _ = QCStore(store).save(asset, rows)
                    return {"shot_id": shot_id, "provider_job_id": job_id,
                        "asset_id": asset.asset_id, "path": asset.uri_or_path,
                        "sha256": asset.sha256, "qc_report_id": report.report["qc_report_id"],
                        "qc_decision": report.report["decision"], "state": "ACQUIRED_REVIEW_REQUIRED"}
            session.page.wait_for_timeout(min(5000, max(1, int((deadline-time.monotonic())*1000))))
        return {"shot_id": shot_id, "provider_job_id": job_id, "state": "RECONCILE_REQUIRED",
                "note": "No new submission on resume; reconcile the reserved job."}
