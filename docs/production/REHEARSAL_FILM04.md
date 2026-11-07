# Offline dress rehearsal on film04 (P10-05)

Date: 2026-11-07 · no provider contacted, **0 credits** · stamp: **REHEARSAL — synthetic** · `release_ready: false`.
This shows the *system* runs from plan to a delivery archive. It says nothing about footage quality, and nothing here is an Owner
acceptance (Technical PASS only).

```bash
python tools/film.py rehearse --film films/film04_last_ticket --out <new empty dir>   # ~5 min
```

`rehearse` copies the package to `--out` (the real `films/film04_last_ticket` is never touched; media stays in the copy), sets
`film.json` `"rehearsal": true`, and runs the real chain. The only substitute is the video step: `generate` gets a mock runner
(`rehearsal.mock_runner`, ffmpeg: the start still with a slow drifting crop, grain and a quiet tone, 8 s) instead of Flow.
The report is `<out>/REHEARSAL_REPORT.json`.

## What the `rehearsal` flag changes

| Where | Rehearsal package | Normal package |
| --- | --- | --- |
| Reviewer `REHEARSAL-BOT` (stills approve, take review incl. waivers, storyboard approval, picture lock) | allowed | **refused** (`refuse_bot`) |
| `generate` with an explicit mock runner | skips `OWNER_GO_LIVE`, budget check; credits recorded 0 | needs `OWNER_GO_LIVE: YES` |
| `generate` with the default (Flow) runner | still needs `OWNER_GO_LIVE: YES` | same |
| `deliver` | adds WARN `REHEARSAL_SYNTHETIC` (in the manifest) and `stamp` in the result; `release_ready` stays false | unchanged |
| `deliver --accept` | refused: "rehearsal package … never releasable" | normal rules; BOT name refused |

## Run result (film04, 12 generations)

| Step | Result | Wall time |
| --- | --- | --- |
| `plan --approve-storyboard REHEARSAL-BOT` | ok | 1 s |
| `stills --register/--approve` ×12 (storyboard frame as placeholder) | ok | 17 s |
| `generate` ×12 (mock runner) | ok, 12 takes, 0 credits | 10 s |
| `review --ingest` ×12 (`human:REHEARSAL-BOT`) | 12 ACCEPTED | 9 s |
| `cut --render` | ok, 12 events | 35 s |
| `lock --lock --by REHEARSAL-BOT` | ok | 1 s |
| `grade --render` | ok | 91 s |
| `titles --render --color` | ok (103.0 s film) | 105 s |
| `mix` | ok (10 × `CUE_NO_SPEECH` WARN: the clips carry a tone, not speech) | 15 s |
| `mastercheck` | ok, 0 BLOCK, WARN: `CUE_NO_SPEECH`, `DUPLICATED_FRAMES` | 4 s |
| `versions` | ok | 22 s |
| `deliver` | ok, 31 files, **0 BLOCK**, 7 WARN (6 × `RIGHTS_PENDING`, `REHEARSAL_SYNTHETIC`), label on 5 of 5 sampled frames | 4 s |

Total 312 s. Gates after the run: 1–5 PASS, 6 `OWNER_PENDING`; `deliver --accept Owner` is refused.

**Re-run after P11-01…P11-08 (2026-11-07):** same chain, all steps ok, 494 s wall, 0 credits. The delivery now carries the AI label on
the 16:9 body *and* the 9:16 version (every sampled frame, P11-01/02), gate 4 and gate 3 read the stronger evidence (P11-03/04), and
a last step `restore` copies `delivery/` to a temporary directory and runs `film.py status --package` on the copy: ok, 31 files,
`film04_last_ticket`, every hash, the package and each master's disclosure verified (P11-08; `REHEARSAL_REPORT.json` key `restore`).
Still synthetic: no footage quality, no Owner acceptance.

## Things the rehearsal found (each becomes a P11 item)

First attempts failed for real reasons, not mock tricks:

1. `plan` left every storyboard `PENDING`, so `generate` was blocked (`PACKAGE_PROBLEM … preflight BLOCKED`). Correct behaviour; a real run needs the Owner's storyboard approval first.
2. The first mock clips were static; master QC rightly BLOCKed `FREEZE` ×12. The mock now moves; the check was not touched.
3. `deliver` BLOCKed `AI_LABEL_MISSING` until the title card had an AI line.

Manual steps the rehearsal had to do itself (nothing in the CLI authors them):

| # | Manual step | P11 item |
| --- | --- | --- |
| M1 | `05_edit.json` was `{}`: the rehearsal wrote one TAKE event per generation in plan order | closed by P11-07 `film.py edit --init`: drafts an EDL from the shot list and the take log (human edits it); the rehearsal itself still writes its own |
| M2 | The title card needs an AI line (`title: [..., "Generated with AI"]`) or `deliver` BLOCKs | closed by P11-07: the drafted EDL includes the title card with the AI line |
| M3 | `generators.json` (role/name/model/settings) written by hand | closed by P11-07 `film.py generators --init` from the take log routes/models and the still sources |
| M4 | Start stills are storyboard frames; real ones need the image step in Flow | LIVE (P3-05) – no system fix |
| M5 | Storyboard approval and every take review are placeholders | Owner checkpoints, by design |

## Not covered

Real Flow sends, the 215-word limit with real prompts at generation time, real speech/cue timing, C2PA signing, rights decisions,
Owner acceptance.
