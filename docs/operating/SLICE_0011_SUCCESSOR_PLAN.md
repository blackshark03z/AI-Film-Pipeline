# SLICE-0011 — proposed successor attempt (not authorized)

## Current authority

This continuation is implementation-only. **No provider calls, reconciliation,
uploads or video submits are authorized.** Existing ambiguous Shot A must not
be modified or retried. This document is a proposal, not a new GenerationAttempt,
ProviderJob, reservation, replacement allowance or dispatch approval.

Baseline HEAD: `d958067d20a0961c0f350bdd08085a925aa676c3`.
Existing protected job:
`job_26f3a0b279b6d43ca6ad4cff7084ebc552f0ba7ad792c8519e74fd526490a6b8`.
Existing protected attempt:
`attempt_3b7fa3f988caeb979db14c6332be05c535aca9af6c3514c459aa74302d48d4ca`.
It remains INCONCLUSIVE, dispatch_count=1, null output and zero bindings.
Neither this job nor its historical canonical plan/request will be rewritten.

## Prepared provider implementation

- Film's canonical compiler and PromptPlan are unchanged. A separate
  `flow-r2v-compact-v1` adapter derives concise cinematic prose from their
  creative blocks. Current A/B examples are 1072/1177 characters, 149/167 words,
  including a full-length example marker. Oversize intent fails for explicit
  reduction; it is not silently truncated.
- The exact reference remains Asset
  `asset_70834935ccb760367645411d115c0c24243f4dd921182ef4b9502cad382062ff`, SHA
  `31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531`, remote UUID
  `53b5a413-7bb5-4f97-9be4-2461794a7d80` in project
  `f6b40e79-d6f8-4354-80ae-c863260e96f5`. Model: `abra_r2v_8s`.
- Future job evidence stores the adapted prompt separately from the canonical
  plan and hashes both. It appends exactly one `[FILM-<provider_job_id>]` marker.
  Existing legacy jobs retain their original prompt attribution contract.
- Received MZZa6b response diagnostics record parsed/not parsed, fixed type
  counts, UTF-8 byte length and type-only response-shape hash. Raw values,
  dictionary keys, tokens, signed URLs and numeric values do not enter the
  diagnostic shape hash. Diagnostics have advisory rank 0; no counts threshold
  establishes provider admission or authorizes a retry.
- Output binding requires the exact project, reference UUID, model, marker in
  the qualified primary prompt slot, new output UUID relative to baseline, and
  agreeing qualified lineage slots when present. Malformed/conflicting lineage,
  marker collision, duplicate identities and multiple candidates stop closed.

## Successor Shot A prompt preview

The final line below is a placeholder, not an allocated job/dispatch marker.
The actual suffix will contain the entire new job ID after authorization and
intent freezing. This preview is derived from the unchanged canonical A plan.

```text
8-second cinematic medium close-up, 16:9, eye level, portrait lens, locked camera.
Introduce the fictional illustrated woman and establish her stable identity and look.
Use the exact image reference. one illustrated adult woman faces slightly frame-right
in the room. subtle natural breathing; one small blink while keeping a calm neutral
expression; one small natural blink; gentle breathing. the same woman holds the same
pose and look. day; simple illustrated living room with window left and sofa and
plant right. Preserve same illustrated adult woman as the exact image reference;
teal bob hair; crimson round glasses; mustard jacket over blue shirt; silver triangle
earrings; small beauty mark below her right eye; one person only; no wardrobe or
identity mutation; reference face and look; illustrated room layout. slightly frame
right; near camera right. Avoid identity change; wardrobe change; large head turn;
extra person; identity swap; new accessories; camera movement; scene change.
[FILM-<new_provider_job_id>]
```

## Proposed procedure after explicit Owner authorization

1. Owner must explicitly authorize a **new successor attempt**, its exact shot
   scope and generation limit. The historical A allowance is already consumed;
   this implementation does not grant another. No B dispatch is implied.
2. Create a separate, durably linked successor intent with a fresh attempt/job
   identity. Record `supersedes_attempt` for audit only. Preserve the original
   row, journal, prompt, reservation and ambiguity fact. Never remove its gate
   or reset its dispatch counter.
3. Implement/review the bounded successor-entry procedure under that explicit
   authority. Current `_existing_job_for_shot` intentionally rejects multiple
   attempts for the same shot, and the live CLI still stops before opening Flow
   when it sees the original ambiguity. **No bypass or successor CLI is added
   by this implementation-only request.**
4. After authorization and that procedure, revalidate reference receipt/source,
   exact project access and current catalog contract; capture a fresh baseline.
   Compute the actual provider_job_id from the new frozen intent/baseline, then
   compile and persist its single marker before the one permitted submit. No
   speculative actual job ID or marker is allocated in this document.
5. Persist request arm and sanitized response diagnostics. HTTP200/parsed/type
   counts remain observations. Bind only a uniquely qualified new output;
   bounded absence or ambiguity immediately stops. No blind retry, substitute,
   reference reupload or provider switch.
6. Acquire/decode/hash the exact bound bytes, then technical QC and the joint
   character review. Final SelectedTake/assembly still requires explicit Owner
   approval of the actual clips. No Slice-0012 or AutoEdit change.

## Acceptance boundary

Deterministic offline tests and independent review establish implementation
behavior only. There is **no new live compact-prompt or MZZa6b response proof**
in this continuation. The existing ambiguous Shot A is not evaluated, recovered,
modified or retried. A successor attempt remains proposed and uncreated.

Verification: 32 new compact-adapter cases and 101 focused tests PASS (13.07s),
compileall/diff check PASS. Independent reviewer confirmed the exact-one-reference
guard, retained creative fields and no allocated successor/dispatch authority.
Production and research runtime files retain their exact pre-implementation
SHA256 values recorded in SLICE_0011_STATUS.md. Final full regression:
**270 passed (55.48s)**. Live compact-prompt behavior remains unverified.
