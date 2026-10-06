"""V2-011R — repair specs, compiled prompts, pre-render QC gates."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011r_targeted_repair"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


F2A_R_PROMPT = (
    "Generate a 5-second cinematic video, 16:9, locked camera. The camera "
    "stands BESIDE the road at its edge, filming the scene strictly from "
    "the SIDE, in full profile view. A swordsman in flowing white robes "
    "with a black sash and a topknot walks along a mountain road that "
    "crosses a continuous natural rock ridge, traveling from the RIGHT "
    "side of the frame toward the LEFT — pure lateral side-profile "
    "travel, never toward the camera and never away from it. He passes "
    "into the single narrow gap in the natural rock ridge — the only "
    "walkable opening — and the shot ends while he is inside that gap, "
    "still moving left. The rock ridge is natural, rough and continuous, "
    "extending beyond the opening on both sides, closing every bypass; "
    "the road visibly funnels into the gap. A hard gust blows from the "
    "left, directly against his direction of travel: his robes press "
    "flat on the windward side and stream leeward to the right, his "
    "headband streams leeward, the grass bends leeward, and he leans "
    "into the gust, forcing every step with visible muscular effort. "
    "Cool storm-blue light, overcast sky. No sword, no scabbard, no "
    "weapon. No gate, no cut stone, no architecture — natural rock only.")

F2B_R_PROMPT = (
    "Generate a 5-second cinematic video, 16:9, locked camera. The camera "
    "stands BESIDE the road at its edge, filming strictly from the SIDE, "
    "in full profile view. The same swordsman in flowing white robes with "
    "a black sash and a topknot breaks out of the single narrow gap in a "
    "continuous natural rock ridge and continues along the open mountain "
    "road beyond, traveling from the RIGHT side of the frame toward the "
    "LEFT — pure lateral side-profile travel, never toward the camera, "
    "never away from it. The natural rock ridge he forced through is "
    "behind him to the right of frame; the road ahead continues open "
    "toward the left. The same hard gust funnels through the gap behind "
    "him against his direction of travel: his robes press flat on the "
    "windward side and stream leeward to the right, his headband streams "
    "leeward, grass bends leeward, dust moves with the wind, and his "
    "first steps remain effortful before easing slightly as he clears "
    "the gap. The ridge is natural, rough and continuous, extending "
    "beyond the opening on both sides. Cool storm-blue light, overcast "
    "storm sky. No sword, no scabbard, no weapon. No gate, no cut stone "
    "blocks, no mortar, no lintel, no roof, no parapet, no castle, no "
    "fortress, no built architecture of any kind — natural rock only.")

SPECS = {
    "F2A-R": {
        "budget_kind": "f2a_r", "shot_id": "SEQ7_F2A_R",
        "prompt": F2A_R_PROMPT,
        "repair_target": "TRAVEL AXIS ONLY — everything that passed 011A "
                         "is preserved verbatim (world, wardrobe, no-sword, "
                         "causal wind, start/end states)",
        "changes_vs_failed_prompt": [
            "camera BESIDE the traversal axis, full profile view",
            "explicit right-to-left lateral crossing",
            "'never toward the camera and never away from it'",
            "wind vector tied to frame geometry (from the LEFT, streaming "
            "to the RIGHT) so all vectors agree with lateral travel"],
        "pre_render_gates": {
            "travel_direction == frame_left": ["RIGHT side of the frame",
                                               "toward the LEFT"],
            "camera_axis_profile": ["BESIDE the road", "profile"],
            "no_sword_negative": ["No sword"],
            "natural_pass": ["natural rock ridge", "single narrow gap"],
            "causal_wind_vectors": ["stream leeward", "leans"],
            "storm_palette": ["storm-blue"]},
    },
    "F2B-R": {
        "budget_kind": "f2b_r", "shot_id": "SEQ7_F2B_R",
        "prompt": F2B_R_PROMPT,
        "repair_target": "FULL REBUILD of world/prop/light/action against "
                         "the frozen spec; continuity derived from the "
                         "accepted F2A-R end-state (lateral axis, natural "
                         "ridge, storm palette, no sword)",
        "changes_vs_failed_prompt": [
            "explicit negative-architecture block (no cut blocks/mortar/"
            "lintel/roof/parapet/castle/fortress)",
            "explicit no-sword/no-scabbard/no-weapon",
            "cool storm-blue + overcast storm sky (no warm plain)",
            "causal wind vectors enumerated (lean/cloth/headband/grass/"
            "dust) with effortful first steps",
            "lateral frame-left exit with the ridge behind to frame-right"],
        "pre_render_gates": {
            "travel_direction == frame_left": ["RIGHT side of the frame",
                                               "toward the LEFT"],
            "camera_axis_profile": ["profile"],
            "natural_pass": ["natural rock ridge", "gap"],
            "no_built_architecture_negatives": ["No gate, no cut stone",
                                                "no castle, no", "fortress"],
            "no_sword_negative": ["No sword"],
            "storm_palette": ["storm-blue", "storm sky"],
            "causal_wind_vectors": ["stream leeward", "effortful",
                                    "grass bends"]},
    },
}


def _strip_sanctioned_negatives(prompt: str) -> str:
    """Remove the sanctioned negative constructions so the forbidden-word
    scan only sees POSITIVE uses."""
    negative_clauses = [
        r"no sword[^.]*", r"no scabbard[^.]*", r"no weapon[^.]*",
        r"no gate[^.]*", r"no cut stone[^.]*", r"no mortar[^.]*",
        r"no lintel[^.]*", r"no roof[^.]*", r"no parapet[^.]*",
        r"no castle[^.]*", r"no fortress[^.]*", r"no built architecture[^.]*",
        r"no architecture[^.]*", r"never toward[^.]*", r"never away[^.]*",
    ]
    cleaned = prompt
    for clause in negative_clauses:
        cleaned = re.sub(clause, " ", cleaned, flags=re.I)
    return cleaned


FORBIDDEN_POSITIVE = {
    "F2A-R": ["sword", "scabbard", "gate", "castle", "fortress",
              "toward the camera", "away from the camera", "lintel",
              "parapet", "golden"],
    "F2B-R": ["sword", "scabbard", "weapon", "gate", "cut stone",
              "mortar", "lintel", "roof", "parapet", "castle", "fortress",
              "toward the camera", "away from the camera", "warm"],
}


def pre_render_qc(shot: str) -> dict:
    spec = SPECS[shot]
    prompt = spec["prompt"]
    gate_results = {}
    for gate, tokens in spec["pre_render_gates"].items():
        gate_results[gate] = all(t.lower() in prompt.lower() for t in tokens)
    cleaned = _strip_sanctioned_negatives(prompt)
    forbidden_hits = [w for w in FORBIDDEN_POSITIVE[shot]
                      if re.search(rf"\b{re.escape(w)}\b", cleaned, re.I)]
    gate_results["forbidden_concepts_absent_from_positive_context"] = \
        not forbidden_hits
    all_pass = all(gate_results.values())
    return {"shot": shot, "prompt_sha256": hashlib.sha256(
                prompt.encode()).hexdigest(),
            "gate_results": gate_results,
            "forbidden_positive_hits": forbidden_hits,
            "verdict": "PASS" if all_pass else "STOPPED_PRE_RENDER_SPEC_GAP"}


def main() -> int:
    out = {"version": "v2-011r-repair-specs-v1",
           "checkpoint": "V2011R_P1_REPAIR_SPECS",
           "built_at": utcnow(),
           "authority": "frozen V2-009 plan + V2-008 intent blocks + "
                        "V2-011A repair findings; generated outputs are "
                        "NOT creative authority",
           "mutation_budget": {"f2a_r": 1, "f2b_r": 1, "max": 2,
                               "no_retry": True},
           "lowest_escalation_rationale": {
               "F2A-R": "only the direction failed — lateral-axis prompt "
                        "enforcement, no new control surfaces (no image "
                        "attach: unreversed provider surface)",
               "F2B-R": "structural rebuild via text: negative-"
                        "architecture block + no-weapon + storm palette + "
                        "enumerated causal wind vectors + lateral axis"},
           "specs": {k: {kk: vv for kk, vv in v.items()
                         if kk != "prompt"} for k, v in SPECS.items()},
           "prompts": {k: v["prompt"] for k, v in SPECS.items()},
           "pre_render_qc": {}}
    for shot in ("F2A-R", "F2B-R"):
        qc = pre_render_qc(shot)
        out["pre_render_qc"][shot] = qc
        print(json.dumps({"shot": shot, "verdict": qc["verdict"],
                          "gates": qc["gate_results"]}))
    (PKG / "V2_011R_REPAIR_SPECS.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = all(q["verdict"] == "PASS" for q in out["pre_render_qc"].values())
    print(json.dumps({"checkpoint": "V2011R_PRE_RENDER_QC",
                      "all_pass": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
