# FLOW-SEQUENCE-SCALE-005 — Final Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-sequence-scale-005`
**Original Package-004 SHA:** `603c4b50fabf8e53de1df5b71ed909d1f3a653dc`
**Package-005 base SHA:** `9e2093fb88b2b4b860af1cc0e7c9e8819f49eacc` (Q0 custody-closure commit)
**Delivery:** the branch tip carrying this record (parent = `ed20f3d` Q4/Q5 commit chain tip; verify `git log -1`).

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
