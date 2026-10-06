# AI FILM QUALITY V2-011W — DOLA UNWATERMARKED ASSET AUTHORITY QUALIFICATION

Slice: `AI-FILM-QUALITY-V2-011W` · Start HEAD `a48a0ad` · **VIDEO_GENERATION_MUTATIONS = 0**
Nature: provider-asset authority qualification, read-only. No generation, no purchase, no
parameter tampering, no URL guessing, no undocumented endpoints.

## Final state

```
STATUS                    = COMPLETED_CANDIDATE
AUTHORITY                 = NOT ESTABLISHED — LEVEL D for all four frozen creations
UNWATERMARKED_VARIANT     = OBSERVED_NOT_AUTHORIZED (retained)
UNWATERMARKED_AUTHORITY   = NOT_AVAILABLE (current creations, current qualified paths)
CURRENT FILM ASSETS       = UNCHANGED (all SHAs recomputed: F1R b879f215…, F2 ada66463…,
                            F3R_012 b558f8e8…, proof 63eac46c…; SEQ_CONTEXT_LOCK stays GRANTED)
```

## What was inspected

PHASE 0 custody: HEAD `a48a0ad`, all film SHAs recomputed, seal GRANTED — PASS.

PHASE 1 — creation objects (limit-10 qualified pull, redacted: signed query values stripped,
`lr` marker + param names kept as structural evidence):

| Creation | Account | lr values provider-delivered | Level |
| --- | --- | --- | --- |
| F1R (1546471384527889) | ACCOUNT_A | cici_ai only | D |
| F2A-R (1543341075843857) | ACCOUNT_A | cici_ai only | D |
| F2B-R (1546449850446097) | ACCOUNT_A | cici_ai only | D |
| F3R_012 (1542350901495057) | ACCOUNT_D | cici_ai only | D |

PHASE 2 — UI entitlement: card-scoped control surfaces on all four creations show the generic
player controls (play/pause/mute) and **no no-watermark/original control anywhere**
(`UI_GENERIC_DOWNLOAD` at page level; the only "download"-labeled page element is the site's
Windows-installer button — the v1 lesson: page-wide label scans must never drive clicks).
Screenshots in `owner_review_011w/`.

PHASE 3 — network correlation (the decisive evidence): opening the F3R_012 video mounts the
provider player whose `<video>.currentSrc` is a **provider-issued URL (unmodified, lr=cici_ai)**.
Acquiring that exact URL through the authenticated browser-context request returned
**569,573 bytes, sha `b558f8e8…` — byte-identical to the watermarked custody asset**. The
provider's own authenticated player streams the WATERMARKED variant. Parameter tampering: NONE.

## Authority classification

- **LEVEL A (explicit): NOT REACHED** — no UI control, plan surface, or provider workflow on
  the four creations exposes a no-watermark variant.
- **LEVEL B (provider-delivered, unclear): NOT REACHED** for the four frozen creations —
  provider-delivered objects carry only `lr=cici_ai`. HISTORICAL note: the 010C-era F2A raw SSE
  capture (reconstructed in `V2_010D_UNWATERMARKED_VARIANT.json`) carried `lr=unwatermarked`-
  labeled variants, but that creation's message has rolled out of the current conversation pull
  window and cannot be re-verified through any qualified path — it remains
  `OBSERVED_NOT_AUTHORIZED` (re-deriving it would require forbidden URL work).
- **LEVEL C (derivable): NOT EXERCISED** — forbidden by the package.
- **LEVEL D (no variant observed): REACHED** for all four minimum creations under current
  qualified paths — three independent channels agree: creation objects, UI control surfaces,
  and the player stream bytes.

## Consequences

- `DolaAssetVariantResolver` = **NOT_QUALIFIED**; the conditional contract and qualification
  preconditions are recorded in `V2_011W_ADAPTER_CONTRACT.json`.
- Migration: **NOT_REQUIRED** — no authority; watermarked custody stands. A controlled rebind
  sketch is recorded for a future Owner-authorized slice if LEVEL A ever materializes.
- Production continues on watermarked assets; watermark remains a finishing/provider-rights
  question.

## Mandatory handoff — STOP

Return to Tech Lead: **(A) V2-011X authorized watermark-free rebinding is NOT actionable now**
(no authority to bind); **(B) retain watermarked custody and proceed to finishing strategy.**
Re-qualification preconditions are recorded in `V2_011W_ADAPTER_CONTRACT.json`.
