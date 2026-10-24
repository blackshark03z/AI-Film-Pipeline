# OFFLINE HARDENING — GLM 5.3 WORKER REPORT (2026-10-24)

**WP:** `docs/operating/TASK_OFFLINE_HARDENING_GLM53_RESUME_READINESS_20261024.md`
**Worker branch:** `feature/offline-hardening-glm53-20261024`
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Offline-Hardening-GLM53` (isolated, created from task commit `e363eb5f39617d7654ffbf86acc2f802c6fb02b3`)
**Commits (this WP only, no push/merge):**

- `d9d0718ef25d24d401ddcab8fc02067884f7c3ed` — A1+A2+A3 fail-closed bootstrap, transient-failure classification, budget provenance, tests
- `e3d449d182ad118adb15c1649d6cb4a31feb31ef` — B1 pydantic fix, B2 CI workflow, B3 dev extra
- `995a935c98b7c336d9eb2c633a5c5bdbaf63f2fb` — fresh-checkout import fix for `run_scene_scale_003.py`
- (a fourth commit adds this report file)

**Policy preflight (VERIFIED):** `git cat-file -e 45f71d6226c5ffc58b4e70f3bcea1bb0151b7003^{commit}` OK; policy blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` identical at POLICY_REF and task HEAD; `AGENTS.md` clean. Frozen SoTs read at HEAD (`AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`, `00_SOT_INDEX.md`, `PROJECT_OPERATING_PROFILE.md`, committed `CURRENT_SLICE.md`/`IMPLEMENTATION_STATUS.md` headers = 2026-10-22 Owner Pause).

**Status of the film (unchanged by this WP):** `DEVELOPMENT=PAUSED_BY_OWNER`, `OWNER_CREATIVE_ACCEPTANCE=REJECTED`, `FILM_RELEASE=NOT_SHIPPED`. Everything below is **TECHNICAL_VERIFIED** engineering only. No provider/account/credit access occurred; no media touched; primary root left byte-identical (verified `git status` unchanged before/after).

---

## Changed files (exact paths, branch diff vs e363eb5)

| File | Change |
|---|---|
| `tools/run_v2_022_production.py` | A1/A3: lazy fail-closed compilation bootstrap; state/compilation agreement; docstring budget lineage |
| `tools/v2_020_runner.py` | A2: `TRANSIENT_FAILURE_MARKERS` + `classify_recent_failure()` wired into the real dispatch control flow |
| `tools/v2_021_recover.py` | A2 mirror (`transient_failure` in scan) + A1-class lazy compilation (no more import crash) |
| `tools/run_scene_scale_003.py` | A1-class: lazy `reference_binding.json` load (3 test files were uncollectable in fresh checkouts) |
| `src/film_pipeline/narrative/narrative.py` | B1: `type(before).model_fields` (instance access deprecated) |
| `tests/test_v2_022_compilation.py` | namespace test now uses a deterministic NON-AUTHORITATIVE builder sample; budget docstring 25→27 lineage; transient marker-priority test |
| `tests/test_v2_022_fresh_checkout_bootstrap.py` | NEW — 10 fresh-checkout bootstrap/agreement tests |
| `tests/test_v2_022_transient_failure.py` | NEW — 8 tests incl. 4 exercising the real `dispatch_and_acquire` control flow with scripted fake provider surfaces |
| `.github/workflows/ci.yml` | NEW — minimal offline CI (B2) |
| `pyproject.toml` | B3: `dev` extra (`pytest>=8,<10`) |

10 files, 885 insertions, 39 deletions. `git diff --check` clean at every commit.

## What was implemented, by lane

### A1 — Fail-closed missing-compilation bootstrap — IMPLEMENTED + TESTED
- Import no longer reads the Git-ignored `projects/quality_v2_022_longform_120s/V2_022_LONGFORM_COMPILATION.json`: `COMP`/`BUDGET` load lazily via `load_compilation()` with structural validation (missing / unreadable / invalid JSON / missing keys / nodes-vs-planned_shots mismatch all raise informative `CompilationUnavailableError`).
- `gate`/`auto` refuse with exit code 4 and a `COMPILATION_UNAVAILABLE` emit **before any account probe or dispatch** (zero provider access when design authority is missing). Fresh state init requires the compilation; **status on an existing run and CLI help work compilation-free**.
- Deterministic builder output may substitute via `V2_022_COMPILATION` for read-only simulation/tests — strictly NON-AUTHORITATIVE for spend (documented in error text, docstrings, tests).
- Fresh-checkout defect also fixed in `v2_021_recover.py` (import crash) and `run_scene_scale_003.py` (3 test files could not even be collected at the task commit).

### A2 — Dola transient-failure classification — IMPLEMENTED + TESTED (live integration BLOCKED by Owner pause, by design)
- Provider message "動画を生成できません。今回の生成でクレジットは使用されませんでした。" contains the generic refusal marker `生成できません`; `classify_recent_failure()` classifies it **before** refusal (returns `TRANSIENT_GENERATION_FAILURE_NO_CREDIT`), wired into the actual `dispatch_and_acquire` discovery loop → `STOPPED_PROVIDER_GENERATION_FAILED_NO_CREDIT`.
- Conservation guarantees (tested): the latched release is accounted exactly once (`on_release` fired before failing — budget never silently rolled back on the provider's **provisional** no-credit claim); journal evidence preserved; latched journal blocks a second paid mutation (no auto-retry); a completed creation next to failure text is a SUCCESS; ambiguous rows stop at the strictly bounded poll window (`poll_seconds=0` proof: zero discovery polls).
- `v2_021_recover.scan` now reports `transient_failure` alongside `refusal` for read-only reconciliation.
- The dirty primary-root WIP (`tools/v2_020_runner.py`, `tools/v2_021_recover.py`, `tests/test_v2_022_compilation.py`) was read as reference only; this branch contains an independent, convergent implementation (same marker, same error status string, plus the classifier function, fresh-checkout bootstrap and control-flow tests the WIP lacks). Nothing was copied over or overwritten.

### A3 — Budget provenance — IMPLEMENTED + TESTED
- Evidence chain for **27**: builder rationale (`tools/build_v2_022_compilation.py`: cap 25 = 24+1 reserve → 26 for day-1 refusals S03/S08 → 27 when S09 DECISION also refused; version `v2-022-mutation-budget-v3` with `total_budget != 27` hard-stop) + the live runtime artifact in the primary root (read-only check this WP: `v3`, total 27, planned 24, 24 nodes) + tests asserting 27. Stale "cap 25" docstrings in the runner and test module reconciled to the dated lineage.
- `_activate_comp` now enforces run-state ↔ compilation agreement (fixture identity, `planned_shots`, gate `computed_budget`); a recorded compilation that vanished refuses instead of silently substituting the default (V2-021 manifest-defect class). Docstrings explicitly noted as never being spend permission.

### B1 — Pydantic deprecation — IMPLEMENTED + TESTED
`narrative.py` `WorldStateGraph.delta` uses `type(before).model_fields`. Focused suites: **96 warnings → 0**, same passes.

### B2 — Offline CI — IMPLEMENTED, LOCALLY EQUIVALENT-TESTED (NOT yet run on GitHub)
`.github/workflows/ci.yml`: windows-latest (the Dola session layer imports `ctypes.wintypes` at import time), Python 3.11, `pip install -e .[dev]`, `compileall`, tracked-source trailing-whitespace guard (correctly inverted `git grep` logic with `shell: bash`), and the fresh-checkout-safe focused suites. **Locally executed equivalents:** compileall OK; whitespace guard OK (0 findings in tracked `.py`/`.md`); focused pytest **76/76**. CI on GitHub requires a push, which this WP forbids — first real run belongs to Tech Lead.

### B3 — Dependency reproducibility — PARTIALLY IMPLEMENTED, lockfile DEFERRED
Added tracked `dev` extra (`pytest>=8,<10`); runtime ranges verified installed-compatible (pydantic 2.13.5, jsonschema 4.26.0, pytest 9.1.1; `pip install --dry-run -e .[dev]` resolves). **Deferred:** committing any lockfile — root `uv.lock` is untracked, protected and owned by the primary root; generating one in the worktree risks embedding private index config and conflicting with that file. Next action (Tech Lead): deliberately generate and commit a lockfile from a reviewed, public-index-only environment, or adopt `pip install -e .[dev]` + CI as the reproducibility baseline.

### B4 — Git hygiene — IMPLEMENTED
All Worker commits `git diff --check`-clean; committed tree has **0 trailing-whitespace findings** in `.py`/`.md` (the 3 MAR findings live only in the protected primary dirty files, untouched). No new ignore rules needed (test side-effects land in `tmp_path`; `.pytest_cache`/`__pycache__` already ignored). Secret-path audit (names only, nothing opened): **0 tracked files** match key/cookie/token/secret/credential/password patterns; `.gitignore` covers `.env`, `*.cookie`, `api_keys/`, `secrets/`, `*session*.json`.

---

## Test evidence (exact commands and outcomes)

All in the isolated worktree, `PYTHONPATH=src`, offline:

1. Three MAR-audit suites `python -m pytest tests/test_v2_022_compilation.py tests/test_v2_021_hardening.py tests/test_dispatch_recovery.py -q`:
   - task commit baseline (fresh checkout): **3 failed / 48 passed** (import-time FileNotFoundError — the A1 defect)
   - after this WP: **52 passed, 0 failed, 0 warnings** (MAR's 52/52 baseline now holds in a clean checkout)
2. Focused set incl. new suites (also the CI command): `pytest tests/test_v2_022_compilation.py tests/test_v2_022_fresh_checkout_bootstrap.py tests/test_v2_022_transient_failure.py tests/test_v2_021_hardening.py tests/test_dispatch_recovery.py tests/test_v2_022_account_routing.py -q` → **76 passed** (25 new tests; `test_v2_022_account_routing.py` was previously un-runnable in a fresh checkout).
3. Full offline suite (bounded, `timeout 540`): **1241 passed, 122 failed, 62 errors, 3 warnings in ~170s**. Classification of the 184 failure/error detail lines: **180 = FileNotFoundError on Git-ignored `projects/*` runtime artifacts** (fresh-checkout environmental limitation, pre-existing), 2 sqlite-artifact (same class), 2 assertion failures — `test_semantic_identity_019.py::test_05` shells out to `uv run` (environmental) and one `v2_010a` invariant in the same file family that fails at base too. **Base-commit comparison** (detached temp worktree at `e363eb5`, removed after): the same non-environmental failures exist at base, plus `test_semantic_identity_019.py` could not be collected at all at base. **Net delta of this WP on the full suite: strictly non-negative** (3 committed-tree failures fixed, 1 test file unblocked, 1239→1241 passed). No regression introduced; full-suite pass is NOT claimed.
4. `python -m compileall -q src tools tests` → OK. Import simulation blocking `playwright`/`patchright`/`PIL` → all CI-relevant modules import (CI does not need the `flow` extra).

**Known limitations:** CI not yet run on GitHub (no push authorized); `v2_021_recover`/`run_scene_scale_003` fixes are proven by import + unit tests, not against the real ignored artifacts (absent by design here); the transient classifier is verified against the verbatim day-1 provider message only — further live phrasings need the future authorized resume.

---

## C1 — Proposed primary-root header reconciliation — TECH_LEAD_REVIEW_REQUIRED (NOT applied)

Fact pattern (read-only): the dirty working copies of `docs/operating/CURRENT_SLICE.md` (+41 lines) and `docs/operating/IMPLEMENTATION_STATUS.md` (+62 lines) put the **2026-10-21** "3-SHOT QUALIFICATION STOP (15/30 remaining)" state on top, overwriting the **committed 2026-10-22 Owner Pause** headers. Committed files remain authority (pause is newer and Owner-ordered). Proposed minimal patch for a future Tech Lead commit — restore the pause header ABOVE the 10-21 text, keeping every historic line (the 10-21 content is genuine chronology and stays, tagged superseded):

```
# CURRENT SLICE — S3 XIANXIA60 / OWNER-PAUSED — NOT SHIPPED

**2026-10-22 — AUTHORITATIVE OWNER PAUSE (supersedes the 2026-10-21
qualification-stop entries below; their 15/30 envelope and balance
claims are historical, NOT current spend authorization):**
[re-insert the exact committed 2026-10-22 header block from
 mission/quality-v2-022-120s@e363eb5 docs/operating/CURRENT_SLICE.md]

---

[existing dirty 2026-10-21 content follows unchanged below this line]
```

Same shape for `IMPLEMENTATION_STATUS.md` (re-insert committed `## 2026-10-22 — OWNER PAUSE CLOSEOUT / TECH LEAD INDEPENDENT PROVE` section above the dirty `## 2026-10-21` section). Worker did NOT touch the primary root; this proposal creates no new truth.

## C2 — Media custody / resume-readiness audit (read-only, names/hashes only)

- **Ignored runtime corpus:** 54 project dirs under primary `projects/*` (Git-ignored by design) — includes `quality_v2_020/021/022_*` journals/run state and the flow production history. None committed; none deleted/moved this WP.
- **V2-022 frozen runtime compilation** (primary root, read-only hash): `projects/quality_v2_022_longform_120s/V2_022_LONGFORM_COMPILATION.json` SHA256 `4ab2d7e3e8778f959832583d4bc0356060e04a2a3a5aa249eb8fc7f7e18497db`, `mutation_budget v3` total 27 / planned 24 / 24 nodes — matches builder + tests (A3 chain closed).
- **Untracked review media:** primary `OWNER_REVIEW/` holds 7 top-level packets (V2_002…V2_021, `DOLA_COMBAT_RHYTHM_REVIEW_PACKET`, `DOLA_SPATIAL_BLOCKING_REVIEW_PACKET`, `XIANXIA60_CONTINUITY_WORKPRINT_V3`) — local-only.
- **Checksummed closeout evidence:** Worker closeout report EXISTS at `feature/film120-gemini-realshot-001:docs/operating/S3_XIANXIA60_PAUSE_CLOSEOUT_REPORT.md` (independently verified ledger SHAs per committed IMPLEMENTATION_STATUS 2026-10-22 entry; "19 physically identified video outputs / 30-output envelope").
- **No offsite-backup assumption:** per committed pause header, absence of the root review path at independent PROVE means backups must NOT be inferred from file existence.

**Resume-custody checklist (for Tech Lead at any future resume gate):**
1. `git status --porcelain` primary root — the 7 tracked-modified + untracked set must still match the 2026-10-24 inventory (this WP changed nothing there).
2. Re-hash the V2-022 compilation (`4ab2d7e3…97db`) and spot-re-hash 2–3 ledger-listed Dola videos against the film120 closeout report SHAs.
3. Confirm the 54 `projects/*` dirs and `OWNER_REVIEW/` packets still exist with unchanged top-level names; count media files, don't open them.
4. Re-verify POLICY_REF blob `6cab2103…` and that both operating docs' committed HEAD still carry the 2026-10-22 pause header.
5. Only then: explicit Owner resume → new slice; never auto-restart.

## C3 — PR integration recommendation

- Do **not** touch PR #2 (`refactor/quality-v2-021-hardening` → main) or stacked draft PR #3 (`mission/quality-v2-022-120s` → PR #2). Land this Worker branch **after** those, by rebase/cherry-pick onto the then-current `mission/quality-v2-022-120s`, because `tools/v2_020_runner.py`, `tools/v2_021_recover.py` and `tests/test_v2_022_compilation.py` overlap the primary root's dirty WIP (convergent, not conflicting, semantics — expect a small reviewed merge favoring this branch's classifier + tests).
- **Rollback:** branch is additive; `git revert` of the three commits (or simply not merging) restores prior behavior; no migration, no state files, no remote effects. The only intentional behavior changes are fail-closed (missing/mismatched compilation now refuses instead of crashing or silently rebinding).
- This branch is **not automatically integrated** anywhere; `main` at `ecaa129c` and both PRs are untouched.

---

## GOAL → PRODUCT DELTA → PROOF → RISK → NEXT ACTION

- **GOAL (WP):** maximum safe offline hardening + resume readiness. **Met within scope.**
- **PRODUCT DELTA (engineering only):** fresh-checkout reproducibility restored (52/52 + 76/76 focused, 0 warnings), fail-closed authority gates around the frozen compilation, transient-failure classification with latched-budget conservation, first tracked CI definition, custody/lineage evidence recorded. Film progress: **none intended** — product remains `PAUSED_BY_OWNER / CREATIVE_REJECTED / NOT_SHIPPED`.
- **PROOF:** commit SHAs + commands/counts above; **TECHNICAL_VERIFIED** only. **PRODUCT_ACCEPTANCE: unchanged REJECTED; FILM_RELEASE: NOT SHIPPED.**
- **RISK/DEFERRED:** CI unrun on GitHub; lockfile deferred (B3); recover/scene-scale lazy fixes not exercised against real artifacts; further live transient phrasings need authorized resume; full suite still environmentally blocked in clean checkouts (180 missing-artifact tests — inherent to ignored runtime data, listed for awareness, not fixed by design).
- **TECH LEAD NEXT ACTION:** independently PROVE this branch in the isolated worktree (`PYTHONPATH=src python -m pytest tests/test_v2_022_compilation.py tests/test_v2_022_fresh_checkout_bootstrap.py tests/test_v2_022_transient_failure.py tests/test_v2_021_hardening.py tests/test_dispatch_recovery.py tests/test_v2_022_account_routing.py -q`), review the C1 header patch for a canonical reconciliation commit, decide the lockfile policy (B3), and only then schedule the first push/CI run.
