# M3 merge plan, Step 2 report: source-history scan and baseline

Date: 2026-11-21. Executed in the throwaway clone only. Nothing was edited, staged, committed, stashed or reset in
`D:\Muse` (`git status` there still shows only `?? HANDOFF_CLAUDE_MUSE_20261119.md`; HEAD `a8f2b9c`). No commit in AFP-stable.

## Clone

- Path: `C:\m3tmp\muse_r15` (kept).
- Command: `git clone --no-local --branch muse-v1.0-r15 D:\Muse C:\m3tmp\muse_r15`
- HEAD = `a8f2b9c6ff6f5e238e6a0d71606cb42724ab6fa1` (detached at the tag). Annotated tag object `1163f905908fc396ecb930da80c7e63d14769aaa`
  peels to that commit. Clone history: 4 commits (`b9d6d5c`, `a23f677`, `c607029`, `a8f2b9c`), 2038 files in the tag tree.

## Checkpoint-1 scan (history)

Command (in the clone, `PYTHONIOENCODING=utf-8`):
`python tools/secret_scan.py --history . --allow tools/secret_scan_allow.txt --out <step2>\scan_muse-v1.0-r15.md`
The scanner has no JSON mode (`--out` writes markdown). Exit 1. Files: `scan_muse-v1.0-r15.md` (report),
`scan_stdout.txt`, `hits_classified.json` and `hits_classified.md` (my classification: per path, rule, max blob size, first
commit, commits where present).

Result: 7941 file entries, 646 blobs read, 4 commits; **39 hits, 17 allowed**.

| rule | hits | class |
|---|---:|---|
| large-media | 35 | expected (media in film folders) |
| large-blob | 3 | expected (`narration_seg*.flac` in MARCUS_SEG2/3/4) |
| path-backup | 1 | expected (`MARCUS_SEG2_20261031/shotplan_v3.bak.json`) |
| content / credential / cookie / email / `.env` / `accounts.json*` / `profiles/` / `lane_leases.json` / halt | 0 | none |

**Expected 39, unexplained 0.** Total size of the 39 hit blobs about 817 MB (see `hits_classified.md` for each size).
A path check over every path of every commit found no `accounts.json*`, `profiles/`, `muse_halt.json`, cookie, `.env` or
sqlite path. The only `lane_leases` matches are source files (`muse_studio/core/lane_leases.py`, `muse_studio/tests/test_lane_leases.py`).

Points that differ from the brief (none changes the verdict):
1. **Two hits are not from `b9d6d5c`.** `MARCUS_PIPELINE_20261101/P60/P60_v2_1080p.mp4` and `P60_v2_704p.mp4` were first added
   by `a23f677` ("feat(p60) ..."). The other 37 first appear in `b9d6d5c`. Both are media in a film folder, so still expected.
2. **17 allowed content hits exist** (the brief said 0 credential/cookie/email hits). They are `content-email-near-credential`
   (13), `content-cookie-export` (1) and `content-credential-assignment` (3) matched by
   the 7 pre-existing lines in `tools/secret_scan_allow.txt`, each with a written reason (dummy tempmail rows, fixture cookie
   array, lease-redaction sentinels). I spot-checked all 17 lines by shape only (domains and local-part length/pattern,
   nothing printed): domains are tempmail services or `example.test`, local parts are 1-5 characters. I did not print values.
   These entries are in the shipped allow file and are listed in the report's "Allowed" table. Step 3 note: the allow globs
   use the pre-rename paths (see scanner README).
3. The scan lists most hits under commit `a8f2b9c` (the latest commit that holds the blob); `hits_classified.*` gives the first commit.

### Step 3 filter lists
- `step3_filter_paths.txt` (10 lines): the film folders that contain a hit, as directory prefixes, plus the one root-level zip
  `GOLDEN_GRIDDLE_FIRST_PASS_EMPIRICAL_DELIVERY.zip`. Every one of the 39 hit paths lies under one of these (asserted by script).
- `step3_other_nonallowlist_paths.txt` (5 lines, extra): tracked top-level film folders without a hit that §2.3's allow-list
  also drops: `MARCUS_SPACE_LAB_20261101/`, `FLOW_ONEPASS_CORE/`, `_FILM_KIT/`, `DRY_RUN_OUTPUT/`, `GPT_JOBS/`.
- Observations for the AFP TL (not acted on): the tag tree also tracks `muse_studio/data/sample_script.csv` (inside the
  `muse_studio/data/**` exclusion), `.claude/launch.json`, `.claude/settings.json` and `.agents/skills/muse-filmmaker/**`.
  The §2.3 allow-list as written drops `.claude/launch.json`, `.claude/settings.json` and `tools/`; `.agents/skills`
  keeps `muse-filmmaker`. Confirm that is intended. `tools/` (the scanner) is handed over separately in `scanner\`.

## Rule-test baseline

Isolation env (set for the shell that ran pytest; scratch root `C:\m3tmp\scratch`): `MUSE_DATA_DIR=C:\m3tmp\scratch\data`,
`MUSE_HALT_FILE=C:\m3tmp\scratch\data\muse_halt.json`, `MUSE_LEASES_FILE=C:\m3tmp\scratch\data\lane_leases.json`,
`AFP_STATE_DIR=C:\m3tmp\scratch\afp`, `AFP_HALT_FILE` unset, `PYTHONIOENCODING=utf-8`.
Note: **this tag's code does not read `MUSE_DATA_DIR`** (`rg` finds no use; `core/config.py` derives `DATA_DIR` from its own
`BASE_DIR/data`). Data-dir isolation therefore comes from the clone location (its `muse_studio/data` has no `accounts.json`;
importing config created only empty `output/`, `profiles/`, `projects/` dirs in the clone). The halt and lease files are
isolated by `MUSE_HALT_FILE` / `MUSE_LEASES_FILE` and the test conftest.

Command (cwd = clone root):
`python -m pytest muse_studio/tests/test_review6_fixes.py muse_studio/tests/test_review7_fixes.py muse_studio/tests/test_review9_fixes.py muse_studio/tests/test_review11_fixes.py muse_studio/tests/test_blocked_halt.py muse_studio/tests/test_stop_all_r14.py muse_studio/tests/test_stop_all_r15.py -q --tb=short -p no:cacheprovider -rA --junitxml=<step2>\rule_tests_junit.xml`

Result: **130 passed, 0 failed, 0 errors, 0 skipped, 0 missing files** in 91.9 s (exit 0).
Per file: review6 21, review7 19, review9 9, review11 4, blocked_halt 17, stop_all_r14 17, stop_all_r15 43.
Files: `rule_tests_junit.xml`, `rule_tests_passfail.txt` (status, module::test per line).
Canary: stat of `D:\Muse\muse_studio\data\muse_halt.json` and `lane_leases.json` identical before and after (stat only, never opened).
Extra: `tools/test_secret_scan.py` in the clone, 143 passed.

## B14 baseline

Fixture: `D:\Muse\_director_review_B14_20261119` (227 MB, 318 files; named in plan §2.3 and in `docs/AFP_MUSE_LANE_CONTRACT.md` §14).
Not in the clone (untracked). Copied with `cp -r` to `C:\m3tmp\b14` (the copy kept; the source was only read). It holds
`shots_manifest.json` (21 shots), `beats.json`, `story_bible.json`, SRT, and the step_05..step_15 review runs; no `lane.json`,
no account/cookie/profile files.

Command (clone root, same isolation env):
`python -m muse_studio.pool_runner videos C:\m3tmp\b14 --simulate`
(no browser, no account use: the engine used the synthetic accounts `sim_acc_01/02`; lane none).

**Result: exit 1, status `INCOMPLETE`, 0 of 21 shots passed, 5.9 s.** Cause: every batch fails with `BATCH_ERROR`
"first-frame image not found": the manifest references `shot01_after_tag_fadeout.png`, `shot02_after_tag_fadeout.png`,
`officer_craig_anchor.png`, `todd_wilson_anchor.png` (as `first_frame_path` / `anchor_ref`) and the B14 folder does not
contain them. They exist elsewhere in `D:\Muse` (`BLACK_PILOT_EXTENDED_FEATURE_FILM\assets\anchors\`, same hashes as the copy
under `BLACK_PILOT_DEMO_60S_20261117\...\evidence_nosub_tagged\` for the two shot frames). So as a standalone fixture
the B14 folder cannot complete a `videos --simulate` run. The run is deterministic and finished cleanly (no halt, no crash,
no integrity/unconfirmed state).

Custody bundle: `b14_custody\primary_as_is\` holds `run_stdout.json` (engine result), `run_stderr.txt` (empty),
`qc_audit_report.json`, `BATCHES_V2\POOL_..._R0n_B0m\render_fingerprints.json` (12 files, 3 rounds x 4 batches),
`new_files.txt` (the 13 files the run created, from a before/after file listing; `verified_clips/` and `qc_strips/` were
created empty). **No receipts, no quarantine decisions and no unconfirmed-submission ledger were produced**, because no
clip was generated. The custody content of this baseline is therefore thin: fingerprints per shot per batch, the audit report
with `PENDING_OR_MISSING` for all 21 shots, and the batch error list. Batch ids contain a timestamp
(`POOL_<yymmddHHMMSS><hex>_R..`), so later comparisons must normalize them (plan R2).

Not done: a **variant run** (B14 plus those 4 PNGs copied from the BLACK_PILOT folder into a second copy) that would exercise
the full simulate path (receipts, QC, quarantine). I attempted it, the command was denied by the permission system (it
copied files out of another film folder), and I did not retry or work around it; nothing from it ran. It is a different fixture from the plan's B14, so it needs a coordinator decision (which
source for the 4 images; whether to treat B14 + images as the baseline fixture).

## Scanner handoff

`scanner\` holds `secret_scan.py`, `test_secret_scan.py`, `secret_scan_allow.txt` (byte-identical to the clone, `cmp` checked),
a derived `secret_scan_allow_step3_renamed.txt` (`src/` prefix) and `README.md` (usage, exit codes, allow format, SHA256,
checkpoint 2 and 3 command lines).

## Verdict against Step 2 "Done"
- Zero unexplained scan hits: yes (39 expected, 0 unexplained).
- Baseline recorded: rule tests yes (130/130); B14 recorded as-is but **degraded** (exit 1, fixture incomplete, see above).
- Scanner handed over: yes.

## Open items for the coordinator
1. B14 fixture is not self-contained (4 first-frame/anchor PNGs missing); decide the baseline fixture, then re-run.
2. `MUSE_DATA_DIR` is a no-op in this tag (the plan's step 4 data-location edit introduces it); step-4 "reproduce the baseline exactly" must account for this.
3. Allow-list globs need the `src/` prefix after the rename (derived file provided).
4. `D:\Muse\muse_studio\data\muse_halt.json` exists (stat only, modified 2026-11-21 10:08; not opened). It is a real Muse halt; the
   scratch `MUSE_HALT_FILE` kept it out of these runs.
5. Two hits first appear in `a23f677`, not `b9d6d5c` (both media, expected).

## Commands run (summary)
`git clone --no-local --branch muse-v1.0-r15 D:\Muse C:\m3tmp\muse_r15`; `git rev-parse HEAD`;
`python tools/secret_scan.py --history . --allow tools/secret_scan_allow.txt --out ...`; a classification script over `git cat-file -s` / `git log --diff-filter=A` (scratchpad);
`python -m pytest <7 files> -q --tb=short -p no:cacheprovider -rA --junitxml=...`;
`python -m pytest tools/test_secret_scan.py -q`; `cp -r D:\Muse\_director_review_B14_20261119 C:\m3tmp\b14`;
`python -m muse_studio.pool_runner videos C:\m3tmp\b14 --simulate`.
