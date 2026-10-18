# Scope and Principles

## Goal

Build the smallest durable film-production kernel that can turn structured story intent into traceable AI-generated shots, continuity-aware selection, rough edit and Resolve finishing.

The goal is **not** to maximize the number of models/tools integrated.

## MVP production envelope

Initial benchmark target:

- 30–60 seconds;
- 8–12 shots;
- 1–2 recurring characters;
- 1–2 locations;
- mostly narration or short dialogue;
- simple action;
- at least one continuity-critical shot;
- at least one failed shot that exercises the repair loop.

After the vertical slice passes, the same architecture may scale to longer narration-driven story drama.

## In scope

- story/narration ingestion;
- scene and shot breakdown;
- character/world/cinematography/continuity bibles;
- ShotSpec;
- prompt compilation;
- Flow/Veo and Seedance adapters;
- deterministic lineage;
- QC and repair;
- rough assembly;
- Resolve handoff;
- cost/attempt logging.

## Explicit non-goals for V1

- local Stable Diffusion / ComfyUI dependency;
- mandatory image/keyframe generation;
- local video inference;
- training/fine-tuning;
- 3D blocking;
- complex web app;
- distributed workers;
- durable orchestration platform;
- microservices;
- automatic "AI judge" as final authority;
- complete NLE replacement;
- autonomous multi-agent film crew.

## Design principles

### Continuity is data
Identity, look, props, geography, screen direction, eyelines, light direction, weather, injury/dirt/wetness and emotional state must be explicit state.

### Cheap decisions before expensive generation
Lock story purpose, shot necessity, continuity constraints and camera intent before sending a video job.

### One shot, one primary performance idea
Avoid overloading a short generation with many simultaneous state transitions.

### Camera motion has meaning
Movement is selected for dramatic purpose, not because "cinematic" prompts tend to add a push-in.

### Provider-neutral core
Flow/Veo, Dola, Elyum and future providers are execution engines, not the architecture.

### Explicit degradation
If a provider cannot express a control, the compiler records that control as unsupported and either:
- converts it into text constraints;
- routes elsewhere;
- or accepts the degradation deliberately.

### Editorial is part of generation
Rough cut can request pickups. Generation is not "done" merely because a provider returned an MP4.

### Evidence over preference
Veo-vs-Seedance routing quality, retry count, cost and latency are benchmark decisions, not permanent beliefs.

---

## Current ship milestones — product-delivery clarification (2026-10-18)

**Product Goal remains unchanged:** turn narrative/story intent into an actually watchable, traceable AI-made film through provider generation, continuity-aware QC/selection, editorial and Resolve-compatible finishing. Production infrastructure is an enabler; source code, tests, sessions or a slate workprint alone are not a shipped film. **This addendum does not rewrite the frozen V1 30–60 second / 8–12 shot benchmark or its acceptance gates above.**

The milestones below clarify **outcome and evidence**, not permission to begin the next slice. There is **one active project execution focus** at a time, as defined by the root `docs/operating/CURRENT_SLICE.md`; historical and future work never supersede it merely because a branch or worker is newer. Runtime status and proof belong in `docs/operating/IMPLEMENTATION_STATUS.md`.

| Milestone | User-visible outcome / exact ship gate | Status at 2026-10-18 | Acceptance authority |
| --- | --- | --- | --- |
| **S0 — Film Pipeline V1 technical foundation** | Existing Story/ShotSpec → provider lineage → QC/selection → EditManifest/rough cut → Resolve handoff kernel technically operable, with traceable evidence. **Not a film or release acceptance.** | **TECHNICAL PROVEN_COMPLETE** (Package-019, 25 stages, zero NOT_IMPLEMENTED/BROKEN); original V1 film creative/content gates still open | Tech Lead technical PROVE; Owner creative/release decision separate |
| **S1 — SHIP Dola Session OneClick, three-source operator journey** (**ACTIVE**) | One-click managed A–F, ordinary Chrome owner-click MV3/native-host and Owner-permitted GPM sources; exact alias+identity binding, independent DPAPI vaults, sanitized actionable matrix, credible source-time credit freshness, fail-closed UNKNOWN/deferred/busy states, A1–A8 acceptance and an independently observed real Chrome capture → destination identity readback. No generation/paid action. | **PARTIAL_DELIVERY / OWNER-GATED**: code freshness fix + 85 focused tests independently PASS, managed live evidence reported; Chrome live capture A4 not proven, GPM fresh reproof optional/authority-bounded. See `CURRENT_SLICE.md`. | Owner explicitly performs Chrome Capture/login and controls any GPM launch; Tech Lead independently PROVEs frozen A1–A8 |
| **S2 — First short narrative-to-real-film owner review/release gate** (**DEFINED, NOT ACTIVE**) | A fully playable, real-asset narrative film with verified story/shot continuity, exact provenance and editorial/master readback, plus Owner visual/creative accept-or-repair decision. A technical export does not automatically satisfy V1's separate 30–60s benchmark or final release gates. | **TECHNICAL CANDIDATE EXISTS**: V2-021 five real shots, 25.208s `DISTRIBUTION_MASTER.mp4`; Owner creative acceptance still **PENDING**, no promotion or release implied. | Owner accepts/rejects exact candidate, trims and release scope; Tech Lead validates evidence before marking ship |
| **S3 — Complete real-asset 120-second film** (**PAUSED / NOT AUTHORIZED TO RESUME**) | 24 intended roughly 5s beats are genuinely rendered and individually QC-accepted with verified lineage; final 120s target master has **no placeholder slates**, playable picture/sound, editorial/continuity review, budget/accounting and explicit Owner creative/release approval. Duration alone is not ship. | **PARTIAL**: V2-022 latest recorded **8/24 QC_ACCEPT; 16 pending**; 120s slate workprint is not completion. No new releases/credits currently authorized by this milestone. | Separate Owner decision on resumption, spend/account/profile authority and acceptance before new provider mutations |

**Critical-path sequencing:** Finish **S1 live A4** and adjudicate A1–A8 first. The existing V2-021 S2 candidate may be reviewed without new generation, but only by Owner's deliberate review decision. **S3 stays paused until Owner expressly resumes the production mission**, independently of OneClick technical PASS. No automatic transition S1 → S2 → S3, no new work package or worker, and no change to existing external-effect restrictions is implied.

**Proof and truth boundary:** For each milestone record Product Delta → exact evidence → main blocker → next Owner/Tech Lead decision in existing Implementation Status. Distinguish `TECHNICAL_PROVEN`, `PRODUCT_VERIFIED`, `OWNER_ACCEPTED` and `RELEASE_READY`. A committed branch, passing tests, provider output or technical checkpoint cannot change another milestone's status. If evidence or permission is missing, retain `PARTIAL`/`INCONCLUSIVE`; Owner-deferred accounts remain untouched.
