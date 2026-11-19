# Post playbook — edit, post and delivery (`05_edit` … `07_delivery`)

Written 2026-11-19. Audience: the model acting as editor / post supervisor after the takes exist. Companion to
[DIRECTOR_PLAYBOOK.md](DIRECTOR_PLAYBOOK.md) (stages 01–04) and read through the skill `.claude/skills/film-post`.
It says **what to decide, which command does it, which files it reads and writes, what blocks you, and what is the
Owner's**. Machine rules live in `src/film_pipeline/production/` (`edit, lock, color, titles, mix, sound_rights, foley,
master_qc, dialogue_stt, versions, deliver, finish, post_engine`) and `src/film_pipeline/drama/{post,disclosure}.py`.
Every command below was checked with `python tools/film.py <cmd> --help` on 2026-11-19; flags not listed there do not
exist. Run from the repo root.

## 0. Rules that govern post

- **Technical PASS ≠ a good cut ≠ Owner acceptance.** `cut`, `mastercheck` and Gate 6 prove the declared rules hold;
  they say nothing about rhythm, performance or emotion. Do the craft review (§6) and report the three separately.
- **Fix the defect in the stage that should have caught it.** A bad take found in the cut goes back to `review` /
  `retake` (stage 04), not to a colour or audio band-aid.
- **Never touch take files.** Trims, gains, reframes and cues live in JSON (`05_edit.json`, `color/`, `titles/`,
  `audio/`); renders go to `media/cut/`. A changed take byte blocks the cut (`the clip on disk changed`).
- **Short output.** Commands print a summary; read reports with `rg -n "BLOCK|FAIL|WARN" <report.json> | head`.
  Review picture as a contact sheet (one image ≤ 1280 px), not frame by frame (`D:\AI FILM MAKER\CLAUDE.md`, the
  parent folder's rules; `AFP-stable` has no `CLAUDE.md` of its own).
- **Nothing here spends credits.** Every post command is local (ffmpeg). A pickup shot found missing in the cut is a
  stage-04 send and follows `OWNER_POLICY.md` §2 (360p Omni Flash, one send at a time).

## 1. Order of work

```
accepted takes (Gate 4)
  → edit --init → hand-edit 05_edit.json → cut (check) → cut --render        rough cut      media/cut/rough_cut.mp4
  → craft passes on the EDL (trim, cut on action, reactions, J/L, cards)      fine cut       (§6.1)
  → cut --accepted-only → lock --lock --by ...                                Gate 5         lock/picture.lock.json
  → generators --init (once)
  → grade → [foley] → titles --render --color [--clean-copy]                  picture        media/cut/titled_cut.mp4
  → sounds (rights) → mix --cut media/cut/titled_cut.mp4                      sound          media/cut/mixed.mp4
  → mastercheck --cut-report media/cut/titled_cut.cut.json                    master QC      qc/master_qc.json
  → versions → dialoguecheck → deliver                                        archive        07_delivery.json (Gate 6 OWNER_PENDING)
  → Owner: deliver --accept NAME                                              Gate 6 PASS
```

`finish` runs the picture → deliver part for you, in exactly this order (`production/finish.py` `finish`:
generators → grade → foley if a shot's `sfx` matches an unsourced catalog entry → titles → mix → mastercheck → versions
→ dialoguecheck → deliver), skips steps whose inputs are unchanged (`media/finish-state.json`), and refuses unless
Gates 1–4 PASS and the picture lock is fresh. `finish --dry-run` lists the steps that would run **only once those
preconditions hold**: while a gate 1–4 is not PASS or the lock is missing/stale it returns `"steps": []` with the
reasons in `blocked` and exits 1 (the check comes before the plan in `finish`), so read `blocked`, not the empty step
list. Like other package writers it takes a per-film lock file under `%LOCALAPPDATA%\AI-Film-Pipeline\locks\`
(`production/runtime.py`; `~/.cache` when `LOCALAPPDATA` is unset), even for `--dry-run`. Run the steps by hand when
you need to inspect one (a colour outlier, a cue warning) before going on.

### Entry branch: a legacy film (e.g. film03)

Check first: `status --film F` and `validate --film F`. If takes are `INCOMPLETE` (imported, never reviewed), the plan
record `gate3.json` is missing, and an older delivery archive exists (film03: legacy `delivery/` plus
`delivery.superseded-*`), **do not run `finish` or `deliver`**: they would refuse (Gates 1–4 not PASS, no lock) and the
old archive is historical evidence, not this cut. Work in this order:
1. Stages 01–04 belong to the `film-director` skill: get the plan record (`plan --film F --out <dir>`; storyboard
   approval follows that skill and `OWNER_POLICY.md`, which forbids `--approve-storyboard`).
2. Review the imported takes (`review --film F` → fill → `review --ingest`), by a reviewer the package lists in
   `film.json` `delegated_reviewers` (§3). film03 lists none: stop and ask the Owner to delegate (§3).
3. Only when Gates 1–4 PASS: rework the EDL (§6.1), lock, then `finish`.
How a legacy film was imported and what it lost: [PACKAGE_RERUN](../drama/film03/PACKAGE_RERUN.md).

Note: `mix` defaults to `--cut media/cut/rough_cut.mp4`; the finishing route mixes the **titled** cut
(`media/cut/titled_cut.mp4`) so the master carries credits and burned cues. Pass `--cut` explicitly by hand.

## 2. Commands (verified with `--help`)

| Command | What it does | Reads | Writes |
|---|---|---|---|
| `edit --film F --init` | Draft EDL: one TAKE event per generation (latest ACCEPTED take of the current shot version) + title card with the AI line. Refused if `05_edit.json` has events | `04_shots.json`, take log | `05_edit.json` |
| `cut --film F [--clips DIR] [--accepted-only]` | Check the EDL against the take log; print timeline, rhythm report, cut-continuity findings. Exit 1 on BLOCK | `05_edit.json`, take log, `media/takes/` | — |
| `cut --film F --render [--out MP4] [--color] [--jobs N] [--hwaccel]` | Render the assembly (hard cuts, dissolves, dips, J/L) | same | `media/cut/rough_cut.mp4` + `.cut.json` |
| `lock --film F` | Lock status and post/delivery items that no longer match the cut. Exit 0 only when a fresh lock exists and no item is dirty: an **unlocked** film also exits 1 (`fresh` is false) | `lock/`, `06_post.json`, `07_delivery.json` | — |
| `lock --film F --lock --by NAME [--reason TEXT] [--clips DIR]` | Freeze the cut (every take accepted, no BLOCK at a cut) | EDL, take log, reviews | `lock/picture.lock.json`, `lock/history/` |
| `generators --film F --init` | Draft `generators.json` (role video+audio / image / voice / music, name, model, settings) | package | `generators.json` |
| `grade --film F [--clips DIR] [--render] [--out MP4] [--jobs N] [--hwaccel]` | Per-scene colour match: reference shot, clamped per-channel gains, before/after deviation | `color/color_plan.json` (optional), takes | `color/color.json`, post item `color`; `--render` → `media/cut/graded_cut.mp4` |
| `foley --film F [--ids IDS] [--all] [--list]` | Offline procedural SFX from the catalog, registered as `GENERATED_OFFLINE` | `04_shots.json` `sfx`, `assets/sfx_catalog.json` | `audio/sfx/<slug>.wav`, `audio/assets.json` |
| `titles --film F [--langs en,vi] [--generators TEXT \| --generators-file JSON] [--render] [--out MP4] [--color] [--clean-copy] [--clips DIR] [--jobs N] [--hwaccel]` | End credits, dialogue cues, EN/VI sidecar SRTs, reframe check; `--render` burns them | `titles/cues.json`, `titles/reframe.json`, script, `02_direction.translations`, `audio/assets.json` | `titles/titles.json`, `titles/credits.json`, `titles/<film>.<lang>.srt`, post item `titles`; `--render` → `media/cut/titled_cut.mp4` (+ `.clean.mp4`) |
| `sounds --film F` | Cue sheet (IN/HOLD/DUCK/OUT/NONE per scene from the emotional curve) and rights state | `audio/mix_plan.json`, `audio/assets.json` | — |
| `sounds --film F --record PATH --kind {music,sfx} --license ID [--source-url URL] [--attribution TEXT] [--usage START:END] [--note TEXT] [--status ...]` | Record a sound asset's rights (`pending` by default) | the file (hashed) | `audio/assets.json` |
| `mix --film F [--cut MP4] [--out MP4] [--stems DIR] [--engine DIR]` | Four stems (dialogue = the cut's sound, ambience from `room_tone`, sfx, music), duck bed under dialogue, master to -14 LUFS / -1 dBTP | the cut + its `.cut.json`, `audio/mix_plan.json`, `audio/sfx/`, `audio/assets.json` | `audio/stems/*.wav`, `audio/mix.json`, `media/cut/mixed.mp4`, post item `mix` |
| `mastercheck --film F [--video MP4] [--cut-report JSON]` | Technical QC of the master (§5) | `media/cut/mixed.mp4`, the `.cut.json` | `qc/master_qc.json` |
| `dialoguecheck --film F [--engine {auto,vosk,faster-whisper}]` | Advisory STT: did the actors say the scripted lines (English only) | master, script | `qc/dialogue_stt.json` |
| `versions --film F [--video MP4] [--cut-report JSON] [--portrait-source MP4] [--generators ... \| --generators-file ...] [--portrait \| --no-portrait] [--jobs N] [--hwaccel]` | Thumbnails, metadata draft with AI disclosure (`DRAFT_NOT_PUBLISHED`), opt-in 9:16 | master, cut report, tags, reframes | `versions/versions.json`, `versions/metadata.json`, `versions/thumbs/` |
| `deliver --film F [--video MP4] [--cut-report JSON] [--generators ... \| --generators-file ...] [--c2pa-cert PEM --c2pa-key PEM] [--portrait \| --no-portrait]` | Build the archive: marked masters, sidecars, thumbs, metadata, QC, rights, package copy, `MANIFEST.json` with hashes | everything above | archive dir named by `07_delivery.json` `delivery.manifest` (film08: `media/deliveries/<stamp>/`; legacy `delivery/`), `07_delivery.json` |
| `deliver --film F --accept NAME` | **Owner only.** Record acceptance of the current archive (bound to its manifest hash); builds nothing. Refused unless Gates 1–5 PASS, Gate 6 `master_issues` is empty and `release_ready` is true (§5) | gates, archive | `07_delivery.json` `owner_acceptance` |
| `finish --film F [--dry-run] [--portrait \| --no-portrait] [--jobs N] [--hwaccel]` | Run/resume the finishing chain (§1); never accepts for the Owner | everything | everything above, `media/finish-state.json` |
| `status --film F` / `status --package DIR` | Where the film is + `next_action` / restore check of a copied archive | package / archive | — |
| `validate --film F` | All gates; exit 1 if any BLOCKs | package | — (`--sync-gates` writes `film.json` gates when safe) |
| `reviewpack --film F [--out HTML]` | One review page for the film | package | `media/review/index.html` |
| `ledger --film F --add TEXT --ref WHERE [--area AREA]` | Record a learning from this film | — | `ledger.json` |

Optional external engine: `mix --engine DIR` (or env `AFP_POST_ENGINE_DIR`) hands the final mix/master to the AutoEdit
v2 post engine as a subprocess (`production/post_engine.py`); only a passing `final.mp4` is copied back. Unset = AFP's
own mix.

`narration` (`import|status|prepare|resume|finish`) is the separate narration profile (E2E import, Flow project
resume); it is not part of the drama post route and is not covered here.

## 3. Stage 05 — edit (`05_edit.json`, Gate 5)

Shape (`production/edit.py`): `{"title": [...], "events": [...]}`. A TAKE event names `take_id` (`<gid>_t<N>`) and
optionally the used range `src_in_s` .. `src_out_s`; a CARD event is a context card. Each event carries the
`transition` into it (`CUT`, `MATCH_CUT`, `DISSOLVE`, `DIP_TO_BLACK`; the first event is a CUT; dissolve/dip need
`duration_s` > 0 and overlap the neighbours) and `audio.j_cut_s` / `audio.l_cut_s`. Identity tags sit on a TAKE event
in seconds of its used part.

What blocks the cut: a take of a superseded shot version, a rejected take, a clip whose bytes changed since logging, a
trim outside the clip, a transition longer than its neighbours, a J-cut without `j_cut_s` of source before `src_in_s`,
an L-cut whose previous take was not trimmed early enough (`src_out_s + l_cut_s` must fit in the clip). An unreviewed
take only WARNs until `--accepted-only` (use it for the fine cut and the lock).

What `cut` reports but does not gate (advice for the human at CUT level): rhythm (scene average shot length vs
`02_direction` `pacing.target_avg_shot_s` within 30%; a shot over 1.5 × target with no declared hold is an unplanned
hold) and cut continuity (chained handoff states, trimmed chained cuts it cannot prove, line crossings with flipped
eyelines, `JUMP_CUT_RISK` for same scene + same size/angle on the same subject, `edit.py` `cut_continuity`).

**Gate 5 (`editorial_picture_lock`, `lock.picture_lock_issues`)** passes only while a lock exists and is fresh. Any
change to the EDL, to an accepted take's bytes or to its review makes it stale; `lock` then lists the post items to
redo (everything at or after the first changed event; a title/end change affects all). Relock after review; old locks
stay in `lock/history/`.

Who locks: treated as a technical decision under `OWNER_POLICY.md` §5 (inferred, not named there — confirm with the
Owner). film08 was locked by `agent:tech-lead.delegated-by.owner-khoikk03`; never use a `human:owner-*` name.
`lock.py` only refuses the rehearsal bot name (`rehearsal.refuse_bot`). Where the code checks delegation
(`rehearsal.refuse_undelegated`: take QC records via `takes.py`, still approvals via `stills.py`, prompt rebinds via
`gate_checks.py`), an `agent:` reviewer must be listed in `film.json` `delegated_reviewers`. **`lock` itself does not
check that list** (code truth, `lock.lock_picture`), but a lock needs every take ACCEPTED, and an agent can only
accept takes under a listed name — so in practice the same list governs. Use a listed name for the lock too. If the
package has no `delegated_reviewers` (film03; film04–film08 have one), stop and ask the Owner to delegate; never add an entry or
invent a name yourself. Dropping or reordering a scene so the story's meaning changes is the Owner's (`OWNER_POLICY.md`: "cutting a
scene" is reserved; reordering is inferred).

## 4. Stage 06 — post (`06_post.json`)

Each item (`color`, `titles`, `mix`, `master_qc`, `versions`) is written by its command and stamped
`locked_against: <edl_sha256 of the lock>` (`mix.stamp_post_item`). Before the lock an item is UNSTAMPED. `lock` and
`status` list dirty items; redo them, do not edit the stamp.

### 4.1 Colour (`grade`)

Shots of one scene should read as one light. `grade` measures the mean R/G/B of each used take, picks a per-scene
reference (`color/color_plan.json` `references`, else the per-channel median) and applies gains clamped to ±0.25 so a
deliberate light change is not flattened; list such shots in `skip`. `OUT_OF_RANGE` in `color/color.json` means the
clamp left a shot far from the reference: reshoot it or `skip` it with a reason. The gains are applied at render
(`grade --render`, `cut --render --color`, `titles --render --color`), ahead of the global look (`drama.post.GRADE`);
take files never change.

### 4.2 Titles, cues, subtitles, reframe (`titles`)

- Opening title: `05_edit.json` `title` must contain a line naming AI (e.g. "Generated with AI"), or `deliver` refuses.
  `edit --init` writes it.
- End card: characters of `03_preprod.json`, the AI generator line (prefer `--generators-file generators.json`,
  roles `video+audio | image | voice | music`), attributions of cleared sound assets, the fiction line;
  `CREDITS_OVERFLOW` blocks.
- Dialogue cues: text from the script lines a shot declares; timing from `silencedetect` in the used part of the
  event, or an explicit `titles/cues.json` entry (`event_id`, `line_no`, `start_s`, `end_s` in seconds into the used
  part). `DIALOGUE_UNALIGNED` / `DIALOGUE_NO_SPEECH` / `CUE_TOO_FAST` → a human checks that cue; real takes carry room
  tone, so expect to write `cues.json` (film08 wrote 270). Cues are clamped to their event: **a subtitle never runs into
  the next shot** (film01 defect).
- Sidecar SRTs for the film language and, from `02_direction.translations`, Vietnamese; a missing translation blocks
  that language.
- Reframe: `titles/reframe.json` box (`w == h`, fractions of the frame). Under half the frame warns about softness; a
  reframed event with identity tags warns that the face moves under the tag.
- `--clean-copy` renders `<out>.clean.mp4` without burned cues so `versions --portrait-source` can re-lay them for 9:16.

### 4.3 Sound (`foley`, `sounds`, `mix`)

- **Order: dialogue → SFX/ambience → music.** Dialogue is the cut's own take sound (and the duck key). Ambience is a
  generated bed per scene from the location's `room_tone` at -40 LUFS. SFX: a shot's `sfx` text is placed only if
  `audio/sfx/<slug>.wav` exists (else `SFX_UNSOURCED`, the take's own sound stays); `foley` can synthesise catalog
  entries offline. Music: cues in `audio/mix_plan.json` (asset, start/end, gain, fades, `why`); a missing asset blocks.
- **Rights before the mix.** Every music file and matched SFX needs a record in `audio/assets.json`:
  `sounds --record audio/music/x.wav --kind music --license CC0-1.0 --source-url URL --usage 0:20`. Licence ids
  (`sound_rights.LICENSES`): `CC0-1.0`, `CC-BY-4.0`, `CC-BY-3.0`, `ROYALTY_FREE`, `ORIGINAL`, `GENERATED_OFFLINE`,
  `OWNER_LICENSED`; a source URL is required for `CC0-1.0`, `CC-BY-4.0`, `CC-BY-3.0` and `ROYALTY_FREE`
  (`NEEDS_SOURCE_URL`), attribution text for the two CC-BY ids (`NEEDS_ATTRIBUTION`). A changed file, a cue outside
  its usage range or a missing source blocks `validate`. The tools download nothing.
- **Who clears.** `sound_rights` (module docstring) says only a human sets `cleared`; the CLI records `pending`. The
  agent never passes `--status cleared` itself. One code exception: `foley` registers the SFX it synthesises as
  `GENERATED_OFFLINE` with status `cleared` (`foley.materialize_film_foley` → `sound_rights.record_asset(...,
  status="cleared")`),
  because the asset is made offline from the catalog.
- **Voice.** One voice per character: `03_preprod.json` `characters.<id>.voice` (voice-bible words compiled into every
  line, `production/sections.py` `CharacterSpec.voice`) and `voice_reference` (an accepted take span later takes are compared against,
  the voice question in `production/takes.py` dailies). That comparison is a reviewer question, not a measurement. `dialoguecheck` is advisory STT for
  the words only (English).
- **Loudness.** `mix` aims at **-14 LUFS ±1.0 LU** and normalises with a -1.5 dBTP limiter target
  (`MixPlan.target_lufs` / `lufs_tolerance` / `true_peak_db`; `normalize_loudness(..., true_peak=min(true_peak_db, -1.5))`
  in `mix.py`), and reports `LOUDNESS_OFF` (BLOCK) outside ±1.0 or above -1 dBTP. `mastercheck` then BLOCKs outside
  -14 ±1.5 LU (-15.5 … -12.5) or a peak above -1 dBTP (`MasterSpec` `target_lufs` / `lufs_tol` / `true_peak_max` in
  `master_qc.py`). **The AFP gate overrides** the generic targets of the shared `film-sound-design` skill and the
  general "−14 to −16 LUFS" streaming range: a -16 master fails here. The field is named `peak_dbfs` but holds a
  **true peak**: `drama.post.measure_ebur128` runs ffmpeg `ebur128=peak=true` and reads the summary's "True peak"
  value, which ffmpeg prints with a "dBFS" unit label. film03 and film08 both measured -14.6 LUFS
  (peaks -1.1 and -2.9).

## 5. Gate 6 (`final_master`) and delivery (`07_delivery.json`)

`mastercheck` (`production/master_qc.py`) on the mixed master checks streams; 1280x720 / 24 fps / h264 / yuv420p;
duration against the planned clock; black frames (BLOCK from 0.5 s); frozen picture (WARN 2 s, BLOCK 4 s); duplicated
frames share; loudness and true peak; clipping; silent gaps over 3 s; A/V length; dialogue cues against the dialogue
stem (offset over 0.3 s blocks); faststart. Title, end card, CARD events and dips to black are exempt from
black/freeze/silence. A group it cannot assess stays UNASSESSED. It never says the film is good.

`versions` writes thumbnails (emphasis moments with no tag or cue over them) and `metadata.json`
(`DRAFT_NOT_PUBLISHED`). **9:16 is opt-in** (`film.json` `portrait_9x16`, or `--portrait`); when on, the crop follows
identity-tag anchors, else the reframe box centre, else the frame centre (`PORTRAIT_FOCUS_UNKNOWN`), and burned cues
are lost at the edges (`PORTRAIT_BURNED_TEXT`): pass `--portrait-source` with the clean copy.

`deliver` refuses (writes nothing, the previous archive stays) when the opening title has no AI line, no generator is
named, `qc/master_qc.json` is missing/stale/failing, a required 9:16 version is missing, or the disclosure fails
`check_release`. It also BLOCKs when the visible AI label is not found burned into sampled frames:
`AI_LABEL_NOT_BURNED` (policy `always`) or `AI_TITLE_CARD_NOT_BURNED` (policy `title_card`), plus `_9X16` variants for
the portrait version. Open rights and an unlocked picture only WARN, and any WARN keeps `release_ready` false. Take
clips are listed by hash, not archived.

`deliver --accept NAME` (`deliver.accept_delivery`) writes nothing and refuses unless Gates 1–5 PASS,
`gate_checks.master_issues` is empty and `release_ready` is true; it also refuses a rehearsal package and the
rehearsal bot name. So open rights or an unlocked picture block the Owner's acceptance until fixed and re-delivered.

**Gate 6 (`gate_checks.master_issues` / `master_pending`, `production/gate_checks.py`)** BLOCKs on: no or failing master
QC, a stale picture lock, no archive, a manifest changed after `07_delivery.json` recorded it, an archive built under a
different `film.json` `disclosure.ai_label`, an archive that does not verify, master QC re-run after delivery. It stays
**OWNER_PENDING** while `release_ready` is false or the Owner has not accepted this manifest.

**AI disclosure** (`drama/disclosure.py`, EU AI Act Art. 50): visible label per `disclosure.ai_label` (`always` = the
small "AI-generated" body label on every frame, the default; `title_card` = title card only), a `disclosure.json`
record, MP4 metadata tags (IPTC digital source type), and optional C2PA (`--c2pa-cert/--c2pa-key`). The dev signer in
`c2pa_dev` is self-issued: validators report it as untrusted. **It is not release-grade**; a trusted certificate is a
purchase/account decision for the Owner. The platform's own AI-content label is set by the Owner at upload.

**Restore check.** Copy the archive anywhere and run `status --package <copy>`; it must pass with the working tree gone.

## 6. Craft layer — what makes the cut good, not just valid

The tools enforce structure. These passes are the editor's job; record what you did and why in the EDL `reason`
fields or the review notes. Use the shared skills `film-creative-review` (rubric for the cut review) and
`film-sound-design` (voice and sound decisions) alongside this list.

### 6.1 Picture edit

1. **Rough cut at about final length first.** Assemble every scene (`edit --init`, `cut --render`), watch it once
   end to end, and get the total within ~10% of the target before polishing any one cut. Polishing a scene that later
   gets cut wastes passes and relocks.
2. **Trim the AI heads and tails.** Start-frame generations open on a near-still frame and often settle or drift in the
   last second. Set `src_in_s` past the stiff head and `src_out_s` before the settle on every TAKE event. The trim also
   creates the handle a J/L cut needs. **No package under `films/` has a trimmed event yet** (checked 2026-11-19:
   film03–film08 have 0 events with `src_in_s` > 0 or a `src_out_s`, 0 J/L, all hard cuts); film08 shipped the
   `edit --init` draft unchanged — technically valid, editorially a string-out.
3. **Cut on action.** End the outgoing shot inside a movement (a turn, a stand, a hand reaching) and start the incoming
   one on the continuation. A cut on a still frame reads as a jump; `JUMP_CUT_RISK` flags the worst cases only.
4. **Reaction timing.** The reaction carries the beat: hold the listener after a line lands for the time
   `02_direction` plans (`pacing` holds, `emphasis` reaction devices); cut away before the face goes slack. A reaction
   held over 1.5 × the scene target with no declared hold is flagged by the rhythm report.
5. **J and L cuts in dialogue.** Lead the next line's sound under the current picture (J, `j_cut_s`) or let a line
   finish over the listener (L, `l_cut_s`). Keep them short (0.3–1.0 s) and only where the source handle exists.
6. **Transitions mean something.** Hard cut by default; DISSOLVE for elapsed time; DIP_TO_BLACK for a chapter or act
   break; CARD for a fact the picture cannot carry. Say why in `02_direction` `transition_in/out`.
7. **Review the cut as a contact sheet + one full watch.** E.g.
   `ffmpeg -v error -i media/cut/rough_cut.mp4 -vf "fps=1/3,scale=256:-1,tile=5x4" -frames:v 1 media/review/cut_sheet.png`
   (one image; a 5x4 tile holds 20 frames, so set `fps` to about 20 / duration and sheet one scene at a time for a
   long film), then watch the whole render once for rhythm. Open a full frame only for the cut in doubt.

### 6.2 Colour and texture

1. **Unify first, grade second.** Match shots within a scene (`grade`) before judging the global look; a look on
   unmatched shots exaggerates the mismatch. film08: 2 of 300 shots stayed `OUT_OF_RANGE` in `color/color.json`
   (worst 11.5 after matching, master QC `COLOR_MATCH` WARN): check those shots on the contact sheet, then skip or
   reshoot.
2. **Deliberate light changes are not errors.** Put them in `color/color_plan.json` `skip` with the reason.
3. **Grain / texture is not modelled** in this pipeline (no grain filter in `drama/post.py` or `production/color.py`).
   Do not add it with ad-hoc ffmpeg outside the tools (it breaks the hash chain); record the need in the backlog.

### 6.3 Sound

1. Dialogue clean and intelligible first; then SFX and ambience so the room is never dead; music last, ducked under
   dialogue, with a `why` for every cue start and stop (`sounds` prints the cue sheet against the emotional curve).
2. No music under a line the audience must hear unless it ducks; `mix` reports a bed ducked by less than
   `min_duck_depth_db` (6 dB, `MixPlan.min_duck_depth_db` in `mix.py`).
3. Silence is a choice: a gap over 3 s in the master is flagged; make it a held room tone, not a dropout.

### 6.4 Subtitles and text

Subtitle **inside the speaking shot**, never across a cut to the listener (the clamp enforces the edge; you still
check that the cue starts when the mouth starts). ≤ 2 lines, readable speed (`CUE_TOO_FAST`). Cards: white on black,
≤ 2 lines, 2–3 s.

## 7. Owner reservations in post (from `OWNER_POLICY.md`)

`OWNER_POLICY.md` names approvals of stills, storyboards and takes, live sends and technical decisions (design,
restaging, coverage, fixes) as delegated, and publishing/sharing, `git push`, purchases and accounts, raising caps,
changing the story's meaning (cutting a scene, changing an ending, adding characters) and starting a film as reserved.
It says nothing specific about post. Rows marked *(inferred)* below are this playbook's reading, **not in
OWNER_POLICY — confirm with the Owner** before relying on them.

| Delegated to the agent (act, record, no question) | Reserved to the Owner (stop and ask) |
|---|---|
| EDL edits, trims, transitions, J/L (technical decisions, policy §5) | `deliver --accept NAME` *(inferred; the code also requires Gates 1–5 PASS and `release_ready`)* |
| Picture lock `lock --lock --by agent:...` *(inferred)* | Publishing, uploading, sharing outside this machine (policy) |
| Grade, titles, cues, reframes, mix, mastercheck, versions, local `deliver` builds (technical, policy §5) | The platform AI label at upload *(inferred, follows from publishing)* |
| Recording sound assets as `pending`; synthesising Foley offline (`foley` self-clears its `GENERATED_OFFLINE` output in code) | Any purchase or account: music libraries, voice services (policy); a trusted C2PA certificate *(inferred, a purchase)* |
| Choosing which accepted take to use (take approval, policy §1); asking for a pickup within caps (policy §2–3) | Cutting a scene, changing the ending (policy); reordering scenes so the meaning changes *(inferred)* |
| Ledger entries | `git push`; raising credit caps for pickups (policy) |

Setting a sound asset to `cleared` is a human act (`sound_rights` docstring): the agent never passes
`--status cleared`. The only automatic `cleared` is `foley`'s own `GENERATED_OFFLINE` output (§4.3).

## 8. Worked example (read only, never re-render)

- **film03 "The Front Desk"** (`films/film03_front_desk/`): 16 TAKE + 2 CARD events, untrimmed, all hard cuts, title
  "THE FRONT DESK" / "Generated with AI". Master 139.125 s, -14.6 LUFS, peak -1.1; findings DUPLICATED_FRAMES (7.3%),
  COLOR_MATCH, two CUE_NO_SPEECH — all WARN. Legacy archive under `delivery/`; `release_ready` false, no Owner
  acceptance. What the package re-run lost against the shipped final: [PACKAGE_RERUN](../drama/film03/PACKAGE_RERUN.md).
- **film08 "Chain of Custody"** (`films/film08_chain_of_custody/`): 300 events, all hard cuts, untrimmed; picture
  locked by `agent:tech-lead.delegated-by.owner-khoikk03` on 2026-11-18; 06_post items `color` (298/300 corrected),
  `titles` (270 cues EN/VI, 45 reframes), `mix`, `master_qc`; master 1807 s, -14.6 LUFS, peak -2.9; archive under
  `media/deliveries/20261118T044106-40b49011c3/`, `release_ready` true, `ai_label` always, **Owner accepted
  2026-11-19**. Technically complete; as an edit it is the untouched draft (§6.1 item 2).

## 9. Red flags — stop

- You are about to call the film done on `mastercheck` PASS with no full watch.
- The EDL is still the `edit --init` draft (no `src_in_s`/`src_out_s`) at picture lock.
- You are fixing a take defect with colour, a reframe or a cue instead of a retake/pickup.
- A music or SFX asset is `pending` and you are about to pass `--status cleared` yourself (only a human clears).
- You are about to run `deliver --accept` yourself, sign as `human:owner-*`, or upload anything.
- `deliver` reports `AI_LABEL_NOT_BURNED` / `AI_TITLE_CARD_NOT_BURNED` (or `_9X16`): rerender titles/versions, do not
  edit the disclosure.
- A post item is dirty against the lock and you are editing its stamp instead of rerunning the command.
- A loudness "fix" by hand outside `mix` (the master hash, `mastercheck` and the archive will disagree).
