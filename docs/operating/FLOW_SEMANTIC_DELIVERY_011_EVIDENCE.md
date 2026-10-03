# FLOW-SEMANTIC-DELIVERY-011 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-semantic-delivery-011`
**Package-010 exact starting SHA:** `38347cbc09a66865f29f472810ab7c6fe71e90a0`
**Package-010 custody-correction SHA:** `eaf7ef2dc45f39790a62c4b4c6a4ca6f4a5ff85a`
**Package-011 base SHA:** `eaf7ef2dc45f39790a62c4b4c6a4ca6f4a5ff85a`
**Delivery:** the branch tip carrying this record (`git rev-parse HEAD`).
**Exact delivery SHA (appended by FLOW-OWNER-REVIEW-SEMANTIC-RELEASE-012
Phase 0):** `4dba81e567b348f5baf0f418f7e1fd12640e9981`

## CUSTODY APPEND + CORRECTION (Package-012 Phase 0, 2026-10-04)

**0B — Wall-time correction.** The historical field above stated
"durable commit span 2026-10-03T17:11Z (ef5d892) → 2026-10-04T18:1xZ
(delivery)" — that conversion is WRONG and is preserved verbatim as
history. Corrected durable basis (CLOCK_SOURCE = git commit timestamps,
system clock UTC):
- EARLIEST_DURABLE_EVENT: commit `ef5d892` 2026-10-03T23:55:40+0700
  (2026-10-03T16:55:40Z);
- LATEST_DURABLE_EVENT: commit `4dba81e` 2026-10-04T00:25:19+0700
  (2026-10-03T17:25:19Z);
- SPAN_BASIS = 2026-10-03T23:55:40+0700 → 2026-10-04T00:25:19+0700
  (≈ 30 m). ACTIVE_TIME_EXACT = UNKNOWN.

**0C — Semantic call accounting** (`semantic_call_accounting_011.json`),
resolving "34 attempts" vs "zero retries":
- HTTP_CALL_ATTEMPTS = 41 (1 discovery + 4 probes + 19 harness-defect
  POSTs (doubled models/ URL: 2 probes + 17 run1-attempt) + 17 valid
  evaluations);
- VALID_SEMANTIC_EVALUATIONS = 17 (one per non-lineage control);
- RETRIES = 0 (the harness-defect POSTs received HTTP 404 at an invalid
  endpoint — no semantic evaluation occurred to retry; each control has
  exactly one valid evaluation row). The durable counter
  `eval_calls_used = 34` counted POST ATTEMPTS, not valid evaluations —
  the accounting corrects that semantics without rewriting history.

**0 — Custody freeze.** Full Package-011 offline battery re-run clean
(809 passed; SoT 30/30; compileall/diff-check clean; recovery matrix
83/83). Frozen: **PACKAGE-011_TECHNICAL_DELIVERY = PROVEN** while
preserving SEMANTIC_QC_NOT_QUALIFIED (GEMINI_3_5_FLASH_LITE),
CONTENT_AUDIO_PRODUCTION_UNQUALIFIED, TIMED_CAPTION_AUTHORITY_UNAVAILABLE,
OWNER_REVIEW_REQUIRED.
**Corrected Package-010 wall-time basis:** SPAN_BASIS
2026-10-03T22:11+0700 → 2026-10-03T23:35:13+0700 (≈1 h 24 m);
ACTIVE_TIME_EXACT = UNKNOWN (recorded in the 010 custody append; the
erroneous "21:48→24:30" field preserved as history).
**Package-011 wall-time basis:** session 2026-10-03 23:40+0700 → 01:20+0700
(2026-10-04); durable commit span 2026-10-03T17:11Z (ef5d892) →
2026-10-04T18:1xZ (delivery); ACTIVE_TIME_EXACT = UNKNOWN.

## 1. Semantic error observability (S1)

`src/film_pipeline/semantic_errors.py`: the SEMANTIC_API_UNAVAILABLE
umbrella is preserved for backward-compatible fail-closed handling while
every failure now carries `internal_class` (8 evidence-based classes incl.
SEMANTIC_RATE_OR_QUOTA_LIMIT / AUTH / PERMISSION_DENIED / MODEL_UNAVAILABLE
/ SERVICE_UNAVAILABLE / RESPONSE_MALFORMED / LINEAGE_FAILURE /
UNKNOWN_EXTERNAL_ERROR), the raw sanitized `provider_class`, HTTP status,
Retry-After, and a truncated token-redacted detail. 13 tests
(`tests/test_semantic_errors_011.py`) cover 429±quota, 401, 403,
404/model, 408/504, 5xx, malformed success, SDK-without-HTTP,
Retry-After, redaction, and the evaluator integration path.

## 2. Credential + model discovery (S2)

- Credential: Owner file `D:\API KEY\gemini_api_key.txt` loaded into
  process memory ONLY; **credential accepted**; the key never printed,
  persisted, or embedded in exceptions (state files store only
  "accepted" — grep-verified).
- Read-only discovery: 61 models visible. **Frozen selection:
  `models/gemini-3.5-flash-lite`** (the Owner-preferred Gemini 3.5 Flash
  Lite; fallback 3.1 Flash Lite also present but unused). Frozen at
  discovery, BEFORE any evaluation request.
- Health probes: probes 1–2 were **HARNESS_URL_DEFECT** (doubled
  `models/` prefix in the probe URL — recorded as failures, never
  retried against the service); after the harness fix, probes 3 and 4
  both PASS (HTTP 200, <1 s) on the frozen model →
  **SEMANTIC_SERVICE_HEALTHY_FOR_QUALIFICATION**.

## 3. Frozen-corpus requalification (S3/S4)

- Corpus: EXACTLY the frozen Package-006 corpus
  (`qualification_corpus.json`, 18 controls — 8 POSITIVE / 8 NEGATIVE /
  1 AMBIGUOUS / 1 MUST_REJECT_LINEAGE), corpus hash recorded; zero
  relabeling, zero threshold changes.
- **Run 1** (`qualification_011.json`): 17 evaluation calls + 1 pre-API
  lineage rejection; **0 API errors** (the availability gate that blocked
  Package-006/006-R1 is GONE on the frozen 3.5-flash-lite model).
  Frozen acceptance A–L applied as-is:
  A schema 18/18 · B/C lineage+wrong-source-reject PASS ·
  **D positives 6/8 · E negatives 7/8** · F ambiguous observed FAIL ·
  G errors fail-closed PASS (0 errors) · I/J/K/L by construction.
- **Verdict: SEMANTIC_QC_NOT_QUALIFIED** — the frozen acceptance is NOT
  met. Precise mismatches: action_positive (PASS→FAIL, conf 0.95),
  scene_transition_positive (PASS→FAIL, conf 0.95),
  lighting_negative (FAIL→INCONCLUSIVE), ambiguous (INCONCLUSIVE→FAIL).
- Run 2 NOT executed: the package authorizes the repeat ONLY if run 1
  passes. The residual gate is **model capability against the frozen
  corpus, not service availability** — the first precise classification
  of this gate across 006/006-R1/011.
- Call accounting: 34 evaluation calls total (17 × run1 + 17 × the
  aborted first run1 attempt with the URL defect), probes 4, discovery
  calls excluded by contract; caps 80 / ≤10 RPM / 0 retries — all
  honored. NO model switch after the first evaluation request.
- S5 (30-shot backfill) and S6 (master semantic review): **SKIPPED per
  package rule** (authorized only after qualification).

## 4. Owner Take Review Packet (S7)

`review/owner_review_packet_011.json` — 4 entries (F2C, G2C, E2C, G3C):
canonical slot, source spec, selected take, asset hash, provider output
identity, editorial range (full JSON), reference lineage, 3-frame
deterministic contact sheets (sha-recorded), technical QC, semantic
status NOT_AVAILABLE, and the reason for review. No subjective
self-approval anywhere.

## 5. Narration + captions (S8–S10)

- S8: five read-only surfaces scanned (repo projects/fixtures, Story Auto
  runtime + evidence, AutoVideoPipeline). Audio/transcript files exist on
  other-story surfaces, but **no candidate carries lineage to the
  canonical swordsman film** → no adoption. `narration_discovery_011.json`.
- S9: skipped (no authoritative source).
  **CONTENT_AUDIO_PRODUCTION remains UNQUALIFIED** — no fake narration.
- S10: no authoritative timed transcript exists for the current project →
  **TIMED_CAPTION_AUTHORITY_UNAVAILABLE**; no SRT/VTT fabricated.

## 6. Delivery contract + bundle (S11–S13)

- `src/film_pipeline/delivery.py`: immutable finalized DeliveryManifest
  (identity minted over sorted entries; post-finalize edits detected),
  relative paths enforced, role vocabulary closed, media-type binding,
  duplicate roles refused, undeclared-file detection. 10 tests.
- Bundle `projects/flow_semantic_delivery_011/delivery_011/`:
  `master/master_editorial_010_v1.mp4` (byte-copy of the frozen 010
  receipt), `poster/delivery_poster_frame.png` (DELIVERY_POSTER_FRAME:
  SEQ4_A1 @ 4.0 s, deterministic extraction, repo-relative provenance,
  NOT a marketing thumbnail), `qc/` (technical QC + semantic verdict +
  conformance + release readiness), `review/owner_review_packet.json`,
  `manifests/delivery_manifest.json` + `provenance.json`,
  `SHA256SUMS.txt` — 6 finalized manifest entries, all verified.
- **ZIP `DELIVERY_011.zip`**:
  sha256 `e61f1ca42b28aa08bd74674f0985bb100769655ad5bf2cd16fa79856893b3698`
  — **deterministic** (3 consecutive builds → identical hash; fixed
  timestamps, sorted paths). Contains no credentials, browser state,
  cookies, signed URLs, or absolute private paths (poster provenance
  relativized).

## 7. Delivery conformance + release readiness (S14/S15)

- Conformance PASS: manifest↔files 6/6 verified, 0 missing, 0 checksum
  mismatches, self-describing artifacts enumerated, master identity ==
  010 receipt, forbidden-artifact scan (19 tokens: 007 post-gate, 008
  successors + continuation, 008 canary media, Shot-3C) → 0 hits.
- Release gates (explicit, un-collapsed): VISUAL_TECHNICAL_READY ✓ ·
  SEMANTIC_QC_READY ✗ · CONTENT_AUDIO_READY ✗ · CAPTIONS_READY ✗ ·
  OWNER_TAKE_REVIEW_READY ✓ (packet built; Owner judgment pending) ·
  DELIVERY_BUNDLE_READY ✓.
- **release_status = OWNER_REVIEW_REQUIRED** (+ semantic and audio
  content gates). TECHNICAL_DELIVERY_PROVEN is explicitly distinct from
  RELEASE_READY; RELEASE_CANDIDATE is NOT claimed.

## 8. Recovery matrix (S16) — 83/83 PASS

`recovery_matrix_011.json`: custody 4, observability 11, model freeze 7,
qualification 9, semantic production 9, narration 10, captions 8,
delivery 17, readiness 8 — every row with ID/acceptance/proof/result.

## 9. Adversarial findings → outcomes

1. Key material: never persisted (state JSON stores "accepted" only);
   exception messages redacted (AIza/sk-/32+-char tokens);
   `semantic_errors.sanitize_detail` tested.
2. Discovery/probe URL defect (doubled `models/`) — harness bug, honestly
   recorded as failed probes 1–2; fixed; qualifying pair taken fresh.
3. Absolute local paths in delivery metadata → relativized.
4. ZIP determinism verified across 3 builds (identical hash).
5. Secret-scan scoping: scanner marker literals and redaction-test
   fixtures (obviously-fake keys) excluded from leak detection — with the
   rationale recorded in the scan code.
6. Semantic results grant ZERO provider mutation authority (package rule
   + interface by construction).

## 10. Final verification

- **809 passed, 0 failed** (787 + 22 new) — full network-free regression
  incl. Packages 004→010, semantic recovery 006 suite, upload classifier,
  authority, render lifecycle, editorial, delivery.
- Recovery matrix 83/83; SoT manifest 30/30; `compileall` clean;
  `git diff --check` clean; secret/PII/API-key scan clean.

## 11. Unresolved unknowns

1. SEMANTIC_QC_NOT_QUALIFIED: the frozen acceptance (D 8/8, E 8/8,
   H stability) is not met by `gemini-3.5-flash-lite` (D 6/8, E 7/8,
   ambiguous→FAIL). Whether ANY model can meet it is untested (budget
   forbids switching after start). Requalification triggers unchanged.
2. Whether the 2 positive-control FAILs (action, scene_transition) are
   corpus-frame edge cases or true model blindness — UNKNOWN (single-run
   evidence; repeat unauthorized).
3. CONTENT_AUDIO_PRODUCTION gate: no authoritative narration source
   exists in any allowed surface — OWNER decision whether one will be
   produced.
4. Cost UNKNOWN (no billing data).

## 12. Production-readiness impact

The semantic gate is now DIAGNOSED (capability, not availability) with
precise per-control evidence; the delivery pipeline exists end-to-end and
is deterministic + independently conformant; the release state is honest
and gated. What remains for RELEASE_READY is Owner review + either a
semantic model that passes the frozen corpus or an Owner waiver, plus
authoritative narration content.

Recommended next LARGE package: **FLOW-OWNER-REVIEW-AND-RELEASE-012** —
Owner take review of the 4 successors + narration production decision +
semantics re-run (3.1 Flash Lite fallback or a higher-capability model,
Owner-authorized) + final release packaging.

## 13. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
