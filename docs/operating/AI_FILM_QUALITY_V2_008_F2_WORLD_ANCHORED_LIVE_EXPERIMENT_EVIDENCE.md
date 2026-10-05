# AI-FILM-QUALITY-V2-008 — F2 World-Anchored Live Experiment — Evidence Record

**Status: OWNER_DECISION_GATE** — FIRST PACKAGE IN THE V2 TRACK WITH
BOTH HALVES PASSING ALL HARD QC: the pair is QUALITY_REVIEW_READY
(worker advisory). No promotion; Owner decision = future authority.

## 1. Custody chain

| Item | Value |
| --- | --- |
| Exact start SHA (V2-007 final HEAD) | `ceecf2781c7f2c46962088f9627a0b59bc7d580d` (branch `quality-v2/008-world-anchored-live`) |
| Owner authorization | `AUTHORIZE_V2_008 = ONE_REFERENCE_UPLOAD + F2A_PACING_DELTA` (Owner explicit approval in Tech Lead chat after V2-007); NOT authorized: second upload, alternate reference/take, retry, provider switch, extra Generate, canonical promotion |
| Frozen V2-005 lineage | F2A/F2B DI/BS/CC ids rebound; V2-005 F2A plan PRESERVED (revision 2 created alongside) |
| Canonical | F2 take `e84ba56c…`, EditManifest `edit_c82343ee…`, master `976876a1…6595` — all re-verified byte-identical |
| QD-001 | ACTIVE |
| PACKAGE_008_FINAL_HEAD_SHA | returned in the final worker report |

## 2. Frame re-extraction (P1) — `frame_reextraction_v2_008.json`

Re-extracted @6.6 s from the EXACT acquired V2-004-B asset (bytes
sha-verified first). **FRAME_SHA256 = `fc527bac6fa9a85f5e6be359e5466e7
b5dccc81bb41a2beec95a10ee9c9fbac3`** — matches BOTH the V2-007 recorded
still AND the fresh V2-007 still byte-for-byte (`match: true`,
`v7_still_match: true`). Pixel classification re-confirmed:
FULL_FRAME_WORLD_AND_IDENTITY, FAR_SIDE_COMPATIBLE, storm-gate world,
no fortress/metal/warm clouds, identity acceptable. The rejected take
remains REJECTED.

## 3. Reference qualification (P2) — exactly ONE upload

`reference_qualification_v2_008.json` + `upload_ledger.json`
(max_uploads=1, uploads=[1]):

| Item | Value |
| --- | --- |
| Local asset | `asset_e802da3a…` (frame, sha `fc527bac…`, lineage: V2-004-B job/output/video sha recorded in rights_metadata) |
| Upload | ONE maseQ POST (request `c346d11a…`), response = QUALIFIED_PENDING (designed state; skeleton hash `ae90da3e…`) |
| Reconciliation | bounded catalog readback (NO re-POST): unique strong match found; the one unresolved blocking row was cleared with **durable pre-dispatch evidence** — the V2-006 frozen catalog baselines (81+82 ids captured before this package existed) |
| **Provider media** | **`eac3615c-0842-4559-859f-eea55e2737d7`** |
| Attestation | `refbind_b67867a9ea33b7…` (strong_match, exact bytes) |
| Adopted asset | `adopt_existing_reference` into the durable store (runtime-ready) |

## 4. F2A plan revision (P3) — plan_revision=2, previous preserved

`CLOSE_BEFORE_THRESHOLD`: start_zone
`BEFORE_GATE:CLOSE_BEFORE_THRESHOLD` → arrival AT the threshold by
2.4 s (timing invariant PASS); forbidden: sword draw/guard/rock/metal
gate/full crossing. **Old F2A identity ≠ revised F2A identity**
(proven); B1–B10 ALL_PASS; D1–D10 ALL_PASS on the revised pair.

## 5. F2B (P4) — frozen plan + world-anchored reference swap

Frozen V2-005 F2B plan unchanged; reference swapped from the
identity-only `7b725f7b…` to the newly qualified far-side world frame
`eac3615c…` (`FULL_FRAME_WORLD_AND_IDENTITY (FAR_SIDE)`). **Old F2B
identity ≠ world-anchored F2B identity** (proven). Historical
identities unchanged.

## 6. Semantic identities + compiler (P5/P6)

| Candidate | Generation semantic identity | Wire |
| --- | --- | --- |
| F2A-V2-008 | `269537d4c4f60a26…` (rev2) | 477 ch / 72 w — close · gust · commit · opening · gate |
| F2B-V2-008 | `d3e0a021ec4ec4f5…` | 486 ch / 73 w — beyond · onward · far side · gate · behind |

A≠B; old≠new (both proven). Envelope fail-closed; forbidden-token scan
(word-boundary aware — "sword" no longer false-positives on
"swordsman_white_robes").

## 7. Admission (P7) — **EXA-0dfeea778cfd812b ADMITTED** (hypothesis
verbatim; budget 2; uploads note: 1 consumed by qualification before
any Generate).

## 8. Generate ledger (P8/P9)

| Shot | Provider job | Output identity | Asset sha256 |
| --- | --- | --- | --- |
| F2A | `job_0575910328473d7b760493d833e598314ca50c3b3694a055f136223f2a43af9e` | `1a3c792f-81ed-454a-949c-f64750eb9db8` | `ba9086b513ab…` |
| F2B | `job_145491dcfe98e3ea…` | `d6428eb8-21f0-4f2a-bddc-83e606fc7dde` | `c45b4918f9cc…` |

**2/2 consumed · 0 retries · dispatch_count=1 each · latch OPEN.**
F2B submitted only after F2A SHOT_PROVEN with clean attribution.
Execution note: two local-scope corrections before the first POST
(separate upload/generate scope dirs) — zero provider effect; the
generate ledger lives under `generate_scope/` and was synced to the
package root after the run.

## 9. F2A spatial QC (P10) — ALL PASS

A1 close-start visible ✓ · A2 gust already active ✓ · A3 immediate
commit ✓ · A4 one/two-step path ✓ · **A5 threshold reached ≈2.4 s ✓**
· A6 no full crossing ✓ · A7 no rock interaction ✓ · A8 no reversal ✓
· **A9 NO SWORD DRAW ✓ (the V2-006 defect is gone)** · A10
end-at-threshold readable ✓ · **A11 NO METAL GATE ✓** · A12
storm-gate world compatible ✓.

## 10. F2B spatial QC (P11) — ALL PASS

B1 opens crossing-or-beyond ✓ · **B2 gate BEHIND subject ✓ (in every
frame — the world-anchored reference did its job)** · B3 moves away ✓
· B4 one direction ✓ · B5 far side reached ✓ · **B6 far-side readable
from ~0.15 s ✓** · B7 no return ✓ · B8 no rock contact ✓ · B9 no
reversal ✓ · B10 end state clear ✓ · **B11 storm-gate world
PRESERVED ✓** · B12 no fortress ✓ · B13 no metal gate ✓ · B14 no warm
cloud world ✓ · B15 no incompatible architecture ✓ · **B16 no sword
draw ✓** · B17 no guard action ✓.

## 11. Pair QC (P12) — evaluated (both halves passed)

P1 threshold→just-beyond compatible ✓ · P2 cut implies crossing ✓ ·
P3 direction coherent ✓ · P4 WORLD MATCH across cut ✓ (same granite
storm-gate family both sides) · P5 gate geometry compatible ✓ (the
V2-007 doorway-staging risk did NOT materialize: F2A's pillars and
F2B's doorway read as the same stone-gate structure from different
angles; the staging variance is honest-noted) · P6 no loitering ✓ ·
P7 goal clear ✓ · P8 outcome clear ✓ · P9 F1/F3 continuity ✓ · P10
duration 5.6 s exact ✓.

## 12. Identity QC (P13)

IDENTITY UNCHANGED on both (canonical/F2A/F2B grid: face, hair,
robes). The world-anchored reference preserved identity AND world —
the V2-006 tradeoff is resolved.

## 13. Owner review surface (P14) — `OWNER_REVIEW/V2_008/`

| File | SHA256 (16) |
| --- | --- |
| `BASELINE_F2.mp4` | `e84ba56ccd0f556e` (= canonical) |
| `F2A_REVISED.mp4` | `ba9086b513ab…` |
| `F2B_WORLD_ANCHORED.mp4` | `c45b4918f9cc…` |
| `NEW_F2_PAIR.mp4` | `b9138fa7fc7765d1` (5.6 s) |
| `COMPARE_REEL.mp4` | `e980f9361aed0446` (BASELINE → F2A → F2B → 7-question card) |

All copies SHA-verified; sources untouched. Decision template:
SELECT_F2A_F2B_PAIR / REJECT_ALL / KEEP_CANONICAL / NEEDS_REPAIR /
DEFER; decision NULL; no half-selection; no promotion in this package.

## 14. Canonical (P15) — `canonical_no_change_v2_008.json`

Master ✓ · F2 take ✓ · EditManifest ✓ · tracked files clean ✓ ·
promotion ledger EMPTY · canonical mutation **0**.

## 15. Recovery (P16) — `recovery_matrix_v2_008.json`

**415 cases total**: 333 reused frozen (89+28+30+62+52+72; all still
executed live) + **82 V2-008 cases** executed against live guards
(`tests/test_v2_008_recovery_001.py`): wrong-timestamp/SHA-mismatch/
wrong-video extraction, upload ambiguity/nonunique/second-upload/
hidden-upload, unresolved-row blocking (the live incident), plan
revision preservation, sword/guard/metal-gate/late-arrival defects,
old-reference reuse (both kinds), multi-reference, fortress/warm-
cloud/metal worlds, gate-in-front, half-selection, pair-half failures
(both directions), timing/direction/world/geometry mismatches,
loitering/goal/outcome/F1-F3 breaks, retry/third-generate/provider-
switch/wrong-mapping, worker auto-select, canonical mutation,
promotion attempt. Ambiguity: OWNER_AMBIGUITY_GATE.

## 16. Final verification (P17)

- **1245 tests passed** (918 V1 + 140 V2-001 + 26 V2-002 + 55 V2-003 +
  26 V2-004 + 20 V2-005 + 11 V2-005R + 22 V2-006 + 10 V2-007 + 17
  V2-008), 0 failed.
- compileall clean · `git diff --check` clean · secret scan clean ·
  SoT manifest 30/30.

## 17. Unresolved unknowns

1. The Owner's decision on the QUALITY_REVIEW_READY pair (the package
   ends AT the decision gate).
2. Whether the Owner accepts the doorway-staging variance across the
   cut as film-acceptable (worker read: same world, materially
   compatible; the staging variance has existed across every take
   since V2-002).
3. If selected: the promotion-adapter package (V2-009) must qualify
   the real PromotionEnvironment (QCStore/EditorialStore adapter) —
   exactly one promotion transaction of slot 24 → F2A+F2B.

## 18. Final status

**OWNER_DECISION_GATE** — admission proven · Owner authorization
applied exactly (1 upload + pacing delta, scope respected) · 2/2
Generates clean · 0 retries · clean attribution · **both halves ALL
hard QC PASS → pair QUALITY_REVIEW_READY** · world anchored ·
identity preserved · canonical unchanged · no promotion.
PACKAGE_008_FINAL_HEAD_SHA is returned in the final worker report.
