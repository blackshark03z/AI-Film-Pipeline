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
unverified. Phase 2 proceeded under the explicit Owner decision.

## Phase 2 final result — OWNER_AMBIGUITY_GATE

Implementation revision: `152444dfc6892633c67c545692302f06f51cbf93`.
Execution preflight repeated all five read-only checks successfully before
allocation (another Zzl0ze=1/as29s=2, no generation/upload). A new fresh baseline
contained the same four IDs listed above; it was revalidated before reservation.

New successor attempt:
`attempt_9723d6dd168ac7fe47baf03ad5fd33ef8f9e0c21cf6f8bcc83cfa002a46822aa`.
New ProviderJob:
`job_4d11911518710248299682693a3fdb48ec1426ffc0a6ab6d45de615596060d40`.
Original authority has exactly one allocation and one consumption. The new job
has dispatch_count=1, INCONCLUSIVE, no external output/binding. The exact prompt
below was frozen and sent once: **430 body characters / 70 words**, three sentences,
one final full job marker. Reference/project/model are unchanged from Owner scope:
`53b5a413-7bb5-4f97-9be4-2461794a7d80` /
`f6b40e79-d6f8-4354-80ae-c863260e96f5` / `abra_r2v_8s`, 8s, 16:9.

```text
8-second locked eye-level medium close-up, 16:9. Use the exact image reference: one illustrated adult woman with teal bob hair, crimson round glasses, a mustard jacket over a blue shirt, silver triangle earrings and a beauty mark below her right eye; facing slightly right, she breathes gently and blinks once in a daytime living room, window left, sofa and plant right. Keep her face and outfit stable; movements subtle and calm.
[FILM-job_4d11911518710248299682693a3fdb48ec1426ffc0a6ab6d45de615596060d40]
```

One armed request, one MZZa6b response diagnostic and HTTP200 observation are
durable. Sanitized diagnostic: parsed=true, UTF-8 bytes=228, type counts null=1
and bool/dict/float/int/list/str=0, advisory_only=true. Response shape hash:
`f072cbec3bf8841871d4284230c5e983dc211a56837aed862487148f947d1a1f`.
Request hash:
`0144fdec7c100466800650379420e9150e4e8b75ac4b80387174f0eed0a56ea4`.
These observations do not prove provider admission, generation failure, or
compact-prompt failure. No raw response/request secrets were persisted.

Last visible poll: no owned output, 568 seconds remaining. The execution tool's
process session subsequently disappeared; local process inventory found no
Python runner and no completion report. The cause is unknown. Completion of the
600-second polling bound is NOT established. Exact final catalog-poll count is
unavailable. This is post-submit observation/recovery ambiguity: STOP, no restart,
no new Flow query, no retry. Appended AMBIGUOUS_EVIDENCE only to the new job,
diagnostic `successor_observation_process_lost`, then wrote the local stop report.

Exact output identity: none bound. Acquired Asset/SHA: none. Live technical QC,
character review packet: not run/created. SelectedTake=0. Provider acceptance and
remote outcome remain UNKNOWN. No compact-prompt live success or failure claimed.
Shot B=0; new reference uploads=0; Dola/Seedance=0; no provider calls after this gate.

Historical A snapshot is unchanged at the hash above. Original A remains
INCONCLUSIVE, dispatch_count=1, null output, with its five original facts and
ambiguity intact. Prior zero-RPC auth stop retains its exact file hash. Reference
receipt/events remain unchanged: one historical reservation, four events.
Qualification DB retains SHA256
`6054581a1d2fd9824b3a8691f964a11d42b7e9781691612304b7c53869232adf`.
Canonical A PromptPlan retains
`cbc6cabae3fe2132c6ba6c3b49d78e9994ff3b670549f1980eff82e0cc9da324`.
Final counts: 2 attempts, 2 jobs, 11 dispatch facts (5 historical + 6 successor),
0 bindings, 1 reference Asset, 0 QC reports, 0 SelectedTakes, 0 B attempts.

Evidence: read_only_preflight.json, execution_preflight.json and
continuation_result.json under auth_restoration_v1; frozen_intent.json,
historical_before.json, historical_after.json and live_result.json under the
fixed successor output directory. The original consumed-grant and wrapper proof
guards prohibit further execution. Continue only under a new explicit Owner
ambiguity procedure; never infer a second submit from missing output.
