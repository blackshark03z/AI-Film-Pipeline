"""READ-ONLY reconciliation of a latched canary upload (C4-sanctioned path).

Never uploads, never mutates the provider. Resolves external-effect
knowledge only; any latch stays latched (authority untouched).
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession, OwnerAuthRequired
from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore, _key
from film_pipeline.providers.flow_reference_transport import FlowReferenceTransport
from film_pipeline.live_runtime import Asset

RUN_DIR = ROOT / "projects/flow_upload_reconciliation_008"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
ACCOUNT_ID = "clean-pro-qualified"
PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"

canary = sys.argv[1] if len(sys.argv) > 1 else "canary1"
canary_dir = RUN_DIR / canary
frame_asset_data = json.loads((canary_dir / "frame_asset.json").read_text(encoding="utf-8"))
asset = Asset(**{k: frame_asset_data[k] for k in (
    "asset_id", "origin", "asset_type", "uri_or_path", "sha256",
    "mime_type", "width", "height", "file_size", "rights_metadata")})
store = ReferenceUploadStore(canary_dir / "upload_1.sqlite")
key = _key("flow_veo", PROJECT_ID, ACCOUNT_ID, asset)
progress = store.read_progress(key)
print("state before:", progress["effective_state"])
try:
    with FlowReferenceRpcSession(profile_path=Path(PROFILE),
                                 project_id=PROJECT_ID, native_ui=True) as session:
        transport = FlowReferenceTransport(
            store, session, account_id=ACCOUNT_ID,
            evidence_dir=canary_dir / "evidence", interval_s=5, probes=2)
        preexisting = json.loads((canary_dir / "preexisting_ids.json").read_text(
            encoding="utf-8")) if (canary_dir / "preexisting_ids.json").exists() else None
        receipt = transport.reconcile_only(
            asset, preexisting_ids=preexisting)
    print(json.dumps({"resolved": True, "media_id": receipt["media_id"],
                      "provider_media_sha256": receipt["provider_media_sha256"]}))
except OwnerAuthRequired:
    print(json.dumps({"resolved": False, "reason": "OWNER_AUTH_REQUIRED"}))
    raise SystemExit(2)
