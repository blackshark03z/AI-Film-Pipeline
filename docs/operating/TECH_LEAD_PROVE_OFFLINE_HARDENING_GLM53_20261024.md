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

---

## PR #2 V2-021 D3 corrective review — independent PROVE (2026-10-25)

**Audit scope:** local-only Worker `fix/pr2-d3-compilation-provenance@847b2675e76b6cb81f5622061a136cf4d3948ecd` (parent `ba4c5ee08a88fea9ffdc6dca26973eba87d720e4`; same PR #2 base, but correction **not pushed** to the PR). Worker worktree `D:\AI FILM MAKER\AI-Film-Pipeline-PR2-D3-Fix` clean; exactly two changed files (`tools/run_v2_021_production.py`, `tests/test_v2_021_hardening.py`), +188/-5; `git diff --check ba4c5ee..847b267` PASS. Primary root 7 tracked dirty + 175 untracked protected paths unchanged.

**Independent test evidence:** `tests/test_v2_021_hardening.py` + `tests/test_narrative_compiler_021.py` + `tests/test_dispatch_recovery.py` run in Worker worktree via primary Python `.venv`, Python `-B`, `pytest -q -p no:cacheprovider`: **62/62 passed in 21.48s**, 2 Pydantic deprecation warnings. Only offline fakes and temporary local compilation fixtures; zero real provider interaction or spend.

**Original D3 fixed at tested boundary:** With 6-shot import-time fixture and 5-shot executed state naming a nonexistent state-selected compilation, `manifest` returns **4** (`COMPILATION_UNAVAILABLE`), fake probes=0, no manifest output; `auto` with `gate.decision=DISPATCH_AUTHORIZED` returns **4**, fake probes=0, dispatch=0. Previous PR #2 `ba4c5ee` returned success and silently wrote incorrect 6-shot manifest. Preserves pre-gate default for a new state with no recorded path.

**Two residual acceptance gaps discovered in additional adversarial probes:**
1. **P1 — re-gate probes before provenance check:** For already recorded *missing* `compilation_path` with `gate=None`, `cmd_auto` calls `cmd_gate` before `_activate_comp`. With `POOL_ACCOUNTS=['FAKE_A','FAKE_B']`, fake `_probe` and fake `_comp_for=lambda _:None`, got **rc=2, probes=2, dispatch=0**, not trust preflight rc=4/probes=0. Require preflight of recorded path before any account probe regardless of gate status; do not disable normal fresh-run planning with no recorded path.
2. **P2 — nested malformed compilation accepted:** `_load_state_compilation` accepts `shot_graph.nodes=['badnode']` when outer `shot_graph`/`prompt_plans`/`mutation_budget` are dict containers. Validate shot node dict+shot_id and required plan mapping/consumer structure with a controlled `CompilationUnavailableError`; prevent malformed data flowing into a manifest or runtime error. Add direct adversarial regression cases.

**Policy custody:** PR #2 is older than the accepted policy commit: `HEAD:AGENTS.md` blob `8026ed4a4c968153c9e4881fdf30728cc933e25e` differs from `POLICY_REF=45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`. Mark `POLICY_SYNC_REQUIRED` at the PR #2 checkout; never reconcile via unreviewed reset/cherry-pick onto dirty root. An accepted-policy-bearing clean stacked integration exists separately; don't conflate this old branch with accepted governing instructions.

**Review verdict:** `D3_ORIGINAL_REPRO_FIXED / 62_OF_62_RELEVANT_PASS / TWO_FINAL_GUARD_GAPS / PR2_NOT_MERGE_READY`. GitHub PR #2 review comment posted with exact repros, and PR #3's stale 25-vs-27 budget wording remains a distinct documentation review item. PR #4 CI is independently SUCCESS at `a899081` (87/87) but does not qualify this unpushed PR #2 correction. No PR merged; film remains `PAUSED_BY_OWNER / CREATIVE_REJECTED / NOT_SHIPPED`.

---

## 2026-10-25 — Independent PROVE of PR #2 Worker 690e2e2 (local only)

**Scope & policy:** Worker `fix/pr2-d3-compilation-provenance@690e2e21427a78b2af324534841eb79c626859d0` on `D:\AI FILM MAKER\AI-Film-Pipeline-PR2-D3-Fix`, parent `847b2675e76b6cb81f5622061a136cf4d3948ecd`, clean. Two-file change only: `tools/run_v2_021_production.py`, `tests/test_v2_021_hardening.py`, +176/-1; `git diff --check 847b267..690e2e2` PASS; both modified Python files compile. PR #2's old `AGENTS.md` blob is `8026ed4a4c968153c9e4881fdf30728cc933e25e` vs pinned Owner policy blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`: `POLICY_SYNC_REQUIRED`; governed by pinned policy read from `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`. No policy mutation.

**Independent focused regression:** `test_v2_021_hardening.py` + `test_narrative_compiler_021.py` + `test_dispatch_recovery.py` via root Python `.venv`, Worker cwd, `-B`, `pytest -q -p no:cacheprovider`: **65 passed in 27.30s**; 2 Pydantic deprecation warnings. All adversarial scenarios use temp files and fake account/provider functions, zero actual provider or credit access.

**Two assigned gaps CLOSED:** (1) `auto` with recorded missing 5-shot compilation and `gate=None`: CLI rc **4**, `COMPILATION_UNAVAILABLE`, **0 fake account probes**, **0 dispatch**, no manifest. Previously `847b267` returned rc 2 after two fake probes. (2) malformed nested `shot_graph.nodes=["badnode"]`: controlled `CompilationUnavailableError`, previously incorrectly accepted. Also checked already-authorized `auto` with missing compilation => rc 4/probes 0/dispatch 0; `manifest` => rc 4/no manifest; clean fresh `auto` without recorded path still performs expected two fake probes and gates off rc 2. `D3_ASSIGNED_GUARDS_TECHNICAL_PASS`.

**Newly quantified release-route risk: direct `gate` still bypasses these guards.** Independent CLI `main(..., "gate")` on a fake run state recording a **missing** 5-shot compilation with `gate=None`:
- With fake `POOL_ACCOUNTS=["FAKE_A","FAKE_B"]` each SESSION_INVALID and fake `_comp_for=lambda _:None`: rc **2**, **2 fake probes** (should reject before any probe).
- With a single fake SESSION_VALID account reporting 6 mock credits, fake `_comp_for` supplying a different valid 6-shot compilation: rc **0**, **1 fake probe**, `DISPATCH_AUTHORIZED`, replaced state `compilation_path` with the 6-shot file and expanded `shots` **5 -> 6**. No actual provider touched. This is concrete provenance substitution and reauthorization via a direct CLI entry point, not a theoretical style concern.

**Verdict:** `TWO_REQUESTED_CORRECTIONS_PROVEN_FIXED / 65_OF_65_PASS / DIRECT_GATE_P1_BLOCKER / PR2_NOT_MERGE_READY`. The separate direct-gate guard must validate any recorded compilation **before probe or replacement** and produce rc 4 and no state rewrite for unavailable/invalid recorded compilation; new runs without recorded path must preserve legitimate gate behavior. Add one exact fake-probe direct-gate negative and one positive fresh gate regression. PR #2 remains remote at `ba4c5ee` (this correction has **not been pushed**), and PRs #3 and #4 remain draft. GitHub PR #2 review comment posted with evidence. No push, merge, creative work, release or spending. Primary dirty WIP must remain protected; film `PAUSED_BY_OWNER / CREATIVE_REJECTED / NOT_SHIPPED`.

---

## 2026-10-25 — Independent final PROVE PR #2 D3 direct-gate correction (`3d1c89e`)

**Decision:** `D3_SCOPED_TECHNICAL_PASS`; **remote PR #2 NOT YET UPDATED / NOT MERGE-READY**. The independently reviewed three-commit correction series is `847b2675e76b6cb81f5622061a136cf4d3948ecd` → `690e2e21427a78b2af324534841eb79c626859d0` → `3d1c89eb00b7cbda6e9db44850fa50d2fe422cd9`, all on `fix/pr2-d3-compilation-provenance` in `D:\AI FILM MAKER\AI-Film-Pipeline-PR2-D3-Fix`. Final worktree clean. New commit changes only `tools/run_v2_021_production.py` and `tests/test_v2_021_hardening.py` (+126 lines); `git diff --check 690e2e2..3d1c89e` and `git diff --check ba4c5ee..3d1c89e` PASS; two files syntax compile PASS.

**Independent three-suite replay:** `tests/test_v2_021_hardening.py`, `tests/test_narrative_compiler_021.py`, `tests/test_dispatch_recovery.py` run from Worker worktree with primary project's Python `.venv`, `-B`, `pytest -q -p no:cacheprovider`: **68/68 passed in 25.02s**, two preexisting Pydantic warnings. No actual provider, account, spending, browser or film work.

**Exact fresh-process direct-gate challenge:** a fake five-shot run state with missing recorded compilation path, one fake valid account reporting six mock credits, and alternate valid six-shot `COMPS` candidate. Previously `gate` returned 0 and replaced selected compilation; at `3d1c89e` result is **CLI rc=4 / `COMPILATION_UNAVAILABLE` / zero fake account probes / original state byte-for-byte unchanged / five shots retained / no `V2_021_POOL_GATE.json` / no dispatch journals**. Malformed recorded compilation containing `shot_graph.nodes=["badnode"]` also rc=4/probes 0/original state unchanged. Positive fresh direct-gate path with *no recorded compilation* still returns rc=0 and makes one fake probe, selecting the six-shot fixture. Previous `auto`/manifest D3 cases passed and remain covered. This closes the three previously reported D3 guard findings at the tested boundary.

**External integration and policy custody remain separate gates:** GitHub PR #2 still points to `refactor/quality-v2-021-hardening@ba4c5ee08a88fea9ffdc6dca26973eba87d720e4`; corrected commits **not pushed**. PR #2 checkout's `AGENTS.md` blob remains legacy `8026ed4...`, different from Owner-pinned `POLICY_REF=45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` / `6cab2103...`: `POLICY_SYNC_REQUIRED` until reviewed reconciliation. Local root contains protected preexisting seven tracked modifications and 175 untracked paths. Before merge, review/push correction onto remote PR #2 (with policy reconciliation), observe fresh remote CI/review, then recheck downstream PR #3/#4 stack against advanced base. The existing green PR #4 CI does not validate unpushed PR #2 changes. No push, rebase, merge, CD or production authorization.

**Current product status unchanged:** `DEVELOPMENT=PAUSED_BY_OWNER`; `OWNER_CREATIVE_ACCEPTANCE=REJECTED`; `FILM_RELEASE=NOT_SHIPPED`.

---

## 2026-10-25 — PR #2 fast-forward promotion and policy reconciliation (remote; no merge)

**Remote GitHub PR #2 advanced safely:** `refactor/quality-v2-021-hardening` moved **non-force fast-forward** from `ba4c5ee08a88fea9ffdc6dca26973eba87d720e4` to `181b23aa47ebb4d1601425593059532d1ffe919d`; four commits in sequence: the independently PROVEN corrective `847b267`, `690e2e2`, `3d1c89e`, then reviewed, isolated, policy-only reconciliation commit `181b23a`. The policy blob is byte-exact `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`, read from pinned POLICY_REF `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`; it matches PR #3 and PR #4. No overwrite or migration of dirty root's existing WIP. Scope versus previous PR #2 head is precisely `AGENTS.md`, `tools/run_v2_021_production.py`, `tests/test_v2_021_hardening.py`; `git diff --check` PASS.

**Promotion proof:** clean isolated promotion checkout `D:\AI FILM MAKER\AI-Film-Pipeline-PR2-Promotion-20261025`, head `181b23a`, independent three related suites **68/68 PASS in 25.10s**, three nonblocking pre-existing warnings; D3 adversarial cases independently proven at `3d1c89e`. New policy blob verified via `git hash-object` and `git rev-parse HEAD:AGENTS.md`. GitHub PR #2 confirmed open, unmerged, remote head `181b23a`. PR review comment added with promotion evidence.

**Remaining gate, explicitly NOT complete:** no GitHub Actions workflow exists on PR #2 itself; GitHub reports **0 runs**, so PR #2 has **local focused PASS, remote CI UNVERIFIED**, not an invented CI success. PR #3 and #4 remain draft and unchanged. PR #3's old head diverges from advanced PR #2; `git merge-tree --write-tree` read-only analysis returned rc 0 (no content conflict) but branch ancestry still needs normal reviewed reconciliation before final merges. No push to PR #3/#4, merge to main, CD, production, provider visit, media render or credit spending. Film still `PAUSED_BY_OWNER / CREATIVE_REJECTED / NOT_SHIPPED`.

**Next strategic work:** Pause additional speculative code hardening; conduct a *read-only* evidence-backed comparison of the current film pipeline against concrete Chinese-language ComfyUI storyboard/reference-conditioned/multishot production workflows, then choose a bounded creative-quality experiment subject to separate Owner authorization.
