# M3 Step 3 executor brief: import Muse into `studio/m3-merge`

Coordinator: AFP Tech Lead (Opus). Executor: Sonnet, effort high. Plan: `docs/production/M3_MERGE_PLAN.md` §1.2, §2.2
(checkpoints 2-3), §2.3, §6 Step 3 gate (line ~345), §7 Step 3. Read those sections first; this brief only pins the
choices the plan leaves open.

## Inputs (verified by the coordinator before this brief was sent)
- AFP base: `feature/drama-preprod-p0` current tip (freeze code tip ca9d328f; later commits are docs-only).
- Muse source: annotated tag `muse-v1.0-r15` -> a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1 in `D:\Muse`.
- Step 2 outputs: `_archive/m3_merge_plan/step2/` (scanner + README with checkpoint command lines,
  `step3_filter_paths.txt` = media/blob paths to drop, history-scan report, rule-test baseline, B14 custody bundle).

## Do
1. Worktree: `git -C "D:\AI FILM MAKER\AFP-stable" worktree add "D:\AI FILM MAKER\wt-m3-merge" -b studio/m3-merge
   feature/drama-preprod-p0`. All merge work happens there.
2. Fresh throwaway clone **outside both repos** (do not reuse Step 2's `C:\m3tmp\muse_r15`, which holds test dirs):
   `git clone --no-local --branch muse-v1.0-r15 D:\Muse C:\m3tmp\muse_filter`; confirm `git rev-parse HEAD` =
   a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1. Never run a git write command in `D:\Muse`.
3. Filter tool: `git filter-repo` is not installed. Make a venv at `C:\m3tmp\fr.venv`, `pip install
   git-filter-repo` (PyPI, official). If that fails, use the §2.3.4 fallback (`git archive` of the tag + the same
   allow-list/renames by script + one provenance commit) and say so in the report.
4. Filter in the clone (allow-list, §2.3.1), one filter-repo run with `--path` keeps and `--path-rename`s:
   - keep: `muse_studio/` (minus `muse_studio/data/`), `docs/`, `.claude/skills/muse-director/`,
     `.claude/hooks/stage_skills.py`, `.agents/skills/`, `.agents/skills.json`, `.agents/hooks.json`, `CLAUDE.md`,
     `AGENTS.md`, `PIPELINE_SOT_NATIVE_FILM.md`, `CRAFT_GAP_BACKLOG.md`, `PIPELINE_AUDIT_20261101.md`, `.gitignore`,
     plus (coordinator decision after Step 2): `tools/secret_scan.py`, `tools/test_secret_scan.py`,
     `tools/secret_scan_allow.txt` (same paths; AFP has no file there; content untouched, the allow globs get the `src/`
     prefix in Step 4), `.claude/launch.json` and `.claude/settings.json` (renamed, see below; AFP has neither, but they
     must not become live config before Step 7).
     `muse_studio/data/sample_script.csv` is dropped with `muse_studio/data/**` (no code references it).
   - drop additionally: `muse_studio/data/**`, every path in `step3_filter_paths.txt`, anything matching
     `_worktrees`, `_backups`, `_live_*`, `_director_review_*`, `HANDOFF_*`, `*.zip`, media (`*.mp4 *.mov *.webm *.png
     *.jpg *.jpeg *.webp *.wav *.mp3 *.m4a`) unless the path is under `muse_studio/static/` or
     `muse_studio/tests/fixtures/` and < 1 MB (list each kept one).
   - rename: `muse_studio/`->`src/muse_studio/`; `docs/`->`docs/muse/`; `CLAUDE.md`->`docs/muse/MUSE_CLAUDE.md`;
     `AGENTS.md`->`docs/muse/MUSE_AGENTS.md`; `PIPELINE_SOT_NATIVE_FILM.md`, `CRAFT_GAP_BACKLOG.md`,
     `PIPELINE_AUDIT_20261101.md` -> `docs/muse/`; `.claude/hooks/stage_skills.py`->`.claude/hooks/stage_skills_muse.py`;
     `.gitignore`->`docs/muse/muse.gitignore.txt`; `.claude/launch.json`->`docs/muse/claude/launch.json`;
     `.claude/settings.json`->`docs/muse/claude/settings.json`.
   - Save the commit map (`.git/filter-repo/commit-map`) to `_archive/m3_merge_plan/step3/commit-map.txt`.
5. Checkpoint 2 (scanner and exact command lines: `_archive/m3_merge_plan/step2/scanner/README.md`; run from that
   `scanner\` dir with `PYTHONIOENCODING=utf-8` and `--allow secret_scan_allow_step3_renamed.txt`):
   `python secret_scan.py --history C:\m3tmp\muse_filter --allow secret_scan_allow_step3_renamed.txt --out
   "D:\AI FILM MAKER\AFP-stable\_archive\m3_merge_plan\scan_muse-v1.0-r15_filtered.md"`. Exit must be 0 (the 39
   Step 2 hits are all under `step2/step3_filter_paths.txt` and must be gone). Any hit stops here: fix by filtering
   the clone, re-scan; never fetch on a non-zero exit.
6. In the worktree: `git fetch C:\m3tmp\muse_filter +HEAD:refs/imports/muse/muse-v1.0-r15` (also fetch the tag
   rewritten by filter-repo if present, under `refs/imports/muse/tags/`). Never push `refs/imports/*`.
7. `git merge --allow-unrelated-histories --no-ff --no-commit refs/imports/muse/muse-v1.0-r15`.
   - Expect no content conflict. If `.claude/` or `docs/` paths collide with AFP files, stop and report.
   - Root `.gitignore`: AFP version wins; append a clearly marked block with Muse's secret rules (accounts, profiles,
     leases, halt, cookies, `.env*`, `*.sqlite*`, `data/`), rewritten for the new `src/muse_studio/` prefix.
   - Add `docs/muse/IMPORT_PROVENANCE.md`: tag, original commit a8f2b9c6, filtered head, method (filter-repo version or
     fallback), allow-list, renames, drops, path of the commit map, scan report paths, date.
   - Add `fixtures/muse_b14/MANIFEST.json`: `fixture` = `D:\Muse\_director_review_B14_20261119` (read-only; file count,
     total bytes, sha256 of the sorted `relpath\tsize\tsha256` list) and `supplement` = the 4 images the manifest needs
     but the folder lacks (`shot01_after_tag_fadeout.png`, `shot02_after_tag_fadeout.png`, `officer_craig_anchor.png`,
     `todd_wilson_anchor.png`), source `D:\Muse\BLACK_PILOT_EXTENDED_FEATURE_FILM\assets\anchors\` (relpath, size,
     sha256 each; if a name is not there, record `missing` and say so). Compute in Python; print counts only.
8. Checkpoint 3: `python secret_scan.py --staged "D:\AI FILM MAKER\wt-m3-merge" --allow
   secret_scan_allow_step3_renamed.txt --out "D:\AI FILM MAKER\AFP-stable\_archive\m3_merge_plan\scan_muse-v1.0-r15_merge_staged.md"`
   (from the `scanner\` dir). Exit 0 required. Clean -> commit with message
   `merge: import muse_studio at muse-v1.0-r15 (a8f2b9c6) into studio` + provenance lines + the commit trailer below.
9. Gate check (§6 line ~345): script that lists every file in the tag tree (`git -C C:\m3tmp\muse_r15 ls-tree -r
   a8f2b9c6`, Step 2's unfiltered clone) and every imported file, maps each through the renames,
   and asserts: imported blob == tag blob for every kept file (by blob SHA); every tag file not imported is in a named
   drop class. Output `_archive/m3_merge_plan/step3/content_diff.md` (counts per class + any mismatch, which must be 0).
   Also: `git diff --stat feature/drama-preprod-p0 HEAD -- . ':!src/muse_studio' ':!docs/muse' ':!fixtures/muse_b14'
   ':!.claude' ':!.agents'` shows only `.gitignore`.
10. Report: `_archive/m3_merge_plan/step3/STEP3_REPORT.md` (method, counts, scan results, gate result, deviations).

## Do not
- Run any test (importing `config.py` would create a data dir in the tree; §7 Step 3).
- Run any git write in `D:\Muse` or `D:\AI FILM MAKER\AFP-stable` main checkout other than `worktree add`.
- Open `accounts.json*`, `profiles/`, `lane_leases.json*`, `muse_halt.json*`, cookies or any session file; print matched
  secret text; use `git add -A` (stage explicit paths or let the merge stage); push; force anything; stash.
- Edit any imported Muse file content (moves only). Edits start in Step 4.

## Done
Merge commit on `studio/m3-merge` in `wt-m3-merge`; scans 2 and 3 clean; content diff 0 mismatches; AFP files
untouched except `.gitignore`; report written. Reply to the coordinator with: merge SHA, method, kept/dropped counts,
scan results, gate result, any deviation.

Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`
