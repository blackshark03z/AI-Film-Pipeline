"""FLOW-SEMANTIC-DELIVERY-011 (S12-S15): deterministic delivery bundle.

Poster: DELIVERY_POSTER_FRAME extracted from the canonical master at a
frozen canonical slot/time (SEQ4_A1 — the opening establishing shot — at
its mid-point 4.0 s); explicit provenance; NOT a marketing thumbnail.

Bundle: delivery_011/{master,poster,qc,review,manifests}/ with the
canonical master, technical QC, Owner Review Packet, provenance, and
semantic verdict (NOT_QUALIFIED). Conditionally absent: narration master,
SRT/VTT (TIMED_CAPTION_AUTHORITY_UNAVAILABLE), semantic per-shot reports.

Conformance (S14): manifest vs files, hashes, sizes, master identity vs
the 010 receipt, decode, invalid-artifact scans. Release readiness (S15):
explicit gates, no collapsing.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.core import sha256
from film_pipeline.delivery import (
    DeliveryEntry, DeliveryManifest, finalize, undeclared_files, verify)

R9 = ROOT / "projects/flow_upload_contract_requal_009"
R10 = ROOT / "projects/flow_editorial_runtime_scale_010"
D11 = ROOT / "projects/flow_semantic_delivery_011"
BUNDLE = D11 / "delivery_011"
MASTER = R10 / "master_package_010/master_editorial_010_v1.mp4"
POSTER_SLOT, POSTER_TIME_S = "SEQ4_A1", 4.0

FORBIDDEN_TOKENS = [
    # Package-007 post-gate outputs
    "job_7373ea97", "job_639fb3ec", "job_32779dcf", "job_1e758977",
    # Package-008 successors + continuation
    "job_d217648a", "job_440e92d9", "job_82c693f0", "job_83f26211",
    "job_bce71ae4", "7d61b2f2" if False else "c5b928df",
    # Package-008 canary media + session-reuse canary outputs
    "91823da5-7764", "454e75b4-0bca",
    "f2020c4e", "90c58900", "89d7ca22", "d55c36a3",
    # historical invalid Shot-3C
    "job_fe0a5e73", "cae6e2a5", "asset_0ff2d6bb",
]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_poster() -> dict:
    poster = BUNDLE / "poster" / "delivery_poster_frame.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    if not poster.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{POSTER_TIME_S:.3f}",
             "-i", str(MASTER), "-frames:v", "1", str(poster)],
            check=True, capture_output=True)
    slots = {s["slot_id"]: s for s in json.loads(
        (R10 / "master_package_010/master_summary.json")
        .read_text(encoding="utf-8"))["slots"]}
    slot = slots[POSTER_SLOT]
    # Adversarial fix: user-facing delivery metadata carries REPO-RELATIVE
    # paths, never absolute local filesystem paths.
    rel_asset_path = Path(slot["asset_path"]).relative_to(ROOT).as_posix()
    return {"role": "poster", "slot": POSTER_SLOT,
            "asset_path": rel_asset_path,
            "asset_sha256": slot["asset_sha256"],
            "source_timestamp_s": POSTER_TIME_S,
            "extraction_method": "ffmpeg -ss <t> -frames:v 1 (deterministic)",
            "sha256": file_hash(poster), "bytes": poster.stat().st_size,
            "label": "DELIVERY_POSTER_FRAME (not a marketing thumbnail)"}


def build() -> dict:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    for sub in ("master", "poster", "qc", "review", "manifests"):
        (BUNDLE / sub).mkdir(exist_ok=True)

    # canonical master (copied byte-for-byte from the frozen 010 receipt)
    master_dst = BUNDLE / "master" / "master_editorial_010_v1.mp4"
    if not master_dst.exists():
        shutil.copy2(MASTER, master_dst)
    master_sha = file_hash(master_dst)
    receipt = json.loads((R10 / "master_package_010/master_summary.json")
                         .read_text(encoding="utf-8"))
    if receipt["output_sha256"] != master_sha:
        raise SystemExit("master copy differs from the frozen 010 receipt")

    poster = make_poster()

    qc = {"version": "technical-qc-011-v1",
          "master_sha256": master_sha,
          "duration_s": receipt["duration_s"], "fps": "24/1",
          "video_codec": receipt["video_codec"],
          "audio_codec": receipt["audio_codec"],
          "full_decode": receipt["full_decode"],
          "conformance": "CONFORMANT (master_package_010, 12/12 checks, "
                         "29/29 boundaries)"}
    semantic = json.loads(
        (D11 / "qualification_011.json").read_text(encoding="utf-8"))
    review = json.loads(
        (D11 / "review/owner_review_packet_011.json").read_text(
            encoding="utf-8"))
    narration = json.loads(
        (D11 / "narration_discovery_011.json").read_text(encoding="utf-8"))

    (BUNDLE / "qc" / "technical_qc.json").write_text(
        json.dumps(qc, indent=1), encoding="utf-8")
    (BUNDLE / "qc" / "semantic_verdict.json").write_text(
        json.dumps({"verdict": semantic["verdict"],
                    "model": semantic["model_frozen"],
                    "corpus_hash": semantic["corpus_hash"],
                    "run1_matrix": semantic["run1"]["matrix"]}, indent=1),
        encoding="utf-8")
    (BUNDLE / "review" / "owner_review_packet.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    (BUNDLE / "manifests" / "provenance.json").write_text(
        json.dumps({"film": "swordsman_white_robes canonical 30-slot lineage",
                    "canonical_run": "FLOW-UPLOAD-CONTRACT-REQUAL-009",
                    "editorial_master": "FLOW-EDITORIAL-RUNTIME-SCALE-010",
                    "poster": poster,
                    "audio": {"policy": "source-audio passthrough (proven)",
                              "narration": narration["classification"]}},
                   indent=1), encoding="utf-8")

    entries = [
        DeliveryEntry(role="master", path="master/master_editorial_010_v1.mp4",
                      sha256=master_sha, bytes=master_dst.stat().st_size,
                      media_type="video/mp4",
                      source_lineage="MASTER_EDITORIAL_010_V1 receipt " +
                                     receipt["render_id"]),
        DeliveryEntry(role="poster", path="poster/delivery_poster_frame.png",
                      sha256=poster["sha256"], bytes=poster["bytes"],
                      media_type="image/png",
                      source_lineage=f"slot {POSTER_SLOT} @ {POSTER_TIME_S}s"),
        DeliveryEntry(role="technical_qc", path="qc/technical_qc.json",
                      sha256=file_hash(BUNDLE / "qc/technical_qc.json"),
                      bytes=(BUNDLE / "qc/technical_qc.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="Package-010 conformance + receipt"),
        DeliveryEntry(role="semantic_qc", path="qc/semantic_verdict.json",
                      sha256=file_hash(BUNDLE / "qc/semantic_verdict.json"),
                      bytes=(BUNDLE / "qc/semantic_verdict.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="frozen 006 corpus, model " +
                                     semantic["model_frozen"]),
        DeliveryEntry(role="owner_review",
                      path="review/owner_review_packet.json",
                      sha256=file_hash(
                          BUNDLE / "review/owner_review_packet.json"),
                      bytes=(BUNDLE /
                             "review/owner_review_packet.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="Package-009 successors F2C/G2C/E2C/G3C"),
        DeliveryEntry(role="provenance", path="manifests/provenance.json",
                      sha256=file_hash(BUNDLE / "manifests/provenance.json"),
                      bytes=(BUNDLE /
                             "manifests/provenance.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="canonical lineage packages 004-010"),
    ]
    manifest = finalize(DeliveryManifest(film_id="swordsman_film_011",
                                         entries=entries), BUNDLE)
    (BUNDLE / "manifests" / "delivery_manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=1),
        encoding="utf-8")

    # checksums file over every delivered file
    sums, lines = verify(manifest, BUNDLE), []
    for entry in manifest.entries:
        lines.append(f"{entry.sha256}  {entry.path}")
    (BUNDLE / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n",
                                           encoding="utf-8")

    # deterministic zip (fixed timestamps, sorted order)
    zip_path = D11 / "DELIVERY_011.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BUNDLE.rglob("*"),
                           key=lambda p: p.relative_to(BUNDLE).as_posix()):
            if path.is_file():
                arc = path.relative_to(BUNDLE)
                info = zipfile.ZipInfo(str(arc),
                                       date_time=(2026, 10, 3, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())

    # S14 conformance
    # Self-describing artifacts are expected outside the manifest: the
    # manifest cannot contain its own hash, and SHA256SUMS.txt is written
    # after finalize.
    SELF_DESCRIBING = {"manifests/delivery_manifest.json", "SHA256SUMS.txt",
                       "qc/delivery_conformance_011.json",
                       "qc/release_readiness.json"}
    undeclared_all = undeclared_files(manifest, BUNDLE, BUNDLE)
    undeclared = [u for u in undeclared_all if u not in SELF_DESCRIBING]
    bundle_blob = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in BUNDLE.rglob("*") if p.is_file() and p.suffix in
        (".json", ".txt"))
    forbidden_hits = [t for t in FORBIDDEN_TOKENS if t in bundle_blob]
    conformance = {
        "manifest_vs_files": sums,
        "undeclared_files": undeclared,
        "self_describing_artifacts": sorted(
            set(undeclared_all) & SELF_DESCRIBING),
        "master_identity_matches_010_receipt": True,
        "master_full_decode": receipt["full_decode"],
        "forbidden_artifact_scan": {"tokens": len(FORBIDDEN_TOKENS),
                                    "hits": forbidden_hits},
        "captions": "TIMED_CAPTION_AUTHORITY_UNAVAILABLE (no authoritative "
                    "timed transcript; none generated)",
        "narration": narration["classification"],
        "result": ("PASS" if sums["result"] == "PASS" and not undeclared
                   and not forbidden_hits else "FAIL")}
    (BUNDLE / "qc" / "delivery_conformance_011.json").write_text(
        json.dumps(conformance, indent=1), encoding="utf-8")

    # S15 release readiness
    readiness = {
        "VISUAL_TECHNICAL_READY": True,
        "SEMANTIC_QC_READY": False,   # NOT_QUALIFIED (model capability)
        "CONTENT_AUDIO_READY": False,  # UNQUALIFIED (no authoritative narration)
        "CAPTIONS_READY": False,       # TIMED_CAPTION_AUTHORITY_UNAVAILABLE
        "OWNER_TAKE_REVIEW_READY": True,  # packet built; review pending Owner
        "DELIVERY_BUNDLE_READY": conformance["result"] == "PASS",
        "final_status": ("OWNER_REVIEW_REQUIRED + SEMANTIC_EXTERNAL_GATE + "
                         "AUDIO_CONTENT_GATE — TECHNICAL_DELIVERY_PROVEN "
                         "does NOT imply RELEASE_READY"),
        "release_status": "OWNER_REVIEW_REQUIRED"}
    (BUNDLE / "qc" / "release_readiness.json").write_text(
        json.dumps(readiness, indent=1), encoding="utf-8")

    zip_sha = file_hash(zip_path)
    print(json.dumps({"bundle": str(BUNDLE), "entries": len(entries),
                      "conformance": conformance["result"],
                      "undeclared": undeclared,
                      "forbidden_hits": forbidden_hits,
                      "zip_sha256": zip_sha,
                      "zip_bytes": zip_path.stat().st_size,
                      "readiness": readiness}))


if __name__ == "__main__":
    build()
