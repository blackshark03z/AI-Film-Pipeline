"""FLOW-UPLOAD-CONTRACT-REQUAL-009 Phase 4 (V5).

ONE conditioned Generate using Canary B's newly bound reference, under the
SAME single authority domain (no sub-scope). Proves:
QUALIFIED_PENDING -> UPLOAD_BOUND -> OPEN -> later planned Generate valid.

The generate chain is the proven Package-007 per-shot chain re-entered with
RUN_DIR/SCOPE_ID rebound to the 009 state (one authority file).
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

RUN_DIR = ROOT / "projects/flow_upload_contract_requal_009"
SCOPE_ID = "FLOW-UPLOAD-CONTRACT-REQUAL-009"
MAX_CONDITIONED_GENERATES = 1
MAX_TOTAL_GENERATES = 5  # 1 continuation + 4 re-proof

import run_production_scale_007 as base

base.RUN_DIR = RUN_DIR
base.SCOPE_ID = SCOPE_ID
base.PROFILE = "D:/AI FILM MAKER/Flow-Claude-Clean-Profile"

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from mutation_authority import MutationAuthority

CANARY_B_MEDIA = "65e73642-1140-4cd6-be68-fd8b772bdf4a"
_CANARY_B = json.loads((ROOT / "projects/flow_upload_contract_requal_009/"
                        "canaryB_report.json").read_text(encoding="utf-8"))
ADOPTED_ASSET_ID = _CANARY_B["adopted_asset_id"]
ADOPTED_ATTESTATION = _CANARY_B["adopted_attestation_id"]
ADOPTED_ATTESTATION_FILE = ("projects/flow_upload_contract_requal_009/canaryB/"
                            "reference/attestation/"
                            + ADOPTED_ATTESTATION + ".json")


def base_reference_binding_for(shot, scene_dir):
    return {"media_id": CANARY_B_MEDIA, "asset_id": ADOPTED_ASSET_ID,
            "attestation_id": ADOPTED_ATTESTATION,
            "mechanism": "last_frame"}


def main() -> None:
    from film_pipeline.live_runtime import utc_now
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    gen_ledger = RUN_DIR / "generate_ledger.json"
    if not gen_ledger.exists():
        gen_ledger.write_text(json.dumps({
            "initialized_at": utc_now(),
            "max_primary": MAX_TOTAL_GENERATES, "max_repair": 0,
            "max_uploads": 0, "primary_consumed": [], "repair_consumed": [],
            "uploads": []}, indent=1), encoding="utf-8")

    auth = MutationAuthority(RUN_DIR, SCOPE_ID)
    data = json.loads(gen_ledger.read_text(encoding="utf-8"))
    if len(data["primary_consumed"]) >= MAX_CONDITIONED_GENERATES:
        raise OwnerAmbiguityGate("conditioned generate budget exhausted (1 max)")
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("package authority latched")
    auth.check_mutation_allowed("conditioned_generate")

    canary_b_report = json.loads(
        (RUN_DIR / "canaryB_report.json").read_text(encoding="utf-8"))
    if canary_b_report.get("result") != "CANARY_PASS":
        raise OwnerAmbiguityGate("canary B did not pass; no continuation")
    print(json.dumps({"step": "bind_confirmed",
                      "media_id": CANARY_B_MEDIA}), flush=True)

    scene_dir = RUN_DIR / "scene_V5_CONTINUATION_PROOF"
    att_dir = scene_dir / "continuity_reference" / "attestation"
    att_dir.mkdir(parents=True, exist_ok=True)
    att_src_dir = ROOT / "projects/flow_upload_contract_requal_009/canaryB/"         "reference/attestation"
    import shutil
    for item in att_src_dir.iterdir():
        target = att_dir / item.name
        if not target.exists():
            if item.suffix == ".json":
                target.write_text(item.read_text(encoding="utf-8"),
                                  encoding="utf-8")
            else:
                target.write_bytes(item.read_bytes())

    base.reference_binding_for = base_reference_binding_for
    shot = {"shot_id": "V5_CONT",
            "fixture": "fixtures/requal009/V5_CONT.json",
            "continuity": {"kind": "canary_reference",
                           "media_id": CANARY_B_MEDIA},
            "budget_kind": "primary",
            "editorial_target_duration": 8.0}
    report = base.run_live_shot(shot, scene_dir, {})
    print(json.dumps({"step": "continuation_result", "gate": report.get("gate"),
                      "output": report.get("output_identity")}), flush=True)


if __name__ == "__main__":
    main()
