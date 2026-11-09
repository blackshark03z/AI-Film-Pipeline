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
  Still open: RIGHTS_PENDING (Owner); THUMB_REJECTED WARN for SC05_g3 (dark frames, pre-existing); the SFX are not
  yet judged by ear.
