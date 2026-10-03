"""Provider-neutral semantic backend boundary (Package-014 W2-W4).

Film Core consumes only SemanticQCRequest -> SemanticQCObservation.
Provider/model/harness details stay inside backends. Backends carry
provenance on every observation; a worker backend is NEVER represented
as an API backend. Semantic results grant ZERO provider authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256
from .semantic_qc import SemanticQCRequest, SemanticQCObservation

BACKEND_TYPES = ("API_MODEL", "WORKER_REVIEW", "OWNER_REVIEW")
OBSERVATION_SCHEMA_VERSION = "semantic-observation-provenance-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackendIdentity(ContractModel):
    """The strongest exact identity a backend can truthfully expose."""
    backend_type: str
    backend_id: str = Field(min_length=1)
    backend_version: str = Field(min_length=1)
    reviewer_identity: str  # exact if exposed; else "UNKNOWN"
    harness_identity: str
    capability_flags: list[str] = []

    @model_validator(mode="after")
    def validate_identity(self):
        if self.backend_type not in BACKEND_TYPES:
            raise ValueError(f"unknown backend type {self.backend_type}")
        if self.backend_type == "WORKER_REVIEW" and \
                "api" in self.backend_id.lower().split("-"):
            raise ValueError("worker backend must not be labeled as an API "
                             "backend")
        return self

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class ProvenancedObservation(ContractModel):
    """SemanticQCObservation + full replacement/comparison provenance."""
    observation_schema_version: str = OBSERVATION_SCHEMA_VERSION
    backend_type: str
    backend_id: str
    backend_version: str
    reviewer_identity: str
    harness_identity: str
    request_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_source_fingerprints: list[str]
    rubric_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: str
    verdict: str
    dimension: str
    confidence: float | None = None
    evidence: list[str] = []
    lineage: dict = {}
    limitations: list[str] = []

    @model_validator(mode="after")
    def validate_provenance(self):
        if self.verdict not in ("PASS", "FAIL", "INCONCLUSIVE"):
            raise ValueError("unqualified verdict")
        if self.backend_type not in BACKEND_TYPES:
            raise ValueError("unknown backend type")
        if self.backend_type in ("WORKER_REVIEW", "OWNER_REVIEW") and \
                self.reviewer_identity == "UNKNOWN":
            self.limitations = list(set(self.limitations) | {
                "reviewer_identity_unknown: no API-equivalent "
                "reproducibility claim possible"})
        return self

    def provenance_digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class SemanticEvaluatorBackend:
    """Minimal interchangeable backend interface (W2 contract).

    Subclasses implement evaluate(); identity() is frozen at
    construction. Film logic must never special-case a provider name.
    """

    def __init__(self, identity: BackendIdentity):
        self.identity = identity

    def evaluate(self, request: SemanticQCRequest
                 ) -> list[ProvenancedObservation]:
        raise NotImplementedError("backend must implement evaluate")

    def provenance_for(self, request_fingerprint: str,
                       rubric_fingerprint: str) -> dict:
        return {
            "backend_type": self.identity.backend_type,
            "backend_id": self.identity.backend_id,
            "backend_version": self.identity.backend_version,
            "reviewer_identity": self.identity.reviewer_identity,
            "harness_identity": self.identity.harness_identity,
            "request_fingerprint": request_fingerprint,

            "rubric_fingerprint": rubric_fingerprint,
            "created_at": utc_now(),
        }


class WorkerReviewPacket(ContractModel):
    """Sealed evidence packet for a worker reviewer (W3).

    Contains ONLY what the reviewer needs. It MUST NOT contain expected
    labels, acceptance thresholds, prior verdicts, or any semantic label
    in its identifier (blind aliases like CTRL-Q014-001 are used).
    """
    packet_id: str = Field(pattern=r"^PKT-Q014-[0-9]{3}$")
    request_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    shot_spec_json: dict
    selected_take_lineage: dict
    frame_hashes: list[str]
    frame_paths: list[str]
    reference_context: dict = {}
    continuity_context: dict = {}
    rubric: dict
    rubric_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_schema_version: str = OBSERVATION_SCHEMA_VERSION
    sealed_at: str

    @model_validator(mode="after")
    def validate_blind(self):
        blob = canonical_json(self.model_dump(mode="json")).lower()
        for leak in ("positive", "negative", "expected", "acceptance",
                     "threshold", "must_reject", "ambiguous", "pass_target",
                     "fail_target"):
            if leak in blob and leak in self.rubric_fingerprint:
                raise ValueError("blind leak")
        for field in ("shot_spec_json", "rubric"):
            text = canonical_json(getattr(self, field)).lower()
            for leak in ("expected_class", "expected_verdict",
                         "acceptance", "threshold", "pass_target"):
                if f'"{leak}"' in text:
                    raise ValueError(f"packet leaks hidden field: {leak}")
        return self

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class WorkerReviewResult(ContractModel):
    """The worker's sealed answer for one packet, before import."""
    packet_id: str = Field(pattern=r"^PKT-Q014-[0-9]{3}$")
    packet_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    backend: BackendIdentity
    reviewed_at: str
    observations: list[dict]  # dimension/verdict/confidence/evidence

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


def import_worker_result(packet: WorkerReviewPacket,
                         result: WorkerReviewResult,
                         expected_dimensions: list[str],
                         backend: SemanticEvaluatorBackend,
                         rubric_fingerprint: str,
                         ) -> list[ProvenancedObservation]:
    """Strict importer: packet -> observations, fail-closed on every
    mismatch. The worker result has ZERO provider authority."""
    if result.packet_id != packet.packet_id:
        raise ValueError("result is for another request")
    if result.packet_digest != packet.digest():
        raise ValueError("packet was altered after review")
    if result.backend.digest() != backend.identity.digest():
        raise ValueError("unknown backend identity")
    if result.observations and len(result.observations) > \
            len(expected_dimensions) * 2:
        raise ValueError("duplicate final observations")
    provenance = backend.provenance_for(packet.request_fingerprint,
                                        rubric_fingerprint)
    seen = set()
    for entry in result.observations:
        dimension = entry.get("dimension")
        if dimension not in expected_dimensions:
            raise ValueError(f"unexpected/missing dimension {dimension}")
        if dimension in seen:
            raise ValueError("duplicate dimension observation")
        seen.add(dimension)
    missing = set(expected_dimensions) - seen
    if missing:
        raise ValueError(f"missing required dimensions: {sorted(missing)}")
    observations = []
    for entry in result.observations:
        dimension = entry.get("dimension")
        verdict = entry.get("verdict")
        if verdict not in ("PASS", "FAIL", "INCONCLUSIVE"):
            raise ValueError("unqualified verdict")
        observations.append(ProvenancedObservation(
            backend_type=provenance["backend_type"],
            backend_id=provenance["backend_id"],
            backend_version=provenance["backend_version"],
            reviewer_identity=provenance["reviewer_identity"],
            harness_identity=provenance["harness_identity"],
            request_fingerprint=packet.request_fingerprint,
            input_source_fingerprints=packet.frame_hashes,
            rubric_fingerprint=packet.rubric_fingerprint,
            created_at=result.reviewed_at,
            verdict=verdict,
            dimension=dimension,
            confidence=entry.get("confidence"),
            evidence=[str(o)[:400] for o in entry.get("observations", [])],
            lineage={"packet_id": packet.packet_id,
                     "packet_digest": packet.digest()},
            limitations=["worker review is observational; zero provider "
                         "mutation authority"]))
    return observations


