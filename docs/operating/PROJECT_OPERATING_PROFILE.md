# Project Operating Profile — AI Film Pipeline

## 2026-10-25 — Decision and operating precedence checkpoint

**Research index:** [Foyege24 / Chinese ComfyUI workflow audit](../research/CHINA_AI_FILM_WORKFLOWS_FOYEGE24_COMFYUI.md) is the one living evidence dossier; it is not a new SoT and grants no BUILD permission.

1. **Canonical precedence:** The dated current header of root `CURRENT_SLICE.md` governs project status; `IMPLEMENTATION_STATUS.md` records independently verified product progress, while this profile binds them to frozen Film/Development SoTs. Older `ACTIVE`, `PRODUCT PASS` and `MASTER SHIPPED` passages remain historical technical/Worker evidence, not Owner creative or release acceptance. This is not a fourth truth or new lifecycle.
2. **Owner Pause persists:** `DEVELOPMENT=PAUSED_BY_OWNER / OWNER_CREATIVE_ACCEPTANCE=REJECTED / FILM_RELEASE=NOT_SHIPPED`; the main blocker is convincing two-person sword contact with persistent actor identity, shot geometry, eyelines and choreography. No further provider sessions, generation, credit spend, recut, CD or deployment absent separate explicit Owner resume.
3. **Engineering exact evidence:** PR #2 remote head `181b23aa47ebb4d1601425593059532d1ffe919d` received three independently PROVEN D3 fail-closed commits and a policy-only commit matching pinned `AGENTS.md` blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`. Independent local promotion focused tests 68/68 PASS; GitHub Actions at this PR #2 head **NOT VERIFIED**. PR #3 remains draft `cc2edc9`; PR #4 draft `a899081`, with its own clean-checkout GitHub Actions 87/87 PASS (only that head). None merged to `main`.
4. **Custody:** Preserve original primary checkout 7 tracked dirty and 175 untracked paths. Do not rebase/reset/stash/overwrite those WIP files or automatically incorporate worktree evidence. PR #3 old cap-25 text versus executable/historic 27-budget lineage requires evidence reconciliation, NOT renewed spending authorization.
5. **Next sequence:** Finish documentary and PR/CI review gates, stop speculative code hardening, then conduct Owner-requested **read-only comparative study** of ComfyUI workflows before proposing any new build. ComfyUI remains deferred in V1 by default; no engine/model selection or production resume is yet approved.

---

**Status:** FROZEN FOR V1 EXECUTION  
**Governing lifecycle:** AI-Native Development Model SoT v1  
**Product/System SoT:** AI Film Pipeline V1 SoT

## 1. Purpose

This file binds the generic AI-Native Development Model to this repository.

It is not a new lifecycle layer.

## 2. Canonical truth mapping

### PRODUCT TRUTH
Primarily represented by:
- Film SoT `01_SCOPE_AND_PRINCIPLES.md`
- Film SoT `03_CINEMATIC_CONTROL_SPEC.md`
- Film SoT `09_EDITORIAL_FLOW.md`
- Film SoT `10_VERTICAL_SLICE_BENCHMARK.md`

Product truth includes:
- coherent film sequence over isolated pretty clips;
- continuity-aware AI generation;
- cinematic/directorial intent;
- practical cost/quality balance;
- ability to replace generation providers.

### SYSTEM TRUTH
Primarily represented by:
- Film SoT `00_SOT_INDEX.md`
- Film SoT `02_CANONICAL_DOMAIN_MODEL.md`
- Film SoT `04_SHOTSPEC_V1.md`
- Film SoT `05_PROMPT_COMPILER.md`
- Film SoT `06_PROVIDER_CAPABILITIES.md`
- Film SoT `07_ROUTING_REPAIR_QC.md`
- Film SoT `08_ASSET_LINEAGE_COST.md`
- JSON Schemas under `/schemas`

Hard invariants include:
- ShotSpec / Film State is canonical; provider prompts are derived.
- Continuity is explicit data.
- Creative state is separated from runtime/provider state.
- Provider transports are replaceable adapters.
- Browser/cookie state never enters Film Core.
- Exact GenerationAttempt → ProviderJob → Asset lineage is required.
- No blind retry except genuinely transient transport retry.
- Filesystem + JSON/SQLite is the V1 persistence baseline.
- DaVinci Resolve remains finishing truth.
- Model IDs/pricing/capabilities are runtime config/evidence, not Film IR.

### CURRENT SLICE
Represented only by:
- `CURRENT_SLICE.md`

The worker may not redefine acceptance inside an attempt.

## 3. Role mapping

### Owner
Owns:
- product intent;
- real quality/cost trade-offs;
- subjective film acceptance;
- consequential external authorization.

### Tech Lead
Owns:
- SHAPE/BOUND/SLICE;
- preserving SoT;
- acceptance semantics;
- proof custody;
- deciding whether evidence warrants a truth delta.

### Worker
Owns:
- implementation HOW inside Current Slice;
- code structure;
- local refactoring;
- local tests;
- replaceable library choices;
- internal progression through pre-authorized gates.

### Trusted Verification
May be:
- protected tests/checks;
- exact revision identity;
- GitHub branch protection/CI;
- provider readback;
- manually reviewed evidence outside candidate authority.

## 4. Work style

Default:
- larger bounded work packages;
- fewer manual relays;
- worker self-progresses through internal gates;
- stop only at meaningful boundary or authority requirement.

Worker SHOULD search/reuse before building:
`SEARCH → REUSE → COMPOSE → ADAPT → EXTEND → BUILD LAST`

Existing `AutoVideoPipeline` is a reuse/reference source for Flow/Veo and media mechanics, not the canonical architecture.

## 5. V1 implementation posture

Prefer:
- Python;
- Pydantic;
- JSON Schema;
- SQLite;
- filesystem;
- CLI;
- FFmpeg;
- provider adapters.

Do NOT introduce by default:
- Postgres;
- Redis;
- Temporal;
- S3;
- Kubernetes;
- microservices;
- complex web UI;
- local Stable Diffusion / ComfyUI;
- Blender/Unreal;
- fine-tuning;
- custom orchestration framework.

Any deferred component requires measured evidence of need.

## 6. Provider reality

Available practical execution paths:
- Gemini API.
- Google Flow / Veo.
- Seedance via Dola.
- Seedance via Elyum.
- ChatGPT Plus / Codex for development and difficult interactive reasoning.

Browser/cookie automation is allowed only behind provider adapters.

## 7. Stop conditions

Worker must stop when:
- owner product decision is required;
- a new external authority is required;
- external state is ambiguous and cannot be reconciled safely;
- a frozen hard invariant would need changing;
- live/consequential action was not pre-authorized;
- secrets or account access are required and unavailable;
- package scope must materially change;
- no-progress/retry limit is reached.

## 8. Change control

If implementation evidence challenges SoT:
1. do not silently change SoT;
2. record evidence;
3. return to LEARN;
4. Tech Lead adjudicates Product/System Truth delta;
5. create a new slice if required.

## 9. Multi-worktree truth, interchangeable worker and MAR (2026-10-18 integration rule)

These are **operating interpretations of the frozen lifecycle**, not a fourth truth type or a new process.

1. **Whole-project view:** Root `CURRENT_SLICE.md` and `IMPLEMENTATION_STATUS.md` are project-level canonical operating references. A subproject/worktree has its own implementation/attempt evidence, but it is not automatically the entire project's current Goal. Historical copies and completed/paused activities must be explicitly distinguished.
2. **Role invariant across runtimes:** The Tech Lead owns SHAPE → BOUND → SLICE, independent acceptance PROVE, LEARN and canonical state promotion. Worker owns BUILD/HOW and operational PROVE within an immutable accepted task. Worker can be OpenCode, Codex, Claude, DeepSeek or another agent. Platform-specific kit skills are optional adapters; never require a Worker to run a named model or orchestrator.
3. **Tech Lead MAR source-of-evidence:** For project continuation, progress assessment, task selection, acceptance and cross-worktree changes, use MAR/MAR2 to read the local **root Git repository plus all relevant linked worktrees**, branch/HEAD/status/diff, SoT, frozen task contracts and newest evidence. The root-plus-worktree inventory is required before using any child branch as project-wide status. Treat snapshot results as observations, not Product Truth.
4. **Canonical update protocol:** Worker sends an exact revision/candidate and facts. Tech Lead independently verifies frozen acceptance, inspects any truth delta, **updates existing project state and remaining blockers**, and only then creates/revises the next root Current Slice. A worker must never edit Product/System Truth or acceptance to make its own candidate pass. Reconcile contradictory root/worktree states before task dispatch. Preserve historical evidence rather than rewriting prior outcome.
5. **No concurrent write collision:** A current Worker owns its isolated worktree. Tech Lead edits only its scoped operating documentation in the root with Git-status/path/hash checks and must not alter the Worker's branch or dirty mission files while a run is active. Promote results across branches/worktrees only via explicit reviewed integration, never silently by assuming the latest branch is canonical.
6. **Kit policy:** Apply `CODEX_NATIVE_WORKFLOW_KIT` manifest version 1.2.2 as role-neutral methodology: approved Goal is exit unit; product-first, reuse-first, risk-specific/ship-boundary proof; finite time/retry/no-progress; technical, product and Owner acceptance separately. Its Codex/BMAD/Ponytail/UI-UX/Superpowers-specific tooling is optional and requires actual host capability and permission. Existing Film/Development SoTs outrank all kit templates.

**MAR is not background monitoring:** it supplies read/audit/documentation on Tech Lead invocation. No daemon, remote push, deploy or new governance framework is implied.

### Historical tool handoff — OpenCode / DeepSeek V4.1 Flash (Owner direction, 2026-10-18; superseded for next WP)

For the **currently approved S1 Dola OneClick continuation only**, the Owner selects **OpenCode running DeepSeek V4.1 Flash** as the coding Worker. The Tech Lead prepares the bounded Work Package in the relevant Git worktree and hands the Owner a **copy-ready prompt relay** for that OpenCode session. **Do not dispatch an MAR worker task** or change this into an MAR-managed agent. MAR is reserved for Tech Lead's repo-wide inspection, scope-checked file/document writes and independent readback; it is not the Worker executor.

This is an **execution adapter choice**, not a replacement policy, new SoT, changed Goal or compulsory future Worker model. `POLICY_REF=45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` remains the sole accepted agent policy; the Worker independently runs its Git policy preflight before BUILD. The frozen S1 A1–A8 contract still wins; Chrome cookie capture/login and GPM live launches require explicit Owner action. Tech Lead owns the final Product Progress Gate and acceptance. For a subsequent Worker change, update only the bounded handoff, not the pinned policy.

### Current NEXT Worker routing — Gemini (Owner direction, 2026-10-19)

Owner reports the **OpenCode quota is exhausted** and explicitly chooses **Gemini** as the Worker for the **next necessary BUILD task / WP**. The execution host/interface and exact Gemini model variant are **not yet specified**; do not assume Gemini CLI, API, OpenCode-internal runtime, extra account connection or spending authorization. In the next frozen WP and Owner relay, name the selected Gemini surface only after it is available and agreed. The previous OpenCode/DeepSeek Flash handoffs remain historical evidence at their exact Git revisions; **no retrofit to completed Worker reports**.

**Authority unchanged:** Owner controls creative/release decisions and any external cost/account action. Tech Lead uses MAR for repo policy/SoT inspection, scoped documents and independent PROVE, and sends a copy-ready WP relay; **do not use MAR submit/task to run Gemini as coding Worker**. Gemini owns only BUILD/HOW and operational PROVE in a bounded authorized WP. Keep the fixed `POLICY_REF=45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`, frozen Film Product Goal, root Current Slice, owner assets, dirty `opencode.json` and mission WIP unchanged. The completed S2 `LOCAL_SHIP_PACKAGE_READY` milestone alone does not justify creating another Worker task or publicly releasing the film.

**Relay size preference (Owner direction, 2026-10-19):** For subsequent genuinely necessary Worker tasks, freeze **one larger cohesive product-oriented WP** with consecutive internally bounded BUILD → focused PROVE → candidate-media/QC → ONE final delivery report, so the Owner does not need to relay each ordinary technical gate. Broad execution **does not expand paid provider/account rights**: allow only the explicitly approved exact per-shot attempt/cost ceiling; stop at actual paid-cost uncertainty, Owner-only identity/session/capture, missing real mutation authority or creative acceptance gate. No new orchestration layer, duplicate Worker or routine progress-update relays.

**Durable FREE-POOL quota decision (Owner 2026-10-19, superseding earlier manual-confirmation asks):** Owner explicitly directs **"Cứ thử đi hỏi lắm thế, ghi quyết định bền vững: không hỏi lại về qouta, dùng hết thì mới hỏi"**. Operational default for **future individually authorized free-route shot WPs**: let Worker choose among existing eligible, non-deferred provider pool accounts itself, use current trusted evidence, and **do not ask Owner merely because remaining free video credit is UNKNOWN**. An *expressly shot/attempt-bounded* WP may authorize **one free-route trial with UNKNOWN remaining quota** when the no-paid/no-auto-purchase route, user/account eligibility, durable no-replay guard and isolated evidence writes are genuinely established. After any video release, **no retry/switching account on receipt ambiguity**. Never turn UNKNOWN into a false EXHAUSTED status; distinguish provider-confirmed exhaustion from credit unobservable. **Ask Owner about quota replenishment/budget only when all permitted eligible free-pool routes are actually confirmed exhausted** and a new consequential decision is required; report other genuine independent Owner-only gates accurately, not as quota questions. This is **not** a standing authorization for unlimited shot generation, paid use, new accounts, login/credential transfer, changed Goal, rotation into hard-blocked/deferred profiles, or bypassing AGENTS.md policy. Capture this preference in every appropriate future WP without repeatedly seeking the same quota approval.
