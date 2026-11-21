# Pre-M3 cleanup report — Muse side (MERGE_INVENTORY rows M10–M13)

Date: 2026-11-21. Read-only inventory: nothing moved, deleted or edited. Recommendations only; the coordinator and the
Owner decide. "Unique" = content not found in `muse_studio/`, `docs/` or `.claude/skills/muse-director/`.
Out of scope, named only: `C:\film-work\BIKER_DEAD_ENGINE_20261120`, `C:\film-work\BLACK_PILOT_P0_20261120`.

Headline: nothing here is pure junk except the scratch scripts, the craft-skills worktree and the idle sessions.
`black-drama-eutlzb7ycky` is **not stale** (11 GB, last written 2026-11-17, holds Owner-approved masters), and the four
`_live_v50_*` / B14 folders are **cited as evidence** by lessons L17–L22, so they need their paths updated before moving.

## M10 — `C:\film-work` stale folders

| Item | What | Last activity | Unique content | Recommendation |
|---|---|---|---|---|
| `black-drama-eutlzb7ycky` (11 GB, 15,562 files) | "The Spare Jacket": adaptation of YouTube source EuTlZB7YCkY (Vale Stories) in 2 parts, expanded to a ~25 min cut. Has `RIGHTS.md`, `PART_MAP.md`, per-part STATUS, 178 received clips + QC JSON, `part02/review/THE_SPARE_JACKET_PART02_FINAL.mp4`, `full_review/THE_SPARE_JACKET_FULL.mp4` (9:08 approved cut). | 2026-11-17 | Everything. `docs/` and lessons have no mention of it. Rights basis is Owner's word (license=null at source), publishing was never granted. The 25:10 final named in the audit (`expanded_27min/THE_SPARE_JACKET_FINAL_25MIN.mp4`) is **not in the folder**; Part 1 NO_LABEL master is outside it at `D:\film-work\eutlzb7ycky-part01-finishing\...`. | **KEEP the folder as is** (final masters, publishing is Owner-reserved). **HARVEST** the 4 text files below. Cold-archive of `expanded_27min/` (7 GB) only after the Owner confirms the final is stored elsewhere. |
| `muse-gateway-20261112` (52 MB, 107 files) | Early Muse gateway probe: one-shot payload, raw receipt, dialogue ASR check, `film06_probe/` (story/direction/shots JSON). `LOOP_BACKLOG.md` = "OWNER_GO_LIVE: NO". | 2026-11-12 | Only receipts of the first probe; superseded by the lane contract and `pool_runner`. | **ARCHIVE** |
| `muse-pilot-3m-20261112` (1.3 GB, 580 files) | "Six A.M." 3-minute pilot: `film/` (7 stage JSONs + fountain script), 14-shot preview and 3-min review MP4 with `.qc.json`, ad-hoc ASR/crop/receive scripts. `LOOP_BACKLOG.md` = "OWNER_GO_LIVE: NO". | 2026-11-13 | Review MP4s (734 MB) + the film JSONs. Scripts are one-off. No lesson cites it. | **ARCHIVE** whole folder (cold storage). Keep nothing in the repo. |
| `muse-shot7-support-draft.txt` (1.6 KB) | Draft support ticket: Muse refused `eutlzb7ycky_p1_kitchen / SC01_g7` with `integrity_check_failed` although the prompt is benign. Holds request ID and SHA-256 values. | 2026-11-14 | The incident text (a false-positive refusal on a benign shot). Not in lessons. | **HARVEST** into `lessons.md` as one row (defect: benign shot refused `integrity_check_failed`; stage: 3 generability / 4 send; check: log request id + prompt hash, change the input instead of retrying), then **ARCHIVE** the file. |

## M11 — `D:\Muse\_worktrees`

| Item | What | Last activity | Unique content | Recommendation |
|---|---|---|---|---|
| `craft-skills` (branch `docs/craft-skills`, clean, 1 commit `c607029`) | The first version of `CLAUDE.md`, the `muse-director` skill (5 files) and `CRAFT_GAP_BACKLOG.md`. | 2026-11-19 | None. `CRAFT_GAP_BACKLOG.md` is byte-identical to the one in `D:\Muse`; the other 6 files in `D:\Muse` are newer and longer (`CLAUDE.md` 73 vs 46 lines, `commands.md` 165 vs 61, `lessons.md` 67 vs 59). | **ARCHIVE.** Remove the worktree, then the branch, once the `D:\Muse` copies are committed (they are still untracked). Do not remove before that commit. |
| `pilot-60s-zero-defect` (branch `feature/pilot-60s-zero-defect`, HEAD `a23f677` 2026-11-02) | "P60": 60 s zero-defect master for the Marcus pipeline. Commit adds 34 files under `MARCUS_PIPELINE_20261101/P60/` (+976 lines): `P60_v2_1080p.mp4`, `P60_v2_704p.mp4`, `P60_v2.srt`, `p60_edl_v2.json`, `FINAL_60S_ACCEPTANCE_REPORT.md`, `DIRECTING_PRINCIPLES.md`, `DIRECTOR_PLAN_P60.md`, QC and assemble scripts. | 2026-11-02 | **The whole commit.** `main` has `MARCUS_PIPELINE_20261101/` (P1, P2, `ERROR_CATALOG.md`) but no `P60/`. `lessons.md` takes only `ERROR_CATALOG.md`. | **HARVEST, then keep the branch** (do not delete the branch until the files are copied): masters + EDL + the two reports + `DIRECTING_PRINCIPLES.md`. Then archive the worktree directory. |
| — dirty part of `pilot-60s-zero-defect` | 49 files, **all untracked** (`??`, 0 modified, 0 staged; `git diff --stat` is empty). ~45 are CDP/Playwright one-offs against the Muse and ChatGPT web UIs (`check_cdp.py`, `ask_muse_generate.py`, `upload_to_muse.py`, `read_gpt*.py`, `get_muse_reply*.py`, `track_s9_*.py`, `eval_draw_motion.py`), plus `clips/P60_S9_draw.mp4`, `clips/P60_S9_muse_new.mp4` (24 MB) and `debug_33_34/`, `debug_draw/`, `debug_s9/` (≈5 MB). Work is the S9 "two officers oscillate left-right" fix. | 2026-11-02 | None of these scripts exist in `muse_studio` (they scrape the web UI; the pool runner replaced that path). The S9 motion defect is the same class as L13 (camera/action drift). | **ARCHIVE** the 49 files (disposable). Optional: keep `track_s9_motion.py` and `eval_draw_motion.py` only if the prop-motion check in L18/L20 is ever built. |

## M12 — `D:\Muse` loose folders and scratch

| Item | What | Last activity | Unique content | Recommendation |
|---|---|---|---|---|
| `HANDOFF_CLAUDE_MUSE_20261119.md` (18 KB) | Handoff of the B14 verification session. It said "implementation not started" on 2026-11-19. The agreed work (T0 normalise to 1280×720, compile defaults) has since landed: `lessons.md` L22 cites `normalize_first_frame`, and `CRAFT_GAP_BACKLOG.md` holds the remaining gaps. | 2026-11-19 | Section 2 lists reads outside the repo (`C:\Users\ADMIN\Documents\Nghiên cứu\Video\Kiểm chứng muse\Bao-cao-tong-hop-kiem-chung-Muse-FINAL.md`) — the pointers are the only unique part. | **ARCHIVE** after one line in `docs/` keeping that source-report path. |
| `_director_review_B14_20261119\` (227 MB, 318 files) | Scene B14 review runs: staging proposals R1–R3, `IMPROVEMENTS_FROM_MUSE_VERIFICATION_20261119.md`, step_09…step_15 live runs (T0 control `step_15_t0_normalized`). | 2026-11-19 21:07 | `IMPROVEMENTS_…md` (PSNR table, the T0 case) and `step_15_t0_normalized` are the evidence for **L22**; Pamela/Todd redesign notes are story-level, not in lessons. | **HARVEST** (below), then **ARCHIVE** the rest. Update the L22 path in `lessons.md` when moved. |
| `_live_v50_20261118\` (31 MB) | First live v5.0 run: 3 batches / 5 images; REPORT, events.jsonl, assets. | 2026-11-18 | `REPORT.md` is cited by **L17**. | **HARVEST** `REPORT.md`; archive the rest. |
| `_live_v50_macro_retest_20261118\` (8 MB) | Macro keyframe re-test (skin tone, finger gap). `macro_before_after.jpg`. | 2026-11-18 | `REPORT.md` + before/after sheet = fix proof for L17. | **HARVEST** `REPORT.md`, `macro_before_after.jpg`; archive the rest. |
| `_live_v50_macro_video_20261118\` (25 MB) | Macro video: continuity FAIL (background jump 1.88→1.92 s, key lifts). | 2026-11-18 | `REPORT.md` is cited by **L18** and SOT line 99. | **HARVEST** `REPORT.md`, `continuity_evidence.jpg`; archive the rest (`macro_live.mp4` optional). |
| `_live_v50_macro_short_video_20261118\` (41 MB) | 59-word prompt returned 10.00 s at 1248×704 for a 5 s ask. | 2026-11-18 | `REPORT.md` is cited by **L20** and SOT line 100. | **HARVEST** `REPORT.md`, `macro_ab_contact_sheet.jpg`; archive the rest. |
| `_archive_scripts\` (64 files, 1.1 MB, untracked) | Where the `scratch_*` files landed, plus older CDP and port probes (`check_cdp.py`, `check_pool1_*`, `dispatch_single_batch.py`, `download_batch_0*.py`, `verify_batch_0*.py`, screenshots, `test_err.mp3`). Nothing refers to it. | 2026-11-18 | None; it is superseded by `pool_runner`, `lane`, `qc-audit`. | **ARCHIVE** (disposable). |
| 31 staged deletions (`git status --short`): 30 `scratch_*` + `stage_proxy.svg` (≈743 KB, tracked in baseline `b9d6d5c`) | Ad-hoc inspection scripts for Flow/Muse tiles, credits, topbar, RCNN test, plus `scratch_tile_click.png` and `scratch_top_right.png`. | 2026-11-18 | None; their copies are in `_archive_scripts`. | **Disposable.** Safe to commit the deletions (stage by explicit path) after `r15-finish` is done. |

## M13 — idle sessions with cwd `D:\Muse` (read last 3–4 events only)

| Session | What | Last activity | Unique content | Recommendation |
|---|---|---|---|---|
| `local_04a27087` "Antigravity autonomous lane setup" (agy-setup) | Wrote lane docs (`.agents/skills/muse-filmmaker`, `AGENTS.md`, `commands.md`). Last turn: `--takes` docs aligned to code, verified against `pool_runner.py`; lists open † items (`--no-srt-gate`, `LANE_ID_IN_USE`, …) as unverified. | 2026-11-20 09:18 | The † list is a to-do; docs themselves are in the tree. | **ARCHIVE.** Copy the † items into `CRAFT_GAP_BACKLOG.md` first if they are still wanted. |
| `local_3af0d00b` "Lane account leases" (lane-leases, state failed) | Built `muse_studio/lane.py` lease + pool changes. Stopped at the 5-hour limit with the `--takes` request pending; `pool_runner.py:126` now has `--takes`, so it was done later. | 2026-11-20 08:53 | None found. | **ARCHIVE.** |
| `local_dc86a1a2` "P0 baseline prep (no send)" (p0-black-pilot, failed) | Died at the limit right after loading the director skill (7 messages). Replaced by `local_c688e8bc` p0-prep (same title, 2026-11-20 18:03, also failed). | 2026-11-20 15:27 | None. | **ARCHIVE** both p0 sessions (c688e8bc is outside your list; same reason). |
| `local_f56b6f23` "Muse: CLAUDE.md + muse-director skill" | **Not inspected**: `get_session` returns "not found" for that short id, and the list tool does not show it. Another session's listing put its last activity at ~2026-11-19 21:24. Its output is the CLAUDE.md/skill that already sit in `D:\Muse`. | ~2026-11-19 | Unknown. | **ARCHIVE** (low risk, output verified in tree); look it up in the sidebar by title first if you want to be sure. |
| `local_3a840c58` "Fix Codex r6" (fix-codex-r6-takes-lease, failed) | 902 messages. Died at the limit with the second live defect pending (unique batch ids per run; loose `_find_attachment_card` fallback). `keyframe_composer.py:616` now has `run_token` (L38), but `_find_attachment_card` (`headless_muse_client.py:249`) was not re-checked and video batch ids were not checked. | 2026-11-21 03:09 | Open fix list = those two items. | **ARCHIVE only after `r15-finish` confirms its fixes A/B/C cover (1) video batch ids and (2) the card fallback.** Until then **KEEP**. |

## Harvest list (exact paths to keep)

| Path | Goes to |
|---|---|
| `C:\film-work\black-drama-eutlzb7ycky\RIGHTS.md` | `docs/` (rights basis and scope) or the film's own folder in Film Studio |
| `C:\film-work\black-drama-eutlzb7ycky\PART_MAP.md` | same |
| `C:\film-work\black-drama-eutlzb7ycky\expanded_27min\STATUS.md` | same |
| `C:\film-work\black-drama-eutlzb7ycky\expanded_27min\MUSE_WORKFLOW_AUDIT_20261117.md` (timings: 198 sends, 178 clips, 20 refusals; median 78.75 s per clip) | `docs/` as a pipeline benchmark; feeds CRAFT_GAP G5 |
| `C:\film-work\muse-shot7-support-draft.txt` | one `lessons.md` row, then archive |
| `D:\Muse\_worktrees\pilot-60s-zero-defect\MARCUS_PIPELINE_20261101\P60\` : `P60_v2_1080p.mp4`, `P60_v2_704p.mp4`, `P60_v2.srt`, `p60_edl_v2.json`, `FINAL_60S_ACCEPTANCE_REPORT.md`, `DIRECTING_PRINCIPLES.md`, `DIRECTOR_PLAN_P60.md` (or keep branch `feature/pilot-60s-zero-defect`) | main repo `MARCUS_PIPELINE_20261101/P60/` |
| `D:\Muse\_director_review_B14_20261119\IMPROVEMENTS_FROM_MUSE_VERIFICATION_20261119.md`, `step_15_t0_normalized\` | evidence for L22 → `docs/evidence/B14/` |
| `D:\Muse\_live_v50_20261118\REPORT.md`, `_live_v50_macro_retest_20261118\REPORT.md` + `macro_before_after.jpg`, `_live_v50_macro_video_20261118\REPORT.md` + `continuity_evidence.jpg`, `_live_v50_macro_short_video_20261118\REPORT.md` + `macro_ab_contact_sheet.jpg` | `docs/evidence/v50/` (L17, L18, L20); then fix the four paths in `lessons.md` and SOT lines 97–100 |
| Path to `C:\Users\ADMIN\Documents\Nghiên cứu\Video\Kiểm chứng muse\Bao-cao-tong-hop-kiem-chung-Muse-FINAL.md` (from the handoff) | one line in `docs/` |

## Order and caveats

1. Do not touch `muse_studio/` or anything `r15-finish` is editing; commit the scratch deletions only after it ends.
2. Commit `CLAUDE.md`, `.claude/`, `AGENTS.md`, `CRAFT_GAP_BACKLOG.md` (untracked now) **before** removing the `craft-skills` worktree.
3. Harvest first, then update the evidence paths in `lessons.md`, then archive; otherwise L17–L22 point at nothing.
4. The `eutlzb7ycky` rights basis is Owner's word only; keep `RIGHTS.md` with whatever copy of the film survives.
5. Sizes: M10 ≈ 12.4 GB, M12 ≈ 335 MB, `pilot-60s` P60 ≈ 142 MB.
