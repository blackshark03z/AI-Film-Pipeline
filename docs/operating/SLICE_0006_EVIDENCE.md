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
