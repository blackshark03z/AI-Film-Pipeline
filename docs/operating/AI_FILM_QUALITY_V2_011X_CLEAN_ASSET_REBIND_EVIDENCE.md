# AI FILM QUALITY V2-011X — DOLA PROVIDER-ISSUED UNWATERMARKED ASSET REBINDING

Slice: `AI-FILM-QUALITY-V2-011X` · Start HEAD `55d4fe2` · **VIDEO_GENERATION_MUTATIONS = 0** ·
Elyum frozen (canary 0/1 UNSPENT).

## Owner authority (Phase 1)

`V2_011X_OWNER_AUTHORITY.json` — decision
`CLASS_B_PROVIDER_ISSUED_SIBLINGS_ALLOWED_FOR_CANONICAL_CUSTODY`, explicit for this project.
Allowed: exact provider-emitted URLs only. Forbidden: constructed URLs, lr/signature editing,
guessed paths, watermark removal/inpainting/cropping, alternate-generation substitution. This is
a product authorization, not UI-explicit entitlement (class B remains class B).

## Phase 0 — custody entry gate: PASS

HEAD `55d4fe2`, clean worktree, `SEQ_CONTEXT_LOCK = GRANTED`; recomputed and matched:
F1R `b879f215…`, F2A-R `50a133c8…`, F2B-R `8679709b…`, F3R_012 `b558f8e8…`, F2 proof
`ada66463…`, 326-frame proof `63eac46c…`.

## Phase 2 — clean sibling acquisition (all four, exact provider-emitted URLs)

The proven resolver (fresh authorized polls → deep-parse embedded JSON strings →
`video.video_model<json>.video_list` → enumerate renditions → select `lr=unwatermarked`) acquired:

| Creation | Clean sibling | Size | Notes |
| --- | --- | --- | --- |
| F1R (1546471384527889) | sha `36f887df…` | 297,336 B | ACCOUNT_A poll |
| F2A-R (1543341075843857) | sha `cb6332a6…` | 642,925 B | ACCOUNT_A poll |
| F2B-R (1546449850446097) | sha `caa35ec8…` | 511,216 B | ACCOUNT_A poll |
| F3R_012 (1542350901495057) | sha `1b2515a1…` | 564,976 B | ACCOUNT_D poll (byte-identical to the R2 acquisition — provider emission stable) |

Operational lesson recorded: a crashed patchright launch leaves a live chromium holding the
profile lock ("Opening in existing browser session") — force-clear the profile holder between
targets. Signed query values never persisted.

## Phases 3–5 — per-creation QC: ALL PASS

| Creation | Technical compatible | Equivalence MAD (excl. watermark region) | Watermark (pixels) |
| --- | --- | --- | --- |
| F1R | PASS (121 fr, 5.088s, 1280x720, hevc) | max 0.729 | ABSENT (BR delta 108) |
| F2A-R | PASS | max 1.408 | ABSENT (BR delta 79; box max-diff 191) |
| F2B-R | PASS | max 1.049 | ABSENT (BR delta 95; box max-diff 211) |
| F3R_012 | PASS | max 1.138 | ABSENT (box max-diff 214 — the p95 delta was diluted by bright robes; documented metric refinement + visual zoom `F3R_BR_ZOOM.png`) |

`SAME_GENERATION_EQUIVALENCE = PROVEN ×4` · `WATERMARK_ABSENT = PROVEN ×4` — at deterministic
positions 0/10/25/50/75/90/100% per pair.

## Phases 6–7 — canonical rebind (custody migration only)

`assets/clean/{f1r,f2a_r,f2b_r,f3r_012}.mp4` bound as canonical clean custody; historical
watermarked assets ARCHIVED as `PREDECESSOR_VARIANT` (not deleted). ShotSpec/PromptPlan/story
state/director intent/world state/creative verdict/continuity verdict/editorial ranges —
untouched. Registry in `V2_011X_ASSET_REGISTRY.json`.

## Phases 8–9 — clean proofs rebuilt (exact frozen ranges, concat filter)

```
F2_SEQUENCE_EDITORIAL_PROOF_CLEAN.mp4   134 frames EXACT · 5.583356s · sha 1dc186699c3b…
F1R_F2_F3R_SEQUENCE_PROOF_CLEAN.mp4     326 frames EXACT · 13.583356s · sha 08200f018c18…
h264 yuv420p + AAC 192k · 24fps · decode PASS · 0 timestamp discontinuities · no black/frozen
```

## Phases 10–12 — sequence QC, lock preservation, watermark-free master

- Sequence QC: **TECHNICAL_QC = PASS** (326 exact, decode PASS, 0 discontinuities, no
  black/frozen frames).
- Lock preservation: 12 frames spanning all three units and both cuts, watermark regions
  excluded → **max MAD 1.645** → CREATIVE/PRODUCTION/EDITORIAL/SEQ_CONTEXT locks **PRESERVED**.
  ARRIVE → FORCE THROUGH → COST HELD unchanged (same frames).
- Master watermark proof: bottom-right box sampled every 13 frames + both cut boundaries
  (31 samples) → **0 elevated** → `DOLA_WATERMARK = ABSENT`; no other provider marks observed.

## Canonical state

```
DOLA_CLEAN_ASSET_ROUTE = QUALIFIED
DOLA_ASSET_VARIANT_RESOLVER = QUALIFIED_FOR_PROVIDER_ISSUED_VARIANTS
CURRENT_CANONICAL_FILM_ASSETS = UNWATERMARKED_PROVIDER_ISSUED
SEQ7_F1_F2_F3 = CLEAN_FILM_USABLE
F2_CREATIVE_LOCK = PRESERVED · F2_PRODUCTION_LOCK = PRESERVED · F2_EDITORIAL_LOCK = PRESERVED
FULL_SEQUENCE_CONTEXT = PROVEN · SEQ_CONTEXT_LOCK = PRESERVED
Predecessor (watermarked) proof 63eac46c… = ARCHIVED
AUDIO_CONTEXT = FINISHING_REPAIR_REQUIRED (J1 0.8 dB, J2 8.0 dB — carried to V2-015)
```

## STOP — return to Tech Lead

Next intended slice: **V2-015 — Final Audio / Finishing / Distribution Master**
(ambience level-match J2 ~8 dB / J1 ~0.8 dB, wind continuity, loudness normalization — on the
clean master).
