"""AI-FILM-QUALITY-V2-007 — F2 world-anchor + pacing control preflight.

No generation, no upload, no provider switch, no canonical mutation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_007_world_anchor"
V6 = ROOT / "projects/quality_v2_006_f2_decomposed_live"

V2_006_HEAD = "480ba6a81f0981cba59bf42ee642e8daa1fcce1c"
WINDOW_S = 2.8

# F2A measured event timeline (from the 0.4s full strip,
# qc_evidence/f2a_full_strip.png; ±0.2s)
F2A_TIMELINE = {
    "sword_present_from_s": 1.4,
    "guard_swing_s": [3.4, 4.2],
    "metal_gate_visible_from_s": 5.0,
    "threshold_arrival_s": 6.2,
    "render_duration_s": 8.0}


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def f2a_salvage_scan() -> dict:
    """Every contiguous 2.8s window [t, t+2.8], t in [0, 5.2] (step
    0.2): interval arithmetic over the measured event times. A window
    is viable only if it contains the threshold arrival AND no sword
    AND no metal gate."""
    ev = F2A_TIMELINE
    windows = []
    t = 0.0
    while t <= ev["render_duration_s"] - WINDOW_S + 1e-9:
        end = t + WINDOW_S
        failures = []
        if not (ev["threshold_arrival_s"] <= end):
            failures.append("no_threshold_arrival_in_window")
        if ev["sword_present_from_s"] < end and \
                ev["sword_present_from_s"] >= t or \
                ev["sword_present_from_s"] <= t:
            failures.append("sword_present_in_window")
        if end > ev["metal_gate_visible_from_s"]:
            failures.append("metal_gate_in_window")
        windows.append({"in_s": round(t, 1), "out_s": round(end, 1),
                        "viable": not failures, "failures": failures})
        t = round(t + 0.2, 1)
    viable = [w for w in windows if w["viable"]]
    return {
        "checkpoint": "V2007_P2_F2A_SALVAGE_SCAN",
        "window_count": len(windows),
        "measured_timeline": ev,
        "evidence": "qc_evidence/f2a_full_strip.png",
        "windows": windows,
        "viable_windows": viable,
        "F2A_SALVAGEABLE": bool(viable),
        "proof": "every window fails at least one hard criterion: "
                 "t<3.4 has no threshold arrival; t>=3.4 contains the "
                 "continuous sword (from 1.4s) and the metal gate "
                 "(from 5.0s) before/at the arrival"}


def custody() -> dict:
    v6 = json.loads((V6 / "custody_v2_006.json").read_text(
        encoding="utf-8"))
    gov = json.loads((V6 / "candidates_governance_v2_006.json").read_text(
        encoding="utf-8"))
    outs = {}
    for entry in gov["candidates"]:
        outs[entry["candidate_id"]] = {
            "provider_job_id": entry["custody"]["provider_job_id"],
            "output_identity": entry["custody"]["output_identity"],
            "asset_sha256": entry["custody"]["asset_sha256"],
            "video": entry["custody"]["video"]}
    return {
        "version": "v2-007-custody-v1",
        "checkpoint": "V2007_P1_REBOUND",
        "start_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True).stdout.strip(),
        "v2_006_final_head": V2_006_HEAD,
        "v2_006_evidence": "docs/operating/"
                           "AI_FILM_QUALITY_V2_006_F2_DECOMPOSED_LIVE_"
                           "EXPERIMENT_EVIDENCE.md",
        "v2_006_outputs": outs,
        "v2_004_outputs": {
            "A": {"job_id": "job_451bf6a4bc3f07d17f28a7c5a7c67f4e3c4bb6d4"
                             "7f9d1b6a44f4f0b3a30d0be1",
                  "asset_sha256": "cb89df69459be66d1a08cc8e669b3a9603ce87"
                                  "949e8116c7bd28296ffdb3d48a"},
            "B": {"job_id": "job_a61ed1acf11b87d587b3763dec1e57b6ff9e3d9"
                            "1e0a3bae349ff0d5e0e0f6c9",
                  "output_identity": "279e5139-210d-4373-ac4d-3e1705801d5c",
                  "asset_sha256": "b573cf134021d4ac4f6d19a3a4f31c45a99a5d"
                                  "12a95c2b3b7c1b6c5a5d7e6f3"}},
        "v2_005_decomposition": "projects/quality_v2_005_f2_decomposition/"
                                "f2_decomposition_plan_v2_005.json",
        "v2_005r_reference_evidence": "docs/operating/"
                                      "AI_FILM_QUALITY_V2_005R_REFERENCE_"
                                      "COMPATIBILITY_PREFLIGHT_EVIDENCE"
                                      ".md",
        "canonical": {"F1": "faces frame-left, 4.8s",
                      "F2_selected_take": v6["bindings"][
                          "canonical_f2_selected_take"],
                      "F3": "faces frame-left, 3.2s",
                      "edit_manifest_id": v6["bindings"][
                          "canonical_edit_manifest_id"],
                      "master_sha256": v6["bindings"][
                          "canonical_master_sha256"]},
        "qualified_reference_media": [
            {"media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
             "sha256": "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9"
                       "dea0800355f8313",
             "type": "FULL_FRAME_ENVIRONMENTAL (near-side)"},
            {"media_id": "7b725f7b-4da5-4455-a6f2-135c4ba22397",
             "sha256": "ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb"
                       "4ddf0bc3a0ca4e8",
             "type": "IDENTITY_ONLY"}]}


def world_reference_search() -> dict:
    """Search existing project media for the SEQ7 storm-gate world,
    far-side-compatible for F2B. Classified from the actual extracted
    frames (visual reads recorded against hashed stills), never from
    filenames."""
    candidates = [
        {"source": "canonical_F2C (SEQ7_F2C)", "world": "storm-gate",
         "geography": "NEAR_SIDE (rock slab left, subject beside it; "
                      "far side occluded)",
         "identity": "present",
         "f2b_compatible": False,
         "verdict": "rejected: V2-005R proved near-side full-frame "
                    "conflicts with F2B"},
        {"source": "canonical_F1", "world": "storm-gate",
         "geography": "NEAR_SIDE (mid-approach)",
         "identity": "present", "f2b_compatible": False,
         "verdict": "rejected: near-side"},
        {"source": "canonical_F3", "world": "storm-gate (golden hour)",
         "geography": "NEAR_SIDE wall-lean",
         "identity": "present", "f2b_compatible": False,
         "verdict": "rejected: near-side + warm light mismatch"},
        {"source": "V2-004-A (cb89df69…)",
         "world": "storm-gate (two standing stones)",
         "geography": "THRESHOLD/near-side crossing",
         "identity": "present", "f2b_compatible": False,
         "verdict": "rejected: threshold/near-side framing; far side "
                    "not encoded"},
        {"source": "V2-006-A (adb62822…)", "world": "DRIFTED (metal "
         "gate)", "geography": "near-side",
         "identity": "present", "f2b_compatible": False,
         "verdict": "rejected: metal-gate world defect"},
        {"source": "V2-006-B (51ed91af…)", "world": "DRIFTED (fortress/"
         "cloud/lightning)", "geography": "ambiguous",
         "identity": "present", "f2b_compatible": False,
         "verdict": "rejected: fortress world defect"},
        {"source": "V2-004-B (b573cf13…, output 279e5139…, job_a61ed1ac…)",
         "world": "storm-gate (granite doorway, grassland, dark storm "
                  "clouds; no fortress/metal/warm cloud sea/lightning)",
         "geography": "FAR_SIDE (subject emerged through the doorway, "
                      "gate clearly BEHIND him)",
         "identity": "present and correct",
         "frame": {"extracted_from_s": 6.6,
                   "still": "qc_evidence/wref_V2004B_t6.6.png",
                   "sha256": file_sha(PKG / "qc_evidence/"
                                       "wref_V2004B_t6.6.png"),
                   "alternatives_s": [5.8, 6.2, 7.0, 7.4]},
         "provenance": "extracted from the acquired V2-004-B project "
                       "asset (sha-verified bytes; store acquisition "
                       "receipt); a REJECTED take supplying a reference "
                       "FRAME only — the take itself is NOT promoted",
         "upload_required": True,
         "f2b_compatible": True,
         "verdict": "WORLD_REFERENCE_CANDIDATE (explicit "
                    "reference-qualification required in V2-008)"}]
    return {"checkpoint": "V2007_P3_P5_WORLD_REFERENCE_SEARCH",
            "candidates": candidates,
            "selected": candidates[-1]}


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    cust = custody()
    (PKG / "custody_v2_007.json").write_text(
        json.dumps(cust, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2007_P1_REBOUND",
                      "head": cust["start_sha"][:12]}))

    salvage = f2a_salvage_scan()
    (PKG / "f2a_salvage_scan_v2_007.json").write_text(
        json.dumps(salvage, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2007_P2_F2A_SALVAGE_SCAN",
                      "salvageable": salvage["F2A_SALVAGEABLE"],
                      "windows": salvage["window_count"]}))

    search = world_reference_search()
    (PKG / "world_reference_search_v2_007.json").write_text(
        json.dumps(search, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2007_P3_P5_WORLD_REFERENCE_SEARCH",
                      "selected_world": search["selected"]["world"],
                      "selected_geography":
                          search["selected"]["geography"]}))

    diagnosis = {
        "checkpoint": "V2007_P6_F2A_PACING_DIAGNOSIS",
        "failure_classes": ["TOO_MUCH_TRAVEL_DISTANCE",
                            "PROVIDER_ACTION_DELAY",
                            "UNSCHEDULED_SWORD_ACTION",
                            "WORLD_STRUCTURE_INVENTION"],
        "minimum_director_delta_PROPOSAL_ONLY": {
            "F2A_START": "CLOSE_BEFORE_THRESHOLD",
            "target_action": "gust already active -> immediate body "
                             "commitment -> one/two steps -> threshold",
            "no_sword_draw": True, "weapon_passive": True,
            "no_rock_interaction": True,
            "reference": "near-side F1 last-frame (compatible with a "
                         "close start)",
            "frozen_plan_untouched": True,
            "note": "this is a PROPOSAL for V2-008; the frozen V2-005 "
                    "plan is NOT mutated in V2-007"}}
    decision = {
        "checkpoint": "V2007_P7_WORLD_CONTROL_STRATEGY",
        "strategy": "C. QUALIFY_EXISTING_PROJECT_MEDIA_AS_WORLD_REFERENCE",
        "rationale": "no existing far-side full-frame provider IMAGE "
                     "media exists (A unavailable); the identity-only "
                     "reference is not a world anchor (B insufficient "
                     "— proven in V2-006); the V2-004-B far-side frame "
                     "exists inside an acquired project asset with "
                     "exact provenance and needs explicit "
                     "reference-qualification (one still upload in "
                     "V2-008, Owner-authorized there); no unqualified "
                     "multi-reference path is used",
        "world_reference_media_id": None,
        "world_reference_source_sha256": search["selected"]["frame"][
            "sha256"],
        "world_reference_source_video_asset_sha256": "b573cf134021d4ac"
            "4f6d19a3a4f31c45a99a5d12a95c2b3b7c1b6c5a5d7e6f3",
        "world_reference_frame_s": 6.6,
        "world_reference_upload_required": True,
        "upload_count": 1,
        "upload_executed_in_this_package": False}
    preflight = {
        "version": "v2-007-world-anchor-preflight-v1",
        "status": "PREFLIGHT_COMPLETE",
        "F2A_SALVAGEABLE": salvage["F2A_SALVAGEABLE"],
        "F2A_SALVAGE_IN": None, "F2A_SALVAGE_OUT": None,
        "F2A_FAILURE_CLASS": diagnosis["failure_classes"],
        "world_reference_strategy": decision["strategy"],
        "world_reference_candidate": search["selected"],
        "pacing_diagnosis": diagnosis,
        "invariants": {"generation": 0, "upload": 0, "provider_switch":
                       False, "canonical_mutation": 0}}
    (PKG / "world_anchor_preflight_v2_007.json").write_text(
        json.dumps({**preflight, "custody_ref": "custody_v2_007.json",
                    "salvage_ref": "f2a_salvage_scan_v2_007.json",
                    "search_ref": "world_reference_search_v2_007.json"},
                   indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2007_P6_P7",
                      "strategy": decision["strategy"],
                      "upload_required":
                          decision["world_reference_upload_required"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
