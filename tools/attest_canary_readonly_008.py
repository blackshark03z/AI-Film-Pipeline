"""Read-only attestation + adoption of a resolved canary upload (Package-008).

No provider mutation: one as29s readback of the exact bound media, then
local immutable attestation + canonical reference adoption.
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

RUN_DIR = ROOT / "projects/flow_upload_reconciliation_008"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"
SHARED_STORE = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"

canary = sys.argv[1] if len(sys.argv) > 1 else "canary2"
canary_dir = RUN_DIR / canary
data = json.loads((canary_dir / "frame_asset.json").read_text(encoding="utf-8"))
asset = Asset(**{k: data[k] for k in (
    "asset_id", "origin", "asset_type", "uri_or_path", "sha256",
    "mime_type", "width", "height", "file_size", "rights_metadata")})
from film_pipeline.providers.flow_reference_upload import _key
store = SQLiteStore(canary_dir / "upload_1.sqlite")
store.initialize()
key = _key("flow_veo", PROJECT_ID, ACCOUNT_ID, asset)
receipt = ReferenceUploadStore(canary_dir / "upload_1.sqlite").read_verified(
    "flow_veo", PROJECT_ID, ACCOUNT_ID, asset)
print("verified receipt:", receipt["media_id"])
with FlowReferenceRpcSession(profile_path=Path(PROFILE),
                             project_id=PROJECT_ID, native_ui=True) as session:
    attestation = attest_existing_reference(
        store, asset, session, account_id=ACCOUNT_ID,
        media_id=receipt["media_id"],
        evidence_dir=canary_dir / "evidence")
    shared = SQLiteStore(SHARED_STORE)
    shared.initialize()
    adopted_asset, adopted_attestation = adopt_existing_reference(
        shared, session, account_id=ACCOUNT_ID,
        media_id=receipt["media_id"],
        reference_dir=canary_dir / "reference")
print(json.dumps({"attestation_id": attestation["attestation_id"],
                  "adopted_asset_id": adopted_asset.asset_id,
                  "adopted_attestation_id": adopted_attestation["attestation_id"]}))
