# Vertical Slice Benchmark V1

## Purpose

Prove that the architecture can create a coherent film sequence, not merely beautiful isolated clips.

## Film

Target:
- 30–60 seconds;
- 8–12 shots;
- 1–2 recurring characters;
- 1–2 locations.

Must include:
- establishing shot;
- continuity-sensitive character shot;
- MCU/CU;
- two-person or spatial relation shot if possible;
- reaction shot;
- prop or hand-state continuity;
- one intentional camera movement;
- one locked/observational shot;
- one shot expected to require repair;
- rough cut with at least one editorial pickup opportunity.

## Acceptance gates

### Story gate
- every shot has dramatic purpose;
- shot order is narratively coherent.

### Character gate
- recurring identity recognizably stable;
- look/wardrobe state does not drift without a state change.

### World gate
- location/time/weather/key-light direction are coherent enough for edit.

### Camera gate
- framing and movement match ShotSpec intent;
- movement has a declared purpose;
- no systematic default push-in behavior.

### Continuity gate
- screen direction/eyeline/prop/body orientation survive intended cuts.

### Generation gate
- every output maps to an exact GenerationAttempt/ProviderJob;
- failed attempts have classified reasons.

### Repair gate
- at least one failed shot is fixed through a changed RepairDecision rather than blind retry.

### Editorial gate
- approved shots can be assembled into a watchable rough cut;
- missing coverage can create PickupRequest(s).

### Provenance gate
- each used timeline asset traces to its ShotSpec and attempt.

## Metrics

Record:

```text
attempts_per_approved_shot
first_pass_approval_rate
provider_failure_rate
continuity_failure_rate
repair_success_rate
generated_seconds_per_approved_second
cost_per_approved_shot
cost_per_approved_second
cost_per_finished_minute
human_minutes_per_approved_shot
submit_to_output_wall_clock
```

Latency is observed and summarized (median/p90/p95 when enough samples exist); do not use an invented "<10 seconds per shot" requirement.

## Provider comparison

Compare Flow/Veo and Seedance transports only on the shot classes actually tested.

The benchmark must not force equal workloads merely for symmetry; route shots as production would, then record evidence.
