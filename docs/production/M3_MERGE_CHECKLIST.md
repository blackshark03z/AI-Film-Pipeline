# M3 merge checklist: Steps 1-3 (freeze, source scan, import)

Plan: `docs/production/M3_MERGE_PLAN.md` §7, Gate 0 and Step 1. Every line is verified by reading the repo or the
file named, not by a session report. Status: **SIGNED 2026-11-21** by the coordinator. Step 2 may start.

## AFP (`D:\AI FILM MAKER\AFP-stable`, branch `feature/drama-preprod-p0`)

| Item | Evidence | State |
|---|---|---|
| A1 S1 addendum | commits 6e606905, cfb29744, c962414e, c101a974; coordinator ACCEPT (Codex unavailable for R10) | done |
| A2 S2-lite | `feature/s2-lite` c49b0866 merged as ca9d328f; Codex r2 REJECT, 4 High fixed; 65/65 tests | done |
| A5 push | origin pushes delegated to the agent (OWNER_POLICY 89c2b78c) | done |
| A8 harvest | `_archive/merge_triage/` patches | done |
| A9 old worktrees | Owner decision (fate); not blocking the merge, nothing imported from them | open, non-blocking |
| A10 branch triage | 28 tagged `archive/<branch>` | done |
| AFP full suite on the freeze tip | `pytest -q -x` on ca9d328f: 2799 passed, 204 skipped, 0 failed (52 min) | done |
| `git status` clean (only `uv.lock`, `MUSE_CONSOLIDATION.md` untracked, both never committed) | checked at ca9d328f | done |
| Freeze tip SHA | ca9d328f (code); later docs-only commits are integrated in Step 8 | candidate |

## Muse (`D:\Muse`)

| Item | Evidence | State |
|---|---|---|
| M1 r15 stop-all (fixes a-c), r15b/c/d review | in a8f2b9c; Codex r3 (final) CHANGES_REQUIRED, last 2 High + MED 7 fixed with fail-before tests (`test_r15d_fixes.py`), Muse coordinator review, no round 4 by rule; `docs/R15B_FIX_REPORT.md` | done |
| M2 PRE-TAG #11 (no `src.unlink()`) | in a8f2b9c, `muse_studio/tests/test_m2_never_delete.py` present | done |
| M3 accounts lock | in a8f2b9c, `muse_studio/tests/test_m3_accounts_lock.py` present; Muse suite 351 passed | done |
| M6 git baseline, checkpoint-0 scan clean | a8f2b9c, 147 paths by explicit path; `--staged` 0 hits; `--history` 39 media/blob hits from b9d6d5c, 0 credential/cookie/email; tracked file names checked (no accounts/halt/lease data/cookie/.env/profiles); `accounts.json` ignored | done (media in history handled by the Step 3 filter) |
| M7 tag `muse-v1.0-r15`, SHA, = commit of the P0 hash list | annotated tag -> a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1. Deviation (coordinator): P0 ran on pre-r15b code (hash fbbcfef34485ce01), so the tag is not the P0 commit. Accepted: P0 is a quality reference for stages 2-2.5 only; code parity is judged against the Step 2 baseline made on the tag | done |
| M8 P0 PARTIAL final, 4 anchors held (`P0_HELD_CHILDREN.json`) | Muse TL report 2026-11-21; ledger 0 UNCONFIRMED | done |
| M9 BIKER stopped, no live lease | leases expired 2026-11-20T16:14Z with dead PIDs (Muse TL); coordinator: 0 python processes with muse_studio/pool_runner/lane in the command line | done |
| M10-M13 housekeeping decided | `D:\Muse\docs\PRE_M3_CLEANUP_REPORT.md`: harvest then archive by move, never delete, after Step 2; 7 GB cold archive and session archiving stay with the Owner | decided |
| `git status` clean; no live lane process or lease | only `?? HANDOFF_CLAUDE_MUSE_20261119.md` (M12, untracked, not imported) | done |

## Sign-off

- Coordinator (Techlead, Opus), 2026-11-21: Gate 0 met. AFP freeze tip ca9d328f, Muse tag `muse-v1.0-r15` = a8f2b9c6. Open, non-blocking: A9 (Owner), deferred scanner MED 8/9 -> Step 4 backlog.

## Step 2: source-history scan and baseline (coordinator-verified 2026-11-21)

| Item | Evidence | State |
|---|---|---|
| Checkpoint-1 history scan of the tag | `_archive/m3_merge_plan/step2/scan_muse-v1.0-r15.md`: 39 hits (35 large media, 3 flac blobs, 1 path-backup), 17 allowed, 0 unexplained; all hit paths listed in `step3_filter_paths.txt` | done |
| Rule-test baseline on the tag | `step2/rule_tests_passfail.txt`: 130 passed; `test_secret_scan` 143 passed | done |
| B14 baseline | `step2/b14_custody/full/README.md`: fixture B14 + 4 anchor images in the fixture root, cwd = fixture; 19/21, exit 1 INCOMPLETE; S08 empty `first_frame_path` fails its batch (S07 with it) | done (defect -> Step 4 backlog, new tag per plan §8) |

## Step 3: import with history (coordinator-verified 2026-11-21)

| Item | Evidence | State |
|---|---|---|
| Merge commit | `studio/m3-merge` d3ad4700 = merge of AFP e9213b53 and filtered Muse head 725a7f06 (`refs/imports/muse/muse-v1.0-r15`, local only) | done |
| Method | git-filter-repo a40bce548d2c, one run, allow-list + renames; `step3/STEP3_REPORT.md`, `step3/commit-map.txt` | done |
| Counts | tag 2038 files: 116 kept (src/muse_studio 86, docs/muse 12, .agents 9, .claude 6, tools 3), 1922 dropped in named classes | done |
| Checkpoint 2 (filtered history) | `scan_muse-v1.0-r15_filtered.md`: CLEAN, 0 hits, 17 allowed | done |
| Checkpoint 3 (staged merge) | `scan_muse-v1.0-r15_merge_staged.md`: CLEAN, 0 hits, 17 allowed | done |
| Content-diff gate | `step3/content_diff.md`: 0 mismatches; AFP paths changed: `.gitignore` (+Muse secret block) and the 3 approved `tools/secret_scan*` files; `.claude`/`.agents` additions only | done |
| `.gitignore` side effects | tracked-but-ignored files: 47 before and after the merge, identical sets | done |
| B14 fixture manifest | `fixtures/muse_b14/MANIFEST.json`: 318 files, sha256 of file list, 4 supplement images, run conditions, baseline ref | done |

Coordinator, 2026-11-21: Step 3 gate met. Next: Step 4 (MUSE_DATA_DIR edits, `film_studio` skeleton, allow-glob `src/` prefix).
B14 custody media (`*.mp4`, handoff `*.zip`) stays local under `_archive/m3_merge_plan/step2/b14_custody/full/`, hashed in its README files, not committed.
