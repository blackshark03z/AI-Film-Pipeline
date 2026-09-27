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
