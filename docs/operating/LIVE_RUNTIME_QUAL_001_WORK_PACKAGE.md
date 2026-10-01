# LIVE-RUNTIME-QUAL-001 — Bounded Generic Flow R2V Live Qualification

## Status

Frozen Owner-authorized live work package.

## Worker profile

```text
ZCode Agent
Model: GLM-5.3-Flash
Thinking: Max
Mode: Goal / long-running autonomous execution
Target wall time: 4–8 hours
```

## Base

```text
Expected implementation base:
aeab4048c04d92520ae4b56c4a8f9cba720c95f5

Target branch:
zcode/live-runtime-qual-001
```

The offline runtime and hardening chain through `RUNTIME-HARDEN-001` are accepted at the base revision. This package is the first bounded live qualification of the generic `FlowR2VShotRuntime` production path.

## Owner authority

The Owner explicitly authorizes **fewer than 5 Generate actions** for this live qualification. Interpret this strictly as:

```text
MAX_NATIVE_UI_GENERATE_RELEASES = 4
```

This is a ceiling, not a target. Use the minimum number of Generates necessary to establish the acceptance criteria.

Authority applies only to the exact project/account/reference/session scope established by the existing qualified Flow evidence and this package. It does not authorize uploads, account changes, project changes, provider switching, direct private-RPC mutation, or retries after ambiguity.

### Critical ambiguity rule

The remaining Generate budget is **not retry authority**.

If any released Generate crosses the possible external-effect boundary and its external effect, output identity, reference lineage, project scope, backend attribution, or acquisition truth becomes ambiguous/inconclusive:

```text
STOP IMMEDIATELY
→ preserve evidence
→ OWNER_AMBIGUITY_GATE
→ NO REDISPATCH
→ NO NEXT CANARY
```

This rule overrides the remaining Generate budget.

## Live write authority

Authorized live writes:

- Native provider UI `Generate` only.
- Maximum 4 total released Generate requests.
- Each Generate must belong to a distinct frozen ProviderJob/canary intent.
- No upload.
- No delete.
- No project creation.
- No account/project switching.
- No settings mutation outside the already-qualified native UI envelope.
- No direct/private `MZZa6b` mutation.
- No synthetic in-page mutation.
- No CAPTCHA/anti-abuse bypass.

Read-only provider operations required for qualification are allowed when they use existing qualified read paths and preserve sanitized evidence only.

## Qualified live boundary

Use the accepted production path and existing provider-native UI mutation path:

```text
fresh exact FlowReferenceRpcSession
→ qualify_flow_catalog_source (0 reads)
→ FlowR2VShotRuntime.freeze
   → exactly one authoritative catalog read
   → qualified snapshot + atomic ProviderJob freeze
→ verified canonical reference attestation
→ FlowR2VShotRuntime.reserve
→ native UI prepare/readback
→ FlowR2VShotRuntime.arm_native_guard
→ exactly one browser-created qualified Generate request released
→ request/response/acceptance facts
→ reconciliation only
→ backend unique attribution
→ exact media binding/acquisition
→ generated Asset
→ QC technical eligibility
```

The browser is transport only. DOM/request/HTTP success never establishes output ownership.

## Existing scope to reuse

Reuse the existing qualified Flow project/account/reference already established by prior evidence. Do not create another project or upload another reference merely for this task.

The runtime must use the exact verified reference attestation chain already proven for the canonical fictional reference, unless current read-only verification shows that chain is unavailable or inconsistent. If unavailable/inconsistent, stop before Generate with `OWNER_GATE`; do not upload a replacement.

Historical Fresh Shot A remains immutable history. Do not retry it. Do not mutate or reinterpret its ambiguity state.

## Goal

Prove that the accepted generic runtime works against the real current Flow provider boundary under provider-native UI admission, with durable exact lineage and fail-closed recovery.

Primary success criterion:

```text
one ordinary synthetic generic R2V shot
→ live native UI Generate
→ unique backend-owned output
→ exact acquisition
→ persisted Asset
→ QC technical eligibility
```

If the first canary fully proves the generic path, additional Generates may be used only for clearly distinct qualification questions below and only while the prior canary is conclusively PROVEN or conclusively terminal without ambiguity.

## Planned Generate ladder

### G1 — Mandatory generic live canary

One ordinary synthetic reference-conditioned R2V shot through the generic runtime. This must not use Slice-0011 semantic orchestration or historical Shot A/B identities.

Prove:

- fresh session capability mint with zero catalog reads;
- exactly one pre-dispatch catalog capture;
- exact verified reference lineage;
- frozen provider prompt / intent;
- one reserved mutation budget;
- one native UI qualified Generate request;
- backend output attribution against fresh baseline;
- exact media acquisition;
- generated Asset lineage;
- QC technical eligibility;
- restart after completion produces no second Generate.

### G2 — Optional repeatability canary

Run only if G1 is fully PROVEN and there is no ambiguity.

A second distinct ordinary synthetic shot using the same verified reference and same qualified native UI contract. Purpose: prove the generic runtime is reusable and not accidentally coupled to one shot/job identity.

### G3 — Optional restart/recovery live canary

Run only if G1/G2 are fully PROVEN and a distinct live mutation is genuinely needed to prove restart semantics not already established by read-only restart of the earlier jobs.

The worker must justify why another Generate is necessary before releasing it. Prefer read-only restart/recovery proof using existing G1/G2 state if sufficient.

### G4 — Optional final bounded canary

Run only if a remaining material provider-live uncertainty can be answered by one additional distinct shot and cannot be answered read-only. Document the hypothesis before reservation. Never use G4 merely to increase sample size.

## Generate accounting

Before each reservation/release, write an immutable local authority ledger entry containing:

```text
canary_id
provider_job_id
shot_id
hypothesis
preconditions
current_generate_count
max_generate_count = 4
```

After release, record that authority as consumed before any reconciliation.

A browser request blocked before `route.continue_()` does not count as a released Generate, but the cause must be preserved. A request that is released counts permanently even if the provider later rejects it.

## Preflight before any Generate

Before G1:

1. Verify exact branch/revision and full regression baseline.
2. Verify current worktree is isolated and source repo historical state is untouched.
3. Verify no historical canary authority is being reused as retry authority.
4. Open only the existing qualified Flow project/session.
5. Read current session/project metadata.
6. Mint catalog capability from a fresh exact session.
7. Let runtime freeze perform the one authoritative catalog read.
8. Verify the canonical provider reference exists uniquely and exact attestation still validates.
9. Verify native UI settings/profile exactly match the qualified profile.
10. Verify prompt editor/reference chip/project/model/count/duration/aspect ratio before arming.
11. Verify Generate budget ledger says 0/4.
12. Only then reserve mutation authority.

If any preflight truth fails, stop before Generate. Do not repair by changing project/account/model/reference/settings contract live.

## Native UI mutation policy

Mutation must come from the provider-native UI interaction path.

Do not construct or send the private mutation RPC yourself.

Use the existing `OneGenerateGuard` / `FlowR2VBoundary` protections so the browser-created request is inspected against:

- exact project;
- exact reference media id;
- frozen prompt;
- qualified model/profile;
- 8 seconds;
- 720p;
- 16:9;
- x1 output;
- current reserved ProviderJob.

If the observed request differs, abort it and stop before any substitute strategy.

## Reconciliation policy

After a released Generate:

- Never click Generate again for that job.
- Never reserve another attempt as a retry.
- Reconciliation is read-only.
- Poll/read only through qualified provider read paths.
- Baseline ownership requires exact fresh delta + exact marker + exact reference + exact model + exact project + completed backend record.
- Zero candidates after the bounded observation window = `EXTERNAL_EFFECT_UNRESOLVED` / owner gate, not retry authority.
- More than one candidate or any conflicting identity = `OWNER_AMBIGUITY_GATE`.
- UI tile/gallery order/filename/DOM alone are never ownership authority.

## Acquisition policy

Only a uniquely attributed backend output may be acquired.

Use the runtime-owned qualified media payload/resource/bytes path. Do not trust caller-created `BoundMedia` or arbitrary signed URL/file bytes.

Persist only sanitized stable identities/hashes/metadata. Do not persist signed URLs, cookies, auth tokens, CAPTCHA tokens, Chrome caches, or raw authenticated responses.

## QC

For each successfully acquired canary:

- exact fresh lineage readback;
- full technical media validation;
- existing QC exact-lineage precondition;
- produce a review packet/contact sheet if current reusable QC tooling supports it without widening scope.

Visual quality is evidence, not the primary success criterion. Do not reject a technically/lineage-proven canary merely because it is aesthetically mediocre; document visual observations separately.

## Mandatory long-run checkpoints

```text
L0 BASELINE
- accepted base verified
- full tests green
- authority ledger initialized 0/4

L1 LIVE PREFLIGHT
- fresh session/project/reference/native UI truths proven
- no mutation yet

L2 G1 RELEASED
- one distinct job frozen/reserved
- exactly one qualified native UI request released
- authority consumed durably

L3 G1 RECONCILED
- either PROVEN exact output/acquisition/QC
- or OWNER_AMBIGUITY_GATE / conclusive terminal negative

L4 OPTIONAL CANARIES
- G2..G4 only under the ladder rules
- each with its own hypothesis and exact authority consumption

L5 ADVERSARIAL REVIEW
- STOP MUTATING
- independently attack attribution, lineage, budget accounting, restart, evidence, and any claimed live conclusions
- no Generate during this phase

L6 DELIVERY
- full regression
- compileall
- git diff --check
- security/evidence scan
- exact delivery HEAD
- consolidated live evidence handoff
```

## Long-run autonomy

Continue autonomously through ordinary coding/test/instrumentation/reconciliation work. Do not stop merely to report progress.

You may repair local code if live evidence reveals a deterministic implementation bug **only if** the repair does not require redispatching an ambiguous prior job. Re-run offline tests after repairs.

A repaired implementation does not revive consumed Generate authority for an ambiguous job.

## Hard stops

Stop immediately and return `OWNER_GATE` / `OWNER_AMBIGUITY_GATE` when:

- any possible-effect Generate has ambiguous external effect;
- output attribution is nonunique/conflicting;
- reference identity/readback conflicts;
- project/account/session scope changes;
- UI/native request and backend evidence disagree materially;
- continuing requires upload, project/account switch, direct mutation RPC, CAPTCHA bypass, provider switch, or blind retry;
- remaining authority would only be used as retry/sample-size rather than a distinct qualification hypothesis.

## Historical custody

Do not modify historical Slice-0011 jobs/evidence, Fresh A ambiguity classification, prior live canary receipts, or source repo browser/profile data. The existing local browser profile may be used as an execution source but must not be copied into Git or mutated beyond ordinary provider-native session state.

## Acceptance

Return `COMPLETED_CANDIDATE` only if all live claims made are exactly supported by durable evidence and:

1. G1 generic runtime path is PROVEN end-to-end live, or a narrower terminal state is honestly returned.
2. Generate accounting is exact and never exceeds 4.
3. No blind retry occurred.
4. No ambiguity was crossed by later mutation.
5. Provider-native UI was the mutation admission path.
6. Backend attribution, not UI, owned outputs.
7. Acquired Asset lineage is exact.
8. Restart/recovery cannot redispatch consumed jobs.
9. Historical custody is unchanged.
10. Full regression remains green.
11. Tracked delta/evidence contains no secrets/profile/cache material.
12. All remaining unknowns/non-claims are explicit.

## Final handoff

Return one consolidated report containing:

- terminal state;
- base revision and delivery HEAD;
- exact live project/reference/model/profile scope;
- Generate budget: authorized / released / remaining;
- per-canary ledger G1..G4;
- exact native UI request evidence;
- backend attribution evidence;
- acquisition/Asset/QC evidence;
- restart/recovery evidence;
- adversarial-review findings and repairs;
- focused/full test results;
- provider reads/writes summary;
- historical custody result;
- security scan;
- remaining UNKNOWN/non-claims;
- whether any human intervention was required;
- recommendation for next production step.

Do not merge or push.
