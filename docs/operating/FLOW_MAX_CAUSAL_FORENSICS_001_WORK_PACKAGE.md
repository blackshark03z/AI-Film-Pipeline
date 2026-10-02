# FLOW-MAX-CAUSAL-FORENSICS-001 — Claude Full-Observability Causal Investigation

## Status
Frozen Owner-directed final Flow investigation package.

## Worker profile

```text
Claude coding/agent environment
Use the strongest Claude model available to the Owner
Reasoning: maximum / extended thinking
Mode: long-running autonomous investigation
```

This is NOT another ordinary reverse-engineering pass. The goal is to exhaust the strongest client-side method available without provider-internal backend telemetry:

```text
static reverse engineering
+ dynamic browser instrumentation
+ native manual execution shadowing
+ success/failure differential
+ one-variable causal interventions
+ JavaScript execution-path tracing
+ backend effect verification
+ repeated reproduction
```

## Base

```text
Latest prior evidence/code base:
5d4df90a192db6018a541b1091897ff3b831628a

Target branch:
claude/flow-max-causal-forensics-001
```

Read all current Flow evidence before live mutation. Historical evidence is prior truth, not current proof.

## Owner directive

The Owner wants one final, maximum-strength Flow investigation before abandoning Flow for Dola.

Hard active-forensics limit:

```text
MAX_FLOW_FORENSIC_WALL_TIME = 4 hours
```

The 4-hour clock starts only AFTER the Owner has manually logged into the fresh Chrome profile and explicitly indicated the account is ready for Flow investigation. Human login waiting time does not consume the forensic clock.

If no stable Flow route is proven by the deadline:

```text
STOP FLOW
→ classify client-side investigation exhausted/degraded
→ preserve evidence
→ recommend PIVOT_TO_DOLA
```

Do not continue because one more experiment might help.

## Fresh-account experiment — mandatory

The Owner will log into a CLEAN Google account that has never used Flow before.

You must create and launch a completely fresh, visible Chrome profile yourself.

Preferred profile location outside the repository:

```text
D:\AI FILM MAKER\Flow-Claude-Clean-Profile
```

Requirements:

- Use real Google Chrome, headful/visible.
- New empty `user-data-dir`; do not copy/import any prior Flow/Google profile.
- Do not import raw cookies from previous accounts.
- Do not ask the Owner to paste a password, 2FA code, recovery code, cookie, token, or any credential into chat/logs/files.
- Do not record login-network traffic, credential forms, passwords, 2FA, cookies, auth headers, or tokens.
- Open Chrome and stop at exactly one human gate:

```text
OWNER_LOGIN_GATE
```

At that gate instruct the Owner only:

> Please log in manually to the clean Google account in the Chrome window. Do not send me credentials. When login is complete, navigate to Flow and leave the browser on the Flow home/project screen, then tell me READY.

Do not automate Google login.

Only AFTER Owner says READY may Flow forensic instrumentation begin.

If first-run Flow onboarding/terms/account eligibility appears, observe it. Do not accept a paid plan, purchase credits, or bypass eligibility. A normal free project may be created through the native Flow UI if needed for the experiment; payment/plan/identity/legal-consent gates require Owner action.

## Mutation authority

Historical Owner authority remains bounded at fewer than five Generate releases. For THIS package interpret the fresh budget strictly as:

```text
MAX_TOTAL_FRESH_FLOW_GENERATE_RELEASES = 4
```

This includes BOTH Owner-manual and agent-triggered Generate releases.

Budget is a ceiling, not a target.

Preferred use:

```text
G1 = Owner-manual native Generate under full instrumentation (golden control)
G2 = first automated native-UI causal comparison, only if G1 is PROVEN
G3 = one-variable causal intervention, only if prior state is unambiguous
G4 = final confirmation/reversal, only if needed to prove the discriminator
```

The remaining budget is NEVER retry authority.

### Critical ambiguity rule

For any released Generate, if external effect, admission, output identity, reference lineage, project/session scope, or acquisition truth becomes ambiguous/inconclusive:

```text
STOP ALL FURTHER FLOW MUTATION
→ preserve evidence
→ OWNER_AMBIGUITY_GATE
→ no redispatch
→ no next Generate
```

This overrides the remaining budget.

## Prior evidence — read before mutation

Read in full from the existing repositories/worktrees, at minimum:

```text
FLOW_CURRENT_R2V_CONTRACT_20261001.md
FLOW_R2V_OPEN_INVESTIGATION_20261001.md
FLOW_R2V_INDEPENDENT_STORYAUTO_RECONSTRUCTION.md
FLOW_R2V_CURRENT_CONTRACT_CANARY_20261001.md
STORY_AUTO_R2V_LIVE_CONTROL_20261001.md
docs/operating/LIVE_RUNTIME_QUAL_001_EVIDENCE.md
docs/operating/FLOW_FORENSIC_TO_DOLA_001_EVIDENCE.md
```

Also inspect relevant Flow code, tests, browser/native-UI guards, catalog/media readers, and historical successful evidence.

Do not restart from zero. Build a concise prior-truth matrix of:

```text
PROVEN
DISPROVEN
OBSERVED
INFERRED
UNKNOWN
```

## Primary scientific question

Answer this exact question:

> What observable state or event-path difference causes a provider-native Flow Generate to be ADMITTED instead of producing HTTP 200 / null / zero durable backend effect?

The deliverable is an evidence-backed admission discriminator or an evidence-backed conclusion that the discriminator lies beyond client-side observability.

# PHASE 0 — BASELINE + EXPERIMENT HYGIENE

Before Flow instrumentation:

1. Verify branch/base/worktree.
2. Full regression baseline.
3. Record exact Chrome binary/version.
4. Verify fresh profile is empty/new before Owner login.
5. Create a sanitized evidence directory outside tracked source if large traces are needed.
6. Create immutable experiment ledger.
7. Confirm Generate budget 0/4.
8. Do not touch old ambiguous jobs.

After Owner READY:

9. Record `FORENSICS_STARTED_AT` and `FORENSICS_DEADLINE = START + 4h`.
10. Bind investigation to this exact fresh account/profile/session without storing raw identity secrets.

# PHASE 1 — MAXIMUM PASSIVE OBSERVABILITY

Instrument ONLY after login is complete.

Use the strongest non-bypass browser observability reasonably available:

```text
Chrome DevTools Protocol (CDP)
Network
Page
Runtime
Performance / PerformanceObserver
Tracing
Console
DOM snapshots / targeted DOM state
request initiator / stack when available
frontend build/WIZ/session fingerprints
browser navigation/lifecycle timestamps
Flow catalog/backend reads
```

For native input/event chronology, capture sanitized metadata only, for example:

```text
event type
relative timestamp
target semantic selector/hash
focus state
pointer/keyboard/input ordering
Event.isTrusted when observable
```

Do not capture typed credentials or unrelated page contents.

Do not patch/bypass CAPTCHA, risk controls, entitlements, anti-abuse, or trusted-event checks.

Do not attempt to synthesize or forge `isTrusted` or security state.

## Required trace classes

Create normalized/sanitized traces for:

```text
T0 = fresh-account idle Flow state
T1 = pre-Generate UI state
T2 = Generate event chain
T3 = outbound MZZa6b request chronology
T4 = response chronology/shape
T5 = read-only Zzl0ze backend effect timeline
T6 = as29s/acquisition if an output exists
```

Raw secrets must never enter evidence.

# PHASE 2 — OWNER MANUAL GOLDEN CONTROL

This is the most important experiment.

Prepare one ordinary minimal native Flow video-generation intent through the NORMAL provider UI. Prefer the simplest configuration exposed to the clean account that is relevant to production; do not force R2V if clean-account UI capability does not expose it. Record exact capability/model/mode first.

The Owner performs the final Generate click manually.

The agent does NOT click Generate for G1.

The agent shadows/records the execution.

Before G1:

- capture fresh backend baseline;
- record exact project/session/build/model/mode/settings;
- if reference-conditioned generation is used, verify exact reference identity/readback first;
- install passive request/response tracing;
- create immutable G1 preclaim;
- confirm budget 0/4.

Then ask the Owner only:

> Please click the native Flow Generate button once now. Do not click it again.

After click:

- record event chronology;
- identify the browser-native request initiator stack if available;
- record sanitized request structure/hashes;
- record response structure/timing;
- reconcile backend read-only;
- never infer ownership from UI/gallery order.

### G1 decision

If G1 produces a unique durable backend output with exact lineage:

```text
G1 = PROVEN_MANUAL_NATIVE_SUCCESS
```

Acquire/validate it exactly and continue to Phase 3.

If G1 itself reaches HTTP200/null/no-delta or otherwise ambiguous external effect:

```text
STOP MUTATION
OWNER_AMBIGUITY_GATE
```

Do NOT spend G2-G4. Produce the strongest client-side conclusion possible from the trace. This indicates clean-account manual-native admission is not currently available, so there is no justified automation discriminator experiment.

# PHASE 3 — SUCCESS-vs-AUTOMATION DIFFERENTIAL

Only if G1 is fully PROVEN.

Create one fresh distinct intent G2 with the SAME:

```text
account
profile
project
frontend build
model/mode/settings
reference (if any)
prompt semantics
browser session class
```

Change only the interaction source required for automation comparison.

Use normal native UI automation. Do NOT construct private mutation RPCs.

Instrument G2 identically to G1.

If G2 also succeeds, compare traces anyway and determine whether the current generic native automation path is already stable on the clean account.

If G2 fails while G1 succeeds, this is the ideal causal A/B. Build a normalized differential across at least:

```text
DOM/focus state before click
input/pointer/key event ordering
Event.isTrusted observations
Angular/native event handler path
request initiator stack
captcha invocation timing metadata (never token value)
client/session/request UUID generation chronology
WIZ/build/session fingerprints
request URL/query/header-name set (no secret values)
request payload structure and hashes
request timing relative to UI state changes
response bytes/shape/timing
catalog side effects
```

Classify every delta as:

```text
MATERIAL_CANDIDATE
EXPECTED_NOISE
SECRET_REDACTED
UNKNOWN
```

# PHASE 4 — JAVASCRIPT EXECUTION-PATH FORENSICS

If G1 succeeds and G2 fails but network-level differential is insufficient, descend into frontend execution.

Use DevTools/source maps/debugger/instrumentation as available to OBSERVE, not bypass:

```text
Generate button handler
Angular/component callback path
request-builder invocation
reference/context binding reads
captcha invocation point/timing
internal client IDs/state read at dispatch
native request creation function
```

Prefer breakpoints/logpoints/wrappers that record arguments/state fingerprints without changing provider semantics.

Do NOT patch code to skip security/risk/entitlement checks.

Do NOT inject a private RPC as a substitute for native UI.

Produce a call-path graph:

```text
native user event
→ frontend handler(s)
→ state reads
→ request builder
→ request dispatch
→ provider response
```

for success and failure, then diff them.

# PHASE 5 — CAUSAL INTERVENTION

Only if prior released Generate states are fully unambiguous.

Use G3/G4 sparingly to test one variable at a time.

Candidate dimensions may include only observed client-side differences, for example:

```text
manual vs automated native click
fresh tab vs same tab
focus/blur ordering
reference attach before prompt vs prompt before attach
fresh navigation vs long-lived canvas
historical native sequence vs minimized native sequence
project A vs project B only if same account/session and scientifically necessary
```

Do NOT test speculative security-evasion variables.

For each experiment:

1. Write hypothesis before mutation.
2. State exactly ONE manipulated variable.
3. Hold all other observable variables constant as much as possible.
4. Capture the same trace schema.
5. Reconcile backend exactly.

A candidate admission discriminator becomes causal evidence only if the direction can be demonstrated, ideally:

```text
FAIL state
→ change X only
→ SUCCESS
```

and then, if safe and budget allows:

```text
SUCCESS
→ reverse X
→ FAIL
```

or a second independent success under X.

Never use remaining budget merely for sample size.

# STABLE ROUTE DEFINITION

`FLOW_STABLE_ROUTE_PROVEN` requires ALL:

1. Current clean-account route stated exactly.
2. Provider-native UI mutation only.
3. At least two fresh distinct successful current executions under the claimed route, unless one manual success plus one automated success conclusively prove the same route and contract.
4. Unique durable backend attribution for every claimed success.
5. Exact acquisition and technical QC.
6. Restart/recovery cannot redispatch consumed jobs.
7. Zero blind retry.
8. No UI/gallery ownership inference.
9. Admission discriminator either identified OR proven unnecessary because both manual and automation succeed under the same bounded route.
10. No anti-abuse/CAPTCHA/risk bypass.

# CLIENT-SIDE EXHAUSTION DEFINITION

Classify `FLOW_CLIENT_SIDE_CAUSAL_EXHAUSTED` when, within the 4h limit:

- clean-account manual native G1 itself cannot establish durable admission; OR
- manual succeeds but no client-observable discriminator can be isolated despite full traces and bounded causal tests; OR
- evidence indicates the remaining cause is likely provider-internal/account-side admission state not observable from the client.

Do not claim the exact backend cause (risk score, entitlement, scheduler, policy flag) without provider-side evidence.

# EVIDENCE HYGIENE

Never persist/commit:

```text
Google password
2FA/recovery codes
cookies
Authorization headers
raw reCAPTCHA token
signed media URLs
full browser profile
Chrome cache
raw authenticated response bodies containing secrets
```

Allowed evidence:

```text
sanitized header names
redacted/salted scope identifiers when needed
SHA-256 hashes of non-secret request bodies/artifacts
structural fingerprints
event names/timing
frontend build IDs
provider model IDs
project/output/media IDs when needed for lineage
backend catalog facts
video asset hashes/metadata
```

If a trace tool captures secrets by default, post-process/redact before storing evidence and keep raw trace untracked/local only; delete raw secret-bearing trace after extracting the sanitized evidence unless deletion would destroy needed Owner evidence, in which case keep it outside repo and report its location without exposing contents.

# AUTONOMY

After OWNER_LOGIN_GATE, work autonomously for up to 4h.

Do not stop for ordinary:

```text
coding mistakes
instrumentation defects
test failures
trace-parser bugs
selector drift
local tooling failures
```

Diagnose → repair → verify → continue.

Stop only at:

```text
OWNER_AMBIGUITY_GATE
OWNER_AUTH/ELIGIBILITY/PAYMENT_GATE
4h hard deadline
FLOW_STABLE_ROUTE_PROVEN
```

# REQUIRED CHECKPOINTS

```text
C0 BASELINE / FRESH PROFILE CREATED
C1 OWNER_LOGIN_GATE
C2 PRIOR TRUTH + CLEAN ACCOUNT PREFLIGHT
C3 MAX PASSIVE OBSERVABILITY READY
C4 G1 OWNER-MANUAL GOLDEN TRACE
C5 G2 AUTOMATION DIFFERENTIAL (only if G1 proven)
C6 JS EXECUTION-PATH DIFFERENTIAL (if needed)
C7 G3/G4 CAUSAL INTERVENTION (if justified)
C8 ADVERSARIAL REVIEW
C9 DELIVERY
```

Use local commits/checkpoints. No push. No merge.

# ADVERSARIAL REVIEW

Before final conclusion, stop mutation and attack your own claims:

- Could the manual/automation difference be timing noise?
- Did instrumentation itself perturb execution?
- Did any account/project/model/reference variable change unintentionally?
- Is request equality only structural while temporal ordering differs?
- Is a claimed success uniquely owned from backend truth?
- Did a trace accidentally omit a material event because instrumentation started late?
- Did any experiment cross ambiguity and then improperly continue?
- Is the alleged discriminator reproducible/reversible?
- Are provider-internal hypotheses being mislabeled as observed facts?

Repair local evidence/analysis issues without new mutation unless remaining mutation is explicitly justified and unambiguous.

# FINAL DELIVERY

Return one consolidated report with:

- terminal state;
- exact branch/worktree/base/delivery HEAD;
- Chrome version and fresh-profile proof;
- login gate timestamps (no credentials);
- active forensic start/deadline/end and wall time;
- Generate budget authorized/released/remaining;
- clean-account Flow capability/onboarding observations;
- prior evidence consumed;
- G1 manual-native trace/result;
- G2 automation trace/result if run;
- normalized success/failure differential;
- JS call-path differential if performed;
- every causal hypothesis and result;
- exact admission discriminator if found;
- stable production route if proven;
- backend attribution/acquisition/QC evidence;
- provider reads/writes accounting;
- test results / compileall / git diff --check / security scan;
- historical custody;
- remaining UNKNOWNs/non-claims;
- recommendation exactly one of:

```text
ROUTE_FLOW
PIVOT_TO_DOLA
NEITHER
```

Terminal state exactly one of:

```text
FLOW_STABLE_ROUTE_PROVEN
FLOW_CLIENT_SIDE_CAUSAL_EXHAUSTED
OWNER_AMBIGUITY_GATE
OWNER_GATE
INCONCLUSIVE_TIMEOUT
```

Do not merge.
Do not push.
