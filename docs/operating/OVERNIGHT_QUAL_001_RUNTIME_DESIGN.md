# OVERNIGHT-QUAL-001 — Generic Flow R2V Runtime: design record

Status: IN PROGRESS (checkpoint journal). This file records C0 baseline truth and
the C1 bound. It is extended at every checkpoint; final state is reported in the
delivery handoff, never here alone.

## C0 BASELINE (proven 2026-10-01)

- Worktree: `D:\AI FILM MAKER\AI-Film-Pipeline-Overnight`, branch
  `zcode/overnight-qual-001-r2v-runtime-integration`, HEAD `1d84831e6f1e796d8e9afdd43a9ea6a80ef0cc82`
  (frozen package commit), parent `d8d4b0a94fe4383393407977f0f77ae2e54064e9`
  (implementation baseline). Source repo untouched at `d8d4b0a` on
  `zcode/qual-001-flow-adapter-productization`.
- Environment: isolated execution = source repo `.venv` interpreter (read-only
  reuse; Python 3.11.9, pydantic 2.13.5, jsonschema, Pillow, pytest) +
  `PYTHONPATH` pointing at this worktree's `src`. No package installation, no
  network. Fresh `uv sync --offline` was attempted and failed (incomplete local
  wheel cache); the read-only interpreter reuse was chosen instead so that zero
  network access is required.
- Baseline regression: **433 passed in 84.18s** (`python -m pytest -q`, full
  suite, in this worktree). Floor met; no tests modified.

## C1 BOUND — smallest reusable design

### Decision: one new module, `src/film_pipeline/flow_r2v_runtime.py`

`FlowR2VShotRuntime` composes existing, proven systems; it owns nothing that
already exists elsewhere:

```text
compile_prompt (film compiler, reference_hashes bound)
→ route (execution.route)
→ DryRunProvider.create_attempt
→ make_provider_job preview → generic compact prompt freeze → store.save_path
  + store.save_provider_job (one job per shot; restart returns the prior job)
→ FlowR2VBoundary.reserve_mutation (attestation gate + one dispatch budget
  + MUTATION_INTENT_BOUND journal fact)
→ FlowR2VBoundary.request_guard → OneGenerateGuard (one qualified native
  request; frozen durable prompt)
→ FlowR2VBoundary.observe_native_request (request qualification, transport only)
→ PROVIDER_RESPONSE_OBSERVED / PROVIDER_ACCEPTANCE_OBSERVED facts bound to the
  journal's GENERATE_REQUEST_OBSERVED request_hash
→ FlowR2VBoundary.attribute_output (backend-owned identity vs frozen baseline)
→ store REMOTE_IDENTITY_OBSERVED + bind_owned_output
→ LiveRuntimeExecutor.reconcile (SUCCEEDED from bindings; never re-polls past
  an exact binding) + boundary.acquire_bound_media precondition
  + LiveRuntimeExecutor.download_assets (receipt/staging/promotion machinery)
→ fresh store.read_runtime_lineage + qc_runner.exact_lineage
  + qc.technical_evidence (bytes/metadata/duration gates)
```

Not created (per package): no second dispatch journal, ProviderJob model,
attestation system, acquisition store, or Film Core. `slice0011*.py` are not
imported; their generic *behavior* (freeze-then-reserve, one job per shot,
baseline-gated attribution) is re-expressed compositionally.

### Decision: generic compact prompt adapter at the runtime boundary

The qualified Flow R2V wire envelope bounds the creative body (500 chars /
75 words, marker excluded) and requires exactly one `[FILM-job_<id>]` marker in
the submitted prompt; backend attribution re-finds that marker in output
records. `compile_flow_r2v_prompt` is the historical Shot-A-qualified *semantic*
mapping and stays slice authority. The runtime therefore owns a mechanical,
deterministic adapter `compact_r2v_prompt(plan, provider_job_id)`:

- renders the canonical blocks into fixed-order compact prose (shot/camera/
  subject/action/environment/blocking/continuity), whitespace-normalized;
- fail-closed unless: `provider_id == 'flow_veo'`, `duration_target_s == 8`,
  `mapped_controls['image_input']` is exactly one `{asset_id, sha256}` entry,
  no `[FILM-` anywhere in creative data, body ≤ 500 chars and ≤ 75 words
  (`FLOW_R2V_COMPACT_PROMPT_LIMIT … explicit creative reduction required`);
- appends `film_marker(provider_job_id)` (existing generic marker mechanics);
- freezes `correlation_evidence = {prompt, prompt_plan_hash,
  submission_prompt_hash, correlation_marker, provider_prompt_compiler:
  'flow-r2v-runtime-compact-v1', reference_binding}` before any authority.

Creative/semantic qualification per shot remains a per-shot creative concern;
the runtime guarantees wire-mechanical qualification only, and never silently
truncates or drops creative content.

### Decision: `reference_binding` carries the provider-side reference filename

Backend attribution's optional AST slot checks the reference filename. The
filename is a frozen transport detail, not an authority: it is pinned inside the
`reference_binding` correlation key at freeze (`asset_id`, `reference_sha256`,
`media_id`, optional `provider_filename`). That key is in
`save_provider_job`'s frozen-intent check list and in `intent_hash`, so it is
durable and immutable across restarts; attribution re-reads it from the stored
job, never from mutable caller state.

### Decision: baseline catalog facts

`pre_dispatch_snapshot = {catalog_ids (sorted lower-case UUIDs),
catalog_fingerprint, project_id}`; the runtime fails closed unless the
fingerprint equals `QUALIFIED_BASELINE_FINGERPRINT` and the project matches.
Attribution reuses the frozen snapshot ids as `baseline_ids`.

### Acceptance → proof map (adversarial matrix; test module
`tests/test_flow_r2v_runtime.py`, composed on top of retained boundary tests)

| # | case | proof |
|---|------|-------|
| 1 | shot/plan/route mismatch | freeze raises before any job exists |
| 2 | wrong route provider | freeze rejects non-`flow_veo` route/profile |
| 3 | missing/tampered attestation | runtime reserve → OwnerAmbiguityGate, dispatch_count 0 |
| 4 | attested ≠ intent reference | runtime reserve → gate |
| 5 | project/account/profile drift | scope mismatch / binding fingerprint drift |
| 6 | prompt drift after freeze | FROZEN_PROVIDER_INTENT_CHANGED + boundary PROMPT_DRIFT/TOCTOU (retained) |
| 7 | mutation before reservation | guard refuses unreserved; attribution requires MUTATION_INTENT_BOUND |
| 8 | duplicate/re-entry mutation | reserve → RECONCILE_ONLY; store budget consumed |
| 9 | request without backend output | attribution None → unresolved, reconcile-only |
| 10 | preexisting output | frozen baseline → PREEXISTING_IDENTITY |
| 11 | wrong marker/reference/model lineage | attribution ContractError |
| 12 | multiple candidates | OUTPUT_MARKER_COLLISION |
| 13 | cross-job output rebind | bind_output OUTPUT_ALREADY_BOUND_TO_ANOTHER_ATTEMPT |
| 14 | media ID/project/resource mismatch | acquire_bound_media ContractError |
| 15 | download bytes/metadata mismatch | BoundMedia precondition + ACQUISITION_RECEIPT_BYTES_MISMATCH |
| 16 | local file without receipt | EXISTING_FILE_WITHOUT_ACQUISITION_RECEIPT |
| 17 | staging bytes never final | partial staging discarded, fresh fetch, no Asset from partials |
| 18 | restart after reservation | fresh runtime: no second mutation, reconcile-only |
| 19 | restart after binding | recovery ACQUIRE_ONLY → acquisition continues |
| 20 | restart after acquisition | same exact Asset/lineage, transport fetch count unchanged |
| 21 | QC rejects tampered bytes | exact_lineage + technical_evidence hash mismatch |
| 22 | no Slice-0011 import/coupling | source scan of runtime module + tests use no slice IDs |

Vertical proof: `test_generic_r2v_shot_end_to_end_offline` — ordinary shot
(`FLOW_CANARY_001` + one synthetic reference) through the full runtime path to
QC-handoff eligibility, with a locally FFmpeg-generated valid MP4 fixture and
frozen synthetic provider doubles. Provider access/mutation count: 0.
