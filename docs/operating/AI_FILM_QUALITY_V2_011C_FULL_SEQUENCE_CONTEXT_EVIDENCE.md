# AI FILM QUALITY V2-011C — FULL SEQUENCE CONTEXT EVIDENCE

Slice: `AI-FILM-QUALITY-V2-011C` — F1 → Locked F2 → F3 Context Recovery + Sequence Proof
Branch: `quality-v2/011b-editorial-assembly` · Head at slice start: `afc15b84c26bcf22175410081ed7a05b3b17ad6b`
Provider mutations: **0** (read-only/editorial slice; no generation attempted)

---

## Final state

```
ENGINEERING_STATUS    = COMPLETE (COMPLETED_CANDIDATE)
FILM_CONTEXT_STATUS   = FAILED — FULL_SEQUENCE_CONTEXT NOT proven
SEQ_CONTEXT_LOCK      = DENIED
F2_SEQUENCE           = FILM_USABLE (unchanged — creative/production/editorial locks all intact)
Canonical lineage     = UNCHANGED (nothing promoted, nothing demoted)
```

Both context junctions **CUT_FAIL** on `GEOGRAPHY + LIGHTING`. Per package: no regeneration, no
proof rendered, repair plan produced for Tech Lead decision.

---

## Phase 0 — custody closure

| Item | Value | Verification |
| --- | --- | --- |
| 011B_FINAL_HEAD_SHA | `afc15b84c26bcf22175410081ed7a05b3b17ad6b` | `git rev-parse HEAD` (resolved, not inferred) |
| 011B_CANDIDATE_SEAL_SHA | `e418c6536acb81a7d0515cec496d1f5921a17a64fee4f1d790ef66bc933e05bc` | sha256 of `V2_011B_CANDIDATE_SEAL.json` |
| F2_EDITORIAL_PROOF_SHA | `ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de` | recomputed from disk, matches 011B lock |
| F2A asset SHA | `50a133c891aaa0060bc1f7d9d6c48c77a3fab1e802bc5f7a4fc43e112404d99b` | recomputed from `011r/assets/f2a_r.mp4` |
| F2A selected | frames 41 → 108 | `V2_011B_EDITORIAL_LOCK.json` |
| F2B asset SHA | `8679709b00860a2e3af45354b2166eae2b6d6b365731a278f21809a42babbbff` | recomputed from `011r/assets/f2b_r.mp4` |
| F2B selected | frames 0 → 67 | `V2_011B_EDITORIAL_LOCK.json` |
| Locked F2 | HARD_CUT, 134 frames @ 24fps, 5.583333s | probe + lock file |

F2 treated as `F2_SEQUENCE_LOCKED_v1`: used verbatim as the middle unit. Proof SHA re-verified
**after** all assembly work — unchanged. Watermark preserved (no removal/concealment).

## Phase 1 — F1/F3 authority (lineage, not filename)

Both assets were traced **exclusively** through lineage: editorial plan/ranges of
`master_package_010` → asset ids → generation results → local files → recomputed SHA.

### F1 = SEQ7_F1 (canonical master slot 23)

- ShotSpec/intent: `fixtures/sequence007/SEQ7_F1.json` (establishing WS, locked, faces frame-left;
  "Obstacle: the storm front meets him at the narrow rock gate"); prompt sha `34e59504…`.
- GenerationAttempt `attempt_7d962ead…` · ProviderJob `job_0e6e6851…` (flow_veo, veo_3_1_r2v_lite,
  720p/24, 8s) · provider asset `eba1fb3b-…`.
- Local asset: `shot_SEQ7_F1/videos/1978828aa83ed40e78523c43.mp4` · SHA
  `f50f07e8…` (recomputed, matches registry `asset_9805ce8e…`).
- Technical QC: `SHOT_PROVEN`, full-decode EOF PASS, `exact_lineage + technical_pass`.
- Creative status: canonical slot conformed in master packages **007/008/009/010**; Owner 019
  retained canonical lineage verbatim (`ACCEPT_KNOWN_QUALITY_DEBT`) with **no debt item on F1**
  (only F2/G3 named NEEDS_REDESIGN). Semantic per-shot model QC never qualified (006/012/013) —
  recorded, not averaged away.
- Editorial range (frozen ×4 packages): source 0→4.8s ⇒ nearest-frame **0..114** (115 frames,
  4.791667s).
- Identity: continuity reference `7b725f7b-…` — the **same identity mechanism** as the F2 pair.

### F3 = SEQ7_F3 (canonical master slot 25)

- ShotSpec: `fixtures/sequence007/SEQ7_F3.json` (performance MCU, locked, faces frame-left;
  "against the rock wall he sets his jaw; the cost, held"); prompt sha `47f5f6d0…`.
- GenerationAttempt `attempt_c6f54817…` · ProviderJob `job_55327b8f…` (flow_veo, veo_3_1_r2v_lite)
  · provider asset `ec2d2965-…`.
- Local asset: `shot_SEQ7_F3/videos/83df94b5d166dedce511ab1c.mp4` · SHA `24f05128…` (recomputed,
  matches `asset_9a7f2a18…`).
- Technical QC: `SHOT_PROVEN`, decode PASS. Creative status: as F1 (slot 25 conformed; no debt).
- Editorial range: source 0→3.2s ⇒ nearest-frame **0..76** (77 frames, 3.208333s).
- Identity: same reference `7b725f7b-…`.

The V2-005 decomposition plan binds the context explicitly:
`F2A.continuity_bindings.previous_shot_id = SEQ7_F1`, `F2B.continuity_bindings.next_shot_id =
SEQ7_F3`, authority "fixtures/sequence007 F1/F2/F3 screen_direction authority".

**Result: Case A** — exact accepted canonical assets exist and were deterministically identified.

## Phases 2–4 — continuity + cut QC

Frame evidence: `owner_review_011c/F1_F2_JUNCTION.png`, `owner_review_011c/F2_F3_JUNCTION.png`,
full-res pairs `frames/PAIR_*.png`. Trim windows (±12 frames, F1-out / F3-in) were fully evaluated
and are **world-invariant** — the failure class cannot be landed around, so the base boundaries were
kept (frozen editorial ranges honored, minimal deviation).

### F1 → F2 (base: F1 frame 114 → locked F2 frame 0) — **CUT_FAIL**

| Dimension | Verdict |
| --- | --- |
| Character identity / wardrobe / props | MATCH / MATCH / N-A (no props, no visible sword) |
| Screen direction · travel · eyeline · body · motion phase · energy | **MATCH** (all frame-left, mid-stride lean) |
| Causal action / narrative state | MATCH narratively (arrive → enter) |
| Character scale | minor step, acceptable (cut-in) |
| **Location/world** | **FAIL** — F1 = freestanding twin standing stones + wooden gate cross in open grassland (bypass and horizon visible); locked F2 = continuous dark rock-ridge choke point — the exact `FREESTANDING_DECORATIVE_GATE` / `OPEN_FIELD_BYPASS` geography V2-009 forbade, now adjacent to its replacement |
| **Lighting/palette** | **FAIL** — warm golden key vs cold blue-grey flat storm light |

### F2 → F3 (base: locked F2 frame 133 → F3 frame 0) — **CUT_FAIL**

| Dimension | Verdict |
| --- | --- |
| Identity / wardrobe / screen direction / eyeline | MATCH (topknot + headband; frame-left held) |
| Motion energy | acceptable: motion → settle ("jaw sets" is the fixture intent) |
| Shot-size rhythm | PASS (WS → MCU standard cut-in) |
| Causal action / narrative state | MATCH (crossed → cost held) |
| **Location/world** | **FAIL** — dark jagged natural rock face vs light tan **built** stone wall at the same landmark |
| **Lighting/palette** | **FAIL** — cold blue-grey storm vs warm golden sunlight (measured luma 91.75 vs **139.15**, +47) |

Critical failures were **not** averaged away: every editorial-grammar dimension passes; the failure
is the *world* the shots live in.

## Phase 5 — assembly

`outputs/F1_F2_F3_SEQUENCE_PROOF.mp4` was **NOT created**: the PHASE-5 gate (both junctions pass)
is not met, and a file named SEQUENCE_PROOF would falsely imply PROVEN context.

Rendered instead, clearly labeled `REFERENCE_ONLY_NOT_A_PROOF`:

```
outputs/F1_F2_F3_CONTEXT_FAIL_REFERENCE_CUT.mp4
sha256 9c7c44ce04ca390ee95ebaba0ee4ec26b0d7f7e598ace7e388926e675388a074
326 frames = 115 (F1 0..114) + 134 (locked F2 verbatim) + 77 (F3 0..76) @ 24fps = 13.583333s
h264 yuv420p + AAC 192k · concat FILTER (011B lesson — demuxer duplicates a junction frame)
junctions at output frames 115 and 249
```

## Phase 6 — sequence QC + technical QC

- Technical QC (reference cut): decode PASS (rc 0), 326 frames, continuous timestamps
  (**0** discontinuities), no black frames, no frozen frames, 24fps, codecs/container recorded,
  SHA above.
- Audio (source audio preserved, no final mix): ambience level steps at the cuts —
  J1 −16.3 → −23.5 dB (**7.2 dB step**), J2 −17.6 → −29.4 dB (**11.8 dB step**); wind character
  shifts. Recorded as **editorial/audio repair notes** (finishing-slice level matching), not video
  regeneration.
- Watermark: preserved verbatim; the mark itself changes across cuts (Veo vs Dola AI) — later
  provider-rights/finishing issue, intentionally untouched.
- Sequence-as-film: narrative arc (arrive → force through → hold the cost), screen direction,
  motion flow, shot-size rhythm, camera grammar, character/performance continuity, edit rhythm all
  **pass**; spatial geography, visual palette, weather continuity, context-causal readability
  **fail**.
- **Does F2 function naturally as the middle beat?** Not yet in canonical context: locked F2 is
  internally FILM_USABLE and is the strongest beat, but the film enters a cold ridge world for
  5.58s and exits back to the warm world — it reads as a different place/time, not a style choice.
  The context fails around F2; F2 does not fail.

## Production decision

```
F1_F2_CUT = FAIL    F2_F3_CUT = FAIL
FULL_SEQUENCE_CONTEXT = FAILED
SEQ_CONTEXT_LOCK = DENIED
```

## Repair plan (no generation performed)

`V2_011C_CONTEXT_REPAIR_PLAN.json` — failure classes `GEOGRAPHY + LIGHTING` at both junctions;
explicitly **not** failing: DIRECTION, IDENTITY, PROP, CAUSAL_ACTION, EDITABILITY, MISSING_ASSET.

- **R-A (recommended):** world-matched F1/F3 regeneration — F1R/F3R keep the fixture specs verbatim
  but must render the locked-F2 world (continuous-ridge choke point / BEYOND_GATE exit, cold
  blue-grey palette, road funneling into the single opening; forbidden: freestanding decorative
  gate, built tan wall, warm golden key). Identity via reference `7b725f7b-…`. Est. 2 generates.
  Then re-run 011C phases 2–6 read-only.
- **R-B:** grade-only bridge — requires separate Owner authorization (VFX/color concealment is
  forbidden inside the proof) and leaves GEOGRAPHY broken. Recorded as incomplete.
- **R-C:** narrative reorder (act break at F1→F2) — weakest; loses the bound geography.

## Outputs

```
projects/quality_v2_011c_full_sequence_context/
  V2_011C_CUSTODY.json  V2_011C_F1_AUTHORITY.json  V2_011C_F3_AUTHORITY.json
  V2_011C_F1_F2_CUT_QC.json  V2_011C_F2_F3_CUT_QC.json  V2_011C_SEQUENCE_QC.json
  V2_011C_ASSEMBLY_MANIFEST.json  V2_011C_CONTEXT_LOCK.json
  V2_011C_CONTEXT_REPAIR_PLAN.json  V2_011C_CANDIDATE_SEAL.json
  outputs/F1_F2_F3_CONTEXT_FAIL_REFERENCE_CUT.mp4
  owner_review_011c/{F1_F2_JUNCTION,F2_F3_JUNCTION,FULL_SEQUENCE_CONTACT_SHEET}.png
tools/build_v2_011c_evidence.py   (fail-closed: recomputes every custody SHA before writing)
```
