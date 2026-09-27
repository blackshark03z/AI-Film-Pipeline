# SLICE-0006 live canary evidence ledger

## Frozen authority and starting state

- Work package: `CURRENT_SLICE.md`, supplied by the Owner; maximum five fresh normal Flow Generate transactions. Stop after one complete proof.
- Source baseline: `42cc74c2cab1cc0dfb25333d9dc721b4ae79e6df` from SLICE-0005; full deterministic suite 103 passed.
- Dispatch semantics: `AT_MOST_ONCE_WITH_POSSIBLE_LOSS`. A reservation consumes the attempt's budget; no attempt redispatch.
- Prior SLICE-0004 DB SHA-256: `4c3e216abff5bfd951f0ffb7c0dedc3d3432e8253f3af6211c4ff3c1f84b597c`, one job, `dispatch_count=1`, `INCONCLUSIVE`. This history remains read-only.
- Current bound Flow project: `51ea107f-20b9-4222-a133-b4ccbfb1963b`. It hosted the prior uncertain attempt and cannot be used for an exact new delta without a separately proven way to exclude late prior output.

## Initial gates

- Active cookie and session files: present outside Git; contents not logged or copied.
- Active Flow provider preflight: `AUTH_REQUIRED / PROJECT_READBACK_AUTH_REQUIRED`.
- Candidate Flow provider preflight: `AUTH_REQUIRED / PROJECT_READBACK_AUTH_REQUIRED`.
- Operator normal authentication: completed through the existing headed AutoVideoPipeline login helper. It exported a fresh candidate cookie atomically to the configured local path; no cookie value was logged.
- Fresh candidate Flow provider preflight against the prior bound project: `READY / PROJECT_READBACK_READY`.
- Candidate account read-only project discovery: 21 accessible project IDs, including the prior bound project. No project was selected or created by this discovery.
- Separate project/isolation: pending proof.
- Fresh GenerationAttempts: 0.
- Fresh ProviderJobs: 0.
- Live Generate reservations/transactions conservatively used: **0 of 5**.
- Assets: 0.

No Generate, project creation, credential promotion or prior-job reconciliation occurred during this initial gate. The candidate is READY against the old project, but that project is unsafe for a new exact-delta attempt while the prior effect remains uncertain. The next live effect requires a separate, proven correlation domain first.

## Attempt 1 — quarantined uncertainty

- Source candidate at reservation: `3884499e4da702e556877b1ead987c1b28a9c409`.
- Fresh dedicated Flow project: `d223e652-1ebc-4db1-929b-c2d84cab70f4`; project creation used the existing authenticated helper. Candidate preflight `CONNECTED / valid=true`, atomic activation `ok`, AI Film preflight `READY / PROJECT_READBACK_READY`.
- Pre-dispatch passive baseline: 0 identities, 17 observed responses, 0 rendered video tiles, 0 generation indicators. Fresh runtime DB began with 0 ProviderJobs; SQLite journal schema and write transaction were available.
- GenerationAttempt: `attempt_bd569035b0b8c857f551d96f7a74aa61acf71ccb9dbf0a6d242d1277944d656e`.
- ProviderJob: `job_f7c54cac2162702395ab8743ce4e8f9bf5cc4c55f0d3ad0deaad08e46a2f4021`; dispatch_count=1, submission_state=`SUBMISSION_RESERVED`, status=`INCONCLUSIVE`.
- Durable facts: `RESERVED` only. No durable prompt verification, click, request, response, acceptance, provider identity, binding or Asset. The exact external Generate count remains unknown under the conservative reservation rule.
- Project disposition: `QUARANTINED_UNCERTAIN`. No second Generate or output attribution is permitted there.
- Slice budget: **1 used, 4 remaining**.

Read-only inspection after the stop found one visible editable ProseMirror prompt and one visible Generate button, disabled while the prompt is empty. The frozen submit path tested button enabled **before** filling. This is a strong explanation for the pre-prompt stop, but the original exception type was not persisted, so it is an inference rather than a proved external-effect classification. The prior uncertainty remains unchanged.

Remediation options considered before changing source: (A) fill exact prompt, verify readback, then wait boundedly for enabled Generate; (B) move fill before durable reservation, which changes the submit boundary and increases rework; (C) click while disabled, which cannot generate reliably. Choose A as the smallest safe correction. Offline tests must reproduce Flow's initially disabled button and prove no click when it never enables. Attempt 2 must use a separately created empty project and fresh job.

## Attempt 2 pre-dispatch preparation

- Fresh dedicated Flow project: `22da5179-8ab7-4ac8-9993-2b8e3faf4d67`, distinct from both prior uncertain projects.
- Candidate project preflight: `CONNECTED / valid=true`; safe activation: `ok / CONNECTED`; AI Film active preflight: `READY / PROJECT_READBACK_READY`.
- Stable passive snapshot: 0 provider response identities, 17 observed responses, 0 rendered video tiles, 0 concurrent indicators.
- Safe editor dry check, with no Generate: button initially disabled; full compiled multiline prompt with a shape-matched test correlation marker read back exactly; button enabled after fill; exact readback still held after enable.
- Source correction: verify prompt, wait boundedly for enabled button, verify prompt again, attach a synchronous capture guard to the exact button element, and click that pinned element only. Prompt drift or DOM replacement blocks the click. CDP trusted-click remains evidence of the UI event only, never provider acceptance.
- Offline intercepted browser cases: 8 passed, including never-enabled, prompt drift before enable, prompt mutation on pointerdown, and guarded-button replacement. Full regression: 107 passed. Independent reviewer found no remaining material issue in the guarded click change.
- Attempt 2 GenerationAttempt/ProviderJob: not yet created. Dispatch_count and slice budget remain 0 for this attempt; total slice used remains **1 of 5**.

## Attempt 2 — quarantined uncertainty

- GenerationAttempt: `attempt_99a6b502d81297adb250cc9a76fb5c1e6bebc2a161b66bab618de8f55d7d743e`.
- ProviderJob: `job_8f798e18dc48465971ebb8d5b3426b32616a6334d2936b55ad4f46e2a831c6cc`; dispatch_count=1, submission_state=`SUBMISSION_RESERVED`, status=`INCONCLUSIVE`.
- Durable facts: `RESERVED`, `PROMPT_VERIFIED`, `CLICK_ARMED`, `TRUSTED_CLICK_OBSERVED`, `PROMPT_ACCEPTANCE_TRANSITION`. No qualified Generate request, provider response, acceptance, remote identity, binding, download or Asset was journaled. Trusted click and prompt reset are UI evidence only.
- The immediate canary ended `INCONCLUSIVE`. A later read-only re-open of this project found 0 decoded identities, 0 rendered video tiles, 0 progress indicators; passive observer drain was healthy and a read-only poll returned `RUNNING`. This does not resolve whether the original click caused an external transaction.
- Project disposition: `QUARANTINED_UNCERTAIN`. No second Generate or output attribution is permitted there.
- Slice budget: **2 used, 3 remaining**.

The immediate failure cannot be reconstructed from the original process: the transport and executor previously erased exception type, and reopening the page creates a new healthy observer. Read-only checks found no current output or progress, but absence is not a no-dispatch receipt. Considered three remedies: treating click/reset or empty UI as success/failure (unsound), ignoring response read failures (would make identity observation incomplete), and recording a bounded failure code while retaining fail-closed polling. Selected the third. The source now writes only a fixed diagnostic code such as `BODY_READ_ERROR` or `RESPONSE_MODEL_LIMIT_OR_COLLISION` to the dispatch journal when the passive observer fails. Exception text, response body, URLs and credentials are never recorded. Full offline suite: 108 passed. Any new attempt still requires a separate fresh project with an independently empty baseline.

## Attempt 3 — quarantined request observer failure

- Source candidate at reservation: `32337c42207019d01b801244bdd18ba14fbf83f0`.
- Fresh dedicated Flow project: `0d480008-9319-4fdc-9d1e-6bdad5c7fe6b`; candidate preflight `CONNECTED / valid=true`, activation `ok`, AI Film preflight `READY / PROJECT_READBACK_READY`.
- Stable passive baseline: 0 identities, 17 responses, 0 video tiles, 0 concurrent indicators. Fresh journal had 0 jobs and accepted a write transaction.
- GenerationAttempt: `attempt_a79533a97f1f01506b66f0fe2486b96d79fa9a61c2a16b1e5771af38a163ed6b`.
- ProviderJob: `job_f33b926463a82ace6640ecb84ad4b32134e667ecd0be0b640e7deca7c467890f`; dispatch_count=1, submission_state=`SUBMISSION_RESERVED`, status=`INCONCLUSIVE`.
- Durable facts: `RESERVED`, `PROMPT_VERIFIED`, `CLICK_ARMED`, `TRUSTED_CLICK_OBSERVED`, `OBSERVATION_FAILURE` with fixed code `REQUEST_OBSERVER_ERROR`, `PROMPT_ACCEPTANCE_TRANSITION`. No qualified Generate request, response, acceptance, identity, binding or Asset.
- The observer callback originally inspected `post_data` for **every** request after arming, including unrelated browser traffic. A read failure or another exception anywhere in that callback could terminate exact observation. The fixed code does not identify which operation failed; this remains a hypothesis, not an external-effect classification.
- Project disposition: `QUARANTINED_UNCERTAIN`; no further Generate there. Slice budget: **3 used, 2 remaining**.

Remedy options considered: ignore callback errors (unsafe incomplete evidence), allow an output without network evidence (weakens the specified proof), or filter to the exact Flow POST endpoint before reading a body and retain explicit stage diagnostics. Selected the last. A relevant request body/classifier/journal failure still fails closed; unrelated POST bodies are not read. Two intercepted cases plus the full 110-test suite pass. Attempt 4 requires another independently empty project.

## Attempt 4 — bounded polling without video identity

- Source candidate at reservation: `6cdb6deedfe29f1c345bf06fff7c354ac4f7e22d`.
- Fresh dedicated Flow project: `9543b970-a9ab-461a-98d2-2bc8e6767e50`; candidate preflight `CONNECTED / valid=true`, activation `ok`, AI Film preflight `READY / PROJECT_READBACK_READY`.
- Stable passive baseline: 0 identities, 17 responses, 0 video tiles, 0 concurrent indicators. Journal initially had 0 jobs and was writable.
- GenerationAttempt: `attempt_04591f963c47b8a25709040c226f7669862b7bf35b8538d970c12269ef65f1a5`.
- ProviderJob: `job_30fbba2250359ed4fd665511800033597235735b4cdecb69272300dca5a2302b`; dispatch_count=1, submission_state=`SUBMISSION_RESERVED`, status=`RUNNING` at bounded timeout.
- Durable facts: `RESERVED`, `PROMPT_VERIFIED`, `CLICK_ARMED`, `TRUSTED_CLICK_OBSERVED`, `PROMPT_ACCEPTANCE_TRANSITION`. No qualified request, response, acceptance, provider video identity, binding or Asset. The canary returned `INCONCLUSIVE` because the 60-poll window ended without completion. An independent read-only view during that window also showed 0 identities, 0 video tiles and 0 progress indicators; absence does not cancel the external uncertainty.
- Project disposition: `QUARANTINED_UNCERTAIN`; never Generate there again. Slice budget: **4 used, 1 remaining**.

A later read-only screenshot of the project displayed `Nano Banana 2` in the creation settings. New browser contexts opened fresh projects in image mode. The source had never selected or verified Veo video mode before the prior four reservations. This falsifies the assumed video submit surface; it does not prove what external image effects, if any, those clicks caused. The projects and jobs remain quarantined.

## Final fresh project — blocked before Attempt 5 reservation

- Fresh dedicated Flow project: `bb651601-cd00-447a-bd05-c6839580f56c`; candidate preflight `CONNECTED / valid=true`, activation `ok`, AI Film preflight `READY / PROJECT_READBACK_READY`.
- Read-only empty baseline: 0 identities, 17 observed responses and 0 video tiles. No GenerationAttempt or ProviderJob exists in its fresh runtime DB; dispatch_count=0.
- The normal settings menu was inspected without Generate. Video → Frames → `Veo 3.1 - Fast` → x1 displayed a 20-credit cost and an explicit insufficient-credit warning. `Veo 3.1 - Lite` → x1 displayed a 10-credit cost and the same warning. With Fast selected, the visible control was `prompt-warning-button` labelled as insufficient credits; the normal Generate button was absent.
- Source now configures and verifies Veo Fast video mode before creating a new job. It checks the credit warning and Generate-control presence before freezing/reserving. An independent review identified that an empty prompt could conceal a later credit warning; source now also previews the exact prospective frozen prompt, waits for a stable enabled Generate control without clicking it, and verifies its hash against the subsequently frozen job before any reservation. Recovery of existing jobs remains independent of this new-job gate. The live no-Generate pre-dispatch run before the exact-prompt refinement returned `INCONCLUSIVE / FLOW_VIDEO_CREDITS_INSUFFICIENT / dispatch_count=0`; the DB had 0 jobs. The exact-prompt refinement passed the full 111-test suite, including a no-click credit-warning case. Its live execution could not be completed because both active and candidate Flow sessions then returned `AUTH_REVOKED / valid=false`; AI Film preflight returned `AUTH_REQUIRED / PROJECT_READBACK_AUTH_REQUIRED`. No fifth Generate was invoked or reserved.
- Project disposition: `CLEAN` with no generation. The fifth authorization remains unused; slice total **4 used, 1 remaining**. No billing or subscription action was taken. Stop at Owner authentication and credit authority boundary.

## Owner login, account correction and final Attempt 5 — live lineage proven

- The Owner reported that Google Flow redirected from the requested `hoangbsea` account to `khoikk03` when the login helper targeted the prior project URL. The helper was stopped. Its existing headed login workflow was restarted with an isolated local browser profile and the Flow home URL, so the Owner could select and authenticate `hoangbsea` normally. No credential entry was automated. The helper atomically exported a 49-cookie candidate outside Git. Read-only Flow account-menu inspection matched `hoangbsea` and did not match `khoikk03`; the account displayed 1,050 Flow credits. No cookie values were printed or recorded.
- The earlier `bb651601-cd00-447a-bd05-c6839580f56c` project remained clean but was inaccessible to the requested account. It received no GenerationAttempt, ProviderJob or Generate. It was relinquished as an unusable binding. The authenticated account's existing project-creation helper created replacement dedicated project `df0f30d1-e59e-4d87-a6b3-a2a9bc3257e3` for the still-unused final attempt; project creation was not a Generate.
- Candidate preflight on the replacement project: `CONNECTED / valid=true`; safe activation: `ok`; AI Film preflight: `READY / PROJECT_READBACK_READY`. Stable passive project baseline: 0 video identities, 17 observed responses, 0 video tiles, 0 active generation indicators, healthy observer. Attempt-5 DB initially had 0 jobs and a writable journal. Video → Frames → Veo 3.1 Fast → x1 was verified. The exact prospective frozen prompt read back byte-for-byte, the Generate button stayed enabled, and there was no insufficient-credit warning. No account, billing or subscription gate appeared.
- Source candidate at reservation: `40df72b1e9b14123f3697a01b760416f96ecaa78`. GenerationAttempt: `attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5`. ProviderJob: `job_62eab53994a2b8b1bde875b67f0068da97798a02f8aa75f8765d042edb07f0ea`. `dispatch_count=1`; one trusted normal UI Generate was observed. No second Generate occurred. The original browser's bounded 60-poll window ended `RUNNING / INCONCLUSIVE` without an exact identity in its in-memory decoder; that did not authorize redispatch.
- A fresh read-only project load independently decoded exactly one new provider response identity and exactly one matching rendered video tile, with no unresolved tiles. Recovery of the **existing** job, without Generate, recorded `REMOTE_IDENTITY_OBSERVED`, created one immutable binding and moved the job to `SUCCEEDED`. Provider identity: `response-tuple:df5e2bf2-c980-44f2-953a-73c3c536962f:df0f30d1-e59e-4d87-a6b3-a2a9bc3257e3:3776f9fe-d18b-4eb2-978b-7834e58794ca`; binding hash: `9b4f79287063aa1b8c9b35af78191f4a6ed60b8154d8c64179a61c6aed3b86d0`.
- Official Download from that exact tile produced `projects/flow_canary/outputs/95d299c70b8a5a37ec1e1fed.mp4`, 10,150,400 bytes. `ffprobe`: valid video, 8.0 seconds, 1280×720. SHA-256: `c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf`. One Asset was persisted. Fresh SQLite lineage readback returned the frozen ShotSpec, PromptPlan, RoutingDecision, GenerationAttempt, ProviderJob and Asset; the immutable identity binding was separately read back. Fresh file hashing matched the persisted Asset SHA-256.
- Durable Attempt-5 facts: `RESERVED`, `PROMPT_VERIFIED`, `CLICK_ARMED`, `TRUSTED_CLICK_OBSERVED`, `PROMPT_ACCEPTANCE_TRANSITION`, `REMOTE_IDENTITY_OBSERVED`, `IDENTITY_BOUND`, `DOWNLOAD_STARTED`, `DOWNLOAD_VALIDATED`, `ASSET_PERSISTED`. The exact Generate RPC classifier did **not** record `GENERATE_REQUEST_OBSERVED` or `PROVIDER_RESPONSE_OBSERVED`; no provider-native acceptance receipt was qualified. The provider-observed **output identity** came from passive response decoding, but the sanitized Generate request/response capture subgoal remains **UNPROVEN**. Preserve `AT_MOST_ONCE_WITH_POSSIBLE_LOSS` and `submission_state=SUBMISSION_RESERVED` rather than interpreting a trusted click or output as a native acceptance/idempotency receipt.
- Final Attempt-5 project disposition: `PROVEN` for the work package's explicit E2E acceptance conditions: one reserved Generate, exact isolated output identity and tile, immutable binding, official Download, valid video, SHA-256 Asset, complete fresh SQLite lineage, no gallery-order inference and no blind retry. Slice budget: **5 used, 0 remaining**. Full regression: **111 passed**. Stop SLICE-0006; do not start another Generate or SLICE-0007.
