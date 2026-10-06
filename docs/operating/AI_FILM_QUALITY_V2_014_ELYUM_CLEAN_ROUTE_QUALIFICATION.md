# AI FILM QUALITY V2-014 — ELYUM VIDEOPROVIDER PORT + CLEAN-OUTPUT QUALIFICATION

Slice: `AI-FILM-QUALITY-V2-014` · Start HEAD `6cf4128` · Lifecycle BOUND → BUILD → PROVE
**VIDEO MUTATIONS = 0/1 (UNSPENT)** — the canary was frozen but NOT dispatched: the pre-dispatch
credit gate failed closed (cheapest provider-quoted configuration 56 credits vs a 30-credit balance).

## Final state

```
STATUS                    = STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH (engineering COMPLETE)
ELYUM_ADAPTER             = QUALIFIED_LOCAL (ported from the live-proven Story Auto source; 16/16 tests)
ELYUM_CLEAN_MASTER_ROUTE  = NOT_PROVEN (watermark verdict requires a render; none affordable)
CURRENT FILM ASSETS       = UNCHANGED (F2 ada66463…, proof 63eac46c… recomputed; SEQ_CONTEXT_LOCK GRANTED)
```

## Phase 0 — source authority

Story Auto repo `D:/Story Auto/story-auto` @ `5464cbb` — `story_auto/providers/elyum_seedance/`
(client 426 lines, service 752, plus research/opening). Provider contract recorded verbatim:
`elyum_account` / `elyum_models` / `elyum_estimate` (read-only), `elyum_make_video` (one job,
idempotent clientRef), `elyum_wait`/`elyum_job_status` (durable jobId), `elyum_keep` (the only
documented credit-spending action — unlocks the downloadable original), `elyum_kill`.
Classification per piece in `V2_014_ELYUM_SOURCE_AUTHORITY.json`.

## Phase 1–3 — AI-Film adapter (transport only)

`src/film_pipeline/providers/elyum_provider.py` — the MCP session and client semantics ported
verbatim (failure-class taxonomy included); credential loader adapted (env `ELYUM_API_KEY` →
Owner key file; value never logged/persisted); clientRef builder
(`aifilm-v2014-<sha48>`); download (https-only, size-capped, sha256-bound). Film Core sees only
capabilities/preflight/submit/poll/fetch_outputs/download — MCP wire format, auth and URL
semantics never leave the module. `cancel` is intentionally not wired to `elyum_kill`.

## Phase 4 — capability discovery (live, read-only — auth PROVEN)

```
balance: 30 credits (read-only elyum_account)
catalog: 16 Seedance model ids — dedicated t2v family exists
         (seedance-2-{fast,t2v,mini}-{t2v,i2v,reference}, seedance-2.5 family)
pricing matrix (elyum_estimate, provider-quoted, read-only):
  mini  t2v/i2v  2s/3s/4s/5s @480p = 56 credits (duration-invariant at this tier)
  fast  t2v/i2v  2s/3s/4s/5s @480p = 80 credits
  base  t2v      5s @480p/720p/1080p = 145 credits; fast 5s @720p = 100
480p/4s in Story Auto were DEFAULTS, not limits: schema 2..30s, {480p,720p,1080p},
and every quoted combination was provider-accepted for costing
```

## Phase 5 — adapter tests: 16/16 PASS

`tests/test_v2_014_elyum_provider.py` (deterministic MockToolSession, no network): auth injection
without secret persistence · request translation (t2v + i2v reference rule) · clientRef
stability · nested job/gen identity · poll transitions · pre/post-keep output extraction ·
duplicate absorption · sha256 download binding · https-only enforcement · timeout mapping ·
provider failure-class matrix (401/403/429/422/500/418) · malformed responses · missing-jobId
fail-closed to RECONCILE_BY_CLIENT_REF · restart recovery (stable clientRef + idempotent replay)
· secret redaction. The tests caught and fixed a real port regression (`_collect_urls`
list-branch).

## Phase 6 — canary: frozen, NOT dispatched

The benign canary (empty windswept mountain pass, no people/text/logos; t2v,
`seedance-2-mini-t2v`, 4s/480p — the cheapest provider-quoted configuration) is frozen with a
stable idempotent clientRef in `V2_014_CANARY_REQUEST.json`. Pre-dispatch credit gate: the
cheapest configuration quotes **56 credits against a 30-credit balance**; every model tier
(mini 56 / fast 80 / base 145) is duration-invariant at 480p. Dispatch would fail closed —
the mutation was NOT spent.

## Watermark + clean route

```
ELYUM_WATERMARK  = UNPROVEN (no render exists to inspect)
ELYUM_ADAPTER    = QUALIFIED_LOCAL
ELYUM_CLEAN_MASTER_ROUTE = NOT_PROVEN
```

Production readiness matrix: TRANSPORT PROVEN · IDENTITY PROVEN · AUTH PROVEN · WATERMARK
UNPROVEN · RESOLUTION QUOTED_UNPROVEN · DURATION QUOTED_UNPROVEN (price is model-tier-driven,
duration-invariant) · COST PROVEN · RESTART_RECOVERY PROVEN · AI_FILM_INTEGRATION PROVEN.

The adapter bug the tests caught: `_collect_urls` list-branch regression
(UnboundLocalError) — fixed and covered by the dedup test.

## Unblocking (Tech Lead)

The frozen clientRef dispatches the SAME canary (idempotent) the moment the Elyum balance
covers the floor:
- Owner tops up Elyum credits (≥ 56 for the mini tier; ≥ 80 for the fast tier), or
- a cheaper tier appears in the catalog (re-run discovery, read-only), or
- the official Seedance API route (V2-013: MEDIUM cost) proceeds independently.

Then phases 7–9 (technical QC + watermark verdict + route classification) complete unchanged.

**STOP — return to Tech Lead.** No regeneration, no film rebind: F1R/F2/F3R/proof untouched.
