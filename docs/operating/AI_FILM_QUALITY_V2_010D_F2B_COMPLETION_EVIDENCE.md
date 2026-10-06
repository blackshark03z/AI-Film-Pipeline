# AI-FILM-QUALITY-V2-010D — Dola F2B Completion + Explicit Duration Authority

Tracked evidence document. State JSONs in the untracked
`projects/quality_v2_010d_f2b_completion/` (hashes in
`V2_010D_CANDIDATE_SEAL.json`). 010C truths preserved untouched.

```text
STATUS
  STOPPED_EXPLICIT_PROVIDER_FAILURE — the provider failed the F2B generation
  server-side on its ONLY authorized attempt. Duration authority (the new
  capability this package set out to prove) is PROVEN. Everything 010C left
  proven remains proven; nothing was retried, nothing was latched-new
  (the crash-induced ambiguity was latched and then knowledge-resolved
  read-only).

FINAL HEAD
  branch quality-v2/010d-f2b-completion (base c3145d6 = 010C final)

SESSION
  Reused the 010C DPAPI-backed DOLA_RE_PROFILE session; read-only
  validation only (poll ok) before dispatch. No login required, no new
  secret material; runtime_secret_store/dola_session.dpapi unchanged.

DURATION AUTHORITY                      ← the package's core deliverable
  requested:               5s class (explicit, transport-controlled)
  proven provider class:   chat_ability.ability_param.duration is THE
                           provider duration parameter — set by the
                           composer video-mode UI (chip "10s ▾" → dropdown),
                           NOT by prompt text. Proof: the 010C F2A release
                           body carried duration:10 while its own prompt
                           text said "5-second" (both visible in the same
                           ability_param JSON).
  read-only mapping proof: chip 10s → dropdown → 5s → chip reads "5s",
                           ZERO /chat/completion POSTs during the whole
                           exploration (duration_selected_5s.png).
  pre-dispatch gate:       verify_duration_pre_dispatch(5) — fail-closed;
                           it refused two dispatch attempts that would
                           otherwise have been uncontrolled (one toggle-off
                           bug, one missing-selection bug) and saved the
                           single mutation both times.
  adapter delta:           tools/dola_010d_adapter_delta.py (subclass; the
                           qualified 010C adapter file is UNTOUCHED).
  expected credit:         1 (5s class)
  actual duration:         N/A — the provider failed the generation
                           (see F2B).

F2B
  receipt:                 reconstructed post-hoc (the runner crashed between
                           Enter and persistence — an accounting defect,
                           recorded as such; the release itself is proven)
  conversation:            38417972940811793
  question:                idx29 msg 1540187097250321 (echo of the released
                           prompt; raw-capture POST 2026-10-06T02:59:51.6Z,
                           request_id 8052.765)
  acceptance ack:          idx30 msg 1544399803432977 — "will generate with
                           Seedance 2.0 in 1-3 min; 0 video credits
                           remaining today" (last credit reserved)
  terminal notice:         idx34 msg 1543317950013969 (newest chain message,
                           gap-probed) — "動画を生成できません。今回の生成で
                           クレジットは使用されませんでした。" = the
                           generation FAILED server-side and the provider
                           asserts NO credit was consumed for it
  creation:                NONE — the provider never produced a creation
                           object for this exchange
  asset / sha256 / decode: N/A — no asset exists
  credit arithmetic:       day 4 → M2 1 → F2A 2 → F2B_010D reserved-then-
                           refunded/never-consumed (provider's own statement)

F2A
  preserved status:        PROVEN (10.08s, sha 970018be…, TRANSPORT+TECHNICAL
                           QC PASS; CREATIVE deferred to Owner). Editorial
                           flags recorded: trim required (10s→2.8s slot),
                           watermark handling = Owner decision, direction
                           advisory pending owner read, regeneration
                           PROHIBITED.

MUTATIONS USED / 1
  f2b_010d = 1 (released once, provider-failed; no retry, authority spent).
  The scope is LATCHED (the crash produced a release-without-receipt
  ambiguity, latched per the rule; read-only reconciliation then resolved
  the effect knowledge to RESOLVED_NO_EFFECT — the latch itself never
  re-opens).

TRANSPORT QC
  dispatch/receipt/acceptance chain PROVEN under the BrowserNetwork
  transport with the 5s duration gate. The generation outcome is a provider-
  side failure — transport success is measured by the proven chain, not the
  provider's internal render farm.

TECHNICAL QC
  NOT_APPLICABLE_NO_ASSET for F2B_010D. F2A's technical record stands.

CREATIVE QC
  NOT_APPLICABLE_NO_ASSET for F2B_010D. F2A's advisory stands (deferred to
  Owner).

TESTS
  Focused (new, 8): duration carrier field (prompt-text non-authority),
  duration gate fail-closed, credit parsing from the real refusal text,
  restart-after-receipt, restart-after-download integrity, multi-creation
  filtering, credit-text redaction safety, committed-fixture secret scan.
  Full regression: 1302 passed (1294 + 8 new). Secret audit: CLEAN
  (zero hits in 010D files; fail-closed scanner).

SECRET AUDIT
  No secret committed/logged. DPAPI store unchanged; raw captures encrypted
  at close; fixtures redacted incl. double-escaped \u0026 forms.

EVIDENCE PATHS (state dir projects/quality_v2_010d_f2b_completion/)
  V2_010D_CUSTODY.json — new scope, F2B_010D=ONE, 010C truths hashed
  V2_010D_DURATION_AUTHORITY.json — the carrier-field + UI-mapping proof
  V2_010D_DURATION_UI_EXPLORATION.json / V2_010D_DURATION_SELECTION_TEST.json
  V2_010D_F2B_EVIDENCE.json — final F2B story (crash, release, acceptance,
                              provider failure, false-correlation exhibit)
  V2_010D_PROVIDER_LINEAGE.json — full message chain idx2→idx34 with ids
  V2_010D_RECONCILIATION.json / V2_010D_TIMELINE_DUMP / V2_010D_GAP_PROBE
  V2_010D_UNWATERMARKED_VARIANT.json — OBSERVED_NOT_AUTHORIZED
  V2_010D_MUTATION_LEDGER.json / f2b_010d_receipt.json (reconstructed)
  V2_010D_SECRET_AUDIT.json / V2_010D_CANDIDATE_SEAL.json
  assets/MISATTRIBUTED_canary4_history_video.mp4 — the false-correlation
  exhibit, renamed for honesty (canary-4's asset, sha c4a0761b…)

WORKTREE
  010D work products committed on quality-v2/010d-f2b-completion; the
  qualified 010C adapter is byte-unchanged (audited delta in a subclass).

STOP REASON
  The provider failed the F2B generation server-side ("動画を生成できません")
  on the single authorized attempt and asserts no credit was consumed. Under
  F2B_010D = ONE, no retry is possible. DOLA_BROWSER_NETWORK stays QUALIFIED;
  F2A stays PROVEN; a future F2B requires a NEW Owner-authorized scope — the
  duration authority built here (5s class proven pre-dispatch, fail-closed
  gate, 1-credit expectation) makes that attempt deterministic and cheap.
```
