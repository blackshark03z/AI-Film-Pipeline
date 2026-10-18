# AI-Film-Pipeline — project instructions (model/worker agnostic)

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

## Protected work
Never reset/clean/rebase/overwrite dirty mission worktrees or another Worker's current files; no source asset/journal/DPAPI or credential disclosure; no unauthorized paid Generate, publish, deploy, budget/account/proxy change, blind retry or push/merge. Only one writer per mutable scope. If no MAR/local repo access, contradictory sources or unclear consequential authority, **STOP** the affected Tech Lead decision and state precisely what could not be verified.

## Tools, scope and collaboration
Use project/native tools actually available. Codex, BMAD, Ponytail, UI UX Pro Max, Superpowers, MAR worker supervisor and external skill installation are **optional and capability/permission-gated**, never an automatic requirement for the Worker. Preserve any actual design/architecture SoT. No extra process framework, second SoT or speculative platform build.

Report the exact worktree/branch/HEAD, observed product journey, independent and Worker evidence, dirty changes protected, remaining blocker and next authorized action. Keep work moving on the Owner-approved Goal rather than reporting only tests or commits.
