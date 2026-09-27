# WORK PACKAGE — SLICE-0002: FILM CORE VERTICAL SKELETON

**Status:** READY FOR BUILD  
**Lifecycle:** SLICE → BUILD → PROVE  
**Worker authority:** Bounded autonomous execution  
**Recommended worker:** GPT-6 Sol / Medium  
**Repository:** `blackshark03z/AI-Film-Pipeline`  
**Base branch:** `main`  
**Expected starting HEAD:** `cde1c1576221cfdde64edd201b66ee7715744069`  
**Previously proven bootstrap baseline:** `da1cec733cc7df352f5de976794be76674f8bfab`

---

## 1. Authority and reading order

This Work Package is the active **CURRENT SLICE contract** for this execution attempt.

Before implementation, read:

1. `docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`
2. `docs/sot/film/00_SOT_INDEX.md`
3. `docs/sot/film/02_CANONICAL_DOMAIN_MODEL.md`
4. `docs/sot/film/03_CINEMATIC_CONTROL_SPEC.md`
5. `docs/sot/film/04_SHOTSPEC_V1.md`
6. `docs/sot/film/05_PROMPT_COMPILER.md`
7. `docs/sot/film/06_PROVIDER_CAPABILITIES.md`
8. `docs/sot/film/08_ASSET_LINEAGE_COST.md`
9. `docs/sot/film/11_IMPLEMENTATION_PLAN.md`
10. `docs/operating/PROJECT_OPERATING_PROFILE.md`
11. `docs/operating/IMPLEMENTATION_STATUS.md`

The repository's previous `CURRENT_SLICE.md` describes the completed bootstrap slice and must not be interpreted as the active task after this Work Package is received.

Persist this Work Package verbatim as a project execution artifact before substantial implementation. Do not change its acceptance semantics.

---

# 2. Outcome

Build and prove the smallest provider-neutral **Film Core vertical skeleton**:

```text
existing ShotSpec fixture
        ↓
Pydantic domain model
        ↓
canonical serialization + hash
        ↓
deterministic Prompt Compiler
        ↓
PromptPlan
        ↓
RoutingDecision
        ↓
provider-neutral dry-run request
        ↓
GenerationAttempt
        ↓
SQLite persistence
        ↓
readback / exact lineage proof
```

The purpose of this slice is to prove that the frozen Film architecture can exist as working code **before introducing live provider/browser/cookie complexity**.

---

# 3. Product/System Truth that must remain frozen

The worker MUST preserve these invariants:

1. `ShotSpec / Film State` is canonical; provider prompts are derived artifacts.
2. Continuity is explicit data.
3. Creative state is separate from runtime/provider state.
4. Providers are replaceable adapters.
5. Provider cookies, sessions, browser selectors and credentials never enter Film Core.
6. `ShotSpec → PromptPlan → RoutingDecision → GenerationAttempt → ProviderJob/Asset` identities must be deterministic and traceable.
7. Unsupported provider controls must be explicit; they may not silently disappear.
8. No blind retry logic is introduced.
9. V1 persistence remains filesystem + JSON/SQLite.
10. Model IDs, pricing and transport quirks are runtime/config concerns, not Film IR.
11. Existing JSON Schemas are authoritative contracts for this slice.
12. Frozen SoT semantics must not be changed to simplify implementation.

If implementation reveals that one of these truths is internally contradictory, stop and report a potential **BOUND delta** rather than silently changing it.

---

# 4. In scope

The worker owns HOW, but the resulting system must provide the following behavior.

## 4.1 Domain models

Implement typed Python domain models sufficient for this vertical path.

At minimum:

```text
ShotSpec
ProviderCapabilities
PromptPlan
RoutingDecision
GenerationAttempt
```

Add other supporting models only when genuinely required.

The three existing ShotSpec fixtures must load through the implementation successfully.

Pydantic is the expected V1 choice unless a concrete repository constraint gives a better reason otherwise.

---

## 4.2 Schema compatibility

The existing JSON Schema remains authoritative.

Required:

```text
fixtures/*.json
      ↓
JSON Schema validation
      ↓
Pydantic model validation
```

The implementation must not require changing the meaning of existing fixtures merely to make parsing easier.

Round-trip serialization must preserve the semantic content of the ShotSpec.

---

## 4.3 Canonical serialization and hashing

Implement deterministic canonical serialization for objects that participate in lineage.

At minimum establish deterministic hashes for:

```text
ShotSpec
PromptPlan input
```

Requirements:

- same semantic input → same canonical representation;
- dictionary/property ordering must not change the hash;
- whitespace formatting must not change the hash;
- the hash algorithm must be explicit;
- runtime secrets must never contribute to creative-state hashes.

SHA-256 is acceptable unless an existing repository constraint justifies another stable algorithm.

---

## 4.4 Deterministic Prompt Compiler core

Implement the deterministic compiler path described by the Film SoT.

Input conceptually:

```text
ShotSpec
+ relevant creative state
+ ProviderCapabilities
+ compiler version/policy
```

Output:

```text
PromptPlan
```

The compiler must preserve canonical blocks equivalent to:

```text
SHOT / DRAMATIC PURPOSE
SUBJECT / CHARACTER LOCK
ACTION / PERFORMANCE
ENVIRONMENT / WORLD LOCK
CAMERA / LENS / MOVEMENT
BLOCKING / START-END STATE
LIGHTING / STYLE
AUDIO / DIALOGUE
CONTINUITY CONSTRAINTS
NEGATIVE / FORBIDDEN BEHAVIOR
```

Not every block must contain data for every shot.

No Gemini or other LLM call is required in this slice.

The deterministic compiler is the subject being proven.

---

## 4.5 Capability degradation

Create at least two deterministic test capability profiles, for example:

```text
provider_full
provider_limited
```

They are synthetic test providers, not claims about real Veo/Seedance capability.

Prove that when a requested control is unsupported, PromptPlan explicitly records:

```text
unsupported_controls
degraded_controls
warnings
```

No requested control may silently vanish.

---

## 4.6 RoutingDecision

Implement a minimal deterministic routing mechanism sufficient to prove the architecture.

It does NOT need to know whether Veo or Seedance is better.

For this slice routing may select among synthetic providers using:

```text
required capabilities
provider health/availability
supported controls
```

The decision must record why the selected provider was chosen.

Do not implement a speculative scoring/ML routing system.

---

## 4.7 Provider-neutral dry-run adapter

Implement a provider abstraction sufficient to compile a PromptPlan into a dry-run request.

No network call.

No cookie.

No API key.

No browser automation.

No Google Flow.

No Dola/Elyum.

The dry-run provider must return enough deterministic execution information to create a `GenerationAttempt`.

It may produce a synthetic `ProviderJob` if useful, but live ProviderJob semantics are not being proven yet.

---

## 4.8 GenerationAttempt

Create a GenerationAttempt that binds at minimum:

```text
generation_attempt_id
shot_id
shot_spec_version
shot_spec_hash
prompt_plan_hash
routing_decision_id
provider_id
status
timestamps
```

The exact ShotSpec/PromptPlan lineage must be reconstructable.

---

## 4.9 SQLite persistence

Persist the vertical-path runtime records to SQLite.

The smallest acceptable implementation is preferred.

Required proof:

```text
write GenerationAttempt
        ↓
close/reopen or new DB access
        ↓
read exact persisted record
        ↓
lineage identifiers still match
```

Do not introduce:

```text
Postgres
Redis
Temporal
object storage
queue infrastructure
ORM complexity without need
```

SQLite schema design belongs to the worker as implementation HOW.

---

## 4.10 Tests

Add focused tests sufficient to prove the acceptance claims.

Candidate-authored tests are useful BUILD evidence but do not by themselves redefine acceptance.

Existing bootstrap tests must continue to pass.

---

# 5. Explicitly out of scope

Do NOT implement in SLICE-0002:

```text
real Gemini API calls
Google Flow browser/cookie integration
real Veo generation
Dola integration
Elyum integration
Seedance generation
provider account/session management
live provider capability discovery
paid actions
image generation
Stable Diffusion / ComfyUI
automatic visual QC
RepairDecision execution loop
FFmpeg rough cut
Resolve integration
web UI
Postgres / Redis / Temporal
distributed workers
3D / Blender / Unreal
LoRA / fine-tuning
production deployment
```

Do not inspect or port `AutoVideoPipeline` unless a concrete core abstraction question genuinely requires reference material.

Live Flow reuse belongs to a later slice.

---

# 6. Acceptance claims

Acceptance is immutable during this execution attempt.

## A — Frozen truth preserved

No frozen Development SoT or Film SoT semantic content is modified.

PASS requires no implementation-driven weakening of existing contracts.

---

## B — Existing ShotSpec fixtures work

All three canonical fixtures:

```text
dialogue_closeup.json
continuity_two_shot.json
action_reveal.json
```

must:

1. validate against the existing JSON Schema;
2. load into the Python domain model;
3. serialize successfully;
4. preserve semantically relevant fields.

---

## C — Canonical hashing is deterministic

Equivalent semantic ShotSpec inputs must produce the same canonical hash.

At least one test must prove property/key ordering does not change the result.

---

## D — Prompt compilation is deterministic

For the same:

```text
ShotSpec
ProviderCapabilities
compiler version/policy
```

the deterministic core must produce equivalent:

```text
canonical blocks
input hash
mapped controls
unsupported controls
degraded controls
warnings
```

Repeated execution must not introduce uncontrolled variation.

---

## E — Capability degradation is explicit

When a synthetic provider does not support a requested control:

```text
unsupported_controls
```

must identify it.

If text fallback/degradation occurs:

```text
degraded_controls
```

must identify what happened.

Silent omission = FAIL.

---

## F — Routing is explainable

A synthetic RoutingDecision must include:

```text
selected provider
required capabilities
reason(s)
fallback information if applicable
```

No opaque random choice.

---

## G — Dry-run execution is provider-neutral

A dry-run provider request can be generated from PromptPlan without:

```text
provider credentials
cookies
browser sessions
live network calls
provider-specific state leaking into ShotSpec
```

---

## H — GenerationAttempt lineage is exact

A generated attempt must refer to the exact:

```text
ShotSpec version/hash
PromptPlan hash
RoutingDecision ID
provider ID
```

used to create it.

---

## I — SQLite round-trip works

The attempt must survive persistence/readback with lineage fields intact.

A fresh DB handle/process-equivalent read should be used rather than merely returning an in-memory object.

---

## J — Existing checks remain green

All existing bootstrap tests plus new slice tests must pass.

The worker must not modify tests or frozen schemas solely to convert a failing candidate into PASS.

---

## K — No unintended external effects

This slice performs no:

```text
paid generation
provider mutation
credential use
browser automation
external video creation
```

Any unexpected external call is a slice violation.

---

# 7. Required evidence

Final evidence must include at minimum:

```text
1. starting baseline SHA
2. candidate SHA
3. branch name
4. git diff --stat / changed-file inventory
5. confirmation that frozen SoT semantic files were not modified
6. JSON Schema + Pydantic fixture validation result
7. complete test-suite result
8. deterministic-hash proof
9. compiler/degradation proof
10. SQLite persistence/readback proof
11. git status --short
```

If the candidate branch is pushed to GitHub, also provide:

```text
remote branch
remote candidate SHA readback
```

The exact revision reported as the candidate must be the exact revision on which the evidence was collected.

---

# 8. Worker authority

The worker MAY autonomously:

- create a feature branch;
- choose local module/class/function decomposition;
- add replaceable Python dependencies when justified;
- modify `pyproject.toml`;
- implement models/compiler/persistence/tests;
- refactor bootstrap skeleton;
- create local test helpers;
- create synthetic provider capability fixtures;
- create SQLite migrations/schema initialization as needed;
- run all local tests repeatedly;
- fix implementation bugs;
- push a non-main candidate branch if GitHub authorization already exists;
- self-progress through all internal gates below.

The worker does NOT need Owner approval for routine engineering decisions within this boundary.

---

# 9. External authority

Pre-authorized:

```text
local file changes
local Git commits
creation of a non-main feature branch
non-destructive GitHub readback
push of candidate branch to the existing private repository
```

Not authorized:

```text
merge to main
force push
delete branches
make repository public
change repository visibility/settings
use Gemini keys
use Flow/Dola/Elyum cookies or credentials
perform paid generation
modify external provider state
```

---

# 10. Branch / candidate isolation

Start from:

```text
main@cde1c1576221cfdde64edd201b66ee7715744069
```

Recommended branch:

```text
slice-0002-film-core-vertical-skeleton
```

If `main` no longer points to the expected starting revision:

**STOP before implementation and report BASELINE_DRIFT.**

Do not silently rebase the contract onto an unknown newer baseline.

Do not merge the finished candidate into `main`.

---

# 11. Internal gates

The worker may progress automatically when each gate passes.

## Gate 0 — Baseline

```text
expected main SHA confirmed
working tree clean
```

---

## Gate 1 — Contract integrity

```text
SoT understood
Work Package persisted unchanged
no frozen semantics modified
```

---

## Gate 2 — Domain model

```text
3 canonical fixtures
→ JSON Schema PASS
→ Python model PASS
→ serialization PASS
```

---

## Gate 3 — Canonical identity

```text
canonical serialization PASS
deterministic ShotSpec hash PASS
```

---

## Gate 4 — Compiler

```text
fixture
→ PromptPlan
→ deterministic output
→ capability degradation explicit
```

---

## Gate 5 — Routing / dry provider

```text
PromptPlan
→ explainable RoutingDecision
→ synthetic provider request
→ GenerationAttempt
```

No network activity.

---

## Gate 6 — Persistence

```text
GenerationAttempt
→ SQLite
→ fresh readback
→ exact lineage recovered
```

---

## Gate 7 — Regression

```text
existing bootstrap tests PASS
new slice tests PASS
git diff hygiene PASS
```

---

## Gate 8 — Candidate freeze

```text
exact candidate commit created
working tree clean
evidence collected against that exact commit
```

If pushing the candidate branch is possible:

```text
push
→ remote readback
→ exact SHA match
```

Then STOP at the slice boundary.

---

# 12. Stop conditions

Stop and return `INCONCLUSIVE` or `DISPROVEN` as appropriate if:

- repository baseline differs from the expected starting SHA;
- a frozen SoT invariant appears internally inconsistent;
- existing schema cannot be implemented without changing its semantics;
- implementation requires a live provider or secret;
- implementation requires a consequential architecture choice outside current System Truth;
- an external operation produces ambiguous state;
- a required dependency cannot be safely obtained;
- tests can pass only by weakening acceptance;
- no-progress/retry limits are reached;
- scope needs to expand materially.

Do not solve a stop condition by silently increasing scope.

---

# 13. Explicit non-goals for technical elegance

Do not optimize for:

```text
maximum abstraction
future microservices
future cloud scale
generic plugin ecosystem
all-provider support
perfect ORM design
full production observability
enterprise deployment
```

Optimize for:

```text
correct canonical model
deterministic compiler
traceable lineage
simple persistence
clear provider boundary
tests that expose architectural drift
```

---

# 14. Expected final candidate

At the end of BUILD, this should work conceptually:

```text
load fixture
    ↓
ShotSpec model
    ↓
canonical hash
    ↓
compile
    ↓
PromptPlan
    ↓
route
    ↓
RoutingDecision
    ↓
dry-run provider request
    ↓
GenerationAttempt
    ↓
SQLite persist
    ↓
fresh readback
    ↓
exact lineage match
```

That is the only end-to-end vertical path required by this slice.

---

# 15. Final report format

Return exactly this structure:

```text
RESULT: PROVEN | DISPROVEN | INCONCLUSIVE

SLICE:
SLICE-0002 — Film Core Vertical Skeleton

BASELINE_SHA:
CANDIDATE_SHA:
BRANCH:
REMOTE_SHA: <if pushed>

GATES:
0 Baseline: PASS/FAIL
1 Contract integrity: PASS/FAIL
2 Domain model: PASS/FAIL
3 Canonical identity: PASS/FAIL
4 Prompt compiler: PASS/FAIL
5 Routing/dry provider: PASS/FAIL
6 SQLite persistence: PASS/FAIL
7 Regression: PASS/FAIL
8 Candidate freeze/readback: PASS/FAIL

IMPLEMENTED:
- ...

ACCEPTANCE:
A Frozen truth preserved: PASS/FAIL
B ShotSpec fixtures: PASS/FAIL
C Deterministic hashing: PASS/FAIL
D Deterministic compiler: PASS/FAIL
E Capability degradation: PASS/FAIL
F Explainable routing: PASS/FAIL
G Provider-neutral dry run: PASS/FAIL
H Exact attempt lineage: PASS/FAIL
I SQLite round-trip: PASS/FAIL
J Existing checks green: PASS/FAIL
K No unintended external effects: PASS/FAIL

TESTS:
- ...

EVIDENCE:
- ...

SOT_FILES_CHANGED:
- NONE
or
- <files + reason; this normally prevents PROVEN>

OPEN_ISSUES:
- ...

TRUTH_CHALLENGES:
- NONE
or
- <potential SHAPE/BOUND delta>

NEXT:
- Ready for Tech Lead PROVE / SLICE-0003
or
- Must not proceed
```

---

# 16. Completion rule

Do not begin SLICE-0003 automatically.

A successful BUILD candidate is not itself authorization for the next slice.

Freeze the exact candidate, return evidence, and stop for Tech Lead PROVE.