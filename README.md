# AI Film Pipeline

Lean, local-first AI film production pipeline.

## Canonical sources

This repository is governed by two frozen SoTs:

1. `docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`
   - HOW the project is developed.
   - Lifecycle: SHAPE → BOUND → SLICE → BUILD → PROVE → LEARN.

2. `docs/sot/film/00_SOT_INDEX.md`
   - WHAT the system is and which architectural/product decisions are frozen.
   - Film State / ShotSpec is the source of truth.
   - Continuity is data.
   - Providers are replaceable adapters.
   - V1 is local-first.

Project-local execution artifacts live under `docs/operating/`.

## Current execution stack

- Gemini API: primary automated LLM path.
- Google Flow / Veo: current primary video execution path.
- Seedance via Dola / Elyum: alternate video transports.
- ChatGPT Plus / Codex: development / difficult interactive reasoning.
- FFmpeg: rough assembly and media utilities.
- DaVinci Resolve: finishing truth.

Stable Diffusion / ComfyUI is not a V1 dependency.

## Before changing code

Read, in order:

1. `docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`
2. `docs/sot/film/00_SOT_INDEX.md`
3. `docs/operating/PROJECT_OPERATING_PROFILE.md`
4. `docs/operating/CURRENT_SLICE.md`
5. `docs/operating/IMPLEMENTATION_STATUS.md`

Do not reinterpret frozen SoT silently.
If implementation evidence challenges a frozen truth, route it through LEARN and create an explicit truth delta.
