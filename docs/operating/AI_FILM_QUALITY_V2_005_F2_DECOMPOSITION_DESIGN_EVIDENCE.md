# AI-FILM-QUALITY-V2-005 — F2 Shot-Decomposition Design — Evidence Record

**Status: COMPLETED_CANDIDATE** — the two-shot decomposition plan is
FROZEN with all gates PASS; no generation, no provider contact, no
canonical mutation.

## 1. Custody chain

| Item | Value |
| --- | --- |
| Exact start SHA (V2-004 final HEAD) | `a1dec4d27882dddf27adeb91449d3fcc41e771ad` (branch `quality-v2/005-f2-decomposition`) |
| Frozen V2-003 director identities | rebound byte-identical (`start_custody_v2_005.json` vs the 019-era plan `director_layer`) |
| V2-004 evidence | `AI_FILM_QUALITY_V2_004_F2_BLOCKING_LIVE_EXPERIMENT_EVIDENCE.md` |
| F1/F2/F3 continuity | `faces frame-left`; durations 4.8 / 5.6 / 3.2 s |
| Canonical EditManifest | `edit_c82343ee…c7969d3` (UNCHANGED) |
| Canonical F2 slot | 24, SEQ7_F2C, 5.6 s |
| Canonical master | `976876a1…6595` — re-verified byte-identical |
| PACKAGE_005_FINAL_HEAD_SHA | returned in the final worker report |

## 2. V2-004 Owner decision custody — `v2_004_owner_decision.json`

**V2_004_OWNER_DECISION = REJECT_ALL**, reasons verbatim:
LOITERING_FAILURE_REPEATED (A) · REVERSAL_OVERSHOOT (B) ·
CROSSING_AFTER_DEADLINE (B) · FAR_SIDE_NOT_READABLE (B). Recorded
through the frozen state machine — both V2-004 renders minted as
governed candidates from their exact custody and transitioned
PROPOSED → **OWNER_REJECTED** (the Owner-rejection-at-any-state rule,
added this package). No promotion. **QD-001 stays ACTIVE.**

## 3. The frozen decomposition — `f2_decomposition_plan_v2_005.json`

Story meaning preserved verbatim (trigger / goal / outcome / NOT-goal:
destination, cover, interaction target; no new story events).

**F2A — COMMIT TO CROSS (trim 2.8 s)**
- START clearly BEFORE_GATE → gust hits → he sets himself against it
  with BODY ONLY → committed arrival AT the threshold
  (`CENTER_GATE_OPENING:AT_THRESHOLD`, anchor 2.4 s).
- The crossing NEVER completes in-shot: BEYOND_GATE is a FORBIDDEN
  zone; the crossing waypoint is the LAST waypoint (D2).
- Camera: WS near-side three-quarter, threshold centered; no orbit /
  reversal / axis cross.

**F2B — EMERGE FAR SIDE (trim 2.8 s)**
- OPENS already crossing / just beyond the threshold
  (`CROSSING_OR_JUST_BEYOND`), one-direction movement away, ends
  `BEYOND_GATE:FAR_SIDE_CLEAR` (readable by 2.4 s).
- Camera: WS beyond-gate placement — the gate reads BEHIND him; the
  angle itself proves the far side. BEFORE_GATE is a forbidden zone.

**Editorial state transition (frozen)**: F2A_END =
`AT_THRESHOLD_COMMITTED_FORWARD` → F2B_START =
`CROSSING_OR_JUST_BEYOND_THRESHOLD` → F2B_END = `FAR_SIDE_CLEAR`.
The cut is a legitimate ellipsis — the audience infers "He crossed."
— no continuous crossing footage is required (D7).

**Timing**: 2.8 + 2.8 = 5.6 s = the EXISTING F2 allocation. Scene
duration is NOT doubled (D9 bounded at 6.4 s max).

## 4. Gates

- **B1–B10**: ALL_PASS for BOTH shots (run against the frozen F1/F3
  screen-direction authority).
- **D1–D10**: ALL_PASS — story meaning preserved (semantic anchors),
  one dominant action per shot (F2A never crosses; F2B opens across),
  threshold-family handoff compatible, far side observable, rock never
  a destination (all four ROCK_* interactions forbidden in BOTH plans +
  AT_ROCK zones), no reversal required, ellipsis legible, F1→F2A→F2B→F3
  chain bound at `faces frame-left`, duration bounded, canonical
  unchanged.

## 5. Preview EditManifest (P6) — canonical untouched

`preview_edit_manifest` inside the plan JSON: 31 clips (30 canonical
slots − SEQ7_F2C + F2A + F2B), contiguous orders, F2A/F2B at 2.8 s
each, total 194.4 s (≤ canonical 194.54). Deterministic derived id
`edit_f4d258e8…`; **payload-only construction — never written to any
store; the canonical EditManifest byte-unchanged.**

## 6. Previz (P7) — `previz_manifest_v2_005.json`

`F2A_BLOCKING_TOPDOWN.png` · `F2B_BLOCKING_TOPDOWN.png` ·
`F2A_START_END_SCHEMATIC.png` · `F2B_START_END_SCHEMATIC.png` ·
`F2_DECOMPOSITION_PREVIZ.mp4` (BEFORE_GATE → THE CUT → BEYOND_GATE,
visually verified) — sha-manifested, watermarked PLANNING EVIDENCE.

## 7. Recovery (P10) — `recovery_matrix_v2_005.json`

**261 cases total**: 209 reused frozen cases (89+28+30+62; all still
executed live) + **52 decomposition cases** executed against live
guards (`tests/test_v2_005_decomposition_001.py` + the D-gate failure
modes): new story events, missing meaning anchors, in-shot crossing
completion, misplaced/extra crossing waypoints, family mismatches,
rock-interaction allowances, editorial-state drift, direction
conflicts, duration doubling, preview/canonical id collision, missing
generation/upload/provider surface, previz determinism and CUT-card
presence, handoff budget/question integrity. Any ambiguity:
OWNER_AMBIGUITY_GATE.

## 8. Governance extension (minimal, additive)

- `quality_repair_v2`: Owner REJECTION/DEFERRAL now available at ANY
  state (authority truth); SELECTION still requires the full
  QUALITY_REVIEW_READY chain. Existing refusals unchanged.
- `director_blocking`: B5 circling refined to family RE-ENTRY after
  leaving (deepening within a family is progress); B6 vacuous when no
  crossing is marked; D1–D10 decomposition gates added. All 209 reused
  recovery cases still pass unmodified in behavior.

## 9. Verification

- **1185 tests passed** (918 V1 + 140 V2-001 + 26 V2-002 + 55 V2-003 +
  26 V2-004 + 20 V2-005), 0 failed, network-free.
- External calls 0 · generation 0 · Flow submit 0 · upload 0 ·
  canonical mutation 0.
- compileall clean · `git diff --check` clean · secret scan clean ·
  SoT manifest 30/30.

## 10. Unresolved unknowns

1. Whether the qualified route renders the F2A commit and the F2B
   emerge legibly (that is exactly V2-006).
2. The Owner's acceptance of the two-shot rhythm at the review reel.
3. Prompt phrasing for "sets himself" vs the rock-word co-occurrence
   boundary (V2-006 freeze resolves it mechanically).

## 11. Final status

**COMPLETED_CANDIDATE** — DIRECTOR_DECOMPOSITION = FROZEN ·
DECOMPOSITION_GATES = ALL_PASS (D1–D10 + B1–B10 ×2) ·
VIDEO_GENERATION = 0 · CANONICAL_MUTATION = 0 · NEXT =
V2_006_F2_DECOMPOSED_LIVE (budget 2: 1+1, no alternate takes).
PACKAGE_005_FINAL_HEAD_SHA is returned in the final worker report.
