# FLOW-PRODUCTION-TOOLS-LONGRUN-001 — 6h Productionization + Flow Tools Qualification

## Status
Frozen Owner-directed long-running package.

## Base truth

```text
SoT HEAD: e758f83dacbf742248f5dfe8ce15a8358c440158
Evidence HEAD: 29018d3340b85ade788b3aec2963496036cddbe9
Branch: zcode/flow-production-tools-longrun-001
```

Read first:

```text
docs/sot/film/00_SOT_INDEX.md
docs/sot/film/06_PROVIDER_CAPABILITIES.md
docs/sot/film/08_ASSET_LINEAGE_COST.md
docs/sot/film/11_IMPLEMENTATION_PLAN.md
docs/sot/film/12_DECISION_LOG.md
docs/sot/film/13_FLOW_NATIVE_UI_QUALIFICATION.md
docs/operating/FLOW_MAX_CAUSAL_FORENSICS_001_EVIDENCE.md
```

The SoT is authoritative. Historical reports are evidence, not architecture truth.

## Owner intent

Run autonomously for up to **6 active hours** while the Owner is away.

Do not stop merely because the first implementation passes. Use remaining time for deeper integration, adversarial review, fixture expansion, deterministic recovery, Flow Tools discovery, capability mapping and evidence hardening until either:

```text
ACTIVE_TIME >= 6h
or
all acceptance criteria are genuinely exhausted
or
an external owner/legal/payment/auth gate prevents all remaining useful work
```

If a provider mutation becomes ambiguous, immediately stop **all further provider mutation**, preserve evidence, record `OWNER_AMBIGUITY_GATE`, and continue only read-only/offline work that cannot worsen ambiguity.

## Mission

Deliver two tightly coupled outcomes:

1. **Productize the proven Flow native-UI route** into a reusable, testable provider/runtime boundary consistent with the updated SoT.
2. **Investigate and qualify Flow Tools / custom mini-apps** as a first-party programmable surface for AI-Film, determining whether they can improve orchestration, reference handling, batch generation, project asset persistence or provider integration without relying on brittle external browser mutation logic.

Do not redesign Film Core.

# PHASE 0 — BASELINE / CUSTODY

1. Verify exact base `e758f83...`.
2. Verify worktree/branch cleanliness.
3. Run full current regression using the known project venv if required.
4. Record baseline test count, Chrome version, current qualified profile presence and current SoT manifest verification.
5. Audit tracked repo for leaked cookies, auth headers, raw CAPTCHA/security tokens and signed CDN URLs. Do not print secrets.
6. Preserve historical evidence; do not rewrite old evidence to make it look cleaner than it was.

Checkpoint: `C0_BASELINE_PROVEN`.

# PHASE 1 — INDEPENDENT REVIEW OF STABLE FLOW ROUTE

Audit `FLOW_MAX_CAUSAL_FORENSICS_001` against the new SoT.

Required classifications:

```text
PROVEN
OBSERVED
HYPOTHESIS
UNKNOWN
```

At minimum verify independently:

- Release 1 and Release 3 are distinct successful outputs;
- unique provider media identity and marker-based backend attribution exist;
- output acquisition and full decode evidence exist;
- Release 2 was admitted/candidate-created but not render-completed;
- admission and render completion are not conflated;
- no claim that reCAPTCHA is the sole historical root cause is promoted to SoT;
- no claim that prompt deduplication is proven is promoted to SoT;
- direct/private `MZZa6b` mutation remains outside the production route.

Do not spend a live Generate for this review.

Checkpoint: `C1_ROUTE_REVIEWED`.

# PHASE 2 — PRODUCTIZE THE QUALIFIED FLOW NATIVE-UI ROUTE

Reuse existing code before building new code. Search current implementations including:

```text
flow_r2v_boundary
flow_r2v_runtime
flow_live / flow_network
flow_reference_binding / flow_reference_rpc / flow_reference_transport
OneGenerateGuard / durable dispatch evidence
run_causal_forensics_release1.py
Zzl0ze/as29s parsers
Asset/QC/acquisition helpers
```

Build the smallest production seam that represents the SoT lifecycle:

```text
preflight exact qualified scope
→ durable attempt/preclaim
→ exact reference attestation
→ native UI preparation
→ at-most-once Generate release
→ admission observation
→ durable catalog ownership binding
→ render pending/completed/dropped state
→ media resolution
→ acquisition
→ hash/metadata/full decode
→ Asset/QC or RepairDecision
```

Requirements:

- no direct/private mutation RPC as production path;
- no hard-coded browser profile/account/project in Film Core;
- profile/session paths are runtime provider config;
- no raw cookie export required by production code;
- no CAPTCHA/security token capture/persistence required by production code;
- no signed CDN URL persisted as canonical identity;
- explicit state for `ADMITTED_RENDER_DROPPED` or equivalent;
- `as29s` miss while render pending is not automatic failure/retry;
- restart/recovery cannot redispatch consumed authority;
- marker/project/reference/media binding is deterministic;
- ambiguity fails closed.

Prefer adapting existing tested code over adding a parallel duplicate provider stack.

Add focused deterministic offline tests using sanitized recorded fixtures/mocks.

Checkpoint: `C2_FLOW_NATIVE_ROUTE_PRODUCTIZED`.

# PHASE 3 — FLOW TOOLS / CUSTOM MINI-APP DISCOVERY

Investigate the current first-party Flow Tools/custom mini-app surface from both public documentation and the authenticated product UI where available.

Questions to answer with evidence:

```text
1. Can a user create a custom Tool/mini-app inside Flow?
2. What code/runtime is generated or editable?
3. Can a Tool trigger image/video generation natively?
4. Can it select model/mode/duration/aspect/output count?
5. Can it consume project media/reference identities?
6. Can it create multiple variations/batch work?
7. Are generated media automatically persisted into the current project?
8. Does Tool runtime expose stable job/media/result identifiers?
9. Does it expose a supported SDK/function surface or only opaque UI actions?
10. Can AI-Film pass structured ShotSpec/PromptPlan data into it without manual copy/paste?
11. Can Tool outputs be reconciled using the same Zzl0ze/as29s identity path?
12. What capability gaps remain versus direct native Flow UI generation?
```

Separate:

```text
PUBLICLY_DOCUMENTED
OBSERVED_IN_UI
PROVEN_BY_CODE/READBACK
INFERRED
UNKNOWN
```

Do not call something an API merely because generated code invokes an internal function.

Checkpoint: `C3_FLOW_TOOLS_SURFACE_MAPPED`.

# PHASE 4 — MINIMAL FLOW TOOL CANARY

Only if Flow Tools/custom mini-app creation is clearly available in the existing authenticated clean Pro profile and no payment/legal/account-recovery gate appears.

Authority for this package:

```text
MAX_CUSTOM_TOOL_CREATE_OR_SAVE = 1
MAX_FRESH_VIDEO_GENERATE = 1
```

The video Generate is optional and may be used ONLY if it is necessary to establish Tool generation/output semantics after read-only discovery is complete.

The budget is never retry authority.

Use the existing clean authenticated Chrome profile if still valid. Do not export cookies. Do not automate Google login. If login is lost, record `OWNER_AUTH_GATE` and continue offline/read-only work.

Preferred minimal Tool concept:

```text
AI Film Shot Tool
inputs:
  prompt
  optional project reference asset
  aspect ratio
  duration if exposed
  model/mode if exposed
  output count if exposed
behavior:
  use only first-party Flow capabilities
  persist generated output to current Flow project when supported
```

Do not build a large UI. The goal is capability qualification.

Before any optional live Tool Generate:

1. preclaim a unique Film job marker;
2. capture fresh backend baseline;
3. bind exact project/reference identity;
4. prove Tool invocation is first-party/native and not a hidden direct private replay authored by us;
5. install read-only reconciliation;
6. release at most once.

If external effect or output identity becomes ambiguous:

```text
STOP ALL PROVIDER MUTATION
→ OWNER_AMBIGUITY_GATE
→ no retry
→ continue offline/read-only only
```

If Tool generation succeeds, require unique provider output identity, project persistence, exact acquisition if available, and technical validation.

Checkpoint: `C4_FLOW_TOOL_CANARY` or explicit `C4_NOT_RUN_WITH_REASON`.

# PHASE 5 — ARCHITECTURAL DECISION / ADAPTER SEAM

Based on evidence, choose exactly one current classification:

```text
FLOW_TOOL_PRODUCTION_CANDIDATE
FLOW_TOOL_ASSISTIVE_ONLY
FLOW_TOOL_NO_MATERIAL_VALUE
FLOW_TOOL_INCONCLUSIVE
```

If Tool is useful, define the smallest replaceable adapter seam. Do not put Flow-specific Tool semantics into ShotSpec/Film Core.

Potential architecture only if supported by evidence:

```text
ShotSpec / PromptPlan
→ flow_tool adapter
→ first-party Tool runtime
→ Flow project asset
→ existing backend reconciliation/acquisition
```

If Tool is not useful, preserve the proven native-UI provider route as primary and document why.

Checkpoint: `C5_ARCH_DECISION`.

# PHASE 6 — HARDENING / ADVERSARIAL REVIEW

Use remaining active time up to the six-hour ceiling for aggressive review:

- crash before/after Generate release;
- browser restart after consumed authority;
- render pending across restart;
- renderer drop after admission;
- duplicate/non-unique marker;
- stale project/reference scope;
- frontend build drift;
- media read returns duplicate identical URLs;
- signed URL expiry;
- profile/session missing;
- secret leakage in logs/evidence;
- Tool code/runtime drift;
- Tool output exists in UI but not uniquely backend-bound;
- Tool generation completes but acquisition fails;
- regression against existing Flow R2V boundary and canonical reference attestation.

Add tests for every repaired invariant where practical.

Run:

```text
focused tests
full regression
syntax/compile validation
git diff --check
SoT manifest verification
secret-pattern scan
```

Do not use extra live Generates for adversarial testing.

Checkpoint: `C6_ADVERSARIAL_REVIEW_COMPLETE`.

# STOP CONDITIONS

Stop provider mutation immediately on:

```text
possible external effect with non-unique/unknown identity
submit released but admission/effect unknown
project/reference binding conflict
Tool output attribution conflict
login/payment/legal/identity gate
provider asks for account recovery/2FA
```

Do not bypass CAPTCHA, risk controls, entitlement checks or provider anti-abuse mechanisms.

Do not switch Google account/provider/project as a recovery tactic after ambiguity.

Continue offline/read-only work after a provider-mutation gate whenever safe.

# DELIVERY

Produce:

```text
docs/operating/FLOW_PRODUCTION_TOOLS_LONGRUN_001_EVIDENCE.md
```

and any production code/tests needed.

Final report must include:

- exact base/delivery HEAD and worktree;
- active start/end/wall time;
- checkpoint timeline;
- stable native-UI route implementation delta;
- state-machine delta for admission/render/acquisition;
- focused/full test results;
- Flow Tools capability matrix;
- exact public-doc vs UI-observed vs proven distinctions;
- custom Tool artifact/behavior if created;
- live mutation accounting;
- any Owner gates;
- security/evidence hygiene result;
- unresolved unknowns;
- final Flow Tools classification;
- next recommended slice.

No push.
No merge.
