# Operator runbook: from `film.py new` to `deliver --accept`

One film, one package `films/<id>/`. Commands run from the repo root with `PYTHONPATH=src`. `film.py status --film F` prints the
next action and the step of this runbook it belongs to (`runbook: docs/production/RUNBOOK.md R<n>`).
Every command below is checked against the CLI parser by `tests/test_production_runbook.py`.

**Who decides what.** The Owner approves each new film's brief, rights and budget before generation, and the final delivery.
Under [OWNER_POLICY.md](OWNER_POLICY.md), the delegated agent reviews stills, storyboards and takes and records technical
picture lock with concrete evidence under its own name. Story meaning, cap increases and publication remain Owner decisions.
A gate is never marked PASS by hand. The approved [P20 plan](PRODUCTION_STABILITY_P20_PLAN.md) requires two consecutive
Owner-approved25–30minute films before claiming stable operation.

## R1 Create the package

```bash
python tools/film.py new film05_name --profile drama --title "Title"
```

Write `script.fountain`, then `01_story.json` … `04_shots.json` (see `docs/director/DIRECTOR_PLAYBOOK.md`). Allocate enough
generations for each scene's speech, movement and reactions; each generation still passes its own duration/speech limits.
Drama only; media (`media/`) is git-ignored and never committed. Long films need a dedicated scratch volume: at least20GiB
free before starting, or1.5times the measured peak scratch if larger; retain4GiB reserve during the run.

## R2 Gates 1–2: story and direction

```bash
python tools/film.py validate --film films/film05_name
```

Fix what a BLOCK names, in the stage that should have caught it. **Owner checkpoint 1 — story:** the Owner approves the story and
the audio lock (`OWNER_PENDING` at gate 1 until then).

## R3 Plan and storyboard

```bash
python tools/film.py plan --film films/film05_name --out films/film05_name/media/plan
python tools/film.py animatic --film films/film05_name
python tools/film.py planning --film films/film05_name
python tools/film.py reviewpack --film films/film05_name
```

`plan` writes prompts, start-still prompts, storyboard frames and `gate3.json` (+ `plan_meta.json` with the word budget per
prompt section). **Delegated storyboard review:** inspect the frames (`media/review/index.html`) and record each reviewed
frame's approval and hash in the existing storyboard registry under the delegated agent's name. Do not use the blanket
`--approve-storyboard` flag (OWNER_POLICY.md). Reuse valid existing approvals; never infer approval from a successful plan.

Re-run `plan` after any change to a stage file (gate 3 says "the plan is stale").

## R4 Rights, budget, go-live

**Owner checkpoint 3 — rights:** every character, location and source in `03_preprod.json` `rights` is cleared or consciously
accepted. **Owner checkpoint 4 — new-film brief and budget:** prepare the script/shot plan and estimate, then obtain the
Owner's explicit approval. The existing256.8credit cap is not enough authorization for a long film and never rises itself.
`OWNER_GO_LIVE: YES` in `docs/production/LOOP_BACKLOG.md` gates real sends. No agent flips it without authorization;
OWNER_POLICY.md delegates a one-send enable/reset after the film and its cap have been approved. Restore `NO` even on error.
Without it `generate` refuses and status says "Generate is paused". Before a first live run, rehearse offline:

```bash
python tools/film.py rehearse --film films/film05_name --out D:/rehearsals/film05
```

## R5 Start stills

The Flow route needs an approved start still per generation (prompt in `media/plan/stills/start_<GID>.txt`). Generate the image
in Flow, then register it and have the named delegated reviewer approve it after inspection:

```bash
python tools/film.py stills --film films/film05_name --register SC01_g1 --image path/to/still.png --source "Flow Nano Banana"
python tools/film.py stills --film films/film05_name --approve SC01_g1 --by "Owner Name"
python tools/film.py stills --film films/film05_name
```

A still goes stale when its prompt or file changes. Photoreal references are refused by some providers; keep the illustrated pass.

## R6 Generate

```bash
python tools/film.py generate --film films/film05_name --gid SC01_g1 --dry-run
python tools/film.py generate --film films/film05_name --gid SC01_g1 --start-token tok:TAIL_OF_UPLOADED_STILL
```

The dry run lists every blocker (unapproved still, previous take not accepted, budget). The live call needs
`OWNER_GO_LIVE: YES`, the start token of the uploaded still, and Flow open in the GPM browser (never closed; no cookies or
captchas touched). A generation after a hand-off waits until the previous take is ACCEPTED. **Stop rules:** stop at 1.5x the
estimate; stop and call it BLOCKED when the same cause fails twice (change the prompt or the start frame, not the retry count).

## R7 Review takes

```bash
python tools/film.py review --film films/film05_name
python tools/film.py review --film films/film05_name --ingest path/to/filled_sheet.json
python tools/film.py retake --film films/film05_name
```

**Delegated take reviews:** `review` writes a QC sheet per take; the reviewer watches the full moving clip and fills the
content groups with concrete evidence (an automatic metric may only WARN). Never sign as the Owner. `--ingest` binds the
sheet to the take's bytes. `retake` lists what to redo and why
(`PROMPT`, `START_FRAME`, `PROVIDER_LIMIT`, `STAGING`); `retake --pickup GID --reason "…"` records a pickup.

## R8 Edit and picture lock

`05_edit.json` lists the accepted takes in order, the title card (it must carry the AI line) and the tags. `edit --init`
drafts it from the shot list and the latest ACCEPTED take of each generation (a generation without one is listed as missing, no
footage is invented); it refuses to overwrite an EDL that already has events. Check the draft, then cut:

```bash
python tools/film.py edit --film films/film05_name --init
python tools/film.py cut --film films/film05_name --render --out films/film05_name/media/cut/cut.mp4
python tools/film.py lock --film films/film05_name --lock --by "Owner Name" --reason "picture approved"
```

**Technical picture lock:** the cut is watched and locked by the named delegated reviewer. Any later change to a take or EDL makes the
lock stale and everything downstream "dirty".

## R9 Post: grade, titles, mix, master QC, versions

For a fresh locked EDL, run or resume the standard chain:

```bash
python tools/film.py finish --film films/film05_name --dry-run
python tools/film.py finish --film films/film05_name
```

`finish` checks environment, free space and input/output hashes; completed fresh steps and render parts are reused after
interruption. It runs grade/titles/clean picture, mix, mastercheck, portrait, dialoguecheck and delivery. It never signs final
Owner acceptance. The individual commands remain available for diagnosis:

```bash
python tools/film.py grade --film films/film05_name --render --out films/film05_name/media/cut/graded.mp4
python tools/film.py titles --film films/film05_name --generators-file films/film05_name/generators.json --render --color --out films/film05_name/media/cut/titled_cut.mp4
python tools/film.py sounds --film films/film05_name
python tools/film.py mix --film films/film05_name --cut films/film05_name/media/cut/titled_cut.mp4 --out films/film05_name/media/cut/mixed.mp4
python tools/film.py mastercheck --film films/film05_name --cut-report films/film05_name/media/cut/titled_cut.cut.json
python tools/film.py versions --film films/film05_name --cut-report films/film05_name/media/cut/titled_cut.cut.json --generators-file films/film05_name/generators.json
```

`generators.json` names each provider with role, model and settings (it feeds the credits and the AI disclosure).
`python tools/film.py generators --film films/film05_name --init` drafts it from the take log (video tool) and the registered
start stills (image tool); check the names and settings, it never overwrites a filled file. A BLOCK from
`mastercheck` (freeze, loudness, label) is fixed upstream, never waived by editing the check.

## R10 Deliver and accept

```bash
python tools/film.py deliver --film films/film05_name --cut-report films/film05_name/media/cut/titled_cut.cut.json --generators-file films/film05_name/generators.json
python tools/film.py status --film films/film05_name --package films/film05_name/delivery
python tools/film.py deliver --film films/film05_name --accept "Owner Name"
```

`deliver` builds a new immutable `media/deliveries/<version>/` (masters, sidecars, metadata, QC, rights, a package copy and
`MANIFEST.json`). `07_delivery.json` contains the current manifest path; use that path for `status --package` instead of the
legacy example above. The pointer changes atomically only after verification; an open previous master remains usable.
Unchanged inputs reuse the same manifest and preserve its acceptance. It BLOCKs on a
missing AI label and WARNs while rights or the picture lock are open; `release_ready` is true only with no WARN.
**Owner checkpoint 7 — acceptance:** `--accept` is bound to the manifest hash; a changed delivery needs new acceptance. A rehearsal package
can never be accepted.

## Where things live

| What | Where |
| --- | --- |
| Package (tracked) | `films/<id>/` stage files, `ledger.json`, `generators.json`, `takes/` logs and receipts |
| Media (git-ignored) | `films/<id>/media/` — plan, stills, takes, cut, review page |
| Delivery archive | Manifest path in `07_delivery.json`; immutable `media/deliveries/<version>/`; legacy `delivery/` remains readable |
| Loop state | `docs/production/LOOP_BACKLOG.md`, `IMPLEMENTATION_STATUS.md` |

## Recovery

* A send that raised before reporting leaves a `PENDING` receipt in `takes/intents/`, reserving its quoted cost. Status lists
  its take ID and structured `next_step`. Reconcile it before another send; never edit the receipt or registry by hand:

```bash
python tools/film.py reconcile --film films/film05_name --take-id SC01_g1_t1
```

* Reconcile uses the original prompt snapshot and hash-bound provider/download evidence, registers exactly once, and never
  accepts the take creatively. Ambiguous results remain pending; only evidenced provider failure permits the existing bounded
  resend policy, still subject to rights and budget. The film/Flow writer lock releases on process death, while receipts persist.
* A stale plan or still: re-run `plan`, re-register the still. Nothing is silently reused.
* A bad delivery: fix upstream and run `deliver` again; the earlier archive is kept.
* Defects found in a film are fixed in the pipeline stage that should have caught them, then in the film (playbook §7).
