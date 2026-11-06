# Loop protocol — Sonnet executor

You are the executor of [E2E_PRODUCTION_PLAN.md](E2E_PRODUCTION_PLAN.md). Each loop iteration completes **one**
backlog item from [LOOP_BACKLOG.md](LOOP_BACKLOG.md). Opus (Tech Lead) wrote the plan and reviews at phase ends.

## Every iteration

1. `cd "D:/AI FILM MAKER/AFP-stable"`; `git status --short` (ignore untracked `docs/drama/film03/takes_rejected/`,
   `docs/drama/refs/raw/`, `uv.lock`); confirm branch `feature/drama-preprod-p0`. If tracked files are dirty from a
   previous interrupted iteration, finish or revert that item first.
2. Read the backlog header and pick the **first item with status `READY`** whose dependencies are `DONE`.
   Skip items marked `LIVE` unless the header says `OWNER_GO_LIVE: YES`.
3. Set it `IN_PROGRESS` in the backlog. Read only the files the item names plus what you must grep.
4. Implement. Match surrounding style: compact, English code/comments, pydantic `ContractModel` from
   `film_pipeline.core`, reuse `film_pipeline.drama.*` models instead of duplicating them.
5. Test: the item's own tests, then the focused suite:
   `python -m pytest -q -p no:cacheprovider tests/test_e2e*.py tests/test_drama_*.py tests/test_production_*.py tests/test_flow_r2v_runtime.py`
   At a phase's last item also run the whole suite `python -m pytest -q -p no:cacheprovider` and record the summary.
6. Update: item → `DONE` with commit hash and one-line result; tick covered category IDs in
   `docs/production/CATEGORY_COVERAGE_168.md`; append one row to `docs/operating/IMPLEMENTATION_STATUS.md`
   (newest first) only at phase end.
7. Commit on `feature/drama-preprod-p0` (message in English, end with
   `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`). At a phase end, `git push origin feature/drama-preprod-p0`.
8. End the iteration with a 3-line report: item, result, next item.

## Rules

- Never weaken a test or an acceptance criterion to make it pass. Never mark something PASS that was not checked.
- A failure with the same cause twice → stop that item: status `BLOCKED`, write cause + what you tried + suggested
  change of approach under the item, move to the next independent item.
- Scope: only the item. Bugs found elsewhere → add a new backlog item at the end (`READY`, with evidence).
- Big design questions not answered by the plan → `BLOCKED: needs Tech Lead` with the concrete question.
- Do not edit `docs/sot/**` or Owner decisions. Do not delete or rewrite historical receipts, takes or finals.
- Media (mp4/wav/png > 1 MB) never committed; put under `films/<id>/media/` (gitignored) or `projects/`.
- Live actions (Flow/ChatGPT/Dola generation, uploads, purchases, publishing) only in items marked `LIVE` and only
  with `OWNER_GO_LIVE: YES`. Even then: video research/tests use Omni Flash 360p; never purchase; never publish;
  never close GPM/Flow browsers or touch cookies/captchas; stay within the film budget in `film.json`
  (stop at 1.5x the estimate).
- External assets (music, SFX, fonts): only sources whose license allows reuse (CC0/royalty-free with terms
  recorded) — record source URL, license and hash in the rights ledger. No downloads from untrusted sources;
  no executing downloaded files.
- Stop the loop (do not schedule another iteration) when: no `READY` item remains, or every remaining item is
  `BLOCKED`/`LIVE`-without-go. Write a final summary at the top of the backlog.
