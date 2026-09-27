# Scope and Principles

## Goal

Build the smallest durable film-production kernel that can turn structured story intent into traceable AI-generated shots, continuity-aware selection, rough edit and Resolve finishing.

The goal is **not** to maximize the number of models/tools integrated.

## MVP production envelope

Initial benchmark target:

- 30–60 seconds;
- 8–12 shots;
- 1–2 recurring characters;
- 1–2 locations;
- mostly narration or short dialogue;
- simple action;
- at least one continuity-critical shot;
- at least one failed shot that exercises the repair loop.

After the vertical slice passes, the same architecture may scale to longer narration-driven story drama.

## In scope

- story/narration ingestion;
- scene and shot breakdown;
- character/world/cinematography/continuity bibles;
- ShotSpec;
- prompt compilation;
- Flow/Veo and Seedance adapters;
- deterministic lineage;
- QC and repair;
- rough assembly;
- Resolve handoff;
- cost/attempt logging.

## Explicit non-goals for V1

- local Stable Diffusion / ComfyUI dependency;
- mandatory image/keyframe generation;
- local video inference;
- training/fine-tuning;
- 3D blocking;
- complex web app;
- distributed workers;
- durable orchestration platform;
- microservices;
- automatic "AI judge" as final authority;
- complete NLE replacement;
- autonomous multi-agent film crew.

## Design principles

### Continuity is data
Identity, look, props, geography, screen direction, eyelines, light direction, weather, injury/dirt/wetness and emotional state must be explicit state.

### Cheap decisions before expensive generation
Lock story purpose, shot necessity, continuity constraints and camera intent before sending a video job.

### One shot, one primary performance idea
Avoid overloading a short generation with many simultaneous state transitions.

### Camera motion has meaning
Movement is selected for dramatic purpose, not because "cinematic" prompts tend to add a push-in.

### Provider-neutral core
Flow/Veo, Dola, Elyum and future providers are execution engines, not the architecture.

### Explicit degradation
If a provider cannot express a control, the compiler records that control as unsupported and either:
- converts it into text constraints;
- routes elsewhere;
- or accepts the degradation deliberately.

### Editorial is part of generation
Rough cut can request pickups. Generation is not "done" merely because a provider returned an MP4.

### Evidence over preference
Veo-vs-Seedance routing quality, retry count, cost and latency are benchmark decisions, not permanent beliefs.
