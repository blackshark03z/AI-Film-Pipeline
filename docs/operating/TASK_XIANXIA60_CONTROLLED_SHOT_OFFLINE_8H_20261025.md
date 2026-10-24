# Owner-approved bounded offline Work Package — XIANXIA60 controlled-shot feasibility (up to 8h)

**Date:** 2026-10-25 Asia/Bangkok
**Status:** `FROZEN_WORK_PACKAGE / OFFLINE_ONLY / OWNER_CREATIVE_PAUSE_REMAINS`
**Owner authorization:** User requests a decision-grade research closure, implementation plan and an **up-to-eight-hour unattended Worker task**. This authorizes ONLY the minimum **isolated, local, offline research-to-prototype implementation** specified here. It does **NOT** authorize generation, uploading real media, provider/Flow/Dola account sessions, Vast.ai rental, model downloads, Blender/ComfyUI installation/execution, new budget, GitHub push/merge, film release or changes to accepted Film/Development SoTs. No assumption of future automatic progress, exact 8-hour wall time, or readiness to ship.

## Authority and exact scope

- **Root project:** `D:\AI FILM MAKER\AI-Film-Pipeline`. **Baseline before this doc:** `mission/quality-v2-022-120s@245a2883be9a3c13d3b3b96bd67372c28b0bb1fd`. If this document is later committed, use the **new verified exact HEAD** for any MAR submitted contract.
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

The Worker may finish sooner than eight hours. An asynchronous task submission does **not** establish that it will run continuously for the full duration. Task executor availability and actual status must be checked through MAR before reporting it as running.
