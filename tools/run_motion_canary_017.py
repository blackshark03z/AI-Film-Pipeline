"""FLOW-PERFORMANCE-MOTION-CANARY-017 (Phase 9): the bounded live
canary runner.

NEW authority scope: FLOW-PERFORMANCE-MOTION-CANARY-017 (fresh mutation
authority + fresh generate ledger; the Package-009 scope stays closed
and untouched). LIVE BUDGET: MAX 4 primary Generates total, 0 retries,
0 uploads (both references are already-bound provider media).

Each candidate: exact frozen fixture -> NEW ProviderJob -> ONE native-UI
Generate -> reconcile -> acquire -> decode -> durable result. Any
OwnerAmbiguityGate with an observed generate request latches the scope
(no workaround scopes, no second sessions). Restart-safe: a durable
result short-circuits; consumed authority is never re-released.
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

CANARY_DIR = ROOT / "projects/flow_performance_motion_canary_017"
AUTHORITY_DIR = CANARY_DIR
CANARY_SCOPE = "FLOW-PERFORMANCE-MOTION-CANARY-017"
MAX_CANARY_GENERATES = 4

import run_production_scale_007 as base

base.RUN_DIR = CANARY_DIR
base.SCOPE_ID = CANARY_SCOPE
base.MAX_PRIMARY_GENERATES = MAX_CANARY_GENERATES
base.MAX_REPAIR_GENERATES = 0
base.MAX_CONTINUITY_UPLOADS = 0

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.performance_compiler import compile_performance_r2v_prompt
from freeze_motion_experiment_017 import body_variant
from mutation_authority import MutationAuthority

SEQ = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"

F2C_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2C_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"
F2C_BINDING = {
    "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
    "asset_id": F2C_REF,
    "attestation_id": "refbind_f4277ac1a7a5651c8370212417c06593f08a003aee"
                      "1676517622292f37cb4fdf",
    "mechanism": "last_frame", "from_shot": "SEQ7_F1",
    "source_frame_sha256": F2C_REF_SHA}

BODY_BY_SHOT = {
    "SEQ7_F2C_P017_A": body_variant(True),
    "SEQ7_F2C_P017_B": body_variant(False),
    "SEQ7_F2C_P017_C": body_variant(True),
    "SEQ7_G3C_P017_D": body_variant(True),
}

SLOTS = [
    {"shot_id": "SEQ7_F2C_P017_A",
     "fixture": "fixtures/requal017/SEQ7_F2C_P017_A.json",
     "scene_id": "SCENE_F_STORM_GATE", "editorial_target_duration": 5.6,
     "binding": F2C_BINDING, "candidate": "F2C-P017-A"},
    {"shot_id": "SEQ7_F2C_P017_B",
     "fixture": "fixtures/requal017/SEQ7_F2C_P017_B.json",
     "scene_id": "SCENE_F_STORM_GATE", "editorial_target_duration": 5.6,
     "binding": F2C_BINDING, "candidate": "F2C-P017-B"},
    {"shot_id": "SEQ7_F2C_P017_C",
     "fixture": "fixtures/requal017/SEQ7_F2C_P017_C.json",
     "scene_id": "SCENE_F_STORM_GATE", "editorial_target_duration": 5.6,
     "binding": F2C_BINDING, "candidate": "F2C-P017-C"},
    {"shot_id": "SEQ7_G3C_P017_D",
     "fixture": "fixtures/requal017/SEQ7_G3C_P017_D.json",
     "scene_id": "SCENE_G_HIGH_PLATEAU", "editorial_target_duration": 3.2,
     "binding": None, "candidate": "G3C-P017-D"},
]


class PerformanceRuntime(base.FlowR2VShotRuntime):
    """Freeze through the performance compiler for 017 candidates; the
    compact compiler stays the default for every other shot."""

    def freeze(self, shot, *args, **kwargs):
        if getattr(shot, "performance_spec", None) is not None:
            kwargs["prompt_compiler"] = compile_performance_r2v_prompt
            kwargs["compiler_kwargs"] = {
                "performance_spec": shot.performance_spec,
                "body_authority": BODY_BY_SHOT[shot.shot_id]}
        return super().freeze(shot, *args, **kwargs)

    def _resume_frozen(self, prior, shot, plan, decision, reference_binding,
                       *args, **kwargs):
        if getattr(shot, "performance_spec", None) is not None:
            kwargs["prompt_compiler"] = compile_performance_r2v_prompt
            kwargs["compiler_kwargs"] = {
                "performance_spec": shot.performance_spec,
                "body_authority": BODY_BY_SHOT[shot.shot_id]}
        return super()._resume_frozen(prior, shot, plan, decision,
                                      reference_binding, *args, **kwargs)


base.FlowR2VShotRuntime = PerformanceRuntime


def make_binding_for(slot):
    def binding_for(_shot, scene_dir):
        if slot["binding"] is None:
            return {"media_id": base.BASE_REFERENCE["media_id"],
                    "asset_id": base.BASE_REFERENCE["asset_id"],
                    "attestation_id": base.BASE_REFERENCE["attestation_id"],
                    "mechanism": "same_reference"}
        return dict(slot["binding"])
    return binding_for


def main() -> None:
    from film_pipeline.live_runtime import utc_now
    CANARY_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path = CANARY_DIR / "generate_ledger.json"
    if not ledger_path.exists():
        ledger_path.write_text(json.dumps({
            "initialized_at": utc_now(), "max_primary": 4,
            "max_repair": 0, "max_uploads": 0, "primary_consumed": [],
            "repair_consumed": [], "uploads": []}, indent=1),
            encoding="utf-8")

    auth = MutationAuthority(AUTHORITY_DIR, CANARY_SCOPE)
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("package authority latched")
    auth.check_mutation_allowed("canary_generate")

    consumed = len(json.loads(ledger_path.read_text(
        encoding="utf-8"))["primary_consumed"])
    if consumed >= MAX_CANARY_GENERATES:
        raise OwnerAmbiguityGate("canary generate budget exhausted (4 max)")

    for slot in SLOTS:
        base.reference_binding_for = make_binding_for(slot)
        if slot["binding"] is not None:
            scene_dir = CANARY_DIR / f"scene_{slot['scene_id']}"
            att_src = SEQ / f"scene_{slot['scene_id']}" / \
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
        print(json.dumps({"step": "slot_start",
                          "candidate": slot["candidate"],
                          "shot_id": slot["shot_id"]}), flush=True)
        report = base.run_live_shot(
            {"shot_id": slot["shot_id"], "fixture": slot["fixture"],
             "continuity": {"kind": "performance_canary_reference",
                            "media_id": (slot["binding"] or
                                         base.BASE_REFERENCE)["media_id"]},
             "budget_kind": "primary",
             "editorial_target_duration":
                 slot["editorial_target_duration"]},
            CANARY_DIR / f"scene_{slot['scene_id']}", {})
        print(json.dumps({"step": "slot_done",
                          "candidate": slot["candidate"],
                          "gate": report.get("gate"),
                          "output": report.get("output_identity")}),
              flush=True)
        if report.get("gate") != "SHOT_PROVEN":
            print(json.dumps({"step": "slot_stopped",
                              "candidate": slot["candidate"],
                              "gate": report.get("gate"),
                              "diagnostic":
                                  str(report.get("diagnostic"))[:300]}),
                  flush=True)
            raise SystemExit(4)


if __name__ == "__main__":
    main()
