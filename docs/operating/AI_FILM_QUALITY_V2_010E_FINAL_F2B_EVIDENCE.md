# AI-FILM-QUALITY-V2-010E RESUME — Multi-Account Routing + Final F2B Qualification

```text
STATUS
  COMPLETED_CANDIDATE
  F2B_010E = PROVEN (reconciled completion after a documented post-release
  tooling crash)
  F2_SEEDANCE_DOLA = PROVEN

FINAL HEAD
  branch quality-v2/010e-final-f2b (base cb54e87; resume of 010E — no 010F)

DOLA ACCOUNT POOL (new)
  discovered:      ACCOUNT_A (dola-main), ACCOUNT_B (dola-profile-20260923)
                   — both Owner-authorized via the Story Auto DPAPI store
  session-valid:   ACCOUNT_A (fresh manual login, hardened detection);
                   ACCOUNT_B (carried session)
  ready:           ACCOUNT_A — 928 points + full daily video quota
  selected:        ACCOUNT_A (deterministic: only READY account; ACCOUNT_B
                   = NO_CREDIT with 0 daily credits)
  selected credit: 928 points; daily video credits 4 → 3 after the dispatch
  selection reason: only READY account; ACCOUNT_B quota exhausted
  binding:         IMMUTABLY bound at NETWORK_RELEASE_OBSERVED
                   (2026-10-06T05:30:04Z, request 16212.1692); no switch,
                   no second account, no retry after release

DISPATCH DURABILITY (unchanged from 010E Phase 1-2, exercised live)
  release persistence: NETWORK_RELEASE_OBSERVED fsync'd inside the CDP
                       handler — the runner then crashed AFTER release and
                       the journal still proved the release (the rule held
                       under a real crash)
  receipt persistence: SSE_ACK structure proven in 010C; this slice's crash
                       occurred post-release; the chain was completed by
                       read-only reconciliation
  crash recovery:      boundary B (release-without-receipt) exercised LIVE:
                       ambiguity latched per the rule, knowledge resolved
                       RESOLVED_EFFECT_IDENTIFIED read-only, latch terminal
  restart idempotency: 14 journal tests green; journal chain verified

DURATION
  requested:       5s (journal-enforced; 010D chip-gated authority)
  provider class:  chat_ability.ability_param.duration = 5
  actual:          5.088005s — EXACT class match (the 010D authority held)

F2A
  preserved PROVEN (10.08s, sha 970018be…); creative advisory deferred to
  Owner; comparison with F2B deferred until the Owner reads both strips.

F2B
  receipt:         journal release record + provider acceptance ack
                   ("Seedance 2.0, 1-3 min, 3 daily credits remaining")
  conversation:    38417852184170001 (NEW conversation on ACCOUNT_A)
  question:        the F2B frozen-plan prompt (echo verified)
  reply:           "動画が生成されました。" + creation card
  creation:        1546437193256465 (type 2, video status 3)
  asset:           assets/f2b_010e_reconciled.mp4 (574,166 bytes,
                   host v16-dola.dola.com)
  sha256:          9c86ac27b8361af0278184a82647f4a8ad9e72338e109fe2d1b296b12831c1a6
  decode:          full decode PASS; 1280x720 24fps hevc
  provider hash:   download_filehash d4413411… (independent cross-check)
  credit:          1 daily video credit (4 → 3, provider ack)
  watermark:       watermarked variant (Dola AI); unwatermarked variants
                   exist (lr=unwatermarked) — UNWATERMARKED_VARIANT remains
                   OBSERVED_NOT_AUTHORIZED

MUTATIONS USED / 1
  1/1 — F2B_010E released exactly once (the crash did NOT cause a second
  release; reconciliation only observed and downloaded)

TRANSPORT QC   PASS (single release, durable records, network authority)
TECHNICAL QC   PASS (5s class match, full decode, provider filehash)
CREATIVE QC    DEFERRED_TO_OWNER (strips in owner_review_f2b_010e/)

TESTS
  Full regression 1316 passed after commit (the 2 pre-commit failures were
  dirty-tree allowlist tests resolved by this commit); 14 journal tests +
  8 focused 010D tests green throughout.

SECRET AUDIT
  CLEAN after classification: the only marker hits are the scanner's own
  pattern list and the redaction test's synthetic fake payload.

PROVIDER LINEAGE
  ACCOUNT_A → conversation 38417852184170001 → question (F2B frozen-plan
  prompt) → acceptance ack (Seedance 2.0, 3 credits remaining) → creation
  1546437193256465 → vid v186a3gm000cdb28fn7og65geeidop40 → asset sha
  9c86ac27…

EVIDENCE PATHS (projects/quality_v2_010e_final_f2b/)
  V2_010E_DOLA_ACCOUNT_POOL.json / V2_010E_ACCOUNT_SELECTION.json (new)
  V2_010E_DISPATCH_JOURNAL_CONTRACT.json / V2_010E_CRASH_RECOVERY_PROOF.json
  dispatch_journal_f2b_010e.jsonl (RESERVED → ARMED → RELEASE_OBSERVED →
                                   CREATION_BOUND → ASSET_DOWNLOADED →
                                   TERMINAL_SUCCESS, with the honest
                                   AMBIGUITY_LATCHED between)
  V2_010E_F2B_EVIDENCE.json / V2_010E_PROVIDER_LINEAGE.json
  V2_010E_F2B_CREATION_OBJECT.json / V2_010E_F2B_ASSET_RECORD.json
  V2_010E_SESSION_CREDIT_PRECHECK.json / V2_010E_SECRET_AUDIT.json
  V2_010E_CANDIDATE_SEAL.json / owner_review_f2b_010e/F2B_t*.png

WORKTREE
  All 010E-resume work committed on quality-v2/010e-final-f2b.

STOP REASON
  None — COMPLETED_CANDIDATE. Final canonical status:
  DOLA_BROWSER_NETWORK = QUALIFIED; F2A = PROVEN; F2B = PROVEN;
  F2_SEEDANCE_DOLA = PROVEN. Remaining Owner items: visual read of the
  F2A/F2B strips (creative acceptance), watermark-handling decision,
  trim/crop decisions for the editorial slice.
```

Documented defects fixed during this slice (all recorded in evidence):
1. regex `\1\2` template stale in the 010C adapter after the sanitizer
   patch batch — crashed the runner AFTER release (the journal made the
   release provable anyway — the durability rule worked as designed);
2. cookie injection over a live persistent profile DOWNGRADES the session
   (profile owns its login; one account = one launch for the whole flow);
3. anonymous sessionid is not authentication (detection hardened: no login
   affordance in ja/en/vi + on dola.com + 15s stability);
4. correlation baselines must include EVERY pre-existing creation.
