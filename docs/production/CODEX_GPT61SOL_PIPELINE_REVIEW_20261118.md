# Independent Full-Pipeline Review (`gpt-6.1-sol` via Codex CLI) — 2026-11-18

## 1. Review Metadata
- **Reviewer:** OpenAI Codex CLI (`codex-cli 0.169.0-alpha.11.1`), model **`gpt-6.1-sol`**, `model_reasoning_effort = "high"`, sandbox `read-only`, `--ephemeral`
- **Codex Session ID:** `01a1ed76-055f-77e2-8c1a-8a15b2cff43e`
- **Audited Repository:** `D:\AI FILM MAKER\AFP-stable` (`feature/drama-preprod-p0`)
- **Audited Baseline HEAD:** `c3bd2f44b58d5bc417d00294fd2e637b13992e34`
- **Pinned Governance Policy (`POLICY_REF`):** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (`AGENTS.md` blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`)
- **Source Inventory Audited:** 65 core files (~15,741 lines across `tools/film.py`, `src/film_pipeline/production/*.py`, `src/film_pipeline/agentic/*.py`, `src/film_pipeline/drama/post.py`, `src/film_pipeline/film_package_export/*.py`), plus `pyproject.toml`, `docs/`, `providers/`, and `tests/`.

---

## 2. Verbatim `gpt-6.1-sol` Technical Report

# Verdict — FIX_FIRST

The pipeline has a usable supervised production path, but several recovery, accounting, cache and delivery defects prevent a daily-production `STABLE` verdict.

Audited checkout `D:\AI FILM MAKER\AFP-stable`, branch `feature/drama-preprod-p0`, HEAD `c3bd2f44b58d5bc417d00294fd2e637b13992e34`. The pinned policy exists and its `AGENTS.md` blob matches HEAD. The audit remained read-only, including the existing film07 changes and untracked outputs.

Evidence includes source/caller/test inspection, in-memory reproductions, actual ledger readback and PNG rendering into memory. MAR context access was rejected by the session’s `never` approval policy, leaving project-wide MAR reconciliation unverified.

## P0

No P0 finding confirmed within the inspected evidence.

## P1 findings

### 1. Stale reconciliation evidence can reopen an uncertain send

`_sent_receipts()` can replace an uncertain outcome with `FLOW_FAILED_NO_CLIP` through `_provider_no_clip()`. That helper trusts the `provider_no_clip` boolean alone, bypassing the intent/native/prompt hash checks in `resolved_receipt()`.

An in-memory reproduction accepted a wrong-hash reconciliation record. The resulting receipt disappeared from `unresolved_sends()`, allowing another submission while the original effect remains uncertain.

**Minimal fix.** Remove this boolean-only fallback and use the existing hash-bound resolution path exclusively. Add one regression covering a stale reconciliation file. `generate.py:463`, `generate.py:478`, `recovery.py:58`

### 2. Status underreports actual charged production cost

`report._production()` calls `money_ledger(log, {}, adjustments)`, excluding submitted receipts that never became registered takes.

Current readback confirms the discrepancy.

| Film | Status calculation | Ledger including receipts |
|---|---:|---:|
| film07 | 2,142 credits | 2,388 credits |
| film08 | 2,118 credits | 2,124 credits |

This also understates percentage-of-cap and credits-per-usable-second.

**Minimal fix.** Reuse `_sent_receipts()` with the existing fallback-price calculation when building the report. Preserve separate charged and pending amounts. `report.py:142`, `money.py:177`

### 3. Finish invalidation can reuse stale credits, audio and rendered chunks

Three dependency gaps interact.

- Titles consume sound attributions, but their fingerprint omits `audio/assets.json` and `audio/mix_plan.json`.
- Mixing supports WAV, FLAC and MP3 assets, while finish fingerprints audio bytes through `*.wav` only.
- `_CODE_SHA` invalidates finishing stages, but intermediate render-cache keys contain settings/source hashes and a manually fixed cache version. A changed renderer can therefore rerun a stage while reusing its old chunks.

**Minimal fix.** Hash the actual assets returned by existing sound/mix resolution, include attribution inputs in titles, and include a render implementation revision in intermediate keys. Add focused invalidation checks for attribution changes, MP3 replacement and changed render code. `finish.py:63`, `finish.py:74`, `render_cache.py:20`

### 4. Delivery can combine a new landscape master with an old portrait

Delivery verifies the portrait against its own recorded hash. It does not compare the `master_16x9` hash recorded by `versions` with the master currently being delivered.

A newly mixed and QC-passed landscape file can consequently ship alongside an earlier portrait.

**Minimal fix.** Require the recorded landscape source hash to equal `master_sha`, and bind the versions report to the exact cut report. Rebuild versions when either differs. `deliver.py:334`, `versions.py:566`

### 5. `title_card` disclosure has no rendered-pixel verification

`visible_label()` reads the EDL declaration. Pixel sampling runs only for `ai_label="always"`, while `check_release()` verifies disclosure records and metadata.

With `title_card`, an EDL can declare an AI line while the supplied master’s opening pixels omit it.

**Minimal fix.** Verify the opening disclosure on both delivered aspect ratios, using the declared title text and window. Retain the existing body-label checks. `deliver.py:151`, `deliver.py:354`, `disclosure.py:259`

### 6. A cold wheel installation cannot support the production journey

Package discovery correctly targets `src`, but package data includes only provider JSON.

Runtime dependencies remain outside the installed package.

- Foley loads repository-root `assets/sfx_catalog.json`.
- Export validation loads repository-root `docs/integration/film_package.v1.schema.json`.
- Importing `finish` hashes repository-root `tools/film.py`.
- Flow and fallback STT load scripts from `tools/`.
- No installed film CLI entrypoint is declared.

**Minimal fix.** Package the required resources and executable modules, resolve resources with `importlib.resources`, and expose the existing CLI through one installed entrypoint. Verify a wheel from a directory outside the checkout. `pyproject.toml:19`, `foley.py:17`, `validate.py:13`, `finish.py:18`

### 7. Lease acquisition starts its transaction after choosing the account

`isolation_level="IMMEDIATE"` starts the transaction at the first modifying statement. Both lease lookup and account selection occur beforehand.

The in-memory SQLite trace confirmed this order.

```text
SELECT existing lease
SELECT eligible account
BEGIN IMMEDIATE
INSERT lease
```

Concurrent callers can select the same idle account before either lease is committed.

**Minimal fix.** Execute `BEGIN IMMEDIATE` before both reads and add a database constraint enforcing one active lease per account. `lease_pool.py:82`

### 8. Lease release and quarantine allow incorrect settlement or redispatch

`release()` deducts credits even when the lease is already released. Releasing one six-credit lease twice reduced an in-memory account from 100 to 88.

Quarantine also marks active leases released without establishing whether their provider jobs completed. A generation can then be acquired by another account while its original job remains unresolved.

**Minimal fix.** Settle only an active lease with a matching ownership token, make repeated settlement idempotent, and retain an unresolved job reservation through quarantine. Scope lease identity to film, generation and version. `lease_pool.py:136`, `lease_pool.py:169`

### 9. A pending Muse handoff is invisible to the normal send guard

Muse claims live under `media/muse/*/state.json`. `generate` checks Flow/API intent receipts and registered takes.

After `muse dispatch`, a normal `generate` call can therefore submit the same generation before the Muse response is reconciled.

**Minimal fix.** Include unresolved Muse claims in the existing pending-send guard, preserving their provider-specific evidence and unknown monetary cost. `muse_gateway.py:208`, `generate.py:219`

### 10. Interrupted Muse copying cannot resume automatically

Muse persists `BINDING`, then copies directly into the final output filename. A process death during copying leaves a partial final file. The next ingest detects conflicting bytes and stops indefinitely.

**Minimal fix.** Copy to a task-owned temporary sibling, verify its hash, then atomically promote it. Preserve conflicting final evidence for inspection. `muse_gateway.py:275`

### 11. Incremental conform can label corrupted or editorially stale media `FRESH`

The conformer hashes accepted index entries and shared configuration. It does not verify source bytes, hash the conformed output, or include EDL trims/order/transitions in its identity.

A one-byte cached MKV with matching metadata was reported `FRESH` in an in-memory reproduction. Rendering also concatenates whole takes in shot-list order, so it cannot represent the actual edited scene.

**Minimal fix.** Use an EDL scene subset through the existing renderer, include its editorial inputs, verify accepted source hashes, and persist/check the output hash. `incremental_conform.py:56`, `incremental_conform.py:85`, `incremental_conform.py:140`

### 12. Dissolves cannot pass the external post-engine export contract

`build_timeline()` exports overlapping TAKE ranges from a dissolve. The v1 validator rejects overlapping events.

A synthetic two-shot, 0.5-second dissolve reproduced `event b overlaps the previous event`. Consequently, `mix --engine` fails for an otherwise supported edited cut.

**Minimal fix.** Represent the already-rendered picture as a non-overlapping v1 timeline, explicitly preserving transition provenance. Add the dissolve export case to the existing exporter tests. `story.py:38`, `validate.py:51`

## P2 findings

### 13. Pre-send critic crashes when compiled prompts are absent

Its fallback calls `_Plan.video_prompt()`, which does not exist. A cold-plan inspection reproduced `AttributeError`.

**Minimal fix.** Return a structured `PLAN_MISSING` blocker, or reuse a side-effect-free compiler entrypoint already shared with planning. `pre_send_critic.py:65`

### 14. Causal repair consumes a different failure vocabulary from production QC

Normal review ingestion produces `PROMPT`, `START_FRAME`, `PROVIDER_LIMIT` and `STAGING`. The causal router expects detailed codes such as `OFF_FRAME_INTRUSION`.

Consequently, ordinary causes reach its generic restage fallback. An absent cause is specifically guessed to be off-frame intrusion. Its rejection counter also resets with each shot version.

**Minimal fix.** Reuse `retake_plan()` for existing cause decisions. Require explicit defect evidence for detailed causal routing, and count the authorized repair budget across version history. `qc_model.py:37`, `causal_repair.py:66`, `causal_repair.py:89`

### 15. Agentic readiness, pricing and checkpoint labels overstate their evidence

The scheduler trusts accepted index entries without checking current media/review provenance or pending sends. The router assumes six credits regardless of shot duration. CP2 becomes `APPROVED` from accepted-take counts without a pilot-reel decision.

**Minimal fix.** Label the scheduler result as dependency readiness, derive cost from the existing route registry and `shot_seconds()`, and require a bound pilot-review receipt for CP2 approval. `scheduler.py:24`, `capability_router.py:49`, `capability_router.py:100`

### 16. Film03 golden compatibility can be restored through the existing flag

Current output drops the historical eyeline clause for `SC03_g1` and `SC05_g2`, changing both video and still prompts and their gate3 word counts.

An in-memory historical-description substitution restored every film03 golden text and the gate3 record. Film06, film07 and film08 all enable `interaction_contract`.

**Minimal fix.** Route historical description behavior through `interaction_contract=False`, using a nonserialized compatibility setting. Retain modern description behavior and current `off_partner` serialization for opted-in films.

The experiment preserved all **617 modern prompts, 617 rendered storyboard PNG hashes and 617 fingerprints** between baseline and compatibility trials. `coverage.py:95`, `plan.py:203`, `storyboard.py:49`

### 17. The Dola invariant test depends on unrelated worktree dirtiness

`test_05_invariants` examines all tracked modifications in the repository. Direct read-only invocation failed against the inherited film07 changes.

Its actual fixture directory is `projects/quality_v2_010a_dola_re_authority`.

**Minimal fix.** Bind protection checks to explicit contract paths/hashes and changes caused by the operation under test. Retain the no-generation-ledger and no-MP4 assertions, and check the Git subprocess exit status. `test_v2_010a_dola_re_001.py:60`

### 18. Ledger adjustments accept nonfinite values and duplicate identities

`LedgerAdjustment.delta` accepts `NaN`. The resulting spent total is `NaN`, and `spent + cost > cap` evaluates false. Explicit adjustment IDs also lack uniqueness/idempotency enforcement.

**Minimal fix.** Require finite monetary/checkpoint numbers and enforce unique adjustment IDs. Repeating an identical ID should return its existing entry, while conflicting content should fail. Checkpoints currently remain recorded observations without balance reconciliation. `money.py:24`, `money.py:76`, `generate.py:261`

### 19. Triage sampling misses the end of longer clips

`_gray_frames()` floors sampling frequency at one frame per second and caps output at 12 frames. A 15-second take therefore receives approximately its first 12 seconds of visual analysis, leaving the tail outside the advertised scan.

**Minimal fix.** Sample evenly across the complete duration, including its final frame, and bind the report to the checked output hash. Keep its advisory status. `dailies_triage.py:35`, `dailies_triage.py:102`

### 20. Review-supplied reframes use generation IDs where rendering requires event IDs

Review ingestion writes `titles/reframe.json` using `generation_id`. Titles validates and rendering resolves reframes by `event_id`.

An EDL event named `E12` using take `SC01_g1_t1` consequently receives an unknown-event blocker after its review supplies a crop.

**Minimal fix.** Resolve the reviewed take to its actual EDL event IDs before merging the reframe. Cover renamed and repeated events. `takes.py:418`, `takes.py:439`, `titles.py:319`

## Agentic v2 integration gap

| Boundary | Current condition | Smallest production connection |
|---|---|---|
| Parallel dispatch | CLI and `generate()` hold the film lock throughout provider execution. Different CDP endpoints still contend on that film lock. | Transactionally reserve intent, take number and budget before releasing the short film-write section. Retain the CDP composer lock throughout browser mutation. |
| Account identity | `account_scope` affects filtering, but account identity is absent from persisted send receipts and recursive resend arguments. | Persist account identity and carry it through resend/recovery. |
| Critic | Called by `agentic-plan`, absent from the live send path. | Run the shared pre-send inspection against the exact compiled request and approved inputs. |
| Repair | Produces suggestions without applying the established retake/version contract. | Translate an approved repair into the existing pickup mechanism and normal gates. |
| Conform | Scene outputs have no connection to `edit`/`finish`. | Reuse EDL-aware rendering and its cache provenance. |
| Foley | Standalone materialization exists. `finish` omits it, while missing SFX produce warnings. | Add an explicit Foley preparation step for requested catalog matches before mixing. Record unmatched cues for review. |

## Editing, audio and runtime assessment

- **Audio has substantive safeguards.** Four stems exist, the production track retains J/L-cut audio, ambience/music use dialogue-driven ducking, AAC true peak is measured after encoding, and `mix_cut()` blocks an out-of-spec result. `dialogue.wav` contains the native production composite, which limits speech-specific ducking and STT interpretation.
- **Frame accuracy needs boundary qualification.** Rendering fixes the profile at 24 fps and 1280×720, while headers accept other values. Fine rendering rounds starts to frames while retaining fractional lengths. Portrait chunk lists provide exact durations, while landscape chunk lists omit them. Existing join tests cover VUI normalization and video frame count, with additional audio-boundary and fractional-duration coverage needed.
- **Crash protection is uneven.** Finish state and core JSON replacement are durable, and delivery uses staged immutable archives. Several render/QC subprocesses still lack timeouts, and several stage records use direct writes. Corrupt master-QC or manifest JSON can also raise through gate evaluation.
- **Gate synchronization preserves archived custody by default.** Delivery explicitly forces synchronization before publication. Keep archive-bound acceptance separate from mutable header summaries, and turn malformed evidence into structured blockers.

## Daily-production stabilization checklist

- [x] Fix hash-bound negative reconciliation and shared pending-provider visibility first.
- [x] Unify status and send accounting, validate finite amounts, and make settlement idempotent.
- [x] Complete finish dependencies and version render-cache keys.
- [x] Bind portrait, cut report, QC and delivery to the same candidate. Verify opening disclosure pixels.
- [x] Restore film03 through the existing compatibility flag and scope the Dola invariant. Run full pytest on the exact candidate to establish `0 FAIL`.
- [x] Qualify installed-wheel operation outside the checkout, including resources, CLI, Flow helpers and fallback STT.
- [x] Expose the existing preflight as a read-only `doctor` command. Check supported render profile, fonts, required FFmpeg capabilities, packaged resources, optional engine availability and scratch requirements.
- [x] Use existing `run_ffmpeg()` bounds and `atomic_json()` for remaining production paths. Return structured failures for corrupt evidence.
- [x] Add one boundary fixture covering fractional trims, dissolve plus J/L audio, portrait cues and many PCM chunks. Verify decoded frame/sample counts and sound continuity across joins.
- [x] Integrate supervised agentic execution after lease/receipt corrections, retaining Owner checkpoints and the existing long-film stability acceptance requirement.

---

## 3. Tech Lead Disposition & Fix Mapping (2026-11-18)

| Item | Finding / Gap | Action Taken | Primary Files | Verification Test(s) |
|---|---|---|---|---|
| P1 #1 | Boolean-only `_provider_no_clip` fallback | Removed boolean shortcut; rely exclusively on hash-bound `recovery.resolved_receipt()` | `src/film_pipeline/production/generate.py` | `test_gpt61sol_stabilization.py` |
| P1 #2 | `status` omits unregistered charged receipts | Wired `_sent_receipts` + `_fallback_price` into `report._production()` with separate logged vs unresolved breakdown | `src/film_pipeline/production/report.py` | `test_gpt61sol_stabilization.py`, `test_production_report.py` |
| P1 #3 | Finish cache/invalidation gaps | Added `audio/assets.json`, `audio/mix_plan.json` to `titles`; `*.wav`/`*.flac`/`*.mp3` to `mix`; auto-foley step; `_RENDER_IMPL_SHA` in `render_cache.py` | `src/film_pipeline/production/finish.py`, `src/film_pipeline/production/render_cache.py` | `test_gpt61sol_stabilization.py`, `test_production_finish_p20.py` |
| P1 #4 | Landscape/portrait binding mismatch in `deliver` | Bound `versions.json` to `cut_report_sha256` and verified `master_16x9.sha256 == master_sha` in `deliver()` | `src/film_pipeline/production/versions.py`, `src/film_pipeline/production/deliver.py` | `test_gpt61sol_stabilization.py`, `test_production_deliver.py` |
| P1 #5 | `title_card` disclosure lacks opening-pixel check | Added `title_card_evidence()` pixel contrast check on 16:9 & 9:16 opening card when `visible_label.text` is declared | `src/film_pipeline/production/deliver.py` | `test_gpt61sol_stabilization.py`, `test_production_deliver.py` |
| P1 #6 | Cold wheel install incomplete | Moved CLI to `film_pipeline.cli`, added `afp-film` script, packaged `sfx_catalog.json`, `film_package.v1.schema.json`, `_flow_ui/*.py`, `importlib.resources` fallbacks | `pyproject.toml`, `src/film_pipeline/cli.py`, `tools/film.py`, `foley.py`, `validate.py`, `flow_ui_adapter.py`, `dialogue_stt.py`, `finish.py`, `rehearsal.py` | Isolated wheel install outside repo + `afp-film doctor` |
| P1 #7 | Lease `acquire()` transaction starts after SELECTs | Forced `isolation_level=None` + explicit `BEGIN IMMEDIATE` before reads + unique partial index on active account | `src/film_pipeline/agentic/lease_pool.py` | `test_gpt61sol_stabilization.py`, `test_agentic_v2.py` |
| P1 #8 | Lease `release()` double debit & quarantine release | Added `lease_token`, idempotent settled `release()`, `QUARANTINED_PENDING_RECONCILE` state, and `(film_id, generation_id, shot_version)` scope | `src/film_pipeline/agentic/lease_pool.py` | `test_gpt61sol_stabilization.py`, `test_agentic_v2.py` |
| P1 #9 | Pending Muse dispatch invisible to `generate` | Merged `muse_gateway.pending_muse_claims()` into `generate.build_payload` & `recovery.pending_receipts` | `src/film_pipeline/production/muse_gateway.py`, `src/film_pipeline/production/generate.py`, `src/film_pipeline/production/recovery.py` | `test_gpt61sol_stabilization.py`, `test_muse_gateway.py` |
| P1 #10 | Interrupted Muse copy blocks retry | Staged copy via sibling temp file + SHA-256 check + atomic `os.replace()` | `src/film_pipeline/production/muse_gateway.py` | `test_gpt61sol_stabilization.py`, `test_muse_gateway.py` |
| P1 #11 | Incremental conform trusts 1-byte MKV / ignores EDL | Verified source hashes & output hash in `.scene.json`, included EDL & color inputs, rendered scene EDL subset | `src/film_pipeline/agentic/incremental_conform.py` | `test_gpt61sol_stabilization.py`, `test_agentic_v2.py` |
| P1 #12 | Dissolve overlap fails `film_package` v1 export | Clamped overlapping dissolve out-frame to `frames(nxt["start_s"], fps)` with explicit warning while keeping schema compliance | `src/film_pipeline/film_package_export/story.py` | `test_gpt61sol_stabilization.py`, `test_film_package_export.py` |
| P2 #13 | `PreSendCritic` crashes on cold plan | Emitted `PLAN_MISSING` `BLOCK` and compiled via `_Plan.build()` without nonexistent `video_prompt()` | `src/film_pipeline/agentic/pre_send_critic.py` | `test_gpt61sol_stabilization.py` |
| P2 #14 | `CausalRepairRouter` vocabulary & cross-version cap | Mapped QC `Cause` values & `retake_plan()` rules, empty cause -> `CLASSIFY`, counted rejections across versions | `src/film_pipeline/agentic/causal_repair.py` | `test_gpt61sol_stabilization.py`, `test_agentic_v2.py` |
| P2 #15 | Scheduler / Router / CP2 evidence overstatement | Checked clip/review existence, derived credit quote via `resolve_route`/`shot_seconds`, required `pilot_approval.json` for CP2 `APPROVED` | `src/film_pipeline/agentic/scheduler.py`, `src/film_pipeline/agentic/capability_router.py` | `test_gpt61sol_stabilization.py`, `test_agentic_v2.py` |
| P2 #16 | `film03` golden regression | Restored historical 3rd-person partner fallback when `interaction_contract=False` (`film04`-`film08` 100% untouched) | `src/film_pipeline/production/plan.py` | `test_production_film03_golden.py`, `film06/07/08` hash invariance |
| P2 #17 | `test_05_invariants` fails on unrelated dirty files | Scoped `git status --porcelain` check to Dola/010a paths with `check=True` | `tests/test_v2_010a_dola_re_001.py` | `test_v2_010a_dola_re_001.py` |
| P2 #18 | `NaN`/`Inf` & duplicate `adjustment_id` in `money.py` | Enforced finite validators and unique/idempotent `adjustment_id` handling | `src/film_pipeline/production/money.py` | `test_gpt61sol_stabilization.py`, `test_money_adjustments.py` |
| P2 #19 | `dailies_triage` misses clip tail past 12s | Even sampling across full duration + final frame + `output_sha256` verification in report | `src/film_pipeline/production/dailies_triage.py` | `test_gpt61sol_stabilization.py`, `test_foley_and_triage.py` |
| P2 #20 | Review reframe keyed by `generation_id` vs `event_id` | Resolved to EDL `TAKE` `event_id`s on ingest and fallback expansion in `titles.py` | `src/film_pipeline/production/takes.py`, `src/film_pipeline/production/titles.py` | `test_gpt61sol_stabilization.py` |
| Tech Lead #1 | Multi-account parallel `generate()` `FILM_BUSY` + lost `account`/`sent_on` | Decoupled `composer_lock` & short `film_lock(timeout_s=15)`; persisted `account` & `sent_on`; forwarded `account_scope` in `auto_resend` | `src/film_pipeline/production/runtime.py`, `src/film_pipeline/production/generate.py`, `src/film_pipeline/production/recovery.py` | `test_gpt61sol_stabilization.py`, `test_flow_shard_lock.py` |
| Tech Lead #2 | FFmpeg concat quoting, missing timeouts, silent `normalize_loudness`, corrupt JSON crashes, CLI wiring | Escaped quotes + `.resolve()`, applied `run_ffmpeg`, guarded `-inf` in `normalize_loudness`, guarded corrupt JSON in `deliver`/`gate_checks`, added `doctor`/`lease`/`scene-conform`/`generate --critic` & boundary test | `versions.py`, `edit.py`, `post.py`, `deliver.py`, `gate_checks.py`, `cli.py`, `DAILY_PRODUCTION_RUNBOOK.md` | `test_gpt61sol_stabilization.py`, full RC `pytest` (`0 FAIL`) |
