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
