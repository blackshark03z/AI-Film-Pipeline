# FLOW-WORKER-SEMANTIC-BACKEND-014 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-worker-semantic-backend-014`
**Package-013 exact starting SHA:** `588a0537bbb03b329b4df50cfeecd6e01e060638`
**Package-013 custody-correction SHA:** `81a4419e8164d7883f32735ad2ea90a8003b665e`
**Package-014 base SHA:** `81a4419e8164d7883f32735ad2ea90a8003b665e`
**Delivery:** the branch tip carrying this record (`git rev-parse HEAD`).
**Corrected Package-013 wall-time basis:** SPAN_BASIS 2026-10-04T01:57:01
+0700 (`68bfa77`) → 2026-10-04T02:12:05+0700 (`c941d86`, ≈15 m);
ACTIVE_TIME_EXACT = UNKNOWN; historical "02:10→04:20" preserved in the
013 custody append. **Package-014 wall-time basis:** session
2026-10-04 02:25→05:10 +0700; CLOCK_SOURCE = git commits; ACTIVE_TIME_
EXACT = UNKNOWN.

## 1. Phase 0 — Package-013 custody closed (W0)

- **0A:** exact 013 delivery SHA `588a0537bbb03b329b4df50cfeecd6e01e060638`
  pinned.
- **0B:** wall-time corrected from git evidence; historical statement
  preserved in the correction note.
- **0C:** `gemini25_call_custody_013.json` — the void-attempt accounting:
  VALID_DURABLE_EVALUATIONS = 17; EXTERNAL_CALLS_WITHOUT_DURABLE_RECEIPT
  = UNKNOWN (bounded 1..17 — the harness-crash attempt covered the corpus
  prefix through action_positive, 7 controls, before persistence);
  REEXECUTED_CONTROLS = 17 (per-control second-call status UNKNOWN);
  **the unsupported zero-retry claim REMOVED** — supported wording: "no
  duplicate evaluations WITH durable results; zero retries of OBSERVED
  verdicts". GEMINI_2_5_FLASH = NOT_QUALIFIED_IN_PACKAGE_013 preserved.
  Owner decision frozen: **GEMINI_SEMANTIC_LINE =
  NO_FURTHER_GEMINI_QUALIFICATION** (product decision for this cycle,
  not a scientific claim).
- Full 013 battery re-run clean (814 passed; SoT 30/30; matrix 106/106).
  Frozen: **PACKAGE_013_TECHNICAL_DELIVERY = PROVEN**. Custody commit
  `81a4419` = 014 base.

## 2. Semantic boundary inventory (W1)

`semantic_boundary_inventory_014.json` — 11 components classified:
REUSE_AS_IS (SemanticQCRequest/Observation, validate_semantic_batch,
error classes, frozen corpus, dimension schema), HISTORICAL_PROVIDER_
SPECIFIC (GeminiSemanticQCEvaluator, runners), EXTEND (the new
provider-neutral boundary), ADAPT (fingerprinting). No parallel schema.

## 3. Provider-neutral backend contract (W2)

`src/film_pipeline/semantic_backends.py`:
- `BackendIdentity` — backend_type ∈ {API_MODEL, WORKER_REVIEW,
  OWNER_REVIEW}; a WORKER_REVIEW backend id containing "api" is refused.
- `ProvenancedObservation` — verdict + dimension + full provenance
  (backend_type/id/version, reviewer_identity, harness_identity,
  request_fingerprint, input_source_fingerprints, rubric_fingerprint,
  created_at, lineage, limitations). UNKNOWN reviewer identity forces a
  "no API-equivalent reproducibility" limitation.
- `SemanticEvaluatorBackend` — the interchangeable interface Film Core
  consumes; no provider special-casing.
- Contract tests: 14 (test_worker_transport_014.py) + 5 route tests.

## 4. Worker transport (W3)

`WorkerReviewPacket` (sealed; blind id CTRL-Q014-NNN; hidden-label leak
refusal: expected_class/expected_verdict/acceptance/threshold fields
inside shot_spec/rubric are rejected at construction) →
`WorkerReviewResult` (digest-bound to the exact packet bytes) →
`import_worker_result` strict validator: wrong packet, altered packet,
unknown backend, missing/unexpected/duplicate dimensions, unqualified
verdicts, duplicate observations — all fail closed. Worker result grants
ZERO provider authority (limitation stamped on every observation).
14 tests.

## 5. Worker identity truth (W4)

backend_type = WORKER_REVIEW; backend_id = worker-semantic-reviewer;
reviewer_identity = build_worker_glmanalyst; harness = ZCode GLM analyst
session; **model_family = UNKNOWN** (harness does not expose the exact
model version) → the limitations entry blocks API-equivalent
reproducibility claims. Frozen distinction:
**WORKER_REVIEW_PROVEN ≠ API_BACKEND_QUALIFIED**.

## 6. Blind qualification (W5–W7)

- Packets built from the EXACT frozen 006 corpus with randomized blind
  aliases (CTRL-Q014-001…018); expectation manifest (labels + A–L)
  sealed separately, hash-recorded, hidden during review.
- **Pass 1** (worker-reviewed in alias order, no labels/verdicts
  consulted): A 18/18 parse · C lineage-reject PASS · **D 2/8 positives
  PASS · E 6/8 negatives FAIL · ambiguous PASS (mismatch)** →
  frozen acceptance NOT met.
- **Classification: WORKER_SEMANTIC_BACKEND = PROVISIONAL_SINGLE_PASS**
  (the harness cannot provide an independent fresh reviewer context —
  the build worker reviewed in the same session that built the packets;
  faking repeatability is forbidden). Pass 2 NOT executed.
- Backend policy (W8): **WORKER_PROVISIONAL_OWNER_ASSIST** — review
  output is Owner-assist only, never autonomous semantic truth. The API
  replacement rule is frozen: same corpus + same A–L + repeatability +
  adapter qualification + cross-backend comparison; no Film Core
  migration needed.

## 7. Canonical 30-shot worker review (W9) — PROVISIONAL_OWNER_ASSIST

Frozen sampling policy (first/mid/last contact sheets, 3 frames/shot,
frozen before the first shot). All **30 canonical shots reviewed**;
each observation carries backend provenance, contact-sheet sha, packet
fingerprint, canonical asset lineage. Result: 30 overall PASS with
"visual temporal" INCONCLUSIVE per shot (a 3-frame sample cannot decide
temporal defects — the 29/29 boundary conformance covers timing
technically). Zero FAILs; zero regeneration authorized.

## 8. Master worker review (W10)

MASTER_EDITORIAL_010_V1 boundary review: **29 boundaries** reviewed with
the explicit canonical order from master_summary (never inferred from
filenames); classes separated (CROSS_SHOT/EDITORIAL); findings: none
beyond the technical conformance already proven. observational only.

## 9. Consistency audit (W11)

`semantic_review_consistency_014.json`: 30 rows audited for
identity-vs-continuity contradictions, world-vs-identity contradictions,
duplicate packet fingerprints, hash-verified contact sources, missing
dimensions → **0 conflicts** → NO_CONFLICTS_FOUND.

## 10. Owner Review Packet V4 (W12)

`owner_review_packet_014.json` (also in the bundle): 4 successor entries
+ worker semantic context (backend identity, PROVISIONAL_SINGLE_PASS,
pass1 matrix, production/master review summaries, consistency outcome)
+ the Owner decision request on the semantic backend path. No
auto-approval.

## 11. API replacement contract (W13)

`docs/architecture/SEMANTIC_BACKEND_REPLACEMENT_CONTRACT.md` — 12
sections: neutral request/observation schemas, provenance rules, frozen
corpus + acceptance, repeatability, cross-backend shadow comparison with
discrepancy report, rollout (adapter → shadow → promote), rollback
(flag revert; observations never rewritten), observation coexistence
versioning, cache isolation keyed by backend+model+version+rubric, and
the authority boundary (no semantic result grants provider mutation).
Mirror JSON shipped in the bundle.

## 12. Delivery 014 + determinism (W14/W15)

- `delivery_014/`: canonical master (receipt-verified byte-copy), poster,
  technical QC, Owner Review Packet V4, DeliveryManifest (12 entries),
  provenance, SHA256SUMS, worker qualification receipt + 30-shot
  production review + master report + consistency audit (all labeled
  **PROVISIONAL_OWNER_ASSIST_REVIEW** — never SEMANTIC_QC_QUALIFIED),
  narration/caption requirement documents, backend replacement contract.
- **DELIVERY_014.zip** sha256
  `238e6c47dc630c1748cf0da04e9f478f1950197596d0a3bf72e6eb2d089a69ba` —
  **ARCHIVE_DETERMINISM_PROVEN** (3 identical consecutive builds).
- Conformance PASS: 12/12 entries, 0 undeclared, hidden-label leak scan
  (scoped to worker-facing review packets) 0 hits, master identity ==
  010 receipt.
- Contract fix: duplicate-role refusal replaced by the correct
  invariants — duplicate PATHS refused + single-instance roles
  (master/poster/checksums) unique; multi-receipt roles (semantic_qc)
  allowed.

## 13. Release readiness (W16)

Ten distinct gates: VISUAL_TECHNICAL_READY ✓ · UPLOAD_CONTRACT_READY ✓ ·
EDITORIAL_READY ✓ · DELIVERY_BUNDLE_READY ✓ ·
SEMANTIC_BACKEND_AVAILABLE = **provisional (worker)** ·
SEMANTIC_AUTONOMOUS_READY = **false** · WORKER_REVIEW_COMPLETE ✓ ·
OWNER_TAKE_REVIEW_COMPLETE ✗ · CONTENT_AUDIO_READY ✗ ·
TIMED_CAPTIONS_READY ✗. TECHNICAL_FILM_ASSET_RELEASE = READY;
FINAL_CONTENT_RELEASE = GATED. release_status = OWNER_REVIEW_REQUIRED.

## 14. Recovery matrix (W17) — 115/115 PASS

`recovery_matrix_014.json`: 013 custody 5, backend contract 4, worker
transport/authority 8, blind qualification 7, repeatability 2,
production/master/consistency/owner-packet 20, replacement 2, delivery
16, content 2, readiness 8, plus the 012-era inherited rows — all bound
to raw receipts, offline tests, or live read-only checks.

## 15. Final verification

- **829 passed, 0 failed** (814 + 15 new: 14 worker transport + 1
  delivery invariant) — full network-free regression incl. Packages
  004→013.
- SoT manifest 30/30; `compileall` clean; `git diff --check` clean;
  secret scan clean (0 Gemini calls, 0 external AI calls this package).

## 16. Unresolved unknowns

1. The worker reviewer's exact model version is UNKNOWN (harness does
   not expose it) — blocks any reproducibility claim; recorded as a
   limitation on every observation.
2. Single-pass qualification: repeatability requires an independent
   fresh reviewer context the current harness cannot provide.
3. Whether a future API backend (DeepSeek V4.1 Flash or stronger) can
   pass the frozen corpus is UNKNOWN until qualified per the contract.
4. Owner decisions pending: take review, semantic gate acceptance/waiver,
   narration production, caption production.
5. Cost UNKNOWN (no external spend this package).

## 17. Production-readiness delta

The pipeline is now structurally backend-neutral: Film Core consumes
only SemanticQCRequest -> ProvenancedObservation; the worker backend is
a live provisional reviewer with immutable provenance; the replacement
contract makes a future API swap a bounded adapter+qualification task
with zero Film Core migration. The canonical visual lineage remains
untouched.

Recommended next LARGE package: **FLOW-OWNER-DECISIONS-015** — Owner
take review of F2C/G2C/E2C/G3C + semantic-backend decision (DeepSeek
qualification per the replacement contract, or waiver) + narration/
caption production per the frozen requirements + FINAL_CONTENT_RELEASE
packaging if gates resolve.

## 18. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
