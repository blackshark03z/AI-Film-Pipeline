"""AI-FILM-QUALITY-V2-004 — Phase 0 (rebind) + Phase 1 (admission).

Rebinds EVERY frozen V2-003 director artifact by identity and re-proves
B1-B10 + the Owner timing invariant from the frozen plan file itself.
Any identity drift => BLOCKED_INVARIANT (the plan MUST NOT be
redesigned). Then mints the fresh V2-004 admission receipt and runs the
frozen admission gate BEFORE any provider mutation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import sha256
from film_pipeline.director_blocking import (
    BlockingSpec, CameraCoveragePlan, DirectorIntent,
    director_semantic_identity, validate_director_gates,
    validate_timing_invariant)
from film_pipeline.quality_repair_v2 import (
    ADMISSION_REQUIRED_FROM, QUALITY_V2_CANONICAL_BASELINE, admission_gate,
    load_frozen_debt_ids, make_experiment_admission_receipt)

PKG = ROOT / "projects/quality_v2_004_f2_blocking"
V3 = ROOT / "projects/quality_v2_003_director_blocking"
V2_002 = ROOT / "projects/quality_v2_002_f2_causality_experiment"


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)

    # ---- P0: rebind the frozen plan by identity -------------------------
    plan = json.loads((V3 / "f2_director_plan_v2_003.json").read_text(
        encoding="utf-8"))
    binding = json.loads((V3 / "director_model_binding_v2_003.json")
                         .read_text(encoding="utf-8"))
    previz = json.loads((V3 / "previz_manifest_v2_003.json").read_text(
        encoding="utf-8"))
    intent = DirectorIntent.model_validate(plan["director_intent"])
    blocking = BlockingSpec.model_validate(plan["blocking_spec"])
    camera = CameraCoveragePlan.model_validate(plan["camera_coverage_plan"])
    identity = director_semantic_identity(
        plan["semantic_identity"]["base_shot_spec_sha256"], intent,
        blocking, camera)
    identity_ok = identity["generation_semantic_identity"] == \
        plan["semantic_identity"]["generation_semantic_identity"]
    gates = validate_director_gates(intent, blocking, camera,
                                    previous_screen_direction="faces "
                                    "frame-left",
                                    next_screen_direction="faces "
                                    "frame-left")
    timing = validate_timing_invariant(blocking, usable_window_s=5.6,
                                       cross_deadline_s=4.8)
    rebind = {
        "version": "v2-004-rebind-v1",
        "checkpoint": "V2004_P0_REBOUND",
        "start_sha": "7d257bf6bf471c463f0038d38ff2131ad6a9edd5",
        "v2_003_final_head": "7d257bf6bf471c463f0038d38ff2131ad6a9edd5",
        "frozen_identities": {
            "director_intent_id": intent.director_intent_id,
            "blocking_spec_id": blocking.blocking_spec_id,
            "camera_plan_id": camera.camera_plan_id,
            "generation_semantic_identity":
                identity["generation_semantic_identity"],
            "identity_unchanged": identity_ok},
        "director_receipt": {
            "provider": "OpenAI", "model": "GPT-5.6 Sol",
            "role": "DIRECTOR_SHOT_DESIGNER",
            "authorization_source":
                binding["substitute_authorization"]["authorization_source"]},
        "b1_b10": gates,
        "timing": timing,
        "previz_manifest": previz["artifacts"],
        "v2_004_handoff": "docs/quality-v2/"
                          "V2_004_F2_BLOCKING_EXPERIMENT_HANDOFF.md",
        "canonical_f2_predecessor": {
            "selected_take_id":
                "take_91e4997b99432358ec713c072ef3a82571f65b6b43a4a48fab8cf"
                "a17f31efb67",
            "asset_sha256":
                "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c398982548"
                "90a767",
            "master_slot": 24, "trim": [0.0, 5.6]},
        "canonical_master_sha256":
            "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda17865"
            "95",
        "f1_f3_continuity": {
            "screen_direction": "faces frame-left",
            "basis": "fixtures/sequence007 SEQ7_F1/F2/F3 (mechanical "
                     "resolution, V2-003)"},
        "quality_debt": "QD-001 (ACTIVE)",
        "spatial_state_required": ["BEFORE_GATE_NEAR_SIDE",
                                   "CENTER_GATE_OPENING",
                                   "BEYOND_GATE_FAR_SIDE_CLEAR"],
        "timing_required": {"cross_by_s": 4.8, "far_side_readable_by_s": 5.6},
    }
    if not identity_ok or not gates["all_pass"] or \
            timing["state"] != "PASS":
        (PKG / "rebind_v2_004.json").write_text(
            json.dumps(rebind, indent=1), encoding="utf-8")
        raise SystemExit("BLOCKED_INVARIANT: frozen identity drift")
    (PKG / "rebind_v2_004.json").write_text(
        json.dumps(rebind, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2004_P0_REBOUND",
                      "identity": identity["generation_semantic_identity"][
                          :16],
                      "B1_B10": "ALL_PASS", "timing": "PASS"}))

    # ---- P1: admission receipt + gate (BEFORE any provider mutation) ----
    receipt = make_experiment_admission_receipt(
        experiment_id="V2-004",
        target_quality_debt_ids=["QD-001"],
        canonical_baseline_sha256=QUALITY_V2_CANONICAL_BASELINE,
        hypothesis="A frozen direct-traversal BlockingSpec plus explicit "
                   "camera coverage will produce a shot in which the "
                   "viewer unambiguously sees the swordsman move from the "
                   "near side, THROUGH the gate, to the far side without "
                   "treating the rock as a destination.",
        variables_changed=[
            "performance layer only: A pure traversal vs A+bio "
            "biomechanics refinement"],
        variables_held_constant=[
            "DirectorIntent (frozen DI id)", "BlockingSpec (frozen BS id)",
            "CameraCoveragePlan (frozen CC id)", "screen direction "
            "(faces frame-left)", "start zone (BEFORE_GATE)",
            "threshold (CENTER_GATE_OPENING)",
            "end zone (BEYOND_GATE:FAR_SIDE_CLEAR)", "travel path "
            "(DIRECT_TRAVERSAL)", "ActionIntent (frozen)",
            "provider route (qualified Flow/Veo, unchanged)",
            "reference authority (SEQ7_F1 last-frame binding)",
            "canonical predecessor"],
        max_generate_budget=2,
        provider_route="the exact currently qualified Flow/Veo route from "
                       "the frozen V1 SoT (flow_veo / veo_3_1_r2v_lite / "
                       "project 93a579b4-834e-435b-8304-5f6682937935 / "
                       "account clean-pro-qualified)",
        acceptance_criteria=[
            "S3,S4,S5,S6,S8,S9,S10,S11,S12,S13 hard-required PASS "
            "(spatial/blocking QC)",
            "IDENTITY must not REGRESS; no HIGH/CRITICAL regression",
            "no aggregate score; worker review advisory",
            "canonical promotion 0; Owner decision required"],
        owner_review_surface="OWNER_F2_BLOCKING_V2_004_REEL.mp4 + "
                             "OWNER_REVIEW/V2_004 copies + decision "
                             "template (SELECT_A/SELECT_B/REJECT_ALL/"
                             "KEEP_CANONICAL/NEEDS_REPAIR/DEFER)",
        rollback_plan="not applicable to canonical state: no canonical "
                      "mutation allowed; candidates remain evidence-only "
                      "unless the Owner selects one for a future "
                      "promotion-adapter package")
    known = load_frozen_debt_ids(ROOT)
    gate = admission_gate(receipt, known_debt_ids=known)
    if gate["status"] != "ADMITTED":
        raise SystemExit("BLOCKED_INVARIANT")
    (PKG / "experiment_admission_v2_004.json").write_text(
        json.dumps({"version": "experiment-admission-v2-004-v1",
                    "checkpoint": "V2004_P1_ADMISSION_PROVEN",
                    "admission_required_from": ADMISSION_REQUIRED_FROM,
                    "receipt": receipt, "gate_result": gate,
                    "uploads_policy": "0 unless an already-qualified "
                                      "required reference path demands "
                                      "it; otherwise STOP rather than "
                                      "inventing a new upload route",
                    "known_debt_ids": known}, indent=1),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2004_P1_ADMISSION_PROVEN",
                      "receipt_id": receipt["receipt_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
