# Muse commands — verified 2026-11-19, lane contract 2026-11-20

Verified by `--help` (with `PYTHONIOENCODING=utf-8`) and by reading `muse_studio/cli.py` (argparse at lines
727–823, handlers 319–724) and `muse_studio/pool_runner.py` (lines 56–141). Run from `D:\Muse`. Without
`PYTHONIOENCODING=utf-8` every `--help` on a cp1252 console dies with `UnicodeEncodeError`.

Entries marked † are the lane/QC contract agreed on 2026-11-20 and being implemented by session `lane-leases`;
confirm each with `--help` (or the JSON output) before relying on it, and stop if it is missing.

Only the commands below are part of the director workflow. Other subcommands in `cli.py` / `pool_runner.py` are
out of scope for this skill.

## `python -m muse_studio.cli`

| Command | Positional | Flags (default) | Exit code | Writes |
|---|---|---|---|---|
| `normalize-srt` | `srt` | `--chapters F`, `--output F` (stdout if absent), `--window 22.0` | 0 | beat skeleton JSON (`total_beats`, `story_end_s`) |
| `srt-audit` | `target`: a beats JSON (stage 1) or the project dir (needs `shots_manifest.json`, i.e. after compile) | `--srt F`, `--chapters F` (fallback: bible `source_srt_path` / `source_chapters_path`) | 0 pass, 1 fail | JSON report on stdout: HARD gates `UNCOVERED_SRT_TAIL`, `UNCOVERED_SRT_CHAPTER`, `ADAPTATION_TOO_SHORT` (ratio < 0.28) |
| `compile` | `project_dir` | `--beats F` (default `beats.json`; if absent it takes the first non-empty `*beats*.json`. `F` resolves against the current directory, not the project — always pass `--beats` with an absolute path), `--audio-mode native_drama\|hybrid_narrated` (`native_drama`), `--no-strict-bible`, `--cinematic-cutaways` | 0 | `shots_manifest.json`, `shots_manifest.csv`; prints first 10 coverage warnings |
| `keyframes` | `project_dir` | `--simulate` (required), `--include-setups`, `--include-turnarounds` — **dry run only** (round 15): without `--simulate` it sends nothing and prints `REFUSED_USE_POOL_RUNNER` (exit 2); real stills go through `pool_runner keyframes` only | 0, 1 if any keyframe rejected, 2 refused (real run) | `assets/anchors/`, `assets/setups/`, `assets/keyframes/`, contact sheets; JSON on stdout |
| `animatic` | `project_dir` | `--output F` (default `ANIMATIC/animatic_preview.mp4`), `--fps 12` | 0 / 1 (0 even with no keyframes: missing first frames become text slates) | MP4 1280×720 + sidecar SRT |
| `preflight` | `project_dir` | `--srt F`, `--chapters F`, † `--no-srt-gate` (excerpt SRTs: skips the SRT coverage gate and records `srt_gate: SKIPPED_BY_FLAG` in the report). Omitting `--srt` does **not** skip the gate when the bible has `source_srt_path` (it is re-read); it is skipped silently only when neither exists | 0 if 0 HARD errors, else 1 | `preflight_report.json` (`passed`, `errors`, `warnings`, `srt_coverage`, † `srt_gate`) |
| `qc-audit` | `project_dir` | `--strips` | **always 0** | `qc_audit_report.json`, `verified_clips/<shot>.mp4`, `qc_strips/` |
| † `promote-take` | `project_dir shot_id take` (`take` = take number from `per_shot_qc[<shot>].candidates[].take`, or that take's `clip_path` when the number is ambiguous) | — | 0; 1 with JSON `error`: `TAKE_NOT_FOUND`, `TAKE_NOT_PASSING`, `TAKE_STALE` (older design), `TAKE_UNPROVEN` (legacy batch without fingerprint: re-render with `videos`, `qc-audit`, then promote a new take), `AMBIGUOUS_TAKE`, `CLIP_MISSING` (source clip gone or its SHA-256 no longer matches the audit), `NO_AUDIT`, `UNKNOWN_SHOT` (audit unchanged); 3 `PROJECT_LOCKED` | copies the take's own source clip to `verified_clips/<shot>.mp4` and its own strip (or a strip regenerated from the clip) to `qc_strips/<shot>_strip.jpg`; `per_shot_qc[<shot>]` becomes that take (`selected_by: promote-take`, `previous_take`), with its fingerprint |
| `assemble` | `project_dir` | `--output F` (default `MASTER_OUTPUT/final_master_1080p.mp4`), `--bgm F`, `--room-tone F`, `--capcut-draft`, `--color-mood` (`cinematic_neutral`), `--with-titles`, `--promo-kit`, `--no-stems`, `--no-grain`, `--no-timbre-lock`, `--no-jl-cuts` | 0; † non-zero when `qc_audit_report.json` exists but no clip passed (no fallback to raw batches) — still read the report, a partial master exits 0 | master MP4; beside it `<stem>.srt`, `<stem>.i18n_template.json`, `<stem>.chapters.txt`, `<stem>.dialogue_stem.m4a`, `<stem>.me_stem.m4a`; `_build_<stem>/normalized_clips/` |
| `deliver` | `project_dir` | `--master F` (default `MASTER_OUTPUT/final_master_1080p.mp4`; error if missing) | 0 | `<master dir>/DELIVERY_KIT/`: `trailer_1080p.mp4`, `shorts_vertical_9x16.mp4`, `poster_1080p.png` |

Notes from the code:
- `compile` runs `plan_staging` on the beats; `staging_review` in the manifest lists each staging decision with its
  outcome (`invalid` rows also become coverage warnings). Use the same `--cinematic-cutaways` value before and after
  keyframes (SOT §3). Without that flag, `reaction` and `state_insert` directions are skipped silently (no review
  row) unless saved in the beats; with it they are capped at floor(20%) of source beats. `source_action` always
  materialises as a 100 mm "Macro Prop Insert" (`core/staging.py` ~240–247).
- Strict compile (default) fails if a character lacks `id`/`look_verbatim`/`anchor_image` or a location lacks
  `look_verbatim`; it does not need the anchor files. `preflight` does (missing file = HARD).
- `keyframes` reads `shots_manifest.json` and requires current staging, so compile first.
- † `qc-audit` and `promote-take` hold the project lock like `videos` / `keyframes`: while another of them runs on
  the same project they exit 3 and change nothing.
- `qc-audit` prints "5-Gate QC Audit" (the SOT counts sub-gates as 7). It picks the best candidate per shot, copies
  it to `verified_clips/` and deletes a stale verified copy when a shot fails. † Only takes rendered for the
  **current** design can win: each `videos` batch writes `BATCHES_V2/<batch>/render_fingerprints.json`, and a take
  whose fingerprint differs from the current shot is listed but never evaluated (`fingerprint_status: stale`); a
  shot with only such takes fails as `STALE_RENDER`. Legacy batches without fingerprints are audited as before when
  no take of that shot has one, but their winner gets no fingerprint (the next `videos` run re-renders it).
  `per_shot_qc[<shot>]` keeps the winner's `take`, `clip_path` (source clip), `batch_id`, `fingerprint`, and
  `candidates` (every take: `take`, `clip_path`, `verdict`, `quality_score`, `defects`, `metrics`,
  `fingerprint_status`, `strip_path`, `sha256`); `render_fingerprints` comes from each winning take itself. A take
  chosen with `promote-take` stays the shot's take in later audits while it still passes for the current design
  (`selected_by: promote-take` kept); once it fails or goes stale the best passing take wins again.
- † `promote-take` applies a self-review choice: assemble reads only `passed_clips`, so a take kept for performance
  (not the highest score) must be promoted before `assemble`. Only passing takes with the current design's
  fingerprint.
- `assemble` uses `qc_audit_report.json` `passed_clips`; if the report is absent it falls back to any clips it finds
  († with a report and zero passed clips it fails instead of falling back to raw batches).

## `python -m muse_studio.pool_runner`

| Command | Positional | Director flags (default) | Exit code |
|---|---|---|---|
| `keyframes` | `project_dir` | `--include-setups`, `--include-turnarounds`, `--simulate`, `--no-ui-sync`, `--session-tag` (`pool_keyframes`), `--lane`, `--accounts-file F` | 0 completed, 1 incomplete († also `INCOMPLETE` + non-zero when expected keyframes are missing after the run), 2 blocked — stop and report to the Owner, 3 session conflict |
| `videos` (the generation step) | `project_dir` | `--max-rounds 3`, `--no-auto-repair` (auto-repair is **on** by default; `--auto-repair` is a no-op), `--simulate`, `--no-ui-sync`, `--session-tag` (`pool_videos`), `--lane`, `--accounts-file F`. `--takes K` (default 1): independent takes per shot sent in parallel each round; a shot's manifest field `takes` overrides K only when it is an integer ≥ 1 (0, negative, bool, float or text fall back to K). † `--release-unconfirmed`, `--unconfirmed-ttl-min M` (see below). With `--max-rounds 1`: at most one send round per shot per run; JSON reports `sends_by_shot`, `takes_by_shot` and the failed shots. Lane mode always uses `--max-rounds 1 [--takes K]` (one review cycle per run) | same |

Both print a JSON result; `videos` also writes `qc_audit_report.json` and fills `verified_clips/`. `videos` sends
every shot not yet in `passed_clips` (no subset flag). † After a restage + recompile, takes of the old design are
stale automatically (design fingerprints are kept through `qc-audit`), so the restaged shot is pending again.

Multi-take (`videos --takes K`): take k of every shot forms its own batch layer (batch ids end `_T<k>` when any
shot has more than one take); layers run concurrently across the lane's accounts and a batch never holds the same
shot twice. Within a run, `verified_clips/<shot>.mp4` and `per_shot_qc[<shot>]` hold the **passing** take with the
highest `metrics.quality_score` (the record carries `take` and `clip_path`); a rejected take never overwrites a
passing one. Strips: every take writes its own `qc_strips/<shot>_<batch>_strip.jpg` (batch ids are unique per run,
so a strip is never rewritten) and only the take that becomes the shot's QC record is copied to `<shot>_strip.jpg`
(takes may finish in any order); `candidates[].strip_path` names each take's own strip. `per_shot_qc[<shot>].candidates` lists every take. `qc-audit`
still discovers every take in `BATCHES_V2/*` (current design only). The score only orders takes: review each take's
whole clip before keeping one, and run `cli promote-take` for a kept take that is not the verified one.

† Send ledger `<project>/unconfirmed_submissions.json`: every batch is written `PENDING_SEND` before it is
dispatched, then `RESOLVED` (`RESULT_RECEIVED` / `NOT_SENT`) or `UNCONFIRMED` (reached Muse, no reconciled result:
browser crash, quota after send, unpack error…). Entries are kept as history (shot, batch, take, UTC time,
fingerprint, status). A `PENDING_SEND` left by a crashed run, an `UNCONFIRMED` entry, and — on the first run of a
project without a ledger — a `BATCHES_V2/<batch>` dir with no result zip and no clips (old code, maybe still
rendering) all block a resend of their shot, in this run and later runs, until released: the shot passed (e.g.
`qc-audit` found the clip), the shot was restaged (fingerprint changed), the batch's result arrived (clips unpacked,
or a result zip that opens, passes its CRC check and holds a clip; an empty/broken zip makes the entry
`RESULT_CORRUPT`, still blocking), or an explicit
`--release-unconfirmed` (all) / `--release-unconfirmed-shot <shot>` (repeatable). Past the TTL
(`--unconfirmed-ttl-min`, env `MUSE_UNCONFIRMED_TTL_MIN`, default 120 min) an entry becomes
`EXPIRED_NEEDS_RECONCILE`: reported, **still blocking** — age alone never allows a resend. JSON:
`submitted_unconfirmed_shot_ids`, `unconfirmed_submissions` (still blocking), `unconfirmed_expired`,
`unconfirmed_released` (with `reason`: `RECONCILED_PASSED`, `STALE_DESIGN`, `RESULT_RECEIVED`, `MANUAL`,
`SHOT_REMOVED`), `unconfirmed_ttl_min`; blocked shots fail as `SUBMITTED_UNCONFIRMED`.
**CAPTCHA / verification / unusual-activity page = machine-wide halt (round 15):** the moment any detector sees it
(login, page load, polling, or the pre-submit gate), this process stops pressing Enter (in memory) and publishes the
halt under the halt-file lock: `muse_studio/data/muse_halt.json` (env `MUSE_HALT_FILE` overrides; a copy goes to
`<project>/muse_halt.json` for the report). Every send on the machine — every pool engine, project and process, and
the Web UI queue — runs ONE gate right before the submit keystroke: page challenge probe, the in-memory stop, the
machine-wide signals (`MUSE_HALT_FILE`, `<AFP_STATE_DIR>/halt_pending/*.json`, optional `AFP_HALT_FILE`; read under
the lock, unreadable = refuse), then the lease. `videos` / `keyframes` report `"halted"` and `"halt_publication"`
(`PUBLISHED` / `PENDING` / `HALT_PENDING_UNWRITTEN` / `ALREADY_HALTED`) and exit **4**; `cli run-pool` and
`cli accounts-verify` (stops at the first BLOCKED account) exit 4 too. Every later run refuses until the Owner clears it
on Muse and reruns with `--clear-halt` (`pool_runner keyframes|videos`); `--clear-halt` never removes `halt_pending`
markers or the AFP halt (Owner-only), and `--simulate` ignores the halt (reported as `halt_file`). `--clear-halt`
never releases a send that reached Muse without a result: keyframes are withheld via `unconfirmed_keyframes.json`
(keyframe batches handed off before the ledger existed are adopted as `legacy` UNCONFIRMED entries; an entry is
released only by a verified image of that submission — size floor + PNG/JPEG decode in its own result zip — or by
`pool_runner keyframes --release-unconfirmed` / `--release-unconfirmed-kf ID`), videos via
`unconfirmed_submissions.json` as above. `cli keyframes` and `autoprod` no longer send (`REFUSED_USE_POOL_RUNNER`). A lane whose lease is lost
while a batch is being prepared aborts it before the submit keystroke (not counted as sent). A clip whose SHA-256
differs from the receipt is never verified (`INTEGRITY_FAILED`): it is listed in `BATCHES_V2/<batch>/integrity_failed.json`
and moved to `BATCHES_V2/<batch>/integrity_failed/`. Clip discovery (`qc-audit`, `assemble` fallback) skips listed or
quarantined clips and any batch clip whose SHA-256 differs from its receipt, plus untrusted copies of such a clip (a canonical
clip is judged by its own SHA-256 against the receipt / promote SHA: intact → kept even if its source rotted; mismatched →
`INTEGRITY_FAILED`, moved to `verified_clips/integrity_failed/`, never deleted); the other clips of that batch are kept. Batch ids carry date, time and a random tag
(`POOL_<yymmddHHMMSS><hex>_R..`), and a batch dir is created exclusively (never reused). `compile` does not write a `takes` field,
and `shots_manifest.json` is never hand-edited, so in practice pass `--takes` = the largest count any pending shot
needs (shots that need fewer simply get extra takes).

Lanes (added 2026-11-20): `keyframes`, `videos` and `capacity` take `--lane <id>`. Without it, an open
`<project_dir>/lane.json` selects the lane automatically. With a lane, only that lane's leased accounts are used
(also for hot-swap), leases are renewed at start, every 5 min (env `MUSE_LANE_HEARTBEAT_S`) and at the end, and the
JSON gains `lane: {lane_id, accounts, lost_leases, renewals}`; an account whose lease is lost mid-run gets no new
batch. Without a lane, every account leased by a live lane is skipped (`skipped_busy_accounts[id] = LEASED_BY_<lane>`).

## `python -m muse_studio.lane` — production lanes (one chat = one lane)

Registry `muse_studio/data/lane_leases.json` (env `MUSE_LEASES_FILE` overrides), file-locked. A lease is live while
`now < expires_at`; default TTL 8 h; process liveness is not used. Each command prints ONE JSON object.

| Command | Flags | Exit | Output / writes |
|---|---|---|---|
| `open` | `--lane L --project <abs dir> -n N`, `--accounts a,b`, `--ttl-hours 8`, `--simulate` | 0; 2 if 0 granted; 1 error (e.g. `PROJECT_HELD_BY_OTHER_LANE`); † 3 `LANE_ID_IN_USE` (the id belongs to another project) or `PROJECT_IN_USE` (another lane holds the project) | `{lane_id, accounts, granted, requested, newly_granted, skipped:{id:reason}, expires_at}`; writes `<project>/lane.json`. One lane id = one project = one chat: pick a unique id (e.g. project folder + date). Idempotent: re-open keeps/extends the lane's leases and tops up to N († `held > requested` is reported when it already holds more). Only READY, not BUSY, not profile-locked, not leased accounts, highest quota first |
| `status` | `--lane L` (filter) | 0 | `{lanes:{L:{project_dir, accounts, expires_at}}, accounts:[{id, name, email, status, quota_pct, weekly_remaining_pct, lease:{lane_id, project_dir, expires_at, heartbeat_age_s}\|null, profile_locked}]}` — no cookies/passwords/proxies |
| `renew` | `--lane L`, `--ttl-hours H`, † `--project P` | 0; 2 if the lane holds no live lease | extends every live lease; expired ones are dropped, never revived |
| `close` | `--lane L`, `--project P` | 0 | releases all leases; marks `lane.json` `status: closed` |
| `gc` | — | 0 | drops expired leases |

`--simulate` on any subcommand uses `MUSE_LEASES_FILE` or `%TEMP%\muse_sim_lane_leases.json`, never the real
registry; `open --simulate` grants `sim_acc_XX` ids. A `--simulate` pool run never writes the real registry.
Legacy pickers (`cli run-pool`, the Web UI queue) also skip leased accounts, but they are **not** lane spend paths
(`cli keyframes` and `autoprod` send nothing without `--simulate`): in lane mode spend only through `pool_runner keyframes|videos`; `GET /api/accounts` shows a
read-only `lease` per account.

## Offline dry run

```
$env:PYTHONIOENCODING="utf-8"
python -m muse_studio.cli compile <P>
python -m muse_studio.pool_runner keyframes <P> --simulate --no-ui-sync --accounts-file <scratch>\accounts.json
python -m muse_studio.cli compile <P>
python -m muse_studio.cli preflight <P>
python -m muse_studio.cli animatic <P>
python -m muse_studio.pool_runner videos <P> --simulate --no-ui-sync --max-rounds 1 --takes 2 --accounts-file <scratch>\accounts.json
python -m muse_studio.cli assemble <P>
python -m muse_studio.cli deliver <P>
```
Expected: every step exits 0. Do **not** run `qc-audit` in a dry run: `videos --simulate` skips FilmQC and writes
the audit itself, while a real `qc-audit` rejects the synthetic clips (tiny, silent, no picture content), and
`assemble` then stops with `NO_QC_PASSED_CLIPS`. That is expected, not a pipeline defect. Keep the scratch path
short (e.g. `%TEMP%\mr\<P>`): keyframe batch paths add ~50 characters plus a kf id of ~100, and past Windows'
260-character limit the simulated ZIP fails to unpack (`Keyframe ZIP bị hỏng ... No such file or directory`).
Use a scratch copy of the project for dry runs, placed under the OS temp folder: `qc-audit` and `assemble` mirror
any project outside the temp folder into the Web UI's `data/projects` (`cli.py:174-179`), whatever `--no-ui-sync`
says on `pool_runner`. `<scratch>\accounts.json` is a copy of `muse_studio/data/accounts.json` inside the same
temp rehearsal folder, so a simulated run can never change real account state (the code also guards this); never
print it, and delete the rehearsal folder when done. Keep `<P>` (the copy) free of a real `lane.json`.
