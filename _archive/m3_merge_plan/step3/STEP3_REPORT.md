# M3 Step 3 report: Muse imported into `studio/m3-merge`

Date: 2026-11-21. Executor: Sonnet. Merge commit: `d3ad4700609942f562fae8501dc01907d3554883` on `studio/m3-merge` in `D:\AI FILM MAKER\wt-m3-merge`
(parents: `e9213b53` AFP, `725a7f06` filtered Muse head). Nothing pushed.

## Method

- Worktree: `git worktree add "D:\AI FILM MAKER\wt-m3-merge" -b studio/m3-merge feature/drama-preprod-p0` (base `e9213b53`). Only git write in AFP-stable.
- Fresh clone `C:\m3tmp\muse_filter` (`--no-local --branch muse-v1.0-r15 D:\Muse`), HEAD = `a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1` (confirmed).
- Filter tool: `git-filter-repo` from PyPI, version `a40bce548d2c`, venv `C:\m3tmp\fr.venv`. Primary method; the fallback was not used.
- One filter-repo run: 17 `--path` keeps, 11 `--path-rename`s (docs/ first, so later moves into `docs/muse/` do not chain), plus one `--filename-callback`
  (`C:\m3tmp\filename_cb.py`) for the drop classes (`muse_studio/data/**`, step-2 path lists, name patterns, zips, media outside static/fixtures).
- Result: 4 commits became 3 (`a23f677`, media only, pruned). Commit map: `step3\commit-map.txt`.
- Fetched `+HEAD` to `refs/imports/muse/muse-v1.0-r15` and the rewritten tag to `refs/imports/muse/tags/muse-v1.0-r15`; merged with
  `--allow-unrelated-histories --no-ff --no-commit`; no conflicts, no path collision with AFP.

## Counts

- Tag tree: 2038 files. Kept (imported): **116**. Dropped: **1922** (1724 film folders and zip from `step3_filter_paths.txt`, 197 from
  `step3_other_nonallowlist_paths.txt`, 1 `muse_studio/data/sample_script.csv`; 0 other).
- Kept by area: `src/muse_studio` 86, `docs/muse` 12, `.agents` 9, `.claude` 6, `tools` 3.
- No media file lies inside the allow-list in this tag, so no kept-media list exists (rule 1 MB under `static/` and `tests/fixtures/` never applied).
- Merge commit adds 119 files: 116 imported plus `docs/muse/IMPORT_PROVENANCE.md`, `fixtures/muse_b14/MANIFEST.json`, and `.gitignore` modified.

## Scans (scanner and `secret_scan_allow_step3_renamed.txt` from `step2\scanner`, `PYTHONIOENCODING=utf-8`)

| checkpoint | scope | exit | result | report |
|---|---|---:|---|---|
| 2 | filtered clone, all reachable blobs | 0 | 0 hits, 17 allowed, 127 file entries, 123 blobs, 3 commits | `_archive\m3_merge_plan\scan_muse-v1.0-r15_filtered.md` |
| 3 | staged merge result in `wt-m3-merge` | 0 | 0 hits, 17 allowed, 119 files | `_archive\m3_merge_plan\scan_muse-v1.0-r15_merge_staged.md` |

The 39 Step 2 hits are gone. The 17 allowed hits are the same pre-existing allow-list matches as in Step 2.

## Gate (plan section 6)

`step3\content_diff.md`, script `C:\m3tmp\gate.py` (independent mapping, compares blob SHA and mode against `HEAD^2` and `HEAD`):
**0 mismatches**; 116 kept files identical to the tag blobs at their mapped paths; every dropped file is in a named class and absent from the import;
no imported file without a kept tag source; 0 AFP first-parent paths changed or removed (excluding `.gitignore`).
`git diff --stat feature/drama-preprod-p0 HEAD` with the brief's pathspec shows `.gitignore` (+30) and the three `tools/secret_scan*` files (new, +1476).
The brief's pathspec did not exclude `tools/`, but the coordinator decision adds those three files, so this is expected (see deviations).

## Added files (not Muse content)

- `.gitignore`: AFP content unchanged; appended a marked block (`BEGIN/END Muse secret and runtime-state rules`) with Muse's secret rules under the
  `src/muse_studio/data/` prefix, plus root `accounts.json*`, `lane_leases.json*`, `muse_halt.json*`, `.env`, `.env.*`, `*.sqlite*`, cookies, session files,
  `_worktrees/`, `_backups/`, `_live_*/`, `_director_review_*/`. `git ls-files -ci` shows only pre-existing AFP ignores, none caused by the block.
  Note: file uses CRLF; the block was written with CRLF.
- `docs/muse/IMPORT_PROVENANCE.md`.
- `fixtures/muse_b14/MANIFEST.json`: fixture `D:\Muse\_director_review_B14_20261119`, 318 files, 236,738,764 bytes, sha256 of the sorted
  `relpath\tsize\tsha256` list (LF-terminated, forward slashes); supplement of 4 images from `BLACK_PILOT_EXTENDED_FEATURE_FILM\assets\anchors\` (all 4 present,
  none `missing`); sha256 values copied from `step2\b14_custody\full\supplement_images.sha256` and cross-checked against my own hash of the anchors source (0 differences);
  plus the coordinator's later fields `layout`, `run`, `baseline` (19/21 pass, exit 1, INCOMPLETE; S08 empty `first_frame_path` also fails S07).

## Deviations from the brief

1. `--filename-callback` is used for the drop classes next to `--path` and `--path-rename`: filter-repo cannot exclude a subpath inside a `--path` keep in one run
   otherwise. It sees the renamed names (renames run first). Still one run.
2. Rename order matters in filter-repo (rules apply in sequence on the already-renamed path); `docs/` is renamed before the root `.md` moves.
3. Git Bash rewrote `old:new` arguments; the run needed `MSYS2_ARG_CONV_EXCL='*'` (the first attempt exited 1 before touching anything).
4. The first `git fetch` of `+HEAD` auto-followed the filtered tag and created a local tag `muse-v1.0-r15` in the shared AFP repo. I deleted it at once
   (`git tag -d`, it pointed at the filtered tag object `93a8168c`); the tag now exists only as `refs/imports/muse/tags/muse-v1.0-r15`.
5. Gate diff pathspec: `.gitignore` plus the three `tools/secret_scan*` files appear, not only `.gitignore` (coordinator-approved additions).
6. Manifest fields `layout`, `run`, `baseline` added per the coordinator's mid-task message.
7. The IMPORT_PROVENANCE commit-map table lists 4 old-to-new lines; the filter-repo file reports `a23f677` as all-zero (pruned).

## Observations (not acted on)

- `D:\Muse` shows `M .claude/skills/muse-director/references/lessons.md` and `?? HANDOFF_...md` in its working tree; I did not touch `D:\Muse`.
  The import is from the tag, so that modification is not in it.
- The `step2\scanner` copy was used as is; the allow globs in the imported `tools/secret_scan_allow.txt` still have no `src/` prefix (Step 4).
- No tests were run. Temporary files stay in `C:\m3tmp` (`muse_filter`, `fr.venv`, `filename_cb.py`, `gate.py`, `b14_manifest.py`, logs).
