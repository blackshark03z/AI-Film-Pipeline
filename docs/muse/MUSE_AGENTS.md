# Muse — agent working rules (Antigravity and other non-Claude agents)

Muse is a closed-loop AI film pipeline (Python package `muse_studio`): SRT/script → story bible → anchors, plates
and keyframes → screenplay compiler → animatic → generation → FilmQC + multi-take → master assembly → delivery kit.
**Source of truth:** `PIPELINE_SOT_NATIVE_FILM.md` (Vietnamese). Gaps not built yet: `CRAFT_GAP_BACKLOG.md`.
Claude Code reads `CLAUDE.md` instead; both files state the same rules.

## Run
- Run from `D:\Muse` (`python -m muse_studio...` fails from inside `muse_studio/`). Set `PYTHONIOENCODING=utf-8`
  first (PowerShell: `$env:PYTHONIOENCODING="utf-8"`), or `--help` crashes on the Vietnamese help text.
- Pass file arguments (`--beats`, `--srt`, `--output`) as absolute paths.
- `--simulate` = offline dry run, but it writes placeholder images into the project: only on a scratch copy under
  `%TEMP%`, never in a real project. Full stage → command map: skill `muse-director`.
- Tests: `python -m pytest muse_studio/tests/<file> -q --tb=short`; the full suite takes ~3 min.

## Context budget
- Review images as ONE contact-sheet grid ≤ 1280 px wide; built-in sheets are 1920 px — downscale first. Never open
  frames one by one.
- Read summaries and JSON reports, not media, raw logs, MP4 probes or whole manifests.
  Logs: `rg -n "ERROR|FAIL" <log> | head -40`.

## Discipline
- Fix a defect in the stage that should have caught it, then add a row to
  `.claude/skills/muse-director/references/lessons.md` (defect → evidence → stage that missed it → check → status).
- Technical PASS ≠ acceptance. `preflight`, `qc-audit` and `quality_score` measure defects, not story,
  performance or continuity.
- `qc-audit` always exits 0 and `assemble` exits 0 on a partial master (non-zero only when no clip passed): read
  `qc_audit_report.json`, not the exit code.
- Excerpt SRT: `preflight <P> --no-srt-gate` (omitting `--srt` does not skip the gate when the bible has
  `source_srt_path`).
- Rate every shot GREEN/AMBER/RED/UNKNOWN before stills; restage RED, don't retry it.
- Every dialogue line has an addressee and a listener anchor.
- Never hand-edit `compiled_prompt` or `shots_manifest.json`: fix `beats.json` / `story_bible.json`, then recompile.

## Skills (activate before working a stage)
Project skill `muse-director` (`.claude/skills/`, registered in `.agents/skills.json`), lane runner
`muse-filmmaker` (`.agents/skills/`), film skills `film-craft`, `film-treatment`, `film-creative-review`,
`film-sound-design`, `film-lessons`: `.agents/skills/<name>/` holds only a pointer stub, the real skill is
`C:\Users\ADMIN\.claude\skills\<name>\SKILL.md` (Antigravity refuses skill paths outside the workspace; reading
them needs non-workspace file access allowed). If a skill is not in your list, read its `SKILL.md` directly.
Ignore the global `film-story-bible`, `film-shot-compiler`, `film-post-assembly`, `film-qa-qc`,
`film-screenplay-normalizer` skills for Muse — they are outdated.

| Stage | Skills |
|---|---|
| whole film from an SRT (lane) | `muse-filmmaker` first, then per stage below |
| 1–2 SRT, beats, story bible, treatment | `muse-director`, `film-treatment`, `film-craft` |
| 3a compile/staging, 3b preflight | `muse-director`, `film-craft` |
| 2.5 anchors/plates/keyframes, 3.5 animatic | `muse-director`, `film-craft`, `film-creative-review` |
| any dialogue, voice, lip-sync, music, mix | + `film-sound-design` |
| 4 generation | `muse-director`, `film-craft`, `film-lessons` |
| 5 QC + take review, 6–7 assemble/master, 8 delivery | `muse-director`, `film-creative-review`, `film-lessons` (6–7 also `film-sound-design`) |
| any defect, retry, "done?" | `film-lessons` |

The hook `.agents/hooks.json` (SessionStart + PreInvocation) → `.claude/hooks/stage_skills.py` injects this
reminder once per stage per conversation, from your prompt and from the `muse_studio` commands you ran.

## Spend and approval
- Outside a lane: the Owner approves anchors/turnarounds, plates, keyframes, the animatic, each kept take and the
  master. Muse spend needs no approval (Owner, 2026-11-20): non-`--simulate` `keyframes` / `videos` runs go
  without asking and without a send cap. Stop and tell the Owner on a halt (`muse_halt.json`), and report
  out-of-quota or failed-login accounts. Other providers (e.g. Flow) still need approval for every spend.
- **Lane mode** (skill `muse-filmmaker`): one chat = one lane. The Owner's opening message (SRT, lane id, N
  accounts) approves every stills and video run of that lane. Muse credit is not a constraint in a lane: optimise
  output quality first, then speed. No spend caps, no cap counting (`sends_by_shot` / `takes_by_shot` are reported for information).
  - Run only through `pool_runner keyframes|videos` (never `cli keyframes`, `cli run-pool` or `autoprod` in a
    lane), only while the account lease is open (`python -m muse_studio.lane open --lane <id> --project <abs P>
    -n <N>`; one lane id = one project = one chat); renew before and after long pauses (TTL 8 h), close at the end
    or on abort.
  - Speed: all N accounts every run; anchors, turnarounds, setups and keyframes in one
    `pool_runner keyframes <P> --include-setups --include-turnarounds` call; every pending shot of the film in one
    video wave; one downscaled contact sheet per stage.
  - Takes: `videos <P> --max-rounds 1 --takes K` (K parallel takes per shot; a manifest `takes` field overrides
    K but `compile` does not write it, so K = the largest need): GREEN 1, AMBER 2, UNKNOWN 3, dialogue / lip-sync
    at least 2; RED is restaged before stills, never sent. Cycle: wave → `qc-audit` (finds every take;
    `verified_clips/` holds the passing take with the highest `quality_score`) → self-review picks the kept take
    from the whole clip of each take + ledger →
    restage/recompile → next wave only for shots still needed.
  - Self-review (film-creative-review, labelled self-review) replaces Owner review at every ★ point — never stop
    to ask — written to `<P>/LANE_REVIEW.md` as PASS / RESTAGE / CUT with evidence. Stills may be regenerated as
    often as needed. Quality stop rule: never re-send an identical design for a structural defect; a defect's 2nd
    occurrence on a beat → change approach (restage, reframe, new `opening_state`, new reference); 3rd → CUT or
    BLOCKED, continue, report. Only technical blockers end a lane early.
  - Dialogue: split a line at a sentence boundary or tighten it (`DIALOGUE_OVER_CAPACITY`, lip-sync fit) without
    changing its meaning, logged with before/after in `LANE_REVIEW.md`. A change of story meaning is not allowed:
    cut the beat and report the story cost.
  - The final report keeps technical PASS, agent self-review and "Owner acceptance: pending" apart.
  Lane rules in `muse-filmmaker` and muse-director's "Lane mode" win over any "ask the Owner" or send cap
  elsewhere, except the items in the next bullet.
- Changing story meaning or a locked look, a RED exception, or a voice/music source with unclear rights needs the
  Owner outside a lane and is never done inside one (cutting a BLOCKED beat is allowed — report its story cost; an uncleared source is
  simply not used).

## Shared folder
- Other sessions and lanes work here (`_director_review_*`, `HANDOFF_*`, `_live_*`, other project folders, other
  lanes' `lane.json`). Don't edit their files, runs, accounts or git state. Don't commit, clean or stash git.
- Never kill browser or Python processes; never print credentials or account files.

## Language
- Answer the Owner in Vietnamese. Code, comments and commit messages in English.

## Opening prompt for a new lane (copy, fill in, send in a NEW chat opened in D:\Muse)

```
Dùng skill muse-filmmaker. Làm phim từ file SRT: <đường dẫn tuyệt đối .srt>
Lane: <tên lane>   Số tài khoản: <N>
Thư mục dự án (tuỳ chọn): <D:\Muse\TEN_PHIM_YYYYMMDD hoặc để trống>
Tin nhắn này phê duyệt mọi lượt chạy ảnh và video của lane này, không giới hạn credit. Ưu tiên chất lượng,
rồi tốc độ. Tự duyệt ở mọi điểm ★, ghi LANE_REVIEW.md, không dừng để hỏi. Báo cáo cuối bằng tiếng Việt.
```
