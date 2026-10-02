"""FLOW-FORENSIC-TO-DOLA-001 F-G1 — reference-differential canary.

Frozen package: docs/operating/FLOW_FORENSIC_TO_DOLA_001_WORK_PACKAGE.md

HYPOTHESIS (distinct from LIVE-RUNTIME-QUAL-001 G1, which is never retried):
On project f6b40e79, provider-native UI R2V with the historically successful
reference 347f9951-5bbc-4910-b6fd-3a17c74e29d2 (the only reference whose UI
R2V release ever produced a backend-attributable output on this project,
a47636b8) admits a backend-attributable output NOW.

Facts used: the AI-Film VERIFIED upload receipt for 347f9951 exists in
projects/character_continuity/reference_qualification_20260930/runtime.sqlite
(provider_media_sha256 93fa8edf...), which the 2026-10-01 binding-resolution
evidence shows are exactly the bytes the provider serves today, strongly
matching the local immutable source dc766e13....png. The canary store is a
verbatim byte copy of that store (source sha256 pinned); the attestation is
created fresh from a live as29s readback.

Authority: MAX_NEW_FLOW_GENERATE_RELEASES = 3; this tool releases at most ONE
Generate (F-G1). Native-UI mutation only; backend attribution only; no
upload; no direct MZZa6b; no retries. A null/no-delta outcome is
EXTERNAL_EFFECT_UNRESOLVED -> Flow mutation for this package ends.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from film_pipeline.core import ProviderCapabilities, References, canonical_json, load_shot, sha256
from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime, qualify_flow_catalog_source
from film_pipeline.live_runtime import file_sha256, utc_now
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_canonical_ui import (
    DEFAULT_NATIVE_UI,
    prepare_inputs,
    verify_chip,
    verify_settings,
)
from film_pipeline.providers.flow_media import parse_media_resource
from film_pipeline.providers.flow_reference_binding import (
    attest_existing_reference,
    verify_attestation,
)
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
    OwnerAuthRequired,
)
from film_pipeline.providers.flow_reference_transport import image_comparison
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from film_pipeline.providers.flow_r2v_prompt import MARKER_RE
from film_pipeline.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPO = Path("D:/AI FILM MAKER/AI-Film-Pipeline")
SOURCE_STORE = SOURCE_REPO / "projects/character_continuity/reference_qualification_20260930/runtime.sqlite"

QUAL_DIR = ROOT / "projects/flow_forensic_dola_20261002"
FG1_DIR = QUAL_DIR / "fg1"
LEDGER_DIR = QUAL_DIR / "generate_ledger"
DATABASE = QUAL_DIR / "runtime.sqlite"

PROJECT_ID = "f6b40e79-d6f8-4354-80ae-c863260e96f5"
ACCOUNT_ID = "project_scoped_unverified_account"
REFERENCE_MEDIA_ID = "347f9951-5bbc-4910-b6fd-3a17c74e29d2"
REFERENCE_ASSET_ID = "asset_88e3948cd04cd4651ff49034e5d38d6d97109a6ec7e28d12d0e01dd303f5396c"
REFERENCE_FILENAME_CANDIDATE = "story-auto-reference.png"
MODEL = contract.MODEL_VEO_3_1_LITE
SHOT_ID = "FLOW_FORENSIC_FG1_001"
STARTED_AT = "2026-10-02T02:00:00+00:00"
PROFILE = Path("D:/Video/AutoVideoPipeline/scratch/google_flow_slice0011_manual")
CANARY_ID = "F-G1-FLOW-FORENSIC-TO-DOLA-001"

MAX_GENERATE_COUNT = 3
OBSERVATION_WINDOW_S = 1500
POLL_INTERVAL_S = 60
RELEASE_WAIT_S = 45

HYPOTHESIS = (
    "On project f6b40e79, provider-native UI R2V with the historically successful "
    "reference 347f9951 (the only reference whose UI release ever produced a "
    "backend-attributable output on this project) admits a backend-attributable "
    "output NOW. Distinct from LIVE-RUNTIME-QUAL-001 G1 (reference 53b5a413, "
    "EXTERNAL_EFFECT_UNRESOLVED, never retried)."
)

MUTATION_BLOCKED = "**/batchexecute?*"


def write_new(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise OwnerAmbiguityGate(f"immutable evidence file already exists: {path.name}")
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json(value))
        stream.flush()
        os.fsync(stream.fileno())


def source_store_sha() -> str:
    if not SOURCE_STORE.is_file():
        raise OwnerAmbiguityGate("historical qualification store unavailable")
    return file_sha256(SOURCE_STORE)


def historical_unchanged(expected: str) -> bool:
    return source_store_sha() == expected


def ledger_state() -> dict:
    init = LEDGER_DIR / "L0_INIT.json"
    if not init.is_file():
        raise OwnerAmbiguityGate("authority ledger not initialized")
    consumed = [json.loads(entry.read_text(encoding="utf-8"))
                for entry in sorted(LEDGER_DIR.glob("*_CONSUMED.json"))]
    return {"init": json.loads(init.read_text(encoding="utf-8")), "consumed": consumed}


def require_generate_budget(count_needed: int) -> None:
    state = ledger_state()
    if len(state["consumed"]) + count_needed > state["init"]["max_generate_count"]:
        raise OwnerAmbiguityGate("GENERATE_BUDGET_EXHAUSTED")


def flow_capabilities() -> ProviderCapabilities:
    payload = {
        "profile_version": "flow-forensic-fg1-v1",
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
    return shot.model_copy(update={
        "shot_id": SHOT_ID,
        "references": References(other_asset_ids=[REFERENCE_ASSET_ID])})


def open_session() -> FlowReferenceRpcSession:
    if not PROFILE.is_dir():
        raise OwnerAmbiguityGate("qualified browser profile unavailable")
    return FlowReferenceRpcSession(profile_path=PROFILE, project_id=PROJECT_ID, native_ui=True)


def load_attestation(store: SQLiteStore) -> dict:
    evidence = FG1_DIR / "attestation"
    rows = sorted(evidence.glob("refbind_*.json"))
    if len(rows) != 1:
        raise OwnerAmbiguityGate("FG1 attestation evidence not unique")
    attestation = json.loads(rows[0].read_text(encoding="utf-8"))
    return verify_attestation(store, store.read_reference_asset(REFERENCE_ASSET_ID),
                              attestation, media_id=REFERENCE_MEDIA_ID,
                              project_id=PROJECT_ID, evidence_dir=evidence)


def reference_row(records):
    matches = [row for row in records if row[0].lower() == REFERENCE_MEDIA_ID.lower()]
    if len(matches) != 1:
        raise OwnerAmbiguityGate("REFERENCE_ROW_NOT_UNIQUE_IN_CATALOG")
    return matches[0]


def derive_provider_filename(records) -> str:
    strings = list(contract._strings(reference_row(records)))
    if REFERENCE_FILENAME_CANDIDATE in strings:
        return REFERENCE_FILENAME_CANDIDATE
    pngs = {s for s in strings if s.lower().endswith(".png")}
    if len(pngs) == 1:
        return pngs.pop()
    if not pngs:
        return ""
    raise OwnerAmbiguityGate("REFERENCE_FILENAME_AMBIGUOUS_IN_CATALOG")


class PreflightMutationBlock:
    def __init__(self):
        self.blocked = []

    def route(self, route):
        request = route.request
        body = request.post_data or ""
        if any(token in request.url or token in body for token in ("MZZa6b", "maseQ")):
            self.blocked.append({"method": request.method})
            try:
                route.abort()
            finally:
                raise OwnerAmbiguityGate("PREFLIGHT_MUTATION_BLOCKED")
        route.continue_()


def stage_setup() -> dict:
    source_sha = source_store_sha()
    QUAL_DIR.mkdir(parents=True, exist_ok=True)
    if not DATABASE.exists():
        shutil.copyfile(SOURCE_STORE, DATABASE)
    if file_sha256(DATABASE) != source_sha:
        raise OwnerAmbiguityGate("canary custody copy differs from pinned source store")
    write_new(LEDGER_DIR / "L0_INIT.json", {
        "checkpoint": "C0_BASELINE",
        "package_head": "570ca85e83cf55c272a97938399051a87c3d85ba",
        "accepted_base": "85e88cc87e0cd9f0a523fe399072655c20f700b4",
        "branch": "zcode/flow-forensic-dola-fallback-001",
        "flow_forensics_started_at": "2026-10-02T01:21:50+00:00",
        "flow_forensics_deadline": "2026-10-02T05:21:50+00:00",
        "regression": "489 passed",
        "max_generate_count": MAX_GENERATE_COUNT,
        "generate_count": 0,
        "custody_source_store_sha256": source_sha,
        "custody_source_store": "reference_qualification_20260930/runtime.sqlite (verbatim copy)",
    })
    store = SQLiteStore(DATABASE)
    asset = store.read_reference_asset(REFERENCE_ASSET_ID)
    if file_sha256(Path(asset.uri_or_path)) != asset.sha256:
        raise OwnerAmbiguityGate("geometric reference source bytes changed")
    return {"custody_source_sha256": source_sha, "ledger": ledger_state()["init"]}


def stage_preflight() -> dict:
    if (FG1_DIR / "preflight.json").exists():
        report = json.loads((FG1_DIR / "preflight.json").read_text(encoding="utf-8"))
        if report["gate"] != "L1_PREFLIGHT_PASS":
            raise OwnerAmbiguityGate("preflight did not pass; no live work may proceed")
        return report
    store = SQLiteStore(DATABASE)
    require_generate_budget(1)
    report = {"stage": "FG1_PREFLIGHT", "gate": "OWNER_GATE",
              "project_id": PROJECT_ID, "reference_media_id": REFERENCE_MEDIA_ID,
              "model": MODEL, "ledger": ledger_state()["init"],
              "provider_reads": {}, "blocked_mutations": []}
    blocker = PreflightMutationBlock()
    try:
        with open_session() as session:
            session.page.context.route(MUTATION_BLOCKED, blocker.route)
            meta = session.metadata()
            report["session"] = contract.sanitize_session(meta, PROJECT_ID)
            records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            report["provider_reads"]["catalog"] = True
            report["catalog_ids"] = sorted(row[0].lower() for row in records)
            report["provider_filename"] = derive_provider_filename(records)
            # Fresh attestation from a live readback; content-verified vs the
            # immutable geometric source and the copied VERIFIED receipt.
            receipt = ReferenceUploadStore(store.path).read_verified(
                "flow_veo", PROJECT_ID, ACCOUNT_ID,
                store.read_reference_asset(REFERENCE_ASSET_ID))
            if receipt is None or receipt["media_id"] != REFERENCE_MEDIA_ID:
                raise OwnerAmbiguityGate("verified 347f9951 receipt unavailable")
            media = session.bound_media(REFERENCE_MEDIA_ID, "image")
            if media.evidence["sha256"] != receipt["provider_media_sha256"]:
                raise OwnerAmbiguityGate("reference remote bytes changed since upload verification")
            comparison = image_comparison(
                Path(store.read_reference_asset(REFERENCE_ASSET_ID).uri_or_path).read_bytes(),
                media.data)
            if not comparison["strong_match"]:
                raise OwnerAmbiguityGate("reference content no longer matches immutable source")
            attestation = attest_existing_reference(
                store, store.read_reference_asset(REFERENCE_ASSET_ID), session,
                account_id=ACCOUNT_ID, media_id=REFERENCE_MEDIA_ID,
                evidence_dir=FG1_DIR / "attestation")
            report["attestation_id"] = attestation["attestation_id"]
            report["provider_reads"]["reference_media"] = True
            if session.page.locator("button.chip-container img.chip-image").count():
                verify_chip(session.page, REFERENCE_MEDIA_ID)
                report["reference_chip_present"] = True
            else:
                report["reference_chip_present"] = False
            verify_settings(session.page)
            report["native_ui_settings_readback"] = list(DEFAULT_NATIVE_UI.settings_tokens)
            report["gate"] = "L1_PREFLIGHT_PASS"
    except OwnerAuthRequired:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
    except OwnerAmbiguityGate as exc:
        report["gate"] = "OWNER_GATE"
        report["diagnostic"] = str(exc)
    finally:
        report["blocked_mutations"] = blocker.blocked
        report["historical_store_unchanged"] = historical_unchanged(
            ledger_state()["init"]["custody_source_store_sha256"])
        write_new(FG1_DIR / "preflight.json", report)
    print(json.dumps({"stage": "fg1_preflight", "gate": report["gate"]}), flush=True)
    if report["gate"] != "L1_PREFLIGHT_PASS":
        raise SystemExit(1)
    return report


class LiveDownloadTransport:
    def __init__(self, session, resource, output_id):
        self.session = session
        self.resource = resource
        self.output_id = output_id
        self.fetches = 0

    async def fetch(self, job, output_id, destination):
        if output_id != self.output_id:
            raise OwnerAmbiguityGate("ACQUISITION_OUTPUT_IDENTITY_MISMATCH")
        self.fetches += 1
        response = self.session.page.context.request.get(
            self.resource.url, timeout=60000, max_redirects=0, max_retries=0)
        try:
            if response.status != 200:
                raise OwnerAmbiguityGate("OUTPUT_MEDIA_UNAVAILABLE")
            data = response.body()
        finally:
            response.dispose()
        max_bytes = 256 * 1024 * 1024
        if not data or len(data) > max_bytes:
            raise OwnerAmbiguityGate("OUTPUT_MEDIA_INVALID")
        destination.write_bytes(data)
        return destination


def _release_wait(guard, session, deadline_s: float) -> None:
    end = time.monotonic() + deadline_s
    while guard.sent != 1 and guard.error is None and time.monotonic() < end:
        session.page.wait_for_timeout(250)


def _observe(session, runtime, frozen, guard, *, poll_version: str, report: dict):
    window_end = time.monotonic() + OBSERVATION_WINDOW_S
    next_poll = time.monotonic() + 15.0
    polls = 0
    last_progress = 0.0
    pending_codes = []
    while time.monotonic() < window_end:
        if guard.error is not None:
            report.setdefault("post_release_guard_blocks", [])
            if guard.error not in [e.get("cause") for e in report["post_release_guard_blocks"]]:
                report["post_release_guard_blocks"].append(
                    {"cause": guard.error, "observed_at_poll": polls})
        now = time.monotonic()
        if now >= next_poll:
            polls += 1
            next_poll = now + POLL_INTERVAL_S
            try:
                records = session.catalog(contract_version=poll_version)
            except FlowReferenceRpcDrift:
                report["catalog_read_failures"] = report.get("catalog_read_failures", 0) + 1
                continue
            try:
                output_id = runtime.attribute_backend_output(frozen, records)
            except contract.ContractError as exc:
                code = str(exc)
                if code == "OUTPUT_STATUS_UNQUALIFIED":
                    if code not in pending_codes:
                        pending_codes.append(code)
                        report.setdefault("pending_observations", []).append(
                            {"code": code, "at_poll": polls})
                    continue
                raise OwnerAmbiguityGate("BACKEND_ATTRIBUTION_MATERIAL_DISAGREEMENT: " + code)
            if output_id is None:
                if now - last_progress >= 240:
                    print(json.dumps({"stage": "reconciliation_pending",
                                      "elapsed_s": round(now - (window_end - OBSERVATION_WINDOW_S), 1),
                                      "polls": polls}), flush=True)
                    last_progress = now
                continue
            report["reconciliation_polls"] = polls
            return output_id, records
        session.page.wait_for_timeout(1000)
    raise OwnerAmbiguityGate("EXTERNAL_EFFECT_UNRESOLVED")


def _review_packet(store: SQLiteStore, asset, frozen, out_dir: Path) -> dict:
    from PIL import Image, ImageDraw
    from film_pipeline.qc import QCStore, evidence, technical_evidence
    from film_pipeline.qc_media import make_review_media
    from film_pipeline.qc_runner import exact_lineage
    _, shot, _ = exact_lineage(store.path, frozen.attempt.generation_attempt_id,
                               frozen.job.provider_job_id, asset.asset_id)
    technical, metadata = technical_evidence(shot, asset)
    if not metadata or any(row.verdict != "pass" for row in technical):
        raise OwnerAmbiguityGate("technical QC failed")
    criteria = {
        "visual": (("reference_and_prompt_lock", "Output consistent with the reference image and frozen prompt?"),),
        "continuity": (("single_composition", "One stable composition across the full 8 seconds?"),),
        "editorial": (("technical_stability", "No encoding artifacts blocking editorial use?"),)}
    rows, media = make_review_media(asset, out_dir / "frames", criteria=criteria)
    reference = store.read_reference_asset(REFERENCE_ASSET_ID)
    descriptor, staging_name = tempfile.mkstemp(suffix=".png", dir=out_dir)
    os.close(descriptor)
    staging = Path(staging_name)
    try:
        process = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(asset.duration_s / 2),
             "-i", asset.uri_or_path, "-frames:v", "1", str(staging)],
            capture_output=True, timeout=60)
        if process.returncode or not staging.stat().st_size:
            raise OwnerAmbiguityGate("full-resolution comparison frame unavailable")
        middle = out_dir / ("middle_" + file_sha256(staging) + ".png")
        try:
            os.link(staging, middle)
        except FileExistsError:
            if file_sha256(middle) != file_sha256(staging):
                raise OwnerAmbiguityGate("middle-frame evidence collision")
    finally:
        staging.unlink(missing_ok=True)
    sheet = Image.new("RGB", (1600, 500), "#151a24")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), "EXACT REFERENCE", fill="white")
    draw.text((812, 12), "F-G1 GENERATED OUTPUT - sampled middle frame", fill="white")
    for x, source in ((0, reference.uri_or_path), (800, middle)):
        with Image.open(source) as image:
            sheet.paste(image.convert("RGB").resize((800, 450)), (x, 40))
    pair = out_dir / "reference_vs_fg1_output.png"
    sheet.save(pair)
    rows.append(evidence(asset=asset, evaluator_type="ffmpeg",
        evaluator_version="flow-forensic-fg1-review-v1", gate="continuity",
        criterion="reference_vs_output", verdict="uncertain",
        observation="Owner review required; sampled frames do not establish all-frame identity.",
        source_artifacts=[{"path": reference.uri_or_path, "sha256": reference.sha256},
                          {"path": str(pair), "sha256": file_sha256(pair)}]))
    record, _disposition = QCStore(store).save(asset, technical + rows)
    if record.report["decision"] != "needs_human_review":
        raise OwnerAmbiguityGate("F-G1 must remain unselected for Owner review")
    return {"qc_report_id": record.report["qc_report_id"], "technical_pass": True,
            "comparison": str(pair), "comparison_sha256": file_sha256(pair),
            "sampled_media": media, "selected_take_created": False}


def _restart_proofs(store: SQLiteStore, runtime: FlowR2VShotRuntime, frozen, attestation: dict) -> dict:
    job_id = frozen.job.provider_job_id
    fresh_job = store.read_provider_job(job_id)
    facts = [fact["kind"] for fact in store.read_dispatch_facts(job_id)]
    if fresh_job.dispatch_count != 1:
        raise OwnerAmbiguityGate("RESTART_PROOF_DISPATCH_COUNT_DRIFT")
    recovery = runtime.recovery(frozen)
    reserve_rejected = None
    try:
        runtime.reserve(frozen, attestation=attestation, evidence_dir=FG1_DIR / "attestation")
        raise OwnerAmbiguityGate("RESTART_PROOF_RE_RESERVE_UNEXPECTEDLY_ALLOWED")
    except OwnerAmbiguityGate as exc:
        reserve_rejected = str(exc)
        if "MUTATION_ALREADY_CONSUMED" not in reserve_rejected:
            raise
    fresh_runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID, account_id=ACCOUNT_ID, model=MODEL)
    dormant = FlowReferenceRpcSession(profile_path=PROFILE, project_id=PROJECT_ID, native_ui=True)
    resumed = fresh_runtime.freeze(ordinary_shot(), flow_capabilities(),
        reference_asset=store.read_reference_asset(REFERENCE_ASSET_ID),
        reference_media_id=REFERENCE_MEDIA_ID,
        reference_filename=frozen.job.correlation_evidence["reference_binding"].get("provider_filename", ""),
        catalog_source=qualify_flow_catalog_source(dormant), started_at="2099-01-01T00:00:00+00:00")
    if resumed.job.provider_job_id != job_id:
        raise OwnerAmbiguityGate("RESTART_RESUME_CHANGED_JOB_IDENTITY")
    if dormant.rpc_call_counts:
        raise OwnerAmbiguityGate("RESTART_PERFORMED_PROVIDER_READS")
    return {"recovery_classification": recovery.classification, "recovery_action": recovery.action,
            "recovery_may_submit": recovery.may_submit,
            "reserve_rejected_with": reserve_rejected, "resumed_job_id": resumed.job.provider_job_id,
            "journal_kinds": facts}


def run_release() -> dict:
    out_dir = FG1_DIR
    if (out_dir / "live_result.json").exists() or (out_dir / "reconcile_result.json").exists():
        raise OwnerAmbiguityGate("durable F-G1 result already recorded; no redispatch")
    preflight = stage_preflight()
    store = SQLiteStore(DATABASE)
    require_generate_budget(1)
    custody_sha = ledger_state()["init"]["custody_source_store_sha256"]
    runtime = FlowR2VShotRuntime(store, project_id=PROJECT_ID, account_id=ACCOUNT_ID, model=MODEL)
    report = {"stage": "C3_FG1_RELEASE", "gate": "OWNER_GATE_LOCAL_FAILURE",
              "canary_id": CANARY_ID, "hypothesis": HYPOTHESIS,
              "project_id": PROJECT_ID, "account_id": ACCOUNT_ID,
              "reference_media_id": REFERENCE_MEDIA_ID, "model": MODEL,
              "shot_id": SHOT_ID, "generate_clicks": 0,
              "provider_generate_requests": 0, "observed_generate_requests": 0,
              "retries": 0, "uploads": 0, "direct_mzza6b_submits": 0}
    session = open_session()
    blocker = PreflightMutationBlock()
    job_id = None
    try:
        with session as session:
            session.page.context.route(MUTATION_BLOCKED, blocker.route)
            capability = qualify_flow_catalog_source(session)
            frozen = runtime.freeze(ordinary_shot(), flow_capabilities(),
                reference_asset=store.read_reference_asset(REFERENCE_ASSET_ID),
                reference_media_id=REFERENCE_MEDIA_ID,
                reference_filename=preflight["provider_filename"],
                catalog_source=capability, started_at=STARTED_AT)
            job_id = frozen.job.provider_job_id
            prompt = frozen.job.correlation_evidence["prompt"]
            report.update(provider_job_id=job_id,
                          generation_attempt_id=frozen.attempt.generation_attempt_id,
                          provider_prompt=prompt,
                          pre_dispatch_snapshot=frozen.job.pre_dispatch_snapshot)
            write_new(out_dir / "frozen_intent.json", {
                "canary_id": CANARY_ID, "provider_job_id": job_id,
                "generation_attempt_id": frozen.attempt.generation_attempt_id,
                "prompt": prompt, "prompt_sha256": sha256(prompt),
                "correlation_marker": frozen.job.correlation_evidence["correlation_marker"],
                "pre_dispatch_snapshot": frozen.job.pre_dispatch_snapshot,
                "reference_binding": frozen.job.correlation_evidence["reference_binding"]})
            write_new(LEDGER_DIR / "FG1_PRECLAIM.json", {
                "canary_id": CANARY_ID, "provider_job_id": job_id, "shot_id": SHOT_ID,
                "hypothesis": HYPOTHESIS,
                "preconditions": {"preflight": "L1_PREFLIGHT_PASS",
                                  "reference_chain": "attested-fresh",
                                  "distinct_from": "LIVE-RUNTIME-QUAL-001 G1 (53b5a413)"},
                "current_generate_count": len(ledger_state()["consumed"]),
                "max_generate_count": MAX_GENERATE_COUNT})
            attestation = load_attestation(store)
            runtime.reserve(frozen, attestation=attestation, evidence_dir=out_dir / "attestation")
            records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            if sorted(row[0].lower() for row in records) != frozen.job.pre_dispatch_snapshot["catalog_ids"]:
                raise OwnerAmbiguityGate("BASELINE_CHANGED_BEFORE_UI_PREPARATION")
            ui = prepare_inputs(session, records, media_id=REFERENCE_MEDIA_ID, prompt=prompt)
            report["ui_preflight"] = ui
            verify_attestation(store, store.read_reference_asset(REFERENCE_ASSET_ID),
                               attestation, media_id=REFERENCE_MEDIA_ID,
                               project_id=PROJECT_ID, evidence_dir=out_dir / "attestation")
            write_new(out_dir / "pre_generate_proof.json", {
                "provider_job_id": job_id, "ui": ui, "prompt_sha256": sha256(prompt)})
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
                    response_holder["diagnostics"] = {"classification": "UNPARSEABLE", "advisory_only": True}
            session.page.on("response", on_response)
            session.page.context.unroute(MUTATION_BLOCKED, blocker.route)
            guard = runtime.arm_native_guard(frozen)
            session.page.context.route(MUTATION_BLOCKED, guard.route)
            verify_chip(session.page, REFERENCE_MEDIA_ID)
            editor = session.page.locator('div.ProseMirror[contenteditable="true"]')
            if editor.count() != 1 or editor.inner_text() != prompt:
                raise OwnerAmbiguityGate("PROMPT_CHANGED_AT_MUTATION_BOUNDARY")
            store.record_dispatch_fact(job_id, "PROMPT_VERIFIED", {"prompt_sha256": sha256(prompt)})
            store.record_dispatch_fact(job_id, "CLICK_ARMED", {})
            guard.armed = True
            report["generate_clicks"] = 1
            session.page.locator("button.generate-icon-button").click(timeout=15000)
            print(json.dumps({"stage": "one_native_generate_click_issued"}), flush=True)
            _release_wait(guard, session, RELEASE_WAIT_S)
            report["observed_generate_requests"] = guard.seen
            if guard.error is not None:
                report["gate"] = "OWNER_GATE_REQUEST_NEVER_RELEASED"
                report["blocked_request_cause"] = guard.error
                write_new(LEDGER_DIR / "FG1_REQUEST_BLOCKED.json",
                          {"cause": guard.error, "seen": guard.seen, "sent": guard.sent})
                raise OwnerAmbiguityGate(guard.error)
            if guard.sent != 1:
                report["gate"] = "OWNER_GATE_REQUEST_NEVER_RELEASED"
                raise OwnerAmbiguityGate("EXACT_NATIVE_REQUEST_NOT_OBSERVED")
            write_new(LEDGER_DIR / "FG1_CONSUMED.json", {
                "canary_id": CANARY_ID, "provider_job_id": job_id,
                "released_at": utc_now(), "guard_sent": guard.sent,
                "hypothesis": HYPOTHESIS,
                "note": "F-G1 Generate authority consumed; never retry authority."})
            report["provider_generate_requests"] = guard.sent
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            print(json.dumps({"stage": "generate_released_authority_consumed",
                              "provider_job_id": job_id}), flush=True)
            end = time.monotonic() + 30
            while "status" not in response_holder and time.monotonic() < end:
                session.page.wait_for_timeout(250)
            report["provider_response"] = response_holder
            if "status" in response_holder:
                runtime.observe_provider_response(frozen, status=response_holder["status"])
                counts = (response_holder.get("diagnostics") or {}).get("type_counts") or {}
                if any(count for key, count in counts.items() if key != "null"):
                    runtime.observe_provider_acceptance(frozen, provider_reference="MZZa6b_wire_ack")
            output_id, records = _observe(session, runtime, frozen, guard,
                                          poll_version=contract.CONTRACT_VERSION_2026_10_01,
                                          report=report)
            report["output_identity"] = output_id
            print(json.dumps({"stage": "backend_output_attributed", "output_id": output_id}), flush=True)
            marker = frozen.job.correlation_evidence["correlation_marker"]
            marker_rows = [row for row in records if marker in " ".join(contract._strings(row))]
            if len(marker_rows) != 1:
                raise OwnerAmbiguityGate("BACKEND_MARKER_ROW_NOT_UNIQUE")
            echo_texts = [s for s in contract._strings(marker_rows[0])
                          if MARKER_RE.findall(s) == [marker]]
            report["backend_prompt_echo_exact"] = prompt in echo_texts
            if not report["backend_prompt_echo_exact"]:
                raise OwnerAmbiguityGate("BACKEND_EXACT_PROMPT_MISMATCH")
            payload = session.rpc(contract.RPC_MEDIA, contract.build_media(output_id))
            resource = parse_media_resource(payload, media_id=output_id,
                                            project_id=PROJECT_ID, kind="video")
            asset = runtime.acquire(frozen,
                transport=LiveDownloadTransport(session, resource, output_id),
                destination_dir=out_dir / "videos", media_payload=payload)
            report["asset"] = asset.model_dump(mode="json")
            print(json.dumps({"stage": "asset_acquired", "asset_id": asset.asset_id,
                              "sha256": asset.sha256}), flush=True)
            report["review"] = _review_packet(store, asset, frozen, out_dir)
            report["restart_proofs"] = _restart_proofs(store, runtime, frozen, attestation)
            report["rpc_calls"] = dict(session.rpc_call_counts)
            report["direct_mzza6b_submits"] = session.rpc_call_counts.get("MZZa6b", 0)
            report["reference_uploads"] = session.rpc_call_counts.get("maseQ", 0)
            report["gate"] = "FG1_PROVEN"
    except OwnerAuthRequired:
        report["gate"] = "OWNER_GATE_AUTH_REQUIRED"
        report["stop_type"] = "OwnerAuthRequired"
    except OwnerAmbiguityGate as exc:
        report["stop_type"] = type(exc).__name__
        report["diagnostic"] = str(exc)
        if report["gate"] != "OWNER_GATE_REQUEST_NEVER_RELEASED":
            if report.get("provider_generate_requests") == 1:
                report["gate"] = "OWNER_AMBIGUITY_GATE"
                record_ambiguous_evidence(store, job_id)
            else:
                report["gate"] = "OWNER_GATE: " + str(exc)
    except Exception as exc:
        report["stop_type"] = type(exc).__name__
        if report.get("provider_generate_requests") == 1:
            report["gate"] = "OWNER_AMBIGUITY_GATE"
            record_ambiguous_evidence(store, job_id)
        else:
            report["gate"] = "OWNER_GATE_LOCAL_FAILURE"
    finally:
        if job_id is not None:
            fresh = store.read_provider_job(job_id)
            report["final_dispatch_count"] = fresh.dispatch_count
            report["dispatch_journal_kinds"] = [f["kind"] for f in store.read_dispatch_facts(job_id)]
        report["ledger_consumed"] = [entry["canary_id"] for entry in ledger_state()["consumed"]]
        report["historical_store_unchanged"] = historical_unchanged(custody_sha)
        if not report["historical_store_unchanged"]:
            report["gate"] = "OWNER_AMBIGUITY_GATE"
        write_new(out_dir / "live_result.json", report)
    print(json.dumps({"gate": report["gate"], "provider_job_id": report.get("provider_job_id"),
                      "output": str(out_dir / "live_result.json")}), flush=True)
    return report


def record_ambiguous_evidence(store: SQLiteStore, job_id) -> None:
    if job_id is None:
        return
    try:
        if store.read_provider_job(job_id).dispatch_count:
            if not any(f["kind"] == "AMBIGUOUS_EVIDENCE" for f in store.read_dispatch_facts(job_id)):
                store.record_dispatch_fact(job_id, "AMBIGUOUS_EVIDENCE",
                                           {"diagnostic": "flow_forensic_fg1_owner_gate"})
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["setup", "preflight", "release"])
    args = parser.parse_args()
    if args.stage == "setup":
        print(json.dumps(stage_setup(), indent=1))
    elif args.stage == "preflight":
        print(json.dumps({k: v for k, v in stage_preflight().items()
                          if k in ("gate", "catalog_ids", "provider_filename", "attestation_id")}, indent=1))
    else:
        run_release()
