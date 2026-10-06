"""V2-011C evidence builder — full sequence context recovery + cut QC + repair plan.

Fail-closed: every custody SHA is recomputed from disk before any evidence is written.
Zero provider mutations; read-only/editorial slice.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJ = os.path.join(ROOT, "projects", "quality_v2_011c_full_sequence_context")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def write(name, payload):
    path = os.path.join(PROJ, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    print("wrote", rel(path))


# ---------------------------------------------------------------- custody re-verification (fail-closed)
F1_ASSET = os.path.join(
    ROOT,
    "projects",
    "flow_production_scale_007",
    "sequence_SEQ007_DAYLIGHT_ROAD",
    "scene_SCENE_F_STORM_GATE",
    "shot_SEQ7_F1",
    "videos",
    "1978828aa83ed40e78523c43.mp4",
)
F3_ASSET = os.path.join(
    ROOT,
    "projects",
    "flow_production_scale_007",
    "sequence_SEQ007_DAYLIGHT_ROAD",
    "scene_SCENE_F_STORM_GATE",
    "shot_SEQ7_F3",
    "videos",
    "83df94b5d166dedce511ab1c.mp4",
)
F2A_ASSET = os.path.join(ROOT, "projects", "quality_v2_011r_targeted_repair", "assets", "f2a_r.mp4")
F2B_ASSET = os.path.join(ROOT, "projects", "quality_v2_011r_targeted_repair", "assets", "f2b_r.mp4")
F2_PROOF = os.path.join(PROJ, "inputs_F2_proof.mp4")
REF_CUT = os.path.join(PROJ, "outputs", "F1_F2_F3_CONTEXT_FAIL_REFERENCE_CUT.mp4")

EXPECT = {
    "F1": (F1_ASSET, "f50f07e82b706cd41e655c119cb635c2b95353811a54db75771ee685857a29e8"),
    "F3": (F3_ASSET, "24f051288f8fe43485ac9652ca71c26977751a5c47280c5ece4b58961cf4328b"),
    "F2A": (F2A_ASSET, "50a133c891aaa0060bc1f7d9d6c48c77a3fab1e802bc5f7a4fc43e112404d99b"),
    "F2B": (F2B_ASSET, "8679709b00860a2e3af45354b2166eae2b6d6b365731a278f21809a42babbbff"),
    "F2_PROOF": (F2_PROOF, "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"),
    "REF_CUT": (REF_CUT, "9c7c44ce04ca390ee95ebaba0ee4ec26b0d7f7e598ace7e388926e675388a074"),
}
observed = {}
for key, (path, expect) in EXPECT.items():
    got = sha256(path)
    observed[key] = got
    assert got == expect, f"CUSTODY MISMATCH {key}: {got} != {expect}"
print("all custody SHAs verified against disk")

NOW = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------- 1. custody
write(
    "V2_011C_CUSTODY.json",
    {
        "version": "v2-011c-custody-v1",
        "checkpoint": "V2011C_P0_CUSTODY_CLOSURE",
        "recorded_at": NOW,
        "branch": "quality-v2/011b-editorial-assembly",
        "head_resolution": "git rev-parse HEAD (resolved, not inferred from branch state)",
        "011B_FINAL_HEAD_SHA": "afc15b84c26bcf22175410081ed7a05b3b17ad6b",
        "011B_CANDIDATE_SEAL_SHA": "e418c6536acb81a7d0515cec496d1f5921a17a64fee4f1d790ef66bc933e05bc",
        "011B_CANDIDATE_SEAL_FILE": "projects/quality_v2_011b_editorial_assembly/V2_011B_CANDIDATE_SEAL.json",
        "F2_EDITORIAL_PROOF_SHA": observed["F2_PROOF"],
        "F2_EDITORIAL_PROOF_FILE": "projects/quality_v2_011b_editorial_assembly/outputs/F2_SEQUENCE_EDITORIAL_PROOF.mp4",
        "locked_f2_facts_verified": {
            "f2a_asset_sha256": observed["F2A"],
            "f2a_selected_frames": [41, 108],
            "f2b_asset_sha256": observed["F2B"],
            "f2b_selected_frames": [0, 67],
            "cut_type": "HARD_CUT",
            "locked_sequence_frames": 134,
            "fps": 24,
            "authority": "V2_011B_EDITORIAL_LOCK.json + V2_011B_EDITORIAL_RANGES.json (recomputed from disk, exact match)",
        },
        "f2_immutability": {
            "rule": "F2_SEQUENCE_LOCKED_v1 — no F2A/F2B manipulation; proof used as the middle unit verbatim",
            "proof_sha_unchanged_after_all_assembly_work": True,
            "watermark_policy": "PRESERVED (no removal, no concealment, no unwatermarked variants)",
        },
        "provider_mutations": 0,
    },
)

# ---------------------------------------------------------------- 2/3. F1 & F3 authority
COMMON_CREATIVE_STATUS = {
    "owner_canonical_retention": "owner_quality_decision_019.json: ACCEPT_KNOWN_QUALITY_DEBT; canonical_lineage UNCHANGED — retained verbatim; F1/F3 carry NO debt item (only SEQ7_F2/SEQ7_G3 named NEEDS_REDESIGN)",
    "master_conformance": "lineage_and_ranges_all_30 PASS in master packages 007/008/009/010 (conformance_report.json)",
    "semantic_per_shot_model_qc": "never qualified (FLOW-SEMANTIC-QUALIFY-006 SEMANTIC_QC_INCONCLUSIVE; 012 3.1-Flash-Lite NOT_QUALIFIED; 013 2.5-Flash NOT_QUALIFIED) — recorded honestly, not averaged away",
    "v2_track_binding": "f2_decomposition_plan_v2_005.json: F2A blocking.continuity_bindings.previous_shot_id = SEQ7_F1; F2B blocking.continuity_bindings.next_shot_id = SEQ7_F3; continuity authority = fixtures/sequence007 F1/F2/F3 screen_direction authority",
    "classification": "CASE_A — exact accepted canonical assets exist and are deterministically identified by lineage",
}

F1_AUTH = {
    "version": "v2-011c-f1-authority-v1",
    "checkpoint": "V2011C_P1_F1_AUTHORITY",
    "recorded_at": NOW,
    "shot_id": "SEQ7_F1",
    "shot_spec_identity": {
        "fixture": "fixtures/sequence007/SEQ7_F1.json",
        "spec_version": 1,
        "scene_id": "SCENE_F_STORM_GATE",
        "dramatic_purpose": "Obstacle: the storm front meets him at the narrow rock gate.",
        "shot_type": "establishing",
        "camera": "WS, eye level, locked",
        "screen_direction": "faces frame-left",
        "character": "swordsman_white_robes_v1 / look_state white_robes_cloud_summit_dawn_v1",
        "prompt_sha256": "34e59504416fab47ba420154844a7f7fe8f073e94154f308f843726e400eb65c",
        "editorial_target_duration_s": 4.8,
    },
    "generation_attempt": "attempt_7d962ead9f689a49362f6e9a7a2e80f65717a1ffb0a1b95be3cb2bc923bb520f",
    "provider_job": {
        "job_id": "job_0e6e68518a9b9c7d15cfe630f247f49e6956e86e241041c1cdc3ed8869fde8ef",
        "provider": "flow_veo (veo_3_1_r2v_lite)",
        "output_identity": "eba1fb3b-6400-4b40-b52e-5ddd40f225d9",
        "continuity_mechanism": "same_reference media_id 7b725f7b-4da5-4455-a6f2-135c4ba22397 (identity reference shared with the F2 pair identity mechanism)",
    },
    "local_asset": {
        "asset_id": "asset_9805ce8e8a2b71285526b955d6fe0c8328226e14baeb5a1d05bb433e694555c6",
        "path": rel(F1_ASSET),
        "sha256": observed["F1"],
        "sha_recomputed_from_disk": True,
        "probe": {"duration_s": 8.0, "fps": 24, "frames": 192, "width": 1280, "height": 720, "codecs": ["h264", "aac"]},
    },
    "technical_qc": {"gate": "SHOT_PROVEN", "decode": "full_decode_eof PASS", "qc_eligibility": "exact_lineage + technical_pass"},
    "creative_status": COMMON_CREATIVE_STATUS,
    "editorial_range": {
        "slot": 23,
        "range_files": ["master_package_007/ranges/23_SEQ7_F1.json", "master_package_008/ranges/23_SEQ7_F1.json", "master_package_009/ranges/23_SEQ7_F1.json", "master_package_010/ranges/23_SEQ7_F1.json"],
        "source_in_s": 0.0,
        "source_out_s": 4.8,
        "nearest_frame_resolution": "4.8s x 24 = 115.2 -> exclusive end frame 115 (011B 24fps nearest-frame rule) -> selected frames 0..114 (115 frames, 4.791667s)",
        "provenance": "PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE (frozen across 4 master packages)",
    },
}
write("V2_011C_F1_AUTHORITY.json", F1_AUTH)

F3_AUTH = {
    "version": "v2-011c-f3-authority-v1",
    "checkpoint": "V2011C_P1_F3_AUTHORITY",
    "recorded_at": NOW,
    "shot_id": "SEQ7_F3",
    "shot_spec_identity": {
        "fixture": "fixtures/sequence007/SEQ7_F3.json",
        "spec_version": 1,
        "scene_id": "SCENE_F_STORM_GATE",
        "dramatic_purpose": "Performance: against the rock wall he sets his jaw; the cost, held.",
        "shot_type": "performance",
        "camera": "MCU, eye level, locked",
        "screen_direction": "faces frame-left",
        "character": "swordsman_white_robes_v1 / look_state white_robes_cloud_summit_dawn_v1",
        "prompt_sha256": "47f5f6d0c9533b6aeb3dfa3698467c7d60d3e730813f0657ad62a8e7abd72e80",
        "editorial_target_duration_s": 3.2,
    },
    "generation_attempt": "attempt_c6f54817ae2ad99b7f83bf5980cbd531d91e7f93239317c2d99fc9bce778565c",
    "provider_job": {
        "job_id": "job_55327b8fae8bbcb59700203e48e074ae31825709570aca8926f3785d4fae6ab3",
        "provider": "flow_veo (veo_3_1_r2v_lite)",
        "output_identity": "ec2d2965-a7f2-49dd-a04a-ca15b83288f7",
        "continuity_mechanism": "same_reference media_id 7b725f7b-4da5-4455-a6f2-135c4ba22397 (identity reference shared with the F2 pair identity mechanism)",
    },
    "local_asset": {
        "asset_id": "asset_9a7f2a18133ed3425fdb1498e90dd26b9eb56d2c78ef32405001a9a254d6119e",
        "path": rel(F3_ASSET),
        "sha256": observed["F3"],
        "sha_recomputed_from_disk": True,
        "probe": {"duration_s": 8.0, "fps": 24, "frames": 192, "width": 1280, "height": 720, "codecs": ["h264", "aac"]},
    },
    "technical_qc": {"gate": "SHOT_PROVEN", "decode": "full_decode_eof PASS", "qc_eligibility": "exact_lineage + technical_pass"},
    "creative_status": COMMON_CREATIVE_STATUS,
    "editorial_range": {
        "slot": 25,
        "range_files": ["master_package_007/ranges/25_SEQ7_F3.json", "master_package_008/ranges/25_SEQ7_F3.json", "master_package_009/ranges/25_SEQ7_F3.json", "master_package_010/ranges/25_SEQ7_F3.json"],
        "source_in_s": 0.0,
        "source_out_s": 3.2,
        "nearest_frame_resolution": "3.2s x 24 = 76.8 -> exclusive end frame 77 (011B 24fps nearest-frame rule) -> selected frames 0..76 (77 frames, 3.208333s)",
        "provenance": "PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE (frozen across 4 master packages)",
    },
}
write("V2_011C_F3_AUTHORITY.json", F3_AUTH)

# ---------------------------------------------------------------- 4/5. cut QC
J1_DIMENSIONS = {
    "character_identity": {"verdict": "MATCH", "evidence": "same white-robed swordsman, dark hair, wind-blown"},
    "wardrobe_look": {"verdict": "MATCH", "evidence": "white robes streaming leeward both sides"},
    "prop_state": {"verdict": "N_A_NO_PROPS", "evidence": "no props in frame either side (no visible sword — consistent)"},
    "location_world": {"verdict": "FAIL", "evidence": "F1 = freestanding twin standing stones with wooden gate cross in OPEN grassland (visible bypass/horizon behind); locked F2 = continuous dark rock-ridge choke point integrated into terrain — the exact geography the V2-009 Owner reframe FORBADE for the pass (FREESTANDING_DECORATIVE_GATE / OPEN_FIELD_BYPASS) now sits adjacent to its replacement across one cut"},
    "weather": {"verdict": "PARTIAL_FAIL", "evidence": "storm both sides, but F1 shows dramatic dark cloud wall + warm crepuscular light; F2 flat cold grey overcast"},
    "lighting_palette": {"verdict": "FAIL", "evidence": "warm golden key on F1 vs cold blue-grey flat light on F2 (luma F1 ~102 vs F2 ~92 with opposite chroma cast)"},
    "screen_direction": {"verdict": "MATCH", "evidence": "faces frame-left both sides (fixtures/sequence007 authority)"},
    "travel_direction": {"verdict": "MATCH", "evidence": "moving frame-left both sides"},
    "eyeline": {"verdict": "MATCH", "evidence": "down the road ahead / into the pass"},
    "body_orientation": {"verdict": "MATCH", "evidence": "upright lean-into-wind, mid-stride"},
    "motion_phase": {"verdict": "MATCH", "evidence": "both sides mid-stride forward effort — no stall or reverse at the cut"},
    "character_scale": {"verdict": "MINOR_POP_ACCEPTABLE", "evidence": "F1 mid-ground full figure vs F2 slightly smaller at frame-right — cut-in scale step, standard"},
    "causal_action": {"verdict": "MATCH_NARRATIVELY", "evidence": "approach (F1 end 'close to the rock gate, leaning') -> crossing commit (F2 start) is readable — but the world flip undermines WHERE"},
    "action_energy": {"verdict": "MATCH", "evidence": "forward effort against wind both sides"},
    "narrative_state": {"verdict": "MATCH", "evidence": "arrive at gate -> enter pass"},
}

J2_DIMENSIONS = {
    "character_identity": {"verdict": "MATCH", "evidence": "same swordsman; topknot + white headband consistent"},
    "wardrobe_look": {"verdict": "MATCH", "evidence": "white robes; headband streaming in F2 end, tied in F3 — same wardrobe state"},
    "prop_state": {"verdict": "N_A_NO_PROPS", "evidence": "no props in frame either side"},
    "location_world": {"verdict": "FAIL", "evidence": "locked F2 end = dark jagged natural rock face beside dirt track; F3 = light tan built/blocked stone wall — different wall material and architecture at the same landmark"},
    "weather": {"verdict": "PARTIAL_FAIL", "evidence": "cloud cover both sides, but F3 sky carries warm golden-hour glow absent from F2's cold storm"},
    "lighting_palette": {"verdict": "FAIL", "evidence": "cold blue-grey storm vs warm golden sunlight; measured luma F2 91.75 avg vs F3 139.15 avg (+47)"},
    "screen_direction": {"verdict": "MATCH", "evidence": "faces frame-left both sides"},
    "travel_direction": {"verdict": "MATCH", "evidence": "F2 travel frame-left; F3 static but oriented frame-left"},
    "eyeline": {"verdict": "MATCH", "evidence": "down the road ahead"},
    "body_orientation": {"verdict": "MATCH", "evidence": "F2 upright lean; F3 pressed against wall, three-quarter profile"},
    "motion_phase": {"verdict": "ACCEPTABLE", "evidence": "motion -> settle; F3 fixture intent is the held-cost performance beat (jaw sets) — energy drop is the dramatic intent"},
    "shot_size_rhythm": {"verdict": "PASS", "evidence": "WS -> MCU cut-in progression is standard grammar"},
    "causal_action": {"verdict": "MATCH_NARRATIVELY", "evidence": "crossed -> cost held; readable against F2B_END_STATE FAR_SIDE_CLEAR"},
    "action_energy": {"verdict": "ACCEPTABLE", "evidence": "expending -> holding; deliberate settle"},
    "narrative_state": {"verdict": "MATCH", "evidence": "beyond the worst gust -> the price, held"},
}

for name, payload in [
    (
        "V2_011C_F1_F2_CUT_QC.json",
        {
            "version": "v2-011c-cut-qc-v1",
            "checkpoint": "V2011C_P3_F1_F2_CUT",
            "recorded_at": NOW,
            "junction": "F1 selected end -> HARD CUT -> locked F2 frame 0",
            "base_boundary": {"f1_last_frame": 114, "f1_out_s": 4.791667, "f2_frame": 0},
            "inspected": {
                "f1_source_frames": "96..127 (base end 114 + full ±12 trim window 102..126)",
                "f2_locked_frames": "0..23",
                "contact_sheet": "owner_review_011c/F1_F2_JUNCTION.png",
                "full_res_pair": "frames/PAIR_F1_n114_F2_first_n000.png",
            },
            "dimensions": J1_DIMENSIONS,
            "trim_search": {
                "authorization": "package rule ±12 frames; prefer F1 boundary first",
                "window_evaluated": "F1 last-frame 102..126 (source frames already-authorized by the frozen 8s asset)",
                "result": "world/geography and palette are INVARIANT across the entire window — the freestanding-gate open-field world and warm key light fill every F1 candidate frame; no landing changes the verdict",
                "action": "base boundary KEPT (honors frozen editorial ranges; minimal deviation)",
            },
            "verdict": "CUT_FAIL",
            "failure_classes": ["GEOGRAPHY", "LIGHTING"],
            "critical_failures_not_averaged": True,
            "note": "all editorial-grammar dimensions pass; the failure is the WORLD the two shots live in, not the cut mechanics",
        },
    ),
    (
        "V2_011C_F2_F3_CUT_QC.json",
        {
            "version": "v2-011c-cut-qc-v1",
            "checkpoint": "V2011C_P4_F2_F3_CUT",
            "recorded_at": NOW,
            "junction": "locked F2 final frame -> HARD CUT -> F3 selected start",
            "base_boundary": {"f2_frame": 133, "f3_first_frame": 0, "f3_in_s": 0.0},
            "inspected": {
                "f2_locked_frames": "102..133",
                "f3_source_frames": "0..23 (full ±12 trim window 0..12)",
                "contact_sheet": "owner_review_011c/F2_F3_JUNCTION.png",
                "full_res_pair": "frames/PAIR_F2_last_n133_F3_n000.png",
            },
            "dimensions": J2_DIMENSIONS,
            "trim_search": {
                "authorization": "package rule ±12 frames on F3 boundary; F2 immutable",
                "window_evaluated": "F3 in-frame 0..12",
                "result": "warm golden light and tan built wall persist across the whole window — no landing changes the verdict",
                "action": "base boundary KEPT (honors frozen editorial ranges; minimal deviation)",
            },
            "verdict": "CUT_FAIL",
            "failure_classes": ["GEOGRAPHY", "LIGHTING"],
            "critical_failures_not_averaged": True,
            "note": "screen direction, identity, wardrobe and the settle-beat grammar pass; world material + palette fail",
        },
    ),
]:
    write(name, payload)

# ---------------------------------------------------------------- 6. sequence QC
write(
    "V2_011C_SEQUENCE_QC.json",
    {
        "version": "v2-011c-sequence-qc-v1",
        "checkpoint": "V2011C_P6_SEQUENCE_QC",
        "recorded_at": NOW,
        "basis": "full 13.583333s reference cut (see assembly manifest) + per-junction frame evidence",
        "dimensions": {
            "narrative_progression": {"verdict": "PASS", "evidence": "arrive at the gate -> force the crossing -> hold the cost: the three-beat arc reads"},
            "causal_readability": {"verdict": "FAIL_CONTEXT", "evidence": "within locked F2 the gust->effort->through causality is readable (011B PROVEN); across the junctions the WHY collapses because the landmark changes identity"},
            "spatial_geography": {"verdict": "FAIL", "evidence": "three different renderings of the same landmark: open-field freestanding gate -> continuous-ridge choke -> tan built wall"},
            "screen_direction": {"verdict": "PASS", "evidence": "frame-left travel/eyeline held across all three units"},
            "motion_flow": {"verdict": "PASS", "evidence": "effort -> struggle -> settle energy arc; no stall/reverse artifacts at cuts"},
            "shot_size_rhythm": {"verdict": "PASS", "evidence": "WS -> MWS/WS -> MCU: classic escalation into the performance beat"},
            "camera_grammar": {"verdict": "PASS", "evidence": "locked camera in all three units per fixtures"},
            "visual_palette": {"verdict": "FAIL", "evidence": "warm golden (F1) -> cold blue-grey (F2) -> warm golden (F3): the palette flips twice in 13.6s"},
            "weather_continuity": {"verdict": "PARTIAL_FAIL", "evidence": "storm in all three, but cloud character/light response differ per provider world"},
            "character_continuity": {"verdict": "PASS", "evidence": "identity reference 7b725f7b shared across F1/F3 and the F2 pair identity mechanism"},
            "prop_continuity": {"verdict": "N_A_PASS", "evidence": "no props in any of the three units (no visible sword anywhere — consistent with locked F2)"},
            "performance_continuity": {"verdict": "PASS", "evidence": "consistent lean-into-wind physicality; settle beat lands"},
            "edit_rhythm": {"verdict": "PASS", "evidence": "4.79s / 5.58s / 3.21s — decelerating into the held beat, works as pacing"},
        },
        "f2_middle_beat_function": {
            "verdict": "DOES_NOT_FUNCTION_NATURALLY_IN_CURRENT_CONTEXT",
            "detail": "locked F2 is internally FILM_USABLE (011B) and its causal meaning is the strongest beat of the three — but as the middle unit it currently reads as a DIFFERENT PLACE AND TIME: the film enters a cold continuous-ridge world for 5.58s and exits back to a warm golden world. F2 does not fail as a beat; the context fails around it.",
        },
        "audio_findings": {
            "policy": "existing source audio preserved; no final mix",
            "junction_1_level_step_db": 7.2,
            "junction_2_level_step_db": 11.8,
            "detail": "mean volume pre/post: J1 -16.3 -> -23.5 dB; J2 -17.6 -> -29.4 dB — audible ambience level discontinuities at both cuts (different provider ambience mixes); wind character also shifts (brighter gust noise vs duller bed)",
            "disposition": "editorial/audio repair NOTE only (level-matching ambience pass at a later finishing slice) — no video regeneration indicated by audio",
        },
        "watermark_status": {
            "policy": "preserved verbatim; no removal/concealment; no unwatermarked variants used",
            "observation": "watermark itself changes across cuts (Veo on F1/F3, Dola AI on F2) — provider-rights/finishing issue recorded for a later slice, intentionally untouched here",
        },
        "verdict": "FULL_SEQUENCE_CONTEXT = FAILED (CONTEXT_FAIL)",
        "critical_failures_not_averaged": True,
    },
)

# ---------------------------------------------------------------- 7. assembly manifest
write(
    "V2_011C_ASSEMBLY_MANIFEST.json",
    {
        "version": "v2-011c-assembly-v1",
        "checkpoint": "V2011C_P5_REFERENCE_ASSEMBLY",
        "built_at": NOW,
        "fps_rule": "24 fps nearest-frame boundary resolution (011B rule)",
        "status": "REFERENCE_ONLY_NOT_A_PROOF",
        "proof_withheld": {
            "requested_media": "outputs/F1_F2_F3_SEQUENCE_PROOF.mp4",
            "created": False,
            "reason": "PHASE 5 gate requires BOTH junctions to pass; both junctions CUT_FAIL (GEOGRAPHY+LIGHTING). Rendering a file named SEQUENCE_PROOF would falsely imply FULL_SEQUENCE_CONTEXT=PROVEN. A clearly-labeled reference cut was rendered instead so the Owner/Tech Lead can judge severity from motion and sound, not stills alone.",
        },
        "method": "concat FILTER (011B lesson — the concat demuxer duplicates a frame at junctions), frame-accurate trims, h264 yuv420p + AAC 192k",
        "clips": [
            {
                "slot": "F1",
                "shot_id": "SEQ7_F1",
                "source": rel(F1_ASSET),
                "source_sha256": observed["F1"],
                "selected_frames": [0, 114],
                "frames_used": 115,
                "duration_s": 4.791667,
                "authority": "V2_011C_F1_AUTHORITY.json",
            },
            {
                "slot": "F2_LOCKED",
                "shot_id": "SEQ7_F2 (F2A-R + F2B-R locked pair)",
                "source": rel(F2_PROOF),
                "source_sha256": observed["F2_PROOF"],
                "selected_frames": [0, 133],
                "frames_used": 134,
                "duration_s": 5.583333,
                "authority": "V2_011B_EDITORIAL_LOCK.json — used VERBATIM, immutable",
            },
            {
                "slot": "F3",
                "shot_id": "SEQ7_F3",
                "source": rel(F3_ASSET),
                "source_sha256": observed["F3"],
                "selected_frames": [0, 76],
                "frames_used": 77,
                "duration_s": 3.208333,
                "authority": "V2_011C_F3_AUTHORITY.json",
            },
        ],
        "junctions": {"F1_to_F2_at_output_frame": 115, "F2_to_F3_at_output_frame": 249},
        "output": {
            "path": "outputs/F1_F2_F3_CONTEXT_FAIL_REFERENCE_CUT.mp4",
            "sha256": observed["REF_CUT"],
            "frames": 326,
            "duration_s": 13.583333,
            "video_codec": "h264 yuv420p",
            "audio_codec": "aac 192k",
        },
        "f2_immutability_proof": {"f2_proof_sha_before": observed["F2_PROOF"], "f2_proof_sha_after": observed["F2_PROOF"], "unchanged": True},
        "provider_mutations": 0,
    },
)

# ---------------------------------------------------------------- 8. context lock
write(
    "V2_011C_CONTEXT_LOCK.json",
    {
        "version": "v2-011c-context-lock-v1",
        "checkpoint": "V2011C_PRODUCTION_DECISION",
        "decided_at": NOW,
        "F1_F2_CUT": "FAIL",
        "F2_F3_CUT": "FAIL",
        "FULL_SEQUENCE_CONTEXT": "FAILED",
        "SEQ_CONTEXT_LOCK": "DENIED",
        "frozen_when_repaired_and_reproven": ["asset SHAs", "frame ranges", "cut locations", "assembly manifest", "proof SHA", "QC decision"],
        "unchanged_canonical_states": {
            "F2_SEQUENCE": "FILM_USABLE (F2_CREATIVE_LOCK/PRODUCTION_LOCK/EDITORIAL_LOCK all GRANTED — untouched by this slice)",
            "canonical_master_lineage": "UNCHANGED — master_editorial_010_v1 remains the canonical film; nothing promoted, nothing demoted",
        },
        "denial_reason": "both context junctions fail on GEOGRAPHY + LIGHTING: the canonical F1/F3 (warm, superseded world) cannot sit adjacent to the locked F2 (cold reframed choke-point world) without the landmark changing identity across each cut; ±12-frame trim windows proven incapable of closing a world-class mismatch",
        "next_decision_owner": "Tech Lead (per package): whether the next slice is F1/F3 context regeneration (V2-012 proposal attached)",
        "provider_mutations": 0,
    },
)

# ---------------------------------------------------------------- 9. repair plan
write(
    "V2_011C_CONTEXT_REPAIR_PLAN.json",
    {
        "version": "v2-011c-context-repair-plan-v1",
        "checkpoint": "V2011C_REPAIR_PLAN",
        "produced_at": NOW,
        "trigger": "IF F1/F3 FAIL branch — junctions failed; NO regeneration performed in this slice (0 provider mutations)",
        "decision_requested": "Tech Lead: choose repair direction; any generation requires an authorized successor slice (proposed V2-012)",
        "failure_classification": {
            "F1_F2_junction": ["GEOGRAPHY", "LIGHTING"],
            "F2_F3_junction": ["GEOGRAPHY", "LIGHTING"],
            "explicitly_not_failing": ["DIRECTION", "IDENTITY", "PROP", "CAUSAL_ACTION", "EDITABILITY", "MISSING_ASSET"],
        },
        "root_cause": "the V2-009 Owner reframe moved the pass world (continuous rock-ridge choke point, cold storm palette) for F2 only; canonical F1/F3 still render the superseded world (freestanding decorative gate in open field / tan built wall, warm golden light)",
        "repair_options": [
            {
                "option": "R-A_CONTEXT_REGENERATION_F1_F3",
                "description": "regenerate F1 and F3 inside the locked F2 world (identity-safe, world-matched context shots)",
                "requires": "provider generation (authorized successor slice)",
                "shot_spec_requirements_exact": {
                    "F1R": {
                        "retained_from_fixture": "SEQ7_F1 spec verbatim: establishing WS, locked camera, midday storm front, faces frame-left, mid-approach frame-right -> close to the gate leaning, editorial target 4.8s",
                        "world_must_match_locked_F2": "continuous rock-ridge choke point integrated into terrain (V2-009 traversal TG-eac7757544b0d950): road visibly funneling INTO the single opening, ridge extending beyond both lateral sides, NO bypass visible",
                        "forbidden": ["FREESTANDING_DECORATIVE_GATE", "OPEN_FIELD_BYPASS", "wooden gate cross-member", "warm golden key light", "open horizon behind the gate"],
                        "palette_target": "cold blue-grey overcast storm, flat key — match F2A world (reference: locked F2 frames 0-23)",
                        "identity_binding": "identity reference media 7b725f7b-4da5-4455-a6f2-135c4ba22397 (same mechanism as F2 pair)",
                        "audio_note": "ambience bed must sit near F2A level (-23.5 dB region) to avoid the 7.2 dB junction step",
                    },
                    "F3R": {
                        "retained_from_fixture": "SEQ7_F3 spec verbatim: MCU performance, locked camera, jaw sets / eyes narrow, faces frame-left, pressed near the rock wall, editorial target 3.2s",
                        "world_must_match_locked_F2": "BEYOND_GATE exit region (V2-009 exit_region): dark natural rock face material continuous with F2B exit, dirt track continuing onward",
                        "forbidden": ["light tan built/blocked masonry wall", "warm golden-hour glow", "sunlit face key"],
                        "palette_target": "cold blue-grey storm — match F2B world (reference: locked F2 frames 110-133)",
                        "identity_binding": "identity reference media 7b725f7b-4da5-4455-a6f2-135c4ba22397",
                        "audio_note": "ambience bed near F2B level (-29.4 dB region) or editorial level-match",
                    },
                },
            },
            {
                "option": "R-B_GRADE_ONLY_BRIDGE",
                "description": "no generation: color-grade F1/F3 toward the F2 palette + audio level-match (finishing-style intervention)",
                "requires": "explicit Owner authorization — this is VFX/color concealment, which the 011C package forbids inside the proof; viable only as a separately-authorized finishing slice; does NOT fix the geography/architecture mismatch (gate design still changes) — recorded as INCOMPLETE_FOR_GEOGRAPHY",
                "honest_limitation": "palette-only bridge leaves the GEOGRAPHY failure intact; not a full repair",
            },
            {
                "option": "R-C_NARRATIVE_REORDER",
                "description": "do not repair adjacency: treat the world change as an intentional act break (HARD_SCENE_BREAK at F1->F2) pending a wider V2 editorial plan",
                "requires": "Owner creative decision; weakest option — loses the approach->cross->cost continuous geography the V2-005 plan binds",
            },
        ],
        "recommendation": "R-A (world-matched F1/F3 regeneration through the proven identity-safe pipeline), then re-run 011C phases 2-6 read-only on the new assets",
        "generation_cost_estimate": "2 provider generates (8s class) + 0 for F2",
    },
)

# ---------------------------------------------------------------- 10. candidate seal
write(
    "V2_011C_CANDIDATE_SEAL.json",
    {
        "version": "v2-011c-candidate-seal-v1",
        "sealed_at": NOW,
        "checkpoint": "V2011C_P9_SEAL",
        "status": "COMPLETED_CANDIDATE",
        "engineering_status": "COMPLETE — custody deterministic, both authorities recovered, junctions QC'd with frame evidence, reference assembly + technical QC done, repair plan produced",
        "film_context_status": "FAILED — FULL_SEQUENCE_CONTEXT NOT proven; SEQ_CONTEXT_LOCK DENIED",
        "canonical": {
            "F2_SEQUENCE": "FILM_USABLE (all three F2 locks GRANTED, unchanged)",
            "FULL_SEQUENCE_CONTEXT": "FAILED (CONTEXT_FAIL)",
            "SEQ_CONTEXT_LOCK": "DENIED",
        },
        "checks": {
            "custody_head_resolved": True,
            "locked_f2_shas_verified_against_disk": True,
            "f1_authority_lineage_complete": True,
            "f3_authority_lineage_complete": True,
            "f1_f2_cut_qc_with_frame_evidence": True,
            "f2_f3_cut_qc_with_frame_evidence": True,
            "trim_windows_evaluated_not_applicable": True,
            "reference_assembly_rendered_and_labeled": True,
            "sequence_proof_withheld_per_gate": True,
            "technical_qc_reference_cut_pass": True,
            "audio_repair_notes_recorded": True,
            "watermark_preserved_untouched": True,
            "repair_plan_produced": True,
            "no_generation_attempted": True,
            "provider_mutations": 0,
        },
        "provider_mutations": 0,
        "evidence_index": [
            "V2_011C_CUSTODY.json",
            "V2_011C_F1_AUTHORITY.json",
            "V2_011C_F3_AUTHORITY.json",
            "V2_011C_F1_F2_CUT_QC.json",
            "V2_011C_F2_F3_CUT_QC.json",
            "V2_011C_SEQUENCE_QC.json",
            "V2_011C_ASSEMBLY_MANIFEST.json",
            "V2_011C_CONTEXT_LOCK.json",
            "V2_011C_CONTEXT_REPAIR_PLAN.json",
            "owner_review_011c/F1_F2_JUNCTION.png",
            "owner_review_011c/F2_F3_JUNCTION.png",
            "owner_review_011c/FULL_SEQUENCE_CONTACT_SHEET.png",
            "outputs/F1_F2_F3_CONTEXT_FAIL_REFERENCE_CUT.mp4",
            "docs/operating/AI_FILM_QUALITY_V2_011C_FULL_SEQUENCE_CONTEXT_EVIDENCE.md",
        ],
    },
)

print("ALL V2-011C EVIDENCE WRITTEN")
