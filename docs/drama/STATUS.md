# 2026-11-21 — S1 Broker v2 built (commits f3c6dcf8..620d4c88); last Codex round REJECT, its 2 findings fixed, not re-reviewed

- Goal: STUDIO_ARCHITECTURE.md v3 S1 (§3/§5/§6/§9, §11 row). POLICY_REF 1d500274 pinned; no POLICY_SYNC needed.
- Built: `agentic/broker.py` (SQLite, user_version 2, migrated in place from the step-4 pool; states FREE/BUSY/
  COOLDOWN/NEEDS_LOGIN/QUARANTINED/HELD/HALTED; slots flow 1, muse video 6 / stills 4; epoch; quota constant or
  probed; re-login <= 1 per 2 h and 2 failures -> NEEDS_LOGIN; profile claim per epoch); one exclusive batch lease
  per account; atomic admission (halt + epoch + account quota + film budget + provider cap + machine cap per unit,
  units credits/VND/USD/muse_requests, "unlimited"); pre-Enter / pre-login checks in one transaction; account
  warning = quarantine + machine halt, never auto-cleared. `agentic/broker_api.py` + `afp-film broker ...` (JSON,
  exit 0/1/2/3) for an external lane; `afp-film accounts` lists broker ids/labels only. Direct `afp-film generate`
  admits through the broker; `AccountLeasePool` is a step-4 facade.
- Decisions (why):
  - Pre-S1 spend is imported once per films directory (`legacy_imports`); admission refuses LEGACY_IMPORT_PENDING
    until then, and while a migrated open step-4 send has no price (it is priced from its receipt, custody kept).
    Why: the machine/provider caps must see all spend sent before S1.
  - Under a film budget a take id is one live reservation (TAKE_REUSED); a reservation is credited only with the
    ledger's verified amount for that take in the same unit; rows sharing a take id count in full. Why: Codex
    R2-2/R3-1/R4-1, never undercount money.
  - A replay of an ACTIVE lease must be identical (unit, scope, job kind, provider, children and prices).
  - Settlement amounts must be finite and >= 0. `set_halt(db=...)` locks the broker the caller admits against.
- Codex (gpt-6.1-sol, read-only; prompts/outputs in `_archive/s1_broker_20261120/`): round 1 REJECT (5), round 2
  REJECT (3), round 3 REJECT (3), round 4 REJECT (2: per-take ledger credit, halt lock with --db). Every finding was
  fixed with a test; the round-4 fixes were NOT re-reviewed (3-round limit reached).
- Tests (TMP/TEMP on D:): required files green: test_broker_s1 39, test_lease_exclusivity 21 + 1 skip (env: no
  `websockets`), rehearsal_cli_e2e, offframe_protection, edge_intrusion, defect_custody, provider_routing,
  production_generate, production_halt, production_recovery_p20. Full suite on the WIP: 1 failed / 2667 passed /
  204 skipped; the failure (FILM_BUSY, global lock under LOCALAPPDATA) came from a second pytest run in parallel and
  passes alone: env.
  `uv run python -m pytest tests/test_broker_s1.py tests/test_lease_exclusivity.py -q --basetemp "D:/AI FILM MAKER/_tmp_pytest/s1"`
- Open: no independent review of the round-4 fixes; rehearsal pools and the machine broker share one halt file.
- Next: S2 (daemon, job journal, lanes) on top of `broker_api`; an optional extra Codex round on f3c6dcf8..HEAD.

---

# 2026-11-20 — Studio architecture v3 agreed; Muse-first policy; POLICY_REF pinned; S1 started

- Design: docs/production/STUDIO_ARCHITECTURE.md v3. Codex v2 review was ACCEPT_WITH_FIXES (F1-F6 applied). The
  Muse Tech Lead (session local_e75f8a13) reviewed v3 and accepted it; its points are marked M1-M10.
- Owner decisions 2026-11-20 (OWNER_POLICY.md):
  - Muse is the video and stills provider: max resolution, no request cap, no spend approval.
  - Flow and Vilao are paused; every Flow spend needs the Owner.
  - Out of quota or failed login on an account: tell the Owner and continue on the other accounts.
  - CAPTCHA, verification or warning: stop all Muse sending.
  - Pilot P1 runs on Muse; order S1-S2-S3-S5-P1-S4-S6.
- **D0: POLICY_REF = 1d5002742ab9c3990fb369af36aaab6c958c2d56** (Owner accepted in chat: "Accept, start S1"). Pin
  it in every worker handoff.
- Muse side: the CAPTCHA currently fails over to another account in standalone Muse. The Muse TL is fixing it
  (Codex round 2); until then that is a known gap in the standalone production path.
- Muse verification report: docs/production/muse/Bao-cao-tong-hop-kiem-chung-Muse-FINAL.md.
- Next: S1, Broker v2, run in its own session.

---

# 2026-11-20 — Upgrade step 5 done: edge-intrusion detector (advisory) + defect custody

- Detector `production/edge_intrusion.py`: 12 fps, frame-to-frame camera-motion compensation, changed pixels in edge
  strips with persistence; YuNet faces optional (model in production/models/, Apache-2.0, 232 KB) and off by default
  (faces caught only 4-8% of intrusions). Labelled set: film07 50 pos / 263 clean, film08 28 / 242
  (manifest + feature cache in `_archive/step5_edge/`). Calibration doc:
  docs/production/edge_intrusion_calibration_20261120.md.
- Targets (held-out recall >= 0.80 at FPR <= 0.15) NOT met: tuned on film07 -> film08 0.75 / 0.214; shipped point
  (tuned on film08) film07 0.78 / 0.076, film08 0.75 / 0.074 but film08 is no longer a clean held-out (looked at
  its misses). Old 12-frame check: film07 0.56 / 0.053, film08 0.21 / 0.070. Misses: intruder already in frame 0,
  tiny/brief slivers; false alarms: push-ins with shoulder parallax, subject turning/exiting at the edge.
- So triage emits `EDGE_INTRUSION_SUSPECT` as INFO in result["signals"] (not a warning, never a reject). Flip
  `EDGE_INTRUSION_SEVERITY = "WARN"` only after a clean new film's first batch meets the targets. Old check kept.
- Custody: `production/defects.py` registry (OFFFRAME_INTRUSION, IDENTITY_DRIFT, WRONG_SPEAKER_LIPSYNC,
  DIALOGUE_TRUNCATED, GAZE_EYELINE_DRIFT, PROP_CONTINUITY_BREAK, CAMERA_INSTABILITY, PROVIDER_ARTEFACT; only
  PROVIDER_ARTEFACT allows a plain retry; only OFFFRAME_INTRUSION may confirm EDGE_INTRUSION_SUSPECT).
  `TakeQc.defects` (code, clip_sha256 = take hash, time ranges, optional source signal + detector version); a v2
  REJECT needs >= 1 defect. causal_repair routes from reviewed defects, unknown codes -> STOP_UNKNOWN_DEFECT (the
  old auto-retry fallback is gone); signals alone never trigger a repair. film06-08 reviews and Gate 4 unchanged.
- Not done: defects in dailies_template / CLI; no time-range upper bound check.
- Next: step 6 = Owner-authorised pilot (new film is Owner-reserved). Also pending Owner: Muse consolidation D0-D4.

---

# 2026-11-20 — Upgrade step 4 done: one sender, exclusive leases, CLI rehearsal with faults

- One sender: `afp-film generate` is the only send path. flow_pool_runner.main() is retired (prints the generate
  route, exit 2); its helpers stay importable. flow_send's account-warning detection now uses the pool runner's
  wording (EN + VI unusual activity / verify you are human), package and tools/ copies byte-identical.
- Leases (agentic/lease_pool.py, production/leases.py): one machine pool `<state dir>/lease_pool.sqlite3` (same state
  dir as the halt). An ACTIVE lease goes only to its holder; release needs the token; accounts with an ACTIVE or
  QUARANTINED_PENDING_RECONCILE lease are never picked. Accounts may carry cdp_endpoint/project (`lease register`).
- generate: every non-mock Flow send takes a lease in Phase A (none -> NO_ACCOUNT_LEASE with the reason); dry runs
  only warn. Outcome settles it: charged -> credits spent + cooldown; never submitted (refusal, or crash while the
  receipt is still PREPARING) -> released, 0 credits; crash after SUBMITTING or AMBIGUOUS -> held until `reconcile`
  then `afp-film lease settle --film F --take T`; FLOW_ACCOUNT_WARNING -> halt + account quarantined. Back to work:
  `halt clear`, reconcile + settle the warned take, `lease unquarantine --account A --by ... --reason ...`.
  Knobs: AFP_LEASE_COOLDOWN_S (60), AFP_LEASE_MIN_RESERVE (20). Accounts must be registered before any live send.
- Rehearsal through the CLI: a rehearsal package always uses mock_runner (never real Flow), its halt goes to
  `<copy>/takes/production_halt.json`, AFP_REHEARSAL_FAULT (crash_before_submit, crash_after_submit,
  crash_after_download, account_warning, provider_failed, slow:N) works only on rehearsal packages. CLI `reconcile`
  refuses rehearsal packages (it would scan live Flow). tests/test_rehearsal_cli_e2e.py (12 tests) drives two film03
  scenes through generate -> review -> cut ... deliver and each fault, incl. concurrent duplicates (exactly one send).
- Known gaps: a hard-killed sender leaves its lease ACTIVE under a dead holder (account still blocked, settle works;
  no expiry); cap exhaustion cannot be rehearsed (rehearsals skip budget, tested in-process instead); `afp-film
  rehearse` on film03 stops at plan (SC03_g1 preflight-BLOCKED fixture); AI_LABEL_NOT_BURNED false-fails one sampled
  frame of a 16 s mock body (body t=4.15 s) — investigate before a real delivery relies on it.
- Next: step 5 (edge-intrusion detector calibrated on labelled rejects + clean takes).

---

# 2026-11-20 — Upgrade step 3 done: off-frame protection for new films

- `film.json` `defaults_version` (1 = films shipped before 2026-11-19, 2 = new defaults); `scaffold` writes 2.
  `preflight.offframe_protection` (None = follow defaults_version, explicit value wins). When on, PreprodSection
  expands it once: every scene id joins safeguard/clear_eyeline/listener_unplaced/de_personify_off_frame/
  interperson_no_touch lists and object_gaze_neutral_eyeline is on, so plan, interaction, critic and generate all
  read the same typed settings. Raw 03_preprod.json and its hash are untouched.
- Leak check `interaction.offframe_leaks`: single-visible shot naming an off-frame character id/handle outside the
  dialogue (quoted text and the shot's script lines are cut out, so spoken names stay legal). Protection on:
  generate adds blocker `CROSS_ATTENTION_LEAK` (dry runs show it, no `--critic` needed) and the critic's
  CROSS_ATTENTION_LEAK_RISK is BLOCK; protection off: unchanged (critic WARN on SINGLE only).
- film08 measured offline (copy, protection forced on): single-visible shots leaking an off-frame name 184/285 -> 0/285
  (before: "the older man" x83, "the woman" x77, "the young man" x24, e.g. SC01_g02 "The woman speaks to the older man").
- film03-08 stay defaults_version 1: compiled prompts byte-identical, accepted takes not stale
  (tests/test_offframe_protection.py checks film06/07/08 against accepted prompt_sha256).
- Not proven live: whether the protected prompts actually cut edge intrusion; that is step 5 (detector) + step 6 (pilot).
- Next: step 4 (one sender + lease exclusivity + rehearsal).

---

# 2026-11-19 — Upgrade steps 1-2 done (docs/production/UPGRADE_PLAN_20261119.md)

- Step 1, honest QC evidence: `TakeQc.evidence_version` 2 + `GroupCheck.observed` (frames_viewed/frames_total/
  full_playback/audio_listened). v2 rules: judged checks need `observed`; FULL_MOTION/CUT needs full playback or every
  frame viewed; only `human:` may claim playback/listening, so an agent cannot PASS audio/sync by judgment (use auto:
  tools); FULL_MOTION contradicting "contact strip / sampled / not listened" evidence is refused. New films
  (`scaffold`) get `film.json` `qc_evidence_version: 2`; ingest and Gate 4 refuse older reviews there. film03-08 stay
  v1, unchanged. review-ui no longer hardcodes FULL_MOTION: it records played coverage (>=98% = full playback,
  >=90% unmuted = listened; counts 1.5x as played).
- Step 2, machine-wide halt: `production/halt.py`, file `~/.afp/production_halt.json` (env AFP_STATE_DIR /
  AFP_HALT_FILE). Set by any FLOW_ACCOUNT_WARNING outcome in generate, flow_pool_runner's warning detector and any
  lease quarantine. While set: generate refuses (and re-checks right before the Enter), lease acquire returns None,
  `doctor --operation send` is not ok, no auto-resend. Only `afp-film halt clear --by human:|agent:<id> --reason` clears
  it; history in production_halt_history.jsonl. tests/conftest.py isolates the halt file for every test.
- film08 SC10_g05_t1: already reconciled (native evidence hash-bound, FLOW_FAILED_UNUSUAL_ACTIVITY -> PROVIDER_FAILED,
  booked as charged by the Flow registry). 2124 is the official spend; lowering it needs account 03's real balance.
- test_agentic_v2 film08 checkpoint assertions updated to APPROVED after the Gate 6 acceptance.
- Next: step 3 (off-frame intrusion prevention for new films) then step 4 (one sender + lease exclusivity + rehearsal).

---

# 2026-11-19 — Pre-upgrade baseline (current state)

- Full suite at 88ebf731 + this commit: **2532 passed, 202 skipped, 0 failed** (28 min;
  log `D:/AI FILM MAKER/_archive/cleanup_20261119/full_tests_20261119.log`).
- Films: film06, film07 delivered and accepted; film08 Gates 1-5 PASS, archive `20261118T044106-40b49011c3`
  verifies (38 files, 0 hash mismatch), **Gate 6 OWNER_PENDING**. film05 Gate 6 waits on rights. film03/film04
  are golden test fixtures (20+ tests read them): their status rows are expected, do not move or "close" them.
- film08 credits: status reports 2124, take log 2118. The 6-credit gap is `SC10_g05_t1` (account 03,
  2026-11-18 05:52): Flow "unusual activity" tile, no clip, recorded as charged on purpose without touching the
  account. Earlier such tiles said "not charged"; add a `film.py ledger-adjust` only after reading account 03's
  real balance. Account 03 was flagged on 2026-11-18: treat it as halted until checked.
- MAR worktree f31dc: its 7 commits are on `feature/dola-session-oneclick-001` (safe); its 4 untracked
  dola_daily_quota files are backed up in `_archive/cleanup_20261119/`.
- Pushed 2026-11-19 on Owner's "Push": feature/drama-preprod-p0 40dbd4f5..788df5ee (875 commits) to origin.
- Owner-reserved and open: Gate 6 film08 review; film05 rights; fate of the paused Film120-Gemini worktree.
- Next: production-system upgrade from this baseline.

---

# 2026-11-19 — Project cleanup (Owner: "dọn dẹp dự án, rác cũ, phần đã xong, worktree đã xong")

- Worktrees removed (branches kept, nothing unmerged lost): AFP-provider-a, AFP-film-package,
  AI-Film-Pipeline-System-Ship-20261110, AI-Film-Pipeline-Claude-Forensics, -Live-Qual, -Overnight,
  -ZCode-ControlledShot-20261025, -S2-Audio-Review, C:/Users/ADMIN/.codex/worktrees/film-e2e-ship. Empty stub AFP-shard-3 removed.
- Their untracked/uncommitted content is in `D:/AI FILM MAKER/_archive/cleanup_20261119/` (3 scratch tgz,
  S2 OWNER_REVIEW tgz, ZCode uncommitted .patch).
- Moved (not deleted) from C:/film-work to `E:/AFP-Archive/C-film-work/`: film07-full, film07-pilot, film07_review,
  film07_*.log, film08 (working files; delivered archive is in films/), irene-v3-20261110, production-stability-p20.
  Paths cited earlier in this file under C:/film-work/{film07-*,film08,production-stability-p20} now live there.
- Deleted: AFP-stable/build/, old Temp pytest/playwright dirs, 3 stale Claude scratchpads, empty shard3 patch.
- C: 6.3 -> 8.3 GiB free.
- Kept: AI-Film-Pipeline (main checkout, 50 dirty), Film120-Gemini (paused WP, 1.2 GB untracked evidence),
  Muse worktrees + C:/film-work Muse dirs (active), MAR worktrees (MAR tool state; f31dc holds 7 commits on no branch),
  _research_pilots and _exports (written in last 72 h). Owner then said delete what is not needed:
  C:/AFP-Live-v3-20261110 worktree removed (superseded v3 runtime; commits stay on codex/real-film-v3-20261110;
  OWNER_REVIEW kept as _archive/cleanup_20261119/AFP-Live-v3_OWNER_REVIEW.tgz). C:/AFP-QA-20261110-audit and
  C:/AFP-Cold-v3-20261110 are not needed but the agent's delete was blocked; Owner deletes them by hand.

---

# 2026-11-18 — Comprehensive System Audit, Quality Hardening & Production Speed Optimization (All 2,529 Tests PASS, Zero Failures)

- **System-Wide Multi-Worktree Audit & Custody Verification:**
  - Audited root repository (`D:/AI FILM MAKER/AI-Film-Pipeline`), active stable worktree (`D:/AI FILM MAKER/AFP-stable`), all 17 Git worktrees, 6 film packages (`film03`..`film08`), and the parallel Muse master (*The Spare Jacket* at `C:/film-work/black-drama-eutlzb7ycky/expanded_27min/THE_SPARE_JACKET_FINAL_25MIN.mp4`, SHA-256 `a9d502ed...`).
  - Verified `POLICY_REF = 45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (blob `6cab2103...`) identical across all worktrees.
  - Confirmed 100% custody and manifest integrity across delivered archives via `afp-film status --package`: `film06_six_am` (`2b1c1405...`, Gates 1–6 PASS), `film07_first_shift` (`f3476aa2...`, Gates 1–6 PASS), and `film08_chain_of_custody` (`357d662d...`, Gates 1–5 PASS, `release_ready=True`, Gate 6 `OWNER_PENDING`).
  - Protected all 47 dirty/untracked paths at root and protected 2 dirty files in `AFP-stable` (`films/film07_first_shift/_author.py`, `films/film07_first_shift/media/takes/SC12_g23_t1.reconcile.json`).
- **Storage & Scratch Overflow Engine:**
  - Integrated `preflight.scratch_dir()` with disk free-space scanning and auto-overflow to large secondary storage (`E:\AFP-Scratch`, 183.5+ GiB free) when system drive `C:` has < 10 GiB available.
  - Added `scratch_tempdir()` across `assemble()`, `normalize_loudness()`, `mix()`, `versions()`, `color()`, and `deliver()` to prevent disk exhaustion errors during 30-minute film builds.
- **Cinematic Quality Hardening & Defect Elimination:**
  - **Dialogue STT Acceleration & Dual-Engine Verification:** Replaced per-cue FFmpeg subprocess slicing with 1-pass 16kHz mono PCM decoding (`decode_mono_16k_pcm`) + memory slicing (`slice_pcm_16k`) and parallel `KaldiRecognizer.Reset()`. Slashed 270-cue `film08` scan time from >300s to **56.56s** (5.3x speedup). Added automated offline second-opinion STT verification using cached `faster-whisper-small.en` (recovering 1.0 recall on short/homophone errors like `SC08_g13` and `SC11_g02` without API spend).
  - **Balanced Subtitle Auto-Wrapping:** Implemented `_wrap_subtitle_lines()` and `subtitle_png(..., max_w=1120)` in `drama/post.py`. Dynamically wraps long dialogue lines into balanced two-line blocks with height-adaptive translucent backdrops, eliminating margin overflow (e.g., `film08 SC02_g08` 1247px) while maintaining exact pixel parity for lines <= 1120px.
  - **Multi-Angle Color Consistency:** Added `ColorPlan.group_by_camera: bool = False` (groups by `side:subject`), eliminating cross-angle color skew between bright window and dim bar directions in dialogue scenes. Multithreaded `frame_stats()` and `verify` across `render_workers(jobs)`.
  - **Master QC Parallelization:** Parallelized all 5 QC metrics (`frame_series`, `ebur128`, `clipping`, `silent_gaps`, `dialogue_activity`) across 5 concurrent workers, with process timeouts (`media_timeout()`) and atomic JSON writes.
  - **Dailies Triage Cache & Optical/Acoustic QC:** Implemented content-hash caching at `<film>/media/triage/<take_id>.json`, unified `warnings`/`flags` key sync, and added optical/acoustic hazard checks (`FROZEN_TAKE_RISK`, `LUMA_FLICKER_SPIKE`, `SPEECH_TRUNCATED_AT_TAIL`, `AUDIO_CLIPPING_RISK`) with parallel `triage_batch()`.
  - **Planning False-Positive Resolution:** Updated `planning_issues()` to ignore `RISK_NO_FALLBACK` for generations having an `ACCEPTED` take matching current `shot_version` and existing `review_file`.
  - **Pre-Send Dialogue & Pacing Critic:** Added `STAGE_DIRECTION_IN_DIALOGUE`, `END_STILL_NOT_READY`, and `DIALOGUE_PACE_OVERFLOW` checks with multi-scene Fountain `(scene_id, line_no)` dialogue lookups.
- **Production Speed & Concurrency Upgrades:**
  - Parallelized `incremental_conform` and `capability_router` via `hash_files_parallel()`, sharing `verified_hashes` and `wave_info` to drop `agentic-plan` execution time from 43s to **12.44s** (3.5x speedup).
  - Parallelized clip hashing and verification in `edit_problems()` and `versions.py` for EDL event counts > 8.
  - Provided pure Pillow fallback (`_GreyPatch`) in `flow_send.py` for environments lacking `cv2`/`numpy`, maintaining byte-for-byte sync across tools and pipeline provider.
  - Enhanced CLI with optional `--all` films path, `--critic`/`--no-critic` in `generate`, `--engine` in `dialoguecheck`, and `--jobs` in `grade` and `titles`.
- **Comprehensive Verification & Handoff:**
  - Full test suite: **2,529 passed, 205 skipped, 0 failed** across all 192 test files.
  - Focused audit suite: `tests/test_audit_quality_speed_v2.py` 11/11 passed in 5.93s.
  - Cold wheel package qualification: `ai_film_pipeline-0.0.0-py3-none-any.whl` built and verified in clean virtualenv without `cv2` (`doctor ok: true`, exit 0).
  - Zero paid provider credits spent, zero `git push`, Gate 6 preserved as `OWNER_PENDING` for `film08`.

---

# 2026-11-18 — Film08 Chain of Custody Completed (300/300 Accepted, 16:9 & 9:16 Delivered, Gate 6 OWNER_PENDING) + Phase 2/3/4 Daily-Production Stabilization & Speed Upgrade

- **Film08 Production & Delivery (`98535367`, P20 M4 Candidate):**
  - Eliminated off-frame listener intrusion root cause via opt-in `de_personify_off_frame` & `interperson_no_touch_ids` (0 changes to the 197 previously `ACCEPTED` prompt SHA-256s; verified `SC09_g03` v3 & `SC12_g02` v2 clean on right edge without cropping Gemini sparkle corner).
  - Completed remaining `49` start stills + `SC09_g24` storyboard approval and all `103` remaining generations across Flow accounts (`khoia1k571`, `khoicaesar02`, `04`): **`300 / 300` `ACCEPTED`**, `353` total takes, `53` rejected, `first_pass_rate = 0.863`, `credits.spent = 2118.0 / 2140.0` (`99.0%`), `0` pending sends.
  - Picture lock (`edl_sha256: 9b5fd506863bb17e480021b04c8ad0f165e24ce0d266238330bf8462fd7ae79a`), speech-aligned `titles/cues.json` (`270` cues, `0` `SYNC_OFFSET` BLOCKs, `median_offset_s = 0.0`), `titles/portrait_focus.json` (`300` events, `PORTRAIT_FOCUS_UNKNOWN = 0`), closed-loop AAC true-peak normalizer in `drama/post.py` (`-14.6 LUFS / -2.9 dBTP`).
  - Full `film.py finish` succeeded (`ok: true`, `release_ready: true`): archive `films/film08_chain_of_custody/media/deliveries/20261118T044106-40b49011c3` (`manifest_sha256: 357d662d61a3484d759f14eb98cc1e50d34334bbd231d69ab80a080fa3343d5`, `38` files, `verify_archive ok: True`), `Gates 1–5 == PASS`, **`Gate 6 == OWNER_PENDING`** (`owner_acceptance_written: false`; awaiting Owner creative review and explicit `film.py deliver --accept`).
- **Phase 2 Tech Debt, 168-Category Closure & Consolidation:**
  - Restored `test_accepted_film07_takes_do_not_go_stale` (`5/5 PASS`) by gating `_anchored_eyeline` behind opt-in `object_gaze_neutral_eyeline` + adding 5 human-reviewed `prompt_rebind.json` records (preserving `film07` delivered archive `f3476aa23f`).
  - Closed `P20 money ledger adjustments` (`money.py` `LedgerAdjustment` & `BalanceCheckpoint`, `film.py ledger-adjust`), `plan_package` SHA cache & account-scoped `SEND_PENDING` (`generate.py`), and `sync_header_gates` (`gates.py`, `deliver.py`, `validate --sync-gates`).
  - Closed the final `GAP` in [CATEGORY_COVERAGE_168.md](../production/CATEGORY_COVERAGE_168.md) (`110 Foley` / `111 Sound effects` via `assets/sfx_catalog.json` + `production/foley.py` `GENERATED_OFFLINE`), added `transition_alignment_issues` (`edit.py`), and added R44-informed assist-only `dailies_triage.py` (`film.py triage`, never bypasses human QC).
  - Ported `muse_gateway.py` (`5d981c34`) and opt-in `film_package_export` + `post_engine.py` (`eceaa135`), wrote [THE_SPARE_JACKET_ASR_REVIEW.md](../production/THE_SPARE_JACKET_ASR_REVIEW.md) (`25` `REVIEW_REQUIRED` lines), and [WORKTREE_CONSOLIDATION_MANIFEST.md](../production/WORKTREE_CONSOLIDATION_MANIFEST.md).
- **Phase 3 Agentic Filmmaking v2:** Authored [AGENTIC_FILMMAKING_UPGRADE_RFC.md](../architecture/AGENTIC_FILMMAKING_UPGRADE_RFC.md) and implemented `src/film_pipeline/agentic/` (`WaveDAGScheduler`, `AccountLeasePool` SQLite WAL, `PreSendCritic`, `CausalRepairRouter`, `SceneIncrementalConformer`, `CapabilityRouter`) + read-only `film.py agentic-plan`.
- **Phase 4 `gpt-6.1-sol` Audit, Remediation & Daily-Production Stabilization (`bb3f7c5`):**
  - Completed independent read-only `codex` CLI (`gpt-6.1-sol`) audit ([CODEX_GPT61SOL_PIPELINE_REVIEW_20261118.md](../production/CODEX_GPT61SOL_PIPELINE_REVIEW_20261118.md), session `01a1ed76-055f-77e2-8c1a-8a15b2cff43e`, initial verdict `FIX_FIRST`: `0 P0`, `12 P1`, `8 P2`).
  - Remediated all `20 / 20` findings (`P1 #1–#12`, `P2 #13–#20`) plus multi-account CDP endpoint concurrency locking (`composer_lock(cdp_endpoint)` + short `film_lock`), FFmpeg/ffprobe timeout & silent `loudnorm` guards, corrupt JSON gate guards, packaged resources (`production/data/sfx_catalog.json`, `film_package_export/film_package.v1.schema.json`, `providers/_flow_ui/*.py`), installable `afp-film` CLI (`film_pipeline.cli:main` + `doctor --operation ...`), and [DAILY_PRODUCTION_RUNBOOK.md](../production/DAILY_PRODUCTION_RUNBOOK.md).
  - Verified full unfiltered test suite (`2514 passed, 205 skipped, 0 failed`), isolated outside-checkout wheel qualification (`ai_film_pipeline-0.0.0-py3-none-any.whl`, `afp-film doctor --operation send` exit `0`), and untouched custody of delivered archives (`film06`, `film07`, `film08`).
- **Phase 5 `16:9`-Only Default Delivery & End-to-End Speed Upgrade:**
  - Switched `9:16` portrait rendering/packaging to opt-in (`FilmHeader.portrait_9x16: bool = False`, `wants_portrait()`, `--portrait` / `--no-portrait` flags on `versions`, `deliver`, `finish`; `titles`/`finish` skip `--clean-copy` double 16:9 render, `portrait_focus`, and `*_9x16.mp4` by default while preserving `film06`/`07`/`08` archive custody).
  - Parallelized chunk FFmpeg rendering across workers (`ffjoin.render_workers` default `4`, `--jobs N` / `AFP_RENDER_JOBS`, thread-safe `render_cache.save`), added second-pass `assemble()` skip for unannotated fine chunks, and added opt-in GPU `h264_nvenc` acceleration (`--hwaccel` / `AFP_HWACCEL`, confirmed `"nvenc_available": true`).
  - Added exact-hash start-still auto-binding (`afp-film stills --bind-matching --by <reviewer>`), Setup-Anchor DAG chain flattening (`ShotDecl.independent_still`, `afp-film setup-anchors --max-depth 4 --apply`, `agentic-plan --lookahead N`), and self-contained local HTML Batch Dailies Reviewer (`production/review_ui.py`, `afp-film review-ui --triage` + batch list `afp-film review --ingest`).
  - Verified `4/4 PASS` in `test_production_speed_and_16x9_default.py` and **`163 passed, 0 failed`** across the 14-file production/delivery/edit/agentic regression suite plus `afp-film doctor --operation send` (`"ok": true`).

---

# 2026-11-17 — Continue Film08 toward 300 accepted takes

- Offline reviewed and registered the existing Naomi close single for SC10_g08, g09, g20 and g21, whose still prompts specify the same gaze and initial staging. The opened packet and ledger are outside this still crop and must be checked in the adjacent footage. The approved still does not qualify any video output or clear the repeated-defect stop; no Flow send or credits used.

- Offline compared the identical Naomi start-state prompts for SC11_g03, g05, g06, g08, g21 and g23, then registered and approved the previously reviewed SC08_g17 single for each. Counter props lie outside the close crop and the output must still be checked for listener intrusion. No live sends or credits; the repeated-defect stop remains in force.

- Offline prepared T42_SC11_g02_start.png from character and room references, reviewed the gaze and single framing, then registered and approved it for SC11_g02, g04, g07, g20 and g22 after checking their identical initial states. All counter props are outside the still crop and must be checked in the resulting video and adjacent coverage; still approvals do not clear the recurring listener intrusion or the unattended-send stop. No Flow credits used.

- Offline prepared and individually registered/approved the reviewed SC12_g01 Eli still for SC12_g03, g05, g07, g09, g10, g13 and g15 after comparing each planned initial state and eyeline. Ledger/pen are outside the close crop, not visually verified in the still. SC12_g01 generated listener intrusion despite a clean start and is usable only with its recorded crop; these still approvals do not qualify future renders or override the repeated-defect stop. No Flow credits used.

- Offline candidate T31_SC10_g01_candidate.png preserved in _exports/FILM08_CONTINUE_20261117. The right thumb visibly touches the lower edge of the intact wax seal, but it is not clear enough that it is underneath as required, so the image is not registered or approved. SC12_g02 and its related Naomi singles use the same start framing; the g02 render nevertheless introduced an off-frame person, so do not blindly treat matching stills as proof of a reliable generation. No new sends; repeated-defect stop remains in force.

- Offline continuation: SC11_g01 start image T41 reviewed and approved with three characters looking away from lens, Hollis behind counter, packet open and ledger closed; preserved at _exports/FILM08_CONTINUE_20261117/T41_SC11_g01_start.png. Build reports no blockers, but its compiled prompt says both Hollis lays down the ID card and 'No touching'; resolve that ambiguity before any live attempt. The edit draft maps SC12_g01 to event_id SC12_g01 and titles rendering applies the recorded reframe. An exact-filter frame and local six-second cropped verification clip are in the SC12_g01 audit directory; the listener is absent and the sparkle remains. The actual full final edit remains unverified. STOP on unattended sends remains in force; no credits used this continuation.

- STOP unattended sends: the off-frame listener intrusion recurred after framing changes (SC09_g03_t2, SC12_g01_t1 before crop, SC12_g02_t1). SC12_g02_t1 rejected; cropping the right edge would remove the known corner mark. SC08_g19_t1 accepted after ordered-frame and transcription review. CDP actual debits: 02 279 → 273 and 571 1050 → 1044; all four accounts have now produced a take. Canonical totals 197 accepted, 46 rejected, 1,458 credits, zero pending. Diagnose and change staging/review workflow before more unattended sends; do not bypass the corner-mark decision. Independent SC11_g01 ImageGen candidate exec-4053b110-4955-434b-b541-dc568ae57d0c.png is unapproved: all three subjects look at camera. No human ear or phoneme-level sync review.

- Three parallel sends reconciled at 6 credits each: SC08_g18_t2 accepted (02 285 → 279); SC09_g03_t2 rejected because listener again enters frame (03 1032 → 1026); SC12_g01_t1 accepted with mandatory crop x=.12 y=.06 w=h=.88 (04 58 → 52). The original SC12 clip contains a partial listener at left; all 144 cropped frames were reviewed and the right-side sparkle remains, with the reframe stored in titles/reframe.json. Verify the final edit applies it. Crop for g03 would remove the known bottom-right sparkle, so it was not used. Change g03 staging rather than repeat. Total 196 accepted, 45 rejected, 1,446 credits, no pending. The fourth account khoia1k571 was verified as PRO at 1,050 credits and configured Video/Frame/360p/16:9/x1/6s/Omni Flash, quote 6; no take sent yet. Human ear and phoneme-level sync remain unverified.

- SC08_g18 and SC09_g03 restaged as v2 after rejected singles. Targeted storyboard sketches reviewed; new Hollis still shows blank packet face, Naomi start tightened away from listener, and SC12_g01 independent Eli start was registered after review (ledger below crop). All three builds have zero blockers at 6 credits each; no new send yet. Relevant generated stills preserved in _exports/FILM08_CONTINUE_20261117; current attempt count is unchanged.

- Next parallel pair SC08_g18_t1 and SC09_g03_t1 was reconciled at 6 credits each (02: 291 → 285; 03: 1038 → 1032) and rejected: both show the listener at frame-right despite a single-person constraint; g18 also exposes the red packet seal toward camera. Restage and review new start frames/shot versions before another attempt. Canonical ledger: 194 accepted, 44 rejected, 1,428 credits, no pending. Account 04 has 58 credits and composer verified at 360p, 6s, x1, Omni 1.2 Flash and 6 credits; account 571 has 1,050 credits but its different Agent composer is not qualified. Independent SC10_g01 still candidate in Codex generated_images (exec-6c75c84d-5ccf-4bf6-b59e-1789ab8f00a7.png) remains unapproved: the right thumb is not visibly under the seal. No sends on 04/571.

- Parallel CDP sends completed and reconciled: SC08_g17_t1 (khoicaesar02 297 → 291) and SC09_g02_t1 (khoicaesar03 1044 → 1038), both 6 credits and accepted after ordered-frame and local transcription review. SC09 packet seal is outside the crop; phoneme-level sync and human listening remain unverified. Isolated worktree film08/parallel-03 was merged by the shard take union and its specific evidence copied. Canonical status: 194/300 accepted, 1,416 credits, zero pending; next SC08_g18 and SC09_g03. Both 04 and 571 profiles exist in Gmail chính; their Flow configuration is not yet qualified.

- `SC08_g16_t1` and `SC09_g01_t1` passed frame and transcription review. Balances: `khoicaesar02` 303 → 297 and `khoicaesar03` 1050 → 1044. The second account's new Flow Agent project was switched to the standard frame composer and verified at Omni 1.2 Flash / 360p / 6 s / x1, then its first take was downloaded and reconciled by exact prompt. 192/300 accepted; `SC08_g17` and `SC09_g02` are next.
- The single package currently blocks a new submission while any send is unresolved. Parallel sends need isolated production packages or a targeted concurrency-safe change to that gate, the global budget and shared journal. Until then, submit and reconcile one at a time.
- `SC08_g15_t1` was accepted after frame and local transcription checks; the booked debit was 6 credits, `khoicaesar02` 309 → 303. Count 190/300 accepted, no pending sends. `SC08_g16` is next.
- Owner requested parallel use of the four named Flow accounts. A new project was created on `khoicaesar03`, but it opens the newer Agent composer; its start-frame, duration, resolution and per-send quote still need confirmation before a production send. Project ID `1f023648-69d2-421f-9bbb-3ee32198b25a`. No generation was sent on that account.
- Owner requested automatic continuation to 300 accepted takes. `SC08_g11_t1` passed visual and dialogue QC. Flow debited 6 credits on `khoicaesar02` (333 → 327). Retain at least 5.75 s of the original in the edit because the final word ends near 5.56 s.
- `SC08_g12_t1`, `SC08_g13_t1` and `SC08_g14_t1` passed sequential-frame and local transcription checks. Flow balance 327 → 321 → 315 → 309. Count is 189/300 accepted; `SC08_g15` is next. The T27 and T28 start images were reviewed and registered for `SC08_g24` and `SC09_g18`; the approved Naomi single was reused for `SC09_g19`, `SC09_g25` and `SC10_g02`.
- The remaining run includes 78 missing start-image registrations and the pending board for `SC09_g24`. Existing approved shot and account limits apply. Audit files and the CDP operator script are in `D:/AI FILM MAKER/_exports/FILM08_CONTINUE_20261117/`.

# 2026-11-17 — Film08 SC08_g10 retake accepted

- `SC08_g10` v2 keeps the same approved start still and restages the action so Hollis tips the packet toward his chest and keeps the plain kraft face toward the camera. The new storyboard fingerprint was reviewed against the storyboard frame and start image.
- One CDP send on the same Film08 project in `khoicaesar02` yielded `SC08_g10_t2`. Flow debited 6 credits (339 → 333). The exact v2 prompt matched the new detail page and the original 640×360 clip decoded through all 144 frames. The form stays out of view. Local VAD and Whisper found no speech.
- Film08 now has 185 accepted, 42 rejected, 1,362 credits booked and zero pending sends. `SC08_g11` is next and passed local preflight. `OWNER_GO_LIVE` is back to `NO`. Evidence is in `D:/AI FILM MAKER/_exports/FILM08_SC08_g10_v2_20261117/`.

# 2026-11-17 — Film08 SC08_g10 one-take check

- One CDP submit on the Film08 project in `khoicaesar02` used the approved start still and exact plan prompt. Flow quoted 6 credits for Omni 1.2 Flash, 6 s, 360p, 16:9, x1. The account balance changed from 345 to 339 after the output completed.
- `SC08_g10_t1` was reconciled by the exact prompt shown on the new Flow detail page and the downloaded original. The 640×360, 24 fps clip fully decoded. The form faced the camera after Hollis tilted the packet, contrary to the script. The take is recorded as rejected for action continuity. Sampled frames and proof are in `D:/AI FILM MAKER/_exports/FILM08_SC08_g10_20261117/`.
- Film08 now shows 184 accepted, 42 rejected, 1,356 credits booked and zero pending local sends. `OWNER_GO_LIVE` is back to `NO`. The one-take request is complete. `SC08_g10` still needs restaging before a later retake.

# 2026-11-17 — Codex resumes Film08 Flow engineering

- Active source: `AFP-stable`, `feature/drama-preprod-p0`, taken over at `9b74093d`; last accepted take `SC08_g09_t1`. The October `claude/flow-max-causal-forensics-001` branch is historical.
- Local film status: 184/300 accepted (41 rejected); 116 missing, starting with `SC08_g10`; booked 1,350 credits against the approved 3,210 cap. No unresolved local intent. Current Flow account balance and in-flight UI state were not checked.
- Rebuilt `media/plan` from current package inputs and preserved the previous directory. Only `SC09_g24` changed prompt and storyboard approval; the accepted take count and Gate 4's 116 missing entries are unchanged. Offline generate dry-run for `SC08_g10`: approved start still, 6-credit quote, no blockers. For `SC09_g24`, the new board is pending, its still is missing, and `SC09_g23` must be accepted before the handoff can bind.
- Flow sender/reconciler check exact project identity. An observed account warning keeps a submitted attempt pending and prevents automatic resend; a negative gallery scan cannot clear that stop. Offline scope only; `OWNER_GO_LIVE` stays `NO`. Before a live continuation, check the already approved project/account in the normal Flow UI for an in-flight job, warnings and balance. Keep the existing Omni Flash 360p, single output and no-JS conditions for the Film08 run.
- Local custody and branch inventory: `D:/AI FILM MAKER/_exports/CODEX_BRANCH_AUDIT_20261117/`.


Older entries (before 2026-11-17): [STATUS_ARCHIVE_2026-11.md](STATUS_ARCHIVE_2026-11.md).
