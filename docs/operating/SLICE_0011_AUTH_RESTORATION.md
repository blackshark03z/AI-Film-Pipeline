# SLICE-0011 — Owner-authorized authentication restoration

## Current authority

Owner explicitly authorizes normal authentication/session restoration of the
preallocation OwnerAuthRequired stop, then continuation of the ORIGINAL one-A
successor experiment only after five read-only checks pass. Base revision:
`6f5ec950bb66f2dca2c8c6feecc37eb6a2960309`.
The old durable stop and all historical A evidence remain immutable. Its exact
live_result.json SHA256 is
`98951453497d3e171e00dc4cd0d351019b8644619a73a8c42098ced806b6aaba`.
No new generation allowance is created: one new A attempt/job and at most one
MZZa6b under the original authority ID. No B, reference upload, provider switch,
Dola/Seedance, billing/account change, compact policy change or Slice-0012.

## Milestones and implementation

1. Verify zero-RPC/zero-allocation stop and unchanged historical ledger.
2. Copy the existing dedicated manual Chrome profile into the Film runtime.
   Original profile and existing cookie export are read only. Open copied profile
   on the exact project using normal Chrome, without generation/upload actions;
   refresh the private cookie export only in the isolated Film runtime.
3. AuthPreflightSession rejects every RPC except Zzl0ze/as29s and rejects
   generation captcha requests. Validate coherent session metadata, exact project,
   qualified catalog, exhaustive image readbacks, unique strong content match at
   exact reference UUID and unchanged verified remote SHA256. No journal/receipt
   mutation: database file SHA and historical rows must remain unchanged.
4. Test/review the exact-stop continuation wrapper before Phase 2. Failed auth
   proof or any repeated durable execution proof blocks before provider access.
5. Only on PASS, use a new fixed evidence directory and delegate to the already
   reviewed original one-authority runner. Preserve the prior output directory.
   Capture another fresh catalog baseline, allocate one A successor, reserve
   atomically, submit at most once, attribute strongly, acquire/QC/review or stop.

Output directories:
`projects/character_continuity/slice0011/auth_restoration_v1/` and
`projects/character_continuity/slice0011/successor_a_compact_v1_auth_restored/`.
Private cookies and browser files remain ignored runtime authentication material;
only non-secret proof/report fields enter durable diagnostics. No raw RPC body,
signed URL, cookie value, WIZ or captcha token is logged/persisted as evidence.

## Phase 1 live proof

Restored session metadata succeeded from the copied dedicated profile. Read-only
preflight PASS: authenticated session, exact project accessible, catalog success,
coherent qualified metadata, reference uniquely verified and usable. Zzl0ze=1,
as29s=2, MZZa6b=0, maseQ=0. No attempt/job allocation. Database SHA before/after:
`81cf752dcadf9df60156f77e2971aba47420e9fe68fa8903b18c17cbedcf10bd`.
Historical snapshot before/after:
`d01f12761d25232ee22f4cd47834f9fe83efbbb6be97666524f7f6187f5aea85`.
Catalog fingerprint:
`78ca7a1c3048b2c86802981696ca7e196752a661a027d3f11b8b5edece84e049`.
Catalog IDs:
`347f9951-5bbc-4910-b6fd-3a17c74e29d2`,
`53b5a413-7bb5-4f97-9be4-2461794a7d80`,
`78203d6c-16b9-4cae-a66c-a1f7de58275f`,
`86a88de1-62a6-4ad6-9df0-07c2a501f2d0`.
Both image candidates were read. Only exact reference UUID matches strongly;
remote SHA256 remains
`af0ad578968002fd6cdfa864cbf2acbafaf3e8f140d8decbb2990cca7f71012f`.
Account name is not technically verified; existing project-scoped receipt remains.

43 auth/successor cases PASS, including the dynamic Phase-2 delegation gate.
322 full regression cases PASS (60.93s). Compileall src/tools/tests, diff check
and SoT integrity PASS; no production source/canonical policy changes.
Independent review: no material blocker; reviewer reran 42 offline cases before
the final delegation test was added. Character/provider acceptance remains
unverified. Phase 2 is ready under the explicit Owner decision.
