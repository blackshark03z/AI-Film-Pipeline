---
name: film-ship-first
description: Continue AI-Film-Pipeline in OpenCode under Native Workflow Kit v1.2.2 principles, prioritizing a verified end-to-end production milestone over technical-only slices.
compatibility: opencode
metadata:
  opencode/slash: "true"
---

# Film Ship-First — OpenCode bridge

This is an **OpenCode compatibility delta**, not a replacement for frozen Film/Development SoTs or a new lifecycle. Reuse the principles in `.agents/skills/codex-techlead/SKILL.md` (Native Workflow Kit v1.2.2), but do not assume Codex CLI, Codex marketplace, its agent delegation, or any Codex-specific installer exists inside OpenCode.

## SHAPE and BOUND
1. Inspect current branch/HEAD, dirty Git state, repo instructions, Film SoT, accepted implementation evidence and real runtime code. Never overwrite another worker's changes.
2. State the approved Product Goal and one representative user journey (source audio/SRT or accepted equivalent → shot/assets → review/editorial → playable MP4), including what is already proven and what remains unproven.
3. Pick the evidenced critical-path product blocker. Prefer REUSE/NATIVE before DISCOVER/BUILD. Treat AutoVideoPipeline as a reuse source and AutoEdit as a separate consumer; do not mutate either repo without its own authorization.
4. Bound scope, costs, duration, external side effects, protected criteria, finite retry limit and authority. Provider generation and publishing require explicit authorization.

## SLICE, BUILD and PROVE
- Keep existing state and acceptance representations; make only necessary truth deltas. Do not create orchestration frameworks, extra status ledgers or research-first ceremony.
- Worker owns HOW with OpenCode native tools. Load additional task-relevant skills only if necessary and available; do not launch Codex, BMAD, MAR2 or Ponytail merely because the kit mentions them.
- Implement a coherent end-to-end product delta. Test focused behavior after meaningful changes, and exercise a real media/app path using approved existing assets before spending new generation quota.
- For the exact release candidate, run required/protected regression and verify media decode, duration/sync, correct ShotSpec → GenerationAttempt → ProviderJob → Asset → SelectedTake → Edit/MP4 lineage where applicable.
- Never weaken tests, misclassify an uncertain provider effect, or equate technical PASS with Owner acceptance of creative quality.

## LEARN and stop
Report delivered user-visible outcome, revision/asset identity, verified evidence, risks and next demonstrated blocker. The exit is `COMPLETE_VERIFIED`, `PARTIAL_DELIVERY` or `BLOCKED`; finishing a technical slice alone is not the milestone.
