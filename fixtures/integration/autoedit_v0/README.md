# EditJobInputV0 producer fixtures (0.1.0)

These frozen producer fixtures are inputs for future AutoEdit research, not an AutoEdit implementation or ingest acceptance claim. Generic fixtures require only portable headers and media; they need no Film domain classes.

| Fixture | Expected proof |
| --- | --- |
| `one_media_no_timeline.json` | Minimal non-Film image, no intent/timeline/Film fields |
| `one_selected_take_with_timeline_hint/edit_job.json` | Golden real Film input read from the approved Slice8 SQLite state, optional suggested manifest and provenance |
| `multi_media.json` | Two generic image/audio entries |
| `with_transcript.json` | Generic audio with optional transcript enrichment; no speech asserted by the synthetic tone |
| `with_frozen_constraint.json` | Explicit requirement with media scope, separate from suggestions |
| `with_optional_film_metadata.json` | Optional Film metadata on a generic input; removing it remains valid |
| `malformed_missing_media.json` | Structural reject |
| `malformed_bad_version.json` | Unsupported-version reject |
| `malformed_hash_mismatch.json` | Structurally valid hash; resolved byte verification must reject |

`media/color.ppm` and `media/tone.wav` are tiny deterministic local fixtures, not AI generation. Generic locators resolve from this fixture directory. The real Film package **references** `projects/flow_canary/outputs/95d299c70b8a5a37ec1e1fed.mp4` via explicit root ID `film_workspace`. Bind that ID to the Film workspace (or a relocated root with the same layout); never guess it. The MP4 is local/ignored and not embedded in Git. A consumer without it can validate structure and package checksum but must report source bytes unavailable/unverified, not ingest PROVEN.

The golden package's `checksums.json` binds exact UTF-8 envelope bytes, package identity and expected media SHA-256. Golden JSON files and local media fixtures are marked binary in `.gitattributes` to preserve exact bytes. No absolute machine path, DB location, cookie, token or signed URL is packaged. Full Film state remains private to its own persistence; provenance identifiers are links, not a shared-database requirement.

Schema and future gate: `docs/integration/edit_job_input_v0.schema.json`, `AUTOEDIT_COMPATIBILITY_BASELINE_v0.md`, `AUTOEDIT_BOOTSTRAP_CHECKLIST_v0.md`.
