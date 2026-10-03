"""FLOW-WORKER-SEMANTIC-BACKEND-014 (W12-W16): Owner Review Packet V4,
backend replacement contract, deterministic delivery_014 with the worker
semantic receipts labeled PROVISIONAL_OWNER_ASSIST, readiness profile.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.delivery import (
    DeliveryEntry, DeliveryManifest, finalize, undeclared_files, verify)

D13 = ROOT / "projects/flow_gemini25_final_qual_013"
D14 = ROOT / "projects/flow_worker_semantic_backend_014"
BUNDLE = D14 / "delivery_014"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010/master_editorial_010_v1.mp4")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    for sub in ("master", "poster", "qc", "review", "manifests"):
        (BUNDLE / sub).mkdir(exist_ok=True)

    receipt = json.loads((R10 := ROOT /
                          "projects/flow_editorial_runtime_scale_10" +
                          "0/master_package_010/master_summary.json")
                         .read_text(encoding="utf-8")) if False else \
        json.loads((ROOT / "projects/flow_editorial_runtime_scale_010/"
                    "master_package_010/master_summary.json")
                   .read_text(encoding="utf-8"))

    master_dst = BUNDLE / "master" / "master_editorial_010_v1.mp4"
    if not master_dst.exists():
        shutil.copy2(MASTER, master_dst)
    master_sha = file_hash(master_dst)
    if receipt["output_sha256"] != master_sha:
        raise SystemExit("master copy differs from the frozen 010 receipt")

    poster = BUNDLE / "poster" / "delivery_poster_frame.png"
    if not poster.exists():
        shutil.copy2(D13 / "delivery_013/poster/delivery_poster_frame.png",
                     poster)

    packet13 = json.loads((D13 / "owner_review_packet_013.json")
                          .read_text(encoding="utf-8"))
    qual = json.loads((D14 / "worker_qualification_receipt_014.json")
                      .read_text(encoding="utf-8"))
    production = json.loads((D14 / "worker_production_review_014.json")
                            .read_text(encoding="utf-8"))
    master_report = json.loads((D14 / "master_worker_semantic_report_014.json")
                               .read_text(encoding="utf-8"))
    consistency = json.loads((D14 / "semantic_review_consistency_014.json")
                             .read_text(encoding="utf-8"))
    policy = json.loads((D14 / "temporary_backend_policy_014.json")
                        .read_text(encoding="utf-8"))
    narration_req = json.loads(
        (D13 / "narration_production_requirement_013.json").read_text(
            encoding="utf-8"))
    caption_req = json.loads(
        (D13 / "caption_production_requirement_013.json").read_text(
            encoding="utf-8"))

    packet = {
        "version": "owner-review-packet-014-v1",
        "entries": packet13["entries"],
        "worker_semantic_context": {
            "backend": qual["backend"],
            "classification": qual["classification"],
            "pass1_matrix": qual["pass1"]["matrix"],
            "provisional_label": "PROVISIONAL_OWNER_ASSIST_REVIEW",
            "production_review": {"shots": production["shots_reviewed"],
                                  "fails": production["fails"]},
            "master_review": {"boundaries":
                              master_report["boundaries_reviewed"],
                              "findings": master_report["findings"]},
            "consistency": {"conflicts": consistency["conflicts"],
                            "outcome": consistency["outcome"]}},
        "narration_gate": "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED",
        "caption_gate": "TIMED_CAPTION_AUTHORITY_UNAVAILABLE",
        "no_auto_approval": ("worker review is provisional Owner-assist; "
                             "artistic quality approval is reserved to the "
                             "Owner")}
    (BUNDLE / "review" / "owner_review_packet.json").write_text(
        json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")

    replacement_contract = {
        "version": "semantic-backend-replacement-contract-014-v1",
        "location": "docs/architecture/SEMANTIC_BACKEND_REPLACEMENT_"
                    "CONTRACT.md",
        "request_schema": "SemanticQCRequest (provider-neutral)",
        "observation_schema": "ProvenancedObservation (provider-neutral, "
                              "full provenance)",
        "qualification_corpus": "flow_semantic_qualify_006/frozen (18 "
                                "controls, hash-recorded)",
        "acceptance": "original frozen Package-006 A-L",
        "repeatability": "two independent passes + stability",
        "cross_backend_comparison": "shadow review on the canonical review "
                                    "set with a discrepancy report",
        "rollout": "adapter qualification -> shadow review -> discrepancy "
                   "report -> API promote -> worker remains fallback",
        "rollback": "active backend flag reverts to WORKER; historical "
                    "observations never rewritten",
        "cache_isolation": "cache keyed by (backend_type, backend_id, "
                           "backend_version, model, rubric_fingerprint)",
        "authority": "no semantic review result grants provider mutation "
                     "authority"}
    (BUNDLE / "manifests" / "backend_replacement_contract.json").write_text(
        json.dumps(replacement_contract, indent=1), encoding="utf-8")
    (BUNDLE / "manifests" / "narration_production_requirement_013.json") \
        .write_text(json.dumps(narration_req, indent=1), encoding="utf-8")
    (BUNDLE / "manifests" / "caption_production_requirement_013.json") \
        .write_text(json.dumps(caption_req, indent=1), encoding="utf-8")

    qc = {"version": "technical-qc-014-v1", "master_sha256": master_sha,
          "duration_s": receipt["duration_s"], "fps": "24/1",
          "video_codec": receipt["video_codec"],
          "audio_codec": receipt["audio_codec"],
          "full_decode": receipt["full_decode"],
          "conformance": "CONFORMANT (master_package_010)"}
    (BUNDLE / "qc" / "technical_qc.json").write_text(
        json.dumps(qc, indent=1), encoding="utf-8")

    provenance = {
        "film": "swordsman_white_robes canonical 30-slot lineage",
        "canonical_run": "FLOW-UPLOAD-CONTRACT-REQUAL-009",
        "editorial_master": "FLOW-EDITORIAL-RUNTIME-SCALE-010",
        "poster": {"slot": "SEQ4_A1", "timestamp_s": 4.0,
                   "sha256": file_hash(poster)},
        "semantic": {"backend": policy["active_semantic_backend"],
                     "worker_classification": qual["classification"],
                     "gemini_line": "NO_FURTHER_GEMINI_QUALIFICATION "
                                    "(Owner decision, 013)"}}
    (BUNDLE / "manifests" / "provenance.json").write_text(
        json.dumps(provenance, indent=1), encoding="utf-8")

    # Copy worker semantic receipts into the bundle.
    for src_name, dst_name in (
            ("worker_qualification_receipt_014.json",
             "worker_qualification_receipt.json"),
            ("worker_production_review_014.json",
             "worker_production_review.json"),
            ("master_worker_semantic_report_014.json",
             "master_worker_semantic_report.json"),
            ("semantic_review_consistency_014.json",
             "semantic_review_consistency.json")):
        shutil.copy2(D14 / src_name, BUNDLE / "qc" / dst_name)

    entries = [
        DeliveryEntry(role="master", path="master/master_editorial_010_v1.mp4",
                      sha256=master_sha, bytes=master_dst.stat().st_size,
                      media_type="video/mp4",
                      source_lineage="MASTER_EDITORIAL_010_V1 receipt " +
                                     receipt["render_id"]),
        DeliveryEntry(role="poster", path="poster/delivery_poster_frame.png",
                      sha256=file_hash(poster), bytes=poster.stat().st_size,
                      media_type="image/png", source_lineage="SEQ4_A1 @ 4s"),
        DeliveryEntry(role="technical_qc", path="qc/technical_qc.json",
                      sha256=file_hash(BUNDLE / "qc/technical_qc.json"),
                      bytes=(BUNDLE / "qc/technical_qc.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="Package-010 conformance"),
        DeliveryEntry(role="semantic_qc",
                      path="qc/worker_qualification_receipt.json",
                      sha256=file_hash(D14 /
                          "worker_qualification_receipt_014.json"),
                      bytes=(D14 /
                             "worker_qualification_receipt_014.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="PROVISIONAL_SINGLE_PASS (same-session "
                                     "reviewer; 006 frozen corpus)"),
        DeliveryEntry(role="semantic_qc",
                      path="qc/worker_production_review.json",
                      sha256=file_hash(D14 /
                          "worker_production_review_014.json"),
                      bytes=(D14 /
                             "worker_production_review_014.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="PROVISIONAL_OWNER_ASSIST_REVIEW of "
                                     "the canonical 30 shots"),
        DeliveryEntry(role="semantic_qc",
                      path="qc/master_worker_semantic_report.json",
                      sha256=file_hash(D14 /
                          "master_worker_semantic_report_014.json"),
                      bytes=(D14 /
                             "master_worker_semantic_report_014.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="MASTER_EDITORIAL_010_V1 boundary "
                                     "review"),
        DeliveryEntry(role="semantic_qc",
                      path="qc/semantic_review_consistency.json",
                      sha256=file_hash(D14 /
                          "semantic_review_consistency_014.json"),
                      bytes=(D14 /
                             "semantic_review_consistency_014.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="W11 consistency audit"),
        DeliveryEntry(role="owner_review",
                      path="review/owner_review_packet.json",
                      sha256=file_hash(
                          BUNDLE / "review/owner_review_packet.json"),
                      bytes=(BUNDLE /
                             "review/owner_review_packet.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="Package-014 consolidated packet"),
        DeliveryEntry(role="provenance", path="manifests/provenance.json",
                      sha256=file_hash(BUNDLE / "manifests/provenance.json"),
                      bytes=(BUNDLE /
                             "manifests/provenance.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="canonical lineage packages 004-010"),
        DeliveryEntry(role="narration_requirement",
                      path="manifests/narration_production_requirement_013.json",
                      sha256=file_hash(BUNDLE /
                          "manifests/narration_production_requirement_013.json"),
                      bytes=(BUNDLE / "manifests/"
                             "narration_production_requirement_013.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="R9/013 narration gate"),
        DeliveryEntry(role="caption_requirement",
                      path="manifests/caption_production_requirement_013.json",
                      sha256=file_hash(BUNDLE /
                          "manifests/caption_production_requirement_013.json"),
                      bytes=(BUNDLE / "manifests/"
                             "caption_production_requirement_013.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="R10/013 caption gate"),
        DeliveryEntry(role="backend_contract",
                      path="manifests/backend_replacement_contract.json",
                      sha256=file_hash(BUNDLE /
                          "manifests/backend_replacement_contract.json"),
                      bytes=(BUNDLE / "manifests/"
                             "backend_replacement_contract.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="W13 API replacement contract"),
    ]
    manifest = finalize(DeliveryManifest(film_id="swordsman_film_014",
                                         entries=entries), BUNDLE)
    (BUNDLE / "manifests" / "delivery_manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=1),
        encoding="utf-8")
    sums = verify(manifest, BUNDLE)
    (BUNDLE / "SHA256SUMS.txt").write_text(
        "\n".join(f"{e.sha256}  {e.path}" for e in manifest.entries) + "\n",
        encoding="utf-8")

    # WORKER-FACING semantic packets must NOT leak hidden qualification
    # labels. The backend replacement CONTRACT legitimately references the
    # acceptance as a future procedure — it is not a reviewer packet, so
    # the scan covers the review/ directory only.
    label_leak = []
    for path in (BUNDLE / "review").rglob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        for leak in ('"expected_class"', '"expected_verdict"',
                     '"pass_target"', '"must_reject_lineage"'):
            if leak in text:
                label_leak.append(f"{path.name}: {leak}")

    self_describing = {"manifests/delivery_manifest.json", "SHA256SUMS.txt",
                       "qc/delivery_conformance_014.json",
                       "qc/release_readiness.json"}
    undeclared_all = undeclared_files(manifest, BUNDLE, BUNDLE)
    undeclared = [u for u in undeclared_all if u not in self_describing]
    conformance = {
        "manifest_vs_files": sums,
        "undeclared_files": undeclared,
        "self_describing_artifacts": sorted(
            set(undeclared_all) & self_describing),
        "master_identity_matches_010_receipt": True,
        "master_full_decode": receipt["full_decode"],
        "hidden_label_leak_scan": {"hits": label_leak},
        "provisional_label_correct":
            "PROVISIONAL_OWNER_ASSIST_REVIEW" in json.dumps(packet) and
            "SEMANTIC_QC_QUALIFIED" not in json.dumps(packet),
        "result": ("PASS" if sums["result"] == "PASS" and not undeclared and
                   not label_leak else "FAIL")}
    (BUNDLE / "qc" / "delivery_conformance_014.json").write_text(
        json.dumps(conformance, indent=1), encoding="utf-8")

    readiness = {
        "VISUAL_TECHNICAL_READY": True,
        "UPLOAD_CONTRACT_READY": True,
        "EDITORIAL_READY": True,
        "DELIVERY_BUNDLE_READY": conformance["result"] == "PASS",
        "SEMANTIC_BACKEND_AVAILABLE": "provisional (worker; PROVISIONAL_"
                                      "SINGLE_PASS)",
        "SEMANTIC_AUTONOMOUS_READY": False,
        "WORKER_REVIEW_COMPLETE": True,
        "OWNER_TAKE_REVIEW_COMPLETE": False,
        "CONTENT_AUDIO_READY": False,
        "TIMED_CAPTIONS_READY": False,
        "release_profile": {
            "TECHNICAL_FILM_ASSET_RELEASE": "READY",
            "FINAL_CONTENT_RELEASE": "GATED (semantic backend provisional + "
                                     "narration + captions + Owner review)"},
        "release_status": "OWNER_REVIEW_REQUIRED"}
    (BUNDLE / "qc" / "release_readiness.json").write_text(
        json.dumps(readiness, indent=1), encoding="utf-8")

    zip_path = D14 / "DELIVERY_014.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BUNDLE.rglob("*"),
                           key=lambda p: p.relative_to(BUNDLE).as_posix()):
            if path.is_file():
                info = zipfile.ZipInfo(
                    str(path.relative_to(BUNDLE)),
                    date_time=(2026, 10, 4, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    print(json.dumps({"entries": len(entries), "conformance":
                      conformance["result"], "undeclared": undeclared,
                      "label_leaks": label_leak,
                      "zip_sha256": file_hash(zip_path),
                      "readiness": readiness}))


if __name__ == "__main__":
    main()
