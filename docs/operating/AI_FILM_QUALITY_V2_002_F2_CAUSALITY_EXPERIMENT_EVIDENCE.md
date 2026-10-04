# AI-FILM-QUALITY-V2-002 — F2 Action-Causality Redesign — Live Bounded Experiment — Evidence Record

**Status: OWNER_DECISION_GATE** — the blind Owner surface is ready and
the Owner can now judge whether the redesigned action logic is actually
better. NO candidate is promoted in V2-002.

## 1. Custody chain

| Item | Value |
| --- | --- |
| Exact start SHA (V2-001 final revision) | `5793dc55bb1ae5d5ff2cb22e02e0ead760f53f46` (branch `quality-v2/002-f2-causality-experiment` created from it) |
| V1 frozen baseline | `14ba281d12c15a5678a3fe1b3f0242f577512e5f` — verified ancestor at P0 |
| Canonical master | `976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595` — re-verified byte-identical at P15 |
| Canonical F2 predecessor | `SEQ7_F2C` slot 24, take `take_91e4997b…f31efb67`, asset sha `e84ba56c…90a767`, editorial range `er_790f3678…`, trim 0–5.6 s |
| PACKAGE_002_FINAL_HEAD_SHA | returned in the final worker report (no self-referential SHA field) |

## 2. Admission (P2) — `experiment_admission_v2_002.json`

`ExperimentAdmissionReceipt` **EXA-e0afeb407d0cae60**, gate **ADMITTED**
(known debts QD-001..005; baseline equals the frozen
QUALITY_V2_CANONICAL_BASELINE; max_generate_budget = 2; provider route =
the exact qualified Flow/Veo route `flow_veo / veo_3_1_r2v_lite /
project 93a579b4-834e-435b-8304-5f6682937935 / clean-pro-qualified`).

## 3. Owner-approved F2 intent (P1) — `owner_approved_f2_intent_v2_002.json`

Frozen verbatim from the work package; intent fingerprint
`1610b18ea35ed9b1122ae22a0a4d20cd44f9dd196d882aa5a68a379cc2cd65b0`;
bound to the canonical predecessor, the narrative authority
(`sequence_plan_007` SCENE_F_STORM_GATE + `action_authority_trace_018`
gate A1 = RESOLVED), and QD-001. Used EXACTLY — no new story events.

## 4. Candidate designs (P3/P4) — `f2_redesign_v2_002.json`, `experiment_freeze_v2_002.json`

Frozen BEFORE Generate #1 on the existing rails only (ShotSpec +
ActionIntent v1 + PerformanceSpec v1 + `flow-r2v-causal-compact-v1` +
BodyProportionAuthority). Dominant objective: PASS THROUGH THE GATE
AGAINST THE GUST. Critical negatives compiled into the fixture
`performance.forbidden` (full Owner wording preserved in the redesign
record). Prompt envelope: A 476 chars / 73 words, B 481 chars / 74
words (limits 500/75, fail-closed).

| Candidate | Design | fixture_sha256 (prompt basis) | prompt_sha256 (live) |
| --- | --- | --- | --- |
| F2C-V2-002-A | CAUSAL CLEAN — simple blocking, no stone contact, no sword action | recorded in freeze | `b5fe82612a0cd049…` |
| F2C-V2-002-B | same meaning + bounded realism (weight shift, planted steps, functional brief brace, settle) | recorded in freeze | `2e361e1ca8f42ad0…` |

ActionIntent digest + PerformanceSpec digest recorded per candidate in
the freeze. Both reference the F2C binding (SEQ7_F1 last frame,
media `8f2f5277…`, attestation `refbind_f4277ac1…`), 0 uploads.

## 5. Generate ledger (P6) — `generate_ledger.json`, `mutation_authority.json`

| Candidate | Provider job | Output identity | Released (UTC) |
| --- | --- | --- | --- |
| A | `job_4ca55a57c78d3565a56b0547f20dcc63ba69ae9bb2487bb7d186d15a3371114b` | `89f41f93-53c6-41a4-aa29-a69a222f1517` | 2026-10-04T12:56:54 |
| B | `job_f92362d217077d0e050581f0bd7014640f128c83c6ef754716da40a3738193a1` | `9fb7bd78-f5ad-4437-a398-0833987078e2` | 2026-10-04T12:57:59 |

**2 / 2 consumed · 0 retries · 0 uploads · 0 ambiguous events.** One
native-UI submit per candidate (guarded route), dispatch reservation
proven single (`dispatch_count == 1` both jobs in the shared durable
store). Mutation authority stayed OPEN (no ambiguity ⇒ no latch).

## 6. Assets + technical QC (P7) — `technical_qc_v2_002.json`

| Candidate | Asset sha256 | Probe | Full decode |
| --- | --- | --- | --- |
| A | `cb89df69459be66d1a08cc8e669b3a9603ce87949e8116c7bd28296ffdb3d48a` | 8.0 s · 1280x720 | PASS |
| B | `3071eaea20277ce7bc7f555c4202b24770f821ec2fe271aa8474471eae1a07f4` | 8.0 s · 1280x720 | PASS |

Trim-compatible with the 5.6 s editorial slot (window 0–5.6 inside the
8 s render). Acquisition receipts bound (file sha == receipt sha).
Dense 8 fps motion packets + frame strips on disk (`qc_evidence/`).

## 7. Identity QC (P8) — `qc_evidence/identity_side_by_side_v2_002.png`

Worker advisory grid observation (baseline vs A vs B at t=0.2/2.8/5.0):
**UNCHANGED on both** — white robes, white hair ribbon + topknot, facial
features, slim silhouette all consistent; no visible drift. Limitations
recorded: no automated identity authority is qualified; the final
identity judgment belongs to the Owner on the same reel.

## 8. Blind review (P12) — protocol kept

1. Blind reel built FIRST: `OWNER_F2_CAUSALITY_V2_002_REEL.mp4`
   (sha256 `100805ea6d1acd3028921cce840c8015fa9dc0e70352d0731632eb77e5fb9ff5`),
   neutral labels BASELINE / CANDIDATE 1 / CANDIDATE 2, order fixed by a
   deterministic hash draw; the intent card plays only AFTER the blind
   section.
2. The worker answered the five questions **blind**
   (`owner_f2_blind_review_v2_002.json`, `answered_blind: true`) BEFORE
   the answer key was opened.
3. Answer key (`answer_key_v2_002.json`, separate): **CANDIDATE 1 = A
   (cb89df69…), CANDIDATE 2 = B (3071eaea…)**.
4. Blind read: BOTH candidates show a clear through-state (pass between
   the stones); the baseline stays braced at the rock with no
   communicated goal; B showed a clearer perceptual beat (reads the
   gust) before pushing. Leak scan clean (no candidate ids, no intent,
   no mapping in the blind surfaces).

## 9. Causality review + 10-dimension receipts (P9/P10)

Per-candidate open observations (`observations_v2_002.json`) recorded
the 8 causal dimensions + 5 critical negatives independently (no
scoring), then the governed receipts were minted through the frozen
V2-001 state machine:

| Candidate | Governed id | State | Target dim | Identity |
| --- | --- | --- | --- | --- |
| F2C-V2-002-A | `QRC-1bd5a34bdefcffba` | QUALITY_REVIEW_READY | ACTION_CAUSALITY = IMPROVED | UNCHANGED |
| F2C-V2-002-B | `QRC-8c1b2dbe614c2489` | QUALITY_REVIEW_READY | ACTION_CAUSALITY = IMPROVED | UNCHANGED |

Receipts carry all ten dimensions (no aggregate score anywhere;
`no_aggregate_score: true`), no REGRESSED finding on either candidate,
identity receipts UNCHANGED, technical receipts PASS. **No Owner
decision was minted** (`no_owner_decision_minted: true`) — the Owner
selects through the template below.

## 10. Editorial fit (P11)

Preview successor manifests only (slot 24 replaced; build_successor
deterministic); the canonical EditManifest was NOT modified
(`editorial_plan_010.json` + `ranges/24_SEQ7_F2.json` untouched;
`edit_manifest_id edit_c82343ee…` unchanged in master_summary).
Receipts: editorial_compatible + trim_compatible TRUE for both, with
entry/exit continuity observations (entry consistent with F1 last
frame; exit cuts acceptably into F3's calm wall-lean — flow improved).

## 11. Owner decision template (P13) — `owner_f2_decision_v2_002.template.json`

Six options (SELECT_CANDIDATE_A / SELECT_CANDIDATE_B / KEEP_CANONICAL /
REJECT_ALL / DEFER / NEEDS_REPAIR); a selection must bind the exact
candidate asset sha256; per-candidate 10-dimension tradeoff summary +
technical/identity/editorial receipts + blind answers exposed. **This
package does NOT execute promotion**: a selection stops at
OWNER_SELECTED; NEXT = V2-003_PROMOTION_ADAPTER_QUALIFICATION.

## 12. Experiment classification (P14) — `quality_v2_002_experiment_result.json`

ACTION_CAUSALITY_EFFECT = **EFFECT_OBSERVED** · SHOT_DESIGN_EFFECT =
**EFFECT_OBSERVED** · PERFORMANCE_EFFECT = **EFFECT_OBSERVED** ·
EDITORIAL_FIT = **PASS**. Q1 YES (purpose readable blind) · Q2 YES
(through-state unambiguous) · Q3 YES per advisory identity grids · Q4
not applicable (no failure state reached). Scope-limited; no universal
provider claims.

## 13. Canonical no-change proof (P15) — `canonical_no_change_v2_002.json`

Master sha256 == frozen `976876a1…` ✓ · canonical F2 take bytes ==
`e84ba56c…` ✓ · 0 tracked files modified ✓ · no V2 candidate in the
canonical lineage ✓ · **promotion ledger: EMPTY** · canonical mutation
**0** · both candidates remain QUALITY_REVIEW_READY (evidence only).

## 14. Recovery / adversarial (P16) — `recovery_matrix_v2_002.json`

**117 cases total**: 89 reused frozen V2-001 governance cases
(re-executed live by `tests/test_quality_v2_recovery_matrix_001.py`) +
28 package cases (executed by
`tests/test_quality_v2_002_recovery_001.py`: wrong baseline /
predecessor / QD, missing admission, budget >2, third generate,
duplicate dispatch, ambiguity latch, blind retry, mislabel, intent
leak, blind-order discipline, ends-at-rock / hides-behind-rock /
through-state absent, identity drift, logic-vs-performance trade-off,
editorial-fit refusal, EditManifest/master/lineage mutation,
forged selection, in-package promotion, stale reference, wrong output
identity, hidden trade-off, aggregate score, ambiguous attribution).
Any future external-effect ambiguity remains **OWNER_AMBIGUITY_GATE**.

## 15. Final verification

- **1084 tests passed** (918 V1 predecessor + 140 V2-001 + 26 V2-002
  package), 0 failed, network-free, ~3 m 10 s.
- compileall clean · `git diff --check` clean · secret scan clean ·
  SoT manifest 30/30.

## 16. Unresolved unknowns

- The Owner's actual decision (the package ends AT the decision gate).
- Identity/temporal-motion judgments remain worker-advisory + Owner
  surfaces; no qualified automated backend exists (QD-005 stands).
- Whether the Owner prefers A (clean) or B (refined) is exactly the
  creative judgment this package was built to expose — not to predict.

## 17. Final status

**OWNER_DECISION_GATE** — admission proven · Owner-approved intent used
exactly · ≤2 Generates (2 consumed) · 0 retries · clean attribution ·
2/2 technically valid review-ready candidates · blind Owner surface
ready · 10-dimension tradeoffs visible · canonical F2/master unchanged.
PACKAGE_002_FINAL_HEAD_SHA is returned in the final worker report.
