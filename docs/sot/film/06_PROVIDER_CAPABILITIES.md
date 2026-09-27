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
