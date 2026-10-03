"""FLOW-EDITORIAL-RUNTIME-SCALE-010 Phase 4 (T4): live session-reuse
canaries A/B/C.

ONE ProviderBrowserShell (persistent native-UI browser) for THREE shots;
THREE independent ProviderJobs/markers/baselines/guards. All proven
per-shot custody steps are kept verbatim from the Package-007 chain; only
the browser lifecycle changes (reuse instead of per-shot launch).

Authority: single domain FLOW-EDITORIAL-RUNTIME-SCALE-010. Budget: 3
generates, 0 uploads, 0 retries. Any OwnerAmbiguityGate with an observed
generate request latches the package.
"""
from __future__ import annotations

import json
import sys
import time
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
tools_path = str(Path(__file__).resolve().parent)
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

RUN_DIR = ROOT / "projects/flow_editorial_runtime_scale_010"
SCOPE_ID = "FLOW-EDITORIAL-RUNTIME-SCALE-010"
MAX_GENERATES = 3

import run_production_scale_007 as base

base.RUN_DIR = RUN_DIR
base.SCOPE_ID = SCOPE_ID

from film_pipeline.core import References, load_shot, sha256
from film_pipeline.providers.flow_r2v_prompt import MARKER_RE
from film_pipeline.flow_r2v_runtime import (
    FlowR2VShotRuntime, qualify_flow_catalog_source)
from film_pipeline.live_runtime import utc_now
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_canonical_ui import prepare_inputs, verify_chip
from film_pipeline.providers.flow_media import parse_media_resource
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift, FlowReferenceRpcSession)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_session_shell import (
    ProviderBrowserShell, SessionStateRequirements, SessionStateUnqualified)
from mutation_authority import MutationAuthority

FIXTURES = {
    "SHOT_A": "fixtures/requal010/SHOT_A.json",
    "SHOT_B": "fixtures/requal010/SHOT_B.json",
    "SHOT_C": "fixtures/requal010/SHOT_C.json",
}


def fresh_requirements(stage: str, prompt: str, marker: str,
                       fingerprint) -> SessionStateRequirements:
    return SessionStateRequirements(
        project_id=base.PROJECT_ID, prompt=prompt, marker=marker,
        model=None, aspect=2, duration_s=8, output_count=1,
        reference_media_id=base.BASE_REFERENCE["media_id"],
        catalog_fingerprint=fingerprint, stage=stage,
        verify_model_and_settings=(stage == "before_prepare"))


def run_reuse_shot(tag: str, shell: ProviderBrowserShell, store,
                   timings: dict) -> dict:
    scene_dir = RUN_DIR / "scene_SESSION_REUSE"
    shot_dir = scene_dir / f"shot_{tag}"
    shot_dir.mkdir(parents=True, exist_ok=True)
    result_path = shot_dir / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))
    auth = base.authority()
    auth.check_mutation_allowed("primary_generate")
    store.initialize()
    ledger_data = base.ledger()
    report = {"shot_id": tag, "gate": "OWNER_GATE_LOCAL_FAILURE",
              "generate_clicks": 0, "observed_generate_requests": 0,
              "budget_kind": "primary"}
    started = utc_now()
    t0 = time.monotonic()

    binding = {"media_id": base.BASE_REFERENCE["media_id"],
               "asset_id": base.BASE_REFERENCE["asset_id"],
               "attestation_id": base.BASE_REFERENCE["attestation_id"],
               "mechanism": "same_reference"}
    attestation = json.loads(
        (base.BASE_ATTESTATION_DIR /
         (binding["attestation_id"] + ".json")).read_text(encoding="utf-8"))
    runtime = FlowR2VShotRuntime(store, project_id=base.PROJECT_ID,
                                 account_id=base.ACCOUNT_ID, model=base.MODEL)
    spec = load_shot(ROOT / FIXTURES[tag])
    spec = spec.model_copy(update={
        "references": References(other_asset_ids=[binding["asset_id"]])})
    # Session reuse: the RPC layer rides the SAME live shell page (one
    # authenticated browser); no second browser is launched.
    session = FlowReferenceRpcSession.attach(page=shell.page,
                                             project_id=base.PROJECT_ID)
    if True:
        capability = qualify_flow_catalog_source(session)
        fingerprint = session.catalog_fingerprint
        frozen = runtime.freeze(spec, base.flow_capabilities(),
            reference_asset=store.read_reference_asset(binding["asset_id"]),
            reference_media_id=binding["media_id"],
            reference_filename="", catalog_source=capability,
            started_at=started)
        job_id = frozen.job.provider_job_id
        prompt = frozen.job.correlation_evidence["prompt"]
        marker = frozen.job.correlation_evidence["correlation_marker"]
        report["provider_job_id"] = job_id
        fi_path = shot_dir / "frozen_intent.json"
        fi_payload = {"shot_id": tag, "provider_job_id": job_id,
                      "prompt_sha256": sha256(prompt),
                      "correlation_marker": marker,
                      "continuity": binding, "budget_kind": "primary"}
        if fi_path.exists():
            if json.loads(fi_path.read_text(encoding="utf-8"))[
                    "provider_job_id"] != job_id:
                raise OwnerAmbiguityGate("EVIDENCE_CONFLICT: frozen_intent")
        else:
            base.write_durable(fi_path, fi_payload)
        job_now = store.read_provider_job(job_id)
        facts = store.read_dispatch_facts(job_id)
        kinds = {f["kind"] for f in facts}
        release_stage = bool(kinds & {
            "PROMPT_VERIFIED", "CLICK_ARMED", "GENERATE_REQUEST_OBSERVED",
            "PROVIDER_RESPONSE_OBSERVED", "REMOTE_IDENTITY_OBSERVED",
            "IDENTITY_BOUND"})
        already_consumed = bool(job_now.dispatch_count) and release_stage
        if not already_consumed:
            auth.check_mutation_allowed("primary_generate")
            import scale_run as _scale
            _scale.assert_budget_available(
                len(ledger_data["primary_consumed"]), MAX_GENERATES,
                "PRIMARY")
            runtime.reserve(frozen, attestation=attestation,
                            evidence_dir=base.BASE_ATTESTATION_DIR)
        records = session.catalog(
            contract_version=contract.CONTRACT_VERSION_2026_10_01)
        if not already_consumed and sorted(
                row[0].lower() for row in records) != \
                frozen.job.pre_dispatch_snapshot["catalog_ids"]:
            raise OwnerAmbiguityGate("BASELINE_CHANGED_BEFORE_UI_PREPARATION")
    timings["freeze_and_reserve_s"] = round(time.monotonic() - t0, 3)
    if already_consumed:
        # At-most-once: the release already happened; this re-entry
        # is observation + acquisition ONLY. No second click, ever.
        report["resume_read_only"] = True
    else:

        t1 = time.monotonic()
        shell.reset_for_shot(fresh_requirements(
            "before_prepare", prompt, marker, fingerprint))
        timings["shell_reset_s"] = round(time.monotonic() - t1, 3)

        t2 = time.monotonic()
        ui_session = SimpleNamespace(page=shell.page, project_id=base.PROJECT_ID)
        try:
            ui = prepare_inputs(ui_session, records,
                                media_id=binding["media_id"], prompt=prompt)
        except Exception:
            shell.page.screenshot(path=str(shot_dir / "ui_prepare_failure.png"))
            raise
        report["ui_preflight"] = ui
        timings["prepare_inputs_s"] = round(time.monotonic() - t2, 3)

        before_gen = fresh_requirements(
            "before_generate", prompt, marker, fingerprint)
        shell.before_generate_check(before_gen)

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
                response_holder["diagnostics"] = contract.submission_diagnostics(
                    body)
            except Exception:
                response_holder["diagnostics"] = {
                    "classification": "UNPARSEABLE", "advisory_only": True}

        shell.page.on("response", on_response)
        guard = runtime.arm_native_guard(frozen)
        # Adversarial fix: route handlers ACCUMULATE on a shared context;
        # a stale guard must never observe the next shot's request.
        shell.page.context.unroute(base.MUTATION_ROUTE)
        shell.page.context.route(base.MUTATION_ROUTE, guard.route)
        verify_chip(shell.page, binding["media_id"])
        editor = shell.page.locator('div.ProseMirror[contenteditable="true"]')
        if editor.count() != 1 or editor.inner_text() != prompt:
            raise OwnerAmbiguityGate("PROMPT_CHANGED_AT_MUTATION_BOUNDARY")
        store.record_dispatch_fact(job_id, "PROMPT_VERIFIED",
                                   {"prompt_sha256": sha256(prompt)})
        store.record_dispatch_fact(job_id, "CLICK_ARMED", {})
        guard.armed = True
        report["generate_clicks"] = 1
        t3 = time.monotonic()
        shell.page.locator("button.generate-icon-button").click(timeout=15000)
        end = time.monotonic() + base.RELEASE_WAIT_S
        while guard.sent != 1 and guard.error is None and \
                time.monotonic() < end:
            shell.page.wait_for_timeout(250)
        timings["release_to_guard_s"] = round(time.monotonic() - t3, 3)
        report["observed_generate_requests"] = guard.seen
        if guard.error is not None:
            raise OwnerAmbiguityGate(
                guard.error + " :: " + getattr(guard, "error_detail", ""))
        if guard.sent != 1:
            raise OwnerAmbiguityGate("EXACT_NATIVE_REQUEST_NOT_OBSERVED")
        ledger_data["primary_consumed"].append({
            "shot_id": tag, "provider_job_id": job_id,
            "released_at": utc_now(),
            "note": "Generate authority consumed; never retry authority."})
        base.save_ledger(ledger_data)
        auth.consume("primary_generate")
        release_end = time.monotonic() + 30
        while "status" not in response_holder and time.monotonic() < release_end:
            shell.page.wait_for_timeout(250)
        report["provider_response"] = response_holder
        shell.page.screenshot(path=str(shot_dir / "post_release.png"))
        if report.get("provider_response", {}).get("status"):
            runtime.observe_provider_response(
                frozen, status=report["provider_response"]["status"])
            counts = (report["provider_response"].get("diagnostics")
                      or {}).get("type_counts") or {}
            if any(count for key, count in counts.items() if key != "null"):
                runtime.observe_provider_acceptance(
                    frozen, provider_reference="MZZa6b_wire_ack")

    t4 = time.monotonic()
    if True:
        session = FlowReferenceRpcSession.attach(page=shell.page,
                                                 project_id=base.PROJECT_ID)
        window_end = time.monotonic() + base.OBSERVATION_WINDOW_S
        next_poll = time.monotonic() + 10.0
        output_id, records2 = None, None
        polls = 0
        while time.monotonic() < window_end and output_id is None:
            if time.monotonic() >= next_poll:
                polls += 1
                next_poll = time.monotonic() + base.POLL_INTERVAL_S
                try:
                    records2 = session.catalog(
                        contract_version=contract.CONTRACT_VERSION_2026_10_01)
                except FlowReferenceRpcDrift:
                    continue
                try:
                    output_id = runtime.attribute_backend_output(
                        frozen, records2)
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
        marker_rows = [row for row in records2
                       if marker in " ".join(contract._strings(row))]
        if len(marker_rows) != 1:
            raise OwnerAmbiguityGate("BACKEND_MARKER_ROW_NOT_UNIQUE")
        if prompt not in [s for s in contract._strings(marker_rows[0])
                          if MARKER_RE.findall(s) == [marker]]:
            raise OwnerAmbiguityGate("BACKEND_EXACT_PROMPT_MISMATCH")
        render = runtime.observe_render_state(frozen, session=session)
        report["render_state_observed"] = render.state
        payload = render.payload if render.state == "RENDER_COMPLETED" \
            else base.poll_media(session, output_id, report)
        media = session.bound_media(output_id, "video")
    timings["attribute_render_s"] = round(time.monotonic() - t4, 3)
    report["timings_s"] = timings
    report["total_s"] = round(time.monotonic() - t0, 3)
    # Acquisition is DEFERRED until the shell (and its Playwright event
    # loop) closes: LiveRuntimeExecutor.reconcile uses asyncio.run, which
    # cannot nest inside the shell's running loop.
    return report, {"frozen": frozen, "output_id": output_id,
                    "media_data": media.data, "payload": payload,
                    "shot_dir": shot_dir, "job_id": job_id}


def main() -> None:
    from film_pipeline.store import SQLiteStore
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    gen_ledger = RUN_DIR / "generate_ledger.json"
    if not gen_ledger.exists():
        gen_ledger.write_text(json.dumps({
            "initialized_at": utc_now(), "max_primary": MAX_GENERATES,
            "max_repair": 0, "max_uploads": 0, "primary_consumed": [],
            "repair_consumed": [], "uploads": []}, indent=1),
            encoding="utf-8")
    auth = MutationAuthority(RUN_DIR, SCOPE_ID)
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("package authority latched")
    auth.check_mutation_allowed("session_reuse_generate")
    data = json.loads(gen_ledger.read_text(encoding="utf-8"))
    released = {e["shot_id"] for e in data["primary_consumed"]}
    pending = [t for t in FIXTURES
               if t not in released
               and not (RUN_DIR / f"scene_SESSION_REUSE/shot_{t}/result.json")
               .exists()]
    if len(released & set(FIXTURES)) + len(pending) > MAX_GENERATES:
        raise OwnerAmbiguityGate("session-reuse budget exhausted (3 max)")

    store = SQLiteStore(base.STORE_PATH)
    store.initialize()
    all_timings, stashed = {}, []
    with ProviderBrowserShell(
            profile=base.PROFILE,
            project_url=f"https://flow.google.com/project/{base.PROJECT_ID}"
            ) as shell:
        for tag in FIXTURES:
            timings = {}
            report = {}
            try:
                report, ctx = run_reuse_shot(tag, shell, store, timings)
            except OwnerAmbiguityGate as exc:
                import traceback
                traceback.print_exc()
                diag = str(exc)
                report_local = {"shot_id": tag, "gate": "OWNER_GATE_LOCAL",
                                "diagnostic": diag}
                if "observed_generate_requests" in diag or \
                        report.get("generate_clicks"):
                    auth.latch("GENERATE_AMBIGUITY", diag)
                    report_local["gate"] = "OWNER_AMBIGUITY_GATE"
                base.write_durable(
                    RUN_DIR / f"scene_SESSION_REUSE/shot_{tag}/result.json",
                    report_local)
                print(json.dumps(report_local), flush=True)
                raise SystemExit(4)
            all_timings[tag] = report.get("timings_s", timings)
            stashed.append((tag, report, ctx))
    # Shell closed: the Playwright loop is gone; acquisition is safe now.
    for tag, report, ctx in stashed:
        t5 = time.monotonic()
        runtime = FlowR2VShotRuntime(store, project_id=base.PROJECT_ID,
                                     account_id=base.ACCOUNT_ID,
                                     model=base.MODEL)
        asset = runtime.acquire(
            ctx["frozen"],
            transport=base.PreFetchedTransport(ctx["media_data"],
                                               ctx["output_id"]),
            destination_dir=ctx["shot_dir"] / "videos",
            media_payload=ctx["payload"])
        report["timings_s"]["acquire_s"] = round(time.monotonic() - t5, 3)
        report["asset"] = asset.model_dump(mode="json")
        report["decode"] = base.verify_full_decode(Path(asset.uri_or_path))
        report["qc_eligibility"] = runtime.qc_eligibility(
            ctx["frozen"], asset)
        executor = base.LiveRuntimeExecutor(store, None)
        recovery = executor.recovery_decision(ctx["job_id"])
        report["restart_proofs"] = {
            "dispatch_count": store.read_provider_job(
                ctx["job_id"]).dispatch_count,
            "recovery_classification": recovery.classification,
            "may_submit": recovery.may_submit}
        report["gate"] = "SHOT_PROVEN"
        base.write_durable(ctx["shot_dir"] / "result.json", report)
        print(json.dumps({"shot_id": tag, "gate": report["gate"],
                          "output": report.get("output_identity"),
                          "timings": report["timings_s"]}), flush=True)
    base.write_durable(RUN_DIR / "session_reuse_timings.json",
                       {"shots": all_timings,
                        "shell": "ONE ProviderBrowserShell for A/B/C"})
    print(json.dumps({"result": "SESSION_REUSE_ABC_PASS"}), flush=True)


if __name__ == "__main__":
    main()
