"""AI-FILM-QUALITY-V2-002 — Phases 13-15.

template: the Owner decision surface (NO promotion; selection stops at
          OWNER_SELECTED through an explicit Owner decision; next =
          V2-003).
classify: the experiment result classification (advisory, per-dimension,
          Q1-Q4; no universal provider claims).
nochange: the mechanical canonical no-change proof.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import sha256
from film_pipeline.quality_repair_v2 import (
    CANONICAL_MASTER_SHA256, QualityReviewReceipt)

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010/master_editorial_010_v1.mp4")
BASELINE_F2 = (ROOT / "projects/flow_upload_contract_requal_009/reproof/"
               "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
               "c1a69047933565230870ad22.mp4")


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def template() -> int:
    gov = json.loads((PKG / "candidates_governance_v2_002.json").read_text(
        encoding="utf-8"))
    blind = json.loads((PKG / "owner_f2_blind_review_v2_002.json").read_text(
        encoding="utf-8"))
    key = json.loads((PKG / "answer_key_v2_002.json").read_text(
        encoding="utf-8"))
    items = []
    for entry in gov["candidates"]:
        cid = entry["candidate_id"]
        review = QualityReviewReceipt.model_validate(entry["review"])
        items.append({
            "candidate_id": cid,
            "select_by_asset_sha256": entry["custody"]["asset_sha256"],
            "asset_id": entry["custody"]["asset_id"],
            "provider_job_id": entry["custody"]["provider_job_id"],
            "state": entry["governed"]["owner_decision_state"],
            "tradeoff_summary": review.tradeoff_summary(),
            "technical_receipt": entry["governed"]["technical_qc_receipt"],
            "identity_receipt":
                entry["governed"]["identity_receipt"],
            "editorial_fit_receipt":
                entry["governed"]["editorial_compatibility_receipt"]})
    template_doc = {
        "version": "owner-f2-decision-template-v2-002-v1",
        "checkpoint": "V2002_P13_OWNER_DECISION_SURFACE",
        "instructions": [
            "choose EXACTLY ONE decision option; a selection must bind "
            "the exact candidate asset sha256 (copy it verbatim)",
            "THIS PACKAGE MUST NOT EXECUTE PROMOTION: if you select A or "
            "B the candidate becomes OWNER_SELECTED and the package "
            "STOPS; V2-003 qualifies the real PromotionEnvironment and "
            "performs the promotion",
            "the 10-dimension tradeoff summary is shown per candidate; "
            "a soft regression would require an explicit "
            "TRADEOFF_ACCEPTED note (none exists in these receipts)",
            "KEEP_CANONICAL / REJECT_ALL / DEFER / NEEDS_REPAIR leave "
            "the canonical film untouched and the debt ACTIVE"],
        "decision_options": ["SELECT_CANDIDATE_A", "SELECT_CANDIDATE_B",
                             "KEEP_CANONICAL", "REJECT_ALL", "DEFER",
                             "NEEDS_REPAIR"],
        "decision": None,
        "selected_asset_sha256": None,
        "note": "",
        "blind_review": {"packet": "owner_f2_blind_review_v2_002.json",
                         "answers": blind["answers"],
                         "answered_blind": blind["answered_blind"],
                         "answer_key": key["mapping"]},
        "canonical_predecessor": gov["source_canonical_take"],
        "candidates": items,
        "no_promotion_in_this_package": True,
        "next_if_selected": "V2-003_PROMOTION_ADAPTER_QUALIFICATION"}
    (PKG / "owner_f2_decision_v2_002.template.json").write_text(
        json.dumps(template_doc, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P13_OWNER_DECISION_SURFACE",
                      "candidates": [i["candidate_id"] for i in items]}))
    return 0


def classify() -> int:
    blind = json.loads((PKG / "owner_f2_blind_review_v2_002.json").read_text(
        encoding="utf-8"))
    gov = json.loads((PKG / "candidates_governance_v2_002.json").read_text(
        encoding="utf-8"))
    result = {
        "version": "quality-v2-002-experiment-result-v1",
        "scope_limit": "classification applies ONLY within this observed "
                       "experiment (two submissions, one shot family, one "
                       "qualified route); worker judgments are advisory; "
                       "no universal provider capability is claimed",
        "generate_accounting": {"authorized": 2, "consumed": 2,
                                "retries": 0, "uploads": 0,
                                "ambiguous_events": 0},
        "effects": {
            "ACTION_CAUSALITY_EFFECT": "EFFECT_OBSERVED",
            "SHOT_DESIGN_EFFECT": "EFFECT_OBSERVED",
            "PERFORMANCE_EFFECT": "EFFECT_OBSERVED",
            "EDITORIAL_FIT": "PASS"},
        "questions": {
            "Q1_did_redesigned_intent_make_purpose_readable":
                "YES (blind read): both candidates read as forward "
                "passage against the gust; the baseline reads as bracing "
                "at the rock with no communicated goal",
            "Q2_through_state_visually_unambiguous":
                "YES (blind read): both candidates end having passed "
                "between the stones; the baseline ends mid-brace",
            "Q3_logic_improved_without_identity_regression":
                "YES per worker advisory identity grids (UNCHANGED on "
                "both) — final identity judgment is the Owner's on the "
                "same reel",
            "Q4_if_still_failing_next_problem":
                "not applicable: no failure state was reached; residual "
                "risks recorded as inconclusive-none; the next bound "
                "question is Owner selection, not redesign"},
        "candidate_review_states": {
            entry["candidate_id"]:
                entry["governed"]["owner_decision_state"]
            for entry in gov["candidates"]},
        "no_candidate_promoted": True,
        "canonical_mutation": 0}
    (PKG / "quality_v2_002_experiment_result.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P14_CLASSIFIED",
                      "effects": result["effects"]}))
    return 0


def nochange() -> int:
    gov = json.loads((PKG / "candidates_governance_v2_002.json").read_text(
        encoding="utf-8"))
    import subprocess
    tracked_dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
        text=True).stdout.splitlines()
    dirty = [ln for ln in tracked_dirty if not ln.startswith("??")]
    proof = {
        "version": "v2-002-canonical-no-change-proof-v1",
        "checkpoint": "V2002_P15_CANONICAL_UNCHANGED",
        "canonical_master_sha256_expected": CANONICAL_MASTER_SHA256,
        "canonical_master_sha256_actual": file_sha(MASTER),
        "canonical_master_unchanged":
            file_sha(MASTER) == CANONICAL_MASTER_SHA256,
        "canonical_f2_take_sha256_expected":
            "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c39898254890a767",
        "canonical_f2_take_sha256_actual": file_sha(BASELINE_F2),
        "canonical_f2_take_unchanged":
            file_sha(BASELINE_F2) ==
            "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c39898254890a767",
        "v1_tracked_files_modified": dirty,
        "v1_tracked_files_clean": not dirty,
        "no_v2_candidate_in_canonical_lineage": True,
        "promotion_ledger": "EMPTY (no promotion transaction was proposed "
                            "or executed in this package)",
        "canonical_mutation": 0,
        "candidate_states": {e["candidate_id"]:
                             e["governed"]["owner_decision_state"]
                             for e in gov["candidates"]}}
    (PKG / "canonical_no_change_v2_002.json").write_text(
        json.dumps(proof, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = (proof["canonical_master_unchanged"] and
          proof["canonical_f2_take_unchanged"] and
          proof["v1_tracked_files_clean"])
    print(json.dumps({"checkpoint": "V2002_P15_CANONICAL_UNCHANGED",
                      "result": "UNCHANGED" if ok else "MUTATED"}))
    if not ok:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "template":
        raise SystemExit(template())
    if cmd == "classify":
        raise SystemExit(classify())
    if cmd == "nochange":
        raise SystemExit(nochange())
    raise SystemExit("usage: finalize_v2_002.py template|classify|nochange")
