# Owner-approved bounded offline Work Package — XIANXIA60 controlled-shot feasibility (up to 8h)

## 2026-10-25 — OWNER EXECUTOR CORRECTION / ZCODE ONLY (supersedes any executor ambiguity below)

**EXECUTOR=ZCODE AGENT ONLY.** Owner explicitly selected **ZCode as coding Worker**. Earlier Tech Lead use of `mcp__MAR__submit` to run a coding worker was a **ROLE/EXECUTOR DRIFT**, not an Owner-approved choice. **DO NOT dispatch another MAR coding Worker for this slice.** Tech Lead may use MAR for read-only repo verification, Git/worktree custody and documentation but **not** as a substitute coding executor. This specific Owner choice overrides generic platform-interchangeability for this slice without changing frozen `AGENTS.md`.

**Current ZCode handoff status:** `ZCODE_READY_NOT_STARTED` as of this correction; a prepared clean dedicated worktree is **not** proof that ZCode is running. No ZCode connection, CLI or native launch operation was available in the Tech Lead's active tool session; the ZCode agent must be started using its own user-accessible execution interface, and its state confirmed before claiming `RUNNING`.

**Pre-created ZCode workspace (Tech Lead Git custody only, not Worker BUILD):**
- Worktree: `D:\AI FILM MAKER\AI-Film-Pipeline-ZCode-ControlledShot-20261025`
- Branch: `zcode/controlled-shot-v0-reproof-20261025`
- Starting HEAD: `87a2308de9b6c711cece87c02afdee12d816c39a`, clean at handoff, with pinned `AGENTS.md` blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`.
- **Provenance warning:** starting HEAD is a prior **MAR-authored candidate**, not a ZCode deliverable and **not accepted/integrated**. It comprises exactly `src/film_pipeline/creative_control/__init__.py` and `tests/test_controlled_shot_offline.py` since `22e9d8e`. ZCode must independently inspect and re-PROVE, repair discovered flaws within original scope, and own any new commits on the `zcode/` branch. Do not passively rename MAR work as ZCode work.
- Tech Lead local pytest of MAR candidate: **42/42 scoped PASS**, but MAR machine result was **`BLOCKED / UNVERIFIED / NOT_INTEGRATED`** due to missing criterion-specific oracles. Product Delta = NONE. Neither result authorizes acceptance, production or a merge.
- Root operating documentation (newer than the candidate parent) is authoritative; read current root `CURRENT_SLICE.md` and `IMPLEMENTATION_STATUS.md` without writing to them. Preserve 7 tracked modified + 175 untracked protected root paths.

**ZCode assignment:** Goal/long-running mode, optional higher reasoning, **up to 8 hours**, stop upon PASS or blocker. This is an offline *reproof/hardening of the existing candidate*, not permission for a new unrelated feature build. Same seven acceptance/stop gates in this work package apply. Owner D1–D3 are on HOLD (B multi-cut acceptance, rights/reference selection/cloud upload, explicit paid A/A+ budget and production resume).


**Date:** 2026-10-25 Asia/Bangkok
**Status:** `FROZEN_WORK_PACKAGE / OFFLINE_ONLY / OWNER_CREATIVE_PAUSE_REMAINS`
**Owner authorization:** User requests a decision-grade research closure, implementation plan and an **up-to-eight-hour unattended Worker task**. This authorizes ONLY the minimum **isolated, local, offline research-to-prototype implementation** specified here. It does **NOT** authorize generation, uploading real media, provider/Flow/Dola account sessions, Vast.ai rental, model downloads, Blender/ComfyUI installation/execution, new budget, GitHub push/merge, film release or changes to accepted Film/Development SoTs. No assumption of future automatic progress, exact 8-hour wall time, or readiness to ship.

## Authority and exact scope

- **Root project:** `D:\AI FILM MAKER\AI-Film-Pipeline`. **Baseline before this doc:** `mission/quality-v2-022-120s@245a2883be9a3c13d3b3b96bd67372c28b0bb1fd`. This is the **historical baseline before the documentation handoff**. The current ZCode worktree/HEAD is pinned by the Owner correction above; **no MAR coding-worker submission** is authorized.
- **Accepted unified policy:** `POLICY_REF=45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`, expected `AGENTS.md` Git blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`. Before BUILD, compare HEAD and frozen policy; if not matching, STOP. No edit to `AGENTS.md`.
- **SoT and status:** `docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`, `docs/sot/film/00_SOT_INDEX.md`, Film Decision Log, Operating Profile, root Current Slice and Implementation Status. **Product:** one creative-accepted 55–65s XIANXIA60 duel film, still `DEVELOPMENT=PAUSED_BY_OWNER / OWNER_CREATIVE_ACCEPTANCE=REJECTED / FILM_RELEASE=NOT_SHIPPED`. This is only a narrow authorized **offline R&D exception**, not film resumption.
- **Evidence dossier (the single research item):** `docs/research/CHINA_AI_FILM_WORKFLOWS_FOYEGE24_COMFYUI.md`, especially R8 (canonical X04 ≠ recoil diagnostic) and R10 (stage decision, owner gates). Do not copy the research into other documents or invent another SoT.
- **Protected root:** seven pre-existing tracked dirty files and 175 untracked paths at this checkpoint, including `CURRENT_SLICE.md` and `IMPLEMENTATION_STATUS.md`. DO NOT alter, stage, reset, stash, rebase or cherry-pick these root WIP items. Create a **new clean isolated git worktree/branch** from a verified policy-correct HEAD; fail closed if clean isolation impossible. Only one writer to that isolated scope.
- **Mode:** up to eight hours of bounded offline work, **stop earlier once acceptance passes**. No time-based infinite polling, provider probing, automated mutation/retries, cron loops or unattended purchases. If a blocker arises, record once and stop; no waiting for Owner to wake.

## Product problem to solve in the offline contract

X04 has **two separate targets** and no Worker may silently change canonical creative truth:

1. **Canonical X04 (film truth, do not mutate)** — read-only `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini\projects\xianxia60_nhat_kiem_pha_van\shots\X04.json`: 5s TWO_SHOT, 35mm, dolly-in first 2s then camera lock, Black's diagonal cleave vs White's raised parry, collision/pressure, White's foot slide and **sustained edge-to-edge sword lock**.
2. **Distinct motion-proof diagnostic** — frozen `docs/operating/TASK_S3_XIANXIA60_MOTION_CONTROL_OR_STOP.md`: Black right attacks, White left blocks and Black **recoils** in a ~3–5s steady shot, no orbit. **Never claim it is the canonical X04 ending**.
3. **Asset admission** — Film120 `look_development/reference_asset_ledger.json`: **5 canonical references, 0 bound**. Provisional hashed images in candidate ledger are **not** Owner-accepted references or licensed remote inputs. Strict `INPUTS_BLOCKED` until separate evidence and Owner consent.

## Implementation window and acceptance

**Allowed code** (small, reusable, additive; do not refactor existing pipeline or change frozen JSON Schemas): under a minimal new `src/film_pipeline/creative_control/` module or comparably small isolated package, implement a typed, versioned **`ControlledShotPackage-v0`**, **pure static validator**, no network side effects, and targeted unit tests. Pure Python/Pydantic/JSON already in repo; avoid large dependencies. No Blender or ComfyUI SDK required for offline preflight. The grade/budget separation may be represented as **planning metadata only**, never executable spending authority.

**Acceptance criteria (must all hold):**

1. **Canonical truth lock:** canonical X04 package references an explicit source digest, retains 5.0s collision→lock, White slide and specified camera; diagnostic recoil variant is separately named and cannot overwrite/rebind canonical. Static tests fail if variant or end-state is substituted.
2. **Fail-closed real-input gate:** missing actor/wardrobe/arena real SHA/bind, unresolved usage rights, absent actor or second sword, missing timed contact and weapon grip/path, inconsistent frame-rate/timing or unsupported control-video capability → named blocker and **zero dispatch**. No auto-promotion of candidates.
3. **API graph distinction:** separately validate/describe ComfyUI *UI save JSON* versus *API prompt JSON*; reject UI graph pretending to be executable API-format, missing typed required node inputs/model version or silently dropped control modality. **Do not convert/execute a real external graph**; pure static validation only.
4. **Grade fidelity:** B editorial multi-cut plan and A continuous plan share the canonical story beat but are never scored as same proof; A+ is a target with extra creative/QC gates, not a model label. Add small deterministic cost worksheet accepting user-entered rates and returning **unknown** when quote/credit values are not provided; no fabricated $/clip.
5. **Reproducible demonstration:** a deterministic **synthetic-only** X04 fixture can validate a *paper package*; a separate named read-only fixture for **real X04** returns `INPUTS_BLOCKED` due to 5 unbound refs. Tests never change ignored film media or current ledger.
6. **Verification:** focused new regression tests (negative and positive), existing relevant schema/continuity tests if locally available, Python syntax checks and `git diff --check`; report passed counts and any uncovered suite/CI. Commit local isolated branch only with exact changed paths/head; **no GitHub push, merge or deployment**. If tests require privileged accounts, GPU, network or media mutation, **STOP** that test rather than simulating a real provider success.

**Preferred work sequence:** Preflight & isolate → audit/reuse existing schemas → minimal typed package → static failure tests → synthetic demo → targeted regression and self-review → local commit & terminal worker report. No speculative new infrastructure, Blender scene authoring or provider adapters. No autonomous changes to acceptance or Film SoT.

## Stop conditions / Owner decisions

- **STOP immediately** if policy mismatches, root/WIP cannot be protected, privileged/missing assets tempt a fake bind, tests need external calls, feature scope expands, the single offline technical deliverable is complete, or the Worker reaches its supported time window.
- **Owner decisions after Tech Lead independent PROVE:** (1) Is a B-grade multi-cut contact/lock acceptable for X04 film; (2) which final face/robe/arena/weapon refs are approved, with rights and whether cloud upload is permitted; (3) whether to fund an A/A+ bounded Vast/ComfyUI test with exact **USD total / attempts / storage & egress / shutdown policy** and whether film production resumes. **None approved by this WP.**
- **No accepted film result:** candidate status can be `OFFLINE_CONTROL_CONTRACT_TECHNICAL_PASS` only. Real X04 remains `INPUTS_BLOCKED`; film still NOT_SHIPPED. Independent Tech Lead PROVE required before promotion into any PR and before any next creative task.

## Mandatory worker handoff (one terminal report)

`GOAL → PRODUCT DELTA → EXACT WORKTREE/BRANCH/HEAD → CHANGED PATHS → TESTS/ADVERSARIAL EVIDENCE → REAL X04 INPUTS_BLOCKED PROOF → STOP/BLOCKER → OWNER DECISIONS → NEXT RECOMMENDATION`.

ZCode may finish sooner than eight hours. A prepared worktree or handoff is not an agent launch. Confirm actual execution status through the ZCode application; otherwise report ZCODE_READY_NOT_STARTED.


---

## 2026-10-25 — Post-execution custody / independent Tech Lead PROVE (does NOT amend the frozen WP)

**MAR task:** `task-8b0b37cb1226496885913034da6e1e27`, result `result-6ec5b89c94f14f22a76498d095904f3e`, evidence `evidence-382ec0084ec34dd68d5a62377d3a8db6`. Submitted from Owner-approved policy-correct base `22e9d8eac176fbc5224a52a160d41f06ba32eb99`, local sandbox workspace `D:\MAR\.mar\w\e0ac1ab0bcfc7f328d1cdefacf519954`. MAR candidate commit `87a2308de9b6c711cece87c02afdee12d816c39a` preserved under `review/controlled-shot-v0-offline-20261025` **local only**. Branch and commit parent were independently verified; no push/merge.

**Exact candidate scope:** only `src/film_pipeline/creative_control/__init__.py` (300 lines) and `tests/test_controlled_shot_offline.py` (197 lines), additive and synthetic-only. Implements paper package, explicit canonical-lock vs recoil-variant distinction, five-ref rights/binding preflight, two actors/two swords/weapon path/contact timing, required control-video/capability checks, ComfyUI UI-versus-API JSON validation including linked typed graph inputs, separate B editorial/A continuous/A+ metadata and quote-only cost calculation. It does **not** perform any provider/job/film mutation or visual inference.

**Independent scoped PROVE:** Tech Lead invoked primary project Python against the isolated MAR workspace using `-B`, `pytest -q -p no:cacheprovider tests/test_controlled_shot_offline.py tests/test_narrative_compiler_021.py`; **42 tests PASS, zero FAIL**, with two existing Pydantic deprecation warnings. AST parsing and whitespace check on both new files PASS; `git diff --check 22e9d8e..87a2308` PASS. Git policy blob unchanged `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`; root WIP was exactly **7 tracked modified + 175 untracked** before/after. This is **scoped static/technical evidence**, not full-suite, engine, media, owner creative or release acceptance.

**MAR verifier's separate status is `BLOCKED / UNVERIFIED / NOT_INTEGRATED`**, not silently upgraded: built-in verifier executed `python -m unittest discover -v` and `python -m compileall -q .` successfully, but marked seven contract acceptance criteria `UNVERIFIED` for lack of criterion-specific scenarios/oracles. This mismatch is a **verification-profile evidence gap**, not a failing pytest assertion. A dedicated criterion/oracle verification or an independent reviewed promotion decision is required before declaring a formally accepted next BUILD slice. Task stopped early as authorized (no artificial eight-hour occupation).

**Product Delta:** NONE. All five canonical production refs remained UNBOUND; original `shots/X04.json` unchanged; film `PAUSED_BY_OWNER / CREATIVE_REJECTED / NOT_SHIPPED`. No ComfyUI/Blender install or execution, Flow/Dola/Vast session, paid GPU, rendering, media copying, service or credit charge. Decisions D1 (B multi-cut acceptable?), D2 (identity/reference rights/upload permission?) and D3 (exact capped A/A+ spend/attempts/provider and resume?) are **all still on Owner HOLD**. Do not restart film production or automatically promote code to PR #2/#3/#4.

**Next technical action:** reviewer may attach explicit criterion-specific evidence to this isolated local candidate and decide offline integration custody after independent review, without changing Owner creative truth. Next film action requires separate Owner decision.
