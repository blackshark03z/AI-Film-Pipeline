# SLICE-0004 Flow VIDEO network media diagnostic

Reference: Story Auto@5464cbb1d1c11a550b5e096647b9f94587de5bfe response_model.py, live.py, video_identity.py and video_acquisition.py. Existing exact response tuple -> thumbnail token -> unique rendered tile -> official 720p Download mechanics were reused. No undocumented UUID component is called a provider job ID.

## Diagnostic outcome

IDENTITY_TO_OFFICIAL_DOWNLOAD_PROVEN. Bound canary project was empty. Existing authenticated home project links were visited read-only until a video identity could be resolved. Target was selected by explicit response tuple and resolved to exactly one tile, never by gallery ordering. Passive observation was attached before navigation/download. Two normal official Download results for that exact target had SHA-256 d4e96008a94c3c0b7cf163ef809fa3a4522855a54215a187762bce1ecbf9258b. Technical validation: MP4, 8.0 seconds, 1280x720. These diagnostic outputs are existing provider media, not canary Assets and are ignored by Git.

Observed network metadata: GET Flow /asb/<resource> image thumbnails; signed Googlevideo media responses (206, video/mp4); flow-content.google media response (200, video/mp4, reported content length 2187170). The official browser download used a blob resource. Response.body() for its full-download response produced zero bytes, so direct network-byte SHA equivalence is UNVERIFIED. Empty response bodies are not canonical video evidence. A subsequent read-only diagnostic hit an ambiguous/not-yet-ready download control and made no download. No generation was dispatched during diagnosis. No authentication headers, raw bodies or signed URLs were persisted.

## Authorized adaptation

User explicitly authorized Outcome B to replace the static data-asset-id baseline. Reused bounded passive decoder with async same-host UI-response observer; raw response bodies exist only in memory. Decoder maps /asb/ tokens to neutral three-component response tuples with exact project UUID binding, rejects token collisions and enforces parse limits. The dedicated new project must have an empty stable baseline, no active progress and a unique submit surface. Generate is guarded by SQLite reservation and in-memory invocation guard. Poll requires trusted official click, prompt reset/acceptance transition, exactly one new tuple and exactly one tile resolving to that tuple. The tuple/job binding hash is persisted before official acquisition. Ambiguity remains INCONCLUSIVE; no second submit.

Read-only adaptation precheck: READY / PROJECT_READBACK_READY; empty stable network identity baseline; 17 observed UI responses. Official diagnostic video validates. Deterministic suite: 65 passed, including decoder collision/limits, wrong-project bodies, causal activation, exact delta, missing/duplicate tiles and repeated-submit rejection, plus all prior timeout/restart/SQLite tests.

Direct media acquisition remains unqualified. Use exact official Download for this canary. No new Flow project created. Frozen SoT unchanged.

Independent review identified textarea acceptance reading and missing baseline refusal coverage. Corrected textarea acceptance to read its actual value, and added deterministic delay-reset and absent/unstable/nonempty/unresolved baseline tests. Full suite now 70 passed. Single-submit SQLite/runtime source remains unchanged.
