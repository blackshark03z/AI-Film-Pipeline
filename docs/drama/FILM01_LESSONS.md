# film01 "First Day" — lessons for the drama pipeline (LEARN, Worker report)

Date: 2026-11-01. Branch `feature/drama-preprod-p0`, base commit 3732664,
changes uncommitted at the time of writing.
Status: Worker evidence and proposed truth deltas. Not canonical status;
`docs/operating/IMPLEMENTATION_STATUS.md` is updated only by the Tech Lead.

Owner rule behind this document: a defect found in a film is fixed in the
pipeline stage that should have caught it, not only in that film.

## Outcome

- 5 scenes x 16 s, each scene = two 8 s generations on Google Flow
  (Omni 1.1 Flash, 720p, 12 credits each), text-only route.
- Owner approved the rough cut and the final on 2026-11-01:
  `film01_post/film01_first_day_final.mp4` (86.8 s, English subtitles burned
  in, sidecar `film01_first_day.en.srt`, manifest `film01_post/film01_post.json`).
- Credits: 60 block investigation + 120 first text-only pass + 12 rejected hair
  fix + 36 SC03 v2 (g1, g2, g2 re-render) = 228.

## Defects, root cause stage, pipeline fix

| # | Defect seen | Stage that missed it | Fix in the pipeline | Proof |
|---|---|---|---|---|
| 1 | Flow refused every scene with character refs ("reputational risk", ~22 s, refunded) | Provider route choice | Route evidence: refs + police-mistreatment beat are refused, the same text without refs passes. `preflight_scene(reference_mode="TEXT_ONLY")` is a supported route, and attached refs on that route BLOCK | `film01_takes/flow_block_rootcause.json` |
| 2 | NORA's hair changed between scenes; a per-scene "fix" overshot (curly locs) | Prompt compile: looks were re-described per scene | `bible.CharacterLook` (locked text + QC invariants + approval); the compiler copies `look.text` verbatim; preflight `LOOK` blocks a missing, unapproved or altered look | `tests/test_drama_continuity.py` (locked look tests) |
| 3 | SC03: the torn pieces fell behind the counter in g1, but in g2 NORA picked other pieces off the floor | Script + generation split: g2 assumed an outcome g1 never controlled | `continuity.ContinuityState` start/end states per generation, compiled into the prompt; `feasibility.check_cross_cut` blocks (`CROSS_CUT_DEPENDENCY`) when a prop moves through an uncontrolled verb (fall, drop, tear, xé, rơi...) until the end state is verified; `qc.HandoffQC` + `handoff_sheet` verify the rendered last frame before g2 is sent (sequential render gating). Script beat rewritten: pieces are laid on the counter | `gate3_film01_sc03_v2.json`, `film01_takes/qc/SC03_handoff_qc.json` |
| 4 | SC03 g2 v2: a different, younger officer stood in for DOYLE | Prompt compile: the start state named DOYLE, but only in-frame characters got a look | Preflight `LOOK` now covers every character named by the start state, not only those in frame; caught the old prompt before re-render | `test_character_named_by_start_state_needs_its_look_in_prompt`; `film01_takes/qc/SC03_g1_g2_handoff.png` |
| 5 | Subtitle of NORA's line sat over DOYLE's close-up | Post: cue timing was estimated from audio alone | Cues clamped to the speaking shot of the generation plan (post script, not yet in `src/`) | `film01_post/film01_post.json` |
| 6 | Single-pass loudnorm gave -16.4 LUFS; the linear second pass clipped (+0.2 dBFS) | Post | 2-pass loudnorm + limiter -> -14.5 LUFS, -0.5 dBFS peak (ebur128) | `film01_post/film01_post.json` |

Also found in tooling: the Flow send step failed behind an overlay and the
download still returned the old top tile as "PASSED". The send script now
dismisses overlays first and reports `SEND_FAILED` instead of downloading.
A take counts as new only if its sha differs from the previous tile.

## Rules to keep

1. One locked look per character per film; never re-describe appearance in a
   scene prompt. Fix drift by changing the look (with approval) for all scenes.
2. Generations of one scene are rendered one at a time. Generation N+1 is sent
   only after a reviewer has passed every item of the N -> N+1 handoff QC.
3. A beat whose outcome cannot be controlled (something falls, tears, spills)
   must not be relied on across the 8 s cut. Rewrite the beat as placed or held
   objects, or verify the rendered end state first.
4. Anyone named in the continuity sentence is described to the model: give
   them their locked look, or leave them out of the state.
5. Subtitle cues stay inside the speaker's shot; timing from audio alone is not
   enough.

## Still open (proposals, not done)

- Residual SC03 g2 drift accepted by the Owner: the background differs a little
  from g1 (no EXIT sign) and the framing is medium instead of the planned
  close-up. A set/location look like `CharacterLook` would target this.
- Shot framing is not honoured reliably on single-shot 8 s generations; there
  is no check for it yet.
- Subtitle text comes from the script, not a transcription; no ASR is installed.
- The post-production script (grade, fades, loudness, label, cards, subtitle
  overlays) lives in the session scratchpad; moving it into `src/` is a
  separate task.
- Proposed truth delta for the Tech Lead: record film01 as an Owner-accepted
  drama film on the text-only Flow route, and the continuity gating above as
  the drama pre-production standard.
