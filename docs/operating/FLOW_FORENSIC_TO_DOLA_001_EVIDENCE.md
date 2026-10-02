# FLOW-FORENSIC-TO-DOLA-001 — evidence record (2026-10-02)

Package: [FLOW_FORENSIC_TO_DOLA_001_WORK_PACKAGE.md](FLOW_FORENSIC_TO_DOLA_001_WORK_PACKAGE.md)
(frozen). Base `85e88cc87e0cd9f0a523fe399072655c20f700b4`, package HEAD
`570ca85e83cf55c272a97938399051a87c3d85ba`, branch
`zcode/flow-forensic-dola-fallback-001`, worktree
`D:\AI FILM MAKER\AI-Film-Pipeline-Flow-Dola-Qual`.

## Terminal state: OWNER_AMBIGUITY_GATE

Flow was classified `FLOW_DEGRADED_UNAVAILABLE` at C4 and its mutation path
frozen. The Dola fallback produced one bounded submission whose possible
external effect is ambiguous (no receipt), which per the frozen critical rule
stopped all further mutation on both providers. No retry was performed
anywhere; no remaining budget is usable.

## Clock

```text
FLOW_FORENSICS_STARTED_AT = 2026-10-02T01:21:50Z
FLOW_FORENSICS_DEADLINE   = 2026-10-02T05:21:50Z
Flow phase ended          = 2026-10-02T02:00Z (39 minutes; pivot decision)
Dola phase ended          = 2026-10-02T02:47Z (mutation frozen)
Total wall clock used     = ~1h25m of the authorized window
```

## Prior evidence consumed (read in full before any mutation)

`FLOW_CURRENT_R2V_CONTRACT_20261001`, `FLOW_R2V_OPEN_INVESTIGATION_20261001`,
`FLOW_R2V_INDEPENDENT_STORYAUTO_RECONSTRUCTION`,
`FLOW_R2V_CURRENT_CONTRACT_CANARY_20261001`, `STORY_AUTO_R2V_LIVE_CONTROL_20261001`,
`docs/operating/LIVE_RUNTIME_QUAL_001_EVIDENCE.md`. Story Auto's Dola provider
code, docs and evidence (`dola-browser-ui-canary-4-20260923`, cookie account
store) were read as reuse inputs for Phase D.

## C1 success-vs-failure matrix (OBSERVED unless noted)

| Release | Date | Project | Path | Reference | Result |
|---|---|---|---|---|---|
| manual UI gen `8d88d601` | 09-30 | a94d36d0 | native UI | project media (69ac3d31) | SUCCESS (CAE, acquired) |
| UI canary `a47636b8` | 10-01 | f6b40e79 | native UI | 347f9951 | SUCCESS (+13s CAE, acquired, QC PASS) |
| successor `job_4d11911…` | 09-30 | f6b40e79 | direct RPC | stale media | null / no delta |
| current-contract canary | 10-01 | f6b40e79 | direct RPC | 53b5a413 | null / no delta |
| reproof fresh A `job_3f809a1…` | 10-01 | f6b40e79 | native UI | 53b5a413 | null / no delta |
| LIVE-RUNTIME-QUAL G1 | 10-02 | f6b40e79 | native UI | 53b5a413 | null / no delta (2×40 min windows) |
| **F-G1 `job_0884f2b…`** | 10-02 | f6b40e79 | native UI | **347f9951** | **null / no delta (25-min window)** |

INFERENCE: after F-G1, reference identity is disproven as the discriminator;
every current-contract-era native-UI route this account can express has been
re-executed cleanly and produces the identical null-ack
(`response_shape_hash f072cbec…`, HTTP 200, 229 bytes, parsed null) with zero
catalog delta. UNKNOWN: the provider-side cause (risk scoring, entitlement,
scheduling, or account/project flagging).

## C2 read-only differential (c2_differential/differential.json)

Both projects: host `flow.google.com`, identical build
`boq_labs-ai-sandbox-frontend_20260929.10_p1`, identical qualified settings
tokens, **no high-demand/outage banners**, historical success records durable
(CAE, `veo_3_1_r2v_lite`, exact reference slots). Catalogs: A=16 records,
B=5 records. Both B references present. No mutation was performed to inspect.

## C3 F-G1 (one released Flow Generate; 1/3 used, 2 dead)

Hypothesis: the historically successful route (f6b40e79 + reference 347f9951
+ `veo_3_1_r2v_lite` + native UI) still admits R2V. The reference chain was
re-attested live (`refbind_c5a8838b…`: as29s readback sha `93fa8edf…` ==
receipt bytes, strong content match to the immutable `dc766e13…` source).
One guard-qualified Generate was released (`GENERATE_REQUEST_OBSERVED`,
contract `native-ui-r2v-canonical-20261001-v1`), HTTP 200 null-ack, zero
catalog candidates in 1500 s (25 polls) and zero delta in the late read-only
check. `AMBIGUOUS_EVIDENCE` recorded; `EXTERNAL_EFFECT_UNRESOLVED`.

## C4 Flow decision

`FLOW_DEGRADED_UNAVAILABLE` — recorded in `C4_FLOW_DECISION.json` with the
full basis. Flow mutation frozen; budget 1/3 released, remainder not retry
authority. Disproven: reference identity, build drift, banner-state, local
automation defect. The LIVE-RUNTIME-QUAL-001 G1 job was never retried or
reinterpreted.

## C5 Dola discovery

Reused (SEARCH→REUSE→COMPOSE→ADAPT): the Owner's Story Auto
`dola_cookie` observed contract — `www.dola.com /chat/completion` SSE
(SSE_ACK → durable `conversation_id` receipt), `/im/chain/single` poll with
`client_request_id` echo verification, allowlisted CDN download —
live-qualified by Story Auto on 2026-09-23 (canary 4: task `38417972940811793`
succeeded, 5s MP4 acquired). Model `seedance_v2.0` (observed in upstream
seed; acceptance observed post-hoc). Durations 5/10 s; aspects 16:9/9:16/1:1.
Encrypted account store: `dola-main` (no credential), `dola-profile-20260923`
(session alive at preflight via read-only probe).

## C6 Dola boundary and D-G1 (one released Dola submit; 1/2 used, 1 dead)

New production boundary (no Dola semantics in Film Core):

- `src/film_pipeline/providers/dola_provider.py` — `DolaCookieTransport`
  (submit-once with persisted-receipt callback, identity-echo poll,
  host-allowlisted ffprobe-validated download, fail-closed ambiguity and
  hygiene classes) + `probe_session` read-only liveness probe.
- `tools/run_dola_qualification_d1.py` — durable orchestration:
  ShotSpec(5s T2V) → PromptPlan → `seedance_dola` RoutingDecision →
  GenerationAttempt → ProviderJob → ledger preclaim → `reserve_dispatch` →
  one submit → journal facts (`GENERATE_REQUEST_OBSERVED`,
  `PROVIDER_RESPONSE_OBSERVED`, `PROVIDER_ACCEPTANCE_OBSERVED` bound to the
  transport-reported request hash) → poll → exact acquisition → Asset →
  technical QC → restart/recovery proofs (never re-submit).
- `tests/test_dola_provider.py` — 8 focused offline proofs (receipt-first
  persistence, request binding, failure classes, identity echo required,
  ambiguity fail-closed, host/atomic acquisition, session probe, cookie
  hygiene). 8/8 pass; no network, no credentials.

**D-G1 outcome: `OWNER_AMBIGUITY_GATE` — `DOLA_SUBMISSION_AMBIGUOUS_NO_RECEIPT`.**
One POST reached the wire; no SSE_ACK conversation receipt came back; no
conversation identity exists, so read-only reconciliation cannot determine
whether the provider created a generation. A read-only session probe after
the fact shows the session still alive (not credential death). The exact
HTTP failure class was lost in a local handler crash and is UNKNOWN. Per the
frozen critical rule, the second Dola budget is not retry authority: D-G2 was
never released and Dola mutation is frozen.

Local defects during Phase D (all pre-dispatch or post-release local code,
each preserved as `*.local-defect-*.json`, none a provider event): missing
store initialization; journal fact-kinds/pipeline mismatch; rendition
constant; preclaim filename clash; post-release handler crash (invalid
`AMBIGUOUS` job literal + lost failure class). The Dola ledger consumption
entry was recorded post-hoc with explicit `recorded_post_hoc: true` — the
release itself is evidenced by the durable journal (`RESERVED`,
`PROMPT_VERIFIED`, `dispatch_count=1`).

## C7 adversarial review findings

- Submit-wire certainty: pre-wire validation failures classify
  `NOT_DISPATCHED`; the AMBIGUOUS class can only arise post-connect, so the
  "released on the wire" claim holds.
- Receipt-parser drift since 2026-09-23 cannot be distinguished from server
  rejection read-only — recorded as the residual unknown, not resolved by
  assumption.
- Budget accounting: Flow 1/3, Dola 1/2, both consumption entries durable;
  all other preclaims without consumption are documented pre-release stops.
- No cookies, tokens, signed URLs or provider bodies are persisted anywhere
  in the tracked delta; the cookie is loaded in memory only.
- Historical custody: both source stores byte-identical; source repo
  untouched; LIVE-RUNTIME-QUAL-001 evidence untouched.

## C8 delivery

- Full regression: 497 passed (489 floor + 8 Dola transport proofs).
- `compileall -q src tools` clean; `git diff --check` clean; tracked-delta
  security scan clean (no secrets/cookies/tokens/URLs/profile material).
- Tracked delta: `src/film_pipeline/providers/dola_provider.py`,
  `tests/test_dola_provider.py`, `tools/flow_dola_forensic_c2_differential.py`,
  `tools/run_flow_forensic_fg1.py`, `tools/run_dola_qualification_d1.py`,
  this document. Evidence directories remain gitignored (`projects/*`).
- Delivery HEAD: recorded in the final handoff report.

## Remaining UNKNOWNs / non-claims

1. The provider-side cause of the Flow null-ack/no-delta behavior (risk
   scoring, entitlement, project/account flagging, scheduling) — not
   resolvable read-only from here.
2. Whether the Dola submit created a server-side conversation (Owner can
   inspect the `dola-profile-20260923` chat UI manually; if a generation is
   sitting there it was produced by job `job_1bcfd770…`).
3. The exact HTTP class of the Dola submit failure (lost in the local crash).
4. Dola T2V route is NOT claimed stable: one ambiguous submit is not a
   qualification. The transport and its offline proofs are the deliverable.
5. No claim about Flow R2V admission on this account today.

## Routing recommendation

**NEITHER, for character-continuity production today.** Flow R2V is degraded
at the provider for this account (six clean releases across two references,
two projects, identical null-ack/no-delta). Dola's cookie transport is
technically sound and offline-proven but its one live submit ended ambiguous
— it needs exactly one Owner-side manual check of the account chat UI (did a
conversation appear?) and, if clean, a fresh bounded qualification before any
production routing. The Owner decision points are: (1) manual Flow UI
generation to isolate account-level risk flagging; (2) manual inspection of
the Dola account; (3) only then re-approach either provider with new
authorization.
