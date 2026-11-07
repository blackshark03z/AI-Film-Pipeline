# CURRENT SLICE — DRAMA (ACTIVE) — 2026-11-07

Keep this file to one screen. Full history up to 2026-11-06:
[archive/CURRENT_SLICE_HISTORY_THRU_20261106.md](archive/CURRENT_SLICE_HISTORY_THRU_20261106.md).

## Focus

- **Product line:** drama (Owner, 2026-11-01). Tech Lead has full technical authority to finish the
  [drama upgrade plan](../roadmap/DRAMA_PIPELINE_UPGRADE_PLAN_V1.md).
- **Branch:** `feature/drama-preprod-p0` (worktree `D:/AI FILM MAKER/AFP-stable`). The E2E narration CLI
  from `codex/film-e2e-ship` is merged here (2026-11-06); that branch is no longer a separate line.
- **XIANXIA60 / X04:** PAUSED_BY_OWNER, NOT_SHIPPED. History only.

## Owner constraints in force

- **Generation paused** (2026-11-06). No new image/video Generate without an explicit Owner go.
- **Video research/tests: Omni Flash only, 360p.** Verify the actual UI binding; never substitute silently.
  Source: [Film SoT index](../sot/film/00_SOT_INDEX.md).
- **SRT → faithful action:** keep the sentence's actor, action, receiver and consequence; stage
  setup → contact → reaction → aftermath; add nothing the sentence does not state.
  Source: [Prompt Compiler](../sot/film/05_PROMPT_COMPILER.md). Enforced for E2E plan v2 by
  `action_meaning` (`src/film_pipeline/drama/action_meaning.py`).
- Flow video: GPM `wanglin08ma`. ChatGPT images: GPM `nethaolabycss222@gmail.com`, tab 2. No purchases,
  no top-ups on the old Flow account, no publish, never close GPM/Flow browsers or touch cookies/captchas.

## Where things stand

| Item | State |
|---|---|
| film01 "First Day" | Owner-accepted final |
| film02 "The Spare Key" | TECHNICAL PASS, rebuilt with cards/tags (WP8); Owner creative review pending |
| film03 "The Front Desk" | TECHNICAL PASS, 139 s final with C2PA dev signer; Owner review pending |
| E2E narration CLI (`tools/film_e2e.py`) | prepare/resume/status/finish; plan v2 gates blocking, continuity, WP3 choreography and SRT action meaning; per-project image profile/tab and Flow account alias |
| E2E sample `e2e_badge_20261104` | 2 SelectedTakes, 6 clips awaiting review; SHOT04 fix awaiting Owner; SHOT08 NOT_FIXED |
| Production system (`films/<id>/` + `tools/film.py`), 2026-11-07 | P0–P10 DONE offline ([backlog](../production/LOOP_BACKLOG.md)): gates 1–6 validated, start-still stage, delivery fixes, prompt word budget, offline dress rehearsal of film04 (synthetic, never product proof), runbook + Owner review pack, Codex review; full suite 1873 passed; film03 re-run through the package (technical); film04 "Last Ticket" authored to gate 2 + clean plan, 0 credits; next: Owner go-live for P3-05 / P8-02, P11 hardening meanwhile |

## Main blocker and next step

- **Ship the production system (active, Tech Lead plan 2026-11-07):** phase P10 in the
  [loop backlog](../production/LOOP_BACKLOG.md) — gates 3/4/6 validators, start-still stage, delivery fixes, prompt budget
  report, offline dress rehearsal of film04 on synthetic clips, runbook + Owner review pack, coverage reconciliation, Codex
  review. Executed by the Sonnet loop. After P10 the strongest blocker is the Owner go-live for P3-05 (one Omni Flash 360p
  canary) and P8-02 (film04: 12 generations, expected 171.2, cap 256.8 credits). Rehearsal output is never product proof.
- **SHOT08 (shove → stagger back):** no accepted take after G/H/A/B/I2/Omni (at least 306 credits). Last Omni 360p
  take was PARTIAL (extra knee-lift/return step). Next, only on Owner go: one Omni Flash 360p attempt whose
  plan declares `action_meaning` + choreography so lock/prompt/QC follow the SRT rule. Same cause twice →
  change approach, no retry loop.
- **Release:** replace the dev C2PA signer with a trusted one before any public release.
- Owner decisions pending: creative review of film02/film03; whether to resume Generate.
