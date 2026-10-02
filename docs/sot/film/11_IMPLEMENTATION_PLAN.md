# Implementation Plan

## Repository shape

```text
ai-film-pipeline/
├── pyproject.toml
├── README.md
├── config/
│   └── runtime.yaml
├── src/film_pipeline/
│   ├── cli.py
│   ├── core/
│   │   ├── models.py
│   │   ├── ids.py
│   │   ├── hashing.py
│   │   └── state.py
│   ├── bibles/
│   │   ├── characters.py
│   │   ├── world.py
│   │   └── cinematography.py
│   ├── compiler/
│   │   ├── prompt_compiler.py
│   │   ├── canonical_blocks.py
│   │   └── templates/
│   ├── routing/
│   │   ├── classifier.py
│   │   └── router.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── flow_veo.py
│   │   ├── seedance_dola.py
│   │   └── seedance_elyum.py
│   ├── runtime/
│   │   ├── jobs.py
│   │   ├── attempts.py
│   │   └── sqlite_store.py
│   ├── assets/
│   │   ├── registry.py
│   │   └── hashing.py
│   ├── qc/
│   │   ├── taxonomy.py
│   │   ├── evaluator.py
│   │   └── repair.py
│   ├── cost/
│   │   └── ledger.py
│   └── editorial/
│       ├── manifest.py
│       └── ffmpeg.py
├── tests/
│   ├── fixtures/
│   ├── test_schema.py
│   ├── test_prompt_compiler.py
│   ├── test_lineage.py
│   ├── test_router.py
│   └── test_repair.py
└── projects/
```

## Persistence V1

- SQLite: entity metadata, attempts, jobs, QC, cost.
- Filesystem: source/reference/output media.
- JSON: export/import and human-readable fixtures.
- No Redis/Postgres/Temporal/S3 dependency.

## Reuse policy

### AutoVideoPipeline
Inspect and selectively reuse/port:
- Flow project/session handling;
- cookie validation/preflight;
- batching;
- exact download/correlation logic where sound;
- FFmpeg utilities;
- doctor/logging patterns.

Do not make its current stage structure the new Film Core.

### Research repos
Reuse vocabulary/patterns, not full applications:
- CineCrew: structured Shot/Asset/QC vocabulary;
- Take: provider/capability/job abstraction;
- Jellyfish: task/link lifecycle concepts;
- STAGE: continuity/start-end strategy concept.

## Current Flow/Veo production target

Productize the qualified provider-native UI route before inventing a new mutation transport:

```text
ShotSpec / PromptPlan
→ durable attempt + unique Film marker
→ exact reference attestation
→ headful Chrome provider-native Flow UI preparation
→ one Generate release
→ bounded Zzl0ze reconciliation
→ unique media ownership
→ bounded render completion / as29s resolution
→ exact acquisition
→ SHA-256 + metadata + full technical decode
→ Asset / QC / RepairDecision
```

The adapter must explicitly model admission vs render completion, preserve at-most-once mutation authority, and fail closed on ambiguity. Direct/private Flow mutation RPC replay is not a production target. Provider security/session artifacts remain runtime-local secrets.

## Phase A — 2–3 day skeleton

Deliver:
- Pydantic models aligned with JSON Schema;
- SQLite store;
- asset registry + SHA-256;
- Prompt Compiler deterministic core;
- provider base interface;
- Flow adapter spike using proven existing mechanics;
- CLI commands:
  - `project init`
  - `shot validate`
  - `shot compile`
  - `provider doctor`
  - `generate`
  - `qc record`
  - `take select`
- golden tests on fixtures.

Gate:
`fixture ShotSpec → PromptPlan → dry-run ProviderRequest → persisted Attempt` works end-to-end.

## Phase B — 1–2 weeks

Deliver:
- productionized Flow/Veo adapter;
- Seedance Dola/Elyum adapters;
- routing;
- QC taxonomy;
- RepairDecision;
- cost ledger;
- FFmpeg rough assembly;
- benchmark runner;
- vertical slice.

Gate:
30–60s benchmark passes the acceptance criteria in `10_VERTICAL_SLICE_BENCHMARK.md`.

## Phase C — only after benchmark

Add only where measured:
- image generation/reference service;
- better VLM QC;
- OTIO;
- web UI;
- official provider APIs if available/economic;
- database/object-store upgrade;
- durable worker orchestration;
- 3D/previz;
- fine-tuning.

## Upgrade triggers

### SQLite → Postgres
Only when multi-process/multi-user concurrency or remote collaboration becomes painful.

### Filesystem → object storage
Only when assets need remote collaboration, large-scale retention or multi-machine workers.

### Local job loop → durable orchestration
Only when long-running jobs, crashes and concurrent provider workloads create measurable recovery problems.

### CLI → web UI
Only when operator throughput is limited by CLI/manual inspection rather than generation quality.

## Definition of "ready to build"

No additional architecture research is required when:
- schemas validate;
- adapter contract is stable;
- benchmark spec exists;
- runtime model/provider values are config-driven.
