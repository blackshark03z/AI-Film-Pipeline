# AI-FILM-QUALITY-V2-007 — F2 World-Anchor + Pacing Control Preflight — Evidence Record

**Status: PREFLIGHT_COMPLETE** — F2A proven unsalvageable; a
far-side WORLD reference candidate FOUND inside already-acquired
project media; strategy = qualify that existing media. Generation 0 ·
upload 0 · provider switch 0 · canonical mutation 0.

## 1. Custody (P1)

| Item | Value |
| --- | --- |
| Exact V2-006 final HEAD | `480ba6a81f0981cba59bf42ee642e8daa1fcce1c` (branch `quality-v2/007-world-anchor-preflight`) |
| V2-006 outputs | F2A: job `job_8768d6fc…`, output `329aa625…`, asset `adb62822…` · F2B: job `job_26e6cc44…`, output `1f2d1a27…`, asset `51ed91af…` |
| V2-004 outputs | A `cb89df69…` · B `b573cf13…` (output `279e5139…`, job `job_a61ed1ac…`) |
| Canonical | F1/F2/F3 `faces frame-left` (4.8/5.6/3.2 s); EditManifest `edit_c82343ee…`; master `976876a1…6595` (re-verified byte-identical) |
| Qualified reference media | `8f2f5277…` (FULL_FRAME_ENVIRONMENTAL near-side) + `7b725f7b…` (IDENTITY_ONLY) — no far-side world image exists |
| PACKAGE_007_FINAL_HEAD_SHA | returned in the final worker report |

## 2. F2A salvage scan (P2) — `f2a_salvage_scan_v2_007.json`

All **27** contiguous 2.8 s windows (t ∈ [0, 5.2], step 0.2) evaluated
against the measured event timeline (0.4 s full strip,
`qc_evidence/f2a_full_strip.png`): sword present from **1.4 s**
(continuous), guard swing 3.4–4.2 s, metal gate visible from **5.0 s**,
threshold arrival ≈ **6.2 s**.

Interval proof: a viable window must CONTAIN the arrival ⇒ t ≥ 3.4 ⇒
the window also contains the continuous sword AND the metal gate ⇒
world/action defects. Every window with t < 3.4 has no threshold
arrival. **F2A_SALVAGEABLE = false** — proven, not judged from the
first 2.8 s only. No new rendering.

## 3. World-reference search (P3/P5) — `world_reference_search_v2_007.json`

| Candidate | World | Geography | F2B-compatible |
| --- | --- | --- | --- |
| canonical F2C | storm-gate | NEAR_SIDE (V2-005R-proven conflict) | ✗ |
| canonical F1 | storm-gate | NEAR_SIDE approach | ✗ |
| canonical F3 | storm-gate golden hour | NEAR_SIDE wall-lean | ✗ |
| V2-004-A | storm-gate two stones | THRESHOLD/near | ✗ |
| V2-006-A | DRIFTED metal gate | near | ✗ |
| V2-006-B | DRIFTED fortress/cloud | ambiguous | ✗ |
| **V2-004-B @ 6.6 s** | **storm-gate granite doorway, dark storm clouds** | **FAR_SIDE — subject emerged through the doorway, gate clearly BEHIND him** | **YES** |

## 4. Special check V2-004-B (P4)

Frame-by-frame inspection of the actual acquired asset (bytes
sha-verified, `b573cf13…`): the late frames (5.8–7.4 s) show the
rectangular granite doorway with the subject EMERGED to the far side.
Selected still: **t = 6.6 s**
(`qc_evidence/wref_V2004B_t6.6.png`, sha `fc527bac…`;
alternatives 5.8/6.2/7.0/7.4 recorded). **The rejected take is NOT
promoted** — it supplies one reference FRAME only, through explicit
reference-qualification provenance (the still's sha is recorded; V2-008
performs the qualification).

## 5. Provider-media reuse check (P5)

Priority applied: 1 (existing far-side provider IMAGE media) does not
exist → 2/3: the frame lives inside an acquired PROJECT asset
(zero-cost extraction, exact provenance) but as a still it needs ONE
reference-qualification upload. `upload_required = yes` (executed in
V2-008 under explicit Owner authorization, NOT in V2-007).

## 6. F2A pacing diagnosis (P6) — PROPOSAL ONLY

Failure classes: TOO_MUCH_TRAVEL_DISTANCE · PROVIDER_ACTION_DELAY ·
UNSCHEDULED_SWORD_ACTION · WORLD_STRUCTURE_INVENTION. Minimum Director
delta: `F2A_START = CLOSE_BEFORE_THRESHOLD` (gust already active →
immediate commitment → one/two steps → threshold; no sword, weapon
passive, no rock interaction; near-side F1 last-frame reference stays
compatible). The frozen V2-005 plan is NOT mutated (verified on disk);
the delta becomes a NEW plan revision in V2-008 only if the Owner
authorizes it.

## 7. World control strategy (P7)

**C. QUALIFY_EXISTING_PROJECT_MEDIA_AS_WORLD_REFERENCE** — A
impossible (no far-side provider image exists), B insufficient
(identity-only proven not to anchor world in V2-006), D unnecessary (a
compatible frame exists in project media), E false. No unqualified
multi-reference path used.

## 8. V2-008 handoff (P8)

`docs/quality-v2/V2_008_F2_WORLD_ANCHORED_LIVE_HANDOFF.md` — READY
contingent on the Owner authorizing (1) the ONE reference-qualification
upload and (2) the F2A pacing delta. Budget ≤ 2 new Generates (1 F2A
revised render — salvage failed — + 1 F2B world-anchored render); no
alternate takes; retries 0; canonical promotion 0.

## 9. Recovery / tests (P9)

New package tests (`tests/test_v2_007_preflight_001.py`, 10 tests)
cover every required adversarial scenario: salvage proven by interval
arithmetic (not first-window judgment), wrong-world references
rejected, near-side-for-far-side rejected, metal-gate/fortress/sword
defect classes recorded, rejected-take-frame-without-promotion
provenance, pacing proposal without frozen-plan mutation, hidden
upload/generation/provider-switch/canonical invariants, ambiguity rule.
Full matrix: 333 (V2-006) + new cases absorbed into the package tests;
**1228 tests passed** total, 0 failed. compileall clean ·
`git diff --check` clean · secret scan clean · SoT manifest 30/30.

## 10. Unresolved unknowns

1. Owner authorization for the one reference-qualification upload + the
   F2A pacing delta (both are V2-008 preconditions).
2. Whether the qualified route renders F2A's close-start commitment
   inside 2.8 s (the pacing delta's exact question).
3. Whether the V2-004-B far-side frame anchors F2B's world without
   importing its slightly-different doorway staging (the V2-006 pair
   cut would then need the same doorway in F2A's background — noted as
   a V2-008 QC attention point).

## 11. Final status

**PREFLIGHT_COMPLETE** · F2A_SALVAGEABLE = false (proven) ·
F2A_FAILURE_CLASS = TOO_MUCH_TRAVEL_DISTANCE + PROVIDER_ACTION_DELAY +
UNSCHEDULED_SWORD_ACTION + WORLD_STRUCTURE_INVENTION ·
WORLD_REFERENCE_STRATEGY = C · WORLD_REFERENCE_SOURCE_SHA =
`fc527bac…` (frame @6.6 s from asset `b573cf13…`) ·
UPLOAD_REQUIRED = 1 (V2-008) · V2_008_READY = true (contingent) ·
NEXT = Owner authorization → V2-008.
PACKAGE_007_FINAL_HEAD_SHA is returned in the final worker report.
