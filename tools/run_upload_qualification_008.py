"""FLOW-UPLOAD-RECONCILIATION-CONTRACT-008 — live upload qualification canary.

Owner-authorized qualification experiment (Phases 4-5):
    MAX_QUAL_UPLOADS = 2 total for the whole package. Zero retries.

One canary = deterministic last frame of one PRE_GATE_CLEAN Package-007
asset (never uploaded with identical bytes) -> ONE maseQ POST through the
classified transport -> qualified pending -> SUSPENDED scope authority ->
bounded READ-ONLY catalog reconciliation -> unique binding (UPLOAD_BOUND)
restores authority, or any conflict/exhaustion promotes TRUE AMBIGUITY and
latches the scope permanently.

Canary 2 additionally asserts the observed pending skeleton fingerprint
equals Canary 1's frozen fingerprint (response-shape drift = fail closed).

Commands: canary1 | canary2 | status
"""
from __future__ import annotations

import hashlib
import json
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

from film_pipeline.live_runtime import Asset, utc_now
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcSession, OwnerAuthRequired)
from film_pipeline.providers.flow_reference_transport import FlowReferenceTransport
from film_pipeline.providers.flow_reference_upload import (
    OwnerAmbiguityGate, ReferenceUploadStore, _key)
from film_pipeline.providers.flow_upload_classifier import (
    pending_fingerprint_matches, QualifiedUploadPending)
from mutation_authority import MutationAuthority

RUN_DIR = ROOT / "projects/flow_upload_reconciliation_008"
SCOPE_ID = "FLOW-UPLOAD-RECONCILIATION-CONTRACT-008"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"
SEQ_DIR = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"
MAX_QUAL_UPLOADS = 2
RECONCILE_ROUNDS = 12
RECONCILE_SLEEP_S = 45
# Gates that mean conflict (never retry): immediate TRUE AMBIGUITY.
TERMINAL_RECONCILE_GATES = ("multiple strong", "content mismatch",
                            "contract drift", "disagrees with Owner evidence")

SOURCES = {
    "canary1": {"slot": "SEQ7_E1", "scene": "scene_SCENE_E_RIDGE_APPROACH"},
    "canary2": {"slot": "SEQ7_G4", "scene": "scene_SCENE_G_HIGH_PLATEAU"},
}


def write_durable(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)


def authority() -> MutationAuthority:
    return MutationAuthority(RUN_DIR, SCOPE_ID)


def ledger() -> dict:
    path = RUN_DIR / "qualification_ledger.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"uploads_used": [], "generates_used": [],
            "max_uploads": MAX_QUAL_UPLOADS, "events": []}


def save_ledger(data: dict) -> None:
    write_durable(RUN_DIR / "qualification_ledger.json", data)


def open_session():
    return FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                   project_id=PROJECT_ID, native_ui=True)


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


def load_source_asset(slot: str, canary: str) -> dict:
    """Frozen Package-007 proven asset record (path + sha), verified."""
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
                receipt = transport.reconcile_only(asset)
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
                authority().promote_pending_to_ambiguity(
                    key, f"terminal reconciliation conflict: {message}")
                fail(report, "CANARY_FAIL_TRUE_AMBIGUITY",
                     f"terminal reconciliation conflict: {message}", 3)
        if attempt < RECONCILE_ROUNDS:
            time.sleep(RECONCILE_SLEEP_S)
    return None


def canary_upload_store(canary: str) -> Path:
    return RUN_DIR / canary / "upload_1.sqlite"


def run_canary(canary: str) -> dict:
    slot = SOURCES[canary]["slot"]
    auth = authority()
    canary_dir = RUN_DIR / canary
    report = {"canary": canary, "slot": slot, "phase": "preflight",
              "reconcile_rounds": 0, "started_at": utc_now()}
    write_report(report)

    auth.check_mutation_allowed("qualification_upload")
    data = ledger()
    already = [e for e in data["uploads_used"] if e.get("canary") == canary]
    if already and not (canary_dir / "upload_1.sqlite").exists():
        raise OwnerAmbiguityGate("ledger consumed but no durable upload store")
    if len(data["uploads_used"]) >= MAX_QUAL_UPLOADS and not already:
        raise OwnerAmbiguityGate("qualification upload budget exhausted (2 max)")

    source = load_source_asset(slot, canary)
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
    report["phase"] = "upload"
    report["frame_sha256"] = frame["sha256"]
    report["source_asset_sha256"] = source["sha256"]
    report["reservation_id"] = key
    report["upload_store"] = str(canary_upload_store(canary))

    # Durable frozen intent BEFORE any release.
    write_durable(canary_dir / "frozen_intent.json", {
        "canary": canary, "slot": slot, "project_id": PROJECT_ID,
        "account_id": ACCOUNT_ID, "frame_sha256": frame["sha256"],
        "source_asset_sha256": source["sha256"], "reservation_id": key,
        "expected_response_class": "maseQ-200-list-nouuid",
        "frozen_at": utc_now()})

    try:
        progress = store.read_progress(key)
    except OwnerAmbiguityGate:
        raise
    receipt = None
    try:
        if progress and progress["effective_state"] not in (
                None, "LOCAL_RESERVED"):
            # Resume path: the one POST already happened; read-only only.
            report["resumed_from_durable_state"] = \
                progress["effective_state"]
            data = ledger()
            if not [e for e in data["uploads_used"]
                    if e.get("canary") == canary]:
                data["uploads_used"].append({
                    "canary": canary, "slot": slot, "at": utc_now(),
                    "reservation_id": key, "resumed": True})
                data["events"].append({
                    "kind": f"{canary.upper()}_UPLOAD_RELEASED",
                    "at": utc_now(), "resumed": True})
                save_ledger(data)
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
                    report["response_class"] = "QUALIFIED_COMPLETED"
                except QualifiedUploadPending as pending:
                    report["response_class"] = "QUALIFIED_PENDING"
                    report["skeleton_fingerprint"] = pending.fingerprint
                    if canary == "canary2":
                        frozen = json.loads(
                            (RUN_DIR / "canary1_report.json")
                            .read_text(encoding="utf-8")) \
                            .get("skeleton_fingerprint")
                        if not pending_fingerprint_matches(
                                frozen, pending.fingerprint):
                            auth.latch("UPLOAD_RESPONSE_SHAPE_DRIFT",
                                       "canary2 pending skeleton differs "
                                       "from canary1 frozen fingerprint")
                            fail(report, "CANARY_FAIL_RESPONSE_DRIFT",
                                 "pending fingerprint drift vs frozen "
                                 "canary1 class", 3)
                    auth.enter_upload_pending(key, pending.fingerprint,
                                              f"{canary} qualified pending")
                    data = ledger()
                    data["uploads_used"].append({
                        "canary": canary, "slot": slot, "at": utc_now(),
                        "reservation_id": key,
                        "skeleton_fingerprint": pending.fingerprint})
                    data["events"].append({
                        "kind": f"{canary.upper()}_UPLOAD_RELEASED",
                        "at": utc_now()})
                    save_ledger(data)
                except OwnerAmbiguityGate as exc:
                    auth.latch("UPLOAD_RESPONSE_AMBIGUOUS", str(exc))
                    fail(report, "CANARY_FAIL_TRUE_AMBIGUITY", str(exc), 3)

        if receipt is None:
            receipt = reconcile_until_bound(asset=frame_asset, key=key,
                                            report=report)
            if receipt is None:
                auth.promote_pending_to_ambiguity(
                    key, "bounded reconciliation exhausted without unique "
                         "binding")
                fail(report, "CANARY_FAIL_TRUE_AMBIGUITY",
                     "bounded reconciliation exhausted without unique "
                     "binding", 3)
            if auth.authority == "SUSPENDED_QUALIFIED_UPLOAD_PENDING":
                auth.upload_bound(key, f"{canary} unique catalog binding")

        report["phase"] = "attestation"
        with open_session() as session:
            from film_pipeline.providers.flow_reference_binding import (
                adopt_existing_reference, attest_existing_reference)
            attestation = attest_existing_reference(
                store, frame_asset, session, account_id=ACCOUNT_ID,
                media_id=receipt["media_id"],
                evidence_dir=canary_dir / "evidence")
            adopted_asset, adopted_attestation = adopt_existing_reference(
                runtime, session, account_id=ACCOUNT_ID,
                media_id=receipt["media_id"],
                reference_dir=canary_dir / "reference")
        report["attestation_id"] = attestation["attestation_id"]
        report["adopted_asset_id"] = adopted_asset.asset_id
    except OwnerAuthRequired:
        report["result"] = "BLOCKED_OWNER_AUTH"
        report["finished_at"] = utc_now()
        write_report(report)
        raise SystemExit(2)

    report["result"] = "CANARY_PASS"
    report["authority_after"] = auth.authority
    report["finished_at"] = utc_now()
    write_report(report)
    return report


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command in ("canary1", "canary2"):
        run_canary(command)
    elif command == "status":
        auth = authority()
        print(json.dumps({"authority": auth.authority,
                          "upload_pending": auth._state.get("upload_pending"),
                          "uploads_bound": auth._state.get("uploads_bound", []),
                          "ledger": ledger()}, default=str, indent=1))
    else:
        raise SystemExit("usage: run_upload_qualification_008.py canary1|canary2|status")
