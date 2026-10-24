# Tech Lead independent PROVE — GLM 5.3 Offline Hardening (2026-10-24)

**Decision:** `FOCUSED_TESTS_VERIFIED / CORRECTIVE_REVIEW_REQUIRED / NOT_INTEGRATION_READY`.
**Product state unchanged:** `DEVELOPMENT=PAUSED_BY_OWNER`, `OWNER_CREATIVE_ACCEPTANCE=REJECTED`, `FILM_RELEASE=NOT_SHIPPED`. This document is evidence and a bounded QA correction for existing WP `TASK_OFFLINE_HARDENING_GLM53_RESUME_READINESS_20261024.md`, **not** a second SoT or authorization to resume any provider/media work.

## Scope and exact revisions

- Primary root: `D:\AI FILM MAKER\AI-Film-Pipeline`, `mission/quality-v2-022-120s@e363eb5f39617d7654ffbf86acc2f802c6fb02b3` before this independent PROVE report commit, with **7 tracked modified and 175 untracked entries preserved**; no primary dirty file was edited, staged or removed.
- Worker: `D:\AI FILM MAKER\AI-Film-Pipeline-Offline-Hardening-GLM53`, branch `feature/offline-hardening-glm53-20261024@00eb887b14fab32f90c46c967e859563a5e098d8`, worktree clean. Four commits: `d9d0718`, `e3d449d`, `995a935`, `00eb887`.
- Independent `git diff --stat e363eb5..feature/offline-hardening-glm53-20261024`: **11 changed paths, 1,017 insertions / 39 deletions** (Worker report's 10/885 omits its own final report). `git diff --check`: exit 0. Worker tree `AGENTS.md` Git blob matches pinned POLICY_REF blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`.
- Independent targeted test run: from Worker worktree using Python from the primary project's `.venv`, `python -B -m pytest -q -p no:cacheprovider` with `PYTHONPATH=src` effect set in-process, files `test_v2_022_compilation.py`, `test_v2_022_fresh_checkout_bootstrap.py`, `test_v2_022_transient_failure.py`, `test_v2_021_hardening.py`, `test_dispatch_recovery.py`, `test_v2_022_account_routing.py`: **76 passed in 28.38s; exit 0**. No live network/provider calls. Git whitespace check against Worker tracked `.py/.md`: zero matches.
- Worker reports bounded full suite **1241 passed / 122 failed / 62 errors**, with majority missing Git-ignored runtime artifacts. This full-suite outcome/classification was **not independently replayed** in this PROVE. New CI workflow is **not yet run on GitHub**; do not claim green CI or full regression acceptance.

## Independent offline defects requiring correction before integration

### P1 — Frozen compilation content is not cryptographically bound

`tools/run_v2_022_production.py::load_compilation` validates only shape, and `_activate_comp` checks `fixture_id`, `planned_shots` and gate budget, not the actual compilation content SHA-256. In a local `tempfile.TemporaryDirectory` with a structurally valid test fixture, independent PROVE changed `prompt_plans.S01.compiled_text` from `ORIGINAL` to `ALTERED`, keeping state identity/count/budget constant; `_activate_comp` **accepted the modified prompt**. This fails the WP's integrity-check objective; do not mistake a state path/metadata match for frozen design attestation.

**Corrective acceptance:** persist and verify full-file SHA-256 tied to a trusted, already-authorized run evidence source (or explicit `UNVERIFIED/AUTHORITY_REQUIRED` stop for legacy state), including the gate-to-auto-to-manifest boundary and fresh process. Do **not** silently pin arbitrary current bytes, treat a regenerated sample as paid-generation authorization, rewrite legacy runtime artifacts, or change the Owner-authorized budget. Add offline tamper tests proving prompt mutation with unchanged identity/budget is rejected. Existing running state must fail closed if trustworthy digest is unavailable; provide a read-only migration/report path, not auto-rebind.

### P2 — Malformed nested type throws the wrong exception

Calling `load_compilation` with `shot_graph: ["invalid-shape"]` (other required keys present) raises raw `AttributeError: 'list' object has no attribute 'get'` at nested `.get`, not the intended `CompilationUnavailableError`. Independently reproduced with a temporary JSON file, zero paid/remote work.

**Corrective acceptance:** type-check nested `shot_graph`, `prompt_plans`, budget fields and shot IDs before indexing; route malformed data through the documented fail-closed error/CLI exit code 4. Add regression tests for wrong container types, not just missing fields.

### P1 — Recovery scan enters session path before artifact preflight

In `tools/v2_021_recover.py::scan`, `_open(alias)` executes before `_shot_ids()` loads the ignored required compilation. Independently reproduced with a **fake async `_open`** (no actual provider): with `RECOVER_COMPILATION` pointing to an absent temporary file, `scan(["DUMMY_ACCOUNT"])` still called fake session-open once before reporting compilation missing. The exception is caught and an error record written in temporary storage; no real account/session was accessed.

**Corrective acceptance:** validate required compilation and shot ID plan **before calling `_open`, browser eval or account/session read**, fail closed with a clear error/result, preserve current read-only recovery behavior when valid, and test ordering with fake `_open` asserting zero session opens on missing/malformed compilation. No provider access in testing.

## Integration gate / next step

- Keep existing Worker branch `feature/offline-hardening-glm53-20261024`; execute **one narrowly scoped corrective pass on that same isolated Worker worktree**, addressing the three findings, with targeted tests and exact commit(s), no remote push/merge/rebase.
- Existing root WIP overlaps `tools/v2_020_runner.py`, `tools/v2_021_recover.py`, `tests/test_v2_022_compilation.py`; do not cherry-pick into dirty primary checkout. Later integration requires independent diff conflict resolution in a clean worktree after Owner/Tech Lead decides the dirty WIP custody and confirms PR #2/#3 topology.
- After corrections Tech Lead reruns focused suites, tamper/type/session-order probes and `git diff --check`. Only after independent PASS should integration/CI first push be considered via explicit review. `uv.lock` remains untracked/protected and lockfile policy deferred.
- **No video Generate, editing, provider session, credit spend, publication or creative acceptance change is authorized.** The XIANXIA60 film-critical blocker remains two-actor controlled martial contact/geometry/identity; offline CI and test PASS do not resolve it.

**Product Progress Gate:** Product delta = engineering safety improvement only, not film progress; proof = targeted 76/76 plus independent adversarial probes; main blocker = three identified pre-integration hardening gaps (engineering) and unqualified two-person controlled combat (film); next choice = finish in-scope corrective verification, then Tech Lead decides integration and requests separate explicit Owner authorization before any film production resumes.

---

## Addendum — Independent corrective PROVE of Worker `470e8af` (2026-10-25)

**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Offline-Hardening-GLM53`, `feature/offline-hardening-glm53-20261024@470e8aff8ad468eb4a792cfc416ffa2cee4740dc`, clean; accepted policy blob still `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`. Root is `mission/quality-v2-022-120s@7dbb89fd0c606ce6ac260a79a69b9d352b0b0c8a` before this addendum commit, with 7 tracked dirty + 175 untracked unchanged. Worker's correction changed 4 files, +599/-46, `git diff --check 00eb887..470e8af` exit 0.

**Independent tests:** six prior offline suites in Worker worktree via primary `.venv`, `PYTHONPATH=src` equivalent, Python `-B`, `pytest -q -p no:cacheprovider`: **85 passed, 0 failed in 24.47s**. Three original adverse cases independently re-executed in a temporary isolated directory: (a) modify `prompt_plans.S01.compiled_text` after state digest pin, metadata unchanged: `CompilationUnavailableError: compilation integrity failure` (FIXED); (b) `shot_graph` as list: documented `CompilationUnavailableError` instead of `AttributeError` (FIXED); (c) absent `RECOVER_COMPILATION` with a fake async `_open`: `RECOVERY_PREFLIGHT_FAILED` return 1, **zero fake session opens** (FIXED). These are offline checks only: no actual provider call.

**Additional adversarial findings, not covered by the nine corrective tests:**

1. **P1 — trust preflight before any account probe is still missing:** with a structurally valid compilation, no `V2_022_COMPILATION_SHA256` or sidecar, and a fake `_probe` returning a valid session/30 credits, `cmd_gate()` returned `STOP_COMPILATION_TRUST_MISSING` (rc 2) **only after calling fake `_probe` once**. Guard the trust digest *before entering the `POOL_ACCOUNTS` probe loop*, ideally before state/gate mutation, while preserving the existing diagnostic `verify` path. This is required to avoid touching provider/account sessions when spend authority provenance is already insufficient. Test `_probe` is not called on missing/mismatched anchor; valid anchor may proceed into a fake probe.
2. **P2 — malformed budget field type accepted:** with a structurally complete temp compilation but `mutation_budget.total_budget = ["list"]`, `load_compilation` returned successfully; this bypasses the documented malformed-compilation fail-closed validation. Require `total_budget` and `planned_shots` to be positive **integers excluding bool**, `rule` to be a nonblank string, and maintain `total_budget >= planned_shots` as appropriate; reject wrong types and missing values through `CompilationUnavailableError`. Add adversarial regression cases for list/string/negative/bool/zero and nested invalid fields. No change to the actual approved budget or provider behavior is authorized.

**Verdict:** `THREE_ORIGINAL_PROVE_FINDINGS_FIXED / 85_OF_85_FOCUSED_PASS / TWO_FRESH_GUARD_GAPS / STILL_NOT_INTEGRATION_READY`. The requested three corrective tasks are accepted at the tested boundary, but paid-runner hardening is not fully closed. Execute one **small final source-only Worker correction** to the two findings above; no CI push, no provider access, no dirty root edits or product resumption. Do not repeat the environmental full suite merely to inflate progress: rerun the focused tests and direct negative cases, report exact output. If one fails, mark the precise residual risk instead of another speculative refactor. Additional iteration requires product-progress reassessment per the project policy.

---

## Final independent PROVE — Worker `30257f2` (2026-10-25)

**Final decision:** `OFFLINE_HARDENING_TECHNICAL_PASS` for the specifically authorized Worker workpackage; `INTEGRATION_PENDING`, `GITHUB_CI_UNVERIFIED`, `FULL_SUITE_NOT_GREEN`, `FILM_PAUSED_BY_OWNER`. Supersedes the *open engineering gap* verdicts above, without altering historical observations.

- Worker: `feature/offline-hardening-glm53-20261024@30257f26a6e545a3e13adc3ab9135c2e788cccae` in `D:\AI FILM MAKER\AI-Film-Pipeline-Offline-Hardening-GLM53`, clean; `HEAD:AGENTS.md` blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221` matches pinned policy. Latest correction is exactly 2 files (`tools/run_v2_022_production.py`, `tests/test_v2_022_fresh_checkout_bootstrap.py`), +182/-3; total Worker delta from WP base touches 11 paths.
- Independent six focused suites run read-only under the primary project's Python `.venv` but executing in Worker worktree with `PYTHONPATH=src` equivalent, Python `-B`, `pytest -q -p no:cacheprovider`: **87 passed / 0 failed in 24.79s**. These focused tests include new trust-preflight and strict budget-negative tests. `git diff --check e363eb5..feature/offline-hardening-glm53-20261024`: exit 0; 4 affected Python files compiled via built-in `compile()`: PASS, tracked `.py`/`.md` trailing-whitespace grep: zero matches.
- Independently replayed with temporary local compilation and fake `_probe` (zero actual provider/account access): absent trust anchor `STOP_COMPILATION_TRUST_MISSING` rc 2 **probes=0**; mismatched anchor `STOP_COMPILATION_TRUST_MISMATCH` rc 2 **probes=0**; matched anchor allowed fake probe and gate `DISPATCH_AUTHORIZED`. This proves ordering, not live spend authority or readiness.
- Independently tested malformed budget samples: `total_budget` list/bool/float/negative, `planned_shots=0`, `total_budget < planned_shots` and blank `rule` all raised `CompilationUnavailableError`. Worker test file covers additional string/range cases. Earlier three findings (full-file prompt digest tamper, nested container exceptions, recovery session preflight) were independently confirmed fixed at Worker `470e8af` and remain covered by passing focused suite.
- **Product Progress Gate:** measurable delta = testable offline fail-closed state/provenance safety plus CI definition, not film footage. Proof = exact Worker commits and offline regression/adversarial cases. Film-critical blocker remains unqualified two-person sword action with maintained actor identity/geometry. No film release or Owner creative change. No authorized video generate, account/session visit, credit spending or provider test.
- **Integration remains separate:** primary root `mission/quality-v2-022-120s` retains 7 preexisting tracked dirty files and 175 untracked paths; conflicting WIP includes `tools/v2_020_runner.py`, `tools/v2_021_recover.py` and `tests/test_v2_022_compilation.py`. **Do not merge/cherry-pick into dirty primary root.** Review/prioritize protected WIP, PR #2 and stacked #3 in a clean isolated integration worktree, preserve Owner Pause and policy, run clean-checkout CI only after an explicitly reviewed GitHub push. Private `uv.lock` remains a deferred lockfile decision.
- The Worker-reported full-suite outcome at an earlier revision was **1241 passed, 122 failed, 62 errors**, largely due to unavailable ignored `projects/*` runtime evidence. Not independently rerun here; no full-suite pass claim. GitHub Actions workflow exists on Worker branch but is not proven to have run remotely.

**Close this OFFLINE hardening Worker package at TECHNICAL_PASS rather than inventing another refactor loop.** Next meaningful engineering action is integration conflict/custody resolution and a real CI run; separate explicit Owner resume and a new film critical-path decision are required for production. All code remains on the Worker branch until reviewed integration.
