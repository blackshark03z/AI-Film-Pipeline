# AI FILM QUALITY V2-013 — CLEAN MASTER ROUTE DECISION

Slice: `AI-FILM-QUALITY-V2-013` · Start HEAD `7f68cb6` · **VIDEO_GENERATION_MUTATIONS = 0**
Read-only decision slice: no generation, no asset replacement, no watermark removal, 011W not reopened.

## Decision

```
DECISION = A. KEEP_CURRENT_WATERMARKED_PROOF_ONLY + qualify a clean route before final master

INTERNAL PROOF            = the locked 326-frame watermarked sequence (proof 63eac46c…,
                            SEQ_CONTEXT_LOCK GRANTED) — valid for all editorial/QC/review work
FINAL DISTRIBUTION MASTER = NOT_YET_AUTHORIZED — requires a qualified clean route first
```

## Route evaluation

### ROUTE A — Dola plan entitlement: **NO**

Authenticated UI inspection (ACCOUNT_D + every 011W/013 session on both accounts): the Dola
consumer web app exposes **no plan/subscription/upgrade/billing surface at all** — sidebar,
composer chips, account chip (opens nothing), settings gear (opens nothing), credit mechanics
are a daily allowance announced in chat. `DOLA_PLAN_NO_WATERMARK = NO`; there is no
entitlement layer to enable. Nothing purchased, no URL touched.

### ROUTE B — Elyum: **READY_TO_QUALIFY** (preferred candidate)

From project truth (V2-009 Seedance audit, V2-010A route state, SoT) + the existing Story Auto
implementation (`story_auto/providers/elyum_seedance/`):

| Field | State |
| --- | --- |
| ELYUM_ADAPTER_EXISTS | Story Auto: **YES** (752-line gated service + 426-line MCP client, live-proven) · AI-Film: not built |
| ELYUM_AUTH_STATE | Bearer key present (`D:/API KEY/elyum_api_key.txt`, Owner-managed); MCP endpoint `https://elyum.ai/mcp` |
| ELYUM_SEEDANCE_MODEL_AVAILABLE | `seedance-2-fast-i2v` (Seedance 2.0) live-proven; modes t2v/i2v/ugc/clone; 16:9; 480p default; 4s default (5s is a parameter) |
| ELYUM_OUTPUT_WATERMARK_POLICY | **UNKNOWN/UNVERIFIED** — zero watermark handling in the adapter; the Dola mark is a consumer-web delivery artifact and is not expected on direct API delivery, but unestablished |
| ELYUM_COST_MODEL | credit-based (X2 proof: 20 credits; run cap 44) |
| ELYUM_JOB_IDENTITY_SUPPORT | PROVEN — durable jobId/genId, idempotent clientRef, request_identity_sha256 manifest |
| ELYUM_DOWNLOAD_AUTHORITY | PROVEN — repeated live proofs with durable download |

Classification: **READY_TO_QUALIFY** — not ALREADY_QUALIFIED (no AI-Film adapter; the output
watermark verdict is the single unverified variable), not NOT_READY (nothing missing except
bounded work). Expected qualification work: port the MCP client behind the SoT VideoProvider
interface + ONE bounded watermark-verdict canary (Owner-authorized, 1 mutation, no retry) +
custody wiring.

### ROUTE C — Official Seedance API: **MEDIUM** migration cost

Architecture readiness is high: the SoT mandates the VideoProvider adapter interface and the
replaceable-transport rule; the same ShotSpec→editorial→QC pipeline has already conformed
flow_veo AND seedance assets (transport is data, never domain logic). A future official API
adapter is strictly simpler than the proven browser transport. Blocked only on external
entitlement availability. Not implemented in this slice.

## Why not B/C/D

- **B** (Dola plan can export clean): false premise — no entitlement surface exists.
- **C** (Elyum route is ready): overstated — it is ready to *qualify*; the watermark behavior
  of its outputs is unverified.
- **D** (wait for official API): idles a proven READY_TO_QUALIFY route while adding no
  information.

## Audio finishing plan (plan only — no master rendered)

Inputs: proof `63eac46c…`; measured steps J1 (F1R→F2) **0.8 dB**, J2 (F2→F3R) **8.0 dB**.

1. Ambience bed inventory per unit (spectrum, loudness, wind character)
2. J2 level-match (~8 dB ride or 12-frame ambience crossfade with a matched wind bed); J1 needs
   only a 0.8 dB trim
3. Wind-character continuity pass (one storm bed across both cuts)
4. Loudness normalization to the distribution target (Owner picks −14 LUFS streaming /
   −23 LUFS broadcast) with true-peak cap
5. Render the finishing master in the SAME slice as (or after) the clean-video route
   qualification, so watermark status and audio land together in ONE final mastering pass

Rules: audio is never a cause of video regeneration; original source audio preserved; watermark
untouched by any audio work.

## Locked sequence status

```
modified = NO · watermark = PRESENT · usable as internal proof = YES
clean final master = NOT_YET_AUTHORIZED
```

## Mandatory handoff — STOP

Return to Tech Lead. Proposed next slice: **V2-014** — Elyum adapter port + ONE bounded
watermark-verdict canary; then the rebind/mastering decision. No regeneration or final
mastering begins without a new package.
