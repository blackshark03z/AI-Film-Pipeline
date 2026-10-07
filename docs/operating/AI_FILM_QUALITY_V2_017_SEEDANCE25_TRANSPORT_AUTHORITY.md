# AI FILM QUALITY V2-017 — SEEDANCE 2.5 DRAFT→FINAL TRANSPORT AUTHORITY

Slice: `AI-FILM-QUALITY-V2-017` · Start HEAD `a857cbb` · **VIDEO MUTATIONS = 0** ·
Film untouched (`FINAL_MASTER_LOCK = GRANTED`; Elyum canary frozen 0/1).

## Conclusion

```
A THIRD SeedanceProvider route — BytePlus ModelArk (Dreamina Seedance family),
model dreamina-seedance-2-5-260628 — NATIVELY SUPPORTS:

  480p Draft ("draft": true)          → TaskCreationResponse.id = persistent draft_task_id
  → 7-day finalization window          → same-take 1080p Final
  → watermark=false as a DOCUMENTED REQUEST PARAMETER on both stages

RECONSTRUCTED FROM SOURCE IMPLEMENTATION (priority-1 evidence):
the ComfyUI built-in ByteDance partner node (comfy_api_nodes/nodes_bytedance.py,
3907 lines) + wire schemas (apis/bytedance.py, 425 lines), cross-confirmed by
the local Story Auto BytePlus client (watermark: False in real requests).
```

## Transport reconstruction (all fields per the package checklist)

| Requirement | Reconstructed value | Source |
| --- | --- | --- |
| Upstream provider | BytePlus ModelArk (`ark.ap-southeast.bytepluses.com/api/v3`) | ComfyUI + local client |
| Auth model | Bearer API key (env `BYTEPLUS_MODELARK_API_KEY`/`BYTEPLUS_API_KEY`/`ARK_API_KEY`) | client.py `_api_key` |
| Draft submit | `POST contents/generations/tasks` with `draft: true`, `resolution: "480p"` | nodes_bytedance `_seedance2_build_request` |
| Model ID | `dreamina-seedance-2-5-260628` — SAME id for draft and final (Draft is a mode flag) | `SEEDANCE_MODELS` |
| Request schema | `Seedance2TaskCreationRequest`: model/content[text\|image\|video\|audio\|draft_task]/generate_audio/resolution/ratio/duration(≤30)/seed/watermark/output_format/omni_reference_task_type/draft | apis/bytedance.py |
| draft_task_id source | `TaskCreationResponse.id` of the draft run (returned by the t2v/i2v/reference nodes as the `draft_task_id` output); ONLY the "Seedance 2.5 Draft" mode produces one | `_seedance2_validate_draft_output` |
| Poll/status | `GET contents/generations/tasks/{task_id}` (ComfyUI `/proxy/byteplus-seedance2/` variant), 9 s interval, statuses queued/running/cancelled/succeeded/failed | `_seedance2_poll_video_task` |
| Expiry | Draft renderable for **7 days**; output URLs cleared 24 h after completion (BytePlus docs) | node tooltip + docs |
| Finalization | `POST contents/generations/tasks` with content **type `"draft_task"`**: `{"task": {"id": draft_task_id}}`, `resolution: "1080p"` | `ByteDance2DraftToFinalVideoNode` |
| Same-take lineage | provider-documented: *"The final keeps the draft's scene and motion, and reuses its prompt, references, duration, aspect ratio, and audio setting"* | node description |
| Watermark parameter | `watermark: bool` request field on BOTH stages (node default **false**; Story Auto sends `watermark: False`) | both sources |
| Resolution/duration/references/audio | 480p draft → 1080p final; duration 4–30 s; references ≤30 images + ≤10 videos (≤15 s) + ≤10 audios with auto down/upscale; `generate_audio` flag + documented audio-policy rejection class | node inputs + error handling |
| Output identity | task id (persistent, listable via `contents/generations/tasks?page_size`) + `content.video_url` | client + schema |
| Download authority | `content.video_url`, https, host allowlist `volces.com`/`bytepluses.com`/`byteplus.com` | Story Auto client |
| Pricing semantics | per-frame: 2.5 480p ≈ 400 frames/unit at $0.015301/kframe; 1080p ≈ 2025 at $0.016731 — **4 s 480p draft ≈ $0.59; 4 s 1080p final ≈ $3.29** (price-badge formula matches the node's $3.2864 min) | `_SEEDANCE2_PRICE_EXPR_TEMPLATE` |
| Account-pool suitability | one API key = one account namespace; the finalization MUST share the draft's key (task ownership); rotation only before draft dispatch | reconstruction |
| Restart/idempotency | poll GETs idempotent; draft id persistent + listable (`list_tasks`); POST transport failure = `AMBIGUOUS_POST_DISPATCH` → reconcile via list/get, NEVER a second POST | Story Auto service discipline |

## Draft→Final domain mapping (Film Core boundary)

`V2_017_DRAFT_FINAL_DOMAIN_MODEL.json` maps the reconstructed transport onto
DraftAttempt (provider_draft_id = draft task id, expiry 7 d/24 h, mutation
receipt) → DraftSelection → FinalizationAttempt (`parent_draft_attempt_id`
→ content type `draft_task`) — the invariant **finalization references an
EXIST draft identity** is satisfied by the provider's own `draft_task`
content type. Film Core never sees `draft: true`, content-type strings,
ModelArk paths, CDN hosts, or signature params.

## Source snapshots

`analysis/nodes_bytedance.py` + `analysis/bytedance_schema.py` (upstream
master snapshots, retained locally; untracked).

## STOP — return to Tech Lead

Live qualification requires an **Owner decision + provisioned BytePlus
ModelArk API key and credits** (none verified present on this machine —
credential scan CLEAN). The frozen experiment would be:
1 draft (480p, ~$0.59) → 1 finalization (1080p, ~$3.29) → per-position pixel
QC → watermark=false verification — under the 011D/012 dispatch discipline.
