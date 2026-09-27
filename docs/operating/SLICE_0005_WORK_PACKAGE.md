# SLICE-0005 — Durable Flow Dispatch Evidence & Recovery Semantics

## Context

Prior slice:

`SLICE-0004 — Single Flow/Veo Live Canary & Exact Lineage`

ended:

```text
INCONCLUSIVE_EXTERNAL_EFFECT
```

The single-submit budget was consumed conservatively.

Do NOT reuse that ProviderJob.

Do NOT rewrite its history.

Known proven facts:

```text
Flow authentication                    PROVEN
Bound project preflight                 PROVEN
Passive response identity baseline      PROVEN
Exact response identity delta model     PROVEN deterministically
Identity → exact video tile             PROVEN live
Exact tile → official Download          PROVEN live
Official downloaded video validation    PROVEN live
No gallery ordering dependency          PROVEN
```

Unresolved:

```text
After durable local dispatch reservation,
did the external Generate transaction actually occur?
```

The prior attempt ended with:

```text
dispatch_count = 1
submission_state = SUBMISSION_RESERVED
confirmed_generate_transactions = UNKNOWN (0 or 1)
```

No redispatch is authorized for that attempt.

---

# 1. Goal

Design and prove the strongest practical dispatch/recovery protocol available for Google Flow browser transport.

Primary question:

> After a crash, timeout, browser failure, process failure, or transport exception around Generate, how much can the system prove about whether the external effect occurred?

Do not assume the answer is merely "add more local logging".

Explore the full solution space first.

---

# 2. Mandatory exploration before implementation

Use:

```text
SEARCH
→ REUSE
→ COMPOSE
→ ADAPT
→ BUILD LAST
```

Investigate all relevant existing implementations before choosing the protocol.

Primary brownfield sources:

```text
D:\Story Auto\story-auto
D:\Video\AutoVideoPipeline
```

Also inspect current AI-Film-Pipeline source.

Search conceptually for:

```text
idempotency
request id
request_id
operation
operation_id
creation
generation
submit
dispatch
acceptance
response
RPC
XHR
fetch
mutation
retry
reconcile
receipt
client token
nonce
request token
provider identity
```

Do not limit investigation to filenames already known.

---

# 3. Solution-space lanes

Evaluate all lanes below.

## Lane A — Provider-native operation/idempotency identity

Highest priority.

Inspect the actual Generate network transaction and determine whether Flow sends or returns any stable value such as:

```text
request identifier
client-generated request token
operation identifier
creation identifier
mutation identifier
provider correlation token
```

Do NOT assign semantic names to unknown UUIDs without proof.

Questions:

```text
Does the Generate request contain a unique client value?
Does Flow return a stable operation/creation identity?
Can that identity later be queried or observed?
Does repeating an identical request with the same identity deduplicate?
```

Do NOT experimentally replay a consequential Generate request merely to test idempotency.

Only use passive observation or non-consequential evidence unless explicitly authorized later.

If provider-native idempotency exists and is safely usable:

prefer it over all browser-derived approximations.

---

## Lane B — Generate network request/response receipt

Determine whether the browser click produces an observable request that itself proves external dispatch.

Arm request/response observers BEFORE click.

Potential evidence:

```text
Generate request observed
request fingerprint
request timestamp
request body safe hash
bound project
HTTP/provider response received
provider acceptance response
returned provider identity
```

Persist only sanitized evidence.

Never persist:

```text
cookies
Authorization
signed URLs
raw secret-bearing payloads
```

If a request can be proven to have left the browser, distinguish:

```text
CLICK_OBSERVED
REQUEST_OBSERVED
PROVIDER_RESPONSE_OBSERVED
```

These are not equivalent.

---

## Lane C — Durable local dispatch journal

Evaluate stage-by-stage local durability.

Possible states:

```text
NOT_RESERVED

RESERVED

PROMPT_VERIFIED

CLICK_ARMED

TRUSTED_CLICK_OBSERVED

GENERATE_REQUEST_OBSERVED

PROVIDER_ACCEPTANCE_OBSERVED

REMOTE_IDENTITY_OBSERVED

SUBMITTED
```

Do not add all states unless each materially improves recovery semantics.

The journal must be:

```text
append-safe or monotonic
durable
crash-readable
attempt-scoped
immutable where possible
```

Every state must have a precise meaning.

---

## Lane D — Remote post-crash reconciliation

Explore what can be learned after losing the original browser process.

Given:

```text
exact project
exact attempt
exact prompt hash / correlation marker
pre-dispatch network baseline
known reservation
```

determine whether a fresh authenticated browser can establish:

```text
no provider operation exists
one exact operation/output exists
multiple ambiguous operations exist
unknown
```

Possible evidence:

```text
response identities
project operation metadata
video tiles
prompt history
provider activity indicators
creation timestamps
remote operation state
```

Remote absence must NOT automatically mean zero dispatch.

Define precisely when absence can and cannot prove anything.

---

## Lane E — Isolation as a proof amplifier

Evaluate dedicated-project/single-flight semantics.

For a controlled canary or production execution mode:

```text
one bound project
one active GenerationAttempt
stable empty/known baseline
no concurrent generation
```

Determine what this isolation lets reconciliation prove that a shared project cannot.

Do NOT rely on isolation alone if provider evidence remains ambiguous.

---

## Lane F — Conservative at-most-once fallback

If Flow exposes no sufficiently durable provider receipt or idempotency mechanism:

retain:

```text
reserve-before-side-effect
+
never blind retry after uncertainty
```

This means some generations may be lost.

That is acceptable if the alternative is duplicate external effects.

Document this explicitly as:

```text
AT_MOST_ONCE_WITH_POSSIBLE_LOSS
```

not "exactly once".

Never claim mathematical exactly-once semantics unless provider capabilities actually support it.

---

# 4. Important architecture distinction

Separate three concepts:

```text
Dispatch Intent
External Dispatch Evidence
Output Attribution
```

They are different.

Example:

```text
reservation persisted
```

proves Dispatch Intent.

```text
Generate request observed leaving browser
```

proves stronger external-effect evidence.

```text
provider acceptance response
```

is stronger still.

```text
new provider response identity
```

supports Output Attribution.

Do not collapse these into one `SUBMITTED` boolean.

---

# 5. Required failure-window analysis

Model at least these crash points:

```text
F0 before reservation

F1 after reservation
   before prompt fill

F2 after prompt fill
   before click

F3 during click
   before request observable

F4 request leaves browser
   before provider response

F5 provider accepts
   before local durable acceptance write

F6 provider identity appears
   before local binding write

F7 binding persisted
   before download

F8 during download

F9 after download
   before Asset persistence
```

For every window define:

```text
what local evidence exists
what remote evidence may exist
whether redispatch is allowed
whether reconciliation is possible
terminal classification
```

---

# 6. Desired recovery matrix

Produce a table conceptually like:

```text
Evidence                                 Recovery

reservation only                         reconcile; never blind retry

trusted click only                       reconcile; no retry

Generate request observed                reconcile; no retry

provider acceptance observed             mark dispatched; reconcile output

provider identity observed               bind exact identity

identity binding persisted               resume acquisition only

validated download exists                persist/recover Asset

ambiguous remote state                   INCONCLUSIVE
```

Do not hardcode these conclusions before investigation; validate them against actual Flow behavior.

---

# 7. Reuse Story Auto where applicable

Story Auto already provides strong mechanisms for:

```text
passive response observation
quiescent baseline
exact identity delta
dispatch evidence concepts
identity binding
exact video acquisition
```

Reuse these semantics rather than rewriting them.

But independently inspect whether Story Auto has stronger dispatch evidence/recovery behavior than the current AI-Film port.

If Story Auto solved a failure window already:

reuse it.

---

# 8. Current AI-Film issue to correct

Current runtime effectively has:

```text
reserve durable
→ transport.submit()
→ transport returns all evidence
→ persist SUBMITTED
```

This creates an uncertainty interval covering the whole transport call.

The new design should minimize that interval.

Do NOT simply move `submitted_at` earlier.

Persist only evidence that has actually occurred.

---

# 9. Provider-side observation preferred over UI observation

Evidence strength order:

```text
provider-native idempotency/operation identity
>
provider network acceptance/receipt
>
provider response identity
>
browser trusted event
>
DOM transition
>
timing/UI heuristics
```

Prefer stronger evidence whenever available.

UI evidence may complement network evidence but should not override it.

---

# 10. No consequential live Generate during initial BUILD/PROVE

This slice begins with:

```text
code inspection
network-model inspection
deterministic implementation
tests
failure simulation
```

No fresh live Generate is automatically authorized.

Existing media/download diagnostics may be used read-only where useful.

A new live canary requires a fresh explicit authorization after deterministic proof is complete.

---

# 11. Deterministic proof requirements

Add tests covering at least:

```text
crash after reserve
crash before click
crash after trusted click
crash after Generate request observation
crash after provider acceptance
crash after provider identity observation
crash after identity binding
crash during download
crash after valid download before Asset persistence
```

Also prove:

```text
restart never causes blind Generate
reconciliation never creates a second submit
journal states cannot move backwards
ambiguous evidence fails closed
provider identity cannot be rebound to a different attempt
download can resume without Generate after identity binding
```

---

# 12. Investigate recovery of already-downloaded media

If exact provider identity is bound and a valid downloaded file exists but DB Asset persistence failed:

the system should preferably be able to:

```text
validate existing immutable file
→ SHA-256
→ reconstruct/persist Asset
```

without downloading or generating again.

Prove this deterministically.

---

# 13. Architecture decision output

Before implementation is accepted, write an explicit comparison:

```text
OPTION_A_PROVIDER_IDEMPOTENCY
availability:
strength:
cost:
selected/rejected:

OPTION_B_NETWORK_RECEIPT
availability:
strength:
cost:
selected/rejected:

OPTION_C_DURABLE_JOURNAL
availability:
strength:
cost:
selected/rejected:

OPTION_D_REMOTE_RECONCILIATION
availability:
strength:
cost:
selected/rejected:

OPTION_E_ISOLATED_PROJECT
availability:
strength:
cost:
selected/rejected:

OPTION_F_AT_MOST_ONCE_FALLBACK
availability:
strength:
cost:
selected/rejected:
```

Then state the composed protocol actually chosen.

---

# 14. Keep architecture minimal

Do not build a generic distributed transaction framework.

This is a Flow adapter problem.

Prefer the smallest protocol that closes the proven failure windows.

No Kafka.
No workflow engine.
No new distributed datastore.
No custom orchestration framework.

SQLite remains acceptable unless evidence proves otherwise.

---

# 15. Prior SLICE-0004 history

Never mutate:

```text
attempt_c4c8...
job_f1f239...
dispatch_count = 1
INCONCLUSIVE
```

Treat it as historical evidence.

No reset.

No attempt reuse.

No second Generate for it.

---

# 16. Acceptance

This slice is PROVEN only when:

```text
full solution space was evaluated
chosen dispatch evidence protocol is explicit
failure-window matrix is complete
durable implementation passes deterministic crash tests
no restart path can blind-submit
network identity/output attribution remains intact
official Download path remains exact
prior INCONCLUSIVE attempt remains untouched
```

A live generation is NOT required to prove the deterministic remediation itself.

---

# 17. End-of-slice recommendation

After deterministic PROVEN status, report whether a fresh live canary is justified.

If yes, specify exactly what new evidence the live canary must prove:

```text
fresh attempt
→ durable reservation
→ Generate transaction evidence
→ provider acceptance evidence
→ exact new response identity
→ persisted identity binding
→ exact official download
→ technical validation
→ SHA-256
→ Asset
→ fresh SQLite lineage readback
```

Do not execute it without fresh authorization.

Do NOT begin QC work yet.