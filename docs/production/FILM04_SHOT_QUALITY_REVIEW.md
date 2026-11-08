# film04: why a shot took so long, and how to make one that passes

Written 2026-11-08 after SC02_g1 take t2. Sources: `films/film04_last_ticket/takes/` (index, intents, reviews),
git history 9e3a182..310a96a, Google's Omni 1.2 Flash docs (aistudio.google.com/docs/omni), the Omni 1.1 launch post,
and two third-party guides (marked [3p], unverified).

## 1. Where the time went (2026-11-07 18:00 -> 2026-11-08 07:55, ~14 h)

| Measure | Value |
|---|---|
| Generations accepted | 2 of 12 (SC01_g1 4 s, SC01_g2 8 s) |
| Send attempts | 18; 8 produced a video, 10 failed in the UI before generating (START_NOT_FOUND 6, UNBOUND 2, AMBIGUOUS 2) |
| Takes | 9 (2 accepted, 6 rejected, 1 pending); 80 credits |
| Rejections caused by the shutter | 5 of 6 (SC01_g1 t2-t4, SC01_g2 t1, SC02_g1 t1); the pending SC02_g1 t2 has the same defect |
| Shot plan versions | SC01_g1 v5, SC01_g2 v2, SC02_g1 v2 |
| Commits | 33; about two thirds are pipeline features or fixes, one third film data |

SC01_g1 (a 4 s shot) alone took ~7.5 h: 5 takes, 5 plan versions, and the end-frame route, duration control and
trajectory QC were built between its takes.

## 2. Root causes, in order of cost

1. **The script hangs its key action on the one thing the model cannot hold: a mechanical prop with a partial state.**
   A rolling shutter "lowered to a face-high gap" is pinned through SC01-SC05. The model moves it when a hand is near
   (SC01_g1, SC02_g1 t1), when no hand is near (SC01_g2 t1, SC02_g1 t2), overshoots a target height (SC01_g1 t4) and
   reverses (t3). Google's model card lists "complex motion" and full consistency as open challenges; published 2026
   benchmarks (MemoBench, WROP) find that models do not restore object state changes. No stage asked "can the model do
   this beat?" before stills were drawn.
2. **The first and last frames were far apart.** SC02_g1 v2 went from standing to seated with the face inside a fixed
   gap. Guidance for Flow frames [3p, Veo]: large differences "force an invented transition, which is where objects
   distort". The model resolved the gap by moving the shutter, not the body.
3. **One take at a time, each waiting for review.** Google's Omni launch post recommends 3-4 drafts at 360p and
   changing one variable at a time. We sent one take, reviewed it, changed the plan or code, and sent again: each
   loop cost 30-90 min of which generation was ~2 min.
4. **The fix was always a full regeneration.** Omni 1.2 supports conversational edits of a generated clip
   ("keep simple ... keep everything else the same"). SC02_g1 t2 had good dialogue and only a wrong shutter, but
   there is no edit route in our pipeline. Whether Flow's UI exposes the edit for Omni is not yet verified.
5. **Send automation failed more often than it worked (10/18).** Each failure cost no credits but cost a debug
   session: token tails change per page load, re-uploaded stills tie in the pixel search, binding by tile title.
6. **QC came after the failure.** Autoqc reported 0 warnings on every rejected take; motion QC on the tracked
   prop was added after four rejections; no VLM judge compares a take with its end still or the costume bible.
7. **Character look drift (SC01_g2 t1: THEO's jacket).** Omni accepts up to 3 reference images per character for 2
   characters; we send only the start frame. Combining a start frame and references in Flow is unverified (memory:
   in WP5 the start frame beat ingredients).

## 3. Stage-by-stage audit

| Stage | What it should catch | film04 result | Change |
|---|---|---|---|
| Story / direction (G1, G2) | Beats the model cannot do | Shutter state, coin pour, coin counting, glasses on a chain all passed | Add a **generability rating** per beat (section 4); RED beats must be restaged before G2 passes |
| Pre-production | Props that must hold a state | Shutter pinned "unchanged" in 10 states, never rated | A pinned articulated prop either leaves the frame, sits still in the far background, or changes only between shots |
| Shots | One main action, length = action | Fixed by P13-06 (duration, motion library) | Keep; add "body travel against a pinned prop" as RED |
| Stills (start/end) | Start and end close enough to interpolate | Stand -> sit with a fixed gap | **Frame-delta check**: same camera and light, pose change small, no pinned prop near a moving body |
| Prompt | Motion only, one continuous shot | Fixed by P13-04 | Keep |
| Send | Deterministic attach | 10/18 failed | Upload the still in the same send so it is the newest picker item; keep the pixel match as a check, not the search |
| Generate | Choice among drafts | 1 take per send | **Best-of-3 at 360p** for AMBER/RED beats, 1 for GREEN |
| QC | Reject before the Owner sees it | Autoqc blind to action; motion QC late | Motion QC on every tracked prop (now exists) + VLM judge against end still and look bible; Owner sees only takes that pass |
| Repair | Smallest change | Full regeneration, prompt rewording | Edit the clip when one element is wrong (after probing Flow); after 2 failures of one kind, restage, never reword |

## 4. Generability rating (Omni 1.2 Flash, from our takes and the docs)

- **GREEN** (expect 1-2 takes): faces, looks, glances, dialogue to camera or across, small head and hand gestures,
  sitting still, a slow camera push or locked camera, light changes, a train or weather in the background.
- **AMBER** (best-of-3): walking in or out, sitting down or standing up with nothing pinned nearby, placing a large
  object on a surface, a two-person dialogue with one speaker, a door that only opens.
- **RED** (restage first): a mechanism stopping at a partial position (shutter, window, drawer), any prop that
  must not move while a body moves near it, hands manipulating small objects (coins, glasses, stamps), pouring or
  granular matter, counting, text that must read, two people touching the same prop, a body entering a fixed gap.

Restage tools for RED beats: cut around it (show the before and after in two GREEN shots); an insert where only the
prop moves, framed like a product shot, with no hand contact; move it off screen and carry it with sound; or frame
the prop out of the shot.

## 5. Recipe for one shot that passes

1. Rate the beat. RED -> restage before any still is drawn.
2. One main action, duration = action time + a short hold (P13-06).
3. Start still approved; end still only when the frame delta is small; a pinned prop is far from any moving body or
   out of frame.
4. Prompt: motion only, "a single unbroken shot", timecodes, sound design (P13-04).
5. Send N drafts at 360p Omni 1.2 Flash (N = 1 GREEN, 3 AMBER/RED).
6. Automatic QC on every draft: autoqc, motion QC on tracked props, VLM judge vs end still and look bible. Discard failures.
7. The Owner reviews the best passing draft, side by side with the end still.
8. Wrong in one element -> edit; same failure twice -> restage at the stage that should have caught it.
9. Upscale to 720p/1080p only after acceptance.

## 6. Remaining film04 generations

| gid | Rating | Why |
|---|---|---|
| SC02_g1 (v3 proposed) | GREEN once seated at the start | v2 had a body entering a fixed gap |
| SC02_g2, SC03_g2 | GREEN | Looks and dialogue; shutter edge must stay out of frame or far from motion |
| SC03_g1 | AMBER | Sets the jar on the counter, two people |
| SC04_g1 | RED | Takes off glasses on a chain |
| SC04_g2 | RED x2 | Pushes the shutter up; coins pour into the tray; two people |
| SC05_g1 | RED | Sorts and counts coins with fingers |
| SC05_g2 | RED | Stamps a ticket |
| SC06_g1 | AMBER | Walks out behind THEO; moving headlights |
| SC06_g2 | AMBER | Train doors slide open (background) |

At the current rate (2.5-5 takes per shot) the remaining nine would cost ~25-35 takes. Restaging the five RED beats
first should bring most shots to 1-3 takes.

## 7. Proposed backlog items

1. P15-01 Generability rating per beat at G2 (RED blocks), with the section 4 lists as data and tests from film04 takes.
2. P15-02 Frame-delta check on start/end stills (pose distance, pinned prop near a moving body).
3. P15-03 Best-of-N send at 360p and a draft table for the Owner.
4. P15-04 VLM judge (end-still match, look bible) as a pre-filter; never an acceptance.
5. P15-05 Probe Flow: Omni clip edit and start frame + character references together (0-credit image checks first).
6. P15-06 Send: upload the still in the same send; picker match as a check.
7. P15-07 film04 restage of the RED beats (needs Owner approval of the story changes).
