# AI-Film-Pipeline — OpenCode project instructions

## Active coding runtime
- Continue this repository in **OpenCode**, not Codex or Antigravity.
- The project-level OpenCode model target is DeepSeek V4.1 Flash (`deepseek/deepseek-flash`). Provider authentication stays in OpenCode; never put API keys in Git.
- For complex continuation, use the project skill `film-ship-first`. The installed `.agents/skills/codex-techlead/SKILL.md` from Native Workflow Kit v1.2.2 is **method guidance**, not a mandate to launch Codex.

## Authoritative context
Read actual Git branch, HEAD, status/diff and relevant source before editing. Then consult:
1. `docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`
2. `docs/sot/film/00_SOT_INDEX.md`
3. `docs/operating/PROJECT_OPERATING_PROFILE.md`
4. `docs/operating/IMPLEMENTATION_STATUS.md`, `docs/operating/CURRENT_SLICE.md`
5. Latest applicable package/quality evidence on the checked-out branch.

Older current-slice documents may lag newer work; resolve by source, commits and evidence, not by inventing a new Source of Truth. Reuse AutoVideoPipeline/AutoEdit across existing product boundaries, without taking over their active worktrees.

## Ship-first rules
- Follow the existing SHAPE → BOUND → SLICE → BUILD → PROVE → LEARN lifecycle. No competing workflow or redundant SoT.
- Finish a representative input → usable-film-output journey before unrelated infrastructure polish. Prefer reuse, minimal changes and the proven media renderer.
- Verify with focused checks during BUILD; run required/protected checks on the exact release candidate, or sooner when a demonstrated risk requires them. Distinguish technical PASS, actual product PASS and Owner creative acceptance.
- Protect dirty files, previously accepted assets and external job lineage. No reset/clean of active work, test weakening, credential changes, paid generation, publish, deploy or irreversible actions without explicit authority.
- No blind resubmission of ambiguous provider operations. Keep ShotSpec/Film State, exact lineage and provenance authoritative.
- Report exact revision and media outputs, tests, product deltas, blockers and honest COMPLETE_VERIFIED / PARTIAL_DELIVERY / BLOCKED.
