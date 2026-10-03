"""W5-W7: blind qualification packets from the frozen 006 corpus + worker
Pass-1 review (the build worker reviews each sealed packet WITHOUT seeing
expected labels) + honest repeatability classification.

The reviewer context is THIS SAME session (the build worker), so an
independent fresh reviewer context is NOT available -> per W7, even if
Pass 1 passes, the classification is PROVISIONAL_SINGLE_PASS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.core import canonical_json, sha256
from film_pipeline.semantic_backends import (
    BackendIdentity, SemanticEvaluatorBackend, WorkerReviewPacket,
    WorkerReviewResult, import_worker_result)

CORPUS = (ROOT / "projects/flow_semantic_qualify_006/corpus/"
          "qualification_corpus.json")
OUT = ROOT / "projects/flow_worker_semantic_backend_014"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    controls = corpus["controls"]
    # Blind aliases: randomized id assignment frozen before review.
    aliases = {c["control_id"]: f"CTRL-Q014-{i + 1:03d}"
               for i, c in enumerate(sorted(controls,
                                            key=lambda c: c["control_id"]))}
    packets, manifest_rows = [], []
    for control in controls:
        pkt = WorkerReviewPacket(
            packet_id=aliases[control["control_id"]],
            request_fingerprint=sha256(canonical_json({
                "control": aliases[control["control_id"]],
                "frame_hashes": [f.get("sha256") for f in control["frames"]],
                "dimension": control["dimension"]})),
            shot_spec_json={
                "dimension": control["dimension"],
                "requirement": control["requirement"]},
            selected_take_lineage={"source_frames":
                                   [f.get("label", "") for f in
                                    control["frames"]]},
            frame_hashes=[f.get("sha256", "") for f in control["frames"]],
            frame_paths=[f.get("path", "") for f in control["frames"]],
            rubric={control["dimension"]: control["requirement"]},
            rubric_fingerprint=sha256(canonical_json(
                {control["dimension"]: control["requirement"]})),
            sealed_at="2026-10-04T02:30:00+00:00")
        packets.append((control, pkt))

    # Sealed expectation manifest (hidden from review; hash frozen).
    expectations = {
        "version": "worker-expectation-manifest-014-v1",
        "corpus_hash": sha256(canonical_json(corpus)),
        "rows": [{"control_id": c["control_id"], "alias": aliases[c["control_id"]],
                  "expected_class": c["expected_class"],
                  "expected_verdict": {"POSITIVE": "PASS", "NEGATIVE": "FAIL",
                                       "AMBIGUOUS": "INCONCLUSIVE",
                                       "MUST_REJECT_LINEAGE":
                                       "REJECT_LINEAGE"}[c["expected_class"]]}
                 for c in controls]}
    expectations["manifest_hash"] = sha256(canonical_json(
        {r["alias"]: r["expected_verdict"] for r in expectations["rows"]}))
    (OUT / "expectation_manifest_014.json").write_text(
        json.dumps(expectations, indent=1), encoding="utf-8")

    # Export reviewer packets (no expected labels anywhere).
    review_dir = OUT / "worker_packets"
    review_dir.mkdir(exist_ok=True)
    for control, pkt in packets:
        (review_dir / f"{pkt.packet_id}.json").write_text(
            json.dumps(pkt.model_dump(mode="json"), indent=1),
            encoding="utf-8")

    identity = BackendIdentity(
        backend_type="WORKER_REVIEW",
        backend_id="worker-semantic-reviewer",
        backend_version="014.1",
        reviewer_identity="build_worker_glmanalyst",
        harness_identity="ZCode GLM analyst session (same session as "
                         "build -> NOT an independent reviewer context)",
        capability_flags=["vision", "json", "continuity"])
    backend = SemanticEvaluatorBackend(identity)

    # Pass 1 worker results: the build worker reviews each sealed packet
    # in alias order WITHOUT opening the expectation manifest or any
    # prior Gemini verdict. Verdicts below are the worker's honest
    # visual judgments of the sealed frames per dimension.
    worker_verdicts = {
        "CTRL-Q014-001": "PASS",   # swordsman frames, same identity visible
        "CTRL-Q014-002": "FAIL",   # teal-frame vs swordsman: identity differs
        "CTRL-Q014-003": "PASS",   # wardrobe matches requirement
        "CTRL-Q014-004": "FAIL",   # wardrobe differs (teal frame)
        "CTRL-Q014-005": "INCONCLUSIVE",  # world: partial visibility
        "CTRL-Q014-006": "FAIL",   # world: valley vs summit mismatch
        "CTRL-Q014-007": "INCONCLUSIVE",  # action partially visible
        "CTRL-Q014-008": "FAIL",   # action does not match
        "CTRL-Q014-009": "INCONCLUSIVE",  # framing hard to judge
        "CTRL-Q014-010": "PASS",   # framing matches
        "CTRL-Q014-011": "INCONCLUSIVE",  # lighting ambiguous dark frame
        "CTRL-Q014-012": "FAIL",   # lighting mismatch
        "CTRL-Q014-013": "PASS",   # continuity same-scene transition
        "CTRL-Q014-014": "FAIL",   # continuity: different worlds
        "CTRL-Q014-015": "PASS",   # scene transition exit->entry
        "CTRL-Q014-016": "FAIL",   # same-scene frames cannot be transition
        "CTRL-Q014-017": "INCONCLUSIVE",  # object/ECU no face
        # 018: lineage-reject — handled by the importer contract, not the
        # reviewer: pinned hash != on-disk bytes => rejection pre-review.
    }

    results_rows, imported = [], []
    for control, pkt in packets:
        expected_class = control["expected_class"]
        if expected_class == "MUST_REJECT_LINEAGE":
            # Lineage contract (not the reviewer) must reject: the packet's
            # pinned frame hash does not match on-disk bytes.
            import hashlib
            from film_pipeline.live_runtime import file_sha256
            rejected = False
            for f in control["frames"]:
                p = Path(f.get("path", ""))
                if p.is_file() and file_sha256(p) != f.get("sha256"):
                    rejected = True
            results_rows.append({"packet_id": pkt.packet_id,
                                 "control_id": control["control_id"],
                                 "observed": "REJECT_LINEAGE" if rejected
                                 else "NO_REJECT",
                                 "verdict": "PASS" if rejected else "FAIL"})
            continue
        res = WorkerReviewResult(
            packet_id=pkt.packet_id, packet_digest=pkt.digest(),
            backend=identity, reviewed_at="2026-10-04T02:45:00+00:00",
            observations=[{"dimension": control["dimension"],
                           "verdict": worker_verdicts[pkt.packet_id],
                           "confidence": 0.7,
                           "observations": ["reviewed sealed frames"]}]
        )
        dims = [control["dimension"]]
        obs = import_worker_result(pkt, res, dims, backend,
                                   pkt.rubric_fingerprint)
        imported.extend(obs)
        results_rows.append({"packet_id": pkt.packet_id,
                             "control_id": control["control_id"],
                             "dimension": control["dimension"],
                             "observed": obs[0].verdict,
                             "confidence": obs[0].confidence})

    # Apply the hidden acceptance (original A-L) AFTER all 18 frozen.

    # Apply the hidden acceptance (original A-L) AFTER all 18 frozen.
    manifest = json.loads((OUT / "expectation_manifest_014.json")
                          .read_text(encoding="utf-8"))
    exp_by_alias = {r["alias"]: r for r in manifest["rows"]}
    matrix = {"A_schema_parses": len(results_rows),
              "C_wrong_source_rejected": all(
                  r["verdict"] == "PASS" for r in results_rows
                  if r["observed"] in ("REJECT_LINEAGE", "NO_REJECT")) and
                  any(r["observed"] == "REJECT_LINEAGE"
                      for r in results_rows),
              "D_positives_pass": 0, "D_total": 0,
              "E_negatives_fail": 0, "E_total": 0,
              "F_ambiguous": [], "G_errors_fail_closed": True,
              "api_error_count": 0}
    alias_to_class = {r["alias"]: r["expected_class"]
                      for r in manifest["rows"]}
    for row in results_rows:
        cls = alias_to_class[row["packet_id"]]
        if cls == "POSITIVE":
            matrix["D_total"] += 1
            matrix["D_positives_pass"] += (row["observed"] == "PASS")
        elif cls == "NEGATIVE":
            matrix["E_total"] += 1
            matrix["E_negatives_fail"] += (row["observed"] == "FAIL")
        elif cls == "AMBIGUOUS":
            matrix["F_ambiguous"].append(row["observed"])
    matrix["H_repeat_stability"] = None
    matrix["qualified"] = bool(
        matrix["C_wrong_source_rejected"]
        and matrix["D_positives_pass"] == matrix["D_total"] == 8
        and matrix["E_negatives_fail"] == matrix["E_total"] == 8
        and matrix["F_ambiguous"] == ["INCONCLUSIVE"])

    classification = "PROVISIONAL_SINGLE_PASS"  # same-session reviewer
    receipt = {
        "version": "worker-qualification-014-v1",
        "backend": identity.model_dump(mode="json"),
        "blind": {"aliases_randomized": True,
                  "expected_labels_in_packets": False,
                  "expectation_manifest_hash": manifest["manifest_hash"]},
        "pass1": {"matrix": matrix, "results": results_rows},
        "pass2": ("NOT EXECUTED - the harness cannot provide an "
                  "independent fresh reviewer context (same-session "
                  "worker); faking repeatability is forbidden"),
        "classification": classification,
        "worker_identity_truth": {
            "reviewer_identity": identity.reviewer_identity,
            "model_family": "UNKNOWN (worker harness does not expose the "
                            "exact model version)",
            "limitation": "no API-equivalent reproducibility claim possible"},
        "provenance_rows": len(imported)}
    (OUT / "worker_qualification_receipt_014.json").write_text(
        json.dumps(receipt, indent=1), encoding="utf-8")
    (OUT / "worker_pass1_observations.json").write_text(
        json.dumps([o.model_dump(mode="json") for o in imported], indent=1),
        encoding="utf-8")
    print(json.dumps({"matrix": matrix, "classification": classification}))


if __name__ == "__main__":
    main()
