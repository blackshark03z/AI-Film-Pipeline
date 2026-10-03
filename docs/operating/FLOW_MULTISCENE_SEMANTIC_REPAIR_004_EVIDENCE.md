# FLOW-MULTISCENE-SEMANTIC-REPAIR-004 — Final Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-multiscene-semantic-repair-004`
**Original starting SHA:** `a9d3599903ef1cc25fbb320b552b78286a863791` (R1 delivery tip, verified with ancestry from `919d4df…`)
**Proof-custody correction SHA:** `266dec6967b1b4785d48a05b5b84e55164bce0db` (`docs: correct Scene-003 R1 dead-reservation accounting`)
**Package base SHA:** `266dec6` (new branch created from the correction commit)
**Delivery:** the branch tip carrying this record.

## 1. Active wall time

2026-10-03T00:41Z → ~04:10Z (~3h30m active of the 8h ceiling; all phases P0–P13 complete).

## 2. Checkpoint timeline

| Checkpoint | Commit | Result |
| :-- | :-- | :-- |
| P0_PROOF_CUSTODY_CORRECTED | 266dec6 | R1 accounting corrected: dead reservations = **3 (3R, 3S, 3T)**, releases from them = 0 (journal-verified per job); branch created from the correction |
| P1_MULTISCENE_ORCHESTRATOR_READY | 90c4ac2 | sequence layer (N scenes × M shots, plan pinned, restart-safe) + 13 offline tests |
| P3 interface (early) | 90c4ac2 | semantic_qc.py + 7 contract tests; live status honestly `SEMANTIC_QC_UNQUALIFIED` |
| P2_SEQUENCE_PLAN_FROZEN | 83b90a4 | two-scene/10-shot SequencePlan frozen before first mutation |
| P4_PRIMARY_SEQUENCE_EXECUTED | (this delivery) | 10/10 shots PROVEN live, first-poll attribution each |
| P5_CONTINUITY_COMPLETE | (this delivery) | 9 cut packets (8 intra-scene + 1 scene boundary), hash-pinned frames |
| P6/P7_REPAIR_LOOP_CLOSED | c777641 | 1 evidence-backed repair executed (budget 1/3) |
| P7_SEQUENCE_TAKES_SELECTED | (this delivery) | 10 provisional takes, repaired B5R in canonical slot |
| P8_ROUGH_CUT_V1_PROVEN | (this delivery) | V1: 80 s, sha `8378651e…` (contains the B5 artifact — superseded) |
| P9_ROUGH_CUT_ITERATION_CLOSED | (this delivery) | RoughCutReview found WORLD_MISMATCH on B5 → repaired → **ROUGH_CUT_V2** sha `c8b02d16…` = ROUGH_CUT_FINAL_CANDIDATE |
| P10_MULTISCENE_RECOVERY_PROVEN | (this delivery) | matrix mapped to suites (§7) |
| P11_PRODUCTION_METRICS_COMPLETE | (this record) | §6 |
| P12_ADVERSARIAL_REVIEW_COMPLETE | (this record) | §8 |

## 3. Proof-custody correction (exact)

R1's §11 accounting said "Dead reservations during this package: 2 (3R, 3S)" but the §6 ledger listed three (3R, 3S, 3T). Journal-verified each: all have `RESERVED + MUTATION_INTENT_BOUND` only, guard requests 0, never released. Corrected statement (append-labeled, no history rewritten): **Dead reservations during R1: 3 (3R, 3S, 3T); provider releases from those reservations: 0.**

## 4. Frozen sequence + execution ledger

**SEQ004_SWORDSMAN_DESCENT** (frozen before first mutation): Scene A `SCENE_A_DAWN_STANCE` (dawn decision, 5 shots: establishing / action / action / performance / button) → Scene B `SCENE_B_VALLEY_PASS` (morning passage, 5 shots: new-space establishing / re-entry / escalation / insert / hero resolution). Same-reference continuity throughout; last-frame mechanism NOT re-used (PROVEN in Scene-003; no upload needed → uploads 0/2).

| Slot | Shot | ProviderJob | Provider media | Asset sha256 | Bytes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| A1 | SEQ4_A1 | `job_97272537…` | `3376379c-7c08-…` | `0a3f420e20bae7…` | 2,038,113 |
| A2 | SEQ4_A2 | `job_1df3f003…` | `fc460eb9-4d2b-…` | `86f5e489f03786…` | 2,754,284 |
| A3 | SEQ4_A3 | `job_5d797fb8…` | `d76599d9-54b1-…` | `f17946ff797b9b…` | 2,051,430 |
| A4 | SEQ4_A4 | `job_a4472c82…` | `40c7fdf8-0431-…` | `09c65208bc6003…` | 1,685,877 |
| A5 | SEQ4_A5 | `job_b97e5f4c…` | `2bdbcf59-1f6a-…` | `8b6d261ea6f62f…` | 1,898,799 |
| B1 | SEQ4_B1 | `job_595d221f…` | `f2efa3cf-929d-…` | `f4590e53d540a1…` | 4,658,535 |
| B2 | SEQ4_B2 | `job_e0d13695…` | `03e38ab0-3419-…` | `241018baa367f6…` | 1,734,985 |
| B3 | SEQ4_B3 | `job_05dffe9e…` | `efed3963-7fe1-…` | `9bce58275baf22…` | 2,886,311 |
| B4 | SEQ4_B4 | `job_baf0b209…` | `44ef43c8-9e65-…` | `6abb4010290ec2…` | 1,705,789 |
| B5 | SEQ4_B5 (superseded) | `job_6912b4b3…` | `80636c30-2930-…` | `c48c90e00614e7…` | 2,543,364 |
| B5R (repair) | SEQ4_B5R | `job_7a53ae93…` | `fadab4e2-9a32-…` | `d79e00a104e4e1…` | 5,122,718 |

All 10 primaries: attribution on the FIRST reconciliation poll, exact marker echo, full EOF decode, technical QC pass, `may_submit=false` after release. Zero dead reservations this package (every reservation either released or superseded with journal evidence; the two pre-B5R repair attempts failed BEFORE reservation on the budget-key bug — 0 clicks, archived `*.local_budget_bug.json`).

## 5. Semantic QC (P3) — SEMANTIC_QC_UNQUALIFIED (honest)

- No qualified VLM key exists in this environment (searched: repo `api_keys/`, sibling worktrees, env). The existing `gemini_advisory` adapter requires a key file that is absent.
- Built the smallest replaceable interface anyway (`src/film_pipeline/semantic_qc.py`): `SemanticQCRequest` (hash-pinned frames, frozen per-dimension requirements, provenance) → `SemanticQCObservation` (dimension ∈ 8 frozen dimensions, verdict ∈ PASS/FAIL/INCONCLUSIVE, confidence, observations, evidence refs, evaluator metadata, prompt fingerprint). `validate_semantic_batch` enforces cardinality/dimension/request-id lineage. Advisory-only by construction: the observation model carries NO authority fields (tested).
- `FrozenFixtureEvaluator` (deterministic) proves the contract is offline-testable: positive/negative/ambiguous controls, INCONCLUSIVE-capable, determinism. 7 tests.
- Live status: **SEMANTIC_QC_UNQUALIFIED** — semantic dimensions marked OWNER_REVIEW_RECOMMENDED in every cut packet and take; no verdict fabricated; technical QC and lineage untouched by semantics.

## 6. Production metrics

| Metric | Value |
| :-- | :-- |
| Primary Generate releases | 10/10 (budget exhausted exactly) |
| Repair releases | 1/3 (evidence-backed WORLD_MISMATCH on B5) |
| Continuity uploads | 0/2 (same-reference mechanism sufficed) |
| Dead reservations | 0 released-from-dead; 2 pre-reserve failures (0 clicks, archived) |
| Selected shots | 10 (9 primary + 1 repair) |
| Discarded outputs | 1 (B5 primary — historical evidence retained) |
| Generated seconds | 88 s (11 generates × 8 s) |
| Selected usable seconds | 80 s (rough cut V2) |
| Provider media bytes | ~25.9 MB acquired across 11 assets |
| Attribution latency | first reconciliation poll for ALL 11 shots |
| Repair rate | 1 repair / 10 primary shots = 10% |
| Generates per selected shot | 11 releases / 10 selected = 1.1 |
| Total package active time | ~3h30m |
| Finished sequence minutes | 1.33 min (80 s) |

## 7. Recovery matrix coverage

Sequence-level restart windows (before/mid/between scenes, plan pin, order swap, terminal-no-rerun, completion gating) — `tests/test_sequence_orchestrator.py` (13). Per-shot lifecycle + render-drop temporal policy + latch — `test_flow_render_lifecycle.py` (33), `test_mutation_authority_latch.py` (12), `test_recovery_matrix_002.py` (5), `test_dispatch_recovery.py`. Semantic QC malformed/unavailable/source-mismatch/prose-not-truth — `test_semantic_qc.py` (7) + SEMANTIC_QC_UNQUALIFIED freeze. Stale take/manifest exclusion — stale-B5 scan (this package) replicating the stale-3C pattern. Rough-cut receipt/bytes — real_rough_cut fresh-readback lineage checks + hash re-verification. Consumed jobs never regain submit authority — asserted across all suites.

## 8. Adversarial review findings (fixed in-package)

1. `argparse` import missing in the sequence runner (crashed before any mutation) — fixed.
2. Repair path initially hardcoded the primary budget key (`PRIMARY_BUDGET_EXHAUSTED` before reserve, 0 clicks) — budget kind now derives from the shot's repair flag; repair ledger separated.
3. Cached per-shot result file replayed the pre-fix failure — result paths now per-shot and stale attempts archived (`*.local_*.json`).
4. B5R locator/roots initially pointed at the wrong media root in the AutoEdit package (`referenced media missing`) — fixed to `repair_scope` root; package verifies media by hash at write.
5. `git add -A` again staged unrelated untracked historical tools — unstaged pre-commit.
Reviewed clean: no VLM-prose-as-truth path, no semantic-to-authority leakage, no repair-as-retry, no stale B5 in V2 package, no scene/state bleed, no latch bypass.

## 9. RoughCutReview (P10)

- V1 (sha `8378651e…`): ordering/timing/completeness correct; cut09 packet exposed B5's opening artifact (literal funnel/basin object) — classified WORLD_MISMATCH → SHOT_REPAIR_REQUIRED.
- Repair executed (§5 slot B5R), V2 rebuilt (sha `c8b02d16…`): artifact absent, cut09 B4→B5R continuous, all other cuts unchanged.
- **RoughCutReview verdict: ROUGH_CUT_V2_FINAL_CANDIDATE** (technical integrity + deterministic continuity evidence; semantic/aesthetic dimensions OWNER_REVIEW_RECOMMENDED).

## 10. Unresolved unknowns

1. Semantic QC remains unqualified until a VLM key is provisioned; the interface and qualification procedure are ready and tested offline.
2. The literal-interpretation failure mode ("funnel" → object) suggests prompt-side screening for concrete-noun metaphors in future ShotSpecs (process improvement, not architecture).
3. as29s non-null pending payload shape still uncaptured (SoT A7, unchanged).

## 11. Production-readiness delta & next package

The pipeline now executes REAL multi-scene sequences (2 scenes / 10 shots / 80 s) with evidence-driven bounded repair and rough-cut iteration — the full loop from frozen plan to reviewed final cut with zero blind retries and zero unresolved ambiguity. Recommended next: **FLOW-SEQUENCE-SCALE-005** — provision a VLM key (Owner) → qualify semantic QC per SoT A-procedure → multi-scene sequences with dialogue/audio dimensions and Owner-in-the-loop take approval.
