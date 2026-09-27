# Canonical Domain Model

## Layer boundaries

### A. Creative / Film State
Stable, provider-neutral, human-understandable.

```text
Project
├── StorySource
├── Scene
├── Character
│   └── CharacterLookState
├── Location
├── Prop
├── WorldStateSnapshot
├── CinematographyBible
├── PerformanceBible
└── ShotSpec
```

### B. Derived planning state
Rebuildable from creative state + configuration.

```text
PromptPlan
RoutingDecision
```

### C. Runtime / execution state
Never embedded into ShotSpec.

```text
GenerationAttempt
ProviderJob
Asset
CostEvent
QCReport
RepairDecision
```

### D. Editorial state

```text
SelectedTake
PickupRequest
EditManifest
MasterRecord
```

## Entity definitions

### Project
Owns project identity, source media, bibles, scenes, shots and production policy.

### StorySource
Raw screenplay, narration, SRT, transcript or outline. Immutable source files should be asset-linked.

### Scene
Narrative unit with purpose, location, participating characters, start world state and end world state.

### Character
Stable identity definition:
- facial/body identity;
- age range;
- hair/skin/silhouette;
- unique traits;
- behavioral baseline;
- voice identity metadata if used.

### CharacterLookState
Versioned mutable appearance:
- wardrobe;
- hair variation;
- makeup;
- accessories;
- wetness/dirt/blood/injury.

### Location
Persistent world/location definition:
- era;
- architecture/materials;
- geometry notes;
- doors/windows/key landmarks;
- palette/atmosphere;
- recurring props.

### Prop
Persistent object identity and scene state where continuity matters.

### WorldStateSnapshot
State at a narrative boundary:
- character positions/orientations;
- look state;
- props and ownership;
- time/weather;
- light direction;
- knowledge/emotional state.

### CinematographyBible
Global visual language:
- aspect ratio;
- lens language;
- camera height philosophy;
- movement philosophy;
- lighting/contrast/palette;
- depth of field;
- texture/grain;
- handheld behavior.

### PerformanceBible
Observable behavior rules:
- gaze;
- gesture density;
- posture;
- speech rhythm;
- stress/anger/fear patterns;
- forbidden behaviors.

### ShotSpec
Canonical creative contract for exactly one required shot.

### PromptPlan
Compiler output. Contains canonical prompt blocks, provider mapping and unsupported-control warnings.

### RoutingDecision
Why a provider/transport was selected for a specific attempt.

### GenerationAttempt
One intentional generation attempt for one ShotSpec version.

### ProviderJob
Transport-level execution record. Can wrap an official API job, browser/cookie operation, or synthetic local correlation ID.

### Asset
Immutable file/reference record with SHA-256 where bytes are local.

### QCReport
Technical, visual, continuity and editorial usability evaluation.

### RepairDecision
Diagnosis plus next action. A retry without a changed hypothesis is invalid.

### SelectedTake
The approved output asset selected for editorial use.

### PickupRequest
Editorial-generated request for missing reaction, insert, cutaway, bridge or replacement shot.

### EditManifest
Ordered editorial intent for rough assembly / Resolve handoff.

### CostEvent
Per-attempt/provider/asset cost record. Direct cost may be unknown for subscription-based/browser-mediated transports.

## Required relationships

```text
Project
  → Scene
    → ShotSpec(version)

ShotSpec(version)
  → PromptPlan
  → RoutingDecision
  → GenerationAttempt
  → ProviderJob
  → Asset(output)
  → QCReport
  → RepairDecision? / SelectedTake?

SelectedTake
  → EditManifest usage

EditManifest
  → PickupRequest?
  → new ShotSpec / new GenerationAttempt
```

## Forbidden coupling

ShotSpec MUST NOT contain:
- cookie/session data;
- API keys;
- provider job IDs;
- provider-specific gallery indices;
- billing transaction IDs;
- raw browser selectors;
- retry counters;
- runtime error strings.

Those belong to runtime records.
