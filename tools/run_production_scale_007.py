"""FLOW-PRODUCTION-SCALE-007 — large-scale production-run runner.

RUN007_FLOW_SWORDSMAN_SCALE through the full proven chain:

    scale_run.execute_scale_run
    → production_run.execute_production_run
    → sequence_runner / scene_runner
    → per-shot Flow native-UI runtime chain

Slots:
- SEQ004_SWORDSMAN_DESCENT  (ADOPTED, read-only, 10 proven shots, P-004);
- SEQ005_VALLEY_STREAM      (ADOPTED, read-only,  8 proven shots, P-005);
- SEQ007_DAYLIGHT_ROAD      (LIVE, 3 scenes × 4 shots = 12 required slots).

Budgets: MAX_PRIMARY_GENERATES = 12, MAX_REPAIR_GENERATES = 3,
MAX_CONTINUITY_UPLOADS = 2 (hard ceiling 15 generates; unused authority is
never retry authority). Every Generate: unique durable ProviderJob,
immutable intent, exact reference, fresh backend baseline, at-most-once
release, exact marker attribution, may_submit=false forever after
consumption. Any ambiguity → OWNER_AMBIGUITY_GATE → durable latch for the
whole execution scope (tools/mutation_authority.py semantics).

Continuity: same-reference default; the two frozen within-scene last-frame
slots (SEQ7_F2 ← SEQ7_F1, SEQ7_G2 ← SEQ7_G1) each consume exactly one
budgeted upload through the proven upload/attestation/adoption chain.
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

from film_pipeline.core import References, load_shot, sha256
from film_pipeline.flow_r2v_runtime import (
    FlowR2VShotRuntime,
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

import production_run
import scale_run
import scene_runner
from mutation_authority import MutationAuthority
from run_scene_scale_003 import (
    flow_capabilities,
    poll_media,
    verify_full_decode,
)

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "projects/flow_production_scale_007"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
PLAN_C = ROOT / "fixtures/sequence007/sequence_plan_007.json"
SEQ004_STATE = ROOT / "projects/flow_multiscene_004/sequence_state.json"
SEQ005_DIR = ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM"
BASE_REFERENCE = json.loads(
    (ROOT / "projects/flow_production_harden_002/requal_current_build/"
     "reference_binding.json").read_text(encoding="utf-8"))
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
RUN_ID = "RUN007_FLOW_SWORDSMAN_SCALE"
SCOPE_ID = "FLOW-PRODUCTION-SCALE-007"
MODEL = contract.MODEL_VEO_3_1_LITE
MAX_PRIMARY_GENERATES = 12
MAX_REPAIR_GENERATES = 3
MAX_CONTINUITY_UPLOADS = 2
OBSERVATION_WINDOW_S = 2400
POLL_INTERVAL_S = 60
RELEASE_WAIT_S = 45
MUTATION_ROUTE = "**/batchexecute?*"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"
BASE_ATTESTATION_DIR = (ROOT / "projects/flow_production_harden_002/"
                        "requal_current_build/reference/attestation")


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
    return MutationAuthority(RUN_DIR, SCOPE_ID)


def ledger() -> dict:
    path = RUN_DIR / "generate_ledger.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"initialized_at": now(), "max_primary": MAX_PRIMARY_GENERATES,
            "max_repair": MAX_REPAIR_GENERATES,
            "max_uploads": MAX_CONTINUITY_UPLOADS,
            "primary_consumed": [], "repair_consumed": [], "uploads": []}


def save_ledger(data: dict) -> None:
    path = RUN_DIR / "generate_ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def open_read_session():
    return FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                   project_id=PROJECT_ID, native_ui=True)


class PreFetchedTransport:
    def __init__(self, data: bytes, output_id: str):
        self.data = data
        self.output_id = output_id

    async def fetch(self, job, output_id, destination):
        if output_id != self.output_id:
            raise OwnerAmbiguityGate("ACQUISITION_OUTPUT_IDENTITY_MISMATCH")
        destination.write_bytes(self.data)
        return destination


# ---------------------------------------------------------------------------
# Adopted-sequence loaders (read-only; two durable historical layouts)
# ---------------------------------------------------------------------------

def adopted_loader_dispatch(state_ref: Path) -> dict:
    """Read-only adoption for both historical layouts:
    - sequence-state-v1 file (SEQ004; tools/production_run semantics);
    - sequence run directory holding run_result.json (SEQ005 production-run
      layout: run_result.json + per-scene shot results + parent run state)."""
    from production_run import adopted_sequence_snapshot
    state_ref = Path(state_ref)
    if state_ref.is_file():
        return adopted_sequence_snapshot(state_ref)
    run_result_path = state_ref / "run_result.json"
    if not run_result_path.is_file():
        raise ValueError(f"adopted sequence state missing: {state_ref}")
    run_result = json.loads(run_result_path.read_text(encoding="utf-8"))
    if run_result.get("complete") is not True:
        raise ValueError("adopted sequence run_result not complete")
    sequence_id = run_result["sequence_id"]
    parent_state = state_ref.parent / "production_run_state.json"
    if parent_state.is_file():
        parent = json.loads(parent_state.read_text(encoding="utf-8"))
        status = parent.get("sequences", {}).get(sequence_id, {}).get("status")
        if status != "PROVEN":
            raise ValueError(
                f"adopted sequence {sequence_id} not PROVEN in run state")
    shots = {}
    for result_path in sorted(state_ref.glob("scene_*/shot_*/result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        shot_id = result.get("shot_id")
        if result.get("gate") not in ("SHOT_PROVEN", "R3_SHOT3_REPROOF_PROVEN"):
            raise ValueError(f"adopted shot {shot_id} not proven")
        if shot_id in shots:
            raise ValueError(f"duplicate adopted shot {shot_id}")
        asset = result.get("asset", {})
        if not asset.get("sha256"):
            raise ValueError(f"adopted shot {shot_id} asset hash missing")
        shots[shot_id] = {"scene_id": result_path.parent.parent.name[
            len("scene_"):],
            "asset_sha256": asset["sha256"],
            "provider_media_id": result.get("output_identity"),
            "selected_take_source": "historical_proven"}
    if not shots:
        raise ValueError("adopted sequence has no proven shots")
    return {"sequence_id": sequence_id, "shots": shots}


# ---------------------------------------------------------------------------
# Continuity (per-scene, budgeted, proven upload chain)
# ---------------------------------------------------------------------------

def _continuity_ledger_path(scene_dir: Path) -> Path:
    return Path(scene_dir) / "continuity_ledger.json"


def extract_last_frame(asset_path: Path, destination: Path) -> dict:
    import subprocess
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
    return {"path": str(destination),
            "sha256": __import__("hashlib").sha256(data).hexdigest(),
            "width": width, "height": height, "file_size": len(data),
            "source_asset": str(asset_path)}


def continuity_upload(scene_dir: Path, shot_id: str, from_shot: str) -> dict:
    """ONE durable last-frame continuity upload for a frozen transition.

    Chain: acquired from-shot Asset → deterministic final-frame extraction →
    registered local Asset → durable upload reservation → ONE transport POST
    → unique provider identity → readback attestation → read-only adoption
    into the scene store. Budget + Owner latch enforced. Idempotent via the
    scene continuity ledger; never a re-upload.
    """
    ledger_path = _continuity_ledger_path(scene_dir)
    ledger_data = json.loads(ledger_path.read_text(encoding="utf-8")) \
        if ledger_path.exists() else {"bindings": [], "uploads": []}
    existing = [e for e in ledger_data["bindings"] if e["for_shot"] == shot_id]
    if existing:
        return existing[0]
    if len(ledger_data["bindings"]) >= MAX_CONTINUITY_UPLOADS:
        raise OwnerAmbiguityGate("CONTINUITY_UPLOAD_BUDGET_EXHAUSTED")
    auth = authority()
    auth.check_mutation_allowed("continuity_upload")
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    prior_result = json.loads(
        (Path(scene_dir) / f"shot_{from_shot}" / "result.json")
        .read_text(encoding="utf-8"))
    if prior_result.get("gate") != "SHOT_PROVEN":
        raise OwnerAmbiguityGate("CONTINUITY_SOURCE_SHOT_NOT_PROVEN")
    from film_pipeline.live_runtime import Asset, file_sha256
    source_asset = Asset.model_validate(prior_result["asset"])
    if file_sha256(Path(source_asset.uri_or_path)) != source_asset.sha256:
        raise OwnerAmbiguityGate("CONTINUITY_SOURCE_BYTES_CHANGED")
    frame = extract_last_frame(
        Path(source_asset.uri_or_path),
        Path(scene_dir) / "continuity" / f"frame_{shot_id}.png")
    frame_asset = Asset(
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
    upload_store_path = Path(scene_dir) / \
        f"continuity_upload_{len(ledger_data['bindings']) + 1}.sqlite"
    upload_store = SQLiteStore(upload_store_path)
    upload_store.initialize()
    upload_store.save_reference_asset(frame_asset)
    ledger_data["uploads"] = ledger_data.get("uploads", [])
    write_durable(Path(scene_dir) / f"continuity_frame_{shot_id}.json", frame)
    receipt = None
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
        attestation = attest_existing_reference(
            upload_store, frame_asset, session, account_id=ACCOUNT_ID,
            media_id=uploaded_media_id,
            evidence_dir=upload_store_path.parent / "continuity_evidence")
        adopted_asset, adopted_attestation = adopt_existing_reference(
            store, session, account_id=ACCOUNT_ID, media_id=uploaded_media_id,
            reference_dir=Path(scene_dir) / "continuity_reference")
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
    ledger_data["bindings"].append(binding)
    ledger_data["uploads"].append({"for_shot": shot_id,
                                   "media_id": uploaded_media_id,
                                   "at": binding["at"]})
    ledger_path.write_text(json.dumps(ledger_data, indent=2,
                                      ensure_ascii=False), encoding="utf-8")
    ledger_data2 = ledger()
    ledger_data2["uploads"].append({"for_shot": shot_id,
                                    "media_id": uploaded_media_id,
                                    "scene": Path(scene_dir).name,
                                    "at": binding["at"]})
    save_ledger(ledger_data2)
    auth.consume("continuity_upload")
    return binding


def reference_binding_for(shot: dict, scene_dir: Path) -> dict:
    """Resolve the frozen continuity binding for one planned shot.

    Last-frame bindings lazily trigger their ONE budgeted upload on first
    need (idempotent via the scene continuity ledger; never a re-upload)."""
    kind = shot["continuity"]["kind"]
    if kind == "reference":
        return {"media_id": BASE_REFERENCE["media_id"],
                "asset_id": BASE_REFERENCE["asset_id"],
                "attestation_id": BASE_REFERENCE["attestation_id"],
                "mechanism": "same_reference"}
    if kind == "last_frame":
        ledger_path = _continuity_ledger_path(scene_dir)
        entries = json.loads(ledger_path.read_text(encoding="utf-8"))[
            "bindings"] if ledger_path.exists() else []
        binding_for = shot["continuity"].get("binding_for", shot["shot_id"])
        from_shot = shot["continuity"]["from_shot"]
        matches = [e for e in entries if e["for_shot"] == binding_for]
        if len(matches) > 1:
            raise OwnerAmbiguityGate(
                f"CONTINUITY_BINDING_AMBIGUOUS for {shot['shot_id']}")
        if not matches:
            continuity_upload(scene_dir, shot_id, from_shot)
            entries = json.loads(ledger_path.read_text(encoding="utf-8"))[
                "bindings"]
            matches = [e for e in entries if e["for_shot"] == binding_for]
            if len(matches) != 1:
                raise OwnerAmbiguityGate(
                    f"CONTINUITY_BINDING_MISSING for {shot['shot_id']}")
        entry = matches[0]
        return {"media_id": entry["provider_media_id"],
                "asset_id": entry["adopted_asset_id"],
                "attestation_id": entry["adopted_attestation_id"],
                "mechanism": "last_frame",
                "from_shot": from_shot,
                "source_frame_sha256": entry["frame_sha256"],
                "upload_store": entry["upload_store"],
                "upload_attestation_id": entry["attestation_id"]}
    raise OwnerAmbiguityGate("CONTINUITY_KIND_UNQUALIFIED")


# ---------------------------------------------------------------------------
# Per-shot live execution (the proven native-UI chain)
# ---------------------------------------------------------------------------

def run_live_shot(shot: dict, state_dir: Path, scene_state: dict) -> dict:
    """ONE live shot: freeze → baseline → reserve → attested reference →
    headful native UI → ONE Generate → reconcile → render lifecycle →
    acquire → decode → durable result. Restart-safe: a durable result short-
    circuits; consumed authority is never re-released."""
    tag = shot["shot_id"]
    scene_dir = Path(state_dir)
    shot_dir = scene_dir / f"shot_{tag}"
    shot_dir.mkdir(parents=True, exist_ok=True)
    result_path = shot_dir / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))
    auth = authority()
    auth.check_mutation_allowed("primary_generate")
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    ledger_data = ledger()
    report = {"shot_id": tag, "gate": "OWNER_GATE_LOCAL_FAILURE",
              "generate_clicks": 0, "observed_generate_requests": 0,
              "continuity": shot["continuity"],
              "editorial_target_duration":
                  shot.get("editorial_target_duration")}
    frozen = None
    already_consumed = False
    started = utc_now()
    try:
        binding = reference_binding_for(shot, scene_dir)
        if binding["mechanism"] == "same_reference":
            attestation = json.loads(
                (BASE_ATTESTATION_DIR /
                 (binding["attestation_id"] + ".json")).read_text(
                     encoding="utf-8"))
        else:
            attestation = json.loads(
                (scene_dir / "continuity_reference" / "attestation" /
                 (binding["attestation_id"] + ".json")).read_text(
                     encoding="utf-8"))
        runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID,
                                     account_id=ACCOUNT_ID, model=MODEL)
        with open_read_session() as session:
            capability = qualify_flow_catalog_source(session)
            spec = load_shot(ROOT / shot["fixture"])
            spec = spec.model_copy(update={
                "references": References(other_asset_ids=[binding["asset_id"]])})
            frozen = runtime.freeze(spec, flow_capabilities(),
                reference_asset=store.read_reference_asset(binding["asset_id"]),
                reference_media_id=binding["media_id"],
                reference_filename="",
                catalog_source=capability, started_at=started)
            job_id = frozen.job.provider_job_id
            prompt = frozen.job.correlation_evidence["prompt"]
            report["provider_job_id"] = job_id
            write_durable(shot_dir / "frozen_intent.json", {
                "shot_id": tag, "provider_job_id": job_id,
                "prompt_sha256": sha256(prompt),
                "correlation_marker":
                    frozen.job.correlation_evidence["correlation_marker"],
                "continuity": binding,
                "editorial_target_duration":
                    shot.get("editorial_target_duration"),
                "pre_dispatch_snapshot": frozen.job.pre_dispatch_snapshot})
            already_consumed = bool(
                store.read_provider_job(job_id).dispatch_count)
            if not already_consumed:
                auth.check_mutation_allowed("primary_generate")
                primary = not tag.startswith("REPAIR_")
                budget_key = "primary_consumed" if primary \
                    else "repair_consumed"
                cap = MAX_PRIMARY_GENERATES if primary \
                    else MAX_REPAIR_GENERATES
                if len(ledger_data[budget_key]) >= cap:
                    raise OwnerAmbiguityGate(
                        ("PRIMARY" if primary else "REPAIR") +
                        "_BUDGET_EXHAUSTED")
                runtime.reserve(frozen, attestation=attestation,
                                evidence_dir=BASE_ATTESTATION_DIR
                                if binding["mechanism"] == "same_reference"
                                else scene_dir / "continuity_reference" /
                                "attestation")
            records = session.catalog(
                contract_version=contract.CONTRACT_VERSION_2026_10_01)
            if not already_consumed and sorted(
                    row[0].lower() for row in records) != \
                    frozen.job.pre_dispatch_snapshot["catalog_ids"]:
                raise OwnerAmbiguityGate(
                    "BASELINE_CHANGED_BEFORE_UI_PREPARATION")
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
                                            media_id=binding["media_id"],
                                            prompt=prompt)
                    except Exception:
                        page.screenshot(path=str(shot_dir /
                                                 "ui_prepare_failure.png"))
                        raise
                    report["ui_preflight"] = ui
                    response_holder = {}

                    def on_response(response):
                        if "MZZa6b" not in response.url or \
                                "status" in response_holder:
                            return
                        try:
                            body = response.text()
                        except Exception:
                            body = ""
                        response_holder["status"] = response.status
                        response_holder["byte_length"] = \
                            len(body.encode("utf-8"))
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
                        raise OwnerAmbiguityGate(
                            "PROMPT_CHANGED_AT_MUTATION_BOUNDARY")
                    store.record_dispatch_fact(job_id, "PROMPT_VERIFIED",
                                               {"prompt_sha256": sha256(prompt)})
                    store.record_dispatch_fact(job_id, "CLICK_ARMED", {})
                    guard.armed = True
                    report["generate_clicks"] = 1
                    page.locator("button.generate-icon-button").click(
                        timeout=15000)
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
                        raise OwnerAmbiguityGate(
                            "EXACT_NATIVE_REQUEST_NOT_OBSERVED")
                    ledger_data[budget_key_of(tag)].append({
                        "shot_id": tag, "provider_job_id": job_id,
                        "released_at": utc_now(),
                        "note": "Generate authority consumed; never retry "
                                "authority."})
                    save_ledger(ledger_data)
                    auth.consume(budget_key_of(tag))
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
                runtime.observe_provider_response(
                    frozen, status=report["provider_response"]["status"])
                counts = (report["provider_response"].get("diagnostics")
                          or {}).get("type_counts") or {}
                if any(count for key, count in counts.items()
                       if key != "null"):
                    runtime.observe_provider_acceptance(
                        frozen, provider_reference="MZZa6b_wire_ack")
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
                        output_id = runtime.attribute_backend_output(
                            frozen, records)
                    except contract.ContractError as exc:
                        if str(exc) == "OUTPUT_STATUS_UNQUALIFIED":
                            continue
                        raise OwnerAmbiguityGate(
                            "BACKEND_ATTRIBUTION_MATERIAL_DISAGREEMENT: "
                            + str(exc))
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
                                            project_id=PROJECT_ID,
                                            kind="video")
            media = session.bound_media(output_id, "video")
        asset = runtime.acquire(
            frozen, transport=PreFetchedTransport(media.data, output_id),
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
            auth.latch("GENERATE_AMBIGUITY", str(exc))
            try:
                store.record_dispatch_fact(frozen.job.provider_job_id,
                    "AMBIGUOUS_EVIDENCE", {"diagnostic": SCOPE_ID})
            except Exception:
                pass
        else:
            report["gate"] = "OWNER_GATE: " + str(exc)
    except Exception as exc:  # noqa: BLE001
        report["diagnostic"] = f"{type(exc).__name__}: {exc}"[:400]
        if report.get("observed_generate_requests"):
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            auth.latch("GENERATE_AMBIGUITY", str(exc))
        else:
            report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
    write_durable(result_path, report)
    print(json.dumps({"shot_id": tag, "gate": report["gate"],
                      "output": report.get("output_identity")}), flush=True)
    return report


def budget_key_of(shot_id: str) -> str:
    return "repair_consumed" if shot_id.startswith("REPAIR_") \
        else "primary_consumed"


def run_live_sequence(entry, state_dir: Path) -> dict:
    """Execute every scene of the frozen live plan via the scene chain."""
    plan = json.loads(Path(entry["plan_ref"]).read_text(encoding="utf-8"))
    scene_results = []
    for scene in plan["scenes"]:
        scene_state = Path(state_dir) / f"scene_{scene['scene_id']}"
        scene_result = scene_runner.execute_scene(
            {"scene_id": scene["scene_id"], "shots": scene["shots"]},
            scene_state, run_live_shot)
        scene_results.append(scene_result)
    return {"sequence_id": entry["sequence_id"],
            "complete": all(r.get("scene_complete") for r in scene_results),
            "scenes": [{"scene_id": r.get("scene_id"),
                        "scene_complete": r.get("scene_complete")}
                       for r in scene_results]}


def scale_plan() -> dict:
    plan_c = json.loads(PLAN_C.read_text(encoding="utf-8"))
    return {"run_id": RUN_ID, "project_id": "ai_film_run007_swordsman_scale",
            "sequences": [
                {"sequence_id": "SEQ004_SWORDSMAN_DESCENT",
                 "mode": "adopted", "state_ref": str(SEQ004_STATE)},
                {"sequence_id": "SEQ005_VALLEY_STREAM",
                 "mode": "adopted", "state_ref": str(SEQ005_DIR)},
                {"sequence_id": "SEQ007_DAYLIGHT_ROAD", "mode": "live",
                 "plan_ref": str(PLAN_C),
                 "media_scope": [BASE_REFERENCE["media_id"]],
                 "scenes": plan_c["scenes"]}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command",
                        choices=["run", "status", "preflight"])
    args = parser.parse_args()
    if args.command == "status":
        state_path = RUN_DIR / "scale_run_state.json"
        if state_path.exists():
            print(state_path.read_text(encoding="utf-8"))
        else:
            print(json.dumps({"run_id": RUN_ID, "started": False}))
        return
    if args.command == "preflight":
        with open_read_session() as session:
            capability = qualify_flow_catalog_source(session)
            records = session.catalog(
                contract_version=contract.CONTRACT_VERSION_2026_10_01)
            present = any(BASE_REFERENCE["media_id"] in
                          " ".join(contract._strings(r)) for r in records)
            print(json.dumps({"catalog_rows": len(records),
                              "model_ok": bool(capability),
                              "reference_media_present": present,
                              "authority": authority().authority}))
        return
    result = scale_run.execute_scale_run(
        scale_plan(), RUN_DIR, run_live_sequence,
        adopted_loader_dispatch, production_run.execute_production_run)
    print(json.dumps({k: result[k] for k in
                      ("run_id", "sequences_proven", "sequences_total",
                       "run_complete", "slot_count")}), flush=True)


if __name__ == "__main__":
    main()
