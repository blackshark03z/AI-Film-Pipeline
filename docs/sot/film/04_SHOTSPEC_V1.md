# ShotSpec V1

Schema: `schemas/shot_spec.schema.json`

## Purpose

`ShotSpec` is the canonical provider-neutral description of one required shot.

It describes **what the film needs**, not how Flow/Dola/Elyum happen to execute it.

## Required core

```text
schema_version
shot_id
scene_id
dramatic_purpose
duration_target_s
shot_type
characters[]
camera
blocking
continuity
```

## Optional but first-class

```text
performance
lighting
environment
audio
references
constraints
editorial
```

## Rules

1. `dramatic_purpose` must say what the audience should learn/feel.
2. A shot should contain one primary performance/action idea.
3. `camera.movement.purpose` is required whenever movement != `locked`.
4. Start and end state should be explicit for continuity-critical shots.
5. Reference fields point to canonical asset IDs, not file paths hard-coded into prompts.
6. Provider/model names are forbidden.
7. Runtime retry state is forbidden.
8. Fields unsupported by a provider remain in ShotSpec; the compiler records degradation.

## Creative state vs runtime state

Allowed in ShotSpec:
- character identity/look reference;
- location ID;
- camera intent;
- eyeline;
- screen direction;
- observable performance;
- dialogue;
- reference asset IDs.

Not allowed:
- `flow_cookie_path`;
- `dola_task_id`;
- `seedance_model_id`;
- `provider_cost`;
- `attempt_number`;
- `download_url`.

## Versioning

- Schema uses semantic versioning.
- Every stored shot has `spec_version`.
- Editing a locked ShotSpec creates a new version.
- GenerationAttempt stores the exact ShotSpec version/hash it used.
- Old attempts remain immutable.

## Fixtures

See:
- `fixtures/dialogue_closeup.json`
- `fixtures/continuity_two_shot.json`
- `fixtures/action_reveal.json`
