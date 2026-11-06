# Implementation Status — 2026-11-06

Evidence-backed status of the active line only; one entry per landed increment, newest first.
Full history up to 2026-11-06 (XIANXIA60, Dola, V2 qualification, Codex E2E receipts):
[archive/IMPLEMENTATION_STATUS_HISTORY_THRU_20261106.md](archive/IMPLEMENTATION_STATUS_HISTORY_THRU_20261106.md).

Keep technical proof, product proof and Owner acceptance separate. Tests passing never implies footage
is accepted.

## Branch `feature/drama-preprod-p0`

| Date | Commit | Increment | Proof | Owner |
|---|---|---|---|---|
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
