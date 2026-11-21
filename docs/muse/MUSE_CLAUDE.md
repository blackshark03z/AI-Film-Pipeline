# Muse — Claude working rules

Muse is a closed-loop AI film pipeline (Python package `muse_studio`): SRT/script → story bible → anchors, plates
and keyframes → screenplay compiler → animatic → generation → FilmQC + multi-take → master assembly → delivery kit.
**Source of truth:** `PIPELINE_SOT_NATIVE_FILM.md` (Vietnamese). Gaps not built yet: `CRAFT_GAP_BACKLOG.md`.

## Run
- Run from `D:\Muse` (`python -m muse_studio...` fails from inside `muse_studio/`). On a Windows console set
  `PYTHONIOENCODING=utf-8` first, or `--help` crashes on the Vietnamese help text.
- `python -m muse_studio.cli normalize-srt|srt-audit|compile|keyframes|animatic|preflight|qc-audit|assemble|deliver <...>`
- `python -m muse_studio.pool_runner keyframes <project_dir> [--include-setups] [--include-turnarounds]`
- Generation step: `python -m muse_studio.pool_runner videos <project_dir> [--max-rounds 3] [--no-auto-repair]`
- `--simulate` = offline dry run (no spend). Full stage → command map: skill `muse-director`.
- Tests: targeted `python -m pytest muse_studio/tests/<file> -q --tb=short`; the full suite takes ~3 min.

## Context budget
- Review images as ONE contact-sheet grid ≤ 1280 px wide. Built-in sheets are 4 × 480 = 1920 px: downscale before
  reading. Never open frames one by one.
- Scripts print a short summary (counts, PASS/FAIL, paths); full detail goes to a JSON file.
- Logs: `rg -n "ERROR|FAIL" <log> | head -40`. Never read raw logs, MP4 probes or whole manifests.

## Discipline
- **Fix a defect in the stage that should have caught it**, then add a line to the lessons ledger
  (`.claude/skills/muse-director/references/lessons.md`): defect → evidence → stage that missed it → check → status.
- **Technical PASS ≠ Owner acceptance.** `preflight`, `qc-audit` and `quality_score` measure defects, not story,
  performance or continuity. The macro key shot passed QC while the key lifted off the table (SOT §3).
- `qc-audit` and `assemble` exit 0 even with rejected shots: read `qc_audit_report.json`, not the exit code.
- Rate every beat GREEN/AMBER/RED/UNKNOWN before stills (`muse-director/references/generability.md`); restage RED, don't retry it.
- Every dialogue line has an addressee and a listener anchor (`muse-director/references/interaction-contract.md`).

## Owner authority: one policy for the whole studio
- **`D:\AI FILM MAKER\AFP-stable\docs\production\OWNER_POLICY.md` is the single Owner policy for AFP and Muse**
  (Owner, 2026-11-21: "Hợp nhất ngay"). Read it before asking the Owner anything. Where this file conflicts with
  it, OWNER_POLICY wins. An Owner instruction given in any AFP or Muse session is valid here too. Sessions record
  it in OWNER_POLICY with the exact quote; nobody asks the Owner to repeat it.
- In short:
  - **Delegated to the agent** (Owner, 2026-11-21: "Về contact sheet thì agent duyệt"): anchors/turnarounds,
    plates, keyframe contact sheets, the animatic and kept takes. Each one is approved by a written
    film-creative-review (PASS/RESTAGE per cell).
  - **Muse spend needs no approval.**
  - **Reserved to the Owner:** the final master, story meaning, dialogue or locked-look changes, publishing,
    `git push`, new accounts and purchases, and every Flow spend.
  - **Halt:** a CAPTCHA, verification page or unusual-activity notice stops ALL Muse sending; tell the Owner.
    Report out-of-quota or failed-login accounts.

## Skills
- Here: `muse-director` (`.claude/skills/muse-director/`).
- Shared (user level, `C:\Users\ADMIN\.claude\skills\`): `film-craft`, `film-treatment`, `film-creative-review`,
  `film-sound-design`, `film-lessons`.
- **Load by stage (default, no need to ask).** Invoke these with the Skill tool before working a stage:
  | Stage | Skills |
  |---|---|
  | 1–2 SRT, beats, story bible, treatment | `muse-director`, `film-treatment`, `film-craft` |
  | 3a compile/staging, 3b preflight | `muse-director`, `film-craft` |
  | 2.5 anchors/plates/keyframes, 3.5 animatic | `muse-director`, `film-craft`, `film-creative-review` |
  | any dialogue, voice, lip-sync, music, mix | + `film-sound-design` |
  | 4 generation | `muse-director`, `film-craft`, `film-lessons` |
  | 5 QC + take review, 6–7 assemble/master, 8 delivery | `muse-director`, `film-creative-review`, `film-lessons` (6–7 also `film-sound-design`) |
  | any defect, retry, "done?" | `film-lessons` |
- Hook `.claude/hooks/stage_skills.py` (UserPromptSubmit + Bash `muse_studio` commands) injects this reminder.

## Shared folder
- Other sessions may be working here (e.g. `_director_review_*`, `HANDOFF_*`). Don't edit their files, runs or
  git state.
- Git (Owner, 2026-11-21, see OWNER_POLICY): local commits of source and docs are allowed, including putting
  `muse_studio` under version control. Stage by explicit path.
  - Never commit `muse_studio/data/accounts.json*` (backups included), `muse_studio/data/profiles/`,
    `muse_studio/data/lane_leases.json`, any cookie or session file, `.env`, or film work folders.
  - Never clean, stash or reset another session's work.
  - No push.

## Language
- Answer the Owner in Vietnamese. Code, comments and commit messages in English.
