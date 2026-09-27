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
