"""AI-FILM-QUALITY-V2-002 — Phase 5: register the planned renders as
PROPOSED candidates against QD-001.

The governed QualityRepairCandidate (quality_repair_v2) derives its id
from the EXACT asset sha256, which does not exist until acquisition.
This phase therefore registers the planned renders with a clearly
marked deterministic placeholder asset sha; at custody update (Phase
6/7) the governed candidate is minted against the real acquired sha and
the mapping planned_render_id -> candidate_id is recorded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import sha256

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"

CANONICAL_F2_TAKE = "take_91e4997b99432358ec713c072ef3a82571f65b6b43a4a48fab8cfa17f31efb67"


def main() -> int:
    freeze = json.loads((PKG / "experiment_freeze_v2_002.json").read_text(
        encoding="utf-8"))
    registry = {"version": "quality-v2-002-planned-renders-v1",
                "checkpoint": "V2002_P5_CANDIDATES_REGISTERED",
                "repair_reason": "ACTION_CAUSALITY_REDESIGN",
                "quality_debt_ids": ["QD-001"],
                "source_canonical_take": CANONICAL_F2_TAKE,
                "initial_state": "PROPOSED",
                "note": "no candidate can be OWNER_SELECTED yet; the "
                        "governed QualityRepairCandidate is minted at "
                        "custody update once the real asset sha256 "
                        "exists (asset_sha256 here is a marked "
                        "placeholder, never a real render)",
                "planned_renders": []}
    for cand in freeze["candidates"]:
        semantic_fingerprint = sha256({
            "candidate_id": cand["candidate_id"],
            "action_intent_digest": cand["action_intent_digest"],
            "performance_spec_digest": cand["performance_spec_digest"],
            "creative_body": cand["creative_body"],
            "fixture_sha256": cand["fixture_sha256"]})
        placeholder_sha = sha256({"placeholder_for": cand["candidate_id"],
                                  "semantic_fingerprint":
                                      semantic_fingerprint})
        registry["planned_renders"].append({
            "planned_render_id": "PR-" + sha256(
                {"planned": cand["candidate_id"]})[:12],
            "candidate_id": cand["candidate_id"],
            "shot_id": cand["shot_id"],
            "source_canonical_take": CANONICAL_F2_TAKE,
            "affected_shot": "SEQ7_F2C",
            "quality_debt_ids": ["QD-001"],
            "semantic_fingerprint": semantic_fingerprint,
            "asset_sha256_placeholder": placeholder_sha,
            "asset_sha256": None,
            "state": "PROPOSED",
            "governed_candidate_id": None,
            "budget_note": "at most ONE Generate submission each; "
                           "MAX 2 total; no retry"})
    (PKG / "planned_renders_v2_002.json").write_text(
        json.dumps(registry, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P5_CANDIDATES_REGISTERED",
                      "count": len(registry["planned_renders"]),
                      "renders": [r["planned_render_id"] for r in
                                  registry["planned_renders"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
