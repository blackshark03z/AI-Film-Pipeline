# M3 merge checklist: Step 1 (freeze and import-source check)

Plan: `docs/production/M3_MERGE_PLAN.md` §7, Gate 0 and Step 1. Every line is verified by reading the repo or the
file named, not by a session report. Status: **DRAFT** (AFP side filled; Muse side waits for tag `muse-v1.0-r15`).

## AFP (`D:\AI FILM MAKER\AFP-stable`, branch `feature/drama-preprod-p0`)

| Item | Evidence | State |
|---|---|---|
| A1 S1 addendum | commits 6e606905, cfb29744, c962414e, c101a974; coordinator ACCEPT (Codex unavailable for R10) | done |
| A2 S2-lite | `feature/s2-lite` c49b0866 merged as ca9d328f; Codex r2 REJECT, 4 High fixed; 65/65 tests | done |
| A5 push | origin pushes delegated to the agent (OWNER_POLICY 89c2b78c) | done |
| A8 harvest | `_archive/merge_triage/` patches | done |
| A9 old worktrees | Owner decision (fate); not blocking the merge, nothing imported from them | open, non-blocking |
| A10 branch triage | 28 tagged `archive/<branch>` | done |
| AFP full suite on the freeze tip | `pytest -q -x` on ca9d328f: 2799 passed, 204 skipped, 0 failed (52 min) | done |
| `git status` clean (only `uv.lock`, `MUSE_CONSOLIDATION.md` untracked, both never committed) | checked at ca9d328f | done |
| Freeze tip SHA | ca9d328f (code); later docs-only commits are integrated in Step 8 | candidate |

## Muse (`D:\Muse`)

| Item | Evidence | State |
|---|---|---|
| M1 r15 stop-all (fixes a-c), Codex ACCEPT | | pending |
| M2 PRE-TAG #11 (no `src.unlink()`) | | pending |
| M3 accounts lock | | pending |
| M6 git baseline, checkpoint-0 scan clean | | pending |
| M7 tag `muse-v1.0-r15`, SHA, = commit of the P0 hash list | | pending |
| M8 P0 PARTIAL final, 4 anchors held (`P0_HELD_CHILDREN.json`) | Muse TL report 2026-11-21 | done (verify file) |
| M9 BIKER stopped, no live lease | | pending |
| M10-M13 housekeeping decided | | pending |
| `git status` clean; no live lane process or lease | | pending |

## Sign-off

- Coordinator: (pending)
