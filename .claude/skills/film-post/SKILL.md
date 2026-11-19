---
name: film-post
description: Edit, finish and deliver a drama film package (films/<id>/) after the takes exist — 05_edit EDL, picture lock, colour, titles/subtitles, sound mix, master QC, versions and the delivery archive (Gates 4–6), plus the editor's craft passes. Use when assembling or polishing a cut, running film.py cut/lock/grade/titles/mix/mastercheck/versions/deliver/finish, or debugging why Gate 5/6 or a post command blocks.
---

# Film post (stages 05–07)

Follow [docs/director/POST_PLAYBOOK.md](../../../docs/director/POST_PLAYBOOK.md). Read only the section you need:
order §1, commands + files §2, edit/Gate 5 §3, colour/titles/sound §4, Gate 6 + delivery + AI disclosure §5,
craft passes §6, Owner reservations §7, worked examples §8, red flags §9.
Stages 01–04 are the `film-director` skill.

## When to use

- Every generation has an ACCEPTED take (Gate 4) and you are building or tightening the cut.
- `film.py lock`, `finish`, `mastercheck` or `deliver` reports BLOCK / stale / dirty and you need the cause.
- Reviewing a cut or master for the Owner.

## Order

`edit --init` → hand-edit `05_edit.json` → `cut` → `cut --render` (rough cut at ~final length) → craft passes →
`cut --accepted-only` → `lock --lock --by "<agent: name listed in film.json delegated_reviewers>"` →
`finish --dry-run` → `finish` (= generators → grade → [foley] → titles → mix → mastercheck → versions →
dialoguecheck → deliver) → Owner runs `deliver --accept NAME`.
First run `status` + `validate`. `finish --dry-run` shows steps only when Gates 1–4 PASS and the lock is fresh; else
`steps: []`, exit 1, reasons in `blocked`. `lock` (status form) exits 1 when unlocked, too. No name in
`delegated_reviewers` → stop and ask the Owner to delegate; never invent one. Legacy film (INCOMPLETE takes, no
`gate3.json`, old archive, e.g. film03) → playbook §1 "Entry branch": review/plan first, never `finish`.
All commands: `python tools/film.py <cmd> --film films/<id> ...`; flags exactly as in playbook §2.

## Craft passes (the tools do not check these)

- Trim stiff AI heads/tails on every TAKE (`src_in_s`/`src_out_s`); the trim is also the J/L handle.
- Cut on action; hold reactions as `02_direction` plans, cut before the face goes slack.
- J/L cuts in dialogue (0.3–1.0 s); transitions only with a reason.
- Colour: match within the scene (`grade`) before any look; deliberate light changes go in `skip`. No grain filter exists.
- Sound: dialogue → SFX/ambience → music (ducked, every cue has a `why`). `mix` aims -14 ±1.0 LU and limits at
  -1.5 dBTP; `mastercheck` blocks outside -14 ±1.5 LU or a peak above -1 dBTP (so -16 fails). This AFP gate overrides
  the generic loudness targets of the shared `film-sound-design` skill.
- Subtitles stay inside the speaking shot; write `titles/cues.json` for noisy takes.
- AI label always on (`disclosure.ai_label`), title line naming AI, generators named; the dev C2PA signer is not
  release-grade.
- Review the cut as one contact sheet + one full watch; run the `film-creative-review` rubric next to `mastercheck`.

## Non-negotiables

- Never edit take files, stamps (`locked_against`) or gate states by hand; rerun the command.
- A take defect found in the cut goes back to `review`/`retake`, not to colour, reframe or cue band-aids.
- Owner only: `deliver --accept`, publishing/upload, purchases (music, voice, trusted C2PA cert), cutting a scene or
  changing the meaning (playbook §7 marks which of these are inferred, not in `OWNER_POLICY.md`). Never sign as
  `human:owner-*`. Never pass `sounds --status cleared` yourself; only `foley` self-clears its offline output.
- Report technical PASS (Gates 5–6), craft review and Owner acceptance separately.
- A defect → `film-lessons`: fix the stage that should have caught it, then `ledger --add`.
