# CURRENT SLICE — DOLA-ONECLICK-MULTIACCOUNT-CLEAN-001 (ACTIVE PROJECT EXECUTION FOCUS)

**Reconciled by Tech Lead using MAR on 2026-10-18; read-only inventory of root + linked worktrees.** This is the root AI-Film-Pipeline project-level Current Slice. It is NOT a claim that the whole film product has shipped or that the root and child branch HEADs have been merged.

**Approved project Product Goal:** Deliver a usable, coherent AI-film production pipeline and real film outcomes. **V1 pipeline technical implementation was proven complete** (Package-019); creative quality/final content release remains subject to separate Owner/content gates. The Owner's **current approved execution focus** is to clean/refactor and finish **multi-account Dola Session OneClick management** across managed profiles, ordinary Chrome and GPM, as an enabling production operator journey.

**Active worker slice:** `DOLA-ONECLICK-MULTIACCOUNT-CLEAN-001` on isolated Git worktree `D:\AI FILM MAKER\AI-Film-Pipeline-OneClick`, branch `feature/dola-session-oneclick-001`, frozen handoff base `37dacb1c309c245464218587f9a294463a5a17eb`. The immutable A1–A8 BUILD/PROVE contract is **`docs/operating/TASK_DOLA_ONECLICK_MULTI_ACCOUNT_CLEAN_SHIP.md` in that worktree**. That path does NOT exist as an equivalent canonical root file on this branch. The Worker has already received this task; do not interrupt, silently amend acceptance or treat uncommitted Worker edits as accepted.

**Acceptance still open:** reliable one-click actionable multi-account operator view; genuine independent Chrome MV3/native-host consent and readback (unless live consent already observed); GPM permitted-profile handling with deferred profile untouched; per-alias DPAPI identity/vault isolation; timestamp-correct source credit freshness; focused/integration/protected regressions and exact final report. Worker technical PASS alone does not close these gates.

**Actual dependency and bounded authority:** four previously identity-bound GPM profiles have UNKNOWN credit; the fifth Owner-deferred GPM profile must NOT be resumed or probed. A previous ordinary-Chrome live acceptance was not evidenced. No Generate, paid call, daily quota reset assumption, proxy repair, mission mutation, AutoEdit implementation, merge or push is authorized by this OneClick slice. An older S15 one-shot conditional authorization from a different workstream does not transfer into this slice.

**Parallel / paused work:** V2-022 Film-120s mission remains a **protected paused production workstream**, last recorded 8/24 QC_ACCEPT and 16 pending; 120s slate workprint in OneClick was a partial editorial proof, NOT a completed film. No Film-120s auto-run is activated through OneClick. Other Flow qualification/forensics worktrees retain their own Git/evidence histories and are not automatically active slices. AutoEdit producer compatibility SLICE-0009 is **historically PROVEN**, not the present project execution focus.

**Handoff / role boundary:** Tech Lead owns SHAPE → BOUND → SLICE, independent PROVE → LEARN and root canonical status. Worker (any runtime/model) owns BUILD → operational PROVE. After Worker finishes, Tech Lead uses MAR for exact-commit/evidence/state audit, updates `docs/operating/IMPLEMENTATION_STATUS.md`, then decides whether to close or revise Current Slice. If project-wide direction is reconsidered, consult Owner and frozen SoTs; do not infer from the latest branch.

---

## Historical preserved slice — SLICE-0009 AutoEdit Compatibility Baseline v0 (INACTIVE)

## Worker model

```text
Primary model: GPT-5.6 Sol
Thinking effort: High
```

After boundary decisions are frozen:

```text
GPT-5.6 Sol / Medium
```

---

# 1. Starting point

Accepted baseline:

```text
bdaac47501c9822a6b8037817ec1803358a7873d
```

SLICE-0008 is PROVEN.

Film Pipeline currently proves:

```text
SelectedTake
→ EditManifest
→ local rough cut
→ provenance
```

Do not expand Film Pipeline into a full post-production engine in this slice.

---

# 2. Goal

Prevent future mismatch between:

```text
AI-Film-Pipeline
```

and:

```text
AutoEdit
```

before AutoEdit implementation begins.

This slice does NOT implement AutoEdit.

It freezes only:

```text
system boundary
ownership
compatibility envelope
producer fixture
contract expectations
```

Do NOT freeze the full future EditIR.

---

# 3. Fundamental relationship

Freeze:

```text
AI-Film-Pipeline
= one optional upstream producer for AutoEdit
```

It has no architectural privilege.

AutoEdit must also remain able to ingest:

```text
raw footage
podcast/interview
screen recording
gameplay
existing timeline/project
stock media
AI-generated media
future producers
```

Therefore Film-specific concepts must not become required AutoEdit kernel inputs.

---

# 4. Ownership

Freeze ownership boundaries.

## AI-Film-Pipeline owns

```text
Story
Scene
WorldState
ShotSpec
PromptPlan
RoutingDecision
GenerationAttempt
ProviderJob
Asset provenance
QCReport
RepairDecision
SelectedTake
```

## AutoEdit owns

```text
MediaIndex
EditIR
editorial planning
clip selection within allowed inputs
trims
timing
tracks
audio
graphics
VFX
color
preview
edit critique
edit repair
final post-production execution
```

## Shared integration boundary owns only

```text
cross-system input/output representation
contract versioning
portable identifiers
media references
constraints
provenance links
```

No shared database.

---

# 5. EditManifest semantics

Current Film `EditManifestV1` remains valid.

But freeze this interpretation:

```text
Film EditManifest
= producer-side editorial intent / suggested assembly / handoff
```

It is NOT:

```text
AutoEdit EditIR
```

and NOT necessarily:

```text
final editorial authority
```

AutoEdit may change:

```text
trim
order
pacing
transition
sound
graphics
VFX
```

unless a constraint is explicitly frozen.

---

# 6. Generic compatibility envelope

Define a conceptual v0 envelope.

Do NOT over-specify implementation.

Target concept:

```text
EditJobInputV0
├── contract_version
├── job_id
├── media[]
├── optional_timeline_hint
├── optional_transcripts
├── optional_subtitles
├── optional_semantic_metadata
├── optional_provenance
├── user_intent
├── optional_references
├── optional_constraints
└── frozen_constraints
```

Important:

```text
media[]
```

must be sufficient for a minimal producer.

Film-specific data belongs under optional enrichment.

---

# 7. Media entry

Minimum conceptual fields:

```text
media_id
uri or portable locator
media_type
duration if known
sha256 if local immutable bytes exist
provenance reference if available
```

Optional Film enrichment may include:

```text
asset_id
selected_take_id
shot_id
scene_id
QC status
ShotSpec-derived intent
continuity metadata
camera intent
dramatic purpose
```

AutoEdit must not require these enrichment fields.

---

# 8. Timeline hint

Film Pipeline may export current `EditManifest` as:

```text
optional_timeline_hint
```

Semantics:

```text
suggested editorial starting point
```

not:

```text
mandatory final timeline
```

Each field must distinguish:

```text
suggestion
```

from:

```text
frozen constraint
```

Do not infer frozen authority merely because Film supplied a value.

---

# 9. Frozen constraints

Create explicit semantics for constraints that AutoEdit must preserve.

Examples:

```text
must_use_selected_take
must_not_reorder
must_preserve_dialogue
must_preserve_duration_range
must_preserve_aspect_ratio
must_not_crop_character
```

Do NOT build a huge constraint taxonomy.

Create only minimal structure sufficient to distinguish:

```text
metadata / suggestion / frozen requirement
```

---

# 10. Producer fixture from real SLICE-0008 state

Build one golden fixture from the real proven Film Pipeline state.

Fixture should reference:

```text
FLOW_CANARY_001
SelectedTake:
take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b

Asset:
asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01

EditManifest:
edit_52750848b473f76fd6e14f4007fa30b73a25082017e2d0fa191efcb44526ecc5
```

Do not embed absolute Windows paths into canonical fixture identity.

Use relative or portable locators.

---

# 11. Additional deterministic fixtures

Create minimal fixture cases:

```text
one_media_no_timeline
one_selected_take_with_timeline_hint
multi_media
with_transcript
with_frozen_constraint
with_optional_film_metadata
malformed_missing_media
malformed_bad_version
malformed_hash_mismatch
```

No AI generation.

---

# 12. Compatibility rule

A future AutoEdit implementation must be able to accept:

```text
minimal generic producer fixture
```

without importing:

```text
film_pipeline Python modules
Film SQLite schema
ShotSpec classes
QCReport classes
SelectedTake classes
```

Film-specific enrichment may improve AutoEdit reasoning but cannot be required.

---

# 13. Producer adapter

Implement only a thin Film-side exporter if necessary:

```text
Film internal state
→ EditJobInputV0 fixture/package
```

No AutoEdit consumer implementation yet.

Do not create:

```text
HTTP service
MCP bridge
message queue
shared database
distributed orchestration
```

Filesystem/package export is sufficient.

---

# 14. Transport

Freeze:

```text
contract != transport
```

Initial transport:

```text
filesystem package
```

Future transports may include:

```text
CLI piping
HTTP
MCP
object storage
queue
```

without changing semantic contract.

---

# 15. Package form

Prefer something similar to:

```text
edit_job/
├── edit_job.json
├── media/
│   └── ...
├── checksums.json
└── optional/
    ├── timeline_hint.json
    ├── transcript.json
    └── film_metadata.json
```

Do not require media copying if a safe portable reference is sufficient.

Record whether media is:

```text
embedded
referenced
```

---

# 16. Versioning

Use an explicit compatibility version.

For now:

```text
0.x
```

because AutoEdit implementation has not begun.

Meaning:

```text
experimental compatibility envelope
not yet stable public API
```

Do NOT call it `1.0.0` yet.

Do NOT use `"latest"`.

---

# 17. What is deliberately NOT frozen

Explicitly leave open:

```text
exact EditIR schema
MediaIndex schema
AutoEdit persistence model
backend capability schema
editor planner protocol
critic protocol
repair protocol
NLE adapters
OTIO mapping
Premiere/AE/Resolve implementation
generic reverse MediaRequest schema
```

These belong to AutoEdit architecture research.

---

# 18. Reverse direction

Do NOT fully implement AutoEdit → producer communication yet.

Only reserve the conceptual idea:

```text
AutoEdit may request additional/replacement media
```

Future generic form might become:

```text
MediaRequest
```

Film integration can later map:

```text
MediaRequest
→ PickupRequest
→ ShotSpec
→ generation
```

But do not freeze exact schema before AutoEdit research.

---

# 19. Compatibility baseline document

Create:

```text
docs/integration/AUTOEDIT_COMPATIBILITY_BASELINE_v0.md
```

It must contain:

```text
relationship
ownership
generic input envelope
Film enrichment mapping
EditManifest interpretation
transport independence
version policy
open questions
non-goals
```

This document is NOT a replacement for Film SoT or AutoEdit SoT.

It is integration truth only.

---

# 20. Contract tests

Add Film-side producer tests.

Prove:

```text
exported fixture is deterministic
same Film state → same canonical package identity
absolute local paths do not affect identity
Asset hash retained
SelectedTake provenance retained
EditManifest can be included as optional timeline hint
Film-specific metadata can be removed and package remains structurally valid
malformed package rejected
unknown optional fields handled according to chosen v0 rule
```

---

# 21. Drift prevention

Produce a small compatibility checklist to be copied/reused when AutoEdit repo begins.

Future AutoEdit bootstrap must test against these fixtures.

Required future rule:

```text
AutoEdit cannot declare ingest V1 PROVEN
until it consumes the frozen Film producer fixtures
plus at least one non-Film generic fixture
```

This prevents AutoEdit from accidentally becoming Film-specific.

---

# 22. No Film SoT rewrite

Do not rewrite frozen Film SoT.

If needed, add only an operating/integration truth delta stating:

```text
AI-Film-Pipeline is one optional AutoEdit input producer.
```

No canonical Film entities need removal or renaming.

---

# 23. No AutoEdit implementation

Forbidden in this slice:

```text
MediaIndex implementation
EditIR implementation
EditorBrain
ModelGateway
Premiere adapter
AE adapter
Resolve adapter
critic
repair loop
```

Those belong to AutoEdit's own architecture lifecycle.

---

# 24. Acceptance

SLICE-0009 is PROVEN when:

```text
system boundary documented
ownership documented
EditManifest handoff semantics documented
generic EditJobInputV0 envelope documented
Film-side real golden fixture produced
generic/minimal fixtures produced
Film exporter deterministic if implemented
contract tests pass
absolute machine paths excluded from canonical identity
no Film-specific field is structurally mandatory
transport is explicitly replaceable
full future EditIR remains unfrozen
Film SoT remains unchanged
no AutoEdit implementation begins
full regression passes
```

---

# 25. Final report

Return:

```text
RESULT:
PROVEN | INCONCLUSIVE | DISPROVEN

SLICE:
SLICE-0009

MODEL:
  model:
  thinking_effort:

BASELINE_SHA:

BOUNDARY:
  film_role:
  autoedit_role:
  shared_role:

COMPATIBILITY_ENVELOPE:
  name:
  version:
  required_fields:
  optional_film_enrichment:
  timeline_hint_semantics:
  frozen_constraint_semantics:

FIXTURES:
  real_film_fixture:
  generic_fixture_count:
  malformed_fixture_count:

PRODUCER_EXPORT:
  implemented:
  deterministic:
  portable_paths:
  package_identity:

CONTRACT_TESTS:
  count:
  result:

UNFROZEN_AUTOEDIT_AREAS:
  editir:
  mediaindex:
  reverse_media_request:
  backend_contracts:

REGRESSION:
  tests:

SOT_FILES_CHANGED:

CANDIDATE_SHA:
REMOTE_SHA:
WORKING_TREE:
SECRETS_COMMITTED:

NEXT:
  AutoEdit may begin architecture/prototype phase against this compatibility baseline.
```