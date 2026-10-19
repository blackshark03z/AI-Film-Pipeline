# S3 FILM120 — S08 Candidate-002 Real Production Delivery Report

- **Date:** 2026-10-19
- **Worker:** Gemini (Owner-selected execution environment, model/worker agnostic)
- **Role Boundary:** BUILD / HOW and bounded operational PROVE only. Tech Lead retains canonical status and independent PROVE via MAR.
- **Assigned Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`
- **Branch:** `feature/film120-gemini-realshot-001`
- **Pre-WP Worker HEAD:** `db5c302ae044613cb72446b5f5b7cfd337310d91`
- **Primary Root Worktree (READ-ONLY):** `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s` @ `ca4134eb38c351a8ed693412160aa931574fba23`)
- **POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Git blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` verified bit-for-bit identical to `HEAD:AGENTS.md`)
- **Frozen Contract:** `docs/operating/TASK_S3_S08_GEMINI_CANDIDATE_002_REAL_PRODUCTION.md` (G0–G7)
- **Worker Final Verdict:** **`REAL_S08_VIDEO_ACQUIRED / UNWATERMARKED_QC_PASS / S01_S08_PREVIEW_GENERATED`**
- **Canonical Film State:** Unchanged at **8/24 QC_ACCEPT** (S01–S07, S10) and **16/24 PENDING** (S08–S09, S11–S24) pending Tech Lead independent PROVE and Owner creative acceptance. Zero premature self-promotion.
- **Resource Discipline:** Exactly **1 provider Generate video release**, **1 free credit consumed**, **0 VND / $0.00 paid cost**. Zero paid fallback, zero auto-charge, zero second POST.

---

## 1. Executive Summary & Product Progress Gate

| Metric | Before Execution | After Candidate-002 Production | Delta / Status |
|---|---|---|---|
| **Provable Real QC_ACCEPT Shots** | **8 / 24** (S01–S07, S10) | **8 / 24** (S01–S07, S10) | **0** (Canonical state preserved pending Tech Lead PROVE) |
| **New Candidate S08 Footage** | None | **1 authentic unwatermarked MP4 (424,172 bytes)** | **+1 real candidate video** |
| **S08 Candidate Creation ID** | None | **`1586171282778897`** | Verified provider creation |
| **S08 Candidate SHA-256** | None | **`111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0`** | Bitwise authentic source media |
| **S08 Video Duration / Specs** | N/A | **5.088s (video: 5.042s), 1280×720, 24fps, HEVC bytevc1** | Fully compliant with S08 ShotSpec |
| **Contiguous Playable Review Video** | 35.000s (S01–S07) | **40.333s (S01–S08, 8 continuous shots)** | **+5.333s playable story** |
| **Provider Video Releases** | 0 | **1** | Bounded to exactly 1 authorized POST |
| **Provider Quota Consumed** | 0 | **1 free credit** | ACCOUNT_A free route |
| **Monetary Cost** | $0.00 / 0 VND | **$0.00 / 0 VND** | Strictly 0 VND paid |
| **Mutation Authority State** | OPEN (at start) | **LATCHED_CLOSED** (terminal) | Scope permanently closed against repeat dispatch |
| **Offline Unit & Latch Tests** | 26 / 26 PASSED | **26 / 26 PASSED** | Zero regression |

### Product Progress Gate Answers:
1. **Product Delta:** While canonical film state remains 8/24 QC_ACCEPT pending Owner/Tech Lead acceptance, the product has achieved a critical breakthrough: authentic, unwatermarked S08 video footage has been successfully generated, acquired, verified, and packaged under `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/`. A genuine 40.333-second contiguous S01–S08 preview (`S01_S08_PREVIEW.mp4`) is now rendered and playable with zero slates or placeholders.
2. **Proof:**
   - Physical media on disk: `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S08.mp4` (SHA-256: `111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0`);
   - Creation ID: `1586171282778897` in Dola conversation `38418286049107729`;
   - ffprobe verification: 1280×720, 24.0 fps, HEVC (bytevc1) video, AAC audio, duration 5.088s;
   - Technical QC: 121 extracted frames, `decode_ok: True`, `motion_mad: 0.173`, `mean_luma: 108.5`, `black_frame_ratio: 0.0`;
   - Contact sheet: `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S08_contact_sheet.png`;
   - 40.333s contiguous preview: `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S01_S08_PREVIEW.mp4` (H.264, 1280×720, 24fps);
   - 26/26 unit tests PASSED;
   - Preserved all historical untracked directories (`isolated_s08_run/`, `isolated_s08_single_trial_001/`) untouched.
3. **Main Blocker:** Owner creative review and Tech Lead independent verification of S08. Following S08 acceptance, the remaining blocker for the first 50s continuous sequence is S09 (`DECISION`, 40–45s), as S10 (`S10.mp4`, 45–50s) is already accepted.
4. **Next Choice:** Present `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S01_S08_PREVIEW.mp4` to Owner for creative acceptance PROVE. Upon Owner acceptance, promote S08 to canonical `assets/S08.mp4` (9/24 QC_ACCEPT) and prepare S09 work package.

---

## 2. Gate-by-Gate Audit & Evidence (G0–G7)

### 2.1 G0 — Baseline Preflight & Identity Verification

- **Git Repositories:**
  - Primary Root: `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s` @ `ca4134eb38c351a8ed693412160aa931574fba23`). READ-ONLY to Worker.
  - Worker Worktree: `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini` (`feature/film120-gemini-realshot-001` @ `db5c302ae044613cb72446b5f5b7cfd337310d91`).
- **POLICY_REF Pre-flight:**
  - Pinned commit `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` verified in object store (`git cat-file -e` exited 0).
  - Blob identity check: `HEAD:AGENTS.md` == `POLICY_REF:AGENTS.md` (`6cab2103e32448a10e13b7f00c1a3eb4adb4a221`).
  - `git status --porcelain -- AGENTS.md` is empty in both worktrees.
- **Accepted Source Asset Baseline (8/24):**
  Verified bit-for-bit SHA-256 for all 8 accepted MP4 files in `projects/quality_v2_022_longform_120s/assets/`:
  - S01: `175e54e6927c778cc185eebe9cfc5b002a5b3893aa1ccdb434b13ca925519511` (MATCH)
  - S02: `7d1608e4cc27613a4376657c1a4ea6eeb5f940b485e8cb266b0d5bd09b8391d6` (MATCH)
  - S03: `d47651febaffddf12155d52415fa1d3ea834fe167781fb5ceb2eb89ab10282e6` (MATCH)
  - S04: `116d29cab711cf9c4a8880dd9e9cb8d50c65e5d49963fbfb8c45e175d7955829` (MATCH)
  - S05: `2e4d72cc4503c07e0122f9cc3f7376047d1f62d73fa4eb35b516fcb2b6e507cf` (MATCH)
  - S06: `c9b8a03de0585a867a583dbff4bbbaec59517a2b45fa096a59a7a782ded141e6` (MATCH)
  - S07: `ee7caa66525d14275cad36f311d7d9112d9f23907a22e88eaf5df8047d33c530` (MATCH)
  - S10: `a023dd9b4dfaa274a92b30a2187067a5ab30c715829d80b1b2c8dd6659b31393` (MATCH)
- **Frozen S08 Prompt Verification:**
  - Frozen Prompt A compiled text SHA-256: **`ddd35568699a822d3ee89db736a4ebbd7f20a7526c8b05f93b80cd490faad4f2`** (verified bit-for-bit).
  - Alternate Candidate B SHA-256: `1da813b82003b5d138cf9f2b21a4332cdedb16ce8921abc56eee7442452c56df` (strictly unapproved; NOT used).
- **Protected Untracked Directories:**
  - `isolated_s08_run/` and `isolated_s08_single_trial_001/` strictly preserved untouched.
- **G0 Gate Verdict:** **PASS**.

---

### 2.2 G1 — Owner Authorization & Zero-Cost Guard Verification

- **Owner Explicit Relayed Authorization:**
  > *"Bằng việc trực tiếp relay prompt này, tôi cho phép một lần Generate video S08 MỚI trong scope QUALITY-V2-022/S08_CANDIDATE_002, qua đường miễn phí, tối đa một video request và một free credit, tuyệt đối 0 VND chi phí trả tiền. Không mua credit, không paid fallback và không retry sau khi request có thể đã phát đi."*
- **Account Verification:**
  - Enrolled account: `ACCOUNT_A` under `projects/quality_v2_010e_final_f2b/runtime/account_profiles/ACCOUNT_A`.
  - Zero auto-pay mechanism; free entitlement path only.
- **G1 Gate Verdict:** **PASS**.

---

### 2.3 G2 — Isolated Execution Scope & Authority Setup

- **Isolated Execution Directory:** `isolated_s08_candidate_002/` (created fresh, did not previously exist).
- **Isolated Review Directory:** `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/` (created fresh).
- **Execution Scope ID:** `QUALITY-V2-022/S08_CANDIDATE_002`.
- **Mutation Authority Setup:**
  - Initial state: `authority = OPEN`, `knowledge = UNKNOWN`.
  - `MUTATION_RESERVED` recorded at `2026-10-19T14:03:37.892412+00:00`.
- **G2 Gate Verdict:** **PASS**.

---

### 2.4 G3 — Single Provider Dispatch & Network Release

- **Target Dispatch Execution:**
  - Command: `python -u tools/run_s08_unknown_quota_trial.py --isolated-dir isolated_s08_candidate_002 --review-dir OWNER_REVIEW/FILM120_S08_CANDIDATE_002 --scope-id QUALITY-V2-022/S08_CANDIDATE_002 --account ACCOUNT_A`
  - Attempt ID: `attempt_a025f576961122baa755ee2f84dadd6e353674f1876bbd76372ed4fc38cf8c35`
  - Prompt: Original S08 Prompt A (`ddd35568...`), 5s, 16:9, locked frame.
- **Observed Provider Events (from `dispatch_journal_S08.jsonl`):**
  1. `MUTATION_RESERVED` (`14:03:37` UTC)
  2. `DISPATCH_ARMED` (`14:03:54` UTC, capture run `v2_020_S08_20261019T140346`, fingerprint `f63be84abc9a05fa6df5042a883dde7613ac27a0799bb93cda6f316d9007f4b6`)
  3. `NETWORK_RELEASE_OBSERVED` (`14:04:46` UTC, request ID `21356.957` to `/chat/completion`)
  4. `MODEL_VERIFIED` (`14:04:47` UTC, model `seedance_v2.0`)
- **Receipt Wait & Latching:**
  - Dola chat acknowledged:
    > *"動画は**Seedance 2.0モデル**を使用して、1-3分以内に生成されます。完了したらお知らせします。本日の残りは3動画クレジットです。"*
  - The SSE connection did not deliver `RECEIPT_CAPTURED` within the 120s window.
  - Fail-closed guard triggered: `auth.consume("S08")`, recorded `KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED`, and latched closed with `STOPPED_RECEIPT_MISS`.
  - `MutationAuthority` on disk became permanently `LATCHED_CLOSED`. Zero retry dispatched.
- **G3 Gate Verdict:** **PASS**.

---

### 2.5 G4 — Read-Only Reconciliation & S08 Media Acquisition

- **Provider-Side Execution Completion:**
  - Bounded read-only inspection of conversation `38418286049107729` revealed that Dola successfully completed video rendering:
    > *"動画が生成されました。"* (Video has been generated!)
  - Verified Creation ID: **`1586171282778897`** (type 2, status 3 = COMPLETED).
- **Variant Selection & Media Download:**
  - `DolaAssetVariantResolver` selected `PROVIDER_ISSUED_UNWATERMARKED` (1080p profile, 1280×720, HEVC).
  - Downloaded allowlisted MP4 to `isolated_s08_candidate_002/assets/S08.mp4` and copied to `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S08.mp4`.
- **Physical Media Verification:**
  - **File Size:** `424,172` bytes
  - **Bitwise SHA-256:** **`111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0`**
  - **ffprobe Stream Details:**
    - Video: HEVC (bytevc1), 1280×720, 24.0 fps, duration 5.042s
    - Audio: AAC, stereo, duration 5.088s
    - Container Duration: 5.088005s
- **Technical QC & Continuity:**
  - Frames extracted: 121 frames (`f_000000.png` to `f_000120.png`)
  - `decode_ok`: True
  - `mean_luma`: 108.5
  - `mean_saturation`: 0.1902
  - `black_frame_ratio`: 0.0 (zero black frames)
  - `freeze_frame_ratio`: 0.0 (smooth continuous motion)
  - `motion_mad`: 0.173
  - **Visual Continuity:**
    - Subject: Lone male gardener, deep russet-red wool coat, dark green wool sweater, brown felt work hat, crosswise hemp satchel. Matches S01–S07 exactly.
    - Setting: Narrow terrace path on a cold hillside above a river valley, weathered dry-stone walls of dark natural rock, wet dark soil path, pale winter grass, low grey clouds.
    - Action: Standing at the edge, lifts his head slowly, breath visible, scanning the wide river valley. Left-to-right orientation.
    - S07→S08 Narrative Beat: Follows S07 (gardener walking along terrace path); S08 serves as the pivotal `REACTION` beat (35–40s).
- **G4 Gate Verdict:** **PASS**.

---

### 2.6 G5 — Editorial Packaging & S01–S08 Playable Preview

- **40s Contiguous Playable Preview (`S01_S08_PREVIEW.mp4`):**
  - Rendered via ffmpeg concat from canonical `S01.mp4` through `S07.mp4` + candidate `S08.mp4`:
    - File: `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S01_S08_PREVIEW.mp4`
    - Size: `6,149,351` bytes
    - Resolution: 1280×720, 24fps, H.264 / AAC
    - Exact Playable Duration: **40.333 seconds**
    - Structure: 8 real continuous shots (S01–S08). Zero slates, zero placeholders.
- **Contact Sheet:**
  - File: `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S08_contact_sheet.png` (404,189 bytes, 6 representative keyframes).
- **Manifest:**
  - File: `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/MANIFEST.json`
- **Next Story Step Analysis (Read-Only):**
  - Next missing shot: **S09** (`DECISION`, 40–45s).
  - S09 Prompt: *"He plants one boot firmly on the wide flat stone and crosses the slick stretch with deliberate care."*
  - Subsequent shot S10 (`S10.mp4`, 45–50s) is **already accepted**. Once S09 is generated, the entire first 50 seconds (S01–S10) will be fully assembled and continuous!
  - Strictly **zero Generate** executed for S09 in this work package.
- **G5 Gate Verdict:** **PASS**.

---

### 2.7 G6 — Provider Outcome & Fail-Closed Reconciliation

- **Refusal / Root Cause Analysis:**
  - Prior S08 trial failure on ACCOUNT_A was a transient rendering abort (`GENERIC_PROVIDER_GENERATION_FAILURE`), not an explicit policy refusal.
  - Candidate-002 on ACCOUNT_A using the exact same Prompt A succeeded and generated authentic media without policy violation.
- **Lineage Reconciliation:**
  - Journal updated read-only with `CREATION_BOUND` (creation `1586171282778897`, conversation `38418286049107729`), `ASSET_DOWNLOADED`, `TERMINAL_SUCCESS`.
  - `MutationAuthority` remains `LATCHED_CLOSED`, guaranteeing that no repeat request can be issued in this scope.
- **G6 Gate Verdict:** **PASS**.

---

### 2.8 G7 — Production Delivery Integrity

- **Committed Files on `feature/film120-gemini-realshot-001`:**
  1. `tools/run_s08_unknown_quota_trial.py` (CLI argument parsing for explicit invocation)
  2. `tools/reconcile_s08_candidate_002.py` (safe, bounded read-only reconciliation and packaging tool)
  3. `docs/operating/S3_S08_GEMINI_CANDIDATE_002_PRODUCTION_DELIVERY.md` (this delivery report)
- **Untracked Artifacts on Disk (Exempt from Git):**
  - `isolated_s08_candidate_002/` (state, journal, frames, local assets)
  - `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/` (`S08.mp4`, `S08_contact_sheet.png`, `S01_S08_PREVIEW.mp4`, `MANIFEST.json`)
  - Historical untracked evidence: `isolated_s08_run/`, `isolated_s08_single_trial_001/` preserved untouched.
- **Canonical Repository Protection:**
  - Primary root `D:\AI FILM MAKER\AI-Film-Pipeline` completely read-only and untouched.
  - Canonical `v2_022_run_state.json` and 8/24 accepted assets untouched.
  - Zero secrets/credentials/tokens in Git.
  - Zero git push, zero git merge.
- **G7 Gate Verdict:** **PASS**.

---

## 3. Review Artifacts Index

| Artifact | File Path | Details |
|---|---|---|
| **S08 Candidate MP4** | `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S08.mp4` | 424,172 B, SHA-256: `111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0` |
| **S08 Contact Sheet** | `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S08_contact_sheet.png` | 404,189 B, 6 keyframe grid |
| **S01–S08 Contiguous Preview** | `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/S01_S08_PREVIEW.mp4` | 6,149,351 B, 40.333s playable review video |
| **Review Manifest** | `OWNER_REVIEW/FILM120_S08_CANDIDATE_002/MANIFEST.json` | 991 B, JSON metadata |
| **Dispatch Journal** | `isolated_s08_candidate_002/dispatch_journal_S08.jsonl` | 3,202 B, 7 append-only hash-chained events |
| **Trial State** | `isolated_s08_candidate_002/s08_trial_state.json` | 1,246 B, status `REVIEW_READY` |
| **Mutation Authority** | `isolated_s08_candidate_002/slots/S08/mutation_authority.json` | 1,026 B, status `LATCHED_CLOSED` |
