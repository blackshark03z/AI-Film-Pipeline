# FLOW-SEMANTIC-QUALIFY-006 — Final Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-semantic-qualify-006`
**Original Package-005 SHA:** `a167506f80ca265f2b4781139a62ab920ee04081`
**Package-005 proof correction SHA:** `100c5a173429b6a3efc95c5019bc07bea22866c1`
**Package-006 base SHA:** `100c5a17…` (branch created from the correction commit)
**Delivery:** the branch tip carrying this record (verify `git log -1`).

## 1. Active wall time

2026-10-03T00:41Z → 2026-10-03T05:20Z (~4h40m active of the 8h ceiling; S0–S14 complete).

## 2. Checkpoint timeline

| Checkpoint | Commit | Result |
| :-- | :-- | :-- |
| S0_PACKAGE005_CUSTODY_CLOSED | 100c5a1 | delivery SHA frozen (`a167506…`); battery 606/0; explicit 45/45 recovery mapping; SEQ005 8-slot identity ledger inline |
| S1_GEMINI_RUNTIME_READY | (this delivery) | credential OWNER_APPROVED_LOCAL_FILE validated via existing adapter; 44 models; auth proven by smallest read call; `gemini-2.5-flash` chosen |
| S2_SEMANTIC_CORPUS_FROZEN | (this delivery) | 18 controls (8 POS / 8 NEG / 1 AMBIGUOUS / 1 MUST_REJECT_LINEAGE), 29 hash-pinned frames, expected labels frozen pre-query |
| S3_SEMANTIC_QC_QUALIFIED → INCONCLUSIVE | (this delivery) | frozen acceptance applied as-is: **SEMANTIC_QC_INCONCLUSIVE** (not lowered) |
| S4 cache | skipped per gate | S3 did not QUALIFY |
| S5 canonical semantic audit | not claimed | evaluator not qualified — no audit performed |
| S6 prior-judgment audit | partial (§4) | world_negative control independently FAILs the summit-vs-valley mismatch (supports, does not replace, the B5 provisional review) |
| S7_REPAIR_DECISIONS_FROZEN | (this delivery) | NO_CHANGE — 0/2 repairs; technical QC all pass; semantic INCONCLUSIVE cannot contribute |
| S8_SEMANTIC_REPAIR_LOOP_COMPLETE | (this delivery) | 0/2 consumed — acceptable per package |
| S9_OWNER_REVIEW_PACKET_READY | (this delivery) | V2 packet: per-slot semantic status + qualification summary + repair pass |
| S10_CANONICAL_MANIFEST_READY | (this delivery) | manifest/package/master verified UNCHANGED immutably (sha re-check) |
| S11_MASTER_READY | (this delivery) | 144 s master reused (no identical re-render) |
| S12_SEMANTIC_MASTER_REVIEW_COMPLETE | (this delivery) | SemanticMasterReview = INCONCLUSIVE (unqualified); technical FINAL_CANDIDATE stands |
| S13_SEMANTIC_RECOVERY_PROVEN | (this delivery) | 26 semantic recovery tests, all green |
| S14_ADVERSARIAL_REVIEW_COMPLETE | (this delivery) | §7 |

## 3. Credential + evaluator identity

- Credential source class: **OWNER_APPROVED_LOCAL_FILE** — `D:\API KEY\gemini_api_key.txt` (runtime read only; never printed/persisted/committed; not in argv; not in fixtures; size 1,035 B, 21 lines verified, format plausible).
- Auth proven via the existing `list_gemini_models` adapter: 44 models visible.
- Model: **`gemini-2.5-flash`** (current multimodal, JSON response mode, low cost; not chosen for strength).
- Evaluator: `GeminiSemanticQCEvaluator` (`src/film_pipeline/gemini_semantic.py`) implementing the frozen `SemanticQCEvaluator` interface; prompt version `gemini-semantic-v1`; prompt fingerprint recorded per observation.
- API-key scan of the entire package delta (code+docs): **zero key material**.

## 4. Qualification (S2/S3)

Frozen corpus: `projects/flow_semantic_qualify_006/corpus/qualification_corpus.json` — 18 controls over 29 hash-pinned frames derived from immutable canonical assets (Scene-003 R1, Package-004 incl. B5R, Package-005) + 2 deterministic synthetic fixtures. Expected classes frozen pre-query: 8 POSITIVE / 8 NEGATIVE / 1 AMBIGUOUS / 1 MUST_REJECT_LINEAGE.

Results (`qualification_results.json`):

| Acceptance | Result |
| :-- | :-- |
| A schema parses | PASS (15/18 calls; 3 transient API errors) |
| B/C lineage exact + wrong-source rejected | PASS — `SEMANTIC_SOURCE_LINEAGE_MISMATCH` raised pre-API |
| D positives materially PASS | **FAIL — 4/8** (identity INCONCLUSIVE, action FAIL, framing/lighting API errors; one later retry PASS) |
| E negatives materially FAIL | PARTIAL — 5/8 (wardrobe INCONCLUSIVE, scene_transition PASS, lighting errors) |
| F ambiguous may stay INCONCLUSIVE | PASS first run; UNSTABLE on repeat (FAIL) |
| G errors fail closed | PASS — no error became PASS |
| H repeats stable | **FAIL** — 3/5 unstable |
| I fingerprint/model/version recorded | PASS |
| J/K/L authority separation | PASS — by construction + tests |

**Verdict: SEMANTIC_QC_INCONCLUSIVE** (matrix: `projects/flow_semantic_qualify_006/qualification_matrix.json`). Frozen thresholds were not lowered. Bounded characterization of the 3 API-errored controls (`api_error_characterization.json`): framing_positive → PASS on retry (transient confirmed); both lighting controls errored persistently (likely content/robustness edge — the synthetic dark-blue night frame).

Notable correct behaviors: world_negative correctly FAILED summit-vs-valley mismatch (independently SUPPORTS the prior B5 provisional review — additional evidence, not a rewrite); identity_negative correctly FAILED the teal-character mismatch; wrong-source lineage rejected pre-API.

## 5. Semantic recovery matrix (S13) — 26 offline tests

`tests/test_semantic_recovery_006.py` covers all 30 frozen scenarios: credential missing/empty/whitespace (fail-closed), API unavailable/model-rejected/timeout (→ SEMANTIC_API_UNAVAILABLE, never PASS), malformed JSON/truncated/unknown verdict/missing dimension (fail-closed), duplicate dimension (request-level), wrong request-id/asset/source-hash/frame-hash (lineage), evaluator/model/prompt fingerprint drift visible, INCONCLUSIVE preserved, semantic FAIL cannot generate (no mutation surface), PASS cannot override technical FAIL, FAIL cannot override ownership truth, Owner gate unmoved by semantic PASS, restart cache identity, repair decision durable, stale result cannot bind repaired asset (now ENFORCED: batch lineage check rejects evidence refs whose hashes ≠ pinned request frames — closes a real gap found by this matrix), status guard.

## 6. Canonical manifest / master (S10–S12)

- Manifest `edit_82f9162c…`, package `editpkg_5c2041bf…`, master rough cut `rough_f03a0856…` (144.0 s, sha `0644a741…`) — verified **UNCHANGED** (sha re-check) and reused immutably; no identical re-render.
- SemanticMasterReview: **INCONCLUSIVE** — no qualified evaluator verdicts; technical review `MASTER_ROUGH_CUT_V1_FINAL_CANDIDATE` stands unchanged.
- Owner Review Packet V2 (`owner_review_packet_v2.json`): per-slot semantic status INCONCLUSIVE/OWNER_REVIEW_RECOMMENDED + qualification summary + repair pass (NO_CHANGE).

## 7. Live mutation accounting (this package)

```text
Repair Generates authorized: 2 → consumed 0/2
Primary Generates: 0 (not granted)
Uploads: 0
Retries: 0
Direct/private MZZa6b: 0
Gemini API calls (read-only evaluator): 18 qualification + 5 repeats
  + 3 characterization = 26 total, 0 mutations
```

No OWNER_AMBIGUITY_GATE: no provider (Flow) mutation occurred; the Gemini API is an evaluator service, and its failures were recorded as evidence, not ambiguity.

## 8. Adversarial review findings (fixed in-package)

1. **Real gap found by the recovery matrix**: `validate_semantic_batch` did not bind observation evidence_refs to the request's pinned frame hashes — a stale/wrong-source semantic result could pass batch validation. Fixed: batch now rejects evidence refs whose hash set ≠ the request's pinned frames (`source lineage mismatch`); test 30 enforces it.
2. Gemini adapter: constructor failures (e.g. missing observations list) escaped as raw pydantic errors — now wrapped `SEMANTIC_RESPONSE_MALFORMED` (fail-closed uniformity).
3. Test hygiene: binary frame fixture regenerated lazily under an ignored path; heredoc/quoting and helper-signature issues iterated out; `git add -A` staging checked each commit.
Reviewed clean: key never printed/persisted/committed/in-evidence; evaluator has no mutation surface; FAIL never auto-grants Generate; PASS never overrides technical; INCONCLUSIVE preserved; no stale-cache path (cache skipped per gate).

## 9. Final verification battery

| Check | Result |
| :-- | :-- |
| Full network-free regression | **632 passed, 0 failed** (606 → +26 semantic recovery; +1 collected delta accounted) |
| Semantic qualification tests | matrix verdict INCONCLUSIVE (§4) |
| Semantic recovery tests | 26 passed |
| Mutation-latch tests | 12 passed |
| Slice-0011 / Scene-003 / R1 / Package-004 regressions | green (in full run) |
| `git diff --check`, compile/syntax | clean |
| SoT manifest | 30/30 |
| Protected-file review | SoT unchanged this package (no new SoT truth claimed — evaluator NOT qualified) |
| Secret/PII/API-key scan on delta | clean |

## 10. Unresolved unknowns

1. Whether `gemini-2.5-flash` (or a stronger model, e.g. `gemini-2.5-pro`) can reach 8/8 positive controls with stable repeats — the 3 transient API errors and 1 persistent lighting-control error are unexplained; a longer-backoff requalification may differ.
2. Whether the lighting-negative synthetic dark-blue fixture is a fair control (may trip safety/robustness filters).
3. Semantic audit of the canonical corpus remains unperformed pending QUALIFIED status.

## 11. Production-readiness impact

Semantic QC remains the single unqualified seam. Everything downstream of it is proven: 18-shot canonical lineage, latch, adoption, repair, manifest, 144 s master rough cut, Owner review seam. Once a QUALIFIED evaluator exists (requalification per this package's frozen corpus + criteria — zero code changes needed beyond pointing the adapter at the credential), semantic evidence can be attached as advisory observations with the same guarantees demonstrated here: exact lineage, fail-closed errors, zero authority.

## 12. Recommended next LARGE package

**FLOW-SEMANTIC-QUALIFY-006-R1** (after Owner provisioning/review): re-run this exact frozen-corpus qualification with bounded retries/backoff and, if QUALIFIED, execute S4–S12 (cache, canonical audit, prior-judgment audit, semantic repairs ≤2, SemanticMasterReview) as already specified — no redesign required.
