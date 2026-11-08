# Claude round 1 — full production process for AI drama (independent draft)

## 0. Root finding from the SC02_g1 defect (data, not prompt)
- `03_preprod.json` already has a floor plan: `locations.*.layout` with zones, objects at [x,y], cameras A/B/C at [x,y] with `look_at` and `sees`.
- But character positions are free text in `states.*.positions` ("at the window, frame-left"). "frame-left" is camera-relative, written once per state and reused for every camera.
- So nothing can compute: camera A at [0.62,0.86] looks at the window [0.62,0.42]; THEO "at the window" stands at ~[0.62,0.50], i.e. ON the line of sight, 0.36 from camera. A MEDIUM_CLOSE single of MARA from A must either show THEO (foreground / OTS) or move the camera. The pipeline instead wrote "Only MARA in frame".
- Principle: every relation that must be guaranteed on screen must exist as data in world coordinates, and each shot's framing must be derived from that data (not re-described by hand per shot).

## 1. Stage map (inputs -> outputs -> checks -> approver)
| # | Stage | Output (artifact / fields) | Machine check | Approver |
|---|---|---|---|---|
| S0 | Brief | film.json: runtime, format, language, audience, budget cap, generator profile | budget/runtime sanity | Owner |
| S1 | Script | script.fountain + 01_story: logline, structure, beats, scenes, dialogue ids | Gate 1: beat functions, every line has a speaker & addressee | Owner (story) |
| S2 | Relationship & knowledge bible (NEW) | per character pair: relation, power, want, what each knows when; per scene: who addresses whom, who listens/reacts | each dialogue line has `to:`; knowledge never used before it is revealed | Tech Lead |
| S3 | Direction | 02_direction: vision, visual rules, reveals, coverage plan per beat, comprehension facts | every fact has evidence shot; every exchange has a coverage pattern | Owner (tone) |
| S4 | World & geography | locations.layout: zones, objects, barriers, cameras, entrances; characters' marks in world coordinates (NEW) | marks inside zones; barriers respected; camera sees the marks it claims | Tech Lead |
| S5 | Blocking (NEW as typed step) | per scene: character marks over time (mark ids), moves (from->to, path), props held | moves are legal paths; no teleport across cuts; body travel vs pinned props flagged | Tech Lead |
| S6 | Coverage & shot design | 04_shots: camera id, size, coverage, subject, listener anchor, visible/foreground DERIVED from geometry, eyeline target | frustum check, 180 line, listener anchoring, generability | Tech Lead |
| S7 | Generability & restage | rating per generation (GREEN/AMBER/RED), drafts N, restage notes | RED blocks unless waived | Owner for story changes |
| S8 | Look development | character refs (3 per char), costume, props, location plates | refs exist and approved before any still | Owner |
| S9 | Stills & storyboard | start/end frames per generation, storyboard panels | pair delta, pinned props, listener present/anchored, VLM still review | Owner |
| S10 | Prompt compile | video prompt, still prompt from data | no pronoun without antecedent; no reference to a person not placed; word limits | machine |
| S11 | Generate | N drafts at 360p (GREEN 1, AMBER 2, RED 3) | send reliability, intent receipt, go-live lock | Owner lock |
| S12 | Dailies / QC | autoqc, motion, audio, VLM judge, relation questions | 16 QC groups + relation group | Owner accepts |
| S13 | Retake / clip edit | version N+1 or conversational edit | defect -> stage mapping recorded | Tech Lead |
| S14 | Edit | 05_edit: cut list, J/L cuts, reaction timing | cut continuity: state, axis, eyeline, listener continuity | Owner |
| S15 | Sound | dialogue cleanup, room tone, sfx, music | voice bible match across takes | Owner |
| S16 | Grade & delivery | grade, subtitles, master, rights ledger | lock check, deliverable spec | Owner |

## 2. Category catalogue (what each film must record)
1. Story: concept, premise, conflict, logline, structure, beats, scene purpose, turn per scene, stakes, ending.
2. Characters: look, costume, voice bible + reference take, behaviour bible (how they move/speak), arc per scene.
3. Relations (NEW typed): pair relation (stranger/colleague/family), status/power per scene, attitude (hostile -> warm), knowledge state, who drives the scene.
4. Dialogue: line id, speaker, addressee, listener reaction, subtext, language, duration estimate, overlap.
5. World: locations, layout, barriers, light sources, weather, time of day, sound bed.
6. Blocking: marks, moves, entrances/exits, props in hand, posture (stand/sit/lean).
7. Camera: positions, size, angle, height, lens intent, movement, coverage pattern, eyeline target, foreground.
8. Continuity: state per generation boundary (positions, props, looks, light), screen direction, 180 line, time.
9. Generability: action type, risk class, drafts, restage, fallbacks.
10. Assets: references, plates, stills, storyboard, rights.
11. Production: budget, credits, schedule, send log, retakes.
12. QC: technical, performance, relation, continuity, audio, look.
13. Post: edit, sound, music, grade, subtitles, delivery.

## 3. Relationship model (the core of the Owner's question)
### 3.1 Types
- R1 Address: line L is spoken by A TO B (or to self / to a group). Every line must have `to`.
- R2 Reaction: B's reaction to L (beat, emotion) and whether it must be seen (reaction shot) or heard only.
- R3 Spatial: each character stands on a mark (world [x,y], posture, facing). Distance A-B, barrier between (counter/glass).
- R4 Camera-to-world: camera at [x,y] looking at target; derived for each character: in frame / foreground / occluder / behind camera / off-frame left/right.
- R5 Eyeline: A looks at B => on screen A's gaze goes toward B's projected position (screen side, and how far off lens). Never into lens unless declared.
- R6 Listener anchor: in a shot where A speaks to B, B must be (a) visible, (b) foreground OTS, or (c) off-frame on the side of A's eyeline, with the frame NOT showing the place where B stands empty.
- R7 Possession: prop P held by C / at place X; the prop goes with C.
- R8 Hand-off: end state of generation n == start state of n+1 in world terms (positions, posture, props, looks).
- R9 Power/attitude: per beat; maps to camera height/angle and size choices (e.g. clerk seated = lower than standing customer?) and performance notes.
- R10 Knowledge: what each character and the audience knows; reveals happen on screen with evidence.

### 3.2 Data (proposal)
- `locations.*.layout.marks`: id, at [x,y], zone, posture options. Characters' positions per state become `{"THEO": {"mark": "hall_window", "posture": "bent", "facing": "window"}}` instead of free text "frame-left".
- `dialogue[]`: add `to`, `reaction_of_listener`.
- `generations[]`: `addressee` (derived from lines), `listener_anchor`: VISIBLE | OTS_FOREGROUND | OFF_FRAME_LEFT | OFF_FRAME_RIGHT; `visible`/`foreground` derived by a projection function (camera at, look_at, size -> horizontal FOV -> which marks fall in frame and in what order of depth).

### 3.3 Invariants (validator)
- V1 every dialogue line has `to`; addressee present in the scene's occupancy at that time.
- V2 projection: if a character's mark falls inside the frame cone of the shot's camera and closer than the subject, the character MUST be foreground (OTS) or the shot is BLOCK (CAMERA_INSIDE_PARTNER / PARTNER_HIDDEN).
- V3 listener anchor declared and consistent: OFF_FRAME_x needs the addressee's projected position outside the frame on side x; the speaker's eyeline side == x; size CLOSE or tighter recommended (AMBER otherwise).
- V4 reverse pairs: speaker A shot and listener B shot of the same exchange use cameras on the same side of the axis, eyelines opposite.
- V5 hand-off in world terms (mark, posture, props) between consecutive generations; posture changes across a cut must be declared (the SC01/SC02 stand->sit jump).
- V6 prompt hygiene: no pronoun (him/her/them) or possessive of a person who is not placed in the prompt; no "Only X in frame" while another character is in the scene, unless the projection says they are off-frame or behind camera.
- V7 prop possession: pinned props tied to a character only if that character is placed in the frame or explicitly off-frame.

### 3.4 Prompt text
- OTS: "Over THEO's shoulder: the back of his head and his wet olive jacket shoulder fill the near left of the frame, out of focus; the jar in his hands on the counter."
- Off-frame: "She speaks to the young man standing just off frame-left beside the camera; her eyes go just past the lens to the left."
- Stills get the same placement sentence; the review asks "where is the listener?".

### 3.5 Review questions (stills + takes)
- Who is X talking to? Can you see that person or their shoulder, or does X look just past the lens toward them?
- Does the frame show the place where the listener stands? If so, are they there?
- Does X look into the lens? (FAIL)
- After the cut, is everyone where the previous shot left them?

## 4. Script processing for this generator
1. Script -> scenes -> beats (one turn per beat). Each beat: who wants what from whom.
2. Beat -> exchange units: line + addressee + reaction.
3. Exchange -> coverage pattern chosen from a small library that the generator can make reliably:
   - P1 OTS pair (default for dialogue between two people at a barrier): A over B's shoulder, B over A's shoulder. Relationship always visible.
   - P2 Two-shot side-on (camera C) for physical exchange (handing over objects) — but hands/small objects RED: prefer result over process.
   - P3 Clean close single only with off-frame anchor and CLOSE size; for emotion peaks.
   - P4 Insert (object) as its own short generation; RED objects get best-of-3 or static aftermath.
   - P5 Master to establish geography at the scene start (or the first shot after a location change).
4. One generation = one simple action + optional line; 3-8 s sized to the action; start and end frame near each other.
5. Generability rating before stills; RED -> restage (move the action off-screen, use sound, show result).
6. Every scene starts with a geography-establishing shot or inherits it from the previous scene in the same place.

## 5. Gaps in this repo (ranked)
1. Character positions are free text, not on the floor plan (no projection) — root cause of SC02_g1 t3.
2. Dialogue lines lack `to` (addressee) and listener reaction; no listener anchor in shots.
3. `plan.py` still prompt writes "Only X in frame"; video prompt uses pronouns without antecedents.
4. Still/take review questions lack relation questions; no VLM judge yet (P15-04).
5. Coverage chosen per shot by hand, not from patterns tied to exchanges.
6. Hand-off checks text equality, not world state (posture change SC01->SC02 unflagged).
7. Character reference images unused.
8. One take per send loop; no best-of-N.

## 6. Plan sketch
- Q1 (offline): world-coordinate marks + projection + V1-V7 checks; prompt/still text from placement; review questions. Re-rate film04: expect BLOCK on SC02_g1/g2, SC03_g2, SC04_g1, SC05_g1.
- Q2 (offline): coverage-pattern library + exchange table in 02_direction; regenerate film04 shot list from it (with the P15-07 restage).
- Q3 (Owner): new stills for the affected shots, Owner approves.
- Q4 (live, Owner lock): best-of-N at 360p, VLM pre-screen, Owner accepts.
- Q5: edit/sound/delivery for film04.
