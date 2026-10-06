# AI-FILM-QUALITY-V2-010C — Dola Full-Stack Authority Reconstruction + Fresh Session Qualification

Evidence document (tracked). State JSONs live in the untracked state dir
`projects/quality_v2_010c_dola_fullstack/` (paths below are relative to it);
their SHA256 prefixes are recorded in `V2_010C_CANDIDATE_SEAL.json`.

```text
STATUS
  STOPPED_PROVIDER_CREDIT_REFUSAL (F2B leg)
  Everything before F2B: PROVEN end-to-end.

FINAL HEAD
  branch quality-v2/010c-dola-fullstack-re, base 51fc0eb2afb63117fe9832cea367cf01b4cdf3bf (V2-010B, immutable)

SESSION
  fresh login:            NOT REQUIRED — the Owner's DPAPI-stored Dola session
                          (story_auto dola-profile-20260923) was still alive when
                          injected into the dedicated DOLA_RE_PROFILE browser
                          (patchright chromium, headed, ja-JP, Asia/Tokyo).
                          The two earlier "SESSION_EXPIRED" reads were a tooling
                          bug (un-awaited cookie injection), corrected and
                          re-proven.
  encrypted store:        runtime_secret_store/dola_session.dpapi
                          (Windows DPAPI, current-user scope, OUTSIDE tracked
                          evidence; tracked metadata carries names/classes/
                          expiry classes/value-hash prefixes only)
  expiry/state:           SESSION_VALID at capture (35 cookies, AUTH =
                          sessionid + sessionid_ss; 28 web-storage keys;
                          0 service workers). Inventory classified per the
                          work-package taxonomy (AUTH/SESSION/DEVICE/CSRF/
                          RUNTIME/UNKNOWN).

BROWSER ORACLE (M1)
  endpoint:               POST https://www.dola.com/chat/completion (h2) —
                          SAME endpoint family as 010B; response is
                          text/event-stream consumed as a fetch stream.
                          Query carries the attestation layer the browser adds:
                          a_bogus, device_id, web_id, tea_uuid, fp=verify_…,
                          rotating msToken, region/sys_region=VN (live),
                          doubao_pc_version=3.39.1, pkg_type, real_aid, tz_name.
  receipt:                SSE_ACK IS CURRENT — ack_client_meta.conversation_id
                          (+ section_id) with query_list[].question_id /
                          local_message_id / message_index. M1 receipt:
                          conversation 38417972940811793 (durable Seedance skill
                          conversation; canary-4's "task_id" was this
                          conversation id), question 1541253913616145,
                          message_index 7.
  stable IDs:             question message, reply message
                          (1546406012981009), creation ids
                          (40033753389997329/7585/7841/8097) — issued via the
                          STREAM_CHUNK creation card (block_type 2074).
  polling:                the page itself uses a WS push channel
                          (wss://wss-normal-i18n.dola.com/ws/v2, binary
                          protobuf); the HTTP poll POST /im/chain/single is
                          CURRENT but with a DIFFERENT request schema than 010B:
                          uplink_body.pull_singe_chain_uplink_body wrapper,
                          anchor_index = MAX_SAFE_INTEGER, and Content-Type
                          "application/json; encoding=utf-8" (without the
                          encoding parameter the API returns 712012002
                          不支持编码类型 — proven live).
  output correlation:     creation-id equality between the live card and the
                          read-only poll — history-immune. M1 output: 4 image
                          creations (Agent-Creation chose IMAGE for the scenic
                          prompt; req_key seedream_v43_flow), all image_status 2
                          (completed), correlated by exact ids. The video stage
                          is M2's proof.

ROOT CAUSE OF 010B (HTTP 200 + NO RECEIPT)
  classification:         ATTESTATION_DEPENDENCY (multi-layer)
  proven:                 SIGNATURE_GAP (a_bogus never sent by cookie-HTTP);
                          DEVICE_ID_GAP (device_id/web_id/tea_uuid absent);
                          REGION_MISMATCH (010B hardcoded JP, live session VN);
                          CONVERSATION_CONTEXT_GAP (010B always demanded a NEW
                          conversation; the browser reuses the durable skill
                          conversation with last_section_id/last_message_index);
                          RUNTIME_TOKEN_GAP (rotating msToken vs static);
                          FINGERPRINT_GAP (fp=verify_… vs s_v_web_id);
                          QUERY_PARAM_GAP (6 missing version/platform params);
                          POLLING_DRIFT (010B poll schema is WRONG — proven by
                          712012002); OUTPUT_HOST_DRIFT (video CDN is
                          v16-dola.dola.com + ibyteimg.com, outside the 010B
                          download allowlist). chat_ability was NULL even in the
                          browser's successful video dispatch — the 010A
                          ability_type=17 theory was NOT the blocker.
  plausible:              the backend enqueues but the attestation layer
                          silently drops generation for unattested clients
                          (exactly the observed 200+silence signature).
  unknown:                exact server-side decision logic; a_bogus signing
                          algorithm; WS protobuf frame schema.

FINAL DOLA TRANSPORT
  BrowserNetwork (Route B/C hybrid): managed authenticated browser runtime
  (DOLA_RE_PROFILE) + UI trigger ONLY for dispatch (composer + 動画を作成
  video-mode button) + NETWORK AUTHORITY for every identity (SSE_ACK receipt,
  creation ids, type-2 download_url). Film Core never reads identity from the
  DOM. NativeHTTP (Route A) is disqualified on evidence: it requires
  reproducing a_bogus signing + mssdk device attestation — a moving anti-bot
  target, not deterministically reproducible. Cookie-HTTP stays dead (010A/
  010B latches preserved, never reused).

QUALIFICATION
  M2 (browser video qualification — the optional slot, deliberately spent on
  the evidence-selected transport instead of a native-HTTP attempt):
    7/7 chain verdicts PROVEN — user action → release → SSE_ACK receipt →
    stable ids → poll/stream → exact generation → exact video
    (5.041667s, 1248x704, hevc, full decode OK,
    sha256 9ef5aedaab19773f40abe962176ee643cbfec85218cd57db06687118759ffc34,
    creation 1543843763689489, host v16-dola.dola.com).
  F2A: PROVEN — 10.080000s, 1280x720 24fps, hevc, full decode OK,
    sha256 970018be88d579a6… (full value in V2_010C_F2A_EVIDENCE.json),
    dispatched through the qualified adapter (DolaBrowserNetworkAdapter) with
    the 動画を作成 video mode; prompt built from the FROZEN V2-009 plan
    (traversal geometry + causal environment + forbidden geography).
    Worker advisory: output is the 10s duration class (the video mode default
    overrides a "5-second" prompt text) — trim-compatible with the 2.8s
    editorial slots; carry a "Dola AI" corner watermark (unwatermarked URL
    variants EXIST in the same creation object — recorded in the protocol
    map); travel direction reads camera-facing rather than the frozen
    frame-left lateral travel. CREATIVE_QC = DEFERRED_TO_OWNER (owner visual
    read is authoritative; frame strips in owner_review/).
  F2B: STOPPED_PROVIDER_CREDIT_REFUSAL — the dispatch was released and the
    provider refused BEFORE any generation: "2 video credits will be used,
    only 1 remains today" (F2A 10s cost 2 + M2 5s cost 1 of 4 daily). The
    video-mode default (10s class) needs 2 credits. Explicit, deterministic,
    no ambiguity, NO latch; F2B = ONE authority is spent, no retry. A 5s-class
    F2B (1 credit, trim-compatible) can be dispatched through the SAME
    qualified adapter under a NEW Owner-authorized scope.

MUTATIONS USED / 4
  m1_browser_oracle 1 + m2_browser_video_qualification 1 + f2a_dola 1 +
  f2b_dola 1 (provider-refused, zero generation effect) = 4 = HARD MAX.
  No unauthorized retry. No alternate transport after any ambiguity (no
  ambiguity ever occurred in 010C).

TESTS
  Full regression: 1294 passed (1285 baseline + 9 new 010C replay/contract
  tests over golden fixtures recorded from the live captures; fixtures pass a
  fail-closed secret scan: msToken/a_bogus/fp/x-signature/x-expires redacted,
  including inside double-escaped JSON strings).

SECRET AUDIT
  No secret committed/logged: cookies and web-storage values exist only in
  process memory and the DPAPI blob; raw CDP captures are DPAPI-encrypted at
  session close; tracked fixtures/evidence are URL-redacted and marker-
  scanned (the scanner itself caught and forced the fix of one msToken/
  a_bogus leak before anything was committed). Secret-store: DPAPI current-
  user, outside git-tracked evidence.

PROVIDER LINEAGE
  Durable conversation 38417972940811793 (Seedance 2.0 skill): M1 =
  message_index 7 (question 1541253913616145 → reply 1546406012981009,
  image creations ×4); M2 = video creation 1543843763689489 (5.04s);
  F2A = video (10.08s, sha 970018be…); F2B = message released, generation
  refused pre-effect. 010B latch and D-G1 quarantine untouched.

EVIDENCE PATHS (state dir projects/quality_v2_010c_dola_fullstack/)
  V2_010C_CUSTODY.json — Layer 0 custody, baselines, latch non-reuse
  V2_010C_SESSION_ACQUISITION.json — session inventory (no values)
  V2_010C_CURRENT_PROTOCOL.json — Layer 4 map (+ late-observed facts)
  V2_010C_PROTOCOL_DIFF.json — Layer 5 diff vs 010B cookie-HTTP
  V2_010C_TRANSPORT_DECISION.json — Layer 6 decision + budget plan
  V2_010C_BROWSER_ORACLE_EVIDENCE.json — M1 chain (v2, image-class output)
  V2_010C_M1_OUTPUT_OBSERVATION.json — read-only completion correlation
  V2_010C_M2_QUALIFICATION_EVIDENCE.json — M2 7/7 PROVEN
  V2_010C_F2A_EVIDENCE.json — F2A PROVEN + separated QC
  V2_010C_F2B_EVIDENCE.json — F2B explicit credit refusal
  V2_010C_CANDIDATE_SEAL.json — seal (f2b check open, all others green)
  mutation_authority.json + reservations/receipts — governance ledger
  runtime/capture/raw_*.jsonl.dpapi — raw captures (DPAPI-encrypted)
  owner_review/F2A_t*.png — frame strips for the owner visual read
  Tracked tools: tools/dola_010c_*.py, tools/run_v2_010c_*.py,
  tools/build_v2_010c_*.py, tools/custody_v2_010c.py, tools/seal_v2_010c.py
  Tracked tests: tests/test_v2_010c_replay_001.py + tests/fixtures/v2_010c/

WORKTREE
  010C work products committed on quality-v2/010c-dola-fullstack-re;
  pre-existing untracked allowlist unchanged (FLOW_*.md, OWNER_REVIEW/,
  chrome_profile/, scratch/, fixtures/requal002/, uv.lock, …).

STOP REASON
  F2B could not be generated: the provider refuses any further video today
  (1 credit remaining; the qualified video-mode default class costs 2). The
  F2B = ONE authority forbids a parameter-corrected re-dispatch. Owner input
  (fresh scope for ONE 5s-class F2B) is the single remaining step to reach
  COMPLETED_CANDIDATE on this branch's successor.
```
