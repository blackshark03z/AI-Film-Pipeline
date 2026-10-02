"""FLOW-PRODUCTION-HARDEN-MULTISHOT-002 Phase 2 — current-build native requalification.

Frozen authority: MAX_NATIVE_REQUAL_GENERATE = 1 (never retry authority).

Re-qualifies the proven native-UI Flow generation route on the CURRENT
frontend/build in the exact forensics-qualified scope:

    provider   Google Flow / Veo
    profile    D:/AI FILM MAKER/Flow-Claude-Clean-Profile (clean, authenticated)
    project    93a579b4-834e-435b-8304-5f6682937935
    reference  7b725f7b-4da5-4455-a6f2-135c4ba22397 — the effective reference of
               the two proven 2026-10-02 native-UI generations, adopted into the
               Film registry through the READ-ONLY attested readback path (the
               historical run carried no upload receipt; adoption performs zero
               provider mutation)
    mode       Video → Ingredients (R2V), veo_3_1_r2v_lite, 16:9, 8s, x1

Lifecycle per SoT 13: preflight → current build fingerprint → fresh backend
baseline → durable ProviderJob/preclaim → exact reference attestation →
native UI prepare → ONE Generate → admission observation → backend reconcile →
render state → exact provider identity → as29s resolution → acquire → hash →
ffprobe → full decode EOF → QC eligibility.

Stages (durable, restart-safe, fail-closed):
  adopt      read-only reference adoption (idempotent)
  preflight  live read-only truths (catalog, reference row, settings, bundle)
  release    freeze → preclaim → attested reservation → headful native UI →
             exactly one browser-created Generate → wire observation;
             a crash after release never re-releases (resume with reconcile)
  reconcile  read-only continuation: bounded catalog reconciliation → unique
             attribution → marker echo → render state → as29s → exact
             acquisition → technical QC → restart/recovery proofs

Provider writes: the one native-UI Generate click only (guard-qualified).
Reads: Zzl0ze/as29s through the qualified session. No cookies/tokens/signed
URLs persisted. No upload. No direct MZZa6b mutation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from film_pipeline.core import ProviderCapabilities, References, canonical_json, load_shot, sha256
from film_pipeline.flow_r2v_runtime import (
    FlowR2VShotRuntime,
    qualify_flow_catalog_source,
)
from film_pipeline.live_runtime import LiveRuntimeExecutor, file_sha256, utc_now
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_canonical_ui import (
    DEFAULT_NATIVE_UI,
    prepare_inputs,
    verify_chip,
    verify_settings,
)
from film_pipeline.providers.flow_media import parse_media_resource
from film_pipeline.providers.flow_reference_binding import (
    adopt_existing_reference,
    verify_attestation,
)
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
    OwnerAuthRequired,
)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_r2v_prompt import MARKER_RE
from film_pipeline.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
MAX_MEDIA_BYTES = 256 * 1024 * 1024
MAX_NATIVE_REQUAL_GENERATE = 1

PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
REFERENCE_MEDIA_ID = "7b725f7b-4da5-4455-a6f2-135c4ba22397"
PROFILE = Path("D:/AI FILM MAKER/Flow-Claude-Clean-Profile")
MODEL = contract.MODEL_VEO_3_1_LITE
SHOT_ID = "FLOW_PRODUCTION_HARDEN_002_REQUAL"
STARTED_AT = "2026-10-02T12:00:00+00:00"

QUAL_DIR = ROOT / "projects/flow_production_harden_002/requal_current_build"
RELEASE_DIR = QUAL_DIR / "release"
REFERENCE_DIR = QUAL_DIR / "reference"
ATT_EVIDENCE = REFERENCE_DIR / "attestation"
DATABASE = QUAL_DIR / "runtime.sqlite"
LEDGER_DIR = QUAL_DIR / "ledger"
RELEASE_WAIT_S = 45
OBSERVATION_WINDOW_S = 2400
POLL_INTERVAL_S = 60
MUTATION_ROUTE = "**/batchexecute?*"


def write_new(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise OwnerAmbiguityGate(f"EVIDENCE_FILE_EXISTS: {path.name}")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_durable(path: Path, data) -> None:
    """Write-or-verify: idempotent durable evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, indent=2, ensure_ascii=False)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise OwnerAmbiguityGate(f"EVIDENCE_CONFLICT: {path.name}")
        return
    path.write_text(encoded, encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ledger_path() -> Path:
    return LEDGER_DIR / "requal_ledger.json"


def load_ledger() -> dict:
    path = ledger_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"initialized_at": now(), "max_generate": MAX_NATIVE_REQUAL_GENERATE,
            "consumed": []}


def save_ledger(ledger: dict) -> None:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")


def require_budget(n: int) -> None:
    ledger = load_ledger()
    if len(ledger["consumed"]) + n > ledger["max_generate"]:
        raise OwnerAmbiguityGate("GENERATE_BUDGET_EXHAUSTED")


def consume_budget(entry: dict) -> None:
    ledger = load_ledger()
    ledger["consumed"].append(entry)
    save_ledger(ledger)


def open_read_session() -> FlowReferenceRpcSession:
    if not PROFILE.is_dir():
        raise OwnerAmbiguityGate("qualified browser profile unavailable")
    return FlowReferenceRpcSession(profile_path=PROFILE, project_id=PROJECT_ID,
                                   native_ui=True)


def flow_capabilities() -> ProviderCapabilities:
    payload = {
        "profile_version": "flow-production-harden-002-requal-v1",
        "provider_id": "flow_veo",
        "transport_type": "other",
        "supports_text_to_video": True,
        "supports_image_input": True,
        "supports_duration_control": True,
    }
    from film_pipeline.core import validate_contract
    validate_contract("provider_capabilities", payload)
    return ProviderCapabilities.model_validate(payload)


def ordinary_shot():
    shot = load_shot(ROOT / "fixtures/flow_canary.json")
    reference_asset_id = json.loads((QUAL_DIR / "reference_binding.json")
                                    .read_text(encoding="utf-8"))["asset_id"]
    return shot.model_copy(update={
        "shot_id": SHOT_ID,
        "references": References(other_asset_ids=[reference_asset_id])})


# ------------------------------------------------------------------- adopt
def stage_adopt() -> dict:
    report_path = QUAL_DIR / "adopt.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["gate"] != "ADOPTED":
            raise OwnerAmbiguityGate("adoption did not previously pass")
        return report
    QUAL_DIR.mkdir(parents=True, exist_ok=True)
    report = {"stage": "ADOPT", "gate": "OWNER_GATE_LOCAL_FAILURE",
              "project_id": PROJECT_ID, "reference_media_id": REFERENCE_MEDIA_ID,
              "provider_mutations": 0}
    try:
        store = SQLiteStore(DATABASE)
        with open_read_session() as session:
            # Read-only adoption of the existing project media.
            catalog_before = {row[0].lower() for row in session.catalog()}
            if REFERENCE_MEDIA_ID.lower() not in catalog_before:
                raise OwnerAmbiguityGate("REFERENCE_MEDIA_NOT_IN_PROJECT_CATALOG")
            catalog_count = len(catalog_before)
            asset, attestation = adopt_existing_reference(
                store, session, account_id=ACCOUNT_ID, media_id=REFERENCE_MEDIA_ID,
                reference_dir=REFERENCE_DIR)
            # Adoption must not have changed provider state: same catalog.
            catalog_after = {row[0].lower() for row in session.catalog()}
            if catalog_after != catalog_before:
                raise OwnerAmbiguityGate("CATALOG_CHANGED_DURING_READ_ONLY_ADOPTION")
            report.update({
                "gate": "ADOPTED", "asset_id": asset.asset_id,
                "reference_sha256": asset.sha256,
                "attestation_id": attestation["attestation_id"],
                "catalog_count": catalog_count,
                "provider_mutations": 0,
                "note": "read-only attested readback adoption; zero provider mutation"})
            write_durable(QUAL_DIR / "reference_binding.json", {
                "asset_id": asset.asset_id, "media_id": REFERENCE_MEDIA_ID,
                "reference_sha256": asset.sha256,
                "attestation_id": attestation["attestation_id"],
                "account_id": ACCOUNT_ID, "project_id": PROJECT_ID})
    except OwnerAuthRequired:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
    except OwnerAmbiguityGate as exc:
        report["gate"] = "OWNER_GATE"
        report["diagnostic"] = str(exc)
    write_durable(report_path, report)
    print(json.dumps({"stage": "adopt", "gate": report["gate"]}), flush=True)
    if report["gate"] != "ADOPTED":
        raise SystemExit(1)
    return report


# --------------------------------------------------------------- preflight
def stage_preflight() -> dict:
    report_path = QUAL_DIR / "preflight.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["gate"] != "PREFLIGHT_PASS":
            raise OwnerAmbiguityGate("preflight did not previously pass")
        return report
    binding = json.loads((QUAL_DIR / "reference_binding.json").read_text(encoding="utf-8"))
    report = {"stage": "PREFLIGHT", "gate": "OWNER_GATE",
              "project_id": PROJECT_ID, "reference_media_id": REFERENCE_MEDIA_ID,
              "model": MODEL, "provider_reads": {}, "blocked_mutations": []}
    try:
        store = SQLiteStore(DATABASE)
        asset = store.read_reference_asset(binding["asset_id"])
        attestation = json.loads(
            (ATT_EVIDENCE / (binding["attestation_id"] + ".json")).read_text(encoding="utf-8"))
        verify_attestation(store, asset, attestation, media_id=REFERENCE_MEDIA_ID,
                           project_id=PROJECT_ID, evidence_dir=ATT_EVIDENCE)
        report["reference_chain"] = "verified_pre_session"
        with open_read_session() as session:
            meta = session.metadata()
            report["session_ready"] = True
            records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            report["provider_reads"]["catalog_current_parser"] = True
            report["catalog_ids"] = sorted(row[0].lower() for row in records)
            matches = [row for row in records
                       if row[0].lower() == REFERENCE_MEDIA_ID.lower()]
            if len(matches) != 1:
                raise OwnerAmbiguityGate("REFERENCE_ROW_NOT_UNIQUE_IN_CATALOG")
            strings = list(contract._strings(matches[0]))
            pngs = {s.rsplit("=", 1)[0].rsplit("/", 1)[-1] for s in strings
                    if ".png" in s.lower()}
            report["reference_row_strings_with_png"] = sorted(pngs)[:4]
            settings = session.page.locator("button.settings-trigger-button")
            report["settings_tokens"] = (settings.first.inner_text()
                                         if settings.count() else None)
            report["generate_button_present"] = bool(
                session.page.locator("button.generate-icon-button").count())
            scripts = session.page.evaluate(
                "() => Array.from(document.scripts).map(s => s.src)"
                ".filter(src => /boq-labs|ai-sandbox/.test(src)).slice(0, 4)")
            report["frontend_scripts"] = scripts
        report["gate"] = "PREFLIGHT_PASS"
    except OwnerAuthRequired:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
    except OwnerAmbiguityGate as exc:
        report["gate"] = "OWNER_GATE"
        report["diagnostic"] = str(exc)
    except FlowReferenceRpcDrift as exc:
        report["gate"] = "OWNER_GATE_READ_DRIFT"
        report["diagnostic"] = str(exc)
    write_durable(report_path, report)
    print(json.dumps({"stage": "preflight", "gate": report["gate"]}), flush=True)
    if report["gate"] != "PREFLIGHT_PASS":
        raise SystemExit(1)
    return report


# ----------------------------------------------------------------- release
def stage_release() -> dict:
    out_dir = RELEASE_DIR
    if (out_dir / "release_result.json").exists():
        raise OwnerAmbiguityGate("durable release result already recorded; no redispatch")
    require_budget(1)
    preflight = stage_preflight()
    store = SQLiteStore(DATABASE)
    binding = json.loads((QUAL_DIR / "reference_binding.json").read_text(encoding="utf-8"))
    runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID, account_id=ACCOUNT_ID,
                                 model=MODEL)
    report = {"stage": "RELEASE", "gate": "OWNER_GATE_LOCAL_FAILURE",
              "project_id": PROJECT_ID, "account_id": ACCOUNT_ID,
              "reference_media_id": REFERENCE_MEDIA_ID, "model": MODEL,
              "shot_id": SHOT_ID, "generate_clicks": 0,
              "observed_generate_requests": 0, "uploads": 0,
              "direct_mzza6b_submits": 0}
    job_id = None
    try:
        with open_read_session() as session:
            capability = qualify_flow_catalog_source(session)
            frozen = runtime.freeze(ordinary_shot(), flow_capabilities(),
                reference_asset=store.read_reference_asset(binding["asset_id"]),
                reference_media_id=REFERENCE_MEDIA_ID,
                reference_filename=preflight.get("provider_filename", ""),
                catalog_source=capability, started_at=STARTED_AT)
            job_id = frozen.job.provider_job_id
            prompt = frozen.job.correlation_evidence["prompt"]
            report.update(provider_job_id=job_id, provider_prompt=prompt,
                          pre_dispatch_snapshot=frozen.job.pre_dispatch_snapshot)
            write_new(out_dir / "frozen_intent.json", {
                "provider_job_id": job_id,
                "generation_attempt_id": frozen.attempt.generation_attempt_id,
                "prompt": prompt, "prompt_sha256": sha256(prompt),
                "correlation_marker": frozen.job.correlation_evidence["correlation_marker"],
                "prompt_compiler": frozen.job.correlation_evidence["provider_prompt_compiler"],
                "pre_dispatch_snapshot": frozen.job.pre_dispatch_snapshot})
            write_new(LEDGER_DIR / "REQUAL_PRECLAIM.json", {
                "provider_job_id": job_id, "shot_id": SHOT_ID,
                "preconditions": {"preflight": "PREFLIGHT_PASS",
                                  "reference_chain": "adopted+verified",
                                  "baseline_captured": True},
                "current_generate_count": len(load_ledger()["consumed"]),
                "max_generate_count": MAX_NATIVE_REQUAL_GENERATE})
            attestation = json.loads(
                (ATT_EVIDENCE / (binding["attestation_id"] + ".json")).read_text(encoding="utf-8"))
            runtime.reserve(frozen, attestation=attestation, evidence_dir=ATT_EVIDENCE)
            records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            if sorted(row[0].lower() for row in records) != \
                    frozen.job.pre_dispatch_snapshot["catalog_ids"]:
                raise OwnerAmbiguityGate("BASELINE_CHANGED_BEFORE_UI_PREPARATION")
            report["baseline_unchanged_at_release"] = True
        # ---- headful release (the qualified route is headful) ----
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(PROFILE), channel="chrome", headless=False,
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
                ui = prepare_inputs(ui_session, records,
                                    media_id=REFERENCE_MEDIA_ID, prompt=prompt)
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
                        response_holder["diagnostics"] = contract.submission_diagnostics(body)
                    except Exception:
                        response_holder["diagnostics"] = {
                            "classification": "UNPARSEABLE", "advisory_only": True}

                page.on("response", on_response)
                guard = runtime.arm_native_guard(frozen)
                page.context.route(MUTATION_ROUTE, guard.route)
                verify_chip(page, REFERENCE_MEDIA_ID)
                editor = page.locator('div.ProseMirror[contenteditable="true"]')
                if editor.count() != 1 or editor.inner_text() != prompt:
                    raise OwnerAmbiguityGate("PROMPT_CHANGED_AT_MUTATION_BOUNDARY")
                store.record_dispatch_fact(job_id, "PROMPT_VERIFIED",
                                           {"prompt_sha256": sha256(prompt)})
                store.record_dispatch_fact(job_id, "CLICK_ARMED", {})
                guard.armed = True
                report["generate_clicks"] = 1
                page.locator("button.generate-icon-button").click(timeout=15000)
                print(json.dumps({"stage": "one_native_generate_click_issued"}), flush=True)
                end = time.monotonic() + RELEASE_WAIT_S
                while guard.sent != 1 and guard.error is None and time.monotonic() < end:
                    page.wait_for_timeout(250)
                report["observed_generate_requests"] = guard.seen
                if guard.error is not None:
                    report["gate"] = "OWNER_GATE_REQUEST_NEVER_RELEASED"
                    report["blocked_request_cause"] = guard.error
                    write_new(LEDGER_DIR / "REQUAL_REQUEST_BLOCKED.json",
                              {"cause": guard.error, "seen": guard.seen,
                               "sent": guard.sent})
                    raise OwnerAmbiguityGate(guard.error)
                if guard.sent != 1:
                    report["gate"] = "OWNER_GATE_REQUEST_NEVER_RELEASED"
                    raise OwnerAmbiguityGate("EXACT_NATIVE_REQUEST_NOT_OBSERVED")
                consume_budget({"provider_job_id": job_id, "released_at": utc_now(),
                                "guard_sent": guard.sent,
                                "note": "Generate authority consumed; never retry authority."})
                report["gate"] = "OWNER_AMBIGUITY_GATE"
                print(json.dumps({"stage": "generate_released_authority_consumed",
                                  "provider_job_id": job_id}), flush=True)
                end = time.monotonic() + 30
                while "status" not in response_holder and time.monotonic() < end:
                    page.wait_for_timeout(250)
                report["provider_response"] = response_holder
                page.screenshot(path=str(out_dir / "post_release.png"))
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
        # ---- transport facts recorded post-close (local journal writes) ----
        if report.get("provider_response", {}).get("status"):
            runtime.observe_provider_response(frozen,
                status=report["provider_response"]["status"])
            counts = (report["provider_response"].get("diagnostics") or {}).get("type_counts") or {}
            if any(count for key, count in counts.items() if key != "null"):
                runtime.observe_provider_acceptance(frozen,
                                                    provider_reference="MZZa6b_wire_ack")
        report["release_phase"] = "COMPLETED_AWAITING_RECONCILIATION"
    except OwnerAuthRequired as exc:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
        report["diagnostic"] = str(exc)
    except OwnerAmbiguityGate as exc:
        report["stop_type"] = type(exc).__name__
        report["diagnostic"] = str(exc)
        if report["gate"] != "OWNER_GATE_REQUEST_NEVER_RELEASED":
            if report.get("observed_generate_requests"):
                report["gate"] = "OWNER_AMBIGUITY_GATE"
                try:
                    store.record_dispatch_fact(job_id, "AMBIGUOUS_EVIDENCE",
                        {"diagnostic": "requal_release_owner_gate"})
                except Exception:
                    pass
            else:
                report["gate"] = "OWNER_GATE: " + str(exc)
    except Exception as exc:
        report["stop_type"] = type(exc).__name__
        report["diagnostic"] = str(exc)[:400]
        if report.get("observed_generate_requests"):
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            try:
                store.record_dispatch_fact(job_id, "AMBIGUOUS_EVIDENCE",
                    {"diagnostic": "requal_release_owner_gate"})
            except Exception:
                pass
        else:
            report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
    finally:
        if job_id is not None:
            try:
                fresh = store.read_provider_job(job_id)
                report["final_dispatch_count"] = fresh.dispatch_count
                report["dispatch_journal_kinds"] = [f["kind"] for f in
                                                    store.read_dispatch_facts(job_id)]
            except Exception:
                pass
        write_durable(out_dir / "release_result.json", report)
    print(json.dumps({"gate": report["gate"], "provider_job_id": report.get("provider_job_id")}),
          flush=True)
    return report


# -------------------------------------------------------------- reconcile
def reconcile() -> dict:
    """Read-only continuation for an already-released job. Never re-releases."""
    out_path = RELEASE_DIR / "reconcile_result.json"
    if out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))
    store = SQLiteStore(DATABASE)
    binding = json.loads((QUAL_DIR / "reference_binding.json").read_text(encoding="utf-8"))
    runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID, account_id=ACCOUNT_ID,
                                 model=MODEL)
    frozen_intent = json.loads((RELEASE_DIR / "frozen_intent.json").read_text(encoding="utf-8"))
    job_id = frozen_intent["provider_job_id"]
    report = {"stage": "RECONCILE", "gate": "OWNER_AMBIGUITY_GATE", "provider_job_id": job_id}
    try:
        job = store.read_provider_job(job_id)
        if job.dispatch_count != 1:
            raise OwnerAmbiguityGate("RECONCILE_REQUIRES_CONSUMED_DISPATCH")
        frozen = frozen_job_handle(store, job_id)
        with open_read_session() as session:
            window_end = time.monotonic() + OBSERVATION_WINDOW_S
            next_poll = time.monotonic() + 10.0
            output_id = None
            records = None
            polls = 0
            while time.monotonic() < window_end and output_id is None:
                if time.monotonic() >= next_poll:
                    polls += 1
                    next_poll = time.monotonic() + POLL_INTERVAL_S
                    try:
                        records = session.catalog(
                            contract_version=contract.CONTRACT_VERSION_2026_10_01)
                    except FlowReferenceRpcDrift:
                        report["catalog_read_failures"] = \
                            report.get("catalog_read_failures", 0) + 1
                        continue
                    try:
                        output_id = runtime.attribute_backend_output(frozen, records)
                    except contract.ContractError as exc:
                        if str(exc) == "OUTPUT_STATUS_UNQUALIFIED":
                            continue
                        raise OwnerAmbiguityGate(
                            "BACKEND_ATTRIBUTION_MATERIAL_DISAGREEMENT: " + str(exc))
                    if output_id is None:
                        print(json.dumps({"stage": "reconciliation_pending",
                                          "polls": polls}), flush=True)
                time.sleep(1.0)
            if output_id is None:
                raise OwnerAmbiguityGate("EXTERNAL_EFFECT_UNRESOLVED")
            report["reconciliation_polls"] = polls
            report["output_identity"] = output_id
            marker = frozen_intent["correlation_marker"]
            marker_rows = [row for row in records
                           if marker in " ".join(contract._strings(row))]
            if len(marker_rows) != 1:
                raise OwnerAmbiguityGate("BACKEND_MARKER_ROW_NOT_UNIQUE")
            prompt = frozen_intent["prompt"]
            echo_texts = [s for s in contract._strings(marker_rows[0])
                          if MARKER_RE.findall(s) == [marker]]
            report["backend_prompt_echo_exact"] = prompt in echo_texts
            if not report["backend_prompt_echo_exact"]:
                raise OwnerAmbiguityGate("BACKEND_EXACT_PROMPT_MISMATCH")
            # Render lifecycle observation through the hardened states.
            render = runtime.observe_render_state(frozen, session=session)
            report["render_state_observed"] = render.state
            if render.state == "RENDER_COMPLETED":
                payload = render.payload
            else:
                payload = _poll_media_resolution(session, output_id, report)
            resource = parse_media_resource(payload, media_id=output_id,
                                            project_id=PROJECT_ID, kind="video")
            # Exact acquisition GET inside the authenticated session; the
            # runtime-owned binding of staged bytes happens in acquire() after
            # the session closes (playwright sync and asyncio.run cannot share
            # a thread).
            media = session.bound_media(output_id, "video")
            report["acquisition_get_bytes"] = len(media.data)
        asset = runtime.acquire(frozen,
            transport=PreFetchedTransport(media.data, output_id),
            destination_dir=RELEASE_DIR / "videos", media_payload=payload)
        report["asset"] = asset.model_dump(mode="json")
        # Technical decode validation (full EOF decode).
        report["decode"] = verify_full_decode(Path(asset.uri_or_path))
        report["qc_eligibility"] = runtime.qc_eligibility(frozen, asset)
        report["restart_proofs"] = restart_proofs(store, job_id)
        report["rpc_calls"] = dict(getattr(session, "rpc_call_counts", {}))
        report["direct_mzza6b_submits"] = getattr(session, "rpc_call_counts", {}).get("MZZa6b", 0)
        report["reference_uploads"] = getattr(session, "rpc_call_counts", {}).get("maseQ", 0)
        report["gate"] = "REQUAL_PROVEN"
    except OwnerAmbiguityGate as exc:
        report["diagnostic"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        report["diagnostic"] = f"{type(exc).__name__}: {exc}"[:400]
    write_durable(out_path, report)
    print(json.dumps({"gate": report["gate"], "output": str(out_path)}), flush=True)
    return report


def frozen_job_handle(store: SQLiteStore, job_id: str):
    """Rebuild a FrozenR2VShot handle for an already-frozen job (read-only)."""
    from film_pipeline.flow_r2v_boundary import MutationIntent
    from film_pipeline.flow_r2v_runtime import FrozenR2VShot

    job = store.read_provider_job(job_id)
    binding = job.correlation_evidence["reference_binding"]
    shot, plan, route, attempt = store.read_path(job.generation_attempt_id)
    intent = MutationIntent(project_id=PROJECT_ID, account_id=ACCOUNT_ID,
                            reference_media_id=binding["media_id"], model=MODEL)
    return FrozenR2VShot(shot=shot, plan=plan, attempt=attempt, job=job,
                         intent=intent,
                         reference_asset=store.read_reference_asset(binding["asset_id"]))


def _poll_media_resolution(session, output_id: str, report: dict):
    """Bounded as29s resolution loop for the owned output.

    Only a payload the deterministic recognizer classifies as the qualified
    completed media shape resolves the loop; recognized-pending and UNKNOWN
    payloads keep the read-only poll going and are never pending-equivalent
    for unknown shapes."""
    from film_pipeline.flow_r2v_runtime import (
        AS29S_PAYLOAD_COMPLETED,
        classify_as29s_payload,
    )
    window_end = time.monotonic() + 600
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


def verify_full_decode(path: Path) -> dict:
    import shutil

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OwnerAmbiguityGate("FFMPEG_UNAVAILABLE")
    completed = subprocess.run(
        [ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=300, check=False)
    return {"returncode": completed.returncode,
            "stderr_tail": completed.stderr[-400:],
            "full_decode_eof": completed.returncode == 0}


def restart_proofs(store: SQLiteStore, job_id: str) -> dict:
    fresh = SQLiteStore(store.path)
    job = fresh.read_provider_job(job_id)
    executor = LiveRuntimeExecutor(fresh, None)
    recovery = executor.recovery_decision(job_id)
    consumed = job.dispatch_count == 1
    return {
        "dispatch_count": job.dispatch_count,
        "consumed_authority": consumed,
        "recovery_classification": recovery.classification,
        "recovery_action": recovery.action,
        "may_submit": recovery.may_submit,
        "redispatch_blocked": bool(consumed and not recovery.may_submit),
    }


class PreFetchedTransport:
    """Places the exact session-fetched bytes at the runtime-owned staging
    path. The signed-URL GET ran inside the authenticated session; the
    runtime-owned binding of the staged bytes against the parsed as29s
    resource happens inside FlowR2VShotRuntime.acquire."""

    def __init__(self, data: bytes, output_id: str):
        self.data = data
        self.output_id = output_id

    async def fetch(self, job, output_id, destination):
        if output_id != self.output_id:
            raise OwnerAmbiguityGate("ACQUISITION_OUTPUT_IDENTITY_MISMATCH")
        destination.write_bytes(self.data)
        return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["adopt", "preflight", "release", "reconcile"])
    args = parser.parse_args()
    if args.stage == "adopt":
        stage_adopt()
    elif args.stage == "preflight":
        stage_preflight()
    elif args.stage == "release":
        stage_release()
    elif args.stage == "reconcile":
        reconcile()


if __name__ == "__main__":
    main()
