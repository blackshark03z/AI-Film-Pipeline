# FLOW-PRODUCTION-HARDEN-MULTISHOT-002 — Final Evidence Record

**Status:** COMPLETED_CANDIDATE
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline`
**Branch:** `zcode/flow-production-harden-multishot-002`
**Starting SHA:** `cdde4507cf0c2f63ffbb76b1afaea1aec9f6db22` (verified tip of `zcode/flow-production-tools-longrun-001`; ancestry from the prior package)
**Delivery:** the branch tip of `zcode/flow-production-harden-multishot-002` carrying this record (verify with `git log -1`); full checkpoint chain in §2.

---

## 1. Clock

| Item | Value (UTC) |
| :-- | :-- |
| Active start | 2026-10-02T11:59Z |
| Active end | 2026-10-02T14:10Z |
| Active wall time | ~2h10m of the 8h ceiling |
| Termination reason | All bounded acceptance criteria genuinely exhausted (C0–C7 complete); remaining ceiling intentionally not spent on speculative work |

## 2. Checkpoint timeline

| Checkpoint | Commit (UTC) | Result |
| :-- | :-- | :-- |
| `C0_BASELINE_PROVEN` | (verified, no commit needed) | tip `cdde450` verified; clean tracked tree; manifest 30/30; profile present; secret scan clean |
| `C1_RENDER_LIFECYCLE_HARDENED` | fe23f59 (12:21Z) | GAP 1 + GAP 2 closed; read-only reference adoption path added (6603aaa) |
| `C2_CURRENT_BUILD_REQUALIFIED` | 4dbbe91 (12:55Z) | LIVE: native route proven on the current build (1/1) |
| `C3_FLOW_TOOL_RECONCILIATION` | f30c336 (13:13Z) | LIVE: `FLOW_TOOL_GENERATION_RECONCILABLE` (1/1) |
| `C4_REAL_MULTISHOT_VERTICAL` | ddfba46 (13:40Z) | LIVE: two-shot scene proven end-to-end (2/2) |
| `C5_RECOVERY_MATRIX_PROVEN` | a30c627 (13:54Z) | 20-scenario matrix closed incl. new lifecycle states |
| `C6_PRODUCTION_VERTICAL_INTEGRATED` | c5ba986 (13:57Z) | seam genericity pinned; SoT 13 addendum A1–A6; manifest 30/30 |
| `C7_ADVERSARIAL_REVIEW_COMPLETE` | 3c4f0fd (14:06Z) | review caught and fixed a real test-process pollution bug; 529 passed |

## 3. Render lifecycle before/after (the two Tech-Lead gaps)

**GAP 1 — bound identity was treated as acquirable.** Before: `OUTPUT_BOUND → ACQUIRE_ONLY` fired with no render evidence. After: a durably bound output without render observation is `OUTPUT_BOUND_UNOBSERVED → RECONCILE_RENDER_STATE`; `ACQUIRE_ONLY` requires a durable `RENDER_COMPLETED_OBSERVED` fact. Proof: `tests/test_flow_render_lifecycle.py` (17 tests), `tests/test_recovery_matrix_002.py::test_consumed_authority_never_yields_may_submit` (12 consumed-state combinations, all `may_submit=False`), and the dispatch-recovery F7 window updated to `OUTPUT_BOUND_UNOBSERVED`.

**GAP 2 — one disappearance was terminal.** Before: a single qualified catalog absence recorded terminal `ADMITTED_RENDER_DROPPED`. After: one disappearance is `RENDER_STATE_UNRESOLVED` (eventual consistency/read lag); terminal drop requires the disappearance to persist across `RENDER_DROP_PERSISTENCE_THRESHOLD = 3` consecutive qualified observations (durable per-observation facts; DB-level immutable journal), or explicit provider terminal evidence (none is observable on current surfaces — no code path fabricates one). Terminality short-circuits further datapoints. Before terminality `may_submit=false` and repair-regeneration authority does not exist. Proof: lifecycle tests 3/3b/3c/9/13 (single disappearance, threshold boundary, streak reset on row return, conflicting completion/drop resolves conservatively to the drop, restart in every state) plus journal-tamper proof (SQLite triggers block UPDATE/DELETE).

## 4. Current-build Flow requalification (C2) — PASS

- Scope: clean Pro profile, qualified project `93a579b4-…`, reference `7b725f7b-…` (the effective reference of the two historically proven generations), `veo_3_1_r2v_lite`, Video → Ingredients, 16:9/8s/x1.
- **Reference chain:** the historical run carried no upload receipt, so the reference was **adopted read-only** (`adopt_existing_reference`): attested readback bound exact provider bytes into the Film registry with the catalog unchanged across adoption (zero provider mutation; no upload budget existed or was needed). JPEG readbacks now supported by the store provenance validator with exact-bytes/metadata checks.
- **Chain:** fresh qualified baseline (9 records) → durable ProviderJob `job_e73294637794…` + preclaim → attested reservation → headful native-UI preparation (settings tokens read back exactly `Video · 720p · 8 giây crop_16_9 x1`) → ONE guard-qualified browser-created Generate → wire HTTP 200 (2,247 B, parsed diagnostics) → unique backend attribution on the FIRST reconciliation poll: provider media `714e901d-1da2-49d1-8d48-09c5f52af3c4`, exact marker echo → `RENDER_COMPLETED` (hardened lifecycle) → as29s exact acquisition 7,067,284 B, sha256 `93fb50df…`, 8.0 s 1280×720 H.264 → full EOF decode PASS → QC exact-lineage + technical pass → restart: `may_submit=false`, redispatch blocked.
- RPC accounting: `Zzl0ze` ×1, `as29s` ×2, direct `MZZa6b` ×0, uploads ×0.
- Verdict: **`CURRENT_FLOW_BUILD_REQUALIFIED`**. No causal claim is made about reCAPTCHA/isTrusted/prompt-dedup/account risk.

## 5. Flow Tool reconciliation (C3) — `FLOW_TOOL_GENERATION_RECONCILABLE`

- Reused the existing private canary tool "Director's Shot Lab" (`083a64f8-…`); no tool created/edited. The tool's first-party production UI runs inside a sandboxed blob iframe (`flow-applet-runner`).
- Pre-conditions honored: fresh catalog baseline (10 records incl. the requal output), preclaimed marker `[FILM-job_0e1a1f45…]`, tool identity recorded, code/config read back (React TSX + internal `flow-sdk`), first-party invocation (the runner only filled the tool's prompt and clicked the tool's own Render control once), read-only reconciliation installed.
- The tool host issued **different wire RPCs (`YhhmEf`, `jwpduf`) — NOT `MZZa6b`** — yet the backend persisted the generation into the project catalog: exactly one fresh id `515afb77-3b90-473d-8409-e21181fd46b2`, unique marker echo, correct project binding, as29s resolved, acquired 2,285,089 B sha256 `c852e728…`, 8 s 1280×720 H.264, full EOF decode PASS.
- Classification: `FLOW_TOOL_GENERATION_RECONCILABLE` — a **capability observation** (SoT 13 A5). The production mutation path remains the provider-native UI; a `flow_tool` adapter is future work requiring its own qualification. No claim about which wire surface tools use beyond the two observed ids.

## 6. Multi-shot vertical (C4) — PROVEN

| Item | Shot A | Shot B |
| :-- | :-- | :-- |
| ShotSpec | `fixtures/multishot_shot_a.json` (establishing, EWS, locked) | `fixtures/multishot_shot_b.json` (performance/MCU, locked) |
| ProviderJob | `job_9a9e85e0…` | `job_61ae1a84…` |
| Generate | 1/2 consumed | 2/2 consumed |
| Provider media | `7495b46c-8377-44f6-a13c-968df523c9c7` | `1ecc7be4-3941-4f50-8c9c-71edf4b9d288` |
| Asset sha256 | `2064c6ef…` (2,213,509 B) | `e9e7fe34…` (1,696,011 B) |
| Attribution | marker echo on first poll | marker echo on first poll |
| Render lifecycle | live pending-shape observations → `RENDER_COMPLETED` | live pending-shape observation → resolved on attempt 2 |
| Decode | full EOF PASS | full EOF PASS |
| QC | pass (exact lineage + technical) | pass (exact lineage + technical) |
| Restart | `may_submit=false`, recovery `ACQUIRED` | `may_submit=false`, recovery `ACQUIRED` |

- Continuity mechanism: the SAME verified adopted reference conditioned both shots (SoT 06 mechanism 1). No upload occurred; no unsupported continuity control claimed.
- Continuity evidence: `continuity_a_end_vs_b_start.png` (Shot A last frame | Shot B first frame) — same character identity, wardrobe, light and world across the cut (visual packet for Owner review; no automated VLM verdict claimed).
- SelectedTakes (provisional): `take_db77e5d1…` (A), `take_ee9108fc…` (B) — recorded with a transparently labeled autonomous build-worker approval (`reviewer_id` names it; notes mark it provisional pending Owner post-hoc review; the Owner may reject and re-select). This is the one judgment call made to satisfy the frozen package's explicit SelectedTake requirement while the Owner was away.
- Handoff: EditManifestV1 `edit_1b97c8ba…` (two clips, order 1→2) and the AutoEdit producer package `editpkg_38673b5e…` (schema-validated `edit_job_input_v0`, referenced media, checksums; no AutoEdit redesign).
- Live mutation accounting: 2/2 consumed; each shot at-most-once; no retries; a read-only resume path was exercised for Shot A after a runner-local fix (no redispatch).

## 7. Live mutation budget — total

| Budget | Authority | Consumed |
| :-- | :-- | :-- |
| Native current-build requal generate | 1 | 1 (C2) |
| Flow Tool video generate | 1 | 1 (C3) |
| Multi-shot generates | 2 | 2 (C4: A, B) |
| Uploads | 0 granted | 0 performed |
| Direct/private `MZZa6b` | forbidden | 0 (structural guard + wire accounting) |

Each sub-budget was consumed only after its preceding gate passed. No budget was used as retry authority. The runner-local failures encountered during development (Path+str, schema enums, store initialization, prompt-limit fail-closed, asyncio/playwright thread conflict, non-null pending as29s payloads) all occurred BEFORE any Generate was released for that shot and are archived as `*.local_bug_*.json` next to the durable results.

**Owner gates in this package: none.** Fail-closed interim states recorded by the runners (e.g., a release result is stamped `OWNER_AMBIGUITY_GATE` until backend reconciliation resolves it) were each resolved by read-only reconciliation to `REQUAL_PROVEN`/`SHOT_PROVEN`/`RECONCILABLE`; none required Owner input and no ambiguity survived.

## 8. Restart/recovery matrix (C5)

All 20 frozen scenarios covered: crash windows F0–F7 (existing suite, F7 re-pointed to the new classification); admission-without-identity (`DISPATCH_CONFIRMED → RECONCILE_ONLY`); bound-unobserved (`OUTPUT_BOUND_UNOBSERVED → RECONCILE_RENDER_STATE`); pending/unresolved/disappearance/persistent-drop/return (lifecycle suite); completed-not-acquired (`RENDER_COMPLETED → ACQUIRE_ONLY`); partial staging discarded + refetched; orphaned destination fails closed; receipt/bytes tamper fails closed; acquired (`ACQUIRED → RECOVER_ASSET`); profile missing → explicit session failure; frontend contract drift → `RENDER_UNOBSERVABLE`/shape gates; marker collision; multiple candidates; reference/project mismatch; signed-URL/media binding mismatches; identical-duplicate normalization; conflicting resources; cross-job/cross-project binding refusals (existing suite); Tool-output-without-backend-identity → `NOT_RECONCILABLE`/`INCONCLUSIVE` classification path (Phase 3 runner + SoT A5). Invariant proof: every consumed-authority fact combination keeps `may_submit=False`.

## 9. Tests, verification, hygiene

- Full regression: **529 passed, 0 failed** (final; 511 at package start → +18: 17 lifecycle + 5 adoption + 5 recovery-matrix + 3 genericity, minus nothing removed; F7 expectation updated).
- `git diff --check`: clean. SoT manifest: 30/30 verified over post-addendum blobs. Secret/PII scan on the package diff: clean (no cookies, tokens, signed URLs, CAPTCHA material, account PII). Protected-file review: only `docs/sot/film/13_FLOW_NATIVE_UI_QUALIFICATION.md` (addendum A1–A6; no historical statement modified) and the manifest hash refresh.
- Adversarial review finding fixed: the seam-genericity guard originally polluted the shared pytest process (module reload + sys.modules deletion) and broke 13 slice0011 tests — replaced with a fresh-subinterpreter proof (the actual claim), restoring 529 green.
- Changed files: the 17 files listed in `git diff --name-only cdde450..HEAD` (3 src, 6 tests, 5 tools, 2 fixtures, 2 SoT/docs).

## 10. Classifications & unresolved unknowns

- Flow native route: **CURRENT_FLOW_BUILD_REQUALIFIED** (qualified scope unchanged: same account/profile/project/reference/model/mode; bundle-revision drift watch item remains, DOM/settings contract re-verified live).
- Flow Tool: **FLOW_TOOL_GENERATION_RECONCILABLE** as a capability observation (production path unchanged; adapter = future qualified work). UNKNOWNs: full `flow-sdk` surface (references/batch/count), tool-run model/credit semantics at scale, tool-runtime drift independence, whether tool wire ids (`YhhmEf`/`jwpduf`) are stable.
- New watch item: **non-null as29s pending payloads** on the current build (SoT A2) — the pending signature is no longer null-only; the hardened lifecycle treats unparseable payloads as pending evidence.
- Multi-shot continuity beyond same-reference (last-frame upload, Ingredients reuse) remains unqualified — an upload budget would be required and was not granted.

## 11. Production-readiness impact

The Flow path is now: qualified on the current build, productized behind a generic seam (no Slice-0011 dependency, structurally pinned), with admission/render/acquisition lifecycle hardened to the Tech-Lead spec, a read-only reference-adoption path for pre-existing project media, a live-proven two-shot scene with QC→takes→manifest→AutoEdit handoff, and a recovery matrix that keeps `may_submit=False` in every consumed state. The next natural large package is a `flow_tool` adapter qualification (only if the Owner wants Tool-based orchestration) or scaling the proven vertical to a full scene list.

## 12. Next recommended large work package

**FLOW-SCENE-SCALE-003**: generalize the proven two-shot vertical into N-shot scene execution (scene list → per-shot lifecycle → per-cut continuity packets → single EditManifest/AutoEdit handoff), with a bounded continuity-mechanism qualification slice (last-frame reference upload) only if the Owner grants an upload budget. No push, no merge performed.

---

# TECH LEAD PROVE HARDENING DELTA

Status: **COMPLETED_CANDIDATE** (offline delta; Tech Lead retains final PROVE acceptance — no PROVEN claimed here).

## Scope & custody

- Starting SHA: `1cc54de497ab4bc2601b3f759dd4afbd8cf868f0` (prior delivery tip, branch `zcode/flow-production-harden-multishot-002`).
- Delta delivery SHA: the branch tip carrying this section (delta root commit `85f2f55`; SoT manifest refresh `f807836`).
- Live provider mutations in this delta: **0**. Native requal Generate: 1/1 (historical package count, unchanged). Flow Tool Generate: 1/1 (unchanged). Multi-shot Generates: 2/2 (unchanged). Uploads: 0 (unchanged). Direct/private MZZa6b: 0 (unchanged).
- Changed files: `src/film_pipeline/flow_r2v_runtime.py`, `src/film_pipeline/dispatch_evidence.py`, `src/film_pipeline/store.py`, `tests/test_flow_render_lifecycle.py`, `tools/run_current_build_requal_002.py`, `tools/run_multishot_vertical_002.py`, `docs/sot/film/13_FLOW_NATIVE_UI_QUALIFICATION.md` (addendum A7 only), `docs/sot/film/MANIFEST.sha256.json` (hash refresh).

## FIX 1 — exact pending-shape semantics

New deterministic, schema-specific recognizer `classify_as29s_payload(payload, *, media_id, project_id)`:

- Recognized shapes (exhaustive): (1) JSON `null` — the historically observed and still-evidenced pending form; (2) the qualified completed media-resource shape for the exact owned id/project (the flow_media contract is the schema check).
- Everything else — arbitrary objects, non-list types, wrong lengths, the live-observed class of right-length/right-id-slot lists with drifted inner slots, extra/unknown slots — is `UNKNOWN` → `RENDER_UNOBSERVABLE` + durable `OBSERVATION_FAILURE`, advancing neither any render state, nor the disappearance streak, nor the persistence window, and never inferring terminal failure.
- The non-null unparseable payload observed once live was never structurally captured, so it is deliberately NOT a recognized pending shape; a future shape enters the recognized set only with captured, constrained structural evidence (SoT A7).
- Runtime integration: `observe_render_state` classifies before any state decision; `UNKNOWN` cannot append `RENDER_COMPLETED` or `ADMITTED_RENDER_DROPPED` (tested). Runner poll loops (`run_multishot_vertical_002.poll_media`, `run_current_build_requal_002._poll_media_resolution`) now branch on the recognizer: only a `COMPLETED` classification resolves the loop; `KNOWN_PENDING`/`UNKNOWN` keep read-only polling.

## FIX 2 — exact render-drop temporal policy

`ADMITTED_RENDER_DROPPED` requires ALL of: durable unique binding (precondition); all streak observations qualified; owned row absent across ≥ `RENDER_DROP_PERSISTENCE_THRESHOLD = 3` consecutive qualified disappearance observations; disappearance persisting ≥ `RENDER_DROP_MIN_ELAPSED_SECONDS = 900` (15 minutes — chosen because proven renders complete within ~30–120 s and provider consistency windows are expected far shorter; a disappearance both repeatedly observed and ≥15 min old is durable absence, not a polling burst); no qualified row return during the streak; no completion evidence; and the terminal observation itself qualified.

- Elapsed time is measured **durably**: journal timestamp of the streak's FIRST disappearance → the current qualified observation. `append_fact`/`record_dispatch_fact` gained an explicit, digest-bound `at` parameter; `observe_render_state` gained `observed_at` (production: wall clock; tests: pinned times, zero sleeps). Process memory is never the time source, so a restart cannot shorten the window; a pre-streak/out-of-order clock can only fail the window, never satisfy it; malformed/naive timestamps fail closed (`RENDER_OBSERVATION_TIME_INVALID`) before anything is journaled.
- Row return records `RENDER_PENDING_OBSERVED`, which breaks the streak and starts a new persistence interval on the next disappearance. Unqualified/unknown observations are skipped by the streak walk (no advance, no reset). `RENDER_COMPLETED` evidence is terminal-protective: `observe_render_state` short-circuits to `RENDER_COMPLETED` and `recovery_decision` now ranks completion ABOVE a recorded drop (resolved media outranks a policy-derived absence — reversing the prior conservative drop-wins order per Tech Lead direction).
- Before threshold+window: `RENDER_STATE_UNRESOLVED → RECONCILE_ONLY`, `may_submit=false`, no repair authority.

## FIX 3 — exact test arithmetic (audited, not guessed)

Method: per-file `pytest --collect-only` counts at the baseline SHA via a temporary git worktree, diffed against the delivery SHA.

| Inventory point | Collected tests |
| :-- | :-- |
| Baseline `cdde450` (prior package start) | **511** |
| Prior delivery `1cc54de` | **529** |
| This delta final | **545** |

Original-package delta `511 → 529 = +18`, broken down exactly:

- `tests/test_flow_render_lifecycle.py`: 14 → 17 (**+3 net**) — the file was created in the prior package with 14 tests; the first round of this package added 3 net tests. The earlier evidence line "17 lifecycle" wrongly counted the whole file.
- `tests/test_film_core_slice.py`: 14 → 16 (**+2**) — it parametrizes over `fixtures/*.json`; the two new multishot fixtures each added one case. This was missing from the earlier breakdown entirely.
- `tests/test_reference_adoption.py`: 0 → 5 (**+5**, new file).
- `tests/test_recovery_matrix_002.py`: 0 → 5 (**+5**, new file).
- `tests/test_production_seam_genericity.py`: 0 → 3 (**+3**, new file).
- Sum: 3 + 2 + 5 + 5 + 3 = **18** = 529 − 511. No tests were removed; `test_dispatch_recovery`'s F7 expected-classification string was updated in place (count unchanged). The earlier "+18" total was correct; its component breakdown was wrong in the two ways above. Historical records stand unmodified; this section is the labeled correction.

This delta: `529 → 545 = +16`, all in `tests/test_flow_render_lifecycle.py` (17 → 33): 20 new test functions covering FIX 1/FIX 2, minus 4 prior functions removed by merge/rewrite (single-disappearance merged into the two-disappearance test; persistent-disappearance split into inside-window and threshold+window tests; row-return split into reset and new-interval tests; drop-is-terminal replaced by the two completion-precedence tests). 20 − 4 = +16. No other test file changed.

## Adversarial review findings (found and fixed within the delta)

1. The first temporal test draft used an out-of-order observation timeline (an unknown payload at t+100000 s followed by a qualified observation at t+900 s) — a physically impossible ordering that would have exercised the policy on contradictory journal time. Rewritten with an ordered timeline; the implementation additionally degrades conservatively on any out-of-order/pre-streak clock (elapsed can only fail the window).
2. Identical `OBSERVATION_FAILURE` diagnostics dedupe in the immutable journal — an initial test wrongly expected one failure row per unknown read; corrected to assert the idempotent single row (the state semantics were already correct).
3. Malformed/naive `observed_at` could have been journaled before validation on some paths; validation now happens at method entry, before anything is written.
4. `git add -A` briefly staged four untracked historical investigation tools unrelated to this delta; caught during pre-commit review and unstaged.

Reviewed clean: no unknown-payload-as-pending path, no drift-as-consistency path, no rapid-poll terminality, no restart window shortening, no completion downgrade, no submit/repair authority before terminality, no test-order or import/reload pollution (the genericity proof runs in a fresh subinterpreter).

## Verification results

| Check | Result |
| :-- | :-- |
| Focused render-lifecycle suite | 33 passed |
| Recovery matrix | 5 passed |
| Reference adoption | 5 passed |
| Genericity (fresh subinterpreter) | 3 passed |
| Slice-0011 regression (4 modules, explicit) | 63 passed |
| Complete network-free regression | **545 passed, 0 failed** |
| Test collection audit | 545 collected (per-file deltas above) |
| Compile/syntax validation | clean |
| `git diff --check` | clean |
| SoT manifest | 30/30 verified over post-A7 blobs (regenerated) |
| Tracked secret/PII scan on delta | clean |
| Protected-file review | only SoT 13 addendum A7 + manifest hash refresh |
