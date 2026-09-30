# SLICE-0011 compact A successor — Owner-authorized execution

## Authority and baseline

Base revision: `86acfeb1166717ab4ec76c689dd0e862c57ef134`.
Exact Owner brief SHA256:
`377ba947f30f3b8b664a33e5950889d261964ebecfa2374a369719b0ad60a54f`.
This new brief supersedes the implementation-only authority in the earlier
successor proposal. It authorizes exactly one new A attempt/job and at most one
MZZa6b invocation, using the existing verified reference. No B, upload, alternate
provider, account/billing change, selection or assembly is authorized.

Protected attempt:
`attempt_3b7fa3f988caeb979db14c6332be05c535aca9af6c3514c459aa74302d48d4ca`.
Protected job:
`job_26f3a0b279b6d43ca6ad4cff7084ebc552f0ba7ad792c8519e74fd526490a6b8`.
Its INCONCLUSIVE state, dispatch_count=1, no binding/output, and ambiguity fact
remain intact. Successor lineage does not resolve or remove that ambiguity.

## Milestones

1. Implement a separate fixed-authority successor entry in the original ledger.
   Allocation inserts attempt, job and immutable authority together. Reservation
   consumes the grant, increments the new job counter and journals RESERVED in
   one transaction. Concurrency, rollback and crash tests must pass. Ordinary
   shot allocation/dispatch/ambiguity gates stay unchanged.
2. Verify focused/full tests, compileall, diff check, canonical/SoT integrity and
   independent review before opening Flow. Freeze the implementation revision.
3. Read cached cookies into an ephemeral browser without changing the existing
   credential export/profile. Validate exact project/catalog contract and frozen
   receipt. Capture a fresh baseline; compile A's 430-character body plus exactly
   one marker using the actual new job ID. Freeze intent and reserve before POST.
4. Submit once; retain only sanitized diagnostics and request hashes. Attribute
   only exact project/reference/model/marker/new identity with agreeing qualified
   lineage. Poll for at most 600 seconds. No output or any ambiguity stops.
5. For one uniquely bound identity, download exact bytes, hash, inspect MP4/8s/
   16:9 and decode EOF. Run local technical QC; prepare a full-resolution middle
   PNG and five chronological samples with the exact reference. Human character,
   continuity and editorial criteria remain uncertain, with no SelectedTake.

Stop at OWNER_CHARACTER_CONTINUITY_REVIEW_GATE or OWNER_AMBIGUITY_GATE. A durable
stop blocks the successor CLI before any new provider access, including stops
before reservation. A consumed grant blocks restart even without a result file.

## Verification before live execution

23 successor cases PASS, including concurrent allocation/reservation, transaction
rollback, frozen provenance, wrong scope, baseline drift, terminal restart,
absence/conflicting candidates, download failure and complete offline exact-byte
acquisition/QC/review with no selection. Full regression: 302 PASS (62.99s).
Compileall src/tools/tests PASS; git diff --check PASS. Frozen SoT, schemas,
fixtures, canonical compiler and compact reduction policy have no diff from base.
Production database remains SHA256
`81cf752dcadf9df60156f77e2971aba47420e9fe68fa8903b18c17cbedcf10bd` before live;
qualification database remains
`6054581a1d2fd9824b3a8691f964a11d42b7e9781691612304b7c53869232adf`.
Pre-existing Owner scratch/ is preserved and excluded from staging.

Independent review cleared the successor implementation with no material blocker:
89 offline focused cases PASS, diff check PASS, historical frozen intent unchanged.
Parent focused suite: 89 cases (the final result is recorded below).
Live result is pending. This milestone is offline implementation evidence, not
provider acceptance or visual continuity proof.
Runtime evidence will be under
`projects/character_continuity/slice0011/successor_a_compact_v1/`.
