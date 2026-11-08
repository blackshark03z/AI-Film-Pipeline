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
python tools/film.py cut        --film films/<film_id> [--clips <dir>] [--accepted-only]   # check 05_edit.json against the take log, print the timeline (exit 1 on BLOCK)
python tools/film.py cut        --film films/<film_id> --render [--out <mp4>]   # assembly (hard cuts, dissolves, J/L) -> media/cut/rough_cut.mp4 + .cut.json report
python tools/film.py lock       --film films/<film_id>    # lock status + post/delivery items that no longer match the cut (exit 1 if stale or dirty)
python tools/film.py lock       --film films/<film_id> --lock --by "<name>" [--reason "<why>"] [--clips <dir>]   # freeze the cut
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

Cut rule of thumb (`production/edit.py`): `05_edit.json` lists events in order; a TAKE event names a take id
(`<gid>_t<N>`) of the take log and optionally the used range `src_in_s`..`src_out_s`; a CARD event is a context card.
Identity tags sit on a TAKE event in seconds of its used part. Each event carries the transition into it (the first is a
CUT; MATCH_CUT is a cut, DISSOLVE and DIP_TO_BLACK overlap the neighbours by their duration) and the J/L split. A J-cut
needs `j_cut_s` of source before `src_in_s`; an L-cut needs the previous take trimmed early (`src_out_s` + `l_cut_s`
inside the clip): trim to create the handle. A take of a superseded shot version, a rejected take, a clip whose bytes
changed since logging, a trim outside the clip or a transition longer than its neighbours blocks the cut; an unreviewed
take only warns until `--accepted-only` (use it for the fine cut and picture lock). `film.py cut` also prints the
rhythm report (scene average vs `target_avg_shot_s` within 30%; a declared hold buys its seconds over the target;
a shot over 1.5 x target with no hold is an unplanned hold) and the cut-continuity findings (chained handoff states,
trimmed chained cuts that cannot be proven, line crossings with flipped eyelines, jump-cut risk). Rhythm and axis
findings are advice for the human at CUT level, not gates. Loudness, subtitles and credits are P5.

Picture lock rule of thumb (`production/lock.py`): lock only a cut whose takes a human accepted and that has no BLOCK
at any cut; the lock names who locked it. Everything built on the picture (subtitles, mix, colour, titles, master QC,
packaging) is an item of `06_post.json` / `07_delivery.json` and carries `"locked_against": "<edl_sha256 of the lock>"`
(+ `"events": [...]` if it covers only part of the film). After any change to the EDL, to a take's bytes or to its
review, `film.py lock` lists the items to redo: everything at or after the first changed event is affected (a change moves
the clock), a title/end change affects every event. Relock after review; old locks stay in `lock/history/` so stamps from
older cuts remain comparable. Gate 5 passes only while the lock is fresh.

Mix rule of thumb (`production/mix.py`): render the cut first, then `film.py mix --film films/<id>` writes four
stems to `audio/stems` (dialogue = the cut's own sound; ambience = a generated bed per scene from the location's
`room_tone`; sfx; music from `audio/mix_plan.json`), ducks ambience + music under the dialogue, and masters the result to
-14 LUFS / -1 dBTP (`media/cut/mixed.mp4`, report `audio/mix.json`). A shot's `sfx` text is placed only if
`audio/sfx/<slug>.wav` exists (else `SFX_UNSOURCED`, the take's own sound stays); a music cue whose asset is missing blocks.
The mix is recorded in `06_post.json` as item `mix` with `locked_against` = the fresh picture lock (empty, so UNSTAMPED,
until the picture is locked). Rights of sfx/music assets are recorded in P5-02.

Sound rights rule of thumb (`production/sound_rights.py`): every music file in `audio/mix_plan.json` and every
`audio/sfx/<slug>.wav` that matches a shot's `sfx` needs a cleared record in `audio/assets.json`
(`film.py sounds --record audio/music/x.wav --kind music --license CC0-1.0 --source-url URL --usage 0:20`; it records
`pending`, only a human passes `--status cleared`). Licenses: CC0-1.0, CC-BY (attribution text required), ROYALTY_FREE
(source URL), ORIGINAL, GENERATED_OFFLINE, OWNER_LICENSED. A changed file, a cue outside the recorded usage range or a
missing source blocks `film.py validate`. `film.py sounds` also prints the cue sheet: per scene IN/HOLD/DUCK/OUT/NONE from
the emotional curve with the reason, and warnings for planned cues without a `why`. Nothing is downloaded by the tools.

Colour rule of thumb (`production/color.py`, `film.py grade`): shots of one scene should read as one light. `grade` measures
the mean R/G/B of each used take, picks a per-scene reference (the shot named in `color/color_plan.json` `references`, else the
per-channel median), and computes channel gains clamped to +-`max_gain` (0.25) so a deliberate light change is never flattened;
list such shots in `skip`. The report (`color/color.json`) gives per shot the deviation before/after, exposure in stops and the
white-balance shift, and `OUT_OF_RANGE` warns where the clamp left a shot far from the reference (re-shoot or `skip` it). The
gains are applied at render (`film.py grade --render`, `cut --render --color`), ahead of the global look (`post.GRADE` or the
plan's `look`); take files are never changed. The result is the post item `color`, stamped with the picture lock.

Titles, credits, subtitles, reframe (`production/titles.py`, `film.py titles`): the end card is built from the package -
characters of `03_preprod.json`, the AI disclosure line (`--generators "Google Flow Omni 1.1 Flash"`), the attributions of the
cleared sound assets and the fiction line; it is fitted to the frame or `CREDITS_OVERFLOW` blocks. Dialogue text comes from the
script lines a shot declares; timing is the speech `silencedetect` finds in the used part of the take, or an explicit entry in
`titles/cues.json` (seconds into the used part of the event). A `DIALOGUE_UNALIGNED` / `DIALOGUE_NO_SPEECH` / `CUE_TOO_FAST`
warning means a human checks that cue; real takes carry room tone, so expect to write `cues.json` for noisy shots. Sidecar SRTs
(title, cards, tags, dialogue, credits) are written for the film language and, from `direction.translations`, Vietnamese; a
text with no translation blocks that language. A reframe is a box in `titles/reframe.json` (`w == h`, fractions of the frame);
under half the frame it warns about softness, and an event with identity tags warns that the face moves under the tag.

Status rule of thumb (`production/report.py`, `film.py status`, `film.py status --all`, `film.py ledger`): `status --film` is the one
question "where is this film and what is next". It lists the gates, the missing stages, credits spent against the estimate and
the cap, usable seconds (accepted generations x generation length: a nominal figure, not the cut), credits per usable second,
the retake rate and first-pass rate, open retake decisions, open P0 / P1 findings, dirty post items, rights blockers, the
delivery state and a single `next_action`. A section that fails is named in `errors`, never dropped. `status --all films/` puts every
package side by side. Record what a film taught in `ledger.json` (`film.py ledger --add "<text>" --ref <where to check>`): it stays an
`observation` until another film shows it again (`--replicate L001 --from-film <id> --ref <where>`); the same film twice never
promotes it.

Delivery rule of thumb (`production/deliver.py`, `film.py deliver`, `film.py status --package`): after `mastercheck` and `versions`,
`deliver --generators "<tool and model>"` builds `delivery/` (marked masters, sidecars, thumbnails, metadata, QC, rights, package
JSON, `MANIFEST.json` with hashes). It refuses (nothing is written, an earlier `delivery/` stays) when the opening title card has no
line naming AI (add one to `title` in `05_edit.json`, e.g. "Generated with AI"), when no generator is named, when `qc/master_qc.json`
is missing, stale or failing, when the 9:16 version is missing, or when the disclosure fails `check_release`. Open rights and an
unlocked picture only warn and keep `release_ready` false. Take clips are not archived: the manifest lists them by hash. To prove a
copy is whole, run `film.py status --package <copy of delivery/>` anywhere; it must pass with the working tree gone.

Versions rule of thumb (`production/versions.py`, `film.py versions`): after the master QC, `versions` writes `versions/` with a
9:16 cut of the master, thumbnail candidates and `metadata.json` (status always `DRAFT_NOT_PUBLISHED`; nothing is uploaded). The
9:16 window follows the identity-tag anchor of each shot, else the centre of its reframe box, else the middle of the frame
(`PORTRAIT_FOCUS_UNKNOWN`: put a tag or a reframe box on any shot whose subject is off-centre); title, end card and CARD events
are fitted to the width on black. The master burns its dialogue cues across the 16:9 frame, so the crop loses some of them
(`PORTRAIT_BURNED_TEXT`): pass `--portrait-source` with a clean cut on the same clock, or ship the sidecar SRTs. Thumbnails come
from the emphasis moments (reveal first, then hold / push / reaction / insert) at a moment with no tag or cue over it. Pass
`--generators` so the AI disclosure names the tools. The platform's own AI-content label is the Owner's to set at upload.

Master QC rule of thumb (`production/master_qc.py`, `film.py mastercheck`): run it on the mixed master (default
`media/cut/mixed.mp4`, with `--cut-report` pointing at the `.cut.json` that holds the planned clock). It checks streams,
1280x720 / 24 fps / h264 / yuv420p, duration against the plan, black frames (BLOCK from 0.5 s), frozen picture (WARN from 2 s,
BLOCK from 4 s), the share of duplicated frames, loudness -14 LUFS +-1.5 and true peak <= -1 dBTP, clipping, silent gaps over
3 s, A/V length, dialogue cues against the dialogue stem (offset over 0.3 s blocks) and faststart. The title card, end card, CARD
events and EDL dips to black are exempt from black/freeze/silence. Results go to `qc/master_qc.json` as CUT-level group checks
(technical, audio, sync, color, delivery); a group it could not assess (no dialogue stem, no timed cues) stays UNASSESSED. It is
technical evidence only: it never says the film is good.

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

Script writing constraints that come from the generator, not taste: **a scene is cut from generations of 3-15 s
(Omni 1.2 Flash; film header `generation_s` is only the default), one shot each, each as long as its action**; at most 2 speakers and 3 people in frame; dialogue ≤ 28 syllables per generation at 2.5 syll/s; at least
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

One declaration per generation (`duration_s` 3-15, default the header's `generation_s`): `generation_id` (`SC03_g1`), `scene_id`, `coverage`
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
5. **A shot is as long as its action** (film04 SC01_g1 t9/t10: a ~2 s shutter pull in a 4 s ACTION phase; the model
   pulled past the target and pushed it back up to fill the time). Give each ACTION phase a `motion` from
   `drama/motion_library.py` (natural length; preflight `TIME_FILL` / `RUSHED`), size `duration_s` as about
   1 s setup + the motion + 0.5-1 s settle, and fill extra story time with a scripted beat, not a hold.
   A motion that stops mid-travel stops **on a visible set object** (`stops_at`, e.g. brass shutter catches):
   never "halfway" / "the middle" (`STOP_TARGET`, `TARGET_CONFLICT`). With an end still, the last frame comes
   right after the stop. Measure the prop's path on every take (`film.py motion`) before the review.
   **What the shot does not change is pinned too** (film04 SC01_g2 t1: the action named "the gap under the shutter"
   and the model rolled the shutter up to make one): start-frame prompts say "Unchanged the whole shot, nothing moves
   it: <prop> <state>" for every prop whose end state equals its start state. A person who walks toward the camera is
   pinned only by a far, small start frame (same take: olive rain jacket became a black hoodie); give such a shot an
   end frame where they arrive (plan WARN `LOOK_NOT_PINNED`).
   **Draw the end still first when the action needs room in a prop** (same shot, v2: the approved start still left a
   ~15 cm gap under the shutter; asked for THEO's face in the gap, the end-still edit raised the shutter). Make the
   end still, then redraw the start still from it, and check that unchanged props sit at the same height in both
   (shutter edge row 315 vs 317 here; the old start was 389) before asking for approval.
   **Anchor a prop's state to the set, never to a body that moves** (film04 SC02_g1, before any take): the shutter
   state read "on the catches at her chest height", and the shot has her sit down; "her chest" moves with her, so the
   prompt invites the shutter to follow. It now reads "on the brass catches, a face-high gap left above the counter".
   Check every camera that holds the prop: a lowered shutter at a standing clerk's chest hides her face from the hall,
   so she sits (SC02_g1) and the conversation plays through the gap.
6. **Words that cost credits.** Police + race themes together triggered refunded "reputational risk" blocks (film01,
   film03): no race words in video prose (the start frame carries the look) and drop "police" from the prose of the
   video prompt (`.soft.txt`), dialogue unchanged. Photoreal character refs are refused by some providers; the
   start-frame route avoids refs in the video prompt.
7. **Prompt budget.** `PreflightLimits.max_prompt_words` defaults to 120; the Flow start-frame route runs at **215**
   (film02: all six prompts 165–220 words, 6/6 first pass), set in `03_preprod.json`. The limit applies to the
   **emitted** text (start prefix + compiled text). A prompt over the limit is either shortened or listed in
   `accepted_overlong` with a reason — never silently allowed. (The earlier backlog figure of 170 words does not match
   either value; use the one in the film's `preflight` block.)
8. **Know where the words go.** `plan` writes `plan_meta.json` `word_budget` per generation (words per section of the
   emitted text: start prefix, cast/looks, setting, start state, shot timing/action, performance, dialogue, sound,
   fixed tail; they add up to the prompt's word count) and an over-limit `PROMPT_TOO_LONG` line names the three biggest.
   In film04 the budget was eaten by the locked looks + location text + the start-state list, not by the action: shorten
   there first (fewer people in frame, a shorter state list) before cutting beats. The limit stays 215 (Owner item).
9. **A mid-shot entrant is in the start state.** Anyone who walks into frame during the 8 s must still be named in the
   start state (off-screen, with position), or the model invents them and the next handoff has no state to match.
10. **A once-action is spelled out in its ACTION phase.** A must-show action ("hands over the badge") is written in the
   choreography phase where it happens, in observable words; a mention only in the summary or the performance cue is
   not enough, and the model may skip or repeat it.
11. **A prop that changes needs an ACTION/CONSEQUENCE phase that names it.** If a prop is opened, torn, filled or
    moved, the phase says which prop and what the visible result is; otherwise the end state cannot be verified and the
    next generation starts from a guess (§2 above: only control what the model controls).

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
| film03 | 12 credits ×3 lost to moderation | Prompt wording in §6.6; record risk in the README |

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
- **Re-run through the package (P7-02).** The shipped takes were imported (`tools/film03_to_package.py`, hash-bound, not
  accepted: INCOMPLETE until a human reviews them), then `cut → grade → titles --render --color → mix → mastercheck →
  versions → deliver` produced a 139.125 s master, a 9:16 version and a 33-file archive. What it lost against the shipped
  final (always-on AI label, generator roles, C2PA) is listed in [PACKAGE_RERUN](../drama/film03/PACKAGE_RERUN.md).
  A legacy film joins the package the same way: register takes with the real prompt, judge only what a machine can,
  write the EDL from the shipped order, and report every difference.

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
