"""FLOW-V1-COMPLETION-QUALITY-DEBT-FREEZE-019 (Phase V11): the small
technical-completion bundle delivery_019 + DELIVERY_019.zip with
3-build determinism. References/hashes only — no experimental videos,
no secrets, no absolute paths.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.delivery import (DeliveryEntry, DeliveryManifest,
                                    finalize, undeclared_files, verify)

D18 = ROOT / "projects/flow_action_intent_causality_018"
D19 = ROOT / "projects/flow_v1_completion_quality_debt_freeze_019"
BUNDLE = D19 / "delivery_019"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                    encoding="utf-8")


def main() -> None:
    for sub in ("receipts", "manifests"):
        (BUNDLE / sub).mkdir(parents=True, exist_ok=True)

    # core artifacts (copies of the frozen 019 records)
    shutil.copy2(ROOT / "docs/operating/"
                 "AI_FILM_PIPELINE_V1_COMPLETION_019.md",
                 BUNDLE / "receipts/v1_completion_receipt.md")
    shutil.copy2(D19 / "v1_pipeline_completeness_019.json",
                 BUNDLE / "receipts/v1_pipeline_completeness_019.json")
    shutil.copy2(D19 / "quality_debt_registry_019.json",
                 BUNDLE / "receipts/quality_debt_registry_019.json")
    shutil.copy2(D19 / "owner_quality_decision_019.json",
                 BUNDLE / "receipts/owner_quality_decision_019.json")
    shutil.copy2(ROOT / "docs/roadmap/"
                 "AI_FILM_QUALITY_HARDENING_V2.md",
                 BUNDLE / "receipts/quality_hardening_v2_roadmap.md")
    shutil.copy2(D19 / "canonical_no_change_019.json",
                 BUNDLE / "receipts/canonical_no_change_019.json")
    shutil.copy2(D19 / "owner_gate_manifest_019_reconciled.json",
                 BUNDLE / "receipts/owner_gate_manifest_019.json")

    readiness = {
        "version": "readiness-axes-019-v1",
        "project": "swordsman_film",
        "pipeline_technical_ready": True,
        "film_creative_quality_accepted": False,
        "final_content_release_ready": False,
        "content_gates": {"OWNER_TAKE_REVIEW": False,
                          "SEMANTIC_RELEASE": False,
                          "PRODUCTION_NARRATION": False,
                          "TIMED_CAPTIONS": False},
        "derived_from": "v1_pipeline_completeness_019.json + "
                        "owner_quality_decision_019.json + "
                        "quality_debt_registry_019.json",
        "invariants": ["quality debt never satisfies a release gate",
                       "technical completion does not imply creative "
                       "acceptance",
                       "creative acceptance does not imply content "
                       "ready",
                       "no aggregate READY boolean exists"]}
    write_json(BUNDLE / "receipts/readiness_profile_019.json", readiness)

    # semantic identity invariant proof receipt
    candidates = []
    for cid, fixture, wire in (
            ("F2C-P017-C", ROOT / "fixtures/requal017/"
             "SEQ7_F2C_P017_C.json", "flow-r2v-performance-compact-v1"),
            ("F2C-P017-D", ROOT / "fixtures/requal017/"
             "SEQ7_G3C_P017_D.json", "flow-r2v-performance-compact-v1"),
            ("F2C-P018-A", ROOT / "fixtures/requal018/"
             "SEQ7_F2C_P018_A.json", "flow-r2v-causal-compact-v1"),
            ("F2C-P018-B", ROOT / "fixtures/requal018/"
             "SEQ7_F2C_P018_B.json", "flow-r2v-causal-compact-v1"),
            ("G3C-P018-C", ROOT / "fixtures/requal018/"
             "SEQ7_G3C_P018_C.json", "flow-r2v-causal-compact-v1")):
        from film_pipeline.core import ShotSpec, canonical_json, sha256
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        shot = ShotSpec.model_validate(payload)
        candidates.append({
            "candidate": cid,
            "shot_spec_sha256": sha256(shot),
            "performance_spec_sha256": sha256(shot.performance_spec),
            "action_intent_sha256": sha256(shot.action_intent)
            if shot.action_intent else None,
            "wire_compiler_version": wire})
    identity = {
        "version": "semantic-identity-invariant-019-v1",
        "mechanism": "option A (live): ActionIntent/PerformanceSpec "
                     "participate directly in sha256(shot) -> plan "
                     "input_hash -> prompt_plan_id -> "
                     "GenerationAttempt.prompt_plan_hash -> "
                     "correlation_evidence; legacy shots without the "
                     "extensions keep historical digests (exclusion)",
        "no_collision": "two semantically different generation requests "
                        "cannot collide (tests/test_semantic_identity_"
                        "019.py: same base + different intent/spec -> "
                        "different identity; identical semantics -> "
                        "deterministic; resume path guard refuses "
                        "differing semantics)",
        "candidate_fingerprints": candidates,
        "custody": "fingerprints computed mechanically from the frozen "
                   "fixtures; they bind candidate provenance and any "
                   "future replay/cache keying"}
    write_json(BUNDLE / "receipts/semantic_identity_invariant_019.json",
               identity)

    # 018 custody closure reference
    custody = {
        "version": "package-018-custody-closure-019-v1",
        "PACKAGE_018_START_SHA": "895ca4cb7d8344f2bedcb0740e695ebfc9a4c"
                                 "259",
        "PACKAGE_018_DELIVERY_SUBJECT_SHA":
            "b127560fc7232797f1a62814f7f05be451b76cdd",
        "PACKAGE_019_BASE_SHA": "c955247b899c3be75999e4bd75ed6119bdbbdb"
                                "6f",
        "full_identities": "appended to "
                           "docs/operating/"
                           "FLOW_ACTION_INTENT_CAUSALITY_018_EVIDENCE.md"
                           " section 14 (job IDs, output identities, "
                           "asset SHAs, prompt SHAs for F2C-P018-A/B, "
                           "G3C-P018-C; pre-mutation local failures "
                           "reproved)",
        "generation_budget": "3/3 consumed, 0 retries, 0 uploads"}
    write_json(BUNDLE / "receipts/package_018_custody_019.json", custody)

    provenance = {
        "film": "swordsman_white_robes canonical 30-slot lineage",
        "canonical_master_sha256":
            "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda17"
            "86595",
        "lineage": "Packages 004-019",
        "freeze_basis": "AI_FILM_V1_TECHNICAL_FREEZE_016 (3494c7b1...) "
                        "stands; this bundle records technical "
                        "COMPLETION, not film acceptance",
        "experimental_assets": "evidence only; referenced by hash, "
                               "never copied here"}
    write_json(BUNDLE / "manifests/provenance.json", provenance)

    def entry(role, path, lineage, media_type="application/json"):
        full = BUNDLE / path
        return DeliveryEntry(role=role, path=path,
                             sha256=file_hash(full),
                             bytes=full.stat().st_size,
                             media_type=media_type,
                             source_lineage=lineage)

    entries = [
        entry("technical_qc", "receipts/v1_completion_receipt.md",
              "V1 completion receipt", "text/plain"),
        entry("technical_qc", "receipts/v1_pipeline_completeness_019.json",
              "25-stage completeness matrix"),
        entry("semantic_qc", "receipts/quality_debt_registry_019.json",
              "QD-001..005 accepted creative defects"),
        entry("owner_review", "receipts/owner_quality_decision_019.json",
              "Owner product decision (quality freeze)"),
        entry("backend_contract",
              "receipts/quality_hardening_v2_roadmap.md",
              "future quality track handoff", "text/plain"),
        entry("technical_qc", "receipts/canonical_no_change_019.json",
              "canonical lineage unchanged proof"),
        entry("owner_review", "receipts/owner_gate_manifest_019.json",
              "remaining external-input gates"),
        entry("technical_qc", "receipts/readiness_profile_019.json",
              "separated readiness axes"),
        entry("backend_contract",
              "receipts/semantic_identity_invariant_019.json",
              "generation semantic identity proof + fingerprints"),
        entry("provenance", "receipts/package_018_custody_019.json",
              "Package-018 custody closure"),
        entry("provenance", "manifests/provenance.json",
              "canonical lineage packages 004-019"),
    ]
    manifest = finalize(DeliveryManifest(film_id="swordsman_film_019",
                                         entries=entries), BUNDLE)
    write_json(BUNDLE / "manifests/delivery_manifest.json",
               manifest.model_dump(mode="json"))
    sums = verify(manifest, BUNDLE)
    (BUNDLE / "SHA256SUMS.txt").write_text(
        "\n".join(f"{e.sha256}  {e.path}" for e in manifest.entries) +
        "\n", encoding="utf-8")

    self_describing = {"manifests/delivery_manifest.json",
                       "SHA256SUMS.txt"}
    undeclared = [u for u in undeclared_files(manifest, BUNDLE, BUNDLE)
                  if u not in self_describing]
    TEXT_SUFFIXES = {".json", ".txt", ".md"}
    blob = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in sorted(BUNDLE.rglob("*"))
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and
        p.relative_to(BUNDLE).as_posix() not in self_describing)
    secret_hits = [t for t in ("AIza", "set-cookie", "BEGIN PRIVATE KEY",
                               "sig=", "expected_verdict")
                   if t in blob]
    abs_hits = [t for t in ("D:\\", "C:\\Users", "/Users/")
                if t in blob]
    stale_hits = [t for t in ("PROVISIONAL_SINGLE_PASS", "job_7373ea97",
                              "asset_0ff2d6bb", "shot_SEQ4_B5/")
                  if t in blob]
    conformance = {
        "manifest_vs_files": sums,
        "undeclared_files": undeclared,
        "secret_scan": {"hits": secret_hits},
        "absolute_path_scan": {"hits": abs_hits},
        "stale_lineage_scan": {"hits": stale_hits},
        "completion_receipt_honesty": "the receipt states "
                                      "FILM_CREATIVE_QUALITY_ACCEPTED = "
                                      "false and never claims the film "
                                      "is finished",
        "result": "PASS" if (sums["result"] == "PASS" and not undeclared
                             and not secret_hits and not abs_hits
                             and not stale_hits) else "FAIL"}
    write_json(BUNDLE / "manifests/delivery_conformance_019.json",
               conformance)

    def build_zip(target: Path) -> None:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(BUNDLE.rglob("*"),
                               key=lambda p: p.relative_to(BUNDLE)
                               .as_posix()):
                if path.is_file():
                    info = zipfile.ZipInfo(
                        str(path.relative_to(BUNDLE)).replace("\\", "/"),
                        date_time=(2026, 10, 4, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, path.read_bytes())

    hashes = []
    for build in range(3):
        t = D19 / f"_build_{build}.zip"
        build_zip(t)
        hashes.append(file_hash(t))
        if build:
            t.unlink()
        else:
            (D19 / "DELIVERY_019.zip").unlink(missing_ok=True)
            t.rename(D19 / "DELIVERY_019.zip")
    determinism = {
        "version": "archive-determinism-019-v1", "builds": 3,
        "hashes": hashes,
        "result": "ARCHIVE_DETERMINISM_PROVEN"
        if len(set(hashes)) == 1 else "FAIL",
        "archive_sha256": hashes[0]}
    write_json(D19 / "determinism_019.json", determinism)
    print(json.dumps({"entries": len(entries),
                      "conformance": conformance["result"],
                      "zip": hashes[0],
                      "determinism": determinism["result"]}))


if __name__ == "__main__":
    main()
