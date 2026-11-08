# Production process v2 — interaction contract (Claude × Codex brainstorm, 2026-11-08)

Trigger: Owner on take SC02_g1_t3 — "who is she talking to? The relationships do not seem to be guaranteed."
MARA's performance was right, but she spoke to an empty counter: camera A stands on THEO's side, the still showed
the place where THEO stands empty, and `plan.py` wrote "Only MARA in frame." The same pattern exists in SC02_g2,
SC03_g2, SC04_g1 and SC05_g1.

Method: Claude (Tech Lead) and Codex gpt-6.1-sol wrote independent round-1 drafts, cross-critiqued in round 2, and
Codex reviewed this plan in round 3. Codex's verdict was "AGREE WITH CHANGES", with five required edits, all applied:
- P16-01 reconciles intent receipts.
- P16-07 is split into a pilot (P16-07a) and a rollout (P16-07b).
- Prompt compilation comes before stills.
- P16-06 must be proven at the generation entry point.
- P16-04 needs human evidence on each relation question.

Positions are marked **[agreed]** or **[decided: who, why]**.

## 1. Root cause (agreed)

The pipeline records people, props, actions and camera labels but never connects them into a **staged encounter**.
Missing facts:
- Who each line is spoken **to**.
- Where the listener **is** when not in frame.
- Which **world mark** each person stands on. Positions are free text such as "at the window, frame-left", which is
  camera-relative and reused for every camera.
- How the listener is **anchored** in the frame.

Downstream, the still and video prompts are compiled separately and drop the hidden partner. No review question
asks about the listener. Four stages missed it: shot design, prompt compile, still review and take review.

## 2. Locked principles [agreed]

1. **Scene presence ≠ frame visibility.** Hiding THEO from a shot keeps his mark, listening role, gaze target and
   prop custody.
2. Every relation that must hold on screen exists as data. Still and video prompts are compiled from **one**
   placement source.
3. Machine checks guarantee a coherent specification, not the pixels. Pixels need still and full-motion review by
   the Owner.
4. **Coverage is HOW, so the Tech Lead chooses it.** The Owner approves the resulting storyboard and stills, plus
   any change of meaning.
5. Restaging creates a new design that is re-rated; it is not a waiver. Extra drafts do not cure a structural
   difficulty.
6. A VLM judge is advisory. It ranks and flags drafts and never hides them from the Owner.
7. Prove one exchange (SC01_g2 → SC02_g1 → SC02_g2) before spreading the fix to the rest of the film.

## 3. Stage map

| # | Stage | Records | Checks | Approves |
|---|---|---|---|---|
| 1 | Development | `01_story`: premise, conflict, ending, script revision, rights | goal, obstacle and outcome present; rights | Owner |
| 2 | Dramatic design | scenes, **local playable beats** (want, tactic, response, change), causes and effects, reveals | every scene turns something; each reveal has a carrier; effects cite causes | Owner (creative) |
| 3 | Character and relationship bible | looks, costume, voice bible plus reference take, wants; directed relations (stance, power, knowledge) per beat | relation and knowledge changes have a causing beat | Owner |
| 4 | World and geography | `locations.*.layout`: zones, barriers and openings, objects, cameras, **actor marks** | marks inside accessible zones; barrier sides; camera setups | Tech Lead |
| 5 | Blocking | per state: actor `mark`, posture, facing, gaze target; prop custody; moves | no teleport; no body path through a barrier; custody has one holder; posture change across a cut declared | Tech Lead |
| 6 | Coverage | `04_shots`: setup, size (**explicit `camera.size` is authoritative**), addressees, listener anchors, reaction pairs, inserts | every line has a recipient; anchors valid; OTS foreground is the distinct partner | Tech Lead; Owner approves the board |
| 7 | Generability | GREEN / AMBER / RED / **UNKNOWN** with evidence; allowance cap | RED blocks without an Owner exception; UNKNOWN gets one exploratory send | Tech Lead; Owner for exceptions |
| 8 | Prompt compile (before any still) | still and video prompts from one staged source, emitted together (`plan.py:368`) | same participants and placement in both; no dangling pronoun or held-prop clause; size words consistent | machine |
| 9 | Stills, storyboard, animatic | start/end stills, timed board with scratch sound; generation manifest binds the exact approved images and the prompt and input hashes | listener readable; no empty listener position; compatible endpoints; sequence reads; a material recompile invalidates the affected approval | **Owner** |
| 10 | Generation | intent receipt, exact attachments, cost | go-live lock; attachment identity; ambiguous sends reconciled before a resend | **Owner lock** |
| 11 | Dailies and QC | autoqc, motion, audio, **relation questions** | missing checks stay UNASSESSED | **Owner** accepts |
| 12 | Repair | defect class → clip edit / regenerate / restage / abandon | repeated defect forces a changed approach; defect counts survive version bumps | Tech Lead; Owner for meaning or spend |
| 13 | Editorial | `05_edit`, reaction timing, J/L cuts, lock | cut continuity on the real cut points; causality reads | Owner |
| 14 | Sound, finish, delivery | dialogue, ambience, SFX (sound carries off-screen actions), grade, master | words and speaker; voice matches the reference; loudness; rights | Owner |

## 4. Category catalogue

For each of the Owner's 168 categories (`CATEGORY_COVERAGE_168.md`), we track one status ladder:
**recorded → validated → compiled → observed → Owner-approved**. "HAVE" in the matrix means recorded or validated
only. New or strengthened categories:
- **Relations:** directed stance, power basis, tactic and knowledge per beat.
- **Address:** speaker, addressees and mode (in_person / offscreen / phone / voiceover / self) per line.
- **Blocking:** marks, posture, facing, gaze target, prop custody and transfers.
- **Listener anchoring and frame presence** per shot.
- **Encounter:** continuous physical state across screenplay scene numbers.
- **Generability evidence** and exception records.

**Physical camera operation is N/A; visual intent and its verification are not** (framing, lighting outcome).

## 5. Relationship model

| Relation | Data (proposed) | Invariant | Prompt text | Review question |
|---|---|---|---|---|
| R1 Address | `ShotDecl.addressees {line_id: [chars]}`; mode | in_person addressees present in the encounter | "She speaks to THEO, …" (named, never a bare "him") | Who is X talking to? |
| R2 Listener anchor | `ShotDecl.listener_anchors {char: {mode VISIBLE \| OTS_FOREGROUND \| OFF_FRAME, side, placement, established_by}}` | OTS needs the distinct partner as `foreground`; OFF_FRAME needs CLOSE or tighter, an earlier establishing shot, and composition evidence | OTS: "THEO's blurred shoulder and the back of his head fill the near left; MARA beyond the counter faces him through the gap." Off-frame: "THEO stands just off frame-left beside the camera; her eyes go just past the lens to the left." | Can you see the listener or their shoulder, or does X look just past the lens toward them? Is the listener's place shown empty? |
| R3 Spatial | `SetLayout.marks [{id, at, zone}]`; `ContinuityState.blocking {char: {mark, posture}}` | marks resolve; no barrier crossing; moving the camera needs a new setup, never moving the actor's mark | from mark and setup: near/far order, barrier side | Are near/far order and barrier sides correct? |
| R4 Gaze | `ShotDecl.gaze_target` (character / mark / object) | resolves; lens gaze only when declared | "eyes on THEO" / "looks down at the coins" | Does X look at the target the whole time? |
| R5 Custody | prop holder or support per state; transfers with a cause | one holder; no prop held by a hidden person in prompt text | visible props only; off-screen custody stays in data | Correct holder, hand and support? |
| R6 Shot to shot | edit relation: continuous / reverse / reaction / insert / ellipsis | reverse keeps world positions; an ellipsis declares what it skips | correct opening state per generation | Is everyone where the previous shot left them? |
| R7 Encounter | `SceneSpec.encounter_id`; hand-off across scene numbers | `continuity.py` hand-off runs over the encounter, not only `same_scene` | — | After the cut, does the posture and prop state match? |
| R8 Relations and knowledge | beat `relationships[]`, `knowledge_changes[]` | changes have causes; no use of knowledge before it is acquired | written as observable behaviour (stimulus, tactic, pause), not labels | Does the change read after its cause, without contempt or indifference misreads? |

**Projection [decided: Codex; Claude agrees].** A 2D cone over the floor plan is a later **contradiction detector**
(WARN / UNRESOLVED), never a visibility oracle. A point has no width, height or occlusion, and shot size does not fix
a field of view. It is not in the first slice. A direct contradiction, such as an OTS shot whose foreground is not
the partner, BLOCKs at once.

## 6. Script processing for this generator

1. Keep four levels apart: screenplay scene, dramatic beat, editorial shot, generation clip. Keep line provenance.
2. Beat = actor wants X → tactic Y → response Z → a fact, relation or physical state changes.
3. Mark the evidence the audience must see; a suitcase alone does not prove retirement.
4. **Block before choosing coverage.** Settle marks, barrier, gaze, props and the listener's position first.
5. One generation = one stable setup + one principal action (speech plus a small glance is fine). Duration follows
   the action and speech plus handles, within 3–15 s; there is no fixed "two 8 s per scene".
6. **Dialogue across a barrier between two people [decided: Tech Lead, Codex agreed]:**
   - Establish readable geography first: a master or two-shot, or inherit it within the encounter.
   - Then complementary **OTS** shots are the default.
   - A clean single is allowed at CLOSE or tighter only with an OFF_FRAME anchor after geography is established, and
     the still must not show the listener's place empty.
   - A wider clean single needs a written directing exception backed by the composition.
7. Add reaction shots when information changes a listener, not after every line. Inserts carry essential evidence
   as their own shots.
8. An action the generator cannot make moves off-screen and is carried by sound, while cause → result → response
   still reads. A cut-around needs a legible interval: coins do not appear stacked instantly.

## 7. Generability v2 [decided: Codex rule set, Claude agrees]

- **Values:**
  - GREEN: a supported action family **with matching conditions and evidence**.
  - AMBER: understood variability.
  - RED: an evidenced hard constraint or a coupled interaction.
  - UNKNOWN: no rule matched or not enough evidence.
- **Aggregation:** RED > UNKNOWN > AMBER > GREEN. SETUP and HOLD phases are also scanned for constraints such as a
  pinned mechanism at a partial position.
- **Allowances are caps, not permission to spend:**
  - GREEN: 1 send.
  - AMBER: up to 2, reviewed one after the other.
  - UNKNOWN: 1 exploratory send after approved stills and targeted review questions.
  - RED: 0 without an exception.
- **Exceptions:** only the Owner may authorise a RED exception. The record carries the shot version and input
  fingerprint, the reason, the evidence, an attempt and credit cap, and an expiry. The rating stays RED.
  - An accepted historical take covers reuse of that exact take only.
  - The current free-text `generability_waiver` values on SC01_g1 and SC01_g2 become "accepted take reuse" records.

## 8. Film04 defects mapped to the stage that missed them

| Defect | Stage that should catch it | Check |
|---|---|---|
| MARA talks to nobody (SC02_g1 t3) | Coverage + compile + still review | addressee + listener anchor; one placement source; "is the listener's place shown empty?" |
| Shutter drifts at a partial position (SC01_g1 ×5) | Generability | partial articulated mechanism → RED, restage before stills |
| Body lowering moves the pinned shutter (SC02_g1 t1, t2) | Blocking + generability | body path against a fixed opening → restage |
| First and last frames far apart | Still-pair review | compatible endpoints and a feasible path; pixel delta cannot prove feasibility |
| Several actions per clip | Beat decomposition | count principal state-changing actions |
| 10 of 19 sent receipts did not end PASSED | Generation | exact attachment identity; reconcile ambiguous sends |
| Jacket drift | Look development | Video preflight does not check character-reference attachments: `plan.py` passes `reference_sets=[]` and `TEXT_ONLY`. Actual reference use in stills or video needs attachment evidence |
| "medium close-up: close-up" in the same prompt | Compile | explicit `camera.size` is authoritative on the new route |
| SC01 → SC02 stand-to-sit jump unflagged | Continuity | encounter hand-off on posture; `_handoff()` skips cross-scene positions today |

## 9. Plan (P16, supersedes the order of completion-plan phases B–C)

| Item | Work | Done when |
|---|---|---|
| P16-01 | Reconcile the ledger. Facts: 10 takes and 85 credits logged; 19 sent receipts, 10 of them not PASSED; 2 takes ACCEPTED; SC02_g1_t3 awaits the Owner's verdict. 256.8 − 85 = 171.8 is the cap minus logged credits **before reconciliation**, not a spending allowance. `generate.py:159` also counts sent receipts whose ids are missing from the log: 170 spent or reserved, 86.8 left. Receipt ids are offset from take ids (receipt `SC02_g1_t4` = take `SC02_g1_t3`). | Take entries, intent receipts and attributable provider outcomes reconciled: receipt ids mapped to registered takes; confirmed pre-send failures told apart from unresolved effects; the generator's remaining-budget figure verified without double counting; Owner verdict on t3 recorded in the Owner's words |
| P16-02 | **Interaction-contract slice:** `PreflightLimits.interaction_contract`; `SetLayout.marks`; `ContinuityState.blocking`; `SceneSpec.encounter_id`; `ShotDecl.addressees / listener_anchors / gaze_target`; checks per §5 | Fixtures: v3 as shot BLOCKs. Each false OFF_FRAME claim BLOCKs: missing establishing shot, unresolved mark, contradictory foreground, absent composition evidence. OTS v4 passes; an established CLOSE off-frame single passes. film01–03 unchanged and green. Pixel visibility stays with Owner review |
| P16-03 | Compile: one placement clause for both prompts; no "Only X in frame" while a partner is present; no dangling pronoun or held-prop clause; explicit `camera.size` wins | prompt-agreement test; off-screen jar custody test |
| P16-04 | Review: listener identity, empty listener place, gaze, barrier side in still review and take dailies (`takes.py`). Questions alone prove nothing: today ingest reads `qc`, not the questions (`takes.py:199`) | Every applicable relation question needs explicit human evidence in its required QC group before a take can be ACCEPTED; unanswered relation questions stay UNASSESSED. Affected existing takes get a supplemental review sheet; historical sheets are not overwritten |
| P16-05 | Encounter continuity: hand-off on mark and posture across scene numbers in `continuity.py`; ellipses declared | SC01_g2 → SC02_g1 stand-to-sit is flagged until declared or restaged |
| P16-06 | Generability v2 (§7); migrate the waivers | Proven through the generation entry point with an offline runner, Owner and budget gates unchanged: RED cannot generate through an accepted-take-reuse record; expired or mismatched exceptions refuse; UNKNOWN stops after its one exploratory send; AMBER's second send waits for review; version bumps keep attempt and defect history |
| P16-07a | **Pilot exchange** SC01_g2 → SC02_g1 → SC02_g2: marks, addressees and anchors; SC02_g1 v4 OTS over THEO; SC02_g2 OTS over MARA; the SC01/SC02 stand-to-sit decision | `film.py plan` PASS under the contract for the pilot; pilot board and stills; **Owner approves them** |
| P16-08 | Send reliability offline (P15-06): exact start/end attachment binding; reconcile ambiguous sends | demonstrated offline on recorded UI states |
| P16-09 | **Live pilot:** corrected SC02_g1, then SC02_g2, at 360p on Omni Flash; full-motion review; both adjacent cuts (SC01_g2 \| SC02_g1, SC02_g1 \| SC02_g2) | Owner accepts both takes and both cuts |
| P16-07b | **Remaining encounter rollout** SC03–SC06: audit SC03_g2, SC04_g1 and SC05_g1; merge with P15-07; timed animatic with scratch sound | `plan` PASS under the contract; Owner approves the board and stills |
| P16-10 | Shoot SC03 → SC06 exchange by exchange. Later: projection detector, identity-reference route probe (P15-05), advisory VLM judge (P15-04), voice and sound evidence | all takes Owner-accepted; cut, sound and master checked; Owner final acceptance |

**Before the next live send:** P16-01 through P16-06, P16-07a and P16-08 are done, and the Owner has approved the
pilot board and stills. Order: P16-01 → P16-02 → P16-03 → P16-04 → P16-05 → P16-06 → P16-07a → P16-08 → P16-09 →
P16-07b → P16-10.
Best-of-N in bulk, the VLM judge and a coverage-pattern generator are not prerequisites.

## 10. Owner decisions (product only)

1. **Verdict on SC02_g1_t3.** The performance is right; the relationship failed.
2. **P15-07 restage of the SC04/SC05 RED beats.** Both reviewers recommend option 2:
   - The shutter opening is carried by sound.
   - The coins are shown as a static aftermath, with a legible interval before the counted stacks.
   - The line "Pour it out" is kept.
3. **Approve the SC02 board and stills** once P16-07 produces them.
