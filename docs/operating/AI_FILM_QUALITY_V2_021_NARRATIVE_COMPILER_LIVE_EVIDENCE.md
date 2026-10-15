# AI-FILM-QUALITY-V2-021 — Narrative Compiler Live Production (Release Checkpoint)

```text
STATUS
  EXECUTED_CANDIDATE — technical milestone closed at a release checkpoint
  AUTONOMOUS_NARRATIVE_TO_FILM = EXECUTED_CANDIDATE
  CREATIVE ACCEPTANCE = PENDING (Owner visual read) — NOT claimed final

FINAL HEAD
  branch quality-v2/011b-editorial-assembly (base c74694c + release
  checkpoint commits on top)

FIXTURE
  input: one prose paragraph (6 story beats: cross the pass / find the
  abandoned pack / hesitate / open it / read a letter bearing her own
  name / walk on faster)
  compiled: V2_021_FIXTURE_COMPILATION_5SHOT.json — 5-shot minimum set
  (AFTERMATH folded into REVEAL as one continuous camera action)
  budget: 5+1 = 6 nominal; effective bound 10 (budget_extension, below)
  gate: DISPATCH_AUTHORIZED at pool >= 6 floor (5-shot variant selected)

DELIVERY — 5/5 shots, all PROVIDER_ISSUED_UNWATERMARKED
  S01 ESTABLISH  LOCKED           ACCOUNT_F
      conv 38418443768597521  creation 1574622740545297
      assets/S01.mp4  506,303 B  sha 5f683368fb7628b1be59e87dce1c0c8f80bb86112775283b587713183b55249d
  S02 DISCOVER   PUSH_IN          ACCOUNT_E
      conv 38418427667607825  creation 1575635627563025
      assets/S02.mp4  440,870 B  sha 8dd8aa9754fbc3e73f722ff3c9858e6f923079fbb0423d38356fa556f43f8bbe
  S03 PRESSURE   LOCKED           ACCOUNT_D
      conv 38417945342840849  creation 1544678839963921
      assets/S03.mp4  383,042 B  sha 977695651fea9b9dee2301ad1de737e5e776c735dff1e36f42fd1ac2e626fa73
  S04 REVEAL     PUSH_IN          ACCOUNT_A
      conv 38417945323209745  creation 1548720367402769
      assets/S04.mp4  349,171 B  sha 5c4050553fdde3f7e3f076ac14dbc395783cf431f8e73ee162be51dc617606ec
  S05 RESOLVE    TRACKING_LATERAL ACCOUNT_A
      conv 38418087165774609  creation 1546718558938385
      assets/S05.mp4  435,909 B  sha efbbaa4607dfca37007941df9a4a7b0913816ea7b4b43565e780936d0f9f1fc1

MASTER
  assembled: SEQUENCE_PROOF.mp4 605 frames sha dfec840ae457f183a5fac44c0d5a10efc24ec874cd1a40ad2970302e34cd805b
  finished:  FINISH_MASTER.mov sha 0573eb23eec91ea32960c52f0ba5a786ee69c0790f993c1fe0ed40e3a3b77d05
             (silent-track finish; loudnorm by cmd_master)
  master:    DISTRIBUTION_MASTER.mp4
             sha 9085a50bf0babd81257dd8f8e982a2553eff7cd8592dde6de8d84a4be923f27d
             25.208 s, 1280x720, 24 fps, H.264 + AAC
             watermark ABSENT_BY_PROVIDER_ISSUED_AUTHORITY
  editorial: all 5 shots full length (0-121), no trims, no repairs

MUTATIONS USED / 7 (nominal budget 6; effective bound 10)
  per-slot mutation_authority ledgers (one-way consume):
    S01 ACCOUNT_D 2026-10-07 (dead release, no video)
    S02 ACCOUNT_D 2026-10-07 (dead release, no video)
    S03 ACCOUNT_D 2026-10-07 (delivered)
    S04 ACCOUNT_A 2026-10-07 (delivered)
    S05 ACCOUNT_A 2026-10-07 (delivered)
    S01 ACCOUNT_F 2026-10-16 (delivered; receipt capture missed; reconciled)
    S02 ACCOUNT_E 2026-10-16 (delivered; receipt capture missed; reconciled)
  budget_extension (recorded in state): original 6 -> effective 10 (+4)
  authorized by the Owner's mid-run provisioning of ACCOUNT_E/F with the
  expressed intent to continue the sequence; per-ACK credit verification
  and honest PARTIAL stop remained in force.

RECOVERY LINEAGE (read-only; no shot re-dispatched after a latched release)
  pass 1 (2026-10-15): S03 recovered clean from ACCOUNT_D; S04 hash-verified
  rebind on ACCOUNT_A; S05 reconciled from its latched journal
    scan: V2_021_RECOVERY_SCAN.json (morning backup kept)
    bind: recover_S03.json / recover_S04.json; journal: reconcile_S05.json
  pass 2 (2026-10-15/16): S01 (ACCOUNT_F), S02 (ACCOUNT_E) after receipt
  misses on latched releases — first re-dispatch attempt exposed the
  profile-root defect (below); after the fix, fresh dispatches released +
  MODEL_VERIFIED latched, receipt capture missed again, both bound read-only
    evidence: recover_S01.json / reconcile_S01.json, recover_S02.json /
    reconcile_S02.json
  all 5 dispatch journals terminate TERMINAL_SUCCESS

QUALITY
  technical per shot: full decode, 121 frames, 5.088 s, 1280x720 hevc
  24 fps, has_audio true, black_frame_ratio 0.0 for all 5
  motion: MAD 0.637 / 0.939 / 0.333 / 0.337 / 0.204; freeze ratios
  0.0 / 0.0 / 0.0167 / 0.0 / 0.0833 (S03/S05 advisory flags on wide or
  seated beats; visual progression confirmed in contact sheets)
  visual QC (worker read of contact_sheets/S0*.png, 6 frames each):
  all 5 ACCEPT — lone courier, slate-blue hooded cloak + leather satchel,
  left-to-right traversal, continuous basalt-pass world, cold overcast
  grade; continuity intact across the cut points
  OWNER CREATIVE ACCEPTANCE: PENDING — worker verdicts are advisory

TESTS
  focused: 26 passed (test_narrative_compiler_021.py +
  test_dola_orchestrator_020.py)
  full regression: 1386 passed, 0 failed (post-commit; the 2 pre-commit
  failures were the repository's dirty-tree guard tests, resolved by the
  checkpoint commits themselves)

SECRET AUDIT
  CLEAN (V2_021_SECRET_AUDIT.json over evidence surfaces; no marker hits)

EVIDENCE PATHS (projects/quality_v2_021_narrative_compiler/)
  v2_021_run_state.json
  qualification_run/V2_021_ACCEPTANCE.json + V2_021_CANDIDATE_SEAL.json
  qualification_run/V2_021_SECRET_AUDIT.json + V2_021_RUN_MANIFEST.json
  qualification_run/DISTRIBUTION_MASTER.mp4 (+ SEQUENCE_PROOF, FINISH_MASTER)
  dispatch_journal_S0*.jsonl, slots/S0*/mutation_authority.json
  contact_sheets/S0*.png, frames/S0*/ (121 frames each)
  recover_*.json, reconcile_*.json, V2_021_RECOVERY_SCAN*.json
  (qualification_run/history/ holds the pre-execution gated-outcome seal)

ARTIFACT STORAGE (per repository policy: rendered media stays local;
hashes pinned here and in the checkpoint commit)
  local: projects/quality_v2_021_narrative_compiler/... (full run package)
  Owner review package: OWNER_REVIEW/V2_021/ (DISTRIBUTION_MASTER.mp4,
  contact_sheets/, evidence/, OWNER_REVIEW.md, V2_021_OWNER_REVIEW.zip)
  not committed to Git; recoverable from this doc + commit message hashes

DOCUMENTED DEFECTS (all recorded in state operator_notes / evidence)
  1. dispatch profile-root mismatch: the E/F enrolled slots were probed
     from the package pool but dispatched from the 010E runtime root
     (empty profile -> USER_LOGIN_REQUIRED after 240 s). Fixed with a
     per-alias profile_root in the live runner and the reconcile tool;
     unit-verified remap.
  2. SSE receipt capture misses on latched releases (recurring env
     pattern): every miss recovered read-only from the latched journal +
     provider-side bind; never a blind resubmission.
  3. ACCOUNT_D daily-count cap (stale-credit override annotated
     hard_blocked_today): D excluded from rotation for the day; fresh
     slots ranked first.

STOP REASON
  Milestone checkpoint. Remaining Owner items: creative acceptance of the
  film (OWNER_REVIEW/V2_021/), optional editorial trims, and promotion of
  the sequence into the canonical film if accepted.
```
