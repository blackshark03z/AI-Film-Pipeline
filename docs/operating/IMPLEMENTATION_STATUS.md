# Implementation Status — 2026-11-06

Evidence-backed status of the active line only; one entry per landed increment, newest first.
Full history up to 2026-11-06 (XIANXIA60, Dola, V2 qualification, Codex E2E receipts):
[archive/IMPLEMENTATION_STATUS_HISTORY_THRU_20261106.md](archive/IMPLEMENTATION_STATUS_HISTORY_THRU_20261106.md).

Keep technical proof, product proof and Owner acceptance separate. Tests passing never implies footage
is accepted.

## Branch `feature/drama-preprod-p0`

| Date | Commit | Increment | Proof | Owner |
|---|---|---|---|---|
| 11-06 | `76f9913` | Phase P2 (pre-production, categories 35-56): versioned designs + `id@version` pins + `film.py impact`; continuity bible with six kinds (`continuity.py`, causing-action rule, hand-off equality) hooked into `plan` and `film.py continuity`; camera and lighting plan (`camera.py`, only shot size reaches the prompt); timed animatic mp4/srt/timing report (`animatic.py`, 0 credits); budget from the film01-03 KPI ledgers, hand-off schedule, risk register with fallback rule, rights ledger (`planning.py`, shown by `validate`); matrix now HAVE 29 / PARTIAL 89 / GAP 24 / N/A 26 | full suite 1585 passed, 194 skipped, 1 failed: the known `test_dispatch_recovery` F0/F1 (P9-01); film03 prompts still byte-identical (golden); animatic run on film03 = 16 generations, 128.0 s, no findings. Gate PASS = declared rules hold, not Owner acceptance; film03 camera/lighting values, declared size repeats and the pending rights entries were set by the model and await Owner review | n/a |
| 11-06 | `b1d14e2` | Phase P1 (story and direction, categories 1-34): typed `01_story.json` + Gate 1 (beats, arcs, logline, script parity, rights -> OWNER_PENDING), typed `02_direction.json` + Gate 2 (treatment, emotional continuity, reveals, carrier shots, coverage plan), director playbook + `film-director` skill, narration profile adapter over E2E projects (`film.py narration import/status`); film03 Gates 1-2 PASS; matrix now HAVE 22 / PARTIAL 86 / GAP 34 / N/A 26 | 128 production tests; full suite 1476 passed, 194 skipped, 0 failed apart from the known `test_dispatch_recovery` (deselected, P9-01); `test_v2_010a_dola_re_001::test_05_invariants` passes on a clean tree. Gate PASS = declared rules hold, not Owner acceptance; film03 direction values were set by the model from the shipped film | n/a |
| 11-06 | `4054a2e` | Phase P0 (production foundation): `films/<id>/` package schema + loader, `tools/film.py new/validate/status/plan`, film03 ported to `films/film03_front_desk`, generic `plan` stage; coverage of Owner's 168 categories mapped ([CATEGORY_COVERAGE_168.md](../production/CATEGORY_COVERAGE_168.md): HAVE 15 / PARTIAL 78 / GAP 49 / N/A 26) | `plan` reproduces all 16 video prompts, 21 still prompts and the gate3 record of `tools/drama_film03.py` byte-for-byte (golden test); full suite 1444 passed, 194 skipped, 2 failed; one (`test_v2_010a_dola_re_001::test_05_invariants`) only fails on a dirty tree and passes once committed, the other (`test_dispatch_recovery` F0/F1) is a pre-existing environment case — backlog P9-01 | n/a |
| 11-06 | `b16dd1d` | Per-project image profile/tab and Flow account alias (`prepare --image-profile/--image-tab/--flow-account-alias`); defaults keep old lineage | 424 focused tests PASS; real project `e2e_badge_20261104` status readback unchanged (2 selected / 6 pending, DB/plan/meta hashes unchanged) | n/a |
| 11-06 | `80041f9` | pytest finds `src` without `PYTHONPATH` | suites run with plain `python -m pytest` | n/a |
| 11-06 | `4e232c3` | SRT faithful-action gate: `action_meaning` blocks partial sentences, words not in the SRT, choreography without ACTION → REACTION; escalation warnings; QC questions in review template | 420 focused tests PASS | rule is Owner's; code not Owner-reviewed |
| 11-06 | `f375a8d` | Optional drama WP3 choreography in E2E plan v2 (phases must cover 8 s; timing reaches prompt) | 409 focused tests PASS | n/a |
| 11-06 | `07ddebe` | Merge `codex/film-e2e-ship` (E2E CLI, plan v2 direction, Flow provider fixes) | 407 focused tests PASS; only CURRENT_SLICE conflicted | n/a |
| 11-02 | `63eaf57` | film03 "The Front Desk": SRT motif → original script → final | final 139.1 s, −15.3 LUFS, C2PA dev signer, comprehension 0 issues | review pending |
| 11-01 | `ccd8077`…`e44c540` | WP8 comprehension (identity tags, context cards, script lint, tag layout); film02 delivery with EN/VI sidecars | see `docs/drama/film02/README.md` | review pending |
| 11-01 | `dc149d0` | WP7 film02 benchmark: 6/6 first-pass, 1.75 credits per usable s (film01 2.1) | KPI ledger | review pending |
| 11-01 | `f135414`, `d979e16`, `a2f8f4f`, `8f6fef1`, `a6c3345` | WP1b flow_send binding, WP5 start-frame route, WP6 disclosure + C2PA, WP4 autoqc (WARN-only), WP2/WP3, WP1a | focused suites PASS at each commit | n/a |
| 10-31…11-01 | `e700c93`…`ec8c1bb` | Pre-production P0 (Fountain, Gates 1–3), film01 "First Day" | final in `docs/drama/film01_post/` | **accepted** |

## Known gaps

- Full repo pytest last recorded NOT PASS on the mission line (1,223 pass / 133 fail / 62 errors, mostly
  missing git-ignored historical evidence); not re-run on this branch.
- E2E production DB stores absolute paths; projects are not relocatable (delivery packages are).
- WP4 autoqc is WARN-only; `action_meaning` checks declarations, not footage.
- C2PA uses a dev signer; not release-ready.
