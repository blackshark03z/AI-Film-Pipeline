# Prompt Compiler V1

## Contract

Input:

```text
ShotSpec
+ Character/Look data
+ Location/World data
+ Cinematography Bible
+ ProviderCapabilities
+ CompilerPolicy
```

Output:

```text
PromptPlan
```

`PromptPlan` is derived and reproducible.

## PromptPlan fields

```text
compiler_version
input_hash
shot_spec_version
canonical_blocks
provider_id
provider_prompt
mapped_controls
unsupported_controls
degraded_controls
warnings
```

## Canonical prompt blocks

The deterministic core builds blocks in this order:

```text
SHOT / DRAMATIC PURPOSE
SUBJECT / CHARACTER LOCK
ACTION / PERFORMANCE
ENVIRONMENT / WORLD LOCK
CAMERA / LENS / MOVEMENT
BLOCKING / START-END STATE
LIGHTING / STYLE
AUDIO / DIALOGUE
CONTINUITY CONSTRAINTS
NEGATIVE / FORBIDDEN BEHAVIOR
```

The exact provider prompt may reorder or compress these blocks.

## Deterministic core + optional LLM expansion

### Deterministic core
Must:
- inject immutable identity attributes;
- inject correct look version;
- inject location anchors;
- encode camera intent;
- encode screen direction/eyeline;
- preserve start/end states;
- map structured controls to provider capabilities;
- record unsupported/degraded controls.

### Optional LLM expansion
Gemini may:
- rewrite prose for clarity;
- compress redundant text;
- make observable action wording more natural;
- turn structured intent into provider-friendly prose.

Gemini may NOT:
- change shot purpose;
- invent a new character look;
- reverse screen direction;
- change required props;
- add camera movement contradicting CameraPlan;
- mutate start/end states.

## Compiler hashing

`input_hash` should include:
- ShotSpec canonical JSON;
- referenced Bible/version IDs;
- compiler version;
- provider capability profile version;
- prompt template version.

This allows golden-test regression.

## Golden tests

For each fixture:
1. same input + same compiler version => same canonical blocks/hash;
2. provider mapping may differ but must preserve declared intent;
3. unsupported controls must be explicit;
4. no provider runtime secret may appear in PromptPlan;
5. character/world invariant blocks must remain stable across shots using the same locked versions.

## Example degradation

If ShotSpec requests an end-frame constraint but provider profile says `supports_end_frame=false`:

```text
unsupported_controls: ["end_frame"]
degraded_controls: ["end_state converted to textual continuity constraint"]
```

The compiler must not silently omit the end state.
