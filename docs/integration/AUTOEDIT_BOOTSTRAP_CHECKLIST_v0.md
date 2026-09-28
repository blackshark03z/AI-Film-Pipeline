# AutoEdit bootstrap compatibility checklist

Copy/reuse this gate in AutoEdit's own architecture/prototype work. Baseline: `EditJobInputV0` compatibility version `0.1.0`; fixtures in `fixtures/integration/autoedit_v0/`.

- Load the standalone schema/JSON, with no imports from Film Python modules, no Film SQLite access and no required ShotSpec/QCReport/SelectedTake class.
- Consume every valid frozen fixture, including the real Film golden package and the minimal non-Film `one_media_no_timeline` fixture.
- Report structural validation separately from media availability and actual SHA-256 verification. Reject mismatching known bytes.
- Reject missing media, unsupported versions, malformed locators and identity/reference conflicts.
- Reject duplicate JSON keys recursively before interpreting constraints or checksums.
- Preserve supported opaque enrichment/extensions; reject unknown structural fields under the agreed v0 rule.
- Treat timeline/metadata/optional constraints as suggestions. Preserve each explicit frozen requirement or refuse as unsupported; never silently ignore it.
- Accept a package after Film enrichment is removed. Keep root bindings and machine paths outside canonical input identity.
- Preserve separate system persistence and transport-independent contract semantics.
- Research AutoEdit's own EditIR/MediaIndex/backend/planner/critic/repair/NLE/reverse-request contracts before freezing them.

**Required future acceptance rule:** AutoEdit cannot declare ingest V1 PROVEN until the frozen Film producer fixtures and at least one non-Film generic fixture are consumed with media/hash and constraint limits honestly reported. SLICE-0009 proves the producer baseline only; it does not prove a future consumer.
