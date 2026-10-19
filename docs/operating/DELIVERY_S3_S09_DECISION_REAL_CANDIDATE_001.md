# DELIVERY REPORT: S3 S09 DECISION Real Candidate-001

**Date:** 2026-10-19  
**Worker:** Gemini Worker (`feature/film120-gemini-realshot-001`)  
**Work Package:** `docs/operating/TASK_S3_S09_DECISION_REAL_CANDIDATE_001.md`  
**RESULT:** **PARTIAL / STOPPED_PROVIDER_FAILURE** (Single authorized attempt executed, provider error returned, zero credits spent, scope latched closed, fail-closed stop)

---

## 1. Baseline Identity and Preflight

- **Worker Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`
- **Worker Branch:** `feature/film120-gemini-realshot-001`
- **Worker Baseline HEAD:** `0c820c2e3f2a014760ffd92b6eb784bf357e2771`
- **Primary Repository:** `D:\AI FILM MAKER\AI-Film-Pipeline`
- **Primary Mission Branch:** `mission/quality-v2-022-120s`
- **Primary Root HEAD:** `f2b1d431cc6bee41d22287a5c2703068ea2b97a7`
- **POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`
  - Git object check: `git cat-file -e "45f71d6226c5ffc58b4e70f3bcea1bb0151b7003^{commit}"` -> exit code 0
  - Policy blob: `git rev-parse 45f71d6226c5ffc58b4e70f3bcea1bb0151b7003:AGENTS.md` -> `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`
  - Worker worktree blob: `git rev-parse HEAD:AGENTS.md` -> `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` (Exact match)
  - `git status --porcelain -- AGENTS.md`: clean.

---

## 2. Pinned Integrity Checks

- **Canonical Film State (`projects/quality_v2_022_longform_120s/v2_022_run_state.json`):**
  - SHA256: `476760bfad67c1c324b6b7f97dec3b11dc3b8da663103434b391f2c1064b917b` (Verified exact match)
  - Counts: **9 / 24 QC_ACCEPT**, **15 / 24 PENDING** (`S09=PENDING`, `S10=QC_ACCEPT`)
  - Untouched during this task (canonical state remains at 9/24 QC_ACCEPT / 15 PENDING).
- **Compilation (`V2_022_LONGFORM_COMPILATION.json`):**
  - SHA256: `4ab2d7e3e8778f959832583d4bc0356060e04a2a3a5aa249eb8fc7f7e18497db` (Verified exact match)
  - Original compiled S09 prompt SHA256: `6a8a9ade4f377f22cf7678bdb792d0a59941b74222c3df36696cc095eb0edaad` (Verified)
- **Frozen S09 Candidate Prompt:**
  - Content: Verbatim Owner-authorized candidate prompt (framing adaptation: locked slightly elevated medium-long shot, whole body, both boots, flat stepping stone visible).
  - SHA256: `880d734aa5097b839c8be4740a4c4b320fff1e77d371614da494169085d146a1` (Verified exact match)
- **Historical S09 Archives:**
  - `dispatch_journal_S09.jsonl.prior-1` and `slots/S09.prior-1` verified present and preserved read-only.
- **Prior 9 Accepted Canonical Media:**
  - S01, S02, S03, S04, S05, S06, S07, S08, S10 hashes all checked and 100% bitwise intact.

---

## 3. Account Pool Eligibility & Route Preflight

- `POOL_ACCOUNTS`:
  - `ACCOUNT_D`: hard-blocked in `stale_credit_overrides.json` (unobservable, excluded).
  - `ACCOUNT_F`: probed `SESSION_VALID`, known credit: `0`.
  - `ACCOUNT_E`: probed `SESSION_VALID`, known credit: `0`.
  - `ACCOUNT_A`: probed `SESSION_VALID`, known credit: `3` (positive headroom, Seedance v2.0 unwatermarked, free route, $0 paid).
- Route selection: `ACCOUNT_A` selected via `_pick_account` doctrine (known-positive balance preferred over zero balance).

---

## 4. Single S09 Generation Execution & Lineage

- **Scope:** `QUALITY-V2-022/S09_CANDIDATE_001` (fresh isolated scope under `isolated_s09_candidate_001/`).
- **Attempt ID:** `attempt_8c0cb1fdafaa55cb482a24f218b07d2cc31ac2ab780920bb87611836c1b89921`
- **Dispatch Events (`isolated_s09_candidate_001/dispatch_journal_S09.jsonl`):**
  1. `MUTATION_RESERVED` (`2026-10-19T16:37:23Z`, `ACCOUNT_A`, prompt SHA `880d734aa5...`)
  2. `DISPATCH_ARMED` (`2026-10-19T16:37:39Z`)
  3. `NETWORK_RELEASE_OBSERVED` (`2026-10-19T16:38:27Z`, `request_id: 23928.914`, `url_path: /chat/completion`)
  4. `MODEL_VERIFIED` (`2026-10-19T16:38:28Z`, `released_model: seedance_v2.0`)
  5. `TERMINAL_PROVIDER_FAILURE` (`2026-10-19T16:45:00Z`, conversation `38418268122723601`)
- **Conversation Audit (`38418268122723601` on ACCOUNT_A):**
  - Prompt received by Dola: Candidate S09 text (`880d734aa5...`)
  - Provider response text: `エラーが発生しました。もう一度お試しください。` ("An error occurred. Please try again.")
  - Creantions produced: `0` (`creations: []`)
  - Post-dispatch credit balance: **3** (confirmed by read-only probe: no credits consumed, monetary spend: **$0.00 / 0 VND**)
- **Mutation Authority Latch (`isolated_s09_candidate_001/slots/S09/mutation_authority.json`):**
  - Status: `LATCHED_CLOSED`
  - Knowledge: `RESOLVED_EFFECT_IDENTIFIED`
  - Latch: `STOPPED_PROVIDER_FAILURE` (single attempt exhausted; provider error; zero credits consumed)

---

## 5. Scope & Safety Enforcement (Zero Retry Rule)

In strict accordance with `TASK_S3_S09_DECISION_REAL_CANDIDATE_001.md`:
- Max ONE network release authorized across all accounts.
- Outbound release was confirmed (`NETWORK_RELEASE_OBSERVED`), consuming the single permitted attempt.
- No second POST, no account transition, no retry, no paid fallback executed.
- Result recorded objectively as `STOPPED_PROVIDER_FAILURE` / `PARTIAL`.
- No media was generated; candidate manifest records `candidate_obtained: false`.
- Canonical Film State remains strictly `S09=PENDING`, **9/24 QC_ACCEPT / 15 PENDING**.

---

## 6. Test Suite Verification

- Worker focused test suite (`D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`):
  `pytest -v tests/test_run_s09_real_candidate_001.py tests/test_promote_s08_candidate_002.py`
  - **11 passed** (5 S09 candidate runner tests + 6 S08 safe promotion tests)
- Primary test suite (`D:\AI FILM MAKER\AI-Film-Pipeline`):
  `pytest -v tests/test_v2_022_compilation.py tests/test_v2_022_account_routing.py`
  - **17 passed** (9 compilation tests + 8 account routing tests)
- `git diff --check`: Clean.

---

## 7. Files Created & Preserved

**Created on Worker branch (`feature/film120-gemini-realshot-001`):**
- `tools/run_s09_real_candidate_001.py`
- `tests/test_run_s09_real_candidate_001.py`
- `docs/operating/DELIVERY_S3_S09_DECISION_REAL_CANDIDATE_001.md`

**Preserved Untracked Evidence:**
- `isolated_s09_candidate_001/` (journal, slot authority latch, candidate state, provider events)
- `OWNER_REVIEW/FILM120_S09_CANDIDATE_001/MANIFEST.json`
- All `isolated_s08_*/` and `OWNER_REVIEW/FILM120_S08_*/` directories untouched.

**Protected Primary WIP:**
- `opencode.json`, `tests/test_v2_022_compilation.py`, `tools/v2_020_runner.py`, `tools/v2_021_recover.py`, and untracked files in root untouched.
- No push or merge executed.

---

## 8. Blockers & Next Decision Gate

- **Blocker:** Dola provider Seedance v2.0 on `ACCOUNT_A` returned a transient generic error (`エラーが発生しました。もう一度お試しください。`) on the candidate prompt, yielding 0 creations, but consuming 0 credits (credit balance remains 3).
- **Next Decision for Tech Lead / Owner:**
  - Single authorized attempt for scope `S09_CANDIDATE_001` is exhausted and safely latched closed.
  - Tech Lead audits evidence via MAR.
  - Owner / Tech Lead decision on S09: Authorize Candidate-002 attempt on `ACCOUNT_A` (which still has 3 valid credits) or adjust prompt / timing.
