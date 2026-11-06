# film04 "Last Ticket" (P8-01)

Date: 2026-11-07 · authored from scratch by the model, following `docs/director/DIRECTOR_PLAYBOOK.md` only ·
**nothing generated, 0 credits** · Owner acceptance: **PENDING** (technical result only).

Premise: a night-shift ticket clerk (MARA) is closing the window at 10:31 when a soaked young man (THEO) arrives with a jar of
coins for the last train. She refuses, then counts his coins, issues the ticket, and walks onto the platform with her own suitcase.
6 scenes × 2 generations = 12 generations, ~96 s. Original characters and locations; no real person; no music.

## What exists

| Stage | State |
| --- | --- |
| `01_story`, `02_direction` | Gates 1 and 2 **PASS** (checked by the package validators). |
| `03_preprod`, `04_shots` | Authored. Locked looks/locations, axis THEO left / MARA right, props pinned by design refs, 4 HIGH-risk fallbacks. |
| `film.py plan` | 12 prompts ≤ 215 emitted words with no `accepted_overlong`; the **only** remaining BLOCK per generation is `STORYBOARD … PENDING`. |
| Gate 3 / 4 | `NOT_RUN` in `validate` (no registered validator, as for film03); the plan record `gate3.json` is the evidence for gate 3. |
| Gate 5 / 6 | `BLOCK` – nothing shot, nothing cut. Not applicable before generation; not claimed. |
| Animatic | `media/animatic.mp4` (96.0 s, 0 findings) built from the plan's storyboard placeholders; gitignored. |
| Budget | 12 generations: expected 171.2, high 201.6, cap 256.8 credits (1.5 × estimate). `credits_estimate` in `film.json` stays `null` – the Owner sets it. |

## Open for the Owner

1. **Storyboard approval** (`film.py plan --approve-storyboard "<reviewer>"`) – not self-approved.
2. **Originality / rights**: characters, locations, script, likeness are `pending` in `03_preprod.rights`.
3. **Go-live**: `OWNER_GO_LIVE: NO`; no generation until the Owner says so.
4. Creative review of the story itself (the model wrote it; there is no product proof yet).

## Known risks (planning)

- Physical contact in frame: SC01_g1 (shutter cord), SC01_g2 (door), SC04_g2 (shutter push). Fallbacks are in `risk_fallbacks`.
- Hand-over: SC05_g2 (ticket). Fallback: the ticket lies on the counter and THEO takes it himself.
- Coin pour (SC04_g2) is kept inside one generation and ends in a felt tray, so the next generation does not depend on where
  loose coins land (the cross-cut rule).
- Moderation: no police, weapons, violence or race words; the context card reads "10:50 p.m.".

## Lessons for the system (not film-specific)

- The emitted-prompt budget is what bites: locked looks + location + continuity-state list leave about 90 words for the shot.
  Tracked props should be few and their state strings short.
- A character who enters mid-generation must be in the start state (e.g. "outside the glass door") or the prompt has no look text for them.
- A once-action must be spelled in the ACTION phase text; a prop that changes or appears must be named by an ACTION/CONSEQUENCE phase.
