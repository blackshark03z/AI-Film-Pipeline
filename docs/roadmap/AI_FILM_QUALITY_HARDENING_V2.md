# AI FILM QUALITY HARDENING V2 — Handoff Roadmap (Package-019, Phase V7)

**Status:** NOT an active implementation package. No provider
selection, no implementation, no generation authorized by this
document. This is the bounded handoff of known creative-quality work,
organized by PROBLEM (not by individual failed shot), for a future
dedicated track. Evidence references point into the frozen Package-017
/ 018 / 019 records.

**Context:** `AI_FILM_PIPELINE_V1_TECHNICAL = PROVEN_COMPLETE` while
`FILM_CREATIVE_QUALITY_ACCEPTED = false` (Owner decision,
`owner_quality_decision_019.json`; debt registry
`quality_debt_registry_019.json` QD-001..005).

---

## QH-1 — Narrative / action causality
- **Problem:** shots render natural motion but do not communicate
  WHY the character acts, WHAT he wants, WHAT changes (debt QD-001,
  QD-002).
- **Evidence from current film:** 018 baseline meaning review —
  canonical F2C/G3C NOT_LEGIBLE standalone; 018-A rendered the causal
  chain visibly (CAUSAL_CONTROL_EFFECT_OBSERVED) but is not promoted.
- **Existing mechanism:** ActionIntent v1 + gate A1
  (recover-intent-from-authority-or-no-generation), causal legibility
  checks, causality graph with state-change invariant, causal compiler
  `flow-r2v-causal-compact-v1`.
- **Remaining unknown:** whether redesigned shot INTENT (new
  dramatic_purpose/beats, not just compiled direction) plus the
  existing causal pipeline yields Owner-accepted meaning.
- **Proposed experiment:** one bounded redesign package on ONE shot:
  rewrite the ShotSpec action logic from the narrative authority
  (Owner-approved), run ≤2 generates through the causal compiler,
  blind-review against the answer key.
- **Success criterion:** the Owner's blind read of trigger/goal/
  outcome matches the authoritative intent without hints.

## QH-2 — Shot decomposition / one-dominant-action design
- **Problem:** multi-beat physical actions compress into stiff or
  illegible single clips.
- **Evidence:** 017 classifier flagged EXTREME/HIGH cases; 018 causal
  complexity recommends SPLIT_NARRATIVE_BEAT / INSERT_REACTION_SHOT /
  ESTABLISH_TRIGGER (advisory only, never auto-applied).
- **Existing mechanism:** action-complexity + causal-complexity
  classifiers; EditorialRange contract; edit pipeline.
- **Remaining unknown:** the cost/benefit of splitting one dense beat
  into two shots against the master's rhythm.
- **Proposed experiment:** take one flagged EXTREME design, produce a
  split two-shot alternative + revised edit slice, compare reels.
- **Success criterion:** the split version reads causally AND
  conformance + master rebuild stay clean.

## QH-3 — Character full-body proportion authority
- **Problem:** silhouettes can read short/compact; no full-body
  reference exists (debt QD-003; 017 Q1 INCONCLUSIVE).
- **Evidence:** chest-up base reference only; 017-A (proportion-only)
  lost to a provider anti-abuse failure; 017-C confounded by
  re-staging.
- **Existing mechanism:** BodyProportionAuthority v1 (exact = UNKNOWN,
  directional constraint only); the fake-precision refusal.
- **Remaining unknown:** whether body proportion is prompt-controllable
  on this provider WITHOUT identity drift.
- **Proposed experiment:** (a) obtain an Owner-approved full-body
  reference (content input) → upgrade BODY_PROPORTION_EXACT_AUTHORITY;
  (b) one isolated A/B proportion canary with identity-compare.
- **Success criterion:** silhouette improves with FACE_IDENTITY/HAIR/
  COSTUME unchanged under blind side-by-side.

## QH-4 — Blocking / biomechanics / performance choreography
- **Problem:** canonical action reads stiff (debt QD-004) even though
  choreography direction is proven effective (017 Q2
  CONTROL_EFFECT_OBSERVED).
- **Evidence:** baseline PERFORMANCE_STIFFNESS FAIL; 017-B/C
  materially more natural; PerformanceSpec beats render.
- **Existing mechanism:** PerformanceSpec v1 (biomechanics fields +
  beats) + phrase-capped movement clause in the wire compilers.
- **Remaining unknown:** how much choreography density fits the
  qualified 500/75 envelope before quality saturates.
- **Proposed experiment:** a small choreography-intensity ladder (1/2/
  3 movement phrases) on one action shot, motion-packet compared.
- **Success criterion:** monotone improvement to saturation with the
  optimum documented.

## QH-5 — Camera motivation and action coverage
- **Problem:** staging drifts (re-framing, re-staging) between takes
  of the same spec; coverage of an action (through-state) is not
  guaranteed.
- **Evidence:** 017-B/C re-staged the gate; 018-B drifted to bracing
  AT the rock.
- **Existing mechanism:** locked-camera reductions; continuity
  invariants; reel comparisons.
- **Remaining unknown:** how much staging control the qualified route
  exposes (blocking wording vs reference framing).
- **Proposed experiment:** same action, three blocking-wording
  variants, measure staging stability against the reference frame.
- **Success criterion:** a documented staging-control recipe with
  ≥2/3 renders matching the intended coverage.

## QH-6 — Temporal motion QC
- **Problem:** the qualified 3-frame sampling cannot judge motion
  (debt QD-005); no autonomous temporal QC exists.
- **Evidence:** 014 all-shot INCONCLUSIVE; MotionReviewPacket v1
  proven (dense 10 fps evidence + 11 dimensions); worker semantic
  backend NOT_QUALIFIED.
- **Existing mechanism:** dense packets, grids, compare reels —
  Owner-judgment surfaces.
- **Remaining unknown:** whether ANY backend can pass the frozen
  semantic qualification corpus (replacement contract sections 4-8)
  and extend to motion dimensions.
- **Proposed experiment:** qualify a future API backend per the
  frozen contract; if qualified, extend the packet dimensions to it.
- **Success criterion:** a qualified backend + repeatable motion
  verdicts on the frozen baseline packets.

## QH-7 — Provider/model capability benchmarking
- **Problem:** single-provider experience; the anti-abuse render
  rejection (017-A, not charged) shows operational fragility; no
  capability ceiling map.
- **Evidence:** 017 Q3 classified within-scope only; "unusual
  activity" failure cause UNKNOWN.
- **Existing mechanism:** frozen qualification corpus + acceptance
  (A-L); cross-backend comparison contract; budget/no-retry custody.
- **Remaining unknown:** relative capability of other providers/models
  on THIS film's shot classes.
- **Proposed experiment:** Owner-authorized benchmark package on the
  frozen corpus + one canonical shot per class, same custody rules.
- **Success criterion:** a capability table with per-class verdicts,
  no universal claims.

## QH-8 — Quality repair policy / candidate selection
- **Problem:** five candidates exist across 017/018 (evidence-only);
  the promotion path (Owner decision bound to exact asset SHA) is
  built but unused; repair policy for quality (vs technical) failure
  is undefined.
- **Evidence:** owner_motion_decisions_017.template.json +
  owner_action_decisions_018.template.json (unpopulated); debt
  registry.
- **Existing mechanism:** SelectedTake authority, RepairDecision,
  OwnerReviewDecision ledger with supersession.
- **Remaining unknown:** the policy for WHEN a repair/candidate
  replaces a canonical take (who decides, what evidence, how the
  master rebuilds).
- **Proposed experiment:** write the policy as a Tech Lead package
  (no generation): decision rights, evidence bar, master-rebuild
  procedure, rollback.
- **Success criterion:** a frozen, Owner-approved repair/selection
  policy document.

---

**Track rules (inherited):** every experiment keeps the custody
pattern (frozen intent → one submit → no retry → ambiguity =
OWNER_AMBIGUITY_GATE); identity never regresses for meaning; the
canonical master only changes through an explicit Owner selection.
