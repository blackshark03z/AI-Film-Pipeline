# SLICE-0006 — Fresh Flow Live Canary with Durable Dispatch Evidence

## Authorization

Owner explicitly authorizes:

```text
MAXIMUM 5 fresh Google Flow/Veo Generate transactions
```

for this slice.

This is a maximum budget, NOT a requirement to use all 5.

Stop immediately once one full end-to-end canary is PROVEN unless additional execution is strictly necessary to resolve a specific acceptance criterion.

Each Generate must use:

```text
fresh GenerationAttempt
fresh ProviderJob
dispatch_count starts at 0
maximum one Generate per ProviderJob
```

Never redispatch the same attempt.

---

# 1. Starting baseline

Accepted deterministic remediation candidate:

```text
42cc74c2cab1cc0dfb25333d9dc721b4ae79e6df
```

SLICE-0005 status:

```text
PROVEN deterministic
103 tests PASS
```

Known execution semantics:

```text
AT_MOST_ONCE_WITH_POSSIBLE_LOSS
```

Do NOT claim exactly-once.

Prior SLICE-0004 attempt/job remains historical and immutable:

```text
dispatch_count = 1
status = INCONCLUSIVE
```

Never reuse or mutate it.

---

# 2. Proven components already available

Do not redesign these unless live evidence disproves them:

```text
Flow authentication
exact project binding
project preflight
passive response observer
stable response identity baseline
exact identity delta
identity → exact video tile
exact tile → official Download
video technical validation
SHA-256
durable dispatch journal
immutable output binding
download recovery
Asset recovery
restart/no-blind-retry semantics
```

---

# 3. Goal

Prove at least one fresh complete live path:

```text
ShotSpec
→ PromptPlan
→ RoutingDecision
→ GenerationAttempt
→ ProviderJob
→ durable reservation
→ exactly one normal UI Generate
→ durable dispatch evidence
→ sanitized network request/response evidence
→ provider acceptance evidence IF genuinely qualified
→ exact new provider-observed identity
→ immutable identity binding
→ exact video tile
→ official Download
→ ffprobe/media validation
→ SHA-256
→ Asset persistence
→ fresh SQLite lineage readback
```

---

# 4. Five-transaction budget semantics

Maintain a slice-level counter:

```text
live_generate_budget_max = 5
live_generate_transactions_used = N
```

Hard invariant:

```text
0 <= N <= 5
```

A transaction is considered consumed conservatively once its durable dispatch reservation reaches the external-effect boundary.

Never restore budget because:

```text
no output was seen
request evidence was missing
browser crashed
timeout occurred
provider state was ambiguous
```

---

# 5. Per-attempt rules

For attempt K:

```text
Attempt_K
ProviderJob_K
dispatch_count = 0
```

Before Generate require:

```text
preflight READY
exact project binding
stable baseline
no known concurrent generation
observer healthy
journal writable
frozen prompt verified
dispatch_count == 0
```

Then:

```text
reserve
→ dispatch_count = 1
→ exactly one Generate invocation maximum
```

After this point:

```text
NEVER call Generate again for Attempt_K
```

regardless of timeout, exception or ambiguity.

---

# 6. Stop-on-success rule

If an attempt proves:

```text
Generate evidence
+
exact output identity
+
immutable binding
+
official Download
+
technical validation
+
SHA-256
+
Asset
+
fresh lineage readback
```

then:

```text
SLICE-0006 = PROVEN
```

Stop.

Do not spend remaining Generate budget for repetition merely to increase confidence.

---

# 7. Inconclusive-attempt rule

If Attempt_K becomes:

```text
INCONCLUSIVE_EXTERNAL_EFFECT
```

then:

```text
Attempt_K budget consumed
Attempt_K frozen permanently
no retry
```

Before starting Attempt_K+1, prove that the next attempt will not be contaminated by late output from Attempt_K.

Acceptable ways include, in strength order:

```text
provider-visible terminal/failure evidence for Attempt_K

OR

strong isolated execution surface with no possible aliasing

OR

a separately isolated project already authorized/available

OR

another method whose independence is explicitly proven
```

Do NOT proceed merely because the UI currently shows no output.

Remote absence is not proof of zero prior dispatch.

---

# 8. Cross-attempt contamination

This is critical.

If an earlier uncertain attempt could still produce a late response identity in the same project, do NOT start a later attempt in that same correlation domain unless the attribution model can mathematically separate them.

Forbidden:

```text
Attempt_1 uncertain
→ immediately Generate Attempt_2
→ assume first new output belongs to Attempt_2
```

That destroys exact lineage.

If safe isolation cannot be established:

```text
STOP
RESULT = INCONCLUSIVE
remaining budget unused
```

Safety is more important than consuming all 5 transactions.

---

# 9. Provider acceptance qualification

Observe Generate request and response passively.

Persist sanitized facts only.

Possible stages:

```text
RESERVED
PROMPT_VERIFIED
CLICK_ARMED
TRUSTED_CLICK_OBSERVED
GENERATE_REQUEST_OBSERVED
GENERATE_RESPONSE_OBSERVED
PROVIDER_ACCEPTANCE_OBSERVED   # only if independently qualified
REMOTE_IDENTITY_OBSERVED
OUTPUT_BOUND
```

Do NOT infer:

```text
HTTP 200 == provider accepted generation
```

unless the actual Flow contract proves that.

If Flow does not expose a durable acceptance receipt:

record:

```text
provider_acceptance = UNQUALIFIED
delivery_semantics = AT_MOST_ONCE_WITH_POSSIBLE_LOSS
```

This does not automatically fail the E2E canary if output lineage is otherwise proven.

---

# 10. Network evidence

Capture only safe facts:

```text
request observed
safe endpoint/path classification
timestamp
method
safe request fingerprint/hash
response observed
status
safe response fingerprint/hash
provider-observed identity
```

Never persist:

```text
Cookie
Authorization
signed URLs
raw secret-bearing bodies
```

---

# 11. Output attribution

Use the proven Story Auto-derived mechanism:

```text
baseline identities
→ one Generate
→ current identities
→ exact delta
```

Interpretation:

```text
0 new
→ bounded wait/reconciliation

1 new
→ candidate identity

>1 new
→ OUTPUT_ATTRIBUTION_AMBIGUOUS
→ attempt INCONCLUSIVE
```

Never choose via:

```text
latest
newest
first
last
gallery order
DOM position
filename order
```

---

# 12. Binding before acquisition

Mandatory order:

```text
provider-observed identity
→ validate exact attempt ownership
→ immutable bind to ProviderJob/GenerationAttempt
→ persist binding
→ then and only then acquire video
```

A crash after binding must allow:

```text
resume acquisition
```

without Generate.

---

# 13. Official acquisition

Preferred proven path:

```text
bound provider identity
→ exact flow-video-tile
→ exact tile menu
→ official Download
→ 720p
→ expect_download
```

Do not use direct network-byte replay unless separately proven safe and equivalent.

---

# 14. Asset proof

After download:

```text
validate non-empty file
ffprobe
duration > 0
width > 0
height > 0
valid video stream
SHA-256
persist Asset
```

Then perform fresh DB reconstruction/readback.

Required lineage:

```text
ShotSpec
→ PromptPlan
→ RoutingDecision
→ GenerationAttempt
→ ProviderJob
→ ProviderObservedIdentity
→ Asset
```

---

# 15. Recovery cases

If crash occurs:

### After identity binding

Resume only:

```text
exact acquisition
→ validation
→ Asset persistence
```

Never Generate.

### During download

Resume acquisition for the same bound identity only.

### After valid bytes but before Asset DB persistence

Use deterministic recovery:

```text
validate existing owned file
→ verify receipt/hash
→ persist Asset
```

No provider call required if local proof is sufficient.

---

# 16. Attempt loop

Conceptually:

```text
for attempt_number in 1..5:

    create fresh attempt/job

    prove preconditions

    execute at most one Generate

    reconcile

    if complete lineage PROVEN:
        STOP PROVEN

    if attempt safely terminal but no usable output:
        determine whether another fresh attempt is safe

    if attempt uncertain and next attempt cannot be isolated:
        STOP INCONCLUSIVE

STOP after 5 consumed transactions
```

Do not mechanically loop.

Every next attempt requires proof that attribution remains uncontaminated.

---

# 17. No architecture expansion unless live evidence requires it

SLICE-0005 already explored the broad solution space.

Do not redesign the whole adapter during live execution.

However, if live evidence falsifies a deterministic assumption:

```text
stop
capture sanitized evidence
classify root cause
```

Then evaluate alternative solutions broadly before modifying architecture.

Do not tunnel into the first hypothesis.

---

# 18. Acceptance

SLICE-0006 is PROVEN when at least one fresh attempt has:

```text
exactly one Generate maximum
durable dispatch evidence
exact provider output attribution
immutable identity binding
exact official Download
valid video
SHA-256 Asset
complete SQLite lineage
fresh readback
no secret leakage
no gallery-order dependency
no blind retry
```

Provider-native idempotency is NOT required.

Provider acceptance receipt is NOT required unless Flow demonstrably exposes one.

---

# 19. Final report

Return:

```text
RESULT:
PROVEN | INCONCLUSIVE | DISPROVEN

SLICE:
SLICE-0006

GENERATE_BUDGET:
  authorized: 5
  used:
  remaining:

ATTEMPTS:
  - attempt:
    provider_job:
    dispatch_count:
    terminal_state:
    request_observed:
    response_observed:
    provider_acceptance:
    provider_identity:
    asset_sha256:
    contamination_risk:

PROVEN_ATTEMPT:

DISPATCH_PROTOCOL:
  semantics: AT_MOST_ONCE_WITH_POSSIBLE_LOSS
  native_idempotency:
  acceptance_receipt:

OUTPUT_LINEAGE:
  identity_method:
  binding:
  acquisition:
  validation:
  fresh_readback:

REGRESSION:
  tests:

CANDIDATE_SHA:
REMOTE_SHA:
WORKING_TREE:
SECRETS_COMMITTED:
SOT_FILES_CHANGED:

STOP_REASON:
```

Hard maximum:

```text
Generate transactions used <= 5
```