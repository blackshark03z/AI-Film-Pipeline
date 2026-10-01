# Slice 0011 current handoff — reference ambiguity resolved, 2026-10-01

**Current result: B. REFERENCE_BINDING_PROVEN_CONTENT_MISMATCH.**
**Proof state: PROVEN for the observed ID → resource → served bytes chain.**
Stop at the Owner content-mismatch gate. Generate=0, upload=0, retries=0.
Shot B remains ungenerated; no reference was replaced or rebound.

**OBSERVED:** read-only `as29s(["347f9951-5bbc-4910-b6fd-3a17c74e29d2"])`
returns a record echoing that exact ID and the fixed project. Its two identical
image URL slots point to `/image/347f9951-5bbc-4910-b6fd-3a17c74e29d2`.
Zero-redirect GET returns 54,082 JPEG bytes, 1280x720, SHA256
`93fa8edf3093a62f6053b5ae95352d7355d803329b00cb55f336c559216d8c89`.
The catalog, response, headers, decoded dimensions, and historical qualification
receipt agree. That hash **is attributable to 347f…** for the observed resource.

**OBSERVED:** those bytes show the geometric transport-test fixture and strongly
match its local source `dc766e136c039ce4ae25f78dc7555c161a6178e8c835cf3d37600b4d7d0e8b0e`.
They fail the canonical character comparison. Existing control `53b5…` strongly
matches canonical source `31ca872d…` and agrees with its production recovery
receipt. Two successful reads of each image and approved Shot A were stable;
two additional no-cache image controls returned the same hashes. Origin cache
freshness remains **UNKNOWN**; no origin-contact claim is made.

**DISPROVEN for these captures:** a wrong nested URL caused the mismatch.
**INFERRED:** the earlier qualification/continuation facts conflated the geometric
canary ID with the canonical character Asset. The precise historical selection
step remains **UNKNOWN**. Shot A's backend lineage names `347f…`; its Owner
visual approval stands, while the claim of canonical character-reference input
is disproven. No new Shot A review is requested.

**Proposed minimum future delta:** enforce echoed ID/project/kind and exact
resource-path binding, then content verification against the immutable source.
The current parser lacks those explicit guards, but selected the correct
resource in this investigation. No production fix, reference substitution,
runtime ledger edit, or Shot B resumption was performed or authorized here.

The complete findings, redacted structure, all response UUIDs, control results,
cache limitations, historical custody, root-cause classification, and validation
are in [the reference-binding resolution](SLICE_0011_REFERENCE_BINDING_RESOLUTION.md).
Sanitized captured evidence and exact bytes are preserved under
`projects/character_continuity/reference_binding_20261001/`.
The offline verifier passed 6 observations, 2 cache controls, and 13 negative
controls. Production source is unchanged from the blocked attempt.

## Historical blocked-attempt handoff (superseded identity uncertainty)

The following section preserves the earlier stop evidence. Its INCONCLUSIVE
reference-identity assessment is superseded by result B above; its unexecuted
production milestones remain incomplete.

Task: `task-756ef7bd024b4c70adb8f8aaa97b4aad`.
Final state: **OWNER_AMBIGUITY_GATE**. Overall proof: **INCONCLUSIVE**.
Production implementation is incomplete; this is not a completed candidate.

## Source identity

Branch: `codex/slice-0011-reference-i2v-continuity`.
Base and delivery HEAD: `6b018fcb71f97f35458700ba671de69bfe663d52`.
No new commit was made. The inherited working tree remains dirty.
The successful read-only preflight used uncommitted source, bound by the source
manifest in `SLICE_0011_UI_MUTATION_GATE_EVIDENCE.json`:
`03e156f135125770a410ae102dcb99590bdfab7de619abcfc05362dc62da9950`.
The exercised session file SHA256 is
`fcb5d5cc9ffe7379a69582b13e2df5c7f3628dbd7ac19c6d3154d8c0f6abcbd8`.

## Blocking observation and exact evidence

Read-only `Zzl0ze` on project `f6b40e79-d6f8-4354-80ae-c863260e96f5`
returned these five identities:

- `347f9951-5bbc-4910-b6fd-3a17c74e29d2`
- `53b5a413-7bb5-4f97-9be4-2461794a7d80`
- `78203d6c-16b9-4cae-a66c-a1f7de58275f`
- `86a88de1-62a6-4ad6-9df0-07c2a501f2d0`
- approved Shot A `a47636b8-f7fb-4d99-8100-4cb5d989da8d`

Existing `as29s` acquisition was asked for reference media ID
`347f9951-5bbc-4910-b6fd-3a17c74e29d2`. Returned bytes failed the existing
`reference-rgb-dhash256-v2-flow-cdn-20260930` comparison against the immutable
reference asset `asset_70834935ccb760367645411d115c0c24243f4dd921182ef4b9502cad382062ff`:

| Observation | Result |
| --- | --- |
| Source SHA256 | `31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531` |
| Returned image SHA256 | `93fa8edf3093a62f6053b5ae95352d7355d803329b00cb55f336c559216d8c89` |
| Source / returned dimensions | 1280x720 / 1280x720 |
| Strong content match | false |
| Maximum channel MAE | 118.42483940972222 |
| Maximum channel RMS | 138.69036280906872 |
| Large-difference fraction | 0.9888335503472222 |
| Maximum tile MAE | 193.14013671875 |
| dHash distance | 123/256 |

This disproves this returned image's content match, but leaves exact provider
reference identity **INCONCLUSIVE**. Source inspection shows that the existing
media resolver constrains host and media kind, without independently validating
the requested media ID in the returned URL path. The observation therefore does
not establish that the backend changed the intended reference. No causal
explanation is asserted. No further provider reads or mutations followed this
failed comparison. Raw authenticated responses and transient URLs are excluded
from this handoff. Returned binary bytes were not retained by the preflight.

The restored cookie session required normal authentication. The existing
qualification Chrome profile reached the exact project using ordinary Chrome
without stealth/fingerprint flags. Google account identity remains unverified;
project access does not prove account identity. No account switch is claimed.

## Changed files and inherited classification

New continuation work:

- `src/film_pipeline/providers/flow_reference_rpc.py`: explicit native Chrome
  and existing-profile session support; removed inherited hard-coded User-Agent.
  Existing cookie source remains supported. This is partial session work, not a
  production single-dispatch adapter.
- `docs/operating/SLICE_0011_UI_MUTATION_STATUS.md`: durable boundary, milestones,
  observed gate, and remaining work.
- `docs/operating/SLICE_0011_UI_MUTATION_GATE_EVIDENCE.json`: sanitized comparison,
  mutation counters, exact source manifest, and validation results.
- This handoff.

Inherited, preserved, and not accepted wholesale: model-parameter delta in
`flow_r2v_prompt.py`; current catalog parser/matcher and direct builder in
`flow_rpc_contract.py`; current-version catalog support in
`flow_reference_rpc.py`; current-contract tests, forensic reports/scripts,
`chrome_profile/`, `scratch/`, and `uv.lock`. Direct mutation remains unqualified.
No profile/cache, credentials, raw dump, screenshot, or forensic script was
promoted into a commit. No blanket staging occurred.

## Reuse and implementation status

Reused for live read-only evidence: `FlowReferenceRpcSession`, current catalog
parser, `as29s` media acquisition, and existing source/image comparison.
Discovery identified reusable SQLite reservation/journal, compact prompt
compiler, immutable acquisition/EOF decode, Film QC/SelectedTake, editorial,
and Slice-0009 producer export. The older DOM/gallery transport cannot be reused
unchanged as output truth. UI single-dispatch productization, stronger matching,
and new state-machine qualification remain unimplemented because the identity
gate was reached first. No canonical schemas or Film/AutoEdit semantics changed.

## Validation

- Initial system Python: collection failed because project dependencies and
  package were unavailable; switched to the existing project environment.
- `.venv/Scripts/python.exe -m pytest -q`: baseline **343 passed in 80.53s**.
- `.venv/Scripts/python.exe -m compileall -q src tools`: exit **0**.
- `.venv/Scripts/python.exe -m pytest -q`: final **343 passed in 69.03s**.
- `git diff --check`: exit **0**.

The complete suite includes existing current-contract and dispatch-recovery
tests. No new mutation-boundary tests were added or claimed. Existing tests do
not qualify an unfinished native mutation implementation. No post-Shot-B suite
exists because Shot B was not dispatched.

## Live Shot B receipt and downstream state

Project: `f6b40e79-d6f8-4354-80ae-c863260e96f5`.
Canonical fixture: `fixtures/character_continuity_shot_b.json`, unchanged.
Generate actions **0**; retries **0**; reference uploads **0**.
This continuation created no Shot B job, marker, or dispatch reservation and
recorded no generation-wire receipt. Existing Shot B ledger state was not
further audited after the reference identity gate.
There is no claim about globally exactly-once provider execution.

Shot B backend attribution, output ID, local Asset/SHA256, duration/resolution,
full decode, character QC, and SelectedTake: **not reached**.
No reference/A/B contact sheet was created because no B media exists.
Shot A approval remains accepted without another review request; no new Shot A
selection record was created in this continuation.
Two-shot EditManifest/rough cut: **not reached**.
AutoEdit producer package: **not reached**; AutoEdit itself was untouched.

## Required Owner resolution

Resolve the existing approved reference identity/readback conflict using the
Owner ambiguity process before resuming any Shot B generation. Do not choose
another reference, re-upload, switch project/account, change correlation, or
generate under this stop record. This continuation's generation grant is unused,
but that budget does not override the identity gate. A future continuation must
first re-ground evidence and qualify the production mutation boundary.


## 2026-10-01 canonical-reference reproof superseding update

See [canonical A reproof](SLICE_0011_CANONICAL_A_REPROOF.md). The production
receipt already named `53b5…`; new immutable ID/resource/bytes/content proof
and fail-closed UI/grant guards are implemented. Historical `347f…` canary
remains UI mutation evidence only, never canonical-conditioning proof.
Fresh A: one Generate click, one request, zero retry/upload/B. Backend output
identity was not proven within the bounded reconciliation window. Final state
`OWNER_AMBIGUITY_GATE`; no fresh output or continuity QC accepted. Stop.
