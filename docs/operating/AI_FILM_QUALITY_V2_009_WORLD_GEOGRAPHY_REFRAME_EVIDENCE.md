# AI-FILM-QUALITY-V2-009 — F2 World-Geography Reframe — Evidence Record

**Status: COMPLETED_CANDIDATE** — the Owner NEEDS_REPAIR reframe is
frozen as a provider-neutral geography authority (G1–G10 + W1–W6 +
L1–L8 ALL PASS); the V2-005/V2-008 plans are preserved; the revised
F2A/F2B plans pass ALL gates; NO generation, NO upload, NO provider
switch, NO canonical mutation.

## 1. Custody chain

| Item | Value |
| --- | --- |
| Exact start SHA (V2-008 final HEAD) | `8b6c766126eabcf8c3828937b9907fc074be304e` (branch `quality-v2/009-world-geography-reframe`) |
| V2-008 Owner decision | **NEEDS_REPAIR** — reasons: WORLD_GEOGRAPHY_DOES_NOT_JUSTIFY_GATE_TRAVERSAL · ACTION_GOAL_NOT_NARRATIVELY_LEGIBLE · CHARACTER_READS_AS_SHELTERING_OR_LOITERING · GUST_NOT_LEGIBLE_AS_CAUSAL_OBSTACLE |
| Canonical F2 | `take_91e4997b…` / `e84ba56c…` — unchanged |
| Canonical master | `976876a1…6595` — re-verified byte-identical |
| QD-001 | ACTIVE |
| PACKAGE_009_FINAL_HEAD_SHA | returned in the final worker report |

## 2. The reframe (P0) — `v2_008_owner_decision.json`

Authoritative narrative truth frozen verbatim:
- TRIGGER: a hard gust hits
- GOAL: continue onward THROUGH the gate / passage
- ACTION: drive forward through the obstacle despite the gust
- OUTCOME: emerge beyond the worst gust and continue
- NOT-GOAL: hide / shelter / inspect stone / circle obstacle / linger / use rock as destination
- **Reframe**: the source does NOT require a freestanding decorative doorway in an open field; treat "gate" as a PASS-THROUGH OBSTACLE / CHOKE POINT whose visual design must make the existing causal action believable
- **Key invariant**: THE VIEWER MUST NOT REASONABLY THINK "he could simply walk around it"

## 3. TraversalGeometrySpec v1 (P1/P2) — G1–G10 ALL PASS

| Field | Value |
| --- | --- |
| Entry | ROAD_BEFORE_PASS: travel path visibly funnels toward the stone boundary |
| Threshold | NARROW_PASS_OPENING: the only walkable gap |
| Exit | BEYOND_GATE:ROAD_BEYOND_PASS: open travel path continuing onward |
| Barrier extent | CONTINUOUS_ROCK_RIDGE_BOTH_SIDES — extends beyond the visible opening on both lateral sides |
| Bypass visibility | NONE_IN_FRAME |
| Shelter affordance | NONE |
| World connection | road funnels INTO the pass; road beyond continues from exit — barrier stands ACROSS the road |
| Wind channel | gust channels THROUGH the pass against travel direction — the choke point IS the wind funnel |
| Forbidden geography | freestanding decorative gate, open-field bypass, shelter niche, castle/fortress, metal gate, warm cloud sea, lightning proxy, forbidden destination |

Director interpretation: narrow stone pass / ruined stone boundary / rock choke point integrated into the terrain — DESIGN, not a new source fact.

## 4. CausalEnvironmentSpec v1 (P2) — W1–W6 ALL PASS

Gust direction: from beyond the pass INTO his face (against travel). At least 2 environment cues agree: cloth pressure (robes press flat windward, stream leeward) + body lean (center of gravity drops INTO the gust; every step pushes against the wind). Effort: forward progress requires visible muscular effort — the pass IS the wind funnel. Forbidden: ambient wind with unaffected body, random storm VFX, lightning proxy, voluntary crouching, cover-seeking, loitering, lingering, ambient-only wind.

## 5. Legibility contract (P3) — L1–L8 ALL PASS

L1 obstacle necessary to traverse ✓ · L2 bypass not visible ✓ · L3 forward goal dominates ✓ · L4 rock not destination ✓ · L5 no sheltering body language ✓ · L6 no loitering ✓ · L7 no meaningless side movement ✓ · L8 end state proves progress ✓

## 6. Revised blocking (P4) — B1–B10 ALL PASS ×2

**F2A — ENTER CHOKE POINT** (plan_revision=3, V2-005 rev1 + V2-008 rev2 preserved): ROAD_BEFORE_PASS:CLOSE → NARROW_PASS_OPENING:ENTERED (1-2 steps, crossing completes across the CUT). Absolutely forbidden: touching wall for support, leaning behind rock, side-step toward cover, circling, backtracking, stopping beside pillar, draw sword, look-around behavior.

**F2B — EXIT CHOKE POINT** (plan_revision=2, V2-005 F2B preserved): NARROW_PASS_OPENING:CROSSING_OR_JUST_BEYOND → BEYOND_GATE:ROAD_BEYOND_PASS FAR_SIDE_CLEAR. Absolutely forbidden: turn back, return toward opening, stand beside gate, inspect obstacle, loiter, shelter.

## 7. Decomposition gates (P7) — D1–D10 ALL PASS

Story meaning preserved (anchors matched against the revised narrative truth) · one dominant action per shot · threshold handoff compatible · far side observable · rock never destination · no reversal required · ellipsis legible · F1→F2A→F2B→F3 chain bound · duration bounded · canonical unchanged.

## 8. Seedance access audit (P8/P9) — READ ONLY

The explore agent audited all Seedance access paths:

| Path | Implementation | Live proof | Verdict |
| --- | --- | --- | --- |
| Dola cookie-HTTP (`seedance_dola`) | AI-Film: 457-line adapter + 8/8 offline tests + restart-never-resubmit | **ZERO successful receipts** — 3 ambiguous no-receipt submits (2 Story Auto `dola-main`, 1 AI-Film D-G1); quarantined | NOT QUALIFIED for live; needs Owner UI inspection of orphaned conversations before any new Dola submit |
| Dola browser-UI | Story Auto only (not AI-Film) | 1 success (canary 4, 2026-09-23, task 38417972940811793) | Different transport family; would need own authorization |
| **Elyum MCP** (`seedance_elyum`) | Story Auto: 752-line service + 426-line client; AI-Film: **not implemented** | **MULTIPLE live proofs**: R1 (gen g_e2fa8c99…), X2 KEEP (g_d59e88f0…, 20 credits), X3 preview (g_a18de93d…, sha 8c9163…), UAT (g_f62ed089…, preview sha a8c72a65…) | **SHORTEST ROUTE to AI-Film-qualified Seedance**: durable jobId/genId custody + idempotent clientRef + proven download |
| BytePlus ModelArk | Story Auto only | No live proof in audited evidence | Provisional |

**Route selection**: Elyum is the only Seedance path with repeated durable job/output correlation. A bounded AI-Film canary through it (using the existing `D:\API KEY\elyum_api_key.txt` Bearer key) is the shortest route to an "AI-Film-qualified" Seedance claim. The Dola cookie-HTTP transport has never produced a successful receipt anywhere.

## 9. Recovery

Recovery matrix count carried from 333 (V2-006) + new cases absorbed into the module tests. Full suite **1245 passed** (918 V1 + 140 V2-001 + 26 V2-002 + 55 V2-003 + 26 V2-004 + 20 V2-005 + 11 V2-005R + 22 V2-006 + 10 V2-007 + 17 V2-008), 0 failed.

## 10. Verification

compileall clean · `git diff --check` clean · secret scan clean · SoT manifest 30/30 · 2 new schemas (`traversal_geometry_spec`, `causal_environment_spec`).

## 11. Unresolved unknowns

1. Whether the qualified route can render a terrain-integrated choke point (the Director's narrow-stone-pass interpretation) — that is exactly what V2-010 would test.
2. The Elyum adapter for AI-Film has not been built (Story Auto implementation exists and is live-proven).
3. Whether the Dola orphaned conversations can be resolved by Owner UI inspection.

## 12. Final status

**COMPLETED_CANDIDATE** — WORLD_GEOGRAPHY_REFRAME = FROZEN ·
TRAVERSAL_G1_G10 = ALL_PASS · WIND_W1_W6 = ALL_PASS ·
LEGIBILITY_L1_L8 = ALL_PASS · DECOMPOSITION_D1_D10 = ALL_PASS ·
DIRECTOR_B1_B10 = ALL_PASS ×2 · VIDEO_GENERATION = 0 · UPLOAD = 0 ·
CANONICAL_MUTATION = 0 · NEXT = V2-010 (choke-point render test with
the Elyum route selection) · PACKAGE_009_FINAL_HEAD_SHA returned in
the final worker report.
