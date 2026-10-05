# AI-FILM-QUALITY-V2-004 — F2 Direct-Blocking Live Experiment — Evidence Record

**Status: OWNER_DECISION_GATE** — the experiment ran clean (2/2
generates, zero retries, zero ambiguity) and the honest spatial result
is IN: both candidates FAIL the hard-required S-checks, so neither can
reach QUALITY_REVIEW_READY by the frozen rule. The Owner visual read is
authoritative and the full review surface is ready.

## 1. Custody chain

| Item | Value |
| --- | --- |
| Exact start SHA (V2-003 ingest final HEAD) | `7d257bf6bf471c463f0038d38ff2131ad6a9edd5` (branch `quality-v2/004-f2-blocking-live`) |
| Frozen director identities (rebound, unchanged) | DI/BS/CC ids + generation identity `5fa2b3ed75fbbafa…` — re-derived byte-identical at P0; **B1-B10 ALL_PASS re-proven; timing PASS** |
| Director receipt | OpenAI / GPT-5.6 Sol / DIRECTOR_SHOT_DESIGNER / Owner explicit authorization in Tech Lead chat |
| Compiler contract | flow-r2v-causal-compact-v1 (limits 500/75, fail-closed) |
| Previz manifest | `projects/quality_v2_003_director_blocking/previz_manifest_v2_003.json` (4 artifacts, sha-bound) |
| Canonical F2 predecessor | `take_91e4997b…` / asset `e84ba56c…` (slot 24, trim 0–5.6) |
| Canonical master | `976876a1…6595` — re-verified byte-identical (P11) |
| QD-001 | ACTIVE |
| PACKAGE_004_FINAL_HEAD_SHA | returned in the final worker report |

## 2. Admission (P1) — `experiment_admission_v2_004.json`

**EXA-81ec371495b6efe2 — ADMITTED** before any provider mutation.
Hypothesis (verbatim from the package), budget 2, uploads 0, route
UNCHANGED qualified Flow/Veo, canonical promotion 0, owner review
required, hard S-check acceptance criteria.

## 3. Candidate freeze (P2/P3) — `experiment_freeze_v2_004.json`

Both candidates share the FROZEN DirectorIntent / BlockingSpec /
CameraCoveragePlan / ActionIntent / screen direction (faces frame-left)
/ zones (BEFORE_GATE → CENTER_GATE_OPENING → BEYOND_GATE:FAR_SIDE_CLEAR)
/ travel path / route / reference (F2C last-frame binding) —
byte-equivalence proven (ActionIntent digest equality + embedded frozen
identity; only the performance layer differs). Candidate semantic
identities frozen BEFORE Generate #1:

| Candidate | Purpose | semantic identity | compiled prompt |
| --- | --- | --- | --- |
| F2C-V2-004-A | PURE TRAVERSAL | `9877ae7faae390c7…` | 414 chars / 62 words |
| F2C-V2-004-B | same blocking + biomechanics | `37f236b4a20243fb…` | 483 chars / 73 words |

Compiler conformance (P3): both wire texts mechanically contain
start-side state / direct-traversal commitment / gate / through /
far-side end read; no rock interaction (component-word scan against
the frozen BlockingSpec); envelope failure would have been
BLOCKED_INVARIANT (no silent shortening).

## 4. Generate ledger (P4)

| Candidate | Provider job | Output identity | Asset sha256 |
| --- | --- | --- | --- |
| A | `job_451bf6a4bc3f07d17f28a7c5a7…` (full in result.json) | `4b10aa08-c675-4ea1-a09e-7b6e4457f688` | `db03191ab185d0d8…` |
| B | `job_a61ed1acf11b87d587b3763dec…` | `279e5139-210d-4373-ac4d-3e1705801d5c` | `b573cf134021d4ac…` |

**2/2 consumed · 0 retries · 0 uploads · 0 ambiguous events · latch
OPEN.** Sequential submits; dispatch proven single per job; restart-safe
durable results.

## 5. Technical QC (P5) — `technical_qc_v2_004.json`

Both: full decode PASS, 8.0 s, 1280x720, CFR; deterministic 0.4 s
crossing strips (2.8–6.0 s) + early strips (0.2–2.6 s) + start/end
frames on disk. Technical failure would NOT have authorized retry.

## 6. PRIMARY RESULT — Spatial/Blocking QC (P6), worker advisory
(`observations_v2_004.json`; measured off the 0.4 s strips)

| Check | A | B |
| --- | --- | --- |
| S1 START_SIDE_VISIBLE | PASS | PASS |
| S2 FORWARD_COMMIT_VISIBLE | PASS | PASS |
| S3 PATH_DIRECT | **FAIL** (toward camera → 180° turn ~4.0 s → back to stones) | **FAIL** (overshoot left past the arch, return, then cross) |
| S4 NO_ROCK_CONTACT | PASS | PASS |
| S5 NO_ROCK_CIRCLING | PASS | PASS |
| S6 NO_REVERSAL | **FAIL** (~4.0 s) | **FAIL** (~3.6–4.4 s) |
| S7 GATE_THRESHOLD_VISIBLE | **FAIL** (no legible threshold boundary) | PASS (rectangular doorway unmistakable) |
| S8 FULL_BODY_CROSSES_THRESHOLD | **FAIL** (no crossing) | PASS (~5.6–6.0 s, through the doorway) |
| S9 CROSSING_BY_4_8_SECONDS | **FAIL** (no crossing) | **FAIL** (measured ≈5.8 s > 4.8 s) |
| S10 FAR_SIDE_REACHED | **FAIL** | **FAIL** (BEFORE→BEYOND direction semantics not unambiguously rendered) |
| S11 FAR_SIDE_READABLE_BY_5_6 | **FAIL** (static, back to camera) | **FAIL** (still inside the doorway plane at 5.4–5.6 s) |
| S12 END_SIDE_DISTINCT_FROM_START | **FAIL** | **FAIL** |
| S13 ROCK_NOT_DESTINATION | **FAIL** (ends static facing the stones — the V2-002 loitering failure REPEATS) | PASS (arch reads purely as passage) |

**Hard-required set: A fails 9/10, B fails 6/10.** Per the frozen rule
neither candidate can be QUALITY_REVIEW_READY: both stop at PROPOSED
with recorded review refusals (`candidates_governance_v2_004.json`).
No 10-dimension receipt was attached to either (the state machine
refuses); the advisory findings are preserved in observations.

## 7. Camera QC (P7) — independent of action quality

A: mechanics locked/no-orbit/no-axis-reversal PASS, but threshold not
legible and the rocks dominate the static end — **camera QC FAIL
overall**. B: **PASS overall** (locked, threshold legible, both sides
visible, trajectory visible, no geography collapse).

## 8. Owner review surface (P9/P10)

- Reel: `projects/quality_v2_004_f2_blocking/OWNER_F2_BLOCKING_V2_004_REEL.mp4`
  (sha256 `39cdaf5a2eaa7d82…`, BASELINE → CANDIDATE A → CANDIDATE B →
  Vietnamese question card; NOT blind by design — the Owner is
  explicitly reviewing the spatial repair).
- Copies (SHA-verified, sources untouched):
  - `OWNER_REVIEW/V2_004/BASELINE.mp4` — `e84ba56ccd0f556e…` (= the canonical take)
  - `OWNER_REVIEW/V2_004/CANDIDATE_A.mp4` — `db03191ab185d0d8…`
  - `OWNER_REVIEW/V2_004/CANDIDATE_B.mp4` — `b573cf134021d4ac…`
  - `OWNER_REVIEW/V2_004/COMPARE_REEL.mp4` — `39cdaf5a2eaa7d82…`
- Decision template
  (`owner_f2_blocking_decision_v2_004.template.json`): SELECT_A /
  SELECT_B / REJECT_ALL / KEEP_CANONICAL / NEEDS_REPAIR / DEFER;
  decision + selected sha are NULL; selection is FUTURE authority
  only; **no promotion in this package**. Worker S-verdicts are
  advisory — the Owner's visual read decides (V2-002 lesson honored in
  BOTH directions).

## 9. Canonical no-change (P11) — `canonical_no_change_v2_004.json`

Master `976876a1…` ✓ · F2 take `e84ba56c…` ✓ · `edit_manifest_id`
unchanged ✓ · tracked files clean ✓ · promotion ledger EMPTY ·
canonical mutation **0**.

## 10. Recovery (P12) — `recovery_matrix_v2_004.json`

**209 cases total**: 147 reused frozen cases (89 V2-001 + 28 V2-002 +
30 V2-003; all still executed live) + **62 V2-004 package cases**
executed against live guards
(`tests/test_v2_004_recovery_001.py`): compiler rock additions
(contact/brace/circle/shelter), plan-level hallucinations, stop-at-rock,
reversal, crossing after 4.8 s, far-side after 5.6 s, missing anchors,
never clears threshold, camera hides crossing / too tight / geography
collapse, candidate B changing blocking/camera/ActionIntent, third
generate, retry, ambiguous output, single-dispatch, wrong mapping,
wrong asset copy, worker auto-select, worker claims Owner acceptance,
in-package promotion, canonical/EditManifest/take mutation, V1
mutation, envelope shortening, question-card completeness, alternate
scope, null-ack interpretation. Any ambiguity: OWNER_AMBIGUITY_GATE.

## 11. Final verification (P13)

- **1165 tests passed** (918 V1 + 140 V2-001 + 26 V2-002 + 55 V2-003 +
  26 V2-004), 0 failed, network-free.
- compileall clean · `git diff --check` clean · secret scan clean ·
  SoT manifest 30/30.

## 12. Honest reading for the Owner

The frozen spatial plan **improved the legibility of the gate as a
threshold** (B's doorway geometry and S7/S8/S13 PASS) but the qualified
route did not execute the frozen DIRECT traversal: A reverted to the
exact loitering failure the Owner rejected in V2-002; B crossed the
threshold but added an unauthorized reversal/overshoot and crossed
after the 4.8 s deadline, and the far-side direction semantics stayed
ambiguous. The binding constraints that failed are the ROUTE's staging
interpretation, not the authority layer (identity of the frozen plan
never drifted; B1–B10 held on the plan itself). Candidate levers for a
future package (Owner's call, NOT part of this one): tighter
waypoint/timing phrasing inside the same envelope, or the
shot-decomposition lever (QH-2) — no plan redesign happened here and
none is proposed by this package.

## 13. Unresolved unknowns

1. The Owner's decision (the package ends AT the decision gate).
2. Why the route stages a reversal/overshoot against a direct-traversal
   spec (provider behavior; bounded evidence, no universal claim).
3. Whether any prompt-expressible variation can pin the crossing inside
   4.8 s on this route.

## 14. Final status

**OWNER_DECISION_GATE** — admission proven · frozen plan used exactly
(redesign 0) · ≤2 Generates (2 consumed) · 0 retries · clean
attribution · honest S1–S13 recorded · blind-free Owner surface ready
· canonical unchanged · no promotion. PACKAGE_004_FINAL_HEAD_SHA is
returned in the final worker report.
