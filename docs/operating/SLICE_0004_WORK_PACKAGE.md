# WORK PACKAGE — SLICE-0004: SINGLE FLOW/VEO LIVE CANARY & EXACT LINEAGE

**Status:** READY FOR BUILD  
**Lifecycle:** SLICE → BUILD → PROVE  
**Worker authority:** Bounded autonomous execution with one pre-authorized consequential external effect  
**Recommended worker:** GPT-6 Sol / Medium

**Repository:** `blackshark03z/AI-Film-Pipeline`

**Prior PROVEN candidate:**

```text
c2ef1a97920e48348102bea4e4796a4357a2fd31
```

**Prior branch:**

```text
slice-0003-flow-veo-adapter-preflight
```

**Reuse source:**

```text
blackshark03z/AutoVideoPipeline
revision:
826e01866af1b28ed29b6fbb51cabb71f31ef561
```

---

# 1. Tech Lead adjudication

`SLICE-0003 — Accept Core + Flow/Veo Adapter Preflight` is **PROVEN**.

The exact accepted candidate is:

```text
c2ef1a97920e48348102bea4e4796a4357a2fd31
```

Validated architectural properties include:

- Flow is behind a replaceable provider boundary.
- only `READY` health is routable;
- auth/misconfiguration/uncertainty fail closed;
- provider secrets/session paths remain outside Film Core;
- current capability declaration is conservative;
- generation functions remained disabled in SLICE-0003;
- camera movement purpose contract is aligned between JSON Schema and Python model.

---

# 2. Outcome

Prove exactly one real end-to-end Flow/Veo generation path:

```text
Canary ShotSpec
      ↓
canonical validation/hash
      ↓
Prompt Compiler
      ↓
Flow capability profile
      ↓
RoutingDecision
      ↓
GenerationAttempt
      ↓
ProviderJob persisted BEFORE dispatch
      ↓
EXACTLY ONE Flow generation dispatch
      ↓
poll / reconcile
      ↓
exact remote output correlation
      ↓
download
      ↓
technical validation
      ↓
Asset + SHA-256
      ↓
SQLite lineage persistence
      ↓
fresh readback
```

This slice proves **transport + external-effect semantics + lineage**.

It does NOT attempt to prove cinematic quality.

---

# 3. External-effect authorization

By relaying this Work Package, Owner authorizes:

```text
EXACTLY ONE fresh Flow/Veo generation submit transaction
```

under the conditions in this package.

A single provider submit may naturally produce more than one provider-native output if Flow does so as part of one transaction.

The authorization is for:

```text
one submit transaction
```

not:

```text
one retry
one successful video
one output file
```

No second submit is authorized.

---

# 4. Absolute external-effect invariant

The worker MUST maintain:

```text
dispatch_count <= 1
```

for this slice.

After the first external submit:

```text
timeout
network loss
browser crash
poll failure
download failure
ambiguous UI state
```

MUST NOT cause another generation submit.

Instead:

```text
reconcile existing external state
```

or return:

```text
INCONCLUSIVE
```

This is a hard acceptance invariant.

---

# 5. Baseline integration

Before implementing SLICE-0004:

Verify remote:

```text
c2ef1a97920e48348102bea4e4796a4357a2fd31
```

is the exact PROVEN candidate.

If repository topology permits, fast-forward `main` to the exact accepted candidate.

Expected result:

```text
main
→ c2ef1a97920e48348102bea4e4796a4357a2fd31
```

Do not recreate, squash or rewrite the accepted implementation unnecessarily.

Then create:

```text
slice-0004-single-flow-live-canary
```

from that exact accepted code.

If unexpected `main` drift exists:

```text
STOP
→ INCONCLUSIVE_BASELINE_DRIFT
```

---

# 6. Existing Flow credentials/session

Do not request that credentials be pasted into chat, code or Git.

Worker MAY use existing locally authorized Flow state already present on the operator machine, including the existing AutoVideoPipeline configuration/session files.

Worker MAY:

```text
inspect existing configuration paths
resolve existing local cookie/session files
set local environment variables
read local authenticated state
```

only as needed for the authorized provider execution.

Worker MUST NOT:

```text
copy credentials into repository
print cookie/token values
commit session files
upload credentials
extract protected browser tokens
bypass CAPTCHA
bypass login/security controls
```

If a valid session is not already available:

```text
STOP → OPERATOR_AUTH_GATE
```

and report what non-secret action is required.

Do not circumvent authentication.

---

# 7. Mandatory authenticated preflight

Before generation:

```text
FlowVeoProvider.preflight()
```

must establish:

```text
READY
```

against the exact bound Flow project.

Anything else:

```text
AUTH_REQUIRED
MISCONFIGURED
UNAVAILABLE
INCONCLUSIVE
```

means:

```text
NO GENERATION
```

The external-effect budget remains unused.

---

# 8. Live canary ShotSpec

Use a deliberately simple provider-qualification shot.

Do NOT use a character-continuity shot for this transport test.

Create a provider-neutral canary similar to:

```text
shot_id: FLOW_CANARY_001
scene_id: FLOW_CANARY

dramatic_purpose:
  Establish a quiet rain-soaked urban alley at night.

duration_target_s:
  modest provider-supported/default duration

shot_type:
  establishing

characters:
  []

camera:
  framing: WS
  height: eye_level
  lens_intent: wide
  movement:
    type: locked

environment:
  time_of_day: night
  weather: rain
  atmosphere: quiet reflective urban alley

blocking:
  start: static empty alley
  action_beats:
    - rain falls
    - distant reflected light shimmers on wet pavement
  end: same spatial composition

continuity:
  screen_direction: null
  eyeline: null
  start_state: {}
  end_state: {}
  critical_invariants:
    - no people
    - stable alley geography
```

Exact creative wording may be improved without increasing shot complexity.

Do not add dialogue, named characters, reference assets or complex motion.

Persist the canary ShotSpec as non-secret execution evidence.

---

# 9. Live provider implementation

Complete only the minimum real Flow methods required for the canary:

```text
submit()
poll()
fetch_outputs()
```

`cancel()` may remain unsupported unless the existing transport has a safe proven mechanism and it is genuinely required.

Reuse/adapt the established mechanics from:

```text
AutoVideoPipeline@826e01866af1b28ed29b6fbb51cabb71f31ef561
```

Do not build a new generalized browser framework.

---

# 10. ProviderJob

Introduce a runtime `ProviderJob` representation sufficient to preserve external-effect identity.

At minimum record:

```text
provider_job_id           # internal stable ID
generation_attempt_id
provider_id
project binding identity
submission state
submitted_at
external_job_id           # nullable if Flow exposes none
correlation evidence
status
last_checked_at
```

Do NOT put secret/session content inside ProviderJob.

ProviderJob must be persisted **before or atomically around the point of external dispatch** such that crash recovery can know that a submit may already have occurred.

The system must never rely only on in-memory state to remember whether generation was dispatched.

---

# 11. Pre-dispatch evidence snapshot

Immediately before the single submit, record enough non-secret provider state to identify what already existed.

Prefer stable remote identifiers.

For example, where transport mechanics permit:

```text
existing creation IDs
existing video asset IDs
existing output URLs/identities
existing relevant project media identities
```

Do not store temporary secret-bearing URLs if they contain credentials.

Persist:

```text
pre_dispatch_snapshot
```

or equivalent correlation evidence.

---

# 12. Dispatch transaction

Before external submit:

1. ShotSpec is frozen.
2. PromptPlan is frozen.
3. RoutingDecision is frozen.
4. GenerationAttempt is persisted.
5. ProviderJob/submission intent is persisted.
6. authenticated preflight remains READY.
7. `dispatch_count == 0`.

Then perform:

```text
ONE submit transaction
```

Immediately persist:

```text
dispatch_count = 1
submission timestamp
any returned external identifier
non-secret correlation evidence
```

After this point:

```text
NO SECOND SUBMIT
```

under any condition in this slice.

---

# 13. Correlation rule

The generated output MUST be correlated to this exact GenerationAttempt.

Best available evidence order:

```text
1. stable provider external job / creation / asset ID
2. submit response identity linked to later output identity
3. deterministic before/after provider asset-set delta
4. combination of exact project + submission time + unique new remote identity
```

Forbidden:

```text
download latest video
take outputs[0]
choose newest visible gallery item
choose first media element
filename coincidence
```

If one submit results in multiple legitimate provider outputs:

```text
record every correlated output identity
```

Do not identify one by array ordering.

---

# 14. Concurrency ambiguity

Before dispatch, determine whether the bound Flow project has unrelated concurrent generation activity that could destroy exact correlation.

If exact correlation remains possible through stable job/output IDs:

```text
continue
```

If output identification would depend only on "the new/latest item" while other activity may occur:

```text
STOP before dispatch
```

or use a stronger correlation mechanism first.

After dispatch, if multiple unrelated new assets appear and exact ownership cannot be established:

```text
INCONCLUSIVE_EXTERNAL_STATE
```

No retry.

---

# 15. Polling

Polling must apply only to the already-submitted ProviderJob.

Poll until:

```text
SUCCEEDED
known FAILED
or bounded timeout
```

A polling timeout means:

```text
external state uncertain
```

not:

```text
generation failed
```

Then run read-only reconcile against the same ProviderJob/project.

If reconcile cannot establish truth:

```text
INCONCLUSIVE
```

No resubmit.

---

# 16. Crash/restart semantics

This slice must prove enough persistence that the following condition is safe:

```text
submit occurred
→ local worker/process stops
→ process starts again
→ system can determine a dispatch may already exist
→ it does NOT blindly generate again
```

A full durable workflow engine is not required.

Minimal SQLite-backed recovery is sufficient.

Add at least one deterministic test simulating this situation.

---

# 17. Output retrieval

After exact output correlation:

Download only output(s) proven to belong to this ProviderJob.

Store generated media under ignored runtime/project paths.

Do not commit generated MP4s into Git.

For every downloaded output create an Asset record containing at least:

```text
asset_id
origin = generated
local path
provider asset identity if available
source GenerationAttempt
SHA-256
MIME/container information
file size
duration if obtainable
width/height if obtainable
```

---

# 18. Technical media validation

Use an existing reliable mechanism such as `ffprobe` if available.

At minimum establish:

```text
file exists
file non-trivial / non-empty
recognized video container
video stream exists
duration > 0
```

Where practical also record:

```text
codec
width
height
fps
duration
```

A downloaded HTML/error page renamed `.mp4` must not pass.

No creative quality judgment is required for SLICE-0004.

---

# 19. Asset hashing

For every downloaded canary video:

```text
SHA-256
```

must be computed from local immutable bytes.

Fresh readback must prove:

```text
ShotSpec
→ PromptPlan
→ RoutingDecision
→ GenerationAttempt
→ ProviderJob
→ remote output identity
→ Asset
→ SHA-256
```

---

# 20. Persistence

Extend SQLite only as much as required for:

```text
ProviderJob
Asset
external correlation state
```

Do not add:

```text
Postgres
Redis
Temporal
S3
queue service
distributed workers
```

Persistence must preserve exact lineage after reopening the DB.

---

# 21. External-effect state model

Preserve uncertainty explicitly.

ProviderJob/execution state must be able to represent at least:

```text
NOT_SUBMITTED
SUBMITTED
RUNNING
SUCCEEDED
FAILED
INCONCLUSIVE
```

or semantically equivalent states.

Do NOT encode an ambiguous timeout as FAILED.

---

# 22. Existing Film Core preservation

All SLICE-0002 and SLICE-0003 tests must remain green.

Do not modify frozen Film semantics to accommodate Flow.

Provider-specific compromises stay inside the adapter/runtime layer.

---

# 23. Secrets policy

Evidence/logs MUST NOT contain:

```text
cookie values
Google tokens
session contents
private auth URLs
authorization headers
credentials
```

Diagnostic evidence may contain safe values such as:

```text
provider_id
health state
fixed diagnostic code
internal attempt/job IDs
hashes
timestamps
non-secret remote asset IDs
```

Project ID should be redacted in public/log evidence unless operationally required.

---

# 24. External-effect budget test

Implement a deterministic fake/mock transport test proving:

```text
first submit
→ dispatch counter becomes 1

then timeout/error/restart/reconcile
→ submit is NOT called again
```

The test must demonstrate the no-blind-retry invariant at the provider execution layer.

---

# 25. Acceptance claims

Acceptance is immutable for this attempt.

## A — Prior PROVEN candidate preserved

SLICE-0003 behavior remains green.

## B — Authenticated provider is READY

Real Flow preflight returns READY before dispatch.

## C — Exactly one submit

Observed Flow generation submit transactions:

```text
1
```

Not 0 for a successful PROVEN canary.

Not >1 under any circumstances.

## D — No blind retry

Timeout/error/restart path does not dispatch another generation.

## E — Exact correlation

Every downloaded output used as evidence is proven to belong to the single ProviderJob.

## F — Persisted external identity

ProviderJob survives DB reopen with enough identity/evidence for reconciliation.

## G — Valid media

At least one correlated output downloads as a valid video with duration > 0.

## H — Asset SHA-256

Downloaded asset has deterministic SHA-256 and persisted lineage.

## I — Fresh readback

A new SQLite handle reconstructs exact:

```text
ShotSpec
PromptPlan
RoutingDecision
GenerationAttempt
ProviderJob
Asset
```

lineage.

## J — Secret hygiene

No secret/session material appears in Git or final evidence.

## K — Provider isolation

Flow-specific state remains outside Film Core creative models.

## L — Regression

Full deterministic test suite passes.

---

# 26. Result semantics

Return:

```text
PROVEN
```

only if one submit occurred and exact correlated valid output lineage was established.

Return:

```text
DISPROVEN
```

when trusted evidence establishes that the candidate implementation violated acceptance, for example:

```text
>1 submit
wrong output downloaded
lineage corruption
known implementation failure
secret leakage
```

Return:

```text
INCONCLUSIVE
```

when external truth cannot safely be established, for example:

```text
submit may have happened but response was lost
output ownership cannot be determined
timeout with unresolved remote state
provider UI changed and correlation is ambiguous
```

INCONCLUSIVE must never cause a second generation.

---

# 27. Internal gates

## Gate 0 — Integrate prior candidate

```text
main@c2ef1a97920e48348102bea4e4796a4357a2fd31
```

or exact safe equivalent proven.

Create SLICE-0004 branch.

---

## Gate 1 — Regression before live work

Run all existing tests.

PASS required.

---

## Gate 2 — Provider runtime implementation

Implement:

```text
ProviderJob
Flow submit
Flow poll/reconcile
Flow output discovery/download
Asset persistence
```

using fake transport tests first.

No live dispatch yet.

---

## Gate 3 — No-retry/recovery proof

Fake transport proves:

```text
dispatch <= 1
```

through timeout/restart/reconciliation scenarios.

---

## Gate 4 — Authenticated live preflight

```text
Flow = READY
```

PASS required.

If not READY:

```text
STOP without generation
```

---

## Gate 5 — Pre-dispatch freeze

Persist:

```text
ShotSpec
PromptPlan
RoutingDecision
GenerationAttempt
ProviderJob intent
pre-dispatch provider snapshot
```

Verify:

```text
dispatch_count = 0
```

---

## Gate 6 — SINGLE LIVE DISPATCH

Perform exactly:

```text
1 Flow generation submit
```

Persist effect evidence immediately.

After this gate, no retry authorization exists.

---

## Gate 7 — Poll / reconcile

Establish remote terminal state or preserve uncertainty.

---

## Gate 8 — Exact output correlation

PASS only with exact evidence.

---

## Gate 9 — Download / validate / hash

At least one correlated valid video:

```text
download
→ inspect
→ SHA-256
→ Asset
```

---

## Gate 10 — Lineage readback

Fresh DB read reconstructs the full path.

---

## Gate 11 — Regression

Full tests pass.

---

## Gate 12 — Candidate freeze

Create exact commit.

Working tree clean.

Push feature branch.

Remote SHA readback matches.

STOP.

---

# 28. Stop conditions BEFORE dispatch

Stop before any generation if:

- prior candidate integration is unsafe;
- existing tests fail;
- Flow authenticated preflight is not READY;
- cookie/session state is unavailable;
- correlation mechanism cannot distinguish the canary output;
- unrelated Flow activity makes exact output ownership impossible;
- implementation would require bypassing security/CAPTCHA;
- secrets would need to enter Git;
- System Truth needs changing;
- dispatch counter safety cannot be proven.

External-effect budget remains zero.

---

# 29. Stop conditions AFTER dispatch

After the first submit, never submit again.

Stop/reconcile if:

- browser crashes;
- submit response is lost;
- polling times out;
- provider changes UI;
- result appears ambiguous;
- download fails;
- more than one unrelated output appears;
- external state cannot be proven.

If read-only reconciliation cannot solve ambiguity:

```text
RESULT = INCONCLUSIVE
```

---

# 30. Explicitly out of scope

Do NOT add:

```text
second generation attempt
quality retry
Seedance/Dola/Elyum
character consistency evaluation
automatic VLM QC
RepairDecision loop
Gemini director
rough-cut assembly
Resolve
web UI
multi-shot benchmark
Postgres/Redis/Temporal
3D/image generation
```

The purpose is one external canary only.

---

# 31. Git policy

Generated media/runtime DB/session/cookies remain uncommitted.

Commit:

```text
source code
tests
non-secret canary ShotSpec
safe evidence summary
runtime schemas/migrations
reuse notes if changed
CURRENT_SLICE / IMPLEMENTATION_STATUS
```

Do not commit:

```text
MP4
cookies
sessions
local DB
browser profiles
raw authenticated dumps
```

---

# 32. Final evidence

Final report must state:

```text
RESULT

PRIOR_PROVEN_SHA
MAIN_AFTER_INTEGRATION_SHA
CANDIDATE_SHA
BRANCH
REMOTE_SHA

FLOW_PREFLIGHT:
state
safe diagnostic code

CANARY:
shot_id
shot_spec_hash
prompt_plan_hash
routing_decision_id
generation_attempt_id
provider_job_id

EXTERNAL_EFFECT:
dispatch_count
submitted_at
external_job_id if available
terminal provider state

CORRELATION:
method
remote output IDs
why ownership is exact

ASSETS:
asset_id
safe filename
file size
duration
resolution
SHA-256

PERSISTENCE:
fresh readback PASS/FAIL

TESTS:
full result

SECRETS_COMMITTED:
NONE

EXTERNAL_EFFECTS:
Flow submit transactions: <must equal 1 for PROVEN>

SOT_FILES_CHANGED:
NONE

OPEN_ISSUES

TRUTH_CHALLENGES

NEXT
```

Never print credential values.

---

# 33. Final report format

```text
RESULT: PROVEN | DISPROVEN | INCONCLUSIVE

SLICE:
SLICE-0004 — Single Flow/Veo Live Canary & Exact Lineage

PRIOR_PROVEN_SHA:
MAIN_AFTER_INTEGRATION_SHA:
CANDIDATE_SHA:
BRANCH:
REMOTE_SHA:

GATES:
0 Prior integration: PASS/FAIL
1 Pre-live regression: PASS/FAIL
2 Provider runtime implementation: PASS/FAIL
3 No-retry/recovery proof: PASS/FAIL
4 Authenticated Flow preflight: PASS/FAIL
5 Pre-dispatch freeze: PASS/FAIL
6 Single live dispatch: PASS/FAIL
7 Poll/reconcile: PASS/FAIL/INCONCLUSIVE
8 Exact correlation: PASS/FAIL/INCONCLUSIVE
9 Media validation/hash: PASS/FAIL
10 Full lineage readback: PASS/FAIL
11 Regression: PASS/FAIL
12 Candidate freeze: PASS/FAIL

FLOW_PREFLIGHT:
state:
diagnostic:

CANARY:
shot_id:
shot_spec_hash:
prompt_plan_hash:
routing_decision_id:
generation_attempt_id:
provider_job_id:

EXTERNAL_EFFECT:
dispatch_count:
submitted_at:
external_job_id:
terminal_state:

CORRELATION:
method:
remote_output_ids:
evidence:

ASSETS:
- asset_id:
  filename:
  size:
  duration:
  resolution:
  sha256:

TESTS:
- ...

SECRETS_COMMITTED:
NONE

EXTERNAL_EFFECTS:
Flow generation submit transactions: <0 or 1>

SOT_FILES_CHANGED:
NONE

OPEN_ISSUES:
- ...

TRUTH_CHALLENGES:
- NONE
or
- ...

NEXT:
Ready for Tech Lead PROVE / next slice
or
Must not proceed
```

Do not begin another generation or SLICE-0005 automatically.