"""FLOW-FORENSIC-TO-DOLA-001 Phase D — seedance_dola live qualification.

Frozen package: docs/operating/FLOW_FORENSIC_TO_DOLA_001_WORK_PACKAGE.md

Authority: MAX_DOLA_GENERATE_RELEASES = 2 (ceiling, never retry authority).
No reference upload (the observed Dola T2V contract requires none). No account
creation, payment, CAPTCHA bypass, or switching: the transport uses the Owner's
existing encrypted Story Auto Dola cookie account, loaded in memory only.

Hypothesis D-G1: the observed Dola cookie contract (www.dola.com
/chat/completion SSE receipt -> /im/chain/single poll with client_request_id
echo -> allowlisted CDN acquisition) admits one bounded T2V generation for an
ordinary AI-Film shot through the durable AI-Film boundary (ShotSpec ->
PromptPlan -> seedance_dola route -> ProviderJob -> one submit -> exact
acquisition -> Asset -> technical QC), with restart able to resume but never
re-submit.

Hypothesis D-G2 (only if D-G1 is fully PROVEN): a second distinct shot through
the same route proves repeatability.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(r"D:/Story Auto/story-auto")))

from film_pipeline.core import ProviderCapabilities, canonical_json, load_shot, sha256
from film_pipeline.execution import DryRunProvider, route as route_plan
from film_pipeline.live_runtime import GenerationAttempt, file_sha256, make_provider_job, utc_now
from film_pipeline.providers.dola_provider import (
    DolaCookieTransport,
    DolaTransportError,
    probe_session,
)
from film_pipeline.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
QUAL_DIR = ROOT / "projects/flow_forensic_dola_20261002"
DOLA_DIR = QUAL_DIR / "dola"
LEDGER_DIR = QUAL_DIR / "dola" / "generate_ledger"
DATABASE = DOLA_DIR / "runtime.sqlite"

STORY_AUTO_ROOT = Path(r"D:/Story Auto/story-auto")
PREFERRED_ACCOUNTS = ("dola-profile-20260923", "dola-main")
MODEL = "seedance_v2.0"
MAX_DOLA_GENERATE_RELEASES = 2
POLL_WINDOW_S = 1200
POLL_INTERVAL_S = 5

D_G1_HYPOTHESIS = (
    "The observed Dola cookie contract admits one bounded 5s T2V generation for an "
    "ordinary AI-Film shot through the durable seedance_dola boundary, with exact "
    "acquisition, Asset lineage, technical QC, and restart-never-resubmit semantics."
)
D_G2_HYPOTHESIS = (
    "A second distinct shot through the exact same route proves the seedance_dola "
    "boundary is repeatable and not coupled to one conversation/task identity."
)


def write_new(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"immutable evidence file already exists: {path.name}")
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json(value))
        stream.flush()
        os.fsync(stream.fileno())


def ledger_state() -> dict:
    init = LEDGER_DIR / "D_INIT.json"
    if not init.is_file():
        raise RuntimeError("dola authority ledger not initialized")
    consumed = [json.loads(entry.read_text(encoding="utf-8"))
                for entry in sorted(LEDGER_DIR.glob("D-G*_CONSUMED.json"))]
    return {"init": json.loads(init.read_text(encoding="utf-8")), "consumed": consumed}


def require_budget(count_needed: int) -> None:
    state = ledger_state()
    if len(state["consumed"]) + count_needed > state["init"]["max_dola_generate_releases"]:
        raise RuntimeError("DOLA_GENERATE_BUDGET_EXHAUSTED")


def load_cookie_in_memory(account_id: str) -> str:
    """Load the Owner's existing Dola session via Story Auto's own encrypted
    account store. The cookie never touches disk, logs, or evidence here."""
    from story_auto.providers.dola_cookie.accounts import DolaAccountStore
    cookie = DolaAccountStore().get_cookie(account_id)
    if not isinstance(cookie, str) or "sessionid=" not in cookie:
        raise RuntimeError("DOLA_CREDENTIAL_UNAVAILABLE")
    return cookie


def dola_capabilities() -> ProviderCapabilities:
    payload = {
        "profile_version": "seedance-dola-observed-20260923-v1",
        "provider_id": "seedance_dola",
        "transport_type": "other",
        "supports_text_to_video": True,
        "supports_image_input": False,
        "supports_duration_control": True,
    }
    from film_pipeline.core import validate_contract
    validate_contract("provider_capabilities", payload)
    return ProviderCapabilities.model_validate(payload)


def ordinary_t2v_shot(shot_id: str) -> "object":
    shot = load_shot(ROOT / "fixtures/flow_canary.json")
    return shot.model_copy(update={"shot_id": shot_id, "duration_target_s": 5})


def stage_setup() -> dict:
    DOLA_DIR.mkdir(parents=True, exist_ok=True)
    SQLiteStore(DATABASE).initialize()
    write_new(LEDGER_DIR / "D_INIT.json", {
        "checkpoint": "C6_DOLA_BASELINE",
        "max_dola_generate_releases": MAX_DOLA_GENERATE_RELEASES,
        "dola_generate_count": 0,
        "reference_uploads_allowed": 1,
        "reference_uploads_used": 0,
        "contract_basis": "Owner Story Auto dola_cookie observed contract, live-qualified 2026-09-23",
        "requested_model": MODEL,
    })
    return {"ledger": ledger_state()["init"]}


def stage_preflight() -> dict:
    if (DOLA_DIR / "preflight.json").exists():
        report = json.loads((DOLA_DIR / "preflight.json").read_text(encoding="utf-8"))
        if report["gate"] != "D_PREFLIGHT_PASS":
            raise RuntimeError("dola preflight did not pass")
        return report
    report = {"stage": "D_PREFLIGHT", "gate": "OWNER_GATE",
              "accounts_probed": {}, "provider_reads": {}}
    chosen = None
    for account_id in PREFERRED_ACCOUNTS:
        try:
            cookie = load_cookie_in_memory(account_id)
        except Exception as exc:
            report["accounts_probed"][account_id] = {"credential": type(exc).__name__}
            continue
        try:
            alive = probe_session(cookie)
        except DolaTransportError as exc:
            report["accounts_probed"][account_id] = {"probe": exc.failure_class}
            continue
        report["accounts_probed"][account_id] = {"session_alive": alive, "probe_reads": 1}
        report["provider_reads"][account_id] = 1
        if alive and chosen is None:
            chosen = account_id
    if chosen is not None:
        report["chosen_account_id"] = chosen
        report["gate"] = "D_PREFLIGHT_PASS"
    else:
        report["diagnostic"] = "NO_LIVE_DOLA_SESSION"
    write_new(DOLA_DIR / "preflight.json", report)
    print(json.dumps({"stage": "dola_preflight", "gate": report["gate"],
                      "chosen": report.get("chosen_account_id")}), flush=True)
    if report["gate"] != "D_PREFLIGHT_PASS":
        raise SystemExit(1)
    return report


def _reserve_and_submit(store: SQLiteStore, job, transport: DolaCookieTransport,
                        prompt: str, aspect: str, duration: int, canary_id: str) -> str | None:
    """Reserve durably, then submit exactly once with a persisted receipt.

    Journal mapping for the observed Dola contract: the serialized request is
    armed/observed facts from the transport itself; the SSE_ACK conversation
    receipt is the observed provider acceptance bound to that request.

    The authority-consumption entry is written for EVERY on-the-wire submit
    attempt (receipt or not) before this function returns; failure evidence
    is recorded crash-proof (a ledger gap after an ambiguous release is the
    one unrecoverable custody defect, so consumption is persisted first).
    """
    reserved = store.reserve_dispatch(job.provider_job_id)
    store.record_dispatch_fact(job.provider_job_id, "PROMPT_VERIFIED", {
        "prompt_sha256": job.correlation_evidence["submission_prompt_hash"]})
    receipt_holder = {}
    contract_tag = "dola-cookie-observed-20260923-v1"

    def on_receipt(conversation_id: str) -> None:
        receipt_holder["conversation_id"] = conversation_id
        store.record_dispatch_fact(job.provider_job_id, "GENERATE_REQUEST_OBSERVED", {
            "request_hash": transport.last_request_hash,
            "body_sha256": transport.last_body_sha256,
            "contract": contract_tag})
        store.record_dispatch_fact(job.provider_job_id, "PROVIDER_RESPONSE_OBSERVED", {
            "request_hash": transport.last_request_hash,
            "status": transport.last_response_status})
        store.record_dispatch_fact(job.provider_job_id, "PROVIDER_ACCEPTANCE_OBSERVED", {
            "request_hash": transport.last_request_hash,
            "provider_reference": conversation_id,
            "contract": contract_tag})
        submitted = reserved.model_copy(update={
            "submission_state": "SUBMITTED", "status": "SUBMITTED",
            "external_job_id": conversation_id, "submitted_at": utc_now(),
            "last_checked_at": utc_now()})
        store.save_provider_job(submitted)

    failure: DolaTransportError | None = None
    try:
        transport.submit(prompt, aspect, duration, on_receipt,
                         client_request_id=job.provider_job_id)
    except DolaTransportError as exc:
        failure = exc
    # The submit hit the wire (or failed before it): persist consumption NOW,
    # then classify. INCONCLUSIVE is the only valid durable uncertain state.
    write_new(LEDGER_DIR / f"{canary_id}_CONSUMED.json", {
        "canary_id": canary_id, "provider_job_id": job.provider_job_id,
        "released_at": utc_now(),
        "receipt_observed": bool(receipt_holder.get("conversation_id")),
        "note": "Dola Generate authority consumed; never retry authority."})
    if failure is None:
        if not receipt_holder.get("conversation_id"):
            raise RuntimeError("DOLA_RECEIPT_NOT_PERSISTED")
        return receipt_holder["conversation_id"]
    uncertain = reserved.model_copy(update={
        "status": "INCONCLUSIVE" if failure.dispatch_state == "AMBIGUOUS" else "FAILED",
        "last_checked_at": utc_now()})
    store.save_provider_job(uncertain)
    try:
        if failure.dispatch_state == "AMBIGUOUS":
            store.record_dispatch_fact(job.provider_job_id, "AMBIGUOUS_EVIDENCE", {
                "diagnostic": "dola-submission-uncertain"})
        else:
            store.record_dispatch_fact(job.provider_job_id, "OBSERVATION_FAILURE", {
                "diagnostic": failure.failure_class})
    except Exception:
        # The fact row must never mask the durable job state; the ledger
        # consumption entry above already preserves custody.
        pass
    raise failure


def _poll_to_completion(store: SQLiteStore, job, transport: DolaCookieTransport,
                        report: dict) -> dict:
    deadline = time.monotonic() + POLL_WINDOW_S
    conversation_id = job.external_job_id
    while time.monotonic() < deadline:
        try:
            result = transport.poll(conversation_id, client_request_id=job.provider_job_id)
        except DolaTransportError as exc:
            if exc.failure_class in {"CREDENTIAL_OR_ACCESS_DENIED", "PROVIDER_RESULT_AMBIGUOUS",
                                     "DOLA_RESULT_IDENTITY_MISMATCH"}:
                store.record_dispatch_fact(job.provider_job_id, "RECONCILIATION_STOP", {
                    "failure_class": exc.failure_class})
                raise RuntimeError("DOLA_RECONCILIATION_STOP: " + exc.failure_class)
            report["transient_poll_errors"] = report.get("transient_poll_errors", 0) + 1
            time.sleep(POLL_INTERVAL_S)
            continue
        status = result["status"]
        if status == "COMPLETED":
            store.record_dispatch_fact(job.provider_job_id, "REMOTE_IDENTITY_OBSERVED", {
                "output_id": result["creation_id"],
                "method": "dola_cookie_creation_identity_echo"})
            store.bind_output(job.provider_job_id, result["creation_id"])
            succeeded = store.read_provider_job(job.provider_job_id).model_copy(update={
                "status": "SUCCEEDED", "last_checked_at": utc_now()})
            store.save_provider_job(succeeded)
            return result
        if status == "FAILED":
            store.record_dispatch_fact(job.provider_job_id, "PROVIDER_FAILED_TERMINAL", {
                "failure_class": "DOLA_PROVIDER_REFUSED",
                "note": "explicit provider refusal text observed; no generation admitted"})
            failed = store.read_provider_job(job.provider_job_id).model_copy(update={
                "status": "FAILED", "last_checked_at": utc_now()})
            store.save_provider_job(failed)
            raise RuntimeError("DOLA_PROVIDER_REFUSED")
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError("DOLA_GENERATION_TIMEOUT")


def _asset_from_download(store: SQLiteStore, job, transport: DolaCookieTransport,
                         result: dict, out_dir: Path):
    from film_pipeline.live_runtime import Asset, inspect_video
    destination = out_dir / "videos" / f"{sha256(result['creation_id'])[:24]}.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    binding = store.read_output_bindings(job.provider_job_id)[0]
    intent = {"binding_hash": binding["binding_hash"], "final_path": str(destination),
              "staging_path": str(destination.with_suffix(".mp4.candidate")),
              "rendition": "official-720p"}
    store.save_acquisition_record(job.provider_job_id, result["creation_id"], intent)
    metadata = transport.download(result["video_url"], destination)
    digest = file_sha256(destination)
    receipt = {**intent, **metadata, "sha256": digest,
               "file_size": destination.stat().st_size}
    store.save_acquisition_record(job.provider_job_id, result["creation_id"], receipt,
                                  completed=True)
    asset = Asset(
        asset_id=f"asset_{sha256({'job': job.provider_job_id, 'provider_asset_id': result['creation_id'], 'sha256': digest})}",
        asset_type="video", origin="generated", uri_or_path=str(destination),
        sha256=digest, mime_type=metadata["mime_type"], duration_s=metadata["duration_s"],
        width=metadata["width"], height=metadata["height"], file_size=destination.stat().st_size,
        source_attempt_id=job.generation_attempt_id, provider_job_id=job.provider_job_id,
        provider_asset_id=result["creation_id"],
        rights_metadata={"provider": "seedance_dola", "requested_model": MODEL,
                         "account_scope": "owner-existing-session"})
    store.save_asset(asset)
    store.record_dispatch_fact(job.provider_job_id, "ASSET_PERSISTED", {
        "output_id": result["creation_id"], "asset_id": asset.asset_id})
    return asset


def _review_packet(store: SQLiteStore, shot, asset, out_dir: Path) -> dict:
    from PIL import Image, ImageDraw
    from film_pipeline.qc import QCStore, evidence, technical_evidence
    from film_pipeline.qc_media import make_review_media
    technical, metadata = technical_evidence(shot, asset)
    if not metadata or any(row.verdict != "pass" for row in technical):
        raise RuntimeError("technical QC failed")
    criteria = {
        "visual": (("prompt_lock", "Output consistent with the frozen prompt?"),),
        "continuity": (("single_composition", "One stable composition across the full duration?"),),
        "editorial": (("technical_stability", "No encoding artifacts blocking editorial use?"),)}
    rows, media = make_review_media(asset, out_dir / "frames", criteria=criteria)
    descriptor, staging_name = tempfile.mkstemp(suffix=".png", dir=out_dir)
    os.close(descriptor)
    staging = Path(staging_name)
    try:
        process = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(asset.duration_s / 2),
             "-i", asset.uri_or_path, "-frames:v", "1", str(staging)],
            capture_output=True, timeout=60)
        if process.returncode or not staging.stat().st_size:
            raise RuntimeError("middle frame unavailable")
        middle = out_dir / ("middle_" + file_sha256(staging) + ".png")
        try:
            os.link(staging, middle)
        except FileExistsError:
            if file_sha256(middle) != file_sha256(staging):
                raise RuntimeError("middle-frame evidence collision")
    finally:
        staging.unlink(missing_ok=True)
    rows.append(evidence(asset=asset, evaluator_type="ffmpeg",
        evaluator_version="dola-qual-review-v1", gate="continuity",
        criterion="sampled_frame_review", verdict="uncertain",
        observation="Owner review required; sampled frames do not establish all-frame identity.",
        source_artifacts=[{"path": str(middle), "sha256": file_sha256(middle)}]))
    record, _disposition = QCStore(store).save(asset, technical + rows)
    if record.report["decision"] != "needs_human_review":
        raise RuntimeError("Dola canary must remain unselected for Owner review")
    return {"qc_report_id": record.report["qc_report_id"], "technical_pass": True,
            "middle_frame": str(middle), "sampled_media": media,
            "selected_take_created": False}


def _restart_proofs(store: SQLiteStore, job, preclaim: dict) -> dict:
    from film_pipeline.dispatch_evidence import recovery_decision
    fresh = store.read_provider_job(job.provider_job_id)
    facts = store.read_dispatch_facts(job.provider_job_id)
    bindings = store.read_output_bindings(job.provider_job_id)
    acquired = bool(bindings) and all(
        store.read_acquisition_record(job.provider_job_id, b["output_id"], completed=True)
        for b in bindings)
    decision = recovery_decision(fresh, facts, bound=bool(bindings), acquired=acquired)
    if decision.may_submit:
        raise RuntimeError("RESTART_PROOF_MAY_SUBMIT_TRUE")
    return {"recovery_classification": decision.classification,
            "recovery_action": decision.action, "may_submit": decision.may_submit,
            "journal_kinds": [f["kind"] for f in facts],
            "receipt_conversation_bound": fresh.external_job_id is not None}


def _run_canary(canary_id: str, shot_id: str, hypothesis: str, out_dir: Path) -> dict:
    if (out_dir / "live_result.json").exists():
        raise RuntimeError("durable result already recorded; no redispatch")
    preflight = stage_preflight()
    require_budget(1)
    store = SQLiteStore(DATABASE)
    store.initialize()
    report = {"stage": canary_id, "gate": "OWNER_GATE_LOCAL_FAILURE",
              "canary_id": canary_id, "hypothesis": hypothesis,
              "account_id": preflight["chosen_account_id"], "requested_model": MODEL,
              "shot_id": shot_id, "submit_calls": 0, "poll_calls": 0, "download_calls": 0}
    try:
        shot = ordinary_t2v_shot(shot_id)
        capabilities = dola_capabilities()
        plan_plan = _compile(shot, capabilities)
        decision = route_plan(shot, [plan_plan], [capabilities],
                              {"seedance_dola": True}, required_controls=None)
        dry = DryRunProvider()
        request = dry.build_request(plan_plan, decision)
        attempt = dry.create_attempt(shot, plan_plan, decision, request,
                                     started_at=utc_now())
        pre_dispatch_snapshot = {
            "contract": "dola-cookie-observed-20260923-v1",
            "account_id": preflight["chosen_account_id"],
            "requested_model": MODEL, "aspect_ratio": "16:9", "duration_s": 5,
            "session_probe": "alive"}
        job = make_provider_job(attempt,
                                project_binding_id=sha256("seedance_dola:" + preflight["chosen_account_id"]),
                                pre_dispatch_snapshot=pre_dispatch_snapshot)
        job = job.model_copy(update={"correlation_evidence": {
            "prompt": plan_plan.provider_prompt,
            "prompt_plan_hash": sha256(plan_plan),
            "submission_prompt_hash": sha256(plan_plan.provider_prompt),
            "provider_prompt_compiler": "film-canonical-provider-prompt-v1"}})
        store.save_frozen_path_and_job(shot, plan_plan, decision, attempt, job)
        report["provider_job_id"] = job.provider_job_id
        report["prompt_sha256"] = sha256(plan_plan.provider_prompt)
        write_new(LEDGER_DIR / f"{canary_id}_PRECLAIM.json", {
            "canary_id": canary_id, "provider_job_id": job.provider_job_id,
            "shot_id": shot_id, "hypothesis": hypothesis,
            "current_dola_generate_count": len(ledger_state()["consumed"]),
            "max_dola_generate_releases": MAX_DOLA_GENERATE_RELEASES})
        cookie = load_cookie_in_memory(preflight["chosen_account_id"])
        transport = DolaCookieTransport(cookie)
        conversation_id = _reserve_and_submit(store, job, transport,
                                              plan_plan.provider_prompt, "16:9", 5,
                                              canary_id)
        report["submit_calls"] = 1
        report["gate"] = "OWNER_AMBIGUITY_GATE"
        print(json.dumps({"stage": "dola_generate_released_authority_consumed",
                          "provider_job_id": job.provider_job_id,
                          "receipt_observed": conversation_id is not None}), flush=True)
        fresh_job = store.read_provider_job(job.provider_job_id)
        result = _poll_to_completion(store, fresh_job, transport, report)
        report["output_identity"] = result["creation_id"]
        report["poll_calls"] = transport.call_counts["poll"]
        print(json.dumps({"stage": "dola_output_attributed",
                          "creation_id": result["creation_id"]}), flush=True)
        asset = _asset_from_download(store, fresh_job, transport, result, out_dir)
        report["download_calls"] = transport.call_counts["download"]
        report["asset"] = asset.model_dump(mode="json")
        print(json.dumps({"stage": "asset_acquired", "asset_id": asset.asset_id,
                          "sha256": asset.sha256}), flush=True)
        report["review"] = _review_packet(store, shot, asset, out_dir)
        report["restart_proofs"] = _restart_proofs(store, fresh_job, {"canary_id": canary_id})
        report["call_counts"] = dict(transport.call_counts)
        report["gate"] = "D_G1_PROVEN" if canary_id == "D-G1" else "D_G2_PROVEN"
    except TimeoutError:
        report["gate"] = "DOLA_GENERATION_TIMEOUT"
        report["stop_type"] = "TimeoutError"
    except RuntimeError as exc:
        text = str(exc)
        report["stop_type"] = type(exc).__name__
        if text.startswith("DOLA_RECONCILIATION_STOP") or "RECEIPT" in text or "AMBIGUOUS" in text:
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            report["diagnostic"] = text
        elif text == "DOLA_PROVIDER_REFUSED":
            report["gate"] = "DOLA_PROVIDER_REFUSED"
        else:
            report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
            report["diagnostic"] = text
    except DolaTransportError as exc:
        report["stop_type"] = type(exc).__name__
        if exc.dispatch_state == "AMBIGUOUS":
            report["gate"] = "OWNER_AMBIGUITY_GATE"
        else:
            report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
        report["diagnostic"] = exc.failure_class
    except Exception as exc:
        # Any other local failure (including validation errors) is recorded
        # durably; the consumption entry is already on the ledger the moment
        # a submit reached the wire.
        report["stop_type"] = type(exc).__name__
        report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
        report["diagnostic"] = type(exc).__name__
    finally:
        report["ledger_consumed"] = [entry["canary_id"] for entry in ledger_state()["consumed"]]
        write_new(out_dir / "live_result.json", report)
    print(json.dumps({"gate": report["gate"], "output": str(out_dir / "live_result.json")}), flush=True)
    return report


def _compile(shot, capabilities):
    from film_pipeline.compiler import compile_prompt
    return compile_prompt(shot, capabilities)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["setup", "preflight", "dg1", "dg2"])
    args = parser.parse_args()
    if args.stage == "setup":
        print(json.dumps(stage_setup(), indent=1))
    elif args.stage == "preflight":
        print(json.dumps({k: v for k, v in stage_preflight().items()
                          if k in ("gate", "chosen_account_id", "accounts_probed")}, indent=1))
    elif args.stage == "dg1":
        _run_canary("D-G1", "DOLA_QUAL_DG1_001", D_G1_HYPOTHESIS, DOLA_DIR / "dg1")
    else:
        _run_canary("D-G2", "DOLA_QUAL_DG2_002", D_G2_HYPOTHESIS, DOLA_DIR / "dg2")
