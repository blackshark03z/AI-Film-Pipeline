# Muse secret scanner: handoff to the AFP Tech Lead (M3 plan §2.2, Step 2)

Source: `D:\Muse` tag `muse-v1.0-r15` (commit `a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1`), copied byte-for-byte
from the throwaway clone `C:\m3tmp\muse_r15\tools\` (verified with `cmp`). Standard library only, Python 3.11.

## Files and SHA256

| file | sha256 |
|---|---|
| `secret_scan.py` | `7e1b4e169ef441e71eeb4c8e906951c7b7104dd3c983393309a3fc6a35405a91` |
| `test_secret_scan.py` | `f54fdce49e149c2c27c2a3a08a01316db82507108e7b4e5b229f6e52845db0c9` |
| `secret_scan_allow.txt` | `19a1cc21352f3f75a0cc38fbb07b2d1b292cd87901b39012a326a3c07e02550f` |
| `secret_scan_allow_step3_renamed.txt` (derived, see below) | `6d825ef81987172973239ff3e6a1324deecc8173fafaab0f29a1d277a644dc3f` |

`test_secret_scan.py`: 143 passed in the clone (`python -m pytest tools/test_secret_scan.py -q`, about 100 s).

## Usage

```
python secret_scan.py (--staged REPO | --history REPO | --tree DIR) [--max-mb 5] [--out report.md] [--allow FILE]
```

- `--staged REPO`: the index of a repo (the staged blobs, `git diff --cached` semantics).
- `--history REPO`: every blob of every commit reachable from any ref of that repo, one scan per distinct blob.
- `--tree DIR`: plain files under a folder.
- `--max-mb`: size limit for a blob or media file (default 5).
- `--out`: markdown report (path, commit, rule, line; never the matched text). There is no JSON mode.
- The scanner only reads; it prints no matched text anywhere. Run with `PYTHONIOENCODING=utf-8` on a Windows console.

## Exit codes

0 = clean, 1 = hits (not in the allow list), 2 = error (bad arguments, unreadable allow file, git failure).

## Allow-file format

One entry per line: `path|rule|reason`. `path` is an **fnmatch glob** over the repo-relative path (`*` also matches `/`),
`rule` is an exact rule name or `*`, `reason` is required and must not look like credential text. An allowed hit is
listed in the report with its reason and does not count towards the exit code. Entries match path and rule, not line
numbers, so a new hit of an allowed rule in an allowed file is also allowed.

The shipped `secret_scan_allow.txt` has 7 entries, all `content-*` rules on dummy test fixtures and UI placeholder text
under `muse_studio/`. **After the Step 3 rename (`muse_studio/` becomes `src/muse_studio/`) those globs no longer match.**
`secret_scan_allow_step3_renamed.txt` is the same file with the `src/` prefix, generated with
`sed 's#^muse_studio/#src/muse_studio/#'`; use it for checkpoints 2 and 3 (and review it once, as the reasons are
Muse TL's).

## Checkpoint command lines (plan §2.2 items 4 and 5)

Run from a directory that holds `secret_scan.py` (here: `D:\AI FILM MAKER\AFP-stable\_archive\m3_merge_plan\step2\scanner`),
with `PYTHONIOENCODING=utf-8`. Replace `<TAG>` with `muse-v1.0-r15`.

Checkpoint 2, filtered export, before anything is fetched into AFP (every reachable blob of the filtered clone;
fetch only on exit 0):

```
python secret_scan.py --history <FILTERED_CLONE> --allow secret_scan_allow_step3_renamed.txt --out "D:\AI FILM MAKER\AFP-stable\_archive\m3_merge_plan\scan_<TAG>_filtered.md"
```

Checkpoint 3, merge result, after `git merge --allow-unrelated-histories --no-ff --no-commit refs/imports/muse/<TAG>`
and before the commit (commit only on exit 0):

```
python secret_scan.py --staged <MERGE_WORKTREE> --allow secret_scan_allow_step3_renamed.txt --out "D:\AI FILM MAKER\AFP-stable\_archive\m3_merge_plan\scan_<TAG>_merge_staged.md"
```

Checkpoint 1 (already done, see `..\scan_muse-v1.0-r15.md`):

```
python tools/secret_scan.py --history . --allow tools/secret_scan_allow.txt --out <report.md>
```
(run in `C:\m3tmp\muse_r15`; exit 1 with 39 hits, all classified expected, see `..\hits_classified.md`).

For checkpoint 2 the 39 hits must be gone: the filter drops every path in `..\step3_filter_paths.txt`. If checkpoint 2
reports anything, do not fetch; fix by filtering in the clone, not by a later delete.
Also run `--history` again on every runtime tag (plan §2.2 item 6).
