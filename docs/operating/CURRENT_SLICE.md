# CURRENT SLICE — S2 REAL-FILM FINISHING REVIEW (ACTIVE / OWNER CREATIVE ACCEPTANCE PENDING)

**Owner continuation decision — 2026-10-18:** Owner confirms they have **watched** the existing V2-021 real-assets 5-shot film and asks Tech Lead to **continue**. Treat this as authorization for **non-destructive local S2 finishing/review preparation only**, **NOT** as explicit acceptance of story, edit, sound, film release, paid provider Generate or Film120 resumption. S1 GPM-first remains `PRODUCT_VERIFIED_LOCAL` and closed; ordinary Chrome A4 stays `SKIPPED_BY_OWNER`. S3 stays PAUSED.

**S2 critical path:** The V2-021 `DISTRIBUTION_MASTER.mp4` is 25.208s / 1280×720 / H.264+AAC and matches sealed SHA-256 `9085a50bf0babd81257dd8f8e982a2553eff7cd8592dde6de8d84a4be923f27d`. Independent read-only `ffmpeg volumedetect` found the FINISH and DISTRIBUTION master audio **effectively silent (-91.0 dB max and mean)**. The five original provider-issued shot clips `S01..S05.mp4` have measurable non-silent sound (max about -15.9, -23.1, -25.2, -30.7, -28.6 dB, respectively). Source production evidence explicitly documents a `silent-track finish`, so this is an **editorial/finishing comparison opportunity**, not a proven engineering regression or authority to impose a new creative choice.

**Active bounded slice:** Prepare **one local alternate master preserving the original provider-shot audio** (or demonstrate a concrete blocker), using unchanged/hashed source picture and preserving original master, journals, asset states and accepted film. Existing FFmpeg/edit tooling must be reused. Local-only source audio, no invented music, no provider Generate or credit use; output must be clearly labeled `REVIEW_VARIANT` and never silently replace the current distribution master. Tech Lead independently verifies picture equivalence, audio levels/absence of clipping, duration/lineage and exact revision; **Owner alone** chooses creative acceptance of silent vs audio variant or requests editorial repair. This S2 five-shot candidate is **not** the separate frozen V1 30–60s/8–12 shot benchmark.

**Worker handoff (WP frozen, Owner relay PENDING):** Dedicated clean worktree `D:\AI FILM MAKER\AI-Film-Pipeline-S2-Audio-Review`, branch `feature/s2-audio-review-001@08a8687363832c317c17ef7273b935059444462d`, WP `docs/operating/TASK_S2_V2_021_SOURCE_AUDIO_REVIEW.md`. Originated from policy-bearing root `b48a878ba0b7aaec12f5e6f35fc06101af4dca78`. Worker **OpenCode + DeepSeek V4.1 Flash** through Owner manual prompt relay, **not MAR task execution**. Root mission checkout has protected dirty Film120 WIP; no coding Worker may edit it. Original `OWNER_REVIEW/V2_021`, `projects/quality_v2_021_narrative_compiler`, accepted assets/media, secrets, DPAPI and proxy/account settings are read-only. Output only one separate review variant in Worker worktree, non-committed media. **Main blocker:** audible source-faithful alternate candidate and subsequent Owner creative verdict. No push/merge/deploy.

---

## Historical S1 closeout (completed, superseded as active focus)

# CURRENT SLICE — S1 DOLA ONECLICK / GPM-FIRST (LOCAL PRODUCT_VERIFIED; OWNER NEXT-SLICE GATE)

**Tech Lead independent PROVE / LEARN — 2026-10-18:** **S1 GPM-first critical operator journey PRODUCT_VERIFIED LOCALLY; scoped G1–G6 acceptance closed.** Exact completed Worker revision `feature/dola-session-oneclick-001@958337ec799e2616a1d7fea767b41c5aedeaf3b7` (only GPM live evidence/delivery docs changed after authorization). Tech Lead inspected real persisted git-ignored `session_registry.json`, `session_matrix.json` and `oneclick_events.jsonl` read-only: **4/4 non-deferred GPM aliases** each `SESSION_VALID` with exact bound identity match and mutually distinct hash, 5 targeted live sync events with the first alias twice, all four `credits=UNKNOWN` with absent provider-source timestamps (correct fail-closed), and the fifth remains `OWNER_DEFERRED` with no new sync event. **85 focused tests and 59 protected checkpoint tests independently PASS** (96 Pydantic deprecation warnings, no failures). Exact source and acceptance in root `IMPLEMENTATION_STATUS.md` and `docs/sot/film/01_SCOPE_AND_PRINCIPLES.md`.

**Scope boundaries:** Ordinary Chrome A4 remains **SKIPPED_BY_OWNER / NOT PASS**. S1 passed only as **local GPM-first OneClick operator outcome**; no positive Dola credit balance was demonstrated, no paid provider Generate was authorized, and no code/branch integration to root, push, deploy, S2 film acceptance or S3 Film120 completion is implied. The old scope/history below is retained as superseded evidence, not currently actionable authority.

**Current Product Progress Gate:** S1's former GPM live blocker is **CLOSED** by independent readback. No new project's Active Slice has been authorized; **OWNER_NEXT_SLICE_DECISION_REQUIRED** before switching to S2 review, S3, provider-cost actions, or other work. Tech Lead may propose Owner review of the already-existing V2-021 25.208s real-film candidate **without new generation**, but must not auto-activate it. Preserve root mission WIP and Owner assets. No new Worker task is justified solely by S1 passing.

---

## Historical GPM-first live-run setup (completed; superseded)

**Owner Product/Scope decision — 2026-10-18:** **SKIP ordinary Chrome entirely for S1** and ship OneClick on **Owner-approved GPMLogin profiles as the primary live operational source**. This explicitly **supersedes only** the earlier three-source/Chrome mandatory acceptance: A4 Chrome MV3/native-host/Owner Capture = **SKIPPED_BY_OWNER (waived, NOT PASS)**; managed-source compatibility from earlier technical work is retained but not a new ship blocker. GPM A5 real operational journey becomes the critical acceptance. The Product Goal remains usable safe multi-account Dola Session OneClick enabling AI film production; S2 and S3 remain unchanged. Product SoT definition: `docs/sot/film/01_SCOPE_AND_PRINCIPLES.md`.

**Active WP and newest Owner execution authority (2026-10-18):** The initial OpenCode GPM-only handoff completed at `feature/dola-session-oneclick-001@e841478876d33bdf7cc4a5e6d4477e4061d646f3`, without code changes or live proof. Owner has now **explicitly authorized OpenCode + DeepSeek V4.1 Flash to autonomously open/start/reuse eligible GPMLogin browsers, navigate to Dola and click login, and run bounded identity-bound read-only Sync**. Owner intervenes **only when human authentication/approval is required** (2FA/CAPTCHA/credential entry) or on new out-of-scope actions. This authorizes start/reuse effects of `GET /profiles/start/{id}` for eligible profiles in the S1 WP; does not authorize other accounts, proxy changes, spending or provider Generate. Current WP contains a dated Owner authority addendum at `D:\AI FILM MAKER\AI-Film-Pipeline-OneClick\docs\operating\TASK_DOLA_ONECLICK_GPM_ONLY_S1_SHIP.md`, branch `feature/dola-session-oneclick-001@b6a0e5ee8bcc6fcc255c428f83c70d9c87c52cd7`. Frozen G1–G6 acceptance unchanged; A4 ordinary Chrome stays `SKIPPED_BY_OWNER`. Owner's relay of this revision is pending; MAR must not start coding Worker.

**Existing GPM evidence, not yet fresh acceptance:** pinned group `Youtube ngoại key story` has five entries; earlier `DOLA_GPM_GROUP_ENROLL_002_EVIDENCE.md` states **three identity-bound SESSION_VALID/UNKNOWN**, **one ProfileInUse/UNKNOWN**, **one OWNER_DEFERRED/UNKNOWN** (source label beginning `minh`). The deferred profile stays untouched, busy profile stays fail-closed (no force start/stop/proxy changes), and credit UNKNOWN cannot become READY without genuinely fresh same-day source evidence. Tech Lead must independently verify actual authorized GPM workflow before S1 PRODUCT_PASS.

**Execution (latest Owner clarification governs):** preserve frozen original A1–A8 as historical baseline, with Owner-waived A4 and promoted GPM G1–G6. OpenCode + DeepSeek V4.1 Flash is authorized for **routine GPM browser start/reuse, Dola login clicks and scoped Sync of eligible profiles**, initially `GPM_5FC7A2A8_63C2627E0C3`, later other non-busy eligible profiles sequentially if necessary. Owner provides interactive human authentication/2FA/CAPTCHA when prompted; the Worker may not bypass verification, read/export private credentials, alter proxy/fingerprint, force free busy profiles or touch the deferred fifth. MAR remains only Tech Lead's Git/SoT/evidence transport. No Generate, spend, Film120 mission mutation, push or merge. **Main blocker** = actual permitted GPM live Dola identity/status readback and repeated safe matrix proof. **Next** = Owner relays current WP addendum to existing OpenCode Worker, then Tech Lead independently PROVEs; do not reopen Chrome A4.

---

## Superseded historical Current Slice — Chrome-required phase (inactive, retained for evidence)

# CURRENT SLICE — DOLA-ONECLICK-MULTIACCOUNT-CLEAN-001 (OWNER-GATED LIVE COMPLETION)

**Product ship milestones (Owner-requested Product Truth clarification, 2026-10-18):** See existing `docs/sot/film/01_SCOPE_AND_PRINCIPLES.md`, section `Current ship milestones`. **S0** V1 technical foundation = PROVEN_COMPLETE (not film acceptance); **S1** usable three-source OneClick = **ACTIVE / PARTIAL_DELIVERY**, Chrome A4 real Owner Capture/readback remains blocker; **S2** existing 25.208s V2-021 real-film candidate = DEFINED / NOT ACTIVE, awaiting Owner creative judgment; **S3** full 120s real-asset film = PAUSED / NOT AUTHORIZED TO RESUME (last 8/24 QC_ACCEPT). These are acceptance/checkpoint definitions, **not** automatic slice transitions, new external permission or changes to frozen A1–A8. The operative next decision is still S1 Owner-gated live Chrome verification.

**Owner-selected Worker relay (2026-10-18):** Tech Lead prepared the **subordinate A4 live-ship WP** at `D:\AI FILM MAKER\AI-Film-Pipeline-OneClick\docs\operating\TASK_DOLA_ONECLICK_A4_OWNER_LIVE_SHIP.md`, branch `feature/dola-session-oneclick-001@8070e5ed936168ed1c4f901bbc3d3963c66fc387`. Worker runner is **OpenCode / DeepSeek V4.1 Flash**, started by Owner's manual prompt relay, **not via MAR task submission**. The WP adds no new acceptance or authority to frozen S1 A1–A8: Worker does safe readiness checks, repairs only evidenced defects, then STOP at Owner's explicit Chrome Capture/identity consent. Current Goal remains S1 PARTIAL_DELIVERY until actual Owner-click and independent destination readback; no GPM-deferred access, Film120, Generate or paid actions.

**Tech Lead LEARN / authoritative current state — 2026-10-18.** The approved product execution focus is unchanged: **ship a usable Dola multi-account Session OneClick across managed browser profiles, ordinary Chrome and Owner-authorized GPM**. The separate AI Film Pipeline V1 implementation is technically complete (Package-019), but film creative/release acceptance is not implied. V2-022 Film-120s is paused/protected; no Generate, mission mutation, budget use, provider account rotation or filmworkprint expansion is part of this slice.

**Exact frozen authority:** A1–A8 at `feature/dola-session-oneclick-001:docs/operating/TASK_DOLA_ONECLICK_MULTI_ACCOUNT_CLEAN_SHIP.md` (handoff baseline `37dacb1`). Worker delivered implementation/report at `2a42ac53c5ce0bfa823486e5dd14d9a1ddcd6f04`; subsequent `159b2d6` on that worktree changed **only pinned policy files**, not product code. Full accepted policy ref: `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`.

**Present acceptance:** Managed OneClick and source-timestamp credit freshness A1–A3 have bounded independent evidence: Tech Lead inspected credit freshness/classification source and reran 85 focused tests (PASS). Related regression: 58 PASS, 1 subprocess import-path failure; that exact test passed with `PYTHONPATH=<OneClick>/src` (environment discrepancy, not proven code defect). A4 ordinary Chrome **live Owner-click capture + identity-bound readback remains UNPROVEN**; A5 GPM functionality has offline PASS and historical bounded read-only live identity observations, but no fresh GPM re-probe. Worker report's larger 422-pass suite and managed live observations are Worker evidence, not separately repeated real-browser PROVE by Tech Lead. Three-source **Product Goal remains PARTIAL_DELIVERY**, not COMPLETE_VERIFIED.

**Product Progress Gate:** **Product Delta** — previously stale 2026-10-16 credit statements no longer authorize 2026-10-18 READY; display now separates source and observation times and fails closed to UNKNOWN. **Evidence** — exact Worker commit/report, independently inspected code, 85 tests and import-corrected subprocess regression. **Main Blocker** — genuine ordinary-Chrome extension/native-host installation and explicit Owner **Capture** consent, after which independent read-only identity/session readback is required. **Next Decision** — keep this same slice at its Owner gate; do not create another Worker task or resume Film120/hardening merely because tests passed. Eligible GPM re-proof is optional and may not touch Owner-deferred profile.

**Git/authority:** MAR confirmed all **six non-temporary worktrees** use byte-identical `AGENTS.md` and two optional skill files from `POLICY_REF` at HEAD (root + five linked worktrees). Local `main` policy-only commit `3d43243` now contains the same blobs for safe future local worktree bases. No reset, merge, cherry-pick, push, deploy or destructive cleanup. MAR temporary detached scratch worktree was left untouched. Root mission code and untracked Owner assets remain dirty/protected. This is a checked local Git state, **not remote propagation or a claim that every branch's historical Current Slice has been rewritten**.

---

## Historical kickoff snapshot (preserved; superseded where dated)

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