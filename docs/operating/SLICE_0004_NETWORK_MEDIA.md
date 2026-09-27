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

## Live canary continuation and final stop

Frozen execution source: 5b5e294263890f97dfd55c225292a6d598667161. After READY and the stable empty network baseline, Gate 5 persisted the full ShotSpec/PromptPlan/RoutingDecision/GenerationAttempt/ProviderJob path in the fixed runtime SQLite DB. The existing atomic reserve committed dispatch_count=1 before the sole transport invocation. The transport did not return a confirmed Generate receipt; job remains SUBMISSION_RESERVED / INCONCLUSIVE with submitted_at=null. No second invocation or Generate is authorized. Exact external submit transactions are unconfirmed (0 or 1), while the conservative durable budget is consumed (1). No external job ID or acquired canary output exists.

Fresh read-only reconciliation of the same job/project found zero response identities, zero video tiles and zero activity indicators. Absence is not no-dispatch proof. Causal activation evidence is unavailable, so reconciliation correctly retained INCONCLUSIVE. No reset, redispatch or state rewriting occurred. New SQLite handle reconstructs the complete frozen core path and job; zero canary Assets. Gates 8–9 remain unproven; Gate 10 core/job readback passes but complete Asset lineage is not established. Final full regression: 70 passed. No implementation source was changed after the consequential phase.

Safe lineage readback:

```json
{
  "result": "INCONCLUSIVE",
  "remote_readonly": {
    "identity_count": 0,
    "video_tiles": 0,
    "activity_indicators": 0
  },
  "frozen_source_sha": "5b5e294",
  "canary": {
    "shot_id": "FLOW_CANARY_001",
    "shot_spec_hash": "5c6e0256269105fec0988e84fc67b206ef740d5d16c2e2c67347b4b3c8c0bbc2",
    "prompt_plan_hash": "52c232e3f70947806814427fc4f31af1b1cbc8e4d93189ab189863f06f4fdbeb",
    "routing_decision_id": "route_3b199995b3459dcb7f540f17e6d94833f3d9b631e687fbc63d20c5e50a0f46e0",
    "generation_attempt_id": "attempt_c4c8cb3afe1de581ed07f7c620a2bf43470b03d469de6595691e61aab4880eaa",
    "provider_job_id": "job_f1f239861c477db36d0cb28369a14c7ccda7d4f1a9808246f72ce6637e9f6cd1"
  },
  "external_effect": {
    "dispatch_count": 1,
    "submission_state": "SUBMISSION_RESERVED",
    "submitted_at": null,
    "terminal_state": "INCONCLUSIVE",
    "external_job_id": null,
    "confirmed_generate_transactions": null
  },
  "correlation": {
    "method": "passive_response_tuple_baseline",
    "baseline_ids": [],
    "output_ids": []
  },
  "assets": [],
  "fresh_readback": true
}
```

NEXT: Must not dispatch again under this slice authorization. Preserve INCONCLUSIVE. SLICE-0005 not started.
