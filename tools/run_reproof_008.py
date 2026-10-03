"""FLOW-UPLOAD-RECONCILIATION-CONTRACT-008 Phase 9 (U9).

Package-007 clean re-proof of the four post-gate-invalidated canonical slots
(U7 salvage set): SEQ7_F2R, SEQ7_G2R, SEQ7_E2R2, SEQ7_G3BR.

LIVE AUTHORITY: MAX_REPROOF_GENERATES = 8 (4 used). NO uploads (0 authorized;
every binding references an already-bound provider media). Zero retries.

Each slot: exact frozen creative spec (identity fields only renamed) -> NEW
ProviderJob -> NEW marker -> fresh baseline -> ONE native-UI Generate ->
acquisition -> decode -> durable result. Any OwnerAmbiguityGate with an
observed generate request latches the REPROOF scope (the 007 runner-gap is
NOT reproduced: upload-side gates cannot occur here because no upload path
runs, and every gate class latches through the same handler).
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

REPROOF_DIR = ROOT / "projects/flow_upload_reconciliation_008/reproof"
REPROOF_SCOPE = "FLOW-UPLOAD-RECONCILIATION-CONTRACT-008-REPROOF"
MAX_REPROOF_GENERATES = 8

import run_production_scale_007 as base

base.RUN_DIR = REPROOF_DIR
base.SCOPE_ID = REPROOF_SCOPE

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from mutation_authority import MutationAuthority

SEQ = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"

# U8 re-attested lineage (fresh readback proved exact identity today).
F2R_BINDING = {
    "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
    "asset_id": "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3",
    "attestation_id": "refbind_f4277ac1a7a5651c8370212417c06593f08a003aee1676517622292f37cb4fdf",
    "mechanism": "last_frame", "from_shot": "SEQ7_F1",
    "source_frame_sha256": "a3672ac2cf44ed22829c08f9c49519ebc0039b1d72c40d8817597833779fbb48"}
G2R_BINDING = {
    "media_id": "75dbd0bc-8416-40a0-9c2a-19700fdcf665",
    "asset_id": "asset_1ff28bfe3f98d64a8ac8f56e3e41c635731d864f568326c6d5c516580323b843",
    "attestation_id": "refbind_8f95534289779d546cf256c842d4f8bfdbc723da142b1324f5d2b6fdbe57aa5a",
    "mechanism": "last_frame", "from_shot": "SEQ7_G1",
    "source_frame_sha256": "07ceff242abf90ca0c373fc10934c60f2a690509fdd7db3b9732798859a195a4"}

SLOTS = [
    {"shot_id": "SEQ7_F2R", "fixture": "fixtures/reproof008/SEQ7_F2R.json",
     "scene_id": "SCENE_F_STORM_GATE", "editorial_target_duration": 5.6,
     "binding": F2R_BINDING, "successor_of": "SEQ7_F2"},
    {"shot_id": "SEQ7_G2R", "fixture": "fixtures/reproof008/SEQ7_G2R.json",
     "scene_id": "SCENE_G_HIGH_PLATEAU", "editorial_target_duration": 4.0,
     "binding": G2R_BINDING, "successor_of": "SEQ7_G2"},
    {"shot_id": "SEQ7_E2R2", "fixture": "fixtures/reproof008/SEQ7_E2R2.json",
     "scene_id": "SCENE_E_RIDGE_APPROACH", "editorial_target_duration": 4.0,
     "binding": None, "successor_of": "SEQ7_E2R"},
    {"shot_id": "SEQ7_G3BR", "fixture": "fixtures/reproof008/SEQ7_G3BR.json",
     "scene_id": "SCENE_G_HIGH_PLATEAU", "editorial_target_duration": 3.2,
     "binding": None, "successor_of": "SEQ7_G3B"},
]


def make_binding_for(shot):
    def binding_for(_shot, scene_dir):
        if shot["binding"] is None:
            # Base reference, identical to every same-reference Package-007 slot.
            return {"media_id": base.BASE_REFERENCE["media_id"],
                    "asset_id": base.BASE_REFERENCE["asset_id"],
                    "attestation_id": base.BASE_REFERENCE["attestation_id"],
                    "mechanism": "same_reference"}
        return dict(shot["binding"])
    return binding_for


def main() -> None:
    from film_pipeline.live_runtime import utc_now
    REPROOF_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path = REPROOF_DIR / "generate_ledger.json"
    if not ledger_path.exists():
        ledger_path.write_text(json.dumps({
            "initialized_at": utc_now(), "max_primary": MAX_REPROOF_GENERATES,
            "max_repair": 0, "max_uploads": 0, "primary_consumed": [],
            "repair_consumed": [], "uploads": []}, indent=1), encoding="utf-8")

    auth = MutationAuthority(REPROOF_DIR, REPROOF_SCOPE)
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("REPROOF scope latched")
    auth.check_mutation_allowed("reproof_generate")

    plan_path = REPROOF_DIR / "reproof_plan_008.json"
    if not plan_path.exists():
        plan_path.write_text(json.dumps({
            "version": "reproof-plan-008-v1",
            "salvage_basis": "salvage_plan_008.json (U7)",
            "slots": [{"shot_id": s["shot_id"],
                       "successor_of": s["successor_of"],
                       "editorial_target_duration":
                           s["editorial_target_duration"],
                       "reference": (s["binding"] or {}).get("media_id",
                           base.BASE_REFERENCE["media_id"])} for s in SLOTS],
            "frozen_at": utc_now()}, indent=1), encoding="utf-8")

    for shot in SLOTS:
        base.reference_binding_for = make_binding_for(shot)
        if shot["binding"] is not None:
            scene_dir = REPROOF_DIR / f"scene_{shot['scene_id']}"
            att_src = SEQ / f"scene_{shot['scene_id']}" / \
                "continuity_reference" / "attestation"
            att_dst = scene_dir / "continuity_reference" / "attestation"
            att_dst.mkdir(parents=True, exist_ok=True)
            for item in att_src.iterdir():
                target = att_dst / item.name
                if not target.exists():
                    if item.suffix == ".json":
                        target.write_text(item.read_text(encoding="utf-8"),
                                          encoding="utf-8")
                    else:
                        target.write_bytes(item.read_bytes())
        print(json.dumps({"step": "slot_start", "shot_id": shot["shot_id"],
                          "successor_of": shot["successor_of"]}), flush=True)
        report = base.run_live_shot(
            {"shot_id": shot["shot_id"], "fixture": shot["fixture"],
             "continuity": {"kind": "reproof_reference",
                            "media_id": (shot["binding"] or {}).get(
                                "media_id", base.BASE_REFERENCE["media_id"])},
             "budget_kind": "primary",
             "editorial_target_duration": shot["editorial_target_duration"]},
            REPROOF_DIR / f"scene_{shot['scene_id']}", {})
        if report.get("gate") != "SHOT_PROVEN":
            print(json.dumps({"step": "slot_stopped", "shot_id": shot["shot_id"],
                              "gate": report.get("gate"),
                              "diagnostic": str(report.get("diagnostic"))[:300]}),
                  flush=True)
            raise SystemExit(4)


if __name__ == "__main__":
    main()
