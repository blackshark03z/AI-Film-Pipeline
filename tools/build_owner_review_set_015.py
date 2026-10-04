"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phase 3): freeze the Owner review
set.

Five requests: the four historically mandatory clean successors
(SEQ7_E2/SEQ7_F2/SEQ7_G2/SEQ7_G3, canonical master order) plus the one
real Package-014 advisory item that is INCONCLUSIVE (the systemic
"visual temporal" limitation of the worker's 3-frame sampling, bound at
master level). No fake issues are created; every request binds exact
canonical identities from frozen receipts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import canonical_json, sha256
from film_pipeline.owner_review import OwnerReviewRequest

D14 = ROOT / "projects/flow_worker_semantic_backend_014"
D15 = ROOT / "projects/flow_owner_review_content_gates_015"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"
CREATED_AT = "2026-10-04T00:00:00+00:00"

# canonical slot order -> (shot id, successor spec stem)
TARGETS = [("OWNER-REV-015-001", "SEQ7_E2", "SEQ7_E2C"),
           ("OWNER-REV-015-002", "SEQ7_F2", "SEQ7_F2C"),
           ("OWNER-REV-015-003", "SEQ7_G2", "SEQ7_G2C"),
           ("OWNER-REV-015-004", "SEQ7_G3", "SEQ7_G3C")]


def main() -> None:
    packet = json.loads((D14 / "delivery_014/review/owner_review_packet.json")
                        .read_text(encoding="utf-8"))
    entries = {e["canonical_shot_id"]: e for e in packet["entries"]}
    production = json.loads(
        (D14 / "worker_production_review_014.json").read_text(
            encoding="utf-8"))
    rows = {r["shot_id"]: r for r in production["rows"]}
    master = json.loads((M10 / "master_summary.json").read_text(
        encoding="utf-8"))
    slots = {s["slot_id"]: s for s in master["slots"]}

    requests = []
    for rid, shot, successor in TARGETS:
        entry = entries[shot]
        spec_payload = json.loads(
            (ROOT / "fixtures/requal009" / f"{successor}.json")
            .read_text(encoding="utf-8"))
        spec_sha = sha256(canonical_json(spec_payload))
        row = rows[shot]
        contact = entry["contact_sheet"]
        contact_path = Path(contact["path"])
        rel = contact_path.relative_to(ROOT).as_posix()
        if not contact_path.is_file():
            raise SystemExit(f"contact sheet missing: {rel}")
        import hashlib
        actual = hashlib.sha256(contact_path.read_bytes()).hexdigest()
        if actual != contact["sha256"]:
            raise SystemExit(f"contact sheet hash drift: {rel}")
        advisory = {
            "classification": "PROVISIONAL_OWNER_ASSIST_REVIEW",
            "backend_qualification": "WORKER_SEMANTIC_BACKEND = "
                                     "NOT_QUALIFIED (Package-015 Phase 0B "
                                     "correction; advisory only)",
            "overall": row["overall"],
            "dimensions": row["dimensions"],
            "source": "worker_production_review_014.json row " + shot,
        }
        requests.append(OwnerReviewRequest(
            review_request_id=rid, project="swordsman_film", scope="SHOT",
            canonical_shot_id=shot,
            sequence_id=slots[shot]["sequence"],
            scene_id=slots[shot]["scene"],
            narrative_function=spec_payload["dramatic_purpose"],
            shot_spec_identity={"shot_id": successor,
                                "spec_version": spec_payload["spec_version"],
                                "shot_spec_sha256": spec_sha},
            selected_take=entry["selected_take"],
            asset_id="asset_" + entry["asset_sha256"],
            asset_sha256=entry["asset_sha256"],
            provider_media_identity=entry["provider_output_identity"],
            reference_lineage=entry["reference_lineage"],
            editorial_range=entry["editorial_range"],
            technical_qc=entry["technical_qc"],
            advisory_semantic_review=advisory,
            contact_sheet={"path": rel, "sha256": contact["sha256"]},
            reason_review_required=entry["reason_for_review"],
            created_at=CREATED_AT))

    requests.append(OwnerReviewRequest(
        review_request_id="OWNER-REV-015-005", project="swordsman_film",
        scope="MASTER", master_sha256=MASTER_SHA,
        narrative_function="whole-film temporal quality judgment",
        advisory_semantic_review={
            "classification": "PROVISIONAL_OWNER_ASSIST_REVIEW",
            "item": ("'visual temporal': INCONCLUSIVE on all 30 shots — "
                     "the existing Package-014 advisory INCONCLUSIVE item"),
            "why_master_level": ("systemic 3-frame sampling limitation, "
                                 "not 30 separate shot defects; technical "
                                 "boundary conformance 29/29 already "
                                 "covers timing"),
            "source": "worker_production_review_014.json "
                      "inconclusive_dims"},
        reel_locator={"reel": "OWNER_REVIEW_REEL_015.mp4",
                      "coverage": "full"},
        reason_review_required=("existing Package-014 advisory item is "
                                "INCONCLUSIVE; temporal quality is an "
                                "Owner judgment the worker sample cannot "
                                "decide"),
        created_at=CREATED_AT))

    set_id = "reviewset_" + sha256(canonical_json(
        [r.digest() for r in requests]))
    review_set = {
        "version": "owner-review-set-015-v1",
        "project": "swordsman_film",
        "canonical_master": {"sha256": MASTER_SHA,
                             "version": master["version"]},
        "review_set_id": set_id,
        "review_set_sha256": None,  # filled after serialization below
        "inclusion_policy": (
            "the four historically mandatory clean successors (E2C, F2C, "
            "G2C, G3C) + the only existing Package-014 advisory item that "
            "is FAIL/INCONCLUSIVE/conflict-level (the systemic 'visual "
            "temporal' INCONCLUSIVE, bound at master level). No fake "
            "issues created: 014 production review had 0 FAILs, master "
            "review 0 findings, consistency audit 0 conflicts."),
        "advisory_basis": {
            "reviews_are": "PROVISIONAL_OWNER_ASSIST_REVIEW (advisory "
                           "only; never semantic truth)",
            "worker_semantic_backend": "NOT_QUALIFIED",
            "semantic_autonomous_ready": False},
        "requests": [r.model_dump(mode="json") for r in requests],
    }
    D15.mkdir(parents=True, exist_ok=True)
    out = D15 / "owner_review_set_015.json"
    text = json.dumps(review_set, indent=2, ensure_ascii=False)
    # the file binds its own hash over the payload with review_set_sha256
    # set to the sha of the text with the placeholder empty string — so
    # instead we record the hash of the request payloads only (already
    # covered by review_set_id) and keep the file self-describing.
    review_set["review_set_sha256"] = sha256(canonical_json(
        [r.model_dump(mode="json") for r in requests]))
    out.write_text(json.dumps(review_set, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"review_set_id": set_id, "requests": len(requests),
                      "out": str(out)}))


if __name__ == "__main__":
    main()
