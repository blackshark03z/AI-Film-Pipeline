"""AI-FILM-QUALITY-V2-006 — Phases 0-7: custody/rebind, the Owner-
authorized split-reference amendment, the ATOMIC pair freeze (fixtures,
semantic identities), compiler conformance, and the admission receipt.

Generation happens ONLY in the driver (Phase 8); nothing here contacts
a provider.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.core import (ActionIntent, References, ShotSpec,
                                sha256, validate_contract)
from film_pipeline.compiler import compile_prompt
from film_pipeline.director_blocking import (
    BlockingSpec, CameraCoveragePlan, DirectorIntent,
    director_semantic_identity)
from film_pipeline.performance import BodyProportionAuthority
from film_pipeline.performance_compiler import compile_causal_r2v_prompt
from film_pipeline.quality_repair_v2 import (
    ADMISSION_REQUIRED_FROM, QUALITY_V2_CANONICAL_BASELINE, admission_gate,
    load_frozen_debt_ids, make_experiment_admission_receipt)
from run_scene_scale_003 import flow_capabilities

PKG = ROOT / "projects/quality_v2_006_f2_decomposed_live"
V5 = ROOT / "projects/quality_v2_005_f2_decomposition"
V5R = ROOT / "projects/quality_v2_005r_reference_preflight"
V4 = ROOT / "projects/quality_v2_004_f2_blocking"
FIXTURES = ROOT / "fixtures/requal006"

F2A_BINDING = {
    "media_id": "8f2f5277-aae8-44b5-a5b7-c197d1d7c115",
    "asset_id": ("asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72"
                 "eda0fa31ec44edc3"),
    "attestation_id": ("refbind_f4277ac1a7a5651c8370212417c06593f08a003a"
                       "ee1676517622292f37cb4fdf"),
    "mechanism": "last_frame", "from_shot": "SEQ7_F1",
    "source_frame_sha256": ("fecf669e9b81436c80cd6502036d10b401f3964534e"
                            "8d3fe9dea0800355f8313"),
    "reference_type": "FULL_FRAME_ENVIRONMENTAL",
    "usage": "near-side F2A only"}
F2B_BINDING = {
    "media_id": "7b725f7b-4da5-4455-a6f2-135c4ba22397",
    "asset_id": ("asset_2ab16c9f6aff842e3c3c15b2f1b0619217f3925a0ab2ae25"
                 "5b9fcd86d60a0ae2"),
    "attestation_id": ("refbind_57abbee5abc482fa52f808f813d4144bad8a8533"
                       "a972382502d4a72efe6ea2f1"),
    "mechanism": "identity_only_adoption",
    "source_frame_sha256": ("ed75a8b27b9be48c30f948a93ad7f1421e60c35a600"
                            "3efdfb4ddf0bc3a0ca4e8"),
    "reference_type": "IDENTITY_ONLY",
    "usage": "far-side F2B"}
F2B_REF_LOCAL = (ROOT / "projects/flow_production_harden_002/"
                 "requal_current_build/reference/"
                 "ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4ddf0b"
                 "c3a0ca4e8.jpg")
F2A_ATT_SRC = (V4 / "scene_SCENE_F_STORM_GATE/continuity_reference/"
               "attestation")
F2B_ATT_SRC = (ROOT / "projects/flow_production_harden_002/"
               "requal_current_build/reference/attestation")

F2_INTENT_V2 = {
    "schema_version": "action-intent-v1",
    "trigger": "a gust hits the gate",
    "perception": "he reads the gust's force",
    "character_goal": "through the gate",
    "motivation": "the journey continues past the gate",
    "obstacle_or_pressure": "the gust drives against him",
    "chosen_action": "he lowers and advances through the gust",
    "intended_outcome": "he emerges past the gate",
    "resulting_state": "he pauses briefly to recover",
    "next_decision": "the journey resumes (F3)",
    "visual_legibility_requirements": [
        "forward passage through the gate stays visible",
        "the rock is support, never destination"],
    "stakes": "the path is blocked until he passes",
    "urgency": "steady, deliberate",
    "knowledge_state": "he knows the wind, he chooses passage"}

CANDIDATES = [
    {"candidate_id": "F2A-V2-006", "shot_id": "SEQ7_F2A_V2_006",
     "purpose": "COMMIT TO CROSS — gust hits, body sets against the "
                "gust, clear forward commitment; ends AT the threshold; "
                "the crossing NEVER completes in this shot",
     "dramatic_purpose": "the gust blocks the gate; he commits",
     "blocking_start": "near side", "blocking_end": "at the gate opening",
     "critical_invariants": [
         "rock gate walls consistent with SEQ7_F1 last frame",
         "wardrobe unchanged",
         "wind direction constant against him",
         "he is on the near side moving toward the opening",
         "the crossing completes only across the cut"],
     "performance_spec": {
         "schema_version": "performance-spec-v1",
         "primary_action": "sets himself against the gust and advances "
                           "to the gate opening",
         "action_intent": "commits forward against the gust",
         "weight_transfer": "weight lowers forward",
         "motion_energy": "moderate",
         "beats": [
             {"label": "gust", "approx_start_s": 0.0,
              "description": "the gust hits him at the gate"},
             {"label": "sets himself", "approx_start_s": 1.0,
              "description": "he sets himself, body against the wind"},
             {"label": "commit", "approx_start_s": 1.8,
              "description": "deliberate steps to the opening"}]},
     "editorial_target_duration": 2.8,
     "binding": F2A_BINDING},
    {"candidate_id": "F2B-V2-006", "shot_id": "SEQ7_F2B_V2_006",
     "purpose": "EMERGE FAR SIDE — opens already crossing / just beyond "
                "the threshold; continues one direction away; the gate "
                "is BEHIND him; far side readable early",
     "dramatic_purpose": "beyond the gate, gate behind him, onward",
     "blocking_start": "just beyond the gate opening",
     "blocking_end": "beyond gate, far side clear",
     "critical_invariants": [
         "wardrobe unchanged",
         "wind direction constant",
         "the gate is behind him",
         "he keeps moving away from the gate",
         "no return toward the gate"],
     "performance_spec": {
         "schema_version": "performance-spec-v1",
         "primary_action": "continues onward away from the gate",
         "action_intent": "the committed crossing carries him onward",
         "weight_transfer": "weight rolls forward",
         "motion_energy": "moderate",
         "beats": [
             {"label": "emerge", "approx_start_s": 0.0,
              "description": "already crossing / just past the opening"},
             {"label": "stride", "approx_start_s": 0.9,
              "description": "continues onward, away from the gate"},
             {"label": "settle", "approx_start_s": 1.9,
              "description": "far side clear, steady gait"}]},
     "editorial_target_duration": 2.8,
     "binding": F2B_BINDING},
]


def body_variant(avoid: bool) -> BodyProportionAuthority:
    payload = json.loads((ROOT / "fixtures/character_bible/"
                          "swordsman_white_robes_body_v1.json")
                         .read_text(encoding="utf-8"))
    base = BodyProportionAuthority(**{k: v for k, v in payload.items()
                                      if k not in ("extends",
                                                   "look_state_id")})
    return base.model_copy(
        update={"avoid_short_compact_silhouette": avoid})


def f2b_ref_bytes_ok() -> bool:
    return F2B_REF_LOCAL.exists() and hashlib.sha256(
        F2B_REF_LOCAL.read_bytes()).hexdigest() == \
        F2B_BINDING["source_frame_sha256"]


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    V2_005R_HEAD = "6af0e7490e985d859b7148fc1b25ffa60c4d5b72"
    if head != V2_005R_HEAD:
        raise SystemExit("BLOCKED_INVARIANT: start HEAD drift")
    if not f2b_ref_bytes_ok():
        raise SystemExit("BLOCKED_INVARIANT: identity reference bytes "
                         "missing or sha mismatch")

    # ---- P0: custody ----------------------------------------------------
    plan5 = json.loads((V5 / "f2_decomposition_plan_v2_005.json")
                       .read_text(encoding="utf-8"))
    preflight = json.loads((V5R / "reference_preflight_v2_005r.json")
                           .read_text(encoding="utf-8"))
    custody = {
        "version": "v2-006-custody-v1",
        "checkpoint": "V2006_P0_REBOUND",
        "start_sha": head,
        "v2_005_final_head": "b92e03710d5aec6a48527b4fc24c4ef35deb41c7",
        "v2_005r_final_head": V2_005R_HEAD,
        "bindings": {
            "v2_005_evidence": "docs/operating/"
                               "AI_FILM_QUALITY_V2_005_F2_DECOMPOSITION_"
                               "DESIGN_EVIDENCE.md",
            "v2_005r_evidence": "docs/operating/"
                                "AI_FILM_QUALITY_V2_005R_REFERENCE_"
                                "COMPATIBILITY_PREFLIGHT_EVIDENCE.md",
            "v2_006_handoff": "docs/quality-v2/"
                              "V2_006_F2_DECOMPOSED_LIVE_HANDOFF.md",
            "frozen_f2a": {
                "director_intent_id":
                    plan5["f2a_commit_to_cross"]["intent"][
                        "director_intent_id"],
                "blocking_spec_id":
                    plan5["f2a_commit_to_cross"]["blocking"][
                        "blocking_spec_id"],
                "camera_plan_id":
                    plan5["f2a_commit_to_cross"]["camera"][
                        "camera_plan_id"]},
            "frozen_f2b": {
                "director_intent_id":
                    plan5["f2b_emerge_far_side"]["intent"][
                        "director_intent_id"],
                "blocking_spec_id":
                    plan5["f2b_emerge_far_side"]["blocking"][
                        "blocking_spec_id"],
                "camera_plan_id":
                    plan5["f2b_emerge_far_side"]["camera"][
                        "camera_plan_id"]},
            "f1_f3_continuity": {"screen_direction": "faces frame-left"},
            "quality_debt": "QD-001 (ACTIVE)",
            "canonical_f2_selected_take":
                "take_91e4997b99432358ec713c072ef3a82571f65b6b43a4a48fab8"
                "cfa17f31efb67",
            "canonical_edit_manifest_id":
                "edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590"
                "654b059c7969d3",
            "canonical_master_sha256":
                "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afd"
                "a1786595",
            "qualified_route": "flow_veo / veo_3_1_r2v_lite / project "
                               "93a579b4-834e-435b-8304-5f6682937935 / "
                               "clean-pro-qualified"},
        "owner_authorization": {
            "AUTHORIZE_SPLIT_REFERENCE": "YES",
            "authorization_source": "Owner explicit approval in Tech Lead "
                                    "chat after V2-005R",
            "scope": "ONLY the reference-strategy amendment; no provider "
                     "switch; no new uploads; no retry; no canonical "
                     "promotion"}}
    (PKG / "custody_v2_006.json").write_text(
        json.dumps(custody, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2006_P0_REBOUND", "head":
                      head[:12]}))

    # ---- P1: split-reference amendment applied --------------------------
    amendment = {
        "version": "v2-006-split-reference-amendment-v1",
        "checkpoint": "V2006_P1_AMENDMENT_APPLIED",
        "F2A_reference": {**F2A_BINDING},
        "F2B_reference": {**F2B_BINDING},
        "identity_reference_bytes_verified": f2b_ref_bytes_ok(),
        "uploads": 0,
        "upload_attempt_forbidden": "BLOCKED_INVARIANT",
        "no_environment_authority_from_identity_reference":
            "the identity-only reference carries character identity "
            "only; the F2B world (storm gate, far side) is carried by "
            "the prompt semantics alone"}
    (PKG / "split_reference_amendment_v2_006.json").write_text(
        json.dumps(amendment, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2006_P1_AMENDMENT_APPLIED"}))

    # ---- P3/P4: fixtures -------------------------------------------------
    FIXTURES.mkdir(parents=True, exist_ok=True)
    caps = flow_capabilities()
    frozen = []
    for cand in CANDIDATES:
        payload = json.loads(
            (ROOT / "fixtures/requal004/SEQ7_F2C_V2_004_A.json")
            .read_text(encoding="utf-8"))
        payload["shot_id"] = cand["shot_id"]
        payload["characters"][0]["behavior_state"] = None
        payload["dramatic_purpose"] = cand["dramatic_purpose"]
        payload["camera"] = {"framing": "WS", "height": "eye_level",
                             "lens_intent": "normal",
                             "movement": {"type": "locked"}}
        payload["environment"] = {"weather": "storm",
                                  "atmosphere": "rock gate"}
        payload["blocking"] = {"start": cand["blocking_start"],
                               "action_beats": [],
                               "end": cand["blocking_end"],
                               "prop_interactions": []}
        payload["performance"] = {
            "observable_beats": [],
            "forbidden": ["cover or stop at rock", "aimless touch",
                          "reversal"]}
        payload["continuity"] = {
            "screen_direction": "faces frame-left",
            "eyeline": "down the road ahead",
            "start_state": {}, "end_state": {},
            "critical_invariants": cand["critical_invariants"]}
        payload["performance_spec"] = cand["performance_spec"]
        payload["action_intent"] = dict(F2_INTENT_V2)
        validate_contract("shot_spec", payload)
        fixture_path = FIXTURES / f"{cand['shot_id']}.json"
        fixture_path.write_text(json.dumps(payload, indent=1),
                                encoding="utf-8")
        spec = ShotSpec.model_validate(payload)
        binding = cand["binding"]
        shot = spec.model_copy(update={
            "references": References(other_asset_ids=[binding[
                "asset_id"]])})
        plan = compile_prompt(shot, caps, reference_hashes={
            binding["asset_id"]: binding["source_frame_sha256"]})
        prompt = compile_causal_r2v_prompt(
            plan, "job_" + "0" * 64, model="veo_3_1_r2v_lite",
            performance_spec=shot.performance_spec,
            body_authority=body_variant(True),
            action_intent=shot.action_intent)
        body_text = prompt.text.rsplit(" [FILM-", 1)[0]
        if len(body_text) > 500 or len(prompt.text.split()) > 76:
            raise SystemExit(
                f"BLOCKED_INVARIANT: {cand['candidate_id']} cannot fit "
                f"the envelope ({len(body_text)} chars / "
                f"{len(prompt.text.split())} words); no silent "
                f"shortening")
        low = body_text.lower()
        required = (["gust", "sets himself", "near side", "opening",
                     "gate"] if cid_is_a(cand) else
                    ["beyond", "onward", "far side", "gate", "behind"])
        missing = [t for t in required if t not in low]
        if missing:
            raise SystemExit(
                f"BLOCKED_INVARIANT: {cand['candidate_id']} compiled "
                f"semantics lack {missing}")
        frozen.append({
            "candidate_id": cand["candidate_id"],
            "shot_id": cand["shot_id"],
            "purpose": cand["purpose"],
            "fixture": fixture_path.relative_to(ROOT).as_posix(),
            "fixture_sha256": sha256(shot),
            "prompt_compiler_version": prompt.version,
            "creative_body": body_text,
            "creative_body_chars": len(body_text),
            "creative_body_words": len(prompt.text.split()),
            "action_intent_digest": shot.action_intent.digest(),
            "performance_spec_digest": shot.performance_spec.digest(),
            "reference_binding": binding,
            "editorial_target_duration": cand["editorial_target_duration"]})

    # ---- P5: generation semantic identities (BEFORE any mutation) -------
    from film_pipeline.director_blocking import _mint as mint
    for cand, raw in zip(frozen, CANDIDATES):
        is_a = cid_is_a(raw)
        key = "f2a_commit_to_cross" if is_a else "f2b_emerge_far_side"
        shot5 = plan5[key]
        intent = DirectorIntent.model_validate(shot5["intent"])
        blocking = BlockingSpec.model_validate(shot5["blocking"])
        camera = CameraCoveragePlan.model_validate(shot5["camera"])
        ident = director_semantic_identity(
            cand["fixture_sha256"], intent, blocking, camera)
        cand["director_layer_identity"] = ident["director_layer"]
        cand["generation_semantic_identity"] = sha256({
            "base_shot_spec_sha256": cand["fixture_sha256"],
            "director_layer": ident["director_layer"],
            "action_intent_digest": cand["action_intent_digest"],
            "performance_spec_digest": cand["performance_spec_digest"],
            "reference_binding": cand["reference_binding"],
            "creative_body": cand["creative_body"]})
    if frozen[0]["generation_semantic_identity"] == \
            frozen[1]["generation_semantic_identity"]:
        raise SystemExit("BLOCKED_INVARIANT: F2A and F2B identities "
                         "collide")

    # ---- P2: atomic pair freeze -----------------------------------------
    experiment = {
        "version": "quality-v2-006-experiment-freeze-v1",
        "checkpoint": "V2006_P2_PAIR_FROZEN",
        "frozen_before_generate_1": True,
        "atomic_pair_contract": {
            "solution": "F2A + F2B (ONE editorial solution)",
            "allowed_owner_decisions": ["SELECT_F2A_F2B_PAIR",
                                        "REJECT_ALL", "KEEP_CANONICAL",
                                        "NEEDS_REPAIR", "DEFER"],
            "forbidden": ["SELECT_F2A alone", "SELECT_F2B alone"]},
        "split_reference_amendment": amendment,
        "route": {"provider_id": "flow_veo",
                  "model_label": "veo_3_1_r2v_lite",
                  "project_id": "93a579b4-834e-435b-8304-5f6682937935",
                  "account_id": "clean-pro-qualified",
                  "route_qualification": "UNCHANGED qualified route"},
        "generation_settings": {"duration_s": 8,
                                "aspect": "16:9 (1280x720)",
                                "references_per_shot": 1,
                                "reference_media": "already-bound "
                                                   "provider media only; "
                                                   "0 uploads"},
        "compiler": {"canonical": "deterministic-v1",
                     "wire": "flow-r2v-causal-compact-v1",
                     "limits": {"max_chars": 500, "max_words": 75}},
        "budget": {"max_new_generates": 2,
                   "allocation": {"F2A": 1, "F2B": 1},
                   "retries": 0, "uploads": 0,
                   "f2b_requires": "F2A completed with clean attribution",
                   "ambiguity": "OWNER_AMBIGUITY_GATE; do not submit F2B "
                                "after ambiguity"},
        "canonical_promotion": {"in_this_package": 0},
        "candidates": frozen}
    (PKG / "experiment_freeze_v2_006.json").write_text(
        json.dumps(experiment, indent=1, ensure_ascii=False),
        encoding="utf-8")
    for cand in frozen:
        print(json.dumps({"checkpoint": "V2006_P2_PAIR_FROZEN",
                          "candidate": cand["candidate_id"],
                          "identity":
                              cand["generation_semantic_identity"][:16],
                          "chars": cand["creative_body_chars"],
                          "words": cand["creative_body_words"]}))

    # ---- P7: admission ----------------------------------------------------
    receipt = make_experiment_admission_receipt(
        experiment_id="V2-006",
        target_quality_debt_ids=["QD-001"],
        canonical_baseline_sha256=QUALITY_V2_CANONICAL_BASELINE,
        hypothesis="Splitting F2 into commit-to-cross + emerge-far-side "
                   "and using geometry-compatible references will make "
                   "the state transition legible without requiring Veo "
                   "to execute the entire traversal in one clip.",
        variables_changed=["shot decomposition (one clip -> two shots)",
                           "F2B reference strategy (near-side full "
                           "frame -> identity-only)"],
        variables_held_constant=[
            "story meaning", "character identity authority",
            "screen direction", "provider route", "model/wire route",
            "F1/F3 continuity", "total editorial duration 5.6 s"],
        max_generate_budget=2,
        provider_route="the exact currently qualified Flow/Veo route "
                       "(flow_veo / veo_3_1_r2v_lite / project "
                       "93a579b4-834e-435b-8304-5f6682937935 / "
                       "clean-pro-qualified)",
        acceptance_criteria=[
            "F2A A1-A10 ALL hard PASS and F2B B1-B10 ALL hard PASS",
            "pair P1-P10 evaluation only if both pass",
            "IDENTITY must not REGRESS; no HIGH/CRITICAL regression",
            "no aggregate score; worker review advisory",
            "canonical promotion 0; Owner decision required"],
        owner_review_surface="OWNER_REVIEW/V2_006 (BASELINE_F2, F2A, "
                             "F2B, NEW_F2_PAIR, COMPARE_REEL) + atomic-"
                             "pair decision template",
        rollback_plan="not applicable to canonical state: no canonical "
                      "mutation allowed; the pair remains evidence-only "
                      "unless the Owner selects the pair for a future "
                      "promotion-adapter package")
    known = load_frozen_debt_ids(ROOT)
    gate = admission_gate(receipt, known_debt_ids=known)
    if gate["status"] != "ADMITTED":
        raise SystemExit("BLOCKED_INVARIANT")
    (PKG / "experiment_admission_v2_006.json").write_text(
        json.dumps({"version": "experiment-admission-v2-006-v1",
                    "checkpoint": "V2006_P7_ADMISSION_PROVEN",
                    "admission_required_from": ADMISSION_REQUIRED_FROM,
                    "receipt": receipt, "gate_result": gate,
                    "known_debt_ids": known}, indent=1),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2006_P7_ADMISSION_PROVEN",
                      "receipt_id": receipt["receipt_id"]}))
    return 0


def cid_is_a(cand) -> bool:
    return cand["candidate_id"].startswith("F2A-")


if __name__ == "__main__":
    raise SystemExit(main())
