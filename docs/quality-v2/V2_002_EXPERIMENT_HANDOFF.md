# V2-002 EXPERIMENT HANDOFF — First Quality-Hardening Experiment

**From:** AI-FILM-QUALITY-V2-001 (repair-selection policy freeze)
**To:** V2-002 (first authorized experiment package, if the Owner wants one)
**Status:** HANDOFF ONLY. This document defines the boundary of the next
package. It authorizes NO generation and NO provider change.

---

## 1. Recommended first target

**QH-1 — Narrative / action causality redesign** (roadmap
`docs/roadmap/AI_FILM_QUALITY_HARDENING_V2.md` QH-1; debts QD-001,
QD-002).

Ranked first by the frozen evidence-based ranking
(`projects/quality_v2_repair_selection_policy_001/quality_v2_experiment_priority_001.json`,
weighted total 4.45 vs 3.80 for the runner-up QH-4 ladder).

## 2. Why it is first

- **Largest owner-visible defect:** both causal-logic debts carry the
  Owner assessment `NEEDS_REDESIGN`; the canonical F2/G3 shots do not
  communicate trigger/goal/outcome.
- **The mechanism is already proven:** Package-018 candidate A
  (`CAUSAL_CONTROL_EFFECT_OBSERVED`) rendered the causal chain visibly —
  "goal+outcome go from unreadable to readable" — under the same
  qualified route. What is untested is redesigned INTENT, not the
  compiler.
- **Cheapest information:** one shot, ≤2 generates, master slot
  preserved, fully reversible under the frozen promotion/rollback
  contract.

## 3. Exact hypothesis

> Rewriting ONE canonical shot's action logic from the narrative
> authority (new `dramatic_purpose` and beats, compiled through the
> existing `flow-r2v-causal-compact-v1` causal compiler) produces a
> render whose trigger/goal/outcome the Owner reads correctly in a
> blind review, without identity or editorial regression — i.e. a
> candidate that can pass the frozen ten-condition acceptance policy.

## 4. Required inputs

- Owner-approved redesigned intent for the chosen shot (content input;
  the V2 track may not invent narrative authority).
- The candidate must enter the governance machinery as a
  `QualityRepairCandidate` (PROPOSED) bound to the exact canonical
  `SelectedTake` it would replace, carrying `quality_debt_ids`
  [QD-001 or QD-002].
- Frozen baseline: `QUALITY_V2_CANONICAL_BASELINE`
  (`14ba281d12c15a5678a3fe1b3f0242f577512e5f`); canonical master
  `976876a1…6595` must be unchanged at experiment start.

## 5. Max mutation budget

- Generates: **≤ 2** for the one shot (admission field
  `max_generate_budget = 2`).
- Canonical mutation: **0** until a candidate reaches `OWNER_SELECTED`
  through the immutable Owner decision surface, then at most ONE
  promotion transaction affecting exactly one clip.
- Everything else (prompt/shot-spec redesign artifacts, review
  packets, receipts) is evidence, not mutation.

## 6. Acceptance dimensions

Quality review receipt per `QUALITY_V2_SOT.md` section 2, with:

- target dimensions: `ACTION_CAUSALITY` (and `NARRATIVE_LOGIC` if the
  redesign changes story logic, not just action legibility);
- hard gates: `IDENTITY` must not regress (unconditional), and no
  `HIGH`/`CRITICAL` regression on any other dimension;
- technical QC must pass; editorial fit must be proven for the same
  slot and trim.

## 7. Owner decision surface

- Blind legibility packet (answer key separated, as in Package-018) +
  side-by-side compare reel vs the canonical take.
- The Owner sees the full ten-dimension `tradeoff_summary()`; any soft
  regression requires an explicit `TRADEOFF_ACCEPTED=<dims>` note in
  the decision.
- Decision states: `ACCEPT` (selects the exact asset SHA) / `REJECT` /
  `DEFER` / `NEEDS_REPAIR` (routes back to a fresh Tech Lead package).

## 8. Stop conditions

Any of these ends the experiment package immediately:

1. sustained provider availability/anti-abuse failure (no retry —
   custody pattern: one submit, no blind retry);
2. any ambiguous external effect => `OWNER_AMBIGUITY_GATE`;
3. identity regression observed on the single render;
4. Generate budget exhausted without a review-ready candidate;
5. Owner decision is `REJECT` or `DEFER` (candidate stops; debt stays
   ACTIVE — a candidate alone never closes debt).

## 9. Invariants carried into V2-002

- `ExperimentAdmissionReceipt` REQUIRED before any live step
  (`BLOCKED_INVARIANT` otherwise) — `film_pipeline.quality_repair_v2.admission_gate`.
- No worker/model may mint `OWNER_SELECTED`; no aggregate quality score
  exists anywhere.
- V1 truth immutable: no V1 file, take, manifest, or master is modified
  by the experiment; all canonical change is via the frozen promotion
  transaction with retained rollback.
