"""FLOW-SCENE-SCALE-003 — live N-shot scene runner over the proven runtime.

Generalizes the proven per-shot Flow runtime to a frozen ScenePlan:

ScenePlan → per-shot [freeze → baseline → reserve → attested reference →
headful native UI → ONE Generate → reconcile → render lifecycle → acquire →
decode] → continuity upload (last-frame, budgeted) → QC → provisional
SelectedTakes → scene EditManifest → AutoEdit producer package → real rough
cut through the existing editorial boundary.

Frozen budgets: MAX_PRIMARY_GENERATES = 6, MAX_REPAIR_GENERATES = 2,
MAX_CONTINUITY_UPLOADS = 2. Every Generate: unique durable ProviderJob,
immutable intent, exact marker/project/reference binding, fresh baseline,
at-most-once release, marker-echo attribution. may_submit=false forever for
consumed jobs. No gallery heuristics. No direct MZZa6b.

Scene layer: tools/scene_runner.py (generic, restart-safe, executor-injected).
"""
from __future__ import annotations

import argparse
import json
import subprocess
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
from film_pipeline.providers.flow_reference_binding import (
    adopt_existing_reference,
    attest_existing_reference,
)
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
    OwnerAuthRequired,
)
from film_pipeline.providers.flow_reference_transport import FlowReferenceTransport
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_r2v_prompt import MARKER_RE
from film_pipeline.store import SQLiteStore

import scene_runner

ROOT = Path(__file__).resolve().parents[1]
SCENE_DIR = ROOT / "projects/flow_scene_scale_003"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
# The reference binding is a Git-ignored runtime artifact: load it
# lazily so importing this module (and its pure helpers such as
# flow_capabilities) works in a fresh clean checkout; only the paths
# that genuinely need the binding fail closed with this error.
_BINDING_PATH = (ROOT / "projects/flow_production_harden_002/requal_current_build/reference_binding.json")
_BASE_REFERENCE_BINDING: dict | None = None


def _base_reference_binding() -> dict:
    global _BASE_REFERENCE_BINDING
    if _BASE_REFERENCE_BINDING is None:
        try:
            _BASE_REFERENCE_BINDING = json.loads(
                _BINDING_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise RuntimeError(
                f"reference binding missing: {_BINDING_PATH} "
                f"(Git-ignored runtime artifact; fresh checkouts do not "
                f"carry it — restore the requal build or copy "
                f"reference_binding.json from the production checkout "
                f"before running scene-scale dispatch)") from error
    return _BASE_REFERENCE_BINDING
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
MODEL = contract.MODEL_VEO_3_1_LITE
MAX_PRIMARY_GENERATES = 6
MAX_REPAIR_GENERATES = 2
MAX_CONTINUITY_UPLOADS = 2
OBSERVATION_WINDOW_S = 2400
POLL_INTERVAL_S = 60
RELEASE_WAIT_S = 45
MUTATION_ROUTE = "**/batchexecute?*"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"


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


def ledger() -> dict:
    path = SCENE_DIR / "generate_ledger.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"initialized_at": now(), "max_primary": MAX_PRIMARY_GENERATES,
            "max_repair": MAX_REPAIR_GENERATES, "max_uploads": MAX_CONTINUITY_UPLOADS,
            "primary_consumed": [], "repair_consumed": [], "uploads": []}


def save_ledger(data: dict) -> None:
    path = SCENE_DIR / "generate_ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def open_read_session():
    return FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                   project_id=PROJECT_ID, native_ui=True)


def flow_capabilities() -> ProviderCapabilities:
    payload = {
        "profile_version": "flow-scene-scale-003-v1",
        "provider_id": "flow_veo", "transport_type": "other",
        "supports_text_to_video": True, "supports_image_input": True,
        "supports_duration_control": True,
    }
    from film_pipeline.core import validate_contract
    validate_contract("provider_capabilities", payload)
    return ProviderCapabilities.model_validate(payload)


def frozen_handle(store: SQLiteStore, job_id: str) -> FrozenR2VShot:
    job = store.read_provider_job(job_id)
    binding = job.correlation_evidence["reference_binding"]
    shot, plan, route, attempt = store.read_path(job.generation_attempt_id)
    intent = MutationIntent(project_id=PROJECT_ID, account_id=ACCOUNT_ID,
                            reference_media_id=binding["media_id"], model=MODEL)
    return FrozenR2VShot(shot=shot, plan=plan, attempt=attempt, job=job,
                         intent=intent,
                         reference_asset=store.read_reference_asset(binding["asset_id"]))


class PreFetchedTransport:
    def __init__(self, data: bytes, output_id: str):
        self.data = data
        self.output_id = output_id

    async def fetch(self, job, output_id, destination):
        if output_id != self.output_id:
            raise OwnerAmbiguityGate("ACQUISITION_OUTPUT_IDENTITY_MISMATCH")
        destination.write_bytes(self.data)
        return destination


def verify_full_decode(path: Path) -> dict:
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=300, check=False)
    return {"returncode": completed.returncode, "full_decode_eof": completed.returncode == 0}


def poll_media(session, output_id: str, report: dict):
    from film_pipeline.flow_r2v_runtime import (
        AS29S_PAYLOAD_COMPLETED, classify_as29s_payload)
    window_end = time.monotonic() + 900
    attempts = 0
    while time.monotonic() < window_end:
        attempts += 1
        payload = session.media_payload(output_id)
        classification = classify_as29s_payload(payload, media_id=output_id,
                                                project_id=PROJECT_ID)
        if classification == AS29S_PAYLOAD_COMPLETED:
            report["media_resolution_attempts"] = attempts
            return payload
        report.setdefault("media_resolution_observations", []).append(
            {"attempt": attempts, "classification": classification})
        print(json.dumps({"stage": "media_resolution_pending", "attempts": attempts,
                          "classification": classification}), flush=True)
        time.sleep(20.0)
    raise OwnerAmbiguityGate("MEDIA_RESOLUTION_WINDOW_EXPIRED")


def reference_binding_for(shot: dict) -> dict:
    """Resolve the continuity binding for one planned shot (durable ledger)."""
    kind = shot["continuity"]["kind"]
    if kind == "reference":
        binding = _base_reference_binding()
        return {"media_id": binding["media_id"],
                "asset_id": binding["asset_id"],
                "attestation_id": binding["attestation_id"],
                "mechanism": "same_reference"}
    if kind == "last_frame":
        ledger_path = SCENE_DIR / "continuity_ledger.json"
        entries = json.loads(ledger_path.read_text(encoding="utf-8"))["bindings"]
        binding_for = shot["continuity"].get("binding_for", shot["shot_id"])
        matches = [e for e in entries if e["for_shot"] == binding_for]
        if len(matches) != 1:
            raise OwnerAmbiguityGate(
                f"CONTINUITY_BINDING_MISSING for {shot['shot_id']}")
        entry = matches[0]
        # The runtime consumes the ADOPTED attestation (the scene-store
        # readback binding of the uploaded media); the upload attestation
        # remains in the dedicated continuity store as upload provenance.
        return {"media_id": entry["provider_media_id"],
                "asset_id": entry["adopted_asset_id"],
                "attestation_id": entry["adopted_attestation_id"],
                "mechanism": "last_frame",
                "from_shot": shot["continuity"]["from_shot"],
                "source_frame_sha256": entry["frame_sha256"],
                "upload_store": entry["upload_store"],
                "upload_attestation_id": entry["attestation_id"]}
    raise OwnerAmbiguityGate("CONTINUITY_KIND_UNQUALIFIED")


def extract_last_frame(asset_path: Path, destination: Path) -> dict:
    """Deterministic exact final-frame extraction from an acquired Asset."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(asset_path),
         "-frames:v", "1", str(destination)], capture_output=True, text=True,
        check=False)
    if completed.returncode or not destination.exists():
        raise OwnerAmbiguityGate("LAST_FRAME_EXTRACTION_FAILED")
    from PIL import Image
    with Image.open(destination) as image:
        width, height = image.size
        image.load()
    data = destination.read_bytes()
    import hashlib
    return {"path": str(destination), "sha256": hashlib.sha256(data).hexdigest(),
            "width": width, "height": height, "file_size": len(data),
            "source_asset": str(asset_path)}


def continuity_upload(shot_id: str, from_shot: str) -> dict:
    """ONE durable last-frame continuity upload for the planned transition.

    Chain: acquired Shot-N Asset → deterministic final-frame extraction →
    registered local Asset → one durable upload reservation → ONE maseQ POST
    through the proven transport → unique provider identity → readback
    verification → attestation → read-only adoption into the scene store.
    """
    ledger = json.loads((SCENE_DIR / "continuity_ledger.json").read_text(
        encoding="utf-8")) if (SCENE_DIR / "continuity_ledger.json").exists() \
        else {"bindings": []}
    if any(e["for_shot"] == shot_id for e in ledger["bindings"]):
        return [e for e in ledger["bindings"] if e["for_shot"] == shot_id][0]
    if len(ledger["bindings"]) >= MAX_CONTINUITY_UPLOADS:
        raise OwnerAmbiguityGate("CONTINUITY_UPLOAD_BUDGET_EXHAUSTED")
    from mutation_authority import MutationAuthority
    MutationAuthority(SCENE_DIR, "FLOW-SCENE-SCALE-003").check_mutation_allowed(
        "continuity_upload")
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    # Source: the acquired, exactly-hashed Shot-N Asset from the scene store.
    prior_result = json.loads((SCENE_DIR / f"shot_{from_shot}" / "result.json")
                              .read_text(encoding="utf-8"))
    if prior_result.get("gate") != "SHOT_PROVEN":
        raise OwnerAmbiguityGate("CONTINUITY_SOURCE_SHOT_NOT_PROVEN")
    asset_payload = prior_result["asset"]
    from film_pipeline.live_runtime import Asset, file_sha256
    source_asset = Asset.model_validate(asset_payload)
    if file_sha256(Path(source_asset.uri_or_path)) != source_asset.sha256:
        raise OwnerAmbiguityGate("CONTINUITY_SOURCE_BYTES_CHANGED")
    frame = extract_last_frame(Path(source_asset.uri_or_path),
                               SCENE_DIR / "continuity" / f"frame_{shot_id}.png")
    from film_pipeline.live_runtime import Asset as AssetModel
    frame_asset = AssetModel(
        asset_id="asset_" + sha256({"origin": "reference",
            "kind": "last_frame", "from_shot": from_shot,
            "for_shot": shot_id, "sha256": frame["sha256"]}),
        origin="reference", asset_type="image",
        uri_or_path=frame["path"], sha256=frame["sha256"],
        mime_type="image/png", width=frame["width"], height=frame["height"],
        file_size=frame["file_size"],
        rights_metadata={"source_kind": "last_frame_of_acquired_asset",
                         "from_shot": from_shot, "for_shot": shot_id,
                         "source_asset_sha256": source_asset.sha256})
    # Dedicated single-upload store (the upload store is single-reservation
    # by design; MAX_CONTINUITY_UPLOADS = 2 → at most two dedicated stores).
    upload_store_path = SCENE_DIR / f"continuity_upload_{len(ledger['bindings']) + 1}.sqlite"
    upload_store = SQLiteStore(upload_store_path)
    upload_store.initialize()
    upload_store.save_reference_asset(frame_asset)
    ledger["uploads"] = ledger.get("uploads", [])
    write_durable(SCENE_DIR / f"continuity_frame_{shot_id}.json", frame)
    write_durable(upload_store_path.parent / "frame_asset.json",
                  frame_asset.model_dump(mode="json"))
    binding = None
    try:
        with open_read_session() as session:
            from film_pipeline.providers.flow_reference_upload import (
                ReferenceUploadStore)
            transport = FlowReferenceTransport(
                ReferenceUploadStore(upload_store_path), session,
                account_id=ACCOUNT_ID,
                evidence_dir=upload_store_path.parent / "continuity_evidence",
                interval_s=0, probes=2)
            receipt = transport.ensure_verified(frame_asset)
            uploaded_media_id = receipt["media_id"]
            # Independent attestation: fresh readback against the verified
            # upload receipt (same immutable chain as the canonical reference).
            attestation = attest_existing_reference(
                upload_store, frame_asset, session, account_id=ACCOUNT_ID,
                media_id=uploaded_media_id,
                evidence_dir=upload_store_path.parent / "continuity_evidence")
            # Read-only adoption into the scene store for the runtime.
            adopted_asset, adopted_attestation = adopt_existing_reference(
                store, session, account_id=ACCOUNT_ID, media_id=uploaded_media_id,
                reference_dir=SCENE_DIR / "continuity_reference")
    except OwnerAuthRequired as exc:
        raise OwnerAmbiguityGate(f"OWNER_AUTH_GATE: {exc}")
    binding = {"for_shot": shot_id, "from_shot": from_shot,
               "frame_sha256": frame["sha256"],
               "frame_asset_id": frame_asset.asset_id,
               "upload_store": str(upload_store_path),
               "upload_receipt_id": receipt["id"],
               "provider_media_id": uploaded_media_id,
               "provider_media_sha256": receipt["provider_media_sha256"],
               "attestation_id": attestation["attestation_id"],
               "adopted_asset_id": adopted_asset.asset_id,
               "adopted_attestation_id": adopted_attestation["attestation_id"],
               "at": now()}
    ledger["bindings"].append(binding)
    ledger["uploads"].append({"for_shot": shot_id, "media_id": uploaded_media_id,
                              "at": binding["at"]})
    (SCENE_DIR / "continuity_ledger.json").write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return binding


def run_scene_shot(shot: dict, state_dir: Path, scene_state: dict) -> dict:
    """Execute ONE planned shot through the proven per-shot runtime."""
    from mutation_authority import MutationAuthority

    tag = shot["shot_id"]
    shot_dir = Path(state_dir) / f"shot_{tag}"
    shot_dir.mkdir(parents=True, exist_ok=True)
    result_path = shot_dir / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))
    # The Owner ambiguity latch gates EVERY mutation path of this scope.
    authority = MutationAuthority(SCENE_DIR, "FLOW-SCENE-SCALE-003")
    authority.check_mutation_allowed("primary_generate")
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    ledger_data = ledger()
    report = {"shot_id": tag, "gate": "OWNER_GATE_LOCAL_FAILURE",
              "generate_clicks": 0, "observed_generate_requests": 0,
              "continuity": shot["continuity"]}
    frozen = None
    try:
        runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID,
                                     account_id=ACCOUNT_ID, model=MODEL)
        binding = reference_binding_for(shot)
        attestation = json.loads(_attestation_path(binding).read_text(encoding="utf-8"))
        # ---- freeze + reserve (headless reads) ----
        with open_read_session() as session:
            capability = qualify_flow_catalog_source(session)
            spec = load_shot(ROOT / shot["fixture"])
            spec = spec.model_copy(update={
                "references": References(other_asset_ids=[binding["asset_id"]])})
            frozen = runtime.freeze(spec, flow_capabilities(),
                reference_asset=store.read_reference_asset(binding["asset_id"]),
                reference_media_id=binding["media_id"],
                reference_filename="",
                catalog_source=capability, started_at=utc_now())
            job_id = frozen.job.provider_job_id
            prompt = frozen.job.correlation_evidence["prompt"]
            report["provider_job_id"] = job_id
            write_durable(shot_dir / "frozen_intent.json", {
                "shot_id": tag, "provider_job_id": job_id,
                "generation_attempt_id": frozen.attempt.generation_attempt_id,
                "prompt": prompt, "prompt_sha256": sha256(prompt),
                "correlation_marker": frozen.job.correlation_evidence["correlation_marker"],
                "continuity": binding,
                "pre_dispatch_snapshot": frozen.job.pre_dispatch_snapshot})
            already_consumed = bool(store.read_provider_job(job_id).dispatch_count)
            if not already_consumed:
                primary = not tag.startswith("REPAIR_")
                budget_key = "primary_consumed" if primary else "repair_consumed"
                used = len(ledger_data[budget_key])
                cap = MAX_PRIMARY_GENERATES if primary else MAX_REPAIR_GENERATES
                if used >= cap:
                    raise OwnerAmbiguityGate(f"{budget_key.upper()}_BUDGET_EXHAUSTED")
                write_durable(SCENE_DIR / f"preclaim_{tag}.json", {
                    "shot_id": tag, "provider_job_id": job_id,
                    "budget_kind": budget_key, "used": used, "cap": cap})
                runtime.reserve(frozen, attestation=attestation,
                                evidence_dir=_attestation_dir(binding))
            records = session.catalog(
                contract_version=contract.CONTRACT_VERSION_2026_10_01)
            if not already_consumed and sorted(
                    row[0].lower() for row in records) != \
                    frozen.job.pre_dispatch_snapshot["catalog_ids"]:
                raise OwnerAmbiguityGate("BASELINE_CHANGED_BEFORE_UI_PREPARATION")
        if already_consumed:
            report["resume_read_only"] = True
        else:
            # ---- headful release: ONE guard-qualified Generate ----
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
                                            media_id=binding["media_id"],
                                            prompt=prompt)
                    except Exception:
                        page.screenshot(path=str(
                            shot_dir / "ui_prepare_failure.png"))
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
                    verify_chip(page, binding["media_id"])
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
                    primary = not tag.startswith("REPAIR_")
                    budget_key = "primary_consumed" if primary else "repair_consumed"
                    ledger_data[budget_key].append({
                        "shot_id": tag, "provider_job_id": job_id,
                        "released_at": utc_now(),
                        "note": "Generate authority consumed; never retry authority."})
                    save_ledger(ledger_data)
                    report["gate"] = "OWNER_AMBIGUITY_GATE"
                    end = time.monotonic() + 30
                    while "status" not in response_holder and \
                            time.monotonic() < end:
                        page.wait_for_timeout(250)
                    report["provider_response"] = response_holder
                    page.screenshot(path=str(shot_dir / "post_release.png"))
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
            destination_dir=shot_dir / "videos", media_payload=payload)
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
        report["gate"] = "SHOT_PROVEN"
    except OwnerAuthRequired as exc:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
        report["diagnostic"] = str(exc)
    except OwnerAmbiguityGate as exc:
        report["diagnostic"] = str(exc)
        if report.get("observed_generate_requests"):
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            authority.latch("GENERATE_AMBIGUITY", str(exc))
            try:
                store.record_dispatch_fact(frozen.job.provider_job_id,
                    "AMBIGUOUS_EVIDENCE", {"diagnostic": "scene_owner_gate"})
            except Exception:
                pass
        else:
            report["gate"] = "OWNER_GATE: " + str(exc)
    except Exception as exc:  # noqa: BLE001
        report["diagnostic"] = f"{type(exc).__name__}: {exc}"[:400]
        if report.get("observed_generate_requests"):
            report["gate"] = "OWNER_AMBIGUITY_GATE"
        else:
            report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
    write_durable(result_path, report)
    print(json.dumps({"shot_id": tag, "gate": report["gate"],
                      "output": report.get("output_identity")}), flush=True)
    return report


def _attestation_dir(binding: dict) -> Path:
    if binding["mechanism"] == "same_reference":
        return (ROOT / "projects/flow_production_harden_002/"
                "requal_current_build/reference/attestation")
    return SCENE_DIR / "continuity_reference" / "attestation"


def _attestation_path(binding: dict) -> Path:
    return _attestation_dir(binding) / (binding["attestation_id"] + ".json")


def continuity_reconcile(shot_id: str) -> dict:
    """Read-only continuation for an armed-but-unresolved continuity upload.

    The upload external effect may exist (REQUEST_ARMED + HTTP 200 observed).
    The sanctioned recovery is bounded read-only catalog reconciliation:
    probe every qualified image row, require a UNIQUE strong content match
    across two stable probes, then verify by exact readback. Never a
    re-upload. If the bounded probes cannot uniquely resolve the identity,
    the OWNER_AMBIGUITY_GATE stands and mutations stop."""
    ledger_path = SCENE_DIR / "continuity_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))         if ledger_path.exists() else {"bindings": [], "uploads": []}
    from film_pipeline.providers.flow_reference_upload import (
        ReferenceUploadStore, _key)
    from film_pipeline.live_runtime import Asset
    frame_result = json.loads((SCENE_DIR / f"continuity_frame_{shot_id}.json")
                              .read_text(encoding="utf-8"))
    frame_asset = Asset.model_validate(json.loads(
        (SCENE_DIR / "frame_asset.json").read_text(encoding="utf-8")))
    # Locate the armed reservation store for this frame asset (the failed
    # upload may predate the ledger entry; the dedicated store binds it).
    candidates = sorted(SCENE_DIR.glob("continuity_upload_*.sqlite"))
    upload_store_path = None
    for candidate in candidates:
        reservations = ReferenceUploadStore(candidate).events(
            _key('flow_veo', PROJECT_ID, ACCOUNT_ID, frame_asset))
        if reservations:
            upload_store_path = candidate
            break
    if upload_store_path is None:
        raise SystemExit("no armed continuity reservation for this frame asset")
    upload_store = SQLiteStore(upload_store_path)
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    # Rows durably proven to pre-exist the upload (the frozen pre-dispatch
    # baseline of the scene's first shot) cannot be the uploaded media, so a
    # permanently unreadable baseline row must not block unique matching.
    shot1 = json.loads((SCENE_DIR / "shot_SCENE003_SHOT_1" / "frozen_intent.json")
                       .read_text(encoding="utf-8"))
    preexisting_ids = set(shot1["pre_dispatch_snapshot"]["catalog_ids"])
    attempts = 0
    resolved = None
    window = time.monotonic() + 420
    while time.monotonic() < window and resolved is None:
        attempts += 1
        try:
            with open_read_session() as session:
                transport = FlowReferenceTransport(
                    ReferenceUploadStore(upload_store_path), session,
                    account_id=ACCOUNT_ID,
                    evidence_dir=upload_store_path.parent / "continuity_evidence",
                    interval_s=5, probes=2)
                resolved = transport.reconcile_only(frame_asset,
                                                    preexisting_ids=preexisting_ids)
        except OwnerAmbiguityGate as exc:
            message = str(exc)
            print(json.dumps({"stage": "continuity_reconcile_pending",
                              "attempt": attempts, "diagnostic": message}),
                  flush=True)
            if "multiple strong" in message:
                raise
            time.sleep(30.0)
        except FlowReferenceRpcDrift as exc:
            print(json.dumps({"stage": "continuity_reconcile_read_drift",
                              "attempt": attempts, "diagnostic": str(exc)}),
                  flush=True)
            time.sleep(30.0)
    if resolved is None:
        raise OwnerAmbiguityGate(
            "OWNER_AMBIGUITY_GATE: continuity upload identity unresolved "
            "after bounded read-only reconciliation; no re-upload")
    uploaded_media_id = resolved["media_id"]
    with open_read_session() as session:
        attestation = attest_existing_reference(
            upload_store, frame_asset, session, account_id=ACCOUNT_ID,
            media_id=uploaded_media_id,
            evidence_dir=upload_store_path.parent / "continuity_evidence")
        adopted_asset, adopted_attestation = adopt_existing_reference(
            store, session, account_id=ACCOUNT_ID, media_id=uploaded_media_id,
            reference_dir=SCENE_DIR / "continuity_reference")
    binding = {"for_shot": shot_id,
               "frame_sha256": frame_result["sha256"],
               "frame_asset_id": frame_asset.asset_id,
               "upload_store": str(upload_store_path),
               "upload_receipt_id": resolved["id"],
               "provider_media_id": uploaded_media_id,
               "provider_media_sha256": resolved["provider_media_sha256"],
               "attestation_id": attestation["attestation_id"],
               "adopted_asset_id": adopted_asset.asset_id,
               "adopted_attestation_id": adopted_attestation["attestation_id"],
               "reconciled": True, "at": now()}
    ledger["bindings"].append(binding)
    ledger["uploads"].append({"for_shot": shot_id,
                              "media_id": uploaded_media_id, "at": binding["at"]})
    (SCENE_DIR / "continuity_ledger.json").write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"stage": "continuity_reconciled",
                      "provider_media_id": uploaded_media_id}), flush=True)
    return binding


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command",
                        choices=["plan", "scene", "continuity",
                                 "continuity-reconcile", "status"])
    parser.add_argument("--plan", default=str(ROOT / "fixtures/scene003/scene_plan_003.json"))
    parser.add_argument("--shot")
    parser.add_argument("--from-shot")
    args = parser.parse_args()
    plan = scene_runner.load_plan(Path(args.plan))
    if args.command == "plan":
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    elif args.command == "status":
        print(json.dumps(scene_runner.SceneState(SCENE_DIR)._state,
                         indent=2, ensure_ascii=False))
    elif args.command == "continuity":
        if not args.shot or not args.from_shot:
            raise SystemExit("continuity requires --shot and --from-shot")
        print(json.dumps(continuity_upload(args.shot, args.from_shot),
                         ensure_ascii=False))
    elif args.command == "continuity-reconcile":
        if not args.shot:
            raise SystemExit("continuity-reconcile requires --shot")
        print(json.dumps(continuity_reconcile(args.shot), ensure_ascii=False))
    elif args.command == "scene":
        result = scene_runner.execute_scene(plan, SCENE_DIR, run_scene_shot)
        print(json.dumps({k: result[k] for k in ("scene_id", "proven", "total",
                                                 "scene_complete")}), flush=True)


if __name__ == "__main__":
    main()
