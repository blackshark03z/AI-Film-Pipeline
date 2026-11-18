# Muse video gateway — parallel implementation, 2026-11-12

## Active milestone — approximately three-minute film

Owner: "tiếp tục. Mục tiêu tạo được 3p phim thử nghiệm đủ tốt, kiểm chứng khả năng tạo film dài đầy đủ".
This authorizes a new isolated Muse pilot and supersedes the exhausted one-request probe tranche below.
The system expands Six A.M. into 18 authored dialogue shots, nominally 10 seconds each, using the existing
synthetic cast/set references. Source film06 and Claude/Flow production remain untouched.

- Current tranche starts 2026-11-12 23:45 Asia/Saigon, bounded to 180 minutes / at most 30 video requests.
  Existing account entitlement only; no purchase, upgrade, top-up, paid add-on, push or publication.
- Generate one request at a time; record claim before browser action; stop on account/payment warnings.
  Restage a failed shot explicitly before a new version; no blind retry or concealed attempt reset.
- System-side camera conditioning is opt-in (`muse prepare --condition-camera`), preserves the spoken
  text, derives movement/framing from ShotDecl.camera, and records source and routed prompt hashes.
  Legacy request bundles remain readable. Static plans receive explicit locked-camera wording.
- Acceptance: approximately 180 seconds of new moving footage with a coherent beginning/turn/ending,
  all 18 planned lines represented, no title/freeze/repeated-footage padding, no unresolved P0,
  readable prop state and eyelines across joins, no invented speech, audible/natural dialogue,
  usable composition and editing. Technical checks and agent observations remain separate from
  Owner creative acceptance and any unperformed human listening/full-motion review.
- Check real clips early (wide + singles), revise the approach after two ineffective repair cycles,
  then finish the complete pilot within the tranche. Retain rejected takes and all source lineage.
- Long-film assessment: measure throughput, retries, consistency, continuity/joins, recovery and
  local finishing. A successful three-minute pilot supports feasibility; it cannot certify a
  complete 25–30 minute generated film or transfer prior Flow film acceptance to Muse.

Checkpoint: authoring package and runtime under `films/muse_pilot_three_minutes/`; main owns gateway
code/browser/verification, one bounded worker owns only that pilot package. Progress/evidence will be
recorded here and in the existing operating status at milestone boundaries.

### Live checkpoint — 2026-11-13 00:12 Asia/Saigon

- Frozen authored definition: `films/muse_pilot_three_minutes/`; reproducible `_author.py` independently
  rerun and six canonical file hashes unchanged. 18 unique shots/lines and valid planning checked.
- Runtime: `C:/film-work/muse-pilot-3m-20261112/film`; receipts/downloads under sibling `received/`.
  Browser tab: `https://muse.ai/thread/eeeb15da-a0bb-464a-abaf-2edf4f39bc7d`.
- Camera-conditioned v2 bundle SC01_g1 request
  `1d25462d9bc94c83fc2a2fb8033bd6e8c8a9d7d35c25427dc06970d1c788657e` imported as SC01_g1_t1.
  Downloaded `AFP3M_SC01_g1_v1_result.zip`: clip SHA256
  `efe9cc0d6f2e385258db109ab47adbb8569a4c46a2660e1efc795cec232ac740`.
  Native10s/24fps, static wide framing held; five ordered48-frame grids cover all240 frames.
  Vosk contraction ambiguity resolved by local Whisper small.en: planned line matches.
  Named agent review ACCEPTED; no human listening/phoneme audit or Owner acceptance claimed.
- An inherited rights-note defect found by independent review is corrected in authored/runtime data
  and reproducible authoring: pilot is an adaptation, no new Owner originality confirmation asserted.
  Exact pre-correction dispatch source retained in `C:/film-work/muse-pilot-3m-20261112/first_dispatch_source`.
- SC01_g2 request `4971784eed40b4751875b82998966ad48448429645b17e2781f5f9021a3b7ab9`
  claimed/sent at00:11, awaiting existing Muse response. Do not resend. Total new pilot dispatches2/30.
- Dual-ASR local tooling: existing Vosk bridge; cached small.en model with task-isolated uv runtime
  (`uv run --no-project --python C:/Users/ADMIN/AppData/Local/Programs/Python/Python311/python.exe
  --with faster-whisper==1.2.1 ...`).
  No repository dependency/default/auth changes. Generated `whisper.json` retains timing/confidence.
- All future within-scene shots retain canonical predecessor gates. Actual QC, not a label change,
  unlocks the next shot. No acceptance/protected preflight was weakened. Gateway focused tests18 PASS;
  full release suite has not run for this unfinished film.

---

## Approved outcome

The Owner requests a Muse video-generation gateway alongside Claude's Flow work.
The system owns screenplay, staging, shots, references, prompts, QC and editing.
Muse receives one compiled shot and returns footage; it may not re-author the film.
The MNFP v0.6.0 ZIP is reference evidence, not operating authority or master acceptance.

## Boundary and baseline

- Worktree: `C:/Users/ADMIN/.codex/worktrees/muse-video-gateway/AFP-stable`.
- Branch: `codex/muse-video-gateway`, base `fdb133c59140636c95ed961fd6ed5ffa91f46db4`.
- POLICY_REF: `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`; AGENTS blob verified identical.
- Protect Claude's source, film07 production, original film06 delivery, other worktrees and `uv.lock`.
- First execution bound: 90 minutes; at most one live video request, no blind retries,
  purchases, upgrades, top-ups, publication, push or new unattended/background jobs.
- Use existing account entitlement only. Stop at a payment requirement or account warning.
- BMAD runtime is absent in this checkout; use equivalent native implementation without installing it.

## Observed environment / open questions

Authenticated `https://muse.ai/` is an agent chat. A dedicated side chat is created.
Its capability report names `media.generate_video` with ordered text/image inputs,
`name`, `output_dir`, and `resume_from_snapshot_id`. It reports no explicit duration,
aspect, resolution, locked first/last frame, voice-reference input, or async job polling.
Approximate ten-second clips and six successes/message are reported, not yet live-proven.
Monetary price and account quota are UNKNOWN. Do not invent a public API or free price.

## Smallest implementation and proof

- [x] Freeze the operator handoff/import boundary using the existing GenerationRequest,
  plan compiler, immutable hashes, writer locks, take registration and QC pipeline.
- [x] Add focused regressions for altered shot/reference/output, replay, wrong request,
  interrupted dispatch, and honest usage/cost reporting. Run RED before implementation.
- [x] Implement a browser-assisted bridge and CLI. No new UI automation runtime or dependency.
- [x] Export one already-authored shot, invoke Muse once, download its actual attachment,
  measure it locally, import into an isolated package and obtain an unassessed take/QC template.
- [x] Review material changes once; repair interrupted staging and malformed binding paths.
  Focused shared regression and final source identity are recorded in Implementation Status.

Technical verification does not establish acting/identity/continuity quality or Owner acceptance.
No master or full automated gateway claim before the actual product journey and required gates pass.

## Operator path

```powershell
python tools/film.py muse prepare --film FILM_DIR --gid GENERATION_ID
python tools/film.py muse dispatch --film FILM_DIR --request REQUEST_DIR --backlog BACKLOG_FILE
# In the authorised Muse browser chat, upload REQUEST_DIR/handoff.zip and send relay.txt once.
# Download the actual video. Record its hash and the visible response identifying that output.
python tools/film.py muse ingest --film FILM_DIR --request REQUEST_DIR --clip DOWNLOADED_MP4 --response RESPONSE_JSON
python tools/film.py review --film FILM_DIR
```

`dispatch` is a durable **may-have-sent claim**, not an automatic browser action or a
confirmed provider job. A pending claim blocks another Muse dispatch for this film.
One dispatch per shot version; changing prompt wording does not reset the limit.
An interrupted/failed request requires manual evidence reconciliation; no retry/cancel
command or remote polling is invented. Original evidence is retained.

Response JSON requires `request_id`, `output_sha256`, `response_source` (the visible
HTTPS Muse chat URL), and `observed_output` (the exact attachment label). Optional
`snapshot_id` and `media_handle` are observations, never `provider_job_id`.
All registration is under the film writer lock. Existing Flow intents and clip names
reserve their take numbers. Full local decode and byte verification precede registration.
The new take is GENERATED; ordinary dailies/review can reject it or keep it incomplete.

`muse_requests` counts imported clips, **not money, token usage, account quota or all
attempted calls**. Submitted/unknown attempts and UNKNOWN monetary cost stay in
`media/muse/<request_id>/state.json`, outside Flow's recovery journal. No monetary
cap or production route default is changed. Intake is currently bounded to 60 seconds.

## First live proof (2026-11-12, 23:11 Asia/Saigon)

- Source: unchanged film06 SC01_g1 plan and approved still copied to isolated
  `C:/film-work/muse-gateway-20261112/film06_probe`. No prior takes/reviews/delivery copied.
- Request: `d3e2bfa448cbf8d6bb0d548c20db4e34b57e9aad2e107a73de916df7b7cd370c`.
- Dedicated browser response: `https://muse.ai/thread/eeeb15da-a0bb-464a-abaf-2edf4f39bc7d`.
- One reported generation, no retry; actual downloaded MP4 SHA-256
  `aec0bc7d1b8d260ccbe5cf8a7b6cf6ea9640ebe55ea2c76e9002839ef8edd65d`, 4,964,905 bytes.
- Local import/full decode: 10.000 seconds, 1248x704, 24 fps, H.264/AAC. Request was
  7 seconds; DURATION_DIFFERS is retained. Job ID remains empty; model remains unreported.
- Downloaded provider receipt's reported text input exactly matches the compiled prompt.
  This is provider-reported input plus operator-observed download, not server-audited lineage.
- Existing Vosk bridge hears `we closed an hour ago`; preliminary ASR, no human listening claim.
- Sampled contact sheet shows an unrequested move from the specified wide two-shot into a
  close-up of SAM. Ordinary camera QC records P1 FAIL, no waiver; take SC01_g1_t1 is REJECTED.
  Other creative groups are unassessed. This take cannot satisfy release gates.
- Raw provider receipt, operator response, screenshot, contact sheet, dailies, bound QC and
  immutable request are retained under `C:/film-work/muse-gateway-20261112`.

Next critical path: system-side Muse prompt conditioning consistent with the camera plan,
then a separately bounded retest for framing and timing. Do not copy Flow's hard first-frame
assurance into a Muse capability claim. Multi-shot identity/joins, voice consistency,
production-scale reliability, pricing/quota and unattended automation remain unqualified.

Resume 2026-11-13 06:55 Asia/Saigon: Owner said continue after the previous time window. New local work window ends09:55; total request ceiling remains30, current3. No purchase/top-up authority.
