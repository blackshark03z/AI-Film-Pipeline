"""AI-FILM-QUALITY-V2-008 (Phase 8-9): the bounded world-anchored live
runner. Budget: exactly 2 Generates (1 F2A close-start revised, 1 F2B
with the newly qualified far-side WORLD reference — submitted only
after F2A completes with clean attribution). 0 retries. Any ambiguity
latches the scope."""
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

PKG_DIR = ROOT / "projects/quality_v2_008_world_anchored_live"
AUTHORITY_DIR = PKG_DIR / "generate_scope"
SCOPE = "QUALITY-V2-008-WORLD-ANCHORED"
MAX_GENERATES = 2

import run_production_scale_007 as base

base.RUN_DIR = PKG_DIR / "generate_scope"
base.SCOPE_ID = SCOPE
base.MAX_PRIMARY_GENERATES = MAX_GENERATES
base.MAX_REPAIR_GENERATES = 0
base.MAX_CONTINUITY_UPLOADS = 0

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.performance_compiler import compile_causal_r2v_prompt
from freeze_causal_experiment_018 import body_variant
from mutation_authority import MutationAuthority

SEQ = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"

F2A_REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
F2A_REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"
F2A_BINDING = {
    "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
    "asset_id": F2A_REF,
    "attestation_id": "refbind_f4277ac1a7a5651c8370212417c06593f08a003aee"
                      "1676517622292f37cb4fdf",
    "mechanism": "last_frame", "from_shot": "SEQ7_F1",
    "source_frame_sha256": F2A_REF_SHA}

qualification = json.loads((PKG_DIR / "reference_qualification_v2_008.json")
                            .read_text(encoding="utf-8"))
F2B_BINDING = {
    "media_id": qualification["binding"]["media_id"],
    "asset_id": qualification["binding"]["asset_id"],
    "attestation_id": qualification["binding"]["attestation_id"],
    "mechanism": "far_side_world_frame",
    "source_frame_sha256": qualification["binding"]["frame_sha256"]}

F2A_ATT_SRC = SEQ / "scene_SCENE_F_STORM_GATE" / \
    "continuity_reference" / "attestation"
F2B_ATT_SRC = PKG_DIR / "continuity_reference" / "attestation"

BODY_BY_SHOT = {
    "SEQ7_F2A_V2_008": body_variant(True),
    "SEQ7_F2B_V2_008": body_variant(True),
}

SLOTS = [
    {"shot_id": "SEQ7_F2A_V2_008",
     "fixture": "fixtures/requal008/SEQ7_F2A_V2_008.json",
     "scene_id": "SCENE_F_STORM_GATE", "editorial_target_duration": 2.8,
     "binding": F2A_BINDING, "candidate": "F2A-V2-008",
     "attestation_src": F2A_ATT_SRC},
    {"shot_id": "SEQ7_F2B_V2_008",
     "fixture": "fixtures/requal008/SEQ7_F2B_V2_008.json",
     "scene_id": "SCENE_F_FAR_SIDE", "editorial_target_duration": 2.8,
     "binding": F2B_BINDING, "candidate": "F2B-V2-008",
     "attestation_src": F2B_ATT_SRC},
]


class WorldAnchoredRuntime(base.FlowR2VShotRuntime):

    def freeze(self, shot, *args, **kwargs):
        if getattr(shot, "performance_spec", None) is not None:
            kwargs["prompt_compiler"] = compile_causal_r2v_prompt
            kwargs["compiler_kwargs"] = {
                "performance_spec": shot.performance_spec,
                "body_authority": BODY_BY_SHOT[shot.shot_id],
                "action_intent": shot.action_intent}
        return super().freeze(shot, *args, **kwargs)

    def _resume_frozen(self, prior, shot, plan, decision, reference_binding,
                       *args, **kwargs):
        if getattr(shot, "performance_spec", None) is not None:
            kwargs["prompt_compiler"] = compile_causal_r2v_prompt
            kwargs["compiler_kwargs"] = {
                "performance_spec": shot.performance_spec,
                "body_authority": BODY_BY_SHOT[shot.shot_id],
                "action_intent": shot.action_intent}
        return super()._resume_frozen(prior, shot, plan, decision,
                                      reference_binding, *args, **kwargs)


base.FlowR2VShotRuntime = WorldAnchoredRuntime


def make_binding_for(slot):
    def binding_for(_shot, scene_dir):
        return dict(slot["binding"])
    return binding_for


def main() -> None:
    from film_pipeline.live_runtime import utc_now
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path = PKG_DIR / "generate_ledger.json"
    if not ledger_path.exists():
        ledger_path.write_text(json.dumps({
            "initialized_at": utc_now(), "max_primary": MAX_GENERATES,
            "max_repair": 0, "max_uploads": 0, "primary_consumed": [],
            "repair_consumed": [], "uploads": []}, indent=1),
            encoding="utf-8")

    auth = MutationAuthority(AUTHORITY_DIR, SCOPE)
    if auth.authority == "LATCHED_CLOSED":
        raise OwnerAmbiguityGate("package authority latched")
    auth.check_mutation_allowed("primary_generate")

    consumed = len(json.loads(ledger_path.read_text(
        encoding="utf-8"))["primary_consumed"])
    if consumed >= MAX_GENERATES:
        raise OwnerAmbiguityGate("generate budget exhausted (2 max)")

    for slot in SLOTS:
        base.reference_binding_for = make_binding_for(slot)
        scene_dir = PKG_DIR / f"scene_{slot['scene_id']}"
        att_dst = scene_dir / "continuity_reference" / "attestation"
        att_dst.mkdir(parents=True, exist_ok=True)
        for item in slot["attestation_src"].iterdir():
            target = att_dst / item.name
            if not target.exists():
                if item.suffix == ".json":
                    target.write_text(item.read_text(encoding="utf-8"),
                                      encoding="utf-8")
                else:
                    target.write_bytes(item.read_bytes())
        if slot["candidate"] == "F2B-V2-008":
            binding = slot["binding"]
            qual = json.loads((PKG_DIR /
                               "reference_qualification_v2_008.json")
                              .read_text(encoding="utf-8"))
            assert binding["media_id"] == qual["binding"]["media_id"], \
                "F2B must use EXACTLY the newly qualified far-side media"
            assert binding["source_frame_sha256"] != F2A_REF_SHA
            assert binding["mechanism"] == "far_side_world_frame"
            assert not any(p.name.startswith("fecf669e")
                           for p in att_dst.iterdir()), \
                "old near-side reference leaked into F2B"
            assert not any(p.name.startswith("refbind_57abbee5")
                           for p in att_dst.iterdir()), \
                "old identity-only reference leaked into F2B"
        print(json.dumps({"step": "slot_start",
                          "candidate": slot["candidate"],
                          "shot_id": slot["shot_id"],
                          "reference_media_id":
                              slot["binding"]["media_id"]}), flush=True)
        report = base.run_live_shot(
            {"shot_id": slot["shot_id"], "fixture": slot["fixture"],
             "continuity": {"kind": "quality_v2_world_anchored",
                            "media_id": slot["binding"]["media_id"]},
             "budget_kind": "primary",
             "editorial_target_duration":
                 slot["editorial_target_duration"]},
            scene_dir, {})
        print(json.dumps({"step": "slot_done",
                          "candidate": slot["candidate"],
                          "gate": report.get("gate"),
                          "output": report.get("output_identity")}),
              flush=True)
        if report.get("gate") == "SHOT_PROVEN":
            continue
        if report.get("gate") == "PROVIDER_RENDER_FAILED_NOT_CHARGED":
            print(json.dumps({"step": "candidate_failed_continuing",
                              "candidate": slot["candidate"]}), flush=True)
            continue
        print(json.dumps({"step": "slot_stopped",
                          "candidate": slot["candidate"],
                          "gate": report.get("gate"),
                          "diagnostic":
                              str(report.get("diagnostic"))[:300]}),
              flush=True)
        raise SystemExit(4)


if __name__ == "__main__":
    main()
