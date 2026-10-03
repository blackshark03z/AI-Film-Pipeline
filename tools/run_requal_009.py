"""FLOW-UPLOAD-CONTRACT-REQUAL-009 — prospective qualification canaries.

ONE mutation authority domain for the whole package:
FLOW-UPLOAD-CONTRACT-REQUAL-009. No sub-scopes. Any TRUE_AMBIGUITY /
OWNER_AMBIGUITY_GATE / latch in ANY live step permanently kills ALL
remaining provider mutation authority for the package — no second canary,
no continuation, no re-proof, no scope workaround.

Frozen classifier (verified from repo before live work):
    upload-response-class-2026-10-03.2
    ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1
NO classifier/fingerprint/threshold change between Canary A and Canary B.

Budget: 2 qualification uploads, 1 conditioned Generate, 4 re-proof
Generates. Zero retries. Zero additional uploads. Zero MZZa6b.

Commands: canaryA | canaryB | status
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
tools_path = str(Path(__file__).resolve().parent)
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

RUN_DIR = ROOT / "projects/flow_upload_contract_requal_009"
SCOPE_ID = "FLOW-UPLOAD-CONTRACT-REQUAL-009"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"
SEQ_DIR = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"
MAX_QUAL_UPLOADS = 2
MAX_CONDITIONED_GENERATES = 1
MAX_REPROOF_GENERATES = 4
RECONCILE_ROUNDS = 12
RECONCILE_SLEEP_S = 45
TERMINAL_RECONCILE_GATES = ("multiple strong", "content mismatch",
                            "contract drift", "disagrees with Owner evidence")
# Durably pre-existing unresolved catalog row (proven in Package-007 F2
# reconcile evidence, 2026-10-03T07:45 — BEFORE any canary upload).
PREEXISTING_UNRESOLVED = ["58bd411e-f19f-44a0-bee1-7717cfde123e"]

SOURCES = {
    "canaryA": {"slot": "SEQ7_E3", "scene": "scene_SCENE_E_RIDGE_APPROACH"},
    "canaryB": {"slot": "SEQ7_F3", "scene": "scene_SCENE_F_STORM_GATE"},
}

from film_pipeline.live_runtime import Asset, utc_now
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcSession, OwnerAuthRequired)
from film_pipeline.providers.flow_reference_transport import FlowReferenceTransport
from film_pipeline.providers.flow_reference_upload import (
    OwnerAmbiguityGate, ReferenceUploadStore, _key)
from film_pipeline.providers.flow_upload_classifier import (
    LIVE_PENDING_SKELETON_FINGERPRINT, RESPONSE_CLASS_VERSION,
    QualifiedUploadPending)
from mutation_authority import MutationAuthority


def write_durable(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)


def authority() -> MutationAuthority:
    return MutationAuthority(RUN_DIR, SCOPE_ID)


def ledger() -> dict:
    path = RUN_DIR / "mutation_ledger.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"uploads_used": [], "conditioned_generates": [],
            "reproof_generates": [], "max_uploads": MAX_QUAL_UPLOADS,
            "max_conditioned_generates": MAX_CONDITIONED_GENERATES,
            "max_reproof_generates": MAX_REPROOF_GENERATES, "events": []}


def save_ledger(data: dict) -> None:
    write_durable(RUN_DIR / "mutation_ledger.json", data)


def open_session():
    return FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                   project_id=PROJECT_ID, native_ui=True)


def classifier_identity() -> dict:
    blob = subprocess.run(
        ["git", "rev-parse",
         f"HEAD:src/film_pipeline/providers/flow_upload_classifier.py"],
        cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
    return {"class_version": RESPONSE_CLASS_VERSION,
            "fingerprint": LIVE_PENDING_SKELETON_FINGERPRINT,
            "classifier_blob_sha": blob}


def extract_last_frame(asset_path: Path, destination: Path) -> dict:
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
            "sha256": hashlib.sha256(data).hexdigest(),
            "width": width, "height": height, "file_size": len(data),
            "source_asset": str(asset_path)}


def load_source_asset(canary: str) -> dict:
    slot = SOURCES[canary]["slot"]
    scene = SOURCES[canary]["scene"]
    result = json.loads((SEQ_DIR / scene / f"shot_{slot}" /
                         "result.json").read_text(encoding="utf-8"))
    if result.get("gate") != "SHOT_PROVEN":
        raise OwnerAmbiguityGate("canary source slot is not SHOT_PROVEN")
    asset = result["asset"]
    video = Path(asset["uri_or_path"])
    if hashlib.sha256(video.read_bytes()).hexdigest() != asset["sha256"]:
        raise OwnerAmbiguityGate("canary source bytes changed since Package-007")
    return asset


def fail(report: dict, code: str, reason: str, exit_code: int) -> None:
    report["result"] = code
    report["diagnostic"] = reason[:400]
    report["finished_at"] = utc_now()
    write_report(report)
    raise SystemExit(exit_code)


def write_report(report: dict) -> None:
    write_durable(RUN_DIR / f"{report['canary']}_report.json", report)
    slim = {k: v for k, v in report.items() if k != "skeleton"}
    print(json.dumps(slim, default=str, ensure_ascii=False)[:1500], flush=True)


def reconcile_until_bound(asset, key, report):
    """Bounded READ-ONLY reconciliation across fresh sessions."""
    auth = authority()
    for attempt in range(1, RECONCILE_ROUNDS + 1):
        report["reconcile_rounds"] = attempt
        write_report(report)
        try:
            with open_session() as session:
                transport = FlowReferenceTransport(
                    ReferenceUploadStore(canary_upload_store(report["canary"])),
                    session, account_id=ACCOUNT_ID,
                    evidence_dir=RUN_DIR / report["canary"] / "evidence",
                    interval_s=5, probes=2)
                receipt = transport.reconcile_only(
                    asset, preexisting_ids=PREEXISTING_UNRESOLVED)
            report["media_id"] = receipt["media_id"]
            report["provider_media_sha256"] = receipt["provider_media_sha256"]
            return receipt
        except OwnerAuthRequired:
            fail(report, "BLOCKED_OWNER_AUTH",
                 "reconciliation session requires Owner sign-in; pending "
                 "state preserved read-only", 2)
        except OwnerAmbiguityGate as exc:
            message = str(exc)
            report.setdefault("reconcile_gates", []).append(message[:200])
            if any(marker in message for marker in TERMINAL_RECONCILE_GATES):
                auth.promote_pending_to_ambiguity(
                    key, f"terminal reconciliation conflict: {message}")
                fail(report, "CANARY_FAIL_TRUE_AMBIGUITY",
                     f"terminal reconciliation conflict: {message}", 3)
        if attempt < RECONCILE_ROUNDS:
            time.sleep(RECONCILE_SLEEP_S)
    return None


def canary_upload_store(canary: str) -> Path:
    return RUN_DIR / canary / "upload_1.sqlite"


def run_canary(canary: str) -> dict:
    auth = authority()
    canary_dir = RUN_DIR / canary
    report = {"canary": canary, "phase": "preflight",
              "reconcile_rounds": 0, "started_at": utc_now(),
              "classifier": classifier_identity()}
    write_report(report)

    # The single authority domain gates EVERY entry.
    auth.check_mutation_allowed(f"qualification_upload_{canary}")
    data = ledger()
    if len(data["uploads_used"]) >= MAX_QUAL_UPLOADS:
        raise OwnerAmbiguityGate("qualification upload budget exhausted (2 max)")

    slot = SOURCES[canary]["slot"]
    source = load_source_asset(canary)
    frame_path = canary_dir / "frame.png"
    if frame_path.exists() and (canary_dir / "frame_asset.json").exists():
        frame = json.loads((canary_dir / "frame_asset.json")
                           .read_text(encoding="utf-8"))
        if hashlib.sha256(frame_path.read_bytes()).hexdigest() != frame["sha256"]:
            raise OwnerAmbiguityGate("canary frame bytes changed since freeze")
    else:
        frame = extract_last_frame(Path(source["uri_or_path"]), frame_path)

    from film_pipeline.store import SQLiteStore
    runtime = SQLiteStore(canary_dir / "runtime.sqlite")
    runtime.initialize()
    frame_asset = Asset(asset_id=f"asset_{canary}_frame",
                        origin="reference", asset_type="image",
                        uri_or_path=str(frame_path.resolve()),
                        sha256=frame["sha256"], mime_type="image/png",
                        width=frame["width"], height=frame["height"],
                        file_size=frame["file_size"],
                        rights_metadata={"source_kind": "last_frame_of_acquired_asset",
                                         "from_shot": slot, "for_shot": canary,
                                         "source_asset_sha256": source["sha256"]})
    runtime.save_reference_asset(frame_asset)
    write_durable(canary_dir / "frame_asset.json",
                  frame_asset.model_dump(mode="json"))

    store = ReferenceUploadStore(canary_upload_store(canary))
    key = _key("flow_veo", PROJECT_ID, ACCOUNT_ID, frame_asset)
    report.update({"phase": "upload", "slot": slot,
                   "frame_sha256": frame["sha256"],
                   "source_asset_sha256": source["sha256"],
                   "reservation_id": key,
                   "upload_store": str(canary_upload_store(canary)),
                   "expected_response_class": "maseQ-200-live-skeleton",
                   "expected_fingerprint": LIVE_PENDING_SKELETON_FINGERPRINT})
    write_durable(canary_dir / "frozen_intent.json", {
        "canary": canary, "slot": slot, "project_id": PROJECT_ID,
        "account_id": ACCOUNT_ID, "frame_sha256": frame["sha256"],
        "source_asset_sha256": source["sha256"], "reservation_id": key,
        "classifier": report["classifier"],
        "expected_response_class": "maseQ-200-live-skeleton",
        "frozen_at": utc_now()})

    try:
        progress = store.read_progress(key)
    except OwnerAmbiguityGate:
        raise
    receipt = None
    try:
        if progress and progress["effective_state"] not in (
                None, "LOCAL_RESERVED"):
            report["resumed_from_durable_state"] = \
                progress["effective_state"]
            record_upload_custody(canary, slot, key)
        else:
            with open_session() as session:
                records = session.catalog()
                report["baseline_catalog_rows"] = len(records)
                report["baseline_fingerprint"] = session.catalog_fingerprint
                transport = FlowReferenceTransport(
                    store, session, account_id=ACCOUNT_ID,
                    evidence_dir=canary_dir / "evidence",
                    interval_s=5, probes=2)
                try:
                    receipt = transport.ensure_verified(frame_asset)
                    # Direct-identity envelope: NOT the frozen pending class.
                    # Not an ambiguity (no uncertainty) — bind, record the
                    # deviation, and stop live qualification honestly.
                    record_upload_custody(canary, slot, key)
                    report["response_class"] = "QUALIFIED_COMPLETED"
                    report["media_id"] = receipt["media_id"]
                    report["provider_media_sha256"] = \
                        receipt["provider_media_sha256"]
                    report["result"] = "CANARY_COMPLETED_NOT_PENDING"
                    report["diagnostic"] = (
                        "response classified QUALIFIED_COMPLETED (direct "
                        "identity envelope), which does not match the frozen "
                        "pending class; no ambiguity occurred, but the "
                        "pending path was not exercised — live qualification "
                        "stops without latch")
                    report["finished_at"] = utc_now()
                    write_report(report)
                    raise SystemExit(5)
                except QualifiedUploadPending as pending:
                    record_upload_custody(canary, slot, key)
                    report["response_class"] = "QUALIFIED_PENDING"
                    report["skeleton_fingerprint"] = pending.fingerprint
                    if pending.fingerprint != LIVE_PENDING_SKELETON_FINGERPRINT:
                        auth.latch("UPLOAD_RESPONSE_SHAPE_DRIFT",
                                   "pending skeleton differs from the frozen "
                                   "class fingerprint")
                        fail(report, "CANARY_FAIL_RESPONSE_DRIFT",
                             "pending fingerprint drift vs frozen class", 3)
                    auth.enter_upload_pending(
                        key, pending.fingerprint,
                        f"{canary} qualified pending (frozen class)")
                except OwnerAmbiguityGate as exc:
                    record_upload_custody(canary, slot, key)
                    auth.latch("UPLOAD_RESPONSE_AMBIGUOUS", str(exc))
                    fail(report, "CANARY_FAIL_TRUE_AMBIGUITY", str(exc), 3)
    except OwnerAuthRequired:
        report["result"] = "BLOCKED_OWNER_AUTH"
        report["finished_at"] = utc_now()
        write_report(report)
        raise SystemExit(2)

    if receipt is None:
        receipt = reconcile_until_bound(asset=frame_asset, key=key,
                                        report=report)
        if receipt is None:
            auth.promote_pending_to_ambiguity(
                key, "bounded reconciliation exhausted without unique binding")
            fail(report, "CANARY_FAIL_TRUE_AMBIGUITY",
                 "bounded reconciliation exhausted without unique binding", 3)
        if auth.authority == "SUSPENDED_QUALIFIED_UPLOAD_PENDING":
            auth.upload_bound(key, f"{canary} unique catalog binding")

    report["phase"] = "attestation"
    with open_session() as session:
        from film_pipeline.providers.flow_reference_binding import (
            adopt_existing_reference, attest_existing_reference)
        attestation = attest_existing_reference(
            SQLiteStore(canary_upload_store(canary)), frame_asset, session,
            account_id=ACCOUNT_ID, media_id=receipt["media_id"],
            evidence_dir=canary_dir / "evidence")
        shared = SQLiteStore(ROOT / "projects/flow_production_harden_002/"
                             "requal_current_build/runtime.sqlite")
        shared.initialize()
        adopted_asset, adopted_attestation = adopt_existing_reference(
            shared, session, account_id=ACCOUNT_ID,
            media_id=receipt["media_id"],
            reference_dir=canary_dir / "reference")
    report["attestation_id"] = attestation["attestation_id"]
    report["adopted_asset_id"] = adopted_asset.asset_id
    report["adopted_attestation_id"] = adopted_attestation["attestation_id"]
    report["authority_after"] = auth.authority
    report["result"] = "CANARY_PASS"
    report["finished_at"] = utc_now()
    write_report(report)
    return report


def record_upload_custody(canary: str, slot: str, key: str) -> None:
    """The one POST authority is released at the arm boundary regardless of
    classification: budget custody recorded on EVERY exit path."""
    data = ledger()
    if not [e for e in data["uploads_used"] if e.get("canary") == canary]:
        data["uploads_used"].append({
            "canary": canary, "slot": slot, "at": utc_now(),
            "reservation_id": key})
        data["events"].append({"kind": f"{canary.upper()}_UPLOAD_RELEASED",
                               "at": utc_now()})
        save_ledger(data)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command in ("canaryA", "canaryB"):
        run_canary(command)
    elif command == "status":
        auth = authority()
        print(json.dumps({"authority": auth.authority,
                          "upload_pending": auth._state.get("upload_pending"),
                          "uploads_bound": auth._state.get("uploads_bound", []),
                          "ledger": ledger()}, default=str, indent=1))
    else:
        raise SystemExit("usage: run_requal_009.py canaryA|canaryB|status")
