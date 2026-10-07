# AI FILM QUALITY V2-011W-R2 — DOLA GENERATION-TIME ASSET VARIANT AUTHORITY

Slice: `AI-FILM-QUALITY-V2-011W-R2` · forensic/observability slice · **0 video mutations** ·
Elyum frozen (canary 0/1 UNSPENT) · film assets untouched (`F2 ada66463…`, proof `63eac46c…` recomputed).

## Headline

```
DOLA_UNWATERMARKED_VARIANT = PROVIDER_ISSUED   (upgraded from OBSERVED_NOT_AUTHORIZED)
SAME_CREATION_VARIANTS     = PROVEN
UNWATERMARKED_PIXELS       = PROVEN (WATERMARK_ABSENT)
SAME_GENERATION_EQUIVALENCE = PROVEN
AUTHORITY_CLASS            = B — PROVIDER_ISSUED_SIBLING (Owner entitlement decision pending)
```

## Phase 1 — historical forensics (raw captures, DPAPI-decrypted through authorized tooling)

24 retained raw captures scanned. Results: the 010C-era F2A lifecycle capture
(`raw_f2b_20261006T015220.jsonl.dpapi` — the F2A creation `1540180629641233`) carries **2,214
`unwatermarked` mentions across 245 response entries**; the current-era capture of OUR film asset
F3R_012 (`raw_f3r_012_20261006T145913.jsonl`) carries **12 mentions in 4 entries**; the
F1R/F2A-R/F2B-R captures contain 0 (they ended before their completion polls).

Origin classification: **A — raw poll-response delivery (the /im/chain/single and recent_conv
bodies)**. The marker is NOT metadata: it sits inside `video.video_model` — a JSON-STRING field
of the creation video object — whose decoded payload contains a `video_list` playback structure
with per-rendition URLs.

## The missed surface (011W root cause)

`/im/chain/single` response → `messages[0].content<json>[1].content.creation_block.
creations[0].video.video_model<json>.video_list.video_1.main_url` — the video_list lives inside
`video_model`, a **JSON-string inside the creation video object**. The 011W scan walked object
keys but did not recurse into JSON-string fields, so it saw only `download_url (lr=cici_ai)`.
The same structure also appears a second time in `ext.creation_material_info<json>`.

Decoded `video_1` (definition label "1080p" — **label overstates; the actual render is
1280×720**; bitrate 888152): `main_url` → `v16-dola.dola.com` with **`lr=unwatermarked`**,
`backup_url_1` → `v19-dola.dola.com`, both provider-signed (a/br/bt/ft CDN signature family),
same creation, same vid.

## Phase 2 — AutoVideoPipeline

`tools/dola-render-gateway/video_worker.py::extract_unwatermarked_url` parses exactly
`video_model.video_list`, base64-decodes each `main_url`, selects the highest bitrate, falls
back to the watermarked `download_url`. **No URL construction anywhere →
`AUTOVIDEOPIPELINE_UNWATERMARKED_URL = PROVIDER_RETURNED`** (convergent independent evidence).

## Phase 3 — surface matrix (same creation F3R_012)

| Surface | lr=cici_ai (watermarked) | lr=unwatermarked (video_list) |
| --- | --- | --- |
| raw generation SSE (010C-era full lifecycle) | PRESENT | **PRESENT** |
| /im/chain/single limit=10 | PRESENT | **PRESENT** (video_model<json>) |
| /im/chain/single limit=20 | PRESENT | PRESENT (same shape; the 011W "limit-20 omits fields" finding was unrelated to this surface) |
| /im/chain/recent_conv | PRESENT | **PRESENT** |
| runtime creation object (011W scan) | PRESENT | missed (video_model string un-parsed) |
| player `<video>.currentSrc` | PRESENT | absent |
| UI download control | PRESENT (generic) | absent |
| AVP parser | fallback | **SELECTED** (highest bitrate) |

## Phase 6 verdict — CASE A (no fresh generation needed)

The historical/current raw evidence already proves Dola directly emits the unwatermarked sibling
for an exact creation. **No new generation was required; none was made.**

## Phase 8–11 — acquisition, equivalence, watermark (F3R_012, exact lineage)

A fresh authorized poll re-emits the video_list with fresh signed URLs (provider behavior, not
construction). The **exact provider-emitted unwatermarked URL** (base64-decoded, zero parameter
modification) was acquired:

```
downloads/f3r_012_unwatermarked.mp4
sha256 1b2515a1102bc85f… · 564,976 bytes · 5.088005s · 121 fr @ 24fps · 1280x720 · hevc
```

Same-generation equivalence vs the watermarked custody asset (`b558f8e8…`, 569,573 bytes):
duration/frame-count/fps/resolution/codec **identical**; every UNWM/WM pair at all 7
deterministic positions is the identical frame (same pose, rock, peaks, timing); no crop
difference. Only difference: the render layer.

**Watermark verdict (pixels only)**: unwatermarked variant — TL/TR/BL/BR corners at 0/50/100%
and all 7 full frames show **NO Dola AI mark** → `WATERMARK_ABSENT`. Watermarked reference —
"Dola AI" bottom-right at every sample → `WATERMARK_PRESENT`. The `lr` label is CONFIRMED by
pixels.

## Phase 12 — authority

- **Q1: Did Dola itself directly emit the URL? YES — PROVEN twice** (raw generation-time capture
  + fresh authorized poll).
- **Q2: entitlement = class B — PROVIDER_ISSUED_SIBLING**: directly sent, same creation, no
  client construction — but the UI is silent. Stronger than the old OBSERVED_NOT_AUTHORIZED;
  NOT yet class A (explicit). Whether class-B sibling assets may enter canonical film custody is
  an **Owner product-rights decision** (exactly as V2-010D recorded when the variant was first
  glimpsed).

## Phase 13 — DolaAssetVariantResolver (design proven live)

`tools/v2_011wr2_variant_acquire.py` implements it end-to-end: poll → deep-parse embedded JSON
strings → `video_model<json>.video_list` → enumerate renditions {definition, bitrate,
main/backup URLs, lr} → classify watermark state → exact-URL acquisition. Film Core would see
only classified variant handles. **No rebind executed** — current film unchanged.

## Required outputs

All written under `projects/quality_v2_011wr2_dola_variant_authority/`:
HISTORICAL_PROVENANCE · AVP_ASSET_PATH · SURFACE_MATRIX · OBSERVABILITY_CONTRACT (absorbed into
the acquisition tool + surface matrix) · LIVE_CAPTURE_INDEX · CREATION_VARIANTS ·
ASSET_EQUIVALENCE · WATERMARK_QC · AUTHORITY_CLASSIFICATION · ADAPTER_CONTRACT · SECRET_AUDIT
(CLEAN — 0 signed-value leaks) · CANDIDATE_SEAL. Media: `downloads/f3r_012_unwatermarked.mp4`.
Review: `owner_review_011w/F3R012_VARIANT_CONTACT_SHEET.png`,
`F3R012_VARIANT_CORNERS.png`. Human-readable: this file.

## STOP — return to Tech Lead

1. **Owner decides** whether class-B provider-issued silent siblings may enter canonical custody.
2. If yes → **V2-011X rebind slice**: acquire the unwatermarked siblings for
   F1R/F2A/F2B/F3R_012 via the proven fresh-poll resolver (the provider re-emits video_list per
   poll), run per-creation pixel QC, rebind custody preserving the frozen editorial ranges and
   the sequence lock, and re-seal the proof.
3. If no → retain watermarked custody; the clean-master question returns to the Elyum route
   (frozen 0/1, credit-gated) or the official API.
