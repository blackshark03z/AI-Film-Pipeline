**My independent view: the missing production primitive is an interaction contract.** The pipeline records people, props, actions and camera labels, but does not consistently connect them into a staged encounter. A correct performance can therefore occur in an impossible or empty relationship.

**Keep scene presence separate from frame visibility.** Hiding THEO from a shot must preserve his location, listening role, eyeline target and possession of the jar.

Read-only basis: `D:\AI FILM MAKER\AFP-stable`, branch `feature/drama-preprod-p0`, HEAD `c910564c209b7e5df78bc5454c6bf9f5e2764b0c`; untracked `uv.lock` preserved. This is an advisory proposal for Claude, not a canonical priority change. No accepted `POLICY_REF` was supplied; MAR access was rejected because approval is unavailable in this session.

## A. Complete production stage map

Extend the existing package. Do not create another production database or parallel truth system.

| Stage | Inputs → recorded outputs | Checks / gate | Approval |
|---|---|---|---|
| 1. Development | Brief, audience, rights → `01_story`: premise, theme, protagonist, conflict, intended ending, script revision | Rights disposition; goal/obstacle/outcome present; script revision matches package | Owner approves intent and script |
| 2. Dramatic design | Script → scenes, **local playable beats**, causes, turns, audience information | Every scene changes something; every required revelation has a carrier; consequences reference causes | Director proposes; Owner approves creative changes |
| 3. Character and relationship bible | Characters/beats → identity, costume, voice, wants, relationships, power and knowledge changes | IDs resolve; changed relationship/knowledge has a causing beat | Owner approves designs and interpretation |
| 4. World and geography | Locations → existing `locations.layout`, barriers, openings, actor marks, prop stations, camera setups | Accessible zones, valid marks, camera view, barrier and operator-side consistency | Director checks; Owner approves geography |
| 5. Blocking | Beat + geography → start/end actor positions, facing, gaze, prop custody, movement | No teleportation, impossible reach or unexplained ownership change | Director; material restages to Owner |
| 6. Coverage | Blocking + dramatic emphasis → `04_shots`, dialogue assignments, listener anchors, reaction pairs, inserts | Every beat covered; recipient identified; framing supports required evidence; compatible cuts | Director proposes; Owner approves storyboard |
| 7. Generability | Beat/action + conditioning route → risk reasons, fallback, duration, bounded draft allowance | RED restaged or explicitly authorized; unknown capability remains unknown | Tech Lead assesses; Owner approves exceptions |
| 8. Stills/storyboard/animatic | Locked designs + shot states → candidates, selected image hashes, timed board | Relationships readable; correct first instant; no contradictory start/end geometry; sequence comprehension | **Owner approves stills and board** |
| 9. Prompt compilation | Approved state + shot → still/video prompts, attachment manifest, dependency fingerprint | Same participants, placement, framing and props across both prompts; duration and speech fit | Machine validation; director inspection |
| 10. Generation | Approved inputs + explicit authorization → intent, submission identity, exact outputs, costs | Actual model/settings/attachments verified; ambiguous submission reconciled before another send | **Owner authorizes live work** |
| 11. Dailies/QC | Take + its exact contract → technical findings, semantic questions, full-motion review | Recipient, performance, action, identity, state and sound reviewed; missing checks remain UNASSESSED | **Owner accepts/rejects takes** |
| 12. Repair | Classified defect → edit, regenerate, restage or abandon; new version and invalidations | Repair preserves dramatic meaning; repeated defect triggers changed approach | Director proposes; Owner approves creative/spend changes |
| 13. Editorial | Accepted takes → `05_edit`, trims, reaction timing, J/L cuts, picture lock | Review actual cut boundaries, causality, geography, pacing and comprehension | Owner approves cut/picture lock |
| 14. Sound/finish/delivery | Locked cut → dialogue, ambience, SFX, music, grade, titles, versions, manifest | Word/speaker accuracy, sound perspective, sync, loudness, full decode, rights, disclosure, archive restore | Owner approves final master and delivery |

The stages iterate, but a downstream workaround must identify which upstream decision changed.

## B. Category catalogue: what must be decided

The [168-category matrix](<D:/AI FILM MAKER/AFP-stable/docs/production/CATEGORY_COVERAGE_168.md>) reports **58 HAVE / 83 PARTIAL / 1 GAP / 26 N/A**. These describe implementation responsibility, not achieved filmmaking quality.

I would assess each relevant category through **recorded → validated → compiled → observed → Owner-approved**, using existing fields and evidence records.

| Group / category IDs | Required decisions | Present limitations |
|---|---|---|
| Story, 1–14 | Audience promise, theme, protagonist agency, stakes, causal beats, scene turns, dialogue/subtext, rights, revisions | Concept/audience/premise largely presence checks. Macro beats exist; local playable beats and recipient/knowledge changes need stronger representation |
| Direction, 15–34 | POV, emphasis, visual rules, performance, pacing, coverage, transitions | Vision and rules often declared without shot enforcement. Blocking/axis HAVE does not guarantee an encounter |
| Design/preproduction, 35–56 | Identity references, costume/day, location plate, geometry, barriers, props, light, sound plan, risk, budget | Layout exists. Character marks, listener anchoring, occlusion and framing geometry remain incomplete; lighting/composition have compilation gaps |
| Production, 57–90 | Framing, performance, interaction, motion, background activity, take lineage, review | Interaction, delivery and reaction timing remain PARTIAL. Output relationships are not validated by screen-side labels |
| Editorial, 91–106 | Selects, causal assembly, cut-point state, reactions, rhythm, transitions, lock | Useful EDL and lock machinery exists. Trimmed-state continuity and narrative meaning need actual cut review |
| Sound/finish, 107–130 | Dialogue accuracy, voice, cleanup, Foley/SFX, ambience, perspective, score, grade, reframing | Foley is listed GAP; sound perspective and dialogue editing are limited. Generated sound is not automatically separated dialogue |
| QC/delivery, 131–156 | Semantic, spatial, action, temporal, audio and technical evidence; variants, rights, archive | Stronger technical machinery than semantic verification; several categories remain human/UNASSESSED |
| Management, 157–168 | Dependencies, revisions, approvals, spend, failures, rights, reporting | Design dependencies exist; relationship/blocking changes need equivalent invalidation |

I disagree with marking framing, camera placement and lighting outcomes N/A merely because there is no physical camera. **Physical operation is N/A; visual intent and verification remain necessary.** Likewise, Foley is a responsibility that licensed effects can satisfy, not necessarily a recording subsystem.

Some matrix descriptions lag newer backlog entries—for example shot versioning and archive rehearsal. Reconcile descriptions against code before expanding features.

## C. Relationship model

Use existing `01_story`, `02_direction`, `03_preprod.states/layout`, `04_shots` and take reviews. The following are **proposed field extensions**, not implemented capabilities.

Machine checks can guarantee a coherent specification. They cannot guarantee that the generated pixels obey it; that needs media review.

### 1. Emotional, power and knowledge relationships

**Schema**

```text
beat:
  id, scene_id, causes[], preconditions[], effects[]
  relationships[]:
    from, to, stance_before, stance_after,
    power_basis, tactic, change_cause
  knowledge_changes[]:
    character, fact_id, learned_from, causing_beat
```

Relationships are directed: MARA’s view of THEO need not equal his view of her.

**Invariants:** referenced characters/facts/beats exist; changes have causes; a reveal cannot depend on knowledge its recipient has not acquired, unless explicitly mistaken, deceptive or supernatural.

**Compilation:** turn dramatic intent into observable behavior: “She maintains a level gaze, then releases her breath before answering.” Do not expect “power shifts” alone to direct a performance.

**Review:** Still—does posture/composition support the intended status? Take—does the change occur after its cause, and does it read as the intended tactic rather than contempt, romance or indifference?

### 2. Speaking, addressing and listening

**Schema**

```text
utterance:
  script_line, speaker, addressees[], listeners[],
  mode: in_person | offscreen | phone | voiceover | self
shot:
  utterances[], gaze_target,
  listener_anchor:
    character, visibility: full | partial | offscreen,
    relative_to_camera, crop_reason, established_by_shot
```

**Invariants:** ordinary interpersonal speech has an addressee; participants are present or have an explicit communication channel; gaze target resolves. OTS foreground must be a different, partially visible participant. Offscreen listeners retain a physical position.

**Compilation:** still and video both specify who listens and where. Pronouns follow an identified referent.

**Review:** Still—can we locate the person being addressed, including just outside frame? Take—does the speaker address that position throughout, and does the listener’s response follow the correct line?

Do not require everyone to look at their partner constantly. Looking down, avoiding eye contact and looking at a prop should be explicit gaze targets.

### 3. Geography, camera, barriers and screen direction

**Schema**

```text
actor_state: mark_id, facing, posture, gaze_target
mark: zone, x, y, elevation
camera_setup: position, aim, height, field_of_view, axis_side
barrier: boundary, openings[], permitted_passages[]
frame_presence[]: character, visibility, screen_region, occluded_by
```

Reuse `SetLayout`; add scale only where metric distance/reach matters.

**Invariants:** marks belong to accessible zones; movement does not cross a solid barrier; camera and actor placements are compatible; projected presence agrees with declared crop/occlusion; axis crossing is declared. Unspecified geometry produces an unresolved check, not invented certainty.

Camera placement near a listener’s mark is normal reverse-shot practice. The defect is an unexplained empty position or inconsistent view—not simply a camera near THEO.

**Compilation:** “THEO’s blurred shoulder occupies the lower-left foreground; MARA sits beyond the counter, facing him through the opening.”

**Review:** Still—correct near/far order, barrier sides, gaze height and listener region? Take—do these relationships survive movement without someone passing through glass or changing sides?

### 4. Character–object relationships

**Schema**

```text
prop_state:
  prop_id, holder, hand, support, location, orientation,
  mechanism_state, contents_state
transfer:
  prop_id, from, to, causing_action, contact_interval
```

**Invariants:** one authoritative custody/support state; transfers have causes; an object cannot simultaneously remain in THEO’s hands and rest on the tray. Mechanism state must be compatible with the opening and planned body path.

**Compilation:** visible props receive placement and action text; offscreen custody remains in continuity data and is mentioned only when useful. Do not summon an invisible holder through a dangling prop clause.

**Review:** Still—correct holder, hand and support? Take—grip/contact stable, transfer legible, contents and mechanism state preserved?

### 5. Shot–shot relationships

**Schema**

```text
edit_relation:
  previous_shot,
  kind: continuous | reverse | reaction | insert | ellipsis,
  shared_state_refs[], match_action, reaction_to,
  permitted_differences[]
```

**Invariants:** continuous action preserves shared state; reverse shots preserve world positions while changing projection; reactions reference an available stimulus; ellipses declare skipped changes. Trimmed cut points require observed state evidence.

**Compilation:** each generation receives its correct opening state. “Continues from the previous shot” alone is insufficient conditioning.

**Review:** Stills—does the board establish the exchange? Takes/cut—do gaze, gesture, object custody and reaction timing join at the actual edit?

### 6. Scene–scene causality and time

**Schema:** `scene.preconditions/effects`, `story_time`, elapsed-time estimate, location transition, travel requirement and knowledge/prop carryover.

**Invariants:** causes precede consequences unless explicitly reordered; travel and elapsed time are plausible; scene renumbering cannot erase continuous physical state.

**Compilation:** only shot-relevant time/weather/state reaches prompts; exposition is assigned a visual, dialogue or editorial carrier.

**Review:** Board—does the sequence explain why the next scene happens? Cut—can viewers infer elapsed time, destination and changed circumstances?

### SC02_g1 specifically

My preferred proposal is **OTS from a shifted A setup**, preserving the established axis: THEO’s shoulder anchors the foreground; MARA speaks through the window beyond him. Keep the jar only if the crop actually includes it.

A clean single is also legitimate: establish THEO offscreen beside the lens, use a sufficiently tight crop, and retain his mark and jar custody in scene state. Do not show an empty area that the established geography assigns to him.

## D. Script processing for this generator

**Separate screenplay scenes, dramatic beats, editorial shots and generation clips.** SC01–SC05 can remain screenplay IDs while sharing one continuous encounter and persistent stage state.

1. **Parse without silently rewriting.** Preserve script revision, scene and dialogue-line provenance.
2. **Extract local beats:** actor wants X, uses tactic Y, receives response Z, changing a fact, relationship or physical state.
3. **Mark mandatory audience evidence.** “She makes an exception” needs readable evidence; a suitcase alone does not prove retirement.
4. **Block before selecting coverage.** Establish actor marks, barrier, gaze, props and listener position.
5. **Choose shots by dramatic function and generability.** Do not impose two shots or two eight-second clips per scene.
6. **Allocate speech time plus pauses and handles.** Fit within the supplied 3–15-second limit. Rewrite or split long speech; do not compress emotional performance to satisfy a fixed template.
7. **Generate one stable setup with one principal action.** Speech and a small glance can coexist. Walking, exchanging a prop, operating a shutter and speaking is a different risk class.

For a two-person exchange:

- Start with a readable two-shot or OTS when geography is new.
- Usually use one speaker-focused shot per turn; combine brief lines only when one simple setup supports them.
- A short exchange may need two complementary OTS shots, plus an establishing shot if geography is unknown.
- Use clean singles for emphasis after geography is established, with explicit offscreen listener placement and compatible reverse coverage.
- Add reactions when information changes a listener, not automatically after every line.
- Use inserts for essential evidence; add explicit insert coverage rather than disguising a prop shot as a character single.
- Offscreen sound can bridge difficult action, but preserve before/after causality.

Rate **required interactions**, not only verbs: participant count, contact, mechanism precision, small-object manipulation, body travel, pinned geometry, text, identity scale change and endpoint difference.

GREEN should mean a supported action family with adequate conditions. **“No regex matched” should mean unflagged/unknown, not proven easy.** Restage RED before allocating extra drafts; pouring without faces is still pouring.

## E. Repo gaps ranked by film-quality impact

1. **Missing recipient and listener anchoring.** [`ShotDecl`](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/sections.py>) has `visible`, `subject`, `foreground`, but no utterance recipient or offscreen placement contract. This directly enables the reported defect.

2. **Prompt compilation loses relationships.** [`_Plan.cut()` / `still_prompt()`](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/plan.py:98>) remove hidden actor positions, retain prop strings, filter some hidden-holder props from stills, and append “Only … in frame.” Both prompts need the same staged source.

3. **Spatial checks validate declarations, not encounters.** [`AxisBook`](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/drama/axis.py:68>) derives compliant screen-side records. [`layout_issues()`](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/set_layout.py:156>) checks object visibility/readout references, without actor projection or listener occupancy.

4. **Conflicting framing sources.** `plan.unit_for()` derives size from `coverage._SIZE`; still templates and `camera.size` add other descriptions. SC02_g1 consequently combines “medium close-up” with “close-up.” Coverage purpose and shot size must be independent.

5. **Generability is heuristic and late.** [`rate_shot()`](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/drama/generability.py:87>) mainly scans phase prose, skips HOLD, and relies on declared tracking. A nonempty waiver demotes RED without establishing approval or successful restaging.

6. **QC cannot establish relationship correctness.** `autoqc.run_autoqc()` covers identity, scale and set similarity. `stills.pair_check()` measures image differences, not action feasibility. Extend existing dailies with relationship-specific questions; VLM findings remain advisory.

7. **Continuity and repair scope are too narrow.** `edit.cut_continuity()` identifies trimmed handoffs as uncertain; `retake_plan()` counts causes chiefly within the current version. Persistent defects should survive version bumps and screenplay scene boundaries.

8. **References are not wired through the inspected plan route.** `_Plan.build()` supplies empty reference sets and `TEXT_ONLY`. Provider/UI compatibility must be established before promising reference-based identity control.

## F. Film04 defects → missed stage → concrete check

| Defect | Earliest responsible stage | Concrete check |
|---|---|---|
| MARA talks to nobody | Blocking/coverage | Addressee resolves to a staged listener; crop/foreground agrees with expected presence |
| Repeated partial-shutter drift | Generability | Partial articulated mechanism + required precision → RED; restage before stills |
| Body lowering moves pinned shutter | Blocking/generability | Body path conflicts with fixed opening/prop → restage |
| Distant first/last frames | Still-pair review | Same setup, compatible poses and feasible path; pixel similarity cannot pass feasibility |
| Multiple actions per clip | Beat decomposition | Count principal state-changing actions and coupled contacts |
| Ten UI failures in eighteen sends | Submission | Verify exact attachments and slots; reconcile ambiguous effects before resending |
| Serial review delays | Scheduling | Review bounded candidate groups for independent shots; preserve dependent handoff gates |
| QC added after rejection | Shot planning/dailies | Declare required invariants and measurement coverage before submission |
| Jacket drift; no references | Design/conditioning | Approved identity evidence, supported attachment route, full-clip identity review |
| Full regeneration for one defect | Repair | Classify first; assess localized edit only if supported; inspect collateral changes |

I disagree with automatically hiding all VLM-failed drafts from the Owner. Rank and flag them; a fallible judge must not become an invisible acceptance authority.

## G. Proposed priority plan

| Priority | Step | Done criterion |
|---|---|---|
| 0 | Claude reconciles accepted authority, current evidence and locks | Approved scope identified; `OWNER_GO_LIVE: NO` retained; no implementation inferred from this brainstorm |
| 1 | Freeze one SC01_g2 → SC02_g1 → SC02_g2 interaction design | Board clearly locates both people, recipient, jar and barrier; Owner chooses OTS or justified clean-single treatment |
| 2 | Extend existing schemas and shared compilation | Original unanchored pattern fails focused checks; legal OTS and offscreen-single cases pass; still/video prompts agree |
| 3 | Audit all five affected singles and remaining film04 beats | Every interpersonal shot has an anchor; framing has one authoritative size; RED residuals are explicit |
| 4 | Reconcile restages and build an animatic | Owner approves changed meaning, stills and coverage; no unexplained jump from pour to counted stacks |
| 5 | Strengthen existing review/repair/submission paths | Relationship questions, persistent defect counts, exact attachment identity and ambiguous-send reconciliation demonstrated offline |
| 6 | Propose one bounded live validation | Separate Owner authorization; Omni Flash/360p settings and budget explicit; Owner reviews the take and adjacent cut |
| 7 | Complete production and delivery | All required takes Owner-accepted; actual cut, sound, master and delivery independently checked; final Owner acceptance |

The inspected index now records **10 takes, 85 logged credits, two ACCEPTED and one GENERATED**; the completion-plan figures are older. Take ID `SC02_g1_t3` maps to `SC02_g1_t4.mp4`. Reconcile these before budgeting or selecting footage.

Skipped: live generation, provider/UI verification, test execution and audiovisual playback; no files changed.  
Risk: these checks prevent contradictory plans; generated relationship fidelity still requires moving-image review and Owner acceptance.

