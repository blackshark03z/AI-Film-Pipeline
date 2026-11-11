# drama_flow_ui (experimental, NOT a canonical transport)

Throwaway tools used to drive Google Flow by UI during film01. Kept for
reference only. Run everything from the repo root.

They drive the logged-in GPM Chrome over CDP at `127.0.0.1:9333`, never read,
print or export cookies. Video sends spend credits; price depends on duration/model and the live quote. Production uses
`film.py generate`, which reserves the registry quote and passes `--expected-credits`; the sender refuses before Submit
if the final composer quote (after frames/ingredients) is missing or different. No silent price/cap increase is allowed.

- `flow_host.py` - keeps a headful Chrome on the Flow profile open with the CDP port.
- `flow_tab.py` - one-shot commands on the Flow tab: shot, text, click, type (send), key, upload, attach, status, getvideo, js.
- `flow_dl2.py` - hover the gallery tile at (x, y) and download the `<video>` under it.
- `flow_attach.py` - attach uploaded ingredients to the composer by name.
- `flow_send.py` - one send (video or `--image`, optional `--attach tok:TAIL`, `--start tok:TAIL` for "Khung hình"), with media/prompt binding and atomic `<out>.take.json` checkpoints. Image mode was measured at0credits; pass `--expected-credits 0` when relying on that quote. A changed/missing quote refuses before Submit. A failed job can leave the start slot filled, which the next send clears.
- `film01_noref.sh` - text-only batch: send prompt, wait, download newest tile; prints `PASSED`, `BLOCKED`, `SEND_FAILED` or `STALE_TILE` (download sha equals the previous newest tile).
- `sb_first_day.py`, `sc03_v2.py`, `sc03_qc.py` - film01 storyboard, SC03 v2 prompts/preflight and handoff QC built on `film_pipeline.drama`.

Limits: `film01_noref.sh` correlates a result only by the newest gallery tile
plus a sha change; use `flow_send.py` instead. Neither is the canonical
`providers/flow_response` + `flow_media` transport. `flow_tab.py`
still imports `dola_gpm_adapter` from an external OneClick checkout (path at
the top of the file).
