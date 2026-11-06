# Current continuation — 2026-11-06

For the currently authorized task, follow [E2E_NEW_CHAT_HANDOFF_20261106.md](E2E_NEW_CHAT_HANDOFF_20261106.md) and the canonical root operating files at D:/AI FILM MAKER/AI-Film-Pipeline/docs/operating/. The Goal is the production system with enough real media proof, not full-film shipment. The dated no-Generate statements below describe earlier packaging/qualification work; they do not cancel the later bounded I2 motion canary.

Video scope is GPM `wanglin08ma`; ChatGPT image scope remains `nethaolabycss222@gmail.com`/tab2. The native Frames canary is not a qualification of this guide's generic Ingredients/R2V CLI on the new account. Keep the existing locked plan/database and old account-bound IDs intact. Update2026-11-06: Owner-approved GPM API/CDP recovered access. One I2 canary in wanglin08ma@gmail.com, project e44c1f2a-856a-4bde-b88b-e18baead096a, produced output5c8e38b1-1cf3-4fb7-bb28-c63907a00e6f. Exact acquisition/full decode PASS; physical backward recoil FAIL. Balance1050→950;7.93s generated,0selected. See projects/e2e_badge_20261104/PUSH_I2_WANG_20261106_RESULT.json and REVIEW.json. No automatic retry; original runtime and Owner acceptance unchanged.

---

# Local narration film runner

`tools/film_e2e.py` prepares a human-reviewed, resumable local project. It keeps the original audio and SRT, uses the existing Flow runtime SQLite evidence for selected shots, and refuses incomplete or changed sources.

Use a short Windows project path such as `D:\film-work\film-01`: long nested paths plus immutable receipt filenames can exceed Windows' path limit. Python 3.11+, the dependencies in `pyproject.toml`, and `ffmpeg`/`ffprobe` on PATH are required. The optional `flow` dependencies are needed for live browser dispatch; browser credentials are never bundled.

## Prepare

```powershell
python tools/film_e2e.py prepare --audio D:\media\audio.mp3 --srt D:\media\captions.srt --start 0 --end 57.44 --out D:\film-work\film-01
```

The source interval must be 30–60 seconds. The command copies and hashes both source files and creates the project runtime database. It drafts eight to twelve timeline windows with their overlapping SRT text. Edit contiguous shot boundaries in `shots.json` to follow the narrated actions, and fill `visual_intent`, `image_prompt`, and `video_prompt` for every shot. Before first lock, `resume` refreshes `source_text` from the exact SRT and edited boundaries without changing your prompts. Locked plans remain immutable; `status` only reports any source-window mismatch. The text windows help editing; they do not claim semantic interpretation or visual coverage.

New projects use plan version 2. Fill `blocking.start`, `blocking.end` and the existing `continuity.start_state` / `end_state` dictionaries for each shot. `video_prompt` remains the main action; optional `blocking.action_beats` add ordered detail rather than replacing it. `previous_shot_id` is drafted in timeline order. Resume refuses blank direction or explicit adjacent-state conflicts before locking or generating. Version 1 projects remain readable with their exact historical ShotSpec identity; `legacy_direction_unassessed` flags missing direction without rewriting their locked plans or receipts.

### Direct the whole interaction

Write what **each participant** does before, during and after contact. For a shove, the initiator extends the arm, transfers force, then withdraws the hand; the receiver displaces, contacts the obstacle, absorbs the stop and steadies. A hand left pushing is a different relationship from a completed shove. For an object transfer, track giver → receiver → final location, including the now-empty hand. Quiet dialogue still needs clear gaze, spacing and end state.

Use short, consistent state keys across cuts, for example `hand_contact: false`, `badge_holder: "bin"`, `receiver_pose: "braced"`. Reuse the same key when a relation persists: the existing sequence validator compares explicit shared keys; it does not infer that differently named keys mean the same thing or detect facts you omitted. Include both actors, props and important spatial relations. Avoid a generic `hold` end when a release or recovery must occur.

```json
{
  "video_prompt": "A shoves once, then withdraws his hand. B hits the counter and steadies.",
  "blocking": {
    "start": "Both apart, B beside counter",
    "end": "A arm at side; B braced at counter"
  },
  "continuity": {
    "screen_direction": "A right, B left",
    "eyeline": "at each other",
    "previous_shot_id": null,
    "start_state": {"hand_contact": false, "receiver_pose": "upright"},
    "end_state": {"hand_contact": false, "receiver_pose": "braced"},
    "critical_invariants": []
  }
}
```

The next shot must start from the same released contact and braced pose, then perform its own recovery. Audit the neighboring shots before spending another attempt. Keep the provider prompt within its existing 500-character / 75-word creative-body limit; shorten repeated styling before dropping an essential release or reaction. Do not enlarge the limit or silently truncate direction.

Make the first reference show the pre-action state. If operating native first/last frames, the last reference must show the **completed** interaction (hand withdrawn, receiver settled), not the peak contact pose. Otherwise the endpoint itself orders the model to keep pushing. These native manual artifacts are not automatically integrated into the generic R2V runtime.

Review the actual video from anticipation through recovery and across the cut. `status` supplies `direction_to_review`, including intended end state and the next shot's start state, beside each exact acquired Asset. Mark a held hand, lost object ownership, unexplained side switch or mismatched recovery under the existing continuity/editorial gates. Filled state fields and structural validation are planning proof only; no code here understands whether a rendered hand actually withdraws. Keep narration facts separate from Owner-directed staging and from unreviewed suggestions. A review rejection never becomes PASS because export/decode works.

Create a ChatGPT reference image in the selected GPM profile (`nethaolabycss222@gmail.com`, second tab). A reference can cover several shots when it is intentionally shared. Record its downloaded-file SHA-256, ChatGPT chat URL and shot IDs in a UTF-8 JSON file:

```json
{
  "profile_email": "nethaolabycss222@gmail.com",
  "tab_index": 2,
  "images": [
    {
      "shot_ids": ["SHOT_01", "SHOT_02"],
      "path": "D:/downloads/shot-01.png",
      "sha256": "<64 lowercase hex characters>",
      "chat_url": "https://chatgpt.com/c/<conversation-id>"
    }
  ]
}
```

Include only the shots covered by images currently available. The CLI checks the account and tab labels, URL form, source file and bytes, then stores immutable hash-bound receipts separately from `shots.json`. These fields preserve an operator receipt; they do not independently attest browser login or image generation. References can be added in later `resume` calls without changing the creative-plan hash.

## Continue and inspect

```powershell
python tools/film_e2e.py resume --project D:\film-work\film-01 --project-id <exact-flow-project-id>
python tools/film_e2e.py status --project D:\film-work\film-01
```

Resume locks the reviewed shot plan as soon as every shot has a human-written visual intent and prompts. It then accepts partial reference receipts and checks existing Flow runtime records. Use `references_for_shot(project, shot_id)` before dispatch to verify that the current shot has a valid reference; a shared reference may cover multiple IDs. Every selected shot must resolve to the locked ShotSpec, exact Flow project and provider, current acquired media, passing QC, and human selection in the runtime database. An interrupted or incomplete Flow submission stays unresolved in that provider runtime; the CLI never synthesizes success or dispatches another request.

`status --project` infers the Flow ID locked by `resume` and reads the project's `runtime.sqlite` without initializing or changing it. If you explicitly used a different database, keep supplying `--db <path>`; the Flow ID is still inferred. A conflicting `--project-id` is rejected. Use the project-local database for the normal journey.

`status` emits a pending `review_template` for each exact, acquired Flow Asset. Save it as `review_manifest.json` and fill `reviewer_id`, `visual_pass`, `continuity_pass`, `editorial_pass`, and explanatory `notes` after watching those exact clips. A false gate also requires its specific `failure_observations` entry. Do not edit asset identity fields. Resume with `--review review_manifest.json`; the CLI checks the exact Flow project, ShotSpec, acquisition record and current media hash, then records the HumanDecision and QC report in SQLite. No review is approved by default.

Add references after creative-plan lock with `--references`. Shared references can cover a list of shot IDs; each requested shot must have a valid reference before its dispatch. The optional existing-profile hook is explicit: `--flow-profile D:\path\to\profile --shot SHOT_01 --shot SHOT_02`. Without both flags, resume only reconciles and never submits. Check current Flow authentication and quota before a submission; the CLI never purchases credits or switches accounts.

For an Owner-rejected clip, `resume --review` returns its `repair_decision_id`. A changed request uses a separate JSON file, for example:

```json
{"shot_id":"SHOT_08","spec_version":2,"repair_decision_id":"<stored repair ID>","reference_sha256":"<downloaded image SHA-256>","framing":"WS","video_prompt":"<changed action direction>"}
```

Run `resume --project ... --project-id ... --flow-profile ... --shot SHOT_08 --repair repair.json`. The new image must already have an explicit receipt covering that shot. The original plan and attempt remain immutable. Each new version needs its exact resolved Flow predecessor and explicit Owner rejection; an ambiguous job cannot authorize repair. Duplicate/resumed versions retain the same job, the total cap stays 14, and no take is approved automatically. Use at most two repair versions per shot; reassess the approach after repeated failure instead of replaying it.

## Finish

```powershell
python tools/film_e2e.py finish --project D:\film-work\film-01 --project-id <exact-flow-project-id>
```

Finish requires exactly one currently approved, QC-passing take for every shot. It rechecks each source hash, trims takes to the shot timeline using the editorial manifest, renders the video, removes provider audio, and muxes the selected original-audio interval. It produces an H.264/AAC 16:9 720p-or-higher master with an English subtitle track, a matching excerpted SRT, and `delivery.json` with source and output hashes. An existing master or receipt is read back and verified; unreceipted files are never overwritten.

It also creates `delivery/` containing `master.mp4`, `captions.srt`, `provenance.json` and the existing DeliveryManifest format in `manifest.json`. Copy that directory anywhere, then verify it without the original project, database, browser or credentials:

```powershell
python tools/film_e2e.py status --package D:\handoff\delivery
```

This checks manifest identity and every declared file hash; missing/changed files return `FAIL` and a nonzero exit code. Export performs full decode; portable status is an integrity check, not a second creative or decode review. Existing mismatched package files are refused rather than overwritten. The delivery directory supports playback and provenance readback; it does not relocate the production runtime's absolute source paths. Continue production in its original project folder.

Use `--trim SHOT_05=1.5` when an action happens later in the generated clip: the timeline duration stays fixed, but that shot starts 1.5 seconds into its source. Repeat for other shots. Unknown shot IDs, duplicate offsets, non-finite times and ranges past the source duration are rejected. Keep the same trim arguments when reopening the same export; changed edit ranges produce a different manifest and cannot silently replace an existing master.

This is local operator tooling. PRODUCT PASS requires watching the rendered film in full and checking story coverage, continuity, motion, props, audio and subtitle timing. Technical success does not grant Owner creative or public-release acceptance.

## Production-system increment, 2026-11-04

The Owner changed this increment's completion unit to the production system, not film shipment. See [E2E_SYSTEM_HANDOFF.md](E2E_SYSTEM_HANDOFF.md) for the bounded result, proof and remaining limits. No further provider generation is authorized for this increment.
