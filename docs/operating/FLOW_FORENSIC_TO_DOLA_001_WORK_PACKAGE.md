# FLOW-FORENSIC-TO-DOLA-001 — 4h Flow Forensics, Then Dola Fallback

## Status
Frozen Owner-directed long-run work package.

## Base

```text
Accepted live-runtime evidence HEAD:
85e88cc87e0cd9f0a523fe399072655c20f700b4

Target branch:
zcode/flow-forensic-dola-fallback-001
```

This package starts from the terminal state of `LIVE-RUNTIME-QUAL-001`:

```text
G1 native-UI Generate released exactly once
→ browser request qualified against frozen intent
→ HTTP 200 / parsed null application payload
→ no provider acceptance fact
→ two bounded read-only reconciliation windows
→ zero catalog delta
→ EXTERNAL_EFFECT_UNRESOLVED
→ OWNER_AMBIGUITY_GATE
```

Do not reinterpret or retry that exact job.

## Owner directive

1. Continue Google Flow investigation for **no more than 4 wall-clock hours** from Flow-forensics start.
2. Goal: establish **one stable, reproducible Flow generation route** suitable for AI-Film routing.
3. If no stable route is proven within 4 hours, **STOP Flow investigation** and pivot to **Dola AI / Seedance Dola** qualification.
4. Do not keep polishing Flow after the deadline.

Fresh mutation ceilings:

```text
MAX_NEW_FLOW_GENERATE_RELEASES = 3
MAX_DOLA_GENERATE_RELEASES = 2
```

Ceilings, not targets. Use the minimum necessary.

## Critical ambiguity rule

Remaining mutation budget is never retry authority.

For any newly released mutation, if possible external effect becomes ambiguous — acceptance, output identity, reference lineage, project/session scope, acquisition truth, or correlation — then:

```text
STOP that provider's mutation path immediately
→ preserve evidence
→ no redispatch of that intent
→ no retry using remaining budget
```

For Flow, one new ambiguous release ends Flow mutation for this package unless ambiguity is resolved read-only; then pivot to Dola.

## Prior evidence that MUST be reused

Read these in full, read-only before live mutation:

```text
D:\AI FILM MAKER\AI-Film-Pipeline\FLOW_CURRENT_R2V_CONTRACT_20261001.md
D:\AI FILM MAKER\AI-Film-Pipeline\FLOW_R2V_OPEN_INVESTIGATION_20261001.md
D:\AI FILM MAKER\AI-Film-Pipeline\FLOW_R2V_INDEPENDENT_STORYAUTO_RECONSTRUCTION.md
D:\AI FILM MAKER\AI-Film-Pipeline\FLOW_R2V_CURRENT_CONTRACT_CANARY_20261001.md
D:\AI FILM MAKER\AI-Film-Pipeline\STORY_AUTO_R2V_LIVE_CONTROL_20261001.md
```

Also read `docs/operating/LIVE_RUNTIME_QUAL_001_EVIDENCE.md`.

Historical evidence is prior truth, not a substitute for current qualification.

## Known Flow facts to preserve unless current evidence disproves them

- Direct/private `MZZa6b` mutation repeatedly produced HTTP 200 + null + zero video delta and is unqualified.
- Provider-native UI previously succeeded on project `a94d36d0-5f95-420d-97b4-dc7cf0c87453` with durable Veo 3.1 R2V output.
- Current AI-Film project `f6b40e79-d6f8-4354-80ae-c863260e96f5` repeatedly showed null/no-delta R2V behavior.
- Story Auto's formerly proven direct path later reproduced the same null/no-output pattern, so this is not simply an AI-Film serializer/parser defect.
- Current generic runtime qualifies provider-native UI mutation + backend reconciliation, not direct mutation RPC.
- `Zzl0ze` and `as29s` are read-only evidence paths; UI/DOM is never output authority.
- HTTP 200 + null is non-acceptance/unresolved external effect, not success.

Do not restart investigation from zero. Search for the delta between successful provider-native UI admission and current failing provider-native UI admission.

# PHASE F — FLOW FORENSICS (HARD LIMIT: 4 HOURS)

## F0 — Clock + baseline

At Flow investigation start:

- record `FLOW_FORENSICS_STARTED_AT` UTC/local;
- set hard deadline = start + 4h;
- verify branch/base/worktree;
- run focused + full regression;
- preserve `85e88cc` live evidence unchanged;
- create fresh evidence dir and immutable mutation ledger.

At/after deadline: no further Flow investigation/mutation. Move to Phase D unless stable route already PROVEN.

## F1 — Reconstruct success-vs-failure matrix

Compare at least:

```text
Dimension                         historical/native success        current failure
---------------------------------------------------------------------------------
project                           a94d36d0...                     f6b40e79...
project age/history               successful R2V lineage          no proven R2V admission
session/profile                   known working UI profile         current profile
frontend build / bl               captured success build           current build
WIZ/session metadata              success                          current
UI mode                           Ingredients/Thành phần           current
UI label                          Veo 3.1 Lite / etc.              current
wire model                        observed success wire id          current wire id
reference origin                  successful project media          current verified media
reference attachment form         success shape                     current shape
prompt serialization              successful single-line form      current
request shape/hash                captured success                  current
response bytes/shape              rich accepted vs null            current null
catalog result                    + durable video                  zero delta
quota/warning banners             success scope                     current
```

Separate OBSERVED, INFERENCE, UNKNOWN. Do not promote reCAPTCHA/risk/gesture/account-scoring hypotheses without evidence.

## F2 — Read-only current-state differential

Compare these known projects when accessible under the same Owner account/session context:

```text
A = a94d36d0-5f95-420d-97b4-dc7cf0c87453
B = f6b40e79-d6f8-4354-80ae-c863260e96f5
```

Allowed reads: sanitized session metadata, catalog/fingerprint, existing successful R2V lineage, current UI model/mode/settings, warning/high-demand banners, project capability/telemetry already exposed by qualified reads, and successful-output record shape.

Do not mutate merely to inspect state.

## F3 — Stable-route definition

`FLOW_STABLE_ROUTE_PROVEN` requires ALL:

1. Current provider-native UI admission route specified exactly.
2. Exact project/session/reference/model/settings envelope known.
3. At least **two distinct fresh shots** through the same route succeed, OR one new success plus an already-current same-route success only if current contract/build equivalence is proven.
4. Each success has exactly one released UI Generate, durable backend output, unique baseline attribution, exact reference/model/project lineage, exact acquisition, technical QC eligibility, and restart=no redispatch.
5. Zero blind retry.
6. No UI/gallery ownership inference.

One lucky output is not enough if route conditions remain unknown.

## F4 — Flow mutation ladder

```text
MAX_NEW_FLOW_GENERATE_RELEASES = 3
```

Each release tests a DISTINCT hypothesis with immutable preclaim ledger.

### F-G1 — Known-success project native-UI control

Prefer historical successful project `a94d36d0-5f95-420d-97b4-dc7cf0c87453` if read-only preflight proves current access and an existing verified reference can be reused without upload.

Question: does current provider-native UI still admit R2V on the historically successful project?

No direct/private RPC mutation.

### F-G2 — Confirm same route

Only if F-G1 is fully PROVEN. Use a second distinct shot through the exact same route to establish repeatability.

### F-G3 — Final differential canary

Only for one specific material unknown that distinguishes a stable route from project-specific failure and only if earlier releases created no ambiguity. Never spend budget for sample size.

### Flow ambiguity stop

If any new Flow Generate ends `EXTERNAL_EFFECT_UNRESOLVED` or attribution ambiguity:

```text
no more Flow Generate
→ preserve evidence
→ classify Flow DEGRADED/UNAVAILABLE
→ Phase D
```

## F5 — 4h decision

Before deadline classify exactly one:

```text
FLOW_STABLE_ROUTE_PROVEN
FLOW_DEGRADED_UNAVAILABLE
FLOW_INCONCLUSIVE_TIMEOUT
OWNER_GATE
```

If not stable, freeze Flow and transition immediately to Dola.

# PHASE D — DOLA / SEEDANCE DOLA FALLBACK

Begins automatically when Flow is not stable by deadline or a new Flow ambiguity ends Flow mutation early.

## D0 — Discovery / truth reconstruction

Do not assume Dola implementation exists merely because config mentions it.

Search repo code/docs/config, Story Auto/AutoVideoPipeline reusable provider/session code, local operator-known Dola/Seedance assets/config, and existing browser profiles/gateway config intended for Dola.

Current SoT recognizes:

```text
provider_id = seedance_dola
transport = browser_cookie_or_gateway
```

Exact model names/versions/contracts MUST be verified at runtime.

Reuse ladder:

```text
SEARCH → REUSE → COMPOSE → ADAPT → EXTEND → BUILD LAST
```

## D1 — Qualification target

Establish smallest replaceable Dola boundary:

```text
ShotSpec / PromptPlan
→ seedance_dola RoutingDecision
→ durable GenerationAttempt / ProviderJob
→ reference/media qualification if required
→ bounded submission
→ stable external job/output identity or deterministic correlation
→ polling/reconciliation
→ exact acquisition
→ generated Asset lineage
→ QC technical eligibility
```

No Dola semantics in Film Core.

## D2 — Dola live authority

```text
MAX_DOLA_GENERATE_RELEASES = 2
```

One reference upload allowed only if current Dola contract genuinely requires it and content can be attested before generation. Max one upload.

No account creation, payment/credit purchase, CAPTCHA bypass, anti-abuse evasion, or provider/account switching without explicit Owner authority.

If human sign-in/2FA/payment/unknown credential is required, stop `OWNER_GATE` with exact requirement.

## D3 — Dola stable-route criteria

`DOLA_STABLE_ROUTE_PROVEN` requires exact current session/gateway scope, observed current model/capability, one successful bounded generation with durable output identity, exact acquisition + Asset lineage + technical QC, zero blind retry, restart/recovery cannot duplicate submission, and preferably second distinct success if repeatability remains material.

If first Dola mutation has ambiguous possible effect, stop Dola mutation; second budget is not retry authority.

# LONG-RUN AUTONOMY

Worker owns HOW. Continue through investigation, local instrumentation, deterministic repairs, tests, read-only reconciliation, bounded authorized mutations, evidence, checkpoint commits, and adversarial self-review. Do not stop for ordinary code/test failures or ask Owner to relay routine steps.

Mandatory checkpoints:

```text
C0 BASELINE
C1 FLOW PRIOR-TRUTH RECONSTRUCTION
C2 FLOW READ-ONLY DIFFERENTIAL
C3 FLOW BOUNDED CANARY/FORENSIC PROOF
C4 FLOW 4H DECISION
C5 DOLA DISCOVERY (if Flow not stable)
C6 DOLA FIRST WORKING / LIVE QUALIFICATION
C7 ADVERSARIAL REVIEW
C8 DELIVERY
```

Local checkpoint commits allowed. Never push or merge.

# HARD CONSTRAINTS

- Never retry exact `LIVE_RUNTIME_QUAL_001` G1 job.
- Never reinterpret `85e88cc` ambiguity as proven rejection/success.
- No direct/private Flow mutation RPC as production path.
- No blind retry on either provider.
- No UI/gallery ownership inference.
- No mutation after ambiguous possible-effect boundary unless resolved read-only.
- No account creation/payment purchase/CAPTCHA bypass/anti-abuse evasion.
- No merge/push.
- No force reset/clean historical/source repos.
- No secrets, cookies, tokens, signed URLs, browser profiles, caches, or raw authenticated responses committed.

# FINAL DELIVERY

Return one consolidated report containing terminal state; Flow start/end/deadline and actual wall time; exact prior evidence consumed; success-vs-failure matrix; every Flow read/write; Flow Generate budget and per-canary hypothesis/result; Flow classification and exact stable route if proven; Dola discovery/contract if pivoted; every Dola read/write; Dola mutation/upload budgets; Dola acquisition/QC evidence; production changes; adversarial findings; focused/full regression; compileall/diff/security; historical custody; remaining UNKNOWNs; exact delivery HEAD; and routing recommendation: Flow, Dola, or neither.

Terminal states:

```text
FLOW_STABLE_ROUTE_PROVEN
DOLA_STABLE_ROUTE_PROVEN
OWNER_GATE
OWNER_AMBIGUITY_GATE
INCONCLUSIVE
```

Never claim stability beyond evidence.
