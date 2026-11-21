---
name: muse-filmmaker
description: >-
  End-to-end autonomous lane runner for the Muse AI-film pipeline in D:\Muse (muse_studio). Use it whenever the
  Owner sends an .srt or a script in D:\Muse and asks to make a film ("làm phim", "chạy lane", "chạy Muse từ A-Z"),
  or names a lane and a number of accounts. One chat = one lane: it opens an account lease, runs every stage from
  SRT to delivery kit as fast as the lane's accounts allow, self-reviews each review point with
  film-creative-review, logs defects with film-lessons and ends with an honest report. Workspace skill: it replaces
  the older global muse-filmmaker.
---

# Muse filmmaker — autonomous lane runner

This skill is the **order of work and the lane rules** for one lane. Commands, flags, exit codes and stage gates
live in `muse-director` (stage map, `references/commands.md`, `generability.md`, `interaction-contract.md`,
`lessons.md`) and the five film skills. Activate `muse-director` first and keep it open.

**Precedence.** For command syntax, flags and exit codes, `muse-director/references/commands.md` and the code win.
For approval, review cycle, takes, speed and stop rules, **this skill and the "Lane mode" section of
`muse-director` win** over any "ask the Owner", send cap, per-shot or iteration budget (e.g. film-craft
`iteration-economics.md`), `--max-rounds` or other generic guidance elsewhere.

**Do not use** the global skills `film-story-bible`, `film-shot-compiler`, `film-post-assembly`, `film-qa-qc`,
`film-screenplay-normalizer` or the global `muse-filmmaker` for Muse: they predate the current pipeline
(hand-edited `compiled_prompt`, blind retries "until 100% PASS").

## 1. Lane mode — goals and grant

Muse credit is not a constraint in a lane: optimise for **output quality first, then speed**. There are no spend
caps and no cap counting. The Owner's opening message only needs the SRT, the lane id and N accounts; it is the
approval for every run of this lane. Parse it into `<P>/LANE_REVIEW.md` (template: `references/lane-review.md`)
before anything else:

| Field | Source | Default |
|---|---|---|
| SRT | path in the message | — (required) |
| project folder `<P>` | stated path | new folder `D:\Muse\<TITLE>_<YYYYMMDD>` (must not exist) |
| lane id | "lane X" | the project folder name (already unique). One lane id = one project = one chat |
| N accounts | "N tài khoản" / "N accounts" | ask once if missing; never take every free account |

**No stops for the Owner inside a lane.** Every Owner step in other skills becomes a self-review row in
`LANE_REVIEW.md`, then work continues:

- "present to the Owner" / "Owner approves / review / verdict" for the treatment and cast looks, contact sheets,
  the animatic, takes, the master, interaction-contract exceptions → self-review (§5).
- film-treatment's "if the value at stake or the ending is unclear, stop and ask" → write your reading of the SRT
  as an explicit assumption in `LANE_REVIEW.md` and the final report; keep the SRT's events unchanged.
- Dialogue: you may split a line at a sentence boundary or tighten it (for `DIALOGUE_OVER_CAPACITY` or lip-sync
  fit) **without changing its meaning**; log before/after in `LANE_REVIEW.md`. A fix that would change story meaning
  is not allowed: cut the beat instead and report the story cost.
- RED shots: restage before stills, never send them. Voice/music sources with unclear rights: do not use them (native
  audio or a cleared source instead).

Only technical blockers end a lane early (§8).

## 2. Speed rules

- Use all N lane accounts on every `pool_runner` run (the lane picks them from `<P>/lane.json`; never pass `-n`,
  `--accounts` or `--exclude-accounts`).
- One stills call does everything: `pool_runner keyframes <P> --include-setups --include-turnarounds`
  (anchors, turnarounds, setups/plates and keyframes).
- One video send wave per review cycle covers **every** pending shot of the film, never scene by scene.
- Read one downscaled contact sheet (≤ 1280 px) per stage or per wave, never single frames; read JSON summaries,
  not media or raw logs.
- Real stills and takes go through `pool_runner` only. Never `cli keyframes`, `cli run-pool` or `autoprod` in a lane.

## 3. Stage order (run from `D:\Muse`, `PYTHONIOENCODING=utf-8`, absolute paths for every file argument)

Prefix every command with `python -m muse_studio.`. Load the listed skills before the stage (they stay loaded).

| # | Stage | Skills | Do | Read (only this) | Gate |
|---|---|---|---|---|---|
| 0 | Set up | muse-director, film-lessons | Create `<P>`, copy the SRT in, write `LANE_REVIEW.md`; read `muse-director/references/lessons.md` once | — | `<P>` is new and not another lane's |
| 1 | Normalize | + film-treatment, film-craft | `cli normalize-srt <abs srt> --output <P>/beats_norm.json`; `cli srt-audit <P>/beats_norm.json --srt <abs srt>` (summary one-liner in muse-director) | audit summary | coverage holes explained (excerpt rules in muse-director) |
| 2 | Beats, bible, treatment | + film-sound-design if any dialogue | Author `beats.json` (never over `beats_norm.json`), `story_bible.json`, `treatment.md`; interaction contract per dialogue beat; voice/sound plan | the SRT, your own files | every dialogue line has addressee + listener anchor |
| 3a | Compile #1 | muse-director, film-craft | `cli compile <P> --beats <P abs>/beats.json [--cinematic-cutaways] [--audio-mode …]` — note the flags, reuse them in 3b | `staging_review`, `coverage_warnings`, `bible_warnings` from `shots_manifest.json` | write `<P>/generability_review.md`; restage every RED, then recompile |
| R | Rehearsal | muse-director | Copy `<P>` to `%TEMP%\mr_<lane>\p\` (keep it short: Windows 260-character path limit), copy `muse_studio/data/accounts.json` to `%TEMP%\mr_<lane>\accounts.json`, run the "Offline dry run" of `references/commands.md` **on the copy** (`--simulate`, `--accounts-file` = that copy); delete the rehearsal folder after | exit codes, `preflight_report.json` HARD count | every step exits 0 (no `qc-audit` in a dry run: it rejects synthetic clips by design); fix upstream in `<P>`, never in the copy |
| L | Open lane | — | `lane open --lane <id> --project <abs P> -n <N>` (writes `<P>/lane.json`) | `granted`, `accounts`, `expires_at`, `skipped` (account ids only, never emails) | see §4 |
| 2.5 | Stills | + film-creative-review | `pool_runner keyframes <P> --include-setups --include-turnarounds`. Exit 1 / `INCOMPLETE` = expected keyframes missing: list them (snippet below) and re-run | `anchors_contact_sheet.jpg`, `setups_contact_sheet.jpg`, `keyframes_contact_sheet.jpg` (each downscaled ≤ 1280 px) | ★ self-review each sheet; regenerate rejected stills as often as needed under the defect rule (§7) |
| 3b | Compile #2 + preflight | muse-director, film-craft | Same `compile` command and flags; `cli preflight <P> --srt <abs srt>`, or `cli preflight <P> --no-srt-gate` for an excerpt SRT (report says `srt_gate: SKIPPED_BY_FLAG`) | `preflight_report.json` HARD/warnings | 0 HARD; each DOP warning fixed or justified |
| 3.5 | Animatic | + film-creative-review (+ film-sound-design) | `cli animatic <P>` | one sampled sheet of `ANIMATIC/animatic_preview.mp4` ≤ 1280 px | ★ self-review: who speaks to whom, screen direction, rhythm |
| 4–5 | Generation + QC cycles | muse-director, film-craft, film-lessons, film-creative-review | Review cycles of §6 until no shot is pending | per wave: run JSON (`sends_by_shot`, `takes_by_shot`, failed shots), `qc_audit_report.json`, one sheet per take over the **whole** clip | ★ self-review: pick the kept take per shot, or RESTAGE / CUT |
| 6–7 | Assemble + master | + film-sound-design | `cli assemble <P> [flags chosen in the sound plan]` — non-zero exit when the QC report exists but no clip passed | `MASTER_OUTPUT/final_master_1080p.mp4` sampled sheet; loudness/stems from the sound plan | ★ self-review the master |
| 8 | Delivery | muse-director, film-creative-review | `cli deliver <P>` | `MASTER_OUTPUT/DELIVERY_KIT/` file list + poster/trailer sheet | nothing is published |
| E | Close | — | `lane close --lane <id> --project <abs P>`; final report (§9) | — | also on abort |

Missing keyframes after an `INCOMPLETE` stills run:

```
python -c "import json,pathlib,sys;P=pathlib.Path(sys.argv[1]);m=json.loads((P/'shots_manifest.json').read_text(encoding='utf-8'));k={s['keyframe_key'] for s in m['shots'] if s.get('keyframe_key')};d=P/'assets'/'keyframes';print('keys',len(k),'missing',sorted(x for x in k if not (d/(x+'.png')).exists()))" <abs P>
```

To redo a rejected still with the same key, move `assets/keyframes/<keyframe_key>.png` (or the anchor/plate) into
`<P>/_rejected/` (never delete) and re-run the stills call; a changed `opening_state` gives a new key and a new
still by itself. Contact sheets and sampled take/animatic sheets:
`C:\Users\ADMIN\.claude\skills\film-creative-review\references\contact-sheet.md` (ffmpeg); downscale built-in
1920 px sheets to ≤ 1280 px into `<P>/_review/` before reading.

## 4. Lease lifecycle

- **Open** before the first real `pool_runner` run (stage L). Exit 0 with `granted` < N → continue with the
  granted accounts and record it. Exit 2 (no account granted) or 1 (error, e.g. `PROJECT_HELD_BY_OTHER_LANE`) →
  end the lane (§8). Exit 3 `PROJECT_IN_USE` → another lane owns `<P>`: end the lane. Exit 3 `LANE_ID_IN_USE` →
  the id belongs to another project: if you chose the id, pick a new unique one (`<folder>_<HHMM>`) once and record
  it; if the Owner named it, end the lane. A re-open reporting `held > requested` is fine; note it.
- **Renew** (`lane renew --lane <id> --project <abs P>`) before and after any long step without a `pool_runner`
  run — self-review of many sheets, restaging, rehearsal (TTL 8 h; `pool_runner` renews by itself while it runs).
  Exit 2 = leases expired → `lane open` again with the same flags once; still no grant → end the lane.
- **Close** at the end and on every early end (§8), before the final report.

## 5. Self-review at ★ points

Use `film-creative-review` exactly (blind read first, then intent; exact `CREATIVE_REVIEW` line with
`reviewer=agent:<your model>` and `self_review=yes`). Its cap applies: the best a lane can write is
`RECOMMEND_ACCEPT_LIMITED`. Map it into `LANE_REVIEW.md`:

- **PASS** — `RECOMMEND_ACCEPT_LIMITED`; continue.
- **RESTAGE** — fixable upstream: change `beats.json` (`staging`, `opening_state`, interaction fields),
  `story_bible.json`, the reference images or the treatment, then recompile and regenerate what changed. Never
  hand-edit `compiled_prompt` or `shots_manifest.json`.
- **CUT** — the beat cannot work after the defect loop: remove or `omit` it upstream, recompile, check SRT coverage
  still holds, record the story cost.

Every verdict names its evidence: file + cell (sheet row/column) or timecode. Never skip a ★ review or the ledger
row to save time; a QC `PASS` or a high `quality_score` is not a review.

## 6. Generation review cycle (multi-take)

Takes per shot (more takes = better pick, same wall-clock): GREEN 1, AMBER 2, UNKNOWN 3, and at least 2 for any
dialogue / lip-sync shot. RED is restaged before stills and never sent.

1. Wave: `pool_runner videos <P> --max-rounds 1 --takes <K>` sends every pending shot (not in `passed_clips`) at
   once: take k of every shot is its own batch layer (batch ids end `_T<k>`), layers run concurrently on all lane
   accounts. A shot's manifest field `takes` overrides K, but `compile` does not write it and the manifest is never
   hand-edited, so use `K` = the largest number any pending shot needs (credit is not a constraint). Exit 2
   blocked / 3 session conflict → end the lane (§8).
2. `cli qc-audit <P> --strips` (always exits 0; it discovers every take of the current design in `BATCHES_V2/*`):
   read `passed_clips`, `failed_or_missing`, `per_shot_qc`. `verified_clips/<shot>.mp4` and `per_shot_qc[<shot>]`
   hold the passing take with the highest `metrics.quality_score` (`take`, `clip_path`); `per_shot_qc[<shot>]
   .candidates` lists every take (`take`, `clip_path`, `verdict`, `quality_score`, `defects`, `strip_path`).
   Strips: `qc_strips/<shot>_strip.jpg` (kept take) and each take's own strip at `candidates[].strip_path`.
   `STALE_RENDER` = only takes of an older design exist: that shot is pending again. A promoted take stays kept by
   later audits while it still passes. Exit 3 = another session holds the project: wait, never force.
3. Self-review: per shot, watch the whole clip of each take (`clip_path` of each, one sampled sheet per take),
   pick the kept take, or RESTAGE / CUT. The score only orders the takes. If you keep a take other than the
   verified one, apply it before assembling: `cli promote-take <P> <shot> <take>` (take number from `candidates`,
   or its `clip_path` if the number is ambiguous; only passing takes with the current design's fingerprint; exit 1
   + JSON `error` otherwise: `TAKE_UNPROVEN` = legacy take without fingerprint, re-render it in the next wave),
   then record its `take` and `clip_path` in `LANE_REVIEW.md`. `assemble` reads only `passed_clips`.
4. Log every defect with its ledger row (§7).
5. RESTAGE upstream, recompile with the stage-3 flags, regenerate the affected stills (review the new sheet). Takes
   of the old design become stale automatically; that shot is pending again.
6. Next wave only for shots still needed; BLOCKED shots must be cut or `omit`ted upstream first (`videos` has no
   subset flag and sends every pending shot). When none are pending, go to stage 6–7.

`sends_by_shot` and `takes_by_shot` from each wave go into `LANE_REVIEW.md` for information only.
`submitted_unconfirmed_shot_ids` / `unconfirmed_submissions`: sends that may still be rendering on Muse (sent without
a result, a crash mid-send, or an old batch dir without result). Those shots are not resent by later waves until
reconciled: the shot passes (`qc-audit` finds its clip), is restaged, or the batch's result arrives. Age never
releases them: past 120 min they show in `unconfirmed_expired` as `EXPIRED_NEEDS_RECONCILE`. Only then may the lane
decide to release them — `videos ... --release-unconfirmed-shot <shot>` (or `--release-unconfirmed` for all) — and
only as an explicit decision written in `LANE_REVIEW.md` (shot, batch, age, why the earlier generation is taken as
over). Before the TTL, release only when the Owner has checked on Muse that the earlier generation is over.
Exit code 4 / `"halted"` / `<project>/muse_halt.json` = Muse showed a CAPTCHA or verification page: all sending stopped
and stays stopped. Never work around it: report to the Owner, who clears it on Muse; only then rerun with `--clear-halt`.

## 7. Defects (film-lessons) — the quality stop rule

Fix each defect in the stage that should have caught it, then add a ledger row to
`.claude/skills/muse-director/references/lessons.md`. Count per beat and defect class in `LANE_REVIEW.md`:
1st occurrence → targeted fix; 2nd → change approach (restage, reframe, new `opening_state`, new reference image,
different coverage); 3rd → CUT the beat or mark it **BLOCKED** (and `omit` it upstream so the next wave does not
resend it), continue the rest of the film and report it. Never re-send an identical design for a structural
defect. Stills (anchors, turnarounds, plates, keyframes) follow the same rule; there is no other limit on
regenerating them.

## 8. Ending a lane early (technical blockers only)

`lane open` exit 1, 2 or 3 (except the one `LANE_ID_IN_USE` retry of §4) · leases lost and not re-grantable ·
`pool_runner` exit 2 or 3 · login, CAPTCHA or account problem · preflight HARD you cannot fix upstream after two
attempts · every remaining beat BLOCKED · `assemble` fails because no clip passed. Close the lane, then report what
was done and what blocked it.

## 9. Final report (to the Owner, Vietnamese)

Three separate verdicts, never merged: **Technical PASS** (preflight, QC counts, report paths) · **Agent
self-review** (labelled "self-review, not independent", verdict per ★ point, kept take per shot) · **Owner
acceptance: pending**. Then: lane id and account ids, waves run, `sends_by_shot` and `takes_by_shot` (information), master and
delivery paths, BLOCKED/CUT beats with reason and story cost, dialogue edits (before/after), story assumptions,
ledger rows added, what was skipped (e.g. `srt_gate: SKIPPED_BY_FLAG`). Template: `references/lane-review.md`.

## Never

Run real stills or takes outside an open lane or outside `pool_runner` · run `--simulate` in the real `<P>` or
without a scratch `--accounts-file` · pass `--accounts` of another lane or touch another lane's folder,
`lane.json` or accounts · change story meaning · kill browser or Python processes · print credentials or
`accounts.json` content · edit `muse_studio/` code during a lane · commit, stash or clean git.
