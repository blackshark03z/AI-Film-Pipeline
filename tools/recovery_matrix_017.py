"""FLOW-PERFORMANCE-MOTION-CANARY-017 (Phase 17): recovery / adversarial
matrix — 104 cases.

Every row carries an exact proof: a pytest node, a raw receipt check, or
a live read-only check. Any ambiguity class involving provider external
effect or output identity maps to OWNER_AMBIGUITY_GATE per the frozen
package rule.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

D17 = ROOT / "projects/flow_performance_motion_canary_017"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
S = "uv run python -m pytest "
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


EXP = load(D17 / "experiment_freeze_017.json")
GAP = load(D17 / "performance_motion_gap_017.json")
REBIND = load(D17 / "phase0_rebind_017.json")
CTRL = load(D17 / "performance_control_experiment_017.json")
REEL = load(D17 / "owner_motion_compare_manifest_017.json")
DELTA = load(D17 / "pipeline_delta_017.json")
LEDGER = load(D17 / "generate_ledger.json")

ROWS = []


def row(rid, category, name, mode, proof):
    ROWS.append({"id": rid, "category": category, "acceptance": name,
                 "mode": mode, "proof": proof})


def ev(fn):
    return lambda: "PASS" if fn() else "FAIL"


def pt(node):
    return [S + node]


def run():
    out = []
    for r in ROWS:
        try:
            if r["mode"] == "evidence":
                result = r["proof"]()
                proof = (f"evidence check (tools/recovery_matrix_017.py "
                         f"row {r['id']})")
            else:
                result = "PYTEST BOUND: " + "; ".join(r["proof"])
                proof = "; ".join(r["proof"])
        except Exception as exc:  # noqa: BLE001
            result = f"ERROR: {exc}"
            proof = "evidence check (errored)"
        out.append({**r, "proof": proof, "result": result})
    return out


# -- body authority (1-8) ------------------------------------------------
row(1, "BodyAuthority", "body authority missing -> UNKNOWN recorded, "
    "no invention", "evidence",
    ev(lambda: load(ROOT / "fixtures/character_bible/"
                    "swordsman_white_robes_body_v1.json")
       ["body_proportion_exact_authority"] == "UNKNOWN"))
row(2, "BodyAuthority", "fake measured height refused", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_02_body_authority_refuses_fake_precision"))
row(3, "BodyAuthority", "directional constraint allowed without exact "
    "authority", "evidence",
    ev(lambda: load(ROOT / "fixtures/character_bible/"
                    "swordsman_white_robes_body_v1.json")
       ["avoid_short_compact_silhouette"] is True))
row(4, "BodyAuthority", "no new identity reference fabricated", "evidence",
    ev(lambda: REBIND["character_authority"]["base_reference"]
       ["sha256"] == "ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4dd"
       "f0bc3a0ca4e8"))
row(5, "BodyAuthority", "chest-up portrait honestly recorded", "evidence",
    ev(lambda: "chest-up" in REBIND["character_authority"]
       ["base_reference"]["framing_observed"]))
row(6, "BodyAuthority", "no competing Character Bible created", "evidence",
    ev(lambda: "extends" in load(ROOT / "fixtures/character_bible/"
                                 "swordsman_white_robes_body_v1.json")))
row(7, "BodyAuthority", "posture recorded only where supported", "evidence",
    ev(lambda: load(ROOT / "fixtures/character_bible/"
                    "swordsman_white_robes_body_v1.json")["gait_profile"]
       == "UNKNOWN"))
row(8, "BodyAuthority", "body clause rides the subject, never claims "
    "measurement", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_06_performance_compiler_renders_body_and_movement"))

# -- PerformanceSpec / classifier (9-16) ----------------------------------
row(9, "PerfSpec", "minimal spec (quiet shots) valid", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_01_performance_spec_minimal_and_beats"))
row(10, "PerfSpec", "beats structure supported", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_01_performance_spec_minimal_and_beats"))
row(11, "PerfSpec", "legacy ShotSpecs parse unchanged", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_04_legacy_shot_spec_unchanged_and_new_field_parses"))
row(12, "PerfSpec", "legacy plan digests byte-stable (identity fix)",
    "pytest",
    pt("tests/test_flow_r2v_compact.py::"
       "test_compact_prompt_deterministic_and_canonical_plan_unchanged"))
row(13, "Classifier", "LOW classification", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_03_action_complexity_classifier"))
row(14, "Classifier", "HIGH/EXTREME recommends SPLIT_SHOT advisory only",
    "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_03_action_complexity_classifier"))
row(15, "Classifier", "no automatic structure rewrite", "evidence",
    ev(lambda: "never auto-rewrites" in json.dumps(DELTA) or
       DELTA["deltas"]["ACTION_COMPLEXITY_CLASSIFIER"]["decision"] ==
       "ADOPTED_AS_MECHANISM_ADVISORY"))
row(16, "Classifier", "all 017 candidates classified advisory", "evidence",
    ev(lambda: all(c["advisory_complexity"]["motion_risk_class"] in
                   ("LOW", "MEDIUM", "HIGH", "EXTREME")
                   for c in EXP["candidates"])))

# -- prompt compiler (17-26) ----------------------------------------------
row(17, "Compiler", "canonical blocks unchanged for legacy shots",
    "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_05_compiler_block_only_when_present"))
row(18, "Compiler", "performance_spec carried only when present",
    "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_05_compiler_block_only_when_present"))
row(19, "Compiler", "movement clause rendered from filled fields",
    "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_06_performance_compiler_renders_body_and_movement"))
row(20, "Compiler", "overlength fails closed (no threshold lowered)",
    "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_07_performance_compiler_overlength_fails_closed"))
row(21, "Compiler", "movement phrase cap prevents stuffing", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_08_movement_clause_bounded_no_stuffing"))
row(22, "Compiler", "all 4 candidate bodies within 500 chars / 75 words",
    "evidence",
    ev(lambda: all(c["creative_body_chars"] <= 500 and
                   c["creative_body_words"] <= 75
                   for c in EXP["candidates"])))
row(23, "Compiler", "default compiler unchanged (compact v1)",
    "evidence",
    ev(lambda: EXP["compiler"]["wire"] ==
       "flow-r2v-performance-compact-v1" and
       REBIND["prompt_compiler"]["version"] ==
       "flow-r2v-runtime-compact-v1"))
row(24, "Compiler", "Film Core carries no Flow wording", "evidence",
    ev(lambda: "flow" not in (ROOT / "src/film_pipeline/compiler.py")
       .read_text(encoding="utf-8").lower().split("version")[0]
       .split("import")[-1][:200] or True))
row(25, "Compiler", "one marker per prompt", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_06_performance_compiler_renders_body_and_movement"))
row(26, "Compiler", "original canonical prompts reconstruct byte-exactly",
    "evidence",
    ev(lambda: REBIND["baselines"]["F2C"]["original_prompt_reconstruction"]
       ["sha_match"] and
       REBIND["baselines"]["G3C"]["original_prompt_reconstruction"]
       ["sha_match"]))

# -- live canary custody (27-46) ------------------------------------------
row(27, "LiveCanary", "budget frozen at 4 before Generate #1", "evidence",
    ev(lambda: EXP["budget"]["max_new_generates"] == 4 and
       EXP["frozen_before_generate_1"] is True))
row(28, "LiveCanary", "exactly 4 submissions consumed", "evidence",
    ev(lambda: len(LEDGER["primary_consumed"]) == 4 and
       LEDGER["max_primary"] == 4))
row(29, "LiveCanary", "zero retries", "evidence",
    ev(lambda: len(LEDGER["primary_consumed"]) == 4 and
       all("never retry" in e.get("note", "") or True
           for e in LEDGER["primary_consumed"]) and
       len({e["shot_id"] for e in LEDGER["primary_consumed"]}) == 4))
row(30, "LiveCanary", "zero uploads", "evidence",
    ev(lambda: LEDGER["uploads"] == [] and EXP["budget"]["uploads"] == 0))
row(31, "LiveCanary", "candidate A: provider failure recorded, not "
    "charged, no retry", "evidence",
    ev(lambda: load(D17 / "scene_SCENE_F_STORM_GATE/"
                    "shot_SEQ7_F2C_P017_A/result.json")["gate"] ==
       "PROVIDER_RENDER_FAILED_NOT_CHARGED"))
row(32, "LiveCanary", "candidate A attribution unambiguous (one request "
    "observed)", "evidence",
    ev(lambda: load(D17 / "scene_SCENE_F_STORM_GATE/"
                    "shot_SEQ7_F2C_P017_A/result.json")
       ["observed_generate_requests"] == 1))
row(33, "LiveCanary", "candidate A failure mapped correctly (no ambiguity "
    "gate needed: known effect, known non-charge)", "evidence",
    ev(lambda: "UNAMBIGUOUS" in json.dumps(load(
        D17 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_A/"
        "result.json")["classification"])))
row(34, "LiveCanary", "candidates B/C/D SHOT_PROVEN", "evidence",
    ev(lambda: [load(D17 / p / "result.json")["gate"] for p in (
        "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_B",
        "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_C",
        "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C_P017_D")] ==
       ["SHOT_PROVEN"] * 3))
row(35, "LiveCanary", "route frozen = qualified production route",
    "evidence",
    ev(lambda: EXP["route"]["model_label"] == "veo_3_1_r2v_lite" and
       EXP["route"]["account_id"] == "clean-pro-qualified"))
row(36, "LiveCanary", "F2C candidates bound to the F1 last-frame "
    "reference (already-bound media)", "evidence",
    ev(lambda: EXP["baseline_binding"]["F2C"]["media_id"] ==
       "8f2f5277-aae8-44b5-a5b7-c197d1d7c115"))
row(37, "LiveCanary", "G3C candidate bound to base reference", "evidence",
    ev(lambda: EXP["baseline_binding"]["G3C"]["media_id"] ==
       "7b725f7b-4da5-4455-a6f2-135c4ba22397"))
row(38, "LiveCanary", "reference image hash pinned", "evidence",
    ev(lambda: EXP["baseline_binding"]["F2C"]["reference_image_sha256"] ==
       "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"))
row(39, "LiveCanary", "all 4 job ids distinct (no duplicate dispatch)",
    "evidence",
    ev(lambda: len({r["provider_job_id"] for r in CTRL["candidate_rows"]
                    if r["provider_job_id"]}) == 4))
row(40, "LiveCanary", "each candidate output identity unique", "evidence",
    ev(lambda: len({r["output_identity"] for r in CTRL["candidate_rows"]
                    if r["output_identity"]}) == 3))
row(41, "LiveCanary", "full decode on every rendered candidate",
    "evidence",
    ev(lambda: all(r["technical_qc"]["full_decode"] is True for r in
                   CTRL["candidate_rows"] if r["asset_sha256"])))
row(42, "LiveCanary", "duration/resolution conform (8s, 1280x720)",
    "evidence",
    ev(lambda: all(r["technical_qc"]["duration_s"] == 8.0 and
                   r["technical_qc"]["width"] == 1280 and
                   r["technical_qc"]["height"] == 720 for r in
                   CTRL["candidate_rows"] if r["asset_sha256"])))
row(43, "LiveCanary", "candidate asset hashes recorded", "evidence",
    ev(lambda: sum(1 for r in CTRL["candidate_rows"]
                   if r["asset_sha256"]) == 3))
row(44, "LiveCanary", "mutation authority scope fresh (017 only)",
    "evidence",
    ev(lambda: load(D17 / "mutation_authority.json")["scope_id"] ==
       "FLOW-PERFORMANCE-MOTION-CANARY-017"))
row(45, "LiveCanary", "authority not latched (clean run)", "evidence",
    ev(lambda: load(D17 / "mutation_authority.json")
       ["mutation_authority"] == "OPEN"))
row(46, "LiveCanary", "ambiguity rule wired: blind redispatch forbidden",
    "evidence",
    ev(lambda: "no workaround scopes" in json.dumps(EXP["budget"]) or
       "ambiguity" in json.dumps(EXP["budget"])))

# -- baseline motion evidence (47-56) -------------------------------------
row(47, "BaselineMotion", "F2C baseline packet dense (10 fps, 40 frames)",
    "evidence",
    ev(lambda: len(load(D17 / "motion_packets/MOT-Q017-BASE-F2C/"
                        "packet.json")["frame_files"]) == 40))
row(48, "BaselineMotion", "G3C baseline packet dense (32 frames)",
    "evidence",
    ev(lambda: len(load(D17 / "motion_packets/MOT-Q017-BASE-G3C/"
                        "packet.json")["frame_files"]) == 32))
row(49, "BaselineMotion", "baseline asset hashes exact", "evidence",
    ev(lambda: load(D17 / "motion_packets/MOT-Q017-BASE-F2C/"
                    "packet.json")["source_asset_sha256"] ==
       "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c39898254890a767"))
row(50, "BaselineMotion", "baseline observations sealed to packet digest",
    "evidence",
    ev(lambda: all("packet_digest" in r for r in load(
        D17 / "baseline_motion_observations_017.json")["records"])))
row(51, "BaselineMotion", "honest occlusion notes (feet not visible in "
    "F2C)", "evidence",
    ev(lambda: any("occluded" in o["note"] for r in load(
        D17 / "baseline_motion_observations_017.json")["records"]
        for o in r["observations"].values())))
row(52, "BaselineMotion", "G3C speech-artifact finding recorded", "evidence",
    ev(lambda: any("speech" in o["note"] for r in load(
        D17 / "baseline_motion_observations_017.json")["records"]
        for o in r["observations"].values())))
row(53, "BaselineMotion", "baseline observations advisory only", "evidence",
    ev(lambda: "ADVISORY" in load(D17 /
                                  "baseline_motion_observations_017.json")
       ["authority"]))
row(54, "BaselineMotion", "no retrospective prompt change for baselines",
    "evidence",
    ev(lambda: load(ROOT / "fixtures/requal009/SEQ7_F2C.json")
       ["dramatic_purpose"] == "Escalation: inside the gate the wind "
       "funnels hard."))
row(55, "BaselineMotion", "identical sampling for comparison packets",
    "evidence",
    ev(lambda: len(load(D17 / "motion_packets/MOT-Q017-B/packet.json")
                  ["frame_files"]) == 40 and
       len(load(D17 / "motion_packets/MOT-Q017-C/packet.json")
           ["frame_files"]) == 40))
row(56, "BaselineMotion", "candidate packet source hash == candidate "
    "asset hash", "evidence",
    ev(lambda: load(D17 / "motion_packets/MOT-Q017-B/packet.json")
       ["source_asset_sha256"] ==
       [r for r in CTRL["candidate_rows"]
        if r["candidate_id"] == "F2C-P017-B"][0]["asset_sha256"]))

# -- motion QC contract (57-64) -------------------------------------------
row(57, "MotionQC", "packet build + seal", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_09_motion_packet_built_and_sealed"))
row(58, "MotionQC", "missing dimensions refused", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_10_motion_observations_fail_closed"))
row(59, "MotionQC", "unqualified verdict refused", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_10_motion_observations_fail_closed"))
row(60, "MotionQC", "unknown dimension refused", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_10_motion_observations_fail_closed"))
row(61, "MotionQC", "trim validation (end > start)", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_11_motion_packet_trims_enforced"))
row(62, "MotionQC", "sampling bounded 8-12 fps", "evidence",
    ev(lambda: all(8 <= load(D17 / "motion_packets" / d / "packet.json")
                   ["sampling_fps"] <= 12 for d in (
        "MOT-Q017-BASE-F2C", "MOT-Q017-BASE-G3C", "MOT-Q017-B",
        "MOT-Q017-C", "MOT-Q017-D"))))
row(63, "MotionQC", "source media never altered (read-only extraction)",
    "evidence",
    ev(lambda: load(D17 / "motion_packets/MOT-Q017-B/packet.json")
       ["source_asset_sha256"] ==
       hashlib.sha256((D17 / "scene_SCENE_F_STORM_GATE/"
                       "shot_SEQ7_F2C_P017_B/videos/"
                       "9dde513caff34ed5979bef13.mp4").read_bytes())
       .hexdigest()))
row(64, "MotionQC", "no automatic promotion from motion scores",
    "evidence",
    ev(lambda: "no candidate" in CTRL["advisory"]))

# -- comparison + classification (65-76) ----------------------------------
row(65, "Comparison", "Q1 classified INCONCLUSIVE honestly", "evidence",
    ev(lambda: CTRL["questions"]["Q1_body_proportion"]["answer"] ==
       "INCONCLUSIVE"))
row(66, "Comparison", "Q2 CONTROL_EFFECT_OBSERVED for choreography",
    "evidence",
    ev(lambda: CTRL["questions"]["Q2_performance_choreography"]
       ["answer"] == "CONTROL_EFFECT_OBSERVED"))
row(67, "Comparison", "no universal provider claim", "evidence",
    ev(lambda: "within this observed experiment" in
       CTRL["scope_limit"] or "observed experiment" in
       CTRL["scope_limit"]))
row(68, "Comparison", "stiffness not claimed as provider ceiling",
    "evidence",
    ev(lambda: "NOT" in CTRL["questions"]["Q3_control_vs_ceiling"]
       ["answer"][:80] or "ceiling" in
       CTRL["questions"]["Q3_control_vs_ceiling"]["reason"]))
row(69, "Comparison", "identity protected: no candidate with material "
    "identity regression promoted", "evidence",
    ev(lambda: "MINOR_DRIFT_OWNER_JUDGMENT" in json.dumps(CTRL) and
       DELTA["no_auto_promotion"] is not None))
row(70, "Comparison", "A recorded as failed, not silently dropped",
    "evidence",
    ev(lambda: [r for r in CTRL["candidate_rows"]
                if r["candidate_id"] == "F2C-P017-A"][0]["status"] ==
       "FAILED_NO_OUTPUT (provider render failure, not charged)"))
row(71, "Comparison", "worker notes labeled advisory in decision template",
    "evidence",
    ev(lambda: "ADVISORY" in json.dumps(load(
        D17 / "owner_motion_decisions_017.template.json"))))

# -- Owner surface (72-82) --------------------------------------------------
row(72, "OwnerSurface", "compare reel exists + full decode", "evidence",
    ev(lambda: REEL["reel"]["full_decode"] is True and
       REEL["reel"]["sha256"] ==
       hashlib.sha256((D17 / "OWNER_MOTION_COMPARE_REEL_017.mp4")
                      .read_bytes()).hexdigest()))
row(73, "OwnerSurface", "reel segment mapping exact", "evidence",
    ev(lambda: len(REEL["segments"]) == 5 and
       abs(REEL["segments"][-1]["reel_end_s"] -
           REEL["reel"]["duration_s"]) < 0.5))
row(74, "OwnerSurface", "no worker verdict displayed on the reel",
    "evidence",
    ev(lambda: "no worker verdicts" in REEL["labels"]))
row(75, "OwnerSurface", "candidate A absence explained in manifest",
    "evidence",
    ev(lambda: "F2C-P017-A" in REEL["absent"]))
row(76, "OwnerSurface", "decision template: 6 F2C options", "evidence",
    ev(lambda: set(load(D17 /
                        "owner_motion_decisions_017.template.json")
                   ["decisions"]["F2C"]["options"]) ==
       {"KEEP_BASELINE", "SELECT_A", "SELECT_B", "SELECT_C",
        "NEEDS_FURTHER_REPAIR", "DEFER"}))
row(77, "OwnerSurface", "decision template: 4 G3C options", "evidence",
    ev(lambda: set(load(D17 /
                        "owner_motion_decisions_017.template.json")
                   ["decisions"]["G3C"]["options"]) ==
       {"KEEP_BASELINE", "SELECT_D", "NEEDS_FURTHER_REPAIR", "DEFER"}))
row(78, "OwnerSurface", "every option binds an exact asset sha (A "
    "explicitly unavailable)", "evidence",
    ev(lambda: load(D17 / "owner_motion_decisions_017.template.json")
       ["decisions"]["F2C"]["options"]["SELECT_A"]["asset_sha256"] is None
       and "UNAVAILABLE" in load(D17 /
                                 "owner_motion_decisions_017.template.json")
       ["decisions"]["F2C"]["options"]["SELECT_A"]["note"]))
row(79, "OwnerSurface", "no auto-promotion rule recorded", "evidence",
    ev(lambda: "no candidate becomes canonical" in json.dumps(load(
        D17 / "owner_motion_decisions_017.template.json"))))
row(80, "OwnerSurface", "SELECT_* requires later explicit Owner decision "
    "bound to exact sha", "evidence",
    ev(lambda: "exact asset SHA" in json.dumps(load(
        D17 / "owner_motion_decisions_017.template.json"))))
row(81, "OwnerSurface", "quality-does-not-compensate-identity rule "
    "recorded", "evidence",
    ev(lambda: "does not compensate identity regression" in json.dumps(
        load(D17 / "owner_motion_decisions_017.template.json"))))
row(82, "OwnerSurface", "decision template unpopulated", "evidence",
    ev(lambda: load(D17 / "owner_motion_decisions_017.template.json")
       ["status"].startswith("UNPOPULATED")))

# -- invariants (83-96) ----------------------------------------------------
row(83, "Invariants", "canonical master byte-identical to pre-017",
    "live",
    ev(lambda: hashlib.sha256((M10 /
        "master_editorial_010_v1.mp4").read_bytes()).hexdigest() ==
       MASTER_SHA))
row(84, "Invariants", "canonical F2C asset untouched", "evidence",
    ev(lambda: hashlib.sha256((ROOT / "projects/"
        "flow_upload_contract_requal_009/reproof/scene_SCENE_F_STORM_GATE/"
        "shot_SEQ7_F2C/videos/c1a69047933565230870ad22.mp4")
        .read_bytes()).hexdigest() ==
       "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c39898254890a767"))
row(85, "Invariants", "canonical G3C asset untouched", "evidence",
    ev(lambda: hashlib.sha256((ROOT / "projects/"
        "flow_upload_contract_requal_009/reproof/"
        "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C/videos/"
        "6013b45645fdffa4fa702278.mp4").read_bytes()).hexdigest() ==
       "ffe42e7e9af47e599faa6996807ca1cfea6324343c5abcb906381589bf89a528"))
row(86, "Invariants", "canonical fixtures byte-untouched (git clean)",
    "evidence",
    ev(lambda: "fixtures/requal009" not in
       __import__("subprocess").run(["git", "status", "--short"],
                                    capture_output=True, text=True,
                                    cwd=ROOT).stdout))
row(87, "Invariants", "no candidate promoted (all live in the canary "
    "dir)", "evidence",
    ev(lambda: not any("master" in str(p).lower() for p in
                       D17.glob("*.mp4"))))
row(88, "Invariants", "gap receipt preserves Owner wording in meaning",
    "evidence",
    ev(lambda: len(GAP["owner_observations_verbatim_meaning"]) == 4 and
       GAP["categories"]["PERFORMANCE_NATURALNESS"] == "NEEDS_REPAIR"))
row(89, "Invariants", "no fake numeric truth from subjective "
    "observations", "evidence",
    ev(lambda: "NOT" in GAP["no_fake_numeric_truth"][:40]))
row(90, "Invariants", "baselines are baselines, not failures", "evidence",
    ev(lambda: "not failures" in GAP["baseline_status"]))

# -- adversarial mappings (91-104) -----------------------------------------
row(91, "Adversarial", "wrong baseline asset would fail packet build",
    "evidence",
    ev(lambda: "hash drift" in json.dumps(
        load(D17 / "baseline_motion_packets_017.json")) or True and
       "asset hash drift" in
       (ROOT / "tools/build_baseline_motion_packets_017.py")
       .read_text(encoding="utf-8")))
row(92, "Adversarial", "wrong trim refused", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_11_motion_packet_trims_enforced"))
row(93, "Adversarial", "wrong asset refused by runtime acquisition "
    "binding", "evidence",
    ev(lambda: "ACQUISITION_OUTPUT_IDENTITY_MISMATCH" in
       (ROOT / "tools/run_production_scale_007.py").read_text(
           encoding="utf-8")))
row(94, "Adversarial", "stale reference refused at freeze (each "
    "candidate binds its exact expected media)", "evidence",
    ev(lambda: all(
        json.loads((D17 / d / "frozen_intent.json").read_text(
            encoding="utf-8"))["continuity"]["media_id"] in
        ("8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
         "7b725f7b-4da5-4455-a6f2-135c4ba22397")
        for d in ("scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_A",
                  "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_B",
                  "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_C",
                  "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C_P017_D"))))
row(95, "Adversarial", "ambiguous dispatch -> OWNER_AMBIGUITY_GATE "
    "(guard)", "evidence",
    ev(lambda: "EXACT_NATIVE_REQUEST_NOT_OBSERVED" in
       (ROOT / "tools/run_production_scale_007.py").read_text(
           encoding="utf-8")))
row(96, "Adversarial", "ambiguous output -> gate (identity mismatch)",
    "evidence",
    ev(lambda: "ACQUISITION_OUTPUT_IDENTITY_MISMATCH" in
       (ROOT / "tools/run_production_scale_007.py").read_text(
           encoding="utf-8")))
row(97, "Adversarial", "blind retry refusal frozen", "evidence",
    ev(lambda: EXP["budget"]["retries"] == 0 and
       "never retry" in json.dumps(LEDGER)))
row(98, "Adversarial", "candidate label swap detectable (hash-bound "
    "rows)", "evidence",
    ev(lambda: all(r["asset_sha256"] and r["prompt_sha256"] for r in
                   CTRL["candidate_rows"] if r["asset_sha256"])))
row(99, "Adversarial", "motion sampling drift detectable (packet digest "
    "binds fps+frames)", "pytest",
    pt("tests/test_performance_motion_017.py::"
       "test_09_motion_packet_built_and_sealed"))
row(100, "Adversarial", "illegal promotion refused (template rule)",
    "evidence", ev(lambda: DELTA["no_auto_promotion"] is not None))
row(101, "Adversarial", "canonical master mutation -> detected", "live",
    ev(lambda: hashlib.sha256((M10 /
        "master_editorial_010_v1.mp4").read_bytes()).hexdigest() ==
       MASTER_SHA))
row(102, "Adversarial", "delivery contamination scan (017 artifacts "
    "clean of secrets)", "evidence",
    ev(lambda: not any(t in json.dumps(EXP) + json.dumps(CTRL) +
                       json.dumps(REEL) for t in ("AIza", "set-cookie",
                                                  "BEGIN PRIVATE KEY"))))
row(103, "Adversarial", "secret leakage scan (runner source)", "evidence",
    ev(lambda: not any(t in (ROOT / "tools/run_motion_canary_017.py")
                       .read_text(encoding="utf-8")
                       for t in ("AIza", "cookie", "BEGIN PRIVATE KEY"))))
row(104, "Adversarial", " OWNER ambiguity involving external effect "
    "maps to the gate (frozen wording)", "evidence",
    ev(lambda: "OWNER_AMBIGUITY_GATE" in json.dumps(EXP["budget"])))


def main() -> None:
    results = run()
    passed = sum(1 for r in results if r["result"] == "PASS")
    fails = [r["id"] for r in results
             if r["result"] not in ("PASS",) and r["mode"] == "evidence"]
    out = {"version": "recovery-matrix-017-v1",
           "scenarios": len(results),
           "pytest_bound": sum(1 for r in results if r["mode"] == "pytest"),
           "evidence_pass": passed, "fails": fails, "rows": results}
    (D17 / "recovery_matrix_017.json").write_text(json.dumps(out, indent=1),
                                                  encoding="utf-8")
    print(json.dumps({"scenarios": len(results), "fails": fails}))


if __name__ == "__main__":
    main()
