# QUALITY_V2_SOT — Frozen Quality-Track V2 Source of Truth

**Package:** AI-FILM-QUALITY-V2-001 (QUALITY-REPAIR-SELECTION-POLICY-FREEZE)
**Status:** FROZEN governance. This document is small, durable, and
binding for every future V2 quality-hardening package.
**Branch of record:** `quality-v2/001-repair-selection-policy`

---

## 1. Frozen objective and baseline

```
QUALITY_V2_GOAL = improve film creative quality without weakening V1 technical/provenance guarantees

QUALITY_V2_CANONICAL_BASELINE =
  V1 remote revision 14ba281d12c15a5678a3fe1b3f0242f577512e5f
```

V1 technical truth is CLOSED and IMMUTABLE:

- V1 completion receipt: `AI_FILM_PIPELINE_V1_COMPLETION_019`
  (`docs/operating/AI_FILM_PIPELINE_V1_COMPLETION_019.md`)
- Debt registry: `projects/flow_v1_completion_quality_debt_freeze_019/quality_debt_registry_019.json` (QD-001..005)
- Owner decision: `projects/flow_v1_completion_quality_debt_freeze_019/owner_quality_decision_019.json`
  (creative NOT accepted; `FURTHER_V1_VIDEO_REGENERATION = DISALLOWED`;
  `CANDIDATE_PROMOTION = NONE`)
- Canonical master identity at the V1 close:
  `976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595`
  (`canonical_no_change_019.json`, result `UNCHANGED`)

Package-017/018 experimental candidates remain EVIDENCE ONLY. Nothing in
V2 promotes them implicitly; any promotion runs through the frozen
transaction below, from this baseline.

## 2. The ten independent quality dimensions

Quality improvement is measured independently across:

`NARRATIVE_LOGIC`, `ACTION_CAUSALITY`, `SHOT_DESIGN`, `IDENTITY`,
`BODY_PROPORTION`, `PERFORMANCE`, `BLOCKING`, `CAMERA`,
`TEMPORAL_MOTION`, `EDITORIAL_FIT`

**No collapse rule:** these dimensions are never combined into a single quality score. One improvement can never silently compensate another regression. Trade-offs must be shown to the Owner explicitly, per
dimension, with severity and evidence
(`film_pipeline.quality_repair_v2.QualityReviewReceipt.tradeoff_summary`).

## 3. Governance modules (frozen implementation)

| Contract | Implementation | Schema |
| --- | --- | --- |
| Quality repair candidate + state machine | `src/film_pipeline/quality_repair_v2.py` | `schemas/quality_repair_candidate.schema.json` |
| Per-dimension quality review receipt | `src/film_pipeline/quality_repair_v2.py` | `schemas/quality_review_receipt.schema.json` |
| Promotion transaction + rollback | `src/film_pipeline/quality_repair_v2.py` | `schemas/quality_promotion_transaction.schema.json` |
| Experiment admission gate | `src/film_pipeline/quality_repair_v2.py` | `schemas/experiment_admission_receipt.schema.json` |

Reused V1 mechanisms unchanged: `SelectedTake` (selection authority),
`RepairDecision` (technical repair disposition), `OwnerReviewDecision`
+ `OwnerDecisionLedger` (immutable Owner boundary, supersession),
`EditManifest` (editorial intent identity), `QualityDebtItem` (debt
records). The V2 module extends; it does not rewrite any of them.

## 4. Candidate lifecycle (no auto-promotion)

```
PROPOSED -> TECHNICALLY_VALID -> QUALITY_REVIEW_READY
         -> OWNER_SELECTED | OWNER_REJECTED | DEFERRED
OWNER_SELECTED -> SUPERSEDED (only by a later promoted candidate)
```

Every transition is explicit; terminal states are terminal. **No
candidate becomes canonical automatically.** Canonicality changes only
through an executed promotion transaction
(`execute_promotion`), which requires all ten acceptance conditions.

## 5. Acceptance policy (all ten, no weighting)

A candidate may replace a canonical SelectedTake only if:

1. **C1** exact candidate identity is proven
2. **C2** technical QC passes
3. **C3** identity/world continuity does not materially regress
   (REGRESSED is unconditionally blocking; INCONCLUSIVE is unproven)
4. **C4** the target quality defect shows evidence-supported improvement
5. **C5** no higher-severity new defect is introduced (any regression
   must be explicitly Owner-acknowledged; identity regression can never
   be accepted)
6. **C6** editorial fit is proven
7. **C7** Owner explicitly SELECTS the exact asset SHA
8. **C8** the replacement is recorded append-only
9. **C9** the rebuilt affected edit/master passes deterministic
   verification
10. **C10** the rollback target is retained

No worker/model may mint `OWNER_SELECTED`. There is no "best score
wins": the checklist is pass/fail per condition.

## 6. Ranking criteria for experiments

First-experiment candidates are ranked on six criteria — expected
quality leverage (0.30), information gain (0.20), generation cost
(0.15, inverted), identity risk (0.15, inverted), editorial impact
(0.10, inverted), reversibility (0.10) — with every score citing
frozen evidence artifacts. Current output:
`projects/quality_v2_repair_selection_policy_001/quality_v2_experiment_priority_001.json`.

## 7. Decision rights (frozen)

| Role | May | May never |
| --- | --- | --- |
| Tech Lead | define experiments, freeze acceptance, validate proof | impersonate Owner preference |
| Worker | execute experiments, produce evidence, propose candidates | promote, select, define acceptance |
| Automated QC | validate technical conformance, reject technical invalidity | select a creative winner |
| Owner | select/reject/defer an exact candidate; accept known debt explicitly | be simulated by any machine output |
| Provider/model | nothing | be authority in any form |

Canonical promotion is a procedure, not a role grant:
`PROMOTE_CANDIDATE` is non-grantable to every role.

## 8. Promotion, rollback, and debt closure

- **Promotion** is atomic at authority level: OWNER_SELECTED candidate
  + ten passing conditions + verified deterministic rebuild, committed
  as one step with a promotion receipt. If the rebuild fails, canonical
  authority remains the old take; mixed canonical state is detected and
  fatal. Schema: `quality_promotion_transaction_v1`.
- **Rollback** restores the exact predecessor (SelectedTake,
  EditManifest id, master sha) deterministically, with no regeneration;
  predecessor bytes are retained by contract and verified.
- **Debt closure:** `ACTIVE -> IMPROVEMENT_CANDIDATE ->
  OWNER_ACCEPTED_RESOLUTION -> CLOSED`, or `ACTIVE / DEFERRED /
  ACCEPTED_DEBT`. A candidate alone never closes debt; only an
  Owner-selected, successfully promoted, deterministically verified
  result can. The frozen V1 registry file is never rewritten; closure
  lives in a separate append-only ledger.

## 9. Experiment admission gate

From **V2-002 onward**, any V2 live-generation package requires an
`ExperimentAdmissionReceipt` (target quality debt, canonical baseline,
hypothesis, variables changed / held constant, max Generate budget,
provider route, acceptance criteria, owner-review surface, rollback
plan). Missing or invalid => `BLOCKED_INVARIANT`. Wrong baseline,
unknown debt target, or unbounded budget => `BLOCKED_INVARIANT`.

## 10. Standing track rules (inherited from V1 custody)

- Frozen intent, one submit, no blind retry; ambiguity = `OWNER_AMBIGUITY_GATE`.
- Identity never regresses for meaning.
- The canonical master changes only through an explicit Owner selection
  bound to the exact asset SHA.
- Zero external calls / zero generation / zero canonical mutation by
  governance tooling itself.
