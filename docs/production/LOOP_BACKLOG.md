# Loop backlog — E2E production system

OWNER_GO_LIVE: NO
<!-- 2026-11-07: Owner authorised P3-05 only in chat ("cho phep tat ca", "Duyet ca hai", "Cho gui lan hai"); Claude set YES for each canary send and back to NO right after it. P8-02 stays locked. -->
<!-- Owner flips to YES to allow LIVE items (real Flow/ChatGPT generation). Tech Lead never flips it. -->

## Loop outcome (2026-11-07): STOPPED - no READY item left

P0-P11 are DONE offline. Only two items remain and both are **LIVE** (need `OWNER_GO_LIVE: YES`, written by the Owner): **P3-05**
(one canary generation, Omni Flash 360p) and **P8-02** (film04: 12 generations, expected 171.2, cap 256.8 credits). Test and
canary videos use Omni Flash at 360p (Owner, 2026-11-07). P11 (Codex review follow-ups) closed in 8 commits: P11-01 9:16 label
(37b7813), P11-02 label pixel check (2a866de), P11-03 gate 4 (8ddd638), P11-04 gate 3 (3a71668), P11-05 disclosure policy
(98aeab3), P11-06 still decode (db60d67), P11-07 `edit --init` / `generators --init` (52b14cf), P11-08 rehearsal restore check
(e666c5d). The loop restarts when the Owner flips the go-live line or adds a READY item.

## Phase P10 — Ship readiness (Tech Lead plan, 2026-11-07), closed

P0–P9 built every stage offline; film04 is authored to gate 2 + plan. **Ship** = a new film goes from package to a delivered
master using only `film.py` commands and Owner checkpoints, with no per-film code, and the Owner accepts it. What stands in
the way, in order: (1) gates 3/4/6 report `NOT_RUN` instead of a verdict; (2) there is no package step for start stills, so
`generate` cannot run from the package alone; (3) delivery regressions found by P7-02 (AI label, generator roles);
(4) the whole chain has never run on a *new* film, only on film03's legacy takes; (5) no operator runbook / Owner review pack;
(6) P5–P9 never had an independent review. P10 closes these offline. After it, only Owner decisions and LIVE items remain
(P3-05 canary → P8-02 film04 production).

Owner decisions still open (product only): `OWNER_GO_LIVE` for P3-05/P8-02 (film04 plan: 12 generations, expected 171.2,
cap 256.8 credits); film04 storyboard approval, originality/rights; AI label always-on vs title card only; trusted C2PA signer;
215-word limit; creative review of film02/03; 117 MiB history cleanup.

Status values: READY · IN_PROGRESS · DONE (commit, result) · BLOCKED (cause) · LIVE (needs OWNER_GO_LIVE: YES).
Protocol: [LOOP_PROTOCOL.md](LOOP_PROTOCOL.md). Plan: [E2E_PRODUCTION_PLAN.md](E2E_PRODUCTION_PLAN.md).
Category IDs refer to the Owner's 168-item list; tick them in `CATEGORY_COVERAGE_168.md` when closed.

---

## P0 — Foundation

### P0-01 Coverage matrix on this branch — DONE (3ea43e9: 168 rows; HAVE 14 / PARTIAL 79 / GAP 49 / N/A 26; every GAP mapped to a backlog item)
Create `docs/production/CATEGORY_COVERAGE_168.md`: one row per category 1–168 (keep Owner's numbering/names), columns
`ID | Category | Responsibility (code path / package field / operator receipt / N/A+reason) | Status (HAVE/PARTIAL/GAP/N/A) | Backlog item`.
Seed from root `D:/AI FILM MAKER/AI-Film-Pipeline/docs/research/E2E_FILM_CATEGORY_MATRIX_168_20261104.md` (read-only;
its B01–B08 = modules now on this branch) and from `src/film_pipeline/drama/*`, `e2e*.py`, `editorial.py`,
`rough_cut.py`, `delivery.py`, `qc.py`. Map every GAP to a backlog item ID below (or add a new item at the end).
Done: 168 rows, no row without status, summary counts at top. Docs only, no tests.

### P0-02 Production package schema + loader — DONE (c87ac17: 8 tests; focused suite 267 passed, 1 skipped)
New package `src/film_pipeline/production/` with `package.py`: pydantic models for `film.json` (film_id, title,
profile `drama|narration`, language, aspect, fps, resolution, generation_s=8, budget {credits_estimate, cap_factor=1.5},
gates {1..6: PASS|BLOCK|OWNER_PENDING|NOT_RUN}), and **stage files as optional sections** `01_story.json` …
`07_delivery.json`, `ledger.json` (start with permissive `dict` placeholders for stages not yet designed; P1+ items
replace them with typed models). `load_package(path) -> FilmPackage` validates JSON, resolves `script.fountain` via
`drama.script.parse_fountain`, and reports missing stages. `films/.gitignore` ignores `*/media/`.
Tests `tests/test_production_package.py`: round-trip, missing film.json error, unknown profile rejected, missing
stage reported not raised. Done when tests pass.

### P0-03 `tools/film.py` CLI skeleton — DONE (9dccb51: 5 CLI tests; focused suite 272 passed, 1 skipped)
Subcommands `new <film_id> --profile drama|narration` (scaffold package with empty stage files),
`validate --film DIR` (runs all available gates, prints JSON {gate: status, issues[]}, exit 1 on BLOCK),
`status --film DIR` (stages present, gates, counts). Pattern: `tools/film_e2e.py`. Tests: subprocess `new` then
`validate` on the scaffold → exit 1 with "story missing" style issues, not a crash.

### P0-04 Port film03 declarations into a package — DONE (dba8082: sections.py typed 02/03/04; 7 parity tests; focused suite 279 passed, 1 skipped)
Move the data in `tools/drama_film03.py` + `tools/drama_film03_story.py` (looks, locations, axis books, positions,
prop states, occupancy, story time, shots, choreography, SFX, voices, cards, facts, tags) into
`films/film03_front_desk/` JSON (03_preprod.json / 04_shots.json / 02_direction.json as fits; extend schema in
`production/` with typed sections that **reuse** `film_pipeline.drama` models). Do not modify the original tools or
`docs/drama/film03/`.
Done when `load_package` loads it with zero schema errors.

### P0-05 Generic `plan` stage reproduces film03 — DONE (4054a2e: golden = 16 prompts + 21 stills + gate3 byte-identical; full suite 1444 passed, 194 skipped, 2 failed — test_dispatch_recovery F0/F1 spawns `python -c` without PYTHONPATH so `film_pipeline` is not importable (env, pre-existing); test_v2_010a_dola_re_001::test_05_invariants fails while the tree has non-Dola dirty files)
`production/plan.py` + `film.py plan --film DIR --out DIR`: generalise what `tools/drama_film03.py` does (feasibility,
preflight per generation, handoffs, compile prompts via `drama.prompt.compile_scene_prompt`, still prompts,
schematic storyboard, gate3 json) driven only by package data.
Golden test `tests/test_production_film03_golden.py`: every prompt/still file **that `tools/drama_film03.py`
itself writes** (determine the set by reading the tool; `docs/drama/film03/prompts/` has 20 files for 16
generations, so some come from other steps — list those as out of scope with the reason) is reproduced
byte-identical from the package (normalise line endings only). Any unavoidable difference must be
listed in the test as an explicit expected diff with a reason — none expected. This is the P0 exit criterion.
Phase end: full suite, push, IMPLEMENTATION_STATUS row.

## P1 — Story & Direction (categories 1–34)

### P1-00 Review follow-ups for P0 (Codex gpt-6.1-sol review, 2026-11-06) — DONE (36de9b7: evidence.py, ShotDecl.dialogue, accepted_overlong; 12 tests; focused suite 305 passed, 1 skipped)
Run before P1-01. Fixed already in this review pass: storyboard approval is opt-in (`--approve-storyboard`), `plan` exit code
aggregates every BLOCK, cross-reference/id/predecessor validation, path-escape guard, aspect refusal, `new` never overwrites,
`validate` fails on package issues, golden text comparisons independent of Pillow, matrix rows 18/20/37/52, media untracked.
Remaining (do all three; no weakening of film03 parity):
1. **Explicit dialogue per generation.** Replace "generation k speaks the k-th line" with `ShotDecl.dialogue: list[int]`
   (script line numbers, `[]` for silent shots) and a check that every scripted dialogue line is assigned exactly once.
   Port film03 so prompts stay byte-identical. Today only a count check exists (`DIALOGUE_UNASSIGNED`).
2. **`end_state_verified` from QC evidence, not file existence.** Derive it from a take record (`<gid>.take.json` /
   `HandoffQC`) bound to the take's sha256 and the expected end state; a bare or empty `.mp4` must not verify.
3. **Word limit on the emitted text.** Preflight checks `compiled_text`, but `plan` writes `START_PREFIX + compiled_text`
   (film03: SC02_g2 212 -> 222 words vs limit 215; 3 more prompts over). Measure the emitted text; for film03 record
   the four shipped prompts as an explicit, documented exception in the golden test (they are accepted, shipped footage)
   rather than changing their bytes. Report to Owner if the limit itself should move.

### P1-01 Story bible model + Gate 1 — DONE (4d92f24: story.py, gates built-in + OWNER_PENDING, film03 01_story.json; 22 tests; production+drama suite 263 passed)
Typed `01_story.json`: concept, theme, genre, audience (who/expectation), premise + central conflict, logline,
structure (acts with beats: id, function SETUP/INCITING/ESCALATION/MIDPOINT/CRISIS/CLIMAX/RESOLUTION, scene ids),
plot + subplots, characters (want, need, flaw, arc_change, change_scene_id), scenes (purpose, conflict, outcome,
value shift +/−), adaptation {source, rights_status, fidelity_notes}, rewrite log.
Gate 1 BLOCK rules: every scene has purpose/conflict/outcome and appears in ≥1 beat; every beat function in order;
each protagonist arc has a change scene that exists; logline names protagonist + goal + obstacle; adaptation with
`rights_status != cleared` → OWNER_PENDING (not PASS). Fill film03's story file from its Fountain/README.
Tests with good/bad fixtures.

### P1-02 Director's treatment + per-scene direction — DONE (091786f: direction.py, Gate 2 built-in, film03 02_direction.json; 18 tests; production+drama suite 281 passed)
Typed `02_direction.json`: vision (tone, references as words), visual language rules (list of rule + why),
per scene: POV (whose, what audience knows vs characters — tie to `comprehension` facts), dramatic emphasis
(moment, device: insert/push/hold/reaction), emotional curve (start/end intensity 0–5 per character), pacing
(target avg shot length, hold points), transitions in/out (cut/dissolve/match/J/L + reason), coverage plan
(required shot types per beat). Checks: emotional jump > 2 between consecutive scenes without a cause beat → BLOCK;
every beat has ≥1 carrier shot in 04_shots (Gate 2, reuse `drama.coverage`/`comprehension`); every reveal has an
emphasis device. Fill for film03.

### P1-03 Director playbook — DONE (5e97e02: docs/director/DIRECTOR_PLAYBOOK.md + .claude/skills/film-director; docs only)
`docs/director/DIRECTOR_PLAYBOOK.md`: how the model authors each stage file, in order, with decision checklists
mapped to categories 1–56, lessons from `docs/drama/FILM01_LESSONS.md`, film02 comprehension failure, film03 README,
WP5 route, Owner SRT faithful-action rule (`docs/sot/film/05_PROMPT_COMPILER.md` in the root repo), provider limits
(8 s generations, start frame route, prompt budget 170 words, moderation notes in memory `flow-picker-and-moderation`).
Include a worked example (film03) and "red flags" list. Also `.claude/skills/film-director/SKILL.md` pointing to it
(name, description, when to use). No code.

### P1-04 Narration profile adapter — DONE (1150361: production/narration.py, gates by profile, film.py narration; 12 tests; full suite 1476 passed)
For profile `narration`, `film.py` wraps `e2e.py` (prepare/status/resume/finish) so a narration film is a package too:
story beats come from SRT sentences (`drama.action_meaning.sentences`), shots carry `action_meaning`. Test: package
built from the E2E test fixture validates and `status` matches `e2e.status` fields.

## P2 — Pre-production (35–56)

### P2-01 Design versions + dependency index — DONE (a5919bc: sections.DesignEntry + pins, impact.py, film.py impact, film03 designs; 12 tests; focused suite 364 passed)
Character look, costume, hair/makeup, prop and location entries carry `version`; shots reference `id@version`.
`production/impact.py`: `affected_by(change) -> shots, stills, takes, edit ranges, post items` (G13).
Test: bump film03 Nora costume version → exactly the shots where Nora is in frame are listed; others untouched.

### P2-02 Prop/object state machine + 6 continuity types — DONE (6a9afac)
Continuity bible: per generation start/end state across action, spatial, object, temporal, visual (lighting, time of
day), emotional. Object changes need a causing action in an ACTION phase. Reuse `drama.continuity`,
`scene_bible`, `sequence.validate_shot_sequence`. Test: letter moves pocket → bin without an action → BLOCK.

### P2-03 Camera & lighting plan — DONE (f1c015c)
Per scene: key light direction/quality/colour temp, practicals; per shot: size, angle, height, movement, lens intent,
composition note. Check against axis book (camera side) and shot-size variety (no 3 identical sizes in a row unless
declared). Compiled into prompts only where the route supports it (document which fields reach the prompt).

### P2-04 Animatic — DONE (20223f4)
`film.py animatic`: storyboard frames (schematic or approved stills) timed to the planned durations with temp
dialogue/narration audio when available (TTS optional, offline-only libs; otherwise silence + subtitles), FFmpeg mp4
under `films/<id>/media/animatic.mp4`, plus timing report. Gate 3 input. 0 credits. Test with tiny fixtures.

### P2-05 Budget, schedule, risk, legal — DONE (a0df6aa)
Estimate credits = generations × cost/gen × expected retake factor (from KPI ledgers film01–03), schedule order
(dependency: start frames before videos), risk list (physical contact/interaction shots flagged with fallback
coverage plan), legal: character/location/music/source rights entries. `validate` shows budget and risks.

## P3 — Production (57–90, 131–140 shot level)

### P3-01 QC taxonomy P0/P1/P2 — DONE (98a3d31)
`production/qc_model.py`: QC record per take with the 16 groups 131–146, each `PASS/FAIL/UNASSESSED`, severity
P0/P1/P2, level `STILL|SAMPLED|FULL_MOTION|CUT`, evidence path, reviewer (`human:<id>` or `auto:<tool>`).
Rule: auto tools may only produce WARN/UNASSESSED for content groups; only a human review can PASS
narrative/action/motion/performance. Shot accepted iff no P0 FAIL and P1 FAILs explicitly waived with reason.

### P3-02 Take log + dailies review — DONE (2088e85)
`takes/` index: take id, generation id, prompt hash, start-frame hash, model/route, credits, output hash, status.
`film.py review --film DIR` writes a dailies template per new take (QC groups, the shot's `qc_questions` from
action_meaning, choreography timing, expected start/end state) and ingests a filled one. Integrate
`drama.autoqc` as WARN evidence when models are available (skip cleanly when not).

### P3-03 Retake / pickup policy — DONE (6bbaa40)
After a FAIL: classify cause (prompt, start frame, provider limit, staging). Same cause twice → propose change of
approach (re-stage, split into two shots, insert/reaction coverage, different start frame) instead of retry;
pickup list feeds back into 04_shots as new shot versions with `repair_of`. Tests on synthetic take logs.

### P3-04 Generate stage via package (offline mock) — DONE (19787fd)
`film.py generate --film DIR --shot ID --dry-run` builds the exact send payload for `tools/drama_flow_ui/flow_send.py`
(start frame + "Khung hình" route) and records an intent receipt; without `--dry-run` it refuses unless
`OWNER_GO_LIVE: YES` is in this backlog **and** film budget allows. Mock-session test only.

### P3-05 LIVE canary: one generation through the package — LIVE (after P3-04, P10-02)
Omni Flash 360p, film04 SC01_g1, full path: start still (ChatGPT GPM, `stills --register`, Owner approves) → `generate`
→ acquire → take log → review template. One attempt, then stop and report credits, wall time and every manual step.

**Attempt 1 (2026-11-07, Owner go-live in chat): UNBOUND, not DONE.** Flow account = GPM profile `wanglin08ma`; start still made in Flow (Nano
Banana 2.1, 0 credits; refs MARA + ticket-office plate), approved by the Owner with the storyboard; composer Khung hình, Omni 1.1 Flash,
360p, 8 s, x1 (Flow showed 6 credits; plan said 12). `flow_send` filled the start slot (slot diff 0.0), sent, and a new video tile appeared
(38 s wall) but the one captured response did not bind it to the prompt, so the clip was not saved and no take was registered
(`takes/intents/SC01_g1_t1.intent.json`, result UNBOUND, `take_registered: false`). The clip sits in the Flow project; it was not
downloaded by hand because custody requires the network binding. Credits: about 6 spent (Flow's quoted cost, not read back).
Manual steps: GPM profile start + port forward 9333, new Flow project, composer mode/model/Khung hinh selection, still generation with
attached refs, `flow_send` viewport pinned to 1280x720 (window was 1397x655). Next (needs a second live send, Owner call): find why the Omni
response does not match `bind()` (capture and inspect response frames in memory, never persist signed URLs).

**Attempts 2 and 3 (same day): P3-05 is BLOCKED (same cause twice: no network binding for Omni Flash).** Attempt 2 stopped at
`START_NOT_FOUND` before sending (a page reload had changed the gallery token form; no credits). Attempt 3 (t3) sent (slot diff 0.0)
and ended AMBIGUOUS (2 new tiles). With `flow_send` now recording a body-free `net_trace`, the result is clear: only two XHR
responses (143 and 250 bytes, batchexecute) came back, neither holds the prompt or a tile token, so `bind()` can never match
this model. Flow now holds two 360p clips for SC01_g1 (t1 and t3, same prompt), neither downloaded nor registered; about 12
credits spent in all (Flow's quoted 6 per send, not read back). The clip's detail page (`/edit/<media id>`) shows the full prompt
text, so binding can use the page instead of the network. P12-01 is now implemented; the next step is ONE more send (Owner call) to
prove it end to end; go-live stays NO until the Owner says so. The two orphan clips are in the "before" set of any new send.

### P12-01 Bind a Flow video to its prompt from the clip's detail page — DONE offline + read-only live check (found by P3-05)
Files: `tools/drama_flow_ui/flow_bind.py` (pure rules), `tests/test_flow_bind.py` (10 tests), `flow_send.py` (`video_titles`, `detail_bind`).
Root cause of the AMBIGUOUS in attempt 3 (read-only inspection of the live gallery): a video tile has no media id in the DOM and a
lazy tile shows no `src` until it scrolls in, so an OLD clip's token looks "new" (`new_tiles: 2`). A thumbnail token is therefore not
an identity. What is stable: the tile title (`aria-label` of `flow-grid-tile-container`, generated by Flow and different for equal
prompts) and the detail page (`/edit/<media id>` in the URL, full prompt text in the body).
Rule (video, when the network gives no single match): the set of tile titles before and after the send (gallery scrolled through);
exactly ONE new title; open that tile's detail page; the page must hold the WHOLE sent prompt (whitespace normalised; a truncated
prompt does not match); only then take the thumbnail token of that exact title and download. Records `binding: DETAIL_PROMPT_MATCH`,
`media_id_tail`, `detail_bind`. No new title → UNBOUND; two or more → AMBIGUOUS; a new tile that repeats an old title → UNBOUND (refused,
never guessed); never by position. Images keep their `data-media-id` path.
Verified read-only on the two existing SC01_g1 clips (no send, no credits): removing either title from the "before" set → BOUND to that
clip with its own media id and a thumbnail token; all titles known → UNBOUND; empty before-set → AMBIGUOUS (2 new); a prompt with one
extra sentence → UNBOUND. Not yet proven: a real send end to end (needs one Owner-authorised send); and the equal-title refusal is a
known limit, not a defect.

## P4 — Editorial (91–106)

### P4-01 EDL model + assembly from selects — DONE (66a20e2)
`05_edit.json`: ordered events {take_id, src_in, src_out, transition {type, duration}, audio {j_cut_s, l_cut_s}},
cards/tags as events. `film.py cut` renders via FFmpeg (reuse `drama.post`, `rough_cut`). Golden: film03 events
reproduce the existing final timeline duration within 1 frame per event.

### P4-02 Fine cut tools — DONE (a29b4e1)
Dissolve/match cut/J-L cut rendering; rhythm report (shot lengths vs 02_direction pacing, holds > plan flagged);
continuity-edit check across cuts (end/start states, axis side, eyeline) reusing P2-02.

### P4-03 Picture lock + invalidation — DONE (cca2c49)
Lock = hash of EDL + source take hashes. Any change after lock marks dependent post/QC/delivery items dirty
(`impact.py`). Test: change one src_out after lock → subtitles, mix, master QC flagged dirty.

## P5 — Sound & finishing (107–130)

### P5-01 Audio stems + mix — DONE (d07e898; mix.py, film.py mix: 4 stems, sidechain ducking depth measured, -14 LUFS/-1 dBTP, 9 tests; sfx/music assets recorded with sha256 for P5-02)
Separate stems: dialogue (from takes), ambience/room tone per location, SFX cues (from 04_shots `sfx`), music.
Mix with ducking under dialogue, J/L crossfades, loudness target −14 LUFS / −1 dBTP (reuse
`drama.post.normalize_loudness`, `measure_ebur128`). Sources: generated tones/noise beds offline, or CC0 libraries
recorded in the rights ledger (no untrusted downloads). Test with synthetic stems: ducking depth, peaks, loudness.

### P5-02 Music & SFX sourcing record — DONE (0d14cda; sound_rights.py, film.py sounds: audio/assets.json ledger, validate blocks unrecorded/uncleared/changed assets, cue sheet from emotional curve, 17 tests)
Rights ledger entries (source, license, hash, usage range). `validate` blocks delivery when any used asset lacks a
cleared license. Music cue sheet from 02_direction emotional curve (where music starts/stops and why).

### P5-03 Colour matching + grade — DONE (9a0ca25; color.py, film.py grade / cut --color, render_cut corrections+look: scene reference, clamped gains, before/after report, 9 tests)
Per-shot normalisation (exposure/white balance from frame stats) toward the scene reference, then the global look
grade (`drama.post.GRADE` as default). Report before/after deltas per shot. Test on synthetic coloured clips.

### P5-04 Titles, credits, subtitles, reframe — DONE (7ee9af0; titles.py, film.py titles, render_cut reframes/title_lines/end_lines: credits from package, speech-window cues, EN/VI sidecars, reframe box, 15 tests)
Credits card from package (cast = characters, AI disclosure line, rights credits); subtitles EN/VI from dialogue +
cards (reuse `drama.post`); reframe/stabilise options per event (crop box) for 9:16 later.

## P6 — Final QC & delivery (141–156)

### P6-01 Master technical QC — DONE 0055d3a (master_qc.py, film.py mastercheck: format/black/freeze/duplicate/loudness/clipping/silence/sync/colour/faststart, CUT-level record qc/master_qc.json, 16 tests)
Black frames, freeze frames, duplicated frames, fps/codec/resolution, audio clipping/silence gaps, subtitle sync
offsets, loudness compliance (ffmpeg blackdetect/freezedetect/silencedetect/ebur128). Record in QC model level CUT.

### P6-02 Versions, metadata, packaging — DONE 10c88a4 (versions.py, film.py versions: 9:16 crop by tag/reframe focus, emphasis-moment thumbnails, metadata draft with AI disclosure, 10 tests)
16:9 master + 9:16 reframe (crop boxes from P5-04, face-aware via `drama.tag_layout` detection when available),
thumbnail candidates (frames from emphasis moments), metadata draft (title, description, tags, AI disclosure,
credits). No publishing.

### P6-03 Archive + restore test — DONE 0928b43 (deliver.py, film.py deliver + status --package: marked masters, MANIFEST with hashes, compliance gate, restore check, 8 tests)
`film.py deliver` writes `delivery/` (masters, sidecars, disclosure/C2PA via `drama.disclosure`, manifests with
hashes, rights ledger, QC records, package JSON). Restore test: copy to a new temp dir, `film.py status --package`
verifies every hash and reports missing dependencies.

## P7 — Management (157–168)

### P7-01 Status report + ledgers — DONE b4f4fb9 (report.py, film.py status/status --all/ledger: gates, credits vs estimate, usable seconds, retake rate, open P0/P1, dirty items, rights blockers, next action; learnings observation vs replicated; 9 tests)
`film.py status` covers: gates, stage completeness, credits spent vs estimate, usable seconds, retake rate, open
P0/P1, dirty items, rights blockers, next action. `ledger.json` learnings (observation vs replicated) per film.

### P7-02 Re-run film03 end-to-end through the package — DONE 77a9276 (tools/film03_to_package.py imports 16 shipped takes as INCOMPLETE, EDL + cue timing from the shipped cut; cut → grade → titles → mix → mastercheck → versions → deliver run; diff in docs/drama/film03/PACKAGE_RERUN.md; 7 tests)
Using existing film03 takes (no generation): plan → review (import existing gate/QC data) → cut → post v2 (with
ambience/music/colour match) → QC → deliver. Report diffs vs the shipped final. Phase end: full suite, push, status.

## P8 — Proof film

### P8-01 film04 authored from scratch by the model — DONE 51130ec (after P1-03, P2-04, P7-01)
Following `DIRECTOR_PLAYBOOK.md` only, author an original 90–120 s drama (new characters/location; no real persons;
Owner rules on moderation). All stage files through 03_preprod + 04_shots; `validate` all gates PASS or
OWNER_PENDING; animatic rendered; budget estimate. No new Python specific to film04 — any need becomes a system item.

### P8-02 film04 production — LIVE (after P3-05, P10-09; awaiting Owner: storyboard approval, rights, go-live)
Generate per plan within budget, dailies review, retake/pickup policy, cut, post, QC, deliver. KPI vs film02/03
(credits per usable second, first-pass rate). Owner creative review required; never self-accept.

## P10 — Ship readiness (offline; Tech Lead plan 2026-11-07)

Phase rule: every item ends with its own tests + the focused suite. No item may weaken an existing assertion; where a test
pinned `NOT_RUN` only because no validator existed, replace it with the new real verdict and say so in the commit.

### P10-01 Gate 3, 4 and 6 validators — DONE c61fe7c (gate_checks.py, plan_meta.json sidecar, deliver --accept; 12 tests; focused suite green)
Files: `src/film_pipeline/production/gates.py` (+ a small module per gate if needed), `tests/test_production_gates*.py`,
`tests/test_production_film03_package.py`, `tests/test_production_film04.py`.
- Gate 3 (visual_spatial): read the plan record (`<film>/media/plan/gate3.json`, path from the package, not a CLI arg).
  Missing or older than the stage files it was planned from (store/compare a hash of 03/04 in gate3.json; add it in `plan`)
  → BLOCK "re-run film.py plan". Any non-STORYBOARD BLOCK → BLOCK with the detail. Only storyboard PENDING → OWNER_PENDING.
  Clean + storyboard approved → PASS.
- Gate 4 (production_asset): every generation the EDL needs (or every generation in 04_shots when there is no EDL) has a take
  whose review is complete and ACCEPTED by a named human reviewer → PASS; a take with an open P0/P1 or no take → BLOCK;
  takes present but unreviewed → OWNER_PENDING. Reuse `takes.py`/`qc_model.py`; never accept from autoqc.
- Gate 6 (final_master): fresh `qc/master_qc.json` PASS for the current master hash and `07_delivery.json` MANIFEST hash matching
  the archive → OWNER_PENDING (final creative acceptance is the Owner's); any mismatch/BLOCK finding → BLOCK. Never PASS
  without an Owner acceptance record (add `07_delivery.json.owner_acceptance {by, at}` written only by
  `film.py deliver --accept "<name>"`, refused unless every other gate is PASS).
Done when: film04 validate shows 3 = OWNER_PENDING (storyboard), 4 = BLOCK (no takes), 5/6 = BLOCK; film03 shows 3 = BLOCK
or OWNER_PENDING with the real reason, 4 = OWNER_PENDING (unreviewed takes), 6 = OWNER_PENDING or BLOCK with the reason.
Categories: 41, 80–90, 141–146 partials → re-tick.

### P10-02 Start-still stage in the package — DONE (dd00c4b)
Files: new `src/film_pipeline/production/stills.py`, `tools/film.py stills`, `generate.py`, `animatic.py`, tests.
`film.py stills --film F` lists each generation's still prompt (from the plan) and its state; `--register GID --image PATH
[--source "ChatGPT GPM tab 2" --credits N]` copies the image under `media/stills/`, records sha256, the still-prompt hash it
answers and the source in `03_preprod.json.stills[GID]` (typed, `ContractModel`); `--approve GID --by NAME` marks it approved
(a re-planned prompt with a different hash makes the approval stale → not approved). `generate` and `animatic` take approved
stills from this record by default (`--stills` dir stays as an override). Making the image is an operator/LIVE step outside
this command; nothing here calls a provider. Tests with tiny generated PNGs. Categories: 44–47, 57.

### P10-03 Delivery fixes from the film03 re-run — DONE (9b477c8)
Files: `deliver.py`, `titles.py`, `versions.py`, `tools/film.py`, tests; `docs/drama/film03/PACKAGE_RERUN.md` (mark items).
(a) Structured generators: `--generators-file JSON` = list of {role: video+audio|image|voice|music, name, model, settings};
the string form stays for compatibility and maps to one role-less entry; disclosure + credits print roles; the P7-02 film03
command line in PACKAGE_RERUN is updated to the file form. (b) Visible AI label: `film.json.disclosure.ai_label` =
`always` (default — matches the shipped film01–03 finals) | `title_card`; `titles --render` burns a small bottom-left
"AI-generated" over the whole body when `always`; `deliver` checks the master carries what the setting says (sample frames).
Owner may switch to `title_card`; the code must not pick the weaker one by default. (c) Re-run the film03 chain and record
the new diff lines. Categories: 147–149, 155.

### P10-04 Prompt word budget report + playbook rules — DONE (2d72023; budget is in plan_meta.json word_budget, not gate3.json, which the film03 golden test pins byte-for-byte)
Files: `plan.py` (record only), `docs/director/DIRECTOR_PLAYBOOK.md`, tests.
`plan` writes per generation the emitted word count split by section (prefix, cast/looks, setting, continuity state, shot
timing/action, performance, dialogue, sound, fixed tail) into `gate3.json` and prints the top 3 sections when a prompt is
over the limit. Playbook §6 gets the three film04 rules (budget dominated by looks + location + state list; a mid-shot
entrant must be in the start state; a once-action must be spelled in its ACTION phase; a prop that changes needs an
ACTION/CONSEQUENCE phase naming it). Do not change the 215 limit (Owner item).

### P10-05 Offline dress rehearsal on film04 — DONE (1f98cbf; reached delivery with 0 BLOCK, 312 s; manual steps M1-M5 in REHEARSAL_FILM04.md -> P11-07)
Files: `src/film_pipeline/production/rehearsal.py`, `tools/film.py rehearse`, `tests/test_production_rehearsal.py`,
`docs/production/REHEARSAL_FILM04.md`.
`film.py rehearse --film F --out DIR` copies the package to `DIR` (never touches the real one), sets
`film.json.rehearsal = true`, and runs the real chain with a mock runner instead of Flow: placeholder stills (storyboard frame)
→ `stills --register/--approve` → `generate` per generation with a mock runner that renders an 8 s clip from the still
(ffmpeg, silent or tone) → `takes` → `review` (rehearsal reviewer `REHEARSAL-BOT`, allowed **only** when `rehearsal` is
true) → `cut` → `lock` → `grade` → `titles --render` → `mix` → `mastercheck` → `versions` → `deliver`. A rehearsal package
must be refused by `deliver --accept`, stamp every report `REHEARSAL — synthetic`, and keep `release_ready: false`; add
tests that a non-rehearsal package refuses `REHEARSAL-BOT`. Record per-step result, wall time and every manual step that was
still needed in the doc; each manual step becomes a P11 item. Media stays under `DIR` (gitignored).
Done when: the rehearsal reaches a delivery archive with 0 BLOCK, or each BLOCK is recorded as a P11 system item.

### P10-06 Operator runbook + Owner review pack — DONE (97a1a92)
Files: `docs/production/RUNBOOK.md`, `src/film_pipeline/production/reviewpack.py`, `tools/film.py reviewpack`, tests.
Runbook: the command sequence from `film.py new` to `deliver --accept`, each Owner checkpoint (story, storyboard, rights,
go-live + budget, take reviews, picture lock, final acceptance), stop rules (1.5x budget, same cause twice), recovery, where
media lives. A test parses every `film.py <action>` in the runbook and asserts it exists in the CLI parser.
`film.py reviewpack --film F` writes `media/review/index.html` (self-contained, no external assets): gates with reasons,
storyboard frames, animatic path, budget, risks + fallbacks, rights pending, takes awaiting review with their QC sheet —
one page the Owner can decide from. `status` "next action" names the runbook step.

### P10-07 Coverage + operating state reconciliation — DONE (ea7ad2d; 9 rows fixed, GAP 3 -> 1, summary recounted)
Files: `docs/production/CATEGORY_COVERAGE_168.md`, `docs/drama/film03/PACKAGE_RERUN.md`.
Re-check every GAP/PARTIAL row against the code as it is now (e.g. 166 says "no rights ledger" although
`03_preprod.rights` + `sound_rights.py` exist); fix stale rows with the file that proves it; recompute the summary line. Rows
that are honestly PARTIAL because they need live footage stay PARTIAL with that reason. Docs only.

### P10-08 Independent review (Codex gpt-6.1-sol, read-only) — DONE EARLY (ran in P10-04/05 on the owner's "speed up": `docs/production/reviews/CODEX_REVIEW_2026-11-07.md`; 9 of 11 findings confirmed by code read, 1 partial, 1 refuted → P11-01..P11-06; no code fixed here; rehearsal.py post-dates the review and is not covered)
Run `codex.exe exec -m gpt-6.1-sol -s read-only -C "D:/AI FILM MAKER/AFP-stable" --ephemeral --color never -o <scratch>/review.md - < prompt.md`
on the diff `65c4470..HEAD` plus the P5–P7 modules (`mix.py, sound_rights.py, color.py, titles.py, master_qc.py,
versions.py, deliver.py, report.py, gates.py, stills.py, rehearsal.py`). Prompt: correctness bugs, gates that can PASS
unchecked, any path that self-accepts footage or sends to a provider without `OWNER_GO_LIVE: YES`. Save the review under
`docs/production/reviews/`; each confirmed finding becomes a P11 item (READY, with evidence); fix none in this item.

### P10-09 Phase close — DONE (232b392)
Full suite; `IMPLEMENTATION_STATUS.md` row with the four Product Progress Gate answers (product delta, proof class,
main blocker, next choice); update `docs/operating/CURRENT_SLICE.md` "Where things stand" table; push. Then stop the loop if
only P11 items marked BLOCKED/LIVE remain.

## P11 — Found by P10 (rehearsal manual steps, review findings)

### P11-01 The 9:16 version drops the body AI label — DONE (37b7813) (found by P10-03)
Files: `versions.py` (portrait render), `deliver.py` (`label_evidence` for the portrait), tests. `film.json disclosure.ai_label`
`always` burns the label bottom-left of the 16:9 body (x 24–130 of 1280); the 9:16 centre/tag crop is ~404 px wide, so the
label is cut off unless the window starts left of x≈130. Evidence: `portrait_segments` crop_x in `tests/test_production_versions.py`.
Fix: draw the label onto the portrait body (and check it in `deliver` for `portrait_9x16`), or record why the portrait is
exempt. Do not weaken the 16:9 check. (Codex review finding 2 is the same gap: the portrait claims `watermark_always_on` unchecked.)

### P11-02 AI-label pixel check: independent evidence and full coverage — DONE (2a866de) (Codex review 2026-11-07, findings 3–4; verified)
Files: `deliver.py` `label_evidence`, `tests/test_production_delivery_fixes.py`.
(a) `contrast(target) - contrast(control)` lets a target with 0 contrast and a negative control pass (+30 ≥ 25): require the
target's own contrast ≥ threshold *and* the difference. (b) 3 of 5 sampled frames passes `always`: require every sampled
frame (sample count stays 5, add the first and last body frame) or record the exact frames missing the label as BLOCK.
Tests: zero-contrast target with negative control fails; 4 of 5 fails. Do not lower any threshold.

### P11-03 Gate 4 binds acceptance to current inputs and present bytes — DONE (8ddd638) (Codex findings 5–7; verified)
Files: `gate_checks.py` (`_take_state`, `_review`), `takes.py` (review file pointer), tests.
(a) An ACCEPTED take stays valid after the shot prompt changes without a `ShotDecl.version` bump: compare the take's
`prompt_sha256` with the current emitted prompt and mark the take stale. (b) A missing accepted clip skips the hash check and
passes: a missing clip is a BLOCK. (c) After `dailies` + `ingest`, `review_file` points at the wrapped sheet and `_review`
raises (extra keys forbidden): `ingest_review` should point `review_file` at the stored bare QC, and `_review` should unwrap a
legacy sheet. Tests for each; existing film03 gate-4 tests stay green.

### P11-04 Gate 3 staleness: header fields and storyboard files — DONE (3a71668) (Codex findings 8–9; verified)
Files: `gate_checks.py` (`PLAN_INPUTS`, `plan_issues`), tests.
(a) `film.json` `language`, `generation_s`, `fps`, `aspect` feed the plan but are not in `plan_inputs_sha`: include the
planning-relevant header fields (not `gates`, `budget`, `disclosure`, `rehearsal`). (b) Storyboard approval survives a changed or
deleted PNG: gate 3 re-checks the approved frame hashes. The film03 golden test must stay byte-identical.

### P11-05 Acceptance is bound to the disclosure policy — DONE (98aeab3) (Codex finding 1; verified)
Files: `deliver.py` (`accept_delivery`, manifest), `gate_checks.py` (`master_issues`), tests.
Record `ai_label` in the manifest / `07_delivery.json`; `accept_delivery` and gate 6 refuse when it differs from the current
`film.json` `disclosure.ai_label` ("deliver again under the current policy").

### P11-06 Start stills are decoded before registration — DONE (db60d67) (Codex finding 11; verified)
Files: `stills.py` (`register_still`), tests. A PNG signature followed by garbage is accepted today. Decode (Pillow `verify()` +
`load()`), require width/height ≥ the film resolution's aspect ratio sanity (not zero), refuse otherwise. Finding 10 (stills not
git-ignored) is **refuted**: `films/.gitignore` has `*/media/`.

### P11-07 Draft the edit and the generators record from the package — DONE (52b14cf) (P10-05 manual steps M1–M3)
Files: new `production/edit_init.py` or `edit.py`, `tools/film.py` (`edit --init`, `generators --init`), tests.
Evidence: `docs/production/REHEARSAL_FILM04.md` — `05_edit.json` was `{}` and a human/rehearsal had to write the TAKE events, the
title card with the AI line (deliver BLOCKs `AI_LABEL_MISSING` without it) and `generators.json`. `edit --init` drafts the EDL from
the shot list and the latest ACCEPTED takes (refuses to overwrite a non-empty EDL), title card from the film title plus the AI
line; `generators --init` drafts the record from the route/model of the take log. Both are drafts for a human to review.

### P11-08 The rehearsal also runs the archive restore check — DONE (e666c5d) (found by P10-07, row 156)
Files: `rehearsal.py`, `tests/test_production_rehearsal.py`, `REHEARSAL_FILM04.md`. `deliver.verify_archive` is the restore
check (`film.py status --package <delivery>`) but no run exercises it. Add it as the last rehearsal step on a *copy* of the
archive moved to another directory; record the result. Done when the rehearsal report lists `restore` ok.

## P9 — Found by the loop

### P9-01 `test_dispatch_recovery` F0/F1 needs `film_pipeline` importable in its subprocess — DONE 07defac
Evidence (2026-11-06, full suite): `tests/test_dispatch_recovery.py::test_F0_requires_fresh_authority_and_F1_real_process_exit_is_durable`
runs `python -c "from film_pipeline..."` as a subprocess and gets `ModuleNotFoundError` (returncode 1, expected 72) because
`pythonpath = ["src"]` only applies to the pytest process. Fix: pass `env` with `PYTHONPATH=<repo>/src` (or `cwd`/`-I` aware)
in that subprocess call. Do not weaken the assertion.

