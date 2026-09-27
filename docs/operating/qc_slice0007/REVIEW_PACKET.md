# SLICE-0007 human QC review packet

Asset: `asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01`
SHA-256: `c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf`
Video: [open exact video](../../../projects/flow_canary/outputs/95d299c70b8a5a37ec1e1fed.mp4)

## Frozen shot intent

Shot: `FLOW_CANARY_001`; purpose: Establish a quiet rain-soaked urban alley at night.
Target: 8.0s, establishing, WS, eye_level, wide, locked camera.
Environment: night, rain, quiet reflective urban alley.
Blocking: static empty alley; rain falls; distant reflected light shimmers on wet pavement; same spatial composition.
Critical invariants: no people; stable alley geography

## Evidence and gates

Contact sheet: [five timestamped frames](contact_sheet.jpg)

- 0.2s: [frame](frame_0_0.200s.jpg) · SHA-256 `245e6ec3b56d8a1d58eb70a68823bc89a78ded4dd73ee2a425e62eef792692bb`
- 2.0s: [frame](frame_1_2.000s.jpg) · SHA-256 `7d8540c92f9b91b6e968db52f6cff8da436b74fbfcdde6fdaf0f3d1f4177bf4a`
- 4.0s: [frame](frame_2_4.000s.jpg) · SHA-256 `162abbeb721ffca10102083c649a043e80ec5a1a3f41fd10a86e748ec748c545`
- 6.0s: [frame](frame_3_6.000s.jpg) · SHA-256 `e237bfad343b33ca02b3ddf76e7936b9c2e31a5a8674d61665795969536a159e`
- 7.8s: [frame](frame_4_7.800s.jpg) · SHA-256 `373bf891e0f74327b8c6c144dea1bebab9b45a27e759f4bf3b9d22c43512cd88`

Temporal signals are advisory: {"black_intervals":0,"freeze_intervals":0}

- **technical**: PASS; issues: none
- **visual**: PENDING HUMAN REVIEW; issues: VISUAL_HUMAN_REVIEW_REQUIRED
- **continuity**: PENDING HUMAN REVIEW; issues: CONTINUITY_HUMAN_REVIEW_REQUIRED
- **editorial**: PENDING HUMAN REVIEW; issues: EDITORIAL_HUMAN_REVIEW_REQUIRED

VLM run: {"cost":"unknown","input_strategy":"five timestamped sampled frames","latency_s":6.147,"model":"gemini-3.8-flash","usage":{"candidatesTokenCount":497,"promptTokenCount":5745,"totalTokenCount":6682},"used":true}

### Advisory observations

- **continuity/locked_start_end_composition**: pass; confidence 0.75; Composition and framing landmarks remain aligned from start to end. (evidence `qce_9a1dea27b5a757d00055bb8c3112d82afaadf4280556a66a7e2a06cdc62f3348`)
- **continuity/stable_alley_geography**: pass; confidence 0.75; Brick walls, fire escape, and distant street structures stay spatially consistent. (evidence `qce_8b483bbc5585d71a864b20d880ba8c5fa73a6e4146e59345a9df893f954cf381`)
- **editorial/establishing_usefulness**: pass; confidence 0.75; Atmospheric, stationary street view provides clear environmental context. (evidence `qce_a6cbabe5c7a1e46ee1a81d57e3b88923dd081936aae49ca07efd287af6ccf4a4`)
- **visual/empty_no_people**: uncertain; confidence 0.6; No people visible across sampled frames, but coverage between intervals cannot be confirmed. (evidence `qce_74c5ead0bace49f8a258b13a4dc84945351c1f4e82366653eaffb2fe7c663c66`)
- **visual/establishing_wide_framing**: pass; confidence 0.75; Frame captures a wide perspective of the full alley corridor and flanking buildings. (evidence `qce_c0cced55fbbc02b619978e5b4b66b797d746b95f09733dbcb69667301c859211`)
- **visual/night_rain_alley**: pass; confidence 0.75; Dark sky, artificial lighting, wet cobblestone ground, and visible falling rain. (evidence `qce_3bbc399f641990811cdda8c779165ce83b26bc1ba77ebdfa665f571852ad17b4`)

## Owner decision

Choose **APPROVE**, **REJECT**, or **NEEDS_REVIEW** after viewing the exact video and evidence.
APPROVE requires all visual, continuity and editorial criteria to pass. REJECT requires a failed gate and structured failure code. Technical or critical continuity failure prevents SelectedTake. No repair generation is authorized here.

Current report: `qcr_fa1ef8247c17b733d2a010a7f090dc847404d3f9954b9163bbc521d4b8e9c86d` · `needs_human_review`

Measured local QC wall clock: 9.410s; human review minutes: unknown; total cost: unknown.
