# Decision Log — V1 Freeze

## 2026-10-25 — Owner decision: compare ComfyUI before considering a new BUILD

**2026-10-25 operational authorization clarification (no Film SoT change):** Owner authorizes a [bounded, up-to-eight-hour OFFLINE ONLY controlled-shot prototype](../../operating/TASK_XIANXIA60_CONTROLLED_SHOT_OFFLINE_8H_20261025.md) to test a proposed additive contract in an isolated worktree. This is **not** approval of a production engine, revised X04 story, reference binding, any real GPU/provider/render spend, deployment or film-resumption; all frozen DRs and creative Owner Pause prevail. See the [single research dossier](../../research/CHINA_AI_FILM_WORKFLOWS_FOYEGE24_COMFYUI.md) for evidence and three subsequent Owner gates.

**Single research evidence item (not SoT):** [Foyege24 / Chinese ComfyUI workflow audit](../../research/CHINA_AI_FILM_WORKFLOWS_FOYEGE24_COMFYUI.md). Future rounds update this file only; V1 freeze and Owner Pause remain.

**Research permission, not architecture adoption:** Owner requests a read-only comparison of the present AI-Film-Pipeline with concrete Chinese-language ComfyUI filmmaking workflows before deciding a new implementation round. This does not authorize ComfyUI setup, model download, workflow execution, GPU/provider use, media generation, or changed architecture.

**Frozen V1 decisions still apply:** DR-001/002/003 (Film State/ShotSpec, continuity, replaceable adapters), DR-006 (no blind retry), DR-009 (ComfyUI/image-first is optional and deferred), local-first persistence and Resolve finishing are not superseded. Research evidence alone cannot promote a new Film/System Truth.

**Future evidence gate:** Inspect real workflow graphs/JSON and verify licensing/provenance; compare character identity, two-person blade contact, pose/depth/keyframes, blocking/eyelines, shot continuity, generation quality, costs/GPU and integration with QC/lineage against one identical XIANXIA60 combat shot. Tech Lead presents a bounded candidate experiment; only separate Owner approval can authorize BUILD, generation, spending or a revised SoT.

**Film remains:** `DEVELOPMENT=PAUSED_BY_OWNER / OWNER_CREATIVE_ACCEPTANCE=REJECTED / FILM_RELEASE=NOT_SHIPPED`. The narrow requested desk research is not production resumption. See canonical operating `CURRENT_SLICE.md` and `IMPLEMENTATION_STATUS.md`; prior budgets are historical and grant no new spend.

---

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

### DR-013 — Provider-native UI automation can be a qualified production mutation boundary
A real headful browser driving the provider-native Flow UI may be used as the production mutation transport when the exact account/profile/project/build/model/mode scope is empirically qualified. The provider frontend must construct its own live session/security/request state; the system must not substitute a private direct mutation replay. In the 2026-10-02 clean-scope qualification, two distinct automated native-UI Flow generations completed with unique durable attribution and valid acquired media, so a manual human click is not a Film-Core requirement.

### DR-014 — Admission, rendering and acquisition are separate provider states
An admitted generation can still fail during rendering. A mutation HTTP response, candidate identity, optimistic provider state or UI progress does not imply a completed Asset. Runtime state must distinguish admission, render pending/completed/dropped and acquisition. Retry authority is never inferred from a render/media miss; RepairDecision and ambiguity rules still apply.

### DR-015 — Flow qualification is scope-bound; security and prompt hypotheses do not become architecture truth
Current successful Flow requests expose provider-generated browser/session/security context and a current Veo 3.1 request fingerprint, but these observations do not prove a single universal admission discriminator. reCAPTCHA presence, trusted-event telemetry, account risk/entitlement hypotheses and prompt-deduplication hypotheses remain diagnostic evidence unless separately isolated. No raw cookie/auth/CAPTCHA/signed-URL material belongs in committed SoT/evidence, and no current Flow qualification transfers automatically to another account/project/build/model/mode.

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
