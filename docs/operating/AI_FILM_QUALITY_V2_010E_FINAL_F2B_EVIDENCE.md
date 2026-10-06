# AI-FILM-QUALITY-V2-010E — Atomic Dispatch/Receipt Durability + Final F2B Qualification

Tracked evidence document. State JSONs in the untracked
`projects/quality_v2_010e_final_f2b/` (hashes in `V2_010E_CANDIDATE_SEAL.json`).

```text
STATUS
  STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH — the fail-closed pre-dispatch
  credit gate stopped before any release. Phases 1-2 (the package's
  engineering deliverable) are PROVEN; F2B_010E authority is UNspent.

FINAL HEAD
  branch quality-v2/010e-final-f2b (base cb54e87 = 010D final)

DISPATCH DURABILITY                     ← the package's core deliverable
  release persistence:    NETWORK_RELEASE_OBSERVED is appended SYNCHRONOUSLY
                          inside the CDP requestWillBeSent handler — durable
                          (fsync) before any SSE parsing, before the
                          response, before anything downstream.
  receipt persistence:    SSE_RECEIPT_CAPTURED is appended the moment the
                          captured stream body parses an SSE_ACK beyond the
                          pre-dispatch message-index boundary — never
                          waiting for creation, download, shutdown, or
                          evidence assembly. BUDGET_CONSUMED fires from that
                          same callback.
  crash recovery:         boundaries A-E implemented and tested:
                          A safe-unspent (with an unobserved-release
                          promotion to B via the conversation check);
                          B ambiguity-latch + read-only reconcile;
                          C resume-poll by receipt identity;
                          D resume-download by creation identity;
                          E verify-local-SHA256 + finalize.
                          Recovery NEVER dispatches.
  restart idempotency:    journal reload is hash-chain-verified (torn tail
                          ignored); duplicate events are absorbed
                          (duplicate_ignored); recover mode cannot
                          redispatch (dispatch mode refuses a non-fresh
                          journal).
  journal contract:       append-only JSONL, hash-chained
                          (previous_event_hash → event_hash), ordinal per
                          event, payload hashes, secret-key REDACTION
                          before disk. Sits BESIDE MutationAuthority (the
                          single budget governor) — no parallel governance.

SESSION
  Read-only poll validation: SESSION_VALID (DPAPI DOLA_RE_PROFILE session,
  no login needed, no new secret material).

CREDIT PRECHECK
  Method: the provider-VISIBLE remaining-credit statements, timestamped via
  the /im/chain/single poll of BOTH conversations (ours + the credit-surface
  conversation the sidebar opens) — the LATEST statement wins; chat-history
  inference is limited to provider-issued credit statements (not yesterday's
  guesses) and is fail-closed.
  Result: the latest provider statement is "残りは0動画クレジット"
  (0 remaining). The 4/day quota is consumed: M2 1 + F2A 2 + the Owner's
  separate credit-conversation generation 1 (visible in the 動画生成クレジット
  conversation, id 38417956596221969).
  Verdict: INSUFFICIENT → STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH.
  Mutation remains unused (F2B_010E authority OPEN/UNSPENT; no journal
  armed; zero provider interactions in 010E).

DURATION
  requested:      5s (transport-controlled; journal armed fields require
                  duration_class = 5 and the release body is verified ≠5 →
                  ambiguity latch)
  provider class: chat_ability.ability_param.duration (010D PROVEN carrier)
  actual:         N/A — no dispatch occurred

F2A
  Preserved PROVEN (10.08s, sha 970018be…, TRANSPORT+TECHNICAL PASS;
  creative advisory deferred to Owner). F2A/F2B comparison on causal action,
  geography, travel direction, continuity, camera, identity, editability
  remains DEFERRED — no F2B asset exists to compare.

F2B
  NOT EXECUTED this slice (insufficient provider-visible credit at
  precheck). Three consecutive provider-side blockers are now on record:
  010C refusal (10s class cost), 010D server-side render failure, 010E
  zero-credit precheck — none of them transport or protocol defects.

MUTATIONS USED / 1
  0/1 — F2B_010E unspent by the fail-closed gate (exactly the outcome the
  work package mandates for this branch).

TRANSPORT QC
  The durability chain itself is the transport work of this slice: PROVEN
  (14 focused tests + full regression). No live transport claims changed.

TECHNICAL QC
  NOT_APPLICABLE_NO_ASSET (F2B); F2A's record stands.

CREATIVE QC
  DEFERRED_TO_OWNER (no new asset).

TESTS
  14 new focused tests (crash A-E, duplicate events, restart idempotency,
  receipt replay/stale index, false-historical creation rejection, duration
  enforcement, payload redaction, torn-tail recovery, terminal absorption).
  Full regression: 1316 passed (1302 + 14). Zero-secret-audit hits in 010E
  files.

SECRET AUDIT
  CLEAN. Journal payloads sanitized before disk; DPAPI store unchanged;
  raw captures encrypted at close.

PROVIDER LINEAGE
  Zero new provider interactions in 010E. Carried forward from 010C/010D:
  M1 images ×4, M2 video 1543843763689489 (5.04s), F2A video 1540180629641233
  (10.08s), F2B_010D release 1540187097250321 (failed server-side). Credit
  statement timeline recorded in V2_010E_SESSION_CREDIT_PRECHECK.json.

EVIDENCE PATHS (state dir projects/quality_v2_010e_final_f2b/)
  V2_010E_CUSTODY.json
  V2_010E_DISPATCH_JOURNAL_CONTRACT.json
  V2_010E_CRASH_RECOVERY_PROOF.json
  V2_010E_SESSION_CREDIT_PRECHECK.json (+ credit_surface.png)
  V2_010E_F2B_EVIDENCE.json
  V2_010E_PROVIDER_LINEAGE.json
  V2_010E_SECRET_AUDIT.json
  V2_010E_CANDIDATE_SEAL.json
  Tracked: tools/dola_010e_dispatch_journal.py, tools/dola_010e_adapter_delta.py,
  tools/run_v2_010e_f2b.py, tools/precheck_v2_010e_session_credit.py,
  tools/custody_v2_010e.py, tools/finalize_v2_010e.py,
  tests/test_v2_010e_journal_001.py

WORKTREE
  010E work products committed on quality-v2/010e-final-f2b; qualified
  adapters unchanged (010E is another audited subclass layer).

STOP REASON
  The provider visibly reports 0 remaining video credits today. The
  fail-closed pre-dispatch gate (Phase 3) stopped before release exactly as
  specified; F2B_010E remains unspent. The complete 010E machinery is
  committed and tested — after the daily credit reset, the final F2B attempt
  is: re-run precheck (SUFFICIENT expected) → run_v2_010e_f2b.py dispatch.
  One command, one mutation, atomic journal from arm to terminal.
```
