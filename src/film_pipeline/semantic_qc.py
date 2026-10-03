"""Smallest replaceable semantic QC interface (FLOW-MULTISCENE-SEMANTIC-REPAIR-004).

Semantic QC is EVALUATOR-ONLY evidence. It never controls provider ownership,
lineage, mutation authority, or budget; technical QC and provider lineage
remain separate truths. Verdicts are structured — free-form prose alone can
never become RepairDecision authority.

STATUS (frozen package): SEMANTIC_QC_UNQUALIFIED — no qualified VLM key is
available in this environment, so live semantic observations are advisory
candidates at most. Qualification requires: reliable structured schema,
passing positive controls, detected negative controls, INCONCLUSIVE-capable
ambiguous controls, exact source lineage, zero provider mutation.
"""
from __future__ import annotations

from pydantic import Field

from .core import ContractModel, canonical_json, sha256

SEMANTIC_QC_STATUS = "SEMANTIC_QC_UNQUALIFIED"
SEMANTIC_DIMENSIONS = (
    "character_identity",
    "wardrobe_props",
    "environment_world",
    "action_completion",
    "framing_camera",
    "lighting_time",
    "shot_continuity",
    "scene_transition",
)
SEMANTIC_VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE")


class SemanticQCRequest(ContractModel):
    """Bounded evaluation input. Every referenced artifact is hash-pinned."""

    request_id: str
    dimensions: list[str]
    frames: list[dict]  # [{path, sha256, label}]
    requirements: dict[str, str]  # dimension -> frozen natural-language requirement
    provenance: dict[str, str]  # shot_id/asset_id/provider_media_id/scene_id...
    evaluator_hint: str | None = None

    def model_post_init(self, __context) -> None:
        if not self.dimensions or any(d not in SEMANTIC_DIMENSIONS for d in self.dimensions):
            raise ValueError("semantic dimensions unqualified")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("duplicate semantic dimensions")
        for frame in self.frames:
            if set(frame) < {"path", "sha256"} or not str(frame["sha256"]).isdigit() \
                    and len(str(frame["sha256"])) != 64:
                raise ValueError("semantic frames must be hash-pinned")
        for dimension in self.dimensions:
            if not isinstance(self.requirements.get(dimension), str):
                raise ValueError(f"missing frozen requirement for {dimension}")


class SemanticQCObservation(ContractModel):
    """One structured evaluator output per dimension. Advisory evidence only."""

    request_id: str
    dimension: str
    verdict: str  # PASS | FAIL | INCONCLUSIVE
    confidence: float = Field(ge=0.0, le=1.0)
    observations: list[str]
    evidence_refs: list[dict]
    evaluator_type: str
    evaluator_version: str
    prompt_fingerprint: str

    def model_post_init(self, __context) -> None:
        if self.dimension not in SEMANTIC_DIMENSIONS:
            raise ValueError("semantic dimension unqualified")
        if self.verdict not in SEMANTIC_VERDICTS:
            raise ValueError("semantic verdict unqualified")
        if not self.observations or any(not o.strip() for o in self.observations):
            raise ValueError("semantic observation required")


def semantic_request_id(basis: dict) -> str:
    return "semreq_" + sha256(basis)


def observation_fingerprint(observation: SemanticQCObservation) -> str:
    basis = observation.model_dump(mode="json")
    return sha256(basis)


class SemanticQCEvaluator:
    """Smallest replaceable evaluator interface.

    Implementations MUST: return exactly one observation per requested
    dimension; emit PASS/FAIL/INCONCLUSIVE only; keep provenance lineage; be
    deterministic for a fixed (request, evaluator_version, fixture) tuple.
    Implementations MUST NOT: touch provider state, grant mutation authority,
    or convert prose into verdicts.
    """

    evaluator_type: str = "abstract"
    evaluator_version: str = "abstract-v0"

    def evaluate(self, request: SemanticQCRequest) -> list[SemanticQCObservation]:
        raise NotImplementedError("semantic evaluator must implement evaluate")


class FrozenFixtureEvaluator(SemanticQCEvaluator):
    """Deterministic offline evaluator for interface/schema tests only.

    Verdicts come from a frozen fixture table keyed by (dimension, label);
    anything outside the fixture is INCONCLUSIVE. Never a production
    evaluator — it exists to prove the contract is testable without a VLM.
    """

    evaluator_type = "frozen_fixture"
    evaluator_version = "frozen-fixture-v1"

    def __init__(self, fixtures: dict[tuple[str, str], tuple[str, float, list[str]]]):
        self.fixtures = fixtures

    def evaluate(self, request: SemanticQCRequest) -> list[SemanticQCObservation]:
        observations = []
        for dimension in request.dimensions:
            label = request.provenance.get("fixture_label", "")
            entry = self.fixtures.get((dimension, label))
            if entry is None:
                verdict, confidence, notes = "INCONCLUSIVE", 0.0, ["no fixture entry"]
            else:
                verdict, confidence, notes = entry
            observations.append(SemanticQCObservation(
                request_id=request.request_id, dimension=dimension,
                verdict=verdict, confidence=confidence, observations=notes,
                evidence_refs=list(request.frames),
                evaluator_type=self.evaluator_type,
                evaluator_version=self.evaluator_version,
                prompt_fingerprint=sha256(canonical_json({
                    "dimension": dimension, "fixture_label": label}))))
        return observations


def validate_semantic_batch(request: SemanticQCRequest,
                            observations: list[SemanticQCObservation]) -> None:
    """Contract check for any evaluator output against its request."""
    if len(observations) != len(request.dimensions):
        raise ValueError("semantic batch cardinality mismatch")
    got = [o.dimension for o in observations]
    if sorted(got) != sorted(request.dimensions):
        raise ValueError("semantic batch dimensions mismatch")
    for observation in observations:
        if observation.request_id != request.request_id:
            raise ValueError("semantic observation request_id mismatch")
        observation_fingerprint(observation)  # fingerprint must recompute
