"""AI-FILM-QUALITY-V2-010D — Duration Authority evidence builder.

Consolidates the read-only duration-authority proof:
  1. REQUEST-FIELD carrier: chat_ability.ability_param.duration (from 010C
     F2A release body: UI default 10s → duration:10 while the prompt text
     said "5-second") — prompt text is NOT authoritative.
  2. UI CONTROL: composer duration chip (observed "10s ▾" after video mode).
  3. UI MAPPING PROVEN (read-only, zero dispatch): chip 10s → click → "5s"
     → chip reads "5s"; structural mapping UI class → ability_param.duration.
  4. PRE-DISPATCH GATE: verify_duration_pre_dispatch(5) fail-closed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C10C = ROOT / "projects/quality_v2_010c_dola_fullstack"
PKG = ROOT / "projects/quality_v2_010d_f2b_completion"
sys.path.insert(0, str(ROOT / "tools"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    f2a = json.loads((C10C / "generation_attempt_f2a.json")
                     .read_text(encoding="utf-8"))
    body = f2a.get("release_body_structure") or {}
    ability = body.get("chat_ability") or {}
    ability_param = json.loads(ability.get("ability_param") or "{}") \
        if isinstance(ability.get("ability_param"), str) else \
        (ability.get("ability_param") or {})
    exploration = json.loads((PKG / "V2_010D_DURATION_UI_EXPLORATION.json")
                             .read_text(encoding="utf-8"))
    selection = json.loads((PKG / "V2_010D_DURATION_SELECTION_TEST.json")
                           .read_text(encoding="utf-8"))

    evidence = {
        "version": "v2-010d-duration-authority-v1",
        "checkpoint": "V2010D_P1_DURATION_AUTHORITY",
        "built_at": utcnow(),
        "finding": "provider duration is a TRANSPORT-CONTROLLED PARAMETER, "
                   "not prompt text",
        "request_field_carrier": {
            "field": "chat_ability.ability_param (JSON string) .duration",
            "observed_in_010C_F2A_release_body": {
                "ability_type": ability.get("ability_type"),
                "ability_param_duration": ability_param.get("duration"),
                "ability_param_model": ability_param.get("model"),
                "prompt_text_same_body": "Generate a 5-second cinematic "
                                         "video… (inside "
                                         "input_box_content."
                                         "user_input_content)",
                "actual_output_duration_s": 10.08,
                "conclusion": "duration=10 (UI default) overrode the "
                              "'5-second' prompt text"},
            "m2_counter_case": "the follow-up conversion dispatch carried NO "
                               "chat_ability at all (server-side agent "
                               "decision, 5.04s output) — a different flow, "
                               "not the video-mode path"},
        "ui_control": {
            "control": "composer duration chip with dropdown (observed "
                       "'10s ▾' next to the active 動画を作成 chip; siblings: "
                       "モデル 2.0高速 ▾, 比率 ▾)",
            "exploration_zero_dispatch": exploration.get(
                "no_dispatch_assert"),
        },
        "ui_mapping_proof_readonly": {
            "method": "click chip → dropdown → select '5s' → chip re-read",
            "chip_before": selection.get("chip_before"),
            "chip_after": selection.get("chip_after"),
            "proof_ok": selection.get("duration_proof_ok"),
            "completion_posts_during": selection.get(
                "completion_posts_during_exploration"),
            "screenshot": "duration_selected_5s.png",
            "structural_step": "UI class → chat_ability.ability_param."
                               "duration (1:1, proven in the 10s direction "
                               "by the 010C F2A body; the 5s selection "
                               "therefore maps to duration:5 — verified "
                               "post-release in V2_010D_F2B_EVIDENCE.json)"},
        "pre_dispatch_gate": {
            "rule": "video mode active AND chip == '5s' AND zero completion "
                    "POSTs before the user action, else "
                    "STOPPED_DURATION_AUTHORITY_GAP with no mutation",
            "implemented_in": "tools/dola_010d_adapter_delta.py::"
                              "verify_duration_pre_dispatch",
        },
        "credit_expectation": {
            "5s_class_cost": 1,
            "basis": "010C provider credit texts: 10s class = 2 credits, "
                     "1 remaining at F2B refusal; arithmetic 4/day",
        },
        "integrity": {
            "duration_ui_exploration_sha256_12": hashlib.sha256(
                (PKG / "V2_010D_DURATION_UI_EXPLORATION.json")
                .read_bytes()).hexdigest()[:12],
            "duration_selection_test_sha256_12": hashlib.sha256(
                (PKG / "V2_010D_DURATION_SELECTION_TEST.json")
                .read_bytes()).hexdigest()[:12]},
    }
    (PKG / "V2_010D_DURATION_AUTHORITY.json").write_text(
        json.dumps(evidence, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010D_DURATION_AUTHORITY_WRITTEN",
                      "carrier_field": "chat_ability.ability_param.duration",
                      "ui_proof": selection.get("duration_proof_ok"),
                      "no_dispatch": selection.get("no_dispatch_assert")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
