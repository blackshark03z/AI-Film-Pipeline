# AI-FILM-QUALITY-V2-003 — Director-Blocking Authority Freeze — Evidence Record

**Status: DIRECTOR_MODEL_UNAVAILABLE** — the model-independent
governance layer is PROVEN; every Director-model-dependent deliverable
is BLOCKED_ON_DIRECTOR_MODEL with no substitute authored.

## 1. Custody chain

| Item | Value |
| --- | --- |
| Exact start SHA (V2-002 final revision) | `b460948c9d2ba1a3e676e827c46930563c1a1180` (branch `quality-v2/003-director-blocking-authority` created from it) |
| V2-001 final revision | `5793dc55bb1ae5d5ff2cb22e02e0ead760f53f46` |
| V1 frozen baseline | `14ba281d12c15a5678a3fe1b3f0242f577512e5f` — ancestor verified |
| Canonical master | `976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595` — re-verified byte-identical |
| Canonical F2 SelectedTake | `take_91e4997b…f31efb67` / asset `e84ba56c…90a767` (slot 24) — unchanged |
| PACKAGE_003_FINAL_HEAD_SHA | returned in the final worker report |

## 2. V2-002 Owner decision custody — `v2_002_owner_decision.json`

**V2_002_OWNER_DECISION = REJECT_ALL**, reasons recorded verbatim:
ACTION_GOAL_NOT_SPATIALLY_LEGIBLE · CHARACTER_LOITERS_AROUND_ROCK ·
THROUGH_STATE_NOT_OWNER_ACCEPTED. Applied through the frozen V2-001
state machine: both governed candidates
(`QRC-1bd5a34bdefcffba` asset `cb89df69…`, `QRC-8c1b2dbe614c2489`
asset `3071eaea…`) transitioned QUALITY_REVIEW_READY →
**OWNER_REJECTED** with immutable OwnerReviewDecision records bound to
the exact asset shas. Neither is selected. **QD-001 remains ACTIVE**
(a rejected candidate never closes debt). No promotion.

## 3. Director model availability receipt — `director_model_binding_v2_003.json`

- Binding frozen exactly as the package names it: **gpt-6-sol**,
  thinking_effort **HIGH**, role DIRECTOR_SHOT_DESIGNER, with the
  frozen responsibilities and MUST-NOT list (never invent story
  events, never override Owner narrative authority, never select takes,
  never promote, never call providers, never change acceptance).
- Availability check (2026-10-04): the worker runtime model surface is
  `account:zai-start-plan/GLM-5.3-Flash` + `GLM-5.3` only;
  `api_keys/` contains only `google_flow_cookie.json`; no OpenAI env
  surface. **gpt-6-sol = UNAVAILABLE.**
- Consequence (per the package's own rule): **STOP —
  DIRECTOR_MODEL_UNAVAILABLE. No silent downgrade. No substitution
  without Owner authorization.** `director_work_state =
  BLOCKED_ON_DIRECTOR_MODEL`; blocked deliverables enumerated in the
  binding file. A structural guard enforces it:
  `tests/test_director_blocking_v2_003.py::test_22_…` refuses any
  worker-authored F2 director artifact in the package directory.

## 4. Reuse analysis (searched before building)

Reused unchanged: `core.Blocking` (start/beats/end prose),
`core.Camera/Movement` (framing/height/lens/motion), `Continuity`
(critical_invariants), `ActionIntent`/`PerformanceSpec` (V1 models),
`quality_repair_v2` governance (state machine + ledgers + gates
pattern). Missing delta built new: `src/film_pipeline/director_blocking.py`
+ 3 schemas (`director_intent`, `blocking_spec`,
`camera_coverage_plan`) + previz/recovery tools. The legacy prose
`Blocking` was NOT rewritten — the structured spatial semantics are a
new, parallel-safe layer.

## 5. Authority layering (frozen in code + doc)

`NarrativeBeat → ActionIntent → DirectorIntent → BlockingSpec →
PerformanceSpec → CameraCoveragePlan → ShotSpec → PromptCompiler →
Provider`, with meanings (WHAT / WHY / HOW-the-audience-understands /
WHERE / HOW-the-body / HOW-made-visible / assembly / deterministic
translation only / never authority). The Prompt Compiler may not
invent missing blocking; the Provider is never authority.

## 6. Contracts

- **DirectorIntent v1** (`DI-<sha16>`): shot_id, dramatic_purpose,
  viewer_must_understand, primary_action_objective,
  required_visual_change, required_end_read,
  forbidden_interpretations, authority_sources (all six semantic keys
  required non-empty — no prose-only authority),
  director_model_receipt.
- **BlockingSpec v1** (`BS-<sha16>`, provider-neutral): start/target/
  end zones, screen_direction, travel_path (path_type,
  ordered_waypoints with crossing marker, required_crossing),
  body orientations, required_spatial_state_change, allowed/forbidden
  interactions, forbidden_zones, forbidden_reversal,
  must_exit_start_zone / must_reach_target_zone,
  visibility_requirements, continuity_bindings, authority_sources.
- **CameraCoveragePlan v1** (`CC-<sha16>`): position intent, framing,
  axis, screen_direction, subject start/end regions, required action
  + crossing visibility, occlusion constraints, camera_motion,
  forbidden_camera_behavior, authority_sources.

## 7. Director gates — all ten deterministic (B1–B10)

B1 START_END_DISTINCT · B2 TARGET_REACHED · B3 PATH_HAS_PROGRESS ·
B4 NO_FORBIDDEN_INTERACTION (allowed/forbidden overlap + path-note
invention scan) · B5 NO_CIRCLING (zone-family revisits via
zone_matches; AuthorizedLoop requires an explicit
path_loop_authorization source) · B6 NO_REVERSAL (single marked
crossing; no start-zone return after it) · B7 CROSSING_OBSERVABLE
(visibility flag + not occluded + no forbidden camera motion
co-occurrence) · B8 END_STATE_OBSERVABLE (distinct, zone-bound
subject regions + action visibility) · B9 CONTINUITY_COMPATIBLE
(neighbor bindings + screen-direction match unless flip authorized) ·
B10 AUTHORITY_COMPLETE (intent + blocking + camera sources non-empty,
one shot across all three). Any failure ⇒ `BLOCKED_INVARIANT`
(`require_director_gates`).

## 8. F2 director plan — BLOCKED (honest state)

The Owner truth (trigger / goal / NOT-goal / zones / crossing /
path_type / forbidden interactions / reversal ban) is frozen verbatim
in `docs/quality-v2/V2_004_F2_BLOCKING_EXPERIMENT_HANDOFF.md` §4 —
but the DESIGN COMPLETION (screen direction choice, waypoints,
orientations, camera position/regions, visibility requirements) is the
Director model's authority and was **not exercised**: no F2
DirectorIntent, BlockingSpec, CameraCoveragePlan, previz artifact, or
critique exists in the package. Gates, identity, compiler boundary and
the previz renderer are proven on synthetic fixtures only
(SYNTHETIC_GATE_FIXTURE, clearly labeled, never presented as the F2
plan).

## 9. Semantic identity proof (P11)

`director_semantic_identity(base_shot_spec_sha256, intent, blocking,
camera)` → `generation-semantic-identity-v2`:
- same base + different BlockingSpec ⇒ different identity (proven),
- same base + different CameraCoveragePlan ⇒ different identity
  (proven),
- identical director semantics ⇒ deterministic same identity (proven),
- mixed shot ids refused; `v1_identity_untouched = True` (pure
  forward-compatible extension; no historical identity rewritten).

## 10. Compiler boundary (P12)

`assert_compile_authorities_present` refuses (REFUSE_COMPILE) unless
ActionIntent + DirectorIntent + BlockingSpec + PerformanceSpec +
CameraCoveragePlan are all present and non-empty (empty dict/string
counts as missing). `assert_compiler_respected_authority` refuses a
compiled text that introduces a forbidden interaction (all component
words present) or lacks the required end spatial read (slug-normalized
zone match). No fallback prose inference anywhere.

## 11. Previz (P9) — renderer proven, F2 artifacts blocked

`tools/build_v2_003_previz.py` renders any BlockingSpec deterministically
(PIL + ffmpeg): BLOCKING_TOPDOWN.png (zones, path, crossing threshold,
forbidden strip), START/END_FRAME_SCHEMATIC.png, BLOCKING_PREVIZ.mp4 —
every frame watermarked "PLANNING EVIDENCE ONLY - NOT CANONICAL MEDIA".
Proven byte-identical across re-renders and output-contained on the
SYNTHETIC_GATE_FIXTURE. The four F2 previz artifacts are
BLOCKED_ON_DIRECTOR_MODEL (rendering them would require authoring the
F2 blocking, i.e. a forbidden substitution).

## 12. Recovery / adversarial — `recovery_matrix_v2_003.json`

**147 cases total**: 117 reused frozen cases (89 V2-001 governance +
28 V2-002 package; all still executed live by their test files) +
30 V2-003 package cases executed against live guards
(`tests/test_v2_003_recovery_001.py`): missing DirectorIntent/
BlockingSpec at compile, same start/end, loop around rock, ends-at-rock,
reversal, target-unreached, crossing hidden, geography collapse, axis
cross, indistinguishable regions, compiler path/brace inventions,
missing end read, silent Director-output tamper, unbound story event,
identity separation, missing authority, F1/F3 conflict, V1/canonical
mutation, provider/generation surface scans, silent downgrade, model
unavailable, ambiguity-rule regression, previz determinism/containment,
empty authority strings. Owner ambiguity rule unchanged:
OWNER_AMBIGUITY_GATE.

## 13. Verification

- **1129 tests passed** (918 V1 + 140 V2-001 + 26 V2-002 + 45 V2-003:
  26 director-layer + 19 package recovery), 0 failed, network-free.
- External AI calls: **0** (the authorized Director planning call could
  not run — model unavailable). Video generation 0 · Flow submit 0 ·
  upload 0 · canonical mutation 0.
- compileall clean · `git diff --check` clean · SoT manifest 30/30 ·
  tracked files unchanged (0 modified). Secret-scan note: the only
  pattern matches are the availability-receipt code in
  `tools/bind_v2_003_authority.py` that LISTS key FILE NAMES (e.g.
  `google_flow_cookie.json`) — no key material anywhere.

## 14. Unresolved unknowns

1. gpt-6-sol HIGH availability (or an Owner-authorized explicit
   substitute) — everything in §8 waits on this.
2. The actual F2 blocking/camera design and the Director critique —
   the Director's authority, not the worker's.
3. Whether the qualified provider renders the (future) frozen plan
   legibly — that is exactly V2-004.

## 15. Final status

**DIRECTOR_MODEL_UNAVAILABLE** — with
DIRECTOR_AUTHORITY (contract layer) = PROVEN_CANDIDATE ·
BLOCKING_AUTHORITY (contract + gates) = PROVEN_CANDIDATE ·
CAMERA_COVERAGE_AUTHORITY (contract + gates) = PROVEN_CANDIDATE ·
F2_SPATIAL_PLAN = **BLOCKED_ON_DIRECTOR_MODEL** (not
READY_FOR_LIVE_TEST — the plan itself requires the Director model) ·
VIDEO_GENERATION = 0 · CANONICAL_MUTATION = 0 ·
NEXT = V2_004_F2_BLOCKING_EXPERIMENT (after the model gate resolves).
PACKAGE_003_FINAL_HEAD_SHA is returned in the final worker report.
