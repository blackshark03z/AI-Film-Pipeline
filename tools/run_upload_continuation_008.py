"""FLOW-UPLOAD-RECONCILIATION-CONTRACT-008 Phase 6 (U6).

One Owner-authorized conditioned Generate (MAX_QUAL_CONDITIONED_GENERATES=1)
proving the qualified-upload continuation chain on live authority state:

  canary2 qualified pending (durable classified evidence)
  -> CONT scope enters SUSPENDED_QUALIFIED_UPLOAD_PENDING
  -> read-only bind confirmation (store VERIFIED + fresh receipt)
  -> QUALIFIED_UPLOAD_BOUND restores OPEN
  -> ONE native-UI Generate conditioned on the canary 2 adopted reference
  -> unique output + acquisition + decode.

The generate chain is the proven Package-007 per-shot chain, re-entered
against 008-CONT state dirs (RUN_DIR/SCOPE_ID rebound; binding resolved to
the canary 2 adopted reference).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
tools_path = str(Path(__file__).resolve().parent)
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

CONT_DIR = ROOT / "projects/flow_upload_reconciliation_008/continuation"
CONT_SCOPE = "FLOW-UPLOAD-RECONCILIATION-CONTRACT-008-CONT"
MAX_QUAL_GENERATES = 1

import run_production_scale_007 as base

base.RUN_DIR = CONT_DIR
base.SCOPE_ID = CONT_SCOPE
base.PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"

from film_pipeline.store import SQLiteStore
from film_pipeline.providers.flow_reference_rpc import OwnerAuthRequired
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from mutation_authority import MutationAuthority

CANARY2_MEDIA = "454e75b4-0bca-47ac-95a0-65fda7086d57"
CANARY2_ATTESTATION = ("projects/flow_upload_reconciliation_008/canary2/reference/attestation/"
                       "refbind_1791e3d60e7b87404cb6b1011bba7cd255a9671fe2571467388f6b33415b59cf.json")
ADOPTED_ASSET_ID = "asset_297ad56e568aa791c84075ccb269c0b2e919eafffe69393455a5e90df86623eb"
ADOPTED_ATTESTATION = "refbind_1791e3d60e7b87404cb6b1011bba7cd255a9671fe2571467388f6b33415b59cf"
CANARY2_RESERVATION = ("refup_fe4fe3c9ac97fc99211c00ad6b1ed1be6b4509190e391dcd0bcf533fedb06bf3")
FROZEN_PENDING_FINGERPRINT = ("ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1")

BINDING = {"media_id": CANARY2_MEDIA, "asset_id": ADOPTED_ASSET_ID,
           "attestation_id": ADOPTED_ATTESTATION, "mechanism": "last_frame",
           "from_shot": "SEQ7_G4", "source_frame_sha256":
               "d7cd1cac6801f327c7c90e9cc32d3775fde40a22a851172b730abf803ddb681b"}


def base_reference_binding_for(shot, scene_dir):
    return dict(BINDING)


def main() -> None:
    from film_pipeline.live_runtime import utc_now
    CONT_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path = CONT_DIR / "generate_ledger.json"
    if not ledger_path.exists():
        ledger_path.write_text(json.dumps({
            "initialized_at": utc_now(), "max_primary": MAX_QUAL_GENERATES,
            "max_repair": 0, "max_uploads": 0, "primary_consumed": [],
            "repair_consumed": [], "uploads": []}, indent=1), encoding="utf-8")

    auth = MutationAuthority(CONT_DIR, CONT_SCOPE)
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    if len(data["primary_consumed"]) >= MAX_QUAL_GENERATES:
        raise OwnerAmbiguityGate("conditioned generate budget exhausted (1 max)")
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("CONT scope latched")

    # The canary 2 upload store must be VERIFIED (post-hoc read-only bind).
    from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore
    receipt = ReferenceUploadStore(
        ROOT / "projects/flow_upload_reconciliation_008/canary2/upload_1.sqlite"
    ).read_verified("flow_veo", base.PROJECT_ID, base.ACCOUNT_ID,
                    _frame_asset())
    assert receipt["media_id"] == CANARY2_MEDIA
    print(json.dumps({"step": "bind_confirmed", "media_id": receipt["media_id"]}),
          flush=True)

    if auth.authority == "OPEN":
        # Exercise the real qualified-pending suspension against the durable
        # canary 2 pending evidence, then restore authority by UPLOAD_BOUND.
        auth.enter_upload_pending(
            CANARY2_RESERVATION, FROZEN_PENDING_FINGERPRINT,
            "U6: canary2 qualified pending re-entered for continuation proof")
        auth.upload_bound(
            CANARY2_RESERVATION,
            "U6: unique read-only binding confirmed; continuation authorized")
    if auth.authority != "OPEN":
        raise OwnerAmbiguityGate("continuation requires restored OPEN authority")
    auth.check_mutation_allowed("conditioned_generate")

    # Attestation file for the binding, inside the CONT scene dir layout.
    scene_dir = CONT_DIR / "scene_U6_CONTINUATION_PROOF"
    att_dir = scene_dir / "continuity_reference" / "attestation"
    att_dir.mkdir(parents=True, exist_ok=True)
    att_src = ROOT / CANARY2_ATTESTATION
    att_dst = att_dir / (ADOPTED_ATTESTATION + ".json")
    if not att_dst.exists():
        att_dst.write_text(att_src.read_text(encoding="utf-8"), encoding="utf-8")

    base.reference_binding_for = base_reference_binding_for
    shot = {"shot_id": "U6_CONT",
            "fixture": "fixtures/continuation008/U6_CONT.json",
            "continuity": {"kind": "canary_reference",
                           "media_id": CANARY2_MEDIA},
            "budget_kind": "primary",
            "editorial_target_duration": 8.0}
    report = base.run_live_shot(shot, scene_dir, {})
    print(json.dumps({"step": "continuation_result", "gate": report.get("gate"),
                      "output": report.get("output_identity")}), flush=True)


def _frame_asset():
    from film_pipeline.live_runtime import Asset
    data = json.loads((ROOT / "projects/flow_upload_reconciliation_008/canary2/"
                       "frame_asset.json").read_text(encoding="utf-8"))
    return Asset(**{k: data[k] for k in (
        "asset_id", "origin", "asset_type", "uri_or_path", "sha256",
        "mime_type", "width", "height", "file_size", "rights_metadata")})


if __name__ == "__main__":
    main()
