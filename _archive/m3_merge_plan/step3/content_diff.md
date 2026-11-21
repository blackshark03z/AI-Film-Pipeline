# Step 3 content diff gate: Muse tag tree vs imported tree

Tag tree: `a8f2b9c6` (clone `C:\m3tmp\muse_r15`), 2038 files. Imported tree: `HEAD^2` (filtered head) and `HEAD` of `studio/m3-merge`.

## Counts per class

| class | files |
|---|---:|
| kept | 116 |
| drop: film folder / zip from step3_filter_paths.txt | 1724 |
| drop: film/work folder from step3_other_nonallowlist_paths.txt | 197 |
| drop: muse_studio/data/** | 1 |
| **total** | 2038 |

Kept: 116, dropped: 1922 (sum 2038). Files in `HEAD^2` tree: 116.

## Checks

- Kept file: imported blob SHA == tag blob SHA at the mapped path, in HEAD^2 and in HEAD (mode also equal): 116 checked.
- Every tag file not imported is in a named drop class (table above); none of them appears in the import.
- Every imported file traces back to a kept tag file (no extras).
- Muse tools files collide with AFP paths: none.
- AFP first-parent paths with changed blob (excluding `.gitignore`): 0; removed: 0.

## Mismatches: 0


## AFP side

`git diff --stat feature/drama-preprod-p0 HEAD -- . :!src/muse_studio :!docs/muse :!fixtures/muse_b14 :!.claude :!.agents`:

```
.gitignore                  |  30 ++
 tools/secret_scan.py        | 678 +++++++++++++++++++++++++++++++++++++
 tools/secret_scan_allow.txt |   7 +
 tools/test_secret_scan.py   | 791 ++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 1506 insertions(+)
```

The three `tools/secret_scan*` files are also new (no AFP file there) and are listed by the brief as kept at the same paths.

Dropped class examples (one per class):

- drop: film folder / zip from step3_filter_paths.txt: e.g. `DEMO_PATRICE_30S_20261030/AUDIO_EDIT.json`
- drop: film/work folder from step3_other_nonallowlist_paths.txt: e.g. `DRY_RUN_OUTPUT/LOGS/contract_blocked_DRY_RUN_SH01.png`
- drop: muse_studio/data/**: e.g. `muse_studio/data/sample_script.csv`
