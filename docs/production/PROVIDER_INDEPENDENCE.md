# Provider independence + MiniMax H3 (research, 2026-11-09)

Status: PROPOSAL. Nothing is built. film05 (P17-01) keeps running on Flow and is not touched by this proposal.

## 1. MiniMax H3: what it offers

Source: the official docs at platform.minimax.io:
- `docs/api-reference/video-generation-v2-create`
- `docs/guides/video-generation`
- `docs/pricing/overview`

**API shape**
- Async REST.
  - Create: `POST https://api.minimax.io/v2/video_generation`, which returns `task_id`.
  - Query: `GET .../v2/query/video_generation/{task_id}`. It returns a status of `queued`, `running`, `succeeded`, `failed` or `cancelled`, plus `content.url` and `usage`.
  - Auth: `Authorization: Bearer`.
- Inputs go in a `content[]` array. Each item has a `role`:
  - `first_frame`, and `last_frame` (which must be paired with a first frame);
  - up to 9 `reference_image`, 3 `reference_video` (≤15 s in total) and 3 `reference_audio` ("voice timbre follows reference audio").
  - Image-to-video roles and reference roles cannot be mixed in one request.
- Prompt: at most 7000 characters. Camera tags such as `[pan]`, `[zoom]` and `[static]` go inline.
- Duration is 4–15 s (5–15 s for H3-Max). No seed field is documented.
- Ratio: 16:9, 9:16, adaptive and others.

**Models and prices (USD per output second)**

| Model | Resolutions and price | Notes |
|---|---|---|
| H3 | 768P $0.08 · 2K $0.13 | Quality model |
| H3-Highspeed | 480P $0.04 · 768P $0.06 | |
| H3-Lite | 480P $0.025 · 768P $0.04 | |
| H3-Max | 480P $0.05 · 768P $0.08 | Multi-reference |

- An 8 s test clip on Lite 480P costs about **$0.20**.
- Failed tasks and moderation rejections are **not charged**. A rejection is HTTP 422, code 1026, at create time, or a `failed` task at query time.
- Rate limits for H3 are not published.

**Unconfirmed, and decisive for drama**
- The docs do not say whether the output video carries **native audio, spoken dialogue and lip-sync**.
- Our drama route depends on dialogue audio in the take; `dialoguecheck` reads the dialogue stem.
- If H3 returns silent video, dialogue shots need a separate TTS and lip-sync stage, which is a large addition. If so, H3 is first useful for non-dialogue shots: inserts, reactions, establishing shots and action.

### Vilao (vilao.ai), read 2026-11-09 from the model list, the model page and docs/api-reference

Vilao is a **P2P marketplace**, not MiniMax itself. Independent sellers resell models behind one OpenAI-compatible gateway. The site itself warns that the same model differs in quality from one seller to another.

**Video API**
- Gateway endpoints (OpenAI Videos shape):
  - `POST https://api.vilao.ai/v1/videos`
  - `GET /v1/videos/{id}?model=…`
  - `GET /v1/videos/{id}/content?model=…`
- Per-seller endpoint, e.g. H3 seller OMNiBiU: `POST https://api.vilao.ai/p/omh3/v1/videos`, with `"model": "h3-480p"`.
- Auth: `Authorization: Bearer <VILAO_KEY>`.
- A zero balance blocks a request before it reaches the provider.
- Errors: 402 balance, 403 model access, 404, 429 rate limit, 5xx.

**Pricing:** per request, in VND, with no per-second price shown. Requests and success rates are the marketplace's own figures at the time of reading.

| Model | Seller | Model id | Price/request | Requests | OK |
|---|---|---|---|---|---|
| Minimax H3 480P ("5 modes", 5–15 s) | OMNiBiU | `h3-480p` | 4.158 ₫ (−10% promo, list 4.620 ₫) | 10 | 70% |
| Minimax H3 768P | OMNiBiU | `h3-768p` | 5.198 ₫ | 0 | — |
| Minimax H3 1088P ("image refs + optional audio") | OMNiBiU | `h3-1088p` | 6.930 ₫ | 0 | — |
| Minimax H3 1440P | OMNiBiU | `h3-1440p` | 10.395 ₫ | 0 | — |
| Veo-3.1 | Codex | — | 3.000 ₫ | 3.3K | 84% |
| gemini-omni-flash-preview | Codex | — | 5.000 ₫ | 283 | 89% |
| Omni Flash | tech-ccmax ("acc") | — | 3.400 ₫ | 36 | 33% |
| Seedance 2.5 | tech-ccmax | — | 13.000–46.500 ₫ (5–30 s) | ~0 | — |

Also listed: Grok Imagine Video, and Higgsfield character swap.

**Unknown until a probe**
- How this seller maps first frame, last frame, reference images and reference audio onto the OpenAI-shape body.
- Whether output has audio or dialogue.
- Whether a failed request is charged.
- Rate limits.
- Where our uploaded stills go: the seller is a third party.

**Risk**
- Sellers tagged "acc" are likely shared provider accounts, so supply and terms-of-service status can change without notice.
- Low request counts mean reliability is unproven.
- For these reasons Vilao is treated as a **second provider route behind the adapter**, not as a replacement for Flow.
- Reaching MiniMax's official API directly (§1 above) stays the stable fallback.

The key lives in an environment variable (`VILAO_API_KEY`) and is never committed.

### Fit against our pain points

| Pain with Flow today | H3 via API |
|---|---|
| UI automation is fragile: picker, upload, avatar column | REST plus `task_id`; no UI |
| A send whose result can't be matched to a take (AMBIGUOUS binding, `flow_reconcile`) | `task_id` binds the take exactly |
| FLOW_FAILED cancellations | `failed` with an error code, not charged |
| Character identity drifts between shots | Up to 9 reference images per request (to be measured) |
| One send at a time through one browser profile | Several tasks in parallel; limits unknown |
| Credits and quota tied to one account | Pay as you go |

## 2. Coupling today (repo audit)

- **No interface in the send path.**
  - `generate.py` shells out to `tools/drama_flow_ui/flow_send.py` (`generate.py:199-215`, `:69-72`).
  - `providers/base.py:19 VideoProvider` already has the right shape (`capabilities`, `preflight`, `submit`, `poll`, `fetch_outputs`, `cancel`), but nothing in production uses it.
- **Hard-coded to Flow:**
  - `generate.py:47-50`: `ROUTE` is "start_frame+Khung hinh" and `MODEL` is "Omni 1.2 Flash 360p".
  - `planning.py:39-43` `flow_credits()` is the only price function.
  - `planning.py:35` still uses 12 cr/generation, the Omni 1.1 basis.
- **Result taxonomy is Flow vocabulary.** `PRE_SUBMIT_RESULTS` and `FLOW_FAILED_RESULTS` in `generate.py:238-300` are defined in Flow terms. The ledger also rules FLOW_FAILED as spent.
- **Generability is global and tied to one model.** `drama/generability.py` asks whether "Omni 1.2 Flash" can do the beat.
- **The data model has no `provider` or `provider_job_id`.**
  - `TakeEntry` (`takes.py:37-50`) and the intent receipts have only a free-text `model`.
  - `generators.py` and `deliver.py` take the first word of a free-text string as the provider.
- **Stills are tied to ChatGPT and not abstracted.** `stills.py` is only a record-keeper.

## 3. Target architecture

Rule: shared code speaks in **shots, frames, references, seconds and money**. Only an adapter speaks a provider's language.

1. **`GenerationRequest`** (provider-neutral), built by `generate.py` from the shot declaration:
   - prompt (neutral text);
   - duration;
   - aspect;
   - resolution tier (TEST or FINAL, not "360p");
   - `first_frame` and `last_frame` (file and sha);
   - `references[]` (character, look, voice), each with a role;
   - `audio_mode` (NATIVE_DIALOGUE, SILENT, AMBIENT).
2. **Adapters implement the existing `VideoProvider`.**
   - `FlowUiAdapter` wraps today's `flow_send.py` with no change in behaviour, proven by the current tests and the film04 rehearsal.
   - `MiniMaxAdapter` uses REST: submit, then poll, then download to `takes/`, recording the sha.
   - `VilaoAdapter`, if Vilao is only a gateway, is the same adapter with a different base URL and model map.
3. **Capability registry as data, not code**, for example `providers/registry/*.json` with one entry per provider and model:
   - duration range;
   - resolution tiers mapped to native values;
   - frame roles supported;
   - maximum references;
   - `native_audio`;
   - prompt dialect: language, camera tags, length limit;
   - price function: per second, per credit, or tiered;
   - error-code mapping.

   Preflight checks each shot against the chosen model's capabilities, and blocks before any spend.
4. **Normalized results.** Every adapter maps its own outcomes onto one set:

   | Result | Meaning |
   |---|---|
   | `NOT_SUBMITTED` | Zero cost |
   | `REJECTED_POLICY` | Moderation rejection |
   | `PROVIDER_FAILED` | The provider failed the task |
   | `AMBIGUOUS` | Flow only |
   | `PASSED` | Output received |

   Whether each result is charged comes from the registry, not from an `if` in the ledger.
5. **Money ledger.** The film budget carries a currency per provider: Flow credits, USD. Each take records `cost{amount, unit, provider}`. The caps from OWNER_POLICY apply per unit.
6. **Data model.** Add `provider`, `model` and `provider_job_id` to `TakeEntry`, intents and receipts, with Flow as the default so old films still read. Binding:
   - the API path binds by job id;
   - Flow keeps binding by prompt text and media id.
7. **Generability per model.** Ratings and evidence are keyed `(provider, model)`. A new model starts at **UNKNOWN**, so the existing rule applies: one exploratory send, then review. Film04 evidence stays attached to Omni 1.2 Flash.
8. **Routing.**
   - `film.json` sets a default `route` (provider + model + tier).
   - A shot may override it. Example: dialogue on Flow, inserts and reactions on H3.
   - Preflight refuses a route whose capabilities do not cover the shot. Example: dialogue shot on a SILENT model.
9. **Prompt compiler dialect layer.** The placement and interaction clauses (P16) stay shared. A thin per-provider renderer handles tags, length and phrasing.
10. **Stills.** Use the same pattern later, with ChatGPT web, Flow image and API image models as adapters. Not urgent, since stills already work.

## 4. Parallel plan (does not disturb film05)

Feature freeze (P17) is respected. Phase A is built in its own worktree and branch, and merges only after P17-01 reports.

| Phase | Work | Cost | Gate |
|---|---|---|---|
| A (offline) | Items 1–6 above. FlowUiAdapter has identical behaviour (existing tests and rehearsal stay green). MiniMaxAdapter tested against a mock server. Registry entries for Omni 1.2 Flash and H3 Lite/Highspeed. | 0 | Tests green; diff reviewed by Codex read-only |
| B (live probe) | 3–5 Vilao `h3-480p` sends (≈4.2k ₫ each, ≈20–25k ₫ total) reusing film04 approved stills: first frame, first+last frame, reference images (identity), and one dialogue line (audio?) | ≈ 25k ₫ | **Owner:** Vilao key + top-up |
| C (A/B) | 4 film04 shots on H3 vs the accepted Flow takes, same review checklist | ≈ $2–5 | Results decide routing |
| D | Per-shot routing in film06 | — | After P17 verdict |

Phase B answers the native audio question. If H3 is silent, it is routed to non-dialogue shots until a TTS and lip-sync stage is decided. That stage is a product decision for the Owner.
