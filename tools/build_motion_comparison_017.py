"""FLOW-PERFORMANCE-MOTION-CANARY-017 (Phases 11-13): identity/body
comparison, temporal performance comparison, and the control-vs-ceiling
classification.

Every observation below was made by the worker reviewer against the
dense frame packets and side-by-side stills on disk (grids + comparison
PNGs). All verdicts are ADVISORY; the Owner decides from the compare
reel. A = failed provider-side (no output) and is classified as such.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.motion_qc import MotionReviewPacket, record_motion_observations

D17 = ROOT / "projects/flow_performance_motion_canary_017"
REVIEWER = "build_worker_glmanalyst (dense-frame + side-by-side review)"
NOW = "2026-10-04T12:40:00+00:00"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CANDIDATES = {
    "F2C-P017-A": {
        "shot_id": "SEQ7_F2C_P017_A",
        "result": D17 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_A/"
                 "result.json",
        "status": "FAILED_NO_OUTPUT (provider render failure, not charged)",
        "asset_sha256": None,
        "video": None,
        "packet": None},
    "F2C-P017-B": {
        "shot_id": "SEQ7_F2C_P017_B",
        "result": D17 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_B/"
                 "result.json",
        "status": "SHOT_PROVEN",
        "video": D17 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_B/"
                 "videos/9dde513caff34ed5979bef13.mp4",
        "packet": D17 / "motion_packets/MOT-Q017-B"},
    "F2C-P017-C": {
        "shot_id": "SEQ7_F2C_P017_C",
        "result": D17 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_C/"
                 "result.json",
        "status": "SHOT_PROVEN",
        "video": D17 / "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_C/"
                 "videos/b104f61c4424cf3e0e564323.mp4",
        "packet": D17 / "motion_packets/MOT-Q017-C"},
    "G3C-P017-D": {
        "shot_id": "SEQ7_G3C_P017_D",
        "result": D17 / "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C_P017_D/"
                 "result.json",
        "status": "SHOT_PROVEN",
        "video": D17 / "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C_P017_D/"
                 "videos/23eadf3f247614c52d4cb5a6.mp4",
        "packet": D17 / "motion_packets/MOT-Q017-D"},
}

BASELINES = {
    "F2C": {"video": ROOT / "projects/flow_upload_contract_requal_009/"
            "reproof/scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
            "c1a69047933565230870ad22.mp4",
            "asset_sha256": "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c"
                            "8c39898254890a767",
            "packet": D17 / "motion_packets/MOT-Q017-BASE-F2C"},
    "G3C": {"video": ROOT / "projects/flow_upload_contract_requal_009/"
            "reproof/scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C/videos/"
            "6013b45645fdffa4fa702278.mp4",
            "asset_sha256": "ffe42e7e9af47e599faa6996807ca1cfea6324343c5abc"
                            "b906381589bf89a528",
            "packet": D17 / "motion_packets/MOT-Q017-BASE-G3C"},
}

IDENTITY_ROWS = {
    "F2C-P017-A": {
        "STATUS": ("NO_OUTPUT", "provider render failure before any "
                   "frame existed; nothing to compare; not charged; no "
                   "retry permitted")},
    "F2C-P017-B": {
        "FACE_IDENTITY": ("PASS_MINOR_NOTES", "profile visible; same "
                          "character reads consistent (topknot, "
                          "headband, white robes); no material drift"),
        "HAIR": "PASS", "COSTUME": "PASS",
        "BODY_SILHOUETTE": ("IMPROVED_UNCERTAIN", "reads taller/leaner "
                            "and far less compact than baseline, BUT the "
                            "model also re-staged the shot wider (full "
                            "body vs waist-up), so proportion attribution "
                            "is confounded"),
        "TORSO_LEG_BALANCE": ("IMPROVED_UNCERTAIN", "legs visible and "
                              "proportionate; baseline legs occluded"),
        "APPARENT_STATURE": ("IMPROVED_UNCERTAIN", "reads taller; framing "
                             "confound"),
        "POSTURE": "IMPROVED (dynamic drive vs unit-lean)",
        "WORLD_CONTINUITY": ("CHANGED_STAGING", "gate re-staged behind "
                             "the figure; same world (rocks, storm, "
                             "grass) but the gate-contact continuity of "
                             "the baseline is not preserved"),
    },
    "F2C-P017-C": {
        "FACE_IDENTITY": ("PASS_MINOR_NOTES", "profile visible; "
                          "consistent with the character"),
        "HAIR": "PASS", "COSTUME": "PASS",
        "BODY_SILHOUETTE": ("IMPROVED_UNCERTAIN", "slightly leaner/"
                            "elongated vs baseline; framing closer to "
                            "baseline than B but still re-staged"),
        "TORSO_LEG_BALANCE": ("IMPROVED_UNCERTAIN", "legs visible in the "
                              "drive; proportionate"),
        "APPARENT_STATURE": ("IMPROVED_UNCERTAIN", "reads slightly taller"),
        "POSTURE": "IMPROVED (weight visibly transferring; hand retains "
                   "the gate contact)",
        "WORLD_CONTINUITY": ("BEST_OF_CANDIDATES", "hand-on-rock contact "
                             "preserved; same gate, storm, grass world"),
    },
    "G3C-P017-D": {
        "FACE_IDENTITY": ("MINOR_DRIFT_OWNER_JUDGMENT", "same character "
                          "family, but the face reads slightly slimmer/"
                          "more angular than the baseline; headband sits "
                          "a little differently; NOT clearly "
                          "disqualifying — Owner must judge from the "
                          "reel"),
        "HAIR": "PASS (same topknot/headband; wind motion present)",
        "COSTUME": "PASS",
        "BODY_SILHOUETTE": ("NOT_JUDGEABLE", "CU face framing"),
        "TORSO_LEG_BALANCE": ("NOT_JUDGEABLE", "CU face framing"),
        "APPARENT_STATURE": ("NOT_JUDGEABLE", "CU face framing"),
        "POSTURE": ("IMPROVED_SUBTLE", "mouth stays closed (the "
                    "baseline's speech-like artifact is gone); the "
                    "settle is subtle by framing"),
        "WORLD_CONTINUITY": "PASS (same clouds/mountains/light)",
    },
}

MOTION_OBS = {
    "F2C-P017-B": {
        "GAIT_NATURALNESS": ("PASS", "visible stride with real leg "
                             "articulation; reads as a driven run-step"),
        "WEIGHT_TRANSFER": ("PASS", "weight visibly shifts over the "
                            "driving leg across the window"),
        "FOOT_SLIDING": ("INCONCLUSIVE", "feet visible in many frames "
                         "but partially blurred; no obvious sliding"),
        "JOINT_CONTINUITY": ("PASS", "no joint popping across 40 frames"),
        "TORSO_HIP_COORDINATION": ("PASS", "torso and hips counter-"
                                   "rotate through the drive"),
        "ARM_COUNTERMOTION": ("PASS", "arms visibly counter-swing"),
        "CONTACT_PHYSICS": ("INCONCLUSIVE", "the gate contact of the "
                            "baseline is not restaged; no contact event "
                            "in window"),
        "ACCELERATION_DECELERATION": ("PASS", "acceleration into the "
                                      "stride reads natural"),
        "REACTION_TIMING": ("PASS", "body reads responsive to the gust"),
        "RECOVERY_SETTLING": ("INCONCLUSIVE", "window ends mid-stride"),
        "PERFORMANCE_STIFFNESS": ("PASS", "materially less stiff than "
                                  "the baseline; segment articulation "
                                  "visible"),
    },
    "F2C-P017-C": {
        "GAIT_NATURALNESS": ("PASS", "driving step reads natural"),
        "WEIGHT_TRANSFER": ("PASS", "weight rolls over the planted foot "
                            "as directed"),
        "FOOT_SLIDING": ("INCONCLUSIVE", "feet partly visible; no "
                         "obvious slide"),
        "JOINT_CONTINUITY": ("PASS", "clean across 40 frames"),
        "TORSO_HIP_COORDINATION": ("PASS", "counter-rotation visible as "
                                   "directed"),
        "ARM_COUNTERMOTION": ("INCONCLUSIVE", "arms partially obscured "
                              "by robes"),
        "CONTACT_PHYSICS": ("PASS", "hand keeps the rock-gate contact "
                            "and pushes off plausibly"),
        "ACCELERATION_DECELERATION": ("PASS", "drive and settle read "
                                      "natural"),
        "REACTION_TIMING": ("PASS", "responsive to the gust"),
        "RECOVERY_SETTLING": ("PASS", "settles over the planted foot at "
                              "the end of the window"),
        "PERFORMANCE_STIFFNESS": ("PASS", "materially less stiff than "
                                  "baseline"),
    },
    "G3C-P017-D": {
        "GAIT_NATURALNESS": ("INCONCLUSIVE", "CU face framing"),
        "WEIGHT_TRANSFER": ("INCONCLUSIVE", "CU face framing"),
        "FOOT_SLIDING": ("INCONCLUSIVE", "CU face framing"),
        "JOINT_CONTINUITY": ("PASS", "face/neck stable across 32 frames"),
        "TORSO_HIP_COORDINATION": ("INCONCLUSIVE", "torso edge only"),
        "ARM_COUNTERMOTION": ("INCONCLUSIVE", "arms not visible"),
        "CONTACT_PHYSICS": ("INCONCLUSIVE", "no contact event"),
        "ACCELERATION_DECELERATION": ("INCONCLUSIVE", "no locomotion"),
        "REACTION_TIMING": ("INCONCLUSIVE", "no external event"),
        "RECOVERY_SETTLING": ("PASS", "the directed exhale/settle reads; "
                              "baseline's speech-like mouth artifact is "
                              "eliminated (mouth stays closed)"),
        "PERFORMANCE_STIFFNESS": ("INCONCLUSIVE", "subtle by framing; "
                                  "improved but magnitude not judgeable "
                                  "in CU"),
    },
}


def main() -> None:
    rows = []
    for cand_id, cand in CANDIDATES.items():
        result = json.loads(cand["result"].read_text(encoding="utf-8"))
        frozen = (cand["result"].parent / "frozen_intent.json")
        intent = json.loads(frozen.read_text(encoding="utf-8")) \
            if frozen.exists() else {}
        video_sha = sha(cand["video"]) if cand["video"] else None
        motion = None
        if cand["packet"]:
            packet = MotionReviewPacket.model_validate(json.loads(
                (cand["packet"] / "packet.json").read_text(
                    encoding="utf-8")))
            if video_sha and packet.source_asset_sha256 != video_sha:
                raise SystemExit(f"packet source drift for {cand_id}")
            motion = record_motion_observations(
                packet, observations=MOTION_OBS[cand_id],
                reviewer_identity=REVIEWER, reviewed_at=NOW)
        rows.append({
            "candidate_id": cand_id,
            "shot_id": cand["shot_id"],
            "status": cand["status"],
            "provider_job_id": result.get("provider_job_id") or
            intent.get("provider_job_id"),
            "output_identity": result.get("output_identity"),
            "prompt_sha256": result.get("prompt_sha256") or
            intent.get("prompt_sha256"),
            "asset_sha256": video_sha,
            "technical_qc": {
                "gate": result.get("gate"),
                "duration_s": (result.get("qc_eligibility") or {})
                .get("metadata", {}).get("duration_s"),
                "width": (result.get("qc_eligibility") or {})
                .get("metadata", {}).get("width"),
                "height": (result.get("qc_eligibility") or {})
                .get("metadata", {}).get("height"),
                "full_decode": (result.get("decode") or {})
                .get("full_decode_eof"),
                "reference_binding": intent.get("continuity")},
            "identity_body_comparison": IDENTITY_ROWS[cand_id],
            "motion_observations": motion})

    experiment = {
        "version": "performance-control-experiment-017-v1",
        "scope_limit": "classification applies ONLY within this observed "
                       "experiment (one provider, one model label, four "
                       "submissions, two shot classes); no universal "
                       "provider claim",
        "provider_route": json.loads(
            (D17 / "experiment_freeze_017.json").read_text(
                encoding="utf-8"))["route"],
        "submissions": {"authorized": 4, "consumed": 4, "retries": 0,
                        "uploads": 0,
                        "outcomes": {"F2C-P017-A":
                                     "PROVIDER_RENDER_FAILED_NOT_CHARGED",
                                     "F2C-P017-B": "SHOT_PROVEN",
                                     "F2C-P017-C": "SHOT_PROVEN",
                                     "G3C-P017-D": "SHOT_PROVEN"}},
        "questions": {
            "Q1_body_proportion": {
                "answer": "INCONCLUSIVE",
                "reason": "the isolated proportion candidate (A) failed "
                          "provider-side before rendering; the combined "
                          "candidate (C) reads leaner/taller than the "
                          "baseline but the model also re-staged the "
                          "shot, so the silhouette delta cannot be "
                          "cleanly attributed to the proportion "
                          "control. No identity regression observed "
                          "where the body is visible."},
            "Q2_performance_choreography": {
                "answer": "CONTROL_EFFECT_OBSERVED",
                "reason": "with the SAME provider, model and reference, "
                          "the choreography candidates (B and C) render "
                          "materially more natural biomechanics than "
                          "the canonical baseline: visible stride, "
                          "weight transfer, counter-rotation, arm "
                          "counter-swing, and (C) preserved gate "
                          "contact; on G3C the directed settle removed "
                          "the baseline's speech-like mouth artifact"},
            "Q3_control_vs_ceiling": {
                "answer": ("PROMPT_CONTROL_EFFECTIVE for performance "
                           "choreography; BODY_PROPORTION "
                           "INCONCLUSIVE; the baseline stiffness is NOT "
                           "evidence of a provider ceiling within this "
                           "shot class"),
                "reason": "all candidates that rendered kept identity "
                          "stable while motion quality moved materially "
                          "under frozen choreography direction; the "
                          "stiffness defect appears CONTROLLABLE. The "
                          "single provider failure (A) was an anti-"
                          "abuse render rejection (not charged), not a "
                          "model-capability ceiling signal"},
            "per_control": {
                "BODY_PROPORTION_CONTROL": "INCONCLUSIVE",
                "PERFORMANCE_CHOREOGRAPHY": "CONTROL_EFFECT_OBSERVED",
                "COMBINED_CONTROL": "CONTROL_EFFECT_OBSERVED"},
            "generalization_G3C": ("PARTIAL: the settle/exhale "
                                   "direction clearly improved the "
                                   "worst baseline artifact; overall "
                                   "body motion remains INCONCLUSIVE in "
                                   "a CU face shot")},
        "candidate_rows": rows,
        "advisory": "all worker observations are advisory; no candidate "
                    "is promoted; the Owner decides from the compare "
                    "reel bound to exact asset hashes",
    }
    (D17 / "performance_control_experiment_017.json").write_text(
        json.dumps(experiment, indent=1), encoding="utf-8")
    print(json.dumps({"rows": len(rows),
                      "Q1": experiment["questions"]["Q1_body_proportion"]
                      ["answer"],
                      "Q2": experiment["questions"]
                      ["Q2_performance_choreography"]["answer"],
                      "Q3_scope": "classified"}))


if __name__ == "__main__":
    main()
