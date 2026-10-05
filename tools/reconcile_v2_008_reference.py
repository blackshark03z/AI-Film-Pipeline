"""V2-008: resume the ONE qualified upload's reconciliation with the
durable pre-dispatch catalog evidence (V2-006 F2B frozen intent,
captured BEFORE this package existed). NO re-POST: reconcile_only is a
readback-only path."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

PKG = ROOT / "projects/quality_v2_008_world_anchored_live"
V6 = ROOT / "projects/quality_v2_006_f2_decomposed_live"


def main() -> int:
    from mutation_authority import MutationAuthority
    from film_pipeline.providers.flow_reference_upload import (
        OwnerAmbiguityGate, ReferenceUploadStore)
    from film_pipeline.providers.flow_reference_transport import (
        FlowReferenceTransport)
    from film_pipeline.providers.flow_reference_binding import (
        adopt_existing_reference, attest_existing_reference)
    from film_pipeline.live_runtime import Asset
    from film_pipeline.store import SQLiteStore
    from run_production_scale_007 import ACCOUNT_ID, open_read_session

    auth = MutationAuthority(PKG, "QUALITY-V2-008-REF-UPLOAD")
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("upload authority latched")

    store_path = PKG / "reference_upload_1.sqlite"
    store = SQLiteStore(store_path)
    row = store_path and json.loads((PKG / "frame_reextraction_v2_008.json")
                                    .read_text(encoding="utf-8"))
    asset = Asset.model_validate(store.read_reference_asset(
        row["frame_sha256"]) if hasattr(store, "read_reference_asset")
        else None) if False else None
    # load the exact registered asset from the upload store
    import sqlite3
    con = sqlite3.connect(store_path)
    payload = con.execute("SELECT payload FROM assets").fetchone()[0]
    con.close()
    asset = Asset.model_validate(json.loads(payload))

    # durable pre-dispatch evidence: the union of BOTH V2-006 frozen
    # catalog baselines (captured before this package existed). Any row
    # in this set provably existed BEFORE the upload.
    pre = set()
    for p in (V6).glob("scene_*/shot_*/frozen_intent.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        pre.update(d.get("pre_dispatch_snapshot", {}).get("catalog_ids",
                                                         []))
    print(json.dumps({"step": "preexisting_evidence",
                      "count": len(pre)}), flush=True)

    with open_read_session() as session:
        transport = FlowReferenceTransport(
            ReferenceUploadStore(store_path), session,
            account_id=ACCOUNT_ID,
            evidence_dir=PKG / "reference_evidence",
            interval_s=0, probes=3)
        receipt = transport.reconcile_only(
            asset, preexisting_ids=sorted(pre))
        uploaded_media_id = receipt["media_id"]
        attestation = attest_existing_reference(
            store, asset, session, account_id=ACCOUNT_ID,
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
        "upload_receipt_id": receipt["id"],
        "provider_media_sha256": receipt["provider_media_sha256"],
        "frame_sha256": row["frame_sha256"],
        "mechanism": "far_side_world_frame",
        "reference_type": "FULL_FRAME_WORLD_AND_IDENTITY",
        "usage": "far-side F2B only",
        "reconcile_preexisting_evidence": "V2-006 frozen pre-dispatch "
                                          "catalog baselines (81+82 ids)"}
    ledger = {"version": "v2-008-upload-ledger-v1",
              "max_uploads": 1,
              "uploads": [{"media_id": uploaded_media_id,
                           "asset_id": adopted_asset.asset_id,
                           "frame_sha256": row["frame_sha256"]}],
              "binding": binding}
    (PKG / "upload_ledger.json").write_text(
        json.dumps(ledger, indent=1, ensure_ascii=False),
        encoding="utf-8")
    auth.consume("reference_upload")
    doc = {"version": "v2-008-reference-qualification-v1",
           "checkpoint": "V2008_P2_REFERENCE_QUALIFIED",
           "binding": binding,
           "upload_count": 1}
    (PKG / "reference_qualification_v2_008.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2008_P2_REFERENCE_QUALIFIED",
                      "media_id": uploaded_media_id,
                      "attestation": adopted_attestation[
                          "attestation_id"][:24]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
