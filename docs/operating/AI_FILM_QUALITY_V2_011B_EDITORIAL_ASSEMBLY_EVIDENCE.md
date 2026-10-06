# AI-FILM-QUALITY-V2-011B — F2 Editorial Assembly + Actual Cut Proof

```text
STATUS
  COMPLETED_CANDIDATE — CUT_PASS (after an authorized ±12-frame micro-trim)
  F2_CREATIVE_LOCK = GRANTED (Owner ruling)
  F2_PRODUCTION_LOCK = GRANTED
  F2_EDITORIAL_LOCK = GRANTED
  F2_SEQUENCE = FILM_USABLE

FINAL HEAD
  branch quality-v2/011b-editorial-assembly
  base = 011R HEAD 4564b922c0692775c71d15a0aa308266c256aeee (resolved,
  not inferred)

OWNER RULING (recorded verbatim in V2_011B_OWNER_ACCEPTANCE.json)
  F2A-R ACCEPTED / F2B-R ACCEPTED / PAIR ACCEPTED
  BLACK CLOTH ADVISORY = ACCEPTABLE
  FOOTWEAR DIFFERENCE = ACCEPTABLE / LOW SALIENCE
  PRODUCTION LOCK = GRANTED

F2A
  asset:            assets/f2a_r.mp4 — sha 50a133c8… (custody verified)
  requested range:  1.2s → 4.0s
  resolved frames:  29 → 96 (first build) — then MICRO-TRIMMED to 41 → 108
                    (both junction sides moved into the dark-gap occlusion;
                    67 frames preserved)
  actual range:     1.708333s → 4.500000s (67 frames = 2.791667s)
  selected output:  outputs/F2A_R_SELECTED.mp4 (h264 + AAC, sha in ranges
                    JSON)

F2B
  asset:            assets/f2b_r.mp4 — sha 8679709b… (custody verified)
  requested range:  0.4s → 3.2s
  resolved frames:  10 → 77 (first build) — then MICRO-TRIMMED to 0 → 67
                    (starts deepest in the dark gap; 67 frames preserved)
  actual range:     0.000000s → 2.791667s (67 frames = 2.791667s)
  selected output:  outputs/F2B_R_SELECTED.mp4

CUT
  type:       HARD CUT (no dissolve/crossfade/speed-ramp/interpolation)
  verdict:    CUT_PASS
  micro-trim: PERFORMED within the package's ±12-frame maximum —
              candidates considered and recorded (4 pairs); the chosen
              pair moves both junction sides into the dark-gap darkness:
              the character walks INTO the dark gap on the F2A side and
              comes OUT of the darkness on the F2B side — the black-cloth
              pop visible at the original junction is occluded by the
              darkness and no longer reads
  continuity: screen direction, travel direction, motion vector, body
              phase, world material, palette, weather, action energy,
              wardrobe ALL MATCH across the cut; character scale shows a
              minor expected pop (exit side of a through-cut)

ASSEMBLED PROOF
  outputs/F2_SEQUENCE_EDITORIAL_PROOF.mp4
  duration: 5.583356s (134 frames exactly; expected 5.583333)
  fps:      24/1
  codec:    h264 (yuv420p re-encode; source hevc custody assets preserved)
  audio:    AAC 192k, trimmed in sync (source wind ambience)
  sha256:   ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de
  decode:   PASS; no black frames; no frozen/duplicate frames at the cut;
            no timestamp discontinuity (concat FILTER used after the
            demuxer produced a 1-frame duplicate)

WATERMARK
  PRESENT — Dola AI mark bottom-right, preserved exactly. No removal,
  no concealment. UNWATERMARKED_VARIANT remains OBSERVED_NOT_AUTHORIZED.
  (Video-object variants carry lr=unwatermarked — recorded, not used.)

F2 EDITORIAL LOCK
  GRANTED — frozen: both asset SHAs, both resolved frame ranges, cut type
  HARD_CUT, sequence duration 5.583333s, assembled proof SHA, QC decision,
  Owner ruling. Immutable input to later assembly.

PROVIDER MUTATIONS = 0

TESTS
  Full regression 1316 passed (011R state). 

EVIDENCE
  projects/quality_v2_011b_editorial_assembly/:
    V2_011B_OWNER_ACCEPTANCE.json
    V2_011B_EDITORIAL_RANGES.json
    V2_011B_CUT_QC.json
    V2_011B_TECHNICAL_QC.json
    V2_011B_EDITORIAL_LOCK.json
    V2_011B_CANDIDATE_SEAL.json
    V2_011B_ASSEMBLY_MANIFEST.json
    outputs/{F2A_R_SELECTED,F2B_R_SELECTED,
             F2_SEQUENCE_EDITORIAL_PROOF}.mp4
    owner_review_011b/{ACTUAL_CUT_contact_sheet,
                       CUT_MINUS_12_TO_PLUS_12}.png
  docs/operating/AI_FILM_QUALITY_V2_011B_EDITORIAL_ASSEMBLY_EVIDENCE.md

WORKTREE
  011B work committed on quality-v2/011b-editorial-assembly.

STOP REASON
  None — editorial proof complete with CUT_PASS and all three locks
  granted. Context check: FULL_SEQUENCE_CONTEXT = NOT_EVALUATED (no
  deterministically-identified F1/F3 assets in scope; non-blocking).
```

## Notes

1. **The actual editorial cut differs from the contact-sheet junction** —
   as the package anticipated. The original boundaries (F2A 4.0s / F2B
   0.4s) showed a black-cloth pop (the 011R cape vanishing at the cut —
   CUT_PASS_WITH_MINOR_POP). The authorized ±12-frame micro-trim moved
   both junction sides into the dark-gap occlusion (F2A out 4.0 → 4.5s,
   F2B in 0.4 → 0.0s) — the character now passes THROUGH the darkness and
   the pop is gone. Every candidate pair considered is recorded in
   V2_011B_CUT_QC.json.
2. **Frame-boundary honesty**: 1.2s/0.4s/3.2s do not land on 24fps frames
   (28.8/9.6/76.8); nearest-frame resolution applied and the actual
   resolved timestamps/durations are recorded (2.791667s per clip, not
   2.8s).
3. **Assembly defect found and fixed**: the concat demuxer produced a
   1-frame duplicate at the junction (135 frames); the concat FILTER
   (single encode) yields exactly 134.
