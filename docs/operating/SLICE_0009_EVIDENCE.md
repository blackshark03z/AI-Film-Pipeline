# SLICE-0009 producer compatibility evidence

## Boundary and progression

- Accepted source: `bdaac47501c9822a6b8037817ec1803358a7873d`, SLICE-0008 PROVEN. Current work package persisted byte-for-byte as `CURRENT_SLICE.md`; prior package preserved in `SLICE_0008_WORK_PACKAGE.md`.
- Boundary/version/path/authority decisions recorded before code in `docs/integration/AUTOEDIT_COMPATIBILITY_BASELINE_v0.md`. Film is an optional upstream producer with no privilege. AutoEdit owns its own editorial/post-production kernel and persistence. The shared boundary owns representations, IDs, media links, constraints and versioning only.
- Reused the existing `EditorialStore.read_manifest`, passing-QC SelectedTake resolver, runtime lineage checks, SHA-256 helpers, canonical JSON and jsonschema dependency. No new persistence or consumer backend.
- Schema, thin exporter, golden package and generic/error fixtures complete. Focused contract tests: 23 passed. Full regression after final correction: 153 passed.
- No AI generation, AutoEdit implementation, shared database, bridge/service/queue or NLE action. Frozen Film/development SoT and root domain schemas unchanged.

## Real golden producer package

Fresh source reads resolve the exact Slice8 `edit_52750848b473f76fd6e14f4007fa30b73a25082017e2d0fa191efcb44526ecc5` manifest. Its sole clip resolves to `FLOW_CANARY_001`, SelectedTake `take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b`, final passing QCReport `qcr_058bc4ede5bb77c9b0683c5788d76ad18c424a340328a4ce8d53382401c25904`, Asset `asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01`, and GenerationAttempt `attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5`.

- Golden fixture: `fixtures/integration/autoedit_v0/one_selected_take_with_timeline_hint/edit_job.json` plus `checksums.json`.
- Envelope/version: `EditJobInputV0`, `0.1.0`. Required fields contain no Film concept: `contract_version`, `job_id`, `media`.
- Job ID: `editjob_1c862d64987bcccbc0407392ece4579817aad8d31d43960ae43b6b24934dce81`.
- Package ID: `editpkg_2960e7aa596cd23c8f66d7999f177e36d087c4f38167c3c25cdf2c2d7d76bd28`.
- Exact envelope file SHA-256: `833865744bb4a63444decb93e379306605ff820aea31ac71be51f5e473af9093`.
- Source media SHA-256 retained: `c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf`.
- Source video is referenced, not copied: explicit root ID `film_workspace` + relative POSIX locator `projects/flow_canary/outputs/95d299c70b8a5a37ec1e1fed.mp4`. Machine root, SQLite path and source absolute path are excluded from input/job/package identity.
- EditManifest is an optional suggested timeline; Film provenance and ShotSpec-derived metadata are optional enrichments. Frozen constraints are empty. No Film-supplied trim/order/camera/continuity value is automatically promoted to frozen authority.
- The source runtime DB SHA-256 was `262a28df5360c13ec875e86af05c194439e6a73fdcc08df7cb708fd076a9c034` before and after export. A second export into ignored `projects/flow_canary/slice0009/edit_job` returned identical identities and envelope bytes. Fresh package readback checked schema, package/file checksum, explicit root resolution and source bytes.

## Generic compatibility and failure proof

Five generic valid fixtures cover minimal media without timeline, multiple media, transcript enrichment, explicit frozen constraint and optional Film metadata. Three malformed fixtures cover missing media, unsupported version and a well-formed but byte-mismatching hash. The hash-mismatch fixture passes structural validation deliberately; actual source verification rejects it. A standalone process validates all six valid fixtures with only JSON/jsonschema and actively forbids Film imports. It has no Film SQLite or domain class dependency. Removing all Film enrichment from the golden fixture remains structurally valid.

Two independent fake/local Film runtimes at different machine roots yield byte-identical exported envelopes/checksums and IDs. Other checks prove exact Asset hash/SelectedTake provenance retention, idempotent no-overwrite export, checksum tamper rejection, malformed portable locator rejection, duplicate/unknown media references, explicit suggestion versus frozen distinction, unknown structural field rejection and preservation/identity sensitivity of namespaced optional extensions. Generic PPM/WAV fixture media are deterministic local bytes; no provider call generated them.

The future checklist requires AutoEdit ingest V1 to consume frozen Film fixtures plus at least one non-Film fixture. This slice does not claim future consumer ingest, frozen-constraint enforcement or final render acceptance. EditIR, MediaIndex, backend/planner/critic/repair/NLE contracts and generic reverse MediaRequest remain unfrozen.

## Independent review

Reviewer found a material parsing ambiguity: repeated JSON keys could conceal an earlier frozen requirement using last-value-wins parsing even with matching checksums. The package reader now rejects duplicate keys recursively in both envelope and checksums, and rejects non-finite JSON constants. Two negative package cases cover hidden frozen authority and nested repeated media checksums. The reviewer independently reran all 23 focused tests and read/verified the real golden package against the explicit workspace root. It retained suggestion authority, zero frozen constraints, exact package/job/media identities and unchanged source DB SHA-256. Final review found no remaining material finding; the final full suite then passed 153 tests.
