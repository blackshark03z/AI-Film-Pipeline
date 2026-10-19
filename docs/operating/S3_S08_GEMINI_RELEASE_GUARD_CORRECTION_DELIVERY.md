# S3 FILM120 — S08 Release Lifecycle Guard Correction Delivery Report

- **Date:** 2026-10-19
- **Worker:** Gemini (Owner-selected execution environment, model/worker agnostic)
- **Role Boundary:** BUILD / HOW and bounded operational PROVE only. Tech Lead retains canonical status and independent PROVE via MAR.
- **Assigned Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`
- **Branch:** `feature/film120-gemini-realshot-001`
- **Pre-WP Worker HEAD:** `90220626e980b3838fa65fb586249221fdfd01ee`
- **Primary Root Worktree (READ-ONLY):** `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s` @ `3aa88a8ca581e03c3129835573a3ed7245ab2f20`)
- **POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Git blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` verified bit-for-bit identical to `HEAD:AGENTS.md`)
- **Frozen Contract:** `docs/operating/TASK_S3_S08_GEMINI_RELEASE_GUARD_CORRECTION.md` (C0–C5)
- **Worker Final Verdict:** **`RELEASE_GUARD_CORRECTION_COMPLETED / TESTS_PASS / FAIL_CLOSED_LIFECYCLE_VERIFIED`**
- **Canonical Film State:** Strictly unchanged at **8/24 QC_ACCEPT** (S01–S07, S10) and **16/24 PENDING** (S08–S09, S11–S24). Zero premature promotion (8 → 8).
- **Resource Discipline:** Exactly **0 provider Generate calls dispatched**, **0 credits consumed**, **$0.00 / 0 VND spent** in this Work Package.

---

## 1. Executive Summary & Product Progress Gate

| Metric | Before Correction | After Correction | Delta |
|---|---|---|---|
| **Provable Real QC_ACCEPT Shots** | **8 / 24** (S01–S07, S10) | **8 / 24** (S01–S07, S10) | **0** (No fake/premature promotion) |
| **Pending Missing Shots** | **16 / 24** | **16 / 24** | **0** (Accurately preserved) |
| **Continuous Playable Footage** | 35.000s (S01–S07) + 5.088s (S10) | 35.000s (S01–S07) + 5.088s (S10) | 0s |
| **Provider Video Generate Releases** | 0 | **0** | **0** (Zero network mutation) |
| **Free Video Quota Consumed** | 0 | **0** | **0 credits** |
| **Monetary Spend** | $0.00 / 0 VND | **$0.00 / 0 VND** | **$0.00 / 0 VND** |
| **Post-Acquisition Fail-Closed Guard** | FAILED (Latch `OPEN` on QC error) | **LATCHED_CLOSED** | 100% durable lifecycle latch |
| **Replay Evidence Preservation** | Overwrote `s08_trial_state.json` | **Preserved bit-for-bit** | Pre-check stops before any writes |
| **Journal Malformed Inference** | Failed open to `PRE_RELEASE` | **Fails closed (`UNKNOWN_OR_ARMED`)** | Ambiguous latch with `UNKNOWN` |
| **Focused Unit / Regression Tests** | 7 tests (19 total with authority) | **14 tests (26 total with authority)** | **26 / 26 PASSED** |

### Product Progress Gate Answers:
1. **Product Delta:** Canonical Film State remains unchanged at 8/24 QC_ACCEPT shots (40.088s provable footage). The technical safety guard has been definitively repaired and hardened: post-acquisition failures (frame extraction, technical QC, review copy, contact sheet, preview, manifest, cancellation) now close `MutationAuthority` permanently (`LATCHED_CLOSED`) with `RESOLVED_EFFECT_IDENTIFIED` knowledge, and attempted reruns are halted before touching any artifacts, guaranteeing bit-for-bit SHA-256 preservation of existing state and evidence.
2. **Proof:**
   - Reproduction test `test_post_acquisition_frame_extraction_failure_latches_closed` verifies the exact failure discovered by Tech Lead: when `extract_frames()` raises `RuntimeError("INDEPENDENT_OFFLINE_POST_ACQUISITION_QC_FAILURE")`, the runner records `RESOLVED_EFFECT_IDENTIFIED`, latches closed with `STOPPED_POST_ACQUISITION_QC_ERROR`, and rejects replay (dispatch count remains exactly 1);
   - Bit-for-bit SHA-256 match on all 8 physical MP4 files under `projects/quality_v2_022_longform_120s/assets/`;
   - Bit-for-bit verification of frozen S08 Prompt A (`ddd35568...`) and Prompt B (`1da813b8...`);
   - 14 / 14 focused offline deterministic tests in `tests/test_s08_trial_runner_latch.py` PASSED;
   - 12 / 12 existing mutation authority tests in `tests/test_mutation_authority_latch.py` PASSED;
   - `python -m py_compile` and `git diff --check` exited 0 with zero errors and zero whitespace anomalies;
   - Preserved all historical untracked directories (`isolated_s08_run/`, `isolated_s08_single_trial_001/`) untouched.
3. **Main Blocker:** S08 missing video footage. Previous run failed due to `GENERIC_PROVIDER_GENERATION_FAILURE` (transient server abort, 0 credits charged). ACCOUNT_A possesses 3 remaining free video credits.
4. **Next Choice:** Tech Lead and Owner can now authorize one bounded video generation on ACCOUNT_A using the fully guarded runner and Option A (frozen compiled prompt `ddd35568...`) under a fresh execution scope (e.g., `QUALITY-V2-022/S08_CANDIDATE_002`), knowing that any network release will fail closed regardless of post-acquisition outcome.

---

## 2. Gate-by-Gate Delivery Audit (C0–C5)

### 2.1 C0 — Policy, Git, and Evidence Preflight

- **Repositories & Worktrees:**
  - Primary Root: `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s` @ `3aa88a8ca581e03c3129835573a3ed7245ab2f20`). Strictly READ-ONLY.
  - Worker Worktree: `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini` (`feature/film120-gemini-realshot-001` @ `90220626e980b3838fa65fb586249221fdfd01ee`).
- **POLICY_REF Pre-flight:**
  - Commit `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` verified in Git object store (`git cat-file -e "45f71d6226c5ffc58b4e70f3bcea1bb0151b7003^{commit}"` exited 0).
  - Blob identity check: `HEAD:AGENTS.md` and `POLICY_REF:AGENTS.md` are bitwise identical (`6cab2103e32448a10e13b7f00c1a3eb4adb4a221`).
  - `git status --porcelain -- AGENTS.md` is empty in both worktrees.
- **Protected Scopes:**
  - Root tracked dirty files (`opencode.json`, `tests/test_v2_022_compilation.py`, `tools/v2_020_runner.py`, `tools/v2_021_recover.py`) preserved untouched.
  - Worker untracked directories (`isolated_s08_run/`, `isolated_s08_single_trial_001/`) preserved untouched.
  - Zero competing live writer active on `quality_v2_022_longform_120s`.
- **Accepted Source Asset Baseline (8/24):**
  Full bitwise verification of the 8 accepted MP4 files against `v2_022_run_state.json`:

| Shot | File Name | Size (Bytes) | Computed SHA-256 | State Recorded SHA-256 | Verdict |
|---|---|---|---|---|---|
| **S01** | `S01.mp4` | 436,768 | `175e54e6927c778cc185eebe9cfc5b002a5b3893aa1ccdb434b13ca925519511` | `175e54e6927c778cc185eebe9cfc5b002a5b3893aa1ccdb434b13ca925519511` | **MATCH** |
| **S02** | `S02.mp4` | 549,390 | `7d1608e4cc27613a4376657c1a4ea6eeb5f940b485e8cb266b0d5bd09b8391d6` | `7d1608e4cc27613a4376657c1a4ea6eeb5f940b485e8cb266b0d5bd09b8391d6` | **MATCH** |
| **S03** | `S03.mp4` | 647,369 | `d47651febaffddf12155d52415fa1d3ea834fe167781fb5ceb2eb89ab10282e6` | `d47651febaffddf12155d52415fa1d3ea834fe167781fb5ceb2eb89ab10282e6` | **MATCH** |
| **S04** | `S04.mp4` | 337,940 | `116d29cab711cf9c4a8880dd9e9cb8d50c65e5d49963fbfb8c45e175d7955829` | `116d29cab711cf9c4a8880dd9e9cb8d50c65e5d49963fbfb8c45e175d7955829` | **MATCH** |
| **S05** | `S05.mp4` | 556,385 | `2e4d72cc4503c07e0122f9cc3f7376047d1f62d73fa4eb35b516fcb2b6e507cf` | `2e4d72cc4503c07e0122f9cc3f7376047d1f62d73fa4eb35b516fcb2b6e507cf` | **MATCH** |
| **S06** | `S06.mp4` | 581,330 | `c9b8a03de0585a867a583dbff4bbbaec59517a2b45fa096a59a7a782ded141e6` | `c9b8a03de0585a867a583dbff4bbbaec59517a2b45fa096a59a7a782ded141e6` | **MATCH** |
| **S07** | `S07.mp4` | 539,383 | `ee7caa66525d14275cad36f311d7d9112d9f23907a22e88eaf5df8047d33c530` | `ee7caa66525d14275cad36f311d7d9112d9f23907a22e88eaf5df8047d33c530` | **MATCH** |
| **S10** | `S10.mp4` | 417,278 | `a023dd9b4dfaa274a92b30a2187067a5ab30c715829d80b1b2c8dd6659b31393` | `a023dd9b4dfaa274a92b30a2187067a5ab30c715829d80b1b2c8dd6659b31393` | **MATCH** |

- **Frozen Prompts Verification:**
  - Original S08 Prompt A SHA-256: **`ddd35568699a822d3ee89db736a4ebbd7f20a7526c8b05f93b80cd490faad4f2`** (verified bit-for-bit).
  - Candidate B SHA-256: **`1da813b82003b5d138cf9f2b21a4332cdedb16ce8921abc56eee7442452c56df`** (verified bit-for-bit).
- **C0 Gate Verdict:** **PASS**.

---

### 2.2 C1 — Full Request Lifecycle Fail-Closed Repair

In `tools/run_s08_unknown_quota_trial.py`, we repaired the runner architecture:
1. **Unified Try/Except Boundary:** Wrapped all execution phases (dispatch, media receipt, acquired state save, frame extraction, technical QC, review MP4 copy, contact sheet generation, preview rendering, candidate manifest generation, and success latching) inside a single comprehensive `try ... except BaseException as error:` block.
2. **Post-Release Acquisition Tracking:** Added `acquired = True` flag and tracking of `is_post_release = released or acquired or (j_state == "CONFIRMED_RELEASE")`. Any exception occurring after release/acquisition (including `extract_frames`, `technical_qc`, `generate_contact_sheet`, `generate_s01_s08_preview`, `save_json(MANIFEST)`) is guaranteed to trigger the post-release fail-closed latching branch.
3. **Knowledge & Latch Assignment:**
   - Post-release errors record `KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED` (the provider release occurred).
   - Gate kinds are mapped deterministically:
     - QC/extraction failures -> `STOPPED_POST_ACQUISITION_QC_ERROR`
     - Review/preview/manifest failures -> `STOPPED_POST_ACQUISITION_REVIEW_ERROR`
     - Cancellation -> `STOPPED_CANCELLED_POST_RELEASE`
     - Timeout -> `STOPPED_TIMEOUT_POST_RELEASE`
     - Receipt miss -> `STOPPED_RECEIPT_MISS`
     - Refusal/0-credit abort -> `STOPPED_PROVIDER_GENERATION_FAILED_NO_CREDIT`
   - Authority is latched permanently: `auth.latch(gate_kind, detail=err_msg[:300])`.
4. **KeyboardInterrupt Safety:** If `KeyboardInterrupt` occurs, the latch and knowledge are committed to disk before re-raising the interrupt, ensuring disk state cannot be left `OPEN`.
5. **Durable Latch Error Handling:** If `auth.latch` raises an exception during write, it fails closed with `state["status"] = "FAIL_CLOSED_LATCH_WRITE_ERROR"` and raises `RuntimeError("FAIL_CLOSED_LATCH_ERROR")`.
- **C1 Gate Verdict:** **PASS**.

---

### 2.3 C2 — Evidence Preservation on Attempted Replay

1. **Pre-check Before Artifact Modification:**
   Added a read-only pre-flight check at the very top of `run_trial()`:
   ```python
   slot_dir = target_dir / "slots" / "S08"
   state_path = target_dir / "s08_trial_state.json"
   auth_file = slot_dir / "mutation_authority.json"

   if auth_file.exists():
       pre_auth = MutationAuthority(slot_dir, scope_id)
       if pre_auth.authority != AUTHORITY_OPEN:
           print(f"STOPPED: Mutation authority not OPEN (current: {pre_auth.authority}). Preserving existing state and evidence.")
           return 1
   ```
2. **Guarantee:** If a scope is already latched (completed or stopped with failure), `run_trial()` halts immediately with return code `1` **BEFORE** creating or overwriting `s08_trial_state.json` or any other file.
3. **Verification:** Verified by unit test `test_attempted_replay_preserves_state_json_sha256`: SHA-256 of `s08_trial_state.json` before and after an attempted replay is identical bit-for-bit.
- **C2 Gate Verdict:** **PASS**.

---

### 2.4 C3 — Conservative Journal Inference

Rewrote `inspect_journal_release_state(journal_path: Path) -> str`:
1. If the file does not exist -> returns `"PRE_RELEASE"`.
2. If the file cannot be read, or is empty (0 bytes), or contains any invalid JSON line/syntax error -> returns `"UNKNOWN_OR_ARMED"` (fails closed!).
3. If any line contains a confirmed release event (`NETWORK_RELEASE_OBSERVED`, `MODEL_VERIFIED`, `SSE_RECEIPT_CAPTURED`, `CREATION_BOUND`, `ASSET_DOWNLOADED`, `TERMINAL_SUCCESS`) -> returns `"CONFIRMED_RELEASE"`.
4. If `DISPATCH_ARMED` is present without confirmed release -> returns `"ARMED"`.
5. Only if the journal contains exclusively valid `MUTATION_RESERVED` events and no syntax errors does it return `"PRE_RELEASE"`.
6. Ambiguous journals (`ARMED` or `UNKNOWN_OR_ARMED`) latch the scope with `STOPPED_AMBIGUOUS_RELEASE` and record `KNOWLEDGE_UNKNOWN`, completely eliminating fail-open risk.
- **C3 Gate Verdict:** **PASS**.

---

### 2.5 C4 — Focused Offline Verification (14/14 Runner Tests, 26/26 Total)

We executed the complete offline unit test suite covering all failure modes:

| Test ID | Test Name | Invariant Verified | Outcome |
|---|---|---|---|
| 1 | `test_pre_release_error` | Pre-dispatch error -> `OPEN`, `RESOLVED_NO_EFFECT` | **PASSED** |
| 2 | `test_post_release_generic_refusal` | Refusal -> `LATCHED_CLOSED`, `RESOLVED_EFFECT_IDENTIFIED`, replay rejected & state preserved | **PASSED** |
| 3 | `test_receipt_miss_timeout` | Receipt miss -> `LATCHED_CLOSED`, `RESOLVED_EFFECT_IDENTIFIED` | **PASSED** |
| 4 | `test_cancellation_post_release` | Cancellation -> `LATCHED_CLOSED`, `RESOLVED_EFFECT_IDENTIFIED` | **PASSED** |
| 5 | `test_ambiguous_release_armed` | `DISPATCH_ARMED` -> `LATCHED_CLOSED`, `UNKNOWN` | **PASSED** |
| 6 | `test_success_path_latches_one_shot` | Acquisition success -> `LATCHED_CLOSED`, replay rejected & state preserved | **PASSED** |
| 7 | `test_original_evidence_unmodified` | Historical `isolated_s08_single_trial_001` intact | **PASSED** |
| 8 | `test_post_acquisition_frame_extraction_failure_latches_closed` | **Tech Lead defect reproduction:** `extract_frames()` exception -> `LATCHED_CLOSED`, `RESOLVED_EFFECT_IDENTIFIED`, replay rejected (dispatch count = 1) | **PASSED** |
| 9 | `test_post_acquisition_technical_qc_failure_latches_closed` | `technical_qc()` exception -> `LATCHED_CLOSED`, `RESOLVED_EFFECT_IDENTIFIED`, replay rejected | **PASSED** |
| 10 | `test_post_acquisition_preview_manifest_failure_latches_closed` | Review prep / preview exception -> `LATCHED_CLOSED`, `RESOLVED_EFFECT_IDENTIFIED`, replay rejected | **PASSED** |
| 11 | `test_post_acquisition_cancellation_latches_closed` | `CancelledError` post-acquisition -> `LATCHED_CLOSED`, `RESOLVED_EFFECT_IDENTIFIED`, replay rejected | **PASSED** |
| 12 | `test_attempted_replay_preserves_state_json_sha256` | Replay preserves original state JSON SHA-256 bit-for-bit | **PASSED** |
| 13 | `test_malformed_journal_fails_closed` | Corrupted journal -> `LATCHED_CLOSED`, `UNKNOWN` (fails closed) | **PASSED** |
| 14 | `test_inspect_journal_states` | Direct unit testing of all 8 journal parsing variants | **PASSED** |

#### Test Execution Evidence:
- **Command:**
  ```powershell
  $env:PYTHONPATH="src;tools"; pytest tests/test_s08_trial_runner_latch.py tests/test_mutation_authority_latch.py -v
  ```
- **Exit Code:** `0`
- **Output:**
  ```text
  ============================= test session starts =============================
  platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
  rootdir: D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini
  configfile: pyproject.toml
  collected 26 items

  tests/test_s08_trial_runner_latch.py::test_pre_release_error PASSED      [  3%]
  tests/test_s08_trial_runner_latch.py::test_post_release_generic_refusal PASSED [  7%]
  tests/test_s08_trial_runner_latch.py::test_receipt_miss_timeout PASSED   [ 11%]
  tests/test_s08_trial_runner_latch.py::test_cancellation_post_release PASSED [ 15%]
  tests/test_s08_trial_runner_latch.py::test_ambiguous_release_armed PASSED [ 19%]
  tests/test_s08_trial_runner_latch.py::test_success_path_latches_one_shot PASSED [ 23%]
  tests/test_s08_trial_runner_latch.py::test_original_evidence_unmodified PASSED [ 26%]
  tests/test_s08_trial_runner_latch.py::test_post_acquisition_frame_extraction_failure_latches_closed PASSED [ 30%]
  tests/test_s08_trial_runner_latch.py::test_post_acquisition_technical_qc_failure_latches_closed PASSED [ 34%]
  tests/test_s08_trial_runner_latch.py::test_post_acquisition_preview_manifest_failure_latches_closed PASSED [ 38%]
  tests/test_s08_trial_runner_latch.py::test_post_acquisition_cancellation_latches_closed PASSED [ 42%]
  tests/test_s08_trial_runner_latch.py::test_attempted_replay_preserves_state_json_sha256 PASSED [ 46%]
  tests/test_s08_trial_runner_latch.py::test_malformed_journal_fails_closed PASSED [ 50%]
  tests/test_s08_trial_runner_latch.py::test_inspect_journal_states PASSED [ 53%]
  tests/test_mutation_authority_latch.py::test_upload_ambiguity_latches_closed PASSED [ 57%]
  tests/test_mutation_authority_latch.py::test_generate_ambiguity_latches_closed PASSED [ 61%]
  tests/test_mutation_authority_latch.py::test_readonly_resolution_no_effect_keeps_latch PASSED [ 65%]
  tests/test_mutation_authority_latch.py::test_readonly_resolution_identified_effect_keeps_latch PASSED [ 69%]
  tests/test_mutation_authority_latch.py::test_latch_survives_restart PASSED [ 73%]
  tests/test_mutation_authority_latch.py::test_unused_generate_budget_cannot_be_consumed_after_latch PASSED [ 76%]
  tests/test_mutation_authority_latch.py::test_unused_upload_budget_cannot_be_consumed_after_latch PASSED [ 80%]
  tests/test_mutation_authority_latch.py::test_successor_and_repair_paths_cannot_bypass_latch PASSED [ 84%]
  tests/test_mutation_authority_latch.py::test_scene_resume_cannot_bypass_latch PASSED [ 88%]
  tests/test_mutation_authority_latch.py::test_new_owner_authorized_scope_starts_fresh PASSED [ 92%]
  tests/test_mutation_authority_latch.py::test_latch_is_one_way PASSED     [ 96%]
  tests/test_mutation_authority_latch.py::test_readonly_operations_usable_after_latch PASSED [100%]

  ============================= 26 passed in 0.66s ==============================
  ```
- **Static Syntax & Hygiene:**
  - `python -m py_compile tools/run_s08_unknown_quota_trial.py tests/test_s08_trial_runner_latch.py` -> exit code 0.
  - `git diff --check` -> exit code 0 (clean, no trailing whitespace or blank line issues).
- **C4 Gate Verdict:** **PASS**.

---

### 2.6 C5 — Candidate Options & Production Readiness Handoff

#### Candidate Option A (Primary — Retain Frozen Compiled Prompt):
- **Prompt Hash:** SHA-256 **`ddd35568699a822d3ee89db736a4ebbd7f20a7526c8b05f93b80cd490faad4f2`**
- **Recommendation:** Preferred for future production execution. The refusal investigation confirmed that prior failure was a transient server-side render abort (`GENERIC_PROVIDER_GENERATION_FAILURE` with 0 credits charged), not a prompt-specific policy violation.
- **Execution Target:** ACCOUNT_A, Seedance v2.0, 5.0s, 16:9, locked frame, 24fps.

#### Candidate Option B (Contingency — Semantically Faithful Alternate):
- **Prompt Hash:** SHA-256 **`1da813b82003b5d138cf9f2b21a4332cdedb16ce8921abc56eee7442452c56df`**
- **Status:** Unapproved alternate. Preserved and verified if Option A encounters repeated issues under separate Owner authorization.

#### Release-Readiness Verdict:
**`TECHNICAL_SAFETY_GUARD_REPAIRED / FAIL_CLOSED_VERIFIED / CANDIDATE_A_READY`**
The system is now completely protected against double-spending or open authority leaks across all lifecycle stages.

- **C5 Gate Verdict:** **PASS**.

---

## 3. Strict Prohibitions & Protection Confirmations

1. **Zero Provider Video Generation:** Exactly 0 calls to Dola or any external video generation provider in this work package.
2. **Zero Quota Spend:** 0 credits consumed; $0.00 / 0 VND spent.
3. **No Film State Tampering:** Canonical Film State remains 8/24 accepted.
4. **Historical Evidence Protected:** `isolated_s08_run/` and `isolated_s08_single_trial_001/` untouched.
5. **Primary Root Protected:** Primary root `D:\AI FILM MAKER\AI-Film-Pipeline` remains completely read-only.
6. **No Remote Push / Merge:** All work remains strictly local on branch `feature/film120-gemini-realshot-001`.
