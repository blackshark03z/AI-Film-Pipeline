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
| **S1 — SHIP Dola Session OneClick, GPM-first operator journey** (**LOCAL PRODUCT_VERIFIED; OWNER GPM-FIRST SCOPE 2026-10-18**) | One-click operational matrix for **Owner-permitted GPMLogin** Dola profiles; exact GPM group/profile → alias → Dola identity binding, honest same-day credit evidence/UNKNOWN, safe busy/deferred handling, repeated read-only sync with no cross-account mixing or credential exposure. Existing managed-source compatibility preserved. **Ordinary Chrome MV3/Native Host/Capture A4 = SKIPPED_BY_OWNER (waived for S1 ship, not technically PASSED).** Original A1–A8 are historical evidence; this Owner-approved scope supersession only changes source coverage/A4 applicability, and elevates live GPM A5 into the S1 critical ship gate. No generation/paid action. | **PRODUCT_VERIFIED / LOCAL GPM-FIRST S1 PASS (2026-10-18):** exact Worker commit `958337ec` and independent readback of the persisted runtime matrix/registry/events prove four eligible GPM identity-bound `SESSION_VALID` with distinct hashes and 5 targeted sync events (first alias twice), one untouched `OWNER_DEFERRED`, accurate credit `UNKNOWN`; independently 85 focused + 59 protected regression tests PASS. Chrome A4 remains **SKIPPED_BY_OWNER**, not technically PASS. **This is local scoped product acceptance, not film acceptance, remote release, or evidence of positive provider credits.** | Owner approves GPM scope and any consequential browser start/login; Tech Lead independently verifies safe permitted GPM journey and acceptance, retaining UNKNOWN/deferred/busy truth |
| **S2 — First short narrative-to-real-film owner review/release gate** (**OWNER_CREATIVE_ACCEPTED / LOCAL_SHIP_PACKAGE_READY / OWNER_PUBLIC_RELEASE_APPROVED; DESTINATION_PENDING, 2026-10-19**) | A fully playable, real-asset narrative film with verified story/shot continuity, exact provenance and editorial/master readback, plus Owner visual/creative accept-or-repair decision. A technical export does not automatically satisfy V1's separate 30–60s benchmark or final release gates. | **CREATIVE LOCK CONFIRMED BY OWNER** for existing five-shot, 25.208333s V2-021 picture/story/continuity/edit and source-audio sound direction. Selected exact `S2_SOURCE_AUDIO_REVIEW.mp4` SHA-256 `a00b076a488a2dd87ef3d735ebcd469a609a97c94f1ecd2ff9a29f22f8c82f82` (independently F1–F6 technical review verified); original near-silent `DISTRIBUTION_MASTER.mp4` SHA-256 `9085a50bf0babd81257dd8f8e982a2553eff7cd8592dde6de8d84a4be923f27d` preserved. **OWNER_CREATIVE_ACCEPTED / LOCAL_SHIP_PACKAGE_READY / OWNER_PUBLIC_RELEASE_APPROVED / DESTINATION_PENDING (2026-10-19).** Local package `V2_021_CREATIVE_LOCK_PACKAGE/` contains byte-identical locked MP4 (7,032,526 bytes, same SHA), `MANIFEST.json` and `README.md`; 605 decoded video frames, full A/V decode clean, source lineage verified. The already-sealed package manifest still says `release_authorized=false`; that is an immutable **pre-approval snapshot**, not a statement about the later Owner decision, and it must not be silently rewritten. **No publication performed or public URL confirmed.** Five-shot candidate does not satisfy separate frozen 8–12-shot benchmark. | Owner explicitly authorized **public release of this exact creative-locked S2 film** on 2026-10-19. Tech Lead must first resolve destination channel/account and publication details, verify applicable source-media/provider release rights and then separately record execution proof. Git push/merge, Generate, Film120, paid provider actions are not authorized by this approval |
| **S3 — Complete real-asset 120-second film** (**PAUSED / NOT AUTHORIZED TO RESUME**) | 24 intended roughly 5s beats are genuinely rendered and individually QC-accepted with verified lineage; final 120s target master has **no placeholder slates**, playable picture/sound, editorial/continuity review, budget/accounting and explicit Owner creative/release approval. Duration alone is not ship. | **PARTIAL**: V2-022 latest recorded **8/24 QC_ACCEPT; 16 pending**; 120s slate workprint is not completion. No new releases/credits currently authorized by this milestone. | Separate Owner decision on resumption, spend/account/profile authority and acceptance before new provider mutations |

**Critical-path sequencing (LEARN updated 2026-10-18):** S1 **GPM-first LOCAL PRODUCT_VERIFIED** on the exact live proof; the former live GPM A5 gate is satisfied and **A4 ordinary Chrome remains SKIPPED_BY_OWNER**, never relabeled PASS. Frozen A1–A8 historical contract, Chrome implementation and prior evidence remain intact; G1–G6 Owner-approved scoped acceptance is the completed S1 gate. **No new Active Slice is automatically selected.** The existing V2-021 S2 real-film candidate may proceed to Owner creative review **only by deliberate Owner decision**, with no Generate implied. **S3 stays paused** until Owner explicitly resumes production and authorizes costs. S1 local PASS does not imply remote merge/push, product-wide release, or film creative acceptance.

**Proof and truth boundary:** For each milestone record Product Delta → exact evidence → main blocker → next Owner/Tech Lead decision in existing Implementation Status. Distinguish `TECHNICAL_PROVEN`, `PRODUCT_VERIFIED`, `OWNER_ACCEPTED` and `RELEASE_READY`. A committed branch, passing tests, provider output or technical checkpoint cannot change another milestone's status. If evidence or permission is missing, retain `PARTIAL`/`INCONCLUSIVE`; Owner-deferred accounts remain untouched.
