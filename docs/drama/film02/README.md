# film02 — "The Spare Key" (WP7 benchmark)

3 scenes × 16 s, English, 59 s final with cards and identity tags. Written to hit the Muse
failure list: three people in one room, a prop handled exactly once, a sneer,
rain outside the window, a flashback.

Final: `post/film02_spare_key_final_marked.mp4` (metadata + C2PA, dev
signer; `post/disclosure.json`). Unmarked cut, SRT and post manifest beside it.

## Delivery (post/)

| File | What |
|---|---|
| `film02_spare_key_final_marked.mp4` | the film: 59.3 s, 1280×720, −15 LUFS, English dialogue burned in, AI label, metadata + C2PA (dev signer) |
| `film02_spare_key.en.srt` | full English sidecar: title, context cards, identity tags, dialogue, end card with the AI notice |
| `film02_spare_key.vi.srt` | the same in Vietnamese (`VI` in `tools/drama_film02_story.py`) |
| `disclosure.json` | AI disclosure (EU AI Act Art. 50 notes) |
| `film02_post.json` | post manifest; `delivery` holds the sha256 of every file above |

Sidecar cues never overlap (`post.merge_cues` stacks a tag over a line of
dialogue into one two-line cue). Not for release until the dev C2PA signer
is replaced by a trusted one.

## Route (from WP5)

1. `tools/drama_film02.py` — script → per-generation plan (one shot per 8 s
   generation), locked looks, two lighting states of one locked location,
   continuity states, choreography + performance cues, preflight (6/6 PASS),
   schematic storyboard, image prompts.
2. Flow image mode, 0 credits (`stills_out/`): 3 character stills → night
   plate → morning plate rendered **from** the night plate → 6 start frames
   with plate + character stills attached. Each still QC'd by eye; one
   rejected and re-rendered (SC03_g1, see defects).
3. Flow video, "Khung hình" with the start frame, 12 credits each
   (`takes/`, every take `NETWORK_PROMPT_MATCH` via `flow_send.py`).
4. `tools/drama_film02_post.py` — comprehension check, cut, context cards
   ("After their mother's funeral", "Earlier that morning"), identity tags,
   subtitles, loudness, AI label, disclosure, C2PA.
5. `tools/drama_write_film02_kpi.py` → `film02_kpi.json`.

## Results vs film01

| KPI | film01 | film02 |
|---|---|---|
| First-pass usable rate | 0.8 | **1.0** (6/6) |
| Credits per usable second | 2.1 | **1.75** (84 / 48 s, failed try counted) |
| Rerenders per 100 s | 5.0 | **0** |
| Provider blocks / failures | 6 | 1 (generic failure, one retry) |

Muse checks, by eye on every take:

| Test | Result |
|---|---|
| Three people in one room | identity and screen side held across all three-person shots and across scenes |
| Prop handled once | MARCUS picks up the brass key once and pockets it (SC01_g2); ROSA slides the iron key once (SC02_g1) |
| Sneer | one-sided lip curl and narrowed eyes, not a grin (SC01_g2 4–8 s) |
| Rain outside the window | rain only on the glass at night, dry room; sunlight, no rain, in the flashback |
| Flashback | same room relit, readable through the card and the light; looks unchanged; props reset |
| Timing | every line lands inside its ACTION phase (silencedetect) |

## Defects and the stage that now catches them

- **SC03_g1 start still** had a stranger in frame: the still prompt mentioned
  "the key in MARCUS's pocket" for an ELENA close-up. `still_prompt` drops props
  placed on people out of frame and says "Only ELENA in frame". Caught on
  the 0-credit still, no video credit lost.
- **Morning plate** first came out as a different room. Now rendered from
  the night plate attached ("same room, only the time changes").
- **Preflight** blocked the flashback heading "THAT MORNING (FLASHBACK)"
  (time-of-day compared as a whole string) and would have compared the
  return-to-night scene with the flashback instead of the scene before it.
  Both fixed in `scene_bible.py` with tests.
- **Three-person master** was compiled as "wide two-shot": `coverage.describe`
  now says "wide shot" for 3+ people.
- **SC02_g2** failed once on the provider ("Không thành công – Không tải được
  video"); one retry passed. `flow_send.py` now recovers the start slot a
  failed job leaves filled.

- **Owner review: the aunt read as the mother.** "AUNT ROSA" and the
  mother's death lived only in action lines, so an older woman in the family
  kitchen read as the mother and "Your mother changed the locks" made no
  sense. New stage `drama.comprehension`: every on-screen character needs a
  `CharacterIntro` (name + relation to the story) and every story fact a
  carrier (dialogue, picture, identity tag or context card) no later than the
  first generation that needs it; `check_comprehension` blocks otherwise.
  Fixed at 0 credits: opening card, tags beside all three in the opening
  master (SC01_g1, one at a time, MARCUS named over his first line; plain
  text with a black stroke, no plate), flashback card reworded to "Earlier
  that morning".

## Decisions

- The start-frame route is the drama default (WP5 confirmed on a full film).
- Prompt budget on this route: **215 words**. All six prompts were 165–220
  words and followed their phase timing.
- Stills are the QC gate before video credits: reject there, not on video.
- Comprehension runs at two stages. Script stage (`lint_script`, in
  `tools/drama_film02.py`): every speaker needs an intro, every family member
  named in dialogue ("Mom", "your mother") needs an intro relation or a fact;
  the film02 script as first written fails it. Post stage:
  `tag_layout.auto_place` names faces by SFace against the character stills,
  puts each tag beside its face (toward the frame centre, clear of every face,
  the subtitle band and lamp/window glare) and writes `post/tags_preview.jpg`
  for the human check. Declarations: `tools/drama_film02_story.py`.
- Comprehension is planned with the script: dialogue first (free before
  generation), then picture; tags and cards (white on black, ≤ 2 lines,
  2–3 s from a 15 chars/s reading rule) are the post fallback.
- Open: identity across *films* (new cast per film); the end-frame slot is
  still unmeasured; the dev C2PA signer must be replaced for a real release.
