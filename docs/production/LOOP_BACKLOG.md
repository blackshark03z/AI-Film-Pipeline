# Loop backlog — E2E production system

OWNER_GO_LIVE: NO
<!-- 2026-11-07: Owner authorised P3-05 only in chat ("cho phep tat ca", "Duyet ca hai", "Cho gui lan hai"); Claude set YES for each canary send and back to NO right after it. P8-02 stays locked. -->
<!-- Owner flips to YES to allow LIVE items (real Flow/ChatGPT generation). Tech Lead never flips it. -->

## Loop outcome (2026-11-07): STOPPED - no READY item left

**2026-11-07 later:** P14 (gaps from the external comparison) added as READY offline items; the loop may resume on them.

P0-P11 are DONE offline. Only two items remain and both are **LIVE** (need `OWNER_GO_LIVE: YES`, written by the Owner): **P3-05**
(one canary generation, Omni Flash 360p) and **P8-02** (film04: 12 generations, expected 171.2, cap 256.8 credits). Test and
canary videos use Omni Flash at 360p (Owner, 2026-11-07). P11 (Codex review follow-ups) closed in 8 commits: P11-01 9:16 label
(37b7813), P11-02 label pixel check (2a866de), P11-03 gate 4 (8ddd638), P11-04 gate 3 (3a71668), P11-05 disclosure policy
(98aeab3), P11-06 still decode (db60d67), P11-07 `edit --init` / `generators --init` (52b14cf), P11-08 rehearsal restore check
(e666c5d). The loop restarts when the Owner flips the go-live line or adds a READY item.

## Completion plan (Tech Lead, 2026-11-08)

**Done =** film04 delivered from its package with `film.py` only and accepted by the Owner, at a take rate a second film can
repeat. State: 2 of 12 generations accepted, 9 takes, 80 of 171.2 credits (cap 256.8), 14 h. Why it is slow and what the model
can and cannot do: [FILM04_SHOT_QUALITY_REVIEW.md](FILM04_SHOT_QUALITY_REVIEW.md). P14 (external comparison) and P15 (film04
review) merged and ordered by what shortens the critical path:

| Phase | Items | Credits | Exit |
|---|---|---|---|
| A. Stop failing on design (offline) — done except the Owner's choices | Owner verdict SC02_g1 t2 (REJECTED, v3 planned) → P15-01 generability rating (reads the feasibility part of P14-01) → P15-02 frame-delta check → P15-07 film04 restage of RED beats (**Owner approves the story changes**) → P14-05 voice bible | 0 | Every remaining film04 beat GREEN or AMBER; restaged shots planned |
| B. Fewer, better takes | P15-06 send reliability → P14-02 + P15-03 best-of-N stills and takes → P14-03 / P15-04 VLM judge (WARN) → P15-05 + P14-07 Flow capability probe (Omni clip edit, start frame + character refs) | probe ≤ 20 | Owner sees only drafts that pass motion QC + judge |
| C. Shoot film04 | SC02_g1 v3 → SC06_g2 with the new loop; KPI ≤ 2 sends per accepted shot | ~140-170 | All generations ACCEPTED by the Owner |
| D. Finish and deliver | cut, grade, titles, mix, mastercheck, versions, deliver (P4-P6 built, rehearsed in P10-05); **Owner: rights checkpoint 3, AI label, C2PA signer, final acceptance** | 0 | Master delivered, Owner accepts |

**Superseded order (2026-11-08, after Owner review of SC02_g1_t3: "who is she talking to?"):** phases B-C now run as P16
(interaction contract), see [PRODUCTION_PROCESS_V2.md](PRODUCTION_PROCESS_V2.md) (Claude x Codex brainstorm, rounds in
`reviews/PROCESS_V2_BRAINSTORM_2026-11-08/`). Next live send only after P16-01..06, P16-07a, P16-08 and Owner approval of the
pilot board/stills. Ledger figures above are stale until P16-01.
| E. After ship | P14-04 dialogue ASR (**Owner: install**), P14-06 DramaChain taxonomy, P14-08 API stub, rest of P14-01 | 0 | — |

Budget risk: restaging may add insert shots; best-of-2 by default keeps phase C inside the cap, best-of-3 only for restaged RED
beats. The playbook rule "one scene = two 8 s generations" yields to P13-06 durations and P15-07 inserts (amend in P15-01).

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

### P3-05 LIVE canary: one generation through the package — DONE technical PASS (take SC01_g1_t1 = SC01_g1_t6.mp4); Owner review pending
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

**Attempts 4-6 (Owner: "cho phep su dung toi da han muc", go-live YES per send, NO right after).** Attempt 4 and 5 stopped/failed on
fixable tooling faults, attempt 6 PASSED: video `SC01_g1_t6.mp4` (640x360, 8.04 s, h264+aac, sha256 0c00dcce...), bound by
`NETWORK_PROMPT_MATCH` (this time the network did hold the prompt), take registered as `SC01_g1_t1`, 38 s generation, about 80 s per
`flow_send` run, 6 credits per send (Flow's quote; the take ledger counts 12 per intent and over-reports: 60 shown for 6 intents of which
4 sent). Total real spend so far about 24 credits (4 sends: t1, t3, t5, t6). Technical PASS only: ffprobe + frame strip; a preliminary
look (not the review) suggests MARA stays seated while the plan says she stands at the counter with a hand on the shutter cord.
Owner must watch the clip and fill `takes/dailies/SC01_g1_t1.review.json` (R7). Orphan clips t1/t3/t5 remain in Flow, unregistered.

Manual steps this run: GPM profile start + 9333 forward (already open), composer mode check (Omni 1.1 Flash, 6 credits), no manual download.

### P12-01 Bind a Flow video to its prompt from the clip's detail page — DONE (offline 12 tests, live read-only, one live send)
Files: `tools/drama_flow_ui/flow_bind.py` (pure rules), `tests/test_flow_bind.py` (12 tests), `flow_send.py` (`video_count`, `read_nth_detail`,
`front_snapshot`, `detail_bind`, `_picker_find_image`).
Findings from read-only inspection of the live gallery:
- a video tile has no media id in the DOM; a lazy tile shows no `src` until it scrolls in, so an OLD clip's token can look "new";
- tile titles (`aria-label`) repeat for equal prompts (3 clips, 2 titles), so a title is not an identity either;
- the detail page (`/edit/<media id>`) holds the media id in the URL and the full prompt text; media ids were stable across reloads;
- the start-frame picker's thumbnail token tail changes between page loads (attempt 4 START_NOT_FOUND); its pixels do not.
Rules now in `flow_send.py`:
1. Start still: token tail first; if absent, the picker item whose pixels match the approved still (diff <= 4.0 and at least 3.0 better than
   the runner-up; a sibling still of the same room scores about 7); `start_found_by` is recorded; the slot is re-checked after the click
   (`start_slot_diff`, threshold tightened from 12.0 to 4.0 because the sibling plate scored 7.1).
2. Video binding when the network gives no single match (`flow_bind.decide_front`): before the send read the video count and the media id of the
   front video; after it the gallery must hold exactly one more video, the old front video must now be second (same media id), the new
   front video must have another media id and its detail page must hold the WHOLE sent prompt. Otherwise UNBOUND/AMBIGUOUS. Records
   `binding: DETAIL_PROMPT_MATCH`, `media_id_tail`, `detail_bind`.
Live: read-only count 3 with stable distinct ids; the DETAIL path itself was not exercised by attempt 6 (the network bound it), so it stays
"unit + read-only proven" until a send needs it.

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

### P8-02 film04 production — LIVE, STOPPED AT OWNER CHECKPOINT 5 (SC01_g1 take review)
Generate per plan within budget, dailies review, retake/pickup policy, cut, post, QC, deliver. KPI vs film02/03
(credits per usable second, first-pass rate). Owner creative review required; never self-accept.
State 2026-11-07: storyboard + SC01_g1 still approved, budget 171.2 (cap 256.8), go-live authorised by the Owner in chat ("cho phep su
dung toi da han muc"; flag back to NO). film04 is a strict hand-off chain: every generation except SC06_g1 waits for the previous take
to be ACCEPTED (its end frame is the next start frame), so only the Owner's take review (R7) unblocks SC01_g2. The only independent
generation is SC06_g1 (needs its start still made and approved). Rights checkpoint 3 is still an open Owner decision.

### P13-01 A shot must be readable: wide size, absent people, still pose — DONE (found by the Owner's review of SC01_g1_t1, 2026-11-07)
Owner: the take "gave the viewer no meaning - she sits pulling the cord, the shutter closes". Causes, by stage that missed them:
planner/prompt (`CoverageShot.describe`) named THEO in a two-shot with MARA alone; still prompt (`still_prompt`) never stated the SETUP pose, so
the approved start still seated MARA; camera plan let a WIDE master carry a lone figure acting on a prop and a clock time. Fixes: `describe` names
only who is in frame; `StillTemplates.pose` (film04 on, film03 off to keep its golden) adds "First instant: <SETUP>"; `CAMERA_ACTION_LEGIBLE`
(BLOCK) for a WIDE shot with one person acting on its own prop or a clock time, unless `camera.wide_reason`. Tests in test_drama_scene_bible,
test_production_stills, test_production_camera; focused suite 752 passed, 1 skipped. film04 SC01_g1: take rejected (narrative P0, cause STAGING),
pickup to v2 = MEDIUM_CLOSE SINGLE at the ticket window; B1 coverage plan MASTER -> SINGLE; new start still registered (0 credits), NOT approved;
storyboard needs the Owner's re-approval (plan re-run). Open: Owner approves still + storyboard, then one resend (~6 credits, OWNER_GO_LIVE YES->NO).

### P13-02 The set has a geography and each shot states what the viewer reads — DONE (Owner: "from the image it is still unclear", 2026-11-07)
Cause: a location was a list of objects with no spatial relations (the shutter drew as a separate window, sides were unclear) and no shot said
what the viewer must understand. New `production/set_layout.py`: `LocationSpec.layout` (zones, objects with placement/operation, camera
positions with `sees`/`look_at`), `ShotDecl.camera_position` + `readout` (fact, evidence, min_size). BLOCK rules LAYOUT_CAMERA,
READOUT_MISSING (all-or-nothing per film), READOUT_EVIDENCE (evidence must be in frame), READOUT_SIZE. Still prompts carry the camera's view
text; plan writes per-camera plates `plate_<look>_<cam>.txt` and a floor plan `layout/<look>.png`; take review asks readout questions first.
film04: ticket office layout, cameras A (hall, through the window) / B (booth, to the door) / C (side-on), readouts for all 12 shots; SC01_g1
on camera A with the shutter pulled by its handle. Focused suite 775 passed, 1 skipped. Plates A/B/C made in Flow image mode (0 credits) and
sent to the Owner. Plate B invented a second clock in the hall -> plate prompts name out-of-frame objects (`unseen_text`), B redone.
Owner approved plates A/B/C (2026-11-07; media/stills/plate_ticket_office_night_*). SC01_g1 start still redone from plate A + MARA (0 credits,
Flow media cc2e86cc), registered NOT approved.
Owner rejected that still: the clerk's hand reached through the glass to a hall-side shutter handle. Cause: the layout never said which side
a mechanism is worked from, and the image model defaults handles to the customer side. Fix: `SetObject.operated_from` (zone); view text says
the hand stays on that side when the camera is on the other. film04: shutter on the booth side, worked by fingers under its bottom edge (no
handle), plain rectangular window, clock beside (not above) the window. Plate A redone (A5, Flow 00b15c17), start still v8 (Flow 4a20dabf)
registered NOT approved; Flow picker items are now picked by pixels (picker order is 'recent' and moves). Open: plate C still draws the
shutter on the hall side -> redrawn in a ChatGPT tab (same GPM profile) from plate A5. Owner approved start still v8 and plates A5/C
(2026-11-07); Owner approved the 12-frame storyboard (gate 3 PASS). Focused suite 777 passed, 1 skipped. Resend (Owner: "Cho gửi"):
receipt t7 = START_NOT_FOUND, nothing sent, 0 credits (the start picker reopened mid-list and the search only wheeled down past
the newest still) -> flow_send now scrolls each picker to the top first (tests/test_flow_send_picker.py); receipt t8 = PASSED,
DETAIL_PROMPT_MATCH, media 3e9f674e, registered as SC01_g1_t2 (v2, GENERATED, 6 credits), OWNER_GO_LIVE back to NO.
Tech Lead QC of t2: start frame and booth-side grip hold (no hand through the glass), but the shutter drops only to her brow,
she lets go at ~3 s, the shutter jumps back to fully raised and she rests her hands on the coin tray for the last 4.5 s
-> "she is closing the ticket window" does not read. Owner rejected it ("Reject, fix the action") -> P13-03.
SC03_g1 is still a two-person WIDE with a jar-on-counter beat (not flagged by the rule; no take yet).

### P13-03 The prompt says how the shot ends, not only how it starts — DONE (Owner rejected SC01_g1_t2, 2026-11-07)

Defect: the prompt named only the start state ("the shutter: up"); the model pulled the shutter down, let go and it sprang
back to the one state it was told. Stage that missed it: prompt compile. Fix: `ContinuityState.describe_change` adds
"Ends with <prop> <state>, held to the last frame." for every prop the end state changes (people's moves stay in the action
text; word budget). `generate` no longer lets another shot's PROMPT_TOO_LONG hold this one back (`_problem_subject`).
Review t2 ingested: REJECTED, cause PROMPT. Shot SC01_g1 v3 (retake): action "slowly pulls the shutter down by its bottom
edge to the middle of the window and stops", hold "her fingers stay on the still shutter", once-action "pulls the shutter
down"; prompt 214 words. `preflight.end_state_in_prompt` (default true) is false only in film03 (shipped, golden prompt
bytes). Open: film04 SC03_g1, SC04_g2, SC05_g2 now run 10-20 words over 215 (gate 3 BLOCK; named in
test_production_film04 OPEN_OVERLONG) - shorten them when they are restaged, before their own send;
storyboard re-approved by the Owner ("Approve and send", 2026-11-07); SC01_g1 v3 sent once (YES->NO): take
SC01_g1_t3 (file SC01_g1_t9.mp4), GENERATED, awaiting Owner review. Tech Lead readout: the shutter goes ~2/3 down by
3.5 s, then she pushes it back up to ~1/3 by 5.5 s and holds it there; she never looks at the clock. That is a reversal
(once-action broken) and the end height is not the middle. Not self-accepted.

### P13-04 Prompts follow Google's official Omni Flash / Veo guidance — DONE (Owner rejected SC01_g1_t3, "Sửa đi", 2026-11-08)

Defect: take t3 (v3) pulled the shutter ~2/3 down, pushed it back up to ~1/3 and never looked at the clock. Review
ingested: REJECTED, cause PROMPT. Sources read 2026-11-08: aistudio.google.com/docs/omni (Omni Flash prompt guide, timing
events, first/last frame), docs.cloud.google.com video prompt guide + "Best practices" (image-to-video: "Prompt for motion
only", do not re-describe character/background/light; refer to "the woman"; one focused moment per short clip; audio in
its own sentence). Our 214-word prompt re-described looks and set (~60 words) and buried the end state among them.
Fix (stage: prompt compile): `PreflightLimits.prompt_style` "start_frame" (default; film03 pinned "full"):
no cast/set look text, `CharacterSpec.handle` instead of names, timecodes `[0-2s] ...`, "A single unbroken Ns shot, no
scene cuts" ("continuous" stays banned: UNCONTROLLED_REPEAT), action first then the end state, `PerformanceCue.motion_text`,
"Sound design: ...", "No touching." only with 2+ people visible. film04 prompts now 101-149 words; the three P13-03
overlong shots are gone (OPEN_OVERLONG empty). SC01_g1 v4: one moment, no clock glance; hold = hands rest on the still
shutter. Tests: tests/test_drama_prompt_start_frame.py.

### P13-05 End state pinned by an end still (Flow "Kết thúc" slot) — DONE (code + first send); take t4 REJECTED (P13-06)

Google Omni docs: first and last frame interpolation, "describe the desired transition". `ShotDecl.end_frame`; plan writes
`stills/end_<gid>.txt` (edit of the start still, "Keep everything else the same"); stills record `end:<gid>` needs an
Owner approval like a start still; generate/flow_send send both slots. flow_send finds slots by button text, not fixed
coordinates (the GPM window was 1397x655, not 1280x720). film04 SC01_g1 v4 is the first end_frame shot.
Making the end still (2026-11-08): Flow Nano Banana 2.1 edits of the start still barely moved the shutter (tries 1-2)
or stopped it at her brow with the hands still up (try 3) -> fixes: the film's end state names a body-relative height
("its bottom edge at her chest height") instead of "halfway down"; `ShotDecl.end_pose` (a still pose; a HOLD phase says
what does not move, which an image cannot show); `flow_send --attach file:PATH` finds a gallery image by its pixels
(token tails change: tok:4a20dabf was gone); the composer "+" is found in the DOM (button.add-menu-trigger).
ChatGPT GPM tab try 1 put her face IN FRONT of the half-lowered shutter (the old "through the shutter" defect); try 2
(end_pose: the lowered shutter hides her face) is physically right and is registered as end:SC01_g1, NOT approved.
Open, Owner: pick the end frame (B registered: chest, face hidden; A: brow, face visible), approve it and the storyboard;
then upload the end still to the Flow gallery, set the composer back to Video / Khung hình, one send (YES->NO).
Note: Flow shows 6 credits for 360p 8 s; the pipeline books 12 (CREDITS_PER_GENERATION) - over-counts the budget.
Owner picks (2026-11-08, "Bạn tự làm đi" = Tech Lead decides): B approved as end:SC01_g1 + storyboard (by owner-khoikk03).
Send (2026-11-08): end still uploaded through the "Kết thúc" picker ("Tải nội dung nghe nhìn lên"; Khung hình mode has no
"+"); one send YES->NO; both slots found by pixels (diff 0.0 / 0.4). flow_send ended AMBIGUOUS: video_count read 7 after
8 (virtual-grid miscount). Manual re-check: front detail page 6d1cb844 holds the whole sent prompt and the old front
(t9, ...bda21804) is second -> bound, downloaded as SC01_g1_t10.mp4, registered as take SC01_g1_t4 (GENERATED).
Tech Lead eye check (0.5 s strip + zoom): start frame matches; shutter comes down once (about 1.5-4 s, earlier than the
2-6 s phase) and holds; last frame matches the end still (edge at chest, both hands on it, face hidden); no hand through
the shutter seen at 360p. Not self-accepted: Owner reviews t4.
Fix found by this send: `film.py takes --register` hashed the prompt file with its trailing newline, so the take log
disagreed with the generate receipt; it now strips like generate (test in test_production_takes).
Open: video_count undercounts on the virtual grid -> AMBIGUOUS on a good send (follow-up: count by media ids, not grid slots).
Owner review of t4 (2026-11-08): REJECTED, action P0 - shutter at the end height at 4.0 s, overshoots to waist (edge y 249
vs 210 of 360) at 5.0 s, pushed back up to 200 by 6.25 s; the Tech Lead eye check missed it. Cause: see P13-06.

### P13-06 A shot is as long as its action (Omni 1.2 Flash 3-15 s) + trajectory QC — DONE (code + v5 data); v5 send waits for Owner still approval

Diagnosis (t9 and t10 both reverse): the shot design gave a ~2 s pull a 4 s ACTION phase inside a fixed 8 s generation and
stopped it at an arbitrary mid-point; the model filled the time with an overshoot and a correction. Preflight had no notion
of how long a motion takes; QC looked at strips, not at the trajectory.
Fix (A+B+C): A `ShotDecl.duration_s` 3-15 (Omni 1.2 Flash slider; `flow_send --model/--duration` sets and verifies model,
seconds and cost before filling the frames; generate books `flow_credits(s)` = 1/s to 10 s, then 2/s at 360p) and a motion
library (`drama/motion_library.py`: TIME_FILL > max*1.25, RUSHED < min*0.8, MOTION_UNKNOWN); B a mid-travel stop needs
`stops_at` = a visible layout object whose label is in the text (STOP_TARGET), vague stops (halfway/middle/partway...)
are TARGET_CONFLICT; C end still = the instant right after the stop. QC: `film.py motion` (optical flow on the
declared `tracked` ROI; MOTION_REVERSAL / NO_MOTION P1, MOTION_OUTSIDE_ACTION P2) flags t9 and t10 as MOTION_REVERSAL.
Playbook §4/§5/§6.5 + film-director skill updated.
film04 v5: SC01_g1 = 4 s (SETUP 0-1, ACTION 1-3 lower_roll_shutter_partial stops_at shutter_catch, HOLD 3-4); layout adds
`shutter_catch` ("brass shutter catches"); every shutter state now rests on the catches. New stills (ChatGPT GPM tab)
registered as start/end SC01_g1, NOT approved; storyboard frame changed (4 s) -> approval voided. Preflight caught "keeps"
in the HOLD line (UNCONTROLLED_REPEAT) -> "her hands rest on...".
Live settings check (0 credits, no send): `_set_composer_settings` failed "duration slider not found" - Flow renders the
length as `input[type=range]`, not `[role=slider]`; fixed; re-run set Omni 1.2 Flash, 4 s, Flow shows "tốn 4 tín dụng",
chip "Video · 360p · 4 giây". The composer is left on 4 s.
Owner approved start/end SC01_g1 v5 + storyboard SC01_S1 only ("Duyệt, gửi đi", 2026-11-08; `--approve-storyboard` would
approve all 12 frames, so only SC01_S1 was reviewed through StoryboardGate). Both stills uploaded via the Kết thúc picker;
one send YES->NO: flow_send PASSED (model Omni 1.2 Flash, 4 s, Flow cost 4; both slots by pixels, diff 0.3 / 0.4; bound
without AMBIGUOUS) -> SC01_g1_t11.mp4 (3.97 s), take SC01_g1_t5 GENERATED, 4 credits.
`film.py motion` PASS: one monotonic pull 0.5-3.1 s, peak = final 52.7 (no reversal); edge y 215 from 3.1 s to the end =
end still 215. Tech Lead zoom strip: both hands stay under the edge, stops on the brass catches, face hidden at the end.
Not self-accepted: Owner reviews t5. Note: the motion starts at 0.5 s, inside SETUP (0-1 s) - inside the P2 tolerance.
Owner (2026-11-08, "Tạm ổn, tiếp tục"): t5 ACCEPTED (all groups PASS, human:owner-khoikk03). SC01_g1 is done.
Fix found next: every `film.py plan` re-registered each storyboard frame as PENDING even when the PNG was unchanged, so an
Owner approval vanished on the next plan (all 12 frames were PENDING). `StoryboardGate.register` now keeps the review of
an identical image (test in test_drama_preprod_p0).
SC01_g2 v1 redesigned under P13-06 before any take: 8 s = door 0-1.5 (open_door) / walk to the counter 1.5-4
(`walk_across_room`, new: 1.5-3 s) / stoop to the gap under the shutter and speak 4-7 / hold 7-8 (was: cross+speak 1.5-5,
3 s hold). Staging: the shutter covers the window down to the catches, so from the booth THEO must stoop to the gap to talk.
Layout cameras A/B/C now list `shutter_catch` in `sees`. New refs (ChatGPT GPM tab): char_THEO (portrait, not tracked by
the stills registry) and start SC01_g2 (plate B + THEO + end_SC01_g1), registered NOT approved; the door phase text now
matches the still (door pushed with one hand, jar in the other). Open, Owner: approve THEO's look, start SC01_g2 and
storyboard SC01_S2; then one 8 s send (8 credits). Later: MARA's face is hidden by the lowered shutter from camera A; SC02
("looks at him over her glasses") needs staging (she stoops to the gap, or camera C side-on through the glass screen).
Owner approved THEO + start SC01_g2 + storyboard SC01_S2 ("Duyệt, gửi đi"); start uploaded through the Bắt đầu picker,
one 8 s send YES->NO: PASSED (Omni 1.2 Flash, 8 s, cost 8, start slot by pixels 0.4) -> SC01_g2_t1.mp4, take SC01_g2_t1.
Tech Lead QC (strip + zoom): FAIL P0 - the lowered shutter rolls up by itself at 3.0-4.0 s and THEO leans into the opened
window; P1 - his olive rain jacket becomes a black jacket and hoodie. Dialogue present (about 4.6-7.0 s). Waits for the
Owner's verdict; not ingested.
Causes -> fixes: (1) prompt named only changed props, the action named "the gap under the shutter" -> start-frame prompts
now pin unchanged props ("Unchanged the whole shot, nothing moves it: ...", ContinuityState.describe_static); (2) THEO
starts small at the far door, nothing pins his look where he arrives -> plan WARN LOOK_NOT_PINNED (film04: SC01_g2,
SC06_g1). Next (after the Owner rejects t1): `retake --pickup SC01_g2` with end_frame + end_pose (bent at the gap under
the shutter, jar in both hands, olive jacket), draw and approve the end still, one 8 s send.
Owner rejected t1 ("Loại t1, làm bản 2"): ingested (action P0, character P1, cause PROMPT). SC01_g2 v2 = end_frame +
end_pose. First end-still edit raised the shutter (edge row 317 vs 389 in the approved start): the start still's gap was
too small for a face. Fix: kept the end still's geometry and redrew the start from it (edge 315); both registered, NOT
approved (the start changed, so it needs a new approval); storyboard SC01_S2 kept its approval. Plan PASS (199 words).
Follow-up: a still-pair check (static-prop rows/diff between start and end stills) as a tool, not only an eye check.
Owner approved start/end SC01_g2 v2 ("Duyệt, gửi đi", 2026-11-08). The start was uploaded twice (same bytes); the picker
token tail missed and the pixel search refused two equal matches -> START_NOT_FOUND twice (intents t2, t3; nothing
submitted, 0 Flow credits). Fix in `flow_send._picker_find_image`: a runner-up with the same thumbnail bytes is the same
still, take the best (test_flow_send_picker). Third run PASSED -> SC01_g2_t4.mp4 (7.96 s), take SC01_g2_t2 GENERATED,
8 credits; autoqc 0 warnings. Tech Lead strip: shutter edge holds its height the whole shot, jacket stays olive, door
0-1.5 s, crosses to the counter, appears in the gap at 3.3 s, speech 4-7 s (-28 dB), quiet hold 7-8 s. Waits for Owner.
Follow-up: `generate` budget counts a failed intent (START_NOT_FOUND, nothing submitted) at its expected credits
(credits_spent 124 -> 140 for one 8-credit take); a pre-submit failure should count 0.
Owner accepted SC01_g2_t2 ("Nhận, tiếp tục", 2026-11-08; all groups PASS, human:owner-khoikk03). SC01 is done.
SC02_g1 restaged before any take: from camera A (hall) the shutter on its catches hides a standing MARA's face, so
she lets go of the edge and sits on her stool (sit_down 0-2), glances at the clock (turn_head 2-3), speaks 3-5, holds
5-6 = 6 s; camera height CHEST, end_frame with her face in the gap. MARA is "seated on her stool" in every state
SC02_g2..SC05_end. Shutter state text anchored to the set ("a face-high gap left above the counter", was "at her
chest height"; playbook §7.5). Start still = the approved end still of SC01_g1 (same camera, 0 credits); end still
drawn in ChatGPT from it (shutter edge and catches on the same row, tray/clock/lamp unchanged). Both registered, NOT
approved; storyboard SC02_S1 PENDING. Plan: SC02_g1 BLOCKED only on the storyboard. Stills tests now read the
end-frame shots from the film data. Next: Owner approves start/end SC02_g1 + storyboard SC02_S1; upload, one 6 s send.
Owner approved start/end SC02_g1 + storyboard SC02_S1 ("Duyệt, gửi đi", 2026-11-08). First send: START_NOT_FOUND (no
submit): the start reuses end_SC01_g1, already in the gallery; the two thumbnails scored 1.4 each but were 2 bytes
apart, so the byte rule missed. `flow_send.same_image` now compares the two candidates' pixels (<= SAME_STILL_MAX).
Second send PASSED -> SC02_g1_t2.mp4 (6.04 s), take SC02_g1_t1 GENERATED, 6 credits; autoqc 0 warnings.
Tech Lead QC: P0 action. She pushes the pinned shutter up at 0.75-1.25 s (her hands start hooked under its edge), it
stays up to 3 s, then drops back to the catches over her forehead (end-frame snap). Speech 3-5 s is fine.
Pipeline gap: autoqc and `film.py motion` measured only props declared to move. `tracked.direction: "still"` +
`trajectory.judge_still` flag a pinned prop that moves (PINNED_PROP_MOVED, P0); SC02_g1 declares the shutter still;
on t1 it FLAGs 30 px at 3.2 s. Proposed v2 (after the Owner's rejection): start still with her hands already off the
shutter (standing, hands at her sides), the sit-down phase without any word about the shutter edge.
Owner rejected t1 ("Loại t1, làm bản 2"): ingested (action P0, cause START_FRAME). `retake --pickup SC02_g1` -> v2:
phase 0 "standing ... with her hands at her sides, sits down on her stool"; phase 2 "she speaks to him through the gap"
(was "without lifting the shutter"). New start still: ChatGPT edit of the old one, hands off the shutter, edge and
catches on the same row as the approved end still. Registered NOT approved (end still and storyboard keep their
approval). Plan PASS (171 words). Next: Owner approves the v2 start still; upload, one 6 s send, `film.py motion`.
Owner approved the v2 start still ("Duyệt, gửi đi"). Send PASSED -> SC02_g1_t3.mp4 (6.01 s), take SC02_g1_t2, 6 credits.
QC: `film.py motion` FLAG PINNED_PROP_MOVED 22 px at 1.6 s (the new check caught it; autoqc 0 warnings). With no hand
on it, the shutter still rises at 0.75-1.75 s to show her face, drops back at 2-2.5 s and covers her forehead to the
end. Second take with the same defect: lowering a body until the face enters a fixed gap is beyond the model; it
moves the gap instead. Proposed v3: no body travel against the pinned prop inside the shot. Start already seated with
her face in the gap (the approved end still as start frame), 5 s: glance at the clock and back, speak, hold. She sits
down across the cut from SC01_g2 (camera B, behind her), which costs a small standing-to-seated jump. Waits for Owner.
Owner rejected t2 ("Loại t2, chạy A"): ingested (action P0, cause STAGING). v3 written (5 s, seated, GREEN). Owner
approved the v3 start still (= approved end still) and sent ("Duyệt, gửi đi"). Send PASSED -> SC02_g1_t4.mp4 (5 s),
take SC02_g1_t3, 5 credits. QC: `film.py motion` PASS (shutter peak 0.27 px), autoqc 0 warnings; strip: shutter stays
on its catches, face in the gap throughout, glance up 0.5-1 s, speech about 2-4 s. Waits for Owner take review.
Open, Owner: approve start/end SC01_g1 + storyboard; then upload both stills, one 4 s send (about 4 credits, YES->NO),
`film.py motion` before the eye review. Later stills of the window (SC01_g2..SC05_g2) and the location plates must show the
catches (`film.py impact --design prop_shutter`). Planning budget still uses the 12-credit basis per generation.

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


## P14 — Gaps found by the external comparison (Tech Lead, 2026-11-07)

Source: desk research of public e2e AI film/drama systems (ViMax, MVAgent, DramaChain Bench, "Lights, Camera, Consistency",
OpenMontage, manju-laoli Director Suite, Dramake, Story Claw). Our direction grammar and gates are deeper than all of them; these
items close the gaps where they are ahead. All offline (0 credits) unless marked LIVE. They do not compete with P8-02: film04
waits on the Owner's take review. Assist signals stay WARN/ranking only; nothing here may ACCEPT a still or a take.

### P14-01 Map external rule sets onto our preflight — READY
Read (web, no downloads, nothing executed) the prompt/plan rules of manju-laoli Director Suite
(`github.com/lixiaoxiao9888-create/manju-laoli-skill`: `validate_prompt.py` C1–C33, H1–H12, `gate_check.py`) and Dramake
(`github.com/xixihhhh/ai-short-drama-skill`: `validate_plan.py`, four gates, continuity ledger, voice bible). Write
`docs/research/EXTERNAL_RULES_MAP.md`: one row per external rule → our rule/code path (`preflight`, `feasibility`, `axis`,
`set_layout`, `gate_checks`) or MISSING or N/A with reason. Each MISSING rule that matches a defect we actually hit (film01–04
lessons, P13 reviews) becomes a new READY item with that evidence; others are listed, not built. Licenses recorded; no code copied.
Done when every external rule has a row.

### P14-02 Best-of-N start stills — READY
Files: `production/stills.py`, `tools/film.py stills`, `production/reviewpack.py`, tests. Today a generation has one registered
still. Allow N candidates per generation (default 2; image mode is 0 credits) under `stills/<gid>/cand_<k>`; the review pack shows
them side by side with the plate and the readout; `approve` names the chosen candidate and records the others as REJECTED with an
optional cause. Gate 3 and `approved_still_path` keep their current contract (one approved still). Evidence: ViMax reports best-of-2
keyframe selection +3.8% cross-shot consistency, best-of-3/4 no further gain. Done when film04 stills list/approve works with 2
candidates in a test package and existing still tests pass unchanged.

### P14-03 VLM checklist judge for stills and takes (WARN) — READY (after P14-02)
Files: new `production/vlm_check.py`, reuse `gemini_semantic.py` (`GeminiSemanticQCEvaluator`, key handling, fingerprint), `film.py
review`, tests with a fake evaluator. Build a yes/no checklist from the plan: readout facts + evidence (`set_layout`), people in frame,
choreography phases and `once_actions`, performance `visible_cues` and `prohibited_misread`, start/end state. Ask it on the still
and on sampled take frames (first/last/phase midpoints). Output: per-question answer + frame, written into the dailies template as
pre-filled WARN; also a ranking of P14-02 candidates. Never PASS/ACCEPT. Log every judge answer next to the human verdict so
agreement can be measured (VLM yes/no judges are known to lean "yes"); report agreement on film04 takes once they exist. Live API
calls only with a key already configured for the project; tests use a fake. Done when a film04 dailies template carries the
checklist and the agreement report runs on recorded verdicts.

### P14-04 Dialogue check: what was said vs the script (WARN) — READY (ASR install: Owner decision)
Files: new `production/dialogue_check.py`, `film.py review`, tests. `master_qc` already checks dialogue-cue timing against the
dialogue stem (row 142); nothing checks the words. Compare a transcript of each take with its `SpokenLine`s (Vietnamese): missing,
extra or swapped lines, word error rate, speech outside the speaker's shot window, speech when the plan says silence. Build the
comparison with an injected transcript first (fixtures); the ASR backend (e.g. faster-whisper, local model) is a dependency install
→ `BLOCKED: needs Owner` for that part only, as WP4 was. Evidence: DramaChain Bench's weakest automated score is shot-level
audio-visual sync (1.49/5). Covers rows 74, 142. Done when the comparison runs on fixtures and the dailies template shows the WARNs.

### P14-05 Voice bible per character — DONE (2026-11-08: start-frame prompts carry the voice words on every line; CharacterSpec.voice_reference; dailies ask "same voice as <take> a-b s?"; THEO = SC01_g2_t2 4-7 s, MARA after her first accepted speaking take; 4 tests. Not done: BLOCK on an empty voice for a speaker - all film03/film04 speakers have one)
Files: `03_preprod` schema (`production/sections.py`), `drama/prompt.py` dialogue block, `continuity.py`, tests. Each speaking
character gets a fixed voice description (age, pitch, pace, accent, timbre words) and, once a take is accepted, a reference clip
(take id + time range). Prompts carry the same voice words in every scene; `validate` BLOCKs a speaking character without a voice
entry; take review asks "same voice as the reference clip?". No audio embedding yet. Evidence: Dramake and Story Claw keep a
per-character voice map; we only describe voice per line. Done when film04's characters have entries and prompts compile within the
word budget (golden film03 unchanged or diff justified).

### P14-06 Defect taxonomy aligned with DramaChain Bench — READY
Files: `production/qc_model.py`, `drama/kpi.py`, `production/report.py`, tests. Read the DramaChain Bench paper
(arXiv 2609.00646) axes and leaf dimensions; map our review cause codes and 16 QC groups onto them (table in
`docs/research/EXTERNAL_RULES_MAP.md` or its own file). KPI ledger then reports defects by stage that missed them **and** by
benchmark axis, so our numbers can be compared with published ones. No change to existing verdicts. Done when `film.py status`
prints the per-axis count for film01–03 ledgers.

### P14-07 Motion conditioning beyond text + start frame: capability study — READY (offline part)
Files: `docs/research/MOTION_CONDITIONING.md`, provider capability manifest. SHOT08 (push → backward recoil) failed with text +
start frame only. Record, per provider we can reach (Flow Veo 3.1, Dola Seedance 2.0), which conditioning exists: last frame,
multi-image ref, video reference (Seedance Omni Reference: up to 3 clips), pose/depth/control video; mark each MEASURED or ASSUMED.
Propose one A/B (text-only vs video-ref from a staged reference clip or animatic) for a contact/recoil beat with its credit
estimate. The run itself is a separate LIVE item (Omni Flash 360p on Flow, or Dola within its quota) only after Owner go-live.

### P14-08 API provider fallback: interface only — READY
Files: `providers/base.py` (read first), new `providers/api_stub.py`, capability manifest, tests. The browser routes (Flow, Dola)
are the fragile part of the system. Define what an API route would need to satisfy the same take contract (intent receipt, output
hash, route/model in the take log, credits/cost) and add a stub adapter that refuses to send. No keys, no network, no paid account;
using a paid API (e.g. BytePlus ModelArk) remains an Owner decision (handoff 2026-10-31: backup only). Done when the stub passes the
same take-log tests as the mock runner.

## P15 — Found by the film04 shot quality review (Tech Lead, 2026-11-08)

Evidence: [FILM04_SHOT_QUALITY_REVIEW.md](FILM04_SHOT_QUALITY_REVIEW.md). 5 of 6 rejected takes fail on one articulated prop; 10 of
18 sends failed in the UI; one take per review loop. Order and merge with P14: see "Completion plan" at the top.

### P15-01 Generability rating per beat at Gate 2 — DONE (2026-11-08: drama/generability.py, `film.py generability`, gate3 issues GENERABILITY_RED/_WAIVED/_AMBER, film03 pinned off; film04: SC04_g1, SC04_g2, SC05_g1, SC05_g2 RED and BLOCK, SC01_g1/g2 RED waived, SC03_g1 + SC06 AMBER, rest GREEN; 20 tests)
Files: new `drama/generability.py`, `production/gate_checks.py` (G2), `docs/director/DIRECTOR_PLAYBOOK.md` §2-§5, tests from film04
takes. Rate each choreography phase GREEN / AMBER / RED from data lists (review §4: articulated prop at a partial position, pinned
prop near a moving body, hands on small objects, pouring/granular, counting, readable text, body entering a fixed gap = RED). RED
blocks G2 unless the shot carries a restage (cut-around, prop-only insert, off-screen + sound, prop out of frame). Read the
feasibility rules of P14-01's sources first and fold matching ones in. Done when film04 v1 SC01_g1 and SC02_g1 v2 rate RED,
SC01_g1 v5 and SC02_g1 v3 do not, and the playbook rule on "two 8 s generations" is amended.

### P15-02 Frame-delta check on start/end stills — DONE, reduced (2026-11-08: stills.pair_check on approve: LARGE_DELTA, PINNED_PROP_DIFFERS, SAME_IMAGE; WARN only; 7 tests. Finding: on the real SC02_g1 v2 pair the pixel delta near the shutter was 0.015, the same as a harmless edit (0.01), so "a body moves next to the pinned prop" is rated from the text by P15-01, not from pixels)
Files: `production/stills.py`, `film.py stills`, tests. Before an end still is approved: same camera and light (plate diff), pose
distance between start and end small, no pinned/tracked prop ROI overlapping the moving body's path. Large delta = WARN in the
review pack with the reason. Done when SC02_g1 v2's pair warns and SC01_g1 v5's does not.

### P15-03 Best-of-N takes at 360p — READY (after P15-06)
Files: `film.py generate --drafts N`, take log, review pack. N sends of one intent (N=1 GREEN, 2 AMBER, 3 restaged RED), each a
take; automatic QC runs on all; the review pack shows a draft table with QC results; only the Owner accepts. Budget counts only
sends that produced a video (fixes the P13-06 overcount). Done on a mock runner with 3 drafts.

### P15-04 = P14-03 (VLM judge), extended — READY (after P14-02)
Add to P14-03's checklist: end-still match on the last second, tracked-prop position vs the end still, look bible per visible
character. WARN and ranking only.

### P15-05 Flow capability probe: clip edit and character references — LIVE-routine (test videos, ≤ 20 credits)
Covers P14-07's Flow part. 0-credit UI read first: does Flow offer an edit on an Omni 1.2 clip; can a start frame and character
references go in one send. Then at most two 360p sends: (a) edit SC02_g1 t2 "keep everything else the same, the shutter does not
move"; (b) a THEO shot with start frame + 2 refs. Record MEASURED results in the capability manifest and the playbook.

### P15-06 Send reliability — READY
Files: `tools/drama_flow_ui/flow_send.py`, tests. Upload the still inside the send so it is the newest picker item; keep the pixel
match as a check of the slot, not as the search. Done when the picker tests pass and the next 5 live sends have no
START_NOT_FOUND / AMBIGUOUS.

### P15-07 film04 restage of RED beats — PROPOSED, waits for the Owner ([FILM04_RESTAGE_PROPOSAL.md](FILM04_RESTAGE_PROPOSAL.md))
SC04_g1 (glasses on a chain), SC04_g2 (shutter up + coins pour, two people), SC05_g1 (counting coins), SC05_g2 (stamp), and any
shot where the shutter edge is near a moving body. Proposal per beat with the restage tool and credit estimate → Owner chooses →
package edit → stills. No send before the Owner's choice.

## P16 Interaction contract (Claude x Codex, 2026-11-08) — plan in [PRODUCTION_PROCESS_V2.md](PRODUCTION_PROCESS_V2.md) §9

Trigger: Owner on take SC02_g1_t3 (MARA speaks to an empty counter): "cô ấy đang nói chuyện với ai? Các quan hệ có vẻ không được
đảm bảo". Same unanchored-listener pattern in SC02_g2, SC03_g2, SC04_g1, SC05_g1. Order: P16-01 -> 02 -> 03 -> 04 -> 05 -> 06 ->
07a -> 08 -> 09 (LIVE) -> 07b -> 10. Done-criteria live in the plan table; each item here is one loop round.

### P16-01 Ledger reconcile — DONE except the Owner's t3 verdict (2026-11-08)
film04: 19 sent receipts. 10 became takes (matched by output file; take ids are offset from receipt ids, e.g. take
SC01_g1_t4 = receipt SC01_g1_t10 AMBIGUOUS, bound by hand). 6 stopped before submit (START_NOT_FOUND: frame not found in the
picker, prompt never entered, 0 credits). 3 were submitted and never became a take: SC01_g1_t1 UNBOUND, t3 AMBIGUOUS, t5
UNBOUND (12 each, reserved until checked in Flow). Credits: 85 logged + 36 unresolved = 121 of 256.8, 135.8 left.
Fix: `generate.credit_ledger` matches receipts to takes by output file and skips pre-submit failures (`PRE_SUBMIT_RESULTS`);
before it, `generate` counted 170 (every receipt id missing from the take ids was charged again). Test
`test_credit_ledger_matches_receipts_to_takes_by_output_file_and_skips_pre_submit_failures`. Open: Owner verdict on
SC02_g1_t3 (status GENERATED); the 3 unresolved sends can be released only after checking Flow for their clips.
### P16-02 Interaction-contract schema + checks — DONE (2026-11-08)
`production/interaction.py` (ActorMark, ActorPose, ListenerAnchor, `interaction_issues`); opt-in
`preflight.interaction_contract`; `SetLayout.marks`, `ContinuityState.blocking` (omitted from dumps when empty, goldens
unchanged), `SceneSpec.encounter_id`, `ShotDecl.addressees/listener_anchors/gaze_target`. Checks ADDRESSEE_MISSING/ABSENT,
LISTENER_ANCHOR_MISSING, ANCHOR_CONTRADICTION, OFF_FRAME_TOO_WIDE/NOT_ESTABLISHED/WRONG_SIDE, MARK_UNRESOLVED,
GAZE_TARGET_MISSING/UNRESOLVED, GAZE_INTO_LENS (WARN). 11 tests on a film04 copy: v3 as shot BLOCKs, five false OFF_FRAME
claims BLOCK, OTS v4 and an established CLOSE off-frame single pass. film04 data not yet opted in (P16-07a).
### P16-03 One placement source for still + video prompts; explicit camera.size wins — DONE (2026-11-08)
Contract route only (contract off = byte-identical, film04 shipped prompts reproduced). `interaction.placement_sentences`
("X speaks to Y", OTS shoulder sentence, OFF_FRAME placement + eyes past the lens, object gaze) goes into the still prompt
and, through handles, the video prompt (`compile_scene_prompt(placement=...)`); no "Only X in frame" with 2+ present; props
held by hidden people dropped from the video prompt; still framing word from `camera.size`; HIDDEN_PERSON_UNPLACED BLOCK.
Known limits: `CoverageShot.describe` still hardcodes "close-up of" for SINGLE (camera size only reaches the still); authored
choreography pronouns ("at him") are not checked — write names in P16-07a.
### P16-04 Relation review questions with required QC evidence — DONE (2026-11-08)
Contract route: `relation_review.py` derives REL_ADDRESS:n / REL_LISTENER:name / REL_GAZE / REL_BARRIER per generation;
dailies list them in `qc.required_answers`; a take stays INCOMPLETE until each has a non-blank human answer in its QC
group. Existing takes: `film.py review --supplement <take>` writes `<take>.relations.review.json` (never overwrites);
ingest combines it with the main review. CLI ingest re-derives the ids from the package and refuses sheets that drop
any. Stills register lists the questions. 6 tests; contract off unchanged.
### P16-05 Encounter continuity across scene numbers — DONE (2026-11-08)
Contract route: scenes sharing `encounter_id` are continuous for handoff severity, emotional carry-over and once-action
repeats. New SPATIAL_HANDOFF_BLOCKING (mark/posture) BLOCK; `ShotDecl.handoff_ellipsis` (reason) turns spatial handoff
findings into WARN `*_ELLIPSIS`; lighting/time/location stay BLOCK. 5 tests; contract off unchanged.
### P16-06 Generability v2 (UNKNOWN, exceptions, caps proven at the generation entry point) — DONE (2026-11-08)
GREEN/AMBER/RED/UNKNOWN (unmatched ACTION -> UNKNOWN; HOLD scanned for mechanism/text); send caps 1/2/1/0.
RED needs `accepted_take_reuse` (no new send) or an Owner `generability_exception` bound to version + prompt sha,
attempt/credit cap and expiry; free-text waivers demote nothing (WARN LEGACY). `generate` blocks SEND_CAP,
AWAITING_REVIEW (2nd AMBER), EXCEPTION_MISMATCH/EXPIRED/SPENT, ACCEPTED_TAKE_REUSE; payload carries `attempts`.
Film04: SC01_g1/g2 waivers migrated to reuse of t5/t2. 12 entry-point tests + 24 rating tests.
### P16-07a Pilot exchange SC01_g2 -> SC02_g1 v4 (OTS over THEO) -> SC02_g2 (OTS over MARA): package + stills — PACKAGE DONE (2026-11-08); stills next, then Owner approves board/stills
Film04 `interaction_contract` on. Marks clerk_stool / customer_window / hall_door; encounter `window_plea` (SC01-SC05);
blocking on SC01_g1..SC02_end (MARA seated through SC01_g2 per the accepted take's frames). SC02_g1 v4 = OTS over
THEO from camera A (addressee 22 -> THEO, anchor OTS_FOREGROUND, gaze THEO; end frame dropped: no state change).
SC02_g2 v2 = reverse OTS over MARA from camera B (SC01_g2 framing). Pilot gate3: only STORYBOARD + AMBER WARN.
Found: SC01 occupancy put THEO's ENTER at index 1 but plan.gen_index is 1-based (he entered in SC01_g1 on paper);
fixed to 2. Pipeline gap -> P16-07b: check that an ENTER at generation k matches a position in k's start state.
Open: SC02_g1 `tracked.roi` was drawn on the v3 still; re-measure on the approved v4 still. SC03-SC06 BLOCK on
contract data until P16-07b (expected). `02_direction.coverage_plan.B2` SINGLE -> OTS (gate 2 tracks the restage).
Pilot prompts trimmed to <= 215 words (SC01_g2 214, SC02_g1 ~211, SC02_g2 ~214).
Stills (2026-11-08, Owner: 'Dùng chatgpt vẽ ảnh, trên cùng profile (mở tab mới)'): SC02_g1 v4 = ChatGPT edit of the
approved v3 still in a new GPM tab, try 2 (try 1 put THEO beside the glass, kept in history). SC02_g2 v2 = reuse of the
approved end_SC01_g2 still (same camera B, state SC01_end = SC02_g2). Both registered UNAPPROVED, 0 credits;
review sheet media/review/P16-07a_pilot_stills.jpg. Owner approved both (2026-11-08, 'Approve both').
SC02_g1 `tracked.roi` re-measured on the v4 still: [0.46,0.05,0.66,0.55] (shutter slats, clear of THEO's head).
P16-07a DONE. Next: P16-08.
### P16-08 Send reliability offline (= P15-06) — DONE offline (2026-11-08); live proof in P16-09
`flow_send.py --upload-frames`: the start (then end) still is uploaded inside the send; `_picker_newest` checks only the
newest k picker items by pixels (no list search, no wheel down) -> `START_NOT_FOUND upload` (pre-submit, 0 credits).
`generate` without `--start-token` now emits the upload route (token route kept). Reconcile: `flow_bind.reconcile` +
`flow_reconcile.py` (read-only gallery walk, 0 credits) bind UNBOUND/AMBIGUOUS receipts by whole prompt + unknown
media id; `--download` saves `<receipt>.mp4` for `takes --register`. Limit: receipts hold only prompt_sha256, so a
receipt whose plan prompt changed since reports NO_PROMPT/PROMPT_CHANGED (film04 SC01_g1 t1/t3/t5 likely). 13 new tests.
Done-criterion from P15-06 (5 live sends without START_NOT_FOUND/AMBIGUOUS) is measured from P16-09 on.
### P16-09 Live pilot: SC02_g1 then SC02_g2, 360p Omni Flash, adjacent cuts — LIVE, Owner review
### P16-07b Rollout SC03-SC06 merged with P15-07 — waits for P16-09 and the Owner's P15-07 choice
### P16-10 Shoot SC03-SC06; later projection detector, reference route probe, VLM judge (advisory), voice/sound evidence — LIVE
