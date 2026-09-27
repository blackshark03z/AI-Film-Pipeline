# Cinematic Control Specification V1

This document formalizes the director/continuity knowledge already present in the research into data that the pipeline can compile and validate.

## 1. Character lock

A recurring character has four identities.

### VisualIdentity
- face geometry;
- body proportions;
- age range;
- hair;
- skin;
- silhouette;
- scars / unique traits.

### LookState
- wardrobe;
- makeup;
- hairstyle variation;
- accessories;
- wetness;
- dirt;
- blood;
- injury.

### BehavioralIdentity
- baseline energy;
- posture;
- eye-contact pattern;
- gesture density;
- speech rhythm;
- stress/anger/fear behavior;
- forbidden behavior.

### VocalIdentity
Optional in V1:
- timbre;
- pitch range;
- accent;
- tempo;
- delivery style;
- rights/consent metadata.

**Rule:** after a character identity version is approved, a shot may change LookState but may not silently create a "similar person".

## 2. World / location lock

Location state must be explicit enough to preserve:
- era;
- architecture/materials;
- scene geography;
- doors/windows/landmarks;
- persistent props;
- weather;
- time of day;
- atmosphere;
- light direction.

V1 does not require 3D geometry. `geometry_notes` is text/structured metadata until a future spatial system is justified.

## 3. Cinematography Bible

Project-level language:

```text
aspect_ratio
lens_language
camera_height_philosophy
movement_philosophy
lighting_language
contrast
palette
depth_of_field_language
texture
grain
handheld_behavior
```

## 4. CameraPlan per shot

Recommended controlled vocabulary:

### Framing
`ECU | CU | MCU | MS | MLS | WS | EWS | OTS | TWO_SHOT | INSERT | CUTAWAY`

### Height / angle
`eye_level | low | high | overhead | ground_level | dutch`

### Lens intent
Provider-neutral intent plus optional focal hint:
`ultrawide | wide | normal | portrait | telephoto | macro`

### Motion
`locked | pan | tilt | dolly_in | dolly_out | tracking | orbit | handheld | crane | rack_focus | custom`

### Movement semantics
- dolly-in: intimacy, realization, pressure;
- pull/dolly-out: isolation, context reveal;
- orbit: spatial reveal or destabilization;
- tracking: follow action;
- handheld: subjective instability/immediacy;
- locked: observation, tension, control.

**Rule:** movement needs a `purpose` field. "Cinematic" alone is not a purpose.

## 5. BlockingPlan

Shot blocking expresses observable spatial behavior:

```text
start_position
start_orientation
action_beats[]
end_position
end_orientation
prop_interactions[]
entrance_exit
motion_path_notes
```

## 6. PerformancePlan

Prefer observable behavior over emotion adjectives.

Bad:
`She is very scared.`

Better:
```text
short inhale
eyes move before the head
avoid eye contact for one beat
shoulders remain still
speech becomes slightly slower
no exaggerated expression
```

## 7. ContinuityState

At minimum track:
- character look version;
- body orientation;
- screen direction;
- eyeline;
- hands/prop ownership;
- prop state;
- location geometry anchor;
- key-light direction;
- weather/time;
- injury/dirt/wetness;
- emotional state;
- previous-shot dependency;
- intended end state.

## 8. Coverage grammar

For dialogue scenes, possible coverage:

```text
MASTER / TWO SHOT
→ OTS A / OTS B
→ SINGLE A / SINGLE B
→ reaction CU
→ insert / cutaway
```

V1 does not generate all coverage automatically. Shot planning/rough edit decides what is necessary.

## 9. Provider degradation policy

The Film Core may request:
- text-only generation;
- reference image;
- start frame;
- end frame;
- multi-reference;
- native audio;
- seed;
- duration/aspect controls.

If the chosen provider lacks a requested capability, the compiler must emit:

```text
unsupported_controls[]
degraded_controls[]
compiled_text_fallbacks[]
```

No control may silently disappear.
