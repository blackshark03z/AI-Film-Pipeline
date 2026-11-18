# Daily Production Runbook (`afp-film`)

This document describes the stabilized daily-production CLI workflow over `afp-film` (or `python -m film_pipeline`). Existing regression documentation in `RUNBOOK.md` remains unchanged.

## 1. Environment Preflight (`doctor`)

Run a read-only check before starting daily production or after installing a new wheel:

```bash
afp-film doctor
afp-film doctor --film films/<film_id> --probe-flow
```

Confirms disk reserves, `ffmpeg`/`ffprobe`, required filters (`xfade`, `ebur128`, `loudnorm`), Pillow & fonts, packaged resources (`sfx_catalog.json`, `film_package.v1.schema.json`, `_flow_ui/flow_send.py`), optional post engine, and CDP Flow tab visibility.

## 2. Package Validation & Planning

```bash
afp-film validate --film films/<film_id>
afp-film plan --film films/<film_id> --out films/<film_id>/media/plan
afp-film agentic-plan --film films/<film_id>
```

`agentic-plan` stays read-only and outputs DAG readiness waves (`dependency_and_index` / `verified_media`), pending send exclusions, `PreSendCritic` warnings/blocks, `CausalRepairRouter` actions (`CLASSIFY` / `RETRY` / `ESCALATE`), `SceneIncrementalConformer` statuses, and Owner checkpoints `CP1`–`CP3`.

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

## 4. Dailies Triage, Review, & Retake Classification

```bash
afp-film triage --film films/<film_id> --take-id <TAKE_ID>
afp-film review --film films/<film_id> --take-id <TAKE_ID> --sheet <review.json>
```

`triage` scans evenly across the full clip duration (including the tail frame) and verifies `output_sha256`. Review reframes automatically expand to matching EDL `event_id`s when `05_edit.json` exists.

## 5. Scene Incremental Conform, Lock, & Finishing

```bash
afp-film scene-conform --film films/<film_id> --render
afp-film lock --film films/<film_id> --edl films/<film_id>/05_edit.json --reviewer <name>
afp-film finish --film films/<film_id> --dry-run
afp-film finish --film films/<film_id>
```

`finish` automatically synthesizes unsourced catalog Foley matches (when requested by shots in the cut), renders graded picture & titles/credits, mixes with audio rights & auto-ducking, validates QC + `versions` binding + opening/body AI disclosure pixels (`always` and `title_card`), and stages an immutable archive under `delivery/` (`release_ready=false` until Owner acceptance).

## 6. Offline Archive Verification

```bash
afp-film status --package films/<film_id>/delivery
```

Verifies every manifest hash, package integrity, and release disclosure compliance.
