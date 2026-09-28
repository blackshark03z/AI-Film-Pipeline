# AutoEdit compatibility baseline v0

Status: experimental integration truth, version `0.1.0`, bounded by SLICE-0009. This document supplements operating/integration truth; it does not replace or rewrite either system's SoT. Decisions recorded before producer implementation.

## Relationship and ownership

AI-Film-Pipeline is one optional upstream producer for AutoEdit, with no architectural privilege. AutoEdit must also admit raw footage, podcast/interview, screen recordings, gameplay, existing timeline/projects, stock media, AI media and future producers.

| Owner | Responsibility |
| --- | --- |
| Film | Story, Scene, WorldState, ShotSpec, PromptPlan, RoutingDecision, GenerationAttempt, ProviderJob, Asset provenance, QCReport, RepairDecision, SelectedTake |
| AutoEdit | MediaIndex, EditIR, editorial planning, clip selection within allowed inputs, trims, timing, tracks, audio, graphics, VFX, color, preview, edit critique/repair, final post-production execution |
| Integration | Cross-system representations, contract versions, portable IDs, media references, explicit constraints and provenance links |

Each system retains its own persistence. No shared database. Film exports data; a future consumer need not import Film Python modules, SQLite schemas or Film domain classes. Film's existing local rough-cut path remains valid. This slice adds no AutoEdit kernel, backend or NLE adapter.

## Generic envelope

`EditJobInputV0`, exact supported compatibility version `0.1.0`. The standalone JSON Schema is `edit_job_input_v0.schema.json` beside this document. Only structural envelope fields are fixed; this is not the future EditIR.

Required fields: `contract_version`, `job_id`, nonempty `media`. The minimal producer's semantic content is media alone; version and job ID are portable headers. Job IDs are producer-assigned opaque nonempty strings. The Film exporter derives its job ID from canonical input content. Other producers do not need Film's ID algorithm.

| Field | Meaning |
| --- | --- |
| `media[]` | Required generic inputs; each has `media_id`, `media_type`, `locator`, `storage`; duration and SHA-256 may be supplied when known |
| `user_intent` | Optional general editing intent; absent means unspecified, not inferred Film intent |
| `optional_timeline_hint` | Optional `{authority: suggestion, source_format, data}`; internal data is opaque producer enrichment |
| `optional_transcripts`, `optional_subtitles` | Optional objects/arrays; no transcript/subtitle IR is frozen here |
| `optional_semantic_metadata`, `optional_provenance`, `optional_references` | Optional enrichment objects/arrays, never eligibility requirements for a generic producer |
| `optional_constraints` | Suggested requirements only |
| `frozen_constraints` | Explicit requirements the consumer must preserve or refuse as unsupported; absent/empty means none |
| `extensions` | Optional namespaced objects for additive v0 experimentation |

Unknown top-level, media, locator, timeline wrapper and constraint fields are rejected for this exact v0 version. Unknown content inside optional enrichment or namespaced `extensions` is accepted and preserved, never interpreted as authority. A future version needs explicit negotiation and new fixtures; no `latest` or `1.0.0` claim.

## Portable media and package identity

Media types are generic `video`, `audio`, `image`, or `timeline`. A locator is either `package_relative` (embedded bytes inside the package) or `root_relative` (referenced bytes under an explicitly configured root ID). Paths use relative POSIX components without traversal, backslashes, drive letters or URL credentials. Root bindings are local transport configuration outside the envelope and identity. Resolution must remain inside the selected root, including symlink resolution. The resolver does not guess roots or dereference arbitrary web URLs.

Known local immutable bytes carry a lowercase SHA-256. A structurally valid digest is not proof of matching bytes: producer package verification must resolve the explicit root and compare bytes. Unavailable references remain unverified. Embedded media must be present in the package; referenced media need not be copied.

Initial filesystem package: `edit_job.json` + `checksums.json`, with optional embedded `media/` files. This Film exporter uses referenced media and copies no MP4. Optional enrichment is inline for v0; a future transport may move it into sidecars without granting editorial authority.

Canonical JSON: UTF-8, sorted object keys, no insignificant whitespace, list order retained, non-finite numbers rejected. Reading envelope/checksum JSON must reject duplicate keys recursively; last-value-wins parsing can hide frozen authority and is not compatible. Package ID hashes the complete envelope, including suggestions, constraints and opaque extensions; SHA-256 fields bind available source bytes. File checksum hashes exact `edit_job.json` bytes separately. Absolute runtime source paths, DB locations, root bindings and export directory are never exported or hashed. Identical Film state with identical portable locators yields the same job/package IDs; changing locator or input intent changes package identity. This is input identity, not a promise of byte-identical rendered output.

## Film mapping and editorial authority

Film `EditManifestV1` stays unchanged and valid as producer-side editorial intent, suggested assembly and handoff. It is not AutoEdit EditIR or mandatory final editorial authority. The exporter freshly resolves the persisted manifest through SelectedTake, final passing QCReport, Asset/hash and GenerationAttempt/ShotSpec lineage before export.

| Film data | Envelope destination |
| --- | --- |
| Approved Asset bytes/hash/duration | Generic media entry; hash-based portable media ID |
| EditManifest | `optional_timeline_hint`, `source_format=EditManifestV1`, `authority=suggestion` |
| Asset/SelectedTake/QC/attempt/manifest IDs | `optional_provenance.film`; portable links, no DB access requirement |
| Shot/scene IDs, camera, continuity, dramatic purpose | `optional_semantic_metadata.film`; advisory enrichment |
| Producer user intent | `user_intent`; editorial request, not frozen constraint |

AutoEdit may change trim, order, pacing, transitions, sound, graphics and VFX unless a requirement is explicitly present in `frozen_constraints`. No value becomes frozen merely because Film supplied it. Constraint entries minimally contain a portable `constraint_id`, a nonempty `requirement`, and optional media-ID scope. Examples such as preserving a selected take, dialogue, order, duration range, aspect ratio or character framing do not establish a large taxonomy. AutoEdit must not claim compliance with an unsupported frozen requirement; enforcement/planner details belong to its research. The real golden fixture freezes no editorial constraint.

## Transport independence and drift prevention

Contract is not transport. Filesystem export is sufficient now. CLI piping, HTTP, MCP, object storage or queues may later carry the same semantic envelope; none is implemented here. No service, bridge, queue or distributed orchestration.

The fixture index in `fixtures/integration/autoedit_v0/README.md` and `AUTOEDIT_BOOTSTRAP_CHECKLIST_v0.md` are the future bootstrap gate. AutoEdit cannot declare ingest V1 PROVEN until it consumes the frozen Film producer fixtures **and at least one non-Film generic fixture**, using no Film implementation dependency. Structural acceptance, reference/hash verification and frozen-constraint support must be reported separately.

## Unfrozen areas, questions and non-goals

Exact EditIR, MediaIndex, AutoEdit persistence, backend capability contracts, editor-planner/critic/repair protocols, NLE adapters, OTIO mapping and Premiere/AE/Resolve implementation remain open. A future generic reverse `MediaRequest` may request replacement/additional media; its schema, transport and Film mapping to PickupRequest/ShotSpec/generation are not frozen or implemented.

AutoEdit research must decide timeline/transcript normalization, machine-checkable constraint predicates, backend support, critique/repair protocols and reverse media requests. This baseline creates no EditorBrain, ModelGateway, MediaIndex, EditIR, critic, repair loop, NLE integration, generation, or final master.
