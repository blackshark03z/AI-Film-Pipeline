"""U8: read-only re-attestation of Package-007 historical continuity references.

F1 asset -> deterministic last frame -> historical upload receipt (VERIFIED)
-> fresh as29s readback -> fresh attestation + adoption for the 008 re-proof
chain. No upload, no provider mutation.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.live_runtime import Asset
from film_pipeline.store import SQLiteStore
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore
from film_pipeline.providers.flow_reference_binding import (
    adopt_existing_reference, attest_existing_reference)

PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"
SHARED_STORE = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
SEQ = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"
OUT = ROOT / "projects/flow_upload_reconciliation_008/reproof"

TARGETS = {
    "F1": {"scene": "scene_SCENE_F_STORM_GATE", "for_shot": "SEQ7_F2"},
    "G1": {"scene": "scene_SCENE_G_HIGH_PLATEAU", "for_shot": "SEQ7_G2"},
}


def reattest(tag: str) -> dict:
    cfg = TARGETS[tag]
    scene_dir = SEQ / cfg["scene"]
    import sqlite3
    connection = sqlite3.connect(scene_dir / "continuity_upload_1.sqlite")
    row = connection.execute(
        "SELECT payload FROM assets WHERE id LIKE 'asset_%'").fetchone()
    connection.close()
    data = json.loads(row[0])
    asset = Asset(**{k: data[k] for k in (
        "asset_id", "origin", "asset_type", "uri_or_path", "sha256",
        "mime_type", "width", "height", "file_size", "rights_metadata")})
    import hashlib
    actual = hashlib.sha256(Path(asset.uri_or_path).read_bytes()).hexdigest()
    if actual != asset.sha256:
        raise SystemExit(f"{tag} frame bytes changed since Package-007")
    upload_store = SQLiteStore(scene_dir / "continuity_upload_1.sqlite")
    upload_store.initialize()
    receipt = ReferenceUploadStore(scene_dir / "continuity_upload_1.sqlite") \
        .read_verified("flow_veo", PROJECT_ID, ACCOUNT_ID, asset)
    print(f"{tag}: historical receipt VERIFIED media={receipt['media_id']}")
    out_dir = OUT / f"reattest_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    with FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                 project_id=PROJECT_ID, native_ui=True) as session:
        attestation = attest_existing_reference(
            upload_store, asset, session, account_id=ACCOUNT_ID,
            media_id=receipt["media_id"],
            evidence_dir=out_dir / "evidence")
        # The canonical adopted asset is deterministic and already registered
        # by Package-007; re-adoption would collide by design. Reuse it and
        # record the fresh readback attestation only.
        ledger = json.loads((scene_dir / "continuity_ledger.json")
                            .read_text(encoding="utf-8"))
        binding = [b for b in ledger["bindings"]
                   if b["for_shot"] == cfg["for_shot"]][0]
    result = {"tag": tag, "historical_media_id": receipt["media_id"],
              "provider_media_sha256": receipt["provider_media_sha256"],
              "frame_sha256": asset.sha256,
              "fresh_attestation_id": attestation["attestation_id"],
              "adopted_asset_id": binding["adopted_asset_id"],
              "adopted_attestation_id": binding["adopted_attestation_id"],
              "adoption_note": "canonical adopted asset reused from Package-007 (deterministic identity); fresh readback attestation written read-only"}
    (out_dir / "reattestation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return result


if __name__ == "__main__":
    targets = sys.argv[1:] or ["F1", "G1"]
    for tag in targets:
        reattest(tag)
