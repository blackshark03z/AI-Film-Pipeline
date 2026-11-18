# Daily Production Runbook (`afp-film`)

This document describes the stabilized daily-production CLI workflow over `afp-film` (or `python -m film_pipeline`). Existing regression documentation in `RUNBOOK.md` remains unchanged.

## 1. Environment Preflight (`doctor`)

Run a read-only check before starting daily production or after installing a new wheel:

```bash
afp-film doctor
afp-film doctor --film films/<film_id> --probe-flow
```

Confirms disk reserves, `ffmpeg`/`ffprobe`, required filters (`xfade`, `ebur128`, `loudnorm`), Pillow & fonts, packaged resources (`sfx_catalog.json`, `film_package.v1.schema.json`, `_flow_ui/flow_send.py`), optional post engine, and CDP Flow tab visibility.

## 2. Package Validation, Planning & Fast DAG Pre-Production

```bash
afp-film new <film_id> --profile drama                # 16:9 default (add --portrait-9x16 for 9:16 opt-in)
afp-film validate --film films/<film_id>
afp-film plan --film films/<film_id> --out films/<film_id>/media/plan
afp-film setup-anchors --film films/<film_id> --max-depth 4 --apply
afp-film stills --film films/<film_id> --bind-matching --by human:<Name>
afp-film agentic-plan --film films/<film_id> --lookahead 1
```

- `setup-anchors` marks safe mid-chain `independent_still: true` breakpoints so deep `previous_generation_id` chains split into wide Wave 0 frontiers while keeping `continuity.py` hand-off checks active.
- `stills --bind-matching --by <reviewer>` reuses already-`APPROVED` start/end stills across unapproved shots with identical `(kind, prompt_sha256)`.
- `agentic-plan` stays read-only and outputs DAG readiness waves (`dependency_and_index` / `verified_media`), `--lookahead N` `speculative_frontier`, `PreSendCritic` warnings/blocks, `CausalRepairRouter` actions, `SceneIncrementalConformer` statuses, and Owner checkpoints `CP1`–`CP3`.

## 3. Multi-Account Lease Management & Safe Parallel Dispatch

```bash
afp-film lease register --film films/<film_id> --account acct_a --credits 100
afp-film lease status --film films/<film_id>
```

- Run pre-send inspection and dry-run before spending credits:

```bash
afp-film generate --film films/<film_id> --gid <GID> --dry-run --critic
```

- Parallel workers pinned to separate CDP ports (`AFP_FLOW_CDP`) can execute `generate` concurrently on distinct accounts: short `film_lock(timeout_s=15.0)` serializes only Phase A receipt reservation and Phase C registration while browser submission runs under each CDP endpoint's `composer_lock`.
- If a Flow job loses tab context mid-send, run hash-bound reconciliation before retrying or quarantining:

```bash
afp-film reconcile --film films/<film_id> --take-id <TAKE_ID>
afp-film lease quarantine --film films/<film_id> --account acct_a --reason "session check"
```

Active leases remain `QUARANTINED_PENDING_RECONCILE` until reconciliation proves `NOT_SUBMITTED`.

## 4. Dailies Triage, Batch HTML Review & Retake Classification

```bash
afp-film triage --film films/<film_id> --take-id <TAKE_ID>
afp-film review-ui --film films/<film_id> --triage
afp-film review --film films/<film_id> --ingest batch_reviews.json
```

- `triage` scans evenly across the full clip duration (including the tail frame) and verifies `output_sha256`.
- `review-ui --triage` builds a self-contained local `<film>/media/review_ui/index.html` viewer (playback `1x`/`1.5x`/`2x`, scene/triage filters, explicit `Mark All Clean Pending PASS`, required `REL_*` prompts) and exports a `batch_reviews.json` array accepted directly by `review --ingest` without bypassing human QC or `refuse_bot`. Review reframes automatically expand to matching EDL `event_id`s when `05_edit.json` exists.

## 5. Scene Incremental Conform, Lock & Parallel Finishing (`16:9` Default)

```bash
afp-film scene-conform --film films/<film_id> --render --jobs 4
afp-film lock --film films/<film_id> --edl films/<film_id>/05_edit.json --reviewer <name>
afp-film finish --film films/<film_id> --dry-run
afp-film finish --film films/<film_id> --jobs 4           # ships 16:9 master only by default
afp-film finish --film films/<film_id> --hwaccel          # opt-in GPU h264_nvenc when available
afp-film finish --film films/<film_id> --portrait         # opt-in 9:16 portrait render + delivery
```

- By default (`"portrait_9x16": false` in `film.json`), `titles`, `versions`, and `deliver` skip `--clean-copy` double 16:9 renders, `portrait_focus`, and `*_9x16.mp4` encoding, shipping `master_16x9`, thumbnails, metadata, and `.srt` sidecars. Pass `--portrait` (or `"portrait_9x16": true`) to build and package `9:16`.
- `cut`, `grade --render`, `titles --render`, `versions`, `scene-conform --render`, and `finish` support `--jobs N` / `AFP_RENDER_JOBS` (default `4` CPU workers) and `--hwaccel` / `AFP_HWACCEL=1` (`h264_nvenc`), and fine cut automatically skips redundant second-pass re-encoding on unannotated chunks.
- `finish` synthesizes unsourced catalog Foley matches when requested, validates QC + disclosure pixels (`always` and `title_card`), and stages an immutable archive under `media/deliveries/` (`release_ready=false` until cleared + locked, `Gate 6=OWNER_PENDING` until `deliver --accept`).

## 6. Offline Archive Verification

```bash
afp-film status --package films/<film_id>/delivery
```

Verifies every manifest hash, package integrity, and release disclosure compliance.
