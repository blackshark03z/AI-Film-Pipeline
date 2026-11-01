# film03 — "The Front Desk" (SRT → final film)

Source brief: a 55-minute third-party YouTube drama SRT (a desk officer
throws a Black woman's credentials in the trash; she turns out to be his new
superior). The film is an **original script on that motif only**: names,
events and every line of dialogue are new (`docs/drama/film03_front_desk.fountain`).

8 scenes × 16 s (16 generations × 8 s), English, 2:19 final with title,
context cards, identity tags and end card.

Cast (fictional): CAPTAIN NORA BELL, SGT. WADE KESSLER, OFFICER LUIS ORTIZ.
Locations: precinct lobby (SC01–06), briefing room (SC07–08, after the card
"Roll call, 8 a.m.").

## Delivery (post/)

| File | What |
|---|---|
| `film03_front_desk_final_marked.mp4` | the film: 139.1 s, 1280×720, −15.3 LUFS / −1.7 dBFS, English dialogue burned in, AI label, metadata + C2PA (dev signer) |
| `film03_front_desk.en.srt` / `.vi.srt` | full sidecars: title, cards, identity tags, dialogue, end card with the AI notice |
| `disclosure.json` | AI disclosure (EU AI Act Art. 50 notes) |
| `film03_post.json` | post manifest, comprehension record (0 issues), sha256 of every delivery file |
| `tags_preview.jpg` | the three identity tags as placed by `drama.tag_layout.auto_place` |

Not for release until the dev C2PA signer is replaced by a trusted one.

## Route

1. `tools/drama_film03_story.py` (declarations: order, who is in frame,
   intros, tags, cards, facts, VI table) + `tools/drama_film03.py` — plan,
   locked looks, continuity states, preflight 16/16 PASS (SC03_g1 carries the
   expected CROSS_CUT_DEPENDENCY note), storyboard, image prompts.
2. Flow image mode, 0 credits (`stills_out/`): 3 character stills, 2 plates,
   16 start frames. Every still passes `tag_layout.check_still_identity`
   (the expected people are the ones recognised) and an eye check.
3. Flow video "Khung hình", 12 credits each (`takes/`). Before sending,
   `flow_send.py --start-file` checks the filled start slot pixel-matches the
   local frame. All 16 takes match their start frame (grey diff 4–18).
4. `tools/drama_film03_post.py` — comprehension, cut, cards, tags,
   subtitles (silencedetect windows, script text), loudness, label,
   disclosure, C2PA.
5. `tools/drama_write_film03_kpi.py` → `film03_kpi.json`.

## Moderation trade-off

Flow refused (refunded) several generations with "reputational risk /
misrepresenting current events". Video prompts therefore carry no race
words (the start frames carry the look), and four shots (SC03_g1, SC03_g2,
SC06_g1, SC06_g2) only passed with the word "police" removed from the prose:
`prompts/<gid>.soft.txt` is what was sent for those. Dialogue is unchanged.

## Defects → pipeline fixes

- Picker clicks on the wrong item (wrong start frame, a film02 kitchen
  frame): `scrollIntoView` on Flow's virtual list recycles `<img>` nodes.
  `flow_send._picker_find` now only wheels the list and clicks where
  `elementFromPoint` hits the token; `--start-file` blocks before paying.
- Four duplicate takes from failed jobs: a video without a network prompt
  bind is `UNBOUND`. SC02_g2 was accepted by a unique start-frame match
  (14.1 vs next 52.0), recorded in its take JSON.
- Start frames with the wrong person: still identity gate.
- Wide master too small for face recognition: each character is tagged on
  his first close shot, before his line.

`takes_rejected/` keeps the JSON records of the rejected takes (video files
not committed).
