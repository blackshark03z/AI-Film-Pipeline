# AI FILM QUALITY V2-016 — SEEDANCE 2.5 DRAFT→FINAL CAPABILITY AUTHORITY

Slice: `AI-FILM-QUALITY-V2-016` · Start HEAD `a857cbb` · **VIDEO MUTATIONS = 0 (both providers)** ·
Film untouched (`FINAL_MASTER_LOCK = GRANTED`; master `081935b6…` recomputed via custody checks).

## Conclusion

```
E. NO_CURRENT_ROUTE_OBSERVED — true Draft→Final (same-take provider lineage)
   exists on NEITHER Dola NOR Elyum.

Seedance 2.5 itself: PRESENT on BOTH providers — as a premium GENERATION
model, not as a draft stage:

  Dola   : composer option "Dreamina Seedance 2.5" (wire id seedance_v2.5),
           subscriber-gated (subs_only_tag "enhanced"), 5× credits/generation
  Elyum  : catalog models seedance-2.5-t2v / -i2v / -reference
           (480p/720p/1080p, durations 4-15, native audio, video-edit input),
           quoted 136-170 credits per generation
```

## Evidence chain

1. **Elyum tool surface is exhaustive**: `tools/list` returned the complete
   tool catalog — **21 tools** (`elyum_account, referral, models, estimate,
   creators, add_creator, upload, kling_subjects*, make_image, make_video,
   make_audio, make_avatar, run_test_pack, job_status, wait, keep, kill,
   export_pack, library`). **No draft/finalize/upscale tool exists.** The
   keep/kill lifecycle is hold/unlock of a SINGLE generation — explicitly
   classified as `ELYUM_PREVIEW_KEEP ≠ ELYUM_SEEDANCE_DRAFT ≠
   ELYUM_DRAFT_FINAL`.
2. **Elyum catalog**: Seedance 2.5 family fully specified (resolutions
   480p/720p/1080p, durations 4-15 s, native audio, reference model with
   30 images + 10 clips + video-edit input). The "draft" tokens in the
   catalog are **marketing taglines** positioning cheap tiers ("Quick, cheap
   first-frame drafts") — a use pattern, not lineage.
3. **Dola composer template** (provider-delivered during the f3r_012
   generation, reconstructed from the raw capture): model selector options
   **Dreamina Seedance 2.5 / 2.0 / 1.0** with the 2.5 option carrying
   `model: seedance_v2.5`, `sub_display: 最高品質 • 5倍のクレジットを使用`
   (Highest quality • 5× credits) and **`subs_only_tag: enhanced`**.
4. **Dola frontend bundles**: 8 bundles scanned; "draft"/"finalize" tokens
   are Immer.js internals, chat-draft service and telemetry flush — NOT
   video draft-to-final. UI strings tag only "Seedance 2.0"; `seedance_v2.5`
   appears only in the composer option template.
5. **Dola wire captures**: "draft" tokens across all captures are chat-input
   draft chunk loaders; the `video_model` delivery blob carries playback
   structure only — no model version, no draft lineage fields
   (draft_id/draft_task_id/parent_generation_id/source_task_id/finalize_id
   found NOWHERE on either provider).

## Capability matrix (full matrix in V2_016_SEEDANCE25_CAPABILITY_MATRIX.json)

| | Dola | Elyum |
| --- | --- | --- |
| Seedance 2.5 | YES (UI option) | YES (catalog) |
| Draft generation | NO | NO (cheap tiers are draft-positioned, not a lineage) |
| Draft identity | N/A | N/A |
| Finalize action | NONE OBSERVED | NONE OBSERVED (21-tool surface exhaustive) |
| Same-take guarantee | N/A | N/A |
| Cost | 5× credits (subscriber-gated) | 136-170 credits quoted |
| Clean output | video_list sibling route applies per generation (unproven for 2.5) | unproven (no render) |

## Domain model (conditional), QC split, economics, account pool

- `V2_016_DRAFT_FINAL_DOMAIN_MODEL.json` — DraftAttempt / DraftSelection /
  FinalizationAttempt designed with the invariant **FINALIZATION MUST
  REFERENCE AN EXIST DRAFT IDENTITY**; Film Core sees only handles.
- `V2_016_DRAFT_QC_POLICY.json` — draft-authoritative (composition, blocking,
  motion, world, rhythm, beat) vs final-only (face, hands, texture, defects).
- `V2_016_COST_MODEL.json` — full Elyum quote matrix; **without provider
  lineage the "draft×N + 1 final" pattern is only a DIRECTOR-EFFICIENCY
  improvement (reject composition at 56 instead of 136-170 credits), not
  credit arithmetic**; break-even ≈ 0.7 expected rejects per accepted shot —
  borderline and quality-dependent.
- `V2_016_ACCOUNT_POOL_IMPLICATIONS.json` — Dola finalization binding
  `UNKNOWN_REQUIRE_LIVE_PROOF` (no surface to test); Elyum generations are
  per-account independent; no rotation after ambiguous mutation.

## Live proof

**Not required for the authority question** — the answer comes from
exhaustive surface reconstruction (the Elyum tool list is the complete tool
surface; the Dola composer template is the provider-delivered selector).
Optional Owner canaries (2.5 output quality) would require: Elyum top-up
(≥ 110 credits margin over the 30 balance) or Dola subscriber plan state —
both escalate to Owner.

## STOP — return to Tech Lead

`SEQ7_F1_F2_F3 = CLEAN_DISTRIBUTION_MASTER_READY` untouched; Elyum canary
frozen 0/1; Dola credits untouched.
