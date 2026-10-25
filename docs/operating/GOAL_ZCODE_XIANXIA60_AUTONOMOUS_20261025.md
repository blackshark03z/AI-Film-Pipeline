# ZCode Goal Mode — XIANXIA60 offline creative-control critical path

**Owner instruction:** 2026-10-25 — run a **long autonomous ZCode Goal** while Owner is unavailable, complete as much high-value work as possible, handle ordinary user-facing technical gates without human relay.
**Status at handoff:** `ZCODE_GOAL_READY_NOT_STARTED`. This document is an execution contract, **not** proof that a native ZCode session has been started.
**Policy:** `POLICY_REF=45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`; accepted `HEAD:AGENTS.md` blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`.
**Executor:** **ZCode only** (Goal / Autonomous mode, reasoning effort appropriate to difficult tasks). MAR/Tech Lead may perform read-only cross-project audit, documentation/Git evidence custody and later independent PROVE; **never substitute MAR coding Worker**.
**Maximum session:** up to **8 hours if the ZCode runtime supports it**, stop earlier at sufficient evidence, unresolvable blocker or spending/external approval boundary. No invented promise of continuous operation or background process.

## 1. Task identity and reconciled precedence

- **Clean ZCode worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-ZCode-ControlledShot-20261025`
- **Branch:** `zcode/controlled-shot-v0-reproof-20261025`
- **Starting HEAD:** `c7597b040fb5fb0792099a0a8c9b2fe1d5e43580` (ZCode R2; 106/106 scoped pytest green but additional adversarial inputs not closed).
- **Canonical root (read-only to Worker):** `D:\AI FILM MAKER\AI-Film-Pipeline`; at this Goal's preparation checkpoint `mission/quality-v2-022-120s@b63cca3435fc23ee8cee342426f6cf3bd35d8003`; root contains 7 protected tracked dirty and 175 untracked items, **not permitted to edit, stage, reset, stash or rebase**.
- **Source authority:** root `AGENTS.md`, frozen Development SoT, frozen Film SoT, `docs/operating/PROJECT_OPERATING_PROFILE.md`, root `CURRENT_SLICE.md` and `IMPLEMENTATION_STATUS.md`. Under those SoTs, original X04 is **5.0 s, TWO_SHOT, 35mm, dolly-in first 2 seconds then lock, Black attack → White parry → sustained blade lock with White foot slide**. The alternative `Black recoil` is only a separate technical motion-proof and must never replace canonical X04.
- **Earlier bounded task:** `docs/operating/TASK_XIANXIA60_CONTROLLED_SHOT_OFFLINE_8H_20261025.md` contains MAR history, ZCode R1/R2 and exact non-finite and malformed-input replays. Read it for evidence. **This new Owner-directed Goal supersedes only its narrower “STOP after validator PASS” execution limit**: continue through the optional milestones below if their inputs and safety gates pass. It **does not** supersede frozen Film/Development SoT, paused film state, no blind retries, or protected dirty work.
- **Single research dossier:** `docs/research/CHINA_AI_FILM_WORKFLOWS_FOYEGE24_COMFYUI.md` (R1–R10). Do **not** create a second research SoT or duplicate the dossier. Any new scientific/creative findings should be reported as evidence proposals for Tech Lead to append.
- **Product status still:** `DEVELOPMENT=PAUSED_BY_OWNER / OWNER_CREATIVE_ACCEPTANCE=REJECTED / FILM_RELEASE=NOT_SHIPPED`. The new Owner message opens **autonomous offline preparation only**, not a silent film release or runtime generation.

## 2. Owner's blanket approval: what it resolves and what it cannot establish

**Resolved for this unattended Goal:** ZCode may select the best small technical approach inside the constraints below, create/edit local files in its **own clean worktree**, run offline commands and tests, use preinstalled local tooling with synthetic non-proprietary geometry, make multiple **local-only scoped commits**, self-review/retry ordinary test failures, and advance sequential milestones **without requesting routine human approvals**. Reversible implementation choices and preparing experimental **B multi-cut** and **A continuous** alternative plans are approved **for comparison only**.

**Not magically established by blanket approval:** A verified licensed/Owner-accepted identity, provider reference identity, rights to a third-party Foyege/film asset, source-media cloud transfer authority, access credentials, an actual live Flow/Dola free entitlement, or a **numerical USD cost ceiling** for Vast/GPU/provider generation. No one can infer these factual facts from “all gates approved”. Accordingly use **`external_spend_cap_usd=0`**, **`provider_generation_jobs=0`**, **`external_asset_uploads=0`**, **`merge_or_push=NO`** throughout this overnight Goal. These are safe executable defaults, not a claim Owner is unwilling to pay later. No login/credits/provider experiments, Vast rental, paid models, downloads of unknown-weight/rights materials or private media generation. ZCode's already configured coding-model runtime is its own tool access, not permission to invoke film generation services.

**Allowed optional creative tool:** If Blender or an equivalent **preinstalled, already-working local tool** is available, ZCode may create and inspect a **synthetic low-poly, no-real-character, no-provider-data** offline white-box storyboard/animatic with strictly bounded local computation. Do not install, download, use actual unapproved look references or render final/photoreal film. If unavailable, make a dependency-free static pose/camera/keyframe/prop geometry description instead; **lack of Blender is not a blocker to core Goal**.

**Owner D1/D2/D3 still require real evidence:** D1 may be explored as a **B editorial pilot plan**, not predeclared film creative PASS; D2 unbound five canonical refs must stay unbound until actual provenance/right-to-use evidence exists; D3 needs a real USD cap, GPU/storage/egress/attempt limits and explicit authorization before external paid execution. Do not counterfeit these facts or silently relax the gates.

## 3. Goal: deliver the maximum defensible progress on the film's X04 action blocker

**North star:** move toward making the two-person sword **contact + sustained lock** directable and checkable **before** spending on video generation, without rewriting provider-neutral Film Core. **Do not spend eight hours polishing parser corner cases with no creative/action deliverable.** After the already observed input-boundary bugs close, prioritize a minimal, director-readable control package/previz and honest next-shot decision support.

### Milestone M1 — Close exact observed validation failures and STOP speculative hardening

**Required first.** At starting HEAD independently replay the five counterexamples listed below and add small fail-closed fixes with regression tests; no architecture rewrite:
1. `validate(replace(synthetic_x04(), refs=(1,2,3,4,5)))` must return `INPUTS_BLOCKED`, never AttributeError.
2. `validate(replace(synthetic_x04(), actors=(1,2)))` must return `INPUTS_BLOCKED`, never AttributeError.
3. `validate_comfy_api_graph(valid_synthetic_api_graph, model_revision="x", required_inputs=["ref_image","control_video"])` must fail with named invalid-typed-control blocker, not an `.issubset` exception.
4. `validate(replace(synthetic_x04(), fps=24.5))` must reject FPS because contract expects a positive **integer**, not an arbitrary finite float.
5. `estimate_cost(1e308,1e308,0,None,0,None)` must never return `ILLUSTRATIVE_ONLY, usd=inf`; handle finite-input arithmetic overflow by explicit `UNKNOWN` or structured invalid result.

**Oracle:** exactly these replays plus the 4 already pinned scoped suites, synthetic canonical and recoil positives, `PYTHONPATH=src python -B -m film_pipeline.creative_control` real-X04 read-only `INPUTS_BLOCKED` and `dispatch_count=0`, code syntax and `git diff --check`. A `PAPER_VALID_ONLY` gate **never authorizes dispatch**. Commit minimal changes locally. No third or fourth multi-hour validator rewrite if M1 is accepted. If more major bugs are independently demonstrated, fix only if they threaten the same security boundary and remain small; otherwise report them as risks, not an unbounded new task.

### Milestone M2 — Director-readable synthetic X04 action/control package

**Advance automatically after M1 technical oracle passes.** Reuse existing ShotSpec and `ControlledShotPackage` contract. Create a **minimal reproducible synthetic X04 scene description or previz source** for:
- two separate fixed actor identities labeled White-left / Black-right, one shared stage coordinate system, two *independently identified sword props* with hilt/tip and grip, no composite-identity substitution;
- timed events: Black downward attack, White upward block, first blade contact, force transfer, White slide, **sustained blade lock** by end frame;
- camera: TWO_SHOT / 35 mm, dolly-in first 2 s then fixed, stable screen direction;
- frame/time keys with exact FPS grid; no invented claim that the resulting model output will obey the geometry;
- separate, explicitly marked **`X04_MOTION_PROOF_RECOIL`** diagnostic. Recoil is NOT an edit to canonical X04.

**Smallest useful output** is an auditable time-indexed storyboard/table or JSON fixture, plus an optional *synthetic* SVG/low-poly preview source if the tool exists. One focused validation check and human-readable report suffices. Do **not** build a new 3D engine, generic scene DSL, full animation system, rigging stack, VRAM test or paid rendering pipeline. No 3rd-party reference images, film media or model downloads.

**Success is `OFFLINE_STAGING_PLAN_REPRODUCIBLE`**, not physical video contact or Owner creative PASS. If stage geometry cannot be shown using available local tools, report the exact missing modality and provide a deterministic storyboard instead.

### Milestone M3 — Make B-budget editorial vs A/A+ continuous experimental decisions concrete

**Advance automatically when M2 has a reproducible artifact.** On the **same canonical X04 event** and approved static identity placeholders, produce in the Goal's short terminal evidence report:
- **B_EDITORIAL:** 3 short acts *attack → visible blade contact insert → sustained lock and White slide* with identical left/right geography. Multi-cut is not evidence of one-take physical contact. Mark all real image and provider routes `NOT_EXECUTED`.
- **A_CONTINUOUS:** one 5-second shot with time-indexed actor/weapon contact and camera control, first/control-video inputs and exact typed conditions required to evaluate a ComfyUI graph later. Mark actual multi-actor identity handling and sword contact `UNQUALIFIED`.
- **A_PLUS:** A plus grade-specific actor-face/weapon temporal stability, film-wide shot continuity, lighting/sound/editorial finishing, not merely a higher GPU.
- **Economics:** a *parameterized*, no-invented-quote breakdown for rate × compute, model load, storage, egress, credits, human prep, wasted attempts and QC; cost/accepted beat `UNKNOWN` until real trial and quote. Show which missing evidence prevents purchasing/routing.
- **Existing reality:** Five canonical reference IDs still `UNBOUND`; even hashed candidate images cannot become licensed/Owner-accepted or provider-bound by inference. Propose exact future Owner review checklist, not actual promotion.

Do not create a new SoT or an encyclopedia report. One compact, evidence-backed comparison kept in the Worker terminal handoff, with any single useful on-disk synthetic artifact from M2, is sufficient.

### Milestone M4 — Optional practical reuse / integration feasibility (ONLY if M1–M3 actually finish)

**Optional, bounded and reversible:** compare the synthetic package to existing frozen ShotSpec and observed Wan2.2 `ref_image` + `control_video` API inputs. If a small missing type/manifest interface prevents a feasible future integration, propose it with exact tests but **do not build a ComfyUI or Vast adapter and do not change frozen SoT or schemas**. Check whether a local side-effect-free integration surface already exists; **reuse first**. If this optional milestone becomes speculative infrastructure, **STOP** and report `FUTURE_OWNER_DECISION`.

## 4. Agent-level autonomy and stop conditions

ZCode chooses the HOW inside these bounded milestones. It may run repeated **local** BUILD/TEST/FIX cycles without pinging Owner; one local commit per meaningful milestone is desirable for custody. Do not create multiple competing worktrees, spawn other coding agents, delegate to MAR, push, merge or rewrite canonical docs. The Tech Lead (not ZCode) later independent-PROVEs each new exact SHA and updates project status.

**Continue while:** each milestone directly increases evidenced film-action feasibility and is safe/offline within the scope and elapsed time. **Stop when:** (i) all bounded milestones complete; (ii) two consecutive cycles fail to produce useful acceptance evidence; (iii) new work would just be repetitive validator hardening or unrelated PR/backlog work; (iv) source/rights/identity uncertainty needs real external authority; (v) account/payment, third-party asset transfer, provider generation, software installation/download or irreversible state would be required; (vi) policy conflict/dirty worktree/unapproved external effect; or (vii) the ZCode runtime reaches the agreed **up-to-8-hour** window. Do not fill the clock. Don't claim `SHIPPED` or `PASS` from synthetic success.

**No user relay:** all routine choices within M1–M4 are delegated to ZCode. When blocked, do not ask a sleeping Owner to answer a form or keep checking; record one evidence-based blocker and stop. Separate Owner creative/rights/paid gates remain factual conditions, not routine questions.

## 5. Required one-message terminal ZCode handoff

`GOAL → FINISHED MILESTONES [M1/M2/M3/M4] → EXACT WORKTREE/BRANCH/COMMIT CHAIN → CHANGED PATHS → GIT/TESTS + COUNTEREXAMPLE REPLAYS → X04 CANONICAL VS RECOIL + 5 UNBOUND REF STATUS → B/A/A+ FEASIBILITY/COST UNKNOWN → DRIFT/OVER-ENGINEERING REVIEW → PRODUCT DELTA (if any) → BLOCKED EXTERNAL GATES → NEXT SAFE OWNER CHOICE`.

Every delivered milestone must state **observed vs inferred**, product-facing gain vs merely technical hygiene, and stop reason. Do not claim Goal mode ever launched unless ZCode itself confirms execution, nor claim one ZCode report equals independent Tech Lead acceptance.

## 6. Native ZCode start facts (Tech Lead inspection, no background promise)

On the preparation machine, `C:\Users\ADMIN\AppData\Local\Programs\ZCode\ZCode.exe` is installed, and `C:\Users\ADMIN\.zcode` exists. **No documented callable Goal-task CLI / app connector / remote task trigger was exposed by the available tools.** **Official ZCode native launch:** Open ZCode desktop, **open this exact ZCode worktree as the workspace**, select the regular ZCode Agent (not Plan mode), choose **Full access** execution mode for unattended local file/tests within the authority in section 2, and send `/goal Hoàn thành M1→M2→M3→M4 theo D:\\AI FILM MAKER\\AI-Film-Pipeline\\docs\\operating\\GOAL_ZCODE_XIANXIA60_AUTONOMOUS_20261025.md; tự BUILD/TEST/FIX/PROVE và local commit, không yêu cầu relay; dừng khi hết scope, tối đa tám giờ, hoặc gặp external/rights/spend blocker; chỉ nộp một terminal report.` The official Goal documentation states `/goal <objective>` continues through multiple verification rounds and stops when the goal is met/paused or its configured usage budget is exhausted; **verify the Goal card is active before sleeping**. The official Agent documentation confirms Full access reduces confirmations. Native ZCode UI execution, not opening the desktop process alone, creates the task; **record `ZCODE_GOAL_READY_NOT_STARTED` until an active Goal card/task is observed**. No documented, callable headless Goal launch API/connector is exposed in this tool session. Official references: https://zcode.z.ai/en/docs/goal and https://zcode.z.ai/en/docs/agents. **Never dispatch MAR coding worker to simulate ZCode**.

**Single source for this new Goal's authority and acceptance:** this file; the previous ControlledShot task is historical evidence. Research continues only in the pre-existing single dossier after Tech Lead review.
