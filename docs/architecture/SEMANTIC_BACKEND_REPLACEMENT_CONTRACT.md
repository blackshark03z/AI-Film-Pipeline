# SEMANTIC BACKEND REPLACEMENT CONTRACT

Frozen by FLOW-WORKER-SEMANTIC-BACKEND-014 (W13). This document is the
authoritative migration contract between semantic backends. The JSON
mirror inside every delivery bundle (`manifests/backend_replacement_
contract.json`) must stay in sync with this file.

## 1. Provider-neutral request schema

`SemanticQCRequest` (`src/film_pipeline/semantic_qc.py`): request_id,
dimensions (from the frozen semantic dimension vocabulary), frames
(hash-pinned), requirements (dimension -> frozen natural-language
requirement), provenance. No provider-specific fields.

## 2. Provider-neutral observation schema

`ProvenancedObservation` (`src/film_pipeline/semantic_backends.py`):
every observation carries verdict (PASS/FAIL/INCONCLUSIVE), dimension,
evidence, and full provenance — backend_type (API_MODEL | WORKER_REVIEW
| OWNER_REVIEW), backend_id, backend_version, reviewer_identity,
harness_identity, request_fingerprint, input_source_fingerprints,
rubric_fingerprint, created_at, lineage, limitations.

## 3. Provenance rules

- Historical worker observations are never rewritten as if an API
  produced them; backend_type is immutable per observation.
- `reviewer_identity = UNKNOWN` forces a limitations entry: no
  API-equivalent reproducibility claim.
- Worker/Owner review results carry ZERO provider mutation authority.

## 4. Qualification corpus

The exact frozen Package-006 corpus
(`projects/flow_semantic_qualify_006/corpus/qualification_corpus.json`):
18 controls — 8 POSITIVE / 8 NEGATIVE / 1 AMBIGUOUS /
1 MUST_REJECT_LINEAGE. Never relabeled, never resampled.

## 5. Qualification acceptance

Original frozen Package-006 criteria A–L, applied verbatim: schema
parses; lineage exact; wrong-source rejected pre-API; positives
materially PASS (8/8); negatives materially FAIL (8/8); ambiguous may
stay INCONCLUSIVE; errors fail closed; repeats stable; fingerprints
recorded; authority separated. No threshold may be lowered.

## 6. Repeatability requirement

Two complete passes on the frozen corpus with verdict/dimension/schema
stability. A backend with only one pass is PROVISIONAL_SINGLE_PASS —
usable as Owner-assist review, never as autonomous semantic truth.

## 7. Cross-backend comparison

Before an API backend is promoted, it runs a shadow review of the
canonical review set (the 30 canonical shots + master boundary packets)
and a discrepancy report is produced against the incumbent backend's
observations. Classification is diagnostic only — no composite score.

## 8. Rollout procedure

1. Implement `SemanticEvaluatorBackend` adapter for the new provider.
2. Qualify on the frozen corpus (Pass 1 + Pass 2 + stability).
3. Shadow review of the canonical set; discrepancy report reviewed.
4. Promote: the active-backend flag moves to the new adapter.
5. The worker backend remains a fallback or is disabled by policy.

## 9. Rollback procedure

Revert the active-backend flag to the previous adapter. Historical
observations keep their original provenance; no merge or relabel.

## 10. Observation coexistence / versioning

Observations from multiple backends coexist keyed by
(request_fingerprint, backend_type, backend_id, backend_version).
`observation_schema_version` must be bumped on any schema change.

## 11. Cache isolation

Any result cache must be keyed by (backend_type, backend_id,
backend_version, model/worker identity, rubric_fingerprint,
request_fingerprint). Cross-backend cache reuse is forbidden.

## 12. Authority boundary

No semantic review result — from any backend, any model, any confidence
level — grants, restores, or expands provider mutation authority.
Repair/Owner recommendations are documents, not authority.

## 13. Worker backend verdict correction (Package-015 Phase 0)

The worker semantic backend (worker-semantic-reviewer, 014.1) is
**NOT_QUALIFIED**: Package-014 Pass 1 did not meet the frozen 006 corpus
acceptance (positives 2/8, negatives 6/8, ambiguous mismatch). The
section-6 label "PROVISIONAL_SINGLE_PASS" is a classification that would
only have applied if Pass 1 had met the frozen acceptance but
repeatability was unavailable; it was misapplied in Package-014 and is
superseded by the NOT_QUALIFIED verdict. The worker's 30-shot production
review, master boundary review and consistency audit remain valid as
PROVISIONAL_OWNER_ASSIST_REVIEW — observational Owner-assist only, never
autonomous semantic truth. SEMANTIC_AUTONOMOUS_READY = false. A future
API backend still qualifies exclusively through sections 4–8.
