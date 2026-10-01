# LIVE-RUNTIME-QUAL-001 — live qualification evidence (2026-10-02)

Status: CLOSED — `OWNER_AMBIGUITY_GATE` (conclusive terminal negative on G1;
no ambiguity crossed by later mutation; no Generate retried).

Package: [LIVE_RUNTIME_QUAL_001_WORK_PACKAGE.md](LIVE_RUNTIME_QUAL_001_WORK_PACKAGE.md)
(frozen, authoritative). Base `aeab4048c04d92520ae4b56c4a8f9cba720c95f5`,
package HEAD `291f305f2b17b486855fd10c98162df78bb4f3a2`, branch
`zcode/live-runtime-qual-001`, dedicated worktree
`D:\AI FILM MAKER\AI-Film-Pipeline-Live-Qual`.

## Terminal summary

One ordinary synthetic reference-conditioned R2V shot
(`LIVE_RUNTIME_QUAL_001_G1_A2`, fixture `flow_canary.json` + the canonical
reference Asset) was frozen by the accepted generic `FlowR2VShotRuntime`,
reserved through `FlowR2VBoundary.reserve_mutation`, and released as exactly
one browser-created, guard-qualified native-UI Generate request. The provider
acknowledged with HTTP 200 and a parsed **null** payload (non-acceptance,
response shape hash identical to the 2026-10-01 null-ack evidence). A bounded
40-minute read-only catalog reconciliation plus a second 40-minute late
read-only reconciliation pass found **zero** marker-bearing records; no
backend output could be attributed. Per the frozen reconciliation policy this
is `EXTERNAL_EFFECT_UNRESOLVED` → `OWNER_AMBIGUITY_GATE`, never retry
authority. G2–G4 were not released (ladder forbids canaries after a
non-PROVEN G1). Generate budget: **authorized 4 / released 1 / remaining 3**
(remaining budget is dead — it is not retry authority).

## L0 BASELINE

- Worktree verified/created from `zcode/live-runtime-qual-001` at package HEAD
  `291f305`; parent `aeab404` is the accepted runtime base.
- Full regression: **489 passed** (accepted floor; re-confirmed **489 passed**
  after the adapter repair below).
- Authority ledger initialized `generate_ledger/L0_INIT.json`: 0/4, with the
  pinned historical custody sha256.
- Canary store: **verbatim byte copy** of the historical Slice-0011
  `runtime.sqlite` (sha256 `08040147…252c17` pinned before copy; copy verified
  equal). Historical source store re-verified byte-identical at every stage
  and at delivery. No historical row was ever written.

## L1 LIVE PREFLIGHT (all read-only; `g1/preflight.json`)

- Session: exact Flow project `f6b40e79-d6f8-4354-80ae-c863260e96f5`,
  qualified browser profile `google_flow_slice0011_manual`, session metadata
  sanitized (at length 42, captcha available, hl `vi`), qualified catalog
  baseline fingerprint `78ca7a1c…8e049` established.
- Catalog observed: 5 ids (347f9951…, 53b5a413…, 78203d6c…, 86a88de1…,
  a47636b8…). The runtime's concrete default-parser catalog path works on the
  live envelope; no read-path repair was needed (`runtime_capture_parser_version`
  `flow-batchexecute/2026-09-20.1`).
- Reference chain re-proven live: `as29s` readback of `53b5a413…` returns the
  exact upload-verified bytes (sha256 `af0ad578…71012f`, 75299 bytes,
  1280x720, `/image/53b5a413…`, 0 redirects), strong content match to the
  immutable source `31ca872d…`, and the canonical reproof attestation
  `refbind_73f8434c…` recomputes byte-exact from retained evidence and the
  copied receipt. `provider_filename` derived from the live row: empty (no
  filename string present; the text-only native AST form is therefore the
  qualified shape and the matcher skips the filename slot).
- Native UI readback: settings tokens exactly the qualified
  `['Video','·','720p','·','8','giây','crop_16_9','x1']`.
- Mutation blocker armed on `**/batchexecute?*` for the whole preflight
  (MZZa6b/maseQ abort); zero blocks observed.

## L2 G1 RELEASE

### Attempt 1 — stranded BEFORE release (local defect, budget intact)

Freeze/reserve completed (`job_d1a9a3b4…`), then the qualified native-UI
prepare gate stopped the run at `UI_PROMPT_READBACK_MISMATCH`: the compact
adapter froze a two-line prompt (`body + '\n' + marker`) that the ProseMirror
editor readback cannot reproduce. No click, no request, no external effect
(journal: `RESERVED`, `MUTATION_INTENT_BOUND` only; ledger has no consumed
entry; 0/4 unchanged). The stranded job is terminal `RECONCILE_ONLY` local
state in the canary store, preserved as evidence
(`g1/attempt-1/live_result.json`).

### RUNTIME-LIVE-FIX-001 (local deterministic repair; offline re-proven)

The adapter serialization was the defect: the UI-qualified serialization is
single-line — exactly the form the canonical A reproof released live on
2026-10-01 (`compiled.text.replace('\n',' ')` in the historical slice tool).
Repair: `compact_r2v_prompt` now freezes `body + ' ' + marker` with no
newline; marker/body bounds unchanged. Two offline assertions updated to pin
the single-line form (`tests/test_flow_r2v_runtime.py`); full suite
**489 passed** after the repair. No live state was touched by the repair; a
fresh shot id (`…_G1_A2`) was frozen for the new attempt because the stranded
job is consumed by design.

### Attempt 2 — one Generate released (`g1/attempt-2/`)

- Fresh session → `qualify_flow_catalog_source` minted with **zero** reads →
  `freeze` performed the ONE authoritative catalog capture (5 baseline ids,
  snapshot identity `6a22d066…`), job `job_1893201b4b850377cdc932a57ab49dc8b67cc1ad0d0e46be00ce887a2b45c99a`.
- Ledger preclaim `G1_A2_PRECLAIM.json` (hypothesis + preconditions + 0→4).
- `reserve_mutation`: attestation re-verified; `RESERVED` +
  `MUTATION_INTENT_BOUND` (model `veo_3_1_r2v_lite`, attestation
  `refbind_73f8434c…`, prompt sha `4878aac0…`).
- Post-freeze catalog read: baseline unchanged; `prepare_inputs` added the
  reference chip, verified settings, filled and re-read the prompt exactly.
- One-request guard armed (`CLICK_ARMED`, `PROMPT_VERIFIED`); exactly one
  Generate click; exactly one browser MZZa6b request observed, validated by
  the guard against the frozen project/reference/prompt/model/count and
  released (`GENERATE_REQUEST_OBSERVED`, request hash `746db93a…`, body sha
  `3fe0ac19…`, contract `native-ui-r2v-canonical-20261001-v1`).
- `G1_A2_CONSUMED.json` written durably BEFORE any reconciliation.
- Wire response: HTTP 200, 229 bytes, parsed payload null
  (`PROVIDER_RESPONSE_OBSERVED`; type_counts all-null ⇒ non-acceptance; no
  `PROVIDER_ACCEPTANCE_OBSERVED` was recordable).
- Direct `MZZa6b` submits by our transport: **0**. Uploads: **0**. Retries:
  **0**. Duplicate browser requests post-release: 0 (no guard blocks).

## L3 G1 RECONCILIATION

- Bounded window 2400 s, catalog polls every 60 s through the qualified read
  path: **zero candidates** (no record containing the correlation marker; not
  even a non-CAE pending record). Zero catalog read failures.
- Durable stop: `AMBIGUOUS_EVIDENCE` fact; job status `INCONCLUSIVE`,
  `dispatch_count=1`; gate `EXTERNAL_EFFECT_UNRESOLVED` → `OWNER_AMBIGUITY_GATE`.
- Late read-only reconciliation pass (second full 2400 s window, ~1 h after
  release): 37 polls, again zero candidates
  (`g1/attempt-2/reconcile_result.json`).
- Final catalog-delta observation (`g1/attempt-2/late_catalog_delta.json`):
  one read-only catalog read — the project contains **exactly the five
  pre-dispatch baseline ids**; no record of any kind (marker-bearing or
  marker-less) appeared. The released Generate produced no observable backend
  record at all.
- Restart/recovery proofs (`g1/attempt-2/recovery_proofs.json`): a fresh
  runtime resumes the identical frozen job with **zero** provider reads;
  `recovery_decision` = INCONCLUSIVE / RECONCILE_ONLY / may_submit **false**;
  re-reservation is rejected with `MUTATION_ALREADY_CONSUMED_RECONCILE_ONLY`.
- Acquisition/Asset/QC: **not reached — nothing was owned**; no Asset is
  claimed (honest non-claim).

## L4 OPTIONAL CANARIES

Not executed. The ladder permits G2–G4 only when G1 is fully PROVEN or
conclusively terminal **without ambiguity**; G1 ended
`EXTERNAL_EFFECT_UNRESOLVED` (ambiguous external effect), so the remaining
budget is frozen at 3 and no further mutation is permitted under this package.

## L5 ADVERSARIAL REVIEW (no mutation)

- Budget accounting: ledger files (`L0_INIT`, `G1_A1_PRECLAIM`,
  `G1_A2_PRECLAIM`, `G1_A2_CONSUMED`) are write-once; exactly one consumed
  entry exists; attempt-1's preclaim has no consumed counterpart and its
  journal has no `GENERATE_REQUEST_OBSERVED` (pre-release stop re-verified
  from the journal, not from the report alone).
- Attribution: the guard records `GENERATE_REQUEST_OBSERVED` only after
  in-request validation of project/reference/frozen-prompt/model/count, so
  the released request is exactly the frozen intent; the recorded hashes
  (request/body) are tamper-evident. The null-ack response shape hash equals
  the 2026-10-01 historical null-ack evidence — the server response is
  recognizable, and it is not acceptance.
- Live-claim audit: every positive claim above maps to a durable journal fact
  or write-once evidence file; UI/DOM/ordering was never used as ownership
  authority. The only negative-space claim ("no output") is bounded by the
  two observation windows and the qualified marker-keyed contract.
- Custody: source repo HEAD `d8d4b0a` with the identical untracked set as
  session start; historical store byte-identical (sha256 re-verified at
  delivery); browser profile used in place from its original location, never
  copied into the repository.
- Local tool defects found and fixed during the run (none affected provider
  state): missing `REFERENCE_FILENAME` constant, `verify_settings` page
  argument, attempt-scoped evidence layout, reconcile attempt resolution from
  the preclaim entry, `_NullGuard` for read-only reconciliation.
- Residual non-claims: (1) whether the provider silently rejected the
  generation, queued it beyond the windows, or failed asynchronously is
  **UNKNOWN** — the empty catalog delta rules out "an output exists without
  its marker in this project's catalog" for the observed windows, but cannot
  distinguish silent server-side rejection from delayed/hidden processing;
  (2) a compromised same-shape byte-substituting provider read remains
  indistinguishable (inherited qualified-contract residual); (3) account
  identity remains Owner-attested only (project-scoped), unchanged from the
  accepted base.

## L6 DELIVERY

- Full regression after all repairs: **489 passed**; `compileall -q src tools`
  clean; `git diff --check` clean; tracked-delta security scan: no
  cookies/tokens/credentials/signed URLs/profile or cache material (evidence
  directories are gitignored by `projects/*`).
- Delivery HEAD: recorded in the final handoff report (commit containing the
  adapter repair, test pinning, the G1 tool and this document).
- Provider totals for the whole run: reads = preflight (2 metadata-grouped,
  3 catalog, 1 reference image), release (1 capture + 1 prepare read + ~39
  reconcile polls), late reconciliation (~37 polls + 1 final delta read),
  acquisition media reads 0 (nothing owned); writes = exactly 1 native-UI
  Generate release. Uploads 0. Project/account/provider switches 0.

## Recommendation for next production step

The generic runtime is proven through release + durable authority accounting
+ fail-closed recovery, but the live provider has now returned zero
attributable outputs for **five** released generates on this project across
two days (3 historical + G1, with two independent observation windows on G1).
This is a provider-side acceptance/attribution unknown, not a runtime defect.
Next steps require an Owner decision, not more Generate budget:

1. Owner performs one manual UI generation in the exact qualified project and
   reports whether a tile appears at all (isolates "provider rejects this
   project/account" from "backend strips correlation markers").
2. If tiles appear, a read-only capture of that record's shape will show
   whether the prompt/marker survives to `row[5][1]`/lineage — resolving the
   attribution-contract question without any new Generate.
3. Only after that resolution is a further bounded live canary meaningful.
