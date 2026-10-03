# FLOW-SEQUENCE-SCALE-005 — Final Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-sequence-scale-005`
**Original Package-004 SHA:** `603c4b50fabf8e53de1df5b71ed909d1f3a653dc`
**Package-005 base SHA:** `9e2093fb88b2b4b860af1cc0e7c9e8819f49eacc` (Q0 custody-closure commit)
**Delivery:** `a167506f80ca265f2b4781139a62ab920ee04081` — the exact commit carrying this evidence record (parent `ed20f3d`).

## 1. Active wall time

2026-10-03T00:41Z → 2026-10-03T05:30Z (~4h50m active of the 8h ceiling; Q0–Q16 complete).

## 2. Checkpoint timeline

| Checkpoint | Commit | Result |
| :-- | :-- | :-- |
| Q0_PACKAGE004_PROOF_CUSTODY_CLOSED | 9e2093f | delivery SHA frozen (`603c4b50…`); battery 597/0; recovery mapping (35); B5 judgment source clarified; SoT manifest refreshed 30/30 |
| Q1_SEMANTIC_EXTERNAL_GATE | (recorded) | **SEMANTIC_QC_EXTERNAL_CREDENTIAL_GATE** — no approved Gemini key location exists (repo api_keys/, env, sibling worktrees searched; names only, values never read) |
| Q2 | not run | gate: no permitted evaluator — semantic QC stays UNQUALIFIED |
| Q3 | not run | gate: no qualified evaluator to integrate |
| Q4_MULTI_SEQUENCE_ORCHESTRATOR_READY | ed20f3d | production_run.py (adopted + live sequences) + 9 offline tests |
| Q5_NEW_SEQUENCE_FROZEN | ed20f3d | SEQ005_VALLEY_STREAM (2 scenes × 4 shots) frozen pre-mutation; 8 specs compile 382–443 chars |
| Q6_NEW_SEQUENCE_PRIMARY_COMPLETE | (this delivery) | 8/8 shots PROVEN live (after layout-fix re-entry; zero re-releases) |
| Q7_PRODUCTION_QC_COMPLETE | (this delivery) | technical QC 10 historical + 8 new; 17 cut packets (incl. seq boundary) |
| Q8_REPAIR_DECISIONS_FROZEN | (this delivery) | no new justified repair — 0/3 consumed this package |
| Q9_REPAIR_LOOP_COMPLETE | (this delivery) | 0/3 (no frozen-spec violation found in the new 8) |
| Q10_SELECTION_AND_OWNER_REVIEW_SEAM_READY | (this delivery) | Owner Review Packet: 18 slots + 17 packets; PROVISIONAL_AUTONOMOUS_SELECTION only; OWNER_APPROVED never set |
| Q11_PRODUCTION_RUN_MANIFEST_READY | (this delivery) | edit_82f9162c… (18 clips, historical A + new B, hash-verified locators) |
| Q12_MASTER_ROUGH_CUT_V1_PROVEN | (this delivery) | MASTER_ROUGH_CUT_V1: 144.0 s, sha `0644a741…`, full EOF decode PASS |
| Q13_ROUGH_CUT_REVIEW_CLOSED | (this delivery) | technical review clean → **MASTER_ROUGH_CUT_V1_FINAL_CANDIDATE** (no justified V2; semantic dims OWNER_REVIEW_RECOMMENDED) |
| Q14_RECOVERY_MATRIX_PROVEN | (this delivery) | 45-scenario mapping §5 |
| Q15_PRODUCTION_METRICS_COMPLETE | (this record) | §6 |
| Q16_ADVERSARIAL_REVIEW_COMPLETE | (this record) | §8 |

## 3. Changed files

`tools/production_run.py` (new), `tools/run_production_run_005.py` (new), `tools/freeze_sequence_005.py` (new), `tools/build_master_005.py` (new), `tests/test_production_run.py` (new, 9), `tests/test_flow_r2v_boundary.py` (v2 profile readback), `fixtures/sequence005/*` (9 files), `docs/operating/FLOW_MULTISCENE_SEMANTIC_REPAIR_004_EVIDENCE.md` (Q0 closure), `docs/sot/film/MANIFEST.sha256.json` (refresh).

## 4. Semantic QC status

- **Q1: SEMANTIC_QC_EXTERNAL_CREDENTIAL_GATE.** Credential discovery covered repo `api_keys/`, env `GEMINI_API_KEY`/`GOOGLE_API_KEY`, and sibling worktree `api_keys/` conventions (names/stat only — values never read or printed). No usable credential → Q2/Q3 not run; semantic automation remains UNQUALIFIED and is not claimed.
- The replaceable interface (`semantic_qc.py`, Package-004) + `gemini_advisory` adapter are ready; qualification proceeds exactly per the frozen procedure once the Owner provisions a key at an approved location.
- Production continued unblocked: all semantic dimensions marked OWNER_REVIEW_RECOMMENDED; zero fabricated verdicts; VLM output has no mutation-authority path (interface carries no authority fields — tested).

## 5. Recovery matrix (45 scenarios → concrete proofs)

| Class | Scenario | Proof |
| :-- | :-- | :-- |
| ProductionRun | 1 before run / 2 between sequences / 6 order changed / 7 plan changed | `test_production_run.py`: plan pinning (`::test_run_plan_identity_pinned`), order refusal, PROVEN-demote refusal (`::test_run_state_rejects_demoting_proven`) |
| ProductionRun | 3 historical adopted | `::test_execution_adopts_and_runs_live` (executor never called for adopted) |
| ProductionRun | 4 adopted hash drift | `::test_adopted_snapshot_fails_on_unproven_or_missing` + per-shot gate/hash recheck |
| ProductionRun | 5 new sequence incomplete | `::test_incomplete_live_sequence_blocks_run` (+ no-silent-rerun assertion) |
| Semantic | 8 credential unavailable | Q1 gate recorded (this record §4) |
| Semantic | 9 model unavailable / 10 malformed / 11 timeout | `gemini_advisory` fail-closed `GEMINI_MODEL_DISCOVERY_UNAVAILABLE` / `GEMINI_ADVISORY_MALFORMED` / `GEMINI_ADVISORY_UNAVAILABLE` (prior-package code, unqualified this run) |
| Semantic | 12 source hash mismatch / 13 request id mismatch | `test_semantic_qc.py::test_request_validation_is_strict` + `::test_batch_contract_mismatches_fail` |
| Semantic | 14 stale cache / 15 evaluator drift / 16 prompt fingerprint drift | interface has no cache; evaluator version + prompt fingerprint are required model fields (`SemanticQCObservation`) — drift visible, unqualified status prevents trust |
| Semantic | 17/18 PASS/FAIL wrong source / 19 INCONCLUSIVE | `::test_batch_contract_mismatches_fail` + `::test_frozen_fixture_evaluator_positive_negative_ambiguous` |
| Semantic | 20 disagreement with technical QC | technical QC is the decidable gate; semantic observations carry no authority fields (`::test_observation_never_carries_authority_fields`) |
| Semantic | 21 instability | `::test_evaluator_determinism` (qualified evaluator must be deterministic) |
| Provider | 22–31 | prior-package suites unchanged and green: render lifecycle (33), temporal drop, recovery matrix (5), latch (12), as29s recognizer tests |
| Repair | 32 semantic FAIL without decision | no auto-regeneration path — repairs only via `repair()` + durable decision file |
| Repair | 33 budget exhausted | REPAIR_BUDGET_EXHAUSTED gate (`run_sequence_004.py::repair`) |
| Repair | 34–36 reservation/release/restart | R1 chain (dead reservations 3R–3T; Shot-3U proven) + this package's zero dead reservations |
| Repair | 37 stale primary selected | canonical manifest uses B5R/3U slots; stale scans NONE (R1 + this package) |
| Editorial | 38–40 stale take / wrong scene order / wrong sequence order | plan pinning (`test_sequence_orchestrator.py`, `test_production_run.py`) + EditManifest identity basis |
| Editorial | 41 manifest source missing | `validate_source`/`verify_media` fail-closed (hit and fixed live in Q11) |
| Editorial | 42 AutoEdit package tamper | `validate_producer_package` checksums |
| Editorial | 43–44 receipt/byte tamper | `real_rough_cut` fresh lineage + independent sha re-verification |
| Editorial | 45 Owner approval falsely inferred | OWNER_APPROVED never set; PROVISIONAL_AUTONOMOUS_SELECTION explicit (Owner Review Packet) |

## 6. Production metrics

| Metric | Value |
| :-- | :-- |
| New primary releases | 8/8 (SEQ5_C1–C4, D1–D4) |
| New repair releases | 0/3 (no frozen-spec violation in the new 8) |
| Continuity uploads | 0/1 (same-reference sufficed) |
| Dead reservations (this package) | 0 released-from-dead; 2 killed-runner reservations verifiably unreleased (scene C re-acquired read-only from durable receipts — no re-release) |
| Adopted historical shots | 10 (read-only, zero regeneration) |
| Generated seconds (new) | 64 s; master rough cut 144 s (18 × 8 s) |
| Attribution latency | first reconciliation poll on ALL 8 new shots |
| Semantic QC calls | 0 (credential gate) |
| Generates per selected shot (new seq) | 8/8 = 1.0 |
| Package active time | ~4h50m |

## 7. Execution ledger (new Sequence B)

| Shot | ProviderJob | Provider media | Asset sha256 | Bytes |
| :-- | :-- | :-- | :-- | :-- |
| SEQ5_C1 | (ledger: `generate_ledger.json`) | per-shot `result.json` | per-shot `result.json` | videos under `sequence_SEQ005_VALLEY_STREAM/shot_SEQ5_C1/videos/` |
| SEQ5_C2–C4, D1–D4 | same durable pattern | — | — | — |

Full per-shot job/media/asset identities are in `projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/scene_*/shot_*/result.json` and `generate_ledger.json` (8 entries, release timestamps, may_submit=false proofs). All 8 shots: first-poll attribution, exact marker echo, full EOF decode, technical QC pass, ACQUIRED recovery with `may_submit=false`.

## 8. Adversarial review findings (fixed in-package)

1. Production-run lambda mis-bound the scene plan (KeyError before any mutation) — replaced with an explicit executor function.
2. Scene-layer plan pin collided across multi-scene state dirs (SCENE_D inherited SCENE_C's pin) — per-scene state subdirectories; no re-release occurred.
3. Scene C re-acquisition hit `ACQUISITION_RECORD_CHANGED` (flat-vs-per-scene layout) — resolved by resuming scene C in its original acquisition layout (read-only against existing receipts; zero new releases) and consolidating results.
4. Master packager initially minted DIFFERENT takes for historical shots (new provisional evidence) — fixed to reuse persisted immutable takes; QCStore shot-collision guard was the backstop.
5. `git add -A` staged untracked historical tools again — unstaged pre-commit.
6. `run_plan_hash` used an invalid `json.dumps(encoding=…)` kwarg — fixed.

## 9. Unresolved unknowns

1. Semantic QC stays UNQUALIFIED until the Owner provisions a Gemini (or equivalent) key at an approved location; the interface, offline contract tests, and qualification procedure are ready.
2. The as29s non-null pending-payload shape remains structurally uncaptured (SoT A7).
3. `58bd411e…` remains permanently unreadable via as29s (environmental).

## 10. Production-readiness impact

The system now runs REAL multi-sequence production: a proven historical sequence is adopted read-only into a production run, a fresh 8-shot/2-scene sequence executes under the durable latch, and the combined 18-shot lineage renders through AutoEdit into a 144-second master rough cut — with an Owner review seam (per-slot packets, PROVISIONAL_AUTONOMOUS_SELECTION) and an explicit 45-scenario recovery mapping. The single remaining automation gap is the VLM credential.

## 11. Recommended next LARGE package

**FLOW-SEMANTIC-QUALIFY-006** (Owner prerequisite: provision a Gemini key at `api_keys/gemini_key.txt` or `GEMINI_API_KEY` env): qualify semantic QC per the frozen criteria against the Scene-003/004/005 corpus, integrate behind the QC seam with caching, then run Owner-approved take selection and a semantic-review-driven V2 iteration on the master rough cut.


---

# PROOF CUSTODY CLOSURE (S0, FLOW-SEMANTIC-QUALIFY-006)

## S0A — Exact delivery SHA

Package-005 delivery: `a167506f80ca265f2b4781139a62ab920ee04081` (verified `git rev-parse HEAD` == commit carrying this record before any Package-006 work). Ancestry: `603c4b5…` (Package-004) and `9e2093f…` (Q0 base) are ancestors.

## S0B — Final verification battery at the delivery SHA

- Full network-free regression: **606 passed, 0 failed**.
- Collected test count: 606.
- Compile/syntax: clean. `git diff --check`: clean.
- SoT manifest: 30/30 (refreshed post-A8).
- Protected-file review: SoT 13 appends (A7/A8) + manifest hashes only.
- Secret/PII/API-key scan on Package-005 delta: clean.
- Slice-0011 regression: included in the full run, green.
- Scene-003/R1 regression: test_flow_render_lifecycle.py (33), test_mutation_authority_latch.py (12), test_reference_reconcilable_transport.py (46) — green.
- Package-004 regression: test_sequence_orchestrator.py (13), test_scene_orchestrator.py (18), test_production_run.py (9) — green.

## S0C — Explicit 45-scenario recovery mapping

| # | Scenario | Acceptance | Proof (exact test/function) | Result |
| :-- | :-- | :-- | :-- | :-- |
| 1 | run before first sequence | adopted verified, live deferred | test_production_run.py::test_execution_adopts_and_runs_live | PASS |
| 2 | restart after first shot | per-shot result durable | test_scene_orchestrator.py::test_completed_shots_never_reexecute_after_restart | PASS |
| 3 | restart mid-scene | EXECUTING re-enters exactly once | test_scene_orchestrator.py::test_restart_mid_scene_resumes_from_durable_truth | PASS |
| 4 | restart between scenes | per-scene state dirs isolate pins | test_sequence_orchestrator.py::test_crash_mid_scene2_between_scenes | PASS |
| 5 | all media acquired, pre-QC | packaging read-only + idempotent | build_sequence_004 re-run; QCStore INSERT OR IGNORE | PASS |
| 6 | after QC | takes persist immutable | QCStore shot-collision guard | PASS |
| 7 | after repair decision | decision durable pre-mutation | repair_decision_SEQ4_B5R.json read before reserve | PASS |
| 8 | after selected takes | canonical manifest rebuilds from persisted takes | build_master_005 persisted-take reuse | PASS |
| 9 | before sequence manifest | manifest id = content hash | make_edit_manifest identity basis | PASS |
| 10 | after sequence manifest | overwrite refusal | write_referenced_package 'existing package differs' | PASS |
| 11 | before AutoEdit | rough-cut receipt reuse | real_rough_cut rough_cut_renders check | PASS |
| 12 | after AutoEdit receipt | fresh lineage readback | real_rough_cut 'fresh lineage mismatch' | PASS |
| 13 | sequence order changed | run/sequence plan pin | test_production_run.py::test_run_plan_identity_pinned | PASS |
| 14 | scene order changed | scene plan pin | test_sequence_orchestrator.py::test_scene_order_change_refused | PASS |
| 15 | shot order changed | scene plan pin | test_sequence_orchestrator.py::test_shot_order_change_after_execution_is_refused | PASS |
| 16 | sequence plan content drift | hash pin | test_sequence_orchestrator.py::test_plan_change_after_execution_is_refused | PASS |
| 17 | incomplete prior sequence | adoption refuses non-PROVEN | test_production_run.py::test_adopted_snapshot_fails_on_unproven_or_missing | PASS |
| 18 | adopted state missing | explicit ValueError | same test, missing branch | PASS |
| 19 | duplicate adopted shots | refusal | test_production_run.py::test_adopted_duplicate_shot_refused | PASS |
| 20 | adopted sequence hash drift | per-shot gate/hash recheck | adopted_sequence_snapshot per-result gate check | PASS |
| 21 | stale take in canonical manifest | stale-slot scan | R1 stale-3C scan + Package-004 stale-B5 scan (NONE) | PASS |
| 22 | wrong take selected | QCStore shot-collision guard | qc.py 'different SelectedTake' | PASS |
| 23 | missing selected asset | fail-closed verify | validate_source / verify_media 'referenced media missing' | PASS |
| 24 | manifest source missing | fail-closed at package write | hit live in Q11, fixed locators | PASS |
| 25 | AutoEdit package tamper | checksums.json verify | validate_producer_package | PASS |
| 26 | rough-cut receipt tamper | fresh lineage mismatch raises | real_rough_cut readback | PASS |
| 27 | rough-cut bytes changed | sha vs recorded | rough-cut tamper test + independent sha re-verification | PASS |
| 28 | output-byte tamper | same sha re-verification | post-build sha checks | PASS |
| 29 | Owner approval falsely inferred | OWNER_APPROVED never set | Owner Review Packet model (PROVISIONAL only) | PASS |
| 30 | pending render across restart | RENDER_PENDING -> RECONCILE_ONLY | test_flow_render_lifecycle.py::test_render_pending_is_not_failure… | PASS |
| 31 | unresolved/unknown render payload | UNKNOWN -> UNOBSERVABLE, no streak advance | test_unknown_schema_does_not_advance_drop_counter_or_window | PASS |
| 32 | persistent disappearance | threshold + 900 s temporal policy | test_threshold_plus_minimum_elapsed_window_terminal_drop | PASS |
| 33 | completion beats stale drop | completion precedence | test_completion_before_threshold_prevents_drop | PASS |
| 34 | acquisition partial | staging discarded, refetched | test_recovery_matrix_002.py::test_staging_without_receipt… | PASS |
| 35 | media mismatch | bind_media_bytes fail-closed | test_flow_r2v_boundary.py media binding tests | PASS |
| 36 | owner latch (mutation gate) | one-way durable latch | test_mutation_authority_latch.py (12 tests) | PASS |
| 37 | latch survives restart | durable JSON state | test_latch_survives_restart | PASS |
| 38 | read-only resolution keeps latch | knowledge != authority | test_readonly_resolution_identified_effect_keeps_latch | PASS |
| 39 | unused budget after latch refused | choke point | test_unused_generate_budget_cannot_be_consumed_after_latch | PASS |
| 40 | successor cannot bypass latch | same choke point | test_successor_and_repair_paths_cannot_bypass_latch | PASS |
| 41 | new scope fresh authority | new scope OPEN | test_new_owner_authorized_scope_starts_fresh | PASS |
| 42 | read-only usable after latch | knowledge recording allowed | test_readonly_operations_usable_after_latch | PASS |
| 43 | semantic FAIL cannot Generate | no auto-regeneration path | repair only via durable decision + repair(); semantic_qc has no mutation surface | PASS |
| 44 | VLM PASS != technical pass override | technical gate independent | test_observation_never_carries_authority_fields | PASS |
| 45 | credential absent -> gate, package continues | EXTERNAL_CREDENTIAL_GATE recorded, build unblocked | Package-005 Q1 (parent evidence §4) | PASS |

## S0D — Full new-sequence identity ledger (SEQ005, all 8 slots inline)

| Shot | ProviderJob | Provider media | Asset SHA256 | Bytes | Release | Attribution | Render | Acquisition | may_submit |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| SEQ5_C1 | `job_45e5d29a35b5358b…` | `e4bd163f-07b3-46ba-b96b-2bf5ecb06026` | `86a811477e637380…` | 7,515,842 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |
| SEQ5_C2 | `job_c861cdd1b7395f9b…` | `5efcb0d6-366e-49ae-beef-394169aed3f5` | `93d81043e56ca805…` | 2,638,700 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |
| SEQ5_C3 | `job_536168f72bbf1063…` | `c8bb218b-4272-4a25-801b-a988edbd8fce` | `24ec3a3a2528e605…` | 1,491,416 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |
| SEQ5_C4 | `job_b44414ce4042eacc…` | `bdbcc343-00f3-4f89-84df-c6076d6fd322` | `d156dd8ee3fae4b3…` | 13,026,920 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |
| SEQ5_D1 | `job_61b02a1c0b41cd28…` | `eddf17b5-5fd0-4c7b-a91f-6ef3f6d8099a` | `3d42840371d82bc9…` | 6,928,095 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |
| SEQ5_D2 | `job_bf3b511290a498a6…` | `b5d57862-ceb6-4b30-9e67-abaa9b2fa70c` | `8e17e35e258a7a1a…` | 4,539,204 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |
| SEQ5_D3 | `job_dda46d685b37fe35…` | `0de6b723-90b0-43e3-91c6-c82481cef7b2` | `83bf4774783be0f6…` | 2,549,538 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |
| SEQ5_D4 | `job_c948cfd353d7828e…` | `e18464f5-ec66-4451-85a9-908b8dfd234c` | `70b31768c7f4a2f0…` | 6,699,637 | ONE Generate, at-most-once | marker echo, poll 1 | completion recognized | exact acquire + EOF PASS | false |

All eight: `may_submit = false` permanently after release (recovery `ACQUIRED`, dispatch_count = 1). No shorthand; each row derives from its durable result.json.
