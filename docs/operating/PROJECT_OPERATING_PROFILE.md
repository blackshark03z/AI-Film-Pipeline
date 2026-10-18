# Project Operating Profile — AI Film Pipeline

**Status:** FROZEN FOR V1 EXECUTION  
**Governing lifecycle:** AI-Native Development Model SoT v1  
**Product/System SoT:** AI Film Pipeline V1 SoT

## 1. Purpose

This file binds the generic AI-Native Development Model to this repository.

It is not a new lifecycle layer.

## 2. Canonical truth mapping

### PRODUCT TRUTH
Primarily represented by:
- Film SoT `01_SCOPE_AND_PRINCIPLES.md`
- Film SoT `03_CINEMATIC_CONTROL_SPEC.md`
- Film SoT `09_EDITORIAL_FLOW.md`
- Film SoT `10_VERTICAL_SLICE_BENCHMARK.md`

Product truth includes:
- coherent film sequence over isolated pretty clips;
- continuity-aware AI generation;
- cinematic/directorial intent;
- practical cost/quality balance;
- ability to replace generation providers.

### SYSTEM TRUTH
Primarily represented by:
- Film SoT `00_SOT_INDEX.md`
- Film SoT `02_CANONICAL_DOMAIN_MODEL.md`
- Film SoT `04_SHOTSPEC_V1.md`
- Film SoT `05_PROMPT_COMPILER.md`
- Film SoT `06_PROVIDER_CAPABILITIES.md`
- Film SoT `07_ROUTING_REPAIR_QC.md`
- Film SoT `08_ASSET_LINEAGE_COST.md`
- JSON Schemas under `/schemas`

Hard invariants include:
- ShotSpec / Film State is canonical; provider prompts are derived.
- Continuity is explicit data.
- Creative state is separated from runtime/provider state.
- Provider transports are replaceable adapters.
- Browser/cookie state never enters Film Core.
- Exact GenerationAttempt → ProviderJob → Asset lineage is required.
- No blind retry except genuinely transient transport retry.
- Filesystem + JSON/SQLite is the V1 persistence baseline.
- DaVinci Resolve remains finishing truth.
- Model IDs/pricing/capabilities are runtime config/evidence, not Film IR.

### CURRENT SLICE
Represented only by:
- `CURRENT_SLICE.md`

The worker may not redefine acceptance inside an attempt.

## 3. Role mapping

### Owner
Owns:
- product intent;
- real quality/cost trade-offs;
- subjective film acceptance;
- consequential external authorization.

### Tech Lead
Owns:
- SHAPE/BOUND/SLICE;
- preserving SoT;
- acceptance semantics;
- proof custody;
- deciding whether evidence warrants a truth delta.

### Worker
Owns:
- implementation HOW inside Current Slice;
- code structure;
- local refactoring;
- local tests;
- replaceable library choices;
- internal progression through pre-authorized gates.

### Trusted Verification
May be:
- protected tests/checks;
- exact revision identity;
- GitHub branch protection/CI;
- provider readback;
- manually reviewed evidence outside candidate authority.

## 4. Work style

Default:
- larger bounded work packages;
- fewer manual relays;
- worker self-progresses through internal gates;
- stop only at meaningful boundary or authority requirement.

Worker SHOULD search/reuse before building:
`SEARCH → REUSE → COMPOSE → ADAPT → EXTEND → BUILD LAST`

Existing `AutoVideoPipeline` is a reuse/reference source for Flow/Veo and media mechanics, not the canonical architecture.

## 5. V1 implementation posture

Prefer:
- Python;
- Pydantic;
- JSON Schema;
- SQLite;
- filesystem;
- CLI;
- FFmpeg;
- provider adapters.

Do NOT introduce by default:
- Postgres;
- Redis;
- Temporal;
- S3;
- Kubernetes;
- microservices;
- complex web UI;
- local Stable Diffusion / ComfyUI;
- Blender/Unreal;
- fine-tuning;
- custom orchestration framework.

Any deferred component requires measured evidence of need.

## 6. Provider reality

Available practical execution paths:
- Gemini API.
- Google Flow / Veo.
- Seedance via Dola.
- Seedance via Elyum.
- ChatGPT Plus / Codex for development and difficult interactive reasoning.

Browser/cookie automation is allowed only behind provider adapters.

## 7. Stop conditions

Worker must stop when:
- owner product decision is required;
- a new external authority is required;
- external state is ambiguous and cannot be reconciled safely;
- a frozen hard invariant would need changing;
- live/consequential action was not pre-authorized;
- secrets or account access are required and unavailable;
- package scope must materially change;
- no-progress/retry limit is reached.

## 8. Change control

If implementation evidence challenges SoT:
1. do not silently change SoT;
2. record evidence;
3. return to LEARN;
4. Tech Lead adjudicates Product/System Truth delta;
5. create a new slice if required.

## 9. Multi-worktree truth, interchangeable worker and MAR (2026-10-18 integration rule)

These are **operating interpretations of the frozen lifecycle**, not a fourth truth type or a new process.

1. **Whole-project view:** Root `CURRENT_SLICE.md` and `IMPLEMENTATION_STATUS.md` are project-level canonical operating references. A subproject/worktree has its own implementation/attempt evidence, but it is not automatically the entire project's current Goal. Historical copies and completed/paused activities must be explicitly distinguished.
2. **Role invariant across runtimes:** The Tech Lead owns SHAPE → BOUND → SLICE, independent acceptance PROVE, LEARN and canonical state promotion. Worker owns BUILD/HOW and operational PROVE within an immutable accepted task. Worker can be OpenCode, Codex, Claude, DeepSeek or another agent. Platform-specific kit skills are optional adapters; never require a Worker to run a named model or orchestrator.
3. **Tech Lead MAR source-of-evidence:** For project continuation, progress assessment, task selection, acceptance and cross-worktree changes, use MAR/MAR2 to read the local **root Git repository plus all relevant linked worktrees**, branch/HEAD/status/diff, SoT, frozen task contracts and newest evidence. The root-plus-worktree inventory is required before using any child branch as project-wide status. Treat snapshot results as observations, not Product Truth.
4. **Canonical update protocol:** Worker sends an exact revision/candidate and facts. Tech Lead independently verifies frozen acceptance, inspects any truth delta, **updates existing project state and remaining blockers**, and only then creates/revises the next root Current Slice. A worker must never edit Product/System Truth or acceptance to make its own candidate pass. Reconcile contradictory root/worktree states before task dispatch. Preserve historical evidence rather than rewriting prior outcome.
5. **No concurrent write collision:** A current Worker owns its isolated worktree. Tech Lead edits only its scoped operating documentation in the root with Git-status/path/hash checks and must not alter the Worker's branch or dirty mission files while a run is active. Promote results across branches/worktrees only via explicit reviewed integration, never silently by assuming the latest branch is canonical.
6. **Kit policy:** Apply `CODEX_NATIVE_WORKFLOW_KIT` manifest version 1.2.2 as role-neutral methodology: approved Goal is exit unit; product-first, reuse-first, risk-specific/ship-boundary proof; finite time/retry/no-progress; technical, product and Owner acceptance separately. Its Codex/BMAD/Ponytail/UI-UX/Superpowers-specific tooling is optional and requires actual host capability and permission. Existing Film/Development SoTs outrank all kit templates.

**MAR is not background monitoring:** it supplies read/audit/documentation on Tech Lead invocation. No daemon, remote push, deploy or new governance framework is implied.

### Current tool handoff — OpenCode / DeepSeek V4.1 Flash (Owner direction, 2026-10-18)

For the **currently approved S1 Dola OneClick continuation only**, the Owner selects **OpenCode running DeepSeek V4.1 Flash** as the coding Worker. The Tech Lead prepares the bounded Work Package in the relevant Git worktree and hands the Owner a **copy-ready prompt relay** for that OpenCode session. **Do not dispatch an MAR worker task** or change this into an MAR-managed agent. MAR is reserved for Tech Lead's repo-wide inspection, scope-checked file/document writes and independent readback; it is not the Worker executor.

This is an **execution adapter choice**, not a replacement policy, new SoT, changed Goal or compulsory future Worker model. `POLICY_REF=45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` remains the sole accepted agent policy; the Worker independently runs its Git policy preflight before BUILD. The frozen S1 A1–A8 contract still wins; Chrome cookie capture/login and GPM live launches require explicit Owner action. Tech Lead owns the final Product Progress Gate and acceptance. For a subsequent Worker change, update only the bounded handoff, not the pinned policy.
