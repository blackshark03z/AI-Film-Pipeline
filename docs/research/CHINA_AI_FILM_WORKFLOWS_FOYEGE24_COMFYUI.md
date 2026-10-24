# Research dossier — Chinese AI-film workflows, Foyege24 & ComfyUI

**Opened:** 2026-10-25 (Asia/Bangkok)
**Status:** `RESEARCH_EVIDENCE_ONLY / ARCHITECTURE_NOT_APPROVED / NO_RENDER`
**Scope:** One **living research item** for successive research rounds and audit. **Not a new SoT** or authorization.
**Owner authority:** Desk research, public read-only source inspection, internal architecture audit and future proposal. No ComfyUI installation, model/file downloads into the project, GPU inference, provider browser/session work, paid generation, media recut, merge, CD or release.
**Product status:** `DEVELOPMENT=PAUSED_BY_OWNER / OWNER_CREATIVE_ACCEPTANCE=REJECTED / FILM_RELEASE=NOT_SHIPPED`.
**Canonical pointers (unchanged authority):** `docs/sot/film/12_DECISION_LOG.md`; `docs/operating/PROJECT_OPERATING_PROFILE.md`; `docs/operating/CURRENT_SLICE.md`; `docs/operating/IMPLEMENTATION_STATUS.md`; frozen `docs/sot/film/00_SOT_INDEX.md` and Development SoT.
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`; Owner-pinned `AGENTS.md` Git blob `6cab2103e32448a10e13b7f00c1a3eb4adb4a221`.

## 0. Evidence labels and research protocol

- **S — Creator/official primary source:** Verified page authored by creator or Comfy-Org official documentation. It describes a workflow, **not** an independently reproduced outcome.
- **G — Public graph reviewed:** Actual versioned, inspectable GitHub ComfyUI JSON; static graph inspection does **not** imply downloaded weights or executable graph PASS.
- **R — Repository self-description:** Public third-party README about use/quality/environment, not independently run.
- **L — Local evidence:** Read-only exact local source and independently recorded Tech Lead QA/CI. Not a fresh full-suite or film acceptance.
- **H — Hypothesis/option:** Requires a comparable experiment. Never promote to Product/System SoT based only on a video demo, a README, node inventory or marketing promise.

Source snapshot URLs and dates are recorded below; public projects can change after this date. Record subsequent rounds **in this file**, not duplicate research summaries across operating docs. Those docs should only link here and carry a current authority/status line.

## 1. Round R1 — Foyege24 (弗曳哥), 2026-10-25

### Primary-source observations

| Source | Publicly visible claim | Evidence / limitation |
| --- | --- | --- |
| [F1: GPT-6 Astra + Blender camera white-box (Sep 8)](https://www.bilibili.com/video/BV1Hhb56JE4P/) | Creator-posted workflow description combines AI prompts and Blender previsualization to achieve cinematic camera movement. | S: title/byline verified; **no original Blender project or process execution audited**. |
| [F2: White-box + Blender tutorial (Sep 11)](https://www.bilibili.com/video/BV1GPYj6nEo3/) | Creator describes using white-box models for AI-video shot control, with Seedance in related descriptions. | S: creator-posted educational video; **not proof that ComfyUI is the orchestration platform**. |
| [F3: Seedance performance tutorial (Aug 8)](https://www.bilibili.com/video/BV1jLug6LEgp/) | Describes breaking acting into expression, dialogue, pause and turn-taking. | S: public tutorial theme; video content and exact prompt recipe not independently replayed. |
| [F4: 《新生》 (Oct 3)](https://www.bilibili.com/video/BV18kaS6zEt5/) | Creator says 300+ storyboard shots, ~80% white-box-assisted. | S: **creator claim**, not an audited shot-by-shot production ledger. |
| [F5: Harry Potter/Malfoy fan-film post (Oct 20)](https://www.bilibili.com/video/BV1bKnw6zEsV/) | Public finished-media example attributed to same creator. | S: visual/output reference only; does not expose exact workflow or licenses of reused IP. |

**Working interpretation (H):** Foyege24's relevant *method* is explicit camera/blocking previsualization and separately directed performance before generative video. That could address the current XIANXIA spatial/action issue better than adding prose to a single text prompt. Do **not** assert Foyege24 is a ComfyUI-first producer: **no creator-authenticated ComfyUI graph JSON was established in this round**. Also do not extrapolate the creator's reported credit usage or success ratio to our costs.

**Follow-up research:** seek original white-box files, published prompt packs, shot breakdowns, creator-authenticated reusable workflows or actual making-of segments. Check attribution and licensing before reusing assets. Mark missing artifacts **UNVERIFIED**, not “not existing”.

## 2. Round R2 — Inspectable Chinese ComfyUI and official controlled-video references

| Evidence | Verified artifact | Relevance to XIANXIA | Qualification |
| --- | --- | --- | --- |
| [C1: Comfy-Org Wan2.2 Fun Control graph JSON](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_fun_control.json) | **G:** GitHub `Comfy-Org/workflow_templates`, blob `98a010d7b157f6d93025fccc447633600f781122`; statically inspected **44 top-level nodes / 50 links** including `Wan22FunControlToVideo`, `LoadVideo`, `Canny`, `KSamplerAdvanced`, `SaveVideo`. | Real reference for control video → generation with explicit inputs and outputs. | Graph shape only; model weights, input control media and runtime not installed/tested. |
| [C2: Comfy-Org official Fun Control guide](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/wan/wan2-2-fun-control.mdx) | **S:** Documents OpenPose/depth/Canny/trajectory controls, start frame, high/low-noise models, optional 4-step LoRA. **Published comparison** on 4090D 24 GB/640²/81 frames gives ~524s vs ~138s first run. | Supports conditioning beyond prompt, useful for planned collision paths. | Published tutorial benchmark **not our measured GPU/time**; quality and two-person contact not established. |
| [C3: Comfy-Org overview](https://blog.comfy.org/p/comfyui-wan22-fun-inp-support) | **S:** Distinguishes first-last-frame Fun InP and pose/depth/trajectory Fun Control. | Separates temporal boundary control from action control. | Neither alone guarantees identity or contact correctness. |
| [C4: qiukaihui/comfyui-auto-drama](https://github.com/qiukaihui/comfyui-auto-drama) | **R:** Chinese demo/teaching repository: script → reference actor sheets/scene/storyboards → remote ComfyUI H3 R2V → auto-QC → finishing. [Example graph](https://github.com/qiukaihui/comfyui-auto-drama/blob/main/workflows/video_minimax_h3_i2v_uncensored_enhancer.json) **G**, blob `1ed15d3b6fae4ca38728b48491a1b8a86f0c4ce0`, **7 top-level nodes / 5 top-level links**, some functionality appears in subgraph/custom node. | Actual reference packaging, four-view character sheets, chaining workflow. | **Do not infer total internal node complexity from 7 top-level nodes; not run, demo repository self-described.** |
| [C5: mxbr111/ai-manju-pipeline](https://github.com/mxbr111/ai-manju-pipeline) | **R:** Chinese open-source animated-short production pipeline describing cloud ComfyUI, image character sheets, H3 Ref2VA/LTX alternatives, voice/audio, frame chaining and acceptance; [README blob](https://github.com/mxbr111/ai-manju-pipeline/blob/main/README.md) `c311a49cfe10e41fdcdd01294d7aca25c5e4f936`. | Separates orchestration, reference assembly, multi-engine selection and finishing. | Author claims AutoDL operational workflow and suggests substantial VRAM; **not independently reproduced or guaranteed production quality**. |

**Cross-source lessons, not acceptance claims:** (a) manage reusable image/reference assets early; (b) use actual control video/pose/depth/trajectory or white-box previz where text-only motion fails; (c) store graph revision, node-package versions, weights and inputs per attempt; (d) close the loop with local QC and finishing; (e) separate provider capability assertions from current grounded measurements. **ComfyUI UI graph JSON is not necessarily the server API prompt JSON**; design a conversion/validation boundary only if a later Owner-approved adapter is built.

**Out-of-scope assumptions rejected:** “Chinese masters all use ComfyUI”; “Foyege24 uses this graph”; “pose graph ensures two-blade contact”; “local inference is cheaper/faster”; “GitHub stars/README prove shot acceptance”; “demo quality transfers to our GPU, cast or rights”.

## 2.1 Round R2b — Static graph edge-level check (same research item)

**Wan2.2 official graph, Git blob `98a010d7...`:** two `Wan22FunControlToVideo` nodes expose connected **`ref_image: IMAGE`** and **`control_video: IMAGE`** inputs, plus positive/negative conditioning and VAE; each example has widgets `640 × 640, 81 frames`. Two branches use `KSamplerAdvanced` with **4 vs 20 steps**, Canny preprocessing and separate `SaveVideo` outputs. These are two alternative example paths, **not two independently proven actor streams**. Core graph is 44 top-level nodes/50 links; no nested `definitions.subgraphs` were found. The graph contains **no explicit 3D sword-collision solver or guarantee of physical contact**. API prompt format/export and package execution remain unverified.

**Chinese H3 example, Git blob `1ed15d3...`:** 7 top-level nodes/5 links, **one nested graph with 22 internal nodes**, including `MiniMaxH3GenerationTailLoader`, `SamplerCustomAdvanced`, audio/video decoding and `CreateVideo`. The top-level `LoadImage`, `ResolutionSelector` and `SaveVideo` are visible. **7 top-level nodes is not a claim that the workflow has 7 processing operations**. Rights, dependencies, H3 weights, engine availability and API conversion are not qualified.

**Contract implication (hypothesis):** A future adapter should version and fingerprint (i) graph/API prompt JSON, (ii) custom node and model manifests, (iii) reference-image assets and control-video frames, and (iv) exact output media/job lineage. Reject absent required conditioning inputs rather than silently downgrading to unconditioned output. This is **a design note, not an approved BUILD task**.

## 3. Round R3 — Read-only audit of our code, canonical status and evidence

**Repository snapshot:** primary `D:\AI FILM MAKER\AI-Film-Pipeline`, branch `mission/quality-v2-022-120s@3f6110cbddab04f617386b798cc10ff923999aaf` at research preflight; 7 protected tracked modifications and 175 untracked paths preserved. Pinned `AGENTS.md` matches `6cab2103...`. The audit inspects selected schemas/transport interfaces/SoT and prior Tech Lead PROVE reports; **not** an exhaustive file-by-file code review, fresh provider session, GPU benchmark or full test-suite claim.

| Domain | Observed local evidence | Verdict / implication |
| --- | --- | --- |
| Film authoring / truth | `src/film_pipeline/core.py`: `ShotSpec`, `CharacterRef`, `Camera`, `Blocking`, `Continuity`, `PerformanceSpec`, `ActionIntent` and schema validation. | **KEEP:** Film IR/continuity identities are provider-neutral and valuable. |
| Spatial/action representation | `Blocking.start/action_beats/end` and `PerformanceSpec.contact_event` are mainly narrative strings; `Camera` describes lens/movement intent, not tracked 3D transforms/occlusion/contact/actor coordinates. | **GAP:** director intent exists but is not an executable two-actor geometry/pose/contact constraint for model inputs. |
| Capability negotiation | `ProviderCapabilities` has T2V, image, first/end, multi-reference, seed, audio, duration, size flags; no explicit pose/depth/trajectory/control-video/white-box/versioned-graph capability in this reviewed class. | **GAP:** condition input modality/version/required refs need a fail-closed contract in a future additive adapter. |
| Provider separation | `src/film_pipeline/providers/base.py`: `VideoProvider` defines capabilities, preflight, submit/poll/fetch/cancel. Flow/Dola/Elyum adapters exist. | **KEEP:** adapter boundary; do not replace entire Film Core with ComfyUI. |
| Provenance/operational durability | PR #2 remote `181b23a` with independently verified D3 correction, 68/68 clean-promotion focused tests; PR #4 `a899081` GitHub CI 87/87 for its tested revision. | **KEEP and finish gating:** PR #2 current-head GitHub CI unverified; PR #3/#4 draft, stack unmerged; no full-suite green claim. |
| Actual action quality | Canonical 2026-10-22 Owner Pause: prior masters/workprint REJECTED; two actors fail readable sword contact + identity/spatial continuity; five canonical identity refs UNBOUND. | **MAIN PRODUCT BLOCKER**; no technical test count changes Owner acceptance. |
| Workflow cost/control | Frozen Film Decision Log DR-009 defers ComfyUI by default; profile requires measured evidence before new component; provider spend and video outputs under current Owner Pause zero. | **KEEP default / COMPARE FIRST:** candidate engine or creative control layer is not yet approved. |

**What is obsolete vs intact:** The overall canonical architecture is **not proven obsolete**. The current *execution method for complex physical interactions* is under-qualified: natural-language blocking and prompt-first generation did not produce acceptable two-person choreography. Audit provides no evidence that simply upgrading model version or routing more accounts would solve that failure.

## 4. Three-way decision register for the next discussion (not SoT change)

| Decision | Classification | Basis / condition |
| --- | --- | --- |
| Film State, ShotSpec, character/shot IDs, continuity, lineage, at-most-once dispatch, QC, local-first data, editor/Resolve finishing | **KEEP** | Frozen SoT, core schema and safety evidence. |
| Previsualization output: performer/prop/camera geometry, timed contact and recoil, actor anchors; identity sheets and reference validation; frame/control-video provenance | **CANDIDATE CHANGE** | Directly addresses evidenced two-person action failure. Design additive contracts; do not edit frozen schema before benchmark/Owner review. |
| ComfyUI as *replaceable* generation/conditioning adapter; Wan2.2 Fun Control, H3, other models; Blender white-box or cloud-to-video conditioning | **BENCHMARK ONLY** | Real public artifacts exist but no local two-actor quality, GPU, cost or licensing qualification. |
| Rewriting orchestration, switching all engines, copying proprietary creator assets/prompts, opening provider/credits | **NOT APPROVED** | No measured advantage and no Owner permission. |

**Likely direction to discuss (H):** retain canonical Film Core as conductor, add a *previsualization/controlled-shot package* between ShotSpec and provider adapters; start with whichever reference/pose/white-box modality actually reproduces the desired X04 collision. A graph UI is a replaceable tool, not creative truth.

## 5. Proposed *design only* bounded A/B benchmark: X04 blade-clash

**Same spec and fair constraints for every candidate:** X04 from rejected qualification evidence; fixed two characters and references, one arena, two readable blade paths with **visible contact, timed recoil, no actor disappearance**, consistent screen direction, start/end geography. Predefine start frame, key contact frame and recovery beat. Preserve original failed baseline as **historical comparison**, not a fresh paid rerun.

| Candidate | Preparation method (not executed) | Risk to check |
| --- | --- | --- |
| A — historical text/Flow baseline | Reuse already recorded X04 evidence (no new Generate) | Prior frozen/static/far-apart motion failure. |
| B — white-box previz → conditioned engine | Geometry and camera set in a static Blender/white-box storyboard or animatic; image/video conditioning when truly supported. | Control not faithfully propagated; identity drift; tool prep overhead. |
| C — ComfyUI conditioned video | Version-pinned Fun Control/OpenPose/depth/trajectory JSON with approved rights and cast/control inputs. | Blade geometry still nonphysical; graph dependency and VRAM cost; inability to bind identity and pose together. |
| D — editorial decomposition fallback | Attack motion, contact insert, defender recoil assembled as coherent action beat. | Perceived cheats, eyeline discontinuity and editorial cost. |

**Suggested acceptance rubric before any paid test:** unambiguous blade-to-blade contact; actor IDs remain stable; consistent distance/screen direction; observable force transfer/recoil; cuttable timing; no invented hands/weapons; correct lineage; elapsed GPU/provider time, actual attempts, cost, user QC verdict. A single anecdotal success is a candidate, not a statistically established success rate. Decide sample size and hard stop/spend cap **only after Owner approval**.

**Explicit stop:** Research may read public pages/code. No ComfyUI installation, CUDA/model download, private workflow/weights, graph execution, local or remote video generation, provider/browser session, credits, film edit/release or architecture SoT mutation is authorized by this dossier.

## 6. Next research rounds to append here only

- **R4 — Foyege24 provenance:** If original white-box/project/prompt archives are located, record creator link, rights, revision, file type, available keyframes and independently inspectable sequence; if not, maintain `UNVERIFIED`.
- **R5 — remaining graph contract audit:** the initial node-level review is recorded in R2b; next inspect how UI JSON maps to validated API prompt payloads and how missing conditioning inputs/custom node/weight revisions would be refused. Do not execute graphs.
- **R6 — local matching audit:** map X04 ShotSpec references, geometry and existing QC failure taxonomy into a hypothetical `ControlledShotPackage` contract, **without implementation**; quantify gap coverage and blockers.
- **Decision meeting:** Tech Lead presents concrete alternatives and unknowns to Owner. Owner alone selects a new BUILD slice, benchmark spend, engine and any production resumption.

---

**Change discipline:** Each new round edits this one dossier and updates its evidence ledger; operating/SoT files hold **only a short pointer** and relevant authority status. Do not invent separate “ComfyUI SoT” or create a library of duplicative summaries.
