# WP5 — conditioning A/B on film01 SC03_g2

One 8 s generation per arm (Flow, Omni 1.1 Flash, 720p, 12 credits each; 48
credits total). Same beat for every arm: NORA gathers the torn letter from the
counter, pockets it, looks at DOYLE. Prompts: `prompts/` (built by
`tools/drama_wp5_prompts.py`); takes and custody manifests: `takes/`
(`*.take.json`, all `NETWORK_PROMPT_MATCH` via `tools/drama_flow_ui/flow_send.py`);
signals: `measure.json` (`tools/drama_wp5_measure.py`).

## Results

| Arm | Conditioning | Words | Visual verdict | NORA id vs film01 (mean / head) | Self id NORA / DOYLE | Set vs g1 (inliers / HSV) |
|---|---|---|---|---|---|---|
| A0 | text only (accepted take) | ~130 | usable; background drifted (EXIT sign lost) | 0.515 / 0.54 | 0.68 / 0.84 | 11 / 0.29 |
| R1 | rich text: locked location + choreography | 165 | usable; EXIT sign, clock, portraits kept; single shot | 0.478 / 0.69 | 0.89 / 0.90 | 5 / 0.21 |
| V1 | + SC03_g1 video as ingredient | 132 | reject: NORA hair drifts, room changes, DOYLE lost | 0.483 / 0.70 | 0.84 / — | 8 / 0.62 |
| P1 | + empty-set plate (Flow image) as ingredient | 137 | partial: set matches the plate, but the model cut wide → insert → CU | 0.496 / 0.62 | 0.54 / 0.42 | 6 / 0.44 |
| F1 | start frame (Flow image: plate + look text), "Khung hình" mode | 134 | **best**: one continuous shot, set locked, both people stable, each action once | 0.459 / 0.50 | 0.56 / 0.84 | 5 / 0.37 |

Set/identity numbers are WARN-level assists. They compare against film01's
SC03_g1, which F1 and P1 do not continue (their start image defines a new
room and new faces), so a low film01 score there is expected, not drift. F1's
lower NORA self score comes from her looking down at the counter (profile),
checked on the frames.

## Decisions (Tech Lead)

1. **Default route for drama generations: start frame + "Khung hình".**
   Per generation: a Flow image (Nano Banana 2.1, **0 credits**) built from the
   location plate and the look text, QC'd as a still, then the video from it
   (12 credits). The still is the cheap place to reject set/identity errors.
2. **Locked location text stays in every prompt** (R1 proved it carries the
   invariants even text-only); the start frame does not replace it.
3. **Video ingredient (V1) is not used** for continuity: it drifts identity
   and set.
4. **Plate as an ingredient (P1) is not enough on its own**: it holds the room
   but not the shot plan. Plates are inputs to the start-frame image instead.
5. **Prompt budget: 170 words** for the compiled drama prompt (R1 at 165 words
   passed preflight and was followed). The Dola-era 120 was an assumption.

## Capability manifest (measured vs assumed)

| Capability | Status |
|---|---|
| Output bound by network response (prompt ↔ token) for video and image jobs | measured (6/6 PASSED) |
| Image mode costs 0 credits; full-res output via `flow-content.google/image/` | measured |
| Video "Khung hình" start-frame slot accepts gallery images | measured |
| "Thành phần" accepts video and image ingredients | measured |
| Uploading a local file opens a usage-rights dialog | measured; needs the Owner's consent per upload, not given by the agent |
| Video ingredient preserves identity | measured: no |
| Illustrated character refs already in the Flow project as start-image ingredients | assumed; tested in WP7 |
| End-frame slot ("Kết thúc") for handoffs | assumed; not tested |
