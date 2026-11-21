# Muse import provenance (M3 Step 3)

Date: 2026-11-21. Plan: `docs/production/M3_MERGE_PLAN.md` section 2.3 (primary method: filter in a throwaway clone, merge unrelated histories).

## Source

| item | value |
|---|---|
| repository | `D:\Muse` (package `muse_studio`), read-only for this import; no git write was run there |
| tag | `muse-v1.0-r15` (annotated; tag object `1163f905908fc396ecb930da80c7e63d14769aaa`) |
| original commit | `a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1` (a8f2b9c6) |
| tag tree | 2038 files |
| filtered head | `725a7f06eacad4678c85c59b7e6ef768a2d0f8c3` (filtered tag object `93a8168cf7fc3ec6a87f1a09325df983e2171c5f`) |
| imported refs (local only, never pushed) | `refs/imports/muse/muse-v1.0-r15`, `refs/imports/muse/tags/muse-v1.0-r15` |

## Method

`git filter-repo` (PyPI `git-filter-repo`, version `a40bce548d2c`, installed in `C:\m3tmp\fr.venv`) in a fresh clone
`C:\m3tmp\muse_filter` (`git clone --no-local --branch muse-v1.0-r15 D:\Muse`), one run with `--path` keeps, `--path-rename`s and
one `--filename-callback` for the drop classes. Then `git fetch` of the filtered clone into the refs above and
`git merge --allow-unrelated-histories --no-ff --no-commit`, checkpoint-3 scan of the staged result, commit.
The fallback (`git archive` plus script) was not needed.

## Allow-list (kept, original paths)

`muse_studio/` (minus `muse_studio/data/**`), `docs/`, `.claude/skills/muse-director/`, `.claude/hooks/stage_skills.py`,
`.agents/skills/`, `.agents/skills.json`, `.agents/hooks.json`, `CLAUDE.md`, `AGENTS.md`, `PIPELINE_SOT_NATIVE_FILM.md`,
`CRAFT_GAP_BACKLOG.md`, `PIPELINE_AUDIT_20261101.md`, `.gitignore`, `tools/secret_scan.py`, `tools/test_secret_scan.py`,
`tools/secret_scan_allow.txt`, `.claude/launch.json`, `.claude/settings.json`.

## Renames

| from | to |
|---|---|
| `muse_studio/` | `src/muse_studio/` |
| `docs/` | `docs/muse/` |
| `CLAUDE.md` | `docs/muse/MUSE_CLAUDE.md` |
| `AGENTS.md` | `docs/muse/MUSE_AGENTS.md` |
| `PIPELINE_SOT_NATIVE_FILM.md`, `CRAFT_GAP_BACKLOG.md`, `PIPELINE_AUDIT_20261101.md` | `docs/muse/<same name>` |
| `.claude/hooks/stage_skills.py` | `.claude/hooks/stage_skills_muse.py` |
| `.gitignore` | `docs/muse/muse.gitignore.txt` (its secret rules are merged into the root `.gitignore`, marked block) |
| `.claude/launch.json` | `docs/muse/claude/launch.json` (not live config before Step 7) |
| `.claude/settings.json` | `docs/muse/claude/settings.json` (not live config before Step 7) |

`.claude/skills/muse-director/`, `.agents/skills*`, `.agents/hooks.json` and the three `tools/` files keep their paths. File
content is unchanged (moves only); the Muse tools allow globs get the `src/` prefix in Step 4.

## Drops

Everything outside the allow-list (every film folder, root zips, `tools/` other than the three scanner files, and so on), plus
inside it: `muse_studio/data/**` (this includes `muse_studio/data/sample_script.csv`), every path of
`_archive/m3_merge_plan/step2/step3_filter_paths.txt` and `step3_other_nonallowlist_paths.txt`, anything matching `_worktrees`,
`_backups`, `_live_*`, `_director_review_*`, `HANDOFF_*`, `*.zip`, and media (`.mp4 .mov .webm .png .jpg .jpeg .webp .wav .mp3
.m4a`) outside `muse_studio/static/` and `muse_studio/tests/fixtures/`. No media file was inside the allow-list in this tag, so no
media was kept. The B14 fixture is not imported; see `fixtures/muse_b14/MANIFEST.json`.

## Commit map (old to new; the filter-repo file is `_archive/m3_merge_plan/step3/commit-map.txt` in the AFP-stable checkout, untracked)

| original | filtered |
|---|---|
| `b9d6d5caeff1e129a39f7d010626c9cc54485f49` | `6a15ed7b6fef3df76a907429f8ac1f66c7c2182e` |
| `c6070298e3614b640c459dcd7cc5c12a313cacb3` | `97d06d6dee5811e7904e81b28b926789ceba5b5a` |
| `a23f67763c38163078f206ef18615e5ff55f8b6b` | pruned (it only touched dropped media paths) |
| `a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1` | `725a7f06eacad4678c85c59b7e6ef768a2d0f8c3` |

## Scan reports (checkpoints 2 and 3, scanner and allow file from `step2/scanner`)

- Checkpoint 2, filtered clone history: `_archive/m3_merge_plan/scan_muse-v1.0-r15_filtered.md` (exit 0).
- Checkpoint 3, staged merge result: `_archive/m3_merge_plan/scan_muse-v1.0-r15_merge_staged.md` (exit 0).
- Both paths are in the AFP-stable checkout and are untracked there.
