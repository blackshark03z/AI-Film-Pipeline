# V2-006 F2 DECOMPOSED LIVE HANDOFF

**From:** AI-FILM-QUALITY-V2-005 (F2 shot-decomposition design, frozen)
**To:** V2-006 (decomposed live experiment, when the Owner authorizes it)
**Status:** HANDOFF — **V2_006_READY = false** pending the Owner's
authorization of the reference-strategy amendment (V2-005R preflight:
`projects/quality_v2_005r_reference_preflight/reference_preflight_v2_005r.json`).
The frozen two-shot plan itself is unchanged.

---

## 1. Target

Replace canonical F2 (SEQ7_F2C, slot 24, 5.6 s) with TWO shots:
**F2A — COMMIT TO CROSS** (2.8 s) + **F2B — EMERGE FAR SIDE** (2.8 s).
Total scene duration UNCHANGED (5.6 s; D9 BOUNDED). Debt QD-001 stays
ACTIVE. V2-004 REJECT_ALL is recorded (`v2_004_owner_decision.json`);
neither V2-004 candidate is reusable.

## 2. Frozen plans (do NOT redesign)

`projects/quality_v2_005_f2_decomposition/f2_decomposition_plan_v2_005.json`:

- **F2A**: BEFORE_GATE → committed arrival AT the threshold
  (`CENTER_GATE_OPENING:AT_THRESHOLD`, crossing NEVER completes in-shot;
  B1–B10 ALL_PASS, arrival anchor 2.4 s); camera WS near-side three-
  quarter, threshold centered; forbidden zones AT_ROCK + BEYOND_GATE.
- **F2B**: opens already crossing / just beyond the threshold
  (`CENTER_GATE_OPENING:CROSSING_OR_JUST_BEYOND`), one-direction
  movement away, ends `BEYOND_GATE:FAR_SIDE_CLEAR` (B1–B10 ALL_PASS,
  far-side readable 2.4 s); camera WS beyond-gate placement — the gate
  BEHIND the subject; forbidden zones AT_ROCK + BEFORE_GATE.
- Editorial states frozen: F2A_END =
  `AT_THRESHOLD_COMMITTED_FORWARD`, F2B_START =
  `CROSSING_OR_JUST_BEYOND_THRESHOLD`, F2B_END = `FAR_SIDE_CLEAR`;
  the cut is a legitimate ellipsis ("He crossed.").
- D1–D10 ALL_PASS; story meaning preserved verbatim; rock interaction
  forbidden COMPLETELY in both shots.

## 2b. REFERENCE STRATEGY AMENDMENT (V2-005R preflight — REQUIRED)

The preflight classified the frozen F2C reference (media `8f2f5277…`,
sha `fecf669e…`) as **FULL_FRAME_ENVIRONMENTAL**: it visually encodes
NEAR-SIDE gate geography (rock at frame-left, subject beside it, far
side occluded). Consequences, proven mechanically from the exact
hashed bytes:

- **F2A_REFERENCE_COMPATIBLE = true** (near-side shot, near-side
  reference).
- **F2B: REFERENCE_GEOGRAPHY_CONFLICT** — the far-side plan requires
  the gate BEHIND the subject with BEFORE_GATE forbidden; the
  full-frame near-side conditioning materially constrains that
  geography, and prompt text is NOT proven to override it.

**Smallest fix (option 1, no upload):** bind F2B to the
ALREADY-QUALIFIED identity-only reference — media `7b725f7b-4da5-4455-
a6f2-135c4ba22397`, asset `asset_2ab16c9f…`, sha `ed75a8b2…` (chest-up
portrait, clouds only, zero gate geography; adopted provider media with
full store provenance, qualified since Packages 003+). F2A keeps the
near-side full-frame reference. **0 uploads; 0 provider switch.** V2-006
may run ONLY after the Owner authorizes this split-reference strategy.

## 3. Budget and route (frozen)

- Generates: **2 total — exactly 1 submit for F2A, 1 for F2B.** No
  alternate takes in this first experiment.
- Uploads: 0 (both shots reference the already-bound SEQ7_F1 last-frame
  media; the F2C binding carries over).
- Provider route: UNCHANGED qualified Flow/Veo route unless explicitly
  re-qualified by a dedicated package.
- Retries: 0. Ambiguity => OWNER_AMBIGUITY_GATE; do not submit F2B
  after an F2A ambiguity.
- Canonical promotion: 0 (selection = future authority; promotion needs
  a dedicated adapter package).

## 4. Fixture guidance (for the V2-006 freeze)

Both ShotSpecs compile through `flow-r2v-causal-compact-v1` with the
frozen ActionIntent semantics split across the pair:

- F2A wire: trigger (gust hits) + set/commit + `Start: near side; End:
  at the gate opening` — the word "brace" must NOT co-occur with
  "rock" (compiler boundary); use "sets himself".
- F2B wire: opens through/just past the opening + continues onward +
  `End: beyond gate, far side clear`.
- The envelope (500 chars / 75 words) is fail-closed: if the frozen
  semantics cannot fit, BLOCKED_INVARIANT — no silent shortening.

## 5. Owner review surface (mandatory)

Reel: **BASELINE F2 → NEW F2A + F2B CUT** (the two new shots joined by
the frozen cut), then the questions:

1. Is the goal obvious?
2. Does the cut clearly communicate that he crossed the gate?
3. Does he ever appear to loiter around the rock?
4. Is the direction of travel coherent?
5. Does the two-shot version feel more natural than the old F2?

Decision options (ATOMIC PAIR contract, V2-005R):
**SELECT_F2A_F2B_PAIR / REJECT_ALL / KEEP_CANONICAL / NEEDS_REPAIR /
DEFER**. The pair is judged as ONE editorial solution — NO option can
select F2A alone or F2B alone (an editorially orphaned half-shot is
unusable). Selection is future authority only (promotion via the
adapter package).

## 6. Stop conditions

1. Either shot ambiguous at the provider => OWNER_AMBIGUITY_GATE (no
   second submit).
2. Envelope cannot express a frozen semantic => BLOCKED_INVARIANT.
3. Either shot's S-hard checks fail at QC => that shot is refused;
   the pair cannot be review-ready (both shots must pass their
   hard checks).
4. Budget exhausted without two usable renders.
5. Owner rejection => QD-001 stays ACTIVE.
