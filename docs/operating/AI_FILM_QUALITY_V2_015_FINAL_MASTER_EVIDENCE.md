# AI FILM QUALITY V2-015 — FINAL AUDIO / FINISHING / DISTRIBUTION MASTER

Slice: `AI-FILM-QUALITY-V2-015` · Start HEAD `18f0d49` · **VIDEO_GENERATION_MUTATIONS = 0** ·
no provider mutation, no rebind, no creative change.

## Final state

```
STATUS                    = COMPLETED_CANDIDATE
FINAL_MASTER_LOCK         = GRANTED
AUDIO_CONTEXT             = FINISHED · FINISHING_QC = PASS
SEQ7_F1_F2_F3             = CLEAN_DISTRIBUTION_MASTER_READY
CREATIVE/PRODUCTION/EDITORIAL/SEQ_CONTEXT locks = PRESERVED (unchanged)
```

## Phase 0 — custody: PASS

HEAD `18f0d49`, clean worktree, clean sequence SHA recomputed
`08200f018c182fb1995d54853853aa7e231da929725d68ae6668e4895dba94b2`, 326 frames @ 24fps,
`SEQ_CONTEXT_LOCK = PRESERVED`.

## Phase 1 — audio forensics (re-measured from the clean canonical source; the earlier 0.8/8.0 mean-based values are superseded)

| Window | Integrated (1 s) | True peak |
| --- | --- | --- |
| F1R segment | −21.2 LUFS | — |
| F2 segment | −17.1 LUFS | — |
| F3R segment | −26.1 LUFS (contains near-silence — the settle beat is intended) | — |
| J1 pre / post (1 s) | −14.8 / −16.5 → momentary step **1.8 dB** | −11.7 / −15.7 dBFS |
| J2 pre / post (1 s) | −12.8 / −24.4 → momentary step **8.7 dB** | −7.1 / −18.5 dBFS |
| FULL | −19.5 LUFS, LRA 7.3 | — |

## Phases 2–3 — repair (minimal intervention, existing audio only)

- Per-segment gains: **F2 −1.5 dB** (balancing J1 and easing J2), **F3R +7.0 dB** (ambience-bed
  continuity).
- **0.4 s equal-power crossfades (~10 frames, within the ≤12 window) centered exactly on each
  picture cut** — the crossfade crosses the cut in audio while the picture never moves. Total
  duration preserved exactly at 13.583333 s.
- No external ambience bed required; no EQ needed (wind character continuous after level
  matching); crossfade removes the discontinuity (de-click by construction).

## Phase 4 — loudness

Two-pass linear `loudnorm` (I = −14, TP = −1.5, LRA = 11) + 48 kHz resample.
Measured on the distribution master: **−13.9 LUFS integrated, True Peak −1.5 dBTP, LRA 4.8** —
no clipping, no pumping, natural wind dynamics.

## Phases 5–6 — masters (video stream-COPIED, never re-encoded)

| Master | Path | SHA256 |
| --- | --- | --- |
| Mezzanine (.mov, video copy + PCM 16-bit 48 kHz) | `outputs/SEQ7_F1_F2_F3_CLEAN_FINISH_MASTER.mov` | `6a844134f505484d…` |
| Distribution (.mp4, video copy + AAC 192k 48 kHz) | `outputs/SEQ7_F1_F2_F3_CLEAN_DISTRIBUTION.mp4` | `081935b68a7b99af…` |

Both: 1280×720, 326 frames, 13.583333 s, h264 high, faststart.

## Phases 7–10 — QC

- **Frame preservation: BIT-EXACT** — the video elementary stream MD5 is identical between the
  clean locked proof and the distribution master (`3df80e57…`); same composition/crop/timing/shot
  boundaries/326-frame timeline, no inserted or dropped frames.
- **Watermark regression: 31 bottom-right samples (every 13 frames + both cut boundaries) —
  0 elevated → `DOLA_WATERMARK = ABSENT`**; no other marks or overlays (corner zooms at unit
  boundaries reviewed).
- **Junction QC: J1 PERCEPTUALLY_CONTINUOUS** (residual 1.7 dB over 1 s windows, masked by the
  0.4 s crossfade at the cut; no click/pop) — **J2 PERCEPTUALLY_CONTINUOUS** (residual **0.5 dB**,
  from 8.7 dB); no phase collapse, no clipping (TP −1.5), no pumping, natural wind modulation.
- **AV sync: PASS** — video and audio durations both 13.583333 s, aligned start/end, no padding,
  no truncation, no drift. Picture remains the 326-frame authority.

## Phase 11 — FINAL_MASTER_LOCK

```
AUDIO_CONTEXT = FINISHED      FINISHING_QC = PASS      FINAL_MASTER_LOCK = GRANTED
SEQ7_F1_F2_F3 = CLEAN_DISTRIBUTION_MASTER_READY
CREATIVE_LOCK = PRESERVED · PRODUCTION_LOCK = PRESERVED
EDITORIAL_LOCK = PRESERVED · SEQ_CONTEXT_LOCK = PRESERVED
```

Review assets: `owner_review_015/{FINAL_SEQUENCE_CONTACT_SHEET,FINAL_CUT_J1,FINAL_CUT_J2,
FINAL_SEQUENCE_CORNERS}.png`.

## STOP — return to Tech Lead

The distribution master is ready. Any further production (more sequences), delivery specs, or
release decisions are Tech Lead scope. No further generation was performed; Elyum canary remains
frozen 0/1.
