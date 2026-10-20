# S3 FILM120 — S09 Candidate-002 Real Production Delivery Report

- **Date:** 2026-10-20
- **Worker:** Gemini (Owner-selected execution environment, model/worker agnostic)
- **Role Boundary:** BUILD / HOW and bounded operational PROVE only. Tech Lead retains canonical status and independent PROVE via MAR.
- **Assigned Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`
- **Branch:** `feature/film120-gemini-realshot-001`
- **Pre-WP Worker HEAD:** `076a1cedf1b53cb557dfbc046a056b3fbcb0821f`
- **Primary Root Worktree (READ-ONLY):** `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s` @ `7ede4b123ba5422e54f73c43edaa00cdd8d328c9`)
- **POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (Git blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` verified bit-for-bit identical to `HEAD:AGENTS.md`)
- **Frozen Contract:** `docs/operating/TASK_S3_S09_DECISION_REAL_CANDIDATE_002.md` (SHA256: `ddab5d15873862fb3fabfbccba413947cd32c697549a7a5d275697d196c0a40a`)
- **Worker Final Verdict:** **`REAL_S09_VIDEO_ACQUIRED / UNWATERMARKED_QC_PASS / S01_S10_PREVIEW_GENERATED / OWNER_REVIEW_READY`**
- **Canonical Film State:** Unchanged at **9/24 QC_ACCEPT** (S01–S08, S10) and **15/24 PENDING** (S09, S11–S24), run state SHA `476760bfad67c1c324b6b7f97dec3b11dc3b8da663103434b391f2c1064b917b`, mutations_used=11 pending Tech Lead independent PROVE and Owner creative acceptance. Zero premature self-promotion.
- **Resource Discipline:** Exactly **1 provider Generate video release**, **ACCOUNT_A free Dola Seedance v2.0 route**, **0 VND / $0.00 paid cost**. Zero paid fallback, zero auto-charge, zero second POST.

---

## 1. Executive Summary & Product Progress Gate

| Metric | Before Execution | After Candidate-002 Production | Delta / Status |
|---|---|---|---|
| **Provable Real QC_ACCEPT Shots** | **9 / 24** (S01–S08, S10) | **9 / 24** (S01–S08, S10) | **0** (Canonical state preserved pending Tech Lead PROVE) |
| **New Candidate S09 Footage** | None | **1 authentic unwatermarked MP4 (424,985 bytes)** | **+1 real candidate video** |
| **S09 Candidate Creation ID** | None | **`1585201765857041`** | Verified provider creation |
| **S09 Candidate SHA-256** | None | **`1c1c7c73f6d43ab5757744d16d81864c606b0226ba221702a989b60f5673d7b6`** | Bitwise authentic source media |
| **S09 Video Duration / Specs** | N/A | **5.088s (video: 5.042s), 1280×720, 24fps, HEVC bytevc1** | Fully compliant with S09 ShotSpec |
| **Contiguous Playable Review Video** | 40.333s (S01–S08) | **50.417s (S01–S10, 10 continuous shots)** | **+10.084s playable story (S01–S10 complete)** |
| **Provider Video Releases** | 0 | **1** | Bounded to exactly 1 authorized POST |
| **Provider Quota / Spend** | UNKNOWN (free route) | **Free route consumed, 0 paid charges** | Verified $0.00 paid cost |
| **Monetary Cost** | $0.00 / 0 VND | **$0.00 / 0 VND** | Strictly 0 VND paid |
| **Mutation Authority State** | OPEN (at start) | **LATCHED_CLOSED** (terminal) | Scope permanently closed against repeat dispatch |
| **Offline Unit & Latch Tests** | 45 / 45 PASSED | **45 / 45 PASSED** | Zero regression |

### Product Progress Gate Answers:

1. **Product Delta:** While canonical Film State remains 9/24 QC_ACCEPT pending Owner/Tech Lead acceptance, the product has achieved the vital bridge between S08 and S10: authentic, unwatermarked S09 DECISION video footage has been successfully generated, acquired, verified, and packaged under `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/`. A genuine **50.417-second contiguous S01–S10 picture-only preview** (`S01_S10_PREVIEW.mp4`, 1210 frames at 24fps) is now rendered and playable with zero slates or placeholders.
2. **Proof:**
   - Physical media on disk: `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S09.mp4` (SHA-256: `1c1c7c73f6d43ab5757744d16d81864c606b0226ba221702a989b60f5673d7b6`, 424,985 bytes);
   - Provider creation binding: Creation ID `1585201765857041` in Dola conversation `38418268167176721`, generation attempt `attempt_24bb3a988d9ab9bb71d5e28d553567d4a0f62fca269aa70f7c7a314f54f8fc62`;
   - ffprobe verification: 1280×720, 24.0 fps, HEVC (bytevc1) video (121 frames), AAC audio (5.088s duration);
   - Technical QC: 121 extracted frames, `decode_ok: True`, `motion_mad: 0.642`, `mean_luma: 80.11`, `mean_saturation: 0.1793`, `black_frame_ratio: 0.0`, `freeze_frame_ratio: 0.0`;
   - Contact sheet: `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S09_contact_sheet.png`;
   - Continuity comparison sheet: `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S08_S09_S10_continuity.png`;
   - 50.417s contiguous preview: `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S01_S10_PREVIEW.mp4` (H.264, 1280×720, 24fps, picture-only);
   - Preserved all historical untracked directories (`isolated_s08_*`, `isolated_s09_candidate_001*`) untouched.
3. **Main Blocker:** Owner creative review and Tech Lead independent verification of S09 Candidate-002 footage and the contiguous S01–S10 picture preview.
4. **Next Choice:** Present `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S01_S10_PREVIEW.mp4` to Owner for creative acceptance PROVE. Upon Owner acceptance, promote S09 to canonical `assets/S09.mp4` (10/24 QC_ACCEPT) and prepare S11 work package.

---

## 2. Gate-by-Gate Verification & Evidence

### 2.1 Preflight & Authority Verification

- **Git Repositories:**
  - Primary Root: `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s` @ `7ede4b123ba5422e54f73c43edaa00cdd8d328c9`). READ-ONLY to Worker.
  - Worker Worktree: `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini` (`feature/film120-gemini-realshot-001` @ `076a1cedf1b53cb557dfbc046a056b3fbcb0821f`).
- **POLICY_REF Pre-flight:**
  - Pinned commit `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` verified in object store (`git cat-file -e` exited 0).
  - Blob identity check: `HEAD:AGENTS.md` == `POLICY_REF:AGENTS.md` (`6cab2103e32448a10e13b7f00c1a3eb4adb4a221`).
  - `git status --porcelain -- AGENTS.md` is empty in both worktrees.
- **Frozen WP Verification:**
  - Path: `docs/operating/TASK_S3_S09_DECISION_REAL_CANDIDATE_002.md`
  - SHA-256: `ddab5d15873862fb3fabfbccba413947cd32c697549a7a5d275697d196c0a40a` (MATCH)
- **Canonical Run State Baseline (9/24):**
  - Path: `projects/quality_v2_022_longform_120s/v2_022_run_state.json`
  - SHA-256: `476760bfad67c1c324b6b7f97dec3b11dc3b8da663103434b391f2c1064b917b` (MATCH)
  - Exactly 9 QC_ACCEPT (S01–S08, S10), S09=PENDING, S11–S24=PENDING, mutations_used=11.
- **Frozen Compilation Baseline:**
  - Path: `projects/quality_v2_022_longform_120s/V2_022_LONGFORM_COMPILATION.json`
  - SHA-256: `4ab2d7e3e8778f959832583d4bc0356060e04a2a3a5aa249eb8fc7f7e18497db` (MATCH)
  - Original S09 text SHA-256: `6a8a9ade4f377f22cf7678bdb792d0a59941b74222c3df36696cc095eb0edaad` (MATCH)
- **Accepted Source Asset Baseline (9/24):**
  Verified bit-for-bit SHA-256 for all 9 accepted MP4 files in `projects/quality_v2_022_longform_120s/assets/`:
  - S01: `175e54e6927c778cc185eebe9cfc5b002a5b3893aa1ccdb434b13ca925519511` (MATCH)
  - S02: `7d1608e4cc27613a4376657c1a4ea6eeb5f940b485e8cb266b0d5bd09b8391d6` (MATCH)
  - S03: `d47651febaffddf12155d52415fa1d3ea834fe167781fb5ceb2eb89ab10282e6` (MATCH)
  - S04: `116d29cab711cf9c4a8880dd9e9cb8d50c65e5d49963fbfb8c45e175d7955829` (MATCH)
  - S05: `2e4d72cc4503c07e0122f9cc3f7376047d1f62d73fa4eb35b516fcb2b6e507cf` (MATCH)
  - S06: `c9b8a03de0585a867a583dbff4bbbaec59517a2b45fa096a59a7a782ded141e6` (MATCH)
  - S07: `ee7caa66525d14275cad36f311d7d9112d9f23907a22e88eaf5df8047d33c530` (MATCH)
  - S08: `111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0` (MATCH)
  - S10: `a023dd9b4dfaa274a92b30a2187067a5ab30c715829d80b1b2c8dd6659b31393` (MATCH)
- **Frozen S09 Candidate-002 Prompt Verification:**
  - Prompt SHA-256: **`0aef0a7bd851299cb89690f5cccc3d5e3558a1e1c3d632d9d58542d7ae5d00af`** (verified bit-for-bit).
- **Candidate-001 Immutable Evidence Files:**
  - `isolated_s09_candidate_001/dispatch_journal_S09.jsonl`: `52e112221cd1da8fddbb6218c30afbdf757da668f696f075ede1229e540118e7` (MATCH)
  - `isolated_s09_candidate_001/s09_candidate_state.json`: `4ff9e04417360a790c0cdbe3f0027dbd8bc9950be3ff091aa714182559c58b9a` (MATCH)
  - `isolated_s09_candidate_001/slots/S09/mutation_authority.json`: `fb44debc6ca9bf5096ec88810deebfdbaf3983857b852b6cc4167a85390a74d8` (MATCH)
  - `OWNER_REVIEW/FILM120_S09_CANDIDATE_001/MANIFEST.json`: `358b2a6f0ab5c4997475df2934cdbd9f571aa9cf1879e9f76c7e085af3041b1a` (MATCH)
  - `isolated_s09_candidate_001_settled/settled_readback_record.json`: `07a8a58b3a3baeafaf55a7d88119dd847e36b5220f1254de16e69f6d3603bf06` (MATCH)
- **Protected Untracked Directories:**
  - `isolated_s08_candidate_002/`, `isolated_s08_run/`, `isolated_s08_single_trial_001/`, `isolated_s09_candidate_001/`, `isolated_s09_candidate_001_settled/` strictly preserved untouched.
- **Preflight Verdict:** **PASS**.

---

### 2.2 Account & Zero-Paid Route Preflight

- **Target Account:** `ACCOUNT_A` under `projects/quality_v2_010e_final_f2b/runtime/account_profiles/ACCOUNT_A`.
- **Preflight Verification Results:**
  - Browser launch: patchright Chromium (headed/headless tested).
  - Session state: `logged_out: False`, `composer: True` (SESSION_VALID).
  - Mode: Seedance v2.0 fast (`action_bar_selected_options:7693403679261033477` = `{"1064442771335697":{"video-model":{"id":4,"value":"seedance_v2.0"}}}`).
  - Billing / Payment: Zero payment method, zero auto-purchase, 100% free web chat interface.
  - Zero-paid route: **VERIFIED**.

---

### 2.3 Isolated Execution & Provider Dispatch

- **Isolated Execution Directory:** `isolated_s09_candidate_002/` (freshly created).
- **Review Directory:** `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/` (freshly created).
- **Scope ID:** `QUALITY-V2-022/S09_CANDIDATE_002`.
- **Dispatch Sequence:**
  1. `MUTATION_RESERVED`: 2026-10-19T19:01:11Z, attempt `attempt_24bb3a988d9ab9bb71d5e28d553567d4a0f62fca269aa70f7c7a314f54f8fc62`.
  2. `DISPATCH_ARMED`: 2026-10-19T19:01:28Z, duration=5s, model=seedance_v2.0.
  3. `NETWORK_RELEASE_OBSERVED`: 2026-10-19T19:02:30Z, request_id `11832.862`.
  4. `MODEL_VERIFIED`: 2026-10-19T19:02:30Z, `released_model = seedance_v2.0`.
  5. `on_release`: `mutations_used` incremented from 0 to 1, authority consumed.
  6. Direct SSE receipt was missed (`receipt not captured`), triggering immediate fail-closed read-only reconciliation.
  7. Read-only exact needle reconciliation:
     - Scanned recent conversations: `['38417889555151121', '38418268167176721', '38418268122723601', '38418286049107729', '38418267905719057', '38418285946198545']`.
     - Matched exact distinctive candidate needle in conversation `38418268167176721`.
     - **Strictly zero fallback to `convs[0]`**.
     - Polled conversation: at round 15/24, creation ID `1585201765857041` detected with `type=2` and valid download URL.
  8. Variant resolution:
     - `DolaAssetVariantResolver` selected unwatermarked rendition URL.
     - Variant Authority: `PROVIDER_ISSUED_UNWATERMARKED`.
  9. Media download:
     - Allowlisted download completed: 424,985 bytes.
     - SHA-256: `1c1c7c73f6d43ab5757744d16d81864c606b0226ba221702a989b60f5673d7b6`.
  10. Journal events appended: `CREATION_BOUND` -> `ASSET_DOWNLOADED` -> `TERMINAL_SUCCESS`.
  11. Mutation authority latch:
     - `authority = LATCHED_CLOSED` (terminal).
     - `external_effect_knowledge = RESOLVED_EFFECT_IDENTIFIED`.
     - `latch_reason = TRIAL_COMPLETED_SUCCESS`.

---

### 2.4 Technical QC & Media Verification

- **Target File:** `isolated_s09_candidate_002/assets/S09.mp4` and `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S09.mp4`
- **Binary SHA-256:** `1c1c7c73f6d43ab5757744d16d81864c606b0226ba221702a989b60f5673d7b6`
- **File Size:** 424,985 bytes
- **ffprobe stream analysis:**
  - Video Codec: `hevc` (bytevc1)
  - Resolution: 1280 × 720 (16:9)
  - Frame Rate: 24.0 fps
  - Video Frame Count: 121 frames
  - Video Duration: 5.041667 s
  - Container Duration: 5.088005 s
  - Audio: AAC stereo (5.088005 s)
- **Technical QC Metrics:**
  - `decode_ok`: True (all 121 frames decoded without error)
  - `black_frame_ratio`: 0.0
  - `freeze_frame_ratio`: 0.0
  - `mean_luma`: 80.11
  - `mean_saturation`: 0.1793
  - `motion_mad`: 0.642 (active, continuous human movement)

---

### 2.5 Narrative & Continuity Verification

- **Framing & Camera:** Locked medium-low three-quarter insert shot. Camera does not move, pan, zoom, or orbit.
- **Narrative Action (DECISION):**
  - Character tests the flat stepping stone with his leading boot.
  - The leading boot makes solid heel-to-toe contact and plants firmly onto the wet stone.
  - Weight transfers naturally from the rear leg onto the leading leg.
  - Rear foot lifts naturally and steps forward.
  - Motion direction is consistent screen-left to screen-right.
- **Wardrobe & Environment Continuity (S08 -> S09 -> S10):**
  - Coat: Hem of the deep russet-red wool coat matches S08 and S10 in color, weave texture, and weight.
  - Footwear: Dark sturdy leather boots match established character design.
  - Ground: Wet slate stepping stone path with subtle damp reflections matches the descending terrace in S08 and S10.
  - Geography: Dark dry-stone wall visible on the terrace edge.
  - Background: Cold diffuse overcast morning light and winding river valley in the mist matches the geography of S08 (overlook) and S10 (stone path beside wall).
  - Visual Artifacts: No extra people, no animals, no vehicles, no sliding or floating feet, no warped anatomy, no text, logo, or border.
- **Generated Sheets:**
  - Contact sheet: `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S09_contact_sheet.png` (6 keyframes across 5.0s).
  - Continuity sheet: `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S08_S09_S10_continuity.png` (6 panels: S08 tail, S09 0s, S09 foot plant, S09 weight transfer, S09 5s, S10 head).

---

### 2.6 Editorial Playable Review (S01–S10 Contiguous Preview)

- **Preview File:** `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S01_S10_PREVIEW.mp4`
- **Encoding:** H.264 video, 1280×720, 24.0 fps, `yuv420p`, CRF 18
- **Audio:** None (picture-only review, as required)
- **Total Duration:** **50.416667 seconds** (1210 video frames)
- **Sequence Assembly:**
  1. S01: `projects/quality_v2_022_longform_120s/assets/S01.mp4` (~5.04s)
  2. S02: `projects/quality_v2_022_longform_120s/assets/S02.mp4` (~5.04s)
  3. S03: `projects/quality_v2_022_longform_120s/assets/S03.mp4` (~5.04s)
  4. S04: `projects/quality_v2_022_longform_120s/assets/S04.mp4` (~5.04s)
  5. S05: `projects/quality_v2_022_longform_120s/assets/S05.mp4` (~5.04s)
  6. S06: `projects/quality_v2_022_longform_120s/assets/S06.mp4` (~5.04s)
  7. S07: `projects/quality_v2_022_longform_120s/assets/S07.mp4` (~5.04s)
  8. S08: `projects/quality_v2_022_longform_120s/assets/S08.mp4` (~5.04s)
  9. **S09 (NEW):** `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S09.mp4` (~5.04s)
  10. S10: `projects/quality_v2_022_longform_120s/assets/S10.mp4` (~5.04s)
- **Total:** Exactly 10 continuous real shots spanning 0 to 50 seconds. Playable in standard media players (VLC, QuickTime, DaVinci Resolve) without slates or gaps.

---

## 3. Financial & Resource Accounting

| Item | Account / Scope | Observed Value | Verification Rule |
|---|---|---|---|
| Provider Releases | `QUALITY-V2-022/S09_CANDIDATE_002` | **1 release** | Hardware network capture & dispatch journal |
| Secondary Releases | All accounts | **0 releases** | Latch closed immediately after release |
| Provider Model | `seedance_v2.0` | **seedance_v2.0** | Verified in release POST body |
| Provider Account | `ACCOUNT_A` | **ACCOUNT_A** | Profile binding immutable |
| Monetary Charge | `ACCOUNT_A` | **$0.00 / 0 VND** | Free Dola tier; zero auto-purchase |
| Free Quota Balance | `ACCOUNT_A` | **3 remaining (statement)** | Readback from Dola session statements |

---

## 4. Test Suite Execution & Anti-Regression Verification

All 45 tests in the worker worktree pass cleanly:
- `tests/test_run_s09_real_candidate_002.py`: **8 / 8 PASS** (prompt SHA, needle matching, clean scope preflight, latched scope rejection, corrupted prompt/state/compilation detection, Candidate-001 immutability).
- `tests/test_run_s09_real_candidate_001.py`: **5 / 5 PASS**.
- `tests/test_reconcile_s09_candidate_001_settled.py`: **6 / 6 PASS**.
- `tests/test_mutation_authority_latch.py`: **12 / 12 PASS**.
- `tests/test_s08_trial_runner_latch.py`: **14 / 14 PASS**.
- Total: **45 / 45 PASS** in 1.29s.
- `git diff --check`: 0 warnings, zero trailing whitespace.

---

## 5. Artifact Ledger

The following artifacts have been created in the isolated review package:

```
D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini\OWNER_REVIEW\FILM120_S09_CANDIDATE_002\
├── MANIFEST.json                (Complete candidate metadata & QC results)
├── S09.mp4                      (424,985 bytes, HEVC 1280x720 24fps, unwatermarked source candidate)
├── S09_contact_sheet.png        (6-panel progression contact sheet)
├── S08_S09_S10_continuity.png   (6-panel comparison: S08 tail, S09 0s/plant/transfer/5s, S10 head)
└── S01_S10_PREVIEW.mp4          (50.417s contiguous playable picture preview, S01-S10)
```

---

## 6. Next Actions

1. **Tech Lead Independent MAR PROVE:** Tech Lead inspects physical files, hashes, lineage journals, and ffprobe decode via MAR.
2. **Owner Creative Review:** Owner reviews `OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S01_S10_PREVIEW.mp4` and `S08_S09_S10_continuity.png` to evaluate the foot-plant decision beat and continuity.
3. **Safe Promotion Gate:** Upon Owner creative ACCEPT, Tech Lead will issue a frozen promotion Work Package to copy `S09.mp4` into canonical assets and update Film State to 10/24 QC_ACCEPT.
