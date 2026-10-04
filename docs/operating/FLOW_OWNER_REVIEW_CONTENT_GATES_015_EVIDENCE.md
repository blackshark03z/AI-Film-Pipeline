# FLOW-OWNER-REVIEW-CONTENT-GATES-015 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE
acceptance)
**Branch:** `zcode/flow-owner-review-content-gates-015`
**Package-014 exact starting SHA:**
`3c9c1f06e48eba947ebd360c677916079331d0f6`
**Package-014 custody-correction SHA:**
`b477249b2b42dd2eb05bc04bde04e42dbc8b8c0b`
**Package-015 base SHA:** `b477249b2b42dd2eb05bc04bde04e42dbc8b8c0b`
(ancestry re-verified from
`81a4419e8164d7883f32735ad2ea90a8003b665e`)
**Delivery:** the branch tip carrying this record
(`git rev-parse HEAD`). **Wall-time basis:** CLOCK_SOURCE = git
commits; ACTIVE_TIME_EXACT = UNKNOWN.
**External spend:** 0 external AI calls, 0 Flow Generates, 0 Flow
uploads, 0 TTS. Zero visual mutation of the canonical lineage.

## 1. Phase 0 — Package-014 custody closed + truth corrected

- **0A:** `PACKAGE_014_ORIGINAL_DELIVERY_SHA =
  3c9c1f06e48eba947ebd360c677916079331d0f6` pinned in the 014 evidence
  record (section 19); custody-correction commit `b477249` = Package-015
  base.
- **0B — corrected worker semantic truth (durable):**
  - `WORKER_SEMANTIC_BACKEND = NOT_QUALIFIED`
  - `WORKER_SEMANTIC_REVIEW_MODE = PROVISIONAL_OWNER_ASSIST`
  - `SEMANTIC_AUTONOMOUS_READY = false`
  Reason: Package-014 Pass 1 did NOT meet the frozen 006 corpus
  acceptance (positives 2/8, negatives 6/8, ambiguous mismatch). The
  historical label "PROVISIONAL_SINGLE_PASS" was a misapplied
  classification — valid only if Pass 1 had met the frozen acceptance
  but repeatability was unavailable. Correction keys appended to
  `worker_qualification_receipt_014.json` and
  `temporary_backend_policy_014.json` (historical fields preserved
  verbatim; no silent rewrite); the replacement contract gained
  section 13 recording the correction.
- **0C — stale-wording exclusion proof:** the 30-shot production
  review, master boundary review and consistency audit remain valid as
  `PROVISIONAL_OWNER_ASSIST_REVIEW` (unchanged label). Historical
  wording intentionally preserved in frozen custody + builders: the
  frozen `delivery_014/` bundle + `DELIVERY_014.zip`, the 014-era
  builders (`build_delivery_014.py`, `build_worker_qualification_014.py`),
  014 matrix rows 91/109 (asserting the historical recorded state), and
  014 evidence sections 6/13 — all superseded by the correction keys +
  contract section 13 + the Package-015 readiness model. No stale
  wording remains as an ACTIVE qualification verdict: the Delivery-015
  bundle carries the corrected classification
  (`corrected_classification_in_bundle: true` in its conformance
  record).
- **0D — battery:** full Package-014 offline battery re-run clean after
  the corrections: **829 passed** (pre-correction baseline also 829;
  014 matrix 115/115 PASS; SoT manifest 30/30).
  **PACKAGE_014_TECHNICAL_ARCHITECTURE = PROVEN**:
  SEMANTIC_BACKEND_NEUTRAL_BOUNDARY = PROVEN ·
  WORKER_PACKET_IMPORT_BOUNDARY = PROVEN ·
  SEMANTIC_BACKEND_REPLACEMENT_CONTRACT = PROVEN ·
  WORKER_SEMANTIC_BACKEND = NOT_QUALIFIED ·
  WORKER_OWNER_ASSIST_MODE = AVAILABLE ·
  SEMANTIC_AUTONOMOUS_READY = false.
- Branch `zcode/flow-owner-review-content-gates-015` created from the
  custody commit. **O0_PACKAGE014_CLOSED.**

## 2. Owner review as a first-class contract (Phase 1-2)

`src/film_pipeline/owner_review.py` — extends (not parallels) the
existing owner-review packet lineage:

- `OwnerReviewRequest` (owner-review-request-v1): binds
  review_request_id, project, canonical shot/sequence/scene, ShotSpec
  identity (exact spec sha), SelectedTake, Asset id + sha256, provider
  media identity, reference lineage, EditorialRange payload, technical
  QC, optional advisory semantic review, deterministic contact-sheet
  locator, reel locator, the exact reason review is required, and the
  derived `bindings()` (asset hash + take + range id + spec sha + master
  sha) a decision must carry verbatim. SHOT vs MASTER scopes validated.
- `OwnerReviewDecision` (owner-review-decision-v1): decision_id,
  review_request_id, exact reviewed bindings, decision ∈ {ACCEPT,
  REJECT, NEEDS_REPAIR, DEFER}, optional note, decided_at,
  decision_source = OWNER (Literal), owner_identity. **A decision
  against different asset/hash fails closed.** Worker/model output can
  NEVER create one: schema Literal + `refuse_worker_origin` marker scan
  (WORKER_REVIEW / worker backend ids / reviewer_identity /
  packet_digest / harness_identity / API_MODEL) on mint, record and
  import.
- `OwnerDecisionLedger` (owner-decision-ledger-v1): durable JSON with
  per-decision payload digests (tamper detected on reload), duplicate
  refusal (decisions immutable), conflicting second decision only via
  explicit `SupersessionRecord` (superseded decision never deleted),
  DEFER leaves the request unresolved, `provider_mutation_authority()`
  structurally NONE.
- 17 tests (`tests/test_owner_review_015.py`) covering the twelve
  frozen authority scenarios. **O1_OWNER_REVIEW_CONTRACT_PROVEN ·
  O2_OWNER_AUTHORITY_BOUNDARY_PROVEN.** The conceptual chain is
  enforced: review finding → OwnerReviewDecision → future Tech Lead
  RepairDecision / fresh work package → provider mutation authority.
  Owner ACCEPT/REJECT/NEEDS_REPAIR never triggers Generate (tests
  assert no mutation artifacts appear and the authority stays NONE).

## 3. Owner review set (Phase 3)

`projects/flow_owner_review_content_gates_015/owner_review_set_015.json`
— **review_set_id `reviewset_218a04d7116a47717a6da41c8f355245576517d3
985daec6b7a54da5c8e2c72c`**, 5 requests:

1. OWNER-REV-015-001 — SEQ7_E2 (successor SEQ7_E2C)
2. OWNER-REV-015-002 — SEQ7_F2 (successor SEQ7_F2C)
3. OWNER-REV-015-003 — SEQ7_G2 (successor SEQ7_G2C)
4. OWNER-REV-015-004 — SEQ7_G3 (successor SEQ7_G3C)
   (the four historically mandatory clean successors, in canonical
   master order; each binds exact take/asset/range/spec hashes,
   contact-sheet sha, technical QC, and the 014 advisory row clearly
   labeled PROVISIONAL_OWNER_ASSIST with the NOT_QUALIFIED backend
   note)
5. OWNER-REV-015-005 — MASTER scope: the only existing Package-014
   advisory item that is INCONCLUSIVE (systemic "visual temporal"
   3-frame sampling limitation). No fake issues: 014 had 0 FAILs, 0
   conflicts, 0 master findings. **O3_OWNER_REVIEW_SET_FROZEN.**

## 4. Fast human review reel (Phase 4)

`OWNER_REVIEW_REEL_015.mp4` — sha256
`a8afd24c5b3002a88d0d02902deaeb8398c8aa4e78f142430bea95271d491872`,
1280x720 @ 24 fps, probed duration 46.125 s (nominal 46.0 s), audio:
none (visual review; narration gate unqualified). Built ONLY from
canonical master assets (edit-manifest sha-verified) using each shot's
frozen editorial-range-v1 trim, in canonical master order, pattern
previous → target → next per target; the two adjacent G targets share
one built window (G1→G4) so context is never duplicated. No textual
overlay burned in (the manifest maps time ranges; no worker verdict is
displayed anywhere). `review_reel_manifest_015.json` maps reel time
ranges → canonical shots/assets → review request ids (5 items; the
master-level request covers the full reel). Validation
(`reel_validation_015.json`): source hashes, canonical ordering, fps,
duration, FULL DECODE — all PASS; forbidden markers (Shot-3C, B5
primary, canaries, post-gate) absent from every resolved asset path.
**O4_OWNER_REVIEW_REEL_PROVEN.**

## 5. Owner decision input surface (Phase 5)

`owner_decisions_015.template.json` (sha256
`0c89f337e4ca0d802ddcc5216e70c32d4a5d4d6b895f67f16a653f00fc2ff137`, 5
items): carries the frozen reviewed bindings + review-set hash; the
Owner only chooses decision + optional note. Importer
(`import_decision_set`) fails closed on: unknown request, missing
request, binding drift (stale asset/take/range), invalid state,
duplicate item, duplicate recorded decision, modified review packet
(review-set hash mismatch), worker-origin markers, malformed JSON.
**O5_OWNER_DECISION_SURFACE_READY.**

## 6. Owner decision replay / simulation (Phase 6)

OFFLINE ONLY, synthetic fixtures in pytest tmp dirs (never canonical
truth): all ACCEPT → owner gate satisfied; REJECT / NEEDS_REPAIR / DEFER
→ review stays blocking; mixed states; stale binding refused;
conflicting decisions require the supersession contract; restart
preserves truth. Canonical production state remains
**OWNER_TAKE_REVIEW_COMPLETE = false** (asserted against the shipped
readiness file). **O6_OWNER_REVIEW_WORKFLOW_PROVEN_OFFLINE.**

## 7. Narration ingestion + handoff (Phase 7-8)

- `NarrationSourceReceipt` (narration-source-receipt-v1) +
  `verify_narration_receipt`: binds project/story authority (id +
  sha), text authority (id + sha), audio locator (repo-relative),
  audio sha256, duration/sample rate/channels, voice + production
  provenance, license note, optional transcript authority. Fails
  closed on wrong project, wrong/unknown story, missing text
  authority, hash drift (source mutation), unsupported audio,
  duration/sample-rate/channel mismatch (re-probed from the actual
  bytes), missing provenance. 10 test modes green. No narration was
  synthesized.
- `narration_handoff_015/`: status
  **NARRATION_TEXT_AUTHORITY_MISSING** (no authoritative narration
  text exists for the canonical film — Package-011 S8/S10 scans,
  unchanged since). Contains project identity, master target duration
  194.541667 s, 30 scene/shot timing references, required output audio
  format (48 kHz, mono/stereo), delivery naming contract, required
  NarrationSourceReceipt fields, transcript/timing expectations. No
  script invented; no model/provider recommendation. **O7 · O8.**

## 8. Timed caption ingestion (Phase 9)

`TimedCaptionSource` (timed-caption-source-v1) + strict SRT/VTT parser:
UTF-8 enforced, malformed timestamps refused, negative start refused,
end ≤ start refused, cues beyond the canonical master duration
(194.541667 s) refused, ordering must increase, **overlapping cues are
refused — never silently fixed**, transcript binding + project/story
binding + caption hash + lineage required. 10 test modes green. No
timing was invented. **O9_CAPTION_INGESTION_PROVEN_OFFLINE.**

## 9. Content input bundle + final release compiler (Phase 10-11)

- `ContentReleaseInputBundle` (content-release-input-bundle-v1):
  optional NarrationSourceReceipt / TimedCaptionSource /
  OwnerReviewDecisionSet / waiver digests; binds exact project +
  canonical master sha + lineage version; validator refuses any
  provider-authority vocabulary; grants ZERO provider generation
  authority.
- `FinalContentReleaseCompiler` dry-run gate report
  (`final_release_gate_report_015.json`): inputs = Package-010 master
  receipt + DeliveryManifest truth + input bundle. Result:
  **FINAL_CONTENT_RELEASE_BLOCKED** with exactly the derived missing
  gates — OWNER_TAKE_REVIEW · SEMANTIC_RELEASE · PRODUCTION_NARRATION ·
  TIMED_CAPTIONS (visual/upload/editorial gates satisfied). Each gate
  row: name, required, current truth, blocking, satisfying artifact.
  The compiler refuses to compile while any gate is blocked (false
  ready refused; a synthetic all-gates-satisfied fixture reaches READY
  in dry-run only). **O10 · O11.**

## 10. Semantic waiver boundary (Phase 12)

Existing product truth (Package-011 release contract, section 12 of its
evidence record: "a semantic model that passes the frozen corpus or an
Owner waiver") **authorizes** the waiver route →
`SEMANTIC_WAIVER_BOUNDARY = AUTHORIZED`
(`semantic_waiver_status_015.json`; no hidden bypass — the waiver is a
recorded Owner decision object). `SemanticQCWaiverDecision`
(semantic-qc-waiver-decision-v1) binds project + exact canonical master
+ reason + known limitations + date + decision_source OWNER. It may
satisfy the semantic RELEASE gate as `SEMANTIC_QC_GATE = OWNER_WAIVED`;
it NEVER rewrites semantic truth to PASS and
SEMANTIC_AUTONOMOUS_READY stays false (schema-enforced Literal + tests
+ wrong-master refusal). No waiver decision exists yet. **O12.**

## 11. Delivery 015 + determinism + conformance (Phase 13-15)

- `delivery_015/` — 24 manifest entries
  (**delivery_id `delivery_6b641995d7d9c08a60dd7fa9eb0d933797c8af591a
  96a8d1f73f62ff761b82ef`**): canonical master (receipt-verified
  byte-copy, unchanged), poster, technical QC + master conformance
  (CONFORMANT, 18 checks + 29 boundaries), the 4 worker advisory
  receipts (corrected classification), owner review set + review reel
  + reel manifest/validation + decision template, backend replacement
  contract, narration requirement + ingestion contract + handoff,
  caption requirement + ingestion contract, ContentReleaseInputBundle
  schema + empty template, final release gate report, semantic waiver
  status, provenance, DeliveryManifest, SHA256SUMS. Excluded: hidden
  qualification expectation data (expectation_manifest_014 not
  shipped), credentials, browser state, cookies, signed URLs, absolute
  private paths, synthetic Owner decision fixtures.
- **DELIVERY_015.zip** sha256
  `6ea3327dcaaec3f67f75d935aa91f72cb42a04ca0a0b59f4c85dcefcb1306354` —
  **ARCHIVE_DETERMINISM_PROVEN** (3 independent builds, identical
  SHA256, normalized POSIX paths, fixed archive timestamps
  2026-10-04T00:00:00).
- Bundle conformance **PASS**: manifest ↔ files (24/24), 0 undeclared,
  master identity == 010 receipt, master + reel full decode, forbidden
  artifact scan 23 tokens 0 hits, absolute-path scan 0 hits, secret
  scan 0 hits, hidden-label leak scan (review surface) 0 hits.
- Independent verifier (`tools/verify_delivery_015.py`) — 20 checks
  **PASS**: manifest/hashes/sizes, master identity + full decode, reel
  identity + full decode + per-segment source lineage (hash-recomputed
  from the canonical assets), decision-template bindings re-validated
  against the review set, narration/caption schema identity, bundle
  binding, gate-report consistency, no undeclared files, forbidden
  lineage scan, **B5R canonical + 009 four successors (E2C/F2C/G2C/
  G3C) canonical**. **O13 · O14 · O15.**

## 12. Release readiness model V3 (Phase 16)

`qc/release_readiness.json` — 13 separate gates, **every value derived
from frozen receipts** (conformance report, 009 authority equivalence,
worker receipts, gate report, handoff): VISUAL_TECHNICAL_READY ✓ ·
UPLOAD_CONTRACT_READY ✓ · EDITORIAL_READY ✓ ·
TECHNICAL_DELIVERY_READY ✓ · WORKER_OWNER_ASSIST_REVIEW_AVAILABLE ✓ ·
SEMANTIC_AUTONOMOUS_READY = **false** · SEMANTIC_RELEASE_GATE =
OWNER_DECISION_REQUIRED (backend NOT_QUALIFIED; waiver AUTHORIZED, not
exercised) · OWNER_TAKE_REVIEW_COMPLETE = **false** ·
NARRATION_INGESTION_READY ✓ (content absent) · CONTENT_AUDIO_READY ✗ ·
CAPTION_INGESTION_READY ✓ (content absent) · TIMED_CAPTIONS_READY ✗ ·
FINAL_CONTENT_RELEASE_READY = **false**. release_status =
OWNER_REVIEW_REQUIRED. **O16_RELEASE_READINESS_V3.**

## 13. Recovery matrix (Phase 17) — 122 scenarios

`recovery_matrix_015.json`: **122 rows** (58 pytest-bound to exact test
nodes; 64 raw-receipt/derivation evidence checks, all PASS) across 014
custody (6), Owner contract (14), review set/reel (13), Owner import
(7), narration (12), captions (10), content bundle (7), semantic (7),
final release compiler (11), delivery (27), readiness (8). Every row:
ID, acceptance, exact test/proof, result. **O17_RECOVERY_MATRIX_PROVEN.**

## 14. Adversarial review (Phase 18) — findings + resolutions

Attacked and resolved:

1. *Stale PROVISIONAL_SINGLE_PASS as verdict* — only preserved verbatim
   inside correction keys / frozen 014 custody (declared inventory,
   section 1); every 015 surface carries NOT_QUALIFIED; delivery
   conformance asserts the corrected classification is present.
2. *Worker treated as qualified* — readiness + review set + provenance
   all carry SEMANTIC_AUTONOMOUS_READY=false / NOT_QUALIFIED.
3. *Owner decision forged by worker/model* — schema Literal +
   refuse_worker_origin on mint/record/import; probes refused
   (tests 03/04 + matrix rows 11/12).
4. *Stale asset/take accepted by importer* — binding equality enforced
   (tests + rows 8/9/37).
5. *Owner rejection auto-generating video* — structurally impossible:
   the Owner module imports no provider code; tests assert zero
   mutation artifacts; bundle validator refuses authority vocabulary.
6. *Review reel using superseded assets* — assets hash-verified against
   the edit manifest + per-range sha; forbidden-token scan on every
   resolved path; independent verifier recomputes lineage.
7. *Worker advisory displayed as truth* — reel has no overlays; review
   set labels advisory rows PROVISIONAL_OWNER_ASSIST with
   NOT_QUALIFIED note.
8. *Narration filename mistaken for authority / fake script / invented
   caption timings* — receipt binds text authority by id+hash; handoff
   records NARRATION_TEXT_AUTHORITY_MISSING and contains no script;
   parser validates only, never generates timings; overlaps refused
   (not fixed).
9. *Bundle binding wrong master* — compiler + verifier refuse
   (different-master tests).
10. *Waiver silently turning QC PASS* — schema Literals + tests prove
    truth unchanged and wrong-master waiver refused.
11. *Compiler weakening gates / stale report* — gate list derived per
    run from live receipts; verifier re-checks gate-report consistency
    against the bundle; compile refuses while blocked.
12. *Synthetic decisions leaking into canonical state* — simulations
    sandbox in tmp dirs; test asserts canonical readiness still false.
13. *Archive hidden answers / secrets / absolute paths /
    nondeterminism* — expectation manifest not shipped; text-surface
    scans 0 hits (binary media proven by hash + decode instead — a
    false-positive loop where the conformance file scanned itself was
    found and fixed by excluding self-describing artifacts); 3-build
    determinism PROVEN.

**O18 complete: all safe findings fixed (scan-scope fix + verifier
lineage fix were the two code changes).**

## 15. Final verification

- **Full network-free regression: 882 passed, 0 failed** (829
  inherited + 53 new: 17 owner-review + 36 content-release) — includes
  Packages 004→014 regression, upload classifier, mutation authority,
  render lifecycle, scene/sequence/production run, EditorialRange,
  audio contract, AutoEdit, master conformance.
- 014 custody verifier: matrix 115/115 PASS; SoT manifest 30/30.
- 015 recovery matrix: 122/122 (58 pytest-bound + 64 evidence PASS).
- `compileall` clean; `git diff --check` clean; secret/PII/API-key
  scan of the bundle 0 hits.

## 16. Unresolved Owner/content gates (by design)

1. **OWNER_TAKE_REVIEW**: import the filled
   `owner_decisions_015.template.json` (5 requests; reel + contact
   sheets ready).
2. **SEMANTIC_RELEASE**: either qualify a future API backend per the
   frozen replacement contract, or record a SemanticQCWaiverDecision
   (route AUTHORIZED; truth stays NOT_QUALIFIED/false).
3. **PRODUCTION_NARRATION**: produce the authoritative narration asset
   + NarrationSourceReceipt (handoff package ready;
   NARRATION_TEXT_AUTHORITY_MISSING until the Owner supplies text).
4. **TIMED_CAPTIONS**: authoritative SRT/VTT bound to the narration
   text (TimedCaptionSource ready; no timing invented).
5. Worker reviewer's exact model version remains UNKNOWN (014
   limitation, unchanged). Cost of this package: 0 external spend.

## 17. Production-readiness delta

Remaining work is now **explicit Owner/content inputs, not unfinished
architecture**: the Owner review boundary is a formal immutable
contract with a decision ledger; the review reel + template make the
Owner pass fast; narration and caption ingestion are fail-closed and
require zero new architecture; the final content release compiler
knows exactly which gates remain and refuses to fake any of them. The
canonical visual lineage is byte-unchanged; zero external AI spend.

## 18. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
