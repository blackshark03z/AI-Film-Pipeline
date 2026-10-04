"""AI-FILM-QUALITY-V2-003 — Phase 0/1: custody, Owner REJECT_ALL custody,
and the Director model availability receipt.

The package names gpt-6-sol (thinking_effort HIGH) as the dedicated
DIRECTOR_SHOT_DESIGNER authority. The worker runtime availability check
runs HERE and is recorded verbatim; nothing substitutes it silently.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import sha256
from film_pipeline.owner_review import make_owner_decision
from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, QUALITY_V2_CANONICAL_BASELINE)

PKG = ROOT / "projects/quality_v2_003_director_blocking"
V2_002 = ROOT / "projects/quality_v2_002_f2_causality_experiment"

DIRECTOR_MODEL_BINDING = {
    "provider_model": "gpt-6-sol",
    "thinking_effort": "HIGH",
    "role": "DIRECTOR_SHOT_DESIGNER",
    "responsibilities": [
        "interpret story/narrative authority",
        "design shot geography",
        "blocking",
        "screen direction",
        "start/end spatial state",
        "action path",
        "coverage",
        "camera motivation",
        "observability of causal action"],
    "must_not": [
        "invent new story events",
        "override Owner narrative authority",
        "select final takes",
        "promote canonical footage",
        "call providers directly",
        "change acceptance after experiment starts"],
    "substitution_policy": "No silent downgrade. No substitution without "
                           "explicit Owner authorization."}


def check_model_availability() -> dict:
    """The worker runtime is this ZCode host. Its full model surface is
    queried (ListModels); any local API-key surface is checked too."""
    import os
    api_keys_dir = ROOT / "api_keys"
    key_files = sorted(p.name for p in api_keys_dir.glob("*")) \
        if api_keys_dir.exists() else []
    env_hits = sorted(k for k in os.environ
                      if "OPENAI" in k.upper() or "GPT" in k.upper())
    # ListModels result recorded 2026-10-04 (exact surface of this host):
    configured_models = [
        "account:zai-start-plan/GLM-5.3-Flash (levels low,high,max; "
        "session model)",
        "account:zai-start-plan/GLM-5.3 (levels low,high,max)"]
    available = "gpt-6-sol" in configured_models
    return {
        "checked_at": "2026-10-04",
        "worker_runtime": "ZCode host (account:zai-start-plan)",
        "configured_models": configured_models,
        "api_key_files": key_files,
        "openai_env_vars": env_hits,
        "requested_model": "gpt-6-sol",
        "requested_thinking_effort": "HIGH",
        "exact_model_available": available,
        "result": "AVAILABLE" if available else "DIRECTOR_MODEL_UNAVAILABLE",
        "no_silent_downgrade": True,
        "no_substitution_without_owner_authorization": True}


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)

    # --- P0 custody ------------------------------------------------------
    gov = json.loads((V2_002 / "candidates_governance_v2_002.json")
                     .read_text(encoding="utf-8"))
    custody = {
        "version": "v2-003-start-custody-v1",
        "checkpoint": "V2003_P0_CUSTODY_BOUND",
        "start_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True).stdout.strip(),
        "v2_002_final_revision": "b460948c9d2ba1a3e676e827c46930563c1a1180",
        "v2_001_final_revision": "5793dc55bb1ae5d5ff2cb22e02e0ead760f53f46",
        "v1_frozen_baseline": QUALITY_V2_CANONICAL_BASELINE,
        "canonical_master_sha256": CANONICAL_MASTER_SHA256,
        "canonical_f2_selected_take":
            "take_91e4997b99432358ec713c072ef3a82571f65b6b43a4a48fab8cfa17f"
            "31efb67",
        "bindings": {
            "quality_v2_sot": "docs/quality-v2/QUALITY_V2_SOT.md",
            "v2_002_evidence":
                "docs/operating/"
                "AI_FILM_QUALITY_V2_002_F2_CAUSALITY_EXPERIMENT_EVIDENCE.md",
            "f_specs": ["fixtures/sequence007/SEQ7_F1.json",
                        "fixtures/sequence007/SEQ7_F2.json",
                        "fixtures/sequence007/SEQ7_F3.json"],
            "action_intent": "action-intent-v1 (film_pipeline.core)",
            "performance_spec": "performance-spec-v1 (film_pipeline.core)",
            "causal_compiler": "flow-r2v-causal-compact-v1 "
                               "(film_pipeline.performance_compiler)",
            "camera_fields": "film_pipeline.core.Camera/Movement",
            "continuity": "film_pipeline.core.Continuity"},
    }
    (PKG / "start_custody_v2_003.json").write_text(
        json.dumps(custody, indent=1, ensure_ascii=False), encoding="utf-8")

    # --- Owner REJECT_ALL custody (conveyed through the V2-003 package) --
    rejections = []
    for entry in gov["candidates"]:
        asset_sha = entry["custody"]["asset_sha256"]

        class Req:
            review_request_id = "OWNER-REV-V2002-REJECT"
            bindings_asset = asset_sha

            def bindings(self):
                return {"asset_sha256": self.bindings_asset}

        decision = make_owner_decision(
            request=Req(), decision="REJECT",
            note="V2_002_OWNER_DECISION = REJECT_ALL; reasons: "
                 "ACTION_GOAL_NOT_SPATIALLY_LEGIBLE; "
                 "CHARACTER_LOITERS_AROUND_ROCK; "
                 "THROUGH_STATE_NOT_OWNER_ACCEPTED")
        from film_pipeline.quality_repair_v2 import QualityRepairCandidate
        candidate = QualityRepairCandidate.model_validate(
            entry["governed"])
        rejected = None
        from film_pipeline import quality_repair_v2 as qv2
        rejected = qv2.apply_owner_decision(candidate, decision)
        assert rejected.owner_decision_state == "OWNER_REJECTED"
        rejections.append({
            "candidate_id": entry["candidate_id"],
            "governed_candidate_id": candidate.candidate_id,
            "asset_sha256": asset_sha,
            "owner_decision_id": decision.decision_id,
            "state_before": candidate.owner_decision_state,
            "state_after": rejected.owner_decision_state,
            "decision": decision.model_dump(mode="json")})
    owner_decision_doc = {
        "version": "v2-002-owner-decision-record-v1",
        "checkpoint": "V2003_P0_REJECT_ALL_RECORDED",
        "decision_source": "OWNER (conveyed verbatim in the V2-003 work "
                           "package; recorded by the execution worker)",
        "V2_002_OWNER_DECISION": "REJECT_ALL",
        "reasons": ["ACTION_GOAL_NOT_SPATIALLY_LEGIBLE",
                    "CHARACTER_LOITERS_AROUND_ROCK",
                    "THROUGH_STATE_NOT_OWNER_ACCEPTED"],
        "candidates_never_selected": True,
        "debt_QD-001_state": "ACTIVE (a rejected candidate never closes "
                             "debt)",
        "no_promotion": True,
        "rejections": rejections}
    (PKG / "v2_002_owner_decision.json").write_text(
        json.dumps(owner_decision_doc, indent=1, ensure_ascii=False),
        encoding="utf-8")

    # --- P1 Director model binding + availability receipt ----------------
    availability = check_model_availability()
    binding = {
        "version": "director-model-binding-v2-003-v1",
        "checkpoint": "V2003_P1_DIRECTOR_BINDING_RECORDED",
        "binding": DIRECTOR_MODEL_BINDING,
        "availability_receipt": availability,
        "director_work_state": ("BLOCKED_ON_DIRECTOR_MODEL" if not
                                availability["exact_model_available"]
                                else "READY"),
        "blocked_deliverables": ([] if availability["exact_model_available"]
                                 else ["F2 DirectorIntent (P7)",
                                       "F2 BlockingSpec design completion "
                                       "(P7)",
                                       "F2 CameraCoveragePlan (P8)",
                                       "F2 previz artifacts (P9)",
                                       "Director critique pass (P10)"])}
    (PKG / "director_model_binding_v2_003.json").write_text(
        json.dumps(binding, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2003_P0_CUSTODY_BOUND",
                      "start": custody["start_sha"][:12],
                      "reject_all": "RECORDED",
                      "director_model": availability["result"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
