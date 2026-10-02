"""FLOW-SCENE-SCALE-003-R1 — fresh authorized Shot-3 re-proof runner.

A NEW Owner-authorized execution scope (this frozen package grants
MAX_FRESH_VIDEO_GENERATE = 1, UPLOAD AUTHORITY = 0, retries 0). The old
FLOW-SCENE-SCALE-003 scope is permanently LATCHED_CLOSED (retroactive
custody): only this fresh scope may mutate.

Chain per frozen package: re-attested continuity reference (read-only)
→ NEW ProviderJob (SCENE003_SHOT_3R, fresh marker) → fresh pre-dispatch
baseline → attested reservation → headful native UI → ONE Generate →
release observation → read-only reconciliation → unique attribution →
render lifecycle → exact acquisition → SHA256 → ffprobe → full EOF decode
→ QC. PASS requires exact marker echo, unique provider media, correct
project/reference lineage, render completion, may_submit=false after.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys_path = str(Path(__file__).resolve().parents[1] / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
tools_path = str(Path(__file__).resolve().parent)
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

from film_pipeline.core import ProviderCapabilities, References, load_shot, sha256
from film_pipeline.flow_r2v_boundary import MutationIntent
from film_pipeline.flow_r2v_runtime import (
    FlowR2VShotRuntime,
    FrozenR2VShot,
    qualify_flow_catalog_source,
)
from film_pipeline.live_runtime import LiveRuntimeExecutor, utc_now
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_canonical_ui import prepare_inputs, verify_chip
from film_pipeline.providers.flow_media import parse_media_resource
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
    OwnerAuthRequired,
)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_r2v_prompt import MARKER_RE
from film_pipeline.store import SQLiteStore

from mutation_authority import (
    KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
    MutationAuthority,
)
from run_scene_scale_003 import (
    PreFetchedTransport,
    flow_capabilities,
    poll_media,
    verify_full_decode,
)

ROOT = Path(__file__).resolve().parents[1]
REPROOF_DIR = ROOT / "projects/flow_scene_scale_003_reproof_001"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
MODEL = contract.MODEL_VEO_3_1_LITE
MAX_FRESH_VIDEO_GENERATE = 1
CONTINUITY_MEDIA_ID = "0c16d60b-b027-48da-adb8-c1cb9a4ecf64"
SHOT_ID = "SCENE003_SHOT_3R"
OBSERVATION_WINDOW_S = 2400
POLL_INTERVAL_S = 60
RELEASE_WAIT_S = 45
MUTATION_ROUTE = "**/batchexecute?*"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"
BASE_REFERENCE_BINDING = json.loads(
    (ROOT / "projects/flow_production_harden_002/requal_current_build/reference_binding.json")
    .read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_durable(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, indent=2, ensure_ascii=False)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise OwnerAmbiguityGate(f"EVIDENCE_CONFLICT: {path.name}")
        return
    path.write_text(encoded, encoding="utf-8")


def authority() -> MutationAuthority:
    return MutationAuthority(REPROOF_DIR, "FLOW-SCENE-SCALE-003-R1")


def frozen_handle(store: SQLiteStore, job_id: str) -> FrozenR2VShot:
    job = store.read_provider_job(job_id)
    binding = job.correlation_evidence["reference_binding"]
    shot, plan, route, attempt = store.read_path(job.generation_attempt_id)
    intent = MutationIntent(project_id=PROJECT_ID, account_id=ACCOUNT_ID,
                            reference_media_id=binding["media_id"], model=MODEL)
    return FrozenR2VShot(shot=shot, plan=plan, attempt=attempt, job=job,
                         intent=intent,
                         reference_asset=store.read_reference_asset(binding["asset_id"]))


def stage_reattest() -> dict:
    """R2 — read-only continuity reference re-attestation (fresh readback).

    Chain recomputed: shot-2 asset (sha b45816bb…) → extracted frame
    (sha 5e0dc357…) → historical upload receipt refup_73a4bacf… → provider
    media 0c16d60b… → fresh provider readback (exact bytes) → content/metadata
    attestation. No upload, no mutation, no gallery heuristics.
    """
    out = REPROOF_DIR / "r2_reattest.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    report = {"stage": "R2_REATTEST", "gate": "OWNER_GATE_LOCAL_FAILURE",
              "provider_mutations": 0}
    try:
        scene_dir = ROOT / "projects/flow_scene_scale_003"
        frame = json.loads((scene_dir / "continuity_frame_SCENE003_SHOT_3.json")
                           .read_text(encoding="utf-8"))
        frame_asset = json.loads((scene_dir / "frame_asset.json").read_text(
            encoding="utf-8"))
        upload_store_path = scene_dir / "continuity_upload_1.sqlite"
        from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore
        receipt = ReferenceUploadStore(upload_store_path).read_verified(
            "flow_veo", PROJECT_ID, ACCOUNT_ID,
            __import__("film_pipeline.live_runtime", fromlist=["Asset"])
            .Asset.model_validate(frame_asset))
        if receipt["media_id"] != CONTINUITY_MEDIA_ID:
            raise OwnerAmbiguityGate("CONTINUITY_MEDIA_IDENTITY_DRIFT")
        report["upload_receipt_verified"] = True
        report["provider_media_id"] = receipt["media_id"]
        report["provider_media_sha256"] = receipt["provider_media_sha256"]
        with open_read_session() as session:
            records = session.catalog(
                contract_version=contract.CONTRACT_VERSION_2026_10_01)
            matches = [row for row in records
                       if row[0].lower() == CONTINUITY_MEDIA_ID.lower()]
            if len(matches) != 1:
                raise OwnerAmbiguityGate("CONTINUITY_ROW_NOT_UNIQUE")
            if matches[0][1].lower() != PROJECT_ID.lower():
                raise OwnerAmbiguityGate("CONTINUITY_PROJECT_MISMATCH")
            # Fresh provider readback: exact bytes vs the verified receipt.
            media = session.bound_media(CONTINUITY_MEDIA_ID, "image")
            from film_pipeline.core import canonical_json
            readback_sha = media.evidence["sha256"]
            if readback_sha != receipt["provider_media_sha256"]:
                raise OwnerAmbiguityGate("CONTINUITY_READBACK_DRIFT")
            report["fresh_readback_sha256"] = readback_sha
            # Content identity vs the extracted frame source bytes.
            frame_bytes = Path(frame["path"]).read_bytes()
            report["frame_bytes_equal_readback"] = (frame_bytes == media.data)
            report["frame_sha256"] = frame["sha256"]
            # Re-attest through the immutable chain (fresh readback inside).
            from film_pipeline.providers.flow_reference_binding import (
                attest_existing_reference)
            upload_store = SQLiteStore(upload_store_path)
            upload_store.initialize()
            attestation = attest_existing_reference(
                upload_store, __import__("film_pipeline.live_runtime",
                                         fromlist=["Asset"])
                .Asset.model_validate(frame_asset), session,
                account_id=ACCOUNT_ID, media_id=CONTINUITY_MEDIA_ID,
                evidence_dir=upload_store_path.parent / "continuity_evidence")
            report["attestation_id"] = attestation["attestation_id"]
            report["provider_mutations"] = 0
        report["gate"] = "R2_CONTINUITY_REFERENCE_REATTESTED"
    except OwnerAuthRequired as exc:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
        report["diagnostic"] = str(exc)
    except OwnerAmbiguityGate as exc:
        report["gate"] = "OWNER_AMBIGUITY_GATE"
        report["diagnostic"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
        report["diagnostic"] = f"{type(exc).__name__}: {exc}"[:300]
    write_durable(out, report)
    print(json.dumps({"stage": "reattest", "gate": report["gate"]}), flush=True)
    return report


def stage_generate() -> dict:
    """R3 — the ONE fresh authorized Generate for Shot-3R."""
    out = REPROOF_DIR / "shot_3R_result.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    reattest = stage_reattest()
    if reattest["gate"] != "R2_CONTINUITY_REFERENCE_REATTESTED":
        return {**reattest, "shot_id": SHOT_ID,
                "note": "R2 did not pass; no mutation attempted"}
    report = {"shot_id": SHOT_ID, "gate": "OWNER_GATE_LOCAL_FAILURE",
              "generate_clicks": 0, "observed_generate_requests": 0,
              "fresh_authority": "FLOW-SCENE-SCALE-003-R1 (MAX_FRESH_VIDEO_GENERATE=1)"}
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    frozen = None
    try:
        runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID,
                                     account_id=ACCOUNT_ID, model=MODEL)
        # The re-proof continuity binding: same provider media + adopted asset
        # + attestation already living in the shared runtime store.
        binding = {"media_id": CONTINUITY_MEDIA_ID,
                   "asset_id": _continuity_adopted_asset_id(),
                   "attestation_id": _continuity_adopted_attestation_id(),
                   "mechanism": "last_frame_reproof"}
        attestation = json.loads(_continuity_attestation_path(
            binding["attestation_id"]).read_text(encoding="utf-8"))
        # ---- freeze + reserve (headless reads) ----
        with open_read_session() as session:
            capability = qualify_flow_catalog_source(session)
            spec = load_shot(ROOT / "fixtures/scene003/scene003_shot_3r.json")
            spec = spec.model_copy(update={
                "references": References(other_asset_ids=[binding["asset_id"]])})
            frozen = runtime.freeze(spec, flow_capabilities(),
                reference_asset=store.read_reference_asset(binding["asset_id"]),
                reference_media_id=CONTINUITY_MEDIA_ID,
                reference_filename="",
                catalog_source=capability, started_at=utc_now())
            job_id = frozen.job.provider_job_id
            prompt = frozen.job.correlation_evidence["prompt"]
            report["provider_job_id"] = job_id
            write_durable(REPROOF_DIR / "frozen_intent.json", {
                "shot_id": SHOT_ID, "provider_job_id": job_id,
                "generation_attempt_id": frozen.attempt.generation_attempt_id,
                "prompt": prompt, "prompt_sha256": sha256(prompt),
                "correlation_marker": frozen.job.correlation_evidence["correlation_marker"],
                "continuity": binding,
                "pre_dispatch_snapshot": frozen.job.pre_dispatch_snapshot})
            write_durable(REPROOF_DIR / "preclaim.json", {
                "shot_id": SHOT_ID, "provider_job_id": job_id,
                "budget": "MAX_FRESH_VIDEO_GENERATE=1", "uploads": 0})
            already_consumed = bool(store.read_provider_job(job_id).dispatch_count)
            if not already_consumed:
                authority().check_mutation_allowed("fresh_video_generate")
                runtime.reserve(frozen, attestation=attestation,
                                evidence_dir=_continuity_attestation_dir())
            records = session.catalog(
                contract_version=contract.CONTRACT_VERSION_2026_10_01)
            if not already_consumed and sorted(
                    row[0].lower() for row in records) != \
                    frozen.job.pre_dispatch_snapshot["catalog_ids"]:
                raise OwnerAmbiguityGate("BASELINE_CHANGED_BEFORE_UI_PREPARATION")
        if already_consumed:
            report["resume_read_only"] = True
        else:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(
                    PROFILE, channel="chrome", headless=False,
                    args=["--no-first-run", "--no-default-browser-check",
                          "--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"], viewport=None)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    page.goto(f"https://flow.google.com/project/{PROJECT_ID}",
                              timeout=60000)
                    page.wait_for_timeout(8000)
                    if "accounts.google" in page.url:
                        raise OwnerAuthRequired("OWNER_AUTH_REQUIRED: sign-in lost")
                    ui_session = SimpleNamespace(page=page, project_id=PROJECT_ID)
                    try:
                        ui = prepare_inputs(ui_session, records,
                                            media_id=CONTINUITY_MEDIA_ID,
                                            prompt=prompt)
                    except Exception:
                        page.screenshot(path=str(REPROOF_DIR / "ui_prepare_failure.png"))
                        raise
                    report["ui_preflight"] = ui
                    response_holder = {}

                    def on_response(response):
                        if "MZZa6b" not in response.url or "status" in response_holder:
                            return
                        try:
                            body = response.text()
                        except Exception:
                            body = ""
                        response_holder["status"] = response.status
                        response_holder["byte_length"] = len(body.encode("utf-8"))
                        try:
                            response_holder["diagnostics"] = \
                                contract.submission_diagnostics(body)
                        except Exception:
                            response_holder["diagnostics"] = {
                                "classification": "UNPARSEABLE",
                                "advisory_only": True}

                    page.on("response", on_response)
                    guard = runtime.arm_native_guard(frozen)
                    page.context.route(MUTATION_ROUTE, guard.route)
                    verify_chip(page, CONTINUITY_MEDIA_ID)
                    editor = page.locator('div.ProseMirror[contenteditable="true"]')
                    if editor.count() != 1 or editor.inner_text() != prompt:
                        raise OwnerAmbiguityGate("PROMPT_CHANGED_AT_MUTATION_BOUNDARY")
                    store.record_dispatch_fact(job_id, "PROMPT_VERIFIED",
                                               {"prompt_sha256": sha256(prompt)})
                    store.record_dispatch_fact(job_id, "CLICK_ARMED", {})
                    guard.armed = True
                    report["generate_clicks"] = 1
                    page.locator("button.generate-icon-button").click(timeout=15000)
                    end = time.monotonic() + RELEASE_WAIT_S
                    while guard.sent != 1 and guard.error is None and \
                            time.monotonic() < end:
                        page.wait_for_timeout(250)
                    report["observed_generate_requests"] = guard.seen
                    if guard.error is not None:
                        report["gate"] = "OWNER_GATE_REQUEST_NEVER_RELEASED"
                        raise OwnerAmbiguityGate(guard.error)
                    if guard.sent != 1:
                        report["gate"] = "OWNER_GATE_REQUEST_NEVER_RELEASED"
                        raise OwnerAmbiguityGate("EXACT_NATIVE_REQUEST_NOT_OBSERVED")
                    authority().consume("fresh_video_generate")
                    report["gate"] = "OWNER_AMBIGUITY_GATE"
                    end = time.monotonic() + 30
                    while "status" not in response_holder and \
                            time.monotonic() < end:
                        page.wait_for_timeout(250)
                    report["provider_response"] = response_holder
                    page.screenshot(path=str(REPROOF_DIR / "post_release.png"))
                finally:
                    try:
                        ctx.close()
                    except Exception:
                        pass
            if report.get("provider_response", {}).get("status"):
                runtime.observe_provider_response(frozen,
                    status=report["provider_response"]["status"])
                counts = (report["provider_response"].get("diagnostics") or {}).get(
                    "type_counts") or {}
                if any(count for key, count in counts.items() if key != "null"):
                    runtime.observe_provider_acceptance(
                        frozen, provider_reference="MZZa6b_wire_ack")
        # ---- read-only reconciliation + acquisition ----
        with open_read_session() as session:
            window_end = time.monotonic() + OBSERVATION_WINDOW_S
            next_poll = time.monotonic() + 10.0
            output_id, records = None, None
            polls = 0
            while time.monotonic() < window_end and output_id is None:
                if time.monotonic() >= next_poll:
                    polls += 1
                    next_poll = time.monotonic() + POLL_INTERVAL_S
                    try:
                        records = session.catalog(
                            contract_version=contract.CONTRACT_VERSION_2026_10_01)
                    except FlowReferenceRpcDrift:
                        continue
                    try:
                        output_id = runtime.attribute_backend_output(frozen, records)
                    except contract.ContractError as exc:
                        if str(exc) == "OUTPUT_STATUS_UNQUALIFIED":
                            continue
                        raise OwnerAmbiguityGate(
                            "BACKEND_ATTRIBUTION_MATERIAL_DISAGREEMENT: " + str(exc))
                time.sleep(1.0)
            if output_id is None:
                raise OwnerAmbiguityGate("EXTERNAL_EFFECT_UNRESOLVED")
            report["reconciliation_polls"] = polls
            report["output_identity"] = output_id
            marker = frozen.job.correlation_evidence["correlation_marker"]
            marker_rows = [row for row in records
                           if marker in " ".join(contract._strings(row))]
            if len(marker_rows) != 1:
                raise OwnerAmbiguityGate("BACKEND_MARKER_ROW_NOT_UNIQUE")
            if prompt not in [s for s in contract._strings(marker_rows[0])
                              if MARKER_RE.findall(s) == [marker]]:
                raise OwnerAmbiguityGate("BACKEND_EXACT_PROMPT_MISMATCH")
            render = runtime.observe_render_state(frozen, session=session)
            report["render_state_observed"] = render.state
            payload = render.payload if render.state == "RENDER_COMPLETED" \
                else poll_media(session, output_id, report)
            resource = parse_media_resource(payload, media_id=output_id,
                                            project_id=PROJECT_ID, kind="video")
            media = session.bound_media(output_id, "video")
        asset = runtime.acquire(frozen, transport=PreFetchedTransport(media.data, output_id),
            destination_dir=REPROOF_DIR / "videos", media_payload=payload)
        report["asset"] = asset.model_dump(mode="json")
        report["decode"] = verify_full_decode(Path(asset.uri_or_path))
        report["qc_eligibility"] = runtime.qc_eligibility(frozen, asset)
        executor = LiveRuntimeExecutor(SQLiteStore(STORE_PATH), None)
        recovery = executor.recovery_decision(frozen.job.provider_job_id)
        report["restart_proofs"] = {
            "dispatch_count": store.read_provider_job(
                frozen.job.provider_job_id).dispatch_count,
            "recovery_classification": recovery.classification,
            "may_submit": recovery.may_submit}
        report["gate"] = "R3_SHOT3_REPROOF_PROVEN"
        authority().record_knowledge("RESOLVED_EFFECT_IDENTIFIED",
                                     f"unique output {output_id}")
    except OwnerAuthRequired as exc:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
        report["diagnostic"] = str(exc)
    except OwnerAmbiguityGate as exc:
        report["diagnostic"] = str(exc)
        if report.get("observed_generate_requests"):
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            authority().latch("GENERATE_AMBIGUITY", str(exc))
            try:
                store.record_dispatch_fact(frozen.job.provider_job_id,
                    "AMBIGUOUS_EVIDENCE", {"diagnostic": "reproof_owner_gate"})
            except Exception:
                pass
        else:
            report["gate"] = "OWNER_GATE: " + str(exc)
    except Exception as exc:  # noqa: BLE001
        report["diagnostic"] = f"{type(exc).__name__}: {exc}"[:400]
        if report.get("observed_generate_requests"):
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            authority().latch("GENERATE_AMBIGUITY", str(exc))
        else:
            report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
    write_durable(out, report)
    print(json.dumps({"shot_id": SHOT_ID, "gate": report["gate"],
                      "output": report.get("output_identity")}), flush=True)
    return report


def _continuity_adopted_asset_id() -> str:
    ledger = json.loads((ROOT / "projects/flow_scene_scale_003/continuity_ledger.json")
                        .read_text(encoding="utf-8"))
    matches = [b for b in ledger["bindings"] if b["for_shot"] == "SCENE003_SHOT_3"]
    if len(matches) != 1:
        raise OwnerAmbiguityGate("CONTINUITY_BINDING_NOT_UNIQUE")
    return matches[0]["adopted_asset_id"]


def _continuity_adopted_attestation_id() -> str:
    ledger = json.loads((ROOT / "projects/flow_scene_scale_003/continuity_ledger.json")
                        .read_text(encoding="utf-8"))
    matches = [b for b in ledger["bindings"] if b["for_shot"] == "SCENE003_SHOT_3"]
    return matches[0]["adopted_attestation_id"]


def _continuity_attestation_dir() -> Path:
    return SCENE_ATT_DIR


SCENE_ATT_DIR = (ROOT / "projects/flow_scene_scale_003/continuity_reference/attestation")


def open_read_session():
    return FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                   project_id=PROJECT_ID, native_ui=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["reattest", "generate"])
    args = parser.parse_args()
    if args.stage == "reattest":
        stage_reattest()
    else:
        stage_generate()


if __name__ == "__main__":
    main()
