# Production upgrade plan — 2026-11-19 (proposed, awaiting Owner go)

Evidence (measured 2026-11-19 at 319892bd):
- film07 300 gens / 357 takes, first pass 221/300; film08 300 / 353, first pass 260/300; ~2120 cr per 30-min film.
- Dominant reject: off-frame person intrusion at frame edges (~45/57 film07, ~35-40/53 film08).
- film08's last 129 sends ran through six copy-pasted scripts outside the repo
  (`D:/AI FILM MAKER/_exports/FILM08_CONTINUE_20261117/flow08_live*.py`), not `afp-film generate`.
- `src/film_pipeline/agentic/` landed 2026-11-18, after film08 takes: never used live.
- Take QC records say FULL_MOTION but describe 3 sampled frames and audio "not listened to".
Independent review: `D:/AI FILM MAKER/_archive/upgrade_plan_20261119/codex_review.md` (gpt-6.1-sol, FIX_FIRST).

Order (revised after review):
1. Honest QC evidence: review level must match what was actually checked (frames sampled, audio played or not);
   the next pilot requires full playback + listening. Delivered films are not rewritten.
2. Global production halt: any account warning writes a persistent halt checked before every submit (no
   continuing on other accounts); reconcile film08 SC10_g05_t1 from its evidence, without rewriting history.
3. Off-frame intrusion prevention for NEW films: versioned default de_personify_off_frame for SINGLE/close shots,
   leak check enforced at the send boundary (not only with --critic), keeping spoken names/eyelines/OTS intent;
   films 06-08 prompt hashes pinned.
4. One sender + rehearsal: fold flow_pool_runner / flow08_live behaviour into the generate path (no new parallel
   sender); fix lease exclusivity (acquire must not hand an ACTIVE lease to a second caller); rehearse two scenes
   through the real CLI on a fake provider with crash/duplicate/warning/cap-exhaustion injection.
5. Edge-intrusion detector calibrated on labelled film07/08 rejects AND clean takes (target FN/FP rates);
   signal -> reviewed defect code -> repair, unknown codes stop. Mouth/face automation deferred.
6. Owner-authorised staged pilot (new film reserved to Owner): 360p Omni Flash, budget with retake allowance
   (50 gens ~ 360-400 cr), predefined quality/custody/halt criteria.
Deferred: moving tools/ scripts (runtime still loads tools/drama_flow_ui).
