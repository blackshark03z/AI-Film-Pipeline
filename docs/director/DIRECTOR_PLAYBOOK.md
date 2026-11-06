# Director playbook — how the model authors a film package

Written 2026-11-06 (loop item P1-03). Audience: the model acting as director/producer. It says **what to decide, in
which file, in which order, and what blocks you**. It is guidance, not canonical status; the machine rules live in
`src/film_pipeline/production/` and `src/film_pipeline/drama/`, product truth in `docs/sot/film/`.

Scope of this version: the **drama** profile through pre-production and prompt planning (`01_story` … `04_shots`,
`tools/film.py plan`). Editing, post and delivery stages (`05`–`07`) have no typed model yet; sections 8–9 say what to
do by hand until their phases land. Category numbers (`#n`) refer to
[CATEGORY_COVERAGE_168.md](../production/CATEGORY_COVERAGE_168.md) (the Owner's 168 categories; this playbook covers #1–56).

## 0. The rule that governs everything

A defect found in a film is fixed in the **stage that should have caught it**, not only in that film
([FILM01_LESSONS.md](../drama/FILM01_LESSONS.md)). Before patching a prompt, ask which gate was supposed to block this and why it did not; then
fix the check (model, validator, test) and the film. Technical PASS ≠ product proof ≠ Owner acceptance: a green gate
means the declared rules hold, never that the film is good.

Standing Owner constraints: Generate stays paused (`OWNER_GO_LIVE: NO`), no purchases, publishing, cookies,
captchas or closing GPM-Flow; video research only on Omni Flash 360p; uploading local files to Flow opens a rights
dialog that needs the Owner.

## 1. Order of work

```
film.json + script.fountain
  → 01_story.json     Gate 1  (story_audio_lock)
  → 02_direction.json Gate 2  (directorial_coverage)
  → 03_preprod.json   Gate 3  (visual_spatial)     } written together, checked by `plan`
  → 04_shots.json                                   }
  → tools/film.py plan   prompts, still prompts, storyboard, gate3.json
  → [Owner-approved Generate]  stills (free) → video takes, one generation at a time
  → 05_edit … 07_delivery (by hand until typed)
```

Commands (from the repo root):

```bash
python tools/film.py new <film_id> --profile drama
python tools/film.py validate --film films/<film_id>      # gates 1–6 + package issues, exit 1 if anything blocks
python tools/film.py status   --film films/<film_id>
python tools/film.py continuity --film films/<film_id>    # action/spatial/object/temporal/visual/emotional; BLOCKs also fail `plan`
python tools/film.py camera     --film films/<film_id>    # camera & lighting plan (scenes[].lighting, generations[].camera)
python tools/film.py animatic   --film films/<film_id> [--stills <dir>] [--audio <dir>]   # media/animatic.mp4 + srt + timing report, 0 credits
python tools/film.py planning   --film films/<film_id>    # budget, schedule, risk register, rights ledger (validate shows a summary)
python tools/film.py qc         --record <take_qc.json>   # validate a take QC record (16 groups 131–146) → ACCEPTED / REJECTED / INCOMPLETE
python tools/film.py takes      --film films/<film_id> --register <gid> --clip <mp4> --prompt <sent prompt.txt> --model <m> --credits <n> [--start-frame <png>]
python tools/film.py review     --film films/<film_id> [--clips <dir>]    # dailies sheet per new take; autoqc WARNs when models exist
python tools/film.py review     --film films/<film_id> --ingest <filled.json>   # sets the take ACCEPTED / REJECTED / INCOMPLETE
python tools/film.py generate   --film films/<film_id> --gid <gid> --dry-run [--stills <dir>] [--start-token tok:<tail>]   # exact send payload + intent receipt, sends nothing
python tools/film.py retake     --film films/<film_id>    # per-generation decision after rejections; exit 1 while pickups are open
python tools/film.py retake     --film films/<film_id> --pickup <gid> --reason "<why>" --edits <changes.json>   # shot version N+1
python tools/film.py plan     --film films/<film_id> --out <dir> --takes <takes_dir> --approve-storyboard "<reviewer>"
```

QC record rule of thumb (`production/qc_model.py`): every check names its evidence, review level (STILL < SAMPLED <
FULL_MOTION < CUT) and reviewer. An `auto:` tool can only WARN on content groups (story, action, motion, look...) — it
cannot pass them; a human PASS needs the group's minimum level (motion/action: the whole clip). Any P0 FAIL rejects the
take for good; a P1 FAIL rejects until a human waives it with a written reason; an untouched group keeps the take
INCOMPLETE, never accepted.

Generate rule of thumb (`production/generate.py`): a payload is built from the package as it is now (it re-plans, using
the storyboard approval recorded in `media/plan` by `film.py plan --approve-storyboard`). It lists blockers: package
problems for this shot, a chained shot whose previous shot has no ACCEPTED take, a missing start still, and for a real
send also no start token, no `budget.credits_estimate`, or credits past the cap. A real send (no `--dry-run`) is refused
unless the backlog header says `OWNER_GO_LIVE: YES` and nothing blocks; the receipt in `takes/intents/` is written first.

Retake rule of thumb (`production/retake.py`): when you reject a take, name the cause in the review (`cause`: PROMPT,
START_FRAME, PROVIDER_LIMIT, STAGING). The first failure gets the cheap fix for that cause; the same cause twice means
change the shot (split it, re-stage it, cover with an insert/reaction, new start frame), not another identical render;
three rejections in one version go to the Owner. A pickup replaces the shot in place as version N+1 (old version kept in
`history`), so a later review of a new take counts from zero.

Continuity rule of thumb: any prop, position or look that differs between a generation's start and end state needs an
ACTION/CONSEQUENCE phase that names it ("she drops the letter in the bin"); a chained generation must start exactly
where the previous one ended (a scene cut only warns).

Camera & lighting: declare `lighting` on every scene and `camera` on every shot, or on none. Only the shot size reaches
the prompt (derived from the coverage type); angle, movement, lens and light are planning data the Flow route cannot
obey. Three identical sizes in one scene BLOCK unless each repeat carries `declared_repeat`.

Animatic: review `media/animatic_report.json` before Generate - `DIALOGUE_TOO_FAST` means the line cannot be spoken in
its 8 s window (more than 3.5 words/s); fix the script or split the generation. Approved stills replace schematic frames.

Planning: a shot with person-to-person contact or a prop passing between characters is a HIGH risk and needs a
`risk_fallbacks[<generation_id>]` plan (usually an insert or cutaway that avoids staging the touch). Rights entries live in
`03_preprod.rights`; anything not `original`/`cleared` is an Owner decision, never a pass.

Never mark a gate PASS by hand. A stage that exists but has no validator reports `NOT_RUN`, which is not a pass.

## 2. Stage 1 — story (`01_story.json`, Gate 1, #1–14)

Decide, in this order, and write each down:

| # | Decision | Field | Checklist |
|---|---|---|---|
| 1 Concept, 3 Premise | what the film is about in one breath; the situation that starts it | `concept`, `premise`, `central_conflict` | Is the conflict between two *wants*, not a mood? |
| 2 Audience | who watches and what they expect | `audience.who`, `.expectation` | Would they follow it with no background? (film02 failure: see §7) |
| 4 Logline | one sentence | `logline.{text,protagonist,goal,obstacle}` | Names the protagonist, the goal and the obstacle in words the text contains (the gate checks this) |
| 5–6 Structure, plot, subplot | acts → beats → scenes | `structure[].beats[]`, `plot`, `subplots` | Functions in order SETUP < INCITING < ESCALATION < MIDPOINT < CRISIS < CLIMAX < RESOLUTION; SETUP, INCITING, CLIMAX, RESOLUTION all present |
| 7 Character arcs | want / need / flaw / change | `characters` | Protagonist has `arc_change` and a `change_scene_id` that exists |
| 8–9 Beats, scene design | each scene's purpose, conflict, outcome, value shift | `scenes` | A scene with no conflict or outcome is a transition, not a scene — cut or merge it |
| 10–12 Screenplay, dialogue, rewrite | the Fountain script, rewrite log | `script.fountain`, `rewrite_log` | Every story scene is a script scene and vice versa; log each rewrite with its reason |
| 14 Adaptation | source and rights | `adaptation` / `source_note` | Any source material → `adaptation.rights_status`; anything but `cleared` makes Gate 1 `OWNER_PENDING` |

Script writing constraints that come from the generator, not taste: **one scene = 16 s = two 8 s generations, one
shot each**; at most 2 speakers and 3 people in frame; dialogue ≤ 28 syllables per generation at 2.5 syll/s; at least
3 s of silence/reaction in a scene (film03 limits in `03_preprod.json`). Write beats as **observable actions**
(§6), not feelings.

## 3. Stage 2 — direction (`02_direction.json`, Gate 2, #15–34)

| # | Decision | Field | Checklist |
|---|---|---|---|
| 15–16 Vision, visual language | tone, references **as words**, rules with their *why* | `vision`, `visual_rules` | A rule without a reason is a preference; the gate wants both |
| 33 POV | whose view each scene favours; what audience vs characters know | `scenes.<id>.pov` | Every fact id it names exists in `comprehension.facts` |
| 34 Emphasis | the moment and the device (insert / push / hold / reaction) | `scenes.<id>.emphasis`, `reveals` | **Every reveal has an emphasis device** on a shot of that scene |
| 28 Emotional direction | intensity 0–5 per character, start and end of each scene | `scenes.<id>.curve` | A jump > 2 between consecutive scenes needs `jump_cause_beat` |
| 29 Rhythm, pacing | target average shot length, hold points | `scenes.<id>.pacing` | Holds sit on shots of that scene; in the 8 s route a "hold" is a reaction left on screen |
| 31 Transitions | in/out kind and reason | `transition_in/out` | Card + cut, cut, dissolve, match, J/L: say why |
| 30 Coverage strategy | required shot types per beat | `coverage_plan` | Every beat has carrier shots in `04_shots` and every planned type really appears |
| 27, 32 Performance, visual storytelling | what the audience *sees* that carries the meaning | `choreography` in `04_shots` (§5) | See §6 |

Comprehension (also in `02_direction.json`) is directing, not post: every on-screen character needs a
`CharacterIntro`; every story fact needs a **carrier** (dialogue, picture, identity tag or context card) no later
than the first generation that needs it. Plan it with the script — dialogue first (free), picture second, tags/cards
(white on black, ≤ 2 lines, 2–3 s) as the fallback.

## 4. Stage 3 — pre-production (`03_preprod.json`, Gate 3, #35–56)

| # | Decision | Where | Rule |
|---|---|---|---|
| 35–36, 42–43 Casting, design, costume, hair | `characters.<id>.look` (locked text, QC invariants, approval) + `video_text` | **One locked look per character per film.** Never re-describe appearance in a scene prompt; fix drift by changing the look for all scenes. The start frame carries the face, so `video_text` has no ethnicity words |
| 37–41 Location, set, dressing, props | `locations`, `scenes.<id>.occupancy`, `states` | Locked location text in every prompt; prop positions live in continuity states |
| 24, 22–23 Screen direction, blocking, staging | `scenes.<id>.axis`, `choreography` | One axis per scene (180° rule); who stands where is declared, extras never get positions |
| 26, 50 Temporal and continuity planning | `story_time`, `states` | Start/end state per generation; the end state of g(n) is the start state of g(n+1) |
| 46–49 Storyboard, previs, shot planning | `plan` writes `storyboard/` and `gate3.json` | Storyboard frames are `PENDING` until a reviewer is named with `--approve-storyboard`; an agent approving its own frames is the weakest evidence — say so in the report |
| 44–45 Cinematography, lighting | `locations.<id>.look` + `room_tone` | Only a lighting string exists; no camera plan model yet (matrix GAP) |
| 51 Sound | `sfx` per shot, room tone | Prompt-level strings only |
| 52 Technical planning | `film.json` (aspect 16:9, fps, resolution 1280x720, generation_s 8) | `plan` refuses other aspects |
| 53–56 Schedule, budget, risk, legal | — | Not modelled yet (P6-02, P7). Record by hand in the film README: credits estimate (12 per generation), moderation risks (§7), disclosure notes |

## 5. Stage 4 — shots (`04_shots.json`)

One declaration per 8 s generation: `generation_id` (`SC03_g1`), `scene_id`, `coverage`
(MASTER / TWO_SHOT / OTS / SINGLE / REACTION), `subject`, `foreground`, `visible`, `dialogue` (script **line
numbers**, `[]` for a silent shot; every scripted line must be assigned exactly once), `start_state`, `end_state`,
`previous_generation_id`, `choreography` (timed phases, visible performance cues, once-only must-show actions), `sfx`.
`previous_generation_id` marks a handoff; the next generation is only sent after the previous take's end state is
verified (§8).

## 6. Writing shots the generator can obey

1. **SRT / script → faithful action** (Owner rule, `docs/sot/film/05_PROMPT_COMPILER.md` in the root repo). Read the
   whole sentence across cues; extract actor, action, receiver, direction and stated consequence; convert to a few
   observable ordered beats: setup → initiating action → receiver's reaction → aftermath. Do not add a harder shove,
   a fall, an injury or a new endpoint the source does not have, and do not merge a later event into this one because
   it shares the room. Keep enough continuous coverage to *see* the initiating contact and the reaction.
2. **Control only what the model controls.** A beat whose outcome is uncontrolled (something falls, tears, spills)
   must not be relied on across the 8 s cut: rewrite it as a placed or held object, or verify the rendered end state
   first (`CROSS_CUT_DEPENDENCY`). film03's crumpled letter is thrown into a bin and *recovered by hand* — a held
   object, not a fall.
3. **Anyone named in the continuity sentence is described to the model**: give them their locked look or leave them
   out of the state (film01 defect 4).
4. **Framing is not honoured reliably** on single-shot 8 s generations; a planned close-up may come out as a medium.
   Plan so either reads correctly, and do not let a story point depend on exact framing.
5. **Words that cost credits.** Police + race themes together triggered refunded "reputational risk" blocks (film01,
   film03): no race words in video prose (the start frame carries the look) and drop "police" from the prose of the
   video prompt (`.soft.txt`), dialogue unchanged. Photoreal character refs are refused by some providers; the
   start-frame route avoids refs in the video prompt.
6. **Prompt budget.** `PreflightLimits.max_prompt_words` defaults to 120; the Flow start-frame route runs at **215**
   (film02: all six prompts 165–220 words, 6/6 first pass), set in `03_preprod.json`. The limit applies to the
   **emitted** text (start prefix + compiled text). A prompt over the limit is either shortened or listed in
   `accepted_overlong` with a reason — never silently allowed. (The earlier backlog figure of 170 words does not match
   either value; use the one in the film's `preflight` block.)

## 7. Lessons from shipped films (each is a check, not a story)

| Film | What went wrong | Where it is now caught |
|---|---|---|
| film01 | Hair drifted scene to scene | Locked `CharacterLook`; preflight `LOOK` blocks a missing/altered look |
| film01 | Torn pieces fell one way in g1, another in g2 | `ContinuityState` + `CROSS_CUT_DEPENDENCY` + handoff QC |
| film01 | Wrong officer in g2 | `LOOK` check covers every character the start state names |
| film01 | Subtitle over the wrong close-up | Cues clamp to the speaking shot (post) |
| film01 | Provider blocked refs + mistreatment storyline | Route evidence; text-only route is a supported mode |
| film02 | The aunt read as the mother — a viewer could not tell who anyone was | `drama.comprehension`: intros, fact carriers, identity tags, cards; `lint_script` before generation |
| film03 | Wrong start frames from the Flow picker (virtual list) | `flow_send --start-file` pixel-checks the slot before paying |
| film03 | 12 credits ×3 lost to moderation | Prompt wording in §6.5; record risk in the README |

## 8. Generation discipline (once the Owner lifts the pause)

1. Stills first — Flow image mode costs 0 credits; reject identity/set errors there, with an eye check and
   `tag_layout.check_still_identity`, before any 12-credit video.
2. Start-frame route ("Khung hình" slot) is the drama default; ingredients drift identity and set.
3. One generation at a time within a scene; send g(n+1) only after a reviewer has passed g(n)'s handoff QC
   (`<gid>.handoff_qc.json`, bound to the take's sha256). A take counts as new only if its hash differs from the
   previous tile; `SEND_FAILED` is a failure, never a download.
4. Budget: cap = estimate × 1.5 (`film.json`); stop and report instead of retrying blindly.

## 9. After generation (by hand until P5–P6)

Comprehension record (0 issues), cut, context cards, identity tags placed by `tag_layout.auto_place` and checked by
eye, subtitles inside the speaking shot, two-pass loudness (−14 to −16 LUFS, peak below −1 dBFS), AI label,
metadata and C2PA. The dev C2PA signer is **not** release-grade. Read [film03's README](../drama/film03/README.md) for a complete worked route.

## 10. Worked example — film03 "The Front Desk"

Package: `films/film03_front_desk/`.

- **Story.** Logline: *On her first morning, Captain Nora Bell has to get past a desk sergeant who throws her
  credentials in the trash because she does not look like his idea of a captain.* Seven beats over eight scenes:
  SETUP SC01 → INCITING SC02 (letter crumpled) → ESCALATION SC03 → MIDPOINT SC04 (Ortiz recovers the letter) →
  CRISIS SC05 (phone call + name read aloud) → CLIMAX SC06 → RESOLUTION SC07–08. Value at stake: *recognition*,
  shifting − − − + + + + +.
- **Direction.** Rules: eye level, no handheld; Nora stays screen-right across the desk; hold on the reaction after a
  line lands. Two reveals (`letter_is_appointment`, `lieutenant_confirms`), each with a hold/reaction on a named shot.
  Kessler's intensity climbs 3→5 in SC05, then falls: no jump above 2.
- **Pre-production and shots.** Three locked looks, two locations (lobby SC01–06, briefing room SC07–08 after the card
  "Roll call, 8 a.m."), 16 generations, 4 documented over-length prompts.
- **Handoffs.** Letter: held → read → crumpled → binned → recovered, never "dropped" across a cut.
- **Proof it works.** `plan` reproduces the shipped prompts and stills byte for byte; Gates 1–2 `PASS`, Gate 3 needs a
  named storyboard reviewer. The film has **not** been accepted by the Owner (creative review pending), and the C2PA
  signer is a dev signer.

## 11. Red flags — stop and re-plan

- A gate says `NOT_RUN` and you are about to call it done.
- You are editing a prompt to fix something a locked look, state or check should have prevented.
- A beat needs something to fall, tear, spill or be thrown and caught across the 8 s cut.
- A scene carries a reveal with no emphasis device, or a fact with no carrier before it is needed.
- More than two speakers, more than three people in frame, or dialogue over the syllable limit.
- Race or police wording in a video prompt; photoreal character refs on a route that refuses them.
- You are about to approve your own storyboard frames and report it as independent review.
- A "fix" that makes a test pass by weakening the check.
- Spending credits without an Owner go-ahead (`OWNER_GO_LIVE`), or retrying a blocked job unchanged.
