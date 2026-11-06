# film03 re-run through the production package (P7-02)

Date: 2026-11-07 · no generation, no credits spent · Owner acceptance: **PENDING** (technical result only).

Source: the 16 shipped takes in `docs/drama/film03/takes` (hash-checked against their `.take.json`), imported by
`tools/film03_to_package.py` into `films/film03_front_desk/` (media under the gitignored `media/takes`). Chain run
through the generic CLI: `cut` → `grade` → `titles --render --color` → `mix` → `mastercheck` → `versions` → `deliver`.
Tests: `tests/test_production_film03_rerun.py`.

## What the package now holds

| Stage | Result |
| --- | --- |
| Take log | 16 takes `SCxx_gy_t1`, bound to their bytes and prompts; **all INCOMPLETE** – only the `technical` group is judged (auto:ffprobe). Content groups wait for a human review; the importer never accepts a take. Credits recorded as 0 (the legacy takes carry no per-take cost; film total is in `film03_kpi.json`: 228). |
| EDL `05_edit.json` | 18 events (16 takes + 2 context cards), 3 identity tags, title 3.0 s, credits 4.0 s – same order, card text and tag times as the shipped cut. |
| Dialogue timing | `titles/cues.json`: the 16 silencedetect windows of the shipped post, each mapped to exactly one script line. |
| Colour (`grade`) | 16 of 16 shots corrected; worst deviation from the scene reference 17.5 → 6.76 levels (tolerance 6): SC08_g1 hits the ±0.25 gain clamp (WARN). |
| Sound (`mix`) | Synthetic room-tone ambience per scene (-40 LUFS), dialogue ducking, no music (no cleared music exists in the sound ledger). |
| Master QC | PASS, 4 WARN (below). |
| Versions | 16:9 master + 9:16 (720x1280, tag/centre focus), 6 thumbnails, metadata draft (`DRAFT_NOT_PUBLISHED`). |
| Delivery | `delivery/` archive, 33 files, MANIFEST hash in `07_delivery.json`; `release_ready: false`. |

## Diff against the shipped final (`post/film03_front_desk_final_marked.mp4`)

| Aspect | Shipped | Package v2 | Note |
| --- | --- | --- | --- |
| Duration | 139.125 s | 139.125 s | identical structure |
| Format | 1280x720, 24 fps, h264 + aac 48 kHz | same | |
| Loudness | -15.3 LUFS, -1.7 dBFS | -14.6 LUFS, -1.1 dBFS | v2 follows the -14 ±1 target; peak under the -1.0 ceiling |
| Colour | default grade | per-shot match to the scene median | body luma 84.2 → 82.5 |
| Audio bed | none | synthetic ambience | room tone is generated, not recorded |
| Title card | "THE FRONT DESK" | "THE FRONT DESK" + "Generated with AI" | needed by the `deliver` AI-label gate |
| Credits card | title + fiction line + "Video, images and voices generated with AI." | cast, synthetic-persons notice, generator line, fiction line | built from the package; fits the frame |
| Identity tag text | `NORA BELL – the precinct's new captain` | two lines, name then role | same names, same times |
| Sidecars | EN + VI, 23 cues each | EN + VI, 23 cues each | VI translations come from `direction.translations`; none missing |
| Disclosure | metadata + C2PA dev signer; visible label "AI-generated" **always on over the body** | metadata; visible label **only on the 3.0 s title card** | see open item 1 |
| Generators in disclosure | video+audio (Omni 1.1 Flash) and image (Nano Banana 2.1) with settings | both listed as role `video+audio`, no settings, model strings prefixed "Flow" | see open item 2 |

## Open items found by the re-run (not fixed here)

1. **Visible AI label coverage regressed.** The shipped film burned "AI-generated" bottom-left for the whole body; the package
   only requires the label on the title card. Whether the card alone is enough is a legal/product call for the Owner. If the
   always-on label stays, `deliver`/`titles` need a watermark option (pipeline gap, not film-specific).
2. **`--generators` loses role and settings.** One string cannot say that Nano Banana makes images. Needs structured generator input
   (role, settings) in `deliver`.
3. **C2PA not re-applied** (no signer supplied; the shipped dev signer is untrusted anyway). A trusted signer is still an Owner item.
4. **DUPLICATED_FRAMES 7.3 %** of body frames repeat the previous one (> 5 %). The takes themselves are probably the source; the shipped
   final was never measured for this, so it is not known to be a regression.
5. **CUE_NO_SPEECH at 39.77 s and 72.03 s** – the legacy windows for SC03_g1 and SC05_g1 do not line up with audible speech in the
   mixed master; a human should listen. 8 timing WARNs from `titles` (reading speed / minimum cue length) carry over from the shipped text.
6. **Takes are not reviewed.** A picture lock needs every take accepted by a human (`lock.py`); nothing here is a creative acceptance.
7. SC08_g1 colour stays 6.76 levels off its reference after the clamp.
