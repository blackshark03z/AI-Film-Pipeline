# AI-FILM-QUALITY-V2-011A — F2 Creative / Continuity Acceptance

Read-only quality slice. **0 provider mutations.** Evaluation authority:
the FROZEN V2-009 plan + V2-008 intent blocks. Worker visual read of the
deterministic 11-frame review pack (`owner_review/`) — the Owner visual
read remains authoritative.

## VERDICT SUMMARY

```text
F2A: REPAIR_REQUIRED   (direction failure — everything else largely works)
F2B: REJECT            (fortress-gate world + sword + warm palette +
                        no causal wind — 12 critical dimension failures)
PAIR CUT: FAIL         (the two shots do not join as continuous film)
F2_SEQUENCE: REPAIR_REQUIRED
STATUS: COMPLETED_CANDIDATE (engineering) — creative acceptance NOT granted
```

## F2A — REPAIR_REQUIRED

| Dimension | Verdict | Evidence |
|---|---|---|
| Narrative purpose | PASS | road funnel → commit → enter pass, crossing not completed |
| Causal action | PASS | t60: lean INTO gust, headband streaming leeward, robes pressed |
| Identity / wardrobe | PASS | white robes + black sash + topknot, stable; **no sword** |
| Scene geography (in-shot) | PASS | continuous ridge BOTH sides of the single gap, in the same frames; road funnels in; no bypass |
| **Screen/Travel direction** | **FAIL** | **frontal (toward-camera) traversal — the frozen axis is lateral frame-left (F1/F3 continuity); no sub-range fixes it** |
| Start / End state | PASS | t0 road-before-pass; t100 inside the opening, committed, boundary both sides |
| Camera | PASS | locked, no orbit, geography kept legible |
| Technical | PASS | full decode, no frozen/dup frames, no anomalies in samples |
| Watermark | PRESENT | bottom-right, every frame |

**Phase 4 classification: MAJOR_DIRECTION_FAILURE.** In-shot geography is
coherent; the failure is the traversal axis against the frozen F1/F3
lateral continuity — wholesale, not trim-fixable.

**Editorial:** a clean ≈2.8s section exists (7.2–10.0s, in-pass) and is
narrative-best — but every section inherits the frontal axis, so no cut
satisfies the frozen slot.

## F2B — REJECT

| Dimension | Verdict | Evidence |
|---|---|---|
| Narrative purpose | **FAIL** | calm walk out of a built gate; the forced exit through a wind funnel is absent |
| Causal action | **FAIL** | no gust anywhere: robes hang, no lean, no streaming |
| Prop state | **FAIL** | **a sword (dark scabbard) is visible t0→t100** |
| Scene geography | **FAIL** | **built fortress-gate architecture: cut stone blocks, mortar, LINTEL ROOF, parapets — CASTLE_OR_FORTRESS and FREESTANDING_DECORATIVE_GATE are explicitly forbidden by the frozen plan** |
| **Screen/Travel direction** | **FAIL** | moves AWAY from camera; with F2A frontal, the pair holds no consistent axis |
| Lighting | **FAIL** | warm golden key vs the cool storm-blue SEQ7 world |
| Environment | **FAIL** | hazy warm plain; no rock-ridge boundary, no storm sky |
| Start / End state | **FAIL** | built corridor + doorway instead of pass threshold + natural boundary behind |
| Identity / technical | PASS | robes/topknot consistent; decode and temporal stability clean |
| Watermark | PRESENT | bottom-right, every frame |

**Editorial:** no sub-range usable — the violations are in every frame.

## F2A → F2B CUT

| Dimension | Verdict |
|---|---|
| Character identity | MATCH |
| World material | **MISMATCH** (natural rock pass vs built blocks) |
| Palette | **MISMATCH** (cool storm-blue vs warm gold) |
| Prop | **MISMATCH** (sword appears) |
| Travel axis | **MISMATCH** (toward-camera → away-from-camera: the traversal REVERSES at the cut) |
| Action energy | **MISMATCH** (forcing lean → calm stroll) |

The cut does not read as continuous film. Confidence: HIGH (frames sampled
on both sides of the junction; side-by-side at
`owner_review/F2A_F2B_side_by_side.png`).

## REPAIR SPECIFICATIONS (no regeneration executed)

```text
F2A  DIRECTION_FAILURE      → new start/end frame constraint enforcing the
                              lateral frame-left axis (camera beside the
                              pass axis); world/wardrobe already QC-PASS
F2B  GEOGRAPHY_FAILURE      → stronger location reference: natural
                              rock-ridge choke point; forbid cut blocks/
                              lintel/parapet in the negative set
F2B  IDENTITY_PROP_FAILURE  → explicit no-visible-sword wardrobe constraint
F2B  LIGHTING_CAUSAL_FAILURE→ cool storm-blue reference + causal wind
                              escalation (cloth/hair/grass vectors against
                              travel)
```

## PRODUCTION LOCK

**NOT GRANTED.** `F2_SEQUENCE = REPAIR_REQUIRED`. The assets stay
custody-frozen as repair-source material (F2A sha `970018be…`, F2B sha
`9c86ac27…`, creation 1546437193256465) but are NOT accepted as film
footage. Tech Lead decision: **V2-011R TARGETED REPAIR is the recommended
route** (editorial-first cannot fix either shot's critical failures); any
regeneration requires NEW Owner authority under the repair specs above.

## WHAT THE OWNER SHOULD LOOK AT

1. `owner_review/F2A_contact_sheet.png` — the commitment/enter read
   (works) and the frontal axis (the failure)
2. `owner_review/F2B_contact_sheet.png` — the fortress-gate world, the
   sword, the warm palette
3. `owner_review/F2A_F2B_side_by_side.png` — why the cut cannot join

Worker verdicts are advisory; the Owner visual read is authoritative.
