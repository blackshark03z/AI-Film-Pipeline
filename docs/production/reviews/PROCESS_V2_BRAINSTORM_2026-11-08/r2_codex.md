**Lock the interaction contract; reject projection as proof of visibility.** Claude correctly identifies missing staging data, but overstates what a floor-plan cone can establish and moves too quickly from risk classification to bulk generation.

Read-only basis: `D:\AI FILM MAKER\AFP-stable`, `feature/drama-preprod-p0`, HEAD `c910564c209b7e5df78bc5454c6bf9f5e2764b0c`; untracked `uv.lock` preserved. MAR access required unavailable approval. No accepted `POLICY_REF` was supplied, so these are advisory positions, not an implementation handoff or canonical project decision.

**Critique of Claude**

- **Agree and lock:** scene presence differs from frame visibility; addressees need explicit identity; blocking needs world-relative marks; still/video prompts need the same placement source; relationship questions belong in existing dailies; continuity must survive screenplay scene boundaries.
- **The alleged coordinates are inferred.** THEO’s approximately `[0.62,0.50]` is a proposed mark, not an existing authoritative position. Freeze it before using it to prove a contradiction.
- **“Inside cone means visible” is wrong.** A point has no shoulder width, height, posture, or occlusion. Nearer means smaller camera-space depth, not necessarily foreground pixels. A person behind the subject can be completely occluded. Do not derive `visible` automatically from this model.
- **This is not solely a data defect.** Correct data can still compile into contradictory wording or produce wrong pixels. SC02_g1 requires checks at specification, compilation, still review and moving-take review.
- **A coverage-pattern library is premature.** First repair one exchange using existing OTS/SINGLE coverage. Generating a replacement shot list before validating that exchange spreads an unproven solution.
- **Reject fixed “three references,” “best-of-3 RED,” and “start/end frames must be near.”** Reference count depends on the actual supported route; extra drafts do not cure structural difficulty; compatible endpoints matter more than pixel proximity.
- **Several rules are too absolute:** direct lens gaze can be intentional; reverse eyelines need compatible targets rather than mechanically opposite labels; every dialogue line needs an address mode, including self, phone and voiceover—not necessarily an in-room listener.
- **The restage remains unsafe:** [P15-07](<D:/AI FILM MAKER/AFP-stable/docs/production/FILM04_RESTAGE_PROPOSAL.md>) retains SC02_g1 v3 unchanged and calls a pour insert “RED waived.” Neither addresses the underlying failure.

**Q1 — Projection**

Use a 2D cone as a **contradiction detector and staging sketch**, never a visibility oracle. **No authoritative half-angle mapping by shot size.** CLOSE describes subject scale; different camera distances and fields of view can produce it. Independently normalized floor-plan axes also need a known aspect ratio before angles mean anything. If projection becomes necessary, declare a per-setup/per-shot horizontal half-angle, informed by the approved composition; do not derive it from size. Classify depth and angular position, then report visibility **UNRESOLVED** where body extent, vertical framing or occlusion matters. That is an evidence status, not a new severity: exploratory planning may WARN; required listener visibility/cropping unresolved at live-readiness must BLOCK until resolved by a reviewed still or adequate geometry. Direct contradictions BLOCK immediately. A mark behind the camera is horizontally behind; do not invent “off-frame left/right” at an undefined camera-origin or rear-axis position. This catches suspicious central occupancy without claiming a shoulder must appear.

**Q2 — Coverage authority**

**Amend and accept for film04.** My previous “Owner chooses OTS or single” was wrong under the standing WHAT/HOW rule. Tech Lead chooses coverage; Owner approves its resulting storyboard/stills and any changed meaning. Default this barrier exchange to complementary OTS after readable geography. Permit a clean single at CLOSE or tighter when the listener’s persistent mark, offscreen placement, gaze target and establishing shot are explicit, and the still does not expose that position empty. This is a conservative production rule for this exchange, not a universal filmmaking law: a wider clean single can be legitimate, but requires a deliberate directing exception supported by the composition. OTS itself still needs shoulder placement, barrier-side and identity review.

**Q3 — Generability**

Use **GREEN / AMBER / RED / UNKNOWN**, independently of staging validity. GREEN requires a supported action family **and matching conditions** with attributable evidence for the intended route; AMBER means understood variability; RED means an evidenced difficult constraint or coupled interaction; UNKNOWN means insufficient coverage/evidence, including unmatched prose. Aggregate RED first, then UNKNOWN, then AMBER, then GREEN; scan SETUP/HOLD for constraints even when they contain no action. Tech Lead records ratings and evidence. Restaging creates a new design that is re-rated—it is not a waiver. Only Owner may authorize a RED exception, recorded against exact shot version/input fingerprint, reason, evidence, attempt/credit cap and expiry; Tech Lead records that authorization. The rating stays RED. An accepted historical take supports reuse of that exact take, not permission to generate replacements. UNKNOWN permits offline work, requires approved stills and targeted review questions, and requires a bounded authorization for **one exploratory video**, not an automatic draft bundle. Proposed initial allowances: GREEN one; AMBER up to two sequentially reviewed attempts; RED zero without exception. Allowances are caps, not spend permission.

**Q4 — Scene versus encounter**

**Extend existing scenes/states; do not create another state store.** Add optional `SceneSpec.encounter_id`; SC01–SC05 share one ID. The existing globally keyed `03_preprod.states` holds actor marks/posture, props, looks and environmental state; shot `start_state`, `end_state` and `previous_generation_id` remain the links. An encounter is a grouping over that chain. Existing per-scene occupancy remains, but validate its boundary agreement rather than resetting presence at each scene number. In `production/continuity.py`, use continuous encounter membership—not only `same_scene`—for physical handoff, once-action repetition and emotional carryover. Keep story-time ordering separate. An ellipsis must explicitly declare its skipped transition; scene renumbering cannot silently authorize it. Importantly, the current `_handoff()` does **not** check cross-scene positions at all, so replacing free text alone will not fix the SC01→SC02 gap.

**Q5 — Minimum first slice**

Paths below are relative to the repo; these are proposed additions. Preserve existing free-text fields for legacy packages.

| Field/type | Schema file → package location |
|---|---|
| `interaction_contract: bool = False` | `drama/preflight.py:PreflightLimits` → `03_preprod.preflight` |
| `marks: list[ActorMark] = []`, each `{id: Ident, at: tuple[float,float], zone: Ident}` | `production/set_layout.py:SetLayout` → `03_preprod.locations.*.layout` |
| `blocking: dict[str, ActorPose] = {}`, pose `{mark: Ident, posture: str}` | `drama/continuity.py:ContinuityState` → `03_preprod.states.*` |
| `encounter_id: Ident \| None` | `production/sections.py:SceneSpec` → `03_preprod.scenes.*` |
| `addressees: dict[int,list[str]] = {}` keyed by script line | `production/sections.py:ShotDecl` → `04_shots.generations[]` |
| `listener_anchors: dict[str,ListenerAnchor] = {}` keyed by listener | Same; anchor `{mode: VISIBLE\|OTS_FOREGROUND\|OFF_FRAME, side: LEFT\|RIGHT\|BEHIND_CAMERA\|None, placement: str, established_by: Ident\|None}` |
| `gaze_target: str \| None` resolving a character/mark/object | Same |

Enable the contract for film04 and require complete data throughout its affected encounter. BLOCK missing/absent addressees, unresolved marks, missing anchors, OTS without the correct distinct `foreground`/`visible` participant, and unsupported OFF_FRAME declarations. An OFF_FRAME single requires CLOSE, earlier geography and approved composition evidence; moving the camera requires a new setup, not moving THEO’s mark. **No projection solver is necessary in this slice.**

In [`production/plan.py`](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/plan.py>), compile one placement clause into both prompts; retain offscreen state without emitting its full visible-character description or dangling held-prop clauses. Make explicit `camera.size` authoritative on the new route; retain coverage-derived size only for legacy packages. Add listener identity, empty-position, eyeline and barrier questions to `production/takes.py`, using existing spatial/character groups.

Acceptance fixtures must demonstrate: original v3 fails for missing relationship data; a falsely asserted offscreen listener remains blocked without supporting composition; staged OTS v4 passes with THEO foreground; an established legal close single passes. Also test prompt agreement, offscreen jar custody and cross-scene posture continuity. Leave film01–03 on the unchanged route and run their existing tests, particularly `test_production_film03_golden.py`; do not rewrite goldens. A default-false field alone must not allow film04 to bypass enforcement.

**Q6 — Completion order and the next live send**

First reconcile custody: [the index](<D:/AI FILM MAKER/AFP-stable/films/film04_last_ticket/takes/index.json>) records **10 takes, 85 credits, two ACCEPTED, one GENERATED**; `SC02_g1_t3` points to `SC02_g1_t4.mp4`, and its dailies checks remain UNASSESSED. Those labels do not independently establish Owner acceptance. Reconcile actual spend, pending/ambiguous sends and protected accepted footage before budgeting. Then freeze Tech Lead’s encounter staging and P15-07 treatment together: my recommendation is sound-led shutter opening, static poured-coin aftermath, and an editorially legible interval before counted stacks; retain the quoted invitation to pour. Owner approves the resulting meaning/stills. Complete the minimum slice, audit all affected singles, and review a timed board with scratch dialogue/sound. Demonstrate exact start/end attachment binding and ambiguous-send reconciliation offline. Only then seek the required bounded live authorization for **one corrected SC02_g1**, followed by full-motion review and its adjacent cut with accepted SC01_g2. Expand production after that exchange works. Bulk best-of-N, a VLM judge and a coverage generator are not prerequisites. Under the same 256.8 total cap, 85 logged leaves 171.8 **before reserves and unreconciled charges**, not a fresh generation allowance.

**Five remaining priorities, ranked**

1. **Audience causality:** cut-arounds must preserve decision → action/result → response; “coins appear stacked” needs readable elapsed work.
2. **Sound/voice:** pin an accepted voice excerpt, accurate words/speaker and dialogue handles; shutter/stamp sounds become essential story evidence when actions move offscreen.
3. **Performance:** reuse existing intent/prohibited-misread cues; specify stimulus, tactic, pause and reaction timing instead of emotion labels alone.
4. **Identity conditioning:** verify the actual attachment route before promising reference control; inspect identity/costume throughout motion and scale changes.
5. **Dependency invalidation:** staging, recipient, camera or size changes must stale prompts, still approvals and downstream readiness while preserving historical take evidence.

Skipped: edits, tests, playback and live-provider checks; no files changed.  
Risk: coherent specifications reduce preventable failures; they cannot establish generated performance or Owner acceptance.

