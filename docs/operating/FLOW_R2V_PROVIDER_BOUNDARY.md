# Flow R2V provider boundary — productization (ZCODE-QUAL-001)

Status: OFFLINE / LOCAL PROVEN candidate. **No live generation, upload or any
provider mutation occurred in this work.** The Fresh Shot A state remains
exactly as recorded in [the canonical A reproof](SLICE_0011_CANONICAL_A_REPROOF.md):
`DISPATCH OBSERVED / EXTERNAL EFFECT UNRESOLVED / OWNER_AMBIGUITY_GATE`. This
package does not resolve it and must not trigger a retry.

## What exists now

`src/film_pipeline/flow_r2v_boundary.py` is the reusable Flow reference-to-video
execution boundary. It composes the already-proven pieces — attestation
(`providers/flow_reference_binding.py`), once-only reservation
(`store.reserve_dispatch`), native-UI request qualification
(`providers/flow_canonical_ui.py`), backend catalog ownership
(`providers/flow_rpc_contract.match_r2v_output_v2026_10_01`) and exact
ID/resource/bytes binding (`providers/flow_media.py`) — into one parameterized
lifecycle for any reference-conditioned shot:

1. verified Film reference → mandatory immutable provider-reference attestation
   (`FlowR2VBoundary.verify_reference`; malformed/tampered/wrong-scope evidence
   raises `OwnerAmbiguityGate`, never a crash);
2. durable `ProviderJob` reservation (`reserve_mutation` verifies the attested
   reference first, then consumes the single dispatch budget);
3. provider-native UI input preparation with a parameterized `NativeUiProfile`
   (locale labels, selector text and the wire model string are transport data,
   not code, and never enter Film Core);
4. exactly one authorized mutation (`OneGenerateGuard` releases one exact
   browser-created request; uploads and duplicates are aborted);
5. external effect UNKNOWN until backend proof (observed request, HTTP success,
   DOM/gallery state are transport facts only);
6. reconciliation-only recovery (`mutation_state`/`reconciliation_only`: a
   consumed dispatch is `RECONCILE_ONLY` forever; a missing output never
   re-authorizes a Generate);
7. unique backend output attribution (`attribute_output` over
   `match_r2v_output_v2026_10_01`: pre-dispatch baseline, new provider
   identity, exact marker/reference/model lineage; preexisting outputs, wrong
   references, malformed records, marker collisions and multiple candidates
   fail closed);
8. exact media acquisition (`acquire_bound_media`,
   `normalize_bound_media`: identical duplicate representations of one bound
   resource normalize to one; different resources stay ambiguous; signed URLs
   are transport only and are never persisted).

`MutationIntent` freezes the qualified envelope (project UUID, reference media
UUID, qualified Veo 3.1 R2V model, 8 s / 720p / 16:9 / output count 1,
contract `flow-batchexecute/2026-10-01.1`); anything outside it fails closed.
No hypothesis about provider volatility (why direct RPC writes fail while
native-UI writes may succeed) is encoded anywhere.

## Slice-0011 relationship

`slice0011_canonical_reproof.py` keeps its immutable Owner-grant authority,
historical custody and grant tables unchanged (grant identity is untouched).
Its freeze path now also proves the canonical authority remains expressible as
a generic qualified `MutationIntent`. A future ordinary reference-conditioned
shot needs no component whose semantic purpose is "canonical Shot A reproof".

## Offline proof

`tests/test_flow_r2v_boundary.py` proves, with frozen/synthetic evidence only:
attested reference permits reservation and exactly one mutation opportunity;
wrong/geometric references, wrong media IDs/scope and tampered evidence are
rejected before mutation; re-entry is reconciliation only; request intent
mismatches (reference/project/model/count/creative AST) are rejected; request +
HTTP success without a backend output stays unresolved and unbound; one fresh
backend output is uniquely owned; preexisting outputs and wrong-reference
lineage cannot be claimed; marker collisions and malformed contracts fail
closed; acquisition binds exact ID/project/resource/bytes; identical resource
duplicates normalize and different resources stay ambiguous; historical jobs
stay byte-identical across boundary use; the boundary and UI transport import
no slice components. Existing reference-attestation/reproof tests remain valid.

Regression at delivery: full suite green (380-pass baseline floor held;
new boundary tests added on top). No Film Core, schema or fixture changes.
