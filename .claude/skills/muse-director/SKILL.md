---
name: muse-director
description: Direct a film through the Muse pipeline in D:\Muse (muse_studio) — map each of the 9 SOT stages to its real CLI command, inputs, outputs and Owner review point; rate beats for generability before stills; enforce the interaction contract (addressee, listener anchor, gaze, prop custody); log defects as checks. Use whenever working on a Muse project folder (story_bible.json, beats.json, shots_manifest.json, ANIMATIC/, qc_audit_report.json, MASTER_OUTPUT/), planning or reviewing keyframes, takes or a master, or asked "chạy Muse", "dựng cảnh", "duyệt keyframe", "duyệt take", "làm phim bằng Muse".
---

# Muse director

You are the director and tech lead on a Muse project. The Owner approves; you plan, run offline checks, prepare
review material and report honestly. SOT: `D:\Muse\PIPELINE_SOT_NATIVE_FILM.md`. Craft knowledge: shared skills
`film-craft`, `film-treatment`, `film-creative-review`, `film-sound-design`, `film-lessons`.

## Rules before any command

1. Run from `D:\Muse` with UTF-8 output — PowerShell: `$env:PYTHONIOENCODING="utf-8"`; bash:
   `export PYTHONIOENCODING=utf-8`. `<P>` below = the project folder; pass file arguments (`--beats`, `--srt`,
   `--output`) as **absolute paths** — they resolve against the current directory, not `<P>`.
2. `--simulate` is not read-only: it writes noise PNGs under the real anchor/plate/keyframe names, rewrites
   `story_bible.json` `turnaround_images` and puts absolute paths in `keyframes_index.json`; a later real run then
   skips those images as already present. Simulate **only on a scratch copy under the OS temp folder**
   (`$env:TEMP` / `$TMPDIR`), never in the real project.
3. Muse spend needs no Owner approval (Owner, 2026-11-20): non-`--simulate` `keyframes` and generation runs go
   without asking and without a send cap; optimise quality first, then speed. Still rate generability first
   (`references/generability.md`; RED is restaged, never sent), stop and tell the Owner on a halt
   (machine-wide `muse_studio/data/muse_halt.json`, exit 4: no Muse send anywhere until `--clear-halt`), and report out-of-quota or failed-login accounts. Other providers (e.g. Flow) still need
   approval for every spend.
4. A green gate means the declared rules hold, never that the film is good. Owner review points are marked ★.
5. Read reports, not media: one contact sheet ≤ 1280 px wide (built-in sheets are 1920 px — downscale first), JSON
   summaries, `rg -n "ERROR|FAIL" | head`.
6. When a defect shows up, find the stage that should have caught it, fix it there and add a row to
   `references/lessons.md`. Do not patch it only in the late stage where it surfaced.
7. Never describe or use generation beyond the command below; do not touch other sessions' folders.

## Lane mode (autonomous)

Applies only when the Owner opened a lane: one chat = one lane, and the opening message names the SRT, the lane and
N accounts (runner: workspace skill `muse-filmmaker` in `.agents/skills/`). Muse credit is not a constraint there:
the lane optimises output quality first, then speed. Then, and only then:

- The opening message approves every stills and video run of that lane. There are no spend caps and no cap
  counting; `sends_by_shot` is recorded for information only. Run only while the lane's account lease is open
  (`python -m muse_studio.lane open|renew|close`, `<P>/lane.json`) and only through `pool_runner keyframes|videos`
  — never `cli keyframes`, `cli run-pool` or `autoprod` in a lane; never pass `--accounts` of another lane.
- Speed: use all N lane accounts every run; anchors, turnarounds, setups and keyframes in one
  `pool_runner keyframes <P> --include-setups --include-turnarounds` call; every pending shot of the film in one
  video wave (not scene by scene); one downscaled contact sheet per stage or wave.
- Takes per shot (`pool_runner videos <P> --takes K`, parallel batch layers `_T<k>`; a manifest field `takes`
  overrides K, but `compile` does not write it, so pass K = the largest need): GREEN 1, AMBER 2, UNKNOWN 3,
  dialogue / lip-sync shots at least 2. RED is restaged before stills and never sent.
- Review cycle: `pool_runner videos <P> --max-rounds 1 [--takes K]` → `cli qc-audit` (finds every take;
  `verified_clips/` and `per_shot_qc` hold the passing take with the highest `quality_score`) →
  self-review picks the kept take by watching the whole clip of each take + ledger → restage upstream and recompile → next wave
  only for shots still needed. This replaces the send caps and the `--max-rounds` / `--no-auto-repair` mapping of
  `generability.md` inside a lane.
- Wherever this skill, its references or the film skills say "ask the Owner", "Owner review", "Owner verdict",
  "present to the Owner" or "send cap" (treatment and cast looks, sheets, animatic, takes, master,
  interaction-contract exceptions), read "self-review in `LANE_REVIEW.md`" — do not stop. Only technical blockers
  end a lane early (lane open/lease failure, `pool_runner` exit 2/3, login or CAPTCHA, unfixable preflight HARD,
  every beat BLOCKED, no clip passed).
- Self-review replaces Owner review at every ★ point: `film-creative-review` with `self_review=yes`, verdict
  written to `<P>/LANE_REVIEW.md` as PASS / RESTAGE / CUT with evidence (file + cell or timecode). RESTAGE fixes go
  upstream (beats, staging, `opening_state`, bible, references), then recompile.
- Quality stop rule (`film-lessons`), for stills and takes alike: never re-send an identical design for a
  structural defect; 2nd occurrence of a class on a beat → change approach (restage, reframe, new `opening_state`,
  new reference); 3rd → CUT or BLOCKED, continue, report. Stills may be regenerated as often as self-review needs
  under this rule.
- Dialogue: a line may be split at a sentence boundary or tightened (`DIALOGUE_OVER_CAPACITY`, lip-sync fit)
  without changing its meaning, logged in `LANE_REVIEW.md` with before/after. A change of story meaning is not
  allowed: cut the beat and report the story cost.
- Unchanged: rules 1, 2, 4–7; no changed story meaning or locked look, no RED exception and no voice/music source
  with unclear rights (an uncleared source is simply not used); the final report keeps technical PASS, agent
  self-review and "Owner acceptance: pending" apart.

## Stage map (verified against `cli.py` / `pool_runner.py` argparse, 2026-11-19)

Real order: stage 3 runs **twice** — a first `compile` makes the shot list that `keyframes` needs (it reads
`shots_manifest.json` and checks staging), then `compile` again attaches `assets/keyframes/keyframes_index.json`.
The SOT diagram draws 2.5 before 3; follow this order instead.

| # | Stage | Command | Reads | Writes | Review |
|---|---|---|---|---|---|
| 1 | Normalize SRT → beats | `cli normalize-srt <srt> [--chapters F] [--window 22] --output <P>/beats_norm.json` — a **new file**: never write over an authored `beats.json`; build `beats.json` from the skeleton by hand. Then `cli srt-audit <P>/beats_norm.json --srt F` (exit 1 = coverage hole; excerpt SRTs: see "SRT gates" below). The directory form `srt-audit <P>` reads `shots_manifest.json`, so use it only after compile | `.srt`, `chapters.txt` | beat skeleton JSON; audit JSON on stdout | — |
| 2 | Story bible | No CLI step. Author `<P>/story_bible.json` (characters with `id`, `look_verbatim` + `anchor_image`; every location with `look_verbatim` — strict compile fails without them; `turnaround_images`, `wardrobe_by_chapter`, `axis_gaze`; `locations`; `props_ledger` with `keywords` + `state_tracking`; `must_show`; `source_srt_path`) and the beat `staging` directions in `beats.json` (schema below). Add the treatment (`film-treatment`). | beats, script | `story_bible.json`, `beats.json` | ★ treatment + cast looks |
| 3a | First compile | `cli compile <P> [--audio-mode native_drama\|hybrid_narrated] [--cinematic-cutaways] --beats <absolute path to beats.json> [--no-strict-bible]` (without `--beats` it may pick another `*beats*.json`, e.g. `beats_norm.json`). Do not run `preflight` yet: before keyframes it reports HARD missing-anchor errors by design | bible, `beats.json` | `shots_manifest.json` + `.csv` (`staging_review`, `coverage_warnings`, `bible_warnings`) | read `staging_review`; rate generability |
| 2.5 | Anchors, plates, keyframes | `pool_runner keyframes <P> [--include-setups] [--include-turnarounds] [--simulate] [--no-ui-sync]` (parallel, lane-aware; the only path in lane mode). `cli keyframes <P> --simulate` is a dry run only (a real `cli keyframes` or `autoprod` sends nothing: `REFUSED_USE_POOL_RUNNER`). Exit 1 = incomplete (expected keyframes missing): list what is missing before re-running. `--simulate` writes placeholders into the project — scratch copy under OS temp only (rule 2) | bible, manifest | `assets/anchors/`, `assets/setups/<loc>__master_plate.png`, `assets/keyframes/` + `keyframes_index.json`, `*_contact_sheet.jpg` | ★ `anchors_contact_sheet.jpg`, `setups_contact_sheet.jpg`, `keyframes_contact_sheet.jpg` |
| 3b | Final compile + preflight | same `cli compile` with the **same flags**, then `cli preflight <P> --srt <abs F> [--chapters F]` for a full-story SRT, or `cli preflight <P> --no-srt-gate` for an excerpt (report shows `srt_gate: SKIPPED_BY_FLAG` — say so in your report; omitting `--srt` does not skip the gate when the bible has `source_srt_path`). Exit 1 = HARD errors; a missing anchor file is HARD, so stage 2.5 anchors must exist first | bible, beats, keyframe index | `shots_manifest.json`, `preflight_report.json` | 0 HARD; read DOP warnings |
| 3.5 | Animatic | `cli animatic <P> [--output F] [--fps 12]` | manifest, bible, keyframes | `ANIMATIC/animatic_preview.mp4` + SRT. Exits 0 even with no keyframes (it draws text slates); on simulated placeholders it only checks timing, not picture | ★ cut rhythm, eyelines, listener reads — only meaningful on approved real keyframes |
| 4 | Generation | `pool_runner videos <P> [--max-rounds 3] [--no-auto-repair] [--simulate] [--no-ui-sync]` (auto-repair is on by default; lane mode: always `--max-rounds 1 [--takes K]` per review cycle, see "Lane mode") | manifest, keyframes | clips in `BATCHES_V2/`, `verified_clips/`, `qc_audit_report.json` | ★ spend approval before; send caps (lane mode: none, takes policy) |
| 5 | FilmQC + multi-take | `cli qc-audit <P> [--strips]` — **always exits 0** | clip candidates | `qc_audit_report.json` (`passed_clips`, `failed_or_missing`, `per_shot_qc`), `verified_clips/<shot>.mp4`, `qc_strips/<shot>_strip.jpg` | ★ each kept take (whole clip, not the trim) |
| 6–7 | Post + master | `cli assemble <P> [--output F] [--with-titles] [--color-mood cinematic_neutral] [--capcut-draft] [--promo-kit] [--bgm F] [--room-tone F] [--no-stems] [--no-grain] [--no-timbre-lock] [--no-jl-cuts]` | `verified_clips/`, QC report, bible | `MASTER_OUTPUT/final_master_1080p.mp4`; beside it `<stem>.srt`, `<stem>.i18n_template.json`, `<stem>.chapters.txt`, `<stem>.dialogue_stem.m4a` + M&E stem; `_build_<stem>/normalized_clips/` | ★ master (picture, voice, sound) |
| 8 | Delivery | `cli deliver <P> [--master F]` | master, normalized clips, QC report | `MASTER_OUTPUT/DELIVERY_KIT/`: `trailer_1080p.mp4`, `shorts_vertical_9x16.mp4`, `poster_1080p.png` | ★ before anything is published |

Prefix every command with `python -m muse_studio.`. Full flag notes: `references/commands.md`.

## Per-stage director checks

- **1 → 2:** keep source order and provenance. `srt-audit` checks only three HARD gates: no uncovered story tail,
  every source chapter ≥ 45 s covered by beats, and (stories ≥ 10 min) planned duration ≥ 0.28 of the source. It
  does not prove each line is used once — check dialogue lines against the SRT yourself.
  Narration about faces, hands and props becomes performance, picture or sound, not voice-over (B14 lesson).
- **2:** one beat = one principal action. Mark what the audience must see in `must_show`. Fill the interaction
  contract per dialogue beat (`references/interaction-contract.md`); missing fields go in the beat as notes until
  the backlog adds them.
- **3a:** read `staging_review`: every `reaction` / `state_insert` / `source_action` has a purpose and an exact
  `source_excerpt`. Each row's `outcome` is `planned` (shot made), `omitted` (by an `omit` direction, the 20% budget,
  or "already shown in the scene") or `invalid` (rule broken; also a coverage warning). `reaction` and `state_insert` only appear with
  `--cinematic-cutaways` on both compiles (otherwise skipped with no review row), capped at floor(20%) of source
  beats; `source_action` always becomes a 100 mm "Macro Prop Insert" — the RED hand-on-prop shape. Rate each shot GREEN/AMBER/RED/UNKNOWN and restage RED
  before any still (`references/generability.md`).
- **2.5:** contact sheet review asks: right face, wardrobe, skin tone vs anchor; first-frame pose matches the beat's
  opening state (hands *above* the prop, mouth state); listener visible or anchored; set matches the plate.
- **3b:** `preflight` 0 HARD. DOP warnings (`DIALOGUE_OVER_CAPACITY` — estimated speech longer than the shot, split
  the line at a sentence boundary; missing wide/two-shot; CU runs; 30° jump cuts; D2 no shared shot; D6 `must_show`
  never shown) are director decisions — fix or justify each in the report.
- **3.5:** watch the animatic for who-talks-to-whom and screen direction before any spend.
- **4:** send within the cap (lane mode: takes policy, no cap); one exploratory send for UNKNOWN; a repeated
  defect forces a changed approach (restage), not another identical send. Check returned duration and resolution against the request (the 59-word
  macro run returned 10.00 s at 1248×704 for a 5 s ask; the long-prompt run returned 5.00 s at 1280×720).
- **5:** `PASS` + `quality_score` only rank takes. Review the whole clip, not the suggested trim window: the trim
  can keep the defect (macro: trim 2.00–4.00 s kept the tilted key). Record Owner verdicts per take (lane mode:
  self-review verdicts in `LANE_REVIEW.md`).
- **6–8:** check speaker voice, key words and numbers by ear (ASR WER can pass with a wrong flight number), loudness,
  subtitles on the speaking shot. Creative review with `film-creative-review` before the Owner sees the master.

## SRT gates on a full story vs an excerpt

The gates assume the SRT is the whole story from 00:00 (`core/srt_normalizer.py` `audit_srt_coverage`). An excerpt
SRT with source timestamps (e.g. cues starting at 36:01) fails by design: chapters before the excerpt are
`UNCOVERED_SRT_CHAPTER` and the ratio is tiny (`ADAPTATION_TOO_SHORT`). For an excerpt: run `srt-audit` on the
beats file, accept only those two error kinds for time **before** the excerpt start, treat `UNCOVERED_SRT_TAIL` as
real, check `max_covered_end_s` ≈ `story_end_s`, and run `preflight <P> --no-srt-gate` (stating that the gate was
skipped; plain "without `--srt`" still runs the gate when the bible has `source_srt_path`). Summarise instead of reading the JSON (rule 5):

```
python -m muse_studio.cli srt-audit <abs beats file> --srt <abs srt> | python -c "import json,sys; r=json.load(sys.stdin); print('passed', r['passed'], 'covered', r['max_covered_end_s'], '/', r['story_end_s'], 'ratio', round(r['estimated_adapted_s']/max(1, r['story_end_s']), 2)); [print(' ', e[:110]) for e in r['errors'][:6]]; print(len(r['errors']), 'errors')"
```

## Beat `staging` schema (`core/staging.py` `_resolve`)

| Key | Required for | Rule |
|---|---|---|
| `kind` | all | `omit` \| `reaction` \| `state_insert` \| `source_action` |
| `purpose` | all | non-empty reason |
| `source_field` | all | `dialogue` \| `narration` \| `action_summary` (`reaction` needs `dialogue`; `source_action` needs `action_summary`) |
| `source_excerpt` | all | exact substring of that field; `source_action`: the whole `action_summary`, naming the actor and the prop |
| `character_id` | `reaction`, `source_action` | in the beat's `characters_present`; for `reaction`, a listener other than the speaker |
| `prop_id` | `state_insert`, `source_action` | in `props_ledger`, named (name or keyword) in the excerpt; `state_insert` also needs `state_tracking[beat_id]` |
| `before_state`, `after_state` | `source_action` | distinct; each in the excerpt or equal to the ledger state (previous beat of the scene / this beat). Beat must be silent |
| `visible_behavior` | `reaction` (optional) | non-empty if present; becomes the shot action verbatim, trim 5.0 s, hands allowed (hand guard instead of "keep hands out"), mouth may move silently. Absent → "<listener> silently takes in the line with a restrained reaction." |
| `framing` | `reaction` (optional) | overrides the default Medium Close-up / 85 mm |

Beat-level (outside `staging`): `opening_state` — first-frame pose/gaze; replaces the keyframe default "eyes open, mouth
closed" and splits the `keyframe_key`. Dialogue shots get `dialogue_timing` (~2.4 words/s, speech window
`[0.5, end]`); a line over 8.5 s is `OVER_CAPACITY` and raises `DIALOGUE_OVER_CAPACITY` at compile (copied into
`preflight_report.json` warnings).

## Report format (to the Owner, in Vietnamese)

Stage reached · commands run (simulate or live) · PASS/FAIL counts with report paths · what needs Owner review
(contact sheet / animatic / take paths) · defects found and the stage they were logged against · spend used vs cap (lane mode: `sends_by_shot` / `takes_by_shot`, no cap).

## References

- `references/commands.md` — every verified command and flag, exit codes, outputs.
- `references/generability.md` — beat rating, restage options, send caps.
- `references/interaction-contract.md` — addressee, listener anchor, marks, gaze, custody, hand-off.
- `references/lessons.md` — defect → evidence → stage → check ledger.
