"""AI-FILM-QUALITY-V2-008 — Phases 0-2: custody, deterministic frame
re-extraction + classification, and the ONE Owner-authorized reference
qualification upload (full durable chain, exactly as Packages 003+
proved it).

Upload budget: exactly 1 (MutationAuthority scope + ledger). Any
ambiguity latches the scope and dies ALL later mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

PKG = ROOT / "projects/quality_v2_008_world_anchored_live"
V7 = ROOT / "projects/quality_v2_007_world_anchor"
V5 = ROOT / "projects/quality_v2_005_f2_decomposition"
V6 = ROOT / "projects/quality_v2_006_f2_decomposed_live"

V2_007_HEAD = "ceecf2781c7f2c46962088f9627a0b59bc7d580d"
FRAME_S = 6.6
EXPECTED_FRAME_SHA = None  # verified against V2-007's recorded still
UPLOAD_SCOPE = "QUALITY-V2-008-REF-UPLOAD"


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rebind() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    if head != V2_007_HEAD:
        raise SystemExit(f"BLOCKED_INVARIANT: start HEAD drift ({head})")
    plan5 = json.loads((V5 / "f2_decomposition_plan_v2_005.json")
                       .read_text(encoding="utf-8"))
    pre7 = json.loads((PKG.parent / "quality_v2_007_world_anchor" /
                       "world_anchor_preflight_v2_007.json").read_text(
                           encoding="utf-8"))
    v6 = json.loads((V6 / "custody_v2_006.json").read_text(
        encoding="utf-8"))
    custody = {
        "version": "v2-008-custody-v1",
        "checkpoint": "V2008_P0_CUSTODY",
        "start_sha": head,
        "v2_007_final_head": V2_007_HEAD,
        "owner_authorization": {
            "AUTHORIZE_V2_008": "ONE_REFERENCE_UPLOAD + F2A_PACING_DELTA",
            "authorization_source": "Owner explicit approval in Tech Lead "
                                    "chat after V2-007",
            "not_authorized": ["second reference upload", "alternate "
                               "reference", "alternate take", "retry",
                               "provider switch", "extra Generate",
                               "canonical promotion"]},
        "bindings": {
            "v2_007_evidence": "docs/operating/"
                               "AI_FILM_QUALITY_V2_007_WORLD_ANCHOR_"
                               "PREFLIGHT_EVIDENCE.md",
            "v2_008_handoff": "docs/quality-v2/"
                              "V2_008_F2_WORLD_ANCHORED_LIVE_HANDOFF.md",
            "v2_006_evidence": "docs/operating/"
                               "AI_FILM_QUALITY_V2_006_F2_DECOMPOSED_LIVE_"
                               "EXPERIMENT_EVIDENCE.md",
            "v2_005_decomposition": "projects/quality_v2_005_f2_"
                                    "decomposition/"
                                    "f2_decomposition_plan_v2_005.json",
            "v2_005r_findings": "docs/operating/"
                                "AI_FILM_QUALITY_V2_005R_REFERENCE_"
                                "COMPATIBILITY_PREFLIGHT_EVIDENCE.md",
            "frozen_f2a": {
                "blocking_spec_id":
                    plan5["f2a_commit_to_cross"]["blocking"][
                        "blocking_spec_id"],
                "camera_plan_id":
                    plan5["f2a_commit_to_cross"]["camera"][
                        "camera_plan_id"]},
            "frozen_f2b": {
                "blocking_spec_id":
                    plan5["f2b_emerge_far_side"]["blocking"][
                        "blocking_spec_id"],
                "camera_plan_id":
                    plan5["f2b_emerge_far_side"]["camera"][
                        "camera_plan_id"]},
            "canonical": {
                "f1_f3_direction": "faces frame-left",
                "f2_selected_take": v6["bindings"][
                    "canonical_f2_selected_take"],
                "edit_manifest_id": v6["bindings"][
                    "canonical_edit_manifest_id"],
                "master_sha256": v6["bindings"]["canonical_master_sha256"]},
            "qualified_route": v6["bindings"]["qualified_route"],
            "quality_debt": "QD-001 (ACTIVE)"},
        "v2_007_preflight": {
            "world_reference_source_sha256":
                pre7["world_reference_candidate"]["frame"]["sha256"],
            "world_reference_frame_s":
                pre7["world_reference_candidate"]["frame"][
                    "extracted_from_s"]}}
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "custody_v2_008.json").write_text(
        json.dumps(custody, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2008_P0_CUSTODY",
                      "head": head[:12]}))
    return custody


def reextract_and_classify() -> dict:
    """Re-extract @6.6s from the EXACT acquired V2-004-B asset and
    compare to the V2-007 recorded still."""
    pre7 = json.loads((PKG.parent / "quality_v2_007_world_anchor" /
                       "world_anchor_preflight_v2_007.json").read_text(
                           encoding="utf-8"))
    expected_sha = pre7["world_reference_candidate"]["frame"]["sha256"]
    result = json.loads(
        (ROOT / "projects/quality_v2_004_f2_blocking/scene_SCENE_F_"
         "STORM_GATE/shot_SEQ7_F2C_V2_004_B/result.json").read_text(
            encoding="utf-8"))
    video = Path(result["asset"]["uri_or_path"])
    if file_sha(video) != result["asset"]["sha256"]:
        raise SystemExit("BLOCKED_INVARIANT: source video bytes changed")
    out = PKG / "world_reference_frame.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{FRAME_S}", "-i",
         str(video), "-frames:v", "1", "-update", "1", str(out)],
        check=True)
    frame_sha = file_sha(out)
    v7_still = (PKG.parent / "quality_v2_007_world_anchor" /
                "qc_evidence" / "wref_V2004B_t6.6.png")
    v7_sha = file_sha(v7_still)
    match = frame_sha == expected_sha
    v7_match = frame_sha == v7_sha
    if not match or not v7_match:
        raise SystemExit(
            f"BLOCKED_INVARIANT: frame sha mismatch: extracted "
            f"{frame_sha[:16]} vs V2-007 recorded {expected_sha[:16]} / "
            f"v7 still {v7_sha[:16]}")
    from PIL import Image
    img = Image.open(out)
    classification = {
        "reference_type": "FULL_FRAME_WORLD_AND_IDENTITY",
        "geography": "FAR_SIDE_COMPATIBLE (gate visibly BEHIND the "
                     "subject; he has emerged through the doorway)",
        "world": "storm-gate (granite doorway, grassland, dark storm "
                 "clouds; no fortress, no metal gate, no warm cloud "
                 "sea, no lightning)",
        "identity": "acceptable (same character: white robes, topknot + "
                    "ribbon, face consistent)",
        "dimensions": list(img.size),
        "visual_read_basis": "exact re-extracted hashed bytes; worker "
                             "visual read recorded",
        "source_take_remains_REJECTED": True}
    doc = {
        "version": "v2-008-frame-reextraction-v1",
        "checkpoint": "V2008_P1_FRAME_REEXTRACTED",
        "source_video_asset_sha256": result["asset"]["sha256"],
        "source_provider_job_id": result["provider_job_id"],
        "source_output_identity": result["output_identity"],
        "frame_timestamp_s": FRAME_S,
        "frame_sha256": frame_sha,
        "v2_007_recorded_sha256": expected_sha,
        "match": match, "v7_still_match": v7_match,
        "classification": classification,
        "rejected_take_status": "REJECTED (unchanged); only the exact "
                                "frame is being qualified"}
    (PKG / "frame_reextraction_v2_008.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2008_P1_FRAME_REEXTRACTED",
                      "frame_sha": frame_sha[:16],
                      "match": match}))
    return doc


def qualify_reference() -> dict:
    """The ONE Owner-authorized upload through the exact proven chain:
    local Asset -> single-upload store -> FlowReferenceTransport.
    ensure_verified (ONE POST) -> attest_existing_reference ->
    adopt_existing_reference."""
    from mutation_authority import MutationAuthority
    from film_pipeline.providers.flow_reference_upload import (
        OwnerAmbiguityGate, ReferenceUploadStore)
    from film_pipeline.providers.flow_reference_transport import (
        FlowReferenceTransport)
    from film_pipeline.providers.flow_reference_binding import (
        adopt_existing_reference, attest_existing_reference)
    from film_pipeline.live_runtime import Asset
    from film_pipeline.store import SQLiteStore
    from run_production_scale_007 import (PROJECT_ID, ACCOUNT_ID,
                                          open_read_session)
    from film_pipeline.providers.flow_reference_rpc import \
        FlowReferenceRpcSession

    ledger_path = PKG / "upload_ledger.json"
    if ledger_path.exists():
        raise SystemExit("BLOCKED_INVARIANT: upload ledger already "
                         "exists; exactly ONE qualification per package")
    auth = MutationAuthority(PKG, UPLOAD_SCOPE)
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("upload authority latched")
    auth.check_mutation_allowed("reference_upload")

    frame_doc = json.loads((PKG / "frame_reextraction_v2_008.json")
                           .read_text(encoding="utf-8"))
    frame_path = PKG / "world_reference_frame.png"
    sha = frame_doc["frame_sha256"]
    from PIL import Image
    w, h = Image.open(frame_path).size
    frame_asset = Asset(
        asset_id="asset_" + sha256({"origin": "reference",
            "kind": "far_side_world_frame", "source_take": "V2-004-B",
            "frame_s": FRAME_S, "sha256": sha}),
        origin="reference", asset_type="image",
        uri_or_path=str(frame_path), sha256=sha,
        mime_type="image/png", width=w, height=h,
        file_size=frame_path.stat().st_size,
        rights_metadata={"source_kind": "frame_of_acquired_asset",
                         "source_take": "V2-004-B (REJECTED as a take; "
                                        "frame only)",
                         "source_job_id": frame_doc[
                             "source_provider_job_id"],
                         "source_output_identity": frame_doc[
                             "source_output_identity"],
                         "source_asset_sha256": frame_doc[
                             "source_video_asset_sha256"],
                         "frame_timestamp_s": FRAME_S,
                         "world": frame_doc["classification"]["world"],
                         "geography": frame_doc["classification"][
                             "geography"],
                         "purpose": "F2B_WORLD_ANCHOR"})
    store_path = PKG / "reference_upload_1.sqlite"
    store = SQLiteStore(store_path)
    store.initialize()
    store.save_reference_asset(frame_asset)
    binding = None
    with open_read_session() as session:
        transport = FlowReferenceTransport(
            ReferenceUploadStore(store_path), session,
            account_id=ACCOUNT_ID,
            evidence_dir=PKG / "reference_evidence",
            interval_s=0, probes=2)
        try:
            receipt = transport.ensure_verified(frame_asset)
        except OwnerAmbiguityGate as exc:
            # QUALIFIED_PENDING is a designed state: exactly ONE POST is
            # armed and the response is a JSON-list skeleton. The store
            # is durable (state ARMED, attempts=1); re-entry dispatches
            # to reconcile_only — a catalog readback that NEVER re-
            # POSTs. A second QualifiedUploadPending here would mean
            # the reconcile path itself was refused — ambiguity.
            if "QUALIFIED_PENDING" not in str(exc):
                raise
            reconcile_note = {"kind": "qualified_pending_reconcile",
                              "diagnostic": str(exc)[:200]}
            (PKG / "reference_evidence").mkdir(parents=True,
                                               exist_ok=True)
            (PKG / "reference_evidence" /
             "qualified_pending_reconcile.json").write_text(
                json.dumps(reconcile_note, indent=1), encoding="utf-8")
            print(json.dumps({"step": "QUALIFIED_PENDING_reconcile",
                              "note": "re-entering ensure_verified: "
                                      "catalog readback, no re-POST"}),
                  flush=True)
            receipt = transport.ensure_verified(frame_asset)
        uploaded_media_id = receipt["media_id"]
        attestation = attest_existing_reference(
            store, frame_asset, session, account_id=ACCOUNT_ID,
            media_id=uploaded_media_id,
            evidence_dir=PKG / "reference_evidence")
        adopted_asset, adopted_attestation = adopt_existing_reference(
            SQLiteStore(ROOT / "projects/flow_production_harden_002/"
                        "requal_current_build/runtime.sqlite"),
            session, account_id=ACCOUNT_ID, media_id=uploaded_media_id,
            reference_dir=PKG / "continuity_reference")
    binding = {
        "media_id": uploaded_media_id,
        "asset_id": adopted_asset.asset_id,
        "attestation_id": adopted_attestation["attestation_id"],
        "source_attestation_id": attestation["attestation_id"],
        "upload_receipt_id": receipt["id"],
        "provider_media_sha256": receipt["provider_media_sha256"],
        "frame_sha256": sha,
        "mechanism": "far_side_world_frame",
        "reference_type": "FULL_FRAME_WORLD_AND_IDENTITY",
        "usage": "far-side F2B only"}
    ledger = {"version": "v2-008-upload-ledger-v1",
              "max_uploads": 1, "uploads": [
                  {"media_id": uploaded_media_id,
                   "asset_id": adopted_asset.asset_id,
                   "frame_sha256": sha,
                   "at": adopted_attestation.get("at", "")}],
              "binding": binding}
    ledger_path.write_text(json.dumps(ledger, indent=1,
                                      ensure_ascii=False),
                           encoding="utf-8")
    auth.consume("reference_upload")
    doc = {"version": "v2-008-reference-qualification-v1",
           "checkpoint": "V2008_P2_REFERENCE_QUALIFIED",
           "binding": binding,
           "upload_count": 1,
           "adoptions_dir": str((PKG / "continuity_reference")
                                .relative_to(ROOT))}
    (PKG / "reference_qualification_v2_008.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2008_P2_REFERENCE_QUALIFIED",
                      "media_id": uploaded_media_id,
                      "attestation": adopted_attestation[
                          "attestation_id"][:24]}))
    return doc


def sha256(value) -> str:
    from film_pipeline.core import sha256 as core_sha
    return core_sha(value)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("all", "custody"):
        rebind()
    if cmd in ("all", "frame"):
        reextract_and_classify()
    if cmd in ("all", "upload"):
        qualify_reference()
