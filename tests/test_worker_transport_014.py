"""Package-014 W3 — worker transport offline proofs: sealed blind packets,
strict importer, hidden-label leak refusal, provenance authority."""
import hashlib
import io
import json
from pathlib import Path

import pytest

from film_pipeline.semantic_backends import (
    BackendIdentity, ProvenancedObservation, SemanticEvaluatorBackend,
    WorkerReviewPacket, WorkerReviewResult, import_worker_result)
from film_pipeline.core import canonical_json, sha256

RUBRIC = {"character_identity": "the same lone swordsman: white robes"}
FP = "a" * 64


def identity():
    return BackendIdentity(backend_type="WORKER_REVIEW",
                           backend_id="worker-semantic-reviewer",
                           backend_version="014.1",
                           reviewer_identity="build_worker_glmanalyst",
                           harness_identity="ZCode GLM analyst session",
                           capability_flags=["vision", "json"])


def backend():
    return SemanticEvaluatorBackend(identity())


def packet(packet_id="CTRL-Q014-001", rubric=None):
    return WorkerReviewPacket(
        packet_id=packet_id, request_fingerprint=FP,
        shot_spec_json={"shot_id": "X", "dramatic_purpose": "p"},
        selected_take_lineage={"take": "t"}, frame_hashes=["f" * 64],
        frame_paths=["frames/x_0.png"],
        rubric=rubric or RUBRIC,
        rubric_fingerprint=sha256(canonical_json(RUBRIC)),
        sealed_at="2026-10-04T00:00:00+00:00")


def result(pkt, dims=None, verdict="PASS"):
    dims = list(RUBRIC) if dims is None else dims
    return WorkerReviewResult(
        packet_id=pkt.packet_id, packet_digest=pkt.digest(),
        backend=identity(), reviewed_at="2026-10-04T01:00:00+00:00",
        observations=[{"dimension": d, "verdict": verdict,
                       "confidence": 0.8, "observations": ["visible fact"]}
                      for d in dims])


def test_01_immutable_packet_digest_binds_content(tmp_path):
    pkt = packet()
    frozen = pkt.digest()
    other = pkt.model_copy(update={"shot_spec_json": {"shot_id": "Y"}})
    assert other.digest() != frozen


def test_02_result_for_wrong_packet_refused():
    pkt = packet()
    res = result(pkt)
    other = packet(packet_id="CTRL-Q014-002")
    with pytest.raises(ValueError, match="another request"):
        import_worker_result(other, res, list(RUBRIC), backend(),
                             sha256(canonical_json(RUBRIC)))


def test_03_altered_packet_after_review_refused():
    pkt = packet()
    res = result(pkt)
    altered = pkt.model_copy(update={"frame_hashes": ["0" * 64]})
    with pytest.raises(ValueError, match="altered after review"):
        import_worker_result(altered, res, list(RUBRIC), backend(),
                             sha256(canonical_json(RUBRIC)))


def test_04_unknown_backend_refused():
    pkt = packet()
    res = result(pkt)
    stranger = SemanticEvaluatorBackend(BackendIdentity(
        backend_type="WORKER_REVIEW", backend_id="someone-else",
        backend_version="0", reviewer_identity="x", harness_identity="y"))
    with pytest.raises(ValueError, match="unknown backend"):
        import_worker_result(pkt, res, list(RUBRIC), stranger,
                             sha256(canonical_json(RUBRIC)))


def test_05_missing_dimension_refused():
    pkt = packet()
    res = result(pkt, dims=[])
    with pytest.raises(ValueError, match="missing required dimensions"):
        import_worker_result(pkt, res, list(RUBRIC), backend(),
                             sha256(canonical_json(RUBRIC)))


def test_06_duplicate_dimension_refused():
    pkt = packet()
    res = WorkerReviewResult(
        packet_id=pkt.packet_id, packet_digest=pkt.digest(),
        backend=identity(), reviewed_at="t",
        observations=[{"dimension": "character_identity", "verdict": "PASS"},
                      {"dimension": "character_identity", "verdict": "FAIL"}])
    with pytest.raises(ValueError, match="duplicate dimension"):
        import_worker_result(pkt, res, list(RUBRIC), backend(),
                             sha256(canonical_json(RUBRIC)))


def test_07_unqualified_verdict_refused():
    pkt = packet()
    res = WorkerReviewResult(
        packet_id=pkt.packet_id, packet_digest=pkt.digest(),
        backend=identity(), reviewed_at="t",
        observations=[{"dimension": "character_identity",
                       "verdict": "PROBABLY"}])
    with pytest.raises(ValueError, match="unqualified verdict"):
        import_worker_result(pkt, res, list(RUBRIC), backend(),
                             sha256(canonical_json(RUBRIC)))


def test_08_expected_label_hidden_in_packet_refused():
    with pytest.raises(ValueError, match="expected_class"):
        packet(rubric={"character_identity": "same swordsman",
                       "expected_class": "POSITIVE"})


def test_09_label_words_in_alias_free_id():
    pkt = packet(packet_id="CTRL-Q014-007")
    assert "positive" not in pkt.packet_id.lower()
    assert "negative" not in pkt.packet_id.lower()


def test_10_provenanced_observation_carries_backend_provenance():
    pkt = packet()
    obs = import_worker_result(pkt, result(pkt), list(RUBRIC), backend(),
                               sha256(canonical_json(RUBRIC)))
    assert obs[0].backend_type == "WORKER_REVIEW"
    assert obs[0].backend_id == "worker-semantic-reviewer"
    assert obs[0].rubric_fingerprint == sha256(canonical_json(RUBRIC))
    assert obs[0].request_fingerprint == FP


def test_11_worker_result_grants_no_authority():
    obs = import_worker_result(packet(), result(packet()), list(RUBRIC),
                               backend(), sha256(canonical_json(RUBRIC)))
    assert all("zero provider mutation authority" in o.limitations[0]
               for o in obs)


def test_12_worker_backend_never_labeled_api():
    with pytest.raises(ValueError, match="must not be labeled"):
        BackendIdentity(backend_type="WORKER_REVIEW",
                        backend_id="worker-api-backend",
                        backend_version="0", reviewer_identity="x",
                        harness_identity="y")


def test_13_owner_review_backend_type_allowed():
    ident = BackendIdentity(backend_type="OWNER_REVIEW",
                            backend_id="owner", backend_version="1",
                            reviewer_identity="owner", harness_identity="-")
    assert ident.backend_type == "OWNER_REVIEW"


def test_14_result_digest_tamper_detection():
    pkt = packet()
    res = result(pkt)
    sealed = res.digest()
    tampered = res.model_copy(update={"reviewed_at": "later"})
    assert tampered.digest() != sealed
