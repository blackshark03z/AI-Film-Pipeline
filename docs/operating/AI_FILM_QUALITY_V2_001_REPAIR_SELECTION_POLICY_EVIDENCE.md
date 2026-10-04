# AI-FILM-QUALITY-V2-001 — Repair-Selection Policy Freeze — Evidence Record

**Status:** COMPLETED_CANDIDATE · **QUALITY_V2_GOVERNANCE = PROVEN_CANDIDATE**
**Mission:** SHAPE → BOUND → SLICE → PROVE — freeze the quality-repair
governance required before any Quality Hardening experiment is allowed to
mutate canonical film state. No generation, no promotion, no V1 rewrite.

## 1. Custody chain (branch authority)

| Item | Value |
| --- | --- |
| Exact baseline (remote revision) | `14ba281d12c15a5678a3fe1b3f0242f577512e5f` |
| Ancestry check | `git merge-base --is-ancestor 14ba281… HEAD` → verified; baseline IS ancestor of the working branch and of the pre-work HEAD (they were identical) |
| New branch | `quality-v2/001-repair-selection-policy` created from the exact baseline SHA |
| PACKAGE_019 binding | `AI_FILM_PIPELINE_V1_COMPLETION_019`; debt registry `quality_debt_registry_019.json` (QD-001..005); Owner decision `owner_quality_decision_019.json` (ACCEPT_KNOWN_QUALITY_DEBT, FURTHER_V1_VIDEO_REGENERATION = DISALLOWED, CANDIDATE_PROMOTION = NONE); canonical master `976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595` (`canonical_no_change_019.json`, result UNCHANGED) |
| Roadmap binding | `docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md` (QH-1..QH-8) |
| PACKAGE_019_FINAL_HEAD_SHA | returned in the final worker report (`git rev-parse HEAD` after the last evidence commit) — no self-referential SHA field is claimed |

## 2. Reuse analysis (searched before building)

Existing V1 models found and REUSED unchanged (zero modification):

- `SelectedTake` (`src/film_pipeline/qc.py:140`) — the canonical
  selection authority every candidate binds against.
- `RepairDecision` (dict + `schemas/repair_decision.schema.json`,
  `src/film_pipeline/qc.py:239-271`) — technical repair disposition;
  the V2 candidate model complements it for QUALITY repair.
- `OwnerReviewDecision` / `OwnerDecisionLedger` / `SupersessionRecord`
  (`src/film_pipeline/owner_review.py`) — immutable Owner boundary,
  `decision_source` schema-locked to OWNER, `refuse_worker_origin`
  markers. Reused verbatim; the V2 candidate selection REQUIRES one.
- `EditManifest` / `EditClip` (`src/film_pipeline/editorial.py`) —
  canonical editorial intent; the successor manifest is derived from
  it deterministically.
- `QualityDebtItem` + registry rule (`src/film_pipeline/quality_debt.py`)
  — reused read-only; debt closure lives in a separate V2 ledger.

Missing delta built new: `src/film_pipeline/quality_repair_v2.py`
(governance module) + 4 schemas + evidence tools. Nothing in V1 was
rewritten (git proof in section 12).

## 3. Quality decision model (sections 2, 4 of the package)

`QualityRepairCandidate` (`schemas/quality_repair_candidate.schema.json`):
`candidate_id` (derived `QRC-<sha16>` from the exact identity basis:
source_canonical_take + affected_shot + asset_sha256 +
generation_semantic_identity — state transitions never change identity),
`source_canonical_take`, `affected_shot`, `repair_reason`,
`quality_debt_ids`, `generation_semantic_identity`, `asset_sha256`,
`technical_qc_receipt`, `identity_receipt`, `quality_review_receipt`,
`editorial_compatibility_receipt`, `owner_decision_state`.

States (exactly the seven frozen): `PROPOSED → TECHNICALLY_VALID →
QUALITY_REVIEW_READY → OWNER_SELECTED | OWNER_REJECTED | DEFERRED`;
`OWNER_SELECTED → SUPERSEDED`. Skip transitions are refused; terminal
states are terminal; `OWNER_SELECTED/REJECTED/DEFERRED` structurally
require a recorded immutable Owner decision id; **no candidate becomes
canonical automatically**.

`QualityReviewReceipt` (`schemas/quality_review_receipt.schema.json`):
exactly one finding per each of the TEN dimensions
(NARRATIVE_LOGIC, ACTION_CAUSALITY, SHOT_DESIGN, IDENTITY,
BODY_PROPORTION, PERFORMANCE, BLOCKING, CAMERA, TEMPORAL_MOTION,
EDITORIAL_FIT); verdict ∈ {IMPROVED, UNCHANGED, REGRESSED, INCONCLUSIVE,
NOT_APPLICABLE}; per finding: severity, evidence, affected time range;
per receipt: review source, limitations; `no_aggregate_score` is
structurally `const true`. **One improvement can never silently
compensate another regression** — there is no aggregate anywhere; the
Owner sees `tradeoff_summary()` explicitly. Identity regression is an
unconditional hard block ("identity never regresses for meaning");
HIGH/CRITICAL regressions hard-block; LOW/MEDIUM regressions block
unless the Owner's decision note carries
`TRADEOFF_ACCEPTED=<dimensions>`.

## 4. Acceptance policy (section 3)

Ten frozen conditions (all ten required; no weighting; no "best score
wins"), enforced by `evaluate_acceptance` and re-checked inside the
transaction: C1 exact candidate identity proven · C2 technical QC
passes · C3 identity/world does not materially regress (INCONCLUSIVE =
unproven = refused) · C4 target defect shows evidence-supported
improvement · C5 no higher-severity new defect (unacknowledged
regressions block) · C6 editorial fit proven (receipt must bind the
canonical predecessor manifest) · C7 Owner explicitly SELECTS the exact
asset SHA · C8 replacement recorded append-only · C9 rebuilt edit/master
passes deterministic verification (rebuild preview must be
deterministic) · C10 rollback target retained (predecessor bindings +
bytes). No worker/model may mint OWNER_SELECTED (schema + `refuse_worker_origin` + Owner-identity guard).

## 5. Decision rights (section 5)

`ROLE_PERMISSIONS` frozen in code: Tech Lead {DEFINE_EXPERIMENT,
FREEZE_ACCEPTANCE, VALIDATE_PROOF}; Worker {EXECUTE_EXPERIMENT,
PRODUCE_EVIDENCE, PROPOSE_CANDIDATE}; Automated QC
{VALIDATE_TECHNICAL_CONFORMANCE, REJECT_TECHNICAL_INVALIDITY}; Owner
{SELECT_CANDIDATE, REJECT_CANDIDATE, DEFER_CANDIDATE,
ACCEPT_KNOWN_QUALITY_DEBT}; Provider {} (never authority).
`PROMOTE_CANDIDATE` is non-grantable to every role — canonical
promotion is a procedure, not a permission. Tech Lead cannot
impersonate Owner preference (`owner_identity` must be exactly OWNER).

## 6. Canonical promotion transaction (section 6)

`quality_promotion_transaction_v1`
(`schemas/quality_promotion_transaction.schema.json`):
`QPT-<sha16>` transaction id derived from candidate + predecessor
binding + clip order; `PredecessorBinding` (selected_take_id, shot_id,
asset_sha256, edit_manifest_id, master_sha256); successor manifest is
built deterministically changing ONLY the affected clip
(`build_successor_manifest`); promotion_scope = AFFECTED_CLIP_ONLY.

`execute_promotion` is atomic at authority level: refuses non-PROPOSED
state, ledger-detects double commit AND failed-transaction blind retry,
refuses wrong canonical predecessor / stale EditManifest / tampered
successor id / non-deterministic rebuild / unretained candidate bytes,
re-evaluates all ten conditions, then commits as ONE step and emits a
promotion receipt binding before/after master shas + the full rollback
target. If the rebuild fails: transaction recorded PROMOTION_FAILED,
**canonical authority remains the old take**, and a full
canonical-state-digest check proves no mixed state (torn-write fault
injection included). Environments implement the `PromotionEnvironment`
surface; the synthetic reference implementation is in-module, a real
QCStore/EditorialStore adapter is deferred to a later package (zero
live canonical mutation in this package).

## 7. Rollback contract (section 7) — proven on the synthetic fixture

Every promotion receipt preserves: previous SelectedTake id, previous
EditManifest id/hash, previous master sha, the promotion receipt
itself, and the replacement asset sha. `rollback_promotion` restores
the EXACT predecessor deterministically (verified: restored master ==
recorded predecessor master; restored manifest id; refusal on any
mismatch — surfaced, never absorbed), requires the COMMITTED state with
its receipt, refuses double rollback (ledger), and requires **no
regeneration** — predecessor bytes are retained by contract
(`C10`) and the environment exposes no generation capability.
Proofs: `tests/test_quality_v2_promotion_rollback_001.py`
(20 tests) on `SyntheticFilmEnvironment` +
`FaultInjectionEnvironment`.

## 8. Quality-debt closure (section 8)

`DebtClosureLedger` (append-only, hash-chained, tamper-checking; never
rewrites the frozen registry file): `ACTIVE → IMPROVEMENT_CANDIDATE`
(only a candidate targeting that debt at QUALITY_REVIEW_READY or
better) `→ OWNER_ACCEPTED_RESOLUTION` (requires OWNER_SELECTED
candidate + a promotion receipt binding it — a candidate alone does
NOT close debt) `→ CLOSED` (requires deterministic verification
receipt); plus `ACTIVE ↔ DEFERRED` and `ACTIVE → ACCEPTED_DEBT`. All
other transitions refused.

## 9. Experiment admission gate (section 9)

`ExperimentAdmissionReceipt` (`schemas/experiment_admission_receipt.schema.json`)
+ `admission_gate`: target quality debt (must exist in the frozen
registry), canonical baseline (must equal
`14ba281d12c15a5678a3fe1b3f0242f577512e5f`), hypothesis, variables
changed, variables held constant, max Generate budget (finite, ≤50,
unbounded refused), provider route, acceptance criteria, owner-review
surface, rollback plan. Missing/invalid ⇒ **BLOCKED_INVARIANT**.
`ADMISSION_REQUIRED_FROM = "V2-002"` — mandatory for V2-002 onward.

## 10. First experiment selection (section 10) — NO generation, NOT authorized

`tools/build_quality_v2_experiment_priority_001.py` →
`projects/quality_v2_repair_selection_policy_001/quality_v2_experiment_priority_001.json`.
Ranking computed at runtime from frozen weights (leverage 0.30,
information gain 0.20, generation cost 0.15⁻¹, identity risk 0.15⁻¹,
editorial impact 0.10⁻¹, reversibility 0.10); every score cites frozen
evidence artifacts whose existence is verified before write; byte-identical
re-generation re-proven. Result:

| Rank | Candidate | Weighted total |
| --- | --- | --- |
| 1 | QH-1 action causality redesign (QD-001, QD-002) | 4.45 |
| 2 | QH-4 choreography intensity ladder (QD-004) | 3.80 |
| 3 | QH-3 full-body proportion (QD-003) | 3.75 |
| 4 | QH-5 camera/blocking staging control | 3.10 |
| 5 | QH-2 shot decomposition split beat | 2.65 |

Recommendation: QH-1, `authorization_state: NOT_AUTHORIZED`. Nothing
was generated; no candidate was promoted; no provider was contacted.

## 11. V2-002 handoff (section 11)

`docs/quality-v2/V2_002_EXPERIMENT_HANDOFF.md` — defines ONLY:
recommended first target (QH-1), why first, exact hypothesis, required
inputs (incl. Owner-approved redesigned intent), max mutation budget
(≤2 generates, ≤1 promotion transaction of one clip), acceptance
dimensions, Owner decision surface (blind packet + compare reel +
trade-off note), and five stop conditions. No generation, no hidden
provider change.

## 12. V1 no-change proof

- `git status --porcelain` (tracked): **0 modified / 0 deleted** — all
  delivery files are NEW paths (`schemas/quality_*`,
  `schemas/experiment_*`, `src/film_pipeline/quality_repair_v2.py`,
  `tools/build_quality_v2_*`, `tests/test_quality_v2_*`,
  `docs/quality-v2/*`, `projects/quality_v2_repair_selection_policy_001/*`,
  this evidence record). V1 sources
  (`core.py, qc.py, owner_review.py, quality_debt.py, editorial.py`, …)
  byte-unchanged.
- Frozen 019 artifact bytes re-verified unchanged after full governance
  exercise (RC-082/RC-083).
- Zero external calls, zero video generation, zero provider mutation,
  zero canonical promotion — structural (module surface scan RC-084) +
  behavioral (fresh ledger stays empty through the full selection flow,
  RC-085).

## 13. Test / recovery / verification counts

- Full suite: **1058 passed** (918 V1 predecessor tests unchanged +
  **140 new**: 30 policy, 20 promotion/rollback, 89 recovery-matrix
  parametrized + 1 matrix-integrity), 0 failed, ~3m45s, network-free.
- Adversarial/recovery matrix: **89 cases** across 10 categories
  (ACCEPTANCE_POLICY 12, REVIEW_CONTRACT 11, DECISION_RIGHTS 12,
  CANDIDATE_STATE_MACHINE 10, PROMOTION_TRANSACTION 12, ROLLBACK 8,
  DEBT_LIFECYCLE 8, EXPERIMENT_ADMISSION 8, V1_BASELINE_IMMUTABILITY 6,
  CUSTODY 2) — every case executed against its live
  guard (`tests/test_quality_v2_recovery_matrix_001.py`); required
  topics covered incl. identity-regression, aggregate-hides-regression,
  selected-without-Owner, wrong asset SHA, wrong predecessor, stale
  manifest, rebuild failure, partial promotion, rollback mismatch,
  debt closed too early, worker auto-promotion, ambiguous provider
  output, blind retry, wrong experiment baseline, unbounded budget,
  V1 baseline mutation. Any future external-effect ambiguity remains
  **OWNER_AMBIGUITY_GATE**.
- `compileall` clean · `git diff --check` clean · secret scan clean ·
  SoT manifest 30/30 verified (docs/sot/film untouched) · generated
  JSONs byte-identical on re-run.

## 14. Final status

**COMPLETED_CANDIDATE** — QUALITY_V2_GOVERNANCE = **PROVEN_CANDIDATE** ·
V1_BASELINE = **UNCHANGED** · LIVE_GENERATION = **0** ·
CANONICAL_PROMOTION = **0** · NEXT =
**V2_002_EXPERIMENT_HANDOFF** (Owner decides whether V2-002 runs; an
admission receipt is mandatory before any live step).
PACKAGE_001_FINAL_HEAD_SHA is returned in the final worker report.
