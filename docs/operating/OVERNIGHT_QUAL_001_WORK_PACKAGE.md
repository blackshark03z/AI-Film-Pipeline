# OVERNIGHT-QUAL-001 — Generic Flow R2V Runtime Integration

## Worker

```text
ZCode Agent
Model: GLM-5.3-Flash
Thinking: Max
Mode: Goal / long-running autonomous execution
Target wall time: 4–6 hours
```

## Base

```text
Branch: zcode/overnight-qual-001-r2v-runtime-integration
Expected base: d8d4b0a94fe4383393407977f0f77ae2e54064e9
```

`ZCODE-QUAL-001` is accepted. `FlowR2VBoundary` is the reusable, offline-proven Flow reference-to-video mutation/reconciliation boundary. Do not redesign it unless a concrete contradiction is proven.

Fresh Shot A remains historical live state only:

```text
DISPATCH OBSERVED
EXTERNAL EFFECT UNRESOLVED
OWNER_AMBIGUITY_GATE
```

No retry or replacement live attempt is authorized.

## Goal

Productize the next reusable layer above `FlowR2VBoundary`: a generic reference-conditioned Flow R2V runtime orchestration path that can take an ordinary Film shot from frozen Film lineage to an acquired generated Asset **without any Slice-0011 semantic dependency**.

Target conceptual path:

```text
ShotSpec
→ PromptPlan
→ RoutingDecision
→ GenerationAttempt
→ ProviderJob
→ verified reference attestation
→ qualified MutationIntent
→ durable mutation reservation
→ one guarded native-UI request boundary
→ backend reconciliation / unique output attribution
→ exact media acquisition
→ generated Asset persisted with complete lineage
→ QC-handoff eligibility
```

Prove the path OFFLINE/LOCAL only with frozen/synthetic provider evidence and a locally generated valid MP4 fixture. Do not execute Flow.

## Why this package

The repository already has Film Core/routing, durable runtime lineage, `FlowR2VBoundary`, `LiveRuntimeExecutor` acquisition/Asset persistence, and QC exact-lineage checks. What remains too slice-specific is orchestration around freezing an ordinary reference-conditioned Flow job and composing those pieces together. `slice0011.py` and `slice0011_canonical_reproof.py` are historical authority, not the future generic execution API.

Do not delete or rewrite historical modules. Extract/compose only generic behavior.

## Lifecycle and autonomy

Follow `SHAPE → BOUND → SLICE → BUILD → PROVE → LEARN`.

Techlead owns WHAT/boundaries/acceptance. Worker owns HOW.

Continue autonomously through repository discovery, design, implementation, failed-test repair, adversarial review, regression and delivery. Do not stop merely to report progress or ask routine clarification.

Reuse-first:

```text
SEARCH → REUSE → COMPOSE → ADAPT → EXTEND → BUILD LAST
```

Inspect at minimum:

```text
src/film_pipeline/flow_r2v_boundary.py
src/film_pipeline/live_runtime.py
src/film_pipeline/execution.py
src/film_pipeline/compiler.py
src/film_pipeline/store.py
src/film_pipeline/qc_runner.py
src/film_pipeline/slice0011.py
src/film_pipeline/slice0011_canonical_reproof.py
relevant Flow/provider/runtime/QC tests
```

Do not create a second dispatch journal, ProviderJob model, reference-attestation system, acquisition store, or Film Core.

## Required architecture semantics

1. Film lineage stays canonical. Preserve exact ShotSpec hash, PromptPlan hash, RoutingDecision id, GenerationAttempt id and ProviderJob id. Provider/UI details must not leak into Film Core.
2. Flow-specific compact prompt/correlation stays at adapter/runtime boundary. Exact provider submission prompt must be frozen before mutation authority and participate in existing durable mutation binding.
3. Verified provider-reference attestation is mandatory before mutation eligibility. Filename/gallery/prior claims/weak similarity are insufficient.
4. One mutation opportunity only. Consumed jobs are reconciliation/acquisition only; missing output never re-authorizes Generate.
5. Backend owns output identity. UI/request/HTTP/DOM are transport facts only.
6. Reuse existing immutable output binding/acquisition machinery. Resulting Asset must bind attempt, job, provider output id, local SHA256, validated metadata and acquisition receipt.
7. Prove resulting Asset satisfies existing QC exact-lineage precondition. Do not fake human SelectedTake.

## Absolute provider boundary

ZERO provider access.

Do NOT open Flow, click Generate, call MZZa6b, upload media, create/delete/switch project/account, perform live catalog/media reads, retry Fresh Shot A, generate Shot B, or use live provider responses as a test oracle.

All provider behavior must be frozen/synthetic/local doubles. Final provider access/mutation count must be `0`.

## Historical custody

Existing Slice-0011 evidence/state is immutable. Do not modify historical ProviderJobs, reset dispatch counts, delete ambiguity facts, rewrite receipts/attestations, change Fresh Shot A classification, manufacture successor attempts, or change old bindings/acquisition records.

## Required offline end-to-end proof

Build one deterministic test proving a **new synthetic ordinary R2V shot** runs through production code:

- valid reference Asset + existing attestation mechanics;
- ordinary ShotSpec / PromptPlan / RoutingDecision;
- new GenerationAttempt / ProviderJob;
- frozen synthetic provider catalog baseline;
- qualified Flow R2V MutationIntent/profile;
- one simulated browser-created qualified request;
- one synthetic backend output record with exact marker/reference/model lineage;
- one local valid MP4 fixture generated with FFmpeg or existing local fixture machinery;
- exact acquisition/persistence through production code;
- fresh lineage readback proving QC-handoff eligibility.

No production generic module/test may special-case `CHAR_CONTINUITY_A`, `CHAR_CONTINUITY_B`, Slice-0011 authority IDs, or historical project state.

## Adversarial proof matrix

At minimum prove fail-closed behavior for:

1. Shot/plan/route mismatch.
2. Wrong route provider.
3. Missing/tampered reference attestation.
4. Attested reference != mutation intent reference.
5. Project/account/profile/model drift.
6. Prompt/correlation drift after job freeze.
7. Mutation before durable reservation.
8. Duplicate/re-entry mutation after reservation.
9. Request observed but no backend output => unresolved/reconcile-only.
10. Preexisting provider output cannot be owned.
11. Wrong marker/reference/model lineage cannot be owned.
12. Multiple output candidates => ambiguity.
13. Output from another ProviderJob cannot be rebound.
14. Media ID/project/resource mismatch.
15. Download bytes/metadata mismatch.
16. Existing local file without acquisition receipt rejected.
17. Partial/staging bytes never accepted as final Asset.
18. Restart after reservation cannot create second mutation.
19. Restart after exact output binding continues acquisition only.
20. Restart after completed acquisition yields same exact Asset/lineage with no provider mutation.
21. QC exact-lineage precondition rejects tampered Asset bytes.
22. Generic runtime production modules do not import Slice-0011 modules.

Add stronger cases if discovered.

## Mandatory checkpoint protocol

Create local checkpoint commits only on this branch. Never push/merge.

```text
C0 BASELINE
- reconstruct truth
- baseline 433-test suite green
- record reuse/design decision

C1 BOUND
- generic orchestration contract chosen
- acceptance mapped to tests

C2 FIRST_WORKING
- reusable offline vertical path works
- focused tests green

C3 ADVERSARIAL_REVIEW
- STOP BUILDING
- review as hostile independent reviewer
- persist concrete findings before repair

C4 REPAIRED
- material findings reproduced by tests and fixed
- focused/integration regressions green

C5 DELIVERY
- full regression
- compile/import checks
- git diff --check
- tracked-delta security/secret/profile/cache scan
- exact delivery HEAD + consolidated handoff
```

Do not fake PROVEN at any checkpoint.

## Mandatory self-adversarial review

After FIRST_WORKING, change roles and try to disprove your implementation. Search specifically for cross-component invariant gaps, TOCTOU, docs stronger than code, tests exercising the wrong object, duplicate authority systems, known-good drift, restart/crash-window holes, mutable provenance after reservation, ways to pass by weakening tests, and hidden Slice-0011 coupling.

For each material finding:

```text
finding → adversarial reproduction test → repair → regression
```

Completion is forbidden until this phase occurs.

## Stop conditions

Ordinary failures (tests, refactor dead ends, local implementation mistakes, build issues) are not blockers; diagnose and continue.

Hard-stop only if continued work requires prohibited provider/network access, external write/deploy/push/merge, destructive action outside the worktree, secret/auth manipulation, changing frozen SoT/acceptance, altering historical live state, or a genuine unresolved contradiction requiring Owner authority.

At hard stop preserve evidence and return `OWNER_GATE` or `INCONCLUSIVE`; do not improvise around authority.

## Verification floor

Accepted base full suite: **433 passed**. This is a floor, not a target. Do not remove/weaken tests.

Final verification must include focused new orchestration tests, existing Flow R2V boundary tests, live_runtime/dispatch recovery, reference-attestation tests, relevant QC exact-lineage tests, full pytest, `python -m compileall -q src tools`, `git diff --check`, and tracked-delta secret/profile/cache scan.

## Security

Never track cookies, auth/captcha tokens, signed URLs, Chrome profiles/caches, raw authenticated responses, credentials or unrelated scratch evidence. No stealth/fingerprint/CAPTCHA/anti-abuse bypass.

## Non-goals

Do not resolve Fresh Shot A, generate Shot B, add Seedance, implement multi-provider fallback, change Film SoT or ShotSpec schema, implement human continuity approval, AutoEdit, Slice-0012, merge or push.

## Acceptance

Return `COMPLETED_CANDIDATE` only if:

1. Generic reference-conditioned Flow R2V runtime orchestration exists.
2. It composes `FlowR2VBoundary` + existing runtime/store rather than parallel systems.
3. Generic production modules have no Slice-0011 semantic dependency.
4. Film lineage is exact/freshly readable.
5. Reference attestation mandatory.
6. Provider prompt/mutation intent frozen before authority consumption.
7. One mutation opportunity survives restart.
8. Missing output remains reconciliation-only.
9. Backend attribution unique/fail-closed.
10. Exact acquisition produces immutable generated Asset provenance.
11. Restart/resume cases proven offline.
12. Existing QC exact-lineage precondition consumes the resulting Asset shape.
13. Mandatory adversarial review occurred and material findings repaired.
14. Historical Slice-0011 state unchanged.
15. Provider access/mutation count = 0.
16. Full regression >= 433 and no tests weakened.
17. Tracked delta security scan clean.
18. Exact delivery revision committed locally.

## Final handoff

Return one consolidated report with: final state; base; delivery HEAD; checkpoint/commit history C0–C5 or equivalent; reuse/design decisions; production/test files changed; exact offline vertical proof; restart/crash-window proofs; adversarial findings/repairs; exact focused/full results; provider access count=0; historical custody proof; security scan; remaining UNKNOWN/non-claims; whether any human `continue`/clarification was needed; and recommendation for a separately authorized live continuation.

Do not merge or push.
