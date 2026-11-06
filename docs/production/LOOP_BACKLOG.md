# Loop backlog — E2E production system

OWNER_GO_LIVE: NO
<!-- Owner flips to YES to allow LIVE items (real Flow/ChatGPT generation). Tech Lead never flips it. -->

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

### P1-01 Story bible model + Gate 1 — READY
Typed `01_story.json`: concept, theme, genre, audience (who/expectation), premise + central conflict, logline,
structure (acts with beats: id, function SETUP/INCITING/ESCALATION/MIDPOINT/CRISIS/CLIMAX/RESOLUTION, scene ids),
plot + subplots, characters (want, need, flaw, arc_change, change_scene_id), scenes (purpose, conflict, outcome,
value shift +/−), adaptation {source, rights_status, fidelity_notes}, rewrite log.
Gate 1 BLOCK rules: every scene has purpose/conflict/outcome and appears in ≥1 beat; every beat function in order;
each protagonist arc has a change scene that exists; logline names protagonist + goal + obstacle; adaptation with
`rights_status != cleared` → OWNER_PENDING (not PASS). Fill film03's story file from its Fountain/README.
Tests with good/bad fixtures.

### P1-02 Director's treatment + per-scene direction — READY (after P1-01)
Typed `02_direction.json`: vision (tone, references as words), visual language rules (list of rule + why),
per scene: POV (whose, what audience knows vs characters — tie to `comprehension` facts), dramatic emphasis
(moment, device: insert/push/hold/reaction), emotional curve (start/end intensity 0–5 per character), pacing
(target avg shot length, hold points), transitions in/out (cut/dissolve/match/J/L + reason), coverage plan
(required shot types per beat). Checks: emotional jump > 2 between consecutive scenes without a cause beat → BLOCK;
every beat has ≥1 carrier shot in 04_shots (Gate 2, reuse `drama.coverage`/`comprehension`); every reveal has an
emphasis device. Fill for film03.

### P1-03 Director playbook — READY (after P1-02)
`docs/director/DIRECTOR_PLAYBOOK.md`: how the model authors each stage file, in order, with decision checklists
mapped to categories 1–56, lessons from `docs/drama/FILM01_LESSONS.md`, film02 comprehension failure, film03 README,
WP5 route, Owner SRT faithful-action rule (`docs/sot/film/05_PROMPT_COMPILER.md` in the root repo), provider limits
(8 s generations, start frame route, prompt budget 170 words, moderation notes in memory `flow-picker-and-moderation`).
Include a worked example (film03) and "red flags" list. Also `.claude/skills/film-director/SKILL.md` pointing to it
(name, description, when to use). No code.

### P1-04 Narration profile adapter — READY (after P1-02)
For profile `narration`, `film.py` wraps `e2e.py` (prepare/status/resume/finish) so a narration film is a package too:
story beats come from SRT sentences (`drama.action_meaning.sentences`), shots carry `action_meaning`. Test: package
built from the E2E test fixture validates and `status` matches `e2e.status` fields.

## P2 — Pre-production (35–56)

### P2-01 Design versions + dependency index — READY (after P1-02)
Character look, costume, hair/makeup, prop and location entries carry `version`; shots reference `id@version`.
`production/impact.py`: `affected_by(change) -> shots, stills, takes, edit ranges, post items` (G13).
Test: bump film03 Nora costume version → exactly the shots where Nora is in frame are listed; others untouched.

### P2-02 Prop/object state machine + 6 continuity types — READY (after P2-01)
Continuity bible: per generation start/end state across action, spatial, object, temporal, visual (lighting, time of
day), emotional. Object changes need a causing action in an ACTION phase. Reuse `drama.continuity`,
`scene_bible`, `sequence.validate_shot_sequence`. Test: letter moves pocket → bin without an action → BLOCK.

### P2-03 Camera & lighting plan — READY (after P2-01)
Per scene: key light direction/quality/colour temp, practicals; per shot: size, angle, height, movement, lens intent,
composition note. Check against axis book (camera side) and shot-size variety (no 3 identical sizes in a row unless
declared). Compiled into prompts only where the route supports it (document which fields reach the prompt).

### P2-04 Animatic — READY (after P2-03)
`film.py animatic`: storyboard frames (schematic or approved stills) timed to the planned durations with temp
dialogue/narration audio when available (TTS optional, offline-only libs; otherwise silence + subtitles), FFmpeg mp4
under `films/<id>/media/animatic.mp4`, plus timing report. Gate 3 input. 0 credits. Test with tiny fixtures.

### P2-05 Budget, schedule, risk, legal — READY (after P2-01)
Estimate credits = generations × cost/gen × expected retake factor (from KPI ledgers film01–03), schedule order
(dependency: start frames before videos), risk list (physical contact/interaction shots flagged with fallback
coverage plan), legal: character/location/music/source rights entries. `validate` shows budget and risks.

## P3 — Production (57–90, 131–140 shot level)

### P3-01 QC taxonomy P0/P1/P2 — READY (after P0-05)
`production/qc_model.py`: QC record per take with the 16 groups 131–146, each `PASS/FAIL/UNASSESSED`, severity
P0/P1/P2, level `STILL|SAMPLED|FULL_MOTION|CUT`, evidence path, reviewer (`human:<id>` or `auto:<tool>`).
Rule: auto tools may only produce WARN/UNASSESSED for content groups; only a human review can PASS
narrative/action/motion/performance. Shot accepted iff no P0 FAIL and P1 FAILs explicitly waived with reason.

### P3-02 Take log + dailies review — READY (after P3-01)
`takes/` index: take id, generation id, prompt hash, start-frame hash, model/route, credits, output hash, status.
`film.py review --film DIR` writes a dailies template per new take (QC groups, the shot's `qc_questions` from
action_meaning, choreography timing, expected start/end state) and ingests a filled one. Integrate
`drama.autoqc` as WARN evidence when models are available (skip cleanly when not).

### P3-03 Retake / pickup policy — READY (after P3-02)
After a FAIL: classify cause (prompt, start frame, provider limit, staging). Same cause twice → propose change of
approach (re-stage, split into two shots, insert/reaction coverage, different start frame) instead of retry;
pickup list feeds back into 04_shots as new shot versions with `repair_of`. Tests on synthetic take logs.

### P3-04 Generate stage via package (offline mock) — READY (after P3-02)
`film.py generate --film DIR --shot ID --dry-run` builds the exact send payload for `tools/drama_flow_ui/flow_send.py`
(start frame + "Khung hình" route) and records an intent receipt; without `--dry-run` it refuses unless
`OWNER_GO_LIVE: YES` is in this backlog **and** film budget allows. Mock-session test only.

### P3-05 LIVE canary: one generation through the package — LIVE (after P3-04)
Omni Flash 360p, one shot of film04 (or a film03 pickup), full path: start frame → send → acquire → take log → review
template. Stop after one attempt; report.

## P4 — Editorial (91–106)

### P4-01 EDL model + assembly from selects — READY (after P3-02)
`05_edit.json`: ordered events {take_id, src_in, src_out, transition {type, duration}, audio {j_cut_s, l_cut_s}},
cards/tags as events. `film.py cut` renders via FFmpeg (reuse `drama.post`, `rough_cut`). Golden: film03 events
reproduce the existing final timeline duration within 1 frame per event.

### P4-02 Fine cut tools — READY (after P4-01)
Dissolve/match cut/J-L cut rendering; rhythm report (shot lengths vs 02_direction pacing, holds > plan flagged);
continuity-edit check across cuts (end/start states, axis side, eyeline) reusing P2-02.

### P4-03 Picture lock + invalidation — READY (after P4-02, P2-01)
Lock = hash of EDL + source take hashes. Any change after lock marks dependent post/QC/delivery items dirty
(`impact.py`). Test: change one src_out after lock → subtitles, mix, master QC flagged dirty.

## P5 — Sound & finishing (107–130)

### P5-01 Audio stems + mix — READY (after P4-01)
Separate stems: dialogue (from takes), ambience/room tone per location, SFX cues (from 04_shots `sfx`), music.
Mix with ducking under dialogue, J/L crossfades, loudness target −14 LUFS / −1 dBTP (reuse
`drama.post.normalize_loudness`, `measure_ebur128`). Sources: generated tones/noise beds offline, or CC0 libraries
recorded in the rights ledger (no untrusted downloads). Test with synthetic stems: ducking depth, peaks, loudness.

### P5-02 Music & SFX sourcing record — READY (after P5-01)
Rights ledger entries (source, license, hash, usage range). `validate` blocks delivery when any used asset lacks a
cleared license. Music cue sheet from 02_direction emotional curve (where music starts/stops and why).

### P5-03 Colour matching + grade — READY (after P4-01)
Per-shot normalisation (exposure/white balance from frame stats) toward the scene reference, then the global look
grade (`drama.post.GRADE` as default). Report before/after deltas per shot. Test on synthetic coloured clips.

### P5-04 Titles, credits, subtitles, reframe — READY (after P4-01)
Credits card from package (cast = characters, AI disclosure line, rights credits); subtitles EN/VI from dialogue +
cards (reuse `drama.post`); reframe/stabilise options per event (crop box) for 9:16 later.

## P6 — Final QC & delivery (141–156)

### P6-01 Master technical QC — READY (after P5-01)
Black frames, freeze frames, duplicated frames, fps/codec/resolution, audio clipping/silence gaps, subtitle sync
offsets, loudness compliance (ffmpeg blackdetect/freezedetect/silencedetect/ebur128). Record in QC model level CUT.

### P6-02 Versions, metadata, packaging — READY (after P6-01, P5-04)
16:9 master + 9:16 reframe (crop boxes from P5-04, face-aware via `drama.tag_layout` detection when available),
thumbnail candidates (frames from emphasis moments), metadata draft (title, description, tags, AI disclosure,
credits). No publishing.

### P6-03 Archive + restore test — READY (after P6-02)
`film.py deliver` writes `delivery/` (masters, sidecars, disclosure/C2PA via `drama.disclosure`, manifests with
hashes, rights ledger, QC records, package JSON). Restore test: copy to a new temp dir, `film.py status --package`
verifies every hash and reports missing dependencies.

## P7 — Management (157–168)

### P7-01 Status report + ledgers — READY (after P6-03)
`film.py status` covers: gates, stage completeness, credits spent vs estimate, usable seconds, retake rate, open
P0/P1, dirty items, rights blockers, next action. `ledger.json` learnings (observation vs replicated) per film.

### P7-02 Re-run film03 end-to-end through the package — READY (after P7-01)
Using existing film03 takes (no generation): plan → review (import existing gate/QC data) → cut → post v2 (with
ambience/music/colour match) → QC → deliver. Report diffs vs the shipped final. Phase end: full suite, push, status.

## P8 — Proof film

### P8-01 film04 authored from scratch by the model — READY (after P1-03, P2-04, P7-01)
Following `DIRECTOR_PLAYBOOK.md` only, author an original 90–120 s drama (new characters/location; no real persons;
Owner rules on moderation). All stage files through 03_preprod + 04_shots; `validate` all gates PASS or
OWNER_PENDING; animatic rendered; budget estimate. No new Python specific to film04 — any need becomes a system item.

### P8-02 film04 production — LIVE (after P8-01)
Generate per plan within budget, dailies review, retake/pickup policy, cut, post, QC, deliver. KPI vs film02/03
(credits per usable second, first-pass rate). Owner creative review required; never self-accept.

## P9 — Found by the loop

### P9-01 `test_dispatch_recovery` F0/F1 needs `film_pipeline` importable in its subprocess — READY
Evidence (2026-11-06, full suite): `tests/test_dispatch_recovery.py::test_F0_requires_fresh_authority_and_F1_real_process_exit_is_durable`
runs `python -c "from film_pipeline..."` as a subprocess and gets `ModuleNotFoundError` (returncode 1, expected 72) because
`pythonpath = ["src"]` only applies to the pytest process. Fix: pass `env` with `PYTHONPATH=<repo>/src` (or `cwd`/`-I` aware)
in that subprocess call. Do not weaken the assertion.

