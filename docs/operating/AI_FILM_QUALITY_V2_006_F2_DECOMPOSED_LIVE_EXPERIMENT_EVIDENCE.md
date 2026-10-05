# AI-FILM-QUALITY-V2-006 — F2 Decomposed Live Experiment — Evidence Record

**Status: OWNER_DECISION_GATE** — the experiment ran clean (2/2
generates, split-reference PROVEN on the qualified route, zero
retries/ambiguity) and the honest spatial result is IN: BOTH halves
fail their hard QC, so the ATOMIC PAIR is REFUSED and cannot be
QUALITY_REVIEW_READY. The Owner visual read is authoritative; the full
review surface is ready.

## 1. Custody chain

| Item | Value |
| --- | --- |
| Exact start SHA (V2-005R final HEAD) | `6af0e7490e985d859b7148fc1b25ffa60c4d5b72` (branch `quality-v2/006-f2-decomposed-live`) |
| Owner authorization | `AUTHORIZE_SPLIT_REFERENCE = YES` — Owner explicit approval in Tech Lead chat after V2-005R; scope: ONLY the reference-strategy amendment |
| Frozen V2-005 plan identities | F2A/F2B DI/BS/CC ids rebound byte-identical (`custody_v2_006.json`) |
| Canonical F2 predecessor | `take_91e4997b…` / `e84ba56c…` (slot 24) — unchanged |
| Canonical master | `976876a1…6595` — re-verified byte-identical (P11) |
| QD-001 | ACTIVE |
| PACKAGE_006_FINAL_HEAD_SHA | returned in the final worker report |

## 2. Split-reference amendment (P1) — applied, 0 uploads

| Shot | Reference | Type | Sha | Attestation |
| --- | --- | --- | --- | --- |
| F2A | `8f2f5277-aae8-44b5-a5b7-c197d1d7c115` | FULL_FRAME_ENVIRONMENTAL (near-side) | `fecf669e…8313` | `refbind_f4277ac1…` |
| F2B | `7b725f7b-4da5-4455-a6f2-135c4ba22397` | **IDENTITY_ONLY** | `ed75a8b2…a4e8` | `refbind_57abbee5…` |

Both media already project-bound (0 uploads; identity bytes
sha-verified before any mutation). F2B operates in its OWN scene dir
(`SCENE_F_FAR_SIDE`) so the near-side attestation can never co-locate
with the identity-only binding (leak guard).

## 3. Pair freeze (P2-P5) — `experiment_freeze_v2_006.json`

Atomic pair (SELECT_F2A_F2B_PAIR / REJECT_ALL / KEEP_CANONICAL /
NEEDS_REPAIR / DEFER; half-selections removed). Semantic identities
frozen BEFORE any mutation (ShotSpec + ActionIntent + DirectorIntent +
BlockingSpec + PerformanceSpec + CameraCoveragePlan + reference
binding): **F2A `a6303e002e82a1db…` ≠ F2B `0df7e8425b8e3007…`**
(changing F2B's reference changed its identity, as required).

## 4. Compiler conformance (P6)

F2A wire 456 ch / 69 words — gust · **sets himself** · near side ·
opening · gate. F2B wire 482 ch / 72 words — beyond · onward · far
side · gate · **behind** ("the gate behind him" carried in the
dramatic purpose). Envelope fail-closed; no silent shortening; each
shot compiled with ONLY its own reference (no geography import).

## 5. Admission (P7) — **EXA-4bf23c71f5fd5fef ADMITTED** (hypothesis
verbatim; budget 2 = 1+1; uploads 0; promotion 0).

## 6. Generate ledger (P8)

| Shot | Provider job | Output identity | Asset sha256 |
| --- | --- | --- | --- |
| F2A | `job_8768d6fcb9a33245dfb3387414e293d19f840975bcb93cca357c6c1b3478ebf3` | `329aa625-5711-4deb-b44d-2ed2e97387bb` | `adb62822b2003f5e…` |
| F2B | `job_26e6cc44c920debc8c74e6ec8278a79300ec71021d893916983cd5d131dcda3c` | `1f2d1a27-b409-44f6-88f4-e5bc8ed4db0a` | `51ed91afc4d8b2f9…` |

**2/2 consumed · 0 retries · 0 uploads · 0 ambiguous events · latch
OPEN.** Sequential (F2B submitted only after F2A SHOT_PROVEN with
clean attribution). The split-reference strategy RAN on the qualified
route: F2B was conditioned on the identity-only media with zero
upload. One execution incident, caught by the package's own guard:
the driver's pre-submit leak check halted F2B the first time (the
near-side attestation co-located in the shared scene dir); the scope
was re-entered WITHOUT any second submit of F2A (durable
short-circuit), F2B got a separate scene dir, and F2B's single submit
then completed. Ledger total: exactly 2.

## 7. Technical QC (P9)

Both: full decode PASS, 8.0 s, 1280x720. 0.4 s strips + identity 3-way
grid (canonical/F2A/F2B) + the PAIR join `NEW_F2_PAIR.mp4` (F2A 2.8 s
+ F2B 2.8 s = 5.6 s, sha `8064d582…`) on disk.

## 8. PRIMARY RESULT — F2A spatial QC (P10, worker advisory)

| Check | Verdict |
| --- | --- |
| A1 START_BEFORE_GATE_VISIBLE | PASS |
| A2 GUST_READABLE | PASS |
| A3 FORWARD_COMMIT_READABLE | PASS |
| A4 DIRECT_PATH_TO_THRESHOLD | PASS |
| A5 REACHES_THRESHOLD | **FAIL** — measured arrival ≈6.5 s, far outside the frozen 2.8 s window (anchor 2.4 s) |
| A6 DOES_NOT_CROSS_FULLY | PASS |
| A7 NO_ROCK_INTERACTION | PASS (NOTE: unplanned contact with a METAL gate structure at ~7 s) |
| A8 NO_REVERSAL | PASS (NOTE: opens back-to-camera vs the planned orientation) |
| A9 THRESHOLD_VISIBLE | PASS |
| A10 END_STATE_AT_THRESHOLD_READABLE | **FAIL** — inside the 2.8 s window he is mid-turn, sword drawn |
| WORLD_CONTINUITY | **FAIL** — a METAL ornate gate materializes between the rock pillars |
| ADDED_ACTION | **FAIL** — unplanned sword draw + guard stance |

**F2A hard fails: A5, A10 (+ world/added-action defects).**

## 9. F2B spatial QC (P11, worker advisory)

| Check | Verdict |
| --- | --- |
| B1 START_ALREADY_CROSSING_OR_BEYOND | **FAIL** — hero-walk well in front, no just-crossed state |
| B2 GATE_BEHIND_SUBJECT | PASS (composition; the structure's world identity fails below) |
| B3 MOVEMENT_AWAY_FROM_GATE | PASS |
| B4 ONE_DIRECTION_ONLY | PASS |
| B5 FAR_SIDE_REACHED | **FAIL** — unverifiable: the world is a castle fortress above clouds, not the SEQ7 storm-gate grassland |
| B6 FAR_SIDE_READABLE_BY_2_4S | **FAIL** |
| B7 NO_BEFORE_GATE_RETURN | PASS |
| B8 NO_ROCK_INTERACTION | PASS |
| B9 NO_REVERSAL | PASS |
| B10 END_STATE_DISTINCT_AND_CLEAR | **FAIL** — distinct but geographically wrong |
| WORLD_CONTINUITY | **FAIL — MATERIAL world drift: castle fortress + lightning + warm cloud sea (the identity-only reference's aesthetic leaked; with no environmental anchor the model invented geography)** |
| ADDED_ACTION | **FAIL** — unscheduled drawn sword |

**F2B hard fails: B1, B5, B6, B10 (+ material world drift).** Identity
itself was PRESERVED (the identity-only reference worked for identity);
the world is what broke — the exact §13 risk, now proven with data.

## 10. Pair verdict (P12/P15)

Both halves fail their hard sets ⇒ per the frozen rule **the ATOMIC
PAIR is REFUSED** — neither half reaches QUALITY_REVIEW_READY and the
pair cannot either (`candidates_governance_v2_006.json`,
`pair_state: REFUSED`). P1–P10 were never evaluated (both hard sets
required). No Owner decision minted; no promotion; decision = future
authority.

## 11. Identity/world QC (P13)

IDENTITY: UNCHANGED on both (face/hair/robes consistent vs canonical —
the identity-only reference DID its job for identity). WORLD: F2A
metal-gate drift; F2B fortress/cloud/lightning drift — both materially
incompatible with the storm-gate world. World NOT auto-accepted.

## 12. Owner review surface (P14) — `OWNER_REVIEW/V2_006/`

| File | SHA256 (16) |
| --- | --- |
| `BASELINE_F2.mp4` | `e84ba56ccd0f556e` (= canonical) |
| `F2A.mp4` | `adb62822b2003f5e` |
| `F2B.mp4` | `51ed91afc4d8b2f9` |
| `NEW_F2_PAIR.mp4` | `8064d5822a5c6868` |
| `COMPARE_REEL.mp4` | `ff047fc7a710de57` (BASELINE → F2A → F2B → 7-question card) |

All copies SHA-verified against sources (sources untouched). Decision
template: atomic pair, decision NULL. NOTE: a cid-dispatch bug
(`endswith("A")` vs `startswith`) initially mapped F2A's review copy
to F2B's file; the package's own custody==file equality check caught
it and the surface was regenerated from provenance-bound
`uri_or_path` — the bug class is now a permanent recovery case
(V2-006-RC-023).

## 13. Canonical no-change (P11) — `canonical_no_change_v2_006.json`

Master ✓ · F2 take ✓ · EditManifest ✓ · tracked files clean ✓ ·
promotion ledger EMPTY · canonical mutation **0**.

## 14. Recovery (P16) — `recovery_matrix_v2_006.json`

**333 cases total**: 261 reused frozen cases (89+28+30+62+52; all
still executed live) + **72 V2-006 cases** executed against live
guards (`tests/test_v2_006_recovery_001.py`): old-reference leak into
F2B, SHA mismatch, full-frame leak, hidden upload, F2A crossing/
stop-at-rock/late-arrival/added-action/world-drift, F2B near-side
start/gate-in-front/reversal/toward-gate/late far-side/invented-world,
pair timing/direction/destination/one-half-selected/half-fails
(both directions), wrong asset mapping (the dispatch-bug class),
ambiguity, retry, third generate, provider switch, worker claims,
canonical mutation, promotion attempt. Ambiguity: OWNER_AMBIGUITY_GATE.

## 15. Final verification (P17)

- **1218 tests passed** (918 V1 + 140 V2-001 + 26 V2-002 + 55 V2-003 +
  26 V2-004 + 20 V2-005 + 11 V2-005R + 22 V2-006), 0 failed.
- compileall clean · `git diff --check` clean · secret scan clean ·
  SoT manifest 30/30.

## 16. Honest reading for the Owner

The decomposed experiment CLEANLY answered its two questions:

1. **The split-reference strategy works mechanically** — an
   identity-only reference ran on the qualified route with 0 uploads,
   preserved identity perfectly, and did NOT leak near-side geography.
2. **But identity-only anchoring is insufficient for world
   continuity**: with no environmental anchor, F2B invented a fantasy
   fortress world (the reference's warm cloud aesthetic leaked), and
   F2A drifted too (metal gate, sword action, late arrival). The
   single-clip traversal problem from V2-002/004 is replaced by a
   world-anchor problem.

Candidate levers for a FUTURE package (Owner's call; nothing proposed
or authorized here): (a) a dedicated FAR-SIDE WORLD reference
qualification (V2-005R option 3) — a real far-side frame carrying
stone-gate geography without near-side contradiction; (b) tighter
timing phrasing. The frozen V2-005 two-shot EDITORIAL design itself
remains sound; the failure is render-world anchoring.

## 17. Unresolved unknowns

1. The Owner's decision on the refused pair.
2. Whether a qualified far-side world reference can anchor F2B without
   re-importing near-side geography.
3. F2A's timing failure (6.5 s arrival vs the 2.8 s window) — whether
   prompt-expressible pacing can compress the approach.

## 18. Final status

**OWNER_DECISION_GATE** — admission proven · Owner amendment applied
exactly (scope respected) · ≤2 Generates (2 consumed) · 0 retries ·
clean attribution · split-reference PROVEN on route · honest A/B
verdicts recorded · pair REFUSED per the frozen rule · atomic surface
ready · canonical unchanged · no promotion.
PACKAGE_006_FINAL_HEAD_SHA is returned in the final worker report.
