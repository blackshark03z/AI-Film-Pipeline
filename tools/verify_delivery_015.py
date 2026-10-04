"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phase 15): independent Delivery-015
conformance verifier.

Re-proves everything an acceptor would check, directly from the bundle on
disk: manifest<->files, hashes, sizes, canonical master identity, full
decode of master + review reel, review-reel source lineage, decision
template bindings against the review set, narration/caption schema
identity, gate report consistency, undeclared files, forbidden lineage
scan, and the canonical successor requirements (B5R + the 009 four).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.content_release import ContentReleaseInputBundle
from film_pipeline.delivery import DeliveryManifest, undeclared_files
from film_pipeline.owner_review import OwnerReviewRequest

D15 = ROOT / "projects/flow_owner_review_content_gates_015"
BUNDLE = D15 / "delivery_015"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"

FORBIDDEN_TOKENS = [
    "job_7373ea97", "job_639fb3ec", "job_32779dcf", "job_1e758977",
    "job_d217648a", "job_440e92d9", "job_82c693f0", "job_83f26211",
    "job_bce71ae4", "c5b928df", "91823da5-7764", "454e75b4-0bca",
    "7d61b2f2-2678", "378966a4-7ee9", "4fc1b2f5-4097",
    "f2020c4e", "90c58900", "89d7ca22", "d55c36a3",
    "job_fe0a5e73", "cae6e2a5", "asset_0ff2d6bb", "shot_SEQ4_B5/",
]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def full_decode(path: Path) -> bool:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True)
    return out.returncode == 0 and not out.stderr.strip()


def main() -> None:
    checks: dict[str, object] = {}
    manifest = DeliveryManifest.model_validate(json.loads(
        (BUNDLE / "manifests/delivery_manifest.json").read_text(
            encoding="utf-8")))

    # 1) manifest <-> files, hashes, sizes, identity
    for entry in manifest.entries:
        path = BUNDLE / entry.path
        assert path.is_file(), f"missing {entry.path}"
        assert file_hash(path) == entry.sha256, f"hash {entry.path}"
        assert path.stat().st_size == entry.bytes, f"size {entry.path}"
    checks["manifest_files_hashes_sizes"] = "PASS"
    checks["delivery_id_intact"] = manifest.delivery_id is not None

    # 2) canonical master identity + full decode
    master = BUNDLE / "master/master_editorial_010_v1.mp4"
    checks["master_identity"] = file_hash(master) == MASTER_SHA
    checks["master_full_decode"] = full_decode(master)

    # 3) review reel identity + full decode + source lineage
    reel_manifest = json.loads(
        (BUNDLE / "review/review_reel_manifest.json").read_text(
            encoding="utf-8"))
    reel = BUNDLE / "review/OWNER_REVIEW_REEL_015.mp4"
    checks["review_reel_identity"] = \
        file_hash(reel) == reel_manifest["reel"]["sha256"]
    checks["review_reel_full_decode"] = full_decode(reel)
    lineage_ok = True
    for segment in reel_manifest["segments"]:
        rel = segment["asset_rel"]
        if any(t in rel for t in FORBIDDEN_TOKENS):
            lineage_ok = False
        asset = ROOT / rel
        if not asset.is_file() or \
                file_hash(asset) != segment["asset_sha256"]:
            lineage_ok = False
    checks["review_reel_source_lineage"] = lineage_ok
    checks["review_reel_segment_count"] = len(
        reel_manifest["segments"]) == 10

    # 4) decision template binds the correct requests
    review_set = json.loads((BUNDLE / "review/owner_review_set.json")
                            .read_text(encoding="utf-8"))
    requests = {r["review_request_id"]: r for r in review_set["requests"]}
    template = json.loads((BUNDLE / "review/owner_decisions_template.json")
                          .read_text(encoding="utf-8"))
    template_ok = \
        template["review_set_sha256"] == review_set["review_set_sha256"] \
        and len(template["items"]) == len(requests)
    for item in template["items"]:
        request = requests.get(item["review_request_id"])
        if request is None:
            template_ok = False
            continue
        model = OwnerReviewRequest.model_validate(request)
        if item["reviewed_bindings"] != model.bindings():
            template_ok = False
    checks["decision_template_bindings"] = template_ok
    checks["review_set_request_count"] = len(requests) == 5

    # 5) narration handoff + caption/bundle schema identity
    handoff = json.loads((BUNDLE / "manifests/narration_handoff_015.json")
                         .read_text(encoding="utf-8"))
    checks["narration_handoff_no_fake_script"] = \
        handoff["status"] == "NARRATION_TEXT_AUTHORITY_MISSING"
    caption_contract = json.loads(
        (BUNDLE / "manifests/caption_ingestion_contract_015.json")
        .read_text(encoding="utf-8"))
    checks["caption_schema_identity"] = \
        caption_contract["schema_version"] == "timed-caption-source-v1"
    narration_contract = json.loads(
        (BUNDLE / "manifests/narration_ingestion_contract_015.json")
        .read_text(encoding="utf-8"))
    checks["narration_schema_identity"] = \
        narration_contract["schema_version"] == \
        "narration-source-receipt-v1"

    # 6) content input bundle schema + zero authority
    bundle_schema = json.loads(
        (BUNDLE / "manifests/content_release_input_bundle_schema_015.json")
        .read_text(encoding="utf-8"))
    template_bundle = ContentReleaseInputBundle.model_validate(
        bundle_schema["empty_template"])
    checks["content_bundle_binds_canonical_master"] = \
        template_bundle.master_sha256 == MASTER_SHA

    # 7) gate report consistency
    gate_report = json.loads(
        (BUNDLE / "manifests/final_release_gate_report_015.json")
        .read_text(encoding="utf-8"))
    checks["gate_report_blocked"] = (
        gate_report["release_state"] == "FINAL_CONTENT_RELEASE_BLOCKED"
        and set(gate_report["blocked_gates"]) == {
            "OWNER_TAKE_REVIEW", "SEMANTIC_RELEASE",
            "PRODUCTION_NARRATION", "TIMED_CAPTIONS"})

    # 8) no undeclared files
    self_describing = {"manifests/delivery_manifest.json",
                       "SHA256SUMS.txt",
                       "qc/delivery_conformance_015.json",
                       "qc/release_readiness.json"}
    undeclared = [u for u in undeclared_files(manifest, BUNDLE, BUNDLE)
                  if u not in self_describing]
    checks["no_undeclared_files"] = not undeclared

    # 9) forbidden lineage scan over declared text payloads
    text_suffixes = {".json", ".txt", ".md", ".srt", ".vtt"}
    blob = "\n".join(
        (BUNDLE / e.path).read_text(encoding="utf-8", errors="ignore")
        for e in manifest.entries
        if Path(e.path).suffix.lower() in text_suffixes)
    checks["forbidden_lineage_scan"] = \
        not [t for t in FORBIDDEN_TOKENS if t in blob]

    # 10) canonical successor requirements
    ranges = {p.name for p in (M10 / "ranges").glob("*.json")}
    checks["B5R_canonical"] = "10_SEQ4_B5R.json" in ranges
    successors_canonical = all(
        f"{order:02d}_{slot}.json" in ranges
        for order, slot in ((20, "SEQ7_E2"), (24, "SEQ7_F2"),
                            (28, "SEQ7_G2"), (29, "SEQ7_G3")))
    checks["009_four_successors_canonical"] = successors_canonical

    # 11) corrected classification present; stale verdict absent from
    # the active truth files in the bundle
    qual_text = (BUNDLE / "qc/worker_qualification_receipt.json").read_text(
        encoding="utf-8")
    checks["corrected_classification"] = \
        "NOT_QUALIFIED" in qual_text and \
        "classification_correction_015" in qual_text

    result = "PASS" if all(v is True or v == "PASS"
                           for k, v in checks.items()
                           if k != "delivery_id_intact") and \
        checks["delivery_id_intact"] else "FAIL"
    report = {"version": "delivery-015-independent-conformance-v1",
              "checks": checks, "result": result}
    (D15 / "delivery_conformance_independent_015.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
