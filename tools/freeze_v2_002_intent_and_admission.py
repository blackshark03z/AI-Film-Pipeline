"""AI-FILM-QUALITY-V2-002 — Phase 1 (intent freeze) + Phase 2 (admission).

P1: freeze the Owner-approved redesigned F2 intent VERBATIM from the
work package, bound to the exact canonical predecessor / narrative
authority / quality debt / fingerprint. Nothing is generated here.

P2: mint the ExperimentAdmissionReceipt and run the frozen
admission_gate (BLOCKED_INVARIANT on any violation).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import sha256
from film_pipeline.quality_repair_v2 import (
    ADMISSION_REQUIRED_FROM, QUALITY_V2_CANONICAL_BASELINE,
    admission_gate, load_frozen_debt_ids, make_experiment_admission_receipt)

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"

# --- exact canonical bindings (P0) --------------------------------------
CANONICAL_F2 = {
    "shot_id": "SEQ7_F2C",
    "master_slot": 24,
    "selected_take_id": "take_91e4997b99432358ec713c072ef3a82571f65b6b43a4a"
                        "48fab8cfa17f31efb67",
    "asset_id": "asset_4cfb8757f62442b325e7b03f836ef13f659d550695e03c60a0a9"
                "86b8de10fb7c",
    "asset_sha256": "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c3989"
                    "8254890a767",
    "editorial_range_id": "er_790f3678253d8339beb1f5f5aeaef636ca5f547784af"
                          "0f459a99f817b1c7349c",
    "selected_duration_s": 5.6,
    "source_in_s": 0.0, "source_out_s": 5.6,
    "handles_in_s": 0.0, "handle_out_s": 2.4,
    "canonical_video": "projects/flow_upload_contract_requal_009/reproof/"
                       "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
                       "c1a69047933565230870ad22.mp4",
    "neighbors": {"previous_slot": "23_SEQ7_F1",
                  "next_slot": "25_SEQ7_F3"}}

NARRATIVE_AUTHORITY = {
    "sequence_plan": "fixtures/sequence007/sequence_plan_007.json",
    "scene_id": "SCENE_F_STORM_GATE",
    "action_authority_trace": "projects/flow_action_intent_causality_018/"
                              "action_authority_trace_018.json",
    "gate_A1": "RESOLVED",
    "neighbors": {"F1": "fixtures/sequence007/SEQ7_F1.json",
                  "F2": "fixtures/sequence007/SEQ7_F2.json",
                  "F3": "fixtures/sequence007/SEQ7_F3.json"}}

# --- P1: the Owner-approved intent, VERBATIM from the work package ------
INTENT_TEXT = {
    "TRIGGER": "A strong gust suddenly sweeps across the stone gate and "
               "obstructs his path.",
    "GOAL": "The swordsman must get THROUGH the gate and continue onward. "
            "His goal is NOT to hide behind the rock.",
    "ACTION_LOGIC": [
        "he perceives the direction/force of the gust",
        "lowers his center of gravity against the wind",
        "advances deliberately through the gust",
        "may touch/brace against the stone only as a temporary "
        "balance/support point",
        "continues moving until he has clearly passed through the gate"],
    "OUTCOME": "He emerges on the far side of the gate, pauses briefly to "
               "recover, then is ready to continue the journey.",
    "CRITICAL_NEGATIVES": [
        "do NOT turn the action into taking cover behind the rock",
        "do NOT make \"brace at rock\" the terminal state",
        "do NOT run toward rock without clear purpose",
        "do NOT touch the rock as an isolated meaningless gesture",
        "do NOT end before the through-state is visually clear"],
    "DESIGN_AUTHORITY_STATEMENT": "This is Owner-approved design authority "
                                  "for V2-002. Do NOT add new story events.",
}


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)

    # ---- P1: owner-approved intent ------------------------------------
    intent_fingerprint = sha256({"kind": "owner-approved-f2-intent",
                                 "text": INTENT_TEXT})
    intent = {
        "version": "owner-approved-f2-intent-v2-002-v1",
        "checkpoint": "V2002_P1_INTENT_FROZEN",
        "owner_source": "work package AI-FILM-QUALITY-V2-002 (Owner "
                        "conveyed the redesigned F2 intent verbatim in the "
                        "package; recorded by the execution worker)",
        "target_shot": "SEQ7_F2C (canonical F2, master slot 24)",
        "canonical_predecessor": CANONICAL_F2,
        "narrative_authority": NARRATIVE_AUTHORITY,
        "quality_debt": "QD-001 ACTION_CAUSAL_LOGIC",
        "intent_fingerprint": intent_fingerprint,
        "scope_limits": ["no new story events",
                         "no provider/model switch",
                         "no promotion in this package"],
        "intent": INTENT_TEXT,
    }
    (PKG / "owner_approved_f2_intent_v2_002.json").write_text(
        json.dumps(intent, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P1_INTENT_FROZEN",
                      "intent_fingerprint": intent_fingerprint}))

    # ---- P2: admission receipt + gate ---------------------------------
    receipt = make_experiment_admission_receipt(
        experiment_id="V2-002",
        target_quality_debt_ids=["QD-001"],
        canonical_baseline_sha256=QUALITY_V2_CANONICAL_BASELINE,
        hypothesis="Redesigned F2 action logic will make trigger/goal/"
                   "outcome readable to the Owner in blind review without "
                   "identity or editorial regression.",
        variables_changed=[
            "dramatic purpose / ActionIntent structure",
            "shot action beats",
            "associated PerformanceSpec necessary to execute the new logic"],
        variables_held_constant=[
            "provider (flow_veo)", "model (veo_3_1_r2v_lite)",
            "reference identity authority (SEQ7_F1 last-frame binding)",
            "world/look authority", "aspect ratio (16:9 1280x720)",
            "target editorial slot (master slot 24, 5.6s trim)",
            "causal compiler family (flow-r2v-causal-compact-v1)",
            "canonical predecessor (take_91e4997b…)"],
        max_generate_budget=2,
        provider_route="the exact currently qualified Flow/Veo route from "
                       "the frozen V1 SoT (flow_veo / veo_3_1_r2v_lite / "
                       "project 93a579b4-834e-435b-8304-5f6682937935 / "
                       "account clean-pro-qualified)",
        acceptance_criteria=[
            "V2 frozen ten-condition acceptance policy (C1-C10)",
            "canonical promotion DISABLED in this package: if the Owner "
            "selects a candidate, STOP at OWNER_SELECTED; V2-003 "
            "qualifies the real PromotionEnvironment and performs "
            "promotion"],
        owner_review_surface="blind legibility packet + side-by-side "
                             "compare reel + 10-dimension tradeoff summary",
        rollback_plan="not applicable to canonical state because no "
                      "canonical mutation is allowed; all candidates "
                      "remain evidence-only unless selected for future "
                      "V2-003")
    known = load_frozen_debt_ids(ROOT)
    gate = admission_gate(receipt, known_debt_ids=known)
    if gate["status"] != "ADMITTED":
        raise SystemExit("BLOCKED_INVARIANT")
    (PKG / "experiment_admission_v2_002.json").write_text(
        json.dumps({"version": "experiment-admission-v2-002-v1",
                    "checkpoint": "V2002_P2_ADMISSION_PROVEN",
                    "admission_required_from": ADMISSION_REQUIRED_FROM,
                    "receipt": receipt,
                    "gate_result": gate,
                    "known_debt_ids": known}, indent=1), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P2_ADMISSION_PROVEN",
                      "receipt_id": receipt["receipt_id"],
                      "status": gate["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
