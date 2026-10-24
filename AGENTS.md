# AI-Film-Pipeline — project instructions (model/worker agnostic)

## One Policy — POLICY_REF preflight (Owner-approved Unified Tech Lead Standard v1.0)

**This `AGENTS.md` is the single Git-managed agent-policy entrypoint for the AI-Film-Pipeline repository.** Reuse the frozen Development/Film SoTs, `PROJECT_OPERATING_PROFILE.md` and installed Workflow Kit. Optional `.agents/` or `.opencode/` skills are adapters, never a second policy. Neither a worker report nor a branch-local copy of `AGENTS.md` can supersede the Owner-accepted policy.

`POLICY_REF` means the **full, fixed commit SHA of the Owner-accepted policy-only commit**. Supply it in ChatGPT Project Instructions and every Worker handoff; it is deliberately not a self-referential SHA inside this file. Never infer it from `HEAD`, `main`, a recent commit or an old worktree's `AGENTS.md`. If no accepted `POLICY_REF` was supplied, **STOP the affected coding/task handoff** and request the pinned revision.

**Read-only preflight, before any implementation or new task:**
1. Select the canonical Git repository, then identify worktree absolute path, branch, HEAD and dirty state. For cross-project decisions the Tech Lead uses MAR and enumerates `git worktree list --porcelain`; the assigned Worker only audits its worktree and the authoritative policy revision.
2. Verify the commit exists in the shared Git object store (`git cat-file -e <POLICY_REF>^{commit}`), then read `git show <POLICY_REF>:AGENTS.md` **from that exact commit**. Inspect its referenced Kit/SoT and the current accepted product/operating state. The caller must not trust `HEAD:AGENTS.md` merely because it is in the current branch.
3. Compare `HEAD:AGENTS.md` with `POLICY_REF:AGENTS.md` by Git blob identity and check `git status --porcelain -- AGENTS.md`; if the file is absent, diverges or has uncommitted policy edits, mark that worktree `POLICY_SYNC_REQUIRED`. Also compare any optional skill policy adapter when used. Retrieve the accepted policy read-only and resolve relevant instruction conflicts **before BUILD**, not by pretending that the old file is current.
4. New worktrees should branch from a revision already carrying accepted policy. Older worktrees require explicit reviewed reconciliation; **never automatically reset, merge, cherry-pick, overwrite or interrupt dirty Worker work to synchronize policy**. If policy/SoT/authority cannot be verified or a real conflict remains, STOP the affected task.
5. Pin the identical `POLICY_REF` in all future Worker contracts (repository/worktree/branch/HEAD, Product SoT, frozen scope/acceptance/authority/stop conditions). A Worker may change model or tool but not policy or Product Goal.

## Roles and authority
This is the root **AI-Film-Pipeline** project, NOT an isolated OneClick, Film120, AutoEdit or AutoVideoPipeline subproject. Follow the frozen six-stage AI-native workflow **SHAPE → BOUND → SLICE → BUILD → PROVE → LEARN**, and CODEX_NATIVE_WORKFLOW_KIT v1.2.2 Product Delivery Guard **as methodology, not as a mandate to run Codex**.

- **Owner:** approved product intent, trade-offs, creative acceptance, consequential external authorization.
- **Tech Lead (including ChatGPT):** SHAPE, BOUND, SLICE, independent acceptance PROVE, LEARN, canonical status/SoT stewardship and next-slice decisions.
- **Worker:** BUILD/HOW, focused technical verification and operational PROVE **only within an already frozen contract**. Worker may be OpenCode, Codex, Claude, DeepSeek or another executor; no model, runtime, skill manager or orchestrator is mandatory. Worker reports evidence and proposed truth deltas but never changes canonical acceptance, Owner intent or Product/System SoT.
- **MAR/MAR2:** Tech Lead's local project-wide **read/audit/documentation transport**, not a substitute for workflow authority or a default coding supervisor. Its calls happen when requested; it is not continuous background monitoring.

## Mandatory Tech Lead MAR bootstrap before project decisions
For a continuation, task assignment, acceptance, project-status question or material change of goal, use MAR/MAR2 to **first inventory the root project and all related worktrees**. Do not assume the most recently discussed feature branch is the project. Minimum:
1. Discover registered local projects; start from the Git root at `D:\AI FILM MAKER\AI-Film-Pipeline`; enumerate **git worktree list**, branch/HEAD/status/recent commits and protected dirty changes on each relevant worktree. Identify ancillary AutoVideoPipeline and AutoEdit repos as distinct reuse/consumer systems, not canonical Film SoT.
2. Read root `AGENTS.md`, `docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`, `docs/sot/film/00_SOT_INDEX.md`, `docs/operating/PROJECT_OPERATING_PROFILE.md`, `docs/operating/CURRENT_SLICE.md`, `docs/operating/IMPLEMENTATION_STATUS.md`, and exact latest PROVE/LEARN + source/runtime code relevant to the active slice. Cross-check the linked worktree and its exact task contract.
3. Establish the Owner-approved project/product Goal, active execution focus, frozen acceptance, actual remaining blocker, external permission and next critical-path product action. If canonical files lag or disagree, stop new handoffs and reconcile with evidence and Owner authority; do not pick a Goal from Git recency, memory or chat summary.
4. Record MAR audit findings and dated truth/status corrections **in existing operating files**, with an evidence report only when needed. Git-diff and scope-check before publishing. Never say “audited entire repo” when only paths or selected sources were read.

A Worker only needs its assigned worktree, source and frozen slice; it must **not** be forced to run MAR, Codex, OpenCode or a full multi-worktree audit. Local worker instructions may add an optional runtime adapter but cannot change the role/authority boundary.

## Canonical precedence and status
- Product/System truth: frozen `docs/sot/film/` and `docs/sot/development/` under `docs/operating/PROJECT_OPERATING_PROFILE.md`.
- **One project-level Current Slice**: root `docs/operating/CURRENT_SLICE.md`; its active worker contract may live in a separate dedicated worktree and MUST be cross-referenced at an exact branch/revision. `docs/operating/IMPLEMENTATION_STATUS.md` records active, paused, historical and independently verified status. An older worktree copy is never authority to change the project-wide Goal.
- Evidence is not a fourth canonical truth; Worker report, CI PASS, MAR status and commit HEAD alone cannot promote Product/System truth.

## Kit execution guard and handoff
Use the installed `.agents/skills/codex-techlead/SKILL.md` as an **optional v1.2.2 kit method** for the Tech Lead, not a Codex CLI requirement. Existing repo SoT, acceptance and Owner choices override kit templates. The `.opencode/skills/film-ship-first/SKILL.md` is only an optional OpenCode compatibility adapter. Other workers use their native tools.

Goal/approved milestone is the completion unit. Choose evidenced blockers on its product critical path, not an infrastructure backlog. Reuse first. BUILD uses focused tests; exact candidate uses required/full/protected checks at ship boundary; independently verify the real user journey. Separate TECHNICAL PASS, PRODUCT PASS and OWNER acceptance. Limit cost, time and ineffective retries. Do not complete a Goal from a passing unit test, milestone title or working placeholder.

Before moving slices, Tech Lead verifies Worker evidence independently, records remaining blocker and product delta in the canonical implementation state, adjudicates any legitimate truth delta and only then freezes the next slice. Worker may not edit accepted truth or acceptance merely to pass. When external state is uncertain, use INCONCLUSIVE, not guessed success.

## One Product Truth — unchanged canonical documents

Read Product/System Truth through `docs/operating/PROJECT_OPERATING_PROFILE.md` → `docs/sot/film/` and the frozen Development SoT. Read the **currently authorized ship/enablement focus, Critical User Journey, frozen acceptance, cost/safety bounds and strongest blocker** through root `docs/operating/CURRENT_SLICE.md`, with evidence-backed progress in root `docs/operating/IMPLEMENTATION_STATUS.md`. These are existing representations of the three truth classes, **not a new Product SoT or control plane**. Keep Product Goal, actual implementation, Worker technical proof, and Owner creative/release acceptance distinct.

If root operating status disagrees with an exact Worker commit/report or fresh MAR readback, record it as a **pending LEARN/reconciliation**, never silently promote Worker claims, assume the newest worktree wins or dispatch another slice on stale data. Update existing canonical state **only after** Tech Lead independent PROVE and proper Owner authority; preserve source-history sections.

## Product Progress Gate (mandatory before every next Worker task)

After receiving the Worker's exact revision/report, Tech Lead independently reads relevant evidence via MAR, then explicitly answers and records concisely in **existing `IMPLEMENTATION_STATUS.md`**:
1. **Product Delta:** Which approved end-to-end journey/ship criterion is measurably closer to completion (or unchanged)?
2. **Proof:** Which genuine runtime/provider/media or trusted verification evidence supports that claim? Distinguish TECHNICAL PASS, PRODUCT PASS and OWNER ACCEPTANCE.
3. **Main blocker:** What is the single most important evidenced obstacle to the approved ship Goal?
4. **Next choice:** Finish this journey or change to another proven critical-path blocker? The Worker can suggest, but **Tech Lead decides priority within Owner-approved scope**.

After **two consecutive cycles without evidenced Goal progress**, stop repeated unrelated hardening/refactor and reassess the approach within existing SHAPE/BOUND/SLICE; do not create a new framework or silently change the Goal. Run focused tests during BUILD; run required/full/protected verification at the actual release candidate or earlier mandated gate. A unit-test PASS or a placeholder film is not Product PASS.

## Protected work
Never reset/clean/rebase/overwrite dirty mission worktrees or another Worker's current files; no source asset/journal/DPAPI or credential disclosure; no unauthorized paid Generate, publish, deploy, budget/account/proxy change, blind retry or push/merge. Only one writer per mutable scope. If no MAR/local repo access, contradictory sources or unclear consequential authority, **STOP** the affected Tech Lead decision and state precisely what could not be verified.

## Tools, scope and collaboration
Use project/native tools actually available. Codex, BMAD, Ponytail, UI UX Pro Max, Superpowers, MAR worker supervisor and external skill installation are **optional and capability/permission-gated**, never an automatic requirement for the Worker. Preserve any actual design/architecture SoT. No extra process framework, second SoT or speculative platform build.

Report the exact worktree/branch/HEAD, observed product journey, independent and Worker evidence, dirty changes protected, remaining blocker and next authorized action. Keep work moving on the Owner-approved Goal rather than reporting only tests or commits.
