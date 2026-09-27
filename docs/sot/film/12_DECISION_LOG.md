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
