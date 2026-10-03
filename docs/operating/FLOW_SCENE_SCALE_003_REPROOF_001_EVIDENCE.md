# FLOW-SCENE-SCALE-003-R1 — CONTINUITY RE-PROOF + OWNER-GATE HARDENING — Final Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline`
**Branch:** `zcode/flow-scene-scale-003-reproof-001`
**Starting SHA:** `bd0a0942b7d1990f7e027cad61428d0f75d98807` — resolved exactly: the tip of `zcode/flow-scene-scale-003` carrying `docs/operating/FLOW_SCENE_SCALE_003_EVIDENCE.md` (ancestry from accepted parent `919d4df…` verified; tracked tree clean at start)
**Delivery:** the branch tip carrying this record (parent `6de3ab1`).

## 1. Active wall time

2026-10-02T23:50Z → 2026-10-03T02:35Z (~2h45m active of the 4–6h target; all checkpoints R0–R7 complete).

## 2. Protocol-breach statement (historical truth, preserved)

The original FLOW-SCENE-SCALE-003 run observed the continuity upload POST → HTTP 200 → response unparseable → `FAILED_AMBIGUOUS`. Under the frozen rules that ambiguity required `OWNER_AMBIGUITY_GATE` with ALL further provider mutation permanently stopped for that package. The prior worker's read-only reconciliation validly identified the uploaded media, but the worker then executed Shot 3C — a mutation after an ambiguity gate should have latched. This history is preserved unmodified: Shot 3C (provider media `cae6e2a5…`, job `job_fe0a5e73…`, asset `c94b2c0c…`) is retained as historical evidence but is NOT clean authorized-mutation proof and is excluded from the canonical lineage.

## 3. Owner-gate latch implementation (R1)

`tools/mutation_authority.py` — durable, per-execution-scope, one-way:

```text
external_effect_knowledge: UNKNOWN → RESOLVED_NO_EFFECT | RESOLVED_EFFECT_IDENTIFIED
mutation_authority:        OPEN → LATCHED_CLOSED   (terminal, one-way)
```

- Enforced in runner behavior: `check_mutation_allowed` gates `run_scene_shot` (before reserve), the continuity upload path, and the re-proof runner's fresh-generate path; ambiguity in the shot/upload handlers calls `latch(...)`; `consume(budget_kind)` records authorized consumption and re-checks the latch.
- `retroactive_latch` recorded custody for the historically breached scope (`projects/flow_scene_scale_003/mutation_authority.json` = LATCHED_CLOSED with RETROACTIVE_CUSTODY_LATCH event) — history annotated, never erased.
- 12 adversarial tests (`tests/test_mutation_authority_latch.py`): upload/generate ambiguity latches; both knowledge resolutions keep the latch; restart preserves it (fresh instance over disk); unused generate/upload budgets refused; successor/repair/scene-resume paths cannot bypass (same choke point, no bypass flag); a NEW scope starts OPEN; the latch is one-way; read-only operations remain usable after latching.

## 4. Read-only continuity reference re-attestation (R2)

Full chain recomputed read-only (0 mutations): Shot-2 asset sha `b45816bb…` → deterministic final frame `5e0dc357…` → historical upload receipt `refup_73a4bacf…` (state VERIFIED in `continuity_upload_1.sqlite`) → provider media `0c16d60b-b027-48da-adb8-c1cb9a4ecf64` (row unique, project matches) → **fresh provider readback sha `ed16cfec39da…` == receipt `provider_media_sha256`** → immutable attestation recomputed identically (`refbind_9bff…`). `provider_mutations: 0`. Note: extracted-frame bytes ≠ readback bytes (provider re-encodes uploads); content-level strong-match attestation is the evidence chain, byte-inequality documented.

## 5. Fresh authorized Shot-3 re-proof (R3)

- Budget: MAX_FRESH_VIDEO_GENERATE = 1 → consumed 1/1. Uploads: 0/0. Retries: 0.
- New fixture `scene003_shot_3u.json` (shot_id `SCENE003_SHOT_3U`; original Shot-3 creative intent unchanged).
- New ProviderJob `job_38d4368c972d…`, new marker `[FILM-job_38d4368c…]`, new pre-dispatch baseline, attested reservation.
- ONE native-UI Generate (guard-qualified, headful) → HTTP 200 observed → **unique backend attribution on the first reconciliation poll**: provider media `288910c3-f47a-4344-bce3-26b61bec8fba`, exact marker echo → `RENDER_UNOBSERVABLE` (evidenced pending class) → recognized completion → exact acquisition 1,817,751 B, asset sha `495ab74bc51070da…` → full EOF decode PASS → QC exact-lineage + technical pass → `may_submit=false`, recovery `ACQUIRED`.
- Latch events: `BUDGET_CONSUMED(fresh_video_generate)` + knowledge `RESOLVED_EFFECT_IDENTIFIED`.

## 6. Dead-reservation ledger (all verifiably never released)

| Job | Shot | Journal kinds | Guard requests | Custody |
| :-- | :-- | :-- | :-- | :-- |
| `job_5d9ab195…` | 3 | RESERVED, MUTATION_INTENT_BOUND | 0 | `successor_shot_3b.json` (prior package) |
| `job_4650908e…` | 3B | RESERVED, MUTATION_INTENT_BOUND | 0 | `successor_shot_3c.json` (prior package) |
| `job_9295d326…` | 3R | RESERVED, MUTATION_INTENT_BOUND | 0 | archived `shot_3R_result.local_intent_drift.json` |
| `job_4442ebb6…` | 3S | RESERVED, MUTATION_INTENT_BOUND | 0 | `successor_shot_3t.json` |
| `job_d08575b1…` | 3T | RESERVED, MUTATION_INTENT_BOUND | 0 | `successor_shot_3u.json` |

Every dead job stays `RECONCILE_ONLY` forever; none was re-released; the fresh release slot was consumed exactly once by Shot 3U.

## 7. Continuity proof (R4) — LAST_FRAME_CONTINUITY_PROVEN

- Cut 2→3U packet: Shot-2 last frame | Shot-3U first frame — same character identity (white robes, hair bun + band, sword at side), same summit geography (rock/snow, identical cloud-sea and range), same dawn light from frame-left; the transition is near-frame-continuous, matching the mechanism's purpose. Visual evidence only; semantic verdict = OWNER_REVIEW_RECOMMENDED (no qualified VLM fabricated).
- Cut 3U→4 packet: Shot-3U last frame | Shot-4 first frame — identity/wardrobe/light continuous into the MCU beat.
- Classification: **LAST_FRAME_CONTINUITY_PROVEN** — source frame provenance exact, provider reference exact (re-attested), ProviderJob exact (fresh authority), output exact, zero mutation ambiguity, packets exist, no frozen-spec violation.

## 8. Clean six-shot lineage (R5) + rough cut (R6)

- New SelectedTake ledger (all PROVISIONAL_AUTONOMOUS_SELECTION, no Owner approval claimed): shots 1,2,4,5,6 reuse their unchanged immutable assets/takes (`take_e784c62b…`, `take_1acd7e32…`, `take_a98e0482…`, `take_2081a6e5…`, `take_945efac8…`); slot 3 = fresh `take_49f12ec8…` (SCENE003_SHOT_3U).
- New EditManifest `edit_2abf920b…` (project `ai_film_scene_scale_003_reproof_r1`, 6 clips, order 1→6).
- New AutoEdit producer package `editpkg_7171a045…` (schema-validated, referenced media incl. `reproof_media` root).
- New rough cut: render `rough_ad4663f8…`, artifact `rough_cut_edit_10abb1e3….mp4`, sha256 `0227e8eb6ca2b9bb…`, 48.000 s, 1280×720 H.264, 9,940,368 B — independent ffprobe + full EOF decode PASS.
- **Stale-3C scan: `cae6e2a5…`, `job_fe0a5e73…`, `c94b2c0c…` are ABSENT from every json in `scene_package_reproof_r1/` and from the package files (`edit_job.json`, `checksums.json`); the new Shot-3U asset IS present.** Superseded prior packages retained under versioned names, never overwritten.

## 9. UI overlay contract v2 (discovered during R3)

The settings overlay's checked-toggle set is MODEL-DEPENDENT: with Omni 1.1 Flash persisted, `720p`/`8 giây` toggles appear; selecting the qualified Veo 3.1 - Lite restores the original 4-toggle shape. `prepare_inputs` now deterministically SELECTS the qualified model inside the overlay (`ensure_qualified_model`, fail-closed when not offered) before verification; wire model unchanged (`veo_3_1_r2v_lite` — enforced by the guard's request validation). Contract tag `native-ui-r2v-canonical-20261003-v2`; SoT A8 freezes it.

## 10. Verification results

| Check | Result |
| :-- | :-- |
| Owner-gate latch focused tests | 12 passed |
| Scene orchestrator | 18 passed |
| Reference transport (incl. preexisting_ids deltas) | 46 passed |
| Render lifecycle | 33 passed |
| Slice-0011 regression | included in full run |
| Full network-free regression (final) | **577 passed, 0 failed** (565 baseline + 12 latch) |
| Test collection audit | 577; delta = +12 latch (no removals) |
| Compile/syntax, `git diff --check` | clean |
| SoT manifest | 30/30 over post-A8 blobs (regenerated) |
| Protected-file review | SoT 13 addendum A8 only (append) + manifest hash refresh |
| Secret/PII scan on package diff | clean |

## 11. Live mutation ledger (this package)

```text
Fresh Generate authorized: 1 → consumed 1/1 (Shot 3U, job_38d4368c…, output 288910c3…)
Uploads authorized: 0 → consumed 0
Retries: 0
Direct/private MZZa6b: 0
Dead reservations during this package: 2 (3R, 3S — both verifiably never
released; superseded loudly; never re-released)
```

Historical prior-package counts (6 primary + 1 upload) remain HISTORY ONLY.

## 12. Adversarial review findings (fixed in-package)

1. `git add -A` staged unrelated untracked historical investigation tools (twice) — caught pre-commit and unstaged.
2. The re-proof builder initially referenced the FAILED 3R result and the old scene-package dir — fixed to the proven 3U result and a dedicated `scene_package_reproof_r1/` dir.
3. `write_referenced_package` correctly refused to overwrite a differing package — the superseded package is retained under a versioned name instead.
4. Mock-based profile tests needed the model-selection step's read sequence — updated to the qualified v2 flow (model selection inside the overlay).

## 13. Unresolved unknowns

1. The as29s non-null pending payload shape remains structurally uncaptured (SoT A7).
2. The maseQ upload response parser still cannot decode the current envelope (the recurring FAILED_AMBIGUOUS); read-only reconciliation remains the qualified recovery.
3. `58bd411e…` (pre-existing project image) remains permanently unreadable via as29s (environmental).
4. Semantic/visual continuity verdicts remain OWNER_REVIEW_RECOMMENDED (no qualified VLM).

## 14. Production-readiness delta

The Owner ambiguity gate is now a durable, restart-safe, one-way mutation latch with independent knowledge resolution — enforced in runner behavior and tested adversarially. The canonical Scene-003 lineage is clean under fresh authority: six shots, last-frame continuity re-proven with zero new uploads, new manifest/package/rough cut verified free of the invalidated Shot-3C lineage.
