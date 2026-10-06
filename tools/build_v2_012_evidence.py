"""V2-012 final evidence builder — fail-closed (recomputes custody SHAs)."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P11D = ROOT / "projects/quality_v2_011d_world_matched_context"
PKG = ROOT / "projects/quality_v2_012_f3r_policy_repair"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write(name, payload):
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")
    print("wrote", name)


f1r_sha = sha256(P11D / "assets" / "f1r.mp4")
f2_sha = sha256(P11D / "inputs_F2_proof.mp4")
f3r_sha = sha256(PKG / "assets" / "f3r_012.mp4")
assert f1r_sha == "b879f21586392fa7463021f60853b1aa99fecb286890dad1b3f192c6dd805171"
assert f2_sha == "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"
assert f3r_sha == "b558f8e89ae4664ca6d7325f84fcf18ad17174bc72caa12773354266c2427bbb"
proof_sha = sha256(PKG / "outputs" / "F1R_F2_F3R_SEQUENCE_PROOF.mp4")
assert proof_sha == "63eac46c7a5568ba4a3c1f0ffe54d911f7d96d35d3369bab59c70fe31c1b30ef"
print("custody verified: F1R/F2/F3R_012/PROOF")

spec = json.loads((PKG / "V2_012_F3R_REPAIRED_SPEC.json").read_text(encoding="utf-8"))
runner_ev = json.loads((PKG / "V2_012_F3R_EVIDENCE.json").read_text(encoding="utf-8"))
slot = json.loads((PKG / "slot_f3r_012" / "mutation_authority.json").read_text(encoding="utf-8"))

# ---- creative QC -----------------------------------------------------------
write("V2_012_F3R_CREATIVE_QC.json", {
    "version": "v2-012-f3r-creative-qc-v1",
    "checkpoint": "V2012_F3R_CREATIVE_QC",
    "recorded_at": utcnow(),
    "asset": {"path": "assets/f3r_012.mp4", "sha256": f3r_sha,
              "probe": {"frames": 121, "fps": "24/1", "codec": "hevc",
                        "width": 1280, "height": 720,
                        "duration_s": 5.088005}},
    "palette": {"measured": {"luma": 78.74, "u": 138.36, "v": 115.68},
                "target_f2_end_region": {"luma": 99.10, "u": 141.53,
                                         "v": 112.97},
                "verdict": "PASS — same cold blue-grey family; F3R_012 "
                           "slightly darker/moodier; the replaced canonical "
                           "F3 was warm 139"},
    "hard_qc": {
        "WORLD": {
            "natural_dark_rock": {"verdict": "PASS", "evidence": "dark jagged natural rock face fills frame-right; rough natural stone"},
            "same_world_family_as_F2": {"verdict": "PASS", "evidence": "continuous with the locked F2 ridge material; misty mountain backdrop consistent with the mountain-road world"},
            "no_masonry": {"verdict": "PASS", "evidence": "zero built/cut/tan stone anywhere"},
            "cold_storm_lighting": {"verdict": "PASS", "evidence": "cold blue-grey key, heavy overcast"},
        },
        "IDENTITY": {
            "same_protagonist": {"verdict": "PASS_WITH_RECORDED_OBSERVATION",
                "evidence": "wardrobe chain continuous (white/light-grey robes, topknot, streaming headband, dark sash at waist); the locked sequence (F1R+F2) contains NO resolvable face, so this MCU ESTABLISHES the facial identity for the new sequence — no in-sequence contradiction exists. RECORDED: the facial rendering is a mature, hard-featured adult male (text-only identity cannot bind facial geometry — the QD-003 limitation); the headband reads lighter than F1R's distant dark ribbon. Flagged for the future face-reference work item; NOT averaged into a failure."},
            "same_wardrobe_look": {"verdict": "PASS", "evidence": "white robes + topknot + headband; sash below MCU frame (not contradicted)"},
            "no_unexplained_prop": {"verdict": "PASS", "evidence": "no weapon, no props in any of the 121 frames"},
        },
        "COMPOSITION": {
            "medium_close_framing": {"verdict": "PASS", "evidence": "face and shoulders, three-quarter profile"},
            "faces_frame_left": {"verdict": "PASS", "evidence": "faces and gazes frame-left in every frame"},
            "compatible_eyeline": {"verdict": "PASS", "evidence": "steady gaze down the road ahead (frame-left)"},
        },
        "PERFORMANCE": {
            "post_traversal_settling": {"verdict": "PASS", "evidence": "still, settled posture; robes settling; the traversal is over"},
            "calm_determination": {"verdict": "PASS", "evidence": "calm, composed expression; steady gaze"},
            "reflective_resolve": {"verdict": "PASS", "evidence": "the held beat reads: the cost, held"},
            "no_unintended_panic_aggression": {"verdict": "PASS", "evidence": "expression composed throughout"},
        },
    },
    "watermark": "Dola AI present (preserved verbatim)",
    "verdict": "F3R_012_ACCEPTED",
    "critical_failures": [],
})

# ---- F2 -> F3R cut QC -------------------------------------------------------
write("V2_012_F2_F3R_CUT_QC.json", {
    "version": "v2-012-f2-f3r-cut-qc-v1",
    "checkpoint": "V2012_F2_F3R_CUT_QC",
    "recorded_at": utcnow(),
    "junction": "locked F2 final frame (133) -> HARD CUT -> F3R_012 frame 0",
    "trim_search": {
        "authorization": "F3R IN ±12 frames only (F2 immutable)",
        "candidates_considered": [
            {"f3r_in": 0, "observation": "base junction: same-world cut-in, motion->settle reads immediately", "chosen": True},
            {"f3r_in": "1..12", "observation": "F3R_012 frames 0-12 are near-identical (the settle beat is already still) — no landing improves continuity; base kept honoring the frozen 3.208333s slot duration"},
        ],
        "chosen": "IN=0 (no trim); F3R selection = frames 0..76 (77 frames, 3.208333s — F3 slot parity)",
    },
    "dimensions": {
        "identity": {"verdict": "PASS", "evidence": "wardrobe chain continuous across the cut (see creative-QC recorded observation)"},
        "wardrobe": {"verdict": "PASS", "evidence": "white robes + topknot + headband both sides"},
        "world": {"verdict": "PASS", "evidence": "the 011C tan-built-wall failure is GONE — both sides are dark jagged natural rock"},
        "rock_material": {"verdict": "PASS", "evidence": "same rough natural stone family"},
        "lighting": {"verdict": "PASS", "evidence": "cold blue-grey storm light continuous"},
        "palette": {"verdict": "PASS", "evidence": "no warm/cold flip anywhere (luma 91.75 -> ~78.7, same cold family)"},
        "weather": {"verdict": "PASS", "evidence": "overcast + mist both sides"},
        "screen_direction": {"verdict": "PASS", "evidence": "frame-left travel -> frame-left profile"},
        "eyeline": {"verdict": "PASS", "evidence": "gaze down the road ahead (frame-left)"},
        "body_orientation": {"verdict": "PASS", "evidence": "upright settle after lean-into-wind traversal"},
        "motion_to_settle": {"verdict": "PASS", "evidence": "mid-motion -> still: the intended performance beat lands exactly"},
        "action_energy": {"verdict": "PASS", "evidence": "expenditure -> held resolve"},
        "character_scale": {"verdict": "PASS", "evidence": "WS -> MCU standard cut-in escalation"},
        "shot_size_rhythm": {"verdict": "PASS", "evidence": "EWS (F1R) -> WS/MWS (F2) -> MCU (F3R): classic progression"},
        "narrative_state": {"verdict": "PASS", "evidence": "crossed -> the cost, held"},
    },
    "verdict": "CUT_PASS",
})

# ---- sequence QC ------------------------------------------------------------
write("V2_012_SEQUENCE_QC.json", {
    "version": "v2-012-sequence-qc-v1",
    "checkpoint": "V2012_SEQUENCE_QC",
    "recorded_at": utcnow(),
    "passage": "ARRIVE (F1R) -> FORCE THROUGH (locked F2) -> COST HELD (F3R_012)",
    "dimensions": {
        "narrative_progression": {"verdict": "PASS", "evidence": "the three-beat arc reads clearly as one passage"},
        "world_continuity": {"verdict": "PASS", "evidence": "continuous cold storm-pass world; carried observation: F1R's establishing WS renders the ridge monumental vs F2's human-scale entry (recorded in 011D, unchanged)"},
        "lighting_continuity": {"verdict": "PASS", "evidence": "cold blue-grey throughout"},
        "weather_continuity": {"verdict": "PASS", "evidence": "overcast + wind + mist throughout"},
        "screen_direction": {"verdict": "PASS", "evidence": "frame-left throughout"},
        "motion_flow": {"verdict": "PASS", "evidence": "approach -> effort -> settle"},
        "identity": {"verdict": "PASS", "evidence": "wardrobe chain continuous; recorded observations carried from creative QC"},
        "wardrobe": {"verdict": "PASS", "evidence": "white robes + topknot + headband in all three units"},
        "performance": {"verdict": "PASS", "evidence": "lean-into-wind physicality -> crossing effort -> held resolve"},
        "camera_grammar": {"verdict": "PASS", "evidence": "locked camera, three distinct setups"},
        "shot_size_rhythm": {"verdict": "PASS", "evidence": "EWS -> WS -> MCU escalation"},
        "edit_rhythm": {"verdict": "PASS", "evidence": "4.79s / 5.58s / 3.21s — decelerating into the held beat"},
    },
    "technical": {"proof_sha256": proof_sha, "frames": 326,
                  "frame_count_exact": True, "decode_pass": True,
                  "timestamp_discontinuities": 0, "no_black": True,
                  "no_frozen": True, "fps": "24/1",
                  "duration_s": 13.583356},
    "audio": {
        "AUDIO_CONTEXT": "FINISHING_REPAIR_REQUIRED",
        "junction_1_step_db": 0.8,
        "junction_2_step_db": 8.0,
        "note": "J1 (F1R->F2) ambience is nearly seamless (0.8 dB vs the "
                "011C 7.2 dB); J2 (F2->F3R) drops 8.0 dB — ambience "
                "level-match at the finishing mix; NOT a regeneration cause",
    },
    "watermark": "Dola AI preserved on F3R_012 and F2; PRESERVE rule "
                 "unchanged; UNWATERMARKED_VARIANT = OBSERVED_NOT_AUTHORIZED",
    "verdict": "FULL_SEQUENCE_CONTEXT = PROVEN",
})

# ---- editorial ranges -------------------------------------------------------
write("V2_012_EDITORIAL_RANGES.json", {
    "version": "v2-012-editorial-ranges-v1",
    "fps_rule": "24 fps nearest-frame boundary resolution (011B/011C rule)",
    "F1R": {"asset_sha256": f1r_sha, "selected_frames": [0, 114],
            "frames": 115, "duration_s": 4.791667, "immutable": "011D authority"},
    "F2_LOCKED": {"asset_sha256": f2_sha, "frames": [0, 133], "count": 134,
                  "immutable": True},
    "F3R_012": {"asset_sha256": f3r_sha, "provider_frames": 121,
                "selected_frames": [0, 76], "frames_used": 77,
                "duration_s": 3.208333, "trim": "IN=0 (base kept; window 0..12 evaluated — no better landing)"},
    "assembly": {"junctions": {"f1r_f2": 115, "f2_f3r": 249},
                 "total_frames": 326, "total_duration_s": 13.583333},
})

# ---- mutation ledger + lineage ----------------------------------------------
write("V2_012_MUTATION_LEDGER.json", {
    "version": "v2-012-mutation-ledger-final-v1",
    "built_at": utcnow(),
    "authority": "F3R_012 = EXACTLY ONE (V2-012 package; 011D authority exhausted and NOT extended)",
    "mutations": {
        "F3R_012": "1/1 — RELEASED 14:59Z on ACCOUNT_D; SSE receipt "
                   "captured in-window; creation bound; asset acquired "
                   "b558f8e8…; creative QC ACCEPTED",
    },
    "max": 1,
    "no_retry": True,
    "no_provider_switch": True,
    "slots": {"slot_f3r_012": slot},
})

write("V2_012_PROVIDER_LINEAGE.json", {
    "version": "v2-012-provider-lineage-v1",
    "built_at": utcnow(),
    "account": "ACCOUNT_D (owner-manual native session, Khởi Đặng219)",
    "F3R_012": {
        "conversation_id": runner_ev.get("conversation_id"),
        "creation_ids": runner_ev.get("creation_ids"),
        "asset_sha256": f3r_sha,
        "duration_s": 5.088005,
        "model_statement": "Seedance 2.0",
        "credit_ack": "本日の残りは3動画クレジットです (dispatch-time ack; "
                      "prior-epoch evidence treated per package)",
        "release": "SSE receipt CAPTURED in-window (no latch this time)",
    },
    "policy_repair_record": {
        "prior_refusal": "011D F3R frozen prompt refused after billing",
        "exact_trigger": "UNKNOWN (not promoted)",
        "repair": "policy-compliant rephrase per the package (no "
                  "safety-evasion); the repaired prompt was accepted and "
                  "generated on the first dispatch",
        "honest_note": "the repaired prompt differing from the refused one "
                       "in BOTH wording and (nothing else) — same account "
                       "family, same session, same model: the acceptance is "
                       "consistent with a wording-class trigger but does NOT "
                       "prove which token; trigger remains UNKNOWN",
    },
})

# ---- candidate seal ----------------------------------------------------------
write("V2_012_CANDIDATE_SEAL.json", {
    "version": "v2-012-candidate-seal-v1",
    "sealed_at": utcnow(),
    "checkpoint": "V2012_SEAL",
    "status": "COMPLETED_CANDIDATE",
    "canonical": {
        "F1R": "ACCEPTED (011D)",
        "F1R_F2_CUT": "PASS (011D)",
        "F2_SEQUENCE": "FILM_USABLE (all locks; sha re-verified unchanged)",
        "F3R_012": "ACCEPTED (this slice — policy-compliant repair)",
        "F2_F3R_CUT": "PASS (CUT_PASS, no trim needed)",
        "FULL_SEQUENCE_CONTEXT": "PROVEN",
        "SEQ_CONTEXT_LOCK": "GRANTED",
        "SEQ7_F1_F2_F3": "FILM_USABLE",
    },
    "proof": {
        "path": "outputs/F1R_F2_F3R_SEQUENCE_PROOF.mp4",
        "sha256": proof_sha,
        "frames": 326, "duration_s": 13.583333, "fps": 24,
        "structure": "F1R(0..114) HARD CUT LOCKED F2(134 verbatim) HARD CUT F3R_012(0..76)",
    },
    "checks": {
        "prompt_audit_trigger_unknown": True,
        "repair_no_safety_evasion": True,
        "prerender_gates_pass": True,
        "exactly_one_mutation": True,
        "receipt_captured_in_window": True,
        "creative_qc_accepted": True,
        "cut_qc_pass": True,
        "assembly_frame_exact": True,
        "sequence_qc_pass": True,
        "f2_untouched": True,
        "f1r_untouched": True,
        "watermark_preserved": True,
        "secret_audit_clean": True,
        "audio_finishing_debt_recorded": True,
    },
    "mutations_used": "1/1",
    "next_handoff": "SEQ_CONTEXT_LOCK = GRANTED → STOP. Return to Tech Lead. "
                    "Do NOT begin finishing. Next planned slice: V2-011W "
                    "(Dola Unwatermarked Asset Authority Qualification; "
                    "read-only, zero video-generation mutations unless "
                    "separately authorized).",
})

print("V2-012 evidence complete")
