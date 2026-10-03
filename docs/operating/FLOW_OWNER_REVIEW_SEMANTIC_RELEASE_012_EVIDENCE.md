# FLOW-OWNER-REVIEW-SEMANTIC-RELEASE-012 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-owner-review-semantic-release-012`
**Package-011 exact starting SHA:** `4dba81e567b348f5baf0f418f7e1fd12640e9981`
**Package-011 custody-correction SHA:** `3af6c069e4a1f7b0d271f9645bdd0b371f2987e6`
**Package-012 base SHA:** `3af6c069e4a1f7b0d271f9645bdd0b371f2987e6`
**Delivery:** the branch tip carrying this record (`git rev-parse HEAD`).
**Corrected Package-011 wall-time basis:** SPAN_BASIS
2026-10-03T23:55:40+0700 (`ef5d892`) → 2026-10-04T00:25:19+0700
(`4dba81e`, ≈30 m); ACTIVE_TIME_EXACT = UNKNOWN (recorded in the 011
custody append; the erroneous "17:11Z→18:1xZ" wording preserved there).
**Package-012 wall-time basis:** session 2026-10-04 00:40→02:10 +0700;
CLOCK_SOURCE = git commit timestamps + state-file probe timestamps;
ACTIVE_TIME_EXACT = UNKNOWN.

## 1. Phase 0 — Package-011 custody closed (R0)

- **0A:** exact 011 delivery SHA `4dba81e…` pinned (no branch-tip identity).
- **0B:** wall-time corrected from durable git evidence; historical
  wording preserved in the correction note.
- **0C:** `semantic_call_accounting_011.json` — the "34 attempts vs zero
  retries" contradiction resolved from durable artifacts:
  | Class | Count |
  |---|---:|
  | MODEL_DISCOVERY_CALLS | 1 |
  | HEALTH_PROBE_CALLS | 4 (2 valid PASS + 2 harness-defect 404) |
  | HARNESS_DEFECT_HTTP_CALLS | 19 (doubled `models/` URL: 2 probes + 17 run1-attempt POSTs) |
  | VALID_SEMANTIC_EVALUATION_CALLS | 17 |
  | VALID_EVALUATION_RETRIES | 0 |
  | TOTAL_EXTERNAL_HTTP_ATTEMPTS | 41 |
  The durable `eval_calls_used = 34` counter counted POST ATTEMPTS (17
  defect + 17 valid), not valid evaluations — the accounting corrects
  that semantics without rewriting history. Zero-retry proof: every
  harness-defect call received HTTP 404 at an invalid endpoint (no
  semantic evaluation occurred to retry); each of the 17 non-lineage
  controls has exactly ONE valid evaluation row.
- Full 011 battery re-run clean (809 passed; SoT 30/30; matrix 83/83).
  Frozen: **PACKAGE-011_TECHNICAL_DELIVERY = PROVEN** preserving
  GEMINI_3_5_FLASH_LITE = NOT_QUALIFIED, CONTENT_AUDIO_PRODUCTION_
  UNQUALIFIED, TIMED_CAPTION_AUTHORITY_UNAVAILABLE, OWNER_REVIEW_REQUIRED.
- Custody commit `3af6c06` = Package-012 base.

## 2. Harness revalidation (R1)

`normalize_model_id` — exactly ONE canonical model-id normalization path:
discovery ids with a `models/` prefix and bare ids both normalize to the
bare id; empty/whitespace refused; the evaluator normalizes on
construction (a doubled `models/models/` route can never recur). 5 tests.

## 3. Gemini 3.1 Flash Lite qualification (R2–R4)

- Discovery: 61 models; **`models/gemini-3.1-flash-lite` discovered +
  frozen BEFORE any evaluation**; credential accepted (process memory
  only; state files store "accepted" only).
- Health probes A and B: both PASS (HTTP 200, 1.5/2.0 s) on the frozen
  model.
- **Run 1** (frozen 006 corpus, hash identical to 006/011 truth; original
  acceptance A–L unchanged): 15 evaluated + 2 HTTP 503
  SERVICE_UNAVAILABLE (action_negative, scene_transition_positive) +
  1 pre-API lineage rejection. **D 3/7, E 6/7, ambiguous → FAIL.**
- **Verdict: GEMINI_3_1_FLASH_LITE_NOT_QUALIFIED.** Run 2 NOT executed
  (run 1 did not pass). No model switch, no prompt/config/corpus change,
  no retries. 17 valid evaluation calls (budget 34) + 2 probes.
- The 2×503s are recorded with sanitized classification
  (SEMANTIC_SERVICE_UNAVAILABLE / UNAVAILABLE) — evidence the provider
  side also contributes intermittent unavailability on this model.

## 4. Model comparison (R5) — `semantic_model_comparison_012.json`

**Classification: BOTH_NOT_QUALIFIED** (diagnostic only). Control-level
evidence: both models fail identity/wardrobe/world/action positives;
3.1 alone correctly rejects scene_transition_negative (3.5 wrongly
passed it... 3.5 observed FAIL — recorded exactly); 3.5 alone showed
lighting INCONCLUSIVE where 3.1 returned FAIL. No composite leaderboard,
no acceptance change. The frozen warning stands: two model failures do
NOT support "Gemini cannot do semantic QC".

## 5. Canonical backfill + master review (R6/R7)

**SKIPPED per package rule** (authorized only for a qualified model).
No production semantic calls were made (0 of the 40 authorized).

## 6. Owner Review Packet V2 (R8)

`owner_review_packet_012.json`: the 4 successor entries (F2C/G2C/E2C/G3C
with specs, takes, hashes, output identities, ranges, contact-sheet
hashes, technical QC) PLUS semantic context (both models' verdicts +
mismatched control ids + the 2×503 details), the model comparison
classification, and the explicit Owner decision request: accept the
NOT_QUALIFIED semantic gate, authorize a higher-capability model
attempt, or waive semantic QC for this film. No auto-approval.

## 7. Narration/caption gates (R9/R10)

Read-only recheck: no new authoritative narration exists.
**CONTENT_AUDIO_PRODUCTION_UNQUALIFIED** preserved;
`narration_production_requirement_012.json` freezes the 6 mandatory
provisions for any future narration source (story binding, text
authority, voice provenance, audio hash/rate/channels, timed-transcript
expectations, licensing). **TIMED_CAPTION_AUTHORITY_UNAVAILABLE**
preserved; `caption_production_requirement_012.json` freezes the 5
mandatory provisions (bound transcript, ordering, bounds ≤ 194.541667 s,
UTF-8, lineage). No audio or subtitle synthesis.

## 8. Delivery 012 + determinism + conformance (R11–R13)

- `delivery_012/`: canonical master (byte-copy, receipt-verified),
  poster, technical QC, 010 conformance, **Owner Review Packet V2**,
  DeliveryManifest (9 entries), provenance, SHA256SUMS, semantic verdict
  (both models) + comparison receipt, narration/caption requirement
  documents. Roles extended (semantic_receipt, narration_requirement,
  caption_requirement).
- **DELIVERY_012.zip** sha256
  `ade642639dab04e87510bdb659b162c887c5f07d10635badf4b200a5cd07de1a` —
  **ARCHIVE_DETERMINISM_PROVEN: 3 consecutive builds identical.** (The
  initial nondeterminism was NTFS rglob member ordering; fixed with an
  explicit POSIX-path sort — a real root-cause fix, and the 011 builder
  received the same fix.)
- Conformance PASS: 9/9 manifest entries verified, 0 undeclared
  (self-describing artifacts enumerated), forbidden-artifact scan
  extended to 22 tokens (007 post-gate, 008 successors + continuation,
  008 canary media, **010 session-reuse canaries**, Shot-3C) → 0 hits;
  master identity == 010 receipt.

## 9. Release readiness (R14)

Eight separate gates:
VISUAL_TECHNICAL_READY ✓ · UPLOAD_CONTRACT_READY ✓ · EDITORIAL_READY ✓ ·
DELIVERY_BUNDLE_READY ✓ · SEMANTIC_QC_READY ✗ (both models) ·
OWNER_TAKE_REVIEW_COMPLETE ✗ (packet ready, Owner pending) ·
CONTENT_AUDIO_READY ✗ · TIMED_CAPTIONS_READY ✗.

**RELEASE_PROFILE:** TECHNICAL_FILM_ASSET_RELEASE = **READY** ·
FINAL_CONTENT_RELEASE = **GATED** (semantic + narration + captions +
Owner review). release_status = **OWNER_REVIEW_REQUIRED**. No gate was
weakened to claim completion.

## 10. Recovery matrix (R15) — 97/97 PASS

`recovery_matrix_012.json`: custody 6, harness 4, discovery 6, freeze 6,
qualification 15, comparison 4, production 11, master semantic 5, owner
review 5, narration 6, captions 5, delivery 16, readiness 8.

## 11. Final verification

- **814 passed, 0 failed** (809 + 5 route tests) — full network-free
  regression incl. Packages 004→011.
- SoT manifest 30/30; `compileall` clean; `git diff --check` clean.
- External calls this package: 1 discovery + 2 probes + 17 valid corpus
  evaluations = 20 (budget 34+2+40); 0 retries; ≤10 RPM enforced
  (6 s interval); no other external surface.
- Secret scan clean (credentials never persisted; exceptions redacted).

## 12. Unresolved unknowns

1. Whether ANY Gemini model meets the frozen corpus acceptance — two
   tested NOT_QUALIFIED; higher-capability models untested (out of
   authority).
2. The 2×503s on 3.1: transient provider-side unavailability (no retry
   authorized) — impact on D/E scores UNKNOWN.
3. Owner decisions pending: semantic gate (accept/waive/escalate),
   narration production, caption production.
4. Cost UNKNOWN (no billing data).

## 13. Production-readiness delta

The release boundary is now fully SPECIFIED: a deterministic, conformant
delivery candidate exists with an honest two-profile readiness model; the
semantic question is narrowed to model capability with two models
evidenced; the narration and caption paths have frozen adoption
contracts a future content source can be validated against mechanically.

Recommended next LARGE package: **FLOW-FINAL-RELEASE-013** — Owner
decisions (take review + semantic gate + content production), then
final content release packaging if gates resolve.

## 14. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
