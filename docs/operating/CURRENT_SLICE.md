# WORK PACKAGE — SLICE-0003: ACCEPT CORE + FLOW/VEO ADAPTER PREFLIGHT

**Status:** READY FOR BUILD  
**Lifecycle:** BOUND delta → SLICE → BUILD → PROVE  
**Worker authority:** Bounded autonomous execution  
**Recommended worker:** GPT-6 Sol / Medium

**Repository:** `blackshark03z/AI-Film-Pipeline`  
**Proven candidate:** `7041252d9e6b0c6bc7589d606fe30f45b302c1b8`  
**Candidate branch:** `slice-0002-film-core-vertical-skeleton`

---

# 1. Tech Lead adjudication

`SLICE-0002 — Film Core Vertical Skeleton` is **PROVEN**.

The exact candidate accepted by Tech Lead is:

```text
7041252d9e6b0c6bc7589d606fe30f45b302c1b8
```

The next slice may proceed only from the exact accepted Film Core.

---

# 2. BOUND delta — schema representation alignment

This is NOT a change to Film System Truth.

Frozen Film Truth already states:

> A camera movement other than `locked` requires a dramatic purpose.

The Python domain model enforces this invariant, but the current ShotSpec JSON Schema still permits a moving camera with `purpose: null`.

Align the machine-readable JSON Schema with the already-frozen invariant.

Required semantic outcome:

```text
movement.type == locked
→ purpose may be absent/null

movement.type != locked
→ purpose must be a non-empty string
```

Do not change the underlying cinematic rule.

Add regression evidence proving JSON Schema and Python validation now agree.

---

# 3. Outcome

Establish the first **real provider boundary** without performing video generation.

Target vertical path:

```text
PROVEN Film Core
      ↓
ProviderCapabilities
      ↓
Flow/Veo Adapter
      ↓
existing AutoVideoPipeline mechanics
      ↓
local configuration/session boundary
      ↓
read-only preflight / doctor
      ↓
normalized ProviderHealth
```

The goal is to prove that Google Flow can be connected as a replaceable production engine **without leaking browser/cookie/session implementation into Film Core**.

No video is generated in this slice.

---

# 4. Reuse source

Primary brownfield reuse source:

```text
blackshark03z/AutoVideoPipeline
```

Worker must inspect the current accessible repository and record the **exact source revision** used for analysis/reuse.

Relevant existing concepts known to be worth inspecting include:

```text
Flow/Veo client
session/cookie handling
project binding
preflight
cookie expiry validation
FlowVideoGenerator
download/correlation mechanics
doctor/health patterns
```

Do not blindly copy its architecture.

Use:

```text
SEARCH
→ REUSE
→ COMPOSE
→ ADAPT
→ EXTEND
→ BUILD LAST
```

Extract only the mechanics needed behind the new provider contract.

`AutoVideoPipeline` is an implementation/reuse source, NOT System Truth for the new project.

---

# 5. Baseline integration

Before feature implementation:

1. Verify the proven candidate SHA exists remotely.
2. Ensure `main` has not acquired unexpected divergent work.
3. Integrate the exact proven Film Core into `main`.

Preferred if topology permits:

```text
fast-forward main
→ 7041252d9e6b0c6bc7589d606fe30f45b302c1b8
```

The exact accepted code should not be unnecessarily rewritten or recreated.

After integration, create a new isolated branch for SLICE-0003.

Recommended:

```text
slice-0003-flow-veo-adapter-preflight
```

If `main` has unexpected drift or cannot safely integrate the exact proven candidate:

```text
STOP → INCONCLUSIVE_BASELINE
```

Do not silently rebase onto unknown work.

---

# 6. In scope

## 6.1 Provider contract

Introduce or formalize the provider layer appropriate for a real adapter.

At minimum it must conceptually support:

```text
capabilities()
preflight()
submit()
poll()
fetch_outputs()
cancel()
```

Only `capabilities()` and `preflight()` need real implementation for Flow in this slice.

Other methods may deliberately return a clear:

```text
NOT_IMPLEMENTED_IN_SLICE_0003
```

They must not accidentally trigger provider mutations.

Implementation structure belongs to the worker.

---

## 6.2 Flow/Veo adapter

Create a replaceable Flow/Veo provider adapter.

Film Core must interact with Flow only through this boundary.

Forbidden leakage into Film Core:

```text
cookies
session files
browser selectors
Flow project IDs
private transport URLs
browser/CDP implementation
download-page ordering
```

These are adapter/runtime concerns.

---

## 6.3 Provider health model

Normalize preflight into a provider-neutral health result.

It should distinguish at least conceptually:

```text
READY
UNAVAILABLE
AUTH_REQUIRED
MISCONFIGURED
INCONCLUSIVE
```

Include useful evidence/diagnostic data without exposing secrets.

Do not collapse ambiguous remote state into READY or FAILED.

---

## 6.4 Real capability profile

Create a Flow/Veo capability profile based only on capabilities actually established from:

```text
existing working transport
+
observed implementation
+
verified provider behavior/documentation where available
```

Do not invent model/version capabilities.

If a capability is not established, fail closed.

For the current boolean capability representation:

```text
unverified
→ false
```

and record the uncertainty in notes/evidence.

Do not treat `false` as proof that the underlying Veo product universally lacks that feature; it means the current adapter profile has not established usable support.

Exact model/tier name remains runtime information.

---

## 6.5 Configuration/secrets boundary

Secrets must stay outside Git.

Allowed mechanisms include environment variables and ignored local secret/session paths.

Repository may contain only examples such as:

```text
FLOW_COOKIE_PATH
FLOW_SESSION_PATH
```

Never:

```text
real cookie values
session tokens
API keys
authenticated browser storage
```

Tests must not need real secrets.

---

## 6.6 Read-only preflight

If an already-configured local Flow session is available, worker MAY perform a **read-only** provider preflight.

Allowed read-only effects:

```text
validate configuration
load local session metadata
check cookie/session validity
verify expected project/account binding
perform non-mutating health/readback required by preflight
```

Not authorized:

```text
create video
submit generation
delete project
modify Flow project
refresh credentials through bypass mechanisms
solve CAPTCHA
bypass anti-bot/security checks
extract protected tokens
```

If authenticated preflight requires manual login, CAPTCHA, fresh credential acquisition, or unavailable operator action:

```text
do not bypass
→ report AUTH_REQUIRED / INCONCLUSIVE
```

A real authenticated Flow session is NOT required for the implementation portion to pass.

The adapter must remain testable with fake/mocked transport state.

---

# 7. Existing AutoVideoPipeline reuse evidence

Worker must produce a small reuse record containing:

```text
source repository
source revision
source files inspected

REUSED:
- ...

ADAPTED:
- ...

NOT REUSED:
- ...

WHY:
- ...
```

Do not copy large modules merely because they already exist.

Prefer extracting stable mechanics behind the Film provider interface.

---

# 8. Explicitly out of scope

Do NOT perform:

```text
Flow/Veo video generation
paid generation
Seedance
Dola integration
Elyum integration
automatic QC
RepairDecision execution
asset downloading from a new generation
rough cut
Gemini runtime calls
web UI
Postgres/Redis/Temporal
3D
image generation
fine-tuning
```

Do not implement speculative generalized browser automation infrastructure.

---

# 9. Acceptance claims

Acceptance is immutable for this execution attempt.

## A — Proven Film Core preserved

The exact accepted behavior from SLICE-0002 remains green.

---

## B — Schema alignment

JSON Schema and Pydantic both reject:

```text
movement != locked
+
missing/null/empty purpose
```

and permit a locked shot without a movement purpose.

Existing canonical fixtures still pass.

---

## C — Provider boundary exists

Flow implementation is isolated behind a replaceable provider interface.

No Flow/browser/session semantics enter ShotSpec or other creative Film State.

---

## D — No secrets committed

Repository contains no live Flow credential/session material.

---

## E — Capability profile is conservative

Only established current-adapter capabilities are enabled.

Unknown/unverified capability is not silently marked supported.

---

## F — Preflight is normalized

Synthetic preflight tests prove conversion into provider-neutral health states.

At minimum cover:

```text
ready
auth/session missing
misconfigured
ambiguous/inconclusive
```

---

## G — Fail closed

Unavailable or uncertain Flow transport cannot be routed as healthy/ready.

---

## H — Brownfield reuse is evidenced

The worker records exact AutoVideoPipeline revision and what was reused/adapted/rejected.

---

## I — No generation occurs

No video-generation request is submitted in SLICE-0003.

---

## J — Regression stays green

All previously proven Film Core tests and new adapter tests pass.

---

# 10. Required tests

At minimum:

```text
schema camera-purpose invariant
Flow capabilities mapping
Flow preflight READY mapping
missing-session/auth mapping
misconfiguration mapping
INCONCLUSIVE mapping
no-secret fixture/config behavior
Film Core regression
```

External network tests must be isolated from deterministic unit tests.

A live read-only preflight, if performed, is evidence in addition to tests, not a replacement for them.

---

# 11. Required evidence

Final report must include:

```text
starting main SHA
SLICE-0003 branch
candidate SHA
remote SHA if pushed

AutoVideoPipeline source revision
reuse record

schema-alignment proof
full test result
changed-file inventory
Flow boundary explanation
capability profile evidence

whether real read-only preflight was attempted:
YES / NO

if YES:
provider health result
non-secret evidence

secret scan
git status
```

No cookie/token value may appear in evidence.

---

# 12. Worker authority

Worker MAY autonomously:

```text
fast-forward main to exact PROVEN candidate if safe
create SLICE-0003 branch
inspect/clone/read AutoVideoPipeline
selectively reuse code
add provider modules
refactor local provider abstraction
align JSON Schema to existing frozen rule
add tests
add example config
run read-only Flow preflight if existing credentials are already locally available
push candidate feature branch
perform non-destructive GitHub readback
```

Worker does not need Owner relay for routine engineering decisions inside these boundaries.

---

# 13. Not authorized

Worker MUST NOT:

```text
generate a video
perform paid provider action
merge completed SLICE-0003 candidate to main
force push
make repository public
commit credentials
obtain/bypass CAPTCHA
bypass provider security
modify frozen Film/System truth
start Seedance work
begin SLICE-0004
```

---

# 14. Internal gates

## Gate 0 — Accept prior candidate

```text
7041252... verified
→ safely integrated into main
→ new slice branch created
```

## Gate 1 — Contract alignment

```text
camera-purpose JSON Schema
↔
Pydantic invariant
```

PASS.

## Gate 2 — Reuse discovery

```text
AutoVideoPipeline exact revision frozen
relevant mechanics identified
reuse decision recorded
```

## Gate 3 — Provider abstraction

```text
Film Core
→ generic provider boundary
→ Flow adapter
```

No transport leakage.

## Gate 4 — Capability mapping

Conservative capability profile validated.

## Gate 5 — Preflight tests

All normalized health states pass deterministic tests.

## Gate 6 — Optional real read-only preflight

If locally possible without new authority:

```text
existing Flow session
→ adapter preflight
→ normalized health
```

No generation.

If unavailable:

```text
record NOT_RUN / AUTH_REQUIRED
```

This alone does not fail the slice.

## Gate 7 — Regression

Full suite green.

## Gate 8 — Candidate freeze

```text
exact commit
clean tree
remote readback if pushed
```

STOP.

---

# 15. Stop conditions

Stop if:

- exact SLICE-0002 candidate cannot be safely integrated;
- SoT would need semantic modification;
- provider connection requires bypassing protection;
- secret/session material would need to enter Git;
- adapter requires a consequential architecture change outside existing boundaries;
- external state becomes materially ambiguous with no read-only reconcile path;
- generation appears necessary to satisfy this slice;
- scope materially expands.

Do not convert an external ambiguity into a retry loop.

---

# 16. Final report

Return:

```text
RESULT: PROVEN | DISPROVEN | INCONCLUSIVE

SLICE:
SLICE-0003 — Accept Core + Flow/Veo Adapter Preflight

PRIOR_PROVEN_SHA:
MAIN_AFTER_INTEGRATION_SHA:
CANDIDATE_SHA:
BRANCH:
REMOTE_SHA:

GATES:
0 Prior candidate integration: PASS/FAIL
1 Contract alignment: PASS/FAIL
2 Reuse discovery: PASS/FAIL
3 Provider abstraction: PASS/FAIL
4 Capability mapping: PASS/FAIL
5 Preflight tests: PASS/FAIL
6 Real read-only preflight: PASS/NOT_RUN/INCONCLUSIVE
7 Regression: PASS/FAIL
8 Candidate freeze: PASS/FAIL

AUTOVIDEOPIPELINE_SOURCE:
revision:
files inspected:

REUSED:
- ...

ADAPTED:
- ...

REJECTED:
- ...

IMPLEMENTED:
- ...

TESTS:
- ...

LIVE_PREFLIGHT:
attempted: YES/NO
result:
evidence:

EXTERNAL_EFFECTS:
video generations: 0
paid actions: 0

SECRETS_COMMITTED:
NONE

SOT_FILES_CHANGED:
NONE
or
<explicit representation alignment + Tech Lead-authorized reason>

OPEN_ISSUES:
- ...

TRUTH_CHALLENGES:
- NONE
or
- ...

NEXT:
Ready for Tech Lead PROVE / live Flow canary slice
or
Must not proceed
```

Do not begin the live-generation slice automatically.