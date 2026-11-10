# Drama handoff — P19 film06 local finishing verified (2026-11-10; final qualification pending)

## Goal and source
Finish Claude's existing film06 "Six A.M." local delivery and P19 scorecard. Source
`feature/drama-preprod-p0@65d7467`; original dirty stage05/06/07 and finishing artifacts preserved at
`C:/Users/ADMIN/AppData/Local/Temp/AFP-P19-20261110/claude-before-finishing/` before replacement.
Owner explicitly corrected this chat from the separate Codex Irene line, then said "Vậy tiếp tục".

## Independently established
- All17 native send/take/intent receipts agree on prompt/output hashes, model and quoted cost; all17 declared ACCEPTED
  on first send, all17 bind inside the send,118credits,0provider failures/auto-resends. Own tile identity12/17 agrees with
  the five P19-02 incidents. This is retained receipt proof, not a fresh account-balance or full-speed acting review.
- Original33-file archive verifies and both masters fully decode. `release_ready=false` has five RIGHTS_PENDING items.
- Budget criterion has a real miss:118 versus frozen expected140.3 = -15.895%, outside literal +/-15%; cap210.45 PASS.
  Preserve that baseline and FAIL_UNDERRUN result. Never generate extra takes to spend into the band.
- Finishing gaps: audio/mix.json used rough_cut.mp4 rather than the rendered graded/titled cut; portrait crop removed
  one actor from the declared MASTER opening/closing. Logged P19-03 before repair. Existing clean-render/relaid-cue path
  repairs captions; a small versions fix fits declared multi-person MASTER events, leaving singles/OTS cropped.
- Regression reproduced crop != fit before repair;30 versions/titles tests PASS after repair (134.74s).

## Finishing verification
Existing CLI chain all exit0: titles --render --color --clean-copy -> mix(titled_cut) -> mastercheck -> versions ->
dialoguecheck -> deliver -> package status. Fourteen EN cues now burn correctly in each aspect; VI remains a sidecar.
Portrait uses the hash-bound clean source, relays14cues, fits opening/closing MASTER shots with both seated actors,
and reports0BLOCK/0WARN. Reviewer independently inspected the two bookends and four caption samples.
Both delivery masters fully decode,124.625s;33-file archive hash/restore check passes after copying to C.
Fresh STT14/14 PASS, mean recall0.972. Master -14.7LUFS/-1.1dBFS peak; mastercheck retains COLOR_MATCH and three
CUE_NO_SPEECH warnings (not waived; advisory STT finds the lines). Picture lock stays fresh.62protected plan/receipt
files stay unchanged. `qc/p19_scorecard.json` and `qc/p19_completion.json` record exact scope/limits.

## Next / remaining limits
Scope-commit this verified film06 finishing and P19-03 repair, then run full qualification on the exact clean candidate.
Logs/large derived audio remain on C at `C:/Users/ADMIN/AppData/Local/Temp/AFP-P19-20261110/`; raw takes remain on D.
Original archive retained as `delivery.superseded-20261110T041616534561Z`; no footage was regenerated.
Local delivery is complete, but P19 scorecard is not an all-PASS because budget deviation is -15.895%.
`release_ready=false` has five RIGHTS_PENDING items; Owner film-level creative/release acceptance is not inferred.
No new film, generation, purchase, publication or push. P19-02 fix and automatic resend remain without new live proof.

---

# Drama handoff — P18 Flow route hardening (2026-11-09, P18-01..09)

## Goal
Make the Google Flow route run plan -> delivery with no manual step and reliable in-send binding (MiniMax/Vilao parked).

## Done (commits on feature/drama-preprod-p0, not pushed)
- 9bea690 P18-01: the video wait ends on tile PIXELS (32x18 signatures), binding only by detail-page media id + whole
  prompt (`reconcile_bind`); tokens and `video_count` removed.
- 1edc350 P18-02: a new take is named after its receipt / clip stem; historical takes keep their ids.
- 7de2689 P18-03: one auto-resend after PROVIDER_FAILED (same version, no board re-approval, every gate re-run);
  restage hint at 3 provider failures; `takes/send_log.jsonl` with times; a job with no clip after 600 s and a full
  6-page scan is FLOW_FAILED_NO_CLIP.
- d641fe0 P18-04: the 26.8% "duplicated frames" were calm frames, not repeats (takes are 24 fps, 0 repeats);
  DUPLICATED_FRAMES now counts diff <= 0.02, `low_motion_ratio` keeps the old figure.
- 2895899 P18-05: test_session_reuse_010 failures were an import path (`tests.` prefix) in the 008 file.
- 521d297 P18-06 fix: `page.screenshot` hangs on the GPM tab -> CDP JPEG capture; a crash before the prompt is
  typed is PRE_SUBMIT_ERROR (0 credits), not a charged NO_MANIFEST.
- 032d81d P18-06 live proof on film05, re-delivered.
- 4aa2f9e Codex (gpt-6.1-sol, read-only) findings fixed: a job still rendering at the deadline ends UNBOUND (no
  auto-resend, no double spend); a failed tile while a job renders is not this send's failure, baseline re-read right
  before submit; the take-number allocator counts registered ids/stems.

## P18 scorecard (cumulative, every live send since 9bea690)
| Measure | Before (film05 P17-01) | After P18 (5 sends, 2026-11-09) |
|---|---|---|
| Bound inside the send | 5/13 sends (38%) | 4/4 submitted sends (100%), all RECONCILE_PROMPT_MATCH |
| Manual step / flow_reconcile needed | 5 binds carried by flow_reconcile | none |
| Provider failures | 3/13, each a version bump + board re-approval | 0; auto-resend proven offline only |
| Sends lost before the submit | — | 1 (PRE_SUBMIT_ERROR, 0 credits, fixed 521d297) |
| Send time (submit -> saved clip) | 38-59 s token wait, then reconcile minutes later | 122-136 s |

Incident log (`films/film05_one_cup/takes/send_log.jsonl`, credits in brackets):
- 16:24 SC02_g2_t3 PRE_SUBMIT_ERROR TimeoutError [0]: `page.screenshot` hang on the GPM tab (fixed 521d297).
- 16:28-16:33 SC02_g2_t4 PASSED in-send, 127 s [7].
- 16:33-16:37 SC05_g1_t3 PASSED in-send, 122 s [6].
- 23:30-23:34 SC02_g2_t5 PASSED in-send, 128 s [7]. P18-07 took no own identity: the pre-submit pixel check
  fired on the start-frame upload (fixed 9f27434).
- 23:41-23:45 SC05_g1_t4 PASSED in-send, 136 s [6]. The own tile read "play_circle 0% ..." 8 s after the submit with
  the media id bound later, but the play-icon rule called it a stray (fixed 8479445: own = new tile showing a %).

P18-07..09 (after the first handoff): stray-job guard c04a59e + live fixes 9f27434 / 8479445; camera angle/height in
the still prompt bbc14a3; film05 low-angle v4 singles 727b62b (IRIS reads as standing; deliver 0 blocks,
dialoguecheck 8 PASS / 1 WARN). film05 spend 123/123: the cap is reached, any further film05 send is blocked.

## Open defects
- Auto-resend and FLOW_FAILED_NO_CLIP are not proven live (no provider failure happened).
- The P18-07 own-tile identity (8479445) is not proven live end to end: the film05 cap is reached. When it holds, a
  stray clip or stray failure cannot be taken for the send's; when it is missing, the prompt match + Codex guards apply.
- SC05_g1 "tea": Vosk small hears "t" (raw take "you made me", master "he made me").

## Test commands
- P18-07..09 check: uv run --frozen pytest -q tests/test_production_*.py tests/test_flow_*.py tests/test_plan_handoff_hidden_props.py (on 727b62b: 932 passed, 1 skipped)
- uv run --frozen pytest -q tests/test_flow_send_wait_p18.py tests/test_production_generate.py tests/test_production_takes.py tests/test_production_master_qc.py tests/test_production_camera.py
- Full: uv run --frozen pytest -q --ignore=tests/test_upload_state_machine_008.py (on 4aa2f9e: 2176 passed, 202 skipped; 1 fail = test_v2_010a_dola_re_001::test_05_invariants, which needs a clean tree and saw STATUS.md mid-edit; passes once committed)

## Next step
1. On the next film's sends, check `own_tile_at_submit` in each take manifest (media id taken, matches the bound
   clip) and, on the first provider failure, the auto-resend line in send_log.jsonl.
2. Start the next film on the Flow route; the chain needs no manual step.

---

# Drama handoff — film05 "One Cup", P17-01 stability run (2026-11-09)

## Goal
Make film05 end to end under OWNER_POLICY.md with no new pipeline features, and score it against the 4 P17-01 criteria.

## Result
- Delivered: films/film05_one_cup/delivery/. Masters are 16:9 and 9:16, 75.75 s.
- Audio: -14.8 LUFS, -1.7 dBTP.
- Subtitles: EN and VI SRT, with STT-timed cues in titles/cues.json.
- 9:16 framing: titles/portrait_focus.json, plus a clean copy for 9:16 subtitles.
- `deliver` ok, 0 blocks. The 5 warnings are all RIGHTS_PENDING, which is the Owner's to clear.
- mastercheck ok. Warnings:
  - DUPLICATED_FRAMES 26.8%: high, compared with 7.6% on film04.
  - CUE_NO_SPEECH at 3 cues. Vosk STT does hear those lines.
- dialoguecheck: 8 PASS, 1 WARN. SC05_g1 "tea" is clipped to "t".
- Picture lock signed agent:tech-lead.delegated-by.owner-khoikk03.
- Shots: 10 generations, all ACCEPTED by the delegated reviewer.

## P17-01 scorecard
| # | Criterion | Result |
|---|---|---|
| 1 | Zero new pipeline code apart from logged fixes | PASS: only P17-02, P17-03, P17-04 and P17-05, each logged in LOOP_BACKLOG. P17-06 and P17-07 are logged, not fixed. |
| 2 | ≥70% of shots accepted on the first send; no shot over its cap | PASS, on the line: 7/10 = 70%. SC02_g2, SC03_g1 and SC04_g1 needed a second send. None of the 3 was rejected for its content; all 3 were Flow provider failures. Counting only real attempts, no shot went over its cap. Flag: SC02_g2 and SC04_g1 were bumped to v2 with the same prompt, because the code counts a vanished job against the cap (P17-07). |
| 3 | No manual rescue of the Flow UI | PASS: nothing was driven by hand. flow_send bound only 5 of 13 sends itself; flow_reconcile bound 5 more automatically, and 3 were provider failures. |
| 4 | Spend within ±15% of plan | PASS: 91 credits sent vs 82 expected (+11%). That is 69 for accepted takes plus 22 for the 3 failed sends. Cap 123, budget 256.8. |

Verdict: **PASS with flags.** The pipeline itself is stable: planning, stills, boards, review, assembly and delivery all ran with no manual step. Flow send and bind are the weak link:
- 3 of 13 sends were provider failures.
- flow_send's own binding works on less than half of the sends; reconcile is carrying it.

## After the scorecard: live check of P17-05 and P17-07 (e50ca60)
- SC05_g1 v2 sent at 15:33 for 6 credits. The speak phase was widened to 2–4.5 s, because dialoguecheck heard "t" for "tea".
- The detail bind gave AMBIGUOUS again (video count 45→39). `reconcile_bind` then bound the clip inside the send on its first try (RECONCILE_PROMPT_MATCH) and saved it, with no separate flow_reconcile run. **P17-05 is live-verified.** P17-07 had no vanished job to prove it this time.
- The new take matches t1: Flow kept the line at 3.3–3.9 s, and Vosk still hears "t", which looks like a small-model miss.
- t2 is accepted and replaces t1 in the cut, so the cut matches shot v2. Then: re-cut, re-lock, grade, titles, mix, mastercheck ok, versions, deliver 0 blocks.
- Spend: the 6 credits sit outside the P17-01 run. P17-01 itself spent 91 (+11%); film05 total is now 97.

## Decisions + why
- Vanished-job workaround: v2 with the same prompt and a re-approved board. The peer Tech Lead says a vanished job is a provider failure and must not reset the cap; the real fix is P17-07.
- Cues are timed from Vosk word timings. The audio-window cues spanned whole clips.
- The SC02_g2 take was accepted with a minor note: HAL's out-of-focus profile drifts into frame-right.
- The cut is accepted with one WARN: IRIS's close singles at table height read as if she is seated before SC06.

## Open defects
- P17-05 / P17-07: fixed in e50ca60. The in-send bind is live-verified; a vanished job is not proven live yet.
- P17-06: a take id is numbered by register count, not by receipt. Example: take SC02_g2_t1 is file SC02_g2_t2.mp4.
- P17-07: a vanished Flow job uses up the send cap.
- 26.8% duplicated frames in the master. Not investigated; probably the Omni Flash frame cadence.

## Test commands
- uv run --frozen pytest -q tests/test_plan_handoff_hidden_props.py tests/test_production_planning.py tests/test_flow_reconcile.py tests/test_flow_bind.py tests/test_flow_send_picker.py tests/test_production_film04.py tests/test_production_generability_gate.py

## Next step
1. Decide whether the feature freeze ends. P17-01 passed, and P17-05 and P17-07 are fixed.
2. Still open: P17-06 (take id vs receipt), 26.8% duplicated frames, and a better STT model for short words.

---

# Drama handoff — film04 "Last Ticket" (2026-11-08)

## Goal
Prove the interaction contract on one exchange (SC01_g2 -> SC02_g1 -> SC02_g2), then roll out SC03-SC06.

## Done this session
- P16-04/06/07a/08/09 DONE (see docs/production/LOOP_BACKLOG.md). Pilot exchange accepted by the Owner:
  SC01_g2_t2 (SC01_g2_t4.mp4), SC02_g1_t4 (SC02_g1_t7.mp4), SC02_g2_t1. Cut: films/film04_last_ticket/media/review/cut_SC01_g2__SC02_g1__SC02_g2.mp4.
- flow_send: frame stills upload inside the slot picker (Video mode has no composer "+"); newest-item check reads only the
  list column; exceptions before the prompt Enter return PRE_SUBMIT_ERROR (0 credits).
- AMBIGUOUS sends: tools/drama_flow_ui/flow_reconcile.py binds by prompt text and downloads (0 credits).

## Decisions + why
- Stills drawn in ChatGPT (same GPM profile, new tab) when Flow stills fail review.
- Owner approvals are recorded only with quoted chat words; never --approve-storyboard.
- Test sends: 360p Omni 1.2 Flash; OWNER_GO_LIVE flipped YES/NO in one shell with an EXIT trap.

## Open defects
- MARA hair reads lighter in SC02_g1_t4 than in SC01_g2/SC02_g2 (accepted by Owner; watch identity in SC03+).
- generate payload start_frame.source text is stale ("end frame of ..."); stale end:SC02_g1 still record.
- tests/test_upload_state_machine_008.py fails collection (No module named 'tests'), pre-existing.

## Test commands
- uv run --frozen pytest -q tests/test_flow_send_picker.py tests/test_flow_reconcile.py tests/test_production_generability_gate.py tests/test_production_film04.py
- uv run --frozen pytest -q -k "generate or ledger or flow" --ignore=tests/test_upload_state_machine_008.py

## 2026-11-09
- P15-07 decided by the Tech Lead (Owner: "Tự quyết định kỹ thuật, đừng hỏi mình, tiếp tục"): choice 2 amended, see
  docs/production/FILM04_RESTAGE_PROPOSAL.md. P16-07b done offline (89f9503): SC03-SC06 = 11 generations, no RED.
- Owner delegates technical decisions; still/board/take approvals and live sends stay with the Owner.

## Next step
P16-11 DONE (boards carry a shot fingerprint; generate BLOCKs STORYBOARD_STALE). Then Owner's P15-07 restage choice -> P16-07b rollout SC03-SC06 -> P16-10 shoot.
- P16-12 DONE: SC03-SC06 stills (12, ChatGPT GPM tab) + boards approved by the Owner ('Duyệt tất cả'); SC06_g1 end
  frame added; shutter ROIs re-measured; gate3 SC03-SC06 PASS. Next: P16-10 shoot SC03-SC06 (needs OWNER_GO_LIVE per send).
- P16-10 DONE 2026-11-09: SC03-SC06 shot; all 15 film04 generations ACCEPTED. Owner accepted SC03_g1..SC05_g3/SC06
  batches; from SC04_g1 on, delegated review ("Bạn tự duyệt still, board và take (ký là agent:tech-lead, ủy quyền của
  mình) ..."), signed agent:tech-lead.delegated-by.owner-khoikk03 (qc_model now allows agent:). SC04_g3_t1 rejected (end
  state missing), t2 accepted. Fix: flow_send FLOW_FAILED ("Không thành công", no clip) no longer uses the send cap.
  Ledger 223/256.8 credits.
- Assembly: 05_edit.json drafted (15 TAKE events + title card); `film.py cut --film films/film04_last_ticket
  --accepted-only --render` -> media/cut/rough_cut.mp4, 84.7 s, -25.0 LUFS, LRA 19.5 LU. Continuity WARNs only: coins
  spread (SC04_g4) -> neat stacks (SC05_g1), an intended time skip.
  Open: mix/loudness (LRA wide, SC04 quiet shots -41/-44 LUFS), grade, titles/SRT, deliver; dialogue not
  machine-checked (no STT). Next: fine cut + mix (film.py mix/grade/titles), then deliver.
- film04 FINISHED (local delivery) 2026-11-09: 10:50 p.m. CARD added before SC06; grade (skip SC04_g2/SC04_g4: deliberate
  green lamp light); titles with explicit titles/cues.json (cue windows from the dialogue-stem activity, EN+VI SRT);
  mix -14.6 LUFS / -1.7 dBTP; picture locked by agent:tech-lead.delegated-by.owner-khoikk03 (OWNER_POLICY.md);
  mastercheck PASS (WARN: 7.6% duplicated frames, SC04_g2 colour left 28 levels off by design); versions 9:16;
  `film.py deliver` ok -> films/film04_last_ticket/delivery/ (masters 16x9 + 9x16, 86.7 s), release_ready false:
  RIGHTS_PENDING for characters/location (asset rights not cleared) - publishing stays the Owner's.
  Open: 9:16 crop is centred on every shot (no tags/reframe boxes); SFX_UNSOURCED (take sound kept); "Generated with AI"
  not translated in the VI SRT title; dialogue words not machine-checked (no STT).
- film04 SC04_g3 v2 reshoot 2026-11-09: Owner flagged the pour (jar knocked over, coins spill by themselves). Cause:
  restage text had no agent for the prop change; fix = continuity OBJECT_NO_AGENT (484473c). v2 has THEO tip and pour
  the jar with both hands; POURING is RED, Owner granted the exception ("Cho phép, quay lại", max 3 sends / 12 cr).
  t3 FLOW_FAILED (not counted), t4 (log take SC04_g3_t3) ACCEPTED by agent:tech-lead (delegated). Re-cut, re-lock,
  grade/titles/mix, mastercheck PASS (-14.7 LUFS, sync PASS), deliver ok (86.7 s); old delivery kept as
  delivery.superseded-20261109T014451541729Z. Ledger ~231/256.8 cr. Open items unchanged (9:16 centre crop,
  SFX_UNSOURCED, VI SRT credit line, no STT, RIGHTS_PENDING).
- Codex gpt-6.1-sol review of the 2026-11-09 code (read-only), all 5 findings fixed:
  (1) flow_send: a page-wide "Không thành công" no longer ends the send as FLOW_FAILED; it stops the wait and the send is
  FLOW_FAILED only if no new clip binds to its prompt (no offline test: needs a live Flow page);
  (2) generate: FLOW_FAILED sends skip the RED attempt count but still spend the exception's max_credits;
  (3+4) continuity OBJECT_NO_AGENT checks the sentence that changes the prop, cast names as whole words, no possessives;
  (5) an `agent:` reviewer must be listed in film.json `delegated_reviewers` (with the Owner's words) or ingest refuses.
- film04 polish: VI SRT title line "Generated with AI" -> "Tạo bằng AI" (titles.t_title translated only the name and hid
  other title lines; now uses LABELS or reports TRANSLATION_MISSING); 9:16 window per shot from titles/portrait_focus.json
  (new, moves only the 9:16 crop), set from a contact sheet. Re-delivered. 9:16 subtitles: `titles --render --clean-copy` renders
  media/cut/titled_cut.clean.mp4 (no cues, sha in titles.json clean_render); `versions` crops it, re-lays the 10 cues for
  9:16 and takes the sound from the master (rehearsal chain uses --clean-copy). - Dialogue STT check (advisory, WARN only): `film.py dialoguecheck --film F` transcribes each cue from the
  dialogue stem with Vosk small-en (model ~/.cache/vosk/vosk-model-small-en-us-0.15; vosk is not in the uv env, so set
  AFP_STT_PYTHON to a python that has it), word recall >= 0.8 passes, homophones/near-spellings tolerated; a stem miss
  gets a second opinion on the raw take (+-1 s). film04: 10/10 lines PASS, mean recall 0.98 -> qc/dialogue_stt.json.
- SFX sourced (2026-11-09): editornghiepdu.vn rejected for now (needs Owner account + 1M VND + Premiere panel). All 9
  film04 effects now come from Freesound CC0 HQ previews (no login), trimmed/faded to each shot into audio/sfx/<slug>.wav
  (media, not committed) and recorded in audio/assets.json (CC0-1.0, cleared, source URL + author). Re-ran mix
  (9 placed, -14.3 LUFS, TP -1.7), mastercheck PASS, versions, deliver (0 blocks), lock fresh, dialoguecheck 10/10.
- Thumbnails: low-key frames (luma 15-28) with real contrast are now lifted (eq gamma 1.45, "lifted": true) instead of
  rejected; film04 SC05_g3 thumb luma 25 -> 52, THUMB_REJECTED gone (3 thumbs). Black/flat frames still rejected.
  Still open: RIGHTS_PENDING (Owner); the SFX are not
  yet judged by ear.
