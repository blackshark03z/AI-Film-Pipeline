# Decision Log — V1 Freeze

## FROZEN

### DR-001 — Film State / ShotSpec over prompt-as-truth
Provider prompts are compiled artifacts.

### DR-002 — Continuity is first-class data
Character, world, prop, eyeline, screen direction and start/end state are explicit.

### DR-003 — Provider-neutral core
Flow/Veo, Dola and Elyum are adapters.

### DR-004 — Local-first persistence
Filesystem + JSON/SQLite.

### DR-005 — Resolve finishing truth
FFmpeg supports rough assembly and utilities.

### DR-006 — No blind retry
QC failure produces RepairDecision.

### DR-007 — Current minimum stack first
Use available Gemini API + Flow/Veo + Seedance transports before buying/building more.

### DR-008 — Browser/cookie automation isolated, not forbidden
Current reality requires it. It is a replaceable transport with preflight, correlation and failure isolation.

### DR-009 — Image-first is optional
Local Stable Diffusion/ComfyUI is unavailable. The architecture supports future image/keyframe providers without requiring them now.

### DR-010 — Volatile private provider contracts require reverse-qualification on ambiguity
Undocumented/browser-backed provider contracts are versioned observations, not permanent APIs. A historically proven Flow/Dola/Elyum path may drift at the request, response, catalog, model, reference or session layer without a stable migration notice. When a provider path becomes ambiguous, fail closed: preserve the consumed attempt, reconcile read-only where safe, then reconstruct the **current successful provider operating path** from live evidence before changing the adapter. Do not fix Film Core around stale provider quirks and do not use blind retries to discover a changed contract. Re-qualification requires a bounded canary and a new observed contract/fingerprint before production routing resumes.

### DR-011 — Mutation admission is separate from output truth
For browser-backed providers, the transport that can admit a mutation and the transport that can observe/reconcile provider state may differ. A provider-native UI action may therefore be an acceptable replaceable mutation boundary while durable backend catalog/media evidence remains the canonical source of acceptance and output ownership. A click, observed outbound request, HTTP success, visible progress state or gallery tile is never enough to authorize retry or assign an output. If the backend effect is not uniquely attributable, preserve the consumed dispatch and fail closed.

### DR-012 — Provider reference identity requires immutable attestation
A canonical Film reference asset may condition generation only after its provider media identity is independently bound and content-verified within the intended provider/account/project scope. Historical receipts, filenames and prior mappings are evidence to investigate, not sufficient proof. Reference mismatch or unresolved binding blocks mutation; do not silently substitute or re-upload to escape ambiguity.

## SUPERSEDED

### Old heavy infrastructure V1
`Postgres + Redis + Temporal + S3 + web backend` is not V1 baseline.

### Mandatory ComfyUI / local image stack
Removed from V1.

### Mandatory approved keyframe before every video shot
Removed. Use when/if an available provider supports a useful reference workflow.

### Hard-coded model/version names from research reports
Superseded. Runtime config only after verification.

### Hard-coded provider pricing from old reports
Superseded. Operational benchmark/config only.

### "Official API only" as architecture requirement
Superseded for the current operator environment. Official APIs remain preferable when available, but browser/cookie transports may be used behind adapters.

### Multi-agent film crew
Deferred. One primary automated LLM path plus optional human/strong-model review is sufficient for V1.

## DEFERRED

- 3D/Blender/Unreal;
- LoRA/fine-tuning;
- local video models;
- distributed queue/orchestrator;
- object storage;
- web studio;
- sophisticated automatic VLM hard gates;
- full rights/provenance compliance automation;
- self-host GPU economics.

## VERIFY / BENCHMARK, NOT ARCHITECTURE BLOCKERS

- exact current Veo model/tier behind Flow;
- exact Seedance model/tier exposed by Dola/Elyum;
- supported reference/start/end-frame capabilities of each transport;
- actual cost attribution under subscriptions/credits;
- approval rate by shot class;
- latency and failure rate;
- whether Codex/ChatGPT should ever be integrated into runtime beyond development workflows.

## Open decisions allowed after freeze

Only these remain intentionally open:
1. empirical Veo vs Seedance routing weights;
2. provider capability profiles as transports evolve;
3. runtime model IDs;
4. cost tables;
5. future image provider choice.

None of these block repository implementation.
