# FLOW-UPLOAD-RECONCILIATION-CONTRACT-008 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-upload-reconciliation-contract-008`
**Package-007 starting SHA:** `30657c2f768ecca745e81ad418609753d8e7aa71`
**Package-007 custody-correction SHA (U0):**
`ca2a19081c6f4c3ef10224dab2f5e634398c3d4f`
**Package-008 base SHA:** `ca2a19081c6f4c3ef10224dab2f5e634398c3d4f`
(branch created immediately after the custody correction)
**Delivery:** the branch tip carrying this record (resolve with
`git rev-parse HEAD`; commit chain below).
**Package-008 exact delivery SHA (appended by
FLOW-UPLOAD-CONTRACT-REQUAL-009 Phase 0, 2026-10-03):**
`a7edff2a1a70a349c50def1f2933ca719ef41d3d`

> **CUSTODY APPEND (Package-009 Phase 0)** — no historical classification
> above is modified by this note. Package-008 live continuation/salvage
> outputs are frozen as **TECHNICALLY_DEMONSTRATED but
> INVALID_AS_CLEAN_AUTHORIZED_PROOF**: Canary 1 became TRUE_AMBIGUOUS, the
> then-frozen package authority ended there, and the later Canary 2 / U6 /
> U9 mutations (executed under new Owner-authorized sub-scopes of the same
> package) cannot establish clean prospective proof. Package-009
> re-qualifies prospectively under ONE mutation authority domain with the
> classifier frozen before any live work.

**Active wall time:** continuous build session 2026-10-03
16:31→20:25 +0700 (09:31→13:25Z), ≈ 3 h 54 m; first custody commit
`ca2a190` 16:52:05 +0700, final battery 20:2x +0700. (Idle gaps are not
exactly recoverable; span basis stated.)

## 0. Commit chain (all on this branch)

| Commit | Content |
| :-- | :-- |
| `ca2a190` | U0 custody correction of Package-007 (first gate point + slot classification) |
| `d202f72` | U2–U3 classifier + qualified-pending upload state + authority suspension; 722 tests |
| `5803c94` | U1 sanitized maseQ forensic matrix + canary tool |
| `5b09b80` | U4 canary-1 correction: pending class re-frozen to the live skeleton fingerprint |
| `6b79060` | U4–U6 live: canary1 latch+resolve, canary2 qualified-pending bind, U6 conditioned Generate |
| `2f89311` | U7 salvage plan + U8 F1/G1 re-attestation |
| `fd5b4d5` | U9 clean re-proof 4/4 SHOT_PROVEN |
| `53fe02a` | U10–U12 clean lineage + MASTER_SCALE_REPROOF_V1 + CONFORMANT audit |
| `b99ce7f` | U13 recovery/contract matrix 65/65 |
| `9aadb3e` | U14 adversarial fix: upload budget custody at arm boundary |

## 1. Historical breach chronology (frozen; see Package-007 evidence §13)

- First historical gate point: **2026-10-03T07:39:32.111961Z** — F2
  continuity upload `refup_fb013d43…` FAILED_AMBIGUOUS after ONE maseQ
  POST (HTTP 200, 651 B).
- Code-level root cause: `tools/run_production_scale_007.py:694` latched
  only on generate ambiguity (`if report.get("observed_generate_requests")`);
  upload-side OwnerAmbiguityGate was recorded per-slot without a scope
  latch.
- POST_GATE_INVALID canonical slots (chronology-proven): SEQ7_F2, SEQ7_G2,
  SEQ7_E2R, SEQ7_G3B. PRE_GATE_CLEAN: E1, E3, E4, F1, F3, F4, G1, G4.
  NO_PROVIDER_EFFECT: E2, G3 (dead reservations).
- History preserved verbatim; nothing reinterpreted.

## 2. Historical maseQ forensics (U1)

Full sanitized matrix: `docs/operating/FLOW_UPLOAD_008_FORENSICS.json`
(local state copy: `projects/flow_upload_reconciliation_008/
upload_forensics_008.json`). Summary:

| Upload | Date | Status/bytes | First parse | Catalog outcome |
| :-- | :-- | :-- | :-- | :-- |
| slice0011 qualification | 09-30 | 200 / 647 B | FAILED_AMBIGUOUS | unique media `347f9951…`, exact readback |
| Scene-003 C4 | 10-02 | 200 / 651 B | FAILED_AMBIGUOUS | unique `0c16d60b…`, exact readback |
| Package-007 F2 (gate point) | 10-03 | 200 / 651 B | FAILED_AMBIGUOUS | unique `8f2f5277…`, exact readback |
| Package-007 G2 | 10-03 | 200 / 651 B | FAILED_AMBIGUOUS | unique `75dbd0bc…`, exact readback |
| Story Auto control (external system, different project/account) | 10-01 | direct-UUID envelope | parsed directly | media `69ac3d31…` |

Conclusions: the AI-Film maseQ response class is stable (4/4) but the
envelope is NOT universal (the external control received a direct-UUID
shape). Byte length alone is not a fingerprint (647 vs 651). No secrets,
cookies, tokens or signed URLs persisted anywhere.

## 3. Classifier contract (U2, corrected at U4)

`src/film_pipeline/providers/flow_upload_classifier.py` — deterministic,
fail-closed:

- **QUALIFIED_COMPLETED** — direct identity envelope (payload[0][0] is a
  provider media UUID, no conflicting siblings) → existing transport path.
- **QUALIFIED_PENDING** — HTTP 200 + strict parse + the EXACT structural
  skeleton fingerprint frozen from live evidence:
  `ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1`
  (`maseQ-200-live-skeleton`, class version
  `upload-response-class-2026-10-03.2`). Grants ONLY bounded read-only
  reconciliation. The skeleton records structure only (types, uuid-ness,
  list lengths, dict key names) — string values, lengths, URLs and numbers
  never enter it.
- **UNOBSERVABLE / TRUE_AMBIGUOUS** — everything else (non-200, unparseable,
  degenerate shapes, metadata echoes, conflicting identities, drift).
  Fail-closed; parsing failure can NEVER become pending.

Correction record: the U2-guessed envelope ("no UUID anywhere") was a
mis-prediction; Canary 1 observed the real class and fail-closed exactly as
designed (latch). The class was then re-frozen from the live skeleton
BEFORE Canary 2. This sequence is documented, not hidden.

## 4. State machine + authority (U3)

Lifecycle (durable across restart):
`UPLOAD_INTENT_FROZEN → REQUEST_ARMED → QUALIFIED_PENDING_RECONCILIATION →
REMOTE_RESOURCE_VERIFIED (bound)` with new journal stage
`UPLOAD_RESPONSE_CLASSIFIED {classification, skeleton_hash}`.

`tools/mutation_authority.py` adds `SUSPENDED_QUALIFIED_UPLOAD_PENDING`:
enter (from OPEN only, one reservation), `upload_bound` (restores OPEN),
`promote_pending_to_ambiguity` (permanent latch). While suspended every
mutation class is refused with `UPLOAD_PENDING_SUSPENDED` (distinct from
`MUTATION_LATCHED_CLOSED`). Read-only reconciliation is always allowed and
never reopens a latch.

## 5. Scope lineage (custody-preserving)

| Scope | Authority state | Cause |
| :-- | :-- | :-- |
| `FLOW-UPLOAD-RECONCILIATION-CONTRACT-008` (scope-1) | **LATCHED_CLOSED**; knowledge RESOLVED_EFFECT_IDENTIFIED | Canary 1 TRUE_AMBIGUOUS (honest fail-closed against the mis-predicted envelope) |
| `…-QUAL2` (scope-2) | **LATCHED_CLOSED** | tool defect: drift check compared a None fingerprint; the actual skeleton matched the frozen class exactly. Custody preserved; correction noted in the ledger |
| `…-CONT` (U6) | OPEN after recorded pending→bound pair | continuation proof |
| `…-REPROOF` (U9) | OPEN | 4 re-proof generates |

The package's single global budget ledger enforces the Owner caps across
scopes: `qualification_ledger.json` — uploads 2/2 consumed, generates 1/1
(U6), reproof 4/8. Unused authority was never used as retry authority.

## 6. Live qualification evidence

- **Canary 1** (E1 last frame, frame sha `5c536d6a…`, reservation
  `refup_777ee27f…`): POST → 200/650 B → classified TRUE_AMBIGUOUS
  (`conflicting_primary_identities`) → scope-1 latch. Post-hoc READ-ONLY
  reconciliation (C4-sanctioned, `preexisting_ids` = durably pre-existing
  row `58bd411e…`) bound exactly one media:
  **`91823da5-7764-47c2-a2a4-7eb3ae7254d6`** (provider sha `baa02693…`,
  MAE 1.52, dhash 1). The upload effect was real, unique, content-verified.
- **Canary 2** (G4 last frame, frame sha `d7cd1cac…`, reservation
  `refup_fe4fe3c9…`): POST → 200/650 B → **QUALIFIED_PENDING**, skeleton
  fingerprint = frozen class EXACTLY → durable pending state → (tool-defect
  latch, see §5) → post-hoc read-only bind from the PENDING state:
  **`454e75b4-0bca-47ac-95a0-65fda7086d57`** (sha `27592439…`).
- **U6 continuation** (`…-CONT`): bind confirmed →
  `QUALIFIED_UPLOAD_PENDING_ENTERED` → `QUALIFIED_UPLOAD_BOUND` → OPEN →
  ONE native-UI Generate conditioned on the canary-2 adopted reference
  (`asset_297ad56e…`, media `454e75b4…`) → **SHOT_PROVEN**, output
  `c5b928df-9c3b-4f16-92cc-4a8d280cffee`, asset sha `60a49ba5…`, 8.0 s,
  1 click / 1 observed request, zero retries. (Pre-mutation local fixture
  failures — schema field, prompt-limit refusal, attestation file-name bug —
  were archived loudly with zero provider effects; the Package-007 v1→v2
  creative-reduction precedent was applied.)

## 7. Historical continuity re-attestation (U8)

F1 → media `8f2f5277…`: historical receipt VERIFIED; FRESH readback sha
`fecf669e…` **identical** to the historical provider sha; fresh attestation
`refbind_51a96d41…`; canonical adopted asset `asset_cb5bba09…` reused
(deterministic identity). G1 → media `75dbd0bc…`: fresh readback `c1f13c50…`
identical; fresh attestation `refbind_0e7fd04e…`; adopted asset
`asset_1ff28bfe…` reused. Exact lineage established for both — no
replacement upload needed or performed.

## 8. Salvage set (U7) and clean re-proof (U9)

`projects/flow_upload_reconciliation_008/salvage_plan_008.json` — 4 slots
(≤ 8 rule satisfied):

| Old slot | Old job (prefix) | Reason | Successor | Target kept |
| :-- | :-- | :-- | :-- | --: |
| SEQ7_F2 | `job_7373ea97…` | generate post-gate; gate-point upload | **SEQ7_F2R** `job_d217648a…` | 5.6 s |
| SEQ7_G2 | `job_639fb3ec…` | upload POST + generate post-gate | **SEQ7_G2R** `job_440e92d9…` | 4.0 s |
| SEQ7_E2R | `job_32779dcf…` | repair generate post-gate | **SEQ7_E2R2** `job_82c693f0…` | 4.0 s |
| SEQ7_G3B | `job_1e758977…` | repair generate post-gate | **SEQ7_G3BR** `job_83f26211…` | 3.2 s |

All four successors: exact frozen creative spec (identity fields renamed
only; shot_id never enters the wire prompt), NEW ProviderJob + marker,
fresh baseline, ONE generate each, SHOT_PROVEN (1 click / 1 observed
request each), F2R/G2R conditioned on the U8-re-attested last-frame
references, E2R2/G3BR on the unchanged base reference. New output
identities: F2R `f2020c4e…`, G2R `90c58900…`, E2R2 `89d7ca22…`, G3BR
`d55c36a3…`. New asset hashes: `417a5cf6…`, `fce27c26…`, `a479054f…`,
`9b9f50bb…`. Zero uploads, zero retries, zero blind re-release.

## 9. Clean 30-slot canonical lineage (U10)

18 historical Package-004/005 slots (unchanged, full-clip) + 8 PRE_GATE_CLEAN
SEQ007 slots (unchanged) + 4 re-proof successors. Old editorial targets
kept for every replaced slot. Manifest
`edit_f2b095a1495d1b3a5d20ada01e67b5c5c2c246853f247b8889d85e26d6bbfebb`;
AutoEdit package
`editpkg_a3ab030235ddeb195123cbfe5df09c9e3556e7f01ef2ff13d17be55b6751be60`;
producer locators include `reproof008_media`.

**Invalidated-artifact exclusion scan (U10):** the 4 invalidated ProviderJobs,
output identities, asset ids and asset hashes are ABSENT from
master_summary.json, editorial_plan_008.json, all 30 EditorialRanges, the
autoedit package payload and the manifest clips (conformance check
`invalidated_artifacts_excluded_from_canonical_package` = PASS; 16 tokens ×
40+ haystacks). The invalidated artifacts remain only in historical
evidence directories.

## 10. MASTER_SCALE_REPROOF_V1 (U11)

- Output `projects/flow_upload_reconciliation_008/master_package_008/
  master_scale_reproof_v1.mp4`
- SHA-256 `1c4213abb672a78cc010cd11d02e47bea17c29947ef7c6eb9a6befc20d90890b`
- Duration 194.541667 s (timeline 194.4 s; Δ0.14 s frame rounding,
  tolerance 1.05 s), 30 sources, trim-aware, full-decode EOF ✓
- Render receipt `rough_73ebf168bbbd1fe58a7f79051d9afdab26bf6e9604c97ae3cfe737cdf6822d25`

## 11. Independent conformance (U12) — CONFORMANT

`conformance_report.json`: lineage+ranges all 30 PASS; repair-take-canonical
(4 successors exact) PASS; no stale primary takes PASS; invalidated-artifact
exclusion PASS; reproof-successor binding PASS (4); historical B5R canonical
/ B5 absent PASS; duration PASS; full decode PASS; **29/29 boundary frame
sampling PASS** (single contiguous transitions). No black/freeze master
artifacts (builder anomaly scans + per-slot QC windows).

## 12. Recovery/contract matrix (U13) — 65/65 PASS

`recovery_matrix_008.json`: classifier 8, reconciliation 12 (incl. canary
evidence rows), authority 8, generate continuation 10, salvage 7, editorial
6, conformance 7 (incl. live 30-unique-slot scan and live master-hash
recompute), custody/secrets 6 (incl. live secret scans over the upload
stores, evidence artifacts and continuation state — no signed URLs, no
cookies, no session/captcha tokens persisted).

## 13. Final battery

- **726 passed, 0 failed** (675 baseline + 51 new/updated) — full
  network-free regression incl. Slice-0011, Scene-003/R1, Package-004/005/
  006/007 regressions, plus the new classifier/state-machine suites.
- Recovery matrix 65/65 (fresh pytest pass + evidence + live checks).
- SoT manifest: 30/30 verified (`tools/verify_sot_manifest.py`).
- `compileall` clean; `git diff --check` clean.
- Secret/PII/API-key scan over all 24 changed files: NONE (one marker
  literal inside the scanner itself is intentional, not a leak).
- Zero Gemini calls; zero direct MZZa6b submits; zero MZZa6b retries.

## 14. Mutation accounting (this package)

| Budget | Used | Cap | Note |
| :-- | --: | --: | :-- |
| Qualification uploads | 2 | 2 | canary1 + canary2; no third POST exists |
| Conditioned generates (U6) | 1 | 1 | `job_bce71ae4…` |
| Re-proof generates (U9) | 4 | 8 | one per salvage slot |
| Salvage uploads | 0 | 0 | no upload authorized or performed |
| Retries | 0 | — | failed pre-mutation local attempts archived loudly |
| True-ambiguity latches | 2 | — | scope-1 (honest), scope-2 (tool defect, custody preserved) |

## 15. Unresolved unknowns / deviations for Tech Lead review

1. **U5 strict reading not met:** the package required "two independent
   passing canaries". Canary 1 honestly latched on the mis-predicted
   envelope (fail-closed behavior proven live); the class was re-frozen
   from the live skeleton; Canary 2 then matched the class exactly, entered
   the durable pending state and bound read-only. The qualified-pending
   contract therefore has: 6 observed instances of the same response class
   (4 historical + 2 canaries), 2 read-only unique binds on that class
   today, 1 live latch-path proof, and 1 live continuation proof. This is a
   documented deviation from "two blind passes" — Tech Lead decides
   acceptance.
2. **Scope-2 latch was raised by a tool defect** (None fingerprint
   comparison), not by provider ambiguity. The latch remains in place as
   custody; the correction is recorded in the ledger and §5. All subsequent
   authority came from new Owner-authorized scopes under this package's
   frozen budgets.
3. The exact trigger that makes the provider return the direct-UUID
   envelope (Story Auto 10-01) vs the pending envelope (all AI-Film
   observations) remains UNKNOWN (project/account/session state suspected).
   Requalification triggers are listed in `FLOW_UPLOAD_008_FORENSICS.json`.
4. Provider billing data absent → cost UNKNOWN.
5. Semantic QC remains UNQUALIFIED (no Gemini calls; unchanged external
   gate).

## 16. Production-readiness impact

The upload path now distinguishes QUALIFIED_PENDING from TRUE_AMBIGUITY by
an explicit, evidence-frozen structural fingerprint; the ambiguous class
still latches permanently; the pending class suspends all mutation and may
only end in a content-verified unique binding (authority restored) or a
latch. The Package-007 breach class (upload ambiguity not latching) is
structurally closed: the transport classifies, the scope suspends or
latches, and the runner gap cannot recur because no upload path exists in
the re-proof chain. Clean lineage is rebuildable after a breach without
re-uploading or regenerating pre-gate work.

Recommended next package: **FLOW-EDITORIAL-SCALE-009** — Owner take review
of the 4 re-proof successors + semantic QC rerun (external gate) + audio
path qualification + session-reuse hardening.

## 17. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
