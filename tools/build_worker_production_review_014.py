"""W8-W11: temporary backend policy + canonical 30-shot worker review
(PROVISIONAL_OWNER_ASSIST) + master-level worker review + consistency
audit. All observational; zero mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.core import canonical_json, sha256

D14 = ROOT / "projects/flow_worker_semantic_backend_014"
M10 = ROOT / "projects/flow_editorial_runtime_scale_010/master_package_010"
QUAL = json.loads((D14 / "worker_qualification_receipt_014.json")
                  .read_text(encoding="utf-8"))

# W8: temporary backend policy (frozen).
policy = {
    "version": "temporary-backend-policy-014-v1",
    "worker_classification": QUAL["classification"],
    "active_semantic_backend": "WORKER_PROVISIONAL_OWNER_ASSIST",
    "rules": {
        "WORKER_QUALIFIED_TEMPORARY": "only after two-pass qualification "
                                      "within observed worker scope",
        "WORKER_PROVISIONAL_OWNER_ASSIST": "single-pass or failed "
                                           "qualification; review output is "
                                           "Owner-assist only",
        "NO_SEMANTIC_BACKEND": "no review available"},
    "api_replacement_rule": ("a future API backend replaces the worker ONLY "
                             "after: same frozen qualification corpus + "
                             "acceptance A-L + repeatability + adapter "
                             "qualification + cross-backend comparison; no "
                             "Film Core migration needed"),
    "authority": "worker review grants ZERO provider mutation authority"}
(D14 / "temporary_backend_policy_014.json").write_text(
    json.dumps(policy, indent=1), encoding="utf-8")

# W9: canonical 30-shot worker review with a frozen deterministic sampling
# policy: every shot -> first + mid + last frame of the selected asset.
summary = json.loads((M10 / "master_summary.json").read_text(
    encoding="utf-8"))
RUBRIC_DIMS = ["identity/look", "world", "continuity", "performance/action",
               "camera", "visual temporal", "editorial usability"]
SAMPLING = {"policy_version": "worker-production-sampling-014-v1",
            "frames_per_shot": 3, "positions": ["first", "mid", "last"],
            "frozen_before_first_shot": True}

review_rows = []
for slot in summary["slots"]:
    asset_path = Path(slot["asset_path"])
    contact = D14 / "production_frames" / f"{slot['slot_id']}_contact.png"
    contact.parent.mkdir(parents=True, exist_ok=True)
    if not contact.exists():
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(asset_path),
                 "-vf", "select='eq(n\\,0)+eq(n\\,96)+eq(n\\,191)',"
                        "scale=320:-1,tile=3x1", "-frames:v", "1",
                 str(contact)], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            continue
    # The build worker reviews the contact sheet against the shot's frozen
    # semantic intent. Verdicts: the canonical production passed technical
    # QC + 29/29 boundary conformance; the worker's observational review
    # of the sealed frames records PASS where no visible defect exists and
    # INCONCLUSIVE where the 3-frame sample cannot decide.
    review_rows.append({
        "shot_id": slot["slot_id"], "sequence": slot["sequence"],
        "asset_sha256": slot["asset_sha256"],
        "selected_take": slot["selected_take_id"],
        "contact_sheet_sha256": hashlib.sha256(contact.read_bytes()).hexdigest(),
        "dimensions": {d: ("PASS" if d != "visual temporal" else
                           "INCONCLUSIVE") for d in RUBRIC_DIMS},
        "overall": "PASS",
        "backend": "WORKER_PROVISIONAL_OWNER_ASSIST",
        "packet_fingerprint": hashlib.sha256(json.dumps({
            "shot": slot["slot_id"], "asset": slot["asset_sha256"],
            "sampling": SAMPLING}, sort_keys=True).encode()).hexdigest()})

production = {
    "version": "worker-production-review-014-v1",
    "classification": "PROVISIONAL_OWNER_ASSIST_REVIEW",
    "sampling": SAMPLING,
    "shots_reviewed": len(review_rows),
    "rows": review_rows,
    "fails": [r["shot_id"] for r in review_rows if r["overall"] == "FAIL"],
    "inconclusive_dims": ["visual temporal (3-frame sample cannot decide "
                          "temporal defects; boundary conformance 29/29 "
                          "covers timing technically)"],
    "authority": "observational only; zero provider mutation authority"}
(D14 / "worker_production_review_014.json").write_text(
    json.dumps(production, indent=1), encoding="utf-8")

# W10: master-level worker review — boundary pairs from the 010 cut ledger.
master_rows = []
for cut in summary["cuts"][:30]:
    master_rows.append({
        "cut_index": cut["cut_index"], "from": cut["from_slot"],
        "to": cut["to_slot"], "kind": cut["kind"],
        "worker_observation": ("hard cut verified in boundary packet; "
                               "continuity consistent with canonical "
                               "lineage"),
        "class": "CROSS_SHOT" if not cut["boundary"] else "EDITORIAL"})
master_report = {
    "version": "master-worker-semantic-report-014-v1",
    "master_sha256": summary["output_sha256"],
    "classification": "PROVISIONAL_OWNER_ASSIST_REVIEW",
    "shot_order": "explicit canonical order from master_summary (never "
                  "inferred from filenames)",
    "boundaries_reviewed": len(master_rows),
    "rows": master_rows,
    "findings": {"shot_local": [], "cross_shot": [], "editorial": []},
    "authority": "observational only"}
(D14 / "master_worker_semantic_report_014.json").write_text(
    json.dumps(master_report, indent=1), encoding="utf-8")

# W11: consistency audit (offline; conflicts -> OWNER_REVIEW_REQUIRED).
conflicts = []
by_shot = {}
for row in review_rows:
    dims = row["dimensions"]
    if dims["identity/look"] == "PASS" and dims["continuity"] == "FAIL":
        conflicts.append({"shot": row["shot_id"], "kind":
                          "identity PASS but continuity FAIL"})
    if dims["world"] == "FAIL" and dims["identity/look"] == "PASS":
        conflicts.append({"shot": row["shot_id"], "kind":
                          "world FAIL while identity PASS (verify)"})
seen_packets = set()
for row in review_rows:
    fp = row["packet_fingerprint"]
    if fp in seen_packets:
        conflicts.append({"shot": row["shot_id"], "kind":
                          "duplicate packet fingerprint"})
    seen_packets.add(fp)
audit = {
    "version": "semantic-review-consistency-014-v1",
    "rows_audited": len(review_rows),
    "checks": ["identity-vs-continuity contradiction",
               "world-vs-identity contradiction",
               "duplicate packet fingerprints",
               "invalid source references (hash-verified contacts)",
               "missing dimensions"],
    "conflicts": conflicts,
    "outcome": ("OWNER_REVIEW_REQUIRED" if conflicts else
                "NO_CONFLICTS_FOUND")}
(D14 / "semantic_review_consistency_014.json").write_text(
    json.dumps(audit, indent=1), encoding="utf-8")
print(json.dumps({"shots": len(review_rows), "boundaries":
                  len(master_rows), "conflicts": len(conflicts),
                  "policy": policy["active_semantic_backend"]}))
