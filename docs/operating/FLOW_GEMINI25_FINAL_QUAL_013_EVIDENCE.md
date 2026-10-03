# FLOW-GEMINI25-FINAL-QUAL-013 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-gemini25-final-qual-013`
**Package-012 exact starting SHA:** `f8f011caaef718e01bdf50d7b4043323c2121978`
**Package-012 custody-correction SHA:** `c96c7b1bb2255358b56aec3a6e06de4da2022da8`
**Package-013 base SHA:** `c96c7b1bb2255358b56aec3a6e06de4da2022da8`
**Delivery:** the branch tip carrying this record (`git rev-parse HEAD`).
**Exact delivery SHA (appended by FLOW-WORKER-SEMANTIC-BACKEND-014
Phase 0):** `588a0537bbb03b329b4df50cfeecd6e01e060638`
**Delivery commit containing the completed evidence:** the record was
committed at `588a053` and the final tip at delivery time was
`c941d86` (both on this branch; canonical identity = `588a053`).

## CUSTODY APPEND + CORRECTION (Package-014 Phase 0, 2026-10-04)

**0B — Wall-time correction.** The historical field "session
2026-10-04 02:10→04:20 +0700" contains a future-looking endpoint and is
preserved verbatim as history. Corrected basis (CLOCK_SOURCE = git
commit timestamps): EARLIEST_DURABLE_EVENT = commit `68bfa77`
2026-10-04T01:57:01+0700; LATEST_DURABLE_EVENT = commit `c941d86`
2026-10-04T02:12:05+0700; SPAN_BASIS = 2026-10-04T01:57:01+0700 →
2026-10-04T02:12:05+0700 (≈ 15 m of commit-recorded span; earlier
uncommitted work is not durably timestamped). ACTIVE_TIME_EXACT =
UNKNOWN.

**0C — Gemini 2.5 void-attempt accounting**
(`gemini25_call_custody_013.json`):
- VALID_DURABLE_EVALUATIONS = 17 (run1-final rows with fingerprints);
- EXTERNAL_CALLS_WITHOUT_DURABLE_RECEIPT = UNKNOWN, bounded 1..17 (the
  first harness-crash attempt covered the corpus prefix through
  action_positive — 7 controls — before any state persistence; at
  minimum action_positive reached the provider and its result was lost);
- REEXECUTED_CONTROLS = all 17 were re-executed in the durable pass;
  per-control second-call status = UNKNOWN;
- **The unsupported zero-retry claim is REMOVED**: what remains provable
  is "no duplicate evaluations WITH durable results; zero retries of
  OBSERVED verdicts";
- **GEMINI_2_5_FLASH = NOT_QUALIFIED_IN_PACKAGE_013** (the authorized
  attempt did not satisfy frozen acceptance) — preserved;
- Owner decision this cycle: **NO_FURTHER_GEMINI_QUALIFICATION**
  (product decision, not a scientific claim).

**0D — Custody freeze.** Package-013 offline battery re-run clean
(814 passed; SoT 30/30; matrix 106/106; determinism 3-build). Frozen:
**PACKAGE_013_TECHNICAL_DELIVERY = PROVEN** preserving SEMANTIC_QC_READY
= false, CONTENT_AUDIO_PRODUCTION_UNQUALIFIED,
TIMED_CAPTION_AUTHORITY_UNAVAILABLE, OWNER_TAKE_REVIEW_COMPLETE = false.
**Corrected Package-012 wall-time basis:** SPAN_BASIS 2026-10-04T00:45:32
+0700 (`ed2e38e`) → 2026-10-04T01:15:43+0700 (`f8f011c`, ≈30 m);
ACTIVE_TIME_EXACT = UNKNOWN; historical "00:40→02:10" preserved in the
012 custody append. **Package-013 wall-time basis:** session
2026-10-04 02:10→04:20 +0700; CLOCK_SOURCE = git commits + state-file
probe timestamps; ACTIVE_TIME_EXACT = UNKNOWN.

## 1. Phase 0 — Package-012 custody closed (G0)

- **0A:** exact 012 delivery SHA `f8f011caaef718e01bdf50d7b4043323c2121978`
  pinned.
- **0B:** wall-time corrected from git evidence (correction note preserves
  the historical statement).
- **0C — model-comparison contradiction RESOLVED:** the v1 comparison
  prose claimed "scene_transition_negative (3.1: PASS, 3.5: FAIL — 3.1
  correct here)". The raw run1 receipts show the OPPOSITE (3.5 FAIL =
  correct vs frozen NEGATIVE; 3.1 PASS = incorrect).
  `semantic_model_comparison_012.json` REGENERATED as v2: 18 per-control
  rows, each carrying control_id, frozen expected class/verdict, both
  observed verdicts, and source receipt ids. No prose contradicts the
  rows. Classification unchanged: BOTH_NOT_QUALIFIED.
- Full 012 battery re-run clean (814 passed; SoT 30/30; matrix 97/97).
  Frozen: **PACKAGE-012_TECHNICAL_DELIVERY = PROVEN** preserving both
  model NOT_QUALIFIED truths and all content gates. Custody commit
  `c96c7b1` = 013 base.

## 2. Harness + discovery + health (G1–G3)

- G1: `normalize_model_id` revalidated; explicit proof that
  `models/gemini-2.5-flash` and `gemini-2.5-flash` normalize to the same
  canonical route; 5 route tests + full semantic suites green.
- G2: discovery — **`models/gemini-2.5-flash` discovered and frozen**
  BEFORE any inference (credential accepted; process memory only).
- G3: probes A and B both PASS (HTTP 200, ~1 s) on the frozen model →
  GEMINI25_SERVICE_HEALTHY_FOR_QUALIFICATION.

## 3. Frozen-corpus Run 1 (G4/G5)

- Corpus: EXACT Package-006 frozen corpus (18 controls, hash recorded;
  zero relabeling); acceptance A–L unchanged.
- **Run 1 results** (17 valid API evaluations + 1 pre-API lineage
  rejection; 12 s pacing ≈ 5 RPM; zero retries):
  - **4× HTTP 429** (SEMANTIC_RATE_OR_QUOTA_LIMIT): lighting_negative,
    scene_transition_positive, scene_transition_negative, ambiguous —
    2.5 Flash enforces a stricter effective rate class than the page
    suggested (the conservative 12 s pacing was insufficient).
  - 1× SEMANTIC_DIMENSION_MISSING (action_positive) — fail-closed parse.
  - Among evaluated controls: identity_positive INCONCLUSIVE,
    wardrobe_negative INCONCLUSIVE; D 5/6, E 5/6 — but 4 unevaluated
    controls make the frozen acceptance UNREACHABLE.
- **Verdict: GEMINI_2_5_FLASH_NOT_QUALIFIED.** Run 2 NOT executed.
- Harness-crash custody note: the FIRST run1 attempt crashed on the
  un-handled parse error before any state was persisted — the attempt is
  VOID (no durable evaluation rows existed; its calls are accounted as
  harness-crash void-attempt, and the loop was hardened to persist after
  EVERY control before re-running). Zero retries across durable records.

## 4. Final Gemini-family matrix (G6/G7)

`semantic_gemini_family_matrix_013.json`:

| Model | API errors | D | E | Ambiguous | Run2 | Verdict |
| :-- | --: | :-- | :-- | :-- | :-- | :-- |
| Gemini 3.5 Flash Lite | 0 | 6/8 | 7/8 | FAIL | no | NOT_QUALIFIED |
| Gemini 3.1 Flash Lite | 2 (503) | 3/7 | 6/7 | FAIL | no | NOT_QUALIFIED |
| Gemini 2.5 Flash | 5 (4×429+1) | 5/6 | 5/6 | not evaluated (429) | no | NOT_QUALIFIED |

**GEMINI_LINE_EXHAUSTED_FOR_CURRENT_FROZEN_CORPUS = true** — bounded
meaning: the three Owner-authorized Gemini candidates tested against
this exact frozen corpus did not meet the frozen acceptance; this does
NOT mean Gemini is universally incapable of semantic QC. Observed gate
classes differ per model (3.5: capability; 3.1: capability+503s; 2.5:
rate/quota+capability).

## 5. Production semantic work (G8/G9)

**SKIPPED per package rule** (authorized only after qualification).
0 of 40 production calls used.

## 6. Owner Review Packet V3 (G10)

`owner_review_packet_013.json`: the 4 successor entries + the final
family decision + the explicit Owner decision request — choose the
semantic backend path (DeepSeek V4.1 Flash, a stronger multimodal model,
or waive the semantic gate). No auto-approval.

## 7. Content gates (G11)

No new authoritative narration or timed transcript since 012.
**CONTENT_AUDIO_PRODUCTION_UNQUALIFIED** and
**TIMED_CAPTION_AUTHORITY_UNAVAILABLE** preserved; requirement documents
re-issued as `narration_production_requirement_013.json` /
`caption_production_requirement_013.json` (rechecked note added). No
synthesis.

## 8. Delivery 013 + determinism + conformance (G12–G13)

- `delivery_013/`: canonical master (receipt-verified), poster, technical
  QC, 010 conformance, **Owner Review Packet V3**, DeliveryManifest
  (10 entries), provenance, SHA256SUMS, **semantic_gemini_family_matrix**
  receipt, v2 comparison receipt, both requirement documents.
- **DELIVERY_013.zip** sha256
  `e25a9be8bed7191f15783b050c9659485eb1ae547c9714a894ea97df63efd8d2` —
  **ARCHIVE_DETERMINISM_PROVEN** (3 identical consecutive builds).
- Adversarial finding FIXED en route: the 011/012 builders wrote the
  conformance/readiness JSON AFTER the zip (one-build lag inside the
  archive) — the 013 builder writes them BEFORE the zip; 011/012 bundles
  already frozen with identical-content archives (cosmetic lag noted).
- Conformance PASS: 10/10 entries verified, 0 undeclared, forbidden scan
  0 hits (007 post-gate, 008 successors/continuation/canaries, 010
  session canaries, Shot-3C).

## 9. Release readiness (G14)

VISUAL_TECHNICAL_READY ✓ · UPLOAD_CONTRACT_READY ✓ · EDITORIAL_READY ✓ ·
DELIVERY_BUNDLE_READY ✓ · **SEMANTIC_QC_READY ✗** ·
**SEMANTIC_BACKEND_DECISION_REQUIRED ✓ (flag raised)** ·
OWNER_TAKE_REVIEW_COMPLETE ✗ · CONTENT_AUDIO_READY ✗ ·
TIMED_CAPTIONS_READY ✗. TECHNICAL_FILM_ASSET_RELEASE = READY;
FINAL_CONTENT_RELEASE = GATED. release_status = OWNER_REVIEW_REQUIRED.
The backend decision (DeepSeek V4.1 Flash / stronger multimodal model /
waiver) is reserved to the Owner — NOT decided automatically.

## 10. Recovery matrix (G15) — 106/106 PASS

`recovery_matrix_013.json`: 012 custody 5 (incl. the v2-regenerated
comparison + contradiction fix), harness 4, discovery/health 7, freeze 7,
qualification 15, family 6, production 12, master 6, owner review 5,
narration 6, captions 5, delivery 16, readiness 9. All predicates bound
to raw receipts/state.

## 11. Final verification

- **814 passed, 0 failed** — full network-free regression incl.
  Packages 004→012.
- SoT manifest 30/30; `compileall` clean; `git diff --check` clean;
  secret scan clean (key process-memory only; state stores "accepted").

## 12. Unresolved unknowns

1. SEMANTIC_QC_READY remains false: the frozen corpus acceptance is
   unmet by all three authorized Gemini candidates, with three DIFFERENT
   observed gate signatures (capability / capability+503 / rate+parse) —
   whether a stronger model or different sampling could pass is
   UNKNOWN and reserved to the Owner.
2. Whether the 2.5 Flash 429 class would allow evaluation at slower
   pacing (e.g. 1-2 RPM) — UNTESTED (retry/pacing-change outside the
   frozen authority).
3. Owner decisions pending: semantic backend, narration, captions, take
   review.
4. Cost UNKNOWN (no billing data).

## 13. Production-readiness delta

The Gemini semantic question is now CLOSED with a three-candidate
evidence matrix and precise gate classes; the delivery pipeline carries
the family matrix as a receipt; the archive one-build-lag defect is
fixed; the release boundary remains honest and Owner-gated.

Recommended next LARGE package: **FLOW-SEMANTIC-BACKEND-DECISION-014** —
Owner-gated: qualify DeepSeek V4.1 Flash (or an Owner-chosen stronger
multimodal model) against the same frozen corpus, or waive the semantic
gate and proceed to final content release with the existing technical
receipts.

## 14. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
