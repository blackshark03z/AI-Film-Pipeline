# INC-001 - two stray video jobs while drawing SC03 stills (2026-11-12)

- Cause: a scratch still-maker (outside the repo) toggled image/video mode by screen coordinates; the composer was in
  video mode, so two stills were submitted as 6 s Omni 1.2 Flash 360p video jobs instead of Nano Banana images.
- Cost: 12 credits (2 x 6). Not a take, no receipt: `money_ledger` (takes + intent receipts) does NOT include them.
  Real account spend = ledger spent + 12. Flow balance read 2026-11-12 (avatar menu): 55.
- Fix: stills now go through DOM-driven `_ensure_radio` with a "Nano" chip abort before submit; `flow_send` forces the
  video sub-mode (7b4f0ae, tests/test_flow_send_video_mode.py).
- Binding: video sends bind by media id plus prompt text (`RECONCILE_PROMPT_MATCH`); the stray clips carry still prompts,
  never an SC03 video prompt, so they cannot be taken for a take. Their media ids were not captured.
- Cap: film.json budget.credits_estimate raised 356.67 -> 2140 so the cap is the Owner-approved full-film 3,210
  (pilot cap 535 was exhausted at 534). Approved by the coordinator session 2026-11-12.
