# SLICE-0005 protocol decision and proof plan

Base: acd2a1c210ce593cea3844341b7b0b476dc2b232. BUILD is deterministic only; no Generate, RPC replay, new project, QC or prior-job recovery is authorized.

## Exploration and comparison

SEARCH covered current source, Story Auto Flow source/tests/decision notes and AutoVideoPipeline Flow source/helpers beyond previously known files. Story Auto checkout HEAD is 5464cbb1d1c11a550b5e096647b9f94587de5bfe, but relevant experimental files are local dirty/untracked work; HEAD alone does not identify their contents. AutoVideoPipeline HEAD is 99b2a33e55db84f216ebc9706682d84c74c3b871; login helper is dirty. Reuse is of inspected local semantics, never proof of a committed/live provider capability.

| Option | Availability and strength | Cost | Decision |
|---|---|---|---|
| OPTION_A_PROVIDER_IDEMPOTENCY | RPC builder uses UUIDv5 client/session/request fields. No proved server deduplication, native operation identity or replay-safe contract. Current Generate transaction cannot be observed without a newly authorized Generate. | Private contract drift and live qualification | Reject idempotency claims; retain as unqualified research |
| OPTION_B_NETWORK_RECEIPT | Normal UI request observation can prove a browser request event. Same-request HTTP response is stronger; HTTP 200 alone is not acceptance. `MZZa6b` reference-video RPC shape is locally inspected but current text-video shape/acceptance remains unqualified. | Small passive classifier; later live qualification | Select sanitized request/response facts, never synthesize/replay RPC or infer acceptance from status |
| OPTION_C_DURABLE_JOURNAL | Story Auto has sealed atomic journals and service-owned provider-boundary callbacks. Current AI Film has one wide reserve-to-return gap. | SQLite append facts and immutable binding | Select immediate attempt-scoped write-through evidence |
| OPTION_D_REMOTE_RECONCILIATION | Passive tuples/catalog/exact prompt-reference checks can identify outputs. Empty catalog/tiles cannot prove no prior effect. Private catalog schema is held experimental. | Read-only observation and binding validation | Select bound-output recovery; absent/ambiguous evidence stays inconclusive |
| OPTION_E_ISOLATED_PROJECT | Stable empty baseline and one active attempt amplify exact delta attribution, but another account/process may write. | Existing dedicated project | Supporting condition only, never acceptance proof |
| OPTION_F_AT_MOST_ONCE_FALLBACK | Reserve before side effect and forbid any repeated submit after reservation. | Possible lost generations | Select AT_MOST_ONCE_WITH_POSSIBLE_LOSS |

Composed protocol: B + C + D + F, supported by E. A is unavailable as a proved capability. No mathematical exactly-once claim.

Reuse: Story Auto `rpc_contract.py`, `rpc_transport.py`, `response_model.py`, `video_identity.py`, `video_acquisition.py`, `live.py::DispatchEvidenceTracker` and corresponding tests. Experimental HTTP200 diagnostic explicitly says PARSED_NOT_ACCEPTANCE_PROOF. AutoVideoPipeline provides normal session/project setup and UI transport but no durable operation identity; its prefix/gallery heuristics are rejected. The existing exact tuple/official Download path is preserved.

## Protocol

Intent, external dispatch evidence and output attribution are separate. Reservation and RESERVED fact commit atomically. Typed allowlisted evidence commits as soon as actually observed, before transport return. Raw bodies, credentials and signed URLs remain memory-only. Observer failure never authorizes retry. Browser request observation is not proof of server receipt. Provider acceptance requires a separately qualified provider contract; the current production parser has no acceptance rule.

Append order records observation order. Evidence strength is a derived high-water mark, so asynchronous late weaker facts can be retained without regressing state. Rows are immutable and hash-linked; this detects accidental corruption, not a malicious actor rewriting the whole DB. Frozen job project, attempt, prompt and baseline cannot change. One provider identity can bind to only one attempt/job. Binding commits before download and survives independently of mutable job status.

Acquisition intent names one exact bound output and owned staging/final path. Validated bytes get a durable SHA/media receipt before promotion and Asset persistence. Recovery accepts only matching receipt/file bytes, never a playable file at a guessed filename. Acquisition recovery never calls Generate. Legacy consumed jobs are read-only, including the prior SLICE-0004 job; its runtime DB is not migrated.

## Failure windows

| Window | Durable local evidence | Remote evidence may exist | Redispatch | Recovery / classification |
|---|---|---|---|---|
| F0 before reserve | Frozen intent only | None from this worker | Fresh authorization required | NOT_RESERVED |
| F1 after reserve before fill | RESERVED | Unknown in lost process | Never | Read-only reconcile; INCONCLUSIVE |
| F2 after fill before click | Prompt fact if committed | Normally none; absence is not proof | Never | Reconcile; no budget restoration |
| F3 during click | CLICK_ARMED, perhaps trusted event | Request may already exist | Never | Reconcile; INCONCLUSIVE unless stronger proof |
| F4 request before response | Request fingerprint if committed | Accepted/pending/failed/unknown | Never | Request observed, acceptance unknown |
| F5 acceptance before local write | Earlier request/response facts | Provider may have accepted | Never | Qualified remote proof or INCONCLUSIVE |
| F6 identity before binding | Identity fact if committed | Exact tuple/tile may remain | Never | Validate attribution; immutable bind or INCONCLUSIVE |
| F7 binding before download | Immutable output binding | Exact official resource/tile | Never | Acquisition only |
| F8 during download | Binding + acquisition intent/partial | Exact output remains | Never | Same-output acquisition recovery; partial is not an Asset |
| F9 validated file before Asset | Receipt, SHA, owned path, binding | Output need not be reacquired | Never | Validate hash/media and persist Asset locally |

## Recovery matrix

Reservation, prompt or trusted click alone: reconcile, never retry. Request observation: reconcile; server acceptance unknown. HTTP response: preserve status/hash; no implied acceptance. Qualified acceptance: dispatch confirmed, reconcile output. Valid attributed identity observation: bind exact identity. Immutable binding: acquire only. Valid receipt/file: persist Asset without network. Conflicting/absent/unqualified evidence: INCONCLUSIVE. Isolation and remote absence never replenish authority.

## Milestones

1. Exploration/decision: complete; planner findings incorporated.
2. Durable journal, binding and recovery implementation: complete. Contenteditable multiline input has exact pre-click readback; CDP trusted-event receipt commits through the SQLite sink. Frozen project binding is checked before click.
3. F0–F9 deterministic crash/corruption/no-retry proof and full regression: 103 passed, including intercepted offline browser request/response and trusted-write failure tests. F5 lost acceptance write remains INCONCLUSIVE. No test reached Flow.
4. Independent review: completed with no material defect at the review point. Prior database and job payload byte hashes rechecked unchanged, count 1 / INCONCLUSIVE. This candidate requires commit, push and exact remote readback before the slice report closes.

## End-of-slice recommendation

A fresh live canary is justified to qualify the current Flow Generate network contract and observe whether it exposes a durable provider acceptance or operation identity. It requires a fresh attempt and explicit new authorization. Evidence required: frozen prompt and project; durable reservation; exactly one normal UI Generate; sanitized request and response facts; a separately qualified acceptance receipt if the provider exposes one; exact new response identity and immutable binding; exact official Download, technical validation and SHA-256 Asset; fresh SQLite lineage readback. If no acceptance receipt exists, report that limit and retain `AT_MOST_ONCE_WITH_POSSIBLE_LOSS`. The current slice performs none of those external effects.

Prior DB SHA-256: 4c3e216abff5bfd951f0ffb7c0dedc3d3432e8253f3af6211c4ff3c1f84b597c. Prior payload SHA-256: 46cdb3cff8dcc72845660c0773762341fcd177941edf23d3437791c0c28920fd. Prior dispatch_count=1 / INCONCLUSIVE remains immutable.
