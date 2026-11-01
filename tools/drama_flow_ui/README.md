# drama_flow_ui (experimental, NOT a canonical transport)

Throwaway tools used to drive Google Flow by UI during film01. Kept for
reference only. Run everything from the repo root.

They drive the logged-in GPM Chrome over CDP at `127.0.0.1:9333`, never read,
print or export cookies, and every send spends 12 Flow credits (paid).

- `flow_host.py` - keeps a headful Chrome on the Flow profile open with the CDP port.
- `flow_tab.py` - one-shot commands on the Flow tab: shot, text, click, type (send), key, upload, attach, status, getvideo, js.
- `flow_dl2.py` - hover the gallery tile at (x, y) and download the `<video>` under it.
- `flow_attach.py` - attach uploaded ingredients to the composer by name.
- `film01_noref.sh` - text-only batch: send prompt, wait, download newest tile; prints `PASSED`, `BLOCKED`, `SEND_FAILED` or `STALE_TILE` (download sha equals the previous newest tile).
- `sb_first_day.py`, `sc03_v2.py`, `sc03_qc.py` - film01 storyboard, SC03 v2 prompts/preflight and handoff QC built on `film_pipeline.drama`.

Limits: results are correlated to a prompt only by the newest gallery tile plus
a sha change. That is weaker than the canonical `providers/flow_response` +
`flow_media` binding; WP1b will replace these tools with it. `flow_tab.py`
still imports `dola_gpm_adapter` from an external OneClick checkout (path at
the top of the file).
