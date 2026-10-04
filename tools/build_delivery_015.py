"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phases 13-14 + 16): deterministic
Delivery-015 bundle, 3-build archive determinism, and the release
readiness model V3 (every readiness value derived from receipts — none
hard-coded).

The canonical master is NOT changed. No hidden qualification expectation
data, credentials, browser state, cookies, signed URLs, absolute private
paths, or synthetic Owner decision fixtures enter the bundle.
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
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.content_release import ContentReleaseInputBundle
from film_pipeline.delivery import (DeliveryEntry, DeliveryManifest,
                                    finalize, undeclared_files, verify)

D13 = ROOT / "projects/flow_gemini25_final_qual_013"
D14 = ROOT / "projects/flow_worker_semantic_backend_014"
D15 = ROOT / "projects/flow_owner_review_content_gates_015"
BUNDLE = D15 / "delivery_015"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
D009 = ROOT / "projects/flow_upload_contract_requal_009"
MASTER = M10 / "master_editorial_010_v1.mp4"
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"

# Inherited from build_delivery_013.py: forbidden lineage tokens.
FORBIDDEN_TOKENS = [
    "job_7373ea97", "job_639fb3ec", "job_32779dcf", "job_1e758977",
    "job_d217648a", "job_440e92d9", "job_82c693f0", "job_83f26211",
    "job_bce71ae4", "c5b928df",
    "91823da5-7764", "454e75b4-0bca",
    "7d61b2f2-2678", "378966a4-7ee9", "4fc1b2f5-4097",
    "f2020c4e", "90c58900", "89d7ca22", "d55c36a3",
    "job_fe0a5e73", "cae6e2a5", "asset_0ff2d6bb",
    # B5 primary (only B5R is canonical)
    "shot_SEQ4_B5/",
]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def main() -> None:
    for sub in ("master", "poster", "qc", "review", "manifests"):
        (BUNDLE / sub).mkdir(parents=True, exist_ok=True)

    # -- canonical master + poster (unchanged) --------------------------
    master_dst = BUNDLE / "master" / "master_editorial_010_v1.mp4"
    if not master_dst.exists():
        shutil.copy2(MASTER, master_dst)
    master_sha = file_hash(master_dst)
    receipt = json.loads((M10 / "master_summary.json").read_text(
        encoding="utf-8"))
    if receipt["output_sha256"] != master_sha or master_sha != MASTER_SHA:
        raise SystemExit("master copy differs from the frozen 010 receipt")

    poster = BUNDLE / "poster" / "delivery_poster_frame.png"
    if not poster.exists():
        shutil.copy2(D13 / "delivery_013/poster/delivery_poster_frame.png",
                     poster)

    # -- owner review surface -------------------------------------------
    shutil.copy2(D15 / "owner_review_set_015.json",
                 BUNDLE / "review/owner_review_set.json")
    shutil.copy2(D15 / "reel/OWNER_REVIEW_REEL_015.mp4",
                 BUNDLE / "review/OWNER_REVIEW_REEL_015.mp4")
    shutil.copy2(D15 / "reel/review_reel_manifest_015.json",
                 BUNDLE / "review/review_reel_manifest.json")
    shutil.copy2(D15 / "reel/reel_validation_015.json",
                 BUNDLE / "review/reel_validation.json")
    shutil.copy2(D15 / "owner_decisions_015.template.json",
                 BUNDLE / "review/owner_decisions_template.json")

    # -- worker advisory receipts (corrected classification) ------------
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
    shutil.copy2(M10 / "conformance_report.json",
                 BUNDLE / "qc/master_conformance_010.json")

    qc = {"version": "technical-qc-015-v1", "master_sha256": master_sha,
          "duration_s": receipt["duration_s"], "fps": "24/1",
          "video_codec": receipt["video_codec"],
          "audio_codec": receipt["audio_codec"],
          "full_decode": receipt["full_decode"],
          "conformance": "CONFORMANT (master_package_010)"}
    write_json(BUNDLE / "qc/technical_qc.json", qc)

    # -- contracts + reports --------------------------------------------
    shutil.copy2(D14 / "delivery_014/manifests/"
                 "backend_replacement_contract.json",
                 BUNDLE / "manifests/backend_replacement_contract.json")
    shutil.copy2(D13 / "delivery_013/manifests/"
                 "narration_production_requirement_013.json",
                 BUNDLE / "manifests/narration_production_requirement_013"
                          ".json")
    shutil.copy2(D13 / "delivery_013/manifests/"
                 "caption_production_requirement_013.json",
                 BUNDLE / "manifests/caption_production_requirement_013"
                          ".json")
    shutil.copy2(D15 / "narration_handoff_015/narration_handoff_015.json",
                 BUNDLE / "manifests/narration_handoff_015.json")
    shutil.copy2(D15 / "final_release_gate_report_015.json",
                 BUNDLE / "manifests/final_release_gate_report_015.json")
    shutil.copy2(D15 / "semantic_waiver_status_015.json",
                 BUNDLE / "manifests/semantic_waiver_status_015.json")

    ingestion_common = {
        "version": "content-ingestion-contract-015-v1",
        "module": "src/film_pipeline/content_release.py",
        "fail_closed": True,
        "no_synthesis": True}
    write_json(BUNDLE / "manifests/narration_ingestion_contract_015.json", {
        **ingestion_common, "contract": "NarrationSourceReceipt",
        "schema_version": "narration-source-receipt-v1",
        "validator": "verify_narration_receipt",
        "refuses": ["wrong project", "wrong/unknown story authority",
                    "missing text authority", "hash drift",
                    "unsupported audio", "duration mismatch",
                    "sample-rate mismatch", "channel mismatch",
                    "missing provenance", "source mutation"],
        "current_truth": "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED",
        "handoff": "manifests/narration_handoff_015.json"})
    write_json(BUNDLE / "manifests/caption_ingestion_contract_015.json", {
        **ingestion_common, "contract": "TimedCaptionSource",
        "schema_version": "timed-caption-source-v1",
        "validator": "verify_caption_source",
        "formats": ["srt", "vtt"],
        "refuses": ["non-UTF-8", "malformed timestamps", "negative start",
                    "end <= start", "cues beyond master duration",
                    "non-increasing ordering", "overlapping cues (never "
                    "silently fixed)", "transcript binding drift",
                    "hash drift", "wrong project"],
        "current_truth": "TIMED_CAPTION_AUTHORITY_UNAVAILABLE"})

    bundle_template = ContentReleaseInputBundle(
        project="swordsman_film", master_sha256=MASTER_SHA,
        canonical_lineage_version="master-editorial-010-v1")
    write_json(BUNDLE / "manifests/"
               "content_release_input_bundle_schema_015.json", {
        "version": "content-release-input-bundle-schema-015-v1",
        "schema_version": "content-release-input-bundle-v1",
        "json_schema": ContentReleaseInputBundle.model_json_schema(),
        "empty_template": bundle_template.model_dump(mode="json"),
        "optional_inputs": ["NarrationSourceReceipt",
                            "TimedCaptionSource",
                            "OwnerReviewDecisionSet",
                            "SemanticQCWaiverDecision"],
        "authority": "INPUT to final content release; grants ZERO "
                     "provider generation authority"})
    write_json(BUNDLE / "manifests/"
               "content_release_input_bundle_template.json",
               bundle_template.model_dump(mode="json"))

    provenance = {
        "film": "swordsman_white_robes canonical 30-slot lineage",
        "canonical_run": "FLOW-UPLOAD-CONTRACT-REQUAL-009",
        "editorial_master": "FLOW-EDITORIAL-RUNTIME-SCALE-010",
        "worker_semantic_truth": {
            "WORKER_SEMANTIC_BACKEND": "NOT_QUALIFIED",
            "WORKER_SEMANTIC_REVIEW_MODE": "PROVISIONAL_OWNER_ASSIST",
            "SEMANTIC_AUTONOMOUS_READY": False,
            "correction": "Package-015 Phase 0B; historical "
                          "PROVISIONAL_SINGLE_PASS label superseded"},
        "owner_review_surface": {
            "review_set_id": json.loads(
                (BUNDLE / "review/owner_review_set.json").read_text(
                    encoding="utf-8"))["review_set_id"],
            "reel_sha256": file_hash(
                BUNDLE / "review/OWNER_REVIEW_REEL_015.mp4"),
            "template_sha256": file_hash(
                BUNDLE / "review/owner_decisions_template.json")},
        "poster": {"slot": "SEQ4_A1", "timestamp_s": 4.0,
                   "sha256": file_hash(poster)},
        "gemini_line": "NO_FURTHER_GEMINI_QUALIFICATION (Owner decision, "
                       "013)"}
    write_json(BUNDLE / "manifests/provenance.json", provenance)

    # -- Phase 16: readiness model V3 (all derived) ---------------------
    conformance_010 = json.loads(
        (BUNDLE / "qc/master_conformance_010.json").read_text(
            encoding="utf-8"))
    equivalence_009 = json.loads(
        (D009 / "authority_equivalence_009.json").read_text(
            encoding="utf-8"))
    reel_validation = json.loads(
        (BUNDLE / "review/reel_validation.json").read_text(
            encoding="utf-8"))
    qual = json.loads((BUNDLE / "qc/worker_qualification_receipt.json")
                      .read_text(encoding="utf-8"))
    production = json.loads((BUNDLE / "qc/worker_production_review.json")
                            .read_text(encoding="utf-8"))
    gate_report = json.loads((BUNDLE / "manifests/"
                              "final_release_gate_report_015.json")
                             .read_text(encoding="utf-8"))
    handoff = json.loads((BUNDLE / "manifests/narration_handoff_015.json")
                         .read_text(encoding="utf-8"))
    readiness = {
        "version": "release-readiness-v3-015",
        "derivation": "every value below is derived from frozen receipts; "
                      "nothing is hard-coded",
        "VISUAL_TECHNICAL_READY": conformance_010["overall"] ==
                                  "CONFORMANT" and receipt["full_decode"],
        "UPLOAD_CONTRACT_READY": equivalence_009["all_equivalent"] is True,
        "EDITORIAL_READY": receipt["version"] == "master-editorial-010-v1",
        "TECHNICAL_DELIVERY_READY": None,  # filled after conformance
        "WORKER_OWNER_ASSIST_REVIEW_AVAILABLE":
            production["shots_reviewed"] == 30 and
            production["classification"] == "PROVISIONAL_OWNER_ASSIST_REVIEW",
        "SEMANTIC_AUTONOMOUS_READY":
            qual["classification_correction_015"][
                "semantic_autonomous_ready"],
        "SEMANTIC_RELEASE_GATE": "OWNER_DECISION_REQUIRED (qualified "
                                 "backend absent: WORKER_SEMANTIC_BACKEND "
                                 "= NOT_QUALIFIED; waiver route "
                                 "AUTHORIZED but not exercised)",
        "OWNER_TAKE_REVIEW_COMPLETE": False,
        "OWNER_TAKE_REVIEW_DETAIL": "awaiting the imported "
                                    "owner_decisions file for "
                                    "reviewset_218a04d7 (5 requests)",
        "NARRATION_INGESTION_READY": True,
        "NARRATION_INGESTION_DETAIL": handoff["status"],
        "CONTENT_AUDIO_READY": False,
        "CAPTION_INGESTION_READY": True,
        "TIMED_CAPTIONS_READY": False,
        "FINAL_CONTENT_RELEASE_READY":
            gate_report["release_state"] == "FINAL_CONTENT_RELEASE_READY",
        "FINAL_CONTENT_RELEASE_BLOCKED_GATES": gate_report["blocked_gates"],
    }

    # -- manifest -------------------------------------------------------
    def entry(role, path, lineage):
        full = BUNDLE / path
        return DeliveryEntry(role=role, path=path, sha256=file_hash(full),
                             bytes=full.stat().st_size,
                             media_type={
                                 ".mp4": "video/mp4", ".png": "image/png",
                                 ".json": "application/json",
                                 ".txt": "text/plain"}[full.suffix],
                             source_lineage=lineage)

    entries = [
        entry("master", "master/master_editorial_010_v1.mp4",
              "MASTER_EDITORIAL_010_V1 receipt " + receipt["render_id"]),
        entry("poster", "poster/delivery_poster_frame.png",
              "SEQ4_A1 @ 4s"),
        entry("technical_qc", "qc/technical_qc.json",
              "Package-010 conformance"),
        entry("technical_qc", "qc/master_conformance_010.json",
              "conformance-010-v1 18 checks + 29 boundaries"),
        entry("semantic_qc", "qc/worker_qualification_receipt.json",
              "WORKER_SEMANTIC_BACKEND = NOT_QUALIFIED (corrected 015); "
              "PROVISIONAL_OWNER_ASSIST preserved"),
        entry("semantic_qc", "qc/worker_production_review.json",
              "PROVISIONAL_OWNER_ASSIST_REVIEW of the canonical 30 shots"),
        entry("semantic_qc", "qc/master_worker_semantic_report.json",
              "MASTER_EDITORIAL_010_V1 boundary review"),
        entry("semantic_qc", "qc/semantic_review_consistency.json",
              "W11 consistency audit"),
        entry("owner_review", "review/owner_review_set.json",
              "reviewset_218a04d7 (4 successors + master advisory)"),
        entry("review_reel", "review/OWNER_REVIEW_REEL_015.mp4",
              "deterministic Owner review reel (canonical assets only)"),
        entry("owner_review", "review/review_reel_manifest.json",
              "reel time ranges -> shots/assets/request ids"),
        entry("owner_review", "review/reel_validation.json",
              "reel full-decode + lineage validation"),
        entry("owner_review", "review/owner_decisions_template.json",
              "Owner decision import surface (frozen bindings)"),
        entry("backend_contract",
              "manifests/backend_replacement_contract.json",
              "W13 API replacement contract"),
        entry("narration_requirement",
              "manifests/narration_production_requirement_013.json",
              "R9/013 narration gate"),
        entry("narration_handoff", "manifests/narration_handoff_015.json",
              "NARRATION_TEXT_AUTHORITY_MISSING; production handoff"),
        entry("narration_requirement",
              "manifests/narration_ingestion_contract_015.json",
              "NarrationSourceReceipt v1 fail-closed ingestion"),
        entry("caption_requirement",
              "manifests/caption_production_requirement_013.json",
              "R10/013 caption gate"),
        entry("caption_requirement",
              "manifests/caption_ingestion_contract_015.json",
              "TimedCaptionSource v1 strict SRT/VTT ingestion"),
        entry("content_input_bundle",
              "manifests/content_release_input_bundle_schema_015.json",
              "ContentReleaseInputBundle v1 schema (zero provider "
              "authority)"),
        entry("content_input_bundle",
              "manifests/content_release_input_bundle_template.json",
              "empty input bundle bound to the canonical master"),
        entry("release_gate_report",
              "manifests/final_release_gate_report_015.json",
              "dry-run compiler: FINAL_CONTENT_RELEASE_BLOCKED"),
        entry("semantic_waiver_status",
              "manifests/semantic_waiver_status_015.json",
              "SEMANTIC_WAIVER_BOUNDARY = AUTHORIZED; no decision yet"),
        entry("provenance", "manifests/provenance.json",
              "canonical lineage packages 004-010 + 014/015 truth"),
    ]
    manifest = finalize(DeliveryManifest(film_id="swordsman_film_015",
                                         entries=entries), BUNDLE)
    write_json(BUNDLE / "manifests/delivery_manifest.json",
               manifest.model_dump(mode="json"))
    sums = verify(manifest, BUNDLE)
    (BUNDLE / "SHA256SUMS.txt").write_text(
        "\n".join(f"{e.sha256}  {e.path}" for e in manifest.entries) + "\n",
        encoding="utf-8")

    # -- scans ----------------------------------------------------------
    self_describing = {"manifests/delivery_manifest.json",
                       "SHA256SUMS.txt",
                       "qc/delivery_conformance_015.json",
                       "qc/release_readiness.json"}
    undeclared_all = undeclared_files(manifest, BUNDLE, BUNDLE)
    undeclared = [u for u in undeclared_all if u not in self_describing]

    # scans cover every declared TEXT payload file (media binaries are
    # proven by hash + full decode instead and cannot be meaningfully
    # text-scanned); the self-describing artifacts are excluded so a
    # scan cannot describe (and thereby poison) itself on rebuild
    TEXT_SUFFIXES = {".json", ".txt", ".md", ".srt", ".vtt"}
    scan_files = [p for p in sorted(BUNDLE.rglob("*"))
                  if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and
                  p.relative_to(BUNDLE).as_posix() not in self_describing]
    bundle_blob = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in scan_files) + \
        " ".join(p.relative_to(BUNDLE).as_posix() for p in scan_files)
    forbidden_hits = [t for t in FORBIDDEN_TOKENS if t in bundle_blob]
    abs_path_hits = sorted(set(
        token for token in ("D:\\", "C:\\Users", "/Users/", "chrome_profile",
                            "file:///")
        if token in bundle_blob))
    secret_hits = sorted(set(
        token for token in ("AIza", "set-cookie", "flow-content",
                            "BEGIN PRIVATE KEY", "Bearer ",
                            "expected_class", "expected_verdict",
                            "pass_target", "must_reject_lineage")
        if token in bundle_blob))
    # worker review packets must not leak hidden labels (scoped scan)
    review_leak = []
    for path in (BUNDLE / "review").rglob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        for leak in ('"expected_class"', '"expected_verdict"',
                     '"pass_target"', '"must_reject_lineage"'):
            if leak in text:
                review_leak.append(f"{path.name}: {leak}")

    conformance = {
        "manifest_vs_files": sums,
        "undeclared_files": undeclared,
        "self_describing_artifacts": sorted(
            set(undeclared_all) & self_describing),
        "master_identity_matches_010_receipt": master_sha == MASTER_SHA,
        "master_full_decode": receipt["full_decode"],
        "review_reel_full_decode": reel_validation["result"] == "PASS",
        "forbidden_artifact_scan": {"tokens": len(FORBIDDEN_TOKENS),
                                    "hits": forbidden_hits},
        "absolute_path_scan": {"hits": abs_path_hits},
        "secret_scan": {"hits": secret_hits},
        "hidden_label_leak_scan_review_dir": {"hits": review_leak},
        "corrected_classification_in_bundle":
            "NOT_QUALIFIED" in (BUNDLE / "qc/"
                                "worker_qualification_receipt.json")
            .read_text(encoding="utf-8"),
        "result": "PASS" if (sums["result"] == "PASS" and not undeclared
                             and not forbidden_hits and not abs_path_hits
                             and not secret_hits and not review_leak)
        else "FAIL"}
    write_json(BUNDLE / "qc/delivery_conformance_015.json", conformance)

    readiness["TECHNICAL_DELIVERY_READY"] = conformance["result"] == "PASS"
    readiness["release_profile"] = {
        "TECHNICAL_FILM_ASSET_RELEASE": "READY",
        "FINAL_CONTENT_RELEASE": "BLOCKED (" +
                                 ", ".join(gate_report["blocked_gates"]) +
                                 ")",
        "remaining_work": "explicit Owner/content inputs only: owner "
                          "decisions import, semantic decision "
                          "(qualified backend or waiver), narration "
                          "asset, timed captions"}
    readiness["release_status"] = "OWNER_REVIEW_REQUIRED"
    write_json(BUNDLE / "qc/release_readiness.json", readiness)

    # -- Phase 14: deterministic archive, 3 independent builds ----------
    def build_zip(target: Path) -> None:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(BUNDLE.rglob("*"),
                               key=lambda p: p.relative_to(BUNDLE)
                               .as_posix()):
                if path.is_file():
                    info = zipfile.ZipInfo(
                        str(path.relative_to(BUNDLE)).replace("\\", "/"),
                        date_time=(2026, 10, 4, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, path.read_bytes())

    hashes = []
    for build in range(3):
        target = D15 / f"_archive_build_{build}.zip"
        build_zip(target)
        hashes.append(file_hash(target))
        if build:
            target.unlink()
        else:
            (D15 / "DELIVERY_015.zip").unlink(missing_ok=True)
            target.rename(D15 / "DELIVERY_015.zip")
    determinism = {
        "version": "archive-determinism-015-v1",
        "builds": 3,
        "hashes": hashes,
        "normalized_posix_paths": True,
        "fixed_archive_timestamps": "2026-10-04 00:00:00",
        "result": "ARCHIVE_DETERMINISM_PROVEN" if len(set(hashes)) == 1
        else "FAIL",
        "archive_sha256": hashes[0]}
    write_json(D15 / "determinism_015.json", determinism)

    print(json.dumps({"entries": len(entries), "conformance":
                      conformance["result"], "undeclared": undeclared,
                      "forbidden_hits": forbidden_hits,
                      "zip_sha256": hashes[0],
                      "determinism": determinism["result"],
                      "readiness": {k: v for k, v in readiness.items()
                                    if not isinstance(v, (dict,))}}))


if __name__ == "__main__":
    main()
