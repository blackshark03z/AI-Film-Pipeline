# Provider Capability Contract

## Current provider transports

V1 recognizes practical transports, not marketing assumptions:

```text
flow_veo
seedance_dola
seedance_elyum
```

Exact model names/versions are runtime configuration and must be verified when used.

## Required adapter interface

```python
class VideoProvider:
    def capabilities(self) -> ProviderCapabilities: ...
    async def preflight(self) -> ProviderHealth: ...
    async def submit(self, request) -> ProviderJob: ...
    async def poll(self, provider_job_id) -> ProviderStatus: ...
    async def fetch_outputs(self, provider_job_id) -> list[ProviderOutput]: ...
    async def cancel(self, provider_job_id) -> None: ...
```

Optional:
```python
def estimate_cost(self, request) -> CostEstimate | None: ...
```

## ProviderCapabilities

Capability profile is data and versioned.

```text
supports_text_to_video
supports_image_input
supports_start_frame
supports_end_frame
supports_multi_reference
supports_seed
supports_native_audio
supports_duration_control
supports_aspect_ratio
supports_resolution_control
supports_negative_prompt
supports_batch
supports_cancel
supports_stable_external_job_id
transport_type
```

## Browser/cookie transport rule

Flow/Dola/Elyum browser/session automation is allowed as a **replaceable adapter** because it is part of the operator's current viable stack.

However:

- Film Core never stores cookies.
- Sessions are provider-local secrets.
- Expiry means provider health failure, not corrupted project state.
- Every attempt must have an internal `provider_job_id`.
- If a stable remote job ID exists, store it as `external_job_id`.
- If not, create deterministic correlation evidence (submission timestamp, project/session binding, prompt/input hash, discovered remote asset ID).
- Never select "latest output" without correlation evidence.
- Never use UI/gallery ordering as canonical identity.

## Provider contract drift / reverse-qualification rule

Private, browser-backed and undocumented provider contracts may change without notice, including RPC identifiers, request/response envelopes, model IDs, reference encoding, session/account routing, capability flags and catalog schemas.

Therefore a provider adapter is qualified against an **observed contract version**, not assumed to be permanently valid. The adapter/runtime evidence should retain, where available:

```text
qualified_at
contract_version / observed fingerprint
project/account/session scope
model identifier(s)
request structural fingerprint
response/catalog structural fingerprint
known-good control evidence
```

If a previously qualified path becomes ambiguous (for example: HTTP success without attributable output, parser/schema drift, null/empty provider payload, identity mismatch, or UI/manual success while the adapter fails):

1. **STOP provider mutation and blind retries.** Preserve the exact attempt, request hashes, baseline and ambiguity evidence.
2. **RECONCILE read-only first** against durable provider state when safe.
3. **REVERSE THE CURRENT WORKING PATH** from an actually successful provider/UI/control execution. Compare wire/request/response/session/model/reference/catalog semantics against the last qualified adapter.
4. **VERSION THE DELTA** as a provider-contract change. Adapt only the provider layer; do not rewrite ShotSpec/Film State to match provider drift.
5. **RE-QUALIFY with one bounded canary** before restoring production routing.
6. If the current contract cannot be uniquely established, keep the provider capability degraded/unavailable and route elsewhere rather than guessing.

Historical Story Auto / AutoVideoPipeline paths are reusable evidence and implementation references, but are never proof that a private Flow/Dola/Elyum contract remains current.

## Flow/Veo current qualified transport split (2026-10-02 evidence)

The current Flow/Veo V1 production candidate is now **qualified within one explicit clean scope** as a provider-native UI automation route plus durable backend reconciliation. This qualification is recorded in `13_FLOW_NATIVE_UI_QUALIFICATION.md` and derives from evidence commit `29018d3340b85ade788b3aec2963496036cddbe9`.

### Qualified mutation path

- Real Google Chrome, headful, using an isolated authenticated profile.
- Provider-native Flow UI controls the current frontend/session/security/request construction.
- Current proven mode: reference-conditioned Video → Ingredients with observed wire model `veo_3_1_r2v_lite`, 16:9, x1.
- The adapter releases Generate at most once per durable attempt/job.
- Two distinct fresh automated UI generations completed, were uniquely attributed, acquired and full-decoded successfully in the qualified scope.
- Therefore manual human clicking is **not** a required invariant for this qualified route.

### Qualified observation / reconciliation path

- `Zzl0ze` remains a qualified read-only catalog/reconciliation surface.
- `as29s` remains a qualified read-only media-resolution surface after the exact media identity is independently bound.
- `maseQ` reference upload remains an observed in-page capability, but uploaded media still requires independent identity/content attestation before use.
- A unique Film marker echoed in a fresh backend catalog delta, combined with exact project/reference binding and unique provider media identity, is acceptable ownership evidence.
- UI/gallery order, newest-card selection and filename coincidence remain forbidden.
- `as29s` may surface duplicate identical URL slots for one exact media resource; identical normalized duplicates may be deduplicated only after independent media/project binding.

### Admission is not render completion

Current evidence proves a distinct lifecycle:

```text
provider-native UI dispatch
→ admission/candidate identity
→ render pending
→ render completed
→ media resolution
→ acquisition/QC
```

One bounded release was admitted and received a unique provider candidate but did not finish rendering. Therefore:

- HTTP 200, optimistic `CAE`, request observation or visible render progress are not completion truth;
- `as29s` may be temporarily unavailable/NOT_FOUND while a render is still pending;
- an admitted render that later disappears/fails is classified separately from an admission failure;
- a temporary media miss never authorizes blind redispatch.

### Current observed request fingerprint

Successful current Veo 3.1 native UI executions exposed a request shape with plain prompt AST in slot 0, reference media binding in slot 1 and the current wire model identifier in slot 2. The older inline reference-entity prompt shape is not the current qualified Veo 3.1 R2V fingerprint.

This request layout is **volatile provider-contract evidence**, not Film-Core truth. Keep exact slots/model IDs/version fingerprints in the adapter/runtime qualification layer.

### Security/session observations are not frozen causal claims

Successful native UI executions contained provider-generated browser/session/security context, including fresh reCAPTCHA Enterprise material, and automated native UI telemetry observed trusted browser events. These facts are diagnostically relevant but the experiment did not isolate them as the sole/root admission discriminator.

Therefore:

- do not hard-code or persist reCAPTCHA/security tokens;
- do not treat `isTrusted` as an architectural admission requirement;
- do not convert the native UI route into direct/private `MZZa6b` replay;
- do not claim historical null responses were caused solely by reCAPTCHA, request AST, account risk, entitlement or any other single factor without separate causal evidence.

### Prompt/render-drop non-claim

A near-duplicate prompt preceded one admitted-but-dropped render, while a later distinct prompt completed. This is **not sufficient evidence** to freeze a provider prompt-deduplication rule. Treat prompt deduplication as a hypothesis only until independently reproduced.

### Scope boundary

The current route is qualified only for the observed account/profile/project/frontend-build/model/mode state. It does not automatically qualify older accounts/projects, other Flow builds, other Veo models/modes, other aspect/output configurations, or future provider versions.

Any material scope or contract change triggers bounded re-qualification before production mutation resumes.

- Two continuity mechanisms remain evidenced behind the adapter: reuse the same verified reference media for identity/look continuity, and use a verified extracted last frame as a new reference for tighter frame continuity. These are provider capabilities, not Film-Core semantics, and remain versioned/qualified.

### Reference attestation rule

Before a provider reference can condition a generation, persist and verify an immutable chain:

```text
canonical Film asset_id + local SHA-256
→ provider account/project scope
→ provider media_id
→ response/resource binding for that exact media_id
→ readback bytes SHA-256 + content verification
→ immutable attestation/evidence hash
```

A filename, historical receipt, gallery position, adjacent catalog row, or previously claimed provider ID is never sufficient. A mismatch or unbound readback blocks mutation and enters ambiguity handling; do not repair by blind re-upload.

## Current stack policy

### Gemini API
Primary automated LLM path for structured planning, compilation assistance and QC assistance.

### ChatGPT Plus / Codex
Development and difficult interactive reasoning resource.
Do not design Film Core around undocumented runtime access.

### Flow/Veo
Primary video path available now.
Reuse proven session/preflight/batching/download mechanics from `AutoVideoPipeline` where useful, behind the new provider interface.

### Seedance via Dola/Elyum
Alternate video paths.
Implement independent adapters so one transport can fail without affecting canonical state.

### Image generation
No required V1 provider.
The interface may be added later without changing ShotSpec semantics.

## Runtime configuration

See `config/runtime.example.yaml`.

No API key, cookie or session material belongs in committed config.
