# B14 full baseline (Step 4+ regression reference)

Date 2026-11-21. Code: throwaway clone `C:\m3tmp\muse_r15` at tag `muse-v1.0-r15` (`a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1`).

## Fixture
`D:\Muse\_director_review_B14_20261119` copied whole to `C:\m3tmp\b14_plus`, plus 4 supplement images copied
read-only from `D:\Muse\BLACK_PILOT_EXTENDED_FEATURE_FILM\assets\anchors\` into the fixture root
(SHA256 in `supplement_images.sha256`). Fixture decision: AFP TL, 2026-11-21.

## Command
cwd **must be the fixture dir**: `shots_manifest.json` stores `first_frame_path` / `anchor_ref` as bare file names,
resolved against the process cwd (`Path(name)`), not against the project dir. Run from the clone root (as the
`primary_as_is` run did) and every batch fails `BATCH_ERROR` (file not found), with or without the images.

```
cd C:\m3tmp\b14_plus
set PYTHONPATH=C:\m3tmp\muse_r15
set MUSE_DATA_DIR=C:\m3tmp\scratch2\data      (no-op on this tag)
set MUSE_HALT_FILE=C:\m3tmp\scratch2\data\muse_halt.json
set MUSE_LEASES_FILE=C:\m3tmp\scratch2\data\lane_leases.json
set AFP_STATE_DIR=C:\m3tmp\scratch2\afp
set PYTHONIOENCODING=utf-8                    (AFP_HALT_FILE unset)
python -m muse_studio.pool_runner videos C:\m3tmp\b14_plus --simulate
```
Synthetic accounts `sim_acc_01/02`, no browser, no real send. Data dir isolation = clone location
(`C:\m3tmp\muse_r15\muse_studio\data`, new files listed with SHA256 in `clone_data_dir_new_files.sha256`).

## Result
Exit 1, status `INCOMPLETE`, 19/21 shots passed, 14 s, 3 rounds.
Failed: `S07`, `S08__st_e0b581116dbb`, both `BATCH_ERROR` `[Errno 13] Permission denied: '.'` in R01_B02, R02_B01, R03_B01.
Cause (fixture + code): `S08__st_e0b581116dbb` has `first_frame_path: ""`; `Path("")` is `.`, opening it raises
EACCES, and the whole batch fails, taking its batch-mate `S07` down with it. Expected in parity reruns until the
code or fixture changes; a fix (reject empty `first_frame_path` at preflight/packaging, isolate the bad shot from its
batch) means a new tag per plan §8.

## Contents
`BATCHES_V2/` (manifests, receipts, render fingerprints, result zips, simulated clips), `qc_audit_report.json`,
`verified_clips/`, `qc_strips/` (empty), `run_stdout.json`, `run_stderr.txt` (empty), `supplement_images.sha256`,
`clone_data_dir_new_files.sha256`. Compare on normalized custody records (plan R2), not counts.
