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
