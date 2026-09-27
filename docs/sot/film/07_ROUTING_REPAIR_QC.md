# Routing, Repair and QC

## 1. Shot difficulty dimensions

Before generation, classify:

```text
identity_dependency
continuity_dependency
multi_character_count
prop_interaction_complexity
body_motion_complexity
camera_complexity
spatial_dependency
dialogue_dependency
lip_sync_dependency
physics_dependency
```

Optional derived classes:

- A: insert / atmosphere / simple establishing
- B: one character / simple motion
- C: identity + performance sensitive
- D: multi-character / prop interaction
- E: precise blocking / complex physical interaction / complex camera

The class helps routing but does not hard-code a provider.

## 2. V1 routing order

The router selects by:

1. required capabilities;
2. provider health/session availability;
3. continuity/control fit;
4. benchmarked approval rate for similar shots;
5. benchmarked cost per approved second;
6. latency only after quality/cost constraints;
7. fallback availability.

No permanent claim that Veo or Seedance is universally superior is frozen in V1.

## 3. V1 repair ladder

Because local Stable Diffusion/ComfyUI is unavailable, image-first is not mandatory.

A failed shot should escalate through a practical ladder:

```text
0 Diagnose failure
1 Repair ShotSpec / simplify action / clarify invariant
2 Recompile with stronger text constraints or provider-supported references
3 Use another supported control of the same provider
4 Route to alternate provider/transport
5 Split the shot into simpler coverage
6 Request reaction/insert/cutaway pickup
7 Use editorial/VFX cleanup if cheaper than regeneration
8 Defer advanced image/3D/V2V capability until economically justified
```

Any future image/keyframe capability can be inserted into levels 2–4 without redesigning Film Core.

## 4. Failure taxonomy

### Technical
- submit failed;
- auth/session expired;
- timeout;
- corrupt output;
- wrong duration/resolution;
- download/correlation failure.

### Identity / look
- wrong person;
- face drift;
- wardrobe drift;
- hair/accessory drift.

### World
- location mutation;
- wrong geography;
- missing/persistent prop error;
- weather/time mismatch;
- light-direction mismatch.

### Continuity
- screen direction;
- eyeline;
- body orientation;
- prop changes hand;
- wrong start/end state;
- emotional discontinuity.

### Performance / action
- exaggerated expression;
- wrong gesture;
- incorrect action order;
- weak reaction;
- contact/physics failure.

### Camera
- wrong framing;
- wrong angle;
- wrong movement;
- unwanted orbit/handheld;
- lens/perspective mismatch.

### Visual temporal
- anatomy;
- morphing;
- flicker;
- texture crawl;
- background mutation.

### Editorial usability
- no handles;
- action cannot cut;
- missing reaction;
- wrong pacing;
- needed coverage absent.

## 5. QCReport rules

QC has separate gates:

- technical;
- visual;
- continuity;
- editorial usability.

A visually beautiful shot still fails if a critical continuity invariant fails.

Do not average all dimensions into a single pass score.

## 6. RepairDecision

Every failure must produce:
- failure codes;
- evidence/notes;
- repair strategy;
- what changes on next attempt;
- route decision if provider changes;
- budget impact;
- whether human approval is needed.

`retry_same_request` is not a valid repair strategy unless failure was purely transient transport failure.

## 7. Human authority

Gemini/VLM can assist QC, but V1 final shot selection remains human-authoritative for:
- identity;
- narrative correctness;
- performance;
- continuity;
- editorial usefulness.
