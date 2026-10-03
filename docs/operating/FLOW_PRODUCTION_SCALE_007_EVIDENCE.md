# FLOW-PRODUCTION-SCALE-007 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-production-scale-007`
**Base SHA:** `671f685400639ed58ccdd5990cc8e1591028fb0b` (Package-007 branch
point = semantic-R1 custody-freeze commit; verify `git log --oneline -3`)
**Delivery:** the branch tip carrying this record (verify `git log -1`).

## 0. Custody chain

| Item | SHA |
| :-- | :-- |
| Original semantic-R1 delivery | `78832fee6f42a924108954d9c3c0d91e91eec478` |
| Custody correction (freeze append) | `671f685400639ed58ccdd5990cc8e1591028fb0b` |
| Package-007 base | `671f685400639ed58ccdd5990cc8e1591028fb0b` |

Ancestry verified (`git merge-base --is-ancestor`): `7ca82d2…` (Package-006)
→ `78832fe…` (semantic-R1) → `671f685…` (freeze) → this package.
Durable semantic truth unchanged: credential VALID; qualification
INCONCLUSIVE; blocking class SEMANTIC_API_AVAILABILITY_GATE; exact external
cause UNKNOWN. Zero Gemini calls in this package.

## 1. Checkpoint timeline (L0–L17)

| Checkpoint | Commit / proof |
| :-- | :-- |
| L0_CUSTODY_FROZEN | `671f685` (append to R1 evidence; classification unchanged) |
| L1_LARGE_RUN_ORCHESTRATOR_READY | `ecc7a2e` — `tools/scale_run.py` + 20 offline tests (30-slot, restart×3, order/drift/duplicate/cross-project refusals) |
| L2_SEQUENCE_C_FROZEN | `1bd32e6` (v1) → `75924ac` (v2, pre-mutation creative reduction; zero mutations consumed by v1) |
| L3_PRIMARY_12_COMPLETE | 10 direct SHOT_PROVEN + 2 dead reservations with custody (`5b69f0a` machinery); canonical 12/12 after repairs |
| L4_CONTINUITY_COMPLETE | 2/2 uploads (F2←F1, G2←G1), both armed-then-`reconcile_only`-resolved read-only; `bd69298`, `e7349ed` |
| L5_EDITORIAL_RANGE_PROVEN_OFFLINE | `4c02208` — `src/film_pipeline/editorial_range.py` + 15 tests |
| L6_30_SHOT_TIMING_PLAN_READY | ranges/ (30 EditorialRanges; historical full-clip; live = frozen targets in usable windows) |
| L7_QC_COMPLETE | per-slot technical QC + decode in `build_master_scale_007.py`; 12/12 pass, semantic = OWNER_REVIEW_RECOMMENDED |
| L8_REPAIR_LOOP_CLOSED | E2R + G3B proven under durable RepairDecisions (`rd_5d16ca…`, `rd_0cb587…` ids in files); budget 2/3 |
| L9_EDITORIAL_PLAN_READY | `editorial_plan_007.json` — transitions CUT/HARD_SCENE_BREAK/MATCH_CUT; pacing metrics; anomalies: none |
| L10_TRIMMED_MASTER_V1_PROVEN | MASTER_SCALE_V1 rendered trim-aware (see §6) |
| L11_MASTER_CONFORMANCE_PROVEN | `audit_master_scale_007.py` → CONFORMANT, 29/29 boundaries |
| L12_MASTER_ITERATION_CLOSED | V1 review clean → **MASTER_SCALE_V1_FINAL_CANDIDATE** (no V2 justified) |
| L13_AUDIO_BOUNDARY_MAPPED | **AUDIO_PRODUCTION_PATH_NOT_YET_QUALIFIED** (audio exists only as prompt intent + probe metadata; no narration/music/lanes boundary) |
| L14_SCALE_RECOVERY_PROVEN | `recovery_matrix_007.py` → **58/58 scenarios PASS** |
| L15_TELEMETRY_COMPLETE | `telemetry_007.json` (§7) |
| L16_SCALE_HARDENED | measurements recorded (§8); no unmeasured optimization; no contract-breaking change |
| L17_ADVERSARIAL_REVIEW | findings fixed in-package (§9) |

## 2. Frozen Sequence C (v2)

`fixtures/sequence007/sequence_plan_007.json` — SEQ007_DAYLIGHT_ROAD,
3 scenes × 4 shots; plan SHA-256 `b76ccd4b6154b4012991d3a6b04fb4b2131fcb16fb1a7696a7dd1960d40dd1ed`
(over shot ids/fixtures/continuity/frozen editorial targets).
v1 freeze (`1bd32e6`) never reached a Generate: 10/12 fixtures were refused
at the compact-prompt gate (500 chars / 75 words) BEFORE any provider
effect; v2 applied the required explicit creative reduction with the same
shots, narrative functions, continuity mechanisms and frozen editorial
targets. Attempt-1 state archived at
`projects/flow_production_scale_007_archive/attempt1_v1plan_prompt_limit_refusal`
(authority OPEN, events: []).

Frozen editorial targets (NOT provider durations, never tuned post-hoc):
E1 6.0, E2 4.0, E3 3.2, E4 2.4 | F1 4.8, F2 5.6, F3 3.2, F4 2.0 |
G1 5.6, G2 4.0, G3 3.2, G4 6.4 — scene sums 15.6 / 15.6 / 19.2 = 50.4 s.
Continuity: same-reference everywhere except two pre-committed within-scene
last-frame slots (SEQ7_F2←SEQ7_F1, SEQ7_G2←SEQ7_G1).

## 3. ProviderJob ledger (12 required slots + 2 repair successors)

| Slot | Gate | ProviderJob (prefix) | Asset dur | Bytes |
| :-- | :-- | :-- | --: | --: |
| SEQ7_E1 | SHOT_PROVEN | `job_827856ff…` | 8.0 | 7,724,120 |
| SEQ7_E2 | DEAD_RESERVATION | `job_ba8eaa52…` | — | — |
| SEQ7_E3 | SHOT_PROVEN | `job_3751fdc2…` | 8.0 | 2,284,706 |
| SEQ7_E4 | SHOT_PROVEN | `job_91e6899e…` | 8.0 | 5,883,941 |
| SEQ7_F1 | SHOT_PROVEN | `job_0e6e6851…` | 8.0 | 5,921,594 |
| SEQ7_F2 | SHOT_PROVEN | `job_7373ea97…` | 8.0 | 4,855,749 |
| SEQ7_F3 | SHOT_PROVEN | `job_55327b8f…` | 8.0 | 2,198,059 |
| SEQ7_F4 | SHOT_PROVEN | `job_dd93eb1d…` | 8.0 | 2,368,179 |
| SEQ7_G1 | SHOT_PROVEN | `job_5fbb44c1…` | 8.0 | 2,845,983 |
| SEQ7_G2 | SHOT_PROVEN | `job_639fb3ec…` | 8.0 | 2,273,020 |
| SEQ7_G3 | DEAD_RESERVATION | `job_3569503a…` | — | — |
| SEQ7_G4 | SHOT_PROVEN | `job_4613cea5…` | 8.0 | 6,127,725 |
| SEQ7_E2R (repair) | SHOT_PROVEN | `job_32779dcf…` | 8.0 | 2,132,751 |
| SEQ7_G3B (repair) | SHOT_PROVEN | `job_1e758977…` | 8.0 | 1,857,749 |

Dead reservations: both consumed the one-submit authority AT RESERVATION
(store semantics) with the release boundary never reached — deterministic
zero-effect knowledge (no PROMPT_VERIFIED/CLICK_ARMED/request facts;
browser never opened). Custody: `dead_reservation.json` per slot + ledger
`dead_reservations` + result `SLOT_DEAD_RESERVATION_REPAIR_REQUIRED`.
Both jobs may_submit=false forever. Full job ids in
`projects/flow_production_scale_007/generate_ledger.json` and per-slot
`frozen_intent.json`.

## 4. Mutation accounting

| Budget | Used | Cap | OK |
| :-- | --: | --: | :-- |
| Primary releases | 10 | 12 | ✓ (unused authority NOT used as retry) |
| Repair releases | 2 | 3 | ✓ |
| Continuity uploads | 2 | 2 | ✓ |
| Dead reservations | 2 | — | recorded |
| **Generates authorized** (releases + dead) | **14** | **15** | ✓ |

Zero blind retries; zero re-releases; zero same-job retries; zero
provider/account/project switching; zero direct MZZa6b; zero Gemini calls.

## 5. Continuity ledger

| Upload | Source | Frame SHA (prefix) | Provider media | Resolution |
| :-- | :-- | :-- | :-- | :-- |
| F2←F1 | SEQ7_F1 asset → last frame | `f4…` (ledger) | `8f2f5277-aae8-44b5-a5b7-c197d1d7c115` | armed → `reconcile_only` (2 stable probes + exact readback) → attested → adopted |
| G2←G1 | SEQ7_G1 asset → last frame | (ledger) | `75dbd0bc-8416-40a0-9c2a-19700fdcf665` | same read-only path |

Both uploads hit the armed-but-unresolved window (transient response
unresolved after ONE maseQ POST); the Scene-003 C4 sanctioned recovery
(read-only bounded reconciliation, never a re-upload) resolved both. The
F2 ledger contains one exact-duplicate binding line from a reconcile
re-run whose first pass had completed the binding but crashed on its own
final report print; the duplicate was removed in place with a durable
`dedupe_note` (reporting-bug repair, media identity identical).
LAST_FRAME continuity is thereby proven at 30-slot scale (2/2).

## 6. Canonical 30-slot production lineage → MASTER_SCALE_V1

Slot order (frozen): SEQ4_A1…A5, B1…B4, B5R (adopted) → SEQ5_C1…C4, D1…D4
(adopted) → SEQ7_E1…E4, F1…F4, G1…G4 (live; slot E2 ← E2R take, slot G3 ←
G3B take). 18 historical slots reuse their persisted immutable takes and
keep full-clip ranges (no qualified trim); 12 live slots carry
PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE ranges cut against frozen targets.

- EditManifest: `edit_b599e0c436c467e62756c234785dbdc106b5f64fb418139946e6a7fcf19f80b4`
- AutoEdit producer package: `editpkg_4da4146c21b9688c3e66cf29b9d9e26519881c030738a862a6c952cbec3b0a87`
- Render receipt: `rough_0ecba7d0ee51806ac7c2d99b69d3abbfbeb07305bd6c18768c5e8cae6d4bde56`
- Output: `master_package_007/master_scale_v1.mp4`,
  SHA-256 `51b929371d4f2612d0565e389f3f5cb9dbfbc6d048c0322be3c5013676899509`,
  duration 194.541667 s (timeline 194.4 s; Δ0.14 s = frame rounding,
  tolerance 1.05 s), 24 fps, h264/aac, full-decode EOF ✓, trim-aware
  (`trim=start/end` per clip; NOT whole-file concatenation).

Scene/sequence durations (selected): SEQ004 = 80 s (10×8), SEQ005 = 64 s
(8×8), SEQ007 = 50.4 s (12 trimmed). Pacing anomalies: none.
Conformance audit (independent): lineage+ranges all 30 PASS; repair takes
canonical (E2→E2R, G3→G3B) PASS; no stale primary takes PASS; B5R
canonical / B5 absent PASS; duration PASS; full decode PASS; boundary
frame sampling 29/29 PASS (single contiguous transitions; drift ≤ 0.2 s
from 24 fps segment quantization). **CONFORMANT.**
V1 review: master-level blackdetect/freezedetect clean; no repeated
action, no missing shot, no range/transition/boundary error.
Semantic/creative dimensions: OWNER_REVIEW_RECOMMENDED (no qualified VLM).
**MASTER_SCALE_V1_FINAL_CANDIDATE.**

## 7. Production telemetry (telemetry_007.json)

Generated provider seconds: 96 (12 releases × 8 s). Selected final
seconds: 194.4 timeline. Trim ratio (new slots): 0.525. Average selected
shot: 6.48 s. Provider media bytes (new releases): ≈ 47.5 MB. Reconcile
polls: mean < 2 (60 s interval). Master minutes / active hour ≈ 12.7
(wall-span basis — see note in file). Monetary cost:
**COST_UNKNOWN_TRUSTED_DATA_UNAVAILABLE**. Releases/canonical shot: 0.4;
repair rate 2/12 = 0.167; discarded-media rate 0.

## 8. Scale measurements (L16 — measured, no blind optimization)

runtime.sqlite: 2.14 MB, 48 jobs / 48 attempts / 45 assets / 38 takes /
6 manifests / 6 renders — journal growth linear and small at this scale.
Per-slot state dirs isolate cleanly (no collision; validation-refused).
Test suite: 675 tests ≈ 3.6 min. Dominant live cost: per-shot browser
session setup/teardown (inherent to the native-UI custody design; session
reuse would need a contract-preserving proof pass — recommended for a
future package, NOT changed here).

## 9. Adversarial review (findings → outcomes)

1. Attempt-1 prompt-limit refusals pre-mutation → v2 creative reduction,
   documented; no threshold weakened.
2. `evidence_dir` wrong for attestation verification → fixed (`75924ac`).
3. Lazy continuity-upload missing (tool bug) → fixed; F2/G2 fail-closed
   first (proves the gate), then succeeded (`6be0271`).
4. Loud re-entry machinery formalized (archive + notes + scale-layer
   sanctioned-archived state) → `1a94eeb` + tests.
5. Baseline race (provider catalog mutates between freeze and UI prep)
   burned 2 reservations post-reserve → structural: the store consumes
   authority at reservation. Custody recorded; successors via repair
   decisions; NOT silently retried. **Structural finding for Owner** (§11).
6. Stale v1 frozen job (fixture drift) → RESTART_PATH_DIFFERS refused
   correctly; successor G3B with fresh baseline; v1 job never released.
7. Reconcile double-append duplicate → deduped in place with durable note
   + idempotence guard (`e7349ed`).
8. Mutation-accounting semantics (dead reservations count toward the
   generate ceiling; uploads separate) → corrected + tested (`389a8be`).
9. Verified: master SHA recompute ✓; 12 live scale bindings unique ✓;
   secret scan clean (api_keys/ gitignored); no Gemini calls; editorial
   layer provider-free; SoT manifest 30/30; `git diff --check` clean;
   compile clean.

## 10. Final battery

- **675 passed, 0 failed** (baseline 632 + 43 new: scale 24, editorial
  range 15, recovery-matrix gaps 4) — full network-free regression incl.
  Slice-0011, Scene-003/R1, Package-004/005/006 regressions.
- Recovery matrix: 58/58 scenarios PASS (`recovery_matrix.json`).
- SoT manifest 30/30 verified; `git diff --check` clean; compileall clean;
  secret/PII/API-key scan clean.

## 11. Unresolved unknowns

1. Root cause of the baseline race (provider-side catalog row mutation
   within the freeze→UI window) is environmental and unproven; the gate
   behaved fail-closed. Structural consequence: a post-reserve refusal
   burns the one-submit authority — the runtime may warrant a
   pre-reserve baseline re-check (contract-preserving change; future
   package, requires Owner approval because it touches the mutation path).
2. Semantic QC remains UNQUALIFIED (external gate unchanged; no calls
   made).
3. Exact provider billing data absent → cost unknown.

## 12. Production-readiness impact

The system now runs N-sequence production at 30 slots: adopted historical
lineage enters read-only; fresh sequences execute under frozen budgets
with at-most-once custody visible at scale; dead reservations have a
durable custody + bounded-repair path; editorial truth is a deterministic
source-range model binding take/asset/shot/probe; AutoEdit renders
trim-aware masters verified by independent frame-level conformance.
Recommended next package: **FLOW-EDITORIAL-SCALE-008** — Owner take
review + semantic QC rerun (when the API gate clears) + audio path
qualification + per-shot session-reuse hardening.
