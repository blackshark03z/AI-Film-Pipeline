# V2-004 F2 BLOCKING EXPERIMENT HANDOFF

**From:** AI-FILM-QUALITY-V2-003 (Director/Blocking authority freeze)
**To:** V2-004 (F2 blocking live experiment, if the Director authority
becomes available and the Owner authorizes it)
**Status:** HANDOFF ONLY. No generation. No provider change.

**CRITICAL PRECONDITION:** the dedicated Director model
(`gpt-6-sol`, thinking_effort HIGH) was **UNAVAILABLE** in the worker
runtime at V2-003 time (see `projects/quality_v2_003_director_blocking/
director_model_binding_v2_003.json`). The F2 DirectorIntent /
BlockingSpec design, CameraCoveragePlan, previz artifacts and the
Director critique pass are therefore **BLOCKED_ON_DIRECTOR_MODEL**.
No worker-authored substitute exists and none may be created without
explicit Owner authorization (no silent downgrade).

---

## 1. Target

F2 (`SEQ7_F2C`, master slot 24, take `take_91e4997b…`, asset
`e84ba56c…`). Debt: **QD-001 stays ACTIVE** — V2-002 ended
`REJECT_ALL` (ACTION_GOAL_NOT_SPATIALLY_LEGIBLE /
CHARACTER_LOITERS_AROUND_ROCK / THROUGH_STATE_NOT_OWNER_ACCEPTED);
candidates A and B are OWNER_REJECTED and never selected.

## 2. Why blocking, and what changes

V2-002 proved the narrative/action goal was correct (blind reads
matched the intent) while the rendered character still loitered around
the rock: spatial blocking was never an explicit authority layer. V2-003
freezes the missing layer
(`film_pipeline.director_blocking`): authority ordering
NarrativeBeat → ActionIntent → **DirectorIntent → BlockingSpec →
PerformanceSpec → CameraCoveragePlan** → ShotSpec → Compiler →
Provider, with ten deterministic gates (B1–B10), director-layer
semantic identity, and a compiler boundary (REFUSE_COMPILE without the
frozen authorities; no invented path/zones/rock interaction).

## 3. Director model binding (unchanged from V2-003)

`gpt-6-sol` · thinking_effort HIGH · role DIRECTOR_SHOT_DESIGNER.
Responsibilities and prohibitions as frozen in
`director_model_binding_v2_003.json`. If it is still unavailable at
V2-004 start, the experiment CANNOT run: status stays
DIRECTOR_MODEL_UNAVAILABLE until the Owner authorizes an explicit
substitute or the model becomes available.

## 4. Owner truth the Director must design within (frozen)

- TRIGGER: strong gust blocks passage.
- GOAL: pass through the stone gate and continue onward.
- NOT GOAL: interact with or shelter behind the rock.
- start_zone = BEFORE_GATE; target_zone = BEYOND_GATE;
  end_zone = BEYOND_GATE:FAR_SIDE_CLEAR.
- required_crossing = CENTER_GATE_OPENING; path_type =
  DIRECT_TRAVERSAL; forbidden_interactions = ROCK_CONTACT /
  ROCK_BRACE / ROCK_CIRCLE / ROCK_SHELTER; forbidden_reversal = true;
  must_exit_start_zone = must_reach_target_zone = true.
- No sword action. No extra obstacle interaction. No new narrative
  events.
- The ten gates (B1–B10) must pass on the frozen plan; any
  critique-triggered change creates a NEW plan revision (previous
  revision preserved) and reruns all gates.

## 5. Exact deliverable slots (BLOCKED_ON_DIRECTOR_MODEL)

| Slot | Status |
| --- | --- |
| F2 DirectorIntent v1 | BLOCKED_ON_DIRECTOR_MODEL |
| F2 BlockingSpec v1 (design completion: screen direction, waypoints, orientations, visibility requirements) | BLOCKED_ON_DIRECTOR_MODEL |
| F2 CameraCoveragePlan v1 (position, framing, axis, regions; no orbit/reversal/ambiguous axial move) | BLOCKED_ON_DIRECTOR_MODEL |
| F2 previz (F2_BLOCKING_TOPDOWN_V2_003.png, start/end schematics, previz mp4 — via `tools/build_v2_003_previz.py`) | BLOCKED_ON_DIRECTOR_MODEL |
| Director critique pass (7 questions) | BLOCKED_ON_DIRECTOR_MODEL |

The previz renderer itself is PROVEN on a synthetic fixture
(`tests/test_director_blocking_v2_003.py::test_25_…`). The moment a
frozen F2 plan exists, the artifacts render deterministically.

## 6. Max mutation budget (for the future live experiment)

- Generates: **≤ 2** (admission field max_generate_budget = 2).
- Uploads: 0 (the F2 reference stays already-bound provider media).
- Provider switch: 0 — the unchanged qualified Flow/Veo route
  (`flow_veo / veo_3_1_r2v_lite / project 93a579b4-… / clean-pro-
  qualified`).
- Canonical mutation: 0 until a candidate reaches OWNER_SELECTED
  through the immutable Owner decision surface, then at most ONE
  promotion transaction (V2-003+ promotion adapter qualification).

## 7. Candidate design frame (for the future live experiment)

- **A:** pure direct traversal, minimal performance (the frozen
  BlockingSpec executed plainly).
- **B:** same blocking, only bounded biomechanics refinement
  (PerformanceSpec deltas; identical BlockingSpec and camera plan —
  the director-layer semantic identity must show B differing from A
  ONLY through the performance/performance-spec component, while
  blocking stays identical).
- Both: NO rock interaction (gates B4/B6 refuse otherwise).

## 8. Owner decision surface (mandatory questions)

1. Where does he start?
2. Where is he trying to go?
3. Does he cross the gate?
4. Where does he end?
5. Does he ever treat the rock as the destination?

Blind protocol as in V2-002 (neutral labels first, answer key
separate, leak-checked).

## 9. Stop conditions

1. Director model still unavailable → DIRECTOR_MODEL_UNAVAILABLE (no
   substitution).
2. Any gate failure on the frozen plan → BLOCKED_INVARIANT (revise as
   a new revision, never rewrite).
3. Ambiguous provider effect → OWNER_AMBIGUITY_GATE (one submit, no
   retry).
4. Budget exhausted without a review-ready candidate.
5. Owner rejection (candidates stop; QD-001 stays ACTIVE).
