# FLOW-SCENE-SCALE-003 — Final Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline`
**Branch:** `zcode/flow-scene-scale-003`
**Base SHA:** `919d4df59d920693cf7a464c96e4a216dc9270ab` (accepted parent revision, verified)
**Delivery:** the branch tip carrying this record (verify with `git log -1`); checkpoint chain in §2.

## 1. Clock

| Item | Value (UTC) |
| :-- | :-- |
| Active start | 2026-10-02T15:26Z |
| Active end | 2026-10-02T18:00Z |
| Active wall time | ~2h35m of the 8h ceiling |
| Termination reason | all bounded acceptance criteria genuinely exhausted (C0–C10) |

## 2. Checkpoint timeline

| Checkpoint | Commit | Result |
| :-- | :-- | :-- |
| C0_BASELINE_PROVEN | (verified) | base `919d4df`; manifest 30/30; baseline regression **545 passed**; clean tracked tree |
| C1_N_SHOT_ORCHESTRATOR_READY | fa57646 | generic scene layer (N≥1, durable restart-safe state, plan identity pinned) + 18 offline tests incl. restart windows |
| C2_SCENE_PLAN_FROZEN | fa57646 | six ShotSpecs + ScenePlan frozen BEFORE first live Generate; all compile 389–445 compact chars |
| C3 primary scene executed | 724a453 | shots 1,2,4,5,6 PROVEN live (5 releases); shot 3 slot dead-reservation handled via loud successors |
| C4_CONTINUITY_MECHANISM_QUALIFIED | 724a453 | LAST_FRAME_CONTINUITY_PROVEN (1/2 uploads; read-only reconciliation of the armed upload) |
| C4_SCENE_QC_COMPLETE / C5_REPAIR_LOOP_CLOSED / C6_SCENE_MANIFEST_PROVEN / C7_AUTOEDIT_ROUGH_CUT_PROVEN | (this delivery) | 6/6 QC pass, 5 cut packets, repair 0/2, manifest + package + real 48 s rough cut |
| C8_SCENE_RECOVERY_PROVEN | bada8d5 | scene-level restart/refusal/tamper tests; per-shot matrix from prior packages still green |
| C9_PRODUCTION_METRICS_COMPLETE | (this record) | §6 |
| C10_ADVERSARIAL_REVIEW_COMPLETE | (this record) | §7 |

## 3. Changed files (delta vs base)

`tools/scene_runner.py` (new), `tools/run_scene_scale_003.py` (new), `tools/build_scene_003.py` (new), `tests/test_scene_orchestrator.py` (new, 18 tests), `tests/test_reference_reconcilable_transport.py` (+2), `fixtures/scene003/*` (7 files), `src/film_pipeline/providers/flow_canonical_ui.py` (quick-add drift), `src/film_pipeline/providers/flow_reference_transport.py` (preexisting_ids).

## 4. Frozen ScenePlan (frozen before the first live Generate)

`fixtures/scene003/scene_plan_003.json` — scene `SCENE003_CLOUD_SUMMIT`, six 8 s Veo shots of the qualified swordsman character/world, in order: 1 establishing (EWS) → 2 ridge walk (WS, action) → 3 blade draw (MS) → 4 face performance (MCU) → 5 hilt cut-in (ECU insert) → 6 hero resolution (WS). Continuity invariants frozen per shot: white robes + single sword, summit/cloud-sea geography, dawn light from frame-left, screen direction frame-left.

## 5. Ledgers

### 5.1 ProviderJob / media ledger (all uniquely marker-attributed, may_submit=false forever)

| Shot | ProviderJob | Provider media | Asset sha256 | Bytes | Continuity |
| :-- | :-- | :-- | :-- | :-- | :-- |
| SCENE003_SHOT_1 | `job_c2a3e6f3ee09…` | `c0f22d55-1177-4f8f-b92b-0787133d495d` | `98210914c10c4513…` | 1,809,285 | same reference |
| SCENE003_SHOT_2 | `job_694d7dca7518…` | `1bd453b5-e9eb-4201-b8aa-059173960617` | `b45816bbf747dda8…` | 2,263,842 | same reference |
| SCENE003_SHOT_3C | `job_fe0a5e736451…` | `cae6e2a5-b035-480e-a4c6-9377e8175237` | `c94b2c0c02139e62…` | 1,676,876 | **last-frame(shot 2)** |
| SCENE003_SHOT_4 | `job_fac2339842cf…` | `140b8a1b-3c20-4750-a0f8-23dc3c67c088` | `d68b264847d08eec…` | 1,755,240 | same reference |
| SCENE003_SHOT_5 | `job_db8409e214c9…` | `47da166d-4a69-4046-b01a-d25800492a82` | `f3e5233f5c8be8e2…` | 1,176,238 | same reference |
| SCENE003_SHOT_6 | `job_82d2d37325dd…` | `e6e11a6f-1e9e-4446-b306-c0768ec5a137` | `6dde523130cfa1e8…` | 2,770,699 | same reference |

Total acquired: 11,452,180 bytes (48 s of 1280×720 H.264 video). Every shot: attribution on the FIRST reconciliation poll (exact marker echo), first render observation `RENDER_UNOBSERVABLE` (the evidenced non-null pending-payload class — SoT A7) followed by recognized completion, exact acquisition, full EOF decode PASS.

### 5.2 Live mutation accounting

| Budget | Cap | Consumed |
| :-- | :-- | :-- |
| Primary generates | 6 | **6** (shots 1,2,4,5,6 + 3C) |
| Repair generates | 2 | **0** (no frozen-spec violation warranted one — a successful outcome per package) |
| Continuity uploads | 2 | **1** (last frame of shot 2) |
| Direct/private MZZa6b | 0 | 0 |
| **Total video generates** | **8** | **6** |

Dead reservations (never released; journal proves `GENERATE_REQUEST_OBSERVED` absent; both stay `RECONCILE_ONLY` forever and were never re-released): `job_5d9ab195…` (shot 3, UI quick-add drift timeout) and `job_4650908e…` (shot 3B, same drift) — superseded **loudly** via durable successor records (`successor_shot_3b.json`, `successor_shot_3c.json`) after the adapter drift was fixed; creative spec and acceptance unchanged (plan v2/v3 note).

### 5.3 Continuity upload ledger (LAST_FRAME_CONTINUITY_PROVEN)

- Source: acquired Shot-2 Asset (sha `b45816bb…`) → deterministic final-frame extraction `frame sha256 5e0dc357…` (1280×720 PNG) → ONE maseQ upload through the proven `FlowReferenceTransport.ensure_verified` (dedicated single-upload store `continuity_upload_1.sqlite`, receipt `refup_73a4bacf…`).
- The upload POST returned HTTP 200 with an unparseable response → `FAILED_AMBIGUOUS` → resolved **read-only**: bounded catalog probes found exactly ONE stable strong content match (`0c16d60b-b027-48da-adb8-c1cb9a4ecf64`) across two stable probes; the only blocking unreadable row (`58bd411e…`) is durably proven pre-existing (it is in the scene's frozen pre-dispatch baseline) and cannot be the uploaded media — `reconcile_only` gained the additive `preexisting_ids` evidence parameter (strict default unchanged; offline tests for both directions).
- Chain: shot-2 asset → extracted frame (sha) → upload receipt → provider media `0c16d60b…` (`provider_media_sha256 ed16cfec…`) → fresh-readback attestation `refbind_9bff…` → read-only adoption into the scene store (`refbind_44da…`) → shot 3C ProviderJob → shot 3C asset. Classification: **LAST_FRAME_CONTINUITY_PROVEN** within this scope; the cut-2 packet shows near-frame-continuous transition (visual evidence; no fabricated semantic verdict).

## 6. Production metrics

| Metric | Value |
| :-- | :-- |
| Primary generations / successful shots | 6 / 6 (dead reservations: 2, zero releases) |
| Repairs | 0 |
| Successful shot per generate release | 6/6 = 100% |
| Generated video seconds | 48 s |
| Selected usable seconds | 48 s (all six takes provisionally selected) |
| Rough-cut seconds | 48.0 s |
| Acquired bytes | 11,452,180 B; rough cut 9,904,976 B |
| Release timeline | 15:37:24 → 15:42:07Z for shots 1,2,4,5,6 (~69 s average between releases); 3C at 16:56:50Z after continuity qualification + two dead-reservation recoveries |
| Total active package time | ~2h35m |
| Provider cost | not available from trusted data — not invented |

## 7. Adversarial review findings (all fixed in-package)

1. **Scene runner resumed a stale pre-continuity result** for shot 3 — the shot's UNRESOLVED status came from a local missing-binding precondition; re-entry was performed loudly (archived stale result + explicit scene-state note), never silently.
2. **Continuity binding returned the upload attestation instead of the adopted attestation** — fixed to consume the scene-store adoption binding; upload attestation retained as provenance.
3. **Out-of-order observation timestamps** in a temporal test draft — rewritten ordered; the implementation degrades conservatively on any out-of-order clock.
4. **`fixtures/scene_plan_003.json` fell into the ShotSpec fixture glob** (`test_film_core_slice` schema round-trip) — moved to `fixtures/scene003/`.
5. `git add -A` twice briefly staged unrelated untracked historical tools — caught and unstaged pre-commit both times.
Reviewed clean: no hardcoded six-shot logic in the scene layer (N≥1 tests), no gallery/newest heuristics, no stale job recovery, no cross-shot/project binding, no repair-as-retry, no unknown-payload-as-pending, no secret/signed-URL/cookie persistence, no Flow Tool code in the production path.

## 8. Verification results

| Check | Result |
| :-- | :-- |
| Scene-layer offline tests | 18 passed |
| Reference transport tests (incl. new reconcile deltas) | 46 passed |
| Slice-0011 regression (explicit, 4 modules) | 63 passed |
| Full network-free regression (final) | **565 passed, 0 failed** (baseline 545 → +20: 18 scene + 2 reconcile; `film_core_slice` fixture-glob cases unchanged after the plan move) |
| `git diff --check` / compile validation | clean |
| SoT manifest | 30/30 (no protected SoT blob changed in this package — no new SoT truth claimed beyond the parent packages' A1–A7) |
| Secret/PII scan on package diff | clean |
| Rough-cut artifact | independent ffprobe (48.000 s, 1280×720 H.264) + full EOF decode PASS + sha256 `2ce8b1fd…` matches the render receipt |

## 9. AutoEdit execution (C8)

Executed through the EXISTING boundary — no AutoEdit redesign: six persisted SelectedTakes → `editorial_runner.real_rough_cut` → manifest `edit_07cea785…` (fresh readback verified) → FFmpeg rough cut render `rough_dacf7299…` → output `rough_cut_edit_d8210ea3….mp4` (9,904,976 B, 48.000 s, 1280×720 H.264, sha256 `2ce8b1fd5a220a3a5c32bfd4a1d4b9db0da5745fb0fdf8ebd0ad565a67dc7fea`, full lineage readback: manifest + sources + take ids match). Producer package `editpkg_fa6f4cc6…` (schema-validated `edit_job_input_v0`) exported alongside with per-media provenance and semantic metadata. `AUTOEDIT_EXECUTION_EXTERNAL_GATE` was NOT needed: the qualified local execution path performed the real render.

## 10. Unresolved unknowns & watch items

1. The non-null as29s pending payload shape remains structurally uncaptured (SoT A7); all six shots observed it and resolved via recognized completion.
2. Upload response unparseability (maseQ HTTP 200 → FAILED_AMBIGUOUS) recurred as in slice-0011; the read-only reconciliation resolved it. Whether the response parser can be repaired against the current envelope is unqualified.
3. `58bd411e…` (pre-existing project image) is permanently unreadable via as29s — environmental; covered by baseline evidence in reconciliation.
4. Last-frame continuity is PROVEN within this scope (one transition); it does not generalize to a universal provider law.
5. Two dead reservations were burned by the same UI drift before the adapter fix — the quick-add path now accommodates newly uploaded media; future first-picker interactions after an upload should watch for further UX drift.

## 11. Production-readiness delta & next package

The pipeline can now execute a REAL multi-shot scene end-to-end: frozen ScenePlan → per-shot qualified generation with continuity (same-reference + last-frame upload mechanism) → per-shot/per-cut QC evidence → provisional takes → one EditManifest → AutoEdit producer package → a real, technically valid 48 s rough cut — all restart-safe with zero blind retries and zero unresolved ambiguity. Recommended next: **FLOW-SCENE-SCALE-004** — Owner-reviewed take selection + semantic QC (VLM) integration, multi-scene sequences, and rough-cut iteration loops (repair-driven), building on the unchanged Film Core.
