"""FLOW-SEQUENCE-SCALE-005 — production-run runner.

ProductionRun RUN005_FLOW_SWORDSMAN_JOURNEY:
- Sequence A (ADOPTED, read-only): SEQ004_SWORDSMAN_DESCENT (10 proven shots,
  Package-004) — verified from durable state, never regenerated;
- Sequence B (LIVE): SEQ005_VALLEY_STREAM (2 scenes × 4 shots, this
  package's fresh authority).

Budgets: MAX_PRIMARY_GENERATES = 8, MAX_REPAIR_GENERATES = 3,
CONTINUITY_UPLOADS = 0 (unused; same-reference continuity suffices).
Mutation authority: durable latch scope FLOW-SEQUENCE-SCALE-005 (fresh,
Owner-authorized by this package).
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

import production_run
import scene_runner
from mutation_authority import MutationAuthority
from run_scene_scale_003 import (
    PreFetchedTransport,
    flow_capabilities,
    poll_media,
    verify_full_decode,
)

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "projects/flow_sequence_005"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
PLAN_B = ROOT / "fixtures/sequence005/sequence_plan_005.json"
HIST_STATE = ROOT / "projects/flow_multiscene_004/sequence_state.json"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
MODEL = contract.MODEL_VEO_3_1_LITE
MAX_PRIMARY_GENERATES = 8
MAX_REPAIR_GENERATES = 3
OBSERVATION_WINDOW_S = 2400
POLL_INTERVAL_S = 60
RELEASE_WAIT_S = 45
MUTATION_ROUTE = "**/batchexecute?*"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"
BASE_REFERENCE = json.loads(
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
    return MutationAuthority(RUN_DIR, "FLOW-SEQUENCE-SCALE-005")


def ledger() -> dict:
    path = RUN_DIR / "generate_ledger.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"initialized_at": now(), "max_primary": MAX_PRIMARY_GENERATES,
            "max_repair": MAX_REPAIR_GENERATES, "max_uploads": 0,
            "primary_consumed": [], "repair_consumed": [], "uploads": []}


def save_ledger(data: dict) -> None:
    path = RUN_DIR / "generate_ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def open_read_session():
    return FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                   project_id=PROJECT_ID, native_ui=True)


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


def run_live_shot(shot: dict, state_dir: Path, scene_state: dict) -> dict:
    """ONE live sequence shot through the proven per-shot runtime chain."""
    tag = shot["shot_id"]
    shot_dir = Path(state_dir) / f"shot_{tag}"
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
              "generate_clicks": 0, "observed_generate_requests": 0}
    frozen = None
    started = utc_now()
    try:
        runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID,
                                     account_id=ACCOUNT_ID, model=MODEL)
        binding = {"media_id": BASE_REFERENCE["media_id"],
                   "asset_id": BASE_REFERENCE["asset_id"],
                   "attestation_id": BASE_REFERENCE["attestation_id"],
                   "mechanism": "same_reference"}
        attestation = json.loads((
            ROOT / "projects/flow_production_harden_002/requal_current_build/"
            "reference/attestation" / (binding["attestation_id"] + ".json"))
            .read_text(encoding="utf-8"))
        attestation_dir = (ROOT / "projects/flow_production_harden_002/"
                           "requal_current_build/reference/attestation")
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
                "correlation_marker": frozen.job.correlation_evidence["correlation_marker"],
                "pre_dispatch_snapshot": frozen.job.pre_dispatch_snapshot})
            already_consumed = bool(store.read_provider_job(job_id).dispatch_count)
            if not already_consumed:
                auth.check_mutation_allowed("primary_generate")
                used = len(ledger_data["primary_consumed"])
                if used >= MAX_PRIMARY_GENERATES:
                    raise OwnerAmbiguityGate("PRIMARY_BUDGET_EXHAUSTED")
                runtime.reserve(frozen, attestation=attestation,
                                evidence_dir=attestation_dir)
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
                                            media_id=binding["media_id"],
                                            prompt=prompt)
                    except Exception:
                        page.screenshot(path=str(shot_dir / "ui_prepare_failure.png"))
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
                    ledger_data["primary_consumed"].append({
                        "shot_id": tag, "provider_job_id": job_id,
                        "released_at": utc_now(),
                        "note": "Generate authority consumed; never retry authority."})
                    save_ledger(ledger_data)
                    auth.consume("primary_generate")
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
            auth.latch("GENERATE_AMBIGUITY", str(exc))
            try:
                store.record_dispatch_fact(frozen.job.provider_job_id,
                    "AMBIGUOUS_EVIDENCE", {"diagnostic": "seq005_owner_gate"})
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "status"])
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(json.loads((RUN_DIR / "production_run_state.json").read_text(
            encoding="utf-8")), indent=2, ensure_ascii=False))
        return
    run = {"run_id": "RUN005_FLOW_SWORDSMAN_JOURNEY",
           "sequences": [
               {"sequence_id": "SEQ004_SWORDSMAN_DESCENT",
                "mode": "adopted", "state_ref": str(HIST_STATE)},
               {"sequence_id": "SEQ005_VALLEY_STREAM",
                "mode": "live", "plan_ref": str(PLAN_B)}]}
    result = production_run.execute_production_run(
        run, RUN_DIR, lambda entry, state_dir: scene_runner.execute_scene(
            {"scene_id": s["scene_id"], "shots": s["shots"]},
            state_dir, run_live_shot)
        if (s := json.loads(Path(entry["plan_ref"]).read_text(encoding="utf-8")))
        else None)
    print(json.dumps({k: result[k] for k in ("run_id", "sequences_proven",
                                             "sequences_total",
                                             "run_complete")}), flush=True)


if __name__ == "__main__":
    main()
