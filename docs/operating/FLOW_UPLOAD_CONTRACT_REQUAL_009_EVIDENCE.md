# FLOW-UPLOAD-CONTRACT-REQUAL-009 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-upload-contract-requal-009`
**Package-008 exact starting SHA:** `a7edff2a1a70a349c50def1f2933ca719ef41d3d`
**Package-008 custody-correction SHA (V0):**
`56ff7f01bf99da893f5aad56a8dd128d7450f731`
**Package-009 base SHA:** `56ff7f01bf99da893f5aad56a8dd128d7450f731`
**Delivery:** the branch tip carrying this record (`git rev-parse HEAD`;
commit chain below).
**Active wall time:** 2026-10-03 20:44→23:15 +0700 (13:44→16:15Z),
≈ 2 h 31 m continuous single session; custody commit `56ff7f0` 20:52 +0700.

## 0. Commit chain

| Commit | Content |
| :-- | :-- |
| `56ff7f0` | V0 custody freeze of Package-008 (delivery SHA pinned; live outputs frozen TECHNICALLY_DEMONSTRATED but INVALID_AS_CLEAN_AUTHORIZED_PROOF) |
| (pre-A) | single-domain qualification tool + frozen classifier verification + 134 offline tests |
| (V3–V5) | Canary A + Canary B PASS, continuation SHOT_PROVEN |
| (V6–V8) | salvage re-confirm + re-attest + clean 4-slot re-proof 4/4 |
| (V9–V11) | canonical 30-slot + MASTER_SCALE_009_V1 + CONFORMANT audit |
| (V12) | recovery matrix 77/77 + single-domain adversarial fix + guardrail tests |

## 1. Frozen classifier identity (V1 — BEFORE any live work)

- Class version: **`upload-response-class-2026-10-03.2`**
- Qualified pending structural fingerprint:
  **`ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1`**
- Verified from the repo (not from the prompt): module constants +
  `tests/test_upload_classifier_008.py::test_live_frozen_class_is_qualified_pending`.
- Proof of NO change across A/B: both canary frozen intents record the
  classifier git blob sha `73cd69147f00c0e8…`; identical at A and B and
  equal to `HEAD:src/…/flow_upload_classifier.py` at delivery
  (recovery rows 40–42). Zero classifier/fingerprint/threshold/contract
  modification between the canaries.

## 2. One mutation authority domain (absolute rule)

Single scope `FLOW-UPLOAD-CONTRACT-REQUAL-009`, single durable state file
`projects/flow_upload_contract_requal_009/mutation_authority.json`. The
full event chain: PENDING_ENTERED → BOUND (canary A) → PENDING_ENTERED →
BOUND (canary B) → 5× BUDGET_CONSUMED (1 continuation + 4 re-proof) →
CUSTODY_CORRECTION (see §9). Authority OPEN throughout; **no ambiguity
occurred in this package**, so the one-way latch rule was never exercised
live here (it is offline-proven: `test_requal_009_single_domain.py`,
`test_mutation_authority_latch.py`).

## 3. Canary A ledger (V3) — PASS

- Source: SEQ7_E3 asset (PRE_GATE_CLEAN, sha `6b191f0d…`); frame sha
  `e74c5a79…` (never previously uploaded; no provider duplicate at fresh
  baseline: 61 catalog rows, fingerprint `78ca7a1c…` unchanged).
- Reservation `refup_faf4a4ab…`; exactly ONE maseQ POST.
- Response: **QUALIFIED_PENDING**, skeleton fingerprint = frozen class
  EXACTLY → authority SUSPENDED → bounded read-only reconciliation
  (1 round; stable probes; preexisting unresolved row `58bd411e…` covered
  by durable pre-upload evidence) → exactly one strong match → exact
  project binding → content attestation → **UPLOAD_BOUND** → OPEN.
- Provider media: **`08f5f4fb-b358-4136-a61d-f02435b1e157`** (sha
  `44b0de87…`); attestation `refbind_424b5059…`; adopted asset
  `asset_c74a9f1c…`.

## 4. Canary B ledger (V4) — PASS (independent reproduction)

- Source: SEQ7_F3 asset (PRE_GATE_CLEAN, sha `24f05128…` — distinct from
  A); frame sha `649b6cc3…` (distinct, never uploaded).
- Exactly ONE POST → **QUALIFIED_PENDING** (fingerprint exact — no
  classifier change) → SUSPENDED → read-only reconcile (1 round) → unique
  bind → attestation → **UPLOAD_BOUND** → OPEN.
- Provider media: **`65e73642-1140-4cd6-be68-fd8b772bdf4a`** (sha
  `85385775…`); attestation `refbind_4fc822aa…`; adopted asset
  `asset_0ca577d0…`.

**Checkpoint V4:** `UPLOAD_PENDING_RECONCILIATION_PROSPECTIVELY_QUALIFIED`
within the exact observed scope (request class `maseQ` PNG upload;
response fingerprint above; project `93a579b4…`; account
`clean-pro-qualified`; read-only catalog reconcile + exact as29s readback).
`QUALIFIED_PENDING != TRUE_AMBIGUITY`; unknown shapes fail closed;
requalification triggers listed in `FLOW_UPLOAD_008_FORENSICS.json`.

## 5. Post-upload continuation (V5) — SHOT_PROVEN

Canary B's newly bound reference (`asset_0ca577d0…` → media `65e73642…`);
minimal ShotSpec frozen BEFORE the generate
(`fixtures/requal009/V5_CONT.json`); NEW ProviderJob + NEW marker; fresh
baseline; **ONE native-UI Generate: 1 click, 1 observed request**; output
`bab25d49-60b7-4338-b511-2f237876fcc7`; asset sha `89a…` (result.json);
render lifecycle + acquisition + decode + technical QC passed;
`may_submit=false` after release (store semantics). Zero retries.

## 6. Salvage re-confirmation (V6, read-only)

Independently re-derived from durable artifacts
(`tools/reconfirm_salvage_009.py` → `salvage_reconfirm_009.json`):
PRE_GATE_CLEAN = E1, E3, E4, F1, F3, F4, G1, G4 (8);
POST_GATE_INVALID = exactly **SEQ7_F2, SEQ7_G2, SEQ7_E2R, SEQ7_G3B** (4);
NO_PROVIDER_EFFECT = E2, G3. Salvage set size 4 — no BLOCKED_INVARIANT.

## 7. Continuity re-attestation (V7, zero upload)

F1 → media `8f2f5277…`: fresh readback sha `fecf669e…` identical to the
historical provider sha; fresh attestation `refbind_51a96d41…`. G1 → media
`75dbd0bc…`: fresh readback `c1f13c50…` identical; fresh attestation
`refbind_0e7fd04e…`. Exact lineage proven today, not assumed.

## 8. Clean four-slot re-proof (V8) — 4/4 SHOT_PROVEN

New deterministic successor identities (Package-008 successors NOT reused
as proof); exact frozen creative specs (identity fields renamed only);
original editorial targets kept:

| Canonical slot | 009 successor | ProviderJob | Output identity | Asset sha |
| :-- | :-- | :-- | :-- | :-- |
| SEQ7_F2 | **SEQ7_F2C** | `job_9b52476a…` | `20cfe9c0…` | `e84ba56c…` |
| SEQ7_G2 | **SEQ7_G2C** | `job_51d51d0d…` | `abc9461b…` | `5fac2f01…` |
| SEQ7_E2 | **SEQ7_E2C** | `job_98172eac…` | `b2168549…` | `b96d1fd8…` |
| SEQ7_G3 | **SEQ7_G3C** | `job_fa40f8bf…` | `dfd86f9e…` | `ffe42e7e…` |

F2C/G2C conditioned on the V7-re-attested last-frame references; E2C/G3C
on the unchanged base reference. Each: unique attribution, exact project,
render complete, acquisition exact, full decode, technical QC,
provisional editorial range from the ORIGINAL frozen target (5.6 / 4.0 /
4.0 / 3.2 s), `may_submit=false` after release. Zero retries, zero
uploads.

## 9. Adversarial finding and custody correction (V12)

**Finding:** `run_reproof_009.py` initially instantiated the SAME
scope_id against a SUB-DIRECTORY state file
(`…/reproof/mutation_authority.json`) — a fresh OPEN authority that could
have evaded a canary latch (the "new scope loophole", caught in review
before delivery; no ambiguity ever occurred, so no latch was evaded in
fact).

**Correction:** tool fixed to bind the shared root file; the 4 re-proof
BUDGET_CONSUMED events were merged into the shared authority file with
their ORIGINAL timestamps and a CUSTODY_CORRECTION event; the fragment is
archived as `…/reproof/mutation_authority_fragment_defect.json` (never
erased). New guardrail tests (`test_requal_009_single_domain.py`, 5 tests)
pin: every 009 tool binds the package-root authority and only the package
scope id; a latched shared state refuses every later entry class.

## 10. Clean canonical 30-slot lineage (V9–V11)

18 historical Package-004/005 slots + 8 Package-007 PRE_GATE_CLEAN slots +
4 Package-009 clean successors. Excluded from the canonical package
(exclusion scan, 24 tokens × all summary/plan/ranges/package/manifest
haystacks, zero leaks): Package-007 post-gate-invalidated artifacts
(F2, G2, E2R, G3B), **Package-008 re-proof successors
(F2R, G2R, E2R2, G3BR)**, **the Package-008 continuation-test asset
(U6_CONT)**, and the historical invalid **Shot-3C** lineage
(`job_fe0a5e73…`, `cae6e2a5…`, `asset_0ff2d6bb…`, `c94b2c0c…`).

- EditManifest: `edit_54ce6b6bdc38cca8d9ceb84ddff8bb1d52ed22515e657a08cfdb9898d898cd2c`
- AutoEdit package: `editpkg_487a4975c91a362ac877ca9d97d16952182810e528cd0c133b55b978ba83fade`
- Render receipt: `rough_e7ff5dea15030988ff84505596d867ce89800a8bbd85f972bd580b537c9c542c`
- **MASTER_SCALE_009_V1:**
  `projects/flow_upload_contract_requal_009/master_package_009/master_scale_009_v1.mp4`
  SHA-256 `976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595`,
  duration 194.541667 s (timeline 194.4 s; Δ0.14 s frame rounding),
  30 sources, trim-aware, full-decode EOF ✓.

**Conformance (V11) — CONFORMANT:** lineage+ranges 30/30 PASS; 009
successor binding 4/4 PASS; no stale takes PASS; exclusion scan PASS;
B5R canonical / B5 absent PASS; duration PASS; full decode PASS;
**29/29 boundary frame sampling PASS** (single contiguous transitions).

## 11. Recovery/contract matrix (V12) — 77/77 PASS

`recovery_matrix_009.json` — the package's mandated scenario list
(IDs 1–78, 73 undefined by the package): classifier 10, pending 16,
ambiguity 11 (incl. the single-domain evidence row 37), qualification 9,
continuation 8, salvage 7, editorial/master 12, security 5 (live scans:
no raw upload bodies, no signed URLs, no cookies, no session/CAPTCHA
tokens, no API keys).

## 12. Final verification

- **731 passed, 0 failed** (726 baseline + 5 new single-domain guardrail
  tests) — full network-free regression incl. Slice-0011, Scene-003/R1,
  Package-004/005/006/007/008 regressions.
- Recovery matrix 77/77 (fresh pytest pass + evidence + live checks).
- SoT manifest 30/30; `compileall` clean; `git diff --check` clean.
- Zero Gemini calls; zero direct MZZa6b; zero retries anywhere.

## 13. Mutation accounting (this package)

| Budget | Used | Cap |
| :-- | --: | --: |
| Qualification uploads (Canary A + B) | 2 | 2 |
| Conditioned Generate (V5) | 1 | 1 |
| Re-proof Generates (V8) | 4 | 4 |
| Additional uploads | 0 | 0 |
| Retries | 0 | — |
| **Total provider releases** | **7** | **7** |

## 14. Unresolved unknowns

1. What makes the provider return the direct-UUID envelope instead of the
   pending envelope remains UNKNOWN (never observed on this
   project/account across 6 uploads; triggers frozen in the forensics
   record).
2. Provider billing data absent → cost UNKNOWN.
3. Semantic QC remains UNQUALIFIED (external gate; no Gemini calls).

## 15. Production-readiness delta

The upload-pending contract is now prospectively qualified under a
pre-frozen classifier with two independent live passes, one continuation
proof, and a clean lineage rebuild that excludes every prior package's
invalid or superseded artifacts — with a single, latch-safe authority
domain enforced by source-level guardrail tests. The historical breach
classes (upload ambiguity not latching; scope fragmentation) are closed
structurally and by test.

Recommended next LARGE package: **FLOW-EDITORIAL-SCALE-010** — Owner take
review of F2C/G2C/E2C/G3C + semantic QC rerun when the external API gate
clears + audio path qualification + per-shot session-reuse hardening.

## 16. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
