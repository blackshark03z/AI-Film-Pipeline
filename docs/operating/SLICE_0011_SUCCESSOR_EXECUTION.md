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
Parent focused suite: 133 PASS (19.91s); successor-only 23 PASS (9.05s).
This milestone is offline implementation evidence, not provider acceptance or
visual continuity proof.
Runtime evidence will be under
`projects/character_continuity/slice0011/successor_a_compact_v1/`.

## Final live stop — OWNER_AMBIGUITY_GATE

Implementation revision: `b86b539e7e5f4e99a228a44dd73332d5da2e7c95`.
One invocation of the bounded entry stopped during session authentication with
`OwnerAuthRequired`. The exact project/session was not established. RPC counts
are empty: MZZa6b=0, catalog=0, reference uploads=0, Shot B=0, Dola/Seedance=0.
Browser navigation/authentication was attempted; no generation or billing action
was invoked. No second session, alternative cookie or login refresh was tried.
Cached credential bytes, length and modification time remain unchanged.

New successor attempt ID: **not allocated**. New ProviderJob ID: **not allocated**.
No authority allocation/consumption record was created; there is no actual new
marker, frozen provider prompt or fresh catalog baseline. This is an auth stop
before allocation, not compact-prompt provider qualification. The intended
provider body below is an exact deterministic preview, **430 characters / 70
words** excluding the placeholder marker. It was not submitted:

```text
8-second locked eye-level medium close-up, 16:9. Use the exact image reference: one illustrated adult woman with teal bob hair, crimson round glasses, a mustard jacket over a blue shirt, silver triangle earrings and a beauty mark below her right eye; facing slightly right, she breathes gently and blinks once in a daytime living room, window left, sofa and plant right. Keep her face and outfit stable; movements subtle and calm.
[FILM-<new_provider_job_id>]
```

Reference Asset:
`asset_70834935ccb760367645411d115c0c24243f4dd921182ef4b9502cad382062ff`.
Local SHA256:
`31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531`.
Verified media UUID: `53b5a413-7bb5-4f97-9be4-2461794a7d80`.
Intended project: `f6b40e79-d6f8-4354-80ae-c863260e96f5`, model `abra_r2v_8s`,
8 seconds, 16:9. This continuation did not verify access to that project; the
receipt remains the existing qualified receipt. Account identity remains
`project_scoped_unverified_account`, not a freshly verified human account.

Sanitized response diagnostic: **absent**, because there was no MZZa6b response.
Exact output identity: none. Acquired Asset/SHA: none. Live technical QC: not run.
Character review packet: not created. SelectedTake: zero. Compact-prompt live
behavior and visual character continuity remain unverified.

Historical row snapshot before/after SHA256 is identical:
`d01f12761d25232ee22f4cd47834f9fe83efbbb6be97666524f7f6187f5aea85`.
Both complete runtime files retain the SHA256 values listed above. Final counts:
1 historical attempt, 1 historical job, 5 journal facts, 0 output bindings,
1 reference Asset, 1 historical reference reservation/4 events, 0 QC reports,
0 SelectedTakes, 0 Shot B attempts. Historical job remains INCONCLUSIVE,
dispatch_count=1, null output, with its ambiguity fact and original frozen
intent hash `ca9e145208e22e6e77cbd5e4d334a2960b800a0e99c954367040409a4f4b3f56`.
Canonical A plan hash remains
`cbc6cabae3fe2132c6ba6c3b49d78e9994ff3b670549f1980eff82e0cc9da324`.

Durable evidence: `live_result.json`, `historical_before.json`,
`historical_after.json`, `final_local_proof.json` in the runtime directory above.
The durable stop now prevents provider access on a repeated invocation. Any
future session restoration/continuation requires the Owner's explicit procedure
for this gate; the unused numerical allowance is not permission to retry.
