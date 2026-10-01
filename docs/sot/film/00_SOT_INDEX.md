# AI Film Pipeline V1 — Source of Truth Index

**Status:** FROZEN FOR IMPLEMENTATION  
**Version:** 1.0.0  
**Scope:** lean/local-first AI filmmaking pipeline for one developer/operator.

## Authority

This package is the authoritative source of truth for V1.

If an older research report, architecture note, repo README, pricing table, model name, or tool recommendation conflicts with this package, **this package wins**.

Older documents remain evidence/history only.

## Source basis

This SoT consolidates the useful production logic from:

- `AI_Film_Production_Target_Architecture_2026-09-21.md`
- `Nghiên cứu sâu về pipeline sản xuất phim bằng AI.md`
- `Phim AI.txt`
- `deep-research-report.md`
- `deep-research-report (1).md`
- `deep-research-report (2).md`
- the existing `AutoVideoPipeline` codebase, especially its Flow/Veo automation patterns

The package intentionally removes or defers assumptions that do not match the current operator environment.

## Current practical execution stack

### Available now
- Gemini API: automated planning / extraction / ShotSpec assistance / prompt expansion / QC assistance.
- Google Flow / Veo: current primary video execution path.
- Seedance through Elyum and Dola: alternate video execution paths.
- Existing `AutoVideoPipeline`: reference/reuse source for Flow session, cookie preflight, batching, download and FFmpeg-related mechanics.
- ChatGPT Plus / Codex: development, architecture, code review and difficult manual reasoning. It is **not** assumed to be a runtime API.
- FFmpeg: proxy/assembly/media utilities.
- DaVinci Resolve: finishing truth.

### Not available / not required in V1
- Stable Diffusion / ComfyUI local image generation.
- Local video models.
- Mandatory image-first workflow.

### Deferred
- Blender / Unreal / 3D previz.
- LoRA / fine-tuning.
- Postgres / Redis / Temporal / S3 / Kubernetes.
- Full web studio.
- Multi-agent crew.
- Self-host video inference.

## V1 canonical flow

```text
Story / Narration
    ↓
Narrative Compile
    ↓
Character + World + Cinematography + Continuity Bibles
    ↓
Scene / Shot Design
    ↓
ShotSpec
    ↓
Prompt Compiler
    ↓
RoutingDecision
    ↓
Provider Adapter
    ↓
GenerationAttempt → ProviderJob → Output Asset
    ↓
QCReport
    ├─ PASS → SelectedTake
    └─ FAIL → RepairDecision → new attempt / alternate coverage / editorial workaround
    ↓
EditManifest / Rough Cut
    ↓
DaVinci Resolve
    ↓
Master
```

## Frozen invariants

1. ShotSpec / Film State is source of truth; provider prompts are derived artifacts.
2. Continuity is data, not chat memory.
3. Creative intent is separated from provider/runtime state.
4. Providers are replaceable adapters.
5. Browser/cookie automation is transport, never Film Core.
6. Do not correlate outputs by "latest file" or gallery ordering.
7. No blind retry. Failure classification must drive a RepairDecision.
8. Cost is measured primarily as cost per approved shot / approved second / finished minute.
9. DaVinci Resolve is finishing truth.
10. V1 defaults to filesystem + JSON/SQLite and one-machine operation.
11. Model IDs, pricing and provider quirks live in runtime config, never Film IR.
12. A capability may be unavailable; the system degrades explicitly instead of pretending support.
13. Private/provider-facing execution contracts are treated as volatile and versioned. A previously proven adapter is historical evidence, not a permanent protocol guarantee. When provider behavior becomes ambiguous or diverges from the last qualified contract, stop mutations, preserve evidence, and re-observe/reconstruct the provider's current successful operating path before changing Film Core or blindly retrying.
14. Provider mutation admission and provider observation/reconciliation are qualified separately. A UI click, outbound request, HTTP 200, or DOM/gallery state is never acceptance proof by itself. After a possible external effect, output ownership must come from durable backend evidence; if that evidence cannot establish the effect uniquely, the state remains unknown and mutation must not be retried blindly.
15. Reference-conditioned generation requires immutable provider-reference attestation before dispatch: canonical Film asset/hash → provider scope → provider media identity → independently bound readback bytes/content. Historical IDs, filenames, gallery position, or prior claimed mappings are not sufficient reference proof.

## Package map

- `01_SCOPE_AND_PRINCIPLES.md`
- `02_CANONICAL_DOMAIN_MODEL.md`
- `03_CINEMATIC_CONTROL_SPEC.md`
- `04_SHOTSPEC_V1.md`
- `05_PROMPT_COMPILER.md`
- `06_PROVIDER_CAPABILITIES.md`
- `07_ROUTING_REPAIR_QC.md`
- `08_ASSET_LINEAGE_COST.md`
- `09_EDITORIAL_FLOW.md`
- `10_VERTICAL_SLICE_BENCHMARK.md`
- `11_IMPLEMENTATION_PLAN.md`
- `12_DECISION_LOG.md`
- `schemas/`
- `fixtures/`
- `config/runtime.example.yaml`

## Change rule

A frozen V1 decision may change only when one of these is true:

- benchmark evidence contradicts it;
- a provider capability changes materially;
- the current transport becomes unusable;
- a real production bottleneck is measured;
- a legal/rights requirement forces a change.

New tools alone are not a reason to redesign Film Core.
