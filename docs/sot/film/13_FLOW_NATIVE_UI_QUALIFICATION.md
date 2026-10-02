# Flow/Veo Native UI Qualification — 2026-10-02

## Status

**QUALIFIED WITHIN OBSERVED SCOPE.**

This record is durable provider truth for V1. It captures what was actually proven by `FLOW-MAX-CAUSAL-FORENSICS-001` and deliberately excludes causal claims that the evidence did not isolate.

Primary evidence:

- branch: `claude/flow-max-causal-forensics-001`
- evidence commit: `29018d3340b85ade788b3aec2963496036cddbe9`
- evidence record: `docs/operating/FLOW_MAX_CAUSAL_FORENSICS_001_EVIDENCE.md`

## Qualified scope

The proven route is scoped to the observed current provider state, not to every Flow account/project/build/model:

```text
provider: Google Flow / Veo
transport: real Google Chrome, headful, provider-native UI automation
account state: clean authenticated Google account with active Flow Pro capability
browser state: isolated clean Chrome profile
Flow frontend build: boq_labs-ai-sandbox-frontend_20260929.10_p1
mode: Video → Ingredients / reference-conditioned generation
wire model observed: veo_3_1_r2v_lite
aspect/output count: 16:9 / x1
reference: exact provider media identity bound before dispatch
correlation: unique [FILM-job_<id>] marker
observation: Zzl0ze catalog reconciliation
media resolution: as29s after render completion
output class proven: 8.0 s, 1280×720 MP4
```

Any material change in account entitlement, project/session state, frontend build, model/mode, request shape, catalog schema, reference binding, or provider behavior requires re-qualification.

## Proven facts

### P1 — Automated provider-native UI generation works in the qualified scope

The agent drove the real Flow UI and released Generate through the provider-native browser path. Two distinct fresh generations completed successfully:

- Release 1 → provider media `11ae2a2f-ca28-4868-ace8-9c519ff0232f`;
- Release 3 → provider media `5b22f89d-8cbd-4593-9b7c-b0c6a7c3cc4b`.

Both outputs were uniquely attributed, acquired as MP4, hashed, and fully decoded through EOF without FFmpeg decode errors.

Therefore a manual human click is **not** an architectural requirement for this qualified Flow route.

### P2 — Durable backend attribution, not UI state, owns the output

A unique Film correlation marker was echoed in durable Flow catalog state and used together with a fresh baseline delta, exact project binding, provider media identity and reference lineage to own the result.

Gallery ordering, newest-card heuristics, DOM position and filename coincidence remain forbidden.

### P3 — Admission and render completion are separate lifecycle states

Release 2 was admitted far enough to receive a unique provider candidate/media identity and visible render progress, but the backend render did not complete and no final downloadable media became available.

Therefore the provider lifecycle must distinguish at least:

```text
DISPATCH_RELEASED
→ ADMISSION_OBSERVED
→ RENDER_PENDING
→ RENDER_COMPLETED
→ ACQUIRED
```

with terminal alternatives such as:

```text
ADMISSION_UNRESOLVED
ADMITTED_RENDER_DROPPED
ACQUISITION_FAILED
```

An admitted request is not equivalent to a completed video.

### P4 — `MZZa6b` HTTP success / optimistic state is not final completion truth

Current evidence shows the mutation response may arrive before render/CDN finalization. `as29s` can be unavailable/NOT_FOUND while rendering is still in progress. Completion requires bounded reconciliation to a uniquely bound completed provider media resource, followed by acquisition and local validation.

### P5 — Current successful Veo 3.1 request shape differs from the older adapter shape

The successful provider-native UI executions exposed the current observed request fingerprint with:

```text
slot 0: plain prompt AST
slot 1: reference media binding
slot 2: current Veo 3.1 wire model identifier
```

The older inline reference-entity prompt shape is not the current qualified Veo 3.1 R2V request fingerprint.

This is **provider-contract evidence only**. Exact protobuf slots/model IDs remain volatile adapter/runtime detail and must not leak into Film Core.

### P6 — Provider-native browser execution is the qualified mutation boundary; direct/private mutation replay is not

The production-qualified boundary is the real provider UI executing its own current frontend/session/security logic. Direct/private `MZZa6b` construction or replay is not a qualified production mutation path.

Read-only backend reconciliation may use the separately qualified catalog/media read paths.

## Observed but not frozen as causal truth

The following were observed and may be diagnostically useful, but the experiment did not isolate them sufficiently to make them architectural causal requirements:

- successful native UI requests contained fresh provider-generated reCAPTCHA Enterprise material;
- automated native UI event telemetry reported trusted browser events in the observed environment;
- the provider frontend generated the current request envelope and session/context values;
- Release 2 used a near-duplicate prompt and later failed to complete render;
- Release 3 used a distinct prompt and completed.

Do **not** freeze the following claims without new controlled evidence:

- "reCAPTCHA is the sole/root cause of historical null responses";
- "`isTrusted` is the admission discriminator";
- "prompt deduplication is a proven provider filter";
- "the clean-account result proves every Flow account/project will behave the same".

## Production execution contract

For the currently qualified `flow_veo` route:

1. Preflight exact account/profile/project/build/model/mode capability.
2. For reference-conditioned generation, verify immutable reference attestation before mutation.
3. Create a durable internal attempt/job and unique Film correlation marker before release.
4. Prepare the request through the provider-native Flow UI; do not synthesize a private mutation RPC as the production path.
5. Release Generate at most once for that attempt.
6. Treat click success, outbound request, HTTP 200, optimistic response state, progress card or gallery item as observations only.
7. Reconcile read-only against a fresh provider baseline and require a unique marker/media binding before assigning ownership.
8. Distinguish admission from render completion. Poll only within a bounded reconciliation window.
9. Resolve final media only for the uniquely bound provider media identity. A temporary `as29s` miss during render is pending evidence, not automatic permission to redispatch.
10. Acquire media, hash immutable local bytes, inspect metadata and perform technical decode validation before producing the canonical Asset.
11. On non-unique identity, missing durable effect, conflicting state or uncertain external effect: fail closed and enter Owner ambiguity handling; never blind-retry.
12. On a uniquely admitted job that later fails rendering: classify it as render failure/drop and route through RepairDecision; do not rewrite history as an admission failure.

## Security / evidence hygiene

Provider session and security material are runtime secrets, not Film truth:

- no cookies in Film Core or committed SoT/runtime config;
- no raw auth headers, session tokens, CAPTCHA tokens or signed CDN URLs in committed durable evidence;
- use sanitized structural fingerprints, lengths, timestamps, non-secret IDs and hashes where diagnostic evidence is needed;
- browser profiles remain provider-local runtime state;
- signed download URLs are ephemeral transport data, never canonical Asset identity.

## Re-qualification triggers

Re-qualify Flow before production mutation when any of these materially change or become ambiguous:

```text
account entitlement / provider health
project/session scope
frontend build / UI flow
model or generation mode
reference binding semantics
request/response structural fingerprint
catalog/media schema
marker echo / ownership semantics
render state interpretation
acquisition path
```

Re-qualification must start from read-only evidence where possible, use bounded live mutation, preserve consumed authority, and never infer success from UI appearance alone.

## Hardening addendum — 2026-10-02 (FLOW-PRODUCTION-HARDEN-MULTISHOT-002)

Evidence-backed additions to this qualification. No historical statement above is modified.

### A1 — Current-build re-qualification PASSED (scope unchanged)

One bounded native-UI generation on the observed current build (bundle revision `boq-labs-ai-sandbox.AiSandboxAngularFrontend.vi.pV88nTU3z_Q.2018.O` era; qualified DOM/settings contract read back identical) completed with unique marker-echo attribution on the first reconciliation poll, exact acquisition, full EOF decode and QC exact-lineage eligibility — same account/profile/project/reference/model/mode scope. The route remains `CURRENT_FLOW_BUILD_REQUALIFIED`.

### A2 — as29s pending payloads may be NON-NULL on the current build

Live observation: while a render is still in progress, `as29s` may return a payload that does NOT conform to the qualified media-resource contract (shape drift), not the historical null signature. Therefore: an as29s response that fails the media contract is **pending evidence**, never failure and never redispatch authority; only a payload that parses and binds for the exact owned identity is completion.

### A3 — Render lifecycle policy (refines P3)

Between binding and completion the durable states are:

```text
OUTPUT_BOUND_UNOBSERVED → RECONCILE_RENDER_STATE
RENDER_PENDING          → RECONCILE_ONLY
RENDER_STATE_UNRESOLVED → RECONCILE_ONLY
RENDER_COMPLETED        → ACQUIRE_ONLY
ADMITTED_RENDER_DROPPED → REPAIR_DECISION_REQUIRED
```

A bound identity is not proof that downloadable media exists. One qualified catalog disappearance is `RENDER_STATE_UNRESOLVED` (eventual consistency / read lag); terminal `ADMITTED_RENDER_DROPPED` requires the disappearance to persist across the bounded reconciliation policy (consecutive qualified observations) or explicit provider terminal evidence. Before terminality: `may_submit = false` and repair-regeneration authority does not exist.

### A4 — Reference adoption (read-only) is a qualified attestation path

Provider project media that already exists (uploaded outside this system) may be adopted as a canonical Film reference through an attested readback: exact media id + project scope + resource binding + byte-identical readback + immutable receipt/attestation chain. Adoption performs zero provider mutation (catalog must be unchanged across it) and is the required path when no upload receipt exists; it never silently substitutes a different resource.

### A5 — Flow Tool runs are catalog-reconcilable (capability, not a production path)

One bounded run of an existing private Flow Tool ("Director's Shot Lab", agent-generated React mini-app using the internal `flow-sdk`) with a preclaimed Film marker inside the tool prompt produced a backend generation that reconciled through the same identity path: exactly one fresh catalog id, unique marker echo, project binding, as29s resolution and exact acquisition. The tool host issued different RPC identifiers (not `MZZa6b`); no claim is made about which wire surface a tool uses. Classification: `FLOW_TOOL_GENERATION_RECONCILABLE` as a **capability observation**; the production mutation path remains the provider-native UI, and any `flow_tool` adapter remains future work requiring its own qualification.

### A6 — Multi-shot vertical proven within the qualified scope

Two distinct ShotSpecs of one coherent scene executed end-to-end through the productized runtime (unique jobs, per-shot at-most-once Generate, marker-echo attribution, hardened render lifecycle, exact acquisition, full decode, QC, provisional SelectedTakes, EditManifest and AutoEdit producer package), both conditioned by the same adopted verified reference. This is the strongest currently proven continuity mechanism (same-reference identity/look continuity); no other continuity control is claimed.
